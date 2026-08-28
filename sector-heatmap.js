(function () {
  "use strict";
  if (typeof document === "undefined") return;

  const page = document.getElementById("sector-page");
  const body = document.getElementById("sector-body");
  const bar = page && page.querySelector(".bar");
  const themeButton = document.getElementById("sector-theme");
  const backButton = document.getElementById("sector-back");
  if (!page || !body || !bar || document.getElementById("sector-view-toggle")) return;

  const COL_GAP = 42;
  const KEY_SEP = "\u0001";

  const MAJOR_SECTOR_PREFIX = {
    "外需・グローバル景気": "グローバル",
    "資源・市況": "市況",
    "内需・国内景気": "国内",
    "金融・金利敏感": "金融",
    "ディフェンシブ・公共": "ディフェンシブ"
  };
  const SPECIAL_SECTOR_NAMES = new Map([
    [`外需・グローバル景気${KEY_SEP}ハイテク・コンテンツ`, "エンタメ・電子"],
    [`外需・グローバル景気${KEY_SEP}ハイテク・ヘルスケア`, "医療・画像・電子材料"]
  ]);

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
      min-width:1200px; margin:0 0 10px;
    }
    #sector-page .sector-heatmap-title { font-size:18px; color:var(--fg2); }
    #sector-page .sector-heatmap-meta { color:var(--fg); }
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
      grid-template-columns:220px 240px 260px 260px;
      column-gap:${COL_GAP}px;
      min-width:1206px; width:max-content;
      padding:0 4px 5px;
      color:var(--fg2); font-weight:bold;
    }
    #sector-page .sector-tree-list {
      display:flex; flex-direction:column; gap:2px;
      width:max-content; min-width:1206px;
      padding:0 4px;
    }
    #sector-page .sector-tree-major,
    #sector-page .sector-tree-sector,
    #sector-page .sector-tree-industry {
      display:grid;
      grid-template-columns:auto auto;
      column-gap:0;
      align-items:center;
      width:max-content;
      position:relative;
    }
    #sector-page .sector-tree-major { grid-template-columns:220px auto; }
    #sector-page .sector-tree-sector { grid-template-columns:240px auto; }
    #sector-page .sector-tree-industry { grid-template-columns:260px auto; }

    /* 折りたたみ時は大分類同士をほぼ隙間なく並べる。展開分だけ枝の高さが増える。 */
    #sector-page .sector-tree-major > .sector-tree-node-wrap,
    #sector-page .sector-tree-sector > .sector-tree-node-wrap,
    #sector-page .sector-tree-industry > .sector-tree-node-wrap {
      align-self:center;
      position:relative;
    }
    #sector-page .sector-tree-major.has-children > .sector-tree-node-wrap::after,
    #sector-page .sector-tree-sector.has-children > .sector-tree-node-wrap::after,
    #sector-page .sector-tree-industry.has-children > .sector-tree-node-wrap::after {
      content:""; position:absolute; right:-${COL_GAP}px; top:50%;
      width:${COL_GAP}px; border-top:1px solid var(--line);
    }
    #sector-page .sector-tree-branch {
      display:flex; flex-direction:column; gap:4px;
      position:relative; padding-left:${COL_GAP}px;
      width:max-content;
    }
    #sector-page .sector-tree-branch::before {
      content:""; position:absolute; left:0; top:23px; bottom:23px;
      border-left:1px solid var(--line);
    }
    #sector-page .sector-tree-branch > .sector-tree-sector::before,
    #sector-page .sector-tree-branch > .sector-tree-industry::before,
    #sector-page .sector-tree-branch > .sector-tree-stock::before {
      content:""; position:absolute; left:-${COL_GAP}px; top:50%;
      width:${COL_GAP}px; border-top:1px solid var(--line);
    }
    #sector-page .sector-tree-stocks {
      display:flex; flex-direction:column; gap:4px;
      position:relative; padding-left:${COL_GAP}px;
      width:max-content;
    }
    #sector-page .sector-tree-stocks::before {
      content:""; position:absolute; left:0; top:23px; bottom:23px;
      border-left:1px solid var(--line);
    }
    #sector-page .sector-tree-stock {
      position:relative; width:260px;
    }

    #sector-page .sector-heat-node {
      appearance:none;
      width:100%; min-height:46px;
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      grid-template-rows:auto auto;
      align-items:center; gap:2px 10px;
      border:1px solid rgba(255,255,255,.75);
      padding:5px 8px;
      color:#fff;
      font:inherit;
      font-variant-numeric:tabular-nums;
      text-shadow:0 1px 1px rgba(0,0,0,.8);
      text-align:left;
    }
    #sector-page button.sector-heat-node { cursor:pointer; }
    #sector-page button.sector-heat-node:hover,
    #sector-page button.sector-heat-node:focus-visible {
      outline:2px solid #fff; outline-offset:1px;
    }
    #sector-page .sector-heat-name {
      grid-column:1; grid-row:1;
      min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
      text-align:left;
    }
    #sector-page .sector-heat-marker {
      display:inline-block; width:1.25em; font-weight:bold;
    }
    #sector-page .sector-heat-change {
      grid-column:2; grid-row:1 / span 2;
      font-size:15px; font-weight:bold; text-align:right;
    }
    #sector-page .sector-heat-count {
      grid-column:1; grid-row:2;
      font-size:11px; text-align:left; color:#fff;
    }
    #sector-page .sector-heat-placeholder {
      width:260px; min-height:46px;
      display:flex; align-items:center;
      border:1px solid var(--line); padding:5px 8px;
      color:var(--fg); background:var(--panel);
    }

    @media (max-width:700px) {
      #sector-page .sector-heatmap-head { min-width:1060px; }
      #sector-page .sector-tree-columns {
        grid-template-columns:190px 210px 230px 230px;
        column-gap:36px; min-width:1068px;
      }
      #sector-page .sector-tree-list { min-width:1068px; }
      #sector-page .sector-tree-major { grid-template-columns:190px auto; }
      #sector-page .sector-tree-sector { grid-template-columns:210px auto; }
      #sector-page .sector-tree-industry { grid-template-columns:230px auto; }
      #sector-page .sector-tree-stock,
      #sector-page .sector-heat-placeholder { width:230px; }
      #sector-page .sector-tree-branch,
      #sector-page .sector-tree-stocks { padding-left:36px; }
      #sector-page .sector-tree-major.has-children > .sector-tree-node-wrap::after,
      #sector-page .sector-tree-sector.has-children > .sector-tree-node-wrap::after,
      #sector-page .sector-tree-industry.has-children > .sector-tree-node-wrap::after {
        right:-36px; width:36px;
      }
      #sector-page .sector-tree-branch > .sector-tree-sector::before,
      #sector-page .sector-tree-branch > .sector-tree-industry::before,
      #sector-page .sector-tree-branch > .sector-tree-stock::before {
        left:-36px; width:36px;
      }
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
  let memberIndexPromise = null;
  let memberIndex = null;

  const expandedMajors = new Set();
  const expandedSectors = new Set();
  const expandedIndustries = new Set();
  const stockCache = new Map();
  const stockLoading = new Set();
  const stockErrors = new Set();

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

  function sectorKey(major, sector) {
    return `${major || ""}${KEY_SEP}${sector || ""}`;
  }

  function industryKey(major, sector, industry) {
    return `${major || ""}${KEY_SEP}${sector || ""}${KEY_SEP}${industry || ""}`;
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

  function nodeHtml(row, options) {
    const opt = options || {};
    const name = row && row.name ? row.name : "-";
    const count = Number(row && row.count) || 0;
    const marker = opt.loading ? "…" : (opt.expanded ? "▼" : "▶");
    const attrs = [
      `data-level="${esc(opt.level || "")}"`,
      opt.major != null ? `data-major="${esc(opt.major)}"` : "",
      opt.sector != null ? `data-sector="${esc(opt.sector)}"` : "",
      opt.industry != null ? `data-industry="${esc(opt.industry)}"` : "",
      `aria-expanded="${opt.expanded ? "true" : "false"}"`
    ].filter(Boolean).join(" ");

    return `<button type="button" class="sector-heat-node" style="background:${heatColor(row && row.change)}" ` +
      `${attrs} title="${esc(name)} / ${esc(fmt(row && row.change))} / ${count}銘柄">` +
      `<span class="sector-heat-name"><span class="sector-heat-marker">${marker}</span>${esc(name)}</span>` +
      `<span class="sector-heat-change">${fmt(row && row.change)}</span>` +
      `<span class="sector-heat-count">${count}銘柄</span>` +
      `</button>`;
  }

  function stockNodeHtml(row) {
    const code = row && row.code ? row.code : "";
    const name = row && row.name ? row.name : code || "-";
    return `<div class="sector-heat-node" style="background:${heatColor(row && row.change)}" ` +
      `title="${esc(name)}（${esc(code)}） / ${esc(fmt(row && row.change))}">` +
      `<span class="sector-heat-name">${esc(name)}</span>` +
      `<span class="sector-heat-change">${fmt(row && row.change)}</span>` +
      `<span class="sector-heat-count">${esc(code)}</span>` +
      `</div>`;
  }

  function parseCsv(text) {
    const rows = [];
    let row = [], field = "", quoted = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"') {
          if (text[i + 1] === '"') { field += '"'; i++; }
          else quoted = false;
        } else field += ch;
      } else if (ch === '"') quoted = true;
      else if (ch === ",") { row.push(field); field = ""; }
      else if (ch === "\n") {
        row.push(field.replace(/\r$/, "")); field = "";
        if (row.some((v) => v !== "")) rows.push(row);
        row = [];
      } else field += ch;
    }
    if (field !== "" || row.length) {
      row.push(field.replace(/\r$/, ""));
      if (row.some((v) => v !== "")) rows.push(row);
    }
    if (!rows.length) return [];
    const header = rows[0].map((v) => v.replace(/^\uFEFF/, ""));
    return rows.slice(1).map((cells) => {
      const out = {};
      header.forEach((h, i) => { out[h] = cells[i] == null ? "" : cells[i]; });
      return out;
    });
  }

  async function fetchText(url) {
    const res = await fetch(`${url}?t=${Date.now()}`, { cache:"no-store" });
    if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
    return res.text();
  }

  function normalizeClassRows(rows) {
    const prepared = rows.map((r) => {
      const major = String(r.major || "").trim();
      let sector = String(r.sector || "").trim();
      sector = SPECIAL_SECTOR_NAMES.get(sectorKey(major, sector)) || sector;
      return {
        code:String(r.code || "").trim().toUpperCase(),
        major,
        sector,
        industry:String(r.industry || "").trim(),
        demand:String(r.demand || "").trim()
      };
    }).filter((r) => r.code);

    const majorsBySector = new Map();
    prepared.forEach((r) => {
      if (!r.sector) return;
      if (!majorsBySector.has(r.sector)) majorsBySector.set(r.sector, new Set());
      majorsBySector.get(r.sector).add(r.major);
    });
    const duplicates = new Set(
      [...majorsBySector.entries()].filter(([, majors]) => majors.size > 1).map(([name]) => name)
    );
    prepared.forEach((r) => {
      if (duplicates.has(r.sector)) {
        r.sector = `${MAJOR_SECTOR_PREFIX[r.major] || r.major}${r.sector}`;
      }
    });
    return prepared;
  }

  async function ensureMemberIndex() {
    if (memberIndex) return memberIndex;
    if (memberIndexPromise) return memberIndexPromise;
    memberIndexPromise = Promise.all([
      fetchText("data/stock-sectors.csv"),
      fetchText("data/stocks/list.csv")
    ]).then(([classText, listText]) => {
      const classes = normalizeClassRows(parseCsv(classText));
      const names = new Map();
      parseCsv(listText).forEach((r) => {
        const code = String(r.code || "").trim().toUpperCase();
        if (code) names.set(code, String(r.name || code).trim());
      });
      const byIndustry = new Map();
      classes.forEach((r) => {
        if (!r.major || !r.sector || !r.industry) return;
        const key = industryKey(r.major, r.sector, r.industry);
        if (!byIndustry.has(key)) byIndustry.set(key, []);
        byIndustry.get(key).push(r);
      });
      memberIndex = { names, byIndustry };
      return memberIndex;
    }).finally(() => {
      memberIndexPromise = null;
    });
    return memberIndexPromise;
  }

  function changeAtDate(csvText, targetDate) {
    const closes = new Map();
    parseCsv(csvText).forEach((r) => {
      const d = String(r.Date || r.date || "").trim().slice(0, 10);
      const raw = r.Close != null && r.Close !== "" ? r.Close : r.close;
      const c = Number(String(raw == null ? "" : raw).replaceAll(",", ""));
      if (d && Number.isFinite(c) && c > 0) closes.set(d, c);
    });
    const days = [...closes.keys()].filter((d) => d <= targetDate).sort();
    const i = days.indexOf(targetDate);
    if (i <= 0) return null;
    const prev = closes.get(days[i - 1]);
    const close = closes.get(days[i]);
    if (!(prev > 0) || !(close > 0)) return null;
    return (close / prev - 1) * 100;
  }

  async function mapLimit(items, limit, worker) {
    const out = new Array(items.length);
    let next = 0;
    async function run() {
      while (true) {
        const i = next++;
        if (i >= items.length) return;
        out[i] = await worker(items[i], i);
      }
    }
    await Promise.all(Array.from({ length:Math.min(limit, items.length) }, run));
    return out;
  }

  async function loadStocksForIndustry(major, sector, industry) {
    const key = industryKey(major, sector, industry);
    if (stockCache.has(key)) return stockCache.get(key);
    const idx = await ensureMemberIndex();
    const members = idx.byIndustry.get(key) || [];
    const targetDate = heatData && heatData.date ? heatData.date : "9999-12-31";
    const stocks = await mapLimit(members, 6, async (member) => {
      try {
        const text = await fetchText(`data/stocks/${encodeURIComponent(member.code)}.csv`);
        const change = changeAtDate(text, targetDate);
        if (!Number.isFinite(change)) return null;
        return {
          code:member.code,
          name:idx.names.get(member.code) || member.code,
          change
        };
      } catch (_) {
        return null;
      }
    });
    const ready = stocks.filter(Boolean).sort((a, b) => jaCompare(a.name, b.name));
    stockCache.set(key, ready);
    return ready;
  }

  function collapseMajor(major) {
    expandedMajors.delete(major);
    const prefix = `${major}${KEY_SEP}`;
    [...expandedSectors].forEach((key) => { if (key.startsWith(prefix)) expandedSectors.delete(key); });
    [...expandedIndustries].forEach((key) => { if (key.startsWith(prefix)) expandedIndustries.delete(key); });
  }

  function collapseSector(major, sector) {
    const key = sectorKey(major, sector);
    expandedSectors.delete(key);
    const prefix = `${key}${KEY_SEP}`;
    [...expandedIndustries].forEach((k) => { if (k.startsWith(prefix)) expandedIndustries.delete(k); });
  }

  function resetExpansion() {
    expandedMajors.clear();
    expandedSectors.clear();
    expandedIndustries.clear();
    stockLoading.clear();
    stockErrors.clear();
  }

  function renderHeatmap(data) {
    heatData = data;
    const scrollTop = body.scrollTop;
    const scrollLeft = body.scrollLeft;

    const majors = Array.from(data.major || []);
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
      const key = sectorKey(row.major || "", row.sector || "");
      if (!industryMap.has(key)) industryMap.set(key, []);
      industryMap.get(key).push(row);
    });
    industryMap.forEach((rows) => rows.sort((a, b) => jaCompare(a.name, b.name)));

    const tree = majors.map((major) => {
      const majorName = String(major.name || "");
      const majorOpen = expandedMajors.has(majorName);
      let branch = "";

      if (majorOpen) {
        const childSectors = sectorMap.get(majorName) || [];
        const sectorHtml = childSectors.map((sector) => {
          const sectorName = String(sector.name || "");
          const sKey = sectorKey(majorName, sectorName);
          const sectorOpen = expandedSectors.has(sKey);
          let industryBranch = "";

          if (sectorOpen) {
            const childIndustries = industryMap.get(sKey) || [];
            const industryHtml = childIndustries.map((industry) => {
              const industryName = String(industry.name || "");
              const iKey = industryKey(majorName, sectorName, industryName);
              const industryOpen = expandedIndustries.has(iKey);
              let stockBranch = "";

              if (industryOpen) {
                let stockHtml;
                if (stockLoading.has(iKey)) {
                  stockHtml = '<div class="sector-tree-stock"><div class="sector-heat-placeholder">銘柄を読み込み中…</div></div>';
                } else if (stockErrors.has(iKey)) {
                  stockHtml = '<div class="sector-tree-stock"><div class="sector-heat-placeholder">銘柄データを取得できませんでした</div></div>';
                } else {
                  const stocks = stockCache.get(iKey) || [];
                  stockHtml = stocks.length
                    ? stocks.map((stock) => `<div class="sector-tree-stock">${stockNodeHtml(stock)}</div>`).join("")
                    : '<div class="sector-tree-stock"><div class="sector-heat-placeholder">当日データなし</div></div>';
                }
                stockBranch = `<div class="sector-tree-stocks">${stockHtml}</div>`;
              }

              return `<div class="sector-tree-industry${industryOpen ? " has-children" : ""}">` +
                `<div class="sector-tree-node-wrap">${nodeHtml(industry, {
                  level:"industry", major:majorName, sector:sectorName, industry:industryName,
                  expanded:industryOpen, loading:stockLoading.has(iKey)
                })}</div>` + stockBranch + `</div>`;
            }).join("");
            industryBranch = `<div class="sector-tree-branch">${industryHtml}</div>`;
          }

          return `<div class="sector-tree-sector${sectorOpen ? " has-children" : ""}">` +
            `<div class="sector-tree-node-wrap">${nodeHtml(sector, {
              level:"sector", major:majorName, sector:sectorName, expanded:sectorOpen
            })}</div>` + industryBranch + `</div>`;
        }).join("");
        branch = `<div class="sector-tree-branch">${sectorHtml}</div>`;
      }

      return `<section class="sector-tree-major${majorOpen ? " has-children" : ""}">` +
        `<div class="sector-tree-node-wrap">${nodeHtml(major, {
          level:"major", major:majorName, expanded:majorOpen
        })}</div>` + branch + `</section>`;
    }).join("");

    body.innerHTML = `<div class="sector-heatmap">` +
      `<div class="sector-heatmap-head">` +
      `<span class="sector-heatmap-title">日本株 分類ヒートマップ</span>` +
      `<span class="sector-heatmap-meta">${esc(data.date || "-")}</span>` +
      `<span class="sector-heatmap-meta">クリックで右へ展開</span>` +
      `<span class="sector-heatmap-legend"><b>-10%</b><span class="sector-heatmap-gradient"></span><b>0%</b><b>+10%</b></span>` +
      `</div>` +
      `<div class="sector-tree-columns"><span>大分類</span><span>セクター</span><span>業種</span><span>銘柄</span></div>` +
      `<div class="sector-tree-list">${tree}</div>` +
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
    resetExpansion();
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

  body.addEventListener("click", async (e) => {
    if (mode !== "heatmap") return;
    const node = e.target.closest("button.sector-heat-node[data-level]");
    if (!node) return;

    const level = node.dataset.level;
    const major = node.dataset.major || "";
    const sector = node.dataset.sector || "";
    const industry = node.dataset.industry || "";

    if (level === "major") {
      if (expandedMajors.has(major)) collapseMajor(major);
      else expandedMajors.add(major);
      renderHeatmap(heatData);
      return;
    }

    if (level === "sector") {
      const key = sectorKey(major, sector);
      if (expandedSectors.has(key)) collapseSector(major, sector);
      else expandedSectors.add(key);
      renderHeatmap(heatData);
      return;
    }

    if (level === "industry") {
      const key = industryKey(major, sector, industry);
      if (expandedIndustries.has(key)) {
        expandedIndustries.delete(key);
        renderHeatmap(heatData);
        return;
      }

      expandedIndustries.add(key);
      if (stockCache.has(key)) {
        renderHeatmap(heatData);
        return;
      }

      stockLoading.add(key);
      stockErrors.delete(key);
      renderHeatmap(heatData);
      try {
        await loadStocksForIndustry(major, sector, industry);
      } catch (_) {
        stockErrors.add(key);
      } finally {
        stockLoading.delete(key);
        if (mode === "heatmap" && expandedIndustries.has(key)) renderHeatmap(heatData);
      }
    }
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
      resetExpansion();
      toggle.setAttribute("aria-pressed", "false");
    });
  }

  window.SectorHeatmapView = {
    show:showHeatmap,
    table:showTable,
    heatColor
  };
})();
