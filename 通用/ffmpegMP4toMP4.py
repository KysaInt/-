#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量使用 ffmpeg 将当前目录下所有 .mp4 视频重新编码为 MP4：
  画幅比例 1, 0.75, 0.5 以及帧率 1/3, 1/2, 1倍原帧率，共 9 种结果。

输出组织：同目录下；
文件命名：<原名>_<画幅>画幅_<倍数>帧率.mp4  例如 demo_0.5画幅_1_2帧率.mp4

采用 ffmpeg 重新编码，确保质量：
  - 先按新帧率取帧再缩放
  - 使用 libx264 编码，preset medium
  - 如果设置 BITRATE，则使用固定比特率；否则使用 CRF 23（恒定质量）
  - 如果启用 USE_2PASS，则使用2-pass VBR编码（需设置BITRATE）

可调参数：SCALES, FPS_MULTIPLIERS, OVERWRITE, BITRATE, USE_2PASS 等。
依赖：需要 ffmpeg 和 ffprobe 在 PATH。
"""

import subprocess
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import json
import os

# 配置部分 ------------------------------------------------------------
SCALES = [1, 0.75, 0.5]       # 画幅缩放比例
FPS_MULTIPLIERS = [1/3, 0.5, 1]  # 帧率倍数
FPS_MULT_STR = ['1_3', '1_2', '1']  # 帧率倍数字符串，避免特殊字符
VIDEO_EXTS = {'.mp4'}         # 可扩展
MAX_WORKERS = min(8, os.cpu_count() or 4)  # 并行线程数，优化为CPU核心数或8
OVERWRITE = False             # 输出已存在是否覆盖
BITRATE = None                # 视频比特率，如 "1M"；如果使用2-pass，必须设置
USE_2PASS = False             # 是否使用2-pass VBR编码（需要设置BITRATE）
# --------------------------------------------------------------------

def check_ffmpeg() -> None:
    if shutil.which('ffmpeg') is None:
        print("[错误] 未找到 ffmpeg，请先安装并加入 PATH。https://ffmpeg.org/", file=sys.stderr)
        sys.exit(1)
    if shutil.which('ffprobe') is None:
        print("[错误] 未找到 ffprobe，请先安装并加入 PATH。https://ffmpeg.org/", file=sys.stderr)
        sys.exit(1)

def get_video_fps(src: Path) -> float:
    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', str(src)]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
    if res.returncode != 0:
        raise ValueError(f"无法获取视频信息: {src}")
    data = json.loads(res.stdout)
    for stream in data['streams']:
        if stream['codec_type'] == 'video':
            fps_str = stream['r_frame_rate']
            num, den = map(int, fps_str.split('/'))
            return num / den if den != 0 else 0
    raise ValueError(f"未找到视频流: {src}")

def build_ffmpeg_cmd(src: Path, dst: Path, scale: float, new_fps: float, pass_num: int = 0) -> list:
    # 过滤器链：fps -> scale
    # 使用 lanczos 提升缩放质量，确保输出尺寸为偶数
    vf = f"fps={new_fps},scale=trunc(iw*{scale}/2)*2:trunc(ih*{scale}/2)*2:flags=lanczos"
    cmd = [
        'ffmpeg', '-y' if OVERWRITE else '-n', '-i', str(src),
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'medium'
    ]
    if BITRATE:
        cmd.extend(['-b:v', BITRATE])
    else:
        cmd.extend(['-crf', '23'])
    if pass_num == 1:
        cmd.extend(['-pass', '1', '-f', 'null', 'NUL'])
    elif pass_num == 2:
        cmd.extend(['-pass', '2', '-c:a', 'copy', str(dst)])
    else:
        cmd.extend(['-c:a', 'copy', str(dst)])
    return cmd

def process_one(src: Path, base_dir: Path, scale: float, fps_mult: float, fps_mult_str: str, original_fps: float) -> tuple[Path, bool, str]:
    new_fps = original_fps * fps_mult
    file_name = f"{src.stem}_{scale}画幅_{fps_mult_str}帧率.mp4"
    dst = base_dir / file_name
    if dst.exists() and not OVERWRITE:
        return dst, False, "已存在，跳过"
    if USE_2PASS and BITRATE:
        # 第一遍
        cmd1 = build_ffmpeg_cmd(src, dst, scale, new_fps, 1)
        try:
            res1 = subprocess.run(cmd1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
            if res1.returncode != 0:
                return dst, False, f"第一遍失败 code={res1.returncode}\n{tail(res1.stdout)}"
        except Exception as e:
            return dst, False, f"第一遍异常: {e}"
        # 第二遍
        cmd2 = build_ffmpeg_cmd(src, dst, scale, new_fps, 2)
        try:
            res2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
            if res2.returncode != 0:
                return dst, False, f"第二遍失败 code={res2.returncode}\n{tail(res2.stdout)}"
            return dst, True, "成功 (2-pass)"
        except Exception as e:
            return dst, False, f"第二遍异常: {e}"
    else:
        cmd = build_ffmpeg_cmd(src, dst, scale, new_fps)
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
            if res.returncode != 0:
                return dst, False, f"失败 code={res.returncode}\n{tail(res.stdout)}"
            return dst, True, "成功"
        except Exception as e:
            return dst, False, f"异常: {e}"

def tail(text: str, lines: int = 12) -> str:
    data = text.strip().splitlines()
    return "\n".join(data[-lines:])

def gather_videos(directory: Path) -> list[Path]:
    videos = []
    for p in directory.iterdir():
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            videos.append(p)
    return sorted(videos)

def main():
    base_dir = Path(__file__).parent
    check_ffmpeg()
    videos = gather_videos(base_dir)
    if not videos:
        print("未找到任何 MP4 文件。")
        return
    print(f"发现 {len(videos)} 个视频：")
    for v in videos:
        print("  -", v.name)
    print("开始转换为 MP4 (共 9 组合 * 文件数)...")
    tasks = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for src in videos:
            try:
                original_fps = get_video_fps(src)
                print(f"  {src.name} 原始帧率: {original_fps} fps")
            except Exception as e:
                print(f"[错误] 无法获取 {src.name} 的帧率: {e}", file=sys.stderr)
                continue
            for fps_mult, fps_mult_str in zip(FPS_MULTIPLIERS, FPS_MULT_STR):
                for scale in SCALES:
                    tasks.append(ex.submit(process_one, src, base_dir, scale, fps_mult, fps_mult_str, original_fps))
        finished = 0
        total = len(tasks)
        for fut in as_completed(tasks):
            finished += 1
            dst, ok, msg = fut.result()
            status = "[OK]" if ok else "[SKIP]" if msg.startswith("已存在") else "[ERR]"
            progress = f"({finished}/{total}) {finished*100//total}%"
            print(f"\r\033[K{status} {progress} {dst.name} -> {msg}", end="", flush=True)
        print()  # 最后换行
    print("全部处理完成。")

if __name__ == '__main__':
    main()
