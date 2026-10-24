import pytest

from backend.app.units import ft_to_m, format_ft_in, m_to_ft, parse_ft_in


def test_conversions_and_formatting():
    assert m_to_ft(1) == 3.28084
    assert ft_to_m(m_to_ft(7.5)) == pytest.approx(7.5, abs=1e-9)
    assert [(value, format_ft_in(value)) for value in (7.5, 3.6, 0, 11.6 / 12, -7.5)] == [
        (7.5, '7\' 6"'), (3.6, '3\' 7"'), (0, '0\' 0"'), (11.6 / 12, '1\' 0"'), (-7.5, '-7\' 6"')]
    assert parse_ft_in('7\' 6"') == 7.5
    assert parse_ft_in('-3\' 7"') == pytest.approx(-3 - 7 / 12)
