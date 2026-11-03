# ZN-M2 Wired

面向 **ZN-M2 / 256 MiB RAM / 纯有线网关**的 ImmortalWrt 构建配方。仓库提供固定版本的源码入口、精简配置、板级补丁、镜像检查工具和可选服务示例。

用途是少量服务器的软件更新、API 访问、透明代理、HTTPS 反代及远程管理。构建基于 [VIKINGYFY/immortalwrt](https://github.com/VIKINGYFY/immortalwrt)，应用来自 ImmortalWrt 和 Openwrt-Passwall feeds；具体提交与下载哈希见 [sources.lock.json](sources.lock.json)。

**当前状态：源码整理版 `0.1.0-dev`。** 本仓库的公开配置与此前实机验证的内部基线有差异，不能把内部基线的测试结果直接当作本版镜像已验收。当前验证范围见 [docs/VALIDATION.md](docs/VALIDATION.md)。本仓库不包含预编译固件、代理节点、账号、证书私钥或任何 Tailscale 设备身份，也不会自动刷机。

## 功能与取舍

| 项目 | 配置 |
| --- | --- |
| 目标 | `qualcommax/ipq60xx`，设备 `zn_m2`，DT compatible `zn,m2` |
| 管理与基础网络 | LuCI、SSH、firewall4、dnsmasq-full、DHCP |
| 透明代理 | Passwall + 单 Xray；固定版本支持 VLESS、Hysteria2 |
| 附加服务 | Tailscale、Nginx TLS/反代、microsocks、acme.sh DNS API |
| 内存策略 | 小容量 RAM 日志、DNS 缓存 1000、单个代理核心、64 MiB zram 上限 |
| 板级策略 | 纯有线 DT 布局，关闭 WLAN remoteproc，回收不用的 16 MiB NSS 保留区，CPU 最高 1.2 GHz |
| 未提供 | Wi-Fi、NSS 加速、USB/PCI/MMC/SCSI 相关扩展、PPPoE、Lucky、独立 Hysteria/sing-box、校园认证客户端、UPnP、DDNS |

zram 是使用实际 RAM 保存压缩页的交换区，不是额外获得 64 MiB 物理内存。这里的内存策略针对本板型和轻并发负载，不承诺任意业务规模、所有协议组合或千兆加密吞吐。

**需要无线、USB 或 PPPoE 的用户不适合此配置。** 本配方只验证指定设备；补丁会修改共享 target 默认值，不应将同一构建树用于其他板型。首次从原厂系统刷入、不同引导程序/分区布局的兼容性不在当前验证范围内。

## 构建环境

使用 Linux x86_64、Python 3.10+、普通用户。建议至少 16 GiB RAM、60 GiB 可用构建空间；并行度按资源降低。工作目录不能包含空白字符。完整构建入口会在编译前检查至少 30 GiB 空闲空间，这只是最低门槛，不代表所有环境都够用。

Ubuntu 22.04 / 24.04 的依赖示例：

```sh
sudo apt update
sudo apt install -y build-essential clang flex bison g++ gawk gettext git \
  libncurses-dev libssl-dev libelf-dev zlib1g-dev python3 python3-setuptools \
  rsync swig unzip file wget curl ca-certificates patch perl xz-utils zstd
```

还需要访问锁定的 GitHub 仓库、Go 下载站及软件包源码站。不要以 root 运行构建脚本。脚本不会读取桌面密钥环、私人代理订阅、SSH 配置或任何路由器备份。

## 获取与检查仓库

将下方占位符替换成你发布此仓库后的 URL：

```sh
git clone <仓库URL> znm2-wired
cd znm2-wired
python3 tests/check_repository.py
```

离线检查涵盖语法、固定源码提交、配置约束及有限敏感信息模式；不等于完整的许可证审计或 secrets 扫描。

## 准备源码和配置

```sh
python3 scripts/build.py --work-dir /path/to/znm2-build --prepare-only
```

脚本会：

1. 从公开上游获取完整 commit 指定的主源码和四个 feeds，检出 detached HEAD。
2. 检查并应用 `patches/` 中的补丁。
3. 下载并校验固定 SHA256 的 Go bootstrap。
4. 安装选定的 feeds 和无身份的默认文件，移除依赖未提供 Geo 数据库的 Passwall 示例节点。
5. 执行 `make defconfig` 并检查最终依赖展开，输出 `config-check.json`。

首次使用必须提供空工作目录。脚本不覆盖已有构建；已成功准备的同一目录可继续编译。配方或准备后的配置改变时，应换一个新的工作目录，避免把不同版本混在一起。

可选缓存只用于减少下载，不是必须依赖：

```sh
python3 scripts/build.py --work-dir /path/to/znm2-build --prepare-only \
  --go-cache /path/to/public-bootstrap-downloads \
  --dl-cache /path/to/openwrt-source-archives
```

`--go-cache` 中的文件仍必须通过大小和 SHA256 校验；`--dl-cache` 只复制源码归档，软件包下载由上游构建系统校验。不要把旧工具链、`build_dir`、`staging_dir` 或私人配置作为缓存输入。

## 编译和检查镜像

```sh
python3 scripts/build.py --work-dir /path/to/znm2-build --jobs 8
```

首次调用也可以直接编译，准备阶段会自动完成。输出在：

```text
/path/to/znm2-build/firmware/bin/targets/qualcommax/ipq60xx/
/path/to/znm2-build/verification/result.json
```

检查包括软件包/版本、内核裁剪、DT 保留区与 CPU/端口定义、固件格式与哈希、AArch64 可执行文件、无设备身份的默认状态。检查成功仅表示静态合同通过，仍需实机联网与恢复验证。

构建可重复使用固定输入，但本项目尚不承诺不同机器产生逐字节相同的镜像。修改配方、工具链或默认配置后，应使用新版本号与新的测试记录。不要在这个自定义内核上盲目安装滚动快照的 kmod，内核 ABI 可能不匹配；优先重新构建一致的软件包/镜像。

## 刷机和首次访问

脚本不执行 SSH 或刷机。先阅读 [docs/INSTALL.md](docs/INSTALL.md)，确认板型、引导程序、分区布局、备份及恢复方式，并保留可靠有线管理通道。

新配置的默认状态：

- LAN：`192.168.8.1/24`，WAN：DHCP，不克隆 MAC。
- 默认主机名 `ZN-M2-Wired`，时区 `Asia/Shanghai`。
- Passwall、Tailscale、Nginx、ACME 默认禁用，未配置个人密码或节点。
- WAN 不默认开放网页管理、SSH 或 SOCKS；首先从受信任 LAN 设置 root 密码。
- 只读镜像没有 Tailscale 身份；每台设备必须自行授权。
- 默认包含 WAN DNS 前置保护和 Tailscale 自身流量的 Passwall 旁路规则。

用有线客户端访问 `http://192.168.8.1/` 完成基础设置。若上游也使用该网段，先修改 LAN 避免重叠。防护规则假定此板型的物理 WAN 设备名为 `wan`；更改拓扑时应重新检查。

## 配置可选服务

详细步骤和清理方式在 [docs/SERVICES.md](docs/SERVICES.md)。

- **Passwall**：在 LuCI 中添加自己的 Xray 节点，选择 VLESS 或 Hysteria2，检查 DNS/分流后启用。无需额外 Hysteria2 核心。
- **Tailscale**：启用服务后运行 `tailscale up --accept-dns=false --accept-routes=false --hostname=znm2-wired`，自行完成授权。默认不发布子网路由、不做出口节点、不启用 Tailscale SSH。
- **HTTPS 反代**：修改 `examples/nginx/`，自行安装域名证书，先运行 `nginx -t`，再启用服务。示例地址使用文档专用地址，不能不修改就投入使用。
- **SOCKS**：`examples/microsocks/` 提供默认停用、仅绑定回环的可选服务。对外开放和认证策略由使用者明确设计。
- **端口转发**：在 LuCI 添加指定目标/端口；`examples/firewall/` 说明配置字段。不自动导入整个防火墙文件。
- **证书续期**：已包含 acme.sh 和 DNS API；凭据只放在设备私密配置中，续期成功后验证证书并重载 Nginx。不要提交凭据或私钥。

## 项目目录

```text
sources.lock.json        上游 URL、commit、Go bootstrap 哈希
configs/                 单一纯有线 profile
patches/                 可审查的板级/裁剪补丁
files/                   无身份的首次启动与 nftables 文件
scripts/                 获取、构建与静态镜像验证
examples/                可选服务示例，不会自动打包启用
tests/                   离线仓库检查
docs/                    安装、服务、测试边界与发布说明
```

## 许可证与发布

本项目新增脚本和配置采用 **GPL-2.0-only**；修改的上游文件保留原许可，部分设备树文件原为双许可。第三方软件不因本仓库的 LICENSE 而改变许可。见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

源码仓库不包含完整第三方源码或二进制。若发布固件 Release，应同时处理对应源码、许可通知、构建配方、校验和与测试结果，具体检查见 [docs/RELEASING.md](docs/RELEASING.md)。
