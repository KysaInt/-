(function () {
	window.AYE48 = window.AYE48 || {};
	window.AYE48.Maps = window.AYE48.Maps || {};

	async function createShowcaseMap(engine, canvas, hud, config) {
		const scene = new BABYLON.Scene(engine);
		scene.clearColor = new BABYLON.Color4(0.04, 0.06, 0.1, 1);

		// 自然天空环境光（IBL + Skybox）
		let envLocalUrl = (config && config.environmentTextureUrl) || null;
		const envFallbackUrl =
			(config && config.environmentFallbackUrl) || "https://playground.babylonjs.com/textures/environment.env";
		let exrUrl = (config && config.environmentExrUrl) || null;
		let exrPrefilterSize =
			(config && config.environment && config.environment.exrPrefilterSize) ||
			(config && config.environmentExrPrefilterSize) ||
			256;

		function isSameOrigin(url) {
			try {
				const u = new URL(url, window.location.href);
				return u.origin === window.location.origin;
			} catch {
				return true;
			}
		}

		async function urlExists(url) {
			if (!url) return false;
			if (!isSameOrigin(url)) return true; // 跨域不做探测，交给 Babylon 自己加载
			try {
				const head = await fetch(url, { method: "HEAD", cache: "no-store" });
				if (head.ok) return true;
				if (head.status !== 405) return false;
			} catch {
				// ignore
			}
			try {
				const get = await fetch(url, {
					method: "GET",
					headers: { Range: "bytes=0-0" },
					cache: "no-store",
				});
				return get.ok || get.status === 206;
			} catch {
				return false;
			}
		}

		let skyboxMesh = null;
		let envTexture = null;
		let lastSkyboxBlur = null;
		let lastRotationDeg = null;
		let lastIntensity = null;
		let lastExposure = null;
		let lastContrast = null;
		let lastLoadKey = "";
		let loadToken = 0;
		let isLoading = false;

		function disposeSkybox() {
			try {
				skyboxMesh && skyboxMesh.dispose();
			} catch {
				// ignore
			}
			skyboxMesh = null;
		}

		function disposeEnvironmentTexture() {
			try {
				envTexture && envTexture.dispose();
			} catch {
				// ignore
			}
			envTexture = null;
			try {
				// scene.environmentTexture 可能等于 envTexture
				if (scene.environmentTexture) scene.environmentTexture = null;
			} catch {
				// ignore
			}
		}

		function getEnvSettings() {
			const e = (config && config.environment) || {};
			return {
				sourceMode: e.sourceMode || "auto",
				backgroundMode: e.backgroundMode || "skybox",
				backgroundColor: Array.isArray(e.backgroundColor) ? e.backgroundColor : [0.04, 0.06, 0.1],
				backgroundAlpha: typeof e.backgroundAlpha === "number" ? e.backgroundAlpha : 1.0,
				intensity: typeof e.intensity === "number" ? e.intensity : 1.0,
				exposure: typeof e.exposure === "number" ? e.exposure : 1.05,
				contrast: typeof e.contrast === "number" ? e.contrast : 1.05,
				rotationYDeg: typeof e.rotationYDeg === "number" ? e.rotationYDeg : 0,
				skyboxBlur: typeof e.skyboxBlur === "number" ? e.skyboxBlur : 0.25,
			};
		}

		function syncBackgroundParams() {
			const e = getEnvSettings();
			if (e.backgroundMode === "solid") {
				// 确保每帧都会清屏，否则 clearColor 可能看不出来
				try {
					scene.autoClear = true;
					scene.autoClearDepthAndStencil = true;
				} catch {
					// ignore
				}
				const c = e.backgroundColor;
				const r = typeof c[0] === "number" ? c[0] : 0;
				const g = typeof c[1] === "number" ? c[1] : 0;
				const b = typeof c[2] === "number" ? c[2] : 0;
				const a = Math.max(0, Math.min(1, e.backgroundAlpha));
				scene.clearColor = new BABYLON.Color4(r, g, b, a);
			} else {
				try {
					scene.autoClear = true;
					scene.autoClearDepthAndStencil = true;
				} catch {
					// ignore
				}
				// skybox 模式下 clearColor 仍保留一个底色（skybox 失败时可见）
				scene.clearColor = new BABYLON.Color4(0.04, 0.06, 0.1, 1);
			}
		}

		function applySkyboxIfNeeded(blur) {
			const e = getEnvSettings();
			if (e.backgroundMode !== "skybox") {
				disposeSkybox();
				lastSkyboxBlur = null;
				return;
			}
			if (!scene.environmentTexture) return;
			if (lastSkyboxBlur === blur && skyboxMesh) return;
			disposeSkybox();
			try {
				skyboxMesh = scene.createDefaultSkybox(scene.environmentTexture, true, 1200, blur);
				lastSkyboxBlur = blur;
			} catch {
				// ignore
			}
		}

		function syncEnvironmentParams() {
			const e = getEnvSettings();
			if (lastIntensity !== e.intensity) {
				scene.environmentIntensity = e.intensity;
				lastIntensity = e.intensity;
			}
			if (scene.imageProcessingConfiguration) {
				scene.imageProcessingConfiguration.toneMappingEnabled = true;
				if (lastExposure !== e.exposure) {
					scene.imageProcessingConfiguration.exposure = e.exposure;
					lastExposure = e.exposure;
				}
				if (lastContrast !== e.contrast) {
					scene.imageProcessingConfiguration.contrast = e.contrast;
					lastContrast = e.contrast;
				}
			}
			if (scene.environmentTexture && lastRotationDeg !== e.rotationYDeg) {
				try {
					const rad = BABYLON.Tools.ToRadians(e.rotationYDeg);
					scene.environmentTexture.setReflectionTextureMatrix(BABYLON.Matrix.RotationY(rad));
					lastRotationDeg = e.rotationYDeg;
				} catch {
					// ignore
				}
			}
			applySkyboxIfNeeded(e.skyboxBlur);
		}

		function applyEnvironmentTexture(tex) {
			disposeSkybox();
			disposeEnvironmentTexture();
			envTexture = tex;
			scene.environmentTexture = tex;
			lastSkyboxBlur = null;
			lastRotationDeg = null;
			lastIntensity = null;
			lastExposure = null;
			lastContrast = null;
			syncEnvironmentParams();
		}

		async function setupEnvironmentAsync(reason) {
			if (isLoading) return;
			isLoading = true;
			const token = ++loadToken;
			try {
				const e = getEnvSettings();
				if (e.sourceMode === "none") {
					disposeSkybox();
					disposeEnvironmentTexture();
					hud && hud.setStatus && hud.setStatus("环境贴图：无");
					return;
				}
				// 允许 UI 动态改 URL
				envLocalUrl = (config && config.environmentTextureUrl) || envLocalUrl;
				exrUrl = (config && config.environmentExrUrl) || exrUrl;
				exrPrefilterSize =
					(config && config.environment && config.environment.exrPrefilterSize) ||
					(config && config.environmentExrPrefilterSize) ||
					exrPrefilterSize;

				const order =
					e.sourceMode === "env"
						? ["env", "fallback"]
						: e.sourceMode === "exr"
							? ["exr", "fallback"]
							: e.sourceMode === "fallback"
								? ["fallback"]
								: ["env", "exr", "fallback"]; // auto

				for (const step of order) {
					if (token !== loadToken) return;
					if (step === "env") {
						if (envLocalUrl && (await urlExists(envLocalUrl))) {
							try {
								applyEnvironmentTexture(BABYLON.CubeTexture.CreateFromPrefilteredData(envLocalUrl, scene));
								hud && hud.setStatus && hud.setStatus("环境贴图：本地 .env");
								return;
							} catch {
								// ignore
							}
						}
					}
					if (step === "exr") {
						if (exrUrl && (await urlExists(exrUrl))) {
							try {
								const exrTex = new BABYLON.EXRCubeTexture(exrUrl, scene, exrPrefilterSize, false, true, false, true);
								await new Promise((resolve) => exrTex.onLoadObservable.addOnce(resolve));
								if (token !== loadToken) {
									try {
										exrTex.dispose();
									} catch {
										// ignore
									}
									return;
								}
								applyEnvironmentTexture(exrTex);
								hud &&
									hud.setStatus &&
									hud.setStatus("环境贴图：本地 EXR（建议先烘焙成 .env）");
								return;
							} catch {
								// ignore
							}
						}
					}
					if (step === "fallback") {
						try {
							applyEnvironmentTexture(BABYLON.CubeTexture.CreateFromPrefilteredData(envFallbackUrl, scene));
							return;
						} catch {
							// ignore
						}
					}
				}
			} finally {
				isLoading = false;
			}
		}

		function computeLoadKey() {
			const e = getEnvSettings();
			return [
				e.sourceMode,
				(config && config.environmentTextureUrl) || "",
				(config && config.environmentExrUrl) || "",
				(config && config.environmentFallbackUrl) || "",
				(config && config.environment && config.environment.exrPrefilterSize) || config.environmentExrPrefilterSize || 0,
			].join("|");
		}

		await setupEnvironmentAsync("init");
		syncBackgroundParams();

		// Lights + shadows
		const hemi = new BABYLON.HemisphericLight("hemi", new BABYLON.Vector3(0, 1, 0), scene);
		hemi.intensity = 0.75;

		const dir = new BABYLON.DirectionalLight("dir", new BABYLON.Vector3(-0.4, -1.0, 0.6), scene);
		dir.intensity = 1.1;

		const shadowGen = new BABYLON.ShadowGenerator(2048, dir);
		shadowGen.useBlurExponentialShadowMap = true;
		shadowGen.blurKernel = 16;

		// 环境强度在 skybox/IBL 初始化里设置

		// Actors
		const cameraActor = new window.AYE48.Actors.CameraActor(scene, config);
		scene.activeCamera = cameraActor.camera;

		// ===== Render / Pipelines（可在编辑器里实时调） =====
		let defaultPipeline = null;
		let ssao2Pipeline = null;
		let lastRenderKey = "";
		let lastHardwareScaling = null;

		function getRenderSettings() {
			const r = (config && config.render) || {};
			const e = r.engine || {};
			const dp = r.defaultPipeline || {};
			const ssao = r.ssao2 || {};
			return {
				engine: {
					hardwareScalingLevel:
						typeof e.hardwareScalingLevel === "number" ? e.hardwareScalingLevel : 1.0,
				},
				defaultPipeline: {
					enabled: dp.enabled !== false,
					fxaaEnabled: dp.fxaaEnabled !== false,
					bloomEnabled: !!dp.bloomEnabled,
					bloomThreshold: typeof dp.bloomThreshold === "number" ? dp.bloomThreshold : 0.9,
					bloomWeight: typeof dp.bloomWeight === "number" ? dp.bloomWeight : 0.15,
					bloomKernel: typeof dp.bloomKernel === "number" ? dp.bloomKernel : 64,
					bloomScale: typeof dp.bloomScale === "number" ? dp.bloomScale : 0.5,
					sharpenEnabled: !!dp.sharpenEnabled,
					sharpenEdgeAmount: typeof dp.sharpenEdgeAmount === "number" ? dp.sharpenEdgeAmount : 0.2,
					sharpenColorAmount: typeof dp.sharpenColorAmount === "number" ? dp.sharpenColorAmount : 0.6,
					chromaticAberrationEnabled: !!dp.chromaticAberrationEnabled,
					chromaticAberrationAmount:
						typeof dp.chromaticAberrationAmount === "number" ? dp.chromaticAberrationAmount : 15,
					grainEnabled: !!dp.grainEnabled,
					grainIntensity: typeof dp.grainIntensity === "number" ? dp.grainIntensity : 10,
					depthOfFieldEnabled: !!dp.depthOfFieldEnabled,
					dofFocusDistance: typeof dp.dofFocusDistance === "number" ? dp.dofFocusDistance : 200,
					dofFStop: typeof dp.dofFStop === "number" ? dp.dofFStop : 1.4,
					dofFocalLength: typeof dp.dofFocalLength === "number" ? dp.dofFocalLength : 50,
					dofLensSize: typeof dp.dofLensSize === "number" ? dp.dofLensSize : 50,
				},
				ssao2: {
					enabled: !!ssao.enabled,
					ratio: typeof ssao.ratio === "number" ? ssao.ratio : 0.5,
					radius: typeof ssao.radius === "number" ? ssao.radius : 2.0,
					totalStrength: typeof ssao.totalStrength === "number" ? ssao.totalStrength : 1.0,
					base: typeof ssao.base === "number" ? ssao.base : 0.5,
					area: typeof ssao.area === "number" ? ssao.area : 0.0075,
					fallOff: typeof ssao.fallOff === "number" ? ssao.fallOff : 0.000001,
				},
			};
		}

		function disposePipeline(p) {
			try {
				p && p.dispose && p.dispose();
			} catch {
				// ignore
			}
		}

		function ensureDefaultPipeline(r) {
			if (!r.defaultPipeline.enabled) {
				if (defaultPipeline) {
					disposePipeline(defaultPipeline);
					defaultPipeline = null;
				}
				return;
			}
			if (!defaultPipeline) {
				try {
					defaultPipeline = new BABYLON.DefaultRenderingPipeline(
						"defaultPipeline",
						true,
						scene,
						[cameraActor.camera]
					);
				} catch {
					defaultPipeline = null;
				}
			}
			if (!defaultPipeline) return;
			try {
				defaultPipeline.fxaaEnabled = !!r.defaultPipeline.fxaaEnabled;
			} catch {
				// ignore
			}

			try {
				defaultPipeline.bloomEnabled = !!r.defaultPipeline.bloomEnabled;
				defaultPipeline.bloomThreshold = r.defaultPipeline.bloomThreshold;
				defaultPipeline.bloomWeight = r.defaultPipeline.bloomWeight;
				defaultPipeline.bloomKernel = r.defaultPipeline.bloomKernel;
				defaultPipeline.bloomScale = r.defaultPipeline.bloomScale;
			} catch {
				// ignore
			}

			// 这些特性在不同版本/能力下可能不存在，全部做容错
			try {
				if (defaultPipeline.sharpen) {
					defaultPipeline.sharpenEnabled = !!r.defaultPipeline.sharpenEnabled;
					if (typeof defaultPipeline.sharpen.edgeAmount === "number") {
						defaultPipeline.sharpen.edgeAmount = r.defaultPipeline.sharpenEdgeAmount;
					}
					if (typeof defaultPipeline.sharpen.colorAmount === "number") {
						defaultPipeline.sharpen.colorAmount = r.defaultPipeline.sharpenColorAmount;
					}
				}
			} catch {
				// ignore
			}

			try {
				if (defaultPipeline.chromaticAberration) {
					defaultPipeline.chromaticAberrationEnabled = !!r.defaultPipeline.chromaticAberrationEnabled;
					defaultPipeline.chromaticAberration.aberrationAmount = r.defaultPipeline.chromaticAberrationAmount;
				}
			} catch {
				// ignore
			}

			try {
				if (defaultPipeline.grain) {
					defaultPipeline.grainEnabled = !!r.defaultPipeline.grainEnabled;
					defaultPipeline.grain.intensity = r.defaultPipeline.grainIntensity;
				}
			} catch {
				// ignore
			}

			try {
				if (defaultPipeline.depthOfField) {
					defaultPipeline.depthOfFieldEnabled = !!r.defaultPipeline.depthOfFieldEnabled;
					defaultPipeline.depthOfField.focusDistance = r.defaultPipeline.dofFocusDistance;
					defaultPipeline.depthOfField.fStop = r.defaultPipeline.dofFStop;
					defaultPipeline.depthOfField.focalLength = r.defaultPipeline.dofFocalLength;
					defaultPipeline.depthOfField.lensSize = r.defaultPipeline.dofLensSize;
				}
			} catch {
				// ignore
			}
		}

		function ensureSsao2(r) {
			if (!r.ssao2.enabled) {
				if (ssao2Pipeline) {
					disposePipeline(ssao2Pipeline);
					ssao2Pipeline = null;
				}
				return;
			}
			// ratio 改变通常需要重建（内部 RT 尺寸会变）
			if (!ssao2Pipeline) {
				try {
					ssao2Pipeline = new BABYLON.SSAO2RenderingPipeline(
						"ssao2Pipeline",
						scene,
						r.ssao2.ratio,
						[cameraActor.camera],
						true
					);
					scene.postProcessRenderPipelineManager.addPipeline(ssao2Pipeline);
					scene.postProcessRenderPipelineManager.attachCamerasToRenderPipeline(
						"ssao2Pipeline",
						cameraActor.camera
					);
				} catch {
					ssao2Pipeline = null;
				}
			}
			if (!ssao2Pipeline) return;
			try {
				if (typeof ssao2Pipeline.radius === "number") ssao2Pipeline.radius = r.ssao2.radius;
				if (typeof ssao2Pipeline.totalStrength === "number") ssao2Pipeline.totalStrength = r.ssao2.totalStrength;
				if (typeof ssao2Pipeline.base === "number") ssao2Pipeline.base = r.ssao2.base;
				if (typeof ssao2Pipeline.area === "number") ssao2Pipeline.area = r.ssao2.area;
				if (typeof ssao2Pipeline.fallOff === "number") ssao2Pipeline.fallOff = r.ssao2.fallOff;
			} catch {
				// ignore
			}
		}

		function computeRenderKey(r) {
			return [
				"v1",
				r.engine.hardwareScalingLevel,
				r.defaultPipeline.enabled,
				r.defaultPipeline.fxaaEnabled,
				r.defaultPipeline.bloomEnabled,
				r.defaultPipeline.bloomThreshold,
				r.defaultPipeline.bloomWeight,
				r.defaultPipeline.bloomKernel,
				r.defaultPipeline.bloomScale,
				r.defaultPipeline.sharpenEnabled,
				r.defaultPipeline.sharpenEdgeAmount,
				r.defaultPipeline.sharpenColorAmount,
				r.defaultPipeline.chromaticAberrationEnabled,
				r.defaultPipeline.chromaticAberrationAmount,
				r.defaultPipeline.grainEnabled,
				r.defaultPipeline.grainIntensity,
				r.defaultPipeline.depthOfFieldEnabled,
				r.defaultPipeline.dofFocusDistance,
				r.defaultPipeline.dofFStop,
				r.defaultPipeline.dofFocalLength,
				r.defaultPipeline.dofLensSize,
				r.ssao2.enabled,
				r.ssao2.ratio,
				r.ssao2.radius,
				r.ssao2.totalStrength,
				r.ssao2.base,
				r.ssao2.area,
				r.ssao2.fallOff,
			].join("|");
		}

		function syncRender() {
			const r = getRenderSettings();
			const lvl = Math.max(0.5, Math.min(2.0, r.engine.hardwareScalingLevel));
			if (lastHardwareScaling !== lvl) {
				try {
					engine.setHardwareScalingLevel(lvl);
					lastHardwareScaling = lvl;
				} catch {
					// ignore
				}
			}

			const key = computeRenderKey(r);
			// SSAO2 ratio 变化需要重建；其余也可能需要，统一用 key 简化
			if (key !== lastRenderKey) {
				lastRenderKey = key;
				// SSAO2 需要用 pipelineManager 挂载，切换时先销毁
				if (ssao2Pipeline) {
					try {
						scene.postProcessRenderPipelineManager.detachCamerasFromRenderPipeline(
							"ssao2Pipeline",
							cameraActor.camera
						);
					} catch {
						// ignore
					}
					disposePipeline(ssao2Pipeline);
					ssao2Pipeline = null;
				}
			}

			ensureDefaultPipeline(r);
			ensureSsao2(r);
		}

		const groundActor = new window.AYE48.Actors.GroundActor(scene, config);

		const model = await window.AYE48.Actors.loadModel(scene, shadowGen, config.modelUrl, hud.setStatus);

		// 自动取景（放在模型居中贴地之后）
		try {
			cameraActor.camera.position = new BABYLON.Vector3(
				0,
				model.centeredCenter.y + Math.max(1.2, model.radius * 0.35),
				-Math.max(3.5, model.radius * 2.2)
			);
			cameraActor.baseY = cameraActor.camera.position.y;
			cameraActor.lookAt(model.centeredCenter);
		} catch {
			// ignore
		}

		// 通用物件蓝图：基础高度(≈相机高度2/3) + 自转 + 上下浮动
		const propBP = new window.AYE48.Blueprints.PropActorBP(
			model.root,
			cameraActor,
			model.centeredCenter,
			config
		);
		// 抬高/浮动后，重新对准视线并保存复位点
		cameraActor.lookAt(propBP.getSuggestedLookTarget());
		cameraActor.saveSpawn();

		const controller = new window.AYE48.Blueprints.PlayerControllerBP(
			scene,
			canvas,
			cameraActor,
			hud,
			config
		);

		hud.wireReset(() => cameraActor.resetToSpawn());

		hud.setStatus(`加载完成：mesh ${model.result.meshes.length} / materials ${scene.materials.length}`);

		const start = performance.now();
		scene.onBeforeRenderObservable.add(() => {
			const dt = engine.getDeltaTime() / 1000;
			hud.setFps(`${engine.getFps().toFixed(0)} fps`);

			// 环境参数实时同步
			syncBackgroundParams();
			syncEnvironmentParams();
			const key = computeLoadKey();
			if (key !== lastLoadKey) {
				lastLoadKey = key;
				setupEnvironmentAsync("configChanged");
			}

			groundActor.followCamera(cameraActor.camera.position);
			syncRender();
			propBP.tick(dt);
			controller.tick(dt);
		});

		return { scene, cameraActor, model, groundActor, controller, propBP };
	}

	window.AYE48.Maps.createShowcaseMap = createShowcaseMap;
})();
