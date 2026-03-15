<?xml version="1.0" encoding="UTF-8"?>
<map version="1.0.1">
  <node TEXT="M2 音频可视化工具结构图">
    <node TEXT="程序结构">
      <node TEXT="启动入口">
        <node TEXT="启动脚本（启动.bat）">
          <node TEXT="检查并准备 Python 3.13"/>
          <node TEXT="修复或重建虚拟环境（venv313）"/>
          <node TEXT="安装依赖清单（requirements_audio_viz.txt）"/>
          <node TEXT="启动主控程序（0.pyw）"/>
        </node>
        <node TEXT="主控程序（0.pyw）">
          <node TEXT="配置读写"/>
          <node TEXT="主控界面"/>
          <node TEXT="预设与随机系统"/>
          <node TEXT="子进程管理"/>
        </node>
        <node TEXT="渲染子进程（1.pyw）">
          <node TEXT="系统音频回采（WASAPI）"/>
          <node TEXT="频谱分析与对数频段聚合（FFT）"/>
          <node TEXT="物理更新与曲线生成"/>
          <node TEXT="图形绘制（PyOpenGL）"/>
          <node TEXT="拖动调整浮层"/>
        </node>
        <node TEXT="当前运行配置文件（visualizer_config.json）"/>
        <node TEXT="整体预设与分段预设存储（presets / section_presets）"/>
      </node>
      <node TEXT="运行链路">
        <node TEXT="启动脚本 -> 主控程序"/>
        <node TEXT="主控程序 -> 通过多进程启动渲染子进程"/>
        <node TEXT="渲染子进程 -> 音频采集 -> 频谱分析 -> 频谱条目标值"/>
        <node TEXT="物理参数 -> 半径/高度/旋转更新"/>
        <node TEXT="OpenGL 与界面绘制层叠加输出（QPainter）"/>
      </node>
      <node TEXT="界面结构">
        <node TEXT="顶部常驻面板">
          <node TEXT="总开关、模式、K1、K2"/>
          <node TEXT="预设管理"/>
          <node TEXT="颜色预览带"/>
          <node TEXT="复位位置 / 复位参数"/>
          <node TEXT="缩放"/>
          <node TEXT="位置坐标（X / Y）"/>
          <node TEXT="拖动调整位置"/>
        </node>
        <node TEXT="右侧详情页">
          <node TEXT="控制"/>
          <node TEXT="颜色方案"/>
          <node TEXT="运动表现"/>
          <node TEXT="图元设置"/>
          <node TEXT="高级控制"/>
          <node TEXT="随机"/>
        </node>
      </node>
    </node>
    <node TEXT="控制参数结构">
      <node TEXT="基础与窗口">
        <node TEXT="窗口宽度与高度（width / height）"/>
        <node TEXT="主体透明度与界面透明度（alpha / ui_alpha）"/>
        <node TEXT="全局缩放（global_scale）"/>
        <node TEXT="窗口位置（pos_x / pos_y）"/>
        <node TEXT="拖动调整模式（drag_adjust_mode）"/>
        <node TEXT="背景透明与窗口置顶（bg_transparent / always_on_top）"/>
        <node TEXT="主控显示状态（master_visible）"/>
      </node>
      <node TEXT="频谱与音频">
        <node TEXT="频谱条数量（num_bars）"/>
        <node TEXT="平滑强度（smoothing）"/>
        <node TEXT="频率范围下限与上限（freq_min / freq_max）"/>
        <node TEXT="A1 时间窗口（a1_time_window）"/>
        <node TEXT="K2 开关与强度（k2_enabled / k2_pow）"/>
      </node>
      <node TEXT="几何与半径">
        <node TEXT="圆环半径与分段数（circle_radius / circle_segments）"/>
        <node TEXT="A1 圆环旋转与半径响应（circle_a1_rotation / circle_a1_radius）"/>
        <node TEXT="基础旋转与主半径缩放（rotation_base / main_radius_scale）"/>
        <node TEXT="半径阻尼、弹性、重力（radius_damping / radius_spring / radius_gravity）"/>
      </node>
      <node TEXT="频谱条高度与长度">
        <node TEXT="条形阻尼、弹性、重力（damping / spring_strength / gravity）"/>
        <node TEXT="频谱条默认高度（bar_default_height）"/>
        <node TEXT="内部高度下限与上限（bar_internal_min / bar_internal_max）"/>
        <node TEXT="显示高度下限与上限（bar_height_min / bar_height_max）"/>
        <node TEXT="条形长度下限与上限（bar_length_min / bar_length_max）"/>
      </node>
      <node TEXT="颜色系统">
        <node TEXT="配色方案（color_scheme）"/>
        <node TEXT="渐变开关与模式（gradient_enabled / gradient_mode）"/>
        <node TEXT="渐变控制点（gradient_points）"/>
        <node TEXT="动态颜色（color_dynamic）"/>
        <node TEXT="颜色循环速度、强度、A1 响应（color_cycle_speed / color_cycle_pow / color_cycle_a1）"/>
      </node>
      <node TEXT="五层轮廓参数（c1 至 c5）">
        <node TEXT="通用字段">
          <node TEXT="启用、颜色、透明度、粗细（on / color / alpha / thick）"/>
          <node TEXT="填充与填充透明度（fill / fill_alpha）"/>
          <node TEXT="旋转速度与旋转强度（rot_speed / rot_pow）"/>
        </node>
        <node TEXT="c1 与 c5 额外字段">
          <node TEXT="衰减（decay）"/>
        </node>
        <node TEXT="c1、c2、c4、c5 额外字段">
          <node TEXT="步进（step）"/>
        </node>
      </node>
      <node TEXT="四层条形参数（b12 至 b45）">
        <node TEXT="启用与粗细（on / thick）"/>
        <node TEXT="固定长度开关与固定长度（fixed / fixed_len）"/>
        <node TEXT="起点、终点、中心扩展方式（from_start / from_end / from_center）"/>
      </node>
      <node TEXT="预设与随机化">
        <node TEXT="随机勾选项（random_checked）"/>
        <node TEXT="随机对象数量下限与上限（random_object_count_min / random_object_count_max）"/>
        <node TEXT="预设顺序（preset_order）"/>
        <node TEXT="预设自动切换（preset_auto_switch）"/>
        <node TEXT="预设切换间隔（preset_switch_interval）"/>
        <node TEXT="预设间隔随机开关（preset_interval_random_enabled）"/>
        <node TEXT="预设切换间隔下限与上限（preset_switch_interval_min / preset_switch_interval_max）"/>
      </node>
    </node>
    <node TEXT="当前交互机制">
      <node TEXT="颜色按钮 -> 鼠标位置弹出 HSV 取色浮窗"/>
      <node TEXT="数值框右键 -> 软范围设置与恢复默认值"/>
      <node TEXT="手动输入值 -> 可突破软范围，仅滑块受软范围限制"/>
      <node TEXT="拖动调整 -> 修改可视化中心点"/>
      <node TEXT="拖动退出保护 -> 主控回写中心点，渲染端钳制到可见范围"/>
      <node TEXT="频段划分 -> 仅保留对数频率分段"/>
    </node>
  </node>
</map>