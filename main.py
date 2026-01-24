"""
PCIe-7821 DAS Acquisition Software
Main Entry Point

Usage:
    python main.py              # Normal mode (requires hardware)
    python main.py --simulate   # Simulation mode (no hardware required)
"""

import sys
import argparse
import traceback
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt


def setup_high_dpi():
    """Enable high DPI support"""
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


def exception_hook(exc_type, exc_value, exc_tb):
    """Global exception handler"""
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print(f"Unhandled exception:\n{error_msg}")

    # Show error dialog if QApplication exists
    if QApplication.instance():
        QMessageBox.critical(None, "Error", f"An error occurred:\n\n{error_msg}")


def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='PCIe-7821 DAS Acquisition Software')
    parser.add_argument('--simulate', '-s', action='store_true',
                        help='Run in simulation mode without hardware')
    args = parser.parse_args()

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

    # Import main window (after QApplication is created)
    from main_window import MainWindow

    # Create and show main window
    try:
        window = MainWindow(simulation_mode=args.simulate)

        if args.simulate:
            window.setWindowTitle("PCIe-7821 DAS Acquisition Software [SIMULATION MODE]")

        window.show()

        # Run event loop
        sys.exit(app.exec_())

    except Exception as e:
        QMessageBox.critical(None, "Startup Error", f"Failed to start application:\n\n{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
