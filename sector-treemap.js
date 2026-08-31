(function () {
  "use strict";
  if (typeof document === "undefined") return;

  const SEP = "\u0001";
  let mode = "table";
  let heatData = null;
  let resizeTimer = 0;
  let detailIndex = null;
  let detailIndexPromise = null;
  let popupRequest = 0;
  let originalHistory = null;
  let originalHistoryPromise = null;
  let originalSortKey = "id";
  let originalSortDir = 1;

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

  function pctGraphic(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return '<span class="pct-graphic pct-empty">-</span>';
    const a = Math.abs(n);
    const cells = a >= 10 ? 11 : (a < 0.5 ? 1 : Math.min(10, Math.floor(a - 0.5) + 2));
    const neg = n < 0 ? "■".repeat(cells) : "";
    const pos = n >= 0 ? "□".repeat(cells) : "";
    return `<span class="pct-graphic" title="${esc(fmt(n))}">` +
      `<span class="pct-neg">${neg}</span><span class="pct-zero"></span><span class="pct-pos">${pos}</span></span>`;
  }

  function fmtCap(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "-";
    if (n >= 10) return `${n.toFixed(1)}兆`;
    return `${n.toFixed(2)}兆`;
  }

  function fmtIndexValue(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n.toFixed(2) : "-";
  }

  function fmtStockCap(million) {
    if (million == null || million === "") return "-";
    const n = Number(million);
    if (!Number.isFinite(n) || n < 0) return "-";
    const trillion = n / 1_000_000;
    if (trillion >= 1) return `${trillion.toFixed(2)}兆`;
    const oku = n / 100;
    if (oku >= 1) return `${oku.toFixed(0)}億`;
    return `${n.toFixed(0)}百万円`;
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
      if (!groups.has(key)) groups.set(key, { key, major, name:sector, value:0, items:[] });
      const group = groups.get(key);
      group.value += cap;
      group.items.push({ row, value:cap });
    });
    return [...groups.values()]
      .map((group) => ({ ...group, items:group.items.sort((a, b) => b.value - a.value) }))
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
    if (!compact) inner += `<span class="sector-treemap-cap">${fmtCap(cap)} / ${count}銘柄</span>`;
    return `<div class="sector-heat-node sector-treemap-tile${compact ? " compact" : ""}${tiny ? " tiny" : ""}" ` +
      `data-major="${esc(row.major || "")}" data-sector="${esc(row.sector || "")}" data-industry="${esc(row.name || "")}" ` +
      `style="left:${(rect.x + 1).toFixed(2)}px;top:${(rect.y + 1).toFixed(2)}px;width:${w.toFixed(2)}px;height:${h.toFixed(2)}px;background:${heatColor(row && row.change)}" ` +
      `title="${esc(name)} / ${esc(fmt(row && row.change))} / 時価総額 ${esc(fmtCap(cap))} / ${count}銘柄 / ダブルクリックで詳細">${inner}</div>`;
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
      const x = groupRect.x, y = groupRect.y;
      const w = Math.max(0, groupRect.w), h = Math.max(0, groupRect.h);
      const inner = [];
      layoutTreemap(group.items, x + 2, y + 2, Math.max(0, w - 4), Math.max(0, h - 4), inner);
      const tiles = inner.map((entry) => tileHtml(entry.item, entry)).join("");
      const showLabel = w > 90 && h > 34;
      const label = showLabel
        ? `<div class="sector-treemap-sector-label" style="left:${(x + 4).toFixed(2)}px;top:${(y + 4).toFixed(2)}px;max-width:${Math.max(40, w - 8).toFixed(2)}px" title="${esc(group.name)} / ${esc(group.major)} / 時価総額 ${esc(fmtCap(group.value))}">${esc(group.name)}</div>`
        : "";
      return `<div class="sector-treemap-sector-frame" style="left:${x.toFixed(2)}px;top:${y.toFixed(2)}px;width:${w.toFixed(2)}px;height:${h.toFixed(2)}px" title="${esc(group.name)} / ${esc(group.major)} / 時価総額 ${esc(fmtCap(group.value))}"></div>` + tiles + label;
    }).join("");
    body.innerHTML = `<div class="sector-heatmap sector-treemap-view">` +
      `<div class="sector-heatmap-head"><span class="sector-heatmap-title">日本株 業種別時価総額ヒートマップ</span>` +
      `<span class="sector-heatmap-meta">${esc(data.date || "-")}</span>` +
      `<span class="sector-heatmap-meta">面積＝業種合計時価総額</span>` +
      `<span class="sector-heatmap-meta">色＝当日騰落率</span>` +
      `<span class="sector-heatmap-legend"><b>-10%</b><span class="sector-heatmap-gradient"></span><b>0%</b><b>+10%</b></span></div>` +
      `<div class="sector-treemap-canvas" style="width:${width}px;height:${height}px">${sectorsHtml}</div>` +
      `<div class="sector-treemap-note">枠＝セクター / マス＝業種。ダブルクリックで分類・時価総額・騰落率・構成銘柄を表示。時価総額未取得分は面積に含めない。</div></div>`;
  }

  function renderOriginal(data, history) {
    heatData = data;
    const body = document.getElementById("sector-body");
    if (!body || mode !== "original") return;
    const historyMap = new Map((history && history.indices || []).map((item) => [Number(item.id), item]));
    const rows = Array.from(data.original || []).map((row) => ({
      ...row,
      ...(historyMap.get(Number(row.id)) || {}),
    })).sort((a, b) => {
      if (originalSortKey === "id") return (Number(a.id) - Number(b.id)) * originalSortDir;
      const av = Number(a[originalSortKey]), bv = Number(b[originalSortKey]);
      if (Number.isFinite(av) && Number.isFinite(bv) && av !== bv) return (av - bv) * originalSortDir;
      if (Number.isFinite(av) !== Number.isFinite(bv)) return Number.isFinite(av) ? -originalSortDir : originalSortDir;
      return (String(a.name).localeCompare(String(b.name), "ja")) * originalSortDir;
    });
    const tableRows = rows.map((row) => {
      const breakdown = row.breakdown || {};
      const detail = `大${Number(breakdown["大"]) || 0} / 中${Number(breakdown["中"]) || 0} / 小${Number(breakdown["小"]) || 0}`;
      return `<tr>` +
        `<td class="original-index-number">${Number(row.id) || "-"}</td>` +
        `<th class="sector-name"><button type="button" class="original-index-name" data-original-index="${Number(row.id) || ""}" title="クリックで定義を表示">${esc(row.name)}</button></th>` +
        `<td class="original-index-value">${fmtIndexValue(row.latest)}</td>` +
        `<td class="sector-graphic-cell">${pctGraphic(row.change)}</td>` +
        `<td class="sector-change sector-change-col">${fmt(row.change)}</td>` +
        `<td class="sector-change sector-ytd-col">${fmt(row.ytd)}</td>` +
        `<td class="sector-cap sector-cap-col">${fmtCap(row.marketCapTrillion)}</td>` +
        `<td class="sector-count sector-count-col"><button type="button" class="original-index-members" data-original-members="${Number(row.id) || ""}" title="構成銘柄を表示">${Number(row.count) || 0}</button></td>` +
        `<td class="original-index-strength" title="寄与度：大1.0・中0.7・小0.5"><button type="button" class="original-index-members" data-original-members="${Number(row.id) || ""}" title="構成銘柄を表示">${esc(detail)}</button></td>` +
        `</tr>`;
    }).join("");
    body.innerHTML = `<div class="sector-head original-index-head">` +
      `<button type="button" class="sector-title original-index-overview" data-original-overview title="10指数とTOPIX・日経平均の年初来チャートを表示">日本株 オリジナル10指数</button>` +
      `<span class="sector-meta">${esc(data.date || "-")}</span>` +
      `<span class="sector-note">名称クリックで定義・チャート ／ 銘柄数・構成クリックで構成銘柄 ／ 大1.0・中0.7・小0.5の加重平均 ／ 銘柄重複あり</span>` +
      `</div><div class="original-index-benchmarks" id="original-index-benchmarks">${renderBenchmarkPanel(history)}</div>` +
      `<section class="sector-section original-index-section">` +
      `<table class="sector-table original-index-table"><thead><tr>` +
      `<th class="original-index-number"><button type="button" class="original-sort" data-original-sort="id">#</button></th><th class="sector-name">名称</th>` +
      `<th class="original-index-value"><button type="button" class="original-sort" data-original-sort="latest">指数値</button></th>` +
      `<th class="sector-graphic-cell">％graphic</th><th class="sector-change-col"><button type="button" class="original-sort" data-original-sort="change">騰落率</button></th>` +
      `<th class="sector-ytd-col"><button type="button" class="original-sort" data-original-sort="ytd">年初来騰落率</button></th>` +
      `<th class="sector-cap-col"><button type="button" class="original-sort" data-original-sort="marketCapTrillion">時価総額</button></th>` +
      `<th class="sector-count-col"><button type="button" class="original-sort" data-original-sort="count">銘柄数</button></th>` +
      `<th class="original-index-strength">構成（大 / 中 / 小）</th>` +
      `</tr></thead><tbody>${tableRows || '<tr><td colspan="9">オリジナル指数データなし</td></tr>'}</tbody></table></section>`;
  }

  function renderBenchmarkPanel(history) {
    const benchmarks = history && Array.isArray(history.benchmarks) ? history.benchmarks : [];
    if (!benchmarks.length) return '<span>TOPIX・日経平均の履歴を取得できませんでした。</span>';
    return benchmarks.map((item) => {
      const points = Array.isArray(item.points) ? item.points : [];
      const latest = points.length ? Number(points[points.length - 1][1]) : NaN;
      const previous = points.length > 1 ? Number(points[points.length - 2][1]) : NaN;
      const daily = Number.isFinite(latest) && Number.isFinite(previous) && previous ? (latest / previous - 1) * 100 : NaN;
      return `<div class="original-index-benchmark"><b>${esc(item.name)}</b>` +
        `<span>騰落率 <strong>${fmt(daily)}</strong></span><span>年初来 <strong>${fmt(item.ytd)}</strong></span></div>`;
    }).join("");
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

  async function ensureDetailIndex() {
    if (detailIndex) return detailIndex;
    if (detailIndexPromise) return detailIndexPromise;
    detailIndexPromise = Promise.all([
      fetchText("data/stock-sectors.csv"),
      fetchText("data/stocks/list.csv"),
      fetchText("data/market_cap.csv")
    ]).then(([classText, listText, capText]) => {
      const names = new Map();
      parseCsv(listText).forEach((r) => {
        const code = String(r.code || "").trim().toUpperCase();
        if (code) names.set(code, String(r.name || code).trim());
      });
      const caps = new Map();
      parseCsv(capText).forEach((r) => {
        const code = String(r.code || "").trim().toUpperCase();
        const cap = Number(String(r.market_cap_million || "").replaceAll(",", ""));
        if (code && Number.isFinite(cap)) caps.set(code, cap);
      });
      const byIndustry = new Map();
      parseCsv(classText).forEach((r) => {
        const code = String(r.code || "").trim().toUpperCase();
        const major = String(r.major || "").trim();
        const sector = String(r.sector || "").trim();
        const industry = String(r.industry || "").trim();
        if (!code || !major || !sector || !industry) return;
        const key = `${major}${SEP}${sector}${SEP}${industry}`;
        if (!byIndustry.has(key)) byIndustry.set(key, []);
        byIndustry.get(key).push({
          code,
          name:names.get(code) || code,
          major,
          sector,
          industry,
          demand:String(r.demand || "").trim(),
          marketCapMillion:caps.has(code) ? caps.get(code) : null
        });
      });
      detailIndex = { names, caps, byIndustry };
      return detailIndex;
    }).finally(() => { detailIndexPromise = null; });
    return detailIndexPromise;
  }

  function changeAtDate(csvText, targetDate) {
    const closes = [];
    parseCsv(csvText).forEach((r) => {
      const date = String(r.Date || r.date || "").trim().slice(0, 10);
      const raw = r.Close != null && r.Close !== "" ? r.Close : r.close;
      const close = Number(String(raw == null ? "" : raw).replaceAll(",", ""));
      if (date && Number.isFinite(close) && close > 0 && date <= targetDate) closes.push({ date, close });
    });
    closes.sort((a, b) => a.date.localeCompare(b.date));
    const i = closes.findIndex((r) => r.date === targetDate);
    if (i <= 0) return null;
    const prev = closes[i - 1].close, now = closes[i].close;
    return prev > 0 && now > 0 ? (now / prev - 1) * 100 : null;
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

  function findIndustryRow(major, sector, industry) {
    return (heatData && Array.isArray(heatData.industry) ? heatData.industry : []).find((r) =>
      String(r.major || "") === major && String(r.sector || "") === sector && String(r.name || "") === industry
    ) || null;
  }

  function ensurePopup() {
    let modal = document.getElementById("sector-treemap-detail");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "sector-treemap-detail";
    modal.className = "hidden";
    modal.innerHTML = `<div class="sector-treemap-detail-box" role="dialog" aria-modal="true" aria-label="詳細">` +
      `<div class="sector-treemap-detail-head"><strong id="sector-treemap-detail-title">業種詳細</strong><span class="spacer"></span>` +
      `<button id="sector-treemap-detail-close" type="button">閉じる</button></div><div id="sector-treemap-detail-body"></div></div>`;
    document.body.appendChild(modal);
    const close = () => { modal.classList.add("hidden"); popupRequest++; };
    modal.querySelector("#sector-treemap-detail-close").addEventListener("click", close);
    modal.addEventListener("click", (e) => { if (e.target === modal) close(); });
    return modal;
  }

  function closePopup() {
    const modal = document.getElementById("sector-treemap-detail");
    if (!modal || modal.classList.contains("hidden")) return false;
    modal.classList.add("hidden");
    popupRequest++;
    return true;
  }

  async function showIndustryPopup(major, sector, industry) {
    const modal = ensurePopup();
    const title = modal.querySelector("#sector-treemap-detail-title");
    const content = modal.querySelector("#sector-treemap-detail-body");
    const row = findIndustryRow(major, sector, industry);
    const displayName = displayIndustryName(row || { name:industry, sector });
    const requestId = ++popupRequest;
    title.textContent = displayName || industry || "業種詳細";
    modal.classList.remove("hidden");
    content.innerHTML = `<div class="sector-treemap-detail-loading">構成銘柄を読み込み中…</div>`;
    try {
      const idx = await ensureDetailIndex();
      if (requestId !== popupRequest) return;
      const key = `${major}${SEP}${sector}${SEP}${industry}`;
      const members = Array.from(idx.byIndustry.get(key) || []);
      const targetDate = heatData && heatData.date ? heatData.date : "9999-12-31";
      const stocks = await mapLimit(members, 6, async (member) => {
        let change = null;
        try {
          const text = await fetchText(`data/stocks/${encodeURIComponent(member.code)}.csv`);
          change = changeAtDate(text, targetDate);
        } catch (_) { change = null; }
        return { ...member, change };
      });
      if (requestId !== popupRequest) return;
      stocks.sort((a, b) => {
        const ak = Number.isFinite(a.marketCapMillion), bk = Number.isFinite(b.marketCapMillion);
        if (ak && bk && a.marketCapMillion !== b.marketCapMillion) return b.marketCapMillion - a.marketCapMillion;
        if (ak !== bk) return ak ? -1 : 1;
        return String(a.code).localeCompare(String(b.code), "ja", { numeric:true });
      });
      const knownCaps = stocks.filter((s) => Number.isFinite(s.marketCapMillion));
      const knownCapTotal = knownCaps.reduce((sum, s) => sum + s.marketCapMillion, 0);
      const aggregateCap = row && Number(row.marketCapTrillion);
      const aggregateCount = row && Number(row.count);
      const aggregateCapCount = row && Number(row.marketCapCount);
      const summary = `<div class="sector-treemap-detail-class">` +
        `<div><span>大分類</span><b>${esc(major)}</b></div><div><span>セクター</span><b>${esc(sector)}</b></div>` +
        `<div><span>業種</span><b>${esc(displayName)}</b></div></div>` +
        `<div class="sector-treemap-detail-stats"><div><span>騰落率</span><b>${fmt(row && row.change)}</b></div>` +
        `<div><span>合計時価総額</span><b>${fmtCap(aggregateCap)}</b></div>` +
        `<div><span>銘柄数</span><b>${Number.isFinite(aggregateCount) ? aggregateCount : stocks.length}</b></div>` +
        `<div><span>時価総額取得</span><b>${Number.isFinite(aggregateCapCount) ? aggregateCapCount : knownCaps.length} / ${Number.isFinite(aggregateCount) ? aggregateCount : stocks.length}</b></div></div>`;
      const rows = stocks.map((s) => `<tr><td class="code">${esc(s.code)}</td><td class="name">${esc(s.name)}</td>` +
        `<td>${esc(s.demand || "-")}</td><td class="num">${fmtStockCap(s.marketCapMillion)}</td><td class="num">${fmt(s.change)}</td></tr>`).join("");
      const capCheck = Number.isFinite(aggregateCap) ? `集計値 ${fmtCap(aggregateCap)}` : `取得済み構成銘柄合計 ${fmtStockCap(knownCapTotal)}`;
      content.innerHTML = summary + `<div class="sector-treemap-detail-subhead">構成銘柄 <span>${esc(capCheck)}</span></div>` +
        `<div class="sector-treemap-detail-table-wrap"><table class="sector-treemap-detail-table"><thead><tr>` +
        `<th>コード</th><th>銘柄名</th><th>需要地域</th><th>時価総額</th><th>騰落率</th></tr></thead>` +
        `<tbody>${rows || '<tr><td colspan="5">構成銘柄なし</td></tr>'}</tbody></table></div>`;
    } catch (err) {
      if (requestId !== popupRequest) return;
      content.innerHTML = `<div class="sector-treemap-detail-loading">詳細を読み込めませんでした。<br>${esc(err && err.message ? err.message : err)}</div>`;
    }
  }

  function renderHistoryChart(history, series, ariaLabel) {
    const valid = series.filter((s) => s.item && Array.isArray(s.item.points) && s.item.points.length > 1);
    if (!valid.length) return '<div class="original-index-chart-empty">年初来チャートを表示できる履歴がありません。</div>';
    const all = valid.flatMap((s) => s.item.points).map((p) => Number(p[1])).filter(Number.isFinite);
    let lo = Math.min(100, ...all), hi = Math.max(100, ...all);
    const pad = Math.max((hi - lo) * 0.08, 1);
    lo -= pad; hi += pad;
    const width = 920, height = 360, left = 58, right = 16, top = 18, bottom = 58;
    const iw = width - left - right, ih = height - top - bottom;
    const dates = [...new Set(valid.flatMap((s) => s.item.points.map((p) => p[0])))].sort();
    const first = Date.parse(`${dates[0]}T00:00:00Z`), last = Date.parse(`${dates[dates.length - 1]}T00:00:00Z`);
    const x = (date) => left + (last > first ? (Date.parse(`${date}T00:00:00Z`) - first) / (last - first) : 0) * iw;
    const y = (value) => top + (hi - value) / (hi - lo) * ih;
    const path = (points) => points.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(2)},${y(Number(p[1])).toFixed(2)}`).join(" ");
    const ticks = Array.from({ length:5 }, (_, i) => lo + (hi - lo) * i / 4);
    const horizontal = ticks.map((v) => `<line x1="${left}" x2="${width - right}" y1="${y(v).toFixed(2)}" y2="${y(v).toFixed(2)}" class="original-chart-grid"/><text x="${left - 9}" y="${(y(v) + 5).toFixed(2)}" text-anchor="end" class="original-chart-axis">${v.toFixed(1)}</text>`).join("");
    const monthDates = [];
    const seenMonths = new Set();
    dates.forEach((d) => { const month = d.slice(0, 7); if (!seenMonths.has(month)) { seenMonths.add(month); monthDates.push(d); } });
    const monthly = monthDates.map((d) => `<line x1="${x(d).toFixed(2)}" x2="${x(d).toFixed(2)}" y1="${top}" y2="${height - bottom}" class="original-chart-month"/><text x="${x(d).toFixed(2)}" y="${height - 20}" text-anchor="middle" class="original-chart-date">${esc(d.slice(0, 7).replace("-", "/"))}</text>`).join("");
    const base = `<line x1="${left}" x2="${width - right}" y1="${y(100).toFixed(2)}" y2="${y(100).toFixed(2)}" class="original-chart-base"/>`;
    const lines = valid.map((s) => `<path d="${path(s.item.points)}" class="original-chart-line" style="stroke:${s.color};stroke-width:${s.width || 2}"/>`).join("");
    const legend = valid.map((s) => `<span class="original-chart-legend"><i style="border-color:${s.color}"></i>${esc(s.item.name)} ${fmt(s.item.ytd)}</span>`).join("");
    return `<div class="original-index-chart-head"><span>2026年 年初来推移（2026-01-05＝100）</span><span>基準日 ${esc(history.baseDate || "-")}</span></div>` +
      `<svg class="original-index-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(ariaLabel)}">${horizontal}${monthly}${base}${lines}</svg>` +
      `<div class="original-chart-legend-wrap">${legend}</div>`;
  }

  function originalChart(history, indexId) {
    const selected = (history && history.indices || []).find((item) => Number(item.id) === Number(indexId));
    const benchmarks = history && history.benchmarks || [];
    return renderHistoryChart(history, [
      { item:selected, color:"#ff5f56", width:3 },
      { item:benchmarks.find((item) => item.name === "TOPIX"), color:"#56b4ff" },
      { item:benchmarks.find((item) => item.name === "日経平均"), color:"#ffd166" },
    ], `${selected ? selected.name : "選択指数"}とTOPIX・日経平均の2026年推移`);
  }

  function allOriginalChart(history) {
    const colors = ["#ff5f56", "#ff9f43", "#ffd166", "#7ee787", "#2dd4bf", "#4cc9f0", "#6ea8fe", "#9b8afb", "#d783ff", "#ff7ab2"];
    const series = (history.indices || []).map((item, i) => ({ item, color:colors[i % colors.length], width:2.2 }));
    series.push({ item:(history.benchmarks || []).find((item) => item.name === "TOPIX"), color:"var(--fg)", width:3 });
    series.push({ item:(history.benchmarks || []).find((item) => item.name === "日経平均"), color:"#f1c40f", width:3 });
    return renderHistoryChart(history, series, "オリジナル10指数とTOPIX・日経平均の2026年推移");
  }

  async function showOriginalOverviewPopup() {
    const modal = ensurePopup();
    const title = modal.querySelector("#sector-treemap-detail-title");
    const content = modal.querySelector("#sector-treemap-detail-body");
    const requestId = ++popupRequest;
    title.textContent = "日本株 オリジナル10指数";
    content.innerHTML = '<div class="original-index-chart-wrap">10指数とTOPIX・日経平均の年初来チャートを読み込み中…</div>';
    modal.classList.remove("hidden");
    try {
      const history = await fetchOriginalHistory();
      if (requestId !== popupRequest) return;
      content.innerHTML = `<div class="original-index-chart-wrap original-index-chart-all">${allOriginalChart(history)}</div>`;
    } catch (_) {
      if (requestId !== popupRequest) return;
      content.innerHTML = '<div class="original-index-chart-empty">年初来チャートを読み込めませんでした。</div>';
    }
  }

  async function showOriginalPopup(indexId) {
    const row = (heatData && Array.isArray(heatData.original) ? heatData.original : [])
      .find((item) => Number(item.id) === Number(indexId));
    if (!row) return;
    const modal = ensurePopup();
    const title = modal.querySelector("#sector-treemap-detail-title");
    const content = modal.querySelector("#sector-treemap-detail-body");
    const requestId = ++popupRequest;
    title.textContent = `${Number(row.id)}. ${row.name}`;
    const breakdown = row.breakdown || {};
    content.innerHTML = `<div class="original-index-popup-concept">${esc(row.concept || row.name)}</div>` +
      `<div class="original-index-popup-label">定義</div>` +
      `<p class="original-index-popup-definition">${esc(row.definition || "-")}</p>` +
      `<div class="sector-treemap-detail-stats original-index-popup-stats">` +
      `<div><span>騰落率</span><b>${fmt(row.change)}</b></div>` +
      `<div><span>年初来騰落率</span><b>読み込み中…</b></div>` +
      `<div><span>時価総額</span><b>${fmtCap(row.marketCapTrillion)}</b></div>` +
      `<div><button type="button" class="original-index-popup-member-open" data-original-popup-members="${Number(row.id) || ""}" title="構成銘柄を表示"><span>銘柄数</span><b>${Number(row.count) || 0}</b></button></div>` +
      `<div><span>寄与度合計</span><b>${Number(row.weightSum) || 0}</b></div>` +
      `<div><button type="button" class="original-index-popup-member-open" data-original-popup-members="${Number(row.id) || ""}" title="構成銘柄を表示"><span>構成</span><b>大${Number(breakdown["大"]) || 0} / 中${Number(breakdown["中"]) || 0} / 小${Number(breakdown["小"]) || 0}</b></button></div>` +
      `</div><div class="original-index-chart-wrap">チャートを読み込み中…</div>` +
      `<div class="original-index-popup-method">指数騰落率 ＝ Σ（各銘柄の騰落率 × 寄与度）÷ Σ（寄与度）<br>寄与度：大 1.0 ／ 中 0.7 ／ 小 0.5。銘柄の指数間重複を許容。</div>`;
    modal.classList.remove("hidden");
    content.querySelectorAll("button[data-original-popup-members]").forEach((button) => {
      button.addEventListener("click", () => showOriginalMembersPopup(button.dataset.originalPopupMembers));
    });
    try {
      const history = await fetchOriginalHistory();
      if (requestId !== popupRequest) return;
      const series = (history.indices || []).find((item) => Number(item.id) === Number(indexId));
      const ytd = series ? series.ytd : NaN;
      const stats = content.querySelectorAll(".original-index-popup-stats b");
      if (stats[1]) stats[1].textContent = fmt(ytd);
      const chart = content.querySelector(".original-index-chart-wrap");
      if (chart) chart.innerHTML = originalChart(history, indexId);
    } catch (err) {
      if (requestId !== popupRequest) return;
      const chart = content.querySelector(".original-index-chart-wrap");
      if (chart) chart.textContent = "年初来チャートを読み込めませんでした。";
    }
  }

  async function showOriginalMembersPopup(indexId) {
    const row = (heatData && Array.isArray(heatData.original) ? heatData.original : [])
      .find((item) => Number(item.id) === Number(indexId));
    if (!row) return;
    const modal = ensurePopup();
    const title = modal.querySelector("#sector-treemap-detail-title");
    const content = modal.querySelector("#sector-treemap-detail-body");
    const requestId = ++popupRequest;
    title.textContent = `${Number(row.id)}. ${row.name}　構成銘柄`;
    modal.classList.remove("hidden");
    content.innerHTML = '<div class="sector-treemap-detail-loading">構成銘柄を読み込み中…</div>';
    try {
      const members = Array.from(row.members || []).map((member) => ({
        code:String(member.code || "").trim().toUpperCase(),
        name:String(member.name || member.code || "").trim(),
        strength:String(member.strength || ""),
        weight:Number(member.weight),
      })).filter((member) => member.code);
      let sortKey = "strength";
      const draw = () => {
        const sorted = members.slice().sort((a, b) => {
          if (sortKey === "strength" && a.weight !== b.weight) return b.weight - a.weight;
          return a.code.localeCompare(b.code, "ja", { numeric:true });
        });
        const breakdown = row.breakdown || {};
        const rows = sorted.map((member) => `<tr>` +
          `<td class="code">${esc(member.code)}</td><td class="name">${esc(member.name)}</td>` +
          `<td class="num original-member-weight"><b>${esc(member.strength || "-")}</b> ${Number.isFinite(member.weight) ? member.weight.toFixed(1) : "-"}</td></tr>`).join("");
        content.innerHTML = `<div class="sector-treemap-detail-stats original-member-stats">` +
          `<div><span>銘柄数</span><b>${Number(row.count) || members.length}</b></div>` +
          `<div><span>寄与度合計</span><b>${Number(row.weightSum) || 0}</b></div>` +
          `<div><span>構成</span><b>大${Number(breakdown["大"]) || 0} / 中${Number(breakdown["中"]) || 0} / 小${Number(breakdown["小"]) || 0}</b></div>` +
          `</div><div class="original-member-sortbar"><span>並び順</span>` +
          `<button type="button" data-original-member-sort="strength" aria-pressed="${sortKey === "strength"}">寄与度順</button>` +
          `<button type="button" data-original-member-sort="code" aria-pressed="${sortKey === "code"}">コード順</button></div>` +
          `<div class="sector-treemap-detail-table-wrap"><table class="sector-treemap-detail-table original-member-table"><thead><tr>` +
          `<th><button type="button" data-original-member-sort="code">コード</button></th><th>銘柄名</th>` +
          `<th><button type="button" data-original-member-sort="strength">寄与度</button></th></tr></thead>` +
          `<tbody>${rows || '<tr><td colspan="3">構成銘柄なし</td></tr>'}</tbody></table></div>`;
        content.querySelectorAll("button[data-original-member-sort]").forEach((button) => {
          button.addEventListener("click", () => {
            sortKey = button.dataset.originalMemberSort === "code" ? "code" : "strength";
            draw();
          });
        });
      };
      draw();
    } catch (err) {
      if (requestId !== popupRequest) return;
      content.innerHTML = `<div class="sector-treemap-detail-loading">構成銘柄を読み込めませんでした。<br>${esc(err && err.message ? err.message : err)}</div>`;
    }
  }

  async function fetchHeatData() {
    if (heatData) return heatData;
    const res = await fetch(`data/sector_today.json?t=${Date.now()}`, { cache:"no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    heatData = await res.json();
    return heatData;
  }

  async function fetchOriginalHistory() {
    if (originalHistory) return originalHistory;
    if (!originalHistoryPromise) {
      originalHistoryPromise = fetch("data/original_index_history.json?t=" + Date.now(), { cache:"no-store" })
        .then((res) => { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res.json(); })
        .then((data) => { originalHistory = data; return data; });
    }
    return originalHistoryPromise;
  }

  function updateToggleHint(toggle) {
    if (!toggle) return;
    if (mode === "table") toggle.title = "表切替：オリジナル10指数を表示";
    else if (mode === "original") toggle.title = "表切替：業種別時価総額マップを表示";
    else if (mode === "treemap") toggle.title = "表切替：階層ヒートマップを表示";
    else toggle.title = "表切替：表へ戻る";
  }

  async function showOriginal() {
    const body = document.getElementById("sector-body");
    const toggle = document.getElementById("sector-view-toggle");
    if (!body || !toggle) return;
    closePopup();
    mode = "original";
    document.getElementById("sector-page")?.classList.add("original-index-mode");
    toggle.setAttribute("aria-pressed", "false");
    updateToggleHint(toggle);
    body.innerHTML = '<div class="sector-error">オリジナル10指数読み込み中…</div>';
    try {
      const data = await fetchHeatData();
      let history = null;
      try { history = await fetchOriginalHistory(); } catch (_) { /* 表自体は表示する */ }
      if (mode === "original") renderOriginal(data, history);
    } catch (err) {
      if (mode === "original") body.innerHTML = `<div class="sector-error">オリジナル10指数を読み込めませんでした。\n${esc(err && err.message ? err.message : err)}</div>`;
    }
  }

  async function showTreemap() {
    const body = document.getElementById("sector-body");
    const toggle = document.getElementById("sector-view-toggle");
    if (!body || !toggle) return;
    closePopup();
    mode = "treemap";
    document.getElementById("sector-page")?.classList.remove("original-index-mode");
    toggle.setAttribute("aria-pressed", "true");
    updateToggleHint(toggle);
    body.innerHTML = '<div class="sector-error">業種別時価総額マップ読み込み中…</div>';
    try {
      const data = await fetchHeatData();
      if (mode === "treemap") renderTreemap(data);
    } catch (err) {
      if (mode === "treemap") body.innerHTML = `<div class="sector-error">業種別時価総額マップを読み込めませんでした。\n${esc(err && err.message ? err.message : err)}</div>`;
    }
  }

  function showHierarchy() {
    closePopup();
    mode = "hierarchy";
    document.getElementById("sector-page")?.classList.remove("original-index-mode");
    const toggle = document.getElementById("sector-view-toggle");
    updateToggleHint(toggle);
    if (window.SectorHeatmapView && typeof window.SectorHeatmapView.show === "function") window.SectorHeatmapView.show();
  }

  function showTable() {
    closePopup();
    mode = "table";
    document.getElementById("sector-page")?.classList.remove("original-index-mode");
    const toggle = document.getElementById("sector-view-toggle");
    updateToggleHint(toggle);
    if (window.SectorHeatmapView && typeof window.SectorHeatmapView.table === "function") window.SectorHeatmapView.table();
    else if (window.SectorPerformancePage && typeof window.SectorPerformancePage.load === "function") {
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
      #sector-page .sector-treemap-canvas { position:relative; overflow:hidden; background:var(--bg); border:1px solid var(--line); box-sizing:border-box; }
      #sector-page .sector-treemap-sector-frame { position:absolute; z-index:2; box-sizing:border-box; border:2px solid var(--fg2); pointer-events:none; }
      #sector-page .sector-treemap-sector-label { position:absolute; z-index:4; box-sizing:border-box; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; padding:2px 5px; background:rgba(0,0,0,.72); color:#fff; border:1px solid rgba(255,255,255,.55); font-size:12px; font-weight:bold; text-shadow:0 1px 1px #000; pointer-events:none; }
      #sector-page .sector-treemap-tile.sector-heat-node { position:absolute; z-index:1; box-sizing:border-box; min-height:0 !important; display:flex !important; flex-direction:column; align-items:center; justify-content:center; gap:2px; padding:4px; overflow:hidden; border:1px solid rgba(255,255,255,.78); line-height:1.08; text-align:center; cursor:pointer; }
      #sector-page .sector-treemap-tile .sector-treemap-name { display:block; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; font-weight:bold; }
      #sector-page .sector-treemap-tile .sector-heat-change { display:block; grid-column:auto; grid-row:auto; font-size:14px; font-weight:bold; text-align:center; }
      #sector-page .sector-treemap-tile .sector-treemap-cap { display:block; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:10px; }
      #sector-page .sector-treemap-tile.compact { padding:2px; gap:1px; }
      #sector-page .sector-treemap-tile.compact .sector-treemap-name { font-size:10px; }
      #sector-page .sector-treemap-tile.compact .sector-heat-change { font-size:10px; }
      #sector-page .sector-treemap-tile.tiny .sector-treemap-name { font-size:8px; }
      #sector-page .sector-treemap-tile.tiny .sector-heat-change { display:none; }
      #sector-page .sector-treemap-note { margin-top:7px; color:var(--fg); font-size:12px; }
      #sector-page.original-index-mode #sector-ai-run,
      #sector-page.original-index-mode #sector-ai-prompt,
      #sector-page.original-index-mode #sector-ai-status { display:none !important; }
      #sector-page .original-index-section { overflow-x:auto; }
      #sector-page table.original-index-table { min-width:1180px; }
      #sector-page .original-index-table .original-index-number { width:3.5em; min-width:3.5em; text-align:right; color:var(--dim); }
      #sector-page .original-index-table .sector-name { width:15em; min-width:15em; max-width:15em; }
      #sector-page .original-index-value { min-width:6.5em; text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }
      #sector-page .original-index-overview { padding:0; border:0; background:none; color:var(--fg2); font:inherit; font-weight:bold; text-decoration:underline; text-underline-offset:3px; cursor:pointer; }
      #sector-page .original-index-overview:hover,#sector-page .original-index-overview:focus-visible { color:var(--fg); }
      #sector-page .original-index-name { width:100%; padding:0; border:0; background:none; color:var(--fg2); font:inherit; font-weight:bold; text-align:left; cursor:pointer; }
      #sector-page .original-index-name:hover,#sector-page .original-index-name:focus-visible { text-decoration:underline; }
      #sector-page .original-index-strength { width:15em; min-width:15em; text-align:right; white-space:nowrap; color:var(--dim); }
      #sector-page .original-index-members { width:100%; padding:0; border:0; background:none; color:inherit; font:inherit; text-align:inherit; cursor:pointer; text-decoration:underline dotted; text-underline-offset:3px; }
      #sector-page .original-index-members:hover,#sector-page .original-index-members:focus-visible { color:var(--fg2); }
      #sector-page .original-sort { padding:0; border:0; background:none; color:inherit; font:inherit; cursor:pointer; text-decoration:underline dotted; }
      #sector-page .original-sort:hover,#sector-page .original-sort:focus-visible { color:var(--fg2); }
      #sector-page .original-index-benchmarks { display:flex; flex-wrap:wrap; gap:8px; margin:8px 0 12px; }
      #sector-page .original-index-benchmark { display:flex; align-items:baseline; gap:10px; min-width:240px; padding:8px 12px; border:1px solid var(--line); background:var(--panel); }
      #sector-page .original-index-benchmark b { color:var(--fg); }
      #sector-page .original-index-benchmark span { color:var(--fg); font-size:12px; }
      #sector-page .original-index-benchmark strong { color:var(--fg); font-size:14px; }
      #sector-treemap-detail .original-index-popup-concept { margin-bottom:14px; color:var(--fg2); font-size:20px; font-weight:bold; }
      #sector-treemap-detail .original-index-popup-label { margin-bottom:5px; color:var(--dim); font-size:12px; }
      #sector-treemap-detail .original-index-popup-definition { margin:0 0 16px; padding:12px; border:1px solid var(--line); background:var(--panel); color:var(--fg); font-size:16px; line-height:1.75; }
      #sector-treemap-detail .original-index-popup-stats { grid-template-columns:repeat(2,minmax(0,1fr)) !important; }
      #sector-treemap-detail .original-index-popup-member-open { display:block; width:100%; padding:0; border:0; background:none; color:inherit; font:inherit; text-align:left; cursor:pointer; }
      #sector-treemap-detail .original-index-popup-member-open b { text-decoration:underline dotted; text-underline-offset:3px; }
      #sector-treemap-detail .original-index-popup-member-open:hover b,#sector-treemap-detail .original-index-popup-member-open:focus-visible b { color:var(--fg); }
      #sector-treemap-detail .original-index-popup-method { padding:10px 12px; border-top:1px solid var(--line); color:var(--dim); line-height:1.7; }
      #sector-treemap-detail .original-index-chart-wrap { margin:14px 0; padding:10px; border:1px solid var(--line); background:var(--panel); overflow:hidden; }
      #sector-treemap-detail .original-index-chart-head { display:flex; justify-content:space-between; gap:12px; margin-bottom:6px; color:var(--fg); font-size:14px; font-weight:bold; }
      #sector-treemap-detail .original-index-chart { display:block; width:100%; min-height:250px; }
      #sector-treemap-detail .original-chart-grid { stroke:var(--line); stroke-width:1; opacity:.7; }
      #sector-treemap-detail .original-chart-month { stroke:var(--line); stroke-width:1; opacity:.85; }
      #sector-treemap-detail .original-chart-base { stroke:var(--dim); stroke-width:1; stroke-dasharray:4 4; opacity:.9; }
      #sector-treemap-detail .original-chart-axis { fill:var(--fg); font-size:13px; font-weight:bold; }
      #sector-treemap-detail .original-chart-date { fill:var(--fg); font-size:13px; font-weight:bold; }
      #sector-treemap-detail .original-chart-line { fill:none; stroke-width:2; vector-effect:non-scaling-stroke; }
      #sector-treemap-detail .original-chart-line.selected { stroke:var(--fg2); stroke-width:3; }
      #sector-treemap-detail .original-chart-line.nikkei { stroke:#e6b450; }
      #sector-treemap-detail .original-chart-line.topix { stroke:#6bb5ff; }
      #sector-treemap-detail .original-chart-legend-wrap { display:flex; flex-wrap:wrap; gap:12px; margin-top:4px; }
      #sector-treemap-detail .original-chart-legend { color:var(--fg); font-size:13px; }
      #sector-treemap-detail .original-chart-legend i { display:inline-block; width:18px; margin-right:5px; vertical-align:middle; border-top:3px solid var(--fg2); }
      #sector-treemap-detail .original-chart-legend.nikkei i { border-color:#e6b450; }
      #sector-treemap-detail .original-chart-legend.topix i { border-color:#6bb5ff; }
      #sector-treemap-detail .original-index-chart-empty { padding:16px; color:var(--dim); }
      #sector-treemap-detail .original-member-stats { grid-template-columns:repeat(3,minmax(0,1fr)); }
      #sector-treemap-detail .original-member-sortbar { display:flex; align-items:center; gap:7px; margin:12px 0 7px; color:var(--dim); }
      #sector-treemap-detail .original-member-sortbar button,#sector-treemap-detail .original-member-table th button { border:1px solid var(--line); background:var(--panel); color:var(--fg); font:inherit; padding:4px 10px; cursor:pointer; }
      #sector-treemap-detail .original-member-sortbar button[aria-pressed="true"] { background:var(--sel-bg); color:var(--sel-fg); }
      #sector-treemap-detail .original-member-table { min-width:520px; }
      #sector-treemap-detail .original-member-table th button { padding:0; border:0; color:var(--fg2); text-decoration:underline dotted; }
      #sector-treemap-detail .original-member-weight b { color:var(--fg2); }
      #sector-treemap-detail { position:fixed; inset:0; z-index:10040; display:flex; align-items:center; justify-content:center; padding:18px; background:rgba(0,0,0,.74); }
      #sector-treemap-detail.hidden { display:none !important; }
      #sector-treemap-detail .sector-treemap-detail-box { width:min(1000px,96vw); max-height:88vh; overflow:auto; background:var(--bg); color:var(--fg); border:2px solid var(--line); box-shadow:0 10px 40px rgba(0,0,0,.65); }
      #sector-treemap-detail .sector-treemap-detail-head { position:sticky; top:0; z-index:3; display:flex; align-items:center; gap:12px; padding:9px 11px; border-bottom:1px solid var(--line); background:var(--panel); }
      #sector-treemap-detail .sector-treemap-detail-head strong { color:var(--fg2); font-size:19px; }
      #sector-treemap-detail .sector-treemap-detail-head .spacer { flex:1; }
      #sector-treemap-detail .sector-treemap-detail-head button { font:inherit; color:var(--fg); background:var(--panel); border:1px solid var(--line); padding:5px 14px; cursor:pointer; }
      #sector-treemap-detail-body { padding:12px; }
      #sector-treemap-detail .sector-treemap-detail-class,#sector-treemap-detail .sector-treemap-detail-stats { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:7px; margin-bottom:10px; }
      #sector-treemap-detail .sector-treemap-detail-stats { grid-template-columns:repeat(4,minmax(0,1fr)); }
      #sector-treemap-detail .sector-treemap-detail-class>div,#sector-treemap-detail .sector-treemap-detail-stats>div { min-width:0; border:1px solid var(--line); padding:7px 9px; background:var(--panel); }
      #sector-treemap-detail .sector-treemap-detail-class span,#sector-treemap-detail .sector-treemap-detail-stats span { display:block; color:var(--dim); font-size:11px; margin-bottom:2px; }
      #sector-treemap-detail .sector-treemap-detail-class b,#sector-treemap-detail .sector-treemap-detail-stats b { display:block; overflow:hidden; text-overflow:ellipsis; color:var(--fg2); font-size:15px; }
      #sector-treemap-detail .sector-treemap-detail-subhead { display:flex; gap:12px; align-items:baseline; margin:14px 0 5px; color:var(--fg2); font-size:15px; }
      #sector-treemap-detail .sector-treemap-detail-subhead span { color:var(--dim); font-size:11px; }
      #sector-treemap-detail .sector-treemap-detail-table-wrap { overflow:auto; }
      #sector-treemap-detail .sector-treemap-detail-table { width:100%; min-width:700px; border-collapse:collapse; font-variant-numeric:tabular-nums; }
      #sector-treemap-detail .sector-treemap-detail-table th,#sector-treemap-detail .sector-treemap-detail-table td { border:1px solid var(--line); padding:6px 8px; color:var(--fg); }
      #sector-treemap-detail .sector-treemap-detail-table th { position:sticky; top:0; background:var(--panel); color:var(--fg2); text-align:left; }
      #sector-treemap-detail .sector-treemap-detail-table td.num { text-align:right; white-space:nowrap; }
      #sector-treemap-detail .sector-treemap-detail-table td.code { white-space:nowrap; }
      #sector-treemap-detail .sector-treemap-detail-table td.name { min-width:12em; }
      #sector-treemap-detail .sector-treemap-detail-loading { padding:22px 12px; color:var(--fg2); }
      @media (max-width:700px) { #sector-page .sector-treemap-sector-label { font-size:10px; padding:1px 3px; } #sector-treemap-detail { padding:7px; } #sector-treemap-detail .sector-treemap-detail-box { width:99vw; max-height:92vh; } #sector-treemap-detail .sector-treemap-detail-class,#sector-treemap-detail .sector-treemap-detail-stats { grid-template-columns:1fr 1fr; } }
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
    ensurePopup();
    updateToggleHint(toggle);
    toggle.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (mode === "table") showOriginal();
      else if (mode === "original") showTreemap();
      else if (mode === "treemap") showHierarchy();
      else showTable();
    }, true);
    body.addEventListener("dblclick", (event) => {
      if (mode !== "treemap") return;
      const tile = event.target.closest(".sector-treemap-tile[data-industry]");
      if (!tile) return;
      event.preventDefault();
      event.stopPropagation();
      showIndustryPopup(tile.dataset.major || "", tile.dataset.sector || "", tile.dataset.industry || "");
    });
    body.addEventListener("click", (event) => {
      if (mode !== "original") return;
      const overviewButton = event.target.closest("button[data-original-overview]");
      if (overviewButton) {
        event.preventDefault();
        showOriginalOverviewPopup();
        return;
      }
      const sortButton = event.target.closest("button[data-original-sort]");
      if (sortButton) {
        event.preventDefault();
        const key = sortButton.dataset.originalSort || "id";
        if (originalSortKey === key) originalSortDir *= -1;
        else { originalSortKey = key; originalSortDir = key === "id" ? 1 : -1; }
        renderOriginal(heatData, originalHistory);
        return;
      }
      const membersButton = event.target.closest("button[data-original-members]");
      if (membersButton) {
        event.preventDefault();
        showOriginalMembersPopup(membersButton.dataset.originalMembers);
        return;
      }
      const button = event.target.closest("button[data-original-index]");
      if (!button) return;
      event.preventDefault();
      showOriginalPopup(button.dataset.originalIndex);
    });
    themeButton?.addEventListener("click", () => {
      if (!heatData || (mode !== "treemap" && mode !== "original")) return;
      window.setTimeout(() => {
        if (mode === "treemap") renderTreemap(heatData);
        else if (mode === "original") renderOriginal(heatData, originalHistory);
      }, 0);
    });
    backButton?.addEventListener("click", () => {
      closePopup();
      mode = "table";
      page.classList.remove("original-index-mode");
      updateToggleHint(toggle);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      if (!closePopup()) return;
      event.preventDefault();
      event.stopImmediatePropagation();
    }, true);
    window.addEventListener("resize", () => {
      if (mode !== "treemap" || !heatData) return;
      clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => { if (mode === "treemap") renderTreemap(heatData); }, 120);
    });
    window.SectorTreemapView = { show:showTreemap, original:showOriginal, hierarchy:showHierarchy, table:showTable, render:renderTreemap, detail:showIndustryPopup };
    return true;
  }

  if (!init()) {
    const observer = new MutationObserver(() => { if (init()) observer.disconnect(); });
    observer.observe(document.documentElement, { childList:true, subtree:true });
  }
})();
