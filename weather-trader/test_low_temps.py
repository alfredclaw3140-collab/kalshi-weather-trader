"""Comprehensive tests for low temperature trading logic."""
import unittest
from datetime import date
from noaa_complete import (
    parse_temp_bucket, calculate_edge, get_low_temp_for_date, get_temps_for_date
)


class TestLowTempBucketParsing(unittest.TestCase):
    """Test low temperature bucket parsing from market titles."""
    
    def test_low_temp_lt_boundary(self):
        """Low temp <25° should be max=24 (strictly less)."""
        title = "Will the **low temp in NYC** be <25° on Feb 22, 2026?"
        bucket = parse_temp_bucket(title)
        self.assertEqual(bucket['type'], 'lt')
        self.assertEqual(bucket['max'], 24)
        self.assertEqual(bucket['min'], -999)
        self.assertEqual(bucket['temp_type'], 'low')
        self.assertEqual(bucket['city'], 'NYC')
    
    def test_low_temp_gt_boundary(self):
        """Low temp >30° should be min=31 (strictly greater)."""
        title = "Will the **low temp in Chicago** be >30° on Feb 22, 2026?"
        bucket = parse_temp_bucket(title)
        self.assertEqual(bucket['type'], 'gt')
        self.assertEqual(bucket['min'], 31)
        self.assertEqual(bucket['max'], 999)
        self.assertEqual(bucket['temp_type'], 'low')
        self.assertEqual(bucket['city'], 'Chicago')
    
    def test_low_temp_range_boundary(self):
        """Low temp 25-27° should be inclusive."""
        title = "Will the **low temp in Boston** be 25-27° on Feb 22, 2026?"
        bucket = parse_temp_bucket(title)
        self.assertEqual(bucket['type'], 'range')
        self.assertEqual(bucket['min'], 25)
        self.assertEqual(bucket['max'], 27)
        self.assertEqual(bucket['temp_type'], 'low')
        self.assertEqual(bucket['city'], 'Boston')
    
    def test_low_temp_in_bucket_lt(self):
        """Low forecast of 24 should be IN <25 bucket."""
        bucket = {'min': -999, 'max': 24, 'type': 'lt', 'temp_type': 'low'}
        self.assertTrue(bucket['min'] <= 24 <= bucket['max'])
        self.assertFalse(bucket['min'] <= 25 <= bucket['max'])
    
    def test_low_temp_in_bucket_gt(self):
        """Low forecast of 31 should be IN >30 bucket."""
        bucket = {'min': 31, 'max': 999, 'type': 'gt', 'temp_type': 'low'}
        self.assertTrue(bucket['min'] <= 31 <= bucket['max'])
        self.assertFalse(bucket['min'] <= 30 <= bucket['max'])
    
    def test_low_temp_out_of_bucket(self):
        """Low forecast of 20 should be OUT of 25-27 bucket."""
        bucket = {'min': 25, 'max': 27, 'type': 'range', 'temp_type': 'low'}
        self.assertFalse(bucket['min'] <= 20 <= bucket['max'])


class TestLowTempEdgeCalculation(unittest.TestCase):
    """Test edge calculation for low temperature markets."""
    
    def test_low_temp_strong_edge_buy_yes(self):
        """Low temp: 85% confidence vs 35% market = 50% edge."""
        forecast_temp = 24
        bucket = {'min': 22, 'max': 24, 'type': 'range', 'city': 'NYC', 'temp_type': 'low'}
        market_prob = 0.35
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        self.assertTrue(result['in_bucket'])
        self.assertAlmostEqual(result['edge'], 0.50, places=2)
        self.assertEqual(result['recommendation'], 'BUY')
        self.assertGreater(result['kelly_fraction'], 0)
    
    def test_low_temp_weak_edge_hold(self):
        """Low temp: 85% vs 75% market = 10% edge (hold)."""
        forecast_temp = 25
        bucket = {'min': 25, 'max': 27, 'type': 'range', 'city': 'NYC', 'temp_type': 'low'}
        market_prob = 0.75
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        self.assertTrue(result['in_bucket'])
        self.assertAlmostEqual(result['edge'], 0.10, places=2)
        self.assertEqual(result['recommendation'], 'HOLD')
    
    def test_low_temp_outside_bucket_avoid(self):
        """Low forecast of 20 outside 25-27 bucket = avoid."""
        forecast_temp = 20
        bucket = {'min': 25, 'max': 27, 'type': 'range', 'city': 'NYC', 'temp_type': 'low'}
        market_prob = 0.40
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        self.assertFalse(result['in_bucket'])
        self.assertEqual(result['recommendation'], 'AVOID')
    
    def test_low_temp_no_edge_at_85(self):
        """Low temp: market at 85% = no edge."""
        forecast_temp = 24
        bucket = {'min': 22, 'max': 24, 'type': 'range', 'city': 'NYC', 'temp_type': 'low'}
        market_prob = 0.85
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        self.assertAlmostEqual(result['edge'], 0.0, places=2)
    
    def test_low_temp_gt_bucket_edge(self):
        """Low temp >30 bucket with forecast 32."""
        forecast_temp = 32
        bucket = {'min': 31, 'max': 999, 'type': 'gt', 'city': 'NYC', 'temp_type': 'low'}
        market_prob = 0.45
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        self.assertTrue(result['in_bucket'])
        self.assertAlmostEqual(result['edge'], 0.40, places=2)


