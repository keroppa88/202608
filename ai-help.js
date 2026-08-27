(function () {
  "use strict";
  if (typeof document === "undefined") return;

  const API_HELP = "価格データと最適化されたテクニカル指標に基づいてGeminiの高級AIが分析を行う。\n※一回10円ほどのAPI利用料金はKeroppaの自腹である。";
  const PROMPT_HELP = "価格データと最適化されたテクニカル指標、それに基づいた分析用のプロンプトを出力する。コピーして各自のAIチャットに貼ると分析が出力される。※Keroppaのお財布にノーダメージという利点がある。";

  function init() {
    const run = document.getElementById("ai-run");
    const prompt = document.getElementById("ai-prompt");
    if (!run || !prompt || document.getElementById("ai-help")) return;

    // PCではマウスを重ねたときにブラウザ標準の説明を出す。
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
      /* タイトル画面。見出しは26px、期間表示は大きいまま通常色にする。 */
      #title h1 { font-size:26px; }
      #title .sub { color:var(--fg); font-size:24px; }
      #title .hint { display:none !important; }

      /* 予測対象と比較銘柄を明確に分ける。 */
      #ai-analysis .ai-row {
        border:1px solid var(--fg2);
        padding:8px 10px;
        margin-bottom:18px;
      }
      #ai-analysis .ai-row:first-child {
        margin-bottom:24px;
      }
      /* 比較銘柄の見出しは、長いリストの縦中央ではなく枠の左上に置く。 */
      #ai-analysis .ai-row:nth-child(2) {
        align-items:start;
      }
      #ai-analysis .ai-row:nth-child(2) .ai-label {
        align-self:start;
        padding-top:5px;
      }
      @media (max-width:640px) {
        #ai-analysis .ai-row { padding:8px; }
        #ai-analysis .ai-row:first-child { margin-bottom:16px; }
        #ai-analysis .ai-row:nth-child(2) .ai-label { padding-top:0; }
      }

      /* セクター画面は薄暗い補助色を使わず、表の文字を通常の明るい色に統一する。 */
      #sector-page table.sector-table th,
      #sector-page table.sector-table td,
      #sector-page .sector-meta,
      #sector-page .sector-note,
      #sector-page .bar .note,
      #sector-page .pct-empty {
        color:var(--fg) !important;
      }

      #ai-help-modal {
        position:fixed; inset:0; z-index:10020; background:rgba(0,0,0,.72);
        display:flex; align-items:center; justify-content:center; padding:16px;
      }
      #ai-help-modal.hidden { display:none !important; }
      #ai-help-box {
        width:min(720px, 94vw); max-height:82vh; overflow:auto;
        background:var(--bg); color:var(--fg); border:2px solid var(--line);
      }
      #ai-help-head {
        display:flex; align-items:center; gap:8px; padding:7px 9px;
        border-bottom:1px solid var(--line); background:var(--panel);
        position:sticky; top:0;
      }
      #ai-help-head .title { color:var(--fg2); }
      #ai-help-head .spacer { flex:1; }
      #ai-help-head button {
        background:var(--panel); color:var(--fg); border:1px solid var(--line);
        font:inherit; padding:4px 12px; cursor:pointer;
      }
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

    // AI画面から戻ったときに説明だけ残らないようにする。
    document.getElementById("aiback")?.addEventListener("click", close);

    window.AiAnalysisHelp = { open, close };
  }

  function loadSectorView() {
    if (document.querySelector('script[data-sector-view="1"]')) return;
    const script = document.createElement("script");
    script.src = "sector-view.js";
    script.dataset.sectorView = "1";
    document.body.appendChild(script);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      init();
      loadSectorView();
    }, { once:true });
  } else {
    init();
    loadSectorView();
  }
})();
