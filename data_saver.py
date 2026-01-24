"""
PCIe-7821 Data Saver Module
Asynchronous data saving with queue-based buffering
"""

import os
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional
import numpy as np


class DataSaver:
    """
    Asynchronous data saver with queue-based buffering.

    Saves data to binary files in the format: {file_no}-{HH}-{MM}-{SS}_D.bin
    """

    def __init__(self, save_path: str = "save_data", buffer_size: int = 100):
        """
        Initialize data saver.

        Args:
            save_path: Directory to save files
            buffer_size: Maximum number of data blocks in queue
        """
        self.save_path = Path(save_path)
        self.buffer_size = buffer_size

        self._data_queue: queue.Queue = queue.Queue(maxsize=buffer_size)
        self._save_thread: Optional[threading.Thread] = None
        self._running = False
        self._file_handle = None
        self._file_no = 0
        self._current_filename = ""

        # Statistics
        self._bytes_written = 0
        self._blocks_written = 0
        self._dropped_blocks = 0

    def start(self, file_no: Optional[int] = None) -> str:
        """
        Start data saving.

        Args:
            file_no: Optional file number. If None, auto-increment.

        Returns:
            The filename being written to
        """
        if self._running:
            return self._current_filename

        # Ensure save directory exists
        self.save_path.mkdir(parents=True, exist_ok=True)

        # Set file number
        if file_no is not None:
            self._file_no = file_no
        else:
            self._file_no += 1

        # Create filename with timestamp
        now = datetime.now()
        self._current_filename = f"{self._file_no:03d}-{now.hour:02d}-{now.minute:02d}-{now.second:02d}_D.bin"

        # Open file
        filepath = self.save_path / self._current_filename
        self._file_handle = open(filepath, 'wb')

        # Reset statistics
        self._bytes_written = 0
        self._blocks_written = 0
        self._dropped_blocks = 0

        # Clear queue
        while not self._data_queue.empty():
            try:
                self._data_queue.get_nowait()
            except queue.Empty:
                break

        # Start save thread
        self._running = True
        self._save_thread = threading.Thread(target=self._save_loop, daemon=True)
        self._save_thread.start()

        return self._current_filename

    def stop(self):
        """Stop data saving and close file"""
        if not self._running:
            return

        self._running = False

        # Wait for save thread to finish
        if self._save_thread is not None:
            # Put sentinel to wake up thread
            try:
                self._data_queue.put(None, timeout=0.1)
            except queue.Full:
                pass

            self._save_thread.join(timeout=2.0)
            self._save_thread = None

        # Flush remaining data
        while not self._data_queue.empty():
            try:
                data = self._data_queue.get_nowait()
                if data is not None and self._file_handle is not None:
                    self._write_data(data)
            except queue.Empty:
                break

        # Close file
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None

    def save(self, data: np.ndarray) -> bool:
        """
        Queue data for saving.

        Args:
            data: NumPy array to save

        Returns:
            True if data was queued, False if queue is full
        """
        if not self._running:
            return False

        try:
            self._data_queue.put_nowait(data.tobytes())
            return True
        except queue.Full:
            self._dropped_blocks += 1
            return False

    def _save_loop(self):
        """Background thread for saving data"""
        while self._running:
            try:
                data = self._data_queue.get(timeout=0.1)
                if data is None:  # Sentinel
                    continue
                self._write_data(data)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"DataSaver error: {e}")

    def _write_data(self, data: bytes):
        """Write data to file"""
        if self._file_handle is not None:
            self._file_handle.write(data)
            self._bytes_written += len(data)
            self._blocks_written += 1

    @property
    def is_running(self) -> bool:
        """Check if saver is running"""
        return self._running

    @property
    def bytes_written(self) -> int:
        """Get total bytes written"""
        return self._bytes_written

    @property
    def blocks_written(self) -> int:
        """Get total blocks written"""
        return self._blocks_written

    @property
    def dropped_blocks(self) -> int:
        """Get number of dropped blocks due to queue full"""
        return self._dropped_blocks

    @property
    def queue_size(self) -> int:
        """Get current queue size"""
        return self._data_queue.qsize()

    @property
    def current_filename(self) -> str:
        """Get current filename"""
        return self._current_filename

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
        return False

    def __del__(self):
        """Destructor"""
        self.stop()


class MultiFileSaver(DataSaver):
    """
    Data saver that creates new files based on size or time limits.
    """

    def __init__(self, save_path: str = "save_data",
                 max_file_size_mb: float = 1024,
                 max_file_duration_s: float = 0,
                 buffer_size: int = 100):
        """
        Initialize multi-file saver.

        Args:
            save_path: Directory to save files
            max_file_size_mb: Maximum file size in MB (0 = unlimited)
            max_file_duration_s: Maximum file duration in seconds (0 = unlimited)
            buffer_size: Maximum number of data blocks in queue
        """
        super().__init__(save_path, buffer_size)
        self.max_file_size = int(max_file_size_mb * 1024 * 1024) if max_file_size_mb > 0 else 0
        self.max_duration = max_file_duration_s
        self._file_start_time: Optional[datetime] = None

    def start(self, file_no: Optional[int] = None) -> str:
        """Start saving with auto-split capability"""
        self._file_start_time = datetime.now()
        return super().start(file_no)

    def save(self, data: np.ndarray) -> bool:
        """Save data with auto-split check"""
        if not self._running:
            return False

        # Check if need to create new file
        should_split = False

        if self.max_file_size > 0 and self._bytes_written >= self.max_file_size:
            should_split = True

        if self.max_duration > 0 and self._file_start_time is not None:
            elapsed = (datetime.now() - self._file_start_time).total_seconds()
            if elapsed >= self.max_duration:
                should_split = True

        if should_split:
            self._split_file()

        return super().save(data)

    def _split_file(self):
        """Close current file and open new one"""
        # Close current file
        if self._file_handle is not None:
            self._file_handle.close()

        # Increment file number and create new file
        self._file_no += 1
        now = datetime.now()
        self._current_filename = f"{self._file_no:03d}-{now.hour:02d}-{now.minute:02d}-{now.second:02d}_D.bin"

        filepath = self.save_path / self._current_filename
        self._file_handle = open(filepath, 'wb')
        self._bytes_written = 0
        self._file_start_time = now
