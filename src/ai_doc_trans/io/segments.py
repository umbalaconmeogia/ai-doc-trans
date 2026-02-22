from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from ai_doc_trans.models import Segment, TranslatedSegment


def load_segments(path: Union[str, Path]) -> list[Segment]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [Segment.from_dict(d) for d in data]


def save_segments(segments: list[Segment], path: Union[str, Path]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([s.to_dict() for s in segments], f, ensure_ascii=False, indent=2)


def load_translated_segments(path: Union[str, Path]) -> list[TranslatedSegment]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [TranslatedSegment.from_dict(d) for d in data]


def save_translated_segments(
    segments: list[TranslatedSegment], path: Union[str, Path]
) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([s.to_dict() for s in segments], f, ensure_ascii=False, indent=2)
