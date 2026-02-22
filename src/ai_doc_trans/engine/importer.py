from __future__ import annotations

from ai_doc_trans.engine.tm import TM
from ai_doc_trans.models import TranslatedSegment


def run_import(
    translated: list[TranslatedSegment],
    target_lang: str,
    tm: TM,
    project_id: int,
) -> int:
    """
    Upsert translations from *translated* into the TM database.

    Match is done by source_id (order-independent).
    Returns the number of records upserted.
    """
    count = 0
    for ts in translated:
        if not ts.target:
            continue
        tm.upsert_target(ts.source_id, target_lang, project_id, ts.target)
        count += 1
    return count
