# PCIe-7821 eDAS 上位机用户说明

## 1. 软件用途

本软件用于控制 PCIe-7821 采集卡完成 eDAS 数据采集、实时显示、频谱分析、Time-Space 显示、数据保存以及可选的 TCP 数据转发。当前版本把“采集读取、显示窗口、保存包、文件时长、通信包”统一改成以秒为单位配置，用户主要需要理解 `Length/Load`、`Length/Plot`、`Length/Save`、`Length/File` 和 `Length/Comm` 之间的关系。

这几个参数不会改变板卡每秒产生的数据总量；它们改变的是软件每次读取、显示、保存、分文件和发送网络包的时间粒度。若粒度设置过大，单次 DLL 读调用、压缩任务、写盘任务或 TCP 发送包都会变大，现场更容易出现停止响应慢、缓冲区积压或下游处理延迟。

## 2. 启动方式与运行模式

通常直接执行下面的命令即可启动软件：

```bash
python run.py
```

如果当前机器没有连接 PCIe-7821 采集卡，或者希望先检查界面行为、参数恢复和绘图是否正常，可以使用仿真模式：

```bash
python run.py --simulate
```

仿真模式下软件仍会完整创建主窗口、参数面板、波形图、频谱图和 Time-Space 图，并走大部分显示链路，但不会访问真实硬件。这种模式适合新用户熟悉界面，也适合先确认本机 Python、PyQt5 和 pyqtgraph 环境是否齐全。

## 3. 主界面分区

Tab1 左侧现在只保留高频使用的采集、上传、相位处理、显示开关和保存启停控件，减少现场采集时的参数干扰。低频硬件配置、采集长度、保存长度和 BZ 压缩细节集中放在 Tab4。Tab3 只负责通信参数、连接状态和发送统计。

Tab1 参数区主要包含：

- 基础采集：`Scan(Hz)`、`Pulse(ns)`、`Points`。
- 上传设置：`Channels`、`Source`。
- 相位处理：`SpaceAvg`、`Merge`、`DiffOrder`、`Detrend`、`CropStart`、`CropEnd`。
- 显示设置：`Mode`、`Region`、`Waveform`、`PSD`、`Monitor`、`rad`、Filter 参数。
- 保存操作：`SAVE`、`Path`、`Est. Size`、`Files`。

Tab4 参数区主要包含：

- 采集长度：`Length/Load`、`Length/Plot`。
- 硬件细节：`Clock`、`Trig`、`Bypass`、`CenterFreq`、`DataRate`、`Rate2Phase`、`PolarDiv`。
- 存储设置：`Format`、`Length/Save`、`Length/File`、`Save DS`、`Zstd Level`、`Bitshuffle Block`。

Tab3 通信区包含服务器 IP、端口、通道范围、时间/空间降采样、`Length/Comm`、连接状态和发送统计。

## 4. Length 参数的统一规则

运行时软件会根据扫描率把秒数换算成帧数：

```text
load_frames = Length/Load * ScanRate
plot_frames = Length/Plot * ScanRate
save_frames = Length/Save * ScanRate
file_frames = Length/File * ScanRate
comm_frames = Length/Comm * ScanRate
```

这些换算结果必须是整数帧。当前默认值如下：

| 参数 | 默认值 | 作用 |
| --- | ---: | --- |
| `Length/Load` | `0.2 s` | 采集线程每次从 DLL 缓冲区读取的数据时长。 |
| `Length/Plot` | `1 s` | GUI 波形、PSD、Time-Space 可使用的最新显示窗口时长。 |
| `Length/Save` | `1 s` | `.bin` 和 `.bz` 共用的保存包时长。 |
| `Length/File` | `10 s` | `.bin` 和 `.bz` 共用的单文件数据时长。 |
| `Length/Comm` | `1 s` | Tab3 每个 TCP 通信包对应的采集时长。 |

约束关系如下：

```text
Length/Plot 必须是 Length/Load 的整数倍
Length/Save 必须是 Length/Load 的整数倍
Length/Comm 必须是 Length/Load 的整数倍
Length/File 必须是 Length/Save 的整数倍
```

