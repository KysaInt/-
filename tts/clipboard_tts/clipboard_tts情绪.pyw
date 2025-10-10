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

# ==================== edge-tts SSML情绪标签补丁 ====================
# 直接集成补丁代码,无需外部文件
def apply_edge_tts_patch():
    """应用edge-tts SSML情绪标签支持补丁"""
    try:
        import edge_tts
        from edge_tts import communicate
        from xml.sax.saxutils import escape
        
        # 保存原始函数
        _original_mkssml = communicate.mkssml
        _original_communicate_init = communicate.Communicate.__init__
        _original_split = communicate.split_text_by_byte_length
        
        def patched_mkssml(tc, escaped_text):
            """修改后的mkssml,添加mstts命名空间"""
            if isinstance(escaped_text, bytes):
                escaped_text = escaped_text.decode("utf-8")
            
            # 添加mstts命名空间声明
            return (
                "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' "
                "xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='zh-CN'>"
                f"<voice name='{tc.voice}'>"
                f"<prosody pitch='{tc.pitch}' rate='{tc.rate}' volume='{tc.volume}'>"
                f"{escaped_text}"
                "</prosody>"
                "</voice>"
                "</speak>"
            )
        
        def patched_communicate_init(self, text, voice, *args, **kwargs):
            """修改Communicate初始化,在文本转义前提取SSML标签"""
            original_text = text
            
            # 检查是否包含express-as标签
            if '<mstts:express-as' in text and '</mstts:express-as>' in text:
                # 提取标签和内容
                pattern = r'<mstts:express-as\s+([^>]+)>(.*?)</mstts:express-as>'
                match = re.search(pattern, text, re.DOTALL)
                
                if match:
                    attrs = match.group(1)
                    inner_text = match.group(2).strip()
                    
                    # 使用零宽字符作为标记(不会被转义)
                    marker_start = "\u200B__EXPR_START__"
                    marker_attrs = f"\u200B__ATTRS__{attrs}__"
                    marker_end = "\u200B__EXPR_END__"
                    
                    # 替换文本
                    text = f"{marker_start}{marker_attrs}{inner_text}{marker_end}"
            
            # 调用原始__init__
            _original_communicate_init(self, text, voice, *args, **kwargs)
        
        def patched_split(text, max_len):
            """修改split_text,在分割后还原SSML标签"""
            result = _original_split(text, max_len)
            
            # 在每个chunk中还原SSML标签
            processed = []
            for chunk in result:
                # 处理bytes和str
                if isinstance(chunk, bytes):
                    chunk_str = chunk.decode('utf-8')
                else:
                    chunk_str = chunk
                    
                if '\u200B__EXPR_START__' in chunk_str:
                    # 提取属性
                    attrs_match = re.search(r'\u200B__ATTRS__(.+?)__', chunk_str)
                    if attrs_match:
                        attrs = attrs_match.group(1)
                        # 移除标记
                        chunk_str = chunk_str.replace('\u200B__EXPR_START__', '')
                        chunk_str = chunk_str.replace(f'\u200B__ATTRS__{attrs}__', '')
                        chunk_str = chunk_str.replace('\u200B__EXPR_END__', '')
                        # 添加SSML标签
                        chunk_str = f"<mstts:express-as {attrs}>{chunk_str}</mstts:express-as>"
                
                # 保持原类型
                if isinstance(chunk, bytes):
                    processed.append(chunk_str.encode('utf-8'))
                else:
                    processed.append(chunk_str)
            
            return processed
        
        # 应用所有补丁
        communicate.mkssml = patched_mkssml
        communicate.Communicate.__init__ = patched_communicate_init  
        communicate.split_text_by_byte_length = patched_split
        
        print("✓ edge-tts SSML情绪标签补丁已应用")
        return True
    except Exception as e:
        print(f"⚠ edge-tts补丁应用失败: {e}")
        return False

# 立即应用补丁
apply_edge_tts_patch()
# ==================== 补丁代码结束 ====================

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
    voice_rate: str = "+0%"      # 语速控制 (-100% ~ +100%)
    voice_pitch: str = "+0Hz"    # 音调控制 (-50Hz ~ +50Hz)
    voice_volume: str = "+0%"    # 音量控制 (-100% ~ +100%)
    enable_emotion: bool = False  # 是否启用情绪控制
    voice_style: str = "general"  # 情绪样式
    voice_styledegree: str = "1.0"  # 情绪程度 (0.01-2.0)
    voice_role: str = ""  # 角色扮演

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
    QLineEdit, QFileDialog, QFrame, QSplitter, QSizePolicy, QScrollArea, QDoubleSpinBox, QSlider
)
from PySide6.QtCore import QThread, Signal, Qt, QTimer, QPropertyAnimation, QEasingCurve, QEvent
from PySide6.QtGui import QDesktopServices, QTextCursor
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
        # 确保可见性与展开状态一致
        self.content_area.setVisible(self.is_expanded())

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
    """加载语音列表，启动时不强制刷新token以加快速度"""
    # 启动时跳过token刷新，使用缓存的token（如果存在）
    # 首次使用时如果401会自动刷新
    # if not get_edge_session_token(force=False):
    #     get_edge_session_token(force=True)
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


# --- TTS 转换核心 ---

