# 2026-08-14 最新日志显示、存储延时与真实帧率分析

## 分析对象

- 日志：`logs/20260814_050253.log`
- 配置：`Scan=100000 Hz`、PHASE 单通道、`3072` 原始点、`Merge=3`、裁剪 `[100,800)`，保存帧宽 `700` 点。
- `Length/Load=0.2 s`，软件每次请求 `20000` 帧；`Length/Plot=0.4 s`；保存测试使用 `Length/Save=0.2 s`、`Length/File=1 s`。

## 主要结论

### 1. 0.4 秒刷新变成约 0.8 秒

采集块实际到达间隔集中在约 `0.390~0.409 s`，而旧逻辑严格要求距上次发布达到 `0.400 s`。当一个块在 `0.390 s` 到达时会被跳过，只能等下一块，最终 GUI 回调间隔稳定在约 `0.800 s`。这不是参数未生效，而是严格墙钟节流与实际采集块节拍形成的倍周期问题。

Tab2 启用后，旧逻辑还会发送最多 `40000 x 700 x int32` 的完整二维窗口，并先执行 Tab1 波形/频谱路径，再更新 Time-Space。日志中 Tab2 激活阶段 `_on_phase_data` 约 `0.54~0.62 s`，这是切换 Tab 和显示卡顿的主要来源。

### 2. BIN 与 BZ 都只有约 50 kframe/s 输出

从日志中的文件名时间戳统计：

| 格式 | 文件序号 | 文件数 | 首尾文件名时间跨度 | 文件间隔中位数 | 保存帧数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| BIN | 1..92 | 92 | 182.467 s | 2.004 s | 9,200,000 |
| BZ | 1..42 | 42 | 83.163 s | 2.002 s | 4,160,000 |

每个完整文件都是 `100000` 帧。BIN 文件大小应为 `100000 x 700 x 4 = 280,000,000 bytes`；日志总量 `25,760,000,000 bytes` 等于 `92 x 280,000,000`，包数 `460 x 20000` 也精确等于 9,200,000 帧。BZ 为 208 个 20K 帧包，文件序号连续，日志无丢块。

但“一个文件含 100K 帧”只证明按帧数切分正确，不能证明这些帧在真实时间上覆盖 1 秒。文件名显示当前 100K 个 PHASE 输出帧约用 2 秒到达应用，即输出约 50 kframe/s。

该现象不是保存器偷偷做时间降采样：

- 无存储测试同样约 `3,600,000 / 72.36 = 49.8 kframe/s`。
- BIN 与 BZ 的文件名间隔都约 2 秒，和压缩方式无关。
- 测试日志为 `save_ds=1`；`Save DS` 即使大于 1，也只抽取每帧内的空间点，不删除时间帧。
- BIN/BZ 均记录 `dropped=0`，应用接收到的包数与最终文件帧数严格相符。

因此 50 kframe/s 在保存器之前已经形成。当前最可能的原因按优先级为：

1. `PolarDiv` 启用后，固件可能使用两次物理扫描合成一个 PHASE 输出帧，所以 100 kHz 激光扫描对应约 50 kframe/s 相位输出。该语义需要厂商文档或关闭 PolarDiv 的 A/B 测试确认。
2. DLL/固件可能拒绝或钳制 100 kHz，而旧代码忽略所有配置 setter 返回码，仍无条件记录“Device configured successfully”。
3. 不像是主机读取不足：无存储稳定段的驱动缓冲比约 `0.6~1.1`，说明多数时间在等待下一块形成；若硬件持续产生 100 kframe/s 而主机只读 50 kframe/s，缓冲应持续线性增长。

### 3. 存储连续性边界

在“应用已经收到的数据”范围内，本次日志支持连续完整：

- BIN：460 包全部写入，92 个文件序号连续，字节数精确，无保存队列丢块。
- BZ：208 包全部写入，42 个文件序号连续，无 raw/packet/compressed 队列丢块；BZ 格式自带包序号和 CRC。
- 停止时保存器等待后台队列完整排空。

但当前测试环境没有 `D:\eDAS_DATA` 实体文件，无法对本次现场文件执行离线 CRC/逐值复读。BIN 裸流本身也没有包头、时间戳或 CRC，因此只能由文件大小、日志包计数和测试回读证明应用侧连续性，不能仅凭 BIN 内容证明硬件真实扫描时钟为 100 kHz。

## 本次代码优化

- 显示节流增加基于 `Length/Load` 的最大 50 ms 容差。当前配置容差为 30 ms，`0.390 s` 到达的块可以按 0.4 秒节拍发布，不再被推迟到 0.8 秒。
- Time-Space 使用自上次发布以来的不重叠增量二维快照，发布后清空显示历史，避免全窗口重发和重叠数据。
- `snapshot_kind=3` 在 GUI 中直接进入 Time-Space 更新并返回，不再执行 Tab1 波形、滤波和频谱路径。
- 采集诊断新增 `configured_fps`、`measured_fps`、`fps_ratio` 和 `driver_pending_frames`。
- 所有硬件配置 setter 现在检查 DLL 返回码；100 kHz 或其他参数被硬件拒绝时会立即报错，不再误报配置成功。
- INFO 日志记录 `scan_rate`、`rate2phase`、`merge`、`polar_div` 等全部关键硬件参数。
- BIN/BZ 保存器新增 `frames_received`、`frames_written`、`pending_frames` 和 `continuity_gap`；停止时输出完整性摘要，并明确 `storage_downsample_space_only`。
- 修复 BIN 保存器析构时重复输出总计日志的问题。

## 验证

- `python -m py_compile src\acquisition_thread.py src\main_window.py src\data_saver.py src\pcie7821_api.py`：通过。
- `python -m unittest tests.test_display_snapshot_cadence tests.test_data_saver_integrity -v`：7 项全部通过。
- 测试覆盖 BIN 逐值回读、BZ CRC 和包序、跨文件轮转、尾包、空间降采样、数组所有权、停止排空，以及 `frames_received == frames_written`、`continuity_gap == 0`。

## 下一轮现场测试

使用完全相同参数分别运行两次，每次至少 60 秒：

1. `PolarDiv=ON`，不存储或使用 BIN，记录 `measured_fps`、`fps_ratio`、`driver_pending_frames`。
2. 仅将 `PolarDiv=OFF`，其余参数不变，再记录同样指标。

判据：若关闭后 `measured_fps` 从约 50K 升到约 100K，可确认 PolarDiv 两扫描合帧；若仍约 50K，应检查新的 DLL setter 返回码，并向固件/硬件侧确认 3072 点、PHASE、Merge=3 配置下的最大输出帧率。真实时间轴和文件“秒数”在该结论确认前，应以 `measured_fps` 校准，而不是只使用文件名中的 configured `100000Hz`。
