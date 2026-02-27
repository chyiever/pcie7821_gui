"""
Time-Space Plot Widget

PyQt5 widget for 2D time-space visualization of DAS phase data.
Implements rolling window display with configurable parameters.

Features:
- Real-time 2D image display with time (X) vs distance (Y) axes
- Rolling window buffer for smooth scrolling effect
- Configurable downsampling for performance optimization
- Customizable color mapping and range
- PyQtGraph PlotWidget + ImageItem for reliable axis rendering

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
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5 import QtCore
from PyQt5.QtGui import QFont
import pyqtgraph as pg

from logger import get_logger

# Module logger
log = get_logger("time_space_plot")

# Custom colormap creation for missing PyQtGraph colormaps
def _create_custom_colormaps():
    """创建自定义colormap来替代缺失的PyQtGraph文件"""
    custom_maps = {}

    try:
        import numpy as np

        # Jet colormap (经典科学可视化)
        jet_colors = np.array([
            [0, 0, 0.5], [0, 0, 1], [0, 0.5, 1], [0, 1, 1],
            [0.5, 1, 0.5], [1, 1, 0], [1, 0.5, 0], [1, 0, 0], [0.5, 0, 0]
        ])
        custom_maps['jet'] = pg.ColorMap(np.linspace(0, 1, len(jet_colors)), jet_colors)

        # HSV colormap (色相环)
        hsv_colors = np.array([
            [1, 0, 0], [1, 0.5, 0], [1, 1, 0], [0.5, 1, 0],
            [0, 1, 0], [0, 1, 0.5], [0, 1, 1], [0, 0.5, 1],
            [0, 0, 1], [0.5, 0, 1], [1, 0, 1], [1, 0, 0.5]
        ])
        custom_maps['hsv'] = pg.ColorMap(np.linspace(0, 1, len(hsv_colors)), hsv_colors)

        # Hot colormap (热度图)
        hot_colors = np.array([
            [0, 0, 0], [0.4, 0, 0], [0.8, 0, 0], [1, 0, 0],
            [1, 0.4, 0], [1, 0.8, 0], [1, 1, 0], [1, 1, 0.5], [1, 1, 1]
        ])
        custom_maps['hot'] = pg.ColorMap(np.linspace(0, 1, len(hot_colors)), hot_colors)

        # Cool colormap (冷色调)
        cool_colors = np.array([
            [0, 1, 1], [0.2, 0.8, 1], [0.4, 0.6, 1], [0.6, 0.4, 1], [0.8, 0.2, 1], [1, 0, 1]
        ])
        custom_maps['cool'] = pg.ColorMap(np.linspace(0, 1, len(cool_colors)), cool_colors)

        # Gray colormap (灰度)
        gray_colors = np.array([[0, 0, 0], [1, 1, 1]])
        custom_maps['gray'] = pg.ColorMap(np.linspace(0, 1, len(gray_colors)), gray_colors)

        # Seismic colormap (地震数据专用)
        seismic_colors = np.array([
            [0, 0, 0.3], [0, 0, 1], [0.5, 0.5, 1], [1, 1, 1],
            [1, 0.5, 0.5], [1, 0, 0], [0.3, 0, 0]
        ])
        custom_maps['seismic'] = pg.ColorMap(np.linspace(0, 1, len(seismic_colors)), seismic_colors)

        log.info(f"Created {len(custom_maps)} custom colormaps")

    except Exception as e:
        log.warning(f"Failed to create custom colormaps: {e}")

    return custom_maps

# 全局存储自定义colormap
_CUSTOM_COLORMAPS = _create_custom_colormaps()

# Available colormap options for PyQtGraph
COLORMAP_OPTIONS = [
    ("Jet", "jet"),
    ("HSV", "hsv"),
    ("Viridis", "viridis"),
    ("Plasma", "plasma"),
    ("Inferno", "inferno"),
    ("Magma", "magma"),
    ("Seismic", "seismic"),
    ("Gray", "gray"),
    ("Hot", "hot"),
    ("Cool", "cool")
]


class TimeSpacePlotWidget(QWidget):
    """
    基于 PlotWidget + ImageItem 的 Time-Space 图实现

    完全替代 ImageView，确保坐标轴刻度的可靠显示
    这个版本牺牲了 ImageView 的便利性，但提供了完全的轴控制
    """

    # 信号定义
    parametersChanged = pyqtSignal()
    pointCountChanged = pyqtSignal(int)
    plotStateChanged = pyqtSignal(bool)  # 新增：绘图状态变化信号

    def __init__(self):
        """初始化 PlotWidget 版本的 TimeSpacePlot"""
        super().__init__()
        log.debug("Initializing TimeSpacePlotWidget (PlotWidget-based)")

        # 数据相关参数 (与原版本相同)
        self._data_buffer = None
        self._max_window_frames = 100
        self._window_frames = 5
        self._distance_start = 40
        self._distance_end = 100
        self._time_downsample = 50
        self._space_downsample = 2
        self._colormap = "jet"
        self._vmin = -0.1
        self._vmax = 0.1

        # 显示相关参数
        self._current_frame_count = 0
        self._plot_enabled = False  # 替代enable_plot
        self._pending_update = False
        self._full_point_num = 0  # V2新增：完整点数记录

        self._setup_ui()
        log.debug("TimeSpacePlotWidget initialized successfully")

    def _setup_ui(self):
        """设置基于 PlotWidget 的UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # 控制面板 (重用原来的方法)
        control_panel = self._create_control_panel()
        control_panel.setMaximumHeight(140)  # 增加高度，从120调整到140
        layout.addWidget(control_panel)

        # 创建水平布局容纳图形和颜色条
        plot_layout = QHBoxLayout()

        # 创建 PlotWidget 替代 ImageView
        self._create_plot_area()
        plot_layout.addWidget(self.plot_widget, 1)  # 给图形更大比重

        # 创建颜色条
        self._create_colorbar()
        plot_layout.addWidget(self.histogram_widget)  # 添加HistogramLUTWidget

        plot_widget = QWidget()
        plot_widget.setLayout(plot_layout)
        layout.addWidget(plot_widget, 1)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _create_plot_area(self):
        """创建基于 PlotWidget 的绘图区域"""
        # 创建 PlotWidget (完整轴支持)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setMinimumSize(800, 400)

        # 添加 ImageItem 用于2D数据显示
        self.image_item = pg.ImageItem()
        self.plot_widget.addItem(self.image_item)

        # 完全可靠的轴配置 - 正确的坐标轴定义
        self.plot_widget.setLabel('bottom', 'Time (s)',
                                color='k', **{'font-size': '10pt', 'font-family': 'Times New Roman'})
        self.plot_widget.setLabel('left', 'Distance (points)',
                                color='k', **{'font-size': '10pt', 'font-family': 'Times New Roman'})

        # 确保坐标轴显示
        self.plot_widget.showAxis('bottom', show=True)
        self.plot_widget.showAxis('left', show=True)
        self.plot_widget.showAxis('top', show=False)
        self.plot_widget.showAxis('right', show=False)

        # 轴字体设置
        font = QFont("Times New Roman", 9)
        for axis_name in ['bottom', 'left']:
            axis = self.plot_widget.getAxis(axis_name)
            if axis:
                axis.setTickFont(font)
                axis.setPen('k')
                axis.setTextPen('k')
                axis.setStyle(showValues=True)
                axis.enableAutoSIPrefix(False)

        # 设置背景和鼠标交互
        self.plot_widget.setBackground('w')
        view_box = self.plot_widget.getViewBox()
        view_box.setMouseEnabled(x=True, y=True)
        view_box.setAspectLocked(False)

        # 重要：初始化时禁用自动范围，为后续手动控制做准备
        view_box.enableAutoRange(enable=False)
        view_box.setAutoVisible(x=False, y=False)

        # 创建手动 ColorBar
        self._create_colorbar()

        # 应用初始colormap
        self._apply_colormap()

        log.info("PlotWidget plot area created with guaranteed axis display")

    def _create_colorbar(self):
        """创建包含直方图和亮度/对比度控制的复合颜色条组件"""
        # 使用PyQtGraph的HistogramLUTWidget，它包含：
        # 1. 颜色渐变条（垂直方向）
        # 2. 数据直方图分布
        # 3. 亮度/对比度滑块控制
        self.histogram_widget = pg.HistogramLUTWidget()
        self.histogram_widget.setFixedWidth(90)  # 减小宽度，避免与主图重叠
        self.histogram_widget.setMinimumHeight(400)

        # 从控制面板获取初始颜色范围，不使用自动更新
        # 颜色范围完全由前面板控制
        self.histogram_widget.setLevels(self._vmin, self._vmax)

        # 应用初始颜色映射
        self._apply_initial_colormap_to_histogram()

        # 注意：不连接sigLevelsChanged信号，避免自动更新vmin/vmax
        # 颜色范围完全由控制面板的spinbox控制

        # 设置背景为白色
        self.histogram_widget.setBackground('w')

        # 设置颜色栏刻度字体为Times New Roman
        self._setup_colorbar_font()

        log.debug("HistogramLUTWidget colorbar created (manual control mode)")

    def _setup_colorbar_font(self):
        """设置颜色栏刻度字体为Times New Roman"""
        try:
            if not hasattr(self, 'histogram_widget') or self.histogram_widget is None:
                return

            # Get the plot item from histogram widget
            plot_item = getattr(self.histogram_widget, 'plotItem', None)
            if plot_item is None:
                return

            # Set Times New Roman font for colorbar axis
            font = QFont("Times New Roman", 8)

            # Configure the right axis (y-axis of the colorbar)
            axis = plot_item.getAxis('left')
            if axis:
                axis.setTickFont(font)
                axis.setPen('k')
                axis.setTextPen('k')
                axis.setStyle(showValues=True)
                log.debug("Colorbar font set to Times New Roman")

        except Exception as e:
            log.debug(f"Could not set colorbar font: {e}")

    def _apply_initial_colormap_to_histogram(self):
        """为HistogramLUTWidget应用初始颜色映射"""
        try:
            # 获取当前选择的colormap（使用改进的获取方法）
            colormap_obj = self._get_colormap(self._colormap)

            if colormap_obj is None:
                log.warning(f"Could not get colormap '{self._colormap}' for histogram")
                return

            # 应用到HistogramLUTWidget
            if hasattr(self.histogram_widget, 'gradient'):
                self.histogram_widget.gradient.setColorMap(colormap_obj)
                log.debug(f"Applied initial colormap '{self._colormap}' to HistogramLUTWidget")

        except Exception as e:
            log.warning(f"Could not apply initial colormap to HistogramLUTWidget: {e}")
            # 如果失败，使用默认的viridis
            try:
                default_colormap = self._get_colormap('viridis')
                if default_colormap and hasattr(self.histogram_widget, 'gradient'):
                    self.histogram_widget.gradient.setColorMap(default_colormap)
                    log.debug("Applied fallback colormap to HistogramLUTWidget")
            except Exception as e2:
                log.warning(f"Could not apply fallback colormap: {e2}")

    def _get_colormap(self, colormap_name):
        """获取颜色映射对象，优先使用PyQtGraph内置，回退到自定义"""
        try:
            # 首先尝试PyQtGraph内置colormap
            return pg.colormap.get(colormap_name)
        except Exception as e:
            log.debug(f"PyQtGraph colormap '{colormap_name}' not found: {e}")
            # 使用自定义colormap
            if colormap_name in _CUSTOM_COLORMAPS:
                log.debug(f"Using custom colormap: {colormap_name}")
                return _CUSTOM_COLORMAPS[colormap_name]
            else:
                # 最后回退到viridis
                log.warning(f"Colormap '{colormap_name}' not found, falling back to viridis")
                try:
                    return pg.colormap.get('viridis')
                except:
                    # 如果viridis也没有，使用自定义gray
                    return _CUSTOM_COLORMAPS.get('gray', None)

    def _apply_colormap(self):
        """应用颜色映射到图像项和HistogramLUTWidget"""
        try:
            # 获取当前选择的colormap
            colormap_name = self._colormap

            # 获取colormap对象（内置或自定义）
            colormap_obj = self._get_colormap(colormap_name)

            if colormap_obj is None:
                log.error(f"Could not get any colormap for '{colormap_name}'")
                return

            # 应用到ImageItem
            if hasattr(self, 'image_item'):
                self.image_item.setColorMap(colormap_obj)

            # 应用到HistogramLUTWidget
            if hasattr(self, 'histogram_widget') and hasattr(self.histogram_widget, 'gradient'):
                self.histogram_widget.gradient.setColorMap(colormap_obj)

            log.debug(f"Applied colormap '{colormap_name}' to both ImageItem and HistogramLUTWidget")

        except Exception as e:
            log.warning(f"Could not apply colormap '{self._colormap}': {e}")
            # 最后的错误处理：使用viridis
            try:
                default_colormap = self._get_colormap('viridis')
                if default_colormap and hasattr(self, 'image_item'):
                    self.image_item.setColorMap(default_colormap)
                if default_colormap and hasattr(self, 'histogram_widget') and hasattr(self.histogram_widget, 'gradient'):
                    self.histogram_widget.gradient.setColorMap(default_colormap)
                log.debug("Applied fallback colormap")
            except Exception as e2:
                log.warning(f"Could not apply fallback colormap: {e2}")

    def _create_control_panel(self):
        """创建控制面板 - 完整实现"""
        group = QGroupBox()  # 移除标题文字
        group.setFont(QFont("Times New Roman", 9))

        layout = QGridLayout(group)
        layout.setHorizontalSpacing(15)
        layout.setVerticalSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)  # 减少上边距

        # 删除状态指示标签，直接开始第一行控件

        # Row 0: Distance Range + Window Frames + Time Downsample + Space Downsample (上移一行)
        row = 0

        # Distance Range controls
        distance_label = QLabel("Distance Range:")
        distance_label.setFont(QFont("Times New Roman", 8))
        distance_label.setMinimumHeight(22)
        layout.addWidget(distance_label, row, 0)

        from_label = QLabel("From:")
        from_label.setFont(QFont("Times New Roman", 8))
        from_label.setMinimumHeight(22)
        layout.addWidget(from_label, row, 1)

        self.distance_start_spin = QSpinBox()
        self.distance_start_spin.setRange(0, 1000000)
        self.distance_start_spin.setValue(40)
        self.distance_start_spin.setMaximumWidth(60)
        self.distance_start_spin.setMinimumHeight(22)
        self.distance_start_spin.setFont(QFont("Times New Roman", 8))
        self.distance_start_spin.valueChanged.connect(self._on_distance_start_changed)
        layout.addWidget(self.distance_start_spin, row, 2)

        to_label = QLabel("To:")
        to_label.setFont(QFont("Times New Roman", 8))
        to_label.setMinimumHeight(22)
        layout.addWidget(to_label, row, 3)

        self.distance_end_spin = QSpinBox()
        self.distance_end_spin.setRange(1, 1000000)
        self.distance_end_spin.setValue(100)
        self.distance_end_spin.setMaximumWidth(60)
        self.distance_end_spin.setMinimumHeight(22)
        self.distance_end_spin.setFont(QFont("Times New Roman", 8))
        self.distance_end_spin.valueChanged.connect(self._on_distance_end_changed)
        layout.addWidget(self.distance_end_spin, row, 4)

        # Window Frames
        window_label = QLabel("Window Frames:")
        window_label.setFont(QFont("Times New Roman", 8))
        window_label.setMinimumHeight(22)
        layout.addWidget(window_label, row, 5)

        self.window_frames_spin = QSpinBox()
        self.window_frames_spin.setRange(1, self._max_window_frames)
        self.window_frames_spin.setValue(self._window_frames)
        self.window_frames_spin.setMaximumWidth(50)
        self.window_frames_spin.setMinimumHeight(22)
        self.window_frames_spin.setFont(QFont("Times New Roman", 8))
        self.window_frames_spin.valueChanged.connect(self._on_window_frames_changed)
        layout.addWidget(self.window_frames_spin, row, 6)

        # Time Downsample
        time_ds_label = QLabel("Time DS:")
        time_ds_label.setFont(QFont("Times New Roman", 8))
        time_ds_label.setMinimumHeight(22)
        layout.addWidget(time_ds_label, row, 7)

        self.time_downsample_spin = QSpinBox()
        self.time_downsample_spin.setRange(1, 1000)
        self.time_downsample_spin.setValue(self._time_downsample)
        self.time_downsample_spin.setMaximumWidth(50)
        self.time_downsample_spin.setMinimumHeight(22)
        self.time_downsample_spin.setFont(QFont("Times New Roman", 8))
        self.time_downsample_spin.valueChanged.connect(self._on_time_downsample_changed)
        layout.addWidget(self.time_downsample_spin, row, 8)

        # Space Downsample
        space_ds_label = QLabel("Space DS:")
        space_ds_label.setFont(QFont("Times New Roman", 8))
        space_ds_label.setMinimumHeight(22)
        layout.addWidget(space_ds_label, row, 9)

        self.space_downsample_spin = QSpinBox()
        self.space_downsample_spin.setRange(1, 100)
        self.space_downsample_spin.setValue(self._space_downsample)
        self.space_downsample_spin.setMaximumWidth(50)
        self.space_downsample_spin.setMinimumHeight(22)
        self.space_downsample_spin.setFont(QFont("Times New Roman", 8))
        self.space_downsample_spin.valueChanged.connect(self._on_space_downsample_changed)
        layout.addWidget(self.space_downsample_spin, row, 10)

        # Row 1: Color Range + Colormap + Reset Button + PLOT Button (上移一行)
        row = 1

        # Color Range controls
        color_range_label = QLabel("Color Range:")
        color_range_label.setFont(QFont("Times New Roman", 8))
        color_range_label.setMinimumHeight(22)
        layout.addWidget(color_range_label, row, 0)

        min_label = QLabel("Min:")
        min_label.setFont(QFont("Times New Roman", 8))
        min_label.setMinimumHeight(22)
        layout.addWidget(min_label, row, 1)

        self.vmin_spin = QDoubleSpinBox()
        self.vmin_spin.setRange(-10000.0, 10000.0)  # 扩大范围到±10000
        self.vmin_spin.setDecimals(3)
        self.vmin_spin.setSingleStep(0.001)
        self.vmin_spin.setValue(-0.1)
        self.vmin_spin.setMaximumWidth(60)
        self.vmin_spin.setMinimumHeight(22)
        self.vmin_spin.setFont(QFont("Times New Roman", 8))
        self.vmin_spin.valueChanged.connect(self._on_vmin_changed)
        layout.addWidget(self.vmin_spin, row, 2)

        max_label = QLabel("Max:")
        max_label.setFont(QFont("Times New Roman", 8))
        max_label.setMinimumHeight(22)
        layout.addWidget(max_label, row, 3)

        self.vmax_spin = QDoubleSpinBox()
        self.vmax_spin.setRange(-10000.0, 10000.0)  # 扩大范围到±10000
        self.vmax_spin.setDecimals(3)
        self.vmax_spin.setSingleStep(0.001)
        self.vmax_spin.setValue(0.1)
        self.vmax_spin.setMaximumWidth(60)
        self.vmax_spin.setMinimumHeight(22)
        self.vmax_spin.setFont(QFont("Times New Roman", 8))
        self.vmax_spin.valueChanged.connect(self._on_vmax_changed)
        layout.addWidget(self.vmax_spin, row, 4)

        # Colormap
        colormap_label = QLabel("Colormap:")
        colormap_label.setFont(QFont("Times New Roman", 8))
        colormap_label.setMinimumHeight(22)
        layout.addWidget(colormap_label, row, 5)

        self.colormap_combo = QComboBox()
        self.colormap_combo.setMaximumWidth(80)
        self.colormap_combo.setMinimumHeight(22)
        self.colormap_combo.setFont(QFont("Times New Roman", 8))
        for name, value in COLORMAP_OPTIONS:
            self.colormap_combo.addItem(name, value)
        self.colormap_combo.setCurrentText("Jet")
        self.colormap_combo.currentTextChanged.connect(self._on_colormap_changed)
        layout.addWidget(self.colormap_combo, row, 6)

        # Reset Button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setFont(QFont("Times New Roman", 8))
        reset_btn.setMaximumWidth(120)
        reset_btn.setMinimumHeight(22)
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn, row, 7)

        # PLOT Button (替代原来的Time-space模式选择)
        self.plot_btn = QPushButton("PLOT")
        self.plot_btn.setFont(QFont("Times New Roman", 8, QFont.Bold))
        self.plot_btn.setMaximumWidth(60)
        self.plot_btn.setMinimumHeight(22)
        self.plot_btn.setCheckable(True)  # 可切换状态
        self.plot_btn.setChecked(False)   # 初始状态：停止
        self._update_plot_button_style()
        self.plot_btn.clicked.connect(self._on_plot_button_clicked)
        layout.addWidget(self.plot_btn, row, 8)

        # 添加弹性空间
        layout.setColumnStretch(11, 1)

        return group

    def _on_plot_button_clicked(self, checked: bool):
        """处理PLOT按钮点击事件"""
        self._plot_enabled = checked
        self._update_plot_button_style()

        # 发射信号通知主窗口
        if hasattr(self, 'plotStateChanged'):
            self.plotStateChanged.emit(self._plot_enabled)

        log.info(f"Time-space plot {'enabled' if self._plot_enabled else 'disabled'}")

    def _update_plot_button_style(self):
        """更新PLOT按钮样式"""
        if self._plot_enabled:
            # 绿色：正在绘图
            self.plot_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: 1px solid #45a049;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        else:
            # 灰色：停止绘图
            self.plot_btn.setStyleSheet("""
                QPushButton {
                    background-color: #9E9E9E;
                    color: white;
                    border: 1px solid #757575;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #757575;
                }
            """)

    def is_plot_enabled(self) -> bool:
        """返回当前绘图状态"""
        return self._plot_enabled

    def _on_distance_start_changed(self, value: int):
        """处理起始距离变化"""
        self._distance_start = value
        if self._data_buffer is not None:
            self._data_buffer.clear()
            self._update_display()
        self.parametersChanged.emit()

    def _on_distance_end_changed(self, value: int):
        """处理结束距离变化"""
        self._distance_end = value
        if self._data_buffer is not None:
            self._data_buffer.clear()
            self._update_display()
        self.parametersChanged.emit()

    def _on_window_frames_changed(self, value: int):
        """处理窗口帧数变化"""
        self._window_frames = value
        # 重新初始化缓冲区
        self._data_buffer = deque(maxlen=self._window_frames)
        if self._data_buffer is not None:
            self._data_buffer.clear()
            self._update_display()
        self.parametersChanged.emit()

    def _on_space_downsample_changed(self, value: int):
        """处理空间降采样变化"""
        self._space_downsample = value
        if self._data_buffer is not None:
            self._data_buffer.clear()
        self.parametersChanged.emit()

    def _on_time_downsample_changed(self, value: int):
        """处理时间降采样变化"""
        self._time_downsample = value
        if self._data_buffer is not None:
            self._data_buffer.clear()
        self.parametersChanged.emit()

        log.debug(f"Update interval changed to {value}ms")

    def _on_colormap_changed(self, text: str):
        """处理颜色映射变化"""
        for name, value in COLORMAP_OPTIONS:
            if name == text:
                self._colormap = value
                break
        self._apply_colormap()
        self.parametersChanged.emit()

    def _on_vmin_changed(self, value: float):
        """处理最小颜色值变化"""
        self._vmin = value
        # 更新HistogramLUTWidget显示范围（单向控制）
        if hasattr(self, 'histogram_widget'):
            self.histogram_widget.setLevels(self._vmin, self._vmax)
        self._update_display()
        self.parametersChanged.emit()

    def _on_vmax_changed(self, value: float):
        """处理最大颜色值变化"""
        self._vmax = value
        # 更新HistogramLUTWidget显示范围（单向控制）
        if hasattr(self, 'histogram_widget'):
            self.histogram_widget.setLevels(self._vmin, self._vmax)
        self._update_display()
        self.parametersChanged.emit()

    def _reset_to_defaults(self):
        """重置为默认值"""
        self._window_frames = 5
        self._distance_start = 40
        self._distance_end = 100
        self._time_downsample = 50
        self._space_downsample = 2
        self._colormap = "jet"
        self._vmin = -0.1
        self._vmax = 0.1

        # 更新UI控件
        self.window_frames_spin.setValue(self._window_frames)
        self.distance_start_spin.setValue(self._distance_start)
        self.distance_end_spin.setValue(self._distance_end)
        self.time_downsample_spin.setValue(self._time_downsample)
        self.space_downsample_spin.setValue(self._space_downsample)
        self.colormap_combo.setCurrentText("Jet")
        self.vmin_spin.setValue(self._vmin)
        self.vmax_spin.setValue(self._vmax)

        # 清空缓冲区
        if self._data_buffer is not None:
            self._data_buffer = deque(maxlen=self._window_frames)

        self.parametersChanged.emit()

    def update_data(self, data: np.ndarray) -> bool:
        """PlotWidget版本的数据更新方法"""
        try:
            log.debug(f"PlotWidget version received data shape: {data.shape}")

            # 检查绘图是否启用
            if not self._plot_enabled:
                log.debug("Plot disabled, skipping data update")
                return False

            if data.ndim == 1:
                data = data.reshape(1, -1)

            frame_count, point_count = data.shape
            if self._full_point_num != point_count:
                self._full_point_num = point_count
                self.pointCountChanged.emit(point_count)

            # 数据处理 (重用原有逻辑)
            if self._data_buffer is None:
                self._data_buffer = deque(maxlen=self._window_frames)

            processed_data_block = self._process_data_block(data)
            if processed_data_block is not None:
                self._data_buffer.append(processed_data_block)

            # 调度显示更新
            self._schedule_display_update()
            return True

        except Exception as e:
            log.error(f"Error in PlotWidget version update_data: {e}")
            return False

    def _process_data_block(self, data_block: np.ndarray) -> Optional[np.ndarray]:
        """处理数据块 - 重用原有逻辑"""
        try:
            frame_count, point_count = data_block.shape

            # 应用距离范围
            start_idx = max(0, self._distance_start)
            end_idx = min(point_count, self._distance_end)

            if start_idx >= end_idx:
                return None

            range_data = data_block[:, start_idx:end_idx]

            # 应用降采样
            if self._space_downsample > 1:
                range_data = range_data[:, ::self._space_downsample]

            if self._time_downsample > 1 and frame_count > self._time_downsample:
                range_data = range_data[::self._time_downsample, :]

            return range_data

        except Exception as e:
            log.error(f"Error processing data block in PlotWidget version: {e}")
            return None

    def _schedule_display_update(self):
        """直接更新显示，不使用定时器控制"""
        # 改为每帧直接更新，不使用定时器延迟
        self._update_display()

    def _update_display(self):
        """PlotWidget版本的显示更新 - 正确的坐标轴定义"""
        if not self._data_buffer or len(self._data_buffer) == 0:
            return

        try:
            # 合并缓冲区数据 - 确保时间顺序正确
            buffer_list = list(self._data_buffer)
            time_space_data = np.concatenate(buffer_list, axis=0)

            log.debug(f"PlotWidget updating display with data shape: {time_space_data.shape}")
            log.debug(f"Data buffer length: {len(self._data_buffer)}, window_frames: {self._window_frames}")

            # 重要：重新分析坐标轴映射
            # 原始数据: (time_frames, space_points)
            # 我们的目标: Y轴=distance, X轴=time
            #
            # PyQtGraph ImageItem的坐标系统：
            # - 第一个维度对应Y轴(垂直方向)
            # - 第二个维度对应X轴(水平方向)
            #
            # 所以如果原始数据是 (time_frames, space_points)
            # 要实现 Y轴=distance, X轴=time，我们需要转置！

            # 尝试不转置，看看效果
            # display_data = time_space_data  # 不转置：(time_frames, space_points)
            # 这样的话：Y轴=time, X轴=space，这不是我们要的

            # 不需要转置！因为在_update_display中已经转置过了
            # time_space_data已经经过第一次转置，现在应该是(time, space)形状
            display_data = time_space_data  # 直接使用，不再转置

            log.debug(f"PlotWidget V2: received data shape: {time_space_data.shape}")
            log.debug(f"PlotWidget V2: using data without additional transpose")

            log.debug(f"Time-space data shape after processing: {display_data.shape} (should be time x space)")
            log.debug(f"Display data range: [{np.min(display_data):.3f}, {np.max(display_data):.3f}]")

            # 设置图像数据
            self.image_item.setImage(display_data, levels=[self._vmin, self._vmax])

            # 连接数据到HistogramLUTWidget以显示直方图分布
            if hasattr(self, 'histogram_widget'):
                self.histogram_widget.setImageItem(self.image_item)
                # 设置颜色范围，这会更新直方图的显示范围
                self.histogram_widget.setLevels(self._vmin, self._vmax)

            # 获取数据维度 - 现在应该是(time, space)
            n_time_points, n_spatial_points = display_data.shape  # time在Y方向，space在X方向

            # 计算实际坐标范围
            distance_start = self._distance_start
            distance_end = self._distance_end

            # X轴: 时间范围计算 - 重要：不受time DS影响
            try:
                from config import AllParams
                config = AllParams()
                scan_rate_hz = config.basic.scan_rate  # Hz
            except:
                scan_rate_hz = 2000  # 默认值

            # 计算实际时间长度：应该基于原始帧数，不是降采样后的帧数
            original_time_points = time_space_data.shape[0]  # 原始时间帧数
            current_displayed_time_points = display_data.shape[1]  # 当前显示的时间点数

            # 实际时间长度应该基于缓冲区中的总帧数，不受降采样影响
            time_duration_s = original_time_points / scan_rate_hz

            log.debug(f"Time calculation: original_frames={original_time_points}, "
                     f"displayed_frames={current_displayed_time_points}, "
                     f"time_duration={time_duration_s:.3f}s, scan_rate={scan_rate_hz}Hz")

            # 计算实际的坐标范围
            distance_start = self._distance_start
            distance_end = self._distance_end

            # 获取处理后的数据维度
            n_spatial_points, n_time_points_displayed = display_data.shape

            # 设置图像边界 - 映射到实际坐标范围
            # 注意：时间轴应该映射到实际时间，空间轴映射到实际距离
            self.image_item.setRect(pg.QtCore.QRectF(
                0, distance_start,  # 起始位置: (时间=0, 距离=distance_start)
                time_duration_s, distance_end - distance_start  # 宽度=实际时间长度, 高度=距离范围
            ))

            log.debug(f"Image rect set: X=[0, {time_duration_s:.3f}s], Y=[{distance_start}, {distance_end}]")

            self._current_frame_count += 1

        except Exception as e:
            log.error(f"Error updating PlotWidget display: {e}")

    # ========== V2版本的接口兼容性方法 ==========

    def get_parameters(self):
        """获取当前参数 - 兼容原接口"""
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

    def set_parameters(self, params):
        """设置参数 - 兼容原接口"""
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
            for name, value in COLORMAP_OPTIONS:
                if value == params['colormap_type']:
                    self.colormap_combo.setCurrentText(name)
                    break
        if 'vmin' in params:
            self.vmin_spin.setValue(params['vmin'])
        if 'vmax' in params:
            self.vmax_spin.setValue(params['vmax'])

    def clear_data(self):
        """清空数据接口 - 兼容原接口"""
        if self._data_buffer is not None:
            self._data_buffer.clear()

        # 重置到空显示
        empty_data = np.zeros((10, 10))
        self.image_item.setImage(empty_data, levels=[self._vmin, self._vmax])
        self._current_frame_count = 0
        log.debug("TimeSpacePlotWidget data cleared")


def create_time_space_widget():
    """
    Create TimeSpace widget instance.

    Returns:
        TimeSpacePlotWidget: A time-space plot widget instance
    """
    log.info("Creating TimeSpacePlotWidget instance")
    return TimeSpacePlotWidget()


# Module exports
__all__ = ['TimeSpacePlotWidget', 'create_time_space_widget']