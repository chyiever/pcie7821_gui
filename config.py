"""
PCIe-7821 DAS Configuration Module
Default parameters and option mappings
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from enum import IntEnum


class ClockSource(IntEnum):
    INTERNAL = 0
    EXTERNAL = 1


class TriggerDirection(IntEnum):
    INPUT = 0
    OUTPUT = 1


class DataSource(IntEnum):
    raw = 0     # 原始散射光数据
    I_Q = 2     # I/Q路数据
    arc = 3     # IQ解调后的arctan(Q/I)
    PHASE = 4   # 相位数据


class DisplayMode(IntEnum):
    TIME = 0  # Time domain (multiple frames overlay)
    SPACE = 1  # Space domain (single region over time)


@dataclass
class BasicParams:
    """Basic acquisition parameters"""
    clk_src: int = ClockSource.INTERNAL
    trig_dir: int = TriggerDirection.OUTPUT
    scan_rate: int = 2000  # Hz
    pulse_width_ns: int = 100  # ns
    point_num_per_scan: int = 20480
    bypass_point_num: int = 60
    center_freq_mhz: int = 200  # MHz


@dataclass
class UploadParams:
    """Data upload parameters"""
    channel_num: int = 1  # 1, 2, or 4
    data_source: int = DataSource.PHASE
    data_rate: int = 1  # ns per sample


@dataclass
class PhaseDemodParams:
    """Phase demodulation parameters"""
    rate2phase: int = 1  # 1, 2, 3, 4, 5, 10 (默认250M)
    space_avg_order: int = 25
    merge_point_num: int = 25
    diff_order: int = 1
    detrend_bw: float = 0.5  # Hz
    polarization_diversity: bool = False


@dataclass
class DisplayParams:
    """Display control parameters"""
    mode: int = DisplayMode.TIME
    region_index: int = 0
    frame_num: int = 1024
    spectrum_enable: bool = True
    psd_enable: bool = False
    rad_enable: bool = False  # Convert phase data to radians


@dataclass
class SaveParams:
    """Data save parameters"""
    enable: bool = False
    path: str = "D:/eDAS_DATA"  # Changed default path
    file_prefix: str = ""
    frames_per_file: int = 10   # New: frames per file control


@dataclass
class AllParams:
    """All configuration parameters"""
    basic: BasicParams = field(default_factory=BasicParams)
    upload: UploadParams = field(default_factory=UploadParams)
    phase_demod: PhaseDemodParams = field(default_factory=PhaseDemodParams)
    display: DisplayParams = field(default_factory=DisplayParams)
    save: SaveParams = field(default_factory=SaveParams)


# Option mappings for combo boxes
CHANNEL_NUM_OPTIONS: List[Tuple[str, int]] = [
    ("1", 1),
    ("2", 2),
    ("4", 4),
]

DATA_SOURCE_OPTIONS: List[Tuple[str, int]] = [
    ("RawBack", DataSource.raw),    # 原始散射光数据
    ("I/Q", DataSource.I_Q),        # I/Q路数据
    ("Arctan", DataSource.arc),     # IQ解调后的arctan(Q/I)
    ("Phase", DataSource.PHASE),    # 相位解调数据
]

DATA_RATE_OPTIONS: List[Tuple[str, int]] = [
    ("1ns (1GHz)", 1),
    ("2ns (500MHz)", 2),
    ("4ns (250MHz)", 4),
    ("8ns (125MHz)", 8),
]

# Rate2Phase: 原始采样率1GHz，经IQ解调后为250MHz，再经Rate2Phase分频得到实际相位数据率
# 例如: Rate2Phase=1 → 250MHz/1 = 250MHz, Rate2Phase=10 → 250MHz/10 = 25MHz
RATE2PHASE_OPTIONS: List[Tuple[str, int]] = [
    ("250M", 1),
    ("125M", 2),
    ("83.33M", 3),
    ("62.5M", 4),
    ("50M", 5),
    ("25M", 10),
]

# Constraints
MAX_POINT_NUM_1CH = 262144
MAX_POINT_NUM_2CH = 131072
MAX_POINT_NUM_4CH = 65536

POINT_NUM_ALIGN_1CH = 512
POINT_NUM_ALIGN_2CH = 256
POINT_NUM_ALIGN_4CH = 128

# DMA memory alignment
DMA_ALIGNMENT = 4096

# Error codes
ERROR_CODES: Dict[int, str] = {
    0: "Success",
    -1: "Device open failed",
    -2: "Invalid parameter",
    -3: "Buffer overflow",
    -4: "Device not started",
    -5: "DMA error",
}


def get_error_message(code: int) -> str:
    """Get error message from error code"""
    return ERROR_CODES.get(code, f"Unknown error ({code})")


def validate_point_num(point_num: int, channel_num: int) -> Tuple[bool, str]:
    """Validate point_num_per_scan based on channel count"""
    if channel_num == 1:
        if point_num > MAX_POINT_NUM_1CH:
            return False, f"Single channel mode: point_num must be <= {MAX_POINT_NUM_1CH}"
        if point_num % POINT_NUM_ALIGN_1CH != 0:
            return False, f"Single channel mode: point_num must be multiple of {POINT_NUM_ALIGN_1CH}"
    elif channel_num == 2:
        if point_num > MAX_POINT_NUM_2CH:
            return False, f"Dual channel mode: point_num must be <= {MAX_POINT_NUM_2CH}"
        if point_num % POINT_NUM_ALIGN_2CH != 0:
            return False, f"Dual channel mode: point_num must be multiple of {POINT_NUM_ALIGN_2CH}"
    elif channel_num == 4:
        if point_num > MAX_POINT_NUM_4CH:
            return False, f"Quad channel mode: point_num must be <= {MAX_POINT_NUM_4CH}"
        if point_num % POINT_NUM_ALIGN_4CH != 0:
            return False, f"Quad channel mode: point_num must be multiple of {POINT_NUM_ALIGN_4CH}"
    return True, ""


def calculate_fiber_length(point_num: int, data_rate: int, data_source: int, rate2phase: int) -> float:
    """Calculate fiber length in meters based on parameters"""
    if data_source == DataSource.PHASE:
        len_rbw = 0.4 * rate2phase
    else:
        len_rbw = 0.1 * data_rate
    return point_num * len_rbw / 1000.0


def calculate_data_rate_mbps(scan_rate: int, point_num: int, channel_num: int) -> float:
    """Calculate data rate in MB/s"""
    return scan_rate * point_num * 2 * channel_num / 1024.0 / 1024.0


# Enhanced buffer configuration
OPTIMIZED_BUFFER_SIZES = {
    'hardware_buffer_frames': 50,      # FPGA + DMA buffer
    'signal_queue_frames': 20,          # Qt signal queue
    'storage_queue_frames': 200,        # Async file writing (increased)
    'display_buffer_frames': 30         # GUI display history
}

# Dynamic polling configuration
POLLING_CONFIG = {
    'high_freq_interval_ms': 1,         # High frequency polling: 1ms
    'low_freq_interval_ms': 10,         # Low frequency polling: 10ms
    'buffer_threshold_high': 0.8,       # Switch to high freq when buffer > 80%
    'buffer_threshold_low': 0.3          # Switch to low freq when buffer < 30%
}

# System monitoring update intervals
MONITOR_UPDATE_INTERVALS = {
    'buffer_status_ms': 500,            # Buffer status update: 500ms
    'system_status_s': 10,              # CPU/Disk space update: 10s
    'performance_log_s': 30             # Performance logging: 30s
}
