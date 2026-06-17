"""
`src/main_window.py` 是当前工程的业务编排中心，也是整个上位机最重要的模块。

这个文件不只是“画界面”。最新版本里，它同时承担参数采集与校验、设备初始化、采集线程启停、最新显示快照消费、频谱分析触发、Time-Space 控件协同、异步落盘、Tab3 TCP 发送、系统状态监控、自动恢复与本地参数持久化等职责，因此它本质上是桌面实时采集应用的总控层。

当前代码特别值得后续项目参考的点有三项：完整采集数据与 GUI 显示数据已经拆成两条链路；相位转弧度只发生在显示侧，落盘仍保存原始 `int32`；STOP、自动恢复和旧线程延迟信号的处理都围绕“不要误伤下一轮采集”来设计。
"""
import sys
import os
import json
import time
import numpy as np
import psutil  # For CPU and disk monitoring
import shutil  # For disk space monitoring
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox, QPushButton, QCheckBox,
    QRadioButton, QButtonGroup, QSpinBox, QDoubleSpinBox, QFileDialog,
    QMessageBox, QStatusBar, QSplitter, QFrame, QSizePolicy, QProgressBar,
    QTabWidget
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QPalette, QPixmap, QFontDatabase, QIcon
import pyqtgraph as pg

from config import (
    AllParams, BasicParams, UploadParams, PhaseDemodParams, DisplayParams, SaveParams,
    ClockSource, TriggerDirection, DataSource, DisplayMode,
    CHANNEL_NUM_OPTIONS, DATA_SOURCE_OPTIONS, DATA_RATE_OPTIONS, RATE2PHASE_OPTIONS,
    validate_point_num, calculate_fiber_length, calculate_data_rate_mbps,
    calculate_phase_point_num, calculate_cropped_point_count,
    OPTIMIZED_BUFFER_SIZES, MONITOR_UPDATE_INTERVALS
)
from pcie7821_api import PCIe7821API, PCIe7821Error
from acquisition_thread import AcquisitionThread, SimulatedAcquisitionThread
from data_saver import FrameBasedFileSaver
from spectrum_analyzer import RealTimeSpectrumAnalyzer
from time_space_plot import create_time_space_widget
from tcp_tab3 import TCPTab3Manager
from logger import get_logger
from plot_interaction import ZoomablePlotViewBox

# Module logger
log = get_logger("gui")

ACQ_STALL_TIMEOUT_S = 8.0
ACQ_RECOVERY_COOLDOWN_S = 20.0
APP_DISPLAY_VERSION = "eDAS-pt1g-gh-26.6.6"


