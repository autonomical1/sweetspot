# Wall-Mounted Speaker Placement Optimizer

A Python CLI with a 2D room-acoustics optimizer and an interactive 3D layout viewer. The optimizer works in metres internally; the CLI accepts room dimensions in feet and can edit polygonal rooms. Speakers are wall-mounted. Model registry values are generic placeholders and must be replaced with measured or manufacturer datasheet specifications before using results for installation.

## Environment and quick start

```sh
conda env create --prefix ./.conda-env --file environment.yml
conda activate "$PWD/.conda-env"
python -m speakerplacer --length 15 --width 12 --listener 7.5 4 --facing north \
  --speakers front:2:generic_inwall_lcr surround:2:generic_surround_wide bass:2:generic_inwall_sub \
  --mode 3d --height 8 --materials walls=drywall,floor=carpet,ceiling=tile \
  --save-layout output/layout.json --save-candidates output/candidates.json
```

The command prints progress and a speaker table, saves the usual 2D plots plus `output/layout_3d.png`, and opens a rotatable 3D room. `--mode 3d` is the default. Drag to rotate, scroll or right-drag to zoom, and middle-drag to pan. Use the side-panel checkboxes for walls, labels, arrows, listener lines, coverage cones, candidate dots, reflections, and the ear-height plane. The Top, Front, Side, and Perspective buttons reset the camera; Save PNG writes the current view. Keyboard shortcuts are **T/F/S/P** for views, **L** for labels, **C** for coverage, and **Q** to close.

Select a channel preset with `--layout 5.1`, `7.1`, `7.1.4`, or `7.2.4` and an angle-reference table with `--standard dolby` (also `itu`, `thx`, or `custom`). These standard tables are initial seeds marked `verify`, not certified installation instructions. `--channel-model C=generic_center_inwall` and `--role-model surround=generic_surround_wide` select models; `--channel-angle L=-30:-35:-25` overrides a channel's signed target and limits. Optional `--screen-height` sets front-stage height policy. To reserve a door or window, add `--keepout wall=north,u=1.2:2.1,z=0:2.1,label=door` (wall coordinates and height are metres). Keep-outs constrain wall-mounted cabinet footprints and appear in the viewer. The CLI prints MLP and per-seat angle compliance and receiver delay/trim suggestions. `--subs 1|2|4` controls the joint sub count; 7.2.4 uses two by default. Sub candidates use wall, floor, ceiling, or corner surfaces supported by the selected model.

Use `--design-room` with initial `--length` and `--width` values to open the room designer before optimization. Drag the corner handles, double-click a wall to insert another corner, and select the theatre format (including 5.1, 5.2, 7.1, and 7.2) in the side panel. Press **Optimize** to start placement using the resulting room polygon and selected channel layout. The 2D room geometry and wall-mounted placement use the actual polygon; low-frequency modal estimates use an equivalent bounding rectangle for irregular rooms.

Seat grids use `--seats rows=2,seats=3,seat_spacing=0.7,row_spacing=1.1,riser=0.2,ear_height=1.1` and `--mlp row=1,seat=2`; positions and ear heights are stored in JSON and chairs are drawn in the viewer. Imaging terms evaluate all seats, with `--mlp-weight` controlling the MLP share. Bass scoring evaluates the modeled seats and exports `seat_bass_response.png` with axial-mode markers. First-order L/C/R reflection coordinates and suggested panel rectangles are in layout JSON and `report.md`; toggle **Reflections** in the viewer to show paths and points. `--treatment-preset carpeted|draped|treated_theater|bass_trapped` selects typical material coefficients; `--materials` overrides selected surfaces. RT60 by band, 3D room modes, near coincidences, per-seat angle checks, SBIR quarter-wave estimates, and a max-SPL-capped headroom derivation appear in the report. `--crossover-hz` and `--lfe-gain-db` set the LR4 reference diagnostic and LFE reference convention. Receiver delay/trim warning thresholds are configurable with `--receiver-max-delay-ms` and `--receiver-max-trim-db`; `--rt60-target` sets the advisory target.

