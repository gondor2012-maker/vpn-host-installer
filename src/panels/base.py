"""
Abstract base class for VPN panels.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from ..core.state import InstallState


class Panel(ABC):
    def __init__(self, config: Dict[str, Any], state: InstallState):
        self.cfg = config
        self.state = state

    @abstractmethod
    def install(self) -> None:
        """Install panel on this server."""
        pass

    @abstractmethod
    def create_inbound(self, node_ip: str, xray_port: int, path: str, client_uuid: str) -> str:
        """Create inbound and return subscription URL."""
        pass

    @abstractmethod
    def get_credentials(self) -> Dict[str, str]:
        """Return panel access credentials."""
        pass
