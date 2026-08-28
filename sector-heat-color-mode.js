(function () {
  "use strict";
  if (typeof document === "undefined") return;

  const ABSOLUTE_LIMIT = 10;
  const BLUE = [0, 65, 180];
  const GREEN = [0, 128, 64];
  const RED = [190, 35, 45];

  let colorMode = "absolute";
  let relativeLimit = null;
  let relativeLimitPromise = null;
  let paintQueued = false;

  function esc(v) {
    return String(v == null ? "" : v)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function currentLimit() {
    if (colorMode === "relative" && Number.isFinite(relativeLimit) && relativeLimit > 0) {
      return relativeLimit;
    }
    return ABSOLUTE_LIMIT;
  }

  function heatColor(value, limit) {
    const raw = Number(value);
    if (!Number.isFinite(raw)) return "rgb(55,55,55)";
    const edge = Number.isFinite(limit) && limit > 0 ? limit : ABSOLUTE_LIMIT;
    const n = Math.max(-edge, Math.min(edge, raw));
    const from = n <= 0 ? BLUE : GREEN;
    const to = n <= 0 ? GREEN : RED;
    const t = n <= 0 ? (n + edge) / edge : n / edge;
    const rgb = from.map((x, i) => Math.round(x + (to[i] - x) * t));
    return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
  }

  function parseChange(node) {
    const text = node.querySelector(".sector-heat-change")?.textContent || "";
    const value = Number.parseFloat(text.replace("%", "").replace("＋", "+").replace("−", "-"));
    return Number.isFinite(value) ? value : null;
  }

  function fmtEdge(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "-";
    const digits = Math.abs(n - Math.round(n)) < 1e-9 ? 0 : 2;
    return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}%`;
  }

  function updateLegend(limit) {
    const legend = document.querySelector("#sector-page .sector-heatmap-legend");
    if (!legend) return;
    const key = `${colorMode}:${limit.toFixed(6)}`;
    if (legend.dataset.colorModeKey === key) return;
    legend.dataset.colorModeKey = key;
    legend.innerHTML =
      `<span>${esc(fmtEdge(-limit))}</span>` +
      `<span class="sector-heatmap-gradient"></span>` +
      `<span>0%</span>` +
      `<span>${esc(fmtEdge(limit))}</span>`;
    legend.title = colorMode === "absolute"
      ? "絶対値色：-10%～+10%の固定スケール"
      : `相対値色：当日の最大絶対値 ±${limit.toFixed(2)}%`;
  }

  function paint() {
    paintQueued = false;
    const page = document.getElementById("sector-page");
    const toggle = document.getElementById("sector-view-toggle");
    if (!page || !toggle || toggle.getAttribute("aria-pressed") !== "true") return;

    const limit = currentLimit();
    page.querySelectorAll(".sector-heat-node").forEach((node) => {
      const value = parseChange(node);
      if (value == null) return;
      node.style.background = heatColor(value, limit);
    });
    updateLegend(limit);
  }

  function queuePaint() {
    if (paintQueued) return;
    paintQueued = true;
    requestAnimationFrame(paint);
  }

  function computeRelativeLimit(data) {
    let high = -Infinity;
    let low = Infinity;
    ["major", "sector", "industry"].forEach((key) => {
      (Array.isArray(data && data[key]) ? data[key] : []).forEach((row) => {
        const value = Number(row && row.change);
        if (!Number.isFinite(value)) return;
        high = Math.max(high, value);
        low = Math.min(low, value);
      });
    });
    if (!Number.isFinite(high) || !Number.isFinite(low)) return ABSOLUTE_LIMIT;
    const edge = Math.max(Math.abs(high), Math.abs(low));
    return edge > 0 ? edge : 1;
  }

  function loadRelativeLimit() {
    if (relativeLimitPromise) return relativeLimitPromise;
    relativeLimitPromise = fetch(`data/sector_today.json?t=${Date.now()}`, { cache:"no-store" })
      .then((res) => {
        if (!res.ok) throw new Error(`sector_today.json: HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        relativeLimit = computeRelativeLimit(data);
        return relativeLimit;
      })
      .catch((err) => {
        console.warn("相対値色のスケール取得に失敗", err);
        relativeLimit = ABSOLUTE_LIMIT;
        return relativeLimit;
      });
    return relativeLimitPromise;
  }

  function syncButtons() {
    const absolute = document.getElementById("sector-color-absolute");
    const relative = document.getElementById("sector-color-relative");
    if (absolute) absolute.setAttribute("aria-pressed", colorMode === "absolute" ? "true" : "false");
    if (relative) relative.setAttribute("aria-pressed", colorMode === "relative" ? "true" : "false");
  }

  function syncVisibility() {
    const controls = document.getElementById("sector-heat-color-controls");
    const toggle = document.getElementById("sector-view-toggle");
    if (!controls || !toggle) return;
    controls.hidden = toggle.getAttribute("aria-pressed") !== "true";
    if (!controls.hidden) queuePaint();
  }

  async function setColorMode(next) {
    colorMode = next === "relative" ? "relative" : "absolute";
    syncButtons();
    if (colorMode === "relative") await loadRelativeLimit();
    queuePaint();
  }

  function init() {
    const page = document.getElementById("sector-page");
    const body = document.getElementById("sector-body");
    const toggle = document.getElementById("sector-view-toggle");
    if (!page || !body || !toggle) return false;
    if (document.getElementById("sector-heat-color-controls")) return true;

    const style = document.createElement("style");
    style.textContent = `
      #sector-page #sector-heat-color-controls {
        display:inline-flex; align-items:center; gap:4px;
      }
      #sector-page #sector-heat-color-controls[hidden] { display:none !important; }
      #sector-page .sector-color-mode-button[aria-pressed="true"] {
        background:var(--sel-bg); color:var(--sel-fg);
      }
    `;
    document.head.appendChild(style);

    const controls = document.createElement("span");
    controls.id = "sector-heat-color-controls";
    controls.hidden = true;
    controls.innerHTML =
      `<button id="sector-color-absolute" class="sector-color-mode-button" type="button" aria-pressed="true" title="固定 -10%～+10%">絶対値色</button>` +
      `<button id="sector-color-relative" class="sector-color-mode-button" type="button" aria-pressed="false" title="その日の最大絶対値を上下限にする">相対値色</button>`;
    toggle.insertAdjacentElement("afterend", controls);

    document.getElementById("sector-color-absolute").addEventListener("click", () => setColorMode("absolute"));
    document.getElementById("sector-color-relative").addEventListener("click", () => setColorMode("relative"));
    toggle.addEventListener("click", () => setTimeout(syncVisibility, 0));

    new MutationObserver(syncVisibility).observe(toggle, {
      attributes:true,
      attributeFilter:["aria-pressed"]
    });
    new MutationObserver(queuePaint).observe(body, {
      childList:true,
      subtree:true
    });

    syncButtons();
    syncVisibility();
    return true;
  }

  if (!init()) {
    const observer = new MutationObserver(() => {
      if (init()) observer.disconnect();
    });
    observer.observe(document.documentElement, { childList:true, subtree:true });
  }
})();
