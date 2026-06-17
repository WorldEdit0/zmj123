"""Backends used by metric implementations.

Each backend exposes a small functional interface. The default constructor
returns a mock backend that takes float arrays and behaves deterministically;
real backends (CLIP, DINOv2, VLM, etc.) wrap heavy models and are loaded
lazily so unit tests never pay the import cost.

Usage:
    from mseditbench.metrics import backends as B
    dino = B.get_dino()              # mock by default
    emb = dino.embed_frames(frames)

中文说明：
    这个文件不直接定义指标公式，而是把指标需要的重模型统一包装成
    小接口。run_eval.py 只关心 get_dino/get_vlm/get_psq/get_mask 返回的
    对象是否有约定方法，不关心具体模型怎么加载。

    当前真实后端角色：
      DINOv2      -> NEP/USP 中的视觉保持相似度
      Qwen3-VL    -> EE_v3/CSEP_v3 的 VLM 裁判
      pyiqa       -> PSQ 的 MUSIQ + LAION-Aes 质量评分
      SAM3        -> NEP 的目标区域 mask，最终比较 mask 外区域
      OmniShotCut -> TAC 的编辑后镜头边界检测
"""

from __future__ import annotations

import abc
import hashlib
import importlib
import os
from pathlib import Path
import re
import numpy as np


def _metric_ckpt_root() -> Path:
    # 中文注释：所有本地权重默认统一放在 mseditbench/ckpt 下；
    # 也可以用 MSEDITBENCH_CKPT_ROOT 覆盖，方便迁移到别的机器。
    return Path(
        os.environ.get(
            "MSEDITBENCH_CKPT_ROOT",
            str(Path(__file__).resolve().parents[1] / "ckpt"),
        )
    )


def _metric_ckpt_path(*parts: str) -> Path:
    # 中文注释：拼出某个后端的本地权重路径，例如 ckpt/sam3/sam3.pt。
    return _metric_ckpt_root().joinpath(*parts)


# -- abstract interfaces -----------------------------------------------------

class ClipBackend(abc.ABC):
    # 中文注释：CLIP 后端只用于“文本和图像/视频的相似度”；
    # 当前 headline 指标不再使用 CLIP，保留接口是为了旧版 EE/CSEP 消融。
    @abc.abstractmethod
    def score_video_text(self, frames: np.ndarray, text: str) -> float:
        """frames: [T,H,W,3] uint8.  Returns scalar similarity in [0,1]."""

    @abc.abstractmethod
    def score_image_text(self, frame: np.ndarray, text: str) -> float:
        """frame: [H,W,3] uint8."""

    def embed_video(self, frames: np.ndarray) -> np.ndarray:
        """Return L2-normalised mean image embedding over T frames (D,).
        Default: error — concrete backends should override for v2 metrics."""
        raise NotImplementedError("embed_video not implemented")

    def embed_text(self, text: str) -> np.ndarray:
        """Return L2-normalised CLIP text embedding (D,)."""
        raise NotImplementedError("embed_text not implemented")


class DinoBackend(abc.ABC):
    # 中文注释：DINO 后端输出视觉 embedding，用于 source/edit 保持性比较。
    @abc.abstractmethod
    def embed_frames(self, frames: np.ndarray) -> np.ndarray:
        """frames: [T,H,W,3] uint8.  Returns [T,D] L2-normalized."""

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """a, b: [D] vectors.  Returns cosine similarity in [-1,1]."""
        a = a / (np.linalg.norm(a) + 1e-8)
        b = b / (np.linalg.norm(b) + 1e-8)
        return float(np.dot(a, b))


class FaceBackend(abc.ABC):
    # 中文注释：Face 后端负责检测人脸并给出身份 embedding。
    @abc.abstractmethod
    def detect_and_embed(self, frame: np.ndarray) -> list[dict]:
        """Returns list of {bbox, embedding[512], score, landmarks}."""


class VlmBackend(abc.ABC):
    # 中文注释：VLM 后端是统一裁判接口：yes/no 给旧版 EE 用，
    # rate_image_pair 给 EE_v3 用，rate_pair 给 CSEP_v3 用。
    @abc.abstractmethod
    def yes_no(self, frames: np.ndarray, question: str) -> bool:
        """frames: [T,H,W,3] uint8.  Returns binary True/False."""

    def rate(self, frames: np.ndarray, prompt: str, max_score: int = 5) -> float | None:
        """Return continuous rating in [0, 1] (= score / max_score).

        Default impl raises NotImplementedError; concrete backends override.
        Returns None on parse failure.
        """
        raise NotImplementedError("rate not implemented")

    def rate_pair(
        self,
        frames_a: np.ndarray,
        frames_b: np.ndarray,
        prompt: str,
        max_score: int = 5,
    ) -> float | None:
        """Show two frame sets, return continuous rating [0, 1].
        Used for source-vs-edit comparison and cross-shot consistency."""
        raise NotImplementedError("rate_pair not implemented")

    def rate_image_pair(
        self,
        frame_a: np.ndarray,
        frame_b: np.ndarray,
        prompt: str,
        max_score: int = 5,
    ) -> float | None:
        """Show one source/edit image pair, return continuous rating [0, 1]."""
        return self.rate_pair(frame_a[None, ...], frame_b[None, ...], prompt, max_score=max_score)


