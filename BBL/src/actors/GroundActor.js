(function () {
	window.AYE48 = window.AYE48 || {};
	window.AYE48.Actors = window.AYE48.Actors || {};

	function GroundActor(scene, config) {
		this.scene = scene;
		this.config = config;
		this._cameraPos = new BABYLON.Vector3(0, 0, 0);
		this._sig = "";
		this._lastFadeTime = 0;
		this._lastFadeCamX = NaN;
		this._lastFadeCamZ = NaN;
		this._minorPos = null;
		this._minorCol = null;
		this._majorPos = null;
		this._majorCol = null;
		this._minorBaseAlpha = 0;
		this._majorBaseAlpha = 0;

		const g = config.ground;
		// 透明无限网格：使用 LineSystem（只有线条，没有地面填充）
		this.root = new BABYLON.TransformNode("groundRoot", scene);
		this.root.position.y = g.y;

		this.minor = null;
		this.major = null;
		this._rebuild();
	}

	GroundActor.prototype._signature = function () {
		const g = this.config.ground;
		const step = Math.max(0.01, Number(g.gridRatio) || 1);
		const majorEvery = Math.max(1, Math.floor(Number(g.majorUnitFrequency) || 10));
		const minorAlpha = typeof g.minorAlpha === "number" ? g.minorAlpha : 0.06;
		const majorAlpha = typeof g.majorAlpha === "number" ? g.majorAlpha : 0.12;
		const fadeStart = Math.max(0, Number(g.fadeStart) || 0);
		const fadeEnd = Math.max(fadeStart + 1, Number(g.fadeEnd) || (fadeStart + 1));
		const fadePower = Math.max(0.25, Number(g.fadePower) || 1.6);
		const minorColor = g.minorColor || [0.22, 0.22, 0.22];
		const majorColor = g.majorColor || [0.55, 0.55, 0.55];
		const width = Number(g.width) || 2000;
		const height = Number(g.height) || 2000;
		return [
			"v2",
			step,
			majorEvery,
			minorAlpha,
			majorAlpha,
			fadeStart,
			fadeEnd,
			fadePower,
			minorColor.join(","),
			majorColor.join(","),
			width,
			height,
		].join("|");
	};

	GroundActor.prototype._rebuild = function () {
		const g = this.config.ground;
		this.root.position.y = g.y;

		if (this.minor) this.minor.dispose();
		if (this.major) this.major.dispose();

		const step = Math.max(0.01, Number(g.gridRatio) || 1);
		const majorEvery = Math.max(1, Math.floor(Number(g.majorUnitFrequency) || 10));
		const minorAlpha = typeof g.minorAlpha === "number" ? g.minorAlpha : 0.06;
		const majorAlpha = typeof g.majorAlpha === "number" ? g.majorAlpha : 0.12;
		const fadeStart = Math.max(0, Number(g.fadeStart) || 0);
		const fadeEnd = Math.max(fadeStart + 1, Number(g.fadeEnd) || (fadeStart + 1));
		const fadeRange = Math.max(1, fadeEnd - fadeStart);
		// 分段长度：控制渐隐平滑度与性能（越小越平滑但更重）
		const segmentLen = Math.max(step * 2, Math.min(50, fadeRange / 16));
		const minorColor = g.minorColor || [0.22, 0.22, 0.22];
		const majorColor = g.majorColor || [0.55, 0.55, 0.55];
		const width = Number(g.width) || 2000;
		const height = Number(g.height) || 2000;

		const halfW = width / 2;
		const halfH = height / 2;
		// 只生成 fadeEnd 范围内的几何（否则长线段会让渐隐看起来“不自然”且很重）
		const effHalfW = Math.min(halfW, fadeEnd + step * 2);
		const effHalfH = Math.min(halfH, fadeEnd + step * 2);

		function buildLines(gridStep, colorArr, alpha, onlyEvery) {
			const lines = [];
			const colors = [];

			const cx = new BABYLON.Color4(colorArr[0], colorArr[1], colorArr[2], alpha);
			const countX = Math.floor(effHalfW / gridStep);
			const countZ = Math.floor(effHalfH / gridStep);

			function pushPolyline(points) {
				lines.push(points);
				colors.push(points.map(() => cx));
			}

			function makeSegmentedLine(x0, z0, x1, z1) {
				const pts = [];
				const dx = x1 - x0;
				const dz = z1 - z0;
				const len = Math.sqrt(dx * dx + dz * dz);
				const n = Math.max(1, Math.ceil(len / segmentLen));
				for (let i = 0; i <= n; i++) {
					const t = i / n;
					pts.push(new BABYLON.Vector3(x0 + dx * t, 0, z0 + dz * t));
				}
				return pts;
			}

			for (let i = -countX; i <= countX; i++) {
				if (onlyEvery && (Math.abs(i) % onlyEvery) !== 0) continue;
				const x = i * gridStep;
				pushPolyline(makeSegmentedLine(x, -effHalfH, x, effHalfH));
			}

			for (let k = -countZ; k <= countZ; k++) {
				if (onlyEvery && (Math.abs(k) % onlyEvery) !== 0) continue;
				const z = k * gridStep;
				pushPolyline(makeSegmentedLine(-effHalfW, z, effHalfW, z));
			}

			return { lines, colors };
		}

		const minorData = buildLines(step, minorColor, minorAlpha, null);
		this.minor = BABYLON.MeshBuilder.CreateLineSystem(
			"gridMinor",
			{ lines: minorData.lines, colors: minorData.colors, useVertexAlpha: true },
			this.scene
		);
		this.minor.isPickable = false;
		this.minor.parent = this.root;
		this._minorBaseAlpha = minorAlpha;
		this._minorPos = this.minor.getVerticesData(BABYLON.VertexBuffer.PositionKind);
		this._minorCol = this.minor.getVerticesData(BABYLON.VertexBuffer.ColorKind);

		const majorData = buildLines(step, majorColor, majorAlpha, majorEvery);
		this.major = BABYLON.MeshBuilder.CreateLineSystem(
			"gridMajor",
			{ lines: majorData.lines, colors: majorData.colors, useVertexAlpha: true },
			this.scene
		);
		this.major.isPickable = false;
		this.major.parent = this.root;
		this._majorBaseAlpha = majorAlpha;
		this._majorPos = this.major.getVerticesData(BABYLON.VertexBuffer.PositionKind);
		this._majorCol = this.major.getVerticesData(BABYLON.VertexBuffer.ColorKind);

		this._sig = this._signature();
		this._updateFade(true);
	};

	GroundActor.prototype._rebuildIfNeeded = function () {
		const sig = this._signature();
		if (sig !== this._sig) this._rebuild();
	};

	GroundActor.prototype._smoothstep = function (edge0, edge1, x) {
		const t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)));
		return t * t * (3 - 2 * t);
	};

	GroundActor.prototype._updateFade = function (force) {
		const g = this.config.ground;
		const fadeStart = Math.max(0, Number(g.fadeStart) || 0);
		const fadeEnd = Math.max(fadeStart + 1, Number(g.fadeEnd) || (fadeStart + 1));
		const fadePower = Math.max(0.25, Number(g.fadePower) || 1.6);
		if (!this._minorPos || !this._minorCol || !this._majorPos || !this._majorCol) return;

		const now = performance && performance.now ? performance.now() : Date.now();
		const camX = this._cameraPos.x;
		const camZ = this._cameraPos.z;
		if (!force) {
			// 简单节流：最多 30Hz；且相机没动就不更新
			if (now - this._lastFadeTime < 33) return;
			if (camX === this._lastFadeCamX && camZ === this._lastFadeCamZ) return;
		}

		this._lastFadeTime = now;
		this._lastFadeCamX = camX;
		this._lastFadeCamZ = camZ;

		const rx = this.root.position.x;
		const rz = this.root.position.z;

		const applyTo = (mesh, pos, col, baseAlpha) => {
			const vertCount = Math.floor(pos.length / 3);
			for (let vi = 0; vi < vertCount; vi++) {
				const x = pos[vi * 3] + rx;
				const z = pos[vi * 3 + 2] + rz;
				const dx = x - camX;
				const dz = z - camZ;
				const dist = Math.sqrt(dx * dx + dz * dz);
				const s = this._smoothstep(fadeStart, fadeEnd, dist);
				let fade = 1.0 - s;
				fade = Math.pow(Math.max(0, Math.min(1, fade)), fadePower);
				col[vi * 4 + 3] = baseAlpha * fade;
			}
			try {
				mesh.updateVerticesDataDirectly(BABYLON.VertexBuffer.ColorKind, col, 0, true);
			} catch {
				// fallback
				try {
					mesh.setVerticesData(BABYLON.VertexBuffer.ColorKind, col, true);
				} catch {
					// ignore
				}
			}
		};

		applyTo(this.minor, this._minorPos, this._minorCol, this._minorBaseAlpha);
		applyTo(this.major, this._majorPos, this._majorCol, this._majorBaseAlpha);
	};

	GroundActor.prototype.followCamera = function (cameraPosition) {
		this._cameraPos.copyFrom(cameraPosition);
		this._rebuildIfNeeded();

		const step = this.config.ground.followStep;
		this.root.position.x = Math.round(cameraPosition.x / step) * step;
		this.root.position.z = Math.round(cameraPosition.z / step) * step;
		this._updateFade(false);
	};

	window.AYE48.Actors.GroundActor = GroundActor;
})();
