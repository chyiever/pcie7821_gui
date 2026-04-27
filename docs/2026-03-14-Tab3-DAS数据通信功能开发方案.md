# tab3 DAS数据通信功能开发方案

日期：2026-03-14

## 1. 目标

为 `pcie7821_gui` 增加新的 `tab3“通信功能”`，使软件在作为 TCP 客户端时，能够将 PCIe-7821 采集到的 DAS 数据按照 `wb-monitor` 当前 `tab3` 接收协议实时发送到服务器端。

本次方案的目标不是做接收、绘图或定位，而是完成以下能力：

- 单独一个 `tab3` 负责通信参数配置与状态展示。
- 发送数据单位为 `rad`，且为未滤波数据。
- 只发送指定距离点范围的数据，不默认发送全量空间点。
- 支持时间、空间两个维度的降采样，默认都为 `1`。
- 页面不显示波形，只显示通信状态与统计信息。
- 软件启动后通信功能默认处于启用状态，确保一旦开始采集，从第一个采集包开始发送。
- 数据包格式与 `wb-monitor/src/das_tab3/das_tcp_server.py` 当前协议完全兼容。

## 2. 现状与约束

### 2.1 接收端协议现状

根据 `wb-monitor` 当前实现，接收端 `DASTCPServer` 采用如下固定协议：

- 包头格式：`>IIIId`
- 包头字段顺序：
  - `comm_count: uint32`
  - `sample_rate_hz: uint32`
  - `channel_count: uint32`
  - `data_bytes: uint32`
  - `packet_duration_seconds: float64`
- 包体类型：大端 `float64`
- 包体排列：按 `channel-major` 展开
  - 先发第 0 通道全部时间样本
  - 再发第 1 通道全部时间样本
  - 依次类推
- 接收端按以下规则恢复矩阵：
  - `samples_per_channel = round(sample_rate_hz * packet_duration_seconds)`
  - `matrix.shape = (channel_count, samples_per_channel)`

这意味着 7821 客户端只要严格满足上面 5 个头字段和包体展平顺序，就可以直接复用 `wb-monitor` 的现有接收逻辑。

### 2.2 当前 7821 软件的数据流现状

当前 `pcie7821_gui` 的核心采集链路是：

- `AcquisitionThread._read_phase_data()` 从板卡读取 `int32` 相位数据。
- GUI 通过 `phase_data_ready(np.ndarray, channel_num)` 接收数据。
- 当前界面中的 `rad` 转换仅用于显示：
  - `rad = int32_value / 32767.0 * π`
- 当前没有独立通信模块，没有 TCP 客户端，也没有 `comm_count` 字段。

此外，当前相位数据的组织方式是：

- 一个 GUI 回调中包含 `frame_num` 帧扫描结果。
- 每帧的空间点数为：
  - `point_num_after_merge = point_num_per_scan // merge_point_num`
- 整体可以理解为一个二维矩阵：
  - `shape = (frame_num, point_num_after_merge)`

如果要兼容 `wb-monitor` 的 DAS 接收协议，则发送前必须把它重排成：

- `shape = (channel_count, samples_per_channel)`

其中：

- `channel_count` 对应被发送的空间点数
- `samples_per_channel` 对应一个发送包中包含的时间样本数

## 3. 发送数据定义

### 3.1 推荐发送源

推荐从 `AcquisitionThread.phase_data_ready` 这一路分出通信发送数据，原因如下：

- 这里拿到的是最早的主机侧相位数据，尚未滤波。
- 当前 GUI 的 `rad` 转换就是在这一层之后完成，容易复用。
- 可以保证“从采集第一个包开始发送”，不依赖后续绘图节流。
- 不会受到 `tab1` 的显示模式切换影响。

### 3.2 推荐数据语义

发送数据采用以下语义：

- 数据类型：`float64`
- 数据单位：`rad`
- 数据内容：原始相位数据转 `rad` 后，不做滤波
- 空间裁剪：只发送用户指定的通道区间
- 时间降采样：对时间维做抽取
- 空间降采样：对空间维做抽取

推荐转换公式直接沿用当前 GUI：

```python
rad_data = int32_data.astype(np.float64) / 32767.0 * np.pi
```

## 4. 与接收协议的映射规则

### 4.1 本地二维数据重建

对于每个采集回调，先将数据重建为：

```python
frame_matrix.shape = (frame_num, point_num_after_merge)
```

