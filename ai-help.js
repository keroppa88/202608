(function () {
  "use strict";
  if (typeof document === "undefined") return;

  const API_HELP = "価格データと最適化されたテクニカル指標に基づいてGeminiの高級AIが分析を行う。\n※一回10円ほどのAPI利用料金はKeroppaの自腹である。";
  const PROMPT_HELP = "価格データと最適化されたテクニカル指標、それに基づいた分析用のプロンプトを出力する。コピーして各自のAIチャットに貼ると分析が出力される。※Keroppaのお財布にノーダメージという利点がある。";

  function init() {
    const run = document.getElementById("ai-run");
    const prompt = document.getElementById("ai-prompt");
    if (!run || !prompt || document.getElementById("ai-help")) return;
    run.title = API_HELP;
    prompt.title = PROMPT_HELP;
    const help = document.createElement("button");
    help.id = "ai-help";
    help.className = "ai-top-action";
    help.type = "button";
    help.textContent = "説明";
    help.title = "AI分析の各ボタンについて説明する";
    prompt.insertAdjacentElement("afterend", help);
    const style = document.createElement("style");
    style.textContent = `
      #title h1 { font-size:26px; }
      #title .sub { color:var(--fg); font-size:24px; }
      #title .hint { display:none !important; }
      #ai-analysis .ai-row { border:1px solid var(--fg2); padding:8px 10px; margin-bottom:18px; }
      #ai-analysis .ai-row:first-child { margin-bottom:24px; }
      #ai-analysis .ai-row:nth-child(2) { align-items:start; }
      #ai-analysis .ai-row:nth-child(2) .ai-label { align-self:start; padding-top:5px; }
      @media (max-width:640px) {
        #ai-analysis .ai-row { padding:8px; }
        #ai-analysis .ai-row:first-child { margin-bottom:16px; }
        #ai-analysis .ai-row:nth-child(2) .ai-label { padding-top:0; }
      }
      #sector-page table.sector-table th,
      #sector-page table.sector-table td,
      #sector-page .sector-meta,
      #sector-page .sector-note,
      #sector-page .bar .note,
      #sector-page .pct-empty { color:var(--fg) !important; }

      /* 業種別の四角マス・ヒートマップ。文字サイズは前設定の1.5倍。 */
      #sector-page .sector-treemap-view {
        font-size:27px !important;
        line-height:1.2 !important;
      }
      #sector-page .sector-treemap-view .sector-heatmap-head {
        gap:10px 22px !important;
        margin-bottom:14px !important;
      }
      #sector-page .sector-treemap-view .sector-heatmap-title {
        font-size:36px !important;
        font-weight:bold !important;
      }
      #sector-page .sector-treemap-view .sector-heatmap-meta {
        font-size:27px !important;
      }
      #sector-page .sector-treemap-view .sector-heatmap-legend,
      #sector-page .sector-treemap-view .sector-heatmap-legend b,
      #sector-page .sector-treemap-view .sector-heatmap-legend span {
        font-size:26px !important;
      }
      #sector-page .sector-treemap-view .sector-treemap-sector-label {
        font-size:27px !important;
        padding:4px 7px !important;
      }
      #sector-page .sector-treemap-view .sector-treemap-tile.sector-heat-node {
        gap:4px !important;
        padding:6px !important;
        line-height:1.15 !important;
      }
      #sector-page .sector-treemap-view .sector-treemap-tile .sector-treemap-name {
        font-size:27px !important;
        font-weight:bold !important;
      }
      #sector-page .sector-treemap-view .sector-treemap-tile .sector-heat-change {
        font-size:30px !important;
        font-weight:bold !important;
      }
      #sector-page .sector-treemap-view .sector-treemap-tile .sector-treemap-cap {
        font-size:23px !important;
      }
      #sector-page .sector-treemap-view .sector-treemap-tile.compact {
        padding:4px !important;
        gap:2px !important;
      }
      #sector-page .sector-treemap-view .sector-treemap-tile.compact .sector-treemap-name {
        font-size:24px !important;
      }
      #sector-page .sector-treemap-view .sector-treemap-tile.compact .sector-heat-change {
        font-size:26px !important;
      }
      #sector-page .sector-treemap-view .sector-treemap-tile.tiny .sector-treemap-name {
        font-size:21px !important;
      }
      #sector-page .sector-treemap-view .sector-treemap-tile.tiny .sector-heat-change {
        display:block !important;
        font-size:23px !important;
      }
      #sector-page .sector-treemap-view .sector-treemap-note {
        font-size:24px !important;
        margin-top:10px !important;
      }
      @media (max-width:700px) {
        #sector-page .sector-treemap-view { font-size:26px !important; }
        #sector-page .sector-treemap-view .sector-heatmap-title { font-size:33px !important; }
        #sector-page .sector-treemap-view .sector-heatmap-meta { font-size:26px !important; }
        #sector-page .sector-treemap-view .sector-heatmap-legend,
        #sector-page .sector-treemap-view .sector-heatmap-legend b,
        #sector-page .sector-treemap-view .sector-heatmap-legend span { font-size:24px !important; }
        #sector-page .sector-treemap-view .sector-treemap-sector-label { font-size:24px !important; }
        #sector-page .sector-treemap-view .sector-treemap-note { font-size:23px !important; }
      }

      #ai-help-modal { position:fixed; inset:0; z-index:10020; background:rgba(0,0,0,.72); display:flex; align-items:center; justify-content:center; padding:16px; }
      #ai-help-modal.hidden { display:none !important; }
      #ai-help-box { width:min(720px, 94vw); max-height:82vh; overflow:auto; background:var(--bg); color:var(--fg); border:2px solid var(--line); }
      #ai-help-head { display:flex; align-items:center; gap:8px; padding:7px 9px; border-bottom:1px solid var(--line); background:var(--panel); position:sticky; top:0; }
      #ai-help-head .title { color:var(--fg2); }
      #ai-help-head .spacer { flex:1; }
      #ai-help-head button { background:var(--panel); color:var(--fg); border:1px solid var(--line); font:inherit; padding:4px 12px; cursor:pointer; }
      #ai-help-body { padding:14px 16px 18px; line-height:1.75; }
      #ai-help-body h3 { margin:0 0 5px; font-size:1em; color:var(--fg2); }
      #ai-help-body p { margin:0 0 18px; white-space:pre-line; }
      #ai-help-body p:last-child { margin-bottom:0; }
    `;
    document.head.appendChild(style);
    const modal = document.createElement("div");
    modal.id = "ai-help-modal";
    modal.className = "hidden";
    modal.innerHTML = `
      <div id="ai-help-box" role="dialog" aria-modal="true" aria-label="AI分析の説明">
        <div id="ai-help-head">
          <span class="title">AI分析の説明</span>
          <div class="spacer"></div>
          <button id="ai-help-close" type="button">閉じる</button>
        </div>
        <div id="ai-help-body">
          <h3>APIによるAI分析</h3>
          <p>${API_HELP}</p>
          <h3>AI分析用プロンプト出力</h3>
          <p>${PROMPT_HELP}</p>
        </div>
      </div>`;
    document.body.appendChild(modal);
    const open = () => modal.classList.remove("hidden");
    const close = () => modal.classList.add("hidden");
    help.addEventListener("click", open);
    document.getElementById("ai-help-close").addEventListener("click", close);
    modal.addEventListener("click", (e) => { if (e.target === modal) close(); });
    document.getElementById("aiback")?.addEventListener("click", close);
    window.AiAnalysisHelp = { open, close };
  }

  function loadSectorHeatColorMode() {
    if (document.querySelector('script[data-sector-heat-color-mode="1"]')) return;
    const script = document.createElement("script");
    script.src = "sector-heat-color-mode.js";
    script.dataset.sectorHeatColorMode = "1";
    document.body.appendChild(script);
  }

  function loadSectorTreemap() {
    if (document.querySelector('script[data-sector-treemap="1"]')) return;
    const script = document.createElement("script");
    script.src = "sector-treemap.js";
    script.dataset.sectorTreemap = "1";
    document.body.appendChild(script);
  }

  function loadSectorHeatmap() {
    if (!document.querySelector('script[data-sector-heatmap="1"]')) {
      const script = document.createElement("script");
      script.src = "sector-heatmap.js";
      script.dataset.sectorHeatmap = "1";
      document.body.appendChild(script);
    }
    loadSectorHeatColorMode();
    loadSectorTreemap();
  }

  function loadSectorView() {
    const existing = document.querySelector('script[data-sector-view="1"]');
    if (existing) {
      if (window.SectorPerformancePage) loadSectorHeatmap();
      else existing.addEventListener("load", loadSectorHeatmap, { once:true });
      return;
    }
    const script = document.createElement("script");
    script.src = "sector-view.js";
    script.dataset.sectorView = "1";
    script.addEventListener("load", loadSectorHeatmap, { once:true });
    document.body.appendChild(script);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => { init(); loadSectorView(); }, { once:true });
  } else {
    init();
    loadSectorView();
  }
})();
