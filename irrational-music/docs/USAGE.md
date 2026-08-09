# `irrational_music.py` — Usage Reference

Turns the never-ending digits of an irrational number into music. This doc
covers every input you can hand it: the built-in named presets, and every
other form of "any kind of irrational number" it accepts.

Run `python3 irrational_music.py --list-sources` anytime to see this menu
from the script itself.

---

## 1. Named presets (built-in, ready to use as-is)

| Input | What it is | ≈ Value |
|---|---|---|
| `pi` | π | 3.14159265... |
| `e` | Euler's number | 2.71828183... |
| `phi` | Golden ratio | 1.61803399... |
| `silver_ratio` | 1+√2 | 2.41421356... |
| `bronze_ratio` | (3+√13)/2 | 3.30277564... |
| `plastic_number` | root of x³=x+1 | 1.32471796... |
| `supergolden_ratio` | root of x³=x²+1 | 1.46557123... |
| `pythagoras` | √2 | 1.41421356... |
| `theodorus` | √3 | 1.73205081... |
| `sqrt2` `sqrt3` `sqrt5` `sqrt6` `sqrt7` `sqrt8` `sqrt10` `sqrt11` `sqrt12` `sqrt13` `sqrt15` | square roots | — |
| `ln2` `ln3` | natural logs | 0.69314718 / 1.09861229 |
| `champernowne` | 0.123456789101112... | — |
| `liouville` | 1 at every factorial digit position | — |
| `copeland_erdos` | 0.235711131719... (primes) | — |

### Commands using presets

```bash
# just the melody source — rhythm/dynamics/harmony use their defaults
python3 irrational_music.py --melody-source phi --notes 150 --out phi_piece

# mix and match all four roles
python3 irrational_music.py \
  --melody-source plastic_number \
  --rhythm-source e \
  --dynamics-source silver_ratio \
  --harmony-source bronze_ratio \
  --scale dorian --key D --tempo 90 --out metallic_dorian

# real-time, live out of your speakers
python3 irrational_music.py --realtime --melody-source liouville --tempo 70

# see this whole list from the script itself, anytime
python3 irrational_music.py --list-sources
```

---

## 2. Inputs apart from the presets (anything else you want)

| Form | Meaning | Example |
|---|---|---|
| `sqrt:<n>` | √n, any positive integer | `sqrt:17` |
| `root:<k>:<n>` | k-th root of n | `root:5:2` → fifth root of 2 |
| `ln:<n>` | natural log of n | `ln:10` |
| any expression | `+ - * / **` with `sqrt() root() exp() ln() log10()` and `pi e phi` | `"sqrt(2)+sqrt(3)"`, `"e**pi"` |
| `digits:<string>` | use exactly these digits as the expansion (loops if you outrun them) | `digits:14142135623730951` |
| `file:<path>` | read the digit string out of a text file | `file:/home/me/mydigits.txt` |

### Commands using these

```bash
# sqrt of any integer you want
python3 irrational_music.py --melody-source sqrt:17 --notes 100

# any root of any number
python3 irrational_music.py --melody-source "root:5:2" --scale mixolydian

# ln of anything
python3 irrational_music.py --harmony-source "ln:10" --melody-source pi

# a compound expression — quote it so the shell doesn't eat the parentheses/**
python3 irrational_music.py --melody-source "sqrt(2)+sqrt(3)" --scale major_pentatonic

# your own literal digit sequence, typed straight into the command
python3 irrational_music.py --melody-source "digits:271828182845904523536028747135266249775724709369995" --notes 80

# digits pulled from a file you already have (e.g. a constant computed elsewhere)
echo "1.61803398874989484820458683436563811772030917980576" > phi_extra.txt
python3 irrational_music.py --melody-source "file:phi_extra.txt" --notes 80
```

### Things worth knowing when using the "apart from these" forms

- **Quote anything with parentheses, `*`, or `:`** — your shell will otherwise try to interpret it.
- `--offset N` works with all of these the same way — it's your window into the (conceptually) never-ending tail, whichever kind of source you picked.
- `digits:`/`file:` sources are finite and loop once exhausted; everything else (presets, `sqrt:`, `root:`, `ln:`, expressions) can be extended to arbitrary precision on demand, so `--offset` can go as deep as you like.

---

## 3. Other useful flags (quick reference)

| Flag | Purpose |
|---|---|
| `--offset N` | Starting index into the decimal expansion |
| `--notes N` | Number of melody notes to generate (file-render mode) |
| `--key` / `--scale` | Root key and scale (`major`, `natural_minor`, `harmonic_minor`, `dorian`, `mixolydian`, `major_pentatonic`, `minor_pentatonic`) |
| `--tempo` | BPM |
| `--chord-every N` | Change chord every N melody notes |
| `--melody-timbre` / `--chord-timbre` / `--bass-timbre` | `piano`, `pad`, `pluck`, or `bass` |
| `--reverb` | Light comb-filter reverb on the WAV render |
| `--out NAME` | Output basename → writes `NAME.mid` and `NAME.wav` |
| `--realtime` | Stream live out of your speakers instead of writing files (needs `pip install sounddevice`) |
| `--seconds N` | With `--realtime`, auto-stop after N seconds instead of running forever |
| `--list-devices` | List audio output devices (for `--device`) |
| `--list-sources` | Print this whole source menu from the script |
