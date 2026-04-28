# 2026-04-28 raw 和 timespace 绘图优化

## 1. 目标

本次优化针对两条主要绘图链路：

- `Tab1` Raw 时域曲线
- `Tab2` Time-Space 图

目标如下：

- 减少 Raw 大曲线在实时刷新时的无效开销
- 让 Raw 图放大后仍保留有效细节
- 将 Time-Space 图改为固定滚动缓冲，避免每次全量拼接
- 明确 Time-Space 图的数据轴语义，避免滚动方向错误

## 2. 修改内容

### 2.1 Raw 曲线改用 PyQtGraph 大曲线优化

在 [`src/main_window.py`](/D:/OneDrive%20-%20EVER/00_KY/DAS-%E5%99%A8%E4%BB%B6%E6%B5%8B%E8%AF%95%E3%80%81%E4%B8%8A%E4%BD%8D%E6%9C%BA%E5%BC%80%E5%8F%91/BX/PCIe-7821/pcie7821_gui/src/main_window.py) 中为实时曲线统一补充：

- `setClipToView(True)`
- `setDownsampling(auto=True, method="peak")`
- `setSkipFiniteCheck(True)`

作用如下：

- 仅处理当前可视区域附近的数据
- 放大缩小时自动抽样，并尽量保留峰值特征
- 减少每次刷新的有限值检查开销

### 2.2 Raw 图改为显示完整曲线数据

旧逻辑会对 Raw 时域图做手动 `::10` 抽样，这样虽然简单，但放大后无法恢复被丢掉的局部细节。

当前修改为：

- GUI 侧仍保持 `1 Hz` 刷新节流
- 每次刷新时直接给曲线传完整帧数据
- 曲线显示性能交给 PyQtGraph 的 `clipToView + auto downsampling`

这样做的结果是：

- 放大后可看到更真实的局部波形
- 仍保留可接受的实时绘图负载

### 2.3 Time-Space 图改为固定滚动缓冲

[`src/time_space_plot.py`](/D:/OneDrive%20-%20EVER/00_KY/DAS-%E5%99%A8%E4%BB%B6%E6%B5%8B%E8%AF%95%E3%80%81%E4%B8%8A%E4%BD%8D%E6%9C%BA%E5%BC%80%E5%8F%91/BX/PCIe-7821/pcie7821_gui/src/time_space_plot.py) 已重构为固定显示缓冲模型。

新增内部状态：

- `_display_buffer`
- `_display_block_width`
- `_display_space_count`
- `_display_block_duration_s`
- `_valid_block_count`

处理流程改为：

1. 接收一批 `frame x point` 的相位数据
2. 先做距离范围裁剪
3. 再做时间/空间下采样
4. 转为 `(space, time)` 语义的显示块
5. 追加到固定大小滚动缓冲
6. 定时合并刷新图像

### 2.4 去掉每次显示时的全量拼接

旧实现依赖 `deque + np.concatenate(...)` 在每次刷新时重建可视图像，这会随着窗口变大持续放大内存复制和 CPU 开销。

当前实现改为：

- 缓冲区未满时顺序写入
- 缓冲区写满后整体左移一个块宽度，再把新块写入右侧

因此每次更新只处理新增块和一次固定尺寸滚动，不再重复重建整个历史窗口。

### 2.5 Time-Space 图统一使用 `(space, time)` 语义

本次重构明确采用：

- 显示缓冲：`(space, time)`
- `ImageItem(axisOrder="row-major")`
- `setRect(QRectF(time_start, distance_start, time_width, distance_height))`

这样可保证：

- X 轴表示时间
- Y 轴表示空间点号
- 新数据追加在右侧
- 窗口写满后整体向左滚动

这就是参考项目里“避免滚动方向出错”的核心约束。

## 3. 运行时行为

### 3.1 Raw 图

- 仍按 `1 Hz` 节流
- 允许矩形放大后查看更多局部细节
- 不再因为 GUI 侧预抽样而提前丢失数据

### 3.2 Time-Space 图

- 只在 `PLOT` 打开且 `Tab2` 处于活动页时接收刷新
- 多次数据到达会被定时器合并，降低重绘频率
- 缓冲区满后始终向左滚动，不会再出现向下滚动的方向回归

## 4. 风险与说明

### 4.1 Raw 图性能前提

当前 Raw 图优化依赖两点同时成立：

- GUI 刷新节流为 `1 Hz`
- 曲线层使用 PyQtGraph 大曲线优化

如果后续再把 Raw 刷新频率显著提高，需要重新评估主线程负载。

### 4.2 Time-Space 图缓冲是显示缓冲

Time-Space 内部缓冲保存的是“按当前参数下采样后的显示块”，不是原始全分辨率历史数据。因此修改距离范围或下采样参数时，会主动丢弃旧缓冲并等待按新参数重建。

## 5. 总结

本次优化把 Raw 图从“固定预抽样显示”改成了“完整数据 + 绘图库自动优化”，也把 Time-Space 图从“每次全量拼接”改成了“固定滚动缓冲”。两条链路都更适合后续的实时交互放大场景，且滚动方向约束已和参考方案保持一致。
