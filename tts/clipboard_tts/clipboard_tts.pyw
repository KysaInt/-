import asyncio
import json
import os
import sys
import subprocess
import importlib
import re
import tempfile
import time # 导入 time 模块
import hashlib
import traceback
from collections import defaultdict
from datetime import datetime
import threading

# ---- 可调参数 / Troubleshooting 开关 ----
# 默认改为“顺序”合成，避免一次性并发大量不同区域语音可能触发服务端速率/连接限制。
# 如果你确认网络稳定且需要并发，可将 PARALLEL_TTS 设为 True，并调节 MAX_PARALLEL_TTS。
PARALLEL_TTS = False           # False = 严格顺序处理；True = 限制并发
MAX_PARALLEL_TTS = 2           # 并发模式下的最大同时 TTS 数（不要设太大）
DETAILED_TTS_ERROR = True      # 输出更详细的异常堆栈，帮助排查“收不到语音”问题

# ---- 全局日志与崩溃捕获 ----
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
CRASH_LOG = os.path.join(LOG_DIR, "clipboard_tts_crash.log")
RUNTIME_LOG = os.path.join(LOG_DIR, "clipboard_tts_runtime.log")

def _append_log(path, text):
    try:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")
    except Exception:
        pass

def init_global_error_logging():
    def handle_exception(exc_type, exc_value, exc_tb):
        import traceback as _tb
        details = ''.join(_tb.format_exception(exc_type, exc_value, exc_tb))
        _append_log(CRASH_LOG, f"UNCAUGHT: {details}")
        # 继续默认打印（若有控制台）
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    def handle_unraisable(unraisable):
        _append_log(CRASH_LOG, f"UNRAISABLE: {unraisable.exctype} {unraisable.exc_value} attr={getattr(unraisable.object, '__class__', type(unraisable.object))}")
    sys.excepthook = handle_exception
    if hasattr(sys, 'unraisablehook'):
        sys.unraisablehook = handle_unraisable
    _append_log(RUNTIME_LOG, "程序启动，已安装全局异常钩子。")

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView, QCheckBox, QComboBox,
    QLineEdit, QFileDialog, QFrame
)
from PySide6.QtCore import QThread, Signal, Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtCore import QUrl

# --- 自动依赖安装 ---

def ensure_package(package_name, import_name=None):
    normalized_name = import_name or package_name.replace('-', '_')
    try:
        return importlib.import_module(normalized_name)
    except ImportError:
        print(f"未检测到 {package_name}，正在自动安装……")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            return importlib.import_module(normalized_name)
        except (subprocess.CalledProcessError, ImportError) as e:
            print(f"安装或导入 {package_name} 失败: {e}")
            # 在GUI中显示错误
            # For now, just exit or raise
            raise RuntimeError(f"无法加载核心依赖: {package_name}") from e


edge_tts = ensure_package("edge-tts", "edge_tts")
print("edge_tts imported")
pyperclip = ensure_package("pyperclip")
print("pyperclip imported")
keyboard = ensure_package("keyboard")
print("keyboard imported")
pydub = ensure_package("pydub")
print("pydub imported")
sounddevice = ensure_package("sounddevice", "sounddevice")
print("sounddevice imported")
numpy = ensure_package("numpy")
print("numpy imported")
soundfile = ensure_package("soundfile", "soundfile")
print("soundfile imported")

# --- 折叠面板组件 ---
class CollapsibleBox(QWidget):
    def __init__(self, title="设置", parent=None):
        super().__init__(parent)
        self.toggle_button = QPushButton(title)
        font = self.toggle_button.font()
        font.setBold(True)
        self.toggle_button.setFont(font)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.content_area = QWidget()
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        self.anim = QPropertyAnimation(self.content_area, b"maximumHeight", self)
        self.anim.setDuration(260)
        self.anim.setEasingCurve(QEasingCurve.InOutCubic)
        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0,0,0,0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)
        self.toggle_button.clicked.connect(self._on_toggle)
        self._update_title(False)

    def setContentLayout(self, layout):
        old = self.content_area.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                w = item.widget()
                if w:
                    w.setParent(None)
        self.content_area.setLayout(layout)

    def _on_toggle(self, checked):
        target = self.content_area.layout().sizeHint().height() if checked else 0
        self.anim.stop()
        self.anim.setStartValue(self.content_area.maximumHeight())
        self.anim.setEndValue(target)
        self.anim.start()
        self._update_title(checked)

    def _update_title(self, expanded):
        arrow = "▼" if expanded else "►"
        self.toggle_button.setText(f"{arrow} 设置")

# --- Edge API key / Auth 刷新逻辑 ---
# 说明: 部分情况下 edge-tts 内部使用的鉴权参数 (例如 X-Timestamp / authorization token)
# 在长时间运行或者网络环境变化后可能失效，导致 401。这里通过重新创建 VoicesManager
# 或 Communicate 之前刷新，强制 edge_tts 内部重新获取配置。虽然 edge-tts 本身会自动处理，
# 但根据实际需求增加显式刷新机制。

_EDGE_REFRESH_LOCK = threading.Lock()
_LAST_EDGE_REFRESH_TS = 0
_EDGE_REFRESH_INTERVAL = 30  # 秒; 避免频繁刷新，可根据需要调整

