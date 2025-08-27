#!/usr/bin/env python3
"""
下载、校验并执行指定 GitHub 文件的简单工具。

用法示例:
  python dl.py
  python dl.py --raw-url "https://raw.githubusercontent.com/KysaInt/-/main/通用/imap/SFTME.py" --out SFTME.py
  python dl.py --verify-sha256 <hex-sha256>

默认会将文件保存到脚本同目录下的 `SFTME.py`，并在下载后执行。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
import urllib.request
import urllib.parse
from typing import Optional


# 原始（未编码）raw URL 的构建，保留中文路径，让运行时做 percent-encoding
DEFAULT_RAW_URL_UNENCODED = "https://raw.githubusercontent.com/KysaInt/-/main/通用/imap/SFTME.py"


def download_to_path(url: str, out_path: str, timeout: int = 20) -> None:
    """下载 URL 到指定路径，原子写入（先写临时文件再移动）。抛出异常时不留下残留文件。"""
    # 确保 URL 中的非 ASCII 字符被百分号编码
    parsed = urllib.parse.urlsplit(url)
    # 对 path 和 query 做 safe 编码（保留 '/': True）
    path = urllib.parse.quote(parsed.path, safe='/')
    query = urllib.parse.quote_plus(parsed.query, safe='=&') if parsed.query else ''
    normalized = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, query, parsed.fragment))

    req = urllib.request.Request(normalized, headers={
        "User-Agent": "python-download-script/1.0"
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        # 在某些 Python 版本/实现中 resp 可能没有 .status
        if getattr(resp, 'status', None) is not None and resp.status >= 400:
            raise RuntimeError(f"HTTP 错误: {resp.status} {resp.reason}")
        data = resp.read()

    dirpath = os.path.dirname(os.path.abspath(out_path)) or os.getcwd()
    os.makedirs(dirpath, exist_ok=True)

    fd, tmpname = tempfile.mkstemp(dir=dirpath, prefix=".dl_tmp_", text=False)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        # 原子替换目标文件
        os.replace(tmpname, out_path)
    except Exception:
        try:
            os.remove(tmpname)
        except Exception:
            pass
        raise


def sha256_hex(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="下载并可选校验 GitHub raw 文件到本地")
    p.add_argument("--raw-url", default=DEFAULT_RAW_URL_UNENCODED, help="文件的 raw.githubusercontent.com URL（可以包含中文路径，脚本会编码）")
    # 默认保存到脚本同目录下的 SFTME.py
    default_out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SFTME.py")
    p.add_argument("--out", default=default_out, help=f"保存到本地的文件名或路径（默认：{default_out}）")
    p.add_argument("--verify-sha256", dest="sha256", help="如果提供，下载后校验文件的 SHA256（十六进制小写或大写均可）")
    p.add_argument("--timeout", type=int, default=20, help="下载超时（秒）")
    p.add_argument("--run-args", nargs=argparse.REMAINDER, help="传递给被执行脚本的额外参数（放在 --run-args 之后）")

    args = p.parse_args(argv)

    out_path = os.path.abspath(args.out)
    print(f"下载: {args.raw_url}\n保存到: {out_path}")

    try:
        download_to_path(args.raw_url, out_path, timeout=args.timeout)
    except Exception as e:
        print(f"下载失败: {e}")
        return 2

    if args.sha256:
        got = sha256_hex(out_path)
        expected = args.sha256.lower()
        print(f"计算 SHA256: {got}")
        if got != expected:
            print("SHA256 校验失败: 与提供的不匹配。删除已下载文件。")
            try:
                os.remove(out_path)
            except Exception:
                pass
            return 3
        print("SHA256 校验通过。")

    print("下载并保存成功。")

    # 在子进程中执行下载的文件
    cmd = [sys.executable, out_path]
    if args.run_args:
        # argparse.REMAINDER 会把所有剩余参数保留下来（可能包含前导 '--'）
        cmd.extend(args.run_args)
    print(f"运行: {cmd}")
    try:
        proc = subprocess.run(cmd)
        print(f"被执行脚本退出码: {proc.returncode}")
        return proc.returncode or 0
    except Exception as e:
        print(f"执行失败: {e}")
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
