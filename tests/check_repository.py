#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Offline checks for an export, not a replacement for a dedicated secret scan."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
errors = []
required = ['README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'sources.lock.json',
            'configs/zn-m2-wired.config', 'scripts/build.py', 'scripts/verify-image.py',
            'files/etc/uci-defaults/zz-znm2-wired', 'docs/VALIDATION.md']
for name in required:
    if not (ROOT / name).is_file():
        errors.append('Missing ' + name)
skip = {'.git', '__pycache__', 'build', 'output', 'work', 'private'}
if (ROOT / '.git').exists():
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    for name in filter(None, tracked):
        p = Path(name)
        if any(x in skip for x in p.parts) or p.suffix in {'.pem', '.key', '.state', '.bin', '.ubi', '.ipk', '.apk', '.zip'}:
            errors.append('Forbidden tracked artifact: ' + name)
    candidates = subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    paths = [ROOT / name for name in dict.fromkeys(filter(None, candidates))]
else:
    paths = [p for p in ROOT.rglob('*') if p.is_file() and not any(x in skip for x in p.relative_to(ROOT).parts)]
for path in paths:
    rel = str(path.relative_to(ROOT))
    if path.is_symlink():
        errors.append('Unexpected symlink: ' + rel)
        continue
    if not path.is_file():
        errors.append('Missing source file: ' + rel)
        continue
    if path.stat().st_size > 2 * 1024**2:
        errors.append('Unexpected large source file: ' + rel)
        continue
    raw = path.read_bytes()
    if b'\0' in raw:
        errors.append('Unexpected binary in source export: ' + rel)
        continue
    text = raw.decode('utf-8')
    if path.suffix == '.py':
        ast.parse(text, filename=rel)
    if path.suffix == '.json':
        json.loads(text)
    if text.startswith('#!/bin/sh'):
        subprocess.run(['sh', '-n', str(path)], check=True)
    # Report paths only: never echo an accidentally introduced credential.
    for pattern in [r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                    r'https://api\.day\.app/[A-Za-z0-9]{10,}',
                    r'https://login\.tailscale\.com/a/[A-Za-z0-9]+',
                    r'(?:vless|vmess|hysteria2|trojan)://[^\s<>"\x27]{12,}',
                    r'/home/[A-Za-z0-9_-]+/']:
        if re.search(pattern, text):
            errors.append('Potential private value: ' + rel)
lock = json.loads((ROOT / 'sources.lock.json').read_text())
for spec in [lock['source'], *lock['feeds'].values()]:
    if not re.fullmatch('[0-9a-f]{40}', spec['commit']) or not spec['url'].startswith('https://'):
        errors.append('Invalid public source lock')
if not re.fullmatch('[0-9a-f]{64}', lock['go_bootstrap']['sha256']):
    errors.append('Invalid bootstrap checksum')
spec = importlib.util.spec_from_file_location('builder', ROOT / 'scripts/build.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
cfg = module.parse_config((ROOT / 'configs/zn-m2-wired.config').read_text())
for key in ['PACKAGE_xray-core', 'PACKAGE_tailscale', 'PACKAGE_nginx-ssl', 'TARGET_qualcommax_ipq60xx_DEVICE_zn_m2']:
    if cfg.get('CONFIG_' + key) != 'y':
        errors.append('Missing seed component: ' + key)
for key in ['PACKAGE_hysteria', 'PACKAGE_sing-box', 'PACKAGE_lucky', 'PACKAGE_ppp', 'CCACHE']:
    if cfg.get('CONFIG_' + key) == 'y':
        errors.append('Unexpected seed component: ' + key)
defaults = (ROOT / 'files/etc/uci-defaults/zz-znm2-wired').read_text()
if "set network.wan.proto='dhcp'" not in defaults or 'macaddr=' in defaults:
    errors.append('Public default must use DHCP without a cloned MAC')
if '/etc/znm2-wired/configured' not in (ROOT / 'files/etc/sysupgrade.conf').read_text():
    errors.append('Upgrade guard not preserved')
if errors:
    print('\n'.join(sorted(set(errors))), file=sys.stderr)
    sys.exit(1)
print(json.dumps({'passed': True, 'source_files_checked': len(paths),
                  'scope': 'syntax, source lock, default contract and limited privacy patterns'}, indent=2))
