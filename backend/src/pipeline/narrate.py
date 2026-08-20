from typing import Any, Dict


def narrate_match(match_reasons: Dict[str, Any]) -> str:
    if match_reasons.get("reason") == "exact_pan_match":
        return f"Matched on PAN {match_reasons.get('pan', '')}".strip()

    confidence = match_reasons.get("confidence")
    if confidence is not None:
        return f"Matched on name + attribute similarity ({float(confidence) * 100:.1f}% confidence)"
    return "Matched on attribute similarity"


def narrate_conflict(field_name: str, source_system: str) -> str:
    return f"{field_name} resolved via source precedence: took {source_system}'s value"


def narrate_opportunity(
    product_type: str,
    relationship_value: float,
    n_systems: int,
    score: float,
) -> str:
    return (
        f"Eligible for {product_type} - relationship value "
        f"Rs {relationship_value:,.0f}, active across {n_systems} products, "
        f"score {score}/100"
    )
