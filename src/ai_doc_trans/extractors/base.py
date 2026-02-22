from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator

from ai_doc_trans.models import Segment


class BaseExtractor(ABC):
    """Abstract base class for document extractors."""

    @abstractmethod
    def extract(self, path: Path) -> Iterator[Segment]:
        """Yield segments from the document at *path*."""
