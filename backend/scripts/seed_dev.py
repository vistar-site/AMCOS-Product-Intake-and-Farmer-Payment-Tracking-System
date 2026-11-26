"""DEVELOPMENT ONLY: create a demo AMCOS with centres, crops, users and farmers.

    python -m scripts.seed_dev

- Refuses to run when ENVIRONMENT=production.
- Everything belongs to an organization flagged is_demo=true (code "DEMO"),
  so demo data is always distinguishable from real cooperative data.
- Demo user password: DEV_SEED_PASSWORD env var if set, else a random one printed once.
- Running it twice does nothing the second time.
Deliveries, batches, auctions and payouts are added to this script in the phases
that create those tables.
"""
import os
import secrets
import sys
from datetime import date

from sqlalchemy import select

from backend.app.database.core.config import get_settings
from backend.app.database.core.security import hash_password
from app.database.session import SessionLocal
from app.models import CollectionCentre, Crop, CropGrade, Farmer, Organization, Role, Season, User, Warehouse
from scripts.bootstrap import sync_roles_and_permissions

CENTRES = [
    ("MTW-01", "Nanyamba Collection Centre", "Nanyamba", "Nanyamba", "Mtwara Rural", "Mtwara"),
    ("MTW-02", "Mahurunga Collection Centre", "Mahurunga", "Mahurunga", "Mtwara Rural", "Mtwara"),
    ("MTW-03", "Ziwani Collection Centre", "Ziwani", "Ziwani", "Mtwara Rural", "Mtwara"),
]
CROPS = [
    ("CASHEW", "Cashew nuts", [("STD", "Standard grade"), ("UG", "Under grade")]),
    ("COTTON", "Cotton", [("A", "Grade A"), ("B", "Grade B")]),
    ("COFFEE", "Coffee", [("AA", "Grade AA"), ("AB", "Grade AB"), ("PB", "Peaberry")]),
    ("SESAME", "Sesame", [("W", "White"), ("M", "Mixed")]),
]
USERS = [  # (email prefix, name, role, centre codes)
    ("manager", "Asha Mwinyi", "manager", []),
    ("clerk1", "Juma Hassan", "clerk", ["MTW-01"]),
    ("clerk2", "Neema Salum", "clerk", ["MTW-02", "MTW-03"]),
    ("accountant", "Peter Komba", "accountant", []),
    ("warehouse", "Rehema Ally", "warehouse_officer", []),
    ("auditor", "Daudi Mrisho", "auditor", []),
]
FARMERS = [  # (name, gender, village, centre index)
    ("Mohamedi Saidi Mkwawa", "male", "Nanyamba", 0), ("Fatuma Abdallah Nnauye", "female", "Nanyamba", 0),
    ("Hamisi Rashidi Chilumba", "male", "Nanyamba", 0), ("Zainabu Omari Libaba", "female", "Mtiniko", 0),
    ("Bakari Issa Namkuku", "male", "Mahurunga", 1), ("Mwanaidi Selemani Kiputa", "female", "Mahurunga", 1),
    ("Rajabu Musa Lyimo", "male", "Kitaya", 1), ("Halima Juma Mpanda", "female", "Kitaya", 1),
    ("Shabani Athumani Ngoma", "male", "Ziwani", 2), ("Mariamu Hassani Mtumbo", "female", "Ziwani", 2),
    ("Yusufu Ramadhani Chande", "male", "Msangamkuu", 2), ("Amina Kassim Mpwapwa", "female", "Msangamkuu", 2),
]


def main() -> None:
    if get_settings().environment == "production":
        sys.exit("Refusing to seed demo data in production.")

    password = os.environ.get("DEV_SEED_PASSWORD") or secrets.token_urlsafe(9) + "7a"

    with SessionLocal() as db, db.begin():
        sync_roles_and_permissions(db)
        if db.scalar(select(Organization).where(Organization.code == "DEMO")):
            print("Demo data already present; nothing to do.")
            return

        org = Organization(name="Demo Mtwara AMCOS Ltd (DEMONSTRATION DATA)", code="DEMO",
                           registration_no="DEMO-REG-0001", region="Mtwara", district="Mtwara Rural",
                           is_demo=True)
        db.add(org)
        db.flush()

        centres = [CollectionCentre(organization_id=org.id, code=c, name=n, village=v, ward=w,
                                    district=d, region=r) for c, n, v, w, d, r in CENTRES]
        db.add_all(centres)
        for code, name, grades in CROPS:
            db.add(Crop(organization_id=org.id, code=code, name=name,
                        rules={"max_gross_kg": 1000},
                        grades=[CropGrade(code=g, name=gn) for g, gn in grades]))
        db.add(Season(organization_id=org.id, name="2026/27", start_date=date(2026, 10, 1),
                      end_date=date(2027, 9, 30)))
        db.add(Warehouse(organization_id=org.id, code="WH-MTW", name="Demo Mtwara Bonded Warehouse",
                         operator_name="Demo Warehouse Operator", location="Mtwara Town"))

        roles = {r.code: r for r in db.scalars(select(Role))}
        by_code = {c.code: c for c in centres}
        pw_hash = hash_password(password)
        for prefix, name, role, centre_codes in USERS:
            db.add(User(organization_id=org.id, email=f"{prefix}@demo.amcos.test", full_name=name,
                        password_hash=pw_hash, roles=[roles[role]],
                        centres=[by_code[c] for c in centre_codes]))

        for i, (name, gender, village, ci) in enumerate(FARMERS, start=1):
            db.add(Farmer(organization_id=org.id, membership_no=f"DEMO-{i:04d}", full_name=name,
                          gender=gender, village=village, ward=centres[ci].ward,
                          district="Mtwara Rural", region="Mtwara", home_centre_id=centres[ci].id,
                          phone=f"+2557000000{i:02d}", mobile_money_number=f"+2557000000{i:02d}"))

    print("Demo data created (organization code DEMO).")
    print("Users:", ", ".join(f"{u[0]}@demo.amcos.test" for u in USERS))
    print(f"Password for all demo users: {password}")


if __name__ == "__main__":
    main()