# -- mock backends -----------------------------------------------------------

def _hash_to_unit(*items) -> float:
    h = hashlib.md5(repr(items).encode()).digest()
    return int.from_bytes(h[:4], "big") / 0xFFFFFFFF


def _hash_to_vec(*items, dim: int = 384) -> np.ndarray:
    seed = int.from_bytes(hashlib.md5(repr(items).encode()).digest()[:4], "big")
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(dim).astype(np.float32)
    v /= np.linalg.norm(v) + 1e-8
    return v


class MockClip(ClipBackend):
    """Hash-based deterministic CLIP.  Good for unit tests; no model semantics."""
    def score_video_text(self, frames, text):
        sig = (frames.shape, frames.mean(), text)
        return _hash_to_unit(sig)

    def score_image_text(self, frame, text):
        return _hash_to_unit((frame.shape, frame.mean(), text))


class MockDino(DinoBackend):
    def embed_frames(self, frames):
        T = len(frames)
        return np.stack([_hash_to_vec(("dino", i, frames[i].mean())) for i in range(T)])


class MockFace(FaceBackend):
    """Pretends every frame contains one face with a hash-derived embedding."""
    def detect_and_embed(self, frame):
        return [{
            "bbox": (0, 0, frame.shape[1], frame.shape[0]),
            "embedding": _hash_to_vec(("face", frame.shape, frame.mean()), dim=512),
            "score": 0.99,
            "landmarks": None,
        }]


class MockVlm(VlmBackend):
    """Hash-based deterministic yes/no.  Threshold 0.5."""
    def yes_no(self, frames, question):
        return _hash_to_unit((frames.shape, frames.mean(), question)) > 0.5

    def rate(self, frames, prompt, max_score=5):
        return float(_hash_to_unit((frames.shape, frames.mean(), prompt, "rate")))

    def rate_pair(self, frames_a, frames_b, prompt, max_score=5):
        return float(_hash_to_unit((frames_a.shape, frames_a.mean(),
                                    frames_b.shape, frames_b.mean(), prompt, "rate_pair")))

    def rate_image_pair(self, frame_a, frame_b, prompt, max_score=5):
        return float(_hash_to_unit((frame_a.shape, frame_a.mean(),
                                    frame_b.shape, frame_b.mean(), prompt, "rate_image_pair")))


# -- real-backend factories (lazy import) ------------------------------------

