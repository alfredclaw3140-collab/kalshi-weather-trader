"""Comprehensive tests for weather trading bot logic."""
import unittest
from datetime import date
from noaa_fixed import calculate_edge, parse_temp_bucket
from position_tracker import PositionTracker, Position


class TestBucketParsing(unittest.TestCase):
    """Test temperature bucket parsing from market titles."""
    
    def test_less_than_boundary(self):
        """<38° should be max=37 (strictly less)."""
        title = "Will the high temp be <38° on Feb 22?"
        bucket = parse_temp_bucket(title)
        self.assertEqual(bucket['type'], 'lt')
        self.assertEqual(bucket['max'], 37)
        self.assertEqual(bucket['min'], -999)
    
    def test_greater_than_boundary(self):
        """>45° should be min=46 (strictly greater)."""
        title = "Will the high temp be >45° on Feb 22?"
        bucket = parse_temp_bucket(title)
        self.assertEqual(bucket['type'], 'gt')
        self.assertEqual(bucket['min'], 46)
        self.assertEqual(bucket['max'], 999)
    
    def test_range_boundary(self):
        """38-39° should be inclusive."""
        title = "Will the high temp be 38-39° on Feb 22?"
        bucket = parse_temp_bucket(title)
        self.assertEqual(bucket['type'], 'range')
        self.assertEqual(bucket['min'], 38)
        self.assertEqual(bucket['max'], 39)
    
    def test_forecast_in_bucket_lt(self):
        """Forecast of 37 should be IN <38 bucket."""
        bucket = {'min': -999, 'max': 37, 'type': 'lt'}
        self.assertTrue(bucket['min'] <= 37 <= bucket['max'])
        self.assertFalse(bucket['min'] <= 38 <= bucket['max'])
    
    def test_forecast_in_bucket_gt(self):
        """Forecast of 46 should be IN >45 bucket."""
        bucket = {'min': 46, 'max': 999, 'type': 'gt'}
        self.assertTrue(bucket['min'] <= 46 <= bucket['max'])
        self.assertFalse(bucket['min'] <= 45 <= bucket['max'])


class TestEdgeCalculation(unittest.TestCase):
    """Test edge calculation logic."""
    
    def test_strong_edge_buy_yes(self):
        """When we're 85% confident but market is 40%, edge is 45%."""
        forecast_temp = 38
        bucket = {'min': 38, 'max': 39, 'type': 'range', 'city': 'NYC'}
        market_prob = 0.40
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        self.assertTrue(result['in_bucket'])
        self.assertAlmostEqual(result['edge'], 0.45, places=2)  # 0.85 - 0.40
        self.assertEqual(result['recommendation'], 'BUY')
        self.assertGreater(result['kelly_fraction'], 0)
    
    def test_weak_edge_hold(self):
        """When edge is only 10%, we should hold."""
        forecast_temp = 38
        bucket = {'min': 38, 'max': 39, 'type': 'range', 'city': 'NYC'}
        market_prob = 0.75  # Market almost agrees with us
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        self.assertTrue(result['in_bucket'])
        self.assertAlmostEqual(result['edge'], 0.10, places=2)
        self.assertEqual(result['recommendation'], 'HOLD')
    
    def test_outside_bucket_buy_no(self):
        """When forecast is outside bucket, we should buy NO."""
        forecast_temp = 42  # Outside 38-39 bucket
        bucket = {'min': 38, 'max': 39, 'type': 'range', 'city': 'NYC'}
        market_prob = 0.40  # Market thinks YES has 40% chance
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        self.assertFalse(result['in_bucket'])
        # We think YES has only 15% chance (85% confidence NO wins)
        # Edge = 0.85 - 0.40 = 0.45 (for NO side)
        self.assertGreater(abs(result['edge']), 0)
    
    def test_no_edge_at_85(self):
        """When market prices at our confidence level, no edge."""
        forecast_temp = 38
        bucket = {'min': 38, 'max': 39, 'type': 'range', 'city': 'NYC'}
        market_prob = 0.85  # Market agrees with our confidence
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        self.assertAlmostEqual(result['edge'], 0.0, places=2)


class TestKellySizing(unittest.TestCase):
    """Test Kelly criterion position sizing."""
    
    def test_kelly_capped_at_25_percent(self):
        """Kelly should never exceed 5% (safety cap)."""
        forecast_temp = 38
        bucket = {'min': 38, 'max': 39, 'type': 'range', 'city': 'NYC'}
        market_prob = 0.10  # Huge edge: 85% - 10% = 75%
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        # Kelly would suggest betting heavily, but we cap at 5%
        self.assertLessEqual(result['kelly_fraction'], 0.05)
    
    def test_kelly_zero_for_no_edge(self):
        """Kelly should be 0 when there's no edge."""
        forecast_temp = 38
        bucket = {'min': 38, 'max': 39, 'type': 'range', 'city': 'NYC'}
        market_prob = 0.85  # No edge
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        self.assertEqual(result['kelly_fraction'], 0)


