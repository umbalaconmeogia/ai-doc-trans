from __future__ import annotations

import os
from typing import Optional

from ai_doc_trans.models import Segment


class Translator:
    """
    Translates segments using an AI API or a placeholder.

    Set DOCTRANS_AI_BACKEND env var to choose backend:
      - "placeholder" (default): returns source text unchanged (for PoC flow validation)
      - "openai": uses OpenAI Chat Completions API (requires OPENAI_API_KEY)

    Set DOCTRANS_AI_MODEL to override the model name.
    """

    def __init__(self, system_prompt: str = "") -> None:
        self.system_prompt = system_prompt
        self.backend = os.environ.get("DOCTRANS_AI_BACKEND", "placeholder").lower()
        self.model = os.environ.get("DOCTRANS_AI_MODEL", "gpt-4o-mini")

    def translate_batch(
        self, segments: list[Segment], target_lang: str
    ) -> list[str]:
        """Translate a batch of segments. Returns list of translated strings."""
        if self.backend == "placeholder":
            return self._placeholder_batch(segments)
        if self.backend == "openai":
            return self._openai_batch(segments, target_lang)
        raise ValueError(f"Unknown AI backend: {self.backend!r}")

    def translate_all(
        self,
        segments: list[Segment],
        target_lang: str,
        batch_size: int = 50,
    ) -> list[str]:
        """Translate all segments in batches, return results in original order."""
        results: list[str] = []
        for i in range(0, len(segments), batch_size):
            batch = segments[i : i + batch_size]
            results.extend(self.translate_batch(batch, target_lang))
        return results

    # ------------------------------------------------------------------
    # Backends
    # ------------------------------------------------------------------

    def _placeholder_batch(self, segments: list[Segment]) -> list[str]:
        """Return source text unchanged (for validating the overall flow)."""
        return [seg.source for seg in segments]

    def _openai_batch(self, segments: list[Segment], target_lang: str) -> list[str]:
        try:
            import openai  # type: ignore
        except ImportError as e:
            raise ImportError(
                "openai package is required for the openai backend. "
                "Install it with: pip install openai"
            ) from e

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY environment variable is not set.")

        client = openai.OpenAI(api_key=api_key)

        numbered = "\n".join(
            f"{i + 1}. {seg.source}" for i, seg in enumerate(segments)
        )
        user_prompt = (
            f"Translate each numbered line to {target_lang}. "
            "Return only the numbered translations, one per line, same numbering.\n\n"
            + numbered
        )

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content or ""
        return self._parse_numbered_response(raw, len(segments))

    @staticmethod
    def _parse_numbered_response(raw: str, expected: int) -> list[str]:
        """Parse '1. text\n2. text\n...' response into a list of strings."""
        lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
        results: list[str] = []
        for line in lines:
            if line and line[0].isdigit() and ". " in line:
                _, _, text = line.partition(". ")
                results.append(text.strip())
        if len(results) != expected:
            # Fallback: return raw lines if parsing fails
            results = lines[:expected]
            while len(results) < expected:
                results.append("")
        return results
