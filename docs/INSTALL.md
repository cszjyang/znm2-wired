# 安装与恢复边界

本项目只有 `zn_m2` 纯有线 profile。镜像元数据能证明目标板型，不能代替确认当前设备的引导程序和闪存分区。不要把其他机型、修改过分区的机器或不同刷机路径视为已经兼容。

## 刷机前

1. 保存当前固件来源、版本、配置备份，以及该设备恢复所需的资料。设备唯一的校准/身份分区不要用他人的备份覆盖。
2. 确认你有适用于当前引导程序的恢复办法；本仓库不提供通用的原厂转刷、U-Boot 或 MTD 写入流程。
3. 保持客户端通过有线连接目标 LAN；管理电脑的独立上网路径不要依赖待刷设备。仅插入 USB 网卡或网线不会自动证明管理路由正确。
4. 检查固件校验和和 `verification/result.json`。公共源码当前不附带已验收的可刷 Release。

## 已运行兼容 OpenWrt 的设备

只有在确认支持当前 sysupgrade 路径后，才上传对应的 `*-sysupgrade.bin`。以下命令在路由器上执行，文件名需要自己替换：

```sh
image_path=/tmp/your-sysupgrade.bin
sysupgrade -T "$image_path"
```

`-T` 通过不代表所有硬件/引导条件均已检查。干净安装命令如下，**`-n` 会清除旧配置**：

```sh
sysupgrade -n "$image_path"
```

不要把 `factory.ubi`、initramfs 和 sysupgrade 镜像混用，也不要绕过不匹配提示强刷。首次安装建议重建业务配置，避免将含无线、NSS、旧防火墙或旧 Tailscale 身份的整份 overlay 恢复到新配方。

## 首次启动

LAN 默认 `192.168.8.1/24`，WAN 默认 DHCP。从受信任 LAN 设置 root 密码，检查 `ubus call system board`、接口地址、DNS 和服务状态。应用默认停用；逐项配置并测试后启用。

同一 profile 保留配置升级时，`/etc/znm2-wired/configured` 防止首次启动脚本覆盖网络设置。它随 sysupgrade 配置备份保留；使用 `-n` 后标记会消失并重新执行默认设置。不要仅为重跑默认配置而随意删除它。

远程升级、WAN 身份切换或修改 LAN 地址前，应自行准备可靠的恢复通道；仓库没有自动断网、自动刷机或自动恢复旧身份的脚本。
