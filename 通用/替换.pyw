# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import importlib.util

def check_and_install_packages():
    """检查并安装所需的包"""
    required_packages = {
        'pywinstyles': 'pywinstyles',
        'PIL': 'Pillow'
    }
    
    missing_packages = []
    
    # 检查每个包是否已安装
    for import_name, package_name in required_packages.items():
        if importlib.util.find_spec(import_name) is None:
            missing_packages.append(package_name)
    
    if missing_packages:
        # 如果有缺失的包，显示GUI提示
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            
            packages_str = '\n'.join([f"  • {pkg}" for pkg in missing_packages])
            message = f"检测到缺少以下依赖包:\n\n{packages_str}\n\n是否现在自动安装这些包？"
            
            if messagebox.askyesno("缺少依赖包", message):
                # 创建进度窗口
                progress_window = tk.Toplevel()
                progress_window.title("安装依赖包")
                progress_window.geometry("400x200")
                progress_window.resizable(False, False)
                
                # 居中显示
                progress_window.update_idletasks()
                x = (progress_window.winfo_screenwidth() // 2) - (400 // 2)
                y = (progress_window.winfo_screenheight() // 2) - (200 // 2)
                progress_window.geometry(f"400x200+{x}+{y}")
                
                label = tk.Label(progress_window, text="正在安装依赖包，请稍候...", font=('Arial', 12))
                label.pack(pady=20)
                
                text_widget = tk.Text(progress_window, height=8, width=50)
                text_widget.pack(pady=10, padx=20, fill='both', expand=True)
                
                progress_window.update()
                
                success = True
                for package in missing_packages:
                    try:
                        text_widget.insert('end', f"正在安装 {package}...\n")
                        text_widget.see('end')
                        progress_window.update()
                        
                        subprocess.check_call([sys.executable, "-m", "pip", "install", package], 
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        
                        text_widget.insert('end', f"✓ {package} 安装成功\n")
                        text_widget.see('end')
                        progress_window.update()
                    except subprocess.CalledProcessError:
                        text_widget.insert('end', f"✗ {package} 安装失败\n")
                        text_widget.see('end')
                        progress_window.update()
                        success = False
                
                if success:
                    text_widget.insert('end', "\n所有依赖包安装完成！")
                    messagebox.showinfo("安装完成", "所有依赖包安装成功！\n程序将继续启动。")
                else:
                    messagebox.showerror("安装失败", "部分依赖包安装失败！\n请检查网络连接或手动安装。")
                
                progress_window.destroy()
                root.destroy()
                return success
            else:
                root.destroy()
                return False
        except ImportError:
            # 如果tkinter不可用，回退到命令行模式
            print("检测到缺少以下依赖包:")
            for package in missing_packages:
                print(f"  - {package}")
            
            print("\n正在自动安装缺少的包...")
            
            for package in missing_packages:
                try:
                    print(f"正在安装 {package}...")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    print(f"✓ {package} 安装成功")
                except subprocess.CalledProcessError as e:
                    print(f"✗ {package} 安装失败: {e}")
                    print("请手动安装此包或检查网络连接")
                    return False
            
            print("\n所有依赖包安装完成！")
    
    return True

# 执行依赖检查
print("正在检查依赖包...")
if not check_and_install_packages():
    print("依赖安装失败或用户取消，程序退出")
    input("按任意键退出...")
    sys.exit(1)

print("依赖检查完成，启动程序...")

# 导入所需模块
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    import pywinstyles
    import winreg
    from PIL import Image, ImageTk
    import tempfile
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有依赖包都已正确安装")
    input("按任意键退出...")
    sys.exit(1)

def create_transparent_icon():
    """创建一个透明图标"""
    try:
        # 创建一个16x16的透明图像
        img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
        
        # 保存为临时ico文件
        temp_dir = tempfile.gettempdir()
        icon_path = os.path.join(temp_dir, 'transparent_icon.ico')
        img.save(icon_path, format='ICO')
        return icon_path
    except:
        return None

def is_dark_mode():
    """检测系统是否启用深色模式"""
    try:
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, regtype = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0  # 0 表示深色模式
    except:
        return False

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

def on_browse():
    """选择执行路径"""
    directory = filedialog.askdirectory(
        title="选择要重命名的文件夹",
        initialdir=path_var.get() or os.path.dirname(os.path.abspath(__file__))
    )
    if directory:
        path_var.set(directory)

def on_rename():
    find_str = entry_find.get()
    replace_str = entry_replace.get()
    if not find_str:
        status_var.set("查找内容不能为空！")
        return
    
    root_dir = path_var.get() or os.path.dirname(os.path.abspath(__file__))
    
    if not os.path.exists(root_dir):
        messagebox.showerror("错误", "指定的路径不存在！")
        return
    
    try:
        batch_rename(root_dir, find_str, replace_str)
        status_var.set(f"批量重命名完成！处理路径: {root_dir}")
    except Exception as e:
        status_var.set(f"重命名失败: {str(e)}")
        messagebox.showerror("错误", f"重命名过程中发生错误：\n{str(e)}")

def apply_theme_styles(root):
    """应用主题样式"""
    dark_mode = is_dark_mode()
    
    # 设置窗口样式
    pywinstyles.change_header_color(root, "#1e1e1e" if dark_mode else "#ffffff")
    pywinstyles.change_border_color(root, "#333333" if dark_mode else "#cccccc")
    
    # 应用深色主题
    if dark_mode:
        pywinstyles.apply_style(root, "dark")
        root.configure(bg="#2d2d30")
    else:
        pywinstyles.apply_style(root, "normal")
        root.configure(bg="#ffffff")

def configure_dark_theme():
    """配置深色主题的ttk样式"""
    style = ttk.Style()
    
    if is_dark_mode():
        # 深色主题配置
        style.theme_use('clam')  # 使用可自定义的主题
        
        # 配置Frame样式
        style.configure('TFrame', 
                       background='#2d2d30',
                       borderwidth=0)
        
        # 配置Label样式
        style.configure('TLabel',
                       background='#2d2d30',
                       foreground='#ffffff',
                       font=('Segoe UI', 9, 'normal'))
        
        # 配置Entry样式
        style.configure('TEntry',
                       fieldbackground='#3c3c3c',
                       background='#3c3c3c',
                       foreground='#ffffff',
                       borderwidth=1,
                       insertcolor='#ffffff',
                       selectbackground='#0078d4',
                       selectforeground='#ffffff')
        
        # 配置Button样式
        style.configure('TButton',
                       background='#0078d4',
                       foreground='#ffffff',
                       borderwidth=1,
                       focuscolor='none',
                       font=('Segoe UI', 9, 'normal'))
        
        style.map('TButton',
                 background=[('active', '#106ebe'),
                           ('pressed', '#005a9e')])
        
        # 状态标签样式
        style.configure('Status.TLabel',
                       background='#2d2d30',
                       foreground='#4fc3f7',
                       font=('Segoe UI', 9, 'normal'),
                       wraplength=400)  # 添加自动换行
    else:
        # 浅色主题（默认）
        style.theme_use('vista')  # Windows默认主题
        style = ttk.Style()
        style.configure('TLabel', font=('Segoe UI', 9, 'normal'))
        style.configure('TButton', font=('Segoe UI', 9, 'normal'))
        style.configure('Status.TLabel',
                       font=('Segoe UI', 9, 'normal'),
                       wraplength=400)  # 为浅色主题也添加自动换行

def on_window_resize(event=None):
    """窗口大小改变时的回调函数"""
    if event and event.widget == root:
        # 根据窗口宽度调整状态标签的换行长度
        window_width = root.winfo_width()
        wrap_length = max(300, window_width - 100)  # 至少300像素，最大为窗口宽度-100
        
        style = ttk.Style()
        if is_dark_mode():
            style.configure('Status.TLabel',
                           background='#2d2d30',
                           foreground='#4fc3f7',
                           font=('Segoe UI', 9, 'normal'),
                           wraplength=wrap_length)
        else:
            style.configure('Status.TLabel',
                           font=('Segoe UI', 9, 'normal'),
                           wraplength=wrap_length)

# 创建主窗口
root = tk.Tk()
root.title("")  # 空标题

# 创建并设置透明图标
transparent_icon = create_transparent_icon()
if transparent_icon:
    try:
        root.iconbitmap(transparent_icon)
    except:
        root.wm_iconbitmap("")  # 如果失败则使用空字符串
else:
    root.wm_iconbitmap("")  # 备用方法

# 设置初始窗口大小为最小大小
root.geometry("400x150")
# 设置最小窗口大小
root.minsize(400, 150)
# 允许窗口大小调整
root.resizable(True, True)

# 绑定窗口大小改变事件
root.bind('<Configure>', on_window_resize)

# 配置深色主题
configure_dark_theme()

# 应用主题样式
root.after(100, lambda: apply_theme_styles(root))

# 创建变量
path_var = tk.StringVar(value=os.path.dirname(os.path.abspath(__file__)))
status_var = tk.StringVar()

# 主框架 - 支持自适应大小，更紧凑的内边距
mainframe = ttk.Frame(root, padding="10 6 10 6")
mainframe.pack(fill=tk.BOTH, expand=True)

# 配置主框架的行列权重
mainframe.columnconfigure(1, weight=1)
mainframe.rowconfigure(4, weight=1)  # 状态行可扩展

# 执行路径选择
ttk.Label(mainframe, text="执行路径:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
path_frame = ttk.Frame(mainframe)
path_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 5))
path_frame.columnconfigure(0, weight=1)

entry_path = ttk.Entry(path_frame, textvariable=path_var)
entry_path.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 6))

