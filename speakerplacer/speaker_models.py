"""Validated speaker model specifications and acoustic helper functions.

All registry entries are illustrative placeholders. Replace them with measured
polar/response data or manufacturer datasheets before using installation data.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field, replace, fields
from csv import DictReader
from math import cos, log, log10, pi
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import numpy as np


def _metadata(unit: str, doc: str) -> dict:
    return {"unit": unit, "doc": doc}


@dataclass(frozen=True)
class SpeakerModel:
    """Speaker electrical/acoustic specifications; optional values have defaults.

    Metadata on each dataclass field records its unit and short explanation.
    """
    model_id: str = field(metadata=_metadata("identifier", "Stable registry key."))
    display_name: str = field(default="Generic speaker (PLACEHOLDER)", metadata=_metadata("text", "Human-readable model name."))
    role_types: Tuple[str, ...] = field(default=("front",), metadata=_metadata("roles", "Eligible placement roles."))
    freq_low_hz: float = field(default=80., metadata=_metadata("Hz", "Lower rated frequency edge."))
    freq_high_hz: float = field(default=20000., metadata=_metadata("Hz", "Upper rated frequency edge."))
    crossover_hz: float = field(default=0., metadata=_metadata("Hz", "Acoustic/electrical crossover; zero means unspecified."))
    crossover_slope_db_oct: float = field(default=24., metadata=_metadata("dB/octave", "Crossover filter slope."))
    sensitivity_db: float = field(default=85., metadata=_metadata("dB", "Sensitivity at the selected sensitivity basis."))
    sensitivity_basis: str = field(default="1W_1m", metadata=_metadata("basis", "Either 1W_1m or 2.83V_1m."))
    rated_power_w: float = field(default=50., metadata=_metadata("W", "Continuous/rated input power."))
    amp_power_w: Optional[float] = field(default=None, metadata=_metadata("W", "Available amplifier power per channel; optional cap."))
    max_spl_db: float = field(default=105., metadata=_metadata("dB SPL", "Maximum broadband SPL at 1 m (placeholder)."))
    max_spl_lf_db: Optional[float] = field(default=None, metadata=_metadata("dB SPL", "Bass low-frequency maximum SPL; defaults to max_spl_db."))
    nominal_impedance_ohm: float = field(default=8., metadata=_metadata("ohm", "Nominal impedance used for 2.83 V conversion."))
    coverage_h_deg: float = field(default=90., metadata=_metadata("degrees", "Horizontal coverage angle at the reference frequency."))
    coverage_v_deg: float = field(default=60., metadata=_metadata("degrees", "Vertical coverage; stored for future 3D use."))
    coverage_h_vs_freq: Optional[Tuple[Tuple[float, float], ...]] = field(default=None, metadata=_metadata("Hz, degrees", "Optional horizontal coverage versus frequency."))
    directivity_band_weights: Tuple[float, ...] = field(default=(.25,.25,.25,.25), metadata=_metadata("relative weights", "Off-axis scoring weights at 500, 1000, 2000, and 4000 Hz."))
    directivity_model: str = field(default="cos_n", metadata=_metadata("model", "cos_n, omni, cardioid, dipole, or bipole."))
    polar_table: Optional[Any] = field(default=None, metadata=_metadata("CSV path or rows", "Horizontal polar response relative to on-axis."))
    vertical_polar_table: Optional[Any] = field(default=None, metadata=_metadata("CSV path or rows", "Vertical polar response relative to on-axis; combined separably with horizontal response."))
    on_axis_response: Optional[Any] = field(default=None, metadata=_metadata("Hz, dB or CSV path", "Measured/specified response curve; omitted curves are synthesized."))
    mount_type: str = field(default="on_wall", metadata=_metadata("mount", "on_wall, in_wall, or flush."))
    floor_source_height_m: float = field(default=0., metadata=_metadata("m", "Acoustic-center height for floor/stand placement; zero uses the enclosure center."))
    floor_wall_clearance_m: float = field(default=.3, metadata=_metadata("m", "Minimum cabinet clearance from a room boundary for floor placement."))
    width_m: float = field(default=.25, metadata=_metadata("m", "Enclosure width."))
    height_m: float = field(default=.18, metadata=_metadata("m", "Enclosure height."))
    depth_m: float = field(default=.15, metadata=_metadata("m", "Enclosure depth."))
    cutout_width_m: Optional[float] = field(default=None, metadata=_metadata("m", "In-wall/in-ceiling rough cutout width; defaults to enclosure width."))
    acoustic_center_offset_m: Tuple[float, float] = field(default=(0., 0.), metadata=_metadata("m; vertical, forward", "Acoustic-center shift from box center: vertical offset, then forward depth offset."))
    min_corner_clearance_m: float = field(default=.3, metadata=_metadata("m", "Minimum center clearance from wall endpoints."))
    min_listening_distance_m: float = field(default=.6, metadata=_metadata("m", "Recommended minimum listener distance."))
    max_listening_distance_m: float = field(default=8., metadata=_metadata("m", "Recommended maximum listener distance."))
    min_spacing_to_other_speakers_m: float = field(default=.5, metadata=_metadata("m", "Minimum separation from other speaker enclosures."))
    mount_height_range_m: Tuple[float, float] = field(default=(.5, 2.5), metadata=_metadata("m", "Physical/recommended mount-center height range used by 3D placement."))
    wall_gain_db: float = field(default=3., metadata=_metadata("dB", "Low-frequency wall-boundary gain approximation."))
    f3_hz: float = field(default=0., metadata=_metadata("Hz", "Low-frequency -3 dB point for bass response."))
    enclosure: str = field(default="sealed", metadata=_metadata("alignment", "sealed or ported low-frequency alignment."))
    highpass_slope_db_oct: Optional[float] = field(default=None, metadata=_metadata("dB/octave", "High-pass slope; defaults to 12 sealed or 24 ported."))
    max_toe_in_deg: float = field(default=45., metadata=_metadata("degrees", "Maximum absolute swivel angle; in-wall/flush capped at 10 degrees."))
    max_tilt_deg: Optional[float] = field(default=None, metadata=_metadata("degrees", "Maximum absolute vertical aim; defaults to 5 in-wall, 45 on-wall, and 0 for omni."))

    def __post_init__(self) -> None:
        object.__setattr__(self, "role_types", tuple(self.role_types))
        object.__setattr__(self, "directivity_band_weights", tuple(float(x) for x in self.directivity_band_weights))
        object.__setattr__(self, "mount_height_range_m", tuple(float(x) for x in self.mount_height_range_m))
        object.__setattr__(self, "acoustic_center_offset_m", tuple(float(x) for x in self.acoustic_center_offset_m))
        if self.max_tilt_deg is None:
            default_tilt=0. if self.directivity_model=="omni" else (5. if self.mount_type in ("in_wall","flush") else 45.)
            object.__setattr__(self,"max_tilt_deg",default_tilt)
        if self.highpass_slope_db_oct is None: object.__setattr__(self,"highpass_slope_db_oct",24. if self.enclosure=="ported" else 12.)
        if self.coverage_h_vs_freq is not None:
            object.__setattr__(self, "coverage_h_vs_freq", tuple((float(f), float(a)) for f, a in self.coverage_h_vs_freq))
        lo, hi = self.mount_height_range_m
        if not self.model_id.strip(): raise ValueError("model_id must not be empty")
        numeric=(self.freq_low_hz,self.freq_high_hz,self.crossover_hz,self.crossover_slope_db_oct,self.sensitivity_db,
                 self.rated_power_w,self.max_spl_db,self.nominal_impedance_ohm,self.coverage_h_deg,self.coverage_v_deg,
                 self.width_m,self.height_m,self.depth_m,self.floor_source_height_m,self.floor_wall_clearance_m,self.min_corner_clearance_m,self.min_listening_distance_m,
                 self.max_listening_distance_m,self.min_spacing_to_other_speakers_m,lo,hi,self.wall_gain_db,self.f3_hz,
                 self.highpass_slope_db_oct,self.max_toe_in_deg,self.max_tilt_deg)
        optional=(self.amp_power_w,self.max_spl_lf_db,self.cutout_width_m)
        if len(self.acoustic_center_offset_m)!=2 or not all(np.isfinite(value) for value in numeric+self.acoustic_center_offset_m) or not all(value is None or np.isfinite(value) for value in optional):
            raise ValueError("numeric speaker specifications must be finite")
        if not self.role_types or any(r not in ("front", "surround", "bass") for r in self.role_types): raise ValueError("role_types must contain front, surround, or bass")
        if not (0 < self.freq_low_hz < self.freq_high_hz): raise ValueError("frequency range requires 0 < freq_low_hz < freq_high_hz")
        if self.crossover_hz and self.crossover_hz>self.freq_high_hz: raise ValueError("crossover_hz cannot exceed freq_high_hz")
        if self.crossover_hz < 0 or self.crossover_slope_db_oct <= 0: raise ValueError("crossover frequency must be nonnegative and slope positive")
        if not 70 <= self.sensitivity_db <= 110: raise ValueError("sensitivity_db must be between 70 and 110 dB")
        if self.sensitivity_basis not in ("1W_1m", "2.83V_1m"): raise ValueError("sensitivity_basis must be 1W_1m or 2.83V_1m")
        if self.rated_power_w <= 0 or (self.amp_power_w is not None and self.amp_power_w <= 0): raise ValueError("rated and amplifier power must be positive")
        if self.max_spl_db<=0 or (self.max_spl_lf_db is not None and self.max_spl_lf_db<=0): raise ValueError("maximum SPL values must be positive")
        if self.nominal_impedance_ohm <= 0: raise ValueError("nominal_impedance_ohm must be positive")
        if not 20 <= self.coverage_h_deg <= 360 or not 20 <= self.coverage_v_deg <= 180: raise ValueError("coverage must be 20-360 horizontal and 20-180 vertical degrees")
        if len(self.directivity_band_weights)!=4 or any(not np.isfinite(x) or x<0 for x in self.directivity_band_weights) or sum(self.directivity_band_weights)<=0: raise ValueError("directivity_band_weights must have four finite nonnegative values with a positive sum")
        if self.directivity_model not in ("cos_n", "omni", "cardioid", "dipole", "bipole"): raise ValueError("unsupported directivity_model")
        if self.mount_type not in ("on_wall", "in_wall", "flush", "on_ceiling", "in_ceiling", "stand", "floor_standing"): raise ValueError("unsupported mount_type")
        if min(self.width_m, self.height_m, self.depth_m, self.floor_source_height_m, self.floor_wall_clearance_m,self.min_corner_clearance_m, self.min_spacing_to_other_speakers_m) < 0 or (self.cutout_width_m is not None and self.cutout_width_m<=0): raise ValueError("dimensions and clearances must be nonnegative; cutout width must be positive")
        if self.min_listening_distance_m < 0 or self.max_listening_distance_m <= self.min_listening_distance_m: raise ValueError("listening distance range must be nonnegative and increasing")
        if lo < 0 or hi <= lo: raise ValueError("mount_height_range_m must be increasing and nonnegative")
        if self.f3_hz < 0 or self.highpass_slope_db_oct <= 0: raise ValueError("f3 must be nonnegative and highpass slope positive")
        if self.f3_hz>=self.freq_high_hz and self.f3_hz>0: raise ValueError("f3_hz must be below freq_high_hz")
        if self.enclosure not in ("sealed", "ported"): raise ValueError("enclosure must be sealed or ported")
        if not 0 <= self.max_toe_in_deg <= 90: raise ValueError("max_toe_in_deg must be between 0 and 90")
        if not 0 <= self.max_tilt_deg <= 90: raise ValueError("max_tilt_deg must be between 0 and 90")
        if self.coverage_h_vs_freq and (any(not np.isfinite(f+a) or f <= 0 or not 20 <= a <= 360 for f, a in self.coverage_h_vs_freq) or any(b[0] <= a[0] for a, b in zip(self.coverage_h_vs_freq, self.coverage_h_vs_freq[1:]))):
            raise ValueError("coverage_h_vs_freq must have increasing positive Hz and 20-360 degree coverage")
        if self.polar_table is not None: self._polar_rows()  # validate eagerly
        if self.vertical_polar_table is not None: self._polar_rows(self.vertical_polar_table)
        if self.on_axis_response is not None: self._response_points()

    @property
    def directivity_exponent(self) -> float:
        """Cosine-power exponent giving -6 dB amplitude at half coverage."""
        half=cos(self.coverage_h_deg*pi/360.)
        return log(.5)/log(half) if 0 < half < 1 else 0.

    @property
    def effective_power_w(self) -> float:
        return min(self.rated_power_w, self.amp_power_w) if self.amp_power_w is not None else self.rated_power_w

    @property
    def sensitivity_1w_1m_db(self) -> float:
        """Normalize sensitivity to 1 W at 1 m (2.83 V into 4 ohm is 2 W)."""
        if self.sensitivity_basis == "1W_1m": return self.sensitivity_db
        power_283v = 8.0 / self.nominal_impedance_ohm
        return self.sensitivity_db - 10.0*log10(power_283v)

    @property
    def corner_clearance_m(self) -> float:
        """Recommended center distance from wall endpoint including footprint."""
        return max(self.min_corner_clearance_m,self.width_m/2.)

    @property
    def usable_band_fraction(self) -> float:
        """Fraction of 30-200 Hz target band within 3 dB of on-axis level."""
        freqs=np.linspace(30.,200.,681)
        return float(np.mean(self.response_db(freqs)>=-3.))

    @property
    def polar_source(self) -> str:
        return str(self.polar_table) if isinstance(self.polar_table, str) else ("inline polar table" if self.polar_table else "analytic {}".format(self.directivity_model))

    def _response_points(self) -> list[tuple[float, float]]:
        if isinstance(self.on_axis_response, str):
            path=Path(self.on_axis_response).expanduser()
            with path.open(newline="", encoding="utf-8") as handle:
                points=[(float(row["hz"]), float(row["db"])) for row in DictReader(handle)]
        else:
            points=[(float(f), float(db)) for f, db in self.on_axis_response]
        if not points or any(not np.isfinite(f+db) or f<=0 for f,db in points): raise ValueError("on_axis_response needs finite dB points at positive frequencies")
        if any(b[0]<=a[0] for a,b in zip(points,points[1:])): raise ValueError("on_axis_response frequencies must be strictly increasing")
        return points

    def response_db(self, frequency_hz: Any) -> np.ndarray:
        """Return on-axis response level relative to passband (dB)."""
        f=np.maximum(np.asarray(frequency_hz,dtype=float),1e-6)
        if self.on_axis_response is not None:
            points=self._response_points(); response=np.interp(np.log10(f),np.log10([x[0] for x in points]),[x[1] for x in points])
        else:
            f3=self.f3_hz or self.freq_low_hz
            slope=float(self.highpass_slope_db_oct)
            response=np.where(f<=f3,-3.-slope*np.maximum(0.,np.log2(f3/f)),0.)
        if self.crossover_hz>0:
            crossover_loss=np.where(f>=self.crossover_hz,-3.-self.crossover_slope_db_oct*np.maximum(0.,np.log2(f/self.crossover_hz)),0.)
            response=response+crossover_loss
        return response

    def _polar_rows(self, source=None) -> Tuple[dict, ...]:
        source=self.polar_table if source is None else source
        if isinstance(source,str):
            with Path(source).expanduser().open(newline="",encoding="utf-8") as handle: rows=tuple(dict(row) for row in DictReader(handle))
        else: rows=tuple(dict(row) if isinstance(row,dict) else {"angle_deg":row[0],**row[1]} for row in source)
        if not rows: raise ValueError("polar_table must contain at least one row")
        angles=[float(r["angle_deg"]) for r in rows]
        if angles!=sorted(angles) or len(set(angles))!=len(angles) or any(a<0 or a>180 for a in angles): raise ValueError("polar table angles must be strictly increasing within 0-180 degrees")
        columns=[key for key in rows[0] if key!="angle_deg"]
        try: frequencies=sorted(float(key) for key in columns)
        except ValueError as exc: raise ValueError("polar table band columns must be numeric frequencies in Hz") from exc
        if not frequencies or any(f<=0 for f in frequencies): raise ValueError("polar table needs positive frequency columns")
        for row in rows:
            if set(row)!=(set(rows[0])): raise ValueError("polar table rows must share the same frequency columns")
            if any(not np.isfinite(float(row[key])) for key in columns): raise ValueError("polar table gains must be finite dB values")
        return rows

    def coverage_at_hz(self, frequency_hz: float) -> float:
        if not self.coverage_h_vs_freq: return self.coverage_h_deg
        pairs=self.coverage_h_vs_freq
        return float(np.interp(np.log10(max(frequency_hz,1e-6)),np.log10([p[0] for p in pairs]),[p[1] for p in pairs]))

    def gain_db(self, off_axis_deg: float, back_floor_db: float = -30., frequency_hz: Optional[float] = None) -> float:
        """Horizontal normalized response; polar tables interpolate angle and log-frequency."""
        theta=abs(float(off_axis_deg)); theta=min(theta,360.-theta)
        if self.polar_table is not None:
            rows=self._polar_rows(); angle_grid=np.array([float(r["angle_deg"]) for r in rows]); frequencies=sorted(float(k) for k in rows[0] if k!="angle_deg")
            target_f=frequency_hz or 1000.; angle_values=[]
            for row in rows:
                angle_values.append(float(np.interp(np.log10(target_f),np.log10(frequencies),[float(row[str(f)] if str(f) in row else row[str(int(f))]) for f in frequencies])))
            return float(np.interp(theta,angle_grid,angle_values))
        if self.directivity_model=="omni": return 0.
        if self.directivity_model in ("dipole", "bipole"):
            gain=abs(cos(theta*pi/180.))
        elif self.directivity_model=="cardioid":
            gain=.5*(1+cos(min(theta,180.)*pi/180.))
        elif self.directivity_model=="cos_n":
            coverage=self.coverage_at_hz(frequency_hz or 1000.)
            half=cos(coverage*pi/360.); exponent=log(.5)/log(half) if 0<half<1 else 0.
            gain=cos(theta*pi/180.)**exponent if theta<90. else 0.
        else: raise ValueError("unsupported directivity model {!r}".format(self.directivity_model))
        return 20.*log10(max(float(gain),10.**(back_floor_db/20.)))

    def gain_linear(self, off_axis_deg: float, back_floor_db: float = -30.) -> float:
        return 10.**(self.gain_db(off_axis_deg,back_floor_db)/20.)

    def gain_vertical_db(self, off_axis_deg: float, back_floor_db: float = -30.) -> float:
        """Approximate vertical polar response with the configured coverage angle."""
        if self.vertical_polar_table is not None:
            theta=abs(float(off_axis_deg)); rows=self._polar_rows(self.vertical_polar_table)
            angles=np.asarray([float(row["angle_deg"]) for row in rows]); frequencies=sorted(float(key) for key in rows[0] if key!="angle_deg")
            band_values=[]
            for row in rows:
                values=[float(row.get(str(f),row.get(str(int(f))))) for f in frequencies]
                band_values.append(float(np.interp(np.log10(1000.),np.log10(frequencies),values)))
            return float(np.interp(theta,angles,band_values))
        if self.directivity_model=="omni": return 0.
        theta=abs(float(off_axis_deg))
        half=cos(self.coverage_v_deg*pi/360.)
        exponent=log(.5)/log(half) if 0<half<1 else 0.
        gain=cos(theta*pi/180.)**exponent if theta<90. else 0.
        return 20.*log10(max(float(gain),10.**(back_floor_db/20.)))

    def directivity_polarity(self, off_axis_deg: float) -> int:
        """Dipole rear lobe is opposite polarity; bipole rear lobe is in phase."""
        return -1 if self.directivity_model=="dipole" and abs(float(off_axis_deg))>90. else 1


# Built-ins are synthetic placeholders, never claims about commercial hardware.
_RAW_MODELS = {
 "generic_compact_wall": dict(display_name="Generic compact wall speaker (PLACEHOLDER)",role_types=("front","surround"),freq_low_hz=100,freq_high_hz=20000,crossover_hz=120,sensitivity_db=85,rated_power_w=50,max_spl_db=104,nominal_impedance_ohm=8,coverage_h_deg=110,coverage_v_deg=90,directivity_model="cos_n",mount_type="on_wall",width_m=.24,height_m=.16,depth_m=.12,min_corner_clearance_m=.30,wall_gain_db=3),
 "generic_center_onwall": dict(display_name="Generic wide-horizontal on-wall center (PLACEHOLDER)",role_types=("front",),freq_low_hz=80,freq_high_hz=20000,crossover_hz=80,sensitivity_db=87,rated_power_w=80,max_spl_db=108,nominal_impedance_ohm=8,coverage_h_deg=120,coverage_v_deg=40,directivity_model="cos_n",mount_type="on_wall",width_m=.52,height_m=.18,depth_m=.16,min_corner_clearance_m=.30,wall_gain_db=3,mount_height_range_m=(.3,2.2)),
 "generic_center_inwall": dict(display_name="Generic wide-horizontal in-wall center (PLACEHOLDER)",role_types=("front",),freq_low_hz=70,freq_high_hz=20000,crossover_hz=80,sensitivity_db=88,rated_power_w=100,max_spl_db=110,nominal_impedance_ohm=8,coverage_h_deg=120,coverage_v_deg=40,directivity_model="cos_n",mount_type="in_wall",width_m=.60,height_m=.25,depth_m=.10,min_corner_clearance_m=.30,wall_gain_db=6,max_toe_in_deg=10,mount_height_range_m=(.3,2.2)),
 "generic_in_ceiling": dict(display_name="Generic flush in-ceiling speaker (PLACEHOLDER)",role_types=("surround",),freq_low_hz=80,freq_high_hz=20000,crossover_hz=80,sensitivity_db=86,rated_power_w=60,max_spl_db=105,coverage_h_deg=100,coverage_v_deg=100,directivity_model="cos_n",mount_type="in_ceiling",width_m=.22,height_m=.22,depth_m=.10,min_corner_clearance_m=.30,mount_height_range_m=(2.0,4.0),max_toe_in_deg=0,max_tilt_deg=0),
 "generic_on_ceiling": dict(display_name="Generic on-ceiling speaker (PLACEHOLDER)",role_types=("surround",),freq_low_hz=100,freq_high_hz=20000,crossover_hz=100,sensitivity_db=85,rated_power_w=50,max_spl_db=103,coverage_h_deg=100,coverage_v_deg=80,directivity_model="cos_n",mount_type="on_ceiling",width_m=.22,height_m=.22,depth_m=.12,min_corner_clearance_m=.30,mount_height_range_m=(2.0,4.0),max_toe_in_deg=0,max_tilt_deg=45),
 "generic_bookshelf_onwall": dict(display_name="Generic bookshelf on-wall (PLACEHOLDER)",role_types=("front","surround"),freq_low_hz=80,freq_high_hz=20000,crossover_hz=80,sensitivity_db=87,rated_power_w=80,max_spl_db=108,nominal_impedance_ohm=8,coverage_h_deg=90,coverage_v_deg=60,directivity_model="cos_n",mount_type="on_wall",width_m=.30,height_m=.20,depth_m=.18,min_corner_clearance_m=.30,wall_gain_db=3),
 "generic_inwall_lcr": dict(display_name="Generic in-wall LCR (PLACEHOLDER)",role_types=("front",),freq_low_hz=70,freq_high_hz=20000,crossover_hz=80,sensitivity_db=88,rated_power_w=100,max_spl_db=110,nominal_impedance_ohm=8,coverage_h_deg=80,coverage_v_deg=60,directivity_model="cos_n",mount_type="in_wall",width_m=.46,height_m=.30,depth_m=.10,min_corner_clearance_m=.30,wall_gain_db=6,max_toe_in_deg=10),
 "generic_narrow_onwall": dict(display_name="Generic narrow-coverage on-wall (PLACEHOLDER)",role_types=("front","surround"),freq_low_hz=90,freq_high_hz=20000,crossover_hz=100,sensitivity_db=86,rated_power_w=70,max_spl_db=106,nominal_impedance_ohm=8,coverage_h_deg=60,coverage_v_deg=50,directivity_model="cos_n",mount_type="on_wall",width_m=.25,height_m=.18,depth_m=.14,min_corner_clearance_m=.30,wall_gain_db=3,max_toe_in_deg=45),
 "generic_surround_wide": dict(display_name="Generic wide surround (PLACEHOLDER)",role_types=("surround",),freq_low_hz=120,freq_high_hz=20000,crossover_hz=120,sensitivity_db=85,rated_power_w=60,max_spl_db=105,nominal_impedance_ohm=8,coverage_h_deg=120,coverage_v_deg=90,directivity_model="cos_n",mount_type="on_wall",width_m=.28,height_m=.18,depth_m=.14,min_corner_clearance_m=.30,wall_gain_db=3,max_toe_in_deg=60),
 "generic_inwall_sub": dict(display_name="Generic in-wall subwoofer (PLACEHOLDER)",role_types=("bass",),freq_low_hz=25,freq_high_hz=200,crossover_hz=120,sensitivity_db=85,rated_power_w=200,max_spl_db=112,max_spl_lf_db=108,nominal_impedance_ohm=4,coverage_h_deg=360,coverage_v_deg=180,directivity_model="omni",mount_type="in_wall",width_m=.45,height_m=.32,depth_m=.12,min_corner_clearance_m=.35,wall_gain_db=6,f3_hz=30,enclosure="sealed",max_toe_in_deg=0),
 "generic_onwall_sub": dict(display_name="Generic on-wall subwoofer (PLACEHOLDER)",role_types=("bass",),freq_low_hz=30,freq_high_hz=200,crossover_hz=100,sensitivity_db=88,rated_power_w=250,max_spl_db=116,max_spl_lf_db=112,nominal_impedance_ohm=4,coverage_h_deg=360,coverage_v_deg=180,directivity_model="omni",mount_type="on_wall",width_m=.50,height_m=.36,depth_m=.20,min_corner_clearance_m=.40,wall_gain_db=3,f3_hz=35,enclosure="ported",max_toe_in_deg=0),
 "generic_dipole_surround": dict(display_name="Generic dipole surround (PLACEHOLDER)",role_types=("surround",),freq_low_hz=100,freq_high_hz=20000,crossover_hz=120,sensitivity_db=84,rated_power_w=60,max_spl_db=104,nominal_impedance_ohm=8,coverage_h_deg=360,coverage_v_deg=180,directivity_model="dipole",mount_type="on_wall",width_m=.35,height_m=.25,depth_m=.16,min_corner_clearance_m=.35,wall_gain_db=3,max_toe_in_deg=90),
 "generic_onwall_sub_ported": dict(display_name="Generic ported on-wall subwoofer (PLACEHOLDER)",role_types=("bass",),freq_low_hz=25,freq_high_hz=200,crossover_hz=100,sensitivity_db=88,rated_power_w=250,max_spl_db=116,max_spl_lf_db=112,nominal_impedance_ohm=4,coverage_h_deg=360,coverage_v_deg=180,directivity_model="omni",mount_type="on_wall",width_m=.50,height_m=.36,depth_m=.20,min_corner_clearance_m=.40,wall_gain_db=3,f3_hz=35,enclosure="ported",max_toe_in_deg=0),
 "generic_floorstanding_tower": dict(display_name="Generic floor-standing tower (PLACEHOLDER)",role_types=("front","surround"),freq_low_hz=40,freq_high_hz=20000,crossover_hz=80,sensitivity_db=88,rated_power_w=120,max_spl_db=112,nominal_impedance_ohm=8,coverage_h_deg=90,coverage_v_deg=55,directivity_model="cos_n",mount_type="floor_standing",width_m=.24,height_m=1.0,depth_m=.32,floor_source_height_m=.82,floor_wall_clearance_m=.30,f3_hz=42,enclosure="ported",max_toe_in_deg=45),
 "generic_stand_bookshelf": dict(display_name="Generic stand-mounted bookshelf (PLACEHOLDER)",role_types=("front","surround"),freq_low_hz=65,freq_high_hz=20000,crossover_hz=80,sensitivity_db=87,rated_power_w=80,max_spl_db=108,nominal_impedance_ohm=8,coverage_h_deg=100,coverage_v_deg=60,directivity_model="cos_n",mount_type="stand",width_m=.22,height_m=.34,depth_m=.28,floor_source_height_m=.98,floor_wall_clearance_m=.30,f3_hz=65,enclosure="sealed",max_toe_in_deg=45),
 "generic_floor_sub": dict(display_name="Generic floor subwoofer (PLACEHOLDER)",role_types=("bass",),freq_low_hz=25,freq_high_hz=200,crossover_hz=100,sensitivity_db=88,rated_power_w=250,max_spl_db=116,max_spl_lf_db=112,nominal_impedance_ohm=4,coverage_h_deg=360,coverage_v_deg=180,directivity_model="omni",mount_type="floor_standing",width_m=.42,height_m=.48,depth_m=.42,floor_source_height_m=.35,acoustic_center_offset_m=(.11,0.),floor_wall_clearance_m=.12,f3_hz=30,enclosure="ported",max_toe_in_deg=0),
 "generic_ceiling_sub": dict(display_name="Generic ceiling-mount subwoofer (PLACEHOLDER)",role_types=("bass",),freq_low_hz=30,freq_high_hz=200,crossover_hz=100,sensitivity_db=86,rated_power_w=200,max_spl_db=112,max_spl_lf_db=108,nominal_impedance_ohm=4,coverage_h_deg=360,coverage_v_deg=180,directivity_model="omni",mount_type="on_ceiling",width_m=.42,height_m=.42,depth_m=.22,wall_gain_db=6,f3_hz=35,enclosure="sealed",max_toe_in_deg=0),
}

def _load_builtin_registry() -> Dict[str, SpeakerModel]:
    """Load the checked-in YAML registry, retaining a Python fallback."""
    registry_path=Path(__file__).with_name("speaker_models.yaml")
    try:
        import yaml
        data=yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        entries=data.get("models", data)
        return {key:SpeakerModel(**value) for key,value in entries.items()}
    except ImportError:
        return {key:SpeakerModel(model_id=key,**value) for key,value in _RAW_MODELS.items()}


DEFAULT_SPEAKER_MODELS: Dict[str, SpeakerModel] = _load_builtin_registry()
DEFAULT_MODEL_BY_ROLE = {"front":"generic_bookshelf_onwall","center":"generic_center_onwall","surround":"generic_surround_wide","bass":"generic_inwall_sub"}


def load_models_file(path: str, base: Optional[dict[str, SpeakerModel]] = None) -> tuple[dict[str, SpeakerModel], list[str]]:
    """Load user YAML models, allowing same-ID user entries to override defaults."""
    try: import yaml
    except ImportError as exc: raise RuntimeError("PyYAML is required for --models-file; install requirements.txt") from exc
    file=Path(path).expanduser()
    data=yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    entries=data.get("models", data)
    result=dict(DEFAULT_SPEAKER_MODELS if base is None else base); notices=[]
    for key,value in entries.items():
        item=asdict(result[key]) if key in result else {}
        item.update(dict(value)); item.setdefault("model_id",key)
        for path_key in ("polar_table", "vertical_polar_table", "on_axis_response"):
            spec=item.get(path_key)
            if isinstance(spec,str) and not Path(spec).expanduser().is_absolute(): item[path_key]=str((file.parent/spec).resolve())
        model=SpeakerModel(**item)
        if model.model_id in result: notices.append("NOTICE: user model '{}' overrides a built-in model".format(model.model_id))
        result[model.model_id]=model
    return result,notices


def validate_models(models: dict[str, SpeakerModel]) -> list[str]:
    errors=[]
    for model_id,model in models.items():
        try: model.__post_init__()
        except (TypeError,ValueError) as exc: errors.append("{}: {}".format(model_id,exc))
    return errors


def resolve_model(model_id: str) -> SpeakerModel:
    try: return DEFAULT_SPEAKER_MODELS[model_id]
    except KeyError as exc: raise ValueError("unknown speaker model '{}'; use --list-models".format(model_id)) from exc


def predicted_spl_db(model: SpeakerModel, distance_m: float) -> float:
    """Free-field estimate from 1 W/1 m sensitivity and electrical power.

    No wall gain is added: wall-mounted image geometry is represented by the
    room model, and adding this legacy correction would count that boundary twice.
    """
    distance=max(float(distance_m),.1)
    return model.sensitivity_1w_1m_db+10.*log10(max(model.effective_power_w,1e-9))-20.*log10(distance)
