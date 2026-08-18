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
- `docs/2026-7-17滤波配置与数据流.md`
- `docs/2026-07-09-Tab2-Space-Time实时滤波功能开发日志.md`
- `dev_log.md`

### Verification

Completed before commit: `python -m py_compile src\main_window.py src\time_space_plot.py src\realtime_filter.py`, shared FILTER self-test, UTF-8 Chinese mojibake self-check, and `git diff --check`. The Chinese self-check scans modified UTF-8 files for CJK lines containing `?` and for U+FFFD replacement characters.

## 2026-07-17 Packaged eDAS26.7.17 executable

### Packaging request

A dated Windows executable was required after the latest `dev` branch UI and shared FILTER changes. The package must keep previous executables in `dist/` and follow the earlier packaging convention.

### Packaging command

```powershell
python build_exe.py --name eDAS26.7.17 --skip-clean
```

The `--skip-clean` flag was used deliberately so previous executable files in `dist/` were not removed.

### Output

- Generated executable: `dist/eDAS26.7.17.exe`
- Reported size: 77.26 MB
- Generated spec file: `eDAS26.7.17.spec`
- Previous executables confirmed still present: `eDAS26.6.14.exe`, `eDAS26.6.18.exe`, and `eDAS26.7.9.exe`
- The build directory was removed by the packaging script after successful packaging.

### Source control

`dist/` remains ignored by Git, so the executable is a local delivery artifact and is not committed to the source repository. The generated `eDAS26.7.17.spec` is retained with the source, matching the existing versioned spec-file pattern.

## 2026-07-17 Runtime storage enable creates missing directories

### Background

A runtime storage bug was reported: while acquisition was already running, enabling storage with a target folder that did not exist failed to create the folder automatically. The saver implementation already had `mkdir(parents=True, exist_ok=True)` in `BlockBasedFileSaver.start()`, but the running UI path did not actually start a saver when `Enable` was toggled.

### Changes

- Connected `save_enable_check.toggled` to `_on_save_enable_toggled()` in `src/main_window.py`.
- Added `_start_data_saver()` so startup-time storage and runtime storage enable share the same saver creation path.
- Runtime enable now uses the current `Path` and `Blocks/File`, then calls `BlockBasedFileSaver.start()`, which creates missing directories before opening the first `.bin` file.
- Added `_stop_data_saver()` to close the active saver consistently. Manual acquisition stop closes the file but keeps the `Enable` setting for the next run; runtime uncheck stops the saver and disables storage.
- Adjusted local parameter restore order so save path and block count are applied before setting `Enable` with signals blocked.
- Saved payload semantics are unchanged: complete acquisition blocks are saved without GUI `rad`, Tab1/Tab2 display FILTER, or PSD processing.

### Files

- `src/main_window.py`
- `docs/README-2026-03-20-eDAS数据存储技术说明.md`
- `dev_log.md`

### Verification

Completed `python -m py_compile src\main_window.py src\data_saver.py`. Completed a runtime storage path creation regression check with a missing nested folder and confirmed the directory plus first `.bin` file were created. Also asserted that `Save Enable` is connected to the runtime saver startup path. Completed `git diff --check` and the UTF-8 Chinese mojibake self-check.

## 2026-07-20 Storage-only downsample and SAVE button

### Background

现场需要在不影响实时波形、PSD、Tab1/Tab2 FILTER 和 TCP 通信的前提下，降低落盘数据量。这个需求不能复用显示侧 Time-Space 降采样，也不能用滤波重采样代替；保存链路只允许做简单、可解释的抽点：`Save DS = N` 时，每帧每 N 个点保留 1 个点。

同时，保存开关从复选框改为按钮，避免用户把它误解成只在启动前生效的静态配置。界面需要实时显示本轮保存已经创建的 `.bin` 文件数量，停止保存后保留最后的本轮计数，下一轮保存启动时再清零。

### Changes

- `src/config.py` 的 `SaveParams` 新增 `storage_downsample_factor`，默认值为 `1`，并进入本地参数保存/恢复。
- `src/main_window.py` 将 `Data Save` 区域的 `Enable` 复选框替换为可切换 `SAVE` 按钮，按钮样式与现有小型功能按钮保持一致：未启用为灰色，待下一轮保存为绿色，正在保存为蓝色 `SAVING`。
- 在保存路径旁新增 `Save DS` 数值框，范围为 `1` 到 `100000`。该参数只在保存文件打开前锁定；保存进行中禁用，避免同一个 `.bin` 文件内出现前后点数不一致。
- 保存入队前新增 `_downsample_data_for_storage()`：单通道数据按每帧点位抽取；多通道数据按帧内空间/时间行抽取并保留完整通道列，避免直接对扁平数组抽样导致通道交错错位。
- 文件名中的 `pt` 和 `Est. Size` 现在使用降采样后的每帧点数，便于离线解析时识别实际保存形状。
- 新增 `Files: N` 本轮文件计数显示，活动保存时从 `BlockBasedFileSaver.total_files_created` 实时刷新，停止后保留最后计数。

