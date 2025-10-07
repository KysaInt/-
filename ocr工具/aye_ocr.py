"""
AYE OCR Tool - 快捷键截图OCR工具
支持自定义快捷键、截图选择、OCR识别并自动复制到剪贴板
"""
import sys
import json
import os
from pathlib import Path
from PIL import ImageGrab, Image
import pytesseract
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                               QTextEdit, QMessageBox, QSystemTrayIcon, QMenu)
from PySide6.QtCore import Qt, QRect, Signal, QTimer, QPoint
from PySide6.QtGui import (QPainter, QColor, QPen, QKeySequence, QPixmap, 
                          QScreen, QGuiApplication, QIcon, QAction, QCursor)
import keyboard
import pyperclip


class ScreenshotOverlay(QWidget):
    """截图选择覆盖层"""
    screenshot_taken = Signal(QRect)
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | 
                          Qt.WindowType.FramelessWindowHint |
                          Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        
        # 获取所有屏幕的总区域
        self.screens = QGuiApplication.screens()
        self.setup_geometry()
        
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.is_drawing = False
        self.screenshot = None
        
        self.setCursor(Qt.CursorShape.CrossCursor)
        
    def setup_geometry(self):
        """设置覆盖所有屏幕的几何区域"""
        min_x = min(screen.geometry().x() for screen in self.screens)
        min_y = min(screen.geometry().y() for screen in self.screens)
        max_x = max(screen.geometry().x() + screen.geometry().width() for screen in self.screens)
        max_y = max(screen.geometry().y() + screen.geometry().height() for screen in self.screens)
        
        self.setGeometry(min_x, min_y, max_x - min_x, max_y - min_y)
        
    def showEvent(self, event):
        """显示时截取整个屏幕"""
        super().showEvent(event)
        # 短暂延迟以确保覆盖层完全显示
        QTimer.singleShot(50, self.capture_screen)
        
    def capture_screen(self):
        """截取所有屏幕"""
        try:
            # 使用Qt截取所有屏幕
            screens = QGuiApplication.screens()
            if screens:
                # 计算总边界
                min_x = min(s.geometry().x() for s in screens)
                min_y = min(s.geometry().y() for s in screens)
                max_x = max(s.geometry().x() + s.geometry().width() for s in screens)
                max_y = max(s.geometry().y() + s.geometry().height() for s in screens)
                
                # 创建大图像
                full_width = max_x - min_x
                full_height = max_y - min_y
                full_screenshot = QPixmap(full_width, full_height)
                
                painter = QPainter(full_screenshot)
                for screen in screens:
                    screen_pixmap = screen.grabWindow(0)
                    screen_geo = screen.geometry()
                    painter.drawPixmap(screen_geo.x() - min_x, 
                                     screen_geo.y() - min_y, 
                                     screen_pixmap)
                painter.end()
                
                self.screenshot = full_screenshot
        except Exception as e:
            print(f"截图失败: {e}")
            self.screenshot = None
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.is_drawing = True
            
    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.end_point = event.pos()
            self.update()
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.end_point = event.pos()
            self.is_drawing = False
            
            # 计算选择区域
            rect = QRect(self.start_point, self.end_point).normalized()
            
            if rect.width() > 5 and rect.height() > 5:  # 最小尺寸检查
                self.screenshot_taken.emit(rect)
            
            self.hide()
            
    def keyPressEvent(self, event):
        """ESC键取消截图"""
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            
    def paintEvent(self, event):
        painter = QPainter(self)
        
        # 绘制半透明黑色背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        # 如果正在绘制选择框
        if self.is_drawing and self.start_point != self.end_point:
            rect = QRect(self.start_point, self.end_point).normalized()
            
            # 清除选择区域（显示原始截图）
            if self.screenshot:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                painter.fillRect(rect, Qt.GlobalColor.transparent)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                
                # 在选择区域绘制原始截图
                painter.drawPixmap(rect, self.screenshot, rect)
            
            # 绘制选择框边框
            pen = QPen(QColor(0, 150, 255), 2)
            painter.setPen(pen)
            painter.drawRect(rect)
            
            # 显示尺寸信息
            size_text = f"{rect.width()} x {rect.height()}"
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(rect.bottomRight() + QPoint(-100, -5), size_text)


