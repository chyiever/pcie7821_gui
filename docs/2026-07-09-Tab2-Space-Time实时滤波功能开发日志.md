# Tab2 Space-Time 实时滤波功能开发日志


Update note, 2026-07-17: the `Filter` input and `FILTER` button described below were moved out of Tab2 and into the left-side main Display Control area. The controls are now shared by Tab1 phase waveform and Tab2 Time-Space. Tab2 keeps an independent IIR filter state and receives the shared settings through `set_filter_settings()`.

## 1. 修改背景

本次需求是在 Tab2 的 Space-Time 图绘制前增加一个数据流实时滤波预处理能力。该滤波只用于二维图像显示，不允许影响保存数据，也不允许影响 Tab1 的时域曲线、频谱或 Monitor 显示。

当前程序的数据链路中，Tab2 的输入来自 `MainWindow._update_phase_display()` 传给 `TimeSpacePlotWidget.update_data()` 的 `frame x point` 显示快照。保存链路和 Tab1 已经在这个调用之前完成各自处理，因此把滤波逻辑封装在 `src/time_space_plot.py` 内部，可以把影响范围限制在 Tab2 图像缓冲写入之前。

## 2. 用户界面

Tab2 绘图参数区第二行新增两个控件：

- `Filter` 输入框：输入滤波参数字符串。
- `FILTER` 按钮：启用或关闭实时滤波。

输入格式如下：

- `1-`：1 Hz 高通。
- `-10`：10 Hz 低通。
- `2-10`：2 Hz 到 10 Hz 带通。

布局上压缩了原有控件的水平间距和若干输入框宽度，使 `Color Range`、`Colormap`、`Filter`、`Reset` 和 `PLOT` 保持在第二行。滤波按钮开启且参数有效时为蓝色；开启但参数无效或相对当前采样率不可设计时为橙色，并通过 tooltip 给出错误原因。

## 3. 数据流位置

滤波执行顺序如下：

```text
Tab2 update_data(frame x point)
    -> 按 Distance Range 裁剪空间范围
    -> 按 Space DS 选出实际绘制的位置点
    -> 对每个位置点沿时间轴执行实时滤波
    -> 按 Time DS 做显示降采样
    -> 转置为 space x time
    -> 写入 Time-Space 滚动显示缓冲
```

这样做有三个边界：

1. 滤波只接触 Tab2 要写入图像缓冲的数据视图。
2. 不回写 `MainWindow` 传入的原始显示快照，因此不影响 Tab1。
3. 不接触采集线程和保存器，因此不影响落盘数据。

## 4. 实时滤波实现

新增 `src/realtime_filter.py`，提供两个核心能力：

- `parse_filter_spec()`：解析 `1-`、`-10`、`2-10` 三类字符串。
- `RealtimeTimeAxisFilter`：对 `frames x positions` 矩阵沿时间轴执行向量化 IIR 滤波。

滤波器采用 `scipy.signal.butter(..., output="sos")` 生成二阶节形式，并使用 `scipy.signal.sosfilt()` 执行实时因果滤波。阶数当前固定为 2 阶，目的是控制实时计算量和相位延迟，同时保持足够的低通、高通、带通能力。

## 5. 边沿突跳处理

不能使用每个窗口独立 `filtfilt()` 或每次重新初始化滤波器，因为那会在每个实时块的左右边沿引入明显突跳。当前实现使用流式状态：

- 每个位置点维护独立的 IIR 状态。
- 第一个数据块用首个样本初始化 `sosfilt_zi()`，减少启动瞬间的阶跃响应。
- 后续数据块沿用上一次 `sosfilt()` 返回的状态。
- 只有滤波参数、采样率、距离范围、空间降采样或 PLOT 状态变化时才重置状态。

因此实时显示时，每个数据包不是孤立窗口，而是连续数据流的一段，滤波器状态会跨包延续，避免每个窗口都出现边沿突跳。

## 6. 短数据包与 0.1 Hz 高通

如果 `Scan=2000 Hz`、每包约 1 秒、用户设置 `0.1-` 高通，单个数据包长度确实短于 0.1 Hz 对应的 10 秒周期。但当前实现不按单包独立估计频率，也不对单包做零相位双向滤波，而是把每个包串成连续流后执行因果 IIR。

因此技术上可以滤波，不会因为单包只有 1 秒就直接失效。但需要注意：

- 0.1 Hz 高通的响应和稳定时间本来就是秒级到十秒级，不应期待第一个 1 秒包内马上完全稳定。
- 程序保留跨包状态后，滤波效果会随着后续数据持续进入逐步稳定。
- 若用户把截止频率设置到当前采样率 Nyquist 频率以上，程序会跳过滤波并提示参数无效。

这也是本次没有采用按窗口 `filtfilt()` 的主要原因：`filtfilt()` 对短窗口和低截止频率更容易出现边缘伪影，且实时性成本更高。

## 7. 性能处理

本次没有为每个位置点写 Python 循环，而是让 SciPy 在二维矩阵上沿 axis 0 一次性处理所有位置点：

```python
signal.sosfilt(sos, data_float, axis=0, zi=state)
```

在 Tab2 中，滤波发生在 `Distance Range` 裁剪和 `Space DS` 之后，因此处理的是实际要绘制的位置点集合，而不是完整采集空间点。滤波发生在 `Time DS` 之前，保证滤波采样率仍使用真实 `Scan(Hz)`，避免低频截止因为先降采样而失真。

## 8. 涉及文件

- `src/realtime_filter.py`
- `src/time_space_plot.py`
- `src/config.py`
- `src/main_window.py`
- `build_exe.py`
- `eDAS26.6.18.spec`
- `dev_log.md`

## 9. 验证情况

已执行：

```text
python -m py_compile src\realtime_filter.py src\time_space_plot.py src\config.py src\main_window.py
```

结果：通过。

已执行解析和流式滤波自检：

```text
1-     -> highpass
-10    -> lowpass
2-10   -> bandpass
0.1-   -> highpass
```

并确认连续两次处理 1 秒数据块时输出形状正确、结果为有限值、输入数组不被原地修改。

已执行：

```text
git diff --check
```

结果：无空白错误，仅有 Windows 环境下的 LF/CRLF 行尾提示。

## 10. 后续现场验证建议

现场联机时建议重点验证以下场景：

1. Tab2 PLOT 开启，Filter 关闭，确认 Time-Space 图行为与旧版本一致。
2. 输入 `1-` 并开启 FILTER，确认只有 Tab2 Space-Time 图变化，Tab1 曲线、PSD 和保存文件不变化。
3. 输入 `-10`、`2-10`，确认图像响应符合低通和带通预期。
4. 输入 `0.1-`，连续观察至少数十秒，确认没有每个包边界突跳，但允许启动阶段缓慢稳定。
5. 输入超过 Nyquist 的截止频率，确认按钮提示参数无效且程序不崩溃。