### Files

- `src/config.py`
- `src/main_window.py`
- `docs/README-2026-03-20-eDAS数据存储技术说明.md`
- `user_read.md`
- `dev_log.md`

### Verification

已执行 `python -m py_compile src\main_window.py src\config.py`，语法检查通过。已执行 `git diff --check`，未发现空白错误，命令仅提示 Windows 环境下 LF/CRLF 行尾转换。已执行不启动 GUI 的数组自检，覆盖单通道 PHASE 和双通道 Raw：确认 `Save DS` 按帧内点位抽取，返回连续数组，多通道通道列不被打乱。

### Git and packaging

本次源代码修改将在 `dev` 分支提交并推送到 GitHub。推送完成后按请求使用当天日期时间命名 exe，并通过 `build_exe.py --skip-clean` 保留既有 `dist/` 中的历史 exe。

### Packaging output

已执行：

```powershell
python build_exe.py --name eDAS20260720-173900 --skip-clean
```

输出文件为 `dist/eDAS20260720-173900.exe`，大小 `81,018,519` 字节，修改时间为 `2026/7/20 17:43:08`。打包后确认旧版本 `eDAS26.6.14.exe`、`eDAS26.6.18.exe`、`eDAS26.7.9.exe`、`eDAS26.7.17.exe` 仍保留在 `dist/` 目录中。本次 PyInstaller 规格文件 `eDAS20260720-173900.spec` 按历史版本规格文件惯例保留在源码仓库。

## 2026-07-28 Tab4 setting 与 Bitshuffle+Zstd .bz 实时压缩存储

### 背景

本次根据现场需求新增第二种保存格式：原 `.bin` 裸二进制格式必须保持不变，同时增加可选 `.bz` 实时压缩格式。`.bz` 要求采用 `Bitshuffle + Zstd(level=3, block=65536)` 默认参数，参数可在 GUI 中调整，并且必须按包实时保存，不能等整段采集结束后再统一压缩。

### 修改内容

- `src/config.py` 新增保存格式常量和 `SaveParams` 压缩字段：`storage_format`、`bz_zstd_level`、`bz_bitshuffle_block_values`、`bz_packet_frames`、`bz_file_duration_s`。
- `src/bz_format.py` 新增 `.bz` 文件头、`BZS1` packet header、NumPy 可逆 bitshuffle 后端、Zstd 压缩/解压和 packet 迭代读取函数。
- `src/data_saver.py` 新增 `BitshuffleZstdFileSaver`，采用 raw queue、压缩线程和写盘线程。采集侧仍然非阻塞入队；每攒够一个 packet 帧数就立即压缩写盘；停止保存时写入不足一个 packet 的尾包。
- `src/main_window.py` 新增第 4 个 tab，tab 名为 `setting`。Tab4 通过下拉框选择 `BIN (.bin)` 或 `Bitshuffle+Zstd (.bz)`，并提供 Zstd level、Bitshuffle block、BZ packet frames、BZ file seconds 参数。
- `.bin` 保存路径保持原 `BlockBasedFileSaver` 行为不变；`.bz` 保存路径按 `BZ File(s)` 近似按秒分文件，默认 60 秒，每包默认约 1 秒。
- 保存日志新增 `.bz` raw queue、compressed queue、pending frames、`cache`、`dropped`、`not_realtime`、压缩耗时和写盘耗时字段，用于判断是否有缓存、是否因为压缩/写盘无法实时而丢数据。
- `other_files/read/read_bz_notebook.ipynb` 新增离线读取 notebook，可读取指定 `.bz` 文件，打印数据量，绘制指定位置点的时域波形，并绘制 time-space 图。
- `requirements.txt` 新增 `zstandard>=0.22.0`，`build_exe.py` 同步加入 `bz_format` 和 `zstandard` hidden import。
- `docs/README-2026-03-20-eDAS数据存储技术说明.md` 补充 `.bz` 格式、Tab4 参数和实时诊断说明。

### 验证结果

- `python -m py_compile src\main_window.py src\data_saver.py src\bz_format.py src\config.py build_exe.py` 通过。
- 当前环境为 Python 3.9.19，已将新增 `src/bz_format.py` 调整为 Python 3.9 兼容写法，并通过 `import bz_format`、`import data_saver` 实际导入检查。
- 已安装并验证新增运行依赖 `zstandard 0.25.0`；`requirements.txt` 中记录最低版本 `zstandard>=0.22.0`。
- `.bz` round-trip 自检通过：写入 10 帧、5 点、2 通道测试数据，`packet_frames=4`，`file_duration_s=2`，生成 2 个 `.bz` 文件、3 个 packet，读回 packet frame 分布为 `[4, 4, 2]`，50 行双通道数据逐值一致，`dropped=0`、`dropped_samples=0`、`not_rt=0`。
- `.bin` 回归自检通过：写入 50 个 `int32` 值，输出文件 200 字节，读回逐值一致。
- `other_files/read/read_bz_notebook.ipynb` 通过 JSON 格式检查。
- UTF-8 中文自检未发现典型 mojibake 或 replacement character 编码破坏标记。
- `git diff --check` 通过，仅提示 Git 会按配置将部分 LF 文件在工作区转换为 CRLF。

