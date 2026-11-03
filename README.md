# ZN-M2 Wired

为 **256 MiB 内存的 ZN-M2 路由器**制作精简的纯有线 ImmortalWrt 固件，适合通过交换机连接电脑或服务器，提供路由、透明代理、HTTPS 反向代理和远程访问。

项目以轻并发使用为目标，通过去除无线及不需要的驱动、使用单个代理核心，为常用服务留出内存。仓库包含构建脚本、固定版本的源码配置、补丁和使用示例；目前需要自行编译。

构建基于 [VIKINGYFY/immortalwrt](https://github.com/VIKINGYFY/immortalwrt)，应用来自 ImmortalWrt 和 Openwrt-Passwall 软件源。具体提交与下载哈希见 [sources.lock.json](sources.lock.json)。

**当前版本 `0.1.0-dev` 已完成完整编译和镜像静态检查，尚未完成该版本的实机验收。** 具体结果和待验证项目见 [验证说明](docs/VALIDATION.md)。

## 功能与取舍

| 项目 | 配置 |
| --- | --- |
| 支持设备 | ZN-M2；构建目标 `qualcommax/ipq60xx`，设备 `zn_m2` |
| 管理与基础网络 | LuCI、SSH、firewall4、dnsmasq-full、DHCP |
| 透明代理 | Passwall + Xray，支持 VLESS、Hysteria2，两种协议共用一个核心 |
| 远程访问 | Tailscale 组网、microsocks SOCKS5 代理 |
| 网站服务 | Nginx HTTPS/反向代理、acme.sh 证书申请与续期工具 |
| 内存策略 | 小容量 RAM 日志、DNS 缓存 1000、单个代理核心、64 MiB zram 上限 |
| 硬件裁剪 | 关闭无线子系统和 NSS 加速，回收不用的 16 MiB NSS 保留内存；CPU 最高 1.2 GHz |
| 未包含的常见功能 | Wi-Fi、USB 扩展、PPPoE 拨号、UPnP、DDNS |

上述应用已包含在构建配置中，需要自行配置后启用。实际内存占用取决于连接数、代理规则和流量；项目不承诺千兆加密代理吞吐。zram 使用 RAM 保存压缩页，64 MiB 是交换区容量上限，不代表增加了同等物理内存。

**当前配置不适用于需要无线、USB 或 PPPoE 拨号的用途。** 补丁针对 ZN-M2，并会修改共享的构建目标默认值，请为其他设备使用独立构建目录。首次从原厂系统刷入、不同引导程序或分区布局的兼容性尚未验证。

## 构建环境

使用 Linux x86_64、Python 3.10+、普通用户。建议至少 16 GiB RAM、60 GiB 可用构建空间；并行度按资源降低。工作目录不能包含空白字符。完整构建入口会在编译前检查至少 30 GiB 空闲空间，这只是最低门槛，不代表所有环境都够用。

Ubuntu 22.04 / 24.04 的依赖示例：

```sh
sudo apt update
sudo apt install -y build-essential clang flex bison g++ gawk gettext git \
  libncurses-dev libssl-dev libelf-dev zlib1g-dev python3 python3-setuptools \
  rsync swig unzip file wget curl ca-certificates patch perl xz-utils zstd
```

构建时需要访问 GitHub、Go 下载站及软件包源码站。请使用普通用户运行构建脚本。

## 获取与检查仓库

将 `<仓库URL>` 替换为当前仓库的 Git 克隆地址：

```sh
git clone <仓库URL> znm2-wired
cd znm2-wired
python3 tests/check_repository.py
```

这一步检查脚本语法、源码版本、配置约束和部分敏感信息模式，不需要编译固件。

## 准备源码和配置

```sh
python3 scripts/build.py --work-dir /path/to/znm2-build --prepare-only
```

脚本会：

1. 按锁定的提交获取主源码和四个软件源（feeds）。
2. 检查并应用 `patches/` 中的补丁。
3. 下载并校验固定 SHA256 的 Go bootstrap。
4. 安装选定的软件包定义和默认配置，移除缺少 Geo 数据库依赖的 Passwall 示例节点。
5. 执行 `make defconfig` 并检查最终依赖展开，输出 `config-check.json`。

首次使用必须提供空工作目录。脚本不覆盖已有构建；已成功准备的同一目录可继续编译。配方或准备后的配置改变时，应换一个新的工作目录，避免把不同版本混在一起。

可选缓存只用于减少下载，不是必须依赖：

```sh
python3 scripts/build.py --work-dir /path/to/znm2-build --prepare-only \
  --go-cache /path/to/public-bootstrap-downloads \
  --dl-cache /path/to/openwrt-source-archives
```

`--go-cache` 中的文件仍必须通过大小和 SHA256 校验；`--dl-cache` 只复制源码归档，软件包下载由上游构建系统校验。缓存参数不用于复用旧工具链或编译中间文件。

## 编译和检查镜像

```sh
python3 scripts/build.py --work-dir /path/to/znm2-build --jobs 8
```

首次调用也可以直接编译，准备阶段会自动完成。输出在：

```text
/path/to/znm2-build/firmware/bin/targets/qualcommax/ipq60xx/
/path/to/znm2-build/verification/result.json
```

编译完成后会自动检查软件包版本、内核配置、设备树的内存与端口定义、镜像格式及默认配置。静态检查通过后，仍需在实际设备上验证联网、服务运行和重启恢复。

本项目固定源码和配置版本，但尚不保证不同机器生成逐字节相同的镜像。修改配置或工具链后，需要重新记录验证结果。安装额外内核模块（kmod）时应使用同次构建的匹配软件包，其他快照软件源中的模块可能与本固件内核不兼容。

## 刷机和首次访问

刷机前请阅读 [安装说明](docs/INSTALL.md)，确认板型、引导程序、分区布局、备份及恢复方式，并保留可靠的有线管理连接。构建脚本只生成镜像，刷机需要手动执行。

全新安装后的默认配置：

- LAN：`192.168.8.1/24`，WAN：通过 DHCP 自动获取地址，使用设备原有 MAC。
- 默认主机名 `ZN-M2-Wired`，时区 `Asia/Shanghai`。
- Passwall、Tailscale、Nginx、ACME 默认禁用，配置完成后按需启用。
- WAN 不默认开放网页管理、SSH 或 SOCKS；首先从受信任 LAN 设置 root 密码。
- 使用 Tailscale 时需要登录自己的账号并授权设备。
- 阻止从 WAN 访问路由器的 DNS 服务；路由器自身的 Tailscale 流量绕过 Passwall。

用有线客户端访问 `http://192.168.8.1/` 完成基础设置。若上游也使用该网段，先修改 LAN 避免重叠。防护规则假定此板型的物理 WAN 设备名为 `wan`；更改拓扑时应重新检查。

## 配置可选服务

详细步骤和清理方式在 [docs/SERVICES.md](docs/SERVICES.md)。

- **Passwall**：在 LuCI 中添加自己的 Xray 节点，选择 VLESS 或 Hysteria2，检查 DNS/分流后启用。无需额外 Hysteria2 核心。
- **Tailscale**：启用服务后运行 `tailscale up --accept-dns=false --accept-routes=false --hostname=znm2-wired`，自行完成授权。默认不发布子网路由、不做出口节点、不启用 Tailscale SSH。
- **HTTPS 反代**：修改 `examples/nginx/`，自行安装域名证书，按服务文档关闭 UCI 配置生成并检查手写配置，再启用服务。示例地址使用文档专用地址，不能不修改就投入使用。
- **SOCKS**：`examples/microsocks/` 提供默认停用、仅绑定回环的可选服务。对外开放和认证策略由使用者明确设计。
- **端口转发**：在 LuCI 添加指定目标/端口；`examples/firewall/` 说明配置字段。不自动导入整个防火墙文件。
- **证书续期**：已包含 acme.sh 和 DNS API；凭据只放在设备私密配置中，续期成功后验证证书并重载 Nginx。不要提交凭据或私钥。

## 项目目录

```text
sources.lock.json        上游 URL、commit、Go bootstrap 哈希
configs/                 单一纯有线 profile
patches/                 可审查的板级/裁剪补丁
files/                   首次启动默认配置与防火墙规则
scripts/                 获取、构建与静态镜像验证
examples/                可选服务示例，不会自动打包启用
tests/                   离线仓库检查
docs/                    安装、服务、测试边界与发布说明
```

## 许可证与发布

本项目新增脚本和配置采用 **GPL-2.0-only**；修改的上游文件保留原许可，部分设备树文件原为双许可。第三方软件不因本仓库的 LICENSE 而改变许可。见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

源码仓库不包含完整第三方源码或二进制。若发布固件 Release，应同时处理对应源码、许可通知、构建配方、校验和与测试结果，具体检查见 [docs/RELEASING.md](docs/RELEASING.md)。