def _make_real_clip(name: str):
    """Load CLIP. Default 'openai' uses OpenAI's `clip` package which natively
    handles their .pt files; faster than open_clip-via-HF on networks where
    HF is throttled. Set OPENAI_CLIP_PATH to use a local .pt; otherwise
    `clip.load` will fetch from openaipublic.azureedge.net.

    SigLIP variants still go through open_clip.
    """
    import torch
    if name == "openai" or name == "ViT-B-32":
        try:
            import clip as _clip
        except ImportError as e:
            raise ImportError(
                "Install OpenAI CLIP: pip install ftfy regex && "
                "pip install git+https://github.com/openai/CLIP.git"
            ) from e
        import os
        local_path = os.environ.get(
            "OPENAI_CLIP_PATH",
            str(_metric_ckpt_path("clip", "ViT-B-32.pt")),
        )
        # 中文注释：优先使用本地 CLIP 权重；本地没有时才让 clip.load 自己下载。
        if not os.path.exists(local_path):
            local_path = "ViT-B/32"  # let clip.load download
        model, preproc = _clip.load(
            local_path,
            device="cuda" if torch.cuda.is_available() else "cpu",
            download_root=str(_metric_ckpt_path("clip")),
        )
        model.eval()
        device = next(model.parameters()).device

        class _OpenAICLIP(ClipBackend):
            def __init__(self):
                self._text_cache = {}  # text → np.ndarray (D,) on CPU

            @torch.no_grad()
            def _embed_image(self, img):
                from PIL import Image
                x = preproc(Image.fromarray(img)).unsqueeze(0).to(device)
                f = model.encode_image(x)
                return (f / f.norm(dim=-1, keepdim=True)).cpu().numpy()[0]

            @torch.no_grad()
            def _embed_text(self, text):
                if text in self._text_cache:
                    return self._text_cache[text]
                t = _clip.tokenize([text], truncate=True).to(device)
                f = model.encode_text(t)
                emb = (f / f.norm(dim=-1, keepdim=True)).cpu().numpy()[0]
                self._text_cache[text] = emb
                return emb

            def score_image_text(self, frame, text):
                return float((self._embed_image(frame) * self._embed_text(text)).sum())

            @torch.no_grad()
            def score_video_text(self, frames, text):
                # Batch ALL frames into one GPU forward
                # 中文注释：一个 shot 的多帧先分别编码，再平均成视频/shot embedding。
                from PIL import Image
                if len(frames) == 0:
                    return 0.0
                xs = torch.stack([preproc(Image.fromarray(f)) for f in frames]).to(device)
                fs = model.encode_image(xs)
                fs = fs / fs.norm(dim=-1, keepdim=True)
                v = fs.mean(dim=0)
                v = v / (v.norm() + 1e-8)
                # text via cache
                t = self._embed_text(text)  # numpy (D,)
                t_t = torch.from_numpy(t).to(device)
                return float((v * t_t).sum().item())

            # ---- v2 helpers: expose raw embeddings (L2-normalised) ----
            @torch.no_grad()
            def embed_video(self, frames):
                from PIL import Image
                if len(frames) == 0:
                    return np.zeros(512, dtype=np.float32)
                xs = torch.stack([preproc(Image.fromarray(f)) for f in frames]).to(device)
                fs = model.encode_image(xs)
                fs = fs / fs.norm(dim=-1, keepdim=True)
                v = fs.mean(dim=0)
                v = v / (v.norm() + 1e-8)
                return v.cpu().numpy().astype(np.float32)

            def embed_text(self, text):
                return self._embed_text(text)

        return _OpenAICLIP()

    # Fallback: open_clip for SigLIP / ViT-L variants
    import open_clip                                                            # noqa
    model, _, preproc = open_clip.create_model_and_transforms(name, pretrained="openai")
    tokenizer = open_clip.get_tokenizer(name)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()

    class _OpenClipB(ClipBackend):
        def __init__(self): self.model, self.preproc, self.tok, self.device = model, preproc, tokenizer, device

        @torch.no_grad()
        def _embed_image(self, img):
            from PIL import Image
            x = self.preproc(Image.fromarray(img)).unsqueeze(0).to(self.device)
            f = self.model.encode_image(x)
            return (f / f.norm(dim=-1, keepdim=True)).cpu().numpy()[0]

        @torch.no_grad()
        def _embed_text(self, text):
            tok = self.tok([text]).to(self.device)
            f = self.model.encode_text(tok)
            return (f / f.norm(dim=-1, keepdim=True)).cpu().numpy()[0]

        def score_image_text(self, frame, text):
            i = self._embed_image(frame)
            t = self._embed_text(text)
            return float((i * t).sum())

        def score_video_text(self, frames, text):
            t = self._embed_text(text)
            v = np.mean([self._embed_image(f) for f in frames], axis=0)
            v /= np.linalg.norm(v) + 1e-8
            return float((v * t).sum())

    return _OpenClipB()


def _make_real_dino(name: str = "dinov2_vits14"):
    """Load DINOv2 via timm (avoids torch.hub which hits github rate limits).
    Falls back to torch.hub if timm load fails. Set DINOV2_LOCAL_PATH to
    a local .pth file (downloaded from dl.fbaipublicfiles.com)."""
    import torch
    import os
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Map our short names → timm names + Meta CDN URLs
    # 中文注释：v2s/v2b 只是 run_eval 暴露的短名，这里映射到真实 DINOv2 模型。
    name_to_timm = {
        "dinov2_vits14": "vit_small_patch14_dinov2.lvd142m",
        "dinov2_vitb14": "vit_base_patch14_dinov2.lvd142m",
    }
    name_to_url = {
        "dinov2_vits14": "https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth",
        "dinov2_vitb14": "https://dl.fbaipublicfiles.com/dinov2/dinov2_vitb14/dinov2_vitb14_pretrain.pth",
    }
    local_path_default = {
        "dinov2_vits14": str(_metric_ckpt_path("dinov2", "dinov2_vits14.pth")),
        "dinov2_vitb14": str(_metric_ckpt_path("dinov2", "dinov2_vitb14.pth")),
    }

    try:
        import timm
        timm_name = name_to_timm.get(name, name)
        local_path = os.environ.get("DINOV2_LOCAL_PATH", local_path_default.get(name, ""))
        if not local_path or not os.path.exists(local_path):
            raise FileNotFoundError(f"DINOv2 weights not at {local_path}; download from {name_to_url.get(name)}")
        # 中文注释：优先用本地 .pth 加载，避免正式评测时访问外网。
        model = timm.create_model(timm_name, pretrained=False, num_classes=0)
        sd = torch.load(local_path, map_location="cpu", weights_only=False)
        model.load_state_dict(sd, strict=False)  # 'mask_token' is training-only
        model.to(device).eval()
        backend_name = f"timm/{timm_name}"
    except Exception:
        # Fallback to torch.hub
        torch.hub.set_dir(
            os.environ.get("MSEDITBENCH_TORCH_HUB_DIR", str(_metric_ckpt_root()))
        )
        model = torch.hub.load("facebookresearch/dinov2", name)
        model.to(device).eval()
        backend_name = f"torch_hub/{name}"

    class _RealDino(DinoBackend):
        @torch.no_grad()
        def embed_frames(self, frames):
            from torchvision import transforms as T
            # DINOv2 timm models expect 518×518 (matches lvd142m pretrain)
            input_size = 518 if "timm" in backend_name else 224
            tfm = T.Compose([T.ToPILImage(), T.Resize(input_size), T.CenterCrop(input_size),
                             T.ToTensor(),
                             T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])
            x = torch.stack([tfm(f) for f in frames]).to(device)
            f = model(x)
            return (f / f.norm(dim=-1, keepdim=True)).cpu().numpy()

    return _RealDino()


