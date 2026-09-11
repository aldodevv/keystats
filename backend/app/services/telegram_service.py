"""
Telegram Bot Service for BRIGHTS.
Broadcasts high-conviction daily stock recommendations, multi-scenario targets (TP1/TP2),
and risk-managed stop loss levels directly to Telegram users/channels via Telegram Bot API.
"""

import os
import logging
import datetime
from typing import Optional, Dict, Any
import requests

import app.config  # noqa: F401
from app.services.emiten_service import EmitenService
from app.services.market_summary_service import MarketSummaryService
from app.models.market import MarketSummaryResponse, TopPickItem

logger = logging.getLogger(__name__)

# Fallback credentials matching deployment config
DEFAULT_BOT_TOKEN = "8653878371:AAGgLIDflVM2MxGU9omMcWbzqKT7MyQ_olo"
DEFAULT_CHAT_ID = "7690577065"


class TelegramBotService:
    def __init__(
        self,
        bot_token: Optional[str] = None,
        default_chat_id: Optional[str] = None,
        emiten_service: Optional[EmitenService] = None
    ):
        self._bot_token = bot_token
        self._default_chat_id = default_chat_id
        self.emiten_service = emiten_service or EmitenService()
        self.market_service = MarketSummaryService(self.emiten_service)

    @property
    def bot_token(self) -> str:
        token = self._bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            token = DEFAULT_BOT_TOKEN
        return token

    @property
    def default_chat_id(self) -> str:
        cid = self._default_chat_id or os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        if not cid:
            cid = DEFAULT_CHAT_ID
        return str(cid)

    @property
    def is_configured(self) -> bool:
        t = self.bot_token
        return bool(t and len(t) > 15)

    def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True
    ) -> Dict[str, Any]:
        """Sends a text message via Telegram Bot API."""
        if not self.is_configured:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN belum dikonfigurasi. Harap isi TELEGRAM_BOT_TOKEN di file backend/.env."
            )

        target_chat_id = str(chat_id or self.default_chat_id).strip()
        if not target_chat_id:
            raise ValueError("Target chat_id Telegram tidak ditemukan.")

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": target_chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }

        try:
            resp = requests.post(url, json=payload, timeout=20)
            data = resp.json()
            if not resp.ok or not data.get("ok"):
                error_desc = data.get("description", resp.text)
                logger.error(f"Failed to send Telegram message: {error_desc}")
                return {"success": False, "error": error_desc, "status_code": resp.status_code}
            return {"success": True, "result": data.get("result")}
        except Exception as exc:
            logger.exception(f"Telegram API request failed: {exc}")
            return {"success": False, "error": str(exc)}

    def format_daily_picks_html(self, summary: MarketSummaryResponse) -> str:
        """Formats the top picks into an elegant, high-clarity HTML Telegram message."""
        date_now = datetime.datetime.now().strftime("%d %b %Y")
        stats = summary.stats

        lines = [
            "<b>📊 KEYSTATS PRO — REKOMENDASI SAHAM PILIHAN ESOK HARI</b>",
            f"📅 <i>Kalkulasi Kuantitatif & Valuasi Konsensus IDX • {date_now}</i>",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            f"📈 <b>Kondisi Pasar:</b> {stats.total_emitens} Emiten Dianalisis | Skor Rata-rata {stats.avg_composite_score:.1f}/100",
            f"Undervalued: {stats.undervalued_count} | Sektor Unggulan: {stats.top_sector}",
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
        ]

        if not summary.top_picks:
            lines.append("<i>Belum ada emiten yang memenuhi kriteria conviction ketat untuk esok hari.</i>")
        else:
            for idx, pick in enumerate(summary.top_picks, start=1):
                cur_price = pick.current_price
                tp1 = pick.take_profit_1 or pick.fair_value
                tp2 = pick.take_profit_2
                sl = pick.stop_loss or round(cur_price * 0.93)
                entry = pick.entry_zone or f"Rp{cur_price:,.0f}"

                # Upside and Downside percentages
                upside_1_pct = ((tp1 - cur_price) / cur_price * 100) if cur_price > 0 else 0
                downside_pct = ((cur_price - sl) / cur_price * 100) if cur_price > 0 else 0
                
                # Format upside string nicely
                up1_str = f"+{upside_1_pct:.1f}%" if upside_1_pct >= 0 else f"{upside_1_pct:.1f}%"
                
                rr_val = pick.risk_to_reward_ratio
                if rr_val and 0 < rr_val <= 15:
                    rr_str = f"1 : {rr_val:.1f}"
                elif rr_val and rr_val > 15:
                    rr_str = "> 1 : 10"
                else:
                    rr_str = "1 : 2.5+"

                lines.append(f"<b>{pick.category_title.upper()}</b>")
                lines.append(f"🏢 <b>{pick.ticker}</b> — {pick.name}")
                lines.append(f"🏷️ <i>{pick.sector}</i> | Skor: <b>{pick.composite_score:.1f}/100 (Grade {pick.grade})</b>")
                lines.append(f"💵 <b>Harga Terakhir:</b> Rp{cur_price:,.0f}")
                lines.append(f"🎯 <b>Area Beli (Entry):</b> <code>{entry}</code>")
                
                tp_line = f"🚀 <b>Target Profit 1:</b> Rp{tp1:,.0f} ({up1_str})"
                if tp2 and tp2 > tp1:
                    upside_2_pct = ((tp2 - cur_price) / cur_price * 100) if cur_price > 0 else 0
                    up2_str = f"+{upside_2_pct:.1f}%" if upside_2_pct >= 0 else f"{upside_2_pct:.1f}%"
                    tp_line += f" | <b>TP 2:</b> Rp{tp2:,.0f} ({up2_str})"
                lines.append(tp_line)

                lines.append(f"🛑 <b>Stop Loss (SL):</b> Rp{sl:,.0f} (-{downside_pct:.1f}%)")
                lines.append(f"⚖️ <b>Risk/Reward:</b> {rr_str}" + (f" | <b>Alokasi Max:</b> {pick.max_allocation_pct:.0f}%" if pick.max_allocation_pct else ""))

                # Fundamental Highlights
                metrics_text = (
                    f"ROE {pick.roe:.1f}% | PER {pick.per:.1f}x | PBV {pick.pbv:.2f}x | "
                    f"F-Score {pick.piotroski_f_score}/9"
                )
                if pick.dividend_yield > 0:
                    metrics_text += f" | Div {pick.dividend_yield:.1f}%"
                lines.append(f"📊 <code>{metrics_text}</code>")

                if pick.catalyst:
                    lines.append(f"💡 <i>Katalis: {pick.catalyst}</i>")

                lines.append("")  # empty separator line

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ <i>Disclaimer: Analisis berbasis data fundamental & teknikal IDX. Selalu terapkan money management dan disiplin cut loss sesuai toleransi risiko Anda.</i>")
        lines.append("🤖 <b>Generated by KeyStats OS Intelligence • @TradeXQBot</b>")

        return "\n".join(lines)

    def send_daily_picks(self, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Calculates market top picks and broadcasts the formatted message to Telegram."""
        try:
            logger.info("Starting calculation of market top picks for Telegram broadcast...")
            market_summary = self.market_service.get_market_summary()
            html_message = self.format_daily_picks_html(market_summary)

            send_res: Dict[str, Any] = {"success": False}

            # Safeguard message length under 4000 characters
            if len(html_message) > 4000:
                parts = [html_message[:4000], html_message[4000:]]
                for part in parts:
                    send_res = self.send_message(text=part, chat_id=chat_id, parse_mode="HTML")
                    if not send_res.get("success", False):
                        break
            else:
                send_res = self.send_message(text=html_message, chat_id=chat_id, parse_mode="HTML")

            logger.info(f"Telegram broadcast completed with result: {send_res}")
            return {
                "success": send_res.get("success", False),
                "broadcast_result": send_res,
                "total_picks": len(market_summary.top_picks),
                "top_tickers": [p.ticker for p in market_summary.top_picks]
            }
        except Exception as exc:
            logger.exception(f"Exception during send_daily_picks: {exc}")
            # Try to send error notification to Telegram
            try:
                self.send_message(
                    text=f"⚠️ <b>KeyStats Bot Error</b>\n\nGagal memproses rekomendasi saham harian:\n<code>{str(exc)}</code>",
                    chat_id=chat_id
                )
            except Exception:
                pass
            return {"success": False, "error": str(exc)}

    def send_test_message(self, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Sends a verification ping message to test Telegram bot connection."""
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text = (
            "<b>🔔 KEYSTATS PRO — Test Koneksi Telegram Bot Berhasil!</b>\n\n"
            f"Bot: <code>@TradeXQBot</code>\n"
            f"Waktu Server: <i>{date_str}</i>\n"
            f"Chat ID: <code>{chat_id or self.default_chat_id}</code>\n\n"
            "Koneksi antara engine perhitungan saham dan bot Telegram Anda telah aktif dan siap mengirimkan rekomendasi saham esok hari! 🚀"
        )
        return self.send_message(text=text, chat_id=chat_id, parse_mode="HTML")
