"""轻量 Tkinter 演示：更接近 Win11 风格的主题编辑器

特点：
- 使用 Segoe UI 字体和 ttk 样式以贴近 Win11 风格
- 使用空的 PhotoImage 覆盖窗口图标，使标题栏不显示图标
- 运行时修改主题并持久化（由 win11_theme 管理）
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import colorchooser, ttk
from win11_theme import get_manager


def main():
    mgr = get_manager("demo_app")
    root = tk.Tk()
    root.title("Theme Test")
    root.geometry("480x220")

    # 覆盖窗口图标为一个空的 PhotoImage（在 Windows 上这会取消左上角图标）
    try:
        blank = tk.PhotoImage(width=1, height=1)
        root.iconphoto(False, blank)
        # 在 Windows 上尝试清除图标的另一个方法
        try:
            root.iconbitmap("")
        except Exception:
            # 有些 tkinter 版本/平台 不接受空字符串，忽略错误
            pass
    except Exception:
        pass

    # 读取当前主题并应用
    theme = mgr.get_theme()
    root.configure(bg=theme["background"]) 

    # 使用 ttk 并配置 Win11 近似样式
    style = ttk.Style(root)
    # 尝试使用 "clam" 主题获得更一致的可配置性
    try:
        style.theme_use("clam")
    except Exception:
        pass

    font_family = "Segoe UI" if "Segoe UI" in tkfont.families() else None
    heading_font = (font_family or "Arial", 14)
    btn_font = (font_family or "Arial", 10)

    # 自定义样式：Accent 按钮
    style.configure(
        "Accent.TButton",
        font=btn_font,
        foreground=theme["foreground"],
        background=theme["accent"],
        padding=8,
        relief="flat",
    )

    # 回调：当主题更新时，应用到窗口与样式
    def on_theme_change(t):
        root.configure(bg=t["background"]) 
        lbl.config(fg=t["foreground"], bg=t["background"]) 
        frm.config(bg=t["background"]) 
        # 更新 ttk 样式颜色（注意：部分平台/主题对 background 的支持有限）
        try:
            style.configure("Accent.TButton", background=t["accent"], foreground=t["foreground"]) 
        except Exception:
            pass
        # 更新普通 tk 按钮外观（备用）
        try:
            btn_bg.configure(bg=t["background"], fg=t["foreground"])
            btn_fg.configure(bg=t["background"], fg=t["foreground"])
        except Exception:
            pass

    mgr.register_callback(on_theme_change)

    lbl = tk.Label(root, text="当前主题示例", font=heading_font, fg=theme["foreground"], bg=theme["background"]) 
    lbl.pack(pady=12)

    def choose_color(key):
        initial = mgr.get_theme().get(key, "#000000")
        c = colorchooser.askcolor(initialcolor=initial, title=f"选择 {key}")
        if c and c[1]:
            mgr.set_color(key, c[1])

    frm = tk.Frame(root, bg=theme["background"]) 
    frm.pack(pady=8)

    # 使用 ttk.Button 配合自定义样式以获得更现代外观
    btn_bg = tk.Button(frm, text="背景", command=lambda: choose_color("background"), bg=theme["background"], fg=theme["foreground"], relief="flat")
    btn_bg.grid(row=0, column=0, padx=8)
    btn_fg = tk.Button(frm, text="文字", command=lambda: choose_color("foreground"), bg=theme["background"], fg=theme["foreground"], relief="flat")
    btn_fg.grid(row=0, column=1, padx=8)
    btn_accent = ttk.Button(frm, text="强调", command=lambda: choose_color("accent"), style="Accent.TButton")
    btn_accent.grid(row=0, column=2, padx=8)

    def reset():
        mgr.reset()

    btn_reset = ttk.Button(root, text="重置默认", command=reset, style="Accent.TButton")
    btn_reset.pack(pady=12)

    root.mainloop()


if __name__ == "__main__":
    main()