def _make_real_face():
    from insightface.app import FaceAnalysis                           # noqa
    root = os.environ.get(
        "INSIGHTFACE_ROOT",
        str(_metric_ckpt_path("insightface")),
    )
    # Prefer CUDA; fall back to CPU silently (onnxruntime-gpu may be missing).
    # 中文注释：Face backend 仅保留给历史身份相关模块；当前主评测不再调用。
    try:
        app = FaceAnalysis(name="buffalo_l",
                           root=root,
                           providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    except Exception:
        app = FaceAnalysis(name="buffalo_l", root=root)
    app.prepare(ctx_id=0, det_size=(640, 640))

    class _RealFace(FaceBackend):
        def detect_and_embed(self, frame):
            faces = app.get(frame)
            return [{
                "bbox": tuple(int(x) for x in f.bbox),
                "embedding": f.normed_embedding,
                "score": float(f.det_score),
                "landmarks": f.kps if hasattr(f, "kps") else None,
            } for f in faces]

    return _RealFace()


def _make_seed_vlm(
    model_id: str | None = None,
    api_key: str | None = None,
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
    n_frames: int = 2,           # ← was 4. Halves tokens/call to stay under TPM.
    max_side: int = 384,         # ← was 512. Smaller jpegs.
    jpeg_quality: int = 80,
    max_retries: int = 8,
    retry_sleep: float = 4.0,
    temperature: float = 0.0,
    detail: str = "high",
    min_call_interval_sec: float = 0.0,
):
    """Volcengine Ark Seed-family VLM. Defaults to Seed 2.0 Lite.

    Each yes/no call samples `n_frames` keyframes from the input clip,
    base64-jpegs them, and sends as image_url content alongside a 1-line
    yes/no prompt. We parse the LLM's first "yes"/"no" token (case insensitive).

    Override model via SEED_VLM_MODEL_ID env var or `model_id` arg.
    """
    import os
    import base64
    import time
    import random
    import re
    import threading
    import cv2
    from volcenginesdkarkruntime import Ark                             # noqa

    model_id = model_id or os.environ.get("SEED_VLM_MODEL_ID", "doubao-seed-2-0-lite-260215")
    api_key = api_key or os.environ.get("ARK_API_KEY")
    if not api_key:
        raise RuntimeError("Set ARK_API_KEY env var or pass api_key=")

    # Read pacing knob from env (override per-process without code changes)
    min_call_interval_sec = float(os.environ.get("SEED_VLM_MIN_INTERVAL_SEC",
                                                 min_call_interval_sec))

    _local = threading.local()
    _last_call_lock = threading.Lock()
    _last_call_ts = [0.0]  # mutable holder for last call timestamp

    def _client():
        c = getattr(_local, "client", None)
        if c is None:
            c = Ark(base_url=base_url, api_key=api_key)
            _local.client = c
        return c

    def _encode(frame: np.ndarray) -> str:
        h, w = frame.shape[:2]
        scale = min(1.0, max_side / max(h, w))
        if scale < 1.0:
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
        bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
        if not ok:
            raise RuntimeError("jpeg encode failed")
        return base64.b64encode(buf).decode("utf-8")

    def _sample(frames: np.ndarray, k: int) -> np.ndarray:
        T = frames.shape[0]
        if T <= k:
            return frames
        idx = np.linspace(0, T - 1, k).round().astype(int)
        return frames[idx]

    YES_NO_INSTR = (
        "You are a strict visual judge. Look at the frames and answer the question "
        "with exactly one word: 'yes' or 'no'. Do not explain.\n\nQuestion: "
    )

    YES_RE = re.compile(r"^\s*(yes|true|是)\b", re.IGNORECASE)
    NO_RE = re.compile(r"^\s*(no|false|否|不)\b", re.IGNORECASE)

    def _parse(text: str) -> bool:
        if YES_RE.search(text or ""):
            return True
        if NO_RE.search(text or ""):
            return False
        # fallback: substring search
        t = (text or "").lower()
        return ("yes" in t and "no" not in t.split("yes", 1)[0])

    # Robust integer parser for 0..max_score ratings. Returns float in [0,1] or None.
    _RATING_RE = re.compile(r"\b([0-9](?:\.[0-9])?)\b")
    def _parse_rating(text: str, max_score: int) -> float | None:
        if not text:
            return None
        # Look for the FIRST integer/decimal in the response
        m = _RATING_RE.search(text)
        if not m:
            return None
        try:
            v = float(m.group(1))
        except ValueError:
            return None
        # Clip to [0, max_score] and normalise
        v = max(0.0, min(float(max_score), v))
        return v / max(float(max_score), 1e-6)

    class _SeedVlm(VlmBackend):
        def _do_call(self, content):
            """Shared call+retry logic; returns raw text response."""
            last_err = None
            for attempt in range(max_retries):
                if min_call_interval_sec > 0:
                    with _last_call_lock:
                        now = time.time()
                        wait = (_last_call_ts[0] + min_call_interval_sec) - now
                        if wait > 0:
                            time.sleep(wait)
                        _last_call_ts[0] = time.time()

                try:
                    resp = _client().chat.completions.create(
                        model=model_id,
                        messages=[{"role": "user", "content": content}],
                        temperature=temperature,
                    )
                    return resp.choices[0].message.content or ""
                except Exception as e:
                    last_err = e
                    msg = str(e).lower()
                    is_rate_limit = ("429" in msg or "tpm" in msg or
                                     "rate" in msg or "toomanyrequest" in msg)
                    if is_rate_limit:
                        sleep_s = 30 + 15 * attempt + random.random() * 5
                    else:
                        sleep_s = retry_sleep * (2 ** attempt) + random.random()
                    time.sleep(sleep_s)
            raise RuntimeError(f"Seed VLM failed after {max_retries} retries: {last_err}")

        def yes_no(self, frames, question):
            sampled = _sample(frames, n_frames)
            content = [{"type": "text", "text": YES_NO_INSTR + question}]
            for f in sampled:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{_encode(f)}",
                        "detail": detail,
                    },
                })
            return _parse(self._do_call(content))

        def rate(self, frames, prompt, max_score=5):
            """Single-clip rating: rate the edit quality from frames + prompt.
            Used for in-shot evaluation. Returns continuous score in [0, 1]."""
            sampled = _sample(frames, n_frames)
            content = [{"type": "text", "text": prompt}]
            for f in sampled:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{_encode(f)}",
                        "detail": detail,
                    },
                })
            text = self._do_call(content)
            return _parse_rating(text, max_score)

        def rate_pair(self, frames_a, frames_b, prompt, max_score=5):
            """Show two frame sets (e.g. source + edit, or shot1 + shot2 edits).
            Returns continuous rating in [0, 1]. We send them as two image
            groups labelled FRAME-SET A and FRAME-SET B in the prompt."""
            sa = _sample(frames_a, n_frames)
            sb = _sample(frames_b, n_frames)
            content = [{"type": "text", "text": prompt}]
            content.append({"type": "text", "text": "[FRAME-SET A]"})
            for f in sa:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{_encode(f)}",
                        "detail": detail,
                    },
                })
            content.append({"type": "text", "text": "[FRAME-SET B]"})
            for f in sb:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{_encode(f)}",
                        "detail": detail,
                    },
                })
            text = self._do_call(content)
            return _parse_rating(text, max_score)

    return _SeedVlm()


