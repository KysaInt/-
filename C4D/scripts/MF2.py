import os
import shutil
import re
import time
import sys
import subprocess
import threading
try:
    import msvcrt
except ImportError:
    msvcrt = None
try:
    import psutil
except ImportError:
    psutil = None
import json
import c4d
from datetime import datetime
from pathlib import Path

FLAG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '⏳')

class C4DRenderMonitor:
    def __init__(self):
        """初始化C4D渲染监听器"""
        self.c4d_process_names = [
            'CINEMA 4D.exe',
            'Cinema 4D.exe', 
            'c4d.exe',
            'Commandline.exe',  # C4D命令行渲染
            'TeamRender Client.exe',  # 团队渲染客户端
            'TeamRender Server.exe'   # 团队渲染服务器
        ]
        self.is_rendering = False
        self.last_render_status = -1  # -1表示未初始化，0表示未渲染，1表示正在渲染
        self.last_check_time = 0
        self.cached_processes = []
        self.cache_duration = 0.5  # 缓存0.5秒，提高响应速度
        
    def check_c4d_processes(self):
        """检查C4D相关进程（带缓存优化）"""
        if psutil is None:
            return []
            
        current_time = time.time()
        
        # 如果缓存还有效，返回缓存的结果
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
        
        # 更新缓存
        self.cached_processes = c4d_processes
        self.last_check_time = current_time
        
        return c4d_processes
    
    def is_rendering_active(self, processes):
        """判断是否正在渲染"""
        if not processes:
            return False
        
        # 检查CPU使用率，如果C4D进程CPU使用率较高，可能在渲染
        high_cpu_processes = [p for p in processes if p['cpu_percent'] > 20.0]
        
        # 检查是否有命令行渲染进程
        commandline_processes = [p for p in processes if 'commandline' in p['name'].lower()]
        
        # 检查是否有团队渲染进程
        teamrender_processes = [p for p in processes if 'teamrender' in p['name'].lower()]
        
        # 如果有命令行渲染或团队渲染进程，认为正在渲染
        if commandline_processes or teamrender_processes:
            return True
        
        # 如果有高CPU使用率的C4D进程，可能在渲染
        if high_cpu_processes:
            return True
        
        return False
    
    def check_render_queue_files(self):
        """检查C4D渲染队列相关文件（优化版本）"""
        # 为了提高性能，减少文件系统检查的频率
        # 只检查最常见的渲染队列文件位置，而不进行深度遍历
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
                    if time.time() - mtime < 60:  # 1分钟内修改的文件
                        return True
            except Exception:
                continue
        
        return False
    
    def check_render_status(self):
        """检查当前渲染状态"""
        # 检查C4D进程
        processes = self.check_c4d_processes()
        
        # 检查渲染队列文件
        queue_active = self.check_render_queue_files()
        
        # 判断是否正在渲染
        process_rendering = self.is_rendering_active(processes)
        current_rendering = process_rendering or queue_active
        
        return current_rendering

