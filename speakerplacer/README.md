# Wall-Mounted Speaker Placement Optimizer

A Python CLI and importable 2D room-acoustics model. The room is a counterclockwise polygon in metres internally; the CLI accepts rectangular rooms in feet. Speakers are wall-mounted. Model registry values are generic placeholders and must be replaced with measured or manufacturer datasheet specifications before using results for installation.

## Environment and quick start

```sh
conda env create --prefix ./.conda-env --file environment.yml
conda activate "$PWD/.conda-env"
python -m speakerplacer --length 15 --width 12 --listener 7.5 4 --facing north \
  --speakers front:2:generic_inwall_lcr surround:2:generic_surround_wide bass:2:generic_inwall_sub \
  --no-show --validate
```

Counts are customizable. Each argument is `ROLE:COUNT[:MODEL_ID]`; omitting the model selects the role default. Paired roles require an even count. For example, `--speakers bass:2 surround:4` asks for two default subwoofers and four default surrounds. List available placeholder models with:

```sh
python -m speakerplacer --list-models
```

The default layout is `front:2 surround:2 bass:2`. `--priority` changes the initial order; an optional coordinate-descent pass then re-optimizes each role with other roles held fixed, using per-role normalized scores. `--modal-q-scale` configures bass damping; `--target-spl` and `--peak-headroom-db` set listener-level SPL targets (`--reference-spl` and `--peak-headroom` remain aliases); `--coherence` selects coherent or incoherent speaker summation; `--toe-in-range MIN MAX` sets signed swivel bounds; `--disable-reflection-directivity` turns off the first-order reflection directivity estimate. The CLI writes candidate scores, recommended placements, best response, and a role-specific model comparison to the selected directory.

Use `--bass-count 1`, `--bass-count 2`, or `--bass-count 4` to run the optional one/two/four-subwoofer response experiment. The command compares all three counts and saves `bass_count_experiment.png`; additional speakers do not guarantee monotonic improvement in a coherent small-room response.

Run the physics and sensitivity checks with `--validate`. A human-readable report and plots are written to `OUTPUT/validation/`, including score spread, hard/wide/soft/acoustics-only angle-filter comparison, widened term ablations, 200 randomized legal candidate layouts, a rule-of-thumb baseline rescored with the same group metric, a 5×5 listener grid, room/absorption sweeps, numerical convergence, analytic RIR/modal checks, and a bass perimeter heatmap. Candidate percentiles and random/rule improvements are reported separately for each role. Cross-room combined scores use per-role z-scores. The report ends with a per-role SUMMARY. The first-order reflection directivity calculation uses image geometry; timing overhead is measured in each report and higher-order RIR taps are not individually decomposed. Validation may take several minutes because it runs repeated image-source simulations.

## Speaker models

`SpeakerModel` is defined in `speakerplacer/speaker_models.py`; the default registry is in `speakerplacer/speaker_models.yaml`. All entries are illustrative placeholders, not real manufacturer data. The nine generic archetypes include:

| Model ID | Intended roles | Placeholder range | Coverage | Mount |
|---|---|---:|---:|---|
| `generic_compact_wall` | front, surround | 100–20,000 Hz | 110° | on wall |
| `generic_bookshelf_onwall` | front, surround | 80–20,000 Hz | 90° | on wall |
| `generic_inwall_lcr` | front | 70–20,000 Hz | 80° | in wall |
| `generic_narrow_onwall` | front, surround | 90–20,000 Hz | 60° | on wall |
| `generic_surround_wide` | surround | 120–20,000 Hz | 120° | on wall |
| `generic_inwall_sub` | bass | 25–200 Hz | 360° | in wall |
| `generic_onwall_sub` | bass | 30–200 Hz | 360° | on wall |
| `generic_dipole_surround` | surround | 100–20,000 Hz | 360° | on wall |
| `generic_onwall_sub_ported` | bass | 25–200 Hz | 360° | on wall |

