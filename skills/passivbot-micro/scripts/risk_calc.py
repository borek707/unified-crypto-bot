#!/usr/bin/env python3
"""
Risk Calculator Script
======================
Calculate trading risk metrics and position sizes.

Usage:
    python risk_calc.py --entry 50000 --leverage 5 --side long
    python risk_calc.py --balance 100 --price 50000 --risk 0.02
"""

import argparse
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OrderSide(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class RiskMetrics:
    """Risk metrics for a position."""
    liquidation_price: float
    margin_required: float
    break_even_price: float
    position_value: float
    max_loss_usd: float
    risk_reward_ratio: float


class RiskCalculator:
    """Utility class for risk calculations."""
    
    MAINTENANCE_MARGIN_RATE = 0.005  # 0.5%
    
    @staticmethod
    def calculate_liquidation_price(
        entry_price: float,
        side: OrderSide,
        leverage: float,
        maintenance_margin_rate: float = 0.005
    ) -> float:
        """
        Calculate liquidation price for a position.
        
        Formula (long): liq_price = entry * (1 - (1 - mmr) / leverage)
        Formula (short): liq_price = entry * (1 + (1 - mmr) / leverage)
        """
        if side == OrderSide.LONG:
            return entry_price * (1 - (1 - maintenance_margin_rate) / leverage)
        else:
            return entry_price * (1 + (1 - maintenance_margin_rate) / leverage)
    
    @staticmethod
    def calculate_margin_required(
        position_size: float,
        price: float,
        leverage: float
    ) -> float:
        """Calculate margin required for a position."""
        return position_size * price / leverage
    
    @staticmethod
    def calculate_pnl(
        entry_price: float,
        current_price: float,
        size: float,
        side: OrderSide,
        fees_paid: float = 0.0
    ) -> float:
        """Calculate realized or unrealized PnL."""
        if side == OrderSide.LONG:
            return (current_price - entry_price) * size - fees_paid
        else:
            return (entry_price - current_price) * size - fees_paid
    
    @staticmethod
    def calculate_break_even_price(
        entry_price: float,
        fees_pct: float = 0.0005,
        side: OrderSide = OrderSide.LONG
    ) -> float:
        """Calculate price at which position breaks even after fees."""
        if side == OrderSide.LONG:
            return entry_price * (1 + fees_pct * 2)
        else:
            return entry_price * (1 - fees_pct * 2)
    
    @staticmethod
    def calculate_position_size(
        balance: float,
        risk_per_trade: float,
        entry_price: float,
        stop_loss_price: float
    ) -> float:
        """
        Calculate position size based on risk percentage.
        
        Formula: size = (balance * risk_pct) / |entry - stop|
        """
        risk_amount = balance * risk_per_trade
        price_diff = abs(entry_price - stop_loss_price)
        
        if price_diff == 0:
            return 0.0
        
        return risk_amount / price_diff
    
    @staticmethod
    def calculate_kelly_fraction(
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate Kelly fraction for position sizing.
        
        Formula: kelly = (p * b - q) / b
        where p = win rate, q = loss rate, b = win/loss ratio
        """
        if avg_loss == 0:
            return 0.0
        
        b = avg_win / abs(avg_loss)
        p = win_rate
        q = 1 - win_rate
        
        kelly = (p * b - q) / b
        
        # Constrain to reasonable range
        return max(0.0, min(kelly, 0.25))
    
    @staticmethod
    def calculate_max_drawdown(equity_curve: list) -> tuple:
        """Calculate maximum drawdown and duration."""
        if not equity_curve:
            return 0.0, 0
        
        peak = equity_curve[0]
        max_dd = 0.0
        max_duration = 0
        dd_start = 0
        
        for i, equity in enumerate(equity_curve):
            if equity > peak:
                peak = equity
                dd_start = i
            else:
                dd = (peak - equity) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
                duration = i - dd_start
                if duration > max_duration:
                    max_duration = duration
        
        return max_dd, max_duration
    
    @staticmethod
    def calculate_sharpe_ratio(
        returns: list,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 525600
    ) -> float:
        """Calculate annualized Sharpe ratio."""
        if not returns:
            return 0.0
        
        std = math.sqrt(sum((r - sum(returns) / len(returns)) ** 2 for r in returns) / len(returns))
        
        if std == 0:
            return 0.0
        
        mean_return = sum(returns) / len(returns)
        excess_return = mean_return - risk_free_rate / periods_per_year
        
        return excess_return / std * math.sqrt(periods_per_year)
    
    @staticmethod
    def calculate_risk_metrics(
        balance: float,
        entry_price: float,
        position_size: float,
        side: OrderSide,
        leverage: float,
        take_profit_pct: float = 0.01,
        stop_loss_pct: float = 0.02
    ) -> RiskMetrics:
        """Calculate comprehensive risk metrics for a position."""
        
        liquidation_price = RiskCalculator.calculate_liquidation_price(
            entry_price, side, leverage
        )
        
        margin_required = RiskCalculator.calculate_margin_required(
            position_size, entry_price, leverage
        )
        
        break_even = RiskCalculator.calculate_break_even_price(entry_price, side=side)
        
        position_value = position_size * entry_price
        
        # Calculate max loss
        if side == OrderSide.LONG:
            stop_price = entry_price * (1 - stop_loss_pct)
            max_loss = (entry_price - stop_price) * position_size
        else:
            stop_price = entry_price * (1 + stop_loss_pct)
            max_loss = (stop_price - entry_price) * position_size
        
        # Risk/Reward
        tp_price = entry_price * (1 + take_profit_pct) if side == OrderSide.LONG else entry_price * (1 - take_profit_pct)
        potential_profit = abs(tp_price - entry_price) * position_size
        risk_reward = potential_profit / max_loss if max_loss > 0 else 0
        
        return RiskMetrics(
            liquidation_price=liquidation_price,
            margin_required=margin_required,
            break_even_price=break_even,
            position_value=position_value,
            max_loss_usd=max_loss,
            risk_reward_ratio=risk_reward
        )


# ============================================================
# CLI ENTRY POINT
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='Calculate trading risk metrics')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Liquidation price command
    liq_parser = subparsers.add_parser('liquidation', help='Calculate liquidation price')
    liq_parser.add_argument('--entry', type=float, required=True, help='Entry price')
    liq_parser.add_argument('--leverage', type=float, required=True, help='Leverage')
    liq_parser.add_argument('--side', type=str, required=True, choices=['long', 'short'])
    
    # Position size command
    pos_parser = subparsers.add_parser('position', help='Calculate position size')
    pos_parser.add_argument('--balance', type=float, required=True, help='Account balance')
    pos_parser.add_argument('--risk', type=float, required=True, help='Risk per trade (e.g., 0.02 = 2%)')
    pos_parser.add_argument('--entry', type=float, required=True, help='Entry price')
    pos_parser.add_argument('--stop', type=float, required=True, help='Stop loss price')
    
    # Full analysis command
    full_parser = subparsers.add_parser('analyze', help='Full risk analysis')
    full_parser.add_argument('--balance', type=float, default=100, help='Account balance')
    full_parser.add_argument('--entry', type=float, required=True, help='Entry price')
    full_parser.add_argument('--size', type=float, required=True, help='Position size')
    full_parser.add_argument('--side', type=str, required=True, choices=['long', 'short'])
    full_parser.add_argument('--leverage', type=float, default=5, help='Leverage')
    full_parser.add_argument('--tp', type=float, default=0.01, help='Take profit %')
    full_parser.add_argument('--sl', type=float, default=0.02, help='Stop loss %')
    
    args = parser.parse_args()
    
    if args.command == 'liquidation':
        side = OrderSide.LONG if args.side == 'long' else OrderSide.SHORT
        liq_price = RiskCalculator.calculate_liquidation_price(
            args.entry, side, args.leverage
        )
        print(f"\nLiquidation Price: ${liq_price:,.2f}")
        print(f"Distance from entry: {abs(liq_price - args.entry) / args.entry * 100:.2f}%")
    
    elif args.command == 'position':
        size = RiskCalculator.calculate_position_size(
            args.balance, args.risk, args.entry, args.stop
        )
        print(f"\nRecommended Position Size: {size:.6f}")
        print(f"Position Value: ${size * args.entry:,.2f}")
        print(f"Risk Amount: ${args.balance * args.risk:,.2f}")
    
    elif args.command == 'analyze':
        side = OrderSide.LONG if args.side == 'long' else OrderSide.SHORT
        metrics = RiskCalculator.calculate_risk_metrics(
            balance=args.balance,
            entry_price=args.entry,
            position_size=args.size,
            side=side,
            leverage=args.leverage,
            take_profit_pct=args.tp,
            stop_loss_pct=args.sl
        )
        
        print("\n" + "=" * 50)
        print("RISK ANALYSIS")
        print("=" * 50)
        print(f"  Entry Price:        ${args.entry:,.2f}")
        print(f"  Position Size:      {args.size:.6f}")
        print(f"  Position Value:     ${metrics.position_value:,.2f}")
        print(f"  Leverage:           {args.leverage}x")
        print("-" * 50)
        print(f"  Liquidation Price:  ${metrics.liquidation_price:,.2f}")
        print(f"  Break-even Price:   ${metrics.break_even_price:,.2f}")
        print(f"  Margin Required:    ${metrics.margin_required:,.2f}")
        print("-" * 50)
        print(f"  Max Loss:           ${metrics.max_loss_usd:,.2f}")
        print(f"  Risk/Reward Ratio:  {metrics.risk_reward_ratio:.2f}")
        print("=" * 50)
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
