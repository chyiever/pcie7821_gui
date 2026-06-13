"""
`src/tcp_tab3` 子包封装 Tab3 的相位数据 TCP 通信能力。

当前设计不是把网络发送散落在主窗口或采集线程里，而是拆成参数类型定义、包构建、后台发送器和 GUI 管理器四部分。这样做的直接收益是：通信协议的字节布局、重连策略、队列丢包策略和界面状态更新可以分别演进，不必和主采集流程缠在一起。
"""
from .tcp_tab3_manager import TCPTab3Manager

__all__ = ["TCPTab3Manager"]
