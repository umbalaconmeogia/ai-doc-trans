from __future__ import annotations

from typing import Optional

from ai_doc_trans.engine.tm import TM
from ai_doc_trans.models import TranslatedSegment


def run_import(
    translated: list[TranslatedSegment],
    target_lang: Optional[str],
    tm: TM,
    project_id: int,
) -> tuple[int, int]:
    """
    Import segments into the TM database.

    For each segment: ensures segment_source exists (get_or_create_source).
    When target and target_lang are present: also upserts segment_target.
    Works with source-only JSON (e.g. output of extract).

    Returns (sources_ensured, targets_upserted).
    """
    sources_ensured = 0
    targets_upserted = 0
    for ts in translated:
        source_id = tm.get_or_create_source(
            source_hash=ts.source_hash,
            source_text=ts.source,
            source_lang=ts.source_lang,
            structure=ts.structure,
            project_id=project_id,
            position=ts.position,
        )
        sources_ensured += 1
        if ts.target and target_lang:
            tm.upsert_target(source_id, target_lang, ts.target)
            targets_upserted += 1
    return sources_ensured, targets_upserted
