"""
CLI Command Line Interface for BRIGHTS — BRI Stock Intelligence.
Usage:
    python -m cli.commands calc BBRI
    python -m cli.commands compare BBCA BBRI BMRI
    python -m cli.commands screen --preset BUFFETT_MOAT
    python -m cli.commands list
"""

import app.config  # noqa: F401
import typer
from typing import List, Optional
from app.services.emiten_service import EmitenService
from app.services.comparison_service import ComparisonService
from app.services.screener_service import ScreenerService
from app.models.screener import ScreenerCriteria, ScreenerPreset
from cli.terminal_app import TerminalRenderer, console

app = typer.Typer(help="BRIGHTS — BRI Stock Intelligence CLI (Fundamental Analysis, Valuation & Shareholder Insight)")

# Initialize services
emiten_service = EmitenService()
comparison_service = ComparisonService(emiten_service)
screener_service = ScreenerService(emiten_service)


@app.command(name="calc")
def calc(
    ticker: str = typer.Argument(..., help="IDX Stock Ticker (e.g. BBRI, BBCA, ASII, ADRO)"),
    price: Optional[float] = typer.Option(None, "--price", "-p", help="Simulate with custom/override market price (IDR)"),
    live: bool = typer.Option(True, "--live/--cached", help="Fetch live realtime quote from the IDX data source")
):
    """Deep-dive fundamental analysis & valuation with live real-time price or simulation."""
    status_msg = f"[bold cyan]Fetching Realtime KeyStats for {ticker.upper()}..." if not price else f"[bold cyan]Simulating KeyStats for {ticker.upper()} at Rp{price:,.0f}..."
    with console.status(status_msg):
        report = emiten_service.analyze_single_emiten(ticker, override_price=price, force_live=live)
        
    if not report:
        console.print(f"[bold red]❌ Error: Emiten '{ticker.upper()}' tidak ditemukan atau data tidak tersedia.[/bold red]")
        raise typer.Exit(code=1)
        
    TerminalRenderer.render_single_emiten(report)


@app.command(name="shareholders")
def shareholders(
    ticker: str = typer.Argument(..., help="IDX Stock Ticker (e.g. BBRI, BBCA, ASII)")
):
    """Show real shareholder / stakeholder ownership composition, free float, holders, and KSEI SID stats."""
    with console.status(f"[bold cyan]Fetching shareholder composition for {ticker.upper()}..."):
        ownership = emiten_service.get_shareholders(ticker)

    if not ownership:
        console.print(
            f"[bold yellow]⚠️ Data pemegang saham untuk '{ticker.upper()}' tidak tersedia dari sumber data real yang terkonfigurasi.[/bold yellow]"
        )
        raise typer.Exit(code=1)

    TerminalRenderer.render_shareholders(ownership)


@app.command(name="compare")
def compare(
    tickers: List[str] = typer.Argument(..., help="List of stock tickers to compare (e.g. BBCA BBRI BMRI BBNI)")
):
    """Side-by-side peer comparison and benchmark analysis for multiple emitens."""
    with console.status(f"[bold cyan]Comparing {len(tickers)} emitens..."):
        resp = comparison_service.compare_emitens(tickers)
        
    if not resp.items:
        console.print("[bold red]❌ Error: Tidak ada emiten valid yang dapat dibandingkan.[/bold red]")
        raise typer.Exit(code=1)
        
    TerminalRenderer.render_comparison(resp)


@app.command(name="screen")
def screen(
    preset: Optional[str] = typer.Option(None, help="Preset: BUFFETT_MOAT, DIVIDEND_CASH_COW, GARP, DEEP_VALUE, MOMENTUM_QUALITY, AFFORDABLE_GEMS, UNDERVALUED_DEALS"),
    min_price: Optional[float] = typer.Option(None, "--min-price", help="Minimum stock price in IDR"),
    max_price: Optional[float] = typer.Option(None, "--max-price", help="Maximum stock price in IDR"),
    min_roe: Optional[float] = typer.Option(None, help="Minimum ROE %"),
    max_der: Optional[float] = typer.Option(None, help="Maximum DER ratio"),
    min_piotroski: Optional[int] = typer.Option(None, help="Minimum Piotroski F-Score (0-9)"),
    min_div_yield: Optional[float] = typer.Option(None, help="Minimum Dividend Yield %"),
    min_score: Optional[float] = typer.Option(None, help="Minimum Composite Score (0-100)"),
    buy_only: bool = typer.Option(False, "--buy-only", help="Filter only BUY and STRONG BUY recommendations"),
    sort_by: str = typer.Option("composite_score", "--sort-by", help="Sort by: composite_score, price_asc, price_desc, upside_pct, dividend_yield, roe")
):
    """Run quantitative fundamental screening with customizable filters, price ranges, or presets."""
    preset_enum = None
    if preset:
        try:
            preset_enum = ScreenerPreset[preset.upper()]
        except KeyError:
            console.print(f"[bold red]❌ Unknown preset '{preset}'. Available: {[p.name for p in ScreenerPreset]}[/bold red]")
            raise typer.Exit(code=1)
            
    criteria = ScreenerCriteria(
        preset=preset_enum,
        min_price=min_price,
        max_price=max_price,
        min_roe=min_roe,
        max_der=max_der,
        min_piotroski_f=min_piotroski,
        min_dividend_yield=min_div_yield,
        min_composite_score=min_score,
        only_buy_recommendations=buy_only,
        sort_by=sort_by
    )
    
    with console.status("[bold cyan]Running Multi-Factor Screener..."):
        resp = screener_service.run_screener(criteria)
        
    TerminalRenderer.render_screener(resp)


