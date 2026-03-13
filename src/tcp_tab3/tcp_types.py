"""Types for Tab3 TCP communication."""

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
