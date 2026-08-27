(function () {
  "use strict";
  if (typeof document === "undefined") return;

  const menu = document.getElementById("titleMenu");
  const title = document.getElementById("title");
  if (!menu || !title || document.getElementById("sector-page")) return;

  const sectorButton = document.createElement("button");
  sectorButton.id = "sector-menu-button";
  sectorButton.type = "button";
  sectorButton.dataset.go = "sector";
  sectorButton.textContent = "セクター別";
  sectorButton.setAttribute("aria-selected", "false");
  const sheetButton = menu.querySelector('[data-go="sheet"]');
  if (sheetButton) sheetButton.insertAdjacentElement("afterend", sectorButton);
  else menu.appendChild(sectorButton);

  const style = document.createElement("style");
  style.textContent = `
    #sector-page { height:100%; display:flex; flex-direction:column; }
    #sector-page .sector-wrap {
      flex:1; overflow:auto; padding:14px 12px 28px;
      scrollbar-color:var(--fg) var(--bg); scrollbar-width:thin;
    }
    #sector-page .sector-head {
      display:flex; flex-wrap:wrap; gap:7px 18px; align-items:baseline;
      width:min(1380px, 100%); margin:0 auto 14px;
    }
    #sector-page .sector-title { color:var(--fg2); font-size:18px; }
    #sector-page .sector-meta { color:var(--dim); }
    #sector-page .sector-note { color:var(--dim); font-size:12px; margin-left:auto; }
    #sector-page .sector-section { width:min(1380px, 100%); margin:0 auto 22px; overflow-x:auto; }
    #sector-page .sector-section h2 {
      margin:0; padding:5px 8px; border:1px solid var(--line); border-bottom:0;
      color:var(--fg2); font-size:14px; font-weight:normal;
    }
    #sector-page table.sector-table { width:auto; table-layout:fixed; }
    #sector-page th, #sector-page td { padding:5px 8px; }
    #sector-page thead th { position:static; }
    #sector-page tbody th { position:static; }
    #sector-page .sector-name {
      width:11em; min-width:11em; max-width:11em;
      white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-align:left;
    }
    #sector-page .sector-graphic-cell {
      width:24ch; min-width:24ch; max-width:24ch;
      padding-left:5px; padding-right:5px;
    }
    #sector-page .sector-change-col {
      width:7em; min-width:7em; max-width:7em; text-align:right;
    }
    #sector-page .sector-count-col {
      width:5em; min-width:5em; max-width:5em; text-align:right;
    }
    #sector-page .sector-cap-col {
      width:8em; min-width:8em; max-width:8em; text-align:right;
      white-space:nowrap;
    }
    #sector-page .sector-avg-cap-col {
      width:10em; min-width:10em; max-width:10em; text-align:right;
      white-space:nowrap;
    }
    #sector-page .sector-parent-col {
      width:12em; min-width:12em; max-width:12em;
      white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-align:left;
    }
    #sector-page td.sector-change { font-weight:bold; font-size:15px; text-align:right; }
    #sector-page td.sector-count,
    #sector-page td.sector-cap { color:var(--dim); text-align:right; }
    #sector-page .sector-major { color:var(--dim); text-align:left; }
    #sector-page .sector-sort-button {
      display:inline; margin:0; padding:0; border:0; background:none;
      color:inherit; font:inherit; cursor:pointer; white-space:nowrap;
    }
    #sector-page .sector-sort-button:hover,
    #sector-page .sector-sort-button:focus-visible { color:var(--fg2); text-decoration:underline; }
    #sector-page .pct-graphic {
      display:grid; grid-template-columns:11ch 0 11ch; align-items:center;
      width:22ch; line-height:1; white-space:nowrap;
      font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size:13px;
    }
    #sector-page .pct-neg { text-align:right; overflow:hidden; }
    #sector-page .pct-pos { text-align:left; overflow:hidden; }
    #sector-page .pct-zero { height:1.25em; border-left:1px solid var(--dim); }
    #sector-page .pct-empty { color:var(--dim); }
    #sector-page .sector-error {
      width:min(1380px, 100%); margin:24px auto; border:1px solid var(--line);
      padding:14px; color:var(--fg2); white-space:pre-wrap;
    }
    @media (max-width:700px) {
      #sector-page .sector-wrap { padding:8px 6px 20px; }
      #sector-page .sector-head { gap:4px 10px; }
      #sector-page .sector-note { width:100%; margin-left:0; }
      #sector-page th, #sector-page td { padding:5px 5px; font-size:12px; }
      #sector-page td.sector-change { font-size:13px; }
      #sector-page .pct-graphic { font-size:12px; }
    }
  `;
  document.head.appendChild(style);

  const page = document.createElement("section");
  page.id = "sector-page";
  page.className = "hidden";
  page.innerHTML = `
    <div class="bar">
      <button id="sector-back" title="タイトルへ戻る">戻る</button>
      <button id="sector-theme" title="押すたびに配色が変わる">Color</button>
      <div class="spacer"></div>
      <div class="note" id="sector-status"></div>
    </div>
    <div class="sector-wrap" id="sector-body">
      <div class="sector-error">読み込み中…</div>
    </div>`;

  const saver = document.getElementById("saver");
  if (saver) document.body.insertBefore(page, saver);
  else document.body.appendChild(page);

  let previousSelected = null;
  let cache = null;
  const sortState = {
    demand: null,
    major: null,
    sector: null,
    industry: { key: "name", dir: "asc", source: "name" }
  };

  function fmt(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "-";
    return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
  }

  function fmtCap(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "-";
    return `${n.toFixed(2)}兆`;
  }

  function esc(v) {
    return String(v == null ? "" : v)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function jaCompare(a, b) {
    return String(a || "").localeCompare(String(b || ""), "ja", {
      sensitivity: "base",
      numeric: true
    });
  }

  function sortedRows(rows, kind) {
    const out = Array.from(rows || []);
    const state = sortState[kind];
    if (!state) return out;

    if (state.key === "change") {
      const sign = state.dir === "asc" ? 1 : -1;
      out.sort((a, b) => {
        const av = Number(a.change);
        const bv = Number(b.change);
        if (Number.isFinite(av) && Number.isFinite(bv) && av !== bv) return (av - bv) * sign;
        if (Number.isFinite(av) !== Number.isFinite(bv)) return Number.isFinite(av) ? -1 : 1;
        return jaCompare(a.name, b.name);
      });
      return out;
    }

    if (state.key === "name") {
      const sign = state.dir === "asc" ? 1 : -1;
      out.sort((a, b) => jaCompare(a.name, b.name) * sign);
    }
    return out;
  }

  function sortMark(kind, source) {
    const state = sortState[kind];
    if (!state || state.key !== "change" || state.source !== source) return "";
    return state.dir === "asc" ? " ▲" : " ▼";
  }

  function pctGraphic(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return '<span class="pct-graphic pct-empty">-</span>';
    const a = Math.abs(n);
    let cells;
    if (a >= 10) cells = 11;
    else if (a < 0.5) cells = 1;
    else cells = Math.min(10, Math.floor(a - 0.5) + 2);
    const neg = n < 0 ? "■".repeat(cells) : "";
    const pos = n >= 0 ? "□".repeat(cells) : "";
    return `<span class="pct-graphic" title="${esc(fmt(n))}">` +
      `<span class="pct-neg">${neg}</span><span class="pct-zero"></span><span class="pct-pos">${pos}</span></span>`;
  }

  function sortHeader(kind, source, label, cls) {
    return `<th class="${cls}"><button type="button" class="sector-sort-button" ` +
      `data-sector-sort="${kind}" data-sort-source="${source}" ` +
      `title="クリックで騰落率順を昇順・降順切替">${label}${sortMark(kind, source)}</button></th>`;
  }

  function rowsTable(rows, kind) {
    if (!rows || !rows.length) return '<div class="sector-error">該当データなし</div>';

    const showMajor = kind === "sector" || kind === "industry";
    const showSector = kind === "industry";
    const displayRows = sortedRows(rows, kind);

    const head = [
      '<th class="sector-name">名称</th>',
      sortHeader(kind, "graphic", "％graphic", "sector-graphic-cell"),
      sortHeader(kind, "change", "騰落率", "sector-change-col"),
      '<th class="sector-count-col">銘柄数</th>',
      '<th class="sector-cap-col">時価総額</th>',
      '<th class="sector-avg-cap-col">1社平均時価総額</th>',
      showSector ? '<th class="sector-parent-col">セクター</th>' : '',
      showMajor ? '<th class="sector-parent-col">大分類</th>' : ''
    ].join("");

    const body = displayRows.map((r) => {
      const breakdown = kind === "demand" && r.breakdown
        ? Object.entries(r.breakdown).map(([k, n]) => `${k}:${n}`).join(" / ")
        : "";
      const capCount = Number(r.marketCapCount) || 0;
      const count = Number(r.count) || 0;
      const countTitle = [breakdown, capCount !== count ? `時価総額取得:${capCount}/${count}` : ""]
        .filter(Boolean).join(" / ");
      const titleAttr = countTitle ? ` title="${esc(countTitle)}"` : "";
      return `<tr>` +
        `<th class="sector-name" title="${esc(r.name)}">${esc(r.name)}</th>` +
        `<td class="sector-graphic-cell">${pctGraphic(r.change)}</td>` +
        `<td class="sector-change sector-change-col">${fmt(r.change)}</td>` +
        `<td class="sector-count sector-count-col"${titleAttr}>${count}</td>` +
        `<td class="sector-cap sector-cap-col"${titleAttr}>${fmtCap(r.marketCapTrillion)}</td>` +
        `<td class="sector-cap sector-avg-cap-col"${titleAttr}>${fmtCap(r.avgMarketCapTrillion)}</td>` +
        `${showSector ? `<td class="sector-major sector-parent-col" title="${esc(r.sector)}">${esc(r.sector)}</td>` : ""}` +
        `${showMajor ? `<td class="sector-major sector-parent-col" title="${esc(r.major)}">${esc(r.major)}</td>` : ""}` +
        `</tr>`;
    }).join("");

    return `<table class="sector-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }

  function render(data) {
    cache = data;
    const body = document.getElementById("sector-body");
    const status = document.getElementById("sector-status");
    if (!body) return;
    const scrollTop = body.scrollTop;
    const scrollLeft = body.scrollLeft;
    const available = Number(data.available) || 0;
    const classified = Number(data.classified) || 0;
    if (status) status.textContent = data.date ? `${data.date}` : "";
    body.innerHTML = `
      <div class="sector-head">
        <span class="sector-title">日本株 セクター別</span>
        <span class="sector-meta">${esc(data.date || "-")}</span>
        <span class="sector-meta">使用 ${available}/${classified}銘柄</span>
        ${data.marketCapAsOf ? `<span class="sector-meta">時価総額 ${esc(data.marketCapAsOf)}</span>` : ""}
        <span class="sector-note">セクター・業種＝単純平均 ／ 内需・外需＝強1.0・通常0.5 ／ 時価総額は騰落率の加重に不使用</span>
      </div>
      <section class="sector-section">
        <h2>需要地域</h2>
        ${rowsTable(data.demand || [], "demand")}
      </section>
      <section class="sector-section">
        <h2>大分類</h2>
        ${rowsTable(data.major || [], "major")}
      </section>
      <section class="sector-section">
        <h2>セクター別</h2>
        ${rowsTable(data.sector || [], "sector")}
      </section>
      <section class="sector-section">
        <h2>業種別</h2>
        ${rowsTable(data.industry || [], "industry")}
      </section>`;
    body.scrollTop = scrollTop;
    body.scrollLeft = scrollLeft;
  }

  async function load() {
    const body = document.getElementById("sector-body");
    const status = document.getElementById("sector-status");
    if (status) status.textContent = "読み込み中…";
    try {
      const res = await fetch(`data/sector_today.json?t=${Date.now()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      render(data);
    } catch (err) {
      if (status) status.textContent = "データなし";
      if (body) body.innerHTML = `<div class="sector-error">セクター集計データを読み込めませんでした。\n毎夕の個別株更新後に自動生成されます。\n${esc(err && err.message ? err.message : err)}</div>`;
    }
  }

  function open() {
    previousSelected = menu.querySelector('button[aria-selected="true"]:not(#sector-menu-button)');
    menu.querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", "false"));
    sectorButton.setAttribute("aria-selected", "true");
    title.classList.add("hidden");
    page.classList.remove("hidden");
    load();
  }

  function close() {
    page.classList.add("hidden");
    title.classList.remove("hidden");
    sectorButton.setAttribute("aria-selected", "false");
    if (previousSelected && previousSelected.isConnected) previousSelected.setAttribute("aria-selected", "true");
  }

  sectorButton.addEventListener("mouseenter", () => {
    menu.querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", String(b === sectorButton)));
  });
  sectorButton.addEventListener("click", open);
  menu.querySelectorAll("button:not(#sector-menu-button)").forEach((b) => {
    b.addEventListener("mouseenter", () => sectorButton.setAttribute("aria-selected", "false"));
    b.addEventListener("click", () => sectorButton.setAttribute("aria-selected", "false"));
  });

  document.getElementById("sector-back").addEventListener("click", close);
  document.getElementById("sector-theme").addEventListener("click", () => {
    if (typeof nextTheme === "function") nextTheme();
    if (cache) render(cache);
  });

  document.getElementById("sector-body").addEventListener("click", (e) => {
    const button = e.target.closest("[data-sector-sort]");
    if (!button || !cache) return;
    const kind = button.dataset.sectorSort;
    const source = button.dataset.sortSource || "change";
    if (!Object.prototype.hasOwnProperty.call(sortState, kind)) return;

    const current = sortState[kind];
    const dir = current && current.key === "change" && current.dir === "desc" ? "asc" : "desc";
    sortState[kind] = { key: "change", dir, source };
    render(cache);
  });

  document.addEventListener("keydown", (e) => {
    if (page.classList.contains("hidden")) return;
    if (e.key === "Escape") {
      close();
      e.preventDefault();
    }
  });

  window.SectorPerformancePage = { open, close, load };
})();
