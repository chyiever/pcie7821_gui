# PCIe-7821 eDAS GUI 开发说明

本项目是 PCIe-7821 采集卡的 eDAS 上位机软件，负责硬件参数配置、实时采集、显示、数据保存和可选 TCP 转发。当前版本的核心设计是把实时采集链路拆成几条边界清楚的数据流：

- DLL 读取：采集线程按 `Length/Load` 从驱动缓冲区读取完整数据块。
- GUI 显示：采集线程维护最新显示历史，按 `Length/Plot` 生成最新快照，GUI 只消费最新快照。
- 数据保存：`.bin` 和 `.bz` 共用 `Length/Save` 保存包与 `Length/File` 文件时长。
- TCP 通信：Tab3 按 `Length/Comm` 聚合完整采集块后发包。

这个设计目标是减少现场参数歧义，避免为了显示、保存或通信包长而被迫放大 DLL 单次读取块。

## 1. 运行方式

开发环境通常直接运行：

```bash
python run.py
```

无硬件或只验证界面时使用仿真模式：

```bash
python run.py --simulate
```

语法级检查可执行：

```bash
python -m py_compile src\config.py src\main_window.py src\acquisition_thread.py src\data_saver.py src\pcie7821_api.py
```

## 2. 主要模块

| 模块 | 职责 |
| --- | --- |
| `src/config.py` | 参数 dataclass、枚举、默认值和参数持久化基础结构。 |
| `src/main_window.py` | PyQt 主窗口、Tab 布局、参数采集与校验、采集/保存/通信流程编排。 |
| `src/acquisition_thread.py` | 采集线程、DLL 读取、仿真采集、完整数据分发、最新显示快照管理。 |
| `src/pcie7821_api.py` | PCIe-7821 DLL 的 ctypes 封装和 API 锁。 |
| `src/data_saver.py` | `.bin` 裸流保存、`.bz` bitshuffle+zstd 保存、后台队列和分文件。 |
| `src/tcp_tab3/` | Tab3 TCP 通信类型、组包、发送线程、连接管理和 Length/Comm 聚合。 |
| `src/utils.py` | 点数、距离、裁剪等通用计算工具。 |

## 3. 界面参数分布

Tab1 保留现场高频使用参数：

- 基础采集：`Scan(Hz)`、`Pulse(ns)`、`Points`。
- 上传设置：`Channels`、`Source`。
- 相位处理：`SpaceAvg`、`Merge`、`DiffOrder`、`Detrend`、`CropStart`、`CropEnd`。
- 显示设置：`Mode`、`Region`、`Waveform`、`PSD`、`Monitor`、`rad`、Filter。
- 保存操作：`SAVE`、`Path`、`Est. Size`、`Files`。

Tab3 负责通信：服务器 IP/端口、通道范围、时间/空间降采样、`Length/Comm` 和发送统计。

Tab4 负责低频配置：

- `Length/Load`、`Length/Plot`。
- `Clock`、`Trig`、`Bypass`、`CenterFreq`、`DataRate`、`Rate2Phase`、`PolarDiv`。
- `Format`、`Length/Save`、`Length/File`、`Save DS`、`Zstd Level`、`Bitshuffle Block`。

## 4. Length 参数模型

用户界面以秒为单位配置长度，运行时再按扫描率换算成帧数：

```text
load_frames = Length/Load * ScanRate
plot_frames = Length/Plot * ScanRate
save_frames = Length/Save * ScanRate
file_frames = Length/File * ScanRate
comm_frames = Length/Comm * ScanRate
```

默认值：

| 参数 | 默认值 | 作用 |
| --- | ---: | --- |
| `Length/Load` | `0.2 s` | 每次 DLL 读取的数据时长。 |
| `Length/Plot` | `1 s` | GUI 显示窗口时长。 |
| `Length/Save` | `1 s` | `.bin` / `.bz` 保存包时长。 |
| `Length/File` | `10 s` | `.bin` / `.bz` 单文件数据时长。 |
| `Length/Comm` | `1 s` | Tab3 单个 TCP 包数据时长。 |

校验规则：

```text
Length/Plot 必须是 Length/Load 的整数倍
Length/Save 必须是 Length/Load 的整数倍
Length/Comm 必须是 Length/Load 的整数倍
Length/File 必须是 Length/Save 的整数倍
```

