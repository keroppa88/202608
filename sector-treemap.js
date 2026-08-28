(function () {
  "use strict";
  if (typeof document === "undefined") return;

  const SEP = "\u0001";
  let mode = "table";
  let heatData = null;
  let resizeTimer = 0;

  function esc(v) {
    return String(v == null ? "" : v)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function fmt(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "-";
    return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
  }

  function fmtCap(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "-";
    if (n >= 10) return `${n.toFixed(1)}兆`;
    return `${n.toFixed(2)}兆`;
  }

  function heatColor(v) {
    if (window.SectorHeatmapView && typeof window.SectorHeatmapView.heatColor === "function") {
      return window.SectorHeatmapView.heatColor(v);
    }
    const n0 = Number(v);
    if (!Number.isFinite(n0)) return "rgb(55,55,55)";
    const n = Math.max(-10, Math.min(10, n0));
    const blue = [0, 65, 180];
    const green = [0, 128, 64];
    const red = [190, 35, 45];
    const from = n <= 0 ? blue : green;
    const to = n <= 0 ? green : red;
    const t = n <= 0 ? (n + 10) / 10 : n / 10;
    const rgb = from.map((x, i) => Math.round(x + (to[i] - x) * t));
    return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
  }

  function displayIndustryName(row) {
    const name = String(row && row.name || "");
    const sector = String(row && row.sector || "");
    if (name === "B2B" && sector === "国内情報通信") return "情報通信B2B";
    if (name === "B2C" && sector === "国内情報通信") return "情報通信B2C";
    return name;
  }

  function totalValue(items) {
    return items.reduce((sum, item) => sum + Math.max(0, Number(item.value) || 0), 0);
  }

  // 面積比を正確に保つ二分割型ツリーマップ。
  // 長辺方向に、時価総額がほぼ半分ずつになる位置で再帰分割する。
  function layoutTreemap(items, x, y, w, h, out) {
    if (!items.length || w <= 0 || h <= 0) return;
    if (items.length === 1) {
      out.push({ item:items[0], x, y, w, h });
      return;
    }

    const total = totalValue(items);
    if (!(total > 0)) {
      const equal = items.map((item) => ({ ...item, value:1 }));
      layoutTreemap(equal, x, y, w, h, out);
      return;
    }

    let bestIndex = 1;
    let running = 0;
    let bestDiff = Infinity;
    for (let i = 1; i < items.length; i++) {
      running += Math.max(0, Number(items[i - 1].value) || 0);
      const diff = Math.abs(total / 2 - running);
      if (diff < bestDiff) {
        bestDiff = diff;
        bestIndex = i;
      }
    }

    const a = items.slice(0, bestIndex);
    const b = items.slice(bestIndex);
    const aValue = totalValue(a);
    const ratio = total > 0 ? aValue / total : a.length / items.length;

    if (w >= h) {
      const aw = w * ratio;
      layoutTreemap(a, x, y, aw, h, out);
      layoutTreemap(b, x + aw, y, w - aw, h, out);
    } else {
      const ah = h * ratio;
      layoutTreemap(a, x, y, w, ah, out);
      layoutTreemap(b, x, y + ah, w, h - ah, out);
    }
  }

  function buildSectorGroups(data) {
    const groups = new Map();
    (Array.isArray(data && data.industry) ? data.industry : []).forEach((row) => {
      const cap = Number(row && row.marketCapTrillion);
      if (!(cap > 0)) return;
      const major = String(row.major || "");
      const sector = String(row.sector || "");
      const key = `${major}${SEP}${sector}`;
      if (!groups.has(key)) {
        groups.set(key, { key, major, name:sector, value:0, items:[] });
      }
      const group = groups.get(key);
      group.value += cap;
      group.items.push({ row, value:cap });
    });

    return [...groups.values()]
      .map((group) => ({
        ...group,
        items:group.items.sort((a, b) => b.value - a.value)
      }))
      .sort((a, b) => b.value - a.value);
  }

  function tileHtml(entry, rect) {
    const row = entry.row;
    const name = displayIndustryName(row);
    const count = Number(row && row.count) || 0;
    const cap = Number(row && row.marketCapTrillion);
    const w = Math.max(0, rect.w - 2);
    const h = Math.max(0, rect.h - 2);
    const area = w * h;
    const compact = w < 92 || h < 48 || area < 6500;
    const tiny = w < 54 || h < 28 || area < 2400;

    let inner = `<span class="sector-treemap-name">${esc(name)}</span>` +
      `<span class="sector-heat-change">${fmt(row && row.change)}</span>`;
    if (!compact) {
      inner += `<span class="sector-treemap-cap">${fmtCap(cap)} / ${count}銘柄</span>`;
    }

    return `<div class="sector-heat-node sector-treemap-tile${compact ? " compact" : ""}${tiny ? " tiny" : ""}" ` +
      `style="left:${(rect.x + 1).toFixed(2)}px;top:${(rect.y + 1).toFixed(2)}px;` +
      `width:${w.toFixed(2)}px;height:${h.toFixed(2)}px;background:${heatColor(row && row.change)}" ` +
      `title="${esc(name)} / ${esc(fmt(row && row.change))} / 時価総額 ${esc(fmtCap(cap))} / ${count}銘柄 / ${esc(row.sector || "")} / ${esc(row.major || "")}">` +
      inner + `</div>`;
  }

  function renderTreemap(data) {
    heatData = data;
    const page = document.getElementById("sector-page");
    const body = document.getElementById("sector-body");
    if (!page || !body || mode !== "treemap") return;

    const groups = buildSectorGroups(data);
    const width = Math.max(1120, (body.clientWidth || page.clientWidth || 1200) - 8);
    const height = Math.max(650, Math.min(860, Math.round(width * 0.60)));
    const groupRects = [];
    layoutTreemap(groups, 0, 0, width, height, groupRects);

    const sectorsHtml = groupRects.map((groupRect) => {
      const group = groupRect.item;
      const x = groupRect.x;
      const y = groupRect.y;
      const w = Math.max(0, groupRect.w);
      const h = Math.max(0, groupRect.h);
      const inner = [];
      layoutTreemap(group.items, x + 2, y + 2, Math.max(0, w - 4), Math.max(0, h - 4), inner);
      const tiles = inner.map((entry) => tileHtml(entry.item, entry)).join("");
      const showLabel = w > 90 && h > 34;
      const label = showLabel
        ? `<div class="sector-treemap-sector-label" style="left:${(x + 4).toFixed(2)}px;top:${(y + 4).toFixed(2)}px;max-width:${Math.max(40, w - 8).toFixed(2)}px" ` +
          `title="${esc(group.name)} / ${esc(group.major)} / 時価総額 ${esc(fmtCap(group.value))}">${esc(group.name)}</div>`
        : "";
      return `<div class="sector-treemap-sector-frame" style="left:${x.toFixed(2)}px;top:${y.toFixed(2)}px;width:${w.toFixed(2)}px;height:${h.toFixed(2)}px" ` +
        `title="${esc(group.name)} / ${esc(group.major)} / 時価総額 ${esc(fmtCap(group.value))}"></div>` + tiles + label;
    }).join("");

    body.innerHTML = `<div class="sector-heatmap sector-treemap-view">` +
      `<div class="sector-heatmap-head">` +
      `<span class="sector-heatmap-title">日本株 業種別時価総額ヒートマップ</span>` +
      `<span class="sector-heatmap-meta">${esc(data.date || "-")}</span>` +
      `<span class="sector-heatmap-meta">面積＝業種合計時価総額</span>` +
      `<span class="sector-heatmap-meta">色＝当日騰落率</span>` +
      `<span class="sector-heatmap-legend"><b>-10%</b><span class="sector-heatmap-gradient"></span><b>0%</b><b>+10%</b></span>` +
      `</div>` +
      `<div class="sector-treemap-canvas" style="width:${width}px;height:${height}px">${sectorsHtml}</div>` +
      `<div class="sector-treemap-note">枠＝セクター / マス＝業種。時価総額未取得分は面積に含めない。</div>` +
      `</div>`;
  }

  async function fetchHeatData() {
    if (heatData) return heatData;
    const res = await fetch(`data/sector_today.json?t=${Date.now()}`, { cache:"no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    heatData = await res.json();
    return heatData;
  }

  function updateToggleHint(toggle) {
    if (!toggle) return;
    if (mode === "table") toggle.title = "表切替：業種別時価総額マップを表示";
    else if (mode === "treemap") toggle.title = "表切替：階層ヒートマップを表示";
    else toggle.title = "表切替：表へ戻る";
  }

  async function showTreemap() {
    const body = document.getElementById("sector-body");
    const toggle = document.getElementById("sector-view-toggle");
    if (!body || !toggle) return;
    mode = "treemap";
    toggle.setAttribute("aria-pressed", "true");
    updateToggleHint(toggle);
    body.innerHTML = '<div class="sector-error">業種別時価総額マップ読み込み中…</div>';
    try {
      const data = await fetchHeatData();
      if (mode === "treemap") renderTreemap(data);
    } catch (err) {
      if (mode === "treemap") {
        body.innerHTML = `<div class="sector-error">業種別時価総額マップを読み込めませんでした。\n${esc(err && err.message ? err.message : err)}</div>`;
      }
    }
  }

  function showHierarchy() {
    mode = "hierarchy";
    const toggle = document.getElementById("sector-view-toggle");
    updateToggleHint(toggle);
    if (window.SectorHeatmapView && typeof window.SectorHeatmapView.show === "function") {
      window.SectorHeatmapView.show();
    }
  }

  function showTable() {
    mode = "table";
    const toggle = document.getElementById("sector-view-toggle");
    updateToggleHint(toggle);
    if (window.SectorHeatmapView && typeof window.SectorHeatmapView.table === "function") {
      window.SectorHeatmapView.table();
    } else if (window.SectorPerformancePage && typeof window.SectorPerformancePage.load === "function") {
      toggle?.setAttribute("aria-pressed", "false");
      window.SectorPerformancePage.load();
    }
  }

  function installStyle() {
    if (document.getElementById("sector-treemap-style")) return;
    const style = document.createElement("style");
    style.id = "sector-treemap-style";
    style.textContent = `
      #sector-page .sector-treemap-view { width:max-content; min-width:100%; }
      #sector-page .sector-treemap-canvas {
        position:relative; overflow:hidden; background:var(--bg);
        border:1px solid var(--line); box-sizing:border-box;
      }
      #sector-page .sector-treemap-sector-frame {
        position:absolute; z-index:2; box-sizing:border-box;
        border:2px solid var(--fg2); pointer-events:none;
      }
      #sector-page .sector-treemap-sector-label {
        position:absolute; z-index:4; box-sizing:border-box;
        overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
        padding:2px 5px; background:rgba(0,0,0,.72); color:#fff;
        border:1px solid rgba(255,255,255,.55); font-size:12px; font-weight:bold;
        text-shadow:0 1px 1px #000; pointer-events:none;
      }
      #sector-page .sector-treemap-tile.sector-heat-node {
        position:absolute; z-index:1; box-sizing:border-box;
        min-height:0 !important; display:flex !important;
        flex-direction:column; align-items:center; justify-content:center;
        gap:2px; padding:4px; overflow:hidden;
        border:1px solid rgba(255,255,255,.78);
        line-height:1.08; text-align:center;
      }
      #sector-page .sector-treemap-tile .sector-treemap-name {
        display:block; max-width:100%; overflow:hidden;
        text-overflow:ellipsis; white-space:nowrap;
        font-size:13px; font-weight:bold;
      }
      #sector-page .sector-treemap-tile .sector-heat-change {
        display:block; grid-column:auto; grid-row:auto;
        font-size:14px; font-weight:bold; text-align:center;
      }
      #sector-page .sector-treemap-tile .sector-treemap-cap {
        display:block; max-width:100%; overflow:hidden;
        text-overflow:ellipsis; white-space:nowrap; font-size:10px;
      }
      #sector-page .sector-treemap-tile.compact { padding:2px; gap:1px; }
      #sector-page .sector-treemap-tile.compact .sector-treemap-name { font-size:10px; }
      #sector-page .sector-treemap-tile.compact .sector-heat-change { font-size:10px; }
      #sector-page .sector-treemap-tile.tiny .sector-treemap-name { font-size:8px; }
      #sector-page .sector-treemap-tile.tiny .sector-heat-change { display:none; }
      #sector-page .sector-treemap-note { margin-top:7px; color:var(--fg); font-size:12px; }
      @media (max-width:700px) {
        #sector-page .sector-treemap-sector-label { font-size:10px; padding:1px 3px; }
      }
    `;
    document.head.appendChild(style);
  }

  function init() {
    const page = document.getElementById("sector-page");
    const body = document.getElementById("sector-body");
    const toggle = document.getElementById("sector-view-toggle");
    const themeButton = document.getElementById("sector-theme");
    const backButton = document.getElementById("sector-back");
    if (!page || !body || !toggle || !window.SectorHeatmapView) return false;
    if (toggle.dataset.treemapCycle === "1") return true;

    toggle.dataset.treemapCycle = "1";
    installStyle();
    updateToggleHint(toggle);

    // 既存の表↔階層ヒートマップのクリック処理より先に受け取り、3画面循環に拡張する。
    toggle.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (mode === "table") showTreemap();
      else if (mode === "treemap") showHierarchy();
      else showTable();
    }, true);

    themeButton?.addEventListener("click", () => {
      if (mode !== "treemap" || !heatData) return;
      window.setTimeout(() => {
        if (mode === "treemap") renderTreemap(heatData);
      }, 0);
    });

    backButton?.addEventListener("click", () => {
      mode = "table";
      updateToggleHint(toggle);
    });

    window.addEventListener("resize", () => {
      if (mode !== "treemap" || !heatData) return;
      clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        if (mode === "treemap") renderTreemap(heatData);
      }, 120);
    });

    window.SectorTreemapView = {
      show:showTreemap,
      hierarchy:showHierarchy,
      table:showTable,
      render:renderTreemap
    };
    return true;
  }

  if (!init()) {
    const observer = new MutationObserver(() => {
      if (init()) observer.disconnect();
    });
    observer.observe(document.documentElement, { childList:true, subtree:true });
  }
})();
