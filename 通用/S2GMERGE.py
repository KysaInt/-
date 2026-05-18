from __future__ import annotations

import argparse
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
DATE_DIR_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class FrameFile:
    source_dir: Path
    path: Path
    frame_number: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Combine frame sequences from multiple ScreenToGif recording folders "
            "into one new renumbered sequence by copying files."
        )
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Root directory that contains the dated recording folders. Defaults to the current directory.",
    )
    parser.add_argument(
        "--output-name",
        help=(
            "Optional output folder name. Defaults to '<earliest-folder>整合' under the root directory."
        ),
    )
    parser.add_argument(
        "--start-index",
        type=int,
        help=(
            "First index to use in the merged sequence. Defaults to the first numbered frame found in the earliest source folder."
        ),
    )
    parser.add_argument(
        "--digits",
        type=int,
        help="Optional fixed number of digits for output file names, such as 5 for 00001.png. Defaults to no zero padding.",
    )
    parser.add_argument(
        "--include-non-dated",
        action="store_true",
        help="Also include subfolders whose names do not match the default ScreenToGif date pattern.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without creating the output folder or files.",
    )
    return parser.parse_args()


def get_candidate_directories(root: Path, include_non_dated: bool) -> list[Path]:
    directories = [path for path in root.iterdir() if path.is_dir()]
    if include_non_dated:
        return sorted(directories, key=lambda item: item.name)

    dated_directories = [path for path in directories if DATE_DIR_PATTERN.match(path.name)]
    return sorted(dated_directories, key=lambda item: item.name)


def collect_frames(directory: Path) -> list[FrameFile]:
    frames: list[FrameFile] = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if not path.stem.isdigit():
            continue
        frames.append(FrameFile(directory, path, int(path.stem)))
    return sorted(frames, key=lambda item: item.frame_number)


def resolve_output_directory(root: Path, directories: list[Path], output_name: str | None) -> Path:
    if output_name:
        return root / output_name

    earliest_name = directories[0].name
    return root / f"{earliest_name}整合"


def detect_output_padding(requested_digits: int | None) -> int | None:
    if requested_digits is not None:
        return requested_digits
    return None


def build_copy_plan(root: Path, include_non_dated: bool) -> tuple[list[Path], list[FrameFile]]:
    directories = get_candidate_directories(root, include_non_dated)
    if not directories:
        raise ValueError("No recording folders were found under the specified root directory.")

    all_frames: list[FrameFile] = []
    for directory in directories:
        all_frames.extend(collect_frames(directory))

    if not all_frames:
        raise ValueError("No numbered image files were found in the selected recording folders.")

    return directories, all_frames


def detect_start_index(frames: list[FrameFile], requested_start_index: int | None) -> int:
    if requested_start_index is not None:
        return requested_start_index
    return frames[0].frame_number


def copy_frames(
    frames: list[FrameFile],
    output_dir: Path,
    start_index: int,
    digits: int | None,
    dry_run: bool,
) -> None:
    if output_dir.exists() and any(output_dir.iterdir()) and not dry_run:
        raise ValueError(f"Output directory already exists and is not empty: {output_dir}")

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    for offset, frame in enumerate(frames):
        target_index = start_index + offset
        if digits is None:
            target_name = f"{target_index}{frame.path.suffix.lower()}"
        else:
            target_name = f"{target_index:0{digits}d}{frame.path.suffix.lower()}"
        target_path = output_dir / target_name

        if dry_run:
            print(f"[DRY-RUN] {frame.path} -> {target_path}")
            continue

        shutil.copy2(frame.path, target_path)


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()

    if not root.exists() or not root.is_dir():
        raise ValueError(f"Root directory does not exist or is not a directory: {root}")
    if args.start_index is not None and args.start_index < 0:
        raise ValueError("--start-index must be greater than or equal to 0.")
    if args.digits is not None and args.digits <= 0:
        raise ValueError("--digits must be greater than 0.")

    directories, frames = build_copy_plan(root, args.include_non_dated)
    output_dir = resolve_output_directory(root, directories, args.output_name)

    if output_dir in directories:
        raise ValueError(
            "Output directory conflicts with one of the source folders. Use --output-name to choose a different name."
        )

    start_index = detect_start_index(frames, args.start_index)
    digits = detect_output_padding(args.digits)

    print(f"Root directory: {root}")
    print(f"Source folders: {len(directories)}")
    print(f"Frames found: {len(frames)}")
    print(f"Output directory: {output_dir}")
    print(f"Start index: {start_index}")
    print(f"Filename digits: {digits if digits is not None else 'none'}")

    copy_frames(frames, output_dir, start_index, digits, args.dry_run)

    if args.dry_run:
        print("Dry run completed. No files were copied.")
    else:
        print("Copy completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())