For a batch or headless run, add `--no-show --save-views`; this saves `layout_3d.png` and four preset-view PNGs. If Matplotlib has a noninteractive backend such as Agg or no display is available, the same images are saved automatically and the CLI prints a backend hint. To reopen a saved scene without running the optimizer again:

```sh
python -m speakerplacer --view-layout output/layout.json
```

`--mode 2d` opens the earlier 2D plots instead. `--no-view3d` disables the 3D window while still saving its base PNG. The 3D camera can be set with `--view-elev DEG --view-azim DEG`; `--show-coverage`, `--show-candidates`, and `--show-reflections IDX` enable optional layers at startup (`IDX` is zero-based). `--height`, `--ear-height`, `--screen-height`, repeated `--mount-height ROLE=FEET`, and `--panel-protrusion-mm` configure room and display geometry. The optimizer includes role-specific 15 cm wall-height choices in its scoring and candidate heatmap. Vertical polar response affects the score, and the selected z and allowed range are saved per speaker. Wall-sub heights span the available mounting range with cabinet clearances. The room impulse response itself remains horizontal 2D, so z does not yet change its image-source paths.

Use `--materials walls=drywall,floor=carpet,ceiling=tile` or `--treatment-preset treated_theater` to select octave-band room estimates. Material presets are typical approximations. `--save-candidates PATH` writes the height-grid samples separately from the compact layout JSON; `--view-layout` reloads the optional candidate file when the layout references it. A YAML run config can set argument defaults, with CLI flags taking precedence:

```yaml
length: 15
width: 12
height: 8
facing: north
materials: walls=drywall,floor=carpet,ceiling=tile
speakers: [front:2, surround:2, bass:2]
```

Save that as `run.yaml`, then run `python -m speakerplacer --config run.yaml --listener 7.5 4 --no-show`.

Speaker boxes use model width, height, and depth. An on-wall box projects into the room by its specified depth; in-wall and flush boxes use a visible panel depth (12 mm by default). A rigid box that yaws or tilts cannot keep its entire back face on the wall. The viewer rotates about the mounting center, then moves the box inward just enough that its closest back corner touches the wall; at zero yaw and tilt, its full back face is flush. Matplotlib's 3D renderer can sort transparent faces imperfectly, so walls are faint and the nearest wall and ceiling faces start hidden.

Room/model comparison output is also a 3D view and includes speaker position, mounting height, yaw, and tilt. The layout JSON uses schema 2 and records coordinate conventions, units, the wall-index map, aim-vector direction, and the difference between the wall-plane mount point and the optimizer's 1 mm inward source position.

Sample render from the 15 × 12 × 8 ft example:

![Perspective 3D speaker layout](output/cleanup/layout_3d_perspective.png)

Additional [top](output/cleanup/layout_3d_top.png), [front](output/cleanup/layout_3d_front.png), and [side](output/cleanup/layout_3d_side.png) views are saved alongside the [layout JSON](output/cleanup/layout.json) and [candidate sidecar](output/cleanup/candidates.json).

Counts are customizable. Each argument is `ROLE:COUNT[:MODEL_ID]`; omitting the model selects the role default. Paired roles require an even count. `center:1` selects the on-wall center placeholder, and a single subwoofer is allowed with `bass:1`. For example, `--speakers front:2 center:1 surround:2 bass:1` requests a basic 5.1 wall layout. List available placeholder models with:

```sh
python -m speakerplacer --list-models
```

The default layout is `front:2 surround:2 bass:2`. `--priority` changes the initial order; an optional coordinate-descent pass then re-optimizes each role with other roles held fixed, using per-role normalized scores. `--modal-q-scale` configures bass damping; `--target-spl` and `--peak-headroom-db` set listener-level SPL targets (`--reference-spl` and `--peak-headroom` remain aliases); `--coherence` selects coherent or incoherent speaker summation; `--toe-in-range MIN MAX` sets signed swivel bounds; `--disable-reflection-directivity` turns off the first-order reflection directivity estimate. The CLI writes candidate scores, recommended placements, best response, and a role-specific model comparison to the selected directory.

