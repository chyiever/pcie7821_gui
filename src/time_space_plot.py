"""
Time-Space Plot Widget

PyQt5 widget for 2D time-space visualization of DAS phase data.
Implements rolling window display with configurable parameters.

Features:
- Real-time 2D image display with time (X) vs distance (Y) axes
- Rolling window buffer for smooth scrolling effect
- Configurable downsampling for performance optimization
- Customizable color mapping and range
- PyQtGraph ImageView for GPU-accelerated rendering

Author: eDAS Development Team
"""

import numpy as np
from collections import deque
from typing import Optional, Tuple, Dict, Any
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QSpinBox, QDoubleSpinBox, QComboBox, QPushButton,
    QCheckBox, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
import pyqtgraph as pg

from logger import get_logger

# Module logger
log = get_logger("time_space_plot")

# Available colormap options for PyQtGraph
COLORMAP_OPTIONS = [
    ("Jet", "jet"),
    ("HSV", "hsv"),
    ("Viridis", "viridis"),
    ("Plasma", "plasma"),
    ("Inferno", "inferno"),
    ("Magma", "magma"),
    ("Gray", "gray"),
    ("Hot", "hot"),
    ("Cool", "cool")
]


class TimeSpacePlotWidget(QWidget):
    """
    2D Time-Space plot widget with rolling window functionality.

    Displays phase data as a 2D image where:
    - X-axis: Time (frames)
    - Y-axis: Distance (spatial points)
    - Color: Phase value

    Features real-time scrolling with configurable rolling window.
    """

    # Signal emitted when parameters change
    parametersChanged = pyqtSignal()

    def __init__(self):
        """Initialize the time-space plot widget."""
        super().__init__()
        log.debug("Initializing TimeSpacePlotWidget")

        # Data buffer for rolling window
        self._data_buffer = None  # Will be initialized when first data arrives
        self._max_window_frames = 100  # Increased maximum supported window size

        # Plot parameters
        self._window_frames = 5
        self._distance_start = 40     # Changed default range
        self._distance_end = 100      # Changed default range
        self._time_downsample = 50
        self._space_downsample = 2
        self._colormap = "jet"
        self._vmin = -0.02  # Default range for phase data
        self._vmax = 0.02

        # Current data dimensions
        self._full_point_num = 0
        self._current_frame_count = 0

        self._setup_ui()
        log.debug("TimeSpacePlotWidget initialized")

    def _setup_ui(self):
        """Setup the widget UI layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # Create control panel with compact height
        control_panel = self._create_control_panel()
        control_panel.setMaximumHeight(120)  # 减小控制面板高度，因为输入框变小了
        layout.addWidget(control_panel)

        # Create plot area
        self._create_plot_area()
        layout.addWidget(self.image_view, 1)  # 给图像视图更多空间权重

        # Set size policy to allow expansion
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _create_control_panel(self) -> QGroupBox:
        """Create the control panel with parameter controls."""
        group = QGroupBox("Time-Space Plot Controls")

        # Set font for the group box
        font = QFont("Times New Roman", 9)  # 调小组标题字体
        group.setFont(font)

        layout = QGridLayout(group)
        layout.setHorizontalSpacing(15)  # 水平间距
        layout.setVerticalSpacing(10)    # 保持垂直间距

        row = 0

        # Distance range controls
        distance_label = QLabel("Distance Range:")
        distance_label.setFont(QFont("Times New Roman", 8))  # 调小标签字体
        distance_label.setMinimumHeight(22)  # 减小标签高度与输入框一致
        layout.addWidget(distance_label, row, 0)

        from_label = QLabel("From:")
        from_label.setFont(QFont("Times New Roman", 8))
        from_label.setMinimumHeight(22)  # 减小高度
        layout.addWidget(from_label, row, 1)

        self.distance_start_spin = QSpinBox()
        self.distance_start_spin.setRange(0, 1000000)  # Increased range
        self.distance_start_spin.setValue(40)           # Updated default value
        self.distance_start_spin.setMaximumWidth(80)    # 固定宽度
        self.distance_start_spin.setMinimumHeight(22)   # 减小高度
        self.distance_start_spin.setFont(QFont("Times New Roman", 8))  # 调小输入框字体
        self.distance_start_spin.valueChanged.connect(self._on_distance_start_changed)
        layout.addWidget(self.distance_start_spin, row, 2)

        to_label = QLabel("To:")
        to_label.setFont(QFont("Times New Roman", 8))
        to_label.setMinimumHeight(22)  # 减小高度
        layout.addWidget(to_label, row, 3)

        self.distance_end_spin = QSpinBox()
        self.distance_end_spin.setRange(1, 1000000)  # Increased range
        self.distance_end_spin.setValue(100)         # Updated default value
        self.distance_end_spin.setMaximumWidth(80)   # 固定宽度
        self.distance_end_spin.setMinimumHeight(22)  # 减小高度
        self.distance_end_spin.setFont(QFont("Times New Roman", 8))  # 调小输入框字体
        self.distance_end_spin.valueChanged.connect(self._on_distance_end_changed)
        layout.addWidget(self.distance_end_spin, row, 4)

        row += 1

        # Window frames control
        window_label = QLabel("Window Frames:")
        window_label.setFont(QFont("Times New Roman", 8))
        window_label.setMinimumHeight(22)  # 减小高度
        layout.addWidget(window_label, row, 0)

        self.window_frames_spin = QSpinBox()
        self.window_frames_spin.setRange(1, self._max_window_frames)  # Minimum changed to 1
        self.window_frames_spin.setValue(self._window_frames)
        self.window_frames_spin.setMaximumWidth(80)  # 固定宽度
        self.window_frames_spin.setMinimumHeight(22)  # 减小高度
        self.window_frames_spin.setFont(QFont("Times New Roman", 8))  # 调小字体
        self.window_frames_spin.valueChanged.connect(self._on_window_frames_changed)
        layout.addWidget(self.window_frames_spin, row, 1, 1, 2)  # 跨两列

        # Downsampling controls
        time_ds_label = QLabel("Time Downsample:")
        time_ds_label.setFont(QFont("Times New Roman", 8))
        time_ds_label.setMinimumHeight(22)  # 减小高度
        layout.addWidget(time_ds_label, row, 3)

        self.time_downsample_spin = QSpinBox()
        self.time_downsample_spin.setRange(1, 1000)
        self.time_downsample_spin.setValue(self._time_downsample)
        self.time_downsample_spin.setMaximumWidth(80)  # 固定宽度
        self.time_downsample_spin.setMinimumHeight(22)  # 减小高度
        self.time_downsample_spin.setFont(QFont("Times New Roman", 8))  # 调小字体
        self.time_downsample_spin.valueChanged.connect(self._on_time_downsample_changed)
        layout.addWidget(self.time_downsample_spin, row, 4)

        row += 1

        # Space downsampling
        space_ds_label = QLabel("Space Downsample:")
        space_ds_label.setFont(QFont("Times New Roman", 8))
        space_ds_label.setMinimumHeight(22)  # 减小高度
        layout.addWidget(space_ds_label, row, 0)

        self.space_downsample_spin = QSpinBox()
        self.space_downsample_spin.setRange(1, 100)
        self.space_downsample_spin.setValue(self._space_downsample)
        self.space_downsample_spin.setMaximumWidth(80)  # 固定宽度
        self.space_downsample_spin.setMinimumHeight(22)  # 减小高度
        self.space_downsample_spin.setFont(QFont("Times New Roman", 8))  # 调小字体
        self.space_downsample_spin.valueChanged.connect(self._on_space_downsample_changed)
        layout.addWidget(self.space_downsample_spin, row, 1, 1, 2)  # 跨两列

        # Color mapping controls
        colormap_label = QLabel("Colormap:")
        colormap_label.setFont(QFont("Times New Roman", 8))
        colormap_label.setMinimumHeight(22)  # 减小高度
        layout.addWidget(colormap_label, row, 3)

        self.colormap_combo = QComboBox()
        self.colormap_combo.setMaximumWidth(100)  # 固定宽度
        self.colormap_combo.setMinimumHeight(22)  # 减小高度
        self.colormap_combo.setFont(QFont("Times New Roman", 8))  # 调小字体
        for name, value in COLORMAP_OPTIONS:
            self.colormap_combo.addItem(name, value)
        self.colormap_combo.setCurrentText("Jet")
        self.colormap_combo.currentTextChanged.connect(self._on_colormap_changed)
        layout.addWidget(self.colormap_combo, row, 4)

        row += 1

        # Color range controls
        color_range_label = QLabel("Color Range:")
        color_range_label.setFont(QFont("Times New Roman", 8))
        color_range_label.setMinimumHeight(22)  # 减小高度
        layout.addWidget(color_range_label, row, 0)

        min_label = QLabel("Min:")
        min_label.setFont(QFont("Times New Roman", 8))
        min_label.setMinimumHeight(22)  # 减小高度
        layout.addWidget(min_label, row, 1)

        self.vmin_spin = QDoubleSpinBox()
        self.vmin_spin.setRange(-1.0, 1.0)           # Smaller range for phase data
        self.vmin_spin.setDecimals(3)                # 3 decimal places for precision
        self.vmin_spin.setSingleStep(0.001)          # Fine adjustment step
        self.vmin_spin.setValue(-0.02)               # Updated default value
        self.vmin_spin.setMaximumWidth(80)           # 固定宽度
        self.vmin_spin.setMinimumHeight(22)          # 减小高度
        self.vmin_spin.setFont(QFont("Times New Roman", 8))  # 调小字体
        self.vmin_spin.valueChanged.connect(self._on_vmin_changed)
        layout.addWidget(self.vmin_spin, row, 2)

        max_label = QLabel("Max:")
        max_label.setFont(QFont("Times New Roman", 8))
        max_label.setMinimumHeight(22)  # 减小高度
        layout.addWidget(max_label, row, 3)

        self.vmax_spin = QDoubleSpinBox()
        self.vmax_spin.setRange(-1.0, 1.0)           # Smaller range for phase data
        self.vmax_spin.setDecimals(3)                # 3 decimal places for precision
        self.vmax_spin.setSingleStep(0.001)          # Fine adjustment step
        self.vmax_spin.setValue(0.02)                # Updated default value
        self.vmax_spin.setMaximumWidth(80)           # 固定宽度
        self.vmax_spin.setMinimumHeight(22)          # 减小高度
        self.vmax_spin.setFont(QFont("Times New Roman", 8))  # 调小字体
        self.vmax_spin.valueChanged.connect(self._on_vmax_changed)
        layout.addWidget(self.vmax_spin, row, 4)

        row += 1

        # Reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setFont(QFont("Times New Roman", 8))  # 调小字体
        reset_btn.setMaximumWidth(120)  # 固定宽度
        reset_btn.setMinimumHeight(22)  # 减小高度
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn, row, 0, 1, 2)  # 跨两列

        # 添加弹性空间推到左边
        layout.setColumnStretch(5, 1)

        return group

    def _create_plot_area(self):
        """Create the main plot area with ImageView."""
        # Create ImageView for 2D data display
        self.image_view = pg.ImageView()

        # Set minimum size for larger display
        self.image_view.setMinimumSize(800, 400)  # 增大图像显示区域

        # Configure the image view - use getView() to access the ViewBox
        view = self.image_view.getView()
        if hasattr(view, 'setBackgroundColor'):
            view.setBackgroundColor('w')  # White background for main plot

        # Set colorbar background to white
        colorbar = self.image_view.getHistogramWidget()
        if colorbar and hasattr(colorbar, 'setBackground'):
            colorbar.setBackground('w')

        # Configure histogram widget background
        if hasattr(self.image_view, 'ui') and hasattr(self.image_view.ui, 'histogram'):
            hist_widget = self.image_view.ui.histogram
            if hasattr(hist_widget, 'setBackground'):
                hist_widget.setBackground('w')
            # Set gradient editor background
            if hasattr(hist_widget, 'gradient') and hasattr(hist_widget.gradient, 'setBackground'):
                hist_widget.gradient.setBackground('w')

        # Hide controls that we don't need
        self.image_view.ui.roiBtn.hide()  # Hide ROI button
        self.image_view.ui.menuBtn.hide()  # Hide menu button

        # Set up axes labels via the PlotItem
        plot_item = self.image_view.getImageItem().getViewBox().parent()
        if hasattr(plot_item, 'setLabel'):
            plot_item.setLabel('bottom', 'Time (frames)', **{'font-family': 'Times New Roman', 'font-size': '12pt'})
            plot_item.setLabel('left', 'Distance (points)', **{'font-family': 'Times New Roman', 'font-size': '12pt'})

            # Set axis font
            font = QFont("Times New Roman", 10)
            if hasattr(plot_item, 'getAxis'):
                bottom_axis = plot_item.getAxis('bottom')
                left_axis = plot_item.getAxis('left')
                if bottom_axis:
                    bottom_axis.setTickFont(font)
                    bottom_axis.setPen('k')  # Black axis
                    bottom_axis.setTextPen('k')  # Black text
                if left_axis:
                    left_axis.setTickFont(font)
                    left_axis.setPen('k')  # Black axis
                    left_axis.setTextPen('k')  # Black text

        # Initialize with empty data and apply initial colormap
        empty_data = np.zeros((10, 10))
        self.image_view.setImage(empty_data, autoRange=True)

        # Apply initial colormap
        self._apply_colormap()

        # Set colorbar background to white
        self._set_colorbar_white_background()

    def update_data(self, data: np.ndarray) -> bool:
        """
        Update the plot with new phase data.

        Args:
            data: Phase data array (1D: points, or 2D: frames x points)

        Returns:
            True if data was successfully processed and displayed
        """
        try:
            log.debug(f"Received data shape: {data.shape}, dtype: {data.dtype}")

            # Ensure data is 2D (frames x points)
            if data.ndim == 1:
                data = data.reshape(1, -1)

            # Update current dimensions
            frame_count, point_count = data.shape
            self._full_point_num = point_count

            log.debug(f"Processing {frame_count} frames with {point_count} points each")

            # Initialize buffer if needed
            if self._data_buffer is None:
                self._data_buffer = deque(maxlen=self._window_frames)
                log.debug(f"Initialized data buffer with maxlen={self._window_frames}")

            # Process each frame and add to buffer
            frames_added = 0
            for frame_idx in range(frame_count):
                frame_data = data[frame_idx, :]

                # Apply spatial range and downsampling
                processed_data = self._process_frame_data(frame_data)

                if processed_data is not None:
                    # Add to rolling window buffer
                    self._data_buffer.append(processed_data)
                    self._current_frame_count += 1
                    frames_added += 1
                else:
                    log.warning(f"Failed to process frame {frame_idx}")

            log.debug(f"Added {frames_added} frames to buffer. Buffer size: {len(self._data_buffer)}")

            # Update display
            self._update_display()
            return True

        except Exception as e:
            log.error(f"Error updating time-space data: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _process_frame_data(self, frame_data: np.ndarray) -> Optional[np.ndarray]:
        """
        Process a single frame of data with range selection and downsampling.

        Args:
            frame_data: 1D array of phase data for one frame

        Returns:
            Processed 1D array or None if processing failed
        """
        try:
            # Apply distance range
            start_idx = max(0, self._distance_start)
            end_idx = min(len(frame_data), self._distance_end)

            if start_idx >= end_idx:
                log.warning(f"Invalid distance range: {start_idx} >= {end_idx}")
                return None

            range_data = frame_data[start_idx:end_idx]

            # Apply spatial downsampling
            if self._space_downsample > 1:
                # Use strided indexing for downsampling
                range_data = range_data[::self._space_downsample]

            return range_data

        except Exception as e:
            log.error(f"Error processing frame data: {e}")
            return None

    def _update_display(self):
        """Update the 2D image display with current buffer data."""
        if not self._data_buffer or len(self._data_buffer) == 0:
            log.debug("No data in buffer for display update")
            return

        try:
            # Convert buffer to list of frame data
            buffer_list = list(self._data_buffer)

            # Each element in buffer_list is processed frame data (distance range applied)
            # We need to reorganize this data so that:
            # - Y axis represents distance points (spatial positions)
            # - X axis represents time (frames)

            if len(buffer_list) == 0:
                return

            # All frames should have the same spatial dimension after processing
            frame_length = len(buffer_list[0])  # Number of spatial points after range/downsample
            n_frames = len(buffer_list)

            log.debug(f"Buffer contains {n_frames} frames, each with {frame_length} spatial points")

            # Create 2D array: distance (Y) x time (X)
            # Shape will be (spatial_points, time_frames)
            display_data = np.zeros((frame_length, n_frames))

            # Fill the array: each column represents one time frame
            for frame_idx, frame_data in enumerate(buffer_list):
                if len(frame_data) == frame_length:
                    display_data[:, frame_idx] = frame_data
                else:
                    # Handle size mismatch by truncating or padding
                    min_len = min(len(frame_data), frame_length)
                    display_data[:min_len, frame_idx] = frame_data[:min_len]

            log.debug(f"Final display data shape: {display_data.shape} (distance x time)")
            log.debug(f"Data range: [{np.min(display_data):.4f}, {np.max(display_data):.4f}]")

            # Update image view with current color range (no auto-adjustment)
            self.image_view.setImage(display_data,
                                   levels=[self._vmin, self._vmax],
                                   autoRange=False,
                                   autoLevels=False)

            # Apply colormap
            self._apply_colormap()

            # Set colorbar background to white after image update
            self._set_colorbar_white_background()

            # Update scale and labels to reflect actual data dimensions
            self._update_axis_labels(display_data.shape)

            log.debug(f"Display updated successfully with data shape {display_data.shape}")

        except Exception as e:
            log.error(f"Error updating display: {e}")
            import traceback
            traceback.print_exc()

    def _set_colorbar_white_background(self):
        """Set colorbar background to white."""
        try:
            # Get histogram widget (colorbar)
            hist_widget = self.image_view.getHistogramWidget()

            if hist_widget is not None:
                # Try multiple approaches to set white background
                if hasattr(hist_widget, 'setBackground'):
                    hist_widget.setBackground('w')

                # Set background via stylesheet
                hist_widget.setStyleSheet("background-color: white;")

                # Set plot item background
                plot_item = hist_widget.plotItem
                if plot_item and hasattr(plot_item, 'getViewBox'):
                    view_box = plot_item.getViewBox()
                    if view_box and hasattr(view_box, 'setBackgroundColor'):
                        view_box.setBackgroundColor('w')

                # Set gradient editor background
                if hasattr(hist_widget, 'gradient'):
                    gradient = hist_widget.gradient
                    if gradient:
                        gradient.setStyleSheet("background-color: white;")

        except Exception as e:
            log.debug(f"Could not set colorbar background: {e}")

    def _apply_colormap(self):
        """Apply the selected colormap to the image view."""
        try:
            # Use PyQtGraph's built-in colormap
            if self._colormap == "jet":
                # Create a jet-like colormap
                colors = [
                    (0.0, (0, 0, 128)),      # dark blue
                    (0.25, (0, 0, 255)),     # blue
                    (0.5, (0, 255, 255)),    # cyan
                    (0.75, (255, 255, 0)),   # yellow
                    (1.0, (255, 0, 0))       # red
                ]
            elif self._colormap == "viridis":
                colors = [
                    (0.0, (68, 1, 84)),
                    (0.25, (59, 82, 139)),
                    (0.5, (33, 144, 140)),
                    (0.75, (93, 201, 99)),
                    (1.0, (253, 231, 37))
                ]
            elif self._colormap == "plasma":
                colors = [
                    (0.0, (13, 8, 135)),
                    (0.25, (126, 3, 168)),
                    (0.5, (203, 70, 121)),
                    (0.75, (248, 149, 64)),
                    (1.0, (240, 249, 33))
                ]
            elif self._colormap == "hot":
                colors = [
                    (0.0, (0, 0, 0)),        # black
                    (0.33, (255, 0, 0)),     # red
                    (0.66, (255, 255, 0)),   # yellow
                    (1.0, (255, 255, 255))   # white
                ]
            elif self._colormap == "gray":
                colors = [
                    (0.0, (0, 0, 0)),        # black
                    (1.0, (255, 255, 255))   # white
                ]
            else:
                # Default to a simple blue-red colormap
                colors = [
                    (0.0, (0, 0, 255)),      # blue
                    (0.5, (0, 255, 0)),      # green
                    (1.0, (255, 0, 0))       # red
                ]

            # Create colormap
            colormap = pg.ColorMap(pos=[c[0] for c in colors],
                                 color=[c[1] for c in colors])

            # Apply to histogram widget
            hist_widget = self.image_view.getHistogramWidget()
            if hist_widget is not None:
                hist_widget.gradient.setColorMap(colormap)

            log.debug(f"Applied colormap: {self._colormap}")

        except Exception as e:
            log.warning(f"Error applying colormap: {e}")
            import traceback
            traceback.print_exc()

    def _update_axis_labels(self, data_shape: tuple):
        """Update axis labels and scales based on data dimensions."""
        try:
            # Get the plot item
            plot_item = self.image_view.getImageItem().getViewBox().parent()

            if hasattr(plot_item, 'setLabel'):
                # data_shape is (distance_points, time_frames)
                n_distance_points, n_time_frames = data_shape

                # Update axis labels to reflect the correct orientation
                # X-axis: Time (frames in the rolling window)
                plot_item.setLabel('bottom', 'Time (frames)',
                                 **{'font-family': 'Times New Roman', 'font-size': '10pt'})

                # Y-axis: Distance (spatial points within the selected range)
                # Calculate actual distance values
                distance_start_actual = self._distance_start
                distance_end_actual = self._distance_start + n_distance_points * self._space_downsample

                plot_item.setLabel('left', f'Distance (points: {distance_start_actual}-{distance_end_actual})',
                                 **{'font-family': 'Times New Roman', 'font-size': '10pt'})

                # Configure axis properties
                if hasattr(plot_item, 'getAxis'):
                    bottom_axis = plot_item.getAxis('bottom')
                    left_axis = plot_item.getAxis('left')

                    # Set axis fonts and colors
                    font = QFont("Times New Roman", 9)
                    if bottom_axis:
                        bottom_axis.setTickFont(font)
                        bottom_axis.setPen('k')
                        bottom_axis.setTextPen('k')
                        bottom_axis.setStyle(showValues=True)
                    if left_axis:
                        left_axis.setTickFont(font)
                        left_axis.setPen('k')
                        left_axis.setTextPen('k')
                        left_axis.setStyle(showValues=True)

                log.debug(f"Updated axis labels: X=time({n_time_frames} frames), Y=distance({n_distance_points} points)")

        except Exception as e:
            log.warning(f"Error updating axis labels: {e}")

    def _on_distance_start_changed(self, value: int):
        """Handle distance start change."""
        if value < self._distance_end:
            self._distance_start = value
            self._update_distance_range()
            self.parametersChanged.emit()

    def _on_distance_end_changed(self, value: int):
        """Handle distance end change."""
        if value > self._distance_start:
            self._distance_end = value
            self._update_distance_range()
            self.parametersChanged.emit()

    def _update_distance_range(self):
        """Update the distance range spin box constraints."""
        self.distance_start_spin.setMaximum(self._distance_end - 1)
        self.distance_end_spin.setMinimum(self._distance_start + 1)

        # Update maximum based on current data size
        if self._full_point_num > 0:
            self.distance_end_spin.setMaximum(self._full_point_num)

    def _on_window_frames_changed(self, value: int):
        """Handle window frames change."""
        self._window_frames = value

        # Recreate buffer with new size
        if self._data_buffer is not None:
            old_data = list(self._data_buffer)
            self._data_buffer = deque(old_data, maxlen=value)
            self._update_display()

        self.parametersChanged.emit()

    def _on_time_downsample_changed(self, value: int):
        """Handle time downsampling change."""
        self._time_downsample = value
        self._update_display()
        self.parametersChanged.emit()

    def _on_space_downsample_changed(self, value: int):
        """Handle space downsampling change."""
        self._space_downsample = value
        # Clear buffer to force reprocessing with new downsampling
        if self._data_buffer is not None:
            self._data_buffer.clear()
        self.parametersChanged.emit()

    def _on_colormap_changed(self, text: str):
        """Handle colormap change."""
        # Find the colormap value
        for name, value in COLORMAP_OPTIONS:
            if name == text:
                self._colormap = value
                break

        # Apply the new colormap immediately
        self._apply_colormap()
        self.parametersChanged.emit()

    def _on_vmin_changed(self, value: float):
        """Handle minimum color value change."""
        self._vmin = value
        self._update_display()
        self.parametersChanged.emit()

    def _on_vmax_changed(self, value: float):
        """Handle maximum color value change."""
        self._vmax = value
        self._update_display()
        self.parametersChanged.emit()

    def _reset_to_defaults(self):
        """Reset all parameters to default values."""
        self._window_frames = 5
        self._distance_start = 40     # Updated reset value
        self._distance_end = 100      # Updated reset value
        self._time_downsample = 50
        self._space_downsample = 2
        self._colormap = "jet"
        self._vmin = -0.02            # Updated reset value
        self._vmax = 0.02             # Updated reset value

        # Update UI controls
        self.window_frames_spin.setValue(self._window_frames)
        self.distance_start_spin.setValue(self._distance_start)
        self.distance_end_spin.setValue(self._distance_end)
        self.time_downsample_spin.setValue(self._time_downsample)
        self.space_downsample_spin.setValue(self._space_downsample)
        self.colormap_combo.setCurrentText("Jet")
        self.vmin_spin.setValue(self._vmin)
        self.vmax_spin.setValue(self._vmax)

        # Clear buffer and recreate with default size
        if self._data_buffer is not None:
            self._data_buffer = deque(maxlen=self._window_frames)

        self.parametersChanged.emit()

    def get_parameters(self) -> Dict[str, Any]:
        """
        Get current time-space plot parameters.

        Returns:
            Dictionary with current parameter values
        """
        return {
            'window_frames': self._window_frames,
            'distance_range_start': self._distance_start,
            'distance_range_end': self._distance_end,
            'time_downsample': self._time_downsample,
            'space_downsample': self._space_downsample,
            'colormap_type': self._colormap,
            'vmin': self._vmin,
            'vmax': self._vmax
        }

    def set_parameters(self, params: Dict[str, Any]):
        """
        Set time-space plot parameters.

        Args:
            params: Dictionary with parameter values to set
        """
        if 'window_frames' in params:
            self.window_frames_spin.setValue(params['window_frames'])
        if 'distance_range_start' in params:
            self.distance_start_spin.setValue(params['distance_range_start'])
        if 'distance_range_end' in params:
            self.distance_end_spin.setValue(params['distance_range_end'])
        if 'time_downsample' in params:
            self.time_downsample_spin.setValue(params['time_downsample'])
        if 'space_downsample' in params:
            self.space_downsample_spin.setValue(params['space_downsample'])
        if 'colormap_type' in params:
            # Find matching colormap name
            for name, value in COLORMAP_OPTIONS:
                if value == params['colormap_type']:
                    self.colormap_combo.setCurrentText(name)
                    break
        if 'vmin' in params:
            self.vmin_spin.setValue(params['vmin'])
        if 'vmax' in params:
            self.vmax_spin.setValue(params['vmax'])

    def clear_data(self):
        """Clear all data buffers and reset display."""
        if self._data_buffer is not None:
            self._data_buffer.clear()

        # Reset to empty display
        empty_data = np.zeros((10, 10))
        self.image_view.setImage(empty_data, autoRange=True)

        self._current_frame_count = 0
        log.debug("TimeSpacePlotWidget data cleared")