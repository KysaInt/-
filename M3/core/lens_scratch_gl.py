"""
镜头划痕/眩光后处理效果 — OpenGL GLSL 实现
移植自 Unity HDRP AyeLensScratchCameraEffect.shader

依赖：PyOpenGL, numpy
可选：Pillow（用于加载自定义划痕贴图）

用法：
    gl = LensScratchGL()
    # 在 QOpenGLWidget.initializeGL() 内：
    gl.initialize()
    # 在 QOpenGLWidget.resizeGL() 内：
    gl.resize(fb_width, fb_height)
    # 在 paintGL() 末尾（已有独立 scene FBO 时）：
    gl.apply(scene_texture_id, params_dict)
"""

from __future__ import annotations
import math
import ctypes
from pathlib import Path

import numpy as np
from OpenGL import GL

# ---------------------------------------------------------------------------
# GLSL 源码
# ---------------------------------------------------------------------------

_VERT_SRC = """
#version 330 core
out vec2 vTexCoord;

void main() {
    // 全屏三角形 (vertexID=0,1,2 → NDC覆盖整个屏幕)
    vec2 pos[3] = vec2[](vec2(-1.0,-1.0), vec2(3.0,-1.0), vec2(-1.0,3.0));
    vec2 uvs[3] = vec2[](vec2(0.0,0.0),  vec2(2.0,0.0),  vec2(0.0,2.0));
    gl_Position = vec4(pos[gl_VertexID], 0.0, 1.0);
    vTexCoord   = uvs[gl_VertexID];
}
"""

