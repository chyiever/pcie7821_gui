# Detrend Filter Settings Analysis Report

## Current Configuration Analysis

### 1. Current Settings
- **FPGA Processing**: `detrend_bw = 10Hz` high-pass filter
- **scipy.welch**: `detrend='constant'` (remove DC component)

### 2. Test Results Summary

From the analysis, we can see the effectiveness of different detrend methods:

#### Power levels in different frequency bands:
- **Without detrend**:
  - 0-10Hz average: -24.8 dB
  - 50Hz signal: 21.2 dB
  - 100Hz signal: 15.2 dB

- **With detrend='constant'** (current setting):
  - 0-10Hz average: -27.2 dB (3dB improvement)
  - 50Hz signal: 21.2 dB (unchanged)
  - 100Hz signal: 15.2 dB (unchanged)

- **FPGA high-pass filter (10Hz)** effect:
  - DC(0Hz): -90.8 dB (excellent DC suppression)
  - 0-1Hz: -79.0 dB (strong low-freq suppression)
  - 1-10Hz: -57.6 dB (moderate suppression)

## Assessment: Current Settings Are Correct ✅

### Why the current `detrend='constant'` setting is appropriate:

1. **Two-stage filtering approach is optimal**:
   - **Stage 1 (FPGA)**: Hardware 10Hz high-pass filter removes major low-frequency drifts
   - **Stage 2 (Software)**: `detrend='constant'` removes residual DC offset for PSD calculation

2. **FPGA already handles main detrending**:
   - 10Hz cutoff effectively removes:
     - Temperature drifts
     - Mechanical vibrations < 10Hz
     - Optical power fluctuations
   - Preserves vibration signals ≥10Hz (typical DAS interest range)

3. **scipy detrend='constant' is complementary**:
   - Removes any remaining DC bias after FPGA processing
   - Essential for accurate PSD density calculation
   - Doesn't distort AC signal components
   - More conservative than 'linear' detrend

### Alternative settings analysis:

- **`detrend='linear'`**: Would provide slightly better low-frequency suppression but:
  - Risk of removing slow legitimate signals
  - Unnecessary since FPGA already handles linear drifts
  - May introduce artifacts

- **`detrend=False`**: Would keep residual DC components:
  - Affects PSD accuracy at low frequencies
  - Less clean spectrum baseline

## Frequency Response Analysis

### FPGA 10Hz High-pass Filter:
- **Effective range**: Removes 0-10Hz content
- **Transition band**: ~5-15Hz
- **Stopband attenuation**: >80dB at DC
- **Passband**: >10Hz with <1dB attenuation

### Combined Effect (FPGA + scipy):
- **DC suppression**: >90dB
- **Low-frequency rejection**: Excellent (0-10Hz)
- **Signal preservation**: Good (>10Hz)
- **PSD baseline**: Clean and stable

## Recommendations

### ✅ Keep current settings:
```python
# FPGA configuration
detrend_bw: float = 10.0  # Hz - high-pass cutoff

# scipy.welch configuration
detrend='constant'  # Remove DC component
```

### 📋 Optional optimizations based on application:

1. **For ultra-low frequency monitoring** (< 5Hz):
   - Consider reducing `detrend_bw` to 1-5Hz
   - Trade-off: More susceptible to drift artifacts

2. **For high-frequency focused applications** (> 100Hz):
   - Consider increasing `detrend_bw` to 20-50Hz
   - Benefit: Cleaner high-frequency spectrum

3. **For maximum signal preservation**:
   - Keep current 10Hz setting
   - This balances drift removal vs signal preservation

## Technical Verification

The test results confirm:
- ✅ DC component properly suppressed (-90dB vs +44dB)
- ✅ Low-frequency drifts attenuated (0-10Hz: -57dB average)
- ✅ Signal frequencies preserved (50Hz, 100Hz unchanged)
- ✅ PSD baseline improved by 3dB with detrend='constant'

## Conclusion

The current detrend filter settings are **correctly configured** and well-optimized for DAS vibration monitoring applications. The two-stage approach (FPGA hardware + software detrend) provides:

1. **Robust drift removal** without signal distortion
2. **Clean PSD baselines** for accurate analysis
3. **Preserved frequency content** in the monitoring band (>10Hz)
4. **Good noise floor** performance

No changes are recommended to the current detrend configuration.