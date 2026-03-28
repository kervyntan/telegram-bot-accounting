"""Phase 3b: Currency conversion and markup pricing."""

import logging

logger = logging.getLogger(__name__)


def calculate_price(
    raw_price_jpy: int,
    jpy_to_sgd_rate: float,
    markup: float = 1.3,
) -> int:
    """Convert JPY price to SGD with markup, rounded to nearest whole number.

    Args:
        raw_price_jpy: Original price in Japanese Yen.
        jpy_to_sgd_rate: Exchange rate (1 JPY = X SGD).
        markup: Markup multiplier (default 1.3 = 30%).

    Returns:
        Final price in SGD as an integer.
    """
    base_cost = raw_price_jpy * jpy_to_sgd_rate
    final_price = round(base_cost * markup)
    logger.info(
        f"Pricing: ¥{raw_price_jpy:,} × {jpy_to_sgd_rate:.6f} = "
        f"SGD {base_cost:.2f} × {markup} = SGD {final_price}"
    )
    return final_price
