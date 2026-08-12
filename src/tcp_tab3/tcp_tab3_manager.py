"""
`src/tcp_tab3/tcp_tab3_manager.py` 是 Tab3 GUI 与后台 TCP 发送器之间的管理层。

主窗口不直接操作 socket，也不直接拼包，而是把当前采集参数与 Tab3 设置交给本模块。本模块负责判断当前采集模式是否允许通信，在采集开始和结束时开启或关闭会话，并把相位完整块转换成 `PhaseQueueItem` 入队给后台发送器。

这个管理层的价值在于把“业务可用性判断”和“纯网络执行逻辑”分开。这样协议限制、界面提示和后台重连策略就不会相互污染。
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from PyQt5.QtCore import QObject, pyqtSignal

from config import AllParams, DataSource, calculate_cropped_point_count, calculate_phase_point_num

from .tcp_sender_worker import TCPSenderWorker
from .tcp_types import AcquisitionContext, CommSettings, PhaseQueueItem


class TCPTab3Manager(QObject):
    """Own the Tab3 communication state and worker thread."""

    status_changed = pyqtSignal(dict)
    statistics_changed = pyqtSignal(dict)
    availability_changed = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._worker = TCPSenderWorker(self._emit_stats, self._emit_status, self._emit_error)
        self._enabled = True
        self._session_ready = False
        self._availability_reason = "Waiting for acquisition parameters."
        self._pending_comm_chunks: List[np.ndarray] = []
        self._pending_comm_frames = 0
        self._pending_comm_signature = None

    def shutdown(self) -> None:
        """Release the background worker."""
        self._worker.shutdown()

    def update_enabled(self, enabled: bool, params: AllParams) -> None:
        """Update the UI master switch and publish availability."""
        self._enabled = bool(enabled)
        self.publish_availability(params)

    def publish_availability(self, params: AllParams) -> bool:
        """Recompute whether communication is allowed for the current acquisition mode."""
        allowed = True
        reason = "Ready."
        if params.upload.channel_num != 1:
            allowed = False
            reason = "Communication requires upload.channel_num = 1."
        elif params.upload.data_source != DataSource.PHASE:
            allowed = False
            reason = "Communication requires PHASE data source."
        elif params.basic.scan_rate <= 0:
            allowed = False
            reason = "Invalid scan rate."
        elif params.phase_demod.merge_point_num <= 0:
            allowed = False
            reason = "Invalid merge setting."
        else:
            load_frames = max(1, int(getattr(params.display, "frame_load_num", 1)))
            comm_frames = max(1, int(getattr(params.comm, "comm_frame_num", load_frames)))
            if comm_frames % load_frames != 0:
                allowed = False
                reason = "Length/Comm must be an integer multiple of Length/Load."

        if not self._enabled:
            allowed = False
            reason = "Communication disabled by user."

        self._availability_reason = reason
        self.availability_changed.emit({"available": allowed, "reason": reason})
        return allowed

    def start_session(self, params: AllParams) -> bool:
        """Prepare the worker for a new acquisition session."""
        if not self.publish_availability(params):
            self._session_ready = False
            self._emit_status({"state": "disabled", "message": self._availability_reason, "connected": False})
            self._emit_stats(
                {
                    "session_active": False,
                    "connected": False,
                    "state": "disabled",
                    "acquired_packets": 0,
                    "queued_packets": 0,
                    "sent_packets": 0,
                    "dropped_packets": 0,
                    "bytes_sent": 0,
                    "last_comm_count": -1,
                    "channel_count": 0,
                    "sample_rate_hz": 0,
                    "packet_duration_seconds": 0.0,
                    "data_bytes": 0,
                    "last_error": self._availability_reason,
                }
            )
            return False

        self._reset_pending_comm_frames()
        self._worker.start_session()
        self._session_ready = True
        return True

    def stop_session(self) -> None:
        """Stop the current communication session."""
        self._session_ready = False
        self._reset_pending_comm_frames()
        self._worker.stop_session()

    def enqueue_phase_data(self, phase_data, params: AllParams, settings_dict: Dict[str, object]) -> None:
        """Queue phase data after aggregating Length/Load blocks into Length/Comm packets."""
        if not self._session_ready:
            return

        load_frame_num = max(1, int(params.display.frame_load_num))
        comm_frames = max(
            1,
            int(settings_dict.get("comm_frames", getattr(params.comm, "comm_frame_num", load_frame_num))),
        )
        settings = CommSettings(
            enabled=bool(settings_dict.get("enabled", True)),
            server_ip=str(settings_dict.get("server_ip", "169.255.1.2")),
            server_port=int(settings_dict.get("server_port", 3678)),
            channel_start=int(settings_dict.get("channel_start", 50)),
            channel_end=int(settings_dict.get("channel_end", 100)),
            time_downsample=int(settings_dict.get("time_downsample", 1)),
            space_downsample=int(settings_dict.get("space_downsample", 1)),
            comm_frames=comm_frames,
            reconnect_interval_s=float(settings_dict.get("reconnect_interval_s", 1.0)),
            queue_max_packets=int(settings_dict.get("queue_max_packets", 8)),
        )
        if not settings.enabled:
            return
        if comm_frames % load_frame_num != 0:
            self._emit_error("Length/Comm must be an integer multiple of Length/Load.")
            return

        point_num_after_merge = calculate_cropped_point_count(
            calculate_phase_point_num(
                params.basic.point_num_per_scan,
                params.phase_demod.merge_point_num,
            ),
            params.phase_demod.crop_distance_start,
            params.phase_demod.crop_distance_end,
        )
        try:
            matrix = self._coerce_phase_block_to_matrix(
                phase_data,
                load_frame_num,
                point_num_after_merge,
            )
        except ValueError as exc:
            self._emit_error(str(exc))
            return

        self._append_comm_frames(
            matrix,
            settings,
            scan_rate_hz=int(params.basic.scan_rate),
            point_num_after_merge=point_num_after_merge,
        )


    def _reset_pending_comm_frames(self) -> None:
        self._pending_comm_chunks = []
        self._pending_comm_frames = 0
        self._pending_comm_signature = None

    def _coerce_phase_block_to_matrix(self, phase_data, frame_num: int, point_num_after_merge: int) -> np.ndarray:
        flat = np.asarray(phase_data)
        if flat.ndim > 1:
            flat = flat.reshape(-1)
        expected = int(frame_num) * int(point_num_after_merge)
        if flat.size != expected:
            raise ValueError(f"Unexpected phase block size for TCP: expected={expected}, actual={flat.size}.")
        return np.ascontiguousarray(flat.reshape(int(frame_num), int(point_num_after_merge)))

    def _append_comm_frames(
        self,
        frame_matrix: np.ndarray,
        settings: CommSettings,
        *,
        scan_rate_hz: int,
        point_num_after_merge: int,
    ) -> None:
        signature = (int(scan_rate_hz), int(point_num_after_merge), int(settings.comm_frames))
        if self._pending_comm_signature != signature:
            self._reset_pending_comm_frames()
            self._pending_comm_signature = signature

        self._pending_comm_chunks.append(np.ascontiguousarray(frame_matrix))
        self._pending_comm_frames += int(frame_matrix.shape[0])
        while self._pending_comm_frames >= settings.comm_frames:
            packet_matrix = self._take_pending_comm_frames(settings.comm_frames)
            context = AcquisitionContext(
                scan_rate_hz=int(scan_rate_hz),
                frame_num=int(packet_matrix.shape[0]),
                point_num_after_merge=int(point_num_after_merge),
            )
            item = PhaseQueueItem(
                phase_data=np.ascontiguousarray(packet_matrix.reshape(-1)),
                settings=settings,
                context=context,
            )
            self._worker.enqueue(item)

    def _take_pending_comm_frames(self, frame_count: int) -> np.ndarray:
        remaining = int(frame_count)
        parts: List[np.ndarray] = []
        while remaining > 0 and self._pending_comm_chunks:
            chunk = self._pending_comm_chunks[0]
            take = min(remaining, int(chunk.shape[0]))
            parts.append(chunk[:take])
            if take == chunk.shape[0]:
                self._pending_comm_chunks.pop(0)
            else:
                self._pending_comm_chunks[0] = chunk[take:]
            self._pending_comm_frames -= take
            remaining -= take

        if not parts:
            width = 0
            if self._pending_comm_signature is not None:
                width = int(self._pending_comm_signature[1])
            return np.empty((0, width), dtype=np.int32)
        if len(parts) == 1:
            return np.ascontiguousarray(parts[0])
        return np.ascontiguousarray(np.concatenate(parts, axis=0))

    def _emit_status(self, payload: dict) -> None:
        self.status_changed.emit(payload)

    def _emit_stats(self, payload: dict) -> None:
        self.statistics_changed.emit(payload)

    def _emit_error(self, message: str) -> None:
        self.error_occurred.emit(message)
