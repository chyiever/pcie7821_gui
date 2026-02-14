# PCIe-7821 DAS Acquisition Software

PCIe-7821 DAS (Distributed Acoustic Sensing) data acquisition software based on PyQt5.

## Project Structure

```
pcie7821_gui/
├── src/                    # Core source code
│   ├── main.py             # Entry point
│   ├── main_window.py      # Main GUI window
│   ├── acquisition_thread.py  # Data acquisition thread
│   ├── data_saver.py       # Async data storage
│   ├── spectrum_analyzer.py   # FFT spectrum analysis
│   ├── pcie7821_api.py     # Hardware API wrapper
│   ├── config.py           # Configuration
│   └── logger.py           # Logging system
├── resources/              # Static resources
│   └── logo.png
├── libs/                   # External libraries
│   └── pcie7821_api.dll
├── tests/                  # Test code
├── examples/               # Example/tutorial code
├── docs/                   # Documentation
├── output/                 # Data output (gitignored)
├── logs/                   # Log files (gitignored)
├── run.py                  # Quick launch script
├── requirements.txt        # Python dependencies
└── README.md
```

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure `pcie7821_api.dll` is in the `libs/` folder.

## Usage

### Normal Mode (requires hardware)
```bash
python run.py
```

### Simulation Mode (no hardware required)
```bash
python run.py --simulate
```

### Debug Mode
```bash
python run.py --debug
```

### Save Log to File
```bash
python run.py --log output.log
```

## Dependencies

- PyQt5 >= 5.15.0
- pyqtgraph >= 0.12.0
- numpy >= 1.20.0
- psutil (for system monitoring)

## Features

- Real-time data acquisition from PCIe-7821 hardware
- FFT spectrum analysis with multiple window functions
- Power Spectrum and PSD display
- Frame-based data storage with auto file splitting
- System monitoring (CPU, Disk, Buffer status)
- Simulation mode for testing without hardware
