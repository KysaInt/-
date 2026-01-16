(function () {
	window.AYE48 = window.AYE48 || {};
	window.AYE48.UI = window.AYE48.UI || {};

	function _fmt(v, digits) {
		if (typeof v !== "number" || Number.isNaN(v)) return "--";
		return v.toFixed(digits);
	}

	function _getByPath(obj, path) {
		let cur = obj;
		for (const key of path) {
			if (cur == null) return undefined;
			cur = cur[key];
		}
		return cur;
	}

	function _setByPath(obj, path, value) {
		let cur = obj;
		for (let i = 0; i < path.length - 1; i++) {
			const key = path[i];
			const nextKey = path[i + 1];

			// 数组下标路径（如 [.., 0, ..]）
			if (typeof key === "number") {
				if (!Array.isArray(cur)) return;
				if (cur[key] == null) cur[key] = typeof nextKey === "number" ? [] : {};
				cur = cur[key];
				continue;
			}

			// 对象 key
			if (cur[key] == null) cur[key] = typeof nextKey === "number" ? [] : {};
			cur = cur[key];
		}
		cur[path[path.length - 1]] = value;
	}

	function _clamp01(v) {
		if (typeof v !== "number" || Number.isNaN(v)) return 0;
		return Math.max(0, Math.min(1, v));
	}

	function _rgbToHsl01(r, g, b) {
		r = _clamp01(r);
		g = _clamp01(g);
		b = _clamp01(b);
		const max = Math.max(r, g, b);
		const min = Math.min(r, g, b);
		let h = 0;
		let s = 0;
		const l = (max + min) / 2;
		const d = max - min;
		if (d !== 0) {
			s = d / (1 - Math.abs(2 * l - 1));
			s = Number.isFinite(s) ? s : 0;
			s = Math.max(0, Math.min(1, s));
			if (max === r) h = ((g - b) / d) % 6;
			else if (max === g) h = (b - r) / d + 2;
			else h = (r - g) / d + 4;
			h *= 60;
			if (h < 0) h += 360;
		}
		return { h, s, l };
	}

	function _hslToRgb01(h, s, l) {
		h = ((h % 360) + 360) % 360;
		s = _clamp01(s);
		l = _clamp01(l);
		const c = (1 - Math.abs(2 * l - 1)) * s;
		const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
		const m = l - c / 2;
		let rp = 0,
			gp = 0,
			bp = 0;
		if (h < 60) {
			rp = c;
			gp = x;
			bp = 0;
		} else if (h < 120) {
			rp = x;
			gp = c;
			bp = 0;
		} else if (h < 180) {
			rp = 0;
			gp = c;
			bp = x;
		} else if (h < 240) {
			rp = 0;
			gp = x;
			bp = c;
		} else if (h < 300) {
			rp = x;
			gp = 0;
			bp = c;
		} else {
			rp = c;
			gp = 0;
			bp = x;
		}
		return { r: rp + m, g: gp + m, b: bp + m };
	}

	function _rgb01ToHex(r, g, b) {
		function to2(x) {
			const v = Math.round(_clamp01(x) * 255);
			return v.toString(16).padStart(2, "0");
		}
		return `#${to2(r)}${to2(g)}${to2(b)}`;
	}

	function _hexToRgb01(hex) {
		if (!hex || typeof hex !== "string") return null;
		const s = hex.trim().replace(/^#/, "");
		if (!(s.length === 6 || s.length === 3)) return null;
		const full = s.length === 3 ? s.split("").map((c) => c + c).join("") : s;
		const n = parseInt(full, 16);
		if (Number.isNaN(n)) return null;
		const r = (n >> 16) & 255;
		const g = (n >> 8) & 255;
		const b = n & 255;
		return { r: r / 255, g: g / 255, b: b / 255 };
	}

	function _makeSliderRow(doc, opts) {
		const row = doc.createElement("div");
		row.className = "row";

		const label = doc.createElement("label");
		label.textContent = opts.label + " ";

		const val = doc.createElement("span");
		val.className = "val";
		label.appendChild(val);

		const input = doc.createElement("input");
		input.type = "range";
		input.min = String(opts.min);
		input.max = String(opts.max);
		input.step = String(opts.step);
		input.value = String(opts.value);

		function updateLabel() {
			val.textContent = _fmt(Number(input.value), opts.digits);
		}
		updateLabel();

		input.addEventListener("input", () => {
			updateLabel();
			opts.onInput && opts.onInput(Number(input.value), input);
		});

		row.appendChild(label);
		row.appendChild(input);
		return { row, input, val, updateLabel };
	}

	function _makeSelectRow(doc, opts) {
		const row = doc.createElement("div");
		row.className = "row";

		const label = doc.createElement("label");
		label.textContent = opts.label;

		const select = doc.createElement("select");
		for (const item of opts.items || []) {
			const opt = doc.createElement("option");
			opt.value = String(item.value);
			opt.textContent = item.text;
			if (String(item.value) === String(opts.value)) opt.selected = true;
			select.appendChild(opt);
		}

		select.addEventListener("change", () => {
			opts.onChange && opts.onChange(select.value, select);
		});

		row.appendChild(label);
		row.appendChild(select);
		return { row, select };
	}

	function _makeToggleRow(doc, opts) {
		const row = doc.createElement("div");
		row.className = "row";

		const label = doc.createElement("label");
		label.textContent = opts.label;

		const input = doc.createElement("input");
		input.type = "checkbox";
		input.checked = !!opts.value;

		input.addEventListener("change", () => {
			opts.onChange && opts.onChange(!!input.checked, input);
		});

		row.appendChild(label);
		row.appendChild(input);
		return { row, input };
	}

	function mountEditorPanel(rootEl, config, hud) {
		rootEl.classList.add("editor");
		rootEl.innerHTML = "";

		const doc = rootEl.ownerDocument;
		const WinEvent = (doc && doc.defaultView && doc.defaultView.Event) || Event;

		const header = doc.createElement("div");
		header.className = "header";
		const headerLeft = doc.createElement("div");
		headerLeft.innerHTML = `<strong>编辑器</strong><span class="sub">(实时)</span>`;
		const headerRight = doc.createElement("div");
		headerRight.style.display = "flex";
		headerRight.style.alignItems = "center";
		headerRight.style.gap = "8px";
		header.appendChild(headerLeft);
		header.appendChild(headerRight);
		rootEl.appendChild(header);

		// 确保折叠状态容器存在
		config.ui = config.ui || {};
		config.ui.editor = config.ui.editor || {};
		config.ui.editor.open = config.ui.editor.open || {};
		if (typeof config.ui.editor.collapsed !== "boolean") config.ui.editor.collapsed = false;

		function setCollapsed(isCollapsed) {
			config.ui.editor.collapsed = !!isCollapsed;
			try {
				doc.body.classList.toggle("editorCollapsed", !!config.ui.editor.collapsed);
			} catch {
				// ignore
			}
			try {
				window.AYE48 && window.AYE48.ConfigStore && window.AYE48.ConfigStore.markDirty("editorCollapsed");
			} catch {
				// ignore
			}
			if (collapseBtn) {
				collapseBtn.textContent = config.ui.editor.collapsed ? "⮜" : "⮞";
				collapseBtn.title = config.ui.editor.collapsed ? "展开右侧面板" : "折叠隐藏右侧面板";
			}
			if (dockBtn) {
				dockBtn.textContent = config.ui.editor.collapsed ? "⮜" : "⮞";
				dockBtn.title = config.ui.editor.collapsed ? "展开右侧面板" : "折叠隐藏右侧面板";
			}
		}

		let dockBtn = doc.getElementById("editorDock");
		if (!dockBtn) {
			dockBtn = doc.createElement("button");
			dockBtn.id = "editorDock";
			dockBtn.type = "button";
			doc.body.appendChild(dockBtn);
		}
		dockBtn.addEventListener("click", (ev) => {
			ev.preventDefault();
			setCollapsed(!config.ui.editor.collapsed);
		});

		const collapseBtn = doc.createElement("button");
		collapseBtn.type = "button";
		collapseBtn.className = "reset";
		headerRight.appendChild(collapseBtn);
		collapseBtn.addEventListener("click", (ev) => {
			ev.preventDefault();
			ev.stopPropagation();
			setCollapsed(!config.ui.editor.collapsed);
		});

		// 初始化折叠状态
		setCollapsed(!!config.ui.editor.collapsed);

		function getOpen(key) {
			if (!key) return false;
			const v = config.ui && config.ui.editor && config.ui.editor.open && config.ui.editor.open[key];
			return v === true; // 默认全收起
		}

		function setOpen(key, isOpen) {
			if (!key) return;
			config.ui.editor.open[key] = !!isOpen;
			try {
				window.AYE48 && window.AYE48.ConfigStore && window.AYE48.ConfigStore.markDirty("details");
			} catch {
				// ignore
			}
		}

		const bindings = [];

		function _clone(v) {
			if (Array.isArray(v)) return v.map(_clone);
			if (v && typeof v === "object") {
				const out = {};
				for (const k of Object.keys(v)) out[k] = _clone(v[k]);
				return out;
			}
			return v;
		}

		function _matchesPrefix(path, prefix) {
			if (!prefix || prefix.length === 0) return true;
			if (!path || path.length < prefix.length) return false;
			for (let i = 0; i < prefix.length; i++) {
				if (path[i] !== prefix[i]) return false;
			}
			return true;
		}

		function refreshBindings(prefix) {
			for (const b of bindings) {
				if (!_matchesPrefix(b.path, prefix)) continue;
				try {
					b.refresh();
				} catch {
					// ignore
				}
			}
		}

		function resetToDefault(paths) {
			const defaults = (window.AYE48 && window.AYE48.DefaultConfig) || null;
			if (!defaults) return;

			function normalizePaths(p) {
				// 支持两种写法：
				// 1) 单路径：['render','engine']
				// 2) 多路径：[[...],[...]]
				if (!p) return [];
				if (!Array.isArray(p)) return [p];
				if (p.length === 0) return [];
				return Array.isArray(p[0]) ? p : [p];
			}

			const list = normalizePaths(paths);
			for (const p of list) {
				const defVal = _getByPath(defaults, p);
				if (defVal === undefined) continue;
				_setByPath(config, p, _clone(defVal));
			}
			try {
				window.AYE48 && window.AYE48.ConfigStore && window.AYE48.ConfigStore.markDirty("reset");
			} catch {
				// ignore
			}
			refreshBindings([]);
		}

		function createHslPicker(anchorEl, initialRgb01, onChange) {
			const overlay = doc.createElement("div");
			overlay.className = "colorPickerOverlay";
			const panel = doc.createElement("div");
			panel.className = "colorPicker";
			overlay.appendChild(panel);

			const header = doc.createElement("div");
			header.className = "cpHeader";
			header.innerHTML = `<strong>拾色器(HSL)</strong>`;
			const closeBtn = doc.createElement("button");
			closeBtn.type = "button";
			closeBtn.className = "cpClose";
			closeBtn.title = "关闭";
			closeBtn.textContent = "✕";
			header.appendChild(closeBtn);
			panel.appendChild(header);

			const body = doc.createElement("div");
			body.className = "cpBody";
			panel.appendChild(body);

			const canvas = doc.createElement("canvas");
			canvas.width = 220;
			canvas.height = 140;
			canvas.className = "cpCanvas";
			body.appendChild(canvas);

			const right = doc.createElement("div");
			right.className = "cpRight";
			body.appendChild(right);

			const preview = doc.createElement("div");
			preview.className = "cpPreview";
			right.appendChild(preview);

			const lRow = doc.createElement("div");
			lRow.className = "row";
			lRow.innerHTML = `<label>明度(L)</label>`;
			const lInput = doc.createElement("input");
			lInput.type = "range";
			lInput.min = "0";
			lInput.max = "1";
			lInput.step = "0.01";
			lRow.appendChild(lInput);
			right.appendChild(lRow);

			const aRow = doc.createElement("div");
			aRow.className = "row";
			aRow.innerHTML = `<label>透明度(A)</label>`;
			const aInput = doc.createElement("input");
			aInput.type = "range";
			aInput.min = "0";
			aInput.max = "1";
			aInput.step = "0.01";
			aRow.appendChild(aInput);
			right.appendChild(aRow);

			const hexRow = doc.createElement("div");
			hexRow.className = "row";
			hexRow.innerHTML = `<label>HEX</label>`;
			const hexInput = doc.createElement("input");
			hexInput.type = "text";
			hexInput.placeholder = "#RRGGBB";
			hexInput.className = "cpHex";
			hexRow.appendChild(hexInput);
			right.appendChild(hexRow);

			let hsl = _rgbToHsl01(initialRgb01.r, initialRgb01.g, initialRgb01.b);
			lInput.value = String(_clamp01(hsl.l));
			aInput.value = String(_clamp01(_getByPath(config, ["environment", "backgroundAlpha"]) ?? 1.0));

			function draw() {
				const ctx = canvas.getContext("2d", { willReadFrequently: true });
				const w = canvas.width;
				const h = canvas.height;
				const img = ctx.createImageData(w, h);
				const l = Number(lInput.value);
				let p = 0;
				for (let y = 0; y < h; y++) {
					const s = 1 - y / (h - 1);
					for (let x = 0; x < w; x++) {
						const hue = (x / (w - 1)) * 360;
						const rgb = _hslToRgb01(hue, s, l);
						img.data[p++] = Math.round(rgb.r * 255);
						img.data[p++] = Math.round(rgb.g * 255);
						img.data[p++] = Math.round(rgb.b * 255);
						img.data[p++] = 255;
					}
				}
				ctx.putImageData(img, 0, 0);
			}

			function emit() {
				const l = Number(lInput.value);
				const rgb = _hslToRgb01(hsl.h, hsl.s, l);
				const a = Number(aInput.value);
				preview.style.background = `rgba(${Math.round(rgb.r * 255)}, ${Math.round(rgb.g * 255)}, ${Math.round(
					rgb.b * 255
				)}, ${_clamp01(a)})`;
				hexInput.value = _rgb01ToHex(rgb.r, rgb.g, rgb.b);
				onChange({ ...rgb, a: _clamp01(a) });
			}

			function pickFromMouse(ev) {
				const rect = canvas.getBoundingClientRect();
				const x = Math.max(0, Math.min(rect.width, ev.clientX - rect.left));
				const y = Math.max(0, Math.min(rect.height, ev.clientY - rect.top));
				hsl.h = (x / rect.width) * 360;
				hsl.s = 1 - y / rect.height;
				emit();
			}

			let dragging = false;
			canvas.addEventListener("mousedown", (ev) => {
				dragging = true;
				pickFromMouse(ev);
			});
			doc.addEventListener("mousemove", (ev) => {
				if (!dragging) return;
				pickFromMouse(ev);
			});
			doc.addEventListener("mouseup", () => {
				dragging = false;
			});

			lInput.addEventListener("input", () => {
				draw();
				emit();
			});
			aInput.addEventListener("input", emit);
			hexInput.addEventListener("change", () => {
				const rgb = _hexToRgb01(hexInput.value);
				if (!rgb) return;
				hsl = _rgbToHsl01(rgb.r, rgb.g, rgb.b);
				lInput.value = String(_clamp01(hsl.l));
				draw();
				emit();
			});

			function close() {
				try {
					overlay.remove();
				} catch {
					// ignore
				}
			}
			closeBtn.addEventListener("click", (ev) => {
				ev.preventDefault();
				close();
			});
			overlay.addEventListener("click", (ev) => {
				if (ev.target === overlay) close();
			});

			// 定位到 anchor 附近
			const ar = anchorEl.getBoundingClientRect();
			panel.style.left = `${Math.min(window.innerWidth - 20, Math.max(12, ar.left - 260))}px`;
			panel.style.top = `${Math.min(window.innerHeight - 20, Math.max(12, ar.top + 24))}px`;

			doc.body.appendChild(overlay);
			draw();
			emit();
			return { close };
		}

		function section(title, resetPaths, key) {
			const details = doc.createElement("details");
			details.open = getOpen(key);
			const summary = doc.createElement("summary");
			const titleSpan = doc.createElement("span");
			titleSpan.textContent = title;
			summary.appendChild(titleSpan);
			if (resetPaths) {
				const btn = doc.createElement("button");
				btn.type = "button";
				btn.className = "reset";
				btn.textContent = "⟲";
				btn.title = "恢复默认";
				btn.setAttribute("aria-label", "恢复默认");
				btn.addEventListener("click", (ev) => {
					ev.preventDefault();
					ev.stopPropagation();
					resetToDefault(resetPaths);
				});
				summary.appendChild(btn);
			}
			details.appendChild(summary);
			details.addEventListener("toggle", () => setOpen(key, details.open));
			rootEl.appendChild(details);
			return details;
		}

		function subtree(parent, title, resetPaths, key) {
			const details = doc.createElement("details");
			details.open = getOpen(key);
			const summary = doc.createElement("summary");
			const titleSpan = doc.createElement("span");
			titleSpan.textContent = title;
			summary.appendChild(titleSpan);
			if (resetPaths) {
				const btn = doc.createElement("button");
				btn.type = "button";
				btn.className = "reset";
				btn.textContent = "⟲";
				btn.title = "恢复默认";
				btn.setAttribute("aria-label", "恢复默认");
				btn.addEventListener("click", (ev) => {
					ev.preventDefault();
					ev.stopPropagation();
					resetToDefault(resetPaths);
				});
				summary.appendChild(btn);
			}
			details.appendChild(summary);
			details.addEventListener("toggle", () => setOpen(key, details.open));
			parent.appendChild(details);
			return details;
		}

		function bindSlider(parent, label, path, min, max, step, digits, extraOnInput) {
			const cur = _getByPath(config, path);
			const value = typeof cur === "number" ? cur : Number(min);

			const { row, input, updateLabel } = _makeSliderRow(doc, {
				label,
				min,
				max,
				step,
				value,
				digits,
				onInput: (v) => {
					_setByPath(config, path, v);
					try {
						window.AYE48 && window.AYE48.ConfigStore && window.AYE48.ConfigStore.markDirty("slider");
					} catch {
						// ignore
					}
					extraOnInput && extraOnInput(v);
				},
			});
			parent.appendChild(row);
			bindings.push({
				path,
				type: "slider",
				refresh: () => {
					const v = _getByPath(config, path);
					if (typeof v === "number") input.value = String(v);
					updateLabel();
				},
			});
			return input;
		}

		function bindSelect(parent, label, path, items, extraOnChange) {
			const cur = _getByPath(config, path);
			const value = cur != null ? cur : items[0] && items[0].value;

			const { row, select } = _makeSelectRow(doc, {
				label,
				items,
				value,
				onChange: (v) => {
					// 如果原来是数字，则尝试转成数字
					const prev = _getByPath(config, path);
					let out = v;
					if (typeof prev === "number") {
						const n = Number(v);
						out = Number.isNaN(n) ? prev : n;
					}
					_setByPath(config, path, out);
					try {
						window.AYE48 && window.AYE48.ConfigStore && window.AYE48.ConfigStore.markDirty("select");
					} catch {
						// ignore
					}
					extraOnChange && extraOnChange(out);
				},
			});
			parent.appendChild(row);
			bindings.push({
				path,
				type: "select",
				refresh: () => {
					const v = _getByPath(config, path);
					if (v == null) return;
					select.value = String(v);
				},
			});
			return select;
		}

		function bindToggle(parent, label, path, extraOnChange) {
			const cur = _getByPath(config, path);
			const value = !!cur;
			const { row, input } = _makeToggleRow(doc, {
				label,
				value,
				onChange: (v) => {
					_setByPath(config, path, !!v);
					try {
						window.AYE48 && window.AYE48.ConfigStore && window.AYE48.ConfigStore.markDirty("toggle");
					} catch {
						// ignore
					}
					extraOnChange && extraOnChange(!!v);
				},
			});
			parent.appendChild(row);
			bindings.push({
				path,
				type: "toggle",
				refresh: () => {
					const v = _getByPath(config, path);
					input.checked = !!v;
				},
			});
			return input;
		}

		// ===== 先渲染“引擎设置”（要求在第一行） =====
		const render = section("渲染引擎 (Babylon)", ["render"], "render");
		const eng = subtree(render, "Engine", ["render", "engine"], "render.engine");
		bindSlider(
			eng,
			"分辨率缩放(hardwareScaling)",
			["render", "engine", "hardwareScalingLevel"],
			0.5,
			2.0,
			0.05,
			2
		);

		const dp = subtree(render, "DefaultRenderingPipeline", ["render", "defaultPipeline"], "render.defaultPipeline");
		bindToggle(dp, "启用", ["render", "defaultPipeline", "enabled"]);
		bindToggle(dp, "FXAA", ["render", "defaultPipeline", "fxaaEnabled"]);

		const bloom = subtree(
			dp,
			"Bloom",
			[
				["render", "defaultPipeline", "bloomEnabled"],
				["render", "defaultPipeline", "bloomThreshold"],
				["render", "defaultPipeline", "bloomWeight"],
				["render", "defaultPipeline", "bloomKernel"],
				["render", "defaultPipeline", "bloomScale"],
			],
			"render.defaultPipeline.bloom"
		);
		bindToggle(bloom, "启用", ["render", "defaultPipeline", "bloomEnabled"]);
		bindSlider(bloom, "阈值(threshold)", ["render", "defaultPipeline", "bloomThreshold"], 0, 2, 0.01, 2);
		bindSlider(bloom, "权重(weight)", ["render", "defaultPipeline", "bloomWeight"], 0, 1, 0.01, 2);
		bindSlider(bloom, "核(kernel)", ["render", "defaultPipeline", "bloomKernel"], 1, 256, 1, 0);
		bindSlider(bloom, "缩放(scale)", ["render", "defaultPipeline", "bloomScale"], 0.1, 1.0, 0.05, 2);

		const sharpen = subtree(
			dp,
			"Sharpen",
			[
				["render", "defaultPipeline", "sharpenEnabled"],
				["render", "defaultPipeline", "sharpenEdgeAmount"],
				["render", "defaultPipeline", "sharpenColorAmount"],
			],
			"render.defaultPipeline.sharpen"
		);
		bindToggle(sharpen, "启用", ["render", "defaultPipeline", "sharpenEnabled"]);
		bindSlider(sharpen, "边缘(edgeAmount)", ["render", "defaultPipeline", "sharpenEdgeAmount"], 0, 2, 0.01, 2);
		bindSlider(sharpen, "颜色(colorAmount)", ["render", "defaultPipeline", "sharpenColorAmount"], 0, 2, 0.01, 2);

		const ca = subtree(
			dp,
			"Chromatic Aberration",
			[
				["render", "defaultPipeline", "chromaticAberrationEnabled"],
				["render", "defaultPipeline", "chromaticAberrationAmount"],
			],
			"render.defaultPipeline.chromaticAberration"
		);
		bindToggle(ca, "启用", ["render", "defaultPipeline", "chromaticAberrationEnabled"]);
		bindSlider(ca, "强度(amount)", ["render", "defaultPipeline", "chromaticAberrationAmount"], 0, 200, 1, 0);

		const grain = subtree(
			dp,
			"Grain",
			[["render", "defaultPipeline", "grainEnabled"], ["render", "defaultPipeline", "grainIntensity"]],
			"render.defaultPipeline.grain"
		);
		bindToggle(grain, "启用", ["render", "defaultPipeline", "grainEnabled"]);
		bindSlider(grain, "强度(intensity)", ["render", "defaultPipeline", "grainIntensity"], 0, 200, 1, 0);

		const dof = subtree(
			dp,
			"Depth Of Field",
			[
				["render", "defaultPipeline", "depthOfFieldEnabled"],
				["render", "defaultPipeline", "dofFocusDistance"],
				["render", "defaultPipeline", "dofFStop"],
				["render", "defaultPipeline", "dofFocalLength"],
				["render", "defaultPipeline", "dofLensSize"],
			],
			"render.defaultPipeline.dof"
		);
		bindToggle(dof, "启用", ["render", "defaultPipeline", "depthOfFieldEnabled"]);
		bindSlider(dof, "对焦距离(focusDistance)", ["render", "defaultPipeline", "dofFocusDistance"], 1, 2000, 1, 0);
		bindSlider(dof, "光圈(fStop)", ["render", "defaultPipeline", "dofFStop"], 0.5, 32, 0.1, 1);
		bindSlider(dof, "焦距(focalLength)", ["render", "defaultPipeline", "dofFocalLength"], 1, 200, 1, 0);
		bindSlider(dof, "镜头尺寸(lensSize)", ["render", "defaultPipeline", "dofLensSize"], 1, 200, 1, 0);

		const ssao = subtree(render, "SSAO2RenderingPipeline", ["render", "ssao2"], "render.ssao2");
		bindToggle(ssao, "启用", ["render", "ssao2", "enabled"]);
		bindSlider(ssao, "分辨率比例(ratio)", ["render", "ssao2", "ratio"], 0.1, 1.0, 0.05, 2);
		bindSlider(ssao, "半径(radius)", ["render", "ssao2", "radius"], 0.1, 10.0, 0.1, 1);
		bindSlider(ssao, "强度(totalStrength)", ["render", "ssao2", "totalStrength"], 0, 5.0, 0.05, 2);
		bindSlider(ssao, "base", ["render", "ssao2", "base"], 0, 2.0, 0.01, 2);
		bindSlider(ssao, "area", ["render", "ssao2", "area"], 0.0, 0.05, 0.0005, 4);
		bindSlider(ssao, "fallOff", ["render", "ssao2", "fallOff"], 0.0, 0.01, 0.000001, 6);

		// Tree: Blueprints
		const bp = section("蓝图 (Blueprints)", null, "blueprints");

		const playerBP = subtree(bp, "PlayerControllerBP", [["movement"], ["camera"]], "blueprints.player");
		bindSlider(
			playerBP,
			"移动速度",
			["movement", "moveSpeed"],
			0,
			30,
			0.1,
			1,
			(v) => {
				if (hud && hud.els && hud.els.moveSpeed) {
					hud.els.moveSpeed.value = String(v);
					hud.els.moveSpeed.dispatchEvent(new WinEvent("input"));
				}
			}
		);
		bindSlider(
			playerBP,
			"鼠标旋转速率",
			["movement", "mouseTurn"],
			0,
			0.03,
			0.0005,
			4,
			(v) => {
				if (hud && hud.els && hud.els.mouseTurn) {
					hud.els.mouseTurn.value = String(v);
					hud.els.mouseTurn.dispatchEvent(new WinEvent("input"));
				}
			}
		);
		bindSlider(playerBP, "滚轮推进步长", ["movement", "wheelStep"], 0, 3, 0.05, 2);
		bindSlider(playerBP, "跳跃初速度", ["movement", "jumpVel"], 0, 12, 0.1, 1);
		bindSlider(playerBP, "重力", ["movement", "gravity"], 0, 30, 0.2, 1);

		const propBP = subtree(bp, "PropActorBP (通用物件)", ["prop"], "blueprints.prop");
		bindSlider(propBP, "基础高度因子", ["prop", "baseHeightFactor"], 0, 1.5, 0.01, 2);
		bindSlider(propBP, "自转速度(rad/s)", ["prop", "rotationSpeed"], 0, 3, 0.01, 2);
		bindSlider(propBP, "浮动幅度因子", ["prop", "bobAmplitudeFactor"], 0, 0.5, 0.005, 3);
		bindSlider(propBP, "浮动频率(Hz)", ["prop", "bobFrequency"], 0, 3, 0.05, 2);

		// Tree: Actors
		const actors = section("Actors", null, "actors");
		const ground = subtree(actors, "GroundActor", ["ground"], "actors.ground");
		bindSlider(ground, "格距(gridStep)", ["ground", "gridRatio"], 0.1, 10, 0.1, 2);
		bindSlider(ground, "主线间隔(每N格)", ["ground", "majorUnitFrequency"], 1, 50, 1, 0);
		bindSlider(ground, "网格跟随步长", ["ground", "followStep"], 1, 50, 1, 0);
		bindSlider(ground, "子线线宽", ["ground", "minorLineWidth"], 0.002, 0.2, 0.001, 3);
		bindSlider(ground, "主线线宽", ["ground", "majorLineWidth"], 0.002, 0.25, 0.001, 3);
		bindSlider(ground, "子线亮度(alpha)", ["ground", "minorAlpha"], 0, 0.4, 0.005, 3);
		bindSlider(ground, "主线亮度(alpha)", ["ground", "majorAlpha"], 0, 0.6, 0.005, 3);
		bindSlider(ground, "渐隐开始距离", ["ground", "fadeStart"], 0, 200, 1, 0);
		bindSlider(ground, "渐隐结束距离", ["ground", "fadeEnd"], 1, 500, 1, 0);

		const camera = subtree(actors, "CameraActor", ["camera"], "actors.camera");
		bindSlider(camera, "俯仰最小", ["camera", "pitchMin"], -1.56, 0, 0.01, 2);
		bindSlider(camera, "俯仰最大", ["camera", "pitchMax"], 0, 1.56, 0.01, 2);

		// Tree: Environment / Skybox
		const env = section("环境 / Skybox", [
			["environment"],
			["environmentTextureUrl"],
			["environmentFallbackUrl"],
			["environmentExrUrl"],
			["environmentExrPrefilterSize"],
		], "environment");
		bindSelect(
			env,
			"来源",
			["environment", "sourceMode"],
			[
				{ value: "auto", text: "自动(env→exr→fallback)" },
				{ value: "env", text: "优先本地 .env" },
				{ value: "exr", text: "强制本地 EXR(慢)" },
				{ value: "fallback", text: "强制线上兜底" },
				{ value: "none", text: "无/空白(关闭 env/skybox)" },
			]
		);

		const bg = subtree(env, "背景", ["environment"], "environment.background");
		bindSelect(
			bg,
			"背景模式",
			["environment", "backgroundMode"],
			[
				{ value: "skybox", text: "Skybox" },
				{ value: "solid", text: "纯色" },
			]
		);
		// 颜色拾取（HSL）+ RGB(A)
		{
			const row = doc.createElement("div");
			row.className = "row";
			const label = doc.createElement("label");
			label.textContent = "背景色";
			const swatch = doc.createElement("button");
			swatch.type = "button";
			swatch.className = "swatch";
			swatch.title = "点击打开拾色器";
			function refreshSwatch() {
				const c = _getByPath(config, ["environment", "backgroundColor"]) || [0, 0, 0];
				const a = _getByPath(config, ["environment", "backgroundAlpha"]) ?? 1.0;
				swatch.style.background = `rgba(${Math.round(_clamp01(c[0]) * 255)}, ${Math.round(
					_clamp01(c[1]) * 255
				)}, ${Math.round(_clamp01(c[2]) * 255)}, ${_clamp01(a)})`;
			}
			swatch.addEventListener("click", () => {
				try {
					_setByPath(config, ["environment", "backgroundMode"], "solid");
					window.AYE48 && window.AYE48.ConfigStore && window.AYE48.ConfigStore.markDirty("bgMode");
				} catch {
					// ignore
				}
				const c = _getByPath(config, ["environment", "backgroundColor"]) || [0.04, 0.06, 0.1];
				const init = { r: _clamp01(c[0]), g: _clamp01(c[1]), b: _clamp01(c[2]) };
				createHslPicker(swatch, init, (out) => {
					_setByPath(config, ["environment", "backgroundColor"], [_clamp01(out.r), _clamp01(out.g), _clamp01(out.b)]);
					_setByPath(config, ["environment", "backgroundAlpha"], _clamp01(out.a));
					try {
						window.AYE48 && window.AYE48.ConfigStore && window.AYE48.ConfigStore.markDirty("bgColor");
					} catch {
						// ignore
					}
					refreshSwatch();
					refreshBindings([]);
				});
			});
			row.appendChild(label);
			row.appendChild(swatch);
			bg.appendChild(row);
			bindings.push({ path: ["environment", "backgroundColor"], type: "swatch", refresh: refreshSwatch });
			bindings.push({ path: ["environment", "backgroundAlpha"], type: "swatchA", refresh: refreshSwatch });
			refreshSwatch();
		}
		const forceSolid = () => {
			try {
				if (_getByPath(config, ["environment", "backgroundMode"]) !== "solid") {
					_setByPath(config, ["environment", "backgroundMode"], "solid");
					window.AYE48 && window.AYE48.ConfigStore && window.AYE48.ConfigStore.markDirty("bgMode");
				}
			} catch {
				// ignore
			}
		};
		bindSlider(bg, "背景 R", ["environment", "backgroundColor", 0], 0, 1, 0.01, 2, forceSolid);
		bindSlider(bg, "背景 G", ["environment", "backgroundColor", 1], 0, 1, 0.01, 2, forceSolid);
		bindSlider(bg, "背景 B", ["environment", "backgroundColor", 2], 0, 1, 0.01, 2, forceSolid);
		bindSlider(bg, "背景 Alpha", ["environment", "backgroundAlpha"], 0, 1, 0.01, 2, forceSolid);

		bindSelect(
			env,
			"清晰度(.env 分辨率)",
			["environment", "envResolution"],
			[
				{ value: 128, text: "128" },
				{ value: 256, text: "256" },
				{ value: 512, text: "512" },
			],
			(v) => {
				// 约定文件命名：AboveClouds_08_{size}_webp.env
				try {
					const size = Number(v);
					const url = new URL(`assets/env/AboveClouds_08_${size}_webp.env`, window.location.href).toString();
					config.environmentTextureUrl = url;
					try {
						window.AYE48 && window.AYE48.ConfigStore && window.AYE48.ConfigStore.markDirty("envResolution");
					} catch {
						// ignore
					}
				} catch {
					// ignore
				}
			}
		);

		bindSlider(env, "环境亮度", ["environment", "intensity"], 0, 3, 0.01, 2);
		bindSlider(env, "曝光", ["environment", "exposure"], 0.1, 2.5, 0.01, 2);
		bindSlider(env, "对比度", ["environment", "contrast"], 0.1, 2.5, 0.01, 2);
		bindSlider(env, "旋转Y(°)", ["environment", "rotationYDeg"], -180, 180, 1, 0);
		bindSlider(env, "Skybox 模糊", ["environment", "skyboxBlur"], 0, 1, 0.01, 2);
		bindSlider(env, "EXR 预过滤尺寸", ["environment", "exrPrefilterSize"], 64, 1024, 16, 0, (v) => {
			config.environmentExrPrefilterSize = Number(v);
			try {
				window.AYE48 && window.AYE48.ConfigStore && window.AYE48.ConfigStore.markDirty("exrPrefilter");
			} catch {
				// ignore
			}
		});

		return {
			rootEl,
		};
	}

	window.AYE48.UI.mountEditorPanel = mountEditorPanel;
})();
