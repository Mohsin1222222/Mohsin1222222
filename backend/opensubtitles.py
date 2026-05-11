"""Minimal OpenSubtitles REST API client.

Requires an API key (free tier available at https://www.opensubtitles.com/consumers).
Set OPENSUBTITLES_API_KEY in the environment to enable subtitle search/download.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import requests

API_BASE = "https://api.opensubtitles.com/api/v1"
USER_AGENT = "SubSyncStudio v1.0"


class OpenSubtitlesError(RuntimeError):
    pass


@dataclass
class SubtitleHit:
    id: str
    file_id: int
    language: str
    release: str
    movie_name: str
    download_count: int
    fps: Optional[float]


def _headers() -> dict:
    api_key = os.environ.get("OPENSUBTITLES_API_KEY")
    if not api_key:
        raise OpenSubtitlesError(
            "OPENSUBTITLES_API_KEY is not configured. "
            "Get a free key at https://www.opensubtitles.com/consumers"
        )
    return {
        "Api-Key": api_key,
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
    }


def search(query: str, languages: str = "en,ar", limit: int = 20) -> List[SubtitleHit]:
    resp = requests.get(
        f"{API_BASE}/subtitles",
        headers=_headers(),
        params={"query": query, "languages": languages, "order_by": "download_count"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise OpenSubtitlesError(f"Search failed: {resp.status_code} {resp.text}")

    hits: List[SubtitleHit] = []
    for item in resp.json().get("data", [])[:limit]:
        attrs = item.get("attributes", {})
        files = attrs.get("files") or []
        if not files:
            continue
        hits.append(
            SubtitleHit(
                id=item.get("id", ""),
                file_id=files[0].get("file_id", 0),
                language=attrs.get("language", ""),
                release=attrs.get("release", ""),
                movie_name=(attrs.get("feature_details") or {}).get("movie_name", ""),
                download_count=attrs.get("download_count", 0),
                fps=attrs.get("fps"),
            )
        )
    return hits


def download(file_id: int, dest_dir: Path) -> Path:
    resp = requests.post(
        f"{API_BASE}/download",
        headers=_headers(),
        json={"file_id": file_id},
        timeout=30,
    )
    if resp.status_code != 200:
        raise OpenSubtitlesError(f"Download request failed: {resp.status_code} {resp.text}")

    payload = resp.json()
    link = payload.get("link")
    file_name = payload.get("file_name", f"opensubtitles_{file_id}.srt")
    if not link:
        raise OpenSubtitlesError(f"No download link in response: {payload}")

    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_dir / file_name
    with requests.get(link, stream=True, timeout=60) as stream:
        stream.raise_for_status()
        with open(out_path, "wb") as fh:
            for chunk in stream.iter_content(8192):
                fh.write(chunk)
    return out_path
