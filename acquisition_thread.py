"""
PCIe-7821 Data Acquisition Thread Module
QThread-based acquisition with signal-slot communication
"""

import time
import numpy as np
from typing import Optional
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition

from pcie7821_api import PCIe7821API, PCIe7821Error
from config import DataSource, AllParams


class AcquisitionThread(QThread):
    """
    Data acquisition thread for PCIe-7821.

    Runs in a separate thread to avoid blocking the GUI.
    Uses Qt signals to communicate data to the main thread.
    """

    # Signals
    data_ready = pyqtSignal(np.ndarray, int, int)  # data, data_type, channel_num
    phase_data_ready = pyqtSignal(np.ndarray, int)  # phase_data, channel_num
    monitor_data_ready = pyqtSignal(np.ndarray, int)  # monitor_data, channel_num
    buffer_status = pyqtSignal(int, int)  # points_in_buffer, buffer_size_mb
    error_occurred = pyqtSignal(str)  # error message
    acquisition_started = pyqtSignal()
    acquisition_stopped = pyqtSignal()

    def __init__(self, api: PCIe7821API, parent=None):
        """
        Initialize acquisition thread.

        Args:
            api: PCIe7821API instance
            parent: Parent QObject
        """
        super().__init__(parent)
        self.api = api
        self._running = False
        self._paused = False

        # Parameters (will be set before starting)
        self._params: Optional[AllParams] = None
        self._total_point_num = 0
        self._point_num_after_merge = 0
        self._frame_num = 20
        self._channel_num = 1
        self._data_source = DataSource.PHASE

        # Thread synchronization
        self._mutex = QMutex()
        self._pause_condition = QWaitCondition()

        # Statistics
        self._frames_acquired = 0
        self._bytes_acquired = 0

    def configure(self, params: AllParams):
        """
        Configure acquisition parameters.

        Args:
            params: Configuration parameters
        """
        self._params = params
        self._total_point_num = params.basic.point_num_per_scan
        self._point_num_after_merge = self._total_point_num // params.phase_demod.merge_point_num
        self._frame_num = params.display.frame_num
        self._channel_num = params.upload.channel_num
        self._data_source = params.upload.data_source

    def run(self):
        """Thread main loop"""
        self._running = True
        self._frames_acquired = 0
        self._bytes_acquired = 0

        self.acquisition_started.emit()

        try:
            while self._running:
                # Check for pause
                self._mutex.lock()
                while self._paused and self._running:
                    self._pause_condition.wait(self._mutex)
                self._mutex.unlock()

                if not self._running:
                    break

                # Determine expected data size
                if self._data_source == DataSource.PHASE:
                    expected_points = self._point_num_after_merge * self._frame_num
                else:
                    expected_points = self._total_point_num * self._frame_num

                # Wait for enough data in buffer
                wait_count = 0
                while self._running:
                    points_in_buffer = self.api.query_buffer_points()

                    # Emit buffer status
                    buffer_mb = points_in_buffer * self._channel_num * 2 // (1024 * 1024)
                    self.buffer_status.emit(points_in_buffer, buffer_mb)

                    if points_in_buffer >= expected_points:
                        break

                    time.sleep(0.001)  # 1ms wait
                    wait_count += 1

                    if wait_count > 5000:  # 5 second timeout
                        self.error_occurred.emit("Timeout waiting for data")
                        break

                if not self._running:
                    break

                # Read data
                try:
                    if self._data_source == DataSource.PHASE:
                        self._read_phase_data()
                    else:
                        self._read_raw_data()
                except PCIe7821Error as e:
                    self.error_occurred.emit(str(e))
                    time.sleep(0.1)
                    continue

                self._frames_acquired += self._frame_num

        except Exception as e:
            self.error_occurred.emit(f"Acquisition error: {e}")

        finally:
            self.acquisition_stopped.emit()

    def _read_raw_data(self):
        """Read raw IQ data"""
        points_per_ch = self._total_point_num * self._frame_num
        data, points_returned = self.api.read_data(points_per_ch, self._channel_num)

        self._bytes_acquired += len(data) * 2  # short = 2 bytes

        # Reshape data by channels
        if self._channel_num > 1:
            # Data is interleaved: ch0[0], ch1[0], ch0[1], ch1[1], ...
            total_points = len(data)
            points_per_frame = self._total_point_num * self._channel_num
            data = data.reshape(-1, self._channel_num)

        self.data_ready.emit(data, self._data_source, self._channel_num)

    def _read_phase_data(self):
        """Read phase demodulated data"""
        points_per_ch = self._point_num_after_merge * self._frame_num
        phase_data, points_returned = self.api.read_phase_data(points_per_ch, self._channel_num)

        self._bytes_acquired += len(phase_data) * 4  # int = 4 bytes

        # Reshape data by channels
        if self._channel_num > 1:
            phase_data = phase_data.reshape(-1, self._channel_num)

        self.phase_data_ready.emit(phase_data, self._channel_num)

        # Also read monitor data when in phase mode
        try:
            monitor_data = self.api.read_monitor_data(
                self._point_num_after_merge, self._channel_num
            )
            self.monitor_data_ready.emit(monitor_data, self._channel_num)
        except PCIe7821Error:
            pass  # Monitor data read failure is not critical

    def stop(self):
        """Stop acquisition thread"""
        self._running = False

        # Wake up if paused
        self._mutex.lock()
        self._paused = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()

        # Wait for thread to finish
        if self.isRunning():
            self.wait(3000)  # 3 second timeout

    def pause(self):
        """Pause acquisition"""
        self._mutex.lock()
        self._paused = True
        self._mutex.unlock()

    def resume(self):
        """Resume acquisition"""
        self._mutex.lock()
        self._paused = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()

    @property
    def is_running(self) -> bool:
        """Check if acquisition is running"""
        return self._running and self.isRunning()

    @property
    def is_paused(self) -> bool:
        """Check if acquisition is paused"""
        return self._paused

    @property
    def frames_acquired(self) -> int:
        """Get number of frames acquired"""
        return self._frames_acquired

    @property
    def bytes_acquired(self) -> int:
        """Get total bytes acquired"""
        return self._bytes_acquired

    @property
    def point_num_after_merge(self) -> int:
        """Get points per scan after merge"""
        return self._point_num_after_merge

    @property
    def total_point_num(self) -> int:
        """Get total points per scan"""
        return self._total_point_num


