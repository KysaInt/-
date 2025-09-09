# -*- coding: utf-8 -*-
"""
文件查看管理器 - 基于mf.py整理结构的交互式文件浏览器
支持折叠显示、帧统计和可视化帧存在情况
"""

import os
import sys
import re
import subprocess
import importlib.util
from collections import defaultdict
import math

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
    from tkinter import ttk, filedialog, messagebox, Canvas, Scrollbar
    import pywinstyles
    import winreg
    from PIL import Image, ImageTk, ImageDraw
    import tempfile
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有依赖包都已正确安装")
    input("按任意键退出...")
    sys.exit(1)

class FileManager:
    """文件管理器类"""

    def __init__(self, root):
        self.root = root
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.tree_data = {}
        self.expanded_items = set()

        # 常见的通道后缀（与mf.py保持一致）
        self.channel_suffixes = [
            'alpha', 'zdepth', 'normal', 'roughness', 'metallic', 'specular',
            'emission', 'ao', 'displacement', 'bump', 'diffuse', 'reflection', 'refraction',
            'atmospheric_effects', 'background', 'bump_normals', 'caustics', 'coat',
            'coat_filter', 'coat_glossiness', 'coat_reflection', 'coverage', 'cryptomatte',
            'cryptomatte00', 'cryptomatte01', 'cryptomatte02', 'denoiser', 'dl1', 'dl2', 'dl3',
            'dr_bucket', 'environment', 'extra_tex', 'global_illumination', 'lighting',
            'material_id', 'material_select', 'matte_shadow', 'metalness', 'multi_matte',
            'multi_matte_id', 'normals', 'object_id', 'object_select', 'object_select_alpha',
            'object_select_filter', 'raw_coat_filter', 'raw_coat_reflection', 'raw_gi',
            'raw_lighting', 'raw_reflection', 'raw_refraction', 'raw_shadow', 'raw_sheen_filter',
            'raw_sheen_reflection', 'raw_total_light', 'reflection_filter', 'reflection_glossiness',
            'reflection_highlight_glossiness', 'reflection_ior', 'refraction_filter',
            'refraction_glossiness', 'render_id', 'sampler_info', 'sample_rate',
            'self_illumination', 'shadow', 'sheen', 'sheen_filter', 'sheen_glossiness',
            'sheen_reflection', 'sss', 'toon', 'toon_lighting', 'toon_specular',
            'total_light', 'velocity'
        ]

        self.setup_ui()

    def setup_ui(self):
        """设置用户界面"""
        self.root.title("文件查看管理器")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)

        # 创建菜单栏
        self.create_menu()

        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建工具栏
        self.create_toolbar(main_frame)

        # 创建分割面板
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # 左侧：目录树
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        # 右侧：详细信息
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        # 设置左侧目录树
        self.setup_tree_view(left_frame)

        # 设置右侧详细信息
        self.setup_detail_view(right_frame)

        # 应用主题
        self.apply_theme()

        # 初始扫描
        self.scan_directory()

    def create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="选择目录", command=self.select_directory)
        file_menu.add_command(label="刷新", command=self.scan_directory)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)

        # 视图菜单
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="视图", menu=view_menu)
        view_menu.add_command(label="展开全部", command=self.expand_all)
        view_menu.add_command(label="折叠全部", command=self.collapse_all)

    def create_toolbar(self, parent):
        """创建工具栏"""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 5))

        # 当前路径显示
        path_frame = ttk.Frame(toolbar)
        path_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(path_frame, text="当前目录:").pack(side=tk.LEFT, padx=(0, 5))
        self.path_var = tk.StringVar(value=self.current_path)
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var, state='readonly')
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        ttk.Button(path_frame, text="选择...", command=self.select_directory).pack(side=tk.LEFT)

        # 刷新按钮
        ttk.Button(toolbar, text="刷新", command=self.scan_directory).pack(side=tk.RIGHT, padx=(5, 0))

    def setup_tree_view(self, parent):
        """设置目录树视图"""
        # 创建框架
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # 创建树形控件
        self.tree = ttk.Treeview(tree_frame, show='tree')
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 创建滚动条
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=v_scrollbar.set)

        # 绑定事件
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        self.tree.bind('<Double-1>', self.on_tree_double_click)

    def setup_detail_view(self, parent):
        """设置详细信息视图"""
        # 创建框架
        detail_frame = ttk.Frame(parent)
        detail_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        self.detail_title = ttk.Label(detail_frame, text="选择一个序列查看详细信息", font=('Arial', 12, 'bold'))
        self.detail_title.pack(anchor=tk.W, pady=(0, 10))

        # 创建画布用于帧可视化
        self.canvas_frame = ttk.Frame(detail_frame)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = Canvas(self.canvas_frame, bg='#f0f0f0')
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 画布滚动条
        v_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=v_scrollbar.set)

        # 绑定鼠标滚轮
        self.canvas.bind('<MouseWheel>', self.on_canvas_scroll)

    def scan_directory(self):
        """扫描目录结构"""
        self.tree_data = {}
        self.expanded_items.clear()

        # 清空树
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            # 扫描目录
            for item in os.listdir(self.current_path):
                item_path = os.path.join(self.current_path, item)
                if os.path.isdir(item_path):
                    self.scan_sequence_directory(item, item_path)

            # 更新树显示
            self.update_tree_display()

        except Exception as e:
            messagebox.showerror("错误", f"扫描目录失败：{str(e)}")

    def scan_sequence_directory(self, seq_name, seq_path):
        """扫描序列目录"""
        sequence_data = {
            'name': seq_name,
            'path': seq_path,
            'rgb_frames': [],
            'channels': {},
            'total_frames': 0,
            'missing_frames': []
        }

        # 扫描RGB文件夹
        rgb_path = os.path.join(seq_path, 'RGB')
        if os.path.exists(rgb_path):
            sequence_data['rgb_frames'] = self.scan_png_files(rgb_path)

        # 扫描通道文件夹
        for item in os.listdir(seq_path):
            item_path = os.path.join(seq_path, item)
            if os.path.isdir(item_path) and item != 'RGB':
                frames = self.scan_png_files(item_path)
                if frames:
                    sequence_data['channels'][item] = frames

        # 计算总帧数和缺失帧
        all_frames = set()
        if sequence_data['rgb_frames']:
            all_frames.update(sequence_data['rgb_frames'])

        for channel_frames in sequence_data['channels'].values():
            all_frames.update(channel_frames)

        if all_frames:
            min_frame = min(all_frames)
            max_frame = max(all_frames)
            expected_frames = set(range(min_frame, max_frame + 1))
            sequence_data['missing_frames'] = sorted(expected_frames - all_frames)
            sequence_data['total_frames'] = len(expected_frames)

        self.tree_data[seq_name] = sequence_data

    def scan_png_files(self, directory):
        """扫描目录中的PNG文件并提取帧号"""
        frames = []
        try:
            for filename in os.listdir(directory):
                if filename.lower().endswith('.png'):
                    # 提取帧号
                    match = re.search(r'(\d{4})\.png$', filename)
                    if match:
                        frame_num = int(match.group(1))
                        frames.append(frame_num)
        except:
            pass

        return sorted(frames)

    def update_tree_display(self):
        """更新树形显示"""
        # 清空树
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 添加序列
        for seq_name, seq_data in sorted(self.tree_data.items()):
            # 计算统计信息
            rgb_count = len(seq_data['rgb_frames'])
            channel_count = len(seq_data['channels'])
            total_frames = seq_data['total_frames']
            missing_count = len(seq_data['missing_frames'])

            # 创建显示文本
            display_text = f"{seq_name} (RGB:{rgb_count}, 通道:{channel_count}, 总帧:{total_frames}"
            if missing_count > 0:
                display_text += f", 缺失:{missing_count}"
            display_text += ")"

            # 添加到树
            seq_item = self.tree.insert('', 'end', text=display_text, values=(seq_name,))

            # 添加RGB文件夹
            if seq_data['rgb_frames']:
                rgb_item = self.tree.insert(seq_item, 'end', text=f"RGB ({len(seq_data['rgb_frames'])}帧)", values=('rgb', seq_name))

            # 添加通道文件夹
            for channel_name, frames in sorted(seq_data['channels'].items()):
                channel_item = self.tree.insert(seq_item, 'end', text=f"{channel_name} ({len(frames)}帧)", values=('channel', seq_name, channel_name))

    def on_tree_select(self, event):
        """树选择事件"""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            values = self.tree.item(item, 'values')

            if len(values) >= 2:
                item_type = values[0]
                seq_name = values[1]

                if item_type == 'rgb':
                    self.show_rgb_details(seq_name)
                elif item_type == 'channel' and len(values) >= 3:
                    channel_name = values[2]
                    self.show_channel_details(seq_name, channel_name)
                else:
                    self.show_sequence_details(seq_name)

    def on_tree_double_click(self, event):
        """树双击事件"""
        item = self.tree.identify('item', event.x, event.y)
        if item:
            if item in self.tree.get_children():
                # 切换展开/折叠状态
                if self.tree.item(item, 'open'):
                    self.tree.item(item, open=False)
                else:
                    self.tree.item(item, open=True)

    def show_sequence_details(self, seq_name):
        """显示序列详细信息"""
        if seq_name not in self.tree_data:
            return

        seq_data = self.tree_data[seq_name]

        # 更新标题
        self.detail_title.config(text=f"序列: {seq_name}")

        # 清空画布
        self.canvas.delete('all')

        # 显示统计信息
        y_pos = 20
        self.canvas.create_text(10, y_pos, text=f"RGB帧数: {len(seq_data['rgb_frames'])}", anchor=tk.W, font=('Arial', 10))
        y_pos += 25

        self.canvas.create_text(10, y_pos, text=f"通道数量: {len(seq_data['channels'])}", anchor=tk.W, font=('Arial', 10))
        y_pos += 25

        self.canvas.create_text(10, y_pos, text=f"总帧数: {seq_data['total_frames']}", anchor=tk.W, font=('Arial', 10))
        y_pos += 25

        if seq_data['missing_frames']:
            self.canvas.create_text(10, y_pos, text=f"缺失帧数: {len(seq_data['missing_frames'])}", anchor=tk.W, font=('Arial', 10), fill='red')
            y_pos += 25

            # 显示缺失帧列表
            missing_text = f"缺失帧: {', '.join(map(str, seq_data['missing_frames'][:20]))}"
            if len(seq_data['missing_frames']) > 20:
                missing_text += "..."
            self.canvas.create_text(10, y_pos, text=missing_text, anchor=tk.W, font=('Arial', 9), fill='red')
            y_pos += 25

        # 显示帧可视化
        if seq_data['total_frames'] > 0:
            y_pos += 20
            self.draw_frame_visualization(seq_data, y_pos)

    def show_rgb_details(self, seq_name):
        """显示RGB详细信息"""
        if seq_name not in self.tree_data:
            return

        seq_data = self.tree_data[seq_name]

        # 更新标题
        self.detail_title.config(text=f"序列: {seq_name} - RGB")

        # 清空画布
        self.canvas.delete('all')

        # 显示帧列表
        y_pos = 20
        self.canvas.create_text(10, y_pos, text="RGB帧列表:", anchor=tk.W, font=('Arial', 10, 'bold'))
        y_pos += 25

        frames = seq_data['rgb_frames']
        for i, frame in enumerate(frames):
            if i % 10 == 0:
                y_pos += 20
                x_pos = 10
            else:
                x_pos += 60

            self.canvas.create_text(x_pos, y_pos, text=f"{frame:04d}", anchor=tk.W, font=('Arial', 9))

        # 显示帧可视化
        if frames:
            y_pos += 40
            self.draw_frame_visualization(seq_data, y_pos, show_rgb_only=True)

    def show_channel_details(self, seq_name, channel_name):
        """显示通道详细信息"""
        if seq_name not in self.tree_data or channel_name not in self.tree_data[seq_name]['channels']:
            return

        seq_data = self.tree_data[seq_name]
        frames = seq_data['channels'][channel_name]

        # 更新标题
        self.detail_title.config(text=f"序列: {seq_name} - {channel_name}")

        # 清空画布
        self.canvas.delete('all')

        # 显示帧列表
        y_pos = 20
        self.canvas.create_text(10, y_pos, text=f"{channel_name}帧列表:", anchor=tk.W, font=('Arial', 10, 'bold'))
        y_pos += 25

        for i, frame in enumerate(frames):
            if i % 10 == 0:
                y_pos += 20
                x_pos = 10
            else:
                x_pos += 60

            self.canvas.create_text(x_pos, y_pos, text=f"{frame:04d}", anchor=tk.W, font=('Arial', 9))

        # 显示帧可视化
        if frames:
            y_pos += 40
            self.draw_channel_frame_visualization(frames, seq_data['total_frames'], seq_data['missing_frames'], y_pos)

    def draw_frame_visualization(self, seq_data, start_y, show_rgb_only=False):
        """绘制帧可视化图"""
        if seq_data['total_frames'] == 0:
            return

        # 计算可视化参数
        total_frames = seq_data['total_frames']
        missing_frames = set(seq_data['missing_frames'])

        # 每行显示的帧数
        frames_per_row = 50
        rows = math.ceil(total_frames / frames_per_row)

        # 方块大小
        block_size = 8
        block_spacing = 1

        # 绘制标题
        self.canvas.create_text(10, start_y, text="帧存在可视化 (● = 存在, ○ = 缺失):", anchor=tk.W, font=('Arial', 10, 'bold'))
        start_y += 25

        # 获取帧范围
        all_frames = set()
        if seq_data['rgb_frames']:
            all_frames.update(seq_data['rgb_frames'])
        for channel_frames in seq_data['channels'].values():
            all_frames.update(channel_frames)

        if not all_frames:
            return

        min_frame = min(all_frames)
        max_frame = max(all_frames)

        # 绘制帧可视化
        for row in range(rows):
            y = start_y + row * (block_size + block_spacing * 2)

            for col in range(frames_per_row):
                frame_num = min_frame + row * frames_per_row + col

                if frame_num > max_frame:
                    break

                x = 10 + col * (block_size + block_spacing)

                # 判断帧是否存在
                if show_rgb_only:
                    exists = frame_num in seq_data['rgb_frames']
                else:
                    exists = frame_num in seq_data['rgb_frames'] or any(frame_num in frames for frames in seq_data['channels'].values())

                # 绘制方块
                if exists:
                    self.canvas.create_rectangle(x, y, x + block_size, y + block_size, fill='#4CAF50', outline='')
                else:
                    self.canvas.create_oval(x, y, x + block_size, y + block_size, fill='#F44336', outline='')

        # 更新画布滚动区域
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def draw_channel_frame_visualization(self, channel_frames, total_frames, missing_frames, start_y):
        """绘制通道帧可视化图"""
        if total_frames == 0:
            return

        # 计算可视化参数
        frames_per_row = 50
        rows = math.ceil(total_frames / frames_per_row)
        block_size = 8
        block_spacing = 1

        # 获取帧范围
        all_frames = set(channel_frames)
        if not all_frames:
            return

        min_frame = min(all_frames)
        max_frame = max(all_frames)

        # 绘制标题
        self.canvas.create_text(10, start_y, text="帧存在可视化 (● = 存在, ○ = 缺失):", anchor=tk.W, font=('Arial', 10, 'bold'))
        start_y += 25

        # 绘制帧可视化
        for row in range(rows):
            y = start_y + row * (block_size + block_spacing * 2)

            for col in range(frames_per_row):
                frame_num = min_frame + row * frames_per_row + col

                if frame_num > max_frame:
                    break

                x = 10 + col * (block_size + block_spacing)

                # 判断帧是否存在
                exists = frame_num in channel_frames

                # 绘制方块
                if exists:
                    self.canvas.create_rectangle(x, y, x + block_size, y + block_size, fill='#2196F3', outline='')
                else:
                    self.canvas.create_oval(x, y, x + block_size, y + block_size, fill='#F44336', outline='')

        # 更新画布滚动区域
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def on_canvas_scroll(self, event):
        """画布滚动事件"""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def select_directory(self):
        """选择目录"""
        directory = filedialog.askdirectory(
            title="选择要查看的目录",
            initialdir=self.current_path
        )
        if directory:
            self.current_path = directory
            self.path_var.set(directory)
            self.scan_directory()

    def expand_all(self):
        """展开全部"""
        for item in self.tree.get_children():
            self.tree.item(item, open=True)

    def collapse_all(self):
        """折叠全部"""
        for item in self.tree.get_children():
            self.tree.item(item, open=False)

    def apply_theme(self):
        """应用主题样式"""
        dark_mode = self.is_dark_mode()

        # 设置窗口样式
        try:
            if dark_mode:
                pywinstyles.change_header_color(self.root, "#1e1e1e")
                pywinstyles.change_border_color(self.root, "#333333")
                pywinstyles.apply_style(self.root, "dark")
                self.root.configure(bg="#2d2d30")
                self.canvas.configure(bg='#2d2d30')
            else:
                pywinstyles.apply_style(self.root, "normal")
                self.root.configure(bg="#ffffff")
                self.canvas.configure(bg='#f0f0f0')
        except:
            pass

    def is_dark_mode(self):
        """检测系统是否启用深色模式"""
        try:
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, regtype = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return value == 0  # 0 表示深色模式
        except:
            return False

def create_transparent_icon():
    """创建一个透明图标"""
    try:
        # 创建一个16x16的透明图像
        img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))

        # 保存为临时ico文件
        temp_dir = tempfile.gettempdir()
        icon_path = os.path.join(temp_dir, 'file_manager_icon.ico')
        img.save(icon_path, format='ICO')
        return icon_path
    except:
        return None

def main():
    """主函数"""
    root = tk.Tk()

    # 创建并设置透明图标
    transparent_icon = create_transparent_icon()
    if transparent_icon:
        try:
            root.iconbitmap(transparent_icon)
        except:
            root.wm_iconbitmap("")  # 如果失败则使用空字符串
    else:
        root.wm_iconbitmap("")  # 备用方法

    # 创建文件管理器
    app = FileManager(root)

    # 启动主循环
    root.mainloop()

    # 清理临时图标文件
    if transparent_icon and os.path.exists(transparent_icon):
        try:
            os.remove(transparent_icon)
        except:
            pass

if __name__ == "__main__":
    main()