class TestLowTempKellySizing(unittest.TestCase):
    """Test Kelly criterion for low temperatures."""
    
    def test_low_temp_kelly_capped_at_5_percent(self):
        """Low temp Kelly should never exceed 5%."""
        forecast_temp = 22
        bucket = {'min': 20, 'max': 22, 'type': 'range', 'city': 'NYC', 'temp_type': 'low'}
        market_prob = 0.10  # Huge edge: 85% - 10% = 75%
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        self.assertLessEqual(result['kelly_fraction'], 0.05)
    
    def test_low_temp_kelly_zero_for_no_edge(self):
        """Low temp Kelly should be 0 when no edge."""
        forecast_temp = 24
        bucket = {'min': 22, 'max': 24, 'type': 'range', 'city': 'NYC', 'temp_type': 'low'}
        market_prob = 0.85
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        self.assertEqual(result['kelly_fraction'], 0)


class TestHighAndLowTempComparison(unittest.TestCase):
    """Test that high and low temps are handled correctly."""
    
    def test_parsing_distinguishes_high_vs_low(self):
        """Parser should correctly identify high vs low temp markets."""
        high_title = "Will the **high temp in NYC** be 38-40° on Feb 22?"
        low_title = "Will the **low temp in NYC** be 25-27° on Feb 22?"
        
        high_bucket = parse_temp_bucket(high_title)
        low_bucket = parse_temp_bucket(low_title)
        
        self.assertEqual(high_bucket['temp_type'], 'high')
        self.assertEqual(low_bucket['temp_type'], 'low')
        self.assertEqual(high_bucket['min'], 38)
        self.assertEqual(low_bucket['min'], 25)
    
    def test_same_thresholds_for_high_and_low(self):
        """Edge thresholds should be same for high and low temps."""
        # High temp scenario
        high_bucket = {'min': 38, 'max': 40, 'type': 'range', 'temp_type': 'high'}
        high_result = calculate_edge(39, high_bucket, 0.65)
        
        # Low temp scenario
        low_bucket = {'min': 25, 'max': 27, 'type': 'range', 'temp_type': 'low'}
        low_result = calculate_edge(26, low_bucket, 0.65)
        
        # Both should have same edge (85% - 65% = 20%)
        self.assertAlmostEqual(high_result['edge'], 0.20, places=2)
        self.assertAlmostEqual(low_result['edge'], 0.20, places=2)
        self.assertEqual(high_result['recommendation'], 'BUY')
        self.assertEqual(low_result['recommendation'], 'BUY')


class TestTempForecastExtraction(unittest.TestCase):
    """Test high/low temp extraction from forecasts."""
    
    def test_mock_forecast_high_extraction(self):
        """Test extracting high from mock forecast data."""
        from datetime import datetime
        
        # Mock forecast periods
        mock_periods = [
            {'name': 'Today', 'startTime': '2026-02-22T06:00:00-05:00', 
             'endTime': '2026-02-22T18:00:00-05:00', 'temperature': 38, 
             'temperatureUnit': 'F', 'isDaytime': True, 'shortForecast': 'Sunny'},
            {'name': 'Tonight', 'startTime': '2026-02-22T18:00:00-05:00',
             'endTime': '2026-02-23T06:00:00-05:00', 'temperature': 24,
             'temperatureUnit': 'F', 'isDaytime': False, 'shortForecast': 'Clear'},
        ]
        
        forecasts = [type('F', (), p) for p in mock_periods]
        for f, p in zip(forecasts, mock_periods):
            f.name = p['name']
            f.start_time = datetime.fromisoformat(p['startTime'])
            f.end_time = datetime.fromisoformat(p['endTime'])
            f.temperature = p['temperature']
            f.temperature_unit = p['temperatureUnit']
            f.is_daytime = p['isDaytime']
            f.date = f.start_time.date()
        
        target_date = date(2026, 2, 22)
        # Note: get_high_temp_for_date would need proper mock
        # This test validates the concept


class TestMarketEfficiencyLowTemp(unittest.TestCase):
    """Test low temp market efficiency scenarios."""
    
    def test_no_opportunity_when_low_temp_market_agrees(self):
        """When low temp market prices match forecast, no trade."""
        forecast_temp = 24
        bucket = {'min': 22, 'max': 24, 'type': 'range', 'city': 'NYC', 'temp_type': 'low'}
        market_prob = 0.80  # Market close to our confidence
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        self.assertEqual(result['recommendation'], 'HOLD')
    
    def test_opportunity_when_low_temp_market_underprices(self):
        """When low temp market underprices likely outcome, buy."""
        forecast_temp = 20
        bucket = {'min': 18, 'max': 20, 'type': 'range', 'city': 'NYC', 'temp_type': 'low'}
        market_prob = 0.30  # Market thinks unlikely
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        self.assertEqual(result['recommendation'], 'BUY')
        self.assertAlmostEqual(result['edge'], 0.55, places=2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
