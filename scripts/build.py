#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Fetch pinned sources, prepare one profile, build and inspect it. Never flash."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import urllib.request

REPO = Path(__file__).resolve().parents[1]
LOCK = json.loads((REPO / 'sources.lock.json').read_text())


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(args, cwd=None):
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def capture(args, cwd=None):
    return subprocess.check_output(list(map(str, args)), cwd=cwd, text=True).strip()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def recipe_digest():
    h = hashlib.sha256()
    paths = [REPO / 'sources.lock.json']
    for directory in ['configs', 'patches', 'files', 'scripts']:
        paths.extend(p for p in (REPO / directory).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts)
    for p in sorted(paths):
        h.update(str(p.relative_to(REPO)).encode() + b'\0' + p.read_bytes() + b'\0')
    return h.hexdigest()


def overlay_digest(directory):
    h = hashlib.sha256()
    for p in sorted(directory.rglob('*')):
        require(not p.is_symlink(), 'Unexpected symlink in image overlay')
        if p.is_file():
            h.update(str(p.relative_to(directory)).encode() + b'\0')
            h.update(str(p.stat().st_mode & 0o777).encode() + b'\0' + p.read_bytes())
    return h.hexdigest()


def fetch_git(spec, destination):
    require(re.fullmatch(r'[0-9a-f]{40}', spec['commit']), 'Expected full Git commit')
    require(spec['url'].startswith('https://'), 'Only public HTTPS source URLs supported')
    destination.mkdir(parents=True)
    run(['git', 'init', '-q', destination])
    run(['git', 'remote', 'add', 'origin', spec['url']], destination)
    run(['git', 'fetch', '--depth=1', 'origin', spec['commit']], destination)
    run(['git', 'checkout', '--detach', 'FETCH_HEAD'], destination)
    require(capture(['git', 'rev-parse', 'HEAD'], destination) == spec['commit'],
            'Fetched source does not match lock')


def bootstrap_go(work, cache):
    meta = LOCK['go_bootstrap']
    archive = work / 'downloads' / meta['filename']
    archive.parent.mkdir(exist_ok=True)
    cached = cache / meta['filename'] if cache else None
    if cached and cached.is_file():
        shutil.copyfile(cached, archive)
    else:
        print('Downloading pinned Go bootstrap', flush=True)
        with urllib.request.urlopen('https://go.dev/dl/' + meta['filename'], timeout=120) as response:
            with archive.open('wb') as stream:
                shutil.copyfileobj(response, stream)
    require(archive.stat().st_size == meta['size'], 'Go archive size mismatch')
    require(digest(archive) == meta['sha256'], 'Go archive checksum mismatch')
    dest = work / 'bootstrap'
    dest.mkdir()
    # Only the pinned, checksum-verified official archive reaches tar.
    run(['tar', '-xzf', archive, '-C', dest, '--no-same-owner'])
    require(meta['version'] in capture([dest / 'go/bin/go', 'version']), 'Go version mismatch')
    return dest / 'go'


def parse_config(text):
    return dict(re.findall(r'^(CONFIG_\S+?)=(.*)$', text, re.M))


