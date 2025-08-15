"""PyQt6 演示：将 win11_theme 的 JSON 主题转换为 QSS 并支持实时编辑/保存

运行：
pip install PyQt6
python theme_qt_demo.py
"""
from __future__ import annotations

import sys
from typing import Dict

from win11_theme import get_manager


def theme_to_qss(t: Dict[str, str]) -> str:
    """把主题字典转换为一个简单的 QSS 字符串。"""
    bg = t.get("background", "#0f1720")
    fg = t.get("foreground", "#e6eef6")
    accent = t.get("accent", "#0ea5e9")
    btn_bg = t.get("button_bg") or accent
    btn_fg = t.get("button_fg") or fg
    highlight = t.get("highlight", "#1f2937")
    border = t.get("border", "#3b82f6")

    qss = f"""
    QWidget {{
        background-color: {bg};
        color: {fg};
        selection-background-color: {accent};
        selection-color: {fg};
    }}
    QMainWindow {{ background-color: {bg}; }}
    QLabel {{ color: {fg}; }}
    QLineEdit, QTextEdit {{
        background-color: {bg};
        color: {fg};
        border: 1px solid {border};
        padding: 4px;
    }}
    QPushButton {{
        background-color: {btn_bg};
        color: {btn_fg};
        border: 1px solid {border};
        padding: 6px 10px;
        border-radius: 6px;
    }}
    QPushButton:pressed {{
        background-color: {accent};
    }}
    QTabWidget::pane {{ border: 1px solid {border}; }}
    """
    return qss


def make_ui():
    try:
        from PyQt6 import QtWidgets, QtGui
    except Exception as e:
        print("PyQt6 不可用：", e)
        print("请先安装： pip install PyQt6")
        sys.exit(1)

    mgr = get_manager("demo_qt")
    app = QtWidgets.QApplication(sys.argv)

    # 主窗口
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("Win11 Theme - PyQt Demo")
    win.resize(800, 480)

    central = QtWidgets.QWidget()
    win.setCentralWidget(central)

    layout = QtWidgets.QHBoxLayout(central)

    # 左侧预览
    preview = QtWidgets.QFrame()
    preview.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
    preview_layout = QtWidgets.QVBoxLayout(preview)
    preview_layout.setContentsMargins(12, 12, 12, 12)

    label = QtWidgets.QLabel("示例标题")
    label.setStyleSheet("font-size:18px;")
    preview_layout.addWidget(label)

    line = QtWidgets.QLineEdit()
    line.setText("输入文本...")
    preview_layout.addWidget(line)

    text = QtWidgets.QTextEdit()
    text.setPlainText("这是多行文本\n用于预览主题配色。")
    preview_layout.addWidget(text)

    btn_row = QtWidgets.QHBoxLayout()
    accent_btn = QtWidgets.QPushButton("强调按钮")
    normal_btn = QtWidgets.QPushButton("普通按钮")
    btn_row.addWidget(accent_btn)
    btn_row.addWidget(normal_btn)
    preview_layout.addLayout(btn_row)

    layout.addWidget(preview, 1)

    # 右侧控制面板
    ctrl = QtWidgets.QFrame()
    ctrl.setFixedWidth(300)
    ctrl_layout = QtWidgets.QVBoxLayout(ctrl)
    ctrl_layout.setContentsMargins(12, 12, 12, 12)

    title = QtWidgets.QLabel("主题控制")
    title.setStyleSheet("font-weight:bold;font-size:14px;")
    ctrl_layout.addWidget(title)

    def add_color_button(label_text, key):
        lbl = QtWidgets.QLabel(label_text)
        btn = QtWidgets.QPushButton("选择")

        def choose():
            col = QtWidgets.QColorDialog.getColor()
            if col.isValid():
                hexc = col.name()
                mgr.set_color(key, hexc)

        btn.clicked.connect(choose)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(btn)
        ctrl_layout.addLayout(row)

    add_color_button("背景", "background")
    add_color_button("文字", "foreground")
    add_color_button("强调", "accent")
    add_color_button("面板高亮", "highlight")
    add_color_button("边框", "border")
    add_color_button("按钮背景", "button_bg")
    add_color_button("按钮文字", "button_fg")

    ctrl_layout.addStretch()

    btn_save = QtWidgets.QPushButton("保存到磁盘")
    btn_load = QtWidgets.QPushButton("从磁盘加载")
    btn_reset = QtWidgets.QPushButton("重置默认")

    ctrl_layout.addWidget(btn_save)
    ctrl_layout.addWidget(btn_load)
    ctrl_layout.addWidget(btn_reset)

    layout.addWidget(ctrl)

    # 应用主题函数
    def apply_theme(t: Dict[str, str]):
        qss = theme_to_qss(t)
        app.setStyleSheet(qss)

    # 连接 ThemeManager 的回调
    mgr.register_callback(apply_theme)

    # 初始应用
    apply_theme(mgr.get_theme())

    # 控件信号
    btn_save.clicked.connect(mgr.save)
    btn_load.clicked.connect(lambda: mgr.load() or apply_theme(mgr.get_theme()))
    btn_reset.clicked.connect(lambda: mgr.reset())

    win.show()
    return app.exec()


if __name__ == "__main__":
    make_ui()
