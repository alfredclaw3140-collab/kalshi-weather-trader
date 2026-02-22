"""Comprehensive tests for NOAA alerts and forecast change detection."""
import unittest
from datetime import date, datetime
from unittest.mock import patch, MagicMock
from noaa_with_alerts import (
    fetch_noaa_alerts, check_significant_weather_events,
    ForecastSnapshot, has_forecast_changed, ForecastTracker
)


class TestNOAAAlerts(unittest.TestCase):
    """Test NOAA alert fetching and parsing."""
    
    @patch('noaa_with_alerts.requests.get')
    def test_fetch_alerts_success(self, mock_get):
        """Test successful alert fetching."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "features": [
                {
                    "properties": {
                        "event": "Winter Storm Warning",
                        "severity": "Severe",
                        "headline": "Winter Storm Warning in effect",
                        "description": "Heavy snow expected",
                        "effective": "2026-02-22T12:00:00Z",
                        "expires": "2026-02-23T12:00:00Z"
                    }
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        alerts = fetch_noaa_alerts("NYC")
        
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["event"], "Winter Storm Warning")
        self.assertEqual(alerts[0]["severity"], "Severe")
    
    @patch('noaa_with_alerts.requests.get')
    def test_fetch_alerts_empty(self, mock_get):
        """Test when no alerts are active."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"features": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        alerts = fetch_noaa_alerts("NYC")
        
        self.assertEqual(len(alerts), 0)
    
    @patch('noaa_with_alerts.requests.get')
    def test_fetch_alerts_api_error(self, mock_get):
        """Test handling of API errors."""
        mock_get.side_effect = Exception("API Error")
        
        alerts = fetch_noaa_alerts("NYC")
        
        self.assertEqual(len(alerts), 0)
    
    @patch('noaa_with_alerts.fetch_noaa_alerts')
    def test_significant_weather_events_detected(self, mock_fetch):
        """Test detection of significant weather events."""
        mock_fetch.return_value = [
            {"event": "Winter Storm Warning", "severity": "Severe"},
            {"event": "High Wind Warning", "severity": "Moderate"}
        ]
        
        result = check_significant_weather_events("NYC")
        
        self.assertTrue(result["has_significant_event"])
        self.assertTrue(result["should_check_now"])
        self.assertEqual(len(result["events"]), 2)
        self.assertIn("Severe Winter Storm Warning", result["events"])
    
    @patch('noaa_with_alerts.fetch_noaa_alerts')
    def test_no_significant_events(self, mock_fetch):
        """Test when no significant events detected."""
        mock_fetch.return_value = [
            {"event": "Small Craft Advisory", "severity": "Minor"}
        ]
        
        result = check_significant_weather_events("NYC")
        
        self.assertFalse(result["has_significant_event"])
        self.assertFalse(result["should_check_now"])
    
    @patch('noaa_with_alerts.fetch_noaa_alerts')
    def test_extreme_severity_triggers_check(self, mock_fetch):
        """Test that Extreme severity always triggers check."""
        mock_fetch.return_value = [
            {"event": "Heat Advisory", "severity": "Extreme"}
        ]
        
        result = check_significant_weather_events("NYC")
        
        self.assertTrue(result["has_significant_event"])
        self.assertTrue(result["should_check_now"])