若原始数组是一维，则按上式 reshape。

### 4.2 空间裁剪与降采样

在空间维上执行：

```python
selected = frame_matrix[:, channel_start:channel_end+1]
selected = selected[:, ::space_downsample]
```

然后转置为协议所需方向：

```python
send_matrix = selected.T
```

得到：

```python
send_matrix.shape = (channel_count, samples_per_channel_before_time_ds)
```

### 4.3 时间降采样

在时间维上执行：

```python
send_matrix = send_matrix[:, ::time_downsample]
```

最终：

- `channel_count = send_matrix.shape[0]`
- `samples_per_channel = send_matrix.shape[1]`

### 4.4 包头字段计算

推荐按如下规则生成包头：

- `comm_count`
  - 从一次“开始采集”起自增，从 `0` 开始
  - 每发送一个 TCP 数据包加 `1`
- `sample_rate_hz`
  - `effective_sample_rate = scan_rate / time_downsample`
- `channel_count`
  - 空间裁剪并空间降采样后的通道数
- `data_bytes`
  - `channel_count * samples_per_channel * 8`
- `packet_duration_seconds`
  - `samples_per_channel / sample_rate_hz`

由于 `sample_rate_hz` 是 `uint32`，推荐限制 `scan_rate % time_downsample == 0`，保证该值为整数，避免接收端 `round(sample_rate_hz * packet_duration_seconds)` 的恢复误差。

### 4.5 包体展开

发送前按大端 `float64` 且按通道优先展开：

```python
payload = np.asarray(send_matrix, dtype=">f8").reshape(-1, order="C").tobytes()
```

这与 `wb-monitor` 接收端 `np.frombuffer(payload, dtype=">f8")` 的预期一致。

## 5. 软件结构建议

## 5.1 新增模块

建议新增以下模块：

- `src/tcp_tab3/__init__.py`
- `src/tcp_tab3/tcp_client.py`
- `src/tcp_tab3/tcp_packet_builder.py`
- `src/tcp_tab3/tcp_sender_worker.py`
- `src/tcp_tab3/tcp_tab3_manager.py`
- `src/tcp_tab3/tcp_types.py`

### 5.2 模块职责

`tcp_client.py`

- 负责 TCP 连接、断线重连、socket 发送、状态维护。

`tcp_packet_builder.py`

- 负责把采集数据转为 `rad`
- 负责空间裁剪/时间降采样/空间降采样
- 负责组包、头字段计算、字节序转换

`tcp_sender_worker.py`

- 独立工作线程
- 从队列读取待发送帧
- 串行发送，避免阻塞 GUI 线程

`tcp_tab3_manager.py`

- 负责与主窗口、采集线程、启动停止流程对接
- 维护发送统计
- 统一处理自动启用、会话重置、错误上报

## 6. 主流程设计

### 6.1 软件启动

软件启动时：

- 初始化 `tab3` 参数控件
- 初始化 TCP 客户端管理器
- 默认将“通信启用”置为开启
- 默认加载服务器地址：
  - IP：`169.255.1.2`
  - Port：`3678`

说明：

- “通信启用”默认开启，不代表开机立刻反复发起连接；
- 推荐的行为是：管理器和发送线程提前就绪，但真正进入“持续发送”状态以“开始采集”为边界。

### 6.2 开始采集

当用户点击“开始采集”时：

- 重置发送会话状态
- `comm_count = 0`
- 清空待发送队列
- 立即发起 TCP 连接
- 从第一包 `phase_data_ready` 开始构包发送

### 6.3 采集中

每次收到 `phase_data_ready`：

1. 快速复制或引用当前采集数据
2. 投递到发送队列
3. 发送线程完成：
   - 转 `rad`
   - 选通道
   - 时间/空间降采样
   - 组包
   - 发送
   - 更新统计

### 6.4 停止采集

停止采集时：

- 停止接收新的待发送任务
- 按配置决定是否清空剩余队列后断开
- 关闭 socket
- 状态回到“空闲/未连接”

推荐默认行为：

- 停止采集后直接断开，不继续保活。

## 7. Tab3 UI 设计建议

根据你的要求，`tab3` 不显示波形，只显示通信状态与参数。

建议页面分为 4 个区块。

### 7.1 通信参数区

- 启用通信 `checkbox`
- 服务器 IP
- 服务器端口
- 自动重连 `checkbox`
- 重连间隔（秒）

