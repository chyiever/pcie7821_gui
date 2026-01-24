"""
PCIe-7821 DLL Wrapper Module
Provides Python interface to pcie7821_api.dll using ctypes
"""

import ctypes
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import os

from config import DMA_ALIGNMENT, get_error_message


class AlignedBuffer:
    """Memory buffer with specified alignment for DMA transfers"""

    def __init__(self, size: int, dtype: np.dtype, alignment: int = DMA_ALIGNMENT):
        """
        Create an aligned memory buffer.

        Args:
            size: Number of elements
            dtype: NumPy dtype
            alignment: Byte alignment (default 4096 for DMA)
        """
        self.size = size
        self.dtype = np.dtype(dtype)
        self.alignment = alignment
        self.itemsize = self.dtype.itemsize

        # Allocate extra space for alignment
        total_bytes = size * self.itemsize + alignment
        self._raw_buffer = (ctypes.c_char * total_bytes)()

        # Calculate aligned address
        raw_addr = ctypes.addressof(self._raw_buffer)
        offset = (alignment - (raw_addr % alignment)) % alignment

        # Create numpy array view at aligned address
        self.array = np.frombuffer(
            self._raw_buffer,
            dtype=self.dtype,
            count=size,
            offset=offset
        )

        # Store pointer for ctypes
        self._aligned_addr = raw_addr + offset

    def get_ctypes_ptr(self):
        """Get ctypes pointer to aligned buffer"""
        if self.dtype == np.int16:
            return ctypes.cast(self._aligned_addr, ctypes.POINTER(ctypes.c_short))
        elif self.dtype == np.int32:
            return ctypes.cast(self._aligned_addr, ctypes.POINTER(ctypes.c_int))
        elif self.dtype == np.uint32:
            return ctypes.cast(self._aligned_addr, ctypes.POINTER(ctypes.c_uint))
        else:
            raise ValueError(f"Unsupported dtype: {self.dtype}")

    def __del__(self):
        """Ensure buffer is properly released"""
        self._raw_buffer = None
        self.array = None


class PCIe7821Error(Exception):
    """Exception for PCIe-7821 API errors"""
    def __init__(self, code: int, message: str = ""):
        self.code = code
        self.message = message or get_error_message(code)
        super().__init__(f"PCIe-7821 Error {code}: {self.message}")


