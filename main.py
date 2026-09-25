from __future__ import annotations

import asyncio
import os
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated

import imageio_ffmpeg
import perth
import torch
import torchaudio
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = Path(tempfile.gettempdir()) / "heartline-audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
VOICE_DIR = BASE_DIR / "voice-samples"
VOICE_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_TYPES = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/webm",
    "audio/ogg",
    "video/mp4",
}

app = FastAPI(title="Heartline Voice")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
tts_model: ChatterboxMultilingualTTS | None = None


class NoOpWatermarker:
    def apply_watermark(self, audio, sample_rate):
        return audio


class SpeakRequest(BaseModel):
    voice_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=1200)
    language: str = Field(default="en", pattern="^(en|hi|ko)$")


def local_model() -> ChatterboxMultilingualTTS:
    global tts_model
    if tts_model is None:
        if perth.PerthImplicitWatermarker is None:
            perth.PerthImplicitWatermarker = NoOpWatermarker
        device = "cuda" if torch.cuda.is_available() else "cpu"
        tts_model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    return tts_model


def convert_to_wav(source: Path, target: Path) -> None:
    try:
        subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(source), "-vn", "-acodec", "pcm_s16le", "-ar", "24000", "-ac", "1", str(target)],
            check=True,
            capture_output=True,
            timeout=90,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise HTTPException(status_code=422, detail="That recording could not be read or does not contain an audio track.") from error


def voice_path(voice_id: str) -> Path:
    path = VOICE_DIR / f"{Path(voice_id).name}.wav"
    if path.parent != VOICE_DIR or not path.is_file():
        raise HTTPException(status_code=404, detail="Voice sample not found. Upload it again to create a new local voice.")
    return path


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.post("/api/clone")
async def clone_voice(sample: Annotated[UploadFile, File(...)]) -> dict[str, str]:
    is_mp4 = Path(sample.filename or "").suffix.lower() == ".mp4"
    if sample.content_type not in ALLOWED_TYPES and not is_mp4:
        raise HTTPException(status_code=415, detail="Upload an MP3, WAV, M4A, WEBM, OGG, or MP4 recording.")

    suffix = Path(sample.filename or "sample.wav").suffix.lower() or ".wav"
    temp_path = AUDIO_DIR / f"sample-{secrets.token_hex(8)}{suffix}"
    converted_path = AUDIO_DIR / f"sample-{secrets.token_hex(8)}.wav"
    voice_id = f"voice-{secrets.token_hex(10)}"
    saved_voice_path = VOICE_DIR / f"{voice_id}.wav"
    size = 0
    try:
        with temp_path.open("wb") as output:
            while chunk := await sample.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Keep the voice sample under 25 MB.")
                output.write(chunk)

        convert_to_wav(temp_path, converted_path)
        shutil.copyfile(converted_path, saved_voice_path)
        return {"voice_id": voice_id}
    finally:
        if temp_path.exists():
            temp_path.unlink()
        if converted_path.exists():
            converted_path.unlink()


@app.post("/api/speak")
async def speak(request: SpeakRequest) -> dict[str, str]:
    reference_path = voice_path(request.voice_id)
    filename = f"speech-{secrets.token_hex(10)}.wav"
    output_path = AUDIO_DIR / filename
    try:
        model = local_model()
        waveform = await asyncio.to_thread(
            model.generate,
            request.text.strip(),
            language_id=request.language,
            audio_prompt_path=str(reference_path),
        )
        torchaudio.save(str(output_path), waveform.cpu(), model.sr)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Local speech generation failed: {error}") from error
    return {"audio_url": f"/api/audio/{filename}"}


@app.get("/api/audio/{filename}")
async def audio(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    path = AUDIO_DIR / safe_name
    if not path.is_file() or not safe_name.startswith("speech-"):
        raise HTTPException(status_code=404, detail="Audio not found.")
    return FileResponse(path, media_type="audio/wav", filename=safe_name)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8000")), reload=False)
