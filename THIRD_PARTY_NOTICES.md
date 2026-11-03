# Third-party provenance and licenses

New standalone project scripts, configuration and documentation are supplied under GPL-2.0-only. This does not relicense upstream software. Preserve the copyright and license notices attached to each upstream file when redistributing or modifying it.

| Source | Role | Pinned revision |
| --- | --- | --- |
| [VIKINGYFY/immortalwrt](https://github.com/VIKINGYFY/immortalwrt) | Build system, target and kernel integration | `sources.lock.json: source` |
| [immortalwrt/packages](https://github.com/immortalwrt/packages) | Application packages | `sources.lock.json: feeds.packages` |
| [immortalwrt/luci](https://github.com/immortalwrt/luci) | Web management | `sources.lock.json: feeds.luci` |
| [Openwrt-Passwall/openwrt-passwall](https://github.com/Openwrt-Passwall/openwrt-passwall) | Passwall UI and integration | `sources.lock.json: feeds.passwall` |
| [Openwrt-Passwall/openwrt-passwall-packages](https://github.com/Openwrt-Passwall/openwrt-passwall-packages) | Proxy package recipes | `sources.lock.json: feeds.passwall_packages` |
| [Go](https://go.dev/) | Host bootstrap compiler | Version and checksum in `sources.lock.json` |

The pinned ImmortalWrt tree declares GPL-2.0-only in its [COPYING](https://github.com/VIKINGYFY/immortalwrt/blob/4bec1cbf12d144f538b5e88102bee542fd089920/COPYING), with additional licenses applying to other files. Device-tree files touched by the patch include `GPL-2.0-or-later OR MIT` headers; the patch preserves those headers. The GPL text in this repository is copied from the upstream `LICENSES/GPL-2.0` file.

Core application declarations checked against the pinned source/package metadata:

| Component | Version | Declared license |
| --- | --- | --- |
| Xray | 26.10.21-r1 | MPL-2.0 |
| Tailscale | 1.104.1-r1 | BSD-3-Clause |
| Nginx SSL | 1.30.5-r1 | BSD-2-Clause |
| microsocks | 1.0.5-r2 | MIT |
| acme.sh | 3.1.4-r1 | GPL-3.0-only |
| Passwall | 26.10.22-r2 | GNU GPL v3, as stated in the source header and repository LICENSE |

This table covers core applications, not all packages or their bundled dependencies. It records declarations and does not replace reviewing the actual source notices for a binary release.

The build fetches and combines many separately licensed packages. A package manifest is not a complete license bill of materials. Before distributing firmware or individual compiled packages, review their actual pinned source licenses, preserve required notices, and supply complete corresponding source where required. Merely pointing to the current upstream branch or shipping only this patch repository is not a replacement for those obligations.

The public recipe was derived from a private R8 integration and validation effort. No personal configuration, device identity, certificate private key, subscription or raw operational log is part of this repository. Historical test claims are scoped in `docs/VALIDATION.md`.
