#!/usr/bin/env python3
"""
Test script for eDAS storage optimization
验证存储系统优化的测试脚本
"""

import sys
import os
import time
import numpy as np
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_saver import FrameBasedFileSaver
from config import OPTIMIZED_BUFFER_SIZES, POLLING_CONFIG
import logger

log = logger.get_logger("test")

def test_frame_based_saver():
    """Test the new FrameBasedFileSaver"""
    print("🧪 Testing FrameBasedFileSaver...")

    # Test configuration
    test_path = "D:/eDAS_DATA/test"
    frames_per_file = 3  # Small number for quick testing
    scan_rate = 1000
    points_per_frame = 162

    # Create test data saver
    saver = FrameBasedFileSaver(
        save_path=test_path,
        frames_per_file=frames_per_file,
        buffer_size=50
    )

    try:
        # Start saving
        filename = saver.start(
            file_no=1,
            scan_rate=scan_rate,
            points_per_frame=points_per_frame
        )
        print(f"✅ Started saving to: {filename}")

        # Generate and save test frames
        for frame_idx in range(7):  # Should create 2+ files
            # Generate random phase data (int32)
            frame_data = np.random.randint(-100000, 100000, points_per_frame, dtype=np.int32)

            success = saver.save_frame(frame_data)
            print(f"📦 Frame {frame_idx + 1}: {success}, current file frames: {saver.frame_count}/{saver.frames_per_file}")

            # Small delay
            time.sleep(0.1)

        # Check statistics
        print(f"📊 Total files created: {saver.total_files_created}")
        print(f"📊 Total bytes written: {saver.total_bytes_all_files / (1024*1024):.2f} MB")

        # Stop saving
        saver.stop()
        print("✅ FrameBasedFileSaver test completed successfully!")
        return True

    except Exception as e:
        print(f"❌ FrameBasedFileSaver test failed: {e}")
        return False
    finally:
        if saver.is_running:
            saver.stop()

def test_filename_format():
    """Test the new filename format"""
    print("\n📝 Testing filename format...")

    saver = FrameBasedFileSaver("D:/eDAS_DATA/test")
    saver._scan_rate = 2000
    saver._points_per_frame = 162
    saver._file_no = 1

    filename = saver._generate_filename()
    print(f"Generated filename: {filename}")

    # Check format: 序号-eDAS-采样率Hz-每帧点数pt-时间戳.毫秒.bin
    expected_parts = ["00001", "eDAS", "2000Hz", "0162pt"]
    for part in expected_parts:
        if part not in filename:
            print(f"❌ Missing expected part: {part}")
            return False

    if filename.endswith(".bin"):
        print("✅ Filename format test passed!")
        return True
    else:
        print("❌ Filename doesn't end with .bin")
        return False

def test_buffer_configs():
    """Test buffer configuration constants"""
    print("\n⚙️ Testing buffer configurations...")

    try:
        # Check that all required buffer sizes are defined
        required_keys = ['hardware_buffer_frames', 'signal_queue_frames',
                        'storage_queue_frames', 'display_buffer_frames']

        for key in required_keys:
            if key not in OPTIMIZED_BUFFER_SIZES:
                print(f"❌ Missing buffer config: {key}")
                return False
            value = OPTIMIZED_BUFFER_SIZES[key]
            print(f"  {key}: {value}")

        # Check polling configuration
        polling_keys = ['high_freq_interval_ms', 'low_freq_interval_ms']
        for key in polling_keys:
            if key not in POLLING_CONFIG:
                print(f"❌ Missing polling config: {key}")
                return False
            value = POLLING_CONFIG[key]
            print(f"  {key}: {value}ms")

        print("✅ Buffer configuration test passed!")
        return True

    except Exception as e:
        print(f"❌ Buffer configuration test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting eDAS Storage Optimization Tests\n")

    tests = [
        ("Filename Format", test_filename_format),
        ("Buffer Configuration", test_buffer_configs),
        ("FrameBasedFileSaver", test_frame_based_saver)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Testing: {test_name}")
        print('='*50)

        try:
            if test_func():
                passed += 1
            else:
                print(f"❌ {test_name} failed")
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")

    print(f"\n{'='*50}")
    print(f"📊 Test Results: {passed}/{total} tests passed")
    print('='*50)

    if passed == total:
        print("🎉 All tests passed! Storage optimization is ready.")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())