import asyncio
import time
import json
import os
import sys
import subprocess
import importlib
import re
import threading
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from collections import defaultdict
from xml.sax.saxutils import escape


_DEFAULT_AZURE_ENDPOINT_BASE = "https://eastasia.api.cognitive.microsoft.com/"


def _normalize_azure_speech_endpoint(endpoint_or_base: str, region: str = "") -> str:
    """Normalize various Azure Speech endpoints into a TTS endpoint.

    Accepts:
    - https://<region>.tts.speech.microsoft.com/cognitiveservices/v1
    - https://<region>.api.cognitive.microsoft.com/
    - https://<resource>.cognitiveservices.azure.com/
    and returns an endpoint suitable for POST /cognitiveservices/v1.
    """
    ep = (endpoint_or_base or "").strip()
    if not ep:
        ep = ""

    # Strip trailing slash
    if ep.endswith("/"):
        ep = ep[:-1]

    # If user gives the legacy regional Cognitive Services base, derive the Speech TTS endpoint
    # e.g. https://eastasia.api.cognitive.microsoft.com -> https://eastasia.tts.speech.microsoft.com/cognitiveservices/v1
    try:
        if ep.startswith("http://") or ep.startswith("https://"):
            from urllib.parse import urlparse

            u = urlparse(ep)
            host = (u.hostname or "").lower()
            if host.endswith(".api.cognitive.microsoft.com"):
                inferred_region = host.split(".")[0]
                r = (region or inferred_region or "").strip()
                if r:
                    return f"https://{r}.tts.speech.microsoft.com/cognitiveservices/v1"

            # Resource endpoint shape: https://<resource>.cognitiveservices.azure.com
            if host.endswith(".cognitiveservices.azure.com"):
                # Speech resource endpoint supports /cognitiveservices/v1
                base = f"{u.scheme}://{u.netloc}"
                return base + "/cognitiveservices/v1"
    except Exception:
        pass

    # If already points to the TTS endpoint, keep it.
    if ep.endswith("/cognitiveservices/v1"):
        return ep

    # If it looks like a base that isn't the legacy api.cognitive domain, append /cognitiveservices/v1
    if ep and (ep.startswith("http://") or ep.startswith("https://")):
        return ep + "/cognitiveservices/v1"

    # If only region provided
    r = (region or "").strip()
    if r:
        return f"https://{r}.tts.speech.microsoft.com/cognitiveservices/v1"

    return ""


def _azure_voices_list_url_from_tts_endpoint(tts_endpoint: str) -> str:
    base = (tts_endpoint or "").strip()
    if base.endswith("/"):
        base = base[:-1]
    if base.endswith("/cognitiveservices/v1"):
        base = base[: -len("/cognitiveservices/v1")]
    if base.endswith("/"):
        base = base[:-1]
    return base + "/cognitiveservices/voices/list"


def _get_windows_env_var_from_registry(name: str, scope: str) -> str | None:
    """Read Windows environment variables from registry.

    This helps when the current process environment (os.environ) hasn't been refreshed,
    e.g. VS Code was started before user variables were set.

    scope: 'user' or 'system'
    """
    try:
        if os.name != "nt":
            return None
        import winreg  # type: ignore

        if scope == "user":
            root = winreg.HKEY_CURRENT_USER
            path = r"Environment"
        else:
            root = winreg.HKEY_LOCAL_MACHINE
            path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"

        with winreg.OpenKey(root, path) as key:
            value, value_type = winreg.QueryValueEx(key, name)
            if value is None:
                return None
            if isinstance(value, str):
                # Expand %VAR% if present
                return os.path.expandvars(value).strip()
            return str(value).strip()
    except Exception:
        return None


def _get_env_var(name: str) -> str | None:
    """Get environment variable from process env, with Windows registry fallback."""
    v = os.environ.get(name)
    if v is not None and str(v).strip() != "":
        return str(v).strip()
    # Windows fallback: user then system
    v = _get_windows_env_var_from_registry(name, scope="user")
    if v:
        return v
    v = _get_windows_env_var_from_registry(name, scope="system")
    if v:
        return v
    return None


def _utc_now_iso() -> str:
    # Azure Monitor expects ISO 8601 UTC with Z
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _utc_iso_minus_days(days: int) -> str:
    try:
        from datetime import timedelta

        dt = datetime.utcnow() - timedelta(days=max(0, int(days)))
        return dt.replace(microsecond=0).isoformat() + "Z"
    except Exception:
        return _utc_now_iso()


def _azure_arm_get_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    """Get Azure Resource Manager access token.

    Priority:
    1) `AZURE_ARM_TOKEN` env var (advanced override)
    2) Service principal (client_credentials) via AAD (v2 scope, fallback v1 resource)
    3) Azure CLI login context (`az account get-access-token`)
    """
    # 1) Explicit token override
    explicit = _get_env_var("AZURE_ARM_TOKEN")
    if explicit:
        return explicit

    tenant_id = (tenant_id or "").strip()
    client_id = (client_id or "").strip()
    client_secret = (client_secret or "").strip()

    def _missing_sp_fields() -> list[str]:
        missing: list[str] = []
        if not tenant_id:
            missing.append("AZURE_TENANT_ID")
        if not client_id:
            missing.append("AZURE_CLIENT_ID")
        if not client_secret:
            missing.append("AZURE_CLIENT_SECRET")
        return missing

    def _try_az_cli_token() -> str | None:
        try:
            # Requires: Azure CLI installed + `az login` done.
            out = subprocess.check_output(
                [
                    "az",
                    "account",
                    "get-access-token",
                    "--resource",
                    "https://management.azure.com/",
                    "--query",
                    "accessToken",
                    "-o",
                    "tsv",
                ],
                stderr=subprocess.STDOUT,
                timeout=30,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            token = (out or "").strip()
            if token:
                return token
            return None
        except FileNotFoundError:
            return None
        except Exception:
            return None

    # If SP credentials are incomplete, try Azure CLI as a convenience fallback.
    if _missing_sp_fields():
        cli_token = _try_az_cli_token()
        if cli_token:
            return cli_token

        missing = " / ".join(_missing_sp_fields())
        raise Exception(
            "缺少用于获取 Azure Monitor 指标的认证信息："
            f"{missing}。\n"
            "可选方案：\n"
            "- 方案A（推荐，服务主体）：设置 AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET\n"
            "- 方案B（无需服务主体）：安装 Azure CLI 并先执行 `az login`，再重试\n"
            "- 方案C（高级）：直接设置 AZURE_ARM_TOKEN（ARM Bearer token）"
        )

    def _post_form(url: str, data: dict[str, str]) -> dict:
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw)

    # v2.0
    try:
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://management.azure.com/.default",
        }
        data = _post_form(token_url, payload)
        token = str(data.get("access_token") or "").strip()
        if not token:
            raise Exception(f"Token 响应缺少 access_token: {data}")
        return token
    except Exception:
        pass

    # v1
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "resource": "https://management.azure.com/",
    }
    data = _post_form(token_url, payload)
    token = str(data.get("access_token") or "").strip()
    if not token:
        raise Exception(f"Token 响应缺少 access_token: {data}")
    return token


def _azure_require_env_for_metrics(subscription_id: str, resource_group: str, resource_name: str):
    missing: list[str] = []
    if not (subscription_id or "").strip():
        missing.append("AZURE_SUBSCRIPTION_ID")
    if not (resource_group or "").strip():
        missing.append("AZURE_RESOURCE_GROUP")
    if not (resource_name or "").strip():
        missing.append("AZURE_SPEECH_RESOURCE_NAME(或 AZURE_COGNITIVE_ACCOUNT_NAME)")
    if missing:
        raise Exception("缺少资源定位环境变量：" + " / ".join(missing))


def _azure_arm_get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "tts/1.pyw",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    return json.loads(raw)


def _azure_build_resource_id(subscription_id: str, resource_group: str, resource_name: str) -> str:
    subscription_id = (subscription_id or "").strip()
    resource_group = (resource_group or "").strip()
    resource_name = (resource_name or "").strip()
    if not subscription_id or not resource_group or not resource_name:
        raise Exception("缺少 AZURE_SUBSCRIPTION_ID / AZURE_RESOURCE_GROUP / AZURE_SPEECH_RESOURCE_NAME。")
    return (
        f"/subscriptions/{subscription_id}"
        f"/resourceGroups/{resource_group}"
        f"/providers/Microsoft.CognitiveServices/accounts/{resource_name}"
    )


def _azure_fetch_speech_usage_metrics(days: int = 30) -> dict[str, float]:
    """Fetch usage metrics from Azure Monitor for Speech resource.

    Returns totals (sum over interval) for supported metrics.
    """
    tenant_id = _get_env_var("AZURE_TENANT_ID") or ""
    client_id = _get_env_var("AZURE_CLIENT_ID") or ""
    client_secret = _get_env_var("AZURE_CLIENT_SECRET") or ""

    subscription_id = _get_env_var("AZURE_SUBSCRIPTION_ID") or ""
    resource_group = _get_env_var("AZURE_RESOURCE_GROUP") or ""
    resource_name = (
        _get_env_var("AZURE_SPEECH_RESOURCE_NAME")
        or _get_env_var("AZURE_COGNITIVE_ACCOUNT_NAME")
        or ""
    )

    token = _azure_arm_get_token(tenant_id, client_id, client_secret)

    _azure_require_env_for_metrics(subscription_id, resource_group, resource_name)
    resource_id = _azure_build_resource_id(subscription_id, resource_group, resource_name)

    start = _utc_iso_minus_days(days)
    end = _utc_now_iso()
    timespan = f"{start}/{end}"

    metricnames = "SynthesizedCharacters,VideoSecondsSynthesized,VoiceModelHostingHours,VoiceModelTrainingMinutes"

    params = {
        "api-version": "2019-07-01",
        "metricnames": metricnames,
        "timespan": timespan,
        "interval": "PT1H",
        "aggregation": "Total",
    }
    url = "https://management.azure.com" + resource_id + "/providers/microsoft.insights/metrics?" + urllib.parse.urlencode(params)
    data = _azure_arm_get_json(url, token)

    totals: dict[str, float] = {}
    values = data.get("value")
    if not isinstance(values, list):
        raise Exception(f"Metrics 返回格式异常: {data}")

    for metric in values:
        try:
            name_obj = metric.get("name") or {}
            metric_name = str(name_obj.get("value") or name_obj.get("localizedValue") or "").strip()
            if not metric_name:
                continue
            total_value = 0.0
            timeseries = metric.get("timeseries") or []
            if isinstance(timeseries, list):
                for ts in timeseries:
                    points = ts.get("data") or []
                    if not isinstance(points, list):
                        continue
                    for p in points:
                        v = p.get("total")
                        if v is None:
                            continue
                        try:
                            total_value += float(v)
                        except Exception:
                            continue
            totals[metric_name] = total_value
        except Exception:
            continue

    return totals

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView, QLineEdit, QCheckBox,
    QComboBox, QSplitter, QSizePolicy, QSlider
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QIntValidator, QIcon


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
# ==================== 补丁代码结束 ====================


# 自动检查并安装 edge-tts，并处理同名脚本导致的导入冲突
def ensure_edge_tts():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 移除当前脚本所在目录，避免导入冲突
    if script_dir in sys.path:
        sys.path.remove(script_dir)

    def _has_required_api(mod) -> bool:
        # edge-tts 7.x：主入口就是 edge_tts.Communicate
        try:
            _ = getattr(mod, "Communicate")
            _ = getattr(mod, "VoicesManager")
        except Exception:
            return False
        return True

    def _import_edge_tts():
        return importlib.import_module("edge_tts")

    def _purge_edge_tts_modules():
        # 升级后需要清理缓存，否则可能还在用旧模块
        for k in list(sys.modules.keys()):
            if k == "edge_tts" or k.startswith("edge_tts."):
                sys.modules.pop(k, None)
    try:
        mod = _import_edge_tts()
        if not _has_required_api(mod):
            print("检测到 edge-tts 版本缺少必要接口（Communicate/VoicesManager），正在自动升级……")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "edge-tts"])
            _purge_edge_tts_modules()
            mod = _import_edge_tts()
        return mod
    except ImportError:
        print("未检测到 edge-tts，正在自动安装……")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "edge-tts", "PySide6"])
        _purge_edge_tts_modules()
        mod = _import_edge_tts()
        if not _has_required_api(mod):
            print("已安装 edge-tts 但仍缺少必要接口，尝试强制升级……")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "edge-tts"])
            _purge_edge_tts_modules()
            mod = _import_edge_tts()
        return mod
    finally:
        # 恢复 sys.path
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)

