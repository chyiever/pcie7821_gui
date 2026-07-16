# Development Log

本文档用于记录程序每次更新的背景、修改范围、验证情况，以及与 Git 分支和提交对应的发布信息。考虑到本项目已经历多轮围绕采集吞吐、GUI 实时性、数据保存和 Time-Space 绘图的修正，日志不再只记录零散要点，而是尽量把每次修改背后的原因、涉及模块和验证边界说清楚，方便后续维护者快速理解“为什么要这样改”。

记录规则如下：

- 每次功能修改、修复或结构调整后，都在本文档末尾追加新记录。
- 记录中尽量写清楚更新时间、修改背景、涉及文件、验证方式和风险边界。
- 如果代码已经推送到远端分支，需要同时写明分支名和提交号，便于后续追踪。
- `data`、`dist` 等运行产物不在本日志的代码更新范围内，除非单独说明。

## 2026-06-13

### 本次工作的目标

本次更新没有改变主采集逻辑，重点是根据当前代码实况系统性整理开发文档、用户文档和模块文件头注释，同时清理 `src` 目录中的运行产物，降低后续维护者阅读和误判成本。由于项目经历过多轮性能修订，旧文档中已经出现“说明语义落后于代码”的情况，例如早期将显示链路与保存链路混写、把 `FrameLoad` 解释得过于接近硬件参数、以及 Time-Space 文档仍偏向旧实现路径。本次工作就是把这些说明重新拉回到当前版本代码之上。

### 主要修改内容

首先，重写了根目录 `README.md`，使其定位从“泛化项目说明”转为“面向开发者的架构文档”。新版文档围绕模块职责、线程分工、完整数据与显示快照分离、`FrameLoad/FramePlot` 语义、Time-Space 设计、保存链路和 TCP 通信链路进行展开，重点让后来者能够快速建立一张和当前代码一致的系统图，而不是只看到功能列表。

其次，重写了 `user_read.md`。新版用户文档不再只解释个别参数，而是把启动方式、界面区域、关键参数、调参顺序、保存注意事项、Tab3 通信限制和 STOP 行为串成完整的现场使用路径。这样做的目的，是让用户在不深入阅读源码的前提下，也能理解哪些参数影响底层吞吐，哪些参数只影响显示。

第三，重写了 `docs/README-2026-03-20-eDAS数据存储技术说明.md` 和 `docs/README-2026-02-26-Time-Space-Plot技术架构文档.md`。前者现在以当前版本的 `FrameBasedFileSaver`、采集线程裁剪逻辑和完整块直达保存器设计为基线，明确区分保存值、显示值和底层设备值；后者则以现有 `PlotWidget + ImageItem + HistogramLUTWidget + ZoomablePlotViewBox` 架构为中心，解释滚动显示缓冲、颜色范围稳定性和缩放锁定的真实实现意图。

第四，统一补充并更新了 `src` 下各主要 Python 模块的文件级说明。新的文件头不再停留在“本模块是做什么的”这一层，而是补充了模块在整体架构中的位置、与其他模块的边界以及当前版本最重要的实现约束。对 `main_window.py`、`acquisition_thread.py`、`data_saver.py`、`time_space_plot.py` 和 `tcp_tab3` 子模块来说，这一步尤其重要，因为这些文件是当前项目复杂度和后续误改风险最高的部分。

最后，检查 `src` 目录后，确认没有独立的测试源码或明显失效的业务模块。真正属于运行产物、而不应继续留在源码目录中的，是 `src/__pycache__` 和 `src/tcp_tab3/__pycache__` 两个目录。本次已将它们移动到 `other_files/src_runtime_artifacts/` 下归档，避免后续阅读源码时把缓存文件误当作工程组成部分。

### 涉及文件

- `README.md`
- `user_read.md`
- `dev_log.md`
- `docs/README-2026-03-20-eDAS数据存储技术说明.md`
- `docs/README-2026-02-26-Time-Space-Plot技术架构文档.md`
- `src/__init__.py`
- `src/main.py`
- `src/main_window.py`
- `src/config.py`
- `src/pcie7821_api.py`
- `src/acquisition_thread.py`
- `src/data_saver.py`
- `src/logger.py`
- `src/spectrum_analyzer.py`
- `src/time_space_plot.py`
- `src/plot_interaction.py`
- `src/tcp_tab3/__init__.py`
- `src/tcp_tab3/tcp_types.py`
- `src/tcp_tab3/tcp_packet_builder.py`
- `src/tcp_tab3/tcp_sender_worker.py`
- `src/tcp_tab3/tcp_tab3_manager.py`
- `other_files/src_runtime_artifacts/`

### 验证与自检要求

本次修改以注释和 Markdown 文档为主，因此验证重点放在三类检查上。第一，所有被改写的源码和文档文件都必须能够以 `encoding='utf-8'` 正常读取，不能出现问号占位符或替换字符造成的乱码。第二，文档中的描述必须和当前代码职责一致，尤其是完整数据与显示快照分离、单通道 PHASE 裁剪进入保存与通信链路、以及 Time-Space 控件采用固定滚动显示缓冲等关键点。第三，源码修改仅限文件头说明，不得顺带改变运行逻辑。

关于 Git 发布信息，本次记录先保留“待提交”状态；提交号和远端分支信息将在完成本地自检并推送后补入或在后续记录中补充。

## 2026-04-29

### 更新日志

- 已将当前版本程序上传到 GitHub `dev` 分支。
- 本次远端对应提交为 `f824295`。
- 提交信息为：`完善图形交互并更新绘图与参数持久化`。

### Git 记录

- 本地分支：`dev`
- 远端分支：`origin/dev`
- 提交号：`f824295`
- 说明：该提交承载了当前阶段的 `src`、`docs` 以及相关说明文件更新，可作为后续联调和合并前检查的基线版本。

### 更新内容