@app.command(name="recommend")
def recommend(
    budget: Optional[float] = typer.Option(None, "--budget", "-b", help="Max price budget per share in IDR (e.g. 5000)"),
    min_price: Optional[float] = typer.Option(None, "--min-price", help="Minimum stock price in IDR"),
    max_price: Optional[float] = typer.Option(None, "--max-price", help="Maximum stock price in IDR"),
    tier: Optional[str] = typer.Option(None, "--tier", "-t", help="Price tier: budget (<1k), mid (1k-5k), premium (>5k), or all"),
    min_score: float = typer.Option(60.0, "--min-score", "-s", help="Minimum fundamental composite score (0-100)"),
    buy_only: bool = typer.Option(True, "--buy-only/--all", help="Only show BUY and STRONG BUY recommendations"),
    sector: Optional[str] = typer.Option(None, "--sector", help="Filter by sector (e.g. Financials, Energy)"),
    sort_by: str = typer.Option("composite_score", "--sort-by", help="Sort by: composite_score, price_asc, price_desc, upside_pct, dividend_yield, roe"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max recommendations to display")
):
    """Find & recommend top quality stocks filtered by price budget or price tier."""
    if tier and tier.lower() == "all":
        with console.status("[bold cyan]Generating Price-Tier Stock Recommendations..."):
            tier_resp = screener_service.get_price_tier_recommendations()
        TerminalRenderer.render_price_tiers(tier_resp)
        return

    # Handle tier aliases
    effective_min_price = min_price
    effective_max_price = max_price or budget

    if tier:
        t = tier.lower()
        if t in ["budget", "cheap", "low", "1"]:
            effective_min_price = None
            effective_max_price = 1000.0
        elif t in ["mid", "mid-range", "medium", "2"]:
            effective_min_price = 1000.0
            effective_max_price = 5000.0
        elif t in ["premium", "bluechip", "high", "3"]:
            effective_min_price = 5000.0
            effective_max_price = None

    price_desc = "Semua Rentang Harga"
    if effective_min_price and effective_max_price:
        price_desc = f"Rp{effective_min_price:,.0f} - Rp{effective_max_price:,.0f}"
    elif effective_max_price:
        price_desc = f"<= Rp{effective_max_price:,.0f}"
    elif effective_min_price:
        price_desc = f">= Rp{effective_min_price:,.0f}"

    title = f"🎯 REKOMENDASI SAHAM PILIHAN (Harga: {price_desc})"
    with console.status(f"[bold cyan]Finding Top Stock Recommendations ({price_desc})..."):
        items = screener_service.get_recommendations_by_price(
            min_price=effective_min_price,
            max_price=effective_max_price,
            min_score=min_score,
            only_buy=buy_only,
            sector=sector,
            sort_by=sort_by,
            limit=limit
        )

    if not items:
        console.print(f"[bold yellow]⚠️ Tidak ada rekomendasi saham yang cocok dengan harga {price_desc} dan skor >= {min_score}.[/bold yellow]")
        console.print("[dim]Tip: Coba turunkan --min-score atau gunakan --all untuk melihat semua saham.[/dim]")
        return

    TerminalRenderer.render_price_recommendations(items, title=title)


@app.command(name="summary")
def summary():
    """Market-wide fundamental overview, statistical aggregations & best stock picks for tomorrow."""
    from app.services.market_summary_service import MarketSummaryService
    market_service = MarketSummaryService(emiten_service)
    
    with console.status("[bold cyan]Analyzing all emitens & selecting top picks for tomorrow..."):
        resp = market_service.get_market_summary()
        
    TerminalRenderer.render_market_summary(resp)


@app.command(name="list")
def list_emitens():
    """List all supported/cached IDX emitens."""
    tickers = emiten_service.list_all_available_tickers()
    console.print(f"[bold green]Daftar Emiten Terdaftar ({len(tickers)} Emitens):[/bold green]")
    for t in tickers:
        console.print(f"  • [bold cyan]{t}[/bold cyan]")


@app.command(name="fx")
def fx_rate(
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Force refresh rate from live source")
):
    """View real-time USD/IDR exchange rate & currency stats."""
    from app.services.currency_service import CurrencyService
    curr_service = CurrencyService()
    
    with console.status("[bold cyan]Fetching Live USD/IDR Foreign Exchange Rate..."):
        rate_resp = curr_service.get_live_rate(force_refresh=refresh)
        
    TerminalRenderer.render_currency_rates(rate_resp)


@app.command(name="convert")
def convert_currency(
    amount: float = typer.Argument(..., help="Nominal amount to convert (e.g. 10000000 or 500)"),
    from_curr: str = typer.Option("IDR", "--from", "-f", help="Source currency (IDR or USD)"),
    to_curr: str = typer.Option("USD", "--to", "-t", help="Target currency (USD or IDR)")
):
    """Convert amount between IDR and USD using live exchange rates."""
    from app.services.currency_service import CurrencyService
    curr_service = CurrencyService()
    
    with console.status(f"[bold cyan]Converting {amount:,.2f} {from_curr.upper()} ➔ {to_curr.upper()}..."):
        conv_resp = curr_service.convert(amount=amount, from_currency=from_curr, to_currency=to_curr)
        
    TerminalRenderer.render_currency_conversion(conv_resp)


@app.command(name="chart")
def chart_command(
    ticker: str = typer.Argument(..., help="IDX Stock Ticker (e.g. BBRI, BBCA, ASII, ADRO, UNTR)"),
    timeframe: str = typer.Option("1y", "--timeframe", "-t", help="Timeframe: 1mo, 3mo, 6mo, 1y, 5y")
):
    """View technical candlestick analysis, breakouts, gaps, support/resistance, and fundamental target overlay."""
    from app.services.chart_service import ChartService
    chart_service = ChartService(emiten_service)
    
    with console.status(f"[bold cyan]Scanning Technical Chart & Patterns for {ticker.upper()} ({timeframe.upper()})..."):
        chart_resp = chart_service.get_chart_data(ticker, timeframe=timeframe)
        
    if not chart_resp:
        console.print(f"[bold red]❌ Error: Data chart untuk '{ticker.upper()}' tidak ditemukan.[/bold red]")
        raise typer.Exit(code=1)
        
    TerminalRenderer.render_chart_technicals(chart_resp)


@app.command(name="telegram")
def telegram_command(
    test: bool = typer.Option(False, "--test", help="Send a test ping message instead of full market picks"),
    chat_id: Optional[str] = typer.Option(None, "--chat-id", "-c", help="Override destination Telegram Chat ID")
):
    """Calculate multi-factor top picks and broadcast directly to Telegram Bot (@TradeXQBot)."""
    from app.services.telegram_service import TelegramBotService
    tele_service = TelegramBotService()
    
    if not tele_service.is_configured:
        console.print("[bold red]❌ Error: TELEGRAM_BOT_TOKEN belum diset di environment atau file backend/.env.[/bold red]")
        raise typer.Exit(code=1)

    if test:
        with console.status("[bold cyan]Sending test ping to Telegram Bot..."):
            res = tele_service.send_test_message(chat_id=chat_id)
        if res.get("success"):
            console.print("[bold green]✅ Test message successfully sent to Telegram![/bold green]")
        else:
            console.print(f"[bold red]❌ Failed to send test message: {res.get('error')}[/bold red]")
            raise typer.Exit(code=1)
        return

    with console.status("[bold cyan]Calculating multi-factor top picks & broadcasting to Telegram..."):
        res = tele_service.send_daily_picks(chat_id=chat_id)

    b_res = res.get("broadcast_result", {})
    if b_res.get("success"):
        console.print(f"[bold green]✅ Sukses! Rekomendasi saham ({', '.join(res.get('top_tickers', []))}) berhasil dikirim ke Telegram![/bold green]")
    else:
        console.print(f"[bold red]❌ Gagal mengirim ke Telegram: {b_res.get('error')}[/bold red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()



