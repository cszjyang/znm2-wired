# ZN-M2 Wired

为 **256 MiB 内存的 ZN-M2 路由器**制作精简的纯有线 ImmortalWrt 固件，适合通过交换机连接电脑或服务器，提供路由、透明代理、HTTPS 反向代理和远程访问。

项目面向轻并发使用，通过去除无线及不需要的驱动、使用单个代理核心，为常用服务留出内存。目前提供构建脚本、配置和使用示例，需要自行编译。

当前版本：`0.1.0-dev`。构建与测试记录见 [验证说明](docs/VALIDATION.md)。

## 功能与取舍

| 用途 | 提供的组件 |
| --- | --- |
| 基础路由与管理 | LuCI 网页管理、SSH、DHCP/DNS、防火墙、端口转发 |
| 透明代理 | Passwall + Xray，支持 VLESS、Hysteria2，共用一个代理核心 |
| 远程组网 | Tailscale |
| SOCKS5 代理 | microsocks，附可选服务配置示例 |
| HTTPS 网站与反向代理 | Nginx，附反代配置示例 |
| 证书申请与续期 | acme.sh 与 DNS API 支持，需要自行配置域名和凭据 |

精简范围包括 Wi-Fi、USB 扩展、PPPoE 拨号、UPnP 和 DDNS，这些功能未包含在构建配置中。无线接入可由独立 AP 提供。

为控制资源占用，关闭无线子系统和 NSS 加速，回收不用的 16 MiB NSS 保留内存；使用 64 KiB RAM 日志、1000 条 DNS 缓存和上限 64 MiB 的 zram。zram 将内存页压缩后保存在 RAM 中，实际资源占用随连接数、代理规则和流量变化。

目标设备为 ZN-M2，构建目标为 `qualcommax/ipq60xx`、设备为 `zn_m2`。刷机步骤及设备要求见 [安装说明](docs/INSTALL.md)。

## 编译

使用 Linux x86_64、Python 3.10+ 和普通用户；建议至少 16 GiB RAM、60 GiB 可用空间。选择不含空格的构建路径，并确保能够访问 GitHub、Go 下载站和软件包源码站。

Ubuntu 22.04 / 24.04 的依赖安装示例：

```sh
sudo apt update
sudo apt install -y build-essential clang flex bison g++ gawk gettext git \
  libncurses-dev libssl-dev libelf-dev zlib1g-dev python3 python3-setuptools \
  rsync swig unzip file wget curl ca-certificates patch perl xz-utils zstd
```

克隆仓库，并选择一个全新的构建工作目录：

```sh
git clone https://github.com/cszjyang/znm2-wired.git
cd znm2-wired
python3 tests/check_repository.py
python3 scripts/build.py --work-dir /path/to/znm2-build --jobs 8
```

使用普通用户运行构建脚本，它会自动获取锁定版本的源码、应用补丁、准备配置、编译并检查镜像；内存较少时降低 `--jobs` 并行度。

构建结果位于：

```text
/path/to/znm2-build/firmware/bin/targets/qualcommax/ipq60xx/
/path/to/znm2-build/verification/result.json
```

已运行兼容 OpenWrt 的设备通常使用 `*-sysupgrade.bin`，具体操作和配置备份方式见 [安装说明](docs/INSTALL.md)。源码准备、下载缓存、继续构建和修改配置的方法见 [构建说明](docs/BUILD.md)。

## 首次配置

全新安装后的默认设置：

| 项目 | 默认值 |
| --- | --- |
| LAN 地址 | `192.168.8.1/24` |
| WAN | DHCP 自动获取地址，使用设备原有 MAC |
| 主机名 / 时区 | `ZN-M2-Wired` / `Asia/Shanghai` |
| Passwall、Tailscale、Nginx、ACME | 停用，配置完成后按需启用 |
| WAN 管理入口 | 不默认开放网页管理、SSH 或 SOCKS |

按以下顺序配置：

1. 用网线连接电脑和路由器 LAN 口，访问 `http://192.168.8.1/`，先设置 root 密码。
2. 确认 LAN 与上游网段不重叠。如果上游也使用 `192.168.8.0/24`，先修改 LAN 地址，再连接 WAN。
3. 根据上游要求选择 DHCP 或静态 WAN 地址，确认普通设备能正常获取地址、解析 DNS 并联网。
4. 按下表逐项配置所需服务，每启用一项就验证访问和内存占用。
5. 按 [安装说明](docs/INSTALL.md) 保存配置备份，再验证设备重启后的联网和服务恢复。

默认防火墙会阻止从 WAN 访问路由器的 DNS 服务；路由器自身的 Tailscale 流量绕过 Passwall。修改接口名称或网络拓扑后，需要重新检查这些规则。

## 启用可选服务

具体命令、示例和停用方法见 [服务配置说明](docs/SERVICES.md)。

| 服务 | 首次配置需要做什么 |
| --- | --- |
| Passwall | 在 LuCI 中添加 Xray 节点，检查 DNS、分流和直连规则后启用；VLESS 与 Hysteria2 无需分别安装核心 |
| Tailscale | 启动服务并登录自己的账号授权设备；默认不发布内网路由、不作为出口节点 |
| Nginx HTTPS 反代 | 填写实际域名、后端和证书路径，按服务说明安装配置，检查通过后启用 |
| microsocks | 安装示例服务并明确监听地址和访问范围；示例默认停用、仅监听回环地址 |
| 端口转发 | 在 LuCI 中添加需要的目标和端口，再检查后端回包路由及防火墙 |
| 证书续期 | 配置自己的 DNS API 凭据，以及续期成功后的证书部署和 Nginx 重载步骤 |

## 上游与许可证

基于 [VIKINGYFY/immortalwrt](https://github.com/VIKINGYFY/immortalwrt)，应用来自 ImmortalWrt 和 Openwrt-Passwall 软件源。源码提交及下载哈希记录在 [sources.lock.json](sources.lock.json)。

本项目新增脚本和配置采用 **GPL-2.0-only**；第三方组件和修改的上游文件保留各自许可，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。分发固件时的对应源码、许可和验证要求见 [发布说明](docs/RELEASING.md)。
