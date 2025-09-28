
import asyncio
import json
import os
import sys
import subprocess
import importlib
import re
import tempfile
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView, QLineEdit
)
from PySide6.QtCore import QThread, Signal, Qt, QObject

# --- 自动依赖安装 ---

def _install_package(package_name):
    print(f"未检测到 {package_name}，正在自动安装……")
    subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

def ensure_package(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    
    # 检查模块是否可以导入
    try:
        if import_name == "pynput.keyboard":
             from pynput import keyboard
             return keyboard
        return importlib.import_module(import_name)
    except ImportError:
        # 如果不能，则安装
        _install_package(package_name)
        # 再次尝试导入
        if import_name == "pynput.keyboard":
             from pynput import keyboard
             return keyboard
        return importlib.import_module(import_name)

edge_tts = ensure_package("edge-tts")
pyperclip = ensure_package("pyperclip")
keyboard = ensure_package("pynput", "pynput.keyboard")

# --- TTS 转换核心 ---

class TTSWorker(QThread):
    finished = Signal(str)  # 完成后传递 MP3 文件路径
    error = Signal(str)

    def __init__(self, voice: str, text: str, parent=None):
        super().__init__(parent)
        self.voice = voice
        self.text = text
        self.output_ext = ".mp3"
        self.output_dir = tempfile.gettempdir()

    async def tts_async(self):
        if not self.text.strip():
            self.error.emit("剪贴板内容为空。")
            return

        try:
            communicate = edge_tts.Communicate(self.text, self.voice)
            # 使用时间戳和部分文本创建唯一文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_text = re.sub(r'[\\/:*?"<>|]', '_', self.text[:20].strip())
            file_name = f"tts_{timestamp}_{safe_text}{self.output_ext}"
            output_path = os.path.join(self.output_dir, file_name)

            await communicate.save(output_path)
            self.finished.emit(output_path)
        except Exception as e:
            self.error.emit(f"语音转换失败: {e}")

    def run(self):
        asyncio.run(self.tts_async())

# --- 快捷键监听 ---

class HotkeyListener(QObject):
    hotkey_pressed = Signal()

    def __init__(self, hotkey_str, parent=None):
        super().__init__(parent)
        self.hotkey_str = hotkey_str
        self.listener = None
        self.hotkey_combination = self.parse_hotkey(hotkey_str)

    def parse_hotkey(self, hotkey_str):
        combination = set()
        parts = [p.strip().lower() for p in hotkey_str.split('+')]
        for part in parts:
            try:
                # 尝试解析为特殊键
                key = getattr(keyboard.Key, part)
                combination.add(key)
            except AttributeError:
                # 否则视为普通字符键
                combination.add(keyboard.KeyCode.from_char(part))
        return combination

    def on_press(self, key):
        if key in self.hotkey_combination:
            self.pressed_keys.add(key)
            if self.pressed_keys == self.hotkey_combination:
                self.hotkey_pressed.emit()

    def on_release(self, key):
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

    def start(self):
        if self.listener:
            self.listener.stop()
        self.pressed_keys = set()
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

    def stop(self):
        if self.listener:
            self.listener.stop()

# --- 主应用界面 ---

class ClipboardTTSApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("剪贴板语音助手")
        self.setGeometry(100, 100, 500, 600)

        self.layout = QVBoxLayout(self)
        self.hotkey_listener = None

        # --- UI 元素 ---
        self.label_voice = QLabel("选择一个语音模型:")
        self.voice_tree = QTreeWidget()
        self.voice_tree.setHeaderLabels(["名称", "性别", "区域"])
        self.voice_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.voice_tree.setSortingEnabled(True)
        self.voice_tree.sortByColumn(0, Qt.AscendingOrder)
        self.voice_items = {}
        self.populate_voices()

        self.hotkey_layout = QHBoxLayout()
        self.hotkey_label = QLabel("当前快捷键:")
        self.current_hotkey_label = QLabel("未设置")
        self.hotkey_input = QLineEdit()
        self.hotkey_input.setPlaceholderText("例如: ctrl+alt+t")
        self.set_hotkey_button = QPushButton("设置快捷键")
        self.hotkey_layout.addWidget(self.hotkey_label)
        self.hotkey_layout.addWidget(self.current_hotkey_label)
        self.hotkey_layout.addWidget(self.hotkey_input)
        self.hotkey_layout.addWidget(self.set_hotkey_button)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        self.layout.addWidget(self.label_voice)
        self.layout.addWidget(self.voice_tree)
        self.layout.addLayout(self.hotkey_layout)
        self.layout.addWidget(self.log_view)

        # --- 连接信号和槽 ---
        self.set_hotkey_button.clicked.connect(self.on_set_hotkey)
        self.voice_tree.itemSelectionChanged.connect(self.save_settings)

        self.load_settings()
        self.log("欢迎使用剪贴板语音助手！")
        self.log("1. 在上方选择一个语音模型。")
        self.log("2. 在输入框中设置一个快捷键组合 (例如 'ctrl+alt+c')。")
        self.log("3. 按下快捷键，剪贴板中的文本将被转换为语音，MP3文件路径会自动复制到剪贴板。")

    def log(self, message):
        self.log_view.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def populate_voices(self):
        try:
            # 使用 utf-8 编码获取语音列表
            result = subprocess.run(
                [sys.executable, "-m", "edge_tts", "--list-voices"],
                capture_output=True, text=True, encoding='utf-8', errors='ignore'
            )
            lines = result.stdout.strip().split('\n')
            
            voices_by_lang = {}
            for line in lines[2:]: # 跳过标题
                parts = line.split()
                if len(parts) >= 4 and 'zh' in parts[1]:
                    name, lang, gender, *_ = parts
                    if lang not in voices_by_lang:
                        voices_by_lang[lang] = []
                    voices_by_lang[lang].append({"name": name, "gender": gender})

            for lang, voices in sorted(voices_by_lang.items()):
                lang_item = QTreeWidgetItem(self.voice_tree, [lang])
                for voice in sorted(voices, key=lambda x: x['name']):
                    child = QTreeWidgetItem(lang_item, [voice['name'], voice['gender'], lang])
                    self.voice_items[voice['name']] = child
                self.voice_tree.expandItem(lang_item)

        except Exception as e:
            self.log(f"获取语音模型列表失败: {e}")

    def get_selected_voice(self):
        selected_items = self.voice_tree.selectedItems()
        if not selected_items:
            return None
        # 确保选中的是子项
        item = selected_items[0]
        if item.parent():
            return item.text(0)
        return None

    def on_set_hotkey(self):
        hotkey_str = self.hotkey_input.text().strip()
        if not hotkey_str:
            self.log("错误：快捷键不能为空。")
            return
        
        if self.hotkey_listener:
            self.hotkey_listener.stop()

        try:
            self.hotkey_listener = HotkeyListener(hotkey_str, self)
            self.hotkey_listener.hotkey_pressed.connect(self.on_hotkey_triggered)
            self.hotkey_listener.start()
            self.current_hotkey_label.setText(hotkey_str)
            self.log(f"快捷键已设置为: {hotkey_str}")
            self.save_settings()
        except Exception as e:
            self.log(f"设置快捷键失败: {e}")
            self.current_hotkey_label.setText("设置失败")

    def on_hotkey_triggered(self):
        self.log("快捷键触发！")
        voice = self.get_selected_voice()
        if not voice:
            self.log("错误：请先选择一个语音模型。")
            return

        clipboard_text = pyperclip.paste()
        if not clipboard_text:
            self.log("剪贴板内容为空，已跳过。")
            return
        
        self.log(f"正在转换文本: \"{clipboard_text[:30]}...\"")
        self.worker = TTSWorker(voice, clipboard_text, self)
        self.worker.finished.connect(self.on_tts_finished)
        self.worker.error.connect(self.on_tts_error)
        self.worker.start()

    def on_tts_finished(self, mp3_path):
        pyperclip.copy(mp3_path)
        self.log(f"成功！MP3 文件路径已复制到剪贴板: {mp3_path}")

    def on_tts_error(self, error_message):
        self.log(f"错误: {error_message}")

    def get_settings_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "clipboard_tts_settings.json")

    def save_settings(self):
        settings = {
            "selected_voice": self.get_selected_voice(),
            "hotkey": self.current_hotkey_label.text()
        }
        try:
            with open(self.get_settings_path(), "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            self.log(f"保存设置失败: {e}")

    def load_settings(self):
        path = self.get_settings_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                settings = json.load(f)
            
            # 加载快捷键
            hotkey = settings.get("hotkey")
            if hotkey and hotkey != "未设置":
                self.hotkey_input.setText(hotkey)
                self.on_set_hotkey()

            # 加载语音模型
            voice = settings.get("selected_voice")
            if voice and voice in self.voice_items:
                item = self.voice_items[voice]
                self.voice_tree.setCurrentItem(item)

        except Exception as e:
            self.log(f"加载设置失败: {e}")

    def closeEvent(self, event):
        self.save_settings()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ClipboardTTSApp()
    window.show()
    sys.exit(app.exec())
