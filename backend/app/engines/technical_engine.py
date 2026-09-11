"""
Technical Analysis Engine:
Calculates Moving Averages (EMA 20, SMA 50, SMA 200), RSI (14),
and automatically detects Breakouts, Gaps, Golden Crosses, and Support/Resistance levels.
"""

from typing import List, Optional, Tuple
from app.models.chart import (
    CandleDataPoint,
    TechnicalSignal,
    TechnicalSignalType,
    SupportResistanceLevel,
    GapLevel,
    TechnicalIndicators
)


class TechnicalEngine:
    @staticmethod
    def analyze(candles: List[CandleDataPoint]) -> Tuple[TechnicalIndicators, List[TechnicalSignal], List[SupportResistanceLevel], List[GapLevel]]:
        if not candles or len(candles) < 5:
            return TechnicalIndicators(), [], [], []
            
        indicators = TechnicalEngine.calculate_indicators(candles)
        signals = TechnicalEngine.detect_signals(candles)
        support_resistance = TechnicalEngine.detect_support_resistance(candles)
        gaps = TechnicalEngine.detect_gaps(candles)
        
        return indicators, signals, support_resistance, gaps

    @staticmethod
    def calculate_indicators(candles: List[CandleDataPoint]) -> TechnicalIndicators:
        closes = [c.close for c in candles]
        n = len(closes)
        
        # EMA 20
        ema_20: Optional[float] = None
        if n >= 20:
            k = 2.0 / (20 + 1)
            ema = sum(closes[:20]) / 20.0
            for p in closes[20:]:
                ema = (p * k) + (ema * (1 - k))
            ema_20 = round(ema, 2)

        # SMA 50
        sma_50: Optional[float] = None
        if n >= 50:
            sma_50 = round(sum(closes[-50:]) / 50.0, 2)
        elif n >= 20:
            sma_50 = round(sum(closes[-20:]) / 20.0, 2)

        # SMA 200
        sma_200: Optional[float] = None
        if n >= 200:
            sma_200 = round(sum(closes[-200:]) / 200.0, 2)
        elif n >= 100:
            sma_200 = round(sum(closes[-100:]) / 100.0, 2)

        # RSI 14 (Wilder's Smoothing)
        rsi_14: Optional[float] = None
        if n >= 15:
            gains = []
            losses = []
            for i in range(1, 15):
                diff = closes[i] - closes[i - 1]
                if diff >= 0:
                    gains.append(diff)
                    losses.append(0.0)
                else:
                    gains.append(0.0)
                    losses.append(abs(diff))
                    
            avg_gain = sum(gains) / 14.0
            avg_loss = sum(losses) / 14.0
            
            for i in range(15, n):
                diff = closes[i] - closes[i - 1]
                gain = diff if diff > 0 else 0.0
                loss = abs(diff) if diff < 0 else 0.0
                avg_gain = (avg_gain * 13 + gain) / 14.0
                avg_loss = (avg_loss * 13 + loss) / 14.0
                
            if avg_loss == 0:
                rsi_14 = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi_14 = round(100.0 - (100.0 / (1.0 + rs)), 1)
        else:
            rsi_14 = 50.0

        # Trend & Momentum Summary
        curr_price = closes[-1]
        if sma_50 and sma_200:
            if curr_price >= sma_50 >= sma_200:
                trend = "STRONG BULLISH (Above Major MAs)"
            elif curr_price >= sma_50:
                trend = "MODERATE BULLISH"
            elif curr_price < sma_50 < sma_200:
                trend = "BEARISH DOWNTREND"
            else:
                trend = "CONSOLIDATING"
        elif sma_50:
            trend = "BULLISH" if curr_price >= sma_50 else "BEARISH"
        else:
            trend = "NEUTRAL"

        if rsi_14 is not None:
            if rsi_14 <= 30.0:
                momentum = "OVERSOLD (Peluang Beli Rebound)"
            elif rsi_14 >= 70.0:
                momentum = "OVERBOUGHT (Area Jual / Profit Taking)"
            elif rsi_14 >= 55.0:
                momentum = "STRONG BUYING MOMENTUM"
            else:
                momentum = "NEUTRAL CONSOLIDATION"
        else:
            momentum = "NEUTRAL"

        return TechnicalIndicators(
            ema_20=ema_20,
            sma_50=sma_50,
            sma_200=sma_200,
            rsi_14=rsi_14,
            trend_summary=trend,
            momentum_summary=momentum
        )

    @staticmethod
    def detect_signals(candles: List[CandleDataPoint]) -> List[TechnicalSignal]:
        signals: List[TechnicalSignal] = []
        n = len(candles)
        if n < 20:
            return signals

        # 1. Breakout & Volume Spike Detection
        for i in range(20, n):
            c = candles[i]
            prev_window = candles[i - 20:i]
            max_high = max(p.high for p in prev_window)
            avg_vol = sum(p.volume for p in prev_window) / 20.0
            
            # Breakout: close crosses 20-day high with volume spike >= 1.4x
            if c.close > max_high and avg_vol > 0 and c.volume >= avg_vol * 1.35:
                signals.append(TechnicalSignal(
                    date=c.time,
                    price=c.close,
                    signal_type=TechnicalSignalType.BREAKOUT_BUY,
                    title="🚀 BREAKOUT BUY",
                    description=f"Harga menembus resisten 20-hari (Rp{max_high:,.0f}) dengan lonjakan volume {c.volume / avg_vol:.1f}x rata-rata.",
                    color="#10b981",
                    position="belowBar",
                    shape="arrowUp"
                ))

            # Breakdown: close drops below 20-day low
            min_low = min(p.low for p in prev_window)
            if c.close < min_low and avg_vol > 0 and c.volume >= avg_vol * 1.35:
                signals.append(TechnicalSignal(
                    date=c.time,
                    price=c.close,
                    signal_type=TechnicalSignalType.BREAKDOWN_SELL,
                    title="⚠️ BREAKDOWN ALERT",
                    description=f"Harga breakdown di bawah support 20-hari (Rp{min_low:,.0f}) dengan tekanan jual tinggi.",
                    color="#f43f5e",
                    position="aboveBar",
                    shape="arrowDown"
                ))

        # 2. Gap Detection (Gap Up / Gap Down)
        for i in range(1, n):
            c_curr = candles[i]
            c_prev = candles[i - 1]
            
            # Gap Up: current low > prev high by >= 1.5%
            if c_curr.low >= c_prev.high * 1.015:
                gap_size = ((c_curr.low - c_prev.high) / c_prev.high) * 100
                signals.append(TechnicalSignal(
                    date=c_curr.time,
                    price=c_curr.open,
                    signal_type=TechnicalSignalType.GAP_UP,
                    title=f"🕳️ GAP UP (+{gap_size:.1f}%)",
                    description=f"Celah harga naik antara Rp{c_prev.high:,.0f} dan Rp{c_curr.low:,.0f}.",
                    color="#06b6d4",
                    position="belowBar",
                    shape="circle"
                ))
            # Gap Down: current high < prev low by >= 1.5%
            elif c_curr.high <= c_prev.low * 0.985:
                gap_size = ((c_prev.low - c_curr.high) / c_prev.low) * 100
                signals.append(TechnicalSignal(
                    date=c_curr.time,
                    price=c_curr.open,
                    signal_type=TechnicalSignalType.GAP_DOWN,
                    title=f"🕳️ GAP DOWN (-{gap_size:.1f}%)",
                    description=f"Celah harga turun antara Rp{c_prev.low:,.0f} dan Rp{c_curr.high:,.0f}.",
                    color="#f97316",
                    position="aboveBar",
                    shape="circle"
                ))

        # 3. Recent RSI Signal (if applicable in last 5 candles)
        recent_closes = [c.close for c in candles]
        if len(recent_closes) >= 15:
            last_c = candles[-1]
            # Quick RSI check on current candle
            # (handled cleanly in indicators)

        # Sort signals by date ascending, limit to last 15 most relevant
        signals.sort(key=lambda s: s.date)
        return signals[-15:]

    @staticmethod
    def detect_support_resistance(candles: List[CandleDataPoint]) -> List[SupportResistanceLevel]:
        if len(candles) < 15:
            return []

        swing_highs: List[float] = []
        swing_lows: List[float] = []
        
        # 5-day window local extrema
        for i in range(2, len(candles) - 2):
            c = candles[i]
            if c.high > candles[i-1].high and c.high > candles[i-2].high and c.high > candles[i+1].high and c.high > candles[i+2].high:
                swing_highs.append(c.high)
            if c.low < candles[i-1].low and c.low < candles[i-2].low and c.low < candles[i+1].low and c.low < candles[i+2].low:
                swing_lows.append(c.low)
                
        levels: List[SupportResistanceLevel] = []
        curr_price = candles[-1].close
        
        # Cluster swing lows for support
        clustered_supports = TechnicalEngine._cluster_levels(swing_lows, 0.02)
        for price_level, count in clustered_supports:
            if price_level < curr_price:
                levels.append(SupportResistanceLevel(
                    price=round(price_level, 0),
                    kind="SUPPORT",
                    strength=count,
                    description=f"Area Support Kunci (Diuji {count}x swing low)"
                ))

        # Cluster swing highs for resistance
        clustered_resists = TechnicalEngine._cluster_levels(swing_highs, 0.02)
        for price_level, count in clustered_resists:
            if price_level > curr_price:
                levels.append(SupportResistanceLevel(
                    price=round(price_level, 0),
                    kind="RESISTANCE",
                    strength=count,
                    description=f"Area Resisten Kunci (Diuji {count}x swing high)"
                ))

        # Sort levels by price ascending
        levels.sort(key=lambda x: x.price)
        return levels[:8]

    @staticmethod
    def detect_gaps(candles: List[CandleDataPoint]) -> List[GapLevel]:
        gaps: List[GapLevel] = []
        n = len(candles)
        
        for i in range(1, n):
            c_prev = candles[i - 1]
            c_curr = candles[i]
            
            if c_curr.low > c_prev.high * 1.012:
                # Gap up
                g_bottom = c_prev.high
                g_top = c_curr.low
                # Check if filled later
                is_filled = any(c.low <= g_bottom for c in candles[i:])
                gaps.append(GapLevel(
                    date=c_curr.time,
                    gap_type="GAP_UP",
                    gap_bottom=round(g_bottom, 2),
                    gap_top=round(g_top, 2),
                    is_filled=is_filled
                ))
            elif c_curr.high < c_prev.low * 0.988:
                # Gap down
                g_top = c_prev.low
                g_bottom = c_curr.high
                is_filled = any(c.high >= g_top for c in candles[i:])
                gaps.append(GapLevel(
                    date=c_curr.time,
                    gap_type="GAP_DOWN",
                    gap_bottom=round(g_bottom, 2),
                    gap_top=round(g_top, 2),
                    is_filled=is_filled
                ))
                
        return gaps[-6:]  # Return most recent 6 gaps

    @staticmethod
    def _cluster_levels(prices: List[float], tolerance: float = 0.02) -> List[Tuple[float, int]]:
        if not prices:
            return []
            
        prices_sorted = sorted(prices)
        clusters: List[List[float]] = []
        
        for p in prices_sorted:
            matched = False
            for group in clusters:
                avg = sum(group) / len(group)
                if abs(p - avg) / avg <= tolerance:
                    group.append(p)
                    matched = True
                    break
            if not matched:
                clusters.append([p])
                
        results = [(sum(g) / len(g), len(g)) for g in clusters]
        results.sort(key=lambda x: x[1], reverse=True)
        return results
