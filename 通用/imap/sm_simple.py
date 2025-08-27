from __future__ import annotations

import argparse
import os
import sys
import getpass
import smtplib
from pathlib import Path
from datetime import datetime
from email.message import EmailMessage
from typing import List, Tuple, Optional


DEFAULT_RECIPIENT = "kysaint@Foxmail.com"
DEFAULT_SMTP_HOST = "smtp.qq.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_SMTP_USER = "kysaint@Foxmail.com"
DEFAULT_SMTP_PASSWORD = os.environ.get("DEFAULT_SMTP_PASSWORD")
DEFAULT_SMTP_PASS = os.environ.get("DEFAULT_SMTP_PASS")


def compose_message(sender: str, recipient: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body or "(无正文)")

    return msg


def send_message_smtp(msg: EmailMessage, host: str, port: int, user: Optional[str], password: Optional[str]) -> None:
    # 使用 SMTP over SSL
    with smtplib.SMTP_SSL(host, port) as smtp:
        if user:
            smtp.login(user, password or "")
        smtp.send_message(msg)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="将当前目录下的文件发送为邮件（带附件）。")
    parser.add_argument("--to", default=DEFAULT_RECIPIENT, help="收件人邮箱，默认 kysaint@Foxmail.com")
    parser.add_argument("--dir", default=".", help="要扫描并发送的目录，默认当前目录")
    parser.add_argument("--dry-run", action="store_true", help="仅打印将要发送的内容，不实际连接 SMTP 发送")
    parser.add_argument("--smtp-host", default=os.environ.get("SMTP_HOST", DEFAULT_SMTP_HOST))
    parser.add_argument("--smtp-port", type=int, default=int(os.environ.get("SMTP_PORT", str(DEFAULT_SMTP_PORT))))
    parser.add_argument("--smtp-user", default=os.environ.get("SMTP_USER", DEFAULT_SMTP_USER))
    parser.add_argument("--smtp-pass", default=os.environ.get("SMTP_PASS"))
    parser.add_argument("--sender", default=os.environ.get("SMTP_USER", DEFAULT_SMTP_USER), help="发件人地址，默认使用 SMTP_USER")

    args = parser.parse_args(argv)

    directory = Path(args.dir).resolve()
    if not directory.exists() or not directory.is_dir():
        return 2

    subject = f"自动发送 {directory.name} {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    body = "自动发送邮件"

    sender = args.sender or args.smtp_user or os.environ.get("SMTP_USER") or DEFAULT_SMTP_USER
    smtp_user = args.smtp_user or os.environ.get("SMTP_USER") or DEFAULT_SMTP_USER
    # 优先级：命令行参数 > 环境变量 > 内置授权码/密码
    smtp_pass = args.smtp_pass or os.environ.get("SMTP_PASS") or DEFAULT_SMTP_PASS or DEFAULT_SMTP_PASSWORD
    if not smtp_pass and not args.dry_run:
        # prompt for password if not provided and we will send
        try:
            smtp_pass = getpass.getpass("SMTP 密码/授权码: ")
        except Exception:
            smtp_pass = None

    msg = compose_message(sender=sender, recipient=args.to, subject=subject, body=body)

    if args.dry_run:
        return 0

    # validate SMTP config
    if not args.smtp_host or not args.smtp_port:
        return 3
    if not smtp_user:
        smtp_user = DEFAULT_SMTP_USER
    if not smtp_pass:
        # 若脚本中未写入密码，则在运行时提示输入
        smtp_pass = getpass.getpass("SMTP 密码/授权码: ")

    # set From header to smtp_user if sender was empty
    if not sender:
        sender = smtp_user
        msg["From"] = sender

    res_code = 0
    try:
        send_message_smtp(msg, host=args.smtp_host, port=args.smtp_port, user=smtp_user, password=smtp_pass)
        print("发送成功")
        res_code = 0
    except Exception as e:
        print("发送失败")
        res_code = 4

    return res_code


if __name__ == "__main__":
    raise SystemExit(main())
