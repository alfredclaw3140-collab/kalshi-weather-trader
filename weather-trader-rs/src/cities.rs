//! City configuration for weather trading
use std::collections::HashMap;
use lazy_static::lazy_static;

/// Weather market series for each city
#[derive(Debug, Clone)]
pub struct CitySeries {
    pub high: &'static str,
    pub low: &'static str,
}

/// NOAA grid point for API calls
#[derive(Debug, Clone)]
pub struct GridPoint {
    pub office: &'static str,
    pub grid_x: u32,
    pub grid_y: u32,
}

lazy_static! {
    /// City to Kalshi ticker series mapping
    pub static ref CITY_SERIES: HashMap<&'static str, CitySeries> = {
        let mut m = HashMap::new();
        // Original 8 cities
        m.insert("NYC", CitySeries { high: "KXHIGHNY", low: "KXLOWNY" });
        m.insert("Chicago", CitySeries { high: "KXHIGHCHI", low: "KXLOWCHI" });
        m.insert("Houston", CitySeries { high: "KXHIGHTHOU", low: "KXLOWHOU" });
        m.insert("Boston", CitySeries { high: "KXHIGHTBOS", low: "KXLOWBOS" });
        m.insert("Phoenix", CitySeries { high: "KXHIGHTPHX", low: "KXLOWPHX" });
        m.insert("Seattle", CitySeries { high: "KXHIGHTSEA", low: "KXLOWSEA" });
        m.insert("LA", CitySeries { high: "KXHIGHLAX", low: "KXLOWLAX" });
        m.insert("Atlanta", CitySeries { high: "KXHIGHTATL", low: "KXLOWATL" });
        // New 10 cities
        m.insert("Dallas", CitySeries { high: "KXHIGHTDAL", low: "KXLOWTDAL" });
        m.insert("Denver", CitySeries { high: "KXHIGHTDEN", low: "KXLOWTDEN" });
        m.insert("Minneapolis", CitySeries { high: "KXHIGHTMSP", low: "KXLOWTMSP" });
        m.insert("NewOrleans", CitySeries { high: "KXHIGHTMSY", low: "KXLOWTMSY" });
        m.insert("Philadelphia", CitySeries { high: "KXHIGHTPHL", low: "KXLOWTPHL" });
        m.insert("SanFrancisco", CitySeries { high: "KXHIGHTSFO", low: "KXLOWTSFO" });
        m.insert("DC", CitySeries { high: "KXHIGHTDCA", low: "KXLOWTDCA" });
        m.insert("Miami", CitySeries { high: "KXHIGHTMIA", low: "KXLOWTMIA" });
        m.insert("Detroit", CitySeries { high: "KXHIGHTDTW", low: "KXLOWTDTW" });
        m.insert("Portland", CitySeries { high: "KXHIGHTPDX", low: "KXLOWTPDX" });
        m
    };
    
    /// NOAA grid points for each city
    pub static ref GRID_POINTS: HashMap<&'static str, GridPoint> = {
        let mut m = HashMap::new();
        m.insert("NYC", GridPoint { office: "OKX", grid_x: 33, grid_y: 35 });
        m.insert("Chicago", GridPoint { office: "LOT", grid_x: 68, grid_y: 73 });
        m.insert("Houston", GridPoint { office: "HGX", grid_x: 65, grid_y: 97 });
        m.insert("Boston", GridPoint { office: "BOX", grid_x: 71, grid_y: 90 });
        m.insert("Phoenix", GridPoint { office: "PSR", grid_x: 158, grid_y: 58 });
        m.insert("Seattle", GridPoint { office: "SEW", grid_x: 124, grid_y: 68 });
        m.insert("LA", GridPoint { office: "LOX", grid_x: 154, grid_y: 44 });
        m.insert("Atlanta", GridPoint { office: "FFC", grid_x: 51, grid_y: 87 });
        m.insert("Dallas", GridPoint { office: "FWD", grid_x: 89, grid_y: 109 });
        m.insert("Denver", GridPoint { office: "BOU", grid_x: 63, grid_y: 61 });
        m.insert("Minneapolis", GridPoint { office: "MPX", grid_x: 107, grid_y: 71 });
        m.insert("NewOrleans", GridPoint { office: "LIX", grid_x: 71, grid_y: 84 });
        m.insert("Philadelphia", GridPoint { office: "PHI", grid_x: 49, grid_y: 75 });
        m.insert("SanFrancisco", GridPoint { office: "MTR", grid_x: 85, grid_y: 105 });
        m.insert("DC", GridPoint { office: "LWX", grid_x: 97, grid_y: 71 });
        m.insert("Miami", GridPoint { office: "MFL", grid_x: 110, grid_y: 50 });
        m.insert("Detroit", GridPoint { office: "DTX", grid_x: 63, grid_y: 34 });
        m.insert("Portland", GridPoint { office: "PQR", grid_x: 116, grid_y: 87 });
        m
    };
    
    /// Weather correlation regions
    pub static ref WEATHER_REGIONS: HashMap<&'static str, Vec<&'static str>> = {
        let mut m = HashMap::new();
        m.insert("northeast", vec!["NYC", "Boston", "Philadelphia", "DC"]);
        m.insert("midwest", vec!["Chicago", "Detroit", "Minneapolis"]);
        m.insert("southeast", vec!["Atlanta", "Miami", "NewOrleans"]);
        m.insert("southwest", vec!["Phoenix", "LA", "Dallas"]);
        m.insert("northwest", vec!["Seattle", "Portland", "SanFrancisco"]);
        m.insert("mountain", vec!["Denver"]);
        m.insert("texas", vec!["Houston", "Dallas", "NewOrleans"]);
        m
    };
}

