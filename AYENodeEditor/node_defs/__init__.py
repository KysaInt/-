"""
node_defs — AYE Node Editor 节点注册包
========================================

自动加载本目录中所有以 ``_nodes.py`` 结尾的文件，并合并进
全局注册表。其他程序只需在此目录中新建一个 ``*_nodes.py``
（或运行时调用 ``register_pack``），即可向编辑器注入专属节点。

文件格式约定
------------
每个 ``*_nodes.py`` 文件按需定义以下模块级变量（均可省略）：

    NODE_DEFINITIONS    : dict  { name: ([inputs], [outputs]) }
    NODE_EVAL_FUNCS     : dict  { name: callable(inputs_dict, widget_value) }
    NODE_CATEGORIES     : dict  { cat_name: [node_names] }
    CATEGORY_COLORS_RGB : dict  { cat_name: (r, g, b) }

运行时 API
----------
    from node_defs import register_pack
    register_pack(definitions, eval_funcs, categories, colors_rgb)

也可以直接修改模块级字典（注意同步 _NODE_TO_CAT）：
    from node_defs import NODE_DEFINITIONS, NODE_EVAL_FUNCS, _NODE_TO_CAT
"""

import os
import glob
import importlib

# ── 公开注册表 ────────────────────────────────────────────────────────
NODE_DEFINITIONS    = {}   # { name: ([inputs], [outputs]) }
NODE_EVAL_FUNCS     = {}   # { name: callable }
NODE_CATEGORIES     = {}   # { cat_name: [node_names] }
CATEGORY_COLORS_RGB = {}   # { cat_name: (r, g, b) }
_NODE_TO_CAT        = {}   # { node_name: cat_name }


def register_pack(definitions=None, eval_funcs=None,
                  categories=None, colors_rgb=None):
    """
    将一组节点合并进全局注册表。

    Parameters
    ----------
    definitions  : dict | None
    eval_funcs   : dict | None
    categories   : dict | None   — 同名分类自动追加，不覆盖
    colors_rgb   : dict | None   — (r, g, b) 元组
    """
    if definitions:
        NODE_DEFINITIONS.update(definitions)
    if eval_funcs:
        NODE_EVAL_FUNCS.update(eval_funcs)
    if categories:
        for cat, nodes in categories.items():
            bucket = NODE_CATEGORIES.setdefault(cat, [])
            for n in nodes:
                if n not in bucket:
                    bucket.append(n)
    if colors_rgb:
        CATEGORY_COLORS_RGB.update(colors_rgb)

    # 重建快速查找表
    _NODE_TO_CAT.clear()
    for cat, ns in NODE_CATEGORIES.items():
        for n in ns:
            _NODE_TO_CAT[n] = cat


# ── 自动发现并加载 *_nodes.py ─────────────────────────────────────────
_here = os.path.dirname(__file__)
for _fp in sorted(glob.glob(os.path.join(_here, "*_nodes.py"))):
    _mod_name = os.path.splitext(os.path.basename(_fp))[0]
    _mod = importlib.import_module(f".{_mod_name}", package=__name__)
    register_pack(
        definitions = getattr(_mod, "NODE_DEFINITIONS",    None),
        eval_funcs  = getattr(_mod, "NODE_EVAL_FUNCS",     None),
        categories  = getattr(_mod, "NODE_CATEGORIES",     None),
        colors_rgb  = getattr(_mod, "CATEGORY_COLORS_RGB", None),
    )
