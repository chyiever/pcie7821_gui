"""
PCIe-7821 Main Window GUI
PyQt5-based GUI with real-time waveform display
"""

import sys
import os
import time
import numpy as np
from typing import Optional
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox, QPushButton, QCheckBox,
    QRadioButton, QButtonGroup, QSpinBox, QDoubleSpinBox, QFileDialog,
    QMessageBox, QStatusBar, QSplitter, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QPalette, QPixmap, QFontDatabase
import pyqtgraph as pg

from config import (
    AllParams, BasicParams, UploadParams, PhaseDemodParams, DisplayParams, SaveParams,
    ClockSource, TriggerDirection, DataSource, DisplayMode,
    CHANNEL_NUM_OPTIONS, DATA_SOURCE_OPTIONS, DATA_RATE_OPTIONS, RATE2PHASE_OPTIONS,
    validate_point_num, calculate_fiber_length, calculate_data_rate_mbps
)
from pcie7821_api import PCIe7821API, PCIe7821Error
from acquisition_thread import AcquisitionThread, SimulatedAcquisitionThread
from data_saver import TimedFileSaver
from spectrum_analyzer import RealTimeSpectrumAnalyzer
from logger import get_logger

# Module logger
log = get_logger("gui")


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
        self.data_saver: Optional[TimedFileSaver] = None
        self.spectrum_analyzer = RealTimeSpectrumAnalyzer()

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

        # Setup UI
        self.setWindowTitle("eDAS-gh26.1.24")
        self.setMinimumSize(1400, 900)

        log.debug("Setting up UI...")
        self._setup_ui()
        self._setup_plots()
        self._connect_signals()

        # Status timer
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(500)

        # Initialize device
        if not simulation_mode:
            self._init_device()
        else:
            self._update_device_status(True)

        log.info("MainWindow initialized")

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
        self.statusBar.addWidget(self._device_status_label)
        self.statusBar.addWidget(self._data_rate_label)
        self.statusBar.addWidget(self._fiber_length_label)

    def _create_header(self) -> QWidget:
        """Create header with logo and title"""
        header = QFrame()
        header.setFrameStyle(QFrame.StyledPanel)
        header.setFixedHeight(50)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 3, 10, 3)

        # Logo
        logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # Scale logo to fit header height
            scaled_pixmap = pixmap.scaledToHeight(40, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        else:
            logo_label.setText("[LOGO]")
            log.warning(f"Logo file not found: {logo_path}")

        layout.addWidget(logo_label)

        # Title - 黑体加粗28号字
        title_label = QLabel("分布式光纤传感系统（eDAS）")
        title_font = QFont("SimHei", 28, QFont.Bold)  # 黑体
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
                font-family: 'SimHei', 'Microsoft YaHei';
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
        self.scan_rate_spin.setRange(1, 100000)
        self.scan_rate_spin.setValue(2000)
        self.scan_rate_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.scan_rate_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        basic_layout.addWidget(self.scan_rate_spin, 1, 1)

        basic_layout.addWidget(QLabel("Pulse(ns):"), 1, 2)
        self.pulse_width_spin = QSpinBox()
        self.pulse_width_spin.setRange(10, 1000)
        self.pulse_width_spin.setValue(100)
        self.pulse_width_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.pulse_width_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        basic_layout.addWidget(self.pulse_width_spin, 1, 3)

        # Row 2: Points/Scan | Bypass
        basic_layout.addWidget(QLabel("Points:"), 2, 0)
        self.point_num_spin = QSpinBox()
        self.point_num_spin.setRange(512, 262144)
        self.point_num_spin.setValue(20480)
        self.point_num_spin.setSingleStep(512)
        self.point_num_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.point_num_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        basic_layout.addWidget(self.point_num_spin, 2, 1)

        basic_layout.addWidget(QLabel("Bypass:"), 2, 2)
        self.bypass_spin = QSpinBox()
        self.bypass_spin.setRange(0, 65535)
        self.bypass_spin.setValue(60)
        self.bypass_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.bypass_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        basic_layout.addWidget(self.bypass_spin, 2, 3)

        # Row 3: Center Freq (spans full width for clarity)
        basic_layout.addWidget(QLabel("CenterFreq(MHz):"), 3, 0, 1, 2)
        self.center_freq_spin = QSpinBox()
        self.center_freq_spin.setRange(50, 500)
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
        self.detrend_bw_spin.setRange(0.0, 10000.0)
        self.detrend_bw_spin.setValue(0.5)
        self.detrend_bw_spin.setSingleStep(0.1)
        self.detrend_bw_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.detrend_bw_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        phase_layout.addWidget(self.detrend_bw_spin, 2, 1)

        self.polar_div_check = QCheckBox("PolarDiv")
        phase_layout.addWidget(self.polar_div_check, 2, 2, 1, 2)

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
        self.region_index_spin.setRange(0, 65535)
        self.region_index_spin.setValue(0)
        self.region_index_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.region_index_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        display_layout.addWidget(self.region_index_spin, 0, 3)

        # Row 1: Frames | Spectrum/PSD
        display_layout.addWidget(QLabel("Frames:"), 1, 0)
        self.frame_num_spin = QSpinBox()
        self.frame_num_spin.setRange(1, 10000)
        self.frame_num_spin.setValue(1024)
        self.frame_num_spin.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.frame_num_spin.setMaximumWidth(INPUT_MAX_WIDTH)
        display_layout.addWidget(self.frame_num_spin, 1, 1)

        self.spectrum_enable_check = QCheckBox("Spectrum")
        self.spectrum_enable_check.setChecked(True)
        display_layout.addWidget(self.spectrum_enable_check, 1, 2)

        self.psd_check = QCheckBox("PSD")
        display_layout.addWidget(self.psd_check, 1, 3)

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
        self.save_path_edit = QLineEdit("save_data")
        self.save_path_edit.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.browse_btn = QPushButton("...")
        self.browse_btn.setMaximumWidth(25)
        self.browse_btn.setMinimumHeight(INPUT_MIN_HEIGHT)
        self.browse_btn.clicked.connect(self._browse_save_path)
        path_layout.addWidget(self.save_path_edit)
        path_layout.addWidget(self.browse_btn)
        save_layout.addLayout(path_layout, 0, 2, 1, 2)

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
        """Create the plot display panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Configure pyqtgraph
        pg.setConfigOptions(antialias=True)

        # Create plots
        self.plot_widget_1 = pg.PlotWidget(title="Time Domain Data")
        self.plot_widget_2 = pg.PlotWidget(title="FFT Spectrum")
        self.plot_widget_3 = pg.PlotWidget(title="Monitor (Fiber End Detection)")

        # Configure plot styles - white background
        for pw in [self.plot_widget_1, self.plot_widget_2, self.plot_widget_3]:
            pw.setBackground('w')  # White background
            pw.showGrid(x=True, y=True, alpha=0.3)
            pw.setMinimumHeight(200)
            # Set axis and title colors for white background
            pw.getAxis('left').setPen('k')
            pw.getAxis('bottom').setPen('k')
            pw.getAxis('left').setTextPen('k')
            pw.getAxis('bottom').setTextPen('k')

        # Plot 1 - Time domain
        self.plot_widget_1.setLabel('left', 'Amplitude')
        self.plot_widget_1.setLabel('bottom', 'Sample')
        self.plot_curve_1 = []

        # Plot 2 - Spectrum
        self.plot_widget_2.setLabel('left', 'Power', units='dB')
        self.plot_widget_2.setLabel('bottom', 'Frequency', units='Hz')
        self.spectrum_curve = self.plot_widget_2.plot(pen=pg.mkPen('#9467bd', width=1.5))  # Purple

        # Plot 3 - Monitor
        self.plot_widget_3.setLabel('left', 'Amplitude')
        self.plot_widget_3.setLabel('bottom', 'Position')
        self.monitor_curves = []

        # Add plots to layout
        layout.addWidget(self.plot_widget_1, stretch=2)
        layout.addWidget(self.plot_widget_2, stretch=2)
        layout.addWidget(self.plot_widget_3, stretch=1)

        # Status panel
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.StyledPanel)
        status_layout = QHBoxLayout(status_frame)

        self.buffer_label = QLabel("Buffer: 0 MB")
        self.frames_label = QLabel("Frames: 0")
        self.save_status_label = QLabel("Save: Off")

        status_layout.addWidget(self.buffer_label)
        status_layout.addWidget(self.frames_label)
        status_layout.addWidget(self.save_status_label)
        status_layout.addStretch()

        layout.addWidget(status_frame)

        return panel

    def _setup_plots(self):
        """Initialize plot curves"""
        # Colors suitable for white background
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']  # Blue, Orange, Green, Red

        # Time domain curves (up to 4 frames)
        for i in range(4):
            curve = self.plot_widget_1.plot(pen=pg.mkPen(colors[i], width=1.5))
            self.plot_curve_1.append(curve)

        # Monitor curves (up to 2 channels)
        for i in range(2):
            curve = self.plot_widget_3.plot(pen=pg.mkPen(colors[i], width=1.5))
            self.monitor_curves.append(curve)

    def _connect_signals(self):
        """Connect UI signals to slots"""
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)

        self.data_source_combo.currentIndexChanged.connect(self._on_data_source_changed)
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        self.point_num_spin.valueChanged.connect(self._update_calculated_values)
        self.scan_rate_spin.valueChanged.connect(self._update_calculated_values)
        self.merge_points_spin.valueChanged.connect(self._update_calculated_values)
        self.rate2phase_combo.currentIndexChanged.connect(self._update_calculated_values)
        self.data_rate_combo.currentIndexChanged.connect(self._update_calculated_values)

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
        params.phase_demod.diff_order = self.diff_order_spin.value()
        params.phase_demod.detrend_bw = self.detrend_bw_spin.value()
        params.phase_demod.polarization_diversity = self.polar_div_check.isChecked()

        # Display params
        params.display.mode = DisplayMode.SPACE if self.mode_space_radio.isChecked() else DisplayMode.TIME
        params.display.region_index = self.region_index_spin.value()
        params.display.frame_num = self.frame_num_spin.value()
        params.display.spectrum_enable = self.spectrum_enable_check.isChecked()
        params.display.psd_enable = self.psd_check.isChecked()

        # Save params
        params.save.enable = self.save_enable_check.isChecked()
        params.save.path = self.save_path_edit.text()

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

        # Raw data source with 4 channels not supported
        if params.upload.data_source != DataSource.PHASE and params.upload.channel_num == 4:
            return False, "Raw data source does not support 4 channels"

        return True, ""

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
                params.display.frame_num,
                params.phase_demod.merge_point_num,
                params.upload.data_source == DataSource.PHASE
            )

            log.info("Device configured successfully")
            return True

        except PCIe7821Error as e:
            log.error(f"Failed to configure device: {e}")
            QMessageBox.critical(self, "Error", f"Failed to configure device: {e}")
            return False

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
        log.info(f"Parameters: scan_rate={params.basic.scan_rate}, points={params.basic.point_num_per_scan}, "
                 f"channels={params.upload.channel_num}, data_source={params.upload.data_source}, "
                 f"frames={params.display.frame_num}")

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

        # Start data saver if enabled (1 second per file)
        if params.save.enable:
            log.info(f"Starting data saver to {params.save.path}")
            self.data_saver = TimedFileSaver(params.save.path, file_duration_s=1.0)
            filename = self.data_saver.start(scan_rate=params.basic.scan_rate)
            self.save_status_label.setText(f"Save: {filename}")
        else:
            self.save_status_label.setText("Save: Off")

        # Reset counters
        self._data_count = 0
        self._gui_update_count = 0
        self._last_data_time = time.time()

        # Create and start acquisition thread
        log.info("Creating acquisition thread...")
        if self.simulation_mode:
            self.acq_thread = SimulatedAcquisitionThread(self)
        else:
            self.acq_thread = AcquisitionThread(self.api, self)

        self.acq_thread.configure(params)

        # Connect signals with logging
        log.debug("Connecting acquisition thread signals...")
        self.acq_thread.phase_data_ready.connect(self._on_phase_data)
        self.acq_thread.data_ready.connect(self._on_raw_data)
        self.acq_thread.monitor_data_ready.connect(self._on_monitor_data)
        self.acq_thread.buffer_status.connect(self._on_buffer_status)
        self.acq_thread.error_occurred.connect(self._on_error)
        self.acq_thread.acquisition_stopped.connect(self._on_acquisition_stopped)

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

        # Disable stop button immediately to prevent double-clicks
        self.stop_btn.setEnabled(False)
        self.stop_btn.setText("Stopping...")

        if self.acq_thread is not None:
            log.debug("Stopping acquisition thread...")
            self.acq_thread.stop()

        if not self.simulation_mode and self.api is not None:
            log.debug("Stopping device...")
            try:
                self.api.stop()
            except PCIe7821Error as e:
                log.warning(f"Error stopping device: {e}")
            except Exception as e:
                log.warning(f"Unexpected error stopping device: {e}")

        if self.data_saver is not None:
            log.debug("Stopping data saver...")
            try:
                self.data_saver.stop()
            except Exception as e:
                log.warning(f"Error stopping data saver: {e}")
            self.data_saver = None

        self.save_status_label.setText("Save: Off")
        log.info(f"Stopped. Total data callbacks: {self._data_count}, GUI updates: {self._gui_update_count}")

        # Reset stop button text (color will be set by _on_acquisition_stopped)
        self.stop_btn.setText("STOP")

    @pyqtSlot()
    def _on_acquisition_stopped(self):
        """Handle acquisition stopped signal"""
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

    @pyqtSlot(np.ndarray, int)
    def _on_phase_data(self, data: np.ndarray, channel_num: int):
        """Handle phase data from acquisition thread"""
        self._data_count += 1
        start_time = time.perf_counter()

        if self._data_count % 10 == 0:
            log.debug(f"Phase data received #{self._data_count}: shape={data.shape}, channels={channel_num}")

        # Save data if enabled
        if self.data_saver is not None and self.data_saver.is_running:
            self.data_saver.save(data)
            # Update save status periodically
            if self._data_count % 20 == 0:
                self.save_status_label.setText(f"Save: #{self.data_saver.file_no} {self.data_saver.current_filename}")

        # Update display
        try:
            self._update_phase_display(data, channel_num)
            self._gui_update_count += 1
        except Exception as e:
            log.exception(f"Error in _update_phase_display: {e}")

        elapsed = (time.perf_counter() - start_time) * 1000
        if elapsed > 50:
            log.warning(f"Slow _on_phase_data: {elapsed:.1f}ms")

    @pyqtSlot(np.ndarray, int, int)
    def _on_raw_data(self, data: np.ndarray, data_type: int, channel_num: int):
        """Handle raw data from acquisition thread"""
        self._data_count += 1
        start_time = time.perf_counter()

        if self._data_count % 10 == 0:
            log.debug(f"Raw data received #{self._data_count}: shape={data.shape}, type={data_type}, channels={channel_num}")

        # Save data if enabled
        if self.data_saver is not None and self.data_saver.is_running:
            self.data_saver.save(data)
            # Update save status periodically
            if self._data_count % 20 == 0:
                self.save_status_label.setText(f"Save: #{self.data_saver.file_no} {self.data_saver.current_filename}")

        # Update display
        try:
            self._update_raw_display(data, channel_num)
            self._gui_update_count += 1
        except Exception as e:
            log.exception(f"Error in _update_raw_display: {e}")

        elapsed = (time.perf_counter() - start_time) * 1000
        if elapsed > 50:
            log.warning(f"Slow _on_raw_data: {elapsed:.1f}ms")

    @pyqtSlot(np.ndarray, int)
    def _on_monitor_data(self, data: np.ndarray, channel_num: int):
        """Handle monitor data from acquisition thread"""
        self._current_monitor_data = data
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

    def _update_phase_display(self, data: np.ndarray, channel_num: int):
        """Update display for phase data"""
        frame_num = self.params.display.frame_num
        point_num = self.params.basic.point_num_per_scan // self.params.phase_demod.merge_point_num

        if self.params.display.mode == DisplayMode.SPACE:
            # Space mode: extract single region over time
            region_idx = min(self.params.display.region_index, point_num - 1)

            if channel_num == 1:
                # Extract region data across frames
                space_data = []
                for i in range(frame_num):
                    idx = region_idx + point_num * i
                    if idx < len(data):
                        space_data.append(data[idx])

                space_data = np.array(space_data)
                self.plot_curve_1[0].setData(space_data)

                # Clear other curves
                for i in range(1, 4):
                    self.plot_curve_1[i].setData([])

                # Update spectrum
                if self.params.display.spectrum_enable and len(space_data) > 0:
                    self._update_spectrum(space_data, self.params.basic.scan_rate,
                                         self.params.display.psd_enable, 'int')
            else:
                # Multi-channel space mode
                if len(data.shape) == 1:
                    data = data.reshape(-1, channel_num)

                for ch in range(min(channel_num, 2)):
                    space_data = []
                    for i in range(frame_num):
                        idx = region_idx + point_num * i
                        if idx < len(data):
                            space_data.append(data[idx, ch])
                    self.plot_curve_1[ch].setData(np.array(space_data))

                for i in range(channel_num, 4):
                    self.plot_curve_1[i].setData([])

        else:
            # Time mode: show multiple frames overlay
            if channel_num == 1:
                for i in range(min(4, frame_num)):
                    start = i * point_num
                    end = start + point_num
                    if end <= len(data):
                        self.plot_curve_1[i].setData(data[start:end])
                    else:
                        self.plot_curve_1[i].setData([])

                # Spectrum of first frame
                if self.params.display.spectrum_enable and point_num <= len(data):
                    self._update_spectrum(data[:point_num], self.params.basic.scan_rate,
                                         self.params.display.psd_enable, 'int')
            else:
                if len(data.shape) == 1:
                    data = data.reshape(-1, channel_num)

                # Show first frame of each channel
                for ch in range(min(channel_num, 4)):
                    if point_num <= len(data):
                        self.plot_curve_1[ch].setData(data[:point_num, ch])

        # Update frame counter
        if self.acq_thread is not None:
            self.frames_label.setText(f"Frames: {self.acq_thread.frames_acquired}")

    def _update_raw_display(self, data: np.ndarray, channel_num: int):
        """Update display for raw IQ data"""
        point_num = self.params.basic.point_num_per_scan
        frame_num = self.params.display.frame_num

        if channel_num == 1:
            # Show multiple frames
            for i in range(min(4, frame_num)):
                start = i * point_num
                end = start + point_num
                if end <= len(data):
                    self.plot_curve_1[i].setData(data[start:end])
                else:
                    self.plot_curve_1[i].setData([])

            # Spectrum
            if self.params.display.spectrum_enable and point_num <= len(data):
                sample_rate = 1e9 / self.params.upload.data_rate
                self._update_spectrum(data[:point_num], sample_rate,
                                     self.params.display.psd_enable, 'short')
        else:
            if len(data.shape) == 1:
                data = data.reshape(-1, channel_num)

            for ch in range(min(channel_num, 4)):
                if point_num <= len(data):
                    self.plot_curve_1[ch].setData(data[:point_num, ch])

        if self.acq_thread is not None:
            self.frames_label.setText(f"Frames: {self.acq_thread.frames_acquired}")

    def _update_monitor_display(self, data: np.ndarray, channel_num: int):
        """Update monitor plot"""
        point_num = self.params.basic.point_num_per_scan // self.params.phase_demod.merge_point_num

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
            self.spectrum_curve.setData(freq, spectrum)

            # Update axis label
            if psd_mode:
                self.plot_widget_2.setLabel('left', 'PSD', units='dB/Hz')
            else:
                self.plot_widget_2.setLabel('left', 'Power', units='dB')
        except Exception as e:
            log.warning(f"Spectrum update error: {e}")

    def _update_status(self):
        """Periodic status update"""
        self._update_calculated_values()

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

    def _on_data_source_changed(self, index: int):
        """Handle data source change"""
        data_source = self.data_source_combo.currentData()
        is_phase = (data_source == DataSource.PHASE)

        # Enable/disable phase-specific controls
        self.plot_widget_3.setEnabled(is_phase)
        self.mode_space_radio.setEnabled(is_phase)

        if not is_phase:
            self.mode_time_radio.setChecked(True)

        self._update_calculated_values()

    def _on_channel_changed(self, index: int):
        """Handle channel count change"""
        self._update_calculated_values()

    def _browse_save_path(self):
        """Open file dialog to select save path"""
        path = QFileDialog.getExistingDirectory(self, "Select Save Directory", self.save_path_edit.text())
        if path:
            self.save_path_edit.setText(path)

    def closeEvent(self, event):
        """Handle window close"""
        log.info("Window closing...")

        # Stop acquisition
        if self.acq_thread is not None and self.acq_thread.isRunning():
            log.debug("Stopping acquisition thread...")
            self.acq_thread.stop()
            # Give it a reasonable amount of time to stop, then force close
            if not self.acq_thread.wait(2000):
                log.warning("Acquisition thread did not stop gracefully, terminating...")
                self.acq_thread.terminate()
                self.acq_thread.wait(1000)

        # Stop data saver
        if self.data_saver is not None:
            log.debug("Stopping data saver...")
            try:
                self.data_saver.stop()
            except Exception as e:
                log.warning(f"Error stopping data saver: {e}")

        # Close device
        if self.api is not None:
            log.debug("Closing device...")
            try:
                self.api.close()
            except Exception as e:
                log.warning(f"Error closing device: {e}")

        log.info("Window closed")
        event.accept()
