from manim import *
import numpy as np

class ComplexManimExample(Scene):
    """
    复杂的Manim示例，包含多种动画效果
    """
    
    def construct(self):
        # 1. 创建标题和介绍
        self.create_title()
        
        # 2. 数学函数可视化
        self.show_function_graph()
        
        # 3. 几何变换演示
        self.geometric_transformations()
        
        # 4. 矩阵运算可视化
        self.matrix_operations()
        
        # 5. 微积分概念演示
        self.calculus_demo()
        
        # 6. 结束动画
        self.ending_animation()
    
    def create_title(self):
        """创建标题和介绍"""
        title = Text("复杂数学概念可视化", font_size=48, color=BLUE)
        subtitle = Text("使用 Manim 制作", font_size=24, color=GRAY)
        subtitle.next_to(title, DOWN)
        
        self.play(
            Write(title),
            FadeIn(subtitle, shift=UP)
        )
        self.wait(2)
        
        # 标题移动到顶部
        title_group = VGroup(title, subtitle)
        self.play(
            title_group.animate.scale(0.6).to_edge(UP),
            run_time=1.5
        )
        self.wait(0.5)
    
    def show_function_graph(self):
        """显示函数图像和动画"""
        # 创建坐标轴
        axes = Axes(
            x_range=[-4, 4, 1],
            y_range=[-3, 3, 1],
            x_length=8,
            y_length=6,
            axis_config={"color": WHITE}
        )
        
        # 添加标签
        x_label = axes.get_x_axis_label("x")
        y_label = axes.get_y_axis_label("y")
        
        # 创建函数
        def func1(x):
            return np.sin(x) * np.exp(-x/4)
        
        def func2(x):
            return np.cos(x) * np.exp(-x/4)
        
        # 创建函数图像
        graph1 = axes.plot(func1, color=RED, x_range=[-4, 4])
        graph2 = axes.plot(func2, color=BLUE, x_range=[-4, 4])
        
        # 函数标签
        func1_label = MathTex(r"f(x) = \sin(x) \cdot e^{-x/4}", color=RED)
        func2_label = MathTex(r"g(x) = \cos(x) \cdot e^{-x/4}", color=BLUE)
        
        func1_label.to_edge(RIGHT + UP)
        func2_label.next_to(func1_label, DOWN)
        
        # 动画展示
        self.play(Create(axes))
        self.play(Write(x_label), Write(y_label))
        
        self.play(
            Create(graph1),
            Write(func1_label),
            run_time=2
        )
        
        self.play(
            Create(graph2),
            Write(func2_label),
            run_time=2
        )
        
        # 创建移动的点
        dot1 = Dot(color=RED)
        dot2 = Dot(color=BLUE)
        
        # 点沿着曲线移动
        self.play(
            MoveAlongPath(dot1, graph1),
            MoveAlongPath(dot2, graph2),
            run_time=4,
            rate_func=linear
        )
        
        self.wait(1)
        
        # 清除场景
        self.play(
            FadeOut(VGroup(axes, x_label, y_label, graph1, graph2, 
                          func1_label, func2_label, dot1, dot2))
        )
    
    def geometric_transformations(self):
        """几何变换演示"""
        # 创建初始形状
        square = Square(side_length=2, color=YELLOW, fill_opacity=0.7)
        triangle = Triangle(color=GREEN, fill_opacity=0.7)
        circle = Circle(radius=1, color=PURPLE, fill_opacity=0.7)
        
        # 排列形状
        shapes = VGroup(square, triangle, circle)
        shapes.arrange(RIGHT, buff=1)
        
        # 标题
        transform_title = Text("几何变换", font_size=36, color=WHITE)
        transform_title.to_edge(UP, buff=1)
        
        self.play(
            Write(transform_title),
            FadeIn(shapes, shift=UP)
        )
        self.wait(1)
        
        # 旋转变换
        self.play(
            Rotate(square, PI/2),
            Rotate(triangle, PI/3),
            Rotate(circle, PI/4),
            run_time=2
        )
        
        # 缩放变换
        self.play(
            square.animate.scale(1.5),
            triangle.animate.scale(0.7),
            circle.animate.scale(1.3),
            run_time=2
        )
        
        # 扭曲变换
        self.play(
            ApplyFunction(
                lambda p: np.array([
                    p[0] + 0.3 * np.sin(p[1]),
                    p[1] + 0.3 * np.cos(p[0]),
                    p[2]
                ]),
                square
            ),
            run_time=3
        )
        
        # 颜色变换
        self.play(
            triangle.animate.set_color(RED),
            circle.animate.set_color(ORANGE),
            run_time=1.5
        )
        
        self.wait(1)
        
        # 清除场景
        self.play(FadeOut(VGroup(transform_title, shapes)))
    
    def matrix_operations(self):
        """矩阵运算可视化"""
        # 创建矩阵
        matrix_a = Matrix([
            ["1", "2"],
            ["3", "4"]
        ], bracket_h_buff=0.1, bracket_v_buff=0.1)
        
        matrix_b = Matrix([
            ["5", "6"],
            ["7", "8"]
        ], bracket_h_buff=0.1, bracket_v_buff=0.1)
        
        # 创建标题
        matrix_title = Text("矩阵乘法", font_size=36, color=WHITE)
        matrix_title.to_edge(UP, buff=1)
        
        # 乘号
        times_sign = MathTex(r"\times")
        equals_sign = MathTex("=")
        
        # 结果矩阵
        result_matrix = Matrix([
            ["19", "22"],
            ["43", "50"]
        ], bracket_h_buff=0.1, bracket_v_buff=0.1)
        
        # 排列矩阵
        matrix_group = VGroup(matrix_a, times_sign, matrix_b, equals_sign, result_matrix)
        matrix_group.arrange(RIGHT, buff=0.5)
        matrix_group.move_to(ORIGIN)
        
        # 动画展示
        self.play(Write(matrix_title))
        self.wait(0.5)
        
        self.play(Write(matrix_a))
        self.wait(0.5)
        
        self.play(Write(times_sign))
        self.wait(0.5)
        
        self.play(Write(matrix_b))
        self.wait(1)
        
        # 突出显示计算过程
        highlight_color = YELLOW
        
        # 第一行第一列的计算
        self.play(
            matrix_a.get_rows()[0].animate.set_color(highlight_color),
            matrix_b.get_columns()[0].animate.set_color(highlight_color)
        )
        self.wait(1)
        
        self.play(Write(equals_sign))
        
        # 显示结果的第一个元素
        self.play(Write(result_matrix.get_entries()[0]))
        
        # 重置颜色
        self.play(
            matrix_a.get_rows()[0].animate.set_color(WHITE),
            matrix_b.get_columns()[0].animate.set_color(WHITE)
        )
        
        # 快速显示其余元素
        self.play(Write(VGroup(*result_matrix.get_entries()[1:])))
        
        self.wait(2)
        
        # 清除场景
        self.play(FadeOut(VGroup(matrix_title, matrix_group)))
    
    def calculus_demo(self):
        """微积分概念演示"""
        # 创建坐标轴
        axes = Axes(
            x_range=[0, 4, 1],
            y_range=[0, 16, 4],
            x_length=6,
            y_length=4,
            axis_config={"color": WHITE}
        )
        
        # 定义函数
        def quadratic(x):
            return x**2
        
        # 创建函数图像
        curve = axes.plot(quadratic, color=BLUE, x_range=[0, 4])
        
        # 标题
        calculus_title = Text("积分可视化", font_size=36, color=WHITE)
        calculus_title.to_edge(UP, buff=1)
        
        # 函数标签
        function_label = MathTex(r"f(x) = x^2", color=BLUE)
        function_label.next_to(axes, RIGHT, buff=0.5)
        
        self.play(Write(calculus_title))
        self.play(Create(axes), Write(function_label))
        self.play(Create(curve))
        
        # 创建黎曼和
        x_min, x_max = 1, 3
        n_rectangles = 8
        
        rectangles = axes.get_riemann_rectangles(
            curve,
            x_range=[x_min, x_max],
            dx=(x_max - x_min) / n_rectangles,
            color=YELLOW,
            fill_opacity=0.6,
            stroke_width=0.5
        )
        
        # 积分标签
        integral_label = MathTex(
            r"\int_1^3 x^2 \, dx = \frac{26}{3}",
            color=YELLOW
        )
        integral_label.next_to(function_label, DOWN)
        
        self.play(Create(rectangles))
        self.play(Write(integral_label))
        
        # 增加矩形数量以近似积分
        for n in [16, 32, 64]:
            new_rectangles = axes.get_riemann_rectangles(
                curve,
                x_range=[x_min, x_max],
                dx=(x_max - x_min) / n,
                color=YELLOW,
                fill_opacity=0.6,
                stroke_width=0.5
            )
            
            self.play(
                Transform(rectangles, new_rectangles),
                run_time=1.5
            )
            self.wait(0.5)
        
        # 显示精确的积分区域
        area = axes.get_area(curve, x_range=[x_min, x_max], color=GREEN, opacity=0.8)
        self.play(
            FadeOut(rectangles),
            FadeIn(area)
        )
        
        self.wait(2)
        
        # 清除场景
        self.play(FadeOut(VGroup(calculus_title, axes, curve, function_label, 
                                integral_label, area)))
    
    def ending_animation(self):
        """结束动画"""
        # 创建结束文本
        ending_text = Text("感谢观看！", font_size=48, color=GOLD)
        
        # 创建粒子效果
        particles = VGroup(*[
            Dot(
                point=np.random.uniform(-7, 7, 3) * np.array([1, 1, 0]),
                color=random_color(),
                radius=0.05
            )
            for _ in range(50)
        ])
        
        self.play(Write(ending_text))
        
        # 粒子动画
        for particle in particles:
            self.add(particle)
            self.play(
                particle.animate.shift(UP * np.random.uniform(1, 3)),
                particle.animate.set_opacity(0),
                run_time=np.random.uniform(1, 3),
                rate_func=ease_out_cubic
            )
        
        self.play(
            ending_text.animate.scale(1.2).set_color(WHITE),
            run_time=2
        )
        
        self.wait(3)