class TestForecastSnapshots(unittest.TestCase):
    """Test forecast snapshot creation and comparison."""
    
    def test_forecast_snapshot_creation(self):
        """Test creating a forecast snapshot."""
        snapshot = ForecastSnapshot(
            city="NYC",
            date="2026-02-22",
            high_temp=38,
            low_temp=24,
            fetched_at="2026-02-22T12:00:00",
            update_time="2026-02-22T06:00:00Z"
        )
        
        self.assertEqual(snapshot.city, "NYC")
        self.assertEqual(snapshot.high_temp, 38)
        self.assertEqual(snapshot.low_temp, 24)
        self.assertIsNotNone(snapshot.fingerprint)
    
    def test_forecast_snapshot_fingerprint_uniqueness(self):
        """Test that different forecasts have different fingerprints."""
        snapshot1 = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=38, low_temp=24,
            fetched_at="2026-02-22T12:00:00", update_time="2026-02-22T06:00:00Z"
        )
        snapshot2 = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=40, low_temp=24,
            fetched_at="2026-02-22T12:00:00", update_time="2026-02-22T06:00:00Z"
        )
        
        self.assertNotEqual(snapshot1.fingerprint, snapshot2.fingerprint)
    
    def test_has_forecast_changed_no_change(self):
        """Test when forecast hasn't changed."""
        old = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=38, low_temp=24,
            fetched_at="2026-02-22T10:00:00", update_time="2026-02-22T06:00:00Z"
        )
        new = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=38, low_temp=24,
            fetched_at="2026-02-22T12:00:00", update_time="2026-02-22T06:00:00Z"
        )
        
        result = has_forecast_changed(old, new)
        
        self.assertFalse(result["changed"])
        self.assertFalse(result["high_changed"])
        self.assertFalse(result["low_changed"])
    
    def test_has_forecast_changed_high_temp(self):
        """Test detecting high temperature change."""
        old = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=38, low_temp=24,
            fetched_at="2026-02-22T10:00:00", update_time="2026-02-22T06:00:00Z"
        )
        new = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=42, low_temp=24,
            fetched_at="2026-02-22T12:00:00", update_time="2026-02-22T12:00:00Z"
        )
        
        result = has_forecast_changed(old, new)
        
        self.assertTrue(result["changed"])
        self.assertTrue(result["high_changed"])
        self.assertFalse(result["low_changed"])
        self.assertEqual(result["high_diff"], 4)
        self.assertIn("High temp changed from 38°F to 42°F (up 4°F)", result["changes"])
    
    def test_has_forecast_changed_low_temp(self):
        """Test detecting low temperature change."""
        old = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=38, low_temp=24,
            fetched_at="2026-02-22T10:00:00", update_time="2026-02-22T06:00:00Z"
        )
        new = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=38, low_temp=20,
            fetched_at="2026-02-22T12:00:00", update_time="2026-02-22T12:00:00Z"
        )
        
        result = has_forecast_changed(old, new)
        
        self.assertTrue(result["changed"])
        self.assertFalse(result["high_changed"])
        self.assertTrue(result["low_changed"])
        self.assertEqual(result["low_diff"], -4)
        self.assertIn("Low temp changed from 24°F to 20°F (down 4°F)", result["changes"])
    
    def test_has_forecast_changed_both_temps(self):
        """Test detecting both high and low changes."""
        old = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=38, low_temp=24,
            fetched_at="2026-02-22T10:00:00", update_time="2026-02-22T06:00:00Z"
        )
        new = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=42, low_temp=28,
            fetched_at="2026-02-22T12:00:00", update_time="2026-02-22T12:00:00Z"
        )
        
        result = has_forecast_changed(old, new)
        
        self.assertTrue(result["changed"])
        self.assertTrue(result["high_changed"])
        self.assertTrue(result["low_changed"])
        self.assertEqual(len(result["changes"]), 3)  # High, low, NOAA update
    
    def test_has_forecast_changed_noaa_update_only(self):
        """Test when only NOAA update time changed but temps same."""
        old = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=38, low_temp=24,
            fetched_at="2026-02-22T10:00:00", update_time="2026-02-22T06:00:00Z"
        )
        new = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=38, low_temp=24,
            fetched_at="2026-02-22T12:00:00", update_time="2026-02-22T12:00:00Z"
        )
        
        result = has_forecast_changed(old, new)
        
        self.assertTrue(result["changed"])  # NOAA updated
        self.assertFalse(result["high_changed"])
        self.assertFalse(result["low_changed"])
        self.assertTrue(result["noaa_updated"])


