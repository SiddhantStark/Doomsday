"""Interface for later live provider implementations."""

from typing import Protocol

from .config import Target
from .models import ProviderResult


class TicketProvider(Protocol):
    def check_availability(self, target: Target) -> ProviderResult:
        """Return a normalized result, distinguishing failures from absence."""
        ...
