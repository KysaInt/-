(function () {
	window.AYE48 = window.AYE48 || {};
	window.AYE48.UI = window.AYE48.UI || {};

	function mountHud(rootEl, config) {
		const defaultMoveSpeed = Number(config.movement.moveSpeed || 6);
		const defaultMouseTurn = Number(config.movement.mouseTurn || 0.008);

		rootEl.innerHTML = `
			<div class="row">
				<strong>${config.ui.title}</strong>
				<span>
					<button id="resetCamera" type="button">复位</button>
					<span id="fps">-- fps</span>
				</span>
			</div>
			<div class="row">
				<label>移动速度 <span id="moveSpeedVal"></span></label>
				<input id="moveSpeed" type="range" min="0" max="30" step="0.1" value="${defaultMoveSpeed}" />
			</div>
			<div class="row">
				<label>鼠标旋转速率 <span id="mouseTurnVal"></span></label>
				<input id="mouseTurn" type="range" min="0" max="0.03" step="0.0005" value="${defaultMouseTurn}" />
			</div>
			<div id="status">准备中…</div>
			<div id="hint">操作：W/S 前后；A/D 左右平移；右键按住拖动原地转向；空格跳跃。</div>
		`;

		const els = {
			fps: rootEl.querySelector("#fps"),
			status: rootEl.querySelector("#status"),
			resetCamera: rootEl.querySelector("#resetCamera"),
			moveSpeed: rootEl.querySelector("#moveSpeed"),
			moveSpeedVal: rootEl.querySelector("#moveSpeedVal"),
			mouseTurn: rootEl.querySelector("#mouseTurn"),
			mouseTurnVal: rootEl.querySelector("#mouseTurnVal"),
		};

		function setStatus(text) {
			els.status.textContent = text;
		}

		function setFps(text) {
			els.fps.textContent = text;
		}

		function updateLabels() {
			if (els.moveSpeedVal) els.moveSpeedVal.textContent = Number(els.moveSpeed.value).toFixed(1);
			if (els.mouseTurnVal) els.mouseTurnVal.textContent = Number(els.mouseTurn.value).toFixed(4);
		}
		els.moveSpeed.addEventListener("input", updateLabels);
		els.mouseTurn.addEventListener("input", updateLabels);
		updateLabels();

		function getMoveSpeed() {
			return Number(els.moveSpeed.value);
		}

		function getMouseTurn() {
			return Number(els.mouseTurn.value);
		}

		function wireReset(handler) {
			els.resetCamera.addEventListener("click", handler);
		}

		return {
			els,
			setStatus,
			setFps,
			getMoveSpeed,
			getMouseTurn,
			wireReset,
		};
	}

	window.AYE48.UI.mountHud = mountHud;
})();
