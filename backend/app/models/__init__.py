"""Import every model here so Base.metadata knows the full schema (Alembic relies on this)."""
from app.models.farmer import Farmer
from app.models.organization import Organization
from app.models.reference import CollectionCentre, Crop, CropGrade, Season, Warehouse
from app.models.system import AuditLog, NumberSequence, Setting
from app.models.user import Permission, RefreshToken, Role, User

__all__ = [
    "AuditLog", "CollectionCentre", "Crop", "CropGrade", "Farmer", "NumberSequence",
    "Organization", "Permission", "RefreshToken", "Role", "Season", "Setting", "User", "Warehouse",
]
