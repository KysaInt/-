import os
import shutil
import re
import time
import sys
import subprocess
import threading
import msvcrt
import psutil
import json
from datetime import datetime
from pathlib import Path

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
    if h == 0:
        return f"{m:02d}:{s:02d}"
    else:
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
        if line.startswith('"') and '"' in line[1:]:
            end_quote_pos = line.find('"', 1)
            filename_part = line[:end_quote_pos + 1]
            time_part = line[end_quote_pos + 1:]
            
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
                'is_special': is_special
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
            
            padding = " " * (max_filename_length - len(filename))
            
            if is_special or interval == 0:
                bar = empty_char * bar_width
            else:
                ratio = interval / max_time if max_time > 0 else 0.0
                
                ratio = max(0.0, min(1.0, ratio))
                
                filled_length = max(1, int(bar_width * ratio)) if interval > 0 else 0
                
                bar = fill_char * filled_length + empty_char * (bar_width - filled_length)
            
            enhanced_lines.append(f"{filename}{padding}|{bar}|{time_part}")
    
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
        is_rendering = False
        render_status_changed = False
        
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
        
        channel_suffixes = ['alpha', 'zdepth', 'normal', 'roughness', 'metallic', 'specular', 'emission', 'ao', 'displacement', 'bump', 'diffuse', 'reflection', 'refraction']
        
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
                            history.append(f'"{filename}"[初始文件]')
                            moved_count += 1
                            moved_this_round += 1
                        elif is_second_run:
                            history.append(f'"{filename}"[不完整渲染时长]')
                            moved_count += 1
                            moved_this_round += 1
                        else:
                            if last_move_time and is_rendering:
                                interval = now - last_move_time
                                total_interval += interval
                                if interval > max_interval:
                                    max_interval = interval
                                history.append(f'"{filename}"{format_seconds(interval)}')
                            elif last_move_time and not is_rendering:
                                history.append(f'"{filename}"[渲染暂停]')
                            else:
                                history.append(f'"{filename}"[00:00:00]')
                            moved_count += 1
                            moved_this_round += 1
                        
                        if is_rendering:
                            last_move_time = now
                    except Exception:
                        move_failed = True
                        pass
        if is_first_run:
            if moved_this_round > 0:
                stats['first_run_moved'] = stats.get('first_run_moved', 0) + moved_this_round
                is_first_run = False
                is_second_run = True
            else:
                is_first_run = False
                is_second_run = True
        elif is_second_run and moved_this_round > 0:
            stats['second_run_moved'] = stats.get('second_run_moved', 0) + moved_this_round
            is_second_run = False
            
        total_time = time.time() - program_start
        first_run_moved = stats.get('first_run_moved', 0)
        second_run_moved = stats.get('second_run_moved', 0)
        effective_moved_count = moved_count - first_run_moved - second_run_moved
        avg_interval = total_interval / effective_moved_count if effective_moved_count > 0 else 0
        dots = '.' * dot_count + ' ' * (3 - dot_count)
        
        stat_line = f"数量: {moved_count} | 最长: {format_seconds(max_interval)} | 平均: {format_seconds(avg_interval)} | 总渲染时间: {format_seconds(total_render_time)} | 程序运行时间: {format_seconds(total_time)} | {dots}"
        
        os.system('cls')
        enhanced_history = generate_bar_chart_for_history(history, for_log_file=False)
        for line in enhanced_history:
            print(line)
        print(stat_line)
        dot_count = dot_count + 1 if dot_count < 3 else 1
        stats['last_move_time'] = last_move_time
        stats['max_interval'] = max_interval
        stats['total_interval'] = total_interval
        stats['total_render_time'] = total_render_time
        stats['moved_count'] = moved_count
        stats['program_start'] = program_start
        stats['dot_count'] = dot_count
        stats['is_first_run'] = is_first_run
        stats['is_second_run'] = is_second_run
        stats['history'] = history
    except Exception as e:
        print(f"main_logic发生异常: {e}")

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
                is_rendering = False
            
            log_entry += f"程序启动时间: {program_start_str}\n"
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

if __name__ == "__main__":
    print("C4D文件管理器已启动")
    
    program_start_time = time.time()
    stats = {'last_move_time': None, 'moved_count': 0, 'program_start': program_start_time, 'should_exit': False}
    
    save_cmd_content_to_log(stats)
    print(f"已创建记录文件: 记录_{datetime.fromtimestamp(program_start_time).strftime('%m%d_%H%M')}.txt")
    
    keyboard_thread = threading.Thread(target=keyboard_listener, args=(stats,), daemon=True)
    keyboard_thread.start()
    
    try:
        while True:
            if stats.get('should_exit', False):
                break
            main_logic(stats)
            time.sleep(1)
    except KeyboardInterrupt:
        print("程序被用户中断")
    finally:
        save_cmd_content_to_log(stats)
        stats['should_exit'] = True
        print("程序已关闭，最终记录已保存")
        