#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from http.server import SimpleHTTPRequestHandler
from socketserver import ThreadingTCPServer


def is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


class ReuseTCPServer(ThreadingTCPServer):
    allow_reuse_address = True


def start_server(root: Path, host: str, port: int) -> ReuseTCPServer:
    os.chdir(str(root))
    httpd = ReuseTCPServer((host, port), SimpleHTTPRequestHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def detect_workspace_root(script_path: Path) -> Path:
    # script at <workspace>\BBL\serve.pyw → workspace root is parent of BBL
    bbl_dir = script_path.parent
    return bbl_dir.parent


def main():
    parser = argparse.ArgumentParser(description="Start a simple static HTTP server for BBL")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open", action="store_true", help="Open GAME.HTML in browser")
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    workspace_root = detect_workspace_root(script_path)
    bbl_game_url = f"http://{args.host}:{args.port}/BBL/GAME.HTML"

    first_run_flag = script_path.with_name(".first_run")

    if is_port_open(args.host, args.port):
        # Server already running
        if args.open:
            webbrowser.open(bbl_game_url)
        print(f"Server already running on {args.host}:{args.port}")
        return 0

    httpd = start_server(workspace_root, args.host, args.port)
    print(f"Static server started at http://{args.host}:{args.port} (root: {workspace_root})")

    if not first_run_flag.exists():
        try:
            first_run_flag.write_text("首次启动已初始化静态服务器。", encoding="utf-8")
        except Exception:
            pass

    # Give the server a moment, then open browser
    for _ in range(10):
        if is_port_open(args.host, args.port):
            break
        time.sleep(0.2)

    try:
        webbrowser.open(bbl_game_url)
    except Exception:
        print(f"Please open manually: {bbl_game_url}")

    try:
        # Keep the process alive; allow Ctrl+C to exit when run in console
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            httpd.shutdown()
        except Exception:
            pass
        print("Server stopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