class TestForecastTracker(unittest.TestCase):
    """Test forecast tracking and history."""
    
    def test_tracker_first_check(self):
        """Test first time checking a forecast."""
        tracker = ForecastTracker()
        
        with patch('noaa_with_alerts.get_forecast_snapshot') as mock_snapshot:
            mock_snapshot.return_value = ForecastSnapshot(
                city="NYC", date="2026-02-22", high_temp=38, low_temp=24,
                fetched_at="2026-02-22T12:00:00", update_time="2026-02-22T06:00:00Z"
            )
            
            result = tracker.check_and_update("NYC", date(2026, 2, 22))
        
        self.assertTrue(result["first_check"])
        self.assertFalse(result["changed"])
        self.assertIn("First forecast check", result["changes"])
    
    def test_tracker_detects_change(self):
        """Test tracker detecting forecast changes."""
        tracker = ForecastTracker()
        
        # First check
        snapshot1 = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=38, low_temp=24,
            fetched_at="2026-02-22T10:00:00", update_time="2026-02-22T06:00:00Z"
        )
        tracker.record_snapshot(snapshot1)
        
        # Second check with change
        with patch('noaa_with_alerts.get_forecast_snapshot') as mock_snapshot:
            mock_snapshot.return_value = ForecastSnapshot(
                city="NYC", date="2026-02-22", high_temp=42, low_temp=24,
                fetched_at="2026-02-22T12:00:00", update_time="2026-02-22T12:00:00Z"
            )
            
            result = tracker.check_and_update("NYC", date(2026, 2, 22))
        
        self.assertFalse(result["first_check"])
        self.assertTrue(result["changed"])
        self.assertTrue(result["high_changed"])
    
    def test_tracker_retrieves_history(self):
        """Test retrieving historical snapshots."""
        tracker = ForecastTracker()
        
        snapshot = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=38, low_temp=24,
            fetched_at="2026-02-22T12:00:00", update_time="2026-02-22T06:00:00Z"
        )
        tracker.record_snapshot(snapshot)
        
        retrieved = tracker.get_last_snapshot("NYC", date(2026, 2, 22))
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.high_temp, 38)
    
    def test_tracker_no_history(self):
        """Test retrieving when no history exists."""
        tracker = ForecastTracker()
        
        retrieved = tracker.get_last_snapshot("NYC", date(2026, 2, 22))
        
        self.assertIsNone(retrieved)
    
    def test_tracker_multiple_cities(self):
        """Test tracking forecasts for multiple cities."""
        tracker = ForecastTracker()
        
        snapshot_nyc = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=38, low_temp=24,
            fetched_at="2026-02-22T12:00:00", update_time="2026-02-22T06:00:00Z"
        )
        snapshot_chi = ForecastSnapshot(
            city="Chicago", date="2026-02-22", high_temp=35, low_temp=20,
            fetched_at="2026-02-22T12:00:00", update_time="2026-02-22T06:00:00Z"
        )
        
        tracker.record_snapshot(snapshot_nyc)
        tracker.record_snapshot(snapshot_chi)
        
        nyc_retrieved = tracker.get_last_snapshot("NYC", date(2026, 2, 22))
        chi_retrieved = tracker.get_last_snapshot("Chicago", date(2026, 2, 22))
        
        self.assertEqual(nyc_retrieved.high_temp, 38)
        self.assertEqual(chi_retrieved.high_temp, 35)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""
    
    def test_fetch_alerts_unknown_city(self):
        """Test fetching alerts for unknown city returns empty."""
        alerts = fetch_noaa_alerts("UnknownCity")
        self.assertEqual(len(alerts), 0)
    
    def test_forecast_with_none_temps(self):
        """Test snapshot with None temperatures."""
        snapshot = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=None, low_temp=None,
            fetched_at="2026-02-22T12:00:00", update_time="2026-02-22T06:00:00Z"
        )
        
        self.assertIsNone(snapshot.high_temp)
        self.assertIsNone(snapshot.low_temp)
        self.assertIsNotNone(snapshot.fingerprint)
    
    def test_large_temperature_change(self):
        """Test detecting large temperature swings."""
        old = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=40, low_temp=30,
            fetched_at="2026-02-22T10:00:00", update_time="2026-02-22T06:00:00Z"
        )
        new = ForecastSnapshot(
            city="NYC", date="2026-02-22", high_temp=75, low_temp=60,
            fetched_at="2026-02-22T12:00:00", update_time="2026-02-22T12:00:00Z"
        )
        
        result = has_forecast_changed(old, new)
        
        self.assertTrue(result["changed"])
        self.assertEqual(result["high_diff"], 35)
        self.assertEqual(result["low_diff"], 30)
    
    def test_severe_weather_triggers(self):
        """Test all severe weather events trigger checks."""
        severe_events = [
            ("Winter Storm Warning", True),
            ("Blizzard Warning", True),
            ("Hurricane Warning", True),
            ("Extreme Cold Warning", True),
            ("High Wind Warning", True),
            ("Tornado Warning", True),
            ("Small Craft Advisory", False),
            ("Dense Fog Advisory", False),
        ]
        
        for event, should_trigger in severe_events:
            with self.subTest(event=event):
                with patch('noaa_with_alerts.fetch_noaa_alerts') as mock_fetch:
                    mock_fetch.return_value = [
                        {"event": event, "severity": "Severe" if "Warning" in event else "Minor"}
                    ]
                    result = check_significant_weather_events("NYC")
                    self.assertEqual(result["should_check_now"], should_trigger, 
                                   f"{event} should trigger={should_trigger}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
