"""Background sender thread for Tab3 TCP communication."""

from __future__ import annotations

import logging
import socket
import threading
import time
from collections import deque
from typing import Callable, Deque, Optional

from .tcp_packet_builder import TCPPacketBuildError, TCPPacketBuilder
from .tcp_types import PhaseQueueItem


class TCPSenderWorker:
    """Serialize and send packets in a dedicated background thread."""

    def __init__(
        self,
        stats_callback: Callable[[dict], None],
        status_callback: Callable[[dict], None],
        error_callback: Callable[[str], None],
    ) -> None:
        self._stats_callback = stats_callback
        self._status_callback = status_callback
        self._error_callback = error_callback
        self._logger = logging.getLogger(f"{__name__}.TCPSenderWorker")

        self._queue: Deque[PhaseQueueItem] = deque()
        self._queue_max_packets = 8
        self._condition = threading.Condition()
        self._running = True
        self._session_active = False
        self._socket: Optional[socket.socket] = None
        self._thread = threading.Thread(target=self._thread_loop, daemon=True)
        self._thread.start()

        self._pending_connect_after = 0.0
        self._comm_count = 0
        self._session_started_at = 0.0
        self._stats = {
            "session_active": False,
            "connected": False,
            "state": "idle",
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
            "last_error": "",
        }

    def start_session(self) -> None:
        """Reset state for a fresh acquisition session."""
        with self._condition:
            self._queue.clear()
            self._comm_count = 0
            self._pending_connect_after = 0.0
            self._session_active = True
            self._session_started_at = time.time()
            self._close_socket_locked()
            self._stats.update(
                {
                    "session_active": True,
                    "connected": False,
                    "state": "waiting",
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
                    "last_error": "",
                }
            )
            self._condition.notify_all()
        self._emit_status("waiting", "Communication session ready.")
        self._emit_stats()

    def stop_session(self) -> None:
        """Stop the current acquisition session."""
        with self._condition:
            self._session_active = False
            self._queue.clear()
            self._close_socket_locked()
            self._stats.update(
                {
                    "session_active": False,
                    "connected": False,
                    "queued_packets": 0,
                    "state": "idle",
                }
            )
            self._condition.notify_all()
        self._emit_status("idle", "Communication session stopped.")
        self._emit_stats()

    def enqueue(self, item: PhaseQueueItem) -> None:
        """Queue one acquisition block without blocking the producer."""
        with self._condition:
            if not self._session_active or not item.settings.enabled:
                return

            self._stats["acquired_packets"] += 1
            self._queue_max_packets = max(1, int(item.settings.queue_max_packets))
            while len(self._queue) >= self._queue_max_packets:
                self._queue.popleft()
                self._stats["dropped_packets"] += 1
            self._queue.append(item)
            self._stats["queued_packets"] = len(self._queue)
            self._condition.notify()
        self._emit_stats()

    def shutdown(self) -> None:
        """Terminate the worker thread."""
        with self._condition:
            self._running = False
            self._session_active = False
            self._queue.clear()
            self._close_socket_locked()
            self._condition.notify_all()
        self._thread.join(timeout=3.0)

    def _thread_loop(self) -> None:
        while True:
            with self._condition:
                while self._running and (not self._session_active or not self._queue):
                    self._condition.wait(timeout=0.5)
                if not self._running:
                    return
                item = self._queue.popleft()
                self._stats["queued_packets"] = len(self._queue)

            try:
                packet = TCPPacketBuilder.build_packet(
                    item.phase_data,
                    item.context,
                    item.settings,
                    self._comm_count,
                )
            except TCPPacketBuildError as exc:
                self._stats["dropped_packets"] += 1
                self._stats["last_error"] = str(exc)
                self._emit_error(str(exc))
                self._emit_status("error", str(exc))
                self._emit_stats()
                continue

            if not self._ensure_connected(item):
                self._stats["dropped_packets"] += 1
                self._emit_stats()
                continue

            try:
                assert self._socket is not None
                self._socket.sendall(packet.header_bytes)
                self._socket.sendall(packet.payload_bytes)
                self._comm_count += 1
                self._stats.update(
                    {
                        "connected": True,
                        "state": "sending",
                        "sent_packets": self._stats["sent_packets"] + 1,
                        "bytes_sent": self._stats["bytes_sent"] + len(packet.header_bytes) + len(packet.payload_bytes),
                        "last_comm_count": packet.comm_count,
                        "channel_count": packet.channel_count,
                        "sample_rate_hz": packet.sample_rate_hz,
                        "packet_duration_seconds": packet.packet_duration_seconds,
                        "data_bytes": packet.data_bytes,
                        "last_error": "",
                    }
                )
                self._emit_status(
                    "sending",
                    f"Connected to {item.settings.server_ip}:{item.settings.server_port}",
                )
                self._emit_stats()
            except OSError as exc:
                self._handle_socket_error(item, f"Send failed: {exc}")

    def _ensure_connected(self, item: PhaseQueueItem) -> bool:
        if self._socket is not None:
            return True

        now = time.time()
        if now < self._pending_connect_after:
            self._emit_status("reconnecting", "Waiting before reconnect.")
            return False

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(2.0)
            sock.connect((item.settings.server_ip, item.settings.server_port))
            sock.settimeout(None)
            self._socket = sock
            self._stats["connected"] = True
            self._emit_status("connected", f"Connected to {item.settings.server_ip}:{item.settings.server_port}")
            return True
        except OSError as exc:
            self._pending_connect_after = now + max(0.2, float(item.settings.reconnect_interval_s))
            self._stats["connected"] = False
            self._stats["state"] = "reconnecting"
            self._stats["last_error"] = str(exc)
            self._emit_error(f"Connect failed: {exc}")
            self._emit_status("reconnecting", f"Connect failed: {exc}")
            return False

    def _handle_socket_error(self, item: PhaseQueueItem, message: str) -> None:
        self._logger.warning(message)
        with self._condition:
            self._close_socket_locked()
            self._pending_connect_after = time.time() + max(0.2, float(item.settings.reconnect_interval_s))
            self._stats["connected"] = False
            self._stats["state"] = "reconnecting"
            self._stats["last_error"] = message
        self._emit_error(message)
        self._emit_status("reconnecting", message)
        self._emit_stats()

    def _close_socket_locked(self) -> None:
        if self._socket is None:
            return
        try:
            self._socket.close()
        except OSError:
            pass
        self._socket = None

    def _emit_stats(self) -> None:
        self._stats_callback(dict(self._stats))

    def _emit_status(self, state: str, message: str) -> None:
        payload = {
            "state": state,
            "message": message,
            "connected": bool(self._stats.get("connected", False)),
        }
        self._stats["state"] = state
        self._status_callback(payload)

    def _emit_error(self, message: str) -> None:
        self._error_callback(message)
