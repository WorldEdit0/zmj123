from __future__ import annotations

import os
import random
import re
import time
from typing import Any

import numpy as np

from video_io import encode_jpeg_data_url, sample_frame_set


_RATING_RE = re.compile(r"(?<!\d)([0-5](?:\.\d+)?)(?!\d)")


def parse_rating(text: str | None, max_score: int = 5) -> float | None:
    if not text:
        return None
    m = _RATING_RE.search(text)
    if not m:
        return None
    value = max(0.0, min(float(max_score), float(m.group(1))))
    return value / max(float(max_score), 1e-6)


class ArkVlmJudge:
    """Minimal Ark-compatible VLM judge for EE_v3 and CSEP_v3.

    Required environment variable:
        ARK_API_KEY

    Optional environment variables:
        VLM_MODEL_ID              default: doubao-seed-2-0-lite-260215
        VLM_API_BASE_URL          default: https://ark.cn-beijing.volces.com/api/v3
        VLM_IMAGE_MAX_SIDE        default: 384
        VLM_JPEG_QUALITY         default: 80
        VLM_FRAME_SET_IMAGES      default: 2
        VLM_DETAIL                default: high
        VLM_TEMPERATURE           default: 0
        VLM_MAX_RETRIES           default: 8
        VLM_RETRY_SLEEP           default: 4
        VLM_MIN_CALL_INTERVAL_SEC default: 0
    """

    def __init__(self) -> None:
        from volcenginesdkarkruntime import Ark

        api_key = os.environ.get("ARK_API_KEY")
        if not api_key:
            raise RuntimeError("ARK_API_KEY is not set.")
        self.model_id = os.environ.get("VLM_MODEL_ID", "doubao-seed-2-0-lite-260215")
        self.max_side = int(os.environ.get("VLM_IMAGE_MAX_SIDE", "384"))
        self.jpeg_quality = int(os.environ.get("VLM_JPEG_QUALITY", "80"))
        self.frame_set_images = int(os.environ.get("VLM_FRAME_SET_IMAGES", "2"))
        self.detail = os.environ.get("VLM_DETAIL", "high")
        self.temperature = float(os.environ.get("VLM_TEMPERATURE", "0"))
        self.max_retries = int(os.environ.get("VLM_MAX_RETRIES", "8"))
        self.retry_sleep = float(os.environ.get("VLM_RETRY_SLEEP", "4"))
        self.min_call_interval = float(os.environ.get("VLM_MIN_CALL_INTERVAL_SEC", "0"))
        self._last_call_ts = 0.0
        self.client = Ark(
            base_url=os.environ.get("VLM_API_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
            api_key=api_key,
        )

    def _image_item(self, frame: np.ndarray) -> dict[str, Any]:
        return {
            "type": "image_url",
            "image_url": {
                "url": encode_jpeg_data_url(
                    frame,
                    max_side=self.max_side,
                    quality=self.jpeg_quality,
                ),
                "detail": self.detail,
            },
        }

    def _call(self, content: list[dict[str, Any]]) -> str:
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            if self.min_call_interval > 0:
                now = time.time()
                wait = self._last_call_ts + self.min_call_interval - now
                if wait > 0:
                    time.sleep(wait)
                self._last_call_ts = time.time()
            try:
                resp = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=[{"role": "user", "content": content}],
                    temperature=self.temperature,
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:  # pragma: no cover - network/API dependent
                last_err = exc
                msg = str(exc).lower()
                is_rate_limit = (
                    "429" in msg
                    or "tpm" in msg
                    or "rate" in msg
                    or "toomanyrequest" in msg
                )
                if is_rate_limit:
                    sleep_s = 30 + 15 * attempt + random.random() * 5
                else:
                    sleep_s = self.retry_sleep * (2 ** attempt) + random.random()
                time.sleep(sleep_s)
        raise RuntimeError(f"VLM API failed after {self.max_retries} retries: {last_err}")

    def rate_image_pair(self, frame_original: np.ndarray, frame_edited: np.ndarray, prompt: str) -> dict:
        content: list[dict[str, Any]] = [
            {"type": "text", "text": "ORIGINAL image:"},
            self._image_item(frame_original),
            {"type": "text", "text": "EDITED image:"},
            self._image_item(frame_edited),
            {"type": "text", "text": prompt},
        ]
        raw_text = self._call(content)
        return {"score": parse_rating(raw_text), "raw_response": raw_text}

    def rate_pair(self, frames_a: np.ndarray, frames_b: np.ndarray, prompt: str) -> dict:
        sampled_a = sample_frame_set(frames_a, self.frame_set_images)
        sampled_b = sample_frame_set(frames_b, self.frame_set_images)
        if not sampled_a or not sampled_b:
            return {"score": None, "raw_response": "missing frame set"}

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content.append({"type": "text", "text": "[FRAME-SET A]"})
        for frame in sampled_a:
            content.append(self._image_item(frame))
        content.append({"type": "text", "text": "[FRAME-SET B]"})
        for frame in sampled_b:
            content.append(self._image_item(frame))

        raw_text = self._call(content)
        return {
            "score": parse_rating(raw_text),
            "raw_response": raw_text,
            "n_images_a": len(sampled_a),
            "n_images_b": len(sampled_b),
        }
