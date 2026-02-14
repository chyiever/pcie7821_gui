"""
PCIe-7821 Spectrum Analyzer Module
FFT-based spectrum analysis with dBm and PSD support
"""

import numpy as np
from typing import Tuple, Optional
from enum import IntEnum


class WindowType(IntEnum):
    """Window function types"""
    RECTANGULAR = 0
    HANNING = 1
    HAMMING = 2
    BLACKMAN = 3
    FLATTOP = 4


class SpectrumAnalyzer:
    """
    FFT spectrum analyzer with power spectrum and PSD support.

    Reference implementation based on original C demo code.
    """

    # Reference impedance for dBm calculation
    IMPEDANCE = 50.0  # Ohms

    def __init__(self, window_type: WindowType = WindowType.HANNING):
        """
        Initialize spectrum analyzer.

        Args:
            window_type: Type of window function to use
        """
        self.window_type = window_type
        self._window_cache = {}

    def _get_window(self, size: int) -> np.ndarray:
        """Get or create cached window function"""
        if size not in self._window_cache:
            if self.window_type == WindowType.RECTANGULAR:
                window = np.ones(size)
            elif self.window_type == WindowType.HANNING:
                window = np.hanning(size)
            elif self.window_type == WindowType.HAMMING:
                window = np.hamming(size)
            elif self.window_type == WindowType.BLACKMAN:
                window = np.blackman(size)
            elif self.window_type == WindowType.FLATTOP:
                # Flat-top window for amplitude accuracy
                a0, a1, a2, a3, a4 = 0.21557895, 0.41663158, 0.277263158, 0.083578947, 0.006947368
                n = np.arange(size)
                window = a0 - a1*np.cos(2*np.pi*n/(size-1)) + a2*np.cos(4*np.pi*n/(size-1)) \
                        - a3*np.cos(6*np.pi*n/(size-1)) + a4*np.cos(8*np.pi*n/(size-1))
            else:
                window = np.hanning(size)

            self._window_cache[size] = window

        return self._window_cache[size]

    def analyze_short(self, data: np.ndarray, sample_rate: float,
                      psd_mode: bool = False) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        Analyze short (int16) data.

        Args:
            data: Input time-domain data (short/int16)
            sample_rate: Sample rate in Hz
            psd_mode: If True, return PSD (dB/Hz); if False, return power spectrum (dB)

        Returns:
            Tuple of (frequency_axis, spectrum_db, frequency_resolution)
        """
        # Convert to normalized voltage (assuming 16-bit ADC with 0.95V range)
        data_v = data.astype(np.float64) * 0.95 / 32767.0
        return self._analyze(data_v, sample_rate, psd_mode)

    def analyze_int(self, data: np.ndarray, sample_rate: float,
                    psd_mode: bool = False) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        Analyze int (int32) data (e.g., phase data).

        Args:
            data: Input time-domain data (int32)
            sample_rate: Sample rate in Hz
            psd_mode: If True, return PSD (dB/Hz); if False, return power spectrum (dB)

        Returns:
            Tuple of (frequency_axis, spectrum_db, frequency_resolution)
        """
        # Convert to double directly for phase data
        data_d = data.astype(np.float64)
        return self._analyze(data_d, sample_rate, psd_mode)

    def _analyze(self, data: np.ndarray, sample_rate: float,
                 psd_mode: bool = False) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        Internal analysis function.

        Args:
            data: Input time-domain data (float64)
            sample_rate: Sample rate in Hz
            psd_mode: If True, return PSD (dB/Hz); if False, return power spectrum (dB)

        Returns:
            Tuple of (frequency_axis, spectrum_db, frequency_resolution)
        """
        n = len(data)

        # Apply window
        window = self._get_window(n)
        windowed_data = data * window

        # Calculate window correction factors
        # Coherent gain for amplitude correction
        coherent_gain = np.sum(window) / n
        # Noise bandwidth for PSD correction
        noise_bandwidth = np.sum(window**2) / (np.sum(window)**2) * n

        # FFT
        fft_result = np.fft.fft(windowed_data)

        # Calculate power spectrum (V^2)
        # Use single-sided spectrum (positive frequencies only)
        n_half = n // 2
        power_spectrum = np.abs(fft_result[:n_half])**2 / (n**2)

        # Correct for window coherent gain
        power_spectrum /= coherent_gain**2

        # Double the power for single-sided spectrum (except DC)
        power_spectrum[1:] *= 2

        # Frequency resolution
        df = sample_rate / n

        # Create frequency axis
        freq_axis = np.arange(n_half) * df

        # Convert to dB (relative power)
        # Direct conversion without impedance reference
        if psd_mode:
            # Power Spectral Density: divide by frequency resolution
            # Correct for noise bandwidth of window
            power_density = power_spectrum / (df * noise_bandwidth)
            # Convert to dB/Hz
            spectrum_db = 10.0 * np.log10(power_density + 1e-20)
        else:
            # Power spectrum: convert to dB
            spectrum_db = 10.0 * np.log10(power_spectrum + 1e-20)

        return freq_axis, spectrum_db, df

    def analyze(self, data: np.ndarray, sample_rate: float,
                psd_mode: bool = False, data_type: str = 'short') -> Tuple[np.ndarray, np.ndarray, float]:
        """
        Analyze data with automatic type detection.

        Args:
            data: Input time-domain data
            sample_rate: Sample rate in Hz
            psd_mode: If True, return PSD (dB/Hz); if False, return power spectrum (dB)
            data_type: 'short' for raw data, 'int' for phase data

        Returns:
            Tuple of (frequency_axis, spectrum_db, frequency_resolution)
        """
        if data_type == 'short' or data.dtype == np.int16:
            return self.analyze_short(data, sample_rate, psd_mode)
        else:
            return self.analyze_int(data, sample_rate, psd_mode)

    def set_window(self, window_type: WindowType):
        """Change window function type"""
        self.window_type = window_type
        self._window_cache.clear()


class RealTimeSpectrumAnalyzer(SpectrumAnalyzer):
    """
    Real-time spectrum analyzer with averaging support.
    """

    def __init__(self, window_type: WindowType = WindowType.HANNING,
                 averaging_count: int = 1):
        """
        Initialize real-time spectrum analyzer.

        Args:
            window_type: Type of window function
            averaging_count: Number of spectra to average
        """
        super().__init__(window_type)
        self.averaging_count = averaging_count
        self._spectrum_buffer = []
        self._freq_axis: Optional[np.ndarray] = None
        self._df: float = 0

    def update(self, data: np.ndarray, sample_rate: float,
               psd_mode: bool = False, data_type: str = 'short') -> Tuple[np.ndarray, np.ndarray, float]:
        """
        Update spectrum with new data and return averaged result.

        Args:
            data: New time-domain data
            sample_rate: Sample rate in Hz
            psd_mode: If True, return PSD
            data_type: 'short' or 'int'

        Returns:
            Tuple of (frequency_axis, averaged_spectrum_db, frequency_resolution)
        """
        # Analyze new data
        freq_axis, spectrum_db, df = self.analyze(data, sample_rate, psd_mode, data_type)

        self._freq_axis = freq_axis
        self._df = df

        # Add to buffer
        self._spectrum_buffer.append(spectrum_db)

        # Keep only the last N spectra
        if len(self._spectrum_buffer) > self.averaging_count:
            self._spectrum_buffer.pop(0)

        # Calculate average in linear scale, then convert back to dB
        linear_sum = np.zeros_like(spectrum_db)
        for s in self._spectrum_buffer:
            linear_sum += 10 ** (s / 10)
        linear_avg = linear_sum / len(self._spectrum_buffer)
        averaged_db = 10 * np.log10(linear_avg + 1e-20)

        return freq_axis, averaged_db, df

    def reset(self):
        """Clear averaging buffer"""
        self._spectrum_buffer.clear()
        self._freq_axis = None
        self._df = 0

    def set_averaging_count(self, count: int):
        """Set number of spectra to average"""
        self.averaging_count = max(1, count)
        if len(self._spectrum_buffer) > self.averaging_count:
            self._spectrum_buffer = self._spectrum_buffer[-self.averaging_count:]
