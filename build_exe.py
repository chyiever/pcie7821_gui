#!/usr/bin/env python
"""
Build the PCIe-7821 GUI into a standalone Windows executable.

Default behavior:
    python build_exe.py

Common variants:
    python build_exe.py --console
    python build_exe.py --clean-only
    python build_exe.py --skip-clean
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Sequence

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parent
ENTRY_SCRIPT = PROJECT_ROOT / "run.py"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
ICON_SOURCE = PROJECT_ROOT / "resources" / "eDAS-LOGO.png"


def default_app_name() -> str:
    now = datetime.now()
    return f"eDAS{now.year % 100}.{now.month}.{now.day}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Use PyInstaller to package the project into a standalone exe."
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Build a console-mode executable for debugging.",
    )
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Do not remove previous build/dist/spec outputs before packaging.",
    )
    parser.add_argument(
        "--clean-only",
        action="store_true",
        help="Only clean old packaging outputs and then exit.",
    )
    parser.add_argument(
        "--name",
        default=default_app_name(),
        help="Executable name. Default: eDASYY.M.D",
    )
    parser.add_argument(
        "--distpath",
        default=str(DIST_DIR),
        help=f"PyInstaller dist directory. Default: {DIST_DIR}",
    )
    parser.add_argument(
        "--workpath",
        default=str(BUILD_DIR),
        help=f"PyInstaller build directory. Default: {BUILD_DIR}",
    )
    parser.add_argument(
        "--specpath",
        default=str(PROJECT_ROOT),
        help=f"Directory used to store the generated spec file. Default: {PROJECT_ROOT}",
    )
    parser.add_argument(
        "--upx-dir",
        default=None,
        help="Optional UPX directory path passed through to PyInstaller.",
    )
    return parser.parse_args()


def remove_path(path: Path) -> None:
    if not path.exists():
        return

    if path.is_dir():
        shutil.rmtree(path)
        print(f"[clean] Removed directory: {path}")
        return

    path.unlink()
    print(f"[clean] Removed file: {path}")


def clean_outputs(app_name: str, distpath: Path, workpath: Path, specpath: Path) -> None:
    spec_file = specpath / f"{app_name}.spec"
    exe_file = distpath / f"{app_name}.exe"
    for target in (exe_file, workpath, spec_file):
        remove_path(target)


def ensure_entry_script() -> None:
    if not ENTRY_SCRIPT.exists():
        raise FileNotFoundError(f"Entry script not found: {ENTRY_SCRIPT}")


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "PyInstaller is not installed. Install it first with:\n"
            "    pip install pyinstaller"
        ) from exc


def add_data_arg(source: Path, destination: str) -> str:
    separator = ";" if os.name == "nt" else ":"
    return f"{source}{separator}{destination}"


def collect_data_files() -> List[str]:
    data_args: List[str] = []
    candidates = [
        (PROJECT_ROOT / "resources", "resources", True),
        (PROJECT_ROOT / "libs", "libs", True),
    ]

    for source, destination, required in candidates:
        if source.exists():
            data_args.append(add_data_arg(source, destination))
        elif required:
            raise FileNotFoundError(f"Required packaging resource not found: {source}")

    return data_args


def prepare_icon_file() -> Path | None:
    """Convert the requested PNG logo into a Windows .ico for PyInstaller."""
    if not ICON_SOURCE.exists():
        print(f"[warn] Icon source not found, skip exe icon: {ICON_SOURCE}")
        return None

    icon_path = Path(tempfile.gettempdir()) / "eDAS_build_icon.ico"
    with Image.open(ICON_SOURCE) as image:
        image = image.convert("RGBA")
        image.save(
            icon_path,
            format="ICO",
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
        )
    print(f"[build] Prepared icon: {icon_path}")
    return icon_path


def build_hidden_imports() -> List[str]:
    return [
        "main",
        "main_window",
        "logger",
        "config",
        "pcie7821_api",
        "acquisition_thread",
        "data_saver",
        "bz_format",
        "spectrum_analyzer",
        "time_space_plot",
        "realtime_filter",
        "plot_interaction",
        "tcp_tab3",
        "tcp_tab3.tcp_types",
        "tcp_tab3.tcp_tab3_manager",
        "tcp_tab3.tcp_sender_worker",
        "tcp_tab3.tcp_packet_builder",
        "numpy",
        "pyqtgraph",
        "psutil",
        "scipy",
        "scipy.signal",
        "zstandard",
    ]


def build_excluded_modules() -> List[str]:
    return [
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PySide2",
        "PySide2.QtCore",
        "PySide2.QtGui",
        "PySide2.QtWidgets",
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "IPython",
        "matplotlib",
        "pandas",
        "openpyxl",
        "sqlalchemy",
        "h5py",
        "numba",
        "llvmlite",
        "OpenGL",
        "tkinter",
        "jedi",
        "zmq",
        "torch",
    ]


def build_pyinstaller_command(args: argparse.Namespace) -> List[str]:
    distpath = Path(args.distpath).resolve()
    workpath = Path(args.workpath).resolve()
    specpath = Path(args.specpath).resolve()
    src_path = (PROJECT_ROOT / "src").resolve()
    icon_path = prepare_icon_file()

    command: List[str] = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        args.name,
        "--distpath",
        str(distpath),
        "--workpath",
        str(workpath),
        "--specpath",
        str(specpath),
        "--paths",
        str(src_path),
    ]

    if icon_path is not None:
        command.extend(["--icon", str(icon_path)])

    if not args.console:
        command.append("--windowed")

    if args.upx_dir:
        command.extend(["--upx-dir", str(Path(args.upx_dir).resolve())])

    for data_arg in collect_data_files():
        command.extend(["--add-data", data_arg])

    for hidden_import in build_hidden_imports():
        command.extend(["--hidden-import", hidden_import])

    for excluded_module in build_excluded_modules():
        command.extend(["--exclude-module", excluded_module])

    command.append(str(ENTRY_SCRIPT))
    return command


def run_command(command: Sequence[str]) -> None:
    print("[build] Running command:")
    print("        " + " ".join(f'"{part}"' if " " in part else part for part in command))
    subprocess.run(command, cwd=str(PROJECT_ROOT), check=True)


def expected_output_path(app_name: str, distpath: Path) -> Path:
    return distpath / f"{app_name}.exe"


def copy_runtime_defaults(exe_path: Path) -> None:
    """Copy editable runtime files next to the built executable."""
    runtime_targets = [
        PROJECT_ROOT / "last_params.json",
    ]

    for source in runtime_targets:
        if not source.exists():
            continue
        destination = exe_path.parent / source.name
        shutil.copy2(source, destination)
        print(f"[post] Copied runtime file: {destination}")


def remove_build_directory(workpath: Path) -> None:
    if workpath.exists():
        shutil.rmtree(workpath)
        print(f"[post] Removed build directory: {workpath}")


def print_summary(exe_path: Path) -> None:
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print()
    print("[done] Packaging completed.")
    print(f"[done] EXE path: {exe_path}")
    print(f"[done] EXE size: {size_mb:.2f} MB")
    print("[done] The generated executable can run on Windows machines without a local Python installation.")


def main() -> int:
    args = parse_args()

    if os.name != "nt":
        print("[warn] This script is intended for Windows packaging. Current platform is not Windows.")

    ensure_entry_script()
    ensure_pyinstaller()

    distpath = Path(args.distpath).resolve()
    workpath = Path(args.workpath).resolve()
    specpath = Path(args.specpath).resolve()

    if not args.skip_clean:
        clean_outputs(args.name, distpath, workpath, specpath)

    if args.clean_only:
        print("[done] Clean-only mode finished.")
        return 0

    command = build_pyinstaller_command(args)
    run_command(command)

    exe_path = expected_output_path(args.name, distpath)
    if not exe_path.exists():
        raise FileNotFoundError(f"Packaging finished but exe was not found: {exe_path}")

    copy_runtime_defaults(exe_path)
    remove_build_directory(workpath)
    print_summary(exe_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
