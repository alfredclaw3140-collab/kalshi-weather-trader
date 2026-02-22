//! Kalshi API client with RSA authentication
use crate::{Result, TradingError};
use crate::models::{MarketInfo, Side};
use chrono::{DateTime, Utc};
use rsa::{pkcs1::DecodeRsaPrivateKey, pkcs8::DecodePrivateKey, RsaPrivateKey};
use rsa::pss::Pss;
use rsa::signature::{SignatureEncoding, Signer};
use sha2::Sha256;
use serde::{Deserialize, Serialize};
use serde_json::json;
use rand::rngs::OsRng;

const KALSHI_BASE: &str = "https://api.elections.kalshi.com";

#[derive(Debug, Deserialize)]
struct KalshiMarket {
    ticker: String,
    title: String,
    yes_ask: Option<i64>,
    yes_bid: Option<i64>,
    last_price: Option<i64>,
    #[serde(rename = "close_date")]
    close_date: Option<String>,
}

#[derive(Debug, Deserialize)]
struct KalshiMarketResponse {
    market: KalshiMarket,
}

#[derive(Debug, Deserialize)]
struct KalshiMarketsResponse {
    markets: Vec<KalshiMarket>,
}

pub struct KalshiClient {
    client: reqwest::Client,
    private_key: Option<RsaPrivateKey>,
    key_id: Option<String>,
}

impl KalshiClient {
    pub fn new() -> Self {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .expect("Failed to build HTTP client");
        
        Self {
            client,
            private_key: None,
            key_id: None,
        }
    }
    
    pub fn with_auth(mut self, private_key_pem: &str, key_id: &str) -> Result<Self> {
        // Try PKCS#8 format first, then PKCS#1
        let private_key = RsaPrivateKey::from_pkcs8_pem(private_key_pem)
            .or_else(|_| RsaPrivateKey::from_pkcs1_pem(private_key_pem))
            .map_err(|e| TradingError::AuthError(format!("Failed to parse private key: {}", e)))?;
        
        self.private_key = Some(private_key);
        self.key_id = Some(key_id.to_string());
        Ok(self)
    }
    
    fn generate_auth_headers(&self, method: &str, path: &str) -> Result<Vec<(String, String)>> {
        let Some(ref key) = self.private_key else {
            return Err(TradingError::AuthError("No private key configured".to_string()));
        };
        
        let timestamp = Utc::now().timestamp().to_string();
        let msg = format!("{}{}{}", timestamp, method.to_uppercase(), path);
        
        // Sign with RSA-PSS using SHA256
        let mut rng = OsRng;
        let signature = key.sign_with_rng(&mut rng, Pss::new::<Sha256>(), msg.as_bytes())
            .map_err(|e| TradingError::AuthError(format!("Signing failed: {}", e)))?;
        
        let signature_b64 = base64::encode(&signature);
        
        Ok(vec![
            ("KALSHI-ACCESS-KEY".to_string(), self.key_id.clone().unwrap()),
            ("KALSHI-ACCESS-TIMESTAMP".to_string(), timestamp),
            ("KALSHI-ACCESS-SIGNATURE".to_string(), signature_b64),
        ])
    }
    
    pub async fn get_market(&self, ticker: &str) -> Result<MarketInfo> {
        let path = format!("/trade-api/v2/markets/{}", ticker);
        let url = format!("{}{}", KALSHI_BASE, path);
        
        let mut request = self.client.get(&url);
        
        if self.private_key.is_some() {
            let headers = self.generate_auth_headers("GET", &path)?;
            for (key, value) in headers {
                request = request.header(&key, value);
            }
        }
        
        let response = request.send().await?;
        
        if !response.status().is_success() {
            return Err(TradingError::ApiError(
                format!("Kalshi API error: {}", response.status())
            ));
        }
        
        let market_resp: KalshiMarketResponse = response.json().await?;
        let market = market_resp.market;
        
        Ok(MarketInfo {
            ticker: market.ticker,
            title: market.title,
            yes_ask: market.yes_ask.map(|p| p as f64 / 100.0).unwrap_or(0.0),
            yes_bid: market.yes_bid.map(|p| p as f64 / 100.0).unwrap_or(0.0),
            last_price: market.last_price.map(|p| p as f64 / 100.0).unwrap_or(0.0),
            expiration_date: market.close_date
                .and_then(|d| DateTime::parse_from_rfc3339(&d).ok())
                .map(|d| d.with_timezone(&Utc))
                .unwrap_or_else(Utc::now),
        })
    }
    
