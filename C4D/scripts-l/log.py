#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C4D 渲染队列日志读取器
使用 C4D Python API 读取渲染队列日志并输出到 CMD 窗口

支持功能：
- 读取 C4D 渲染队列的日志信息
- 显示渲染任务状态、时间、错误等
- 输出到 CMD 窗口
- 兼容 C4D Python 解释器

使用方法：
1. 在 C4D 中：脚本 > 用户脚本 > 运行脚本
2. 或在命令行：c4dpy resave.py
"""

import os
import sys
from pathlib import Path
import time

# C4D 模块导入
try:
    import c4d
    from c4d import documents, plugins, gui
    C4D_AVAILABLE = True
    print("检测到 C4D Python 环境")
except ImportError:
    C4D_AVAILABLE = False
    print("未检测到 C4D Python 环境，将作为独立脚本运行")

# 配置部分 ------------------------------------------------------------
LOG_UPDATE_INTERVAL = 2  # 日志更新间隔（秒）
MAX_LOG_ENTRIES = 50     # 最大显示的日志条目数
# --------------------------------------------------------------------

def c4d_print(message):
    """C4D 兼容的打印函数"""
    if C4D_AVAILABLE:
        try:
            c4d.GePrint(str(message))
        except:
            print(message)
    else:
        print(message)

def c4d_print_error(message):
    """C4D 兼容的错误打印函数"""
    if C4D_AVAILABLE:
        try:
            c4d.GePrint("[错误] " + str(message))
        except:
            print("[错误] " + str(message), file=sys.stderr)
    else:
        print("[错误] " + str(message), file=sys.stderr)

def get_render_queue_info():
    """获取渲染队列信息"""
    if not C4D_AVAILABLE:
        c4d_print_error("需要 C4D 环境才能获取渲染队列信息")
        return None

    try:
        # 获取渲染队列
        render_queue = documents.GetRenderQueue()
        if not render_queue:
            c4d_print_error("无法获取渲染队列")
            return None

        queue_info = {
            'total_jobs': 0,
            'completed_jobs': 0,
            'failed_jobs': 0,
            'running_jobs': 0,
            'pending_jobs': 0,
            'jobs': []
        }

        # 遍历渲染队列中的所有任务
        job_count = render_queue.GetJobCount()
        queue_info['total_jobs'] = job_count

        for i in range(job_count):
            job = render_queue.GetJob(i)
            if job:
                job_info = {
                    'index': i,
                    'name': job.GetName(),
                    'status': get_job_status(job),
                    'progress': job.GetProgress(),
                    'render_time': job.GetRenderTime(),
                    'output_path': job.GetOutputPath(),
                    'frame_from': job.GetFrameFrom(),
                    'frame_to': job.GetFrameTo(),
                    'last_message': job.GetLastMessage()
                }
                queue_info['jobs'].append(job_info)

                # 统计状态
                if job_info['status'] == 'completed':
                    queue_info['completed_jobs'] += 1
                elif job_info['status'] == 'failed':
                    queue_info['failed_jobs'] += 1
                elif job_info['status'] == 'running':
                    queue_info['running_jobs'] += 1
                elif job_info['status'] == 'pending':
                    queue_info['pending_jobs'] += 1

        return queue_info

    except Exception as e:
        c4d_print_error(f"获取渲染队列信息时出错: {e}")
        return None

def get_job_status(job):
    """获取任务状态"""
    if not C4D_AVAILABLE:
        return "unknown"

    try:
        status = job.GetStatus()
        if status == c4d.RENDERQUEUE_STATUS_PENDING:
            return "pending"
        elif status == c4d.RENDERQUEUE_STATUS_RENDERING:
            return "running"
        elif status == c4d.RENDERQUEUE_STATUS_COMPLETED:
            return "completed"
        elif status == c4d.RENDERQUEUE_STATUS_FAILED:
            return "failed"
        elif status == c4d.RENDERQUEUE_STATUS_PAUSED:
            return "paused"
        else:
            return "unknown"
    except:
        return "unknown"

def get_c4d_log_directory():
    """获取 C4D 日志目录"""
    if C4D_AVAILABLE:
        try:
            # 尝试获取 C4D 的偏好设置目录
            prefs_path = c4d.storage.GeGetC4DPath(c4d.C4D_PATH_PREFS)
            if prefs_path:
                log_dir = Path(prefs_path) / "logs"
                if log_dir.exists():
                    return log_dir
        except:
            pass

    # 默认返回当前目录
    return Path(__file__).parent

def read_c4d_log_files():
    """读取 C4D 日志文件"""
    log_dir = get_c4d_log_directory()
    log_files = []

    # 查找可能的日志文件
    possible_names = [
        "render.log",
        "c4d_render.log",
        "render_queue.log",
        "console.log",
        "c4d.log"
    ]

    for name in possible_names:
        log_file = log_dir / name
        if log_file.exists():
            log_files.append(log_file)

    # 也查找目录中的所有 .log 文件
    if log_dir.exists():
        for file in log_dir.iterdir():
            if file.is_file() and file.suffix.lower() == '.log':
                if file not in log_files:
                    log_files.append(file)

    return log_files

def parse_log_file(file_path):
    """解析日志文件内容"""
    log_entries = []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        for i, line in enumerate(lines[-MAX_LOG_ENTRIES:]):  # 只读取最后的部分
            entry = {
                'line_number': len(lines) - MAX_LOG_ENTRIES + i + 1,
                'content': line.strip(),
                'timestamp': None,
                'level': 'info'
            }

            # 尝试提取时间戳
            if '[' in line and ']' in line:
                try:
                    timestamp_part = line.split('[')[1].split(']')[0]
                    entry['timestamp'] = timestamp_part
                except:
                    pass

            # 判断日志级别
            line_lower = line.lower()
            if 'error' in line_lower or 'failed' in line_lower:
                entry['level'] = 'error'
            elif 'warning' in line_lower or 'warn' in line_lower:
                entry['level'] = 'warning'
            elif 'info' in line_lower:
                entry['level'] = 'info'

            log_entries.append(entry)

    except Exception as e:
        c4d_print_error(f"读取日志文件 {file_path} 时出错: {e}")

    return log_entries

def display_queue_status(queue_info):
    """显示渲染队列状态"""
    if not queue_info:
        return

    c4d_print("\n" + "="*60)
    c4d_print(" C4D 渲染队列状态")
    c4d_print("="*60)
    c4d_print(f"总任务数: {queue_info['total_jobs']}")
    c4d_print(f"✅ 已完成: {queue_info['completed_jobs']}")
    c4d_print(f"❌ 失败: {queue_info['failed_jobs']}")
    c4d_print(f" 运行中: {queue_info['running_jobs']}")
    c4d_print(f"⏳ 等待中: {queue_info['pending_jobs']}")
    c4d_print("")

    # 显示每个任务的详细信息
    for job in queue_info['jobs']:
        status_icon = {
            'pending': '⏳',
            'running': '',
            'completed': '✅',
            'failed': '❌',
            'paused': '⏸️',
            'unknown': '❓'
        }.get(job['status'], '❓')

        c4d_print(f"{status_icon} 任务 {job['index']+1}: {job['name']}")
        c4d_print(f"   状态: {job['status']}")
        c4d_print(f"   进度: {job['progress']:.1f}%")

        if job['render_time'] > 0:
            c4d_print(f"   渲染时间: {job['render_time']:.2f} 秒")

        if job['frame_from'] != job['frame_to']:
            c4d_print(f"   帧范围: {job['frame_from']} - {job['frame_to']}")

        if job['output_path']:
            c4d_print(f"   输出路径: {job['output_path']}")

        if job['last_message']:
            c4d_print(f"   最后消息: {job['last_message']}")

        c4d_print("")

def display_log_entries(log_entries, source_file):
    """显示日志条目"""
    if not log_entries:
        return

    c4d_print(f"\n 日志文件: {source_file}")
    c4d_print("-"*60)

    for entry in log_entries[-20:]:  # 只显示最后20条
        level_icon = {
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️'
        }.get(entry['level'], '')

        timestamp = f"[{entry['timestamp']}] " if entry['timestamp'] else ""
        c4d_print(f"{level_icon} {timestamp}{entry['content']}")

def monitor_render_queue():
    """监控渲染队列"""
    c4d_print(" 开始监控 C4D 渲染队列...")
    c4d_print("按 Ctrl+C 停止监控")

    try:
        while True:
            # 获取队列信息
            queue_info = get_render_queue_info()
            if queue_info:
                display_queue_status(queue_info)

            # 读取日志文件
            log_files = read_c4d_log_files()
            for log_file in log_files:
                log_entries = parse_log_file(log_file)
                display_log_entries(log_entries, log_file.name)

            # 检查是否所有任务都完成
            if queue_info and queue_info['running_jobs'] == 0 and queue_info['pending_jobs'] == 0:
                c4d_print("\n 所有渲染任务已完成！")
                break

            # 等待下次更新
            time.sleep(LOG_UPDATE_INTERVAL)
            c4d_print(f"\n⏰ {time.strftime('%H:%M:%S')} - 等待更新...")

    except KeyboardInterrupt:
        c4d_print("\n 监控已停止")
    except Exception as e:
        c4d_print_error(f"监控过程中出错: {e}")

def main():
    """主函数"""
    c4d_print(" C4D 渲染队列日志读取器")
    c4d_print("="*60)

    if not C4D_AVAILABLE:
        c4d_print_error("此脚本需要 C4D Python 环境才能正常工作")
        c4d_print("请在 C4D 中运行此脚本")
        return

    # 显示初始队列状态
    c4d_print(" 获取初始渲染队列状态...")
    queue_info = get_render_queue_info()
    if queue_info:
        display_queue_status(queue_info)

    # 显示日志文件
    c4d_print(" 读取日志文件...")
    log_files = read_c4d_log_files()
    if log_files:
        c4d_print(f"找到 {len(log_files)} 个日志文件:")
        for log_file in log_files:
            c4d_print(f"  - {log_file.name}")
    else:
        c4d_print("未找到日志文件")

    # 询问是否开始监控
    if C4D_AVAILABLE:
        try:
            result = c4d.gui.MessageDialog(
                "是否开始实时监控渲染队列？\n\n这将持续显示队列状态和日志更新。",
                c4d.GEMB_YESNO
            )
            if result == c4d.GEMB_R_YES:
                monitor_render_queue()
            else:
                c4d_print("ℹ️ 监控已取消。如需查看最新状态，请重新运行脚本。")
        except:
            # 如果GUI不可用，直接开始监控
            monitor_render_queue()
    else:
        monitor_render_queue()

if __name__ == '__main__':
    main()

# C4D 脚本入口点
def PluginMessage(id, data):
    """C4D 插件消息处理"""
    return True

# 在 C4D 中运行时自动执行
if C4D_AVAILABLE:
    main()