class FourierSeriesDemo(Scene):
    """傅里叶级数演示"""
    
    def construct(self):
        title = Text("傅里叶级数", font_size=36)
        title.to_edge(UP)
        self.play(Write(title))
        
        # 创建坐标轴
        axes = Axes(
            x_range=[-2*PI, 2*PI, PI/2],
            y_range=[-2, 2, 1],
            x_length=10,
            y_length=4
        )
        
        self.play(Create(axes))
        
        # 目标函数（方波）
        def square_wave(x):
            return np.sign(np.sin(x))
        
        # 傅里叶级数近似
        def fourier_approximation(x, n_terms):
            result = np.zeros_like(x)
            for k in range(1, 2*n_terms, 2):
                result += (4/PI) * np.sin(k*x) / k
            return result
        
        # 创建目标函数图像
        target = axes.plot(square_wave, color=RED, discontinuities=[PI, -PI, 0])
        
        # 创建近似图像
        approx = axes.plot(
            lambda x: fourier_approximation(x, 1),
            color=BLUE
        )
        
        self.play(Create(target), Create(approx))
        
        # 逐步增加项数
        for n in range(2, 20):
            new_approx = axes.plot(
                lambda x: fourier_approximation(x, n),
                color=BLUE
            )
            self.play(Transform(approx, new_approx), run_time=0.3)
        
        self.wait(3)


if __name__ == "__main__":
    # 运行示例
    # 使用命令: manim -pql a.py ComplexManimExample
    # 或者: manim -pql a.py FourierSeriesDemo
    pass