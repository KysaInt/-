import ctypes
import threading
import time
import tkinter as tk
from tkinter import ttk
import json
import os
from tkinter import colorchooser

# =========================
# Win32 / DWM 常量 & 绑定
# =========================

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
advapi32 = ctypes.windll.advapi32

# Dwm attributes
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWCP_ROUND = 2
DWMSBT_MAINWINDOW = 2
DWMSBT_NONE = 0

# Window style constants
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080

# Registry constants
HKEY_CURRENT_USER = ctypes.c_void_p(0x80000001)
KEY_READ = 0x20019

# Registry paths
PERSONALIZE_PATH = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
APPS_USE_LIGHT_THEME = "AppsUseLightTheme"
DWM_PATH = r"Software\Microsoft\Windows\DWM"
ACCENT_COLOR = "AccentColor"

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "win11_theme_config.json")
# 备用配置路径：用户主目录（当程序目录不可写或 OneDrive 同步冲突时使用）
USER_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".win11_theme_config.json")

# 默认配色方案
DEFAULT_COLORS = {
    "light": {
        "bg": "#f3f3f3",
        "fg": "#1f1f1f",
        "entry_bg": "#ffffff",
        "entry_fg": "#1f1f1f",
        "button_bg": "#e1e1e1",
        "button_fg": "#1f1f1f",
        "accent": "#0078d4"
    },
    "dark": {
        "bg": "#202020",
        "fg": "#f2f2f2",
        "entry_bg": "#2d2d2d",
        "entry_fg": "#ffffff",
        "button_bg": "#454545",  # 提高对比度
        "button_fg": "#ffffff",  # 确保白色文字
        "accent": "#60cdff"
    }
}


# =========================
# 注册表读写工具
# =========================

def _open_key(root, subkey, access=KEY_READ):
    hkey = ctypes.c_void_p()
    res = advapi32.RegOpenKeyExW(root, ctypes.c_wchar_p(subkey), 0, access, ctypes.byref(hkey))
    if res != 0:
        raise OSError(f"RegOpenKeyExW failed: {res}")
    return hkey

def _query_dword(hkey, value_name):
    data = ctypes.c_uint()
    size = ctypes.c_uint(ctypes.sizeof(data))
    res = advapi32.RegQueryValueExW(hkey, ctypes.c_wchar_p(value_name), None, None, ctypes.byref(data), ctypes.byref(size))
    if res != 0:
        raise OSError(f"RegQueryValueExW failed: {res}")
    return data.value


# =========================
# 主题颜色获取
# =========================

def is_light_theme():
    try:
        hkey = _open_key(HKEY_CURRENT_USER, PERSONALIZE_PATH)
        val = _query_dword(hkey, APPS_USE_LIGHT_THEME)
        advapi32.RegCloseKey(hkey)
        return val == 1
    except Exception:
        return True

def get_accent_color_hex():
    try:
        hkey = _open_key(HKEY_CURRENT_USER, DWM_PATH)
        color_int = _query_dword(hkey, ACCENT_COLOR)
        advapi32.RegCloseKey(hkey)
        b = (color_int >> 16) & 0xFF
        g = (color_int >> 8) & 0xFF
        r = (color_int) & 0xFF
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return "#3a86ff"


# =========================
# 配色方案管理
# =========================

def load_color_config():
    """加载配色配置"""
    try:
        # 优先从主配置路径加载，其次尝试用户配置路径
        for path in (CONFIG_FILE, USER_CONFIG_FILE):
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception:
                    # 如果配置文件损坏，忽略并继续尝试下一个位置
                    continue
    except Exception:
        pass
    return DEFAULT_COLORS.copy()