- 为 `Tab1` 三个实时图和 `Tab2` Time-Space 图统一接入矩形放大、滚轮缩放、`Shift + 左键` 水平平移和右键 `View All`。
- 为主窗口新增缩放锁定逻辑，解决实时刷新时手动放大视图被自动范围覆盖的问题。
- 优化 Raw 曲线绘图方式，改为完整数据 + PyQtGraph 自动裁剪/自动抽样，减少放大后细节丢失。
- 重构 Time-Space 绘图链路，改为固定滚动显示缓冲，去掉每次刷新的全量拼接。
- 明确 Time-Space 图显示语义为 `(space, time)`，并固定新数据右侧追加、窗口写满后向左滚动，避免滚动方向回归。
- 新增本地参数自动保存与恢复，启动前和关闭时写入 `last_params.json`，启动时自动恢复。
- 将 `Waveform` 与 `Monitor` 显示开关纳入本地参数持久化。
- 增加 `last_params.json` 的 `.gitignore` 规则，避免本地运行态文件进入版本控制。
- 补充 4 份本次修订技术文档，更新 `README.md`，并建立本 `dev_log.md` 作为持续维护日志。

### 涉及文件

- `src/main_window.py`
- `src/time_space_plot.py`
- `src/plot_interaction.py`
- `src/config.py`
- `docs/2026-04-28-添加GUI矩形放大交互功能.md`
- `docs/2026-04-28-raw和timespace绘图优化.md`
- `docs/2026-04-28-本地参数自动保存与恢复.md`
- `docs/2026-04-28-Monitor与Phase时域绘图开关控制.md`
- `README.md`
- `.gitignore`
- `dev_log.md`

### 验证情况

- 已通过 `python -m py_compile` 对关键源码进行语法检查。
- 已完成仿真模式 GUI 行为清单核查。
- 仿真核查覆盖内容包括：
  - 主窗口启动
  - `PHASE`/`RAW` 数据源切换
  - `Waveform`/`Monitor` 显示开关
  - 普通图与 Time-Space 图的缩放锁定和恢复
  - Time-Space 固定滚动缓冲与滚动方向
  - 本地参数保存与恢复

### 备注

- `f824295` 是当前阶段推荐的联调基线版本。
- 后续如果在 `dev` 分支继续修改，应在下一条记录中明确写出新的提交号，避免多个阶段共用同一条描述。

## 2026-04-28

### 更新日志

- 完成图形交互、绘图优化、参数持久化和显示开关控制的首轮实现。
- 同步补充本次修订技术文档。

### 更新内容

- 为 `Tab1` 三个实时图和 `Tab2` Time-Space 图统一接入矩形放大、滚轮缩放、`Shift + 左键` 水平平移和右键 `View All`。
- 为主窗口新增缩放锁定逻辑，解决实时刷新时手动放大视图被自动范围覆盖的问题。
- 优化 Raw 曲线绘图方式，改为完整数据 + PyQtGraph 自动裁剪/自动抽样，减少放大后细节丢失。
- 重构 Time-Space 绘图链路，改为固定滚动显示缓冲，去掉每次刷新的全量拼接。
- 明确 Time-Space 图显示语义为 `(space, time)`，并固定新数据右侧追加、窗口写满后向左滚动，避免滚动方向回归。
- 新增本地参数自动保存与恢复，启动前和关闭时写入 `last_params.json`，启动时自动恢复。
- 将 `Waveform` 与 `Monitor` 显示开关纳入本地参数持久化。
- 增加 `last_params.json` 的 `.gitignore` 规则，避免本地运行态文件进入版本控制。

### 涉及文件

- `src/main_window.py`
- `src/time_space_plot.py`
- `src/plot_interaction.py`
- `src/config.py`
- `.gitignore`
- `README.md`
- `docs/*.md`

### 说明

- `last_params.json` 属于本地缓存参数文件，不应纳入仓库。
- 本日志后续应持续追加，不建议覆盖历史记录。

## 2026-05-06

### 更新日志

- 基于 `log-20260505.txt`、`log-20260505-2.txt`、`log-20260506-1.txt` 完成大数据量采集死机问题定位与代码修复。
- 新增分析文档：`docs/2026-5-5-大数据量采集死机问题分析与解决.md`。

### 问题定位结论

- 运行期问题：采集线程会在长时间高负载后停摆/阻塞，主线程仍存活（表现为长期 `Storage queue: 0/200`）。
- 停机与复启问题：异常停止后存在设备/驱动状态残留风险，可能导致复启无波形。

### 代码优化

- `src/acquisition_thread.py`
  - 将 `stop()` 改为非阻塞停止请求。
  - 新增 `wait_until_stopped()`，只等待，不再强制 `terminate()`。

- `src/main_window.py`
  - 调整停止与关闭流程顺序：请求线程停 -> `api.stop()` -> 等待线程退出。
  - 去除线程强杀路径，降低驱动状态污染风险。
  - 新增运行期采集卡死检测与自动恢复：
    - `ACQ_STALL_TIMEOUT_S = 8.0`
    - `ACQ_RECOVERY_COOLDOWN_S = 20.0`
    - 无数据超时触发 `STOP -> 延时 -> START` 自动恢复。

### 验证

- 已通过：`python -m py_compile src\acquisition_thread.py src\main_window.py`
- 待继续观察：长时（>10分钟）大数据量采集下自动恢复成功率与稳定性。

## 2026-05-11

### 更新日志

- 基于最新测试日志 `logs/log-20260506-1.txt`，补充大数据量采集死机原因分析，并在关键数据流节点增加详细日志埋点。
- 新增原因分析文档：`docs/2026-5-11-大数据量采集软件死机原因分析.md`
- 新增 20 km / 4 kHz 场景采集参数建议：`docs/2026-5-11-20km采集参数建议.txt`

### 问题分析结论

- 当前主要风险点仍在底层采集链路，而不是存储队列。
- `FrameLoad=4000` 时单次 `PHASE` 读数块约 `102.4 MB`，明显过大，极易放大 DLL / 驱动阻塞风险。
- `STOP` 卡在 `pcie7821.api : Stopping acquisition...`，高度怀疑采集线程已先卡在 DLL 调用内，主线程再调用 `api.stop()` 时被同一把锁或同一底层状态拖住。

