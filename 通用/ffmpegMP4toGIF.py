#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量使用 ffmpeg 将当前目录下所有 .mp4 视频转换为 GIF：
  画幅比例 50%, 25% 以及帧率 1~5 fps，共 10 种结果。

输出组织：目录名 <百分比%>_<fps> 例如 50%_5 ；
文件命名：<原名>_<百分比%>_<fps>.gif  例如 demo_50%_5.gif

采用单次命令内 split + palettegen + paletteuse（双阶段在一条命令内）确保色彩质量：
  - 先按 fps 取帧再缩放再 split 生成调色板
  - palettegen 使用 stats_mode=diff 提高动态场景颜色利用率
  - paletteuse 采用 dither=bayer，可调整参数

可调参数：SCALES, FPS_LIST, GIF_DITHER, GIF_LOOP, OVERWRITE 等。
依赖：需要 ffmpeg 在 PATH。
注意：目录名含 % 仅在 Windows cmd 手动输入时需转义；本脚本内部无影响。
"""

import subprocess
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# 配置部分 ------------------------------------------------------------
SCALES = [0.5, 0.25]          # 画幅缩放比例
FPS_LIST = [1, 2, 3, 4, 5]    # 帧率
VIDEO_EXTS = {'.mp4'}         # 可扩展
MAX_WORKERS = 4               # 并行线程数
OVERWRITE = False             # 输出已存在是否覆盖
GIF_DITHER = "bayer"          # 抖动算法，可选: none, bayer, floyd_steinberg, sierra2, sierra2_4a
GIF_BAYER_SCALE = 5           # bayer 抖动尺度 (0-5)，越高越粗糙
GIF_LOOP = 0                  # 0=循环，无穷；>0 指定循环次数
PALETTE_STATS_MODE = "diff"   # palettegen stats_mode 可选: full / single / diff
# --------------------------------------------------------------------

def check_ffmpeg() -> None:
    if shutil.which('ffmpeg') is None:
        print("[错误] 未找到 ffmpeg，请先安装并加入 PATH。https://ffmpeg.org/", file=sys.stderr)
        sys.exit(1)

def build_output_dir(base_dir: Path, scale: float, fps: int) -> Path:
    # 目录名示例：50%_5
    dir_name = f"{int(scale*100)}%_{fps}"
    dir_path = base_dir / dir_name
    dir_path.mkdir(exist_ok=True)
    return dir_path

def build_ffmpeg_cmd(src: Path, dst: Path, scale: float, fps: int) -> list:
    # 过滤器链：fps -> scale -> split -> palettegen -> paletteuse
    # 使用 lanczos 提升缩放质量
    vf = (
        f"fps={fps},scale=iw*{scale}:ih*{scale}:flags=lanczos,split[s0][s1];"\
        f"[s0]palettegen=stats_mode={PALETTE_STATS_MODE}[pal];"\
        f"[s1][pal]paletteuse=new=1:dither={GIF_DITHER}:bayer_scale={GIF_BAYER_SCALE}"
    )
    return [
        'ffmpeg', '-y' if OVERWRITE else '-n', '-i', str(src),
        '-vf', vf,
        '-loop', str(GIF_LOOP),
        str(dst)
    ]

def process_one(src: Path, base_dir: Path, scale: float, fps: int) -> tuple[Path, bool, str]:
    out_dir = build_output_dir(base_dir, scale, fps)
    file_name = f"{src.stem}_{int(scale*100)}%_{fps}.gif"
    dst = out_dir / file_name
    if dst.exists() and not OVERWRITE:
        return dst, False, "已存在，跳过"
    cmd = build_ffmpeg_cmd(src, dst, scale, fps)
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
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
    print("开始转换为 GIF (共 10 组合 * 文件数)...")
    tasks = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for src in videos:
            for s in SCALES:
                for f in FPS_LIST:
                    tasks.append(ex.submit(process_one, src, base_dir, s, f))
        finished = 0
        total = len(tasks)
        for fut in as_completed(tasks):
            finished += 1
            dst, ok, msg = fut.result()
            status = "[OK]" if ok else "[SKIP]" if msg.startswith("已存在") else "[ERR]"
            print(f"{status} ({finished}/{total}) {dst.name} -> {msg}")
    print("全部处理完成。")

if __name__ == '__main__':
    main()