The YAML model file supports response curves, polar CSV data, frequency-dependent coverage, sensitivity basis, amplifier power, LF maximum SPL, listening distance/spacing recommendations, enclosure alignment, and mounting bounds. Use `--models-file PATH`, `--validate-models`, `--describe-model ID`, and `--role ROLE --list-models` to inspect and load models. Inline overrides use `front:2:generic_inwall_lcr@sensitivity_db=89,coverage_h_deg=75`; quote the whole speaker token in shells. Replace placeholder data with verified values from the exact speaker's datasheet or measurements. Polar CSVs use `angle_deg` plus frequency columns in Hz; response CSVs use `hz,db`. Vertical coverage and mounting height are recorded and validated, but are informational in this 2D model.

The optimizer searches position and toe-in jointly, with mirrored toe angles for symmetric pairs. Modal response is multiplied by the model's on-axis response. Modal scoring interpolates onto a fixed 0.25 Hz grid and caps the computed sweep step at one quarter of the lowest modal frequency divided by Q (half the approximate modal half-width), with a 0.25 Hz floor. SPL uses sensitivity normalized to 1 W at 1 m, effective power `min(rated_power_w, amp_power_w)` when an amp cap is supplied, inverse-square distance, and wall gain. It is a rough free-field estimate; negative headroom values in the report are actual shortfalls under these placeholder max-SPL and 20 dB peak assumptions, not a voltage/watt conversion error. Dipole/bipole patterns are represented in the directivity model. Spacing and enclosure footprint constrain placement; distance recommendations are advisories.

The `--toe-in-range MIN MAX` option applies signed limits to the toe-in search, overriding the model swivel limit when explicitly supplied. Constrained roles also receive exact-target and 0.5° fan candidates from analytic wall-ray intersections; warnings mark toe-in limits, angle-window edges, and recommended listener-distance violations.

## Physics and scoring

Imaging roles use pyroomacoustics image-source RIRs, C50 clarity, model directivity, early-reflection energy, and geometry. The modal bass model calculates rectangular-room modes using `f_nm = (c / 2) * sqrt((n / Lx)^2 + (m / Ly)^2)`, omitting `(0, 0)`, and mode shapes `cos(n*pi*x/Lx) * cos(m*pi*y/Ly)`. Complex source pressures can be summed coherently or incoherently before scoring modal response flatness and null depth. Absorption maps to modal Q as `Q = modal_q_scale / sqrt(max(absorption, 0.01))`.

Modal scoring requires a rectangular four-corner room and omits floor-to-ceiling modes. Imaging off-axis scores average the model's horizontal gain at 500, 1000, 2000, and 4000 Hz using configurable per-band weights; polar tables and coverage-vs-frequency curves are interpolated at those bands. These gains affect the direct-arrival term, while individual RIR taps are not filtered into separate octave bands. Crossover filters and speaker high-pass response are applied to the synthesized on-axis response used for bass scoring. The 2D coverage plot represents horizontal directivity only. Directivity reflection handling is a first-order approximation because pyroomacoustics returns a combined RIR rather than separately tagged image-source taps.

## Python API

```python
from speakerplacer import make_room, optimize_layout
from speakerplacer.speaker_types import parse_speaker_layout

room_m = make_room(15, 12)
listener_m = (7.5 * 0.3048, 4 * 0.3048)
layout = parse_speaker_layout([
    "front:2:generic_inwall_lcr",
    "surround:2:generic_surround_wide",
    "bass:2:generic_inwall_sub",
])
result = optimize_layout(room_m, listener_m, layout, facing="north")
```

`OptimizationResult` contains combined speakers, ranked placements and score breakdowns per role, candidate scores for plotting/debugging, selected RIR (for imaging roles), bass frequency response, and warnings. Position arrays use metres.

## Search and tests

Candidate positions follow polygon edges at 0.25 m spacing, 0.3 m from corners (increased for model footprint), and 5 cm inside the room. Angles are measured at the listener. Paired types are reflected across the facing axis; previously placed speakers reserve space for later types. The modal method currently applies to axis-aligned rectangular rooms.

```sh
python -m pytest
```

The 32 tests cover geometry, analytic candidates, RIR travel time/decay, symmetry and angle constraints, modal sampling/scoring, dipole null aiming, model validation and YAML loading, inline overrides, sensitivity/SPL math, F3/crossover response, polar interpolation, the model wizard, and plotted speaker labels.

## Latest validation run (2026-10-24)

Command:

