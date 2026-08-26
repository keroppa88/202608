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
      width:min(1180px, 100%); margin:0 auto 14px;
    }
    #sector-page .sector-title { color:var(--fg2); font-size:18px; }
    #sector-page .sector-meta { color:var(--dim); }
    #sector-page .sector-note { color:var(--dim); font-size:12px; margin-left:auto; }
    #sector-page .sector-section { width:min(1180px, 100%); margin:0 auto 22px; }
    #sector-page .sector-section h2 {
      margin:0; padding:5px 8px; border:1px solid var(--line); border-bottom:0;
      color:var(--fg2); font-size:14px; font-weight:normal;
    }
    #sector-page table { width:100%; table-layout:auto; }
    #sector-page th, #sector-page td { padding:5px 8px; }
    #sector-page thead th { position:static; }
    #sector-page tbody th { position:static; }
    #sector-page td.sector-change { font-weight:bold; font-size:15px; }
    #sector-page td.sector-count { color:var(--dim); }
    #sector-page .sector-major { color:var(--dim); text-align:left; }
    #sector-page .sector-error {
      width:min(1180px, 100%); margin:24px auto; border:1px solid var(--line);
      padding:14px; color:var(--fg2); white-space:pre-wrap;
    }
    @media (max-width:700px) {
      #sector-page .sector-wrap { padding:8px 6px 20px; }
      #sector-page .sector-head { gap:4px 10px; }
      #sector-page .sector-note { width:100%; margin-left:0; }
      #sector-page th, #sector-page td { padding:5px 5px; font-size:12px; }
      #sector-page td.sector-change { font-size:13px; }
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

  function fmt(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "-";
    return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
  }

  function esc(v) {
    return String(v == null ? "" : v)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function rowsTable(rows, kind) {
    if (!rows || !rows.length) return '<div class="sector-error">該当データなし</div>';
    const showMajor = kind !== "demand" && kind !== "major";
    const showSector = kind === "industry";
    const head = [
      showMajor ? "<th>大分類</th>" : "",
      showSector ? "<th>セクター</th>" : "",
      "<th>名称</th><th>当日騰落率</th><th>銘柄数</th>"
    ].join("");
    const body = rows.map((r) => {
      const extra = kind === "demand" && r.breakdown
        ? ` title="${esc(Object.entries(r.breakdown).map(([k, n]) => `${k}:${n}`).join(" / "))}"`
        : "";
      return `<tr>${showMajor ? `<td class="sector-major">${esc(r.major)}</td>` : ""}` +
        `${showSector ? `<td class="sector-major">${esc(r.sector)}</td>` : ""}` +
        `<th>${esc(r.name)}</th>` +
        `<td class="sector-change">${fmt(r.change)}</td>` +
        `<td class="sector-count"${extra}>${Number(r.count) || 0}</td></tr>`;
    }).join("");
    return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }

  function render(data) {
    cache = data;
    const body = document.getElementById("sector-body");
    const status = document.getElementById("sector-status");
    if (!body) return;
    const available = Number(data.available) || 0;
    const classified = Number(data.classified) || 0;
    if (status) status.textContent = data.date ? `${data.date}` : "";
    body.innerHTML = `
      <div class="sector-head">
        <span class="sector-title">日本株 セクター別</span>
        <span class="sector-meta">${esc(data.date || "-")}</span>
        <span class="sector-meta">使用 ${available}/${classified}銘柄</span>
        <span class="sector-note">セクター・業種＝単純平均 ／ 内需・外需＝強1.0・通常0.5</span>
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

  document.addEventListener("keydown", (e) => {
    if (page.classList.contains("hidden")) return;
    if (e.key === "Escape") {
      close();
      e.preventDefault();
    }
  });

  window.SectorPerformancePage = { open, close, load };
})();
