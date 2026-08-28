(function () {
  "use strict";
  if (typeof document === "undefined") return;

  const page = document.getElementById("sector-page");
  const body = document.getElementById("sector-body");
  const bar = page && page.querySelector(".bar");
  const themeButton = document.getElementById("sector-theme");
  const backButton = document.getElementById("sector-back");
  if (!page || !body || !bar || document.getElementById("sector-view-toggle")) return;

  const style = document.createElement("style");
  style.textContent = `
    #sector-page #sector-view-toggle[aria-pressed="true"] {
      background:var(--sel-bg); color:var(--sel-fg);
    }
    #sector-page .sector-heatmap {
      width:max-content; min-width:100%;
      padding:4px 0 28px;
      color:var(--fg);
    }
    #sector-page .sector-heatmap-head {
      display:flex; flex-wrap:wrap; align-items:center; gap:8px 18px;
      min-width:980px; margin:0 0 12px;
    }
    #sector-page .sector-heatmap-title {
      font-size:18px; color:var(--fg2);
    }
    #sector-page .sector-heatmap-meta {
      color:var(--fg);
    }
    #sector-page .sector-heatmap-legend {
      display:flex; align-items:center; gap:7px;
      margin-left:auto; color:var(--fg); font-size:12px;
    }
    #sector-page .sector-heatmap-gradient {
      width:190px; height:13px; border:1px solid var(--line);
      background:linear-gradient(90deg, rgb(0,65,180) 0%, rgb(0,128,64) 50%, rgb(190,35,45) 100%);
    }
    #sector-page .sector-tree-columns {
      display:grid;
      grid-template-columns:220px 240px 260px;
      column-gap:84px;
      min-width:1012px; width:max-content;
      padding:0 4px 6px;
      color:var(--fg2); font-weight:bold;
    }
    #sector-page .sector-tree-major {
      display:grid;
      grid-template-columns:220px auto;
      column-gap:42px;
      width:max-content; min-width:1012px;
      margin:0 0 18px; padding:6px 4px 18px;
      border-bottom:1px solid var(--line);
    }
    #sector-page .sector-tree-major-node {
      display:flex; align-items:center; position:relative;
    }
    #sector-page .sector-tree-major-node::after {
      content:""; position:absolute; right:-42px; top:50%;
      width:42px; border-top:1px solid var(--line);
    }
    #sector-page .sector-tree-sectors {
      display:flex; flex-direction:column; gap:12px;
      position:relative; padding-left:42px;
    }
    #sector-page .sector-tree-sectors::before {
      content:""; position:absolute; left:0; top:28px; bottom:28px;
      border-left:1px solid var(--line);
    }
    #sector-page .sector-tree-sector {
      display:grid;
      grid-template-columns:240px auto;
      column-gap:42px;
      position:relative; width:max-content;
    }
    #sector-page .sector-tree-sector::before {
      content:""; position:absolute; left:-42px; top:28px;
      width:42px; border-top:1px solid var(--line);
    }
    #sector-page .sector-tree-sector-node {
      display:flex; align-items:center; position:relative;
    }
    #sector-page .sector-tree-sector-node::after {
      content:""; position:absolute; right:-42px; top:50%;
      width:42px; border-top:1px solid var(--line);
    }
    #sector-page .sector-tree-industries {
      display:flex; flex-direction:column; gap:6px;
      position:relative; padding-left:42px; min-width:260px;
    }
    #sector-page .sector-tree-industries::before {
      content:""; position:absolute; left:0; top:20px; bottom:20px;
      border-left:1px solid var(--line);
    }
    #sector-page .sector-tree-industry {
      position:relative; width:260px;
    }
    #sector-page .sector-tree-industry::before {
      content:""; position:absolute; left:-42px; top:50%;
      width:42px; border-top:1px solid var(--line);
    }
    #sector-page .sector-heat-node {
      width:100%; min-height:48px;
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      grid-template-rows:auto auto;
      align-items:center; gap:2px 10px;
      border:1px solid rgba(255,255,255,.72);
      padding:6px 8px;
      color:#fff;
      font-variant-numeric:tabular-nums;
      text-shadow:0 1px 1px rgba(0,0,0,.75);
    }
    #sector-page .sector-heat-name {
      grid-column:1; grid-row:1;
      overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
      text-align:left;
    }
    #sector-page .sector-heat-change {
      grid-column:2; grid-row:1 / span 2;
      font-size:15px; font-weight:bold; text-align:right;
    }
    #sector-page .sector-heat-count {
      grid-column:1; grid-row:2;
      font-size:11px; text-align:left; color:#fff;
    }
    @media (max-width:700px) {
      #sector-page .sector-heatmap-head { min-width:850px; }
      #sector-page .sector-tree-columns {
        grid-template-columns:190px 210px 230px;
        column-gap:72px; min-width:846px;
      }
      #sector-page .sector-tree-major {
        grid-template-columns:190px auto;
        column-gap:36px; min-width:846px;
      }
      #sector-page .sector-tree-major-node::after { right:-36px; width:36px; }
      #sector-page .sector-tree-sectors { padding-left:36px; }
      #sector-page .sector-tree-sector {
        grid-template-columns:210px auto; column-gap:36px;
      }
      #sector-page .sector-tree-sector::before { left:-36px; width:36px; }
      #sector-page .sector-tree-sector-node::after { right:-36px; width:36px; }
      #sector-page .sector-tree-industries { padding-left:36px; min-width:230px; }
      #sector-page .sector-tree-industry { width:230px; }
      #sector-page .sector-tree-industry::before { left:-36px; width:36px; }
    }
  `;
  document.head.appendChild(style);

  const toggle = document.createElement("button");
  toggle.id = "sector-view-toggle";
  toggle.type = "button";
  toggle.textContent = "表切替";
  toggle.title = "表と分類ヒートマップを切り替える";
  toggle.setAttribute("aria-pressed", "false");
  themeButton.insertAdjacentElement("afterend", toggle);

  let mode = "table";
  let heatData = null;

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

  function jaCompare(a, b) {
    return String(a || "").localeCompare(String(b || ""), "ja", {
      sensitivity:"base", numeric:true
    });
  }

  // 固定スケール -10%～+10%。-10以下=青、0=緑、+10以上=赤。
  function heatColor(v) {
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

  function nodeHtml(row) {
    const name = row && row.name ? row.name : "-";
    const count = Number(row && row.count) || 0;
    return `<div class="sector-heat-node" style="background:${heatColor(row && row.change)}" ` +
      `title="${esc(name)} / ${esc(fmt(row && row.change))} / ${count}銘柄">` +
      `<span class="sector-heat-name">${esc(name)}</span>` +
      `<span class="sector-heat-change">${fmt(row && row.change)}</span>` +
      `<span class="sector-heat-count">${count}銘柄</span>` +
      `</div>`;
  }

  function renderHeatmap(data) {
    heatData = data;
    const scrollTop = body.scrollTop;
    const scrollLeft = body.scrollLeft;

    const majors = Array.from(data.major || []).sort((a, b) => jaCompare(a.name, b.name));
    const sectors = Array.from(data.sector || []);
    const industries = Array.from(data.industry || []);

    const sectorMap = new Map();
    sectors.forEach((row) => {
      const key = String(row.major || "");
      if (!sectorMap.has(key)) sectorMap.set(key, []);
      sectorMap.get(key).push(row);
    });
    sectorMap.forEach((rows) => rows.sort((a, b) => jaCompare(a.name, b.name)));

    const industryMap = new Map();
    industries.forEach((row) => {
      const key = `${row.major || ""}\u0000${row.sector || ""}`;
      if (!industryMap.has(key)) industryMap.set(key, []);
      industryMap.get(key).push(row);
    });
    industryMap.forEach((rows) => rows.sort((a, b) => jaCompare(a.name, b.name)));

    const tree = majors.map((major) => {
      const childSectors = sectorMap.get(String(major.name || "")) || [];
      const sectorHtml = childSectors.map((sector) => {
        const key = `${major.name || ""}\u0000${sector.name || ""}`;
        const childIndustries = industryMap.get(key) || [];
        return `<div class="sector-tree-sector">` +
          `<div class="sector-tree-sector-node">${nodeHtml(sector)}</div>` +
          `<div class="sector-tree-industries">` +
          (childIndustries.length
            ? childIndustries.map((industry) => `<div class="sector-tree-industry">${nodeHtml(industry)}</div>`).join("")
            : `<div class="sector-tree-industry">${nodeHtml({ name:"該当業種なし", change:sector.change, count:sector.count })}</div>`) +
          `</div></div>`;
      }).join("");

      return `<section class="sector-tree-major">` +
        `<div class="sector-tree-major-node">${nodeHtml(major)}</div>` +
        `<div class="sector-tree-sectors">${sectorHtml}</div>` +
        `</section>`;
    }).join("");

    body.innerHTML = `<div class="sector-heatmap">` +
      `<div class="sector-heatmap-head">` +
      `<span class="sector-heatmap-title">日本株 分類ヒートマップ</span>` +
      `<span class="sector-heatmap-meta">${esc(data.date || "-")}</span>` +
      `<span class="sector-heatmap-meta">左から右へ細分化</span>` +
      `<span class="sector-heatmap-legend"><b>-10%</b><span class="sector-heatmap-gradient"></span><b>0%</b><b>+10%</b></span>` +
      `</div>` +
      `<div class="sector-tree-columns"><span>大分類</span><span>セクター</span><span>業種</span></div>` +
      tree +
      `</div>`;

    body.scrollTop = scrollTop;
    body.scrollLeft = scrollLeft;
  }

  async function fetchHeatData() {
    const res = await fetch(`data/sector_today.json?t=${Date.now()}`, { cache:"no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async function showHeatmap() {
    mode = "heatmap";
    toggle.setAttribute("aria-pressed", "true");
    body.innerHTML = '<div class="sector-error">ヒートマップ読み込み中…</div>';
    try {
      const data = await fetchHeatData();
      if (mode === "heatmap") renderHeatmap(data);
    } catch (err) {
      if (mode === "heatmap") {
        body.innerHTML = `<div class="sector-error">ヒートマップを読み込めませんでした。\n${esc(err && err.message ? err.message : err)}</div>`;
      }
    }
  }

  function showTable() {
    mode = "table";
    toggle.setAttribute("aria-pressed", "false");
    if (window.SectorPerformancePage && typeof window.SectorPerformancePage.load === "function") {
      window.SectorPerformancePage.load();
    }
  }

  toggle.addEventListener("click", () => {
    if (mode === "table") showHeatmap();
    else showTable();
  });

  // Color は既存側が表を再描画するので、ヒートマップ表示中ならその直後に戻す。
  themeButton.addEventListener("click", () => {
    if (mode !== "heatmap") return;
    window.setTimeout(() => {
      if (mode === "heatmap" && heatData) renderHeatmap(heatData);
    }, 0);
  });

  if (backButton) {
    backButton.addEventListener("click", () => {
      mode = "table";
      toggle.setAttribute("aria-pressed", "false");
    });
  }

  window.SectorHeatmapView = {
    show: showHeatmap,
    table: showTable,
    heatColor
  };
})();
