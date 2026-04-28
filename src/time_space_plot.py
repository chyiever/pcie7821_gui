"""
Time-space plot widget based on PlotWidget + ImageItem.

The widget keeps a fixed-size rolling display buffer so realtime updates do not
rebuild the whole image with repeated concatenation.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
from PyQt5.QtCore import QRectF, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
import pyqtgraph as pg

from logger import get_logger
from plot_interaction import ZoomablePlotViewBox


log = get_logger("time_space_plot")


def _create_custom_colormaps() -> Dict[str, pg.ColorMap]:
    """Provide a few colormaps when the local pyqtgraph build is missing them."""
    custom_maps: Dict[str, pg.ColorMap] = {}
    custom_maps["jet"] = pg.ColorMap(
        np.linspace(0.0, 1.0, 9),
        np.array(
            [
                [0, 0, 127],
                [0, 0, 255],
                [0, 127, 255],
                [0, 255, 255],
                [127, 255, 127],
                [255, 255, 0],
                [255, 127, 0],
                [255, 0, 0],
                [127, 0, 0],
            ]
        ),
    )
    custom_maps["gray"] = pg.ColorMap(
        np.array([0.0, 1.0]),
        np.array([[0, 0, 0], [255, 255, 255]]),
    )
    custom_maps["seismic"] = pg.ColorMap(
        np.linspace(0.0, 1.0, 7),
        np.array(
            [
                [0, 0, 75],
                [0, 0, 255],
                [127, 127, 255],
                [255, 255, 255],
                [255, 127, 127],
                [255, 0, 0],
                [75, 0, 0],
            ]
        ),
    )
    return custom_maps


_CUSTOM_COLORMAPS = _create_custom_colormaps()

COLORMAP_OPTIONS = [
    ("Jet", "jet"),
    ("HSV", "hsv"),
    ("Viridis", "viridis"),
    ("Plasma", "plasma"),
    ("Inferno", "inferno"),
    ("Magma", "magma"),
    ("Seismic", "seismic"),
    ("Gray", "gray"),
]


class TimeSpacePlotWidget(QWidget):
    """Realtime time-space plot with fixed rolling image buffer."""

    parametersChanged = pyqtSignal()
    pointCountChanged = pyqtSignal(int)
    plotStateChanged = pyqtSignal(bool)

    DISPLAY_UPDATE_INTERVAL_MS = 150

    def __init__(self):
        super().__init__()

        self._max_window_frames = 100
        self._window_frames = 5
        self._distance_start = 40
        self._distance_end = 100
        self._time_downsample = 50
        self._space_downsample = 2
        self._colormap = "jet"
        self._vmin = -0.02
        self._vmax = 0.02
        self._scan_rate_hz = 2000.0

        self._plot_enabled = False
        self._pending_update = False
        self._full_point_num = 0
        self._zoom_locked = False

        self._display_buffer: Optional[np.ndarray] = None
        self._display_block_width = 0
        self._display_space_count = 0
        self._display_block_duration_s = 0.0
        self._source_frames_per_block = 0
        self._valid_block_count = 0
        self._current_distance_bounds: Tuple[int, int] = (self._distance_start, self._distance_end)

        self._display_update_timer = QTimer(self)
        self._display_update_timer.setSingleShot(True)
        self._display_update_timer.timeout.connect(self._flush_scheduled_display_update)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        control_panel = self._create_control_panel()
        control_panel.setMaximumHeight(140)
        layout.addWidget(control_panel)

        plot_layout = QHBoxLayout()
        self._create_plot_area()
        plot_layout.addWidget(self.plot_widget, 1)
        self._create_colorbar()
        plot_layout.addWidget(self.histogram_widget)

        plot_container = QWidget()
        plot_container.setLayout(plot_layout)
        layout.addWidget(plot_container, 1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _create_plot_area(self):
        self._view_box = ZoomablePlotViewBox()
        self._view_box.sigManualRangeChange.connect(self._on_manual_range_change)
        self._view_box.sigViewAllRequested.connect(self._restore_auto_range)

        self.plot_widget = pg.PlotWidget(viewBox=self._view_box)
        self.plot_widget.setMinimumSize(800, 400)
        self.plot_widget.setBackground("w")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel(
            "bottom",
            "Time (s)",
            color="k",
            **{"font-size": "10pt", "font-family": "Times New Roman"},
        )
        self.plot_widget.setLabel(
            "left",
            "Distance (points)",
            color="k",
            **{"font-size": "10pt", "font-family": "Times New Roman"},
        )
        self.plot_widget.showAxis("top", show=False)
        self.plot_widget.showAxis("right", show=False)

        font = QFont("Times New Roman", 9)
        for axis_name in ("bottom", "left"):
            axis = self.plot_widget.getAxis(axis_name)
            axis.setTickFont(font)
            axis.setPen("k")
            axis.setTextPen("k")
            axis.setStyle(showValues=True)
            axis.enableAutoSIPrefix(False)

        self.image_item = pg.ImageItem(axisOrder="row-major")
        self.plot_widget.addItem(self.image_item)
        self._apply_colormap()
        self._restore_auto_range()

    def _create_colorbar(self):
        self.histogram_widget = pg.HistogramLUTWidget()
        self.histogram_widget.setFixedWidth(90)
        self.histogram_widget.setMinimumHeight(400)
        self.histogram_widget.setBackground("w")
        self.histogram_widget.setImageItem(self.image_item)
        self.histogram_widget.setLevels(self._vmin, self._vmax)

        plot_item = getattr(self.histogram_widget, "plotItem", None)
        if plot_item is not None:
            axis = plot_item.getAxis("left")
            if axis is not None:
                axis.setTickFont(QFont("Times New Roman", 8))
                axis.setPen("k")
                axis.setTextPen("k")

        self._apply_colormap()

    def _create_control_panel(self):
        group = QGroupBox()
        group.setFont(QFont("Times New Roman", 9))

        layout = QGridLayout(group)
        layout.setHorizontalSpacing(15)
        layout.setVerticalSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        row = 0
        distance_label = QLabel("Distance Range:")
        distance_label.setFont(QFont("Times New Roman", 8))
        layout.addWidget(distance_label, row, 0)

        from_label = QLabel("From:")
        from_label.setFont(QFont("Times New Roman", 8))
        layout.addWidget(from_label, row, 1)

        self.distance_start_spin = QSpinBox()
        self.distance_start_spin.setRange(0, 1000000)
        self.distance_start_spin.setValue(self._distance_start)
        self.distance_start_spin.setMaximumWidth(60)
        self.distance_start_spin.setFont(QFont("Times New Roman", 8))
        self.distance_start_spin.valueChanged.connect(self._on_distance_start_changed)
        layout.addWidget(self.distance_start_spin, row, 2)

        to_label = QLabel("To:")
        to_label.setFont(QFont("Times New Roman", 8))
        layout.addWidget(to_label, row, 3)

        self.distance_end_spin = QSpinBox()
        self.distance_end_spin.setRange(1, 1000000)
        self.distance_end_spin.setValue(self._distance_end)
        self.distance_end_spin.setMaximumWidth(60)
        self.distance_end_spin.setFont(QFont("Times New Roman", 8))
        self.distance_end_spin.valueChanged.connect(self._on_distance_end_changed)
        layout.addWidget(self.distance_end_spin, row, 4)

        window_label = QLabel("Window Frames:")
        window_label.setFont(QFont("Times New Roman", 8))
        layout.addWidget(window_label, row, 5)

        self.window_frames_spin = QSpinBox()
        self.window_frames_spin.setRange(1, self._max_window_frames)
        self.window_frames_spin.setValue(self._window_frames)
        self.window_frames_spin.setMaximumWidth(50)
        self.window_frames_spin.setFont(QFont("Times New Roman", 8))
        self.window_frames_spin.valueChanged.connect(self._on_window_frames_changed)
        layout.addWidget(self.window_frames_spin, row, 6)

        time_ds_label = QLabel("Time DS:")
        time_ds_label.setFont(QFont("Times New Roman", 8))
        layout.addWidget(time_ds_label, row, 7)

        self.time_downsample_spin = QSpinBox()
        self.time_downsample_spin.setRange(1, 1000)
        self.time_downsample_spin.setValue(self._time_downsample)
        self.time_downsample_spin.setMaximumWidth(50)
        self.time_downsample_spin.setFont(QFont("Times New Roman", 8))
        self.time_downsample_spin.valueChanged.connect(self._on_time_downsample_changed)
        layout.addWidget(self.time_downsample_spin, row, 8)

        space_ds_label = QLabel("Space DS:")
        space_ds_label.setFont(QFont("Times New Roman", 8))
        layout.addWidget(space_ds_label, row, 9)

        self.space_downsample_spin = QSpinBox()
        self.space_downsample_spin.setRange(1, 100)
        self.space_downsample_spin.setValue(self._space_downsample)
        self.space_downsample_spin.setMaximumWidth(50)
        self.space_downsample_spin.setFont(QFont("Times New Roman", 8))
        self.space_downsample_spin.valueChanged.connect(self._on_space_downsample_changed)
        layout.addWidget(self.space_downsample_spin, row, 10)

        row = 1
        color_range_label = QLabel("Color Range:")
        color_range_label.setFont(QFont("Times New Roman", 8))
        layout.addWidget(color_range_label, row, 0)

        min_label = QLabel("Min:")
        min_label.setFont(QFont("Times New Roman", 8))
        layout.addWidget(min_label, row, 1)

        self.vmin_spin = QDoubleSpinBox()
        self.vmin_spin.setRange(-10000.0, 10000.0)
        self.vmin_spin.setDecimals(3)
        self.vmin_spin.setSingleStep(0.001)
        self.vmin_spin.setValue(self._vmin)
        self.vmin_spin.setMaximumWidth(60)
        self.vmin_spin.setFont(QFont("Times New Roman", 8))
        self.vmin_spin.valueChanged.connect(self._on_vmin_changed)
        layout.addWidget(self.vmin_spin, row, 2)

        max_label = QLabel("Max:")
        max_label.setFont(QFont("Times New Roman", 8))
        layout.addWidget(max_label, row, 3)

        self.vmax_spin = QDoubleSpinBox()
        self.vmax_spin.setRange(-10000.0, 10000.0)
        self.vmax_spin.setDecimals(3)
        self.vmax_spin.setSingleStep(0.001)
        self.vmax_spin.setValue(self._vmax)
        self.vmax_spin.setMaximumWidth(60)
        self.vmax_spin.setFont(QFont("Times New Roman", 8))
        self.vmax_spin.valueChanged.connect(self._on_vmax_changed)
        layout.addWidget(self.vmax_spin, row, 4)

        colormap_label = QLabel("Colormap:")
        colormap_label.setFont(QFont("Times New Roman", 8))
        layout.addWidget(colormap_label, row, 5)

        self.colormap_combo = QComboBox()
        self.colormap_combo.setMaximumWidth(80)
        self.colormap_combo.setFont(QFont("Times New Roman", 8))
        for name, value in COLORMAP_OPTIONS:
            self.colormap_combo.addItem(name, value)
        self.colormap_combo.setCurrentText("Jet")
        self.colormap_combo.currentTextChanged.connect(self._on_colormap_changed)
        layout.addWidget(self.colormap_combo, row, 6)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setFont(QFont("Times New Roman", 8))
        reset_btn.setMaximumWidth(120)
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn, row, 7)

        self.plot_btn = QPushButton("PLOT")
        self.plot_btn.setFont(QFont("Times New Roman", 8, QFont.Bold))
        self.plot_btn.setMaximumWidth(60)
        self.plot_btn.setCheckable(True)
        self.plot_btn.clicked.connect(self._on_plot_button_clicked)
        self._update_plot_button_style()
        layout.addWidget(self.plot_btn, row, 8)

        layout.setColumnStretch(11, 1)
        return group

    def _get_colormap(self, colormap_name: str) -> Optional[pg.ColorMap]:
        try:
            return pg.colormap.get(colormap_name)
        except Exception:
            return _CUSTOM_COLORMAPS.get(colormap_name) or _CUSTOM_COLORMAPS.get("jet")

    def _apply_colormap(self):
        colormap = self._get_colormap(self._colormap)
        if colormap is None:
            return
        if hasattr(self, "image_item"):
            self.image_item.setColorMap(colormap)
        if hasattr(self, "histogram_widget") and hasattr(self.histogram_widget, "gradient"):
            self.histogram_widget.gradient.setColorMap(colormap)

    def _invalidate_display_buffer(self, clear_image: bool = False):
        self._display_buffer = None
        self._display_block_width = 0
        self._display_space_count = 0
        self._display_block_duration_s = 0.0
        self._source_frames_per_block = 0
        self._valid_block_count = 0
        self._pending_update = False
        self._display_update_timer.stop()
        if clear_image and hasattr(self, "image_item"):
            self.image_item.setImage(np.zeros((1, 1)), autoLevels=False)
            self.image_item.setLevels((self._vmin, self._vmax))

    def _on_plot_button_clicked(self, checked: bool):
        self._plot_enabled = checked
        if not checked:
            self._pending_update = False
            self._display_update_timer.stop()
        self._update_plot_button_style()
        self.plotStateChanged.emit(self._plot_enabled)
        log.info("Time-space plot %s", "enabled" if checked else "disabled")

    def _update_plot_button_style(self):
        if self._plot_enabled:
            self.plot_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: 1px solid #45a049;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                """
            )
        else:
            self.plot_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #9E9E9E;
                    color: white;
                    border: 1px solid #757575;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #757575;
                }
                """
            )

    def _on_distance_start_changed(self, value: int):
        self._distance_start = value
        if self._distance_end <= self._distance_start:
            self.distance_end_spin.setValue(self._distance_start + 1)
            return
        self._invalidate_display_buffer(clear_image=True)
        self.parametersChanged.emit()

    def _on_distance_end_changed(self, value: int):
        if value <= self._distance_start:
            self.distance_end_spin.setValue(self._distance_start + 1)
            return
        self._distance_end = value
        self._invalidate_display_buffer(clear_image=True)
        self.parametersChanged.emit()

    def _on_window_frames_changed(self, value: int):
        self._window_frames = value
        self._invalidate_display_buffer(clear_image=True)
        self.parametersChanged.emit()

    def _on_space_downsample_changed(self, value: int):
        self._space_downsample = value
        self._invalidate_display_buffer(clear_image=True)
        self.parametersChanged.emit()

    def _on_time_downsample_changed(self, value: int):
        self._time_downsample = value
        self._invalidate_display_buffer(clear_image=True)
        self.parametersChanged.emit()

    def _on_colormap_changed(self, text: str):
        for name, value in COLORMAP_OPTIONS:
            if name == text:
                self._colormap = value
                break
        self._apply_colormap()
        self.parametersChanged.emit()

    def _on_vmin_changed(self, value: float):
        self._vmin = value
        self.image_item.setLevels((self._vmin, self._vmax))
        self.histogram_widget.setLevels(self._vmin, self._vmax)
        self.parametersChanged.emit()

    def _on_vmax_changed(self, value: float):
        self._vmax = value
        self.image_item.setLevels((self._vmin, self._vmax))
        self.histogram_widget.setLevels(self._vmin, self._vmax)
        self.parametersChanged.emit()

    def _reset_to_defaults(self):
        self.window_frames_spin.setValue(5)
        self.distance_start_spin.setValue(40)
        self.distance_end_spin.setValue(100)
        self.time_downsample_spin.setValue(50)
        self.space_downsample_spin.setValue(2)
        self.colormap_combo.setCurrentText("Jet")
        self.vmin_spin.setValue(-0.02)
        self.vmax_spin.setValue(0.02)
        self._invalidate_display_buffer(clear_image=True)
        self.parametersChanged.emit()

    def _on_manual_range_change(self):
        self._zoom_locked = True
        self._view_box.disableAutoRange()

    def _restore_auto_range(self):
        self._zoom_locked = False
        self._view_box.enableAutoRange(x=True, y=True)
        self._view_box.autoRange(padding=0.0)

    def is_plot_enabled(self) -> bool:
        return self._plot_enabled

    def set_scan_rate(self, scan_rate_hz: float):
        if scan_rate_hz > 0:
            self._scan_rate_hz = float(scan_rate_hz)

    def update_data(self, data: np.ndarray) -> bool:
        if not self._plot_enabled:
            return False

        if data.ndim == 1:
            data = data.reshape(1, -1)

        frame_count, point_count = data.shape
        if point_count != self._full_point_num:
            self._full_point_num = point_count
            self.pointCountChanged.emit(point_count)

        display_block_info = self._build_display_block(data)
        if display_block_info is None:
            return False

        display_block, block_duration_s, distance_bounds = display_block_info
        self._append_display_block(display_block, block_duration_s, frame_count, distance_bounds)
        self._schedule_display_update()
        return True

    def _build_display_block(
        self, data_block: np.ndarray
    ) -> Optional[Tuple[np.ndarray, float, Tuple[int, int]]]:
        frame_count, point_count = data_block.shape

        start_idx = max(0, min(self._distance_start, max(0, point_count - 1)))
        end_idx = min(point_count, max(start_idx + 1, self._distance_end))
        if start_idx >= end_idx:
            return None

        display_block = data_block[:, start_idx:end_idx]
        if self._space_downsample > 1:
            display_block = display_block[:, :: self._space_downsample]
        if self._time_downsample > 1:
            display_block = display_block[:: self._time_downsample, :]

        if display_block.size == 0:
            return None

        # Keep the display buffer in (space, time) order.
        display_block = np.ascontiguousarray(display_block.T)
        block_duration_s = frame_count / max(self._scan_rate_hz, 1.0)
        return display_block, block_duration_s, (start_idx, end_idx)

    def _append_display_block(
        self,
        display_block: np.ndarray,
        block_duration_s: float,
        source_frame_count: int,
        distance_bounds: Tuple[int, int],
    ):
        space_count, block_width = display_block.shape
        needs_reset = (
            self._display_buffer is None
            or self._display_space_count != space_count
            or self._display_block_width != block_width
            or self._source_frames_per_block != source_frame_count
            or abs(self._display_block_duration_s - block_duration_s) > 1e-12
        )

        if needs_reset:
            self._display_space_count = space_count
            self._display_block_width = block_width
            self._display_block_duration_s = block_duration_s
            self._source_frames_per_block = source_frame_count
            self._display_buffer = np.zeros(
                (space_count, max(1, block_width * self._window_frames)),
                dtype=display_block.dtype,
            )
            self._valid_block_count = 0

        self._current_distance_bounds = distance_bounds

        if self._valid_block_count < self._window_frames:
            start_col = self._valid_block_count * self._display_block_width
            end_col = start_col + self._display_block_width
            self._display_buffer[:, start_col:end_col] = display_block
            self._valid_block_count += 1
            return

        self._display_buffer[:, :-self._display_block_width] = self._display_buffer[:, self._display_block_width :]
        self._display_buffer[:, -self._display_block_width :] = display_block

    def _schedule_display_update(self):
        self._pending_update = True
        if not self._display_update_timer.isActive():
            self._display_update_timer.start(self.DISPLAY_UPDATE_INTERVAL_MS)

    def _flush_scheduled_display_update(self):
        if not self._pending_update:
            return
        self._pending_update = False
        self._update_display()

    def _update_display(self):
        if self._display_buffer is None or self._valid_block_count <= 0:
            return

        valid_columns = self._valid_block_count * self._display_block_width
        display_data = np.ascontiguousarray(self._display_buffer[:, :valid_columns])
        total_duration_s = self._valid_block_count * self._display_block_duration_s
        distance_start, distance_end = self._current_distance_bounds

        self.image_item.setImage(display_data, autoLevels=False)
        self.image_item.setLevels((self._vmin, self._vmax))
        self.image_item.setRect(
            QRectF(
                0.0,
                float(distance_start),
                float(max(total_duration_s, 1.0 / max(self._scan_rate_hz, 1.0))),
                float(max(distance_end - distance_start, 1)),
            )
        )
        self.histogram_widget.setLevels(self._vmin, self._vmax)
        self.histogram_widget.setImageItem(self.image_item)

        if not self._zoom_locked:
            self._view_box.enableAutoRange(x=True, y=True)
            self._view_box.autoRange(padding=0.0)

    def get_parameters(self):
        return {
            "window_frames": self._window_frames,
            "distance_range_start": self._distance_start,
            "distance_range_end": self._distance_end,
            "time_downsample": self._time_downsample,
            "space_downsample": self._space_downsample,
            "colormap_type": self._colormap,
            "vmin": self._vmin,
            "vmax": self._vmax,
        }

    def set_parameters(self, params):
        if "window_frames" in params:
            self.window_frames_spin.setValue(int(params["window_frames"]))
        if "distance_range_start" in params:
            self.distance_start_spin.setValue(int(params["distance_range_start"]))
        if "distance_range_end" in params:
            self.distance_end_spin.setValue(int(params["distance_range_end"]))
        if "time_downsample" in params:
            self.time_downsample_spin.setValue(int(params["time_downsample"]))
        if "space_downsample" in params:
            self.space_downsample_spin.setValue(int(params["space_downsample"]))
        if "colormap_type" in params:
            for name, value in COLORMAP_OPTIONS:
                if value == params["colormap_type"]:
                    self.colormap_combo.setCurrentText(name)
                    break
        if "vmin" in params:
            self.vmin_spin.setValue(float(params["vmin"]))
        if "vmax" in params:
            self.vmax_spin.setValue(float(params["vmax"]))

    def clear_data(self):
        self._invalidate_display_buffer(clear_image=True)
        log.debug("Time-space plot cleared")


def create_time_space_widget():
    log.info("Creating TimeSpacePlotWidget instance")
    return TimeSpacePlotWidget()


TimeSpacePlotWidgetV2 = TimeSpacePlotWidget


__all__ = ["TimeSpacePlotWidget", "TimeSpacePlotWidgetV2", "create_time_space_widget"]