_FRAG_SRC = """
#version 330 core
in vec2 vTexCoord;
out vec4 fragColor;

uniform sampler2D uScene;        // 场景颜色纹理（带 mipmap）
uniform sampler2D uScratchMask;  // 划痕遮罩（r 通道）
uniform sampler2D uScratchNormal;// 划痕法线贴图（rgb 编码）
uniform vec2  uResolution;
uniform vec4  uScratchMask_ST;   // tiling_x, tiling_y, offset_x, offset_y

uniform float uScratchRotation;          // 弧度
uniform float uScratchMaskPower;
uniform float uNormalInfluence;
uniform float uThreshold;
uniform float uSoftKnee;
uniform float uGlareIntensity;
uniform float uStreakLength;
uniform int   uCountA;
uniform float uStreakSpread;
uniform float uFalloffA;
uniform float uFalloffB;
uniform int   uScratchCount;
uniform int   uStreakCount;
uniform float uScratchGroupRotationJitter;
uniform float uRefractionStrength;
uniform float uChromaticAberration;
uniform float uMicroDistortion;
uniform vec4  uGlareTint;
uniform float uMipLevels;   // 场景纹理的 mip 层数（供 LOD 采样）

// ── 工具函数 ────────────────────────────────────────────────────────────────

float hash11(float v) {
    return fract(sin(v * 127.1) * 43758.5453123);
}

vec2 rotateAroundCenter(vec2 uv, float r) {
    float s = sin(r), c = cos(r);
    vec2 d = uv - 0.5;
    return vec2(d.x*c - d.y*s, d.x*s + d.y*c) + 0.5;
}

vec2 rotateDir(vec2 d, float r) {
    float s = sin(r), c = cos(r);
    return vec2(d.x*c - d.y*s, d.x*s + d.y*c);
}

// ── 采样 ────────────────────────────────────────────────────────────────────

float sampleMask(vec2 uv) {
    uv = rotateAroundCenter(uv, uScratchRotation);
    vec2 suv = uv * uScratchMask_ST.xy + uScratchMask_ST.zw;
    float m = texture(uScratchMask, suv).r;
    return pow(clamp(m, 0.0, 1.0), max(uScratchMaskPower, 0.0001));
}

vec3 sampleNormalTS(vec2 uv) {
    uv = rotateAroundCenter(uv, uScratchRotation);
    vec2 suv = uv * uScratchMask_ST.xy + uScratchMask_ST.zw;
    vec3 enc = texture(uScratchNormal, suv).xyz;
    return normalize(enc * 2.0 - 1.0);
}

// 高光提取（模拟 Unity knee 曲线）
vec3 prefilterBright(vec3 color) {
    float brightness = max(color.r, max(color.g, color.b));
    float knee = max(uSoftKnee, 1e-4);
    float soft = clamp((brightness - uThreshold + knee) / (2.0 * knee), 0.0, 1.0);
    soft = soft * soft * knee;
    float contrib = max(soft, brightness - uThreshold);
    return (brightness > 1e-4) ? color * (contrib / brightness) : vec3(0.0);
}

// 带色差的高光采样
vec3 sampleChromatic(vec2 uv, vec2 dir, vec2 refOff, float lod) {
    vec2 texel = 1.0 / max(uResolution, vec2(1.0));
    vec2 chromaOff = dir * (uChromaticAberration * 48.0) * texel;
    float mipLvl = clamp(lod * uMipLevels, 0.0, uMipLevels);
    vec3 sr = textureLod(uScene, uv + refOff + chromaOff, mipLvl).rgb;
    vec3 sg = textureLod(uScene, uv + refOff,             mipLvl).rgb;
    vec3 sb = textureLod(uScene, uv + refOff - chromaOff, mipLvl).rgb;
    return prefilterBright(vec3(sr.r, sg.g, sb.b));
}

// ── 主片元 ──────────────────────────────────────────────────────────────────

void main() {
    vec2 uv   = vTexCoord;
    float mask = sampleMask(uv);
    vec3 normalTS = sampleNormalTS(uv);
    vec2 texel = 1.0 / max(uResolution, vec2(1.0));

    // 划痕方向（沿法线方向偏转）
    float sc = cos(uScratchRotation), ss = sin(uScratchRotation);
    vec2 baseDir = vec2(sc, ss);
    vec2 localPerturb = vec2(normalTS.y, -normalTS.x) * (uNormalInfluence * 0.35);
    vec2 scratchDir = baseDir + localPerturb * clamp(mask, 0.0, 1.0);
    if (dot(scratchDir, scratchDir) < 1e-5) scratchDir = baseDir;
    scratchDir.x *= uResolution.x / max(uResolution.y, 1.0);
    scratchDir = normalize(scratchDir) * max(mask, 0.05);

    // 折射偏移
    vec2 refOff = normalTS.xy * (uRefractionStrength * 28.0) * texel
                  * clamp(mask * uMicroDistortion + 0.05, 0.0, 1.0);

    vec3 baseColor = texture(uScene, uv + refOff).rgb;

    if (mask <= 0.001) {
        fragColor = vec4(baseColor, 1.0);
        return;
    }

    vec3  glareAccum  = vec3(0.0);
    float totalWeight = 0.0;

    int scratchLayerCount = clamp(uScratchCount, 1, 32);
    int streakLayerCount  = clamp(uStreakCount,  1, 32);
    int countA    = clamp(uCountA, 2, 128);
    int halfCountA = max(1, (countA + 1) / 2);

    for (int sl = 0; sl < 32; sl++) {
        if (sl >= scratchLayerCount) break;

        float layer01       = (scratchLayerCount <= 1) ? 0.0
                              : float(sl) / float(max(scratchLayerCount - 1, 1));
        float centeredLayer = layer01 - 0.5;
        float rand01        = hash11(float(sl + 1) * 17.0);
        float signedRand    = rand01 * 2.0 - 1.0;
        float angleOff      = centeredLayer  * uScratchGroupRotationJitter
                            + signedRand     * uScratchGroupRotationJitter;
        float lenScale      = 1.0 + abs(centeredLayer) * 0.65;
        float intScale      = exp2(-abs(centeredLayer) * uFalloffB);
        vec2 layerDir  = rotateDir(scratchDir, angleOff);
        vec2 layerPerp = normalize(vec2(-layerDir.y, layerDir.x));

        for (int stl = 0; stl < 32; stl++) {
            if (stl >= streakLayerCount) break;

            float streak01       = (streakLayerCount <= 1) ? 0.0
                                   : float(stl) / float(max(streakLayerCount - 1, 1));
            float centeredStreak = streak01 - 0.5;
            vec2  streakOff      = layerPerp * centeredStreak * (uStreakSpread * 24.0) * texel;
            float streakWScale   = exp2(-abs(centeredStreak) * uFalloffB);
            vec2  streakStep     = layerDir * (uStreakLength * lenScale * 18.0) * texel;

            for (int si = -64; si <= 64; si++) {
                if (si == 0) continue;
                if (abs(si) > halfCountA) continue;

                float t      = float(si) / float(max(halfCountA, 1));
                float weight = exp2(-abs(t) * uFalloffA);
                vec2  sUv    = uv + streakOff + streakStep * t;
                float sMask  = sampleMask(sUv);
                float sMix   = clamp(mix(mask, sMask, 0.75), 0.0, 1.0)
                               * intScale * streakWScale;
                vec2  sRef   = refOff * sMix;
                float lod    = clamp(abs(t) * 1.5, 0.0, 1.0);
                vec3  bright = sampleChromatic(sUv, layerDir, sRef, lod);
                glareAccum  += bright * weight * sMix;
                totalWeight += weight * sMix;
            }
        }
    }

    vec3 glare = (totalWeight > 1e-5) ? glareAccum / totalWeight : vec3(0.0);
    glare *= uGlareTint.rgb * uGlareIntensity * clamp(mask * 1.5, 0.0, 1.0);

    fragColor = vec4(baseColor + glare, 1.0);
}
"""


