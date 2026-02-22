from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseRebuilder(ABC):
    """Abstract base class for document rebuilders."""

    @abstractmethod
    def rebuild(self, source_path: Path, output_path: Path) -> int:
        """
        Re-extract source, look up translations in TM, write output.
        Returns number of cells replaced.
        """
