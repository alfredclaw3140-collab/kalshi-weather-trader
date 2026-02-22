//! Web Dashboard for monitoring the trading bot
use std::sync::Arc;
use tokio::sync::RwLock;
use warp::Filter;
use serde::Serialize;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Serialize)]
pub struct DashboardState {
    pub last_scan: Option<DateTime<Utc>>,
    pub opportunities_found: u32,
    pub trades_executed: u32,
    pub positions_open: u32,
    pub total_pnl: f64,
    pub account_balance: f64,
    pub bot_status: String,
}

impl Default for DashboardState {
    fn default() -> Self {
        Self {
            last_scan: None,
            opportunities_found: 0,
            trades_executed: 0,
            positions_open: 0,
            total_pnl: 0.0,
            account_balance: 100.0,
            bot_status: "Initializing".to_string(),
        }
    }
}

pub struct Dashboard {
    state: Arc<RwLock<DashboardState>>,
}

impl Dashboard {
    pub fn new() -> Self {
        Self {
            state: Arc::new(RwLock::new(DashboardState::default())),
        }
    }
    
    pub fn get_state(&self) -> Arc<RwLock<DashboardState>> {
        self.state.clone()
    }
    
    pub async fn run(self, port: u16) {
        let state = self.state.clone();
        
        // API routes
        let api_status = warp::path!("api" / "status")
            .and(with_state(state.clone()))
            .and_then(handle_status);
        
        let api_positions = warp::path!("api" / "positions")
            .and_then(handle_positions);
        
        // Static dashboard HTML
        let dashboard = warp::path::end()
            .map(|| warp::reply::html(DASHBOARD_HTML));
        
        let routes = api_status
            .or(api_positions)
            .or(dashboard);
        
        println!("🌐 Dashboard running at http://localhost:{}", port);
        warp::serve(routes).run(([127, 0, 0, 1], port)).await;
    }
}

fn with_state(state: Arc<RwLock<DashboardState>>) -> impl Filter<Extract = (Arc<RwLock<DashboardState>>,), Error = std::convert::Infallible> + Clone {
    warp::any().map(move || state.clone())
}

async fn handle_status(state: Arc<RwLock<DashboardState>>) -> Result<impl warp::Reply, warp::Rejection> {
    let state = state.read().await;
    Ok(warp::reply::json(&*state))
}

async fn handle_positions() -> Result<impl warp::Reply, warp::Rejection> {
    let positions: Vec<serde_json::Value> = vec![];
    Ok(warp::reply::json(&positions))
}

const DASHBOARD_HTML: &str = r#"
<!DOCTYPE html>
<html>
<head>
    <title>Weather Trading Bot Dashboard</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        h1 { margin: 0; color: #4fc3f7; }
        .status { padding: 8px 16px; border-radius: 20px; font-weight: bold; }
        .status.running { background: #4caf50; }
        .status.paused { background: #ff9800; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card { background: #16213e; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        .card h3 { margin-top: 0; color: #4fc3f7; font-size: 14px; text-transform: uppercase; }
        .card .value { font-size: 32px; font-weight: bold; margin: 10px 0; }
        .card .positive { color: #4caf50; }
        .card .negative { color: #f44336; }
        .refresh { text-align: center; color: #888; font-size: 12px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌦️ Weather Trading Bot</h1>
        <span id="bot-status" class="status running">Running</span>
    </div>
    
    <div class="grid">
        <div class="card">
            <h3>Account Balance</h3>
            <div id="balance" class="value">$100.00</div>
        </div>
        <div class="card">
            <h3>Open Positions</h3>
            <div id="positions" class="value">0</div>
        </div>
        <div class="card">
            <h3>Total P&L</h3>
            <div id="pnl" class="value positive">+$0.00</div>
        </div>
        <div class="card">
            <h3>Opportunities Today</h3>
            <div id="opportunities" class="value">0</div>
        </div>
    </div>
    
    <div class="refresh">Last updated: <span id="last-update">Never</span></div>
    
    <script>
        async function updateDashboard() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                document.getElementById('balance').textContent = '$' + data.account_balance.toFixed(2);
                document.getElementById('positions').textContent = data.positions_open;
                document.getElementById('opportunities').textContent = data.opportunities_found;
                
                const pnlEl = document.getElementById('pnl');
                const pnl = data.total_pnl;
                pnlEl.textContent = (pnl >= 0 ? '+$' : '-$') + Math.abs(pnl).toFixed(2);
                pnlEl.className = 'value ' + (pnl >= 0 ? 'positive' : 'negative');
                
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
            } catch (e) {
                console.error('Failed to update:', e);
            }
        }
        
        updateDashboard();
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>
"#;

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_dashboard_state() {
        let state = DashboardState::default();
        assert_eq!(state.account_balance, 100.0);
    }
}
