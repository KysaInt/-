(function () {
	window.AYE48 = window.AYE48 || {};
	window.AYE48.Systems = window.AYE48.Systems || {};

	function FiberAnimSystem(fiberMaterials, hud, config) {
		this.fiberMaterials = fiberMaterials;
		this.hud = hud;
		this.config = config;
		this.start = performance.now();
	}

	FiberAnimSystem.prototype.tick = function () {
		if (!this.hud.els.fiberToggle.checked) return;
		if (!this.fiberMaterials || this.fiberMaterials.size === 0) return;

		const now = performance.now();
		const t = (now - this.start) / 1000;
		const s = Number(this.hud.els.fiberSpeed.value);
		const hue = (t * 0.08 * s) % 1;
		const pulse = 0.65 + 0.35 * Math.sin(t * 2.0 * s);

		let idx = 0;
		for (const mat of this.fiberMaterials) {
			const localHue = (hue + idx * 0.07) % 1;
			const c = window.AYE48.Utils.hsvToColor3(BABYLON, localHue, 0.95, 1.0);

			if (mat.emissiveColor) mat.emissiveColor = c.scale(pulse);
			if (typeof mat.emissiveIntensity === "number") mat.emissiveIntensity = 0.6 + 1.2 * pulse;

			idx++;
		}
	};

	window.AYE48.Systems.FiberAnimSystem = FiberAnimSystem;
})();
