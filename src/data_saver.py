"""
`src/data_saver.py` 负责把采集得到的完整数据块异步写入磁盘，是实时链路中的后台存储模块。

当前工程采用的是典型生产者-消费者模型。前台线程只做 `put_nowait()` 入队，不在采集回调里直接执行磁盘写入；后台保存线程串行取队列、必要时完成 `dtype` 统一、写入二进制文件并处理分文件请求。这样做的目标，是在采集与磁盘吞吐冲突时优先保护采集线程与 GUI 的实时性。

如果后续需要更强的数据可靠性，应在这里继续扩展文件头、元数据索引、写入确认或失败恢复策略，而不是把写盘重新塞回 GUI 线程。
"""
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import numpy as np

from logger import get_logger
from bz_format import (
    BitshuffleZstdCompressor,
    CompressedPacket,
    RawPacket,
    pack_bz_file_header,
)

log = get_logger("data_saver")


# ----- BASE DATA SAVER -----
# Single-file async saver: data queued from producer, written by background thread

class DataSaver:
    """
    Asynchronous data saver with queue-based buffering.

    Saves data to binary files in the format: {seq}-{HH}-{MM}-{SS}-{scan_rate}.bin
    Example: 1-12-30-45-2000.bin
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
        self._split_marker = object()
        self._save_thread: Optional[threading.Thread] = None
        self._running = False
        self._file_handle = None
        self._file_no = 0
        self._current_filename = ""
        self._scan_rate = 2000  # Default scan rate

        # Statistics
        self._bytes_written = 0
        self._blocks_written = 0
        self._dropped_blocks = 0
        self._enqueue_count = 0
        self._max_queue_size_seen = 0
        self._last_write_ms = 0.0
        self._last_write_bytes = 0

    def start(self, file_no: Optional[int] = None, scan_rate: int = 2000) -> str:
        """
        Start data saving.

        Args:
            file_no: Optional file number. If None, auto-increment.
            scan_rate: Scan rate in Hz for filename

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

        self._scan_rate = scan_rate

        # Create filename with timestamp and scan rate
        # Format: seq-HH-MM-SS-scanrate.bin
        now = datetime.now()
        self._current_filename = f"{self._file_no}-{now.hour:02d}-{now.minute:02d}-{now.second:02d}-{scan_rate}.bin"

        # Open file
        filepath = self.save_path / self._current_filename
        self._file_handle = open(filepath, 'wb')

        log.info(f"Started saving to {filepath} (queue_capacity={self.buffer_size})")

        # Reset statistics
        self._bytes_written = 0
        self._blocks_written = 0
        self._dropped_blocks = 0
        self._enqueue_count = 0
        self._max_queue_size_seen = 0
        self._last_write_ms = 0.0
        self._last_write_bytes = 0

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

        # Wait for save thread to drain queued data and exit.
        if self._save_thread is not None:
            try:
                self._data_queue.put(None, timeout=1.0)
            except queue.Full:
                log.warning("Save queue full while stopping; waiting to enqueue sentinel")
                self._data_queue.put(None)

            self._save_thread.join(timeout=5.0)
            self._save_thread = None

        # Close file after the save thread has finished all pending writes.
        if self._file_handle is not None:
            self._file_handle.flush()
            self._file_handle.close()
            self._file_handle = None

        log.info(f"Stopped saving. Bytes written: {self._bytes_written}, "
                 f"Blocks: {self._blocks_written}, Dropped: {self._dropped_blocks}, "
                 f"Max queue: {self._max_queue_size_seen}/{self.buffer_size}, "
                 f"Last write: {self._last_write_ms:.1f}ms/{self._last_write_bytes}B")

    def save(self, data: np.ndarray) -> bool:
        """
        Queue data for saving.

        Args:
            data: NumPy array to save (original int32 phase data, no rad conversion applied)

        Returns:
            True if data was queued, False if queue is full
        """
        if not self._running:
            return False

        try:
            # Keep queueing non-blocking; serialization is deferred to the save thread
            # so the GUI thread only enqueues a reference to the latest numpy block.
            self._data_queue.put_nowait(data)
            self._enqueue_count += 1
            queue_size = self._data_queue.qsize()
            self._max_queue_size_seen = max(self._max_queue_size_seen, queue_size)
            if (
                self._enqueue_count <= 3
                or self._enqueue_count % 20 == 0
                or queue_size >= max(1, self.buffer_size // 2)
            ):
                block_bytes = int(data.nbytes) if isinstance(data, np.ndarray) else len(data)
                log.debug(
                    f"Queued save block #{self._enqueue_count}: bytes={block_bytes}, "
                    f"queue={queue_size}/{self.buffer_size}"
                )
            return True
        except queue.Full:
            self._dropped_blocks += 1
            block_bytes = int(data.nbytes) if isinstance(data, np.ndarray) else len(data)
            log.warning(
                f"Save queue full, dropping block: bytes={block_bytes}, "
                f"dropped={self._dropped_blocks}, queue={self._data_queue.qsize()}/{self.buffer_size}"
            )
            return False

    def _save_loop(self):
        """Background thread for saving data"""
        while True:
            try:
                item = self._data_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            except Exception as e:
                log.error(f"DataSaver error: {e}")
                continue

            try:
                if item is None:  # Sentinel
                    break
                if item is self._split_marker:
                    self._handle_split_request()
                    continue
                self._write_data(item)
            except Exception as e:
                log.error(f"DataSaver error: {e}")

    def _handle_split_request(self):
        """Handle a queued split request. Base saver does not split files."""
        return

    def _write_data(self, data):
        """Serialize one queued block and write it to disk."""
        if self._file_handle is not None:
            start = time.perf_counter()
            if isinstance(data, np.ndarray):
                if data.dtype != np.int32:
                    data = data.astype(np.int32)
                payload = data.tobytes()
            else:
                payload = data

            self._file_handle.write(payload)
            self._last_write_ms = (time.perf_counter() - start) * 1000
            self._last_write_bytes = len(payload)
            self._bytes_written += len(payload)
            self._blocks_written += 1
            if self._last_write_ms > 50:
                log.warning(
                    f"Slow disk write: {self._last_write_ms:.1f}ms, bytes={len(payload)}, "
                    f"queue={self._data_queue.qsize()}/{self.buffer_size}"
                )

    def get_diagnostics_snapshot(self) -> dict:
        """Return save-thread diagnostics for periodic logging."""
        return {
            "queue_size": self.queue_size,
            "buffer_size": self.buffer_size,
            "dropped_blocks": self._dropped_blocks,
            "blocks_written": self._blocks_written,
            "bytes_written": self._bytes_written,
            "enqueue_count": self._enqueue_count,
            "max_queue_size_seen": self._max_queue_size_seen,
            "last_write_ms": self._last_write_ms,
            "last_write_bytes": self._last_write_bytes,
            "is_running": self._running,
        }

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

    @property
    def file_no(self) -> int:
        """Get current file number"""
        return self._file_no

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


# ----- BLOCK-BASED FILE SAVER -----
# Primary saver: splits files after N complete acquisition blocks for manageable file sizes.
# Filename: {seq}-eDAS-{rate}Hz-{points}pt-{timestamp}.{ms}.bin

class BlockBasedFileSaver(DataSaver):
    """
    Block-based file saver that creates new files after N acquisition blocks.
    One block is the complete payload produced by one FrameLoad read.

    Filename format: {seq}-eDAS-{rate}Hz-{points}pt-{timestamp}.{ms}.bin
    Example: 0000001-eDAS-1000Hz-0162pt-20260126T014051.256.bin
    """

    def __init__(self, save_path: str = "D:/eDAS_DATA",
                 blocks_per_file: int = 10,
                 buffer_size: int = 200,
                 frames_per_file: Optional[int] = None):
        """
        Initialize block-based file saver.

        Args:
            save_path: Directory to save files (default D:/eDAS_DATA)
            blocks_per_file: Number of complete acquisition blocks per file (default 10)
            buffer_size: Maximum number of data blocks in queue (increased to 200)
            frames_per_file: Backward-compatible alias for blocks_per_file
        """
        super().__init__(save_path, buffer_size)
        if frames_per_file is not None:
            blocks_per_file = frames_per_file
        self.blocks_per_file = blocks_per_file
        self._block_count = 0
        self._total_bytes_all_files = 0
        self._total_files_created = 0
        self._scan_rate = 2000
        self._points_per_frame = 0
        self._blocks_per_file = blocks_per_file

    def start(self, file_no: Optional[int] = None, scan_rate: int = 2000,
              points_per_frame: int = 0) -> str:
        """Start saving with block-based splitting capability"""
        if self._running:
            return self._current_filename

        # Ensure save directory exists
        self.save_path.mkdir(parents=True, exist_ok=True)

        # Set file number
        if file_no is not None:
            self._file_no = file_no
        else:
            self._file_no += 1

        self._scan_rate = scan_rate
        self._points_per_frame = points_per_frame
        self._block_count = 0
        self._total_files_created = 1

        # Create filename: seq-eDAS-rateHz-pointspt-timestamp.ms.bin
        self._current_filename = self._generate_filename()

        # Open file
        filepath = self.save_path / self._current_filename
        self._file_handle = open(filepath, 'wb')

        log.info(f"Started block-based saving to {filepath}")

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

    def save_block(self, block_data: np.ndarray) -> bool:
        """
        Save one complete acquisition block and check for file splitting.

        Args:
            block_data: Complete acquisition block array

        Returns:
            True if block was queued successfully
        """
        if not self._running:
            return False

        success = self.save(block_data)

        if success:
            self._block_count += 1
            log.debug(f"Saved block {self._block_count}/{self.blocks_per_file}")

            if self._block_count >= self.blocks_per_file:
                if self._split_file():
                    self._block_count = 0

        return success

    def save_frame(self, frame_data: np.ndarray) -> bool:
        """Backward-compatible alias for older callers; the payload is a block."""
        return self.save_block(frame_data)

    def _generate_filename(self) -> str:
        """Generate filename with new format"""
        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%dT%H%M%S")
        milliseconds = int((now.timestamp() % 1) * 1000)

        filename = (f"{self._file_no:07d}-eDAS-{self._scan_rate:04d}Hz-"
                   f"{self._points_per_frame:04d}pt-{timestamp_str}.{milliseconds:03d}.bin")

        return filename

    def _split_file(self) -> bool:
        """Queue a split request so rotation happens in the save thread after pending writes."""
        try:
            self._data_queue.put_nowait(self._split_marker)
            return True
        except queue.Full:
            log.warning("Deferred file split because save queue is full")
            return False

    def _handle_split_request(self):
        """Close current file and open new one in the save thread."""
        self._total_bytes_all_files += self._bytes_written

        if self._file_handle is not None:
            self._file_handle.flush()
            self._file_handle.close()

        self._file_no += 1
        self._current_filename = self._generate_filename()

        filepath = self.save_path / self._current_filename
        self._file_handle = open(filepath, 'wb')
        self._bytes_written = 0
        self._total_files_created += 1

        log.info(f"Split to new file: {self._current_filename} (File #{self._total_files_created})")

    def stop(self):
        """Stop and update total statistics"""
        super().stop()
        log.info(f"Total files created: {self._total_files_created}, "
                 f"Total blocks saved: {(self._total_files_created - 1) * self.blocks_per_file + self._block_count}, "
                 f"Total bytes: {self.total_bytes_all_files}")

    @property
    def total_bytes_all_files(self) -> int:
        """Get total bytes written across all files"""
        return self._total_bytes_all_files + self._bytes_written

    @property
    def total_files_created(self) -> int:
        """Get total number of files created"""
        return self._total_files_created

    @property
    def block_count(self) -> int:
        """Get current block count in active file"""
        return self._block_count

    @property
    def blocks_per_file(self) -> int:
        """Get blocks per file setting"""
        return self._blocks_per_file

    @blocks_per_file.setter
    def blocks_per_file(self, value: int):
        """Set blocks per file"""
        self._blocks_per_file = value

    @property
    def frame_count(self) -> int:
        """Backward-compatible alias for block_count."""
        return self.block_count

    @property
    def frames_per_file(self) -> int:
        """Backward-compatible alias for blocks_per_file."""
        return self.blocks_per_file

    @frames_per_file.setter
    def frames_per_file(self, value: int):
        """Backward-compatible alias for blocks_per_file."""
        self.blocks_per_file = value



# ----- BITSHUFFLE + ZSTD FILE SAVER -----
# Packetizes int32 acquisition data and writes self-describing .bz files.

class BitshuffleZstdFileSaver(DataSaver):
    """
    Real-time packetized saver using Bitshuffle + Zstd.

    The producer path remains non-blocking. Acquisition blocks are queued into a
    bounded raw queue, a compression thread aggregates frames into packet-sized
    matrices, and a writer thread appends packet headers plus compressed payloads
    to .bz files.
    """

    def __init__(self, save_path: str = "D:/eDAS_DATA",
                 file_duration_s: int = 60,
                 packet_frames: int = 0,
                 zstd_level: int = 3,
                 bitshuffle_block_values: int = 65536,
                 buffer_size: int = 200,
                 compressed_queue_size: int = 8):
        super().__init__(save_path, buffer_size)
        self.file_duration_s = max(1, int(file_duration_s))
        self.packet_frames = max(0, int(packet_frames))
        self.zstd_level = int(zstd_level)
        self.bitshuffle_block_values = max(1, int(bitshuffle_block_values))
        self.compressed_queue_size = max(1, int(compressed_queue_size))
        self._compressed_queue: queue.Queue = queue.Queue(maxsize=self.compressed_queue_size)
        self._compress_thread: Optional[threading.Thread] = None
        self._writer_thread: Optional[threading.Thread] = None
        self._compressor: Optional[BitshuffleZstdCompressor] = None
        self._pending_chunks: List[np.ndarray] = []
        self._pending_frames = 0
        self._packet_index = 0
        self._points_per_frame = 0
        self._packet_points_per_frame = 0
        self._channel_num = 1
        self._data_source = 0
        self._storage_downsample_factor = 1
        self._resolved_packet_frames = 0
        self._file_frames_per_file = 0
        self._file_frames_written = 0
        self._total_bytes_all_files = 0
        self._total_files_created = 0
        self._packets_compressed = 0
        self._packets_written = 0
        self._last_compress_ms = 0.0
        self._max_compress_ms = 0.0
        self._last_compression_ratio = 0.0
        self._compression_not_realtime_count = 0
        self._dropped_samples = 0

    def start(self, file_no: Optional[int] = None, scan_rate: int = 2000,
              points_per_frame: int = 0, channel_num: int = 1,
              data_source: int = 0, storage_downsample_factor: int = 1) -> str:
        """Start .bz saving with packetized compression."""
        if self._running:
            return self._current_filename
        if points_per_frame <= 0:
            raise ValueError("points_per_frame must be greater than 0 for .bz storage")

        self.save_path.mkdir(parents=True, exist_ok=True)
        if file_no is not None:
            self._file_no = file_no
        else:
            self._file_no += 1

        self._scan_rate = max(1, int(scan_rate))
        self._points_per_frame = max(1, int(points_per_frame))
        self._channel_num = max(1, int(channel_num or 1))
        self._data_source = int(data_source)
        self._storage_downsample_factor = max(1, int(storage_downsample_factor or 1))
        self._packet_points_per_frame = self._points_per_frame * self._channel_num
        self._resolved_packet_frames = self.packet_frames if self.packet_frames > 0 else self._scan_rate
        self._file_frames_per_file = max(1, int(round(self.file_duration_s * self._scan_rate)))

        self._bytes_written = 0
        self._blocks_written = 0
        self._dropped_blocks = 0
        self._enqueue_count = 0
        self._max_queue_size_seen = 0
        self._last_write_ms = 0.0
        self._last_write_bytes = 0
        self._pending_chunks = []
        self._pending_frames = 0
        self._packet_index = 0
        self._file_frames_written = 0
        self._total_bytes_all_files = 0
        self._total_files_created = 0
        self._packets_compressed = 0
        self._packets_written = 0
        self._last_compress_ms = 0.0
        self._max_compress_ms = 0.0
        self._last_compression_ratio = 0.0
        self._compression_not_realtime_count = 0
        self._dropped_samples = 0

        self._clear_queue(self._data_queue)
        self._clear_queue(self._compressed_queue)
        self._compressor = BitshuffleZstdCompressor(
            zstd_level=self.zstd_level,
            block_values=self.bitshuffle_block_values,
        )
        self._open_new_file()

        self._running = True
        self._compress_thread = threading.Thread(target=self._compression_loop, daemon=True)
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._compress_thread.start()
        self._writer_thread.start()

        log.info(
            f"Started Bitshuffle+Zstd saving to {self.save_path / self._current_filename} "
            f"(zstd_level={self.zstd_level}, bitshuffle_block={self.bitshuffle_block_values}, "
            f"packet_frames={self._resolved_packet_frames}, file_duration_s={self.file_duration_s}, "
            f"raw_queue=0/{self.buffer_size}, compressed_queue=0/{self.compressed_queue_size}, cache=False)"
        )
        return self._current_filename

    def _clear_queue(self, target_queue: queue.Queue):
        while not target_queue.empty():
            try:
                target_queue.get_nowait()
            except queue.Empty:
                break

    def _generate_filename(self) -> str:
        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%dT%H%M%S")
        milliseconds = int((now.timestamp() % 1) * 1000)
        return (f"{self._file_no:07d}-eDAS-{self._scan_rate:04d}Hz-"
                f"{self._points_per_frame:04d}pt-{timestamp_str}.{milliseconds:03d}.bz")

    def _open_new_file(self):
        self._current_filename = self._generate_filename()
        filepath = self.save_path / self._current_filename
        self._file_handle = open(filepath, "wb", buffering=1024 * 1024)
        header = pack_bz_file_header(
            scan_rate_hz=self._scan_rate,
            points_per_frame=self._points_per_frame,
            channel_num=self._channel_num,
            data_source=self._data_source,
            storage_downsample_factor=self._storage_downsample_factor,
            packet_frames=self._resolved_packet_frames,
            file_duration_s=self.file_duration_s,
            zstd_level=self.zstd_level,
            bitshuffle_block_values=self.bitshuffle_block_values,
        )
        self._file_handle.write(header)
        self._bytes_written = len(header)
        self._file_frames_written = 0
        self._total_files_created += 1
        log.info(f"Opened .bz file: {filepath}")

    def _rotate_file(self):
        if self._file_handle is not None:
            self._file_handle.flush()
            self._file_handle.close()
        self._total_bytes_all_files += self._bytes_written
        self._file_no += 1
        self._open_new_file()

    def save_block(self, block_data: np.ndarray) -> bool:
        """Queue one complete acquisition block for .bz packetization."""
        return self.save(block_data)

    def save_frame(self, frame_data: np.ndarray) -> bool:
        """Backward-compatible alias for older callers."""
        return self.save_block(frame_data)

    def save(self, data: np.ndarray) -> bool:
        if not self._running:
            return False
        try:
            self._data_queue.put_nowait(data)
            self._enqueue_count += 1
            queue_size = self._data_queue.qsize()
            self._max_queue_size_seen = max(self._max_queue_size_seen, queue_size)
            if (
                self._enqueue_count <= 3
                or self._enqueue_count % 20 == 0
                or queue_size >= max(1, self.buffer_size // 2)
            ):
                has_cache = self._has_cache()
                block_bytes = int(data.nbytes) if isinstance(data, np.ndarray) else len(data)
                log.debug(
                    f"Queued .bz raw block #{self._enqueue_count}: bytes={block_bytes}, "
                    f"raw_queue={queue_size}/{self.buffer_size}, "
                    f"compressed_queue={self._compressed_queue.qsize()}/{self.compressed_queue_size}, "
                    f"pending_frames={self._pending_frames}, cache={has_cache}"
                )
            return True
        except queue.Full:
            self._dropped_blocks += 1
            self._compression_not_realtime_count += 1
            block_bytes = int(data.nbytes) if isinstance(data, np.ndarray) else len(data)
            log.warning(
                f"BZ raw queue full; compression is not realtime, dropping acquisition block: "
                f"bytes={block_bytes}, dropped={self._dropped_blocks}, "
                f"raw_queue={self._data_queue.qsize()}/{self.buffer_size}, "
                f"compressed_queue={self._compressed_queue.qsize()}/{self.compressed_queue_size}"
            )
            return False

    def stop(self):
        """Stop .bz saving after draining queued raw blocks and the final tail packet."""
        if not self._running:
            return

        self._running = False
        try:
            self._data_queue.put(None, timeout=1.0)
        except queue.Full:
            log.warning("BZ raw queue full while stopping; waiting to enqueue sentinel")
            self._data_queue.put(None)

        if self._compress_thread is not None:
            self._compress_thread.join(timeout=20.0)
            if self._compress_thread.is_alive():
                log.error("BZ compression thread did not stop within timeout")
            self._compress_thread = None

        if self._writer_thread is not None:
            self._writer_thread.join(timeout=20.0)
            if self._writer_thread.is_alive():
                log.error("BZ writer thread did not stop within timeout")
            self._writer_thread = None

        if self._file_handle is not None:
            self._file_handle.flush()
            self._file_handle.close()
            self._file_handle = None

        log.info(
            f"Stopped .bz saving. Files={self._total_files_created}, packets={self._packets_written}, "
            f"bytes={self.total_bytes_all_files}, dropped={self._dropped_blocks}, "
            f"raw_max_queue={self._max_queue_size_seen}/{self.buffer_size}, "
            f"compressed_queue={self._compressed_queue.qsize()}/{self.compressed_queue_size}, "
            f"compression_not_realtime={self._compression_not_realtime_count}, "
            f"max_compress_ms={self._max_compress_ms:.1f}"
        )

    def _compression_loop(self):
        while True:
            try:
                item = self._data_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            except Exception as exc:
                log.error(f"BZ compression queue error: {exc}")
                continue

            try:
                if item is None:
                    break
                frames = self._coerce_block_to_frame_matrix(item)
                if frames.size:
                    self._append_frames_and_emit_packets(frames)
            except Exception as exc:
                self._dropped_blocks += 1
                self._compression_not_realtime_count += 1
                log.exception(f"BZ compression failed; dropping block: {exc}")
            finally:
                try:
                    self._data_queue.task_done()
                except ValueError:
                    pass

        try:
            self._flush_tail_packet()
        finally:
            self._enqueue_writer_sentinel()

    def _writer_loop(self):
        while True:
            try:
                packet = self._compressed_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            except Exception as exc:
                log.error(f"BZ writer queue error: {exc}")
                continue

            try:
                if packet is None:
                    break
                self._write_compressed_packet(packet)
            except Exception as exc:
                self._dropped_blocks += 1
                log.exception(f"BZ writer failed; packet lost: {exc}")
            finally:
                try:
                    self._compressed_queue.task_done()
                except ValueError:
                    pass

    def _coerce_block_to_frame_matrix(self, data: np.ndarray) -> np.ndarray:
        arr = np.asarray(data, dtype=np.int32)
        if self._channel_num <= 1:
            flat = arr.reshape(-1)
            frame_count = flat.size // self._points_per_frame
            valid_items = frame_count * self._points_per_frame
            if valid_items < flat.size:
                dropped = flat.size - valid_items
                self._dropped_samples += dropped
                log.warning(f"BZ packetizer dropped {dropped} trailing samples that do not fill a frame")
            if frame_count <= 0:
                return np.empty((0, self._packet_points_per_frame), dtype=np.int32)
            return np.ascontiguousarray(flat[:valid_items].reshape(frame_count, self._points_per_frame))

        matrix = arr.reshape(-1, self._channel_num)
        frame_count = matrix.shape[0] // self._points_per_frame
        valid_rows = frame_count * self._points_per_frame
        if valid_rows < matrix.shape[0]:
            dropped = (matrix.shape[0] - valid_rows) * self._channel_num
            self._dropped_samples += dropped
            log.warning(f"BZ packetizer dropped {dropped} trailing channel samples that do not fill a frame")
        if frame_count <= 0:
            return np.empty((0, self._packet_points_per_frame), dtype=np.int32)
        framed = matrix[:valid_rows, :].reshape(frame_count, self._points_per_frame, self._channel_num)
        return np.ascontiguousarray(framed.reshape(frame_count, self._packet_points_per_frame))

    def _append_frames_and_emit_packets(self, frames: np.ndarray):
        self._pending_chunks.append(frames)
        self._pending_frames += int(frames.shape[0])
        while self._pending_frames >= self._resolved_packet_frames:
            packet_samples = self._take_pending_frames(self._resolved_packet_frames)
            self._compress_and_enqueue_packet(packet_samples)

    def _take_pending_frames(self, frame_count: int) -> np.ndarray:
        remaining = int(frame_count)
        parts: List[np.ndarray] = []
        while remaining > 0 and self._pending_chunks:
            chunk = self._pending_chunks[0]
            take = min(remaining, int(chunk.shape[0]))
            parts.append(chunk[:take])
            if take == chunk.shape[0]:
                self._pending_chunks.pop(0)
            else:
                self._pending_chunks[0] = chunk[take:]
            self._pending_frames -= take
            remaining -= take

        if not parts:
            return np.empty((0, self._packet_points_per_frame), dtype=np.int32)
        if len(parts) == 1:
            return np.ascontiguousarray(parts[0])
        return np.ascontiguousarray(np.concatenate(parts, axis=0))

    def _flush_tail_packet(self):
        if self._pending_frames <= 0:
            return
        packet_samples = self._take_pending_frames(self._pending_frames)
        log.info(f"Flushing final .bz tail packet with {packet_samples.shape[0]} frames")
        self._compress_and_enqueue_packet(packet_samples)

    def _compress_and_enqueue_packet(self, samples: np.ndarray):
        if self._compressor is None or samples.size == 0:
            return
        packet = RawPacket(
            packet_index=self._packet_index,
            timestamp_ns=time.time_ns(),
            scan_rate_hz=self._scan_rate,
            points_per_frame=self._packet_points_per_frame,
            frames=int(samples.shape[0]),
            samples=samples,
        )
        self._packet_index += 1
        compressed = self._compressor.compress_packet(packet)
        metrics = compressed.metrics
        compress_ms = float(metrics.get("compress_ms", 0.0))
        packet_duration_ms = packet.frames / max(1, self._scan_rate) * 1000.0
        self._packets_compressed += 1
        self._last_compress_ms = compress_ms
        self._max_compress_ms = max(self._max_compress_ms, compress_ms)
        self._last_compression_ratio = float(metrics.get("compression_ratio", 0.0))

        if compress_ms > packet_duration_ms:
            self._compression_not_realtime_count += 1
            log.warning(
                f"BZ compression not realtime: packet={packet.packet_index}, "
                f"compress_ms={compress_ms:.1f}, packet_duration_ms={packet_duration_ms:.1f}, "
                f"raw_queue={self._data_queue.qsize()}/{self.buffer_size}, "
                f"compressed_queue={self._compressed_queue.qsize()}/{self.compressed_queue_size}"
            )

        try:
            self._compressed_queue.put_nowait(compressed)
        except queue.Full:
            self._dropped_blocks += 1
            self._compression_not_realtime_count += 1
            log.warning(
                f"BZ compressed queue full; writer is not realtime, dropping packet={packet.packet_index}, "
                f"dropped={self._dropped_blocks}, compressed_queue={self._compressed_queue.qsize()}/{self.compressed_queue_size}"
            )

    def _enqueue_writer_sentinel(self):
        while True:
            try:
                self._compressed_queue.put(None, timeout=1.0)
                return
            except queue.Full:
                log.warning("BZ compressed queue full while stopping; waiting to enqueue writer sentinel")

    def _write_compressed_packet(self, packet: CompressedPacket):
        if self._file_handle is None:
            self._open_new_file()
        if self._file_frames_written >= self._file_frames_per_file:
            self._rotate_file()

        start = time.perf_counter()
        self._file_handle.write(packet.header)
        self._file_handle.write(packet.payload)
        write_bytes = len(packet.header) + len(packet.payload)
        self._last_write_ms = (time.perf_counter() - start) * 1000.0
        self._last_write_bytes = write_bytes
        self._bytes_written += write_bytes
        self._blocks_written += 1
        self._packets_written += 1
        self._file_frames_written += int(packet.metrics.get("frames", 0.0))

        if self._last_write_ms > 50:
            log.warning(
                f"Slow .bz disk write: {self._last_write_ms:.1f}ms, bytes={write_bytes}, "
                f"compressed_queue={self._compressed_queue.qsize()}/{self.compressed_queue_size}"
            )
        if self._packets_written <= 3 or self._packets_written % 20 == 0:
            log.info(
                f"Wrote .bz packet #{self._packets_written}: ratio={self._last_compression_ratio:.2f}, "
                f"compress_ms={self._last_compress_ms:.1f}, write_ms={self._last_write_ms:.1f}, "
                f"raw_queue={self._data_queue.qsize()}/{self.buffer_size}, "
                f"compressed_queue={self._compressed_queue.qsize()}/{self.compressed_queue_size}, "
                f"pending_frames={self._pending_frames}, cache={self._has_cache()}, "
                f"not_realtime={self._compression_not_realtime_count}, dropped={self._dropped_blocks}"
            )

    def _has_cache(self) -> bool:
        return (
            self._data_queue.qsize() > 0
            or self._compressed_queue.qsize() > 0
            or self._pending_frames > 0
        )

    def get_diagnostics_snapshot(self) -> dict:
        snapshot = super().get_diagnostics_snapshot()
        snapshot.update({
            "format": "bz",
            "queue_size": self.queue_size,
            "raw_queue_size": self._data_queue.qsize(),
            "compressed_queue_size": self._compressed_queue.qsize(),
            "compressed_queue_size_max": self.compressed_queue_size,
            "pending_frames": self._pending_frames,
            "packet_frames": self._resolved_packet_frames,
            "file_duration_s": self.file_duration_s,
            "packets_compressed": self._packets_compressed,
            "packets_written": self._packets_written,
            "compression_not_realtime_count": self._compression_not_realtime_count,
            "last_compress_ms": self._last_compress_ms,
            "max_compress_ms": self._max_compress_ms,
            "last_compression_ratio": self._last_compression_ratio,
            "dropped_samples": self._dropped_samples,
            "has_cache": self._has_cache(),
            "bytes_written": self.total_bytes_all_files,
        })
        return snapshot

    @property
    def queue_size(self) -> int:
        return self._data_queue.qsize()

    @property
    def total_bytes_all_files(self) -> int:
        return self._total_bytes_all_files + self._bytes_written

    @property
    def total_files_created(self) -> int:
        return self._total_files_created

    @property
    def block_count(self) -> int:
        return self._packets_written

    @property
    def blocks_per_file(self) -> int:
        return self._file_frames_per_file

FrameBasedFileSaver = BlockBasedFileSaver


# ----- TIME-BASED FILE SAVER (LEGACY) -----
# Splits files by wall-clock duration. Kept for backward compatibility.

class TimedFileSaver(DataSaver):
    """
    Legacy data saver that creates new files every N seconds.
    Kept for backward compatibility.

    Filename format: {seq}-{HH}-{MM}-{SS}-{scan_rate}.bin
    Example: 1-12-30-45-2000.bin, 2-12-30-46-2000.bin, ...
    """

    def __init__(self, save_path: str = "save_data",
                 file_duration_s: float = 1.0,
                 buffer_size: int = 100):
        """
        Initialize timed file saver.

        Args:
            save_path: Directory to save files
            file_duration_s: Duration per file in seconds (default 1.0)
            buffer_size: Maximum number of data blocks in queue
        """
        super().__init__(save_path, buffer_size)
        self.file_duration = file_duration_s
        self._file_start_time: float = 0
        self._total_bytes_all_files = 0
        self._total_files_created = 0

    def start(self, file_no: Optional[int] = None, scan_rate: int = 2000) -> str:
        """Start saving with auto-split capability"""
        self._file_start_time = time.time()
        self._total_bytes_all_files = 0
        self._total_files_created = 1
        return super().start(file_no, scan_rate)

    def save(self, data: np.ndarray) -> bool:
        """Save data with auto-split check based on time"""
        if not self._running:
            return False

        # Check if need to create new file (time-based)
        elapsed = time.time() - self._file_start_time
        if elapsed >= self.file_duration:
            self._split_file()

        return super().save(data)

    def _split_file(self):
        """Close current file and open new one"""
        # Update total bytes
        self._total_bytes_all_files += self._bytes_written

        # Close current file
        if self._file_handle is not None:
            self._file_handle.flush()
            self._file_handle.close()

        # Increment file number and create new file
        self._file_no += 1
        now = datetime.now()
        self._current_filename = f"{self._file_no}-{now.hour:02d}-{now.minute:02d}-{now.second:02d}-{self._scan_rate}.bin"

        filepath = self.save_path / self._current_filename
        self._file_handle = open(filepath, 'wb')
        self._bytes_written = 0
        self._file_start_time = time.time()
        self._total_files_created += 1

        log.info(f"Split to new file: {self._current_filename}")

    def stop(self):
        """Stop and update total statistics"""
        self._total_bytes_all_files += self._bytes_written
        super().stop()
        log.info(f"Total files created: {self._total_files_created}, "
                 f"Total bytes: {self._total_bytes_all_files}")

    @property
    def total_bytes_all_files(self) -> int:
        """Get total bytes written across all files"""
        return self._total_bytes_all_files + self._bytes_written

    @property
    def total_files_created(self) -> int:
        """Get total number of files created"""
        return self._total_files_created