class PCIe7821API:
    """Python wrapper for pcie7821_api.dll"""

    def __init__(self, dll_path: Optional[str] = None):
        """
        Initialize the DLL wrapper.

        Args:
            dll_path: Path to pcie7821_api.dll. If None, searches in default locations.
        """
        self.dll = None
        self._is_open = False

        # Find DLL
        if dll_path is None:
            dll_path = self._find_dll()

        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"DLL not found: {dll_path}")

        # Load DLL
        try:
            self.dll = ctypes.CDLL(dll_path)
        except OSError as e:
            raise RuntimeError(f"Failed to load DLL: {e}")

        # Setup function prototypes
        self._setup_prototypes()

        # Buffers for data reading
        self._raw_buffer: Optional[AlignedBuffer] = None
        self._phase_buffer: Optional[AlignedBuffer] = None
        self._monitor_buffer: Optional[AlignedBuffer] = None

    def _find_dll(self) -> str:
        """Find the DLL in default locations"""
        # Get the directory containing this script
        script_dir = Path(__file__).parent

        # Search paths
        search_paths = [
            script_dir.parent / "windows_issue" / "dll" / "x64" / "pcie7821_api.dll",
            script_dir / "pcie7821_api.dll",
            Path("pcie7821_api.dll"),
        ]

        for path in search_paths:
            if path.exists():
                return str(path)

        raise FileNotFoundError("pcie7821_api.dll not found in default locations")

    def _setup_prototypes(self):
        """Setup ctypes function prototypes"""
        # int pcie7821_open()
        self.dll.pcie7821_open.restype = ctypes.c_int
        self.dll.pcie7821_open.argtypes = []

        # void pcie7821_close()
        self.dll.pcie7821_close.restype = None
        self.dll.pcie7821_close.argtypes = []

        # int pcie7821_set_clk_src(unsigned int clk_src)
        self.dll.pcie7821_set_clk_src.restype = ctypes.c_int
        self.dll.pcie7821_set_clk_src.argtypes = [ctypes.c_uint]

        # int pcie7821_set_trig_dir(unsigned int trig_dir)
        self.dll.pcie7821_set_trig_dir.restype = ctypes.c_int
        self.dll.pcie7821_set_trig_dir.argtypes = [ctypes.c_uint]

        # int pcie7821_set_scan_rate(unsigned int scan_rate)
        self.dll.pcie7821_set_scan_rate.restype = ctypes.c_int
        self.dll.pcie7821_set_scan_rate.argtypes = [ctypes.c_uint]

        # int pcie7821_set_pusle_width(unsigned int pulse_high_width_ns)
        # Note: typo in DLL API name "pusle" instead of "pulse"
        self.dll.pcie7821_set_pusle_width.restype = ctypes.c_int
        self.dll.pcie7821_set_pusle_width.argtypes = [ctypes.c_uint]

        # int pcie7821_set_point_num_per_scan(unsigned int point_num_per_scan)
        self.dll.pcie7821_set_point_num_per_scan.restype = ctypes.c_int
        self.dll.pcie7821_set_point_num_per_scan.argtypes = [ctypes.c_uint]

        # int pcie7821_set_bypass_point_num(unsigned int bypass_point_num)
        self.dll.pcie7821_set_bypass_point_num.restype = ctypes.c_int
        self.dll.pcie7821_set_bypass_point_num.argtypes = [ctypes.c_uint]

        # int pcie7821_set_center_freq(unsigned int center_freq_hz)
        self.dll.pcie7821_set_center_freq.restype = ctypes.c_int
        self.dll.pcie7821_set_center_freq.argtypes = [ctypes.c_uint]

        # int pcie7821_set_upload_data_param(unsigned int upload_ch_num,
        #                                    unsigned int upload_data_src,
        #                                    unsigned int upload_data_rate)
        self.dll.pcie7821_set_upload_data_param.restype = ctypes.c_int
        self.dll.pcie7821_set_upload_data_param.argtypes = [
            ctypes.c_uint, ctypes.c_uint, ctypes.c_uint
        ]

        # int pcie7821_set_phase_dem_param(unsigned int data_rate2phase_dem,
        #                                  unsigned int space_avg_order,
        #                                  unsigned int space_merge_point_num,
        #                                  unsigned int space_region_diff_order,
        #                                  double detrend_filter_bw,
        #                                  unsigned int polarization_diversity_en)
        self.dll.pcie7821_set_phase_dem_param.restype = ctypes.c_int
        self.dll.pcie7821_set_phase_dem_param.argtypes = [
            ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
            ctypes.c_uint, ctypes.c_double, ctypes.c_uint
        ]

        # int pcie7821_point_num_per_ch_in_buf_query(unsigned int* p_point_num_in_buf_per_ch)
        self.dll.pcie7821_point_num_per_ch_in_buf_query.restype = ctypes.c_int
        self.dll.pcie7821_point_num_per_ch_in_buf_query.argtypes = [
            ctypes.POINTER(ctypes.c_uint)
        ]

        # int pcie7821_read_data(unsigned int point_num_per_ch,
        #                        short* p_data,
        #                        unsigned int* p_points_per_ch_returned)
        self.dll.pcie7821_read_data.restype = ctypes.c_int
        self.dll.pcie7821_read_data.argtypes = [
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_short),
            ctypes.POINTER(ctypes.c_uint)
        ]

        # int pcie7821_read_phase_data(unsigned int point_num_per_ch,
        #                              int* p_phase_data,
        #                              unsigned int* p_points_per_ch_returned)
        self.dll.pcie7821_read_phase_data.restype = ctypes.c_int
        self.dll.pcie7821_read_phase_data.argtypes = [
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint)
        ]

        # int pcie7821_read_monitor_data(unsigned int* p_monitor_data)
        self.dll.pcie7821_read_monitor_data.restype = ctypes.c_int
        self.dll.pcie7821_read_monitor_data.argtypes = [
            ctypes.POINTER(ctypes.c_uint)
        ]

        # int pcie7821_start(void)
        self.dll.pcie7821_start.restype = ctypes.c_int
        self.dll.pcie7821_start.argtypes = []

        # int pcie7821_stop(void)
        self.dll.pcie7821_stop.restype = ctypes.c_int
        self.dll.pcie7821_stop.argtypes = []

        # int pcie7821_test_wr_reg(unsigned int addr, unsigned int data)
        self.dll.pcie7821_test_wr_reg.restype = ctypes.c_int
        self.dll.pcie7821_test_wr_reg.argtypes = [ctypes.c_uint, ctypes.c_uint]

        # int pcie7821_test_rd_reg(unsigned int addr, unsigned int* p_data)
        self.dll.pcie7821_test_rd_reg.restype = ctypes.c_int
        self.dll.pcie7821_test_rd_reg.argtypes = [
            ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)
        ]

    def _check_result(self, result: int, operation: str = ""):
        """Check API result and raise exception on error"""
        if result != 0:
            raise PCIe7821Error(result, f"{operation}: {get_error_message(result)}")

    def open(self) -> int:
        """
        Open the PCIe-7821 device.

        Returns:
            0 on success, error code on failure
        """
        result = self.dll.pcie7821_open()
        if result == 0:
            self._is_open = True
        return result

    def close(self):
        """Close the PCIe-7821 device"""
        if self.dll is not None:
            self.dll.pcie7821_close()
            self._is_open = False

        # Release buffers
        self._raw_buffer = None
        self._phase_buffer = None
        self._monitor_buffer = None

    @property
    def is_open(self) -> bool:
        """Check if device is open"""
        return self._is_open

    def set_clk_src(self, clk_src: int) -> int:
        """
        Set clock source.

        Args:
            clk_src: 0=internal, 1=external
        """
        return self.dll.pcie7821_set_clk_src(clk_src)

    def set_trig_dir(self, trig_dir: int) -> int:
        """
        Set trigger direction.

        Args:
            trig_dir: 0=input, 1=output
        """
        return self.dll.pcie7821_set_trig_dir(trig_dir)

    def set_scan_rate(self, scan_rate: int) -> int:
        """
        Set scan rate in Hz.

        Args:
            scan_rate: Scan rate in Hz
        """
        return self.dll.pcie7821_set_scan_rate(scan_rate)

    def set_pulse_width(self, pulse_ns: int) -> int:
        """
        Set pulse width in nanoseconds.

        Args:
            pulse_ns: Pulse width in ns
        """
        return self.dll.pcie7821_set_pusle_width(pulse_ns)

    def set_point_num_per_scan(self, point_num: int) -> int:
        """
        Set number of points per scan.

        Args:
            point_num: Number of points per scan
        """
        return self.dll.pcie7821_set_point_num_per_scan(point_num)

    def set_bypass_point_num(self, bypass_num: int) -> int:
        """
        Set number of bypass points.

        Args:
            bypass_num: Number of points to bypass
        """
        return self.dll.pcie7821_set_bypass_point_num(bypass_num)

    def set_center_freq(self, freq_hz: int) -> int:
        """
        Set center frequency in Hz.

        Args:
            freq_hz: Center frequency in Hz
        """
        return self.dll.pcie7821_set_center_freq(freq_hz)

    def set_upload_data_param(self, ch_num: int, data_src: int, data_rate: int) -> int:
        """
        Set upload data parameters.

        Args:
            ch_num: Number of channels (1, 2, or 4)
            data_src: Data source (0-4)
            data_rate: Data rate in ns
        """
        return self.dll.pcie7821_set_upload_data_param(ch_num, data_src, data_rate)

    def set_phase_dem_param(self, rate2phase: int, space_avg_order: int,
                            merge_point_num: int, diff_order: int,
                            detrend_bw: float, polarization_en: bool) -> int:
        """
        Set phase demodulation parameters.

        Args:
            rate2phase: Rate to phase demodulation factor
            space_avg_order: Spatial averaging order
            merge_point_num: Number of points to merge
            diff_order: Differentiation order
            detrend_bw: Detrend filter bandwidth in Hz
            polarization_en: Enable polarization diversity
        """
        return self.dll.pcie7821_set_phase_dem_param(
            rate2phase, space_avg_order, merge_point_num,
            diff_order, detrend_bw, int(polarization_en)
        )

    def query_buffer_points(self) -> int:
        """
        Query number of points per channel in buffer.

        Returns:
            Number of points per channel available in buffer
        """
        point_num = ctypes.c_uint()
        self.dll.pcie7821_point_num_per_ch_in_buf_query(ctypes.byref(point_num))
        return point_num.value

    def allocate_buffers(self, point_num: int, channel_num: int, frame_num: int,
                         merge_point_num: int = 1, is_phase: bool = True):
        """
        Allocate aligned buffers for data reading.

        Args:
            point_num: Points per scan
            channel_num: Number of channels
            frame_num: Number of frames
            merge_point_num: Merge point number for phase data
            is_phase: Whether allocating for phase data
        """
        # Raw data buffer (short)
        raw_size = point_num * channel_num * frame_num
        self._raw_buffer = AlignedBuffer(raw_size, np.int16)

        # Phase data buffer (int)
        phase_point_num = point_num // merge_point_num
        phase_size = phase_point_num * channel_num * frame_num
        self._phase_buffer = AlignedBuffer(phase_size, np.int32)

        # Monitor data buffer (uint)
        monitor_size = phase_point_num * channel_num
        self._monitor_buffer = AlignedBuffer(monitor_size, np.uint32)

    def read_data(self, point_num_per_ch: int, channel_num: int) -> Tuple[np.ndarray, int]:
        """
        Read raw data from device.

        Args:
            point_num_per_ch: Number of points per channel to read
            channel_num: Number of channels

        Returns:
            Tuple of (data array, points actually returned per channel)
        """
        total_points = point_num_per_ch * channel_num

        # Ensure buffer is large enough
        if self._raw_buffer is None or self._raw_buffer.size < total_points:
            self._raw_buffer = AlignedBuffer(total_points, np.int16)

        points_returned = ctypes.c_uint()
        result = self.dll.pcie7821_read_data(
            point_num_per_ch,
            self._raw_buffer.get_ctypes_ptr(),
            ctypes.byref(points_returned)
        )

        if result != 0:
            raise PCIe7821Error(result, "read_data")

        # Return copy of data
        return self._raw_buffer.array[:total_points].copy(), points_returned.value

    def read_phase_data(self, point_num_per_ch: int, channel_num: int) -> Tuple[np.ndarray, int]:
        """
        Read phase data from device.

        Args:
            point_num_per_ch: Number of points per channel to read
            channel_num: Number of channels

        Returns:
            Tuple of (phase data array, points actually returned per channel)
        """
        total_points = point_num_per_ch * channel_num

        # Ensure buffer is large enough
        if self._phase_buffer is None or self._phase_buffer.size < total_points:
            self._phase_buffer = AlignedBuffer(total_points, np.int32)

        points_returned = ctypes.c_uint()
        result = self.dll.pcie7821_read_phase_data(
            point_num_per_ch,
            self._phase_buffer.get_ctypes_ptr(),
            ctypes.byref(points_returned)
        )

        if result != 0:
            raise PCIe7821Error(result, "read_phase_data")

        return self._phase_buffer.array[:total_points].copy(), points_returned.value

    def read_monitor_data(self, point_num: int, channel_num: int) -> np.ndarray:
        """
        Read monitor data from device.

        Args:
            point_num: Number of points
            channel_num: Number of channels

        Returns:
            Monitor data array
        """
        total_points = point_num * channel_num

        # Ensure buffer is large enough
        if self._monitor_buffer is None or self._monitor_buffer.size < total_points:
            self._monitor_buffer = AlignedBuffer(total_points, np.uint32)

        result = self.dll.pcie7821_read_monitor_data(
            self._monitor_buffer.get_ctypes_ptr()
        )

        if result != 0:
            raise PCIe7821Error(result, "read_monitor_data")

        return self._monitor_buffer.array[:total_points].copy()

    def start(self) -> int:
        """Start acquisition"""
        return self.dll.pcie7821_start()

    def stop(self) -> int:
        """Stop acquisition"""
        return self.dll.pcie7821_stop()

    def write_reg(self, addr: int, data: int) -> int:
        """
        Write to register (for testing).

        Args:
            addr: Register address (must be 4-byte aligned)
            data: Data to write
        """
        if addr % 4 != 0:
            raise ValueError("Register address must be 4-byte aligned")
        return self.dll.pcie7821_test_wr_reg(addr, data)

    def read_reg(self, addr: int) -> int:
        """
        Read from register (for testing).

        Args:
            addr: Register address (must be 4-byte aligned)

        Returns:
            Register value
        """
        if addr % 4 != 0:
            raise ValueError("Register address must be 4-byte aligned")
        data = ctypes.c_uint()
        self.dll.pcie7821_test_rd_reg(addr, ctypes.byref(data))
        return data.value

    def __enter__(self):
        """Context manager entry"""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False

    def __del__(self):
        """Destructor"""
        if self._is_open:
            self.close()
