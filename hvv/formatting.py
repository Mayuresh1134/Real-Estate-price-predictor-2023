"""Indian-style money formatting (lakh and crore, 12,34,567 digit grouping)."""
from __future__ import annotations

RUPEE = "₹"
LAKH = 100_000
CRORE = 10_000_000


def group_indian(n: int) -> str:
    """1234567 -> '12,34,567' (last three digits, then pairs)."""
    sign = "-" if n < 0 else ""
    digits = str(abs(int(n)))
    if len(digits) <= 3:
        return sign + digits
    head, tail = digits[:-3], digits[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    if head:
        pairs.insert(0, head)
    return sign + ",".join(pairs + [tail])


def rupees(amount: float) -> str:
    """Full amount: 7850000 -> '₹78,50,000'."""
    return f"{RUPEE}{group_indian(round(amount))}"


def compact_rupees(amount: float) -> str:
    """Short amount: 7850000 -> '₹78.5 Lakh', 12400000 -> '₹1.24 Cr'."""
    amount = float(amount)
    if abs(amount) >= CRORE:
        return f"{RUPEE}{amount / CRORE:,.2f} Cr"
    if abs(amount) >= LAKH:
        return f"{RUPEE}{amount / LAKH:,.1f} Lakh"
    return rupees(amount)


def axis_rupees(amount: float) -> str:
    """Short axis label without trailing zeros: '₹2.5 Cr', '₹50 Lakh', '₹0'."""
    if amount == 0:
        return f"{RUPEE}0"
    if abs(amount) >= CRORE:
        return f"{RUPEE}{amount / CRORE:g} Cr"
    if abs(amount) >= LAKH:
        return f"{RUPEE}{amount / LAKH:g} Lakh"
    return rupees(amount)


def parse_amount(text: str) -> float:
    """Read what a person typed: '78,50,000', '₹ 78.5 lakh', '1.2 cr', '7850000'."""
    cleaned = text.strip().lower().replace(RUPEE, "").replace(",", "").replace("rs.", "").replace("rs", "")
    cleaned = cleaned.strip()
    multiplier = 1.0
    for word, value in (("crores", CRORE), ("crore", CRORE), ("cr", CRORE),
                        ("lakhs", LAKH), ("lakh", LAKH), ("lacs", LAKH),
                        ("lac", LAKH), ("l", LAKH)):
        if cleaned.endswith(word):
            cleaned, multiplier = cleaned[: -len(word)].strip(), float(value)
            break
    if not cleaned:
        raise ValueError("empty amount")
    return float(cleaned) * multiplier