### Git

本次修改完成自检后同步到 GitHub `dev` 分支。提交号以最终推送结果为准。

## 2026-07-29 Length 参数模型、保存/通信包长统一与挂死分析整理

本次更新把用户界面的帧数/块数参数统一调整为以秒为单位的 Length 参数模型。`FrameLoad` 改为 Tab4 的 `Length/Load`，默认 `0.2 s`；`FramePlot` 改为 Tab4 的 `Length/Plot`，默认 `1 s`，并要求它是 `Length/Load` 的整数倍。运行时仍会根据 `Scan(Hz)` 派生 `frame_load_num` 和 `frame_plot_num`，但这些字段只作为内部帧数使用，不再作为用户直接填写的界面参数。

保存链路同步完成统一。`.bin` 与 `.bz` 现在共用 `Length/Save` 和 `Length/File`：前者默认 `1 s`，表示每个保存包或压缩 packet 的数据时长；后者默认 `10 s`，表示每个输出文件的数据时长。旧界面中的 `BZPacketFrames`、`BZfiles(s)` 和 `Blocks/File` 已从用户参数中移除。`.bin` 保存器保留裸二进制连续流格式，但内部会把多个 `Length/Load` 采集块聚合成 `Length/Save` 保存包后写盘，并按 `Length/File` 分文件；`.bz` 保存器按同样的保存包和文件时长压缩分包。

通信链路新增 Tab3 的 `Length/Comm`，默认 `1 s`，并要求它是 `Length/Load` 的整数倍。Tab3 管理器不再把每个采集回调直接当成一个 TCP 包，而是先聚合完整 `Length/Load` 块到 `Length/Comm`，再按通道范围、空间降采样和时间降采样构造协议包。TCP 包体大小由 `Length/Comm`、`Scan(Hz)`、`TimeDownsample`、空间通道范围和 `SpaceDownsample` 决定；`Length/Plot`、`Length/Save`、`Length/File` 和 BZ 压缩参数不参与 TCP 包大小。

界面布局也同步调整。Tab1 参数区只保留现场高频操作项，包括基础采集、上传、相位处理、显示开关和保存启停；`Bypass`、`Rate2Phase`、`DataRate`、`PolarDiv`、`Clock`、`Trig`、`CenterFreq` 移到 Tab4，默认值保持不变。Tab4 现在集中承载采集长度、硬件细节和存储设置，降低 Tab1 现场操作时的参数密度。

为支持 `Length/Plot > Length/Load`，采集线程增加显示历史缓存，显示链路可以跨多个采集块拼出最新显示窗口；GUI 仍只消费最新快照，避免历史大数组进入 Qt 事件队列。为支持 `Length/Comm > Length/Load`，Tab3 管理器增加通信帧缓存，只在累计到完整通信包时入发送队列。

本次继续保留并完善 2026-07-29 采集卡挂死分析：14:02 的直接卡点在 DLL `read_phase_data()` 长时间不返回，BZ 队列没有堆积证据；自动恢复在 GUI 主线程同步等待同一把 API 锁，导致界面也卡死；15:15 和 15:22 两次重启仍出现 `buffer=4294967295/6820000`，说明设备或驱动状态没有被上层软件重启复位。本次已在 `query_buffer_points()` 中检查 DLL 返回码和 `0xFFFFFFFF` 无效缓冲区值，避免把底层错误状态误判成真实缓冲区点数。

同步更新了根 `README.md`、`user_read.md`、`docs/README-2026-03-20-eDAS数据存储技术说明.md`、`docs/2026-03-14-Tab3-DAS数据通信功能开发方案.md` 和 `docs/2026-7-29采集卡挂死原因分析与各个环节单包数据长度梳理.md`。其中 7-29 文档补充了改造前后参数对照表，并按 DLL 读取、GUI 显示、`.bin` 保存、`.bz` 保存和 Tab3 TCP 通信分别说明单包/单块长度由哪些参数决定。

验证项包括 Python 语法编译检查、`.bin` Length/Save 聚合与 Length/File 分文件自测、Tab3 Length/Comm 聚合自测，以及配置默认值和旧保存参数残留检查。现场硬件仍需复测 DLL 读停滞后的 watchdog 行为、`0xFFFFFFFF` 缓冲区异常提示、BZ 实时压缩统计和 TCP 下游接收矩阵维度。

## 2026-07-30 PHASE 单通道裁剪显示帧宽与 Length/Plot 刷新修复