### 本次代码修改

- `src/acquisition_thread.py`
  - 增加采集线程内部阶段追踪：等待缓冲区、查询点数、读数、读 monitor、发信号、停止请求等。
  - 增加诊断快照接口，记录最近一次缓冲区点数、查询耗时、读数耗时、块大小、阶段停留时长。
  - 增加单块大小、单块时长、发信号次数、GUI 节流跳过次数等日志。

- `src/main_window.py`
  - 启动时记录 `FrameLoad / FramePlot / block_bytes / block_duration`。
  - 在 `_on_phase_data` 中拆分记录 TCP 入队、保存入队、rad 转换、显示更新耗时。
  - 在 `_on_raw_data` 中增加保存与显示拆分耗时日志。
  - 增加周期性 `Acq snapshot` 汇总日志，并在检测到 stall 或手动 STOP 前强制输出一次。

- `src/data_saver.py`
  - 增加保存队列入队日志、历史最大队列长度、最后一次写盘耗时和写盘字节数。
  - 当队列满或写盘过慢时输出告警。

- `src/tcp_tab3/tcp_sender_worker.py`
  - 增加 TCP 队列丢包、慢打包、慢发送日志。

### 涉及文件

- `src/acquisition_thread.py`
- `src/main_window.py`
- `src/data_saver.py`
- `src/tcp_tab3/tcp_sender_worker.py`
- `src/config.py`
- `src/tcp_tab3/tcp_tab3_manager.py`
- `docs/2026-5-5-大数据量采集死机问题分析与解决.md`
- `docs/2026-5-11-大数据量采集软件死机原因分析.md`
- `docs/2026-5-11-20km采集参数建议.txt`
- `dev_log.md`

### 验证

- 在 `LZdataread39` 环境下完成源码语法编译检查：
  - 通过内置 `compile(...)` 对 `run.py`、`src/main.py`、`src/logger.py`、`src/acquisition_thread.py`、`src/data_saver.py`、`src/main_window.py`、`src/tcp_tab3/tcp_sender_worker.py` 进行检查。
- 已验证命令参数解析正常：
  - `python run.py --help`
- 已验证调试日志参数链路可用：
  - `python run.py --simulate --debug --log debug.log`
  - 已成功创建 `debug.log`

### 现场测试建议

- 首轮稳定性测试建议使用：
  - `ScanRate=4000`
  - `Points=51200`
  - `MergePointNum=8`
  - `FrameLoad=512`
  - `FramePlot=128`
- 若仍异常，优先继续降低 `FrameLoad`，而不是先扩大显示或通信负载。

## 2026-06-06

### 问题背景与日志结论

本次针对单通道 Raw 数据在 `ScanRate=2000`、`Points=20480`、`FrameLoad=1024`、`FramePlot=1024` 条件下出现的时域波形更新卡顿和 STOP 响应延迟进行了专项优化。现场日志表明，每个 Raw 读取块大小为 $40\ \mathrm{MiB}$，对应采集时间仅为 $512\ \mathrm{ms}$，但实际单次读取经常耗时 $1.2$ 至 $4.6\ \mathrm{s}$。驱动缓冲区点数因此持续增长，说明底层读取链路无法及时消费持续产生的数据。

日志同时显示，采集线程在点击 STOP 后通常约几十毫秒内已经退出，但 GUI 收到 `acquisition_stopped` 信号会延迟约 $4.6$ 至 $4.8\ \mathrm{s}$。原有的 50 ms 信号发送节流在单次读取耗时超过 50 ms 时不会跳过任何数据，导致每个完整的 $40\ \mathrm{MiB}$ Raw 数组都进入 Qt 主线程事件队列。停止信号与这些历史数据回调、绘图事件处于同一个事件队列中，因此用户看到的停止延迟主要来自 GUI 队列积压，而不是本次日志中的硬件停止调用。

### 数据通路重构

本次将完整数据处理和实时显示处理拆分为两条独立通路。采集线程读取完整数据块后，会直接调用非 GUI 的完整数据处理器，将完整数据送入线程安全的保存队列；Phase 数据还会进入 TCP 后台发送队列。完整数据不再通过 Qt 大数组信号进入 GUI 主线程，因此保存和通信仍可使用完整分辨率数据，而 GUI 不再承担完整采集块的排队和释放压力。

显示通路改为“单槽最新快照”模型。采集线程依据 `FramePlot` 从完整数据块中截取最新帧，并复制成独立、连续的 NumPy 显示快照。该快照存放在一个可覆盖槽位中；如果 GUI 尚未消费旧快照，新快照会替换旧快照并增加跳过计数。GUI 使用 100 ms 定时器主动取走最多一个最新快照，再执行时域、频谱或 Time-Space 显示。该结构保证 GUI 始终优先显示最新数据，不会因处理历史数据而不断增加延迟。

### 停止流程与停滞检测

STOP 流程现在会先恢复界面控件状态、请求采集线程停止并清理未消费显示快照，再停止硬件并等待线程退出。停止完成后，主窗口会清除当前采集线程引用，因此状态定时器不会继续打印已停止线程的周期性采集快照。`acquisition_stopped` 信号处理增加了来源检查，旧采集线程延迟到达的停止信号会被忽略，避免自动恢复或快速重新启动后，旧信号错误地禁用新一轮采集界面。

停滞检测依据从 GUI 回调时间改为采集线程最近一次成功读取时间。采集线程诊断快照新增 `last_successful_read_age_s`，主窗口使用该字段判断底层读取是否真正停滞。这样可以避免 GUI 绘图繁忙时，因主线程未及时处理显示回调而错误触发自动 stop/start。

### 参数文档与文字编码

新增 `user_read.md`，详细说明 `FrameLoad` 和 `FramePlot` 的含义、计算公式、调整方式以及优化后的数据流。文档明确指出，`FrameLoad` 是上位机每次从 DLL 缓冲区批量读取的帧数，不是直接下发到 FPGA 的硬件参数；`FramePlot` 是显示侧最多使用的最新帧数，不改变持续采集数据率。

