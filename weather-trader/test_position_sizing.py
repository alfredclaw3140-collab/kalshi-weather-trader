"""Comprehensive tests for dynamic position sizing."""
import unittest
from position_sizing import (
    calculate_position_size, check_weather_correlation_risk,
    calculate_contract_quantity, DEFAULT_KELLY, HIGH_EDGE_KELLY,
    REDUCED_KELLY, MODERATE_EDGE_KELLY
)


class TestBasePositionSizing(unittest.TestCase):
    def test_15_percent_edge(self):
        size = calculate_position_size(edge=0.15, current_exposure=0.0,
                                       open_positions_count=0, days_to_resolution=3)
        self.assertEqual(size, MODERATE_EDGE_KELLY)
    
    def test_20_percent_edge(self):
        size = calculate_position_size(edge=0.20, current_exposure=0.0,
                                       open_positions_count=0, days_to_resolution=3)
        self.assertEqual(size, DEFAULT_KELLY)
    
    def test_25_percent_edge(self):
        size = calculate_position_size(edge=0.25, current_exposure=0.0,
                                       open_positions_count=0, days_to_resolution=3)
        self.assertEqual(size, HIGH_EDGE_KELLY)


class TestExposureLimits(unittest.TestCase):
    def test_reduced_at_20_percent(self):
        size = calculate_position_size(edge=0.20, current_exposure=0.20,
                                       open_positions_count=2, days_to_resolution=2)
        self.assertEqual(size, REDUCED_KELLY)
    
    def test_blocked_at_30_percent(self):
        size = calculate_position_size(edge=0.30, current_exposure=0.30,
                                       open_positions_count=3, days_to_resolution=2)
        self.assertEqual(size, 0.0)


class TestPositionCountLimits(unittest.TestCase):
    def test_blocked_at_6_positions(self):
        size = calculate_position_size(edge=0.25, current_exposure=0.15,
                                       open_positions_count=6, days_to_resolution=2)
        self.assertEqual(size, 0.0)


class TestResolutionTime(unittest.TestCase):
    def test_same_day_reduction(self):
        size = calculate_position_size(edge=0.20, current_exposure=0.0,
                                       open_positions_count=0, days_to_resolution=0)
        self.assertAlmostEqual(size, 0.025, places=4)
    
    def test_next_day_reduction(self):
        size = calculate_position_size(edge=0.20, current_exposure=0.0,
                                       open_positions_count=0, days_to_resolution=1)
        self.assertAlmostEqual(size, 0.04, places=4)


class TestWeatherCorrelation(unittest.TestCase):
    def test_nyc_correlates_with_boston(self):
        existing = [{"city": "Boston"}]
        count = check_weather_correlation_risk("NYC", existing)
        self.assertEqual(count, 1)
    
    def test_nyc_no_correlation_with_la(self):
        existing = [{"city": "LA"}]
        count = check_weather_correlation_risk("NYC", existing)
        self.assertEqual(count, 0)


class TestNewCities(unittest.TestCase):
    """Test new cities are in correct regions."""
    
    def test_dallas_with_phoenix(self):
        """Dallas should correlate with Phoenix (both southwest)."""
        existing = [{"city": "Phoenix"}]
        count = check_weather_correlation_risk("Dallas", existing)
        self.assertEqual(count, 1)
    
    def test_philadelphia_northeast(self):
        """Philadelphia should correlate with NYC."""
        existing = [{"city": "NYC"}, {"city": "Boston"}]
        count = check_weather_correlation_risk("Philadelphia", existing)
        self.assertEqual(count, 2)
    
    def test_miami_southeast(self):
        """Miami should be in southeast region."""
        existing = [{"city": "Atlanta"}]
        count = check_weather_correlation_risk("Miami", existing)
        self.assertEqual(count, 1)
    
    def test_denver_isolated(self):
        """Denver is isolated in mountain region."""
        existing = [{"city": "Phoenix"}, {"city": "LA"}]
        count = check_weather_correlation_risk("Denver", existing)
        self.assertEqual(count, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
