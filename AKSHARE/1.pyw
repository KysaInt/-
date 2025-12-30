# -*- coding: utf-8 -*-
import traceback
import importlib.util
import importlib.metadata
import os
import sys
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QComboBox,
    QFileDialog,
)


@dataclass(frozen=True)
class _ExampleApi:
    title: str
    func_name: str


class _FetchWorker(QObject):
    finished = Signal(str, object)
    failed = Signal(str)

    def __init__(self, api: _ExampleApi):
        super().__init__()
        self._api = api


_DEVNULL_STREAM = None


def _ensure_tqdm_safe_stdio():
    """为 .pyw/pythonw 环境补齐 stdout/stderr。

    在 Windows 的 pythonw 中，sys.stdout / sys.stderr 可能为 None，
    tqdm 默认写入 stderr，从而触发 "NoneType has no attribute write"。
    """
    global _DEVNULL_STREAM
    try:
        if _DEVNULL_STREAM is None:
            _DEVNULL_STREAM = open(os.devnull, "w", encoding="utf-8")

        for name in ("stdout", "stderr"):
            stream = getattr(sys, name, None)
            if stream is None or not hasattr(stream, "write"):
                setattr(sys, name, _DEVNULL_STREAM)
    except Exception:
        # 就算失败也不影响后续异常上报
        pass

    def run(self):
        try:
            _ensure_tqdm_safe_stdio()
            try:
                import akshare as ak  # type: ignore
            except Exception as e:
                raise RuntimeError(
                    "未检测到 akshare。请先安装：\n\n"
                    "pip install -U akshare\n"
                ) from e

            func: Optional[Callable] = getattr(ak, self._api.func_name, None)
            if func is None:
                raise RuntimeError(
                    f"当前 akshare 版本不包含接口：{self._api.func_name}\n"
                    "建议升级：pip install -U akshare"
                )

            df = func()
            # 统一把展示转成字符串，避免 UI 端依赖 pandas
            try:
                preview = df.head(200).to_string(index=False)
            except Exception:
                preview = str(df)

            header = f"[OK] {self._api.title}  (akshare.{self._api.func_name})\n\n"
            self.finished.emit(header + preview, df)
        except Exception as e:
            msg = str(e).strip() or repr(e)
            detail = traceback.format_exc(limit=8)
            self.failed.emit(msg + "\n\n" + detail)


class AKShareApp(QWidget):
    """模块1：AKShare 基本功能展示（最小可用）。"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._last_df = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[_FetchWorker] = None

        root = QVBoxLayout(self)

        self.label_title = QLabel("AKShare 模块1：基础示例")
        root.addWidget(self.label_title)

        # 顶部控制区
        row = QHBoxLayout()
        root.addLayout(row)

        self.combo = QComboBox()
        self._apis = [
            _ExampleApi("A股实时行情(东方财富)", "stock_zh_a_spot_em"),
            _ExampleApi("指数实时行情(东方财富)", "stock_zh_index_spot_em"),
            _ExampleApi("ETF 实时行情(东方财富)", "fund_etf_spot_em"),
        ]
        for api in self._apis:
            self.combo.addItem(api.title)
        row.addWidget(self.combo, 1)

        self.btn_fetch = QPushButton("获取数据")
        self.btn_save = QPushButton("保存CSV")
        self.btn_save.setEnabled(False)
        row.addWidget(self.btn_fetch)
        row.addWidget(self.btn_save)

        self.label_status = QLabel("状态：待命")
        root.addWidget(self.label_status)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        root.addWidget(self.text, 1)

        self.btn_fetch.clicked.connect(self._on_fetch)
        self.btn_save.clicked.connect(self._on_save)

        self._init_env_info()

    def _init_env_info(self):
        # 注意：不要在 UI 主线程 import akshare（会触发 pandas 导入，可能卡住启动）
        try:
            if importlib.util.find_spec("akshare") is None:
                self.label_status.setText("状态：未检测到 akshare（可先点“获取数据”查看安装提示）")
                return
            try:
                ver = importlib.metadata.version("akshare")
            except Exception:
                ver = "unknown"
            self.label_status.setText(f"状态：已检测到 akshare 版本 {ver}")
        except Exception:
            self.label_status.setText("状态：未检测到 akshare（可先点“获取数据”查看安装提示）")

    def _selected_api(self) -> _ExampleApi:
        idx = max(0, int(self.combo.currentIndex()))
        return self._apis[idx]

    def _set_busy(self, busy: bool):
        self.btn_fetch.setEnabled(not busy)
        self.combo.setEnabled(not busy)

    def _on_fetch(self):
        api = self._selected_api()
        self._set_busy(True)
        self.btn_save.setEnabled(False)
        self.label_status.setText("状态：正在获取数据…")
        self.text.setPlainText("")

        # 清理旧线程
        if self._thread is not None:
            try:
                self._thread.quit()
                self._thread.wait(300)
            except Exception:
                pass
            self._thread = None
            self._worker = None

        self._thread = QThread(self)
        self._worker = _FetchWorker(api)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_fetch_ok)
        self._worker.failed.connect(self._on_fetch_fail)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_fetch_ok(self, text: str, df_obj: object):
        self._last_df = df_obj
        self.text.setPlainText(text)
        self.label_status.setText("状态：完成")
        self._set_busy(False)
        self.btn_save.setEnabled(True)

    def _on_fetch_fail(self, err: str):
        self._last_df = None
        self.text.setPlainText("[ERROR]\n" + err)
        self.label_status.setText("状态：失败")
        self._set_busy(False)
        self.btn_save.setEnabled(False)

    def _on_save(self):
        if self._last_df is None:
            return

        path, _ = QFileDialog.getSaveFileName(self, "保存 CSV", "akshare.csv", "CSV Files (*.csv)")
        if not path:
            return

        try:
            df = self._last_df
            # 兼容 pandas DataFrame
            df.to_csv(path, index=False, encoding="utf-8-sig")
            self.label_status.setText(f"状态：已保存 {path}")
        except Exception as e:
            self.label_status.setText(f"状态：保存失败：{e}")

