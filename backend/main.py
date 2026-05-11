"""FastAPI server for SubSync Studio."""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import pysubs2

from . import converters, opensubtitles, sync_engine

ROOT = Path(__file__).resolve().parent.parent
STORAGE = ROOT / "storage"
UPLOADS = STORAGE / "uploads"
OUTPUTS = STORAGE / "outputs"
FRONTEND = ROOT / "frontend"

for path in (UPLOADS, OUTPUTS):
    path.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="SubSync Studio", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _new_session_dir(base: Path) -> Path:
    session = base / uuid.uuid4().hex[:12]
    session.mkdir(parents=True, exist_ok=True)
    return session


async def _save_upload(upload: UploadFile, dest_dir: Path) -> Path:
    safe_name = Path(upload.filename or "file.bin").name
    dest = dest_dir / safe_name
    async with aiofiles.open(dest, "wb") as fh:
        while chunk := await upload.read(1024 * 1024):
            await fh.write(chunk)
    await upload.close()
    return dest


def _resolve_within(root: Path, name: str) -> Path:
    candidate = (root / name).resolve()
    if root.resolve() not in candidate.parents and candidate != root.resolve():
        raise HTTPException(status_code=400, detail="Invalid path")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return candidate


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class SyncResponse(BaseModel):
    session_id: str
    method: str
    output_file: str
    preview_vtt: str
    cues: list


class SearchResponse(BaseModel):
    hits: list


class CueModel(BaseModel):
    start_ms: int
    end_ms: int
    text: str


class SaveRequest(BaseModel):
    session_id: str
    file_name: str
    cues: List[CueModel]
    output_format: str = "srt"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "ffsubsync": shutil.which("ffsubsync") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "opensubtitles": bool(os.environ.get("OPENSUBTITLES_API_KEY")),
    }


@app.post("/api/sync", response_model=SyncResponse)
async def sync(
    subtitle: UploadFile = File(...),
    video: Optional[UploadFile] = File(None),
    reference: Optional[UploadFile] = File(None),
):
    if not subtitle.filename:
        raise HTTPException(status_code=400, detail="Subtitle file is required")
    if video is None and reference is None:
        raise HTTPException(
            status_code=400,
            detail="Provide a video (audio sync) or a reference subtitle.",
        )

    session = _new_session_dir(UPLOADS)
    sub_path = await _save_upload(subtitle, session)

    video_path: Optional[Path] = None
    ref_path: Optional[Path] = None
    if video is not None and video.filename:
        video_path = await _save_upload(video, session)
    if reference is not None and reference.filename:
        ref_path = await _save_upload(reference, session)

    out_session = _new_session_dir(OUTPUTS)
    try:
        result = sync_engine.auto_sync(
            subtitle=sub_path,
            out_dir=out_session,
            video=video_path,
            reference=ref_path,
        )
    except sync_engine.SyncError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    vtt_path = converters.to_vtt(result.output_path)
    subs = converters.load_subs(result.output_path)
    cues = [
        {"start_ms": ev.start, "end_ms": ev.end, "text": ev.plaintext}
        for ev in subs
        if not ev.is_comment
    ]

    return SyncResponse(
        session_id=out_session.name,
        method=result.method,
        output_file=result.output_path.name,
        preview_vtt=vtt_path.name,
        cues=cues,
    )


@app.get("/api/download/{session_id}/{file_name}")
def download(session_id: str, file_name: str, fmt: Optional[str] = None):
    session_dir = OUTPUTS / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    target = _resolve_within(session_dir, file_name)
    if fmt and target.suffix.lower().lstrip(".") != fmt.lower():
        converted = converters.convert_file(target, fmt)
        return FileResponse(
            converted, filename=converted.name, media_type="application/octet-stream"
        )
    media_type = "text/vtt" if target.suffix.lower() == ".vtt" else "application/octet-stream"
    return FileResponse(target, filename=target.name, media_type=media_type)


@app.post("/api/save")
def save_edits(req: SaveRequest):
    """Persist user edits from the manual editor back to the output file."""
    session_dir = OUTPUTS / req.session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    target = _resolve_within(session_dir, req.file_name)
    subs = pysubs2.SSAFile()
    for cue in req.cues:
        subs.append(
            pysubs2.SSAEvent(start=cue.start_ms, end=cue.end_ms, text=cue.text)
        )

    fmt = req.output_format.lower()
    if fmt not in converters.SUPPORTED_OUTPUT:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}")

    out_path = target.with_suffix(f".edited.{fmt}")
    subs.save(str(out_path), format_=fmt, encoding="utf-8")

    vtt = converters.to_vtt(out_path)
    return {"file_name": out_path.name, "preview_vtt": vtt.name}


@app.get("/api/search", response_model=SearchResponse)
def search_subs(q: str, languages: str = "en,ar", limit: int = 20):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query is required")
    try:
        hits = opensubtitles.search(q, languages=languages, limit=limit)
    except opensubtitles.OpenSubtitlesError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return SearchResponse(hits=[hit.__dict__ for hit in hits])


@app.post("/api/fetch")
def fetch_sub(file_id: int = Form(...)):
    session = _new_session_dir(UPLOADS)
    try:
        downloaded = opensubtitles.download(file_id, session)
    except opensubtitles.OpenSubtitlesError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"session_id": session.name, "file_name": downloaded.name}


@app.get("/api/fetched/{session_id}/{file_name}")
def get_fetched(session_id: str, file_name: str):
    session_dir = UPLOADS / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    target = _resolve_within(session_dir, file_name)
    return FileResponse(target, filename=target.name)


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
else:
    @app.get("/")
    def index() -> JSONResponse:
        return JSONResponse({"message": "Frontend not built yet."})
