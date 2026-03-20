#!/usr/bin/env python3
"""
Offline tools for single-channel PHASE .bin files.

Storage contract in this project:
- file type: raw binary .bin
- stored dtype: int32
- displayed phase conversion: phase_rad = int32_value / 32767 * pi
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

try:
    from scipy import signal
except ImportError as exc:  # pragma: no cover
    signal = None
    _SCIPY_IMPORT_ERROR = exc
else:
    _SCIPY_IMPORT_ERROR = None


POINTS_PATTERN = re.compile(r"-(\d+)pt-")
PHASE_RAD_SCALE = np.pi / 32767.0


def infer_points_per_frame_from_filename(file_path: str | Path) -> Optional[int]:
    """Infer points_per_frame from a file name like '...-0819pt-....bin'."""
    match = POINTS_PATTERN.search(Path(file_path).name)
    if match is None:
        return None
    return int(match.group(1))


def read_single_channel_phase_bin_raw(
    file_path: str | Path,
    points_per_frame: Optional[int] = None,
) -> np.ndarray:
    """Read one single-channel PHASE bin file as raw int32 data with shape (frames, points)."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if points_per_frame is None:
        points_per_frame = infer_points_per_frame_from_filename(path)

    if points_per_frame is None:
        raise ValueError(
            "points_per_frame is required when the filename does not contain 'XXXXpt'"
        )
    if points_per_frame <= 0:
        raise ValueError("points_per_frame must be a positive integer")

    raw = np.fromfile(path, dtype=np.int32)
    if raw.size == 0:
        raise ValueError("File is empty")
    if raw.size % points_per_frame != 0:
        raise ValueError(
            f"Element count {raw.size} is not divisible by points_per_frame {points_per_frame}"
        )

    frame_count = raw.size // points_per_frame
    return raw.reshape(frame_count, points_per_frame)


def convert_phase_to_radians(data: np.ndarray) -> np.ndarray:
    """Convert stored int32 phase values to phase in radians."""
    return np.asarray(data, dtype=np.float64) * PHASE_RAD_SCALE


def read_single_channel_phase_bin(
    file_path: str | Path,
    points_per_frame: Optional[int] = None,
) -> np.ndarray:
    """Read one single-channel PHASE bin file and return phase in radians."""
    raw = read_single_channel_phase_bin_raw(file_path, points_per_frame=points_per_frame)
    return convert_phase_to_radians(raw)


def _require_scipy() -> None:
    if signal is None:
        raise ImportError("scipy is required for filtering and PSD functions") from _SCIPY_IMPORT_ERROR


def _validate_filtfilt_length(data: np.ndarray, axis: int, padlen: int) -> None:
    axis_length = data.shape[axis]
    if axis_length <= padlen:
        raise ValueError(
            f"Input length along axis {axis} must be greater than padlen {padlen}, got {axis_length}"
        )


def highpass_filter(
    data: np.ndarray,
    sample_rate_hz: float,
    cutoff_hz: float,
    order: int = 2,
    axis: int = -1,
) -> np.ndarray:
    """Apply a zero-phase Butterworth high-pass filter."""
    _require_scipy()
    data = np.asarray(data, dtype=np.float64)
    if cutoff_hz <= 0:
        raise ValueError("cutoff_hz must be > 0")
    nyquist = sample_rate_hz / 2.0
    if cutoff_hz >= nyquist:
        raise ValueError("cutoff_hz must be smaller than Nyquist frequency")
    b, a = signal.butter(order, cutoff_hz / nyquist, btype="high")
    padlen = 3 * max(len(a), len(b))
    _validate_filtfilt_length(data, axis, padlen)
    return signal.filtfilt(b, a, data, axis=axis)


def bandpass_filter(
    data: np.ndarray,
    sample_rate_hz: float,
    lowcut_hz: float,
    highcut_hz: float,
    order: int = 4,
    axis: int = -1,
) -> np.ndarray:
    """Apply a zero-phase Butterworth band-pass filter."""
    _require_scipy()
    data = np.asarray(data, dtype=np.float64)
    nyquist = sample_rate_hz / 2.0
    if not 0 < lowcut_hz < highcut_hz < nyquist:
        raise ValueError("Require 0 < lowcut_hz < highcut_hz < Nyquist frequency")
    b, a = signal.butter(order, [lowcut_hz / nyquist, highcut_hz / nyquist], btype="band")
    padlen = 3 * max(len(a), len(b))
    _validate_filtfilt_length(data, axis, padlen)
    return signal.filtfilt(b, a, data, axis=axis)


