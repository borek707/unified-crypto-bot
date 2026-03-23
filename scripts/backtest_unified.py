#!/usr/bin/env python3
"""
Backtest unified_bot.py — symuluje DOKŁADNIE logikę produkcyjnego bota:
  - detect_trend() z hysteresis (48h lookback, ±5%)
  - UPTREND  → Long Grid (dip 0.8%, markup 0.6%)
  - DOWNTREND → Short 3x (bounce 1.5%, TP 4%, SL 2.5%)
  - SIDEWAYS  → Grid+DCA (support/resistance z ostatnich 48h)
  - Circuit Breaker (daily loss 5%, drawdown 15%, 5 consecutive losses)

Dane: Binance public API (1h candles BTC/USDT), brak klucza API

Uruchom:
  python3 backtest_unified.py --days 365           # oryginał
  python3 backtest_unified.py --days 365 --compare # oryginał vs v2 (fixes)
"""

import sys
import json
import math
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal, Tuple

# ─────────────────────────────────────────────
# KONFIGURACJA (identyczna jak unified_bot)
# ─────────────────────────────────────────────
@dataclass
class Config:
    label: str = "v1_original"
    initial_capital: float = 100.0
    max_total_exposure_pct: float = 0.50
    # Circuit Breaker
    max_daily_loss_pct: float = 0.05
    max_drawdown_pct: float = 0.15
    max_consecutive_losses: int = 5
    circuit_cooldown_hours: int = 1
    # Trend
    trend_lookback_h: int = 48
    trend_threshold: float = 0.05
    adx_period: int = 14
    adx_trend_threshold: float = 22.0
    adx_sideways_threshold: float = 16.0
    ema_fast_h: int = 48
    ema_mid_h: int = 24 * 7
    ema_slow_h: int = 24 * 30
    # Short 3x
    short_leverage: float = 3.0
    short_position_pct: float = 0.15
    short_max_positions: int = 2
    short_bounce_threshold: float = 0.015
    short_tp: float = 0.04
    short_sl: float = 0.025
    # Long Grid
    long_grid_spacing: float = 0.008
    long_markup: float = 0.006
    long_position_pct: float = 0.10
    trend_follow_position_pct: float = 0.15
    trend_follow_hard_stop_pct: float = 0.03
    trend_follow_activation_pct: float = 0.02
    trend_follow_trailing_stop_pct: float = 0.04
    long_guard_enabled: bool = True
    long_guard_ema_period: int = 200
    long_guard_min_24h_change: float = 0.0
    long_guard_min_72h_change: float = 0.01
    disable_long_grid: bool = False
    # Sideways Grid+DCA
    sideways_grid_pct: float = 0.30
    sideways_dca_pct: float = 0.70
    sideways_spacing: float = 0.015
    sideways_markup: float = 0.010
    max_grid_positions: int = 4
    # Fees (Hyperliquid)
    fee_taker: float = 0.0005


def config_v2(capital: float = 100.0) -> "Config":
    """Fixes: produkcyjny long guard + poluzowany Circuit Breaker."""
    return Config(
        label="v2_fixed",
        initial_capital=capital,
        # CB: 15% daily (realny próg dla $100), drawdown 25%, 8 strat z rzędu
        max_daily_loss_pct=0.15,
        max_drawdown_pct=0.25,
        max_consecutive_losses=8,
        circuit_cooldown_hours=4,
        # Sideways: nieco szerszy markup
        sideways_markup=0.012,
    )


def config_v3(capital: float = 100.0) -> "Config":
    """Wariant defensywny: bez Long Grid, tylko short + sideways."""
    return Config(
        label="v3_no_long_grid",
        initial_capital=capital,
        max_daily_loss_pct=0.10,
        max_drawdown_pct=0.20,
        max_consecutive_losses=6,
        circuit_cooldown_hours=2,
        sideways_markup=0.012,
        disable_long_grid=True,
    )


def fetch_btc_hourly(days: int = 365) -> List[Dict]:
    """Pobierz dane godzinowe BTC/USDT z Binance (public, brak API key)."""
    print(f"📡 Pobieram {days} dni danych godzinowych BTC z Binance...")
    url = "https://api.binance.com/api/v3/klines"
    candles = []
    end_ms = int(datetime.now().timestamp() * 1000)
    start_ms = end_ms - days * 24 * 3600 * 1000

    batch_size = 1000  # max Binance
    current_start = start_ms

    while current_start < end_ms:
        params = {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "startTime": current_start,
            "endTime": min(current_start + batch_size * 3600 * 1000, end_ms),
            "limit": batch_size
        }
        try:
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            for c in batch:
                candles.append({
                    "ts": datetime.fromtimestamp(c[0] / 1000),
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": float(c[5])
                })
            current_start = batch[-1][0] + 3600 * 1000
            sys.stdout.write(f"\r  Pobrano {len(candles)} świec...")
            sys.stdout.flush()
        except Exception as e:
            print(f"\n⚠️  Błąd pobierania: {e}")
            break

    print(f"\n✅ Pobrano {len(candles)} świec (1h)")
    return candles


