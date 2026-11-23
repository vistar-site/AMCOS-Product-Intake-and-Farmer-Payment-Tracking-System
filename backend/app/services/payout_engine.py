"""The payout calculation engine — a PURE function (no database), so it is easy to test.

For one farmer:

  1. EARNINGS   one line per (delivery, auction lot) allocation:
                amount = round(kg x price_per_kg, 2)        gross = sum of earning lines
  2. LEVIES and other deductions, in priority order (lowest number first):
                percent_of_gross : round(gross x rate / 100, 2)
                per_kg           : round(eligible_kg x rate, 2)
                fixed            : rate (x number of deliveries if applies_per = 'delivery')
                Levies are statutory, so they are applied in full. If they exceed gross,
                the payout is held as NEEDS_REVIEW with a recorded shortfall — never negative.
  3. LOANS      oldest first, each capped at:  outstanding balance,
                the amount still available, and the loan's max_deduction_percent of that amount.
                Loans can therefore never push a payout below zero.
  4. NET        gross - levies - loans   (>= 0 by construction)

All rounding is ROUND_HALF_UP to 2 decimal places on each line; totals are sums of
the rounded lines, so a statement always adds up exactly as printed.
"""
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Literal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class EarningInput:
    allocation_id: object
    delivery_id: object
    description: str          # e.g. "Receipt DEMO-2026-000012 · Lot L1 (AUC-7)"
    kg: Decimal
    price_per_kg: Decimal


@dataclass(frozen=True)
class DeductionInput:
    deduction_type_id: object
    name: str
    category: Literal["levy", "other"]
    calc_method: Literal["percent_of_gross", "per_kg", "fixed"]
    rate: Decimal
    applies_per: Literal["farmer", "delivery"]
    priority: int


@dataclass(frozen=True)
class LoanInput:
    loan_id: object
    loan_ref: str
    outstanding: Decimal
    max_deduction_percent: Decimal | None


@dataclass
class Line:
    line_type: Literal["earning", "levy", "other", "loan"]
    description: str
    amount: Decimal
    quantity: Decimal | None = None
    rate: Decimal | None = None
    allocation_id: object = None
    deduction_type_id: object = None
    loan_id: object = None


@dataclass
class PayoutResult:
    eligible_kg: Decimal
    gross: Decimal
    total_deductions: Decimal
    net: Decimal
    shortfall: Decimal
    needs_review: bool
    flags: list[str] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)


def calculate(earnings: list[EarningInput], deductions: list[DeductionInput], loans: list[LoanInput]) -> PayoutResult:
    lines: list[Line] = []
    flags: list[str] = []

    # 1. Earnings
    for e in earnings:
        lines.append(Line("earning", e.description, money(e.kg * e.price_per_kg), quantity=e.kg,
                          rate=e.price_per_kg, allocation_id=e.allocation_id))
    gross = sum((l.amount for l in lines), ZERO)
    eligible_kg = sum((e.kg for e in earnings), Decimal("0.000"))
    deliveries = len({e.delivery_id for e in earnings})

    # 2. Levies & other deductions
    applied = ZERO
    for d in sorted(deductions, key=lambda x: (x.priority, x.name)):
        if d.calc_method == "percent_of_gross":
            amount, qty, label = money(gross * d.rate / 100), None, f"{d.name} ({d.rate.normalize()}% of gross)"
        elif d.calc_method == "per_kg":
            amount, qty, label = money(eligible_kg * d.rate), eligible_kg, f"{d.name} ({d.rate.normalize()} per kg)"
        else:
            times = deliveries if d.applies_per == "delivery" else 1
            amount, qty, label = money(d.rate * times), None, f"{d.name} (fixed{f' x {times} deliveries' if times > 1 else ''})"
        if amount > 0:
            lines.append(Line(d.category, label, amount, quantity=qty, rate=d.rate, deduction_type_id=d.deduction_type_id))
            applied += amount

    available = gross - applied
    shortfall = ZERO
    if available < 0:
        shortfall, available = -available, ZERO
        flags.append(f"Levies/deductions exceed gross earnings by {shortfall}; held for review")

    # 3. Loans (oldest first — caller supplies them in that order)
    for loan in loans:
        if available <= 0 or loan.outstanding <= 0:
            if loan.outstanding > 0 and available <= 0:
                flags.append(f"Loan {loan.loan_ref}: nothing available to deduct (outstanding {loan.outstanding})")
            continue
        cap = available
        if loan.max_deduction_percent is not None:
            # round DOWN so the cap is never exceeded by a cent
            cap = (available * loan.max_deduction_percent / 100).quantize(CENT, rounding=ROUND_DOWN)
        amount = min(loan.outstanding, cap)
        if amount > 0:
            lines.append(Line("loan", f"Input loan {loan.loan_ref} repayment", amount, loan_id=loan.loan_id,
                              rate=loan.max_deduction_percent))
            available -= amount
        if amount < loan.outstanding:
            flags.append(f"Loan {loan.loan_ref}: {loan.outstanding - amount} remains outstanding after this payout")

    total_deductions = sum((l.amount for l in lines if l.line_type != "earning"), ZERO)
    net = gross - total_deductions + shortfall  # shortfall restores net to >= 0
    assert net >= 0 and net == available, "engine invariant violated"
    return PayoutResult(eligible_kg=eligible_kg, gross=gross, total_deductions=total_deductions, net=net,
                        shortfall=shortfall, needs_review=shortfall > 0, flags=flags, lines=lines)
