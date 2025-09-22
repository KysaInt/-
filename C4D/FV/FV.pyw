# -*- coding: utf-8 -*-
"""
跨文件夹PNG序列查看管理器
递归扫描整个目录，自动识别序列名，统计渲染完整度
支持分组渲染的帧分布查看，忽略通道图只统计RGB主文件
"""

import os
import sys
import re
import subprocess
import importlib.util
from collections import defaultdict
import math
import ctypes
from datetime import datetime

def check_and_install_packages():
    """检查并安装所需的包"""
    required_packages = {
        'pywinstyles': 'pywinstyles',
        'PIL': 'Pillow'
    }

    missing_packages = []

    # 检查每个包是否已安装
    for import_name, package_name in required_packages.items():
        if importlib.util.find_spec(import_name) is None:
            missing_packages.append(package_name)

    if missing_packages:
        # 如果有缺失的包，显示GUI提示
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口

            packages_str = '\n'.join([f"  • {pkg}" for pkg in missing_packages])
            message = f"检测到缺少以下依赖包:\n\n{packages_str}\n\n是否现在自动安装这些包？"

            if messagebox.askyesno("缺少依赖包", message):
                # 创建进度窗口
                progress_window = tk.Toplevel()
                progress_window.title("安装依赖包")
                progress_window.geometry("400x200")
                progress_window.resizable(False, False)

                # 居中显示
                progress_window.update_idletasks()
                x = (progress_window.winfo_screenwidth() // 2) - (400 // 2)
                y = (progress_window.winfo_screenheight() // 2) - (200 // 2)
                progress_window.geometry(f"400x200+{x}+{y}")

                label = tk.Label(progress_window, text="正在安装依赖包，请稍候...", font=('Arial', 12))
                label.pack(pady=20)

                text_widget = tk.Text(progress_window, height=8, width=50)
                text_widget.pack(pady=10, padx=20, fill='both', expand=True)

                progress_window.update()

                success = True
                for package in missing_packages:
                    try:
                        text_widget.insert('end', f"正在安装 {package}...\n")
                        text_widget.see('end')
                        progress_window.update()

                        subprocess.check_call([sys.executable, "-m", "pip", "install", package],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                        text_widget.insert('end', f"✓ {package} 安装成功\n")
                        text_widget.see('end')
                        progress_window.update()
                    except subprocess.CalledProcessError:
                        text_widget.insert('end', f"✗ {package} 安装失败\n")
                        text_widget.see('end')
                        progress_window.update()
                        success = False

                if success:
                    text_widget.insert('end', "\n所有依赖包安装完成！")
                    messagebox.showinfo("安装完成", "所有依赖包安装成功！\n程序将继续启动。")
                else:
                    messagebox.showerror("安装失败", "部分依赖包安装失败！\n请检查网络连接或手动安装。")

                progress_window.destroy()
                root.destroy()
                return success
            else:
                root.destroy()
                return False
        except ImportError:
            # 如果tkinter不可用，回退到命令行模式
            print("检测到缺少以下依赖包:")
            for package in missing_packages:
                print(f"  - {package}")

            print("\n正在自动安装缺少的包...")

            for package in missing_packages:
                try:
                    print(f"正在安装 {package}...")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    print(f"✓ {package} 安装成功")
                except subprocess.CalledProcessError as e:
                    print(f"✗ {package} 安装失败: {e}")
                    print("请手动安装此包或检查网络连接")
                    return False

            print("\n所有依赖包安装完成！")

    return True

# 执行依赖检查
print("正在检查依赖包...")
if not check_and_install_packages():
    print("依赖安装失败或用户取消，程序退出")
    input("按任意键退出...")
    sys.exit(1)

print("依赖检查完成，启动程序...")

# 导入所需模块
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, Canvas, Scrollbar, font as tkfont
    import pywinstyles
    import winreg
    from PIL import Image, ImageTk, ImageDraw
    import tempfile
    # mf.py 所需的额外导入
    import shutil
    import time
    import threading
    import msvcrt
    import psutil
    import json
    from datetime import datetime
    from pathlib import Path
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有依赖包都已正确安装")
    input("按任意键退出...")
    sys.exit(1)

# 嵌入 mf.py 的代码
class C4DRenderMonitor:
    def __init__(self):
        self.c4d_process_names = [
            'CINEMA 4D.exe',
            'Cinema 4D.exe', 
            'c4d.exe',
            'Commandline.exe',
            'TeamRender Client.exe',
            'TeamRender Server.exe'
        ]
        self.is_rendering = False
        self.last_render_status = -1
        self.last_check_time = 0
        self.cached_processes = []
        self.cache_duration = 0.5
        
    def check_c4d_processes(self):
        current_time = time.time()
        
        if current_time - self.last_check_time < self.cache_duration:
            return self.cached_processes
        
        c4d_processes = []
        
        try:
            for process in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                process_name = process.info['name']
                if any(c4d_name.lower() in process_name.lower() for c4d_name in self.c4d_process_names):
                    c4d_processes.append({
                        'pid': process.info['pid'],
                        'name': process_name,
                        'cpu_percent': process.info['cpu_percent'],
                        'memory': process.info['memory_info'].rss if process.info['memory_info'] else 0
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        
        self.cached_processes = c4d_processes
        self.last_check_time = current_time
        
        return c4d_processes
    
    def is_rendering_active(self, processes):
        if not processes:
            return False
        
        high_cpu_processes = [p for p in processes if p['cpu_percent'] > 20.0]
        
        commandline_processes = [p for p in processes if 'commandline' in p['name'].lower()]
        
        teamrender_processes = [p for p in processes if 'teamrender' in p['name'].lower()]
        
        if commandline_processes or teamrender_processes:
            return True
        
        if high_cpu_processes:
            return True
        
        return False
    
    def check_render_queue_files(self):
        possible_files = [
            os.path.expanduser("~/AppData/Roaming/Maxon/render_queue.xml"),
            os.path.expanduser("~/AppData/Roaming/Maxon/queue.dat"),
            os.path.expanduser("~/Documents/Maxon/render_queue.xml"),
            "C:\\ProgramData\\Maxon\\render_queue.xml"
        ]
        
        for file_path in possible_files:
            try:
                if os.path.exists(file_path):
                    mtime = os.path.getmtime(file_path)
                    if time.time() - mtime < 60:
                        return True
            except Exception:
                continue
        
        return False
    
    def check_render_status(self):
        processes = self.check_c4d_processes()
        
        queue_active = self.check_render_queue_files()
        
        process_rendering = self.is_rendering_active(processes)
        current_rendering = process_rendering or queue_active
        
        return current_rendering

def format_seconds(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def open_last_folder(folder_path):
    try:
        subprocess.Popen(['explorer', folder_path])
        print(f"已打开文件夹: {folder_path}")
    except Exception as e:
        print(f"打开文件夹失败: {e}")

def keyboard_listener(stats):
    while True:
        try:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key == b'o' or key == b'O':
                    last_folder = stats.get('last_target_folder', None)
                    if last_folder and os.path.exists(last_folder):
                        open_last_folder(last_folder)
                    else:
                        print("没有可打开的文件夹记录")
                elif key == b'q' or key == b'Q':
                    print("收到退出信号")
                    stats['should_exit'] = True
                    break
                else:
                    pass
            time.sleep(0.1)
        except Exception as e:
            print(f"键盘监听异常: {e}")
            break

def generate_bar_chart_for_history(history_lines, for_log_file=False):
    """生成带柱状图的历史记录显示
    Args:
        history_lines: 历史记录行列表
        for_log_file: 是否用于日志文件（True时使用|和空格，False时使用█）
    """
    if not history_lines:
        return []
        
    parsed_lines = []
    valid_intervals = []
    
    for line in history_lines:
        # 处理带时间戳的行
        if line.startswith('[') and ']' in line:
            timestamp_end = line.find(']') + 1
            timestamp = line[:timestamp_end]
            remaining = line[timestamp_end:].strip()
            line_to_parse = remaining
        else:
            timestamp = ""
            line_to_parse = line
        
        if line_to_parse.startswith('"') and '"' in line_to_parse[1:]:
            end_quote_pos = line_to_parse.find('"', 1)
            filename_part = line_to_parse[:end_quote_pos + 1]
            time_part = line_to_parse[end_quote_pos + 1:]
            
            interval = 0
            is_special = False
            
            if "[初始文件]" in time_part or "[不完整渲染时长]" in time_part or "[渲染暂停]" in time_part:
                is_special = True
            elif "[00:00:00]" in time_part:
                is_special = True
            else:
                time_match = re.search(r'\[(\d{1,2}):(\d{1,2}):(\d{1,2})\]', time_part)
                if time_match:
                    try:
                        h, m, s = map(int, time_match.groups())
                        interval = h * 3600 + m * 60 + s
                        if interval > 0:
                            valid_intervals.append(interval)
                    except:
                        pass
                else:
                    time_match = re.search(r'(\d{1,2}):(\d{1,2}):(\d{1,2})', time_part)
                    if time_match:
                        try:
                            h, m, s = map(int, time_match.groups())
                            interval = h * 3600 + m * 60 + s
                            if interval > 0:
                                valid_intervals.append(interval)
                        except:
                            pass
            
            parsed_lines.append({
                'filename': filename_part,
                'time': time_part,
                'interval': interval,
                'is_special': is_special,
                'timestamp': timestamp
            })
        else:
            parsed_lines.append({'original_line': line})
    
    if valid_intervals:
        max_time = max(valid_intervals)
        min_time = min(valid_intervals) if valid_intervals else 0
    else:
        max_time = min_time = 0
    
    max_filename_length = 0
    for item in parsed_lines:
        if 'filename' in item:
            max_filename_length = max(max_filename_length, len(item['filename']))
    
    enhanced_lines = []
    bar_width = 20
    
    if for_log_file:
        fill_char = '|'
        empty_char = ' '
    else:
        fill_char = '█'
        empty_char = ' '
    
    for item in parsed_lines:
        if 'original_line' in item:
            enhanced_lines.append(item['original_line'])
        else:
            filename = item['filename']
            time_part = item['time']
            interval = item['interval']
            is_special = item['is_special']
            timestamp = item.get('timestamp', '')
            
            padding = " " * (max_filename_length - len(filename))
            
            if is_special or interval == 0:
                bar = empty_char * bar_width
            else:
                ratio = interval / max_time if max_time > 0 else 0.0
                
                ratio = max(0.0, min(1.0, ratio))
                
                filled_length = int(bar_width * ratio) if interval > 0 else 0
                
                bar = fill_char * filled_length + empty_char * (bar_width - filled_length)
            
            enhanced_lines.append(f"{timestamp}{filename}{padding}|{bar}|{time_part}")
    
    return enhanced_lines

def main_logic(stats):
    folder_path = os.path.dirname(os.path.abspath(__file__))
    if 'history' not in stats:
        stats['history'] = []
    if 'render_monitor' not in stats:
        stats['render_monitor'] = C4DRenderMonitor()
    if 'last_log_save' not in stats:
        stats['last_log_save'] = 0
    
    history = stats['history']
    render_monitor = stats['render_monitor']
    
    current_time = time.time()
    if current_time - stats['last_log_save'] > 1:
        save_cmd_content_to_log(stats)
        stats['last_log_save'] = current_time
    
    try:
        is_rendering = render_monitor.check_render_status()
        render_status_changed = False
        
        if render_monitor.last_render_status != (1 if is_rendering else 0):
            render_status_changed = True
            render_monitor.last_render_status = 1 if is_rendering else 0
        
        last_move_time = stats.get('last_move_time', None)
        moved_count = stats.get('moved_count', 0)
        program_start = stats.get('program_start', time.time())
        dot_count = stats.get('dot_count', 1)
        max_interval = stats.get('max_interval', 0)
        total_interval = stats.get('total_interval', 0)
        total_render_time = stats.get('total_render_time', 0)
        last_render_check = stats.get('last_render_check', time.time())
        is_first_run = stats.get('is_first_run', True)
        is_second_run = stats.get('is_second_run', False)
        moved_this_round = 0
        move_failed = False
        
        current_time = time.time()
        if stats.get('was_rendering', False) and is_rendering:
            total_render_time += current_time - last_render_check
        
        stats['was_rendering'] = is_rendering
        stats['last_render_check'] = current_time
        
        base_dir = folder_path
        sequences = {}
        renamed_files = []
        
        # 常见的通道后缀（大小写不敏感）
        channel_suffixes = ['alpha', 'zdepth', 'normal', 'roughness', 'metallic', 'specular', 'emission', 'ao', 'displacement', 'bump', 'diffuse', 'reflection', 'refraction', 'atmospheric_effects', 'background', 'bump_normals', 'caustics', 'coat', 'coat_filter', 'coat_glossiness', 'coat_reflection', 'coverage', 'cryptomatte', 'cryptomatte00', 'cryptomatte01', 'cryptomatte02', 'denoiser', 'dl1', 'dl2', 'dl3', 'dr_bucket', 'environment', 'extra_tex', 'global_illumination', 'lighting', 'material_id', 'material_select', 'matte_shadow', 'metalness', 'multi_matte', 'multi_matte_id', 'normals', 'object_id', 'object_select', 'object_select_alpha', 'object_select_filter', 'raw_coat_filter', 'raw_coat_reflection', 'raw_gi', 'raw_lighting', 'raw_reflection', 'raw_refraction', 'raw_shadow', 'raw_sheen_filter', 'raw_sheen_reflection', 'raw_total_light', 'reflection_filter', 'reflection_glossiness', 'reflection_highlight_glossiness', 'reflection_ior', 'refraction_filter', 'refraction_glossiness', 'render_id', 'sampler_info', 'sample_rate', 'self_illumination', 'shadow', 'sheen', 'sheen_filter', 'sheen_glossiness', 'sheen_reflection', 'sss', 'toon', 'toon_lighting', 'toon_specular', 'total_light', 'velocity']
        
        for filename in os.listdir(base_dir):
            if filename.lower().endswith('.png'):
                name, ext = os.path.splitext(filename)
                
                basename = None
                num = None
                channel_suffix = None
                
                match = re.search(r'(.+?)\.(.+?)\.(\d{4})$', name)
                if match:
                    basename = match.group(1)
                    channel_suffix = match.group(2)
                    num = match.group(3)
                else:
                    match = re.search(r'(.+?)(\d{4})$', name)
                    if match:
                        basename = match.group(1)
                        num = match.group(2)
                        channel_suffix = None
                    else:
                        continue
                
                if basename and num:
                    numlen = len(num)
                    seq_name = basename
                    
                    if 0 < numlen < 4:
                        newnum = num.zfill(4)
                        if channel_suffix:
                            newname = f"{basename}.{channel_suffix}.{newnum}{ext}"
                        else:
                            newname = f"{basename}.{newnum}{ext}"
                        try:
                            os.rename(os.path.join(base_dir, filename), os.path.join(base_dir, newname))
                            print(f'Renaming "{filename}" to "{newname}"')
                            renamed_files.append((newname, channel_suffix))
                            sequences.setdefault(seq_name, []).append((newname, channel_suffix))
                        except Exception as e:
                            print(f"重命名失败: {filename} -> {newname}, 错误: {e}")
                            sequences.setdefault(seq_name, []).append((filename, channel_suffix))
                    else:
                        sequences.setdefault(seq_name, []).append((filename, channel_suffix))

        time.sleep(0.1)
        
        for seq, file_info_list in sequences.items():
            main_folder = os.path.join(base_dir, seq)
            os.makedirs(main_folder, exist_ok=True)
            
            stats['last_target_folder'] = main_folder
            
            for file_info in file_info_list:
                filename, channel_suffix = file_info
                src = os.path.join(base_dir, filename)
                
                if channel_suffix:
                    channel_folder = os.path.join(main_folder, channel_suffix)
                    os.makedirs(channel_folder, exist_ok=True)
                    dst = os.path.join(channel_folder, filename)
                    
                    try:
                        shutil.move(src, dst)
                    except Exception:
                        pass
                else:
                    rgb_folder = os.path.join(main_folder, "RGB")
                    os.makedirs(rgb_folder, exist_ok=True)
                    dst = os.path.join(rgb_folder, filename)
                    
                    try:
                        shutil.move(src, dst)
                        now = time.time()
                        
                        if is_first_run:
                            timestamp = datetime.now().strftime("%H:%M:%S")
                            history.append(f"[{timestamp}] \"{filename}\"[初始文件]")
                            moved_count += 1
                            moved_this_round += 1
                        elif is_second_run:
                            timestamp = datetime.now().strftime("%H:%M:%S")
                            history.append(f"[{timestamp}] \"{filename}\"[不完整渲染时长]")
                            moved_count += 1
                            moved_this_round += 1
                        else:
                            if last_move_time and is_rendering:
                                interval = now - last_move_time
                                total_interval += interval
                                if interval > max_interval:
                                    max_interval = interval
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                history.append(f"[{timestamp}] \"{filename}\"{format_seconds(interval)}")
                            elif last_move_time and not is_rendering:
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                history.append(f"[{timestamp}] \"{filename}\"[渲染暂停]")
                            else:
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                history.append(f"[{timestamp}] \"{filename}\"[00:00:00]")
                            moved_count += 1
                            moved_this_round += 1
                        
                        if is_rendering:
                            last_move_time = now
                    except Exception:
                        move_failed = True
                        pass
        if is_first_run:
            stats['first_run_moved'] = stats.get('first_run_moved', 0) + moved_this_round
            if moved_this_round > 0:
                is_first_run = False
                is_second_run = True
        elif is_second_run:
            stats['second_run_moved'] = stats.get('second_run_moved', 0) + moved_this_round
            if moved_this_round > 0:
                is_second_run = False
            
        total_time = time.time() - program_start
        first_run_moved = stats.get('first_run_moved', 0)
        second_run_moved = stats.get('second_run_moved', 0)
        effective_moved_count = moved_count - first_run_moved - second_run_moved
        avg_interval = total_interval / effective_moved_count if effective_moved_count > 0 else 0
        dots = '.' * dot_count + ' ' * (3 - dot_count)
        
        render_indicator = "🔴渲染中" if is_rendering else "⚪暂停中"
        
        stat_line = f"数量: {moved_count} | 最长: {format_seconds(max_interval)} | 平均: {format_seconds(avg_interval)} | 总渲染时间: {format_seconds(total_render_time)} | 程序运行时间: {format_seconds(total_time)} | {render_indicator} {dots}"
        
        # 在GUI模式下不执行清屏
        # os.system('cls')
        enhanced_history = generate_bar_chart_for_history(history, for_log_file=False)
        output_lines = []
        for line in enhanced_history:
            output_lines.append(line)
        output_lines.append(stat_line)
        
        # 更新状态
        stats['last_move_time'] = last_move_time
        stats['max_interval'] = max_interval
        stats['total_interval'] = total_interval
        stats['total_render_time'] = total_render_time
        stats['moved_count'] = moved_count
        stats['program_start'] = program_start
        stats['dot_count'] = (dot_count + 1) % 4 if dot_count is not None else 1
        stats['is_first_run'] = is_first_run
        stats['is_second_run'] = is_second_run
        stats['history'] = history

        # 返回输出内容
        return '\n'.join(output_lines)
    except Exception as e:
        error_msg = f"main_logic发生异常: {e}"
        print(error_msg)
        return error_msg

def get_log_file_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    start_time = datetime.fromtimestamp(time.time()).strftime("%m%d_%H%M")
    log_file_name = f"记录_{start_time}.txt"
    return os.path.join(script_dir, log_file_name)

def save_cmd_content_to_log(stats=None):
    try:
        if not hasattr(save_cmd_content_to_log, 'log_file_path'):
            save_cmd_content_to_log.log_file_path = get_log_file_path()
        
        log_file_path = save_cmd_content_to_log.log_file_path
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_entry = f"{'='*60}\n"
        log_entry += f"C4D文件管理器运行记录\n"
        log_entry += f"{'='*60}\n"
        log_entry += f"程序文件: {os.path.basename(__file__)}\n"
        log_entry += f"最后更新: {current_time}\n"
        log_entry += f"{'='*60}\n\n"
        
        if stats:
            moved_count = stats.get('moved_count', 0)
            program_start = stats.get('program_start', time.time())
            total_render_time = stats.get('total_render_time', 0)
            total_time = time.time() - program_start
            program_start_str = datetime.fromtimestamp(program_start).strftime("%Y-%m-%d %H:%M:%S")
            
            render_monitor = stats.get('render_monitor')
            is_rendering = False
            if render_monitor:
                is_rendering = render_monitor.check_render_status()
            
            log_entry += f"程序启动时间: {program_start_str}\n"
            log_entry += f"当前运行状态: {'🔴渲染中' if is_rendering else '⚪暂停中'}\n"
            log_entry += f"已处理文件数量: {moved_count}\n"
            log_entry += f"程序运行时长: {format_seconds(total_time)}\n"
            log_entry += f"总渲染时长: {format_seconds(total_render_time)}\n"
            log_entry += f"{'-'*60}\n"
            
            history = stats.get('history', [])
            if history:
                log_entry += f"文件处理历史:\n"
                display_history = history
                
                enhanced_history = generate_bar_chart_for_history(display_history, for_log_file=True)
                for line in enhanced_history:
                    log_entry += f"{line}\n"
                
                log_entry += f"{'-'*60}\n"
                first_run_moved = stats.get('first_run_moved', 0)
                second_run_moved = stats.get('second_run_moved', 0)
                effective_moved_count = moved_count - first_run_moved - second_run_moved
                total_interval = stats.get('total_interval', 0)
                max_interval = stats.get('max_interval', 0)
                avg_interval = total_interval / effective_moved_count if effective_moved_count > 0 else 0
                
                render_indicator = "🔴渲染中" if is_rendering else "⚪暂停中"
                stat_line = f"数量: {moved_count} | 最长: {format_seconds(max_interval)} | 平均: {format_seconds(avg_interval)} | 总渲染时间: {format_seconds(total_render_time)} | 程序运行时间: {format_seconds(total_time)} | {render_indicator}"
                log_entry += f"{stat_line}\n"
            else:
                log_entry += f"暂无文件处理记录\n"
        
        log_entry += f"\n{'='*60}\n"
        log_entry += f"记录文件: {os.path.basename(log_file_path)}\n"
        log_entry += f"{'='*60}"
        
        with open(log_file_path, 'w', encoding='utf-8') as f:
            f.write(log_entry)
            
    except Exception as e:
        print(f"保存记录失败: {e}")

class FileManager:
    """文件管理器类"""

    def __init__(self, root):
        self.root = root
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.tree_data = {}
        self.expanded_items = set()
        
        # 主题色系统
        self.theme_color = "#B0B0B0"  # 默认深灰色，用于全局序列区分
        
        # 常见的通道后缀（与mf.py保持一致）
        self.channel_suffixes = [
            'alpha', 'zdepth', 'normal', 'roughness', 'metallic', 'specular',
            'emission', 'ao', 'displacement', 'bump', 'diffuse', 'reflection', 'refraction',
            'atmospheric_effects', 'background', 'bump_normals', 'caustics', 'coat',
            'coat_filter', 'coat_glossiness', 'coat_reflection', 'coverage', 'cryptomatte',
            'cryptomatte00', 'cryptomatte01', 'cryptomatte02', 'denoiser', 'dl1', 'dl2', 'dl3',
            'dr_bucket', 'environment', 'extra_tex', 'global_illumination', 'lighting',
            'material_id', 'material_select', 'matte_shadow', 'metalness', 'multi_matte',
            'multi_matte_id', 'normals', 'object_id', 'object_select', 'object_select_alpha',
            'object_select_filter', 'raw_coat_filter', 'raw_coat_reflection', 'raw_gi',
            'raw_lighting', 'raw_reflection', 'raw_refraction', 'raw_shadow', 'raw_sheen_filter',
            'raw_sheen_reflection', 'raw_total_light', 'reflection_filter', 'reflection_glossiness',
            'reflection_highlight_glossiness', 'reflection_ior', 'refraction_filter',
            'refraction_glossiness', 'render_id', 'sampler_info', 'sample_rate',
            'self_illumination', 'shadow', 'sheen', 'sheen_filter', 'sheen_glossiness',
            'sheen_reflection', 'sss', 'toon', 'toon_lighting', 'toon_specular',
            'total_light', 'velocity', 'effectsresult'
        ]

        # 界面设置默认值
        self.viz_font_size = 3  # 默认可视化字体大小
        self.ui_padding = {"padx": 4, "pady": 2}  # 默认界面间距（极紧凑）
        self.card_padding = {"padx": 6, "pady": 2}  # 默认卡片间距（极紧凑）
        self.auto_refresh_enabled = False  # 自动刷新开关，默认关闭
        
        # 选中状态管理
        self.selected_sequence = None  # 当前选中的序列名
        self.card_backgrounds = {}  # 存储原始背景色用于恢复
        
        # 面板切换管理
        self.current_panel = 2  # 当前显示的面板：1=文件管理器，2=渲染监控（默认显示监控面板）
        self.panel_frames = {}  # 存储面板框架
        
        # 渲染监控相关
        self.render_monitor = C4DRenderMonitor()
        self.monitor_stats = {
            'last_move_time': None, 
            'moved_count': 0, 
            'program_start': time.time(), 
            'should_exit': False,
            'render_monitor': self.render_monitor
        }
        self.monitor_thread = None
        self.monitor_running = False

        self.setup_ui()

    def setup_ui(self):
        """设置用户界面"""
        self.root.title("文件查看管理器")
        self.root.geometry("900x650")
        self.root.minsize(400, 300)

        # 创建菜单栏
        self.create_menu()

        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

        # 创建面板容器
        self.panel_container = ttk.Frame(main_frame)
        self.panel_container.pack(fill=tk.BOTH, expand=True)

        # 创建第一个面板：文件管理器（但不立即显示）
        self.panel_frames[1] = ttk.Frame(self.panel_container)
        # self.panel_frames[1].pack(fill=tk.BOTH, expand=True)  # 暂时不pack
        
        # 在第一个面板中创建文件管理器内容
        self.setup_file_manager_panel(self.panel_frames[1])

        # 创建第二个面板：渲染监控（默认显示）
        self.panel_frames[2] = ttk.Frame(self.panel_container)
        self.panel_frames[2].pack(fill=tk.BOTH, expand=True)  # 默认显示第二面板
        
        # 在第二个面板中创建渲染监控内容
        self.setup_monitor_panel(self.panel_frames[2])

        # 应用主题
        self.apply_theme()

        # 初始扫描
        self.scan_directory()

        # 绑定键盘快捷键
        self.bind_keyboard_shortcuts()
        
        # 启动渲染监控
        self.start_monitor_thread()

    def setup_file_manager_panel(self, parent):
        """设置文件管理器面板"""
        # 创建全目录统计区域（顶部）
        self.create_overall_stats(parent)

        # 创建工具栏
        self.create_toolbar(parent)

        # 创建序列树形视图（可折叠）
        self.setup_tree_view(parent)

    def setup_monitor_panel(self, parent):
        """设置渲染监控面板"""
        # 创建监控面板标题
        title_frame = tk.Frame(parent, bg="#2d2d2d")
        title_frame.pack(fill=tk.X, padx=6, pady=4)
        
        title_label = tk.Label(title_frame, text="🎬 C4D 渲染监控", 
                              fg="#ffffff", bg="#2d2d2d", 
                              font=('Segoe UI', 12, 'bold'))
        title_label.pack(side=tk.LEFT)
        
        # 面板切换提示
        switch_label = tk.Label(title_frame, text="按 M 键切换面板", 
                               fg="#cccccc", bg="#2d2d2d", 
                               font=('Segoe UI', 8))
        switch_label.pack(side=tk.RIGHT)
        
        # 创建监控输出区域
        output_frame = tk.Frame(parent, bg="#1e1e1e")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        
        # 创建文本输出区域（不使用滚动条，因为内容会定期刷新）
        self.monitor_text = tk.Text(output_frame, 
                                   bg="#1e1e1e", fg="#ffffff",
                                   font=('Consolas', 9),
                                   wrap=tk.WORD,
                                   state=tk.DISABLED)
        self.monitor_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def switch_panel(self):
        """切换面板"""
        # 隐藏当前面板
        self.panel_frames[self.current_panel].pack_forget()
        
        # 切换到另一个面板
        self.current_panel = 2 if self.current_panel == 1 else 1
        self.panel_frames[self.current_panel].pack(fill=tk.BOTH, expand=True)
        
        # 更新窗口标题
        if self.current_panel == 1:
            self.root.title("文件查看管理器")
        else:
            self.root.title("C4D 渲染监控")

    def start_monitor_thread(self):
        """启动渲染监控线程"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
            
        self.monitor_running = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def monitor_loop(self):
        """监控循环"""
        while self.monitor_running:
            try:
                # 运行mf.py的主要逻辑，但重定向输出到GUI
                self.run_monitor_logic()
                time.sleep(1)
            except Exception as e:
                self.append_monitor_text(f"监控异常: {e}\n")
                time.sleep(1)

    def run_monitor_logic(self):
        """运行监控逻辑（基于mf.py的main_logic）"""
        stats = self.monitor_stats
        
        try:
            # 运行mf.py的核心逻辑，获取输出
            output = main_logic(stats)
            
            # 清空之前的输出，准备新的一轮
            if hasattr(self, 'monitor_text'):
                self.monitor_text.config(state=tk.NORMAL)
                self.monitor_text.delete(1.0, tk.END)
                
                # 重新写入完整的输出内容
                self.monitor_text.insert(tk.END, output)
                self.monitor_text.see(tk.END)  # 自动滚动到底部
                self.monitor_text.config(state=tk.DISABLED)
            
        except Exception as e:
            if hasattr(self, 'monitor_text'):
                self.monitor_text.config(state=tk.NORMAL)
                self.monitor_text.delete(1.0, tk.END)
                self.monitor_text.insert(tk.END, f"监控逻辑异常: {e}")
                self.monitor_text.config(state=tk.DISABLED)

    def append_monitor_text(self, text):
        """向监控文本框追加文本（保留以备将来使用）"""
        if hasattr(self, 'monitor_text'):
            self.monitor_text.config(state=tk.NORMAL)
            self.monitor_text.insert(tk.END, text)
            self.monitor_text.see(tk.END)  # 自动滚动到底部
            self.monitor_text.config(state=tk.DISABLED)

    def create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root, bg="#2d2d2d", fg="#ffffff", 
                         activebackground="#404040", activeforeground="#ffffff")
        self.root.config(menu=menubar)

        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0, bg="#2d2d2d", fg="#ffffff",
                           activebackground="#404040", activeforeground="#ffffff")
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="选择目录", command=self.select_directory)
        file_menu.add_command(label="刷新", command=self.scan_directory)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)

        # 视图菜单
        view_menu = tk.Menu(menubar, tearoff=0, bg="#2d2d2d", fg="#ffffff",
                           activebackground="#404040", activeforeground="#ffffff")
        menubar.add_cascade(label="视图", menu=view_menu)
        view_menu.add_command(label="按完成率排序", command=self.sort_by_completion)
        view_menu.add_command(label="按名称排序", command=self.sort_by_name)
        view_menu.add_separator()
        
        # 自动刷新开关
        self.auto_refresh_var = tk.BooleanVar(value=self.auto_refresh_enabled)
        view_menu.add_checkbutton(label="启用自动刷新 (5秒)", 
                                 command=self.toggle_auto_refresh,
                                 variable=self.auto_refresh_var,
                                 onvalue=True, offvalue=False)
        
        # 文字大小调整
        view_menu.add_command(label="设置可视化字体大小...", command=self.show_font_size_dialog)
        
        # 主题色设置
        view_menu.add_command(label="设置主题色...", command=self.show_theme_color_dialog)
        
        # 界面缩放子菜单
        scale_menu = tk.Menu(view_menu, tearoff=0, bg="#2d2d2d", fg="#ffffff",
                            activebackground="#404040", activeforeground="#ffffff")
        view_menu.add_cascade(label="界面缩放", menu=scale_menu)
        scale_menu.add_command(label="紧凑模式", command=lambda: self.change_ui_scale("compact"))
        scale_menu.add_command(label="标准模式", command=lambda: self.change_ui_scale("normal"))
        scale_menu.add_command(label="舒适模式", command=lambda: self.change_ui_scale("comfortable"))

    def create_toolbar(self, parent):
        """创建工具栏"""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 3))

        # 当前路径显示
        path_frame = ttk.Frame(toolbar)
        path_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(path_frame, text="当前目录:").pack(side=tk.LEFT, padx=(0, 5))
        self.path_var = tk.StringVar(value=self.current_path)
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var, state='readonly')
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        ttk.Button(path_frame, text="选择...", command=self.select_directory).pack(side=tk.LEFT)
        ttk.Button(path_frame, text="刷新", command=self.scan_directory).pack(side=tk.LEFT, padx=(5, 0))

    def setup_tree_view(self, parent):
        """设置卡片式序列视图"""
        # 创建主滚动框架
        self.main_frame = ttk.Frame(parent)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 创建Canvas和滚动条用于卡片式布局
        self.canvas = tk.Canvas(self.main_frame, bg="#202020", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        # 配置滚动 - 使用更可靠的scrollregion更新
        def update_scrollregion(event=None):
            self.scrollable_frame.update_idletasks()
            bbox = self.canvas.bbox("all")
            if bbox:
                self.canvas.configure(scrollregion=bbox)

        self.scrollable_frame.bind("<Configure>", update_scrollregion)

        # 创建窗口，并绑定Canvas宽度变化事件
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # 绑定Canvas大小变化事件，使内容自适应宽度
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # 布局Canvas和滚动条
        self.canvas.pack(side="left", fill="both", expand=True)
        # 滚动条初始隐藏，只在需要时显示
        self.scrollbar.pack_forget()

        # 绑定鼠标滚轮事件
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        
        # 存储卡片组件的字典
        self.sequence_cards = {}

    def on_canvas_configure(self, event):
        """Canvas大小变化时调整内容宽度并刷新可视化"""
        # 获取Canvas的宽度
        canvas_width = event.width
        
        # 调整scrollable_frame的宽度以匹配Canvas宽度
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
        
        # 更新滚动区域
        self.update_scrollregion()
        
        # 延迟刷新可视化内容，提高响应速度（增加到120ms以降低拖动时的运算压力）
        if hasattr(self, '_resize_after_id'):
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(120, self.refresh_all_visualizations)

    def on_mousewheel(self, event):
        """鼠标滚轮事件处理"""
        # 获取当前滚动位置
        current_pos = self.canvas.yview()

        # 计算滚动方向和距离
        scroll_units = int(-1 * (event.delta / 120))

        # 检查是否会超出边界
        if scroll_units > 0:  # 向下滚动
            if current_pos[1] >= 1.0:  # 已经到底部
                return
        elif scroll_units < 0:  # 向上滚动
            if current_pos[0] <= 0.0:  # 已经到顶部
                return

        # 执行滚动
        self.canvas.yview_scroll(scroll_units, "units")

    def refresh_all_visualizations(self):
        """刷新所有已打开的可视化内容"""
        try:
            # 强制更新界面布局以获取正确的宽度
            self.root.update_idletasks()
            
            # 刷新全局可视化
            if hasattr(self, 'global_viz_frame') and hasattr(self, 'global_inner_frame'):
                # 重新计算全局统计
                self.global_stats = self.calculate_global_stats()
                # 更新全局信息标签
                if hasattr(self, 'global_info_label'):
                    info_text = (f"总序列: {self.global_stats['total_sequences']} | "
                                f"总帧: {self.global_stats['total_frames']} | "
                                f"现有: {self.global_stats['existing_frames']}")
                    if self.global_stats['missing_frames'] > 0:
                        info_text += f" | 缺失: {self.global_stats['missing_frames']}"
                    self.global_info_label.config(text=info_text)
                # 重新生成全局可视化
                self.generate_global_visualization()
            
            # 刷新序列可视化
            if hasattr(self, 'sequence_cards'):
                for seq_name, card_info in self.sequence_cards.items():
                    # 检查可视化是否已经显示（现在默认都显示）
                    if card_info['viz_var'].get():
                        # 强制更新父容器尺寸
                        parent_frame = card_info['parent_frame']
                        parent_frame.update_idletasks()
                        
                        # 重新生成可视化内容
                        viz_frame = card_info['viz_frame']
                        seq_data = card_info['seq_data']
                        
                        # 使用统一的生成方法
                        self.generate_and_show_visualization(viz_frame, seq_data, parent_frame)
        except Exception as e:
            print(f"刷新可视化时出错: {e}")

    def create_sequence_card(self, parent, seq_name, seq_data):
        """创建单个序列的卡片"""
        # 计算完成率和状态
        completion_rate = seq_data['completion_rate']
        
        # 状态图标统一为白色
        if completion_rate >= 100:
            status_icon = "✓"
        elif completion_rate >= 90:
            status_icon = "●"
        else:
            status_icon = "○"
        status_color = "#ffffff"  # 统一使用白色

        # 创建卡片主框架 - 全宽显示
        # 根据选中状态设置背景色
        is_selected = (self.selected_sequence == seq_name)
        bg_color = "#404040" if is_selected else "#2d2d2d"
        card_frame = tk.Frame(parent, bg=bg_color, relief="raised", bd=1)
        card_frame.pack(fill=tk.X, padx=6, pady=2)
        
        # 存储原始背景色
        self.card_backgrounds[seq_name] = bg_color
        
        # 内部容器，提供内边距
        inner_frame = tk.Frame(card_frame, bg=bg_color)
        inner_frame.pack(fill=tk.X, padx=6, pady=4)

        # 卡片头部 - 序列名称和状态
        header_frame = tk.Frame(inner_frame, bg=bg_color)
        header_frame.pack(fill=tk.X)

        # 折叠/展开按钮
        expand_icon = "▼" if seq_data.get('expanded', True) else "▶"
        expand_btn = tk.Button(header_frame, text=expand_icon, fg="#cccccc", bg=bg_color, 
                              font=('Segoe UI', 8), bd=0, padx=2, pady=0,
                              command=lambda: self.toggle_sequence_expansion(seq_name))
        expand_btn.pack(side=tk.LEFT, padx=(0, 4))

        # 状态图标
        status_label = tk.Label(header_frame, text=status_icon, fg=status_color, 
                               bg=bg_color, font=('Segoe UI', 12, 'bold'))
        status_label.pack(side=tk.LEFT, padx=(0, 6))

        # 序列名称
        name_label = tk.Label(header_frame, text=seq_name, fg="#ffffff", 
                             bg=bg_color, font=('Segoe UI', 10, 'bold'))
        name_label.pack(side=tk.LEFT)

        # 帧范围信息（与序列名称同一行）
        frame_range_text = f"帧范围: {seq_data['min_frame']:04d}-{seq_data['max_frame']:04d}"
        frame_range_label = tk.Label(header_frame, text=frame_range_text, fg="#cccccc", 
                                    bg=bg_color, font=('Segoe UI', 8))
        frame_range_label.pack(side=tk.LEFT, padx=(15, 0))

        # 统计信息（与序列名称同一行）
        stats_text = f"总帧: {seq_data['total_frames']} | 现有: {seq_data['existing_count']}"
        if seq_data['missing_count'] > 0:
            stats_text += f" | 缺失: {seq_data['missing_count']}"
        
        stats_label = tk.Label(header_frame, text=stats_text, fg="#cccccc", 
                              bg=bg_color, font=('Segoe UI', 8))
        stats_label.pack(side=tk.LEFT, padx=(15, 0))

        # 完成率
        completion_label = tk.Label(header_frame, text=f"{completion_rate:.1f}%", 
                                   fg="#ffffff", bg=bg_color, font=('Segoe UI', 9, 'bold'))
        completion_label.pack(side=tk.RIGHT)

        # 可视化区域（根据折叠状态显示）
        is_expanded = seq_data.get('expanded', True)
        viz_bg_color = "#505050" if is_selected else "#404040"
        viz_frame = tk.Frame(inner_frame, bg=viz_bg_color)
        viz_var = tk.BooleanVar(value=True)  # 默认为True，表示已显示
        
        # 只有在展开状态下才显示可视化区域
        if is_expanded:
            viz_frame.pack(fill=tk.X, pady=(4, 0))
            # 生成并显示可视化内容
            self.generate_and_show_visualization(viz_frame, seq_data, inner_frame)

        # 双击打开文件夹功能，单击选中
        def on_single_click(event):
            self.select_sequence(seq_name)
            
        def on_double_click(event):
            self.open_rgb_folder(seq_data)

        # 绑定单击和双击事件到卡片的各个组件
        for widget in [card_frame, inner_frame, header_frame, expand_btn, status_label, name_label, frame_range_label, stats_label, completion_label]:
            widget.bind('<Button-1>', on_single_click)
            widget.bind('<Double-Button-1>', on_double_click)

        # 返回卡片信息字典
        return {
            'frame': card_frame,
            'viz_frame': viz_frame,
            'viz_var': viz_var,
            'seq_data': seq_data,
            'parent_frame': inner_frame
        }

    def generate_and_show_visualization(self, viz_frame, seq_data, parent_frame):
        """生成并显示可视化内容"""
        try:
            # 清空现有内容
            for widget in viz_frame.winfo_children():
                widget.destroy()
            
            # 强制更新布局并等待完成
            parent_frame.update_idletasks()
            self.root.update()  # 强制完成所有待处理的界面更新
            
            # 根据当前卡片宽度动态生成可视化
            available_width = max(100, parent_frame.winfo_width() - 40)  # 确保最小宽度
            
            # 生成自适应宽度的可视化文本（内部会重新计算字符数）
            viz_text = self.generate_adaptive_frame_visualization_text(seq_data, available_width)
            
            # 使用 tkinter.font 精确测量字符像素宽度（避免小字号时估算过大）
            try:
                font_obj = tkfont.Font(family='Consolas', size=self.viz_font_size)
                char_width = max(1, font_obj.measure('█'))
            except Exception:
                char_width = max(3, int(self.viz_font_size * 0.6))
            chars_per_line = max(1, available_width // char_width)
        except Exception as e:
            print(f"生成可视化内容时出错: {e}")
            viz_text = f"可视化生成错误: {str(e)}"
            chars_per_line = 50  # 默认值
        
        # 动态计算实际需要的行数
        actual_lines = max(1, viz_text.count('\n') + 1)
        
        # 创建可视化文本标签
        viz_text_widget = tk.Text(viz_frame, 
                                height=actual_lines,
                                width=chars_per_line,  # 设置宽度以填满可用空间
                                bg="#404040", fg="#ffffff",
                                font=('Consolas', self.viz_font_size),
                                relief="flat", 
                                borderwidth=0,
                                wrap=tk.NONE,
                                state=tk.DISABLED,
                                cursor="arrow",
                                selectbackground="#505050",
                                padx=5, pady=2)  # 添加内边距使左右对称
        
        # 插入文本并配置标签
        viz_text_widget.config(state=tk.NORMAL)
        viz_text_widget.delete(1.0, tk.END)
        viz_text_widget.insert(tk.END, viz_text)
        viz_text_widget.config(state=tk.DISABLED)
        viz_text_widget.pack(fill=tk.X, padx=8, pady=8)
        
        # 强制更新Text widget的尺寸
        viz_text_widget.update_idletasks()

    def toggle_visualization(self, viz_frame, viz_var, seq_data, toggle_btn, parent_frame):
        """切换可视化显示"""
        if viz_var.get():
            # 隐藏可视化
            viz_frame.pack_forget()
            toggle_btn.config(text="▶")
            viz_var.set(False)
        else:
            # 显示可视化
            viz_frame.pack(fill=tk.X, pady=(8, 0))
            
            # 清空并重新创建可视化内容
            for widget in viz_frame.winfo_children():
                widget.destroy()
            
            # 根据当前卡片宽度动态生成可视化
            parent_frame.update_idletasks()
            available_width = parent_frame.winfo_width() - 40  # 减去内边距
            
            # 生成自适应宽度的可视化文本
            viz_text = self.generate_adaptive_frame_visualization_text(seq_data, available_width)

            # 计算每行字符数（使用字体测量）
            try:
                font_obj = tkfont.Font(family='Consolas', size=self.viz_font_size)
                char_width = max(1, font_obj.measure('█'))
            except Exception:
                char_width = max(3, int(self.viz_font_size * 0.6))
            chars_per_line = max(1, (available_width) // char_width)

            # 创建可视化文本标签 - 使用Text widget以获得更好的显示效果
            viz_text_widget = tk.Text(viz_frame, 
                                    height=max(1, viz_text.count('\n') + 1),
                                    width=chars_per_line,
                                    bg="#404040", fg="#ffffff",
                                    font=('Consolas', self.viz_font_size),
                                    relief="flat", 
                                    borderwidth=0,
                                    wrap=tk.NONE,
                                    state=tk.DISABLED,
                                    cursor="arrow",
                                    selectbackground="#505050")
            
            viz_text_widget.pack(anchor=tk.W, padx=12, pady=10, fill=tk.X)
            
            # 插入文本内容
            viz_text_widget.config(state=tk.NORMAL)
            viz_text_widget.insert(tk.END, viz_text)
            viz_text_widget.config(state=tk.DISABLED)
            
            toggle_btn.config(text="▼")
            viz_var.set(True)

    def on_tree_open(self, event):
        """树形控件展开事件"""
        pass

    def on_tree_close(self, event):
        """树形控件折叠事件"""
        pass

    def create_overall_stats(self, parent):
        """创建全目录统计区域"""
        # 创建全局总览卡片
        self.create_global_overview_card(parent)

    def create_global_overview_card(self, parent):
        """创建全局总览卡片，样式与序列卡片相同"""
        # 计算全局统计
        global_stats = self.calculate_global_stats()
        
        # 创建卡片主框架
        card_frame = tk.Frame(parent, bg="#2f2f2f", relief="raised", bd=2)  # 创建卡片主框架 - 使用比下方卡片更亮的灰色
        card_frame.pack(fill=tk.X, padx=6, pady=4)
        # 内部容器（使用与卡片一致的浅灰色）
        inner_frame = tk.Frame(card_frame, bg="#2f2f2f")
        inner_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # 卡片头部
        header_frame = tk.Frame(inner_frame, bg="#2f2f2f")
        header_frame.pack(fill=tk.X)

        # 状态图标
        status_label = tk.Label(header_frame, text="🌐", fg="#ffffff", 
                               bg="#2f2f2f", font=('Segoe UI', 12, 'bold'))
        status_label.pack(side=tk.LEFT, padx=(0, 8))

        # 全局标题
        name_label = tk.Label(header_frame, text="全局总览", fg="#ffffff", 
                              bg="#2f2f2f", font=('Segoe UI', 10, 'bold'))
        name_label.pack(side=tk.LEFT)

        # 全局统计信息（与标题同一行）
        global_stats_text = (f"总序列: {global_stats['total_sequences']} | "
                           f"总帧: {global_stats['total_frames']} | "
                           f"现有: {global_stats['existing_frames']}")
        
        if global_stats['missing_frames'] > 0:
            global_stats_text += f" | 缺失: {global_stats['missing_frames']}"

        # 存储为实例变量以便更新
        self.global_stats_label = tk.Label(header_frame, text=global_stats_text, fg="#cccccc", 
                                          bg="#2f2f2f", font=('Segoe UI', 8))
        self.global_stats_label.pack(side=tk.LEFT, padx=(15, 0))

        # 整体完成率
        self.global_completion_label = tk.Label(header_frame, text=f"{global_stats['completion_rate']:.1f}%", 
                                               fg="#ffffff", bg="#2f2f2f", font=('Segoe UI', 9, 'bold'))
        self.global_completion_label.pack(side=tk.RIGHT)

        # 全局可视化区域
        viz_frame = tk.Frame(inner_frame, bg="#3a3a3a")  # 稍微不同的背景色（比单列卡片更亮）
        viz_frame.pack(fill=tk.X, pady=(4, 0))
        
        # 生成并显示全局可视化内容
        self.global_viz_frame = viz_frame
        self.global_inner_frame = inner_frame
        self.generate_global_visualization()

        # 存储全局统计数据

    def update_global_overview_card(self):
        """更新全局总览卡片的显示信息"""
        try:
            # 重新计算全局统计
            global_stats = self.calculate_global_stats()
            
            # 更新完成率标签
            if hasattr(self, 'global_completion_label'):
                self.global_completion_label.config(text=f"{global_stats['completion_rate']:.1f}%")
            
            # 更新详细统计信息
            if hasattr(self, 'global_stats_label'):
                info_text = (f"总序列: {global_stats['total_sequences']} | "
                            f"总帧: {global_stats['total_frames']} | "
                            f"现有: {global_stats['existing_frames']}")
                
                if global_stats['missing_frames'] > 0:
                    info_text += f" | 缺失: {global_stats['missing_frames']}"
                
                self.global_stats_label.config(text=info_text)
                
        except Exception as e:
            print(f"更新全局概览卡片时出错: {e}")
        self.global_stats = global_stats

    def generate_global_sequence_visualization(self, available_width):
        """生成全局序列连续可视化，使用默认色和主题色交替显示不同序列"""
        try:
            if not self.tree_data:
                return "无序列数据"
            
            # 使用 tkinter.font 精确测量字符像素宽度
            try:
                font_obj = tkfont.Font(family='Consolas', size=self.viz_font_size)
                char_width = max(1, font_obj.measure('█'))
            except Exception:
                char_width = max(3, int(self.viz_font_size * 0.6))
            chars_per_line = max(1, available_width // char_width)
            
            if chars_per_line < 10:
                return "宽度不足以显示可视化"
            
            # 收集所有序列的帧数据，按序列顺序连接
            all_sequence_data = []  # 存储(字符, 颜色类型)的元组
            
            # 遍历所有序列（按排序后的顺序）
            sequence_index = 0
            for seq_name, seq_data in sorted(self.tree_data.items()):
                frames = seq_data.get('frames', [])
                min_frame = seq_data.get('min_frame', 1)
                max_frame = seq_data.get('max_frame', 1)
                
                if not frames:
                    continue
                    
                # 确定这个序列的颜色：偶数序列用默认色，奇数序列用主题色
                use_theme_color = (sequence_index % 2 == 1)
                
                # 为这个序列生成帧范围
                frame_range = list(range(min_frame, max_frame + 1))
                
                for frame_num in frame_range:
                    if frame_num in frames:
                        char = '█'  # 存在的帧
                    else:
                        char = ' '  # 缺失的帧
                    
                    all_sequence_data.append((char, use_theme_color))
                
                sequence_index += 1
            
            # 按行分割进行换行显示
            viz_lines = []
            current_line = []
            
            for char, use_theme_color in all_sequence_data:
                current_line.append(char)
                
                # 达到每行字符数限制时换行
                if len(current_line) >= chars_per_line:
                    viz_lines.append(''.join(current_line))
                    current_line = []
            
            # 添加最后一行（如果有剩余字符）
            if current_line:
                viz_lines.append(''.join(current_line))
            
            return '\n'.join(viz_lines)
                
        except Exception as e:
            return f"生成全局可视化错误: {str(e)[:30]}..."

    def create_colored_global_visualization(self, viz_text):
        """创建支持多色显示的全局可视化Text widget"""
        try:
            # 清空现有内容
            for widget in self.global_viz_frame.winfo_children():
                widget.destroy()
            
            # 使用 tkinter.font 精确测量字符像素宽度
            available_width = max(200, self.global_inner_frame.winfo_width() - 40)
            try:
                font_obj = tkfont.Font(family='Consolas', size=self.viz_font_size)
                char_width = max(1, font_obj.measure('█'))
            except Exception:
                char_width = max(3, int(self.viz_font_size * 0.6))
            chars_per_line = max(1, available_width // char_width)
            
            # 重新生成带颜色信息的序列数据（与generate_global_sequence_visualization保持一致）
            all_sequence_data = []  # 存储(字符, 颜色类型)的元组
            
            # 遍历所有序列收集颜色信息
            sequence_index = 0
            for seq_name, seq_data in sorted(self.tree_data.items()):
                frames = seq_data.get('frames', [])
                min_frame = seq_data.get('min_frame', 1)
                max_frame = seq_data.get('max_frame', 1)
                
                if not frames:
                    continue
                    
                # 确定这个序列的颜色：偶数序列用默认色，奇数序列用主题色
                use_theme_color = (sequence_index % 2 == 1)
                
                # 为这个序列生成帧范围
                frame_range = list(range(min_frame, max_frame + 1))
                
                for frame_num in frame_range:
                    if frame_num in frames:
                        char = '█'  # 存在的帧
                    else:
                        char = ' '  # 缺失的帧
                    
                    all_sequence_data.append((char, use_theme_color))
                
                sequence_index += 1
            
            # 创建Text widget
            viz_text_widget = tk.Text(self.global_viz_frame, 
                                    height=max(1, len(all_sequence_data) // chars_per_line + 1),
                                    width=chars_per_line,  # 设置宽度以填满可用空间
                                    bg="#404040", fg="#ffffff",
                                    font=('Consolas', self.viz_font_size),
                                    relief="flat", 
                                    borderwidth=0,
                                    wrap=tk.NONE,
                                    state=tk.DISABLED,
                                    cursor="arrow",
                                    selectbackground="#404040",
                                    padx=5, pady=2)
            
            # 配置颜色标签
            viz_text_widget.tag_configure("default", foreground="#ffffff")
            viz_text_widget.tag_configure("theme", foreground=self.theme_color)
            
            # 插入带颜色的文本
            viz_text_widget.config(state=tk.NORMAL)
            viz_text_widget.delete(1.0, tk.END)
            
            current_col = 0
            for char, use_theme_color in all_sequence_data:
                tag = "theme" if use_theme_color else "default"
                viz_text_widget.insert(tk.END, char, tag)
                
                current_col += 1
                # 换行
                if current_col >= chars_per_line:
                    viz_text_widget.insert(tk.END, '\n')
                    current_col = 0
            
            viz_text_widget.config(state=tk.DISABLED)
            viz_text_widget.pack(fill=tk.X, padx=8, pady=8)
            
        except Exception as e:
            # 如果多色显示失败，使用简单文本显示
            print(f"多色可视化创建失败: {e}")
            viz_text_widget = tk.Text(self.global_viz_frame, 
                                    height=max(1, viz_text.count('\n') + 1),
                                    width=50,  # 默认宽度
                                    bg="#404040", fg="#ffffff",
                                    font=('Consolas', self.viz_font_size),
                                    relief="flat", 
                                    borderwidth=0,
                                    wrap=tk.NONE,
                                    state=tk.DISABLED,
                                    cursor="arrow",
                                    selectbackground="#404040",
                                    padx=5, pady=2)
            
            viz_text_widget.config(state=tk.NORMAL)
            viz_text_widget.delete(1.0, tk.END)
            viz_text_widget.insert(tk.END, viz_text)
            viz_text_widget.config(state=tk.DISABLED)
            viz_text_widget.pack(fill=tk.X, padx=8, pady=8)

    def calculate_global_stats(self):
        """计算全局统计数据 - 超级简化版本"""
        try:
            if not self.tree_data:
                return {
                    'total_sequences': 0,
                    'total_frames': 0,
                    'existing_frames': 0,
                    'missing_frames': 0,
                    'completion_rate': 0.0,
                    'min_frame': 1,
                    'max_frame': 1,
                    'frames': [],
                    'existing_count': 0
                }

            # 简单统计，不做复杂的帧映射
            total_sequences = len(self.tree_data)
            total_frames = 0
            existing_frames = 0
            all_frames = []
            
            # 直接累加所有序列的统计，使用安全的字段访问
            for seq_name, seq_data in self.tree_data.items():
                # 使用 get 方法安全访问字段
                seq_total = seq_data.get('total_frames', 0)
                seq_existing = seq_data.get('existing_count', 0)
                seq_frames = seq_data.get('frames', [])
                
                total_frames += seq_total
                existing_frames += seq_existing
                # 直接使用原始帧号（不重新映射）
                all_frames.extend(seq_frames)

            missing_frames = total_frames - existing_frames
            completion_rate = (existing_frames / total_frames * 100) if total_frames > 0 else 0.0
            
            # 找到实际的帧范围
            if all_frames:
                min_frame = min(all_frames)
                max_frame = max(all_frames)
            else:
                min_frame = 1
                max_frame = 1

            return {
                'total_sequences': total_sequences,
                'total_frames': total_frames,
                'existing_frames': existing_frames,
                'missing_frames': missing_frames,
                'completion_rate': completion_rate,
                'min_frame': min_frame,
                'max_frame': max_frame,
                'frames': all_frames,
                'existing_count': existing_frames
            }
        except Exception as e:
            print(f"计算全局统计时出错: {e}")
            # 返回安全的默认值
            return {
                'total_sequences': 0,
                'total_frames': 0,
                'existing_frames': 0,
                'missing_frames': 0,
                'completion_rate': 0.0,
                'min_frame': 1,
                'max_frame': 1,
                'frames': [],
                'existing_count': 0
            }

    def generate_global_visualization(self):
        """生成全局可视化 - 超级简化和安全版本"""
        viz_text = "加载中..."
        
        try:
            # 检查必要的属性
            if not hasattr(self, 'global_viz_frame'):
                viz_text = "全局可视化框架未初始化"
                return
            
            # 清空现有内容
            for widget in self.global_viz_frame.winfo_children():
                widget.destroy()
            
            # 检查是否有数据
            if not hasattr(self, 'tree_data') or not self.tree_data:
                viz_text = "无序列数据"
            else:
                # 计算全局统计数据
                self.global_stats = self.calculate_global_stats()
                
                # 检查统计数据是否有效
                if self.global_stats['total_frames'] == 0:
                    viz_text = "所有序列均为空"
                else:
                    # 获取可用宽度
                    try:
                        self.global_inner_frame.update_idletasks()
                        available_width = max(200, self.global_inner_frame.winfo_width() - 40)
                    except:
                        available_width = 400  # 使用默认宽度
                    
                    # 生成全局序列连续可视化
                    viz_text = self.generate_global_sequence_visualization(available_width)
                
        except Exception as e:
            print(f"生成全局可视化时出错: {e}")
            viz_text = f"错误: {str(e)[:50]}..."  # 限制错误信息长度
        
        # 创建支持多色显示的可视化文本标签
        self.create_colored_global_visualization(viz_text)

    def update_overall_stats(self):
        """更新全目录统计信息"""
        # 现在使用全局卡片替代传统统计标签
        if hasattr(self, 'global_viz_frame'):
            # 重新计算并更新全局统计
            self.global_stats = self.calculate_global_stats()
            
            # 更新完成率标签
            if hasattr(self, 'global_completion_label'):
                self.global_completion_label.config(text=f"{self.global_stats['completion_rate']:.1f}%")
            
            # 更新全局信息标签
            if hasattr(self, 'global_stats_label'):
                info_text = (f"总序列: {self.global_stats['total_sequences']} | "
                            f"总帧: {self.global_stats['total_frames']} | "
                            f"现有: {self.global_stats['existing_frames']}")
                if self.global_stats['missing_frames'] > 0:
                    info_text += f" | 缺失: {self.global_stats['missing_frames']}"
                self.global_stats_label.config(text=info_text)
            
            # 重新生成全局可视化
            self.generate_global_visualization()

    def scan_directory(self):
        """递归扫描目录中的所有PNG文件，按序列分组"""
        # 保存当前滚动位置
        current_scroll_pos = self.canvas.yview()

        self.tree_data = {}

        # 初始化expanded_items（如果不存在）
        if not hasattr(self, 'expanded_items'):
            self.expanded_items = set()

        try:
            # 递归扫描所有PNG文件
            all_png_files = self.scan_all_png_files(self.current_path)

            # 按序列分组
            sequences = self.group_files_by_sequence(all_png_files)

            # 处理每个序列
            for seq_name, files in sequences.items():
                self.process_sequence(seq_name, files)

            # 更新列表显示
            self.update_sequence_list()

            # 更新全目录统计
            self.update_overall_stats()

            # 恢复滚动位置
            self.canvas.yview_moveto(current_scroll_pos[0])

        except Exception as e:
            messagebox.showerror("错误", f"扫描目录失败：{str(e)}")

    def scan_all_png_files(self, directory):
        """递归扫描目录中的所有PNG文件"""
        png_files = []

        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith('.png'):
                        full_path = os.path.join(root, file)
                        png_files.append(full_path)
        except Exception as e:
            print(f"扫描目录时出错: {e}")

        return png_files

    def group_files_by_sequence(self, png_files):
        """按序列名分组PNG文件"""
        sequences = defaultdict(list)

        for file_path in png_files:
            filename = os.path.basename(file_path)

            # 提取序列名和帧号
            seq_info = self.parse_sequence_filename(filename)
            if seq_info:
                seq_name, frame_num = seq_info
                sequences[seq_name].append((frame_num, file_path))

        return sequences

    def parse_sequence_filename(self, filename):
        """解析PNG文件名，提取序列名和帧号"""
        # 匹配模式：序列名_帧号.png 或 序列名.帧号.png
        # 忽略通道后缀（如果有的话）
        patterns = [
            r'^(.+?)_(\d{4})\.png$',  # sequence_0001.png
            r'^(.+?)\.(\d{4})\.png$', # sequence.0001.png
            r'^(.+?)(\d{4})\.png$',   # sequence0001.png
        ]

        for pattern in patterns:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                seq_name = match.group(1)
                frame_num = int(match.group(2))

                # 移除常见的通道后缀
                for suffix in self.channel_suffixes:
                    if seq_name.lower().endswith('_' + suffix.lower()):
                        seq_name = seq_name[:-len('_' + suffix)]
                        break
                    elif seq_name.lower().endswith('.' + suffix.lower()):
                        seq_name = seq_name[:-len('.' + suffix)]
                        break

                return seq_name, frame_num

        return None

    def process_sequence(self, seq_name, files):
        """处理单个序列的数据"""
        # 提取所有帧号
        frames = []
        file_paths = {}

        for frame_num, file_path in files:
            frames.append(frame_num)
            file_paths[frame_num] = file_path

        frames = sorted(set(frames))  # 去重并排序

        if not frames:
            return

        # 计算序列统计信息
        min_frame = min(frames)
        max_frame = max(frames)
        expected_frames = set(range(min_frame, max_frame + 1))
        existing_frames = set(frames)
        missing_frames = sorted(expected_frames - existing_frames)

        sequence_data = {
            'name': seq_name,
            'frames': frames,
            'file_paths': file_paths,
            'min_frame': min_frame,
            'max_frame': max_frame,
            'total_frames': len(expected_frames),
            'existing_count': len(existing_frames),
            'missing_frames': missing_frames,
            'missing_count': len(missing_frames),
            'completion_rate': len(existing_frames) / len(expected_frames) * 100 if expected_frames else 0
        }

        self.tree_data[seq_name] = sequence_data

    def scan_png_files(self, directory):
        """扫描目录中的PNG文件并提取帧号"""
        frames = []
        try:
            for filename in os.listdir(directory):
                if filename.lower().endswith('.png'):
                    # 提取帧号
                    match = re.search(r'(\d{4})\.png$', filename)
                    if match:
                        frame_num = int(match.group(1))
                        frames.append(frame_num)
        except:
            pass

        return sorted(frames)

    def update_sequence_list(self):
        """更新序列列表显示 - 卡片式布局"""
        # 清空现有卡片
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.sequence_cards.clear()

        # 为每个序列创建卡片
        for seq_name, seq_data in sorted(self.tree_data.items()):
            card_info = self.create_sequence_card(self.scrollable_frame, seq_name, seq_data)
            self.sequence_cards[seq_name] = card_info

        # 更新滚动区域 - 使用更可靠的方法
        self.scrollable_frame.update_idletasks()
        # 延迟更新scrollregion以确保布局完成
        self.root.after(10, self.update_scrollregion)

    def open_rgb_folder(self, seq_data):
        """打开RGB文件夹"""
        if not seq_data['file_paths']:
            messagebox.showwarning("提示", "未找到文件路径信息")
            return
        
        # 获取第一个文件的路径
        first_frame = min(seq_data['file_paths'].keys())
        file_path = seq_data['file_paths'][first_frame]
        
        # 获取文件所在目录
        file_dir = os.path.dirname(file_path)
        
        # 查找RGB文件夹
        rgb_directory = None
        
        # 方法1: 如果当前目录就包含RGB，直接使用
        if 'RGB' in file_dir.upper():
            # 找到RGB文件夹的路径
            path_parts = file_dir.split(os.sep)
            try:
                rgb_index = -1
                for i, part in enumerate(path_parts):
                    if part.upper() == 'RGB':
                        rgb_index = i
                        break
                
                if rgb_index >= 0:
                    rgb_directory = os.sep.join(path_parts[:rgb_index + 1])
            except:
                pass
        
        # 方法2: 在同级目录下查找RGB文件夹
        if not rgb_directory:
            parent_dir = os.path.dirname(file_dir)
            potential_rgb = os.path.join(parent_dir, 'RGB')
            if os.path.exists(potential_rgb) and os.path.isdir(potential_rgb):
                rgb_directory = potential_rgb
        
        # 方法3: 在当前目录的同级查找rgb文件夹（小写）
        if not rgb_directory:
            parent_dir = os.path.dirname(file_dir)
            potential_rgb = os.path.join(parent_dir, 'rgb')
            if os.path.exists(potential_rgb) and os.path.isdir(potential_rgb):
                rgb_directory = potential_rgb
        
        # 方法4: 如果当前是shadow文件夹，查找同级的rgb文件夹
        if not rgb_directory and 'shadow' in file_dir.lower():
            # 替换shadow为rgb
            rgb_directory = file_dir.lower().replace('shadow', 'rgb')
            if not (os.path.exists(rgb_directory) and os.path.isdir(rgb_directory)):
                # 尝试大写RGB
                rgb_directory = file_dir.lower().replace('shadow', 'RGB')
                if not (os.path.exists(rgb_directory) and os.path.isdir(rgb_directory)):
                    rgb_directory = None
        
        # 如果都没找到，使用原文件目录
        if not rgb_directory:
            rgb_directory = file_dir
            messagebox.showinfo("提示", f"未找到RGB文件夹，将打开原文件目录:\n{rgb_directory}")
        
        # 在文件管理器中打开目录
        try:
            if os.name == 'nt':  # Windows
                os.startfile(rgb_directory)
            elif os.name == 'posix':  # macOS/Linux
                subprocess.run(['xdg-open', rgb_directory])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件夹:\n{rgb_directory}\n\n错误: {str(e)}")

    def generate_adaptive_frame_visualization_text(self, seq_data, available_width):
        """生成精确的帧可视化文本 - 每个字符精确对应帧，只使用实心块和空白"""
        if seq_data['total_frames'] == 0:
            return "无帧数据"
        
        existing_frames = set(seq_data['frames'])
        min_frame = seq_data['min_frame']
        max_frame = seq_data['max_frame']
        total_range = max_frame - min_frame + 1
        
        # 使用 tkinter.font 测量字符像素宽度，确保小字号也能正确计算
        try:
            font_obj = tkfont.Font(family='Consolas', size=self.viz_font_size)
            font_width = max(1, font_obj.measure('█'))
        except Exception:
            font_width = max(3, int(self.viz_font_size * 0.6))
        chars_per_line = max(1, available_width // font_width)
        
        # 调试信息
        # print(f"字号: {self.viz_font_size}, 字符宽度: {font_width}, 可用宽度: {available_width}, 每行字符数: {chars_per_line}")
        
        viz_lines = []
        current_line = []
        
        # 精确显示：每个字符对应一个帧
        for frame_num in range(min_frame, max_frame + 1):
            if frame_num in existing_frames:
                current_line.append("█")  # 实心块 - 帧存在
            else:
                current_line.append(" ")  # 空白 - 帧缺失
            
            # 达到每行字符数限制时换行
            if len(current_line) >= chars_per_line:
                viz_lines.append(''.join(current_line))
                current_line = []
        
        # 添加最后一行（如果有剩余字符）
        if current_line:
            viz_lines.append(''.join(current_line))
        
        return '\n'.join(viz_lines)

    def generate_frame_visualization_text(self, seq_data):
        """生成帧可视化的多行文本表示"""
        if seq_data['total_frames'] == 0:
            return "无帧数据"
        
        existing_frames = set(seq_data['frames'])
        min_frame = seq_data['min_frame']
        max_frame = seq_data['max_frame']
        total_range = max_frame - min_frame + 1
        
        # 每行显示的帧数和最大行数
        frames_per_line = 60
        max_lines = 8
        max_display_frames = frames_per_line * max_lines
        
        viz_lines = []
        
        if total_range <= max_display_frames:
            # 直接显示所有帧，分行显示
            current_line = []
            for frame_num in range(min_frame, max_frame + 1):
                if frame_num in existing_frames:
                    current_line.append("█")  # 实心块
                else:
                    current_line.append("░")  # 空心块
                
                # 每行60个字符就换行
                if len(current_line) >= frames_per_line:
                    viz_lines.append(''.join(current_line))
                    current_line = []
            
            # 添加最后一行（如果有剩余）
            if current_line:
                viz_lines.append(''.join(current_line))
        else:
            # 采样显示，保持多行格式
            step = total_range / max_display_frames
            current_line = []
            
            for i in range(max_display_frames):
                frame_start = int(min_frame + i * step)
                frame_end = int(min_frame + (i + 1) * step)
                
                # 检查这个范围内是否有帧
                has_frame = any(f in existing_frames for f in range(frame_start, frame_end + 1))
                
                if has_frame:
                    current_line.append("█")  # 实心块
                else:
                    current_line.append("░")  # 空心块
                
                # 每行60个字符就换行
                if len(current_line) >= frames_per_line:
                    viz_lines.append(''.join(current_line))
                    current_line = []
            
            # 添加最后一行（如果有剩余）
            if current_line:
                viz_lines.append(''.join(current_line))
        
        # 添加帧号标记行（每10个帧显示一个标记）
        if viz_lines and total_range > 10:
            marker_line = []
            frames_shown = min(total_range, len(viz_lines[0]) if viz_lines else 0)
            
            for i in range(frames_shown):
                actual_frame = min_frame + i * (total_range / frames_shown) if total_range > frames_shown else min_frame + i
                if int(actual_frame) % 10 == 0:
                    marker_line.append("|")
                else:
                    marker_line.append(" ")
            
            viz_lines.append(''.join(marker_line))
            
            # 添加帧号行
            number_line = []
            for i in range(0, frames_shown, 10):
                actual_frame = min_frame + i * (total_range / frames_shown) if total_range > frames_shown else min_frame + i
                frame_str = f"{int(actual_frame):04d}"
                number_line.extend(list(frame_str))
                # 填充空格到下一个10的倍数位置
                while len(number_line) % 10 != 0 and len(number_line) < frames_shown:
                    number_line.append(" ")
            
            viz_lines.append(''.join(number_line[:frames_shown]))
        
        return '\n'.join(viz_lines)

    def on_tree_select(self, event):
        """选择事件 - 在卡片式布局中不需要特殊处理"""
        pass



    def on_tree_double_click(self, event):
        """双击事件 - 在卡片式布局中由卡片自己处理"""
        pass



    def select_directory(self):
        """选择目录"""
        directory = filedialog.askdirectory(
            title="选择要查看的目录",
            initialdir=self.current_path
        )
        if directory:
            self.current_path = directory
            self.path_var.set(directory)
            self.scan_directory()

    def sort_by_completion(self):
        """按完成率排序"""
        self.sort_sequences('completion')

    def sort_by_name(self):
        """按名称排序"""
        self.sort_sequences('name')

    def sort_sequences(self, sort_by):
        """排序序列"""
        if sort_by == 'completion':
            # 按完成率降序排序
            sorted_items = sorted(self.tree_data.items(),
                                key=lambda x: x[1]['completion_rate'],
                                reverse=True)
        else:
            # 按名称排序
            sorted_items = sorted(self.tree_data.items())

        # 重新创建排序后的数据
        self.tree_data = dict(sorted_items)

        # 刷新显示
        self.update_sequence_list()

    def show_font_size_dialog(self):
        """显示字体大小输入对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("设置可视化字体大小")
        dialog.geometry("300x150")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 150
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 75
        dialog.geometry(f"+{x}+{y}")
        
        # 当前字体大小标签
        current_label = tk.Label(dialog, text=f"当前字体大小: {self.viz_font_size}号", 
                                font=('Segoe UI', 10))
        current_label.pack(pady=10)
        
        # 输入框
        input_frame = tk.Frame(dialog)
        input_frame.pack(pady=10)
        
        tk.Label(input_frame, text="新字体大小:", font=('Segoe UI', 9)).pack(side=tk.LEFT)
        
        font_size_var = tk.StringVar(value=str(self.viz_font_size))
        entry = tk.Entry(input_frame, textvariable=font_size_var, width=10, font=('Segoe UI', 9))
        entry.pack(side=tk.LEFT, padx=(10, 0))
        entry.select_range(0, tk.END)
        entry.focus()
        
        # 按钮
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=20)
        
        def apply_font_size():
            try:
                new_size = int(font_size_var.get())
                if 1 <= new_size <= 20:
                    self.change_viz_font_size(new_size)
                    dialog.destroy()
                else:
                    tk.messagebox.showerror("错误", "字体大小必须在1-20之间")
            except ValueError:
                tk.messagebox.showerror("错误", "请输入有效的数字")
        
        def on_enter(event):
            apply_font_size()
        
        entry.bind('<Return>', on_enter)
        
        tk.Button(button_frame, text="确定", command=apply_font_size,
                 bg="#0078d4", fg="white", font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="取消", command=dialog.destroy,
                 font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)

    def show_theme_color_dialog(self):
        """显示主题色设置对话框"""
        from tkinter import colorchooser
        
        # 打开颜色选择器
        color = colorchooser.askcolor(
            initialcolor=self.theme_color,
            title="选择主题色"
        )
        
        if color[1]:  # 如果用户选择了颜色
            self.theme_color = color[1]
            # 刷新所有可视化以应用新主题色
            self.refresh_all_visualizations()

    def change_viz_font_size(self, font_size):
        """改变可视化字体大小"""
        self.viz_font_size = font_size
        # 强制更新界面布局
        self.root.update_idletasks()
        # 重新生成所有可视化
        self.refresh_all_visualizations()

    def change_ui_scale(self, scale_mode):
        """改变界面缩放模式"""
        if scale_mode == "compact":
            # 紧凑模式：减小间距和边距
            self.ui_padding = {"padx": 4, "pady": 2}
            self.card_padding = {"padx": 6, "pady": 3}
        elif scale_mode == "comfortable":
            # 舒适模式：增加间距和边距
            self.ui_padding = {"padx": 12, "pady": 8}
            self.card_padding = {"padx": 16, "pady": 12}
        else:
            # 标准模式
            self.ui_padding = {"padx": 8, "pady": 4}
            self.card_padding = {"padx": 10, "pady": 6}
        
        # 重新创建界面
        self.update_sequence_list()

    def apply_theme(self):
        """应用Win11深色主题样式"""
        try:
            # 应用Win11深色主题
            pywinstyles.apply_style(self.root, "dark")
            
            # Win11深色主题颜色
            dark_bg = "#202020"          # 主背景色
            dark_surface = "#2d2d2d"     # 表面颜色
            dark_surface_light = "#404040" # 浅表面颜色
            text_primary = "#ffffff"      # 主要文字颜色
            text_secondary = "#cccccc"    # 次要文字颜色
            accent_color = "#0078d4"      # 强调色
            
            # 配置主窗口
            self.root.configure(bg=dark_bg)

            # 设置TTK样式
            style = ttk.Style()
            style.theme_use('clam')
            
            # 配置Frame样式
            style.configure("TFrame", 
                          background=dark_bg,
                          relief="flat")
            
            # 配置Label样式
            style.configure("TLabel", 
                          background=dark_bg, 
                          foreground=text_primary,
                          font=('Segoe UI', 9))
            
            # 配置Button样式
            style.configure("TButton", 
                          background=dark_surface,
                          foreground=text_primary,
                          borderwidth=1,
                          focuscolor='none',
                          font=('Segoe UI', 9))
            style.map("TButton",
                     background=[('active', dark_surface_light),
                               ('pressed', accent_color)])
            
            # 配置Entry样式
            style.configure("TEntry",
                          background=dark_surface,
                          foreground=text_primary,
                          fieldbackground=dark_surface,
                          borderwidth=1,
                          insertcolor=text_primary,
                          font=('Segoe UI', 9))
            
            # 配置Treeview样式
            style.configure("Treeview", 
                          background=dark_surface,
                          foreground=text_primary,
                          fieldbackground=dark_surface,
                          borderwidth=0,
                          font=('Segoe UI', 9))
            
            # 配置Treeview标题样式
            style.configure("Treeview.Heading", 
                          background=dark_surface_light,
                          foreground=text_primary,
                          borderwidth=1,
                          relief="flat",
                          font=('Segoe UI', 9, 'bold'))
            
            # 配置Treeview选中样式
            style.map("Treeview",
                     background=[('selected', accent_color)],
                     foreground=[('selected', text_primary)])
            
            # 配置Scrollbar样式
            style.configure("Vertical.TScrollbar",
                          background=dark_surface,
                          troughcolor=dark_bg,
                          borderwidth=0,
                          arrowcolor=text_secondary,
                          darkcolor=dark_surface,
                          lightcolor=dark_surface)
            
            style.configure("Horizontal.TScrollbar",
                          background=dark_surface,
                          troughcolor=dark_bg,
                          borderwidth=0,
                          arrowcolor=text_secondary,
                          darkcolor=dark_surface,
                          lightcolor=dark_surface)

        except Exception as e:
            print(f"主题应用失败: {e}")
            # 备用深色主题
            self.root.configure(bg="#2d2d2d")

    def start_auto_refresh(self):
        """启动自动刷新功能，每5秒刷新一次"""
        if not self.auto_refresh_enabled:
            return
            
        def auto_refresh():
            if self.auto_refresh_enabled and hasattr(self, 'current_path') and self.current_path:
                self.scan_directory()
            # 如果自动刷新仍然启用，5秒后再次调用
            if self.auto_refresh_enabled:
                self.root.after(5000, auto_refresh)

        # 启动自动刷新
        self.root.after(5000, auto_refresh)

    def toggle_auto_refresh(self):
        """切换自动刷新开关"""
        self.auto_refresh_enabled = not self.auto_refresh_enabled
        self.auto_refresh_var.set(self.auto_refresh_enabled)
        
        if self.auto_refresh_enabled:
            self.start_auto_refresh()
            print("自动刷新已启用")
        else:
            print("自动刷新已禁用")

    def toggle_sequence_expansion(self, seq_name):
        """切换序列的折叠/展开状态"""
        if seq_name in self.tree_data:
            current_state = self.tree_data[seq_name].get('expanded', True)
            self.tree_data[seq_name]['expanded'] = not current_state
            # 重新更新序列列表显示
            self.update_sequence_list()

    def update_scrollregion(self):
        """更新Canvas的滚动区域并动态显示/隐藏滚动条"""
        try:
            self.scrollable_frame.update_idletasks()
            bbox = self.canvas.bbox("all")
            if bbox and len(bbox) == 4:
                self.canvas.configure(scrollregion=bbox)
                
                # 获取内容高度和Canvas高度
                content_height = bbox[3] - bbox[1]
                canvas_height = self.canvas.winfo_height()
                
                # 如果内容高度超过Canvas高度，显示滚动条；否则隐藏
                if content_height > canvas_height:
                    if not self.scrollbar.winfo_ismapped():
                        self.scrollbar.pack(side="right", fill="y")
                else:
                    if self.scrollbar.winfo_ismapped():
                        self.scrollbar.pack_forget()
        except Exception as e:
            print(f"更新滚动区域时出错: {e}")

    def bind_keyboard_shortcuts(self):
        """绑定键盘快捷键"""
        # 绑定到主窗口
        self.root.bind('<KeyPress-a>', lambda e: self.expand_all_sequences())
        self.root.bind('<KeyPress-d>', lambda e: self.collapse_all_sequences())
        self.root.bind('<KeyPress-o>', lambda e: self.open_selected_sequence())
        self.root.bind('<KeyPress-m>', lambda e: self.switch_panel())
        self.root.bind('<KeyPress-M>', lambda e: self.switch_panel())  # 大写M也支持
        # 确保主窗口可以接收键盘焦点
        self.root.focus_set()

    def expand_all_sequences(self):
        """展开所有序列"""
        for seq_name in self.tree_data:
            self.tree_data[seq_name]['expanded'] = True
        self.update_sequence_list()

    def collapse_all_sequences(self):
        """折叠所有序列"""
        for seq_name in self.tree_data:
            self.tree_data[seq_name]['expanded'] = False
        self.update_sequence_list()

    def open_selected_sequence(self):
        """打开选中的序列"""
        if self.selected_sequence and self.selected_sequence in self.tree_data:
            self.open_rgb_folder(self.tree_data[self.selected_sequence])

    def select_sequence(self, seq_name):
        """选中指定的序列"""
        # 如果点击的是已选中的序列，则取消选中
        if self.selected_sequence == seq_name:
            self.selected_sequence = None
        else:
            self.selected_sequence = seq_name
        
        # 重新更新序列列表显示选中状态
        self.update_sequence_list()

    def is_dark_mode(self):
        """检测系统是否启用深色模式"""
        try:
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, regtype = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return value == 0  # 0 表示深色模式
        except:
            return False

def create_transparent_icon():
    """创建一个透明图标"""
    try:
        # 创建一个16x16的透明图像
        img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))

        # 保存为临时ico文件
        temp_dir = tempfile.gettempdir()
        icon_path = os.path.join(temp_dir, 'file_manager_icon.ico')
        img.save(icon_path, format='ICO')
        return icon_path
    except:
        return None

def main():
    """主函数"""
    # 隐藏控制台窗口（仅在Windows上有效）
    try:
        if os.name == 'nt':  # Windows系统
            # 尝试多种方法隐藏控制台窗口
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0
            
            # 额外确保：设置窗口为最小化并隐藏
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE = 6
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0
    except Exception as e:
        print(f"隐藏控制台窗口失败: {e}")
        pass  # 如果隐藏失败，继续正常运行
    
    root = tk.Tk()

    # 创建并设置透明图标
    transparent_icon = create_transparent_icon()
    if transparent_icon:
        try:
            root.iconbitmap(transparent_icon)
        except:
            root.wm_iconbitmap("")  # 如果失败则使用空字符串
    else:
        root.wm_iconbitmap("")  # 备用方法

    # 创建文件管理器
    app = FileManager(root)

    # 启动主循环
    root.mainloop()

    # 清理临时图标文件
    if transparent_icon and os.path.exists(transparent_icon):
        try:
            os.remove(transparent_icon)
        except:
            pass

if __name__ == "__main__":
    main()