To view a full preset-driven room with three seats, activate the project environment and run:

```sh
conda activate "$PWD/.conda-env"
python -m speakerplacer --mode 3d --length 18 --width 14 --height 9 \
  --listener 9 5 --facing north --standard dolby --layout 7.1.4 \
  --seats rows=2,seats=3,seat_spacing=0.7,row_spacing=1.1,riser=0.2,ear_height=1.1 \
  --mlp row=1,seat=2 --fast --save-layout output/layout-7.1.4.json \
  --output output/home-theater
```

This opens the interactive 3D viewer and saves the layout JSON, compliance/delay report, reflection guidance, seat bass figure, and sub-strategy comparison. Remove `--fast` for the finer wall and ceiling search; reference presets at 18×14×9 ft complete in a few seconds in fast mode on the development machine.

Use `--bass-count 1`, `--bass-count 2`, or `--bass-count 4` to run the optional one/two/four-subwoofer response experiment. The command compares all three counts and saves `bass_count_experiment.png`; additional speakers do not guarantee monotonic improvement in a coherent small-room response.

Run the physics and sensitivity checks with `--validate`. A human-readable report and plots are written to `OUTPUT/validation/`, including score spread, hard/wide/soft/acoustics-only angle-filter comparison, widened term ablations, 200 randomized legal candidate layouts, a rule-of-thumb baseline rescored with the same group metric, a 5×5 listener grid, room/absorption sweeps, numerical convergence, analytic RIR/modal checks, and a bass perimeter heatmap. Candidate percentiles and random/rule improvements are reported separately for each role. Cross-room combined scores use per-role z-scores. The report ends with a per-role SUMMARY. The first-order reflection directivity calculation uses image geometry; timing overhead is measured in each report and higher-order RIR taps are not individually decomposed. Validation may take several minutes because it runs repeated image-source simulations.

## Speaker models

`SpeakerModel` is defined in `speakerplacer/speaker_models.py`; the default registry is in `speakerplacer/speaker_models.yaml`. All entries are illustrative placeholders, not real manufacturer data. The generic archetypes include:

| Model ID | Intended roles | Placeholder range | Coverage | Mount |
|---|---|---:|---:|---|
| `generic_compact_wall` | front, surround | 100–20,000 Hz | 110° | on wall |
| `generic_bookshelf_onwall` | front, surround | 80–20,000 Hz | 90° | on wall |
| `generic_inwall_lcr` | front | 70–20,000 Hz | 80° | in wall |
| `generic_center_onwall` | center/front | 80–20,000 Hz | 120° horizontal, 40° vertical | on wall |
| `generic_center_inwall` | center/front | 70–20,000 Hz | 120° horizontal, 40° vertical | in wall |
| `generic_narrow_onwall` | front, surround | 90–20,000 Hz | 60° | on wall |
| `generic_surround_wide` | surround | 120–20,000 Hz | 120° | on wall |
| `generic_inwall_sub` | bass | 25–200 Hz | 360° | in wall |
| `generic_onwall_sub` | bass | 30–200 Hz | 360° | on wall |
| `generic_dipole_surround` | surround | 100–20,000 Hz | 360° | on wall |
| `generic_onwall_sub_ported` | bass | 25–200 Hz | 360° | on wall |
| `generic_floorstanding_tower` | front, surround | 40–20,000 Hz | 90° | floor standing |
| `generic_stand_bookshelf` | front, surround | 65–20,000 Hz | 100° | stand mounted |
| `generic_floor_sub` | bass | 25–200 Hz | 360° | floor standing |
| `generic_ceiling_sub` | bass | 30–200 Hz | 360° | on ceiling |

The YAML model file supports response curves, horizontal and vertical polar CSV data, frequency-dependent horizontal coverage, sensitivity basis, amplifier power, LF maximum SPL, acoustic-center offsets, in-wall cutout width, floor source height/clearance, listening distance/spacing recommendations, enclosure alignment, toe/tilt limits, and mounting bounds. Horizontal and vertical polar responses are combined separably. Use `--models-file PATH`, `--validate-models`, `--describe-model ID`, and `--role ROLE --list-models` to inspect and load models. Inline overrides use `front:2:generic_inwall_lcr@sensitivity_db=89,coverage_h_deg=75`; quote the whole speaker token in shells. Replace placeholder data with verified values from the exact speaker's datasheet or measurements. Polar CSVs use `angle_deg` plus frequency columns in Hz; response CSVs use `hz,db`.