# ---------------------------------------------------------------------------
# 辅助：编译着色器
# ---------------------------------------------------------------------------

def _compile_shader(src: str, shader_type: int) -> int:
    sh = GL.glCreateShader(shader_type)
    GL.glShaderSource(sh, src)
    GL.glCompileShader(sh)
    ok = GL.glGetShaderiv(sh, GL.GL_COMPILE_STATUS)
    if not ok:
        log = GL.glGetShaderInfoLog(sh).decode(errors='replace')
        GL.glDeleteShader(sh)
        raise RuntimeError(f"Shader compile error:\n{log}")
    return sh


def _link_program(vert_sh: int, frag_sh: int) -> int:
    prog = GL.glCreateProgram()
    GL.glAttachShader(prog, vert_sh)
    GL.glAttachShader(prog, frag_sh)
    GL.glLinkProgram(prog)
    ok = GL.glGetProgramiv(prog, GL.GL_LINK_STATUS)
    if not ok:
        log = GL.glGetProgramInfoLog(prog).decode(errors='replace')
        GL.glDeleteProgram(prog)
        raise RuntimeError(f"Program link error:\n{log}")
    GL.glDetachShader(prog, vert_sh)
    GL.glDetachShader(prog, frag_sh)
    GL.glDeleteShader(vert_sh)
    GL.glDeleteShader(frag_sh)
    return prog


def _upload_rgba8(data_rgba: np.ndarray, wrap=GL.GL_REPEAT, gen_mips=False) -> int:
    """将 (H, W, 4) uint8 数组上传为 OpenGL 纹理，返回 texture id。"""
    tex = GL.glGenTextures(1)
    GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
    h, w = data_rgba.shape[:2]
    GL.glTexImage2D(
        GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, w, h, 0,
        GL.GL_RGBA, GL.GL_UNSIGNED_BYTE,
        data_rgba.astype(np.uint8).tobytes(),
    )
    if gen_mips:
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
    else:
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, wrap)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, wrap)
    GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
    return int(tex)


