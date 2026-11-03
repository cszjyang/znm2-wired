# 构建说明

完整构建的依赖和命令见 [README](../README.md)。本页说明可选步骤、缓存和修改配置时的注意事项。

## 构建输入

| 位置 | 用途 |
| --- | --- |
| `sources.lock.json` | 主源码、四个 feeds 的 URL 和提交，以及 Go bootstrap 下载哈希 |
| `configs/` | ZN-M2 纯有线配置 |
| `patches/` | 板级与功能裁剪补丁 |
| `files/` | 首次启动默认配置和防火墙规则 |
| `scripts/` | 源码准备、编译及镜像检查 |
| `examples/` | 可选服务示例，不会自动打包启用 |
| `tests/` | 离线仓库检查 |

补丁会修改共享构建目标的默认值，不应把本构建目录用于其他设备。完整编译入口会检查至少 30 GiB 空闲空间，这是最低门槛；建议预留至少 60 GiB，并按并行度和实际构建情况增加资源。

## 只准备源码

```sh
python3 scripts/build.py --work-dir /path/to/znm2-build --prepare-only
```

准备阶段会：

1. 按锁定的提交获取主源码和四个软件源（feeds）。
2. 检查并应用 `patches/` 中的补丁。
3. 下载并校验 Go bootstrap 的固定 SHA256。
4. 安装选定的软件包定义和默认配置，移除缺少 Geo 数据库依赖的 Passwall 示例节点。
5. 执行 `make defconfig`，检查依赖展开后的配置并输出 `config-check.json`。

## 使用下载缓存

缓存是可选的，只用于减少下载：

```sh
python3 scripts/build.py --work-dir /path/to/znm2-build --prepare-only \
  --go-cache /path/to/public-bootstrap-downloads \
  --dl-cache /path/to/openwrt-source-archives
```

`--go-cache` 中的文件仍必须通过大小和 SHA256 校验；`--dl-cache` 只复制源码归档，软件包下载由上游构建系统校验。缓存参数不用于复用旧工具链或编译中间文件。

## 继续构建与修改配置

首次使用必须提供空工作目录。已成功准备的同一目录可以继续编译：

```sh
python3 scripts/build.py --work-dir /path/to/znm2-build --jobs 8
```

脚本会检查构建输入是否仍与准备时一致。若需调整功能，先修改仓库中的配置、补丁或默认文件，再使用新的工作目录重新准备和编译；不要直接修改已经准备完成的构建树。配置检查包含本项目的组件约束，改变这些约束时还需相应更新检查逻辑并验证依赖。

安装额外内核模块（kmod）时，应使用同次构建的匹配软件包，其他快照软件源中的模块可能与本固件内核不兼容。

## 验证结果

编译完成后会自动检查软件包版本、内核配置、设备树的内存与端口定义、镜像格式及默认配置，结果写入工作目录的 `verification/result.json`。

本项目固定源码和配置版本，但尚不保证不同机器生成逐字节相同的镜像。静态检查通过后，仍需对实际镜像进行联网、服务和恢复测试，见 [验证说明](VALIDATION.md)。