### 背景

根据 `logs/20260730_211841.log`，本次现场参数为 `scan_rate=10000`、`length_load_s=0.200`、`length_plot_s=1.000`、`load_frames=2000`、`plot_frames=10000`，单通道 PHASE 裁剪范围为 `[100, 800)`。日志中 `_on_phase_data` 约按采集块节奏持续触发，结束统计为 `Total data callbacks: 188, GUI updates: 188`，与期望的 1 s 显示刷新不一致；开启 TimeSpace 后 `_on_phase_data` 耗时明显上升，且波形/TimeSpace 图形表现出帧拼接错位特征。

### 根因

单通道 PHASE 数据在采集线程中已经按裁剪范围 `[100, 800)` 从 `points_after_merge=1024` 裁到实际 `700` 点/帧，但显示历史缓存仍按 `1024` 点/帧重组扁平数组，导致 0.2 s 采集块在拼成 1 s 显示窗口时跨帧错位。GUI 侧最新快照消费定时器同时固定为 `100 ms`，没有跟随 `Length/Plot` 派生出的 `frame_plot_num / scan_rate`，因此实际显示刷新快于界面设置。

### 修改

- `src/acquisition_thread.py` 修正单通道 PHASE 裁剪逻辑，按实际完整帧数裁剪，遇到不完整尾部时丢弃并记录 warning，避免把残缺数据继续送入显示矩阵。
- `src/acquisition_thread.py` 新增显示侧帧宽计算，PHASE 单通道使用裁剪后的 `end - start`，多通道 PHASE 仍使用 `points_after_merge`，Raw/IQ 等数据使用 `point_num_per_scan`。
- `src/acquisition_thread.py` 的显示历史缓存现在使用裁剪后的实际帧宽重组窗口，避免 700 点/帧被误按 1024 点/帧拼接，波形和 TimeSpace 共用同一修正后的显示快照。
- `src/main_window.py` 将最新显示快照消费定时器改为由 `Length/Plot` 派生：`frame_plot_num / scan_rate * 1000 ms`，本次日志参数下为 `1000 ms`。修改 Length 参数或启动采集时都会重新应用该间隔。
- `src/config.py` 同步更新 `Length/Plot`/`frame_plot_num` 注释，明确它既是显示窗口长度，也是 GUI 显示刷新周期。

### 验证

- 已执行 `python -m py_compile src\acquisition_thread.py src\main_window.py src\time_space_plot.py`，语法检查通过。
- 已执行数组自检：模拟日志中的 `points=3072`、`merge=3`、裁剪 `[100,800)`、`load_frames=2000`、`plot_frames=10000`，确认单块裁剪为 `2000*700`，两块历史缓存连续拼接为 `4000*700`，首尾帧裁剪范围与原始矩阵一致。
- 已执行显示间隔自检：`scan_rate=10000` 且 `frame_plot_num=10000` 时返回 `1000 ms`，`frame_plot_num=2000` 时返回 `200 ms`，极小窗口按下限钳制到 `50 ms`。

## 2026-08-12 `0xFFFFFFFF` 缓冲区查询异常熔断与现场复位说明

### 背景

根据最新日志 `logs/20260812_091940.log`，程序启动和设备打开正常，用户在约 `8.410 s` 点击 START 后，设备配置、缓冲区分配和 `pcie7821_start()` 均成功返回。但采集线程第一次进入 `query_buffer_points()` 时，DLL 立即持续返回 `0xFFFFFFFF` 无效缓冲区点数。该日志中同类 API 错误文本出现 `6898` 次，采集线程的 `Error querying buffer` 出现 `3449` 次，且多个 stop/start 自动恢复轮次后仍复现。

用户随后反馈：重启电脑和采集卡后恢复正常。这个现场结果确认该问题不是 Length 参数、保存链路、TCP 通信或 GUI 绘图造成，而是采集卡/驱动/DMA 状态残留导致的硬件边界异常。

### 修改

- `src/acquisition_thread.py` 新增缓冲区查询错误计数和熔断逻辑。`PCIe7821Error` 或包含 `0xFFFFFFFF` 的查询异常被视为致命缓冲区查询错误，采集线程立即停止，不再继续高频轮询刷日志。
- 对非致命的普通查询异常保留有限重试，连续失败达到 `BUFFER_QUERY_FAILURE_LIMIT = 5` 后同样停止采集，避免 DLL 查询路径异常时线程无限空转。
- 采集诊断快照新增 `buffer_query_error_count`、`consecutive_buffer_query_errors` 和 `last_buffer_query_error`，主窗口周期性 `Acq snapshot` 日志同步输出查询错误计数和最后一次错误。
- `src/main_window.py` 在收到致命采集错误后调度现有 STOP 清理流程，停止采集线程、硬件、保存器和 TCP 会话，并在状态栏提示需要复位 PCIe 设备/驱动后再重启采集。
- 致命错误路径不触发自动 stop/start 恢复，因为本次日志和现场反馈已经证明单纯软件重启无法清理 `0xFFFFFFFF` 状态，反复恢复只会扩大日志噪声。