例如 `Scan(Hz)=2000` 时，默认配置会得到：

```text
Length/Load = 0.2 s -> 400 frames
Length/Plot = 1.0 s -> 2000 frames = 5 个采集块
Length/Save = 1.0 s -> 2000 frames = 5 个采集块
Length/File = 10.0 s -> 20000 frames = 10 个保存包
Length/Comm = 1.0 s -> 2000 frames = 5 个采集块
```

如果输入的秒数不能换算成整数帧，或者不满足上面的倍数关系，软件会拒绝开始采集或拒绝应用参数。

## 5. `Length/Load` 与 `Length/Plot`

`Length/Load` 是上位机每次从 DLL 缓冲区取走完整数据的时长，它决定单次 DLL 读调用的数据块大小和阻塞窗口。它越大，单次读出的数组越大、一次 DLL 调用不返回时造成的停顿越明显；它越小，单次读块更轻，但 DLL 调用频率会增加。

`Length/Plot` 只决定显示侧窗口大小。当前版本支持 `Length/Plot` 大于 `Length/Load`：采集线程会在内部维护最新显示历史，把多个采集块拼成显示窗口，再只把最新快照交给 GUI。保存链路和通信链路仍接收完整采集数据，不依赖 GUI 是否来得及绘图。

Raw 数据单次读取块大小约为：

```text
raw_load_bytes = Points * load_frames * Channels * 2
```

PHASE 数据单次读取块大小约为：

```text
phase_points = Points / Merge
phase_load_bytes = phase_points * load_frames * Channels * 4
```

若启用 PHASE 裁剪，后续显示、保存和通信使用裁剪后的空间点数；底层 DLL 原始读取压力仍首先由采集点数、合并参数、通道数和 `Length/Load` 决定。

## 6. 保存参数

点击 `SAVE` 并设置好保存路径后，采集开始时程序会创建后台保存器；采集中也可以用该按钮启停保存。当前 `.bin` 和 `.bz` 使用同一组长度参数：

- `Length/Save`：每个保存包包含多少秒数据，默认 `1 s`。
- `Length/File`：每个文件包含多少秒数据，默认 `10 s`。
- `Save DS`：落盘前的空间抽点倍率，只影响保存，不影响实时显示、Filter 或 TCP 通信。
- `Format`：选择 `.bin` 或 `.bz`。

`.bin` 文件仍是裸二进制连续数据流，不写额外 packet header。软件会先把多个 `Length/Load` 采集块聚合成一个 `Length/Save` 保存包，再写入当前文件；达到 `Length/File` 后切换文件。

`.bz` 文件会按 `Length/Save` 生成压缩 packet，并按 `Length/File` 分文件。旧版本中的 `BZPacketFrames`、`BZfiles(s)` 和 `Blocks/File` 已不再作为用户参数出现；对应语义分别由 `Length/Save` 和 `Length/File` 统一替代。

估算保存文件大小时，可以先算每秒数据量，再乘以 `Length/File`。Raw 单通道未降采样时：

```text
raw_bytes_per_second = Points * ScanRate * 2
raw_file_bytes = raw_bytes_per_second * Length/File / SaveDS
```

PHASE 单通道时：

```text
phase_bytes_per_second = phase_points_after_crop * ScanRate * 4
phase_file_bytes = phase_bytes_per_second * Length/File / SaveDS
```

`.bz` 的实际文件大小还取决于数据可压缩性、Zstd 压缩等级和 bitshuffle block 设置，不能只按原始字节数精确预测。

## 7. Tab3 TCP 通信

Tab3 通信当前只支持 `单通道 + PHASE` 模式。若切换到 Raw、多通道或其他不满足条件的模式，界面会显示通信不可用。这不是简单 UI 限制，而是因为后台协议默认输入为单通道 PHASE 时间-空间矩阵。

通信发送流程如下：

1. 采集线程每次读出一个 `Length/Load` 完整块。
2. Tab3 管理器把多个完整块聚合到 `Length/Comm`。
3. 发送前按用户设置裁剪空间通道范围。
4. 再执行空间降采样和时间降采样。
5. 转为 `rad` 单位、大端 `float64`，按通道优先顺序发送。

