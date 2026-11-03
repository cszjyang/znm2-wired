# 可选服务

所有示例都需要人工配置。不要把示例片段整体覆盖到已有网络或防火墙配置，不要在尚未设置密码的设备上开放管理入口。

## Passwall 与 Xray

在 LuCI 的 Passwall 页面填入自己的节点；固定的 Xray/Passwall 组合支持 VLESS 和 Hysteria2。启用前确认节点参数、DNS 分流、内网/校园网直连例外。仅安装一个 Xray 核心；“支持某协议”不等于每个节点供应商的所有新扩展都已测试。

本固件不提供 Geo 数据库默认分流节点。通用国家列表路由默认配置保留；如果自行使用依赖 Geo 数据的规则，需自行补齐依赖并评估内存。

WAN DNS 保护先于 Passwall 的重定向，默认拒绝来自 `wan` 的 TCP/UDP 53。LAN DNS 不受这条规则阻断。如果更改物理接口命名，需重新验证规则作用于正确入口。

## Tailscale

先设置 root 密码，再执行：

```sh
/etc/init.d/tailscale enable
/etc/init.d/tailscale start
tailscale up --accept-dns=false --accept-routes=false --hostname=znm2-wired
tailscale status
tailscale netcheck
```

使用终端输出的授权链接登录自己的 tailnet，不共享身份文件。默认只作为普通节点，不发布 LAN 子网路由、不做出口节点、不启用 Tailscale SSH。

固件中的 Tailscale zone 允许 tailnet 到路由器的访问；还应在 tailnet 的权限策略中限定管理者。路由器自身 Tailscale 数据包有独立的 Passwall 旁路，但这不等于 LAN 中其他设备的 Tailscale 流量也使用相同策略。

先测试实际 `direct`/`relay` 路径，再决定是否显式放行 WAN UDP 41641。UPnP 并非运行 Tailscale 的必要条件。设备密钥有效期与续期由使用者的 Tailscale 管理策略决定。

停用服务：

```sh
/etc/init.d/tailscale stop
/etc/init.d/tailscale disable
```

停用不等于删除身份或撤销设备。需要撤销时到自己的管理控制台处理，并按 Tailscale 的步骤清理对应状态，避免误删仍需保留的身份。

## Nginx HTTPS 反代

`examples/nginx/nginx.conf` 是单 worker、流式转发的起点，包含 WebSocket 配置；不启用访问日志或磁盘大缓冲。改成真实域名、后端和证书路径后，备份原配置，再安装到 `/etc/nginx/nginx.conf`。

安装自己的 fullchain 与私钥到示例指定目录，私钥权限设为 `600`。然后：

```sh
uci set nginx.global.uci_enable='false'
uci commit nginx
nginx -t -c /etc/nginx/nginx.conf
/etc/init.d/nginx enable
/etc/init.d/nginx restart
```

这里关闭 Nginx 包默认的 UCI 配置生成，让服务实际加载你安装的手写 `nginx.conf`。只有语法和证书检查通过后才执行后续启用、重启命令。

先从 LAN 测试登录、跳转、WebSocket/SSE 与上传下载，再根据需要添加 WAN 入口规则。HTTPS 上游应配置正确的 SNI 和受信任 CA；不要把关闭上游证书校验当作通用默认。

证书自动续期使用已安装的 ACME 工具，需提供自己的域名和 DNS API 凭据。本仓库没有预置 DNS 服务商账户；凭据不应出现在命令历史、仓库或示例文件中。续期 hook 需先检查证书与私钥配对，原子替换，再 `nginx -t` 并重载。尚未提供跨 DNS 服务商的自动部署脚本。

## microsocks

示例包含 UCI 配置和 procd init 脚本，默认 `enabled=0`，监听 `127.0.0.1:1080`。它不自动添加 WAN 防火墙例外，也不提供额外的认证封装。

需要时，分别复制 `examples/microsocks/config` 到 `/etc/config/znm2_socks`、`init` 到 `/etc/init.d/znm2-socks`，给 init 设置可执行权限。确认监听地址和访问范围后启用：

```sh
uci set znm2_socks.main.enabled='1'
uci commit znm2_socks
/etc/init.d/znm2-socks enable
/etc/init.d/znm2-socks start
```

本地验证示例：`curl --socks5-hostname 127.0.0.1:1080 https://example.com/`。需要 LAN 或 tailnet 使用时应显式调整绑定和访问策略；不要直接把无认证服务开放到 WAN。

取消此示例时先 stop/disable，再删除自己安装的这两个文件；不会影响 Passwall 的内部 SOCKS。

## 固定端口转发

`examples/firewall/redirect.uci` 是字段示例，只能在替换文档地址后通过 LuCI 或逐项 UCI 操作添加。不要使用未经检查的 `uci import firewall` 覆盖当前防火墙。

从应用层端口代理迁移为 DNAT 时，后端看到的来源地址可能改变。检查后端白名单、默认网关、回包路由，以及 LAN 经公网地址访问时的回流行为。

## 日志和内存

默认 logd 使用 64 KiB RAM 环形日志，重启后不保留；本仓库不预设远端日志接收器、连接级日志或定时重启。长期观察可从外部机器采集，接收端自行轮转。

评估资源时关注 `MemAvailable`、swap-in/out、OOM、进程重启和真实业务成功率。缓存占用不等同于内存不足；避免只读一个 free 数字作稳定性结论。

## 升级前的私密备份

自己安装的证书、Nginx 配置、额外 init 脚本及 Tailscale 状态不应假定都会自动保留。使用 `sysupgrade -l` 检查实际备份清单，按需在设备的 `/etc/sysupgrade.conf` 添加自己的路径，并把备份保存在私密位置。不要把设备身份备份公开或恢复到其他人的设备。
