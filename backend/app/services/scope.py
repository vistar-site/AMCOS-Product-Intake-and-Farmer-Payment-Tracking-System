"""Data-scoping helpers shared by services.

Two layers of restriction beyond permissions:
1. Organization: users only touch rows of their own AMCOS.
2. Centre: a user who is assigned to specific centres and cannot manage centres
   (i.e. a clerk) only works with those centres.
"""
import uuid

from app.core.exceptions import PermissionDeniedError
from app.models import User


def org_id(user: User) -> uuid.UUID:
    if user.organization_id is None:
        raise PermissionDeniedError("This action requires a user that belongs to an AMCOS")
    return user.organization_id


def restricted_centre_ids(user: User) -> set[uuid.UUID] | None:
    """None = may use every centre of the organization."""
    if "centre.manage" in user.permission_codes or not user.centres:
        return None
    return {c.id for c in user.centres}


def ensure_centre_allowed(user: User, centre_id: uuid.UUID) -> None:
    allowed = restricted_centre_ids(user)
    if allowed is not None and centre_id not in allowed:
        raise PermissionDeniedError("You are not assigned to this collection centre")