### 7.2 数据裁剪参数区

- 起始通道
- 结束通道
- 时间降采样
- 空间降采样

默认值按已确认需求设置为：

- 起始通道：`50`
- 结束通道：`100`
- 时间降采样：`1`
- 空间降采样：`1`

### 7.3 采集映射信息区

只读显示：

- 当前 `scan_rate`
- 当前 `frame_num`
- 当前 `point_num_after_merge`
- 当前发送 `sample_rate_hz`
- 当前发送 `channel_count`
- 当前发送 `packet_duration_seconds`
- 当前包 `data_bytes`

### 7.4 实时状态区

- 通信状态：未启用 / 待连接 / 已连接 / 发送中 / 重连中 / 异常
- 最近错误
- 已采集包数
- 已入队包数
- 已发送包数
- 已丢弃包数
- 最近发送 `comm_count`
- 累计发送字节数
- 最近一次成功连接时间

## 8. 自动启动与容错策略

### 8.1 自动启动

你的要求是“打开软件后通信功能自动开启，确保开始采集的第一个数据包就发出去”。

推荐拆分为两层：

- 配置层：通信功能默认启用
- 运行层：采集一开始立即连接并发送

这样可以满足“首包发送”，同时避免软件刚打开但未采集时持续误报连接失败。

### 8.2 断线重连

推荐策略：

- 若已开始采集且通信启用：
  - 连接失败或发送失败后自动重连
- 重连期间允许继续接收采集数据，但发送队列长度要有限制

推荐增加：

- `max_queue_packets`
- 队列满时丢弃最旧包，而不是阻塞采集线程

原因：

- 当前采集线程是实时线程，不能因网络阻塞反压。

### 8.3 发送失败处理

推荐：

- 单次发送失败：记录错误并转入重连
- 队列积压：优先保最新数据，丢弃旧数据
- 状态区明确显示：
  - 当前是否在线
  - 是否正在丢包
  - 丢了多少发送包

## 9. 代码接入点建议

### 9.1 采集线程侧

不建议直接修改 `AcquisitionThread` 的底层读取逻辑去做 socket 发送。

建议只保留它负责：

- 读取板卡数据
- 发出 `phase_data_ready`

### 9.2 主窗口侧

在 `MainWindow` 中新增：

- `tab3` 页面
- 获取通信参数的方法，例如 `get_tab3_comm_settings()`
- 更新状态的方法，例如：
  - `update_tab3_comm_status()`
  - `update_tab3_comm_statistics()`
  - `update_tab3_comm_error()`

### 9.3 应用控制层

建议在 `src/main.py` 中增加 `TCPTab3Manager`，并在以下时机接入：

- 软件初始化时创建
- `MainWindow._on_start()` 前后同步参数
- `phase_data_ready` 信号连接到 `TCPTab3Manager.enqueue_phase_packet`
- `MainWindow._on_stop()` 时停止发送与断线

如果后续希望结构更清晰，也可以把当前单体 GUI 架构逐步演进为：

- `MainWindow` 只做界面
- `AppController` 负责采集、存储、通信三条链路的编排

但本次开发不建议顺带大重构。

## 10. 开发计划

### 阶段 1：方案固化与文档更新

- 固化协议字段、启停策略、默认值、约束条件
- 将“待确认项”转为“已确认实现规则”
- 明确测试范围与失败处理策略

### 阶段 2：协议与发送核心

- 新建发送数据结构与组包器
- 完成大端包头和大端 `float64` 包体发送
- 完成后台发送线程、队列与 socket 生命周期管理
- 编写本地回环或接收端联调验证

### 阶段 3：采集链路接入

- 在 `phase_data_ready` 路径上接入发送管理器
- 以采集开始/停止为会话边界管理 `comm_count`
- 加入自动连接和断线重连
- 仅在 `upload.channel_num == 1` 且 `data_source == PHASE` 时允许启动通信

### 阶段 4：UI 与状态

- 完成 `tab3` 状态页
- 展示统计项与错误信息
- 支持参数动态修改
- IP/端口修改在下一个连接周期生效

### 阶段 5：联调验证

- 与 `wb-monitor` 真机联调
- 验证首包发送
- 验证裁剪范围与降采样结果
- 验证断线重连与接收端恢复

## 11. 联调验证项

建议至少覆盖以下验证：

### 11.1 协议正确性

