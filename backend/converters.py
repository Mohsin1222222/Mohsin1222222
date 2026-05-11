"""Subtitle format conversion helpers built on pysubs2."""
from __future__ import annotations

from pathlib import Path

import pysubs2

SUPPORTED_INPUT = {".srt", ".ass", ".ssa", ".vtt", ".sub"}
SUPPORTED_OUTPUT = {"srt", "ass", "vtt"}


def detect_format(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    if ext == "ssa":
        return "ass"
    return ext


def load_subs(path: Path) -> pysubs2.SSAFile:
    # Subtitle files arrive in many encodings (UTF-8, Windows-1256 for Arabic,
    # CP1252, etc.). Try a sensible chain before falling back to a lossy read.
    for enc in ("utf-8", "utf-8-sig", "cp1256", "cp1252", "latin-1"):
        try:
            return pysubs2.load(str(path), encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(path, "rb") as fh:
        text = fh.read().decode("utf-8", errors="replace")
    return pysubs2.SSAFile.from_string(text)


def save_subs(subs: pysubs2.SSAFile, path: Path, fmt: str) -> Path:
    fmt = fmt.lower()
    if fmt not in SUPPORTED_OUTPUT:
        raise ValueError(f"Unsupported output format: {fmt}")
    out_path = path.with_suffix(f".{fmt}")
    subs.save(str(out_path), format_=fmt, encoding="utf-8")
    return out_path


def convert_file(src: Path, dst_fmt: str) -> Path:
    subs = load_subs(src)
    return save_subs(subs, src, dst_fmt)


def to_vtt(src: Path) -> Path:
    """Always return a VTT version for browser playback."""
    subs = load_subs(src)
    out = src.with_suffix(".preview.vtt")
    subs.save(str(out), format_="vtt", encoding="utf-8")
    return out