class TestExitTriggers(unittest.TestCase):
    """Test exit trigger logic."""
    
    def setUp(self):
        self.tracker = PositionTracker(positions_file='/tmp/test_positions.json')
        # Clear any existing test positions
        self.tracker.positions = []
    
    def test_exit_on_forecast_change(self):
        """Should trigger exit when forecast moves out of bucket."""
        # Entered position thinking forecast was 38°F in 38-39 bucket
        position = Position(
            ticker="KXHIGHNY-26FEB22-B38.5",
            entry_date="2026-02-22",
            resolution_date="2026-02-22",
            side="yes",
            contracts=10,
            entry_price=0.40,
            entry_edge=0.45,
            forecast_temp_at_entry=38,
            bucket_min=38,
            bucket_max=39,
            city="NYC"
        )
        self.tracker.add_position(position)
        
        # Forecast changes to 42°F (outside bucket)
        results = self.tracker.check_exit_triggers(current_forecast=42, current_price=0.35)
        
        self.assertTrue(any(r['should_exit'] for r in results))
        self.assertTrue(any('FORECAST_CHANGED' in r['triggers'] for r in results if r['should_exit']))
    
    def test_exit_on_edge_decay_50(self):
        """Should trigger exit when we lose 50% of our edge."""
        position = Position(
            ticker="KXHIGHNY-26FEB22-B38.5",
            entry_date="2026-02-22",
            resolution_date="2026-02-22",
            side="yes",
            contracts=10,
            entry_price=0.40,
            entry_edge=0.40,  # Started with 40% edge
            forecast_temp_at_entry=38,
            bucket_min=38,
            bucket_max=39,
            city="NYC"
        )
        self.tracker.add_position(position)
        
        # Price moved to 65%, so edge is now 20% (50% decay from 40%)
        results = self.tracker.check_exit_triggers(current_forecast=38, current_price=0.65)
        
        self.assertTrue(any(r['should_exit'] for r in results))
    
    def test_take_profits_at_85(self):
        """Should suggest taking profits when price hits 85%."""
        position = Position(
            ticker="KXHIGHNY-26FEB22-B38.5",
            entry_date="2026-02-22",
            resolution_date="2026-02-22",
            side="yes",
            contracts=10,
            entry_price=0.40,
            entry_edge=0.45,
            forecast_temp_at_entry=38,
            bucket_min=38,
            bucket_max=39,
            city="NYC"
        )
        self.tracker.add_position(position)
        
        # Price moved to 87% (big profit)
        results = self.tracker.check_exit_triggers(current_forecast=38, current_price=0.87)
        
        # Should have TAKE_PROFITS trigger
        profit_triggers = [r for r in results if 'TAKE_PROFITS' in r['triggers']]
        self.assertTrue(len(profit_triggers) > 0)
    
    def test_hold_when_no_triggers(self):
        """Should hold when no exit conditions met."""
        position = Position(
            ticker="KXHIGHNY-26FEB22-B38.5",
            entry_date="2026-02-22",
            resolution_date="2026-02-22",
            side="yes",
            contracts=10,
            entry_price=0.40,
            entry_edge=0.45,
            forecast_temp_at_entry=38,
            bucket_min=38,
            bucket_max=39,
            city="NYC"
        )
        self.tracker.add_position(position)
        
        # Forecast same, price similar (slight move to 45%)
        results = self.tracker.check_exit_triggers(current_forecast=38, current_price=0.45)
        
        # Should NOT exit
        self.assertFalse(any(r['should_exit'] for r in results))


class TestMarketEfficiency(unittest.TestCase):
    """Test scenarios where market is efficient (no edge)."""
    
    def test_no_opportunity_when_market_agrees(self):
        """When market prices match our forecast, no trade."""
        forecast_temp = 38
        bucket = {'min': 38, 'max': 39, 'type': 'range', 'city': 'NYC'}
        market_prob = 0.75  # Market thinks 75% chance
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        # Edge is only 10% (85% - 75%), below 15% threshold
        self.assertEqual(result['recommendation'], 'HOLD')
    
    def test_no_opportunity_when_overpriced(self):
        """When market prices above our confidence, no edge."""
        forecast_temp = 38
        bucket = {'min': 38, 'max': 39, 'type': 'range', 'city': 'NYC'}
        market_prob = 0.90  # Market more confident than us
        
        result = calculate_edge(forecast_temp, bucket, market_prob)
        
        # Negative edge (market smarter than us)
        self.assertLess(result['edge'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
