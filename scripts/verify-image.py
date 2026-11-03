#!/usr/bin/env python3
"""Inspect the shipped image, not just the build configuration. Never flashes."""
import argparse
# SPDX-License-Identifier: GPL-2.0-only
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--source', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
args = p.parse_args()
base = Path(__file__).resolve().parents[1]
src = args.source
out = src/'bin/targets/qualcommax/ipq60xx'
report = args.report
report.mkdir(parents=True, exist_ok=True)
profiles = json.loads((out/'profiles.json').read_text())
profile = profiles['profiles']['zn_m2']
assert 'zn,m2' in profile['supported_devices']
manifests = list(out.glob('*.manifest'))
assert len(manifests) == 1, manifests
manifest = manifests[0].read_text()
packages = {line.split()[0] for line in manifest.splitlines() if line.strip()}
versions = dict(line.split(' - ', 1) for line in manifest.splitlines() if ' - ' in line)
for name, expected in [('xray-core','26.10.21'),('tailscale','1.104.1'),('luci-app-passwall','26.10.22')]:
    assert re.match(re.escape(expected)+r'(?:[-~]|$)',versions[name]), (name,versions.get(name))
required = {'luci-app-passwall','tailscale','xray-core','microsocks','nginx-ssl',
            'acme-acmesh','acme-acmesh-dnsapi','openssl-util','zram-swap','firewall4',
            'kmod-dsa','kmod-phy-qca83xx','dropbear','dnsmasq-full','kmod-tun'}
assert not required-packages, required-packages
for name in packages:
    assert name not in {'hysteria','lucky','luci-app-lucky','sing-box','hust-network-login-ipv4','minieap','ppp','iw','iwinfo','wireless-regdb','wifi-scripts','kmod-cfg80211','kmod-mac80211'}, name
    assert not name.startswith(('kmod-ath','ath11k','wpad','hostapd','ipq-wifi','kmod-usb','kmod-nss','kmod-qca-nss')), name
kconfigs = list((src/'build_dir').glob('target-*/linux-qualcommax_ipq60xx/linux-*/.config'))
assert len(kconfigs) == 1
kernel = kconfigs[0].read_text()
for symbol in ['USB','USB_SUPPORT','PCI','MMC','SCSI','QCOM_Q6V5_WCSS','QCOM_Q6V5_WCSS_SEC','QCOM_Q6V5_MPD','QCOM_Q6V5_COMMON','QCOM_RPROC_COMMON']:
    assert not re.search(rf'^CONFIG_{symbol}=[ym]$', kernel, re.M), symbol
for symbol in ['QCOM_EDMA','QCOM_80211AX_PPE','MTD','MTD_UBI','SQUASHFS','ARM64','SMP']:
    assert f'CONFIG_{symbol}=y\n' in kernel, symbol
dtbs = list((src/'build_dir').glob('target-*/linux-qualcommax_ipq60xx/image-ipq6000-m2.dtb'))
assert len(dtbs) == 1
dtc = kconfigs[0].parent/'scripts/dtc/dtc'
dts = subprocess.check_output([str(dtc),'-q','-I','dtb','-O','dts',str(dtbs[0])], text=True)
assert 'compatible = "zn,m2", "qcom,ipq6018";' in dts
def node(text, name):
    match = re.search(r'(?m)^\s*'+re.escape(name)+r'\s*\{', text)
    assert match, name
    depth = 1
    for i in range(match.end(), len(text)):
        depth += (text[i]=='{')-(text[i]=='}')
        if not depth:
            return text[match.end():i]
    raise AssertionError(name)
for name in ['wifi@c000000','remoteproc@cd00000']:
    assert 'status = "disabled";' in node(dts, name), name
assert 'nss@40000000 {' not in dts
for name, address, size in [('q6@4ab00000',0x4ab00000,0x1000000),
                            ('q6_etr@4eb00000',0x4bb00000,0x100000),
                            ('m3_dump@4ec00000',0x4bc00000,0x100000),
                            ('ramoops@4ed00000',0x4bd00000,0x100000)]:
    # Upstream nowifi overrides the reg property but retains the node's name.
    body = node(dts,name)
    values = [int(s,0) for s in re.search(r'reg = <([^>]+)>;',body)[1].split()]
    assert values == [0,address,0,size], (name,values)
cpu = node(dts,'opp-table-cpu')
frequencies = [int(f) for f in re.findall(r'\bopp-(\d+)\s*\{',cpu) if 'status = "disabled";' not in node(cpu,'opp-'+f)]
assert max(frequencies) == 1200000000
for port in ['wan','lan1','lan2','lan3']:
    assert f'label = "{port}";' in dts
images = []
for item in profile['images']:
    path = out/item['name']
    content = path.read_bytes()
    assert len(content) < 95*1024**2
    if path.suffix == '.ubi':
        assert content[:4] == b'UBI#' and struct.unpack_from('>II',content,16) == (2048,4096)
        assert len(content) % 131072 == 0
    digest = hashlib.sha256(content).hexdigest()
    assert digest == item['sha256']
    images.append({'name':path.name,'bytes':len(content),'sha256':digest})
