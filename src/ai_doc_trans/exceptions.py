"""Custom exceptions for ai-doc-trans."""

from __future__ import annotations


class MissingTranslationsError(Exception):
    """Raised when rebuild finds segments that need translation but are not in TM."""

    def __init__(self, missing: list[tuple[str, str]]) -> None:
        self.missing = missing
        lines = [
            f"  {position}: {text!r}"
            for position, text in missing
        ]
        msg = (
            f"{len(missing)} segment(s) have no translation in TM:\n"
            + "\n".join(lines)
        )
        super().__init__(msg)
