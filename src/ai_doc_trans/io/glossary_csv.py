"""Load glossary and rules from CSV files (same format as export)."""
from __future__ import annotations

import csv
from pathlib import Path

def load_glossary_from_csv(
    path: Path,
    source_lang: str,
    target_lang: str,
) -> list[tuple[str, str]]:
    """
    Load glossary from CSV and return list of (term, translation).
    Filters by source_lang and target_lang (empty target_lang in CSV = apply to all).
    """
    result: list[tuple[str, str]] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_sl = (row.get("source_lang") or "").strip()
            row_tl = (row.get("target_lang") or "").strip()
            if row_sl != source_lang:
                continue
            if row_tl and row_tl != target_lang:
                continue
            term = (row.get("term") or "").strip()
            translation = (row.get("translation") or "").strip()
            if term and translation:
                result.append((term, translation))
    return result


def load_rules_from_csv(
    path: Path,
) -> tuple[list[str], list[str]]:
    """
    Load translation rules from CSV.
    Returns (instructions, skip_patterns).
    """
    instructions: list[str] = []
    skip_patterns: list[str] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rule_type = (row.get("rule_type") or "").strip()
            content = (row.get("content") or "").strip()
            if not content:
                continue
            if rule_type == "instruction":
                instructions.append(content)
            elif rule_type == "do_not_translate_pattern":
                skip_patterns.append(content)
    return (instructions, skip_patterns)
