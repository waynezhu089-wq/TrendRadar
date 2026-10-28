import unittest
from dataclasses import replace
from decimal import Decimal

from test_market import fixture_days
from app.market.technical import compute_technical_state


class TechnicalStateTests(unittest.TestCase):
    def test_exact_30_day_math_and_unsorted_input(self):
        days = fixture_days()
        state = compute_technical_state(list(reversed(days)))
        self.assertEqual(state.sample_days, 30)
        self.assertEqual(state.change_pct, Decimal("3.4483"))
        self.assertEqual((state.ma5, state.ma10, state.ma20),
                         (Decimal("28.0000"), Decimal("25.5000"), Decimal("20.5000")))
        self.assertEqual((state.close_vs_ma5_pct, state.close_vs_ma10_pct,
                          state.close_vs_ma20_pct),
                         (Decimal("7.1429"), Decimal("17.6471"), Decimal("46.3415")))
        self.assertEqual((state.high_20d, state.low_20d), (Decimal(31), Decimal(10)))
        self.assertEqual(state.range_position_20d, Decimal("95.2381"))
        self.assertEqual(state.avg_volume_5d, Decimal("2700.00"))
        self.assertEqual(state.volume_ratio_5d, Decimal("1.1111"))

    def test_insufficient_history_and_missing_close_are_null(self):
        one = compute_technical_state(fixture_days(1))
        self.assertIsNone(one.change_pct)
        self.assertIsNone(one.ma5)
        self.assertIsNone(one.high_20d)
        self.assertIsNone(one.avg_volume_5d)
        self.assertIsNone(one.volume_ratio_5d)
        five = compute_technical_state(fixture_days(5))
        self.assertEqual(five.ma5, Decimal("3.0000"))
        self.assertIsNone(five.ma10)
        self.assertIsNone(five.volume_ratio_5d)
        missing = fixture_days()
        missing[-3] = replace(missing[-3], close=None)
        result = compute_technical_state(missing)
        self.assertIsNone(result.ma5)
        self.assertIsNone(result.ma10)
        self.assertIsNone(result.ma20)
        self.assertIsNone(result.close_vs_ma20_pct)

    def test_flat_range_and_missing_volume_are_null(self):
        flat = [replace(day, high=Decimal(10), low=Decimal(10)) for day in fixture_days()]
        state = compute_technical_state(flat)
        self.assertEqual((state.high_20d, state.low_20d), (Decimal(10), Decimal(10)))
        self.assertIsNone(state.range_position_20d)
        missing = fixture_days()
        missing[-2] = replace(missing[-2], volume=None)
        result = compute_technical_state(missing)
        self.assertIsNone(result.avg_volume_5d)
        self.assertIsNone(result.volume_ratio_5d)


if __name__ == "__main__":
    unittest.main()
