(function () {
  "use strict";
  if (typeof document === "undefined") return;
  if (typeof SAVER_CYCLE === "undefined" || typeof buildBugs !== "function" || typeof stepSaver !== "function") return;

  // 既存の順番を崩さず、最後に牡丹雪を1パターン追加する。
  if (!SAVER_CYCLE.some((entry) => entry && entry.kind === "snow")) {
    SAVER_CYCLE.push({ kind: "snow", count: 8 });
  }

  const originalBuildBugs = buildBugs;
  const originalStepSaver = stepSaver;
  const originalStopSaver = stopSaver;

  // 雪の太鼓：4/4、四分音符=80。
  // 8分音符グリッドでは
  //   ボン / 休 / ボ / ボ / ボン / 休 / ボン / 休
  // を繰り返す。ボボも普通の太鼓音で、ボンより少し高く短めにする。
  const DRUM_BPM = 80;
  const DRUM_EIGHTH_MS = (60_000 / DRUM_BPM) / 2; // 375ms
  const DRUM_PATTERN = ["bon", null, "bo", "bo", "bon", null, "bon", null];

  let drumCtx = null;
  let drumTimer = 0;
  let drumMaster = null;
  let drumRunning = false;
  let drumStep = 0;

  function getDrumContext() {
    if (drumCtx) return drumCtx;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return null;
    drumCtx = new AudioContextClass();
    return drumCtx;
  }

  // iPhone / Safari の自動再生制限対策。最初の操作時に音声コンテキストだけ起こしておく。
  function primeDrumAudio() {
    const ac = getDrumContext();
    if (!ac) return;
    const unlock = () => {
      try {
        const osc = ac.createOscillator();
        const gain = ac.createGain();
        gain.gain.value = 0.000001;
        osc.connect(gain);
        gain.connect(ac.destination);
        osc.start();
        osc.stop(ac.currentTime + 0.01);
      } catch (_) { }
    };
    if (ac.state === "suspended") ac.resume().then(unlock).catch(() => {});
    else unlock();
  }

  ["pointerdown", "touchstart", "keydown", "mousedown"].forEach((name) => {
    window.addEventListener(name, primeDrumAudio, { capture: true, once: true });
  });

  // 歌舞伎の大太鼓を意識した低い「ボン」。低い胴鳴り＋短い打撃ノイズを合成する。
  function playDrumBon() {
    if (!drumRunning || !drumMaster) return;
    const ac = getDrumContext();
    if (!ac || ac.state !== "running") return;

    const t = ac.currentTime + 0.01;

    const body = ac.createOscillator();
    const bodyGain = ac.createGain();
    body.type = "sine";
    body.frequency.setValueAtTime(92, t);
    body.frequency.exponentialRampToValueAtTime(47, t + 0.42);
    bodyGain.gain.setValueAtTime(0.0001, t);
    bodyGain.gain.exponentialRampToValueAtTime(0.30, t + 0.012);
    bodyGain.gain.exponentialRampToValueAtTime(0.0001, t + 0.82);
    body.connect(bodyGain);
    bodyGain.connect(drumMaster);
    body.start(t);
    body.stop(t + 0.86);

    const low = ac.createOscillator();
    const lowGain = ac.createGain();
    low.type = "sine";
    low.frequency.setValueAtTime(55, t);
    low.frequency.exponentialRampToValueAtTime(39, t + 0.55);
    lowGain.gain.setValueAtTime(0.0001, t);
    lowGain.gain.exponentialRampToValueAtTime(0.16, t + 0.018);
    lowGain.gain.exponentialRampToValueAtTime(0.0001, t + 0.95);
    low.connect(lowGain);
    lowGain.connect(drumMaster);
    low.start(t);
    low.stop(t + 0.98);

    // 革を叩いた瞬間の「ボッ」を短い低域ノイズで足す。
    const length = Math.max(1, Math.floor(ac.sampleRate * 0.09));
    const noiseBuffer = ac.createBuffer(1, length, ac.sampleRate);
    const data = noiseBuffer.getChannelData(0);
    for (let i = 0; i < length; i++) {
      const env = 1 - i / length;
      data[i] = (Math.random() * 2 - 1) * env;
    }
    const noise = ac.createBufferSource();
    const filter = ac.createBiquadFilter();
    const noiseGain = ac.createGain();
    noise.buffer = noiseBuffer;
    filter.type = "lowpass";
    filter.frequency.value = 230;
    filter.Q.value = 0.7;
    noiseGain.gain.setValueAtTime(0.11, t);
    noiseGain.gain.exponentialRampToValueAtTime(0.0001, t + 0.12);
    noise.connect(filter);
    filter.connect(noiseGain);
    noiseGain.connect(drumMaster);
    noise.start(t);
    noise.stop(t + 0.13);
  }

  // 「ボボ」用。普通の太鼓のまま、ボンより少し高く短くする。
  function playDrumBo() {
    if (!drumRunning || !drumMaster) return;
    const ac = getDrumContext();
    if (!ac || ac.state !== "running") return;

    const t = ac.currentTime + 0.008;

    const body = ac.createOscillator();
    const bodyGain = ac.createGain();
    body.type = "sine";
    body.frequency.setValueAtTime(125, t);
    body.frequency.exponentialRampToValueAtTime(66, t + 0.22);
    bodyGain.gain.setValueAtTime(0.0001, t);
    bodyGain.gain.exponentialRampToValueAtTime(0.24, t + 0.008);
    bodyGain.gain.exponentialRampToValueAtTime(0.0001, t + 0.34);
    body.connect(bodyGain);
    bodyGain.connect(drumMaster);
    body.start(t);
    body.stop(t + 0.37);

    const low = ac.createOscillator();
    const lowGain = ac.createGain();
    low.type = "sine";
    low.frequency.setValueAtTime(72, t);
    low.frequency.exponentialRampToValueAtTime(49, t + 0.26);
    lowGain.gain.setValueAtTime(0.0001, t);
    lowGain.gain.exponentialRampToValueAtTime(0.10, t + 0.012);
    lowGain.gain.exponentialRampToValueAtTime(0.0001, t + 0.38);
    low.connect(lowGain);
    lowGain.connect(drumMaster);
    low.start(t);
    low.stop(t + 0.40);

    // 打面のアタックだけ低域ノイズで軽く足す。拍子木の高域成分は入れない。
    const length = Math.max(1, Math.floor(ac.sampleRate * 0.055));
    const noiseBuffer = ac.createBuffer(1, length, ac.sampleRate);
    const data = noiseBuffer.getChannelData(0);
    for (let i = 0; i < length; i++) {
      const env = 1 - i / length;
      data[i] = (Math.random() * 2 - 1) * env;
    }
    const noise = ac.createBufferSource();
    const filter = ac.createBiquadFilter();
    const noiseGain = ac.createGain();
    noise.buffer = noiseBuffer;
    filter.type = "lowpass";
    filter.frequency.value = 300;
    filter.Q.value = 0.7;
    noiseGain.gain.setValueAtTime(0.07, t);
    noiseGain.gain.exponentialRampToValueAtTime(0.0001, t + 0.075);
    noise.connect(filter);
    filter.connect(noiseGain);
    noiseGain.connect(drumMaster);
    noise.start(t);
    noise.stop(t + 0.08);
  }

  function playDrumPatternStep() {
    if (!drumRunning) return;
    const hit = DRUM_PATTERN[drumStep];
    if (hit === "bon") playDrumBon();
    else if (hit === "bo") playDrumBo();
    drumStep = (drumStep + 1) % DRUM_PATTERN.length;
  }

  function startSnowDrum() {
    stopSnowDrum();
    const ac = getDrumContext();
    if (!ac) return;
    drumRunning = true;
    drumStep = 0;
    drumMaster = ac.createGain();
    drumMaster.gain.value = 0.55;
    drumMaster.connect(ac.destination);

    const begin = () => {
      if (!drumRunning) return;
      playDrumPatternStep();
      drumTimer = window.setInterval(playDrumPatternStep, DRUM_EIGHTH_MS);
    };
    if (ac.state === "suspended") ac.resume().then(begin).catch(() => {});
    else begin();
  }

  function stopSnowDrum() {
    drumRunning = false;
    drumStep = 0;
    if (drumTimer) {
      clearInterval(drumTimer);
      drumTimer = 0;
    }
    if (drumMaster && drumCtx) {
      try {
        const now = drumCtx.currentTime;
        drumMaster.gain.cancelScheduledValues(now);
        drumMaster.gain.setValueAtTime(0, now);
        drumMaster.disconnect();
      } catch (_) { }
    }
    drumMaster = null;
  }

  function buildSnow(entry) {
    const svg = svgEl("svg", {});
    const w = window.innerWidth;
    const h = window.innerHeight;
    const count = Math.max(1, Number(entry.count) || 8);
    saverBugs = [];

    for (let i = 0; i < count; i++) {
      const g = svg.appendChild(svgEl("g", {}));
      const r = rnd(18, 31);
      g.appendChild(svgEl("circle", {
        class: "bug body snowflake",
        cx: 0,
        cy: 0,
        r: r.toFixed(1)
      }));

      const b = {
        kind: "snow",
        g,
        r,
        baseX: rnd(r, Math.max(r + 1, w - r)),
        x: 0,
        y: h * ((i + 0.5) / count) + rnd(-h / (count * 3), h / (count * 3)),
        speed: rnd(42, 74),
        sway: rnd(10, 34),
        swaySpeed: rnd(0.45, 0.90),
        seed: rnd(0, Math.PI * 2)
      };
      b.x = b.baseX + Math.sin(b.seed) * b.sway;
      saverBugs.push(b);
    }

    saverEl.innerHTML = "";
    saverEl.appendChild(svg);
    startSnowDrum();
  }

  function moveSnow(b, dt, w, h) {
    b.y += b.speed * dt;
    b.x = b.baseX + Math.sin(saverT * b.swaySpeed + b.seed) * b.sway;

    if (b.y - b.r > h) {
      b.r = rnd(18, 31);
      const circle = b.g.querySelector("circle");
      if (circle) circle.setAttribute("r", b.r.toFixed(1));
      b.baseX = rnd(b.r, Math.max(b.r + 1, w - b.r));
      b.y = -b.r * 0.35;
      b.speed = rnd(42, 74);
      b.sway = rnd(10, 34);
      b.swaySpeed = rnd(0.45, 0.90);
      b.seed = rnd(0, Math.PI * 2);
    }
  }

  buildBugs = function (entry) {
    if (entry && entry.kind === "snow") {
      buildSnow(entry);
      return;
    }
    stopSnowDrum();
    originalBuildBugs(entry);
  };

  stepSaver = function (now) {
    const dt = Math.min((now - saverLast) / 1000, 0.05);
    saverLast = now;
    saverT += dt;
    const w = window.innerWidth;
    const h = window.innerHeight;

    saverBugs.forEach((b) => {
      if (b.kind === "snow") {
        moveSnow(b, dt, w, h);
        b.g.setAttribute("transform", `translate(${b.x.toFixed(1)},${b.y.toFixed(1)})`);
        return;
      }

      moveBug(b, dt, w, h);
      if (b.kind === "ball") {
        b.g.setAttribute("transform", `translate(${b.x.toFixed(1)},${b.y.toFixed(1)})`);
      } else if (b.kind === "butterfly") {
        drawButterfly(b);
      } else {
        drawCentipede(b);
      }
    });

    saverRAF = requestAnimationFrame(stepSaver);
  };

  stopSaver = function () {
    stopSnowDrum();
    originalStopSaver();
  };

  window.SnowSaver = {
    playDrum: playDrumBon,
    playDoubleDrum: playDrumBo,
    stopDrum: stopSnowDrum
  };
})();
