"""CSV import/export for translated segments (source ↔ target mapping per language).

CSV format: each row = one segment with source and target.
Convenient for manual editing (Excel, etc.). Best suited for simple text;
complex formatting or embedded newlines may require care with CSV quoting.

source_hash and source_id are NOT stored in CSV; both are derived on import:
- source_hash = computed from source text only (one record per source_text in TM)
- source_id = looked up/created in TM via source_hash
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING, Union

from ai_doc_trans.hash_utils import compute_source_hash
from ai_doc_trans.models import TranslatedSegment

if TYPE_CHECKING:
    from ai_doc_trans.engine.tm import TM

SEGMENTS_CSV_FIELDS = [
    "source",
    "target",
    "source_lang",
    "target_lang",
    "structure",
    "position",
]


def export_tm_to_csv(
    tm: "TM",
    path: Union[str, Path],
    project_id: int,
    target_lang: str,
    source_lang: str | None = None,
) -> int:
    """Export ALL segments from TM DB to CSV (including those without translation).

    Returns number of rows written.
    """
    rows = tm.list_all_segments_for_export(project_id, target_lang, source_lang)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SEGMENTS_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "source": r.get("source", ""),
                "target": r.get("target", ""),
                "source_lang": r.get("source_lang", ""),
                "target_lang": r.get("target_lang", ""),
                "structure": r.get("structure") or "",
                "position": r.get("position") or "",
            })
    return len(rows)


def import_csv_to_tm(
    path: Union[str, Path],
    tm: "TM",
    project_id: int,
    target_lang: str | None = None,
) -> int:
    """Import CSV into TM DB (upsert segment_targets). Returns count upserted."""
    segments = load_translated_segments_from_csv(
        path, target_lang=target_lang, tm=tm, project_id=project_id
    )
    if not segments:
        return 0
    from ai_doc_trans.engine.importer import run_import

    tl = target_lang or (segments[0].target_lang if segments else None)
    if not tl:
        raise ValueError("target_lang required (--tgt or column in CSV)")
    _, targets_upserted = run_import(segments, tl, tm, project_id)
    return targets_upserted


def load_translated_segments_from_csv(
    path: Union[str, Path],
    target_lang: str | None = None,
    tm: "TM | None" = None,
    project_id: int | None = None,
) -> list[TranslatedSegment]:
    """Load translated segments from CSV.

    Args:
        path: Path to CSV file.
        target_lang: Override target_lang for all rows (when missing in CSV).
        tm: Required TM instance. source_id is always resolved/created via
            computed source_hash (lookup or get_or_create_source).
        project_id: Required for segment import. Source belongs to this project.

    Returns:
        List of TranslatedSegment.
    """
    if tm is None:
        raise ValueError("TM instance required for segment import (source_id derived from hash)")
    if project_id is None:
        raise ValueError("project_id required for segment import")

    result: list[TranslatedSegment] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source = (row.get("source") or "").strip()
            target = (row.get("target") or "").strip()
            if not source:
                continue
            source_lang = (row.get("source_lang") or "").strip() or "en"
            tl = (row.get("target_lang") or "").strip() or target_lang or ""
            if not tl:
                continue
            structure = (row.get("structure") or "").strip() or "cell"
            position = (row.get("position") or "").strip() or None

            # Compute hash from source text only (not stored in CSV)
            source_hash = compute_source_hash(source)

            # Resolve source_id via hash: lookup or create segment_source (project-specific)
            source_id = tm.get_source_id_by_hash(source_hash, project_id)
            if source_id is None:
                source_id = tm.get_or_create_source(
                    source_hash, source, source_lang, structure, project_id, position
                )

            result.append(
                TranslatedSegment(
                    source=source,
                    source_hash=source_hash,
                    source_id=source_id,
                    structure=structure,
                    source_lang=source_lang,
                    target=target,
                    target_lang=tl,
                    position=position,
                )
            )
    return result
