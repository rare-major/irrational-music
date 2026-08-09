#!/usr/bin/env python3
"""
irrational_music.py
--------------------
Turns the never-ending trailing digits of irrational numbers into music.

Nothing here is random. Every pitch, duration, dynamic and chord voicing is a
deterministic function of (which irrational number, which digit offset).
Feed it the same inputs and you get exactly the same piece back -- but slide
the offset forward and you're listening to a different, never-repeating
stretch of that number's decimal expansion.

Only the Python standard library + numpy are used (no internet, no
soundfonts): digits come from `decimal` (a from-scratch Chudnovsky pi, and
Decimal.sqrt()/.exp()/.ln() for the others), the melody/harmony/rhythm are
built with basic music-theory rules to keep the raw digit stream from
sounding like noise, a tiny pure-Python MIDI writer produces a .mid you can
open in any DAW, and a small additive synthesizer (numpy) renders audio you
can just press play on -- either to a .wav file, or straight out of your
speakers in real time (--realtime), generated on the fly forever.

Any irrational number
----------------------
  pi | e | phi                    built-in constants
  sqrt2 | sqrt3 | sqrt5 | ...     shorthand presets
  sqrt:<n>                        sqrt of any positive integer
  root:<k>:<n>                    k-th root of any positive number
  ln:<n>                          natural log of any positive number
  "sqrt(2)+sqrt(3)", "e**pi"...   any expression of + - * / ** with
                                   sqrt/root/exp/ln/log10 and pi/e/phi
  digits:3.14159...               use a literal digit string you already have
  file:/path/to/digits.txt        read the digit string from a text file

Real-time mode
--------------
  python3 irrational_music.py --realtime
  python3 irrational_music.py --realtime --melody-source "sqrt(2)+sqrt(3)" \
      --scale dorian --tempo 90
Requires `pip install sounddevice` (wraps PortAudio; on Linux you may also
need `sudo apt-get install libportaudio2`). Runs until you hit Ctrl+C, or
for --seconds N if you want it to stop on its own. Notes are generated
just-in-time from the digit stream a couple of seconds ahead of playback --
there's no fixed-length piece sitting in memory, it genuinely never has to
end.

Usage examples
--------------
  python3 irrational_music.py
  python3 irrational_music.py --melody-source e --scale minor_pentatonic --tempo 120
  python3 irrational_music.py --melody-source sqrt:7 --offset 5000 --notes 200
  python3 irrational_music.py --key A --scale natural_minor --reverb --out night_sky
  python3 irrational_music.py --realtime --melody-source "root:5:2" --key D --tempo 100
"""

import argparse
import decimal
import math
import wave
import struct
import sys
import threading
import time
import numpy as np


# ======================================================================
# 1. DIGIT SOURCES  (arbitrary precision, stdlib `decimal` only)
# ======================================================================

def _digits_after_point(value: decimal.Decimal, n: int) -> str:
    """Return the first n digits after the decimal point of a Decimal."""
    s = format(value, 'f')
    if '.' not in s:
        return '0' * n
    frac = s.split('.', 1)[1]
    if len(frac) < n:
        frac = frac + '0' * (n - len(frac))
    return frac[:n]


def compute_pi(prec: int) -> decimal.Decimal:
    """Chudnovsky algorithm -- ~14 correct decimal digits per iteration."""
    decimal.getcontext().prec = prec + 15
    C = 426880 * decimal.Decimal(10005).sqrt()
    K = decimal.Decimal(6)
    M = decimal.Decimal(1)
    X = decimal.Decimal(1)
    L = decimal.Decimal(13591409)
    S = L
    n_terms = prec // 14 + 3
    for i in range(1, n_terms + 1):
        M = (K ** 3 - 16 * K) * M / decimal.Decimal(i) ** 3
        L += 545140134
        X *= -262537412640768000
        S += M * L / X
        K += 12
    pi = C / S
    decimal.getcontext().prec = prec + 2
    return +pi


def compute_e(prec: int) -> decimal.Decimal:
    decimal.getcontext().prec = prec + 15
    val = decimal.Decimal(1).exp()
    decimal.getcontext().prec = prec + 2
    return +val


def compute_sqrt(k: int, prec: int) -> decimal.Decimal:
    decimal.getcontext().prec = prec + 15
    val = decimal.Decimal(k).sqrt()
    decimal.getcontext().prec = prec + 2
    return +val


def compute_ln(k: int, prec: int) -> decimal.Decimal:
    decimal.getcontext().prec = prec + 15
    val = decimal.Decimal(k).ln()
    decimal.getcontext().prec = prec + 2
    return +val


def compute_phi(prec: int) -> decimal.Decimal:
    decimal.getcontext().prec = prec + 15
    val = (1 + decimal.Decimal(5).sqrt()) / 2
    decimal.getcontext().prec = prec + 2
    return +val


def newton_root(coeffs, x0, prec: int, iters: int = 300) -> decimal.Decimal:
    """
    Real root of an integer polynomial c_n x^n + ... + c1 x + c0 = 0, found
    by Newton's method in Decimal arithmetic. `coeffs` is [c_n, ..., c0],
    `x0` a float seed near the root you want. Newton's method roughly
    doubles the number of correct digits every iteration, so this reaches
    arbitrary precision quickly as long as the seed is in the right basin.
    Used for algebraic constants (plastic number, supergolden ratio, ...)
    whose defining equation is simpler to state than any radical formula.
    """
    decimal.getcontext().prec = prec + 30
    deg = len(coeffs) - 1
    dcoeffs = [c * (deg - i) for i, c in enumerate(coeffs[:-1])]

    def ev(cs, x):
        r = decimal.Decimal(0)
        for c in cs:
            r = r * x + c
        return r

    x = decimal.Decimal(x0)
    tol = decimal.Decimal(1).scaleb(-(prec + 10))
    for _ in range(iters):
        dfx = ev(dcoeffs, x)
        if dfx == 0:
            break
        step = ev(coeffs, x) / dfx
        x_new = x - step
        if abs(x_new - x) < tol:
            x = x_new
            break
        x = x_new
    decimal.getcontext().prec = prec + 2
    return +x


