import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import subprocess
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import platform
import re

class NetworkMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("网络设备监控器")
        self.root.geometry("800x600")
        
        # 数据存储
        self.devices = {}  # IP -> {"name": "", "status": "", "last_status": "", "delay": 0, "last_online": "", "status_count": 0, "last_email_time": 0}
        self.monitoring = False
        self.monitor_thread = None
        self.update_interval = 30  # 默认30秒
        
        # 防抖动设置
        self.status_confirm_count = 3  # 需要连续几次确认状态变化
        self.email_cooldown = 300  # 邮件冷却时间（秒），5分钟
        
        # 邮件设置
        self.email_config = {
            "smtp_server": "",
            "smtp_port": 587,
            "username": "",
            "password": "",
            "from_email": "",
            "to_email": ""
        }
        
        self.create_gui()
        
        # 添加默认设备（在GUI创建之后）
        self.add_default_devices()
        
    def add_default_devices(self):
        """添加默认设备"""
        default_devices = [
            ("10.241.223.253", "K"),
            ("10.241.56.155", "L")
        ]
        
        for ip, name in default_devices:
            self.devices[ip] = {
                "name": name,
                "status": "未知",
                "confirmed_status": "未知",
                "pending_status": None,
                "last_status": "未知",
                "delay": 0,
                "packet_loss": 0.0,
                "last_online": "",
                "status_count": 0,
                "last_email_time": 0
            }
            # 使用print而不是log，因为GUI可能还没初始化
            print(f"添加默认设备: {name} ({ip})")
        
        # 更新设备列表显示
        if hasattr(self, 'device_tree'):
            self.update_device_list()
    
    def create_gui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 设备列表
        device_frame = ttk.LabelFrame(main_frame, text="设备列表", padding="5")
        device_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 设备列表框
        columns = ("IP", "名称", "状态", "延迟(ms)", "丢包率(%)", "确认进度", "最后在线时间")
        self.device_tree = ttk.Treeview(device_frame, columns=columns, show="headings", height=10)
        
        for col in columns:
            self.device_tree.heading(col, text=col)
            self.device_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(device_frame, orient=tk.VERTICAL, command=self.device_tree.yview)
        self.device_tree.configure(yscrollcommand=scrollbar.set)
        
        self.device_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # 设备操作按钮
        button_frame = ttk.Frame(device_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=5)
        
        ttk.Button(button_frame, text="添加设备", command=self.add_device).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="删除设备", command=self.remove_device).grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="编辑设备", command=self.edit_device).grid(row=0, column=2, padx=5)
        
        # 设置框架
        settings_frame = ttk.LabelFrame(main_frame, text="设置", padding="5")
        settings_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # ping频率设置
        ttk.Label(settings_frame, text="Ping频率(秒):").grid(row=0, column=0, sticky=tk.W)
        self.interval_var = tk.StringVar(value="5")
        ttk.Entry(settings_frame, textvariable=self.interval_var).grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        # 邮件设置
        ttk.Label(settings_frame, text="SMTP服务器:").grid(row=1, column=0, sticky=tk.W)
        self.smtp_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.smtp_var).grid(row=1, column=1, sticky=(tk.W, tk.E))
        
        ttk.Label(settings_frame, text="SMTP端口:").grid(row=2, column=0, sticky=tk.W)
        self.port_var = tk.StringVar(value="587")
        ttk.Entry(settings_frame, textvariable=self.port_var).grid(row=2, column=1, sticky=(tk.W, tk.E))
        
        ttk.Label(settings_frame, text="邮箱用户名:").grid(row=3, column=0, sticky=tk.W)
        self.username_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.username_var).grid(row=3, column=1, sticky=(tk.W, tk.E))
        
        ttk.Label(settings_frame, text="邮箱密码:").grid(row=4, column=0, sticky=tk.W)
        self.password_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.password_var, show="*").grid(row=4, column=1, sticky=(tk.W, tk.E))
        
        ttk.Label(settings_frame, text="发件人邮箱:").grid(row=5, column=0, sticky=tk.W)
        self.from_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.from_var).grid(row=5, column=1, sticky=(tk.W, tk.E))
        
        ttk.Label(settings_frame, text="收件人邮箱:").grid(row=6, column=0, sticky=tk.W)
        self.to_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.to_var).grid(row=6, column=1, sticky=(tk.W, tk.E))
        
        # 防抖动设置
        ttk.Label(settings_frame, text="状态确认次数:").grid(row=7, column=0, sticky=tk.W)
        self.confirm_count_var = tk.StringVar(value="3")
        ttk.Entry(settings_frame, textvariable=self.confirm_count_var).grid(row=7, column=1, sticky=(tk.W, tk.E))
        
        ttk.Label(settings_frame, text="邮件冷却时间(秒):").grid(row=8, column=0, sticky=tk.W)
        self.cooldown_var = tk.StringVar(value="300")
        ttk.Entry(settings_frame, textvariable=self.cooldown_var).grid(row=8, column=1, sticky=(tk.W, tk.E))
        
        # 控制按钮
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        self.start_btn = ttk.Button(control_frame, text="开始监控", command=self.start_monitoring)
        self.start_btn.grid(row=0, column=0, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="停止监控", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=5)
        
        self.refresh_btn = ttk.Button(control_frame, text="手动刷新", command=self.manual_refresh)
        self.refresh_btn.grid(row=0, column=2, padx=5)
        
        # 日志显示
        log_frame = ttk.LabelFrame(main_frame, text="日志", padding="5")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        device_frame.columnconfigure(0, weight=1)
        device_frame.rowconfigure(0, weight=1)
        settings_frame.columnconfigure(1, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
    def add_device(self):
        ip = simpledialog.askstring("添加设备", "请输入IP地址:")
        if ip:
            name = simpledialog.askstring("添加设备", "请输入设备名称:")
            if name:
                self.devices[ip] = {
                    "name": name,
                    "status": "未知",
                    "confirmed_status": "未知",
                    "pending_status": None,
                    "last_status": "未知",
                    "delay": 0,
                    "packet_loss": 0.0,
                    "last_online": "",
                    "status_count": 0,
                    "last_email_time": 0
                }
                self.update_device_list()
                self.log(f"添加设备: {name} ({ip})")
    
    def remove_device(self):
        selected = self.device_tree.selection()
        if selected:
            item = self.device_tree.item(selected[0])
            ip = item['values'][0]
            name = item['values'][1]
            if messagebox.askyesno("确认删除", f"确定要删除设备 {name} ({ip}) 吗?"):
                del self.devices[ip]
                self.update_device_list()
                self.log(f"删除设备: {name} ({ip})")
        else:
            messagebox.showwarning("警告", "请先选择要删除的设备")
    
    def edit_device(self):
        selected = self.device_tree.selection()
        if selected:
            item = self.device_tree.item(selected[0])
            ip = item['values'][0]
            name = item['values'][1]
            
            new_ip = simpledialog.askstring("编辑设备", "请输入新的IP地址:", initialvalue=ip)
            if new_ip and new_ip != ip:
                # 删除旧IP，添加新IP
                device_data = self.devices.pop(ip)
                device_data["name"] = simpledialog.askstring("编辑设备", "请输入新的设备名称:", initialvalue=name)
                self.devices[new_ip] = device_data
                self.update_device_list()
                self.log(f"编辑设备: {name} ({ip}) -> {device_data['name']} ({new_ip})")
            elif new_ip == ip:
                new_name = simpledialog.askstring("编辑设备", "请输入新的设备名称:", initialvalue=name)
                if new_name:
                    self.devices[ip]["name"] = new_name
                    self.update_device_list()
                    self.log(f"编辑设备名称: {name} -> {new_name} ({ip})")
        else:
            messagebox.showwarning("警告", "请先选择要编辑的设备")
    
    def update_device_list(self):
        """更新设备列表显示"""
        # 清空列表
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)
        
        # 添加设备
        for ip, data in self.devices.items():
            # 格式化延迟显示
            delay_value = data.get('delay', 0)
            delay_display = f"{delay_value:.1f}ms" if delay_value and delay_value > 0 else "N/A"
            
            # 格式化丢包率显示
            packet_loss_value = data.get('packet_loss', 0.0)
            packet_loss_display = f"{packet_loss_value:.1f}%" if packet_loss_value is not None else "N/A"
            
            # 格式化确认进度
            if data['status_count'] > 0:
                progress_display = f"{data['status_count']}/{self.status_confirm_count}"
            else:
                progress_display = "-"
            
            self.device_tree.insert("", tk.END, values=(
                ip,
                data["name"],
                data["status"],
                delay_display,
                packet_loss_display,
                progress_display,
                data["last_online"]
            ))
    
    def ping_device(self, ip):
        """Ping设备并返回延迟时间和丢包率"""
        try:
            if platform.system().lower() == "windows":
                # Windows ping命令：发送5个数据包，超时时间500ms
                cmd = ["ping", "-n", "5", "-w", "500", ip]
                self.log(f"执行ping命令: ping -n 5 -w 500 {ip}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)

                # 解析Windows ping结果
                success_count = 0
                total_delay = 0
                packet_loss = 100.0

                lines = result.stdout.split('\n')
                for line in lines:
                    line = line.strip()
                    # 查找成功的ping行 (Windows中文)
                    if '时间=' in line and 'ms' in line:
                        success_count += 1
                        # 提取延迟时间
                        match = re.search(r'时间=(\d+)ms', line)
                        if match:
                            total_delay += int(match.group(1))

                    # 查找成功的ping行 (Windows英文)
                    elif 'time=' in line and 'ms' in line:
                        success_count += 1
                        match = re.search(r'time=(\d+)ms', line)
                        if match:
                            total_delay += int(match.group(1))

                    # 查找统计行 (Windows中文)
                    elif '数据包:' in line:
                        match = re.search(r'已接收 = (\d+)', line)
                        if match:
                            success_count = int(match.group(1))

                        match = re.search(r'丢失 = \d+ \((\d+)%', line)
                        if match:
                            packet_loss = float(match.group(1))

                    # 查找统计行 (Windows英文)
                    elif 'Packets:' in line:
                        match = re.search(r'Received = (\d+)', line)
                        if match:
                            success_count = int(match.group(1))

                        match = re.search(r'Lost = \d+ \((\d+)% loss', line)
                        if match:
                            packet_loss = float(match.group(1))

                # 计算结果
                if success_count > 0:
                    avg_delay = total_delay / success_count if total_delay > 0 else 0
                    packet_loss = ((5 - success_count) / 5) * 100
                    self.log(f"Ping成功: {success_count}/5 包成功，平均延迟: {avg_delay:.1f}ms，丢包率: {packet_loss:.1f}%")
                    return avg_delay, packet_loss
                else:
                    self.log(f"Ping失败: {ip} 完全不可达 (5/5包丢失)")
                    return None, 100.0

            else:
                # Linux/Mac ping命令：发送5个数据包，超时时间0.5秒
                cmd = ["ping", "-c", "5", "-W", "0.5", ip]
                self.log(f"执行ping命令: ping -c 5 -W 0.5 {ip}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)

                if result.returncode == 0:
                    # 解析Linux/Mac ping结果
                    success_count = 0
                    total_delay = 0
                    packet_loss = 0.0

                    lines = result.stdout.split('\n')
                    for line in lines:
                        line = line.strip()

                        # 解析每一行的延迟
                        if 'time=' in line and 'ms' in line:
                            success_count += 1
                            match = re.search(r'time=(\d+\.?\d*) ms', line)
                            if match:
                                total_delay += float(match.group(1))

                        # 解析统计信息
                        elif 'packets transmitted' in line:
                            # "5 packets transmitted, 3 received, 40% packet loss"
                            match = re.search(r'(\d+) packets transmitted, (\d+) received, (\d+)% packet loss', line)
                            if match:
                                transmitted = int(match.group(1))
                                received = int(match.group(2))
                                packet_loss = float(match.group(3))
                                success_count = received

                    if success_count > 0:
                        avg_delay = total_delay / success_count
                        self.log(f"Ping成功: {success_count}/5 包成功，平均延迟: {avg_delay:.1f}ms，丢包率: {packet_loss:.1f}%")
                        return avg_delay, packet_loss
                    else:
                        self.log(f"Ping失败: {ip} 完全不可达 (5/5包丢失)")
                        return None, 100.0
                else:
                    self.log(f"Ping失败: {ip} 不可达")
                    return None, 100.0

        except Exception as e:
            self.log(f"Ping异常: {e}")
            return None, 100.0
    
    def send_email(self, subject, body):
        """发送邮件提醒"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config["from_email"]
            msg['To'] = self.email_config["to_email"]
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.email_config["smtp_server"], self.email_config["smtp_port"])
            server.starttls()
            server.login(self.email_config["username"], self.email_config["password"])
            text = msg.as_string()
            server.sendmail(self.email_config["from_email"], self.email_config["to_email"], text)
            server.quit()
            
            self.log("邮件发送成功")
            return True
        except Exception as e:
            self.log(f"邮件发送失败: {str(e)}")
            return False
    
    def check_status_change(self, ip, current_status):
        """检查设备状态变化并发送提醒（带防抖动机制）"""
        device = self.devices[ip]
        confirmed_status = device.get("confirmed_status", "未知")
        current_time = time.time()
        
        # 如果当前ping结果与已确认状态相同，重置计数器
        if current_status == confirmed_status:
            device["status_count"] = 0
            device["status"] = current_status
            return
        
        # 只有当ping结果与确认状态不同时，才需要确认过程
        # 也就是说：在线设备收到离线ping，或离线设备收到在线ping
        
        if device["status_count"] == 0:
            # 第一次检测到不同的状态，开始确认过程
            device["pending_status"] = current_status
            device["status_count"] = 1
            device["status"] = f"确认中({current_status})"
            self.log(f"检测到设备 {device['name']} ({ip}) 状态变化: {confirmed_status} -> {current_status} (1/{self.status_confirm_count})")
        elif device["pending_status"] == current_status:
            # 继续确认过程
            device["status_count"] += 1
            device["status"] = f"确认中({current_status})"
            
            if device["status_count"] >= self.status_confirm_count:
                # 确认完成，正式改变状态
                old_status = confirmed_status
                device["confirmed_status"] = current_status
                device["status"] = current_status
                device["status_count"] = 0
                
                # 检查是否需要发送邮件提醒
                if old_status != "未知":
                    # 检查邮件冷却时间
                    if current_time - device["last_email_time"] >= self.email_cooldown:
                        device_name = device["name"]
                        if current_status == "在线":
                            subject = f"设备上线提醒 - {device_name}"
                            body = f"设备 {device_name} ({ip}) 已上线\n时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n状态已稳定 {self.status_confirm_count} 次确认"
                            self.send_email(subject, body)
                        else:
                            subject = f"设备离线提醒 - {device_name}"
                            body = f"设备 {device_name} ({ip}) 已离线\n时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n状态已稳定 {self.status_confirm_count} 次确认"
                            self.send_email(subject, body)
                        
                        device["last_email_time"] = current_time
                        self.log(f"设备 {device_name} ({ip}) 状态变化已确认并发送邮件: {old_status} -> {current_status}")
                    else:
                        remaining_time = int(self.email_cooldown - (current_time - device["last_email_time"]))
                        self.log(f"设备 {device['name']} ({ip}) 邮件冷却中，还需等待 {remaining_time} 秒")
                
                if current_status == "在线":
                    device["last_online"] = time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                self.log(f"设备 {device['name']} ({ip}) 状态确认中: {confirmed_status} -> {current_status} ({device['status_count']}/{self.status_confirm_count})")
        else:
            # 状态又变回了原来的，重新开始计数
            device["pending_status"] = current_status
            device["status_count"] = 1
            device["status"] = f"确认中({current_status})"
            self.log(f"设备 {device['name']} ({ip}) 状态重新开始确认: {confirmed_status} -> {current_status} (1/{self.status_confirm_count})")
    
    def monitor_devices(self):
        """监控设备状态的主循环"""
        while self.monitoring:
            for ip in list(self.devices.keys()):
                ping_result = self.ping_device(ip)
                device = self.devices[ip]
                
                if ping_result is not None:
                    delay, packet_loss = ping_result
                    status = "在线"
                    device["delay"] = delay
                    device["packet_loss"] = packet_loss
                else:
                    status = "离线"
                    device["delay"] = 0
                    device["packet_loss"] = 100.0
                
                device["status"] = status
                self.check_status_change(ip, status)
            
            # 更新GUI
            self.root.after(0, self.update_device_list)
            
            # 等待下一次检查
            time.sleep(self.update_interval)
    
    def start_monitoring(self):
        # 获取设置
        try:
            self.update_interval = int(self.interval_var.get())
        except ValueError:
            messagebox.showerror("错误", "Ping频率必须是数字")
            return
        
        # 获取邮件设置
        self.email_config["smtp_server"] = self.smtp_var.get()
        try:
            self.email_config["smtp_port"] = int(self.port_var.get())
        except ValueError:
            messagebox.showerror("错误", "SMTP端口必须是数字")
            return
        self.email_config["username"] = self.username_var.get()
        self.email_config["password"] = self.password_var.get()
        self.email_config["from_email"] = self.from_var.get()
        self.email_config["to_email"] = self.to_var.get()
        
        # 获取防抖动设置
        try:
            self.status_confirm_count = int(self.confirm_count_var.get())
            self.email_cooldown = int(self.cooldown_var.get())
        except ValueError:
            messagebox.showerror("错误", "状态确认次数和冷却时间必须是数字")
            return
        
        if not self.devices:
            messagebox.showerror("错误", "请先添加要监控的设备")
            return
        
        if not all(self.email_config.values()):
            messagebox.showwarning("警告", "邮件设置不完整，状态变化将不会发送邮件提醒")
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_devices, daemon=True)
        self.monitor_thread.start()
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.log("开始监控设备...")
    
    def stop_monitoring(self):
        """停止监控设备"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.log("停止监控设备")
    
    def manual_refresh(self):
        """手动刷新设备状态"""
        if not self.devices:
            messagebox.showwarning("警告", "请先添加设备")
            return
        
        self.log("开始手动刷新...")
        for ip in list(self.devices.keys()):
            ping_result = self.ping_device(ip)
            device = self.devices[ip]
            
            if ping_result is not None:
                delay, packet_loss = ping_result
                status = "在线"
                device["delay"] = delay
                device["packet_loss"] = packet_loss
            else:
                status = "离线"
                device["delay"] = 0
                device["packet_loss"] = 100.0
            
            device["status"] = status
        
        self.update_device_list()
        self.log("手动刷新完成")
    
    def log(self, message):
        """添加日志"""
        timestamp = time.strftime('%H:%M:%S')
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)

if __name__ == "__main__":
    print("正在启动网络监控器...")
    try:
        root = tk.Tk()
        print("创建主窗口成功")
        app = NetworkMonitor(root)
        print("网络监控器初始化成功")
        print("启动主循环...")
        root.mainloop()
    except Exception as e:
        print(f"程序启动失败: {e}")
        import traceback
        traceback.print_exc()
