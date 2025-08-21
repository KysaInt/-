import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
from pydub import AudioSegment
from pydub.silence import split_on_silence
import numpy as np


class AudioSplitterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("音频切分工具")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        # 变量
        self.input_file = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.fade_in_enabled = tk.BooleanVar(value=True)
        self.fade_out_enabled = tk.BooleanVar(value=True)
        self.fade_duration = tk.DoubleVar(value=0.1)  # 秒
        self.silence_threshold = tk.DoubleVar(value=-40.0)  # dB
        self.min_silence_len = tk.IntVar(value=500)  # 毫秒
        self.keep_silence = tk.IntVar(value=100)  # 毫秒
        self.min_segment_length = tk.DoubleVar(value=1.0)  # 秒
        
        self.setup_ui()
        
    def setup_ui(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        row = 0
        
        # 文件选择部分
        file_frame = ttk.LabelFrame(main_frame, text="文件选择", padding="5")
        file_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        
        # 输入文件
        ttk.Label(file_frame, text="输入音频文件:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(file_frame, textvariable=self.input_file, width=50).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(file_frame, text="浏览", command=self.browse_input_file).grid(row=0, column=2)
        
        # 输出目录
        ttk.Label(file_frame, text="输出目录:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        ttk.Entry(file_frame, textvariable=self.output_dir, width=50).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 5), pady=(5, 0))
        ttk.Button(file_frame, text="浏览", command=self.browse_output_dir).grid(row=1, column=2, pady=(5, 0))
        
        row += 1
        
        # 切分设置部分
        split_frame = ttk.LabelFrame(main_frame, text="切分设置", padding="5")
        split_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        split_frame.columnconfigure(1, weight=1)
        
        # 响度阈值
        ttk.Label(split_frame, text="静音阈值 (dB):").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        silence_frame = ttk.Frame(split_frame)
        silence_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        silence_scale = ttk.Scale(silence_frame, from_=-60, to=-10, variable=self.silence_threshold, 
                                orient=tk.HORIZONTAL, length=200)
        silence_scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
        silence_frame.columnconfigure(0, weight=1)
        ttk.Label(silence_frame, textvariable=self.silence_threshold).grid(row=0, column=1, padx=(5, 0))
        
        # 最小静音长度
        ttk.Label(split_frame, text="最小静音长度 (ms):").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        ttk.Spinbox(split_frame, from_=100, to=2000, textvariable=self.min_silence_len, 
                   width=10).grid(row=1, column=1, sticky=tk.W, pady=(5, 0))
        
        # 保留静音长度
        ttk.Label(split_frame, text="保留静音长度 (ms):").grid(row=2, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        ttk.Spinbox(split_frame, from_=0, to=500, textvariable=self.keep_silence, 
                   width=10).grid(row=2, column=1, sticky=tk.W, pady=(5, 0))
        
        # 最小片段长度
        ttk.Label(split_frame, text="最小片段长度 (s):").grid(row=3, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        ttk.Spinbox(split_frame, from_=0.5, to=10.0, increment=0.1, textvariable=self.min_segment_length, 
                   width=10).grid(row=3, column=1, sticky=tk.W, pady=(5, 0))
        
        row += 1
        
        # 淡入淡出设置部分
        fade_frame = ttk.LabelFrame(main_frame, text="淡入淡出设置", padding="5")
        fade_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        fade_frame.columnconfigure(1, weight=1)
        
        # 淡入开关
        ttk.Checkbutton(fade_frame, text="启用淡入", variable=self.fade_in_enabled).grid(row=0, column=0, sticky=tk.W)
        
        # 淡出开关
        ttk.Checkbutton(fade_frame, text="启用淡出", variable=self.fade_out_enabled).grid(row=0, column=1, sticky=tk.W)
        
        # 过渡时长
        ttk.Label(fade_frame, text="过渡时长 (s):").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        fade_duration_frame = ttk.Frame(fade_frame)
        fade_duration_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(5, 0))
        fade_duration_frame.columnconfigure(0, weight=1)
        ttk.Scale(fade_duration_frame, from_=0.01, to=1.0, variable=self.fade_duration, 
                 orient=tk.HORIZONTAL, length=150).grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Label(fade_duration_frame, textvariable=self.fade_duration).grid(row=0, column=1, padx=(5, 0))
        
        row += 1
        
        # 操作按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="开始切分", command=self.start_splitting).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="清除", command=self.clear_fields).pack(side=tk.LEFT)
        
        row += 1
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 5))
        
        row += 1
        
        # 状态标签
        self.status_label = ttk.Label(main_frame, text="就绪")
        self.status_label.grid(row=row, column=0, columnspan=2, pady=(0, 10))
        
        row += 1
        
        # 日志文本框
        log_frame = ttk.LabelFrame(main_frame, text="日志", padding="5")
        log_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(row, weight=1)
        
        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
    def browse_input_file(self):
        filename = filedialog.askopenfilename(
            title="选择音频文件",
            filetypes=[
                ("音频文件", "*.mp3 *.wav *.flac *.aac *.ogg *.m4a"),
                ("所有文件", "*.*")
            ]
        )
        if filename:
            self.input_file.set(filename)
            # 自动设置输出目录为输入文件所在目录
            if not self.output_dir.get():
                self.output_dir.set(os.path.dirname(filename))
    
    def browse_output_dir(self):
        dirname = filedialog.askdirectory(title="选择输出目录")
        if dirname:
            self.output_dir.set(dirname)
    
    def clear_fields(self):
        self.input_file.set("")
        self.output_dir.set("")
        self.log_text.delete(1.0, tk.END)
        self.progress_var.set(0)
        self.status_label.config(text="就绪")
    
    def log_message(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def start_splitting(self):
        if not self.input_file.get():
            messagebox.showerror("错误", "请选择输入音频文件")
            return
        
        if not self.output_dir.get():
            messagebox.showerror("错误", "请选择输出目录")
            return
        
        if not os.path.exists(self.input_file.get()):
            messagebox.showerror("错误", "输入文件不存在")
            return
        
        if not os.path.exists(self.output_dir.get()):
            try:
                os.makedirs(self.output_dir.get())
            except Exception as e:
                messagebox.showerror("错误", f"无法创建输出目录: {e}")
                return
        
        # 在新线程中执行切分操作
        thread = threading.Thread(target=self.split_audio)
        thread.daemon = True
        thread.start()
    
    def split_audio(self):
        try:
            self.status_label.config(text="正在加载音频文件...")
            self.progress_var.set(10)
            
            # 加载音频文件
            audio = AudioSegment.from_file(self.input_file.get())
            self.log_message(f"成功加载音频文件: {self.input_file.get()}")
            self.log_message(f"音频时长: {len(audio) / 1000:.2f} 秒")
            
            self.status_label.config(text="正在分析音频...")
            self.progress_var.set(30)
            
            # 使用静音检测切分音频
            chunks = split_on_silence(
                audio,
                min_silence_len=self.min_silence_len.get(),
                silence_thresh=self.silence_threshold.get(),
                keep_silence=self.keep_silence.get()
            )
            
            self.log_message(f"检测到 {len(chunks)} 个音频片段")
            
            if not chunks:
                self.log_message("未检测到音频片段，请调整切分参数")
                self.status_label.config(text="切分完成")
                return
            
            # 过滤过短的片段
            min_length_ms = int(self.min_segment_length.get() * 1000)
            filtered_chunks = [chunk for chunk in chunks if len(chunk) >= min_length_ms]
            
            if len(filtered_chunks) < len(chunks):
                removed_count = len(chunks) - len(filtered_chunks)
                self.log_message(f"移除了 {removed_count} 个过短的片段")
            
            chunks = filtered_chunks
            
            if not chunks:
                self.log_message("所有片段都过短，请调整最小片段长度")
                self.status_label.config(text="切分完成")
                return
            
            self.status_label.config(text="正在保存音频片段...")
            
            # 获取输入文件名（不含扩展名）
            input_basename = os.path.splitext(os.path.basename(self.input_file.get()))[0]
            
            # 保存每个片段
            for i, chunk in enumerate(chunks):
                progress = 30 + (i / len(chunks)) * 60
                self.progress_var.set(progress)
                
                # 应用淡入淡出效果
                if self.fade_in_enabled.get() or self.fade_out_enabled.get():
                    fade_ms = int(self.fade_duration.get() * 1000)
                    fade_ms = min(fade_ms, len(chunk) // 4)  # 淡入淡出时间不超过片段长度的1/4
                    
                    if self.fade_in_enabled.get() and fade_ms > 0:
                        chunk = chunk.fade_in(fade_ms)
                    
                    if self.fade_out_enabled.get() and fade_ms > 0:
                        chunk = chunk.fade_out(fade_ms)
                
                # 生成输出文件名
                output_filename = f"{input_basename}_part_{i+1:03d}.wav"
                output_path = os.path.join(self.output_dir.get(), output_filename)
                
                # 导出音频片段
                chunk.export(output_path, format="wav")
                
                duration = len(chunk) / 1000
                self.log_message(f"保存片段 {i+1}: {output_filename} (时长: {duration:.2f}秒)")
            
            self.progress_var.set(100)
            self.status_label.config(text="切分完成")
            self.log_message(f"音频切分完成！共生成 {len(chunks)} 个文件")
            
            messagebox.showinfo("完成", f"音频切分完成！\n共生成 {len(chunks)} 个音频文件")
            
        except Exception as e:
            self.log_message(f"错误: {str(e)}")
            self.status_label.config(text="切分失败")
            messagebox.showerror("错误", f"音频切分失败: {str(e)}")
        finally:
            self.progress_var.set(0)


def main():
    root = tk.Tk()
    app = AudioSplitterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
