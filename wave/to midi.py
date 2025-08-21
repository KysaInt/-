import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
import numpy as np
import librosa
import mido
from mido import MidiFile, MidiTrack, Message
import time
from pathlib import Path


class AudioToMidiGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("音频转MIDI工具")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        
        # 变量
        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.hop_length = tk.IntVar(value=256)  # 减小跳跃长度提高精度
        self.frame_threshold = tk.DoubleVar(value=0.01)  # 降低帧阈值以检测更多音符
        self.freq_threshold = tk.DoubleVar(value=0.1)  # 降低频率阈值
        self.tempo = tk.IntVar(value=120)
        self.use_onset_detection = tk.BooleanVar(value=True)  # 使用起始点检测
        self.min_note_duration = tk.DoubleVar(value=0.1)  # 最小音符持续时间
        self.is_processing = False
        
        # 支持的音频格式
        self.supported_formats = ('.wav', '.mp3', '.flac', '.aac', '.ogg', '.m4a')
        
        self.setup_ui()
        
    def setup_ui(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(5, weight=1)
        
        row = 0
        
        # 文件选择部分
        file_frame = ttk.LabelFrame(main_frame, text="目录选择", padding="5")
        file_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        
        # 输入目录
        ttk.Label(file_frame, text="音频文件目录:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(file_frame, textvariable=self.input_dir, width=50).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(file_frame, text="浏览", command=self.browse_input_dir).grid(row=0, column=2)
        
        # 输出目录
        ttk.Label(file_frame, text="MIDI输出目录:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        ttk.Entry(file_frame, textvariable=self.output_dir, width=50).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 5), pady=(5, 0))
        ttk.Button(file_frame, text="浏览", command=self.browse_output_dir).grid(row=1, column=2, pady=(5, 0))
        
        row += 1
        
        # 参数设置部分
        param_frame = ttk.LabelFrame(main_frame, text="转换参数", padding="5")
        param_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        param_frame.columnconfigure(1, weight=1)
        
        # 跳跃长度
        ttk.Label(param_frame, text="跳跃长度:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        hop_frame = ttk.Frame(param_frame)
        hop_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Entry(hop_frame, textvariable=self.hop_length, width=10).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(hop_frame, text="(默认: 256, 值越小精度越高但处理越慢)").grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # 帧阈值
        ttk.Label(param_frame, text="帧阈值:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        frame_thres_frame = ttk.Frame(param_frame)
        frame_thres_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 5), pady=(5, 0))
        ttk.Entry(frame_thres_frame, textvariable=self.frame_threshold, width=10).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(frame_thres_frame, text="(默认: 0.01, 音符检测的最小强度，值越小检测越敏感)").grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # 频率阈值
        ttk.Label(param_frame, text="频率阈值:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        freq_thres_frame = ttk.Frame(param_frame)
        freq_thres_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(0, 5), pady=(5, 0))
        ttk.Entry(freq_thres_frame, textvariable=self.freq_threshold, width=10).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(freq_thres_frame, text="(默认: 0.1, 音高检测的置信度阈值，值越小检测越多音符)").grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # 节拍速度
        ttk.Label(param_frame, text="节拍速度 (BPM):").grid(row=3, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        tempo_frame = ttk.Frame(param_frame)
        tempo_frame.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(0, 5), pady=(5, 0))
        ttk.Entry(tempo_frame, textvariable=self.tempo, width=10).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(tempo_frame, text="(默认: 120, 影响MIDI时间分辨率)").grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        # 起始点检测
        onset_frame = ttk.Frame(param_frame)
        onset_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=(0, 5), pady=(5, 0))
        ttk.Checkbutton(onset_frame, text="使用起始点检测 (提高音符准确性)", 
                       variable=self.use_onset_detection).grid(row=0, column=0, sticky=tk.W)
        
        # 最小音符持续时间
        ttk.Label(param_frame, text="最小音符时长 (秒):").grid(row=5, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        duration_frame = ttk.Frame(param_frame)
        duration_frame.grid(row=5, column=1, sticky=(tk.W, tk.E), padx=(0, 5), pady=(5, 0))
        ttk.Entry(duration_frame, textvariable=self.min_note_duration, width=10).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(duration_frame, text="(默认: 0.1, 过滤掉过短的音符)").grid(row=0, column=1, sticky=tk.W, padx=(5, 0))
        
        row += 1
        
        # 控制按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=(0, 10))
        
        self.convert_button = ttk.Button(button_frame, text="开始转换", command=self.start_conversion)
        self.convert_button.grid(row=0, column=0, padx=(0, 10))
        
        self.stop_button = ttk.Button(button_frame, text="停止转换", command=self.stop_conversion, state='disabled')
        self.stop_button.grid(row=0, column=1, padx=(0, 10))
        
        ttk.Button(button_frame, text="清空日志", command=self.clear_log).grid(row=0, column=2)
        
        row += 1
        
        # 进度条
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.progress_label = ttk.Label(progress_frame, text="准备就绪")
        self.progress_label.grid(row=0, column=1)
        
        row += 1
        
        # 日志显示
        log_frame = ttk.LabelFrame(main_frame, text="处理日志", padding="5")
        log_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # 创建文本框和滚动条
        self.log_text = tk.Text(log_frame, height=15, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # 设置默认目录为当前程序所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.input_dir.set(current_dir)
        self.output_dir.set(current_dir)
        
    def browse_input_dir(self):
        """浏览输入目录"""
        directory = filedialog.askdirectory(title="选择音频文件目录")
        if directory:
            self.input_dir.set(directory)
            
    def browse_output_dir(self):
        """浏览输出目录"""
        directory = filedialog.askdirectory(title="选择MIDI输出目录")
        if directory:
            self.output_dir.set(directory)
            
    def log_message(self, message):
        """在日志区域显示消息"""
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
        
    def update_progress(self, current, total, message=""):
        """更新进度条"""
        if total > 0:
            progress = (current / total) * 100
            self.progress_var.set(progress)
            progress_text = f"{current}/{total}"
            if message:
                progress_text += f" - {message}"
            self.progress_label.config(text=progress_text)
        self.root.update_idletasks()
        
    def get_audio_files(self, directory):
        """获取目录中的所有音频文件"""
        audio_files = []
        try:
            for file_path in Path(directory).rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in self.supported_formats:
                    audio_files.append(str(file_path))
            return audio_files
        except Exception as e:
            self.log_message(f"扫描目录时出错: {str(e)}")
            return []
            
    def audio_to_midi(self, audio_path, output_path):
        """将音频文件转换为MIDI"""
        try:
            self.log_message(f"正在处理: {os.path.basename(audio_path)}")
            
            # 加载音频文件
            y, sr = librosa.load(audio_path, sr=22050)  # 使用固定采样率以提高性能
            audio_duration = len(y) / sr
            self.log_message(f"音频长度: {audio_duration:.2f} 秒, 采样率: {sr} Hz")
            
            # 参数设置
            hop_length = self.hop_length.get()
            frame_threshold = self.frame_threshold.get()
            freq_threshold = self.freq_threshold.get()
            min_note_duration = self.min_note_duration.get()
            use_onset = self.use_onset_detection.get()
            
            self.log_message("正在进行音高检测...")
            
            # 使用更准确的音高检测方法
            if use_onset:
                # 1. 检测音符起始点
                onset_frames = librosa.onset.onset_detect(y=y, sr=sr, hop_length=hop_length)
                onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)
                self.log_message(f"检测到 {len(onset_times)} 个音符起始点")
                
                # 2. 在起始点附近进行音高检测
                notes = []
                
                for i, onset_time in enumerate(onset_times):
                    if not self.is_processing:
                        return False
                    
                    # 确定音符的结束时间
                    if i < len(onset_times) - 1:
                        end_time = onset_times[i + 1]
                    else:
                        end_time = audio_duration
                    
                    # 提取音符片段
                    start_sample = int(onset_time * sr)
                    end_sample = int(end_time * sr)
                    note_segment = y[start_sample:end_sample]
                    
                    if len(note_segment) > 0:
                        # 使用YIN算法进行基频检测
                        f0 = librosa.yin(note_segment, fmin=80, fmax=2000, sr=sr)
                        
                        # 取中位数作为该音符的音高
                        valid_f0 = f0[f0 > 0]
                        if len(valid_f0) > 0:
                            median_f0 = np.median(valid_f0)
                            midi_note = librosa.hz_to_midi(median_f0)
                            midi_note = int(np.round(midi_note))
                            
                            # 确保在有效范围内
                            if 21 <= midi_note <= 108:
                                duration = end_time - onset_time
                                if duration >= min_note_duration:
                                    notes.append({
                                        'start': onset_time,
                                        'end': end_time,
                                        'pitch': midi_note,
                                        'duration': duration
                                    })
                
            else:
                # 传统的逐帧检测方法
                pitches, magnitudes = librosa.piptrack(y=y, sr=sr, hop_length=hop_length, 
                                                     threshold=frame_threshold, fmin=80, fmax=2000)
                
                # 提取主要音高序列
                pitch_sequence = []
                time_sequence = []
                
                for i in range(pitches.shape[1]):
                    if not self.is_processing:
                        return False
                    
                    frame_pitches = pitches[:, i]
                    frame_magnitudes = magnitudes[:, i]
                    
                    max_mag_idx = np.argmax(frame_magnitudes)
                    if frame_magnitudes[max_mag_idx] > freq_threshold:
                        freq = frame_pitches[max_mag_idx]
                        if freq > 0:
                            midi_note = librosa.hz_to_midi(freq)
                            midi_note = int(np.round(midi_note))
                            if 21 <= midi_note <= 108:
                                pitch_sequence.append(midi_note)
                            else:
                                pitch_sequence.append(None)
                        else:
                            pitch_sequence.append(None)
                    else:
                        pitch_sequence.append(None)
                    
                    time_sequence.append(i * hop_length / sr)
                
                # 将逐帧数据转换为音符数据
                notes = []
                current_pitch = None
                note_start = 0
                
                for i, (time_sec, pitch) in enumerate(zip(time_sequence, pitch_sequence)):
                    if pitch != current_pitch:
                        # 结束之前的音符
                        if current_pitch is not None:
                            duration = time_sec - note_start
                            if duration >= min_note_duration:
                                notes.append({
                                    'start': note_start,
                                    'end': time_sec,
                                    'pitch': current_pitch,
                                    'duration': duration
                                })
                        
                        # 开始新音符
                        if pitch is not None:
                            note_start = time_sec
                        
                        current_pitch = pitch
                
                # 处理最后一个音符
                if current_pitch is not None:
                    duration = audio_duration - note_start
                    if duration >= min_note_duration:
                        notes.append({
                            'start': note_start,
                            'end': audio_duration,
                            'pitch': current_pitch,
                            'duration': duration
                        })
            
            self.log_message(f"检测到 {len(notes)} 个有效音符")
            
            # 创建MIDI文件
            mid = MidiFile()
            track = MidiTrack()
            mid.tracks.append(track)
            
            # 设置节拍速度
            tempo_bpm = self.tempo.get()
            tempo = mido.bpm2tempo(tempo_bpm)
            track.append(mido.MetaMessage('set_tempo', tempo=tempo))
            
            # 计算时间分辨率
            ticks_per_beat = mid.ticks_per_beat
            ticks_per_second = (tempo_bpm * ticks_per_beat) / 60
            
            self.log_message("正在生成MIDI事件...")
            
            if not notes:
                self.log_message("未检测到任何有效音符")
                # 创建一个空的MIDI文件，但保持正确的长度
                end_time_ticks = int(audio_duration * ticks_per_second)
                track.append(Message('note_on', channel=0, note=60, velocity=0, time=end_time_ticks))
                mid.save(output_path)
                return True
            
            # 按时间排序音符
            notes.sort(key=lambda x: x['start'])
            
            # 添加音符事件
            current_time_ticks = 0
            
            for note in notes:
                if not self.is_processing:
                    return False
                
                start_ticks = int(note['start'] * ticks_per_second)
                end_ticks = int(note['end'] * ticks_per_second)
                
                # Note On 事件
                delta_time = start_ticks - current_time_ticks
                track.append(Message('note_on', channel=0, note=note['pitch'], velocity=64, time=delta_time))
                
                # Note Off 事件
                note_duration_ticks = end_ticks - start_ticks
                track.append(Message('note_off', channel=0, note=note['pitch'], velocity=64, time=note_duration_ticks))
                
                current_time_ticks = end_ticks
            
            # 确保MIDI文件长度与音频文件一致
            final_time_ticks = int(audio_duration * ticks_per_second)
            remaining_time = final_time_ticks - current_time_ticks
            
            if remaining_time > 0:
                # 添加一个无声的结尾
                track.append(Message('note_on', channel=0, note=60, velocity=0, time=remaining_time))
            
            # 保存MIDI文件
            mid.save(output_path)
            
            # 验证MIDI文件长度
            midi_length = mid.length
            self.log_message(f"转换完成! 音频长度: {audio_duration:.2f}s, MIDI长度: {midi_length:.2f}s")
            self.log_message(f"长度误差: {abs(audio_duration - midi_length):.3f}s")
            
            return True
            
        except Exception as e:
            self.log_message(f"转换失败: {str(e)}")
            import traceback
            self.log_message(f"详细错误: {traceback.format_exc()}")
            return False
            
    def conversion_thread(self):
        """转换线程"""
        try:
            input_directory = self.input_dir.get()
            output_directory = self.output_dir.get()
            
            if not input_directory or not os.path.exists(input_directory):
                self.log_message("错误: 请选择有效的音频文件目录")
                return
                
            if not output_directory:
                self.log_message("错误: 请选择输出目录")
                return
                
            # 创建输出目录
            os.makedirs(output_directory, exist_ok=True)
            
            # 获取所有音频文件
            audio_files = self.get_audio_files(input_directory)
            
            if not audio_files:
                self.log_message("在指定目录中未找到支持的音频文件")
                self.log_message(f"支持的格式: {', '.join(self.supported_formats)}")
                return
                
            self.log_message(f"找到 {len(audio_files)} 个音频文件")
            
            # 转换每个文件
            successful = 0
            failed = 0
            
            for i, audio_file in enumerate(audio_files):
                if not self.is_processing:
                    self.log_message("转换已停止")
                    break
                    
                # 更新进度
                self.update_progress(i, len(audio_files), f"处理中: {os.path.basename(audio_file)}")
                
                # 生成输出文件名
                base_name = os.path.splitext(os.path.basename(audio_file))[0]
                output_file = os.path.join(output_directory, f"{base_name}.mid")
                
                # 转换文件
                if self.audio_to_midi(audio_file, output_file):
                    successful += 1
                else:
                    failed += 1
                    
            # 更新最终进度
            self.update_progress(len(audio_files), len(audio_files), "完成")
            self.log_message(f"转换完成! 成功: {successful}, 失败: {failed}")
            
        except Exception as e:
            self.log_message(f"转换过程中发生错误: {str(e)}")
        finally:
            self.is_processing = False
            self.convert_button.config(state='normal')
            self.stop_button.config(state='disabled')
            
    def start_conversion(self):
        """开始转换"""
        if self.is_processing:
            return
            
        self.is_processing = True
        self.convert_button.config(state='disabled')
        self.stop_button.config(state='normal')
        
        # 清空之前的日志
        self.clear_log()
        self.log_message("开始批量转换音频文件...")
        
        # 在新线程中执行转换
        thread = threading.Thread(target=self.conversion_thread)
        thread.daemon = True
        thread.start()
        
    def stop_conversion(self):
        """停止转换"""
        self.is_processing = False
        self.log_message("正在停止转换...")


def main():
    # 检查依赖
    try:
        import librosa
        import mido
    except ImportError as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("依赖缺失", 
                           f"缺少必要的依赖库: {str(e)}\n\n"
                           "请运行 install_dependencies.py 安装依赖")
        return
    
    root = tk.Tk()
    app = AudioToMidiGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()