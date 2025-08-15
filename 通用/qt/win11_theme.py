"""win11_theme — 可复用的主题管理模块

提供：
- 获取/设置 主题颜色（字典形式）
- 将主题保存到磁盘并在启动时恢复
- 可注册回调以便 UI 在运行时更新
- 可选的 Tkinter 应用器辅助函数（轻量）

设计目标：简单、跨平台、可被主程序导入并直接使用。
"""
from __future__ import annotations

import json
import os
import threading
from typing import Callable, Dict, Optional

# --- 默认主题定义 ---
DEFAULT_THEME: Dict[str, str] = {
	"background": "#0f1720",  # 深色窗体背景
	"foreground": "#e6eef6",  # 文字颜色
	"accent": "#0ea5e9",      # 强调色（按钮、链接）
	"highlight": "#1f2937",   # 面板/卡片背景
	"border": "#3b82f6",      # 边框/描边
	# 按钮专用配色（可独立于普通前景/背景）
	"button_bg": "#111827",
	"button_fg": "#e6eef6",
}


class ThemeManager:
	"""管理主题的加载、保存与运行时更新。"""

	def __init__(self, app_name: str = "win11_theme") -> None:
		self.app_name = app_name
		self._lock = threading.RLock()
		self._theme: Dict[str, str] = DEFAULT_THEME.copy()
		self._callbacks: list[Callable[[Dict[str, str]], None]] = []
		self._path = self._default_config_path(app_name)
		# 尝试加载磁盘上的主题（若存在）
		try:
			self.load()
		except Exception:
			# 忽略加载错误，保留默认主题
			pass

	# --- 配置文件路径 ---
	@staticmethod
	def _default_config_path(app_name: str) -> str:
		"""返回平台相关的默认配置文件路径（json）。"""
		if os.name == "nt":
			appdata = os.getenv("APPDATA") or os.path.expanduser("~")
			cfg_dir = os.path.join(appdata, app_name)
		else:
			home = os.path.expanduser("~")
			cfg_dir = os.path.join(home, ".config", app_name)
		os.makedirs(cfg_dir, exist_ok=True)
		return os.path.join(cfg_dir, "theme.json")

	# --- 读/写 ---
	def load(self) -> Dict[str, str]:
		"""从磁盘加载主题（若不存在则写入默认并返回默认）。"""
		with self._lock:
			if os.path.isfile(self._path):
				try:
					with open(self._path, "r", encoding="utf-8") as f:
						data = json.load(f)
					# 只接受 dict 且只保留已知键
					if isinstance(data, dict):
						for k in DEFAULT_THEME.keys():
							if k in data and isinstance(data[k], str):
								self._theme[k] = data[k]
				except Exception:
					# 任何解析错误都不应阻塞程序
					pass
			else:
				# 首次运行，写入默认主题
				self.save()
			return self._theme.copy()

	def save(self) -> None:
		"""将当前主题保存到磁盘。"""
		with self._lock:
			tmp_path = self._path + ".tmp"
			with open(tmp_path, "w", encoding="utf-8") as f:
				json.dump(self._theme, f, indent=2, ensure_ascii=False)
			# 原子替换
			try:
				os.replace(tmp_path, self._path)
			except Exception:
				# 如果替换失败，尝试直接写入目标
				with open(self._path, "w", encoding="utf-8") as f:
					json.dump(self._theme, f, indent=2, ensure_ascii=False)

	# --- 访问/修改 ---
	def get_theme(self) -> Dict[str, str]:
		with self._lock:
			return self._theme.copy()

	def set_theme(self, new_theme: Dict[str, str], persist: bool = True) -> None:
		"""用 new_theme 更新现有主题（只接受已知键）。

		persist: 是否立即保存到磁盘并触发回调。
		"""
		with self._lock:
			changed = False
			for k in DEFAULT_THEME.keys():
				if k in new_theme and isinstance(new_theme[k], str):
					if self._theme.get(k) != new_theme[k]:
						self._theme[k] = new_theme[k]
						changed = True
			if persist:
				self.save()
			if changed:
				self._notify()

	def set_color(self, key: str, value: str, persist: bool = True) -> None:
		"""设置单个颜色值（例如 'accent' 或 'background'）。"""
		if key not in DEFAULT_THEME:
			raise KeyError(f"Unknown theme key: {key}")
		with self._lock:
			if self._theme.get(key) == value:
				return
			self._theme[key] = value
			if persist:
				self.save()
			self._notify()

	def reset(self, persist: bool = True) -> None:
		"""重置为默认主题。"""
		with self._lock:
			self._theme = DEFAULT_THEME.copy()
			if persist:
				self.save()
			self._notify()

	# --- 回调机制 ---
	def register_callback(self, fn: Callable[[Dict[str, str]], None]) -> None:
		"""注册一个回调，主题变更时会被调用（立即不会触发）。"""
		with self._lock:
			if fn not in self._callbacks:
				self._callbacks.append(fn)

	def unregister_callback(self, fn: Callable[[Dict[str, str]], None]) -> None:
		with self._lock:
			if fn in self._callbacks:
				self._callbacks.remove(fn)

	def _notify(self) -> None:
		snapshot = self.get_theme()
		for cb in list(self._callbacks):
			try:
				cb(snapshot)
			except Exception:
				# 回调不应打断主题系统
				pass

	# --- 小工具（针对 Tkinter 的轻量应用） ---
	def apply_to_tk(self, tk_widget) -> None:
		"""尝试把主题应用到一个 tkinter 小部件（浅尝辄止）。

		使用方式示例： ThemeManager().apply_to_tk(root)
		注意：不同组件支持的属性不同，函数尝试设置常见的 bg/fg/activebackground 等。
		"""
		theme = self.get_theme()
		try:
			cfg = {}
			# 常见属性
			cfg["bg"] = theme.get("background")
			cfg["fg"] = theme.get("foreground")
			# 部分小部件支持 highlightbackground
			if hasattr(tk_widget, "configure"):
				try:
					tk_widget.configure(**cfg)
				except Exception:
					# 忽略不支持的属性
					pass
		except Exception:
			pass