本次同时修正了 `src/config.py` 中将 `FrameLoad` 描述为“从 FPGA 读取”的不准确注释，并修复了 `src/main_window.py` 中若干包含乱码问号的历史注释和占位显示文字。所有新增和修改的中文文档均按 UTF-8 进行自检，公式统一使用 `$...$` 或 `$$...$$` Markdown 数学格式。

### 涉及文件

本次核心代码修改涉及 `src/acquisition_thread.py`、`src/main_window.py` 和 `src/config.py`。用户说明新增于 `user_read.md`，开发过程和验证结果记录于 `dev_log.md`。

### 验证要求

代码修改后执行 Python 语法编译检查、模拟采集线程检查、UTF-8 中文自检和 Git 差异检查。现场硬件验证时，应重点比较优化前后的 `read_ms`、`query_ms`、`read_age_s`、`gui_skips`、驱动缓冲区点数和 STOP 响应时间，并从较小的 `FrameLoad` 与 `FramePlot` 组合开始逐步增加负载。

### 本地验证结果

本次已通过 `python -m py_compile` 对入口文件、配置、采集线程、主窗口、PCIe API、保存模块以及 TCP 管理和发送模块执行语法编译检查。Raw 与 Phase 模拟采集线程测试均验证了完整数据处理器能够持续接收全部采集块，显示槽只保留最新的 `FramePlot` 帧，并且停止请求后线程能够正常退出。模拟测试还确认，在 GUI 未及时消费显示快照时，旧快照会被覆盖并增加 `gui_skips`，不会形成无上限队列。

UTF-8 中文自检使用 Python 以 `encoding='utf-8'` 读取本次涉及的代码和文档文件，确认所有文件均可正常解码，Unicode 替换字符和 ASCII 问号计数均为零。`git diff --check` 未发现空白错误，`python run.py --help` 参数检查通过。由于当前执行环境未安装 `pyqtgraph`，主窗口离屏 START/STOP 烟雾测试无法导入 `src/main_window.py`，该项需要在安装完整 `requirements.txt` 依赖的现场环境中继续验证。

### Space-Time 颜色范围与最新日志优化

根据 `logs/log--20260606-2.txt` 完成第二轮检查，并新增分析文档 `docs/2026-06-06-Space-Time颜色范围与最新日志分析.md`。Space-Time 颜色范围无法保持的问题来自显示更新过程中重复调用 `HistogramLUTWidget.setImageItem()`，该调用会重新初始化 Histogram 与图像的关联并可能触发自动范围行为。本次取消更新阶段的重复绑定，颜色 levels 改为由前面板 `vmin/vmax` 唯一控制，颜色条 level 区域禁止拖动，并将输入精度提高到六位小数。

Space-Time 参数恢复改为原子设置 `vmin/vmax`，避免依次设置时因临时非法范围导致参数被修改。显示缓冲写满后不再为完整有效区域额外创建连续副本；尚未写满时仍保留必要的连续化复制。当前滚动缓冲写满后的整块移动仍是后续可优化项，但最新日志中显示更新时间通常只有约 $2\ \mathrm{ms}$，暂未构成主要瓶颈。

最新日志显示上一轮 GUI 最新快照和停止流程优化已经生效，Raw GUI 回调通常只需要约 $2$ 至 $4\ \mathrm{ms}$，采集线程 STOP 延迟约为数毫秒至一百多毫秒。剩余主要问题包括 Raw DLL 读取在相同参数的不同启动轮次中表现差异明显、Phase 全块弧度转换占用约 $50$ 至 $70\ \mathrm{ms}$ 主线程时间，以及磁盘空间耗尽后保存线程持续重复报错。

本次将 Phase 显示弧度转换从 `float64` 改为 `float32` 原位乘法，以降低临时内存和主线程转换开销。

采集线程的慢循环警告阈值改为根据数据块正常周期计算，只有循环耗时超过 $\max(100\ \mathrm{ms}, 1.5 \times T_{\mathrm{block}})$ 时才告警，避免 `FrameLoad=2000` 时正常约一秒的数据块等待被持续误报为慢循环。

### 磁盘写满自动恢复历史修改

该阶段曾将保存线程的磁盘空间耗尽处理改为可恢复状态机。此修改随后根据现场要求回退，不再代表当前保存行为。

历史实现曾每隔约 $2\ \mathrm{s}$ 尝试创建下一个编号文件并恢复写入，并可能保留连续编号的 `0 KB` 文件。当前版本已经移除此状态机。

## 2026-06-06 当前版本发布

## 2026-06-14

### 本次工作目标

本次更新围绕 Windows 可交付版本打包链路展开，目标是让 `PCIe-7821` 上位机在脱离本地 Python 环境后仍然保持与源码运行一致的行为。重点包括四部分：一是补齐独立的 `build_exe.py` 打包脚本；二是保证 exe 启动后默认沿用上次保存的参数；三是增加默认日志落盘并支持长时间运行时按天切分日志文件；四是修复 PyInstaller `onefile` 模式下资源文件、DLL、页头 logo、窗口图标和任务栏图标之间的路径与显示不一致问题。

### 主要修改内容

首先，新建了根目录打包脚本 `build_exe.py`，参考另一个 `pcie7825_gui` 项目的构建方式，统一封装 PyInstaller 调用、资源收集、隐藏导入、无关模块排除、运行时参数文件复制以及打包完成后的清理动作。脚本现在默认生成以日期命名的可执行文件，格式为 `eDASYY.M.D.exe`，例如 `eDAS26.6.14.exe`。同时，脚本在打包完成后会自动删除 `build/` 目录，减少中间产物残留。

其次，确认并保留了现有的本地参数持久化机制。`src/main_window.py` 中的 `last_params.json` 读写逻辑已经具备“退出时保存、下次启动恢复”的能力，本次重点是确保该逻辑在冻结后的 exe 环境中仍然成立。因此打包脚本会在输出 exe 后，将 `last_params.json` 复制到 `dist/` 目录，冻结版本继续按 exe 同目录读写配置。