# ─────────────────────────────────────────────
# SILNIK BACKTESTU
# ─────────────────────────────────────────────
class UnifiedBacktest:
    def __init__(self, candles: List[Dict], cfg: Config):
        self.candles = candles
        self.cfg = cfg
        self.balance = cfg.initial_capital
        self.peak_balance = cfg.initial_capital
        self.current_trend: Literal[
            'strong_uptrend',
            'pullback_uptrend',
            'sideways',
            'bear_rally',
            'strong_downtrend',
        ] = 'sideways'

        # Pozycje
        self.positions_long: List[Dict] = []
        self.positions_short: List[Dict] = []

        # Circuit Breaker
        self.cb_active = False
        self.cb_until: Optional[datetime] = None
        self.cb_activations = 0
        self.daily_pnl = 0.0
        self.daily_reset_date: Optional[datetime.date] = None
        self.consecutive_losses = 0
        self.current_balance = cfg.initial_capital

        # Statystyki
        self.trades: List[Dict] = []
        self.equity_curve: List[Dict] = []
        self.trend_history: List[str] = []

    # ── Trend detection (zsynchronizowany z unified_bot) ──
    @staticmethod
    def pct_change(prices: List[float], lookback: int) -> Optional[float]:
        if len(prices) <= lookback or prices[-lookback - 1] <= 0:
            return None
        return (prices[-1] / prices[-lookback - 1]) - 1

    @staticmethod
    def adx(candles: List[Dict], period: int = 14) -> Optional[Tuple[float, float, float]]:
        """Wilder ADX. Zwraca (adx, +di, -di) dla ostatniej świecy."""
        if len(candles) < period * 3:
            return None

        trs = []
        plus_dm = []
        minus_dm = []

        for i in range(1, len(candles)):
            curr = candles[i]
            prev = candles[i - 1]

            up_move = curr["high"] - prev["high"]
            down_move = prev["low"] - curr["low"]

            plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
            minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)

            tr = max(
                curr["high"] - curr["low"],
                abs(curr["high"] - prev["close"]),
                abs(curr["low"] - prev["close"]),
            )
            trs.append(tr)

        if len(trs) < period * 2:
            return None

        tr_sm = sum(trs[:period])
        plus_sm = sum(plus_dm[:period])
        minus_sm = sum(minus_dm[:period])

        dx_values = []
        for i in range(period, len(trs)):
            tr_sm = tr_sm - (tr_sm / period) + trs[i]
            plus_sm = plus_sm - (plus_sm / period) + plus_dm[i]
            minus_sm = minus_sm - (minus_sm / period) + minus_dm[i]

            if tr_sm <= 0:
                continue

            plus_di = 100.0 * (plus_sm / tr_sm)
            minus_di = 100.0 * (minus_sm / tr_sm)
            di_sum = plus_di + minus_di
            dx = 0.0 if di_sum == 0 else 100.0 * abs(plus_di - minus_di) / di_sum
            dx_values.append((dx, plus_di, minus_di))

        if len(dx_values) < period:
            return None

        adx_value = sum(v[0] for v in dx_values[:period]) / period
        for i in range(period, len(dx_values)):
            adx_value = ((adx_value * (period - 1)) + dx_values[i][0]) / period

        last_plus_di = dx_values[-1][1]
        last_minus_di = dx_values[-1][2]
        return adx_value, last_plus_di, last_minus_di

    def detect_trend(
        self,
        candles: List[Dict]
    ) -> Literal['strong_uptrend', 'pullback_uptrend', 'sideways', 'bear_rally', 'strong_downtrend']:
        prices = [c["close"] for c in candles]
        if len(prices) < 48:
            return self.current_trend

        price = prices[-1]
        adx_data = self.adx(candles, self.cfg.adx_period)
        if adx_data is None:
            return self.current_trend
        adx_value, plus_di, minus_di = adx_data

        change_48h = self.pct_change(prices, 48)
        change_7d = self.pct_change(prices, 24 * 7)
        change_14d = self.pct_change(prices, 24 * 14)
        change_30d = self.pct_change(prices, 24 * 30)

        baseline_change = change_30d
        ema_period = 24 * 30
        if baseline_change is None:
            baseline_change = change_14d if change_14d is not None else change_7d
            ema_period = 24 * 14
        if baseline_change is None or change_48h is None or change_7d is None:
            return self.current_trend

        ema_fast = self.ema(prices[-self.cfg.ema_fast_h * 2:], self.cfg.ema_fast_h)
        ema_mid = self.ema(prices[-self.cfg.ema_mid_h * 2:], self.cfg.ema_mid_h)
        ema_baseline = self.ema(prices[-ema_period * 2:], ema_period)
        ema_slow = self.ema(prices[-self.cfg.ema_slow_h * 2:], self.cfg.ema_slow_h)

        bullish_stack = ema_fast >= ema_mid >= ema_slow
        bearish_stack = ema_fast <= ema_mid <= ema_slow
        adx_strong = adx_value >= self.cfg.adx_trend_threshold
        adx_weak = adx_value <= self.cfg.adx_sideways_threshold

        above_ema = price >= ema_baseline
        below_ema = price <= ema_baseline
        change_14d = change_14d if change_14d is not None else change_7d

        if (
            baseline_change >= 0.08
            and change_14d >= 0.02
            and change_7d >= 0.005
            and above_ema
            and bullish_stack
            and adx_strong
            and plus_di > minus_di
        ):
            if change_48h < 0:
                return 'pullback_uptrend'
            return 'strong_uptrend'

        if (
            baseline_change >= 0.03
            and change_14d >= 0.0
            and price >= ema_mid * 0.985
            and bullish_stack
            and plus_di >= minus_di
        ):
            if -0.08 <= change_48h <= 0.01:
                return 'pullback_uptrend'

        if (
            baseline_change <= -0.08
            and change_14d <= -0.02
            and change_7d <= -0.005
            and below_ema
            and bearish_stack
            and adx_strong
            and minus_di > plus_di
        ):
            if change_48h > 0:
                return 'bear_rally'
            return 'strong_downtrend'

        if (
            baseline_change <= -0.03
            and change_14d <= 0.0
            and price <= ema_mid * 1.015
            and bearish_stack
            and minus_di >= plus_di
        ):
            if change_48h > 0:
                return 'bear_rally'
            return 'strong_downtrend'

        if adx_weak and abs(change_48h) < 0.03 and abs(change_7d) < 0.06:
            return 'sideways'

        return 'sideways'

    # ── Circuit Breaker ──
    def reset_daily(self, ts: datetime):
        if self.daily_reset_date != ts.date():
            self.daily_pnl = 0.0
            self.daily_reset_date = ts.date()

    def cb_check(self, ts: datetime) -> bool:
        if self.cb_active and self.cb_until and ts >= self.cb_until:
            self.cb_active = False
            self.cb_until = None
            self.consecutive_losses = 0
        if self.cb_active:
            return True

        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance

        drawdown = (self.peak_balance - self.current_balance) / self.peak_balance if self.peak_balance > 0 else 0
        daily_loss = abs(self.daily_pnl) / self.cfg.initial_capital if self.daily_pnl < 0 else 0

        if daily_loss > self.cfg.max_daily_loss_pct:
            self._cb_activate(ts, f"daily_loss {daily_loss:.1%}")
            return True
        if drawdown > self.cfg.max_drawdown_pct:
            self._cb_activate(ts, f"drawdown {drawdown:.1%}")
            return True
        if self.consecutive_losses >= self.cfg.max_consecutive_losses:
            self._cb_activate(ts, f"{self.consecutive_losses} consecutive losses")
            return True
        return False

    def _cb_activate(self, ts: datetime, reason: str):
        self.cb_active = True
        self.cb_until = ts + timedelta(hours=self.cfg.circuit_cooldown_hours)
        self.cb_activations += 1

    def record_trade(self, pnl: float, ts: datetime, strategy: str, reason: str):
        self.balance += pnl
        self.current_balance += pnl
        self.daily_pnl += pnl
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        self.trades.append({
            "ts": ts,
            "pnl": pnl,
            "strategy": strategy,
            "reason": reason,
            "trend": self.current_trend,
        })

    def _check_exposure_limit(self, new_position_size: float = 0.0) -> bool:
        current_exposure = sum(p.get("size", 0.0) for p in self.positions_long + self.positions_short)
        exposure_pct = (current_exposure + new_position_size) / self.current_balance if self.current_balance > 0 else 0.0
        return exposure_pct <= self.cfg.max_total_exposure_pct

    # ── EMA (pure python, brak numpy) ──
    @staticmethod
    def ema(prices: List[float], period: int) -> float:
        if len(prices) < period:
            return prices[-1]
        k = 2.0 / (period + 1)
        val = prices[0]
        for p in prices[1:]:
            val = p * k + val * (1 - k)
        return val

    def is_long_allowed(self, price: float, prices: List[float]) -> bool:
        if self.cfg.disable_long_grid:
            return False
        if not self.cfg.long_guard_enabled:
            return True
        min_lookback = max(self.cfg.long_guard_ema_period, 72)
        if len(prices) < min_lookback:
            return False
        recent = prices[-(self.cfg.long_guard_ema_period * 2):]
        ema_value = self.ema(recent, self.cfg.long_guard_ema_period)
        price_24h_ago = prices[-24]
        price_72h_ago = prices[-72]
        ch_24h = (price / price_24h_ago) - 1 if price_24h_ago > 0 else -1
        ch_72h = (price / price_72h_ago) - 1 if price_72h_ago > 0 else -1
        return (
            price >= ema_value
            and ch_24h >= self.cfg.long_guard_min_24h_change
            and ch_72h >= self.cfg.long_guard_min_72h_change
        )

    def get_trend_follow_position(self) -> Optional[Dict]:
        for pos in self.positions_long:
            if pos.get("type") == "trend_follow":
                return pos
        return None

    def should_enter_trend_follow(self, price: float, prices: List[float], ts: datetime) -> bool:
        if self.cb_check(ts):
            return False
        if self.get_trend_follow_position() is not None:
            return False
        if not self.is_long_allowed(price, prices):
            return False
        size = self.cfg.initial_capital * self.cfg.trend_follow_position_pct
        if not self._check_exposure_limit(size):
            return False
        return True

    def open_trend_follow(self, price: float, ts: datetime):
        size = self.cfg.initial_capital * self.cfg.trend_follow_position_pct
        fee = size * self.cfg.fee_taker
        self.balance -= fee
        self.current_balance -= fee
        self.positions_long.append({
            "entry": price,
            "size": size,
            "highest": price,
            "hard_stop": price * (1 - self.cfg.trend_follow_hard_stop_pct),
            "trailing_stop": None,
            "type": "trend_follow",
            "ts": ts,
        })

    def check_trend_follow_exits(self, candle: Dict, ts: datetime):
        closed = []
        for pos in self.positions_long:
            if pos.get("type") != "trend_follow":
                continue

            pos["highest"] = max(pos["highest"], candle["high"])
            exit_price = candle["close"]
            reason = None

            if candle["low"] <= pos["hard_stop"]:
                exit_price = pos["hard_stop"]
                reason = "hard_stop"
            else:
                activation_price = pos["entry"] * (1 + self.cfg.trend_follow_activation_pct)
                if pos["highest"] >= activation_price:
                    trailing_stop = pos["highest"] * (1 - self.cfg.trend_follow_trailing_stop_pct)
                    pos["trailing_stop"] = max(pos.get("trailing_stop") or trailing_stop, trailing_stop)
                    if candle["low"] <= pos["trailing_stop"]:
                        exit_price = pos["trailing_stop"]
                        reason = "trailing_stop"

            if reason:
                pnl_gross = (exit_price - pos["entry"]) / pos["entry"] * pos["size"]
                fee = pos["size"] * self.cfg.fee_taker
                self.record_trade(pnl_gross - fee, ts, "trend_follow", reason)
                closed.append(pos)

        for pos in closed:
            self.positions_long.remove(pos)

    # ── Long Grid ──
    def try_long_entry(self, price: float, prices: List[float], ts: datetime):
        if self.cb_check(ts):
            return
        if any(pos.get("type") == "long_grid" for pos in self.positions_long):
            return
        if len(prices) < 24:
            return
        if not self.is_long_allowed(price, prices):
            return
        recent_high = max(prices[-24:])
        dip = (recent_high - price) / recent_high
        if dip >= self.cfg.long_grid_spacing:
            size = self.cfg.initial_capital * self.cfg.long_position_pct
            if not self._check_exposure_limit(size):
                return
            fee = size * self.cfg.fee_taker
            self.balance -= fee
            self.current_balance -= fee
            self.positions_long.append({
                "entry": price,
                "size": size,
                "tp": price * (1 + self.cfg.long_markup),
                "type": "long_grid",
                "ts": ts
            })

    def check_long_exits(self, candle: Dict, ts: datetime):
        closed = []
        for pos in self.positions_long:
            if pos.get("type") != "long_grid":
                continue
            if candle["high"] >= pos["tp"]:
                pnl_gross = pos["size"] * self.cfg.long_markup
                fee = (pos["size"] + pnl_gross) * self.cfg.fee_taker
                pnl = pnl_gross - fee
                self.record_trade(pnl, ts, "long_grid", "tp")
                closed.append(pos)
        for p in closed:
            self.positions_long.remove(p)

    # ── Short 3x ──
    def try_short_entry(self, price: float, prices: List[float], ts: datetime):
        if self.cb_check(ts):
            return
        if len(self.positions_short) >= self.cfg.short_max_positions:
            return
        if len(prices) < 24:
            return
        recent_low = min(prices[-24:])
        bounce = (price - recent_low) / recent_low if recent_low > 0 else 0
        if bounce >= self.cfg.short_bounce_threshold:
            size = self.cfg.initial_capital * self.cfg.short_position_pct
            if not self._check_exposure_limit(size):
                return
            notional = size * self.cfg.short_leverage
            fee = notional * self.cfg.fee_taker
            self.balance -= fee
            self.current_balance -= fee
            self.positions_short.append({
                "entry": price,
                "size": size,
                "notional": notional,
                "tp": price * (1 - self.cfg.short_tp),
                "sl": price * (1 + self.cfg.short_sl),
                "type": "short",
                "ts": ts
            })

    def check_short_exits(self, c: Dict, ts: datetime):
        closed = []
        for pos in self.positions_short:
            price = c["close"]
            reason = None
            # TP: cena spadła
            if c["low"] <= pos["tp"]:
                price = pos["tp"]
                reason = "tp"
            # SL: cena wzrosła
            elif c["high"] >= pos["sl"]:
                price = pos["sl"]
                reason = "sl"

            if reason:
                entry = pos["entry"]
                notional = pos["notional"]
                if reason == "tp":
                    pnl_gross = notional * self.cfg.short_tp
                else:
                    pnl_gross = -notional * self.cfg.short_sl
                fee = notional * self.cfg.fee_taker
                pnl = pnl_gross - fee
                self.record_trade(pnl, ts, "short_3x", reason)
                closed.append(pos)
        for p in closed:
            self.positions_short.remove(p)

    def close_short_market(self, pos: Dict, price: float, ts: datetime, reason: str):
        pnl_gross = (pos["entry"] - price) / pos["entry"] * pos["notional"]
        fee = pos["notional"] * self.cfg.fee_taker
        self.record_trade(pnl_gross - fee, ts, "short_3x", reason)
        self.positions_short.remove(pos)

    # ── Sideways Grid ──
    def try_sideways_entry(self, price: float, prices: List[float], ts: datetime):
        if self.cb_check(ts):
            return
        sideways_pos = [p for p in self.positions_long if p.get("type") == "sideways"]
        if len(sideways_pos) >= self.cfg.max_grid_positions:
            return
        if len(prices) < 48:
            return
        recent = prices[-48:]
        high = max(recent)
        low = min(recent)
        mid = (high + low) / 2
        if (high - low) / mid < 0.005:
            return
        support = low + (high - low) * 0.2
        support_zone = support * (1 + self.cfg.sideways_spacing * 0.5)
        if price <= support_zone and price >= low * 1.005:
            size = self.cfg.initial_capital * self.cfg.sideways_grid_pct * 0.25
            if not self._check_exposure_limit(size):
                return
            fee = size * self.cfg.fee_taker
            self.balance -= fee
            self.current_balance -= fee
            self.positions_long.append({
                "entry": price,
                "size": size,
                "tp": price * (1 + self.cfg.sideways_markup),
                "sl": price * (1 - self.cfg.sideways_spacing * 1.5),
                "type": "sideways",
                "ts": ts
            })

    def check_sideways_exits(self, c: Dict, ts: datetime):
        closed = []
        for pos in self.positions_long:
            if pos.get("type") != "sideways":
                continue
            if c["high"] >= pos["tp"]:
                pnl_gross = pos["size"] * self.cfg.sideways_markup
                fee = (pos["size"] + pnl_gross) * self.cfg.fee_taker
                pnl = pnl_gross - fee
                self.record_trade(pnl, ts, "sideways_grid", "tp")
                closed.append(pos)
            elif c["low"] <= pos["sl"]:
                pnl_gross = -pos["size"] * self.cfg.sideways_spacing * 1.5
                fee = pos["size"] * self.cfg.fee_taker
                pnl = pnl_gross - fee
                self.record_trade(pnl, ts, "sideways_grid", "sl")
                closed.append(pos)
        for p in closed:
            self.positions_long.remove(p)

    def close_long_market(self, pos: Dict, price: float, ts: datetime, reason: str):
        pnl_gross = (price - pos["entry"]) / pos["entry"] * pos["size"]
        fee = pos["size"] * self.cfg.fee_taker
        self.record_trade(pnl_gross - fee, ts, pos.get("type", "long_grid"), reason)
        self.positions_long.remove(pos)

    # ── Główna pętla ──
    def run(self) -> Dict:
        prices_close = [c["close"] for c in self.candles]

        for i, candle in enumerate(self.candles):
            ts = candle["ts"]
            price = candle["close"]
            prices_so_far = prices_close[:i+1]
            trend_window_h = max(self.cfg.ema_slow_h * 3, 24 * 45)
            candles_so_far = self.candles[max(0, i - trend_window_h):i+1]

            self.reset_daily(ts)

            # Trend detection
            self.current_trend = self.detect_trend(candles_so_far)
            self.trend_history.append(self.current_trend)

            # Wyjścia ochronne i TP są aktywne niezależnie od regime.
            self.check_trend_follow_exits(candle, ts)
            self.check_long_exits(candle, ts)
            self.check_sideways_exits(candle, ts)

            # Strategia wg trendu
            if self.current_trend == 'pullback_uptrend':
                self.try_long_entry(price, prices_so_far, ts)

            elif self.current_trend == 'strong_uptrend':
                for pos in list(self.positions_short):
                    self.close_short_market(pos, price, ts, "strong_uptrend")
                if self.should_enter_trend_follow(price, prices_so_far, ts):
                    self.open_trend_follow(price, ts)

            elif self.current_trend in ('strong_downtrend', 'bear_rally'):
                self.check_short_exits(candle, ts)
                self.try_short_entry(price, prices_so_far, ts)

            else:  # sideways
                for pos in list(self.positions_short):
                    self.close_short_market(pos, price, ts, "sideways")
                if self.is_long_allowed(price, prices_so_far):
                    self.try_sideways_entry(price, prices_so_far, ts)

            # Equity curve
            unrealized = 0.0
            for pos in self.positions_long:
                unrealized += (price - pos["entry"]) / pos["entry"] * pos["size"]
            for pos in self.positions_short:
                unrealized += (pos["entry"] - price) / pos["entry"] * pos["notional"]

            self.equity_curve.append({
                "ts": ts,
                "balance": self.balance,
                "equity": self.balance + unrealized,
                "trend": self.current_trend,
                "price": price
            })

        # Zamknij otwarte pozycje na koniec
        last_price = self.candles[-1]["close"]
        last_ts = self.candles[-1]["ts"]
        for pos in list(self.positions_long):
            pnl = (last_price - pos["entry"]) / pos["entry"] * pos["size"]
            fee = pos["size"] * self.cfg.fee_taker
            self.record_trade(pnl - fee, last_ts, pos["type"], "end")
        for pos in list(self.positions_short):
            pnl = (pos["entry"] - last_price) / pos["entry"] * pos["notional"]
            fee = pos["notional"] * self.cfg.fee_taker
            self.record_trade(pnl - fee, last_ts, "short_3x", "end")

        return self._calc_stats()

    def _calc_stats(self) -> Dict:
        cfg = self.cfg
        trades = self.trades
        if not trades:
            return {}

        pnls = [t["pnl"] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        # Max drawdown z equity curve
        eq = [e["equity"] for e in self.equity_curve]
        peak = eq[0]
        max_dd = 0.0
        for e in eq:
            if e > peak:
                peak = e
            dd = (peak - e) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        # Sharpe (uproszczony)
        if len(eq) > 1:
            import statistics
            returns = [(eq[i] - eq[i-1]) / eq[i-1] for i in range(1, len(eq)) if eq[i-1] > 0]
            if returns:
                mean_r = statistics.mean(returns)
                std_r = statistics.stdev(returns) if len(returns) > 1 else 0.0001
                sharpe = (mean_r / std_r) * math.sqrt(8760) if std_r > 0 else 0
            else:
                sharpe = 0
        else:
            sharpe = 0

        # Trend distribution
        from collections import Counter
        trend_counts = Counter(self.trend_history)
        total_h = len(self.trend_history)

        # Per-strategy
        by_strategy = {}
        by_regime = {}
        for t in trades:
            s = t["strategy"]
            if s not in by_strategy:
                by_strategy[s] = {"trades": 0, "pnl": 0.0, "wins": 0}
            by_strategy[s]["trades"] += 1
            by_strategy[s]["pnl"] += t["pnl"]
            if t["pnl"] > 0:
                by_strategy[s]["wins"] += 1

            regime = t.get("trend", "unknown")
            if regime not in by_regime:
                by_regime[regime] = {"trades": 0, "pnl": 0.0}
            by_regime[regime]["trades"] += 1
            by_regime[regime]["pnl"] += t["pnl"]

        start_price = self.candles[0]["close"]
        end_price = self.candles[-1]["close"]
        hodl_return = (end_price / start_price - 1) * cfg.initial_capital

        return {
            "initial_capital": cfg.initial_capital,
            "final_balance": self.balance,
            "total_return_pct": (self.balance / cfg.initial_capital - 1) * 100,
            "hodl_return_pct": (end_price / start_price - 1) * 100,
            "hodl_final": cfg.initial_capital + hodl_return,
            "max_drawdown_pct": max_dd * 100,
            "sharpe": round(sharpe, 2),
            "total_trades": len(trades),
            "win_rate": len(wins) / len(pnls) * 100,
            "profit_factor": round(profit_factor, 2),
            "avg_win": sum(wins) / len(wins) if wins else 0,
            "avg_loss": sum(losses) / len(losses) if losses else 0,
            "cb_activations": self.cb_activations,
            "by_strategy": by_strategy,
            "by_regime": by_regime,
            "trend_pct": {
                "strong_uptrend": trend_counts.get("strong_uptrend", 0) / total_h * 100,
                "pullback_uptrend": trend_counts.get("pullback_uptrend", 0) / total_h * 100,
                "sideways": trend_counts.get("sideways", 0) / total_h * 100,
                "bear_rally": trend_counts.get("bear_rally", 0) / total_h * 100,
                "strong_downtrend": trend_counts.get("strong_downtrend", 0) / total_h * 100,
            },
            "period": {
                "start": str(self.candles[0]["ts"].date()),
                "end": str(self.candles[-1]["ts"].date()),
                "days": (self.candles[-1]["ts"] - self.candles[0]["ts"]).days,
                "start_price": start_price,
                "end_price": end_price,
            }
        }


def print_results(r: Dict):
    SEP = "=" * 58
    print(f"\n{SEP}")
    print("  BACKTEST UNIFIED BOT — wyniki")
    print(SEP)
    print(f"  Okres:       {r['period']['start']} → {r['period']['end']} ({r['period']['days']} dni)")
    print(f"  BTC:         ${r['period']['start_price']:,.0f} → ${r['period']['end_price']:,.0f}  ({r['hodl_return_pct']:+.1f}%)")
    print(SEP)
    print(f"  Start:       ${r['initial_capital']:.2f}")
    print(f"  Koniec:      ${r['final_balance']:.2f}")
    diff = r['final_balance'] - r['hodl_final']
    sign = "+" if diff >= 0 else ""
    print(f"  Return:      {r['total_return_pct']:+.2f}%   (HODL: {r['hodl_return_pct']:+.1f}%)   alpha: {sign}${diff:.2f}")
    print(f"  Max Drawdown:{r['max_drawdown_pct']:.1f}%")
    print(f"  Sharpe:      {r['sharpe']}")
    print(SEP)
    print(f"  Trades:      {r['total_trades']}")
    print(f"  Win rate:    {r['win_rate']:.1f}%")
    print(f"  Profit F.:   {r['profit_factor']}")
    print(f"  Avg win:     ${r['avg_win']:.3f}")
    print(f"  Avg loss:    ${r['avg_loss']:.3f}")
    print(f"  CB aktyw.:   {r['cb_activations']}x")
    print(SEP)
    print(f"  Czas w trendzie:")
    print(f"    🚀 STRONG UP:   {r['trend_pct']['strong_uptrend']:.1f}%")
    print(f"    📈 PULLBACK UP: {r['trend_pct']['pullback_uptrend']:.1f}%")
    print(f"    ➡️  SIDEWAYS:    {r['trend_pct']['sideways']:.1f}%")
    print(f"    📉 BEAR RALLY:  {r['trend_pct']['bear_rally']:.1f}%")
    print(f"    🧊 STRONG DOWN: {r['trend_pct']['strong_downtrend']:.1f}%")
    print(SEP)
    print("  Per strategia:")
    for name, s in r["by_strategy"].items():
        wr = s["wins"] / s["trades"] * 100 if s["trades"] > 0 else 0
        print(f"    {name:<16} trades={s['trades']:3d}  PnL=${s['pnl']:+6.2f}  WR={wr:.0f}%")
    print(SEP)
    print("  Per regime (exit):")
    for name, s in r.get("by_regime", {}).items():
        print(f"    {name:<16} trades={s['trades']:3d}  PnL=${s['pnl']:+6.2f}")
    print(SEP)


def print_comparison(r1: Dict, r2: Dict):
    """Tabelaryczne porównanie v1 vs v2."""
    SEP = "=" * 62
    print(f"\n{SEP}")
    print(f"  PORÓWNANIE: {r1.get('label','v1')}  vs  {r2.get('label','v2')}")
    print(SEP)
    print(f"  {'Metryka':<28} {'ORYGINAŁ':>12} {'v2 FIXED':>12}")
    print("-" * 62)

    def row(name, k, fmt="{:.2f}"):
        v1 = r1.get(k, 0)
        v2 = r2.get(k, 0)
        diff = v2 - v1 if isinstance(v2, (int, float)) else 0
        sign = "+" if diff > 0 else ""
        print(f"  {name:<28} {fmt.format(v1):>12} {fmt.format(v2):>12}  ({sign}{diff:.2f})")

    row("Return (%)", "total_return_pct")
    row("Final balance ($)", "final_balance")
    row("Max Drawdown (%)", "max_drawdown_pct")
    row("Sharpe", "sharpe")
    row("Win Rate (%)", "win_rate")
    row("Profit Factor", "profit_factor")
    row("Total Trades", "total_trades", "{:.0f}")
    row("CB aktivations", "cb_activations", "{:.0f}")
    r1s = r1.get("by_strategy", {})
    r2s = r2.get("by_strategy", {})
    lg1 = r1s.get("long_grid", {}).get("pnl", 0)
    lg2 = r2s.get("long_grid", {}).get("pnl", 0)
    diff = lg2 - lg1
    sign = "+" if diff > 0 else ""
    print(f"  {'Long Grid PnL ($)':<28} {lg1:>12.2f} {lg2:>12.2f}  ({sign}{diff:.2f})")
    print(SEP)
    hodl = r1.get("hodl_return_pct", 0)
    print(f"  HODL (referencja):       {hodl:+.1f}%")
    print(SEP)


def print_comparison_three(r1: Dict, r2: Dict, r3: Dict):
    SEP = "=" * 86
    print(f"\n{SEP}")
    print("  PORÓWNANIE: v1 produkcyjny vs v2 luźniejszy CB vs v3 bez Long Grid")
    print(SEP)
    print(f"  {'Metryka':<24} {'v1':>10} {'v2':>10} {'v3':>10}")
    print("-" * 86)
    rows = [
        ("Return (%)", "total_return_pct", "{:.2f}"),
        ("Final balance ($)", "final_balance", "{:.2f}"),
        ("Max Drawdown (%)", "max_drawdown_pct", "{:.2f}"),
        ("Sharpe", "sharpe", "{:.2f}"),
        ("Win Rate (%)", "win_rate", "{:.2f}"),
        ("Profit Factor", "profit_factor", "{:.2f}"),
        ("Trades", "total_trades", "{:.0f}"),
        ("CB aktivations", "cb_activations", "{:.0f}"),
    ]
    for name, key, fmt in rows:
        print(
            f"  {name:<24} {fmt.format(r1.get(key, 0)):>10} {fmt.format(r2.get(key, 0)):>10} {fmt.format(r3.get(key, 0)):>10}"
        )
    print(SEP)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365, help="Liczba dni backtestu (default: 365)")
    parser.add_argument("--capital", type=float, default=100.0, help="Kapitał startowy (default: 100)")
    parser.add_argument("--compare", action="store_true", help="Porównaj v1 (produkcyjny) vs v2 (luźniejszy CB) vs v3 (bez Long Grid)")
    parser.add_argument("--save", action="store_true", help="Zapisz wyniki do JSON")
    args = parser.parse_args()

    candles = fetch_btc_hourly(days=args.days)
    if len(candles) < 100:
        print("❌ Za mało danych, sprawdź połączenie z internetem")
        sys.exit(1)

    if args.compare:
        cfg_v1 = Config(initial_capital=args.capital)
        cfg_v2 = config_v2(capital=args.capital)
        cfg_v3 = config_v3(capital=args.capital)

        print(f"\n🔄 Backtest v1 (produkcyjny guard)...")
        r1 = UnifiedBacktest(candles, cfg_v1).run()
        r1["label"] = "v1_original"
        print(f"\n🔄 Backtest v2 (luźniejszy CB)...")
        r2 = UnifiedBacktest(candles, cfg_v2).run()
        r2["label"] = "v2_fixed"
        print(f"\n🔄 Backtest v3 (bez Long Grid)...")
        r3 = UnifiedBacktest(candles, cfg_v3).run()
        r3["label"] = "v3_no_long_grid"

        print_results(r1)
        print_results(r2)
        print_results(r3)
        print_comparison(r1, r2)
        print_comparison_three(r1, r2, r3)

        if args.save:
            out_path = "/workspaces/unified-crypto-bot/memory/backtest_results/unified_bot_comparison.json"
            with open(out_path, "w") as f:
                json.dump({"v1": r1, "v2": r2, "v3": r3}, f, indent=2, default=str)
            print(f"\n💾 Wyniki zapisane: {out_path}")
    else:
        cfg = Config(initial_capital=args.capital)
        print(f"\n🔄 Uruchamiam backtest ({len(candles)} świec 1h)...")
        bt = UnifiedBacktest(candles, cfg)
        results = bt.run()
        print_results(results)

        if args.save:
            out_path = "/workspaces/unified-crypto-bot/memory/backtest_results/unified_bot_backtest.json"
            with open(out_path, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n💾 Wyniki zapisane: {out_path}")