edge_tts = ensure_edge_tts()

# 立即应用补丁
apply_edge_tts_patch()

_mutagen_mp3_module = None

# --- Edge TTS 鉴权刷新（防 401） ---
# 在长时间运行或批量处理时，偶发 401/Invalid response status（WebSocket 连接被拒）。
# 通过调用 VoicesManager.create() 触发 edge-tts 内部重新拉取参数，可缓解该问题。
_EDGE_REFRESH_LAST_TS: float = 0.0
_EDGE_REFRESH_INTERVAL: float = 30.0  # 秒，避免过于频繁的刷新
_EDGE_REFRESH_LOCK = threading.Lock()

# 避免网络卡死导致“没有任何结果发回”
_EDGE_TTS_SAVE_TIMEOUT: float = 120.0  # 秒

async def refresh_edge_tts_key_async(force: bool = True) -> bool:
    """刷新 edge-tts 内部鉴权/配置。

    返回 True/False 表示是否成功。为了简单起见，这里只做一次尝试，
    并做时间间隔节流，防止在高频错误时导致请求风暴。
    """
    global _EDGE_REFRESH_LAST_TS
    with _EDGE_REFRESH_LOCK:
        now = time.time()
        if not force and (now - _EDGE_REFRESH_LAST_TS) < _EDGE_REFRESH_INTERVAL:
            return True
        try:
            # 创建一次 VoicesManager 即可触发内部参数/密钥的重新协商
            await edge_tts.VoicesManager.create()
            _EDGE_REFRESH_LAST_TS = now
            print("Edge TTS 鉴权参数刷新成功")
            return True
        except Exception as e:
            print(f"刷新 Edge TTS 鉴权参数失败: {e}")
            return False


def ensure_mutagen_mp3():
    global _mutagen_mp3_module
    if _mutagen_mp3_module is not None:
        return _mutagen_mp3_module

    script_dir = os.path.dirname(os.path.abspath(__file__))
    removed = False
    if script_dir in sys.path:
        sys.path.remove(script_dir)
        removed = True

    try:
        _mutagen_mp3_module = importlib.import_module("mutagen.mp3")
    except ImportError:
        print("未检测到 mutagen，正在自动安装……")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "mutagen"])
        _mutagen_mp3_module = importlib.import_module("mutagen.mp3")
    finally:
        if removed and script_dir not in sys.path:
            sys.path.insert(0, script_dir)

    return _mutagen_mp3_module


# 自动检查并安装 hanlp，并处理同名脚本导致的导入冲突
def ensure_hanlp():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 移除当前脚本所在目录，避免导入冲突
    if script_dir in sys.path:
        sys.path.remove(script_dir)
    try:
        return importlib.import_module("hanlp")
    except ImportError:
        print("未检测到 hanlp，正在自动安装……")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "hanlp"])
        return importlib.import_module("hanlp")
    finally:
        # 恢复 sys.path
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)

hanlp = ensure_hanlp()


# ---- 折叠面板组件（参考 clipboard_tts.pyw 精简版） ----
class CollapsibleBox(QWidget):
    """简易折叠面板：点击标题按钮展开/收起内容，配合 QSplitter 使用。"""
    toggled = Signal(bool)

    def __init__(self, title: str = "面板", parent=None, expanded: bool = True):
        super().__init__(parent)
        self._base_title = title
        self.toggle_button = QPushButton()
        f = self.toggle_button.font()
        f.setBold(True)
        self.toggle_button.setFont(f)
        self.toggle_button.setCheckable(True)
        self.content_area = QWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content_area)
        self.toggle_button.clicked.connect(self._on_clicked)
        self.set_expanded(expanded)

    def header_height(self):
        return self.toggle_button.sizeHint().height()

    def is_expanded(self):
        return self.toggle_button.isChecked()

    def setContentLayout(self, inner_layout):
        old = self.content_area.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                w = item.widget()
                if w:
                    w.setParent(None)
        self.content_area.setLayout(inner_layout)
        if not self.is_expanded():
            self.content_area.setVisible(False)

    def set_expanded(self, expanded: bool):
        self.toggle_button.setChecked(expanded)
        self.content_area.setVisible(expanded)
        arrow = "▼" if expanded else "►"
        self.toggle_button.setText(f"{arrow} {self._base_title}")
        self.toggled.emit(expanded)

    def _on_clicked(self):
        self.set_expanded(self.toggle_button.isChecked())


def format_timestamp(total_seconds: float) -> str:
    total_milliseconds = max(0, int(round(total_seconds * 1000)))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


class SubtitleGenerator:
    RULE_SMART = "rule_1"
    RULE_NEWLINE = "rule_2"
    RULE_HANLP = "rule_3"

    SPLIT_SYMBOLS = set("。！？!?；;：:,，、")
    MIN_DURATION = 0.4

    _punctuation_replacements = [
        ("……", "..."),
        ("——", "-"),
    ]

    _punctuation_map = str.maketrans({
        "。": ".",
        "，": ",",
        "、": ",",
        "：": ":",
        "；": ";",
        "！": "!",
        "？": "?",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "「": '"',
        "」": '"',
        "『": '"',
        "』": '"',
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "《": "<",
        "》": ">",
        "～": "~",
    })

    @classmethod
    def to_halfwidth_punctuation(cls, text: str) -> str:
        result = text
        for src, dst in cls._punctuation_replacements:
            result = result.replace(src, dst)
        return result.translate(cls._punctuation_map)

    @classmethod
    def to_fullwidth_punctuation(cls, text: str) -> str:
        # 创建反向映射：半角到全角
        reverse_map = str.maketrans({
            ".": "。",
            ",": "，",
            ":": "：",
            ";": "；",
            "!": "！",
            "?": "？",
            "(": "（",
            ")": "）",
            "[": "【",
            "]": "】",
            "<": "《",
            ">": "》",
            "~": "～",
        })
        
        # 先进行字符映射
        result = text.translate(reverse_map)
        
        # 然后处理特殊替换（多字符）
        result = result.replace("——", "——")  # 连字符保持
        result = result.replace("……", "……")  # 省略号保持
        
        return result

    @classmethod
    def remove_punctuation(cls, text: str) -> str:
        """删除标点符号的预处理方法
        
        规则：
        - 删除所有标点符号
        - 行中间的标点替换为空格
        - 行末尾的标点直接删除
        - 保持换行符号，维持多行结构
        """
        lines = text.split('\n')
        result_lines = []
        
        # 定义所有需要处理的标点符号
        all_punctuation = set(cls.SPLIT_SYMBOLS) | set(cls._punctuation_map.keys()) | set(cls._punctuation_map.values())
        # 添加其他常见标点
        all_punctuation |= set('，、；：？！。""''（）【】《》～…—')
        all_punctuation |= set(',.;:?!"\'()[]<>~—…-')
        
        for line in lines:
            if not line.strip():
                result_lines.append(line)
                continue
            
            # 处理每一行
            processed_line = []
            for i, char in enumerate(line):
                if char in all_punctuation:
                    # 检查是否是行末标点（去除末尾空格后）
                    remaining_text = line[i+1:].strip()
                    if not remaining_text:
                        # 行末标点，直接删除
                        continue
                    else:
                        # 行中间标点，替换为空格
                        # 避免连续的空格
                        if processed_line and processed_line[-1] != ' ':
                            processed_line.append(' ')
                else:
                    processed_line.append(char)
            
            result_lines.append(''.join(processed_line).rstrip())
        
        return '\n'.join(result_lines)

    @staticmethod
    def _needs_space(prev_char: str, next_char: str) -> bool:
        if not prev_char or not next_char:
            return False
        if prev_char.isspace() or next_char.isspace():
            return False
        if prev_char.isascii() and next_char.isascii():
            return prev_char.isalnum() and next_char.isalnum()
        return False

    @classmethod
    def split_sentences(cls, text: str) -> list[str]:
        sentences = []
        buffer: list[str] = []

        for char in text:
            if char == "\r":
                continue
            if char == "\n":
                segment = "".join(buffer).strip()
                if segment:
                    sentences.append(segment)
                buffer.clear()
                continue

            buffer.append(char)
            if char in cls.SPLIT_SYMBOLS:
                segment = "".join(buffer).strip()
                if segment:
                    sentences.append(segment)
                buffer.clear()

        if buffer:
            segment = "".join(buffer).strip()
            if segment:
                sentences.append(segment)

        return sentences

    @classmethod
    def _chunk_sentence(cls, sentence: str, limit: int) -> list[str]:
        if limit <= 0:
            return [sentence]
        chunks = []
        start = 0
        while start < len(sentence):
            chunk = sentence[start:start + limit].strip()
            if chunk:
                chunks.append(chunk)
            start += limit
        return chunks or [sentence]

    @classmethod
    def assemble_lines(cls, sentences: list[str], limit: int) -> list[str]:
        if limit <= 0:
            limit = 28

        lines: list[str] = []
        current = ""

        for sentence in sentences:
            segment = sentence.strip()
            if not segment:
                continue

            if len(segment) > limit:
                if current:
                    lines.append(current.strip())
                    current = ""
                lines.extend(cls._chunk_sentence(segment, limit))
                continue

            if not current:
                current = segment
                continue

            separator = " " if cls._needs_space(current[-1], segment[0]) else ""
            tentative = current + separator + segment
            if len(tentative) <= limit:
                current = tentative
            else:
                lines.append(current.strip())
                current = segment

        if current:
            lines.append(current.strip())

        return lines

    @staticmethod
    def _count_characters(lines: list[str]) -> int:
        text = "".join(lines)
        return len("".join(text.split()))

    @classmethod
    def _split_by_newline(cls, text: str) -> list[str]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.strip() for line in normalized.split("\n")]
        return [line for line in lines if line]

    @classmethod
    def _split_by_hanlp(cls, text: str) -> list[str]:
        try:
            # 加载hanlp分句模型
            sent_split = hanlp.pipeline(['sent_split'])
            sentences = sent_split(text)
            return [s.strip() for s in sentences if s.strip()]
        except Exception as e:
            print(f"hanlp分句失败，使用默认分句: {e}")
            return cls.split_sentences(text)

    @classmethod
    def _prepare_lines(
        cls,
        text: str,
        rule: str,
        line_length: int,
    ) -> list[str]:
        if rule == cls.RULE_NEWLINE:
            return cls._split_by_newline(text)
        elif rule == cls.RULE_HANLP:
            sentences = cls._split_by_hanlp(text)
            if not sentences:
                return []
            return cls.assemble_lines(sentences, line_length)

        sentences = cls.split_sentences(text)
        if not sentences:
            return []
        return cls.assemble_lines(sentences, line_length)

    @classmethod
    def build_srt(
        cls,
        text: str,
        duration: float,
        line_length: int,
        convert_punctuation: bool,
        rule: str = RULE_SMART,
        subtitle_lines: int = 1,
    ) -> str:
        lines = cls._prepare_lines(text, rule, line_length)
        if not lines:
            return ""

        if convert_punctuation:
            lines = [cls.to_halfwidth_punctuation(line) for line in lines]

        # 按指定的行数分组成字幕块
        cues = [lines[i:i + subtitle_lines] for i in range(0, len(lines), subtitle_lines)]
        total_chars = sum(max(1, cls._count_characters(cue)) for cue in cues)

        if total_chars <= 0 or duration <= 0:
            return ""

        elapsed_chars = 0
        srt_output: list[str] = []
        cue_count = len(cues)

        for index, cue_lines in enumerate(cues, start=1):
            char_count = max(1, cls._count_characters(cue_lines))
            start_ratio = elapsed_chars / total_chars
            start_time = duration * start_ratio

            elapsed_chars += char_count
            end_ratio = min(1.0, elapsed_chars / total_chars)
            end_time = duration * end_ratio

            if end_time - start_time < cls.MIN_DURATION:
                end_time = min(duration, start_time + cls.MIN_DURATION)

            if index == cue_count:
                end_time = duration

            srt_output.append(str(index))
            srt_output.append(f"{format_timestamp(start_time)} --> {format_timestamp(end_time)}")
            srt_output.extend(cue_lines)
            srt_output.append("")

        return "\n".join(srt_output).strip() + "\n"