Installation planning can optionally snap in-wall and in-ceiling cutouts to framing bays with `--stud-spacing 16in|24in` and `--joist-spacing 16in|24in`; a too-wide cutout reports that it needs a header. The viewer's **Studs / joists** toggle displays the assumed framing grid. `--allow-floor` adds independent L/C/R floor or stand alternatives, their wall comparison, clearance, coverage and SBIR estimate; choose a `--floor-model` and `--floor-wall-clearance` as needed. These alternatives are clearly identified because the current primary optimizer still solves wall positions.

`--screen-loss-db 125:1,250:2,1000:3,4000:4` adds an octave-band insertion-loss curve for a dummy/transparent screen to L/C/R headroom estimates. Existing `--keepout` rectangles can model front-wall screen/door areas. Bass setup reporting runs an LR4 direct-field sweep around `--crossover-hz`, then refines gain, delay and polarity for each sub; `report.md` and `bass_management_response.png` show the recommended controls and the summed magnitude/phase by seat. Treat these as starting estimates and confirm them with measurements.

Every normal layout run now includes a screen and projector estimate, using generic 100-inch 16:9 / 3000-lumen planning placeholders when no specs are supplied. These placeholders also render in the 3D viewer and act as screen/projector keep-outs. Override them with YAML (`--screen-spec screen.yaml --projector-spec projector.yaml`) or inline values, for example `--screen 'diag_in=120,aspect=16:9,bottom_in=24,gain=1' --projector 'throw_ratio=1.4:2.2,lumens=3000,throw_ft=14'`. `--check-display` evaluates the display and writes `display_report.md` plus `display.json`; a normal layout run stores display geometry, throw, zoom, brightness, contrast, lens-shift estimate, and seat metrics in the layout JSON and `report.md`. Unit suffixes `_in`, `_ft`, and `_m` are normalized at input. `--ambient-light dark|dim|lit` or a lux number, `--target-fl`, `--noise-floor-dba`, and `--lumen-derate` configure the estimates. `--init-specs DIR` writes generic, explicitly non-product templates. A throw outside the projector zoom range is reported with the implied ratio and nearest feasible distance/width. Targets and generic projector values are planning assumptions and should be checked against the supplied datasheet. Solid screens and projector-body/ventilation boxes are hard speaker-placement exclusions, including for ATS screens; the front stage may move outside its standard azimuth window to find a clear position, and compliance warns about that deviation. Use `--no-display` to explicitly skip display planning. Beam/head-frustum collision, riser-aware sightline occlusion, and area-weighted screen-wall absorption remain limitations.

The optimizer searches horizontal position, yaw, and role-bounded wall height jointly, with mirrored pairs. Front channels follow a near-ear elevation sector (or `--screen-height`), surrounds use a 0.6–1.2 m elevation above the ears, and bass is constrained low. Vertical polar gain contributes to the imaging score; the 2D RIR and modal field still omit z-dependent paths and floor/ceiling modes. Bass uses a 3×3 seat cluster at 0.3 m spacing: modal pressure power is averaged over seats, spatial variation is penalized, and the exact-point response is retained for reports. The 2D modal solver uses per-mode wall damping based on the surfaces involved in each axial, tangential, or oblique mode.

