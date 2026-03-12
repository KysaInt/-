# 音频可视化工具 OpenGL 版 - 启动说明

## 当前版本约定

- M2 是 M 项目的全功能重制版，渲染层已从 pygame 改为 PyOpenGL。
- 控制台仍然是 `0.pyw`，子渲染窗口改为 `1.pyw` 的 OpenGL 实现。
- 固定使用 Python 3.13 环境运行。
- 推荐直接使用 `启动.bat`。
- 如果双击 `pyw` 没有反馈，可使用 `调试启动.bat` 以控制台模式查看报错。

## 使用方法

1. 双击 `启动.bat`。
2. 脚本会自动：
   - 检查本机 `py -3.13`
   - 创建/复用 `venv313`
   - 安装 `requirements_audio_viz.txt`
   - 启动 `0.pyw`

## 调试启动

- `调试启动.bat` 会用 `python.exe` 而不是 `pythonw.exe` 启动主程序。
- 适合排查这类情况：
   - 双击 `0.pyw` 没反应
   - 启动后立刻闪退
   - OpenGL 或依赖初始化失败

## 主要文件

- `0.pyw`：主控制台
- `1.pyw`：PyOpenGL 可视化子窗口
- `启动.bat`：环境安装与启动脚本
- `requirements_audio_viz.txt`：依赖清单
- `visualizer_config.json`：运行配置
- `presets/`：完整预设
- `section_presets/`：颜色分区预设