def get_bundle_root() -> Path:
    """Return the runtime bundle root for source and frozen builds."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def get_logo_path() -> Path:
    """Return the preferred window/taskbar icon path."""
    bundle_root = get_bundle_root()
    primary = bundle_root / "resources" / "eDAS-LOGO.png"
    if primary.exists():
        return primary
    return bundle_root / "resources" / "logo.png"


def get_header_logo_path() -> Path:
    """Return the preferred page header logo path."""
    bundle_root = get_bundle_root()
    primary = bundle_root / "resources" / "logo.png"
    if primary.exists():
        return primary
    return bundle_root / "resources" / "eDAS-LOGO.png"


# ----- MAIN APPLICATION WINDOW -----

class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self, simulation_mode: bool = False):
        """
        Initialize main window.

        Args:
            simulation_mode: If True, use simulated data without hardware
        """
        super().__init__()
        log.info(f"MainWindow initializing (simulation_mode={simulation_mode})")
        self.simulation_mode = simulation_mode

        # Initialize components
        self.api: Optional[PCIe7821API] = None
        self.acq_thread: Optional[AcquisitionThread] = None
        self.data_saver: Optional[FrameBasedFileSaver] = None
        self.spectrum_analyzer = RealTimeSpectrumAnalyzer()
        self.time_space_widget = None
        self.tcp_tab3_manager = TCPTab3Manager()
        self._interactive_plot_widgets: Dict[str, pg.PlotWidget] = {}
        self._plot_zoom_locked: Dict[str, bool] = {}
        self._time_plot_axis_kind: Optional[str] = None
        self._time_plot_pending_auto_range = False
        self._time_plot_auto_range_frames_remaining = 0
        self._settings_path = self._get_settings_path()

        # Parameters
        self.params = AllParams()

        # Data storage for display
        self._phase_data_buffer = []
        self._raw_data_buffer = []
        self._current_monitor_data = None

        # Performance tracking
        self._last_data_time = 0
        self._data_count = 0
        self._gui_update_count = 0
        self._raw_data_count = 0  # Counter for raw data callbacks
        self._last_raw_display_time = 0  # Last raw display update timestamp
        self._last_storage_queue_log_time = 0.0
        self._last_acq_snapshot_log_time = 0.0
        self._recovery_in_progress = False
        self._last_recovery_time = 0.0
        self._full_data_count = 0
        self._tcp_settings_snapshot: Dict[str, Any] = {}

        # System monitoring
        self._last_system_update = 0
        self._cpu_percent = 0.0
        self._disk_free_gb = 0.0

        # Setup UI
        self.setWindowTitle(APP_DISPLAY_VERSION)
        icon_path = get_logo_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setMinimumSize(1400, 950)  # Slightly increased height to accommodate all content

        log.debug("Setting up UI...")
        self._setup_ui()
        self._setup_plots()
        self._connect_signals()
        self._connect_tcp_tab3_manager()
        self._load_local_params()
        self._sync_tcp_tab3_availability()
        self._update_phase_crop_controls()

        # Status timers
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(MONITOR_UPDATE_INTERVALS['buffer_status_ms'])

        # Consume only the newest display snapshot; acquisition never queues large arrays to Qt.
        self._display_timer = QTimer(self)
        self._display_timer.timeout.connect(self._drain_latest_display_data)
        self._display_timer.start(100)

        # System monitoring timer (slower update)
        self._system_timer = QTimer(self)
        self._system_timer.timeout.connect(self._update_system_status)
        self._system_timer.start(MONITOR_UPDATE_INTERVALS['system_status_s'] * 1000)

        # Initialize system monitoring
        self._last_system_update = 0
        self._cpu_percent = 0.0
        self._disk_free_gb = 0.0

        # Initialize psutil CPU monitoring (first call to establish baseline)
        try:
            psutil.cpu_percent(interval=None)  # Initialize CPU monitoring
        except Exception as e:
            log.warning(f"Failed to initialize CPU monitoring: {e}")

        # Initialize file estimates
        self._update_file_estimates()

        # Initialize device
        if not simulation_mode:
            self._init_device()
        else:
            self._update_device_status(True)

        log.info("MainWindow initialized")

    # ----- UI LAYOUT AND WIDGETS -----

    def _setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main vertical layout
        main_vertical_layout = QVBoxLayout(central_widget)
        main_vertical_layout.setContentsMargins(10, 10, 10, 10)

        # Header with logo and title
        header_widget = self._create_header()
        main_vertical_layout.addWidget(header_widget)

        # Content area (horizontal splitter)
        content_layout = QHBoxLayout()

        # Left panel - Parameters (two-column layout needs more width)
        left_panel = self._create_parameter_panel()
        left_panel.setMaximumWidth(380)
        left_panel.setMinimumWidth(340)

        # Right panel - Plots and controls
        right_panel = self._create_plot_panel()

        # Add to splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([360, 1040])

        main_vertical_layout.addWidget(splitter)

        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self._device_status_label = QLabel("Device: Disconnected")
        self._data_rate_label = QLabel("Data Rate: 0 MB/s")
        self._fiber_length_label = QLabel("Fiber Length: 0 m")
        self._point_num_label = QLabel("Point num: 0")  # Added point num display
        self._institute_label = QLabel("中国科学院半导体研究所")
        self._institute_label.setFont(QFont("等线", 10))

        # Add separators between status items
        self.statusBar.addWidget(self._device_status_label)
        self.statusBar.addPermanentWidget(QLabel("  |  "))  # Separator
        self.statusBar.addWidget(self._data_rate_label)
        self.statusBar.addPermanentWidget(QLabel("  |  "))  # Separator
        self.statusBar.addWidget(self._fiber_length_label)
        self.statusBar.addPermanentWidget(QLabel("  |  "))  # Separator
        self.statusBar.addWidget(self._point_num_label)
        self.statusBar.addPermanentWidget(self._institute_label)

    def _create_header(self) -> QWidget:
        """Create header with logo and title"""
        header = QFrame()
        header.setFrameStyle(QFrame.StyledPanel)
        header.setFixedHeight(50)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 3, 10, 3)

        # Logo
        logo_label = QLabel()
        logo_path = get_header_logo_path()
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            # Scale logo to fit header height
            scaled_pixmap = pixmap.scaledToHeight(40, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        else:
            logo_label.setText("[LOGO]")
            log.warning(f"Logo file not found: {logo_path}")

        layout.addWidget(logo_label)

        # Title - Arial bold 28pt
        title_label = QLabel("Enhanced Distributed Acoustic Sensing (eDAS)")
        title_font = QFont("Arial", 28, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(title_label, 1)  # stretch factor 1 to center
        layout.addStretch()

        return header

    def _create_parameter_panel(self) -> QWidget:
        """Create the parameter configuration panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)
        layout.setContentsMargins(5, 5, 5, 5)

        # Minimum height for input widgets
        INPUT_MIN_HEIGHT = 22
        INPUT_MAX_WIDTH = 80

        # Apply stylesheet for fonts - Times New Roman for English text, SimHei for Chinese
        panel.setStyleSheet("""
            QGroupBox {
                font-family: 'Arial';
                font-size: 12px;
                font-weight: bold;
            }
            QLabel {
                font-family: 'Times New Roman', 'SimHei';
                font-size: 11px;
            }
            QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {
                font-family: 'Times New Roman';
                font-size: 11px;
                max-height: 22px;
            }
            QComboBox {
                max-width: 85px;
            }
            QRadioButton, QCheckBox {
                font-family: 'Times New Roman', 'SimHei';
                font-size: 10px;
            }
            QPushButton {
                font-family: 'Times New Roman', 'SimHei';
                font-size: 12px;
            }
        """)

        # Basic Parameters Group - Two columns layout
        basic_group = QGroupBox("Basic Parameters")
        basic_layout = QGridLayout(basic_group)
        basic_layout.setSpacing(4)
        basic_layout.setContentsMargins(8, 12, 8, 8)

        # Row 0: Clock Source (spans 2 cols) | Trigger Dir (spans 2 cols)
        basic_layout.addWidget(QLabel("Clock:"), 0, 0)
        self.clk_internal_radio = QRadioButton("Int")
        self.clk_external_radio = QRadioButton("Ext")
        self.clk_internal_radio.setChecked(True)
        clk_group = QButtonGroup(self)
        clk_group.addButton(self.clk_internal_radio, 0)
        clk_group.addButton(self.clk_external_radio, 1)
        clk_layout = QHBoxLayout()
        clk_layout.setSpacing(2)
        clk_layout.addWidget(self.clk_internal_radio)
        clk_layout.addWidget(self.clk_external_radio)
        basic_layout.addLayout(clk_layout, 0, 1)

        basic_layout.addWidget(QLabel("Trig:"), 0, 2)
        self.trig_in_radio = QRadioButton("In")
        self.trig_out_radio = QRadioButton("Out")
        self.trig_out_radio.setChecked(True)
        trig_group = QButtonGroup(self)
        trig_group.addButton(self.trig_in_radio, 0)
        trig_group.addButton(self.trig_out_radio, 1)
        trig_layout = QHBoxLayout()
        trig_layout.setSpacing(2)
        trig_layout.addWidget(self.trig_in_radio)
        trig_layout.addWidget(self.trig_out_radio)
        basic_layout.addLayout(trig_layout, 0, 3)

        # Row 1: Scan Rate | Pulse Width
        basic_layout.addWidget(QLabel("Scan(Hz):"), 1, 0)
        self.scan_rate_spin = QSpinBox()
        self.scan_rate_spin.setRange(1, 1000000)
        self.scan_rate_spin.setValue(2000)
        self.scan_rate_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.scan_rate_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        basic_layout.addWidget(self.scan_rate_spin, 1, 1)

        basic_layout.addWidget(QLabel("Pulse(ns):"), 1, 2)
        self.pulse_width_spin = QSpinBox()
        self.pulse_width_spin.setRange(10, 1000000)
        self.pulse_width_spin.setValue(100)
        self.pulse_width_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.pulse_width_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        basic_layout.addWidget(self.pulse_width_spin, 1, 3)

        # Row 2: Points/Scan | Bypass
        basic_layout.addWidget(QLabel("Points:"), 2, 0)
        self.point_num_spin = QSpinBox()
        self.point_num_spin.setRange(512, 10000000)
        self.point_num_spin.setValue(20480)
        self.point_num_spin.setSingleStep(512)
        self.point_num_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.point_num_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        basic_layout.addWidget(self.point_num_spin, 2, 1)

        basic_layout.addWidget(QLabel("Bypass:"), 2, 2)
        self.bypass_spin = QSpinBox()
        self.bypass_spin.setRange(0, 10000000)
        self.bypass_spin.setValue(60)
        self.bypass_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.bypass_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        basic_layout.addWidget(self.bypass_spin, 2, 3)

        # Row 3: Center Freq (spans full width for clarity)
        basic_layout.addWidget(QLabel("CenterFreq(MHz):"), 3, 0, 1, 2)
        self.center_freq_spin = QSpinBox()
        self.center_freq_spin.setRange(1, 100000)
        self.center_freq_spin.setValue(200)
        self.center_freq_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.center_freq_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        basic_layout.addWidget(self.center_freq_spin, 3, 2, 1, 2)

        layout.addWidget(basic_group)

        # Upload Parameters Group - Two columns layout
        upload_group = QGroupBox("Upload Parameters")
        upload_layout = QGridLayout(upload_group)
        upload_layout.setSpacing(4)
        upload_layout.setContentsMargins(8, 12, 8, 8)

        # Row 0: Channels | Data Source
        upload_layout.addWidget(QLabel("Channels:"), 0, 0)
        self.channel_combo = QComboBox()
        for label, value in CHANNEL_NUM_OPTIONS:
            self.channel_combo.addItem(label, value)
        self.channel_combo.setMinimumHeight(INPUT_MIN_HEIGHT)
        upload_layout.addWidget(self.channel_combo, 0, 1)

        upload_layout.addWidget(QLabel("Source:"), 0, 2)
        self.data_source_combo = QComboBox()
        for label, value in DATA_SOURCE_OPTIONS:
            self.data_source_combo.addItem(label, value)
        self.data_source_combo.setCurrentIndex(3)  # Default to Phase
        self.data_source_combo.setMinimumHeight(INPUT_MIN_HEIGHT)
        upload_layout.addWidget(self.data_source_combo, 0, 3)

        # Row 1: Data Rate
        upload_layout.addWidget(QLabel("DataRate:"), 1, 0)
        self.data_rate_combo = QComboBox()
        for label, value in DATA_RATE_OPTIONS:
            self.data_rate_combo.addItem(label, value)
        self.data_rate_combo.setMinimumHeight(INPUT_MIN_HEIGHT)
        upload_layout.addWidget(self.data_rate_combo, 1, 1)

        layout.addWidget(upload_group)

        # Phase Demodulation Parameters Group - Two columns layout
        phase_group = QGroupBox("Phase Demod Parameters")
        phase_layout = QGridLayout(phase_group)
        phase_layout.setSpacing(4)
        phase_layout.setContentsMargins(8, 12, 8, 8)

        # Row 0: Rate2Phase | Space Avg
        phase_layout.addWidget(QLabel("Rate2Phase:"), 0, 0)
        self.rate2phase_combo = QComboBox()
        for label, value in RATE2PHASE_OPTIONS:
            self.rate2phase_combo.addItem(label, value)
        self.rate2phase_combo.setCurrentIndex(0)  # Default 250M (index 0)
        self.rate2phase_combo.setMinimumHeight(INPUT_MIN_HEIGHT)
        phase_layout.addWidget(self.rate2phase_combo, 0, 1)

        phase_layout.addWidget(QLabel("SpaceAvg:"), 0, 2)
        self.space_avg_spin = QSpinBox()
        self.space_avg_spin.setRange(1, 64)
        self.space_avg_spin.setValue(25)
        self.space_avg_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.space_avg_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        phase_layout.addWidget(self.space_avg_spin, 0, 3)

        # Row 1: Merge Points | Diff Order
        phase_layout.addWidget(QLabel("Merge:"), 1, 0)
        self.merge_points_spin = QSpinBox()
        self.merge_points_spin.setRange(1, 64)
        self.merge_points_spin.setValue(25)
        self.merge_points_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.merge_points_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        phase_layout.addWidget(self.merge_points_spin, 1, 1)

        phase_layout.addWidget(QLabel("DiffOrder:"), 1, 2)
        self.diff_order_spin = QSpinBox()
        self.diff_order_spin.setRange(0, 4)
        self.diff_order_spin.setValue(1)
        self.diff_order_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.diff_order_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        phase_layout.addWidget(self.diff_order_spin, 1, 3)

        # Row 2: Detrend BW | Polarization
        phase_layout.addWidget(QLabel("Detrend(Hz):"), 2, 0)
        self.detrend_bw_spin = QDoubleSpinBox()
        self.detrend_bw_spin.setRange(0.0, 1000000.0)
        self.detrend_bw_spin.setValue(10.0)  # 默认值为 10 Hz
        self.detrend_bw_spin.setSingleStep(0.1)
        self.detrend_bw_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.detrend_bw_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        phase_layout.addWidget(self.detrend_bw_spin, 2, 1)

        self.polar_div_check = QCheckBox("PolarDiv")
        self.polar_div_check.setChecked(True)  # 默认启用偏振分集
        phase_layout.addWidget(self.polar_div_check, 2, 2, 1, 2)

        phase_layout.addWidget(QLabel("CropStart:"), 3, 0)
        self.crop_distance_start_spin = QSpinBox()
        self.crop_distance_start_spin.setRange(0, 10000000)
        self.crop_distance_start_spin.setValue(0)
        self.crop_distance_start_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.crop_distance_start_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        self.crop_distance_start_spin.setToolTip("Single-channel PHASE only. 0 with CropEnd=0 keeps the full range.")
        phase_layout.addWidget(self.crop_distance_start_spin, 3, 1)

        phase_layout.addWidget(QLabel("CropEnd:"), 3, 2)
        self.crop_distance_end_spin = QSpinBox()
        self.crop_distance_end_spin.setRange(0, 10000000)
        self.crop_distance_end_spin.setValue(0)
        self.crop_distance_end_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.crop_distance_end_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        self.crop_distance_end_spin.setToolTip("Single-channel PHASE only. End is exclusive; values above total points are clamped.")
        phase_layout.addWidget(self.crop_distance_end_spin, 3, 3)

        layout.addWidget(phase_group)

        # Display Control Group - Two columns layout
        display_group = QGroupBox("Display Control")
        display_layout = QGridLayout(display_group)
        display_layout.setSpacing(4)
        display_layout.setContentsMargins(8, 12, 8, 8)

        # Row 0: Mode | Region Index
        display_layout.addWidget(QLabel("Mode:"), 0, 0)
        self.mode_time_radio = QRadioButton("Time")
        self.mode_space_radio = QRadioButton("Space")
        # Time-space moved to Tab2; Tab1 keeps Time and Space modes.
        self.mode_time_radio.setChecked(True)
        mode_group = QButtonGroup(self)
        mode_group.addButton(self.mode_time_radio, 0)
        mode_group.addButton(self.mode_space_radio, 1)
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(2)
        mode_layout.addWidget(self.mode_time_radio)
        mode_layout.addWidget(self.mode_space_radio)
        display_layout.addLayout(mode_layout, 0, 1)

        display_layout.addWidget(QLabel("Region:"), 0, 2)
        self.region_index_spin = QSpinBox()
        self.region_index_spin.setRange(0, 10000000)
        self.region_index_spin.setValue(0)
        self.region_index_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.region_index_spin.setMaximumWidth(60)  # 缩小 Region 输入框宽度
        display_layout.addWidget(self.region_index_spin, 0, 3)

        # Row 1: FrameLoad | FramePlot
        display_layout.addWidget(QLabel("FrameLoad:"), 1, 0)
        self.frame_load_num_spin = QSpinBox()
        self.frame_load_num_spin.setRange(0, 1000000)
        self.frame_load_num_spin.setValue(1024)
        self.frame_load_num_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.frame_load_num_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        display_layout.addWidget(self.frame_load_num_spin, 1, 1)

        display_layout.addWidget(QLabel("FramePlot:"), 1, 2)
        self.frame_plot_num_spin = QSpinBox()
        self.frame_plot_num_spin.setRange(0, 1000000)
        self.frame_plot_num_spin.setValue(1024)
        self.frame_plot_num_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.frame_plot_num_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        display_layout.addWidget(self.frame_plot_num_spin, 1, 3)

        # Row 2: waveform / monitor display switches
        self.waveform_enable_check = QCheckBox("Waveform")
        self.waveform_enable_check.setToolTip("Enable time/space waveform plot updates")
        self.waveform_enable_check.setChecked(False)
        display_layout.addWidget(self.waveform_enable_check, 2, 0, 1, 2)

        self.monitor_enable_check = QCheckBox("Monitor")
        self.monitor_enable_check.setToolTip("Enable monitor plot updates")
        self.monitor_enable_check.setChecked(False)
        display_layout.addWidget(self.monitor_enable_check, 2, 2, 1, 2)

        # Row 3: spectrum / analysis / rad
        self.spectrum_enable_check = QCheckBox("Spectrum")
        self.spectrum_enable_check.setChecked(True)
        display_layout.addWidget(self.spectrum_enable_check, 3, 0)

        # Analysis type info label (shows Power/PSD based on data type)
        self.analysis_type_label = QLabel("Power")
        self.analysis_type_label.setStyleSheet("QLabel { color: blue; font-weight: bold; }")
        self.analysis_type_label.setToolTip("Analysis type: Raw data -> Power Spectrum, Phase data -> PSD")
        display_layout.addWidget(self.analysis_type_label, 3, 1)

        self.rad_check = QCheckBox("rad")
        self.rad_check.setToolTip("Convert phase data to radians for display only: display = data / 32767 * pi\n(Storage always saves original int32 data)")
        self.rad_check.setChecked(True)  # Default checked
        display_layout.addWidget(self.rad_check, 3, 2, 1, 2)

        layout.addWidget(display_group)

        # Save Control Group
        save_group = QGroupBox("Data Save")
        save_layout = QGridLayout(save_group)
        save_layout.setSpacing(4)
        save_layout.setContentsMargins(8, 12, 8, 8)

        # Row 0: Enable | Path
        self.save_enable_check = QCheckBox("Enable")
        save_layout.addWidget(self.save_enable_check, 0, 0)

        save_layout.addWidget(QLabel("Path:"), 0, 1)
        path_layout = QHBoxLayout()
        path_layout.setSpacing(2)
        self.save_path_edit = QLineEdit(self.params.save.path)  # Use default path from config
        self.save_path_edit.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.browse_btn = QPushButton("...")
        self.browse_btn.setMaximumWidth(25)
        self.browse_btn.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.browse_btn.clicked.connect(self._browse_save_path)
        path_layout.addWidget(self.save_path_edit)
        path_layout.addWidget(self.browse_btn)
        save_layout.addLayout(path_layout, 0, 2, 1, 2)

        # Row 1: Frames per File | File Size Estimate
        save_layout.addWidget(QLabel("Frames/File:"), 1, 0)
        self.frames_per_file_spin = QSpinBox()
        self.frames_per_file_spin.setRange(1, 100000)
        self.frames_per_file_spin.setValue(self.params.save.frames_per_file)
        self.frames_per_file_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.frames_per_file_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        self.frames_per_file_spin.valueChanged.connect(self._update_file_estimates)
        save_layout.addWidget(self.frames_per_file_spin, 1, 1)

        save_layout.addWidget(QLabel("Est. Size:"), 1, 2)
        self.file_size_label = QLabel("~26MB/file")
        self.file_size_label.setStyleSheet("font-weight: normal; color: #666666;")
        save_layout.addWidget(self.file_size_label, 1, 3)

        layout.addWidget(save_group)

        # Control Buttons
        control_layout = QHBoxLayout()

        # START button - green when ready, gray when running
        self.start_btn = QPushButton("START")
        self.start_btn.setMinimumHeight(38)
        self._set_start_btn_ready()

        # STOP button - gray when disabled, red when enabled
        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setMinimumHeight(38)
        self._set_stop_btn_disabled()

        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        layout.addLayout(control_layout)

        layout.addStretch()

        return panel

    def _set_start_btn_ready(self):
        """Set START button to ready state (green)"""
        self.start_btn.setEnabled(True)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)

    def _set_start_btn_running(self):
        """Set START button to running state (gray, disabled)"""
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #9E9E9E;
                color: #666666;
                font-weight: bold;
                font-size: 14px;
                border: none;
                border-radius: 5px;
            }
        """)

    def _set_stop_btn_disabled(self):
        """Set STOP button to disabled state (gray)"""
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #BDBDBD;
                color: #757575;
                font-weight: bold;
                font-size: 14px;
                border: none;
                border-radius: 5px;
            }
        """)

    def _set_stop_btn_enabled(self):
        """Set STOP button to enabled state (red)"""
        self.stop_btn.setEnabled(True)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c41508;
            }
        """)

    def _create_plot_panel(self) -> QWidget:
        """Create the plot display panel with tab widget"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # Configure pyqtgraph
        pg.setConfigOptions(antialias=True)

        # Create tab widget
        self.plot_tabs = QTabWidget()
        self.plot_tabs.setTabPosition(QTabWidget.North)

        # Set tab titles font style
        self.plot_tabs.setStyleSheet("""
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                font-family: 'Arial';
                font-size: 12px;
                font-weight: normal;
                padding: 6px 15px;
                margin: 1px;
                min-width: 90px;
            }
            QTabBar::tab:selected {
                font-weight: bold;
            }
        """)

        # Tab 1: Traditional plots (Time/Space + FFT + Monitor)
        self._create_traditional_plots_tab()

        # Tab 2: Time-Space plot
        self._create_time_space_tab()

        # Tab 3: TCP communication
        self._create_tcp_comm_tab()

        layout.addWidget(self.plot_tabs)

        # System Monitoring Panel - Single row layout
        monitor_frame = QFrame()
        monitor_frame.setFrameStyle(QFrame.StyledPanel)
        monitor_frame.setMaximumHeight(40)  # Reduced height for single row
        monitor_layout = QHBoxLayout(monitor_frame)  # Changed to horizontal layout
        monitor_layout.setSpacing(15)  # Add spacing between sections

        # Buffer Status section
        monitor_layout.addWidget(QLabel("Status:"))

        # Hardware Buffer
        self.hw_buffer_label = QLabel("HW: 0/50")
        self.hw_buffer_bar = QProgressBar()
        self.hw_buffer_bar.setMaximumWidth(80)  # Reduced width
        self.hw_buffer_bar.setMaximumHeight(16)  # Reduced height
        monitor_layout.addWidget(self.hw_buffer_label)
        monitor_layout.addWidget(self.hw_buffer_bar)

        # Signal Queue
        self.signal_queue_label = QLabel("SIG: 0/20")
        self.signal_queue_bar = QProgressBar()
        self.signal_queue_bar.setMaximumWidth(80)
        self.signal_queue_bar.setMaximumHeight(16)
        monitor_layout.addWidget(self.signal_queue_label)
        monitor_layout.addWidget(self.signal_queue_bar)

        # Storage Queue
        self.storage_queue_label = QLabel("STO: 0/200")
        self.storage_queue_bar = QProgressBar()
        self.storage_queue_bar.setMaximumWidth(80)
        self.storage_queue_bar.setMaximumHeight(16)
        monitor_layout.addWidget(self.storage_queue_label)
        monitor_layout.addWidget(self.storage_queue_bar)

        # Add separator
        separator = QLabel("|")
        separator.setStyleSheet("color: gray;")
        monitor_layout.addWidget(separator)

        # System Status section
        self.cpu_label = QLabel("CPU: 0%")
        self.disk_label = QLabel("Disk: 0GB free")
        self.polling_label = QLabel("Poll: 1ms")
        monitor_layout.addWidget(self.cpu_label)
        monitor_layout.addWidget(self.disk_label)
        monitor_layout.addWidget(self.polling_label)

        # Add separator
        separator2 = QLabel("|")
        separator2.setStyleSheet("color: gray;")
        monitor_layout.addWidget(separator2)

        # Additional status section
        self.buffer_label = QLabel("Buffer: 0 MB")
        self.frames_label = QLabel("Frames: 0")
        self.save_status_label = QLabel("Save: Off")
        monitor_layout.addWidget(self.buffer_label)
        monitor_layout.addWidget(self.frames_label)
        monitor_layout.addWidget(self.save_status_label)

        monitor_layout.addStretch()  # Push everything to the left

        layout.addWidget(monitor_frame)

        return panel

    def _create_traditional_plots_tab(self):
        """Create the traditional plots tab with existing functionality"""
        tab1_widget = QWidget()
        tab1_layout = QVBoxLayout(tab1_widget)
        tab1_layout.setSpacing(10)
        tab1_layout.setContentsMargins(5, 5, 5, 10)

        # Create plots with custom titles and styling
        self.plot_widget_1 = self._create_interactive_plot_widget("plot1")
        self.plot_widget_2 = self._create_interactive_plot_widget("plot2")
        self.plot_widget_3 = self._create_interactive_plot_widget("plot3")

        # Configure plot styles - white background and custom title styling
        plot_titles = ["Time Domain Data", "FFT Spectrum", "Monitor (Fiber End Detection)"]
        self.plot_widgets = [self.plot_widget_1, self.plot_widget_2, self.plot_widget_3]

        for i, pw in enumerate(self.plot_widgets):
            pw.setBackground('w')  # White background

            # Set custom title with New Roman font and dark blue color
            title_label = pw.setLabel('top', plot_titles[i])

            # Force dark blue color for title - multiple methods to ensure it works
            title_item = pw.getPlotItem().titleLabel.item
            title_item.setFont(QFont("Times New Roman", 9))

            # Method 1: Set default text color
            title_item.setDefaultTextColor(QColor(0, 0, 139))  # Dark blue

            # Method 2: Set HTML color (backup method)
            blue_title = f'<span style="color: rgb(0,0,139); font-family: Times New Roman; font-size: 9pt">{plot_titles[i]}</span>'
            pw.setLabel('top', blue_title)

            # Method 3: Force color via stylesheet if available
            try:
                title_item.document().setDefaultStyleSheet("color: rgb(0,0,139);")
            except:
                pass

            # Configure axes - keep top axis for title but hide its ticks
            x_axis = pw.getAxis('bottom')
            y_axis = pw.getAxis('left')
            top_axis = pw.getAxis('top')
            right_axis = pw.getAxis('right')

            # Show top axis (for title) but hide its ticks and values
            pw.showAxis('top', show=True)   # Keep for title
            pw.showAxis('right', show=False) # Hide completely

            # Hide top axis ticks and values but keep the title
            top_axis.setStyle(showValues=False, tickLength=0)

            # Hide right axis completely
            # (already done with showAxis above)

            # Grid and tick configuration with smaller fonts
            pw.showGrid(x=True, y=True, alpha=0.6)

            # Set fonts for axes - increase tick font size by 2 units
            axis_font = QFont("Times New Roman", 8)      # 轴标签保持 8 pt
            tick_font = QFont("Times New Roman", 8)      # 刻度值使用 8 pt

            # Configure tick style with reduced spacing
            x_axis.setStyle(showValues=True, tickLength=4, tickTextOffset=6)  # Reduced offset
            y_axis.setStyle(showValues=True, tickLength=4, tickTextOffset=4)  # Reduced offset

            # Set tick fonts (smaller)
            x_axis.setTickFont(tick_font)
            y_axis.setTickFont(tick_font)

            # Set axis colors
            x_axis.setPen('k')
            y_axis.setPen('k')
            x_axis.setTextPen('k')
            y_axis.setTextPen('k')

        # Set specific labels for each plot with consistent smaller fonts
        # Plot 1: Time Domain
        self._set_time_plot_axis('Distance (m)', 'distance')
        self.plot_widget_1.setLabel('left', 'Amp.',
                                   color='k', **{'font-family': 'Times New Roman', 'font-size': '8pt'})

        # Plot 2: FFT Spectrum (consistent font size)
        self.plot_widget_2.setLabel('bottom', 'Frequency (Hz)',
                                   color='k', **{'font-family': 'Times New Roman', 'font-size': '8pt'})
        self.plot_widget_2.setLabel('left', 'Amp. (dB)',
                                   color='k', **{'font-family': 'Times New Roman', 'font-size': '8pt'})

        # Plot 3: Monitor (consistent font size)
        self.plot_widget_3.setLabel('bottom', 'Point Index',
                                   color='k', **{'font-family': 'Times New Roman', 'font-size': '8pt'})
        self.plot_widget_3.setLabel('left', 'Amp.',
                                   color='k', **{'font-family': 'Times New Roman', 'font-size': '8pt'})

        # Plot curves setup - labels already set above
        # Plot 1 - Time Domain
        self.plot_curve_1 = []

        # Plot 2 - Spectrum
        # Linear scale for both axes (dB values already in log scale)
        self.plot_widget_2.setLogMode(x=False, y=False)
        self.spectrum_curve = self.plot_widget_2.plot(pen=pg.mkPen('#9467bd', width=1.5))  # Purple

        # Plot 3 - Monitor
        self.monitor_curves = []

        # Add plots to layout with balanced heights and proper scaling
        # Set both minimum and maximum heights to prevent over-stretching in fullscreen
        self.plot_widget_1.setMinimumHeight(180)  # Time Domain plot - increased
        self.plot_widget_1.setMaximumHeight(210)  # Controlled height range
        self.plot_widget_1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Adjust plot heights - increase since text is smaller
        self.plot_widget_1.setMinimumHeight(200)  # Time Domain - increased
        self.plot_widget_1.setMaximumHeight(250)
        self.plot_widget_1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.plot_widget_2.setMinimumHeight(200)  # FFT Spectrum - increased
        self.plot_widget_2.setMaximumHeight(250)
        self.plot_widget_2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.plot_widget_3.setMinimumHeight(150)  # Monitor plot - increased
        self.plot_widget_3.setMaximumHeight(180)
        self.plot_widget_3.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Reduce spacing between plots
        tab1_layout.setSpacing(5)  # Reduced from default spacing
        tab1_layout.addWidget(self.plot_widget_1)
        tab1_layout.addWidget(self.plot_widget_2)
        tab1_layout.addWidget(self.plot_widget_3)

        # Add a flexible spacer that will absorb extra space in fullscreen mode
        tab1_layout.addStretch(1)

        self.plot_tabs.addTab(tab1_widget, "Time Plot")

    def _create_time_space_tab(self):
        """Create the time-space plot tab"""
        tab2_widget = QWidget()
        tab2_layout = QVBoxLayout(tab2_widget)
        tab2_layout.setSpacing(5)
        tab2_layout.setContentsMargins(5, 5, 5, 5)

        # Create time-space plot widget using intelligent selector
        self.time_space_widget = create_time_space_widget()
        tab2_layout.addWidget(self.time_space_widget)

        self.plot_tabs.addTab(tab2_widget, "Time-Space Plot")

        # Connect signals after widget creation
        self._connect_time_space_signals()

    def _create_tcp_comm_tab(self):
        """Create the communication-only Tab3."""
        tab3_widget = QWidget()
        tab3_layout = QVBoxLayout(tab3_widget)
        tab3_layout.setSpacing(10)
        tab3_layout.setContentsMargins(10, 10, 10, 10)

        settings_group = QGroupBox("TCP Communication")
        settings_layout = QGridLayout(settings_group)
        settings_layout.setContentsMargins(10, 12, 10, 10)
        settings_layout.setHorizontalSpacing(10)
        settings_layout.setVerticalSpacing(6)

        self.tab3_comm_enable_check = QCheckBox("Enable communication")
        self.tab3_comm_enable_check.setChecked(False)
        settings_layout.addWidget(self.tab3_comm_enable_check, 0, 0, 1, 2)

        settings_layout.addWidget(QLabel("Server IP:"), 1, 0)
        self.tab3_server_ip_edit = QLineEdit("169.255.1.2")
        settings_layout.addWidget(self.tab3_server_ip_edit, 1, 1)

        settings_layout.addWidget(QLabel("Server Port:"), 2, 0)
        self.tab3_server_port_spin = QSpinBox()
        self.tab3_server_port_spin.setRange(1, 65535)
        self.tab3_server_port_spin.setValue(3678)
        settings_layout.addWidget(self.tab3_server_port_spin, 2, 1)

        settings_layout.addWidget(QLabel("Channel Start:"), 3, 0)
        self.tab3_channel_start_spin = QSpinBox()
        self.tab3_channel_start_spin.setRange(0, 1000000)
        self.tab3_channel_start_spin.setValue(50)
        settings_layout.addWidget(self.tab3_channel_start_spin, 3, 1)

        settings_layout.addWidget(QLabel("Channel End:"), 4, 0)
        self.tab3_channel_end_spin = QSpinBox()
        self.tab3_channel_end_spin.setRange(0, 1000000)
        self.tab3_channel_end_spin.setValue(100)
        settings_layout.addWidget(self.tab3_channel_end_spin, 4, 1)

        settings_layout.addWidget(QLabel("Time Downsample:"), 5, 0)
        self.tab3_time_downsample_spin = QSpinBox()
        self.tab3_time_downsample_spin.setRange(1, 100000)
        self.tab3_time_downsample_spin.setValue(1)
        settings_layout.addWidget(self.tab3_time_downsample_spin, 5, 1)

        settings_layout.addWidget(QLabel("Space Downsample:"), 6, 0)
        self.tab3_space_downsample_spin = QSpinBox()
        self.tab3_space_downsample_spin.setRange(1, 100000)
        self.tab3_space_downsample_spin.setValue(1)
        settings_layout.addWidget(self.tab3_space_downsample_spin, 6, 1)

        tab3_layout.addWidget(settings_group)

        status_group = QGroupBox("Communication Status")
        status_layout = QGridLayout(status_group)
        status_layout.setContentsMargins(10, 12, 10, 10)
        status_layout.setHorizontalSpacing(10)
        status_layout.setVerticalSpacing(6)

        self.tab3_availability_label = QLabel("Waiting for acquisition parameters")
        self.tab3_comm_state_label = QLabel("Idle")
        self.tab3_comm_state_label.setStyleSheet("color: #555; font-weight: bold;")
        self.tab3_comm_message_label = QLabel("-")
        self.tab3_comm_message_label.setWordWrap(True)
        self.tab3_comm_last_error_label = QLabel("-")
        self.tab3_comm_last_error_label.setWordWrap(True)
        self.tab3_acquired_packets_label = QLabel("0")
        self.tab3_queued_packets_label = QLabel("0")
        self.tab3_sent_packets_label = QLabel("0")
        self.tab3_dropped_packets_label = QLabel("0")
        self.tab3_last_comm_count_label = QLabel("-")
        self.tab3_bytes_sent_label = QLabel("0")
        self.tab3_comm_channel_count_label = QLabel("-")
        self.tab3_comm_sample_rate_label = QLabel("-")
        self.tab3_comm_duration_label = QLabel("-")
        self.tab3_comm_data_bytes_label = QLabel("-")

        status_layout.addWidget(QLabel("Availability:"), 0, 0)
        status_layout.addWidget(self.tab3_availability_label, 0, 1, 1, 3)
        status_layout.addWidget(QLabel("State:"), 1, 0)
        status_layout.addWidget(self.tab3_comm_state_label, 1, 1)
        status_layout.addWidget(QLabel("Message:"), 2, 0)
        status_layout.addWidget(self.tab3_comm_message_label, 2, 1, 1, 3)
        status_layout.addWidget(QLabel("Last Error:"), 3, 0)
        status_layout.addWidget(self.tab3_comm_last_error_label, 3, 1, 1, 3)
        status_layout.addWidget(QLabel("Acquired:"), 4, 0)
        status_layout.addWidget(self.tab3_acquired_packets_label, 4, 1)
        status_layout.addWidget(QLabel("Queued:"), 4, 2)
        status_layout.addWidget(self.tab3_queued_packets_label, 4, 3)
        status_layout.addWidget(QLabel("Sent:"), 5, 0)
        status_layout.addWidget(self.tab3_sent_packets_label, 5, 1)
        status_layout.addWidget(QLabel("Dropped:"), 5, 2)
        status_layout.addWidget(self.tab3_dropped_packets_label, 5, 3)
        status_layout.addWidget(QLabel("Last Comm:"), 6, 0)
        status_layout.addWidget(self.tab3_last_comm_count_label, 6, 1)
        status_layout.addWidget(QLabel("Bytes Sent:"), 6, 2)
        status_layout.addWidget(self.tab3_bytes_sent_label, 6, 3)
        status_layout.addWidget(QLabel("Channels:"), 7, 0)
        status_layout.addWidget(self.tab3_comm_channel_count_label, 7, 1)
        status_layout.addWidget(QLabel("Sample Rate:"), 7, 2)
        status_layout.addWidget(self.tab3_comm_sample_rate_label, 7, 3)
        status_layout.addWidget(QLabel("Packet Duration:"), 8, 0)
        status_layout.addWidget(self.tab3_comm_duration_label, 8, 1)
        status_layout.addWidget(QLabel("Data Bytes:"), 8, 2)
        status_layout.addWidget(self.tab3_comm_data_bytes_label, 8, 3)

        tab3_layout.addWidget(status_group)
        tab3_layout.addStretch(1)

        self.plot_tabs.addTab(tab3_widget, "TCP Comm")

    def _create_interactive_plot_widget(self, plot_key: str) -> pg.PlotWidget:
        """Create a PlotWidget with unified rectangle zoom behavior."""
        view_box = ZoomablePlotViewBox()
        plot_widget = pg.PlotWidget(viewBox=view_box)
        self._interactive_plot_widgets[plot_key] = plot_widget
        self._plot_zoom_locked[plot_key] = False
        view_box.sigManualRangeChange.connect(
            lambda key=plot_key: self._on_plot_manual_range_change(key)
        )
        view_box.sigViewAllRequested.connect(
            lambda key=plot_key: self._restore_plot_auto_range(key)
        )
        return plot_widget

    def _configure_realtime_curve(self, curve: pg.PlotDataItem):
        """Use pyqtgraph fast-path settings for large realtime curves."""
        curve.setClipToView(True)
        curve.setDownsampling(auto=True, method="peak")
        curve.setSkipFiniteCheck(True)

    def _configure_time_plot_curves_for_axis(self, axis_kind: str) -> None:
        """Tune Tab1 curve rendering for distance or time-axis data density."""
        if not hasattr(self, "plot_curve_1"):
            return
        for curve in self.plot_curve_1:
            try:
                if axis_kind == "time":
                    curve.setClipToView(False)
                    curve.setDownsampling(auto=False)
                    curve.setSkipFiniteCheck(True)
                else:
                    self._configure_realtime_curve(curve)
            except Exception:
                pass

    def _on_plot_manual_range_change(self, plot_key: str):
        plot_widget = self._interactive_plot_widgets.get(plot_key)
        if plot_widget is None:
            return
        self._plot_zoom_locked[plot_key] = True
        plot_widget.getViewBox().disableAutoRange()

    def _restore_plot_auto_range(self, plot_key: str):
        plot_widget = self._interactive_plot_widgets.get(plot_key)
        if plot_widget is None:
            return
        self._plot_zoom_locked[plot_key] = False
        view_box = plot_widget.getViewBox()
        view_box.enableAutoRange(x=True, y=True)
        view_box.autoRange(padding=0.0)

    def _curve_data_range(self, curves) -> Optional[tuple[float, float, float, float]]:
        """Return finite x/y bounds for the currently populated curves."""
        x_min = y_min = np.inf
        x_max = y_max = -np.inf
        has_data = False

        for curve in curves:
            x_data, y_data = curve.getData()
            if x_data is None or y_data is None:
                continue
            x_arr = np.asarray(x_data)
            y_arr = np.asarray(y_data)
            if x_arr.size == 0 or y_arr.size == 0:
                continue

            count = min(x_arr.size, y_arr.size)
            x_arr = x_arr[:count]
            y_arr = y_arr[:count]
            finite_mask = np.isfinite(x_arr) & np.isfinite(y_arr)
            if not finite_mask.any():
                continue

            finite_x = x_arr[finite_mask]
            finite_y = y_arr[finite_mask]
            x_min = min(x_min, float(finite_x.min()))
            x_max = max(x_max, float(finite_x.max()))
            y_min = min(y_min, float(finite_y.min()))
            y_max = max(y_max, float(finite_y.max()))
            has_data = True

        if not has_data:
            return None

        if x_min == x_max:
            pad = max(abs(x_min) * 0.01, 1.0)
            x_min -= pad
            x_max += pad
        if y_min == y_max:
            pad = max(abs(y_min) * 0.01, 1.0)
            y_min -= pad
            y_max += pad

        return x_min, x_max, y_min, y_max

    def _force_plot_range_to_curve_data(self, plot_key: str, curves, padding: float = 0.02) -> bool:
        """Set a plot range from curve data instead of relying on cached item bounds."""
        plot_widget = self._interactive_plot_widgets.get(plot_key)
        if plot_widget is None:
            return False

        data_range = self._curve_data_range(curves)
        if data_range is None:
            return False

        x_min, x_max, y_min, y_max = data_range
        view_box = plot_widget.getViewBox()
        self._plot_zoom_locked[plot_key] = False
        view_box.enableAutoRange(x=True, y=True)
        try:
            view_box.setRange(
                xRange=(x_min, x_max),
                yRange=(y_min, y_max),
                padding=padding,
                disableAutoRange=False,
            )
        except TypeError:
            view_box.setRange(xRange=(x_min, x_max), yRange=(y_min, y_max), padding=padding)
            view_box.enableAutoRange(x=True, y=True)
        self._refresh_plot_curve_items(plot_widget, curves)
        return True

    def _refresh_plot_curve_items(self, plot_widget: pg.PlotWidget, curves) -> None:
        """Refresh curve drawing paths after a forced range change."""
        for curve in curves:
            try:
                curve.updateItems()
            except Exception:
                pass
        try:
            plot_widget.getPlotItem().update()
            plot_widget.getViewBox().update()
        except Exception:
            pass

    def _setup_plots(self):
        """Initialize plot curves"""
        # Colors suitable for white background
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']  # Blue, Orange, Green, Red

        # Time domain curves (up to 4 frames)
        for i in range(4):
            curve = self.plot_widget_1.plot(pen=pg.mkPen(colors[i], width=1.5))
            self._configure_realtime_curve(curve)
            self.plot_curve_1.append(curve)

        # Monitor curves (up to 2 channels)
        for i in range(2):
            curve = self.plot_widget_3.plot(pen=pg.mkPen(colors[i], width=1.5))
            self._configure_realtime_curve(curve)
            self.monitor_curves.append(curve)

    # ----- SIGNAL-SLOT CONNECTIONS -----

    def _connect_signals(self):
        """Connect UI signals to slots"""
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)

        self.data_source_combo.currentIndexChanged.connect(self._on_data_source_changed)
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        self.point_num_spin.valueChanged.connect(self._update_calculated_values)
        self.scan_rate_spin.valueChanged.connect(self._update_calculated_values)
        self.merge_points_spin.valueChanged.connect(self._update_calculated_values)
        self.crop_distance_start_spin.valueChanged.connect(self._update_calculated_values)
        self.crop_distance_end_spin.valueChanged.connect(self._update_calculated_values)
        self.rate2phase_combo.currentIndexChanged.connect(self._update_calculated_values)
        self.frames_per_file_spin.valueChanged.connect(self._update_file_estimates)
        self.data_rate_combo.currentIndexChanged.connect(self._update_calculated_values)
        self.data_source_combo.currentIndexChanged.connect(self._sync_tcp_tab3_availability)
        self.channel_combo.currentIndexChanged.connect(self._sync_tcp_tab3_availability)
        self.point_num_spin.valueChanged.connect(self._sync_tcp_tab3_availability)
        self.scan_rate_spin.valueChanged.connect(self._sync_tcp_tab3_availability)
        self.merge_points_spin.valueChanged.connect(self._sync_tcp_tab3_availability)
        self.crop_distance_start_spin.valueChanged.connect(self._sync_tcp_tab3_availability)
        self.crop_distance_end_spin.valueChanged.connect(self._sync_tcp_tab3_availability)
        self.frame_load_num_spin.valueChanged.connect(self._sync_tcp_tab3_availability)
        self.frame_load_num_spin.valueChanged.connect(self._update_file_estimates)
        self.frame_plot_num_spin.valueChanged.connect(self._update_file_estimates)

        # Connect display mode signals.
        self.mode_time_radio.toggled.connect(self._on_mode_changed)
        self.mode_space_radio.toggled.connect(self._on_mode_changed)
        self.waveform_enable_check.toggled.connect(self._on_waveform_display_toggled)
        self.monitor_enable_check.toggled.connect(self._on_monitor_display_toggled)

        # Connect region index changes.
        self.region_index_spin.valueChanged.connect(self._on_region_changed)

        # 初始化分析类型标签
        self._initialize_analysis_type_label()
        self.tab3_comm_enable_check.toggled.connect(self._on_tcp_tab3_settings_changed)
        self.tab3_server_ip_edit.textChanged.connect(self._on_tcp_tab3_settings_changed)
        self.tab3_server_port_spin.valueChanged.connect(self._on_tcp_tab3_settings_changed)
        self.tab3_channel_start_spin.valueChanged.connect(self._on_tcp_tab3_settings_changed)
        self.tab3_channel_end_spin.valueChanged.connect(self._on_tcp_tab3_settings_changed)
        self.tab3_time_downsample_spin.valueChanged.connect(self._on_tcp_tab3_settings_changed)
        self.tab3_space_downsample_spin.valueChanged.connect(self._on_tcp_tab3_settings_changed)

    def _connect_tcp_tab3_manager(self):
        """Connect the communication manager to the Tab3 UI."""
        self.tcp_tab3_manager.status_changed.connect(self.update_tab3_comm_status)
        self.tcp_tab3_manager.statistics_changed.connect(self.update_tab3_comm_statistics)
        self.tcp_tab3_manager.availability_changed.connect(self.update_tab3_comm_availability)
        self.tcp_tab3_manager.error_occurred.connect(self._on_tcp_tab3_error)

    def _clear_waveform_plot(self):
        """Clear all waveform curves on plot 1."""
        if not hasattr(self, 'plot_curve_1'):
            return
        for curve in self.plot_curve_1:
            curve.setData([])

    def _clear_monitor_plot(self):
        """Clear all monitor curves on plot 3."""
        if not hasattr(self, 'monitor_curves'):
            return
        for curve in self.monitor_curves:
            curve.setData([])

    @pyqtSlot(bool)
    def _on_waveform_display_toggled(self, enabled: bool):
        """Enable or disable waveform rendering on plot 1."""
        if not enabled:
            self._clear_waveform_plot()

    @pyqtSlot(bool)
    def _on_monitor_display_toggled(self, enabled: bool):
        """Enable or disable monitor rendering on plot 3."""
        if not enabled:
            self._clear_monitor_plot()
        elif self._current_monitor_data is not None:
            try:
                channel_num = self.params.upload.channel_num or 1
                self._update_monitor_display(self._current_monitor_data, channel_num)
            except Exception as e:
                log.warning(f"Failed to refresh monitor display: {e}")

    def _sync_display_control_states(self):
        """Keep display switches consistent with the current data source."""
        is_phase = self.data_source_combo.currentData() == DataSource.PHASE
        self.plot_widget_3.setEnabled(is_phase)
        self.mode_space_radio.setEnabled(is_phase)
        self.monitor_enable_check.setEnabled(is_phase)
        if not is_phase:
            self._clear_monitor_plot()

    def _initialize_analysis_type_label(self):
        """Initialize the analysis type label based on the current data source."""
        # 根据当前数据源设置分析类型标签
        data_source = self.data_source_combo.currentData() or DataSource.PHASE
        is_phase = (data_source == DataSource.PHASE)

        if is_phase:
            self.analysis_type_label.setText("PSD")
            self.analysis_type_label.setToolTip("Phase data: PSD analysis using scipy.welch")
        else:
            self.analysis_type_label.setText("Power")
            self.analysis_type_label.setToolTip("Raw data: Power spectrum analysis")

    def _connect_time_space_signals(self):
        """Connect time-space widget signals after widget is created"""
        if hasattr(self, 'time_space_widget') and self.time_space_widget is not None:
            self.time_space_widget.parametersChanged.connect(self._on_time_space_params_changed)
            self.time_space_widget.pointCountChanged.connect(self._on_point_count_changed)
            # 连接 PLOT 按钮状态变化信号
            if hasattr(self.time_space_widget, 'plotStateChanged'):
                self.time_space_widget.plotStateChanged.connect(self._on_plot_state_changed)
            log.debug("Time-space widget signals connected")

    def _init_device(self):
        """Initialize the PCIe-7821 device"""
        log.info("Initializing device...")
        try:
            self.api = PCIe7821API()
            result = self.api.open()
            if result == 0:
                self._update_device_status(True)
                log.info("Device initialized successfully")
            else:
                self._update_device_status(False)
                log.error(f"Failed to open device: error code {result}")
                QMessageBox.warning(self, "Warning", f"Failed to open device: error code {result}")
        except FileNotFoundError as e:
            self._update_device_status(False)
            log.error(f"DLL not found: {e}")
            QMessageBox.warning(self, "Warning", f"DLL not found: {e}")
        except Exception as e:
            self._update_device_status(False)
            log.exception(f"Failed to initialize device: {e}")
            QMessageBox.warning(self, "Warning", f"Failed to initialize device: {e}")

    def _update_device_status(self, connected: bool):
        """Update device connection status display"""
        if connected:
            self._device_status_label.setText("Device: Connected")
            self._device_status_label.setStyleSheet("color: green;")
        else:
            self._device_status_label.setText("Device: Disconnected")
            self._device_status_label.setStyleSheet("color: red;")

    def _get_settings_path(self) -> Path:
        """Return the local settings file path for source and frozen builds."""
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent / "last_params.json"
        return Path(__file__).resolve().parents[1] / "last_params.json"

    def _merge_dict_into_dataclass(self, target, values: Dict[str, Any]):
        """Best-effort dataclass merge used by local settings restore."""
        if not isinstance(values, dict):
            return
        for field in fields(target):
            if field.name not in values:
                continue
            current_value = getattr(target, field.name)
            new_value = values[field.name]
            if is_dataclass(current_value) and isinstance(new_value, dict):
                self._merge_dict_into_dataclass(current_value, new_value)
            else:
                setattr(target, field.name, new_value)

    def _set_combo_to_data(self, combo: QComboBox, value: Any):
        """Set combo-box current item by user data when available."""
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return

    def _apply_params_to_ui(self, params: AllParams):
        """Apply restored parameters back to the UI controls."""
        if params.basic.clk_src == ClockSource.EXTERNAL:
            self.clk_external_radio.setChecked(True)
        else:
            self.clk_internal_radio.setChecked(True)

        if params.basic.trig_dir == TriggerDirection.INPUT:
            self.trig_in_radio.setChecked(True)
        else:
            self.trig_out_radio.setChecked(True)

        self.scan_rate_spin.setValue(params.basic.scan_rate)
        self.pulse_width_spin.setValue(params.basic.pulse_width_ns)
        self.point_num_spin.setValue(params.basic.point_num_per_scan)
        self.bypass_spin.setValue(params.basic.bypass_point_num)
        self.center_freq_spin.setValue(params.basic.center_freq_mhz)

        self._set_combo_to_data(self.channel_combo, params.upload.channel_num)
        self._set_combo_to_data(self.data_source_combo, params.upload.data_source)
        self._set_combo_to_data(self.data_rate_combo, params.upload.data_rate)

        self._set_combo_to_data(self.rate2phase_combo, params.phase_demod.rate2phase)
        self.space_avg_spin.setValue(params.phase_demod.space_avg_order)
        self.merge_points_spin.setValue(params.phase_demod.merge_point_num)
        self.crop_distance_start_spin.setValue(params.phase_demod.crop_distance_start)
        self.crop_distance_end_spin.setValue(params.phase_demod.crop_distance_end)
        self.diff_order_spin.setValue(params.phase_demod.diff_order)
        self.detrend_bw_spin.setValue(params.phase_demod.detrend_bw)
        self.polar_div_check.setChecked(params.phase_demod.polarization_diversity)

        if params.display.mode == DisplayMode.SPACE:
            self.mode_space_radio.setChecked(True)
        else:
            self.mode_time_radio.setChecked(True)
        self.region_index_spin.setValue(params.display.region_index)
        self.frame_load_num_spin.setValue(getattr(params.display, "frame_load_num", 1024))
        self.frame_plot_num_spin.setValue(getattr(params.display, "frame_plot_num", getattr(params.display, "frame_num", 1024)))
        self.spectrum_enable_check.setChecked(params.display.spectrum_enable)
        self.rad_check.setChecked(params.display.rad_enable)
        self.waveform_enable_check.setChecked(params.display.waveform_plot_enabled)
        self.monitor_enable_check.setChecked(params.display.monitor_plot_enabled)

        if self.time_space_widget is not None:
            self.time_space_widget.set_parameters(
                {
                    "window_frames": params.time_space.window_frames,
                    "distance_range_start": params.time_space.distance_range_start,
                    "distance_range_end": params.time_space.distance_range_end,
                    "time_downsample": params.time_space.time_downsample,
                    "space_downsample": params.time_space.space_downsample,
                    "colormap_type": params.time_space.colormap_type,
                    "vmin": params.time_space.vmin,
                    "vmax": params.time_space.vmax,
                }
            )
            self.time_space_widget.set_scan_rate(params.basic.scan_rate)

        self.save_enable_check.setChecked(params.save.enable)
        self.save_path_edit.setText(params.save.path)
        self.frames_per_file_spin.setValue(params.save.frames_per_file)

        self._sync_display_control_states()
        self._update_phase_crop_controls()
        self._update_calculated_values()
        self._update_file_estimates()

    def _save_local_params(self):
        """Persist the current UI parameters to last_params.json."""
        try:
            params = self._collect_params()
            payload = {
                "version": 1,
                "params": asdict(params),
            }
            self._settings_path.parent.mkdir(parents=True, exist_ok=True)
            self._settings_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.params = params
            log.info(f"Saved local parameters to {self._settings_path}")
        except Exception as e:
            log.warning(f"Failed to save local parameters: {e}")

    def _load_local_params(self):
        """Restore the last saved UI parameters when available."""
        if not self._settings_path.exists():
            log.info(f"Local parameter file not found, using defaults: {self._settings_path}")
            self._sync_display_control_states()
            self._update_calculated_values()
            self._update_file_estimates()
            return

        try:
            payload = json.loads(self._settings_path.read_text(encoding="utf-8"))
            params_data = payload.get("params", payload)
            params = AllParams()
            self._merge_dict_into_dataclass(params, params_data)
            self._apply_params_to_ui(params)
            self.params = self._collect_params()
            log.info(f"Loaded local parameters from {self._settings_path}")
        except Exception as e:
            log.warning(f"Failed to load local parameters, using defaults: {e}")
            self._sync_display_control_states()
            self._update_calculated_values()
            self._update_file_estimates()

    def _collect_params(self) -> AllParams:
        """Collect current parameter values from UI"""
        params = AllParams()

        # Basic params
        params.basic.clk_src = ClockSource.EXTERNAL if self.clk_external_radio.isChecked() else ClockSource.INTERNAL
        params.basic.trig_dir = TriggerDirection.INPUT if self.trig_in_radio.isChecked() else TriggerDirection.OUTPUT
        params.basic.scan_rate = self.scan_rate_spin.value()
        params.basic.pulse_width_ns = self.pulse_width_spin.value()
        params.basic.point_num_per_scan = self.point_num_spin.value()
        params.basic.bypass_point_num = self.bypass_spin.value()
        params.basic.center_freq_mhz = self.center_freq_spin.value()

        # Upload params
        params.upload.channel_num = self.channel_combo.currentData()
        params.upload.data_source = self.data_source_combo.currentData()
        params.upload.data_rate = self.data_rate_combo.currentData()

        # Phase demod params
        params.phase_demod.rate2phase = self.rate2phase_combo.currentData()
        params.phase_demod.space_avg_order = self.space_avg_spin.value()
        params.phase_demod.merge_point_num = self.merge_points_spin.value()
        params.phase_demod.crop_distance_start = self.crop_distance_start_spin.value()
        params.phase_demod.crop_distance_end = self.crop_distance_end_spin.value()
        params.phase_demod.diff_order = self.diff_order_spin.value()
        params.phase_demod.detrend_bw = self.detrend_bw_spin.value()
        params.phase_demod.polarization_diversity = self.polar_div_check.isChecked()

        # Display params
        # Display mode selection (绉婚櫎TIME_SPACE閫夐」锛岀敱PLOT鎸夐挳鎺у埗)
        if self.mode_space_radio.isChecked():
            params.display.mode = DisplayMode.SPACE
        else:
            params.display.mode = DisplayMode.TIME

        params.display.region_index = self.region_index_spin.value()
        params.display.frame_load_num = self.frame_load_num_spin.value()
        params.display.frame_plot_num = self.frame_plot_num_spin.value()
        params.display.spectrum_enable = self.spectrum_enable_check.isChecked()
        # Note: PSD mode now automatically determined by data_type (removed psd_enable)
        params.display.rad_enable = self.rad_check.isChecked()
        params.display.waveform_plot_enabled = self.waveform_enable_check.isChecked()
        params.display.monitor_plot_enabled = self.monitor_enable_check.isChecked()

        # Time-Space parameters (get from widget if available)
        if self.time_space_widget is not None:
            ts_params = self.time_space_widget.get_parameters()
            params.time_space.window_frames = ts_params['window_frames']
            params.time_space.distance_range_start = ts_params['distance_range_start']
            params.time_space.distance_range_end = ts_params['distance_range_end']
            params.time_space.time_downsample = ts_params['time_downsample']
            params.time_space.space_downsample = ts_params['space_downsample']
            params.time_space.colormap_type = ts_params['colormap_type']
            params.time_space.vmin = ts_params['vmin']
            params.time_space.vmax = ts_params['vmax']

        # Save params
        params.save.enable = self.save_enable_check.isChecked()
        params.save.path = self.save_path_edit.text()
        params.save.frames_per_file = self.frames_per_file_spin.value()

        return params

    def _validate_params(self, params: AllParams) -> tuple[bool, str]:
        """Validate parameters before starting"""
        # Validate point number
        valid, msg = validate_point_num(
            params.basic.point_num_per_scan,
            params.upload.channel_num
        )
        if not valid:
            return False, msg

        if params.display.frame_load_num <= 0:
            return False, "FrameLoad must be greater than 0."

        if params.display.frame_plot_num <= 0:
            return False, "FramePlot must be greater than 0."

        if params.display.frame_plot_num > params.display.frame_load_num:
            return False, "FramePlot must not exceed FrameLoad."

        # Raw data source with 4 channels not supported
        if params.upload.data_source != DataSource.PHASE and params.upload.channel_num == 4:
            return False, "Raw data source does not support 4 channels"

        if params.upload.data_source == DataSource.PHASE and params.upload.channel_num == 1:
            total_points = calculate_phase_point_num(
                params.basic.point_num_per_scan,
                params.phase_demod.merge_point_num,
            )
            crop_start = params.phase_demod.crop_distance_start
            crop_end = params.phase_demod.crop_distance_end
            if crop_start < 0 or crop_end < 0:
                return False, "CropStart/CropEnd must be >= 0"
            if not (crop_start == 0 and crop_end == 0) and crop_start >= total_points:
                return False, f"CropStart must be smaller than total PHASE points ({total_points})"
            if crop_end > 0 and crop_end <= crop_start:
                return False, "CropEnd must be greater than CropStart"

        return True, ""

    def _is_phase_spatial_crop_active(self, params: Optional[AllParams] = None) -> bool:
        """Return whether single-channel PHASE spatial crop should be applied."""
        params = params or self.params
        return (
            params.upload.data_source == DataSource.PHASE
            and params.upload.channel_num == 1
        )

    def _get_phase_point_count_after_merge(self, params: Optional[AllParams] = None) -> int:
        """Return PHASE points per frame before software crop."""
        params = params or self.params
        return calculate_phase_point_num(
            params.basic.point_num_per_scan,
            params.phase_demod.merge_point_num,
        )

    def _get_effective_phase_point_count(self, params: Optional[AllParams] = None) -> int:
        """Return PHASE points per frame after software crop."""
        params = params or self.params
        base_count = self._get_phase_point_count_after_merge(params)
        if not self._is_phase_spatial_crop_active(params):
            return base_count
        return calculate_cropped_point_count(
            base_count,
            params.phase_demod.crop_distance_start,
            params.phase_demod.crop_distance_end,
        )

    def get_tab3_comm_settings(self) -> Dict[str, Any]:
        """Return the current TCP communication settings."""
        return {
            "enabled": self.tab3_comm_enable_check.isChecked(),
            "server_ip": self.tab3_server_ip_edit.text().strip(),
            "server_port": self.tab3_server_port_spin.value(),
            "channel_start": self.tab3_channel_start_spin.value(),
            "channel_end": self.tab3_channel_end_spin.value(),
            "time_downsample": self.tab3_time_downsample_spin.value(),
            "space_downsample": self.tab3_space_downsample_spin.value(),
            "reconnect_interval_s": 1.0,
            "queue_max_packets": 8,
        }

    def _on_tcp_tab3_settings_changed(self, *_args):
        """Refresh Tab3 availability and static field hints after one setting change."""
        self._sync_tcp_tab3_availability()

    def _sync_tcp_tab3_availability(self, *_args):
        """Publish current communication availability using the latest acquisition params."""
        try:
            params = self._collect_params()
        except Exception:
            return
        self.tcp_tab3_manager.update_enabled(self.tab3_comm_enable_check.isChecked(), params)
        self._update_tab3_comm_hints(params)

    def _update_tab3_comm_hints(self, params: AllParams):
        """Update read-only protocol hints shown on Tab3."""
        point_num_after_merge = max(1, self._get_effective_phase_point_count(params))
        channel_start = max(0, min(self.tab3_channel_start_spin.value(), point_num_after_merge - 1))
        channel_end = max(channel_start, min(self.tab3_channel_end_spin.value(), point_num_after_merge - 1))
        selected_count = len(range(channel_start, channel_end + 1, max(1, self.tab3_space_downsample_spin.value())))

        sample_rate_text = "Invalid"
        duration_text = "-"
        data_bytes_text = "-"
        if params.basic.scan_rate > 0 and params.basic.scan_rate % max(1, self.tab3_time_downsample_spin.value()) == 0:
            sample_rate_hz = params.basic.scan_rate // self.tab3_time_downsample_spin.value()
            samples_per_channel = len(range(0, params.display.frame_load_num, max(1, self.tab3_time_downsample_spin.value())))
            sample_rate_text = f"{sample_rate_hz} Hz"
            packet_duration = samples_per_channel / float(sample_rate_hz)
            duration_text = f"{packet_duration:.6f} s"
            data_bytes = selected_count * samples_per_channel * 8
            data_bytes_text = str(data_bytes)

        self.tab3_comm_channel_count_label.setText(str(selected_count))
        self.tab3_comm_sample_rate_label.setText(sample_rate_text)
        self.tab3_comm_duration_label.setText(duration_text)
        self.tab3_comm_data_bytes_label.setText(data_bytes_text)

    def update_tab3_comm_availability(self, payload: Dict[str, Any]):
        """Update whether communication is currently allowed."""
        available = bool(payload.get("available", False))
        reason = str(payload.get("reason", ""))
        self.tab3_availability_label.setText(reason)
        self.tab3_availability_label.setStyleSheet(
            "color: green; font-weight: bold;" if available else "color: #b36b00; font-weight: bold;"
        )

    def update_tab3_comm_status(self, payload: Dict[str, Any]):
        """Update connection state and human-readable status text."""
        state = str(payload.get("state", "idle")).capitalize()
        connected = bool(payload.get("connected", False))
        self.tab3_comm_state_label.setText(state)
        self.tab3_comm_state_label.setStyleSheet(
            "color: green; font-weight: bold;" if connected else "color: #555; font-weight: bold;"
        )
        self.tab3_comm_message_label.setText(str(payload.get("message", "-")))

    def update_tab3_comm_statistics(self, payload: Dict[str, Any]):
        """Update Tab3 packet counters and the latest outgoing header summary."""
        self.tab3_acquired_packets_label.setText(str(payload.get("acquired_packets", 0)))
        self.tab3_queued_packets_label.setText(str(payload.get("queued_packets", 0)))
        self.tab3_sent_packets_label.setText(str(payload.get("sent_packets", 0)))
        self.tab3_dropped_packets_label.setText(str(payload.get("dropped_packets", 0)))
        last_comm = payload.get("last_comm_count", -1)
        self.tab3_last_comm_count_label.setText("-" if int(last_comm) < 0 else str(last_comm))
        self.tab3_bytes_sent_label.setText(str(payload.get("bytes_sent", 0)))
        self.tab3_comm_channel_count_label.setText(str(payload.get("channel_count", self.tab3_comm_channel_count_label.text())))
        sample_rate = payload.get("sample_rate_hz", 0)
        self.tab3_comm_sample_rate_label.setText("-" if not sample_rate else f"{sample_rate} Hz")
        duration = float(payload.get("packet_duration_seconds", 0.0))
        self.tab3_comm_duration_label.setText("-" if duration <= 0 else f"{duration:.6f} s")
        data_bytes = int(payload.get("data_bytes", 0))
        self.tab3_comm_data_bytes_label.setText("-" if data_bytes <= 0 else str(data_bytes))
        last_error = str(payload.get("last_error", "")).strip()
        if last_error:
            self.tab3_comm_last_error_label.setText(last_error)

    def _on_tcp_tab3_error(self, message: str):
        """Show the latest communication error without interrupting acquisition."""
        self.tab3_comm_last_error_label.setText(message)
        self.statusBar.showMessage(f"TCP Comm: {message}", 5000)

    def _configure_device(self, params: AllParams) -> bool:
        """Configure device with parameters"""
        if self.api is None:
            return False

        log.info("Configuring device...")
        try:
            self.api.set_clk_src(params.basic.clk_src)
            self.api.set_trig_dir(params.basic.trig_dir)
            self.api.set_scan_rate(params.basic.scan_rate)
            self.api.set_pulse_width(params.basic.pulse_width_ns)
            self.api.set_point_num_per_scan(params.basic.point_num_per_scan)
            self.api.set_bypass_point_num(params.basic.bypass_point_num)
            self.api.set_center_freq(params.basic.center_freq_mhz * 1000000)

            self.api.set_upload_data_param(
                params.upload.channel_num,
                params.upload.data_source,
                params.upload.data_rate
            )

            self.api.set_phase_dem_param(
                params.phase_demod.rate2phase,
                params.phase_demod.space_avg_order,
                params.phase_demod.merge_point_num,
                params.phase_demod.diff_order,
                params.phase_demod.detrend_bw,
                params.phase_demod.polarization_diversity
            )

            # Allocate buffers
            self.api.allocate_buffers(
                params.basic.point_num_per_scan,
                params.upload.channel_num,
                params.display.frame_load_num,
                params.phase_demod.merge_point_num,
                params.upload.data_source == DataSource.PHASE
            )

            log.info("Device configured successfully")
            return True

        except PCIe7821Error as e:
            log.error(f"Failed to configure device: {e}")
            QMessageBox.critical(self, "Error", f"Failed to configure device: {e}")
            return False

    # ----- ACQUISITION CONTROL (START / STOP) -----

    @pyqtSlot()
    def _on_start(self):
        """Handle start button click"""
        log.info("=== START button clicked ===")

        # Collect and validate parameters
        params = self._collect_params()
        valid, msg = self._validate_params(params)
        if not valid:
            log.warning(f"Invalid parameters: {msg}")
            QMessageBox.warning(self, "Invalid Parameters", msg)
            return

        self.params = params
        self._save_local_params()
        if self.time_space_widget is not None:
            self.time_space_widget.set_scan_rate(params.basic.scan_rate)
        if params.upload.data_source == DataSource.PHASE:
            points_per_frame = self._get_effective_phase_point_count(params)
            bytes_per_point = 4
        else:
            points_per_frame = params.basic.point_num_per_scan
            bytes_per_point = 2
        block_bytes = points_per_frame * params.display.frame_load_num * params.upload.channel_num * bytes_per_point
        block_duration_ms = params.display.frame_load_num / max(params.basic.scan_rate, 1) * 1000.0
        log.info(f"Parameters: scan_rate={params.basic.scan_rate}, points={params.basic.point_num_per_scan}, "
                 f"channels={params.upload.channel_num}, data_source={params.upload.data_source}, "
                 f"frame_load={params.display.frame_load_num}, frame_plot={params.display.frame_plot_num}, "
                 f"block_bytes={block_bytes / 1024 / 1024:.2f}MB, block_duration={block_duration_ms:.1f}ms")

        # Configure device (if not simulation mode)
        if not self.simulation_mode:
            if not self._configure_device(params):
                return

            # Start device
            log.info("Starting device acquisition...")
            try:
                self.api.start()
            except PCIe7821Error as e:
                log.error(f"Failed to start acquisition: {e}")
                QMessageBox.critical(self, "Error", f"Failed to start acquisition: {e}")
                return

        # Start data saver if enabled (frame-based)
        if params.save.enable:
            log.info(f"Starting frame-based data saver to {params.save.path}")
            self.data_saver = FrameBasedFileSaver(
                params.save.path,
                frames_per_file=params.save.frames_per_file,
                buffer_size=OPTIMIZED_BUFFER_SIZES['storage_queue_frames']
            )
            # Calculate points per frame for filename
            if params.upload.data_source == DataSource.PHASE:
                points_per_frame = self._get_effective_phase_point_count(params)
            else:
                points_per_frame = params.basic.point_num_per_scan
            filename = self.data_saver.start(
                scan_rate=params.basic.scan_rate,
                points_per_frame=points_per_frame
            )
            self.save_status_label.setText(f"Save: {filename}")
        else:
            self.save_status_label.setText("Save: Off")

        # Reset counters
        self._data_count = 0
        self._gui_update_count = 0
        self._raw_data_count = 0
        self._full_data_count = 0
        self._last_data_time = time.time()
        self._recovery_in_progress = False
        self._last_raw_display_time = 0  # Force immediate first update

        # Create and start acquisition thread
        log.info("Creating acquisition thread...")
        if self.simulation_mode:
            self.acq_thread = SimulatedAcquisitionThread(self)
        else:
            self.acq_thread = AcquisitionThread(self.api, self)

        self.acq_thread.configure(params)
        self._tcp_settings_snapshot = self.get_tab3_comm_settings()
        self.acq_thread.set_full_data_handler(self._handle_full_data_block)

        # Only small control/monitor signals enter the GUI queue.
        log.debug("Connecting acquisition thread signals...")
        self.acq_thread.monitor_data_ready.connect(self._on_monitor_data)
        self.acq_thread.buffer_status.connect(self._on_buffer_status)
        self.acq_thread.error_occurred.connect(self._on_error)
        self.acq_thread.acquisition_stopped.connect(self._on_acquisition_stopped)

        self.tcp_tab3_manager.start_session(params)

        log.info("Starting acquisition thread...")
        self.acq_thread.start()

        # Update UI state - button colors change
        self._set_start_btn_running()
        self._set_stop_btn_enabled()
        self._set_params_enabled(False)

        # Reset spectrum analyzer
        self.spectrum_analyzer.reset()

        log.info("Acquisition started successfully")

    @pyqtSlot()
    def _on_stop(self):
        """Handle stop button click"""
        log.info("=== STOP button clicked ===")

        # Stop display consumption and restore controls immediately. Hardware cleanup follows.
        self._set_start_btn_ready()
        self._set_stop_btn_disabled()
        self._set_params_enabled(True)
        self.stop_btn.setText("Stopping...")

        thread_stopped = True
        stopping_thread = self.acq_thread
        if stopping_thread is not None:
            log.debug("Requesting acquisition thread stop...")
            stopping_thread.stop()

        self._log_acquisition_diagnostics("manual_stop_before_api_stop", force=True)

        if not self.simulation_mode and self.api is not None:
            log.debug("Stopping device...")
            try:
                self.api.stop()
            except PCIe7821Error as e:
                log.warning(f"Error stopping device: {e}")
            except Exception as e:
                log.warning(f"Unexpected error stopping device: {e}")

        if stopping_thread is not None:
            thread_stopped = stopping_thread.wait_until_stopped(5000)
            if not thread_stopped:
                log.error("Acquisition thread is still running after stop; skip force terminate to avoid driver corruption")
            stopping_thread.set_full_data_handler(None)
            stopping_thread.clear_latest_display_data()

        if self.data_saver is not None:
            log.debug("Stopping data saver...")
            try:
                self.data_saver.stop()
            except Exception as e:
                log.warning(f"Error stopping data saver: {e}")
            self.data_saver = None

        self.tcp_tab3_manager.stop_session()

        self.save_status_label.setText("Save: Off")
        if self.acq_thread is stopping_thread:
            self.acq_thread = None
        log.info(
            f"Stopped (thread_stopped={thread_stopped}). "
            f"Total data callbacks: {self._data_count}, GUI updates: {self._gui_update_count}"
        )

        self.stop_btn.setText("STOP")

    @pyqtSlot()
    def _on_acquisition_stopped(self):
        """Handle acquisition stopped signal"""
        if self.sender() is not self.acq_thread:
            log.debug("Ignoring delayed acquisition_stopped signal from an inactive thread")
            return
        log.info("Acquisition stopped signal received")
        # Restore button colors
        self._set_start_btn_ready()
        self._set_stop_btn_disabled()
        self._set_params_enabled(True)

    def _set_params_enabled(self, enabled: bool):
        """Enable/disable parameter controls"""
        for widget in [self.clk_internal_radio, self.clk_external_radio,
                       self.trig_in_radio, self.trig_out_radio,
                       self.scan_rate_spin, self.pulse_width_spin,
                       self.point_num_spin, self.bypass_spin, self.center_freq_spin,
                       self.channel_combo, self.data_source_combo, self.data_rate_combo,
                       self.rate2phase_combo, self.space_avg_spin, self.merge_points_spin,
                       self.diff_order_spin, self.detrend_bw_spin, self.polar_div_check]:
            widget.setEnabled(enabled)

    # ----- DATA HANDLERS -----
    # Complete blocks stay off the GUI event queue. The GUI consumes only the latest snapshot.

    def _handle_full_data_block(self, data: np.ndarray, data_source: int, channel_num: int):
        """Run in the acquisition thread and hand complete blocks to background consumers."""
        self._full_data_count += 1

        if data_source == DataSource.PHASE:
            self.tcp_tab3_manager.enqueue_phase_data(data, self.params, self._tcp_settings_snapshot)

        saver = self.data_saver
        if saver is not None and saver.is_running:
            save_ok = saver.save_frame(data)
            if not save_ok:
                log.warning(f"Save enqueue failed at full block #{self._full_data_count}")

    def _drain_latest_display_data(self):
        """Consume at most one latest display snapshot per GUI timer tick."""
        thread = self.acq_thread
        if thread is None or not thread.is_running:
            return

        latest = thread.take_latest_display_data()
        if latest is None:
            return

        data, data_source, channel_num = latest
        if data_source == DataSource.PHASE:
            self._on_phase_data(data, channel_num)
        else:
            self._on_raw_data(data, data_source, channel_num)

    @pyqtSlot(np.ndarray, int)
    def _on_phase_data(self, data: np.ndarray, channel_num: int):
        """Handle phase data from acquisition thread"""
        self._data_count += 1
        self._last_data_time = time.time()
        start_time = time.perf_counter()
        rad_ms = 0.0
        display_ms = 0.0

        if self._data_count % 10 == 0:
            log.debug(f"Phase data received #{self._data_count}: shape={data.shape}, channels={channel_num}")

        # rad conversion: display-only, does NOT affect saved data.
        # Formula: rad = int32_value / 32767 * pi (FPGA uses 32767 as full-scale pi)
        processed_data = data
        if self.params.display.rad_enable:
            rad_start = time.perf_counter()
            processed_data = data.astype(np.float32)
            processed_data *= np.float32(np.pi / 32767.0)
            rad_ms = (time.perf_counter() - rad_start) * 1000

        # Update display (use processed data)
        try:
            display_start = time.perf_counter()
            self._update_phase_display(processed_data, channel_num)
            display_ms = (time.perf_counter() - display_start) * 1000
            self._gui_update_count += 1
        except Exception as e:
            log.exception(f"Error in _update_phase_display: {e}")

        if self.acq_thread is not None:
            self.frames_label.setText(f"Frames: {self.acq_thread.frames_acquired}")

        elapsed = (time.perf_counter() - start_time) * 1000
        if self._data_count <= 3 or self._data_count % 10 == 0:
            queue_size = self.data_saver.queue_size if self.data_saver is not None and self.data_saver.is_running else 0
            log.debug(
                f"Phase callback #{self._data_count}: bytes={data.nbytes / 1024 / 1024:.2f}MB, "
                f"rad_ms={rad_ms:.1f}, display_ms={display_ms:.1f}, total_ms={elapsed:.1f}, "
                f"queue={queue_size}"
            )
        if elapsed > 50:
            log.warning(
                f"Slow _on_phase_data: {elapsed:.1f}ms "
                f"(rad={rad_ms:.1f}, display={display_ms:.1f})"
            )

    @pyqtSlot(np.ndarray, int, int)
    def _on_raw_data(self, data: np.ndarray, data_type: int, channel_num: int):
        """Handle raw data from acquisition thread"""
        self._data_count += 1
        self._raw_data_count += 1
        self._last_data_time = time.time()
        start_time = time.perf_counter()
        display_ms = 0.0

        if self._data_count % 10 == 0:
            log.debug(f"Raw data received #{self._data_count}: shape={data.shape}, type={data_type}, channels={channel_num}")

        # Throttle raw display to 1 Hz to reduce GPU load (raw data is high volume)
        current_time = time.time()
        if (current_time - self._last_raw_display_time) >= 1.0:
            # Update display
            try:
                display_start = time.perf_counter()
                self._update_raw_display(data, channel_num)
                display_ms = (time.perf_counter() - display_start) * 1000
                self._gui_update_count += 1
                log.debug(f"Raw display updated #{self._raw_data_count}: interval={current_time - self._last_raw_display_time:.1f}s")
                self._last_raw_display_time = current_time
            except Exception as e:
                log.exception(f"Error in _update_raw_display: {e}")

        if self.acq_thread is not None:
            self.frames_label.setText(f"Frames: {self.acq_thread.frames_acquired}")

        elapsed = (time.perf_counter() - start_time) * 1000
        if self._raw_data_count <= 3 or self._raw_data_count % 10 == 0:
            queue_size = self.data_saver.queue_size if self.data_saver is not None and self.data_saver.is_running else 0
            log.debug(
                f"Raw callback #{self._raw_data_count}: bytes={data.nbytes / 1024 / 1024:.2f}MB, "
                f"display_ms={display_ms:.1f}, total_ms={elapsed:.1f}, queue={queue_size}"
            )
        if elapsed > 50:
            log.warning(f"Slow _on_raw_data: {elapsed:.1f}ms (display={display_ms:.1f})")

    @pyqtSlot(np.ndarray, int)
    def _on_monitor_data(self, data: np.ndarray, channel_num: int):
        """Handle monitor data from acquisition thread"""
        self._current_monitor_data = data
        if not self.monitor_enable_check.isChecked():
            return
        try:
            self._update_monitor_display(data, channel_num)
        except Exception as e:
            log.exception(f"Error in _update_monitor_display: {e}")

    @pyqtSlot(int, int)
    def _on_buffer_status(self, points: int, mb: int):
        """Handle buffer status update"""
        self.buffer_label.setText(f"Buffer: {mb} MB")

    @pyqtSlot(str)
    def _on_error(self, message: str):
        """Handle error from acquisition thread"""
        log.error(f"Acquisition error: {message}")
        self.statusBar.showMessage(f"Error: {message}", 5000)

    # ----- DISPLAY UPDATE METHODS -----
    # Time mode: overlay multiple frames on one plot
    # Space mode: extract single spatial point across frames (temporal trace)

    def _set_time_plot_bottom_label(self, label: str) -> None:
        """Set the bottom axis label for the Tab1 time-domain plot."""
        self.plot_widget_1.setLabel(
            'bottom',
            label,
            color='k',
            **{'font-family': 'Times New Roman', 'font-size': '8pt'},
        )

    def _set_time_plot_axis(self, label: str, axis_kind: str) -> None:
        """Set Tab1 axis semantics and reset view when the x-axis unit changes."""
        previous_axis_kind = self._time_plot_axis_kind
        self._set_time_plot_bottom_label(label)
        self._configure_time_plot_curves_for_axis(axis_kind)
        if previous_axis_kind == axis_kind:
            return

        self._time_plot_axis_kind = axis_kind
        if previous_axis_kind is None:
            return

        self._clear_waveform_plot()
        self._time_plot_pending_auto_range = True
        self._time_plot_auto_range_frames_remaining = 8
        self._restore_plot_auto_range("plot1")
        log.debug(f"Tab1 time plot axis changed: {previous_axis_kind} -> {axis_kind}")

    def _apply_pending_time_plot_auto_range(self) -> None:
        """Restore Tab1 view after new data has been written for a changed x-axis."""
        if (
            not self._time_plot_pending_auto_range
            and self._time_plot_auto_range_frames_remaining <= 0
        ):
            return

        if self._plot_zoom_locked.get("plot1", False):
            self._time_plot_pending_auto_range = False
            self._time_plot_auto_range_frames_remaining = 0
            return

        self._time_plot_pending_auto_range = False
        self._restore_plot_auto_range("plot1")
        forced = self._force_plot_range_to_curve_data("plot1", self.plot_curve_1)
        if forced and self._time_plot_auto_range_frames_remaining > 0:
            self._time_plot_auto_range_frames_remaining -= 1
        expected_axis = self._time_plot_axis_kind
        QTimer.singleShot(0, lambda axis=expected_axis: self._retry_time_plot_auto_range(axis))
        QTimer.singleShot(50, lambda axis=expected_axis: self._retry_time_plot_auto_range(axis))
        QTimer.singleShot(150, lambda axis=expected_axis: self._retry_time_plot_auto_range(axis))
        QTimer.singleShot(300, lambda axis=expected_axis: self._retry_time_plot_auto_range(axis))

    def _retry_time_plot_auto_range(self, expected_axis_kind: Optional[str]) -> None:
        """Repeat Tab1 range restoration after Qt has processed the latest curve update."""
        if expected_axis_kind != self._time_plot_axis_kind:
            return
        if self._plot_zoom_locked.get("plot1", False):
            self._time_plot_auto_range_frames_remaining = 0
            return
        self._restore_plot_auto_range("plot1")
        self._force_plot_range_to_curve_data("plot1", self.plot_curve_1)

    def _raw_distance_axis(self, point_count: int) -> np.ndarray:
        """Return Raw distance coordinates in meters, using 1-based point positions."""
        spacing_m = 0.1 * float(self.params.upload.data_rate or 1)
        return np.arange(1, int(point_count) + 1, dtype=float) * spacing_m

    def _phase_distance_axis(self, point_count: int) -> np.ndarray:
        """Return PHASE distance coordinates in meters, using rate2phase and merge."""
        rate2phase = max(1, int(self.params.phase_demod.rate2phase or 1))
        merge_points = max(1, int(self.params.phase_demod.merge_point_num or 1))
        spacing_m = 0.4 * rate2phase * merge_points
        return np.arange(1, int(point_count) + 1, dtype=float) * spacing_m

    def _phase_time_axis(self, frame_count: int) -> np.ndarray:
        """Return PHASE temporal coordinates in seconds, using Scan(Hz)."""
        scan_rate = max(1.0, float(self.params.basic.scan_rate or 1))
        return np.arange(1, int(frame_count) + 1, dtype=float) / scan_rate

    def _update_phase_display(self, data: np.ndarray, channel_num: int):
        """Update display for phase data"""
        point_num = self._get_effective_phase_point_count()
        waveform_enabled = self.waveform_enable_check.isChecked()
        display_data, frame_num = self._select_latest_display_frames(
            data,
            point_num,
            channel_num,
            self.params.display.frame_plot_num,
        )
        if frame_num <= 0:
            return

        # Debug output to identify mode
        log.debug(f"Display mode: {self.params.display.mode}, Region index: {self.params.display.region_index}")

        if self.params.display.mode == DisplayMode.SPACE:
            self._set_time_plot_axis('Time (s)', 'time')
            time_axis = self._phase_time_axis(frame_num)

            # Space mode: extract single region over time
            region_idx = min(self.params.display.region_index, point_num - 1)

            if channel_num == 1:
                # Extract region data across frames
                space_data = []
                for i in range(frame_num):
                    idx = region_idx + point_num * i
                    if idx < len(display_data):
                        space_data.append(display_data[idx])

                space_data = np.array(space_data)
                if waveform_enabled:
                    self.plot_curve_1[0].setData(time_axis[:len(space_data)], space_data)
                    self._apply_pending_time_plot_auto_range()

                    # Clear other curves
                    for i in range(1, 4):
                        self.plot_curve_1[i].setData([])

                # Update spectrum (Phase data: automatically uses PSD)
                if self.params.display.spectrum_enable and len(space_data) > 0:
                    self._update_spectrum(space_data, self.params.basic.scan_rate,
                                         psd_mode=False, data_type='int')  # psd_mode ignored for phase data
            else:
                # Multi-channel space mode
                if len(display_data.shape) == 1:
                    display_data = display_data.reshape(-1, channel_num)

                for ch in range(min(channel_num, 2)):
                    space_data = []
                    for i in range(frame_num):
                        idx = region_idx + point_num * i
                        if idx < len(display_data):
                            space_data.append(display_data[idx, ch])
                    if waveform_enabled:
                        space_data = np.array(space_data)
                        self.plot_curve_1[ch].setData(time_axis[:len(space_data)], space_data)

                if waveform_enabled:
                    self._apply_pending_time_plot_auto_range()
                    for i in range(channel_num, 4):
                        self.plot_curve_1[i].setData([])

        else:
            self._set_time_plot_axis('Distance (m)', 'distance')
            distance_axis = self._phase_distance_axis(point_num)

            # Time mode: show multiple frames overlay
            if channel_num == 1:
                for i in range(min(4, frame_num)):
                    start = i * point_num
                    end = start + point_num
                    if waveform_enabled and end <= len(display_data):
                        self.plot_curve_1[i].setData(distance_axis, display_data[start:end])
                        if i == 0:
                            self._apply_pending_time_plot_auto_range()
                    elif waveform_enabled:
                        self.plot_curve_1[i].setData([])

                # Spectrum of first frame (Phase data: automatically uses PSD)
                if self.params.display.spectrum_enable and point_num <= len(display_data):
                    self._update_spectrum(display_data[-point_num:], self.params.basic.scan_rate,
                                         psd_mode=False, data_type='int')  # psd_mode ignored for phase data
            else:
                if len(display_data.shape) == 1:
                    display_data = display_data.reshape(-1, channel_num)

                # Show first frame of each channel
                for ch in range(min(channel_num, 4)):
                    if waveform_enabled and point_num <= len(display_data):
                        self.plot_curve_1[ch].setData(distance_axis, display_data[:point_num, ch])
                if waveform_enabled:
                    self._apply_pending_time_plot_auto_range()

        # Time-Space plot: independent from the Tab1 Mode control and driven by PLOT.
        # Update it only when Tab2 is active, avoiding unnecessary Tab1 interference.
        if (self.time_space_widget is not None and
            hasattr(self.time_space_widget, 'is_plot_enabled') and
            self.time_space_widget.is_plot_enabled() and
            self.plot_tabs.currentIndex() == 1):  # Update only while Tab2 is active
            # Use the processed data parameter (already includes rad conversion if enabled)
            self.time_space_widget.set_scan_rate(self.params.basic.scan_rate)

            # Reshape data to frames x points for time-space widget
            if len(display_data.shape) == 1:
                # Single frame data
                reshaped_data = display_data.reshape(frame_num, point_num)
            else:
                # Multi-channel data - use first channel for now
                if channel_num == 1:
                    reshaped_data = display_data.reshape(frame_num, point_num)
                else:
                    # Take first channel from multi-channel data
                    channel_data = display_data.reshape(-1, channel_num)[:, 0]
                    reshaped_data = channel_data.reshape(frame_num, point_num)

            # Update the time-space plot
            success = self.time_space_widget.update_data(reshaped_data)
            if not success:
                log.debug("Time-space plot update skipped (plot disabled)")

    def _update_raw_display(self, data: np.ndarray, channel_num: int):
        """Update display for raw IQ data"""
        point_num = self.params.basic.point_num_per_scan
        waveform_enabled = self.waveform_enable_check.isChecked()
        display_data, frame_num = self._select_latest_display_frames(
            data,
            point_num,
            channel_num,
            self.params.display.frame_plot_num,
        )
        if frame_num <= 0:
            return

        self._set_time_plot_axis('Distance (m)', 'distance')
        distance_axis = self._raw_distance_axis(point_num)

        if channel_num == 1:
            # Show full-resolution frames; pyqtgraph handles view clipping/downsampling.
            for i in range(min(4, frame_num)):
                start = i * point_num
                end = start + point_num
                if waveform_enabled and end <= len(display_data):
                    self.plot_curve_1[i].setData(distance_axis, display_data[start:end])
                    if i == 0:
                        self._apply_pending_time_plot_auto_range()
                elif waveform_enabled:
                    self.plot_curve_1[i].setData([])

            # Spectrum: use full-resolution data (Raw data: automatically uses Power Spectrum)
            if self.params.display.spectrum_enable and point_num <= len(display_data):
                sample_rate = 1e9 / self.params.upload.data_rate
                self._update_spectrum(display_data[-point_num:], sample_rate,
                                     psd_mode=False, data_type='short')  # psd_mode ignored for raw data
        else:
            if len(display_data.shape) == 1:
                display_data = display_data.reshape(-1, channel_num)

            for ch in range(min(channel_num, 4)):
                if waveform_enabled and point_num <= len(display_data):
                    self.plot_curve_1[ch].setData(distance_axis, display_data[:point_num, ch])
            if waveform_enabled:
                self._apply_pending_time_plot_auto_range()

            # Spectrum: full-resolution data (Raw data: automatically uses Power Spectrum)
            if self.params.display.spectrum_enable and point_num <= len(display_data):
                sample_rate = 1e9 / self.params.upload.data_rate
                # Use first channel for spectrum computation
                self._update_spectrum(display_data[-point_num:, 0], sample_rate,
                                     psd_mode=False, data_type='short')  # psd_mode ignored for raw data

    def _update_monitor_display(self, data: np.ndarray, channel_num: int):
        """Update monitor plot"""
        if not self.monitor_enable_check.isChecked():
            return

        point_num = self._get_effective_phase_point_count()

        if channel_num == 1:
            self.monitor_curves[0].setData(data[:point_num])
            self.monitor_curves[1].setData([])
        else:
            if len(data.shape) == 1:
                data = data.reshape(-1, channel_num)

            for ch in range(min(channel_num, 2)):
                self.monitor_curves[ch].setData(data[:point_num, ch])

    def _update_spectrum(self, data: np.ndarray, sample_rate: float, psd_mode: bool, data_type: str):
        """Update spectrum plot"""
        try:
            freq, spectrum, df = self.spectrum_analyzer.update(
                data, sample_rate, psd_mode, data_type
            )

            # Linear axes: Y is already in dB, X is linear frequency
            self.plot_widget_2.setLogMode(x=False, y=False)

            # Filter frequency range:
            # Phase data starts from 1Hz (exclude DC) since phase is relative.
            # Raw IQ data includes 0Hz.
            nyquist = sample_rate / 2
            if data_type == 'int':  # Phase data
                # Phase: X-axis [1, fs/2], skip DC component
                valid_indices = (freq >= 1.0) & (freq <= nyquist)
            else:  # Raw IQ data
                # Raw data: include 0Hz (DC)
                valid_indices = (freq >= 0) & (freq <= nyquist)

            freq_filtered = freq[valid_indices]
            spectrum_filtered = spectrum[valid_indices]

            if len(freq_filtered) > 0:
                # Frequency unit: phase data in Hz, raw data in MHz
                if data_type == 'int':  # Phase data: Hz range (scan rate based)
                    freq_display = freq_filtered
                else:  # Raw data: convert Hz to MHz (high-speed ADC sampling)
                    freq_display = freq_filtered / 1e6

                self.spectrum_curve.setData(freq_display, spectrum_filtered)

                # Set X-axis range
                if not self._plot_zoom_locked.get("plot2", False):
                    spectrum_view_box = self.plot_widget_2.getViewBox()
                    spectrum_view_box.enableAutoRange(y=True)
                    if data_type == 'int':  # Phase data: explicit range [1, fs/2]
                        nyquist_display = nyquist
                        spectrum_view_box.enableAutoRange(x=False)
                        self.plot_widget_2.setXRange(1.0, nyquist_display, padding=0.02)
                    else:  # Raw data: auto range
                        spectrum_view_box.enableAutoRange(x=True)

                # Set axis labels with explicit unit text (bypasses pyqtgraph auto-scaling)
                if data_type == 'int':  # Phase data
                    self.plot_widget_2.setLabel('bottom', 'Frequency (Hz)',
                                              **{'font-family': 'Times New Roman', 'font-size': '8pt'})
                else:  # Raw data
                    self.plot_widget_2.setLabel('bottom', 'Frequency (MHz)',
                                              **{'font-family': 'Times New Roman', 'font-size': '8pt'})

            # Y-axis label: Raw data = Power (dB), Phase data = PSD (dB)
            if data_type == 'int':  # Phase data: Always PSD
                self.plot_widget_2.setLabel('left', 'PSD (dB)',
                                          **{'font-family': 'Times New Roman', 'font-size': '8pt'})
            else:  # Raw data: Always Power Spectrum
                self.plot_widget_2.setLabel('left', 'Power (dB)',
                                          **{'font-family': 'Times New Roman', 'font-size': '8pt'})
        except Exception as e:
            log.warning(f"Spectrum update error: {e}")

    def _select_latest_display_frames(
        self,
        data: np.ndarray,
        points_per_frame: int,
        channel_num: int,
        target_frames: int,
    ) -> tuple[np.ndarray, int]:
        """Extract the most recent frames needed for one GUI update."""
        if points_per_frame <= 0 or target_frames <= 0:
            return np.asarray(data), 0

        if channel_num == 1:
            flat = np.asarray(data).reshape(-1)
            available_frames = flat.size // points_per_frame
            frame_num = min(target_frames, available_frames)
            if frame_num <= 0:
                return flat[:0], 0
            keep_points = frame_num * points_per_frame
            return flat[-keep_points:], frame_num

        matrix = np.asarray(data)
        if matrix.ndim == 1:
            matrix = matrix.reshape(-1, channel_num)

        available_frames = matrix.shape[0] // points_per_frame
        frame_num = min(target_frames, available_frames)
        if frame_num <= 0:
            return matrix[:0], 0
        keep_rows = frame_num * points_per_frame
        return matrix[-keep_rows:, :], frame_num

    # ----- STATUS MONITORING -----

    def _update_status(self):
        """Periodic status update"""
        try:
            # Check if widgets still exist (window might be closing)
            if not hasattr(self, 'frames_label'):
                return

            self._update_calculated_values()

            # Update acquisition status
            if self.acq_thread is not None and self.acq_thread.is_running:
                frames = self.acq_thread.frames_acquired
                if hasattr(self, 'frames_label'):
                    self.frames_label.setText(f"Frames: {frames}")

                # Update buffer status with estimated values
                if hasattr(self.acq_thread, '_current_polling_interval'):
                    polling_ms = self.acq_thread._current_polling_interval * 1000
                    if hasattr(self, 'polling_label'):
                        self.polling_label.setText(f"Poll: {polling_ms:.1f}ms")

                # Update buffer status displays (with estimated values)
                self._update_buffer_status()
                self._check_acquisition_stall()
            else:
                if hasattr(self, 'frames_label'):
                    self.frames_label.setText("Frames: 0")
                if hasattr(self, 'polling_label'):
                    self.polling_label.setText("Poll: --ms")

            # Update file size estimates
            self._update_file_estimates()
            self._log_acquisition_diagnostics("periodic")
            self._log_storage_queue_status()

        except Exception as e:
            log.warning(f"Error in _update_status: {e}")

    def _check_acquisition_stall(self):
        """Detect acquisition-thread read stalls, independent of GUI callback timing."""
        if self._recovery_in_progress:
            return
        if self.acq_thread is None or not self.acq_thread.is_running:
            return

        now = time.time()
        if now - self._last_recovery_time < ACQ_RECOVERY_COOLDOWN_S:
            return

        snapshot = self.acq_thread.get_diagnostics_snapshot()
        silent_s = snapshot["last_successful_read_age_s"]
        if silent_s < ACQ_STALL_TIMEOUT_S:
            return

        self._recovery_in_progress = True
        self._last_recovery_time = now
        self._log_acquisition_diagnostics("stall_detected", force=True)
        log.error(
            f"Acquisition stall detected: no successful reads for {silent_s:.1f}s. "
            "Triggering auto-recovery (stop/start)."
        )

        try:
            self._on_stop()
        except Exception as e:
            log.error(f"Auto-recovery stop failed: {e}")

        QTimer.singleShot(800, self._recover_start)

    def _recover_start(self):
        """Second stage of auto-recovery: restart acquisition."""
        try:
            self._on_start()
            log.info("Auto-recovery restart issued")
        except Exception as e:
            log.error(f"Auto-recovery start failed: {e}")
        finally:
            self._recovery_in_progress = False

    def _log_storage_queue_status(self):
        """Periodically log storage queue occupancy for field diagnostics."""
        if not self.data_saver or not self.data_saver.is_running:
            return

        now = time.time()
        if now - self._last_storage_queue_log_time < 5.0:
            return

        queue_size = self.data_saver.queue_size
        queue_max = getattr(self.data_saver, 'buffer_size', OPTIMIZED_BUFFER_SIZES['storage_queue_frames'])
        dropped = self.data_saver.dropped_blocks
        log.info(f"Storage queue: {queue_size}/{queue_max}, dropped={dropped}")
        self._last_storage_queue_log_time = now

    def _log_acquisition_diagnostics(self, reason: str, force: bool = False):
        """Emit a consolidated acquisition snapshot for field diagnostics."""
        if self.acq_thread is None:
            return
        if not force and not self.acq_thread.is_running:
            return

        now = time.time()
        if not force and now - self._last_acq_snapshot_log_time < 5.0:
            return

        snapshot = self.acq_thread.get_diagnostics_snapshot()
        parts = [
            f"reason={reason}",
            f"stage={snapshot['current_stage']}",
            f"stage_ms={snapshot['stage_elapsed_ms']:.1f}",
            f"loop={snapshot['loop_count']}",
            f"frames={snapshot['frames_acquired']}",
            f"buffer={snapshot['last_buffer_points']}/{snapshot['last_expected_points']}",
            f"waits={snapshot['last_wait_iterations']}",
            f"query_ms={snapshot['last_query_ms']:.1f}",
            f"read_ms={snapshot['last_read_ms']:.1f}",
            f"read_age_s={snapshot['last_successful_read_age_s']:.1f}",
            f"monitor_ms={snapshot['last_monitor_read_ms']:.1f}",
            f"block_mb={snapshot['last_block_bytes'] / 1024 / 1024:.2f}",
            f"poll_ms={snapshot['polling_interval_ms']:.1f}",
            f"emit_phase={snapshot['phase_emit_count']}",
            f"emit_raw={snapshot['raw_emit_count']}",
            f"gui_skips={snapshot['gui_skip_count']}",
        ]
        detail = snapshot.get("current_stage_detail")
        if detail:
            parts.append(f"detail={detail}")

        if self.data_saver is not None and hasattr(self.data_saver, "get_diagnostics_snapshot"):
            saver = self.data_saver.get_diagnostics_snapshot()
            parts.extend([
                f"save_queue={saver['queue_size']}/{saver['buffer_size']}",
                f"save_max_queue={saver['max_queue_size_seen']}",
                f"save_dropped={saver['dropped_blocks']}",
                f"save_written={saver['blocks_written']}",
                f"save_last_write_ms={saver['last_write_ms']:.1f}",
            ])

        log.info("Acq snapshot: " + ", ".join(parts))
        self._last_acq_snapshot_log_time = now

    def _update_calculated_values(self):
        """Update calculated display values"""
        point_num = self.point_num_spin.value()
        scan_rate = self.scan_rate_spin.value()
        channel_num = self.channel_combo.currentData() or 1
        data_source = self.data_source_combo.currentData() or DataSource.PHASE
        data_rate = self.data_rate_combo.currentData() or 1
        rate2phase = self.rate2phase_combo.currentData() or 4

        # Data rate
        data_rate_mbps = calculate_data_rate_mbps(scan_rate, point_num, channel_num)
        self._data_rate_label.setText(f"Data Rate: {data_rate_mbps:.1f} MB/s")

        # Fiber length
        fiber_length = calculate_fiber_length(point_num, data_rate, data_source, rate2phase)
        self._fiber_length_label.setText(f"Fiber Length: {fiber_length:.1f} m")

        # Point num (actual data points after merging)
        if data_source == DataSource.PHASE:
            total_points = calculate_phase_point_num(point_num, self.merge_points_spin.value())
            if channel_num == 1:
                actual_point_num = calculate_cropped_point_count(
                    total_points,
                    self.crop_distance_start_spin.value(),
                    self.crop_distance_end_spin.value(),
                )
            else:
                actual_point_num = total_points
        else:
            actual_point_num = point_num
        self._point_num_label.setText(f"Point num: {actual_point_num}")

    @pyqtSlot(bool)
    def _on_mode_changed(self, checked):
        """Handle mode radio button changes"""
        if checked:  # Only respond to the checked button to avoid duplicate calls
            # 仅更新显示模式参数，避免运行时重新收集全部参数
            try:
                if hasattr(self, 'params') and self.params is not None:
                    # 只更新显示模式相关参数
                    if self.mode_space_radio.isChecked():
                        self.params.display.mode = DisplayMode.SPACE
                        self._set_time_plot_axis('Time (s)', 'time')
                        log.debug("Display mode changed to SPACE")
                    else:
                        self.params.display.mode = DisplayMode.TIME
                        self._set_time_plot_axis('Distance (m)', 'distance')
                        log.debug("Display mode changed to TIME")

                    # Update region index.
                    self.params.display.region_index = self.region_index_spin.value()
                else:
                    log.warning("Params not initialized, mode change ignored")
            except Exception as e:
                log.warning(f"Error updating mode parameters: {e}")

    @pyqtSlot(int)
    def _on_region_changed(self, value):
        """Handle region index changes"""
        try:
            if hasattr(self, 'params') and self.params is not None:
                self.params.display.region_index = value
                log.debug(f"Region index changed to: {value}")
        except Exception as e:
            log.warning(f"Error updating region index: {e}")

    def _on_data_source_changed(self, index: int):
        """Handle data source change"""
        data_source = self.data_source_combo.currentData()
        is_phase = (data_source == DataSource.PHASE)

        self._sync_display_control_states()

        # Update analysis type label
        if is_phase:
            self.analysis_type_label.setText("PSD")
            self.analysis_type_label.setToolTip("Phase data: PSD analysis using scipy.welch")
        else:
            self.analysis_type_label.setText("Power")
            self.analysis_type_label.setToolTip("Raw data: Power spectrum analysis")

        if not is_phase:
            self.mode_time_radio.setChecked(True)

        self._update_phase_crop_controls()
        self._update_calculated_values()

    def _on_channel_changed(self, index: int):
        """Handle channel count change"""
        self._update_phase_crop_controls()
        self._update_calculated_values()

    def _update_phase_crop_controls(self):
        """Enable crop controls only when they are applicable."""
        enabled = (
            self.data_source_combo.currentData() == DataSource.PHASE
            and self.channel_combo.currentData() == 1
        )
        self.crop_distance_start_spin.setEnabled(enabled)
        self.crop_distance_end_spin.setEnabled(enabled)

    def _browse_save_path(self):
        """Open file dialog to select save path"""
        path = QFileDialog.getExistingDirectory(self, "Select Save Directory", self.save_path_edit.text())
        if path:
            self.save_path_edit.setText(path)

    # ----- APPLICATION LIFECYCLE -----

    def closeEvent(self, event):
        """Handle window close - must release hardware and threads gracefully"""
        log.info("Window closing...")

        # Stop all timers first to prevent interference
        log.debug("Stopping timers...")
        if hasattr(self, '_status_timer'):
            self._status_timer.stop()
        if hasattr(self, '_system_timer'):
            self._system_timer.stop()
        if hasattr(self, '_display_timer'):
            self._display_timer.stop()

        self._save_local_params()

        # Stop acquisition (request thread stop -> stop hardware -> wait thread)
        if self.acq_thread is not None and self.acq_thread.isRunning():
            log.debug("Requesting acquisition thread stop...")
            self.acq_thread.stop()

            if not self.simulation_mode and self.api is not None:
                log.debug("Stopping device during close...")
                try:
                    self.api.stop()
                except Exception as e:
                    log.warning(f"Error stopping device during close: {e}")

            if not self.acq_thread.wait_until_stopped(5000):
                log.error("Acquisition thread still running during close; continue shutdown without force terminate")
            self.acq_thread.set_full_data_handler(None)
            self.acq_thread.clear_latest_display_data()

        # Stop data saver
        if self.data_saver is not None:
            log.debug("Stopping data saver...")
            try:
                self.data_saver.stop()
            except Exception as e:
                log.warning(f"Error stopping data saver: {e}")

        try:
            self.tcp_tab3_manager.shutdown()
        except Exception as e:
            log.warning(f"Error stopping TCP Tab3 manager: {e}")

        # Close device
        if self.api is not None:
            log.debug("Closing device...")
            try:
                self.api.close()
            except Exception as e:
                log.warning(f"Error closing device: {e}")

        log.info("Window closed")
        event.accept()

    def _update_file_estimates(self):
        """Update file size and duration estimates"""
        try:
            frames_per_file = self.frames_per_file_spin.value()
            frame_load_num = self.frame_load_num_spin.value()
            scan_rate = self.scan_rate_spin.value()
            point_num = self.point_num_spin.value()
            merge_points = self.merge_points_spin.value()
            channel_num = self.channel_combo.currentData()
            data_source = self.data_source_combo.currentData() or DataSource.PHASE

            if data_source == DataSource.PHASE and channel_num == 1:
                total_points = calculate_phase_point_num(point_num, merge_points)
                points_per_frame = calculate_cropped_point_count(
                    total_points,
                    self.crop_distance_start_spin.value(),
                    self.crop_distance_end_spin.value(),
                )
            elif data_source == DataSource.PHASE:
                points_per_frame = calculate_phase_point_num(point_num, merge_points)
            else:
                points_per_frame = point_num

            # One saved block corresponds to one acquisition callback.
            block_size_mb = points_per_frame * max(1, frame_load_num) * channel_num * 4 / (1024 * 1024)
            file_size_mb = block_size_mb * frames_per_file

            # Update label
            self.file_size_label.setText(f"~{file_size_mb:.1f}MB/file")

        except Exception as e:
            log.warning(f"Error updating file estimates: {e}")
            self.file_size_label.setText("~-- MB/file")

    def _on_time_space_params_changed(self):
        """Handle time-space plot parameters change"""
        # Update the main parameters with current time-space values
        try:
            if self.time_space_widget is not None:
                self.params = self._collect_params()
                log.debug("Time-space parameters updated")
        except Exception as e:
            log.warning(f"Error updating time-space parameters: {e}")

    @pyqtSlot(int)
    def _on_point_count_changed(self, point_count: int):
        """Handle actual data point count change from time-space widget"""
        try:
            self._point_num_label.setText(f"Point num: {point_count}")
            log.debug(f"Updated point count display: {point_count}")
        except Exception as e:
            log.warning(f"Error updating point count display: {e}")

    @pyqtSlot(bool)
    def _on_plot_state_changed(self, enabled: bool):
        """Handle time-space plot button state changes."""
        try:
            log.info(f"Time-space plot state changed: {'Enabled' if enabled else 'Disabled'}")
            # 可在此扩展其他响应逻辑，例如更新状态栏
        except Exception as e:
            log.warning(f"Error handling plot state change: {e}")

    def _update_system_status(self):
        """Update system monitoring information (CPU, disk, etc.)"""
        try:
            current_time = time.time()
            if current_time - self._last_system_update < MONITOR_UPDATE_INTERVALS['system_status_s']:
                return

            self._last_system_update = current_time

            # Update CPU usage (non-blocking version)
            # Use interval=None for non-blocking call (returns value from last call)
            self._cpu_percent = psutil.cpu_percent(interval=None)
            if hasattr(self, 'cpu_label'):  # Check if widget still exists
                self.cpu_label.setText(f"CPU: {self._cpu_percent:.1f}%")

            # Update disk space for save path
            if self.data_saver and self.data_saver.is_running:
                save_path = self.save_path_edit.text()
                if os.path.exists(save_path):
                    _, _, free_bytes = shutil.disk_usage(save_path)
                    self._disk_free_gb = free_bytes / (1024**3)
                    if hasattr(self, 'disk_label'):  # Check if widget still exists
                        self.disk_label.setText(f"Disk: {self._disk_free_gb:.1f}GB free")

            # Update polling interval display (if acquisition is running)
            if self.acq_thread and self.acq_thread.is_running:
                polling_ms = getattr(self.acq_thread, '_current_polling_interval', 0.001) * 1000
                if hasattr(self, 'polling_label'):  # Check if widget still exists
                    self.polling_label.setText(f"Poll: {polling_ms:.1f}ms")

        except Exception as e:
            log.warning(f"Error updating system status: {e}")

    def _update_buffer_status(self, hw_count=0, hw_max=50, signal_count=0, signal_max=20,
                            storage_count=0, storage_max=200, display_count=0, display_max=30):
        """Update buffer status displays"""
        try:
            # Update hardware buffer
            hw_percent = min(100, int(hw_count / hw_max * 100)) if hw_max > 0 else 0
            self.hw_buffer_bar.setValue(hw_percent)
            self.hw_buffer_label.setText(f"HW: {hw_count}/{hw_max}")
            self._set_progress_bar_color(self.hw_buffer_bar, hw_percent)

            # Update signal queue
            signal_percent = min(100, int(signal_count / signal_max * 100)) if signal_max > 0 else 0
            self.signal_queue_bar.setValue(signal_percent)
            self.signal_queue_label.setText(f"SIG: {signal_count}/{signal_max}")
            self._set_progress_bar_color(self.signal_queue_bar, signal_percent)

            # Update storage queue
            storage_percent = min(100, int(storage_count / storage_max * 100)) if storage_max > 0 else 0
            self.storage_queue_bar.setValue(storage_percent)
            self.storage_queue_label.setText(f"STO: {storage_count}/{storage_max}")
            self._set_progress_bar_color(self.storage_queue_bar, storage_percent)

        except Exception as e:
            log.warning(f"Error updating buffer status: {e}")

    def _set_progress_bar_color(self, progress_bar: QProgressBar, percentage: int):
        """Set progress bar color based on usage percentage"""
        if percentage >= 90:
            progress_bar.setStyleSheet("QProgressBar::chunk { background-color: red; }")
        elif percentage >= 70:
            progress_bar.setStyleSheet("QProgressBar::chunk { background-color: orange; }")
        else:
            progress_bar.setStyleSheet("QProgressBar::chunk { background-color: green; }")
