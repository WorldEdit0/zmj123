"""Canonical schemas for MSEdit-Bench.

The whole pipeline communicates through a small set of dict shapes. Frame index
is the canonical time unit; `t_start`/`t_end` (seconds) are derived from
`frame_start`/`frame_end` and `fps`. Read this file before adding new fields.

Shot annotation        — preprocess/shot_detect.py output
EntityTube             — tracking/ output (one per (video, shot, entity))
CharacterDB            — identity/ output (cross-shot identity table)
EditPrompt             — edit_prompts/ output (one per (video, task) sample)
EvalResult             — metrics/ output (one per (video, edit, baseline) tuple)
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


# -- shot annotation ---------------------------------------------------------

@dataclass
class Shot:
    shot_id: int
    frame_start: int
    frame_end: int
    duration_frames: int = 0
    t_start: float = 0.0
    t_end: float = 0.0
    duration_sec: float = 0.0


@dataclass
class ShotAnnotation:
    """Top-level dict produced by preprocess/shot_detect.py."""
    video_id: str
    video_path: str
    fps: float
    total_frames: int
    duration_sec: float
    width: int
    height: int
    expected_shots: Optional[int]
    consensus_shots: list[Shot]
    consensus_n_shots: int


# -- entity tubes ------------------------------------------------------------

@dataclass
class EntityMaskFrame:
    """One frame within an entity tube. RLE-encoded mask saved separately."""
    frame: int
    bbox_xyxy: tuple[int, int, int, int]
    mask_rle_path: Optional[str]
    score: float
    visible: bool = True


@dataclass
class EntityTube:
    """One entity tracked through one shot."""
    video_id: str
    shot_id: int
    entity_id: str
    label: str
    is_face: bool
    frames: list[EntityMaskFrame]
    ref_frame_idx: int
    embedding_path: Optional[str] = None


# -- character identity ------------------------------------------------------

@dataclass
class CharacterRecord:
    character_id: str
    canonical_label: str
    appears_in_shots: list[int]
    n_face_crops: int
    centroid_embed_path: str
    sample_face_crops: list[str]
    src_json_id: Optional[str] = None


@dataclass
class CharacterDB:
    video_id: str
    fps: float
    characters: list[CharacterRecord]


# -- edit prompts ------------------------------------------------------------

@dataclass
class EditSpec:
    task_id: str
    instruction: str
    target_phrase: str
    applicable_shots: list[int]
    target_entity: Optional[str] = None
    target_reference: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class EditPromptSample:
    sample_id: str
    video_id: str
    source_video: str
    shots: list[Shot]
    entities: list[dict]
    characters: list[dict]
    edit: EditSpec


# -- evaluation --------------------------------------------------------------

@dataclass
class PerShotEval:
    shot_id: int
    is_applicable: bool
    psq: Optional[float]
    ee_continuous: Optional[float]
    ee_indicator: Optional[int]
    nep: Optional[float]
    off_target_delta: Optional[float]


@dataclass
class EvalResult:
    sample_id: str
    baseline: str
    snapshot: str
    edited_video_path: str

    psq: float
    cxs_id: Optional[float]
    cxs_style: Optional[float]
    tq: Optional[float]
    ncs: Optional[float]
    ee: Optional[float]
    nep: Optional[float]
    csep: Optional[float]
    csep_coverage: Optional[float]
    csep_consistency: Optional[float]
    ses: Optional[float]

    per_shot: list[PerShotEval]
    extra: dict = field(default_factory=dict)


# -- helpers -----------------------------------------------------------------

def to_dict(x):
    return asdict(x) if hasattr(x, "__dataclass_fields__") else x
