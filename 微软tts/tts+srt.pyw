import asyncio
import os
import sys
import subprocess
import importlib
from datetime import datetime
from collections import defaultdict

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView, QLineEdit, QCheckBox,
    QComboBox
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


def format_timestamp(total_seconds: float) -> str:
    total_milliseconds = max(0, int(round(total_seconds * 1000)))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


class SubtitleGenerator:
    RULE_SMART = "rule_1"
    RULE_NEWLINE = "rule_2"

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
    def _prepare_lines(
        cls,
        text: str,
        rule: str,
        line_length: int,
    ) -> list[str]:
        if rule == cls.RULE_NEWLINE:
            return cls._split_by_newline(text)

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
    ):
        super().__init__(parent)
        self.voice = voice
        self.output_ext = ".mp3"
        self.srt_enabled = srt_enabled
        self.line_length = max(5, int(line_length or 0))
        self.convert_punctuation = convert_punctuation
        self.subtitle_rule = subtitle_rule

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
                
                # 修改输出文件名
                base_name = os.path.splitext(txt_file)[0]
                output_file = f"{base_name}_{self.voice}{self.output_ext}"
                output_path = os.path.join(dir_path, output_file)
                
                await self.tts_async(text, self.voice, output_path)

                if self.srt_enabled:
                    srt_file = f"{base_name}_{self.voice}.srt"
                    srt_path = os.path.join(dir_path, srt_file)
                    self.generate_srt_file(text, output_path, srt_path)

                self.progress.emit("")

            except Exception as e:
                self.progress.emit(f"处理 {txt_file} 时出错: {e}")
        
        self.progress.emit(f"[{self.voice}] 任务处理完毕！")

    def run(self):
        asyncio.run(self.main_task())
        self.finished.emit(self.voice)


class TTSApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("微软 Edge TTS 文本转语音助手")
        self.setGeometry(100, 100, 600, 500)

        self.layout = QVBoxLayout(self)

        self.label_voice = QLabel("选择语音模型 (可多选):")
        self.voice_tree = QTreeWidget()
        self.voice_tree.setHeaderLabels(["名称", "性别", "类别", "个性"])
        self.voice_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.populate_voices()

        self.options_layout = QHBoxLayout()
        self.srt_checkbox = QCheckBox("同步生成 SRT 字幕文件")
        self.srt_checkbox.setChecked(True)
        self.subtitle_rule_combo = QComboBox()
        self.subtitle_rule_combo.addItem(
            "规则1：按换行切分 (默认)", SubtitleGenerator.RULE_NEWLINE
        )
        self.subtitle_rule_combo.addItem(
            "规则2：智能分句", SubtitleGenerator.RULE_SMART
        )
        self.subtitle_rule_combo.setToolTip("选择字幕切分方式")
        self.line_length_label = QLabel("字幕每行字数(约):")
        self.line_length_input = QLineEdit("28")
        self.line_length_input.setValidator(QIntValidator(5, 120, self))
        self.line_length_input.setFixedWidth(30)
        self.punctuation_checkbox = QCheckBox("转为英文标点")
        self.punctuation_checkbox.setChecked(True)

        self.options_layout.addWidget(self.srt_checkbox)
        self.options_layout.addWidget(self.subtitle_rule_combo)
        self.options_layout.addWidget(self.line_length_label)
        self.options_layout.addWidget(self.line_length_input)
        self.options_layout.addWidget(self.punctuation_checkbox)
        self.options_layout.addStretch()
        
        self.start_button = QPushButton("开始转换")
        self.start_button.clicked.connect(self.start_tts)

        self.srt_checkbox.toggled.connect(self.toggle_srt_options)
        self.subtitle_rule_combo.currentIndexChanged.connect(self.update_line_length_controls)
        self.toggle_srt_options(self.srt_checkbox.isChecked())

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        self.layout.addWidget(self.label_voice)
        self.layout.addWidget(self.voice_tree)
        self.layout.addLayout(self.options_layout)
        self.layout.addWidget(self.start_button)
        self.layout.addWidget(self.log_view)

        self.workers = {}

        self.log_view.append("===============================")
        self.log_view.append(" 微软 Edge TTS 文本转语音助手")
        self.log_view.append("===============================")
        self.log_view.append("1. 将需要转换的文本放在本目录的 .txt 文件中")
        self.log_view.append("2. 在下方树状列表中勾选一个或多个语音模型")
        self.log_view.append("3. 点击“开始转换”按钮启动")
        self.log_view.append("4. 可选：勾选“同步生成 SRT 字幕文件”并调整参数")
        self.log_view.append("")

    def toggle_srt_options(self, enabled):
        self.punctuation_checkbox.setEnabled(enabled)
        self.subtitle_rule_combo.setEnabled(enabled)
        self.update_line_length_controls()

    def update_line_length_controls(self):
        srt_enabled = self.srt_checkbox.isChecked()
        rule_supports_line_length = (
            self.subtitle_rule_combo.currentData() == SubtitleGenerator.RULE_SMART
        )
        allow_line_length = srt_enabled and rule_supports_line_length
        self.line_length_label.setEnabled(allow_line_length)
        self.line_length_input.setEnabled(allow_line_length)

    def populate_voices(self):
        try:
            # 使用 utf-8 编码获取语音列表
            result = subprocess.run(
                [sys.executable, "-m", "edge_tts", "--list-voices"],
                capture_output=True, text=True, encoding='utf-8', errors='ignore'
            )
            lines = result.stdout.strip().split('\n')
            
            voices_by_lang = defaultdict(list)
            # 从第三行开始解析，跳过标题和分隔线
            for line in lines[2:]:
                parts = line.split()
                if len(parts) < 2:
                    continue
                name, gender = parts[0], parts[1]
                
                # 提取语言代码，如 zh-CN
                lang_code = "-".join(name.split('-')[:2])
                if 'zh' in lang_code.lower():
                    voices_by_lang[lang_code].append(line)

            for lang_code, voice_lines in sorted(voices_by_lang.items()):
                parent = QTreeWidgetItem(self.voice_tree, [lang_code])
                parent.setFlags(parent.flags() | Qt.ItemIsAutoTristate | Qt.ItemIsUserCheckable)
                parent.setCheckState(0, Qt.Unchecked)
                for line in sorted(voice_lines):
                    parts = line.split(maxsplit=4)
                    child = QTreeWidgetItem(parent, parts)
                    child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                    child.setCheckState(0, Qt.Unchecked)
            
            # 默认展开所有中文顶级项目
            for i in range(self.voice_tree.topLevelItemCount()):
                item = self.voice_tree.topLevelItem(i)
                if 'zh' in item.text(0).lower():
                    item.setExpanded(True)

        except Exception as e:
            self.log_view.append(f"获取语音模型列表失败: {e}")
            # 提供备用选项
            fallback_parent = QTreeWidgetItem(self.voice_tree, ["zh-CN"])
            for voice in ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-YunjianNeural"]:
                child = QTreeWidgetItem(fallback_parent, [voice])
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)

    def get_selected_voices(self):
        selected = []
        root = self.voice_tree.invisibleRootItem()
        for i in range(root.childCount()):
            parent = root.child(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child.checkState(0) == Qt.Checked:
                    selected.append(child.text(0))
        return selected

    def start_tts(self):
        selected_voices = self.get_selected_voices()
        if not selected_voices:
            self.log_view.append("错误：请至少选择一个语音模型。")
            return

        srt_enabled = self.srt_checkbox.isChecked()
        line_length_text = self.line_length_input.text().strip()
        try:
            line_length_value = int(line_length_text)
        except ValueError:
            line_length_value = 28

        line_length_value = max(5, min(120, line_length_value))
        if str(line_length_value) != line_length_text:
            self.line_length_input.setText(str(line_length_value))

        convert_punctuation = self.punctuation_checkbox.isChecked() and srt_enabled
        subtitle_rule = self.subtitle_rule_combo.currentData() or SubtitleGenerator.RULE_SMART

        self.start_button.setEnabled(False)
        self.log_view.append("任务开始...")
        self.log_view.append(f"选中的语音模型: {', '.join(selected_voices)}")
        if srt_enabled:
            style = "英文标点" if convert_punctuation else "原始标点"
            self.log_view.append(f"字幕分段规则：{self.subtitle_rule_combo.currentText()}")
            self.log_view.append(
                f"字幕选项：开启，单行约 {line_length_value} 字，输出符号使用{style}"
            )
        else:
            self.log_view.append("字幕选项：关闭")
        
        self.workers.clear()
        for voice in selected_voices:
            worker = TTSWorker(
                voice=voice,
                parent=self,
                srt_enabled=srt_enabled,
                line_length=line_length_value,
                convert_punctuation=convert_punctuation,
                subtitle_rule=subtitle_rule,
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TTSApp()
    window.show()
    sys.exit(app.exec())
