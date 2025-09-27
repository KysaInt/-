"""简单爬虫模块

功能：
- 提供 fetch_url(url, output_path=None) 函数，返回抓取到的文本（HTML）。
- 支持命令行独立运行，参数为 URL 和可选保存路径。
"""
from __future__ import annotations

import sys
from typing import Optional
import requests


def fetch_url(url: str, output_path: Optional[str] = None) -> str:
    """抓取 URL 并返回文本内容。可选保存到文件。

    返回值：抓取到的文本（str）。抛出 requests.RequestException 用于上层处理。
    """
    headers = {
        "User-Agent": "mini_app_crawler/1.0 (+https://example.com)"
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    content = resp.text
    if output_path:
        with open(output_path, "w", encoding=resp.encoding or "utf-8") as f:
            f.write(content)
    return content


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("用法: python crawler_module.py <url> [output.html]")
        return 1
    url = argv[0]
    out = argv[1] if len(argv) > 1 else None
    try:
        html = fetch_url(url, out)
        print(f"已抓取 {len(html)} 字符")
        if not out:
            print(html[:1000])
        return 0
    except Exception as e:
        print(f"抓取失败: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
