import subprocess
import sys
import threading
from PIL import Image

def install_package(package, import_name=None, options=None):
    """检查并安装指定的 Python 包。"""
    if options is None:
        options = []
    try:
        __import__(import_name or package)
    except ImportError:
        print(f"正在安装 {package}...")
        command = [sys.executable, "-m", "pip", "install", package] + options
        subprocess.check_call(command)

# 检查并安装必要的依赖
install_package('PySide6')
install_package('pyperclip')
install_package('keyboard')
install_package('pyscreenshot')
install_package('Pillow', 'PIL')
install_package('paddleocr')
install_package('paddlepaddle', 'paddle', options=["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"])


from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QTextEdit, QVBoxLayout, QWidget, QStatusBar
from PySide6.QtCore import Qt, QTimer
import pyperclip
import pyscreenshot as ImageGrab
from paddleocr import PaddleOCR
import keyboard

# 初始化 OCR，支持中文和英文
# 放在全局，避免重复加载模型
print("正在初始化 OCR 模型，请稍候...")
ocr = PaddleOCR(use_angle_cls=True, lang='ch')
print("OCR 模型初始化完成。")

class OCRWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AYE_OCR 截图识别")
        self.setGeometry(100, 100, 400, 300)

        # --- UI 组件 ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        self.ocr_button = QPushButton("开始截图识别 (或按 Ctrl+Shift+S)")
        self.result_text = QTextEdit()
        self.result_text.setPlaceholderText("识别结果将显示在这里...")

        self.layout.addWidget(self.ocr_button)
        self.layout.addWidget(self.result_text)

        # --- 状态栏 ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("准备就绪")

        # --- 事件连接 ---
        self.ocr_button.clicked.connect(self.run_ocr)

        # --- 全局热键监听 ---
        # 使用 keyboard 库在后台监听热键
        self.setup_hotkey()

    def setup_hotkey(self):
        """设置全局热键。"""
        try:
            keyboard.add_hotkey('ctrl+shift+s', self.run_ocr_from_hotkey, suppress=True)
        except Exception as e:
            self.status_bar.showMessage(f"热键设置失败: {e}")

    def run_ocr_from_hotkey(self):
        """由热键触发的 OCR，需要确保 UI 操作在主线程中执行。"""
        # QTimer.singleShot 用于将任务调度到 Qt 主事件循环中执行
        QTimer.singleShot(0, self.run_ocr)

    def run_ocr(self):
        """执行截图和 OCR 的核心功能。"""
        self.status_bar.showMessage("请选择截图区域...")
        
        # 隐藏窗口，延迟一小段时间确保窗口完全消失
        self.hide()
        QTimer.singleShot(200, self.capture_and_process)

    def capture_and_process(self):
        """截图并处理图像"""
        try:
            # 截图
            img = ImageGrab.grab()
            
            if img:
                self.status_bar.showMessage("正在识别...")
                # 将 PIL Image 对象转换为 paddleocr 需要的格式 (numpy array)
                # paddleocr 内部会处理
                result = ocr.ocr(img, cls=True)

                # 拼接识别结果
                if result and result[0] is not None:
                    text = "\n".join([line[1][0] for line in result[0]])
                    self.result_text.setPlainText(text)
                    pyperclip.copy(text)
                    self.status_bar.showMessage("识别完成，已复制到剪贴板！")
                else:
                    self.result_text.setPlainText("")
                    self.status_bar.showMessage("未识别到文字。")
            else:
                self.status_bar.showMessage("截图已取消。")

        except Exception as e:
            self.status_bar.showMessage(f"发生错误: {e}")
            print(f"错误信息: {e}")
        finally:
            # 无论成功与否，都重新显示窗口
            self.show()
            self.activateWindow() # 将窗口带到前台

    def closeEvent(self, event):
        """在关闭窗口前清理热键。"""
        keyboard.remove_all_hotkeys()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OCRWindow()
    window.show()
    sys.exit(app.exec())