def format_seconds(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"  # 时:分:秒

def open_last_folder(folder_path):
    """打开指定文件夹的资源管理器"""
    try:
        subprocess.Popen(['explorer', folder_path])
        print(f"已打开文件夹: {folder_path}")
    except Exception as e:
        print(f"打开文件夹失败: {e}")

def keyboard_listener(stats):
    """键盘监听线程"""
    if msvcrt is None:
        print("键盘监听在C4D环境中不可用")
        return
        
    while True:
        try:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key == b'o' or key == b'O':  # 按 O 键打开上一个文件夹
                    last_folder = stats.get('last_target_folder', None)
                    if last_folder and os.path.exists(last_folder):
                        open_last_folder(last_folder)
                    else:
                        print("没有可打开的文件夹记录")
                elif key == b'q' or key == b'Q':  # 按 Q 键退出
                    print("收到退出信号")
                    stats['should_exit'] = True
                    break
            time.sleep(0.1)
        except Exception as e:
            print(f"键盘监听异常: {e}")
            break

def generate_bar_chart_for_history(history_lines):
    """生成带柱状图的历史记录显示（用于CMD和记录文件）"""
    if not history_lines:
        return []
        
    # 分析所有历史记录，提取文件名和时间信息
    parsed_lines = []
    valid_intervals = []
    
    for line in history_lines:
        if line.startswith('"') and '"' in line[1:]:
            # 找到文件名结束的位置
            end_quote_pos = line.find('"', 1)
            filename_part = line[:end_quote_pos + 1]
            time_part = line[end_quote_pos + 1:]
            
            # 提取时间间隔（秒）
            interval = 0
            if "[初始文件]" not in time_part and "[不完整渲染时长]" not in time_part and "[渲染暂停]" not in time_part:
                if ":" in time_part:
                    time_clean = time_part.strip()
                    if time_clean != "[00:00:00]":
                        try:
                            h, m, s = map(int, time_clean.split(':'))
                            interval = h * 3600 + m * 60 + s
                            if interval > 0:
                                valid_intervals.append(interval)
                        except:
                            pass
            
            parsed_lines.append({
                'filename': filename_part,
                'time': time_part,
                'interval': interval,
                'is_special': "[初始文件]" in time_part or "[不完整渲染时长]" in time_part or "[渲染暂停]" in time_part
            })
        else:
            # 不是文件处理行，直接保持原样
            parsed_lines.append({'original_line': line})
    
    # 计算动态比例
    if valid_intervals:
        max_time = max(valid_intervals)
        min_time = min(valid_intervals)
    else:
        max_time = min_time = 0
    
    # 找出最长的文件名长度
    max_filename_length = 0
    for item in parsed_lines:
        if 'filename' in item:
            max_filename_length = max(max_filename_length, len(item['filename']))
    
    # 生成对齐的显示行
    enhanced_lines = []
    bar_width = 20
    
    for item in parsed_lines:
        if 'original_line' in item:
            # 非文件处理行，直接添加
            enhanced_lines.append(item['original_line'])
        else:
            # 文件处理行，添加柱状图
            filename = item['filename']
            time_part = item['time']
            interval = item['interval']
            is_special = item['is_special']
            
            # 计算填充空格（确保柱状图对齐）
            padding = " " * (max_filename_length - len(filename))
            
            if is_special or interval == 0:
                # 特殊状态或无时间间隔，显示空白柱状图
                bar = ' ' * bar_width
            else:
                # 正常渲染时间，显示比例柱状图
                if max_time > min_time:
                    ratio = (interval - min_time) / (max_time - min_time)
                else:
                    ratio = 1.0
                
                filled_length = int(bar_width * ratio)
                bar = '█' * filled_length + ' ' * (bar_width - filled_length)
            
            # 格式：文件名+填充+|+柱状图+|+时间
            enhanced_lines.append(f"{filename}{padding}|{bar}|{time_part}")
    
    return enhanced_lines
    """键盘监听线程"""
    while True:
        try:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key == b'o' or key == b'O':  # 按 O 键打开上一个文件夹
                    last_folder = stats.get('last_target_folder', None)
                    if last_folder and os.path.exists(last_folder):
                        open_last_folder(last_folder)
                    else:
                        print("没有可打开的文件夹记录")
                elif key == b'q' or key == b'Q':  # 按 Q 键退出
                    print("收到退出信号")
                    stats['should_exit'] = True
                    break
            time.sleep(0.1)
        except Exception as e:
            print(f"键盘监听异常: {e}")
            break

def main_logic(stats):
    # 获取C4D当前文档的输出目录
    doc = c4d.documents.GetActiveDocument()
    if doc is None:
        print("没有打开的C4D文档")
        return
    
    render_data = doc.GetFirstRenderData()
    if render_data is None:
        print("无法获取渲染设置")
        return
        
    output_path = render_data[c4d.RDATA_PATH]
    if not output_path:
        print("未设置输出路径")
        return
        
    # 提取输出路径的目录部分
    base_dir = os.path.dirname(output_path)
    
    # 获取C4D工程文件所在目录
    doc_path = doc.GetDocumentPath()
    if not doc_path:
        print("C4D工程文件未保存，无法确定目录")
        return
    
    # 设置日志文件路径为C4D工程文件所在目录下的0文件夹
    log_dir = os.path.join(doc_path, "0")
    os.makedirs(log_dir, exist_ok=True)
    stats['log_dir'] = log_dir
    if 'history' not in stats:
        stats['history'] = []
    if 'render_monitor' not in stats:
        stats['render_monitor'] = C4DRenderMonitor()
    if 'last_log_save' not in stats:
        stats['last_log_save'] = 0
    
    history = stats['history']
    render_monitor = stats['render_monitor']
    
    # 每1秒保存一次记录（实时更新）
    current_time = time.time()
    if current_time - stats['last_log_save'] > 1:  # 1秒间隔
        save_cmd_content_to_log(stats)
        stats['last_log_save'] = current_time
    
    try:
        # 检查渲染状态
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
        total_render_time = stats.get('total_render_time', 0)  # 新增：纯渲染时间
        last_render_check = stats.get('last_render_check', time.time())
        is_first_run = stats.get('is_first_run', True)
        is_second_run = stats.get('is_second_run', False)
        moved_this_round = 0
        move_failed = False
        
        # 更新渲染时间统计
        current_time = time.time()
        if stats.get('was_rendering', False) and is_rendering:
            # 如果之前在渲染且现在还在渲染，累加渲染时间
            total_render_time += current_time - last_render_check
        
        stats['was_rendering'] = is_rendering
        stats['last_render_check'] = current_time
        
        # 第一步：分析所有PNG文件并确定序列，同时进行重命名
        base_dir = output_path
        sequences = {}
        renamed_files = []
        
        # 常见的通道后缀（大小写不敏感）
        channel_suffixes = ['alpha', 'zdepth', 'normal', 'roughness', 'metallic', 'specular', 'emission', 'ao', 'displacement', 'bump', 'diffuse', 'reflection', 'refraction']
        
        for filename in os.listdir(base_dir):
            if filename.lower().endswith('.png'):
                name, ext = os.path.splitext(filename)
                
                # 分析文件名结构：文件名.通道名.序号 或 文件名.序号
                basename = None
                num = None
                channel_suffix = None
                
                # Try channel format first: basename.channel.num
                match = re.search(r'(.+?)\.(.+?)\.(\d{4})$', name)
                if match:
                    basename = match.group(1)
                    channel_suffix = match.group(2)
                    num = match.group(3)
                else:
                    # Try main format: basename.num
                    match = re.search(r'(.+?)(\d{4})$', name)
                    if match:
                        basename = match.group(1)
                        num = match.group(2)
                        channel_suffix = None
                    else:
                        # No match, skip
                        continue
                
                if basename and num:
                    numlen = len(num)
                    seq_name = basename
                    
                    # 如果需要补零，进行重命名
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
                            # 将重命名后的文件添加到序列中
                            sequences.setdefault(seq_name, []).append((newname, channel_suffix))
                        except Exception as e:
                            print(f"重命名失败: {filename} -> {newname}, 错误: {e}")
                            # 重命名失败，使用原文件名
                            sequences.setdefault(seq_name, []).append((filename, channel_suffix))
                    else:
                        # 不需要重命名，直接添加到序列中
                        sequences.setdefault(seq_name, []).append((filename, channel_suffix))

        # 等待所有重命名操作完成
        time.sleep(0.1)
        
        # 第二步：根据已分析的序列移动文件
        for seq, file_info_list in sequences.items():
            # 创建主文件夹
            main_folder = os.path.join(base_dir, seq)
            os.makedirs(main_folder, exist_ok=True)
            
            # 记录最后处理的目标文件夹
            stats['last_target_folder'] = main_folder
            
            for file_info in file_info_list:
                filename, channel_suffix = file_info
                src = os.path.join(base_dir, filename)
                
                # 判断是否为通道图
                if channel_suffix:
                    # 通道图：在主文件夹下创建通道子文件夹
                    channel_folder = os.path.join(main_folder, channel_suffix)
                    os.makedirs(channel_folder, exist_ok=True)
                    dst = os.path.join(channel_folder, filename)
                    
                    # 通道图不参与计数和时间统计，静默移动
                    try:
                        shutil.move(src, dst)
                    except Exception:
                        pass
                else:
                    # 主文件：放入RGB子文件夹，参与计数和时间统计
                    rgb_folder = os.path.join(main_folder, "RGB")
                    os.makedirs(rgb_folder, exist_ok=True)
                    dst = os.path.join(rgb_folder, filename)
                    
                    try:
                        shutil.move(src, dst)
                        now = time.time()
                        
                        if is_first_run:
                            # 第一次运行，不记录时间间隔，只记录文件移动
                            history.append(f'"{filename}"[初始文件]')
                            moved_count += 1
                            moved_this_round += 1
                        elif is_second_run:
                            # 第二次运行，不记录时间间隔，标记为不完整渲染
                            history.append(f'"{filename}"[不完整渲染时长]')
                            moved_count += 1
                            moved_this_round += 1
                        else:
                            # 第三次运行开始，只有在渲染时才记录时间间隔
                            if last_move_time and is_rendering:
                                interval = now - last_move_time
                                total_interval += interval
                                if interval > max_interval:
                                    max_interval = interval
                                history.append(f'"{filename}"{format_seconds(interval)}')
                            elif last_move_time and not is_rendering:
                                # 渲染暂停时，显示暂停标记
                                history.append(f'"{filename}"[渲染暂停]')
                            else:
                                history.append(f'"{filename}"[00:00:00]')
                            moved_count += 1
                            moved_this_round += 1
                        
                        # 只有在渲染时才更新last_move_time
                        if is_rendering:
                            last_move_time = now
                    except Exception:
                        move_failed = True
                        # move失败不记录history，不增加moved_count和moved_this_round
                        pass
        # 处理运行状态转换
        if is_first_run:
            if moved_this_round > 0:
                # 第一次运行有文件被移动，记录第一次运行移动的文件数量并转换到第二次运行
                stats['first_run_moved'] = stats.get('first_run_moved', 0) + moved_this_round
                is_first_run = False
                is_second_run = True
            else:
                # 第一次运行没有文件，直接跳过到第二次运行状态
                is_first_run = False
                is_second_run = True
        elif is_second_run and moved_this_round > 0:
            # 第二次运行有文件被移动，记录第二次运行移动的文件数量并转换到正常运行
            stats['second_run_moved'] = stats.get('second_run_moved', 0) + moved_this_round
            is_second_run = False
            
        total_time = time.time() - program_start
        # 计算平均时间时，排除第一次和第二次运行的文件数量
        first_run_moved = stats.get('first_run_moved', 0)
        second_run_moved = stats.get('second_run_moved', 0)
        effective_moved_count = moved_count - first_run_moved - second_run_moved
        avg_interval = total_interval / effective_moved_count if effective_moved_count > 0 else 0
        dots = '.' * dot_count + ' ' * (3 - dot_count)
        
        # 渲染状态指示器
        render_indicator = "渲染中" if is_rendering else "⚪暂停中"
        
        stat_line = f"数量: {moved_count} | 最长: {format_seconds(max_interval)} | 平均: {format_seconds(avg_interval)} | 总渲染时间: {format_seconds(total_render_time)} | 程序运行时间: {format_seconds(total_time)} | {render_indicator} {dots}"
        
        os.system('cls')
        enhanced_history = generate_bar_chart_for_history(history)
        for line in enhanced_history:
            print(line)
        print(stat_line)
        dot_count = dot_count + 1 if dot_count < 3 else 1
        stats['last_move_time'] = last_move_time
        stats['max_interval'] = max_interval
        stats['total_interval'] = total_interval
        stats['total_render_time'] = total_render_time  # 保存总渲染时间
        stats['moved_count'] = moved_count
        stats['program_start'] = program_start
        stats['dot_count'] = dot_count
        stats['is_first_run'] = is_first_run
        stats['is_second_run'] = is_second_run
        stats['history'] = history
    except Exception as e:
        print(f"main_logic发生异常: {e}")

def get_log_file_path(stats=None):
    """获取当前会话的日志文件路径"""
    # 使用C4D工程目录下的0文件夹
    if stats and 'log_dir' in stats:
        log_dir = stats['log_dir']
    else:
        # 备用方案：使用脚本所在目录
        log_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 使用程序启动时间作为文件名的一部分，格式：记录_0818_1430.txt
    start_time = datetime.fromtimestamp(time.time()).strftime("%m%d_%H%M")
    log_file_name = f"记录_{start_time}.txt"
    return os.path.join(log_dir, log_file_name)

def save_cmd_content_to_log(stats=None):
    """保存当前程序状态到记录文件（替换模式）"""
    try:
        # 获取当前会话的日志文件路径
        if not hasattr(save_cmd_content_to_log, 'log_file_path'):
            save_cmd_content_to_log.log_file_path = get_log_file_path(stats)
        
        log_file_path = save_cmd_content_to_log.log_file_path
        
        # 获取当前时间戳
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 准备要写入的内容
        log_entry = f"{'='*60}\n"
        log_entry += f"C4D文件管理器运行记录\n"
        log_entry += f"{'='*60}\n"
        log_entry += f"程序文件: {os.path.basename(__file__)}\n"
        log_entry += f"最后更新: {current_time}\n"
        log_entry += f"{'='*60}\n\n"
        
        # 如果有stats参数，记录程序统计信息
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
            log_entry += f"当前运行状态: {'渲染中' if is_rendering else '⚪暂停中'}\n"
            log_entry += f"已处理文件数量: {moved_count}\n"
            log_entry += f"程序运行时长: {format_seconds(total_time)}\n"
            log_entry += f"总渲染时长: {format_seconds(total_render_time)}\n"
            log_entry += f"{'-'*60}\n"
            
            # 记录完整历史
            history = stats.get('history', [])
            if history:
                log_entry += f"文件处理历史:\n"
                # 显示所有历史记录（无限制）
                display_history = history
                
                # 生成带柱状图的历史记录（使用全局函数确保与CMD窗口完全一致）
                enhanced_history = generate_bar_chart_for_history(display_history)
                for line in enhanced_history:
                    log_entry += f"{line}\n"
                
                # 添加与CMD窗口相同的统计行
                log_entry += f"{'-'*60}\n"
                first_run_moved = stats.get('first_run_moved', 0)
                second_run_moved = stats.get('second_run_moved', 0)
                effective_moved_count = moved_count - first_run_moved - second_run_moved
                total_interval = stats.get('total_interval', 0)
                max_interval = stats.get('max_interval', 0)
                avg_interval = total_interval / effective_moved_count if effective_moved_count > 0 else 0
                
                # 生成与CMD窗口完全相同的统计行
                render_indicator = "渲染中" if is_rendering else "⚪暂停中"
                stat_line = f"数量: {moved_count} | 最长: {format_seconds(max_interval)} | 平均: {format_seconds(avg_interval)} | 总渲染时间: {format_seconds(total_render_time)} | 程序运行时间: {format_seconds(total_time)} | {render_indicator}"
                log_entry += f"{stat_line}\n"
            else:
                log_entry += f"暂无文件处理记录\n"
        
        log_entry += f"\n{'='*60}\n"
        log_entry += f"记录文件: {os.path.basename(log_file_path)}\n"
        log_entry += f"{'='*60}"
        
        # 覆盖写入到记录文件（替换模式）
        with open(log_file_path, 'w', encoding='utf-8') as f:
            f.write(log_entry)
            
    except Exception as e:
        print(f"保存记录失败: {e}")

def main():
    try:
        print("C4D文件管理器已启动")
        
        # 初始化程序启动时间（用于生成唯一的日志文件名）
        program_start_time = time.time()
        stats = {'last_move_time': None, 'moved_count': 0, 'program_start': program_start_time, 'should_exit': False}
        
        # 先执行一次main_logic来设置路径
        main_logic(stats)
        
        # 每次启动时创建新的记录文件并保存初始状态
        save_cmd_content_to_log(stats)
        print(f"已创建记录文件: 记录_{datetime.fromtimestamp(program_start_time).strftime('%m%d_%H%M')}.txt")
        
        # 启动键盘监听线程（如果可用）
        if msvcrt is not None:
            keyboard_thread = threading.Thread(target=keyboard_listener, args=(stats,), daemon=True)
            keyboard_thread.start()
        
        # 在C4D环境中，只执行一次文件处理
        print("正在处理文件...")
        main_logic(stats)
        save_cmd_content_to_log(stats)
        print("文件处理完成")
        
    except Exception as e:
        print(f"程序执行异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
else:
    # 在C4D中直接调用main函数
    main()