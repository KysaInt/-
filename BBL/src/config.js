(function () {
	window.AYE48 = window.AYE48 || {};
	window.AYE48.Config = {
		modelUrl: new URL("assets/models/48.glb", window.location.href).toString(),
		// 优先使用本地预过滤 .env（体积小、加载快），不存在则会在地图里自动回退到 EXR 或线上默认环境
		environmentTextureUrl: new URL("assets/env/AboveClouds_08_256_webp.env", window.location.href).toString(),
		environmentFallbackUrl: "https://playground.babylonjs.com/textures/environment.env",
		environmentExrUrl: new URL("assets/exr/AboveClouds_08_6K.exr", window.location.href).toString(),
		environmentExrPrefilterSize: 256,
		environment: {
			// auto: env→exr→fallback; env: 只用本地.env优先；exr: 强制用 exr（更慢）；fallback: 强制用线上兜底
			sourceMode: "auto",
			// 背景显示模式：skybox 使用默认 skybox；solid 使用纯色背景（不显示 skybox）
			backgroundMode: "skybox",
			backgroundColor: [0.04, 0.06, 0.1],
			backgroundAlpha: 1.0,
			// IBL 强度（影响 PBR 反射/漫反射整体亮度）
			intensity: 1.0,
			// 画面色调映射参数
			exposure: 1.05,
			contrast: 1.05,
			// 环境旋转（用于对齐主光方向）
			rotationYDeg: 0,
			// Skybox 模糊：0 更清晰，越大越糊
			skyboxBlur: 0.25,
			// 仅用于 UI 选择（需要你自己烘焙出对应的 .env 文件）
			envResolution: 256,
			// EXR 运行时预过滤尺寸（越大越清晰也越慢）
			exrPrefilterSize: 256,
		},
		ui: {
			title: "48.glb 展示",
			editor: {
				// 右侧编辑器折叠/展开状态：默认全收起
				open: {},
				// 右侧编辑器整体折叠（隐藏）
				collapsed: false,
			},
		},
		camera: {
			startPos: { x: 0, y: 1.6, z: -6 },
			pitchMin: -1.2,
			pitchMax: 1.2,
		},
		ground: {
			y: 0,
			width: 2000,
			height: 2000,
			followStep: 10,
			gridRatio: 1,
			majorUnitFrequency: 10,
			// 颜色：主线灰、子线深灰
			majorColor: [0.55, 0.55, 0.55],
			minorColor: [0.22, 0.22, 0.22],
			// 透明度：整体偏暗（可在右侧编辑器里再调）
			minorAlpha: 0.06,
			majorAlpha: 0.12,
			// 线宽（世界单位，值越大越粗）
			minorLineWidth: 0.03,
			majorLineWidth: 0.06,
			// 远端渐隐（单位：世界单位，按相机距离）
			fadeStart: 35,
			fadeEnd: 140,
		},
		movement: {
			mouseTurn: 0.008,
			wheelStep: 0.6,
			moveSpeed: 6,
			jumpVel: 5.2,
			gravity: 12.0,
		},
		prop: {
			baseHeightFactor: 2 / 3,
			rotationSpeed: 0.6,
			bobAmplitudeFactor: 0.08,
			bobFrequency: 1.0,
		},
		render: {
			preset: "balanced",
			engine: {
				// 1 = 原生分辨率；>1 更糊更省；<1 更清晰更耗
				hardwareScalingLevel: 1.0,
			},
			dynamicResolution: {
				enabled: false,
				// 目标 fps（一般会受显示器刷新率上限影响）
				targetFps: 60,
				// hardwareScalingLevel 的可调范围（越大越省、越糊）
				minScaling: 0.5,
				maxScaling: 4.0,
				step: 0.1,
				intervalMs: 250,
				hysteresis: 3,
			},
			shadow: {
				// 注意：当前场景默认没有“地面接收阴影”的面，开启阴影主要用于模型自阴影（会更耗）
				enabled: false,
				mapSize: 1024,
				blurEnabled: false,
				blurKernel: 8,
			},
			defaultPipeline: {
				enabled: true,
				fxaaEnabled: true,
				// Bloom
				bloomEnabled: false,
				bloomThreshold: 0.9,
				bloomWeight: 0.15,
				bloomKernel: 64,
				bloomScale: 0.5,
				// Sharpen
				sharpenEnabled: false,
				sharpenEdgeAmount: 0.2,
				sharpenColorAmount: 0.6,
				// Chromatic Aberration
				chromaticAberrationEnabled: false,
				chromaticAberrationAmount: 15,
				// Grain
				grainEnabled: false,
				grainIntensity: 10,
				// Depth of Field (可能依赖 WebGL2/深度纹理)
				depthOfFieldEnabled: false,
				dofFocusDistance: 200,
				dofFStop: 1.4,
				dofFocalLength: 50,
				dofLensSize: 50,
			},
			ssao2: {
				enabled: false,
				// ratio 越小越省（更糊）
				ratio: 0.5,
				radius: 2.0,
				totalStrength: 1.0,
				base: 0.5,
				area: 0.0075,
				fallOff: 0.000001,
			},
		},
	};

	// ===== 配置自动保存/自动加载（localStorage） =====
	const STORAGE_KEY = "AYE48.UIConfig.v1";
	const config = window.AYE48.Config;
	// 默认值快照：用于 UI 的“恢复默认”
	try {
		window.AYE48.DefaultConfig = JSON.parse(JSON.stringify(config));
	} catch {
		window.AYE48.DefaultConfig = null;
	}

	function isPlainObject(v) {
		return !!v && typeof v === "object" && Object.prototype.toString.call(v) === "[object Object]";
	}

	function deepMerge(target, src) {
		if (!isPlainObject(target) || !isPlainObject(src)) return target;
		for (const k of Object.keys(src)) {
			const sv = src[k];
			const tv = target[k];
			if (Array.isArray(sv)) {
				target[k] = sv.slice();
				continue;
			}
			if (isPlainObject(sv) && isPlainObject(tv)) {
				deepMerge(tv, sv);
				continue;
			}
			target[k] = sv;
		}
		return target;
	}

	function pickPersistedConfig(cfg) {
		return {
			environmentTextureUrl: cfg.environmentTextureUrl,
			environmentFallbackUrl: cfg.environmentFallbackUrl,
			environmentExrUrl: cfg.environmentExrUrl,
			environmentExrPrefilterSize: cfg.environmentExrPrefilterSize,
			environment: cfg.environment,
			ui: { editor: cfg.ui && cfg.ui.editor },
			camera: cfg.camera,
			ground: cfg.ground,
			movement: cfg.movement,
			prop: cfg.prop,
			render: cfg.render,
		};
	}

	function applyPersistedConfig() {
		try {
			const raw = window.localStorage && window.localStorage.getItem(STORAGE_KEY);
			if (!raw) return false;
			const parsed = JSON.parse(raw);
			const data = parsed && parsed.data;
			if (!data || !isPlainObject(data)) return false;
			deepMerge(config, data);
			return true;
		} catch {
			return false;
		}
	}

	let lastSaved = "";
	let saveTimer = null;

	function saveNow(reason) {
		try {
			if (!window.localStorage) return false;
			const payload = {
				v: 1,
				savedAt: Date.now(),
				reason: reason || "auto",
				data: pickPersistedConfig(config),
			};
			const json = JSON.stringify(payload);
			if (json === lastSaved) return true;
			window.localStorage.setItem(STORAGE_KEY, json);
			lastSaved = json;
			return true;
		} catch {
			return false;
		}
	}

	function markDirty(reason) {
		if (saveTimer) window.clearTimeout(saveTimer);
		saveTimer = window.setTimeout(() => {
			saveTimer = null;
			saveNow(reason || "ui");
		}, 250);
	}

	function resetPersisted() {
		try {
			if (window.localStorage) window.localStorage.removeItem(STORAGE_KEY);
			lastSaved = "";
			return true;
		} catch {
			return false;
		}
	}

	// 启动时自动加载
	applyPersistedConfig();
	// 首次保存快照（避免 lastSaved 为空导致第一次 UI 操作重复写入大对象）
	saveNow("init");
	window.addEventListener("beforeunload", () => saveNow("beforeunload"));

	// ===== 渲染性能预设（速度 / 平衡 / 质量） =====
	window.AYE48.RenderPresets = window.AYE48.RenderPresets || {};
	window.AYE48.RenderPresets.apply = function applyRenderPreset(cfg, preset) {
		const target = cfg || config;
		const mode = String(preset || "balanced");
		target.render = target.render || {};
		target.render.engine = target.render.engine || {};
		target.render.defaultPipeline = target.render.defaultPipeline || {};
		target.render.ssao2 = target.render.ssao2 || {};
		target.render.shadow = target.render.shadow || {};
		target.render.preset = mode;

		const r = target.render;
		const dp = r.defaultPipeline;
		const ssao = r.ssao2;
		const shadow = r.shadow;
		const dr = (r.dynamicResolution = r.dynamicResolution || {});

		if (mode === "speed") {
			r.engine.hardwareScalingLevel = 2.0;
			dp.enabled = false;
			dp.fxaaEnabled = true;
			dp.bloomEnabled = false;
			dp.sharpenEnabled = false;
			dp.chromaticAberrationEnabled = false;
			dp.grainEnabled = false;
			dp.depthOfFieldEnabled = false;
			ssao.enabled = false;
			shadow.enabled = false;
			dr.enabled = true;
			dr.targetFps = 60;
			dr.minScaling = 1.0;
			dr.maxScaling = 4.0;
			dr.step = 0.15;
			return;
		}

		if (mode === "quality") {
			r.engine.hardwareScalingLevel = 1.0;
			dp.enabled = true;
			dp.fxaaEnabled = true;
			dp.sharpenEnabled = true;
			dp.sharpenEdgeAmount = 0.18;
			dp.sharpenColorAmount = 0.55;
			dp.bloomEnabled = false;
			dp.chromaticAberrationEnabled = false;
			dp.grainEnabled = false;
			dp.depthOfFieldEnabled = false;
			ssao.enabled = false;
			shadow.enabled = true;
			shadow.mapSize = 1024;
			shadow.blurEnabled = false;
			shadow.blurKernel = 8;
			dr.enabled = false;
			return;
		}

		// balanced
		r.engine.hardwareScalingLevel = 1.4;
		dp.enabled = true;
		dp.fxaaEnabled = true;
		dp.bloomEnabled = false;
		dp.sharpenEnabled = true;
		dp.sharpenEdgeAmount = 0.12;
		dp.sharpenColorAmount = 0.35;
		dp.chromaticAberrationEnabled = false;
		dp.grainEnabled = false;
		dp.depthOfFieldEnabled = false;
		ssao.enabled = false;
		shadow.enabled = false;
		dr.enabled = false;
	};

	window.AYE48.ConfigStore = {
		storageKey: STORAGE_KEY,
		markDirty,
		saveNow,
		reset: resetPersisted,
	};
})();
