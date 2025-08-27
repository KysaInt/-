import subprocess
import time
import threading
import os
import sys
from pathlib import Path
from email.message import EmailMessage
import smtplib
from datetime import datetime

# 添加imap目录到路径，以便导入sm_simple
sys.path.append(str(Path(__file__).parent))

# 导入邮件发送功能
from sm_simple import compose_message, send_message_smtp

# 设备列表
devices = {
    'K': '10.241.223.253',
    'L': '10.241.56.155'
}

# 状态跟踪
status = {name: 'unknown' for name in devices}
success_count = {name: 0 for name in devices}
failure_count = {name: 0 for name in devices}

# 邮件配置
DEFAULT_RECIPIENT = "kysaint@Foxmail.com"
DEFAULT_SMTP_HOST = "smtp.qq.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_SMTP_USER = "kysaint@Foxmail.com"
DEFAULT_SMTP_PASSWORD = os.environ.get("DEFAULT_SMTP_PASSWORD")
DEFAULT_SMTP_PASS = os.environ.get("DEFAULT_SMTP_PASS")

def get_status_icon(status):
    """获取状态对应的图标"""
    if status == 'online':
        return '🟢'
    elif status == 'offline':
        return '🔴'
    elif status == 'unknown':
        return '🟡'
    else:
        return status

def send_notification_email(device_name, new_status, ip):
    """发送设备状态变化通知邮件"""
    try:
        if new_status == 'online':
            subject = "😚"
        elif new_status == 'offline':
            subject = "🥲"
        else:
            subject = "设备状态变化"
        
        body = f"{device_name},{new_status}"
        
        msg = compose_message(
            sender=DEFAULT_SMTP_USER,
            recipient=DEFAULT_RECIPIENT,
            subject=subject,
            body=body
        )
        
        # 优先级：环境变量SMTP_PASS > DEFAULT_SMTP_PASS > DEFAULT_SMTP_PASSWORD
        smtp_pass = os.environ.get("SMTP_PASS") or DEFAULT_SMTP_PASS or DEFAULT_SMTP_PASSWORD
        
        send_message_smtp(
            msg,
            host=DEFAULT_SMTP_HOST,
            port=DEFAULT_SMTP_PORT,
            user=DEFAULT_SMTP_USER,
            password=smtp_pass
        )
        
        print(f"√ {device_name} → {get_status_icon(new_status)}")
        
    except Exception as e:
        # 静默处理错误，不显示SMTP错误信息
        pass

def ping_device(ip):
    """Ping设备一次，返回True如果成功"""
    try:
        # 根据操作系统选择 ping 参数
        if os.name == 'nt':  # Windows
            result = subprocess.run(['ping', '-n', '1', ip], capture_output=True, text=True, timeout=1)
        else:  # Linux/Unix
            result = subprocess.run(['ping', '-c', '1', ip], capture_output=True, text=True, timeout=1)
        return result.returncode == 0
    except:
        return False

def ping_group():
    """执行一组ping，5次，每次间隔0.2秒"""
    results = {name: [] for name in devices}
    for _ in range(5):
        for name, ip in devices.items():
            success = ping_device(ip)
            results[name].append(success)
        time.sleep(0.2)
    return results

def update_status(results):
    """根据结果更新状态"""
    notifications = []  # 收集状态变化通知
    
    for name, pings in results.items():
        # 如果至少一次成功，则这组成功
        group_success = any(pings)
        old_status = status[name]
        
        if group_success:
            success_count[name] += 1
            failure_count[name] = 0
            if success_count[name] >= 3 and status[name] != 'online':
                old_status = status[name]
                status[name] = 'online'
                notifications.append(f"√ {name} → {get_status_icon('online')}")
                # 发送上线通知
                send_notification_email(name, 'online', devices[name])
        else:
            failure_count[name] += 1
            success_count[name] = 0
            if failure_count[name] >= 3 and status[name] in ['unknown', 'online']:
                old_status = status[name]
                status[name] = 'offline'
                notifications.append(f"× {name} → {get_status_icon('offline')}")
                # 发送离线通知
                send_notification_email(name, 'offline', devices[name])
    
    return notifications

def main():
    print("设备列表...")
    # 确保环境变量已设置
    smtp_pass = os.environ.get("SMTP_PASS") or DEFAULT_SMTP_PASS or DEFAULT_SMTP_PASSWORD
    if not smtp_pass:
        print("× 未找到SMTP密码环境变量")
        return
    
    try:
        while True:
            # 清屏
            os.system('cls' if os.name == 'nt' else 'clear')
            
            results = ping_group()
            notifications = update_status(results)
            
            # 显示标题
            print("设备状态监控")
            print("=" * 20)
            
            # 显示状态变化通知
            if notifications:
                for notification in notifications:
                    print(notification)
                print("-" * 20)
            
            # 显示当前状态
            for name in devices:
                status_icon = get_status_icon(status[name])
                ip = devices[name]
                print(f"{name}: {status_icon} ({ip})")
            
            print("=" * 20)
            print("按 Ctrl+C 退出")
            
            time.sleep(5)  # 每5秒一组
            
    except KeyboardInterrupt:
        print("\n监控已停止")

if __name__ == "__main__":
    main()