- `wb-monitor` 能正常解析包头
- `data_bytes` 与实际长度一致
- `matrix.shape` 恢复正确

### 11.2 数据正确性

- 同一采集段内，发送前本地矩阵与接收端恢复矩阵一致
- `rad` 单位换算正确
- 通道裁剪边界正确
- 时间降采样、空间降采样结果正确

### 11.3 时序正确性

- 从开始采集后的第一个回调即开始发送
- `comm_count` 连续递增
- 停止采集后 `comm_count` 在下一次采集时从 `0` 重新开始

### 11.4 异常正确性

- 服务器未启动时客户端状态显示正确
- 网线拔掉后进入重连
- 恢复连接后继续发送
- 队列积压时不会拖慢采集线程

## 12. 风险与注意事项

### 12.1 当前 7821 软件没有原生 `comm_count`

因此本项目内的 `comm_count` 只能由发送模块在“采集会话”内自行生成，不能从硬件协议直接继承。

### 12.2 `sample_rate_hz` 必须是整数

由于接收端头字段定义为 `uint32`，如果时间降采样不能整除 `scan_rate`，协议会出现歧义。

### 12.3 `frame_num` 影响每包时长

当前每次 `phase_data_ready` 回调对应的时间长度与 `frame_num / scan_rate` 直接相关。若运行中允许修改 `frame_num`，发送端必须同步更新包头。

### 12.4 merge 后的空间点是否就是“通道”

该项已确认：

- 当前通信协议里的“通道”直接定义为 `merge` 之后的空间点。
- 当前 `tab2` 时空图的数据组织也是：
  - 第一维为时间
  - 第二维为距离点/空间点
- 因此通信发送前的本地矩阵可以稳定定义为：
  - `shape = (frame_num, point_num_after_merge)`
- 发送时再转为协议要求的：
  - `shape = (channel_count, samples_per_channel)`

### 12.5 板卡多上传通道与协议通道的歧义

该项已确认处理策略：

- 只有 `upload.channel_num == 1` 时，通信功能才允许启动。
- 当 `upload.channel_num != 1` 时，通信功能不可启动，UI 应提示原因。
- 因此本次实现中，协议里的 `channel_count` 只表示空间点数，不表示板卡硬件上传通道数。

## 13. 已确认的技术细节

以下细节已确认，可直接进入实现。

### 13.1 服务器 IP 与端口

- 默认服务器 IP：`169.255.1.2`
- 默认端口：`3678`
- IP/端口在采集中修改时，不立即打断当前连接，而是在下一个连接周期生效。

### 13.2 “通道”的准确含义

- `merge` 之后的每个空间点，就是发送协议里的一个 `channel`。
- 与当前 `tab2` 中时空图的“距离点/空间点”含义一致。

### 13.3 默认发送范围

- 默认发送范围采用固定区间：
  - `50 ~ 100`

### 13.4 时间降采样约束

- `time_downsample` 必须整除 `scan_rate`
- 默认 `time_downsample = 1`

### 13.5 停止采集后的连接策略

- 停止采集后断开 TCP 连接
- 下次开始采集时重新连接并从 `comm_count=0` 开始

### 13.6 断线期间的队列策略

- 队列有限长
- 满了以后丢弃最旧包，保留最新包
- 线程设计要求：
  - 通信不得占用主线程
  - 不得阻塞采集线程
  - 应使用独立后台发送线程与有限队列

### 13.7 是否允许运行中修改通信参数

- 服务器 IP/端口修改后，下一个连接周期生效
- 数据参数修改后，对后续新包立即生效

### 13.8 是否增加“通信启用”总开关

- `tab3` 保留“通信启用”总开关
- 默认打开

### 13.9 启动条件限制

只有同时满足以下条件，通信功能才允许启动：

- `upload.channel_num == 1`
- `upload.data_source == PHASE`

否则：

- 采集功能仍可正常运行
- 但通信功能不启动
- `tab3` 状态区明确提示不可启动原因

## 14. 结论

该功能可以在当前 `pcie7821_gui` 架构内以“新增独立发送链路”的方式实现，无需重写采集线程。最稳妥的接入点是 `phase_data_ready` 信号之后、GUI 显示之前。这样既能保证：

- 发送的是未滤波相位数据
- 单位可统一转为 `rad`
- 从采集第一包开始发送
- 不影响现有显示和存储逻辑

已无需再等待关键需求确认，可以按第 10 节开发计划直接进入编码实现。
