"""Development SMS provider. Sends NOTHING; records the message as 'simulated'.

To exercise the failure/retry path in development, any phone number ending in "000"
is treated as a delivery failure.
"""
import logging
import uuid

from app.integrations.sms.base import SendResult, SmsProvider

log = logging.getLogger("sms.mock")


class MockSmsProvider(SmsProvider):
    name = "mock"

    def send(self, phone: str, body: str) -> SendResult:
        if phone.endswith("000"):
            return SendResult(ok=False, status="failed", error="Simulated failure (number ends in 000)")
        log.info("SIMULATED SMS to %s: %s", phone, body)
        return SendResult(ok=True, status="simulated", provider_message_id=f"mock-{uuid.uuid4().hex[:12]}")


def get_provider(name: str) -> SmsProvider:
    if name == "mock":
        return MockSmsProvider()
    raise ValueError(f"SMS provider '{name}' is not configured. Only 'mock' is implemented; "
                     "add an adapter in app/integrations/sms/ using the provider's documented API.")
