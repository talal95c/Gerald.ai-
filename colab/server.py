from __future__ import annotations

import base64
import binascii
import hmac
import io
import re
import secrets

import torch
from fastapi import FastAPI, Header, HTTPException
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from transformers import AutoModelForCausalLM

MODEL_ID = "vikhyatk/moondream2"
MODEL_REVISION = "2025-06-21"
TOKEN = secrets.token_urlsafe(16)
print(f"Moondream grounder token: {TOKEN}")

model = None
app = FastAPI()


class PointRequest(BaseModel):
    image_url: str
    object: str
    model: str | None = None


def load_model(device: str | None = None):
    target = device or ("cuda" if torch.cuda.is_available() else "cpu")
    if target == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available")
    dtype = torch.float16 if target == "cuda" else torch.float32
    loaded = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        trust_remote_code=True,
        torch_dtype=dtype,
    )
    return loaded.to(target).eval()


@app.on_event("startup")
async def load_model_on_startup() -> None:
    global model
    if model is None:
        model = load_model()


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": model is not None}


@app.post("/v1/point")
async def point(
    request: PointRequest,
    x_moondream_auth: str | None = Header(default=None),
) -> dict[str, object]:
    if not x_moondream_auth or not hmac.compare_digest(x_moondream_auth, TOKEN):
        raise HTTPException(status_code=401, detail="Invalid token")
    header, separator, encoded = request.image_url.partition(",")
    if not separator or not re.fullmatch(r"data:image/[A-Za-z0-9.+-]+;base64", header):
        raise HTTPException(status_code=400, detail="Invalid image_url")
    try:
        image_data = base64.b64decode(encoded, validate=True)
        with Image.open(io.BytesIO(image_data)) as opened:
            image = opened.convert("RGB")
    except (binascii.Error, UnidentifiedImageError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid image_url") from None
    if model is None:
        raise HTTPException(status_code=503, detail="Model is not loaded")
    return {"points": model.point(image, request.object)["points"]}


def parse_trycloudflare_url(output: str) -> str | None:
    match = re.search(r"https://[A-Za-z0-9-]+\.trycloudflare\.com", output)
    return match.group(0) if match else None