def save_color_config(config):
    """保存配色配置"""
    try:
        # 尝试以原子方式写入主配置路径，若失败则回退到用户主目录
        global CONFIG_FILE
        def _atomic_write(path, data):
            dirpath = os.path.dirname(path)
            if dirpath and not os.path.exists(dirpath):
                os.makedirs(dirpath, exist_ok=True)
            tmp_path = path + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, path)

        try:
            _atomic_write(CONFIG_FILE, config)
            return True
        except Exception:
            # 回退到用户目录
            try:
                _atomic_write(USER_CONFIG_FILE, config)
                CONFIG_FILE = USER_CONFIG_FILE
                return True
            except Exception:
                return False
    except Exception:
        return False

def get_current_colors():
    """获取当前使用的配色方案"""
    config = load_color_config()
    light = is_light_theme()
    theme_key = "light" if light else "dark"
    
    # 如果配置中没有对应主题，使用默认配色
    if theme_key not in config:
        config[theme_key] = DEFAULT_COLORS[theme_key].copy()
    
    # 确保配置包含所有必要的字段（向后兼容）
    default_colors = DEFAULT_COLORS[theme_key]
    for key, default_value in default_colors.items():
        if key not in config[theme_key]:
            config[theme_key][key] = default_value
    
    # 尝试获取系统强调色，如果获取失败则使用配置中的强调色
    try:
        system_accent = get_accent_color_hex()
        config[theme_key]["accent"] = system_accent
    except:
        pass
    
    return config[theme_key], light


# =========================
# DWM 样式设置
# =========================

def set_corner_preference(hwnd, pref=DWMWCP_ROUND):
    value = ctypes.c_int(pref)
    dwmapi.DwmSetWindowAttribute(
        ctypes.c_void_p(hwnd),
        ctypes.c_uint(DWMWA_WINDOW_CORNER_PREFERENCE),
        ctypes.byref(value),
        ctypes.sizeof(value)
    )

def set_backdrop_mica(hwnd, enable=True):
    value = ctypes.c_int(DWMSBT_MAINWINDOW if enable else DWMSBT_NONE)
    dwmapi.DwmSetWindowAttribute(
        ctypes.c_void_p(hwnd),
        ctypes.c_uint(DWMWA_SYSTEMBACKDROP_TYPE),
        ctypes.byref(value),
        ctypes.sizeof(value)
    )

def set_titlebar_dark(hwnd, dark: bool):
    value = ctypes.c_int(1 if dark else 0)
    dwmapi.DwmSetWindowAttribute(
        ctypes.c_void_p(hwnd),
        ctypes.c_uint(DWMWA_USE_IMMERSIVE_DARK_MODE),
        ctypes.byref(value),
        ctypes.sizeof(value)
    )

def hide_window_icon(hwnd):
    """隐藏窗口图标但保留标题栏"""
    # 获取当前窗口扩展样式
    ex_style = user32.GetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)
    # 添加 WS_EX_TOOLWINDOW 样式来隐藏图标
    new_style = ex_style | WS_EX_TOOLWINDOW
    user32.SetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE, new_style)
    # 强制重绘窗口
    user32.SetWindowPos(ctypes.c_void_p(hwnd), None, 0, 0, 0, 0, 
                       0x0001 | 0x0002 | 0x0004 | 0x0020)  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED


# =========================
# Tk 主题应用
# =========================

