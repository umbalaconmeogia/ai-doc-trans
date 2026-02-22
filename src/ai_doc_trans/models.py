from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Segment:
    """A unit of text extracted from a document for translation."""
    source: str
    structure: str
    source_lang: str
    source_hash: str
    source_id: int
    position: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "structure": self.structure,
            "source_lang": self.source_lang,
            "source_hash": self.source_hash,
            "source_id": self.source_id,
            "position": self.position,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Segment":
        return cls(
            source=d["source"],
            structure=d["structure"],
            source_lang=d["source_lang"],
            source_hash=d["source_hash"],
            source_id=d["source_id"],
            position=d.get("position"),
        )


@dataclass
class TranslatedSegment:
    """A segment paired with its translation (self-contained for import)."""
    source: str
    source_hash: str
    source_id: int
    structure: str
    source_lang: str
    target: str  # Required; must come before optional fields
    target_lang: Optional[str] = None  # Required in new files; legacy files use --tgt
    position: Optional[str] = None

    def to_dict(self) -> dict:
        out = {
            "source": self.source,
            "source_hash": self.source_hash,
            "source_id": self.source_id,
            "structure": self.structure,
            "source_lang": self.source_lang,
            "position": self.position,
            "target": self.target,
        }
        if self.target_lang is not None:
            out["target_lang"] = self.target_lang
        return out

    @classmethod
    def from_dict(cls, d: dict) -> "TranslatedSegment":
        return cls(
            source=d["source"],
            source_hash=d["source_hash"],
            source_id=d.get("source_id", 0),  # 0 unused when resolving via hash
            structure=d.get("structure", "cell"),
            source_lang=d.get("source_lang", "en"),
            target_lang=d.get("target_lang"),
            target=d.get("target", ""),  # empty = source-only (no translation)
            position=d.get("position"),
        )

    @classmethod
    def from_segment(cls, seg: Segment, target: str, target_lang: str) -> "TranslatedSegment":
        return cls(
            source=seg.source,
            source_hash=seg.source_hash,
            source_id=seg.source_id,
            structure=seg.structure,
            source_lang=seg.source_lang,
            target_lang=target_lang,
            target=target,
            position=seg.position,
        )
