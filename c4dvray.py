#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C4D渲染队列监听程序
监听Cinema 4D的渲染进程状态
当检测到渲染活动时输出1，否则输出0
"""

import psutil
import time
import sys
import os
import subprocess
import json
from datetime import datetime
from pathlib import Path


class C4DRenderMonitor:
    def __init__(self):
        """初始化监听器"""
        self.c4d_process_names = [
            'CINEMA 4D.exe',
            'Cinema 4D.exe', 
            'c4d.exe',
            'Commandline.exe',  # C4D命令行渲染
            'TeamRender Client.exe',  # 团队渲染客户端
            'TeamRender Server.exe'   # 团队渲染服务器
        ]
        self.is_rendering = False
        self.last_status = -1  # -1表示未初始化，0表示未渲染，1表示正在渲染
        self.log_file = Path(__file__).parent / "c4d_render_log.txt"
        self.status_file = Path(__file__).parent / "c4d_render_status.json"
        
    def log_message(self, message):
        """记录日志信息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"写入日志失败: {e}")
    
    def save_status(self, status):
        """保存状态到文件"""
        status_data = {
            'is_rendering': status,
            'timestamp': datetime.now().isoformat(),
            'last_check': time.time()
        }
        
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, indent=2)
        except Exception as e:
            self.log_message(f"保存状态失败: {e}")
    
    def check_c4d_processes(self):
        """检查C4D相关进程"""
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
        """检查C4D渲染队列相关文件"""
        # C4D通常在用户目录下的Maxon文件夹中存储渲染队列信息
        possible_paths = [
            os.path.expanduser("~/AppData/Roaming/Maxon"),
            os.path.expanduser("~/Documents/Maxon"),
            "C:\\ProgramData\\Maxon"
        ]
        
        queue_indicators = []
        
        for base_path in possible_paths:
            if os.path.exists(base_path):
                try:
                    # 查找渲染队列相关文件
                    for root, dirs, files in os.walk(base_path):
                        for file in files:
                            if any(keyword in file.lower() for keyword in ['queue', 'render', 'job']):
                                file_path = os.path.join(root, file)
                                # 检查文件最近修改时间
                                mtime = os.path.getmtime(file_path)
                                if time.time() - mtime < 60:  # 1分钟内修改的文件
                                    queue_indicators.append(file_path)
                except Exception:
                    continue
        
        return len(queue_indicators) > 0
    
    def monitor_render_status(self):
        """监听渲染状态的主函数"""
        while True:
            try:
                # 检查C4D进程
                processes = self.check_c4d_processes()
                
                # 检查渲染队列文件
                queue_active = self.check_render_queue_files()
                
                # 判断是否正在渲染
                process_rendering = self.is_rendering_active(processes)
                current_rendering = process_rendering or queue_active
                
                # 转换为整数状态
                current_status = 1 if current_rendering else 0
                
                # 如果状态发生变化，输出新状态
                if current_status != self.last_status:
                    print(current_status)
                    sys.stdout.flush()  # 确保立即输出
                    
                    # 记录状态变化
                    status_msg = "开始渲染" if current_status == 1 else "停止渲染"
                    self.log_message(f"状态变化: {status_msg} (进程数: {len(processes)})")
                    
                    # 保存状态
                    self.save_status(current_status)
                    
                    self.last_status = current_status
                
                # 等待一段时间再次检查
                time.sleep(2)  # 每2秒检查一次
                
            except KeyboardInterrupt:
                self.log_message("监听程序被用户中断")
                print(0)  # 退出时输出0
                break
            except Exception as e:
                self.log_message(f"监听过程中出现错误: {e}")
                time.sleep(5)  # 出错时等待更长时间


def main():
    """主函数"""
    print("C4D渲染队列监听程序已启动...")
    print("输出说明: 1=正在渲染, 0=未渲染")
    
    monitor = C4DRenderMonitor()
    monitor.log_message("C4D渲染监听程序启动")
    
    try:
        monitor.monitor_render_status()
    except Exception as e:
        monitor.log_message(f"程序异常退出: {e}")
        print(0)  # 异常退出时输出0


if __name__ == "__main__":
    main()