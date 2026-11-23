"""Catalogue of permission codes and the default roles that bundle them.

The backend always checks a *permission* ("payment_batch.approve"), never a role
name. Administrators can later change which permissions a role has without code
changes; this file only defines the starting point, synced by scripts/bootstrap.py.
"""

PERMISSIONS: dict[str, str] = {
    # Administration
    "organization.manage": "Create and edit AMCOS organizations",
    "user.view": "View users",
    "user.manage": "Create, edit, activate and deactivate users",
    "role.manage": "Manage roles and permissions",
    "settings.manage": "Change system and AMCOS settings",
    "audit.view": "View audit trail",
    # Reference data
    "centre.view": "View collection centres",
    "centre.manage": "Create and edit collection centres, assign staff",
    "crop.view": "View crops and seasons",
    "crop.manage": "Configure crops, grades and seasons",
    "warehouse.manage": "Register warehouses",
    # Farmers
    "farmer.view": "View farmers",
    "farmer.create": "Register farmers",
    "farmer.update": "Edit farmer details and status",
    "farmer.view_financial": "View farmer payment details and balances",
    # Deliveries
    "delivery.view": "View deliveries",
    "delivery.create": "Record produce deliveries",
    "delivery.amend_request": "Request a correction to a delivery",
    "delivery.amend_approve": "Approve delivery corrections and voids",
    # Warehouse
    "batch.manage": "Create aggregation batches",
    "dispatch.manage": "Record warehouse dispatches",
    "warehouse_receipt.manage": "Record warehouse receipts",
    "reconciliation.approve": "Approve discrepancy explanations",
    # Auction
    "auction.view": "View auction results",
    "auction.manage": "Enter auction results",
    "auction.approve": "Approve auction results",
    # Finance
    "deduction.manage": "Configure levies and deductions",
    "loan.manage": "Manage farmer input loans",
    "payout.view": "View payout calculations",
    "payout.calculate": "Run payout calculations",
    "payout.approve": "Approve payout calculations",
    "payment_batch.prepare": "Prepare payment batches and exports",
    "payment_batch.approve": "Approve payment batches",
    "payment.reconcile": "Record payment results",
    # Reports & notifications
    "report.operational": "View operational reports",
    "report.financial": "View financial reports",
    "notification.manage": "Manage SMS templates and resend messages",
}

_ALL = set(PERMISSIONS)
_VIEW = {p for p in PERMISSIONS if p.endswith(".view")}

ROLES: dict[str, dict] = {
    "system_admin": {
        "name": "System Administrator",
        "permissions": _ALL,
    },
    "manager": {
        "name": "AMCOS Manager",
        "permissions": _ALL - {"organization.manage", "role.manage", "payment_batch.prepare"},
    },
    "clerk": {
        "name": "Collection Centre Clerk",
        "permissions": {
            "centre.view", "crop.view", "farmer.view", "farmer.create",
            "delivery.view", "delivery.create", "delivery.amend_request",
        },
    },
    "accountant": {
        "name": "Accountant / Finance Officer",
        "permissions": _VIEW | {
            "farmer.view_financial", "deduction.manage", "loan.manage", "payout.calculate",
            "payment_batch.prepare", "payment.reconcile", "report.financial", "report.operational",
        },
    },
    "warehouse_officer": {
        "name": "Warehouse Officer",
        "permissions": {
            "centre.view", "crop.view", "delivery.view", "auction.view",
            "batch.manage", "dispatch.manage", "warehouse_receipt.manage", "report.operational",
        },
    },
    "auditor": {
        "name": "Auditor (read-only)",
        "permissions": _VIEW | {"farmer.view_financial", "report.operational", "report.financial"},
    },
}

# Separation of duties: nobody gets both sides of these pairs by default.
# Note the accountant can *prepare* but not *approve* payment batches; the manager the reverse.
assert "payment_batch.approve" not in ROLES["accountant"]["permissions"]
assert "payment_batch.prepare" not in ROLES["manager"]["permissions"]