def verify_config(src):
    require(capture(['git', 'rev-parse', 'HEAD'], src) == LOCK['source']['commit'], 'Source revision mismatch')
    for name, spec in LOCK['feeds'].items():
        require(capture(['git', 'rev-parse', 'HEAD'], src / 'feeds' / name) == spec['commit'],
                'Feed revision mismatch: ' + name)
        require(not capture(['git', 'status', '--porcelain', '--untracked-files=no'], src / 'feeds' / name),
                'Tracked feed files were modified: ' + name)
    cfg = parse_config((src / '.config').read_text())
    required = ['TARGET_qualcommax', 'TARGET_qualcommax_ipq60xx',
                'TARGET_qualcommax_ipq60xx_DEVICE_zn_m2', 'PACKAGE_luci-app-passwall',
                'PACKAGE_luci-app-passwall_INCLUDE_Xray', 'PACKAGE_xray-core',
                'PACKAGE_tailscale', 'PACKAGE_kmod-tun', 'PACKAGE_nginx-ssl',
                'PACKAGE_microsocks', 'PACKAGE_acme-acmesh', 'PACKAGE_acme-acmesh-dnsapi',
                'PACKAGE_firewall4', 'PACKAGE_dnsmasq-full', 'PACKAGE_zram-swap']
    for name in required:
        require(cfg.get('CONFIG_' + name) == 'y', 'Missing required symbol: ' + name)
    forbidden = ['PACKAGE_hysteria', 'PACKAGE_luci-app-passwall_INCLUDE_Hysteria',
                 'PACKAGE_sing-box', 'PACKAGE_lucky', 'PACKAGE_luci-app-lucky',
                 'PACKAGE_minieap', 'PACKAGE_hust-network-login-ipv4', 'PACKAGE_ppp',
                 'PACKAGE_miniupnpd-nftables', 'PACKAGE_luci-app-upnp', 'PACKAGE_ddns-scripts',
                 'PACKAGE_iperf3', 'PACKAGE_kmod-cfg80211', 'PACKAGE_kmod-mac80211', 'CCACHE']
    for name in forbidden:
        require(cfg.get('CONFIG_' + name) != 'y', 'Forbidden image symbol: ' + name)
    for name, value in cfg.items():
        if value == 'y':
            require(not name.startswith(('CONFIG_PACKAGE_kmod-ath', 'CONFIG_PACKAGE_ath11k',
                    'CONFIG_PACKAGE_ipq-wifi', 'CONFIG_PACKAGE_kmod-usb', 'CONFIG_PACKAGE_kmod-nss',
                    'CONFIG_PACKAGE_kmod-qca-nss', 'CONFIG_PACKAGE_wpad', 'CONFIG_PACKAGE_hostapd')),
                    'Unexpected image component: ' + name)
    require(cfg.get('CONFIG_VERSION_NUMBER') == '"' + LOCK['version'] + '"', 'Version mismatch')
    for name, expected in LOCK['expected_packages'].items():
        matches = [p for p in (src / 'feeds').rglob('Makefile') if p.parent.name == name]
        if name == 'luci-app-passwall':
            require(any(expected in p.read_text() for p in matches), 'Passwall version mismatch')
        else:
            require(any(re.search(r'^PKG_VERSION\s*:?=\s*' + re.escape(expected) + r'\s*$',
                                  p.read_text(), re.M) for p in matches), 'Package version mismatch: ' + name)
    ui = src / 'feeds/passwall/luci-app-passwall/luasrc/model/cbi/passwall/client/type/2_xray.lua'
    require('hysteria2' in ui.read_text(), 'Pinned Passwall lacks Xray Hysteria2 support')
    return {'passed': True, 'expanded_config_sha256': digest(src / '.config'),
            'source_commit': LOCK['source']['commit'], 'profile': LOCK['profile'],
            'required_symbols': required, 'expected_packages': LOCK['expected_packages']}


def prepare(work, go_cache, dl_cache):
    require(not work.exists() or not any(work.iterdir()),
            'Use a new empty --work-dir; an incomplete or unrelated directory will not be overwritten')
    work.mkdir(parents=True, exist_ok=True)
    src = work / 'firmware'
    fetch_git(LOCK['source'], src)
    for name, spec in LOCK['feeds'].items():
        fetch_git(spec, src / 'feeds' / name)
    (src / 'feeds.conf').write_text(''.join(
        'src-git {} {}^{}\n'.format(name, spec['url'], spec['commit'])
        for name, spec in LOCK['feeds'].items()))
    for patch in sorted((REPO / 'patches').glob('*.patch')):
        run(['git', 'apply', '--check', patch], src)
        run(['git', 'apply', patch], src)
    go = bootstrap_go(work, go_cache)
    if dl_cache:
        require(dl_cache.is_dir(), '--dl-cache must point to source archives, not build products')
        (src / 'dl').mkdir(exist_ok=True)
        for p in dl_cache.iterdir():
            if p.is_file() and not p.is_symlink() and not p.name.startswith('.'):
                shutil.copyfile(p, src / 'dl' / p.name)
    shutil.copytree(REPO / 'files', src / 'files', dirs_exist_ok=True)
    default = src / 'feeds/passwall/luci-app-passwall/root/usr/share/passwall/0_default_config'
    text = default.read_text()
    marker = "config nodes 'myshunt'\n"
    require(text.count(marker) == 1, 'Unexpected Passwall default layout')
    text = text.split(marker)[0].rstrip() + '\n'
    require("option enabled '0'" in text and "option chn_list 'direct'" in text,
            'Unexpected Passwall routing defaults')
    require('geosite:' not in text and 'geoip:' not in text, 'Unexpected Geo database dependency')
    target = src / 'files/usr/share/passwall/0_default_config'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    for name in LOCK['feeds']:
        run(['./scripts/feeds', 'update', '-i', name], src)
    run(['./scripts/feeds', 'install', '-a'], src)
    preferred = ['xray-core', 'chinadns-ng', 'dns2socks', 'ipt2socks', 'microsocks', 'tcping']
    run(['./scripts/feeds', 'uninstall', 'luci-app-passwall', *preferred, 'squeezelite'], src)
    run(['./scripts/feeds', 'install', '-p', 'passwall_packages', *preferred], src)
    run(['./scripts/feeds', 'install', '-p', 'passwall', 'luci-app-passwall'], src)
    seed = (REPO / 'configs/zn-m2-wired.config').read_text()
    seed += 'CONFIG_GOLANG_EXTERNAL_BOOTSTRAP_ROOT="' + str(go) + '"\n'
    (src / '.config').write_text(seed)
    run(['make', 'defconfig'], src)
    report = verify_config(src)
    (work / 'config-check.json').write_text(json.dumps(report, indent=2) + '\n')
    stamp = {'recipe_sha256': recipe_digest(), 'config_sha256': digest(src / '.config'),
             'overlay_sha256': overlay_digest(src / 'files'),
             'source_diff_sha256': hashlib.sha256(capture(['git', 'diff', '--no-ext-diff'], src).encode()).hexdigest()}
    (work / '.znm2-prepared.json').write_text(json.dumps(stamp, indent=2) + '\n')
    return src


