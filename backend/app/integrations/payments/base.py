"""Payment channel adapter interface.

Today the only implementation produces FILES (CSV / Excel) that a finance officer uploads
to the bank or mobile-money portal by hand. Nothing is sent anywhere automatically, and an
exported payment is NEVER marked as paid — results are reconciled manually afterwards.

A future real integration (a bank API or mobile-money B2C API) would implement the same
interface using the provider's actual, verified specification; business logic stays unchanged.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PaymentInstruction:
    payment_id: str
    farmer_name: str
    membership_no: str
    destination: str            # phone (mobile money) or account number (bank)
    destination_bank: str | None
    amount: Decimal
    reference: str              # shown to the farmer / on the bank statement


class PaymentExporter(ABC):
    method: str
    file_extension: str
    media_type: str

    @abstractmethod
    def render(self, batch_no: str, currency: str, instructions: list[PaymentInstruction]) -> bytes: ...
