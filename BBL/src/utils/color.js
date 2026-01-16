(function () {
	window.AYE48 = window.AYE48 || {};
	window.AYE48.Utils = window.AYE48.Utils || {};

	function hsvToColor3(BABYLON, h, s, v) {
		h = ((h % 1) + 1) % 1;
		const i = Math.floor(h * 6);
		const f = h * 6 - i;
		const p = v * (1 - s);
		const q = v * (1 - f * s);
		const t = v * (1 - (1 - f) * s);
		let r, g, b;
		switch (i % 6) {
			case 0:
				(r = v), (g = t), (b = p);
				break;
			case 1:
				(r = q), (g = v), (b = p);
				break;
			case 2:
				(r = p), (g = v), (b = t);
				break;
			case 3:
				(r = p), (g = q), (b = v);
				break;
			case 4:
				(r = t), (g = p), (b = v);
				break;
			default:
				(r = v), (g = p), (b = q);
				break;
		}
		return new BABYLON.Color3(r, g, b);
	}

	window.AYE48.Utils.hsvToColor3 = hsvToColor3;
})();