def reuse_prepared(work):
    stamp = json.loads((work / '.znm2-prepared.json').read_text())
    require(stamp['recipe_sha256'] == recipe_digest(), 'Recipe changed; use a new work directory')
    src = work / 'firmware'
    require(stamp['config_sha256'] == digest(src / '.config'), 'Expanded config changed since preparation')
    require(stamp['overlay_sha256'] == overlay_digest(src / 'files'), 'Image overlay changed since preparation')
    diff = hashlib.sha256(capture(['git', 'diff', '--no-ext-diff'], src).encode()).hexdigest()
    require(stamp['source_diff_sha256'] == diff, 'Source changes differ from the prepared recipe')
    verify_config(src)
    return src


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work-dir', type=Path, default=REPO / 'build')
    p.add_argument('--prepare-only', action='store_true', help='Fetch, patch, configure and validate; do not compile')
    p.add_argument('--jobs', type=int, default=min(os.cpu_count() or 2, 16))
    p.add_argument('--go-cache', type=Path, help='Optional directory containing the pinned official bootstrap archive')
    p.add_argument('--dl-cache', type=Path, help='Optional read-only source archive cache; copied, never linked')
    a = p.parse_args()
    require(os.geteuid() != 0, 'Run as a normal user, not root')
    require(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'This profile requires Linux x86_64')
    require(a.jobs > 0, '--jobs must be positive')
    work = a.work_dir.expanduser().resolve()
    require(not re.search(r'\s', str(work)), 'OpenWrt build path must not contain whitespace')
    require(work != REPO and REPO not in work.parents or work == REPO / 'build',
            'Use the default build/ or a separate work directory')
    require(work not in REPO.parents, 'Work directory cannot contain this repository')
    os.environ.update(LC_ALL='C.UTF-8', TZ='UTC', GOMAXPROCS=str(min(a.jobs, 6)))
    marker = work / '.znm2-prepared.json'
    src = reuse_prepared(work) if marker.exists() else prepare(
        work, a.go_cache.expanduser().resolve() if a.go_cache else None,
        a.dl_cache.expanduser().resolve() if a.dl_cache else None)
    print('Configuration verified:', work / 'config-check.json', flush=True)
    if a.prepare_only:
        return
    require(shutil.disk_usage(work).free >= 30 * 1024**3,
            'Full build requires at least 30 GiB free; move to a larger work filesystem')
    run(['make', '-j' + str(a.jobs), 'download', 'V=s'], src)
    run(['make', '-j' + str(a.jobs), 'V=s'], src)
    output = work / 'verification'
    run([sys.executable, REPO / 'scripts/verify-image.py', '--source', src, '--report', output])
    print('Images:', src / 'bin/targets/qualcommax/ipq60xx')
    print('Static verification:', output / 'result.json')
    print('No device has been flashed. Runtime validation is a separate step.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))
