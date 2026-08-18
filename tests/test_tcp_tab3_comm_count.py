import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tcp_tab3.tcp_tab3_manager import TCPTab3Manager
from tcp_tab3.tcp_types import CommSettings


class _CaptureWorker:
    def __init__(self) -> None:
        self.items = []

    def enqueue(self, item) -> None:
        self.items.append(item)

    def shutdown(self) -> None:
        pass


class TCPTab3CommCountTests(unittest.TestCase):
    def test_comm_count_is_assigned_when_packet_is_formed(self) -> None:
        manager = TCPTab3Manager()
        manager._worker.shutdown()
        capture_worker = _CaptureWorker()
        manager._worker = capture_worker
        manager._session_ready = True
        manager._next_comm_count = 0

        settings = CommSettings(
            enabled=True,
            server_ip="127.0.0.1",
            server_port=3678,
            channel_start=0,
            channel_end=1,
            time_downsample=1,
            space_downsample=1,
            comm_frames=2,
            queue_max_packets=1,
        )

        first = np.arange(4, dtype=np.int32).reshape(2, 2)
        second = np.arange(4, 8, dtype=np.int32).reshape(2, 2)
        third = np.arange(8, 12, dtype=np.int32).reshape(2, 2)

        manager._append_comm_frames(first, settings, scan_rate_hz=2, point_num_after_merge=2)
        manager._append_comm_frames(second, settings, scan_rate_hz=2, point_num_after_merge=2)
        manager._append_comm_frames(third, settings, scan_rate_hz=2, point_num_after_merge=2)

        self.assertEqual([item.comm_count for item in capture_worker.items], [0, 1, 2])
        self.assertEqual(manager._next_comm_count, 3)
        manager.shutdown()


if __name__ == "__main__":
    unittest.main()