### 文档

新增问题解决文档 `docs/2026-08-12-buffer-query-0xFFFFFFFF-fault-handling.md`，记录本次日志证据、根因判断、现场处置步骤和代码防护边界。文档明确建议：出现该错误后先停止采集，关闭程序，断电/重启采集卡或重启主机，确认设备重新枚举后再启动程序。

### 验证

已执行 `python -m py_compile src\acquisition_thread.py src\main_window.py src\pcie7821_api.py`，语法检查通过。现场硬件复测仍需在真实设备上确认：再次遇到 `0xFFFFFFFF` 时，日志应只输出一次致命查询错误和 STOP 清理信息，而不是持续刷屏或自动反复重启。


## 2026-08-12 长时间日志分析与实时链路优化

- 分析 `logs/20260812_103513.log`（约 7.01 小时、92,447 行），确认本次长时间 `.bz` 保存 `dropped=0`、队列未满、最终帧率约 9,999.06 Hz；未发现本地实时存储丢数据。
- 识别主要风险为采集/驱动缓冲阶段性积压：长时间保存段缓冲积压 p95 约 2.49 s，峰值约 32.65 s；`gui_skips` 属于 GUI 快照覆盖，不等同于采集或存储数据丢失。
- 优化 Phase 显示发布策略：采集线程保留显示历史但按显示窗口周期限流发布 GUI 快照，减少每 200 ms 重复拼接和主线程覆盖压力。
- 优化监测波形读取：采集线程根据 UI 勾选状态决定是否读取 monitor 数据，未显示时跳过不必要的 PCIe/API 调用。
- 增加采集诊断字段：`api_read_ms`、`crop_ms`、`dispatch_ms`、`display_pub_ms`、`monitor_read_enabled`，便于后续复测直接定位瓶颈。
- 调整 `.bz` 存储实时性指标：将单包慢压缩拆为 `slow_compression_packet_count`，`compression_not_realtime_count` 只保留明确队列满/失败等实时链路风险事件，避免误判本地存储失败。
- 新增分析报告：`docs/2026-08-12日志分析与软件优化.md`，并同步更新 `.bz` 数据存储技术说明。

## 2026-08-13 实时链路保存优先优化

- 针对 2026-08-12 长时间日志中驱动缓冲积压峰值约 32.65 s 的问题，继续优化采集线程到本地保存线程之间的实时链路。
- 调整完整数据回调优先级：采集线程收到完整块后先执行本地保存入队，再处理 Tab3 TCP 通信 ingest，避免通信聚合推迟保存入队。
- 将存储专用降采样从主窗口采集回调移入 `.bin`/`.bz` 保存后台线程，采集线程不再执行大块数组点抽取和拼接。
- 为保存器新增 `last_enqueue_ms`、`max_enqueue_ms`、`source_points_per_frame`、`storage_downsample_factor` 诊断字段，便于复测时直接判断保存入队是否拖慢采集。
- Tab3 TCP 通信新增后台 ingest 队列和线程，采集线程只做轻量入队；Length/Comm 聚合和通信包准备在 TCP 后台线程完成。TCP ingest 队列满时丢弃最旧通信块，只影响通信，不影响本地保存。
- 主采集快照新增 `save_enqueue_ms`、`tcp_enqueue_ms`、`tcp_ingest_queue`、`tcp_ingest_dropped`、`tcp_process_ms` 等字段，用于区分保存、通信、GUI、DLL 读取各自耗时。
- 验证：`python -m py_compile src\data_saver.py src\main_window.py src\tcp_tab3\tcp_tab3_manager.py src\acquisition_thread.py` 通过；保存线程内部降采样小数组测试通过；TCP ingest 启停生命周期测试通过；`git diff --check` 通过。

## 2026-08-13 显示流畅性日志分析与采集优先优化

