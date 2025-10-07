"""
AYE OCR Tool - 快捷键截图OCR工具
支持自定义快捷键、截图选择、OCR识别并自动复制到剪贴板
包含自动依赖检测和安装功能

使用说明:
1. 首次运行会自动检测并安装缺失的依赖
2. 需要手动安装 Tesseract OCR (程序会提供下载链接)
3. 按快捷键 Ctrl+Shift+A 开始截图OCR
4. 可在设置中自定义快捷键和OCR语言
"""
import sys
import json
import os
import subprocess
from pathlib import Path

# ============= 依赖检测和自动安装 =============
def check_and_install_dependencies():
    """检测并自动安装所需依赖"""
    required_packages = {
        'PySide6': 'PySide6',
        'PIL': 'Pillow',
        'pytesseract': 'pytesseract',
        'keyboard': 'keyboard',
        'pyperclip': 'pyperclip',
        'numpy': 'numpy',
        'cv2': 'opencv-python',
        'paddleocr': 'paddleocr',
        'easyocr': 'easyocr'
    }
    
    missing_packages = []
    
    # 检查每个包
    for import_name, package_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_name)
    
    # 如果有缺失的包，提示并安装
    if missing_packages:
        try:
            # 尝试导入tkinter用于显示消息框
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()
            
            msg = f"检测到缺失以下依赖包:\n{', '.join(missing_packages)}\n\n是否自动安装?"
            if messagebox.askyesno("安装依赖", msg):
                root.destroy()
                install_packages(missing_packages)
            else:
                root.destroy()
                sys.exit(0)
        except:
            # tkinter不可用，直接安装
            print("检测到缺失依赖，正在自动安装...")
            install_packages(missing_packages)

def install_packages(packages):
    """安装指定的包"""
    for package in packages:
        print(f"正在安装 {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✓ {package} 安装成功")
        except subprocess.CalledProcessError:
            print(f"✗ {package} 安装失败")
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror("安装失败", 
                    f"无法安装 {package}\n请手动运行:\npip install {package}")
                root.destroy()
            except:
                pass
            sys.exit(1)
    
    print("\n所有依赖安装完成！程序将重新启动...")
    # 重新启动程序
    os.execv(sys.executable, [sys.executable] + sys.argv)

# 在导入其他模块前先检查依赖
check_and_install_dependencies()