class TTSWorker(QThread):
    progress = Signal(str)
    finished = Signal(str)  # Pass worker's voice name on finish

    def __init__(
        self,
        voice: str,
        parent=None,
        tts_mode: str = "edge",
        srt_enabled: bool = False,
        line_length: int = 28,
        convert_punctuation: bool = False,
        subtitle_rule: str = SubtitleGenerator.RULE_SMART,
        output_root: str | None = None,
        extra_line_output: bool = False,
        default_output: bool = True,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
        enable_emotion: bool = False,
        style: str = "general",
        styledegree: str = "1.0",
        role: str = "",
        subtitle_lines: int = 1,
        selected_txt_files: list[str] | None = None,
    ):
        super().__init__(parent)
        self.voice = voice
        self.tts_mode = (tts_mode or "edge").strip().lower()
        self.output_ext = ".mp3"
        self.srt_enabled = srt_enabled
        self.line_length = max(5, int(line_length or 0))
        self.convert_punctuation = convert_punctuation
        self.subtitle_rule = subtitle_rule
        self.extra_line_output = extra_line_output
        self.default_output = default_output
        self.output_root = output_root or os.path.dirname(os.path.abspath(__file__))
        self.subtitle_lines = max(1, int(subtitle_lines or 1))
        os.makedirs(self.output_root, exist_ok=True)
        # 情绪控制参数
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.enable_emotion = enable_emotion
        self.style = style
        self.styledegree = styledegree
        self.role = role
        # 仅处理的文本文件（可选）：若为 None 则扫描目录全部 .txt
        self.selected_txt_files = list(selected_txt_files) if selected_txt_files else None

    def _get_azure_endpoint_and_keys(self) -> tuple[str, list[str]]:
        parent = self.parent()

        endpoint = ""
        region = ""
        keys: list[str] = []

        if parent is not None:
            endpoint = str(getattr(parent, "azure_tts_endpoint", "") or "")
            region = str(getattr(parent, "azure_speech_region", "") or "")
            raw_keys = getattr(parent, "azure_speech_keys", None)
            if isinstance(raw_keys, list):
                keys = [str(k) for k in raw_keys if str(k).strip()]

        env_endpoint = _get_env_var("AZURE_TTS_ENDPOINT") or _get_env_var("AZURE_SPEECH_ENDPOINT")
        if env_endpoint:
            endpoint = env_endpoint

        env_region = (
            _get_env_var("AZURE_SPEECH_REGION")
            or _get_env_var("AZURE_TTS_REGION")
            or _get_env_var("AZURE_REGION")
        )
        if env_region:
            region = env_region

        # Keys: prefer AZURE_SPEECH_KEYS="k1,k2"; fallback to KEY/KEY2
        env_keys = _get_env_var("AZURE_SPEECH_KEYS") or _get_env_var("AZURE_TTS_KEYS")
        if env_keys:
            keys = [k.strip() for k in env_keys.split(",") if k.strip()]
        else:
            key1 = _get_env_var("AZURE_SPEECH_KEY") or _get_env_var("AZURE_TTS_KEY")
            key2 = _get_env_var("AZURE_SPEECH_KEY2") or _get_env_var("AZURE_TTS_KEY2")
            if key1:
                keys = [key1.strip()]
                if key2 and key2.strip() and key2.strip() != key1.strip():
                    keys.append(key2.strip())

        # 内置默认终结点（避免用户未设置 endpoint/region 导致 Azure 模式直接报错）
        if not endpoint and not region:
            endpoint = _DEFAULT_AZURE_ENDPOINT_BASE

        endpoint = _normalize_azure_speech_endpoint(endpoint_or_base=endpoint, region=region)

        return endpoint, keys

    def _build_azure_ssml(self, text: str, force_plain: bool = False) -> str:
        plain = escape(text.strip())

        # 只有在启用情绪控制且情绪不是普通时才添加标签
        use_emotion = (not force_plain) and self.enable_emotion and self.style != "general"
        if use_emotion:
            express_attrs = [f'style="{self.style}"', f'styledegree="{self.styledegree}"']
            if self.role:
                express_attrs.append(f'role="{self.role}"')
            attrs_str = " ".join(express_attrs)
            inner = f"<mstts:express-as {attrs_str}>{plain}</mstts:express-as>"
        else:
            inner = plain

        return (
            "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' "
            "xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='zh-CN'>"
            f"<voice name='{self.voice}'>"
            f"<prosody pitch='{self.pitch}' rate='{self.rate}' volume='{self.volume}'>"
            f"{inner}"
            "</prosody>"
            "</voice>"
            "</speak>"
        )

    def _azure_tts_save_sync(self, ssml: str, endpoint: str, keys: list[str], output: str) -> None:
        if not endpoint:
            raise Exception(
                "Azure 模式缺少 Endpoint/Region。请设置环境变量 AZURE_TTS_ENDPOINT 或 AZURE_SPEECH_REGION。"
            )
        if not keys:
            raise Exception(
                "Azure 模式缺少 Key。请设置环境变量 AZURE_SPEECH_KEY（可选 AZURE_SPEECH_KEY2 / AZURE_SPEECH_KEYS）。"
            )

        last_error: Exception | None = None
        for idx, key in enumerate(keys):
            try:
                req = urllib.request.Request(
                    endpoint,
                    data=ssml.encode("utf-8"),
                    method="POST",
                    headers={
                        "Ocp-Apim-Subscription-Key": key,
                        "Content-Type": "application/ssml+xml",
                        "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
                        "User-Agent": "tts/1.pyw",
                    },
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    audio = resp.read()

                if not audio:
                    raise Exception("Azure TTS 返回空内容。")

                with open(output, "wb") as f:
                    f.write(audio)
                return
            except urllib.error.HTTPError as e:
                try:
                    body = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    body = ""

                msg = f"Azure TTS 请求失败（HTTP {getattr(e, 'code', '?')}）"
                if body.strip():
                    msg += f": {body.strip()}"

                # 401/403 时尝试备用 Key
                if getattr(e, "code", None) in (401, 403) and idx < (len(keys) - 1):
                    last_error = Exception(msg)
                    continue

                raise Exception(msg)
            except Exception as e:
                last_error = e
                if idx < (len(keys) - 1):
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise Exception("Azure TTS 调用失败（未知原因）。")

    async def azure_tts_async(self, text: str, output: str) -> None:
        endpoint, keys = self._get_azure_endpoint_and_keys()

        def _remove_if_empty(path: str):
            if os.path.exists(path) and os.path.getsize(path) == 0:
                try:
                    os.remove(path)
                except OSError:
                    pass

        ssml = self._build_azure_ssml(text, force_plain=False)
        try:
            await asyncio.to_thread(self._azure_tts_save_sync, ssml, endpoint, keys, output)
            if os.path.exists(output) and os.path.getsize(output) == 0:
                _remove_if_empty(output)
                raise Exception("生成的音频文件为空 (0 bytes)。")
            self.progress.emit(f"    ✓ [{self.voice}] (Azure) 语音已保存到 {os.path.basename(output)}")
            return
        except Exception as e:
            # 若启用了情绪，尝试纯文本回退
            if self.enable_emotion and self.style != "general":
                self.progress.emit(f"    ⚠ [{self.voice}] (Azure) 情绪 SSML 可能不被接受，改用纯文本回退…")
                try:
                    ssml_plain = self._build_azure_ssml(text, force_plain=True)
                    await asyncio.to_thread(self._azure_tts_save_sync, ssml_plain, endpoint, keys, output)
                    if os.path.exists(output) and os.path.getsize(output) == 0:
                        _remove_if_empty(output)
                        raise Exception("生成的音频文件为空 (0 bytes)。")
                    self.progress.emit(f"    ✓ [{self.voice}] (Azure) 纯文本回退成功，已保存 {os.path.basename(output)}")
                    return
                except Exception as e2:
                    _remove_if_empty(output)
                    raise Exception(
                        f"Azure TTS 合成失败：{e2}.\n"
                        "请检查：Endpoint/Region 是否正确、Key 是否有效、网络是否可访问 Azure Speech。"
                    )

            _remove_if_empty(output)
            raise Exception(
                f"Azure TTS 合成失败：{e}.\n"
                "请检查：Endpoint/Region 是否正确、Key 是否有效、网络是否可访问 Azure Speech。"
            )

    def build_ssml_text(self, text: str):
        """构建包含情绪标签的文本
        
        通过edge_tts_patch的猴子补丁,可以使用SSML标签
        补丁会在生成最终SSML时正确处理express-as标签
        """
        text = text.strip()
        
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

    async def tts_async(self, text, voice, output):
        # Azure 模式：走 Azure Speech 官方 REST TTS
        if (self.tts_mode or "edge") == "azure":
            await self.azure_tts_async(text=text, output=output)
            return

        """调用 Edge TTS（新版优先）并在失败时做多重回退：
        1) 若运行环境存在 async_api.Communicate，则优先使用
        2) 否则直接使用 edge_tts.Communicate（edge-tts 7.x 主入口）
        3) 若疑似鉴权/403，刷新 VoicesManager 后再试一次
        4) 若仍无音频，禁用自定义 SSML 情绪补丁，改用纯文本重试
        5) 所有失败路径均避免产生 0 字节文件，并输出明确错误信息
        """

        def _remove_if_empty(path: str):
            if os.path.exists(path) and os.path.getsize(path) == 0:
                try:
                    os.remove(path)
                except OSError:
                    pass

        # 第一次：按当前设置构建 SSML（可能包含 mstts:express-as）
        ssml_text = self.build_ssml_text(text)

        last_error: Exception | None = None

        def _has_async_api() -> bool:
            try:
                _ = getattr(edge_tts, "async_api")
                from edge_tts import async_api  # type: ignore
                _ = getattr(async_api, "Communicate")
                return True
            except Exception:
                return False

        async def _try_save(current_text: str, prefer_async_api: bool) -> None:
            communicate = None
            if prefer_async_api and _has_async_api():
                from edge_tts import async_api  # type: ignore
                communicate = async_api.Communicate(
                    current_text,
                    voice,
                    rate=self.rate,
                    pitch=self.pitch,
                    volume=self.volume,
                )
                self.progress.emit(f"    → [{self.voice}] 使用 async_api 合成…")
            else:
                communicate = edge_tts.Communicate(
                    current_text,
                    voice,
                    rate=self.rate,
                    pitch=self.pitch,
                    volume=self.volume,
                )
                self.progress.emit(f"    → [{self.voice}] 使用 Communicate 合成…")

            try:
                await asyncio.wait_for(communicate.save(output), timeout=_EDGE_TTS_SAVE_TIMEOUT)
            except asyncio.TimeoutError:
                _remove_if_empty(output)
                raise Exception(f"合成超时（>{int(_EDGE_TTS_SAVE_TIMEOUT)}s）。可能是网络阻断/服务不可达/连接卡死。")
            # 防止 0 字节伪成功
            if os.path.exists(output) and os.path.getsize(output) == 0:
                _remove_if_empty(output)
                raise Exception("生成的音频文件为空 (0 bytes)。可能是网络连接被拒绝或服务暂时不可用。")

        # 尝试顺序：若可用则 async_api -> Communicate；遇到鉴权错误时刷新一次再试
        for attempt in range(2):
            try:
                try:
                    await _try_save(ssml_text, prefer_async_api=True)
                except Exception:
                    await _try_save(ssml_text, prefer_async_api=False)

                # 成功
                self.progress.emit(f"    ✓ [{self.voice}] 语音已保存到 {os.path.basename(output)}")
                return
            except Exception as e:
                last_error = e
                err = str(e)
                auth_error = (
                    ('401' in err) or
                    ('403' in err) or
                    ('Unauthorized' in err) or
                    ('Invalid response status' in err) or
                    ('No audio was received' in err)
                )
                if auth_error and attempt == 0:
                    self.progress.emit(f"    ↻ [{self.voice}] 疑似鉴权/403，正在刷新参数后重试…")
                    try:
                        await refresh_edge_tts_key_async(force=True)
                    except Exception as rf_e:
                        self.progress.emit(f"    ⚠ 刷新鉴权失败: {rf_e}")
                    await asyncio.sleep(0.8)
                    continue
                break

        # 若到此仍失败：尝试禁用情绪 SSML，改用纯文本重试（部分服务端策略会拒绝自定义 SSML）
        self.progress.emit(f"    ⚠ [{self.voice}] SSML情绪可能被拒绝，改用纯文本回退…")
        plain_text = text.strip()
        try:
            try:
                await _try_save(plain_text, prefer_async_api=True)
            except Exception:
                await _try_save(plain_text, prefer_async_api=False)
            self.progress.emit(f"    ✓ [{self.voice}] 纯文本回退成功，已保存 {os.path.basename(output)}")
            return
        except Exception as e2:
            _remove_if_empty(output)
            # 最终失败，抛出更明确的错误
            raise Exception(
                f"Edge TTS 合成失败：{e2}. 可能原因：服务端拒绝（403/NoAudio），或 Read Aloud API 政策变更。\n"
                f"建议：更换网络出口/代理后重试，或在设置中改用 Azure Speech 官方 TTS。"
            )

    def get_audio_duration(self, audio_path: str) -> float:
        try:
            mp3_module = ensure_mutagen_mp3()
            audio = mp3_module.MP3(audio_path)
            return float(getattr(audio.info, "length", 0.0))
        except Exception as exc:
            self.progress.emit(f"    ⚠ [{self.voice}] 无法读取音频时长: {exc}")
            return 0.0

    def _sanitize_filename(self, text: str, existing: set[str]) -> str:
        sanitized = re.sub(r'[\\/:*?"<>|]', '_', text.strip())
        sanitized = sanitized.replace('\n', ' ').replace('\t', ' ')
        sanitized = sanitized[:80] if len(sanitized) > 80 else sanitized
        if not sanitized:
            sanitized = "行音频"

        candidate = sanitized
        suffix = 1
        while candidate.lower() in existing:
            candidate = f"{sanitized}_{suffix}"
            suffix += 1

        existing.add(candidate.lower())
        return candidate

    async def generate_line_audio(self, text: str, base_name: str, line_output_dir: str) -> None:
        lines = SubtitleGenerator._prepare_lines(text, self.subtitle_rule, self.line_length)
        if not lines:
            self.progress.emit(f"    ⚠ [{self.voice}] 按行输出时未生成有效行，已跳过。")
            return

        os.makedirs(line_output_dir, exist_ok=True)

        existing_names: set[str] = set()
        total = len(lines)
        width = len(str(total))
        for idx, line in enumerate(lines, start=1):
            safe_name = self._sanitize_filename(line, existing_names)
            numbered_name = f"{idx:0{width}d}_{safe_name}" if width > 0 else safe_name
            output_path = os.path.join(line_output_dir, f"{numbered_name}{self.output_ext}")
            await self.tts_async(line, self.voice, output_path)
        relative_path = os.path.relpath(line_output_dir, self.output_root)
        self.progress.emit(f"    ✓ [{self.voice}] 行级音频已输出至 {relative_path}")

    def generate_srt_file(self, text: str, audio_path: str, srt_path: str) -> None:
        duration = self.get_audio_duration(audio_path)
        if duration <= 0:
            self.progress.emit(f"    ⚠ [{self.voice}] 音频时长无效，跳过字幕生成。")
            return

        srt_content = SubtitleGenerator.build_srt(
            text,
            duration,
            self.line_length,
            self.convert_punctuation,
            self.subtitle_rule,
            self.subtitle_lines,
        )

        if not srt_content.strip():
            self.progress.emit(f"    ⚠ [{self.voice}] 文本不足，未生成字幕。")
            return

        try:
            with open(srt_path, "w", encoding="utf-8") as srt_file:
                srt_file.write(srt_content)
            self.progress.emit(f"    ✓ [{self.voice}] 字幕已保存到 {os.path.basename(srt_path)}")
        except Exception as exc:
            self.progress.emit(f"    ⚠ [{self.voice}] 写入字幕失败: {exc}")

    async def main_task(self):
        dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "txt")
        os.makedirs(dir_path, exist_ok=True)
        # 使用传入的选择列表，否则扫描 txt 子目录全部
        if self.selected_txt_files is not None:
            files = [f for f in self.selected_txt_files if f.lower().endswith('.txt')]
        else:
            files = [f for f in os.listdir(dir_path) if f.lower().endswith('.txt')]
        if not files:
            # 需要穿透日志过滤（否则用户只看到线程结束，看不到原因）
            self.progress.emit(f"⚠ [{self.voice}] txt 子目录未找到任何 .txt 文件！")
            return

        self.progress.emit(f"[{self.voice}] 开始处理任务...")
        for txt_file in files:
            txt_path = os.path.join(dir_path, txt_file)
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    text = f.read().strip()
                if not text:
                    # 需要穿透日志过滤（否则用户只看到没输出）
                    self.progress.emit(f"⚠ [{self.voice}] {txt_file} 为空，已跳过。")
                    continue

                self.progress.emit(f"[{datetime.now().strftime('%H:%M:%S')}] [{self.voice}] 开始处理 {txt_file}")
                
                base_name = os.path.splitext(txt_file)[0]
                txt_output_dir = os.path.join(self.output_root, base_name)
                voice_output_dir = os.path.join(txt_output_dir, self.voice)

                if self.default_output or self.extra_line_output:
                    os.makedirs(voice_output_dir, exist_ok=True)

                if self.default_output:
                    output_file = f"{base_name}{self.output_ext}"
                    output_path = os.path.join(voice_output_dir, output_file)
                    await self.tts_async(text, self.voice, output_path)

                    if self.srt_enabled:
                        srt_file = f"{base_name}.srt"
                        srt_path = os.path.join(voice_output_dir, srt_file)
                        self.generate_srt_file(text, output_path, srt_path)

                if self.extra_line_output:
                    line_dir = os.path.join(voice_output_dir, "lines")
                    await self.generate_line_audio(text, base_name, line_dir)

                self.progress.emit("")

            except Exception as e:
                # 需要穿透日志过滤（否则错误会被过滤掉，表现为“鉴权没用/没结果”）
                self.progress.emit(f"✗ [{self.voice}] 处理 {txt_file} 出错: {e}")
        
        self.progress.emit(f"[{self.voice}] 任务处理完毕！")

    def run(self):
        asyncio.run(self.main_task())
        parent = self.parent()
        if parent is not None and hasattr(parent, "save_settings"):
            parent.save_settings()
        self.finished.emit(self.voice)


class TTSApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("微软 Edge TTS 文本转语音助手")
        self._default_geometry = (160, 160, 560, 800)  # 增加窗口高度以容纳情绪控制面板
        self.setGeometry(*self._default_geometry)
        self._settings_geometry_loaded = False

        # 日志视图（提前创建，确保 populate_voices 的错误能显示在 UI 中）
        self.log_view = QTextEdit(); self.log_view.setReadOnly(True)

        # 根布局
        self.root_layout = QVBoxLayout(self)

        # Azure 配置（可由环境变量或 tts_settings.json 提供）
        self.azure_speech_region: str = ""
        # 默认给 eastasia 的基础终结点，避免 Azure 模式提示“未设置终结点”
        self.azure_tts_endpoint: str = _DEFAULT_AZURE_ENDPOINT_BASE
        self.azure_speech_keys: list[str] = []

        # 模式选择（满行下拉栏，默认 Azure）
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Azure 模式", "azure")
        self.mode_combo.addItem("Edge 模式", "edge")
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.setToolTip("选择 TTS 接口模式：Azure Speech（官方）或 Edge（免 Key）。")
        self.mode_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)


        # 确保 ./txt 子目录存在并迁移当前同级旧版 txt 文件
        self._ensure_text_dir_and_migrate()

        # 语音模型树
        self.label_voice = QLabel("选择语音模型 (可多选):")
        self.voice_tree = QTreeWidget()
        self.voice_tree.setHeaderLabels(["名称", "性别", "类别", "个性"])
        self.voice_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.voice_tree.setSortingEnabled(True)
        header = self.voice_tree.header()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        self.voice_tree.sortByColumn(0, Qt.AscendingOrder)
        self.voice_items = {}
        self.populate_voices()
        
        # 添加已选择模型的提示标签（无背景，使用主题文本色）
        self.selected_voices_label = QLabel("已选择: 0 个模型")
        self.selected_voices_label.setStyleSheet("QLabel { font-weight: bold; padding: 3px; }")
        self.selected_voices_label.setWordWrap(True)
        
        # 连接树控件的itemChanged信号以更新选择提示
        self.voice_tree.itemChanged.connect(self._update_selected_voices_label)

        # 标点转换控件
        self.punctuation_layout = QHBoxLayout()
        # 手动刷新鉴权按钮（放在标点转换行的最左侧）
        self.refresh_auth_button = QPushButton("刷新鉴权")
        self.refresh_auth_button.setToolTip("手动刷新 Edge TTS 的鉴权参数，解决 401/连接异常后立即恢复。")
        self.refresh_auth_button.clicked.connect(self._on_manual_refresh_auth)

        # 获取远程用量指标（Azure Monitor）
        self.fetch_metrics_button = QPushButton("获取用量")
        self.fetch_metrics_button.setToolTip(
            "从 Azure Monitor 拉取 Speech 资源用量指标（需要服务主体与资源信息环境变量）。\n"
            "需要：AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET\n"
            "以及：AZURE_SUBSCRIPTION_ID / AZURE_RESOURCE_GROUP / AZURE_SPEECH_RESOURCE_NAME"
        )
        self.fetch_metrics_button.clicked.connect(self._on_fetch_remote_metrics)

        self.punctuation_label = QLabel("标点转换:")
        self.punctuation_combo = QComboBox()
        self.punctuation_combo.addItem("不转换", "none")
        self.punctuation_combo.addItem("中文标点 → 英文标点", "to_halfwidth")
        self.punctuation_combo.addItem("英文标点 → 中文标点", "to_fullwidth")
        self.punctuation_combo.addItem("删除标点符号", "remove_punctuation")
        self.punctuation_combo.setToolTip("选择后立即对 txt 子目录内所有 txt 文件执行转换")
        self.punctuation_layout.addWidget(self.refresh_auth_button)
        self.punctuation_layout.addWidget(self.fetch_metrics_button)
        self.punctuation_layout.addWidget(self.punctuation_label)
        self.punctuation_layout.addWidget(self.punctuation_combo)



        # 选项区
        self.options_layout = QHBoxLayout()
        self.default_output_checkbox = QCheckBox("完整输出")
        self.default_output_checkbox.setChecked(True)
        self.srt_checkbox = QCheckBox("生成字幕")
        self.srt_checkbox.setChecked(True)
        self.extra_line_checkbox = QCheckBox("分行输出")
        self.rule_label = QLabel("分行规则:")
        self.subtitle_rule_combo = QComboBox()
        self.subtitle_rule_combo.addItem("规则1：按换行切分 (默认)", SubtitleGenerator.RULE_NEWLINE)
        self.subtitle_rule_combo.addItem("规则2：智能分句", SubtitleGenerator.RULE_SMART)
        self.subtitle_rule_combo.addItem("规则3：hanlp分句", SubtitleGenerator.RULE_HANLP)
        self.subtitle_rule_combo.setToolTip("选择字幕切分方式")
        self.line_length_label = QLabel("行字数(约):")
        self.line_length_input = QLineEdit("28")
        self.line_length_input.setValidator(QIntValidator(5, 120, self))
        self.line_length_input.setFixedWidth(40)
        # 新增：字幕块行数设置
        self.subtitle_lines_label = QLabel("块行数:")
        self.subtitle_lines_input = QLineEdit("1")
        self.subtitle_lines_input.setValidator(QIntValidator(1, 10, self))
        self.subtitle_lines_input.setFixedWidth(40)
        self.subtitle_lines_input.setToolTip("每个字幕块包含的行数 (1-10)")
        self.options_layout.addWidget(self.default_output_checkbox)
        self.options_layout.addWidget(self.extra_line_checkbox)
        self.options_layout.addWidget(self.srt_checkbox)
        self.options_layout.addWidget(self.subtitle_lines_label)
        self.options_layout.addWidget(self.subtitle_lines_input)
        self.options_layout.addWidget(self.rule_label)
        self.options_layout.addWidget(self.subtitle_rule_combo)
        self.options_layout.addWidget(self.line_length_label)
        self.options_layout.addWidget(self.line_length_input)
        self.options_layout.addStretch()

        # ========== 语音参数控制 ==========
        self.voice_params_layout = QHBoxLayout()
        
        # 语速控制
        self.rate_label = QLabel("语速:")
        self.rate_combo = QComboBox()
        rate_options = ["-50%", "-25%", "+0%", "+25%", "+50%"]
        self.rate_combo.addItems(rate_options)
        self.rate_combo.setCurrentText("+0%")
        
        # 音调控制
        self.pitch_label = QLabel("音调:")
        self.pitch_combo = QComboBox()
        pitch_options = ["-50Hz", "-25Hz", "+0Hz", "+25Hz", "+50Hz"]
        self.pitch_combo.addItems(pitch_options)
        self.pitch_combo.setCurrentText("+0Hz")
        
        # 音量控制
        self.volume_label = QLabel("音量:")
        self.volume_combo = QComboBox()
        volume_options = ["-50%", "-25%", "+0%", "+25%", "+50%"]
        self.volume_combo.addItems(volume_options)
        self.volume_combo.setCurrentText("+0%")
        
        self.voice_params_layout.addWidget(self.rate_label)
        self.voice_params_layout.addWidget(self.rate_combo)
        self.voice_params_layout.addWidget(self.pitch_label)
        self.voice_params_layout.addWidget(self.pitch_combo)
        self.voice_params_layout.addWidget(self.volume_label)
        self.voice_params_layout.addWidget(self.volume_combo)
        self.voice_params_layout.addStretch()

        # ========== 情绪控制选项 (SSML) ==========
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

        # 保存情绪控制的控件引用,便于启用/禁用
        self.emotion_widgets = [
            self.style_label, self.style_combo,
            self.styledegree_label, self.styledegree_slider,
            self.role_label, self.role_combo
        ]
        # 初始状态设为禁用（使用整数0表示未选中）
        self._toggle_emotion_controls(0)

        # 开始按钮
        self.start_button = QPushButton("开始转换")
        self.start_button.clicked.connect(self.start_tts)

        # ========== 折叠面板结构 ==========
        self.splitter = QSplitter(Qt.Vertical)
        self.root_layout.addWidget(self.splitter)

        # 设置面板（顶部）
        self.settings_box = CollapsibleBox("设置", expanded=True)
        settings_inner = QVBoxLayout(); settings_inner.setContentsMargins(8,8,8,8); settings_inner.setSpacing(6)
        settings_inner.addWidget(self.mode_combo)
        settings_inner.addLayout(self.punctuation_layout)
        settings_inner.addLayout(self.options_layout)
        
        # 添加语音参数控制
        settings_inner.addWidget(QLabel("<b>基础参数:</b>"))
        settings_inner.addLayout(self.voice_params_layout)
        
        # 添加情绪控制
        settings_inner.addWidget(QLabel("<b>🎭 情绪控制 (SSML):</b>"))
        
        # 添加说明标签
        emotion_help_label = QLabel("⚠️ 注意：不同语音支持的情绪不同，部分情绪可能无效果。\n推荐使用中文语音（如晓晓/云希/云扬）测试情绪功能。")
        emotion_help_label.setWordWrap(True)
        emotion_help_label.setStyleSheet("color: #666; font-size: 10px; padding: 3px; background: #f0f0f0; border-radius: 3px;")
        settings_inner.addWidget(emotion_help_label)
        
        settings_inner.addWidget(self.enable_emotion_checkbox)
        
        # 情绪选择
        emotion_style_layout = QHBoxLayout()
        emotion_style_layout.addWidget(self.style_label)
        emotion_style_layout.addWidget(self.style_combo, 1)
        settings_inner.addLayout(emotion_style_layout)
        
        # 强度滑动条
        settings_inner.addWidget(self.styledegree_label)
        settings_inner.addWidget(self.styledegree_slider)
        
        # 角色控制
        role_layout = QHBoxLayout()
        role_layout.addWidget(self.role_label)
        role_layout.addWidget(self.role_combo)
        role_layout.addStretch()
        settings_inner.addLayout(role_layout)
        
        settings_inner.addWidget(self.start_button, 0, Qt.AlignLeft)
        self.settings_box.setContentLayout(settings_inner)
        self.splitter.addWidget(self.settings_box)

        # 文本选择面板（新增加）
        self.text_box = CollapsibleBox("文本选择", expanded=True)
        text_inner = QVBoxLayout(); text_inner.setContentsMargins(8,8,8,8); text_inner.setSpacing(6)
        self.label_text = QLabel("选择文本 (可多选):")
        self.text_tree = QTreeWidget()
        self.text_tree.setHeaderLabels(["文件名"]) 
        self.text_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        # 已选择文本提示标签（无背景，使用主题文本色）
        self.selected_texts_label = QLabel("已选择: 0 个文本")
        self.selected_texts_label.setStyleSheet("QLabel { font-weight: bold; padding: 3px; }")
        self.selected_texts_label.setWordWrap(True)
        # 填充TXT文件树（默认全选）
        self.populate_texts()
        # 连接改变信号
        self.text_tree.itemChanged.connect(self._update_selected_texts_label)
        text_inner.addWidget(self.label_text)
        text_inner.addWidget(self.selected_texts_label)
        text_inner.addWidget(self.text_tree)
        self.text_box.setContentLayout(text_inner)
        # 插入到 设置 与 语音 模块之间
        self.splitter.addWidget(self.text_box)

        # 语音模型面板
        self.voice_box = CollapsibleBox("语音模型", expanded=True)
        voice_inner = QVBoxLayout(); voice_inner.setContentsMargins(8,8,8,8); voice_inner.setSpacing(6)
        voice_inner.addWidget(self.label_voice)
        voice_inner.addWidget(self.selected_voices_label)  # 添加已选择模型提示
        voice_inner.addWidget(self.voice_tree)
        self.voice_box.setContentLayout(voice_inner)
        self.splitter.addWidget(self.voice_box)

        # 日志面板
        self.log_box = CollapsibleBox("日志", expanded=True)
        log_inner = QVBoxLayout(); log_inner.setContentsMargins(8,8,8,8); log_inner.setSpacing(6)
        log_inner.addWidget(self.log_view)
        self.log_box.setContentLayout(log_inner)
        self.splitter.addWidget(self.log_box)

        # 填充占位，保证折叠后贴顶
        self.bottom_filler = QWidget(); self.bottom_filler.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.splitter.addWidget(self.bottom_filler)

        # 保存展开尺寸
        self._panel_saved_sizes = {"text": None, "voice": None, "log": None}
        for b in (self.settings_box, self.text_box, self.voice_box, self.log_box):
            b.toggled.connect(self.update_splitter_sizes)
        self.splitter.splitterMoved.connect(lambda *_: self._store_expanded_sizes())
        # 附加：拖动后进行约束修正，避免覆盖折叠标题或挤压内容
        self.splitter.splitterMoved.connect(lambda *_: self._enforce_splitter_constraints())

        # 初始尺寸分配（异步等待渲染完成）
        from PySide6.QtCore import QTimer as _QT
        _QT.singleShot(0, self.update_splitter_sizes)

        # 信号连接（原有逻辑）
        self.punctuation_combo.currentIndexChanged.connect(self.execute_punctuation_conversion)
        self.default_output_checkbox.toggled.connect(self.update_option_states)
        self.srt_checkbox.toggled.connect(self.update_option_states)
        self.subtitle_rule_combo.currentIndexChanged.connect(self.update_option_states)
        self.extra_line_checkbox.toggled.connect(self.update_option_states)
        self.update_option_states()

        self.workers = {}

        self._loading_settings = False
        self.load_settings()

        self.log_view.append("===============================")
        self.log_view.append(" 微软 Edge TTS 文本转语音助手")
        self.log_view.append("===============================")
        self.log_view.append("1. 将需要转换的文本放在 txt 子目录 (./txt) 内的 .txt 文件中")
        self.log_view.append("2. 在下方树状列表中勾选一个或多个语音模型")
        self.log_view.append("3. 点击“开始转换”按钮启动")
        self.log_view.append("4. 可选：勾选“同步生成 SRT 字幕文件”并调整参数")
        self.log_view.append("")

    def populate_texts(self):
        """扫描 txt 子目录的 .txt 文件，填充至文本树（默认全选）。"""
        try:
            self.text_tree.blockSignals(True)
            self.text_tree.clear()
            dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "txt")
            os.makedirs(dir_path, exist_ok=True)
            txt_files = sorted([f for f in os.listdir(dir_path) if f.lower().endswith('.txt')])
            # 顶层汇总节点，便于一键全选/全不选
            root_item = QTreeWidgetItem(self.text_tree, ["TXT 文件"])
            root_item.setFlags(root_item.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
            root_item.setCheckState(0, Qt.Checked)
            for name in txt_files:
                child = QTreeWidgetItem(root_item, [name])
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Checked)
        finally:
            self.text_tree.blockSignals(False)
        # 初始化已选择提示
        self._update_selected_texts_label()

    def get_selected_texts(self) -> list[str]:
        """返回用户勾选的 .txt 文件名列表（位于 ./txt 子目录）。"""
        results: list[str] = []
        root = self.text_tree.invisibleRootItem()
        for i in range(root.childCount()):
            top = root.child(i)
            for j in range(top.childCount()):
                item = top.child(j)
                if item.checkState(0) == Qt.Checked:
                    results.append(item.text(0))
            # 若意外无子项且顶层被选中
            if top.childCount() == 0 and top.checkState(0) == Qt.Checked:
                name = top.text(0)
                if name.lower().endswith('.txt'):
                    results.append(name)
        return results

    def _update_selected_texts_label(self, *args):
        selected = self.get_selected_texts()
        count = len(selected)
        if count == 0:
            self.selected_texts_label.setText("已选择: 0 个文本")
        elif count <= 5:
            names = ", ".join(selected)
            self.selected_texts_label.setText(f"已选择 {count} 个文本: {names}")
        else:
            preview = ", ".join(selected[:5])
            self.selected_texts_label.setText(f"已选择 {count} 个文本: {preview}... 等")

    def _on_manual_refresh_auth(self):
        """手动刷新 Edge TTS 鉴权参数。"""
        try:
            # 起始提示不再显示（按需求仅显示完成信息），故不记录此行
            QApplication.setOverrideCursor(Qt.WaitCursor)
            success = asyncio.run(refresh_edge_tts_key_async(force=True))
        except Exception as e:
            success = False
            self.log_view.append(f"⚠ 刷新异常: {e} AYE:建议切换网络后尝试..")
        finally:
            QApplication.restoreOverrideCursor()
        if success:
            self.log_view.append("✓ 鉴权刷新成功。")
        else:
            self.log_view.append("⚠ 鉴权刷新失败，请稍后重试或检查网络。AYE:建议切换网络后尝试..")

    def _on_fetch_remote_metrics(self):
        """拉取 Azure Monitor 远程指标并输出到日志。"""

        class _MetricsWorker(QThread):
            log = Signal(str)

            def run(self):
                try:
                    totals = _azure_fetch_speech_usage_metrics(days=30)
                    # 输出关键指标
                    chars = totals.get("SynthesizedCharacters")
                    vid_secs = totals.get("VideoSecondsSynthesized")
                    host_hours = totals.get("VoiceModelHostingHours")
                    train_mins = totals.get("VoiceModelTrainingMinutes")

                    self.log.emit("✓ Azure 远程用量（近30天，总计）:")
                    if chars is not None:
                        self.log.emit(f"  - SynthesizedCharacters: {int(chars):,}")
                    if vid_secs is not None:
                        self.log.emit(f"  - VideoSecondsSynthesized: {int(vid_secs):,}")
                    if host_hours is not None:
                        self.log.emit(f"  - VoiceModelHostingHours: {host_hours:.2f}")
                    if train_mins is not None:
                        self.log.emit(f"  - VoiceModelTrainingMinutes: {train_mins:.2f}")

                    # 若没有任何值，提示用户去 Portal 确认
                    if not totals:
                        self.log.emit("⚠ 未返回任何指标值（可能是权限不足/资源类型不对/时间范围内无数据）。")
                except Exception as e:
                    self.log.emit(
                        "⚠ 获取 Azure 远程用量失败。常见原因：\n"
                        "1) 服务主体未被授予该资源的读取/监控权限（至少 Reader 或 Monitoring Reader）\n"
                        "2) 环境变量缺少订阅/资源组/资源名\n"
                        "3) 订阅或资源信息不匹配\n"
                        f"错误: {e}"
                    )

        try:
            self.fetch_metrics_button.setEnabled(False)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            w = _MetricsWorker(self)
            w.log.connect(self.log_view.append)

            def _cleanup():
                try:
                    self.fetch_metrics_button.setEnabled(True)
                except Exception:
                    pass
                try:
                    QApplication.restoreOverrideCursor()
                except Exception:
                    pass

            w.finished.connect(_cleanup)
            # 防 GC
            self._metrics_worker = w
            w.start()
        except Exception as e:
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass
            self.fetch_metrics_button.setEnabled(True)
            self.log_view.append(f"⚠ 启动指标获取失败: {e}")

    # ---------- Splitter 尺寸控制 ----------
    def _store_expanded_sizes(self):
        # 初始化选择提示（如果还未调用）
        if hasattr(self, 'selected_voices_label') and hasattr(self, '_update_selected_voices_label'):
            try:
                self._update_selected_voices_label()
            except:
                pass
        
        sizes = self.splitter.sizes()
        if len(sizes) < 5:
            return
        # sizes: [settings, text, voice, log, filler]
        if self.text_box.is_expanded():
            self._panel_saved_sizes['text'] = max(0, sizes[1])
        if self.voice_box.is_expanded():
            self._panel_saved_sizes['voice'] = max(0, sizes[2])
        if self.log_box.is_expanded():
            self._panel_saved_sizes['log'] = max(0, sizes[3])

    def update_splitter_sizes(self):
        splitter = self.splitter
        total_h = max(1, splitter.height())
        header_s = self.settings_box.header_height()
        header_t = self.text_box.header_height()
        header_v = self.voice_box.header_height()
        header_l = self.log_box.header_height()
        MAX_COMPACT = 500  # 增加高度以容纳情绪控制面板

        # 设置面板高度
        if self.settings_box.is_expanded():
            content_h = self.settings_box.content_area.sizeHint().height()
            set_h = min(MAX_COMPACT, content_h + header_s)
            set_h = max(set_h, header_s + 40)
            self._expanded_settings_height = set_h
        else:
            set_h = header_s

        all_collapsed = (not self.settings_box.is_expanded() and
                         not self.text_box.is_expanded() and
                         not self.voice_box.is_expanded() and
                         not self.log_box.is_expanded())
        if all_collapsed:
            filler = max(0, total_h - (header_s + header_t + header_v + header_l))
            splitter.setSizes([header_s, header_t, header_v, header_l, filler])
            for box, h in [(self.settings_box, header_s), (self.text_box, header_t), (self.voice_box, header_v), (self.log_box, header_l)]:
                box.setMinimumHeight(h); box.setMaximumHeight(h)
            self.bottom_filler.setMinimumHeight(0)
            self.bottom_filler.setMaximumHeight(16777215)
            self._store_expanded_sizes()
            return

        remaining = max(0, total_h - set_h)
        MIN_CONTENT = 80
        # 计算文本/语音/日志三个面板的高度
        panels = [
            ("text", self.text_box, header_t),
            ("voice", self.voice_box, header_v),
            ("log", self.log_box, header_l),
        ]
        expanded = [(key, box, header) for (key, box, header) in panels if box.is_expanded()]
        collapsed = [(key, box, header) for (key, box, header) in panels if not box.is_expanded()]

        heights = {"text": header_t, "voice": header_v, "log": header_l}
        if expanded:
            # 使用已保存尺寸作为权重分配剩余高度
            weights = []
            for key, _, _ in expanded:
                w = self._panel_saved_sizes.get(key) or 1
                weights.append(max(1, int(w)))
            total_w = sum(weights) if sum(weights) > 0 else len(expanded)
            # 初步分配
            alloc = []
            for w in weights:
                alloc.append(max(MIN_CONTENT, int(remaining * (w / total_w))))
            # 调整最后一个填满剩余
            rem_used = sum(alloc)
            if rem_used > remaining:
                # 轻微缩放
                scale = remaining / rem_used if rem_used > 0 else 1
                alloc = [max(MIN_CONTENT, int(a * scale)) for a in alloc]
                rem_used = sum(alloc)
            if alloc:
                alloc[-1] = max(MIN_CONTENT, remaining - sum(alloc[:-1]))
            # 写入高度
            for (key, _, _), h in zip(expanded, alloc):
                heights[key] = h

        used = set_h + heights["text"] + heights["voice"] + heights["log"]
        filler = max(0, total_h - used)
        splitter.setSizes([set_h, heights["text"], heights["voice"], heights["log"], filler])

        # 约束高度
        if self.settings_box.is_expanded():
            self.settings_box.setMinimumHeight(set_h)
            self.settings_box.setMaximumHeight(set_h)
        else:
            self.settings_box.setMinimumHeight(header_s)
            self.settings_box.setMaximumHeight(header_s)

        for (box, expanded_state, header, h) in [
            (self.text_box, self.text_box.is_expanded(), header_t, heights["text"]),
            (self.voice_box, self.voice_box.is_expanded(), header_v, heights["voice"]),
            (self.log_box, self.log_box.is_expanded(), header_l, heights["log"]),
        ]:
            if expanded_state:
                box.setMinimumHeight(MIN_CONTENT)
                box.setMaximumHeight(16777215)
            else:
                box.setMinimumHeight(header)
                box.setMaximumHeight(header)

        self.bottom_filler.setMinimumHeight(0)
        self.bottom_filler.setMaximumHeight(16777215)
        self._store_expanded_sizes()

    def _enforce_splitter_constraints(self):
        """防止拖动超出合理范围：
        - 折叠面板固定为 header 高度
        - 展开面板 >= MIN_CONTENT
        """
        sizes = self.splitter.sizes()
        if len(sizes) < 5:
            return
        header_s = self.settings_box.header_height()
        header_t = self.text_box.header_height()
        header_v = self.voice_box.header_height()
        header_l = self.log_box.header_height()
        MIN_CONTENT = 80
        set_h, text_h, voice_h, log_h, filler = sizes
        if not self.settings_box.is_expanded():
            set_h = header_s
        else:
            fixed = getattr(self, '_expanded_settings_height', None)
            if fixed is not None:
                set_h = fixed
            else:
                set_h = max(set_h, header_s + 40)
        if not self.text_box.is_expanded():
            text_h = header_t
        else:
            text_h = max(text_h, MIN_CONTENT)
        if not self.voice_box.is_expanded():
            voice_h = header_v
        else:
            voice_h = max(voice_h, MIN_CONTENT)
        if not self.log_box.is_expanded():
            log_h = header_l
        else:
            log_h = max(log_h, MIN_CONTENT)
        total = sum(sizes)
        used = set_h + text_h + voice_h + log_h
        filler = max(0, total - used)
        if used > total:
            scale = total / used if used > 0 else 1
            set_h = int(set_h * scale)
            text_h = int(text_h * scale)
            voice_h = int(voice_h * scale)
            log_h = int(log_h * scale)
            used = set_h + text_h + voice_h + log_h
            filler = max(0, total - used)
        self.splitter.setSizes([set_h, text_h, voice_h, log_h, filler])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_splitter_sizes()

    def update_option_states(self, *_):
        default_output_enabled = self.default_output_checkbox.isChecked()
        extra_output_enabled = self.extra_line_checkbox.isChecked()

        if not default_output_enabled and self.srt_checkbox.isChecked():
            self.srt_checkbox.blockSignals(True)
            self.srt_checkbox.setChecked(False)
            self.srt_checkbox.blockSignals(False)

        self.srt_checkbox.setEnabled(default_output_enabled)
        srt_active = self.srt_checkbox.isChecked() and default_output_enabled

        # 字幕块行数输入框仅在生成字幕时启用
        self.subtitle_lines_label.setEnabled(srt_active)
        self.subtitle_lines_input.setEnabled(srt_active)

        allow_rule_selection = default_output_enabled or extra_output_enabled
        self.subtitle_rule_combo.setEnabled(allow_rule_selection)

        rule_supports_line_length = (
            self.subtitle_rule_combo.currentData() == SubtitleGenerator.RULE_SMART or
            self.subtitle_rule_combo.currentData() == SubtitleGenerator.RULE_HANLP
        )
        allow_line_length = rule_supports_line_length and (srt_active or extra_output_enabled)
        self.line_length_label.setEnabled(allow_line_length)
        self.line_length_input.setEnabled(allow_line_length)

    def populate_voices(self):
        try:
            # 尽量保留用户当前勾选
            previous_selected: list[str] = []
            try:
                previous_selected = self.get_selected_voices() if hasattr(self, 'get_selected_voices') else []
            except Exception:
                previous_selected = []

            self.voice_tree.blockSignals(True)
            self.voice_tree.clear()
            self.voice_items.clear()

            # 语言代码到中文名称的映射
            language_names = {
                "ar": "阿拉伯语",
                "bg": "保加利亚语",
                "ca": "加泰罗尼亚语",
                "cs": "捷克语",
                "cy": "威尔士语",
                "da": "丹麦语",
                "de": "德语",
                "el": "希腊语",
                "en": "英语",
                "es": "西班牙语",
                "et": "爱沙尼亚语",
                "fi": "芬兰语",
                "fr": "法语",
                "ga": "爱尔兰语",
                "he": "希伯来语",
                "hi": "印地语",
                "hr": "克罗地亚语",
                "hu": "匈牙利语",
                "id": "印度尼西亚语",
                "is": "冰岛语",
                "it": "意大利语",
                "ja": "日语",
                "ko": "韩语",
                "lt": "立陶宛语",
                "lv": "拉脱维亚语",
                "ms": "马来语",
                "mt": "马耳他语",
                "nb": "挪威语",
                "nl": "荷兰语",
                "pl": "波兰语",
                "pt": "葡萄牙语",
                "ro": "罗马尼亚语",
                "ru": "俄语",
                "sk": "斯洛伐克语",
                "sl": "斯洛文尼亚语",
                "sv": "瑞典语",
                "ta": "泰米尔语",
                "te": "泰卢固语",
                "th": "泰语",
                "tr": "土耳其语",
                "uk": "乌克兰语",
                "ur": "乌尔都语",
                "vi": "越南语",
                "zh": "中文",
            }

            # 按州划分的语言
            regions = {
                "亚洲": ["zh", "ja", "ko", "vi", "th", "ms", "id", "hi", "ta", "te", "ur"],
                "欧洲": ["en", "fr", "de", "it", "es", "pt", "ru", "pl", "nl", "sv", "no", "da", "fi", 
                       "el", "cs", "hu", "ro", "bg", "hr", "sk", "sl", "lt", "lv", "et", "is", "ga", 
                       "cy", "mt", "uk"],
                "中东": ["ar", "he"],
                "美洲": ["en-US", "es-MX", "pt-BR", "fr-CA"],
                "大洋洲": ["en-AU", "en-NZ"],
                "非洲": ["af", "sw"]
            }

            # 直接用 VoicesManager 获取结构化列表，避免解析 CLI 表格导致丢失
            mode = "azure"
            try:
                if hasattr(self, 'mode_combo'):
                    mode = str(self.mode_combo.currentData() or 'azure')
            except Exception:
                mode = "azure"

            def _get_azure_endpoint_and_keys() -> tuple[str, list[str]]:
                endpoint = str(getattr(self, "azure_tts_endpoint", "") or "")
                region = str(getattr(self, "azure_speech_region", "") or "")
                keys: list[str] = []

                raw_keys = getattr(self, "azure_speech_keys", None)
                if isinstance(raw_keys, list):
                    keys = [str(k) for k in raw_keys if str(k).strip()]

                env_endpoint = _get_env_var("AZURE_TTS_ENDPOINT") or _get_env_var("AZURE_SPEECH_ENDPOINT")
                if env_endpoint:
                    endpoint = env_endpoint

                env_region = (
                    _get_env_var("AZURE_SPEECH_REGION")
                    or _get_env_var("AZURE_TTS_REGION")
                    or _get_env_var("AZURE_REGION")
                )
                if env_region:
                    region = env_region

                env_keys = _get_env_var("AZURE_SPEECH_KEYS") or _get_env_var("AZURE_TTS_KEYS")
                if env_keys:
                    keys = [k.strip() for k in env_keys.split(",") if k.strip()]
                else:
                    key1 = _get_env_var("AZURE_SPEECH_KEY") or _get_env_var("AZURE_TTS_KEY")
                    key2 = _get_env_var("AZURE_SPEECH_KEY2") or _get_env_var("AZURE_TTS_KEY2")
                    if key1:
                        keys = [key1.strip()]
                        if key2 and key2.strip() and key2.strip() != key1.strip():
                            keys.append(key2.strip())

                if not endpoint and not region:
                    endpoint = _DEFAULT_AZURE_ENDPOINT_BASE
                endpoint = _normalize_azure_speech_endpoint(endpoint_or_base=endpoint, region=region)
                return endpoint, keys

            def _load_azure_voices_sync() -> list[dict]:
                endpoint, keys = _get_azure_endpoint_and_keys()
                if not endpoint:
                    raise RuntimeError("Azure 模式缺少 Endpoint/Region。请设置 AZURE_SPEECH_REGION 或 AZURE_TTS_ENDPOINT。")
                if not keys:
                    raise RuntimeError("Azure 模式缺少 Key。请设置 AZURE_SPEECH_KEYS 或 AZURE_SPEECH_KEY。")
                url = _azure_voices_list_url_from_tts_endpoint(endpoint)
                last_error: Exception | None = None
                for idx, key in enumerate(keys):
                    try:
                        req = urllib.request.Request(
                            url,
                            method="GET",
                            headers={
                                "Ocp-Apim-Subscription-Key": key,
                                "User-Agent": "tts/1.pyw",
                            },
                        )
                        with urllib.request.urlopen(req, timeout=30) as resp:
                            raw = resp.read().decode("utf-8", errors="ignore")
                        data = json.loads(raw)
                        if not isinstance(data, list):
                            raise RuntimeError("Azure voices/list 返回格式异常（不是列表）。")
                        return data
                    except urllib.error.HTTPError as e:
                        code = getattr(e, "code", None)
                        if code in (401, 403) and idx < (len(keys) - 1):
                            last_error = e
                            continue
                        try:
                            body = e.read().decode("utf-8", errors="ignore")
                        except Exception:
                            body = ""
                        raise RuntimeError(f"Azure voices/list 失败（HTTP {code}）：{body.strip() or e}")
                    except Exception as e:
                        last_error = e
                        if idx < (len(keys) - 1):
                            continue
                        raise
                if last_error is not None:
                    raise last_error
                raise RuntimeError("Azure voices/list 获取失败（未知原因）。")

            voices: list[dict] = []
            if mode == "azure":
                try:
                    voices = _load_azure_voices_sync()
                except Exception as e:
                    # Azure 拉取失败时，回退 Edge 列表，避免界面空
                    self.log_view.append(f"⚠ Azure 语音列表获取失败，已回退 Edge 列表：{e}")
                    mode = "edge"

            if mode != "azure":
                async def _load_edge_voices():
                    manager = await edge_tts.VoicesManager.create()
                    return manager.voices or []

                try:
                    voices = asyncio.run(_load_edge_voices())
                except RuntimeError:
                    # 兼容已有事件循环环境
                    loop = asyncio.new_event_loop()
                    try:
                        voices = loop.run_until_complete(_load_edge_voices())
                    finally:
                        try:
                            loop.close()
                        except Exception:
                            pass

            # 兜底：若获取为空，提示并回退到 CLI（尽量保持可用）
            if not voices:
                raise RuntimeError("语音列表为空（可能网络/区域/被拦截/Key 配置错误）。")

            voices_by_region_lang: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
            for v in voices:
                short_name = str(v.get('ShortName') or v.get('Name') or '').strip()
                locale = str(v.get('Locale') or '').strip()
                if not short_name or not locale:
                    continue

                lang_prefix = locale.split('-')[0].lower()

                # 确定语言所属的区域
                region = "其他"
                for r, langs in regions.items():
                    if lang_prefix in langs or locale in langs:
                        region = r
                        break

                # 获取语言中文名称
                lang_display = locale
                if lang_prefix in language_names:
                    chinese_name = language_names[lang_prefix]
                    lang_display = f"{locale} ({chinese_name})"

                voices_by_region_lang[region][lang_display].append(v)

            # 按区域和语言创建树形结构
            for region, lang_map in sorted(voices_by_region_lang.items()):
                region_item = QTreeWidgetItem(self.voice_tree, [region])
                region_item.setFlags(region_item.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
                region_item.setCheckState(0, Qt.Unchecked)

                for lang_display, voice_rows in sorted(lang_map.items()):
                    lang_item = QTreeWidgetItem(region_item, [lang_display])
                    lang_item.setFlags(lang_item.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
                    lang_item.setCheckState(0, Qt.Unchecked)

                    def _voice_sort_key(v):
                        return str(v.get('ShortName') or '')

                    for v in sorted(voice_rows, key=_voice_sort_key):
                        short_name = str(v.get('ShortName') or '')
                        gender = str(v.get('Gender') or '')
                        locale = str(v.get('Locale') or '')
                        status = str(v.get('Status') or '')
                        # 个性：尽量从 VoiceTag 提取，取不到就显示状态
                        voice_tag = v.get('VoiceTag') or {}
                        personalities = voice_tag.get('VoicePersonalities') or []
                        # Azure voices/list 常见字段：StyleList / VoiceType；Edge voices: VoiceTag/Status
                        style_list = v.get('StyleList') or []
                        if isinstance(style_list, list) and style_list:
                            personalities_text = ",".join(map(str, style_list[:3]))
                        else:
                            personalities_text = ",".join(map(str, personalities[:3])) if personalities else (status or str(v.get('VoiceType') or ''))

                        child = QTreeWidgetItem(lang_item, [short_name, gender, locale, personalities_text])
                        child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                        child.setCheckState(0, Qt.Unchecked)
                        self.voice_items[short_name] = child

            # 恢复之前勾选（仅恢复仍存在的）
            if previous_selected:
                self.apply_saved_voice_selection(previous_selected)

            # 统计中文语音数量，便于用户确认“是否全”
            try:
                zh_count = 0
                for v in voices:
                    locale = str(v.get('Locale') or '')
                    if locale.lower().startswith('zh-') or locale.lower() == 'zh-cn' or locale.lower() == 'zh':
                        zh_count += 1
                self.log_view.append(f"✓ 已加载语音：{len(self.voice_items)} 个（中文相关 {zh_count} 个），模式={mode}")
            except Exception:
                pass

            # 默认展开中文区域项目
            for i in range(self.voice_tree.topLevelItemCount()):
                item = self.voice_tree.topLevelItem(i)
                if item.text(0) == "亚洲":
                    item.setExpanded(True)
                    # 展开亚洲区域内的中文语言
                    for j in range(item.childCount()):
                        lang_item = item.child(j)
                        if 'zh' in lang_item.text(0).lower():
                            lang_item.setExpanded(True)

        except Exception as e:
            log_view = getattr(self, "log_view", None)
            msg = f"获取语音模型列表失败: {e}"
            if log_view is not None:
                log_view.append(msg)
            else:
                print(msg)
            # 提供备用选项
            fallback_region = QTreeWidgetItem(self.voice_tree, ["亚洲"])
            fallback_region.setFlags(fallback_region.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
            fallback_region.setCheckState(0, Qt.Unchecked)
            
            fallback_lang = QTreeWidgetItem(fallback_region, ["zh-CN (中文)"])
            fallback_lang.setFlags(fallback_lang.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
            fallback_lang.setCheckState(0, Qt.Unchecked)
            
            for voice in ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-YunjianNeural"]:
                child = QTreeWidgetItem(fallback_lang, [voice, "", "", ""])
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)
                self.voice_items[voice] = child

        finally:
            try:
                self.voice_tree.blockSignals(False)
            except Exception:
                pass

    def get_selected_voices(self):
        selected = []
        root = self.voice_tree.invisibleRootItem()
        for i in range(root.childCount()):
            region_item = root.child(i)
            for j in range(region_item.childCount()):
                lang_item = region_item.child(j)
                for k in range(lang_item.childCount()):
                    voice_item = lang_item.child(k)
                    if voice_item.checkState(0) == Qt.Checked:
                        selected.append(voice_item.text(0))
            # 兼容回退节点
            if region_item.childCount() == 0 and region_item.checkState(0) == Qt.Checked:
                selected.append(region_item.text(0))
        return selected

    def get_settings_path(self) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_settings.json")

    def load_settings(self) -> None:
        path = self.get_settings_path()
        if not os.path.exists(path):
            self.update_option_states()
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            self.log_view.append("⚠ 设置文件损坏，已忽略。")
            self.update_option_states()
            return

        self._loading_settings = True
        try:
            # 读取 Azure 配置（不做 UI 展示；用于 Azure 模式合成）
            self.azure_speech_region = str(data.get("azure_speech_region", "") or "")
            self.azure_tts_endpoint = str(data.get("azure_tts_endpoint", "") or "") or _DEFAULT_AZURE_ENDPOINT_BASE
            raw_keys = data.get("azure_speech_keys")
            if isinstance(raw_keys, str):
                self.azure_speech_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
            elif isinstance(raw_keys, list):
                self.azure_speech_keys = [str(k).strip() for k in raw_keys if str(k).strip()]
            else:
                self.azure_speech_keys = []

            # 恢复模式选择（默认 Azure）
            mode_value = str(data.get("tts_mode", "azure") or "azure")
            mode_index = self.mode_combo.findData(mode_value)
            if mode_index != -1:
                self.mode_combo.setCurrentIndex(mode_index)


            # 按当前模式重新拉取语音列表（Azure 模式可避免中文语音变少）
            try:
                self.populate_voices()
            except Exception:
                pass

            self.default_output_checkbox.setChecked(data.get("default_output", True))
            self.srt_checkbox.setChecked(data.get("srt_enabled", True))
            self.extra_line_checkbox.setChecked(data.get("extra_line_output", False))

            line_length = int(data.get("line_length", 28))
            self.line_length_input.setText(str(max(5, min(120, line_length))))

            # 恢复字幕块行数
            subtitle_lines = int(data.get("subtitle_lines", 1))
            self.subtitle_lines_input.setText(str(max(1, min(10, subtitle_lines))))

            rule_value = data.get("subtitle_rule", SubtitleGenerator.RULE_NEWLINE)
            index = self.subtitle_rule_combo.findData(rule_value)
            if index != -1:
                self.subtitle_rule_combo.setCurrentIndex(index)

            selected_voices = data.get("selected_voices", [])
            self.apply_saved_voice_selection(selected_voices)

            # 提示：若接口返回的语音列表变少，旧设置里部分模型会找不到
            try:
                missing = [v for v in selected_voices if v not in self.voice_items]
                if missing:
                    preview = ", ".join(missing[:6])
                    more = "" if len(missing) <= 6 else f" 等{len(missing)}个"
                    self.log_view.append(
                        f"⚠ 已保存语音模型中有 {len(missing)} 个当前未加载到（可能网络/区域/拦截导致列表变少）：{preview}{more}"
                    )
            except Exception:
                pass
            
            # 恢复语音参数
            self.rate_combo.setCurrentText(data.get("voice_rate", "+0%"))
            self.pitch_combo.setCurrentText(data.get("voice_pitch", "+0Hz"))
            self.volume_combo.setCurrentText(data.get("voice_volume", "+0%"))
            
            # 恢复情绪控制参数
            self.enable_emotion_checkbox.setChecked(data.get("enable_emotion", False))
            
            style_value = data.get("voice_style", "general")
            style_index = self.style_combo.findData(style_value)
            if style_index != -1:
                self.style_combo.setCurrentIndex(style_index)
            
            styledegree_value = float(data.get("voice_styledegree", "1.0"))
            self.styledegree_slider.setValue(int(styledegree_value * 100))
            
            role_value = data.get("voice_role", "")
            role_index = self.role_combo.findData(role_value)
            if role_index != -1:
                self.role_combo.setCurrentIndex(role_index)
            
            # 恢复窗口大小与位置
            geo = data.get("window_geometry")
            if isinstance(geo, list) and len(geo) == 4:
                try:
                    x, y, w, h = geo
                    if w > 200 and h > 300:
                        self.setGeometry(int(x), int(y), int(w), int(h))
                        self._settings_geometry_loaded = True
                except Exception:
                    pass
            # 折叠面板状态（兼容旧版无字段情况）
            panel_states = data.get("panel_states") or {}
            if isinstance(panel_states, dict):
                if "settings" in panel_states:
                    self.settings_box.set_expanded(bool(panel_states.get("settings", True)))
                if "text" in panel_states and hasattr(self, 'text_box'):
                    self.text_box.set_expanded(bool(panel_states.get("text", True)))
                if "voice" in panel_states:
                    self.voice_box.set_expanded(bool(panel_states.get("voice", True)))
                if "log" in panel_states:
                    self.log_box.set_expanded(bool(panel_states.get("log", True)))
                # 延迟一次尺寸更新
                from PySide6.QtCore import QTimer as _QT
                _QT.singleShot(0, self.update_splitter_sizes)
        finally:
            self._loading_settings = False
            self.update_option_states()

    def save_settings(self) -> None:
        if getattr(self, "_loading_settings", False):
            return

        # 先读取已有设置，避免覆盖用户手动添加的字段（例如 Azure Key/Endpoint）
        existing: dict = {}
        path = self.get_settings_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    existing = loaded
            except Exception:
                existing = {}

        try:
            line_length = int(self.line_length_input.text())
        except (TypeError, ValueError):
            line_length = 28

        try:
            subtitle_lines = int(self.subtitle_lines_input.text())
        except (TypeError, ValueError):
            subtitle_lines = 1

        settings = dict(existing)
        settings.update({
            "default_output": self.default_output_checkbox.isChecked(),
            "srt_enabled": self.srt_checkbox.isChecked(),
            "extra_line_output": self.extra_line_checkbox.isChecked(),
            "line_length": max(5, min(120, line_length)),
            "subtitle_lines": max(1, min(10, subtitle_lines)),
            "subtitle_rule": self.subtitle_rule_combo.currentData(),
            "selected_voices": self.get_selected_voices(),
            "tts_mode": self.mode_combo.currentData() or "azure",
            "voice_rate": self.rate_combo.currentText(),
            "voice_pitch": self.pitch_combo.currentText(),
            "voice_volume": self.volume_combo.currentText(),
            "enable_emotion": self.enable_emotion_checkbox.isChecked(),
            "voice_style": self.style_combo.currentData() or "general",
            "voice_styledegree": str(self.styledegree_slider.value() / 100.0),
            "voice_role": self.role_combo.currentData() or "",
            "panel_states": {
                "settings": self.settings_box.is_expanded(),
                "text": self.text_box.is_expanded(),
                "voice": self.voice_box.is_expanded(),
                "log": self.log_box.is_expanded(),
            },
            "window_geometry": [self.x(), self.y(), self.width(), self.height()],
        })

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            self.log_view.append(f"⚠ 保存设置失败: {exc}")

    def _on_mode_changed(self, *args):
        # 切换模式后立即保存，保持下次启动一致
        self.save_settings()
        # 切换模式后刷新语音列表，避免“显示不全/选了用不了”
        try:
            self.populate_voices()
        except Exception as e:
            try:
                self.log_view.append(f"⚠ 切换模式后刷新语音列表失败: {e}")
            except Exception:
                pass

    def apply_saved_voice_selection(self, voices: list[str]) -> None:
        # 先全部清空（结构：region -> locale -> voice）
        root = self.voice_tree.invisibleRootItem()
        for i in range(root.childCount()):
            region_item = root.child(i)
            region_item.setCheckState(0, Qt.Unchecked)
            for j in range(region_item.childCount()):
                lang_item = region_item.child(j)
                lang_item.setCheckState(0, Qt.Unchecked)
                for k in range(lang_item.childCount()):
                    voice_item = lang_item.child(k)
                    voice_item.setCheckState(0, Qt.Unchecked)

        for voice in voices:
            item = self.voice_items.get(voice)
            if item is not None:
                item.setCheckState(0, Qt.Checked)

    def closeEvent(self, event):
        # 保存窗口几何信息
        self.save_settings()
        super().closeEvent(event)

    def start_tts(self):
        selected_voices = self.get_selected_voices()
        if not selected_voices:
            self.log_view.append("错误：请至少选择一个语音模型。")
            return
        selected_texts = self.get_selected_texts() if hasattr(self, 'get_selected_texts') else []
        if not selected_texts:
            self.log_view.append("错误：请至少勾选一个文本文件。")
            return

        default_output_enabled = self.default_output_checkbox.isChecked()
        extra_line_output = self.extra_line_checkbox.isChecked()
        if not default_output_enabled and not extra_line_output:
            self.log_view.append("错误：请至少选择一种输出方式（整段音频或按行输出）。")
            return

        srt_enabled = self.srt_checkbox.isChecked() and default_output_enabled
        line_length_text = self.line_length_input.text().strip()
        try:
            line_length_value = int(line_length_text)
        except ValueError:
            line_length_value = 28

        line_length_value = max(5, min(120, line_length_value))
        if str(line_length_value) != line_length_text:
            self.line_length_input.setText(str(line_length_value))

        # 获取字幕块行数
        subtitle_lines_text = self.subtitle_lines_input.text().strip()
        try:
            subtitle_lines_value = int(subtitle_lines_text)
        except ValueError:
            subtitle_lines_value = 1
        
        subtitle_lines_value = max(1, min(10, subtitle_lines_value))
        if str(subtitle_lines_value) != subtitle_lines_text:
            self.subtitle_lines_input.setText(str(subtitle_lines_value))

        convert_punctuation = False  # 标点转换现在通过独立的标点转换功能处理
        subtitle_rule = self.subtitle_rule_combo.currentData() or SubtitleGenerator.RULE_SMART

        self.start_button.setEnabled(False)
        # 根据需求：不显示开始执行的提示，仅在完成/错误时输出内容。
        
        self.workers.clear()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_root = os.path.join(script_dir, "output")
        os.makedirs(output_root, exist_ok=True)
        for voice in selected_voices:
            worker = TTSWorker(
                voice=voice,
                parent=self,
                tts_mode=str(self.mode_combo.currentData() or "azure"),
                srt_enabled=srt_enabled,
                line_length=line_length_value,
                convert_punctuation=convert_punctuation,
                subtitle_rule=subtitle_rule,
                output_root=output_root,
                extra_line_output=extra_line_output,
                default_output=default_output_enabled,
                rate=self.rate_combo.currentText(),
                pitch=self.pitch_combo.currentText(),
                volume=self.volume_combo.currentText(),
                enable_emotion=self.enable_emotion_checkbox.isChecked(),
                style=self.style_combo.currentData() or "general",
                styledegree=str(self.styledegree_slider.value() / 100.0),
                role=self.role_combo.currentData() or "",
                subtitle_lines=subtitle_lines_value,
                selected_txt_files=selected_texts,
            )
            worker.progress.connect(self._append_filtered_log)
            worker.finished.connect(self.on_worker_finished)
            self.workers[voice] = worker
            worker.start()

    def on_worker_finished(self, voice):
        self.log_view.append(f"✓ 线程 {voice} 已完成。")
        if voice in self.workers:
            del self.workers[voice]
        
        if not self.workers:
            self.log_view.append("\n✓ 所有任务均已完成！")
            self.start_button.setEnabled(True)

    def execute_punctuation_conversion(self):
        conversion_type = self.punctuation_combo.currentData()
        
        if conversion_type == "none":
            return
        
        # 获取被勾选的 txt 文件（若无面板则退化为全量），路径改为 ./txt
        dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "txt")
        os.makedirs(dir_path, exist_ok=True)
        if hasattr(self, 'get_selected_texts'):
            txt_files = [f for f in self.get_selected_texts() if f.lower().endswith('.txt')]
        else:
            txt_files = [f for f in os.listdir(dir_path) if f.lower().endswith('.txt')]
        
        if not txt_files:
            self.log_view.append("txt 子目录内未找到任何 .txt 文件")
            return
        
        converted_count = 0
        
        for txt_file in txt_files:
            file_path = os.path.join(dir_path, txt_file)
            try:
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 执行转换
                if conversion_type == "to_halfwidth":
                    converted_content = SubtitleGenerator.to_halfwidth_punctuation(content)
                    self.log_view.append(f"✓ 中文标点 → 英文标点: {txt_file}")
                elif conversion_type == "to_fullwidth":
                    converted_content = SubtitleGenerator.to_fullwidth_punctuation(content)
                    self.log_view.append(f"✓ 英文标点 → 中文标点: {txt_file}")
                elif conversion_type == "remove_punctuation":
                    converted_content = SubtitleGenerator.remove_punctuation(content)
                    self.log_view.append(f"✓ 删除标点符号: {txt_file}")
                else:
                    continue
                
                # 写回文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(converted_content)
                
                converted_count += 1
                
            except Exception as e:
                self.log_view.append(f"✗ 处理文件失败 {txt_file}: {e}")
        
        self.log_view.append(f"✓ 标点转换完成，共处理 {converted_count} 个文件")

    # ---------- 语音模型选择提示更新 ----------
    def _update_selected_voices_label(self, *args):
        """更新已选择语音模型的提示标签"""
        selected = self.get_selected_voices()
        count = len(selected)
        
        if count == 0:
            self.selected_voices_label.setText("已选择: 0 个模型")
            self.selected_voices_label.setStyleSheet("QLabel { font-weight: bold; padding: 3px; }")
        elif count <= 3:
            # 显示所有选中的模型名称
            voices_text = ", ".join(selected)
            self.selected_voices_label.setText(f"已选择 {count} 个模型: {voices_text}")
            self.selected_voices_label.setStyleSheet("QLabel { font-weight: bold; padding: 3px; }")
        else:
            # 只显示前3个，其余用省略号
            voices_preview = ", ".join(selected[:3])
            self.selected_voices_label.setText(f"已选择 {count} 个模型: {voices_preview}... 等")
            self.selected_voices_label.setStyleSheet("QLabel { font-weight: bold; padding: 3px; }")

    # ---------- 情绪控制辅助方法 ----------
    def _toggle_emotion_controls(self, state):
        """切换情绪控制UI的启用/禁用状态"""
        # state 来自 stateChanged 信号，是整数: 0=未选中, 2=选中
        enabled = (state == 2) if isinstance(state, int) else bool(state)
        
        print(f"[调试] 情绪控制开关状态变更: state={state}, enabled={enabled}")
        
        for widget in self.emotion_widgets:
            widget.setEnabled(enabled)
            print(f"[调试] 设置控件 {widget.__class__.__name__} 为 {'启用' if enabled else '禁用'}")
    
    def _on_styledegree_changed(self, value):
        """更新情绪强度标签"""
        degree = value / 100.0
        self.styledegree_label.setText(f"强度: {degree:.2f}")

    # ---------- 日志过滤输出 ----------
    def _append_filtered_log(self, text: str):
        """只输出完成/结果类日志，过滤掉开始、进行中提示。"""
        if not isinstance(text, str):
            return
        stripped = text.strip()
        if not stripped:
            return
        # 过滤关键词集合（开始/进行中）
        exclude_keywords = ["开始", "正在", "→", "↻"]
        if any(k in stripped for k in exclude_keywords):
            return
        # 允许的正向特征（完成/结果/错误/警告/勾/叉等）
        include_markers = ["✓", "⚠", "✗", "失败", "完成", "已保存", "任务处理完毕", "错误", "出错", "异常", "已生成", "已输出"]
        if any(m in stripped for m in include_markers):
            self.log_view.append(stripped)
        # 其余普通行默认丢弃，保持日志简洁

    # ---------- txt 目录迁移助手 ----------
    def _ensure_text_dir_and_migrate(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        text_dir = os.path.join(script_dir, "txt")
        os.makedirs(text_dir, exist_ok=True)
        for name in os.listdir(script_dir):
            if name.lower().endswith('.txt'):
                src = os.path.join(script_dir, name)
                dst = os.path.join(text_dir, name)
                if os.path.abspath(src) == os.path.abspath(dst):
                    continue
                if not os.path.exists(dst):
                    try:
                        os.rename(src, dst)
                    except Exception:
                        pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置为 Python 可执行文件的图标（pythonw.exe）
    try:
        import sys
        python_exe = sys.executable  # pythonw.exe 路径
        if os.path.exists(python_exe):
            icon = QIcon(python_exe)
            if not icon.isNull():
                app.setWindowIcon(icon)
    except Exception:
        pass
    
    window = TTSApp()
    window.show()
    sys.exit(app.exec())