第三，扩展了日志系统。`src/logger.py` 增加了按日切换的文件处理器，默认日志目录固定为 `D:/eDAS-log`。`src/main.py` 调整后，在未显式传入 `--log` 时也会自动启用文件日志；日志文件名按启动时间生成，长时间运行跨天后自动切到新的日期文件，避免单文件无限增长。

第四，修复了 `onefile` 模式下的资源路径问题。现场日志显示，冻结后的程序曾在临时解包目录中找不到 `resources/logo.png` 和 `libs/pcie7821_api.dll`。为此，`src/pcie7821_api.py` 增加了对 `sys._MEIPASS` 与 exe 邻近目录的 DLL 搜索；`src/main_window.py` 与 `src/main.py` 则统一增加了 bundle 根目录解析逻辑，确保冻结版本优先从 PyInstaller 临时解包资源目录读取图片与图标。

第五，拆分了“页头显示 logo”和“窗口/任务栏图标”的资源来源。根据最终 UI 要求，页面左上角页头 logo 继续使用 `resources/logo.png`，窗口标题栏左上角图标、任务栏图标以及 exe 文件嵌入图标使用 `resources/eDAS-LOGO.png`。为此，`src/main_window.py` 新增了独立的 `get_header_logo_path()` 与窗口图标路径选择逻辑；`src/main.py` 则在 `QApplication` 级别显式设置窗口图标，并在 Windows 下设置 `AppUserModelID`，降低任务栏图标与文件图标不一致的概率。

第六，打包脚本新增了图标转换步骤。由于 PyInstaller 的 exe 图标嵌入更适合 `.ico`，当前脚本会在打包时用 Pillow 将 `resources/eDAS-LOGO.png` 转换为临时 `.ico` 文件，再通过 `--icon` 参数写入可执行文件。

### 涉及文件

- `build_exe.py`
- `requirements.txt`
- `src/logger.py`
- `src/main.py`
- `src/main_window.py`
- `src/pcie7821_api.py`
- `resources/eDAS-LOGO.png`
- `dev_log.md`

### 验证与结果

本次修改后，已使用 `python -m py_compile` 对 `build_exe.py`、`src/main.py`、`src/main_window.py`、`src/logger.py`、`src/pcie7821_api.py` 等关键文件完成语法检查。随后多次执行 `python build_exe.py` 验证打包链路，成功输出冻结版本 exe，并确认：

- exe 默认命名符合日期格式要求；
- 打包结束后 `build/` 目录会自动删除；
- `dist/` 中会同步复制 `last_params.json`；
- `onefile` 模式下资源和 DLL 路径不再依赖源码目录；
- exe 文件图标来自 `resources/eDAS-LOGO.png`；
- 页头大 logo 与窗口/任务栏图标可以分离配置。

最终产物已验证生成 `dist/eDAS26.6.14.exe`。关于 Windows 资源管理器图标与任务栏图标偶发不一致的问题，本次代码已尽量从 exe 资源、Qt 应用图标和 `AppUserModelID` 三层统一；若现场仍见旧图标，优先判断为 Windows 图标缓存或旧快捷方式缓存，需要通过重新固定任务栏或刷新 `explorer.exe` 进一步验证。

## 2026-06-17 Tab1 时域图坐标轴修改

### 本次工作目标

本次根据现场显示语义要求，修正 Tab1 Time Plot 时域图横轴。此前曲线更新只传入 y 数据，pyqtgraph 默认使用 0 基样本序号作为横轴；修改后按 Raw、Phase-Time、Phase-Space 三种情况显式生成物理坐标数组，并随模式自动更新横轴标签。

### 主要修改内容

Raw 模式下时域图横轴改为 `Distance (m)`，坐标数组按 $x=[1,2,\ldots,\mathrm{Points}] \times 0.1 \times \mathrm{DataRate}$ 生成。`DataRate=4ns (250MHz)` 时点间距为 $0.4\ \mathrm{m}$，`DataRate=8ns (125MHz)` 时点间距为 $0.8\ \mathrm{m}$。

Phase 模式且 `Mode=time` 时，横轴同样改为 `Distance (m)`，坐标数组按 $x=[1,2,\ldots,\lfloor\mathrm{Points}/\mathrm{Merge}\rfloor] \times 0.4 \times \mathrm{Rate2phase} \times \mathrm{Merge}$ 生成。例如 `Rate2phase=250M` 且 `Merge=20` 时，点间距为 $8\ \mathrm{m}$。

Phase 模式且 `Mode=space` 时，横轴改为 `Time (s)`，坐标数组按 $x=[1,2,\ldots,frame\_num]/\mathrm{Scan}$ 生成；稳定显示时 `frame_num` 通常等于 `FramePlot`。例如 `Scan=2000Hz` 时，点间距为 $0.0005\ \mathrm{s}$。

### 涉及文件

- `src/main_window.py`
- `docs/2026-6-17-tab1时域图坐标轴修改日志.md`
- `dev_log.md`

### 验证要求

本次需要执行 Python 语法检查、坐标公式自检、UTF-8 中文自检和 Git 差异检查。现场联机验证时重点确认 Raw 的 `DataRate` 切换、Phase-Time 的 `Rate2phase` 与 `Merge` 联动，以及 Phase-Space 的 `Scan` 时间刻度是否与界面参数一致。

## 2026-06-17 Phase Space 时域波形不可见修复

### 问题原因

Phase 模式下 `Mode=space` 的数据抽取逻辑本身可以生成 `space_data`，上一轮坐标轴修改后也会生成秒级时间轴 $x=[1,2,\ldots,frame\_num]/\mathrm{Scan}$。实际无法显示波形的主要原因是 Tab1 的 ViewBox 在手动框选、平移或滚轮缩放后会关闭自动范围；当横轴从 `Distance (m)` 的米级范围切换到 `Time (s)` 的秒级范围时，旧视图范围仍然保留，新曲线落在可见范围之外。

### 修复内容

