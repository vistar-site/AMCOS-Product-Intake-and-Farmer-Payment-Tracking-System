"""Import every model here so Base.metadata knows the full schema (Alembic relies on this)."""
from app.models.delivery import Delivery, DeliveryAmendment, SyncLog
from app.models.farmer import Farmer
from app.models.finance import (
    DeductionType, FarmerPayout, InputLoan, LoanRepayment, Payment, PaymentBatch, PayoutLine, PayoutRun,
    PayoutRunAllocation,
)
from app.models.notification import SmsMessage, SmsTemplate
from app.models.organization import Organization
from app.models.reference import CollectionCentre, Crop, CropGrade, Season, Warehouse
from app.models.system import AuditLog, NumberSequence, Setting
from app.models.user import Permission, RefreshToken, Role, User
from app.models.warehouse import (
    AggregationBatch, Auction, AuctionLot, BatchDelivery, Discrepancy, DispatchBatch, LotAllocation,
    WarehouseDispatch, WarehouseReceipt, WarehouseReceiptLine,
)

__all__ = [
    "SmsMessage", "SmsTemplate",
    "DeductionType", "FarmerPayout", "InputLoan", "LoanRepayment", "Payment", "PaymentBatch", "PayoutLine",
    "PayoutRun", "PayoutRunAllocation",
    "AggregationBatch", "Auction", "AuctionLot", "BatchDelivery", "Discrepancy", "DispatchBatch",
    "LotAllocation", "WarehouseDispatch", "WarehouseReceipt", "WarehouseReceiptLine",
    "AuditLog", "CollectionCentre", "Delivery", "DeliveryAmendment", "SyncLog", "Crop", "CropGrade", "Farmer", "NumberSequence",
    "Organization", "Permission", "RefreshToken", "Role", "Season", "Setting", "User", "Warehouse",
]
