# -*- coding: utf-8 -*-
"""AkShare 主程序（带界面）

界面结构参考 tts/TTS_Main.pyw：
- 使用 form.ui + pyside6-uic 生成 ui_form.py
- 左侧导航 QListWidget + 右侧 QStackedWidget

功能（尽量全面）：
- 搜索 akshare 的函数（按名称/可选按 doc）
- 查看函数签名与 docstring
- 运行任意函数（kwargs/JSON 参数、缓存、导出）

说明：
- 本文件为 .pyw（无控制台），建议从资源管理器双击运行。
- 需要：PySide6、akshare、pandas
"""

from __future__ import annotations

import ctypes
import dataclasses
import datetime as _dt
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Optional


# 全局缓存，防止图标被 GC
_ICON_CACHE: dict[str, Any] = {}


def check_and_regenerate_ui() -> None:
    """确认并根据本目录的 form.ui 生成 ui_form.py（若缺失或过期）。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ui_file = os.path.join(script_dir, "form.ui")
    py_file = os.path.join(script_dir, "ui_form.py")

    if not os.path.exists(ui_file):
        raise SystemExit("缺少 GP/form.ui，无法启动界面")

    if (not os.path.exists(py_file)) or (os.path.getmtime(ui_file) > os.path.getmtime(py_file)):
        try:
            subprocess.run(["pyside6-uic", ui_file, "-o", py_file], check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise SystemExit(
                "生成 UI 失败：请确认已安装 PySide6，并且 pyside6-uic 可用\n"
                f"原始错误：{exc}"
            )


check_and_regenerate_ui()


def _try_import() -> tuple[Any, Any]:
    try:
        import akshare as ak  # type: ignore
    except Exception as exc:
        raise SystemExit(
            "无法 import akshare。请先安装：pip install akshare\n"
            f"原始错误：{exc}"
        )

    try:
        import pandas as pd  # type: ignore
    except Exception as exc:
        raise SystemExit(
            "无法 import pandas。请先安装：pip install pandas\n"
            f"原始错误：{exc}"
        )

    return ak, pd


ak, pd = _try_import()


from PySide6.QtCore import QAbstractTableModel, QObject, QModelIndex, Qt, QThread, Signal
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui_form import Ui_Widget


@dataclasses.dataclass(frozen=True)
class CacheOptions:
    enabled: bool
    dir_path: Path
    ttl_seconds: int


def _workspace_root() -> Path:
    # GP/akshare_main.pyw -> workspace 根目录
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


def _short_doc(obj: Any, max_lines: int = 3) -> str:
    doc = inspect.getdoc(obj) or ""
    lines = [line.rstrip() for line in doc.splitlines() if line.strip()]
    if not lines:
        return ""
    return "\n".join(lines[:max_lines])


def _smart_parse_value(raw: str) -> Any:
    text = raw.strip()

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

    try:
        return json.loads(text)
    except Exception:
        return text


def _parse_params_text(text: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue

        if "=" not in line:
            raise ValueError(f"参数格式错误：{line}，应为 key=value")
        key, raw_val = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"参数 key 为空：{line}")
        kwargs[key] = _smart_parse_value(raw_val)
    return kwargs


def _hash_for_call(func_name: str, args: list[Any], kwargs: dict[str, Any]) -> str:
    payload = {"func": func_name, "args": args, "kwargs": kwargs}
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
        return


def _as_dataframe(result: Any) -> Any:
    if isinstance(result, pd.DataFrame):
        return result
    if isinstance(result, pd.Series):
        return result.to_frame()

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


def _export_result(result: Any, out_path: Path) -> None:
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
            out_path.write_text(result.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
            return
        if suffix == ".parquet":
            result.to_parquet(out_path, index=False)
            return

        pd.to_pickle(result, out_path)
        return

    try:
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    except Exception:
        out_path.write_text(str(result), encoding="utf-8")


class DataFrameModel(QAbstractTableModel):
    def __init__(self, df: Any | None = None):
        super().__init__()
        self._df = df if isinstance(df, pd.DataFrame) else pd.DataFrame()

    def set_dataframe(self, df: Any) -> None:
        self.beginResetModel()
        self._df = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else int(self._df.shape[0])

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else int(self._df.shape[1])

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:  # noqa: ANN401
        if not index.isValid():
            return None
        if role not in (Qt.DisplayRole,):
            return None

        try:
            val = self._df.iat[index.row(), index.column()]
        except Exception:
            return None

        if pd.isna(val):
            return ""
        return str(val)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:  # noqa: ANN401
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            try:
                return str(self._df.columns[section])
            except Exception:
                return str(section)
        return str(section)


class AkCallWorker(QObject):
    finished = Signal(object, str)  # result, status
    failed = Signal(str)

    def __init__(self, func_name: str, args: list[Any], kwargs: dict[str, Any], cache: CacheOptions):
        super().__init__()
        self.func_name = func_name
        self.args = args
        self.kwargs = kwargs
        self.cache = cache

    def run(self) -> None:
        funcs = _iter_ak_functions()
        fn = funcs.get(self.func_name)
        if fn is None:
            self.failed.emit(f"未找到函数：{self.func_name}")
            return

        key = _hash_for_call(self.func_name, self.args, self.kwargs)
        if self.cache.enabled:
            cached = _cache_read(self.cache, key)
            if cached is not None:
                self.finished.emit(cached, f"cache hit: {key}")
                return

        try:
            result = fn(*self.args, **self.kwargs)
        except Exception as exc:
            self.failed.emit(f"执行失败：{exc}")
            return

        if self.cache.enabled:
            _cache_write(self.cache, key, result)
            self.finished.emit(result, f"cache miss: {key}")
        else:
            self.finished.emit(result, "ok")


class SearchWidget(QWidget):
    functionSelected = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.keyword = QLineEdit()
        self.keyword.setPlaceholderText("输入关键字（函数名；可选搜 doc）")

        self.search_doc = QCheckBox("同时搜索 docstring（更慢）")
        self.limit = QSpinBox()
        self.limit.setRange(0, 10000)
        self.limit.setValue(200)
        self.limit.setToolTip("最多显示多少条；0=不限制")

        self.btn_search = QPushButton("搜索")
        self.btn_search.clicked.connect(self.do_search)

        top = QHBoxLayout()
        top.addWidget(QLabel("关键字"))
        top.addWidget(self.keyword)
        top.addWidget(self.btn_search)

        opts = QHBoxLayout()
        opts.addWidget(self.search_doc)
        opts.addStretch(1)
        opts.addWidget(QLabel("limit"))
        opts.addWidget(self.limit)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._on_item_double_clicked)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(opts)
        layout.addWidget(QLabel("双击条目：发送到【说明/运行】"))
        layout.addWidget(self.list, 1)

        self.do_search()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.UserRole)
        if isinstance(name, str) and name:
            self.functionSelected.emit(name)

    def do_search(self) -> None:
        funcs = _iter_ak_functions()
        kw = self.keyword.text().strip().lower()
        search_doc = self.search_doc.isChecked()
        limit = int(self.limit.value())

        matches: list[tuple[str, str]] = []
        for name, fn in funcs.items():
            if not kw:
                matches.append((name, _short_doc(fn, 2)))
                continue

            if kw in name.lower():
                matches.append((name, _short_doc(fn, 2)))
                continue

            if search_doc:
                doc = (inspect.getdoc(fn) or "").lower()
                if kw in doc:
                    matches.append((name, _short_doc(fn, 2)))

        matches.sort(key=lambda x: x[0])
        if limit > 0:
            matches = matches[:limit]

        self.list.clear()
        for name, doc in matches:
            text = name if not doc else f"{name}\n  {doc.replace('\n', ' / ')}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, name)
            self.list.addItem(item)


class DescribeWidget(QWidget):
    functionSelected = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.func = QLineEdit()
        self.func.setPlaceholderText("输入函数名，例如 stock_zh_a_hist")

        self.btn_load = QPushButton("加载")
        self.btn_load.clicked.connect(self.load)

        self.btn_send_to_run = QPushButton("发送到运行")
        self.btn_send_to_run.clicked.connect(self._send_to_run)

        top = QHBoxLayout()
        top.addWidget(QLabel("函数"))
        top.addWidget(self.func)
        top.addWidget(self.btn_load)
        top.addWidget(self.btn_send_to_run)

        self.sig_label = QLabel("signature: ")
        self.sig_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.doc = QTextEdit()
        self.doc.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.sig_label)
        layout.addWidget(self.doc, 1)

    def set_func(self, name: str) -> None:
        self.func.setText(name)
        self.load()

    def _send_to_run(self) -> None:
        name = self.func.text().strip()
        if name:
            self.functionSelected.emit(name)

    def load(self) -> None:
        name = self.func.text().strip()
        if not name:
            return

        funcs = _iter_ak_functions()
        fn = funcs.get(name)
        if fn is None:
            self.sig_label.setText("signature: (not found)")
            self.doc.setPlainText("未找到该函数。可去【搜索】页找名称。")
            return

        try:
            sig = str(inspect.signature(fn))
        except Exception:
            sig = "(signature unavailable)"

        self.sig_label.setText(f"signature: {name}{sig}")
        self.doc.setPlainText(inspect.getdoc(fn) or "")


class RunWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.func = QLineEdit()
        self.func.setPlaceholderText("函数名，例如 stock_zh_a_hist")

        self.args_json = QLineEdit()
        self.args_json.setPlaceholderText('位置参数 JSON 数组，例如 ["foo", 1]（多数接口用不到）')

        self.params = QPlainTextEdit()
        self.params.setPlaceholderText(
            "每行一个参数：key=value\n"
            "value 支持 JSON（数字/数组/对象/字符串）\n"
            "@file.json 读取文件内容再解析\n"
            "# 开头为注释\n"
            "例：symbol=\"000001\"\nperiod=\"daily\"\nstart_date=20240101"
        )

        self.cache_enabled = QCheckBox("开启缓存")
        self.cache_enabled.setChecked(True)

        self.cache_ttl = QSpinBox()
        self.cache_ttl.setRange(0, 365 * 24 * 3600)
        self.cache_ttl.setValue(0)
        self.cache_ttl.setToolTip("缓存有效期（秒）；0=不过期")

        self.out_path = QLineEdit()
        self.out_path.setPlaceholderText("导出路径：.csv/.xlsx/.json/.parquet 或 .pkl（可空）")

        self.btn_browse = QPushButton("选择…")
        self.btn_browse.clicked.connect(self.browse)

        self.btn_run = QPushButton("执行")
        self.btn_run.clicked.connect(self.run)

        self.status = QLabel("")

        # 结果显示
        self.tabs = QTabWidget()
        self.table = QTableView()
        self.table_model = DataFrameModel()
        self.table.setModel(self.table_model)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)

        self.text = QTextEdit()
        self.text.setReadOnly(True)

        self.tabs.addTab(self.table, "表格")
        self.tabs.addTab(self.text, "文本")

        # --- 布局 ---
        gb = QGroupBox("调用")
        g = QGridLayout(gb)
        g.addWidget(QLabel("函数"), 0, 0)
        g.addWidget(self.func, 0, 1, 1, 3)
        g.addWidget(QLabel("args"), 1, 0)
        g.addWidget(self.args_json, 1, 1, 1, 3)
        g.addWidget(QLabel("导出"), 2, 0)
        g.addWidget(self.out_path, 2, 1, 1, 2)
        g.addWidget(self.btn_browse, 2, 3)

        g.addWidget(self.cache_enabled, 3, 0)
        g.addWidget(QLabel("TTL(s)"), 3, 1)
        g.addWidget(self.cache_ttl, 3, 2)
        g.addWidget(self.btn_run, 3, 3)

        layout = QVBoxLayout(self)
        layout.addWidget(gb)
        layout.addWidget(QLabel("kwargs 参数"))
        layout.addWidget(self.params, 1)
        layout.addWidget(self.status)
        layout.addWidget(self.tabs, 2)

        self._thread: QThread | None = None
        self._worker: AkCallWorker | None = None

    def set_func(self, name: str) -> None:
        self.func.setText(name)

    def browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "选择导出路径",
            str(_workspace_root()),
            "CSV (*.csv);;Excel (*.xlsx);;JSON (*.json);;Parquet (*.parquet);;Pickle (*.pkl)"
        )
        if path:
            self.out_path.setText(path)

    def _set_busy(self, busy: bool) -> None:
        self.btn_run.setEnabled(not busy)

    def run(self) -> None:
        name = self.func.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请先输入函数名")
            return

        try:
            kwargs = _parse_params_text(self.params.toPlainText())
        except Exception as exc:
            QMessageBox.critical(self, "参数错误", str(exc))
            return

        call_args: list[Any] = []
        if self.args_json.text().strip():
            try:
                parsed = _smart_parse_value(self.args_json.text())
            except Exception as exc:
                QMessageBox.critical(self, "args-json 错误", str(exc))
                return
            if not isinstance(parsed, list):
                QMessageBox.critical(self, "args-json 错误", "args 必须是 JSON 数组，例如 [\"a\", 1]")
                return
            call_args = parsed

        cache = CacheOptions(
            enabled=bool(self.cache_enabled.isChecked()),
            dir_path=_default_cache_dir(),
            ttl_seconds=int(self.cache_ttl.value()),
        )

        self.status.setText("执行中…")
        self.text.clear()
        self.table_model.set_dataframe(pd.DataFrame())
        self._set_busy(True)

        self._thread = QThread(self)
        self._worker = AkCallWorker(name, call_args, kwargs, cache)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_failed(self, msg: str) -> None:
        self._set_busy(False)
        self.status.setText(msg)
        self.text.setPlainText(msg)

    def _on_finished(self, result: Any, status: str) -> None:
        self._set_busy(False)
        self.status.setText(status)

        cooked = _as_dataframe(result)

        # 导出
        out = self.out_path.text().strip()
        if out:
            try:
                _export_result(cooked, Path(out))
                self.status.setText(f"{status} | saved: {out}")
            except Exception as exc:
                self.status.setText(f"{status} | 导出失败: {exc}")

        if isinstance(cooked, pd.DataFrame):
            self.table_model.set_dataframe(cooked)
            self.text.setPlainText(
                f"DataFrame shape={cooked.shape}\n\n" + cooked.head(50).to_string(index=False)
            )
            return

        try:
            self.text.setPlainText(json.dumps(cooked, ensure_ascii=False, indent=2, default=str))
        except Exception:
            self.text.setPlainText(str(cooked))


def _load_app_icon_with_fallbacks() -> Optional[QIcon]:
    # 与 tts/TTS_Main.pyw 类似：多路径回退
    if getattr(sys, "frozen", False):
        script_dir = os.path.dirname(sys.executable)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))

    icon_candidates = [
        os.path.join(script_dir, "icon.ico"),
        os.path.join(os.path.dirname(script_dir), "QT", "AYE", "icon.ico"),
        os.path.join(os.path.dirname(script_dir), "tts", "duck.ico"),
    ]

    for p in icon_candidates:
        p = os.path.normpath(os.path.abspath(p))
        if os.path.exists(p):
            ic = QIcon(p)
            if not ic.isNull():
                _ICON_CACHE["app_icon"] = ic
                return ic
    return None


class MainWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.ui = Ui_Widget()
        self.ui.setupUi(self)
        self.setWindowTitle("AkShare 工具")

        # --- 页面 1：搜索 ---
        page_layout_1 = self.ui.page_1.layout()
        while page_layout_1.count():
            item = page_layout_1.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self.search_widget = SearchWidget()
        page_layout_1.addWidget(self.search_widget)

        # --- 页面 2：说明 ---
        page_layout_2 = self.ui.page_2.layout()
        while page_layout_2.count():
            item = page_layout_2.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self.describe_widget = DescribeWidget()
        page_layout_2.addWidget(self.describe_widget)

        # --- 页面 3：运行 ---
        page_layout_3 = self.ui.page_3.layout()
        while page_layout_3.count():
            item = page_layout_3.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self.run_widget = RunWidget()
        page_layout_3.addWidget(self.run_widget)

        # --- 导航文案 ---
        self.ui.navigationList.item(0).setText("搜索")
        self.ui.navigationList.item(1).setText("说明")
        self.ui.navigationList.item(2).setText("运行")

        # --- 信号联动：双击搜索结果 -> 说明 & 运行 ---
        self.search_widget.functionSelected.connect(self.describe_widget.set_func)
        self.search_widget.functionSelected.connect(self.run_widget.set_func)
        self.describe_widget.functionSelected.connect(self.run_widget.set_func)


if __name__ == "__main__":
    # Windows: 设置 AUMID，有助任务栏图标关联
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AYE.AkShare.GUI.1.0")
        except Exception:
            pass

    try:
        QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setOrganizationName("AYE")
    app.setOrganizationDomain("local.aye")
    app.setApplicationName("AYE AkShare")
    app.setApplicationDisplayName("AkShare 工具")

    app_icon = _load_app_icon_with_fallbacks()
    if app_icon is not None and not app_icon.isNull():
        app.setWindowIcon(app_icon)

    w = MainWidget()
    if app_icon is not None and not app_icon.isNull():
        w.setWindowIcon(app_icon)

    # 默认窗口高度 900，居中（参考 tts/TTS_Main.pyw）
    try:
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry() if screen is not None else None
        if geo is not None:
            new_w = min(1100, int(geo.width() * 0.95))
            new_h = min(900, int(geo.height() * 0.95))
            x = geo.x() + max(0, int((geo.width() - new_w) / 2))
            y = geo.y() + max(0, int((geo.height() - new_h) / 2))
            w.setGeometry(x, y, new_w, new_h)
    except Exception:
        pass

    w.show()
    sys.exit(app.exec())