# --- 模块级的单例与快捷函数 ---
_DEFAULT_MANAGER: Optional[ThemeManager] = None


def get_manager(app_name: str = "win11_theme") -> ThemeManager:
	global _DEFAULT_MANAGER
	if _DEFAULT_MANAGER is None or _DEFAULT_MANAGER.app_name != app_name:
		_DEFAULT_MANAGER = ThemeManager(app_name=app_name)
	return _DEFAULT_MANAGER


def load_theme(app_name: str = "win11_theme") -> Dict[str, str]:
	return get_manager(app_name).load()


def save_theme(theme: Dict[str, str], app_name: str = "win11_theme") -> None:
	mgr = get_manager(app_name)
	mgr.set_theme(theme, persist=True)


def set_color(key: str, value: str, app_name: str = "win11_theme") -> None:
	get_manager(app_name).set_color(key, value, persist=True)


def get_theme(app_name: str = "win11_theme") -> Dict[str, str]:
	return get_manager(app_name).get_theme()


def reset_theme(app_name: str = "win11_theme") -> None:
	get_manager(app_name).reset(persist=True)


__all__ = [
	"get_manager",
	"load_theme",
	"save_theme",
	"set_color",
	"get_theme",
	"reset_theme",
	"DEFAULT_THEME",
]


