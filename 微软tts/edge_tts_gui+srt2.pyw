import asyncio
import os
import sys
import subprocess
import importlib
from datetime import datetime, timedelta
from collections import defaultdict

try:
    from mutagen.mp3 import MP3
except ImportError:
    print("未检测到 mutagen，正在自动安装……")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mutagen"])
    from mutagen.mp3 import MP3

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView, QCheckBox, QSpinBox
)
from PySide6.QtCore import QThread, Signal, Qt


# 自动检查并安装 edge-tts
def ensure_edge_tts():
    try:
        # 优先尝试导入已安装的库
        import edge_tts
        return edge_tts
    except ImportError:
        print("未检测到 edge-tts，正在自动安装……")
        # 使用 subprocess 确保在隔离环境中执行 pip
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "edge-tts", "PySide6", "mutagen"])
            # 清除模块缓存，确保能导入新安装的库
            importlib.invalidate_caches()
            import edge_tts
            return edge_tts
        except subprocess.CalledProcessError as e:
            print(f"安装 edge-tts 失败: {e}")
            sys.exit(1)
        except ImportError:
            print("安装后无法导入 edge-tts，请手动检查环境。")
            sys.exit(1)

edge_tts = ensure_edge_tts()

class TTSWorker(QThread):
    progress = Signal(str)
    finished = Signal(str)  # Pass worker's voice name on finish

    def __init__(self, voice, generate_srt=False, srt_max_chars=30, use_half_width_punctuation=False, parent=None):
        super().__init__(parent)
        self.voice = voice
        self.generate_srt = generate_srt
        self.srt_max_chars = srt_max_chars
        self.use_half_width_punctuation = use_half_width_punctuation
        self.output_ext = ".mp3"

    async def tts_async(self, text, voice, output):
        subtitles = []
        communicate = edge_tts.Communicate(text, voice)
        self.progress.emit(f"    → [{self.voice}] 正在调用微软语音服务 (流式)...")
        try:
            with open(output, "wb") as file:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        file.write(chunk["data"])
                    elif self.generate_srt and chunk["type"] == "WordBoundary":
                        subtitles.append(chunk)
            self.progress.emit(f"    ✓ [{self.voice}] 语音已保存到 {os.path.basename(output)}")
            return subtitles
        except Exception as e:
            self.progress.emit(f"    ✗ [{self.voice}] 调用语音服务时出错: {e}")
            self.progress.emit(f"    请确保您的 edge-tts 库是最新版本 (pip install --upgrade edge-tts)")
            return None

    def create_word_boundary_log(self, audio_path, subtitles):
        """创建包含词边界时间戳的日志文件"""
        log_path = os.path.splitext(audio_path)[0] + "_word_boundaries.txt"
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(f"词边界日志: {os.path.basename(audio_path)}\n")
                f.write("========================================\n\n")
                f.write(f"{'词语':<15} | {'开始时间 (秒)':<20} | {'持续时间 (秒)':<20}\n")
                f.write(f"{'-'*15} | {'-'*20} | {'-'*20}\n")
                for sub in subtitles:
                    offset_s = sub['offset'] / 1_000_000
                    duration_s = sub['duration'] / 1_000_000
                    text = sub['text']
                    f.write(f"{text:<14} | {offset_s:<20.6f} | {duration_s:<20.6f}\n")
            self.progress.emit(f"    ✓ [{self.voice}] 词边界日志已保存到 {os.path.basename(log_path)}")
        except Exception as e:
            self.progress.emit(f"    ✗ [{self.voice}] 创建词边界日志失败: {e}")

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
                
                subtitles = await self.tts_async(text, self.voice, output_path)

                if subtitles:
                    # 新增：创建词边界日志
                    self.create_word_boundary_log(output_path, subtitles)

                if self.generate_srt and subtitles:
                    processed_subs = self._process_subtitles(subtitles)
                    self.create_srt_file(output_path, processed_subs)
                elif self.generate_srt:
                    # Fallback for old API
                    self.create_srt_file(output_path, text)

                self.progress.emit("")

            except Exception as e:
                self.progress.emit(f"处理 {txt_file} 时出错: {e}")
        
        self.progress.emit(f"[{self.voice}] 任务处理完毕！")

    def _process_subtitles(self, subtitles):
        """将词边界信息处理成带时间戳的字幕行"""
        
        def to_half_width(text):
            # 简单的半角转换
            mapping = {
                '，': ', ', '。': '. ', '？': '? ', '！': '! ',
                '；': '; ', '：': ': ', '（': ' (', '）': ') ',
                '“': '"', '”': '"', '‘': "'", '’': "'",
            }
            for k, v in mapping.items():
                text = text.replace(k, v)
            return text

        lines = []
        current_line = ""
        line_start_time = None
        
        if not subtitles:
            return []

        for i, sub in enumerate(subtitles):
            text = sub['text']
            offset = sub['offset'] / 1_000_000  # to seconds

            if line_start_time is None:
                line_start_time = offset

            if self.use_half_width_punctuation:
                text = to_half_width(text)

            # 检查是否需要换行
            # 1. 当前行加上新词后超过最大长度
            # 2. 遇到句号、问号、感叹号、省略号等结束性标点
            # 3. 遇到逗号、分号等，并且当前行长度已接近限制
            is_sentence_end = any(p in text for p in "。？！…")
            is_break_char = any(p in text for p in "，；：")
            
            if (len(current_line) + len(text) > self.srt_max_chars and current_line) or \
               (is_break_char and len(current_line) > self.srt_max_chars * 0.7):
                
                line_end_time = offset
                lines.append({
                    "start": line_start_time,
                    "end": line_end_time,
                    "text": current_line.strip()
                })
                current_line = text
                line_start_time = offset
            else:
                current_line += text

            if is_sentence_end:
                line_end_time = offset + (sub['duration'] / 1_000_000) # 加上最后一个词的持续时间
                lines.append({
                    "start": line_start_time,
                    "end": line_end_time,
                    "text": current_line.strip()
                })
                current_line = ""
                line_start_time = None

        # 添加最后剩余的行
        if current_line:
            last_sub = subtitles[-1]
            line_end_time = (last_sub['offset'] + last_sub['duration']) / 1_000_000
            lines.append({
                "start": line_start_time,
                "end": line_end_time,
                "text": current_line.strip()
            })
            
        return lines

    def create_srt_file(self, audio_path, subtitles_data):
        srt_path = os.path.splitext(audio_path)[0] + ".srt"

        def format_time(seconds):
            td = timedelta(seconds=seconds)
            total_seconds = int(td.total_seconds())
            milliseconds = td.microseconds // 1000
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

        try:
            with open(srt_path, 'w', encoding='utf-8') as f:
                # 处理精确时间戳的字幕
                if isinstance(subtitles_data, list) and subtitles_data:
                    for i, sub in enumerate(subtitles_data):
                        start_time = format_time(sub['start'])
                        end_time = format_time(sub['end'])
                        f.write(f"{i + 1}\n")
                        f.write(f"{start_time} --> {end_time}\n")
                        f.write(f"{sub['text']}\n\n")
                # 兼容旧 API，生成单个字幕块
                elif isinstance(subtitles_data, str):
                    audio = MP3(audio_path)
                    duration = audio.info.length
                    start_time = "00:00:00,000"
                    end_time = format_time(duration)
                    f.write("1\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(subtitles_data + "\n")
                else:
                    self.progress.emit(f"    ✗ [{self.voice}] 无有效的字幕数据可供写入。")
                    return

            self.progress.emit(f"    ✓ [{self.voice}] SRT 字幕已保存到 {os.path.basename(srt_path)}")

        except Exception as e:
            self.progress.emit(f"    ✗ [{self.voice}] 创建 SRT 文件失败: {e}")

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

        self.srt_checkbox = QCheckBox("生成 SRT 字幕文件")
        self.srt_checkbox.setChecked(True)
        self.srt_checkbox.stateChanged.connect(self.update_srt_options_state)

        self.srt_options_layout = QHBoxLayout()
        self.srt_char_count_label = QLabel("每行最大字符数:")
        self.srt_char_count_spinbox = QSpinBox()
        self.srt_char_count_spinbox.setRange(10, 100)
        self.srt_char_count_spinbox.setValue(30)
        self.half_width_punctuation_checkbox = QCheckBox("转为英文半角标点")
        self.srt_options_layout.addWidget(self.srt_char_count_label)
        self.srt_options_layout.addWidget(self.srt_char_count_spinbox)
        self.srt_options_layout.addWidget(self.half_width_punctuation_checkbox)
        
        self.start_button = QPushButton("开始转换")
        self.start_button.clicked.connect(self.start_tts)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        self.layout.addWidget(self.label_voice)
        self.layout.addWidget(self.voice_tree)
        self.layout.addWidget(self.srt_checkbox)
        self.layout.addLayout(self.srt_options_layout)
        self.layout.addWidget(self.start_button)
        self.layout.addWidget(self.log_view)

        self.workers = {}

        self.update_srt_options_state()  # Initial state update

        self.log_view.append("===============================")
        self.log_view.append(" 微软 Edge TTS 文本转语音助手")
        self.log_view.append("===============================")
        self.log_view.append("1. 将需要转换的文本放在本目录的 .txt 文件中")
        self.log_view.append("2. 在下方树状列表中勾选一个或多个语音模型")
        self.log_view.append("3. 点击“开始转换”按钮启动")
        self.log_view.append("")

    def update_srt_options_state(self):
        enabled = self.srt_checkbox.isChecked()
        self.srt_char_count_label.setEnabled(enabled)
        self.srt_char_count_spinbox.setEnabled(enabled)
        self.half_width_punctuation_checkbox.setEnabled(enabled)

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

        generate_srt = self.srt_checkbox.isChecked()
        srt_max_chars = self.srt_char_count_spinbox.value()
        use_half_width_punctuation = self.half_width_punctuation_checkbox.isChecked()

        self.start_button.setEnabled(False)
        self.log_view.append("任务开始...")
        self.log_view.append(f"选中的语音模型: {', '.join(selected_voices)}")
        if generate_srt:
            self.log_view.append(f"将生成 SRT 字幕文件，每行最大 {srt_max_chars} 个字符。")
            if use_half_width_punctuation:
                self.log_view.append("字幕中的标点符号将转换为英文半角。")
        
        self.workers.clear()
        for voice in selected_voices:
            worker = TTSWorker(
                voice=voice, 
                generate_srt=generate_srt, 
                srt_max_chars=srt_max_chars,
                use_half_width_punctuation=use_half_width_punctuation
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