def _apply_tk_theme(root: tk.Tk, colors=None, light=None):
    """应用主题配色到 Tkinter 窗口"""
    if colors is None or light is None:
        colors, light = get_current_colors()
    
    bg = colors["bg"]
    fg = colors["fg"] 
    entry_bg = colors["entry_bg"]
    entry_fg = colors["entry_fg"]
    button_bg = colors.get("button_bg", bg)
    button_fg = colors.get("button_fg", fg)
    accent = colors["accent"]

    root.configure(bg=bg)
    style = ttk.Style(root)

    # 首选 'clam' 主题（支持自定义颜色的渲染），若不可用再尝试使用 'vista'
    try:
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        else:
            style.theme_use('vista')
    except:
        # 如果都不可用或发生错误，则忽略，继续使用当前主题
        pass

    # 基础样式
    style.configure(".", font=("Segoe UI", 10), foreground=fg, background=bg)
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("TFrame", background=bg)
    
    # 按钮样式 - 改进深色模式下的显示
    button_hover_bg = "#e0e0e0" if light else "#555555"
    button_pressed_bg = accent if light else "#606060"
    
    style.configure("TButton", 
                   background=button_bg, 
                   foreground=button_fg,
                   borderwidth=1,
                   relief="flat",
                   focuscolor="none",
                   font=("Segoe UI", 10))
    
    # 按钮状态映射 - 处理鼠标悬停和按下状态
    style.map("TButton",
             background=[('active', button_hover_bg),
                        ('pressed', button_pressed_bg),
                        ('disabled', "#cccccc" if light else "#333333"),
                        ('!active', button_bg)],
             foreground=[('active', button_fg),
                        ('pressed', "#ffffff" if button_pressed_bg == accent else button_fg),
                        ('disabled', "#999999"),
                        ('!active', button_fg)],
             relief=[('pressed', 'sunken'),
                    ('!pressed', 'flat')])
    
    # 强调按钮样式
    accent_hover = "#106ebe" if light else "#4fb3ff"
    accent_pressed = "#005a9e" if light else "#3da5ff"
    
    style.configure("Accent.TButton", 
                   background=accent, 
                   foreground="#ffffff",
                   borderwidth=1,
                   relief="flat",
                   focuscolor="none",
                   font=("Segoe UI", 10, "bold"))
    
    style.map("Accent.TButton",
             background=[('active', accent_hover),
                        ('pressed', accent_pressed),
                        ('disabled', "#cccccc" if light else "#333333"),
                        ('!active', accent)],
             foreground=[('active', "#ffffff"),
                        ('pressed', "#ffffff"),
                        ('disabled', "#999999"),
                        ('!active', "#ffffff")],
             relief=[('pressed', 'sunken'),
                    ('!pressed', 'flat')])
    
    # 输入框样式 - 改进深色模式下的对比度
    style.configure("TEntry", 
                   fieldbackground=entry_bg, 
                   foreground=entry_fg, 
                   insertcolor=entry_fg,
                   borderwidth=1,
                   relief="solid",
                   selectbackground=accent,
                   selectforeground="#ffffff")
    
    # 输入框状态映射
    style.map("TEntry",
             fieldbackground=[('focus', entry_bg),
                            ('!focus', entry_bg)],
             foreground=[('focus', entry_fg),
                        ('!focus', entry_fg)],
             bordercolor=[('focus', accent),
                         ('!focus', "#666666" if not light else "#cccccc")])
    
    # 其他控件样式
    style.configure("TCombobox", 
                   fieldbackground=entry_bg,
                   foreground=entry_fg,
                   borderwidth=1,
                   arrowcolor=fg)
    
    style.map("TCombobox",
             fieldbackground=[('readonly', entry_bg)],
             foreground=[('readonly', entry_fg)])
    
    # 复选框和单选按钮
    style.configure("TCheckbutton", background=bg, foreground=fg, focuscolor="none")
    style.configure("TRadiobutton", background=bg, foreground=fg, focuscolor="none")
    
    # 进度条
    style.configure("TProgressbar", background=accent, troughcolor=button_bg)
    
    # 滑块
    style.configure("TScale", background=bg, troughcolor=button_bg, slidercolor=accent)

    # 普通 Tk 控件颜色同步
    def patch_colors(widget):
        try:
            if isinstance(widget, tk.Entry):
                widget.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg,
                               selectbackground=accent, selectforeground="#ffffff",
                               relief="solid", bd=1)
            elif isinstance(widget, tk.Text):
                widget.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg,
                               selectbackground=accent, selectforeground="#ffffff",
                               relief="solid", bd=1)
            elif isinstance(widget, tk.Button):
                # 改进普通 tk.Button 的配色
                hover_bg = "#e0e0e0" if light else "#555555"
                widget.configure(bg=button_bg, fg=button_fg, 
                               activebackground=hover_bg,
                               activeforeground=button_fg,
                               relief="flat", bd=1,
                               font=("Segoe UI", 10))
            else:
                widget.configure(bg=bg, fg=fg)
        except:
            pass
        for child in widget.winfo_children():
            patch_colors(child)

    patch_colors(root)


