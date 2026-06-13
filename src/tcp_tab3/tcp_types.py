"""
`src/tcp_tab3/tcp_types.py` 定义 Tab3 通信链路使用的轻量数据结构。

这里的 dataclass 负责承载三类信息：用户在界面上配置的通信参数、从当前采集参数派生出的上下文，以及已经构建完成、准备发送或用于状态显示的出站包元数据。把这些结构独立出来后，包构建器、后台发送器和主窗口的接口会更稳定。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class CommSettings:
    """Runtime communication settings."""

    enabled: bool
    server_ip: str
    server_port: int
    channel_start: int
    channel_end: int
    time_downsample: int
    space_downsample: int
    reconnect_interval_s: float = 1.0
    queue_max_packets: int = 8


@dataclass
class AcquisitionContext:
    """Acquisition metadata needed to rebuild one outgoing packet."""

    scan_rate_hz: int
    frame_num: int
    point_num_after_merge: int


@dataclass
class OutgoingPacket:
    """Fully serialized TCP packet plus metadata for status display."""

    comm_count: int
    header_bytes: bytes
    payload_bytes: bytes
    channel_count: int
    sample_rate_hz: int
    samples_per_channel: int
    packet_duration_seconds: float
    data_bytes: int


@dataclass
class PhaseQueueItem:
    """One pending acquisition block waiting to be serialized and sent."""

    phase_data: np.ndarray
    settings: CommSettings
    context: AcquisitionContext