def _gen_procedural_scratch_mask(width: int = 256, height: int = 256,
                                  num_scratches: int = 12, seed: int = 42) -> np.ndarray:
    """生成程序化划痕遮罩（适合用作默认贴图）。"""
    rng = np.random.default_rng(seed)
    img = np.zeros((height, width), dtype=np.float32)

    for _ in range(num_scratches):
        cx = rng.uniform(0.0, 1.0)
        cy = rng.uniform(0.0, 1.0)
        angle = rng.uniform(0.0, math.pi)
        length = rng.uniform(0.15, 0.55)
        width_px = rng.uniform(0.3, 1.5)
        intensity = rng.uniform(0.5, 1.0)

        dx = math.cos(angle) * length
        dy = math.sin(angle) * length

        steps = max(2, int(length * max(width, height)))
        for step in range(steps + 1):
            t = step / max(steps, 1)
            px = int((cx + (t - 0.5) * dx) * width)  % width
            py = int((cy + (t - 0.5) * dy) * height) % height
            r = max(1, int(width_px))
            for yy in range(max(0, py - r), min(height, py + r + 1)):
                for xx in range(max(0, px - r), min(width, px + r + 1)):
                    dist = math.sqrt((xx - px) ** 2 + (yy - py) ** 2)
                    falloff = max(0.0, 1.0 - dist / (width_px + 0.5))
                    img[yy, xx] = min(1.0, img[yy, xx] + intensity * falloff)

    img = np.clip(img, 0.0, 1.0)
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    v = (img * 255).astype(np.uint8)
    rgba[..., 0] = v
    rgba[..., 1] = v
    rgba[..., 2] = v
    rgba[..., 3] = 255
    return rgba


def _gen_flat_normal_map(width: int = 4, height: int = 4) -> np.ndarray:
    """生成纯平法线贴图 (0.5, 0.5, 1.0 → 指向 Z+)。"""
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[..., 0] = 128
    rgba[..., 1] = 128
    rgba[..., 2] = 255
    rgba[..., 3] = 255
    return rgba


# ---------------------------------------------------------------------------
# 主类
# ---------------------------------------------------------------------------

