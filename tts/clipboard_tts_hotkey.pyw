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
    QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PySide6.QtCore import QThread, Signal, Qt, QObject

# --- 自动依赖安装 ---

def ensure_package(package_name, import_name=None):
    normalized_name = import_name or package_name.replace('-', '_')
    try:
        return importlib.import_module(normalized_name)
    except ImportError:
        print(f"未检测到 {package_name}，正在自动安装……")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return importlib.import_module(normalized_name)

edge_tts = ensure_package("edge-tts", "edge_tts")
print("edge_tts imported")
pyperclip = ensure_package("pyperclip")
print("pyperclip imported")
keyboard = ensure_package("pynput", "pynput.keyboard")
print("keyboard imported")


def load_voice_list():
    print("load_voice_list called")
    try:
        print("Trying to create VoicesManager...")
        import asyncio
        async def _inner():
            manager = await edge_tts.VoicesManager.create()
            return manager.voices or []

        print("Running asyncio...")
        return asyncio.run(_inner())
    except Exception as e:
        print(f"Error in load_voice_list: {e}")
        return []


# --- TTS 转换核心 ---

class TTSWorker(QThread):
    finished = Signal(str, str)  # voice, mp3_path
    error = Signal(str, str)

    def __init__(self, voice: str, text: str, parent=None):
        super().__init__(parent)
        self.voice = voice
        self.text = text
        self.output_ext = ".mp3"
        self.output_dir = tempfile.gettempdir()

    async def tts_async(self):
        if not self.text.strip():
            self.error.emit(self.voice, "剪贴板内容为空。")
            return

        try:
            communicate = edge_tts.Communicate(self.text, self.voice)
            # 使用时间戳和部分文本创建唯一文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_text = re.sub(r'[\\/:*?"<>|]', '_', self.text[:20].strip())
            file_name = f"tts_{timestamp}_{safe_text}{self.output_ext}"
            output_path = os.path.join(self.output_dir, file_name)

            await communicate.save(output_path)
            self.finished.emit(self.voice, output_path)
        except Exception as e:
            self.error.emit(self.voice, f"语音转换失败: {e}")

    def run(self):
        asyncio.run(self.tts_async())

# --- 快捷键监听 ---

