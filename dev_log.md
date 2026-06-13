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