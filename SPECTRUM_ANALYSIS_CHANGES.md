# 频谱分析逻辑修改总结

## 修改目标
根据用户需求修改频谱分析逻辑：
- **Raw数据** (data_type='short'): 只计算功率谱 (Power Spectrum)
- **Phase数据** (data_type='int'): 只计算PSD (Power Spectral Density)，使用 `scipy.signal.welch` 函数

## 主要修改内容

### 1. spectrum_analyzer.py 修改

#### 导入添加
```python
from scipy import signal  # 添加scipy信号处理库
```

#### 新增方法：`_analyze_phase_psd_welch()`
- 专门用于Phase数据的PSD计算
- 使用 `scipy.signal.welch` 函数
- 参数配置：
  - `nperseg=n` : 窗口长度 = 信号长度
  - `noverlap=0` : 无重叠
  - `scaling='density'` : 密度类型PSD
  - `detrend='constant'` : 去除DC成分

#### 修改 `analyze()` 方法
- Raw数据：强制使用功率谱（`psd_mode=False`）
- Phase数据：强制使用新的PSD方法
- `psd_mode` 参数已废弃，分析类型完全由 `data_type` 决定

#### 修改 `RealTimeSpectrumAnalyzer.update()` 方法
- 更新文档说明新的逻辑
- 保持平均计算逻辑不变

### 2. main_window.py 修改

#### GUI界面修改
- 移除 `PSD` 复选框
- 新增 `analysis_type_label` 标签，显示当前分析类型
- 标签根据数据源自动更新：
  - Phase数据 → 显示 "PSD"
  - Raw数据 → 显示 "Power"

#### 逻辑修改
- 所有 `_update_spectrum()` 调用移除 `self.params.display.psd_enable` 参数
- Y轴标签简化：
  - Phase数据：固定显示 "PSD (dB)"
  - Raw数据：固定显示 "Power (dB)"

#### 新增方法
- `_initialize_analysis_type_label()`: 初始化分析类型标签
- 在 `_on_data_source_changed()` 中更新标签显示

### 3. config.py 修改

#### DisplayParams 类修改
- 移除 `psd_enable: bool = False` 字段
- 更新文档说明新的自动分析逻辑

### 4. 测试验证

创建了 `examples/spectrum_analysis_new_logic_test.py` 测试文件：
- 验证Raw数据强制使用功率谱
- 验证Phase数据强制使用PSD (scipy.welch)
- 验证数据类型自动检测功能
- 验证scipy.welch参数设置

## 技术特点

### scipy.welch 配置优势
1. **最大频率分辨率**：窗口长度 = 信号长度
2. **无重叠**：`noverlap=0`，提高计算效率
3. **密度类型**：`scaling='density'`，符合PSD定义
4. **自动去DC**：`detrend='constant'`，移除直流分量

### 向后兼容
- 保持API接口不变
- `psd_mode` 参数仍然存在但被忽略
- 自动数据类型检测功能保留

## 使用示例

```python
from spectrum_analyzer import RealTimeSpectrumAnalyzer

analyzer = RealTimeSpectrumAnalyzer()

# Raw数据 → 自动计算功率谱
freq1, power, df1 = analyzer.update(raw_data, sample_rate, data_type='short')

# Phase数据 → 自动计算PSD
freq2, psd, df2 = analyzer.update(phase_data, sample_rate, data_type='int')

# psd_mode参数被忽略
freq3, result, df3 = analyzer.update(data, sample_rate, psd_mode=True, data_type='int')
# ↑ 仍然返回PSD，无论psd_mode值如何
```

## 显示效果

- **Raw数据频谱**：
  - Y轴：Power (dB)
  - 分析类型标签：Power
  - 包含0Hz DC成分

- **Phase数据频谱**：
  - Y轴：PSD (dB)
  - 分析类型标签：PSD
  - 自动排除DC成分

## 优势总结

1. **逻辑清晰**：数据类型直接决定分析方法，无需手动选择
2. **算法优化**：Phase数据使用scipy.welch，更标准的PSD计算
3. **频率分辨率**：最大化频率分辨率（窗口长度=信号长度）
4. **界面简化**：移除冗余的PSD选择框，自动显示当前分析类型
5. **向后兼容**：保持API稳定，现有代码无需修改

这一修改提升了系统的易用性和技术规范性，特别是在处理相位数据的PSD分析方面使用了更标准的scipy实现。