_QWEN3VL_SINGLETON = None


def _parse_unit_rating(text: str, max_score: int) -> float | None:
    # 中文注释：VLM prompt 要求输出 0-5；这里从回复中取第一个数字并归一化到 [0,1]。
    if not text:
        return None
    m = re.search(r"\b([0-9](?:\.[0-9])?)\b", text)
    if not m:
        return None
    try:
        v = float(m.group(1))
    except ValueError:
        return None
    v = max(0.0, min(float(max_score), v))
    return v / max(float(max_score), 1e-6)


def _parse_yes_no(text: str) -> bool:
    # 中文注释：yes/no 裁判解析失败时走保守规则，避免长解释干扰。
    if re.search(r"^\s*(yes|true|是)\b", text or "", re.IGNORECASE):
        return True
    if re.search(r"^\s*(no|false|否|不)\b", text or "", re.IGNORECASE):
        return False
    low = (text or "").lower()
    return "yes" in low and "no" not in low.split("yes", 1)[0]


def _make_qwen3vl_vlm(model_path: str | None = None):
    """Local Qwen3-VL VLM backend.

    Defaults to the repository-local Qwen3-VL/ckpt directory. The model is
    cached as a singleton because run_eval creates three VLM objects for the
    old 3-judge protocol, and loading three 8B copies is unnecessary.
    """
    global _QWEN3VL_SINGLETON
    if _QWEN3VL_SINGLETON is not None:
        # 中文注释：run_eval 可创建多个 VLM 对象，供旧版多数票接口使用；
        # 本地 Qwen3-VL 只加载一份模型，三个对象共享它，避免显存爆掉。
        return _QWEN3VL_SINGLETON

    import sys
    import threading
    import torch
    from PIL import Image
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    repo_root = Path(__file__).resolve().parents[2]
    qwen_root = repo_root / "Qwen3-VL"
    utils_src = qwen_root / "qwen-vl-utils" / "src"
    if utils_src.exists() and str(utils_src) not in sys.path:
        # 中文注释：你把 qwen-vl-utils 源码放在 Qwen3-VL 目录下，
        # 这里动态加入 sys.path，不要求额外 pip install。
        sys.path.insert(0, str(utils_src))
    from qwen_vl_utils import process_vision_info

    model_path = model_path or os.environ.get("QWEN3VL_MODEL_PATH") or str(qwen_root / "ckpt")
    # 中文注释：image_size 越小越快但细节更少；max_new_tokens 越小越省时。
    image_size = int(os.environ.get("QWEN3VL_IMAGE_SIZE", 384))
    frame_set_n = int(os.environ.get("QWEN3VL_FRAME_SET_IMAGES", 2))
    max_new_tokens = int(os.environ.get("QWEN3VL_MAX_NEW_TOKENS", 16))
    device_map = os.environ.get("QWEN3VL_DEVICE_MAP", "auto")

    processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
    # 中文注释：local_files_only=True 强制只用本地 Qwen3-VL 权重，不触发联网下载。
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_path,
        dtype=os.environ.get("QWEN3VL_DTYPE", "auto"),
        device_map=device_map,
        local_files_only=True,
    )
    model.eval()
    patch_size = getattr(getattr(processor, "image_processor", None), "patch_size", 16) or 16

    def _model_device():
        try:
            return model.device
        except Exception:
            return next(model.parameters()).device

    def _pil(frame: np.ndarray) -> Image.Image:
        arr = np.asarray(frame)
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        return Image.fromarray(arr)

    def _frame_sig(frame: np.ndarray) -> str:
        # 中文注释：用帧内容 hash 做缓存 key，避免同一帧/同一 prompt 重复生成。
        arr = np.asarray(frame)
        h = hashlib.md5()
        h.update(str(arr.shape).encode())
        h.update(arr.tobytes())
        return h.hexdigest()

    def _sample_frames(frames: np.ndarray, k: int) -> list[np.ndarray]:
        # 中文注释：rate_pair/yes_no 会从一个 shot 的 frame set 中等间隔抽 k 帧。
        if len(frames) == 0:
            return []
        n = min(max(1, k), len(frames))
        idx = np.linspace(0, len(frames) - 1, n).round().astype(int)
        return [frames[int(i)] for i in idx]

    class _Qwen3VL(VlmBackend):
        is_local_model = True

        def __init__(self):
            self._lock = threading.Lock()
            self._cache = {}

        def _generate(self, content: list[dict]) -> str:
            # 中文注释：把 text/image content 组装成 Qwen3-VL chat 输入并生成短回复。
            messages = [{"role": "user", "content": content}]
            text = processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            images, videos, video_kwargs = process_vision_info(
                messages,
                image_patch_size=patch_size,
                return_video_kwargs=True,
                return_video_metadata=True,
            )
            if videos is not None:
                videos, video_metadatas = zip(*videos)
                videos, video_metadatas = list(videos), list(video_metadatas)
            else:
                video_metadatas = None
            inputs = processor(
                text=text,
                images=images,
                videos=videos,
                video_metadata=video_metadatas,
                return_tensors="pt",
                do_resize=False,
                **video_kwargs,
            )
            inputs = inputs.to(_model_device())
            with self._lock, torch.inference_mode():
                # 中文注释：本地模型生成串行化，避免多线程同时调用 generate 导致显存/状态问题。
                generated_ids = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                )
            trimmed = [
                out_ids[len(in_ids):]
                for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            return processor.batch_decode(
                trimmed,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )[0].strip()

        def _cached_generate(self, key, content: list[dict]) -> str:
            # 中文注释：同一轮评测里相同输入直接复用回复，节省 Qwen 推理时间。
            if key in self._cache:
                return self._cache[key]
            out = self._generate(content)
            self._cache[key] = out
            return out

        def rate_image_pair(self, frame_a, frame_b, prompt, max_score=5):
            # 中文注释：EE_v3 的核心接口：给一张 source 图和一张 edit 图，让 Qwen 打 0-5 分。
            key = ("rate_image_pair", prompt, _frame_sig(frame_a), _frame_sig(frame_b), max_score)
            content = [
                {"type": "text", "text": "ORIGINAL image:"},
                {"type": "image", "image": _pil(frame_a), "resized_height": image_size, "resized_width": image_size},
                {"type": "text", "text": "EDITED image:"},
                {"type": "image", "image": _pil(frame_b), "resized_height": image_size, "resized_width": image_size},
                {"type": "text", "text": prompt},
            ]
            return _parse_unit_rating(self._cached_generate(key, content), max_score)

        def rate_pair(self, frames_a, frames_b, prompt, max_score=5):
            # 中文注释：CSEP_v3 的核心接口：给两个 edited shot 的帧集合，判断一致性。
            a = _sample_frames(frames_a, frame_set_n)
            b = _sample_frames(frames_b, frame_set_n)
            if not a or not b:
                return None
            key = (
                "rate_pair", prompt,
                tuple(_frame_sig(x) for x in a),
                tuple(_frame_sig(x) for x in b),
                max_score,
            )
            content = [{"type": "text", "text": "Frame-set A:"}]
            for i, frame in enumerate(a, 1):
                content.extend([
                    {"type": "text", "text": f"A{i}:"},
                    {"type": "image", "image": _pil(frame), "resized_height": image_size, "resized_width": image_size},
                ])
            content.append({"type": "text", "text": "Frame-set B:"})
            for i, frame in enumerate(b, 1):
                content.extend([
                    {"type": "text", "text": f"B{i}:"},
                    {"type": "image", "image": _pil(frame), "resized_height": image_size, "resized_width": image_size},
                ])
            content.append({"type": "text", "text": prompt})
            return _parse_unit_rating(self._cached_generate(key, content), max_score)

        def rate(self, frames, prompt, max_score=5):
            sampled = _sample_frames(frames, frame_set_n)
            if not sampled:
                return None
            key = ("rate", prompt, tuple(_frame_sig(x) for x in sampled), max_score)
            content = []
            for i, frame in enumerate(sampled, 1):
                content.extend([
                    {"type": "text", "text": f"Image {i}:"},
                    {"type": "image", "image": _pil(frame), "resized_height": image_size, "resized_width": image_size},
                ])
            content.append({"type": "text", "text": prompt})
            return _parse_unit_rating(self._cached_generate(key, content), max_score)

        def yes_no(self, frames, question):
            # 中文注释：yes/no 接口用于旧版二值裁判。
            sampled = _sample_frames(frames, frame_set_n)
            if not sampled:
                return False
            prompt = (
                "Answer the visual question using exactly one word: yes or no. "
                f"Question: {question}"
            )
            key = ("yes_no", prompt, tuple(_frame_sig(x) for x in sampled))
            content = []
            for i, frame in enumerate(sampled, 1):
                content.extend([
                    {"type": "text", "text": f"Image {i}:"},
                    {"type": "image", "image": _pil(frame), "resized_height": image_size, "resized_width": image_size},
                ])
            content.append({"type": "text", "text": prompt})
            return _parse_yes_no(self._cached_generate(key, content))

    _QWEN3VL_SINGLETON = _Qwen3VL()
    return _QWEN3VL_SINGLETON


# -- public getters ----------------------------------------------------------

def get_clip(kind: str = "mock"):
    # 中文注释：这些 get_* 是 run_eval.py 唯一调用的后端入口。
    if kind == "mock":   return MockClip()
    if kind == "siglip": return _make_real_clip("ViT-SO400M-14-SigLIP")
    if kind == "openai": return _make_real_clip("ViT-B-32")
    raise ValueError(kind)


def get_dino(kind: str = "mock"):
    if kind == "mock": return MockDino()
    if kind == "v2s":  return _make_real_dino("dinov2_vits14")
    if kind == "v2b":  return _make_real_dino("dinov2_vitb14")
    raise ValueError(kind)


def get_face(kind: str = "mock"):
    if kind == "mock":      return MockFace()
    if kind == "insightface": return _make_real_face()
    raise ValueError(kind)


def get_vlm(kind: str = "mock", **kwargs):
    if kind == "mock": return MockVlm()
    if kind == "seed": return _make_seed_vlm(**kwargs)
    if kind in {"qwen3vl", "qwen"}: return _make_qwen3vl_vlm(**kwargs)
    raise ValueError(f"VLM backend {kind!r} not yet wired (drop in your VLM client here)")


# -- PSQ backend (MUSIQ + LAION-Aes via pyiqa) -------------------------------

def _make_pyiqa_psq(device: str | None = None):
    """Returns a callable (frames_uint8 [T,H,W,3]) -> (musiq_0_100, laion_1_10).

    Loads MUSIQ (KonIQ-trained) + LAION-Aes once, batches all frames in a
    single forward pass per shot. ~50ms/frame on a single A100.
    """
    import torch
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    # 中文注释：pyiqa 可能间接用 torch hub/CLIP 下载权重，这里统一指向本地 ckpt 根目录。
    torch.hub.set_dir(
        os.environ.get("MSEDITBENCH_TORCH_HUB_DIR", str(_metric_ckpt_root()))
    )
    import pyiqa
    try:
        import clip as _clip
        raw_load = _clip.load
        if not getattr(raw_load, "_mseditbench_ckpt_wrapped", False):
            def _load_with_ckpt_root(name, device="cpu", jit=False, download_root=None):
                return raw_load(
                    name,
                    device=device,
                    jit=jit,
                    download_root=download_root or str(_metric_ckpt_path("clip")),
                )

            _load_with_ckpt_root._mseditbench_ckpt_wrapped = True
            _clip.load = _load_with_ckpt_root
    except ImportError:
        pass
    musiq = pyiqa.create_metric("musiq", device=device)
    laion = pyiqa.create_metric("laion_aes", device=device)
    for m in (musiq, laion):
        m.eval()

    @torch.no_grad()
    def _score(frames: np.ndarray) -> tuple[float, float]:
        # 中文注释：对一个 shot 内所有帧分别算 MUSIQ/LAION-Aes，再取均值作为 shot 质量。
        if len(frames) == 0:
            return 0.0, 0.0
        x = torch.from_numpy(frames).permute(0, 3, 1, 2).float().to(device) / 255.0
        m_scores = musiq(x).flatten().tolist()
        l_scores = laion(x).flatten().tolist()
        return float(np.mean(m_scores)), float(np.mean(l_scores))

    return _score


def get_psq(kind: str = "mock"):
    """PSQ backend: callable frames -> (musiq_0_100, laion_1_10)."""
    if kind == "mock":
        _psq_mod = importlib.import_module("mseditbench.metrics.psq")
        return _psq_mod._mock_quality
    if kind == "pyiqa":
        return _make_pyiqa_psq()
    raise ValueError(f"PSQ backend {kind!r} unknown")


# -- Mask backend (SAM-3 text-conditional segmentation) ---------------------

def _make_sam3_mask(ckpt_path: str | None = None,
                    score_threshold: float = 0.3,
                    device: str | None = None):
    """Returns a callable (frames_uint8 [T,H,W,3], phrase: str) -> mask [T,H,W] uint8.

    Runs SAM-3 on each frame with the text phrase. If multiple instances are
    detected, takes the union (any-instance mask). If no detection above
    threshold, returns all-zeros mask for that frame.

    SAM-3 takes ~0.7s/frame at 720p, so we expect ~5s per shot (6 frames).
    """
    import torch
    from PIL import Image
    from sam3.model_builder import build_sam3_image_model
    from sam3.model.sam3_image_processor import Sam3Processor

    if ckpt_path is None:
        # 中文注释：SAM3 权重默认就是 mseditbench/ckpt/sam3/sam3.pt。
        ckpt_path = os.environ.get(
            "SAM3_CKPT",
            str(_metric_ckpt_path("sam3", "sam3.pt")),
        )
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if str(device) != "cuda":
        raise RuntimeError(
            "SAM-3 image backend requires CUDA in the installed sam3 package; "
            "run with a visible GPU or use --backend_mask none."
        )
    bpe_path = (
        Path(__file__).resolve().parents[2]
        / "sam3"
        / "sam3"
        / "assets"
        / "bpe_simple_vocab_16e6.txt.gz"
    )
    model = build_sam3_image_model(
        checkpoint_path=ckpt_path,
        bpe_path=str(bpe_path),
        device=device,
    ).eval()
    processor = Sam3Processor(model, device=device)

    @torch.no_grad()
    def _mask(frames: np.ndarray, phrase: str) -> np.ndarray:
        # 中文注释：输入可以是一帧或多帧；run_eval 当前用 source shot 的中间帧做 anchor。
        T, H, W = frames.shape[:3]
        out = np.zeros((T, H, W), dtype=np.uint8)
        for i in range(T):
            img = Image.fromarray(frames[i])
            try:
                with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                    state = processor.set_image(img)
                    res = processor.set_text_prompt(state=state, prompt=phrase)
            except Exception as e:
                print(f"[sam3] frame {i} '{phrase[:30]}': {e}")
                continue
            masks = res.get("masks")
            scores = res.get("scores")
            if masks is None or len(masks) == 0:
                continue
            # Filter by score threshold
            # 中文注释：低置信度 mask 不用；没有可用 mask 时该帧保持全 0。
            if hasattr(scores, "detach"):
                sc = scores.detach().float().cpu().numpy()
            else:
                sc = np.asarray(scores, dtype=np.float32)
            keep = sc >= score_threshold
            if not keep.any():
                continue
            # masks shape: (N, 1, H, W) or (N, H, W); take union
            # 中文注释：如果检测到多个实例，取并集，表示“目标区域整体”。
            if hasattr(masks, "detach"):
                ms = masks.detach().cpu().numpy()
            else:
                ms = np.asarray(masks)
            ms = ms.squeeze(1) if ms.ndim == 4 else ms
            union = ms[keep].astype(bool).any(axis=0).astype(np.uint8)
            if union.shape != (H, W):
                import cv2
                union = cv2.resize(union, (W, H), interpolation=cv2.INTER_NEAREST)
            out[i] = union
        return out

    return _mask


def get_mask(kind: str = "none"):
    """Mask backend: callable (frames, phrase) -> mask, or None."""
    if kind == "none":
        return None
    if kind == "sam3":
        return _make_sam3_mask()
    raise ValueError(f"Mask backend {kind!r} unknown")