# ----------------------------------------------------------------------
# A few famous irrationals whose digits are easiest to *construct*
# directly, rather than compute via decimal arithmetic. All three below
# are known to be transcendental, and all three can be extended to any
# number of digits on demand (genuinely never-ending, just like pi/e).
# ----------------------------------------------------------------------

def champernowne_digits(n: int) -> str:
    """0.123456789101112... -- integers concatenated in order. The first
    number ever proved transcendental by construction (Champernowne, 1933)."""
    parts, total, k = [], 0, 1
    while total < n:
        s = str(k)
        parts.append(s)
        total += len(s)
        k += 1
    return ''.join(parts)[:n]


def liouville_digits(n: int) -> str:
    """sum_{k=1}^inf 10^-k! -- a 1 at every factorial position, 0 elsewhere.
    Liouville's constant (1844): the first number ever proved transcendental
    at all."""
    digits = ['0'] * n
    k = 1
    while True:
        f = math.factorial(k)
        if f > n:
            break
        digits[f - 1] = '1'
        k += 1
    return ''.join(digits)


def _is_prime(m: int) -> bool:
    if m < 2:
        return False
    if m % 2 == 0:
        return m == 2
    i = 3
    while i * i <= m:
        if m % i == 0:
            return False
        i += 2
    return True


def copeland_erdos_digits(n: int) -> str:
    """0.235711131719... -- primes concatenated in order (Copeland & Erdős,
    1946, proved normal in base 10)."""
    parts, total, candidate = [], 0, 2
    while total < n:
        if _is_prime(candidate):
            s = str(candidate)
            parts.append(s)
            total += len(s)
        candidate += 1
    return ''.join(parts)[:n]


RAW_DIGIT_SOURCES = {
    'champernowne': champernowne_digits,
    'liouville': liouville_digits,
    'copeland_erdos': copeland_erdos_digits,
}


def compute_root(n, k, prec: int) -> decimal.Decimal:
    """k-th root of n (any real k, any positive n) via Decimal's correctly
    rounded fractional power (internally exp(ln(n)/k)) -- this alone covers
    an enormous family of algebraic irrationals: sqrt/cube-root/5th-root/...
    of anything that isn't a perfect k-th power."""
    decimal.getcontext().prec = prec + 15
    val = decimal.Decimal(n) ** (decimal.Decimal(1) / decimal.Decimal(k))
    decimal.getcontext().prec = prec + 2
    return +val


# ----------------------------------------------------------------------
# General expression evaluator: lets someone type essentially *any*
# irrational number built from {+ - * / **}, sqrt/root/exp/ln/log10, and
# the constants pi/e/phi -- e.g. "sqrt(2)+sqrt(3)", "e**pi", "root(2,5)",
# "ln(2)*sqrt(7)-1/3". Evaluated over `decimal.Decimal` at the working
# precision, so it stays arbitrary-precision all the way down. Only a
# whitelisted AST subset is walked -- no arbitrary code execution.
# ----------------------------------------------------------------------
import ast as _ast  # local import name kept short & obviously scoped

_ALLOWED_FUNCS = {'sqrt', 'exp', 'ln', 'log10', 'root'}


def _eval_expr_decimal(expr: str, prec: int) -> decimal.Decimal:
    decimal.getcontext().prec = prec + 25
    consts = {
        'pi': compute_pi(prec + 25),
        'e': compute_e(prec + 25),
        'phi': compute_phi(prec + 25),
    }

    def ev(node):
        if isinstance(node, _ast.Expression):
            return ev(node.body)
        if isinstance(node, _ast.BinOp):
            l, r = ev(node.left), ev(node.right)
            if isinstance(node.op, _ast.Add):
                return l + r
            if isinstance(node.op, _ast.Sub):
                return l - r
            if isinstance(node.op, _ast.Mult):
                return l * r
            if isinstance(node.op, _ast.Div):
                return l / r
            if isinstance(node.op, _ast.Pow):
                return l ** r
            raise ValueError("operator not allowed in expression")
        if isinstance(node, _ast.UnaryOp):
            v = ev(node.operand)
            if isinstance(node.op, _ast.USub):
                return -v
            if isinstance(node.op, _ast.UAdd):
                return v
            raise ValueError("unary operator not allowed in expression")
        if isinstance(node, _ast.Call):
            if not isinstance(node.func, _ast.Name) or node.func.id not in _ALLOWED_FUNCS:
                raise ValueError("only sqrt/root/exp/ln/log10 are allowed as functions")
            args = [ev(a) for a in node.args]
            fname = node.func.id
            if fname == 'sqrt':
                return args[0].sqrt()
            if fname == 'exp':
                return args[0].exp()
            if fname == 'ln':
                return args[0].ln()
            if fname == 'log10':
                return args[0].log10()
            if fname == 'root':
                return args[0] ** (decimal.Decimal(1) / args[1])
        if isinstance(node, _ast.Name):
            if node.id in consts:
                return consts[node.id]
            raise ValueError(f"unknown name '{node.id}' (allowed: pi, e, phi)")
        if isinstance(node, _ast.Constant):
            if isinstance(node.value, (int, float)):
                return decimal.Decimal(str(node.value))
            raise ValueError("only numeric literals are allowed")
        raise ValueError(f"disallowed expression element: {type(node).__name__}")

    tree = _ast.parse(expr, mode='eval')
    val = ev(tree)
    decimal.getcontext().prec = prec + 2
    return +val


