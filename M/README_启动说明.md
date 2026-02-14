# 音频可视化工具 - 启动说明（精简版）

## 当前版本约定

- 已移除乐器识别与 YAMNet 相关功能。
- 固定使用 Python 3.13 环境运行。
- 仅保留一个入口脚本：`启动.bat`。

## 使用方法

1. 双击 `启动.bat`。
2. 脚本会自动：
   - 检查本机 `py -3.13`
   - 创建/复用 `venv313`
   - 安装 `requirements_audio_viz.txt`
   - 启动 `0.pyw`

## 保留文件（最小必要）

- `0.pyw`：主控制台
- `1.pyw`：可视化子窗口
- `启动.bat`：唯一环境安装+启动脚本
- `requirements_audio_viz.txt`：依赖清单
- `visualizer_config.json`：运行配置
- `presets/`：预设参数
