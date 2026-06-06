"""SAM-2 mask propagation within a shot.

Given an initial bbox on a reference frame, propagate a binary segmentation
mask through every frame of the shot. Two backends:
    "sam2" — official SAM-2-Video predictor (needs `sam2` package + ckpt)
    "mock" — returns a centered ellipse mask matching bbox size

The output API:
    propagate_shot(video_path, frame_start, frame_end, anchor_frame,
                   anchor_bbox_xyxy) -> {frame_idx: binary_mask_HxW}

Masks are uint8 {0,1} of the original frame size.
"""

from __future__ import annotations
import abc
import numpy as np
import cv2


class TrackerBackend(abc.ABC):
    @abc.abstractmethod
    def propagate_shot(self, video_path: str, frame_start: int, frame_end: int,
                       anchor_frame: int, anchor_bbox_xyxy: tuple[int, int, int, int]) -> dict[int, np.ndarray]:
        ...


class MockTracker(TrackerBackend):
    """Generates a softly-shifted ellipse around the anchor bbox for each frame."""
    def propagate_shot(self, video_path, frame_start, frame_end, anchor_frame, anchor_bbox_xyxy):
        cap = cv2.VideoCapture(video_path)
        H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        cap.release()
        x0, y0, x1, y1 = anchor_bbox_xyxy
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        a, b = max(1, (x1 - x0) // 2), max(1, (y1 - y0) // 2)

        out = {}
        for fi in range(frame_start, frame_end + 1):
            mask = np.zeros((H, W), dtype=np.uint8)
            shift = int(2 * np.sin(0.3 * (fi - anchor_frame)))
            cv2.ellipse(mask, (cx + shift, cy), (a, b), 0, 0, 360, color=1, thickness=-1)
            out[fi] = mask
        return out


def _make_sam2(model_cfg: str = "sam2_hiera_l.yaml", ckpt: str = "sam2_hiera_large.pt"):
    from sam2.build_sam import build_sam2_video_predictor                       # noqa
    import torch                                                                 # noqa

    device = "cuda" if torch.cuda.is_available() else "cpu"
    predictor = build_sam2_video_predictor(model_cfg, ckpt, device=device)

    class _SAM2(TrackerBackend):
        def propagate_shot(self, video_path, frame_start, frame_end, anchor_frame, anchor_bbox_xyxy):
            state = predictor.init_state(video_path)
            x0, y0, x1, y1 = anchor_bbox_xyxy
            predictor.add_new_points_or_box(
                inference_state=state,
                frame_idx=anchor_frame - frame_start,  # local index within shot
                obj_id=1,
                box=np.array([x0, y0, x1, y1], dtype=np.float32),
            )
            out = {}
            for f_local, obj_ids, mask_logits in predictor.propagate_in_video(state):
                fi = frame_start + f_local
                if fi < frame_start or fi > frame_end:
                    continue
                mask = (mask_logits[0] > 0.0).cpu().numpy().astype(np.uint8)
                out[fi] = mask
            return out

    return _SAM2()


def get_tracker(kind: str = "mock", **kwargs):
    if kind == "mock": return MockTracker()
    if kind == "sam2": return _make_sam2(**kwargs)
    raise ValueError(kind)
