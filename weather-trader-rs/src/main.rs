//! Weather Trading Bot - Rust Edition
use weather_trader::{KalshiClient, TradingBot};
use tracing::{info, Level};
use tracing_subscriber;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_max_level(Level::INFO)
        .init();
    
    info!("🌦️  Weather Trading Bot - Rust Edition");
    info!("=====================================");
    
    // Load configuration
    let bankroll = 100.0;
    let edge_threshold = 0.15;
    let dry_run = true; // Start in dry run mode
    
    // Initialize Kalshi client
    // In production, load from credentials file
    let kalshi = KalshiClient::new();
    
    // Create trading bot
    let bot = TradingBot::new(kalshi, bankroll, edge_threshold, dry_run);
    
    // Print account summary
    match bot.get_account_summary().await {
        Ok(summary) => info!("\n{}", summary),
        Err(e) => info!("Could not fetch account: {}", e),
    }
    
    // Scan for opportunities
    info!("\n🔍 Scanning markets...");
    
    match bot.scan_for_opportunities().await {
        Ok(opportunities) => {
            info!("\nFound {} opportunities", opportunities.len());
            
            for opp in &opportunities {
                info!(
                    "  {}: {} side, {:.1}% edge, {} days to resolution",
                    opp.market_ticker, opp.side, opp.edge * 100.0, opp.days_to_resolution
                );
            }
        }
        Err(e) => {
            info!("Error scanning markets: {}", e);
        }
    }
    
    info!("\n✅ Scan complete");
    
    Ok(())
}
