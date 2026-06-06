"""Runway Aleph baseline.

Aleph is Runway's video-editing API ("instruction-driven video edit on existing
footage"). Cuts a real source video into edited frames according to a prompt.

This module exposes two implementations:
    AlephClient   — real HTTP client (requires RUNWAY_API_KEY env var)
    AlephMock     — local fake that copies the source to output_path; useful
                    for testing the eval orchestrator without burning budget.

Endpoint and field names below follow Runway's developer docs as of 2026-05;
re-verify before paid runs (see DEEP_DIVE.md §3 "TBD: Aleph max input duration
+ seed parameter").
"""

from __future__ import annotations
import os
import shutil
import time
from typing import Optional

from .base import EditorBaseline, EditCallResult


class AlephMock(EditorBaseline):
    """Pretends to call Aleph: just copies input to output and returns success."""

    name = "aleph_mock"
    snapshot_model = "runwayml/aleph-mock"

    def edit(self, source_video, instruction, output_path,
             seed=None, extra=None) -> EditCallResult:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        shutil.copy(source_video, output_path)
        return EditCallResult(
            edited_video_path=output_path,
            request={"source": source_video, "instruction": instruction, "seed": seed, "extra": extra},
            response={"id": "mock-job", "status": "succeeded"},
            succeeded=True,
        )


class AlephClient(EditorBaseline):
    """Real Runway Aleph client. Requires RUNWAY_API_KEY env var.

    Steps:
        1. Upload source video (or pass URL if already hosted)
        2. POST /v1/video_edits with model + instruction
        3. Poll /v1/video_edits/{id} until SUCCEEDED / FAILED
        4. Download result to `output_path`
    """

    name = "aleph"

    def __init__(
        self,
        snapshot_model: str = "runwayml/aleph-2.0",
        api_base: str = "https://api.runwayml.com",
        poll_interval_sec: float = 4.0,
        timeout_sec: float = 600.0,
        api_key_env: str = "RUNWAY_API_KEY",
    ):
        import requests                                                       # noqa
        self.requests = requests
        self.snapshot_model = snapshot_model
        self.api_base = api_base.rstrip("/")
        self.poll = poll_interval_sec
        self.timeout = timeout_sec
        self.api_key = os.environ.get(api_key_env)
        if not self.api_key:
            raise RuntimeError(f"{api_key_env} env var not set")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}",
                "X-Runway-Version": "2026-05-01"}

    def edit(self, source_video, instruction, output_path,
             seed=None, extra=None) -> EditCallResult:
        # 1. Upload source video.  Runway's actual endpoint may differ.
        with open(source_video, "rb") as f:
            up = self.requests.post(
                f"{self.api_base}/v1/uploads",
                headers=self._headers(),
                files={"file": (os.path.basename(source_video), f, "video/mp4")},
                timeout=120,
            )
        try:
            up_json = up.json()
        except Exception:
            up_json = {"raw": up.text}
        if up.status_code >= 300:
            return EditCallResult("", {"upload_status": up.status_code}, up_json, False,
                                  error_message=f"upload failed: {up.status_code}")
        source_uri = up_json.get("uri") or up_json.get("url")

        # 2. Create edit job.
        body = {
            "model": self.snapshot_model,
            "promptText": instruction,
            "videoUri": source_uri,
        }
        if seed is not None:
            body["seed"] = seed
        if extra:
            body.update(extra)
        body["promptRewritingDisabled"] = True   # snapshot protocol

        start = self.requests.post(
            f"{self.api_base}/v1/video_edits",
            headers=self._headers(),
            json=body,
            timeout=60,
        )
        try:
            sj = start.json()
        except Exception:
            sj = {"raw": start.text}
        if start.status_code >= 300:
            return EditCallResult("", body, sj, False,
                                  error_message=f"create failed: {start.status_code}")

        job_id = sj.get("id") or sj.get("uuid")
        if not job_id:
            return EditCallResult("", body, sj, False, "no job id returned")

        # 3. Poll.
        deadline = time.time() + self.timeout
        last = sj
        while time.time() < deadline:
            time.sleep(self.poll)
            r = self.requests.get(f"{self.api_base}/v1/video_edits/{job_id}",
                                  headers=self._headers(), timeout=30)
            try:
                last = r.json()
            except Exception:
                last = {"raw": r.text}
            status = (last.get("status") or "").upper()
            if status in ("SUCCEEDED", "COMPLETE", "DONE"):
                break
            if status in ("FAILED", "ERROR", "CANCELED"):
                return EditCallResult("", body, last, False,
                                      error_message=f"job {status}: {last.get('error')}")
        else:
            return EditCallResult("", body, last, False, "timeout polling job")

        # 4. Download result.
        out_url = last.get("output", {}).get("url") or last.get("videoUri")
        if not out_url:
            return EditCallResult("", body, last, False, "no output URL on success")
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with self.requests.get(out_url, stream=True, timeout=300) as dl:
            dl.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in dl.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        return EditCallResult(
            edited_video_path=output_path,
            request=body,
            response=last,
            succeeded=True,
        )
