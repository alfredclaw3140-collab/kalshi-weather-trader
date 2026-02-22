//! Weather Trading Bot - Rust Edition
use weather_trader::{KalshiClient, TradingBot, Config, SnowTrader};
use weather_trader::dashboard::Dashboard;
use weather_trader::bls::BLSClient;
use tracing::{info, error, Level};
use tracing_subscriber;
use tokio::time::{interval, Duration};
use std::sync::Arc;
use std::env;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_max_level(Level::INFO)
        .init();
    
    info!("🌦️  Weather Trading Bot - Rust Edition v0.2.0");
    info!("================================================");
    
    // Load configuration
    let config = Config::load().unwrap_or_default();
    
    // Check for environment variable overrides
    let dry_run = env::var("DRY_RUN")
        .map(|v| v != "false")
        .unwrap_or(config.trading.dry_run);
    
    let bankroll = env::var("BANKROLL")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(config.trading.bankroll);
    
    let enable_dashboard = env::var("DASHBOARD")
        .map(|v| v == "true")
        .unwrap_or(true);
    
    let enable_snow = env::var("SNOW")
        .map(|v| v != "false")
        .unwrap_or(true);
    
    info!("\n📊 Configuration:");
    info!("  Bankroll: ${:.2}", bankroll);
    info!("  Edge Threshold: {:.0}%", config.trading.edge_threshold * 100.0);
    info!("  Mode: {}", if dry_run { "🔒 DRY RUN" } else { "🔴 LIVE TRADING" });
    info!("  Check Interval: {} minutes", config.trading.check_interval_minutes);
    info!("  Snow Trading: {}", if enable_snow { "❄️ ENABLED" } else { "disabled" });
    
    // Check for upcoming economic events
    let bls = BLSClient::new();
    let upcoming = bls.get_upcoming_high_impact_events();
    if !upcoming.is_empty() {
        info!("\n📅 Upcoming High-Impact Economic Events:");
        for event in upcoming {
            info!("  {} - {} (expectation: {:.1})", 
                event.date.format("%Y-%m-%d %H:%M"),
                event.name,
                event.market_expectation
            );
        }
    }
    
    // Initialize Kalshi client with credentials
    let kalshi = match config.load_credentials() {
        Ok((key_id, private_key)) => {
            info!("✅ Loaded credentials from ~/.config/kalshi/credentials.json");
            info!("   Key ID: {}...", &key_id[..8.min(key_id.len())]);
            KalshiClient::new().with_auth(&private_key, &key_id)?
        }
        Err(e) => {
            info!("⚠️  Could not load credentials: {}", e);
            info!("   Running in demo mode (no trades will execute)");
            KalshiClient::new()
        }
    };
    
    let kalshi = Arc::new(kalshi);
    
    // Create temperature trading bot
    let temp_bot = Arc::new(TradingBot::new(
        (*kalshi).clone(), 
        bankroll, 
        config.trading.edge_threshold, 
        dry_run
    ));
    
    // Create snow trading bot
    let snow_bot = Arc::new(SnowTrader::new(
        (*kalshi).clone(),
        bankroll,
        dry_run
    ));
    
    // Print account summary if authenticated
    match temp_bot.get_account_summary().await {
        Ok(summary) => info!("\n{}", summary),
        Err(e) => info!("\n⚠️  Could not fetch account: {}", e),
    }
    
    // Start dashboard if enabled
    if enable_dashboard {
        let dashboard = Dashboard::new();
        let _dashboard_handle = tokio::spawn(async move {
            dashboard.run(8080).await;
        });
        info!("\n🌐 Dashboard: http://localhost:8080");
    }
    
    // Run initial scans
    run_temp_scan(&temp_bot).await;
    if enable_snow {
        run_snow_scan(&snow_bot).await;
    }
    
    // Set up periodic scanning
    let mut ticker = interval(Duration::from_secs(config.trading.check_interval_minutes * 60));
    
    info!("\n⏰ Starting automated scanning every {} minutes...", config.trading.check_interval_minutes);
    info!("Press Ctrl+C to stop\n");
    
    loop {
        ticker.tick().await;
        run_temp_scan(&temp_bot).await;
        if enable_snow {
            run_snow_scan(&snow_bot).await;
        }
    }
}

async fn run_temp_scan(bot: &Arc<TradingBot>) {
    info!("\n🌡️  [{}] Running TEMPERATURE market scan...", chrono::Local::now().format("%Y-%m-%d %H:%M:%S"));
    
    match bot.scan_for_opportunities().await {
        Ok(opportunities) => {
            if opportunities.is_empty() {
                info!("  No temperature opportunities found");
            } else {
                info!("  ✅ Found {} temperature opportunities:", opportunities.len());
                
                for opp in &opportunities {
                    info!("    {}: {} side, {:.1}% edge, ${:.2} price", 
                        opp.market_ticker, opp.side, opp.edge * 100.0, opp.market_price);
                    
                    if opp.edge >= 0.20 {
                        match bot.execute_trade(opp, &[]).await {
                            Ok(result) => info!("      → {}", result),
                            Err(e) => error!("      → Trade failed: {}", e),
                        }
                    }
                }
            }
        }
        Err(e) => error!("  ❌ Temperature scan error: {}", e),
    }
}

async fn run_snow_scan(bot: &Arc<SnowTrader>) {
    info!("\n❄️  [{}] Running SNOW market scan...", chrono::Local::now().format("%Y-%m-%d %H:%M:%S"));
    
    match bot.scan_snow_opportunities().await {
        Ok(opportunities) => {
            if opportunities.is_empty() {
                info!("  No snow opportunities found");
            } else {
                info!("  ✅ Found {} snow opportunities:", opportunities.len());
                
                for opp in &opportunities {
                    info!("    {}: {} side, {:.1}% edge, {:.1}\" threshold", 
                        opp.market.ticker, 
                        opp.recommended_side, 
                        opp.edge * 100.0,
                        opp.market.threshold);
                    
                    if opp.edge >= 0.25 {
                        match bot.execute_snow_trade(opp).await {
                            Ok(result) => info!("      → {}", result),
                            Err(e) => error!("      → Snow trade failed: {}", e),
                        }
                    }
                }
            }
        }
        Err(e) => error!("  ❌ Snow scan error: {}", e),
    }
}
