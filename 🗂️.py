import os
import shutil
import re
import time
import sys
import subprocess
import threading
import msvcrt

FLAG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '⏳')

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
    folder_path = os.path.dirname(os.path.abspath(__file__))
    if 'history' not in stats:
        stats['history'] = []
    history = stats['history']
    try:
        last_move_time = stats.get('last_move_time', None)
        moved_count = stats.get('moved_count', 0)
        program_start = stats.get('program_start', time.time())
        dot_count = stats.get('dot_count', 1)
        max_interval = stats.get('max_interval', 0)
        total_interval = stats.get('total_interval', 0)
        is_first_run = stats.get('is_first_run', True)
        is_second_run = stats.get('is_second_run', False)
        moved_this_round = 0
        move_failed = False
        
        # 第一步：分析所有PNG文件并确定序列，同时进行重命名
        base_dir = folder_path
        sequences = {}
        renamed_files = []
        
        # 常见的通道后缀（大小写不敏感）
        channel_suffixes = ['alpha', 'zdepth', 'normal', 'roughness', 'metallic', 'specular', 'emission', 'ao', 'displacement', 'bump', 'diffuse', 'reflection', 'refraction']
        
        for filename in os.listdir(base_dir):
            if filename.lower().endswith('.png'):
                name, ext = os.path.splitext(filename)
                
                # 分析文件名结构：文件名+序号+.通道名称 或 文件名+序号
                # 首先查找数字序列
                match = re.search(r'(\d{1,4})(?:\.([^.]+))?$', name)
                if match:
                    num = match.group(1)
                    channel_suffix = match.group(2)  # 通道名称（如果存在）
                    numlen = len(num)
                    
                    # 确定基础文件名（去除序号和通道后缀）
                    if channel_suffix:
                        basename = name[:-(numlen + len(channel_suffix) + 1)]  # -1 for the dot
                    else:
                        basename = name[:-numlen]
                    
                    # 使用basename作为序列名
                    seq_name = basename
                    
                    # 如果需要补零，进行重命名
                    if 0 < numlen < 4:
                        newnum = num.zfill(4)
                        if channel_suffix:
                            newname = f"{basename}{newnum}.{channel_suffix}{ext}"
                        else:
                            newname = f"{basename}{newnum}{ext}"
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
                else:
                    # 没有数字结尾，使用整个文件名作为序列名
                    seq_name = name
                    sequences.setdefault(seq_name, []).append((filename, None))

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
                    # 通道图：在主文件夹下创建通道子文件夹（文件名+通道）
                    channel_folder_name = f"{seq}{channel_suffix}"
                    channel_folder = os.path.join(main_folder, channel_folder_name)
                    os.makedirs(channel_folder, exist_ok=True)
                    dst = os.path.join(channel_folder, filename)
                    
                    # 通道图不参与计数和时间统计，静默移动
                    try:
                        shutil.move(src, dst)
                    except Exception:
                        pass
                else:
                    # 主文件：直接放入主文件夹，参与计数和时间统计
                    dst = os.path.join(main_folder, filename)
                    
                    try:
                        shutil.move(src, dst)
                        now = time.time()
                        
                        if is_first_run:
                            # 第一次运行，不记录时间间隔，只记录文件移动
                            history.append(f'"{filename}"✔️[初始文件]')
                            moved_count += 1
                            moved_this_round += 1
                        elif is_second_run:
                            # 第二次运行，不记录时间间隔，标记为不完整渲染
                            history.append(f'"{filename}"✔️[不完整渲染时长]')
                            moved_count += 1
                            moved_this_round += 1
                        else:
                            # 第三次运行开始，正常记录时间间隔
                            if last_move_time:
                                interval = now - last_move_time
                                total_interval += interval
                                if interval > max_interval:
                                    max_interval = interval
                                history.append(f'"{filename}"✔️{format_seconds(interval)}')
                            else:
                                history.append(f'"{filename}"✔️[00:00:00]')
                            moved_count += 1
                            moved_this_round += 1
                        
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
        stat_line = f"数量: {moved_count} | 最长: {format_seconds(max_interval)} | 平均: {format_seconds(avg_interval)} | 总时间: {format_seconds(total_time)} {dots}"
        
        # 为每行历史记录生成带柱状图的显示
        def generate_bar_chart_for_history(history_lines):
            if not history_lines:
                return []
                
            # 分析所有历史记录，提取文件名和时间信息
            parsed_lines = []
            valid_intervals = []
            
            for line in history_lines:
                if "✔️" in line:
                    parts = line.split("✔️", 1)  # 只分割第一个✔️
                    filename_part = parts[0] + "✔️"
                    time_part = parts[1] if len(parts) > 1 else ""
                    
                    # 提取时间间隔（秒）
                    interval = 0
                    if "[初始文件]" not in time_part and "[不完整渲染时长]" not in time_part:
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
                        'is_special': "[初始文件]" in time_part or "[不完整渲染时长]" in time_part
                    })
                else:
                    # 不包含✔️的行，直接保持原样
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
                    
                    # 计算填充空格
                    padding = " " * (max_filename_length - len(filename))
                    
                    if is_special or interval == 0:
                        # 特殊状态或无时间间隔，显示空白柱状图
                        bar = '░' * bar_width
                    else:
                        # 正常渲染时间，显示比例柱状图
                        if max_time > min_time:
                            ratio = (interval - min_time) / (max_time - min_time)
                        else:
                            ratio = 1.0
                        
                        filled_length = int(bar_width * ratio)
                        bar = '█' * filled_length + '░' * (bar_width - filled_length)
                    
                    enhanced_lines.append(f"{filename}{padding}|{bar}|{time_part}")
            
            return enhanced_lines
        
        os.system('cls')
        enhanced_history = generate_bar_chart_for_history(history)
        for line in enhanced_history:
            print(line)
        print(stat_line)
        dot_count = dot_count + 1 if dot_count < 3 else 1
        stats['last_move_time'] = last_move_time
        stats['max_interval'] = max_interval
        stats['total_interval'] = total_interval
        stats['moved_count'] = moved_count
        stats['program_start'] = program_start
        stats['dot_count'] = dot_count
        stats['is_first_run'] = is_first_run
        stats['is_second_run'] = is_second_run
        stats['history'] = history
    except Exception as e:
        print(f"main_logic发生异常: {e}")

if __name__ == "__main__":
    script_path = os.path.abspath(__file__)
    script_dir, script_name = os.path.split(script_path)
    auto_name = script_name.replace('.py', '⏳.py')
    auto_path = os.path.join(script_dir, auto_name)
    if script_name.endswith('⏳.py'):
        # 恢复原名并退出自动运行
        orig_name = script_name.replace('⏳.py', '.py')
        orig_path = os.path.join(script_dir, orig_name)
        os.rename(script_path, orig_path)
        print("检测到自动运行标志，已关闭自动运行。")
        sys.exit(0)
    else:
        # 开启自动运行，重命名为⏳.py
        os.rename(script_path, auto_path)
        print("自动运行已开启。再次打开脚本将关闭自动运行。")
        stats = {'last_move_time': None, 'moved_count': 0, 'program_start': time.time(), 'should_exit': False}
        
        # 启动键盘监听线程
        keyboard_thread = threading.Thread(target=keyboard_listener, args=(stats,), daemon=True)
        keyboard_thread.start()
        
        try:
            while True:
                if stats.get('should_exit', False):
                    break
                main_logic(stats)
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            # 恢复原名
            stats['should_exit'] = True  # 停止键盘监听线程
            os.rename(auto_path, script_path)
            print("自动运行已关闭。")