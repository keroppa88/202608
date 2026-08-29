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
    help.title = "AI分析・オリジナル指数・セクター別の仕組みを説明する";
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
      #ai-help-modal { position:fixed; inset:0; z-index:10020; background:rgba(0,0,0,.72); display:flex; align-items:center; justify-content:center; padding:16px; }
      #ai-help-modal.hidden { display:none !important; }
      #ai-help-box { width:min(820px, 94vw); max-height:86vh; overflow:auto; background:var(--bg); color:var(--fg); border:2px solid var(--line); }
      #ai-help-head { display:flex; align-items:center; gap:8px; padding:7px 9px; border-bottom:1px solid var(--line); background:var(--panel); position:sticky; top:0; }
      #ai-help-head .title { color:var(--fg2); }
      #ai-help-head .spacer { flex:1; }
      #ai-help-head button { background:var(--panel); color:var(--fg); border:1px solid var(--line); font:inherit; padding:4px 12px; cursor:pointer; }
      #ai-help-body { padding:14px 16px 18px; line-height:1.75; }
      #ai-help-body h3 { margin:0 0 5px; font-size:1em; color:var(--fg2); }
      #ai-help-body p { margin:0 0 18px; white-space:pre-line; }
      #ai-help-body p:last-child { margin-bottom:0; }
      #ai-help-body .help-section { margin-bottom:18px; padding:12px 14px; border:1px solid var(--line); background:var(--panel); }
      #ai-help-body .help-section:last-child { margin-bottom:0; }
      #ai-help-body .help-section p { margin-bottom:10px; }
      #ai-help-body .help-section p:last-child { margin-bottom:0; }
    `;
    document.head.appendChild(style);
    const modal = document.createElement("div");
    modal.id = "ai-help-modal";
    modal.className = "hidden";
    modal.innerHTML = `
      <div id="ai-help-box" role="dialog" aria-modal="true" aria-label="機能説明">
        <div id="ai-help-head">
          <span class="title">説明</span>
          <div class="spacer"></div>
          <button id="ai-help-close" type="button">閉じる</button>
        </div>
        <div id="ai-help-body">
          <section class="help-section">
            <h3>AI分析の概要</h3>
            <p>予測対象を1銘柄、分析用比較銘柄を0〜10銘柄選ぶ。予測対象は約10年の価格から、既定のテクニカル指標、銘柄ごとに自動調整した指標、過去の類似局面、比較銘柄との相関を計算する。AIは計算済みの数字を文章化する。</p>
            <p>予測対象：日本個別株は収録期間400日以上、Yahoo系列は当年40足以上、その他は250足以上かつ当年更新あり。比較対象：日本個別株は90日以上、その他は40足以上かつ当年更新あり。不足する系列は選択肢から除外する。</p>
            <h3>APIによるAI分析</h3>
            <p>${API_HELP}</p>
            <h3>AI分析用プロンプト出力</h3>
            <p>${PROMPT_HELP}</p>
          </section>
          <section class="help-section">
            <h3>日本株オリジナル10指数</h3>
            <p>既存の固定銘柄を10のテーマへ分類した独自指数。銘柄の指数間重複を許容し、各銘柄の騰落率を寄与度「大1.0・中0.7・小0.5」で加重平均する。時価総額加重ではない。</p>
            <p>指数値は2026年最初の取引日を100とする。騰落率、年初来騰落率、構成銘柄数、構成銘柄の時価総額合計を表示する。時価総額は表示用で、指数騰落率の計算には使わない。TOPIX・日経平均を比較表示する。</p>
          </section>
          <section class="help-section">
            <h3>日本株セクター別</h3>
            <p>対象銘柄を「需要地域 → 大分類 → セクター → 業種」の階層で分類する。セクター・業種の騰落率は構成銘柄の単純平均。内需・外需は「強1.0・通常0.5」で集計する。</p>
            <p>時価総額は騰落率の加重には使わず、合計・平均の表示と時価総額マップの面積に使用する。分類または当日価格を取得できない銘柄は集計対象外とし、画面上部の「使用銘柄数／分類銘柄数」で示す。</p>
          </section>
        </div>
      </div>`;
    document.body.appendChild(modal);
    const open = () => modal.classList.remove("hidden");
    const close = () => modal.classList.add("hidden");
    help.addEventListener("click", open);
    document.querySelector('#titleMenu [data-go="help"]')?.addEventListener("click", open);
    document.getElementById("ai-help-close").addEventListener("click", close);
    modal.addEventListener("click", (e) => { if (e.target === modal) close(); });
    document.getElementById("aiback")?.addEventListener("click", close);
    window.AiAnalysisHelp = { open, close };
  }

  function loadSectorHeatColorMode() {
    if (document.querySelector('script[data-sector-heat-color-mode="1"]')) return;
    const script = document.createElement("script");
    script.src = window.sobaAssetUrl ? window.sobaAssetUrl("sector-heat-color-mode.js") : "sector-heat-color-mode.js";
    script.dataset.sectorHeatColorMode = "1";
    document.body.appendChild(script);
  }

  function loadSectorTreemap() {
    if (document.querySelector('script[data-sector-treemap="1"]')) return;
    const script = document.createElement("script");
    script.src = window.sobaAssetUrl ? window.sobaAssetUrl("sector-treemap.js") : "sector-treemap.js";
    script.dataset.sectorTreemap = "1";
    document.body.appendChild(script);
  }

  function loadSectorAI() {
    if (document.querySelector('script[data-sector-ai="1"]')) return;
    const script = document.createElement("script");
    script.src = window.sobaAssetUrl ? window.sobaAssetUrl("sector-ai.js") : "sector-ai.js";
    script.dataset.sectorAi = "1";
    document.body.appendChild(script);
  }

  function loadSectorHeatmap() {
    if (!document.querySelector('script[data-sector-heatmap="1"]')) {
      const script = document.createElement("script");
      script.src = window.sobaAssetUrl ? window.sobaAssetUrl("sector-heatmap.js") : "sector-heatmap.js";
      script.dataset.sectorHeatmap = "1";
      document.body.appendChild(script);
    }
    loadSectorHeatColorMode();
    loadSectorTreemap();
    loadSectorAI();
  }

  function loadSectorView() {
    const existing = document.querySelector('script[data-sector-view="1"]');
    if (existing) {
      if (window.SectorPerformancePage) loadSectorHeatmap();
      else existing.addEventListener("load", loadSectorHeatmap, { once:true });
      return;
    }
    const script = document.createElement("script");
    script.src = window.sobaAssetUrl ? window.sobaAssetUrl("sector-view.js") : "sector-view.js";
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