class TTSWorker(QThread):
    finished = Signal(str, str)  # voice, mp3_path
    error = Signal(str, str)

    def __init__(self, voice: str, text: str, parent=None,
                 custom_output_dir: str | None = None,
                 use_custom_naming: bool = False,
                 rate: str = "+0%",
                 pitch: str = "+0Hz",
                 volume: str = "+0%",
                 enable_emotion: bool = False,
                 style: str = "general",
                 styledegree: str = "1.0",
                 role: str = ""):
        super().__init__(parent)
        self.voice = voice
        self.text = text
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.enable_emotion = enable_emotion
        self.style = style
        self.styledegree = styledegree
        self.role = role
        self.output_ext = ".mp3"
        # 如果启用自定义目录则使用之，否则临时目录
        self.output_dir = custom_output_dir or tempfile.gettempdir()
        self.use_custom_naming = use_custom_naming and bool(custom_output_dir)

    def build_ssml_text(self):
        """构建包含情绪标签的文本
        
        通过edge_tts_patch的猴子补丁,可以使用SSML标签
        补丁会在生成最终SSML时正确处理express-as标签
        """
        text = self.text.strip()
        
        # 只有在启用情绪控制且情绪不是普通时才添加标签
        if self.enable_emotion and self.style != "general":
            express_attrs = [f'style="{self.style}"', f'styledegree="{self.styledegree}"']
            if self.role:
                express_attrs.append(f'role="{self.role}"')
            
            attrs_str = " ".join(express_attrs)
            text = f'<mstts:express-as {attrs_str}>{text}</mstts:express-as>'
            print(f"[调试] 情绪控制已启用 - style={self.style}, degree={self.styledegree}, role={self.role}")
            print(f"[调试] SSML文本片段: {text[:200]}...")
        else:
            if self.enable_emotion:
                print(f"[调试] 情绪控制已启用但style为general，不添加标签")
            else:
                print(f"[调试] 情绪控制未启用")
        
        return text

    async def tts_async(self):
        if not self.text.strip():
            self.error.emit(self.voice, "剪贴板内容为空。")
            return
        attempt = 0
        last_error = None
        while attempt < 2:  # 最多重试1次（总共2次尝试）
            try:
                # 合成前确保 token 有效
                if not get_edge_session_token(force=False):
                    get_edge_session_token(force=True)
                if DETAILED_TTS_ERROR:
                    print(f"[DEBUG] 开始合成 voice={self.voice} attempt={attempt+1}")
                
                # 构建包含情绪的SSML文本
                ssml_text = self.build_ssml_text()
                
                # edge-tts 的 Communicate 会自动识别 SSML 标签
                # 如果文本包含 SSML 标签,rate/pitch/volume 会被整合到 prosody 标签中
                communicate = edge_tts.Communicate(
                    ssml_text, 
                    self.voice,
                    rate=self.rate,
                    pitch=self.pitch,
                    volume=self.volume
                )
                
                if DETAILED_TTS_ERROR:
                    print(f"[DEBUG] SSML文本: {ssml_text[:100]}...")
                    print(f"[DEBUG] 参数 - rate:{self.rate}, pitch:{self.pitch}, volume:{self.volume}")
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


# --- 情绪支持映射表 ---
# 根据微软文档，不同语音支持的情绪样式不同
# 这里列出常见中文语音支持的情绪（仅供参考）
EMOTION_SUPPORT_MAP = {
    # 中文常用语音支持的情绪样式
    'zh-CN-XiaoxiaoNeural': ['affectionate', 'angry', 'assistant', 'calm', 'chat', 'cheerful', 'customerservice', 
                              'disgruntled', 'fearful', 'friendly', 'gentle', 'lyrical', 'newscast', 'poetry-reading',
                              'sad', 'serious', 'sorry', 'whisper'],
    'zh-CN-YunxiNeural': ['angry', 'assistant', 'chat', 'cheerful', 'depressed', 'disgruntled', 'embarrassed',
                          'fearful', 'gentle', 'sad', 'serious'],
    'zh-CN-YunyangNeural': ['customerservice', 'narration-professional', 'newscast-casual'],
    'zh-CN-XiaoyiNeural': ['affectionate', 'angry', 'cheerful', 'disgruntled', 'embarrassed', 'fearful', 'gentle',
                           'sad', 'serious'],
    'zh-CN-YunjianNeural': ['angry', 'cheerful', 'depressed', 'disgruntled', 'documentary-narration', 'narration-relaxed',
                            'sad', 'serious', 'sports_commentary', 'sports_commentary_excited'],
    'zh-CN-XiaochenNeural': ['calm', 'cheerful', 'disgruntled', 'fearful', 'sad'],
    'zh-CN-XiaohanNeural': ['affectionate', 'angry', 'calm', 'cheerful', 'disgruntled', 'embarrassed', 'fearful',
                            'gentle', 'sad', 'serious'],
    'zh-CN-XiaomengNeural': ['chat'],
    'zh-CN-XiaomoNeural': ['affectionate', 'angry', 'calm', 'cheerful', 'depressed', 'disgruntled', 'embarrassed',
                           'envious', 'fearful', 'gentle', 'sad', 'serious'],
    'zh-CN-XiaoqiuNeural': ['angry', 'calm', 'cheerful', 'fearful', 'sad'],
    'zh-CN-XiaoruiNeural': ['angry', 'calm', 'fearful', 'sad'],
    'zh-CN-XiaoshuangNeural': ['chat'],
    'zh-CN-XiaoxuanNeural': ['angry', 'calm', 'cheerful', 'depressed', 'disgruntled', 'fearful', 'gentle', 'serious'],
    'zh-CN-XiaoyanNeural': ['angry', 'cheerful', 'disgruntled', 'fearful', 'sad', 'serious'],
    'zh-CN-XiaoyouNeural': ['angry', 'calm', 'cheerful', 'disgruntled', 'embarrassed', 'fearful', 'gentle', 'sad', 'serious'],
    'zh-CN-XiaozhenNeural': ['angry', 'cheerful', 'disgruntled', 'fearful', 'sad', 'serious'],
}

