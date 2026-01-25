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
    RAW_I = 0
    RAW_Q = 1
    IQ_I = 2
    IQ_Q = 3
    PHASE = 4


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
    rate2phase: int = 4  # 1, 2, 4, 8, 16, 32
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


@dataclass
class SaveParams:
    """Data save parameters"""
    enable: bool = False
    path: str = "save_data"
    file_prefix: str = ""


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
    ("Raw I", DataSource.RAW_I),
    ("Raw Q", DataSource.RAW_Q),
    ("IQ I", DataSource.IQ_I),
    ("IQ Q", DataSource.IQ_Q),
    ("Phase", DataSource.PHASE),
]

DATA_RATE_OPTIONS: List[Tuple[str, int]] = [
    ("1ns (1GHz)", 1),
    ("2ns (500MHz)", 2),
    ("4ns (250MHz)", 4),
    ("8ns (125MHz)", 8),
]

# Rate2Phase: 基础采样率1GHz / Rate2Phase = 实际数据率
# 例如: Rate2Phase=4 → 1GHz/4 = 250MHz
RATE2PHASE_OPTIONS: List[Tuple[str, int]] = [
<<<<<<< HEAD
    ("1G", 1),
    ("500M", 2),
    ("250M", 4),
    ("125M", 8),
    ("62.5M", 16),
    ("31.25M", 32),
=======
    ("1x", 1),
    ("2x", 2),
    ("4x", 4),
    ("8x", 8),
    ("16x", 16),
    ("32x", 32),
>>>>>>> 6a26e535ed848e0881a770e06c6bdfb8baaff2e0
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
