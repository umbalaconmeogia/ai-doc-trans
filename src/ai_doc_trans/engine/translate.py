from __future__ import annotations

from pathlib import Path
from typing import Optional

from ai_doc_trans.engine.glossary import GlossaryLoader
from ai_doc_trans.engine.tm import TM
from ai_doc_trans.engine.translator import Translator
from ai_doc_trans.models import Segment, TranslatedSegment


def run_translate(
    segments: list[Segment],
    target_lang: str,
    tm: TM,
    project_id: int,
    mode: str = "full",
    batch_size: int = 50,
    glossary_path: Optional[Path] = None,
    rules_path: Optional[Path] = None,
) -> list[TranslatedSegment]:
    """
    Translate segments and return TranslatedSegment list.

    mode='full'   : translate all via AI, ignore TM.
    mode='update' : reuse TM translations where available; call AI for the rest.
    """
    glossary_loader = GlossaryLoader(
        tm=tm,
        project_id=project_id,
        glossary_path=glossary_path,
        rules_path=rules_path,
    )
    system_prompt = glossary_loader.build_system_prompt(
        # Use the source_lang from the first segment as document-level lang
        source_lang=segments[0].source_lang if segments else "en",
        target_lang=target_lang,
    )
    translator = Translator(system_prompt=system_prompt)

    if mode == "full":
        return _translate_full(segments, target_lang, translator, batch_size)
    if mode == "update":
        return _translate_update(segments, target_lang, tm, project_id, translator, batch_size)
    raise ValueError(f"Unknown translate mode: {mode!r}. Use 'full' or 'update'.")


def _translate_full(
    segments: list[Segment],
    target_lang: str,
    translator: Translator,
    batch_size: int,
) -> list[TranslatedSegment]:
    translations = translator.translate_all(segments, target_lang, batch_size)
    return [
        TranslatedSegment.from_segment(seg, trans, target_lang)
        for seg, trans in zip(segments, translations)
    ]


def _translate_update(
    segments: list[Segment],
    target_lang: str,
    tm: TM,
    project_id: int,
    translator: Translator,
    batch_size: int,
) -> list[TranslatedSegment]:
    results: list[TranslatedSegment | None] = [None] * len(segments)
    to_translate_indices: list[int] = []
    to_translate_segments: list[Segment] = []

    for i, seg in enumerate(segments):
        cached = tm.get_target(seg.source_id, target_lang)
        if cached is not None:
            results[i] = TranslatedSegment.from_segment(seg, cached, target_lang)
        else:
            to_translate_indices.append(i)
            to_translate_segments.append(seg)

    if to_translate_segments:
        translations = translator.translate_all(
            to_translate_segments, target_lang, batch_size
        )
        for idx, seg, trans in zip(to_translate_indices, to_translate_segments, translations):
            results[idx] = TranslatedSegment.from_segment(seg, trans, target_lang)

    return [r for r in results if r is not None]
