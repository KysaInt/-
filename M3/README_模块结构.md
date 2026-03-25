# M3 模块结构

## 当前分层

- [0.pyw](0.pyw)
  - 主控制台 UI
  - 配置编辑、预设、预览面板
  - 子进程管理与状态回传

- [1.pyw](1.pyw)
  - 圆形频谱渲染窗口
  - 图形状态更新
  - 与音频核心模块对接

- [core/audio_runtime.py](core/audio_runtime.py)
  - 通用音频采集与分析核心
  - 不依赖 Qt / OpenGL / 主界面布局
  - 适合作为 Unity 或其他宿主的算法参考层

- [unity_exporter.py](unity_exporter.py)
  - 轻量 Unity 导出模块
  - 将当前预设配置转换为单文件 C# 组件脚本
  - 不导出主界面、预设管理器或 Unity 侧 UI

## audio_runtime.py 提供的能力

- `LoopbackAudioCapture`
  - WASAPI loopback 采集
  - 输出最新音频帧

- `AudioSignalProcessor`
  - 频带分桶
  - FFT
  - 时间窗平滑
  - K/P 信号计算
  - 独立阻尼配置读取

## 适合 Unity 复用的部分

最适合直接复用或移植到 Unity 的是：

- `AudioSignalProcessor.apply_damping_step`
- `AudioSignalProcessor.build_band_edges`
- `AudioSignalProcessor.process_frame`
- `AudioSignalProcessor.update_spectrum_history`

在 Unity 里建议保留同样的分层：

1. 音频输入层
   - Unity 的麦克风输入或 `GetSpectrumData`
2. 通用分析层
   - 对应这里的 `AudioSignalProcessor`
3. 表现层
   - 粒子、材质、线条、骨骼或触手驱动

## 后续建议

- 继续把 `1.pyw` 中的图形状态生成逻辑拆到 `core/visual_state.py`
- 将配置结构进一步拆成 `audio_config` / `theme_config` / `window_config`
- 如果目标是 Unity 直接复用，当前已经提供 `unity_exporter.py` 作为固定预设导出入口
- [0.pyw](0.pyw) 左侧新增了“导出到Unity”页面，用于选择输出类名、路径并执行导出
- 如果后续要进一步提高 Unity 侧还原度，再考虑抽出一份更纯粹的 C# `AudioSignalProcessor`