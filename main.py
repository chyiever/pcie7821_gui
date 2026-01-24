"""
PCIe-7821 DAS Acquisition Software
Main Entry Point

Usage:
    python main.py              # Normal mode (requires hardware)
    python main.py --simulate   # Simulation mode (no hardware required)
    python main.py --debug      # Enable debug logging
    python main.py --log FILE   # Save log to file
"""

import sys
import argparse
import traceback
import logging
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt

from logger import setup_logging, get_logger


def setup_high_dpi():
    """Enable high DPI support"""
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


def exception_hook(exc_type, exc_value, exc_tb):
    """Global exception handler"""
    log = get_logger("main")
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log.critical(f"Unhandled exception:\n{error_msg}")

    # Show error dialog if QApplication exists
    if QApplication.instance():
        QMessageBox.critical(None, "Error", f"An error occurred:\n\n{error_msg}")


def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='PCIe-7821 DAS Acquisition Software')
    parser.add_argument('--simulate', '-s', action='store_true',
                        help='Run in simulation mode without hardware')
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--log', '-l', type=str, default=None,
                        help='Save log to file (default: pcie7821_YYYYMMDD_HHMMSS.log)')
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO

    # Generate log filename if logging to file
    log_file = args.log
    if log_file == '':
        # Empty string means use default filename
        log_file = f"pcie7821_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    setup_logging(level=log_level, log_file=log_file, console=True)
    log = get_logger("main")

    log.info("=" * 60)
    log.info("PCIe-7821 DAS Acquisition Software Starting")
    log.info(f"Simulation mode: {args.simulate}")
    log.info(f"Debug mode: {args.debug}")
    log.info(f"Log file: {log_file or 'None'}")
    log.info("=" * 60)

    # Setup exception handling
    sys.excepthook = exception_hook

    # Setup high DPI
    setup_high_dpi()

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("PCIe-7821 DAS")
    app.setApplicationVersion("1.0.0")

    # Set application style
    app.setStyle('Fusion')

    log.info("QApplication created")

    # Import main window (after QApplication is created)
    from main_window import MainWindow

    # Create and show main window
    try:
        log.info("Creating main window...")
        window = MainWindow(simulation_mode=args.simulate)

        if args.simulate:
            window.setWindowTitle("PCIe-7821 DAS Acquisition Software [SIMULATION MODE]")

        window.show()
        log.info("Main window shown")

        # Run event loop
        log.info("Entering event loop...")
        exit_code = app.exec_()
        log.info(f"Event loop exited with code {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        log.exception(f"Failed to start application: {e}")
        QMessageBox.critical(None, "Startup Error", f"Failed to start application:\n\n{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
