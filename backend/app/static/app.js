/**
 * Frontend JavaScript for KeyStats Pro — Apple OS Equity Intelligence
 * Institutional Valuation & Global Macro Terminal
 * With Live Multi-Source IDR ⇄ USD Currency Conversion
 */

document.addEventListener('DOMContentLoaded', () => {
    console.log('KeyStats Engine Frontend Initializing...');

    // -------------------------------------------------------------
    // 0. Currency State & Realtime Forex Engine
    // -------------------------------------------------------------
    let currentCurrency = localStorage.getItem('idx_keystats_currency') || 'IDR';
    let liveFxRate = {
        usd_to_idr: 16250.0,
        idr_to_usd: 1.0 / 16250.0,
        source: 'Bank Indonesia JISDOR',
        last_updated_formatted: 'Live',
        change_24h: 0,
        change_pct_24h: 0
    };

    // Cached data for instant re-rendering across currency toggles
    let cachedSingleEmitenData = null;
    let cachedComparisonData = null;
    let cachedScreenerData = null;
    let currentMarketData = null;
    let allMarketEmitens = [];
    let currentScreenerResults = [];
    let currentActiveTicker = 'BBRI';

    // Candlestick Chart & Technicals State
    let currentChartTimeframe = '1y';
    let tvChartInstance = null;
    let tvCandleSeries = null;
    let tvVolumeSeries = null;
    let tvEma20Series = null;
    let tvSma50Series = null;
    let showMaOverlays = true;
    let showFundOverlays = true;
    let cachedChartData = null;
    let currentFinancialMatrixTab = 'eps';

    // -------------------------------------------------------------
    // Formatting Helpers (Reactive to currentCurrency)
    // -------------------------------------------------------------
    function formatPrice(valInIdr, showPrefix = true) {
        if (valInIdr === null || valInIdr === undefined || isNaN(valInIdr)) return '-';
        const num = Number(valInIdr);
        if (currentCurrency === 'USD') {
            const usdVal = num * liveFxRate.idr_to_usd;
            const digits = usdVal < 1 ? 3 : 2;
            const formatted = usdVal.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
            return showPrefix ? `$${formatted}` : formatted;
        } else {
            const formatted = num.toLocaleString('id-ID');
            return showPrefix ? `Rp ${formatted}` : formatted;
        }
    }

    function formatMarketCap(capInIdr) {
        if (!capInIdr || isNaN(capInIdr)) return '-';
        if (currentCurrency === 'USD') {
            const usdCap = capInIdr * liveFxRate.idr_to_usd;
            if (usdCap >= 1e9) {
                return `$ ${(usdCap / 1e9).toFixed(2)} B`;
            } else {
                return `$ ${(usdCap / 1e6).toFixed(1)} M`;
            }
        } else {
            if (capInIdr >= 1e12) {
                return `Rp ${(capInIdr / 1e12).toFixed(1)} T`;
            } else {
                return `Rp ${(capInIdr / 1e9).toFixed(1)} M`;
            }
        }
    }

    function formatLargeCashFlow(valInIdr) {
        if (valInIdr === null || valInIdr === undefined || isNaN(valInIdr)) return '-';
        if (currentCurrency === 'USD') {
            const usdVal = valInIdr * liveFxRate.idr_to_usd;
            if (Math.abs(usdVal) >= 1e9) {
                return `$ ${(usdVal / 1e9).toFixed(2)} B`;
            } else {
                return `$ ${(usdVal / 1e6).toFixed(1)} M`;
            }
        } else {
            if (Math.abs(valInIdr) >= 1e12) {
                return `Rp ${(valInIdr / 1e12).toFixed(1)} T`;
            } else {
                return `Rp ${(valInIdr / 1e9).toFixed(1)} M`;
            }
        }
    }

    function getCurrencySymbol() {
        return currentCurrency === 'USD' ? '$' : 'Rp';
    }

    // -------------------------------------------------------------
    // Live FX Rate Loader & Realtime Synchronizer
    // -------------------------------------------------------------
    async function fetchLiveCurrencyRate(forceRefresh = false) {
        try {
            const resp = await fetch(`/api/v1/currency/rate?refresh=${forceRefresh}`);
            if (resp.ok) {
                const data = await resp.json();
                liveFxRate = data;
                updateFxUI();
            }
        } catch (err) {
            console.warn('Could not fetch live currency rate, using cache/fallback:', err);
        }
    }

    function updateFxUI() {
        const navPill = document.getElementById('nav-fx-rate-text');
        if (navPill) {
            navPill.textContent = `1 USD = Rp ${liveFxRate.usd_to_idr.toLocaleString('id-ID')}`;
        }

        const modalHighlight = document.getElementById('modal-fx-rate-highlight');
        if (modalHighlight) {
            modalHighlight.textContent = `1 USD = Rp ${liveFxRate.usd_to_idr.toLocaleString('id-ID')}`;
        }

        const modalInverse = document.getElementById('modal-fx-inverse');
        if (modalInverse) {
            modalInverse.textContent = `1 IDR = $${liveFxRate.idr_to_usd.toFixed(8)}`;
        }

        const modalSource = document.getElementById('modal-fx-source');
        if (modalSource) {
            modalSource.textContent = liveFxRate.source || 'Live FX';
        }

        const modalUpdated = document.getElementById('modal-fx-updated');
        if (modalUpdated) {
            modalUpdated.textContent = `Update: ${liveFxRate.last_updated_formatted || 'Hari Ini'}`;
        }

        // Recalculate converter if open
        calculateConverterResult();
    }

    // -------------------------------------------------------------
    // Global Currency Switcher (IDR / USD Toggle)
    // -------------------------------------------------------------
    function setGlobalCurrency(currency) {
        currentCurrency = currency.toUpperCase();
        localStorage.setItem('idx_keystats_currency', currentCurrency);

        const btnIdr = document.getElementById('currency-btn-idr');
        const btnUsd = document.getElementById('currency-btn-usd');

        if (currentCurrency === 'USD') {
            if (btnUsd) {
                btnUsd.className = "currency-toggle-btn px-2 sm:px-2.5 py-1 rounded-lg transition-all text-white bg-cyan-600 shadow-sm flex items-center gap-1";
            }
            if (btnIdr) {
                btnIdr.className = "currency-toggle-btn px-2 sm:px-2.5 py-1 rounded-lg transition-all text-slate-400 hover:text-white flex items-center gap-1";
            }
        } else {
            if (btnIdr) {
                btnIdr.className = "currency-toggle-btn px-2 sm:px-2.5 py-1 rounded-lg transition-all text-white bg-brand-600 shadow-sm flex items-center gap-1";
            }
            if (btnUsd) {
                btnUsd.className = "currency-toggle-btn px-2 sm:px-2.5 py-1 rounded-lg transition-all text-slate-400 hover:text-white flex items-center gap-1";
            }
        }

        // Update sim price input placeholder
        const simInput = document.getElementById('sim-price-input');
        if (simInput) {
            simInput.placeholder = currentCurrency === 'USD' ? '$ harga...' : 'Rp harga...';
        }

        // Re-render active views with updated currency
        if (cachedSingleEmitenData) renderSingleEmiten(cachedSingleEmitenData);
        if (currentMarketData) renderMarketOverview(currentMarketData);
        if (cachedComparisonData) renderComparison(cachedComparisonData);
        if (cachedScreenerData) renderScreener(cachedScreenerData);
    }

    const btnIdr = document.getElementById('currency-btn-idr');
    const btnUsd = document.getElementById('currency-btn-usd');
    if (btnIdr) btnIdr.addEventListener('click', () => setGlobalCurrency('IDR'));
    if (btnUsd) btnUsd.addEventListener('click', () => setGlobalCurrency('USD'));

    // -------------------------------------------------------------
    // Interactive Currency Converter Modal Logic
    // -------------------------------------------------------------
    const currencyModal = document.getElementById('currency-modal');
    const fxRatePill = document.getElementById('fx-rate-pill');
    const closeCurrencyModalBtn = document.getElementById('close-currency-modal-btn');
    const modalRefreshBtn = document.getElementById('modal-refresh-rate-btn');
    const converterInputFrom = document.getElementById('converter-input-from');
    const converterInputTo = document.getElementById('converter-input-to');
    const converterSwapBtn = document.getElementById('converter-swap-btn');
    const converterCopyBtn = document.getElementById('converter-copy-btn');
    const converterSummaryText = document.getElementById('converter-summary-text');
    const modalRefreshSpinner = document.getElementById('modal-refresh-spinner');

    let converterDirection = 'IDR_TO_USD'; // 'IDR_TO_USD' or 'USD_TO_IDR'

    function openCurrencyModal() {
        if (currencyModal) {
            currencyModal.classList.remove('hidden');
            calculateConverterResult();
        }
    }

    function closeCurrencyModal() {
        if (currencyModal) {
            currencyModal.classList.add('hidden');
        }
    }

    if (fxRatePill) fxRatePill.addEventListener('click', openCurrencyModal);
    if (closeCurrencyModalBtn) closeCurrencyModalBtn.addEventListener('click', closeCurrencyModal);

    if (currencyModal) {
        currencyModal.addEventListener('click', (e) => {
            if (e.target === currencyModal) closeCurrencyModal();
        });
    }

    function calculateConverterResult() {
        if (!converterInputFrom || !converterInputTo) return;
        const val = parseFloat(converterInputFrom.value) || 0;

        if (converterDirection === 'IDR_TO_USD') {
            const converted = val * liveFxRate.idr_to_usd;
            converterInputTo.value = converted.toFixed(2);
            if (converterSummaryText) {
                converterSummaryText.textContent = `Rp ${val.toLocaleString('id-ID')} = $${converted.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            }
        } else {
            const converted = val * liveFxRate.usd_to_idr;
            converterInputTo.value = Math.round(converted);
            if (converterSummaryText) {
                converterSummaryText.textContent = `$${val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} = Rp ${Math.round(converted).toLocaleString('id-ID')}`;
            }
        }
    }

    function swapConverterDirection() {
        converterDirection = converterDirection === 'IDR_TO_USD' ? 'USD_TO_IDR' : 'IDR_TO_USD';

        const labelFrom = document.getElementById('converter-label-from');
        const badgeFrom = document.getElementById('converter-badge-from');
        const symbolFrom = document.getElementById('converter-symbol-from');

        const labelTo = document.getElementById('converter-label-to');
        const badgeTo = document.getElementById('converter-badge-to');
        const symbolTo = document.getElementById('converter-symbol-to');
        const presetsContainer = document.getElementById('converter-presets-container');

        if (converterDirection === 'IDR_TO_USD') {
            if (labelFrom) labelFrom.textContent = "Nominal Rupiah (IDR):";
            if (badgeFrom) { badgeFrom.textContent = "🇮🇩 Indonesia Rupiah"; badgeFrom.className = "text-[11px] font-mono text-brand-400"; }
            if (symbolFrom) symbolFrom.textContent = "Rp";

            if (labelTo) labelTo.textContent = "Hasil Konversi (USD):";
            if (badgeTo) { badgeTo.textContent = "🇺🇸 US Dollar"; badgeTo.className = "text-[11px] font-mono text-cyan-400"; }
            if (symbolTo) symbolTo.textContent = "$";

            if (converterInputFrom) converterInputFrom.value = "10000000";

            if (presetsContainer) {
                presetsContainer.innerHTML = `
                    <button class="conv-preset-chip px-2.5 py-1 rounded-lg bg-dark-bg border border-dark-border hover:border-brand-500 text-xs font-mono text-slate-300 hover:text-white transition" data-amount="1000000">Rp 1 Juta</button>
                    <button class="conv-preset-chip px-2.5 py-1 rounded-lg bg-dark-bg border border-dark-border hover:border-brand-500 text-xs font-mono text-slate-300 hover:text-white transition" data-amount="10000000">Rp 10 Juta</button>
                    <button class="conv-preset-chip px-2.5 py-1 rounded-lg bg-dark-bg border border-dark-border hover:border-brand-500 text-xs font-mono text-slate-300 hover:text-white transition" data-amount="50000000">Rp 50 Juta</button>
                    <button class="conv-preset-chip px-2.5 py-1 rounded-lg bg-dark-bg border border-dark-border hover:border-brand-500 text-xs font-mono text-slate-300 hover:text-white transition" data-amount="100000000">Rp 100 Juta</button>
                    <button class="conv-preset-chip px-2.5 py-1 rounded-lg bg-dark-bg border border-dark-border hover:border-brand-500 text-xs font-mono text-slate-300 hover:text-white transition" data-amount="1000000000">Rp 1 Miliar</button>
                `;
                attachPresetListeners();
            }
        } else {
            if (labelFrom) labelFrom.textContent = "Nominal US Dollar (USD):";
            if (badgeFrom) { badgeFrom.textContent = "🇺🇸 US Dollar"; badgeFrom.className = "text-[11px] font-mono text-cyan-400"; }
            if (symbolFrom) symbolFrom.textContent = "$";

            if (labelTo) labelTo.textContent = "Hasil Konversi (IDR):";
            if (badgeTo) { badgeTo.textContent = "🇮🇩 Indonesia Rupiah"; badgeTo.className = "text-[11px] font-mono text-brand-400"; }
            if (symbolTo) symbolTo.textContent = "Rp";

            if (converterInputFrom) converterInputFrom.value = "1000";

            if (presetsContainer) {
                presetsContainer.innerHTML = `
                    <button class="conv-preset-chip px-2.5 py-1 rounded-lg bg-dark-bg border border-dark-border hover:border-cyan-500 text-xs font-mono text-slate-300 hover:text-white transition" data-amount="100">$100</button>
                    <button class="conv-preset-chip px-2.5 py-1 rounded-lg bg-dark-bg border border-dark-border hover:border-cyan-500 text-xs font-mono text-slate-300 hover:text-white transition" data-amount="500">$500</button>
                    <button class="conv-preset-chip px-2.5 py-1 rounded-lg bg-dark-bg border border-dark-border hover:border-cyan-500 text-xs font-mono text-slate-300 hover:text-white transition" data-amount="1000">$1,000</button>
                    <button class="conv-preset-chip px-2.5 py-1 rounded-lg bg-dark-bg border border-dark-border hover:border-cyan-500 text-xs font-mono text-slate-300 hover:text-white transition" data-amount="5000">$5,000</button>
                    <button class="conv-preset-chip px-2.5 py-1 rounded-lg bg-dark-bg border border-dark-border hover:border-cyan-500 text-xs font-mono text-slate-300 hover:text-white transition" data-amount="10000">$10,000</button>
                `;
                attachPresetListeners();
            }
        }
        calculateConverterResult();
    }

    function attachPresetListeners() {
        document.querySelectorAll('.conv-preset-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const amt = chip.dataset.amount;
                if (converterInputFrom && amt) {
                    converterInputFrom.value = amt;
                    calculateConverterResult();
                }
            });
        });
    }

    if (converterInputFrom) {
        converterInputFrom.addEventListener('input', calculateConverterResult);
    }

    if (converterSwapBtn) {
        converterSwapBtn.addEventListener('click', swapConverterDirection);
    }

    if (modalRefreshBtn) {
        modalRefreshBtn.addEventListener('click', async () => {
            if (modalRefreshSpinner) modalRefreshSpinner.classList.add('animate-spin');
            await fetchLiveCurrencyRate(true);
            setTimeout(() => {
                if (modalRefreshSpinner) modalRefreshSpinner.classList.remove('animate-spin');
            }, 600);
        });
    }

    if (converterCopyBtn) {
        converterCopyBtn.addEventListener('click', () => {
            if (converterSummaryText) {
                navigator.clipboard.writeText(converterSummaryText.textContent.trim()).then(() => {
                    const originalText = converterCopyBtn.innerHTML;
                    converterCopyBtn.innerHTML = "<span>✓</span> <span>Tersalin!</span>";
                    converterCopyBtn.classList.add('bg-brand-600', 'text-white');
                    setTimeout(() => {
                        converterCopyBtn.innerHTML = originalText;
                        converterCopyBtn.classList.remove('bg-brand-600', 'text-white');
                    }, 1500);
                });
            }
        });
    }

    attachPresetListeners();

    // -------------------------------------------------------------
    // 1. Tab Navigation
    // -------------------------------------------------------------
    const tabs = {
        'tab-market': 'section-market',
        'tab-macro': 'section-macro',
        'tab-calendar': 'section-calendar',
        'tab-single': 'section-single',
        'tab-compare': 'section-compare',
        'tab-screener': 'section-screener'
    };

    Object.keys(tabs).forEach(tabId => {
        const btn = document.getElementById(tabId);
        if (!btn) return;
        btn.addEventListener('click', () => {
            // Update Tab Styles
            document.querySelectorAll('.nav-tab').forEach(t => {
                t.classList.remove('active', 'text-white', 'bg-brand-600', 'shadow-md');
                t.classList.add('text-slate-400');
            });
            btn.classList.add('active', 'text-white', 'bg-brand-600', 'shadow-md');
            btn.classList.remove('text-slate-400');

            // Show corresponding section
            document.querySelectorAll('.tab-content').forEach(s => s.classList.add('hidden'));
            const targetSection = document.getElementById(tabs[tabId]);
            if (targetSection) {
                targetSection.classList.remove('hidden');
            }

            // Trigger fetch for tab if needed
            if (tabId === 'tab-market') {
                loadMarketSummary();
            } else if (tabId === 'tab-macro') {
                loadMacroOverview();
            } else if (tabId === 'tab-calendar') {
                loadCalendarData();
            } else if (tabId === 'tab-compare') {
                runComparison();
            } else if (tabId === 'tab-screener') {
                runScreener('BUFFETT_MOAT');
            }
        });
    });

    // -------------------------------------------------------------
    // 2. Single Emiten Analysis
    // -------------------------------------------------------------
    const singleInput = document.getElementById('single-ticker-input');
    const searchBtn = document.getElementById('single-search-btn');
    const refreshLiveBtn = document.getElementById('refresh-live-price-btn');
    const simPriceInput = document.getElementById('sim-price-input');
    const simPriceBtn = document.getElementById('sim-price-btn');

    async function loadSingleEmiten(ticker, customPrice = null, forceLive = false, isSilent = false, updateUrl = true) {
        if (!ticker) return;
        ticker = ticker.trim().toUpperCase();
        currentActiveTicker = ticker;

        if (singleInput && singleInput.value !== ticker) {
            singleInput.value = ticker;
        }

        // Dynamic URL update to /stock/[TICKER]
        if (updateUrl && window.history && window.history.pushState) {
            const currentPath = window.location.pathname;
            const targetPath = `/stock/${ticker}`;
            if (currentPath !== targetPath) {
                window.history.pushState({ ticker }, `Saham ${ticker} - KeyStats Pro`, targetPath);
            }
            document.title = `${ticker} - Analisis Fundamental, Valuasi & Sentimen | KeyStats Pro`;
        }
        
        let url = `/api/v1/emiten/${ticker}?live=${forceLive}`;
        if (customPrice && customPrice > 0) {
            // If user inputted USD price in simulation, convert to IDR before sending
            const priceInIdr = currentCurrency === 'USD' ? (customPrice * liveFxRate.usd_to_idr) : customPrice;
            url += `&price=${priceInIdr}`;
        }
        
        try {
            const resp = await fetch(url);
            if (!resp.ok) {
                if (!isSilent) {
                    alert(`Emiten '${ticker}' tidak ditemukan atau data belum tersedia.`);
                }
                return;
            }
            const data = await resp.json();
            cachedSingleEmitenData = data;
            renderSingleEmiten(data);
        } catch (err) {
            console.error('Error loading single emiten:', err);
            if (!isSilent) {
                alert('Gagal mengambil data emiten.');
            }
        }
    }

    function renderSingleEmiten(data) {
        if (!data) return;

        // Load and render Candlestick Chart for this ticker
        loadStockChart(data.ticker, currentChartTimeframe);

        const setTxt = (id, val) => {
            const el = document.getElementById(id);
            if (el && val !== undefined && val !== null) el.textContent = val;
        };

        setTxt('r-ticker', data.ticker);
        setTxt('r-name', data.name);
        setTxt('r-sector', data.sector);
        setTxt('r-industry', data.industry);
        
        // Formatted Price and Market Cap
        setTxt('r-price', formatPrice(data.current_price));
        setTxt('r-market-cap', formatMarketCap(data.market_cap));

        // Realtime Price Change %
        const priceChangeElem = document.getElementById('r-price-change');
        const pChange = data.price_change_pct || 0;
        if (priceChangeElem) {
            priceChangeElem.textContent = `(${pChange >= 0 ? '+' : ''}${pChange.toFixed(2)}%)`;
            priceChangeElem.className = pChange >= 0 ? "text-sm font-semibold font-mono text-brand-400" : "text-sm font-semibold font-mono text-rose-400";
        }

        // Upside Badge
        const upside = data.valuation?.upside_downside_pct || 0;
        const upsideBadge = document.getElementById('r-upside-badge');
        if (upsideBadge) {
            upsideBadge.textContent = `${upside > 0 ? '+' : ''}${upside.toFixed(1)}% Upside`;
            upsideBadge.className = upside > 0 
                ? "text-xs font-sans font-bold px-2.5 py-1 rounded-full bg-brand-500/20 text-brand-400 border border-brand-500/30"
                : "text-xs font-sans font-bold px-2.5 py-1 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30";
        }

        // Composite Score & Grade
        setTxt('r-composite-score', data.composite_score);
        const gradeElem = document.getElementById('r-grade');
        if (gradeElem) {
            gradeElem.textContent = `GRADE ${data.grade}`;
            if (['A+', 'A'].includes(data.grade)) {
                gradeElem.className = "px-2.5 py-0.5 text-xs font-bold font-mono rounded bg-brand-500/20 text-brand-400 border border-brand-500/40";
            } else if (data.grade === 'B') {
                gradeElem.className = "px-2.5 py-0.5 text-xs font-bold font-mono rounded bg-amber-500/20 text-amber-400 border border-amber-500/40";
            } else {
                gradeElem.className = "px-2.5 py-0.5 text-xs font-bold font-mono rounded bg-rose-500/20 text-rose-400 border border-rose-500/40";
            }
        }

        // Action Verdict
        const verdictBadge = document.getElementById('r-verdict-badge');
        if (verdictBadge) {
            verdictBadge.textContent = data.verdict;
            if (data.verdict === 'STRONG BUY' || data.verdict === 'BUY') {
                verdictBadge.className = "mt-2 px-3.5 py-1.5 rounded-xl font-extrabold text-xs sm:text-sm tracking-wide bg-brand-600 text-white shadow-lg shadow-brand-600/30";
            } else if (data.verdict === 'HOLD') {
                verdictBadge.className = "mt-2 px-3.5 py-1.5 rounded-xl font-extrabold text-xs sm:text-sm tracking-wide bg-amber-500 text-dark-bg shadow-lg shadow-amber-500/30";
            } else {
                verdictBadge.className = "mt-2 px-3.5 py-1.5 rounded-xl font-extrabold text-xs sm:text-sm tracking-wide bg-rose-500 text-white shadow-lg shadow-rose-500/30";
            }
        }
        setTxt('r-fair-value-text', `Target: ${formatPrice(data.valuation?.average_fair_value || 0)}`);

        // Sensitivity Matrix Scenarios
        const sensContainer = document.getElementById('sensitivity-cards-container');
        if (sensContainer && data.price_sensitivity_scenarios) {
            sensContainer.innerHTML = data.price_sensitivity_scenarios.map(sc => {
                const isBase = sc.price_change_pct === 0.0;
                const borderClass = isBase ? 'border-brand-500 bg-brand-500/10 shadow-lg ring-1 ring-brand-500/40' : 'border-dark-border bg-dark-bg/60 hover:border-slate-500';
                const label = isBase ? 'HARGA SEKARANG' : `${sc.price_change_pct > 0 ? '+' : ''}${sc.price_change_pct}%`;
                const verdictCol = sc.verdict === 'STRONG BUY' || sc.verdict === 'BUY' ? 'text-brand-400' : (sc.verdict === 'HOLD' ? 'text-amber-400' : 'text-rose-400');

                return `
                    <div class="p-2.5 rounded-xl border ${borderClass} transition cursor-pointer" onclick="simulatePrice(${sc.simulated_price})">
                        <div class="text-[10px] font-bold ${isBase ? 'text-brand-300' : 'text-slate-400'}">${label}</div>
                        <div class="text-sm font-bold text-white mt-0.5">${formatPrice(sc.simulated_price)}</div>
                        <div class="text-[11px] text-slate-300 mt-1">PER: <strong>${sc.per}x</strong></div>
                        <div class="text-[11px] text-purple-300">Div: <strong>${sc.dividend_yield}%</strong></div>
                        <div class="text-[11px] font-bold text-cyan-300 mt-0.5">Skor: ${sc.composite_score}</div>
                        <div class="text-[10px] font-bold ${verdictCol} mt-0.5">${sc.verdict}</div>
                    </div>
                `;
            }).join('');
        }

        // Pillar 1: Valuation
        setTxt('p-val-score', `${data.radar?.valuation || 0}/100`);
        setTxt('r-per', `${data.valuation?.per || 0}x`);
        setTxt('r-pbv', `${data.valuation?.pbv || 0}x`);
        setTxt('r-ev-ebitda', `${data.valuation?.ev_ebitda || 0}x`);
        setTxt('r-peg', data.valuation?.peg_ratio ? `${data.valuation.peg_ratio}x` : 'N/A');
        setTxt('r-graham', data.valuation?.graham_number ? formatPrice(data.valuation.graham_number) : 'N/A');
        setTxt('r-dcf', data.valuation?.dcf_fair_value ? formatPrice(data.valuation.dcf_fair_value) : 'N/A');
        setTxt('r-avg-fair', formatPrice(data.valuation?.average_fair_value || 0));

        // Pillar 2: Profitability
        setTxt('p-prof-score', `${data.radar?.profitability || 0}/100`);
        setTxt('r-roe', `${data.profitability?.roe || 0}%`);
        setTxt('r-roa', `${data.profitability?.roa || 0}%`);
        setTxt('r-roic', `${data.profitability?.roic || 0}%`);
        setTxt('r-gpm', `${data.profitability?.gpm || 0}%`);
        setTxt('r-npm', `${data.profitability?.npm || 0}%`);
        setTxt('r-dupont-ato', `${data.profitability?.dupont_asset_turnover || 0}x`);
        setTxt('r-dupont-em', `${data.profitability?.dupont_equity_multiplier || 0}x`);

        // Pillar 3: Health & Solvency
        setTxt('p-health-score', `${data.radar?.financial_health || 0}/100`);
        setTxt('r-der', `${data.solvency?.der || 0}x`);
        setTxt('r-net-der', `${data.solvency?.net_debt_to_equity || 0}x`);
        setTxt('r-altman', `${data.solvency?.altman_z_score || 0} (${data.solvency?.altman_zone || 'SAFE'})`);
        setTxt('r-piotroski', `${data.quality?.piotroski_f_score || 0} / 9`);
        setTxt('r-current-ratio', `${data.liquidity?.current_ratio || 0}x`);
        setTxt('r-cfo-ratio', `${data.quality?.cfo_to_net_income || 0}x`);
        setTxt('r-quality-badge', data.quality?.piotroski_f_score >= 7 ? 'PRISTINE' : 'ADEQUATE');

        // Pillar 4: Cash Flow & Dividend
        setTxt('p-cf-score', `${data.radar?.cash_flow_quality || 0}/100`);
        setTxt('r-fcf', formatLargeCashFlow(data.cash_flow_dividend?.fcf || 0));
        setTxt('r-fcf-yield', `${data.cash_flow_dividend?.fcf_yield || 0}%`);
        setTxt('r-div-yield', `${data.cash_flow_dividend?.dividend_yield || 0}%`);
        setTxt('r-dpr', `${data.cash_flow_dividend?.dpr || 0}%`);
        setTxt('r-rev-growth', `${(data.growth?.revenue_growth_yoy || 0) > 0 ? '+' : ''}${data.growth?.revenue_growth_yoy || 0}%`);
        setTxt('r-eps-growth', `${(data.growth?.eps_growth_yoy || 0) > 0 ? '+' : ''}${data.growth?.eps_growth_yoy || 0}%`);
        setTxt('r-div-safe', (data.cash_flow_dividend?.dpr || 0) <= 80 ? 'SUSTAINABLE' : 'HIGH PAYOUT');

        // Bank Panel
        const bankPanel = document.getElementById('bank-panel');
        if (bankPanel) {
            if (data.bank_metrics && data.bank_metrics.is_bank) {
                bankPanel.classList.remove('hidden');
                setTxt('b-car', `${data.bank_metrics.car}%`);
                setTxt('b-npl-gross', `${data.bank_metrics.npl_gross}%`);
                setTxt('b-npl-net', `${data.bank_metrics.npl_net}%`);
                setTxt('b-nim', `${data.bank_metrics.nim}%`);
                setTxt('b-cir', `${data.bank_metrics.cost_to_income}%`);
                setTxt('b-casa', `${data.bank_metrics.casa_ratio}%`);
                setTxt('b-ldr', `${data.bank_metrics.ldr}%`);
            } else {
                bankPanel.classList.add('hidden');
            }
        }

        // Render Stockbit-Grade Multi-Year Quarterly Financial Matrix (2020 - 2026+)
        renderStockbitFinancialMatrix(data, currentFinancialMatrixTab);

        // Render Shareholder / Stakeholder Ownership Composition
        renderOwnership(data.ownership);

        // High-Conviction Buy Engine & 10-Point Checklist
        if (data.buy_conviction) {
            const bc = data.buy_conviction;
            const sc = bc.scenarios;
            const ps = bc.position_sizing;

            // Buy Zone Badge & Description
            const buyZoneBadge = document.getElementById('r-buy-zone-badge');
            if (buyZoneBadge) {
                buyZoneBadge.textContent = sc.buy_zone_label || sc.buy_zone;
                if (sc.buy_zone === 'STRONG ACCUMULATION') {
                    buyZoneBadge.className = "px-3 py-0.5 rounded-full text-xs font-bold font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm shadow-emerald-500/20";
                } else if (sc.buy_zone === 'MODERATE BUY') {
                    buyZoneBadge.className = "px-3 py-0.5 rounded-full text-xs font-bold font-mono bg-amber-500/20 text-amber-300 border border-amber-500/40";
                } else if (sc.buy_zone === 'FAIR / HOLD') {
                    buyZoneBadge.className = "px-3 py-0.5 rounded-full text-xs font-bold font-mono bg-slate-500/20 text-slate-300 border border-slate-500/40";
                } else {
                    buyZoneBadge.className = "px-3 py-0.5 rounded-full text-xs font-bold font-mono bg-rose-500/20 text-rose-300 border border-rose-500/40";
                }
            }
            setTxt('r-buy-zone-desc', sc.buy_zone_description || '');

            // Conviction Meter
            setTxt('r-conviction-score', `${Math.round(bc.conviction_score || 0)}%`);
            setTxt('r-passed-checks', `${bc.passed_checks_count || 0}`);
            const convTierBadge = document.getElementById('r-conviction-tier-badge');
            if (convTierBadge) {
                convTierBadge.textContent = bc.conviction_tier;
                convTierBadge.className = bc.conviction_tier === 'HIGH CONVICTION'
                    ? "text-[10px] font-bold font-mono text-emerald-400 block mt-0.5"
                    : (bc.conviction_tier === 'MODERATE CONVICTION' ? "text-[10px] font-bold font-mono text-amber-400 block mt-0.5" : "text-[10px] font-bold font-mono text-rose-400 block mt-0.5");
            }

            // Multi-Scenario Target Prices
            setTxt('r-bear-price', formatPrice(sc.bear_case_price || 0));
            setTxt('r-downside-risk-badge', `-${(sc.downside_risk_pct || 0).toFixed(1)}% Downside`);
            
            setTxt('r-base-price', formatPrice(sc.base_case_price || 0));
            setTxt('r-base-upside-badge', `+${(sc.upside_potential_pct || 0).toFixed(1)}% Upside`);

            setTxt('r-bull-price', formatPrice(sc.bull_case_price || 0));
            setTxt('r-bull-upside-badge', `+${(sc.bull_upside_pct || 0).toFixed(1)}% Bull`);

            // Position Sizing & Money Management
            setTxt('r-max-alloc', `Maksimal ${Math.round(ps.max_portfolio_allocation_pct || 0)}% Modal`);
            setTxt('r-alloc-rationale', ps.allocation_rationale || '');
            setTxt('r-rr-ratio', `${(sc.risk_to_reward_ratio || 0).toFixed(2)}x R:R`);
            setTxt('r-mos-val', `${(sc.margin_of_safety_pct || 0) >= 0 ? '+' : ''}${(sc.margin_of_safety_pct || 0).toFixed(1)}% MoS`);

            // 10-Point Checklist Table
            const chkTbody = document.getElementById('r-conviction-checklist-tbody');
            if (chkTbody && bc.checklist) {
                chkTbody.innerHTML = bc.checklist.map((chk, idx) => {
                    const passBadge = chk.passed
                        ? `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/40">✓ PASS</span>`
                        : `<span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-bold border border-rose-500/40">✗ FAIL</span>`;
                    return `
                        <tr class="hover:bg-dark-surface/50 transition text-xs">
                            <td class="p-2.5 text-center text-slate-500 font-mono">${idx + 1}</td>
                            <td class="p-2.5 font-bold text-slate-200">${chk.title}</td>
                            <td class="p-2.5 text-slate-400 font-mono text-[11px]">${chk.category}</td>
                            <td class="p-2.5 text-right font-mono text-cyan-300 font-bold">${chk.actual_value_str}</td>
                            <td class="p-2.5 text-center font-mono text-slate-400 text-[11px]">${chk.benchmark_threshold_str}</td>
                            <td class="p-2.5 text-center">${passBadge}</td>
                            <td class="p-2.5 text-slate-300 text-[11px] font-sans">${chk.explanation}</td>
                        </tr>
                    `;
                }).join('');
            }
        }

        // Bull & Bear Cases & Red Flags
        const bullContainer = document.getElementById('r-bull-cases');
        if (bullContainer) {
            bullContainer.innerHTML = (data.bull_cases || []).map(b => `<li>${b}</li>`).join('') || '<li class="text-slate-500">Tidak ada bull case dominan.</li>';
        }

        const bearContainer = document.getElementById('r-bear-cases');
        if (bearContainer) {
            bearContainer.innerHTML = (data.bear_cases || []).map(b => `<li>${b}</li>`).join('') || '<li class="text-slate-500">Tidak ada risiko mayor teridentifikasi.</li>';
        }

        const flagsContainer = document.getElementById('r-red-flags');
        if (flagsContainer) {
            flagsContainer.innerHTML = (data.red_flags || []).map(f => `<li>${f}</li>`).join('') || '<li class="text-slate-500">Tidak ada red flag / risiko neraca aman.</li>';
        }
    }

    if (searchBtn) {
        searchBtn.addEventListener('click', () => {
            if (singleInput) loadSingleEmiten(singleInput.value);
        });
    }

    if (singleInput) {
        singleInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') loadSingleEmiten(singleInput.value);
        });
    }

    if (refreshLiveBtn) {
        refreshLiveBtn.addEventListener('click', () => {
            loadSingleEmiten(currentActiveTicker, null, true);
        });
    }

    if (simPriceBtn) {
        simPriceBtn.addEventListener('click', () => {
            const p = parseFloat(simPriceInput ? simPriceInput.value : 0);
            if (p > 0) loadSingleEmiten(currentActiveTicker, p);
        });
    }

    if (simPriceInput) {
        simPriceInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const p = parseFloat(simPriceInput.value);
                if (p > 0) loadSingleEmiten(currentActiveTicker, p);
            }
        });
    }

    window.simulatePrice = function(targetPriceInIdr) {
        if (simPriceInput) {
            simPriceInput.value = currentCurrency === 'USD' ? (targetPriceInIdr * liveFxRate.idr_to_usd).toFixed(2) : targetPriceInIdr;
        }
        loadSingleEmiten(currentActiveTicker, targetPriceInIdr);
    };

    document.querySelectorAll('.quick-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const t = chip.textContent.trim();
            if (singleInput) singleInput.value = t;
            loadSingleEmiten(t);
        });
    });

    // -------------------------------------------------------------
    // 2.35 Shareholder / Stakeholder Ownership Composition
    // -------------------------------------------------------------
    function renderOwnership(ownership) {
        const section = document.getElementById('ownership-section');
        if (!section) return;

        if (!ownership) {
            section.classList.add('hidden');
            return;
        }
        section.classList.remove('hidden');

        const srcEl = document.getElementById('ownership-source');
        if (srcEl) srcEl.textContent = `Sumber: ${ownership.source || '-'}`;

        const pct = (v) => (v === null || v === undefined || isNaN(v)) ? '-' : `${Number(v).toFixed(2)}%`;
        const stats = ownership.shares_statistics || {};

        const summaryCards = [
            { label: 'Free Float', value: pct(ownership.public_float_pct ?? stats.float_percentage), color: 'text-brand-400' },
            { label: 'Insider / Pengendali', value: pct(ownership.insider_pct ?? stats.percent_insiders), color: 'text-amber-300' },
            { label: 'Institusi', value: pct(ownership.institution_pct ?? stats.percent_institutions), color: 'text-cyan-400' },
            { label: 'Pemerintah', value: pct(ownership.government_pct), color: 'text-purple-300' },
        ];

        const summaryEl = document.getElementById('ownership-summary');
        if (summaryEl) {
            summaryEl.innerHTML = summaryCards.map(c => `
                <div class="bg-dark-bg/80 border border-dark-border rounded-xl p-3">
                    <div class="text-[10px] text-slate-400 uppercase tracking-wide">${c.label}</div>
                    <div class="text-lg font-bold ${c.color} mt-1">${c.value}</div>
                </div>
            `).join('');
        }

        // KSEI SID retail participation
        const sidEl = document.getElementById('ownership-sid');
        if (sidEl) {
            const sid = ownership.sid_statistics;
            if (sid && (sid.total_sid || sid.equity_sid)) {
                const fmt = (n) => (n === null || n === undefined) ? '-' : Number(n).toLocaleString('id-ID');
                sidEl.classList.remove('hidden');
                sidEl.innerHTML = `
                    <span class="text-slate-400">KSEI SID (Investor Terdaftar):</span>
                    <strong class="text-emerald-400">Total ${fmt(sid.total_sid)}</strong>
                    &middot; <strong class="text-emerald-400">Saham ${fmt(sid.equity_sid)}</strong>
                    ${sid.as_of_date ? `<span class="text-slate-500">(per ${sid.as_of_date})</span>` : ''}
                `;
            } else {
                sidEl.classList.add('hidden');
                sidEl.innerHTML = '';
            }
        }

        // Detailed holders (institutions + funds)
        const holdersEl = document.getElementById('ownership-holders');
        if (holdersEl) {
            const holders = []
                .concat(ownership.major_shareholders || [])
                .concat(ownership.institutional_holders || [])
                .concat(ownership.fund_holders || []);

            if (holders.length === 0) {
                holdersEl.innerHTML = '';
            } else {
                const rows = holders.map(h => `
                    <tr>
                        <td class="p-2 text-slate-200">${h.name || '-'}</td>
                        <td class="p-2 text-slate-400">${h.category || '-'}</td>
                        <td class="p-2 text-right font-mono ${h.is_controlling ? 'text-amber-300 font-bold' : 'text-slate-200'}">${pct(h.percentage)}</td>
                    </tr>
                `).join('');
                holdersEl.innerHTML = `
                    <div class="overflow-x-auto border border-dark-border rounded-xl">
                        <table class="w-full text-xs">
                            <thead class="bg-dark-bg/80 text-slate-400">
                                <tr>
                                    <th class="p-2 text-left font-semibold">Pemegang Saham</th>
                                    <th class="p-2 text-left font-semibold">Kategori</th>
                                    <th class="p-2 text-right font-semibold">Kepemilikan</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-dark-border/80">${rows}</tbody>
                        </table>
                    </div>
                `;
            }
        }

        const notesEl = document.getElementById('ownership-notes');
        if (notesEl) {
            notesEl.textContent = (ownership.notes && ownership.notes.length > 0) ? ownership.notes.join(' ') : '';
        }
    }

    // -------------------------------------------------------------
    // 2.4 Stockbit-Grade Multi-Year Quarterly Financial Matrix
    // -------------------------------------------------------------
    function renderStockbitFinancialMatrix(data, mode = 'eps') {
        currentFinancialMatrixTab = mode;
        const tbody = document.getElementById('matrix-tbody');
        const colTitle = document.getElementById('matrix-col-title');
        if (!tbody || !data) return;

        if (colTitle) {
            colTitle.textContent = currentCurrency === 'USD' ? 'Period (USD)' : 'Period (IDR)';
        }

        const matrix = data.financial_matrix;
        const years = (matrix && matrix.years && matrix.years.length > 0) ? matrix.years : [2026, 2025, 2024, 2023, 2022, 2021, 2020];
        
        let targetMatrix = {};
        if (matrix) {
            if (mode === 'eps') targetMatrix = matrix.eps_matrix || {};
            else if (mode === 'revenue') targetMatrix = matrix.revenue_matrix || {};
            else if (mode === 'net_income') targetMatrix = matrix.net_income_matrix || {};
        }

        const formatVal = (val, isPercentage = false) => {
            if (val === null || val === undefined || isNaN(val)) return '-';
            if (isPercentage) return `${Number(val).toFixed(2)}%`;
            if (mode === 'eps') {
                return formatPrice(val, false);
            } else {
                const num = Number(val);
                if (currentCurrency === 'USD') {
                    const usdVal = num * liveFxRate.idr_to_usd;
                    return (usdVal / 1e6).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' M';
                }
                return (num / 1e9).toLocaleString('id-ID', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' B';
            }
        };

        const rowsConfig = [
            { key: 'q1', label: 'Q1', isPct: false, highlight: false },
            { key: 'q2', label: 'Q2', isPct: false, highlight: false },
            { key: 'q3', label: 'Q3', isPct: false, highlight: false },
            { key: 'q4', label: 'Q4', isPct: false, highlight: false },
            { key: 'annualised', label: 'Annualised', isPct: false, highlight: true, style: 'font-bold text-amber-300' },
            { key: 'ttm', label: 'TTM (Q1)', isPct: false, highlight: true, style: 'font-bold text-brand-400' },
            { key: 'dividend_ttm', label: 'Dividend (TTM)', isPct: false, highlight: false, style: 'text-purple-300' },
            { key: 'payout_ratio_pct', label: 'Payout Ratio', isPct: true, highlight: false },
            { key: 'dividend_yield_pct', label: 'Div Yield', isPct: true, highlight: false, style: 'text-emerald-400 font-bold' },
        ];

        tbody.innerHTML = rowsConfig.map(row => {
            const cells = years.map(y => {
                const yearData = targetMatrix[String(y)];
                const val = yearData ? yearData[row.key] : null;
                const formatted = formatVal(val, row.isPct);
                const cellColor = row.style || (formatted !== '-' ? 'text-slate-200' : 'text-slate-500');
                return `<td class="p-3 text-right font-mono ${cellColor}">${formatted}</td>`;
            }).join('');

            const rowBg = row.highlight ? 'bg-dark-surface/40' : 'hover:bg-dark-surface/30';
            const labelColor = row.highlight ? 'text-white font-bold' : 'text-slate-400 font-medium';
            return `
                <tr class="${rowBg} transition">
                    <td class="p-3 ${labelColor}">${row.label}</td>
                    ${cells}
                </tr>
            `;
        }).join('');

        // Populate Right-hand Breakdown Panels
        const setValText = (id, val) => {
            const el = document.getElementById(id);
            if (el && val !== undefined && val !== null) el.textContent = val;
        };

        if (matrix) {
            const isTTM = matrix.income_statement_ttm;
            if (isTTM) {
                setValText('sb-ttm-rev', formatLargeCashFlow(isTTM.revenue_ttm));
                setValText('sb-ttm-gp', formatLargeCashFlow(isTTM.gross_profit_ttm));
                setValText('sb-ttm-ebitda', formatLargeCashFlow(isTTM.ebitda_ttm));
                setValText('sb-ttm-ni', formatLargeCashFlow(isTTM.net_income_ttm));
            }

            const bsQ = matrix.balance_sheet_quarter;
            if (bsQ) {
                setValText('sb-bs-cash', formatLargeCashFlow(bsQ.cash));
                setValText('sb-bs-assets', formatLargeCashFlow(bsQ.total_assets));
                setValText('sb-bs-liab', formatLargeCashFlow(bsQ.total_liabilities));
                setValText('sb-bs-wc', formatLargeCashFlow(bsQ.working_capital));
                setValText('sb-bs-debt', formatLargeCashFlow(bsQ.total_debt));
                setValText('sb-bs-equity', formatLargeCashFlow(bsQ.total_equity));
            }

            const psM = matrix.per_share_metrics;
            if (psM) {
                setValText('sb-ps-eps-ttm', formatPrice(psM.eps_ttm));
                setValText('sb-ps-eps-ann', formatPrice(psM.eps_annualised));
                setValText('sb-ps-rev', formatPrice(psM.revenue_per_share_ttm));
                setValText('sb-ps-cash', formatPrice(psM.cash_per_share));
                setValText('sb-ps-bvps', formatPrice(psM.book_value_per_share));
            }
        }
    }

    // Matrix Tab Click Handlers
    document.querySelectorAll('.matrix-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.matrix-tab-btn').forEach(b => {
                b.classList.remove('bg-brand-600', 'text-white', 'font-bold', 'shadow-sm');
                b.classList.add('text-slate-400');
            });
            btn.classList.add('bg-brand-600', 'text-white', 'font-bold', 'shadow-sm');
            btn.classList.remove('text-slate-400');
            
            const mode = btn.dataset.mode || 'eps';
            if (cachedSingleEmitenData) {
                renderStockbitFinancialMatrix(cachedSingleEmitenData, mode);
            }
        });
    });

    // -------------------------------------------------------------
    // 2.5 TradingView Lightweight Candlestick Chart Engine
    // -------------------------------------------------------------
    async function loadStockChart(ticker, timeframe = '1y') {
        currentChartTimeframe = timeframe;
        const container = document.getElementById('candlestick-chart-container');
        if (!container) return;

        try {
            const resp = await fetch(`/api/v1/chart/${ticker}?timeframe=${timeframe}`);
            if (!resp.ok) return;
            const data = await resp.json();
            cachedChartData = data;
            renderTradingViewChart(data);
            renderTechnicalStatusBar(data);
            renderDetectedSignalsStream(data);
        } catch (err) {
            console.error("Error loading chart data:", err);
        }
    }

    function renderTradingViewChart(data) {
        const container = document.getElementById('candlestick-chart-container');
        if (!container || !data || !data.candles || data.candles.length === 0) return;

        // Cleanup previous chart instance if exists
        if (tvChartInstance) {
            try {
                tvChartInstance.remove();
            } catch (e) {}
            tvChartInstance = null;
        }

        container.innerHTML = '';

        if (typeof LightweightCharts === 'undefined') {
            container.innerHTML = '<div class="flex items-center justify-center h-full text-slate-500 font-mono text-xs">TradingView Charts library sedang dimuat...</div>';
            return;
        }

        const width = container.clientWidth || 800;
        const height = container.clientHeight || 420;

        tvChartInstance = LightweightCharts.createChart(container, {
            width: width,
            height: height,
            layout: {
                background: { color: '#0B0F19' },
                textColor: '#94a3b8',
                fontSize: 11,
                fontFamily: "'JetBrains Mono', monospace"
            },
            grid: {
                vertLines: { color: '#182234' },
                horzLines: { color: '#182234' }
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: { color: '#38bdf8', width: 1, style: LightweightCharts.LineStyle.Dotted, labelBackgroundColor: '#0284c7' },
                horzLine: { color: '#38bdf8', width: 1, style: LightweightCharts.LineStyle.Dotted, labelBackgroundColor: '#0284c7' }
            },
            timeScale: {
                borderColor: '#233044',
                timeVisible: true,
                secondsVisible: false
            },
            rightPriceScale: {
                borderColor: '#233044',
                autoScale: true
            }
        });

        // 1. Candlestick Series
        tvCandleSeries = tvChartInstance.addCandlestickSeries({
            upColor: '#10b981',
            downColor: '#f43f5e',
            borderUpColor: '#10b981',
            borderDownColor: '#f43f5e',
            wickUpColor: '#10b981',
            wickDownColor: '#f43f5e'
        });

        const candlePoints = data.candles.map(c => ({
            time: c.time,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close
        }));
        tvCandleSeries.setData(candlePoints);

        // 2. Volume Histogram Series
        tvVolumeSeries = tvChartInstance.addHistogramSeries({
            priceFormat: { type: 'volume' },
            priceScaleId: '', // overlay
            scaleMargins: {
                top: 0.82,
                bottom: 0
            }
        });

        const volumePoints = data.candles.map(c => ({
            time: c.time,
            value: c.volume,
            color: c.close >= c.open ? 'rgba(16, 185, 129, 0.4)' : 'rgba(244, 63, 94, 0.4)'
        }));
        tvVolumeSeries.setData(volumePoints);

        // 3. Moving Average Series (EMA 20 & SMA 50)
        if (showMaOverlays) {
            const closes = data.candles.map(c => ({ time: c.time, close: c.close }));
            
            // Calculate EMA 20
            if (closes.length >= 20) {
                const ema20Points = [];
                const k = 2.0 / 21.0;
                let ema = closes[0].close;
                for (let i = 0; i < closes.length; i++) {
                    ema = closes[i].close * k + ema * (1 - k);
                    if (i >= 19) {
                        ema20Points.push({ time: closes[i].time, value: ema });
                    }
                }
                tvEma20Series = tvChartInstance.addLineSeries({
                    color: '#06b6d4',
                    lineWidth: 1.5,
                    title: 'EMA 20',
                    priceLineVisible: false
                });
                tvEma20Series.setData(ema20Points);
            }

            // Calculate SMA 50
            if (closes.length >= 50) {
                const sma50Points = [];
                for (let i = 49; i < closes.length; i++) {
                    const sum50 = closes.slice(i - 49, i + 1).reduce((acc, v) => acc + v.close, 0);
                    sma50Points.push({ time: closes[i].time, value: sum50 / 50.0 });
                }
                tvSma50Series = tvChartInstance.addLineSeries({
                    color: '#f59e0b',
                    lineWidth: 1.5,
                    title: 'SMA 50',
                    priceLineVisible: false
                });
                tvSma50Series.setData(sma50Points);
            }
        }

        // 4. Fundamental Price Overlays (Target TP1, TP2, Stop Loss, Buy Zone)
        if (showFundOverlays && data.fundamental_overlays) {
            const fo = data.fundamental_overlays;
            
            // TP1: Fair Value Consensus
            tvCandleSeries.createPriceLine({
                price: fo.fair_value_tp1,
                color: '#06b6d4',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: '⚖️ TP1 Fair Value'
            });

            // TP2: Bull Target
            tvCandleSeries.createPriceLine({
                price: fo.bull_target_tp2,
                color: '#a855f7',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: '🐂 TP2 Bull Target'
            });

            // Bear Floor / Stop Loss
            tvCandleSeries.createPriceLine({
                price: fo.bear_floor_sl,
                color: '#f43f5e',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: '🐻 Bear Floor SL'
            });

            // Strong Accumulation Buy Area
            tvCandleSeries.createPriceLine({
                price: fo.accumulation_zone_top,
                color: '#10b981',
                lineWidth: 1.5,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: true,
                title: '🟢 Buy Accum Area'
            });
        }

        // 5. Detected Technical Signal Markers (Breakout, Gap, RSI, etc.)
        if (data.signals && data.signals.length > 0) {
            const markers = data.signals.map(s => ({
                time: s.date,
                position: s.position === 'aboveBar' ? 'aboveBar' : 'belowBar',
                color: s.color || '#10b981',
                shape: s.shape === 'arrowDown' ? 'arrowDown' : (s.shape === 'circle' ? 'circle' : 'arrowUp'),
                text: s.title
            }));
            tvCandleSeries.setMarkers(markers);
        }

        // 6. Interactive Crosshair Hover Tooltip
        tvChartInstance.subscribeCrosshairMove(param => {
            const legTime = document.getElementById('leg-time');
            const legOpen = document.getElementById('leg-open');
            const legHigh = document.getElementById('leg-high');
            const legLow = document.getElementById('leg-low');
            const legClose = document.getElementById('leg-close');
            const legVol = document.getElementById('leg-vol');

            if (!param || !param.time || !param.seriesData) {
                if (data.candles.length > 0) {
                    const last = data.candles[data.candles.length - 1];
                    if (legTime) legTime.textContent = last.time;
                    if (legOpen) legOpen.textContent = formatPrice(last.open, false);
                    if (legHigh) legHigh.textContent = formatPrice(last.high, false);
                    if (legLow) legLow.textContent = formatPrice(last.low, false);
                    if (legClose) legClose.textContent = formatPrice(last.close, false);
                    if (legVol) legVol.textContent = (last.volume / 1e6).toFixed(1) + 'M';
                }
                return;
            }

            const candleData = param.seriesData.get(tvCandleSeries);
            const volData = param.seriesData.get(tvVolumeSeries);

            if (candleData) {
                if (legTime) legTime.textContent = param.time;
                if (legOpen) legOpen.textContent = formatPrice(candleData.open, false);
                if (legHigh) legHigh.textContent = formatPrice(candleData.high, false);
                if (legLow) legLow.textContent = formatPrice(candleData.low, false);
                if (legClose) legClose.textContent = formatPrice(candleData.close, false);
            }
            if (volData && legVol) {
                legVol.textContent = (volData.value / 1e6).toFixed(1) + 'M';
            }
        });

        // Set initial legend state
        const legTicker = document.getElementById('leg-ticker');
        if (legTicker) legTicker.textContent = `${data.ticker}.JK`;
        if (data.candles.length > 0) {
            const last = data.candles[data.candles.length - 1];
            const legTime = document.getElementById('leg-time');
            const legOpen = document.getElementById('leg-open');
            const legHigh = document.getElementById('leg-high');
            const legLow = document.getElementById('leg-low');
            const legClose = document.getElementById('leg-close');
            const legVol = document.getElementById('leg-vol');
            if (legTime) legTime.textContent = last.time;
            if (legOpen) legOpen.textContent = formatPrice(last.open, false);
            if (legHigh) legHigh.textContent = formatPrice(last.high, false);
            if (legLow) legLow.textContent = formatPrice(last.low, false);
            if (legClose) legClose.textContent = formatPrice(last.close, false);
            if (legVol) legVol.textContent = (last.volume / 1e6).toFixed(1) + 'M';
        }

        // Responsive resize using ResizeObserver & window resize
        if (window.ResizeObserver && container) {
            const ro = new ResizeObserver(entries => {
                for (const entry of entries) {
                    const cr = entry.contentRect;
                    if (tvChartInstance && cr.width > 0) {
                        tvChartInstance.applyOptions({
                            width: cr.width
                        });
                    }
                }
            });
            ro.observe(container);
        } else {
            window.addEventListener('resize', () => {
                if (tvChartInstance && container) {
                    tvChartInstance.applyOptions({
                        width: container.clientWidth
                    });
                }
            });
        }
    }

    function renderTechnicalStatusBar(data) {
        if (!data || !data.indicators) return;
        const ind = data.indicators;
        const setTxt = (id, val) => {
            const el = document.getElementById(id);
            if (el && val !== undefined) el.textContent = val;
        };

        setTxt('t-trend-summary', ind.trend_summary);
        setTxt('t-rsi-val', ind.rsi_14 !== null ? `${ind.rsi_14} (${ind.momentum_summary.split(' ')[0]})` : '-');
        
        const emaStr = ind.ema_20 ? formatPrice(ind.ema_20, false) : '-';
        const smaStr = ind.sma_50 ? formatPrice(ind.sma_50, false) : '-';
        setTxt('t-ma-val', `Rp ${emaStr} / ${smaStr}`);

        // Support & Resistance
        const supports = (data.support_resistance || []).filter(s => s.kind === 'SUPPORT');
        const resists = (data.support_resistance || []).filter(s => s.kind === 'RESISTANCE');
        
        const nearestSupp = supports.length > 0 ? supports[supports.length - 1].price : (data.current_price * 0.95);
        const nearestRes = resists.length > 0 ? resists[0].price : (data.current_price * 1.05);

        setTxt('t-support-val', formatPrice(nearestSupp));
        setTxt('t-resist-val', formatPrice(nearestRes));
        setTxt('t-signals-count', `${(data.signals || []).length} Sinyal Pola`);
    }

    function renderDetectedSignalsStream(data) {
        const streamList = document.getElementById('signals-stream-list');
        if (!streamList) return;

        const signals = data.signals || [];
        if (signals.length === 0) {
            streamList.innerHTML = `<div class="col-span-full py-2 text-center text-slate-500 text-xs font-mono">Belum ada sinyal teknikal ekstrim pada periode ini.</div>`;
            return;
        }

        streamList.innerHTML = signals.slice(-6).reverse().map(s => {
            const isBullish = s.signal_type.includes('BUY') || s.signal_type.includes('UP') || s.signal_type.includes('GOLDEN') || s.signal_type.includes('OVERSOLD');
            const borderCol = isBullish ? 'border-emerald-500/30 bg-emerald-950/20' : 'border-rose-500/30 bg-rose-950/20';
            const textCol = isBullish ? 'text-emerald-400' : 'text-rose-400';
            
            return `
                <div class="p-3 rounded-xl border ${borderCol} space-y-1 text-xs">
                    <div class="flex items-center justify-between">
                        <span class="font-bold ${textCol} font-mono">${s.title}</span>
                        <span class="text-[10px] text-slate-400 font-mono">${s.date}</span>
                    </div>
                    <p class="text-[11px] text-slate-300 font-sans leading-snug">${s.description}</p>
                </div>
            `;
        }).join('');
    }

    // Timeframe selector button listeners
    document.querySelectorAll('.tf-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.tf-btn').forEach(b => {
                b.className = 'tf-btn px-2.5 py-1 rounded-md text-slate-400 hover:text-white transition text-xs';
            });
            this.className = 'tf-btn px-2.5 py-1 rounded-md bg-brand-600 text-white font-bold transition text-xs';
            const tf = this.dataset.tf;
            loadStockChart(currentActiveTicker, tf);
        });
    });

    // Toggle Moving Averages overlay
    const toggleMaBtn = document.getElementById('toggle-ma-btn');
    if (toggleMaBtn) {
        toggleMaBtn.addEventListener('click', () => {
            showMaOverlays = !showMaOverlays;
            toggleMaBtn.className = showMaOverlays
                ? "px-2.5 py-1.5 rounded-lg bg-dark-bg hover:bg-dark-surface border border-dark-border text-slate-300 text-xs font-mono flex items-center gap-1.5 transition"
                : "px-2.5 py-1.5 rounded-lg bg-dark-bg/40 opacity-50 border border-dark-border text-slate-500 text-xs font-mono flex items-center gap-1.5 transition";
            if (cachedChartData) renderTradingViewChart(cachedChartData);
        });
    }

    // Toggle Fundamental Target overlay
    const toggleFundBtn = document.getElementById('toggle-fund-btn');
    if (toggleFundBtn) {
        toggleFundBtn.addEventListener('click', () => {
            showFundOverlays = !showFundOverlays;
            toggleFundBtn.className = showFundOverlays
                ? "px-2.5 py-1.5 rounded-lg bg-brand-500/20 hover:bg-brand-500/30 border border-brand-500/40 text-brand-300 text-xs font-mono flex items-center gap-1.5 transition"
                : "px-2.5 py-1.5 rounded-lg bg-dark-bg/40 opacity-50 border border-dark-border text-slate-500 text-xs font-mono flex items-center gap-1.5 transition";
            if (cachedChartData) renderTradingViewChart(cachedChartData);
        });
    }

    // -------------------------------------------------------------
    // 3. Peer Comparison Logic
    // -------------------------------------------------------------
    const compareInput = document.getElementById('compare-input');
    const compareRunBtn = document.getElementById('compare-run-btn');

    async function runComparison(customTickers) {
        const raw = customTickers || (compareInput ? compareInput.value : 'BBCA,BBRI,BMRI,BBNI');
        const tickers = raw.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
        if (!tickers.length) return;

        try {
            const resp = await fetch('/api/v1/compare', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tickers })
            });
            if (!resp.ok) return;
            const data = await resp.json();
            cachedComparisonData = data;
            renderComparison(data);
        } catch (err) {
            console.error('Error running comparison:', err);
        }
    }

    function renderComparison(data) {
        if (!data) return;

        // Champions cards
        const champContainer = document.getElementById('compare-champions-container');
        if (champContainer && data.best_in_class) {
            const labels = {
                'cheapest_pe': { name: 'Cheapest P/E', icon: '💰' },
                'cheapest_pbv': { name: 'Cheapest P/B', icon: '🏷️' },
                'highest_roe': { name: 'Highest ROE', icon: '🚀' },
                'highest_dividend_yield': { name: 'Top Dividend', icon: '💵' },
                'highest_piotroski_f': { name: 'Top Quality F', icon: '⭐' },
                'overall_champion': { name: 'Overall Leader', icon: '🏆' }
            };

            champContainer.innerHTML = Object.keys(data.best_in_class).map(key => {
                const info = labels[key] || { name: key, icon: '✨' };
                const ticker = data.best_in_class[key];
                return `
                    <div class="bg-dark-card border border-dark-border p-3 rounded-xl shadow text-center">
                        <div class="text-xs text-slate-400 flex items-center justify-center gap-1">${info.icon} ${info.name}</div>
                        <div class="text-lg font-mono font-extrabold text-white mt-1">${ticker}</div>
                    </div>
                `;
            }).join('');
        }

        // Table Rows
        const tbody = document.getElementById('compare-tbody');
        if (tbody && data.items) {
            tbody.innerHTML = data.items.map(item => {
                const isWinner = data.best_in_class && data.best_in_class['overall_champion'] === item.ticker;
                const scoreClass = isWinner ? 'bg-brand-500/20 text-brand-300 font-bold border border-brand-500/30' : 'text-slate-200';
                const gradeClass = ['A+', 'A'].includes(item.grade) ? 'text-brand-400 font-bold' : 'text-amber-400 font-bold';

                return `
                    <tr class="hover:bg-dark-surface/40 transition">
                        <td class="p-3.5 font-bold text-white flex items-center gap-1.5 font-mono">
                            <span class="px-2 py-0.5 rounded bg-brand-600/20 border border-brand-500/30 text-brand-300">${item.ticker}</span>
                            ${isWinner ? '👑' : ''}
                        </td>
                        <td class="p-3.5 text-right font-mono">${formatPrice(item.current_price)}</td>
                        <td class="p-3.5 text-right font-mono">${item.per}x</td>
                        <td class="p-3.5 text-right font-mono">${item.pbv}x</td>
                        <td class="p-3.5 text-right font-mono text-brand-400">${item.roe}%</td>
                        <td class="p-3.5 text-right font-mono">${item.der}x</td>
                        <td class="p-3.5 text-center font-mono">${item.piotroski_f_score}/9</td>
                        <td class="p-3.5 text-right font-mono">${item.altman_z_score}</td>
                        <td class="p-3.5 text-right font-mono text-purple-400">${item.dividend_yield}%</td>
                        <td class="p-3.5 text-right font-mono ${item.upside_pct > 0 ? 'text-brand-400' : 'text-rose-400'}">${item.upside_pct > 0 ? '+' : ''}${item.upside_pct}%</td>
                        <td class="p-3.5 text-center"><span class="px-2 py-0.5 rounded ${scoreClass}">${item.composite_score}</span></td>
                        <td class="p-3.5 text-center ${gradeClass}">${item.grade}</td>
                        <td class="p-3.5 text-center"><span class="px-2 py-0.5 text-[10px] rounded bg-dark-surface border border-dark-border text-slate-300">${item.verdict}</span></td>
                    </tr>
                `;
            }).join('');
        }
    }

    if (compareRunBtn) {
        compareRunBtn.addEventListener('click', () => runComparison());
    }

    document.querySelectorAll('.compare-preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (compareInput) compareInput.value = btn.dataset.tickers;
            runComparison(btn.dataset.tickers);
        });
    });

    // -------------------------------------------------------------
    // 4. Screener Logic
    // -------------------------------------------------------------
    async function runScreener(presetName, customCriteria = {}) {
        const payload = {
            preset: presetName || 'BUFFETT_MOAT',
            ...customCriteria
        };

        try {
            const resp = await fetch('/api/v1/screener/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!resp.ok) return;
            const data = await resp.json();
            cachedScreenerData = data;
            currentScreenerResults = data.results || [];
            renderScreener(data);
        } catch (err) {
            console.error('Error running screener:', err);
        }
    }

    function renderScreener(data) {
        if (!data) return;

        const countBadge = document.getElementById('screener-count-badge');
        if (countBadge) {
            const presetLabel = data.applied_preset || 'CUSTOM';
            countBadge.textContent = `Menampilkan ${data.total_matched} Emiten Terpilih (${presetLabel})`;
        }

        const tbody = document.getElementById('screener-tbody');
        if (tbody && data.results) {
            if (data.results.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="15" class="p-8 text-center text-slate-400">
                            <div class="text-2xl mb-2">🔍</div>
                            <div class="font-bold text-sm text-slate-300">Tidak ada emiten yang cocok dengan kriteria filter harga/fundamental ini.</div>
                            <div class="text-xs text-slate-500 mt-1">Coba perlebar rentang harga atau kurangi kriteria filter kustom.</div>
                        </td>
                    </tr>
                `;
                return;
            }

            tbody.innerHTML = data.results.map((item, idx) => {
                const gradeClass = ['A+', 'A'].includes(item.grade) ? 'text-brand-400 font-bold' : (item.grade === 'B' ? 'text-amber-400 font-bold' : 'text-rose-400 font-bold');
                const scoreClass = item.composite_score >= 75 ? 'text-brand-400 font-bold' : (item.composite_score >= 60 ? 'text-amber-300 font-bold' : 'text-slate-300');
                const upsideClass = item.upside_pct > 0 ? 'text-emerald-400 font-bold' : 'text-rose-400';
                const upsideSign = item.upside_pct > 0 ? '+' : '';

                let verdictBg = 'bg-dark-surface border-dark-border text-slate-300';
                if (item.verdict === 'STRONG BUY') verdictBg = 'bg-emerald-900/60 border-emerald-500 text-emerald-300 font-bold';
                else if (item.verdict === 'BUY') verdictBg = 'bg-emerald-950/40 border-emerald-700 text-emerald-400 font-semibold';
                else if (item.verdict === 'HOLD') verdictBg = 'bg-amber-950/40 border-amber-700 text-amber-300';
                else if (item.verdict === 'AVOID') verdictBg = 'bg-rose-950/40 border-rose-700 text-rose-300';

                return `
                    <tr class="hover:bg-dark-surface/40 transition">
                        <td class="p-3.5 text-slate-500">${idx + 1}</td>
                        <td class="p-3.5 font-bold text-brand-300 font-mono">
                            <button class="hover:underline" onclick="switchSingle('${item.ticker}')">${item.ticker}</button>
                        </td>
                        <td class="p-3.5 text-slate-300 truncate max-w-[180px]">${item.name}</td>
                        <td class="p-3.5 text-slate-400">${item.sector}</td>
                        <td class="p-3.5 text-right font-mono font-bold text-white">${formatPrice(item.current_price)}</td>
                        <td class="p-3.5 text-right font-mono ${upsideClass}">${upsideSign}${item.upside_pct.toFixed(1)}%</td>
                        <td class="p-3.5 text-right font-mono">${item.per}x</td>
                        <td class="p-3.5 text-right font-mono">${item.pbv}x</td>
                        <td class="p-3.5 text-right font-mono text-brand-400">${item.roe}%</td>
                        <td class="p-3.5 text-right font-mono">${item.der}x</td>
                        <td class="p-3.5 text-center font-mono">${item.piotroski_f_score}/9</td>
                        <td class="p-3.5 text-right font-mono text-purple-400">${item.dividend_yield}%</td>
                        <td class="p-3.5 text-center font-mono ${scoreClass}">${item.composite_score}</td>
                        <td class="p-3.5 text-center ${gradeClass}">${item.grade}</td>
                        <td class="p-3.5 text-center"><span class="px-2 py-0.5 text-[10px] rounded border ${verdictBg}">${item.verdict}</span></td>
                    </tr>
                `;
            }).join('');
        }
    }

    // -------------------------------------------------------------
    // 5. Market Summary & Daily Top Picks Logic
    // -------------------------------------------------------------
    async function loadMarketSummary(retryCount = 0) {
        const topPicksContainer = document.getElementById('top-picks-container');
        const tbody = document.getElementById('market-tbody');
        
        try {
            const resp = await fetch('/api/v1/market/summary');
            if (!resp.ok) {
                throw new Error(`HTTP status ${resp.status}`);
            }
            const data = await resp.json();
            currentMarketData = data;
            allMarketEmitens = data.emitens || [];

            renderMarketOverview(data);
        } catch (err) {
            console.error('Error fetching market summary:', err);
            // Auto retry if server is waking up
            if (retryCount < 3) {
                console.log(`Retrying market summary in 2s (attempt ${retryCount + 1})...`);
                setTimeout(() => loadMarketSummary(retryCount + 1), 2000);
                return;
            }

            if (topPicksContainer) {
                topPicksContainer.innerHTML = `
                    <div class="col-span-full bg-dark-card border border-brand-500/30 rounded-2xl p-6 text-center space-y-3">
                        <div class="text-brand-400 text-sm font-bold">⚡ Menghubungkan ke Server Fundamental...</div>
                        <p class="text-xs text-slate-400">Server sedang menyiapkan kalkulasi IDX. Klik tombol di bawah untuk memuat data.</p>
                        <button onclick="loadMarketSummary(0)" class="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-xl text-xs font-bold transition shadow-md inline-flex items-center gap-2">
                            <span>🔄 Muat Ulang Rekomendasi</span>
                        </button>
                    </div>
                `;
            }
            if (tbody) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="13" class="p-6 text-center text-slate-400 font-mono text-xs">
                            Server sedang memproses. Klik tombol "Update Rekomendasi" di atas untuk memuat ulang.
                        </td>
                    </tr>
                `;
            }
        }
    }
    window.loadMarketSummary = loadMarketSummary;

    function renderMarketOverview(data) {
        if (!data) return;

        // Date and Stats
        const dateEl = document.getElementById('market-generated-date');
        if (dateEl && data.generated_at_desc) {
            dateEl.textContent = data.generated_at_desc;
        }

        const stats = data.stats;
        if (stats) {
            const elTotal = document.getElementById('m-stat-total');
            const elUnder = document.getElementById('m-stat-undervalued');
            const elOver = document.getElementById('m-stat-overvalued');
            const elScore = document.getElementById('m-stat-avg-score');
            const elRoe = document.getElementById('m-stat-avg-roe');
            const elDiv = document.getElementById('m-stat-avg-div');

            if (elTotal) elTotal.textContent = stats.total_emitens;
            if (elUnder) elUnder.textContent = stats.undervalued_count;
            if (elOver) elOver.textContent = stats.overvalued_count;
            if (elScore) elScore.textContent = stats.avg_composite_score;
            if (elRoe) elRoe.textContent = `${stats.avg_roe}%`;
            if (elDiv) elDiv.textContent = `${stats.avg_dividend_yield}%`;
        }

        // Render Top Picks Cards
        const topPicksContainer = document.getElementById('top-picks-container');
        if (topPicksContainer && data.top_picks) {
            const colorMap = {
                emerald: {
                    border: 'border-brand-500/30 hover:border-brand-400',
                    bgGlow: 'bg-emerald-950/15',
                    tagBg: 'bg-brand-500/15 text-brand-400 border-brand-500/30',
                    btnBg: 'bg-brand-600 hover:bg-brand-500 text-white shadow-lg shadow-brand-600/20',
                    textAcc: 'text-brand-400'
                },
                cyan: {
                    border: 'border-cyan-500/30 hover:border-cyan-400',
                    bgGlow: 'bg-cyan-950/15',
                    tagBg: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
                    btnBg: 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg shadow-cyan-600/20',
                    textAcc: 'text-cyan-400'
                },
                indigo: {
                    border: 'border-indigo-500/30 hover:border-indigo-400',
                    bgGlow: 'bg-indigo-950/15',
                    tagBg: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30',
                    btnBg: 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20',
                    textAcc: 'text-indigo-400'
                },
                amber: {
                    border: 'border-amber-500/30 hover:border-amber-400',
                    bgGlow: 'bg-amber-950/15',
                    tagBg: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
                    btnBg: 'bg-amber-600 hover:bg-amber-500 text-white shadow-lg shadow-amber-600/20',
                    textAcc: 'text-amber-400'
                }
            };

            topPicksContainer.innerHTML = data.top_picks.map(pick => {
                const c = colorMap[pick.badge_color] || colorMap.emerald;
                const upsideSign = pick.upside_pct >= 0 ? '+' : '';
                const upsideColor = pick.upside_pct >= 0 ? 'text-brand-400' : 'text-rose-400';

                return `
                    <div class="top-pick-card bg-dark-card border ${c.border} rounded-2xl p-4 sm:p-5 shadow-lg flex flex-col justify-between relative overflow-hidden ${c.bgGlow}">
                        <div class="space-y-3.5">
                            <!-- Category Badge -->
                            <div class="flex items-center justify-between gap-2">
                                <span class="px-2.5 py-0.5 text-[10px] font-mono font-bold rounded-full border ${c.tagBg}">
                                    ${pick.category_tag}
                                </span>
                                <span class="px-2 py-0.5 text-xs font-mono font-bold rounded-lg bg-dark-bg border border-dark-border ${pick.grade.startsWith('A') ? 'text-brand-400' : 'text-amber-400'}">
                                    Grade ${pick.grade} (${pick.composite_score})
                                </span>
                            </div>

                            <!-- Ticker & Company Name -->
                            <div>
                                <div class="flex items-center gap-2">
                                    <span class="text-2xl font-extrabold text-white tracking-tight font-mono">${pick.ticker}</span>
                                    <span class="text-xs text-slate-400 truncate max-w-[170px]">${pick.name}</span>
                                </div>
                                <span class="text-[11px] text-slate-500 font-mono">${pick.sector}</span>
                            </div>

                            <!-- Price vs Fair Value & Upside -->
                            <div class="p-3 bg-dark-bg/90 border border-dark-border rounded-xl font-mono text-xs space-y-1.5">
                                <div class="flex items-center justify-between text-slate-400">
                                    <span>Harga Pasar:</span>
                                    <span class="text-slate-100 font-bold">${formatPrice(pick.current_price)}</span>
                                </div>
                                <div class="flex items-center justify-between text-slate-400">
                                    <span>Nilai Wajar:</span>
                                    <span class="${c.textAcc} font-bold">${formatPrice(pick.fair_value)}</span>
                                </div>
                                <div class="flex items-center justify-between border-t border-dark-border pt-1">
                                    <span class="text-slate-300 font-sans font-medium text-[11px]">Potensi Upside:</span>
                                    <span class="${upsideColor} font-bold text-sm">${upsideSign}${pick.upside_pct.toFixed(1)}%</span>
                                </div>
                            </div>

                            <!-- Key Metrics Pills -->
                            <div class="flex flex-wrap gap-1.5 text-[10px] font-mono">
                                ${pick.key_metrics_summary.map(m => `
                                    <span class="px-2 py-0.5 rounded bg-dark-surface border border-dark-border text-slate-300">${m}</span>
                                `).join('')}
                            </div>

                            <!-- Catalyst Paragraph -->
                            <div class="text-xs text-slate-300 leading-relaxed bg-dark-bg/60 p-2.5 rounded-lg border border-dark-border/70">
                                <span class="text-slate-400 font-medium block text-[10px] uppercase font-mono mb-1">💡 Katalis Esok Hari:</span>
                                ${pick.catalyst}
                            </div>
                        </div>

                        <!-- Action Button -->
                        <div class="mt-4 pt-3 border-t border-dark-border">
                            <button onclick="switchSingle('${pick.ticker}')" class="w-full py-2.5 px-4 rounded-xl ${c.btnBg} font-bold text-xs transition-all flex items-center justify-center gap-2">
                                <span>🔍 Lihat Detail Analisis ${pick.ticker}</span>
                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
        }

        // Populate Sector Filter Options
        const sectorSelect = document.getElementById('market-sector-filter');
        if (sectorSelect && sectorSelect.options.length <= 1) {
            const sectors = Array.from(new Set(allMarketEmitens.map(e => e.sector))).filter(Boolean).sort();
            sectorSelect.innerHTML = '<option value="ALL">Semua Sektor</option>' + 
                sectors.map(s => `<option value="${s}">${s}</option>`).join('');
        }

        // Render Table
        renderMarketTable();
    }

    function renderMarketTable() {
        const tbody = document.getElementById('market-tbody');
        if (!tbody) return;

        const searchQuery = (document.getElementById('market-search-input')?.value || '').trim().toUpperCase();
        const selectedSector = document.getElementById('market-sector-filter')?.value || 'ALL';
        const sortMode = document.getElementById('market-sort-select')?.value || 'score';

        let filtered = allMarketEmitens.filter(it => {
            const matchSearch = !searchQuery || it.ticker.includes(searchQuery) || it.name.toUpperCase().includes(searchQuery);
            const matchSector = selectedSector === 'ALL' || it.sector === selectedSector;
            return matchSearch && matchSector;
        });

        // Sorting
        filtered.sort((a, b) => {
            if (sortMode === 'score') return b.composite_score - a.composite_score;
            if (sortMode === 'upside') return b.upside_pct - a.upside_pct;
            if (sortMode === 'roe') return b.roe - a.roe;
            if (sortMode === 'dividend') return b.dividend_yield - a.dividend_yield;
            if (sortMode === 'pe') return (a.per || 999) - (b.per || 999);
            return 0;
        });

        if (filtered.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="13" class="p-6 text-center text-slate-500 font-mono">
                        Tidak ada emiten yang sesuai dengan kriteria pencarian.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = filtered.map((item, idx) => {
            const gradeClass = ['A+', 'A'].includes(item.grade) ? 'text-brand-400 font-bold' : 'text-amber-400 font-bold';
            const scoreClass = item.composite_score >= 75 ? 'text-brand-400 font-bold' : 'text-slate-200';
            const upsideClass = item.upside_pct >= 0 ? 'text-brand-400 font-bold' : 'text-rose-400';
            const upsideSign = item.upside_pct >= 0 ? '+' : '';

            return `
                <tr class="hover:bg-dark-surface/40 transition">
                    <td class="p-3.5 text-slate-500">${idx + 1}</td>
                    <td class="p-3.5">
                        <div class="flex items-center gap-2">
                            <button onclick="switchSingle('${item.ticker}')" class="font-bold text-brand-300 hover:text-brand-200 hover:underline font-mono text-sm">
                                ${item.ticker}
                            </button>
                            <span class="text-slate-300 truncate max-w-[150px] hidden sm:inline">${item.name}</span>
                        </div>
                    </td>
                    <td class="p-3.5 text-slate-400">${item.sector}</td>
                    <td class="p-3.5 text-right font-mono">${formatPrice(item.current_price)}</td>
                    <td class="p-3.5 text-right font-mono">${item.per}x</td>
                    <td class="p-3.5 text-right font-mono">${item.pbv}x</td>
                    <td class="p-3.5 text-right font-mono text-brand-400">${item.roe}%</td>
                    <td class="p-3.5 text-right font-mono ${upsideClass}">${upsideSign}${item.upside_pct ? item.upside_pct.toFixed(1) : '0.0'}%</td>
                    <td class="p-3.5 text-center font-mono">${item.piotroski_f_score}/9</td>
                    <td class="p-3.5 text-right font-mono text-amber-400">${item.dividend_yield}%</td>
                    <td class="p-3.5 text-center font-mono ${scoreClass}">${item.composite_score}</td>
                    <td class="p-3.5 text-center ${gradeClass}">${item.grade}</td>
                    <td class="p-3.5 text-center">
                        <button onclick="switchSingle('${item.ticker}')" class="px-2.5 py-1 rounded-lg bg-brand-600/20 hover:bg-brand-600 text-brand-300 hover:text-white border border-brand-500/30 text-xs font-sans transition">
                            Analisis ➔
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    window.switchSingle = function(ticker) {
        if (!ticker) return;
        ticker = ticker.trim().toUpperCase();
        
        const singleTab = document.getElementById('tab-single');
        if (singleTab) {
            singleTab.click();
        }
        
        if (singleInput) {
            singleInput.value = ticker;
        }
        loadSingleEmiten(ticker);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    // Market filters & Search listeners
    const marketSearch = document.getElementById('market-search-input');
    if (marketSearch) marketSearch.addEventListener('input', renderMarketTable);

    const marketSectorFilter = document.getElementById('market-sector-filter');
    if (marketSectorFilter) marketSectorFilter.addEventListener('change', renderMarketTable);

    const marketSortSelect = document.getElementById('market-sort-select');
    if (marketSortSelect) marketSortSelect.addEventListener('change', renderMarketTable);

    const refreshMarketBtn = document.getElementById('refresh-market-btn');
    if (refreshMarketBtn) refreshMarketBtn.addEventListener('click', () => loadMarketSummary(0));

    // -------------------------------------------------------------
    // Screener Preset & Quick Price Buttons
    // -------------------------------------------------------------
    let currentScreenerPreset = 'BUFFETT_MOAT';

    function getCustomCriteriaPayload() {
        return {
            min_price: parseFloat(document.getElementById('f-min-price')?.value) || null,
            max_price: parseFloat(document.getElementById('f-max-price')?.value) || null,
            min_roe: parseFloat(document.getElementById('f-min-roe')?.value) || null,
            max_der: parseFloat(document.getElementById('f-max-der')?.value) || null,
            min_piotroski_f: parseInt(document.getElementById('f-min-pio')?.value) || null,
            min_dividend_yield: parseFloat(document.getElementById('f-min-div')?.value) || null,
            max_pe: parseFloat(document.getElementById('f-max-pe')?.value) || null,
            min_composite_score: parseFloat(document.getElementById('f-min-score')?.value) || null,
            only_buy_recommendations: document.getElementById('f-buy-only')?.checked || false,
            only_undervalued: document.getElementById('f-undervalued-only')?.checked || false,
            sort_by: document.getElementById('f-sort-by')?.value || 'composite_score'
        };
    }

    document.querySelectorAll('.screener-preset-card').forEach(card => {
        card.addEventListener('click', () => {
            document.querySelectorAll('.screener-preset-card').forEach(c => {
                c.classList.remove('bg-brand-600/10', 'border-brand-500', 'text-white', 'shadow-lg');
                c.classList.add('bg-dark-card', 'border-dark-border', 'text-slate-300');
            });
            card.classList.add('bg-brand-600/10', 'border-brand-500', 'text-white', 'shadow-lg');
            card.classList.remove('bg-dark-card', 'border-dark-border', 'text-slate-300');

            currentScreenerPreset = card.dataset.preset;
            const sortVal = document.getElementById('f-sort-by')?.value || 'composite_score';
            runScreener(currentScreenerPreset, { sort_by: sortVal });
        });
    });

    // Quick Price Filter Buttons
    document.querySelectorAll('.quick-price-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.quick-price-btn').forEach(b => {
                b.classList.remove('active', 'bg-brand-600', 'text-white', 'border-brand-500', 'shadow-sm');
                b.classList.add('bg-dark-surface', 'text-slate-300', 'border-dark-border');
            });
            btn.classList.add('active', 'bg-brand-600', 'text-white', 'border-brand-500', 'shadow-sm');
            btn.classList.remove('bg-dark-surface', 'text-slate-300', 'border-dark-border');

            const priceType = btn.dataset.price;
            const criteria = {
                sort_by: document.getElementById('f-sort-by')?.value || 'composite_score'
            };

            const minPriceInput = document.getElementById('f-min-price');
            const maxPriceInput = document.getElementById('f-max-price');
            const buyOnlyCheck = document.getElementById('f-buy-only');

            if (priceType === 'budget') {
                criteria.max_price = 1000.0;
                if (minPriceInput) minPriceInput.value = '';
                if (maxPriceInput) maxPriceInput.value = '1000';
            } else if (priceType === 'mid') {
                criteria.min_price = 1000.0;
                criteria.max_price = 5000.0;
                if (minPriceInput) minPriceInput.value = '1000';
                if (maxPriceInput) maxPriceInput.value = '5000';
            } else if (priceType === 'premium') {
                criteria.min_price = 5000.0;
                if (minPriceInput) minPriceInput.value = '5000';
                if (maxPriceInput) maxPriceInput.value = '';
            } else if (priceType === 'buy_only') {
                criteria.only_buy_recommendations = true;
                if (buyOnlyCheck) buyOnlyCheck.checked = true;
            } else {
                // all
                if (minPriceInput) minPriceInput.value = '';
                if (maxPriceInput) maxPriceInput.value = '';
            }

            runScreener('CUSTOM', criteria);
        });
    });

    const screenerFilterBtn = document.getElementById('screener-filter-btn');
    if (screenerFilterBtn) {
        screenerFilterBtn.addEventListener('click', () => {
            const custom = getCustomCriteriaPayload();
            runScreener('CUSTOM', custom);
        });
    }

    const screenerResetBtn = document.getElementById('screener-reset-btn');
    if (screenerResetBtn) {
        screenerResetBtn.addEventListener('click', () => {
            ['f-min-price', 'f-max-price', 'f-min-roe', 'f-max-der', 'f-min-pio', 'f-min-div', 'f-max-pe', 'f-min-score'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
            const buyOnly = document.getElementById('f-buy-only');
            if (buyOnly) buyOnly.checked = false;
            const underOnly = document.getElementById('f-undervalued-only');
            if (underOnly) underOnly.checked = false;
            const sortBy = document.getElementById('f-sort-by');
            if (sortBy) sortBy.value = 'composite_score';

            document.querySelectorAll('.quick-price-btn').forEach(b => {
                if (b.dataset.price === 'all') {
                    b.classList.add('active', 'bg-brand-600', 'text-white', 'border-brand-500');
                    b.classList.remove('bg-dark-surface', 'text-slate-300');
                } else {
                    b.classList.remove('active', 'bg-brand-600', 'text-white', 'border-brand-500');
                    b.classList.add('bg-dark-surface', 'text-slate-300');
                }
            });

            runScreener('BUFFETT_MOAT');
        });
    }

    const screenerSortSelect = document.getElementById('f-sort-by');
    if (screenerSortSelect) {
        screenerSortSelect.addEventListener('change', () => {
            const custom = getCustomCriteriaPayload();
            runScreener('CUSTOM', custom);
        });
    }

    // CSV Export
    const screenerCsvBtn = document.getElementById('screener-export-csv');
    if (screenerCsvBtn) {
        screenerCsvBtn.addEventListener('click', () => {
            if (!currentScreenerResults.length) return;
            const headers = ["Ticker", "Company Name", "Sector", `Price (${currentCurrency})`, "Upside (%)", "PER", "PBV", "ROE", "DER", "Piotroski", "Altman Z", "Div Yield", "Composite Score", "Grade", "Verdict"];
            const rows = currentScreenerResults.map(it => {
                const priceFormatted = currentCurrency === 'USD' ? (it.current_price * liveFxRate.idr_to_usd).toFixed(2) : it.current_price;
                return [
                    it.ticker, `"${it.name}"`, `"${it.sector}"`, priceFormatted, `${it.upside_pct.toFixed(1)}%`, it.per, it.pbv, it.roe, it.der, it.piotroski_f_score, it.altman_z_score, it.dividend_yield, it.composite_score, it.grade, it.verdict
                ];
            });

            const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(e => e.join(","))].join("\n");
            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", `idx_screener_${currentCurrency.toLowerCase()}_${new Date().toISOString().slice(0,10)}.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }

    // =============================================================
    // 5. CALENDAR AGENDA & IMPACT ENGINE FRONTEND
    // =============================================================
    let currentCalendarData = null;
    let currentCalendarFilters = {
        scope: 'ALL',
        category: 'ALL',
        impact_level: 'ALL',
        timeframe: 'ALL',
        search: '',
        ticker: ''
    };

    // Helper: Seamless navigation from Calendar to Single Emiten Analysis
    function navigateToSingleEmiten(ticker) {
        if (!ticker) return;
        ticker = ticker.trim().toUpperCase();

        // Switch active tab styling
        document.querySelectorAll('.nav-tab').forEach(t => {
            t.classList.remove('active', 'text-white', 'bg-brand-600', 'shadow-md');
            t.classList.add('text-slate-400');
        });
        const singleTab = document.getElementById('tab-single');
        if (singleTab) {
            singleTab.classList.add('active', 'text-white', 'bg-brand-600', 'shadow-md');
            singleTab.classList.remove('text-slate-400');
        }

        // Show Single Emiten section
        document.querySelectorAll('.tab-content').forEach(s => s.classList.add('hidden'));
        const singleSec = document.getElementById('section-single');
        if (singleSec) {
            singleSec.classList.remove('hidden');
        }

        // Populate search box and load
        const singleInput = document.getElementById('single-ticker-input');
        if (singleInput) {
            singleInput.value = ticker;
        }
        loadSingleEmiten(ticker);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Make it globally accessible for inline onclick if needed
    window.navigateToSingleEmiten = navigateToSingleEmiten;

    // Fetch Calendar Data
    async function loadCalendarData(forceRefresh = false) {
        const container = document.getElementById('calendar-cards-container');
        if (!currentCalendarData && container) {
            container.innerHTML = `
                <div class="bg-dark-card border border-dark-border rounded-2xl p-12 text-center text-slate-400 font-mono space-y-3">
                    <div class="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto"></div>
                    <p>Memuat kalender agenda makro & analisis saham terdampak...</p>
                </div>
            `;
        }

        try {
            const params = new URLSearchParams();
            if (currentCalendarFilters.scope && currentCalendarFilters.scope !== 'ALL') params.set('scope', currentCalendarFilters.scope);
            if (currentCalendarFilters.category && currentCalendarFilters.category !== 'ALL') params.set('category', currentCalendarFilters.category);
            if (currentCalendarFilters.impact_level && currentCalendarFilters.impact_level !== 'ALL') params.set('impact_level', currentCalendarFilters.impact_level);
            if (currentCalendarFilters.timeframe && currentCalendarFilters.timeframe !== 'ALL') params.set('timeframe', currentCalendarFilters.timeframe);
            if (currentCalendarFilters.search) params.set('search', currentCalendarFilters.search);
            if (currentCalendarFilters.ticker) params.set('ticker', currentCalendarFilters.ticker);

            const url = `/api/v1/calendar?${params.toString()}`;
            const resp = await fetch(url);
            if (!resp.ok) throw new Error('Gagal mengambil data kalender');
            const data = await resp.json();
            currentCalendarData = data;

            renderCalendarKPIs(data.stats, data.generated_at_desc);
            renderCalendarHighlights(data.upcoming_highlights);
            renderCalendarAgendas(data.agendas);
            renderSectorSensitivityModal(data.sector_sensitivities);
        } catch (err) {
            console.error('Error fetching calendar data:', err);
            if (container) {
                container.innerHTML = `
                    <div class="bg-dark-card border border-rose-500/30 rounded-2xl p-8 text-center text-rose-400 space-y-2">
                        <p class="font-bold">Gagal memuat kalender agenda</p>
                        <p class="text-xs text-slate-400">${err.message}</p>
                        <button id="calendar-retry-btn" class="mt-2 px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold shadow-md transition">Coba Lagi</button>
                    </div>
                `;
                const retryBtn = document.getElementById('calendar-retry-btn');
                if (retryBtn) retryBtn.addEventListener('click', () => loadCalendarData(true));
            }
        }
    }

    // Render KPI Metrics
    function renderCalendarKPIs(stats, genDate) {
        if (!stats) return;
        const kpiHigh = document.getElementById('calendar-kpi-high-impact');
        const kpiUs = document.getElementById('calendar-kpi-us-global');
        const kpiDom = document.getElementById('calendar-kpi-domestic');
        const kpiStocks = document.getElementById('calendar-kpi-stocks');
        const dateDesc = document.getElementById('calendar-generated-date');

        if (kpiHigh) kpiHigh.textContent = stats.high_impact_count || 0;
        if (kpiUs) kpiUs.textContent = stats.us_global_count || 0;
        if (kpiDom) kpiDom.textContent = stats.domestic_count || 0;
        if (kpiStocks) kpiStocks.textContent = stats.total_affected_stocks || 0;
        if (dateDesc && genDate) dateDesc.textContent = `Update: ${genDate}`;
    }

    // Render 3 Upcoming Highlights
    function renderCalendarHighlights(highlights) {
        const container = document.getElementById('calendar-highlights-container');
        if (!container) return;
        if (!highlights || !highlights.length) {
            container.innerHTML = `<div class="p-6 text-center text-slate-500 col-span-3 font-mono text-xs">Tidak ada sorotan agenda terdekat saat ini.</div>`;
            return;
        }

        container.innerHTML = highlights.map(item => {
            const countdownBadgeClass = item.days_until <= 1 
                ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse'
                : 'bg-blue-500/20 text-blue-300 border-blue-500/40';

            const impactStars = item.impact_level === 'HIGH' ? '🔴 3★ TINGGI' : (item.impact_level === 'MEDIUM' ? '🟡 2★ SEDANG' : '🟢 1★ RINGAN');

            const stockChips = item.impacted_stocks.slice(0, 4).map(s => `
                <button class="px-2 py-0.5 rounded-md bg-dark-bg border border-dark-border hover:border-brand-500 text-[11px] font-mono font-bold text-white hover:text-brand-400 transition" onclick="navigateToSingleEmiten('${s.ticker}')" title="${s.name} (${s.sector})">
                    ${s.ticker}
                </button>
            `).join('');

            return `
                <div class="bg-dark-bg/70 border border-dark-border hover:border-blue-500/50 rounded-2xl p-4 flex flex-col justify-between space-y-3 transition duration-200 shadow-md group">
                    <div class="space-y-2">
                        <div class="flex items-center justify-between gap-1.5 text-xs">
                            <span class="px-2 py-0.5 rounded-full border text-[10px] font-mono font-bold ${countdownBadgeClass}">
                                ${item.relative_time_label}
                            </span>
                            <span class="text-[10px] font-mono text-slate-400">${item.flag_emoji} ${item.country}</span>
                        </div>
                        <h4 class="text-sm font-bold text-white group-hover:text-blue-300 transition leading-snug line-clamp-2">
                            ${item.title}
                        </h4>
                        <div class="flex items-center gap-2 text-[11px] font-mono text-slate-400">
                            <span>📅 ${item.event_date}</span>
                            <span>⏰ ${item.time_utc7}</span>
                        </div>
                        <p class="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                            ${item.summary}
                        </p>
                    </div>

                    <div class="pt-2 border-t border-dark-border/60 space-y-2">
                        <div class="flex items-center justify-between text-[11px]">
                            <span class="text-slate-400 font-mono">Dampak: <strong class="text-slate-200">${impactStars}</strong></span>
                        </div>
                        <div class="space-y-1">
                            <span class="text-[10px] font-mono text-slate-400 block uppercase">Saham Terdampak:</span>
                            <div class="flex flex-wrap gap-1">
                                ${stockChips}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    // Render Full List of Agenda Cards
    function renderCalendarAgendas(agendas) {
        const container = document.getElementById('calendar-cards-container');
        const emptyState = document.getElementById('calendar-empty-state');
        const countDisplay = document.getElementById('calendar-count-display');

        if (countDisplay) {
            countDisplay.textContent = agendas ? agendas.length : 0;
        }

        if (!agendas || !agendas.length) {
            if (container) container.innerHTML = '';
            if (emptyState) emptyState.classList.remove('hidden');
            return;
        }

        if (emptyState) emptyState.classList.add('hidden');
        if (!container) return;

        container.innerHTML = agendas.map((item, idx) => {
            // Impact level badge
            let impactBadgeHtml = '';
            if (item.impact_level === 'HIGH') {
                impactBadgeHtml = '<span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30 flex items-center gap-1">🔴 Dampak Tinggi (3★)</span>';
            } else if (item.impact_level === 'MEDIUM') {
                impactBadgeHtml = '<span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30 flex items-center gap-1">🟡 Dampak Sedang (2★)</span>';
            } else {
                impactBadgeHtml = '<span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">🟢 Dampak Ringan (1★)</span>';
            }

            // Countdown Pill
            let countdownPillHtml = '';
            if (item.status === 'TODAY') {
                countdownPillHtml = '<span class="px-2.5 py-0.5 rounded-full text-xs font-mono font-extrabold bg-rose-500/25 text-rose-300 border border-rose-400 animate-pulse">🚨 Hari Ini</span>';
            } else if (item.days_until === 1) {
                countdownPillHtml = '<span class="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">⏳ Besok</span>';
            } else if (item.days_until > 1) {
                countdownPillHtml = `<span class="px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold bg-blue-500/15 text-blue-300 border border-blue-500/25">${item.relative_time_label}</span>`;
            } else {
                countdownPillHtml = `<span class="px-2.5 py-0.5 rounded-full text-xs font-mono text-slate-400 bg-dark-surface/60 border border-dark-border">${item.relative_time_label}</span>`;
            }

            // Metric numbers bar (Previous, Forecast, Actual)
            let metricsStripHtml = '';
            if (item.previous_val || item.forecast_val || item.actual_val) {
                metricsStripHtml = `
                    <div class="grid grid-cols-3 gap-2 p-3 bg-dark-bg/60 border border-dark-border/80 rounded-xl font-mono text-xs">
                        <div>
                            <span class="text-[10px] text-slate-400 block uppercase">Sebelumnya</span>
                            <span class="font-bold text-slate-200">${item.previous_val || '-'}</span>
                        </div>
                        <div>
                            <span class="text-[10px] text-slate-400 block uppercase">Konsensus / Proyeksi</span>
                            <span class="font-bold text-blue-300">${item.forecast_val || '-'}</span>
                        </div>
                        <div>
                            <span class="text-[10px] text-slate-400 block uppercase">Aktual / Realisasi</span>
                            <span class="font-bold ${item.actual_val ? 'text-emerald-400' : 'text-slate-500'}">${item.actual_val || 'Menunggu Rilis'}</span>
                        </div>
                    </div>
                `;
            }

            // Impacted stocks cards & badges
            const impactedStocksHtml = item.impacted_stocks.map(s => {
                let biasBadge = '';
                if (s.expected_bias === 'BULLISH') {
                    biasBadge = '<span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 font-bold">🟢 Bullish</span>';
                } else if (s.expected_bias === 'BEARISH') {
                    biasBadge = '<span class="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-400 border border-rose-500/25 font-bold">🔴 Bearish</span>';
                } else {
                    biasBadge = '<span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/25 font-bold">🟡 Volatil</span>';
                }

                return `
                    <div class="bg-dark-bg/90 border border-dark-border hover:border-brand-500/60 rounded-xl p-3 space-y-1.5 transition stock-chip-btn group" onclick="navigateToSingleEmiten('${s.ticker}')">
                        <div class="flex items-center justify-between gap-1">
                            <div class="flex items-center gap-1.5">
                                <span class="font-mono font-extrabold text-sm text-white group-hover:text-brand-400 transition">${s.ticker}</span>
                                <span class="text-[10px] text-slate-400 truncate max-w-[110px]">${s.name}</span>
                            </div>
                            ${biasBadge}
                        </div>
                        <div class="flex items-center justify-between text-[10px] font-mono text-slate-400">
                            <span>${s.sector}</span>
                            <span class="text-slate-500">Sensitivitas: <strong class="text-slate-300">${s.sensitivity}</strong></span>
                        </div>
                        <p class="text-[11px] text-slate-300 leading-snug line-clamp-2">
                            ${s.impact_reason}
                        </p>
                        <div class="text-[10px] text-brand-400 font-mono flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition pt-1">
                            <span>Buka Analisa</span> <span>→</span>
                        </div>
                    </div>
                `;
            }).join('');

            // Scenarios Matrix Items
            const scenariosHtml = item.scenarios.map(sc => `
                <div class="bg-dark-bg/80 border border-dark-border/80 rounded-xl p-3 space-y-2 text-xs">
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1 border-b border-dark-border/50 pb-1.5">
                        <span class="font-bold text-white flex items-center gap-1.5">
                            <span>📌</span> <span>${sc.scenario_name}</span>
                        </span>
                        <span class="text-[11px] font-mono text-cyan-300 bg-cyan-950/40 px-2 py-0.5 rounded border border-cyan-800/40">
                            Kondisi: ${sc.condition}
                        </span>
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                        <div>
                            <span class="text-slate-400 block font-mono">Dampak ke IHSG:</span>
                            <span class="font-semibold text-slate-200">${sc.ihsg_impact}</span>
                        </div>
                        <div>
                            <span class="text-slate-400 block font-mono">Reaksi Sektor:</span>
                            <span class="font-semibold text-slate-200">${sc.sector_impact}</span>
                        </div>
                    </div>
                    <div class="flex flex-wrap items-center gap-3 pt-1 border-t border-dark-border/40 text-[11px]">
                        ${sc.favored_stocks && sc.favored_stocks.length ? `
                            <div class="flex items-center gap-1">
                                <span class="text-emerald-400 font-mono">Saham Diuntungkan:</span>
                                <div class="flex flex-wrap gap-1">
                                    ${sc.favored_stocks.map(tk => `<span class="px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono font-bold">${tk}</span>`).join('')}
                                </div>
                            </div>
                        ` : ''}
                        ${sc.pressured_stocks && sc.pressured_stocks.length ? `
                            <div class="flex items-center gap-1">
                                <span class="text-rose-400 font-mono">Saham Tertekan:</span>
                                <div class="flex flex-wrap gap-1">
                                    ${sc.pressured_stocks.map(tk => `<span class="px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 font-mono font-bold">${tk}</span>`).join('')}
                                </div>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `).join('');

            const accordionId = `scenario-accordion-${idx}`;

            return `
                <div class="cal-agenda-card p-4 sm:p-6 shadow-xl space-y-4 relative overflow-hidden" id="agenda-card-${item.id}">
                    
                    <!-- Card Top Header -->
                    <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-dark-border pb-3.5">
                        <div class="flex items-center gap-2.5">
                            <span class="text-2xl">${item.flag_emoji}</span>
                            <div>
                                <div class="flex flex-wrap items-center gap-2">
                                    <span class="font-bold text-sm text-white">${item.country}</span>
                                    <span class="text-xs text-slate-400">• ${item.institution}</span>
                                    <span class="px-2 py-0.5 rounded-md text-[10px] font-mono bg-dark-surface border border-dark-border text-slate-300">${item.category_label}</span>
                                </div>
                                <h3 class="text-base sm:text-lg font-extrabold text-white mt-0.5 tracking-tight">${item.title}</h3>
                            </div>
                        </div>

                        <div class="flex items-center gap-2 shrink-0">
                            ${impactBadgeHtml}
                            ${countdownPillHtml}
                        </div>
                    </div>

                    <!-- Date & Time + Key Metrics Strip -->
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div class="flex items-center gap-3 p-3 bg-dark-bg/60 border border-dark-border/80 rounded-xl">
                            <div class="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/25 flex items-center justify-center text-blue-400 font-bold">
                                📅
                            </div>
                            <div class="font-mono text-xs">
                                <span class="text-slate-400 block">Jadwal Tanggal</span>
                                <span class="font-bold text-white">${item.event_date}</span>
                                <span class="text-slate-400 text-[10px] ml-1">(${item.time_utc7})</span>
                            </div>
                        </div>

                        <div class="md:col-span-2">
                            ${metricsStripHtml}
                        </div>
                    </div>

                    <!-- Summary & Fundamental Transmission -->
                    <div class="space-y-2.5">
                        <p class="text-xs sm:text-sm text-slate-300 leading-relaxed">
                            ${item.summary}
                        </p>

                        <!-- Transmission Box -->
                        <div class="p-3.5 bg-dark-surface/40 border border-dark-border rounded-xl space-y-1">
                            <div class="flex items-center gap-1.5 text-xs font-bold text-blue-400">
                                <span>⚙️</span>
                                <span>Mekanisme Transmisi Dampak ke Pasar IDX:</span>
                            </div>
                            <p class="text-xs text-slate-300 leading-relaxed">
                                ${item.transmission_mechanism}
                            </p>
                        </div>
                    </div>

                    <!-- Impacted Stocks Grid -->
                    <div class="space-y-2">
                        <div class="flex items-center justify-between">
                            <span class="text-xs font-bold text-white flex items-center gap-1.5">
                                <span>🎯</span>
                                <span>Saham Terdampak Langsung (${item.impacted_stocks.length} Emiten):</span>
                            </span>
                            <span class="text-[11px] font-mono text-slate-400">Klik saham untuk analisa fundamental</span>
                        </div>
                        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                            ${impactedStocksHtml}
                        </div>
                    </div>

                    <!-- Actionable Strategy & Scenario Dropdown Toggle -->
                    <div class="pt-3 border-t border-dark-border space-y-3">
                        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                            <div class="flex items-center gap-2 text-slate-300">
                                <span class="text-amber-400">💡</span>
                                <span><strong>Strategi Aksi:</strong> ${item.actionable_strategy}</span>
                            </div>

                            <button class="toggle-scenarios-btn px-3 py-1.5 rounded-xl bg-dark-surface hover:bg-dark-border text-cyan-400 hover:text-cyan-300 border border-cyan-500/30 text-xs font-semibold transition flex items-center gap-1.5 shrink-0" data-target="${accordionId}">
                                <span>📊</span>
                                <span>Matriks Skenario Hasil</span>
                                <span class="accordion-arrow transform transition-transform duration-200">▼</span>
                            </button>
                        </div>

                        <!-- Collapsible Scenarios Panel -->
                        <div id="${accordionId}" class="scenario-panel hidden space-y-2 pt-2 border-t border-dark-border/40">
                            <span class="text-[11px] font-mono text-slate-400 block uppercase">Analisis Skenario Reaksi Pasar:</span>
                            ${scenariosHtml}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // Attach Scenario Accordion Toggle Listeners
        document.querySelectorAll('.toggle-scenarios-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const targetId = btn.getAttribute('data-target');
                const panel = document.getElementById(targetId);
                const arrow = btn.querySelector('.accordion-arrow');
                if (panel) {
                    const isHidden = panel.classList.contains('hidden');
                    if (isHidden) {
                        panel.classList.remove('hidden');
                        if (arrow) arrow.style.transform = 'rotate(180deg)';
                    } else {
                        panel.classList.add('hidden');
                        if (arrow) arrow.style.transform = 'rotate(0deg)';
                    }
                }
            });
        });
    }

    // Render Sector Sensitivity Modal Content
    function renderSectorSensitivityModal(sectors) {
        const body = document.getElementById('sector-sensitivity-body');
        if (!body || !sectors || !sectors.length) return;

        body.innerHTML = sectors.map(sec => {
            const tickers = sec.key_tickers.map(tk => `
                <button class="px-2 py-0.5 rounded bg-dark-bg border border-dark-border hover:border-brand-500 text-xs font-mono font-bold text-white hover:text-brand-400 transition" onclick="document.getElementById('modal-sector-sensitivity').classList.add('hidden'); navigateToSingleEmiten('${tk}')">
                    ${tk}
                </button>
            `).join('');

            const catalysts = sec.primary_catalysts.map(cat => `
                <span class="px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 text-[11px] font-mono">${cat}</span>
            `).join('');

            let sensitivityBadge = '';
            if (sec.sensitivity_level === 'Sangat Tinggi') {
                sensitivityBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">🔴 Sangat Tinggi</span>';
            } else if (sec.sensitivity_level === 'Tinggi') {
                sensitivityBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">🟡 Tinggi</span>';
            } else {
                sensitivityBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">🟢 Sedang</span>';
            }

            return `
                <div class="bg-dark-bg border border-dark-border hover:border-cyan-500/40 rounded-2xl p-4 sm:p-5 space-y-3 transition">
                    <div class="flex items-center justify-between border-b border-dark-border pb-2.5">
                        <div class="flex items-center gap-2.5">
                            <span class="text-2xl">${sec.icon}</span>
                            <div>
                                <h4 class="text-sm sm:text-base font-bold text-white">${sec.sector_name}</h4>
                            </div>
                        </div>
                        ${sensitivityBadge}
                    </div>

                    <div class="space-y-2 text-xs">
                        <div>
                            <span class="text-[10px] font-mono text-slate-400 block uppercase mb-1">Katalis Penggerak Utama:</span>
                            <div class="flex flex-wrap gap-1.5">
                                ${catalysts}
                            </div>
                        </div>

                        <div>
                            <span class="text-[10px] font-mono text-slate-400 block uppercase mb-1">Saham Utama Terkait:</span>
                            <div class="flex flex-wrap gap-1.5">
                                ${tickers}
                            </div>
                        </div>

                        <div class="p-2.5 bg-dark-surface/40 border border-dark-border/80 rounded-xl text-slate-300 text-xs leading-relaxed">
                            <span class="text-cyan-400 font-semibold font-mono">Sensitivitas Makro:</span> ${sec.macro_exposure}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    // Attach Calendar Event Listeners
    function attachCalendarListeners() {
        // Scope Buttons
        document.querySelectorAll('.cal-scope-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.cal-scope-btn').forEach(b => {
                    b.classList.remove('active', 'text-white', 'bg-blue-600', 'shadow-sm');
                    b.classList.add('text-slate-400');
                });
                btn.classList.add('active', 'text-white', 'bg-blue-600', 'shadow-sm');
                btn.classList.remove('text-slate-400');
                currentCalendarFilters.scope = btn.getAttribute('data-scope') || 'ALL';
                loadCalendarData();
            });
        });

        // Category Buttons
        document.querySelectorAll('.cal-cat-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.cal-cat-btn').forEach(b => {
                    b.classList.remove('active', 'bg-blue-600', 'text-white');
                    b.classList.add('bg-dark-bg', 'border', 'border-dark-border', 'text-slate-300');
                });
                btn.classList.add('active', 'bg-blue-600', 'text-white');
                btn.classList.remove('bg-dark-bg', 'text-slate-300');
                currentCalendarFilters.category = btn.getAttribute('data-category') || 'ALL';
                loadCalendarData();
            });
        });

        // Impact Level Buttons
        document.querySelectorAll('.cal-impact-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.cal-impact-btn').forEach(b => {
                    b.classList.remove('active', 'bg-dark-surface', 'border-slate-600', 'text-white');
                    b.classList.add('bg-dark-bg');
                });
                btn.classList.add('active', 'bg-dark-surface', 'border-slate-600', 'text-white');
                btn.classList.remove('bg-dark-bg');
                currentCalendarFilters.impact_level = btn.getAttribute('data-impact') || 'ALL';
                loadCalendarData();
            });
        });

        // Time Horizon Buttons
        document.querySelectorAll('.cal-time-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.cal-time-btn').forEach(b => {
                    b.classList.remove('active', 'bg-dark-surface', 'border-slate-600', 'text-white');
                    b.classList.add('bg-dark-bg');
                });
                btn.classList.add('active', 'bg-dark-surface', 'border-slate-600', 'text-white');
                btn.classList.remove('bg-dark-bg');
                currentCalendarFilters.timeframe = btn.getAttribute('data-time') || 'ALL';
                loadCalendarData();
            });
        });

        // Search Input with Debounce
        const searchInput = document.getElementById('calendar-search-input');
        const clearSearchBtn = document.getElementById('calendar-clear-search-btn');
        let searchTimer = null;

        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const val = e.target.value.trim();
                if (clearSearchBtn) {
                    if (val) clearSearchBtn.classList.remove('hidden');
                    else clearSearchBtn.classList.add('hidden');
                }
                clearTimeout(searchTimer);
                searchTimer = setTimeout(() => {
                    currentCalendarFilters.search = val;
                    loadCalendarData();
                }, 300);
            });
        }

        if (clearSearchBtn) {
            clearSearchBtn.addEventListener('click', () => {
                if (searchInput) searchInput.value = '';
                clearSearchBtn.classList.add('hidden');
                currentCalendarFilters.search = '';
                loadCalendarData();
            });
        }

        // Reset Filter Buttons
        const resetFilters = () => {
            currentCalendarFilters = {
                scope: 'ALL',
                category: 'ALL',
                impact_level: 'ALL',
                timeframe: 'ALL',
                search: '',
                ticker: ''
            };
            if (searchInput) searchInput.value = '';
            if (clearSearchBtn) clearSearchBtn.classList.add('hidden');

            // Reset UI pills
            document.querySelectorAll('.cal-scope-btn').forEach(b => {
                if (b.getAttribute('data-scope') === 'ALL') {
                    b.classList.add('active', 'text-white', 'bg-blue-600', 'shadow-sm');
                    b.classList.remove('text-slate-400');
                } else {
                    b.classList.remove('active', 'text-white', 'bg-blue-600', 'shadow-sm');
                    b.classList.add('text-slate-400');
                }
            });

            document.querySelectorAll('.cal-cat-btn').forEach(b => {
                if (b.getAttribute('data-category') === 'ALL') {
                    b.classList.add('active', 'bg-blue-600', 'text-white');
                    b.classList.remove('bg-dark-bg', 'text-slate-300');
                } else {
                    b.classList.remove('active', 'bg-blue-600', 'text-white');
                    b.classList.add('bg-dark-bg', 'text-slate-300');
                }
            });

            document.querySelectorAll('.cal-impact-btn').forEach(b => {
                if (b.getAttribute('data-impact') === 'ALL') {
                    b.classList.add('active', 'bg-dark-surface', 'border-slate-600', 'text-white');
                    b.classList.remove('bg-dark-bg');
                } else {
                    b.classList.remove('active', 'bg-dark-surface', 'border-slate-600', 'text-white');
                    b.classList.add('bg-dark-bg');
                }
            });

            document.querySelectorAll('.cal-time-btn').forEach(b => {
                if (b.getAttribute('data-time') === 'ALL') {
                    b.classList.add('active', 'bg-dark-surface', 'border-slate-600', 'text-white');
                    b.classList.remove('bg-dark-bg');
                } else {
                    b.classList.remove('active', 'bg-dark-surface', 'border-slate-600', 'text-white');
                    b.classList.add('bg-dark-bg');
                }
            });

            loadCalendarData();
        };

        const resetBtn1 = document.getElementById('calendar-reset-all-filters-btn');
        const resetBtn2 = document.getElementById('calendar-empty-reset-btn');
        if (resetBtn1) resetBtn1.addEventListener('click', resetFilters);
        if (resetBtn2) resetBtn2.addEventListener('click', resetFilters);

        // Refresh Button
        const refreshBtn = document.getElementById('btn-refresh-calendar');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                refreshBtn.classList.add('animate-spin');
                loadCalendarData(true).finally(() => {
                    setTimeout(() => refreshBtn.classList.remove('animate-spin'), 600);
                });
            });
        }

        // Sector Sensitivity Modal
        const sectorModal = document.getElementById('modal-sector-sensitivity');
        const openSectorModalBtn = document.getElementById('btn-open-sector-sensitivity');
        const closeSectorModalBtn1 = document.getElementById('close-sector-sensitivity-modal-btn');
        const closeSectorModalBtn2 = document.getElementById('btn-close-sector-sensitivity-footer');

        if (openSectorModalBtn && sectorModal) {
            openSectorModalBtn.addEventListener('click', () => {
                sectorModal.classList.remove('hidden');
            });
        }

        const closeSectorModal = () => {
            if (sectorModal) sectorModal.classList.add('hidden');
        };

        if (closeSectorModalBtn1) closeSectorModalBtn1.addEventListener('click', closeSectorModal);
        if (closeSectorModalBtn2) closeSectorModalBtn2.addEventListener('click', closeSectorModal);
        if (sectorModal) {
            sectorModal.addEventListener('click', (e) => {
                if (e.target === sectorModal) closeSectorModal();
            });
        }
    }

    // -------------------------------------------------------------
    // 12. Global Macro Commodities & Forex Real-Time Scoper
    // -------------------------------------------------------------
    let macroData = null;
    let selectedCommodityId = 'COAL';
    let activeMacroCategory = 'ALL';
    let activeScopedFilter = 'ALL';
    let scopedEmitensData = null;

    async function loadMacroOverview(forceRefresh = false) {
        const refreshBtn = document.getElementById('macro-refresh-btn');
        const spinner = document.getElementById('macro-refresh-spinner');
        const updatedLabel = document.getElementById('macro-last-updated');

        if (spinner) spinner.classList.add('animate-spin');
        if (updatedLabel) updatedLabel.textContent = 'Memperbarui data real-time 1:1...';

        try {
            const resp = await fetch(`/api/v1/commodities/overview?refresh=${forceRefresh}`);
            if (!resp.ok) throw new Error('Gagal memuat overview komoditas');
            macroData = await resp.json();

            if (updatedLabel) {
                updatedLabel.textContent = `Update: ${macroData.market_as_of} (${macroData.data_source_status})`;
            }

            renderMacroOverview();

            // Default selection if not selected yet
            if (!scopedEmitensData) {
                const defaultCid = (macroData.top_gainers && macroData.top_gainers.length > 0)
                    ? macroData.top_gainers[0].id
                    : 'COAL';
                selectCommodity(defaultCid);
            }
        } catch (err) {
            console.error('Error loadMacroOverview:', err);
            if (updatedLabel) updatedLabel.textContent = 'Gagal memuat data komoditas live';
        } finally {
            if (spinner) spinner.classList.remove('animate-spin');
        }
    }

    function renderMacroOverview() {
        if (!macroData) return;

        // 1. Render Top Gainers Strip
        const gainersContainer = document.getElementById('macro-gainers-cards');
        if (gainersContainer) {
            const gainers = (macroData.top_gainers && macroData.top_gainers.length > 0)
                ? macroData.top_gainers
                : macroData.commodities.slice(0, 5);

            gainersContainer.innerHTML = gainers.map(g => {
                const chgSign = g.change_pct_24h >= 0 ? '+' : '';
                const isSelected = g.id === selectedCommodityId;
                return `
                    <div class="cursor-pointer group p-3 rounded-xl border transition-all duration-200 ${
                        isSelected 
                            ? 'bg-amber-500/15 border-amber-400 shadow-md shadow-amber-500/10' 
                            : 'bg-dark-card border-dark-border hover:border-amber-500/40 hover:bg-dark-surface'
                    }" onclick="window.selectMacroCommodity('${g.id}')">
                        <div class="flex items-center justify-between text-[11px]">
                            <span class="font-bold text-slate-300 truncate group-hover:text-amber-300 transition">${g.name}</span>
                            <span class="px-1.5 py-0.2 text-[10px] font-mono font-bold rounded ${
                                g.change_pct_24h >= 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                            }">${chgSign}${g.change_pct_24h}%</span>
                        </div>
                        <div class="mt-1.5 flex items-baseline justify-between">
                            <span class="text-sm font-black text-white font-mono">${formatMacroPrice(g.price, g.currency)}</span>
                            <span class="text-[10px] text-slate-400 font-mono">${g.unit}</span>
                        </div>
                    </div>
                `;
            }).join('');
        }

        // 2. Filter list by Category
        let displayList = [];
        if (activeMacroCategory === 'ALL') {
            displayList = [...macroData.commodities, ...macroData.forex_pairs];
        } else if (activeMacroCategory === 'FOREX') {
            displayList = macroData.forex_pairs || [];
        } else {
            displayList = (macroData.commodities || []).filter(c => c.category === activeMacroCategory);
        }

        // 3. Render Cards Grid
        const grid = document.getElementById('macro-commodities-grid');
        if (grid) {
            grid.innerHTML = displayList.map(item => {
                const isSelected = item.id === selectedCommodityId;
                const chgSign = item.change_pct_24h >= 0 ? '+' : '';
                const isPos = item.change_pct_24h >= 0;
                const catBadgeColor = {
                    'ENERGY': 'bg-amber-500/10 text-amber-400 border-amber-500/25',
                    'METALS': 'bg-cyan-500/10 text-cyan-400 border-cyan-500/25',
                    'AGRICULTURE': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25',
                    'FOREX': 'bg-blue-500/10 text-blue-400 border-blue-500/25'
                }[item.category] || 'bg-slate-800 text-slate-300 border-slate-700';

                return `
                    <div class="group relative p-4 rounded-2xl border transition-all duration-200 cursor-pointer ${
                        isSelected
                            ? 'bg-gradient-to-b from-amber-950/20 to-dark-card border-amber-400 ring-2 ring-amber-500/20 shadow-xl'
                            : 'bg-dark-card border-dark-border hover:border-slate-600 hover:bg-dark-surface'
                    }" onclick="window.selectMacroCommodity('${item.id}')">
                        
                        <!-- Top Meta -->
                        <div class="flex items-center justify-between gap-2 mb-2">
                            <span class="px-2 py-0.5 text-[9px] font-mono font-bold uppercase rounded-md border ${catBadgeColor}">
                                ${item.category}
                            </span>
                            <span class="text-[10px] font-mono text-slate-400">${item.symbol}</span>
                        </div>

                        <!-- Title -->
                        <h3 class="text-sm font-bold text-white group-hover:text-amber-300 transition line-clamp-1">
                            ${item.name}
                        </h3>

                        <!-- Price & Change -->
                        <div class="mt-3 flex items-baseline justify-between gap-2">
                            <div>
                                <span class="text-lg sm:text-xl font-extrabold text-white font-mono tracking-tight">
                                    ${formatMacroPrice(item.price, item.currency)}
                                </span>
                                <span class="text-[11px] text-slate-400 font-mono block">${item.unit}</span>
                            </div>
                            <div class="text-right">
                                <span class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-mono font-bold rounded-lg ${
                                    isPos ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                                }">
                                    <span>${isPos ? '▲' : '▼'}</span>
                                    <span>${chgSign}${item.change_pct_24h}%</span>
                                </span>
                                <span class="text-[10px] font-mono text-slate-400 block mt-0.5">
                                    ${chgSign}${formatMacroPrice(item.change_24h, item.currency)}
                                </span>
                            </div>
                        </div>

                        <!-- Footer Pill: Correlated Emitens -->
                        <div class="mt-4 pt-3 border-t border-dark-border/60 flex items-center justify-between text-[11px]">
                            <span class="text-brand-400 font-mono font-semibold flex items-center gap-1">
                                <span>⚡</span>
                                <span>${item.related_emitens_count} Saham Terkait</span>
                            </span>
                            <span class="text-slate-400 text-[10px] group-hover:text-amber-300 transition flex items-center gap-0.5">
                                <span>Scope &amp; Nilai</span>
                                <span>→</span>
                            </span>
                        </div>
                    </div>
                `;
            }).join('');
        }
    }

    async function selectCommodity(cid) {
        selectedCommodityId = cid;
        renderMacroOverview(); // Re-render to highlight active card

        const titleEl = document.getElementById('scoper-commodity-title');
        const priceEl = document.getElementById('scoper-commodity-price-tag');
        const descEl = document.getElementById('scoper-commodity-desc');
        const catBadge = document.getElementById('scoper-category-badge');
        const grid = document.getElementById('macro-scoped-emitens-grid');

        if (grid) {
            grid.innerHTML = `
                <div class="col-span-full p-12 text-center space-y-3">
                    <div class="w-8 h-8 mx-auto border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
                    <p class="text-xs text-slate-400 font-mono">Menganalisis skor fundamental &amp; valuasi emiten terkait...</p>
                </div>
            `;
        }

        try {
            const resp = await fetch(`/api/v1/commodities/${cid}/emitens`);
            if (!resp.ok) throw new Error('Gagal mengambil data emiten terkait');
            scopedEmitensData = await resp.json();

            const c = scopedEmitensData.commodity;
            if (titleEl) titleEl.textContent = c.name;
            if (priceEl) {
                const chgSign = c.change_pct_24h >= 0 ? '+' : '';
                priceEl.textContent = `${formatMacroPrice(c.price, c.currency)} ${c.unit} (${chgSign}${c.change_pct_24h}%)`;
                priceEl.className = `text-sm sm:text-base font-mono font-bold ${c.change_pct_24h >= 0 ? 'text-emerald-400' : 'text-rose-400'}`;
            }
            if (descEl) descEl.textContent = c.description;
            if (catBadge) catBadge.textContent = c.category;

            // Stats update
            const totalEl = document.getElementById('scoper-stat-total');
            const underEl = document.getElementById('scoper-stat-undervalued');
            const avgEl = document.getElementById('scoper-stat-avg-score');
            const topEl = document.getElementById('scoper-stat-top-pick');

            if (totalEl) totalEl.textContent = scopedEmitensData.total_related_emitens;
            if (underEl) underEl.textContent = `${scopedEmitensData.undervalued_count} Emiten`;
            if (avgEl) avgEl.textContent = scopedEmitensData.avg_composite_score;
            if (topEl) topEl.textContent = scopedEmitensData.top_pick_ticker || '-';

            renderScopedEmitens(activeScopedFilter);
        } catch (err) {
            console.error('Error selectCommodity:', err);
            if (grid) {
                grid.innerHTML = `
                    <div class="col-span-full p-8 text-center text-rose-400 text-xs">
                        Gagal memuat evaluasi fundamental emiten: ${err.message}
                    </div>
                `;
            }
        }
    }

    function renderScopedEmitens(filterMode = 'ALL') {
        if (!scopedEmitensData) return;

        let list = scopedEmitensData.emitens || [];

        if (filterMode === 'UNDERVALUED') {
            list = list.filter(e => e.upside_pct > 0);
        } else if (filterMode === 'TOP_SUITABLE') {
            list = list.filter(e => e.suitability === 'SANGAT_LAYAK');
        } else if (filterMode === 'BENEFICIARY') {
            list = list.filter(e => e.impact_direction.includes('POSITIF'));
        }

        const emptyEl = document.getElementById('macro-scoper-empty');
        const grid = document.getElementById('macro-scoped-emitens-grid');

        if (!grid) return;

        if (list.length === 0) {
            grid.innerHTML = '';
            if (emptyEl) emptyEl.classList.remove('hidden');
            return;
        }

        if (emptyEl) emptyEl.classList.add('hidden');

        grid.innerHTML = list.map(em => {
            const isPos = em.upside_pct >= 0;
            const upSign = isPos ? '+' : '';
            
            // Suitability styling
            const suitConfig = {
                'SANGAT_LAYAK': {
                    border: 'border-emerald-500/40 hover:border-emerald-400',
                    bg: 'bg-emerald-950/10',
                    badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
                    icon: '⭐'
                },
                'LAYAK_ANALISIS': {
                    border: 'border-blue-500/40 hover:border-blue-400',
                    bg: 'bg-blue-950/10',
                    badge: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
                    icon: '💎'
                },
                'NETRAL': {
                    border: 'border-slate-700 hover:border-slate-600',
                    bg: 'bg-dark-card',
                    badge: 'bg-slate-800 text-slate-300 border-slate-700',
                    icon: '⚖️'
                },
                'SPEKULATIF_WASPADA': {
                    border: 'border-amber-500/40 hover:border-amber-400',
                    bg: 'bg-amber-950/10',
                    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
                    icon: '⚠️'
                },
                'HINDARI': {
                    border: 'border-rose-500/40 hover:border-rose-400',
                    bg: 'bg-rose-950/10',
                    badge: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
                    icon: '⛔'
                }
            }[em.suitability] || {
                border: 'border-dark-border',
                bg: 'bg-dark-card',
                badge: 'bg-slate-800 text-slate-300 border-slate-700',
                icon: '🔍'
            };

            const isBeneficiary = em.impact_direction.includes('POSITIF');

            return `
                <div class="rounded-2xl border p-5 flex flex-col justify-between transition-all duration-200 shadow-lg ${suitConfig.border} ${suitConfig.bg}">
                    
                    <!-- Header -->
                    <div>
                        <div class="flex items-start justify-between gap-2">
                            <div>
                                <div class="flex items-center gap-2">
                                    <span class="text-xl font-black text-white font-mono tracking-tight">${em.ticker}</span>
                                    <span class="px-2 py-0.5 text-[10px] font-mono font-bold rounded-md border ${
                                        isBeneficiary 
                                            ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' 
                                            : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                                    }">
                                        ${isBeneficiary ? '🚀 BENEFICIARY' : '⚠️ BIAYA NAIK'}
                                    </span>
                                </div>
                                <p class="text-xs text-slate-300 font-medium line-clamp-1 mt-0.5">${em.name}</p>
                                <p class="text-[10px] text-slate-400 font-mono">${em.sector}</p>
                            </div>

                            <!-- Grade & Score Badge -->
                            <div class="text-right shrink-0">
                                <div class="px-2.5 py-1 rounded-xl bg-dark-bg border border-dark-border flex items-center gap-1.5">
                                    <span class="text-[10px] font-mono text-slate-400">SKOR</span>
                                    <span class="text-sm font-extrabold text-amber-400 font-mono">${em.composite_score.toFixed(1)}</span>
                                    <span class="px-1.5 py-0.2 text-[10px] font-black rounded bg-brand-500/20 text-brand-300 font-mono">${em.grade}</span>
                                </div>
                            </div>
                        </div>

                        <!-- Investment Suitability Badge -->
                        <div class="mt-3">
                            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold rounded-xl border ${suitConfig.badge}">
                                <span>${suitConfig.icon}</span>
                                <span>${em.suitability_label}</span>
                            </span>
                        </div>

                        <!-- Price & Valuation Box -->
                        <div class="mt-3 p-3 rounded-xl bg-dark-bg/80 border border-dark-border grid grid-cols-3 gap-2 text-center">
                            <div>
                                <span class="text-[10px] font-mono text-slate-400 block">HARGA</span>
                                <span class="text-xs font-bold text-white font-mono">${formatPrice(em.current_price)}</span>
                            </div>
                            <div>
                                <span class="text-[10px] font-mono text-slate-400 block">FAIR VALUE</span>
                                <span class="text-xs font-bold text-brand-300 font-mono">${formatPrice(em.fair_value)}</span>
                            </div>
                            <div>
                                <span class="text-[10px] font-mono text-slate-400 block">UPSIDE</span>
                                <span class="text-xs font-bold font-mono ${isPos ? 'text-emerald-400' : 'text-rose-400'}">
                                    ${upSign}${em.upside_pct.toFixed(1)}%
                                </span>
                            </div>
                        </div>

                        <!-- Fundamental Metrics Grid -->
                        <div class="mt-3 grid grid-cols-4 gap-1.5 text-center text-[11px] font-mono">
                            <div class="p-1.5 rounded-lg bg-dark-surface border border-dark-border/60">
                                <span class="text-[9px] text-slate-400 block">PER</span>
                                <span class="font-bold text-white">${em.per > 0 ? em.per.toFixed(1) + 'x' : '-'}</span>
                            </div>
                            <div class="p-1.5 rounded-lg bg-dark-surface border border-dark-border/60">
                                <span class="text-[9px] text-slate-400 block">PBV</span>
                                <span class="font-bold text-white">${em.pbv > 0 ? em.pbv.toFixed(2) + 'x' : '-'}</span>
                            </div>
                            <div class="p-1.5 rounded-lg bg-dark-surface border border-dark-border/60">
                                <span class="text-[9px] text-slate-400 block">ROE</span>
                                <span class="font-bold ${em.roe >= 14 ? 'text-emerald-400' : em.roe < 0 ? 'text-rose-400' : 'text-slate-200'}">
                                    ${em.roe.toFixed(1)}%
                                </span>
                            </div>
                            <div class="p-1.5 rounded-lg bg-dark-surface border border-dark-border/60">
                                <span class="text-[9px] text-slate-400 block">DER</span>
                                <span class="font-bold ${em.der <= 1.0 ? 'text-emerald-400' : em.der > 2.0 ? 'text-rose-400' : 'text-slate-200'}">
                                    ${em.der.toFixed(2)}x
                                </span>
                            </div>
                        </div>

                        <!-- Quality & Div Yield Sub-row -->
                        <div class="mt-1.5 flex items-center justify-between text-[10px] font-mono text-slate-400 px-1">
                            <span>Piotroski: <strong class="text-white">${em.piotroski_f_score}/9</strong></span>
                            <span>Altman-Z: <strong class="text-white">${em.altman_z_score.toFixed(2)}</strong></span>
                            <span>Div Yield: <strong class="${em.dividend_yield > 4 ? 'text-amber-400' : 'text-white'}">${em.dividend_yield.toFixed(1)}%</strong></span>
                        </div>

                        <!-- Business Correlation Thesis -->
                        <div class="mt-3 p-3 rounded-xl bg-dark-surface/90 border border-dark-border text-xs leading-relaxed text-slate-300 space-y-1">
                            <div class="text-[10px] font-bold uppercase tracking-wider text-amber-400 font-mono flex items-center gap-1">
                                <span>💡</span>
                                <span>Tesis Korelasi &amp; Transmisi Bisnis</span>
                            </div>
                            <p>${em.correlation_thesis}</p>
                        </div>
                    </div>

                    <!-- Footer Action Button -->
                    <div class="mt-4 pt-3 border-t border-dark-border flex items-center justify-between">
                        <span class="text-[11px] font-mono font-bold text-slate-400">
                            Verdict: <span class="text-white">${em.verdict}</span>
                        </span>
                        <button class="px-3 py-1.5 bg-brand-600 hover:bg-brand-500 text-white text-xs font-bold rounded-xl transition shadow-md flex items-center gap-1.5 cursor-pointer"
                            onclick="window.openEmitenAnalysis('${em.ticker}')">
                            <span>🔍 Analisis Lengkap</span>
                            <span>→</span>
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    function formatMacroPrice(val, curr = 'USD') {
        if (val === null || val === undefined || isNaN(val)) return '-';
        if (curr === 'IDR') {
            return `Rp ${val.toLocaleString('id-ID', { maximumFractionDigits: 0 })}`;
        }
        if (val >= 100) {
            return `$${val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }
        return `$${val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`;
    }

    // Expose helpers globally for inline onclick
    window.selectMacroCommodity = (cid) => {
        return selectCommodity(cid);
    };

    window.openEmitenAnalysis = (ticker) => {
        // Switch to single emiten tab
        const singleTabBtn = document.getElementById('tab-single');
        if (singleTabBtn) singleTabBtn.click();
        const singleInput = document.getElementById('single-ticker-input');
        if (singleInput) singleInput.value = ticker;
        loadSingleEmiten(ticker);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    // Attach listeners for Macro Section
    function attachMacroListeners() {
        const refreshBtn = document.getElementById('macro-refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                loadMacroOverview(true);
            });
        }

        // Category Filter Buttons
        const catButtons = document.querySelectorAll('.macro-cat-btn');
        catButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                catButtons.forEach(b => {
                    b.classList.remove('bg-brand-600', 'text-white', 'border-brand-500/30', 'shadow-sm');
                    b.classList.add('bg-dark-card', 'text-slate-400', 'border-dark-border');
                });
                btn.classList.add('bg-brand-600', 'text-white', 'border-brand-500/30', 'shadow-sm');
                btn.classList.remove('bg-dark-card', 'text-slate-400', 'border-dark-border');

                activeMacroCategory = btn.getAttribute('data-category') || 'ALL';
                renderMacroOverview();
            });
        });

        // Scoper Filter Buttons
        const scoperButtons = document.querySelectorAll('.scoper-filter-btn');
        scoperButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                scoperButtons.forEach(b => {
                    b.classList.remove('bg-brand-600', 'text-white', 'shadow-sm', 'border-brand-500/40');
                    b.classList.add('bg-dark-surface', 'text-slate-400', 'border-dark-border');
                });
                btn.classList.add('bg-brand-600', 'text-white', 'shadow-sm', 'border-brand-500/40');
                btn.classList.remove('bg-dark-surface', 'text-slate-400', 'border-dark-border');

                activeScopedFilter = btn.getAttribute('data-filter') || 'ALL';
                renderScopedEmitens(activeScopedFilter);
            });
        });
    }

    attachMacroListeners();

    // -------------------------------------------------------------
    // Initial load & URL Routing (/stock/[CODE])
    // -------------------------------------------------------------
    setGlobalCurrency(currentCurrency);
    fetchLiveCurrencyRate();

    // Check if current URL matches /stock/[CODE] or query param ?ticker=[CODE]
    const pathMatch = window.location.pathname.match(/\/stock\/([A-Za-z0-9]+)/i);
    const urlParams = new URLSearchParams(window.location.search);
    const queryTicker = urlParams.get('ticker') || urlParams.get('code') || urlParams.get('s');
    const initialTicker = (pathMatch && pathMatch[1]) ? pathMatch[1].toUpperCase() : (queryTicker ? queryTicker.toUpperCase() : null);

    if (initialTicker) {
        // Direct permalink access: switch immediately to single emiten analysis tab
        const singleTabBtn = document.getElementById('tab-single');
        if (singleTabBtn) singleTabBtn.click();
        loadSingleEmiten(initialTicker, null, false, false, false);
    } else {
        // Default homepage flow
        loadMarketSummary();
        loadSingleEmiten('BBRI', null, false, true, false);
    }

    // Support browser back/forward history navigation
    window.addEventListener('popstate', (e) => {
        const pm = window.location.pathname.match(/\/stock\/([A-Za-z0-9]+)/i);
        if (pm && pm[1]) {
            const singleTabBtn = document.getElementById('tab-single');
            if (singleTabBtn) singleTabBtn.click();
            loadSingleEmiten(pm[1].toUpperCase(), null, false, false, false);
        } else if (window.location.pathname === '/' || window.location.pathname === '') {
            const marketTabBtn = document.getElementById('tab-market');
            if (marketTabBtn) marketTabBtn.click();
        }
    });
});
