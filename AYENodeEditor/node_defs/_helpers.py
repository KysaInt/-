"""
node_defs._helpers — 节点求值辅助函数
======================================
纯 Python，无 Qt 依赖，可被任何节点包导入。
"""
import math


def _n(i, k, d=0):
    """取数值，无法转换时返回默认值。"""
    v = i.get(k)
    if v is None:
        return d
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _s(i, k, d=""):
    v = i.get(k)
    return str(v) if v is not None else d


def _b(i, k, d=False):
    return bool(i.get(k, d))


def _l(i, k):
    v = i.get(k)
    return list(v) if isinstance(v, (list, tuple)) else []


def _safe_eval(expr, ctx):
    allowed = {
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "sqrt": math.sqrt, "abs": abs, "min": min, "max": max,
        "pow": pow, "round": round, "int": int, "float": float,
        "pi": math.pi, "e": math.e, "log": math.log, "log10": math.log10,
    }
    allowed.update(ctx)
    try:
        return eval(expr, {"__builtins__": {}}, allowed)
    except Exception:
        return 0