class LensScratchGL:
    """
    镜头划痕眩光后处理效果管理器。

    必须在 OpenGL 上下文存在时调用 initialize()。
    """

    def __init__(self):
        self.ready = False
        self._prog: int = 0
        self._vao: int = 0
        self._default_mask_tex: int = 0
        self._default_normal_tex: int = 0
        self._user_mask_tex: int = 0
        self._user_normal_tex: int = 0
        self._mask_path: str = ''
        self._normal_path: str = ''
        self._uniform_cache: dict[str, int] = {}

    # ── 初始化 ──────────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """在 QOpenGLWidget.initializeGL() 内调用。"""
        try:
            v_sh = _compile_shader(_VERT_SRC, GL.GL_VERTEX_SHADER)
            f_sh = _compile_shader(_FRAG_SRC, GL.GL_FRAGMENT_SHADER)
            self._prog = _link_program(v_sh, f_sh)

            # 全屏三角形 VAO（不需要顶点缓冲，gl_VertexID 驱动）
            self._vao = int(GL.glGenVertexArrays(1))

            # 默认纹理
            mask_data = _gen_procedural_scratch_mask()
            self._default_mask_tex = _upload_rgba8(mask_data, wrap=GL.GL_REPEAT)

            normal_data = _gen_flat_normal_map()
            self._default_normal_tex = _upload_rgba8(normal_data, wrap=GL.GL_REPEAT)

            self.ready = True
            print("[LensScratchGL] 初始化成功")
        except Exception as exc:
            print(f"[LensScratchGL] 初始化失败: {exc}")
            self.ready = False

    def cleanup(self) -> None:
        """释放 OpenGL 资源（在 GL 上下文有效时调用）。"""
        if self._prog:
            GL.glDeleteProgram(self._prog)
            self._prog = 0
        if self._vao:
            GL.glDeleteVertexArrays(1, [self._vao])
            self._vao = 0
        for attr in ('_default_mask_tex', '_default_normal_tex',
                     '_user_mask_tex', '_user_normal_tex'):
            tex = getattr(self, attr, 0)
            if tex:
                GL.glDeleteTextures(1, [tex])
                setattr(self, attr, 0)
        self.ready = False

    # ── 贴图加载 ────────────────────────────────────────────────────────────

    def load_mask(self, path: str) -> bool:
        """加载划痕遮罩贴图。支持任何 Pillow 可读格式。"""
        if not path or path == self._mask_path:
            return bool(self._user_mask_tex)
        tex = self._load_image_texture(path)
        if tex:
            if self._user_mask_tex:
                GL.glDeleteTextures(1, [self._user_mask_tex])
            self._user_mask_tex = tex
            self._mask_path = path
            return True
        return False

    def load_normal(self, path: str) -> bool:
        """加载划痕法线贴图。"""
        if not path or path == self._normal_path:
            return bool(self._user_normal_tex)
        tex = self._load_image_texture(path)
        if tex:
            if self._user_normal_tex:
                GL.glDeleteTextures(1, [self._user_normal_tex])
            self._user_normal_tex = tex
            self._normal_path = path
            return True
        return False

    def _load_image_texture(self, path: str) -> int:
        """使用 Pillow 加载图像并上传到 GPU。"""
        try:
            from PIL import Image
            img = Image.open(path).convert('RGBA')
            data = np.array(img, dtype=np.uint8)
            # Pillow 坐标原点在左上，OpenGL 在左下，翻转 Y
            data = np.flipud(data)
            return _upload_rgba8(data, wrap=GL.GL_REPEAT)
        except ImportError:
            print("[LensScratchGL] Pillow 未安装，无法加载贴图。pip install Pillow")
        except Exception as exc:
            print(f"[LensScratchGL] 贴图加载失败 {path}: {exc}")
        return 0

    # ── 应用效果 ────────────────────────────────────────────────────────────

    def apply(self, scene_tex_id: int, params: dict) -> None:
        """
        将镜头划痕效果叠加到 scene_tex_id 上，输出到当前绑定的 FBO。

        params 键（均有默认值）：
            width, height               - 渲染分辨率（像素）
            scratch_rotation_deg        - 划痕旋转角度（度）
            scratch_tiling_x/y          - 贴图平铺
            scratch_offset_x/y          - 贴图偏移
            scratch_mask_power          - 遮罩幂次
            normal_influence            - 法线影响
            threshold                   - 高光阈值
            soft_knee                   - 过渡柔和
            glare_intensity             - 眩光强度
            streak_length               - 条纹长度
            count_a                     - 采样密度
            streak_spread               - 条纹扩散
            falloff_a                   - 衰减 A
            falloff_b                   - 衰减 B
            scratch_count               - 划痕层数
            streak_count                - 条纹层数
            rotation_jitter_deg         - 随机角度抖动（度）
            refraction_strength         - 折射强度
            chromatic_aberration        - 色差
            micro_distortion            - 微扰动
            tint_r/g/b                  - 眩光颜色（0-255）
            mip_levels                  - 场景纹理 mip 层数
        """
        if not self.ready:
            return

        w = float(params.get('width', 1920))
        h = float(params.get('height', 1080))
        rot_rad = math.radians(float(params.get('scratch_rotation_deg', 0.0)))
        tiling_x = float(params.get('scratch_tiling_x', 1.0))
        tiling_y = float(params.get('scratch_tiling_y', 1.0))
        offset_x = float(params.get('scratch_offset_x', 0.0))
        offset_y = float(params.get('scratch_offset_y', 0.0))
        mask_power = float(params.get('scratch_mask_power', 1.35))
        normal_inf = float(params.get('normal_influence', 1.2))
        threshold  = float(params.get('threshold', 1.1))
        soft_knee  = float(params.get('soft_knee', 0.45))
        glare_int  = float(params.get('glare_intensity', 1.15))
        streak_len = float(params.get('streak_length', 3.6))
        count_a    = int(params.get('count_a', 20))
        streak_spr = float(params.get('streak_spread', 1.1))
        falloff_a  = float(params.get('falloff_a', 3.8))
        falloff_b  = float(params.get('falloff_b', 0.35))
        scratch_cnt= int(params.get('scratch_count', 3))
        streak_cnt = int(params.get('streak_count', 3))
        jitter_rad = math.radians(float(params.get('rotation_jitter_deg', 6.0)))
        refrac     = float(params.get('refraction_strength', 0.18))
        chroma     = float(params.get('chromatic_aberration', 0.0025))
        micro_dist = float(params.get('micro_distortion', 0.55))
        tint_r     = float(params.get('tint_r', 255)) / 255.0
        tint_g     = float(params.get('tint_g', 255)) / 255.0
        tint_b     = float(params.get('tint_b', 255)) / 255.0
        mip_lvls   = float(params.get('mip_levels', 4.0))

        mask_tex   = self._user_mask_tex or self._default_mask_tex
        normal_tex = self._user_normal_tex or self._default_normal_tex

        prev_blend   = GL.glIsEnabled(GL.GL_BLEND)
        prev_depth   = GL.glIsEnabled(GL.GL_DEPTH_TEST)

        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_BLEND)

        GL.glUseProgram(self._prog)

        def _loc(name: str) -> int:
            if name not in self._uniform_cache:
                self._uniform_cache[name] = GL.glGetUniformLocation(self._prog, name)
            return self._uniform_cache[name]

        GL.glUniform2f(_loc('uResolution'), w, h)
        GL.glUniform4f(_loc('uScratchMask_ST'), tiling_x, tiling_y, offset_x, offset_y)
        GL.glUniform1f(_loc('uScratchRotation'), rot_rad)
        GL.glUniform1f(_loc('uScratchMaskPower'), mask_power)
        GL.glUniform1f(_loc('uNormalInfluence'), normal_inf)
        GL.glUniform1f(_loc('uThreshold'), threshold)
        GL.glUniform1f(_loc('uSoftKnee'), soft_knee)
        GL.glUniform1f(_loc('uGlareIntensity'), glare_int)
        GL.glUniform1f(_loc('uStreakLength'), streak_len)
        GL.glUniform1i(_loc('uCountA'), count_a)
        GL.glUniform1f(_loc('uStreakSpread'), streak_spr)
        GL.glUniform1f(_loc('uFalloffA'), falloff_a)
        GL.glUniform1f(_loc('uFalloffB'), falloff_b)
        GL.glUniform1i(_loc('uScratchCount'), scratch_cnt)
        GL.glUniform1i(_loc('uStreakCount'), streak_cnt)
        GL.glUniform1f(_loc('uScratchGroupRotationJitter'), jitter_rad)
        GL.glUniform1f(_loc('uRefractionStrength'), refrac)
        GL.glUniform1f(_loc('uChromaticAberration'), chroma)
        GL.glUniform1f(_loc('uMicroDistortion'), micro_dist)
        GL.glUniform4f(_loc('uGlareTint'), tint_r, tint_g, tint_b, 1.0)
        GL.glUniform1f(_loc('uMipLevels'), mip_lvls)

        # 纹理单元 0 = 场景, 1 = 遮罩, 2 = 法线
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, scene_tex_id)
        GL.glUniform1i(_loc('uScene'), 0)

        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, mask_tex)
        GL.glUniform1i(_loc('uScratchMask'), 1)

        GL.glActiveTexture(GL.GL_TEXTURE2)
        GL.glBindTexture(GL.GL_TEXTURE_2D, normal_tex)
        GL.glUniform1i(_loc('uScratchNormal'), 2)

        GL.glBindVertexArray(self._vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        GL.glBindVertexArray(0)

        # 还原状态
        GL.glUseProgram(0)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        if prev_blend:
            GL.glEnable(GL.GL_BLEND)
        if prev_depth:
            GL.glEnable(GL.GL_DEPTH_TEST)
