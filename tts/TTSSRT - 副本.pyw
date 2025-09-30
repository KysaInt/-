import asyncio
import json
import os
import sys
import subprocess
import importlib
import re
from datetime import datetime
from collections import defaultdict

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView, QLineEdit, QCheckBox,
    QComboBox, QSplitter, QSizePolicy
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QIntValidator


# 自动检查并安装 edge-tts，并处理同名脚本导致的导入冲突
def ensure_edge_tts():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 移除当前脚本所在目录，避免导入冲突
    if script_dir in sys.path:
        sys.path.remove(script_dir)
    try:
        return importlib.import_module("edge_tts")
    except ImportError:
        print("未检测到 edge-tts，正在自动安装……")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "edge-tts", "PySide6"])
        return importlib.import_module("edge_tts")
    finally:
        # 恢复 sys.path
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)

edge_tts = ensure_edge_tts()

_mutagen_mp3_module = None


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
    ) -> str:
        lines = cls._prepare_lines(text, rule, line_length)
        if not lines:
            return ""

        if convert_punctuation:
            lines = [cls.to_halfwidth_punctuation(line) for line in lines]

        cues = [lines[i:i + 2] for i in range(0, len(lines), 2)]
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
        srt_enabled: bool = False,
        line_length: int = 28,
        convert_punctuation: bool = False,
        subtitle_rule: str = SubtitleGenerator.RULE_SMART,
        output_root: str | None = None,
        extra_line_output: bool = False,
        default_output: bool = True,
    ):
        super().__init__(parent)
        self.voice = voice
        self.output_ext = ".mp3"
        self.srt_enabled = srt_enabled
        self.line_length = max(5, int(line_length or 0))
        self.convert_punctuation = convert_punctuation
        self.subtitle_rule = subtitle_rule
        self.extra_line_output = extra_line_output
        self.default_output = default_output
        self.output_root = output_root or os.path.dirname(os.path.abspath(__file__))
        os.makedirs(self.output_root, exist_ok=True)

    async def tts_async(self, text, voice, output):
        try:
            from edge_tts import async_api
            communicate = async_api.Communicate(text, voice)
            self.progress.emit(f"    → [{self.voice}] 正在调用微软语音服务...")
            await communicate.save(output)
        except Exception:
            communicate = edge_tts.Communicate(text, voice)
            self.progress.emit(f"    → [{self.voice}] 检测到旧版 API，已切换兼容模式。")
            await communicate.save(output)
        self.progress.emit(f"    ✓ [{self.voice}] 语音已保存到 {os.path.basename(output)}")

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
        dir_path = os.path.dirname(os.path.abspath(__file__))
        files = [f for f in os.listdir(dir_path) if f.lower().endswith('.txt')]
        if not files:
            self.progress.emit(f"[{self.voice}] 未找到任何 .txt 文件！")
            return

        self.progress.emit(f"[{self.voice}] 开始处理任务...")
        for txt_file in files:
            txt_path = os.path.join(dir_path, txt_file)
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    text = f.read().strip()
                if not text:
                    self.progress.emit(f"[{self.voice}] {txt_file} 为空，跳过。")
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
                self.progress.emit(f"处理 {txt_file} 时出错: {e}")
        
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
        self._default_geometry = (160, 160, 560, 640)
        self.setGeometry(*self._default_geometry)
        self._settings_geometry_loaded = False

        # 根布局
        self.root_layout = QVBoxLayout(self)

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

        # 标点转换控件
        self.punctuation_layout = QHBoxLayout()
        self.punctuation_label = QLabel("标点转换:")
        self.punctuation_combo = QComboBox()
        self.punctuation_combo.addItem("不转换", "none")
        self.punctuation_combo.addItem("中文标点 → 英文标点", "to_halfwidth")
        self.punctuation_combo.addItem("英文标点 → 中文标点", "to_fullwidth")
        self.punctuation_combo.setToolTip("选择后立即对同目录下所有 txt 文件执行转换")
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
        self.options_layout.addWidget(self.default_output_checkbox)
        self.options_layout.addWidget(self.extra_line_checkbox)
        self.options_layout.addWidget(self.srt_checkbox)
        self.options_layout.addWidget(self.rule_label)
        self.options_layout.addWidget(self.subtitle_rule_combo)
        self.options_layout.addWidget(self.line_length_label)
        self.options_layout.addWidget(self.line_length_input)
        self.options_layout.addStretch()

        # 开始按钮
        self.start_button = QPushButton("开始转换")
        self.start_button.clicked.connect(self.start_tts)

        # 日志视图
        self.log_view = QTextEdit(); self.log_view.setReadOnly(True)

        # ========== 折叠面板结构 ==========
        self.splitter = QSplitter(Qt.Vertical)
        self.root_layout.addWidget(self.splitter)

        # 设置面板（顶部）
        self.settings_box = CollapsibleBox("设置", expanded=True)
        settings_inner = QVBoxLayout(); settings_inner.setContentsMargins(8,8,8,8); settings_inner.setSpacing(6)
        settings_inner.addLayout(self.punctuation_layout)
        settings_inner.addLayout(self.options_layout)
        settings_inner.addWidget(self.start_button, 0, Qt.AlignLeft)
        self.settings_box.setContentLayout(settings_inner)
        self.splitter.addWidget(self.settings_box)

        # 语音模型面板
        self.voice_box = CollapsibleBox("语音模型", expanded=True)
        voice_inner = QVBoxLayout(); voice_inner.setContentsMargins(8,8,8,8); voice_inner.setSpacing(6)
        voice_inner.addWidget(self.label_voice)
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
        self._panel_saved_sizes = {"voice": None, "log": None}
        for b in (self.settings_box, self.voice_box, self.log_box):
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
        self.log_view.append("1. 将需要转换的文本放在本目录的 .txt 文件中")
        self.log_view.append("2. 在下方树状列表中勾选一个或多个语音模型")
        self.log_view.append("3. 点击“开始转换”按钮启动")
        self.log_view.append("4. 可选：勾选“同步生成 SRT 字幕文件”并调整参数")
        self.log_view.append("")

    # ---------- Splitter 尺寸控制 ----------
    def _store_expanded_sizes(self):
        sizes = self.splitter.sizes()
        if len(sizes) < 4:
            return
        # sizes: [settings, voice, log, filler]
        if self.voice_box.is_expanded():
            self._panel_saved_sizes['voice'] = max(0, sizes[1])
        if self.log_box.is_expanded():
            self._panel_saved_sizes['log'] = max(0, sizes[2])

    def update_splitter_sizes(self):
        splitter = self.splitter
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
            self._expanded_settings_height = set_h
        else:
            set_h = header_s

        all_collapsed = (not self.settings_box.is_expanded() and
                         not self.voice_box.is_expanded() and
                         not self.log_box.is_expanded())
        if all_collapsed:
            filler = max(0, total_h - (header_s + header_v + header_l))
            splitter.setSizes([header_s, header_v, header_l, filler])
            for box, h in [(self.settings_box, header_s), (self.voice_box, header_v), (self.log_box, header_l)]:
                box.setMinimumHeight(h); box.setMaximumHeight(h)
            self.bottom_filler.setMinimumHeight(0)
            self.bottom_filler.setMaximumHeight(16777215)
            self._store_expanded_sizes()
            return

        remaining = max(0, total_h - set_h)
        voice_exp = self.voice_box.is_expanded()
        log_exp = self.log_box.is_expanded()
        MIN_CONTENT = 80
        voice_h = header_v
        log_h = header_l
        if voice_exp and log_exp:
            sv = self._panel_saved_sizes.get('voice') or 1
            sl = self._panel_saved_sizes.get('log') or 1
            tot = sv + sl
            if tot <= 0: tot = 2; sv = sl = 1
            voice_h = max(MIN_CONTENT, int(remaining * (sv / tot)))
            log_h = max(MIN_CONTENT, remaining - voice_h)
        elif voice_exp and not log_exp:
            log_h = header_l
            voice_h = max(MIN_CONTENT, remaining - log_h)
        elif log_exp and not voice_exp:
            voice_h = header_v
            log_h = max(MIN_CONTENT, remaining - voice_h)

        used = set_h + voice_h + log_h
        filler = max(0, total_h - used)
        splitter.setSizes([set_h, voice_h, log_h, filler])

        # 约束高度
        if self.settings_box.is_expanded():
            self.settings_box.setMinimumHeight(set_h)
            self.settings_box.setMaximumHeight(set_h)
        else:
            self.settings_box.setMinimumHeight(header_s)
            self.settings_box.setMaximumHeight(header_s)

        for box, expanded, header, h in [
            (self.voice_box, voice_exp, header_v, voice_h),
            (self.log_box, log_exp, header_l, log_h)
        ]:
            if expanded:
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
        if len(sizes) < 4:
            return
        header_s = self.settings_box.header_height()
        header_v = self.voice_box.header_height()
        header_l = self.log_box.header_height()
        MIN_CONTENT = 80
        set_h, voice_h, log_h, filler = sizes
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
        total = sum(sizes)
        used = set_h + voice_h + log_h
        filler = max(0, total - used)
        if used > total:
            scale = total / used if used > 0 else 1
            set_h = int(set_h * scale)
            voice_h = int(voice_h * scale)
            log_h = int(log_h * scale)
            used = set_h + voice_h + log_h
            filler = max(0, total - used)
        self.splitter.setSizes([set_h, voice_h, log_h, filler])

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

            # 使用 utf-8 编码获取语音列表
            result = subprocess.run(
                [sys.executable, "-m", "edge_tts", "--list-voices"],
                capture_output=True, text=True, encoding='utf-8', errors='ignore'
            )
            lines = result.stdout.strip().split('\n')

            voices_by_region_lang = defaultdict(lambda: defaultdict(list))
            # 从第三行开始解析，跳过标题和分隔线
            for line in lines[2:]:
                raw_parts = line.split(maxsplit=4)
                if len(raw_parts) < 2:
                    continue
                # Ensure we have at least 4 columns
                while len(raw_parts) < 4:
                    raw_parts.append("")

                name = raw_parts[0]
                lang_code = "-".join(name.split('-')[:2])
                lang_prefix = lang_code.split('-')[0]
                
                # 确定语言所属的区域
                region = "其他"
                for r, langs in regions.items():
                    if lang_prefix in langs or lang_code in langs:
                        region = r
                        break
                    
                # 获取语言中文名称
                lang_display = lang_code
                if lang_prefix in language_names:
                    chinese_name = language_names[lang_prefix]
                    lang_display = f"{lang_code} ({chinese_name})"
                
                # 添加所有语言，不再仅限于中文
                voices_by_region_lang[region][lang_display].append(raw_parts)

            # 按区域和语言创建树形结构
            for region, lang_map in sorted(voices_by_region_lang.items()):
                region_item = QTreeWidgetItem(self.voice_tree, [region])
                region_item.setFlags(region_item.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
                region_item.setCheckState(0, Qt.Unchecked)

                for lang_display, voice_rows in sorted(lang_map.items()):
                    lang_item = QTreeWidgetItem(region_item, [lang_display])
                    lang_item.setFlags(lang_item.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
                    lang_item.setCheckState(0, Qt.Unchecked)

                    for parts in sorted(voice_rows, key=lambda row: row[0]):
                        child = QTreeWidgetItem(lang_item, parts[:4])
                        child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                        child.setCheckState(0, Qt.Unchecked)
                        self.voice_items[parts[0]] = child

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
            self.log_view.append(f"获取语音模型列表失败: {e}")
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
            self.default_output_checkbox.setChecked(data.get("default_output", True))
            self.srt_checkbox.setChecked(data.get("srt_enabled", True))
            self.extra_line_checkbox.setChecked(data.get("extra_line_output", False))

            line_length = int(data.get("line_length", 28))
            self.line_length_input.setText(str(max(5, min(120, line_length))))

            rule_value = data.get("subtitle_rule", SubtitleGenerator.RULE_NEWLINE)
            index = self.subtitle_rule_combo.findData(rule_value)
            if index != -1:
                self.subtitle_rule_combo.setCurrentIndex(index)

            selected_voices = data.get("selected_voices", [])
            self.apply_saved_voice_selection(selected_voices)
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

        try:
            line_length = int(self.line_length_input.text())
        except (TypeError, ValueError):
            line_length = 28

        settings = {
            "default_output": self.default_output_checkbox.isChecked(),
            "srt_enabled": self.srt_checkbox.isChecked(),
            "extra_line_output": self.extra_line_checkbox.isChecked(),
            "line_length": max(5, min(120, line_length)),
            "subtitle_rule": self.subtitle_rule_combo.currentData(),
            "selected_voices": self.get_selected_voices(),
            "panel_states": {
                "settings": self.settings_box.is_expanded(),
                "voice": self.voice_box.is_expanded(),
                "log": self.log_box.is_expanded(),
            },
            "window_geometry": [self.x(), self.y(), self.width(), self.height()],
        }

        try:
            with open(self.get_settings_path(), "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            self.log_view.append(f"⚠ 保存设置失败: {exc}")

    def apply_saved_voice_selection(self, voices: list[str]) -> None:
        # 先全部清空
        root = self.voice_tree.invisibleRootItem()
        for i in range(root.childCount()):
            lang_item = root.child(i)
            lang_item.setCheckState(0, Qt.Unchecked)
            for j in range(lang_item.childCount()):
                gender_item = lang_item.child(j)
                gender_item.setCheckState(0, Qt.Unchecked)
                for k in range(gender_item.childCount()):
                    voice_item = gender_item.child(k)
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

        convert_punctuation = False  # 标点转换现在通过独立的标点转换功能处理
        subtitle_rule = self.subtitle_rule_combo.currentData() or SubtitleGenerator.RULE_SMART

        self.start_button.setEnabled(False)
        self.log_view.append("任务开始...")
        self.log_view.append(f"选中的语音模型: {', '.join(selected_voices)}")
        self.log_view.append(f"整段输出：{'开启' if default_output_enabled else '关闭'}")
        if default_output_enabled:
            if srt_enabled:
                self.log_view.append(f"字幕分段规则：{self.subtitle_rule_combo.currentText()}")
                self.log_view.append(
                    f"字幕选项：开启，单行约 {line_length_value} 字"
                )
            else:
                self.log_view.append("字幕选项：关闭")
        else:
            self.log_view.append("字幕选项：不可用（整段输出已关闭）")
        if extra_line_output:
            self.log_view.append("行级输出：开启 (仅音频)")
        else:
            self.log_view.append("行级输出：关闭")
        
        self.workers.clear()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_root = os.path.join(script_dir, "output")
        os.makedirs(output_root, exist_ok=True)
        for voice in selected_voices:
            worker = TTSWorker(
                voice=voice,
                parent=self,
                srt_enabled=srt_enabled,
                line_length=line_length_value,
                convert_punctuation=convert_punctuation,
                subtitle_rule=subtitle_rule,
                output_root=output_root,
                extra_line_output=extra_line_output,
                default_output=default_output_enabled,
            )
            worker.progress.connect(self.log_view.append)
            worker.finished.connect(self.on_worker_finished)
            self.workers[voice] = worker
            worker.start()

    def on_worker_finished(self, voice):
        self.log_view.append(f"线程 {voice} 已完成。")
        if voice in self.workers:
            del self.workers[voice]
        
        if not self.workers:
            self.log_view.append("\n所有任务均已完成！")
            self.start_button.setEnabled(True)

    def execute_punctuation_conversion(self):
        conversion_type = self.punctuation_combo.currentData()
        
        if conversion_type == "none":
            return
        
        # 获取同目录下所有txt文件
        dir_path = os.path.dirname(os.path.abspath(__file__))
        txt_files = [f for f in os.listdir(dir_path) if f.lower().endswith('.txt')]
        
        if not txt_files:
            self.log_view.append("同目录下未找到任何.txt文件")
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
                
                # 写回文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(converted_content)
                
                converted_count += 1
                
            except Exception as e:
                self.log_view.append(f"✗ 处理文件失败 {txt_file}: {e}")
        
        self.log_view.append(f"标点转换完成，共处理 {converted_count} 个文件")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TTSApp()
    window.show()
    sys.exit(app.exec())