/// Get all cities
pub fn get_all_cities() -> Vec<&'static str> {
    CITY_SERIES.keys().copied().collect()
}

/// Get city region
pub fn get_city_region(city: &str) -> Option<&'static str> {
    for (region, cities) in WEATHER_REGIONS.iter() {
        if cities.contains(&city) {
            return Some(region);
        }
    }
    None
}

/// Check correlation risk between cities
pub fn get_regional_exposure(city: &str, existing_positions: &[&str]) -> usize {
    let Some(region) = get_city_region(city) else {
        return 0;
    };
    
    let region_cities = WEATHER_REGIONS.get(region).unwrap();
    existing_positions.iter()
        .filter(|&&c| region_cities.contains(&c))
        .count()
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_all_cities_count() {
        let cities = get_all_cities();
        assert_eq!(cities.len(), 18);
    }
    
    #[test]
    fn test_nyc_series() {
        let series = CITY_SERIES.get("NYC").unwrap();
        assert_eq!(series.high, "KXHIGHNY");
        assert_eq!(series.low, "KXLOWNY");
    }
    
    #[test]
    fn test_nyc_region() {
        assert_eq!(get_city_region("NYC"), Some("northeast"));
    }
    
    #[test]
    fn test_nyc_correlates_with_boston() {
        let existing = vec!["Boston"];
        assert_eq!(get_regional_exposure("NYC", &existing), 1);
    }
    
    #[test]
    fn test_nyc_no_correlation_with_la() {
        let existing = vec!["LA"];
        assert_eq!(get_regional_exposure("NYC", &existing), 0);
    }
    
    #[test]
    fn test_philadelphia_northeast() {
        let existing = vec!["NYC", "Boston"];
        assert_eq!(get_regional_exposure("Philadelphia", &existing), 2);
    }
    
    #[test]
    fn test_grid_points_exist() {
        assert!(GRID_POINTS.contains_key("NYC"));
        assert!(GRID_POINTS.contains_key("Dallas"));
        assert!(GRID_POINTS.contains_key("Miami"));
    }
}
