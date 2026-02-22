from __future__ import annotations

from pathlib import Path
from typing import Optional

from ai_doc_trans.engine.tm import TM
from ai_doc_trans.io.glossary_csv import load_glossary_from_csv, load_rules_from_csv


class GlossaryLoader:
    """Loads glossary terms and translation rules from TM DB or CSV files."""

    def __init__(
        self,
        tm: Optional[TM] = None,
        project_id: int = 1,
        glossary_path: Optional[Path] = None,
        rules_path: Optional[Path] = None,
    ) -> None:
        self.tm = tm
        self.project_id = project_id
        self.glossary_path = glossary_path
        self.rules_path = rules_path
        self._cached_instructions: Optional[list[str]] = None
        self._cached_skip_patterns: Optional[list[str]] = None

    def get_glossary(
        self, source_lang: str, target_lang: str
    ) -> list[tuple[str, str]]:
        """Return list of (term, translation)."""
        if self.glossary_path is not None:
            return load_glossary_from_csv(
                self.glossary_path, source_lang, target_lang
            )
        if self.tm is not None:
            return self.tm.get_glossary(source_lang, target_lang, self.project_id)
        return []

    def get_instructions(self) -> list[str]:
        """Return AI instruction strings (rule_type=instruction)."""
        if self.rules_path is not None:
            if self._cached_instructions is None:
                self._cached_instructions, self._cached_skip_patterns = (
                    load_rules_from_csv(self.rules_path)
                )
            return self._cached_instructions
        if self.tm is not None:
            rules = self.tm.get_translation_rules(self.project_id)
            return [c for rt, c in rules if rt == "instruction"]
        return []

    def get_skip_patterns(self) -> list[str]:
        """Return do-not-translate regex patterns."""
        if self.rules_path is not None:
            if self._cached_skip_patterns is None:
                self._cached_instructions, self._cached_skip_patterns = (
                    load_rules_from_csv(self.rules_path)
                )
            return self._cached_skip_patterns
        if self.tm is not None:
            rules = self.tm.get_translation_rules(self.project_id)
            return [c for rt, c in rules if rt == "do_not_translate_pattern"]
        return []

    def build_system_prompt(
        self, source_lang: str, target_lang: str
    ) -> str:
        parts = [
            f"You are a professional technical document translator. "
            f"Translate from {source_lang} to {target_lang}. "
            "Output only the translated text. Do not add explanations.",
        ]
        instructions = self.get_instructions()
        if instructions:
            parts.append("Additional instructions:")
            parts.extend(f"- {i}" for i in instructions)
        glossary = self.get_glossary(source_lang, target_lang)
        if glossary:
            parts.append("Use the following terminology consistently:")
            parts.extend(f"- {term} → {translation}" for term, translation in glossary)
        skip_patterns = self.get_skip_patterns()
        if skip_patterns:
            parts.append(
                "Do NOT translate text matching these patterns (keep verbatim): "
                + ", ".join(skip_patterns)
            )
        return "\n".join(parts)
