"""Common interface for editor baselines.

Every editor baseline (Aleph, Luma Modify, Veo 3.1, ...) implements this
interface. The eval orchestrator iterates over baselines and EditPromptSamples
and saves the resulting edited videos to disk, recording which snapshot of
which API produced each output.

The interface is intentionally narrow: input = source video path + edit
instruction; output = local path to the edited video plus a request/response
log dict (for reproducibility archives).
"""

from __future__ import annotations
import abc
import dataclasses
from typing import Optional


@dataclasses.dataclass
class EditCallResult:
    edited_video_path: str
    request: dict
    response: dict
    succeeded: bool
    error_message: Optional[str] = None


class EditorBaseline(abc.ABC):
    """Each baseline must expose name + snapshot_model + edit()."""

    name: str
    snapshot_model: str  # frozen model identifier from snapshot.json

    @abc.abstractmethod
    def edit(
        self,
        source_video: str,
        instruction: str,
        output_path: str,
        seed: Optional[int] = None,
        extra: Optional[dict] = None,
    ) -> EditCallResult:
        ...
