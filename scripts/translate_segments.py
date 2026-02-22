#!/usr/bin/env python3
"""
Translate segments.json from Vietnamese to English.
Uses glossary, rules, and deep-translator. Output: translated.json
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Vietnamese month name -> English
VI_MONTHS = {
    "1": "January", "2": "February", "3": "March", "4": "April",
    "5": "May", "6": "June", "7": "July", "8": "August",
    "9": "September", "10": "October", "11": "November", "12": "December",
}


def load_glossary(path: Path, target_lang: str = "en") -> dict[str, str]:
    """Load glossary: term (vi) -> translation (en). Sorted by len desc for replacement."""
    result: dict[str, str] = {}
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            term = (row.get("term") or "").strip()
            trans = (row.get("translation") or "").strip()
            row_tl = (row.get("target_lang") or "").strip()
            if not term:
                continue
            if row_tl and row_tl != target_lang:
                continue
            result[term] = trans if trans else term  # keep as-is if empty
    return result


def load_skip_patterns(path: Path) -> list[str]:
    """Load do_not_translate_pattern from rules CSV."""
    patterns: list[str] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("rule_type") or "").strip() == "do_not_translate_pattern":
                content = (row.get("content") or "").strip()
                if content:
                    patterns.append(content)
    return patterns


def apply_date_format(text: str) -> str:
    """Tháng 3-5/2026 -> March-May 2026, Tháng 8-9/2026 -> August-September 2026"""
    # Tháng X-Y/YYYY or Tháng X-Y /YYYY
    m = re.match(r"^Tháng\s+(\d+)\s*-\s*(\d+)\s*/?\s*(\d{4})\s*$", text.strip())
    if m:
        a, b, year = m.groups()
        ma = VI_MONTHS.get(a, a)
        mb = VI_MONTHS.get(b, b)
        return f"{ma}-{mb} {year}"
    return text


def apply_glossary_pre(text: str, glossary: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Replace glossary terms with placeholders. Returns (text, placeholder->translation)."""
    placeholders: dict[str, str] = {}
    out = text
    for i, (term, trans) in enumerate(sorted(glossary.items(), key=lambda x: -len(x[0]))):
        ph = f"__G{i}__"
        placeholders[ph] = trans
        pat = re.escape(term)
        out = re.sub(pat, ph, out, flags=re.IGNORECASE)
    return out, placeholders


def apply_glossary_post(text: str, placeholders: dict[str, str]) -> str:
    """Replace placeholders with glossary translations."""
    out = text
    for ph, trans in placeholders.items():
        out = out.replace(ph, trans)
    return out


def should_skip_translate(source: str, skip_patterns: list[str]) -> bool:
    """Return True if source should not be translated (keep as-is)."""
    s = source.strip()
    if not s:
        return True
    # Pure number
    if re.match(r"^[\d.,\s\-+%]+$", s):
        return True
    for pat in skip_patterns:
        if re.match(pat + r"$", s):
            return True
    return False


def translate_batch(
    segments: list[dict],
    glossary: dict[str, str],
    skip_patterns: list[str],
    target_lang: str = "en",
) -> list[dict]:
    """Translate a batch of segments using deep_translator."""
    from deep_translator import GoogleTranslator

    translator = GoogleTranslator(source="vi", target="en")
    result: list[dict] = []

    for seg in segments:
        src = seg.get("source", "")
        out = {**seg, "target_lang": target_lang}

        if should_skip_translate(src, skip_patterns):
            out["target"] = src
            result.append(out)
            continue

        # 1. Date format first
        txt = apply_date_format(src)
        # 2. Replace glossary terms with placeholders (to preserve exact translations)
        txt, ph_map = apply_glossary_pre(txt, glossary)

        try:
            translated = translator.translate(txt)
            translated = translated or txt
            # 3. Restore glossary terms from placeholders
            out["target"] = apply_glossary_post(translated, ph_map)
        except Exception:
            out["target"] = apply_glossary_post(txt, ph_map)
        result.append(out)
        time.sleep(0.05)  # Rate limit (reduced for speed)

    return result


def main() -> None:
    segments_path = ROOT / "segments.json"
    glossary_path = ROOT / "docs" / "sample" / "glossary_global.csv"
    rules_path = ROOT / "docs" / "sample" / "rules_global.csv"
    output_path = ROOT / "translated.json"

    with open(segments_path, encoding="utf-8") as f:
        segments = json.load(f)

    glossary = load_glossary(glossary_path)
    skip_patterns = load_skip_patterns(rules_path)

    print(f"Loaded {len(segments)} segments, {len(glossary)} glossary terms, {len(skip_patterns)} skip patterns")
    print("Translating in batches of 100...")

    batch_size = 100
    all_translated: list[dict] = []
    for i in range(0, len(segments), batch_size):
        batch = segments[i : i + batch_size]
        translated = translate_batch(batch, glossary, skip_patterns)
        all_translated.extend(translated)
        print(f"  Batch {i // batch_size + 1}: {len(translated)} segments")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_translated, f, ensure_ascii=False, indent=2)

    print(f"Done. Wrote {output_path}")


if __name__ == "__main__":
    main()
