"""Worked numerical examples for the payout engine (pure maths, no database).

Farmer A from the Phase 6 example, AMCOS-absorbs policy:
  L1 244.898 kg x 2,100 = 514,285.80
  L2 155.102 kg x 1,950 = 302,448.90
                 GROSS  = 816,734.70   (400.000 kg)

Deductions configured by the AMCOS (example rates, NOT real statutory rates):
  priority 10  District levy        3% of gross      = 24,502.04   (816,734.70 x 0.03 = 24,502.041)
  priority 20  Cooperative levy     25 TZS per kg    = 10,000.00   (400 x 25)
  priority 30  Transport            5,000 fixed      =  5,000.00
                                      levies total   = 39,502.04
  available after levies = 777,232.66
  Loan IL-001 outstanding 150,000, cap 50% -> min(150,000, 388,616.33) = 150,000.00
  NET = 816,734.70 - 39,502.04 - 150,000.00 = 627,232.66
"""
from decimal import Decimal as D

from app.services.payout_engine import DeductionInput, EarningInput, LoanInput, calculate

EARN = [EarningInput("a1", "d1", "L1", D("244.898"), D("2100")), EarningInput("a2", "d1", "L2", D("155.102"), D("1950"))]
DEDS = [
    DeductionInput("t3", "Transport", "other", "fixed", D("5000"), "farmer", 30),
    DeductionInput("t1", "District levy", "levy", "percent_of_gross", D("3"), "farmer", 10),
    DeductionInput("t2", "Cooperative levy", "levy", "per_kg", D("25"), "farmer", 20),
]


def test_worked_example():
    r = calculate(EARN, DEDS, [LoanInput("l1", "IL-001", D("150000"), D("50"))])
    assert r.eligible_kg == D("400.000")
    assert r.gross == D("816734.70")
    amounts = {l.description.split(" (")[0]: l.amount for l in r.lines}
    assert amounts["L1"] == D("514285.80") and amounts["L2"] == D("302448.90")
    assert amounts["District levy"] == D("24502.04")
    assert amounts["Cooperative levy"] == D("10000.00")
    assert amounts["Transport"] == D("5000.00")
    assert amounts["Input loan IL-001 repayment"] == D("150000.00")
    assert r.total_deductions == D("189502.04")
    assert r.net == D("627232.66")
    assert not r.needs_review
    # deductions are applied in priority order regardless of input order
    assert [l.description.split(" (")[0] for l in r.lines if l.line_type != "earning"][:3] == \
        ["District levy", "Cooperative levy", "Transport"]


def test_loan_is_capped_and_remainder_flagged():
    # cap 50% of 777,232.66 = 388,616.33; loan 1,000,000 -> only 388,616.33 deducted
    r = calculate(EARN, DEDS, [LoanInput("l1", "IL-002", D("1000000"), D("50"))])
    loan_line = next(l for l in r.lines if l.line_type == "loan")
    assert loan_line.amount == D("388616.33")
    assert r.net == D("388616.33")
    assert any("IL-002" in f and "remains outstanding" in f for f in r.flags)


def test_loan_without_cap_never_makes_net_negative():
    r = calculate(EARN, DEDS, [LoanInput("l1", "IL-003", D("5000000"), None)])
    assert r.net == D("0.00") and r.net >= 0
    assert not r.needs_review  # loans are limited, not a shortfall


def test_multiple_loans_oldest_first():
    loans = [LoanInput("old", "OLD", D("700000"), None), LoanInput("new", "NEW", D("500000"), None)]
    r = calculate(EARN, DEDS, loans)
    by_ref = {l.loan_id: l.amount for l in r.lines if l.line_type == "loan"}
    assert by_ref == {"old": D("700000.00"), "new": D("77232.66")}


def test_levies_exceeding_gross_are_held_for_review_not_negative():
    tiny = [EarningInput("a", "d", "L", D("1.000"), D("1000"))]          # gross 1,000.00
    deds = [DeductionInput("f", "Big fixed fee", "other", "fixed", D("1500"), "farmer", 1)]
    r = calculate(tiny, deds, [LoanInput("l", "IL", D("100"), None)])
    assert r.gross == D("1000.00")
    assert r.needs_review and r.shortfall == D("500.00")
    assert r.net == D("0.00")
    assert not any(l.line_type == "loan" for l in r.lines)              # nothing left for the loan


def test_fixed_per_delivery():
    earn = [EarningInput("a1", "d1", "x", D("10"), D("1000")), EarningInput("a2", "d2", "y", D("10"), D("1000")),
            EarningInput("a3", "d2", "z", D("10"), D("1000"))]   # 2 distinct deliveries
    r = calculate(earn, [DeductionInput("t", "Bag fee", "other", "fixed", D("500"), "delivery", 1)], [])
    assert next(l for l in r.lines if l.line_type == "other").amount == D("1000.00")


def test_rounding_half_up_per_line():
    # 0.005 must round UP to 0.01 (banker's rounding would give 0.00)
    r = calculate([EarningInput("a", "d", "L", D("0.001"), D("5"))], [], [])
    assert r.gross == D("0.01")


def test_no_earnings():
    r = calculate([], [], [LoanInput("l", "IL", D("100"), None)])
    assert r.gross == r.net == D("0.00")
