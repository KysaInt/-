#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS 图标显示测试程序
测试新生成的图标是否正常显示在任务栏中
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt, QSize

class IconTestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("TTS 图标测试 - 查看任务栏图标")
        self.setGeometry(100, 100, 600, 400)
        
        layout = QVBoxLayout()
        
        # 显示图标预览
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_png = os.path.join(script_dir, "icon.png")
        icon_ico = os.path.join(script_dir, "icon.ico")
        
        # 标题
        title = QLabel("TTS 应用图标测试")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # PNG 预览
        if os.path.exists(icon_png):
            png_label = QLabel("PNG 图标预览 (256x256):")
            png_label.setStyleSheet("font-size: 12px; margin-top: 10px;")
            layout.addWidget(png_label)
            
            pixmap = QPixmap(icon_png)
            icon_label = QLabel()
            icon_label.setPixmap(pixmap.scaledToWidth(256, Qt.SmoothTransformation))
            icon_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(icon_label)
            
            info_label = QLabel(f"✅ 已找到 PNG 图标: {icon_png}")
            info_label.setStyleSheet("color: green; margin: 5px;")
            layout.addWidget(info_label)
        else:
            info_label = QLabel(f"❌ 未找到 PNG 图标")
            info_label.setStyleSheet("color: red; margin: 5px;")
            layout.addWidget(info_label)
        
        # ICO 预览
        if os.path.exists(icon_ico):
            ico_label = QLabel("ICO 图标 (任务栏用):")
            ico_label.setStyleSheet("font-size: 12px; margin-top: 10px;")
            layout.addWidget(ico_label)
            
            info_label2 = QLabel(f"✅ 已找到 ICO 图标: {icon_ico}")
            info_label2.setStyleSheet("color: green; margin: 5px;")
            layout.addWidget(info_label2)
        else:
            info_label2 = QLabel(f"❌ 未找到 ICO 图标")
            info_label2.setStyleSheet("color: red; margin: 5px;")
            layout.addWidget(info_label2)
        
        # 说明
        help_text = QLabel(
            "💡 检查清单:\n"
            "1. ✅ 查看窗口标题栏左上角的图标\n"
            "2. ✅ 查看 Windows 任务栏中的图标\n"
            "3. ✅ 按 Alt+Tab 查看窗口切换器中的图标\n"
            "4. ✅ 关闭程序后，重新启动查看图标是否更新\n\n"
            "如果图标仍为空白:\n"
            "• 清除 Windows 图标缓存: 在 cmd 中运行\n"
            "  taskkill /F /IM explorer.exe\n"
            "• 重启文件管理器\n"
        )
        help_text.setStyleSheet("font-size: 11px; background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        
        # 关闭按钮
        close_btn = QPushButton("关闭测试")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用信息
    app.setApplicationName("AYE TTS")
    app.setApplicationDisplayName("AYE TTS 工具集")
    
    # 加载图标
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_ico = os.path.join(script_dir, "icon.ico")
    icon_png = os.path.join(script_dir, "icon.png")
    
    icon = None
    if os.path.exists(icon_ico):
        icon = QIcon(icon_ico)
        print(f"✅ 已加载 ICO 图标: {icon_ico}")
    elif os.path.exists(icon_png):
        icon = QIcon(icon_png)
        print(f"✅ 已加载 PNG 图标: {icon_png}")
    else:
        print("❌ 未找到图标文件")
    
    if icon:
        app.setWindowIcon(icon)
    
    # 创建窗口
    window = IconTestWindow()
    if icon:
        window.setWindowIcon(icon)
    
    window.show()
    sys.exit(app.exec())
