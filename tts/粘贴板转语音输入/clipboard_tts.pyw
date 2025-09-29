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
from collections import defaultdict
from datetime import datetime
import threading

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView, QCheckBox, QComboBox
)
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QDesktopServices
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
        
        return loop.run_until_complete(_inner())
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
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_text = re.sub(r'[\\/:*?"<>|]', '_', self.text[:20].strip())
            file_name = f"tts_{timestamp}_{safe_text}{self.output_ext}"
            output_path = os.path.join(self.output_dir, file_name)

            await communicate.save(output_path)
            self.finished.emit(self.voice, output_path)
        except Exception as e:
            self.error.emit(self.voice, f"语音转换失败: {e}")

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
        self.hotkey_layout.addWidget(self.hotkey_label)
        self.hotkey_layout.addWidget(self.current_hotkey_label, 1)
        self.hotkey_layout.addWidget(self.record_hotkey_button)
        self.hotkey_layout.addWidget(self.convert_button)

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
        self.layout.addLayout(self.hotkey_layout)
        self.layout.addWidget(self.audio_group)
        self.layout.addWidget(self.log_view)

        # --- 连接信号和槽 ---
        self.record_hotkey_button.clicked.connect(self.start_hotkey_recording)
        self.convert_button.clicked.connect(lambda: self.trigger_conversion("button"))
        self.voice_tree.itemChanged.connect(self.on_voice_item_changed)
        self.output_device_combo.currentIndexChanged.connect(self.save_settings)
        self.monitor_device_combo.currentIndexChanged.connect(self.save_settings)
        self.refresh_devices_button.clicked.connect(self.refresh_audio_devices)

        self._loading_settings = False
        self.active_workers = []
        self.audio_player = None

        self.refresh_audio_devices(is_initial_load=True) # 初始加载
        self.load_settings()
        self.log("欢迎使用剪贴板语音助手！")
        self.log("1. 在下方“音频输出设置”中选择你的虚拟声卡和监听耳机。")
        self.log("2. 勾选一个或多个语音模型。")
        self.log("3. 点击“录制快捷键”，按下组合键后自动保存。")
        self.log("4. 使用快捷键或“立即转换”按钮，剪贴板文本将转为语音。")

    def log(self, message):
        self.log_view.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

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
            keyboard.add_hotkey(self.hotkey_string, lambda: self.trigger_conversion("hotkey"))
            self.log(f"快捷键 '{self.hotkey_string}' 已激活。")
        except Exception as exc:
            self.log(f"设置快捷键失败: {exc}")

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
        for voice in voices:
            self.log(f"[{voice}] 已加入转换队列。")
            worker = TTSWorker(voice, clean_text, self)
            self.active_workers.append(worker)
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

        finally:
            # 使用QTimer确保在UI更新后再重置标志
            QTimer.singleShot(0, lambda: setattr(self, '_loading_settings', False))

        self.setup_hotkey_listener()

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


if __name__ == "__main__":
    import traceback
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    print("Starting application...")
    try:
        app = QApplication(sys.argv)
        window = ClipboardTTSApp()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error starting application: {e}")
        traceback.print_exc()
        input("Press Enter to exit...")