TCP 包头固定为 `>IIIId`，长度为 `24` 字节。包体大小由以下因素决定：

```text
samples_per_channel = comm_frames / TimeDownsample
channel_count = selected_space_points_after_SpaceDownsample
payload_bytes = channel_count * samples_per_channel * 8
tcp_packet_bytes = 24 + payload_bytes
```

因此，`Length/Comm` 决定每包时间窗口；`TimeDownsample` 决定每个通道保留多少时间样本；通道起止范围和 `SpaceDownsample` 决定发送多少空间通道。`Length/Plot`、`Length/Save`、`Length/File` 不参与 TCP 包大小。

为了和接收端恢复矩阵一致，`TimeDownsample` 需要整除 `Scan(Hz)`；`Length/Comm` 需要是 `Length/Load` 的整数倍。

## 8. 波形、频谱和 Time-Space

波形图主要用于观察当前显示窗口中的时域或空间域信号。显示模式为 `TIME` 时，程序展示时间帧上的空间曲线；显示模式为 `SPACE` 时，程序抽取空间位置，展示它随时间变化的曲线。频谱图用于观察当前显示窗口中的频域成分。对于 PHASE 数据，软件会按相位数据路径计算 PSD；对于 Raw 数据，则更接近普通功率谱显示。

Time-Space 图适合观察空间-时间二维结构，例如扰动沿光纤传播的连续轨迹、局部区域稳定性或某段距离范围内的时变分布。它处理的是显示快照，不是保存文件本身的原样平铺，因此适合实时监视趋势，但不能替代完整数据归档。

## 9. `rad`、裁剪与显示开关

PHASE 模式下，勾选 `rad` 后，界面上显示的相位值会按下面公式转为弧度：

```text
phase_rad = phase_int32 / 32767 * pi
```

这个开关只影响显示，不改变保存到磁盘的原始 `int32` 值。Tab3 通信发送的数据固定使用 `rad` 单位，不依赖 Tab1 的显示开关状态。

PHASE 裁剪参数会减少进入后续显示、保存和通信链路的空间点范围。裁剪范围设置过大或错误时，可能导致可显示点数减少、Time-Space 范围超出实际数据或通信载荷不符合预期，因此修改后应检查状态栏中的点数和图像是否仍符合预期。

`Waveform`、`PSD`、`Monitor` 等显示开关可以在不影响采集本身的情况下减少 GUI 绘图负担。现场机器显示压力较大时，可以先关闭不必要的显示项，再观察采集、保存和通信是否稳定。

## 10. 停止采集与异常处理

点击 STOP 后，程序会请求采集线程停止，再停止硬件、关闭保存会话和 TCP 会话，并清理未显示的快照。当前版本已经针对“GUI 历史大数组积压导致 STOP 延迟”的问题做过优化，合理参数下停止响应应明显好于早期版本。

如果 STOP 后界面很久才恢复、驱动缓冲区持续增长、图像长时间不更新，或日志中出现读取停滞，应优先检查 `Length/Load` 是否过大，再检查点数、通道数、数据源、保存格式、磁盘速度和 TCP 下游速度。若日志中出现 `buffer=4294967295` 或类似无效缓冲区值，应优先按设备/驱动异常处理，单纯重启上层软件未必能恢复。

## 11. 一套稳妥的使用顺序

建议先用仿真模式确认界面和参数恢复正常，再连接硬件；接着从较保守的 `Scan(Hz)`、`Points`、`Length/Load`、`Length/Plot` 开始测试；确认开始、停止、保存和图像都稳定后，再逐步提高负载；如果需要 TCP 通信，最后开启 Tab3 并检查连接状态、发送包计数和下游接收状态。

高带宽现场测试时，不要只看 GUI 是否流畅。至少同时观察日志中的读取耗时、缓冲区点数、保存队列、压缩耗时、TCP 队列和 STOP 响应时间。这样才能区分瓶颈是在 GUI、DLL/驱动、磁盘还是网络。