```sh
python -m speakerplacer --length 15 --width 12 \
  --speakers 'front:2:generic_bookshelf_onwall' 'bass:2:generic_inwall_sub' \
  --validate --no-show --output output/final-deliverable
```

The full generated report is in [`output/final-deliverable/validation/report.txt`](output/final-deliverable/validation/report.txt). Damping-aware modal sampling now makes the convergence checks pass: requested 0.5, 1.0, and 2.0 Hz steps each shift the bass score by +0.000 dB-like. Analytic checks passed for direct arrival, image-source echo timing, the first axial mode, and symmetric coherent bass response.

Example CLI output:

```text
front / generic_bookshelf_onwall (score 9.14):
  generic_bookshelf_onwall (3.35, 11.84) ft; SPL 100.4 dB; headroom -12.4 dB; angle -27.9 deg; toe-in +25 deg
bass / generic_inwall_sub (score -14.89):
  generic_inwall_sub (4.27, 0.16) ft; SPL 110.3 dB; headroom -22.3 dB; angle -139.9 deg; toe-in +0 deg
PASS bass frequency step 0.50 Hz score shift +0.000 dB-like; equivalent optimum=True
PASS bass frequency step 1.00 Hz score shift +0.000 dB-like; equivalent optimum=True
PASS bass frequency step 2.00 Hz score shift +0.000 dB-like; equivalent optimum=True
SUMMARY
front: percentile 95.7; Δrandom +1.12; Δrule +0.00 dB-like; answer-changing terms geometry
bass: percentile 97.9; Δrandom +2.54; Δrule +4.88 dB-like; answer-changing terms flatness
```

The front “matched candidate mean” averages each front speaker's single-candidate score. The selected pair is scored jointly and includes group geometry (−5.12 here), so its 9.14 group score is not directly comparable with the 14.17 individual-candidate mean. The roughly −12 dB front and −22 dB LF headroom are real deficits under the placeholder max-SPL estimates and configured 85 dB average plus 20 dB peak allowance, not a sensitivity conversion error. Bass headroom uses `max_spl_lf_db`. SPL uses 1 W at 1 m sensitivity, effective rated/amplifier power, distance loss, and wall gain.

Model CLI examples:

```sh
python -m speakerplacer --list-models --role surround
python -m speakerplacer --describe-model generic_dipole_surround
python -m speakerplacer --validate-models
python -m speakerplacer --describe-model generic_dipole_surround --plot
python -m speakerplacer --describe-model generic_inwall_sub --plot --length 15 --width 12
python -m speakerplacer --new-model --models-file ./my-speakers.yaml
python -m speakerplacer --compare-models surround=generic_surround_wide,generic_dipole_surround --length 15 --width 12
python -m speakerplacer --length 15 --width 12 \
  --speakers 'front:2:generic_inwall_lcr@sensitivity_db=89,coverage_h_deg=75' \
  --no-show
```

The generated report and plots are under `output/final-deliverable/validation/`. The model specifies 108 dB LF maximum SPL, which is why the bass headroom estimate is lower than the broadband SPL limit. Validation includes a per-field ±20% influence experiment, narrow/wide/dipole surround comparisons, 25/45 Hz F3 comparison, and sensitivity-basis check. Dipole surround search aims its null toward the listener within the model's toe range; the placeholder allows up to 90°. Measured polar curves affect the frequency-banded direct-arrival term. The 2D model omits floor-to-ceiling modes, and per-band filtering of individual RIR taps remains an approximation outside this model.

### Full generated validation report

