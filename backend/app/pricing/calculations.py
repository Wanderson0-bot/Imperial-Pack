from decimal import Decimal, ROUND_HALF_UP

MIN_MARGIN = Decimal('0.20')
STANDARD_MARGIN = Decimal('0.30')
MAX_MARKUP = Decimal('1.00')
ROUNDING_STEP = Decimal('0.05')


def margin(price: Decimal, cost: Decimal) -> Decimal:
    return ((price - cost) / price * 100).quantize(Decimal('0.0001')) if price else Decimal('0')


def markup(price: Decimal, cost: Decimal) -> Decimal:
    return ((price - cost) / cost * 100).quantize(Decimal('0.0001')) if cost else Decimal('0')


def commercial_round(value: Decimal) -> Decimal:
    return (value / ROUNDING_STEP).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * ROUNDING_STEP


def suggested_price(cost: Decimal) -> Decimal:
    return commercial_round(cost / (1 - STANDARD_MARGIN)) if cost else Decimal('0')


def minimum_price(cost: Decimal) -> Decimal:
    return cost / (1 - MIN_MARGIN) if cost else Decimal('0')


def maximum_price(cost: Decimal) -> Decimal:
    return cost * (1 + MAX_MARKUP)
