import os
from pathlib import Path

# 获取当前脚本所在目录
folder = Path(__file__).parent
folder_name = folder.name

# 获取所有文件（排除文件夹和脚本自身）
files = [f for f in folder.iterdir() if f.is_file() and f.name != Path(__file__).name]

# 按修改时间排序
files.sort(key=lambda f: f.stat().st_mtime)

# 重命名
for idx, file in enumerate(files, 1):
    new_name = f"{folder_name}{idx:04d}{file.suffix}"
    new_path = folder / new_name
    file.rename(new_path)
