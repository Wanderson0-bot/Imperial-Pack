import unittest
from datetime import date
from intelligence.features.consumption import PurchaseObservation, build_features
from intelligence.prediction.provider import ModelNotConfigured, UnconfiguredProvider


class ConsumptionFeatureTests(unittest.TestCase):
    def test_empty_history_is_insufficient(self):
        self.assertFalse(build_features([]).sufficient_for_model)

    def test_one_purchase_has_last_quantity_but_no_interval(self):
        features = build_features([PurchaseObservation(date(2026, 1, 1), 12)])
        self.assertEqual(features.last_quantity, 12)
        self.assertIsNone(features.mean_interval_days)
        self.assertFalse(features.sufficient_for_model)

    def test_multiple_purchases_calculate_interval_and_observed_rate(self):
        rows = [PurchaseObservation(date(2026, 1, day), quantity) for day, quantity in [(1, 10), (11, 20), (21, 30)]]
        features = build_features(rows)
        self.assertEqual(features.mean_interval_days, 10)
        self.assertTrue(features.sufficient_for_model)
        self.assertEqual(features.observed_quantity_per_day, 3)

    def test_missing_model_does_not_predict(self):
        with self.assertRaises(ModelNotConfigured):
            UnconfiguredProvider().predict({'observed_rate': 1})


if __name__ == '__main__':
    unittest.main()
