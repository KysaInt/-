(function () {
	window.AYE48 = window.AYE48 || {};
	window.AYE48.Blueprints = window.AYE48.Blueprints || {};

	function PropActorBP(transformNode, cameraActor, centeredCenter, config) {
		this.node = transformNode;
		this.cameraActor = cameraActor;
		this.centeredCenter = centeredCenter || new BABYLON.Vector3(0, 0, 0);
		this.config = config;

		const propCfg = (config && config.prop) || {};
		this.baseHeightFactor = typeof propCfg.baseHeightFactor === "number" ? propCfg.baseHeightFactor : 2 / 3;
		this.rotationSpeed = typeof propCfg.rotationSpeed === "number" ? propCfg.rotationSpeed : 0.6; // rad/s
		this.bobAmplitudeFactor =
			typeof propCfg.bobAmplitudeFactor === "number" ? propCfg.bobAmplitudeFactor : 0.08;
		this.bobFrequency = typeof propCfg.bobFrequency === "number" ? propCfg.bobFrequency : 1.0; // Hz

		this.baseY = 0;
		this.start = performance.now();

		this.recomputeBaseHeight();
		this.applyBaseHeight();
	}

	PropActorBP.prototype.recomputeBaseHeight = function () {
		// 按“相机高度”的 2/3 给物件一个基础高度
		const camY = this.cameraActor && typeof this.cameraActor.baseY === "number" ? this.cameraActor.baseY : 1.6;
		this.baseY = camY * this.baseHeightFactor;
		this.bobAmplitude = camY * this.bobAmplitudeFactor;
	};

	PropActorBP.prototype.applyBaseHeight = function () {
		// 由于模型加载阶段已把最低点贴到 y=0，这里直接抬到 baseY 即可
		this.node.position.y = this.baseY;
	};

	PropActorBP.prototype.getSuggestedLookTarget = function () {
		// centeredCenter 是“贴地且XZ归零后”的模型中心点（局部/世界一致），再加上物件整体高度偏移
		return this.centeredCenter.add(new BABYLON.Vector3(0, this.baseY, 0));
	};

	PropActorBP.prototype.tick = function (dt) {
		// 运行时同步配置（编辑器改动可立即生效）
		const propCfg = (this.config && this.config.prop) || {};
		if (typeof propCfg.baseHeightFactor === "number") this.baseHeightFactor = propCfg.baseHeightFactor;
		if (typeof propCfg.rotationSpeed === "number") this.rotationSpeed = propCfg.rotationSpeed;
		if (typeof propCfg.bobAmplitudeFactor === "number") this.bobAmplitudeFactor = propCfg.bobAmplitudeFactor;
		if (typeof propCfg.bobFrequency === "number") this.bobFrequency = propCfg.bobFrequency;
		this.recomputeBaseHeight();

		const t = (performance.now() - this.start) / 1000;

		// 自转
		this.node.rotation.y += this.rotationSpeed * dt;

		// 上下浮动（围绕 baseY）
		this.node.position.y = this.baseY + Math.sin(t * Math.PI * 2 * this.bobFrequency) * this.bobAmplitude;
	};

	window.AYE48.Blueprints.PropActorBP = PropActorBP;
})();
