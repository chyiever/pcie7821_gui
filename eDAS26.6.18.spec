# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:\\codes\\PCIe-7821\\pcie7821_gui\\run.py'],
    pathex=['E:\\codes\\PCIe-7821\\pcie7821_gui\\src'],
    binaries=[],
    datas=[('E:\\codes\\PCIe-7821\\pcie7821_gui\\resources', 'resources'), ('E:\\codes\\PCIe-7821\\pcie7821_gui\\libs', 'libs')],
    hiddenimports=['main', 'main_window', 'logger', 'config', 'pcie7821_api', 'acquisition_thread', 'data_saver', 'spectrum_analyzer', 'time_space_plot', 'plot_interaction', 'tcp_tab3', 'tcp_tab3.tcp_types', 'tcp_tab3.tcp_tab3_manager', 'tcp_tab3.tcp_sender_worker', 'tcp_tab3.tcp_packet_builder', 'numpy', 'pyqtgraph', 'psutil', 'scipy', 'scipy.signal'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PySide2', 'PySide2.QtCore', 'PySide2.QtGui', 'PySide2.QtWidgets', 'PySide6', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'IPython', 'matplotlib', 'pandas', 'openpyxl', 'sqlalchemy', 'h5py', 'numba', 'llvmlite', 'OpenGL', 'tkinter', 'jedi', 'zmq', 'torch'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='eDAS26.6.18',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\QiGh\\AppData\\Local\\Temp\\eDAS_build_icon.ico'],
)