# =========================
# 对外接口
# =========================

def apply_win11_theme(root: tk.Tk, watch_changes=True, custom_colors=None):
    """
    应用 Windows 11 主题到 Tkinter 窗口
    
    Args:
        root: Tkinter 根窗口
        watch_changes: 是否监听系统主题变化
        custom_colors: 自定义配色方案 (可选)
    """
    hwnd = root.winfo_id()
    
    if custom_colors:
        colors = custom_colors
        light = is_light_theme()
    else:
        colors, light = get_current_colors()

    # 移除窗口图标和标题文字
    root.title("")  # 清空标题文字
    root.iconbitmap("")  # 尝试移除图标
    try:
        root.wm_iconbitmap("")  # 另一种移除图标的方法
    except:
        pass
    
    # 应用主题样式
    set_titlebar_dark(hwnd, dark=not light)
    set_corner_preference(hwnd)
    set_backdrop_mica(hwnd)
    
    # 隐藏窗口图标
    root.after(100, lambda: hide_window_icon(hwnd))  # 延迟执行以确保窗口完全创建
    
    _apply_tk_theme(root, colors, light)

    if watch_changes:
        threading.Thread(target=_watch_theme_changes, args=(root, hwnd), daemon=True).start()

def get_theme_colors():
    """获取当前主题配色方案 - 供外部程序调用"""
    return get_current_colors()

def set_custom_colors(light_colors=None, dark_colors=None):
    """
    设置自定义配色方案 - 供外部程序调用
    
    Args:
        light_colors: 浅色主题配色 {"bg": "#f3f3f3", "fg": "#1f1f1f", ...}
        dark_colors: 深色主题配色 {"bg": "#202020", "fg": "#f2f2f2", ...}
    """
    config = load_color_config()
    
    if light_colors:
        config["light"].update(light_colors)
    if dark_colors:
        config["dark"].update(dark_colors)
    
    return save_color_config(config)


def _watch_theme_changes(root: tk.Tk, hwnd):
    last_light = None
    last_accent = None
    while True:
        time.sleep(2)
        cur_light = is_light_theme()
        cur_accent = get_accent_color_hex()
        if cur_light != last_light or cur_accent != last_accent:
            last_light = cur_light
            last_accent = cur_accent
            root.after(0, lambda: apply_win11_theme(root, watch_changes=False))


# =========================
# 配色调整界面
# =========================

