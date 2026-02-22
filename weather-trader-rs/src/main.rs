//! Weather Trading Bot - Rust Edition - ALL WEATHER MARKETS + WIND
use weather_trader::{
    KalshiClient, TradingBot, Config, 
    SnowTrader, RainTrader, SevereWeatherTrader, WindHumidityTrader
};
use weather_trader::dashboard::Dashboard;
use weather_trader::bls::BLSClient;
use tracing::{info, error, Level};
use tracing_subscriber;
use tokio::time::{interval, Duration};
use std::sync::Arc;
use std::env;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt().with_max_level(Level::INFO).init();
    
    info!("🌦️  Weather Trading Bot - Rust Edition v0.4.0");
    info!("================================================");
    info!("📡 Trading ALL weather: Temps | Snow | Rain | Severe | WIND");
    
    let config = Config::load().unwrap_or_default();
    
    let dry_run = env::var("DRY_RUN").map(|v| v != "false").unwrap_or(config.trading.dry_run);
    let bankroll = env::var("BANKROLL").ok().and_then(|v| v.parse().ok()).unwrap_or(config.trading.bankroll);
    let enable_dashboard = env::var("DASHBOARD").map(|v| v == "true").unwrap_or(true);
    
    info!("\n📊 Configuration:");
    info!("  Bankroll: ${:.2}", bankroll);
    info!("  Mode: {}", if dry_run { "🔒 DRY RUN" } else { "🔴 LIVE TRADING" });
    info!("  Check Interval: {} minutes", config.trading.check_interval_minutes);
    
    // Check for upcoming economic events
    let bls = BLSClient::new();
    let upcoming = bls.get_upcoming_high_impact_events();
    if !upcoming.is_empty() {
        info!("\n📅 Upcoming High-Impact Economic Events:");
        for event in upcoming {
            info!("  {} - {} (expectation: {:.1})", 
                event.date.format("%Y-%m-%d %H:%M"), event.name, event.market_expectation);
        }
    }
    
    // Initialize Kalshi client
    let kalshi = match config.load_credentials() {
        Ok((key_id, private_key)) => {
            info!("✅ Loaded credentials");
            KalshiClient::new().with_auth(&private_key, &key_id)?
        }
        Err(e) => {
            info!("⚠️  Could not load credentials: {}", e);
            KalshiClient::new()
        }
    };
    
    let kalshi = Arc::new(kalshi);
    
    // Create all traders
    let temp_bot = Arc::new(TradingBot::new((*kalshi).clone(), bankroll, config.trading.edge_threshold, dry_run));
    let snow_bot = Arc::new(SnowTrader::new((*kalshi).clone(), bankroll, dry_run));
    let rain_bot = Arc::new(RainTrader::new((*kalshi).clone(), bankroll, dry_run));
    let severe_bot = Arc::new(SevereWeatherTrader::new((*kalshi).clone(), bankroll, dry_run));
    let wind_bot = Arc::new(WindHumidityTrader::new((*kalshi).clone(), bankroll, dry_run));
    
    // Print account summary
    match temp_bot.get_account_summary().await {
        Ok(summary) => info!("\n{}", summary),
        Err(e) => info!("\n⚠️  Could not fetch account: {}", e),
    }
    
    // Start dashboard
    if enable_dashboard {
        let dashboard = Dashboard::new();
        let _handle = tokio::spawn(async move { dashboard.run(8080).await; });
        info!("\n🌐 Dashboard: http://localhost:8080");
    }
    
    // Run all scans
    run_all_scans(&temp_bot, &snow_bot, &rain_bot, &severe_bot, &wind_bot).await;
    
    // Set up periodic scanning
    let mut ticker = interval(Duration::from_secs(config.trading.check_interval_minutes * 60));
    
    info!("\n⏰ Starting automated scanning every {} minutes...", config.trading.check_interval_minutes);
    
    loop {
        ticker.tick().await;
        run_all_scans(&temp_bot, &snow_bot, &rain_bot, &severe_bot, &wind_bot).await;
    }
}

async fn run_all_scans(
    temp: &Arc<TradingBot>,
    snow: &Arc<SnowTrader>,
    rain: &Arc<RainTrader>,
    severe: &Arc<SevereWeatherTrader>,
    wind: &Arc<WindHumidityTrader>,
) {
    let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S");
    
    // Temperature scan
    info!("\n🌡️  [{}] TEMPERATURE scan...", now);
    match temp.scan_for_opportunities().await {
        Ok(opps) => report_opportunities("Temperature", opps),
        Err(e) => error!("  ❌ Error: {}", e),
    }
    
    // Snow scan
    info!("\n❄️  [{}] SNOW scan...", now);
    match snow.scan_snow_opportunities().await {
        Ok(opps) => report_opportunities("Snow", opps),
        Err(e) => error!("  ❌ Error: {}", e),
    }
    
    // Rain scan
    info!("\n🌧️  [{}] RAIN scan...", now);
    match rain.scan_rain_opportunities().await {
        Ok(opps) => report_opportunities("Rain", opps),
        Err(e) => error!("  ❌ Error: {}", e),
    }
    
    // Severe weather scan
    info!("\n🌪️  [{}] SEVERE WEATHER scan...", now);
    match severe.scan_severe_opportunities().await {
        Ok(opps) => report_opportunities("Severe", opps),
        Err(e) => error!("  ❌ Error: {}", e),
    }
    
    // Wind scan
    info!("\n💨  [{}] WIND scan...", now);
    match wind.scan_wind_opportunities().await {
        Ok(opps) => report_opportunities("Wind", opps),
        Err(e) => error!("  ❌ Error: {}", e),
    }
}

fn report_opportunities(category: &str, opps: Vec<impl std::fmt::Debug>) {
    if opps.is_empty() {
        info!("  No {} opportunities found", category);
    } else {
        info!("  ✅ Found {} {} opportunities", opps.len(), category);
    }
}
