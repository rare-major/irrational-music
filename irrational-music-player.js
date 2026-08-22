/*!
 * <irrational-music-player>
 * ---------------------------------------------------------------------
 * A drop-in custom element that turns the digits of an irrational number
 * into live, generative music using the Web Audio API. No dependencies,
 * no build step -- one <script> tag and one custom tag.
 *
 *   <script src="irrational-music-player.js"></script>
 *   <irrational-music-player></irrational-music-player>
 *
 * Configure via attributes:
 *   melody-source   "pi" | "e" | "phi" | "silver_ratio" | "bronze_ratio" |
 *                   "plastic_number" | "supergolden_ratio" | "pythagoras" |
 *                   "theodorus" | "sqrt2".."sqrt15" | "champernowne" |
 *                   "liouville" | "copeland_erdos" | "custom:<digits>"
 *   key             C, C#, D, ... B          (default C)
 *   scale           major | natural_minor | harmonic_minor | dorian |
 *                   mixolydian | major_pentatonic | minor_pentatonic
 *   tempo           BPM, e.g. 96             (default 96)
 *   offset          starting digit index     (default 0)
 *   volume          0-100                    (default 70)
 *   autoplay        present = start on user's first interaction with page
 *
 * JS API (on the element instance):
 *   el.play()  el.stop()  el.setSource(name)
 * ---------------------------------------------------------------------
 */