# 现在可以安全导入所有依赖
from PIL import ImageGrab, Image, ImageEnhance, ImageFilter
import pytesseract
import numpy as np
import cv2
try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    print("PaddleOCR未安装，将使用其他引擎")

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    print("EasyOCR未安装，将使用其他引擎")
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                               QTextEdit, QMessageBox, QSystemTrayIcon, QMenu, QComboBox)
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
        self.capture_rect = None
        
        self.setCursor(Qt.CursorShape.CrossCursor)
    
    def emit_screenshot_signal(self):
        """延迟发射截图信号"""
        if self.capture_rect:
            self.screenshot_taken.emit(self.capture_rect)
            self.capture_rect = None
        
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
        QTimer.singleShot(50, self.capture_screen)
        
    def capture_screen(self):
        """截取所有屏幕"""
        try:
            screens = QGuiApplication.screens()
            if screens:
                min_x = min(s.geometry().x() for s in screens)
                min_y = min(s.geometry().y() for s in screens)
                max_x = max(s.geometry().x() + s.geometry().width() for s in screens)
                max_y = max(s.geometry().y() + s.geometry().height() for s in screens)
                
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
            
            rect = QRect(self.start_point, self.end_point).normalized()
            
            if rect.width() > 5 and rect.height() > 5:
                # 保存rect以便稍后使用
                self.capture_rect = rect
                # 先隐藏覆盖层，然后延迟截图
                self.hide()
                QTimer.singleShot(100, self.emit_screenshot_signal)
            else:
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
        self.tesseract_input.setPlaceholderText("留空自动检测")
        tesseract_layout.addWidget(self.tesseract_input)
        layout.addLayout(tesseract_layout)
        
        # OCR引擎选择
        engine_layout = QHBoxLayout()
        engine_layout.addWidget(QLabel("OCR引擎:"))
        self.engine_combo = QComboBox()
        self.engine_combo.addItems([
            "智能组合 (最准确)", 
            "PaddleOCR (推荐-中文)", 
            "EasyOCR (深度学习)",
            "Tesseract (通用)"
        ])
        current_engine = self.settings.get("ocr_engine", "combined")
        engine_map = {"combined": 0, "paddleocr": 1, "easyocr": 2, "tesseract": 3}
        self.engine_combo.setCurrentIndex(engine_map.get(current_engine, 0))
        engine_layout.addWidget(self.engine_combo)
        layout.addLayout(engine_layout)
        
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
        help_text.setMaximumHeight(200)
        help_text.setPlainText(
            "使用说明:\n"
            "1. 设置快捷键后点击保存\n"
            "2. 按下快捷键会弹出截图界面\n"
            "3. 鼠标拖动选择要识别的区域\n"
            "4. 释放鼠标后自动识别并复制到剪贴板\n"
            "5. 按ESC键取消截图\n\n"
            "快捷键格式: ctrl+shift+a, alt+z 等\n\n"
            "OCR引擎说明:\n"
            "  - 智能组合: 使用多个引擎综合识别(最准确，稍慢)\n"
            "  - PaddleOCR: 百度引擎，中文优秀\n"
            "  - EasyOCR: 深度学习，80+语言支持\n"
            "  - Tesseract: 传统引擎，需单独安装\n\n"
            "OCR语言(Tesseract): chi_sim(简中) chi_tra(繁中) eng(英文)"
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
            "ocr_lang": "chi_sim+eng",
            "ocr_engine": "combined"
        }
        
    def save_settings(self):
        """保存设置"""
        engine_list = ["combined", "paddleocr", "easyocr", "tesseract"]
        ocr_engine = engine_list[self.engine_combo.currentIndex()]
        self.settings = {
            "hotkey": self.hotkey_input.text().strip(),
            "tesseract_path": self.tesseract_input.text().strip(),
            "ocr_lang": self.lang_input.text().strip(),
            "ocr_engine": ocr_engine
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
    
    # 定义信号用于线程安全的快捷键触发
    screenshot_signal = Signal()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AYE OCR Tool")
        self.setMinimumSize(400, 200)
        
        self.config_file = Path(__file__).parent / "ocr_settings.json"
        self.settings = self.load_settings()
        
        # 连接信号到槽函数
        self.screenshot_signal.connect(self.show_screenshot_overlay)
        
        # 初始化PaddleOCR
        self.paddle_ocr = None
        ocr_engine = self.settings.get("ocr_engine", "combined")
        
        if PADDLEOCR_AVAILABLE and ocr_engine in ["paddleocr", "combined"]:
            try:
                import warnings
                warnings.filterwarnings('ignore', category=DeprecationWarning)
                warnings.filterwarnings('ignore', category=FutureWarning)
                
                self.paddle_ocr = PaddleOCR(use_angle_cls=True, lang='ch')
                print("✓ PaddleOCR 初始化成功")
            except Exception as e:
                print(f"PaddleOCR 初始化失败: {e}")
                try:
                    self.paddle_ocr = PaddleOCR(lang='ch')
                    print("✓ PaddleOCR 初始化成功（简化参数）")
                except Exception as e2:
                    print(f"✗ PaddleOCR 二次初始化失败: {e2}")
                    self.paddle_ocr = None
        
        # 初始化EasyOCR
        self.easy_ocr = None
        if EASYOCR_AVAILABLE and ocr_engine in ["easyocr", "combined"]:
            try:
                # 支持中文和英文，gpu=False使用CPU（兼容性更好）
                self.easy_ocr = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
                print("✓ EasyOCR 初始化成功")
            except Exception as e:
                print(f"✗ EasyOCR 初始化失败: {e}")
                self.easy_ocr = None
        
        # 检测并设置Tesseract路径
        self.check_tesseract()
        
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
    
    def check_tesseract(self):
        """检测并配置Tesseract OCR"""
        # 尝试从设置中加载路径
        tesseract_path = self.settings.get("tesseract_path", "")
        
        # 常见的Tesseract安装路径
        common_paths = [
            tesseract_path,
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Users\Public\Tesseract-OCR\tesseract.exe",
        ]
        
        # 尝试找到可用的Tesseract
        tesseract_found = False
        for path in common_paths:
            if path and os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                tesseract_found = True
                # 保存找到的路径
                if path != tesseract_path:
                    self.settings["tesseract_path"] = path
                    try:
                        with open(self.config_file, 'w', encoding='utf-8') as f:
                            json.dump(self.settings, f, indent=4, ensure_ascii=False)
                    except:
                        pass
                break
        
        # 如果没找到，尝试系统PATH
        if not tesseract_found:
            try:
                result = subprocess.run(['tesseract', '--version'], 
                                      capture_output=True, 
                                      timeout=3)
                tesseract_found = result.returncode == 0
            except:
                pass
        
        # 如果还是没找到，显示友好提示
        if not tesseract_found:
            QTimer.singleShot(1000, self.show_tesseract_install_guide)
    
    def show_tesseract_install_guide(self):
        """显示Tesseract安装指南"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("需要安装 Tesseract OCR")
        msg.setText("未检测到 Tesseract OCR 引擎")
        msg.setInformativeText(
            "Tesseract 是 OCR 识别的核心引擎，需要先安装才能使用。\n\n"
            "安装步骤:\n"
            "1. 访问下载页面（点击下方按钮）\n"
            "2. 下载 Windows 安装包\n"
            "3. 安装时勾选 'Chinese Simplified' 语言包\n"
            "4. 重启本程序\n\n"
            "或在设置中手动指定 Tesseract 路径"
        )
        
        # 添加打开下载页面按钮
        download_btn = msg.addButton("打开下载页面", QMessageBox.ButtonRole.ActionRole)
        settings_btn = msg.addButton("打开设置", QMessageBox.ButtonRole.ActionRole)
        msg.addButton("稍后安装", QMessageBox.ButtonRole.RejectRole)
        
        msg.exec()
        
        clicked = msg.clickedButton()
        if clicked == download_btn:
            import webbrowser
            webbrowser.open("https://github.com/UB-Mannheim/tesseract/wiki")
        elif clicked == settings_btn:
            self.show_settings()
                
    def setup_hotkey(self):
        """设置全局快捷键"""
        hotkey = self.settings.get("hotkey", "ctrl+shift+a")
        try:
            # 使用lambda触发信号，避免直接在非主线程调用Qt界面
            keyboard.add_hotkey(hotkey, lambda: self.screenshot_signal.emit())
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
            "ocr_lang": "chi_sim+eng",
            "enhance_image": True,
            "ocr_engine": "combined"
        }
        
    def preprocess_image(self, image):
        """图像预处理以提升OCR准确率"""
        try:
            # 转换为numpy数组
            img_array = np.array(image)
            
            # 转换为灰度图
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            # 放大图像以提高识别精度（2倍）
            height, width = gray.shape
            gray = cv2.resize(gray, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)
            
            # 去噪
            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            
            # 自适应二值化 - 对不同光照条件更鲁棒
            binary = cv2.adaptiveThreshold(
                denoised, 255, 
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # 形态学操作 - 去除小噪点
            kernel = np.ones((2, 2), np.uint8)
            morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            # 转换回PIL Image
            processed_image = Image.fromarray(morph)
            
            # 额外的锐化处理
            processed_image = processed_image.filter(ImageFilter.SHARPEN)
            
            return processed_image
            
        except Exception as e:
            print(f"图像预处理失败: {e}")
            # 如果预处理失败，返回原图
            return image
    
    def ocr_with_easyocr(self, image):
        """使用EasyOCR进行识别"""
        try:
            # 转换为numpy数组
            img_array = np.array(image)
            
            # EasyOCR识别
            result = self.easy_ocr.readtext(img_array)
            
            # 提取文本
            if result:
                texts = []
                for detection in result:
                    text = detection[1]  # detection[1]是识别的文本
                    texts.append(text)
                return '\n'.join(texts)
            return ""
        except Exception as e:
            print(f"EasyOCR识别失败: {e}")
            return None
    
    def ocr_with_paddleocr(self, image):
        """使用PaddleOCR进行识别"""
        try:
            # 转换为numpy数组
            img_array = np.array(image)
            
            # PaddleOCR识别
            result = self.paddle_ocr.ocr(img_array, cls=True)
            
            # 提取文本
            if result and result[0]:
                texts = []
                for line in result[0]:
                    if len(line) >= 2:
                        text = line[1][0]  # line[1]是(文本, 置信度)元组
                        texts.append(text)
                return '\n'.join(texts)
            return ""
        except Exception as e:
            print(f"PaddleOCR识别失败: {e}")
            return None
    
    def ocr_with_tesseract(self, image):
        """使用Tesseract进行识别"""
        try:
            ocr_lang = self.settings.get("ocr_lang", "chi_sim+eng")
            custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
            text = pytesseract.image_to_string(image, lang=ocr_lang, config=custom_config)
            return text
        except Exception as e:
            print(f"Tesseract识别失败: {e}")
            return None
    
    def ocr_combined(self, image):
        """智能组合多个OCR引擎的结果"""
        results = []
        
        # 尝试所有可用的OCR引擎
        if self.paddle_ocr:
            paddle_result = self.ocr_with_paddleocr(image)
            if paddle_result:
                results.append(("PaddleOCR", paddle_result))
                print(f"✓ PaddleOCR: {len(paddle_result)} 字符")
        
        if self.easy_ocr:
            easy_result = self.ocr_with_easyocr(image)
            if easy_result:
                results.append(("EasyOCR", easy_result))
                print(f"✓ EasyOCR: {len(easy_result)} 字符")
        
        # Tesseract需要预处理
        try:
            if self.settings.get("enhance_image", True):
                processed_image = self.preprocess_image(image)
            else:
                processed_image = image
            tesseract_result = self.ocr_with_tesseract(processed_image)
            if tesseract_result and tesseract_result.strip():
                results.append(("Tesseract", tesseract_result))
                print(f"✓ Tesseract: {len(tesseract_result)} 字符")
        except:
            pass
        
        if not results:
            return None
        
        # 如果只有一个结果，直接返回
        if len(results) == 1:
            return results[0][1]
        
        # 多个结果时，选择最长且包含最多中文字符的结果
        def score_result(text):
            chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
            return len(text) + chinese_count * 2  # 中文字符权重更高
        
        best_result = max(results, key=lambda x: score_result(x[1]))
        print(f"→ 选择 {best_result[0]} 的结果")
        return best_result[1]
    
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
            screen = QGuiApplication.primaryScreen()
            dpr = screen.devicePixelRatio()
            
            # 调整坐标以适应设备像素比
            x = int(rect.x() * dpr)
            y = int(rect.y() * dpr)
            width = int(rect.width() * dpr)
            height = int(rect.height() * dpr)
            
            # 截取图像
            screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            
            # 根据设置选择OCR引擎
            ocr_engine = self.settings.get("ocr_engine", "combined")
            text = None
            
            if ocr_engine == "combined":
                # 智能组合模式 - 使用多个引擎综合识别
                self.statusBar().showMessage("正在使用多引擎智能识别...")
                text = self.ocr_combined(screenshot)
                
            elif ocr_engine == "paddleocr" and self.paddle_ocr:
                text = self.ocr_with_paddleocr(screenshot)
                if text is None:  # PaddleOCR失败，尝试其他引擎
                    print("PaddleOCR失败，尝试降级...")
                    if self.easy_ocr:
                        text = self.ocr_with_easyocr(screenshot)
                    if text is None:
                        if self.settings.get("enhance_image", True):
                            screenshot = self.preprocess_image(screenshot)
                        text = self.ocr_with_tesseract(screenshot)
                        
            elif ocr_engine == "easyocr" and self.easy_ocr:
                text = self.ocr_with_easyocr(screenshot)
                if text is None:  # EasyOCR失败，尝试其他引擎
                    print("EasyOCR失败，尝试降级...")
                    if self.paddle_ocr:
                        text = self.ocr_with_paddleocr(screenshot)
                    if text is None:
                        if self.settings.get("enhance_image", True):
                            screenshot = self.preprocess_image(screenshot)
                        text = self.ocr_with_tesseract(screenshot)
                        
            else:
                # 使用Tesseract
                if self.settings.get("enhance_image", True):
                    screenshot = self.preprocess_image(screenshot)
                text = self.ocr_with_tesseract(screenshot)
            
            # 清理文本
            if text:
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
            
            # 如果是Tesseract错误，显示安装指南
            if "tesseract" in str(e).lower():
                self.show_tesseract_install_guide()
            else:
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