```text
Physics validation report
Room: 4.572 x 3.6576000000000004 m; facing north; absorption 0.20
INFO first-order reflection-directivity estimate enabled; runtime 0.101s vs 0.060s disabled (+67.4%)
Reflection directivity estimates first-order specular wall hits from image geometry; higher-order RIR taps are not individually decomposed.
PASS front score spread min/max/std 6.00/14.25/2.42 dB; best-median 1.47 dB (23 candidates)
PASS bass score spread min/max/std -20.83/-14.78/1.24 dB; best-median 2.63 dB (47 candidates)
PASS front hard/wide/soft/acoustics-only evaluated; hard vs soft shift 0.29 ft; acoustics-only angle 6.1 deg (textbook 30.0), score 17.03 vs textbook candidate 7.06 dB
WARN front ablate clarity at ±5° (23 candidates): movement 0.00 ft (dead weight at adequate candidate count)
WARN front ablate off_axis at ±5° (23 candidates): movement 0.00 ft (dead weight at adequate candidate count)
WARN front ablate early_reflection at ±5° (23 candidates): movement 0.00 ft (dead weight at adequate candidate count)
WARN front ablate geometry at ±5° (23 candidates): movement 0.00 ft (dead weight at adequate candidate count)
WARN front ablate headroom at ±5° (23 candidates): movement 0.00 ft (dead weight at adequate candidate count)
WARN front ablate clarity at ±15° (60 candidates): movement 0.00 ft (dead weight at adequate candidate count)
WARN front ablate off_axis at ±15° (60 candidates): movement 0.00 ft (dead weight at adequate candidate count)
WARN front ablate early_reflection at ±15° (60 candidates): movement 0.00 ft (dead weight at adequate candidate count)
PASS front ablate geometry at ±15° (60 candidates): movement 1.64 ft
WARN front ablate headroom at ±15° (60 candidates): movement 0.00 ft (dead weight at adequate candidate count)
WARN front ablate clarity at ±20° (72 candidates): movement 0.00 ft (dead weight at adequate candidate count)
WARN front ablate off_axis at ±20° (72 candidates): movement 0.00 ft (dead weight at adequate candidate count)
WARN front ablate early_reflection at ±20° (72 candidates): movement 0.00 ft (dead weight at adequate candidate count)
PASS front ablate geometry at ±20° (72 candidates): movement 2.46 ft
WARN front ablate headroom at ±20° (72 candidates): movement 0.00 ft (dead weight at adequate candidate count)
PASS bass ablate flatness at all candidates (54 candidates): movement 11.95 ft
WARN bass ablate null_penalty at all candidates (54 candidates): movement 0.00 ft (dead weight at adequate candidate count)
PASS random valid candidate layouts: 200 / 200 draws; per-role distributions follow
INFO Per-role comparison (scores are dB-like; do not sum across unlike role metrics):
  front selected group 9.14, matched candidate mean 14.17 | rule group 9.14 | random group mean 8.01 | Δrandom +1.12, Δrule +0.00 dB-like | percentile 95.7 | terms optimized [clarity_db=12.26, off_axis_db=-0.02, early_reflection_db=4.50, headroom_db=-12.40, reflection_directivity_gain_db=-8.10, geometry_db=-5.12] vs rule [clarity_db=12.26, off_axis_db=-0.02, early_reflection_db=4.50, headroom_db=-12.40, reflection_directivity_gain_db=-8.10, geometry_db=-5.12]
  bass selected group -14.89, matched candidate mean -14.83 | rule group -19.77 | random group mean -17.43 | Δrandom +2.54, Δrule +4.88 dB-like | percentile 97.9 | terms optimized [flatness=-10.26, null_penalty=-0.16, geometry_db=0.00, headroom_db=-22.32] vs rule [flatness=-15.86, null_penalty=-0.22, geometry_db=0.00, headroom_db=-18.42]
INFO Random legal candidate layouts are scored as groups; the rule-of-thumb is rescored with the same role scorer. Roles where optimized group score loses: none
PASS listener sweep evaluated 25 grid points (25 with legal layouts), all listener points at least 3 ft from walls; largest adjacent spacing change 5.34 ft; 10 bass wall transitions
  bass wall transition (3.0,3.0) -> (5.2,3.0) ft; runner-up gap 0.000 dB-like
  bass wall transition (5.2,3.0) -> (7.5,3.0) ft; runner-up gap 0.913 dB-like
  bass wall transition (7.5,3.0) -> (9.8,3.0) ft; runner-up gap 0.913 dB-like
  bass wall transition (9.8,3.0) -> (12.0,3.0) ft; runner-up gap 0.695 dB-like
  bass wall transition (5.2,4.5) -> (7.5,4.5) ft; runner-up gap 0.235 dB-like
  bass wall transition (7.5,4.5) -> (9.8,4.5) ft; runner-up gap 0.235 dB-like
  bass wall transition (5.2,6.0) -> (7.5,6.0) ft; runner-up gap 0.350 dB-like
  bass wall transition (7.5,6.0) -> (9.8,6.0) ft; runner-up gap 0.085 dB-like
  bass wall transition (5.2,9.0) -> (7.5,9.0) ft; runner-up gap 0.896 dB-like
  bass wall transition (7.5,9.0) -> (9.8,9.0) ft; runner-up gap 0.663 dB-like
INFO room 10x8 ft alpha 0.05: modal count 30-150 Hz 6, smallest adjacent gap 7.96 Hz, per-role scores front=0.41, bass=-16.68
INFO room 10x8 ft alpha 0.20: modal count 30-150 Hz 6, smallest adjacent gap 7.96 Hz, per-role scores front=2.75, bass=-16.24
INFO room 10x8 ft alpha 0.60: modal count 30-150 Hz 6, smallest adjacent gap 7.96 Hz, per-role scores front=28.13, bass=-15.92
INFO room 10x10 ft alpha 0.05: modal count 30-150 Hz 4, smallest adjacent gap 13.28 Hz, per-role scores front=3.20, bass=-15.03
INFO room 10x10 ft alpha 0.20: modal count 30-150 Hz 4, smallest adjacent gap 13.28 Hz, per-role scores front=8.60, bass=-14.37
INFO room 10x10 ft alpha 0.60: modal count 30-150 Hz 4, smallest adjacent gap 13.28 Hz, per-role scores front=30.63, bass=-13.86
INFO room sweep 10x12.5 ft alpha 0.05 has no legal placement for this fixed role layout: No legal placements for speaker type 'front'
INFO room sweep 10x12.5 ft alpha 0.2 has no legal placement for this fixed role layout: No legal placements for speaker type 'front'
INFO room sweep 10x12.5 ft alpha 0.6 has no legal placement for this fixed role layout: No legal placements for speaker type 'front'
INFO room sweep 10x15.0 ft alpha 0.05 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room sweep 10x15.0 ft alpha 0.2 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room sweep 10x15.0 ft alpha 0.6 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room 12x10 ft alpha 0.05: modal count 30-150 Hz 8, smallest adjacent gap 6.63 Hz, per-role scores front=0.65, bass=-14.01
INFO room 12x10 ft alpha 0.20: modal count 30-150 Hz 8, smallest adjacent gap 6.63 Hz, per-role scores front=5.63, bass=-13.70
INFO room 12x10 ft alpha 0.60: modal count 30-150 Hz 8, smallest adjacent gap 6.63 Hz, per-role scores front=25.09, bass=-13.73
INFO room 12x12 ft alpha 0.05: modal count 30-150 Hz 7, smallest adjacent gap 7.61 Hz, per-role scores front=4.94, bass=-13.54
INFO room 12x12 ft alpha 0.20: modal count 30-150 Hz 7, smallest adjacent gap 7.61 Hz, per-role scores front=10.18, bass=-12.98
INFO room 12x12 ft alpha 0.60: modal count 30-150 Hz 7, smallest adjacent gap 7.61 Hz, per-role scores front=31.02, bass=-12.69
INFO room 12x15 ft alpha 0.05: modal count 30-150 Hz 13, smallest adjacent gap 0.90 Hz, per-role scores front=-10.01, bass=-17.10
INFO room 12x15 ft alpha 0.20: modal count 30-150 Hz 13, smallest adjacent gap 0.90 Hz, per-role scores front=-5.18, bass=-16.37
INFO room 12x15 ft alpha 0.60: modal count 30-150 Hz 13, smallest adjacent gap 0.90 Hz, per-role scores front=12.97, bass=-15.40
INFO room sweep 12x18.0 ft alpha 0.05 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room sweep 12x18.0 ft alpha 0.2 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room sweep 12x18.0 ft alpha 0.6 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room 15x12 ft alpha 0.05: modal count 30-150 Hz 13, smallest adjacent gap 0.90 Hz, per-role scores front=4.19, bass=-15.20
INFO room 15x12 ft alpha 0.20: modal count 30-150 Hz 13, smallest adjacent gap 0.90 Hz, per-role scores front=9.14, bass=-14.89
INFO room 15x12 ft alpha 0.60: modal count 30-150 Hz 13, smallest adjacent gap 0.90 Hz, per-role scores front=28.13, bass=-15.10
INFO room 15x15 ft alpha 0.05: modal count 30-150 Hz 8, smallest adjacent gap 6.09 Hz, per-role scores front=5.94, bass=-14.93
INFO room 15x15 ft alpha 0.20: modal count 30-150 Hz 8, smallest adjacent gap 6.09 Hz, per-role scores front=10.52, bass=-14.41
INFO room 15x15 ft alpha 0.60: modal count 30-150 Hz 8, smallest adjacent gap 6.09 Hz, per-role scores front=27.74, bass=-13.80
INFO room 15x19 ft alpha 0.05: modal count 30-150 Hz 18, smallest adjacent gap 0.72 Hz, per-role scores front=-21.34, bass=-14.89
INFO room 15x19 ft alpha 0.20: modal count 30-150 Hz 18, smallest adjacent gap 0.72 Hz, per-role scores front=-16.82, bass=-14.11
INFO room 15x19 ft alpha 0.60: modal count 30-150 Hz 18, smallest adjacent gap 0.72 Hz, per-role scores front=0.20, bass=-13.78
INFO room sweep 15x22.5 ft alpha 0.05 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room sweep 15x22.5 ft alpha 0.2 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room sweep 15x22.5 ft alpha 0.6 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room 18x14 ft alpha 0.05: modal count 30-150 Hz 17, smallest adjacent gap 0.75 Hz, per-role scores front=0.07, bass=-15.06
INFO room 18x14 ft alpha 0.20: modal count 30-150 Hz 17, smallest adjacent gap 0.75 Hz, per-role scores front=4.61, bass=-14.70
INFO room 18x14 ft alpha 0.60: modal count 30-150 Hz 17, smallest adjacent gap 0.75 Hz, per-role scores front=21.45, bass=-14.29
INFO room 18x18 ft alpha 0.05: modal count 30-150 Hz 12, smallest adjacent gap 3.74 Hz, per-role scores front=4.60, bass=-12.45
INFO room 18x18 ft alpha 0.20: modal count 30-150 Hz 12, smallest adjacent gap 3.74 Hz, per-role scores front=9.09, bass=-11.60
INFO room 18x18 ft alpha 0.60: modal count 30-150 Hz 12, smallest adjacent gap 3.74 Hz, per-role scores front=25.38, bass=-11.00
INFO room 18x22 ft alpha 0.05: modal count 30-150 Hz 24, smallest adjacent gap 0.60 Hz, per-role scores front=0.35, bass=-13.77
INFO room 18x22 ft alpha 0.20: modal count 30-150 Hz 24, smallest adjacent gap 0.60 Hz, per-role scores front=4.65, bass=-12.85
INFO room 18x22 ft alpha 0.60: modal count 30-150 Hz 24, smallest adjacent gap 0.60 Hz, per-role scores front=19.43, bass=-12.27
INFO room sweep 18x27.0 ft alpha 0.05 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room sweep 18x27.0 ft alpha 0.2 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room sweep 18x27.0 ft alpha 0.6 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room 20x16 ft alpha 0.05: modal count 30-150 Hz 20, smallest adjacent gap 0.68 Hz, per-role scores front=6.20, bass=-15.32
INFO room 20x16 ft alpha 0.20: modal count 30-150 Hz 20, smallest adjacent gap 0.68 Hz, per-role scores front=10.30, bass=-14.83
INFO room 20x16 ft alpha 0.60: modal count 30-150 Hz 20, smallest adjacent gap 0.68 Hz, per-role scores front=25.33, bass=-14.35
INFO room 20x20 ft alpha 0.05: modal count 30-150 Hz 13, smallest adjacent gap 2.79 Hz, per-role scores front=3.24, bass=-13.66
INFO room 20x20 ft alpha 0.20: modal count 30-150 Hz 13, smallest adjacent gap 2.79 Hz, per-role scores front=7.60, bass=-12.92
INFO room 20x20 ft alpha 0.60: modal count 30-150 Hz 13, smallest adjacent gap 2.79 Hz, per-role scores front=23.15, bass=-12.53
INFO room 20x25 ft alpha 0.05: modal count 30-150 Hz 30, smallest adjacent gap 0.54 Hz, per-role scores front=1.29, bass=-14.64
INFO room 20x25 ft alpha 0.20: modal count 30-150 Hz 30, smallest adjacent gap 0.54 Hz, per-role scores front=5.40, bass=-14.20
INFO room 20x25 ft alpha 0.60: modal count 30-150 Hz 30, smallest adjacent gap 0.54 Hz, per-role scores front=19.59, bass=-13.64
INFO room sweep 20x30.0 ft alpha 0.05 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room sweep 20x30.0 ft alpha 0.2 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room sweep 20x30.0 ft alpha 0.6 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room 25x20 ft alpha 0.05: modal count 30-150 Hz 30, smallest adjacent gap 0.54 Hz, per-role scores front=5.55, bass=-13.71
INFO room 25x20 ft alpha 0.20: modal count 30-150 Hz 30, smallest adjacent gap 0.54 Hz, per-role scores front=9.41, bass=-13.31
INFO room 25x20 ft alpha 0.60: modal count 30-150 Hz 30, smallest adjacent gap 0.54 Hz, per-role scores front=22.77, bass=-13.60
INFO room 25x25 ft alpha 0.05: modal count 30-150 Hz 20, smallest adjacent gap 1.77 Hz, per-role scores front=4.16, bass=-13.93
INFO room 25x25 ft alpha 0.20: modal count 30-150 Hz 20, smallest adjacent gap 1.77 Hz, per-role scores front=8.18, bass=-13.50
INFO room 25x25 ft alpha 0.60: modal count 30-150 Hz 20, smallest adjacent gap 1.77 Hz, per-role scores front=21.73, bass=-13.01
INFO room 25x31 ft alpha 0.05: modal count 30-150 Hz 45, smallest adjacent gap 0.07 Hz, per-role scores front=1.41, bass=-14.01
INFO room 25x31 ft alpha 0.20: modal count 30-150 Hz 45, smallest adjacent gap 0.07 Hz, per-role scores front=5.12, bass=-13.76
INFO room 25x31 ft alpha 0.60: modal count 30-150 Hz 45, smallest adjacent gap 0.07 Hz, per-role scores front=16.62, bass=-14.04
INFO room sweep 25x37.5 ft alpha 0.05 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room sweep 25x37.5 ft alpha 0.2 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
INFO room sweep 25x37.5 ft alpha 0.6 has no legal placement for this fixed role layout: No valid candidates for speaker type 'front'; check its walls, angle window, and spacing
PASS room/absorption sweep completed 51 configurations; bass/mode locations vary with geometry
INFO default 15x12 ft bass score -14.89 ranks 15/17 at alpha 0.20; 13 modes in 30-150 Hz, nearest distinct gap 0.90 Hz
INFO convergence baseline candidate spacing 0.25 m; bass frequency step 1.00 Hz; equivalence threshold 0.50 dB
PASS bass frequency step 0.50 Hz score shift +0.000 dB-like from baseline; equivalent optimum=True
PASS bass frequency step 1.00 Hz score shift +0.000 dB-like from baseline; equivalent optimum=True
PASS bass frequency step 2.00 Hz score shift +0.000 dB-like from baseline; equivalent optimum=True
WARN placement convergence maximum movement 11.71 ft across 10 numerical settings
PASS near-anechoic direct arrival 28 samples vs 28.0; post-direct energy 0.0009
PASS bottom-wall image-source echo predicted at 79.7 samples; local peak 80.0 samples
PASS first axial mode 37.51 Hz; analytic formula verified by room_modes
PASS symmetric coherent bass response max difference 0.000e+00

SPEC INFLUENCE (single-role ±20% model perturbations)
field | changed outputs; unchanged numeric specs are labeled informational only
front / freq_low_hz: informational only
front / freq_high_hz: informational only
front / crossover_hz: informational only
front / crossover_slope_db_oct: informational only
front / sensitivity_db: predicted SPL, score
front / rated_power_w: predicted SPL, score
front / max_spl_db: score
front / nominal_impedance_ohm: informational only
front / coverage_h_deg: score, toe-in
front / coverage_v_deg: informational only (2D model)
front / width_m: informational only
front / height_m: informational only (2D model)
front / depth_m: informational only
front / min_corner_clearance_m: informational only
front / min_listening_distance_m: informational only
front / max_listening_distance_m: informational only
front / min_spacing_to_other_speakers_m: informational only
front / wall_gain_db: predicted SPL, score
front / f3_hz: informational only
front / highpass_slope_db_oct: informational only
front / max_toe_in_deg: toe-in
front / coverage_h_vs_freq: informational only (unset)
front / polar_table: informational only (unset)
front / on_axis_response: informational only (unset)
front / mount_height_range_m: informational only (2D model)
front / directivity_band_weights: informational only for current frequency-flat model
bass / freq_low_hz: informational only
bass / freq_high_hz: position, predicted SPL, score
bass / crossover_hz: score
bass / crossover_slope_db_oct: score
bass / sensitivity_db: predicted SPL, score
bass / rated_power_w: predicted SPL, score
bass / max_spl_db: informational only
bass / max_spl_lf_db: score
bass / nominal_impedance_ohm: informational only
bass / coverage_h_deg: informational only
bass / coverage_v_deg: informational only (2D model)
bass / width_m: informational only
bass / height_m: informational only (2D model)
bass / depth_m: informational only
bass / min_corner_clearance_m: informational only
bass / min_listening_distance_m: informational only
bass / max_listening_distance_m: informational only
bass / min_spacing_to_other_speakers_m: informational only
bass / wall_gain_db: predicted SPL, score
bass / f3_hz: informational only
bass / highpass_slope_db_oct: informational only
bass / max_toe_in_deg: informational only
bass / coverage_h_vs_freq: informational only (unset)
bass / polar_table: informational only (unset)
bass / on_axis_response: informational only (unset)
bass / mount_height_range_m: informational only (2D model)
bass / directivity_band_weights: informational only for current frequency-flat model
Surround model comparison (same room and constraints):
generic_narrow_onwall: positions [(0.16, 2.81), (14.84, 2.81)] ft, toe-in [20, -20], score 15.28
generic_surround_wide: positions [(0.16, 2.81), (14.84, 2.81)] ft, toe-in [45, -45], score 10.34
generic_dipole_surround: positions [(0.16, 2.81), (14.84, 2.81)] ft, toe-in [-80, 80], score 9.69
dipole listener-to-null deviation: 0.8° (usual guidance targets 0° deviation)
Bass F3 sensitivity:
F3 25 Hz: bass score -14.88; usable 30-200 Hz fraction 0.530
F3 45 Hz: bass score -14.79; usable 30-200 Hz fraction 0.442
Sensitivity basis check (4 ohm, same acoustic sensitivity): normalized SPL delta +0.000 dB

SUMMARY
front: percentile 95.7; Δrandom +1.12; Δrule +0.00 dB-like; acoustics-only deviation 23.9 ° from textbook angle; answer-changing terms geometry
bass: percentile 97.9; Δrandom +2.54; Δrule +4.88 dB-like; acoustics-only deviation 4.2 ft from textbook positions; answer-changing terms flatness
generic_narrow_onwall: positions [(0.16, 2.81), (14.84, 2.81)] ft, toe-in [20, -20], score 15.28
generic_surround_wide: positions [(0.16, 2.81), (14.84, 2.81)] ft, toe-in [45, -45], score 10.34
generic_dipole_surround: positions [(0.16, 2.81), (14.84, 2.81)] ft, toe-in [-80, 80], score 9.69
dipole listener-to-null deviation: 0.8° (usual guidance targets 0° deviation)
F3 25 Hz: bass score -14.88; usable 30-200 Hz fraction 0.530
F3 45 Hz: bass score -14.79; usable 30-200 Hz fraction 0.442
Sensitivity basis check (4 ohm, same acoustic sensitivity): normalized SPL delta +0.000 dB
Bass peak-to-dip response swing 55.03 dB. Placement alone cannot flatten the response in a small room; equalization, treatment, or additional subwoofers may be needed.
The modal model is 2D and omits floor-to-ceiling modes; those require a 3D room model.
Validation plots: output/final-deliverable/validation
```
