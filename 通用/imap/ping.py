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

def send_notification_email(device_name, new_status, ip):
    """发送设备状态变化通知邮件"""
    try:
        subject = f"设备状态变化通知 - {device_name} ({ip})"
        
        if new_status == 'online':
            body = f"设备 {device_name} ({ip}) 已上线\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        elif new_status == 'offline':
            body = f"设备 {device_name} ({ip}) 已离线\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            body = f"设备 {device_name} ({ip}) 状态变化: {new_status}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
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
        
        print(f"✓ 邮件通知发送成功: {device_name} ({ip}) - {new_status}")
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"✗ SMTP认证失败: {e}")
        print(f"请检查用户名和密码设置")
    except smtplib.SMTPConnectError as e:
        print(f"✗ SMTP连接失败: {e}")
        print(f"请检查网络连接和SMTP服务器设置")
    except smtplib.SMTPException as e:
        print(f"✗ SMTP错误: {e}")
    except Exception as e:
        print(f"✗ 发送邮件失败: {e}")
        print(f"调试信息 - 密码长度: {len(smtp_pass) if smtp_pass else 0}")
        print(f"调试信息 - 用户: {DEFAULT_SMTP_USER}")
        print(f"调试信息 - 服务器: {DEFAULT_SMTP_HOST}:{DEFAULT_SMTP_PORT}")
        # 如果邮件实际发送成功了，这可能是误报
        print(f"注意: 如果邮件实际发送成功，请检查是否为误报")

def ping_device(ip):
    """Ping设备一次，返回True如果成功"""
    try:
        result = subprocess.run(['ping', '-n', '1', ip], capture_output=True, text=True, timeout=1)
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
    for name, pings in results.items():
        # 如果至少一次成功，则这组成功
        group_success = any(pings)
        old_status = status[name]
        
        if group_success:
            success_count[name] += 1
            failure_count[name] = 0
            if success_count[name] >= 3 and status[name] != 'online':
                status[name] = 'online'
                print(f"{name} 设备上线")
                # 发送上线通知
                send_notification_email(name, 'online', devices[name])
        else:
            failure_count[name] += 1
            success_count[name] = 0
            if failure_count[name] >= 3 and status[name] in ['unknown', 'online']:
                status[name] = 'offline'
                print(f"{name} 设备离线")
                # 发送离线通知
                send_notification_email(name, 'offline', devices[name])

def main():
    print("开始监控设备状态...")
    # 确保环境变量已设置
    smtp_pass = os.environ.get("SMTP_PASS") or DEFAULT_SMTP_PASS or DEFAULT_SMTP_PASSWORD
    if not smtp_pass:
        print("警告: 未找到SMTP密码环境变量，请运行set_env_vars.py设置")
    
    while True:
        results = ping_group()
        update_status(results)
        # 打印当前状态
        for name in devices:
            print(f"{name}: {status[name]} (成功:{success_count[name]}, 失败:{failure_count[name]})")
        time.sleep(5)  # 每5秒一组

if __name__ == "__main__":
    main()
