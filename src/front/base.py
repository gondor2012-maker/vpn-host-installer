"""
Abstract base for frontends (CDN or shared hosting).
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class Front(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.cfg = config

    @abstractmethod
    def setup(self) -> bool:
        """Setup frontend, return True on success."""
        pass

    @abstractmethod
    def verify(self) -> bool:
        """Verify frontend is working."""
        pass

    @abstractmethod
    def instructions(self) -> str:
        """Return setup instructions for manual steps."""
        pass