Headroom is `available_peak - required_peak`; positive values mean the speaker can meet the target. Available peak is rated-power listener SPL capped by the model's maximum SPL converted from 1 m to the listener distance. Regular speakers require target average SPL + the configured peak allowance (default 85 + 20 dB); bass/LFE uses a 10 dB allowance. Sensitivity is normalized to 1 W at 1 m, and power is `min(rated_power_w, amp_power_w)` when an amp cap is supplied. The level estimate adds direct and diffuse reverberant energy with `Lp = Lw + 10 log10(Q/(4πr²) + 4/R)` and reports critical distance. It is a room estimate, not a substitute for measured response. The coincident mounting-wall image is kept, sources are only 1 mm inside the wall for the image-source solver, and the legacy `wall_gain_db` is not added again; this models up to +6 dB from the boundary image without a delayed own-wall comb notch. Layout JSON records relative receiver delay `(d_max-d_i)/c` and free-field trim `20 log10(d_i/d_ref)` for each speaker.

`--materials` provides typical absorption approximations in six octave bands from 125 Hz through 4 kHz. Sabine and Eyring RT60 estimates use `0.161 V/(S α)` and `0.161 V/(-S ln(1-α))`. The validation report filters the selected RIR by octave band for C50, C80, D50, and measured RT60. The analytical material/RT60 and diffuse-field SPL estimates include floor and ceiling surfaces, while the image-source RIR remains a horizontal wall-only model.

The `--toe-in-range MIN MAX` option applies signed limits to the toe-in search, overriding the model swivel limit when explicitly supplied. Constrained roles also receive exact-target and 0.5° fan candidates from analytic wall-ray intersections; warnings mark toe-in limits, angle-window edges, and recommended listener-distance violations.

`speakerplacer/home_theater.py` implements receiver delay/trim, LR4 transfer functions and phase-mismatch, quarter-wave, reflection-point and geometry-compliance calculations. `speakerplacer/standards.yaml` records initial ITU/Dolby channel-angle targets and 5.1 through 9.1.6 channel lists; it remains marked `verify` because several ranges are implementation seeds. Wall channels in presets are optimized individually; overhead channels are searched on a ceiling grid after wall optimization. ITU-R BS.775-3 specifies L/R at ±30° and LS/RS in a 100°–120° sector; Dolby's 7.1.4 setup guide illustrates overhead angle bounds around 30°–55° ([ITU-R BS.775-3](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.775-3-201208-S%21%21PDF-E.pdf), [Dolby 7.1.4 setup guide](https://www.dolby.com/siteassets/about/support/guide/setup-guides/7.1.4-overhead-speaker-placement/7_1_4_overhead_speaker_setup.pdf)). The `thx` seed currently copies Dolby ranges and `custom` copies ITU ranges before per-channel overrides; neither implies endorsement by those organizations.

## Physics and scoring

Imaging roles use pyroomacoustics image-source RIRs, C50 clarity, model directivity, early-reflection energy, and geometry. The modal bass model calculates rectangular-room modes using `f_nm = (c / 2) * sqrt((n / Lx)^2 + (m / Ly)^2)`, omitting `(0, 0)`, and mode shapes `cos(n*pi*x/Lx) * cos(m*pi*y/Ly)`. Complex source pressures can be summed coherently or incoherently before scoring modal response flatness and null depth. With material inputs, damping is computed from the mean absorption of the wall pairs that each mode uses; the fallback scalar mapping remains `Q = modal_q_scale / sqrt(max(absorption, 0.01))`.

Modal scoring requires a rectangular four-corner room and omits floor-to-ceiling modes. Imaging off-axis scores average the model's horizontal gain at 500, 1000, 2000, and 4000 Hz using configurable per-band weights; horizontal and vertical polar tables are interpolated separately. These gains affect the direct-arrival term, while the report's octave metrics filter the selected RIR rather than separating every image-source tap by order. Crossover filters and speaker high-pass response are applied to the synthesized on-axis response used for bass scoring. Directivity reflection handling is a first-order approximation because pyroomacoustics returns a combined RIR rather than separately tagged image-source taps.

## Assumptions and limitations

