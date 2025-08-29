# PyQt5 GUI应用程序

这是一个基本的PyQt5 GUI应用程序项目，包含窗口、按钮和布局。

## 功能特性

- 基本的PyQt5窗口界面
- 居中的标签显示文本
- 可点击的按钮，点击后更新标签文本
- 响应式布局

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行应用程序

在VS Code中：
1. 按Ctrl+Shift+P打开命令面板
2. 输入"Tasks: Run Task"
3. 选择"运行PyQt5应用程序"

或者直接运行：
```bash
python main.py
```

## 项目结构

```
.
├── main.py              # 主应用程序文件
├── requirements.txt     # Python依赖
├── .vscode/
│   └── tasks.json       # VS Code任务配置
└── .github/
    └── copilot-instructions.md  # Copilot指令
```

## 开发说明

- 使用PyQt5创建GUI界面
- 支持Windows、macOS和Linux
- 可以扩展添加更多组件和功能
