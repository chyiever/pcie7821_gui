# Development Log

本文档用于记录程序每次更新的要点、涉及范围、验证情况，以及与 Git 分支和提交对应的发布信息。

记录规则如下：

- 每次功能修改、修复或结构调整后，都在本文档末尾追加新记录。
- 记录中尽量写清楚更新时间、更新内容、涉及文件、验证方式。
- 如果代码已经推送到远端分支，需要同时写明分支名和提交号，便于后续追踪。
- `data`、`dist` 等运行产物不在本日志的代码更新范围内，除非单独说明。

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