def _load_literal_digits(spec: str) -> str:
    """`digits:<string>` -> use the string itself as the fractional
    expansion. `file:<path>` -> read the digits out of a text file. Either
    way, you can hand this script *any* digit sequence you already have --
    a constant you computed elsewhere, an OEIS dump, anything -- and it will
    be treated as "the number" to sonify. Non-digit characters are stripped;
    if there's a decimal point only what follows it is used."""
    if spec.lower().startswith('digits:'):
        raw = spec.split(':', 1)[1]
    elif spec.lower().startswith('file:'):
        path = spec.split(':', 1)[1]
        with open(path, 'r') as f:
            raw = f.read()
    else:
        raise ValueError(f"not a literal-digits spec: {spec}")
    if '.' in raw:
        raw = raw.split('.', 1)[1]
    digits = ''.join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise ValueError(f"no digits found in source '{spec}'")
    return digits


_SQRT_PRESETS = {
    'sqrt2': 2, 'sqrt3': 3, 'sqrt5': 5, 'sqrt6': 6, 'sqrt7': 7, 'sqrt8': 8,
    'sqrt10': 10, 'sqrt11': 11, 'sqrt12': 12, 'sqrt13': 13, 'sqrt15': 15,
    'pythagoras': 2,   # Pythagoras' constant = sqrt(2)
    'theodorus': 3,    # Theodorus' constant  = sqrt(3)
}

# "Metallic ratios": x = (n + sqrt(n^2+4))/2. golden (n=1) is compute_phi;
# these two are the next-most-famous members of the family.
_EXPR_PRESETS = {
    'silver_ratio': '1+sqrt(2)',        # n=2:  1+sqrt(2)          ~2.41421356
    'bronze_ratio': '(3+sqrt(13))/2',   # n=3:  (3+sqrt(13))/2     ~3.30277564
}

# Algebraic constants defined by a polynomial rather than a radical formula
# -- solved with Newton's method (see newton_root above). (coeffs, seed)
_POLY_PRESETS = {
    'plastic_number':    ([1, 0, -1, -1], 1.3),   # x^3 = x + 1      ~1.32471796
    'supergolden_ratio': ([1, -1, 0, -1], 1.5),   # x^3 = x^2 + 1    ~1.46557123
}


def resolve_irrational(name: str, prec: int) -> decimal.Decimal:
    """
    Accepts, in order of how they're tried:
      pi | e | phi                      built-in constants
      silver_ratio | bronze_ratio       other metallic ratios (golden = phi)
      plastic_number | supergolden_ratio  cubic algebraic irrationals
      sqrt2 | sqrt3 | ... | pythagoras | theodorus   shorthand presets
      sqrt:<n>                          sqrt of any positive integer
      root:<k>:<n>                      k-th root of any positive integer/decimal
      ln:<n>                            natural log of any positive integer
      expr:<expression>                 ANY expression combining + - * / **,
                                         sqrt()/root()/exp()/ln()/log10(), and
                                         pi/e/phi  ->  e.g. "sqrt(2)+sqrt(3)"
      <bare expression>                 same as expr:, tried as a fallback so
                                         you don't have to type the prefix
    `digits:` / `file:` / `champernowne` / `liouville` / `copeland_erdos`
    sources are handled one level up in DigitStream, since they don't need
    `decimal` arithmetic at all. See list_known_sources() for the full menu.
    """
    raw = name.strip()
    lname = raw.lower()
    if lname == 'pi':
        return compute_pi(prec)
    if lname == 'e':
        return compute_e(prec)
    if lname in ('phi', 'goldenratio', 'golden_ratio'):
        return compute_phi(prec)
    if lname in _EXPR_PRESETS:
        return _eval_expr_decimal(_EXPR_PRESETS[lname], prec)
    if lname in _POLY_PRESETS:
        coeffs, seed = _POLY_PRESETS[lname]
        return newton_root(coeffs, seed, prec)
    if lname in _SQRT_PRESETS:
        return compute_sqrt(_SQRT_PRESETS[lname], prec)
    if lname in ('ln2', 'ln3'):
        return compute_ln(int(lname[2:]), prec)
    if lname.startswith('sqrt:'):
        k = int(raw.split(':', 1)[1])
        if int(math.isqrt(k)) ** 2 == k:
            raise ValueError(f"sqrt:{k} is rational (perfect square) -- pick another")
        return compute_sqrt(k, prec)
    if lname.startswith('root:'):
        parts = raw.split(':')
        if len(parts) != 3:
            raise ValueError("root:<k>:<n> expects two numbers, e.g. root:5:2")
        k, n = parts[1], parts[2]
        return compute_root(n, k, prec)
    if lname.startswith('ln:'):
        k = raw.split(':', 1)[1]
        return compute_ln(k, prec)
    if lname.startswith('expr:'):
        return _eval_expr_decimal(raw.split(':', 1)[1], prec)
    # Fallback: try it as a bare expression before giving up, so things like
    # --melody-source "sqrt(2)+sqrt(3)" work without an "expr:" prefix.
    try:
        return _eval_expr_decimal(raw, prec)
    except Exception as exc:
        raise ValueError(
            f"Unknown irrational source '{name}'. Run with --list-sources to "
            f"see every named preset, or use sqrt:<n> / root:<k>:<n> / ln:<n> / "
            f"an expression / digits:<literal> / file:<path>. "
            f"(expression parse error: {exc})"
        ) from exc


def list_known_sources() -> str:
    lines = [
        "Named constants:",
        "  pi, e, phi (golden ratio), silver_ratio, bronze_ratio,",
        "  plastic_number, supergolden_ratio,",
        "  champernowne, liouville, copeland_erdos",
        "",
        "Shorthand roots:",
        "  " + ", ".join(sorted(_SQRT_PRESETS.keys())),
        "  ln2, ln3",
        "",
        "General forms:",
        "  sqrt:<n>            e.g. sqrt:17",
        "  root:<k>:<n>         k-th root of n, e.g. root:5:2",
        "  ln:<n>               e.g. ln:10",
        "  <any expression>     + - * / ** with sqrt()/root()/exp()/ln()/log10()",
        "                       and pi/e/phi, e.g. \"sqrt(2)+sqrt(3)\", \"e**pi\"",
        "  digits:<literal>     use these exact digits as the expansion",
        "  file:<path>          read the digit string from a text file",
    ]
    return "\n".join(lines)


