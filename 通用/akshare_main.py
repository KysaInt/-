"""AkShare 主程序（通用入口）

目标：尽量“功能全面”——不试图手写覆盖 AkShare 的所有主题接口，
而是提供一个统一的命令行入口：
- 搜索 akshare 的函数（按名称/文档）
- 查看函数签名与文档
- 运行任意函数（支持 kwargs、JSON 参数、缓存、导出）

示例：
  python 通用/akshare_main.py search stock
  python 通用/akshare_main.py describe stock_zh_a_hist
  python 通用/akshare_main.py run stock_zh_a_hist --param symbol=000001 --param period=daily --param start_date=20240101 --param end_date=20241231 --out out.csv

说明：
- 仅依赖 akshare + pandas（akshare 自带依赖）。
- 导出 .xlsx 需要环境里有 openpyxl；导出 .parquet 需要 pyarrow 或 fastparquet。
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import textwrap
import time
from typing import Any, Callable


def _try_import() -> tuple[Any, Any]:
    try:
        import akshare as ak  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SystemExit(
            "无法 import akshare。请先安装：pip install akshare\n"
            f"原始错误：{exc}"
        )

    try:
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SystemExit(
            "无法 import pandas。请先安装：pip install pandas\n"
            f"原始错误：{exc}"
        )

    return ak, pd


ak, pd = _try_import()


@dataclasses.dataclass(frozen=True)
class CacheOptions:
    enabled: bool
    dir_path: Path
    ttl_seconds: int


def _workspace_root() -> Path:
    # 以脚本所在目录为基准：通用/akshare_main.py -> workspace 根目录
    return Path(__file__).resolve().parents[1]


def _default_cache_dir() -> Path:
    return _workspace_root() / "ak_cache"


def _iter_ak_functions() -> dict[str, Callable[..., Any]]:
    funcs: dict[str, Callable[..., Any]] = {}
    for name, obj in inspect.getmembers(ak):
        if name.startswith("_"):
            continue
        if inspect.isfunction(obj):
            funcs[name] = obj
    return funcs


def _short_doc(obj: Any, max_lines: int = 4) -> str:
    doc = inspect.getdoc(obj) or ""
    lines = [line.rstrip() for line in doc.splitlines() if line.strip()]
    if not lines:
        return ""
    lines = lines[:max_lines]
    return "\n".join(lines)


def _print_kv(title: str, value: str) -> None:
    print(f"{title}: {value}")


def _smart_parse_value(raw: str) -> Any:
    text = raw.strip()

    # 允许通过 @file.json 读取 JSON
    if text.startswith("@"):
        file_path = Path(text[1:]).expanduser()
        content = file_path.read_text(encoding="utf-8")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content

    lowered = text.lower()
    if lowered in {"none", "null"}:
        return None
    if lowered in {"true", "false"}:
        return lowered == "true"

    # 优先按 JSON 解析（支持数字、数组、对象、字符串）
    try:
        return json.loads(text)
    except Exception:
        return text


def _parse_params(param_list: list[str]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    for item in param_list:
        if "=" not in item:
            raise SystemExit(f"参数格式错误：{item}，应为 key=value")
        key, raw_val = item.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit(f"参数 key 为空：{item}")
        kwargs[key] = _smart_parse_value(raw_val)
    return kwargs


def _hash_for_call(func_name: str, args: list[Any], kwargs: dict[str, Any]) -> str:
    payload = {
        "func": func_name,
        "args": args,
        "kwargs": kwargs,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _cache_paths(cache_dir: Path, key: str) -> tuple[Path, Path]:
    return cache_dir / f"{key}.pkl", cache_dir / f"{key}.meta.json"


def _cache_read(cache: CacheOptions, key: str) -> Any | None:
    if not cache.enabled:
        return None

    data_path, meta_path = _cache_paths(cache.dir_path, key)
    if not data_path.exists() or not meta_path.exists():
        return None

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        created = float(meta.get("created", 0))
    except Exception:
        return None

    if cache.ttl_seconds > 0 and (time.time() - created) > cache.ttl_seconds:
        return None

    try:
        return pd.read_pickle(data_path)
    except Exception:
        return None


def _cache_write(cache: CacheOptions, key: str, value: Any) -> None:
    if not cache.enabled:
        return

    cache.dir_path.mkdir(parents=True, exist_ok=True)
    data_path, meta_path = _cache_paths(cache.dir_path, key)

    try:
        pd.to_pickle(value, data_path)
        meta = {
            "created": time.time(),
            "created_iso": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # 缓存失败不影响主流程
        return


def _as_dataframe(result: Any) -> Any:
    # 尽量把常见返回值变成 DataFrame，便于统一导出
    if isinstance(result, pd.DataFrame):
        return result
    if isinstance(result, pd.Series):
        return result.to_frame()

    # 常见：list[dict] / list[list] / dict
    if isinstance(result, list):
        try:
            return pd.DataFrame(result)
        except Exception:
            return result
    if isinstance(result, dict):
        try:
            return pd.DataFrame([result])
        except Exception:
            return result

    return result


def _export(result: Any, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(result, pd.DataFrame):
        suffix = out_path.suffix.lower()
        if suffix == ".csv":
            result.to_csv(out_path, index=False, encoding="utf-8-sig")
            return
        if suffix in {".xlsx", ".xls"}:
            result.to_excel(out_path, index=False)
            return
        if suffix == ".json":
            out_path.write_text(
                result.to_json(orient="records", force_ascii=False, indent=2),
                encoding="utf-8",
            )
            return
        if suffix == ".parquet":
            result.to_parquet(out_path, index=False)
            return

        # 默认：pickle
        pd.to_pickle(result, out_path)
        return

    # 非 DataFrame：尽量 JSON
    try:
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    except Exception:
        out_path.write_text(str(result), encoding="utf-8")


def cmd_search(args: argparse.Namespace) -> int:
    funcs = _iter_ak_functions()
    keyword = (args.keyword or "").strip().lower()

    matches: list[tuple[str, str]] = []
    for name, fn in funcs.items():
        if not keyword:
            matches.append((name, _short_doc(fn, max_lines=2)))
            continue

        if keyword in name.lower():
            matches.append((name, _short_doc(fn, max_lines=2)))
            continue

        if args.search_doc:
            doc = (inspect.getdoc(fn) or "").lower()
            if keyword in doc:
                matches.append((name, _short_doc(fn, max_lines=2)))

    matches.sort(key=lambda x: x[0])
    if args.limit and args.limit > 0:
        matches = matches[: args.limit]

    for name, doc in matches:
        if doc:
            print(f"{name}\n{textwrap.indent(doc, '  ')}\n")
        else:
            print(name)

    _print_kv("total", str(len(matches)))
    return 0


def cmd_describe(args: argparse.Namespace) -> int:
    funcs = _iter_ak_functions()
    fn = funcs.get(args.func)
    if fn is None:
        raise SystemExit(f"未找到函数：{args.func}（可用 search 查）")

    try:
        sig = str(inspect.signature(fn))
    except Exception:
        sig = "(signature unavailable)"

    _print_kv("name", args.func)
    _print_kv("signature", f"{args.func}{sig}")
    doc = inspect.getdoc(fn) or ""
    if doc:
        print("\n" + doc)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    funcs = _iter_ak_functions()
    fn = funcs.get(args.func)
    if fn is None:
        raise SystemExit(f"未找到函数：{args.func}（可用 search 查）")

    kwargs = _parse_params(args.param or [])

    call_args: list[Any] = []
    if args.args_json:
        parsed = _smart_parse_value(args.args_json)
        if not isinstance(parsed, list):
            raise SystemExit("--args-json 必须是 JSON 数组，例如: [\"a\", 1]")
        call_args = parsed

    cache = CacheOptions(
        enabled=bool(args.cache),
        dir_path=Path(args.cache_dir).expanduser() if args.cache_dir else _default_cache_dir(),
        ttl_seconds=int(args.cache_ttl),
    )

    cache_key = _hash_for_call(args.func, call_args, kwargs)
    if cache.enabled:
        cached = _cache_read(cache, cache_key)
        if cached is not None:
            result = cached
            print(f"[cache hit] {cache_key}")
        else:
            result = fn(*call_args, **kwargs)
            _cache_write(cache, cache_key, result)
            print(f"[cache miss] {cache_key}")
    else:
        result = fn(*call_args, **kwargs)

    result = _as_dataframe(result)

    if args.out:
        out_path = Path(args.out)
        _export(result, out_path)
        print(f"saved: {out_path}")
        return 0

    # 默认：打印预览
    if isinstance(result, pd.DataFrame):
        print(f"shape: {result.shape}")
        with pd.option_context("display.max_rows", args.preview_rows, "display.max_columns", args.preview_cols):
            print(result.head(args.preview_rows))
        return 0

    try:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    except Exception:
        print(result)
    return 0


def cmd_info(_: argparse.Namespace) -> int:
    import platform

    _print_kv("python", sys.version.replace("\n", " "))
    _print_kv("platform", platform.platform())
    _print_kv("akshare", getattr(ak, "__version__", "unknown"))
    _print_kv("pandas", getattr(pd, "__version__", "unknown"))
    _print_kv("cache_dir", str(_default_cache_dir()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="akshare_main",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="AkShare 主程序（搜索/查看/运行任意接口）",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    p_info = sub.add_parser("info", help="显示环境与版本信息")
    p_info.set_defaults(func=cmd_info)

    p_search = sub.add_parser("search", help="搜索 akshare 函数")
    p_search.add_argument("keyword", nargs="?", default="", help="关键字（函数名/文档）")
    p_search.add_argument("--search-doc", action="store_true", help="同时搜索 docstring（更慢）")
    p_search.add_argument("--limit", type=int, default=50, help="最多显示多少条（0=不限制）")
    p_search.set_defaults(func=cmd_search)

    p_desc = sub.add_parser("describe", help="查看函数签名与文档")
    p_desc.add_argument("func", help="函数名，例如 stock_zh_a_hist")
    p_desc.set_defaults(func=cmd_describe)

    p_run = sub.add_parser("run", help="运行任意 akshare 函数")
    p_run.add_argument("func", help="函数名，例如 stock_zh_a_hist")
    p_run.add_argument(
        "--param",
        action="append",
        default=[],
        help="kwargs 参数，格式 key=value；value 支持 JSON；@file.json 读取文件",
    )
    p_run.add_argument(
        "--args-json",
        default="",
        help="位置参数 JSON 数组，例如 [\"foo\", 1]（大多数接口用不到）",
    )
    p_run.add_argument("--out", default="", help="导出路径：.csv/.xlsx/.json/.parquet 或 .pkl")

    p_run.add_argument("--cache", action="store_true", help="开启本地缓存（按函数+参数哈希）")
    p_run.add_argument("--cache-dir", default="", help="缓存目录（默认 workspace/ak_cache）")
    p_run.add_argument("--cache-ttl", type=int, default=0, help="缓存有效期秒数（0=不过期）")

    p_run.add_argument("--preview-rows", type=int, default=20, help="不导出时打印多少行预览")
    p_run.add_argument("--preview-cols", type=int, default=30, help="不导出时最多显示多少列")
    p_run.set_defaults(func=cmd_run)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
