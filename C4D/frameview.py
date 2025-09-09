# -*- coding: utf-8 -*-
"""
跨文件夹PNG序列查看管理器
递归扫描整个目录，自动识别序列名，统计渲染完整度
支持分组渲染的帧分布查看，忽略通道图只统计RGB主文件
"""

import os
import sys
import re
import subprocess
import importlib.util
from collections import defaultdict
import math
import ctypes

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
    from tkinter import ttk, filedialog, messagebox, Canvas, Scrollbar, font as tkfont
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
        
        # 主题色系统
        self.theme_color = "#F5F5F5"  # 默认浅灰色，比白色稍微浅一点
        
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
            'total_light', 'velocity', 'effectsresult'
        ]

        # 界面设置默认值
        self.viz_font_size = 5  # 默认可视化字体大小
        self.ui_padding = {"padx": 8, "pady": 4}  # 默认界面间距
        self.card_padding = {"padx": 10, "pady": 6}  # 默认卡片间距

        self.setup_ui()

    def setup_ui(self):
        """设置用户界面"""
        self.root.title("文件查看管理器")
        self.root.geometry("1000x700")
        self.root.minsize(400, 300)

        # 创建菜单栏
        self.create_menu()

        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建全目录统计区域（顶部）
        self.create_overall_stats(main_frame)

        # 创建工具栏
        self.create_toolbar(main_frame)

        # 创建序列树形视图（可折叠）
        self.setup_tree_view(main_frame)

        # 应用主题
        self.apply_theme()

        # 初始扫描
        self.scan_directory()

    def create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root, bg="#2d2d2d", fg="#ffffff", 
                         activebackground="#404040", activeforeground="#ffffff")
        self.root.config(menu=menubar)

        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0, bg="#2d2d2d", fg="#ffffff",
                           activebackground="#404040", activeforeground="#ffffff")
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="选择目录", command=self.select_directory)
        file_menu.add_command(label="刷新", command=self.scan_directory)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)

        # 视图菜单
        view_menu = tk.Menu(menubar, tearoff=0, bg="#2d2d2d", fg="#ffffff",
                           activebackground="#404040", activeforeground="#ffffff")
        menubar.add_cascade(label="视图", menu=view_menu)
        view_menu.add_command(label="按完成率排序", command=self.sort_by_completion)
        view_menu.add_command(label="按名称排序", command=self.sort_by_name)
        view_menu.add_separator()
        
        # 文字大小调整
        view_menu.add_command(label="设置可视化字体大小...", command=self.show_font_size_dialog)
        
        # 主题色设置
        view_menu.add_command(label="设置主题色...", command=self.show_theme_color_dialog)
        
        # 界面缩放子菜单
        scale_menu = tk.Menu(view_menu, tearoff=0, bg="#2d2d2d", fg="#ffffff",
                            activebackground="#404040", activeforeground="#ffffff")
        view_menu.add_cascade(label="界面缩放", menu=scale_menu)
        scale_menu.add_command(label="紧凑模式", command=lambda: self.change_ui_scale("compact"))
        scale_menu.add_command(label="标准模式", command=lambda: self.change_ui_scale("normal"))
        scale_menu.add_command(label="舒适模式", command=lambda: self.change_ui_scale("comfortable"))

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
        """设置卡片式序列视图"""
        # 创建主滚动框架
        self.main_frame = ttk.Frame(parent)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 创建Canvas和滚动条用于卡片式布局
        self.canvas = tk.Canvas(self.main_frame, bg="#202020", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        # 配置滚动
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # 创建窗口，并绑定Canvas宽度变化事件
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # 绑定Canvas大小变化事件，使内容自适应宽度
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # 布局Canvas和滚动条
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # 绑定鼠标滚轮事件
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        
        # 存储卡片组件的字典
        self.sequence_cards = {}

    def on_canvas_configure(self, event):
        """Canvas大小变化时调整内容宽度并刷新可视化"""
        # 获取Canvas的宽度
        canvas_width = event.width
        
        # 调整scrollable_frame的宽度以匹配Canvas宽度
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
        
        # 更新滚动区域
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        # 延迟刷新可视化内容，提高响应速度（增加到120ms以降低拖动时的运算压力）
        if hasattr(self, '_resize_after_id'):
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(120, self.refresh_all_visualizations)

    def on_mousewheel(self, event):
        """鼠标滚轮事件处理"""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def refresh_all_visualizations(self):
        """刷新所有已打开的可视化内容"""
        try:
            # 强制更新界面布局以获取正确的宽度
            self.root.update_idletasks()
            
            # 刷新全局可视化
            if hasattr(self, 'global_viz_frame') and hasattr(self, 'global_inner_frame'):
                # 重新计算全局统计
                self.global_stats = self.calculate_global_stats()
                # 更新全局信息标签
                if hasattr(self, 'global_info_label'):
                    info_text = (f"总序列: {self.global_stats['total_sequences']} | "
                                f"总帧: {self.global_stats['total_frames']} | "
                                f"现有: {self.global_stats['existing_frames']}")
                    if self.global_stats['missing_frames'] > 0:
                        info_text += f" | 缺失: {self.global_stats['missing_frames']}"
                    self.global_info_label.config(text=info_text)
                # 重新生成全局可视化
                self.generate_global_visualization()
            
            # 刷新序列可视化
            if hasattr(self, 'sequence_cards'):
                for seq_name, card_info in self.sequence_cards.items():
                    # 检查可视化是否已经显示（现在默认都显示）
                    if card_info['viz_var'].get():
                        # 强制更新父容器尺寸
                        parent_frame = card_info['parent_frame']
                        parent_frame.update_idletasks()
                        
                        # 重新生成可视化内容
                        viz_frame = card_info['viz_frame']
                        seq_data = card_info['seq_data']
                        
                        # 使用统一的生成方法
                        self.generate_and_show_visualization(viz_frame, seq_data, parent_frame)
        except Exception as e:
            print(f"刷新可视化时出错: {e}")

    def create_sequence_card(self, parent, seq_name, seq_data):
        """创建单个序列的卡片"""
        # 计算完成率和状态
        completion_rate = seq_data['completion_rate']
        
        # 状态图标统一为白色
        if completion_rate >= 100:
            status_icon = "✓"
        elif completion_rate >= 90:
            status_icon = "●"
        else:
            status_icon = "○"
        status_color = "#ffffff"  # 统一使用白色

        # 创建卡片主框架 - 全宽显示
        card_frame = tk.Frame(parent, bg="#2d2d2d", relief="raised", bd=1)
        card_frame.pack(fill=tk.X, padx=8, pady=4)
        
        # 内部容器，提供内边距
        inner_frame = tk.Frame(card_frame, bg="#2d2d2d")
        inner_frame.pack(fill=tk.X, padx=12, pady=10)

        # 卡片头部 - 序列名称和状态
        header_frame = tk.Frame(inner_frame, bg="#2d2d2d")
        header_frame.pack(fill=tk.X)

        # 状态图标
        status_label = tk.Label(header_frame, text=status_icon, fg=status_color, 
                               bg="#2d2d2d", font=('Segoe UI', 14, 'bold'))
        status_label.pack(side=tk.LEFT, padx=(0, 10))

        # 序列名称
        name_label = tk.Label(header_frame, text=seq_name, fg="#ffffff", 
                             bg="#2d2d2d", font=('Segoe UI', 12, 'bold'))
        name_label.pack(side=tk.LEFT)

        # 完成率
        completion_label = tk.Label(header_frame, text=f"{completion_rate:.1f}%", 
                                   fg="#ffffff", bg="#2d2d2d", font=('Segoe UI', 11, 'bold'))
        completion_label.pack(side=tk.RIGHT)

        # 统计信息框架
        info_frame = tk.Frame(inner_frame, bg="#2d2d2d")
        info_frame.pack(fill=tk.X, pady=(8, 0))

        # 详细统计信息
        info_text = (f"帧范围: {seq_data['min_frame']:04d}-{seq_data['max_frame']:04d} | "
                    f"总帧: {seq_data['total_frames']} | "
                    f"现有: {seq_data['existing_count']}")
        
        if seq_data['missing_count'] > 0:
            info_text += f" | 缺失: {seq_data['missing_count']}"

        info_label = tk.Label(info_frame, text=info_text, fg="#cccccc", 
                             bg="#2d2d2d", font=('Segoe UI', 9))
        info_label.pack(anchor=tk.W)

        # 可视化区域（默认显示）
        viz_frame = tk.Frame(inner_frame, bg="#404040")
        viz_var = tk.BooleanVar(value=True)  # 默认为True，表示已显示
        
        # 显示可视化区域
        viz_frame.pack(fill=tk.X, pady=(8, 0))
        
        # 生成并显示可视化内容
        self.generate_and_show_visualization(viz_frame, seq_data, inner_frame)

        # 双击打开文件夹功能
        def on_double_click(event):
            self.open_rgb_folder(seq_data)

        # 绑定双击事件到卡片的各个组件
        for widget in [card_frame, inner_frame, header_frame, status_label, name_label, completion_label, info_frame, info_label]:
            widget.bind('<Double-Button-1>', on_double_click)

        # 返回卡片信息字典
        return {
            'frame': card_frame,
            'viz_frame': viz_frame,
            'viz_var': viz_var,
            'seq_data': seq_data,
            'parent_frame': inner_frame
        }

    def generate_and_show_visualization(self, viz_frame, seq_data, parent_frame):
        """生成并显示可视化内容"""
        try:
            # 清空现有内容
            for widget in viz_frame.winfo_children():
                widget.destroy()
            
            # 强制更新布局并等待完成
            parent_frame.update_idletasks()
            self.root.update()  # 强制完成所有待处理的界面更新
            
            # 根据当前卡片宽度动态生成可视化
            available_width = max(100, parent_frame.winfo_width() - 40)  # 确保最小宽度
            
            # 生成自适应宽度的可视化文本（内部会重新计算字符数）
            viz_text = self.generate_adaptive_frame_visualization_text(seq_data, available_width)
            
            # 使用 tkinter.font 精确测量字符像素宽度（避免小字号时估算过大）
            try:
                font_obj = tkfont.Font(family='Consolas', size=self.viz_font_size)
                char_width = max(1, font_obj.measure('█'))
            except Exception:
                char_width = max(3, int(self.viz_font_size * 0.6))
            chars_per_line = max(1, available_width // char_width)
        except Exception as e:
            print(f"生成可视化内容时出错: {e}")
            viz_text = f"可视化生成错误: {str(e)}"
            chars_per_line = 50  # 默认值
        
        # 动态计算实际需要的行数
        actual_lines = max(1, viz_text.count('\n') + 1)
        
        # 创建可视化文本标签
        viz_text_widget = tk.Text(viz_frame, 
                                height=actual_lines,
                                width=chars_per_line,  # 设置宽度以填满可用空间
                                bg="#404040", fg="#ffffff",
                                font=('Consolas', self.viz_font_size),
                                relief="flat", 
                                borderwidth=0,
                                wrap=tk.NONE,
                                state=tk.DISABLED,
                                cursor="arrow",
                                selectbackground="#505050",
                                padx=5, pady=2)  # 添加内边距使左右对称
        
        # 插入文本并配置标签
        viz_text_widget.config(state=tk.NORMAL)
        viz_text_widget.delete(1.0, tk.END)
        viz_text_widget.insert(tk.END, viz_text)
        viz_text_widget.config(state=tk.DISABLED)
        viz_text_widget.pack(fill=tk.X, padx=8, pady=8)
        
        # 强制更新Text widget的尺寸
        viz_text_widget.update_idletasks()

    def toggle_visualization(self, viz_frame, viz_var, seq_data, toggle_btn, parent_frame):
        """切换可视化显示"""
        if viz_var.get():
            # 隐藏可视化
            viz_frame.pack_forget()
            toggle_btn.config(text="▶")
            viz_var.set(False)
        else:
            # 显示可视化
            viz_frame.pack(fill=tk.X, pady=(8, 0))
            
            # 清空并重新创建可视化内容
            for widget in viz_frame.winfo_children():
                widget.destroy()
            
            # 根据当前卡片宽度动态生成可视化
            parent_frame.update_idletasks()
            available_width = parent_frame.winfo_width() - 40  # 减去内边距
            
            # 生成自适应宽度的可视化文本
            viz_text = self.generate_adaptive_frame_visualization_text(seq_data, available_width)

            # 计算每行字符数（使用字体测量）
            try:
                font_obj = tkfont.Font(family='Consolas', size=self.viz_font_size)
                char_width = max(1, font_obj.measure('█'))
            except Exception:
                char_width = max(3, int(self.viz_font_size * 0.6))
            chars_per_line = max(1, (available_width) // char_width)

            # 创建可视化文本标签 - 使用Text widget以获得更好的显示效果
            viz_text_widget = tk.Text(viz_frame, 
                                    height=max(1, viz_text.count('\n') + 1),
                                    width=chars_per_line,
                                    bg="#404040", fg="#ffffff",
                                    font=('Consolas', self.viz_font_size),
                                    relief="flat", 
                                    borderwidth=0,
                                    wrap=tk.NONE,
                                    state=tk.DISABLED,
                                    cursor="arrow",
                                    selectbackground="#505050")
            
            viz_text_widget.pack(anchor=tk.W, padx=12, pady=10, fill=tk.X)
            
            # 插入文本内容
            viz_text_widget.config(state=tk.NORMAL)
            viz_text_widget.insert(tk.END, viz_text)
            viz_text_widget.config(state=tk.DISABLED)
            
            toggle_btn.config(text="▼")
            viz_var.set(True)

    def on_tree_open(self, event):
        """树形控件展开事件"""
        pass

    def on_tree_close(self, event):
        """树形控件折叠事件"""
        pass

    def create_overall_stats(self, parent):
        """创建全目录统计区域"""
        # 创建全局总览卡片
        self.create_global_overview_card(parent)

    def create_global_overview_card(self, parent):
        """创建全局总览卡片，样式与序列卡片相同"""
        # 计算全局统计
        global_stats = self.calculate_global_stats()
        
        # 创建卡片主框架
        card_frame = tk.Frame(parent, bg="#2f2f2f", relief="raised", bd=2)  # 创建卡片主框架 - 使用比下方卡片更亮的灰色
        card_frame.pack(fill=tk.X, padx=8, pady=8)
        # 内部容器（使用与卡片一致的浅灰色）
        inner_frame = tk.Frame(card_frame, bg="#2f2f2f")
        inner_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # 卡片头部
        header_frame = tk.Frame(inner_frame, bg="#2f2f2f")
        header_frame.pack(fill=tk.X)

        # 状态图标
        status_label = tk.Label(header_frame, text="🌐", fg="#ffffff", 
                               bg="#2f2f2f", font=('Segoe UI', 14, 'bold'))
        status_label.pack(side=tk.LEFT, padx=(0, 10))

        # 全局标题
        name_label = tk.Label(header_frame, text="全局总览", fg="#ffffff", 
                              bg="#2f2f2f", font=('Segoe UI', 12, 'bold'))
        name_label.pack(side=tk.LEFT)

        # 整体完成率
        self.global_completion_label = tk.Label(header_frame, text=f"{global_stats['completion_rate']:.1f}%", 
                                               fg="#ffffff", bg="#2f2f2f", font=('Segoe UI', 11, 'bold'))
        self.global_completion_label.pack(side=tk.RIGHT)

        # 统计信息框架
        info_frame = tk.Frame(inner_frame, bg="#2f2f2f")
        info_frame.pack(fill=tk.X, pady=(8, 0))

        # 详细统计信息
        info_text = (f"总序列: {global_stats['total_sequences']} | "
                    f"总帧: {global_stats['total_frames']} | "
                    f"现有: {global_stats['existing_frames']}")
        
        if global_stats['missing_frames'] > 0:
            info_text += f" | 缺失: {global_stats['missing_frames']}"

        # 存储为实例变量以便更新
        self.global_info_label = tk.Label(info_frame, text=info_text, fg="#cccccc", 
                             bg="#2f2f2f", font=('Segoe UI', 9))
        self.global_info_label.pack(anchor=tk.W)

        # 全局可视化区域
        viz_frame = tk.Frame(inner_frame, bg="#3a3a3a")  # 稍微不同的背景色（比单列卡片更亮）
        viz_frame.pack(fill=tk.X, pady=(8, 0))
        
        # 生成并显示全局可视化内容
        self.global_viz_frame = viz_frame
        self.global_inner_frame = inner_frame
        self.generate_global_visualization()

        # 存储全局统计数据

    def update_global_overview_card(self):
        """更新全局总览卡片的显示信息"""
        try:
            # 重新计算全局统计
            global_stats = self.calculate_global_stats()
            
            # 更新完成率标签
            if hasattr(self, 'global_completion_label'):
                self.global_completion_label.config(text=f"{global_stats['completion_rate']:.1f}%")
            
            # 更新详细统计信息
            if hasattr(self, 'global_info_label'):
                info_text = (f"总序列: {global_stats['total_sequences']} | "
                            f"总帧: {global_stats['total_frames']} | "
                            f"现有: {global_stats['existing_frames']}")
                
                if global_stats['missing_frames'] > 0:
                    info_text += f" | 缺失: {global_stats['missing_frames']}"
                
                self.global_info_label.config(text=info_text)
                
        except Exception as e:
            print(f"更新全局概览卡片时出错: {e}")
        self.global_stats = global_stats

    def generate_global_sequence_visualization(self, available_width):
        """生成全局序列连续可视化，使用默认色和主题色交替显示不同序列"""
        try:
            if not self.tree_data:
                return "无序列数据"
            
            # 使用 tkinter.font 精确测量字符像素宽度
            try:
                font_obj = tkfont.Font(family='Consolas', size=self.viz_font_size)
                char_width = max(1, font_obj.measure('█'))
            except Exception:
                char_width = max(3, int(self.viz_font_size * 0.6))
            chars_per_line = max(1, available_width // char_width)
            
            if chars_per_line < 10:
                return "宽度不足以显示可视化"
            
            # 收集所有序列的帧数据，按序列顺序连接
            all_sequence_data = []  # 存储(字符, 颜色类型)的元组
            
            # 遍历所有序列（按排序后的顺序）
            sequence_index = 0
            for seq_name, seq_data in sorted(self.tree_data.items()):
                frames = seq_data.get('frames', [])
                min_frame = seq_data.get('min_frame', 1)
                max_frame = seq_data.get('max_frame', 1)
                
                if not frames:
                    continue
                    
                # 确定这个序列的颜色：偶数序列用默认色，奇数序列用主题色
                use_theme_color = (sequence_index % 2 == 1)
                
                # 为这个序列生成帧范围
                frame_range = list(range(min_frame, max_frame + 1))
                
                for frame_num in frame_range:
                    if frame_num in frames:
                        char = '█'  # 存在的帧
                    else:
                        char = ' '  # 缺失的帧
                    
                    all_sequence_data.append((char, use_theme_color))
                
                sequence_index += 1
            
            # 按行分割进行换行显示
            viz_lines = []
            current_line = []
            
            for char, use_theme_color in all_sequence_data:
                current_line.append(char)
                
                # 达到每行字符数限制时换行
                if len(current_line) >= chars_per_line:
                    viz_lines.append(''.join(current_line))
                    current_line = []
            
            # 添加最后一行（如果有剩余字符）
            if current_line:
                viz_lines.append(''.join(current_line))
            
            return '\n'.join(viz_lines)
                
        except Exception as e:
            return f"生成全局可视化错误: {str(e)[:30]}..."

    def create_colored_global_visualization(self, viz_text):
        """创建支持多色显示的全局可视化Text widget"""
        try:
            # 清空现有内容
            for widget in self.global_viz_frame.winfo_children():
                widget.destroy()
            
            # 使用 tkinter.font 精确测量字符像素宽度
            available_width = max(200, self.global_inner_frame.winfo_width() - 40)
            try:
                font_obj = tkfont.Font(family='Consolas', size=self.viz_font_size)
                char_width = max(1, font_obj.measure('█'))
            except Exception:
                char_width = max(3, int(self.viz_font_size * 0.6))
            chars_per_line = max(1, available_width // char_width)
            
            # 重新生成带颜色信息的序列数据（与generate_global_sequence_visualization保持一致）
            all_sequence_data = []  # 存储(字符, 颜色类型)的元组
            
            # 遍历所有序列收集颜色信息
            sequence_index = 0
            for seq_name, seq_data in sorted(self.tree_data.items()):
                frames = seq_data.get('frames', [])
                min_frame = seq_data.get('min_frame', 1)
                max_frame = seq_data.get('max_frame', 1)
                
                if not frames:
                    continue
                    
                # 确定这个序列的颜色：偶数序列用默认色，奇数序列用主题色
                use_theme_color = (sequence_index % 2 == 1)
                
                # 为这个序列生成帧范围
                frame_range = list(range(min_frame, max_frame + 1))
                
                for frame_num in frame_range:
                    if frame_num in frames:
                        char = '█'  # 存在的帧
                    else:
                        char = ' '  # 缺失的帧
                    
                    all_sequence_data.append((char, use_theme_color))
                
                sequence_index += 1
            
            # 创建Text widget
            viz_text_widget = tk.Text(self.global_viz_frame, 
                                    height=max(1, len(all_sequence_data) // chars_per_line + 1),
                                    width=chars_per_line,  # 设置宽度以填满可用空间
                                    bg="#2d4a2d", fg="#ffffff",
                                    font=('Consolas', self.viz_font_size),
                                    relief="flat", 
                                    borderwidth=0,
                                    wrap=tk.NONE,
                                    state=tk.DISABLED,
                                    cursor="arrow",
                                    selectbackground="#404040",
                                    padx=5, pady=2)
            
            # 配置颜色标签
            viz_text_widget.tag_configure("default", foreground="#ffffff")
            viz_text_widget.tag_configure("theme", foreground=self.theme_color)
            
            # 插入带颜色的文本
            viz_text_widget.config(state=tk.NORMAL)
            viz_text_widget.delete(1.0, tk.END)
            
            current_col = 0
            for char, use_theme_color in all_sequence_data:
                tag = "theme" if use_theme_color else "default"
                viz_text_widget.insert(tk.END, char, tag)
                
                current_col += 1
                # 换行
                if current_col >= chars_per_line:
                    viz_text_widget.insert(tk.END, '\n')
                    current_col = 0
            
            viz_text_widget.config(state=tk.DISABLED)
            viz_text_widget.pack(fill=tk.X, padx=8, pady=8)
            
        except Exception as e:
            # 如果多色显示失败，使用简单文本显示
            print(f"多色可视化创建失败: {e}")
            viz_text_widget = tk.Text(self.global_viz_frame, 
                                    height=max(1, viz_text.count('\n') + 1),
                                    width=50,  # 默认宽度
                                    bg="#2d4a2d", fg="#ffffff",
                                    font=('Consolas', self.viz_font_size),
                                    relief="flat", 
                                    borderwidth=0,
                                    wrap=tk.NONE,
                                    state=tk.DISABLED,
                                    cursor="arrow",
                                    selectbackground="#404040",
                                    padx=5, pady=2)
            
            viz_text_widget.config(state=tk.NORMAL)
            viz_text_widget.delete(1.0, tk.END)
            viz_text_widget.insert(tk.END, viz_text)
            viz_text_widget.config(state=tk.DISABLED)
            viz_text_widget.pack(fill=tk.X, padx=8, pady=8)

    def calculate_global_stats(self):
        """计算全局统计数据 - 超级简化版本"""
        try:
            if not self.tree_data:
                return {
                    'total_sequences': 0,
                    'total_frames': 0,
                    'existing_frames': 0,
                    'missing_frames': 0,
                    'completion_rate': 0.0,
                    'min_frame': 1,
                    'max_frame': 1,
                    'frames': [],
                    'existing_count': 0
                }

            # 简单统计，不做复杂的帧映射
            total_sequences = len(self.tree_data)
            total_frames = 0
            existing_frames = 0
            all_frames = []
            
            # 直接累加所有序列的统计，使用安全的字段访问
            for seq_name, seq_data in self.tree_data.items():
                # 使用 get 方法安全访问字段
                seq_total = seq_data.get('total_frames', 0)
                seq_existing = seq_data.get('existing_count', 0)
                seq_frames = seq_data.get('frames', [])
                
                total_frames += seq_total
                existing_frames += seq_existing
                # 直接使用原始帧号（不重新映射）
                all_frames.extend(seq_frames)

            missing_frames = total_frames - existing_frames
            completion_rate = (existing_frames / total_frames * 100) if total_frames > 0 else 0.0
            
            # 找到实际的帧范围
            if all_frames:
                min_frame = min(all_frames)
                max_frame = max(all_frames)
            else:
                min_frame = 1
                max_frame = 1

            return {
                'total_sequences': total_sequences,
                'total_frames': total_frames,
                'existing_frames': existing_frames,
                'missing_frames': missing_frames,
                'completion_rate': completion_rate,
                'min_frame': min_frame,
                'max_frame': max_frame,
                'frames': all_frames,
                'existing_count': existing_frames
            }
        except Exception as e:
            print(f"计算全局统计时出错: {e}")
            # 返回安全的默认值
            return {
                'total_sequences': 0,
                'total_frames': 0,
                'existing_frames': 0,
                'missing_frames': 0,
                'completion_rate': 0.0,
                'min_frame': 1,
                'max_frame': 1,
                'frames': [],
                'existing_count': 0
            }

    def generate_global_visualization(self):
        """生成全局可视化 - 超级简化和安全版本"""
        viz_text = "加载中..."
        
        try:
            # 检查必要的属性
            if not hasattr(self, 'global_viz_frame'):
                viz_text = "全局可视化框架未初始化"
                return
            
            # 清空现有内容
            for widget in self.global_viz_frame.winfo_children():
                widget.destroy()
            
            # 检查是否有数据
            if not hasattr(self, 'tree_data') or not self.tree_data:
                viz_text = "无序列数据"
            else:
                # 计算全局统计数据
                self.global_stats = self.calculate_global_stats()
                
                # 检查统计数据是否有效
                if self.global_stats['total_frames'] == 0:
                    viz_text = "所有序列均为空"
                else:
                    # 获取可用宽度
                    try:
                        self.global_inner_frame.update_idletasks()
                        available_width = max(200, self.global_inner_frame.winfo_width() - 40)
                    except:
                        available_width = 400  # 使用默认宽度
                    
                    # 生成全局序列连续可视化
                    viz_text = self.generate_global_sequence_visualization(available_width)
                
        except Exception as e:
            print(f"生成全局可视化时出错: {e}")
            viz_text = f"错误: {str(e)[:50]}..."  # 限制错误信息长度
        
        # 创建支持多色显示的可视化文本标签
        self.create_colored_global_visualization(viz_text)

    def update_overall_stats(self):
        """更新全目录统计信息"""
        # 现在使用全局卡片替代传统统计标签
        if hasattr(self, 'global_viz_frame'):
            # 重新计算并更新全局统计
            self.global_stats = self.calculate_global_stats()
            
            # 更新完成率标签
            if hasattr(self, 'global_completion_label'):
                self.global_completion_label.config(text=f"{self.global_stats['completion_rate']:.1f}%")
            
            # 更新全局信息标签
            if hasattr(self, 'global_info_label'):
                info_text = (f"总序列: {self.global_stats['total_sequences']} | "
                            f"总帧: {self.global_stats['total_frames']} | "
                            f"现有: {self.global_stats['existing_frames']}")
                if self.global_stats['missing_frames'] > 0:
                    info_text += f" | 缺失: {self.global_stats['missing_frames']}"
                self.global_info_label.config(text=info_text)
            
            # 重新生成全局可视化
            self.generate_global_visualization()

    def scan_directory(self):
        """递归扫描目录中的所有PNG文件，按序列分组"""
        self.tree_data = {}
        
        # 初始化expanded_items（如果不存在）
        if not hasattr(self, 'expanded_items'):
            self.expanded_items = set()

        try:
            # 递归扫描所有PNG文件
            all_png_files = self.scan_all_png_files(self.current_path)

            # 按序列分组
            sequences = self.group_files_by_sequence(all_png_files)

            # 处理每个序列
            for seq_name, files in sequences.items():
                self.process_sequence(seq_name, files)

            # 更新列表显示
            self.update_sequence_list()

            # 更新全目录统计
            self.update_overall_stats()

        except Exception as e:
            messagebox.showerror("错误", f"扫描目录失败：{str(e)}")

    def scan_all_png_files(self, directory):
        """递归扫描目录中的所有PNG文件"""
        png_files = []

        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith('.png'):
                        full_path = os.path.join(root, file)
                        png_files.append(full_path)
        except Exception as e:
            print(f"扫描目录时出错: {e}")

        return png_files

    def group_files_by_sequence(self, png_files):
        """按序列名分组PNG文件"""
        sequences = defaultdict(list)

        for file_path in png_files:
            filename = os.path.basename(file_path)

            # 提取序列名和帧号
            seq_info = self.parse_sequence_filename(filename)
            if seq_info:
                seq_name, frame_num = seq_info
                sequences[seq_name].append((frame_num, file_path))

        return sequences

    def parse_sequence_filename(self, filename):
        """解析PNG文件名，提取序列名和帧号"""
        # 匹配模式：序列名_帧号.png 或 序列名.帧号.png
        # 忽略通道后缀（如果有的话）
        patterns = [
            r'^(.+?)_(\d{4})\.png$',  # sequence_0001.png
            r'^(.+?)\.(\d{4})\.png$', # sequence.0001.png
            r'^(.+?)(\d{4})\.png$',   # sequence0001.png
        ]

        for pattern in patterns:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                seq_name = match.group(1)
                frame_num = int(match.group(2))

                # 移除常见的通道后缀
                for suffix in self.channel_suffixes:
                    if seq_name.lower().endswith('_' + suffix.lower()):
                        seq_name = seq_name[:-len('_' + suffix)]
                        break
                    elif seq_name.lower().endswith('.' + suffix.lower()):
                        seq_name = seq_name[:-len('.' + suffix)]
                        break

                return seq_name, frame_num

        return None

    def process_sequence(self, seq_name, files):
        """处理单个序列的数据"""
        # 提取所有帧号
        frames = []
        file_paths = {}

        for frame_num, file_path in files:
            frames.append(frame_num)
            file_paths[frame_num] = file_path

        frames = sorted(set(frames))  # 去重并排序

        if not frames:
            return

        # 计算序列统计信息
        min_frame = min(frames)
        max_frame = max(frames)
        expected_frames = set(range(min_frame, max_frame + 1))
        existing_frames = set(frames)
        missing_frames = sorted(expected_frames - existing_frames)

        sequence_data = {
            'name': seq_name,
            'frames': frames,
            'file_paths': file_paths,
            'min_frame': min_frame,
            'max_frame': max_frame,
            'total_frames': len(expected_frames),
            'existing_count': len(existing_frames),
            'missing_frames': missing_frames,
            'missing_count': len(missing_frames),
            'completion_rate': len(existing_frames) / len(expected_frames) * 100 if expected_frames else 0
        }

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

    def update_sequence_list(self):
        """更新序列列表显示 - 卡片式布局"""
        # 清空现有卡片
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.sequence_cards.clear()

        # 为每个序列创建卡片
        for seq_name, seq_data in sorted(self.tree_data.items()):
            card_info = self.create_sequence_card(self.scrollable_frame, seq_name, seq_data)
            self.sequence_cards[seq_name] = card_info

        # 更新滚动区域
        self.scrollable_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def open_rgb_folder(self, seq_data):
        """打开RGB文件夹"""
        if not seq_data['file_paths']:
            messagebox.showwarning("提示", "未找到文件路径信息")
            return
        
        # 获取第一个文件的路径
        first_frame = min(seq_data['file_paths'].keys())
        file_path = seq_data['file_paths'][first_frame]
        
        # 获取文件所在目录
        file_dir = os.path.dirname(file_path)
        
        # 查找RGB文件夹
        rgb_directory = None
        
        # 方法1: 如果当前目录就包含RGB，直接使用
        if 'RGB' in file_dir.upper():
            # 找到RGB文件夹的路径
            path_parts = file_dir.split(os.sep)
            try:
                rgb_index = -1
                for i, part in enumerate(path_parts):
                    if part.upper() == 'RGB':
                        rgb_index = i
                        break
                
                if rgb_index >= 0:
                    rgb_directory = os.sep.join(path_parts[:rgb_index + 1])
            except:
                pass
        
        # 方法2: 在同级目录下查找RGB文件夹
        if not rgb_directory:
            parent_dir = os.path.dirname(file_dir)
            potential_rgb = os.path.join(parent_dir, 'RGB')
            if os.path.exists(potential_rgb) and os.path.isdir(potential_rgb):
                rgb_directory = potential_rgb
        
        # 方法3: 在当前目录的同级查找rgb文件夹（小写）
        if not rgb_directory:
            parent_dir = os.path.dirname(file_dir)
            potential_rgb = os.path.join(parent_dir, 'rgb')
            if os.path.exists(potential_rgb) and os.path.isdir(potential_rgb):
                rgb_directory = potential_rgb
        
        # 方法4: 如果当前是shadow文件夹，查找同级的rgb文件夹
        if not rgb_directory and 'shadow' in file_dir.lower():
            # 替换shadow为rgb
            rgb_directory = file_dir.lower().replace('shadow', 'rgb')
            if not (os.path.exists(rgb_directory) and os.path.isdir(rgb_directory)):
                # 尝试大写RGB
                rgb_directory = file_dir.lower().replace('shadow', 'RGB')
                if not (os.path.exists(rgb_directory) and os.path.isdir(rgb_directory)):
                    rgb_directory = None
        
        # 如果都没找到，使用原文件目录
        if not rgb_directory:
            rgb_directory = file_dir
            messagebox.showinfo("提示", f"未找到RGB文件夹，将打开原文件目录:\n{rgb_directory}")
        
        # 在文件管理器中打开目录
        try:
            if os.name == 'nt':  # Windows
                os.startfile(rgb_directory)
            elif os.name == 'posix':  # macOS/Linux
                subprocess.run(['xdg-open', rgb_directory])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件夹:\n{rgb_directory}\n\n错误: {str(e)}")

    def generate_adaptive_frame_visualization_text(self, seq_data, available_width):
        """生成精确的帧可视化文本 - 每个字符精确对应帧，只使用实心块和空白"""
        if seq_data['total_frames'] == 0:
            return "无帧数据"
        
        existing_frames = set(seq_data['frames'])
        min_frame = seq_data['min_frame']
        max_frame = seq_data['max_frame']
        total_range = max_frame - min_frame + 1
        
        # 使用 tkinter.font 测量字符像素宽度，确保小字号也能正确计算
        try:
            font_obj = tkfont.Font(family='Consolas', size=self.viz_font_size)
            font_width = max(1, font_obj.measure('█'))
        except Exception:
            font_width = max(3, int(self.viz_font_size * 0.6))
        chars_per_line = max(1, available_width // font_width)
        
        # 调试信息
        # print(f"字号: {self.viz_font_size}, 字符宽度: {font_width}, 可用宽度: {available_width}, 每行字符数: {chars_per_line}")
        
        viz_lines = []
        current_line = []
        
        # 精确显示：每个字符对应一个帧
        for frame_num in range(min_frame, max_frame + 1):
            if frame_num in existing_frames:
                current_line.append("█")  # 实心块 - 帧存在
            else:
                current_line.append(" ")  # 空白 - 帧缺失
            
            # 达到每行字符数限制时换行
            if len(current_line) >= chars_per_line:
                viz_lines.append(''.join(current_line))
                current_line = []
        
        # 添加最后一行（如果有剩余字符）
        if current_line:
            viz_lines.append(''.join(current_line))
        
        return '\n'.join(viz_lines)

    def generate_frame_visualization_text(self, seq_data):
        """生成帧可视化的多行文本表示"""
        if seq_data['total_frames'] == 0:
            return "无帧数据"
        
        existing_frames = set(seq_data['frames'])
        min_frame = seq_data['min_frame']
        max_frame = seq_data['max_frame']
        total_range = max_frame - min_frame + 1
        
        # 每行显示的帧数和最大行数
        frames_per_line = 60
        max_lines = 8
        max_display_frames = frames_per_line * max_lines
        
        viz_lines = []
        
        if total_range <= max_display_frames:
            # 直接显示所有帧，分行显示
            current_line = []
            for frame_num in range(min_frame, max_frame + 1):
                if frame_num in existing_frames:
                    current_line.append("█")  # 实心块
                else:
                    current_line.append("░")  # 空心块
                
                # 每行60个字符就换行
                if len(current_line) >= frames_per_line:
                    viz_lines.append(''.join(current_line))
                    current_line = []
            
            # 添加最后一行（如果有剩余）
            if current_line:
                viz_lines.append(''.join(current_line))
        else:
            # 采样显示，保持多行格式
            step = total_range / max_display_frames
            current_line = []
            
            for i in range(max_display_frames):
                frame_start = int(min_frame + i * step)
                frame_end = int(min_frame + (i + 1) * step)
                
                # 检查这个范围内是否有帧
                has_frame = any(f in existing_frames for f in range(frame_start, frame_end + 1))
                
                if has_frame:
                    current_line.append("█")  # 实心块
                else:
                    current_line.append("░")  # 空心块
                
                # 每行60个字符就换行
                if len(current_line) >= frames_per_line:
                    viz_lines.append(''.join(current_line))
                    current_line = []
            
            # 添加最后一行（如果有剩余）
            if current_line:
                viz_lines.append(''.join(current_line))
        
        # 添加帧号标记行（每10个帧显示一个标记）
        if viz_lines and total_range > 10:
            marker_line = []
            frames_shown = min(total_range, len(viz_lines[0]) if viz_lines else 0)
            
            for i in range(frames_shown):
                actual_frame = min_frame + i * (total_range / frames_shown) if total_range > frames_shown else min_frame + i
                if int(actual_frame) % 10 == 0:
                    marker_line.append("|")
                else:
                    marker_line.append(" ")
            
            viz_lines.append(''.join(marker_line))
            
            # 添加帧号行
            number_line = []
            for i in range(0, frames_shown, 10):
                actual_frame = min_frame + i * (total_range / frames_shown) if total_range > frames_shown else min_frame + i
                frame_str = f"{int(actual_frame):04d}"
                number_line.extend(list(frame_str))
                # 填充空格到下一个10的倍数位置
                while len(number_line) % 10 != 0 and len(number_line) < frames_shown:
                    number_line.append(" ")
            
            viz_lines.append(''.join(number_line[:frames_shown]))
        
        return '\n'.join(viz_lines)

    def on_tree_select(self, event):
        """选择事件 - 在卡片式布局中不需要特殊处理"""
        pass



    def on_tree_double_click(self, event):
        """双击事件 - 在卡片式布局中由卡片自己处理"""
        pass



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

    def sort_by_completion(self):
        """按完成率排序"""
        self.sort_sequences('completion')

    def sort_by_name(self):
        """按名称排序"""
        self.sort_sequences('name')

    def sort_sequences(self, sort_by):
        """排序序列"""
        if sort_by == 'completion':
            # 按完成率降序排序
            sorted_items = sorted(self.tree_data.items(),
                                key=lambda x: x[1]['completion_rate'],
                                reverse=True)
        else:
            # 按名称排序
            sorted_items = sorted(self.tree_data.items())

        # 重新创建排序后的数据
        self.tree_data = dict(sorted_items)

        # 刷新显示
        self.update_sequence_list()

    def show_font_size_dialog(self):
        """显示字体大小输入对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("设置可视化字体大小")
        dialog.geometry("300x150")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 150
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 75
        dialog.geometry(f"+{x}+{y}")
        
        # 当前字体大小标签
        current_label = tk.Label(dialog, text=f"当前字体大小: {self.viz_font_size}号", 
                                font=('Segoe UI', 10))
        current_label.pack(pady=10)
        
        # 输入框
        input_frame = tk.Frame(dialog)
        input_frame.pack(pady=10)
        
        tk.Label(input_frame, text="新字体大小:", font=('Segoe UI', 9)).pack(side=tk.LEFT)
        
        font_size_var = tk.StringVar(value=str(self.viz_font_size))
        entry = tk.Entry(input_frame, textvariable=font_size_var, width=10, font=('Segoe UI', 9))
        entry.pack(side=tk.LEFT, padx=(10, 0))
        entry.select_range(0, tk.END)
        entry.focus()
        
        # 按钮
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=20)
        
        def apply_font_size():
            try:
                new_size = int(font_size_var.get())
                if 1 <= new_size <= 20:
                    self.change_viz_font_size(new_size)
                    dialog.destroy()
                else:
                    tk.messagebox.showerror("错误", "字体大小必须在1-20之间")
            except ValueError:
                tk.messagebox.showerror("错误", "请输入有效的数字")
        
        def on_enter(event):
            apply_font_size()
        
        entry.bind('<Return>', on_enter)
        
        tk.Button(button_frame, text="确定", command=apply_font_size,
                 bg="#0078d4", fg="white", font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="取消", command=dialog.destroy,
                 font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)

    def show_theme_color_dialog(self):
        """显示主题色设置对话框"""
        from tkinter import colorchooser
        
        # 打开颜色选择器
        color = colorchooser.askcolor(
            initialcolor=self.theme_color,
            title="选择主题色"
        )
        
        if color[1]:  # 如果用户选择了颜色
            self.theme_color = color[1]
            # 刷新所有可视化以应用新主题色
            self.refresh_all_visualizations()

    def change_viz_font_size(self, font_size):
        """改变可视化字体大小"""
        self.viz_font_size = font_size
        # 强制更新界面布局
        self.root.update_idletasks()
        # 重新生成所有可视化
        self.refresh_all_visualizations()

    def change_ui_scale(self, scale_mode):
        """改变界面缩放模式"""
        if scale_mode == "compact":
            # 紧凑模式：减小间距和边距
            self.ui_padding = {"padx": 4, "pady": 2}
            self.card_padding = {"padx": 6, "pady": 3}
        elif scale_mode == "comfortable":
            # 舒适模式：增加间距和边距
            self.ui_padding = {"padx": 12, "pady": 8}
            self.card_padding = {"padx": 16, "pady": 12}
        else:
            # 标准模式
            self.ui_padding = {"padx": 8, "pady": 4}
            self.card_padding = {"padx": 10, "pady": 6}
        
        # 重新创建界面
        self.update_sequence_list()

    def apply_theme(self):
        """应用Win11深色主题样式"""
        try:
            # 应用Win11深色主题
            pywinstyles.apply_style(self.root, "dark")
            
            # Win11深色主题颜色
            dark_bg = "#202020"          # 主背景色
            dark_surface = "#2d2d2d"     # 表面颜色
            dark_surface_light = "#404040" # 浅表面颜色
            text_primary = "#ffffff"      # 主要文字颜色
            text_secondary = "#cccccc"    # 次要文字颜色
            accent_color = "#0078d4"      # 强调色
            
            # 配置主窗口
            self.root.configure(bg=dark_bg)

            # 设置TTK样式
            style = ttk.Style()
            style.theme_use('clam')
            
            # 配置Frame样式
            style.configure("TFrame", 
                          background=dark_bg,
                          relief="flat")
            
            # 配置Label样式
            style.configure("TLabel", 
                          background=dark_bg, 
                          foreground=text_primary,
                          font=('Segoe UI', 9))
            
            # 配置Button样式
            style.configure("TButton", 
                          background=dark_surface,
                          foreground=text_primary,
                          borderwidth=1,
                          focuscolor='none',
                          font=('Segoe UI', 9))
            style.map("TButton",
                     background=[('active', dark_surface_light),
                               ('pressed', accent_color)])
            
            # 配置Entry样式
            style.configure("TEntry",
                          background=dark_surface,
                          foreground=text_primary,
                          fieldbackground=dark_surface,
                          borderwidth=1,
                          insertcolor=text_primary,
                          font=('Segoe UI', 9))
            
            # 配置Treeview样式
            style.configure("Treeview", 
                          background=dark_surface,
                          foreground=text_primary,
                          fieldbackground=dark_surface,
                          borderwidth=0,
                          font=('Segoe UI', 9))
            
            # 配置Treeview标题样式
            style.configure("Treeview.Heading", 
                          background=dark_surface_light,
                          foreground=text_primary,
                          borderwidth=1,
                          relief="flat",
                          font=('Segoe UI', 9, 'bold'))
            
            # 配置Treeview选中样式
            style.map("Treeview",
                     background=[('selected', accent_color)],
                     foreground=[('selected', text_primary)])
            
            # 配置Scrollbar样式
            style.configure("Vertical.TScrollbar",
                          background=dark_surface,
                          troughcolor=dark_bg,
                          borderwidth=0,
                          arrowcolor=text_secondary,
                          darkcolor=dark_surface,
                          lightcolor=dark_surface)
            
            style.configure("Horizontal.TScrollbar",
                          background=dark_surface,
                          troughcolor=dark_bg,
                          borderwidth=0,
                          arrowcolor=text_secondary,
                          darkcolor=dark_surface,
                          lightcolor=dark_surface)

        except Exception as e:
            print(f"主题应用失败: {e}")
            # 备用深色主题
            self.root.configure(bg="#2d2d2d")

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
    # 隐藏控制台窗口（仅在Windows上有效）
    try:
        if os.name == 'nt':  # Windows系统
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except:
        pass  # 如果隐藏失败，继续正常运行
    
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