- 分析 `logs/20260813_230051.log`，确认 `Length/Plot=0.400 s` 已经生效，日志中显示 `GUI display refresh interval set to 400 ms` 且启动参数为 `plot_frames=40000`。用户感觉仍像 1 s 刷新，根因是 GUI 主线程单次显示回调仍有大量 0.5-0.7 s，采集线程显示快照生成也出现秒级 `display_pub_ms`。
- 日志统计：第一段 `Length/Plot=1.000 s` 时 `_on_phase_data` p50 约 `1276.4 ms`，第二段 `Length/Plot=0.400 s` 时 `_on_phase_data` p50 降至约 `70.9 ms`，但 p90 仍约 `641.8 ms`；驱动缓冲峰值均达到单次读取目标的约 `26.2x`。
- 数据完整性判断：本次日志没有 `ERROR`、没有 `0xFFFFFFFF`、没有 TCP ingest 丢弃，也没有保存队列丢弃记录；但本次未看到保存器启动/停止记录，不能作为开启本地保存后的无丢失证明。主要风险是显示路径拖慢采集读取，导致驱动缓冲积压。
- 优化 `src/acquisition_thread.py`：显示历史追加不再对每个 `Length/Load` 块强制复制；如果 GUI 尚未消费上一帧显示快照，采集线程跳过本次大快照生成并记录 `gui_skips`，优先保护读卡、保存和通信链路。
- 优化 `src/main_window.py`：相位转弧度从整块显示窗口转换改为按实际渲染数组延迟转换；SPACE 模式单点时间序列改为 NumPy 向量化抽取；TIME 模式优先显示最新帧，避免在主线程处理无关历史帧。
- 优化 `src/time_space_plot.py`：`update_data()` 支持 `display_scale`，在距离裁剪和空间/时间降采样后再做弧度缩放，降低 Tab2 激活时的大数组转换压力。
- 新增文档 `docs/2026-08-13日志分析与显示流畅性优化.md`，并更新 `README.md` 文档索引和采集/显示链路说明。
- 验证：`python -m py_compile src\acquisition_thread.py src\main_window.py src\time_space_plot.py` 通过。真实流畅性和保存完整性仍需现场硬件复测，重点观察 `_on_phase_data`、`display_pub_ms`、`buffer/expected`、`save_dropped` 和 `.bz` 队列水位。
## 2026-08-14 显示事件驱动与数据存储预检

- 分析 logs/20260813_233432.log：第一段 0.4 s 配置下 GUI 回调间隔 p50/p90 约 4.18/5.36 s，_on_phase_data p90=476.8 ms，display_pub_ms p90=31 ms，buffer/expected p50/p90=21.17/24.57x，read_age_s p90=1.7 s。根因是发布和 GUI 定时消费双重节流、大显示快照以及 DLL 读取/内存带宽积压。
- 显示快照改为信号唤醒、定时器 watchdog；SPACE 只发布 Region 时间序列，TIME 默认只发布最新 4 帧，Time-Space 或 TIME 滤波按需请求完整窗口。
- PCIe Phase 读取支持 DMA view，采集线程在空间裁剪后仅复制最终有效块；完整数据在进入保存/TCP 前拥有独立连续内存。
- 存储队列从固定 200 块改为按 block/packet 字节和可用内存计算，避免 53.41 MiB/块时 raw queue 理论占用约 10.68 GiB。日志新增 input_mib_s、queue_mb、raw_backlog_s 和 .bz worker 工作集估算。
- 保存器成功入队后冻结 NumPy 数组，防止异步落盘前数据被修改；队列满时恢复写权限。.bin 停止保存改为等待后台线程完整排空，不再 5 秒后强行关闭文件。
- 新增 tests/test_data_saver_integrity.py。5 项测试覆盖 .bin/.bz 逐点一致性、CRC、双通道 Save DS、尾包、轮转、所有权、字节容量和 5.2 s 慢盘停止，全部通过。
- 现实尺寸 .bin：3 x 53.41 MiB 全部写入，约 1306.6 MiB/s，字节数一致。
- 现实尺寸 .bz：默认 1 s 包输入 267.03 MiB，压缩约 2683.5 ms，文件 133.62 MiB，CRC/逐点一致且无丢块；4 worker 的 0.2 s 包持续测试约 171 MiB/s，低于约 267 MiB/s 输入速率。高负载长期完整保存优先 .bin，.bz 需提高 Save DS 后复测。
- 验证：py_compile、5 项 unittest、离屏 Qt 0.4 s 节拍测试、存储现实尺寸基准和 git diff --check 均通过。

## 2026-08-14 05:02 日志显示节拍、存储连续性与真实帧率复核

- 分析 `logs/20260814_050253.log`：0.4 s 显示刷新约 0.8 s 的直接原因是采集块约 0.390~0.409 s 到达，旧节流严格要求满 0.400 s，早到块被跳过后等待下一块；Tab2 还重复执行 Tab1 全窗口处理。
- 显示发布增加 30 ms 容差；Tab2 改为不重叠增量二维快照，GUI 使用 `snapshot_kind=3` 直接更新 Time-Space，不再经过 Tab1 波形/频谱路径。
- 结合文件名统计确认 BIN 92 个文件序号 1..92，文件间隔中位数 2.004 s；BZ 42 个文件序号 1..42，文件间隔中位数 2.002 s。两种格式和无存储运行均约 50 kframe/s，排除保存器时间降采样。
- 每个 BIN 文件 100K 帧、280,000,000 bytes，92 个文件总量和 460 个 20K 包完全匹配；BZ 208 个 20K 包全部写入。该结论证明应用收到的数据完整，但不能仅凭 100K 帧文件证明真实墙钟时长为 1 秒。
- 50 kframe/s 最可能与 `PolarDiv` 两扫描合一帧有关，仍需关闭 PolarDiv 做 A/B 测试；另修复 DLL 配置 setter 返回码被忽略的问题，并在 INFO 日志输出完整硬件参数。
- 采集日志新增 `configured_fps`、`measured_fps`、`fps_ratio`、`driver_pending_frames`；BIN/BZ 新增 `frames_received`、`frames_written`、`pending_frames`、`continuity_gap` 完整性摘要，明确 Save DS 仅为空间降采样。
- 新增分析文档 `docs/2026-08-14-latest-log-display-storage-frame-rate-analysis.md`。
- 验证：4 个核心模块 `py_compile` 通过；显示节拍与存储完整性共 7 项测试全部通过，包含 390 ms 节拍容差、Tab2 增量快照不重叠、BIN 逐值回读、BZ CRC/包序、尾包、文件轮转、停止排空和接收/写入帧数一致性。

