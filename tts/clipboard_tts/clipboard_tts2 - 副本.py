import asyncio
import json
import os
import sys
import subprocess
import importlib
import re
import tempfile
import time  # 导入 time 模块
import hashlib
import traceback
from collections import defaultdict
from datetime import datetime
import threading
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict
import random

try:
    import httpx  # 供模拟浏览器获取 token
except ImportError:  # 延迟安装
    httpx = None

# ---- 可调参数 / Troubleshooting 开关 ----
PARALLEL_TTS = False
MAX_PARALLEL_TTS = 2
DETAILED_TTS_ERROR = True
DEBUG_PRINT = False

# ---- 全局日志（已禁用文件写入，根据需求取消 runtime/crash log） ----
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
CRASH_LOG = None  # 原文件路径不再使用
RUNTIME_LOG = None

def _append_log(path, text):
    # 日志文件写入被需求取消；保留函数避免引用报错，可改为 print 或直接忽略
    return

def dprint(*args, **kwargs):
    if DEBUG_PRINT:
        print(*args, **kwargs)

def sanitize_filename(text: str, voice: str, ext: str = ".mp3", max_len: int = 80) -> str:
    raw = (text or "").strip().replace('\n', ' ')
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', raw)
    if len(sanitized) > max_len:
        h = hashlib.sha1(sanitized.encode('utf-8')).hexdigest()[:8]
        sanitized = sanitized[:max_len] + '_' + h
    return f"{sanitized}({voice}){ext}"

def ensure_dir(path: str):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass

@dataclass
class AppSettings:
    hotkey: Optional[str] = None
    checked_voices: List[str] = field(default_factory=list)
    output_device_id: Optional[int] = None
    monitor_device_id: Optional[int] = None
    output_dir_enabled: bool = False
    output_dir_path: Optional[str] = None
    panel_states: Dict[str, bool] = field(default_factory=lambda: {
        "voice_expanded": True,
        "settings_expanded": True,
        "log_expanded": True,
    })
    panel_order: List[str] = field(default_factory=lambda: ["settings", "voice", "log"])
    splitter_sizes: List[int] = field(default_factory=list)
    saved_panel_sizes: Dict[str, Optional[int]] = field(default_factory=lambda: {"voice": None, "log": None})
    expanded_regions: List[str] = field(default_factory=list)          # 新增：区域节点展开状态
    expanded_languages: List[str] = field(default_factory=list)        # 新增：语言节点展开状态 (格式 Region||Language)
    window_geometry: List[int] = field(default_factory=list)           # [x,y,w,h]
    style_settings: Dict[str, any] = field(default_factory=dict)       # 新增：SSML 风格设置

    @classmethod
    def load_from_file(cls, path: str):
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            allowed = {k: data.get(k) for k in cls.__dataclass_fields__.keys()}
            return cls(**allowed)
        except Exception:
            return cls()

    def save_to_file(self, path: str):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

# ---- 新增：SSML/语音效果控制 ----
@dataclass
class StyleSettings:
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"
    style: str = "default"
    style_degree: float = 1.0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            return cls()
        # 过滤掉不存在于 dataclass 字段中的键
        allowed_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in allowed_keys}
        return cls(**filtered_data)

def init_global_error_logging():
    # 保留接口但不写入文件；如需调试可改用 print。
    def handle_exception(exc_type, exc_value, exc_tb):
        try:
            sys.__excepthook__(exc_type, exc_value, exc_tb)
        except Exception:
            pass
    def handle_unraisable(unraisable):
        # 静默忽略
        pass
    sys.excepthook = handle_exception
    if hasattr(sys, 'unraisablehook'):
        sys.unraisablehook = handle_unraisable

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
            raise RuntimeError(f"无法加载核心依赖: {package_name}") from e

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView, QCheckBox, QComboBox,
    QLineEdit, QFileDialog, QFrame, QSplitter, QSizePolicy, QSlider, QGridLayout
)
from PySide6.QtCore import QThread, Signal, Qt, QTimer, QPropertyAnimation, QEasingCurve, QEvent
from PySide6.QtGui import QDesktopServices, QTextCursor, QKeySequence
from PySide6.QtCore import QUrl
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
    """折叠面板 + 可用于 QSplitter 中：
    - 折叠只显示标题按钮高度
    - 发出 toggled(bool) 信号，方便父级重新调整分配
    - 在 splitter 中不使用内容高度动画，以免干扰拖动
    """
    toggled = Signal(bool)
    def __init__(self, title: str = "面板", parent=None, expanded: bool = False):
        super().__init__(parent)
        self._base_title = title
        self.toggle_button = QPushButton()
        f = self.toggle_button.font(); f.setBold(True); self.toggle_button.setFont(f)
        self.toggle_button.setCheckable(True)
        self.content_area = QWidget()
        outer = QVBoxLayout(self)
        outer.setSpacing(0); outer.setContentsMargins(0,0,0,0)
        outer.addWidget(self.toggle_button)
        outer.addWidget(self.content_area)
        self.toggle_button.clicked.connect(self._on_clicked)
        self.set_expanded(expanded)

    def header_height(self):
        return self.toggle_button.sizeHint().height()

    def is_expanded(self):
        return self.toggle_button.isChecked()

    def setContentLayout(self, layout):
        old = self.content_area.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                w = item.widget()
                if w:
                    w.setParent(None)
        self.content_area.setLayout(layout)
        if not self.is_expanded():
            self.content_area.setVisible(False)

    def set_expanded(self, expanded: bool):
        self.toggle_button.setChecked(expanded)
        self.content_area.setVisible(expanded)
        self._update_title(expanded)
        self.toggled.emit(expanded)

    def _on_clicked(self):
        self.set_expanded(self.toggle_button.isChecked())

    def _update_title(self, expanded: bool):
        arrow = "▼" if expanded else "►"
        self.toggle_button.setText(f"{arrow} {self._base_title}")

# --- Edge API key / Auth 刷新逻辑 ---
# 说明: 部分情况下 edge-tts 内部使用的鉴权参数 (例如 X-Timestamp / authorization token)
# 在长时间运行或者网络环境变化后可能失效，导致 401。这里通过重新创建 VoicesManager
# 或 Communicate 之前刷新，强制 edge_tts 内部重新获取配置。虽然 edge-tts 本身会自动处理，
# 但根据实际需求增加显式刷新机制。

_EDGE_REFRESH_LOCK = threading.Lock()
_EDGE_TOKEN_EXPIRE = 0.0
_EDGE_TOKEN_CACHE: Dict[str, str] = {}
_EDGE_TOKEN_LIFETIME = 60 * 8  # 微软 session token 在当前流程下通常较短，这里设置 8 分钟后强制刷新

EDGE_TTS_BASE_HEADERS = {
    # 伪造常见 Edge 浏览器 UA
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
}

def _ensure_httpx():
    global httpx
    if httpx is None:
        try:
            import importlib
            import subprocess, sys as _sys
            subprocess.check_call([_sys.executable, '-m', 'pip', 'install', 'httpx'])
            httpx = importlib.import_module('httpx')  # type: ignore
        except Exception as e:
            raise RuntimeError(f"无法安装 httpx 用于获取 Edge token: {e}")
    return httpx

