"""Hash utilities for TM segment lookup.

source_hash = sha256(source_text) — one record per source_text in segment_sources.
"""

from __future__ import annotations

import hashlib


def compute_source_hash(source_text: str) -> str:
    """Compute source_hash from source_text only.

    Same source_text → same hash → one record in segment_sources (per project).
    """
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()