## 2026-08-14 大数据量 DAS 上位机开发经验总结

- 综合近三天日志分析、测试 log 分析文档，以及 2026-05 以来关于大块读取卡死、GUI 显示解耦、Length 参数模型、异步保存和数据完整性的历史开发记录，新增开发者经验总结文档 `docs/20260814-大数据量DAS上位机软件开发经验总结文档.md`。
- 文档围绕四条主线整理：波形和 Time-Space 显示流畅性、应用侧保存完整性与不丢数据策略、软件控制和 STOP 不被底层或 GUI 链路拖死、采集/保存/显示/TCP 的数据流分层设计。
- 明确本项目形成的核心工程原则：采集优先，完整数据和显示快照分离；GUI 可跳帧但保存必须可验证；保存队列按字节预算；异步数组入队后转移所有权；`.bin` / `.bz` 完整性边界、真实帧率与配置帧率必须分开记录。
- 将 100 kHz 数据量减半分析纳入经验文档，强调文件帧数连续只能证明应用收到的数据完整写入，不能证明硬件真实扫描周期等于配置值；后续类似软件应同时记录 `configured_fps`、`measured_fps` 和 `fps_ratio`。
- 本次为文档和日志更新，不修改运行时代码。验证重点为 UTF-8 正确写入、文档路径和源码文件名引用一致、Git 差异检查；随后同步到 GitHub。

## 2026-08-17 Time-Space 显示变换下放到采集线程

### 背景

根据 `logs/20260817_161814.log`，现场参数 `scan_rate=100000`、`Length/Load=0.200 s`、`Length/Plot=0.400 s`、单通道 PHASE 裁剪 `[50,512)`，Tab2 Time-Space 激活时每个显示快照约 70.5 MB（40000 帧 × 462 点 × int32）。日志中 `_on_phase_data` 持续出现 120-180 ms 的 `Slow _on_phase_data` 警告，`gui_interval_ms` 稳定在约 390-420 ms，说明 GUI 主线程每次仍要处理一个大数组，Tab1 与 Tab2 主观观感不一致。

根因在于：`snapshot_kind=3`（Time-Space 增量全窗口）的显示快照仍以原始 `int32` 全窗口交给 GUI，弧度转换、距离裁剪、空间/时间降采样和转置全部在 GUI 主线程的 `TimeSpacePlotWidget._build_display_block()` 中完成。存储链路早已把降采样下放到保存后台线程，但显示链路尚未做同样处理。

### 修改

- `src/acquisition_thread.py`
  - 新增 `set_display_transform()`，把 `rad_enabled`、`distance_start/end`、`space_downsample`、`time_downsample`、`filter_enabled`、`filter_spec` 同步到采集线程。
  - 采集线程新增 `RealtimeTimeAxisFilter` 实例与 `_build_time_space_display_block()`，在 `_publish_latest_display_data()` 中针对 `snapshot_kind=3` 的单通道 PHASE 快照，直接完成弧度缩放、距离裁剪、空间/时间降采样、实时滤波和 `(space, time)` 转置，产出可直接 `setImage` 的浮点小块。
  - 显示快照元组从 4 元改为 5 元，`snapshot_kind=3` 附带 `(source_frame_count, block_duration_s, distance_start, distance_end)` 元数据。
  - 诊断快照新增 `last_display_transform_ms`，用于区分采集线程内的显示变换耗时与整体发布耗时。

- `src/main_window.py`
  - `_drain_latest_display_data()` / `_on_phase_data()` / `_update_phase_display()` 解包 5 元快照并透传 `display_meta`。
  - `snapshot_kind=3` 走新路径 `time_space_widget.append_prepared_block()`，直接追加已变换块；保留旧 `update_data()` 作为多通道等无法预变换场景的回退。
  - 新增 `_sync_acquisition_display_transform()`，在启动、Tab 切换、模式/区域/PLOT 状态变化、Time-Space 参数变化、滤波与 rad 开关变化时把显示变换同步到采集线程。
  - 新增 `rad_check.toggled` 连接，rad 开关变化即时生效并同步。