| Area | Included | Limitation |
|---|---|---|
| Room geometry | Rectangular shoebox dimensions and wall-index mapping | No furniture, openings, or arbitrary non-rectangular 3D shell |
| Imaging roles | Horizontal image-source RIR, directivity, early reflections, filtered C50/C80/D50 | Floor and ceiling reflection paths are not part of the optimizer RIR |
| Mounting wall | Coincident source image at a 1 mm inward numerical offset | Ideal rigid boundary; real wall, baffle, and installation details vary |
| Height and tilt | Hard per-channel elevation windows, role-bounded wall-height search, vertical polar gain, mount-limited tilt, separate overhead ceiling-grid search | RIR paths and bass modal pressure remain 2D; ceiling channels are not jointly refined with wall channels |
| Bass | Joint sub count/position search across supported wall, floor, ceiling, and corner surfaces; full-height wall z candidates; modal seat response; equal-power strategy comparison; optimized direct-field LR4 crossover/gain/delay/polarity; 3D mode table | The bass modal solver omits vertical pressure; crossover tuning is a direct-field estimate rather than measured room correction |
| Installation | Wall keep-outs, acoustic-center offsets, optional 16/24 in stud and joist bay snapping with cutout-fit/header warnings, floor/stand front-stage alternatives, screen transmission-loss input | Framing grid is referenced to the room polygon origin and must be checked against actual construction; floor choices are surfaced as alternatives, not jointly optimized with wall candidates |
| Front-stage/reflections | Per-seat angular compliance, C50 estimates, geometric delay/trim, first-order reflection points and panel rectangles, SBIR quarter-wave estimates, acoustic-screen loss in L/C/R headroom | Full STI is not calculated; treatment panels are advice-only markers |
| Room materials | Typical six-band material presets, treatment presets, Sabine/Eyring RT60 and diffuse SPL estimates | Coefficients are approximate; the optimizer RIR uses one scalar absorption per run and should be replaced by measured data |
| Room-ratio screening | Normalized dimensions and Bonello third-octave mode counts | Bolt-area classification is not evaluated; ratio guidance is advisory only |
| Speaker data | Dimensions, response, directivity, max SPL, sensitivity, mount limits | Built-in models are placeholders; polar interpolation separates horizontal and vertical response |

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

Candidate positions follow polygon edges at 0.25 m spacing, 0.3 m from corners (increased for model footprint), and 1 mm inside the room so the mounting-wall image is effectively coincident. Angles are measured at the listener. Paired types are reflected across the facing axis; both sides of each analytic angle fan are generated. Previously placed speakers reserve space for later types. The modal method currently applies to rectangular rooms.

```sh
python -m pytest
```

The tests cover geometry, analytic candidates, RIR travel time/decay, symmetry and angle constraints, modal sampling/scoring, dipole null aiming, model validation and YAML loading, inline overrides, sensitivity/SPL math, F3/crossover response, polar interpolation, the model wizard, plotted speaker labels, 3D box poses, viewer toggles, headless fallback, and saved-layout round trips.

## Example output and validation run (2026-10-24)

A complete 15 × 12 × 8 ft run with front, surround, and bass pairs is saved under `output/cleanup/`. It includes the 3D-view PNGs, compact schema-2 layout JSON, optional candidate sidecar, room/height heatmap, model comparison, and physics validation report. Recreate it with:

```sh
MPLBACKEND=Agg MPLCONFIGDIR=/tmp/speakerplacer-mpl python -m speakerplacer \
  --mode 3d --length 15 --width 12 --height 8 --listener 7.5 4 --facing north \
  --speakers front:2 surround:2 bass:2 \
  --materials walls=drywall,floor=carpet,ceiling=tile \
  --save-layout output/cleanup/layout.json \
  --save-candidates output/cleanup/candidates.json \
  --no-show --save-views --validate --output output/cleanup
```

The example demonstrates mirrored surround fan placement, legal 15 cm mounting-height choices, room-acoustic estimates, and per-role headroom. Validation reports corrected headroom influence and a surround yaw sweep. The single-speaker yaw diagnostic and mirrored-pair optimizer can choose different angles because the latter scores both speakers jointly. Numerical convergence remains sensitive to candidate-grid transitions; see the report for detailed metrics and warnings.

See the [validation report](output/cleanup/validation/report.txt), [3D layout](output/cleanup/layout_3d_perspective.png), [layout JSON](output/cleanup/layout.json), and [candidate sidecar](output/cleanup/candidates.json).
