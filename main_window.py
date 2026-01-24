"""
PCIe-7821 Main Window GUI
PyQt5-based GUI with real-time waveform display
"""

import sys
import os
import numpy as np
from typing import Optional
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox, QPushButton, QCheckBox,
    QRadioButton, QButtonGroup, QSpinBox, QDoubleSpinBox, QFileDialog,
    QMessageBox, QStatusBar, QSplitter, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QPalette
import pyqtgraph as pg

from config import (
    AllParams, BasicParams, UploadParams, PhaseDemodParams, DisplayParams, SaveParams,
    ClockSource, TriggerDirection, DataSource, DisplayMode,
    CHANNEL_NUM_OPTIONS, DATA_SOURCE_OPTIONS, DATA_RATE_OPTIONS, RATE2PHASE_OPTIONS,
    validate_point_num, calculate_fiber_length, calculate_data_rate_mbps
)
from pcie7821_api import PCIe7821API, PCIe7821Error
from acquisition_thread import AcquisitionThread, SimulatedAcquisitionThread
from data_saver import DataSaver
from spectrum_analyzer import RealTimeSpectrumAnalyzer


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self, simulation_mode: bool = False):
        """
        Initialize main window.

        Args:
            simulation_mode: If True, use simulated data without hardware
        """
        super().__init__()
        self.simulation_mode = simulation_mode

        # Initialize components
        self.api: Optional[PCIe7821API] = None
        self.acq_thread: Optional[AcquisitionThread] = None
        self.data_saver: Optional[DataSaver] = None
        self.spectrum_analyzer = RealTimeSpectrumAnalyzer()

        # Parameters
        self.params = AllParams()

        # Data storage for display
        self._phase_data_buffer = []
        self._raw_data_buffer = []
        self._current_monitor_data = None

        # Setup UI
        self.setWindowTitle("PCIe-7821 DAS Acquisition Software")
        self.setMinimumSize(1400, 900)

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

    def _setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        # Left panel - Parameters
        left_panel = self._create_parameter_panel()
        left_panel.setMaximumWidth(320)
        left_panel.setMinimumWidth(280)

        # Right panel - Plots and controls
        right_panel = self._create_plot_panel()

        # Add to main layout
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 1100])

        main_layout.addWidget(splitter)

        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self._device_status_label = QLabel("Device: Disconnected")
        self._data_rate_label = QLabel("Data Rate: 0 MB/s")
        self._fiber_length_label = QLabel("Fiber Length: 0 m")
        self.statusBar.addWidget(self._device_status_label)
        self.statusBar.addWidget(self._data_rate_label)
        self.statusBar.addWidget(self._fiber_length_label)

    def _create_parameter_panel(self) -> QWidget:
        """Create the parameter configuration panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        # Basic Parameters Group
        basic_group = QGroupBox("Basic Parameters")
        basic_layout = QGridLayout(basic_group)

        # Clock Source
        basic_layout.addWidget(QLabel("Clock Source:"), 0, 0)
        self.clk_internal_radio = QRadioButton("Internal")
        self.clk_external_radio = QRadioButton("External")
        self.clk_internal_radio.setChecked(True)
        clk_group = QButtonGroup(self)
        clk_group.addButton(self.clk_internal_radio, 0)
        clk_group.addButton(self.clk_external_radio, 1)
        clk_layout = QHBoxLayout()
        clk_layout.addWidget(self.clk_internal_radio)
        clk_layout.addWidget(self.clk_external_radio)
        basic_layout.addLayout(clk_layout, 0, 1)

        # Trigger Direction
        basic_layout.addWidget(QLabel("Trigger Dir:"), 1, 0)
        self.trig_in_radio = QRadioButton("Input")
        self.trig_out_radio = QRadioButton("Output")
        self.trig_out_radio.setChecked(True)
        trig_group = QButtonGroup(self)
        trig_group.addButton(self.trig_in_radio, 0)
        trig_group.addButton(self.trig_out_radio, 1)
        trig_layout = QHBoxLayout()
        trig_layout.addWidget(self.trig_in_radio)
        trig_layout.addWidget(self.trig_out_radio)
        basic_layout.addLayout(trig_layout, 1, 1)

        # Scan Rate
        basic_layout.addWidget(QLabel("Scan Rate (Hz):"), 2, 0)
        self.scan_rate_spin = QSpinBox()
        self.scan_rate_spin.setRange(1, 100000)
        self.scan_rate_spin.setValue(2000)
        basic_layout.addWidget(self.scan_rate_spin, 2, 1)

        # Pulse Width
        basic_layout.addWidget(QLabel("Pulse Width (ns):"), 3, 0)
        self.pulse_width_spin = QSpinBox()
        self.pulse_width_spin.setRange(10, 1000)
        self.pulse_width_spin.setValue(120)
        basic_layout.addWidget(self.pulse_width_spin, 3, 1)

        # Points per Scan
        basic_layout.addWidget(QLabel("Points/Scan:"), 4, 0)
        self.point_num_spin = QSpinBox()
        self.point_num_spin.setRange(512, 262144)
        self.point_num_spin.setValue(20480)
        self.point_num_spin.setSingleStep(512)
        basic_layout.addWidget(self.point_num_spin, 4, 1)

        # Bypass Points
        basic_layout.addWidget(QLabel("Bypass Points:"), 5, 0)
        self.bypass_spin = QSpinBox()
        self.bypass_spin.setRange(0, 65535)
        self.bypass_spin.setValue(0)
        basic_layout.addWidget(self.bypass_spin, 5, 1)

        # Center Frequency
        basic_layout.addWidget(QLabel("Center Freq (MHz):"), 6, 0)
        self.center_freq_spin = QSpinBox()
        self.center_freq_spin.setRange(50, 500)
        self.center_freq_spin.setValue(200)
        basic_layout.addWidget(self.center_freq_spin, 6, 1)

        layout.addWidget(basic_group)

        # Upload Parameters Group
        upload_group = QGroupBox("Upload Parameters")
        upload_layout = QGridLayout(upload_group)

        # Channel Number
        upload_layout.addWidget(QLabel("Channels:"), 0, 0)
        self.channel_combo = QComboBox()
        for label, value in CHANNEL_NUM_OPTIONS:
            self.channel_combo.addItem(label, value)
        upload_layout.addWidget(self.channel_combo, 0, 1)

        # Data Source
        upload_layout.addWidget(QLabel("Data Source:"), 1, 0)
        self.data_source_combo = QComboBox()
        for label, value in DATA_SOURCE_OPTIONS:
            self.data_source_combo.addItem(label, value)
        self.data_source_combo.setCurrentIndex(4)  # Default to Phase
        upload_layout.addWidget(self.data_source_combo, 1, 1)

        # Data Rate
        upload_layout.addWidget(QLabel("Data Rate:"), 2, 0)
        self.data_rate_combo = QComboBox()
        for label, value in DATA_RATE_OPTIONS:
            self.data_rate_combo.addItem(label, value)
        upload_layout.addWidget(self.data_rate_combo, 2, 1)

        layout.addWidget(upload_group)

        # Phase Demodulation Parameters Group
        phase_group = QGroupBox("Phase Demod Parameters")
        phase_layout = QGridLayout(phase_group)

        # Rate2Phase
        phase_layout.addWidget(QLabel("Rate2Phase:"), 0, 0)
        self.rate2phase_combo = QComboBox()
        for label, value in RATE2PHASE_OPTIONS:
            self.rate2phase_combo.addItem(label, value)
        self.rate2phase_combo.setCurrentIndex(2)  # Default 4
        phase_layout.addWidget(self.rate2phase_combo, 0, 1)

        # Space Average
        phase_layout.addWidget(QLabel("Space Avg:"), 1, 0)
        self.space_avg_spin = QSpinBox()
        self.space_avg_spin.setRange(1, 64)
        self.space_avg_spin.setValue(8)
        phase_layout.addWidget(self.space_avg_spin, 1, 1)

        # Merge Points
        phase_layout.addWidget(QLabel("Merge Points:"), 2, 0)
        self.merge_points_spin = QSpinBox()
        self.merge_points_spin.setRange(1, 16)
        self.merge_points_spin.setValue(4)
        phase_layout.addWidget(self.merge_points_spin, 2, 1)

        # Diff Order
        phase_layout.addWidget(QLabel("Diff Order:"), 3, 0)
        self.diff_order_spin = QSpinBox()
        self.diff_order_spin.setRange(0, 4)
        self.diff_order_spin.setValue(1)
        phase_layout.addWidget(self.diff_order_spin, 3, 1)

        # Detrend BW
        phase_layout.addWidget(QLabel("Detrend BW (Hz):"), 4, 0)
        self.detrend_bw_spin = QDoubleSpinBox()
        self.detrend_bw_spin.setRange(0.0, 100.0)
        self.detrend_bw_spin.setValue(0.5)
        self.detrend_bw_spin.setSingleStep(0.1)
        phase_layout.addWidget(self.detrend_bw_spin, 4, 1)

        # Polarization Diversity
        self.polar_div_check = QCheckBox("Polarization Diversity")
        phase_layout.addWidget(self.polar_div_check, 5, 0, 1, 2)

        layout.addWidget(phase_group)

        # Display Control Group
        display_group = QGroupBox("Display Control")
        display_layout = QGridLayout(display_group)

        # Display Mode
        display_layout.addWidget(QLabel("Mode:"), 0, 0)
        self.mode_time_radio = QRadioButton("Time")
        self.mode_space_radio = QRadioButton("Space")
        self.mode_time_radio.setChecked(True)
        mode_group = QButtonGroup(self)
        mode_group.addButton(self.mode_time_radio, 0)
        mode_group.addButton(self.mode_space_radio, 1)
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.mode_time_radio)
        mode_layout.addWidget(self.mode_space_radio)
        display_layout.addLayout(mode_layout, 0, 1)

        # Region Index
        display_layout.addWidget(QLabel("Region Index:"), 1, 0)
        self.region_index_spin = QSpinBox()
        self.region_index_spin.setRange(0, 65535)
        self.region_index_spin.setValue(0)
        display_layout.addWidget(self.region_index_spin, 1, 1)

        # Frame Number
        display_layout.addWidget(QLabel("Frames:"), 2, 0)
        self.frame_num_spin = QSpinBox()
        self.frame_num_spin.setRange(1, 1000)
        self.frame_num_spin.setValue(20)
        display_layout.addWidget(self.frame_num_spin, 2, 1)

        # Spectrum Enable
        self.spectrum_enable_check = QCheckBox("Spectrum Enable")
        self.spectrum_enable_check.setChecked(True)
        display_layout.addWidget(self.spectrum_enable_check, 3, 0)

        # PSD Mode
        self.psd_check = QCheckBox("PSD Mode")
        display_layout.addWidget(self.psd_check, 3, 1)

        layout.addWidget(display_group)

        # Save Control Group
        save_group = QGroupBox("Data Save")
        save_layout = QGridLayout(save_group)

        # Save Enable
        self.save_enable_check = QCheckBox("Enable Save")
        save_layout.addWidget(self.save_enable_check, 0, 0)

        # Save Path
        save_layout.addWidget(QLabel("Path:"), 1, 0)
        path_layout = QHBoxLayout()
        self.save_path_edit = QLineEdit("save_data")
        self.browse_btn = QPushButton("...")
        self.browse_btn.setMaximumWidth(30)
        self.browse_btn.clicked.connect(self._browse_save_path)
        path_layout.addWidget(self.save_path_edit)
        path_layout.addWidget(self.browse_btn)
        save_layout.addLayout(path_layout, 1, 1)

        layout.addWidget(save_group)

        # Control Buttons
        control_layout = QHBoxLayout()
        self.start_btn = QPushButton("START")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.start_btn.setMinimumHeight(40)
        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        layout.addLayout(control_layout)

        layout.addStretch()

        return panel

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

        # Configure plot styles
        for pw in [self.plot_widget_1, self.plot_widget_2, self.plot_widget_3]:
            pw.setBackground('k')
            pw.showGrid(x=True, y=True, alpha=0.3)
            pw.setMinimumHeight(200)

        # Plot 1 - Time domain
        self.plot_widget_1.setLabel('left', 'Amplitude')
        self.plot_widget_1.setLabel('bottom', 'Sample')
        self.plot_curve_1 = []

        # Plot 2 - Spectrum
        self.plot_widget_2.setLabel('left', 'Power', units='dBm')
        self.plot_widget_2.setLabel('bottom', 'Frequency', units='Hz')
        self.spectrum_curve = self.plot_widget_2.plot(pen=pg.mkPen('y', width=1))

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
        colors = ['g', 'c', 'r', 'b']

        # Time domain curves (up to 4 frames)
        for i in range(4):
            curve = self.plot_widget_1.plot(pen=pg.mkPen(colors[i], width=1))
            self.plot_curve_1.append(curve)

        # Monitor curves (up to 2 channels)
        for i in range(2):
            curve = self.plot_widget_3.plot(pen=pg.mkPen(colors[i], width=1))
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
        try:
            self.api = PCIe7821API()
            result = self.api.open()
            if result == 0:
                self._update_device_status(True)
            else:
                self._update_device_status(False)
                QMessageBox.warning(self, "Warning", f"Failed to open device: error code {result}")
        except FileNotFoundError as e:
            self._update_device_status(False)
            QMessageBox.warning(self, "Warning", f"DLL not found: {e}")
        except Exception as e:
            self._update_device_status(False)
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
        if params.upload.data_source < DataSource.PHASE and params.upload.channel_num == 4:
            return False, "Raw data source does not support 4 channels"

        return True, ""

    def _configure_device(self, params: AllParams) -> bool:
        """Configure device with parameters"""
        if self.api is None:
            return False

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

            return True

        except PCIe7821Error as e:
            QMessageBox.critical(self, "Error", f"Failed to configure device: {e}")
            return False

    @pyqtSlot()
    def _on_start(self):
        """Handle start button click"""
        # Collect and validate parameters
        params = self._collect_params()
        valid, msg = self._validate_params(params)
        if not valid:
            QMessageBox.warning(self, "Invalid Parameters", msg)
            return

        self.params = params

        # Configure device (if not simulation mode)
        if not self.simulation_mode:
            if not self._configure_device(params):
                return

            # Start device
            try:
                self.api.start()
            except PCIe7821Error as e:
                QMessageBox.critical(self, "Error", f"Failed to start acquisition: {e}")
                return

        # Start data saver if enabled
        if params.save.enable:
            self.data_saver = DataSaver(params.save.path)
            filename = self.data_saver.start()
            self.save_status_label.setText(f"Save: {filename}")
        else:
            self.save_status_label.setText("Save: Off")

        # Create and start acquisition thread
        if self.simulation_mode:
            self.acq_thread = SimulatedAcquisitionThread(self)
        else:
            self.acq_thread = AcquisitionThread(self.api, self)

        self.acq_thread.configure(params)
        self.acq_thread.phase_data_ready.connect(self._on_phase_data)
        self.acq_thread.data_ready.connect(self._on_raw_data)
        self.acq_thread.monitor_data_ready.connect(self._on_monitor_data)
        self.acq_thread.buffer_status.connect(self._on_buffer_status)
        self.acq_thread.error_occurred.connect(self._on_error)
        self.acq_thread.acquisition_stopped.connect(self._on_acquisition_stopped)

        self.acq_thread.start()

        # Update UI state
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._set_params_enabled(False)

        # Reset spectrum analyzer
        self.spectrum_analyzer.reset()

    @pyqtSlot()
    def _on_stop(self):
        """Handle stop button click"""
        if self.acq_thread is not None:
            self.acq_thread.stop()

        if not self.simulation_mode and self.api is not None:
            try:
                self.api.stop()
            except PCIe7821Error:
                pass

        if self.data_saver is not None:
            self.data_saver.stop()
            self.data_saver = None

        self.save_status_label.setText("Save: Off")

    @pyqtSlot()
    def _on_acquisition_stopped(self):
        """Handle acquisition stopped signal"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
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
        # Save data if enabled
        if self.data_saver is not None and self.data_saver.is_running:
            self.data_saver.save(data)

        # Update display
        self._update_phase_display(data, channel_num)

    @pyqtSlot(np.ndarray, int, int)
    def _on_raw_data(self, data: np.ndarray, data_type: int, channel_num: int):
        """Handle raw data from acquisition thread"""
        # Save data if enabled
        if self.data_saver is not None and self.data_saver.is_running:
            self.data_saver.save(data)

        # Update display
        self._update_raw_display(data, channel_num)

    @pyqtSlot(np.ndarray, int)
    def _on_monitor_data(self, data: np.ndarray, channel_num: int):
        """Handle monitor data from acquisition thread"""
        self._current_monitor_data = data
        self._update_monitor_display(data, channel_num)

    @pyqtSlot(int, int)
    def _on_buffer_status(self, points: int, mb: int):
        """Handle buffer status update"""
        self.buffer_label.setText(f"Buffer: {mb} MB")

    @pyqtSlot(str)
    def _on_error(self, message: str):
        """Handle error from acquisition thread"""
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
                self.plot_widget_2.setLabel('left', 'PSD', units='dBm/Hz')
            else:
                self.plot_widget_2.setLabel('left', 'Power', units='dBm')
        except Exception as e:
            print(f"Spectrum error: {e}")

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
        # Stop acquisition
        if self.acq_thread is not None and self.acq_thread.isRunning():
            self.acq_thread.stop()
            self.acq_thread.wait(2000)

        # Stop data saver
        if self.data_saver is not None:
            self.data_saver.stop()

        # Close device
        if self.api is not None:
            try:
                self.api.close()
            except:
                pass

        event.accept()