sysupgrade = next(out/i['name'] for i in profile['images'] if 'sysupgrade' in i['name'])
with tempfile.TemporaryDirectory(prefix='znm2-image-check-',dir='/tmp') as temp:
    temp = Path(temp)
    with tarfile.open(sysupgrade) as archive:
        root_member = [m for m in archive.getmembers() if m.name.endswith('/root')]
        kernel_member = [m for m in archive.getmembers() if m.name.endswith('/kernel')]
        assert len(root_member) == len(kernel_member) == 1
        root_image = archive.extractfile(root_member[0]).read()
        assert root_image[:4] == b'hsqs'
        (temp/'root.squashfs').write_bytes(root_image)
        (temp/'kernel.itb').write_bytes(archive.extractfile(kernel_member[0]).read())
    dumpimage = list((src/'build_dir/host').glob('u-boot-*/tools/dumpimage'))
    assert len(dumpimage) == 1
    fit = subprocess.check_output([str(dumpimage[0]),'-l',str(temp/'kernel.itb')],text=True)
    assert all(x in fit for x in ['config@cp03-c1','AArch64','0x41000000'])
    for index,name in [(0,'kernel.gz'),(1,'board.dtb')]:
        subprocess.run([str(dumpimage[0]),'-T','flat_dt','-p',str(index),'-o',str(temp/name),str(temp/'kernel.itb')],check=True,stdout=subprocess.DEVNULL)
        assert hashlib.sha1((temp/name).read_bytes()).hexdigest() in fit
    assert (temp/'board.dtb').read_bytes() == dtbs[0].read_bytes()
    kernel_payload = gzip.decompress((temp/'kernel.gz').read_bytes())
    assert kernel_payload[0x38:0x3c] == b'ARM\x64'
    component_sha256 = {
        'kernel_uncompressed': hashlib.sha256(kernel_payload).hexdigest(),
        'kernel_compressed': hashlib.sha256((temp/'kernel.gz').read_bytes()).hexdigest(),
        'board_dtb': hashlib.sha256((temp/'board.dtb').read_bytes()).hexdigest(),
        'rootfs_squashfs': hashlib.sha256(root_image).hexdigest(),
    }
    with (report/'unsquashfs.log').open('w') as log:
        subprocess.run([str(src/'staging_dir/host/bin/unsquashfs4'),'-no-progress','-d',str(temp/'rootfs'),'-excludes',str(temp/'root.squashfs'),'dev/console'],check=True,stdout=log,stderr=subprocess.STDOUT)
    fs = temp/'rootfs'
    for name in ['usr/bin/xray','usr/sbin/tailscale','usr/sbin/tailscaled','usr/bin/microsocks','usr/sbin/nginx']:
        executable = fs/name
        assert executable.is_file(), name
        data = executable.read_bytes()
        header = struct.unpack_from('<16sHHIQQQIHHHHHH',data)
        assert data[:6] == b'\x7fELF\x02\x01' and header[2] == 183, name
        assert header[9] == 56 and header[10] > 0, name
        for i in range(header[10]):
            segment = struct.unpack_from('<IIQQQQQQ',data,header[5]+i*header[9])
            assert segment[2]+segment[5] <= len(data), (name,'truncated program segment')
            if segment[0] == 1:
                assert segment[5] <= segment[6], (name,'invalid PT_LOAD size')
        if header[6] == 0:
            # OpenWrt sstrip intentionally removes the entire section table.
            # Older readelf -S misreads this as ELF extended section numbering.
            assert header[12] == header[13] == 0, name
        else:
            assert header[6]+header[11]*header[12] <= len(data), name
            assert '.debug_info' not in subprocess.check_output(['readelf','-S',str(executable)],text=True)
    for name in ['usr/bin/hysteria','usr/bin/sing-box','etc/tailscale/tailscaled.state','usr/bin/hust-network-login','etc/hust-network-login.conf','etc/config/wireless','etc/znm2-wired/configured']:
        assert not (fs/name).exists(), name
    assert not list((fs/'lib/modules').glob('**/*ath11k*'))
    assert not list((fs/'lib/firmware').glob('**/*q6*'))
    assert not list((fs/'etc/dropbear').glob('*host_key'))
    shadow = (fs/'etc/shadow').read_text()
    root = [line.split(':') for line in shadow.splitlines() if line.startswith('root:')]
    assert len(root) == 1 and root[0][1] in {'','*','!','!!'}
    first_boot = (fs/'etc/uci-defaults/zz-znm2-wired').read_text()
    assert "set network.lan.netmask='255.255.255.0'" in first_boot
    assert "set network.wan.proto='dhcp'" in first_boot
    assert '[ ! -e /etc/znm2-wired/configured ] || exit 0' in first_boot
    assert 'geosite:' not in (fs/'usr/share/passwall/0_default_config').read_text()
    assert (fs/'etc/nftables.d/30-znm2-tailscale.nft').is_file()
    assert (fs/'etc/nftables.d/20-znm2-wan-dns-guard.nft').is_file()
    assert 'hysteria2' in (fs/'usr/lib/lua/luci/model/cbi/passwall/client/type/2_xray.lua').read_text()
    assert 'hysteria2' in (fs/'usr/lib/lua/luci/passwall/util_xray.lua').read_text()
    filesystem = []
    for path in sorted(fs.rglob('*')):
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            filesystem.append({'path':str(path.relative_to(fs)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    (report/'rootfs-manifest.json').write_text(json.dumps(filesystem,indent=2)+'\n')
    (report/'fit-check.txt').write_text(fit)
(report/'resolved-device-tree.dts').write_text(dts)
(report/'kernel.config').write_text(kernel)
(report/'packages.manifest').write_text(manifest)
result = {'static_checks_passed':True,'runtime_tested':False,'profile':'zn-m2-wired-256m',
          'wireless':False,'wcss_remoteproc':False,'nss_acceleration':False,
          'nss_reserved_mib':0,
          'max_cpu_hz':max(frequencies),'images':images,'packages':len(packages),
          'component_sha256':component_sha256,
          'application_versions':{n:versions[n] for n in ['xray-core','tailscale','luci-app-passwall']}}
(report/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
