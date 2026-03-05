"""
AYE LiteGraph 启动器
====================
基于 LiteGraph.js + QWebEngineView 的节点编辑器桌面应用。
依赖: PySide6  (pip install PySide6)
      PySide6.QtWebEngineWidgets / PySide6.QtWebChannel  (已包含于 PySide6)
"""
import sys, os, json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog,
    QMessageBox, QStatusBar, QLabel,
)
from PySide6.QtCore import (
    Qt, QUrl, QObject, Slot, Signal,
    QStandardPaths,
)
from PySide6.QtGui import (
    QColor, QPalette, QKeySequence, QAction, QIcon,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebChannel import QWebChannel

# ── 错误日志重定向 ────────────────────────────────────────────────────
_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_litegraph_errors.log')
try:
    sys.stderr = open(_LOG_PATH, 'w', encoding='utf-8')
except Exception:
    pass

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'litegraph_editor_node_style.html')


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Python ↔ JS 桥接对象                                               ║
# ╚══════════════════════════════════════════════════════════════════════╝
class Bridge(QObject):
    """通过 QWebChannel 暴露给 JavaScript 的 Python 对象。"""

    # JS → Python 的信号槽
    # 发给 JS 的信号
    loadGraphData = Signal(str)   # 把 JSON 字符串推给 JS
    saveGraphData = Signal(str)   # 把保存路径推给 JS（JSend 实际写文件回调）

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._win = window
        self._current_path: str = ''

    @Slot(str, str)
    def action(self, act: str, payload: str):
        """JS 调用的统一入口。act: 'save'|'saveAs'|'openFile'"""
        if act == 'save':
            if self._current_path:
                self._write(self._current_path, payload)
                self._win.set_status(f'已保存: {self._current_path}')
            else:
                self._do_save_as(payload)
        elif act == 'saveAs':
            self._do_save_as(payload)
        elif act == 'openFile':
            self._do_open()

    @Slot(str, str)
    def writeFile(self, path: str, data: str):
        """直接写文件（来自 JS 的另一条路径）。"""
        self._write(path, data)

    # ── 内部方法 ──────────────────────────────────────────────────────
    def _write(self, path: str, data: str):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(data)
            self._current_path = path
            self._win.setWindowTitle(f'AYE LiteGraph — {os.path.basename(path)}')
        except Exception as e:
            QMessageBox.critical(self._win, '保存失败', str(e))

    def _do_save_as(self, payload: str = ''):
        start = self._current_path or QStandardPaths.writableLocation(
            QStandardPaths.DocumentsLocation)
        path, _ = QFileDialog.getSaveFileName(
            self._win, '保存图', start, '图文件 (*.json);;所有文件 (*)')
        if path:
            self._write(path, payload)
            self._win.set_status(f'已另存为: {path}')

    def _do_open(self):
        start = os.path.dirname(self._current_path) if self._current_path else \
            QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        path, _ = QFileDialog.getOpenFileName(
            self._win, '打开图', start, '图文件 (*.json);;所有文件 (*)')
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = f.read()
            json.loads(data)  # 校验 JSON
            self._current_path = path
            self._win.setWindowTitle(f'AYE LiteGraph — {os.path.basename(path)}')
            self.loadGraphData.emit(data)
            self._win.set_status(f'已打开: {path}')
        except Exception as e:
            QMessageBox.critical(self._win, '打开失败', str(e))

    # ── Python 主动触发的保存（来自菜单/快捷键）───────────────────────
    def trigger_save(self):
        """从 Python 端调用 JS 来获取图数据后保存。"""
        if self._current_path:
            script = f"_pyBridge && _pyBridge.action('save', JSON.stringify(graph.serialize(), null, 2));"
        else:
            script = f"_pyBridge && _pyBridge.action('saveAs', JSON.stringify(graph.serialize(), null, 2));"
        self._win.webview.page().runJavaScript(script)

    def trigger_save_as(self):
        script = "_pyBridge && _pyBridge.action('saveAs', JSON.stringify(graph.serialize(), null, 2));"
        self._win.webview.page().runJavaScript(script)

    def trigger_open(self):
        self._do_open()

    def trigger_new(self):
        self._current_path = ''
        self._win.setWindowTitle('AYE LiteGraph — 未命名')
        self._win.webview.page().runJavaScript("graph.clear(); statusMsg('新建图'); updateStats();")

    def trigger_run(self):
        self._win.webview.page().runJavaScript("runGraph();")


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  主窗口                                                              ║
# ╚══════════════════════════════════════════════════════════════════════╝
class LiteGraphWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('AYE LiteGraph 编辑器（Node 风格）')
        self.resize(1280, 800)

        # ── WebView ──────────────────────────────────────────────────
        self.webview = QWebEngineView()
        settings = self.webview.page().settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # ── WebChannel ───────────────────────────────────────────────
        self.channel = QWebChannel()
        self.bridge  = Bridge(self)
        self.channel.registerObject('bridge', self.bridge)
        self.webview.page().setWebChannel(self.channel)

        # 注入 qwebchannel.js（Qt 内置）
        self.webview.page().setWebChannel(self.channel)
        # 页面加载完成后注入 qwebchannel.js
        self.webview.loadFinished.connect(self._on_load_finished)

        self.setCentralWidget(self.webview)

        # ── 菜单栏 ───────────────────────────────────────────────────
        self._build_menu()

        # ── 状态栏 ───────────────────────────────────────────────────
        self._status_label = QLabel('就绪')
        self._status_label.setStyleSheet('color:#7acf7a; padding: 0 8px;')
        self.statusBar().addWidget(self._status_label)
        self.statusBar().setStyleSheet('background:#252525; border-top:1px solid #333;')

        # 加载 HTML
        self.webview.load(QUrl.fromLocalFile(HTML_PATH))

    # ── 菜单 ──────────────────────────────────────────────────────────
    def _build_menu(self):
        mb = self.menuBar()

        # 文件
        fm = mb.addMenu('文件(&F)')
        self._add_action(fm, '新建(&N)',   self.bridge.trigger_new,     'Ctrl+N')
        self._add_action(fm, '打开(&O)…', self.bridge.trigger_open,    'Ctrl+O')
        fm.addSeparator()
        self._add_action(fm, '保存(&S)',   self.bridge.trigger_save,    'Ctrl+S')
        self._add_action(fm, '另存为(&A)…', self.bridge.trigger_save_as, 'Ctrl+Shift+S')
        fm.addSeparator()
        self._add_action(fm, '退出(&Q)',   self.close, 'Alt+F4')

        # 运行
        rm = mb.addMenu('运行(&R)')
        self._add_action(rm, '▶ 运行图(&R)', self.bridge.trigger_run, 'F5')

        # 视图
        vm = mb.addMenu('视图(&V)')
        devAct = QAction('开发者工具', self, checkable=True)
        devAct.triggered.connect(self._toggle_devtools)
        vm.addAction(devAct)
        vm.addSeparator()
        self._add_action(vm, '重新加载页面', self._reload, 'F5')

        # 帮助
        hm = mb.addMenu('帮助(&H)')
        self._add_action(hm, 'LiteGraph.js 文档', lambda: self._open_url(
            'https://github.com/jagenjo/litegraph.js'))
        self._add_action(hm, '关于', self._about)

    def _add_action(self, menu, text, slot, shortcut=None):
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(slot)
        menu.addAction(act)

    def _toggle_devtools(self, checked):
        if checked:
            self._devtools = QWebEngineView()
            self.webview.page().setDevToolsPage(self._devtools.page())
            self._devtools.resize(900, 600)
            self._devtools.setWindowTitle('开发者工具')
            self._devtools.show()
        else:
            if hasattr(self, '_devtools'):
                self._devtools.close()

    def _reload(self):
        self.webview.reload()

    def _open_url(self, url):
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(url))

    def _about(self):
        QMessageBox.about(self, '关于 AYE LiteGraph',
            '<b>AYE LiteGraph 编辑器</b><br>'
            '基于 <a href="https://github.com/jagenjo/litegraph.js">LiteGraph.js</a><br>'
            '前端渲染 + PySide6 QWebEngineView 桌面应用<br><br>'
            '快捷键: 右键画布 = 添加节点 · Delete = 删除 · 鼠标中键/Alt+拖拽 = 平移')

    # ── WebChannel 注入 ───────────────────────────────────────────────
    def _on_load_finished(self, ok):
        if not ok:
            self.set_status('页面加载失败', error=True)
            return
        # 注入 Qt WebChannel JS 库
        script = """
(function() {
  if (typeof QWebChannel !== 'undefined') { _initChannel(); return; }
  var s = document.createElement('script');
  s.src = 'qrc:///qtwebchannel/qwebchannel.js';
  s.onload = function() { _initChannel(); };
  document.head.appendChild(s);
})();
"""
        self.webview.page().runJavaScript(script)
        self.set_status('页面已加载')

    # ── 状态栏 ───────────────────────────────────────────────────────
    def set_status(self, msg: str, error: bool = False):
        self._status_label.setText(msg)
        self._status_label.setStyleSheet(
            'color:#e07070; padding:0 8px;' if error else 'color:#7acf7a; padding:0 8px;')


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  入口                                                               ║
# ╚══════════════════════════════════════════════════════════════════════╝
def _dark_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window,          QColor(45,45,45))
    p.setColor(QPalette.WindowText,      Qt.white)
    p.setColor(QPalette.Base,            QColor(30,30,30))
    p.setColor(QPalette.AlternateBase,   QColor(50,50,50))
    p.setColor(QPalette.ToolTipBase,     QColor(25,25,25))
    p.setColor(QPalette.ToolTipText,     Qt.white)
    p.setColor(QPalette.Text,            QColor(220,220,220))
    p.setColor(QPalette.Button,          QColor(53,53,53))
    p.setColor(QPalette.ButtonText,      Qt.white)
    p.setColor(QPalette.BrightText,      Qt.red)
    p.setColor(QPalette.Link,            QColor(42,130,218))
    p.setColor(QPalette.Highlight,       QColor(42,130,218))
    p.setColor(QPalette.HighlightedText, Qt.black)
    p.setColor(QPalette.Mid,             QColor(70,70,70))
    p.setColor(QPalette.Midlight,        QColor(90,90,90))
    return p

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName('AYE LiteGraph NodeStyle')
    app.setPalette(_dark_palette())
    app.setStyleSheet("""
        QMainWindow   { background:#2d2d2d; }
        QMenuBar      { background:#2d2d2d; color:#ccc; border-bottom:1px solid #3a3a3a; }
        QMenuBar::item:selected { background:#3a3a3a; }
        QMenu         { background:#2a2a2a; color:#ccc; border:1px solid #444; }
        QMenu::item:selected { background:#2a82da; }
        QStatusBar    { background:#252525; color:#888; border-top:1px solid #333; }
        QMessageBox   { background:#2d2d2d; color:#ddd; }
        QPushButton   { background:#3a3a3a; color:#ddd; border:1px solid #555;
                        border-radius:3px; padding:4px 12px; }
        QPushButton:hover   { background:#454545; }
        QPushButton:pressed { background:#2a82da; }
    """)

    win = LiteGraphWindow()
    win.show()
    sys.exit(app.exec())
