"""Conversions at the API boundary; stored lengths are decimal feet."""
import math
import re


def m_to_ft(meters: float) -> float:
    return meters * 3.28084


def ft_to_m(feet: float) -> float:
    return feet / 3.28084


def format_ft_in(feet: float) -> str:
    if not math.isfinite(feet):
        raise ValueError("feet must be finite")
    inches = math.floor(abs(feet) * 12 + 0.5)
    whole, remainder = divmod(inches, 12)
    sign = "-" if feet < 0 and inches else ""
    return f"{sign}{whole}' {remainder}\""


def parse_ft_in(value: str) -> float:
    match = re.fullmatch(r'\s*(-)?\s*(\d+)\s*\'\s*(\d+(?:\.\d+)?)\s*"\s*', value)
    if not match:
        raise ValueError("expected feet and inches, e.g. 7' 6\"")
    inches = float(match[3])
    if inches >= 12:
        raise ValueError("inches must be less than 12")
    result = int(match[2]) + inches / 12
    return -result if match[1] else result