def check_emotion_support(voice_name: str, style: str) -> bool:
    """检查指定语音是否支持某个情绪样式
    
    Args:
        voice_name: 语音名称，如 'zh-CN-XiaoxiaoNeural'
        style: 情绪样式，如 'cheerful', 'sad'
    
    Returns:
        bool: 如果支持返回True，否则返回False（或未知时返回None）
    """
    if voice_name in EMOTION_SUPPORT_MAP:
        return style in EMOTION_SUPPORT_MAP[voice_name]
    return None  # 未知语音，无法确定


# --- 主应用界面 ---

class ClipboardTTSApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("剪贴板语音助手")
        # 增加默认高度以容纳完整的设置面板（包括情绪控制）
        self._default_geometry = (140, 140, 520, 900)  # 从640增加到900
        self.setGeometry(*self._default_geometry)
        self.setMinimumWidth(480)
        self.setMinimumHeight(700)  # 从560增加到700
        self._settings_geometry_loaded = False
    # 原日志写入已禁用

        # 延迟刷新 Edge TTS 鉴权，不阻塞启动（改为后台异步）
        # 注释掉同步刷新，改为首次使用时刷新
        # try:
        #     if refresh_edge_tts_key(force=True):
        #         print("启动时已刷新 Edge TTS key")
        #     else:
        #         print("启动时刷新 Edge TTS key 失败")
        # except Exception as e:
        #     print(f"启动刷新 Edge TTS key 异常: {e}")

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
        
        # 添加支持的情绪说明标签
        self.emotion_support_label = QLabel("支持的情绪: 加载中...")
        self.emotion_support_label.setWordWrap(True)
        self.emotion_support_label.setStyleSheet(
            "color: #666; font-size: 10px; padding: 5px; "
            "background: #f8f8f8; border-radius: 3px; border: 1px solid #e0e0e0;"
        )
        self.emotion_support_label.setVisible(False)  # 初始隐藏，选择语音后显示
        _voice_inner_layout.addWidget(self.emotion_support_label)
        
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

        # --- 语气控制选项 ---
        self.rate_label = QLabel("语速:")
        self.rate_combo = QComboBox()
        rate_options = ["-50%", "-25%", "+0%", "+25%", "+50%", "+75%", "+100%"]
        self.rate_combo.addItems(rate_options)
        self.rate_combo.setCurrentText("+0%")
        
        self.pitch_label = QLabel("音调:")
        self.pitch_combo = QComboBox()
        pitch_options = ["-50Hz", "-25Hz", "+0Hz", "+25Hz", "+50Hz"]
        self.pitch_combo.addItems(pitch_options)
        self.pitch_combo.setCurrentText("+0Hz")
        
        self.volume_label = QLabel("音量:")
        self.volume_combo = QComboBox()
        volume_options = ["-50%", "-25%", "+0%", "+25%", "+50%"]
        self.volume_combo.addItems(volume_options)
        self.volume_combo.setCurrentText("+0%")

        # --- 情绪控制选项 (SSML) - 单一情绪版 ---
        # 添加启用开关
        self.enable_emotion_checkbox = QCheckBox("启用情绪控制 (SSML)")
        self.enable_emotion_checkbox.setChecked(False)
        self.enable_emotion_checkbox.setToolTip("启用后可使用微软TTS的情绪表达功能")
        self.enable_emotion_checkbox.stateChanged.connect(self._toggle_emotion_controls)
        
        # 情绪下拉选择（带emoji图标）
        self.style_label = QLabel("情绪:")
        self.style_combo = QComboBox()
        
        # 情绪选项配置 (带emoji图标)
        emotion_options = [
            # 常用情绪
            ("😐 普通", "general"),
            ("😊 高兴", "cheerful"),
            ("😢 悲伤", "sad"),
            ("😠 生气", "angry"),
            ("🤩 兴奋", "excited"),
            ("🤝 友好", "friendly"),
            ("🥰 温柔", "gentle"),
            ("😌 冷静", "calm"),
            ("😑 严肃", "serious"),
            # 进阶情绪
            ("😨 恐惧", "fearful"),
            ("😱 惊恐", "terrified"),
            ("😒 不满", "disgruntled"),
            ("😞 沮丧", "depressed"),
            ("😳 尴尬", "embarrassed"),
            ("😤 嫉妒", "envious"),
            ("🤗 充满希望", "hopeful"),
            ("💕 亲切", "affectionate"),
            ("🎵 抒情", "lyrical"),
            # 语气变化
            ("🤫 低语", "whispering"),
            ("📢 喊叫", "shouting"),
            ("😾 不友好", "unfriendly"),
            # 专业场景
            ("🤖 助手", "assistant"),
            ("💬 聊天", "chat"),
            ("👔 客服", "customerservice"),
            ("📰 新闻播报", "newscast"),
            ("📻 新闻-休闲", "newscast-casual"),
            ("📺 新闻-正式", "newscast-formal"),
            ("⚽ 体育播报", "sports_commentary"),
            ("🏆 体育-兴奋", "sports_commentary_excited"),
            ("🎬 纪录片", "documentary-narration"),
            ("📣 广告", "advertisement_upbeat"),
            # 专业朗读
            ("📖 诗歌朗读", "poetry-reading"),
            ("📚 讲故事", "narration-professional"),
            ("🎙️ 轻松叙述", "narration-relaxed"),
            # 其他
            ("🥺 同情", "empathetic"),
            ("💪 鼓励", "encouragement"),
            ("👍 肯定", "affirmative")
        ]
        
        for text, value in emotion_options:
            self.style_combo.addItem(text, value)
        self.style_combo.setCurrentIndex(0)
        
        # 强度滑动条（0.01 - 2.0）
        self.styledegree_label = QLabel("强度: 1.00")
        self.styledegree_slider = QSlider(Qt.Horizontal)
        self.styledegree_slider.setMinimum(1)      # 0.01
        self.styledegree_slider.setMaximum(200)    # 2.00
        self.styledegree_slider.setValue(100)      # 1.00
        self.styledegree_slider.setTickPosition(QSlider.TicksBelow)
        self.styledegree_slider.setTickInterval(20)
        self.styledegree_slider.valueChanged.connect(self._on_styledegree_changed)
        
        # 角色控制保留
        self.role_label = QLabel("角色:")
        self.role_combo = QComboBox()
        role_options = [
            ("无", ""),
            ("👧 女孩", "Girl"),
            ("👦 男孩", "Boy"),
            ("👩 年轻女性", "YoungAdultFemale"),
            ("👨 年轻男性", "YoungAdultMale"),
            ("👩‍🦳 成熟女性", "OlderAdultFemale"),
            ("👨‍🦳 成熟男性", "OlderAdultMale"),
            ("👵 老年女性", "SeniorFemale"),
            ("👴 老年男性", "SeniorMale")
        ]
        for text, value in role_options:
            self.role_combo.addItem(text, value)
        self.role_combo.setCurrentIndex(0)
        self.role_combo.setToolTip("角色扮演 (部分语音支持)")

        # ---- 组装折叠设置面板（完整显示所有内容） ----
        self.settings_box = CollapsibleBox("设置", expanded=True)
        
        # 不使用滚动区域，直接显示所有内容
        settings_content = QWidget()
        settings_layout = QVBoxLayout(settings_content)
        settings_layout.setContentsMargins(6,6,6,6)
        settings_layout.setSpacing(3)
        
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
        
        # 基础语音参数（第一行）
        basic_ctrl_frame = QFrame()
        bc_lay = QHBoxLayout(basic_ctrl_frame)
        bc_lay.setContentsMargins(0,0,0,0)
        bc_lay.addWidget(self.rate_label)
        bc_lay.addWidget(self.rate_combo)
        bc_lay.addWidget(self.pitch_label)
        bc_lay.addWidget(self.pitch_combo)
        bc_lay.addWidget(self.volume_label)
        bc_lay.addWidget(self.volume_combo)
        bc_lay.addStretch()
        settings_layout.addWidget(QLabel("基础参数:"))
        settings_layout.addWidget(basic_ctrl_frame)
        
        # 情绪控制标题和开关
        settings_layout.addWidget(QLabel("<b>🎭 情绪控制 (SSML):</b>"))
        
        # 添加说明标签（保存为实例变量以便动态更新）
        self.emotion_help_label = QLabel("⚠️ 注意：不同语音支持的情绪不同，部分情绪可能无效果。\n推荐使用中文语音（如晓晓/云希/云扬）测试情绪功能。")
        self.emotion_help_label.setWordWrap(True)
        self.emotion_help_label.setStyleSheet("color: #666; font-size: 10px; padding: 3px; background: #f0f0f0; border-radius: 3px;")
        settings_layout.addWidget(self.emotion_help_label)
        
        settings_layout.addWidget(self.enable_emotion_checkbox)
        
        # 情绪选择
        emotion_frame = QFrame()
        em_lay = QHBoxLayout(emotion_frame)
        em_lay.setContentsMargins(0,0,0,0)
        em_lay.addWidget(self.style_label)
        em_lay.addWidget(self.style_combo, 1)
        settings_layout.addWidget(emotion_frame)
        
        # 强度滑动条
        degree_frame = QFrame()
        dg_lay = QVBoxLayout(degree_frame)
        dg_lay.setContentsMargins(0,0,0,0)
        dg_lay.addWidget(self.styledegree_label)
        dg_lay.addWidget(self.styledegree_slider)
        settings_layout.addWidget(degree_frame)
        
        # 角色控制
        role_ctrl_frame = QFrame()
        rc_lay = QHBoxLayout(role_ctrl_frame)
        rc_lay.setContentsMargins(0,0,0,0)
        rc_lay.addWidget(self.role_label)
        rc_lay.addWidget(self.role_combo)
        rc_lay.addStretch()
        settings_layout.addWidget(role_ctrl_frame)
        
        # 保存情绪控制的控件引用,便于启用/禁用
        self.emotion_widgets = [
            self.style_label, self.style_combo,
            self.styledegree_label, self.styledegree_slider,
            self.role_label, self.role_combo
        ]
        # 初始状态设为禁用
        self._toggle_emotion_controls(Qt.Unchecked)
        
        # 直接将内容添加到设置盒子（不使用滚动区域）
        settings_wrapper = QVBoxLayout()
        settings_wrapper.setContentsMargins(0,0,0,0)
        settings_wrapper.addWidget(settings_content)
        self.settings_box.setContentLayout(settings_wrapper)
        # 先添加设置面板（顶部）
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
        self.rate_combo.currentTextChanged.connect(self.save_settings)
        self.pitch_combo.currentTextChanged.connect(self.save_settings)
        self.volume_combo.currentTextChanged.connect(self.save_settings)
        self.enable_emotion_checkbox.stateChanged.connect(self.save_settings)
        self.style_combo.currentTextChanged.connect(self.save_settings)
        self.style_combo.currentIndexChanged.connect(self._on_emotion_style_changed)  # 添加情绪变化监听
        self.styledegree_slider.valueChanged.connect(self.save_settings)
        self.role_combo.currentTextChanged.connect(self.save_settings)

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

    def _create_separator(self):
        """创建分隔线"""
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: #ddd;")
        return line

    def _on_styledegree_changed(self, value):
        """滑动条值变化时更新标签显示"""
        degree = value / 100.0  # 1-200 映射到 0.01-2.00
        self.styledegree_label.setText(f"强度: {degree:.2f}")

    def _on_emotion_style_changed(self):
        """情绪样式改变时更新支持的语音提示"""
        style = self.style_combo.currentData()
        if not style or style == "general":
            # 普通情绪，显示默认提示
            self.emotion_help_label.setText(
                "⚠️ 注意：不同语音支持的情绪不同，部分情绪可能无效果。\n"
                "推荐使用中文语音（如晓晓/云希/云扬）测试情绪功能。"
            )
            return
        
        # 查找支持该情绪的语音
        supported_voices = []
        for voice_name, emotions in EMOTION_SUPPORT_MAP.items():
            if style in emotions:
                # 提取简短名称（去掉前缀和后缀）
                short_name = voice_name.replace('zh-CN-', '').replace('Neural', '')
                # 映射到中文名称
                voice_display_names = {
                    'Xiaoxiao': '晓晓', 'Yunxi': '云希', 'Yunyang': '云扬',
                    'Xiaoyi': '晓伊', 'Yunjian': '云健', 'Xiaochen': '晓辰',
                    'Xiaohan': '晓涵', 'Xiaomeng': '晓梦', 'Xiaomo': '晓墨',
                    'Xiaoqiu': '晓秋', 'Xiaorui': '晓睿', 'Xiaoshuang': '晓双',
                    'Xiaoxuan': '晓萱', 'Xiaoyan': '晓颜', 'Xiaoyou': '晓悠',
                    'Xiaozhen': '晓甄', 'Yunfeng': '云枫', 'Yunhao': '云皓',
                    'Yunjie': '云杰', 'Yunxia': '云夏', 'Yunyue': '云悦'
                }
                display_name = voice_display_names.get(short_name, short_name)
                supported_voices.append(display_name)
        
        style_text = self.style_combo.currentText()
        
        if len(supported_voices) == 0:
            # 没有找到支持的语音
            self.emotion_help_label.setText(
                f"⚠️ 情绪 {style_text} 在已知中文语音中支持较少。\n"
                "建议尝试其他情绪，或查看文档了解更多信息。"
            )
        elif len(supported_voices) <= 5:
            # 少量支持
            voices_str = "、".join(supported_voices)
            self.emotion_help_label.setText(
                f"💡 情绪 {style_text} 支持的语音：{voices_str}"
            )
        else:
            # 大量支持
            top_voices = "、".join(supported_voices[:5])
            self.emotion_help_label.setText(
                f"✅ 情绪 {style_text} 支持良好！推荐：{top_voices} 等 {len(supported_voices)} 个语音"
            )

    def _toggle_emotion_controls(self, state):
        """根据复选框状态启用或禁用情绪控件
        
        Args:
            state: Qt.CheckState 或 int (0=未选中, 2=选中)
        """
        # state 可能是 Qt.CheckState 枚举或整数
        # Qt.Unchecked = 0, Qt.Checked = 2
        enabled = (state == Qt.Checked or state == 2)
        
        for widget in self.emotion_widgets:
            widget.setEnabled(enabled)
        
        # 如果禁用,重置所有情绪选择
        if not enabled:
            self.style_combo.setCurrentIndex(0)  # 普通
            self.styledegree_slider.setValue(100)  # 1.00
            self.role_combo.setCurrentIndex(0)  # 无

    def update_splitter_sizes(self):
        """统一计算 4 个 splitter 项（设置 / 语音 / 日志 / filler）。
        行为：
        1. 设置面板：完整显示所有内容（不限制高度），折叠仅标题。
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

        # 设置面板高度 - 完整显示所有内容
        if self.settings_box.is_expanded():
            content_h = self.settings_box.content_area.sizeHint().height()
            set_h = content_h + header_s + 10  # 添加10px间距
            # 记录展开时的高度
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

    def populate_voices(self):
        """构建三层（区域 -> 语言 -> 语音）树结构，参考 TTSSRT.pyw。"""
        # 显示加载提示
        loading_item = QTreeWidgetItem(self.voice_tree, ["正在加载语音列表...", "", "", ""])
        loading_item.setDisabled(True)
        
        # 异步加载语音列表，不阻塞UI
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._load_voices_async)
    
    def _load_voices_async(self):
        """异步加载语音列表的实际实现"""
        try:
            voices_data = load_voice_list()
        except Exception as e:
            self.log(f"加载语音列表失败: {e}")
            voices_data = []

        # 清空加载提示
        self.voice_tree.clear()
        self.voice_items.clear()

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
            # 单选模式：父级不再可勾选
            # 移除可勾选属性（单选逻辑只在叶子节点）
            region_item.setFlags(region_item.flags() & ~Qt.ItemIsUserCheckable)

            for lang_display, voice_list in sorted(lang_map.items()):
                lang_item = QTreeWidgetItem(region_item, [lang_display])
                lang_item.setFlags(lang_item.flags() & ~Qt.ItemIsUserCheckable)

                for voice in sorted(voice_list, key=lambda v: v.get("ShortName", "")):
                    short_name = voice.get("ShortName", "未知语音")
                    gender = voice.get("Gender", "")
                    # "类别"列：使用 Locale；"个性"列：使用第一个 StyleList（如果存在）
                    locale = voice.get("Locale", "")
                    styles = voice.get("StyleList") or voice.get("Stylelist") or voice.get("StyleLists") or []
                    personality = styles[0] if isinstance(styles, (list, tuple)) and styles else ""
                    parts = [short_name, gender, locale, personality]
                    child = QTreeWidgetItem(lang_item, parts)
                    # 只允许叶子节点可勾选（单选行为我们手动控制）
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

        # 若加载设置后有展开状态记录，进行恢复（需在 load_settings 之后再次调用或者 populate 后手动调用 restore）
        if hasattr(self, '_pending_expanded_regions'):
            self.apply_expanded_states(self._pending_expanded_regions, getattr(self, '_pending_expanded_languages', []))
            del self._pending_expanded_regions
            if hasattr(self, '_pending_expanded_languages'):
                del self._pending_expanded_languages
        
        # 加载完成提示
        self.log(f"✓ 已加载 {len(voices_data)} 个语音模型")

    def get_checked_voices(self):
        # 单选模式：返回第一个被选中的叶子语音
        for voice_name, item in self.voice_items.items():
            if item.checkState(0) == Qt.Checked:
                return [voice_name]
        return []

    # ------ 树展开状态保存/恢复 ------
    def _collect_expanded_states(self):
        expanded_regions = []
        expanded_languages = []
        root = self.voice_tree.invisibleRootItem()
        for i in range(root.childCount()):
            region_item = root.child(i)
            region_name = region_item.text(0)
            if region_item.isExpanded():
                expanded_regions.append(region_name)
            for j in range(region_item.childCount()):
                lang_item = region_item.child(j)
                if lang_item.isExpanded():
                    expanded_languages.append(f"{region_name}||{lang_item.text(0)}")
        return expanded_regions, expanded_languages

    def apply_expanded_states(self, expanded_regions, expanded_languages):
        if not expanded_regions and not expanded_languages:
            return
        root = self.voice_tree.invisibleRootItem()
        lang_set = set(expanded_languages or [])
        region_set = set(expanded_regions or [])
        for i in range(root.childCount()):
            region_item = root.child(i)
            region_name = region_item.text(0)
            region_item.setExpanded(region_name in region_set)
            for j in range(region_item.childCount()):
                lang_item = region_item.child(j)
                key = f"{region_name}||{lang_item.text(0)}"
                lang_item.setExpanded(key in lang_set)

    def _on_tree_expansion_changed(self, *_):
        # 仅保存，不做其他处理
        self.save_settings()

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

    def update_emotion_support_label(self, voice_name: str):
        """更新情绪支持说明标签
        
        Args:
            voice_name: 语音名称，如 'zh-CN-XiaoxiaoNeural'
        """
        if voice_name in EMOTION_SUPPORT_MAP:
            supported_emotions = EMOTION_SUPPORT_MAP[voice_name]
            count = len(supported_emotions)
            
            # 情绪名称映射（英文 -> 中文emoji）
            emotion_display_map = {
                'affectionate': '💕亲切', 'angry': '😠生气', 'assistant': '🤖助手',
                'calm': '😌冷静', 'chat': '💬聊天', 'cheerful': '😊高兴',
                'customerservice': '👔客服', 'depressed': '😞沮丧', 'disgruntled': '😒不满',
                'documentary-narration': '🎬纪录片', 'embarrassed': '😳尴尬', 'empathetic': '🥺同情',
                'envious': '😤嫉妒', 'excited': '🤩兴奋', 'fearful': '😨恐惧',
                'friendly': '🤝友好', 'gentle': '🥰温柔', 'hopeful': '🤗希望',
                'lyrical': '🎵抒情', 'narration-professional': '📚讲故事', 'narration-relaxed': '🎙️轻松叙述',
                'newscast': '📰新闻播报', 'newscast-casual': '📻新闻休闲', 'newscast-formal': '📺新闻正式',
                'poetry-reading': '📖诗歌朗读', 'sad': '😢悲伤', 'serious': '😑严肃',
                'shouting': '📢喊叫', 'sorry': '😔抱歉', 'sports_commentary': '⚽体育播报',
                'sports_commentary_excited': '🏆体育兴奋', 'terrified': '😱惊恐', 'unfriendly': '😾不友好',
                'whispering': '🤫低语', 'whisper': '🤫低语'
            }
            
            # 转换为显示文本
            display_emotions = []
            for emotion in supported_emotions:
                display_emotions.append(emotion_display_map.get(emotion, emotion))
            
            # 构建显示文本
            emotions_text = "、".join(display_emotions)
            
            # 根据支持数量显示不同的星级
            if count >= 15:
                star = "⭐⭐⭐⭐⭐"
            elif count >= 10:
                star = "⭐⭐⭐⭐"
            elif count >= 5:
                star = "⭐⭐⭐"
            else:
                star = "⭐⭐"
            
            self.emotion_support_label.setText(
                f"🎭 支持 {count} 种情绪 {star}\n{emotions_text}"
            )
            self.emotion_support_label.setVisible(True)
        else:
            # 未知语音，显示提示
            self.emotion_support_label.setText(
                "ℹ️ 该语音的情绪支持未知，建议使用中文语音（如晓晓、云希）以获得最佳情绪效果。"
            )
            self.emotion_support_label.setVisible(True)

    def on_voice_item_changed(self, item, column):
        if column != 0 or self._loading_settings:
            return
        # 仅处理叶子节点（语音）勾选
        if item.childCount() == 0:
            if item.checkState(0) == Qt.Checked:
                # 单选：取消其他
                voice_name = item.text(0)
                if getattr(self, '_selected_voice', None) == voice_name:
                    # 同一个重复勾选，无需操作
                    return
                self._loading_settings = True
                try:
                    for vn, it in self.voice_items.items():
                        if it is not item and it.checkState(0) == Qt.Checked:
                            it.setCheckState(0, Qt.Unchecked)
                finally:
                    self._loading_settings = False
                prev = getattr(self, '_selected_voice', None)
                self._selected_voice = voice_name
                self.current_voice_label.setText(f"当前语音: {voice_name}")
                self.update_emotion_support_label(voice_name)  # 更新情绪支持说明
                self.log(f"切换语音模型: {voice_name}")
            else:
                # 取消选中当前语音
                if getattr(self, '_selected_voice', None) == item.text(0):
                    self._selected_voice = None
                    self.current_voice_label.setText("当前语音: 未选择")
                    self.emotion_support_label.setVisible(False)  # 隐藏情绪支持说明
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
            keyboard.add_hotkey(self.hotkey_string, _safe_trigger)
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
        
        # 获取情绪设置
        style = self.style_combo.currentData() or "general"
        styledegree = str(self.styledegree_slider.value() / 100.0)  # 转换为字符串
        
        # 检查情绪支持（仅当启用情绪控制时）
        if self.enable_emotion_checkbox.isChecked() and style != "general":
            support = check_emotion_support(voice, style)
            style_text = self.style_combo.currentText()
            if support is False:
                self.log(f"⚠️ [{voice}] 可能不支持 {style_text} 情绪，转换结果可能无情绪变化")
            elif support is None:
                self.log(f"ℹ️ [{voice}] 情绪 {style_text} 支持未知，如无效果请尝试其他语音")
            else:
                self.log(f"✓ [{voice}] 使用情绪: {style_text} (强度: {styledegree})")
        
        worker = TTSWorker(
            voice, 
            self.source_text, 
            self, 
            custom_output_dir=custom_dir, 
            use_custom_naming=use_custom_naming,
            rate=self.rate_combo.currentText(),
            pitch=self.pitch_combo.currentText(),
            volume=self.volume_combo.currentText(),
            enable_emotion=self.enable_emotion_checkbox.isChecked(),
            style=style,
            styledegree=styledegree,
            role=self.role_combo.currentData() or ""
        )
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
            voice_rate=self.rate_combo.currentText(),
            voice_pitch=self.pitch_combo.currentText(),
            voice_volume=self.volume_combo.currentText(),
            enable_emotion=self.enable_emotion_checkbox.isChecked(),
            voice_style=self.style_combo.currentData() or "general",
            voice_styledegree=str(self.styledegree_slider.value() / 100.0),
            voice_role=self.role_combo.currentData() or "",
        )
        obj.save_to_file(self.get_settings_path())

    def load_settings(self):
        path = self.get_settings_path()
        settings_obj = AppSettings.load_from_file(path)
        self._loading_settings = True
        try:
            # 只恢复第一个语音，兼容旧版多选
            first_voice = settings_obj.checked_voices[0] if settings_obj.checked_voices else None
            self.apply_voice_checks([first_voice] if first_voice else [])
            self.hotkey_string = settings_obj.hotkey
            self.update_hotkey_display()
            # 设备
            if settings_obj.output_device_id is not None:
                i = self.output_device_combo.findData(settings_obj.output_device_id)
                if i != -1:
                    self.output_device_combo.setCurrentIndex(i)
                    self.output_device_combo.setProperty("user_set", True)
            if settings_obj.monitor_device_id is not None:
                i = self.monitor_device_combo.findData(settings_obj.monitor_device_id)
                if i != -1:
                    self.monitor_device_combo.setCurrentIndex(i)
            # 输出目录
            self.output_dir_enabled = bool(settings_obj.output_dir_enabled)
            self.output_dir_checkbox.setChecked(self.output_dir_enabled)
            self.output_dir_path = settings_obj.output_dir_path or ""
            self.apply_output_dir_state()
            # 语气控制
            if settings_obj.voice_rate:
                idx = self.rate_combo.findText(settings_obj.voice_rate)
                if idx != -1:
                    self.rate_combo.setCurrentIndex(idx)
            if settings_obj.voice_pitch:
                idx = self.pitch_combo.findText(settings_obj.voice_pitch)
                if idx != -1:
                    self.pitch_combo.setCurrentIndex(idx)
            if settings_obj.voice_volume:
                idx = self.volume_combo.findText(settings_obj.voice_volume)
                if idx != -1:
                    self.volume_combo.setCurrentIndex(idx)
            # 情绪控制开关
            if hasattr(settings_obj, 'enable_emotion') and settings_obj.enable_emotion is not None:
                self.enable_emotion_checkbox.setChecked(bool(settings_obj.enable_emotion))
            else:
                self.enable_emotion_checkbox.setChecked(False)
            # 情绪控制选项
            if settings_obj.voice_style:
                idx = self.style_combo.findData(settings_obj.voice_style)
                if idx != -1:
                    self.style_combo.setCurrentIndex(idx)
            if settings_obj.voice_styledegree:
                try:
                    # 将字符串转换为滑动条值 (0.01-2.0 -> 1-200)
                    degree_float = float(settings_obj.voice_styledegree)
                    slider_value = int(degree_float * 100)
                    self.styledegree_slider.setValue(slider_value)
                except (ValueError, TypeError):
                    self.styledegree_slider.setValue(100)  # 默认1.00
            if hasattr(settings_obj, 'voice_role') and settings_obj.voice_role is not None:
                idx = self.role_combo.findData(settings_obj.voice_role)
                if idx != -1:
                    self.role_combo.setCurrentIndex(idx)
            # 面板状态
            ps = settings_obj.panel_states or {}
            self.voice_box.set_expanded(ps.get("voice_expanded", True))
            self.settings_box.set_expanded(ps.get("settings_expanded", True))
            self.log_box.set_expanded(ps.get("log_expanded", True))
            # 分割尺寸恢复（追加 filler）
            if settings_obj.splitter_sizes and settings_obj.panel_order == ["settings", "voice", "log"]:
                base_sum = sum(settings_obj.splitter_sizes)
                total_h = max(1, self.layout_splitter.height())
                filler = max(0, total_h - base_sum)
                self.layout_splitter.setSizes(settings_obj.splitter_sizes + [filler])
            if isinstance(settings_obj.saved_panel_sizes, dict):
                self._panel_saved_sizes.update(settings_obj.saved_panel_sizes)
            # 恢复窗口几何
            if isinstance(settings_obj.window_geometry, list) and len(settings_obj.window_geometry) == 4:
                try:
                    gx, gy, gw, gh = settings_obj.window_geometry
                    if gw > 200 and gh > 300:
                        self.setGeometry(int(gx), int(gy), int(gw), int(gh))
                        self._settings_geometry_loaded = True
                except Exception:
                    pass
            # 延迟恢复展开状态（populate_voices 已在构造时调用）
            self._pending_expanded_regions = settings_obj.expanded_regions or []
            self._pending_expanded_languages = settings_obj.expanded_languages or []
            # 如果语音数据已经存在，立即尝试应用（否则 populate_voices 会处理）
            if self.voice_items and (self._pending_expanded_regions or self._pending_expanded_languages):
                self.apply_expanded_states(self._pending_expanded_regions, self._pending_expanded_languages)
                del self._pending_expanded_regions
                if hasattr(self, '_pending_expanded_languages'):
                    del self._pending_expanded_languages
        finally:
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
        # 单选恢复：只取第一个
        first = None
        for v in voices or []:
            if v in self.voice_items:
                first = v
                break
        for voice_name, item in self.voice_items.items():
            item.setCheckState(0, Qt.Unchecked)
        self._selected_voice = None
        if first and first in self.voice_items:
            self.voice_items[first].setCheckState(0, Qt.Checked)
            self._selected_voice = first
            self.current_voice_label.setText(f"当前语音: {first}")
        else:
            self.current_voice_label.setText("当前语音: 未选择")

    def closeEvent(self, event):
        # 关闭前保存窗口位置与大小
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

    # ---- 控制台显示/隐藏逻辑 ----
    # 需求：UI 出现之前显示 cmd 窗口，UI 出现后隐藏。
    # 实现：
    #   1. 若当前无控制台 (pythonw.exe) -> 调用 AllocConsole 创建
    #   2. 记录我们是否新建控制台 (created_console)
    #   3. 在窗口 show() 后使用 Win32 API ShowWindow(hWnd, SW_HIDE) 隐藏控制台
    # 注意：如果用户本身就是在已有控制台 (python.exe) 中运行，为避免打断用户，默认仍隐藏，
    #       可根据需要修改 retain_existing_console 标志。
    created_console = False
    try:
        if os.name == 'nt':
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore
            user32 = ctypes.windll.user32      # type: ignore
            get_console = kernel32.GetConsoleWindow
            get_console.restype = ctypes.wintypes.HWND  # type: ignore
            h_console = get_console()
            if not h_console:
                # 无控制台，分配新的
                if kernel32.AllocConsole():
                    created_console = True
                    # 绑定标准流 (只在全新控制台情形下进行，避免覆盖用户控制台缓冲区)
                    try:
                        sys.stdout = open('CONOUT$', 'w', encoding='utf-8', buffering=1)
                        sys.stderr = open('CONOUT$', 'w', encoding='utf-8', buffering=1)
                        sys.stdin = open('CONIN$', 'r', encoding='utf-8')
                    except Exception:
                        pass
                    print("[启动] 已分配新的控制台窗口，用于查看初始化信息…")
                h_console = get_console()
            else:
                print("[启动] 检测到已有控制台窗口。")
    except Exception as _ce:
        print(f"控制台初始化失败: {_ce}")
    
    # Qt6 中这些属性已过时，不再需要设置
    # if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    #     QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    # if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    #     QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    print("Starting application...")
    try:
        app = QApplication(sys.argv)
        window = ClipboardTTSApp()
        window.show()
        # ---- 隐藏控制台 ----
        try:
            if os.name == 'nt':
                import ctypes
                import ctypes.wintypes
                user32 = ctypes.windll.user32  # type: ignore
                kernel32 = ctypes.windll.kernel32  # type: ignore
                h_console = kernel32.GetConsoleWindow()
                if h_console:
                    # 0:SW_HIDE 5:SW_SHOW
                    user32.ShowWindow(h_console, 0)
        except Exception as _he:
            print(f"隐藏控制台失败: {_he}")
        rc = app.exec()
    # 退出日志写入已禁用
        sys.exit(rc)
    except Exception as e:
        err = f"启动异常: {e}"
        print(err)
        traceback.print_exc()
    # 崩溃日志写入已禁用
        input("Press Enter to exit...")
