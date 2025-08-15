# -*- coding: utf-8 -*-
import os
import tkinter as tk
from tkinter import ttk

def batch_rename(root_dir, find_str, replace_str):
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        for filename in filenames:
            if find_str in filename:
                old_path = os.path.join(dirpath, filename)
                new_filename = filename.replace(find_str, replace_str)
                new_path = os.path.join(dirpath, new_filename)
                try:
                    os.rename(old_path, new_path)
                except Exception:
                    pass  # 静默异常
        for dirname in dirnames:
            if find_str in dirname:
                old_dir = os.path.join(dirpath, dirname)
                new_dir = os.path.join(dirpath, dirname.replace(find_str, replace_str))
                try:
                    os.rename(old_dir, new_dir)
                except Exception:
                    pass  # 静默异常

def on_rename():
    find_str = entry_find.get()
    replace_str = entry_replace.get()
    if not find_str:
        status_var.set("查找内容不能为空！")
        return
    root_dir = os.path.dirname(os.path.abspath(__file__))
    batch_rename(root_dir, find_str, replace_str)
    status_var.set("批量重命名完成！")

def center_window(win, width, height):
    screenwidth = win.winfo_screenwidth()
    screenheight = win.winfo_screenheight()
    size = '%dx%d+%d+%d' % (width, height, (screenwidth-width)//2, (screenheight-height)//2)
    win.geometry(size)

root = tk.Tk()
root.title("批量重命名工具")
center_window(root, 380, 210)
root.resizable(False, False)

mainframe = ttk.Frame(root, padding="15 10 15 10")
mainframe.pack(fill=tk.BOTH, expand=True)

ttk.Label(mainframe, text="查找内容:").grid(row=0, column=0, sticky=tk.W, pady=8)
entry_find = ttk.Entry(mainframe, width=28)
entry_find.grid(row=0, column=1, pady=8)

ttk.Label(mainframe, text="替换为:").grid(row=1, column=0, sticky=tk.W, pady=8)
entry_replace = ttk.Entry(mainframe, width=28)
entry_replace.grid(row=1, column=1, pady=8)

btn_rename = ttk.Button(mainframe, text="开始批量重命名", command=on_rename)
btn_rename.grid(row=2, column=0, columnspan=2, pady=18, ipadx=30, ipady=4)

status_var = tk.StringVar()
status_label = ttk.Label(mainframe, textvariable=status_var, foreground="blue")
status_label.grid(row=3, column=0, columnspan=2, pady=5)

root.mainloop()
