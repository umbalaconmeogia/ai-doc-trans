from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterator, Optional

import openpyxl

from ai_doc_trans.engine.tm import TM
from ai_doc_trans.extractors.base import BaseExtractor
from ai_doc_trans.models import Segment


def _compute_hash(structure: str, source_text: str) -> str:
    payload = (structure + source_text).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_text_cell(cell) -> bool:
    """Return True only for cells with actual string content."""
    if cell.value is None:
        return False
    # data_type 's' = string; also accept plain Python str values
    if cell.data_type == "s" or isinstance(cell.value, str):
        return bool(str(cell.value).strip())
    return False


class ExcelExtractor(BaseExtractor):
    """Extract text segments from .xlsx files."""

    def __init__(
        self,
        tm: TM,
        source_lang: str = "en",
        project_id: int = 1,
        tag_open: str = "{",
        tag_close: str = "}",
    ) -> None:
        self.tm = tm
        self.source_lang = source_lang
        self.project_id = project_id
        self.tag_open = tag_open
        self.tag_close = tag_close
        self._skip_patterns: Optional[list[re.Pattern]] = None

    def _get_skip_patterns(self) -> list[re.Pattern]:
        if self._skip_patterns is None:
            rules = self.tm.get_translation_rules(self.project_id)
            self._skip_patterns = [
                re.compile(content)
                for rule_type, content in rules
                if rule_type == "do_not_translate_pattern"
            ]
        return self._skip_patterns

    def _should_skip(self, text: str) -> bool:
        return any(p.search(text) for p in self._get_skip_patterns())

    def extract(self, path: Path) -> Iterator[Segment]:
        wb = openpyxl.load_workbook(str(path), data_only=True)
        for sheet in wb.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if not _is_text_cell(cell):
                        continue
                    text = str(cell.value).strip()
                    if self._should_skip(text):
                        continue
                    structure = "cell"
                    source_hash = _compute_hash(structure, text)
                    position = f"{sheet.title}!{cell.coordinate}"
                    source_id = self.tm.get_or_create_source(
                        source_hash=source_hash,
                        source_text=text,
                        source_lang=self.source_lang,
                        structure=structure,
                        position=position,
                    )
                    yield Segment(
                        source=text,
                        structure=structure,
                        source_lang=self.source_lang,
                        source_hash=source_hash,
                        source_id=source_id,
                        position=position,
                    )
