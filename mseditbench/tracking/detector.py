"""Open-vocabulary detection in a single frame.

We provide two backends:
    "groundingdino"  — heavy: requires `groundingdino-py` + transformers
    "mock"           — returns a centered random box per phrase, deterministic by hash

Use the mock backend for unit tests and dry-runs. Switch to `groundingdino`
when you have weights downloaded (model `groundingdino_swint_ogc.pth` from the
official repo).
"""

from __future__ import annotations
import abc
import hashlib
import numpy as np


class DetectorBackend(abc.ABC):
    @abc.abstractmethod
    def detect(self, frame: np.ndarray, phrases: list[str],
               box_threshold: float = 0.30, text_threshold: float = 0.25) -> list[dict]:
        """Returns list of {phrase, bbox_xyxy, score}."""


class MockDetector(DetectorBackend):
    def detect(self, frame, phrases, box_threshold=0.30, text_threshold=0.25):
        H, W = frame.shape[:2]
        out = []
        for ph in phrases:
            seed = int.from_bytes(hashlib.md5((ph + str(H) + str(W)).encode()).digest()[:4], "big")
            rng = np.random.default_rng(seed)
            cx = rng.integers(W // 4, 3 * W // 4)
            cy = rng.integers(H // 4, 3 * H // 4)
            w = rng.integers(W // 5, W // 2)
            h = rng.integers(H // 5, H // 2)
            x0, y0 = max(0, cx - w // 2), max(0, cy - h // 2)
            x1, y1 = min(W, cx + w // 2), min(H, cy + h // 2)
            out.append({
                "phrase": ph,
                "bbox_xyxy": (int(x0), int(y0), int(x1), int(y1)),
                "score": 0.5 + 0.4 * rng.random(),
            })
        return out


def _make_groundingdino(weights: str = "groundingdino_swint_ogc.pth", config: str = "GroundingDINO_SwinT_OGC.py"):
    from groundingdino.util.inference import load_model, predict, load_image     # noqa
    import torch                                                                  # noqa

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_model(config, weights).to(device)

    class _GD(DetectorBackend):
        def detect(self, frame, phrases, box_threshold=0.30, text_threshold=0.25):
            from torchvision.transforms import functional as F
            H, W = frame.shape[:2]
            tens = F.to_tensor(frame).to(device)
            caption = ". ".join(phrases) + "."
            boxes, scores, labels = predict(
                model=model, image=tens, caption=caption,
                box_threshold=box_threshold, text_threshold=text_threshold,
            )
            out = []
            for b, sc, lab in zip(boxes.cpu().numpy(), scores.cpu().numpy(), labels):
                cx, cy, bw, bh = b
                x0 = int((cx - bw / 2) * W); y0 = int((cy - bh / 2) * H)
                x1 = int((cx + bw / 2) * W); y1 = int((cy + bh / 2) * H)
                out.append({"phrase": str(lab), "bbox_xyxy": (x0, y0, x1, y1), "score": float(sc)})
            return out

    return _GD()


def get_detector(kind: str = "mock", **kwargs):
    if kind == "mock": return MockDetector()
    if kind == "groundingdino": return _make_groundingdino(**kwargs)
    raise ValueError(kind)
