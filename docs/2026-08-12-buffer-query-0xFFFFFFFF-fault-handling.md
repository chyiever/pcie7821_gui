# 2026-08-12 `0xFFFFFFFF` 缓冲区查询异常熔断处理

## 1. 现象

本次分析对象为 `logs/20260812_091940.log`。

日志中的启动过程正常：

- 程序在约 `0.553 s` 初始化设备。
- DLL 路径为 `D:\edas\edas3\libs\pcie7821_api.dll`。
- `pcie7821_open()` 在约 `0.9 ms` 内成功。
- 用户在约 `8.410 s` 点击 START。
- 参数为 `scan_rate=10000`、`points=3072`、`channels=1`、`data_source=4`、`length_load_s=0.200`、`length_plot_s=1.000`、`load_frames=2000`、`plot_frames=10000`、裁剪范围 `[100, 800)`。
- `pcie7821_start()` 在约 `61.3 ms` 内成功返回。

异常从采集线程第一次查询 DLL 缓冲区开始：

```text
query_buffer_points returned invalid buffer count 0xFFFFFFFF; driver/device state is likely stale or faulted
Error querying buffer: PCIe-7821 Error -5: query_buffer_points returned invalid buffer count 0xFFFFFFFF; reset the PCIe device/driver before starting acquisition again
```

本日志里该错误持续重复，`query_buffer_points returned invalid buffer count` 相关文本出现 `6898` 次，采集线程 `Error querying buffer` 出现 `3449` 次。期间自动 stop/start 后仍复现，说明软件层重新开始采集没有清掉底层异常状态。

用户现场反馈：重启电脑和采集卡后恢复正常。这一结果确认问题属于采集卡、驱动或 DMA 状态残留，而不是保存、通信、显示或 Length 参数本身导致。

## 2. 根因判断

`0xFFFFFFFF` 等于十进制 `4294967295`。对“缓冲区内每通道点数”来说，这不是合理物理值，更像底层把 `-1` 或错误哨兵值写入无符号输出参数后被上层按 `uint32` 读取。

当前代码已在 `pcie7821_api.py` 中拒绝该值并抛出 `PCIe7821Error(-5, ...)`，这是正确的硬件边界防护。问题在于旧采集线程捕获该异常后仍继续轮询，导致：

- 日志被同一错误刷屏，掩盖真正的设备状态。
- 自动恢复逻辑按“无成功读数超时”触发 stop/start，但设备/驱动状态仍未被复位，下一轮马上再次进入同一错误。
- 现场人员容易误以为软件仍在尝试恢复，实际应该进行设备/驱动级复位。

因此本次优化重点不是继续扩大软件重试，而是在识别明确的硬件边界异常后尽快停止采集、释放软件侧资源，并给出正确处置提示。

## 3. 代码处理

### 3.1 API 层

`src/pcie7821_api.py` 继续保留以下防护：

- 检查 `pcie7821_point_num_per_ch_in_buf_query()` 返回码，非 0 立即抛出 `PCIe7821Error`。
- 检查输出点数是否为 `0xFFFFFFFF`。
- 对 `0xFFFFFFFF` 抛出明确错误，提示重启采集前需要 reset PCIe device/driver。

### 3.2 采集线程

`src/acquisition_thread.py` 新增缓冲区查询错误熔断：

- `PCIe7821Error` 被视为致命缓冲区查询错误。
- 错误文本包含 `0xFFFFFFFF` 也被视为致命错误。
- 致命错误发生后，采集线程设置阶段为 `buffer_query_error`，发出 `error_occurred` 信号，并将 `_running` 置为 `False`，退出等待循环。
- 普通非致命查询异常保留有限重试，连续达到 `BUFFER_QUERY_FAILURE_LIMIT = 5` 后停止，防止异常轮询无限刷屏。
- 诊断快照新增 `buffer_query_error_count`、`consecutive_buffer_query_errors` 和 `last_buffer_query_error`。

这使日志从“几千行重复警告”收敛为“一次明确致命错误 + 停止信息”。

### 3.3 主窗口

`src/main_window.py` 新增致命采集错误处理：

- `_on_error()` 忽略旧线程延迟到达的错误信号，避免污染新一轮采集状态。
- 对 `Fatal buffer query error`、`0xFFFFFFFF` 或 `driver/device state` 相关错误，调度 STOP 清理流程。
- STOP 清理仍复用原有 `_on_stop()`，包括停止硬件、等待线程退出、停止保存器、停止 Tab3 TCP 会话和恢复 UI 控件。
- 状态栏提示 `Fatal acquisition error: reset PCIe device/driver before restarting`。
- 不再依赖自动恢复重启，因为本次现场已经证明电脑和采集卡重启后才恢复。

## 4. 现场处置步骤

再次看到如下任一日志时，应按设备/驱动异常处理：

- `query_buffer_points returned invalid buffer count 0xFFFFFFFF`
- `Fatal buffer query error; stopping acquisition`
- `reset the PCIe device/driver before starting acquisition again`

建议现场步骤：

1. 在软件中停止采集，确认 START 按钮恢复可用。
2. 关闭上位机程序，避免继续持有 DLL 或设备句柄。
3. 断电并重新上电采集卡，或按现场设备规范执行硬件复位。
4. 若采集卡复位后仍异常，重启 Windows 主机，确保 PCIe 设备重新枚举、驱动状态重新初始化。
5. 重新打开程序，再启动采集。
6. 若再次立即出现 `0xFFFFFFFF`，不要反复软件 stop/start，应检查 PCIe 接触、供电、驱动加载状态、采集卡温度、外部触发/时钟和 DLL/驱动版本。

本次用户反馈“重启电脑和采集卡就好了”，与上述处置路径一致。

## 5. 不应误判为以下问题

本次日志不支持将根因归为以下路径：

- `.bin` 或 `.bz` 保存阻塞：日志在第一次成功读取数据前就失败，没有保存队列堆积证据。
- Tab3 TCP 通信阻塞：没有成功读到 PHASE 数据，也没有进入有效通信包聚合。
- GUI 绘图卡顿：采集线程还没有产生显示快照。
- Length 参数错误：设备配置和 `pcie7821_start()` 已成功，错误点在之后的 DLL 缓冲区查询。
- PHASE 裁剪或 Time-Space 显示：裁剪范围 `[100, 800)` 只影响成功读数后的数据整形，本次失败发生在读取前。

## 6. 验证建议

软件侧验证：

- 执行 `python -m py_compile src\acquisition_thread.py src\main_window.py src\pcie7821_api.py`。
- 构造 mock API，让 `query_buffer_points()` 抛出 `PCIe7821Error(-5, "...0xFFFFFFFF...")`，确认采集线程只触发一次致命错误并退出。
- 检查 `Acq snapshot` 是否包含 `query_errors=current/total` 和 `query_error=...`。

现场硬件验证：

- 在采集卡正常状态下确认采集不受影响。
- 若再次复现 `0xFFFFFFFF`，确认程序停止而不是持续刷屏。
- 复位采集卡或重启主机后，再确认采集可恢复。

## 7. 结论

`0xFFFFFFFF` 是设备/驱动/DMA 状态异常的强信号。软件不应把它当作真实缓冲区点数，也不应在明确异常后无限重试或反复自动重启。正确策略是：API 层拒绝无效值，采集线程熔断退出，主窗口做一次清理停止，并提示现场执行采集卡或驱动级复位。