async def _fetch_edge_token_async():
    """模拟浏览器访问，提取 Edge TTS 所需的 session token。
    注意：微软在线 TTS 页面变动较快，此实现依赖当前公开页面结构，仅供临时稳定。
    如果失败，返回 None。
    流程：
      1. 访问 https://azure.microsoft.com/en-us/products/ai-services/text-to-speech/ 获取初始 cookies
      2. 请求静态 js (若需要) 或直接访问 https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1 获取会话 token
    """
    _ensure_httpx()
    async with httpx.AsyncClient(timeout=10, headers=EDGE_TTS_BASE_HEADERS) as client:  # type: ignore
        # Step1: 打页面获取 cookie
        landing_urls = [
            "https://azure.microsoft.com/en-us/products/ai-services/text-to-speech/",
            "https://www.microsoft.com/en-us/edge/features/immersive-reader"
        ]
        for url in landing_urls:
            try:
                await client.get(url)
            except Exception:
                pass
        # Step2: 获取 token 接口
        # 旧接口： https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1
        # 新接口有时出现 region 参数，这里先尝试旧接口
        token_url_candidates = [
            "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1",
            "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1?trustedclient=1",
        ]
        for token_url in token_url_candidates:
            try:
                r = await client.get(token_url, headers={
                    **EDGE_TTS_BASE_HEADERS,
                    "Pragma": "no-cache",
                    "Accept": "*/*",
                    "Origin": "https://azure.microsoft.com",
                    "Referer": "https://azure.microsoft.com/",
                })
                if r.status_code == 200:
                    # 响应正文为 token 字符串
                    token_text = r.text.strip().strip('"')
                    if token_text and len(token_text) < 200:  # 简单长度校验
                        return token_text
                # 某些情况下 401/403，继续尝试下一个
            except Exception:
                continue
    return None

def get_edge_session_token(force: bool = False) -> Optional[str]:
    """获取/缓存 Edge session token。"""
    global _EDGE_TOKEN_EXPIRE, _EDGE_TOKEN_CACHE
    with _EDGE_REFRESH_LOCK:
        now = time.time()
        cached = _EDGE_TOKEN_CACHE.get('token') if _EDGE_TOKEN_EXPIRE > now and not force else None
        if cached:
            return cached
        # 重新获取（同步包装）
        try:
            try:
                loop = asyncio.get_running_loop()
                needs_close = False
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                needs_close = True
            token = loop.run_until_complete(_fetch_edge_token_async())
            if needs_close:
                try:
                    loop.close()
                except Exception:
                    pass
            if token:
                _EDGE_TOKEN_CACHE['token'] = token
                _EDGE_TOKEN_EXPIRE = time.time() + _EDGE_TOKEN_LIFETIME
                return token
            return None
        except Exception as e:
            print(f"获取 Edge token 失败: {e}")
            return None

def refresh_edge_tts_key(force: bool = True):
    """刷新 edge-tts 内部上下文：
    1. 先确保 session token 可用
    2. 调用 VoicesManager.create() 触发内部 (Authorization) 刷新
    """
    token = get_edge_session_token(force=force)
    if not token:
        print("未能获取 Edge session token，刷新终止。")
        return False
    try:
        async def _do():
            try:
                await edge_tts.VoicesManager.create()
            except Exception as inner_e:
                raise inner_e
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(_do())
        print("Edge TTS 上下文刷新成功 (含 session token)")
        return True
    except Exception as e:
        print(f"刷新 Edge TTS 上下文失败: {e}\n{traceback.format_exc()}")
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
    # 确保 token
    if not get_edge_session_token(force=False):
        get_edge_session_token(force=True)
    try:
        async def _inner():
            manager = await edge_tts.VoicesManager.create()
            return manager.voices or []
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_inner())
        except Exception as e:
            if '401' in str(e) or 'Unauthorized' in str(e):
                print("获取 voices 401，强制刷新 token 后重试…")
                refresh_edge_tts_key(force=True)
                return loop.run_until_complete(_inner())
            print(f"加载 voices 异常: {e}")
            return []
    except Exception as e:
        print(f"Error in load_voice_list outer: {e}")
        return []