(() => {
  'use strict';

  // =====================================================================
  // 1. ARBITRARY-PRECISION DIGIT ENGINE (BigInt fixed-point, no deps)
  // =====================================================================

  const pow10 = (n) => 10n ** BigInt(n);
  const fpMul = (a, b, scale) => (a * b) / pow10(scale);
  const fpDiv = (a, b, scale) => (a * pow10(scale)) / b;

  function fpSqrt(n, scale) {
    // sqrt(n) as a BigInt scaled by 10^scale, via Newton's method.
    let x = BigInt(Math.round(Math.sqrt(Number(n)) * 10 ** Math.min(scale, 15)));
    x = x * pow10(Math.max(scale - Math.min(scale, 15), 0));
    if (x === 0n) x = 1n;
    const targetScaled = BigInt(n) * pow10(2 * scale);
    const iterCount = Math.ceil(Math.log2(scale + 20)) + 6;
    for (let i = 0; i < iterCount; i++) x = (x + targetScaled / x) / 2n;
    return x;
  }

  function newtonCubicRoot(coeffs, seed, scale, iters = 150) {
    // real root of c3*x^3 + c2*x^2 + c1*x + c0 = 0, Newton's method.
    const [c3, c2, c1, c0] = coeffs.map((c) => BigInt(c) * pow10(scale));
    const dc2 = 3n * BigInt(coeffs[0]) * pow10(scale);
    const dc1 = 2n * BigInt(coeffs[1]) * pow10(scale);
    const dc0 = BigInt(coeffs[2]) * pow10(scale);
    let x = BigInt(Math.round(seed * 10 ** Math.min(scale, 15))) *
      pow10(Math.max(scale - Math.min(scale, 15), 0));
    const evalPoly = (a3, a2, a1, a0, x) => {
      let r = a3;
      r = fpMul(r, x, scale) + a2;
      r = fpMul(r, x, scale) + a1;
      r = fpMul(r, x, scale) + a0;
      return r;
    };
    for (let i = 0; i < iters; i++) {
      const fx = evalPoly(c3, c2, c1, c0, x);
      const dfx = evalPoly(0n, dc2, dc1, dc0, x);
      if (dfx === 0n) break;
      const xNew = x - fpDiv(fx, dfx, scale);
      if (xNew === x) break;
      x = xNew;
    }
    return x;
  }

  function fixedDigitsAfterPoint(fixed, scale, n) {
    const sf = pow10(scale);
    const frac = fixed % sf;
    let s = frac.toString().padStart(scale, '0');
    if (s.length < n) s += '0'.repeat(n - s.length);
    return s.slice(0, n);
  }

  // Verified against a from-scratch Chudnovsky-algorithm computation
  // (same algorithm used in the companion Python CLI script).
  const PI_DIGITS = "141592653589793238462643383279502884197169399375105820974944592307816406286208998628034825342117067982148086513282306647093844609550582231725359408128481117450284102701938521105559644622948954930381964428810975665933446128475648233786783165271201909145648566923460348610454326648213393607260249141273724587006606315588174881520920962829254091715364367892590360011330530548820466521384146951941511609433057270365759591953092186117381932611793105118548074462379962749567351885752724891227938183011949129833673362440656643086021394946395224737190702179860943702770539217176293176752384674818467669405132";
  const E_DIGITS = "718281828459045235360287471352662497757247093699959574966967627724076630353547594571382178525166427427466391932003059921817413596629043572900334295260595630738132328627943490763233829880753195251019011573834187930702154089149934884167509244761460668082264800168477411853742345442437107539077744992069551702761838606261331384583000752044933826560297606737113200709328709127443747047230696977209310141692836819025515108657463772111252389784425056953696770785449969967946864454905987931636889230098793127736178215424999229576351482208269895193668033182528869398496465105820939239829488793320362509443117";

  const SQRT_PRESETS = {
    sqrt2: 2, sqrt3: 3, sqrt5: 5, sqrt6: 6, sqrt7: 7, sqrt8: 8,
    sqrt10: 10, sqrt11: 11, sqrt12: 12, sqrt13: 13, sqrt15: 15,
    pythagoras: 2, theodorus: 3,
  };
  const POLY_PRESETS = {
    plastic_number: { coeffs: [1, 0, -1, -1], seed: 1.3 },
    supergolden_ratio: { coeffs: [1, -1, 0, -1], seed: 1.5 },
  };

  function championowneDigits(n) {
    const parts = [];
    let total = 0, k = 1;
    while (total < n) {
      const s = String(k);
      parts.push(s);
      total += s.length;
      k++;
    }
    return parts.join('').slice(0, n);
  }

  function liouvilleDigits(n) {
    const arr = new Array(n).fill('0');
    let k = 1, fact = 1;
    while (true) {
      fact *= k;
      if (fact > n) break;
      arr[fact - 1] = '1';
      k++;
    }
    return arr.join('');
  }

  function isPrime(m) {
    if (m < 2) return false;
    if (m % 2 === 0) return m === 2;
    for (let i = 3; i * i <= m; i += 2) if (m % i === 0) return false;
    return true;
  }

  function copelandErdosDigits(n) {
    const parts = [];
    let total = 0, candidate = 2;
    while (total < n) {
      if (isPrime(candidate)) {
        const s = String(candidate);
        parts.push(s);
        total += s.length;
      }
      candidate++;
    }
    return parts.join('').slice(0, n);
  }

  const RAW_DIGIT_SOURCES = {
    champernowne: championowneDigits,
    liouville: liouvilleDigits,
    copeland_erdos: copelandErdosDigits,
  };

  /** Returns >= n digits of the fractional expansion for a named source. */
  function computeDigits(source, n) {
    const s = source.trim().toLowerCase();
    if (s === 'pi') return PI_DIGITS.length >= n ? PI_DIGITS : PI_DIGITS.repeat(Math.ceil(n / PI_DIGITS.length));
    if (s === 'e') return E_DIGITS.length >= n ? E_DIGITS : E_DIGITS.repeat(Math.ceil(n / E_DIGITS.length));
    if (s in RAW_DIGIT_SOURCES) return RAW_DIGIT_SOURCES[s](n);
    const scale = n + 25;
    if (s === 'phi' || s === 'golden_ratio') {
      const sq5 = fpSqrt(5, scale);
      const val = (sq5 + pow10(scale)) / 2n; // (1+sqrt5)/2
      return fixedDigitsAfterPoint(val, scale, n);
    }
    if (s === 'silver_ratio') {
      const val = fpSqrt(2, scale) + pow10(scale);
      return fixedDigitsAfterPoint(val, scale, n);
    }
    if (s === 'bronze_ratio') {
      const val = (fpSqrt(13, scale) + 3n * pow10(scale)) / 2n;
      return fixedDigitsAfterPoint(val, scale, n);
    }
    if (s in SQRT_PRESETS) {
      return fixedDigitsAfterPoint(fpSqrt(SQRT_PRESETS[s], scale), scale, n);
    }
    if (s in POLY_PRESETS) {
      const { coeffs, seed } = POLY_PRESETS[s];
      return fixedDigitsAfterPoint(newtonCubicRoot(coeffs, seed, scale), scale, n);
    }
    if (s.startsWith('custom:')) {
      let raw = source.slice(7);
      if (raw.includes('.')) raw = raw.split('.', 2)[1];
      const digits = raw.replace(/\D/g, '');
      if (!digits) return '0'.repeat(n);
      return digits.length >= n ? digits : digits.repeat(Math.ceil(n / digits.length));
    }
    console.warn(`[irrational-music-player] unknown source "${source}", falling back to pi`);
    return computeDigits('pi', n);
  }

  class DigitStream {
    constructor(source, offset = 0, buffer = 500) {
      this.source = source;
      this.offset = offset;
      this.buffer = buffer;
      this.cursor = 0;
      this.digits = computeDigits(source, offset + buffer);
    }
    nextDigit() {
      const idx = this.offset + this.cursor;
      if (idx >= this.digits.length - 1) this.digits = computeDigits(this.source, idx + this.buffer);
      this.cursor++;
      return parseInt(this.digits[idx % this.digits.length], 10);
    }
  }

  // =====================================================================
  // 2. MUSIC THEORY  (melody / rhythm / dynamics / harmony from digits)
  // =====================================================================

  const SCALE_STEPS = {
    major: [0, 2, 4, 5, 7, 9, 11],
    natural_minor: [0, 2, 3, 5, 7, 8, 10],
    harmonic_minor: [0, 2, 3, 5, 7, 8, 11],
    dorian: [0, 2, 3, 5, 7, 9, 10],
    mixolydian: [0, 2, 4, 5, 7, 9, 10],
    major_pentatonic: [0, 2, 4, 7, 9],
    minor_pentatonic: [0, 3, 5, 7, 10],
  };
  const NOTE_NAMES = { C: 0, 'C#': 1, D: 2, 'D#': 3, E: 4, F: 5, 'F#': 6, G: 7, 'G#': 8, A: 9, 'A#': 10, B: 11 };
  const DURATION_PALETTE = [0.5, 1.0, 0.5, 1.0, 0.25, 1.0, 0.75, 0.5, 1.5, 2.0];
  const PROGRESSION = [0, 5, 3, 4];

  function scaleDegreeToSemitone(scaleSteps, degreeIndex) {
    const n = scaleSteps.length;
    const octShift = Math.floor(degreeIndex / n);
    const idx = ((degreeIndex % n) + n) % n;
    return [scaleSteps[idx], octShift];
  }
  function clampToRegister(pitch, low, high) {
    while (pitch < low) pitch += 12;
    while (pitch > high) pitch -= 12;
    return pitch;
  }
  function smoothToward(prevPitch, rawPitch, maxJump, low, high) {
    if (prevPitch === null) return clampToRegister(rawPitch, low, high);
    let pitch = rawPitch;
    while (Math.abs(pitch - prevPitch) > maxJump) pitch += pitch > prevPitch ? -12 : 12;
    return clampToRegister(pitch, low, high);
  }
  function buildChord(scaleSteps, keyPc, degree, baseOctaveMidi, extDigit) {
    const n = scaleSteps.length;
    const thirdStep = n >= 6 ? 2 : 1;
    const positions = [0, thirdStep, 2 * thirdStep];
    if (extDigit % 3 === 1) positions.push(3 * thirdStep);
    return positions.map((pos) => {
      const [semi, octShift] = scaleDegreeToSemitone(scaleSteps, degree + pos);
      return baseOctaveMidi + keyPc + semi + 12 * octShift;
    });
  }

  class Composer {
    constructor({ melodySrc, rhythmSrc, dynamicsSrc, harmonySrc, offset, keyPc, scaleName, chordEvery = 4 }) {
      this.scaleSteps = SCALE_STEPS[scaleName] || SCALE_STEPS.major;
      this.keyPc = keyPc;
      this.chordEvery = chordEvery;
      this.melody = new DigitStream(melodySrc, offset);
      this.rhythm = new DigitStream(rhythmSrc, offset + 17);
      this.dynamics = new DigitStream(dynamicsSrc, offset + 41);
      this.harmony = new DigitStream(harmonySrc, offset + 71);
      this.melodyLow = 60; this.melodyHigh = 84;
      this.bassLow = 36; this.bassHigh = 48;
      this.chordLow = 48; this.chordHigh = 67;
    }
    *streamEvents() {
      let prevPitch = null, velHist = [], t = 0, i = 0;
      const n = this.scaleSteps.length;
      while (true) {
        const rDigit = this.rhythm.nextDigit();
        const dur = DURATION_PALETTE[rDigit];

        const degDigit = this.melody.nextDigit();
        const octDigit = this.melody.nextDigit();
        const degree = degDigit % n;
        const baseOctave = 60 + 12 * ((octDigit % 3) - 1);
        const [semi, octShift] = scaleDegreeToSemitone(this.scaleSteps, degree);
        const rawPitch = baseOctave + this.keyPc + semi + 12 * octShift;
        const pitch = smoothToward(prevPitch, rawPitch, 9, this.melodyLow, this.melodyHigh);
        prevPitch = pitch;

        const vDigit = this.dynamics.nextDigit();
        velHist.push(58 + vDigit * 5);
        if (velHist.length > 4) velHist.shift();
        const velocity = Math.round(velHist.reduce((a, b) => a + b, 0) / velHist.length);

        yield { kind: 'melody', startBeat: t, durBeat: dur * 0.95, pitch, velocity, digits: [degDigit, octDigit] };

        if (i % this.chordEvery === 0) {
          const chordIdx = Math.floor(i / this.chordEvery) % PROGRESSION.length;
          const degreeForChord = PROGRESSION[chordIdx];
          const hDigit = this.harmony.nextDigit();
          const span = dur * this.chordEvery;
          const tones = buildChord(this.scaleSteps, this.keyPc, degreeForChord, 48, hDigit);
          for (const ct of tones) {
            yield { kind: 'chord', startBeat: t, durBeat: span * 0.9, pitch: clampToRegister(ct, this.chordLow, this.chordHigh), velocity: 46 };
          }
          yield { kind: 'bass', startBeat: t, durBeat: span * 0.9, pitch: clampToRegister(tones[0], this.bassLow, this.bassHigh), velocity: 64 };
        }
        t += dur;
        i++;
      }
    }
  }

  // =====================================================================
  // 3. WEB AUDIO SYNTH  (additive synthesis + ADSR, no samples needed)
  // =====================================================================

  const TIMBRES = {
    piano: { harmonics: [1.0, 0.55, 0.30, 0.18, 0.10, 0.06], a: 0.005, d: 0.25, s: 0.35, r: 0.25 },
    pad: { harmonics: [1.0, 0.35, 0.15, 0.05], a: 0.35, d: 0.4, s: 0.75, r: 0.6 },
    pluck: { harmonics: [1.0, 0.6, 0.35, 0.2, 0.1], a: 0.002, d: 0.12, s: 0.05, r: 0.10 },
    bass: { harmonics: [1.0, 0.4, 0.15], a: 0.01, d: 0.15, s: 0.6, r: 0.15 },
  };
  const midiToFreq = (m) => 440 * 2 ** ((m - 69) / 12);

  function scheduleNote(ctx, dest, freq, startTime, durSec, velocity, timbreName, panValue) {
    const timbre = TIMBRES[timbreName] || TIMBRES.piano;
    const panner = ctx.createStereoPanner ? ctx.createStereoPanner() : null;
    const noteGain = ctx.createGain();
    if (panner) { panner.pan.value = panValue; noteGain.connect(panner); panner.connect(dest); }
    else { noteGain.connect(dest); }

    const peak = Math.min(1, velocity / 127) * 0.9;
    const { a, d, s, r } = timbre;
    const sustainLevel = peak * s;
    const t0 = startTime;
    noteGain.gain.setValueAtTime(0.0001, t0);
    noteGain.gain.exponentialRampToValueAtTime(Math.max(peak, 0.0001), t0 + Math.max(a, 0.001));
    noteGain.gain.exponentialRampToValueAtTime(Math.max(sustainLevel, 0.0001), t0 + a + Math.max(d, 0.001));
    noteGain.gain.setValueAtTime(Math.max(sustainLevel, 0.0001), t0 + a + d + Math.max(durSec - a - d, 0));
    noteGain.gain.exponentialRampToValueAtTime(0.0001, t0 + a + d + Math.max(durSec - a - d, 0) + Math.max(r, 0.02));

    const stopTime = t0 + a + d + Math.max(durSec - a - d, 0) + Math.max(r, 0.02) + 0.02;
    const oscs = [];
    timbre.harmonics.forEach((amp, hIdx) => {
      const osc = ctx.createOscillator();
      osc.type = 'sine';
      osc.frequency.value = freq * (hIdx + 1) * (1 + 0.0007 * hIdx);
      const hGain = ctx.createGain();
      hGain.gain.value = amp / timbre.harmonics.reduce((a2, b2) => a2 + b2, 0);
      osc.connect(hGain);
      hGain.connect(noteGain);
      osc.start(t0);
      osc.stop(stopTime);
      oscs.push(osc);
    });
    return oscs;
  }

  // =====================================================================
  // 4. THE CUSTOM ELEMENT
  // =====================================================================

  const SOURCE_OPTIONS = [
    ['pi', 'π  Pi'], ['e', 'e  Euler\u2019s number'], ['phi', 'φ  Golden ratio'],
    ['silver_ratio', 'Silver ratio'], ['bronze_ratio', 'Bronze ratio'],
    ['plastic_number', 'Plastic number'], ['supergolden_ratio', 'Supergolden ratio'],
    ['pythagoras', 'Pythagoras\u2019 constant (√2)'], ['theodorus', 'Theodorus\u2019 constant (√3)'],
    ['sqrt5', '√5'], ['sqrt6', '√6'], ['sqrt7', '√7'], ['sqrt8', '√8'], ['sqrt10', '√10'],
    ['sqrt11', '√11'], ['sqrt12', '√12'], ['sqrt13', '√13'], ['sqrt15', '√15'],
    ['champernowne', 'Champernowne\u2019s constant'], ['liouville', 'Liouville\u2019s constant'],
    ['copeland_erdos', 'Copeland\u2013Erdős constant'],
    ['__custom__', 'Custom digits\u2026'],
  ];
  const KEY_OPTIONS = Object.keys(NOTE_NAMES);
  const SCALE_OPTIONS = Object.keys(SCALE_STEPS);
  const NOTE_LETTER = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  const pitchLabel = (p) => `${NOTE_LETTER[p % 12]}${Math.floor(p / 12) - 1}`;

  const TEMPLATE = `
    <style>
      :host {
        /* === RETRO (default): green phosphor CRT === */
        --im-bg: #000;
        --im-panel: #060606;
        --im-line: #1a3d1a;
        --im-amber: #39ff14;
        --im-amber-dim: #0b330b;
        --im-text: #2ddd2d;
        --im-text-dim: #156615;
        --im-radius: 0px;
        --im-panel-radius: 3px;
        all: initial;
        display: block;
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        color: var(--im-text);
        max-width: 560px;
      }
      :host([data-theme="minimal"]) {
        /* === MINIMAL: light, clean, sans-serif === */
        --im-bg: #f5f4f0;
        --im-panel: #ffffff;
        --im-line: #e0dcd6;
        --im-amber: #1a1a18;
        --im-amber-dim: #c0bdb6;
        --im-text: #1a1a18;
        --im-text-dim: #888480;
        --im-radius: 6px;
        --im-panel-radius: 16px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      }
      .panel {
        background: var(--im-panel);
        border: 1px solid var(--im-line);
        border-radius: var(--im-panel-radius);
        padding: 18px 20px 16px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
      }
      :host(:not([data-theme="minimal"])) .panel {
        box-shadow: 0 0 0 1px #1a3d1a, 0 0 40px rgba(57,255,20,0.05), inset 0 0 80px rgba(0,0,0,0.55);
      }
      /* ── tabs ─────────────────────────────────────────────── */
      .tabs {
        display: flex; gap: 0;
        margin-bottom: 16px;
        border-bottom: 1px solid var(--im-line);
      }
      .tab {
        background: transparent; border: none;
        border-bottom: 2px solid transparent;
        padding: 5px 12px 6px; margin-bottom: -1px;
        font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase;
        color: var(--im-text-dim); cursor: pointer; font-family: inherit;
        transition: color 0.15s, border-color 0.15s;
      }
      .tab.active { color: var(--im-amber); border-bottom-color: var(--im-amber); }
      :host(:not([data-theme="minimal"])) .tab.active {
        text-shadow: 0 0 8px rgba(57,255,20,0.55);
      }
      /* ── eyebrow ──────────────────────────────────────────── */
      .eyebrow {
        display: flex; align-items: baseline; justify-content: space-between;
        margin-bottom: 12px;
      }
      .eyebrow .title {
        font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase;
        color: var(--im-text-dim); font-weight: 600;
      }
      .eyebrow .now {
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        font-size: 12px; color: var(--im-amber);
        min-width: 90px; text-align: right;
      }
      :host(:not([data-theme="minimal"])) .eyebrow .now {
        text-shadow: 0 0 8px rgba(57,255,20,0.5);
      }
      /* ── digit tape ───────────────────────────────────────── */
      .tape {
        background: var(--im-bg);
        border: 1px solid var(--im-line);
        border-radius: var(--im-radius);
        padding: 10px 12px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        font-size: 15px; letter-spacing: 0.12em;
        color: var(--im-amber-dim);
        overflow: hidden; white-space: nowrap;
        margin-bottom: 14px;
        box-shadow: inset 0 2px 6px rgba(0,0,0,0.4);
      }
      .tape .cur { color: var(--im-amber); }
      :host(:not([data-theme="minimal"])) .tape .cur {
        text-shadow: 0 0 10px rgba(57,255,20,0.7);
      }
      /* ── visualiser ───────────────────────────────────────── */
      .viz-wrap { position: relative; margin-bottom: 14px; }
      .viz {
        width: 100%; height: 80px; display: block;
        border-radius: var(--im-radius);
        background: var(--im-bg);
        border: 1px solid var(--im-line);
        box-shadow: inset 0 2px 6px rgba(0,0,0,0.4);
      }
      .viz-scan {
        position: absolute; inset: 0; pointer-events: none;
        border-radius: var(--im-radius);
        background: repeating-linear-gradient(
          to bottom,
          transparent 0px, transparent 2px,
          rgba(0,0,0,0.18) 2px, rgba(0,0,0,0.18) 3px
        );
        display: none;
      }
      :host(:not([data-theme="minimal"])) .viz-scan { display: block; }
      /* ── controls ─────────────────────────────────────────── */
      .row { display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
      .field { display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 90px; }
      .field label {
        font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase;
        color: var(--im-text-dim);
      }
      select, input[type="number"], input[type="text"] {
        background: var(--im-bg); color: var(--im-text);
        border: 1px solid var(--im-line); border-radius: var(--im-radius);
        padding: 7px 8px; font-size: 13px; font-family: inherit;
      }
      select:focus, input:focus, button:focus {
        outline: 2px solid var(--im-amber); outline-offset: 1px;
      }
      input[type="range"] { width: 100%; accent-color: var(--im-amber); }
      .slider-value {
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        font-size: 11px; color: var(--im-text-dim);
      }
      .controls-bottom { display: flex; align-items: center; gap: 14px; margin-top: 4px; }
      button.play {
        background: var(--im-amber); color: #000; border: none;
        font-weight: 700; letter-spacing: 0.06em; font-size: 13px;
        border-radius: var(--im-radius); padding: 10px 20px; cursor: pointer;
        font-family: inherit;
        transition: transform 0.05s ease, filter 0.15s ease;
      }
      button.play:hover { filter: brightness(1.1); }
      button.play:active { transform: scale(0.97); }
      button.play.playing { background: transparent; color: var(--im-amber); border: 1px solid var(--im-amber); }
      :host(:not([data-theme="minimal"])) button.play:not(.playing) {
        box-shadow: 0 0 14px rgba(57,255,20,0.28);
      }
      .vol { flex: 1; display: flex; align-items: center; gap: 8px; }
      .vol label { font-size: 10px; color: var(--im-text-dim); text-transform: uppercase; letter-spacing: 0.08em; white-space: nowrap; }
      .custom-input { display: none; margin-top: 8px; }
      .custom-input.visible { display: block; }
      @media (prefers-reduced-motion: reduce) { .tape .cur { text-shadow: none; } }
    </style>
    <div class="panel">
      <div class="tabs">
        <button class="tab active" data-tab="retro">Retro</button>
        <button class="tab" data-tab="minimal">Minimal</button>
      </div>
      <div class="eyebrow">
        <span class="title">Irrational Music</span>
        <span class="now" data-el="now">&mdash;</span>
      </div>
      <div class="tape" data-el="tape">&nbsp;</div>
      <div class="viz-wrap">
        <canvas class="viz" data-el="viz"></canvas>
        <div class="viz-scan"></div>
      </div>
      <div class="custom-input" data-el="customWrap">
        <input type="text" data-el="customDigits" placeholder="Type any digits, e.g. 31415926535..." />
      </div>
      <div class="row">
        <div class="field">
          <label>Source</label>
          <select data-el="source"></select>
        </div>
        <div class="field">
          <label>Key</label>
          <select data-el="key"></select>
        </div>
        <div class="field">
          <label>Scale</label>
          <select data-el="scale"></select>
        </div>
      </div>
      <div class="row">
        <div class="field">
          <label>Tempo <span class="slider-value" data-el="tempoVal"></span></label>
          <input type="range" min="50" max="160" data-el="tempo" />
        </div>
        <div class="field">
          <label>Offset</label>
          <input type="number" min="0" data-el="offset" />
        </div>
      </div>
      <div class="controls-bottom">
        <button class="play" data-el="playBtn">PLAY</button>
        <div class="vol">
          <label>Vol</label>
          <input type="range" min="0" max="100" data-el="volume" />
        </div>
      </div>
    </div>
  `;

  class IrrationalMusicPlayer extends HTMLElement {
    static get observedAttributes() {
      return ['melody-source', 'key', 'scale', 'tempo', 'offset', 'volume', 'autoplay'];
    }

    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this.shadowRoot.innerHTML = TEMPLATE;
      this._audioCtx = null;
      this._master = null;
      this._analyser = null;
      this._composer = null;
      this._gen = null;
      this._playing = false;
      this._nextEventTime = 0; // seconds, in audioCtx time
      this._pendingEvent = null;
      this._schedulerHandle = null;
      this._animFrame = null;
      this._vizTheme = 'retro';
      this._recentDigits = [];
    }

    connectedCallback() {
      const $ = (name) => this.shadowRoot.querySelector(`[data-el="${name}"]`);
      const sourceSel = $('source'), keySel = $('key'), scaleSel = $('scale');
      const tempoInput = $('tempo'), offsetInput = $('offset'), volumeInput = $('volume');
      const playBtn = $('playBtn'), customWrap = $('customWrap'), customDigits = $('customDigits');

      SOURCE_OPTIONS.forEach(([val, label]) => {
        const opt = document.createElement('option');
        opt.value = val; opt.textContent = label;
        sourceSel.appendChild(opt);
      });
      KEY_OPTIONS.forEach((k) => {
        const opt = document.createElement('option'); opt.value = k; opt.textContent = k;
        keySel.appendChild(opt);
      });
      SCALE_OPTIONS.forEach((s) => {
        const opt = document.createElement('option'); opt.value = s;
        opt.textContent = s.replace(/_/g, ' ');
        scaleSel.appendChild(opt);
      });

      const initialSource = this.getAttribute('melody-source') || 'pi';
      if (initialSource.startsWith('custom:')) {
        sourceSel.value = '__custom__';
        customDigits.value = initialSource.slice(7);
        customWrap.classList.add('visible');
      } else {
        sourceSel.value = SOURCE_OPTIONS.some((o) => o[0] === initialSource) ? initialSource : 'pi';
      }
      keySel.value = KEY_OPTIONS.includes(this.getAttribute('key')) ? this.getAttribute('key') : 'C';
      scaleSel.value = SCALE_OPTIONS.includes(this.getAttribute('scale')) ? this.getAttribute('scale') : 'major';
      tempoInput.value = this.getAttribute('tempo') || '96';
      offsetInput.value = this.getAttribute('offset') || '0';
      volumeInput.value = this.getAttribute('volume') || '70';
      $('tempoVal').textContent = `${tempoInput.value} BPM`;

      sourceSel.addEventListener('change', () => {
        customWrap.classList.toggle('visible', sourceSel.value === '__custom__');
        this._restart();
      });
      customDigits.addEventListener('change', () => this._restart());
      keySel.addEventListener('change', () => this._restart());
      scaleSel.addEventListener('change', () => this._restart());
      offsetInput.addEventListener('change', () => this._restart());
      tempoInput.addEventListener('input', () => {
        $('tempoVal').textContent = `${tempoInput.value} BPM`;
        if (this._composer) this._samplesPerBeatCache = null;
        this._tempo = parseInt(tempoInput.value, 10);
      });
      volumeInput.addEventListener('input', () => {
        if (this._master) this._master.gain.value = (parseInt(volumeInput.value, 10) / 100) * 0.5;
      });
      playBtn.addEventListener('click', () => (this._playing ? this.stop() : this.play()));

      this._els = { sourceSel, keySel, scaleSel, tempoInput, offsetInput, volumeInput, playBtn, customDigits, now: $('now'), tape: $('tape'), viz: $('viz') };

      this.setAttribute('data-theme', 'retro');
      this.shadowRoot.querySelectorAll('.tab').forEach((btn) => {
        btn.addEventListener('click', () => {
          this.shadowRoot.querySelectorAll('.tab').forEach((b) => b.classList.remove('active'));
          btn.classList.add('active');
          const theme = btn.dataset.tab;
          this.setAttribute('data-theme', theme);
          this._vizTheme = theme;
        });
      });

      if (this.hasAttribute('autoplay')) {
        const startOnce = () => { this.play(); document.removeEventListener('click', startOnce); };
        document.addEventListener('click', startOnce, { once: true });
      }
    }

    disconnectedCallback() {
      this.stop();
    }

    _currentSourceSpec() {
      const { sourceSel, customDigits } = this._els;
      if (sourceSel.value === '__custom__') {
        return `custom:${customDigits.value.trim() || '0'}`;
      }
      return sourceSel.value;
    }

    _restart() {
      if (this._playing) { this.stop(); this.play(); }
    }

    /** Build (or rebuild) the Composer from current control values. */
    _buildComposer() {
      const { keySel, scaleSel, offsetInput } = this._els;
      const source = this._currentSourceSpec();
      const offset = parseInt(offsetInput.value, 10) || 0;
      this._composer = new Composer({
        melodySrc: source,
        rhythmSrc: source,
        dynamicsSrc: source === 'phi' ? 'e' : 'phi',
        harmonySrc: 'silver_ratio',
        offset,
        keyPc: NOTE_NAMES[keySel.value] ?? 0,
        scaleName: scaleSel.value,
      });
      this._gen = this._composer.streamEvents();
      this._recentDigits = [];
    }

    play() {
      if (this._playing) return;
      if (!this._audioCtx) {
        this._audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        this._master = this._audioCtx.createGain();
        this._master.gain.value = (parseInt(this._els.volumeInput.value, 10) / 100) * 0.5;
        this._analyser = this._audioCtx.createAnalyser();
        this._analyser.fftSize = 2048;
        this._analyser.smoothingTimeConstant = 0.85;
        this._master.connect(this._analyser);
        this._analyser.connect(this._audioCtx.destination);
      }
      if (this._audioCtx.state === 'suspended') this._audioCtx.resume();
      this._buildComposer();
      this._tempo = parseInt(this._els.tempoInput.value, 10) || 96;
      this._nextEventTime = this._audioCtx.currentTime + 0.15;
      this._pendingEvent = this._gen.next().value;
      this._playing = true;
      this._els.playBtn.textContent = 'STOP';
      this._els.playBtn.classList.add('playing');
      this._startViz();
      this._scheduleLoop();
    }

    stop() {
      this._playing = false;
      if (this._schedulerHandle) { clearInterval(this._schedulerHandle); this._schedulerHandle = null; }
      if (this._animFrame) { cancelAnimationFrame(this._animFrame); this._animFrame = null; }
      if (this._els) {
        this._els.playBtn.textContent = 'PLAY';
        this._els.playBtn.classList.remove('playing');
        const c = this._els.viz;
        if (c) c.getContext('2d').clearRect(0, 0, c.width, c.height);
      }
    }

    setSource(name) {
      this._els.sourceSel.value = SOURCE_OPTIONS.some((o) => o[0] === name) ? name : this._els.sourceSel.value;
      this._restart();
    }

    _startViz() {
      const canvas = this._els.viz;
      const analyser = this._analyser;
      const bufLen = analyser.fftSize;
      const timeData = new Uint8Array(bufLen);

      const THEME_COLORS = {
        retro: {
          fillTop: 'rgba(57, 255, 20, 0.10)',
          fillMid: 'rgba(57, 255, 20, 0.32)',
          fillBot: 'rgba(57, 255, 20, 0.10)',
          stroke:  'rgba(57, 255, 20, 0.88)',
          center:  'rgba(57, 255, 20, 0.16)',
        },
        minimal: {
          fillTop: 'rgba(50, 80, 190, 0.05)',
          fillMid: 'rgba(50, 80, 190, 0.18)',
          fillBot: 'rgba(50, 80, 190, 0.05)',
          stroke:  'rgba(50, 80, 190, 0.55)',
          center:  'rgba(50, 80, 190, 0.12)',
        },
      };

      const draw = () => {
        if (!this._playing) return;
        this._animFrame = requestAnimationFrame(draw);

        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        const cssW = rect.width;
        const cssH = rect.height;
        const pw = Math.round(cssW * dpr);
        const ph = Math.round(cssH * dpr);
        if (canvas.width !== pw || canvas.height !== ph) {
          canvas.width = pw;
          canvas.height = ph;
        }

        analyser.getByteTimeDomainData(timeData);

        const C = THEME_COLORS[this._vizTheme] || THEME_COLORS.retro;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, pw, ph);
        ctx.save();
        ctx.scale(dpr, dpr);

        const w = cssW, h = cssH;
        const midY = h / 2;
        const amp = midY - 3;
        const step = Math.max(1, Math.floor(bufLen / w));

        // ── closed symmetric shape (top waveform + mirrored bottom) ────
        ctx.beginPath();
        ctx.moveTo(0, midY);
        for (let i = 0; i < bufLen; i += step) {
          const v = timeData[i] / 128.0 - 1.0;
          ctx.lineTo((i / bufLen) * w, midY - v * amp);
        }
        ctx.lineTo(w, midY);
        for (let i = bufLen - 1; i >= 0; i -= step) {
          const v = timeData[i] / 128.0 - 1.0;
          ctx.lineTo((i / bufLen) * w, midY + v * amp);
        }
        ctx.closePath();
        const fillGrad = ctx.createLinearGradient(0, 0, 0, h);
        fillGrad.addColorStop(0,   C.fillTop);
        fillGrad.addColorStop(0.5, C.fillMid);
        fillGrad.addColorStop(1,   C.fillBot);
        ctx.fillStyle = fillGrad;
        ctx.fill();

        // ── outlines ────────────────────────────────────────────────────
        ctx.strokeStyle = C.stroke;
        ctx.lineWidth = 1.5;
        const drawHalf = (sign) => {
          ctx.beginPath();
          ctx.moveTo(0, midY);
          for (let i = 0; i < bufLen; i += step) {
            const v = timeData[i] / 128.0 - 1.0;
            ctx.lineTo((i / bufLen) * w, midY - sign * v * amp);
          }
          ctx.lineTo(w, midY);
          ctx.stroke();
        };
        drawHalf(1);
        drawHalf(-1);

        // ── faint center line ───────────────────────────────────────────
        ctx.beginPath();
        ctx.moveTo(0, midY);
        ctx.lineTo(w, midY);
        ctx.strokeStyle = C.center;
        ctx.lineWidth = 0.5;
        ctx.stroke();

        ctx.restore();
      };

      draw();
    }

    _scheduleLoop() {
      const LOOKAHEAD = 2.0; // seconds of audio to keep scheduled ahead
      const INTERVAL_MS = 120;
      this._schedulerHandle = setInterval(() => {
        if (!this._playing) return;
        const secPerBeat = 60 / this._tempo;
        this._pump(secPerBeat, LOOKAHEAD);
      }, INTERVAL_MS);
    }

    _pump(secPerBeat, lookahead) {
      const ctx = this._audioCtx;
      // We track absolute schedule time via this._scheduleClock (seconds, ctx time),
      // advancing by each event's own duration along its own track. Since melody
      // drives the beat clock (chords/bass share the same startBeat), we schedule
      // strictly in generator order and convert startBeat -> absolute time using
      // a fixed anchor set when play() was called.
      if (this._anchorTime === undefined || this._anchorBeatZero === undefined) {
        this._anchorTime = this._nextEventTime;
        this._anchorBeatZero = 0;
      }
      while (true) {
        const ev = this._pendingEvent;
        if (!ev) { this._pendingEvent = this._gen.next().value; continue; }
        const absTime = this._anchorTime + ev.startBeat * secPerBeat;
        if (absTime > ctx.currentTime + lookahead) break;
        const durSec = ev.durBeat * secPerBeat;
        const freq = midiToFreq(ev.pitch);
        const timbre = ev.kind === 'melody' ? 'piano' : ev.kind === 'chord' ? 'pad' : 'bass';
        const pan = ev.kind === 'melody' ? -0.15 : ev.kind === 'chord' ? 0.25 : 0;
        const gainScale = ev.kind === 'melody' ? 1.0 : ev.kind === 'chord' ? 0.55 : 0.85;
        scheduleNote(ctx, this._master, freq, absTime, durSec, ev.velocity * gainScale, timbre, pan);
        if (ev.kind === 'melody') this._pushDigitFeedback(ev);
        this._pendingEvent = this._gen.next().value;
      }
    }

    _pushDigitFeedback(ev) {
      this._els.now.textContent = `${pitchLabel(ev.pitch)} \u00b7 ${ev.velocity}`;
      this._recentDigits.push(...ev.digits);
      while (this._recentDigits.length > 40) this._recentDigits.shift();
      const tapeEl = this._els.tape;
      const shown = this._recentDigits.map((d, idx) =>
        idx === this._recentDigits.length - 1 ? `<span class="cur">${d}</span>` : d
      ).join(' ');
      tapeEl.innerHTML = shown;
    }
  }

  if (!customElements.get('irrational-music-player')) {
    customElements.define('irrational-music-player', IrrationalMusicPlayer);
  }
})();