本次在 `src/main_window.py` 中增加 `_time_plot_axis_kind` 状态和 `_set_time_plot_axis()` 方法，用于统一处理 Tab1 时域图横轴标签与横轴语义切换。当横轴类型在 `distance` 与 `time` 之间变化时，程序会清空旧曲线、解除 `plot1` 缩放锁定并恢复自动范围。`_on_mode_changed()` 也同步调用该方法，使用户切换 `Time/Space` 单选按钮后，下一帧 Phase-Space 波形可以直接显示在秒级时间轴范围内。

### 文档更新

已更新 `docs/2026-6-17-tab1时域图坐标轴修改日志.md`，补充 Phase Space 模式波形不可见的原因分析、修复方案和流程图。

### 验证要求

本次需要继续执行 `python -m py_compile src/main_window.py`、坐标公式自检、横轴切换自动范围自检、UTF-8 中文自检和 `git diff --check`。现场验证时应先在 `Mode=time` 下缩放 Tab1，再切换到 `Mode=space`，确认横轴变为 `Time (s)` 后波形仍能自动出现在视图范围内。

## 2026-06-17 Tab1 横轴切换自动范围二次优化

### 问题原因

现场进一步验证发现，Phase 模式下从 `Mode=time` 切换到 `Mode=space` 后，有时仍需要先在绘图控件中画一个矩形放大，再点击自动范围按钮，波形才会出现；从 `Mode=space` 切回 `Mode=time` 后也可能需要手动点击自动范围按钮。原因是上一轮修复只在模式切换瞬间调用 `_restore_plot_auto_range()`。此时旧曲线刚被清空，新模式对应的 `setData(x, y)` 尚未执行，ViewBox 没有新横轴数据边界可用于计算范围。

### 修复内容

本次在 `src/main_window.py` 中增加 `_time_plot_pending_auto_range` 状态和 `_apply_pending_time_plot_auto_range()` 方法。横轴类型在 `distance` 与 `time` 之间切换时，程序先清空旧曲线、解除缩放锁定，并设置 pending 标记；随后在 Phase-Space、Phase-Time 和 Raw 分支完成新曲线 `setData(x, y)` 后，再执行一次 `_restore_plot_auto_range()`。这样自动范围计算发生在新数据写入之后，等效于程序自动完成一次 `Auto/View All`，避免用户手动画矩形或手动点击自动范围按钮。

### 文档更新

已更新 `docs/2026-6-17-tab1时域图坐标轴修改日志.md` 的第 7 节，补充二次优化原因、两阶段自动范围恢复流程和对应公式化流程说明。

### 验证要求

本次需要执行 `python -m py_compile src/main_window.py`、横轴切换 pending 自动范围自检、坐标公式自检、UTF-8 中文自检和 `git diff --check`。现场验证时应重点测试已经手动缩放过的 Tab1，在 `Mode=time` 与 `Mode=space` 之间来回切换时是否无需点击自动范围按钮即可显示波形。

## 2026-06-18 Tab1 横轴切换自动范围三次优化

### 问题背景

现场继续验证后确认，前两轮 Tab1 横轴切换修复仍未完全解决问题。Phase 模式下从 `Mode=time` 切换到 `Mode=space` 后，仍可能需要先在绘图控件中画一个矩形放大，再点击自动范围按钮后才出现波形；从 `Mode=space` 切回 `Mode=time` 后，也可能需要点击自动范围按钮才能恢复显示。

前两轮修复已经分别覆盖了“横轴单位变化时解除旧缩放锁定”和“新曲线 `setData(x, y)` 后再执行自动范围恢复”。本次继续出现问题，说明根因不再只是调用顺序，而是 pyqtgraph 的 ViewBox 自动范围、PlotDataItem 边界缓存和 Qt 事件循环之间存在异步窗口：即使程序已经在 `setData()` 后调用 `_restore_plot_auto_range()`，ViewBox 当时仍可能没有稳定拿到新曲线的真实数据边界。

### 修改内容

本次修改集中在 `src/main_window.py`，不改变采集链路和坐标公式：

- 新增 `_curve_data_range()`，直接从当前 Tab1 曲线的 `getData()` 结果中计算有限 `x/y` 数据边界，避免只依赖 ViewBox 内部边界缓存。
- 新增 `_force_plot_range_to_curve_data()`，在恢复自动范围后使用曲线真实边界对 `plot1` 执行确定性的 `setRange()`，让秒级时间轴或米级距离轴立即进入可视范围。
- 扩展 `_apply_pending_time_plot_auto_range()`，在同步恢复后通过 `QTimer.singleShot(0, ...)` 和 `QTimer.singleShot(50, ...)` 再执行两次延迟恢复，覆盖曲线边界在 Qt 事件循环中稍晚更新的情况。
- 延迟恢复会检查触发时的横轴类型是否仍与当前 `_time_plot_axis_kind` 一致，避免用户快速连续切换 `Time/Space` 时旧任务覆盖新模式视图。

### 涉及文件

- `src/main_window.py`
- `docs/2026-6-17-tab1时域图坐标轴修改日志.md`
- `dev_log.md`

### 验证情况

已执行 `python -m py_compile src/main_window.py`，语法检查通过。后续仍需执行 `git diff --check` 和 Git 提交推送。现场联机验证时，重点测试已手动缩放过的 Tab1：在 Phase 模式下连续执行 `Mode=time -> Mode=space -> Mode=time`，确认每次切换后无需手动画矩形、无需点击自动范围按钮，波形即可直接显示在新的 `Distance (m)` 或 `Time (s)` 横轴范围内。

## 2026-06-18 Tab1 Phase time -> space 显示恢复四次优化

### 问题背景

三次优化后，现场反馈 `Mode=space -> Mode=time` 已经可以不点击 Auto 直接显示波形，但 `Mode=time -> Mode=space` 仍存在残留问题：切换后需要先在绘图控件中画一个矩形放大，再点击 Auto，Space 波形才开始出现。这个结果说明通用横轴切换逻辑已经部分生效，问题重点收敛到 Space 秒级时间轴曲线的绘制刷新。

### 修改内容

本次继续只修改 `src/main_window.py` 的 Tab1 显示恢复逻辑，不改变采集、保存和坐标公式：

