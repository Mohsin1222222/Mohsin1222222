"""Wrapper around ffsubsync for both audio-based and reference-based sync."""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class SyncError(RuntimeError):
    pass


@dataclass
class SyncResult:
    output_path: Path
    method: str
    log: str


def _ensure_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise SyncError(
            f"Required binary '{name}' not found on PATH. "
            "Install ffmpeg and ffsubsync before running the server."
        )


def sync_to_video(subtitle: Path, video: Path, out_dir: Path) -> SyncResult:
    """Sync subtitle using the video's audio track (VAD)."""
    _ensure_binary("ffsubsync")
    _ensure_binary("ffmpeg")

    out_path = out_dir / f"{subtitle.stem}.synced{subtitle.suffix}"
    cmd = [
        "ffsubsync",
        str(video),
        "-i",
        str(subtitle),
        "-o",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SyncError(
            f"ffsubsync failed (video sync):\n{proc.stderr or proc.stdout}"
        )
    return SyncResult(output_path=out_path, method="audio-vad", log=proc.stdout)


def sync_to_reference(
    subtitle: Path, reference: Path, out_dir: Path
) -> SyncResult:
    """Sync subtitle against a reference subtitle already aligned to the video."""
    _ensure_binary("ffsubsync")

    out_path = out_dir / f"{subtitle.stem}.synced{subtitle.suffix}"
    cmd = [
        "ffsubsync",
        str(reference),
        "-i",
        str(subtitle),
        "-o",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SyncError(
            f"ffsubsync failed (reference sync):\n{proc.stderr or proc.stdout}"
        )
    return SyncResult(output_path=out_path, method="reference", log=proc.stdout)


def auto_sync(
    subtitle: Path,
    out_dir: Path,
    video: Optional[Path] = None,
    reference: Optional[Path] = None,
) -> SyncResult:
    """Pick the best method based on what was provided.

    Audio VAD is preferred when a video is available — it stays accurate even
    when the cuts differ across the file (intros, ads, recaps). Reference sync
    is used as a fallback when only another subtitle is available.
    """
    if video is not None:
        return sync_to_video(subtitle, video, out_dir)
    if reference is not None:
        return sync_to_reference(subtitle, reference, out_dir)
    raise SyncError("Either a video or a reference subtitle is required.")
