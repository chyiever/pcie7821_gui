"""Manager that bridges GUI acquisition callbacks to the TCP sender worker."""

from __future__ import annotations

from typing import Dict

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

        self._worker.start_session()
        self._session_ready = True
        return True

    def stop_session(self) -> None:
        """Stop the current communication session."""
        self._session_ready = False
        self._worker.stop_session()

    def enqueue_phase_data(self, phase_data, params: AllParams, settings_dict: Dict[str, object]) -> None:
        """Queue one raw phase block for background transmission."""
        if not self._session_ready:
            return

        settings = CommSettings(
            enabled=bool(settings_dict.get("enabled", True)),
            server_ip=str(settings_dict.get("server_ip", "169.255.1.2")),
            server_port=int(settings_dict.get("server_port", 3678)),
            channel_start=int(settings_dict.get("channel_start", 50)),
            channel_end=int(settings_dict.get("channel_end", 100)),
            time_downsample=int(settings_dict.get("time_downsample", 1)),
            space_downsample=int(settings_dict.get("space_downsample", 1)),
            reconnect_interval_s=float(settings_dict.get("reconnect_interval_s", 1.0)),
            queue_max_packets=int(settings_dict.get("queue_max_packets", 8)),
        )
        if not settings.enabled:
            return

        context = AcquisitionContext(
            scan_rate_hz=int(params.basic.scan_rate),
            frame_num=int(params.display.frame_num),
            point_num_after_merge=calculate_cropped_point_count(
                calculate_phase_point_num(
                    params.basic.point_num_per_scan,
                    params.phase_demod.merge_point_num,
                ),
                params.phase_demod.crop_distance_start,
                params.phase_demod.crop_distance_end,
            ),
        )
        item = PhaseQueueItem(phase_data=phase_data, settings=settings, context=context)
        self._worker.enqueue(item)

    def _emit_status(self, payload: dict) -> None:
        self.status_changed.emit(payload)

    def _emit_stats(self, payload: dict) -> None:
        self.statistics_changed.emit(payload)

    def _emit_error(self, message: str) -> None:
        self.error_occurred.emit(message)
