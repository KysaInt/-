# 音频可视化工具 OpenGL 版 - 启动说明

## 当前版本约定

- M2 是 M 项目的全功能重制版，渲染层已从 pygame 改为 PyOpenGL。
- 控制台仍然是 `0.pyw`，子渲染窗口是 `1.pyw` 的 OpenGL 实现。
- 固定使用 Python 3.13 环境运行。
- 现在只保留一个启动入口：`启动.bat`。

## 使用方法

1. 直接双击 `启动.bat`。
2. 首次在新电脑运行时，脚本会自动：
   - 检查本机 Python 3.13
   - 如果系统未安装 Python 3.13，尝试通过 `winget` 自动安装
   - 自动修复从旧电脑复制过来的失效 `venv313`
   - 创建或复用 `venv313`
   - 安装 `requirements_audio_viz.txt`
   - 启动 `0.pyw`
3. 后续再次启动时，仍会自动做环境检查，但通常会直接进入程序。

## 调试方式

- 只保留 `启动.bat` 这一个入口文件。
- 如果需要控制台模式查看报错，可在终端里运行：`启动.bat debug`
- `debug` 模式会用 `python.exe` 启动主程序，便于查看闪退、依赖或 OpenGL 初始化错误。

## 新电脑注意事项

- 本项目目录里自带的 `venv313` 如果是从别的电脑直接拷贝过来的，里面记录的 Python 路径通常会失效。
- 当前版本的单一启动脚本会自动检测这种情况，并删除后重建虚拟环境。
- 如果系统没有 `winget`，则仍需要先手动安装 Python 3.13。

## 主要文件

- `0.pyw`：主控制台
- `1.pyw`：PyOpenGL 可视化子窗口
- `启动.bat`：唯一启动入口，同时负责环境安装、修复和启动
- `requirements_audio_viz.txt`：依赖清单
- `visualizer_config.json`：运行配置
- `presets/`：完整预设
- `section_presets/`：颜色分区预设