class DigitStream:
    """
    A window onto the never-ending decimal expansion of one irrational
    number (or, for `digits:`/`file:` sources, a fixed digit string that
    loops once exhausted). Digits are computed lazily and re-extended (to
    more precision) automatically if you ask it to walk further than it
    currently holds -- for computed sources there's conceptually no end to
    this stream, we just materialize the part we're about to listen to.
    """

    def __init__(self, source_name: str, offset: int = 0, buffer: int = 4000):
        self.source_name = source_name
        self.offset = offset
        self._buffer_size = buffer
        self._cursor = 0
        self._literal = None
        self._raw_gen = None
        lname = source_name.strip().lower()
        if lname.startswith('digits:') or lname.startswith('file:'):
            self._literal = _load_literal_digits(source_name)
            self._digits = self._literal
        elif lname in RAW_DIGIT_SOURCES:
            self._raw_gen = RAW_DIGIT_SOURCES[lname]
            self._digits = ""
            self._extend(offset + buffer)
        else:
            self._digits = ""
            self._extend(offset + buffer)

    def _extend(self, min_len: int):
        prec = max(min_len + 200, self._buffer_size)
        if self._raw_gen is not None:
            self._digits = self._raw_gen(prec)
        else:
            value = resolve_irrational(self.source_name, prec)
            self._digits = _digits_after_point(value, prec)

    def next_digit(self) -> int:
        idx = self.offset + self._cursor
        if self._literal is not None:
            d = int(self._literal[idx % len(self._literal)])
        else:
            if idx >= len(self._digits) - 1:
                self._extend(idx + self._buffer_size)
            d = int(self._digits[idx])
        self._cursor += 1
        return d

    def next_digits(self, n: int):
        return [self.next_digit() for _ in range(n)]

    def peek_window(self, n: int) -> str:
        if self._literal is not None:
            return ''.join(self._literal[(self.offset + i) % len(self._literal)] for i in range(n))
        idx = self.offset
        if idx + n > len(self._digits):
            self._extend(idx + n + self._buffer_size)
        return self._digits[idx: idx + n]


# ======================================================================
# 2. MUSIC THEORY
# ======================================================================

SCALE_STEPS = {
    'major':            [0, 2, 4, 5, 7, 9, 11],
    'natural_minor':    [0, 2, 3, 5, 7, 8, 10],
    'harmonic_minor':   [0, 2, 3, 5, 7, 8, 11],
    'dorian':           [0, 2, 3, 5, 7, 9, 10],
    'mixolydian':       [0, 2, 4, 5, 7, 9, 10],
    'major_pentatonic': [0, 2, 4, 7, 9],
    'minor_pentatonic': [0, 3, 5, 7, 10],
}

NOTE_NAMES = {
    'C': 0, 'C#': 1, 'DB': 1, 'D': 2, 'D#': 3, 'EB': 3, 'E': 4, 'F': 5,
    'F#': 6, 'GB': 6, 'G': 7, 'G#': 8, 'AB': 8, 'A': 9, 'A#': 10, 'BB': 10,
    'B': 11,
}

# Rhythm palette: 10 slots (one per digit 0-9). Repeating a duration makes
# it statistically more common, which is how a uniformly-distributed digit
# stream still produces a rhythm with "normal" note-length weighting instead
# of chaos: quarters and eighths dominate, half notes and dotted values are
# rarer accents.
DURATION_PALETTE = [0.5, 1.0, 0.5, 1.0, 0.25, 1.0, 0.75, 0.5, 1.5, 2.0]  # in beats

# Diatonic-ish chord progression expressed as *indices into the scale*
# (works for 7-note and pentatonic scales alike, since it's just "stack the
# scale by thirds starting on this degree").
PROGRESSION = [0, 5, 3, 4]  # feels like I - vi - IV - V when scale is 7 notes


def note_name_to_pitch_class(key: str) -> int:
    return NOTE_NAMES[key.strip().upper()]


def scale_degree_to_semitone(scale_steps, degree_index: int):
    """degree_index can be negative or >= len(scale); returns (semitone, octave_shift)."""
    n = len(scale_steps)
    octave_shift, idx = divmod(degree_index, n)
    return scale_steps[idx], octave_shift


def build_chord(scale_steps, root_key_pc: int, degree: int, base_octave_midi: int,
                 extension_digit: int):
    """Stack the scale in thirds (2 scale-steps at a time) starting at `degree`."""
    n = len(scale_steps)
    tones = []
    third_step = 2 if n >= 6 else 1  # pentatonic scales: stack by seconds instead
    stack_positions = [0, third_step, 2 * third_step]
    if extension_digit % 3 == 1:
        stack_positions.append(3 * third_step)  # add a "7th"-like colour tone
    for pos in stack_positions:
        semi, oct_shift = scale_degree_to_semitone(scale_steps, degree + pos)
        pitch = base_octave_midi + root_key_pc + semi + 12 * oct_shift
        tones.append(pitch)
    return tones


def clamp_to_register(pitch: int, low: int, high: int) -> int:
    while pitch < low:
        pitch += 12
    while pitch > high:
        pitch -= 12
    return pitch


def smooth_toward(prev_pitch, raw_pitch, max_jump, low, high):
    """Fold raw_pitch by octaves toward prev_pitch until the melodic leap is
    reasonable, then clamp into the playable register. This is the one bit
    of "taste" imposed on top of the raw digits -- it turns a jagged digit
    sequence into a line a human would actually call a melody."""
    if prev_pitch is None:
        return clamp_to_register(raw_pitch, low, high)
    pitch = raw_pitch
    while abs(pitch - prev_pitch) > max_jump:
        pitch += -12 if pitch > prev_pitch else 12
    return clamp_to_register(pitch, low, high)