- `src/time_space_plot.py`
  - 新增 `append_prepared_block()`，接收采集线程预处理的 `(space, time)` 块，只负责滚动缓冲追加和图像刷新调度，不再做弧度/裁剪/降采样/滤波。

### 影响与边界

- 仅改变 `snapshot_kind=3`（Time-Space 增量全窗口）的显示快照形态；`snapshot_kind=0/1/2`（Tab1 波形/频谱/监测）仍按原样传递，Tab1 的弧度转换仍在 GUI 按最小渲染数组延迟执行。
- 完整采集数据、保存和 TCP 链路不受影响：`_dispatch_full_data()` 仍先于显示路径接收原始 `int32` 块。
- 显示侧弧度/裁剪/降采样结果与旧 `_build_display_block()` 逻辑一致，Time-Space 滚动缓冲语义不变。
- 实时滤波由采集线程内的独立实例承担，滤波开关与截止频率通过 `set_display_transform()` 同步。

### 验证

- `python -m py_compile src\acquisition_thread.py src\main_window.py src\time_space_plot.py` 通过。
- `python -m unittest discover -s tests -p "test_*.py"` 7 项全部通过，含更新后的 `test_time_space_incremental_snapshots_do_not_overlap`（校验 `snapshot_kind=3` 返回预变换 `(space, time)` 块与元数据）。
- 离屏自检：`rad=True, dist=[40,100), space_ds=2, time_ds=50` 时，块形状为 `(30, 8)`、dtype `float32`，弧度缩放与 `raw.reshape(400,512)[:, 40:100:2] * (pi/32767)` 逐值一致。
- 仍需现场硬件复测：观察 `_on_phase_data` 是否回落到几十毫秒量级、`last_display_transform_ms` 是否稳定、`gui_interval_ms` 是否持续接近 400 ms，以及 `buffer/expected` 是否不再长时间积压。

## 2026-08-18 Tab3 TCP comm_count假对齐风险修复

### 背景

为配合 `wb-monitor` 做 FIP+eDAS 联调，复查了 `src/tcp_tab3/` 的发送链路。当前联调目标约为 100 kHz x 800 点，即每秒 80,000,000 个数；若按现有协议 `float64` 发送，满速 1 s payload 约 610 MiB。

本次发现一个比吞吐更隐蔽的对齐风险：旧实现由 `TCPSenderWorker` 在 `sendall()` 成功后才递增 `_comm_count`。当网络未连接、发送失败或发送队列丢弃旧包时，被丢弃的采集块不会消耗序号。下游 `wb-monitor` 会看到连续的 eDAS `comm_count`，但实际采集时间已经跳过，导致 FIP/eDAS 同序号看似对齐、物理时间不对齐。

### 修改

- `src/tcp_tab3/tcp_types.py`
  - `PhaseQueueItem` 新增 `comm_count` 字段。

- `src/tcp_tab3/tcp_tab3_manager.py`
  - 新增 `_next_comm_count`，采集会话开始时清零。
  - 在 `_append_comm_frames()` 将完整采集帧聚合成一个通信包时立即分配并递增 `comm_count`。
  - 因此发送队列后续丢旧包、网络重连或发送失败都不会重写已形成包的序号。

- `src/tcp_tab3/tcp_sender_worker.py`
  - 构包时使用 `item.comm_count`。
  - 移除“发送成功后递增内部 `_comm_count`”逻辑。

- `tests/test_tcp_tab3_comm_count.py`
  - 新增测试，验证连续形成的通信包在进入发送队列前已获得 `[0, 1, 2]` 序号。

### 影响

- 接收端现在可以通过 `comm_count` 缺口识别真实 eDAS 数据缺失。
- FIP/eDAS 联合对齐不再被网络或发送队列丢包掩盖。
- 统计中的 `last_comm_count` 仍为最后成功发送的包序号，因此现场日志可以同时看到发送成功进度与缺包位置。

### 验证

```text
python -X utf8 -m py_compile src\tcp_tab3\tcp_types.py src\tcp_tab3\tcp_tab3_manager.py src\tcp_tab3\tcp_sender_worker.py
python -X utf8 -m unittest tests.test_tcp_tab3_comm_count
python -X utf8 -m unittest discover -s tests
```

结果：

```text
Ran 1 test in 0.002s
OK

Ran 8 tests in 5.286s
OK
```

### 联调关注点

- 若 `tcp_ingest_dropped`、`dropped_packets` 或 `Connect failed` 出现，`wb-monitor` 端应出现对应 `DAS comm_count gap`，不能再表现为 eDAS 序号连续。
- 满速 1 s 包约 610 MiB，长期联调建议优先在本发送端配置 `time_downsample` 或 `space_downsample`，把下游接收、绘图和联合存储压力降到可持续范围。