class SettingsWindow(QMainWindow):
    """设置窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AYE OCR - 设置")
        self.setMinimumSize(500, 400)
        
        self.config_file = Path(__file__).parent / "ocr_settings.json"
        self.settings = self.load_settings()
        
        self.init_ui()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 快捷键设置
        hotkey_layout = QHBoxLayout()
        hotkey_layout.addWidget(QLabel("截图快捷键:"))
        self.hotkey_input = QLineEdit()
        self.hotkey_input.setText(self.settings.get("hotkey", "ctrl+shift+a"))
        self.hotkey_input.setPlaceholderText("例如: ctrl+shift+a")
        hotkey_layout.addWidget(self.hotkey_input)
        layout.addLayout(hotkey_layout)
        
        # Tesseract路径设置
        tesseract_layout = QHBoxLayout()
        tesseract_layout.addWidget(QLabel("Tesseract路径:"))
        self.tesseract_input = QLineEdit()
        self.tesseract_input.setText(self.settings.get("tesseract_path", ""))
        self.tesseract_input.setPlaceholderText("留空使用默认路径")
        tesseract_layout.addWidget(self.tesseract_input)
        layout.addLayout(tesseract_layout)
        
        # OCR语言设置
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("OCR语言:"))
        self.lang_input = QLineEdit()
        self.lang_input.setText(self.settings.get("ocr_lang", "chi_sim+eng"))
        self.lang_input.setPlaceholderText("例如: chi_sim+eng")
        lang_layout.addWidget(self.lang_input)
        layout.addLayout(lang_layout)
        
        # 说明文本
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setMaximumHeight(150)
        help_text.setPlainText(
            "使用说明:\n"
            "1. 设置快捷键后点击保存\n"
            "2. 按下快捷键会弹出截图界面\n"
            "3. 鼠标拖动选择要识别的区域\n"
            "4. 释放鼠标后自动识别并复制到剪贴板\n"
            "5. 按ESC键取消截图\n\n"
            "快捷键格式: ctrl+shift+a, alt+z 等\n"
            "OCR语言: chi_sim(简中) chi_tra(繁中) eng(英文)"
        )
        layout.addWidget(help_text)
        
        # 按钮
        button_layout = QHBoxLayout()
        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)
        
        test_btn = QPushButton("测试截图")
        test_btn.clicked.connect(self.test_screenshot)
        button_layout.addWidget(test_btn)
        
        layout.addLayout(button_layout)
        
        # 状态显示
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        
    def load_settings(self):
        """加载设置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {
            "hotkey": "ctrl+shift+a",
            "tesseract_path": "",
            "ocr_lang": "chi_sim+eng"
        }
        
    def save_settings(self):
        """保存设置"""
        self.settings = {
            "hotkey": self.hotkey_input.text().strip(),
            "tesseract_path": self.tesseract_input.text().strip(),
            "ocr_lang": self.lang_input.text().strip()
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            
            self.status_label.setText("✓ 设置已保存，重启生效")
            QMessageBox.information(self, "成功", "设置已保存！\n请重启程序使快捷键生效。")
        except Exception as e:
            self.status_label.setText(f"✗ 保存失败: {e}")
            QMessageBox.warning(self, "错误", f"保存设置失败: {e}")
            
    def test_screenshot(self):
        """测试截图功能"""
        if hasattr(self.parent(), 'show_screenshot_overlay'):
            self.parent().show_screenshot_overlay()
            self.hide()


class OCRTool(QMainWindow):
    """主程序"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AYE OCR Tool")
        self.setMinimumSize(400, 200)
        
        self.config_file = Path(__file__).parent / "ocr_settings.json"
        self.settings = self.load_settings()
        
        # 设置Tesseract路径
        tesseract_path = self.settings.get("tesseract_path", "")
        if tesseract_path and os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        
        self.screenshot_overlay = ScreenshotOverlay()
        self.screenshot_overlay.screenshot_taken.connect(self.on_screenshot_taken)
        
        self.settings_window = SettingsWindow(self)
        
        self.init_ui()
        self.init_tray()
        self.setup_hotkey()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 标题
        title = QLabel("AYE OCR Tool")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 快捷键显示
        hotkey_label = QLabel(f"快捷键: {self.settings.get('hotkey', 'ctrl+shift+a')}")
        hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hotkey_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        screenshot_btn = QPushButton("手动截图")
        screenshot_btn.clicked.connect(self.show_screenshot_overlay)
        button_layout.addWidget(screenshot_btn)
        
        settings_btn = QPushButton("设置")
        settings_btn.clicked.connect(self.show_settings)
        button_layout.addWidget(settings_btn)
        
        layout.addLayout(button_layout)
        
        # 结果显示
        self.result_text = QTextEdit()
        self.result_text.setPlaceholderText("OCR识别结果将显示在这里...")
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)
        
        # 状态栏
        self.statusBar().showMessage("就绪 - 按快捷键开始截图")
        
    def init_tray(self):
        """初始化系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)
        
        # 尝试加载自定义图标，否则使用默认图标
        icon_path = Path(__file__).parent / "icon.ico"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            self.setWindowIcon(icon)
        else:
            icon = self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        
        # 托盘菜单
        tray_menu = QMenu()
        
        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        screenshot_action = QAction("截图OCR", self)
        screenshot_action.triggered.connect(self.show_screenshot_overlay)
        tray_menu.addAction(screenshot_action)
        
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addAction(settings_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
        
        self.tray_icon.setToolTip("AYE OCR Tool")
        
    def on_tray_activated(self, reason):
        """托盘图标点击事件"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()
                
    def setup_hotkey(self):
        """设置全局快捷键"""
        hotkey = self.settings.get("hotkey", "ctrl+shift+a")
        try:
            keyboard.add_hotkey(hotkey, self.show_screenshot_overlay)
            print(f"快捷键已设置: {hotkey}")
        except Exception as e:
            print(f"设置快捷键失败: {e}")
            QMessageBox.warning(self, "警告", f"设置快捷键失败: {e}\n请检查快捷键格式或权限")
            
    def load_settings(self):
        """加载设置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {
            "hotkey": "ctrl+shift+a",
            "tesseract_path": "",
            "ocr_lang": "chi_sim+eng"
        }
        
    def show_screenshot_overlay(self):
        """显示截图覆盖层"""
        self.screenshot_overlay.start_point = QPoint()
        self.screenshot_overlay.end_point = QPoint()
        self.screenshot_overlay.is_drawing = False
        self.screenshot_overlay.show()
        self.screenshot_overlay.activateWindow()
        
    def show_settings(self):
        """显示设置窗口"""
        self.settings_window.show()
        self.settings_window.activateWindow()
        
    def on_screenshot_taken(self, rect):
        """处理截图"""
        try:
            self.statusBar().showMessage("正在识别...")
            
            # 使用PIL截取选定区域
            # 注意：需要考虑屏幕缩放
            screen = QGuiApplication.primaryScreen()
            dpr = screen.devicePixelRatio()
            
            # 调整坐标以适应设备像素比
            x = int(rect.x() * dpr)
            y = int(rect.y() * dpr)
            width = int(rect.width() * dpr)
            height = int(rect.height() * dpr)
            
            # 截取图像
            screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            
            # OCR识别
            ocr_lang = self.settings.get("ocr_lang", "chi_sim+eng")
            text = pytesseract.image_to_string(screenshot, lang=ocr_lang)
            
            # 清理文本
            text = text.strip()
            
            if text:
                # 复制到剪贴板
                pyperclip.copy(text)
                
                # 显示结果
                self.result_text.setPlainText(text)
                self.statusBar().showMessage("✓ 识别完成，已复制到剪贴板")
                
                # 显示通知
                self.tray_icon.showMessage(
                    "OCR识别完成",
                    f"已识别 {len(text)} 个字符并复制到剪贴板",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000
                )
            else:
                self.result_text.setPlainText("未识别到文字")
                self.statusBar().showMessage("✗ 未识别到文字")
                
        except Exception as e:
            error_msg = f"OCR识别失败: {str(e)}"
            self.statusBar().showMessage(f"✗ {error_msg}")
            self.result_text.setPlainText(error_msg)
            QMessageBox.warning(self, "错误", error_msg)
            
    def closeEvent(self, event):
        """关闭事件 - 最小化到托盘"""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "AYE OCR Tool",
            "程序已最小化到系统托盘",
            QSystemTrayIcon.MessageIcon.Information,
            1000
        )
        
    def quit_application(self):
        """退出程序"""
        keyboard.unhook_all()
        self.tray_icon.hide()
        QApplication.quit()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口不退出程序
    
    window = OCRTool()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
