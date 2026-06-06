"""Snapshot Protocol — pin every API call to a model identifier + date.

Required by RESEARCH_PLAN.md §5 because commercial APIs iterate quickly,
so a number reported in our paper must point back to a frozen snapshot.

A bench config is a dict like:

    {
      "snapshot_id": "msb_20260520_v1",
      "models": {
        "aleph":     {"model": "runwayml/aleph-2.0",       "captured_at": "2026-05-20"},
        "seedance":  {"model": "bytedance/seedance-1.0-pro@2026-04-15", "captured_at": "2026-05-20"},
        "luma":      {"model": "luma/modify-1.0",          "captured_at": "2026-05-20"}
      },
      "k_samples_no_seed": 3,
      "prompt_rewriting_disabled": true,
      "archive_uri": "s3://msedit-bench/archive/msb_20260520_v1/"
    }

Helpers below: load + validate.
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict


@dataclass
class ModelSnapshot:
    model: str
    captured_at: str


@dataclass
class BenchConfig:
    snapshot_id: str
    models: dict[str, ModelSnapshot]
    k_samples_no_seed: int = 3
    prompt_rewriting_disabled: bool = True
    archive_uri: str = ""

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "models": {k: asdict(v) for k, v in self.models.items()},
            "k_samples_no_seed": self.k_samples_no_seed,
            "prompt_rewriting_disabled": self.prompt_rewriting_disabled,
            "archive_uri": self.archive_uri,
        }


def load(path: str) -> BenchConfig:
    with open(path) as f:
        d = json.load(f)
    models = {k: ModelSnapshot(**v) for k, v in d.get("models", {}).items()}
    return BenchConfig(
        snapshot_id=d["snapshot_id"],
        models=models,
        k_samples_no_seed=d.get("k_samples_no_seed", 3),
        prompt_rewriting_disabled=d.get("prompt_rewriting_disabled", True),
        archive_uri=d.get("archive_uri", ""),
    )


def write_template(path: str, snapshot_id: str = "msb_pilot"):
    cfg = BenchConfig(
        snapshot_id=snapshot_id,
        models={
            "aleph":    ModelSnapshot(model="runwayml/aleph-2.0", captured_at="2026-05-20"),
            "seedance": ModelSnapshot(model="bytedance/seedance-1.0-pro", captured_at="2026-05-20"),
        },
    )
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(cfg.to_dict(), f, indent=2)


def validate(cfg: BenchConfig) -> list[str]:
    errors = []
    if not cfg.snapshot_id:
        errors.append("snapshot_id is required")
    if not cfg.models:
        errors.append("at least one model must be pinned")
    for name, m in cfg.models.items():
        if "@" not in m.model and not m.captured_at:
            errors.append(f"{name}: model has no @date and no captured_at — not reproducible")
    return errors
