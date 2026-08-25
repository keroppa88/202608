(function () {
  "use strict";
  if (typeof document === "undefined") return;

  const menu = document.getElementById("titleMenu");
  if (menu) {
    menu.innerHTML = [
      '<button data-go="ai" aria-selected="true">AI分析</button>',
      '<button data-go="sheet">表</button>',
      '<button data-go="chart">チャート</button>',
      '<button data-go="correlation">相関係数</button>',
      '<button data-go="technical">テクニカル</button>'
    ].join("");
  }
  const newItems = menu ? [...menu.querySelectorAll("button")] : [];
  let menuCursor = 0;
  function drawMenuCursor() {
    newItems.forEach((button, i) => button.setAttribute("aria-selected", String(i === menuCursor)));
  }

  const style = document.createElement("style");
  style.textContent = `
    #ai-analysis, #correlation-page { height:100%; display:flex; flex-direction:column; }
    #technical #technical-splitter,
    #technical #technical-bottom,
    #technical #tcomp,
    #technical #tauto,
    #technical #tai,
    #technical #ttxt { display:none !important; }
    #technical .technical-top { flex:1 1 auto !important; flex-basis:auto !important; min-height:0; }
    #correlation-page .technical-bottom { display:flex !important; flex:1 1 auto; min-height:0; }
    #ai-analysis .ai-wrap {
      width:min(920px, 100%); margin:0 auto; padding:18px 14px 28px;
      overflow:auto; flex:1; scrollbar-color:var(--fg) var(--bg); scrollbar-width:thin;
    }
    #ai-analysis .ai-row {
      display:grid; grid-template-columns:170px minmax(0, 1fr); gap:10px;
      align-items:center; margin-bottom:12px;
    }
    #ai-analysis .ai-label { color:var(--fg2); }
    #ai-analysis select,
    #ai-analysis .ai-add,
    #ai-analysis .ai-run,
    #ai-analysis .ai-sub button {
      background:var(--panel); color:var(--fg); border:1px solid var(--line);
      font:inherit; padding:5px 8px;
    }
    #ai-analysis select { width:100%; min-width:0; }
    #ai-analysis .ai-subs { display:flex; flex-direction:column; gap:6px; }
    #ai-analysis .ai-sub { display:flex; gap:6px; align-items:center; }
    #ai-analysis .ai-sub select { flex:1; }
    #ai-analysis .ai-sub button { cursor:pointer; padding:5px 10px; }
    #ai-analysis .ai-actions { display:flex; gap:8px; margin:14px 0; flex-wrap:wrap; }
    #ai-analysis .ai-add, #ai-analysis .ai-run { cursor:pointer; }
    #ai-analysis .ai-run { padding:7px 24px; border-width:2px; }
    #ai-analysis .ai-run:disabled, #ai-analysis .ai-add:disabled { color:var(--dim); border-color:var(--dim); cursor:default; }
    #ai-analysis .ai-result {
      min-height:160px; border-top:1px solid var(--line); padding-top:12px;
      white-space:pre-wrap; line-height:1.8;
    }
    #ai-analysis .ai-empty { color:var(--dim); }
    @media (max-width:640px) {
      #ai-analysis .ai-row { grid-template-columns:1fr; gap:5px; }
    }
  `;
  document.head.appendChild(style);

  const aiPage = document.createElement("section");
  aiPage.id = "ai-analysis";
  aiPage.className = "hidden";
  aiPage.innerHTML = `
    <div class="bar">
      <button id="aiback" title="タイトルへ戻る">戻る</button>
      <button id="aitheme" title="押すたびに配色が変わる">Color</button>
      <div class="spacer"></div>
      <div class="note" id="aistatus"></div>
    </div>
    <div class="ai-wrap">
      <div class="ai-row">
        <div class="ai-label">予測対象銘柄</div>
        <select id="ai-main" aria-label="予測対象銘柄"></select>
      </div>
      <div class="ai-row">
        <div class="ai-label">分析用比較銘柄 <span id="ai-sub-count">0/10</span></div>
        <div id="ai-subs" class="ai-subs"></div>
      </div>
      <div class="ai-actions">
        <button id="ai-add" class="ai-add">＋ 比較銘柄</button>
        <button id="ai-run" class="ai-run">分析する</button>
      </div>
      <div id="ai-result" class="ai-result"><span class="ai-empty">銘柄を選んで「分析する」を押す。</span></div>
    </div>`;

  const corrPage = document.createElement("section");
  corrPage.id = "correlation-page";
  corrPage.className = "hidden";
  corrPage.innerHTML = `
    <div class="bar">
      <button id="rcback" title="タイトルへ戻る">戻る</button>
      <button id="rtheme" title="押すたびに配色が変わる">Color</button>
      <div class="spacer"></div>
    </div>`;

  const saver = document.getElementById("saver");
  if (saver) {
    document.body.insertBefore(aiPage, saver);
    document.body.insertBefore(corrPage, saver);
  } else {
    document.body.append(aiPage, corrPage);
  }

  let aiCatalog = [];
  let aiBusy = false;
  const MAX_SUBS = 10;

  function signature() {
    return [settings.corrAiMain, ...settings.corrAiSubs].join("\n");
  }

  function clearAiResult() {
    const result = document.getElementById("ai-result");
    if (result) result.innerHTML = '<span class="ai-empty">条件を選んで「分析する」を押す。</span>';
  }

  function setAiEnabled(enabled) {
    document.getElementById("ai-main").disabled = !enabled;
    document.getElementById("ai-add").disabled = !enabled || settings.corrAiSubs.length >= MAX_SUBS;
    document.querySelectorAll("#ai-subs select, #ai-subs button").forEach((el) => { el.disabled = !enabled; });
  }

  function normalizeAiSelection() {
    const has = (key) => aiCatalog.some((c) => c.key === key);
    if (!settings.corrAiMain || !has(settings.corrAiMain)) {
      settings.corrAiMain = has(settings.techKey) ? settings.techKey : (aiCatalog[0] ? aiCatalog[0].key : "");
    }
    settings.corrAiSubs = [...new Set(settings.corrAiSubs || [])]
      .filter((key) => has(key) && key !== settings.corrAiMain)
      .slice(0, MAX_SUBS);
    saveSettings();
  }

  function drawAiControls() {
    const main = document.getElementById("ai-main");
    main.innerHTML = "";
    fillPicker(main, aiCatalog, settings.corrAiMain, false);
    main.value = settings.corrAiMain;
    main.onchange = () => {
      settings.corrAiMain = main.value;
      settings.corrAiSubs = settings.corrAiSubs.filter((key) => key !== settings.corrAiMain);
      saveSettings();
      clearAiResult();
      drawAiControls();
    };

    const subs = document.getElementById("ai-subs");
    subs.innerHTML = "";
    settings.corrAiSubs.forEach((key, i) => {
      const row = document.createElement("div");
      row.className = "ai-sub";
      const sel = document.createElement("select");
      sel.setAttribute("aria-label", `分析用比較銘柄 ${i + 1}`);
      fillPicker(sel, aiCatalog, key, false);
      sel.value = key;
      sel.addEventListener("change", () => {
        const next = sel.value;
        if (next === settings.corrAiMain || settings.corrAiSubs.some((k, j) => j !== i && k === next)) {
          sel.value = settings.corrAiSubs[i];
          document.getElementById("aistatus").textContent = "同じ銘柄は重複して選べない";
          return;
        }
        settings.corrAiSubs[i] = next;
        saveSettings();
        clearAiResult();
      });
      const del = document.createElement("button");
      del.textContent = "×";
      del.title = "比較銘柄から外す";
      del.addEventListener("click", () => {
        settings.corrAiSubs.splice(i, 1);
        saveSettings();
        clearAiResult();
        drawAiControls();
      });
      row.append(sel, del);
      subs.appendChild(row);
    });
    document.getElementById("ai-sub-count").textContent = `${settings.corrAiSubs.length}/${MAX_SUBS}`;
    document.getElementById("ai-add").disabled = aiBusy || settings.corrAiSubs.length >= MAX_SUBS;
  }

  async function openAiPage() {
    titleEl.classList.add("hidden");
    corrPage.classList.add("hidden");
    aiPage.classList.remove("hidden");
    document.getElementById("aistatus").textContent = "銘柄一覧を読み込み中…";
    if (!aiCatalog.length) aiCatalog = await buildCatalog(String(new Date().getFullYear()));
    normalizeAiSelection();
    drawAiControls();
    document.getElementById("aistatus").textContent = "";
  }

  function closeAiPage() {
    aiPage.classList.add("hidden");
    titleEl.classList.remove("hidden");
  }

  function openCorrelationPage() {
    titleEl.classList.add("hidden");
    aiPage.classList.add("hidden");
    corrPage.classList.remove("hidden");
    renderCorrelations();
  }

  function closeCorrelationPage() {
    closeCorrInfo();
    corrPage.classList.add("hidden");
    titleEl.classList.remove("hidden");
  }

  async function buildStandaloneAiPayload(progress) {
    const key = settings.corrAiMain;
    const endYear = new Date().getFullYear();

    progress("価格を読んでいます…");
    const rows = await techRows(key, endYear, AI_TECH_YEARS);
    if (rows.length < 250) throw new Error(`足が ${rows.length}日しかない`);
    const at = rows.length - 1;
    const catalog = aiCatalog.length ? aiCatalog : await buildCatalog(String(endYear));
    const name = labelOf(key, catalog);
    const from = Math.min(250, Math.floor(rows.length / 4));

    progress("既定の数字で見ています…");
    const base = JSON.parse(JSON.stringify(DEFAULT_TECH_PARAMS));
    const indBase = techIndicators(rows, base);

    progress("いちばん合う数字を探しています…");
    const tuned = techAutoFit(rows, from, rows.length - 1, base);
    const indTuned = techIndicators(rows, tuned);

    progress("似た局面を探しています…");
    const like = {
      short: aiLike(indTuned, rows, AI_LIKE_SHORT, at),
      long: aiLike(indTuned, rows, AI_LIKE_LONG, at)
    };

    const backRow = (ind, fields) => {
      const out = {};
      AI_TECH_BACK.forEach((n) => {
        const i = at - n;
        out[n] = i >= 0 ? aiTechRow(ind, rows, i, fields) : null;
      });
      return out;
    };
    const recent = [];
    for (let i = Math.max(0, at - AI_TECH_RECENT + 1); i <= at; i++) {
      recent.push(aiTechRow(indTuned, rows, i, AI_TECH_FIELDS));
    }

    progress(settings.corrAiSubs.length ? "比較銘柄との関係を計算しています…" : "分析データをまとめています…");
    let corr = null;
    try {
      corr = await buildCorrAiPayload(catalog, progress);
    } catch (e) {
      corr = { error: String(e && e.message ? e.message : e) };
    }

    return {
      kind: "tech",
      name,
      asOf: rows[at].d,
      span: {
        from: rows[0].d,
        to: rows[at].d,
        rows: rows.length,
        years: aiRound(rows.length / 250, 1)
      },
      params: { base, tuned },
      base: {
        now: aiTechRow(indBase, rows, at, AI_BASE_FIELDS),
        back: backRow(indBase, AI_BASE_FIELDS)
      },
      tuned: {
        recent,
        back: backRow(indTuned, AI_TECH_FIELDS)
      },
      like,
      corr
    };
  }

  async function runAiAnalysis() {
    if (aiBusy || !settings.corrAiMain) return;
    aiBusy = true;
    setAiEnabled(false);
    const run = document.getElementById("ai-run");
    const status = document.getElementById("aistatus");
    const result = document.getElementById("ai-result");
    run.disabled = true;
    run.textContent = "分析中…";
    const requested = signature();
    const progress = (text) => { status.textContent = text; };
    try {
      const payload = await buildStandaloneAiPayload(progress);
      const body = JSON.stringify(payload);
      progress(`送信 ${(body.length / 1024).toFixed(1)}KB`);
      if (!AI_ENDPOINT) throw new Error("AIの中継先が設定されていない");
      const res = await fetch(AI_ENDPOINT, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body
      });
      const raw = await res.text();
      if (!res.ok) throw new Error(`HTTP ${res.status}\n${raw}`);
      let answer = raw;
      try {
        const json = JSON.parse(raw);
        answer = json.text || json.error || raw;
      } catch (_) { }
      if (requested !== signature()) {
        status.textContent = "分析中に条件が変わったため結果を破棄した";
        return;
      }
      result.textContent = answer;
      status.textContent = `${payload.name}　${payload.asOf}　比較 ${settings.corrAiSubs.length}銘柄`;
    } catch (e) {
      result.textContent = `分析できなかった\n${e && e.message ? e.message : e}`;
      status.textContent = "AI分析に失敗";
    } finally {
      aiBusy = false;
      run.disabled = false;
      run.textContent = "分析する";
      setAiEnabled(true);
      drawAiControls();
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const bottom = document.getElementById("technical-bottom");
    if (bottom) corrPage.appendChild(bottom);

    const oldBackToTitle = backToTitle;
    backToTitle = function () {
      aiPage.classList.add("hidden");
      corrPage.classList.add("hidden");
      oldBackToTitle();
    };

    openTechnical = function () {
      titleEl.classList.add("hidden");
      techEl.classList.remove("hidden");
      drawTechParams();
      drawTechnical();
    };
    backFromTechnical = function () {
      closeTechChart();
      closeTechCompare();
      closeTechPick();
      techEl.classList.add("hidden");
      titleEl.classList.remove("hidden");
    };
    pickTechKey = function (key) {
      closeTechPick();
      if (key === settings.techKey) return;
      settings.techKey = key;
      saveSettings();
      drawTechnical();
    };

    setCorrAiDefaults = function (catalog) {
      const has = (key) => catalog.some((c) => c.key === key);
      if (!settings.corrAiMain || !has(settings.corrAiMain)) {
        settings.corrAiMain = settings.corrColumns.find(has) || (catalog[0] ? catalog[0].key : "");
      }
      settings.corrAiSubs = [...new Set(settings.corrAiSubs || [])]
        .filter((key) => has(key) && key !== settings.corrAiMain)
        .slice(0, MAX_AI_SUBS);
      saveSettings();
    };

    const openMenuItem = (button) => {
      if (!button || button.disabled) return;
      const go = button.dataset.go;
      if (go === "ai") openAiPage();
      else if (go === "sheet") openSheet();
      else if (go === "chart") openCharts();
      else if (go === "correlation") openCorrelationPage();
      else if (go === "technical") openTechnical();
    };
    newItems.forEach((button, i) => {
      button.addEventListener("mouseenter", () => { menuCursor = i; drawMenuCursor(); });
      button.addEventListener("click", () => { menuCursor = i; drawMenuCursor(); openMenuItem(button); });
    });
    drawMenuCursor();

    document.getElementById("aiback").addEventListener("click", closeAiPage);
    document.getElementById("aitheme").addEventListener("click", nextTheme);
    document.getElementById("rcback").addEventListener("click", closeCorrelationPage);
    document.getElementById("rtheme").addEventListener("click", () => {
      nextTheme();
      if (corrState) drawCorrelationResults();
    });
    document.getElementById("ai-run").addEventListener("click", runAiAnalysis);
    document.getElementById("ai-add").addEventListener("click", () => {
      if (settings.corrAiSubs.length >= MAX_SUBS) return;
      const first = aiCatalog.find((c) => c.key !== settings.corrAiMain && !settings.corrAiSubs.includes(c.key));
      if (!first) return;
      settings.corrAiSubs.push(first.key);
      saveSettings();
      clearAiResult();
      drawAiControls();
    });
  });

  document.addEventListener("keydown", (e) => {
    if (!titleEl.classList.contains("hidden")) {
      if (e.key === "ArrowDown") {
        menuCursor = (menuCursor + 1) % newItems.length;
        drawMenuCursor();
        e.preventDefault();
        e.stopImmediatePropagation();
      } else if (e.key === "ArrowUp") {
        menuCursor = (menuCursor - 1 + newItems.length) % newItems.length;
        drawMenuCursor();
        e.preventDefault();
        e.stopImmediatePropagation();
      } else if (e.key === "Enter") {
        const button = newItems[menuCursor];
        if (button) button.click();
        e.preventDefault();
        e.stopImmediatePropagation();
      }
      return;
    }
    const active = !aiPage.classList.contains("hidden") || !corrPage.classList.contains("hidden");
    if (!active) return;
    if (e.key === "Escape") {
      if (!corrInfoModal.classList.contains("hidden")) closeCorrInfo();
      else if (!aiPage.classList.contains("hidden")) closeAiPage();
      else closeCorrelationPage();
      e.preventDefault();
    }
    e.stopImmediatePropagation();
  }, true);
})();
