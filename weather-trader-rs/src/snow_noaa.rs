//! NOAA API client specifically for snowfall data
use crate::{Result, TradingError};
use crate::snow_models::{SnowForecast, SnowConfidence};
use serde::Deserialize;
use regex::Regex;

#[derive(Debug, Deserialize)]
struct ForecastResponse {
    properties: ForecastProperties,
}

#[derive(Debug, Deserialize)]
struct ForecastProperties {
    periods: Vec<ForecastPeriod>,
}

#[derive(Debug, Deserialize)]
struct ForecastPeriod {
    name: String,
    #[serde(rename = "startTime")]
    start_time: String,
    #[serde(rename = "endTime")]
    end_time: String,
    #[serde(rename = "detailedForecast")]
    detailed_forecast: String,
    #[serde(rename = "shortForecast")]
    short_forecast: String,
    #[serde(rename = "probabilityOfPrecipitation")]
    pop: Option<ValueUnit>,
}

#[derive(Debug, Deserialize)]
struct ValueUnit {
    value: Option<f64>,
    #[serde(rename = "unitCode")]
    unit_code: String,
}

pub struct SnowNOAAClient {
    client: reqwest::Client,
}

impl SnowNOAAClient {
    pub fn new() -> Self {
        let client = reqwest::Client::builder()
            .user_agent("WeatherTrader-Snow/1.0")
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .expect("Failed to build HTTP client");
        
        Self { client }
    }
    
    /// Fetch snow forecast for a specific city/grid point
    pub async fn fetch_snow_forecast(
        &self,
        office: &str,
        grid_x: u32,
        grid_y: u32,
        city: &str,
    ) -> Result<Vec<SnowForecast>> {
        let url = format!(
            "https://api.weather.gov/gridpoints/{}/{},{}/forecast",
            office, grid_x, grid_y
        );
        
        let response = self.client.get(&url).send().await?;
        
        if !response.status().is_success() {
            return Err(TradingError::ApiError(
                format!("NOAA API error: {}", response.status())
            ));
        }
        
        let forecast: ForecastResponse = response.json().await?;
        let mut snow_forecasts = Vec::new();
        
        for period in forecast.properties.periods {
            // Check if this period mentions snow
            let forecast_text = format!("{} {}", period.short_forecast, period.detailed_forecast);
            
            if let Some(snow_data) = self.parse_snow_accumulation(&forecast_text) {
                let pop = period.pop.as_ref().and_then(|p| p.value).unwrap_or(0.0) / 100.0;
                
                snow_forecasts.push(SnowForecast {
                    city: city.to_string(),
                    date: period.start_time.split('T').next().unwrap_or("").to_string(),
                    min_accumulation: snow_data.0,
                    max_accumulation: snow_data.1,
                    probability: pop.max(0.5), // Minimum 50% if mentioned
                    confidence: self.assess_confidence(&forecast_text, pop),
                });
            }
        }
        
        Ok(snow_forecasts)
    }
    
    /// Parse snow accumulation from forecast text
    /// Returns (min_inches, max_inches) or None if no snow mentioned
    fn parse_snow_accumulation(&self, text: &str) -> Option<(f64, f64)> {
        let text_lower = text.to_lowercase();
        
        // Check if snow is mentioned
        if !text_lower.contains("snow") && !text_lower.contains("blizzard") {
            return None;
        }
        
        // Pattern: "X to Y inches" or "X-Y inches"
        let patterns = [
            // "1 to 3 inches possible"
            Regex::new(r"(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)\s+inch").ok()?,
            // "1-3 inches" 
            Regex::new(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s+inch").ok()?,
            // "around 2 inches"
            Regex::new(r"around\s+(\d+(?:\.\d+)?)\s+inch").ok()?,
            // "up to 5 inches"
            Regex::new(r"up to (\d+(?:\.\d+)?) inch").ok()?,
            // "less than 1 inch"
            Regex::new(r"less than (\d+(?:\.\d+)?) inch").ok()?,
        ];
        
        // Try main range patterns first
        if let Some(caps) = patterns[0].captures(&text_lower) {
            let min: f64 = caps[1].parse().ok()?;
            let max: f64 = caps[2].parse().ok()?;
            return Some((min, max));
        }
        
        if let Some(caps) = patterns[1].captures(&text_lower) {
            let min: f64 = caps[1].parse().ok()?;
            let max: f64 = caps[2].parse().ok()?;
            return Some((min, max));
        }
        
        // Single value patterns
        if let Some(caps) = patterns[2].captures(&text_lower) {
            let val: f64 = caps[1].parse().ok()?;
            return Some((val * 0.8, val * 1.2)); // ±20%
        }
        
        if let Some(caps) = patterns[3].captures(&text_lower) {
            let max: f64 = caps[1].parse().ok()?;
            return Some((0.0, max));
        }
        
        if let Some(caps) = patterns[4].captures(&text_lower) {
            let max: f64 = caps[1].parse().ok()?;
            return Some((0.0, max * 0.9));
        }
        
        // If snow/blizzard mentioned but no accumulation specified, assume trace
        if text_lower.contains("blizzard") || text_lower.contains("heavy snow") {
            return Some((6.0, 12.0)); // Default for heavy snow
        }
        
        None
    }
    
    /// Assess forecast confidence based on wording and POP
    fn assess_confidence(&self, text: &str, pop: f64) -> SnowConfidence {
        let text_lower = text.to_lowercase();
        
        // High confidence indicators
        if text_lower.contains("definite") 
            || text_lower.contains("certain")
            || pop > 0.9 {
            return SnowConfidence::High;
        }
        
        // Low confidence indicators  
        if text_lower.contains("chance")
            || text_lower.contains("possible")
            || text_lower.contains("isolated")
            || pop < 0.5 {
            return SnowConfidence::Low;
        }
        
        // Medium is default
        SnowConfidence::Medium
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_parse_snow_accumulation() {
        let client = SnowNOAAClient::new();
        
        // Test "X to Y inches"
        let text1 = "New snow accumulation of 1 to 3 inches possible";
        assert_eq!(client.parse_snow_accumulation(text1), Some((1.0, 3.0)));
        
        // Test "around X inches"
        let text2 = "Around 6 inches of snow expected";
        let result2 = client.parse_snow_accumulation(text2).unwrap();
        assert!(result2.0 > 4.0 && result2.1 < 8.0); // ±20%
        
        // Test blizzard with no specific amount
        let text3 = "Blizzard conditions expected";
        let result3 = client.parse_snow_accumulation(text3).unwrap();
        assert!(result3.0 >= 6.0); // Heavy snow default
        
        // Test no snow
        let text4 = "Partly cloudy with sunshine";
        assert_eq!(client.parse_snow_accumulation(text4), None);
    }
    
    #[test]
    fn test_assess_confidence() {
        let client = SnowNOAAClient::new();
        
        assert_eq!(client.assess_confidence("Certain snow", 0.95), SnowConfidence::High);
        assert_eq!(client.assess_confidence("Chance of snow", 0.3), SnowConfidence::Low);
        assert_eq!(client.assess_confidence("Snow likely", 0.7), SnowConfidence::Medium);
    }
}