class SimulatedAcquisitionThread(AcquisitionThread):
    """
    Simulated acquisition thread for testing without hardware.
    """

    def __init__(self, parent=None):
        """Initialize with dummy API"""
        # Create a mock API
        self._mock_api = type('MockAPI', (), {
            'query_buffer_points': lambda s: 100000,
            'read_data': lambda s, n, c: (np.random.randint(-32768, 32767, n*c, dtype=np.int16), n),
            'read_phase_data': lambda s, n, c: (np.random.randint(-100000, 100000, n*c, dtype=np.int32), n),
            'read_monitor_data': lambda s, n, c: np.random.randint(0, 65535, n*c, dtype=np.uint32),
        })()
        super().__init__(self._mock_api, parent)

    def run(self):
        """Simulated acquisition loop"""
        self._running = True
        self._frames_acquired = 0
        self._bytes_acquired = 0

        self.acquisition_started.emit()

        try:
            while self._running:
                # Check for pause
                self._mutex.lock()
                while self._paused and self._running:
                    self._pause_condition.wait(self._mutex)
                self._mutex.unlock()

                if not self._running:
                    break

                # Simulate acquisition delay
                time.sleep(self._frame_num / max(self._params.basic.scan_rate if self._params else 2000, 1))

                # Generate simulated data
                if self._data_source == DataSource.PHASE:
                    points = self._point_num_after_merge * self._frame_num
                    phase_data = np.random.randint(-100000, 100000, points * self._channel_num, dtype=np.int32)

                    if self._channel_num > 1:
                        phase_data = phase_data.reshape(-1, self._channel_num)

                    self.phase_data_ready.emit(phase_data, self._channel_num)
                    self._bytes_acquired += len(phase_data.flatten()) * 4

                    # Simulated monitor data
                    monitor_data = np.random.randint(0, 65535, self._point_num_after_merge * self._channel_num, dtype=np.uint32)
                    self.monitor_data_ready.emit(monitor_data, self._channel_num)
                else:
                    points = self._total_point_num * self._frame_num
                    data = np.random.randint(-32768, 32767, points * self._channel_num, dtype=np.int16)

                    if self._channel_num > 1:
                        data = data.reshape(-1, self._channel_num)

                    self.data_ready.emit(data, self._data_source, self._channel_num)
                    self._bytes_acquired += len(data.flatten()) * 2

                # Emit buffer status
                self.buffer_status.emit(100000, 10)

                self._frames_acquired += self._frame_num

        except Exception as e:
            self.error_occurred.emit(f"Simulation error: {e}")

        finally:
            self.acquisition_stopped.emit()
