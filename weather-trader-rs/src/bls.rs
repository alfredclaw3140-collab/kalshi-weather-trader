//! BLS (Bureau of Labor Statistics) Economic Data Module
//! Fetches jobs reports, CPI, and other economic indicators

use crate::{Result, TradingError};
use chrono::{DateTime, Utc, Datelike};
use serde::Deserialize;

const BLS_BASE: &str = "https://api.bls.gov/publicAPI/v2/timeseries/data";

#[derive(Debug, Clone)]
pub struct EconomicEvent {
    pub name: String,
    pub date: DateTime<Utc>,
    pub series_id: String,
    pub market_expectation: f64,
    pub actual_value: Option<f64>,
    pub importance: Importance,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Importance {
    Low,
    Medium,
    High,
}

impl std::fmt::Display for Importance {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Importance::Low => write!(f, "Low"),
            Importance::Medium => write!(f, "Medium"),
            Importance::High => write!(f, "🔴 High"),
        }
    }
}

pub struct BLSClient {
    client: reqwest::Client,
    api_key: Option<String>,
}

impl BLSClient {
    pub fn new() -> Self {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .expect("Failed to build HTTP client");
        
        Self {
            client,
            api_key: std::env::var("BLS_API_KEY").ok(),
        }
    }
    
    /// Get upcoming economic releases for the current month
    pub fn get_monthly_releases(&self) -> Vec<EconomicEvent> {
        let now = Utc::now();
        let year = now.year();
        let month = now.month();
        
        vec![
            // Non-Farm Payrolls (Jobs Report) - First Friday of month
            EconomicEvent {
                name: "Non-Farm Payrolls".to_string(),
                date: get_first_friday(year, month),
                series_id: "CES0000000001".to_string(),
                market_expectation: 200.0, // thousands of jobs
                actual_value: None,
                importance: Importance::High,
            },
            // CPI (Consumer Price Index) - Usually around 13th
            EconomicEvent {
                name: "CPI (Inflation)".to_string(),
                date: get_nth_day_of_month(year, month, 13),
                series_id: "CUUR0000SA0".to_string(),
                market_expectation: 3.2, // percent change
                actual_value: None,
                importance: Importance::High,
            },
            // Unemployment Rate
            EconomicEvent {
                name: "Unemployment Rate".to_string(),
                date: get_first_friday(year, month),
                series_id: "LNS14000000".to_string(),
                market_expectation: 4.0, // percent
                actual_value: None,
                importance: Importance::High,
            },
            // PPI (Producer Price Index)
            EconomicEvent {
                name: "PPI".to_string(),
                date: get_nth_day_of_month(year, month, 14),
                series_id: "WPUFD4".to_string(),
                market_expectation: 2.5,
                actual_value: None,
                importance: Importance::Medium,
            },
        ]
    }
    
    /// Check for high-importance events in the next 7 days
    pub fn get_upcoming_high_impact_events(&self) -> Vec<EconomicEvent> {
        let now = Utc::now();
        let week_from_now = now + chrono::Duration::days(7);
        
        self.get_monthly_releases()
            .into_iter()
            .filter(|e| {
                e.importance == Importance::High 
                && e.date >= now 
                && e.date <= week_from_now
            })
            .collect()
    }
    
    /// Fetch actual data from BLS API
    pub async fn fetch_economic_data(&self, series_id: &str) -> Result<Option<f64>> {
        // If no API key, return None (we'll use scheduled estimates)
        if self.api_key.is_none() {
            return Ok(None);
        }
        
        let url = format!("{}", BLS_BASE);
        let body = serde_json::json!({
            "seriesid": [series_id],
            "registrationkey": self.api_key.as_ref().unwrap(),
            "startyear": (Utc::now().year() - 1).to_string(),
            "endyear": Utc::now().year().to_string(),
        });
        
        let response = self.client
            .post(&url)
            .json(&body)
            .send()
            .await?;
        
        if !response.status().is_success() {
            return Err(TradingError::ApiError(
                format!("BLS API error: {}", response.status())
            ));
        }
        
        // Parse response (simplified)
        #[derive(Deserialize)]
        struct BLSResponse {
            Results: Results,
        }
        
        #[derive(Deserialize)]
        struct Results {
            series: Vec<Series>,
        }
        
        #[derive(Deserialize)]
        struct Series {
            data: Vec<DataPoint>,
        }
        
        #[derive(Deserialize)]
        struct DataPoint {
            value: String,
        }
        
        let bls_data: BLSResponse = response.json().await?;
        
        // Get most recent value
        if let Some(series) = bls_data.Results.series.first() {
            if let Some(latest) = series.data.first() {
                return Ok(latest.value.parse().ok());
            }
        }
        
        Ok(None)
    }
}

fn get_first_friday(year: i32, month: u32) -> DateTime<Utc> {
    // First day of month
    let mut day = 1;
    while day <= 7 {
        let date = chrono::NaiveDate::from_ymd_opt(year, month, day).unwrap();
        if date.weekday() == chrono::Weekday::Fri {
            return DateTime::from_naive_utc_and_offset(
                date.and_hms_opt(8, 30, 0).unwrap(),
                Utc
            );
        }
        day += 1;
    }
    Utc::now()
}

fn get_nth_day_of_month(year: i32, month: u32, n: u32) -> DateTime<Utc> {
    let date = chrono::NaiveDate::from_ymd_opt(year, month, n).unwrap_or_else(|| {
        chrono::NaiveDate::from_ymd_opt(year, month, 1).unwrap()
    });
    DateTime::from_naive_utc_and_offset(
        date.and_hms_opt(8, 30, 0).unwrap(),
        Utc
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_bls_client_creation() {
        let _client = BLSClient::new();
    }
    
    #[test]
    fn test_get_monthly_releases() {
        let client = BLSClient::new();
        let releases = client.get_monthly_releases();
        assert!(!releases.is_empty());
        
        // Should have NFP
        assert!(releases.iter().any(|r| r.name == "Non-Farm Payrolls"));
    }
}