btn_browse = ttk.Button(path_frame, text="浏览...", command=on_browse, width=8)
btn_browse.grid(row=0, column=1)

# 查找内容
ttk.Label(mainframe, text="查找内容:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
entry_find = ttk.Entry(mainframe)
entry_find.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 5))

# 替换内容
ttk.Label(mainframe, text="替换为:").grid(row=2, column=0, sticky=tk.W, pady=(0, 6))
entry_replace = ttk.Entry(mainframe)
entry_replace.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(0, 6))

# 重命名按钮
btn_rename = ttk.Button(mainframe, text="开始批量重命名", command=on_rename)
btn_rename.grid(row=3, column=0, columnspan=2, pady=(4, 6), sticky=(tk.W, tk.E), ipady=2)

# 状态标签
status_label = ttk.Label(mainframe, textvariable=status_var, style='Status.TLabel')
status_label.grid(row=4, column=0, columnspan=2, pady=(0, 2), sticky=(tk.W, tk.E, tk.N))

# 配置主框架的行列权重
mainframe.columnconfigure(1, weight=1)
mainframe.rowconfigure(4, weight=1)  # 状态行可扩展

root.mainloop()

# 清理临时图标文件
if transparent_icon and os.path.exists(transparent_icon):
    try:
        os.remove(transparent_icon)
    except:
        pass