- 新增 `_configure_time_plot_curves_for_axis()`：Tab1 横轴切到 `time` 时关闭 `clipToView` 和自动降采样，避免 Space 小曲线在旧距离视图下先被裁剪成空路径；切回 `distance` 时恢复原来的实时大曲线优化。
- 新增 `_time_plot_auto_range_frames_remaining`：横轴切换后不只恢复第一帧，而是在后续若干帧继续执行范围恢复，覆盖第一帧 ViewBox 或曲线边界未稳定的情况。
- 扩展 `_apply_pending_time_plot_auto_range()` 的延迟重试，从 `0 ms`、`50 ms` 增加到 `0 ms`、`50 ms`、`150 ms`、`300 ms`。
- 新增 `_refresh_plot_curve_items()`：在按曲线真实边界 `setRange()` 后主动刷新 PlotDataItem、PlotItem 和 ViewBox，避免旧裁剪/降采样路径保留空白显示。

### 涉及文件

- `src/main_window.py`
- `docs/2026-6-17-tab1时域图坐标轴修改日志.md`
- `dev_log.md`

### 验证情况

已执行 `python -m py_compile src/main_window.py`，语法检查通过。现场验证时重点复测 Phase 模式下 `Mode=time -> Mode=space`：先在 Time 距离轴中手动框选或缩放，再切换到 Space，确认不再需要手动画矩形和点击 Auto，秒级时间轴波形应直接出现。

## 2026-07-09 Tab2 Space-Time 实时滤波预处理

### 问题背景

现场需要在 Tab2 Space-Time 图绘制前增加数据流实时滤波，用于观察特定频带内的时空变化。该功能必须保持显示侧边界清晰：只能影响 Tab2 的二维图像显示，不能改变保存数据，也不能改变 Tab1 的时域曲线、PSD 或 Monitor 图。

同时，滤波对象不是单个空间点，而是 Space-Time 图中所有实际绘制的位置点的时间序列。由于 Tab2 属于实时刷新控件，不能为每个点写 Python 循环，也不能对每个显示窗口独立做零相位滤波，否则会带来明显卡顿或窗口边沿突跳。

### 修改内容

本次新增 `src/realtime_filter.py`，封装显示侧实时滤波能力。该模块提供 `parse_filter_spec()` 解析 `1-`、`-10`、`2-10` 三类参数，并通过 `RealtimeTimeAxisFilter` 使用 `scipy.signal.butter(..., output="sos")` 和 `scipy.signal.sosfilt()` 对 `frames x positions` 矩阵沿时间轴执行向量化 IIR 滤波。

`src/time_space_plot.py` 中新增 Tab2 第二行滤波控件：`Filter` 参数输入框和 `FILTER` 开关按钮。滤波接入点位于 `_build_display_block()` 内部，执行顺序为：距离范围裁剪、空间降采样、实时滤波、时间降采样、转置并写入滚动显示缓冲。这样滤波处理的是实际要绘制的每个位置点，同时仍使用真实 `Scan(Hz)` 作为滤波采样率，避免先 `Time DS` 后滤波导致低频截止语义失真。

为了避免每个实时窗口边沿突跳，滤波器保留每个位置点的 SOS 状态，并在后续数据包中继续使用上一包返回的状态。只有滤波参数、采样率、距离范围、空间降采样或 PLOT 状态变化时才重置状态。对于 `0.1-` 这类低频高通，即使单包长度只有 1 秒，滤波仍按连续数据流处理；启动阶段允许有秒级到十秒级的自然稳定过程，但不会把每个 1 秒包当成独立窗口重新滤波。

`src/config.py` 的 `TimeSpaceParams` 新增 `filter_enabled` 和 `filter_spec`，`src/main_window.py` 同步补齐 Tab2 参数保存与恢复。`build_exe.py` 和 `eDAS26.6.18.spec` 已补充 `realtime_filter` hidden import，避免后续打包遗漏新模块。

### 与既有 exe 的功能差异

本次已按当前源码打包生成 `dist/eDAS26.7.9.exe`。该 exe 与之前已生成的 `eDAS26.6.18.exe`、`eDAS26.6.14.exe` 的主要功能差异如下：

- 相比 `eDAS26.6.18.exe`，`eDAS26.7.9.exe` 新增 Tab2 Space-Time 图显示前的实时滤波功能。用户可在 Tab2 绘图参数第二行使用 `Filter` 输入框和 `FILTER` 按钮，对 Space-Time 图实际绘制的所有位置点时域数据执行显示侧滤波。
- `eDAS26.7.9.exe` 支持 `1-` 高通、`-10` 低通、`2-10` 带通等参数格式，也支持类似 `0.1-` 的低频高通输入。无效参数或超过当前 `Scan(Hz)` Nyquist 频率的参数会被提示并跳过滤波。
- `eDAS26.7.9.exe` 的滤波状态会跨实时数据包保存，避免每个窗口独立滤波导致边沿突跳；`eDAS26.6.18.exe` 和 `eDAS26.6.14.exe` 没有该 Tab2 滤波状态链路。
- 该滤波只影响 Tab2 Space-Time 图像缓冲，不改变保存文件，不改变 Tab1 时域图、PSD 或 Monitor 图。旧 exe 的保存和 Tab1 显示行为因此可作为对照基线。
- 相比 `eDAS26.6.14.exe`，`eDAS26.7.9.exe` 同时包含 2026-06-18 版本已完成的 Tab1 Phase `time -> space` 显示恢复优化；`eDAS26.6.14.exe` 不包含后续 6 月 17 日至 6 月 18 日围绕 Tab1 横轴切换和自动范围恢复的多轮修正。
- 本次打包使用 `python build_exe.py --name eDAS26.7.9 --skip-clean`，未删除或覆盖 `dist` 目录下既有的 `eDAS26.6.14.exe` 和 `eDAS26.6.18.exe`。

### 涉及文件

- `src/realtime_filter.py`
- `src/time_space_plot.py`
- `src/config.py`
- `src/main_window.py`
- `build_exe.py`
- `eDAS26.6.18.spec`
- `docs/2026-07-09-Tab2-Space-Time实时滤波功能开发日志.md`
- `dev_log.md`