def extract_point_waveform(frame_data: np.ndarray, point_index: int) -> np.ndarray:
    """Extract the time-domain waveform at one spatial point across all frames."""
    if frame_data.ndim != 2:
        raise ValueError("frame_data must be a 2D array shaped as frames x points")
    if not 0 <= point_index < frame_data.shape[1]:
        raise IndexError(f"point_index {point_index} out of range [0, {frame_data.shape[1] - 1}]")
    return frame_data[:, point_index]


def compute_point_psd(
    waveform: np.ndarray,
    sample_rate_hz: float,
    window: str = "hann",
    detrend: str | bool = "constant",
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute PSD using scipy.signal.welch and return (freq_hz, psd_db)."""
    _require_scipy()
    waveform = np.asarray(waveform, dtype=np.float64)
    if waveform.ndim != 1:
        raise ValueError("waveform must be 1D")
    if waveform.size < 2:
        raise ValueError("waveform length must be >= 2")

    freq_hz, psd_linear = signal.welch(
        waveform,
        fs=sample_rate_hz,
        window=window,
        nperseg=waveform.size,
        noverlap=0,
        nfft=waveform.size,
        return_onesided=True,
        scaling="density",
        detrend=detrend,
    )
    psd_db = 10.0 * np.log10(psd_linear + 1e-20)
    return freq_hz, psd_db


def plot_point_waveform(
    waveform: np.ndarray,
    sample_rate_hz: Optional[float] = None,
    title: str = "Point Time-Domain Waveform",
    ylabel: str = "Phase (rad)",
    ax=None,
):
    """Plot a waveform against frame index or time."""
    waveform = np.asarray(waveform)
    if waveform.ndim != 1:
        raise ValueError("waveform must be 1D")

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 4))
    else:
        fig = ax.figure

    if sample_rate_hz is None:
        x = np.arange(waveform.size)
        xlabel = "Frame Index"
    else:
        x = np.arange(waveform.size) / sample_rate_hz
        xlabel = "Time (s)"

    ax.plot(x, waveform, linewidth=1.0)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig, ax


def plot_point_psd(
    freq_hz: np.ndarray,
    psd_db: np.ndarray,
    title: str = "Point PSD",
    ax=None,
):
    """Plot PSD in dB."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 4))
    else:
        fig = ax.figure

    ax.plot(freq_hz, psd_db, linewidth=1.0)
    ax.set_title(title)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("PSD (dB)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig, ax


def plot_space_time(
    frame_data: np.ndarray,
    frame_slice: slice = slice(None),
    point_slice: slice = slice(None),
    sample_rate_hz: Optional[float] = None,
    cmap: str = "jet",
    title: str = "Space-Time Plot",
    colorbar_label: str = "Phase (rad)",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    ax=None,
):
    """Draw a space-time image for data shaped as (frames, points)."""
    if frame_data.ndim != 2:
        raise ValueError("frame_data must be a 2D array shaped as frames x points")

    display = np.asarray(frame_data[frame_slice, point_slice], dtype=np.float64)

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 5))
    else:
        fig = ax.figure

    if sample_rate_hz is None:
        x0 = 0
        x1 = display.shape[0]
        xlabel = "Frame Index"
    else:
        x0 = 0.0
        x1 = display.shape[0] / sample_rate_hz
        xlabel = "Time (s)"

    y0 = 0
    y1 = display.shape[1]
    image = ax.imshow(
        display.T,
        aspect="auto",
        origin="lower",
        extent=[x0, x1, y0, y1],
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
    )
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Point Index")
    fig.colorbar(image, ax=ax, label=colorbar_label)
    fig.tight_layout()
    return fig, ax


__all__ = [
    "infer_points_per_frame_from_filename",
    "read_single_channel_phase_bin_raw",
    "read_single_channel_phase_bin",
    "convert_phase_to_radians",
    "highpass_filter",
    "bandpass_filter",
    "extract_point_waveform",
    "compute_point_psd",
    "plot_point_waveform",
    "plot_point_psd",
    "plot_space_time",
]