def _create_ssml(text: str, voice: str, style_settings: StyleSettings) -> str:
    """根据文本和风格设置创建 SSML 字符串，支持 [break=500ms] 与 [style=cheerful,1.2] 片段。"""
    if not text or not text.strip():
        return ""

    # 解析语音短名中的语言区域，如 zh-CN-XiaoxiaoNeural -> zh-CN
    locale = "en-US"
    try:
        parts = voice.split("-")
        if len(parts) >= 2:
            locale = f"{parts[0]}-{parts[1]}"
    except Exception:
        pass

    def html_escape(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    src = text

    # 支持 [break=500ms] / [pause=1s]
    def _replace_break(m):
        val = m.group(2)
        unit = m.group(3) or "ms"
        # 统一成 ms
        try:
            if unit.lower().startswith("s"):
                # 秒转毫秒
                ms = float(val) * 1000
            else:
                ms = float(val)
            ms_int = max(0, int(ms))
            return f"<break time=\"{ms_int}ms\"/>"
        except Exception:
            return ""

    src = re.sub(r"\[(break|pause)\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*(ms|s)?\]", _replace_break, src, flags=re.IGNORECASE)

    # 解析 [style=cheerful,1.2]...[/style]
    styled_segments: list[tuple[str, Optional[str], Optional[float]]] = []

    def _split_styles(s: str):
        # 将包含 [style=...]...[/style] 的文本拆成 (type, content, style, degree) 片段
        pattern = re.compile(r"\[style\s*=\s*([a-zA-Z0-9_\-]+)(?:\s*,\s*([0-9.]+))?\](.*?)\[/style\]", re.IGNORECASE | re.DOTALL)
        pos = 0
        for m in pattern.finditer(s):
            if m.start() > pos:
                yield ("plain", s[pos:m.start()], None, None)
            sty = m.group(1)
            deg = m.group(2)
            try:
                degf = float(deg) if deg is not None else None
            except Exception:
                degf = None
            yield ("styled", m.group(3), sty, degf)
            pos = m.end()
        if pos < len(s):
            yield ("plain", s[pos:], None, None)

    # 构建 SSML 片段
    parts_xml: list[str] = []
    found_style_segment = False
    for seg_type, seg_text, seg_style, seg_degree in _split_styles(src):
        esc = html_escape(seg_text)
        if seg_type == "styled" and seg_style:
            found_style_segment = True
            deg_val = seg_degree if seg_degree is not None else style_settings.style_degree
            parts_xml.append(
                f"<mstts:express-as style=\"{seg_style}\" styledegree=\"{deg_val}\">"
                f"<prosody rate=\"{style_settings.rate}\" pitch=\"{style_settings.pitch}\" volume=\"{style_settings.volume}\">{esc}</prosody>"
                f"</mstts:express-as>"
            )
        else:
            # 使用默认风格（若用户在设置中选了非 default，则也应用）
            if style_settings.style and style_settings.style != "default":
                parts_xml.append(
                    f"<mstts:express-as style=\"{style_settings.style}\" styledegree=\"{style_settings.style_degree}\">"
                    f"<prosody rate=\"{style_settings.rate}\" pitch=\"{style_settings.pitch}\" volume=\"{style_settings.volume}\">{esc}</prosody>"
                    f"</mstts:express-as>"
                )
            else:
                parts_xml.append(
                    f"<prosody rate=\"{style_settings.rate}\" pitch=\"{style_settings.pitch}\" volume=\"{style_settings.volume}\">{esc}</prosody>"
                )

    inner = "".join(parts_xml)

    # 顶层 speak/voice 包裹
    if "mstts:express-as" in inner:
        return (
            f"<speak version=\"1.0\" xmlns=\"http://www.w3.org/2001/10/synthesis\" xmlns:mstts=\"http://www.w3.org/2001/mstts\" xml:lang=\"{locale}\">"
            f"<voice name=\"{voice}\">{inner}</voice>"
            f"</speak>"
        )
    else:
        return (
            f"<speak version=\"1.0\" xmlns=\"http://www.w3.org/2001/10/synthesis\" xml:lang=\"{locale}\">"
            f"<voice name=\"{voice}\">{inner}</voice>"
            f"</speak>"
        )

# --- TTS 转换核心 ---

class TTSWorker(QThread):
    finished = Signal(str, str)  # voice, mp3_path
    error = Signal(str, str)

    def __init__(self, voice: str, text: str, parent=None,
                 custom_output_dir: str | None = None,
                 use_custom_naming: bool = False,
                 style_settings: Optional[StyleSettings] = None):
        super().__init__(parent)
        self.voice = voice
        self.text = text
        self.style_settings = style_settings or StyleSettings()
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
                # 根据设置创建 SSML
                ssml_text = _create_ssml(self.text, self.voice, self.style_settings)

                # 合成前确保 token 有效
                if not get_edge_session_token(force=False):
                    get_edge_session_token(force=True)
                if DETAILED_TTS_ERROR:
                    print(f"[DEBUG] 开始合成 voice={self.voice} attempt={attempt+1}")
                
                # 使用 SSML 文本进行 Communicate（edge-tts 会根据 <speak> 自动识别为 SSML）
                communicate = edge_tts.Communicate(text=ssml_text, voice=self.voice)

                if self.use_custom_naming:
                    ensure_dir(self.output_dir)
                    file_name = sanitize_filename(self.text, self.voice, self.output_ext)
                    output_path = os.path.join(self.output_dir, file_name)
                    base, ext = os.path.splitext(output_path)
                    counter = 1
                    while os.path.exists(output_path):
                        output_path = f"{base}_{counter}{ext}"
                        counter += 1
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_text = re.sub(r'[\\/:*?"<>|]', '_', self.text[:20].strip())
                    ensure_dir(self.output_dir)
                    output_path = os.path.join(self.output_dir, f"tts_{timestamp}_{safe_text}{self.output_ext}")

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
                    # 刷新 token + 上下文
                    refresh_edge_tts_key(force=True)
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
        # 更窄默认尺寸，如果存在设置文件会在稍后覆盖
        self._default_geometry = (140, 140, 520, 640)
        self.setGeometry(*self._default_geometry)
        self.setMinimumWidth(480)
        self.setMinimumHeight(560)
        self._settings_geometry_loaded = False
    # 原日志写入已禁用

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
        self.style_settings = StyleSettings() # 初始化风格设置

        # --- UI 元素 ---
        self.label_voice = QLabel("选择语音模型 (区域 / 语言 / 语音):")
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

        # --- 风格/情绪控制 ---
        self.style_group = QWidget()
        style_layout = QGridLayout(self.style_group)
        style_layout.setContentsMargins(0, 5, 0, 5)

        # 语速
        self.rate_label = QLabel("语速:")
        self.rate_slider = QSlider(Qt.Horizontal)
        self.rate_slider.setRange(-100, 100)
        self.rate_slider.setValue(0)
        self.rate_value_label = QLabel("+0%")
        style_layout.addWidget(self.rate_label, 0, 0)
        style_layout.addWidget(self.rate_slider, 0, 1)
        style_layout.addWidget(self.rate_value_label, 0, 2)

        # 音调
        self.pitch_label = QLabel("音调:")
        self.pitch_slider = QSlider(Qt.Horizontal)
        self.pitch_slider.setRange(-50, 50)
        self.pitch_slider.setValue(0)
        self.pitch_value_label = QLabel("+0Hz")
        style_layout.addWidget(self.pitch_label, 1, 0)
        style_layout.addWidget(self.pitch_slider, 1, 1)
        style_layout.addWidget(self.pitch_value_label, 1, 2)

        # 音量
        self.volume_label = QLabel("音量:")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(-100, 100)
        self.volume_slider.setValue(0)
        self.volume_value_label = QLabel("+0%")
        style_layout.addWidget(self.volume_label, 2, 0)
        style_layout.addWidget(self.volume_slider, 2, 1)
        style_layout.addWidget(self.volume_value_label, 2, 2)

        # 情绪
        self.style_label = QLabel("情绪:")
        self.style_combo = QComboBox()
        self.populate_styles() # 填充情绪选项
        style_layout.addWidget(self.style_label, 3, 0)
        style_layout.addWidget(self.style_combo, 3, 1, 1, 2)

        # 情绪强度
        self.style_degree_label = QLabel("强度:")
        self.style_degree_slider = QSlider(Qt.Horizontal)
        self.style_degree_slider.setRange(1, 200) # 0.01 to 2.00
        self.style_degree_slider.setValue(100)
        self.style_degree_value_label = QLabel("1.00")
        style_layout.addWidget(self.style_degree_label, 4, 0)
        style_layout.addWidget(self.style_degree_slider, 4, 1)
        style_layout.addWidget(self.style_degree_value_label, 4, 2)

        # 重置按钮
        self.reset_style_button = QPushButton("重置效果")
        style_layout.addWidget(self.reset_style_button, 5, 0, 1, 3)

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

        # 语音选择折叠面板（将排在设置面板之后）
        self.voice_box = CollapsibleBox("语音模型", expanded=True)
        _voice_inner_layout = QVBoxLayout()
        _voice_inner_layout.setContentsMargins(8,8,8,8)
        # 动态显示当前选中的语音（单选模式）
        self.current_voice_label = QLabel("当前语音: 未选择")
        # 使用主题高亮色：通过 palette(highlight) 获取背景色，再提取前景色或使用 highlight 的对比色
        from PySide6.QtGui import QPalette, QColor
        pal = self.palette()
        # 兼容不同 PySide6 版本：优先使用枚举 ColorRole
        try:
            highlight = pal.color(QPalette.ColorRole.Highlight)
            text_color = pal.color(QPalette.ColorRole.HighlightedText)
            window_text = pal.color(QPalette.ColorRole.WindowText)
        except Exception:
            # 旧式备用
            try:
                highlight = pal.highlight().color()  # type: ignore
                text_color = pal.highlightedText().color()  # type: ignore
                window_text = pal.windowText().color()  # type: ignore
            except Exception:
                highlight = QColor(30, 144, 255)
                text_color = QColor("white")
                window_text = QColor("black")

        if text_color == window_text:
            l = (0.299*highlight.red() + 0.587*highlight.green() + 0.114*highlight.blue())
            text_color = QColor("black") if l > 160 else QColor("white")

        # 统一封装: 根据当前主题窗口文字颜色设置样式（无背景，仅加粗）
        self.update_current_voice_label_style()
        _voice_inner_layout.addWidget(self.current_voice_label)
        _voice_inner_layout.addWidget(self.label_voice)
        _voice_inner_layout.addWidget(self.voice_tree)
        self.voice_box.setContentLayout(_voice_inner_layout)

        # Splitter 主布局（稍后按：设置 -> 语音 -> 日志 的顺序添加）
        self.layout_splitter = QSplitter(Qt.Vertical)
        self.layout.addWidget(self.layout_splitter)

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

    # ---- 组装折叠设置面板（紧凑型，放最上方，默认展开） ----
        self.settings_box = CollapsibleBox("设置", expanded=True)
        settings_layout = QVBoxLayout()
        settings_layout.setContentsMargins(8,8,8,8)
        # 热键
        hotkey_frame = QFrame()
        hotkey_lay = QHBoxLayout(hotkey_frame)
        hotkey_lay.setContentsMargins(0,0,0,0)
        hotkey_lay.addLayout(self.hotkey_layout)
        settings_layout.addWidget(QLabel("快捷键与转换:"))
        settings_layout.addWidget(hotkey_frame)
        # 情绪/风格控制
        style_frame = QFrame()
        sf_lay = QVBoxLayout(style_frame)
        sf_lay.setContentsMargins(0,0,0,0)
        sf_lay.addWidget(self.style_group)
        settings_layout.addWidget(QLabel("语音效果控制:"))
        settings_layout.addWidget(style_frame)
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
        # 先添加设置面板（顶部 compact）
        self.layout_splitter.addWidget(self.settings_box)

        # 日志折叠面板
        self.log_box = CollapsibleBox("日志", expanded=True)
        _log_layout = QVBoxLayout()
        _log_layout.setContentsMargins(8,8,8,8)
        _log_layout.addWidget(self.log_view)
        self.log_box.setContentLayout(_log_layout)
        # 添加剩余两个面板（语音、日志）
        self.layout_splitter.addWidget(self.voice_box)
        self.layout_splitter.addWidget(self.log_box)
        # 底部填充：用于在全部折叠时占据剩余空间，使三个面板始终贴顶
        self.bottom_filler = QWidget()
        self.bottom_filler.setObjectName("BottomFiller")
        self.bottom_filler.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.layout_splitter.addWidget(self.bottom_filler)
        # 面板尺寸记录结构（用于恢复用户调整过的高度）
        self._panel_saved_sizes = {"voice": None, "log": None}
        # 内部标志: 避免在程序计算 setSizes 时覆盖用户真实拖动高度
        self._updating_splitter = False
        # 初始分配一次尺寸 & 绑定事件
        QTimer.singleShot(0, self.update_splitter_sizes)
        for b in (self.settings_box, self.voice_box, self.log_box):
            b.toggled.connect(lambda _c, _b=b: self.update_splitter_sizes())
        # 监听 splitter 拖动，记录最新尺寸
        self.layout_splitter.splitterMoved.connect(self._on_splitter_moved)

        # --- 连接信号和槽 ---
        self.record_hotkey_button.clicked.connect(self.start_hotkey_recording)
        self.convert_button.clicked.connect(lambda: self.trigger_conversion("button"))
        self.refresh_key_button.clicked.connect(self.manual_refresh_edge_auth)

        # 连接风格设置控件
        self.rate_slider.valueChanged.connect(self.on_style_slider_changed)
        self.pitch_slider.valueChanged.connect(self.on_style_slider_changed)
        self.volume_slider.valueChanged.connect(self.on_style_slider_changed)
        self.style_degree_slider.valueChanged.connect(self.on_style_slider_changed)
        self.style_combo.currentTextChanged.connect(self.on_style_setting_changed)
        self.reset_style_button.clicked.connect(self.reset_style_settings)

        self.voice_tree.itemChanged.connect(self.on_voice_item_changed)
        self.voice_tree.itemExpanded.connect(self._on_tree_expansion_changed)
        self.voice_tree.itemCollapsed.connect(self._on_tree_expansion_changed)
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
        self.log("2. 选择一个语音模型。")
        self.log("3. 点击“录制快捷键”，按下组合键后自动保存。")
        self.log("4. 使用快捷键或“立即转换”按钮，剪贴板文本将转为语音。")

    def populate_styles(self):
        """填充情绪/风格下拉框。"""
        # 常见风格列表，可根据需要增删
        styles = [
            "default", "advertisement_upbeat", "affectionate", "angry", "assistant",
            "calm", "chat", "cheerful", "customerservice", "depressed", "disgruntled",
            "documentary-narration", "embarrassed", "empathetic", "envious", "excited",
            "fearful", "friendly", "gentle", "hopeful", "lyrical", "narration-professional",
            "narration-relaxed", "newscast", "newscast-casual", "newscast-formal",
            "poetry-reading", "sad", "serious", "shouting", "sports_commentary",
            "sports_commentary_excited", "whispering", "terrified", "unfriendly"
        ]
        self.style_combo.addItems(styles)

    def on_style_slider_changed(self):
        """处理所有滑块变化，更新标签并保存设置。"""
        # 更新语速
        rate_val = self.rate_slider.value()
        self.style_settings.rate = f"{rate_val:+}%"
        self.rate_value_label.setText(self.style_settings.rate)

        # 更新音调
        pitch_val = self.pitch_slider.value()
        self.style_settings.pitch = f"{pitch_val:+d}Hz"
        self.pitch_value_label.setText(self.style_settings.pitch)

        # 更新音量
        volume_val = self.volume_slider.value()
        self.style_settings.volume = f"{volume_val:+}%"
        self.volume_value_label.setText(self.style_settings.volume)

        # 更新强度
        degree_val = self.style_degree_slider.value() / 100.0
        self.style_settings.style_degree = degree_val
        self.style_degree_value_label.setText(f"{degree_val:.2f}")

        self.save_settings()

    def on_style_setting_changed(self):
        """处理下拉框等非滑块控件的变化。"""
        self.style_settings.style = self.style_combo.currentText()
        is_default = self.style_settings.style == "default"
        self.style_degree_slider.setEnabled(not is_default)
        self.style_degree_label.setEnabled(not is_default)
        self.style_degree_value_label.setEnabled(not is_default)
        self.save_settings()

    def reset_style_settings(self):
        """重置所有风格设置为默认值。"""
        self._loading_settings = True
        try:
            self.rate_slider.setValue(0)
            self.pitch_slider.setValue(0)
            self.volume_slider.setValue(0)
            self.style_degree_slider.setValue(100)
            self.style_combo.setCurrentText("default")
            # on_style_slider_changed 和 on_style_setting_changed 会被触发
            # 并自动更新 self.style_settings 和标签
        finally:
            self._loading_settings = False
        self.save_settings() # 确保重置后立即保存
        self.log("语音效果已重置为默认值。")

    def _on_splitter_moved(self, *_):
        """用户拖动 splitter 后记录当前展开面板高度。"""
        if getattr(self, '_updating_splitter', False):
            return
        # 先约束一次，防止拖动覆盖折叠标题或压扁内容
        self._enforce_splitter_constraints()
        self._store_expanded_sizes()

    def _enforce_splitter_constraints(self):
        """在用户拖动后强制修正 sizes：
        - 折叠面板高度 = header 高度
        - 展开面板 >= MIN_CONTENT
        - 不允许把某个展开面板挤到低于 MIN_CONTENT 或把折叠标题挤没
        """
        splitter = getattr(self, 'layout_splitter', None)
        if not splitter:
            return
        sizes = splitter.sizes()  # [settings, voice, log, filler]
        if len(sizes) < 4:
            return
        header_s = self.settings_box.header_height()
        header_v = self.voice_box.header_height()
        header_l = self.log_box.header_height()
        MIN_CONTENT = 80
        set_h, voice_h, log_h, filler = sizes

        # 锁定折叠的面板高度为其 header 高度
        if not self.settings_box.is_expanded():
            set_h = header_s
        else:
            fixed = getattr(self, '_expanded_settings_height', None)
            if fixed is not None:
                set_h = fixed
            else:
                set_h = max(set_h, header_s + 40)

        if not self.voice_box.is_expanded():
            voice_h = header_v
        else:
            voice_h = max(voice_h, MIN_CONTENT)

        if not self.log_box.is_expanded():
            log_h = header_l
        else:
            log_h = max(log_h, MIN_CONTENT)

        # 重新计算剩余/填充，保持总高度不变
        total = sum(sizes)
        used = set_h + voice_h + log_h
        filler = max(0, total - used)
        # 若 filler 不足以维持 used, 做一次比例压缩（极端窗口过小）
        if used > total:
            scale = total / used if used > 0 else 1
            set_h = int(set_h * scale)
            voice_h = int(voice_h * scale)
            log_h = int(log_h * scale)
            used = set_h + voice_h + log_h
            filler = max(0, total - used)
        self._updating_splitter = True
        splitter.setSizes([set_h, voice_h, log_h, filler])
        self._updating_splitter = False

    def _store_expanded_sizes(self):
        # 仅在用户交互(拖动)后调用, 内部自动布局阶段(_updating_splitter=True)跳过
        if getattr(self, '_updating_splitter', False):
            return
        if not hasattr(self, 'layout_splitter'):
            return
        sizes = self.layout_splitter.sizes()  # [settings, voice, log, filler]
        if len(sizes) < 4:
            return
        # 记录当前展开面板的总高度(含标题), 仅更新处于展开状态的面板
        if self.voice_box.is_expanded():
            self._panel_saved_sizes['voice'] = max(0, sizes[1])
        if self.log_box.is_expanded():
            self._panel_saved_sizes['log'] = max(0, sizes[2])

    def update_splitter_sizes(self):
        """统一计算 4 个 splitter 项（设置 / 语音 / 日志 / filler）。
        行为：
        1. 设置面板：紧凑模式（限制最大高度），折叠仅标题。
        2. 语音 / 日志：支持记忆用户拖动；一个展开则占剩余；两个展开按记忆比例或均分。
        3. 全部折叠：三个标题贴顶，filler 吞掉余量。
        """
        splitter = getattr(self, 'layout_splitter', None)
        if not splitter:
            return
        self._updating_splitter = True  # 标记内部调整阶段
        total_h = max(1, splitter.height())
        header_s = self.settings_box.header_height()
        header_v = self.voice_box.header_height()
        header_l = self.log_box.header_height()

        MAX_COMPACT = 260
        # 设置面板高度
        if self.settings_box.is_expanded():
            content_h = self.settings_box.content_area.sizeHint().height()
            set_h = min(MAX_COMPACT, content_h + header_s)
            set_h = max(set_h, header_s + 40)
            # 记录展开时固定高度
            self._expanded_settings_height = set_h
        else:
            set_h = header_s

        # 重新计算设置面板高度，因为内容增加了
        if self.settings_box.is_expanded():
            # 强制重新计算 sizeHint
            self.settings_box.content_area.updateGeometry()
            content_h = self.settings_box.content_area.sizeHint().height()
            # 增加最大高度以容纳新控件
            MAX_COMPACT = 420
            set_h = min(MAX_COMPACT, content_h + header_s)
            set_h = max(set_h, header_s + 40)
            self._expanded_settings_height = set_h
        else:
            set_h = header_s

        # 全部折叠情况
        all_collapsed = (not self.settings_box.is_expanded() and
                         not self.voice_box.is_expanded() and
                         not self.log_box.is_expanded())
        if all_collapsed:
            filler = max(0, total_h - (header_s + header_v + header_l))
            splitter.setSizes([header_s, header_v, header_l, filler])
            # 约束
            for box, h in [(self.settings_box, header_s), (self.voice_box, header_v), (self.log_box, header_l)]:
                box.setMinimumHeight(h); box.setMaximumHeight(h); box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            self.bottom_filler.setMinimumHeight(0)
            self.bottom_filler.setMaximumHeight(16777215)
            self.bottom_filler.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            self._updating_splitter = False
            return

        remaining = max(0, total_h - set_h)

        # 语音/日志高度分配
        voice_exp = self.voice_box.is_expanded()
        log_exp = self.log_box.is_expanded()
        voice_h = header_v
        log_h = header_l
        MIN_CONTENT = 80

        if voice_exp and log_exp:
            # 使用保存的比例；若无则均分
            sv = self._panel_saved_sizes.get('voice') or 1
            sl = self._panel_saved_sizes.get('log') or 1
            total_saved = sv + sl
            if total_saved <= 0:
                sv = sl = 1; total_saved = 2
            voice_h = max(MIN_CONTENT, int(remaining * (sv / total_saved)))
            log_h = max(MIN_CONTENT, remaining - voice_h)
        elif voice_exp and not log_exp:
            log_h = header_l
            voice_h = max(MIN_CONTENT, remaining - log_h)
        elif log_exp and not voice_exp:
            voice_h = header_v
            log_h = max(MIN_CONTENT, remaining - voice_h)
        # else: both collapsed handled earlier (would have returned), so no extra case

        # 计算 filler
        used = set_h + voice_h + log_h
        filler = max(0, total_h - used)
        splitter.setSizes([set_h, voice_h, log_h, filler])

        # 约束设置面板
        if self.settings_box.is_expanded():
            # 展开时完全固定高度，不允许拖动影响
            self.settings_box.setMinimumHeight(set_h)
            self.settings_box.setMaximumHeight(set_h)
            self.settings_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        else:
            self.settings_box.setMinimumHeight(header_s)
            self.settings_box.setMaximumHeight(header_s)
            self.settings_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # 语音/日志面板
        for box, expanded, header, h in [
            (self.voice_box, voice_exp, header_v, voice_h),
            (self.log_box, log_exp, header_l, log_h)
        ]:
            if expanded:
                box.setMinimumHeight(MIN_CONTENT)
                box.setMaximumHeight(16777215)
                box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            else:
                box.setMinimumHeight(header)
                box.setMaximumHeight(header)
                box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # filler 保持扩展
        self.bottom_filler.setMinimumHeight(0)
        self.bottom_filler.setMaximumHeight(16777215)
        self.bottom_filler.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # 若尚未有用户拖动记录, 初始化一次记忆值（避免首次折叠后丢失比例）
        if self.voice_box.is_expanded() and not self._panel_saved_sizes.get('voice'):
            self._panel_saved_sizes['voice'] = voice_h
        if self.log_box.is_expanded() and not self._panel_saved_sizes.get('log'):
            self._panel_saved_sizes['log'] = log_h

        # 结束内部调整; 不在此时写入保存尺寸, 避免覆盖用户拖动记忆
        self._updating_splitter = False

    def _store_expanded_sizes(self):
        # 仅在用户交互(拖动)后调用, 内部自动布局阶段(_updating_splitter=True)跳过
        if getattr(self, '_updating_splitter', False):
            return
        if not hasattr(self, 'layout_splitter'):
            return
        sizes = self.layout_splitter.sizes()  # [settings, voice, log, filler]
        if len(sizes) < 4:
            return
        # 记录当前展开面板的总高度(含标题), 仅更新处于展开状态的面板
        if self.voice_box.is_expanded():
            self._panel_saved_sizes['voice'] = max(0, sizes[1])
        if self.log_box.is_expanded():
            self._panel_saved_sizes['log'] = max(0, sizes[2])

    def update_splitter_sizes(self):
        """统一计算 4 个 splitter 项（设置 / 语音 / 日志 / filler）。
        行为：
        1. 设置面板：紧凑模式（限制最大高度），折叠仅标题。
        2. 语音 / 日志：支持记忆用户拖动；一个展开则占剩余；两个展开按记忆比例或均分。
        3. 全部折叠：三个标题贴顶，filler 吞掉余量。
        """
        splitter = getattr(self, 'layout_splitter', None)
        if not splitter:
            return
        self._updating_splitter = True  # 标记内部调整阶段
        total_h = max(1, splitter.height())
        header_s = self.settings_box.header_height()
        header_v = self.voice_box.header_height()
        header_l = self.log_box.header_height()

        MAX_COMPACT = 260
        # 设置面板高度
        if self.settings_box.is_expanded():
            content_h = self.settings_box.content_area.sizeHint().height()
            set_h = min(MAX_COMPACT, content_h + header_s)
            set_h = max(set_h, header_s + 40)
            # 记录展开时固定高度
            self._expanded_settings_height = set_h
        else:
            set_h = header_s

        # 重新计算设置面板高度，因为内容增加了
        if self.settings_box.is_expanded():
            # 强制重新计算 sizeHint
            self.settings_box.content_area.updateGeometry()
            content_h = self.settings_box.content_area.sizeHint().height()
            # 增加最大高度以容纳新控件
            MAX_COMPACT = 420
            set_h = min(MAX_COMPACT, content_h + header_s)
            set_h = max(set_h, header_s + 40)
            self._expanded_settings_height = set_h
        else:
            set_h = header_s

        # 全部折叠情况
        all_collapsed = (not self.settings_box.is_expanded() and
                         not self.voice_box.is_expanded() and
                         not self.log_box.is_expanded())
        if all_collapsed:
            filler = max(0, total_h - (header_s + header_v + header_l))
            splitter.setSizes([header_s, header_v, header_l, filler])
            # 约束
            for box, h in [(self.settings_box, header_s), (self.voice_box, header_v), (self.log_box, header_l)]:
                box.setMinimumHeight(h); box.setMaximumHeight(h); box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            self.bottom_filler.setMinimumHeight(0)
            self.bottom_filler.setMaximumHeight(16777215)
            self.bottom_filler.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            self._updating_splitter = False
            return

        remaining = max(0, total_h - set_h)

        # 语音/日志高度分配
        voice_exp = self.voice_box.is_expanded()
        log_exp = self.log_box.is_expanded()
        voice_h = header_v
        log_h = header_l
        MIN_CONTENT = 80

        if voice_exp and log_exp:
            # 使用保存的比例；若无则均分
            sv = self._panel_saved_sizes.get('voice') or 1
            sl = self._panel_saved_sizes.get('log') or 1
            total_saved = sv + sl
            if total_saved <= 0:
                sv = sl = 1; total_saved = 2
            voice_h = max(MIN_CONTENT, int(remaining * (sv / total_saved)))
            log_h = max(MIN_CONTENT, remaining - voice_h)
        elif voice_exp and not log_exp:
            log_h = header_l
            voice_h = max(MIN_CONTENT, remaining - log_h)
        elif log_exp and not voice_exp:
            voice_h = header_v
            log_h = max(MIN_CONTENT, remaining - voice_h)
        # else: both collapsed handled earlier (would have returned), so no extra case

        # 计算 filler
        used = set_h + voice_h + log_h
        filler = max(0, total_h - used)
        splitter.setSizes([set_h, voice_h, log_h, filler])

        # 约束设置面板
        if self.settings_box.is_expanded():
            # 展开时完全固定高度，不允许拖动影响
            self.settings_box.setMinimumHeight(set_h)
            self.settings_box.setMaximumHeight(set_h)
            self.settings_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        else:
            self.settings_box.setMinimumHeight(header_s)
            self.settings_box.setMaximumHeight(header_s)
            self.settings_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # 语音/日志面板
        for box, expanded, header, h in [
            (self.voice_box, voice_exp, header_v, voice_h),
            (self.log_box, log_exp, header_l, log_h)
        ]:
            if expanded:
                box.setMinimumHeight(MIN_CONTENT)
                box.setMaximumHeight(16777215)
                box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            else:
                box.setMinimumHeight(header)
                box.setMaximumHeight(header)
                box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # filler 保持扩展
        self.bottom_filler.setMinimumHeight(0)
        self.bottom_filler.setMaximumHeight(16777215)
        self.bottom_filler.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # 若尚未有用户拖动记录, 初始化一次记忆值（避免首次折叠后丢失比例）
        if self.voice_box.is_expanded() and not self._panel_saved_sizes.get('voice'):
            self._panel_saved_sizes['voice'] = voice_h
        if self.log_box.is_expanded() and not self._panel_saved_sizes.get('log'):
            self._panel_saved_sizes['log'] = log_h

        # 结束内部调整; 不在此时写入保存尺寸, 避免覆盖用户拖动记忆
        self._updating_splitter = False

    def _store_expanded_sizes(self):
        # 仅在用户交互(拖动)后调用, 内部自动布局阶段(_updating_splitter=True)跳过
        if getattr(self, '_updating_splitter', False):
            return
        if not hasattr(self, 'layout_splitter'):
            return
        sizes = self.layout_splitter.sizes()  # [settings, voice, log, filler]
        if len(sizes) < 4:
            return
        # 记录当前展开面板的总高度(含标题), 仅更新处于展开状态的面板
        if self.voice_box.is_expanded():
            self._panel_saved_sizes['voice'] = max(0, sizes[1])
        if self.log_box.is_expanded():
            self._panel_saved_sizes['log'] = max(0, sizes[2])

    def update_splitter_sizes(self):
        """统一计算 4 个 splitter 项（设置 / 语音 / 日志 / filler）。
        行为：
        1. 设置面板：紧凑模式（限制最大高度），折叠仅标题。
        2. 语音 / 日志：支持记忆用户拖动；一个展开则占剩余；两个展开按记忆比例或均分。
        3. 全部折叠：三个标题贴顶，filler 吞掉余量。
        """
        splitter = getattr(self, 'layout_splitter', None)
        if not splitter:
            return
        self._updating_splitter = True  # 标记内部调整阶段
        total_h = max(1, splitter.height())
        header_s = self.settings_box.header_height()
        header_v = self.voice_box.header_height()
        header_l = self.log_box.header_height()

        MAX_COMPACT = 260
        # 设置面板高度
        if self.settings_box.is_expanded():
            content_h = self.settings_box.content_area.sizeHint().height()
            set_h = min(MAX_COMPACT, content_h + header_s)
            set_h = max(set_h, header_s + 40)
            # 记录展开时固定高度
            self._expanded_settings_height = set_h
        else:
            set_h = header_s

        # 重新计算设置面板高度，因为内容增加了
        if self.settings_box.is_expanded():
            # 强制重新计算 sizeHint
            self.settings_box.content_area.updateGeometry()
            content_h = self.settings_box.content_area.sizeHint().height()
            # 增加最大高度以容纳新控件
            MAX_COMPACT = 420
            set_h = min(MAX_COMPACT, content_h + header_s)
            set_h = max(set_h, header_s + 40)
            self._expanded_settings_height = set_h
        else:
            set_h = header_s

        # 全部折叠情况
        all_collapsed = (not self.settings_box.is_expanded() and
                         not self.voice_box.is_expanded() and
                         not self.log_box.is_expanded())
        if all_collapsed:
            filler = max(0, total_h - (header_s + header_v + header_l))
            splitter.setSizes([header_s, header_v, header_l, filler])
            # 约束
            for box, h in [(self.settings_box, header_s), (self.voice_box, header_v), (self.log_box, header_l)]:
                box.setMinimumHeight(h); box.setMaximumHeight(h); box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            self.bottom_filler.setMinimumHeight(0)
            self.bottom_filler.setMaximumHeight(16777215)
            self.bottom_filler.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            self._updating_splitter = False
            return

        remaining = max(0, total_h - set_h)

        # 语音/日志高度分配
        voice_exp = self.voice_box.is_expanded()
        log_exp = self.log_box.is_expanded()
        voice_h = header_v
        log_h = header_l
        MIN_CONTENT = 80

        if voice_exp and log_exp:
            # 使用保存的比例；若无则均分
            sv = self._panel_saved_sizes.get('voice') or 1
            sl = self._panel_saved_sizes.get('log') or 1
            total_saved = sv + sl
            if total_saved <= 0:
                sv = sl = 1; total_saved = 2
            voice_h = max(MIN_CONTENT, int(remaining * (sv / total_saved)))
            log_h = max(MIN_CONTENT, remaining - voice_h)
        elif voice_exp and not log_exp:
            log_h = header_l
            voice_h = max(MIN_CONTENT, remaining - log_h)
        elif log_exp and not voice_exp:
            voice_h = header_v
            log_h = max(MIN_CONTENT, remaining - voice_h)
        # else: both collapsed handled earlier (would have returned), so no extra case

        # 计算 filler
        used = set_h + voice_h + log_h
        filler = max(0, total_h - used)
        splitter.setSizes([set_h, voice_h, log_h, filler])

        # 约束设置面板
        if self.settings_box.is_expanded():
            # 展开时完全固定高度，不允许拖动影响
            self.settings_box.setMinimumHeight(set_h)
            self.settings_box.setMaximumHeight(set_h)
            self.settings_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        else:
            self.settings_box.setMinimumHeight(header_s)
            self.settings_box.setMaximumHeight(header_s)
            self.settings_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # 语音/日志面板
        for box, expanded, header, h in [
            (self.voice_box, voice_exp, header_v, voice_h),
            (self.log_box, log_exp, header_l, log_h)
        ]:
            if expanded:
                box.setMinimumHeight(MIN_CONTENT)
                box.setMaximumHeight(16777215)
                box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            else:
                box.setMinimumHeight(header)
                box.setMaximumHeight(header)
                box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # filler 保持扩展
        self.bottom_filler.setMinimumHeight(0)
        self.bottom_filler.setMaximumHeight(16777215)
        self.bottom_filler.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # 若尚未有用户拖动记录, 初始化一次记忆值（避免首次折叠后丢失比例）
        if self.voice_box.is_expanded() and not self._panel_saved_sizes.get('voice'):
            self._panel_saved_sizes['voice'] = voice_h
        if self.log_box.is_expanded() and not self._panel_saved_sizes.get('log'):
            self._panel_saved_sizes['log'] = log_h

        # 结束内部调整; 不在此时写入保存尺寸, 避免覆盖用户拖动记忆
        self._updating_splitter = False

    def update_current_voice_label_style(self):
        """使用主题高亮(Highlight)颜色作为文字颜色, 不加背景。"""
        from PySide6.QtGui import QPalette, QColor
        pal = self.palette()
        # 取 highlight 颜色
        try:
            highlight = pal.color(QPalette.ColorRole.Highlight)
        except Exception:
            try:
                highlight = pal.highlight().color()  # type: ignore
            except Exception:
                highlight = QColor(30, 144, 255)
        # 直接用 highlight 做前景, 去掉背景
        self.current_voice_label.setStyleSheet(
            f"QLabel {{ font-weight: bold; padding:2px 0px; color: {highlight.name()}; }}"
        )

    def changeEvent(self, event):
        if event.type() == QEvent.Type.PaletteChange:
            # 主题/调色板变化时刷新文字颜色
            self.update_current_voice_label_style()
        super().changeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.update_splitter_sizes)

    def log(self, message):
        self.log_view.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        # 自动滚动到末尾
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

    def trigger_conversion(self, source="hotkey"):
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
            self.log("错误：请先选择一个语音模型。")
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
        # 构建队列（单选）
        self.voice_queue = list(voices)  # 只有一个
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
        worker = TTSWorker(voice, self.source_text, self, custom_output_dir=custom_dir, use_custom_naming=use_custom_naming, style_settings=self.style_settings)
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
        sizes = self.layout_splitter.sizes()
        core_sizes = sizes[:3] if len(sizes) >= 3 else sizes
        expanded_regions, expanded_languages = self._collect_expanded_states()
        obj = AppSettings(
            hotkey=self.hotkey_string,
            checked_voices=self.get_checked_voices(),  # 单选仍存列表形式，兼容旧结构
            output_device_id=self.output_device_combo.currentData(),
            monitor_device_id=self.monitor_device_combo.currentData(),
            output_dir_enabled=self.output_dir_enabled,
            output_dir_path=self.output_dir_path,
            panel_states={
                "voice_expanded": self.voice_box.is_expanded(),
                "settings_expanded": self.settings_box.is_expanded(),
                "log_expanded": self.log_box.is_expanded(),
            },
            panel_order=["settings", "voice", "log"],
            splitter_sizes=core_sizes,
            saved_panel_sizes=self._panel_saved_sizes,
            expanded_regions=expanded_regions,
            expanded_languages=expanded_languages,
            window_geometry=[self.x(), self.y(), self.width(), self.height()],
            style_settings=self.style_settings.to_dict(),  # 保存 SSML 风格设置
        )
        obj.save_to_file(self.get_settings_path())

    def load_settings(self):
        self._loading_settings = True
        try:
            s = AppSettings.load_from_file(self.get_settings_path())

            # 加载风格设置
            self.style_settings = StyleSettings.from_dict(s.style_settings)
            self.rate_slider.setValue(int(self.style_settings.rate.replace('%','').replace('+','')))
            self.pitch_slider.setValue(int(self.style_settings.pitch.replace('Hz','').replace('+','')))
            self.volume_slider.setValue(int(self.style_settings.volume.replace('%','').replace('+','')))
            self.style_combo.setCurrentText(self.style_settings.style)
            self.style_degree_slider.setValue(int(self.style_settings.style_degree * 100))
            # 手动触发一次更新
            self.on_style_slider_changed()
            self.on_style_setting_changed()

            # 加载热键
            if s.hotkey:
                self.set_hotkey(s.hotkey)
            # 设备
            if s.output_device_id is not None:
                i = self.output_device_combo.findData(s.output_device_id)
                if i != -1:
                    self.output_device_combo.setCurrentIndex(i)
                    self.output_device_combo.setProperty("user_set", True)
            if s.monitor_device_id is not None:
                i = self.monitor_device_combo.findData(s.monitor_device_id)
                if i != -1:
                    self.monitor_device_combo.setCurrentIndex(i)
            # 输出目录
            self.output_dir_enabled = bool(s.output_dir_enabled)
            self.output_dir_checkbox.setChecked(self.output_dir_enabled)
            self.output_dir_path = s.output_dir_path or ""
            self.apply_output_dir_state()
            # 面板状态
            ps = s.panel_states or {}
            self.voice_box.set_expanded(ps.get("voice_expanded", True))
            self.settings_box.set_expanded(ps.get("settings_expanded", True))
            self.log_box.set_expanded(ps.get("log_expanded", True))
            # 分割尺寸恢复（追加 filler）
            if s.splitter_sizes and s.panel_order == ["settings", "voice", "log"]:
                base_sum = sum(s.splitter_sizes)
                total_h = max(1, self.layout_splitter.height())
                filler = max(0, total_h - base_sum)
                self.layout_splitter.setSizes(s.splitter_sizes + [filler])
            if isinstance(s.saved_panel_sizes, dict):
                self._panel_saved_sizes.update(s.saved_panelsizes)
            # 恢复窗口几何
            if isinstance(s.window_geometry, list) and len(s.window_geometry) == 4:
                try:
                    gx, gy, gw, gh = s.window_geometry
                    if gw > 200 and gh > 300:
                        self.setGeometry(int(gx), int(gy), int(gw), int(gh))
                        self._settings_geometry_loaded = True
                except Exception:
                    pass
            # 延迟恢复展开状态（populate_voices 已在构造时调用）
            self._pending_expanded_regions = s.expanded_regions or []
            self._pending_expanded_languages = s.expanded_languages or []
            if self.voice_items and (self._pending_expanded_regions or self._pending_expanded_languages):
                self.apply_expanded_states(self._pending_expanded_regions, self._pending_expanded_languages)
                del self._pending_expanded_regions
                if hasattr(self, '_pending_expanded_languages'):
                    del self._pending_expanded_languages
        finally:
            QTimer.singleShot(0, lambda: setattr(self, '_loading_settings', False))
        self.setup_hotkey_listener()

    def setup_hotkey_listener(self):
        """设置全局热键监听；在主窗口显示后调用一次，确保不与其他窗口冲突。"""
        if not self.hotkey_string:
            return
        try:
            import keyboard
            def on_hotkey_event(e):
                # 忽略重复触发
                now = time.time()
                if (now - self.last_hotkey_trigger_time) < self.MIN_HOTKEY_INTERVAL:
                    return
                self.last_hotkey_trigger_time = now
                # 触发转换
                self.trigger_conversion("hotkey")
            # 移除可能的旧监听
            keyboard.unhook_all()
            # 注册新热键
            keys = self.hotkey_string.split('+')
            if len(keys) > 1:
                # 同时按下多个键
                keyboard.add_hotkey(self.hotkey_string, on_hotkey_event)
            else:
                # 单个键
                keyboard.add_hotkey(self.hotkey_string, on_hotkey_event)
            print(f"已设置全局热键: {self.hotkey_string}")
        except Exception as e:
            print(f"设置热键时发生错误: {e}")

    def closeEvent(self, event):
        """窗口关闭时清理工作，保存设置，卸载热键监听。"""
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass
        self.save_settings()
        event.accept()

    def keyPressEvent(self, event):
        """重载按键事件，捕获热键设置。"""
        if event.isAutoRepeat():
            return
        key = event.key()
        modifiers = QApplication.keyboardModifiers()
        # 组合键：Ctrl+Shift+X -> "ctrl+shift+x"
        keys = []
        if modifiers & Qt.ControlModifier:
            keys.append("ctrl")
        if modifiers & Qt.ShiftModifier:
            keys.append("shift")
        if modifiers & Qt.AltModifier:
            keys.append("alt")
        keys.append(QKeySequence(key).toString())
        hotkey = '+'.join(keys)
        # 更新热键
        self.set_hotkey(hotkey)

    def set_hotkey(self, hotkey: str):
        """设置热键，更新显示并保存设置。"""
        self.hotkey_string = hotkey
        if hotkey:
            self.current_hotkey_label.setText(hotkey)
            self.log(f"热键已设置: {hotkey}")
        else:
            self.current_hotkey_label.setText("未设置")
            self.log("热键已清除")
        self.save_settings()
        # 更新监听
        self.setup_hotkey_listener()

    def get_checked_voices(self):
        """获取当前选中的语音（单选模式下始终返回一个元素的列表）"""
        if not self.voice_items:
            return []
        checked = [v for v, item in self.voice_items.items() if item.checkState(0) == Qt.Checked]
        if len(checked) == 1:
            return checked
        return []

    def on_voice_item_changed(self, item, column):
        """语音树形视图项状态改变时：
        - 仅允许单选
        - 更新当前语音标签
        - 保存设置
        """
        if item.checkState(0) == Qt.Checked:
            # 取消其他项
            for other_item in self.voice_tree.findItems("", QTreeWidgetItem.ItemIsSelectable | QTreeWidgetItem.ItemIsUserCheckable, 0):
                if other_item != item:
                    other_item.setCheckState(0, Qt.Unchecked)
        # 更新当前语音显示
        checked_voices = self.get_checked_voices()
        if checked_voices:
            self.current_voice_label.setText(f"当前语音: {checked_voices[0]}")
        else:
            self.current_voice_label.setText("当前语音: 未选择")
        self.save_settings()

    def _on_tree_expansion_changed(self, item):
        """树形视图项展开/折叠时，更新保存的状态（避免在程序内部计算时覆盖用户拖动）"""
        if item not in self.voice_items.values():
            return
        if item.isExpanded():
            # 记录展开状态
            for region in self._pending_expanded_regions:
                if region.startswith(item.text(0)):
                    return
            self._pending_expanded_regions.append(item.text(0))
        else:
            # 移除折叠项
            self._pending_expanded_regions = [r for r in self._pending_expanded_regions if not r.startswith(item.text(0))]
        self.save_settings()

    def apply_expanded_states(self, expanded_regions, expanded_languages):
        """恢复区域/语言节点的展开状态（程序启动时调用）"""
        if not self.voice_items or not expanded_regions:
            return
        # 优先按区域展开
        for region in expanded_regions:
            for item in self.voice_items.values():
                if item.text(0) == region:
                    item.setExpanded(True)
                    break
        # 按语言展开
        for lang in expanded_languages:
            for item in self.voice_items.values():
                if item.text(0) == lang:
                    item.setExpanded(True)
                    break

    def _collect_expanded_states(self):
        """收集当前树形视图中所有展开的区域和语言节点（供设置保存）"""
        expanded_regions = set()
        expanded_languages = set()
        if not self.voice_items:
            return expanded_regions, expanded_languages
        # 递归检查子项
        def _check_item(item: QTreeWidgetItem):
            if item.childCount() == 0:
                # 叶子节点，直接记录
                text = item.text(0)
                if re.match(r'^[a-z]{2,3}(-[A-Z]{2,3})?$', text):
                    # 语言代码格式，记录为语言
                    expanded_languages.add(text)
                else:
                    # 其他情况（如区域）
                    expanded_regions.add(text)
            else:
                # 目录节点，检查是否展开
                if item.isExpanded():
                    text = item.text(0)
                    expanded_regions.add(text)
                    # 继续检查子项
                    for i in range(item.childCount()):
                        _check_item(item.child(i))
        # 顶层项
        for item in self.voice_items.values():
            if item.isExpanded():
                expanded_regions.add(item.text(0))
                # 检查其子项
                for i in range(item.childCount()):
                    _check_item(item.child(i))
        return list(expanded_regions), list(expanded_languages)

    def refresh_audio_devices(self, is_initial_load=False):
        """刷新音频输入输出设备列表并更新下拉框选项"""
        try:
            input_devices, output_devices = get_audio_devices()
            # 输入设备（仅提示，不再选择）
            if input_devices:
                self.log(f"检测到 {len(input_devices)} 个音频输入设备。")
            else:
                self.log("未检测到音频输入设备。")
            # 输出设备
            self.output_device_combo.clear()
            self.monitor_device_combo.clear()
            if output_devices:
                # 仅在设备变化时更新选项
                current_output_id = self.output_device_combo.currentData()
                current_monitor_id = self.monitor_device_combo.currentData()
                for i, dev in output_devices:
                    name = dev['name']
                    self.output_device_combo.addItem(name, i)
                    self.monitor_device_combo.addItem(name, i)
                # 恢复上次选择
                if not is_initial_load:
                    if current_output_id is not None:
                        i = self.output_device_combo.findData(current_output_id)
                        if i != -1:
                            self.output_device_combo.setCurrentIndex(i)
                    if current_monitor_id is not None:
                        i = self.monitor_device_combo.findData(current_monitor_id)
                        if i != -1:
                            self.monitor_device_combo.setCurrentIndex(i)
            else:
                self.log("未检测到音频输出设备。")
            if is_initial_load:
                self.log("音频设备列表已初始化。")
            else:
                self.log("音频设备列表已刷新。")
        except Exception as e:
            self.log(f"刷新音频设备时发生错误: {e}")

    def open_cable_install_url(self):
        """打开虚拟声卡安装链接（使用系统默认浏览器）"""
        try:
            QDesktopServices.openUrl(QUrl(VBCABLE_INSTALL_URL))
        except Exception as e:
            self.log(f"打开链接时发生错误: {e}")

    def browse_output_dir(self):
        """浏览文件夹对话框，选择输出目录"""
        try:
            initial_dir = self.output_dir_path if self.output_dir_path else os.path.dirname(os.path.abspath(__file__))
            dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录", initial_dir)
            if dir_path:
                self.output_dir_path = dir_path
                self.output_dir_edit.setText(dir_path)
                self.save_settings()
                self.log(f"输出目录已更改为: {dir_path}")
        except Exception as e:
            self.log(f"选择输出目录时发生错误: {e}")

    def open_output_dir(self):
        """打开输出目录（文件资源管理器）"""
        try:
            if self.output_dir_path and os.path.exists(self.output_dir_path):
                if sys.platform == "win32":
                    os.startfile(self.output_dir_path)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", self.output_dir_path])
                else:
                    subprocess.Popen(["xdg-open", self.output_dir_path])
                self.log(f"已打开输出目录: {self.output_dir_path}")
            else:
                self.log("输出目录路径无效，无法打开。")
        except Exception as e:
            self.log(f"打开输出目录时发生错误: {e}")

    def on_output_dir_toggled(self, checked):
        """输出目录复选框状态改变时"""
        self.output_dir_enabled = checked
        self.output_dir_edit.setEnabled(checked)
        self.output_dir_browse.setEnabled(checked)
        self.output_dir_open.setEnabled(checked)
        if not checked:
            # 清空路径
            self.output_dir_path = ""
            self.output_dir_edit.clear()
        self.save_settings()