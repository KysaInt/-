#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyQt5 GUI应用程序 - 使用 pywinstyle 实现深色主题
现代化的 Windows 深色界面设计
"""

import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import pywinstyles


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.apply_dark_theme()

    def initUI(self):
        # 设置窗口属性
        self.setWindowTitle('PyQt5 深色主题应用')
        self.setGeometry(100, 100, 450, 350)

        # 创建布局
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # 标题标签
        title_label = QLabel('使用 pywinstyle 的深色主题')
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont('Segoe UI', 16, QFont.Bold))
        layout.addWidget(title_label)

        # 创建标签
        self.label = QLabel('欢迎使用PyQt5深色主题应用程序！')
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(QFont('Segoe UI', 12))
        layout.addWidget(self.label)

        # 创建按钮
        self.button = QPushButton('点击我')
        self.button.setFont(QFont('Segoe UI', 11))
        self.button.clicked.connect(self.on_button_click)
        layout.addWidget(self.button)

        # 退出按钮
        exit_button = QPushButton('退出')
        exit_button.setFont(QFont('Segoe UI', 11))
        exit_button.clicked.connect(self.close)
        layout.addWidget(exit_button)

        # 设置布局
        self.setLayout(layout)

    def apply_dark_theme(self):
        """应用 pywinstyle 深色主题"""
        try:
            # 应用深色主题到整个应用程序
            pywinstyles.apply_style(self, "dark")

            # 设置窗口的深色样式
            pywinstyles.set_window_style(self, "dark")

            # 自定义样式表以增强深色主题
            self.setStyleSheet("""
                /* 主窗口样式 */
                QWidget {
                    background-color: #1e1e1e;
                    color: #ffffff;
                    border-radius: 8px;
                }

                /* 标签样式 */
                QLabel {
                    color: #ffffff;
                    background-color: transparent;
                    padding: 8px;
                }

                /* 标题标签特殊样式 */
                QLabel:first-child {
                    color: #ffffff;
                    background-color: #2d2d2d;
                    border-radius: 6px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }

                /* 按钮样式 */
                QPushButton {
                    background-color: #3c3c3c;
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-size: 11px;
                    font-weight: 500;
                    min-height: 16px;
                }

                QPushButton:hover {
                    background-color: #4c4c4c;
                    border: 1px solid #666666;
                }

                QPushButton:pressed {
                    background-color: #2c2c2c;
                    border: 1px solid #777777;
                }
            """)

        except Exception as e:
            print(f"应用深色主题失败: {e}")
            # 如果pywinstyle失败，使用基本的深色样式表
            self.setStyleSheet("""
                QWidget {
                    background-color: #1e1e1e;
                    color: #ffffff;
                }
                QLabel {
                    color: #ffffff;
                }
                QPushButton {
                    background-color: #3c3c3c;
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #4c4c4c;
                }
            """)

    def on_button_click(self):
        self.label.setText('按钮被点击了！🎉 (深色主题)')


def main():
    app = QApplication(sys.argv)

    # 尝试应用全局深色主题
    try:
        pywinstyles.apply_style(app, "dark")
    except Exception as e:
        print(f"应用全局深色主题失败: {e}")

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