# ======================================================================
# 3. COMPOSITION
# ======================================================================

class NoteEvent:
    __slots__ = ("start_beat", "dur_beat", "pitch", "velocity", "channel")

    def __init__(self, start_beat, dur_beat, pitch, velocity, channel):
        self.start_beat = start_beat
        self.dur_beat = dur_beat
        self.pitch = pitch
        self.velocity = velocity
        self.channel = channel


class Composer:
    """
    Weaves four digit streams (which may all point at the same irrational
    number, or four different ones) into melody, rhythm, dynamics and
    harmony, then lays the result out on a beat timeline.
    """

    def __init__(self, melody_src, rhythm_src, dynamics_src, harmony_src,
                 offset, key, scale_name, chord_every=4):
        self.scale_steps = SCALE_STEPS[scale_name]
        self.key_pc = note_name_to_pitch_class(key)
        self.chord_every = chord_every

        self.melody_stream = DigitStream(melody_src, offset=offset)
        self.rhythm_stream = DigitStream(rhythm_src, offset=offset + 17)
        self.dynamics_stream = DigitStream(dynamics_src, offset=offset + 41)
        self.harmony_stream = DigitStream(harmony_src, offset=offset + 71)

        self.melody_low, self.melody_high = 60, 84       # C4..C6
        self.bass_low, self.bass_high = 36, 48            # C2..C3
        self.chord_low, self.chord_high = 48, 67           # C3..G4

    def stream_events(self):
        """
        The core, unbounded generator. Yields (kind, NoteEvent) forever --
        'melody' events one per beat-step, plus 'chord'/'bass' events every
        `chord_every` melody notes -- pulling fresh digits out of the
        (conceptually infinite) DigitStreams as it goes. This is what
        drives both the bounded file-render (compose()) and the unbounded
        real-time player.
        """
        prev_pitch = None
        raw_vel_hist = []
        t = 0.0
        i = 0
        n = len(self.scale_steps)
        while True:
            # --- rhythm ---
            r_digit = self.rhythm_stream.next_digit()
            dur = DURATION_PALETTE[r_digit]

            # --- melody pitch ---
            deg_digit = self.melody_stream.next_digit()
            oct_digit = self.melody_stream.next_digit()
            degree = deg_digit % n
            base_octave = 60 + 12 * (oct_digit % 3 - 1)  # spread across ~3 octaves
            semitone, oct_shift = scale_degree_to_semitone(self.scale_steps, degree)
            raw_pitch = base_octave + self.key_pc + semitone + 12 * oct_shift
            pitch = smooth_toward(prev_pitch, raw_pitch, max_jump=9,
                                   low=self.melody_low, high=self.melody_high)
            prev_pitch = pitch

            # --- dynamics (smoothed so phrasing feels intentional) ---
            v_digit = self.dynamics_stream.next_digit()
            raw_vel = 58 + v_digit * 5  # 58..103
            raw_vel_hist.append(raw_vel)
            if len(raw_vel_hist) > 4:
                raw_vel_hist.pop(0)
            velocity = int(sum(raw_vel_hist) / len(raw_vel_hist))

            yield 'melody', NoteEvent(t, dur * 0.95, pitch, velocity, channel=0)

            # --- harmony, updated every `chord_every` melody notes ---
            if i % self.chord_every == 0:
                chord_idx = (i // self.chord_every) % len(PROGRESSION)
                degree_for_chord = PROGRESSION[chord_idx]
                h_digit = self.harmony_stream.next_digit()
                span = dur * self.chord_every
                tones = build_chord(self.scale_steps, self.key_pc, degree_for_chord,
                                     base_octave_midi=48, extension_digit=h_digit)
                for ct in tones:
                    ct = clamp_to_register(ct, self.chord_low, self.chord_high)
                    yield 'chord', NoteEvent(t, span * 0.9, ct, 46, channel=1)
                root_tone = clamp_to_register(tones[0], self.bass_low, self.bass_high)
                yield 'bass', NoteEvent(t, span * 0.9, root_tone, 64, channel=2)

            t += dur
            i += 1

    def compose(self, num_notes):
        """Bounded convenience wrapper over stream_events(), for file
        rendering: collect exactly num_notes melody notes (plus whatever
        chords/bass fall alongside them), then apply an ending gesture."""
        melody, chords, bass = [], [], []
        melody_count = 0
        for kind, ev in self.stream_events():
            if kind == 'melody':
                melody.append(ev)
                melody_count += 1
                if melody_count >= num_notes:
                    break
            elif kind == 'chord':
                chords.append(ev)
            elif kind == 'bass':
                bass.append(ev)

        all_ends = [e.start_beat + e.dur_beat for e in melody + chords + bass]
        total_beats = max(all_ends) if all_ends else 0.0

        # gentle ritardando on the last few notes: an easy, deterministic
        # "ending" gesture rather than just stopping abruptly.
        self._apply_ritardando(melody, chords, bass, tail_notes=6)
        return melody, chords, bass, total_beats

    @staticmethod
    def _apply_ritardando(*tracks, tail_notes):
        all_events = [e for tr in tracks for e in tr]
        if not all_events:
            return
        total_end = max(e.start_beat + e.dur_beat for e in all_events)
        tail_start = None
        for tr in tracks:
            if tr:
                candidate = tr[0][-tail_notes:] if False else None
        # simpler: stretch anything starting in the final ~10% of the piece
        stretch_from = total_end * 0.85
        for e in all_events:
            if e.start_beat >= stretch_from:
                factor = 1.0 + 0.6 * (e.start_beat - stretch_from) / max(total_end - stretch_from, 1e-6)
                e.dur_beat *= factor


# ======================================================================
# 4. PURE-PYTHON MIDI WRITER  (no external deps)
# ======================================================================

def _vlq(n: int) -> bytes:
    """Variable length quantity encoding used throughout the MIDI format."""
    bytes_ = [n & 0x7F]
    n >>= 7
    while n:
        bytes_.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(bytes_)


def write_midi(path, tracks_events, tempo_bpm, ppq=480):
    """
    tracks_events: list of (channel, program, [NoteEvent, ...])
    Writes a single-track (format 0) MIDI file with all channels merged,
    which every DAW / player handles fine.
    """
    events = []  # (abs_tick, type_rank, bytes)
    usec_per_qn = int(60_000_000 / tempo_bpm)
    events.append((0, 0, b'\xFF\x51\x03' + usec_per_qn.to_bytes(3, 'big')))

    for channel, program, notes in tracks_events:
        events.append((0, 1, bytes([0xC0 | channel, program])))
        for ev in notes:
            start_tick = int(round(ev.start_beat * ppq))
            end_tick = int(round((ev.start_beat + ev.dur_beat) * ppq))
            if end_tick <= start_tick:
                end_tick = start_tick + 1
            vel = max(1, min(127, ev.velocity))
            pitch = max(0, min(127, ev.pitch))
            events.append((start_tick, 2, bytes([0x90 | channel, pitch, vel])))
            events.append((end_tick, 3, bytes([0x80 | channel, pitch, 0])))

    events.sort(key=lambda x: (x[0], x[1]))

    track_bytes = bytearray()
    prev_tick = 0
    for abs_tick, _, data in events:
        delta = abs_tick - prev_tick
        prev_tick = abs_tick
        track_bytes += _vlq(delta) + data
    track_bytes += _vlq(0) + b'\xFF\x2F\x00'  # end of track

    with open(path, 'wb') as f:
        f.write(b'MThd' + struct.pack('>IHHH', 6, 0, 1, ppq))
        f.write(b'MTrk' + struct.pack('>I', len(track_bytes)) + bytes(track_bytes))


# ======================================================================
# 5. AUDIO SYNTHESIS (numpy) -> WAV
# ======================================================================

TIMBRES = {
    # name: (harmonic amplitudes, attack, decay, sustain_level, release)  -- seconds/level
    'piano': ([1.0, 0.55, 0.30, 0.18, 0.10, 0.06], 0.005, 0.25, 0.35, 0.25),
    'pad':   ([1.0, 0.35, 0.15, 0.05], 0.35, 0.4, 0.75, 0.6),
    'pluck': ([1.0, 0.6, 0.35, 0.2, 0.1], 0.002, 0.12, 0.05, 0.10),
    'bass':  ([1.0, 0.4, 0.15], 0.01, 0.15, 0.6, 0.15),
}


def midi_to_freq(pitch: int) -> float:
    return 440.0 * (2.0 ** ((pitch - 69) / 12.0))


def adsr_envelope(n_samples, sr, attack, decay, sustain_level, release):
    env = np.ones(n_samples)
    idx = 0

    a = min(int(attack * sr), n_samples - idx)
    if a > 0:
        env[idx:idx + a] = np.linspace(0, 1, a, endpoint=False)
        idx += a

    d = min(int(decay * sr), n_samples - idx)
    if d > 0:
        env[idx:idx + d] = np.linspace(1, sustain_level, d, endpoint=False)
        idx += d

    r = min(int(release * sr), n_samples - idx)
    s = max(n_samples - idx - r, 0)
    if s > 0:
        env[idx:idx + s] = sustain_level
        idx += s

    r = n_samples - idx  # whatever is left, in case of rounding
    if r > 0:
        env[idx:idx + r] = np.linspace(sustain_level, 0, r)
    return env


def synth_note(freq, duration_sec, velocity, sr, timbre):
    harmonics, attack, decay, sustain, release = TIMBRES[timbre]
    n = max(int(duration_sec * sr), 1)
    t = np.arange(n) / sr
    signal = np.zeros(n)
    for h_idx, amp in enumerate(harmonics, start=1):
        # tiny detune on higher harmonics = a bit of natural "chorus" warmth
        detune = 1.0 + (0.0007 * (h_idx - 1))
        signal += amp * np.sin(2 * np.pi * freq * h_idx * detune * t)
    signal /= sum(harmonics)
    env = adsr_envelope(n, sr, attack, decay, sustain, release)
    signal *= env
    signal *= (velocity / 127.0)
    return signal


def simple_reverb(signal, sr, amount=0.25):
    """Cheap Schroeder-style comb reverb: a handful of feedback delay taps."""
    out = signal.copy()
    for delay_ms, gain in [(29, 0.35), (37, 0.28), (43, 0.22), (53, 0.15)]:
        d = int(sr * delay_ms / 1000)
        if d >= len(signal):
            continue
        tap = np.zeros_like(signal)
        tap[d:] = signal[:-d] * gain
        out += tap * amount
    return out


def render_wav(path, melody, chords, bass, total_beats, tempo_bpm, sr,
                melody_timbre, chord_timbre, bass_timbre, reverb=False):
    beat_sec = 60.0 / tempo_bpm
    total_sec = total_beats * beat_sec + 3.0  # tail for release
    n_total = int(total_sec * sr)
    left = np.zeros(n_total)
    right = np.zeros(n_total)

    def place(events, timbre, pan):
        for ev in events:
            start = int(ev.start_beat * beat_sec * sr)
            dur = ev.dur_beat * beat_sec
            freq = midi_to_freq(ev.pitch)
            snippet = synth_note(freq, dur, ev.velocity, sr, timbre)
            end = start + len(snippet)
            if end > n_total:
                snippet = snippet[: n_total - start]
                end = n_total
            if end <= start:
                continue
            left[start:end] += snippet * (1 - pan)
            right[start:end] += snippet * pan

    place(melody, melody_timbre, pan=0.42)
    place(chords, chord_timbre, pan=0.62)
    place(bass, bass_timbre, pan=0.5)

    if reverb:
        left = simple_reverb(left, sr)
        right = simple_reverb(right, sr)

    peak = max(np.max(np.abs(left)), np.max(np.abs(right)), 1e-9)
    scale = 0.9 / peak
    left *= scale
    right *= scale

    stereo = np.empty((n_total, 2), dtype=np.float32)
    stereo[:, 0] = left
    stereo[:, 1] = right
    pcm = np.clip(stereo * 32767.0, -32768, 32767).astype('<i2')

    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


# ======================================================================
# 6. REAL-TIME STREAMING PLAYER
# ======================================================================

NOTE_LETTER = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def pitch_label(pitch: int) -> str:
    return f"{NOTE_LETTER[pitch % 12]}{pitch // 12 - 1}"


class RealtimePlayer:
    """
    Streams the composition live out of the speakers, generating notes
    just-in-time from the digit stream instead of pre-rendering a
    fixed-length file. Two threads:

      - a scheduler thread that walks Composer.stream_events() forever,
        synthesizes each note's waveform the moment it's needed, and drops
        it into a shared list of "active voices" tagged with the absolute
        sample position it should start at;
      - the audio callback (driven by PortAudio/sounddevice on its own
        thread) that, for every output block, mixes whatever voices
        overlap that block and advances the playback clock.

    The scheduler only ever looks a couple of seconds ahead (LOOKAHEAD_SEC)
    of the playback clock, so it can run indefinitely without unbounded
    memory growth -- there is no end to the piece, only to your patience.
    """

    LOOKAHEAD_SEC = 2.5
    GAIN = {'melody': 0.55, 'chord': 0.16, 'bass': 0.5}
    PAN = {'melody': 0.42, 'chord': 0.62, 'bass': 0.5}

    def __init__(self, composer: Composer, tempo_bpm, sample_rate=44100,
                 blocksize=1024, melody_timbre='piano', chord_timbre='pad',
                 bass_timbre='bass', device=None, verbose=True):
        self.composer = composer
        self.tempo_bpm = tempo_bpm
        self.sr = sample_rate
        self.blocksize = blocksize
        self.timbres = {'melody': melody_timbre, 'chord': chord_timbre, 'bass': bass_timbre}
        self.device = device
        self.verbose = verbose

        self.samples_per_beat = self.sr * 60.0 / tempo_bpm
        self.voices = []
        self.lock = threading.Lock()
        self.play_sample = 0
        self._stop_flag = threading.Event()
        self._scheduler_thread = None
        self.stream = None

    # ---- audio callback: runs on PortAudio's own thread ----
    def _callback(self, outdata, frames, time_info, status):
        start = self.play_sample
        end = start + frames
        left = np.zeros(frames, dtype=np.float32)
        right = np.zeros(frames, dtype=np.float32)
        with self.lock:
            still_active = []
            for v in self.voices:
                v_start, data, pan = v['start'], v['data'], v['pan']
                v_end = v_start + len(data)
                if v_end <= start:
                    continue  # fully played already -> drop
                if v_start >= end:
                    still_active.append(v)  # hasn't started yet -> keep
                    continue
                lo, hi = max(start, v_start), min(end, v_end)
                seg = data[lo - v_start: hi - v_start]
                left[lo - start: hi - start] += seg * (1 - pan)
                right[lo - start: hi - start] += seg * pan
                if v_end > end:
                    still_active.append(v)
            self.voices = still_active
            self.play_sample += frames
        # cheap safety-net limiter so overlapping voices can't hard-clip
        left = np.tanh(left)
        right = np.tanh(right)
        outdata[:, 0] = left
        outdata[:, 1] = right

    # ---- scheduler: runs on a plain Python thread ----
    def _scheduler_loop(self, seconds_limit):
        for kind, ev in self.composer.stream_events():
            if self._stop_flag.is_set():
                return
            start_sample = int(ev.start_beat * self.samples_per_beat)

            if seconds_limit is not None and start_sample / self.sr > seconds_limit:
                return

            # throttle: don't synthesize/schedule further ahead than needed
            while not self._stop_flag.is_set():
                with self.lock:
                    current = self.play_sample
                if start_sample - current <= self.LOOKAHEAD_SEC * self.sr:
                    break
                time.sleep(0.05)
            if self._stop_flag.is_set():
                return

            dur_sec = ev.dur_beat * 60.0 / self.tempo_bpm
            freq = midi_to_freq(ev.pitch)
            data = synth_note(freq, dur_sec, ev.velocity, self.sr, self.timbres[kind])
            data = (data * self.GAIN[kind]).astype(np.float32)

            with self.lock:
                self.voices.append({'start': start_sample, 'data': data, 'pan': self.PAN[kind]})

            if self.verbose and kind == 'melody':
                t_sec = start_sample / self.sr
                print(f"  [{t_sec:6.1f}s] {pitch_label(ev.pitch):<4} vel={ev.velocity:<3}", flush=True)

    def play(self, seconds=None):
        try:
            import sounddevice as sd
        except (ImportError, OSError) as exc:
            print("Real-time playback needs the `sounddevice` package (and PortAudio).")
            print("Install it with:  pip install sounddevice")
            print("On Linux you may also need:  sudo apt-get install libportaudio2")
            print(f"(import error: {exc})")
            return

        self.stream = sd.OutputStream(
            samplerate=self.sr, blocksize=self.blocksize, channels=2,
            dtype='float32', device=self.device, callback=self._callback,
        )
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop, args=(seconds,), daemon=True)

        print("Streaming live -- press Ctrl+C to stop." if seconds is None
              else f"Streaming live for {seconds:.0f}s (Ctrl+C to stop early).")
        with self.stream:
            self._scheduler_thread.start()
            try:
                if seconds is None:
                    while self._scheduler_thread.is_alive():
                        self._scheduler_thread.join(timeout=0.2)
                    # scheduler exhausted (shouldn't normally happen -- it's
                    # an infinite generator) -- let any tail audio drain
                    time.sleep(1.0)
                else:
                    self._scheduler_thread.join(timeout=seconds + 1.0)
                    time.sleep(1.0)
            except KeyboardInterrupt:
                pass
        self._stop_flag.set()
        print("\nStopped.")


