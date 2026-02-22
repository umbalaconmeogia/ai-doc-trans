from __future__ import annotations

import logging
import re
from pathlib import Path

import openpyxl

from ai_doc_trans.engine.tm import TM
from ai_doc_trans.exceptions import MissingTranslationsError
from ai_doc_trans.hash_utils import compute_source_hash
from ai_doc_trans.rebuilders.base import BaseRebuilder

logger = logging.getLogger(__name__)


def _is_text_cell(cell) -> bool:
    if cell.value is None:
        return False
    if cell.data_type == "s" or isinstance(cell.value, str):
        return bool(str(cell.value).strip())
    return False


class ExcelRebuilder(BaseRebuilder):
    """
    Rebuild a translated Excel file.

    Re-extracts the source workbook, looks up each text cell's hash in the TM,
    and replaces the cell value with the target translation.
    Only cell.value is updated; all formatting is preserved.
    """

    def __init__(
        self,
        tm: TM,
        target_lang: str,
        project_id: int = 1,
    ) -> None:
        self.tm = tm
        self.target_lang = target_lang
        self.project_id = project_id
        self._skip_patterns: list[re.Pattern] | None = None

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

    def rebuild(self, source_path: Path, output_path: Path) -> int:
        wb = openpyxl.load_workbook(str(source_path), data_only=True)
        replaced = 0
        missing_list: list[tuple[str, str]] = []

        for sheet in wb.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if not _is_text_cell(cell):
                        continue
                    text = str(cell.value).strip()
                    if self._should_skip(text):
                        continue

                    structure = "cell"
                    source_hash = compute_source_hash(text)
                    target_text = self.tm.get_target_by_hash(
                        source_hash, self.target_lang, self.project_id
                    )
                    if target_text is not None:
                        cell.value = target_text
                        replaced += 1
                    else:
                        position = f"{sheet.title}!{cell.coordinate}"
                        missing_list.append((position, text))

        if missing_list:
            raise MissingTranslationsError(missing_list)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(output_path))
        logger.info("Rebuild complete: %d cells replaced", replaced)
        return replaced