def refresh_edge_tts_key(force: bool = True):
    """强制通过 VoicesManager.create() 触发 edge_tts 内部重新协商参数/密钥。
    返回 True 表示成功，False 表示失败。
    """
    global _LAST_EDGE_REFRESH_TS
    with _EDGE_REFRESH_LOCK:
        now = time.time()
        if not force and (now - _LAST_EDGE_REFRESH_TS) < _EDGE_REFRESH_INTERVAL:
            return True
        try:
            async def _do():
                try:
                    # 创建一次即可; 结果不使用，只为触发内部请求
                    await edge_tts.VoicesManager.create()
                except Exception as inner_e:
                    raise inner_e
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(_do())
            _LAST_EDGE_REFRESH_TS = now
            print("Edge TTS 鉴权参数刷新成功")
            return True
        except Exception as e:
            print(f"刷新 Edge TTS 鉴权参数失败: {e}\n{traceback.format_exc()}")
            return False


VBCABLE_INSTALL_URL = "https://vb-audio.com/Cable/"
VIRTUAL_CABLE_NAMES = ["CABLE Input", "VB-Audio Virtual Cable"]


def get_audio_devices():
    """获取输入和输出设备列表"""
    devices = sounddevice.query_devices()
    input_devices = [(i, dev) for i, dev in enumerate(devices) if dev['max_input_channels'] > 0]
    output_devices = [(i, dev) for i, dev in enumerate(devices) if dev['max_output_channels'] > 0]
    return input_devices, output_devices


def load_voice_list():
    print("load_voice_list called")
    try:
        print("Trying to create VoicesManager...")
        async def _inner():
            manager = await edge_tts.VoicesManager.create()
            return manager.voices or []

        # Use the running event loop if it exists, otherwise create a new one
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            return loop.run_until_complete(_inner())
        except Exception as e:
            # 如果遇到 401/Unauthorized，尝试刷新后再重试一次
            if '401' in str(e) or 'Unauthorized' in str(e):
                print("首次加载语音列表发生 401，尝试刷新鉴权后重试一次…")
                try:
                    refresh_edge_tts_key(force=True)
                    return loop.run_until_complete(_inner())
                except Exception as e2:
                    print(f"重试仍失败: {e2}")
                    return []
            else:
                raise
    except Exception as e:
        print(f"Error in load_voice_list: {e}")
        return []


# --- TTS 转换核心 ---

class TTSWorker(QThread):
    finished = Signal(str, str)  # voice, mp3_path
    error = Signal(str, str)

    def __init__(self, voice: str, text: str, parent=None,
                 custom_output_dir: str | None = None,
                 use_custom_naming: bool = False):
        super().__init__(parent)
        self.voice = voice
        self.text = text
        self.output_ext = ".mp3"
        # 如果启用自定义目录则使用之，否则临时目录
        self.output_dir = custom_output_dir or tempfile.gettempdir()
        self.use_custom_naming = use_custom_naming and bool(custom_output_dir)

    async def tts_async(self):
        if not self.text.strip():
            self.error.emit(self.voice, "剪贴板内容为空。")
            return
        attempt = 0
        last_error = None
        while attempt < 2:  # 最多重试1次（总共2次尝试）
            try:
                if DETAILED_TTS_ERROR:
                    print(f"[DEBUG] 开始合成 voice={self.voice} attempt={attempt+1}")
                communicate = edge_tts.Communicate(self.text, self.voice)
                if self.use_custom_naming:
                    # 文件名 = 文本内容 + (语音模型名称)
                    # 为避免过长与非法字符：截断 + 哈希
                    raw_text = self.text.strip().replace('\n', ' ')
                    sanitized = re.sub(r'[\\/:*?"<>|]', '_', raw_text)
                    max_len = 80  # 控制主体长度，超过则截断并加哈希区分
                    if len(sanitized) > max_len:
                        h = hashlib.sha1(sanitized.encode('utf-8')).hexdigest()[:8]
                        sanitized = sanitized[:max_len] + '_' + h
                    base_name = f"{sanitized}({self.voice})"
                    file_name = base_name + self.output_ext
                    os.makedirs(self.output_dir, exist_ok=True)
                    output_path = os.path.join(self.output_dir, file_name)
                    # 如果已存在，添加序号
                    if os.path.exists(output_path):
                        counter = 1
                        while True:
                            alt = os.path.join(self.output_dir, f"{base_name}_{counter}{self.output_ext}")
                            if not os.path.exists(alt):
                                output_path = alt
                                break
                            counter += 1
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_text = re.sub(r'[\\/:*?"<>|]', '_', self.text[:20].strip())
                    file_name = f"tts_{timestamp}_{safe_text}{self.output_ext}"
                    output_path = os.path.join(self.output_dir, file_name)

                await communicate.save(output_path)
                if DETAILED_TTS_ERROR:
                    print(f"[DEBUG] 合成成功 voice={self.voice} path={output_path}")
                self.finished.emit(self.voice, output_path)
                return
            except Exception as e:
                err_text = str(e)
                if DETAILED_TTS_ERROR:
                    print(f"[DEBUG][ERROR] voice={self.voice} attempt={attempt+1} error={err_text}\n{traceback.format_exc()}")
                last_error = err_text
                if '401' in err_text or 'Unauthorized' in err_text:
                    # 刷新密钥后重试一次
                    try:
                        refresh_edge_tts_key(force=True)
                    except Exception:
                        pass
                    attempt += 1
                    continue
                # 某些地区/新语音可能暂时不可用或返回空流；提示用户稍后再试
                if 'empty audio' in err_text.lower() or 'no audio' in err_text.lower():
                    last_error += " | 可能是该语音暂时不可用或区域限制，稍后重试。"
                else:
                    break
        self.error.emit(self.voice, f"语音转换失败: {last_error}")

    def run(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self.tts_async())