# ======================================================================
# 7. CLI
# ======================================================================

IRRATIONAL_CHOICES_HELP = (
    "pi, e, phi, silver_ratio, bronze_ratio, plastic_number, supergolden_ratio, "
    "champernowne, liouville, copeland_erdos, sqrt2..sqrt15, pythagoras, "
    "theodorus, ln2, ln3, sqrt:<n>, root:<k>:<n>, ln:<n>, any expression like "
    "\"sqrt(2)+sqrt(3)\", digits:<literal digits>, or file:<path>. "
    "Run with --list-sources for the full menu."
)


def build_arg_parser():
    p = argparse.ArgumentParser(
        description="Compose music from the trailing digits of an irrational number.")
    p.add_argument('--melody-source', default='pi',
                   help=f"Irrational number driving the melody. Choices: {IRRATIONAL_CHOICES_HELP}")
    p.add_argument('--rhythm-source', default=None,
                   help="Defaults to melody-source with a different digit offset.")
    p.add_argument('--dynamics-source', default='phi',
                   help="Irrational number driving velocity/dynamics.")
    p.add_argument('--harmony-source', default='sqrt2',
                   help="Irrational number driving chord voicing choices.")
    p.add_argument('--offset', type=int, default=0,
                   help="Starting index into the decimal expansion (pick any window of the never-ending tail).")
    p.add_argument('--notes', type=int, default=120, help="Number of melody notes to generate.")
    p.add_argument('--key', default='C', help="Root key, e.g. C, D#, A.")
    p.add_argument('--scale', default='major', choices=list(SCALE_STEPS.keys()))
    p.add_argument('--tempo', type=int, default=100, help="Tempo in BPM.")
    p.add_argument('--chord-every', type=int, default=4,
                   help="Change chord every N melody notes.")
    p.add_argument('--melody-timbre', default='piano', choices=list(TIMBRES.keys()))
    p.add_argument('--chord-timbre', default='pad', choices=list(TIMBRES.keys()))
    p.add_argument('--bass-timbre', default='bass', choices=list(TIMBRES.keys()))
    p.add_argument('--reverb', action='store_true', help="Add a light comb-filter reverb to the WAV render.")
    p.add_argument('--sample-rate', type=int, default=44100)
    p.add_argument('--out', default='irrational_piece', help="Output basename (writes <out>.mid and <out>.wav).")

    p.add_argument('--realtime', action='store_true',
                   help="Stream audio live out of your speakers instead of writing files. Runs "
                        "forever (Ctrl+C to stop) unless --seconds is given.")
    p.add_argument('--seconds', type=float, default=None,
                   help="With --realtime, auto-stop after this many seconds instead of running forever.")
    p.add_argument('--blocksize', type=int, default=1024, help="Realtime audio callback block size.")
    p.add_argument('--device', default=None, help="Realtime output device (index or name substring).")
    p.add_argument('--list-devices', action='store_true',
                   help="List available audio output devices (needs sounddevice) and exit.")
    p.add_argument('--list-sources', action='store_true',
                   help="List every named irrational-number preset and the general input forms, then exit.")
    p.add_argument('--quiet', action='store_true', help="Suppress the live note printout in --realtime mode.")
    return p