class ColorConfigWindow:
    def __init__(self, parent=None):
        self.parent = parent
        self.config = load_color_config()
        self.current_theme = "light" if is_light_theme() else "dark"
        
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("配色调整")
        self.window.geometry("500x600")
        self.window.resizable(False, True)
        
        self.setup_ui()
        apply_win11_theme(self.window, watch_changes=False)
        
    def setup_ui(self):
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill="both", expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="主题配色调整", font=("Segoe UI", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # 主题选择
        theme_frame = ttk.Frame(main_frame)
        theme_frame.pack(fill="x", pady=(0, 20))
        
        ttk.Label(theme_frame, text="编辑主题:").pack(side="left")
        self.theme_var = tk.StringVar(value=self.current_theme)
        theme_combo = ttk.Combobox(theme_frame, textvariable=self.theme_var, 
                                  values=["light", "dark"], state="readonly", width=10)
        theme_combo.pack(side="left", padx=(10, 0))
        theme_combo.bind("<<ComboboxSelected>>", self.on_theme_change)
        
        # 配色调整区域
        self.color_frame = ttk.LabelFrame(main_frame, text="配色设置", padding="15")
        self.color_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        self.color_vars = {}
        self.color_labels = {
            "bg": "背景色",
            "fg": "前景色", 
            "entry_bg": "输入框背景色",
            "entry_fg": "输入框文字色",
            "button_bg": "按钮背景色",
            "button_fg": "按钮文字色",
            "accent": "强调色"
        }
        
        self.create_color_controls()
        
        # 预览区域
        preview_frame = ttk.LabelFrame(main_frame, text="预览", padding="15")
        preview_frame.pack(fill="x", pady=(0, 20))
        
        self.create_preview_controls(preview_frame)
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x")
        
        ttk.Button(button_frame, text="重置为默认", 
                  command=self.reset_to_default).pack(side="left")
        ttk.Button(button_frame, text="应用到系统", 
                  command=self.apply_to_system).pack(side="left", padx=(10, 0))
        ttk.Button(button_frame, text="保存", 
                  command=self.save_config).pack(side="right")
        ttk.Button(button_frame, text="取消", 
                  command=self.window.destroy).pack(side="right", padx=(10, 0))
    
    def create_color_controls(self):
        for widget in self.color_frame.winfo_children():
            widget.destroy()
            
        current_colors = self.config[self.current_theme]
        
        for i, (key, label) in enumerate(self.color_labels.items()):
            row_frame = ttk.Frame(self.color_frame)
            row_frame.pack(fill="x", pady=5)
            
            ttk.Label(row_frame, text=label, width=15).pack(side="left")
            
            # 颜色变量
            if key not in self.color_vars:
                self.color_vars[key] = tk.StringVar()
            self.color_vars[key].set(current_colors.get(key, "#000000"))
            
            # 颜色显示框
            color_frame = tk.Frame(row_frame, width=30, height=25, 
                                 bg=self.color_vars[key].get(), relief="solid", bd=1)
            color_frame.pack(side="left", padx=(10, 5))
            color_frame.pack_propagate(False)
            
            # 颜色值输入框
            entry = ttk.Entry(row_frame, textvariable=self.color_vars[key], width=10)
            entry.pack(side="left", padx=(5, 5))
            entry.bind("<KeyRelease>", lambda e, f=color_frame, v=self.color_vars[key]: self.update_color_preview(f, v))
            
            # 选择颜色按钮
            ttk.Button(row_frame, text="选择", width=8,
                      command=lambda k=key, f=color_frame: self.choose_color(k, f)).pack(side="left")
    
    def update_color_preview(self, color_frame, color_var):
        try:
            color = color_var.get()
            if color.startswith("#") and len(color) == 7:
                color_frame.configure(bg=color)
                self.update_preview()
        except:
            pass
    
    def choose_color(self, key, color_frame):
        current_color = self.color_vars[key].get()
        color = colorchooser.askcolor(color=current_color, title=f"选择{self.color_labels[key]}")
        if color[1]:  # 如果用户选择了颜色
            self.color_vars[key].set(color[1])
            color_frame.configure(bg=color[1])
            self.update_preview()
    
    def create_preview_controls(self, parent):
        # 示例控件
        ttk.Label(parent, text="预览标签").pack(pady=2)
        
        entry_var = tk.StringVar(value="预览文本")
        ttk.Entry(parent, textvariable=entry_var, width=20).pack(pady=2)
        
        button_frame = ttk.Frame(parent)
        button_frame.pack(pady=2)
        ttk.Button(button_frame, text="普通按钮").pack(side="left", padx=(0, 5))
        ttk.Button(button_frame, text="强调按钮", style="Accent.TButton").pack(side="left")
    
    def update_preview(self):
        # 更新当前配置
        for key, var in self.color_vars.items():
            self.config[self.current_theme][key] = var.get()
        
        # 重新应用主题
        colors = self.config[self.current_theme]
        light = self.current_theme == "light"
        _apply_tk_theme(self.window, colors, light)
    
    def on_theme_change(self, event=None):
        self.current_theme = self.theme_var.get()
        self.create_color_controls()
        self.update_preview()
    
    def reset_to_default(self):
        self.config[self.current_theme] = DEFAULT_COLORS[self.current_theme].copy()
        self.create_color_controls()
        self.update_preview()
    
    def apply_to_system(self):
        # 应用到父窗口（如果存在）
        if self.parent:
            colors = self.config[self.current_theme]
            light = self.current_theme == "light"
            _apply_tk_theme(self.parent, colors, light)
    
    def save_config(self):
        if save_color_config(self.config):
            import tkinter.messagebox as msgbox
            msgbox.showinfo("保存成功", "配色方案已保存！")
            if self.parent:
                self.apply_to_system()
            self.window.destroy()
        else:
            import tkinter.messagebox as msgbox
            msgbox.showerror("保存失败", "无法保存配色方案！")


# =========================
# 测试预览窗口
# =========================

def create_test_window():
    """创建一个包含各种常用控件的测试预览窗口"""
    root = tk.Tk()
    root.title("Win11 主题测试预览")
    root.geometry("700x600")
    root.resizable(True, True)
    
    # 创建菜单栏
    menubar = tk.Menu(root)
    root.config(menu=menubar)
    
    # 主题菜单
    theme_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="主题", menu=theme_menu)
    theme_menu.add_command(label="配色设置", command=lambda: ColorConfigWindow(root))
    theme_menu.add_separator()
    theme_menu.add_command(label="重置为默认", command=lambda: reset_and_apply(root))
    theme_menu.add_command(label="重新加载主题", command=lambda: apply_win11_theme(root, watch_changes=False))
    
    # 创建主框架
    main_frame = ttk.Frame(root, padding="20")
    main_frame.grid(row=0, column=0, sticky="nsew")
    
    # 配置网格权重
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=1)
    
    row = 0
    
    # 标题
    title_label = ttk.Label(main_frame, text="Windows 11 主题预览", font=("Segoe UI", 16, "bold"))
    title_label.grid(row=row, column=0, columnspan=2, pady=(0, 20), sticky="w")
    row += 1
    
    # 配色调整按钮
    config_frame = ttk.Frame(main_frame)
    config_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 20))
    config_frame.grid_columnconfigure(0, weight=1)
    
    ttk.Button(config_frame, text="🎨 配色设置", 
              command=lambda: ColorConfigWindow(root)).pack(side="right")
    ttk.Label(config_frame, text="点击右侧按钮自定义主题配色", 
             font=("Segoe UI", 9), foreground="gray").pack(side="left")
    row += 1
    
    # 普通标签
    ttk.Label(main_frame, text="普通标签:").grid(row=row, column=0, sticky="w", pady=5)
    ttk.Label(main_frame, text="这是一个示例标签").grid(row=row, column=1, sticky="w", padx=(10, 0), pady=5)
    row += 1
    
    # 输入框
    ttk.Label(main_frame, text="文本输入框:").grid(row=row, column=0, sticky="w", pady=5)
    entry_var = tk.StringVar(value="请输入文本...")
    entry = ttk.Entry(main_frame, textvariable=entry_var, width=30)
    entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
    row += 1
    
    # 按钮框架
    ttk.Label(main_frame, text="按钮:").grid(row=row, column=0, sticky="w", pady=5)
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
    
    ttk.Button(button_frame, text="普通按钮").pack(side="left", padx=(0, 10))
    ttk.Button(button_frame, text="强调按钮", style="Accent.TButton").pack(side="left")
    row += 1
    
    # 复选框
    ttk.Label(main_frame, text="复选框:").grid(row=row, column=0, sticky="w", pady=5)
    checkbox_frame = ttk.Frame(main_frame)
    checkbox_frame.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
    
    check_var1 = tk.BooleanVar(value=True)
    check_var2 = tk.BooleanVar(value=False)
    ttk.Checkbutton(checkbox_frame, text="选项 1", variable=check_var1).pack(side="left", padx=(0, 10))
    ttk.Checkbutton(checkbox_frame, text="选项 2", variable=check_var2).pack(side="left")
    row += 1
    
    # 单选按钮
    ttk.Label(main_frame, text="单选按钮:").grid(row=row, column=0, sticky="w", pady=5)
    radio_frame = ttk.Frame(main_frame)
    radio_frame.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
    
    radio_var = tk.StringVar(value="option1")
    ttk.Radiobutton(radio_frame, text="选项 A", variable=radio_var, value="option1").pack(side="left", padx=(0, 10))
    ttk.Radiobutton(radio_frame, text="选项 B", variable=radio_var, value="option2").pack(side="left")
    row += 1
    
    # 下拉菜单
    ttk.Label(main_frame, text="下拉菜单:").grid(row=row, column=0, sticky="w", pady=5)
    combo_var = tk.StringVar()
    combo = ttk.Combobox(main_frame, textvariable=combo_var, values=["选项1", "选项2", "选项3", "选项4"], state="readonly")
    combo.set("请选择...")
    combo.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
    row += 1
    
    # 进度条
    ttk.Label(main_frame, text="进度条:").grid(row=row, column=0, sticky="w", pady=5)
    progress = ttk.Progressbar(main_frame, length=200, mode='determinate')
    progress['value'] = 65
    progress.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
    row += 1
    
    # 滑块
    ttk.Label(main_frame, text="滑块:").grid(row=row, column=0, sticky="w", pady=5)
    scale_var = tk.DoubleVar(value=50)
    scale = ttk.Scale(main_frame, from_=0, to=100, variable=scale_var, orient="horizontal")
    scale.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
    row += 1
    
    # 文本框
    ttk.Label(main_frame, text="多行文本:").grid(row=row, column=0, sticky="nw", pady=5)
    text_frame = ttk.Frame(main_frame)
    text_frame.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=5)
    text_frame.grid_columnconfigure(0, weight=1)
    
    text_widget = tk.Text(text_frame, height=6, width=40)
    text_widget.grid(row=0, column=0, sticky="ew")
    text_widget.insert("1.0", "这是一个多行文本框。\n您可以在这里输入多行文本。\n支持换行和滚动。\n\n配色会自动根据主题调整。")
    
    # 滚动条
    scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    text_widget.configure(yscrollcommand=scrollbar.set)
    row += 1
    
    # 分隔线
    separator = ttk.Separator(main_frame, orient="horizontal")
    separator.grid(row=row, column=0, columnspan=2, sticky="ew", pady=20)
    row += 1
    
    # 底部信息
    info_label = ttk.Label(main_frame, text="主题配色可自定义，支持保存和实时预览", font=("Segoe UI", 9))
    info_label.grid(row=row, column=0, columnspan=2, pady=(0, 10))
    row += 1
    
    # 底部按钮
    bottom_frame = ttk.Frame(main_frame)
    bottom_frame.grid(row=row, column=0, columnspan=2, sticky="ew")
    bottom_frame.grid_columnconfigure(0, weight=1)
    
    def show_info():
        import tkinter.messagebox as msgbox
        colors, light = get_current_colors()
        theme_info = f"当前主题: {'浅色' if light else '深色'}\n"
        theme_info += f"背景色: {colors['bg']}\n"
        theme_info += f"前景色: {colors['fg']}\n"
        theme_info += f"强调色: {colors['accent']}"
        msgbox.showinfo("主题信息", theme_info)
    
    ttk.Button(bottom_frame, text="主题信息", command=show_info).pack(side="right", padx=(10, 0))
    ttk.Button(bottom_frame, text="关闭", command=root.destroy).pack(side="right")
    
    # 应用 Windows 11 主题
    apply_win11_theme(root)
    
    return root

def reset_and_apply(root):
    """重置配色为默认并重新应用主题"""
    config = DEFAULT_COLORS.copy()
    save_color_config(config)
    apply_win11_theme(root, watch_changes=False)


# =========================
# 主程序入口
# =========================

if __name__ == "__main__":
    # 创建并显示测试窗口
    test_window = create_test_window()
    test_window.mainloop()
