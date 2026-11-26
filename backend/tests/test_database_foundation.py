"""Database integrity tests: prove the constraints actually protect the data."""
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from backend.app.database.core.permissions import ROLES
from app.models import AuditLog, CollectionCentre, Farmer, Organization, Role, Season, User


def make_org(db, code="TST"):
    org = Organization(name=f"Test AMCOS {code}", code=code)
    db.add(org)
    db.flush()
    return org


def test_membership_no_unique_within_one_amcos(db):
    org = make_org(db)
    db.add(Farmer(organization_id=org.id, membership_no="M-1", full_name="A"))
    db.flush()
    db.add(Farmer(organization_id=org.id, membership_no="M-1", full_name="B"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_same_membership_no_allowed_in_different_amcos(db):
    a, b = make_org(db, "TA"), make_org(db, "TB")
    db.add_all([Farmer(organization_id=a.id, membership_no="M-1", full_name="A"),
                Farmer(organization_id=b.id, membership_no="M-1", full_name="B")])
    db.flush()  # no error


def test_invalid_farmer_status_rejected_by_check_constraint(db):
    org = make_org(db)
    db.add(Farmer(organization_id=org.id, membership_no="M-2", full_name="X", status="deleted"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_season_end_before_start_rejected(db):
    org = make_org(db)
    db.add(Season(organization_id=org.id, name="bad", start_date=date(2027, 1, 1), end_date=date(2026, 1, 1)))
    with pytest.raises(IntegrityError):
        db.flush()


def test_cannot_delete_organization_that_has_farmers(db):
    org = make_org(db)
    db.add(Farmer(organization_id=org.id, membership_no="M-3", full_name="Y"))
    db.flush()
    with pytest.raises(IntegrityError):  # ON DELETE RESTRICT
        db.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org.id})


def test_user_centre_relationship(db):
    org = make_org(db)
    centre = CollectionCentre(organization_id=org.id, code="C1", name="Centre 1")
    user = User(organization_id=org.id, email="t@x.test", full_name="T", password_hash="x", centres=[centre])
    db.add(user)
    db.flush()
    assert centre.users == [user]


def test_audit_log_is_append_only(db):
    db.add(AuditLog(action="test.event"))
    db.flush()
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("UPDATE audit_logs SET action = 'tampered'"))


def test_seeded_roles_match_catalogue(db):
    codes = set(db.scalars(select(Role.code)))
    assert set(ROLES) <= codes


def test_clerk_cannot_approve_payments_or_change_auctions(db):
    clerk = db.scalar(select(Role).where(Role.code == "clerk"))
    perms = {p.code for p in clerk.permissions}
    assert "delivery.create" in perms
    assert not perms & {"auction.manage", "payout.approve", "payment_batch.approve"}
