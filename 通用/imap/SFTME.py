from __future__ import annotations

import argparse
import os
import sys
import mimetypes
import getpass
import zipfile
import smtplib
from pathlib import Path
from datetime import datetime
from email.message import EmailMessage
from typing import List, Tuple, Optional


DEFAULT_RECIPIENT = "kysaint@Foxmail.com"
DEFAULT_SMTP_HOST = "smtp.qq.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_SMTP_USER = "kysaint@Foxmail.com"
# 注意：仓库中已有明文密码字段（风险自负），运行环境优先使用环境变量或命令行参数。
DEFAULT_SMTP_PASSWORD = "Ky.741953"
DEFAULT_SMTP_PASS = "vohqlhjgjebibbjg"


def read_title_and_body(txt_path: Path) -> Tuple[str, str]:
    text = txt_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    if not lines:
        return "(空主题)", ""
    subject = lines[0].strip()
    body = "\n".join(lines[1:]).strip()
    return subject or "(空主题)", body


def collect_attachments(directory: Path, skip_names: set[str]) -> List[Path]:
    files: List[Path] = []
    for p in sorted(directory.iterdir()):
        if p.is_file() and p.name not in skip_names:
            files.append(p)
    return files


def zip_attachments(attachments: List[Path], out_dir: Path) -> Optional[Path]:
    """把一组文件打包成一个 zip，返回 zip 的路径；没有附件时返回 None。"""
    if not attachments:
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"AYE'file_{timestamp}.zip"
    zip_path = out_dir / zip_name
    if zip_path.exists():
        try:
            zip_path.unlink()
        except Exception:
            pass

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in attachments:
            zf.write(f, arcname=f.name)

    return zip_path


def compose_message(sender: str, recipient: str, subject: str, body: str, attachments: List[Path]) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body or "(无正文)")

    for f in attachments:
        ctype, encoding = mimetypes.guess_type(str(f))
        if ctype is None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        with f.open("rb") as fp:
            data = fp.read()
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=f.name)

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
        print(f"目录不存在: {directory}")
        return 2

    # determine filenames to skip
    script_name = Path(__file__).name
    txt_name = "标题&正文.txt"
    skip_names = {script_name, txt_name}

    subject = ""
    body = ""
    txt_path = directory / txt_name
    if txt_path.exists() and txt_path.is_file():
        subject, body = read_title_and_body(txt_path)
    else:
        subject = f"自动发送 {directory.name} {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    attachments = collect_attachments(directory, skip_names)
    if not body:
        lines = ["附件列表:"]
        for a in attachments:
            lines.append(f"- {a.name} ({a.stat().st_size} bytes)")
        body = "\n".join(lines)

    # 将附件打包为单个 zip（如果有附件）
    zip_file = zip_attachments(attachments, directory)
    if zip_file:
        # 只发送 zip 文件作为附件
        attachments = [zip_file]

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

    msg = compose_message(sender=sender, recipient=args.to, subject=subject, body=body, attachments=attachments)

    print("================= 邮件预览 =================")
    print(f"From: {sender}")
    print(f"To: {args.to}")
    print(f"Subject: {subject}")
    print("附件:")
    for a in attachments:
        print(f" - {a.name} ({a.stat().st_size} bytes)")
    print("============================================")

    if args.dry_run:
        print("dry-run 模式，未实际发送邮件。")
        return 0

    # validate SMTP config
    if not args.smtp_host or not args.smtp_port:
        print("缺少 SMTP 主机或端口配置。请设置 SMTP_HOST/SMTP_PORT 环境变量或使用 --smtp-host/--smtp-port 参数。")
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
        print("邮件发送成功。")
        res_code = 0
    except Exception as e:
        print("发送邮件时出错:", e)
        res_code = 4
    finally:
        # 仅在真实发送（非 dry-run）情况下删除我们生成的 zip 文件
        try:
            if zip_file and zip_file.exists() and not args.dry_run:
                zip_file.unlink()
        except Exception:
            pass

    return res_code


if __name__ == "__main__":
    raise SystemExit(main())
