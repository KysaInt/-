import sys
import librosa
import numpy as np
from pydub import AudioSegment
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QThread, Signal
import sounddevice as sd
import soundfile as sf
import os

class Worker(QThread):
    """
    Worker thread for long-running audio processing tasks.
    """
    finished = Signal(list)
    progress = Signal(str)

    def __init__(self, audio_file, target_beats, target_duration):
        super().__init__()
        self.audio_file = audio_file
        self.target_beats = int(target_beats)
        self.target_duration = float(target_duration)
        self.output_dir = "output_slices"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def run(self):
        try:
            self.progress.emit("正在加载音频文件...")
            y, sr = librosa.load(self.audio_file, sr=None)
            
            self.progress.emit("正在分析节拍...")
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)

            if len(beat_times) < self.target_beats:
                self.progress.emit(f"错误：检测到的节拍数 ({len(beat_times)}) 少于目标节拍数 ({self.target_beats})。")
                self.finished.emit([])
                return

            # Calculate the duration of the original segment of target_beats
            original_segment_duration = beat_times[self.target_beats - 1] - beat_times[0]
            
            # Calculate the required speed change
            # We need to fit original_segment_duration into target_duration
            # For the first segment. We'll apply this to the whole audio.
            # Let's find the duration of a typical segment of target_beats
            beat_durations = np.diff(beat_times)
            if len(beat_durations) > 0:
                avg_beat_duration = np.mean(beat_durations)
                original_slice_duration = avg_beat_duration * (self.target_beats -1)
            else: # If only one beat detected, can't calculate duration
                self.progress.emit("错误: 无法确定节拍间隔。")
                self.finished.emit([])
                return

            # Calculate speedup factor
            # If the audio needs to be 20s long for 5 beats, the new duration between beats is 20/4 = 5s
            # The original average duration is avg_beat_duration
            new_avg_beat_duration = self.target_duration / (self.target_beats)
            # The rate is how much faster we need to play.
            # If new duration is shorter, rate > 1.
            rate = avg_beat_duration / new_avg_beat_duration
            
            self.progress.emit(f"原始BPM: {tempo:.2f}, 原始平均节拍时长: {avg_beat_duration:.2f}s")
            self.progress.emit(f"目标节拍时长: {new_avg_beat_duration:.2f}s, 计算速率: {rate:.2f}x")

            self.progress.emit("正在应用速率变更...")
            audio = AudioSegment.from_file(self.audio_file)
            
            # speedup uses playback_speed, so a value of 2.0 makes it twice as fast.
            sped_up_audio = audio.speedup(playback_speed=rate)
            
            # The beat times also scale down by the same rate
            new_beat_times = beat_times / rate

            output_files = []
            self.progress.emit("正在切分音频...")
            num_possible_slices = len(new_beat_times) - self.target_beats + 1
            
            for i in range(num_possible_slices):
                start_beat_index = i
                end_beat_index = i + self.target_beats
                
                # Get start time from the first beat of the slice
                start_time_ms = new_beat_times[start_beat_index] * 1000
                
                # The end time should be start_time + target_duration
                # But to be more precise, let's calculate it from the beat times if possible
                if end_beat_index < len(new_beat_times):
                    end_time_ms = new_beat_times[end_beat_index] * 1000
                else:
                    # If it's the last possible slice, extrapolate the end time
                    end_time_ms = new_beat_times[-1] * 1000 + (new_avg_beat_duration * 1000)

                # Ensure the slice duration is close to the target duration
                actual_slice_duration_ms = end_time_ms - start_time_ms
                
                # Let's just cut based on the target duration from the start beat
                end_time_ms = start_time_ms + self.target_duration * 1000

                slice_audio = sped_up_audio[start_time_ms:end_time_ms]
                
                output_filename = os.path.join(self.output_dir, f"slice_{i+1:03d}.wav")
                slice_audio.export(output_filename, format="wav")
                
                output_files.append({
                    "path": output_filename,
                    "start_beat": start_beat_index + 1,
                    "end_beat": end_beat_index,
                    "duration": len(slice_audio) / 1000.0
                })
                self.progress.emit(f"已生成片段 {i+1}/{num_possible_slices}")

            self.finished.emit(output_files)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.progress.emit(f"❌ 处理失败: {type(e).__name__} - {str(e)}")
            # Print detailed error to console for debugging
            print("=" * 50)
            print("音频处理失败 - 详细错误信息:")
            print(error_details)
            print("=" * 50)
            self.finished.emit([])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("智能节拍切片器")
        self.setGeometry(100, 100, 800, 600)

        self.audio_file = None
        self.playing_process = None

        # Main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # --- Top Controls ---
        top_layout = QHBoxLayout()
        self.select_file_btn = QPushButton("选择音频文件")
        self.select_file_btn.clicked.connect(self.select_audio_file)
        self.file_label = QLabel("未选择文件")
        self.file_label.setAlignment(Qt.AlignLeft)
        top_layout.addWidget(self.select_file_btn)
        top_layout.addWidget(self.file_label, 1)
        layout.addLayout(top_layout)

        # --- Info Display ---
        self.info_label = QLabel("请先选择一个音频文件并进行分析。")
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)

        # --- Processing Controls ---
        process_layout = QHBoxLayout()
        self.beats_input = QLineEdit()
        self.beats_input.setPlaceholderText("目标节拍数 (e.g., 5)")
        self.duration_input = QLineEdit()
        self.duration_input.setPlaceholderText("目标总时长 (秒, e.g., 20)")
        self.process_btn = QPushButton("开始处理")
        self.process_btn.clicked.connect(self.start_processing)
        self.process_btn.setEnabled(False)
        
        process_layout.addWidget(QLabel("节拍数:"))
        process_layout.addWidget(self.beats_input)
        process_layout.addWidget(QLabel("总时长(s):"))
        process_layout.addWidget(self.duration_input)
        process_layout.addWidget(self.process_btn)
        layout.addLayout(process_layout)

        # --- Results ---
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.play_slice)
        layout.addWidget(QLabel("处理结果 (双击播放):"))
        layout.addWidget(self.results_list)
        
        # --- Status Bar ---
        self.status_label = QLabel("准备就绪")
        layout.addWidget(self.status_label)

    def select_audio_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择音频文件", "", "音频文件 (*.wav *.mp3 *.flac)")
        if file_path:
            self.audio_file = file_path
            self.file_label.setText(os.path.basename(file_path))
            self.analyze_audio()

    def analyze_audio(self):
        if not self.audio_file:
            return
        try:
            self.status_label.setText("正在分析音频...")
            self.info_label.setText("正在分析音频，请稍候...")
            QApplication.processEvents() # Update UI
            y, sr = librosa.load(self.audio_file, sr=None)
            duration = librosa.get_duration(y=y, sr=sr)
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)
            
            self.info_label.setText(
                f"时长: {duration:.2f} 秒\n"
                f"预估 BPM: {tempo:.2f}\n"
                f"检测到节拍数: {len(beat_times)}"
            )
            self.process_btn.setEnabled(True)
            self.status_label.setText("分析完成，可以开始处理。")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.info_label.setText(
                f"❌ 分析失败！\n\n"
                f"错误类型: {type(e).__name__}\n"
                f"错误信息: {str(e)}\n\n"
                f"请检查:\n"
                f"1. 音频文件是否损坏\n"
                f"2. 音频格式是否支持\n"
                f"3. 文件路径是否包含特殊字符"
            )
            self.status_label.setText(f"❌ 分析错误: {str(e)}")
            self.process_btn.setEnabled(False)
            # Print detailed error to console for debugging
            print("=" * 50)
            print("音频分析失败 - 详细错误信息:")
            print(error_details)
            print("=" * 50)

    def start_processing(self):
        target_beats = self.beats_input.text()
        target_duration = self.duration_input.text()

        if not self.audio_file or not target_beats or not target_duration:
            self.status_label.setText("错误: 请确保已选择文件并输入节拍数和时长。")
            return

        try:
            int(target_beats)
            float(target_duration)
        except ValueError:
            self.status_label.setText("错误: 节拍数和时长必须是有效的数字。")
            return

        self.process_btn.setEnabled(False)
        self.results_list.clear()
        self.status_label.setText("正在处理中...")

        self.worker = Worker(self.audio_file, target_beats, target_duration)
        self.worker.progress.connect(self.update_status)
        self.worker.finished.connect(self.processing_finished)
        self.worker.start()

    def update_status(self, message):
        self.status_label.setText(message)

    def processing_finished(self, output_files):
        self.status_label.setText(f"处理完成！生成了 {len(output_files)} 个片段。")
        self.process_btn.setEnabled(True)
        
        if not output_files:
            item = QListWidgetItem("没有找到符合条件的片段。")
            self.results_list.addItem(item)
        else:
            for f_info in output_files:
                item_text = (f"{os.path.basename(f_info['path'])} | "
                             f"节拍: {f_info['start_beat']}-{f_info['end_beat']} | "
                             f"时长: {f_info['duration']:.2f}s")
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, f_info['path']) # Store file path in the item
                self.results_list.addItem(item)

    def play_slice(self, item):
        file_path = item.data(Qt.UserRole)
        if file_path and os.path.exists(file_path):
            try:
                self.status_label.setText(f"正在播放: {os.path.basename(file_path)}")
                data, fs = sf.read(file_path, dtype='float32')
                sd.play(data, fs)
                # sd.wait() # This would block the GUI, not ideal
            except Exception as e:
                self.status_label.setText(f"播放失败: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
