# 2026-04-28 Monitor 与 Phase 时域绘图开关控制

## 1. 目标

为 `Monitor` 数据和 `Phase` 时域曲线增加明确、稳定的 GUI 绘图开关，并让这些开关参与本地参数自动保存与恢复。

本次目标如下：

- `Plot1` 时域曲线可按需关闭刷新
- `Plot3` Monitor 曲线可按需关闭刷新
- 非 `PHASE` 数据源下，Monitor 控件状态与显示行为保持一致
- 开关状态在下次启动时自动恢复

## 2. 当前实现

### 2.1 Plot1 时域曲线开关

[`src/main_window.py`](/D:/OneDrive%20-%20EVER/00_KY/DAS-%E5%99%A8%E4%BB%B6%E6%B5%8B%E8%AF%95%E3%80%81%E4%B8%8A%E4%BD%8D%E6%9C%BA%E5%BC%80%E5%8F%91/BX/PCIe-7821/pcie7821_gui/src/main_window.py) 中沿用并补强了 `waveform_enable_check`：

- 关闭时清空 `Plot1`
- 打开后后续相位/Raw 数据可继续刷新 `Plot1`
- 开关状态写入 `display.waveform_plot_enabled`

虽然控件名称仍为 `Waveform`，但在 `PHASE` 数据源下，它就是 `Phase` 时域曲线的显示开关。

### 2.2 Monitor 曲线开关

`monitor_enable_check` 现已完整纳入以下逻辑：

- 关闭时清空 `Plot3`
- 打开时如果已有缓存的 Monitor 数据，则立即补画
- 开关状态写入 `display.monitor_plot_enabled`

### 2.3 数据源联动

新增 `_sync_display_control_states()` 统一处理显示控件与数据源关系：

- 当数据源为 `PHASE`：
  - `Plot3` 可用
  - `SPACE` 模式可用
  - `Monitor` 复选框可用
- 当数据源不是 `PHASE`：
  - `Plot3` 禁用
  - `SPACE` 模式禁用
  - `Monitor` 复选框禁用
  - 已显示的 Monitor 曲线立即清空

这里禁用的是 GUI 显示入口，不是底层采集线程的读取逻辑。

## 3. 持久化

本次新增的两个显示开关都已经进入本地参数文件：

- `display.waveform_plot_enabled`
- `display.monitor_plot_enabled`

因此软件下次启动时会自动恢复：

- 时域曲线是否显示
- Monitor 曲线是否显示

## 4. 运行时说明

### 4.1 开关作用域

这两个控件只影响 GUI 绘图，不影响：

- 设备采集参数
- Time-Space 图的 `PLOT` 开关
- 数据保存链路
- TCP 通信链路

### 4.2 Monitor 的边界

Monitor 曲线本身只在 `PHASE` 数据源下有意义，因此当切换到 `Raw / I_Q / arc` 时，当前实现会隐藏其显示能力，但保留其勾选状态，待用户切回 `PHASE` 时可继续使用。

## 5. 总结

本次修改把 `Plot1` 时域曲线和 `Plot3` Monitor 曲线的开关从“仅局部起作用”补齐到了“运行时行为完整、和数据源联动、可本地恢复”的状态，更适合长期调试和现场使用。