class AudioPlayer(QThread):
    """在单独的线程中播放音频以避免UI阻塞; 如果有监听设备则并行播放，而不是顺序播放两遍"""
    finished = Signal()
    error = Signal(str)

    def __init__(self, file_path, primary_device_idx, monitor_device_idx=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.primary_device_idx = primary_device_idx
        self.monitor_device_idx = monitor_device_idx

    def _play_on_device(self, data, samplerate, device_idx):
        if device_idx is None or device_idx == -1:
            return
        stream = sounddevice.OutputStream(
            samplerate=samplerate,
            device=device_idx,
            channels=data.shape[1] if data.ndim > 1 else 1
        )
        stream.start()
        stream.write(data)
        stream.stop()
        stream.close()

    def run(self):
        try:
            data, samplerate = soundfile.read(self.file_path, dtype='float32')
            threads = []

            # 主输出设备
            if self.primary_device_idx is not None and self.primary_device_idx != -1:
                t_main = threading.Thread(target=self._play_on_device, args=(data, samplerate, self.primary_device_idx), daemon=True)
                threads.append(t_main)

            # 监听设备（不同于主设备时才播放）
            if (self.monitor_device_idx is not None and self.monitor_device_idx != -1 and
                self.monitor_device_idx != self.primary_device_idx):
                t_monitor = threading.Thread(target=self._play_on_device, args=(data, samplerate, self.monitor_device_idx), daemon=True)
                threads.append(t_monitor)

            # 启动线程
            for t in threads:
                t.start()
            # 等待全部播放结束
            for t in threads:
                t.join()

            self.finished.emit()
        except Exception as e:
            self.error.emit(f"播放音频失败: {e}\n{traceback.format_exc()}")


# --- 主应用界面 ---

class ClipboardTTSApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("剪贴板语音助手")
        self.setGeometry(100, 100, 550, 700)
        # 记录启动
        _append_log(RUNTIME_LOG, "构造 ClipboardTTSApp")

        # 启动即刷新一次 Edge TTS 鉴权
        try:
            if refresh_edge_tts_key(force=True):
                print("启动时已刷新 Edge TTS key")
            else:
                print("启动时刷新 Edge TTS key 失败")
        except Exception as e:
            print(f"启动刷新 Edge TTS key 异常: {e}")

        self.layout = QVBoxLayout(self)
        self.hotkey_string = None
        self.last_hotkey_trigger_time = 0  # 上次热键触发时间
        self.last_text_trigger_time = 0    # 上次相同文本触发时间
        self.last_clip_hash = None         # 最近一次转换文本哈希
        self.active_conversion = False     # 是否有一次批处理正在进行
        self.conversion_lock = threading.Lock()  # 串行化触发
        # 参数（可调）
        self.MIN_HOTKEY_INTERVAL = 1.2     # 热键最小触发间隔(秒)
        self.MIN_SAME_TEXT_INTERVAL = 3.0  # 相同文本最小重复间隔(秒)

        # --- UI 元素 ---
        self.label_voice = QLabel("选择一个或多个语音模型 (区域 / 语言 / 语音):")
        self.voice_tree = QTreeWidget()
        # 与 TTSSRT 对齐的四列表头：名称、性别、类别、个性
        self.voice_tree.setHeaderLabels(["名称", "性别", "类别", "个性"])
        header = self.voice_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        self.voice_tree.setSortingEnabled(True)
        self.voice_tree.sortByColumn(0, Qt.AscendingOrder)
        self.voice_items = {}
        self.populate_voices()
        # 基础样式（可根据需要进一步调整）
        # 使用系统默认配色，只保留间距；不强行设白底，避免深色主题下文字不可见
        self.voice_tree.setStyleSheet(
            "QTreeWidget::item { padding: 2px 4px; }"
            "QTreeWidget::item:selected { background: palette(highlight); color: palette(highlighted-text); }"
            "QHeaderView::section { padding: 4px; }"
        )

        self.hotkey_layout = QHBoxLayout()
        self.hotkey_label = QLabel("当前快捷键:")
        self.current_hotkey_label = QLabel("未设置")
        self.record_hotkey_button = QPushButton("录制快捷键")
        self.convert_button = QPushButton("立即转换")
        self.refresh_key_button = QPushButton("刷新鉴权")
        self.hotkey_layout.addWidget(self.hotkey_label)
        self.hotkey_layout.addWidget(self.current_hotkey_label, 1)
        self.hotkey_layout.addWidget(self.record_hotkey_button)
        self.hotkey_layout.addWidget(self.convert_button)
        self.hotkey_layout.addWidget(self.refresh_key_button)

        # --- 音频设备控制界面 ---
        self.audio_group = QWidget()
        audio_layout = QVBoxLayout(self.audio_group)
        audio_layout.setContentsMargins(0, 5, 0, 5)

        # 输出设备
        output_device_layout = QHBoxLayout()
        self.output_device_label = QLabel("语音输出到 (虚拟麦克风):")
        self.output_device_combo = QComboBox()
        output_device_layout.addWidget(self.output_device_label)
        output_device_layout.addWidget(self.output_device_combo, 1)

        # 监听设备
        monitor_device_layout = QHBoxLayout()
        self.monitor_device_label = QLabel("同时监听设备 (耳机/扬声器):")
        self.monitor_device_combo = QComboBox()
        monitor_device_layout.addWidget(self.monitor_device_label)
        monitor_device_layout.addWidget(self.monitor_device_combo, 1)

        # 刷新和提示
        actions_layout = QHBoxLayout()
        self.refresh_devices_button = QPushButton("刷新设备列表")
        self.cable_info_label = QLabel("未检测到虚拟声卡。 <a href='install'>点击此处下载安装</a>")
        self.cable_info_label.setOpenExternalLinks(False) # We handle the link click manually
        self.cable_info_label.linkActivated.connect(self.open_cable_install_url)
        actions_layout.addWidget(self.refresh_devices_button)
        actions_layout.addWidget(self.cable_info_label, 1, Qt.AlignRight)

        audio_layout.addLayout(output_device_layout)
        audio_layout.addLayout(monitor_device_layout)
        audio_layout.addLayout(actions_layout)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        self.layout.addWidget(self.label_voice)
        self.layout.addWidget(self.voice_tree)
        # --- 输出目录设置控件（后面塞进折叠面板） ---
        self.output_dir_checkbox = QCheckBox("修改地址")
        self.output_dir_label = QLabel("MP3 输出目录:")
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("未启用，使用临时目录")
        self.output_dir_edit.setEnabled(False)
        self.output_dir_browse = QPushButton("浏览")
        self.output_dir_browse.setEnabled(False)
        self.output_dir_open = QPushButton("打开")
        self.output_dir_open.setEnabled(False)

        # ---- 组装折叠设置面板 ----
        self.settings_box = CollapsibleBox("设置")
        settings_layout = QVBoxLayout()
        settings_layout.setContentsMargins(8,8,8,8)
        # 热键
        hotkey_frame = QFrame()
        hotkey_lay = QHBoxLayout(hotkey_frame)
        hotkey_lay.setContentsMargins(0,0,0,0)
        hotkey_lay.addLayout(self.hotkey_layout)
        settings_layout.addWidget(QLabel("快捷键与转换:"))
        settings_layout.addWidget(hotkey_frame)
        # 音频设备
        audio_frame = QFrame()
        af_lay = QVBoxLayout(audio_frame)
        af_lay.setContentsMargins(0,0,0,0)
        af_lay.addWidget(self.audio_group)
        settings_layout.addWidget(QLabel("音频设备:"))
        settings_layout.addWidget(audio_frame)
        # 输出目录
        outdir_frame = QFrame()
        of_lay = QHBoxLayout(outdir_frame)
        of_lay.setContentsMargins(0,0,0,0)
        of_lay.addWidget(self.output_dir_checkbox)
        of_lay.addWidget(self.output_dir_label)
        of_lay.addWidget(self.output_dir_edit, 1)
        of_lay.addWidget(self.output_dir_browse)
        of_lay.addWidget(self.output_dir_open)
        settings_layout.addWidget(QLabel("输出目录:"))
        settings_layout.addWidget(outdir_frame)
        self.settings_box.setContentLayout(settings_layout)
        self.layout.addWidget(self.settings_box)
        self.layout.addWidget(self.log_view)

        # --- 连接信号和槽 ---
        self.record_hotkey_button.clicked.connect(self.start_hotkey_recording)
        self.convert_button.clicked.connect(lambda: self.trigger_conversion("button"))
        self.refresh_key_button.clicked.connect(self.manual_refresh_edge_auth)
        self.voice_tree.itemChanged.connect(self.on_voice_item_changed)
        self.output_device_combo.currentIndexChanged.connect(self.save_settings)
        self.monitor_device_combo.currentIndexChanged.connect(self.save_settings)
        self.refresh_devices_button.clicked.connect(self.refresh_audio_devices)
        self.output_dir_checkbox.toggled.connect(self.on_output_dir_toggled)
        self.output_dir_browse.clicked.connect(self.browse_output_dir)
        self.output_dir_open.clicked.connect(self.open_output_dir)
        self.output_dir_edit.textChanged.connect(self.save_settings)

        self._loading_settings = False
        self.active_workers = []
        # 队列 / 并发控制
        self.voice_queue = []         # 待处理语音队列
        self.running_workers = 0      # 当前运行中的 worker 数
        self.parallel_tts = PARALLEL_TTS
        self.max_parallel = MAX_PARALLEL_TTS
        self.audio_player = None
        # 输出目录设置变量
        self.output_dir_enabled = False
        self.output_dir_path = ""

        self.refresh_audio_devices(is_initial_load=True) # 初始加载
        self.load_settings()
        self.log("欢迎使用剪贴板语音助手！")
        self.log("1. 在下方“音频输出设置”中选择你的虚拟声卡和监听耳机。")
        self.log("2. 勾选一个或多个语音模型。")
        self.log("3. 点击“录制快捷键”，按下组合键后自动保存。")
        self.log("4. 使用快捷键或“立即转换”按钮，剪贴板文本将转为语音。")

    def log(self, message):
        self.log_view.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        # 自动滚动到末尾
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

    def populate_voices(self):
        """构建三层（区域 -> 语言 -> 语音）树结构，参考 TTSSRT.pyw。"""
        try:
            voices_data = load_voice_list()
        except Exception as e:
            self.log(f"加载语音列表失败: {e}")
            voices_data = []

        if not voices_data:
            self.log("警告: 无法加载语音列表，使用回退语音集合。")
            voices_data = [
                {"ShortName": "zh-CN-XiaoxiaoNeural", "Gender": "Female", "Locale": "zh-CN", "StyleList": []},
                {"ShortName": "zh-CN-YunxiNeural", "Gender": "Male", "Locale": "zh-CN", "StyleList": []},
            ]

        # 语言前缀 -> 中文名称
        language_names = {
            "ar": "阿拉伯语", "bg": "保加利亚语", "ca": "加泰罗尼亚语", "cs": "捷克语", "cy": "威尔士语",
            "da": "丹麦语", "de": "德语", "el": "希腊语", "en": "英语", "es": "西班牙语",
            "et": "爱沙尼亚语", "fi": "芬兰语", "fr": "法语", "ga": "爱尔兰语", "he": "希伯来语",
            "hi": "印地语", "hr": "克罗地亚语", "hu": "匈牙利语", "id": "印度尼西亚语", "is": "冰岛语",
            "it": "意大利语", "ja": "日语", "ko": "韩语", "lt": "立陶宛语", "lv": "拉脱维亚语",
            "ms": "马来语", "mt": "马耳他语", "nb": "挪威语", "nl": "荷兰语", "pl": "波兰语",
            "pt": "葡萄牙语", "ro": "罗马尼亚语", "ru": "俄语", "sk": "斯洛伐克语", "sl": "斯洛文尼亚语",
            "sv": "瑞典语", "ta": "泰米尔语", "te": "泰卢固语", "th": "泰语", "tr": "土耳其语",
            "uk": "乌克兰语", "ur": "乌尔都语", "vi": "越南语", "zh": "中文",
        }

        regions = {
            "亚洲": ["zh", "ja", "ko", "vi", "th", "ms", "id", "hi", "ta", "te", "ur"],
            "欧洲": ["en", "fr", "de", "it", "es", "pt", "ru", "pl", "nl", "sv", "no", "da", "fi",
                    "el", "cs", "hu", "ro", "bg", "hr", "sk", "sl", "lt", "lv", "et", "is", "ga",
                    "cy", "mt", "uk"],
            "中东": ["ar", "he"],
            "美洲": ["en-US", "es-MX", "pt-BR", "fr-CA"],
            "大洋洲": ["en-AU", "en-NZ"],
            "非洲": ["af", "sw"],
        }

        voices_by_region_lang = defaultdict(lambda: defaultdict(list))

        for voice in voices_data:
            short_name = voice.get("ShortName") or voice.get("Name") or "UnknownVoice"
            locale = voice.get("Locale", "")  # e.g. zh-CN
            if not locale and '-' in short_name:
                # 尝试从名称推断
                locale = '-'.join(short_name.split('-')[:2])
            lang_prefix = locale.split('-')[0] if locale else ""  # zh

            # 区域判定
            region = "其他"
            for r, lang_list in regions.items():
                if lang_prefix in lang_list or locale in lang_list:
                    region = r
                    break

            # 语言显示文本
            if lang_prefix in language_names:
                lang_display = f"{locale} ({language_names[lang_prefix]})"
            else:
                lang_display = locale or "未知语言"

            voices_by_region_lang[region][lang_display].append(voice)

        self.voice_tree.clear()
        self.voice_items.clear()

        for region, lang_map in sorted(voices_by_region_lang.items()):
            region_item = QTreeWidgetItem(self.voice_tree, [region])
            region_item.setFlags(region_item.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
            region_item.setCheckState(0, Qt.Unchecked)

            for lang_display, voice_list in sorted(lang_map.items()):
                lang_item = QTreeWidgetItem(region_item, [lang_display])
                lang_item.setFlags(lang_item.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
                lang_item.setCheckState(0, Qt.Unchecked)

                for voice in sorted(voice_list, key=lambda v: v.get("ShortName", "")):
                    short_name = voice.get("ShortName", "未知语音")
                    gender = voice.get("Gender", "")
                    # "类别"列：使用 Locale；"个性"列：使用第一个 StyleList（如果存在）
                    locale = voice.get("Locale", "")
                    styles = voice.get("StyleList") or voice.get("Stylelist") or voice.get("StyleLists") or []
                    personality = styles[0] if isinstance(styles, (list, tuple)) and styles else ""
                    parts = [short_name, gender, locale, personality]
                    child = QTreeWidgetItem(lang_item, parts)
                    child.setFlags(child.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
                    child.setCheckState(0, Qt.Unchecked)
                    self.voice_items[short_name] = child

            # 默认展开亚洲及中文语言
            if region == "亚洲":
                region_item.setExpanded(True)
                for i in range(region_item.childCount()):
                    lang_item = region_item.child(i)
                    if 'zh' in lang_item.text(0).lower():
                        lang_item.setExpanded(True)

    def get_checked_voices(self):  # 覆盖旧逻辑以适配三层结构
        voices = []
        root = self.voice_tree.invisibleRootItem()
        for i in range(root.childCount()):  # region
            region_item = root.child(i)
            for j in range(region_item.childCount()):  # language
                lang_item = region_item.child(j)
                for k in range(lang_item.childCount()):  # voice
                    voice_item = lang_item.child(k)
                    if voice_item.checkState(0) == Qt.Checked:
                        voices.append(voice_item.text(0))
            # 兼容回退模式（如果没有子节点仍被选中）
            if region_item.childCount() == 0 and region_item.checkState(0) == Qt.Checked:
                voices.append(region_item.text(0))
        return voices

    def open_cable_install_url(self, link):
        QDesktopServices.openUrl(QUrl(VBCABLE_INSTALL_URL))
        self.log(f"正在打开虚拟声卡下载页面: {VBCABLE_INSTALL_URL}")

    def refresh_audio_devices(self, is_initial_load=False):
        self.log("正在刷新音频设备列表...")
        self._loading_settings = True # 刷新时暂停保存
        
        # 保存当前选择
        current_output_data = self.output_device_combo.currentData()
        current_monitor_data = self.monitor_device_combo.currentData()

        self.output_device_combo.clear()
        self.monitor_device_combo.clear()

        try:
            _, output_devices = get_audio_devices()
            if not output_devices:
                self.log("错误: 未找到任何音频输出设备。")
                return

            # 添加通用选项
            self.output_device_combo.addItem("禁用 (仅复制路径)", -1)
            self.monitor_device_combo.addItem("禁用", -1)

            # 填充设备列表
            for i, device in output_devices:
                self.output_device_combo.addItem(f"{i}: {device['name']}", i)
                self.monitor_device_combo.addItem(f"{i}: {device['name']}", i)

            # 尝试恢复之前的选择
            output_idx = self.output_device_combo.findData(current_output_data)
            if output_idx != -1: self.output_device_combo.setCurrentIndex(output_idx)
            
            monitor_idx = self.monitor_device_combo.findData(current_monitor_data)
            if monitor_idx != -1: self.monitor_device_combo.setCurrentIndex(monitor_idx)

            # 检查虚拟声卡
            self.check_for_virtual_cable(output_devices, is_initial_load)

        except Exception as e:
            self.log(f"无法加载音频设备: {e}")
        finally:
            # 使用QTimer确保在事件循环下一次迭代时重置标志
            QTimer.singleShot(0, self._reset_loading_flag)

    def _reset_loading_flag(self):
        self._loading_settings = False
        self.log("音频设备列表已刷新。")

    def check_for_virtual_cable(self, devices, is_initial_load=False):
        found_cable_device_id = -1
        for i, device in devices:
            for name in VIRTUAL_CABLE_NAMES:
                if name in device['name']:
                    found_cable_device_id = i
                    break
            if found_cable_device_id != -1:
                break
        
        if found_cable_device_id != -1:
            self.cable_info_label.setText("✅ 已检测到虚拟声卡!")
            self.log(f"检测到虚拟声卡: {self.output_device_combo.itemText(self.output_device_combo.findData(found_cable_device_id))}")
            # 如果是首次加载且用户未设置，则自动选择
            if is_initial_load and self.output_device_combo.property("user_set") is not True:
                idx = self.output_device_combo.findData(found_cable_device_id)
                if idx != -1:
                    self.output_device_combo.setCurrentIndex(idx)
                    self.log("已自动选择虚拟声卡作为输出设备。")
        else:
            self.cable_info_label.setText("⚠️ 未检测到虚拟声卡。 <a href='install'>点击此处下载安装</a>")
            self.log("提示: 未检测到虚拟声卡, 建议安装 VB-CABLE。")

    def on_voice_item_changed(self, item, column):
        if column == 0 and not self._loading_settings:
            self.save_settings()

    def start_hotkey_recording(self):
        self.record_hotkey_button.setText("录制中… (Esc取消)")
        self.log("请按下新的快捷键组合，完成后将自动保存。")
        QApplication.processEvents()

        if self.hotkey_string:
            try:
                keyboard.remove_hotkey(self.hotkey_string)
            except (KeyError, ValueError):
                pass

        try:
            hotkey = keyboard.read_hotkey(suppress=False)
            if hotkey == 'esc':
                self.log("已取消快捷键录制。")
            else:
                self.hotkey_string = hotkey
                self.log(f"快捷键已设置为: {self.hotkey_string.replace('+', ' + ').title()}")
        except Exception as e:
            self.log(f"录制快捷键失败: {e}")
        finally:
            self.record_hotkey_button.setText("录制快捷键")
            self.update_hotkey_display()
            self.setup_hotkey_listener()
            self.save_settings()

    def update_hotkey_display(self):
        if self.hotkey_string:
            pretty = " + ".join(k.strip().capitalize() for k in self.hotkey_string.split("+"))
            self.current_hotkey_label.setText(pretty)
        else:
            self.current_hotkey_label.setText("未设置")

    def setup_hotkey_listener(self):
        try:
            keyboard.remove_all_hotkeys()
        except Exception:
            pass

        if not self.hotkey_string:
            self.log("未设置快捷键，监听器未启动。")
            return
        try:
            # 包一层捕获，防止内部抛异常导致进程退出
            def _safe_trigger():
                try:
                    self.trigger_conversion("hotkey")
                except Exception as e:
                    self.log(f"热键触发异常: {e}")
                    _append_log(CRASH_LOG, f"HOTKEY ERROR: {e}\n{traceback.format_exc()}")
            keyboard.add_hotkey(self.hotkey_string, _safe_trigger)
            self.log(f"快捷键 '{self.hotkey_string}' 已激活。")
        except Exception as exc:
            self.log(f"设置快捷键失败: {exc}")
            _append_log(CRASH_LOG, f"设置快捷键失败: {exc}\n{traceback.format_exc()}")

    def trigger_conversion(self, source: str):
        now = time.time()

        # 1. 热键最小间隔防抖
        if source == "hotkey" and (now - self.last_hotkey_trigger_time) < self.MIN_HOTKEY_INTERVAL:
            self.log(f"⚠ 热键触发过快 (<{self.MIN_HOTKEY_INTERVAL:.1f}s)，忽略。")
            return

        # 2. 转换锁：避免在上一批还未结束时重复启动
        if self.active_conversion:
            self.log("⚠ 上一批转换仍在进行，忽略新的触发。")
            return

        clipboard_text = pyperclip.paste() or ""
        clean_text = clipboard_text.strip()
        if not clean_text:
            self.log("剪贴板内容为空，已跳过。")
            return

        # 3. 相同文本重复间隔检测
        clip_hash = hashlib.sha256(clean_text.encode('utf-8')).hexdigest()
        if self.last_clip_hash == clip_hash and (now - self.last_text_trigger_time) < self.MIN_SAME_TEXT_INTERVAL:
            self.log(f"⚠ 相同文本已在 {self.MIN_SAME_TEXT_INTERVAL:.0f}s 内转换，忽略。")
            return

        voices = self.get_checked_voices()
        if not voices:
            self.log("错误：请至少勾选一个语音模型。")
            return

        # 设置状态
        self.last_hotkey_trigger_time = now
        self.last_text_trigger_time = now
        self.last_clip_hash = clip_hash

        # 进入临界区
        with self.conversion_lock:
            if self.active_conversion:  # 双重检查
                self.log("⚠ 并发触发被阻止。")
                return
            self.active_conversion = True

        preview_line = clean_text.splitlines()[0][:40]
        self.log(f"收到转换请求 ({source})，内容: \"{preview_line}...\"")

        self.convert_button.setEnabled(False)
        # 构建队列
        self.voice_queue = list(voices)
        self.source_text = clean_text  # 保存文本
        if self.parallel_tts:
            # 启动最多 max_parallel 个
            for _ in range(min(self.max_parallel, len(self.voice_queue))):
                self._start_next_voice()
        else:
            # 严格顺序
            self._start_next_voice()

    def _start_next_voice(self):
        if not self.voice_queue:
            return
        if self.parallel_tts and self.running_workers >= self.max_parallel:
            return
        voice = self.voice_queue.pop(0)
        self.log(f"[{voice}] 开始转换...")
        custom_dir = None
        use_custom_naming = False
        if self.output_dir_enabled:
            # 若未手动填写路径，初始化为脚本同级 output
            if not self.output_dir_path:
                self.output_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
            custom_dir = self.output_dir_path
            use_custom_naming = True
        worker = TTSWorker(voice, self.source_text, self, custom_output_dir=custom_dir, use_custom_naming=use_custom_naming)
        self.active_workers.append(worker)
        self.running_workers += 1
        worker.finished.connect(self.on_worker_finished)
        worker.error.connect(self.on_worker_error)
        worker.start()

    def on_worker_finished(self, voice: str, mp3_path: str):
        worker = self.sender()
        self.log(f"[{voice}] 转换完成: {os.path.basename(mp3_path)}")
        
        output_device_idx = self.output_device_combo.currentData()
        monitor_device_idx = self.monitor_device_combo.currentData()

        if output_device_idx is not None and output_device_idx != -1:
            self.log(f"通过设备 '{self.output_device_combo.currentText()}' 播放音频...")
            if monitor_device_idx is not None and monitor_device_idx != -1:
                self.log(f"同时监听: '{self.monitor_device_combo.currentText()}'")

            # 清理之前的播放器实例
            if self.audio_player and self.audio_player.isRunning():
                self.audio_player.quit()
                self.audio_player.wait()

            self.audio_player = AudioPlayer(mp3_path, output_device_idx, monitor_device_idx)
            self.audio_player.finished.connect(lambda: self.log(f"[{voice}] 音频播放完毕。"))
            self.audio_player.error.connect(lambda msg: self.log(f"[{voice}] {msg}"))
            self.audio_player.start()
        else:
            pyperclip.copy(mp3_path)
            self.log(f"[{voice}] 未选择输出设备，MP3 路径已复制到剪贴板。")

        self._cleanup_worker(worker)

    def on_worker_error(self, voice: str, error_message: str):
        worker = self.sender()
        self.log(f"[{voice}] 错误: {error_message}")
        self._cleanup_worker(worker)

    def _cleanup_worker(self, worker):
        if worker in self.active_workers:
            self.active_workers.remove(worker)
            self.running_workers = max(0, self.running_workers - 1)
        # 顺序 / 限流 继续启动下一个
        if self.voice_queue:
            self._start_next_voice()
        if not self.active_workers:
            self.convert_button.setEnabled(True)
            # 释放转换状态
            with self.conversion_lock:
                self.active_conversion = False
        worker.deleteLater()

    def get_settings_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "clipboard_tts_settings.json")

    def save_settings(self):
        if self._loading_settings:
            return
        settings = {
            "hotkey": self.hotkey_string,
            "checked_voices": self.get_checked_voices(),
            "output_device_id": self.output_device_combo.currentData(),
            "monitor_device_id": self.monitor_device_combo.currentData(),
            "output_dir_enabled": self.output_dir_enabled,
            "output_dir_path": self.output_dir_path,
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
        except (json.JSONDecodeError, FileNotFoundError) as e:
            self.log(f"加载设置失败或设置文件为空: {e}")
            self.update_hotkey_display()
            return

        self._loading_settings = True
        try:
            self.apply_voice_checks(settings.get("checked_voices", []))
            self.hotkey_string = settings.get("hotkey")
            self.update_hotkey_display()
            
            output_device_id = settings.get("output_device_id")
            if output_device_id is not None:
                combo_index = self.output_device_combo.findData(output_device_id)
                if combo_index != -1:
                    self.output_device_combo.setCurrentIndex(combo_index)
                    self.output_device_combo.setProperty("user_set", True) # 标记用户已设置

            monitor_device_id = settings.get("monitor_device_id")
            if monitor_device_id is not None:
                combo_index = self.monitor_device_combo.findData(monitor_device_id)
                if combo_index != -1:
                    self.monitor_device_combo.setCurrentIndex(combo_index)

            self.output_dir_enabled = bool(settings.get("output_dir_enabled"))
            self.output_dir_checkbox.setChecked(self.output_dir_enabled)
            self.output_dir_path = settings.get("output_dir_path") or ""
            self.apply_output_dir_state()

        finally:
            # 使用QTimer确保在UI更新后再重置标志
            QTimer.singleShot(0, lambda: setattr(self, '_loading_settings', False))

        self.setup_hotkey_listener()

    # --- 输出目录相关 ---
    def on_output_dir_toggled(self, checked: bool):
        self.output_dir_enabled = checked
        if checked and not self.output_dir_path:
            self.output_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
        self.apply_output_dir_state()
        self.save_settings()

    def apply_output_dir_state(self):
        enabled = self.output_dir_enabled
        self.output_dir_edit.setEnabled(enabled)
        self.output_dir_browse.setEnabled(enabled)
        self.output_dir_open.setEnabled(enabled)
        if enabled:
            self.output_dir_edit.setText(self.output_dir_path)
        else:
            self.output_dir_edit.clear()

    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_dir_path or os.path.dirname(os.path.abspath(__file__)))
        if directory:
            self.output_dir_path = directory
            self.output_dir_edit.setText(directory)
            self.save_settings()
            self.log(f"已选择输出目录: {directory}")

    def open_output_dir(self):
        if not self.output_dir_path:
            self.log("未设置输出目录。")
            return
        try:
            os.makedirs(self.output_dir_path, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_dir_path))
        except Exception as e:
            self.log(f"打开目录失败: {e}")

    def apply_voice_checks(self, voices):
        target = set(voices or [])
        for voice_name, item in self.voice_items.items():
            state = Qt.Checked if voice_name in target else Qt.Unchecked
            item.setCheckState(0, state)

    def closeEvent(self, event):
        self.save_settings()
        try:
            keyboard.remove_all_hotkeys()
        except Exception:
            pass
        if self.audio_player and self.audio_player.isRunning():
            self.audio_player.quit()
            self.audio_player.wait()
        sounddevice.stop()
        super().closeEvent(event)

    # --- 手动刷新 Edge TTS 鉴权 ---
    def manual_refresh_edge_auth(self):
        self.refresh_key_button.setEnabled(False)
        self.refresh_key_button.setText("刷新中...")
        self.log("正在刷新 Edge TTS 鉴权参数...")

        def _worker():
            success = False
            try:
                success = refresh_edge_tts_key(force=True)
            except Exception as e:
                print(f"手动刷新线程异常: {e}\n{traceback.format_exc()}")
                success = False
            finally:
                # 回主线程更新（无论成功与否都恢复按钮）
                QTimer.singleShot(0, lambda: self._after_manual_refresh(success))
        threading.Thread(target=_worker, daemon=True).start()

    def _after_manual_refresh(self, success: bool):
        if success:
            self.log("Edge TTS 鉴权刷新成功。")
        else:
            self.log("Edge TTS 鉴权刷新失败，查看控制台或网络。")
        self.refresh_key_button.setEnabled(True)
        self.refresh_key_button.setText("刷新鉴权")


if __name__ == "__main__":
    import traceback
    # 初始化全局异常日志
    try:
        init_global_error_logging()
    except Exception:
        pass
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    print("Starting application...")
    try:
        app = QApplication(sys.argv)
        window = ClipboardTTSApp()
        window.show()
        rc = app.exec()
        _append_log(RUNTIME_LOG, f"QApplication 退出 rc={rc}")
        sys.exit(rc)
    except Exception as e:
        err = f"启动异常: {e}"
        print(err)
        traceback.print_exc()
        _append_log(CRASH_LOG, err + "\n" + traceback.format_exc())
        input("Press Enter to exit...")