def main():
    args = build_arg_parser().parse_args()

    if args.list_sources:
        print(list_known_sources())
        return

    if args.list_devices:
        try:
            import sounddevice as sd
            print(sd.query_devices())
        except (ImportError, OSError) as exc:
            print("Couldn't list devices -- sounddevice/PortAudio not available:", exc)
        return

    rhythm_source = args.rhythm_source or args.melody_source

    composer = Composer(
        melody_src=args.melody_source,
        rhythm_src=rhythm_source,
        dynamics_src=args.dynamics_source,
        harmony_src=args.harmony_source,
        offset=args.offset,
        key=args.key,
        scale_name=args.scale,
        chord_every=args.chord_every,
    )

    print(f"Melody source   : {args.melody_source}  (offset {args.offset})")
    print(f"Rhythm source   : {rhythm_source}")
    print(f"Dynamics source : {args.dynamics_source}")
    print(f"Harmony source  : {args.harmony_source}")
    print(f"Key / scale     : {args.key} {args.scale}")
    print(f"Tempo           : {args.tempo} BPM")

    if args.realtime:
        device = args.device
        if device is not None and device.lstrip('-').isdigit():
            device = int(device)
        player = RealtimePlayer(
            composer, tempo_bpm=args.tempo, sample_rate=args.sample_rate,
            blocksize=args.blocksize, melody_timbre=args.melody_timbre,
            chord_timbre=args.chord_timbre, bass_timbre=args.bass_timbre,
            device=device, verbose=not args.quiet,
        )
        try:
            player.play(seconds=args.seconds)
        except KeyboardInterrupt:
            print("\nStopped.")
        return

    melody, chords, bass, total_beats = composer.compose(args.notes)

    midi_path = f"{args.out}.mid"
    wav_path = f"{args.out}.wav"

    write_midi(
        midi_path, tempo_bpm=args.tempo,
        tracks_events=[
            (0, 0, melody),    # Acoustic Grand Piano
            (1, 88, chords),   # Pad (New Age)
            (2, 32, bass),     # Acoustic Bass
        ],
    )
    render_wav(
        wav_path, melody, chords, bass, total_beats, args.tempo, args.sample_rate,
        melody_timbre=args.melody_timbre, chord_timbre=args.chord_timbre,
        bass_timbre=args.bass_timbre, reverb=args.reverb,
    )

    duration_sec = total_beats * 60.0 / args.tempo
    print(f"Notes generated : {args.notes}  (~{duration_sec:.1f} sec)")
    print(f"Wrote {midi_path}")
    print(f"Wrote {wav_path}")


if __name__ == '__main__':
    main()
