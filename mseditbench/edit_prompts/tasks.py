"""T1-T8 task templates and per-video prompt instantiation.

Each task is a small dataclass with:
- a textual instruction template (Jinja-style {placeholders})
- a target_phrase template (used for CLIP-T mask conditioning)
- a sampler that, given a source-video record, produces concrete prompts

Run from CLI:
    python -m mseditbench.edit_prompts.generate \
        --source_json seedance_api_example/source_prompts_multishot_v1.json \
        --shots_dir runs/pilot_v2/shots \
        --output_json runs/edit_prompts/T1.json \
        --task T1 \
        --max_per_video 3
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TaskDef:
    task_id: str
    description: str
    instruction_templates: list[str]
    target_phrase_template: str
    requires: list[str]


# T1 — replacement: dynamic entities and static objects
T1 = TaskDef(
    task_id="T1",
    description="Cross-Shot Replacement (dynamic entities + static objects)",
    instruction_templates=[
        "Replace {character_desc} with {target_desc} in every shot they appear.",
        "Change {character_desc} into {target_desc}, keeping all actions identical.",
        "Swap {character_desc} for {target_desc}; preserve clothing position and posture.",
        "Replace the {old_object} with {new_object} wherever it appears.",
    ],
    target_phrase_template="{target_desc}",
    requires=["characters", "key_objects"],
)

# T2 — same-object attribute change: color / material / pattern / texture / hair
T2 = TaskDef(
    task_id="T2",
    description="Cross-Shot Attribute Edit (same-object color/material/pattern/texture/hair)",
    instruction_templates=[
        "Change {character_desc}'s {attribute_kind} to {new_value} in every shot.",
        "Change {old_value} on {character_desc} to {new_value} throughout.",
        "Recolor {character_desc}'s {attribute_kind} to {new_value} across all shots.",
    ],
    target_phrase_template="a person with {new_value}",
    requires=["characters"],
)

# T3 — global style only
T3 = TaskDef(
    task_id="T3",
    description="Global Style Re-rendering",
    instruction_templates=[
        "Re-render the entire video in {style} style.",
        "Restyle every shot as {style}, keeping characters and actions intact.",
        "Apply a {style} look to every shot of the video.",
    ],
    target_phrase_template="{style} look",
    requires=[],
)

# T4 — object/entity add / delete only
T4 = TaskDef(
    task_id="T4",
    description="Cross-Shot Static/Dynamic Add/Delete",
    instruction_templates=[
        "Add {new_object} next to {anchor} in every shot where {anchor} is visible.",
        "Delete {old_object} from every shot.",
    ],
    target_phrase_template="{new_object}",
    requires=["characters", "key_objects"],
)

# T5 — shot reorder
T5 = TaskDef(
    task_id="T5",
    description="Shot Reorder",
    instruction_templates=[
        "Reorder the video to shot order {new_order}.",
        "Change the shot sequence to {new_order}, preserving each shot's content.",
        "Make the edited video play in this shot order: {new_order}.",
    ],
    target_phrase_template="shots reordered to {new_order}",
    requires=[],
)

# T6 — cinematic re-shoot (framing / camera move)
T6 = TaskDef(
    task_id="T6",
    description="Cinematic Re-shoot (framing / camera move)",
    instruction_templates=[
        "Re-shoot shot {target_shot_id} as a {target_framing} instead.",
        "Apply a slow {camera_move} to shot {target_shot_id}.",
        "Convert shot {target_shot_id} into a {target_framing} with {camera_move}.",
    ],
    target_phrase_template="{target_framing} shot",
    requires=[],
)

# T7 — global lighting only
T7 = TaskDef(
    task_id="T7",
    description="Global Lighting Re-rendering",
    instruction_templates=[
        "Re-light the entire video with {lighting}, keeping characters and actions intact.",
        "Apply {lighting} across every shot of the video.",
    ],
    target_phrase_template="{lighting} look",
    requires=[],
)

# T8 — global background replacement with foreground preservation
T8 = TaskDef(
    task_id="T8",
    description="Global Background Replacement with Foreground Preservation",
    instruction_templates=[
        "Replace the {old_background} with {new_background}, preserving {preserve_foreground} and the original actions.",
        "Move the scene into {new_background} while keeping {preserve_foreground} unchanged.",
    ],
    target_phrase_template="{new_background} background",
    requires=["characters", "key_objects"],
)

ALL_TASKS = {t.task_id: t for t in [T1, T2, T3, T4, T5, T6, T7, T8]}
