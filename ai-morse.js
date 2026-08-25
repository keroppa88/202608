(function () {
  "use strict";
  if (typeof document === "undefined") return;

  // 固定文「エーアイデブンセキチュウ」。
  // 和文モールスでは小書き「ュ」を独立させず「ユ」として扱う。
  // binary リポジトリの KANA_MORSE_TABLE と同じ符号・時間比を使う。
  const MESSAGE = "エーアイデブンセキチユウ";
  const CODES = [
    "-.---", // エ
    ".--.-", // ー
    "--.--", // ア
    ".-",    // イ
    ".-.--", // テ（デの清音）
    "..",    // 濁点
    "--..",  // フ（ブの清音）
    "..",    // 濁点
    ".-.-.", // ン
    ".---.", // セ
    "-.-..", // キ
    "..-.",  // チ
    "-..--", // ユ
    "..-"    // ウ
  ];

  const UNIT = 0.05;       // binary の和文モールス推奨値: 50ms
  const FREQ = 500;        // binary の既定ベース周波数
  const VOLUME = 0.075;
  const LOOP_GAP = 0.8;    // 文を言い切ってから次の反復まで
  const RAMP = 0.003;

  let ctx = null;
  let running = false;
  let loopTimer = 0;
  let oscillator = null;
  let phraseGain = null;
  let stopObserver = null;

  function audioContext() {
    if (ctx) return ctx;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return null;
    ctx = new AudioContextClass();
    return ctx;
  }

  function schedulePhrase() {
    if (!running) return;
    const ac = audioContext();
    if (!ac) return;

    const osc = ac.createOscillator();
    const gain = ac.createGain();
    oscillator = osc;
    phraseGain = gain;
    osc.type = "sine";
    osc.frequency.value = FREQ;
    gain.gain.value = 0;
    osc.connect(gain);
    gain.connect(ac.destination);

    let t = ac.currentTime + 0.025;
    const start = t;

    function tone(units) {
      const dur = units * UNIT;
      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(VOLUME, t + RAMP);
      gain.gain.setValueAtTime(VOLUME, Math.max(t + RAMP, t + dur - RAMP));
      gain.gain.linearRampToValueAtTime(0, t + dur);
      t += dur + UNIT; // 符号要素間 = 1単位
    }

    CODES.forEach((code, codeIndex) => {
      for (const symbol of code) tone(symbol === "." ? 1 : 3);
      // tone() の末尾ですでに1単位空けているので、文字間3単位にするため+2。
      if (codeIndex < CODES.length - 1) t += UNIT * 2;
    });

    // 末尾に反復間隔を置く。
    t += LOOP_GAP;
    osc.start(start);
    osc.stop(t);

    const delay = Math.max(50, Math.round((t - ac.currentTime) * 1000));
    loopTimer = window.setTimeout(() => {
      oscillator = null;
      phraseGain = null;
      if (running) schedulePhrase();
    }, delay);
  }

  function startAnalysisMorse() {
    if (running) return;
    const ac = audioContext();
    if (!ac) return;
    running = true;
    if (ac.state === "suspended") {
      ac.resume().then(() => {
        if (running) schedulePhrase();
      }).catch(() => {
        running = false;
      });
    } else {
      schedulePhrase();
    }
  }

  function stopAnalysisMorse() {
    running = false;
    if (loopTimer) {
      clearTimeout(loopTimer);
      loopTimer = 0;
    }
    if (phraseGain && ctx) {
      try {
        const now = ctx.currentTime;
        phraseGain.gain.cancelScheduledValues(now);
        phraseGain.gain.setValueAtTime(0, now);
      } catch (_) { }
    }
    if (oscillator) {
      try { oscillator.stop(); } catch (_) { }
      oscillator = null;
    }
    phraseGain = null;
  }

  function watchAnalysisEnd(button) {
    if (stopObserver) stopObserver.disconnect();
    let sawBusy = false;
    const check = () => {
      const text = button.textContent.trim();
      const busy = button.disabled || text === "分析中…" || text === "分析中...";
      if (busy) sawBusy = true;
      if (sawBusy && !button.disabled && text === "APIによるAI分析") {
        stopAnalysisMorse();
        if (stopObserver) {
          stopObserver.disconnect();
          stopObserver = null;
        }
      }
    };
    stopObserver = new MutationObserver(check);
    stopObserver.observe(button, { attributes: true, childList: true, characterData: true, subtree: true });
    queueMicrotask(check);
  }

  function init() {
    const run = document.getElementById("ai-run");
    if (!run) return;

    // capture で先に AudioContext を起こす。iPhone/Safari のユーザー操作制限対策。
    run.addEventListener("click", () => {
      if (run.disabled) return;
      startAnalysisMorse();
      watchAnalysisEnd(run);
    }, true);

    const back = document.getElementById("aiback");
    if (back) back.addEventListener("click", stopAnalysisMorse);
    window.addEventListener("pagehide", stopAnalysisMorse);

    // デバッグ時にコンソールから確認できるよう最小限だけ公開。
    window.AiAnalysisMorse = {
      message: MESSAGE,
      start: startAnalysisMorse,
      stop: stopAnalysisMorse
    };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
