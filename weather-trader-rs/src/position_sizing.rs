use crate::models::SizingInput;

// Risk limits
const DEFAULT_KELLY: f64 = 0.05;
const MODERATE_EDGE_KELLY: f64 = 0.04;
const HIGH_EDGE_KELLY: f64 = 0.10;
const REDUCED_KELLY: f64 = 0.03;
const MAX_TOTAL_EXPOSURE: f64 = 0.30;
const MAX_CONCURRENT_POSITIONS: usize = 6;
const HIGH_EDGE_THRESHOLD: f64 = 0.25;
const MODERATE_EDGE_THRESHOLD: f64 = 0.20;

/// Calculate position size with dynamic risk management
pub fn calculate_position_size(input: &SizingInput) -> f64 {
    let SizingInput {
        edge,
        current_exposure,
        open_positions_count,
        days_to_resolution,
        similar_city_positions,
    } = *input;
    
    // Determine base Kelly from edge
    let mut kelly = if edge >= HIGH_EDGE_THRESHOLD {
        HIGH_EDGE_KELLY
    } else if edge < MODERATE_EDGE_THRESHOLD {
        MODERATE_EDGE_KELLY
    } else {
        DEFAULT_KELLY
    };
    
    // Reduce if near-term resolution
    if days_to_resolution < 1 {
        kelly *= 0.5; // 50% reduction for same-day
    } else if days_to_resolution == 1 {
        kelly *= 0.8; // 20% reduction for next-day
    }
    
    // Reduce if over-exposed
    if current_exposure >= 0.20 {
        kelly = REDUCED_KELLY;
    }
    
    // Block if max exposure or positions hit
    if current_exposure >= MAX_TOTAL_EXPOSURE {
        return 0.0;
    }
    
    if open_positions_count >= MAX_CONCURRENT_POSITIONS {
        return 0.0;
    }
    
    // Reduce if similar city exposure
    if similar_city_positions >= 2 {
        kelly *= 0.5;
    }
    
    // Final cap check
    let potential_exposure = current_exposure + kelly;
    if potential_exposure > MAX_TOTAL_EXPOSURE {
        kelly = MAX_TOTAL_EXPOSURE - current_exposure;
        if kelly < 0.01 {
            return 0.0;
        }
    }
    
    kelly.max(0.0).min(HIGH_EDGE_KELLY)
}

/// Calculate contract quantity
pub fn calculate_contract_quantity(kelly: f64, bankroll: f64, market_price: f64) -> u32 {
    if kelly <= 0.0 || market_price <= 0.0 {
        return 0;
    }
    
    let position_value = kelly * bankroll;
    let quantity = (position_value / market_price) as u32;
    
    if quantity < 1 {
        return 0;
    }
    
    // Max 15% single position
    let max_value = bankroll * 0.15;
    let max_qty = (max_value / market_price) as u32;
    
    quantity.min(max_qty)
}

#[cfg(test)]
mod tests {
    use super::*;
    
    fn sizing(edge: f64, exposure: f64, positions: usize, days: i64, similar: usize) -> SizingInput {
        SizingInput {
            edge,
            current_exposure: exposure,
            open_positions_count: positions,
            days_to_resolution: days,
            similar_city_positions: similar,
        }
    }
    
    #[test]
    fn test_15_percent_edge() {
        let input = sizing(0.15, 0.0, 0, 3, 0);
        assert_eq!(calculate_position_size(&input), 0.04);
    }
    
    #[test]
    fn test_20_percent_edge() {
        let input = sizing(0.20, 0.0, 0, 3, 0);
        assert_eq!(calculate_position_size(&input), 0.05);
    }
    
    #[test]
    fn test_25_percent_edge() {
        let input = sizing(0.25, 0.0, 0, 3, 0);
        assert_eq!(calculate_position_size(&input), 0.10);
    }
    
    #[test]
    fn test_reduced_at_20_exposure() {
        let input = sizing(0.20, 0.20, 2, 2, 0);
        assert_eq!(calculate_position_size(&input), 0.03);
    }
    
    #[test]
    fn test_blocked_at_30_exposure() {
        let input = sizing(0.30, 0.30, 3, 2, 0);
        assert_eq!(calculate_position_size(&input), 0.0);
    }
    
    #[test]
    fn test_blocked_at_6_positions() {
        let input = sizing(0.25, 0.15, 6, 2, 0);
        assert_eq!(calculate_position_size(&input), 0.0);
    }
    
    #[test]
    fn test_same_day_reduction() {
        let input = sizing(0.20, 0.0, 0, 0, 0);
        assert_eq!(calculate_position_size(&input), 0.025);
    }
    
    #[test]
    fn test_next_day_reduction() {
        let input = sizing(0.20, 0.0, 0, 1, 0);
        assert!((calculate_position_size(&input) - 0.04).abs() < 0.0001);
    }
    
    #[test]
    fn test_similar_city_reduction() {
        let input = sizing(0.20, 0.0, 2, 2, 2);
        assert!((calculate_position_size(&input) - 0.025).abs() < 0.0001);
    }
    
    #[test]
    fn test_contract_quantity_basic() {
        // 5% of $100 = $5 / $0.40 = 12.5 → 12
        assert_eq!(calculate_contract_quantity(0.05, 100.0, 0.40), 12);
    }
    
    #[test]
    fn test_contract_quantity_zero() {
        assert_eq!(calculate_contract_quantity(0.0, 100.0, 0.40), 0);
        assert_eq!(calculate_contract_quantity(0.05, 100.0, 0.0), 0);
    }
    
    #[test]
    fn test_contract_quantity_max_cap() {
        // 10% Kelly but 15% max = $15 / $0.10 = 150
        // But 10% of $100 = $10, so 100 contracts
        assert_eq!(calculate_contract_quantity(0.10, 100.0, 0.10), 100);
    }
}
