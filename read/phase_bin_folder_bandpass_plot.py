#!/usr/bin/env python3
"""
Upgraded folder plotting program for PHASE .bin files.

Features:
- read and concatenate matched .bin files from one folder
- optionally limit by matched file serial range before concatenation
- optionally apply band-pass filtering along the time axis before plotting
- draw original and filtered space-time views for direct comparison
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

import phase_bin_tools as pbt


# =========================
# User configuration block
# =========================
FOLDER_PATH = Path(r"F:\das2")
FILE_PATTERN = "0000*.bin"
POINTS_PER_FRAME = None
SCAN_RATE_HZ = None
POINT_INDEX = 100

# Use 1-based inclusive indices in the matched-file list.
# Example: 1~5 means reading the first 5 matched files and concatenating them.
# Set both to None to use all matched files.
FILE_INDEX_START = 1
FILE_INDEX_END = 2

SPACE_TIME_FRAME_SLICE = slice(None)
SPACE_TIME_POINT_SLICE = slice(None)
SPACE_TIME_VMIN = -0.2
SPACE_TIME_VMAX = 0.2
SPACE_TIME_CMAP = "jet"

ENABLE_BANDPASS = True
BANDPASS_LOW_HZ = 100.0
BANDPASS_HIGH_HZ = 999.0
BANDPASS_ORDER = 4

SHOW_POINT_WAVEFORM = True


def _resolve_metadata(selected_files: list[Path]) -> tuple[int, float]:
    points_per_frame = POINTS_PER_FRAME
    scan_rate_hz = SCAN_RATE_HZ

    if points_per_frame is None:
        points_per_frame = pbt.infer_points_per_frame_from_filename(selected_files[0])
    if points_per_frame is None:
        raise ValueError("Unable to infer points_per_frame from file name; set POINTS_PER_FRAME.")

    if scan_rate_hz is None:
        scan_rate_hz = pbt.infer_scan_rate_hz_from_filename(selected_files[0])
    if scan_rate_hz is None:
        raise ValueError("Unable to infer scan_rate_hz from file name; set SCAN_RATE_HZ.")

    return points_per_frame, scan_rate_hz


def _select_files_by_index(all_files: list[Path]) -> tuple[list[Path], int, int]:
    if FILE_INDEX_START is None and FILE_INDEX_END is None:
        return all_files, 1, len(all_files)

    start = 1 if FILE_INDEX_START is None else FILE_INDEX_START
    end = len(all_files) if FILE_INDEX_END is None else FILE_INDEX_END

    if start <= 0 or end <= 0:
        raise ValueError("FILE_INDEX_START and FILE_INDEX_END must be positive integers.")
    if start > end:
        raise ValueError("FILE_INDEX_START must be <= FILE_INDEX_END.")
    if end > len(all_files):
        raise ValueError(
            f"Requested file index range {start}~{end}, but only {len(all_files)} files matched."
        )

    # Convert 1-based inclusive range to Python slice.
    return all_files[start - 1 : end], start, end


def _load_phase_data() -> tuple[object, list[Path], list[Path], int, int, int, float]:
    all_matched_files = pbt.list_phase_bin_files(FOLDER_PATH, pattern=FILE_PATTERN)
    selected_files, selected_start, selected_end = _select_files_by_index(all_matched_files)
    points_per_frame, scan_rate_hz = _resolve_metadata(selected_files)
    frame_data_phase = pbt.read_multi_channel_phase_bin(
        selected_files,
        points_per_frame=points_per_frame,
    )
    return (
        frame_data_phase,
        all_matched_files,
        selected_files,
        selected_start,
        selected_end,
        points_per_frame,
        scan_rate_hz,
    )


def _maybe_bandpass_filter(frame_data_phase, scan_rate_hz: float):
    if not ENABLE_BANDPASS:
        return frame_data_phase
    return pbt.bandpass_filter(
        frame_data_phase,
        sample_rate_hz=scan_rate_hz,
        lowcut_hz=BANDPASS_LOW_HZ,
        highcut_hz=BANDPASS_HIGH_HZ,
        order=BANDPASS_ORDER,
        axis=0,
    )


def main() -> None:
    plt.rcParams["figure.dpi"] = 120

    (
        frame_data_phase,
        all_matched_files,
        selected_files,
        selected_start,
        selected_end,
        points_per_frame,
        scan_rate_hz,
    ) = _load_phase_data()
    filtered_phase = _maybe_bandpass_filter(frame_data_phase, scan_rate_hz)

    print("folder_path:", FOLDER_PATH)
    print("file_pattern:", FILE_PATTERN)
    print("all matched file count:", len(all_matched_files))
    print("selected file range:", f"{selected_start}~{selected_end}")
    print("selected file count:", len(selected_files))
    for file_index, path in enumerate(selected_files, start=selected_start):
        print(f"  [{file_index}]", path.name)
    print("points_per_frame:", points_per_frame)
    print("scan_rate_hz:", scan_rate_hz)
    print("phase shape:", frame_data_phase.shape)
    print("phase dtype:", frame_data_phase.dtype)
    print("phase min/max (rad):", frame_data_phase.min(), frame_data_phase.max())
    print("bandpass enabled:", ENABLE_BANDPASS)
    if ENABLE_BANDPASS:
        print("bandpass low/high/order:", BANDPASS_LOW_HZ, BANDPASS_HIGH_HZ, BANDPASS_ORDER)
        print("filtered min/max (rad):", filtered_phase.min(), filtered_phase.max())

    if SHOW_POINT_WAVEFORM:
        raw_waveform = pbt.extract_point_waveform(frame_data_phase, POINT_INDEX)
        filtered_waveform = pbt.extract_point_waveform(filtered_phase, POINT_INDEX)

        fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
        pbt.plot_point_waveform(
            raw_waveform,
            sample_rate_hz=scan_rate_hz,
            title=f"Original Point Waveform (point={POINT_INDEX})",
            ylabel="Phase (rad)",
            ax=axes[0],
        )
        pbt.plot_point_waveform(
            filtered_waveform,
            sample_rate_hz=scan_rate_hz,
            title=f"Bandpassed Point Waveform (point={POINT_INDEX})",
            ylabel="Phase (rad)",
            ax=axes[1],
        )
        plt.tight_layout()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    pbt.plot_space_time(
        frame_data_phase,
        frame_slice=SPACE_TIME_FRAME_SLICE,
        point_slice=SPACE_TIME_POINT_SLICE,
        sample_rate_hz=scan_rate_hz,
        cmap=SPACE_TIME_CMAP,
        title="Original Space-Time Plot",
        colorbar_label="Phase (rad)",
        vmin=SPACE_TIME_VMIN,
        vmax=SPACE_TIME_VMAX,
        ax=axes[0],
    )
    filtered_title = "Bandpassed Space-Time Plot"
    if ENABLE_BANDPASS:
        filtered_title = (
            f"Bandpassed Space-Time Plot ({BANDPASS_LOW_HZ:g}-{BANDPASS_HIGH_HZ:g} Hz)"
        )
    pbt.plot_space_time(
        filtered_phase,
        frame_slice=SPACE_TIME_FRAME_SLICE,
        point_slice=SPACE_TIME_POINT_SLICE,
        sample_rate_hz=scan_rate_hz,
        cmap=SPACE_TIME_CMAP,
        title=filtered_title,
        colorbar_label="Phase (rad)",
        vmin=SPACE_TIME_VMIN,
        vmax=SPACE_TIME_VMAX,
        ax=axes[1],
    )
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