# -------------------- 以下为内置演示（可选） --------------------
def _run_demo(app_name: str = "demo_app") -> None:
	"""内置 Tkinter 演示：实时编辑与预览更多控件。"""
	try:
		import tkinter as tk
		import tkinter.font as tkfont
		from tkinter import colorchooser, ttk
	except Exception:
		print("tkinter not available")
		return

	mgr = get_manager(app_name)
	root = tk.Tk()
	root.title("Win11 Theme Demo")
	root.geometry("760x420")

	# 隐藏标题栏图标（尽力）
	try:
		blank = tk.PhotoImage(width=1, height=1)
		root.iconphoto(False, blank)
		try:
			root.iconbitmap("")
		except Exception:
			pass
	except Exception:
		pass

	theme = mgr.get_theme()
	root.configure(bg=theme["background"]) 

	style = ttk.Style(root)
	try:
		style.theme_use("clam")
	except Exception:
		pass

	font_family = "Segoe UI" if "Segoe UI" in tkfont.families() else None
	heading_font = (font_family or "Arial", 16)

	# 布局：左侧预览区，右侧控制区
	main_frame = tk.Frame(root, bg=theme["background"]) 
	main_frame.pack(fill="both", expand=True, padx=12, pady=12)

	preview = tk.Frame(main_frame, bg=theme["highlight"], bd=1, relief="flat")
	preview.pack(side="left", fill="both", expand=True, padx=(0,12))

	ctrl = tk.Frame(main_frame, width=300, bg=theme["background"]) 
	ctrl.pack(side="right", fill="y")

	top = tk.Frame(preview, bg=theme["highlight"]) 
	top.pack(fill="x", padx=12, pady=12)

	lbl = tk.Label(top, text="Win11 风格 主题编辑器（演示）", font=heading_font, fg=theme["foreground"], bg=theme["highlight"]) 
	lbl.pack(side="left")

	# 多个控件预览
	sample_lbl = tk.Label(preview, text="示例标题", font=(font_family or "Arial", 14), fg=theme["foreground"], bg=theme["highlight"]) 
	sample_lbl.pack(pady=8)

	sample_entry = tk.Entry(preview, bg=theme["background"], fg=theme["foreground"], insertbackground=theme["foreground"])
	sample_entry.insert(0, "输入文本...")
	sample_entry.pack(pady=6, ipadx=8)

	sample_text = tk.Text(preview, height=6, bg=theme["background"], fg=theme["foreground"], bd=0)
	sample_text.insert("1.0", "这是一个多行文本预览区域。\n可用于查看背景/前景配色。")
	sample_text.pack(fill="both", expand=True, padx=8, pady=6)

	btn_frame = tk.Frame(preview, bg=theme["highlight"]) 
	btn_frame.pack(pady=8)

	accent_btn = tk.Button(btn_frame, text="强调按钮", bg=theme["button_bg"] or theme["accent"], fg=theme["button_fg"] or theme["foreground"], relief="flat", padx=12, pady=6)
	accent_btn.pack(side="left", padx=6)

	normal_btn = tk.Button(btn_frame, text="普通按钮", bg=theme["button_bg"], fg=theme["button_fg"], relief="groove", padx=10)
	normal_btn.pack(side="left", padx=6)

	# 右侧控制面板

	def _choose(key):
		initial = mgr.get_theme().get(key, "#000000")
		c = colorchooser.askcolor(initialcolor=initial, title=f"选择 {key}")
		if c and c[1]:
			mgr.set_color(key, c[1])

	# 控制面板内容（美化布局）
	padx = 10
	py = 8
	section = lambda title: tk.Label(ctrl, text=title, bg=theme["background"], fg=theme["foreground"], anchor="w", font=(font_family or "Arial", 10, "bold"))
	section("配色设置").pack(fill="x", padx=padx, pady=(6,2))
	tk.Button(ctrl, text="背景", command=lambda: _choose("background"), bg=theme["background"], fg=theme["foreground"]).pack(fill="x", padx=padx, pady=py)
	tk.Button(ctrl, text="文字", command=lambda: _choose("foreground"), bg=theme["background"], fg=theme["foreground"]).pack(fill="x", padx=padx, pady=py)
	tk.Button(ctrl, text="强调", command=lambda: _choose("accent"), bg=theme["background"], fg=theme["foreground"]).pack(fill="x", padx=padx, pady=py)
	tk.Button(ctrl, text="高亮（面板）", command=lambda: _choose("highlight"), bg=theme["background"], fg=theme["foreground"]).pack(fill="x", padx=padx, pady=py)
	tk.Button(ctrl, text="边框", command=lambda: _choose("border"), bg=theme["background"], fg=theme["foreground"]).pack(fill="x", padx=padx, pady=py)

	# 按钮配色独立
	section("按钮配色").pack(fill="x", padx=padx, pady=(12,2))
	tk.Button(ctrl, text="按钮背景", command=lambda: _choose("button_bg"), bg=theme["background"], fg=theme["foreground"]).pack(fill="x", padx=padx, pady=py)
	tk.Button(ctrl, text="按钮文字", command=lambda: _choose("button_fg"), bg=theme["background"], fg=theme["foreground"]).pack(fill="x", padx=padx, pady=py)

	def _apply(t: dict):
		# 应用到预览控件
		root.configure(bg=t["background"]) 
		top.configure(bg=t["background"]) 
		lbl.config(bg=t["background"], fg=t["foreground"]) 
		preview.config(bg=t["highlight"]) 
		sample_lbl.config(bg=t["highlight"], fg=t["foreground"]) 
		sample_entry.config(bg=t["background"], fg=t["foreground"], insertbackground=t["foreground"]) 
		sample_text.config(bg=t["background"], fg=t["foreground"]) 
		accent_btn.config(bg=t["accent"], fg=t["foreground"]) 
		normal_btn.config(bg=t["background"], fg=t["foreground"]) 
		ctrl.config(bg=t["background"]) 

	# 注册回调
	mgr.register_callback(_apply)

	# 初始应用
	_apply(theme)

	# 顶部工具：保存/加载/重置
	tools = tk.Frame(root, bg=theme["background"]) 
	tools.place(x=12, y=12)
	tk.Button(tools, text="保存", command=mgr.save, bg=theme["background"], fg=theme["foreground"]).pack(side="left", padx=6)
	tk.Button(tools, text="加载", command=lambda: mgr.load() or _apply(mgr.get_theme()), bg=theme["background"], fg=theme["foreground"]).pack(side="left", padx=6)
	tk.Button(tools, text="重置", command=lambda: mgr.reset(), bg=theme["background"], fg=theme["foreground"]).pack(side="left", padx=6)

	root.mainloop()


if __name__ == "__main__":
	_run_demo("demo_app")

