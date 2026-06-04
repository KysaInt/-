# -*- coding: utf-8 -*-
"""
module1_图形驱动.pyw
方案 B：VisualizerControlUI 嵌入 hub 面板，CircularVisualizerWindow 以独立透明浮窗运行。
MODULE_WIDGET = StandaloneVisualizerModule
"""
import sys
import importlib.util
import queue as _queue
from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout

_DIR = Path(__file__).parent

if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))


def _load_merged_module():
    path = _DIR / "0.pyw"
    if not path.exists():
        raise FileNotFoundError(f"未找到 0.pyw: {path}")
    spec = importlib.util.spec_from_file_location("viz_merged", str(path))
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(path)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_merged_module()


class StandaloneVisualizerModule(QWidget):
    """
    MODULE_WIDGET for hub（方案 B）:
    - VisualizerControlUI 嵌入 hub 右侧面板
    - CircularVisualizerWindow 以原始透明浮窗独立弹出（不嵌入 hub）
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._config_q = _queue.Queue(maxsize=1)
        self._status_q = _queue.Queue(maxsize=1)

        # 独立透明浮窗（embedded=False → 保留全部 Win32 透明/置顶样式）
        self._viz = _mod.CircularVisualizerWindow(
            config_queue=self._config_q,
            status_queue=self._status_q,
            embedded=False,
            parent=None,
        )

        # 控制面板嵌入 hub 面板
        self._ctrl = _mod.VisualizerControlUI()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._ctrl)

        self._patch_ctrl()
        try:
            self._config_q.put_nowait(self._ctrl.config)
        except Exception:
            pass

        # 独立模式：show() + frame_timer.start(16)
        self._viz.run()

    def _patch_ctrl(self):
        ctrl = self._ctrl
        viz = self._viz
        cfg_q = self._config_q
        sts_q = self._status_q

        ctrl.config_queue = cfg_q
        ctrl.status_queue = sts_q

        # 阻止 VisualizerControlUI 尝试启动子进程
        class _FakeAliveProcess:
            def is_alive(self):
                return True

        ctrl.viz_process = _FakeAliveProcess()

        def _start_standalone():
            try:
                cfg_q.put_nowait(ctrl.config)
            except Exception:
                pass
            if not viz.isVisible():
                viz.show()
            if not viz.frame_timer.isActive():
                viz.frame_timer.start(16)
            ctrl.status_timer.start(100)

        def _stop_standalone():
            ctrl.status_timer.stop()
            try:
                viz.frame_timer.stop()
                viz._cleanup()
            except Exception:
                pass
            try:
                viz.hide()
            except Exception:
                pass

        ctrl._start_visualizer = _start_standalone
        ctrl._stop_visualizer = _stop_standalone
        ctrl.status_timer.start(100)

    def _stop_visualizer(self):
        """hub closeEvent 调用的清理入口。"""
        try:
            self._ctrl._stop_visualizer()
        except Exception:
            pass
        try:
            self._viz.frame_timer.stop()
            self._viz._cleanup()
        except Exception:
            pass


MODULE_WIDGET = StandaloneVisualizerModule
