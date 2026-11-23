"""SMS provider adapter interface.

Business code calls notification_service, never a provider directly. Swapping the SMS
gateway means writing one class with this interface, using the provider's real,
verified API documentation and credentials — nothing else changes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SendResult:
    ok: bool
    status: str                  # 'sent' | 'simulated' | 'failed'
    provider_message_id: str | None = None
    error: str | None = None
    retryable: bool = True


class SmsProvider(ABC):
    name: str

    @abstractmethod
    def send(self, phone: str, body: str) -> SendResult: ...
