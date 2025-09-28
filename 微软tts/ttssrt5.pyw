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
    QComboBox
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QIntValidator, QIcon


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
        self.setGeometry(100, 100, 600, 650)

        self.layout = QVBoxLayout(self)

        self.label_voice = QLabel("选择语音模型 (可多选):")
        self.voice_tree = QTreeWidget()
        self.voice_tree.setHeaderLabels(["选择", "星标", "名称", "性别", "类别", "个性"])
        # 设置列宽为更紧凑的尺寸
        self.voice_tree.setColumnWidth(0, 60)  # 选择列
        self.voice_tree.setColumnWidth(1, 50)  # 星标列
        self.voice_tree.setColumnWidth(2, 200) # 名称列
        self.voice_tree.setColumnWidth(3, 80)  # 性别列
        self.voice_tree.setColumnWidth(4, 80)  # 类别列
        self.voice_tree.setColumnWidth(5, 100) # 个性列
        self.voice_tree.setSortingEnabled(True)
        header = self.voice_tree.header()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        self.voice_tree.itemClicked.connect(self.on_voice_item_clicked)
        self.voice_items = {}
        self.starred_voices = set()
        self.populate_voices()

        # 标点转换功能
        self.punctuation_layout = QHBoxLayout()
        self.punctuation_label = QLabel("标点转换:")
        self.punctuation_combo = QComboBox()
        self.punctuation_combo.addItem("不转换", "none")
        self.punctuation_combo.addItem("中文标点 → 英文标点", "to_halfwidth")
        self.punctuation_combo.addItem("英文标点 → 中文标点", "to_fullwidth")
        self.punctuation_combo.setToolTip("选择标点转换方式，选择后立即对同目录下所有txt文件执行转换")
        
        self.punctuation_layout.addWidget(self.punctuation_label)
        self.punctuation_layout.addWidget(self.punctuation_combo)

        self.options_layout = QHBoxLayout()
        self.default_output_checkbox = QCheckBox("完整输出")
        self.default_output_checkbox.setChecked(True)
        self.srt_checkbox = QCheckBox("生成字幕")
        self.srt_checkbox.setChecked(True)
        self.extra_line_checkbox = QCheckBox("分行输出")

        self.rule_label = QLabel("分行规则:")
        self.subtitle_rule_combo = QComboBox()
        self.subtitle_rule_combo.addItem(
            "规则1：按换行切分 (默认)", SubtitleGenerator.RULE_NEWLINE
        )
        self.subtitle_rule_combo.addItem(
            "规则2：智能分句", SubtitleGenerator.RULE_SMART
        )
        self.subtitle_rule_combo.addItem(
            "规则3：hanlp分句", SubtitleGenerator.RULE_HANLP
        )
        self.subtitle_rule_combo.setToolTip("选择字幕切分方式")
        self.line_length_label = QLabel("行字数(约):")
        self.line_length_input = QLineEdit("28")
        self.line_length_input.setValidator(QIntValidator(5, 120, self))
        self.line_length_input.setFixedWidth(30)

        self.options_layout.addWidget(self.default_output_checkbox)
        self.options_layout.addWidget(self.extra_line_checkbox)
        self.options_layout.addWidget(self.srt_checkbox)
        self.options_layout.addWidget(self.rule_label)
        self.options_layout.addWidget(self.subtitle_rule_combo)
        self.options_layout.addWidget(self.line_length_label)
        self.options_layout.addWidget(self.line_length_input)
        self.options_layout.addStretch()
        
        self.start_button = QPushButton("开始转换")
        self.start_button.clicked.connect(self.start_tts)

        self.punctuation_combo.currentIndexChanged.connect(self.execute_punctuation_conversion)

        self.default_output_checkbox.toggled.connect(self.update_option_states)
        self.srt_checkbox.toggled.connect(self.update_option_states)
        self.subtitle_rule_combo.currentIndexChanged.connect(self.update_option_states)
        self.extra_line_checkbox.toggled.connect(self.update_option_states)
        self.update_option_states()

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        self.layout.addWidget(self.label_voice)
        self.layout.addWidget(self.voice_tree)
        self.layout.addLayout(self.punctuation_layout)
        self.layout.addLayout(self.options_layout)
        self.layout.addWidget(self.start_button)
        self.layout.addWidget(self.log_view)

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

            # 国家代码到中文名称的映射
            country_names = {
                'AF': '阿富汗', 'AL': '阿尔巴尼亚', 'DZ': '阿尔及利亚', 'AS': '美属萨摩亚', 'AD': '安道尔', 'AO': '安哥拉', 'AI': '安圭拉', 'AQ': '南极洲', 'AG': '安提瓜和巴布达', 'AR': '阿根廷', 'AM': '亚美尼亚', 'AW': '阿鲁巴', 'AU': '澳大利亚', 'AT': '奥地利', 'AZ': '阿塞拜疆', 'BS': '巴哈马', 'BH': '巴林', 'BD': '孟加拉国', 'BB': '巴巴多斯', 'BY': '白俄罗斯', 'BE': '比利时', 'BZ': '伯利兹', 'BJ': '贝宁', 'BM': '百慕大', 'BT': '不丹', 'BO': '玻利维亚', 'BA': '波斯尼亚和黑塞哥维那', 'BW': '博茨瓦纳', 'BR': '巴西', 'BN': '文莱', 'BG': '保加利亚', 'BF': '布基纳法索', 'BI': '布隆迪', 'KH': '柬埔寨', 'CM': '喀麦隆', 'CA': '加拿大', 'CV': '佛得角', 'KY': '开曼群岛', 'CF': '中非共和国', 'TD': '乍得', 'CL': '智利', 'CN': '中国', 'CO': '哥伦比亚', 'KM': '科摩罗', 'CG': '刚果', 'CD': '刚果民主共和国', 'CK': '库克群岛', 'CR': '哥斯达黎加', 'CI': '科特迪瓦', 'HR': '克罗地亚', 'CU': '古巴', 'CY': '塞浦路斯', 'CZ': '捷克', 'DK': '丹麦', 'DJ': '吉布提', 'DM': '多米尼加', 'DO': '多米尼加共和国', 'EC': '厄瓜多尔', 'EG': '埃及', 'SV': '萨尔瓦多', 'GQ': '赤道几内亚', 'ER': '厄立特里亚', 'EE': '爱沙尼亚', 'ET': '埃塞俄比亚', 'FK': '福克兰群岛', 'FO': '法罗群岛', 'FJ': '斐济', 'FI': '芬兰', 'FR': '法国', 'GF': '法属圭亚那', 'PF': '法属波利尼西亚', 'GA': '加蓬', 'GM': '冈比亚', 'GE': '格鲁吉亚', 'DE': '德国', 'GH': '加纳', 'GI': '直布罗陀', 'GR': '希腊', 'GL': '格陵兰', 'GD': '格林纳达', 'GP': '瓜德罗普', 'GU': '关岛', 'GT': '危地马拉', 'GG': '根西岛', 'GN': '几内亚', 'GW': '几内亚比绍', 'GY': '圭亚那', 'HT': '海地', 'HN': '洪都拉斯', 'HK': '香港', 'HU': '匈牙利', 'IS': '冰岛', 'IN': '印度', 'ID': '印度尼西亚', 'IR': '伊朗', 'IQ': '伊拉克', 'IE': '爱尔兰', 'IM': '马恩岛', 'IL': '以色列', 'IT': '意大利', 'JM': '牙买加', 'JP': '日本', 'JE': '泽西岛', 'JO': '约旦', 'KZ': '哈萨克斯坦', 'KE': '肯尼亚', 'KI': '基里巴斯', 'KP': '朝鲜', 'KR': '韩国', 'KW': '科威特', 'KG': '吉尔吉斯斯坦', 'LA': '老挝', 'LV': '拉脱维亚', 'LB': '黎巴嫩', 'LS': '莱索托', 'LR': '利比里亚', 'LY': '利比亚', 'LI': '列支敦士登', 'LT': '立陶宛', 'LU': '卢森堡', 'MO': '澳门', 'MK': '北马其顿', 'MG': '马达加斯加', 'MW': '马拉维', 'MY': '马来西亚', 'MV': '马尔代夫', 'ML': '马里', 'MT': '马耳他', 'MH': '马绍尔群岛', 'MQ': '马提尼克', 'MR': '毛里塔尼亚', 'MU': '毛里求斯', 'YT': '马约特', 'MX': '墨西哥', 'FM': '密克罗尼西亚', 'MD': '摩尔多瓦', 'MC': '摩纳哥', 'MN': '蒙古', 'ME': '黑山', 'MS': '蒙特塞拉特', 'MA': '摩洛哥', 'MZ': '莫桑比克', 'MM': '缅甸', 'NA': '纳米比亚', 'NR': '瑙鲁', 'NP': '尼泊尔', 'NL': '荷兰', 'NC': '新喀里多尼亚', 'NZ': '新西兰', 'NI': '尼加拉瓜', 'NE': '尼日尔', 'NG': '尼日利亚', 'NU': '纽埃', 'NF': '诺福克岛', 'MP': '北马里亚纳群岛', 'NO': '挪威', 'OM': '阿曼', 'PK': '巴基斯坦', 'PW': '帕劳', 'PS': '巴勒斯坦', 'PA': '巴拿马', 'PG': '巴布亚新几内亚', 'PY': '巴拉圭', 'PE': '秘鲁', 'PH': '菲律宾', 'PN': '皮特凯恩群岛', 'PL': '波兰', 'PT': '葡萄牙', 'PR': '波多黎各', 'QA': '卡塔尔', 'RE': '留尼汪', 'RO': '罗马尼亚', 'RU': '俄罗斯', 'RW': '卢旺达', 'BL': '圣巴泰勒米', 'SH': '圣赫勒拿', 'KN': '圣基茨和尼维斯', 'LC': '圣卢西亚', 'MF': '圣马丁', 'PM': '圣皮埃尔和密克隆', 'VC': '圣文森特和格林纳丁斯', 'WS': '萨摩亚', 'SM': '圣马力诺', 'ST': '圣多美和普林西比', 'SA': '沙特阿拉伯', 'SN': '塞内加尔', 'RS': '塞尔维亚', 'SC': '塞舌尔', 'SL': '塞拉利昂', 'SG': '新加坡', 'SX': '荷属圣马丁', 'SK': '斯洛伐克', 'SI': '斯洛文尼亚', 'SB': '所罗门群岛', 'SO': '索马里', 'ZA': '南非', 'SS': '南苏丹', 'ES': '西班牙', 'LK': '斯里兰卡', 'SD': '苏丹', 'SR': '苏里南', 'SJ': '斯瓦尔巴和扬马延', 'SZ': '斯威士兰', 'SE': '瑞典', 'CH': '瑞士', 'SY': '叙利亚', 'TW': '台湾', 'TJ': '塔吉克斯坦', 'TZ': '坦桑尼亚', 'TH': '泰国', 'TL': '东帝汶', 'TG': '多哥', 'TK': '托克劳', 'TO': '汤加', 'TT': '特立尼达和多巴哥', 'TN': '突尼斯', 'TR': '土耳其', 'TM': '土库曼斯坦', 'TC': '特克斯和凯科斯群岛', 'TV': '图瓦卢', 'UG': '乌干达', 'UA': '乌克兰', 'AE': '阿拉伯联合酋长国', 'GB': '英国', 'US': '美国', 'UY': '乌拉圭', 'UZ': '乌兹别克斯坦', 'VU': '瓦努阿图', 'VA': '梵蒂冈', 'VE': '委内瑞拉', 'VN': '越南', 'VG': '英属维尔京群岛', 'VI': '美属维尔京群岛', 'WF': '瓦利斯和富图纳', 'EH': '西撒哈拉', 'YE': '也门', 'ZM': '赞比亚', 'ZW': '津巴布韦'
            }

            # 国家代码到洲的映射
            continent_map = {
                '亚洲': ['AF', 'AM', 'AZ', 'BD', 'BH', 'BN', 'BT', 'CN', 'CY', 'GE', 'HK', 'ID', 'IL', 'IN', 'IQ', 'IR', 'JO', 'JP', 'KG', 'KH', 'KP', 'KR', 'KW', 'KZ', 'LA', 'LB', 'LK', 'MM', 'MN', 'MO', 'MV', 'MY', 'NP', 'OM', 'PH', 'PK', 'PS', 'QA', 'SA', 'SG', 'SY', 'TH', 'TJ', 'TL', 'TM', 'TR', 'TW', 'UA', 'UZ', 'VN', 'YE'],
                '欧洲': ['AD', 'AL', 'AT', 'BA', 'BE', 'BG', 'BY', 'CH', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI', 'FR', 'GB', 'GG', 'GI', 'GR', 'HR', 'HU', 'IE', 'IM', 'IS', 'IT', 'JE', 'LI', 'LT', 'LU', 'LV', 'MC', 'MD', 'ME', 'MK', 'MT', 'NL', 'NO', 'PL', 'PT', 'RO', 'RS', 'RU', 'SE', 'SI', 'SJ', 'SK', 'SM', 'UA', 'VA'],
                '非洲': ['AO', 'BF', 'BI', 'BJ', 'BW', 'CD', 'CF', 'CG', 'CI', 'CM', 'CV', 'DJ', 'DZ', 'EG', 'EH', 'ER', 'ET', 'GA', 'GH', 'GM', 'GN', 'GQ', 'GW', 'KE', 'KM', 'LR', 'LS', 'LY', 'MA', 'MG', 'ML', 'MR', 'MU', 'MW', 'MZ', 'NA', 'NE', 'NG', 'RW', 'SC', 'SD', 'SL', 'SN', 'SO', 'SS', 'ST', 'SZ', 'TD', 'TG', 'TN', 'TZ', 'UG', 'ZA', 'ZM', 'ZW'],
                '北美洲': ['AG', 'AI', 'AW', 'BB', 'BM', 'BS', 'BZ', 'CA', 'CR', 'CU', 'DM', 'DO', 'GD', 'GL', 'GP', 'GT', 'HN', 'HT', 'JM', 'KN', 'KY', 'LC', 'MF', 'MQ', 'MS', 'MX', 'NI', 'PA', 'PM', 'PR', 'SV', 'TC', 'TT', 'US', 'VC', 'VG', 'VI'],
                '南美洲': ['AR', 'BO', 'BR', 'CL', 'CO', 'EC', 'FK', 'GF', 'GY', 'PE', 'PY', 'SR', 'UY', 'VE'],
                '大洋洲': ['AS', 'AU', 'CK', 'FJ', 'FM', 'GU', 'KI', 'MH', 'MP', 'NC', 'NF', 'NR', 'NU', 'NZ', 'PF', 'PG', 'PN', 'PW', 'SB', 'TK', 'TO', 'TV', 'VU', 'WF', 'WS'],
                '南极洲': ['AQ']
            }

            # 使用 utf-8 编码获取语音列表
            result = subprocess.run(
                [sys.executable, "-m", "edge_tts", "--list-voices"],
                capture_output=True, text=True, encoding='utf-8', errors='ignore'
            )
            lines = result.stdout.strip().split('\n')

            voices_by_continent_lang_gender = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
            # 从第三行开始解析，跳过标题和分隔线
            for line in lines[2:]:
                raw_parts = line.split(maxsplit=4)
                if len(raw_parts) < 2:
                    continue
                # Ensure we have at least 4 columns
                while len(raw_parts) < 4:
                    raw_parts.append("")

                name = raw_parts[0]
                gender = raw_parts[1] or "未知"
                lang_code = "-".join(name.split('-')[:2])
                country_code = lang_code.split('-')[-1] if '-' in lang_code else '未知'
                country_name = country_names.get(country_code.upper(), country_code)
                
                # 确定洲
                continent = "未知"
                for cont, countries in continent_map.items():
                    if country_code.upper() in countries:
                        continent = cont
                        break
                
                voices_by_continent_lang_gender[continent][lang_code][gender].append(raw_parts)

            for continent, lang_map in sorted(voices_by_continent_lang_gender.items()):
                continent_item = QTreeWidgetItem(self.voice_tree, ["", "☆", continent, "", "", ""])
                continent_item.setFlags(continent_item.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
                continent_item.setCheckState(0, Qt.Unchecked)  # 复选框在选择列

                for lang_code, gender_map in sorted(lang_map.items()):
                    # 获取国家名称用于显示
                    country_code = lang_code.split('-')[-1] if '-' in lang_code else '未知'
                    country_name = country_names.get(country_code.upper(), country_code)
                    lang_item = QTreeWidgetItem(continent_item, ["", "☆", f"{lang_code} ({country_name})", "", "", ""])
                    lang_item.setFlags(lang_item.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
                    lang_item.setCheckState(0, Qt.Unchecked)

                    for gender, voice_rows in sorted(gender_map.items()):
                        for parts in sorted(voice_rows, key=lambda row: row[0]):
                            star = "★" if parts[0] in self.starred_voices else "☆"
                            child = QTreeWidgetItem(lang_item, ["", star] + parts[:4])
                            child.setFlags(child.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
                            child.setCheckState(0, Qt.Unchecked)
                            self.voice_items[parts[0]] = child

            # 默认展开所有顶级项目
            for i in range(self.voice_tree.topLevelItemCount()):
                item = self.voice_tree.topLevelItem(i)
                item.setExpanded(True)

        except Exception as e:
            self.log_view.append(f"获取语音模型列表失败: {e}")
            # 提供备用选项
            fallback_parent = QTreeWidgetItem(self.voice_tree, ["未知"])
            fallback_parent.setFlags(fallback_parent.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
            fallback_parent.setCheckState(0, Qt.Unchecked)
            for voice in ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-YunjianNeural"]:
                child = QTreeWidgetItem(fallback_parent, ["", "☆", voice, "", "", ""])
                child.setFlags(child.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)
                self.voice_items[voice] = child

    def on_voice_item_clicked(self, item, column):
        if column == 0:  # 复选框列
            self._handle_checkbox_click(item)
        elif column == 1:  # 星标列
            self._handle_star_click(item)

    def _handle_checkbox_click(self, item):
        """处理复选框点击"""
        item_text = item.text(2)
        if not item_text:
            return

        # 检查是否在星标列表中
        parent = item.parent()
        is_in_starred_list = parent and parent.text(2).startswith("★ 星标列表")

        if is_in_starred_list:
            # 星标列表中的复选框点击 - 同步到主列表
            self._sync_checkbox_from_starred_to_main(item)
        else:
            # 主列表中的复选框点击 - 同步到星标列表
            self._sync_checkbox_from_main_to_starred(item)

    def _handle_star_click(self, item):
        """处理星标点击"""
        voice_name = None
        for name, it in self.voice_items.items():
            if it == item:
                voice_name = name
                break
        
        # 检查是否是星标列表内的项目
        if voice_name and voice_name.startswith("starred_"):
            # 从星标列表中移除
            actual_voice_name = voice_name.replace("starred_", "")
            if actual_voice_name in self.starred_voices:
                self.starred_voices.remove(actual_voice_name)
                # 更新原始项的星标显示和复选框状态
                original_item = self.voice_items.get(actual_voice_name)
                if original_item:
                    original_item.setText(1, "☆")
                    original_item.setCheckState(0, Qt.Unchecked)
                self.update_starred_list()
        elif voice_name and not voice_name.startswith("starred_"):
            # 语音层级的星标切换
            if voice_name in self.starred_voices:
                self.starred_voices.remove(voice_name)
                item.setText(1, "☆")
                item.setCheckState(0, Qt.Unchecked)
            else:
                self.starred_voices.add(voice_name)
                item.setText(1, "★")
                item.setCheckState(0, Qt.Checked)
            self.update_starred_list()
        else:
            # 处理洲和语言层级的星标切换
            item_text = item.text(2)
            if item_text:
                # 检查是否在星标列表中
                parent = item.parent()
                if parent and parent.text(2).startswith("★ 星标列表"):
                    # 星标列表中的洲或语言层级
                    if item.text(1) == "★":
                        item.setText(1, "☆")
                        item.setCheckState(0, Qt.Unchecked)
                        # 递归取消所有子项的星标和复选框
                        self._set_star_recursive(item, "☆")
                        self._set_checkbox_recursive(item, Qt.Unchecked)
                        # 更新主列表中的对应项
                        self._update_main_list_stars_from_starred(item, "☆")
                        self._update_main_list_checkboxes_from_starred(item, Qt.Unchecked)
                    else:
                        item.setText(1, "★")
                        item.setCheckState(0, Qt.Checked)
                        # 递归设置所有子项的星标和复选框
                        self._set_star_recursive(item, "★")
                        self._set_checkbox_recursive(item, Qt.Checked)
                        # 更新主列表中的对应项
                        self._update_main_list_stars_from_starred(item, "★")
                        self._update_main_list_checkboxes_from_starred(item, Qt.Checked)
                else:
                    # 主列表中的洲或语言层级
                    if item.text(1) == "★":
                        item.setText(1, "☆")
                        item.setCheckState(0, Qt.Unchecked)
                        # 递归取消所有子项的星标和复选框
                        self._set_star_recursive(item, "☆")
                        self._set_checkbox_recursive(item, Qt.Unchecked)
                        # 更新starred_voices集合
                        self._update_starred_voices_from_item(item)
                        # 刷新星标列表
                        self.update_starred_list()
                    else:
                        item.setText(1, "★")
                        item.setCheckState(0, Qt.Checked)
                        # 递归设置所有子项的星标和复选框
                        self._set_star_recursive(item, "★")
                        self._set_checkbox_recursive(item, Qt.Checked)
                        # 如果是洲或语言层级，需要更新starred_voices集合
                        self._update_starred_voices_from_item(item)
                        # 刷新星标列表
                        self.update_starred_list()

    def _set_star_recursive(self, item, star_symbol):
        """递归设置所有子项的星标"""
        for i in range(item.childCount()):
            child = item.child(i)
            child.setText(1, star_symbol)
            # 递归处理子项的子项
            self._set_star_recursive(child, star_symbol)

    def _set_checkbox_recursive(self, item, check_state):
        """递归设置所有子项的复选框状态"""
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, check_state)
            # 递归处理子项的子项
            self._set_checkbox_recursive(child, check_state)

    def _sync_checkbox_from_starred_to_main(self, starred_item):
        """从星标列表同步复选框状态到主列表"""
        item_text = starred_item.text(2)
        check_state = starred_item.checkState(0)
        
        # 查找主列表中的对应项并同步
        root = self.voice_tree.invisibleRootItem()
        for i in range(root.childCount()):
            continent_item = root.child(i)
            if continent_item.text(2) == item_text:
                # 找到对应的洲项
                continent_item.setCheckState(0, check_state)
                self._set_checkbox_recursive(continent_item, check_state)
                return
            elif continent_item.text(2).startswith("★ 星标列表"):
                continue  # 跳过星标列表
            else:
                # 检查洲下的语言项
                for j in range(continent_item.childCount()):
                    lang_item = continent_item.child(j)
                    if lang_item.text(2) == item_text:
                        # 找到对应的语言项
                        lang_item.setCheckState(0, check_state)
                        self._set_checkbox_recursive(lang_item, check_state)
                        return

    def _sync_checkbox_from_main_to_starred(self, main_item):
        """从主列表同步复选框状态到星标列表"""
        item_text = main_item.text(2)
        check_state = main_item.checkState(0)
        
        # 查找星标列表中的对应项并同步
        root = self.voice_tree.invisibleRootItem()
        starred_root = None
        for i in range(root.childCount()):
            item = root.child(i)
            if item.text(2).startswith("★ 星标列表"):
                starred_root = item
                break
        
        if starred_root:
            # 递归查找星标列表中的对应项
            self._find_and_sync_starred_item(starred_root, item_text, check_state)

    def _find_and_sync_starred_item(self, item, target_text, check_state):
        """递归查找并同步星标列表中的项"""
        if item.text(2) == target_text:
            item.setCheckState(0, check_state)
            self._set_checkbox_recursive(item, check_state)
            return True
        
        for i in range(item.childCount()):
            if self._find_and_sync_starred_item(item.child(i), target_text, check_state):
                return True
        return False

    def _update_main_list_checkboxes_from_starred(self, starred_item, check_state):
        """根据星标列表中的项更新主列表中的复选框状态"""
        item_text = starred_item.text(2)
        
        # 查找主列表中的对应项
        root = self.voice_tree.invisibleRootItem()
        for i in range(root.childCount()):
            continent_item = root.child(i)
            if continent_item.text(2) == item_text:
                # 找到对应的洲项
                continent_item.setCheckState(0, check_state)
                self._set_checkbox_recursive(continent_item, check_state)
                return
            elif continent_item.text(2).startswith("★ 星标列表"):
                continue  # 跳过星标列表
            else:
                # 检查洲下的语言项
                for j in range(continent_item.childCount()):
                    lang_item = continent_item.child(j)
                    if lang_item.text(2) == item_text:
                        # 找到对应的语言项
                        lang_item.setCheckState(0, check_state)
                        self._set_checkbox_recursive(lang_item, check_state)
                        return

    def _update_starred_voices_from_item(self, item):
        """根据项的状态更新starred_voices集合"""
        star_symbol = item.text(1)
        is_starred = (star_symbol == "★")
        
        # 递归处理所有子项
        self._update_starred_voices_recursive(item, is_starred)

    def _update_starred_voices_recursive(self, item, is_starred):
        """递归更新starred_voices集合"""
        for i in range(item.childCount()):
            child = item.child(i)
            # 检查是否是语音项（有voice_name的项）
            voice_name = None
            for name, it in self.voice_items.items():
                if it == child:
                    voice_name = name
                    break
            
            if voice_name and not voice_name.startswith("starred_"):
                if is_starred:
                    if voice_name not in self.starred_voices:
                        self.starred_voices.add(voice_name)
                else:
                    if voice_name in self.starred_voices:
                        self.starred_voices.remove(voice_name)
            
            # 递归处理子项
            self._update_starred_voices_recursive(child, is_starred)

    def _update_main_list_stars_from_starred(self, starred_item, star_symbol):
        """根据星标列表中的项更新主列表中的对应项"""
        item_text = starred_item.text(2)
        
        # 查找主列表中的对应项
        root = self.voice_tree.invisibleRootItem()
        for i in range(root.childCount()):
            continent_item = root.child(i)
            if continent_item.text(2) == item_text:
                # 找到对应的洲项
                continent_item.setText(1, star_symbol)
                self._set_star_recursive(continent_item, star_symbol)
                return
            elif continent_item.text(2).startswith("★ 星标列表"):
                continue  # 跳过星标列表
            else:
                # 检查洲下的语言项
                for j in range(continent_item.childCount()):
                    lang_item = continent_item.child(j)
                    if lang_item.text(2) == item_text:
                        # 找到对应的语言项
                        lang_item.setText(1, star_symbol)
                        self._set_star_recursive(lang_item, star_symbol)
                        return

    def update_starred_list(self):
        # 清除旧的星标列表
        root = self.voice_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.text(2).startswith("★ 星标列表"):
                root.removeChild(item)
                break
        
        if self.starred_voices:
            # 将星标列表插入到第一个位置
            starred_item = QTreeWidgetItem()
            starred_item.setText(0, "")
            starred_item.setText(1, "")
            starred_item.setText(2, "★ 星标列表")
            starred_item.setText(3, "")
            starred_item.setText(4, "")
            starred_item.setText(5, "")
            starred_item.setFlags(starred_item.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
            starred_item.setCheckState(0, Qt.Unchecked)
            
            root.insertChild(0, starred_item)  # 插入到第一个位置
            
            # 按照洲-语言的方式组织星标列表
            starred_by_continent = defaultdict(lambda: defaultdict(list))
            
            for voice in self.starred_voices:
                if voice in self.voice_items:
                    original_item = self.voice_items[voice]
                    # 从原始项的父级结构中获取洲、语言信息
                    lang_item = original_item.parent()
                    if lang_item:
                        continent_item = lang_item.parent()
                        if continent_item:
                            continent = continent_item.text(2)  # 名称在第2列
                            lang_code = lang_item.text(2).split(' (')[0]  # 提取语言代码，如"zh-CN"
                            starred_by_continent[continent][lang_code].append((voice, original_item))
            
            # 创建星标列表的树形结构
            for continent in sorted(starred_by_continent.keys()):
                continent_starred = QTreeWidgetItem(starred_item, ["", "", continent, "", "", ""])
                continent_starred.setFlags(continent_starred.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
                continent_starred.setCheckState(0, Qt.Unchecked)
                
                for lang_code in sorted(starred_by_continent[continent].keys()):
                    # 获取对应的语言显示名称
                    lang_display = ""
                    for j in range(root.childCount()):
                        cont_item = root.child(j)
                        if cont_item.text(2) == continent:
                            for k in range(cont_item.childCount()):
                                lang_item = cont_item.child(k)
                                if lang_item.text(2).startswith(lang_code):
                                    lang_display = lang_item.text(2)
                                    break
                            break
                    
                    if lang_display:
                        lang_starred = QTreeWidgetItem(continent_starred, ["", "", lang_display, "", "", ""])
                        lang_starred.setFlags(lang_starred.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
                        lang_starred.setCheckState(0, Qt.Unchecked)
                        
                        for voice, original_item in sorted(starred_by_continent[continent][lang_code], key=lambda x: x[0]):
                            # 复制项到星标列表
                            child = QTreeWidgetItem(lang_starred, [
                                "",
                                "★",
                                original_item.text(2),
                                original_item.text(3),
                                original_item.text(4),
                                original_item.text(5)
                            ])
                            child.setFlags(child.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
                            child.setCheckState(0, Qt.Unchecked)
                            # 关联到原始项
                            self.voice_items[f"starred_{voice}"] = child

    def get_selected_voices(self):
        selected = []
        root = self.voice_tree.invisibleRootItem()
        for i in range(root.childCount()):
            continent_item = root.child(i)
            if continent_item.text(0).startswith("★ 星标列表"):
                # 处理星标列表
                for k in range(continent_item.childCount()):
                    voice_item = continent_item.child(k)
                    if voice_item.checkState(0) == Qt.Checked:
                        # 从文本中提取voice name
                        voice_name = voice_item.text(2)
                        selected.append(voice_name)
            else:
                # 处理洲分组
                for j in range(continent_item.childCount()):
                    lang_item = continent_item.child(j)
                    for k in range(lang_item.childCount()):
                        voice_item = lang_item.child(k)
                        if voice_item.checkState(0) == Qt.Checked:
                            selected.append(voice_item.text(2))
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
            
            starred_voices = data.get("starred_voices", [])
            self.starred_voices = set(starred_voices)
            self.update_starred_list()
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
            "starred_voices": list(self.starred_voices),
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
            continent_item = root.child(i)
            continent_item.setCheckState(0, Qt.Unchecked)
            for j in range(continent_item.childCount()):
                lang_item = continent_item.child(j)
                lang_item.setCheckState(0, Qt.Unchecked)
                for k in range(lang_item.childCount()):
                    voice_item = lang_item.child(k)
                    voice_item.setCheckState(0, Qt.Unchecked)

        for voice in voices:
            item = self.voice_items.get(voice)
            if item is not None:
                item.setCheckState(0, Qt.Checked)
                if voice in self.starred_voices:
                    item.setText(1, "★")

    def closeEvent(self, event):
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