内部仍保留 `frame_load_num`、`frame_plot_num` 和 `comm_frame_num` 等派生字段，供采集线程、显示线程和通信线程使用。这些字段是运行时换算结果，不再是用户直接填写的界面参数。

## 5. 采集与显示链路

采集线程每轮读取一个 `Length/Load` 完整块。完整块先进入后台消费者，包括保存和通信；显示链路只保留最新 `Length/Plot` 窗口。若 GUI 未及时消费旧快照，新快照会覆盖旧快照并记录 skip 统计，避免 Qt 事件队列堆积大数组。

Raw 读取块大小约为：

```text
raw_load_bytes = Points * load_frames * Channels * 2
```

PHASE 读取块大小约为：

```text
phase_load_bytes = (Points / Merge) * load_frames * Channels * 4
```

单通道 PHASE 启用裁剪后，进入显示、保存和通信的数据会使用裁剪后的空间点数。

## 6. 保存链路

`.bin` 和 `.bz` 现在共用同一组保存长度参数：

- `Length/Save` 决定每次后台写入或压缩 packet 覆盖多少秒数据。
- `Length/File` 决定一个文件覆盖多少秒数据。
- `Save DS` 只影响落盘数据抽点，不影响显示或 TCP。

`.bin` 文件仍是裸二进制连续数据流，不写 header。保存器会把多个 `Length/Load` 块聚合成 `Length/Save` 包后连续写盘，到 `Length/File` 后轮转文件。

`.bz` 文件为 bitshuffle+zstd packet 格式，packet 时长同样由 `Length/Save` 决定，文件时长由 `Length/File` 决定。旧界面中的 `BZPacketFrames`、`BZfiles(s)` 和 `Blocks/File` 不再作为用户参数出现。

## 7. Tab3 通信链路

Tab3 仅支持 `单通道 + PHASE`。管理器会把多个 `Length/Load` 块聚合到 `Length/Comm`，再交给发送线程构造协议包。

TCP 包体大小：

```text
samples_per_channel = comm_frames / TimeDownsample
channel_count = selected_space_points_after_SpaceDownsample
payload_bytes = channel_count * samples_per_channel * 8
tcp_packet_bytes = 24 + payload_bytes
```

`Length/Plot`、`Length/Save`、`Length/File` 和 BZ 压缩参数不影响 TCP 包大小。

## 8. 2026-07-29 采集卡挂死教训

2026-07-29 14:02 的卡死证据显示，直接卡点在 DLL 的 `pcie7821_read_phase_data()` 长时间不返回。watchdog 随后在 GUI 主线程触发 stop/start，而 stop 又等待同一把 API 锁，导致界面也卡住。15:15 和 15:22 两次重启仍出现 `buffer=4294967295/6820000`，说明底层设备或驱动状态没有被上层软件重启复位。

本次已在 `query_buffer_points()` 中检查 DLL 返回码和 `0xFFFFFFFF` 无效缓冲区值。后续若继续优化，应优先把 DLL 读卡死后的 stop 恢复流程改成异步/设备复位提示，避免 GUI 主线程同步等待不可中断 DLL 调用。

## 9. 文档索引

| 文档 | 内容 |
| --- | --- |
| `user_read.md` | 面向现场用户的操作说明和 Length 参数解释。 |
| `docs/README-2026-03-20-eDAS数据存储技术说明.md` | `.bin` / `.bz` 保存链路和 Length/Save、Length/File 说明。 |
| `docs/2026-03-14-Tab3-DAS数据通信功能开发方案.md` | Tab3 TCP 协议、Length/Comm 聚合和单包长度计算。 |
| `docs/2026-7-29采集卡挂死原因分析与各个环节单包数据长度梳理.md` | 2026-07-29 挂死原因、重启失败证据和各环节单包长度总表。 |

## 10. 开发注意事项

- 不要把显示窗口、保存包、TCP 包和 DLL 读取块重新绑成同一个参数。
- 新增参数时优先放在语义对应的 Tab，不要把低频硬件细节重新堆回 Tab1。
- 保存和通信必须从完整采集数据链路取数，不要从 GUI 显示快照取数。
- 现场硬件问题要结合日志中的 `read_ms`、`query_ms`、buffer 值、保存队列、TCP 队列和 STOP 响应判断。
- 历史文档中的 `FrameLoad`、`FramePlot`、`Blocks/File`、`BZPacketFrames` 多为旧版本语义，维护当前代码时以本 README 和 2026-07-29 后的文档为准。