### 验证情况

已执行 `python -m py_compile src\realtime_filter.py src\time_space_plot.py src\config.py src\main_window.py`，语法检查通过。

已执行小型滤波自检，覆盖 `1-`、`-10`、`2-10` 和 `0.1-` 参数解析，并确认连续两次处理 1 秒矩阵数据时输出形状正确、结果为有限值、输入数组未被原地修改。

已执行 `git diff --check`，未发现空白错误；命令仅提示 Windows 环境下 LF/CRLF 行尾转换。

现场联机验证时，重点确认 Filter 关闭时行为与旧版本一致；Filter 开启后只改变 Tab2 Space-Time 图；`0.1-` 在连续观察时不出现每个包边沿突跳；超过 Nyquist 的截止频率会提示无效并跳过滤波。

## 2026-07-17 Tab1 Phase 时域曲线复用 Tab2 FILTER 配置

### 问题背景

现场需要把 Tab2 的 `FILTER` 开关和 `Filter` 参数扩展为 Tab1 phase 时域曲线的显示滤波配置，同时保持保存数据和 Tab1 phase PSD 的既有边界不变。也就是说，Tab1 波形曲线可以按 Tab2 参数观察滤波后的 phase 显示结果，但保存文件仍然保存未 Rad、未 GUI FILTER 的原始 phase `int32` 块，PSD 仍然基于未经过 Tab1/Tab2 FILTER 的显示数据计算。

### 修改内容

本次修改集中在显示侧数据分流：

- `src/time_space_plot.py` 新增 `get_filter_settings()`，用于向主窗口暴露当前 Tab2 `FILTER` 开关和 `Filter` 文本，不暴露也不共享 Tab2 自己的滤波器状态。
- `src/main_window.py` 引入 `RealtimeTimeAxisFilter`，在主窗口内新增 Tab1 phase 波形专用滤波器 `_tab1_phase_filter`。
- `_update_phase_display()` 中保留原始 `display_data` 作为 PSD 和 Tab2 Time-Space 的输入；额外派生 `waveform_display_data`，只供 Tab1 `plot_curve_1.setData(...)` 使用。
- Phase `Mode=space` 下，Tab1 波形曲线使用滤波后的某空间点时间序列，PSD 仍使用未滤波的 `space_data`。
- Phase `Mode=time` 下，Tab1 多帧距离曲线使用滤波后的波形数据，PSD 仍使用未滤波的 `display_data[-point_num:]`。
- Tab1 和 Tab2 只共享 FILTER 配置，不共享 IIR 状态，避免两个绘图路径因输入窗口、列数和刷新时机不同而互相污染状态。
- 采集开始、Tab1 波形显示开关切换、Tab2 参数变化、滤波配置变化或参数无效时会重置 Tab1 独立滤波状态。

### 数据流边界

最新版本的数据流边界如下：

- 保存数据：不经过 Rad，不经过 Tab1 phase 波形滤波，不经过 Tab2 FILTER。
- Tab1 phase 时域曲线：若 `Rad` 开启，先使用 Rad 转换后的显示数据；若 Tab2 `FILTER` 开启，再按 Tab2 `Filter` 参数进行 Tab1 独立实时滤波。
- Tab1 phase PSD：若 `Rad` 开启，使用 Rad 转换后的显示数据；不经过 Tab1 phase 波形滤波，也不经过 Tab2 FILTER。
- Tab2 Time-Space：若 `Rad` 开启，使用 Rad 转换后的显示数据；若 Tab2 `FILTER` 开启，使用 Tab2 自己的实时滤波器状态，只影响 Tab2 图像缓冲。
- Raw、Monitor、Tab3 TCP：不使用 Tab2 FILTER。

### 涉及文件

- `src/main_window.py`
- `src/time_space_plot.py`
- `docs/2026-7-17滤波配置与数据流.md`
- `dev_log.md`

### 验证情况

已执行 `python -m py_compile src\main_window.py src\time_space_plot.py src\realtime_filter.py`，语法检查通过。已执行 `git diff --check`，未发现空白错误，命令仅提示 Windows 环境下 LF/CRLF 行尾转换。已执行小型数据流自检，确认 Tab1 phase 波形滤波 helper 返回新数组、不原地修改输入数组；PSD 源数据仍保持未滤波；FILTER 关闭时波形数据回退为原显示数据。

## 2026-07-17 Main Display FILTER UI relocation

### Background

The FILTER parameter now controls both the Tab1 phase waveform and the Tab2 Time-Space image. Keeping the `Filter` input and `FILTER` button inside Tab2 made the scope look narrower than it really is. The left-side Display Control options also needed a cleaner single-row layout.

### Changes

- Changed the visible spectrum refresh option from `Spectrum` plus a separate `Power/PSD` label to a single `PSD` checkbox.
- Placed `Waveform`, `PSD`, `Monitor`, and `rad` on one row with spacing between options.
- Moved the shared `Filter` input and `FILTER` button to the next row in the left-side Display Control group.
- Removed the `Filter` input and `FILTER` button from the Tab2 parameter row.
- Added `TimeSpacePlotWidget.set_filter_settings()` so Tab2 receives the shared settings from `MainWindow` while keeping its own IIR filter state.
- Kept Tab1 phase waveform and Tab2 Time-Space state independent; they share only the main-panel switch and parameter text.
- Changed Tab2 `Reset to Defaults` so it no longer resets the shared FILTER controls.

### Files

- `src/main_window.py`
- `src/time_space_plot.py`
- `docs/2026-7-17????????.md`
- `docs/2026-07-09-Tab2-Space-Time??????????.md`
- `dev_log.md`

### Verification

Completed before commit: `python -m py_compile src\main_window.py src\time_space_plot.py src\realtime_filter.py`, shared FILTER self-test, UTF-8 Chinese mojibake self-check, and `git diff --check`. The Chinese self-check scans modified UTF-8 files for CJK lines containing `?` and for U+FFFD replacement characters.