class HotkeyListener(QObject):
    hotkey_pressed = Signal()

    def __init__(self, hotkey_str, parent=None):
        super().__init__(parent)
        self.hotkey_str = hotkey_str
        self.listener = None
        self.hotkey_tokens = self.parse_hotkey(hotkey_str)

    def parse_hotkey(self, hotkey_str):
        tokens = set()
        for part in hotkey_str.split('+'):
            token = part.strip().lower()
            if not token:
                continue
            tokens.add(token)
        if not tokens:
            raise ValueError("无效的快捷键组合")
        return tokens

    def _normalize_key(self, key):
        try:
            if hasattr(key, "char") and key.char:
                return key.char.lower()
        except AttributeError:
            pass
        name = getattr(key, "name", "") or str(key)
        return name.lower()

    def on_press(self, key):
        token = self._normalize_key(key)
        if token in self.hotkey_tokens:
            self.pressed_tokens.add(token)
            if self.pressed_tokens == self.hotkey_tokens:
                self.hotkey_pressed.emit()

    def on_release(self, key):
        token = self._normalize_key(key)
        if token in self.pressed_tokens:
            self.pressed_tokens.remove(token)

    def start(self):
        if self.listener:
            self.listener.stop()
        self.pressed_tokens = set()
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

    def stop(self):
        if self.listener:
            self.listener.stop()
            self.listener = None
        self.pressed_tokens = set()

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
        self.record_hotkey_button = QPushButton("录制快捷键")
        self.convert_button = QPushButton("立即转换")
        self.hotkey_layout.addWidget(self.hotkey_label)
        self.hotkey_layout.addWidget(self.current_hotkey_label, 1)
        self.hotkey_layout.addWidget(self.record_hotkey_button)
        self.hotkey_layout.addWidget(self.convert_button)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        self.layout.addWidget(self.label_voice)
        self.layout.addWidget(self.voice_tree)
        self.layout.addLayout(self.hotkey_layout)
        self.layout.addWidget(self.log_view)

        # --- 连接信号和槽 ---
        self.record_hotkey_button.clicked.connect(self.start_hotkey_recording)
        self.convert_button.clicked.connect(lambda: self.trigger_conversion("button"))
        self.voice_tree.itemChanged.connect(self.on_voice_item_changed)

        self._loading_settings = False
        self.active_workers = []
        self.record_listener = None
        self.recording_active = False
        self.hotkey_string = None

        self.load_settings()
        self.log("欢迎使用剪贴板语音助手！")
        self.log("1. 勾选一个或多个语音模型。")
        self.log("2. 点击“录制快捷键”，按下组合键后松开即可保存。")
        self.log("3. 使用快捷键或“立即转换”按钮，剪贴板文本将转为语音并复制MP3路径。")

    def log(self, message):
        self.log_view.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def populate_voices(self):
        print("Starting populate_voices...")
        # Temporarily add some dummy voices for testing
        dummy_voices = [
            {"ShortName": "zh-CN-XiaoxiaoNeural", "Gender": "Female", "Locale": "zh-CN"},
            {"ShortName": "zh-CN-YunxiNeural", "Gender": "Male", "Locale": "zh-CN"},
        ]
        
        print("Processing dummy voices...")
        locales = {}
        for voice in dummy_voices:
            locale = voice.get("Locale", "未知")
            locales.setdefault(locale, []).append(voice)

        for locale, voice_list in sorted(locales.items()):
            locale_name = locale
            locale_item = QTreeWidgetItem(self.voice_tree, [locale_name, "", locale])
            locale_item.setFlags(locale_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
            locale_item.setCheckState(0, Qt.Unchecked)

            for voice in sorted(voice_list, key=lambda v: v.get("ShortName", "")):
                short_name = voice.get("ShortName") or voice.get("Name") or "未知语音"
                gender = voice.get("Gender", "")
                region_text = voice.get("Locale", locale)

                child = QTreeWidgetItem(locale_item, [short_name, gender, region_text])
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
                child.setCheckState(0, Qt.Unchecked)
                self.voice_items[short_name] = child

            if locale.lower().startswith("zh"):
                self.voice_tree.expandItem(locale_item)

        if self.voice_tree.topLevelItemCount() > 0:
            first_locale = self.voice_tree.topLevelItem(0)
            if first_locale and first_locale.childCount() > 0:
                first_locale.child(0).setCheckState(0, Qt.Checked)

        print("populate_voices completed")

    def on_voice_item_changed(self, item, column):
        if column != 0 or self._loading_settings:
            return
        if item.parent() is None and item.childCount() == 0:
            return
        self.save_settings()

    def get_checked_voices(self):
        voices = []
        root = self.voice_tree.invisibleRootItem()
        for i in range(root.childCount()):
            locale_item = root.child(i)
            for j in range(locale_item.childCount()):
                voice_item = locale_item.child(j)
                if voice_item.checkState(0) == Qt.Checked:
                    voices.append(voice_item.text(0))
        return voices

    def start_hotkey_recording(self):
        if self.recording_active:
            return

        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener = None

        self.recording_active = True
        self.recorded_sequence = []
        self.active_record_keys = set()
        self.record_hotkey_button.setText("录制中… (按 Esc 取消)")
        self.log("请按下新的快捷键组合，松开后自动保存。")

        def on_press(key):
            if not self.recording_active:
                return False
            key_str = self._normalize_key_for_storage(key)
            if key_str == "esc":
                self.log("已取消快捷键录制。")
                self._end_hotkey_recording(cancel=True)
                return False
            if key_str not in self.recorded_sequence:
                self.recorded_sequence.append(key_str)
            self.active_record_keys.add(key_str)
            self.update_hotkey_display(self.recorded_sequence)

        def on_release(key):
            if not self.recording_active:
                return False
            key_str = self._normalize_key_for_storage(key)
            self.active_record_keys.discard(key_str)
            if not self.active_record_keys and self.recorded_sequence:
                self._end_hotkey_recording(cancel=False)
                return False

        self.record_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.record_listener.start()

    def _normalize_key_for_storage(self, key):
        try:
            if hasattr(key, "char") and key.char:
                return key.char.lower()
        except AttributeError:
            pass
        name = getattr(key, "name", "") or str(key)
        return name.lower()

    def _end_hotkey_recording(self, cancel: bool):
        if self.record_listener:
            self.record_listener.stop()
            self.record_listener = None
        self.recording_active = False
        self.record_hotkey_button.setText("录制快捷键")

        if cancel or not self.recorded_sequence:
            self.update_hotkey_display([])
            if self.hotkey_string:
                self.setup_hotkey_listener()
            return

        self.hotkey_string = "+".join(self.recorded_sequence)
        self.update_hotkey_display()
        self.setup_hotkey_listener()
        self.log(f"快捷键已设置为: {self.current_hotkey_label.text()}")
        self.save_settings()

    def update_hotkey_display(self, sequence=None):
        if sequence is None:
            if self.hotkey_string:
                sequence = self.hotkey_string.split("+")
            else:
                sequence = []
        pretty = " + ".join(self._format_key_for_display(k) for k in sequence)
        self.current_hotkey_label.setText(pretty if pretty else "未设置")

    def _format_key_for_display(self, key_name: str) -> str:
        if len(key_name) == 1:
            return key_name.upper()
        mapping = {
            "ctrl": "Ctrl",
            "ctrl_l": "Ctrl",
            "ctrl_r": "Ctrl",
            "alt": "Alt",
            "alt_l": "Alt",
            "alt_r": "Alt",
            "shift": "Shift",
            "shift_l": "Shift",
            "shift_r": "Shift",
            "cmd": "Cmd",
            "cmd_l": "Cmd",
            "cmd_r": "Cmd",
            "win": "Win",
            "super": "Super",
        }
        return mapping.get(key_name, key_name.capitalize())

    def setup_hotkey_listener(self):
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener = None
        if not self.hotkey_string:
            return
        try:
            self.hotkey_listener = HotkeyListener(self.hotkey_string, self)
            self.hotkey_listener.hotkey_pressed.connect(lambda: self.trigger_conversion("hotkey"))
            self.hotkey_listener.start()
        except Exception as exc:
            self.log(f"设置快捷键失败: {exc}")
            self.hotkey_listener = None

    def trigger_conversion(self, source: str):
        voices = self.get_checked_voices()
        if not voices:
            self.log("错误：请至少勾选一个语音模型。")
            return

        clipboard_text = pyperclip.paste()
        if not clipboard_text or not clipboard_text.strip():
            self.log("剪贴板内容为空，已跳过。")
            return

        preview_line = clipboard_text.strip().splitlines()[0][:40]
        if source == "hotkey":
            self.log(f"快捷键触发，开始转换：\"{preview_line}...\"")
        else:
            self.log(f"手动转换触发，开始转换：\"{preview_line}...\"")

        self.convert_button.setEnabled(False)
        for voice in voices:
            self.log(f"[{voice}] 已加入转换队列。")
            worker = TTSWorker(voice, clipboard_text, self)
            self.active_workers.append(worker)
            worker.finished.connect(lambda v, path, w=worker: self.on_worker_finished(v, path, w))
            worker.error.connect(lambda v, msg, w=worker: self.on_worker_error(v, msg, w))
            worker.start()

    def on_worker_finished(self, voice: str, mp3_path: str, worker):
        pyperclip.copy(mp3_path)
        self.log(f"[{voice}] 转换完成，MP3 路径已复制：{mp3_path}")
        self._cleanup_worker(worker)

    def on_worker_error(self, voice: str, error_message: str, worker):
        self.log(f"[{voice}] 错误: {error_message}")
        self._cleanup_worker(worker)

    def _cleanup_worker(self, worker):
        if worker in self.active_workers:
            self.active_workers.remove(worker)
        if not self.active_workers:
            self.convert_button.setEnabled(True)
        worker.deleteLater()

    def get_settings_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "clipboard_tts_settings.json")

    def save_settings(self):
        if self._loading_settings:
            return
        settings = {
            "hotkey": self.hotkey_string,
            "checked_voices": self.get_checked_voices(),
        }
        try:
            with open(self.get_settings_path(), "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"保存设置失败: {e}")

    def load_settings(self):
        path = self.get_settings_path()
        if not os.path.exists(path):
            self.update_hotkey_display()
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception as e:
            self.log(f"加载设置失败: {e}")
            self.update_hotkey_display()
            return

        self._loading_settings = True
        try:
            voices = settings.get("checked_voices")
            if voices is None:
                voices = settings.get("selected_voices")
            if voices is None:
                legacy_voice = settings.get("selected_voice")
                voices = [legacy_voice] if legacy_voice else []
            if isinstance(voices, str):
                voices = [voices]
            self.apply_voice_checks(voices)
            self.hotkey_string = settings.get("hotkey") or None
            self.update_hotkey_display()
        finally:
            self._loading_settings = False

        self.setup_hotkey_listener()

    def apply_voice_checks(self, voices):
        target = set(voices or [])
        for voice_name, item in self.voice_items.items():
            state = Qt.Checked if voice_name in target else Qt.Unchecked
            item.setCheckState(0, state)

    def closeEvent(self, event):
        self.save_settings()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        if self.record_listener:
            self.record_listener.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    print("Starting application...")
    try:
        app = QApplication(sys.argv)
        print("QApplication created")
        window = ClipboardTTSApp()
        print("Window created")
        window.show()
        print("Window shown")
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