    pub async fn get_markets_by_series(&self, series_ticker: &str) -> Result<Vec<MarketInfo>> {
        let path = "/trade-api/v2/markets";
        let url = format!("{}{}?series_ticker={}&status=open", KALSHI_BASE, path, series_ticker);
        
        let mut request = self.client.get(&url);
        
        if self.private_key.is_some() {
            let headers = self.generate_auth_headers("GET", path)?;
            for (key, value) in headers {
                request = request.header(&key, value);
            }
        }
        
        let response = request.send().await?;
        
        if !response.status().is_success() {
            return Err(TradingError::ApiError(
                format!("Kalshi API error: {}", response.status())
            ));
        }
        
        let markets_resp: KalshiMarketsResponse = response.json().await?;
        
        Ok(markets_resp.markets.into_iter().map(|market| MarketInfo {
            ticker: market.ticker,
            title: market.title,
            yes_ask: market.yes_ask.map(|p| p as f64 / 100.0).unwrap_or(0.0),
            yes_bid: market.yes_bid.map(|p| p as f64 / 100.0).unwrap_or(0.0),
            last_price: market.last_price.map(|p| p as f64 / 100.0).unwrap_or(0.0),
            expiration_date: market.close_date
                .and_then(|d| DateTime::parse_from_rfc3339(&d).ok())
                .map(|d| d.with_timezone(&Utc))
                .unwrap_or_else(Utc::now),
        }).collect())
    }
    
    pub async fn place_order(
        &self,
        ticker: &str,
        side: Side,
        contracts: u32,
        price: f64,
    ) -> Result<String> {
        let path = "/trade-api/v2/orders";
        let url = format!("{}{}", KALSHI_BASE, path);
        
        let side_str = match side {
            Side::Yes => "yes",
            Side::No => "no",
        };
        
        let body = json!({
            "ticker": ticker,
            "side": side_str,
            "count": contracts,
            "price": (price * 100.0) as i64, // Convert to cents
            "type": "limit",
        });
        
        let mut request = self.client.post(&url).json(&body);
        
        if self.private_key.is_some() {
            let headers = self.generate_auth_headers("POST", path)?;
            for (key, value) in headers {
                request = request.header(&key, value);
            }
        }
        
        let response = request.send().await?;
        
        if !response.status().is_success() {
            let text = response.text().await.unwrap_or_default();
            return Err(TradingError::ApiError(
                format!("Order failed: {}", text)
            ));
        }
        
        Ok(format!("Order placed: {} {} @ {}", contracts, side_str, price))
    }
    
    pub async fn get_balance(&self) -> Result<f64> {
        let path = "/trade-api/v2/portfolio/balance";
        let url = format!("{}{}", KALSHI_BASE, path);
        
        let mut request = self.client.get(&url);
        
        if self.private_key.is_some() {
            let headers = self.generate_auth_headers("GET", path)?;
            for (key, value) in headers {
                request = request.header(&key, value);
            }
        }
        
        let response = request.send().await?;
        
        if !response.status().is_success() {
            return Err(TradingError::ApiError(
                format!("Balance check failed: {}", response.status())
            ));
        }
        
        #[derive(Deserialize)]
        struct BalanceResponse {
            balance: i64,
        }
        
        let balance: BalanceResponse = response.json().await?;
        Ok(balance.balance as f64 / 100.0) // Convert cents to dollars
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_kalshi_client_creation() {
        let _client = KalshiClient::new();
        assert!(true); // Just verify no panic
    }
}
