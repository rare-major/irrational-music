# Irrational Music

Turn the never-ending digits of an irrational number into music. Nothing is
random — every pitch, duration, dynamic, and chord voicing is a
deterministic function of *(which number, which digit offset)*. Same inputs,
same piece, every time. Slide the offset and you're listening to a different,
never-repeating stretch of that number's expansion.

**[▶ Live demo](#)** — replace with your GitHub Pages URL once it's live (see below)

Two ways to use it, same underlying idea:

| | Python CLI | Web component |
|---|---|---|
| Where it runs | your terminal | any website |
| Output | `.mid` + `.wav` files, or live speaker playback | live in-browser audio |
| Location | [`cli/irrational_music.py`](cli/irrational_music.py) | [`irrational-music-player.js`](irrational-music-player.js) |

---
p
## Web component

Drop it into any page with one script tag:

```html
<script src="irrational-music-player.js"></script>
<irrational-music-player melody-source="phi" key="D" scale="dorian" tempo="92"></irrational-music-player>
```

No build step, no dependencies, no framework. See [`index.html`](index.html)
for a working example, or open it directly in a browser.

Configure via attributes: `melody-source`, `key`, `scale`, `tempo`, `offset`,
`volume`, `autoplay`. JS API on the element: `el.play()`, `el.stop()`,
`el.setSource(name)`.

## Python CLI

```bash
pip install numpy
python3 cli/irrational_music.py --melody-source phi --scale dorian --key D --out my_piece
```

Writes `my_piece.mid` and `my_piece.wav`. Or skip the files and play live out
of your speakers:

```bash
pip install sounddevice
python3 cli/irrational_music.py --realtime --melody-source pi --tempo 96
```

Full reference — every named constant, every custom-input form
(`sqrt:<n>`, `root:<k>:<n>`, arbitrary expressions, literal digit strings,
files), and every flag — is in [`docs/USAGE.md`](docs/USAGE.md).

## Named number presets

`pi`, `e`, `phi` (golden ratio), `silver_ratio`, `bronze_ratio`,
`plastic_number`, `supergolden_ratio`, `pythagoras` (√2), `theodorus` (√3),
`sqrt2`–`sqrt15`, `champernowne`, `liouville`, `copeland_erdos` — plus any
`sqrt:<n>`, `root:<k>:<n>`, `ln:<n>`, arbitrary expression like
`"sqrt(2)+sqrt(3)"`, or your own literal digit string.

## How it works

1. **Digits** — computed to arbitrary precision (Python: `decimal` +
   Chudnovsky's algorithm for π; JS: a small BigInt fixed-point engine using
   Newton's method). No external math libraries.
2. **Music theory layer** — raw digits map to scale degrees, rhythm values,
   velocity, and chord voicings, with melodic smoothing (no wild leaps) and
   a diatonic chord progression underneath, so it sounds intentional rather
   than random.
3. **Sound** — Python: a small additive synthesizer rendered to WAV, or
   live via `sounddevice`. JS: real-time Web Audio synthesis, no audio files.

## License

MIT — see [LICENSE](LICENSE).
