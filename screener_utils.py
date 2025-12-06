import datetime
import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
from ui_components import small_button
from math import sqrt
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from utils import get_available_symbols, get_symbols_list

RISK_FREE_RATE = 0.06  # 6% annual risk-free rate for Sharpe calculation
NIFTY_TICKERS = ['^NSEI', '^N50', '^NIFTY50', '^Nifty50', 'NIFTY50.NS']  # index candidates

# Data storage configuration
DATA_DIR = Path("data")
PRICES_FILE = DATA_DIR / "nifty50_prices.parquet"
TIMESTAMP_FILE = DATA_DIR / "last_update.txt"
METRICS_FILES = {
    'consistent': DATA_DIR / "metrics_consistent.parquet",
    'low_risk': DATA_DIR / "metrics_low_risk.parquet",
    'high_growth': DATA_DIR / "metrics_high_growth.parquet",
    'momentum': DATA_DIR / "metrics_momentum.parquet"
}

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# ----------------------------------------------------------------------------------
# 1. Local Storage Management
# ----------------------------------------------------------------------------------

def save_price_data(price_df: pd.DataFrame, nifty_series: pd.Series) -> None:
    """Save price data and benchmark to local Parquet file."""
    combined = price_df.copy()
    if not nifty_series.empty:
        combined['NIFTY50_INDEX'] = nifty_series
    combined.to_parquet(PRICES_FILE)
    # Save timestamp
    with open(TIMESTAMP_FILE, 'w') as f:
        f.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@st.cache_data(show_spinner=False)
def load_price_data() -> Tuple[pd.DataFrame, pd.Series, str]:
    """Load cached price data from local storage.
    
    Returns (price_df, nifty_series, timestamp_str)
    """
    if not PRICES_FILE.exists():
        return pd.DataFrame(), pd.Series(dtype=float), ""
    
    df = pd.read_parquet(PRICES_FILE)
    timestamp = ""
    if TIMESTAMP_FILE.exists():
        with open(TIMESTAMP_FILE, 'r') as f:
            timestamp = f.read().strip()
    
    # Extract benchmark if exists
    if 'NIFTY50_INDEX' in df.columns:
        nifty_series = df['NIFTY50_INDEX'].copy()
        price_df = df.drop(columns=['NIFTY50_INDEX'])
    else:
        nifty_series = pd.Series(dtype=float)
        price_df = df
    
    return price_df, nifty_series, timestamp

def save_tab_metrics(tab_key: str, metrics_df: pd.DataFrame) -> None:
    """Save computed metrics for a specific tab."""
    if tab_key in METRICS_FILES:
        metrics_df.to_parquet(METRICS_FILES[tab_key])

@st.cache_data(show_spinner=False)
def load_tab_metrics(tab_key: str) -> Optional[pd.DataFrame]:
    """Load cached metrics for a specific tab."""
    if tab_key in METRICS_FILES and METRICS_FILES[tab_key].exists():
        return pd.read_parquet(METRICS_FILES[tab_key])
    return None

def clear_all_metrics() -> None:
    """Delete all cached metrics files to force recalculation."""
    for file in METRICS_FILES.values():
        if file.exists():
            file.unlink()

def check_data_exists() -> bool:
    """Check if local price data exists."""
    return PRICES_FILE.exists()

# ----------------------------------------------------------------------------------
# 2. Data Retrieval (Download from API)
# ----------------------------------------------------------------------------------

def download_price_data(tickers: List[str]) -> Tuple[pd.DataFrame, pd.Series]:
    """Download 5-year daily adjusted close prices for given tickers plus NIFTY50.

    start date fixed at 2019-01-01 for broader context; metrics use slicing for 1y / 5y.
    Returns (price_df, nifty_series) where price_df has columns tickers and nifty_series is benchmark.
    Missing tickers are skipped.
    """
    if not tickers:
        return pd.DataFrame(), pd.Series(dtype=float)
    unique = [t for t in dict.fromkeys(tickers) if t]

    start = '2019-01-01'
    end = datetime.datetime.today().strftime('%Y-%m-%d')

    # Always attempt benchmark with retries
    def _download_benchmark_with_retry() -> Tuple[str, pd.Series]:
        for attempt in range(3):
            for cand in NIFTY_TICKERS:
                try:
                    df_b = yf.download(cand, start=start, end=end, interval='1d', auto_adjust=True, progress=False)
                    if df_b is not None and not df_b.empty:
                        if 'Close' in df_b.columns:
                            series = df_b['Close'].copy()
                        elif 'Adj Close' in df_b.columns:
                            series = df_b['Adj Close'].copy()
                        else:
                            series = pd.Series(dtype=float)
                        if series.dropna().shape[0] >= 30:
                            return cand, series
                except Exception:
                    continue
            # simple backoff
            import time
            time.sleep(1.5 * (attempt + 1))
        return None, pd.Series(dtype=float)

    benchmark_symbol, nifty_series = _download_benchmark_with_retry()
    if benchmark_symbol is None:
        st.warning("Benchmark (NIFTY50) could not be downloaded. Retrying failed; proceeding without correlation.")
    # If benchmark has too few points, discard to avoid correlation errors
    if not nifty_series.empty and nifty_series.dropna().shape[0] < 30:
        st.warning("Benchmark data insufficient (<30 points); correlation metrics skipped.")
        nifty_series = pd.Series(dtype=float)

    collected: Dict[str, pd.Series] = {}
    # Include benchmark series as a column too, if available
    if not nifty_series.empty:
        collected['NIFTY50_INDEX'] = nifty_series.copy()
    for t in unique:
        try:
            data = yf.download(t, start=start, end=end, interval='1d', auto_adjust=True, progress=False)
            if data is None or getattr(data, 'empty', True):
                st.warning(f"Skipping empty ticker: {t}")
                continue
            # Normalize columns: yfinance sometimes returns multi-index if list passed (we pass single, but be safe)
            if isinstance(data.columns, pd.MultiIndex):
                # attempt to locate ('Close', t) pattern
                if ('Close', t) in data.columns:
                    close_series = data[('Close', t)]
                elif ('Adj Close', t) in data.columns:
                    close_series = data[('Adj Close', t)]
                else:
                    # fallback first level filter
                    lvl0 = [c for c in data.columns if c[0] in ('Close', 'Adj Close')]
                    if lvl0:
                        close_series = data[lvl0[0]]
                    else:
                        st.warning(f"No close price in multi-index for {t}; skipped")
                        continue
            else:
                # Standard single-ticker DataFrame
                if 'Close' in data.columns:
                    close_series = data['Close']
                elif 'Adj Close' in data.columns:
                    close_series = data['Adj Close']
                else:
                    st.warning(f"Skipping ticker without close price: {t}")
                    continue
            # If still a DataFrame, squeeze
            if isinstance(close_series, pd.DataFrame):
                if close_series.shape[1] == 1:
                    close_series = close_series.iloc[:,0]
                else:
                    # take first column as fallback
                    close_series = close_series.iloc[:,0]
            # Final type check
            if not isinstance(close_series, pd.Series):
                st.warning(f"Unexpected close data structure for {t}; skipped")
                continue
            non_na = close_series.dropna()
            if non_na.shape[0] < 2:
                st.warning(f"Insufficient data points for {t}; skipped")
                continue
            # Ensure it's truly a 1D Series with proper name
            if isinstance(close_series, pd.Series):
                close_series = close_series.squeeze()
                close_series.name = t
                collected[t] = close_series
            else:
                st.warning(f"Failed to convert {t} to Series; skipped")
                continue
        except Exception as ex:
            st.warning(f"Error downloading {t}; skipped. ({ex})")
    # Build price DataFrame
    if collected:
        # Use pd.concat to handle Series properly
        price_df = pd.concat(collected, axis=1)
        if isinstance(price_df.columns, pd.MultiIndex):
            price_df.columns = price_df.columns.get_level_values(-1)
    else:
        price_df = pd.DataFrame()
    # Align with benchmark index
    if not nifty_series.empty:
        price_df = price_df.reindex(nifty_series.index)
    return price_df, nifty_series

# ----------------------------------------------------------------------------------
# 3. Compute Performance Metrics (Selective by Tab)
# ----------------------------------------------------------------------------------

def _compute_cagr(series: pd.Series, years: float) -> float:
    if series.empty or series.isna().all():
        return np.nan
    start_val = series.iloc[0]
    end_val = series.iloc[-1]
    if start_val <= 0:
        return np.nan
    return (end_val / start_val) ** (1 / years) - 1


def _max_drawdown(series: pd.Series) -> float:
    if series.empty:
        return np.nan
    roll_max = series.cummax()
    drawdown = series / roll_max - 1.0
    return drawdown.min()  # negative number


def calculate_metrics(price_df: pd.DataFrame, nifty_series: pd.Series, 
                     metrics_subset: Optional[List[str]] = None) -> pd.DataFrame:
    """Calculate metrics for each stock column.
    
    Args:
        price_df: Stock price DataFrame
        nifty_series: Benchmark series
        metrics_subset: List of metrics to compute. If None, compute all.
                       Options: 'return_1y', 'cagr_5y', 'annual_vol', 'sharpe', 
                               'max_drawdown', 'corr_nifty', 'mom_3m', 'mom_6m'

    Metrics:
      - 1-year return (absolute)
      - 5-year CAGR (uses last ~5 years; if shorter, uses available length)
      - Annualized volatility (std daily * sqrt(252))
      - Sharpe ratio ((annualized_return - rf)/vol)
      - Max drawdown (most negative percentage)
      - Correlation with NIFTY50 (daily returns)
      - 3-month momentum (return over ~63 trading days)
      - 6-month momentum (return over ~126 trading days)

    Returns metrics_df.
    """
    if price_df.empty:
        return pd.DataFrame()
    
    # If no subset specified, calculate all
    if metrics_subset is None:
        metrics_subset = ['return_1y', 'cagr_5y', 'annual_vol', 'sharpe', 
                         'max_drawdown', 'corr_nifty', 'mom_3m', 'mom_6m']

    # Determine windows
    total_days = len(price_df)
    one_year_days = min(252, total_days - 1)
    three_month_days = min(63, total_days - 1)
    six_month_days = min(126, total_days - 1)

    # 5-year slice (approx 5*252 = 1260 trading days)
    five_year_days = min(1260, total_days - 1)

    metrics = []

    # Daily returns for stocks
    daily_returns = price_df.pct_change().dropna()
    nifty_returns = nifty_series.pct_change().dropna() if not nifty_series.empty else pd.Series(dtype=float)

    for col in price_df.columns:
        series = price_df[col].dropna()
        if series.empty:
            continue

        metric_dict = {'ticker': col}
        
        # 1-year return
        if 'return_1y' in metrics_subset:
            one_year_slice = series.iloc[-one_year_days:] if one_year_days > 0 else series
            one_year_ret = one_year_slice.iloc[-1] / one_year_slice.iloc[0] - 1 if len(one_year_slice) > 1 else np.nan
            metric_dict['return_1y'] = one_year_ret

        # 5-year CAGR
        if 'cagr_5y' in metrics_subset:
            five_year_slice = series.iloc[-five_year_days:] if five_year_days > 0 else series
            years_span = five_year_days / 252 if five_year_days > 0 else np.nan
            cagr_5y = _compute_cagr(five_year_slice, years_span) if years_span and years_span > 0 else np.nan
            metric_dict['cagr_5y'] = cagr_5y

        # Annualized volatility & return
        if 'annual_vol' in metrics_subset or 'sharpe' in metrics_subset:
            dr = daily_returns[col].dropna() if col in daily_returns else pd.Series(dtype=float)
            if 'annual_vol' in metrics_subset:
                ann_vol = dr.std() * sqrt(252) if not dr.empty else np.nan
                metric_dict['annual_vol'] = ann_vol
            if 'sharpe' in metrics_subset:
                ann_vol = dr.std() * sqrt(252) if not dr.empty else np.nan
                ann_ret = dr.mean() * 252 if not dr.empty else np.nan
                sharpe = (ann_ret - RISK_FREE_RATE) / ann_vol if ann_vol and ann_vol > 0 else np.nan
                metric_dict['sharpe'] = sharpe

        # Max drawdown
        if 'max_drawdown' in metrics_subset:
            mdd = _max_drawdown(series)
            metric_dict['max_drawdown'] = mdd

        # Correlation with NIFTY
        if 'corr_nifty' in metrics_subset:
            if not nifty_returns.empty and col in daily_returns.columns:
                stock_ret = daily_returns[col].dropna()
                bench_ret = nifty_returns.dropna()
                common_index = stock_ret.index.intersection(bench_ret.index)
                if common_index.shape[0] >= 30:
                    try:
                        corr_nifty = stock_ret.loc[common_index].corr(bench_ret.loc[common_index])
                    except Exception:
                        corr_nifty = np.nan
                else:
                    corr_nifty = np.nan
            else:
                corr_nifty = np.nan
            metric_dict['corr_nifty'] = corr_nifty

        # Momentum windows
        if 'mom_3m' in metrics_subset:
            three_month_slice = series.iloc[-three_month_days:] if three_month_days > 0 else series
            mom_3m = three_month_slice.iloc[-1] / three_month_slice.iloc[0] - 1 if len(three_month_slice) > 1 else np.nan
            metric_dict['mom_3m'] = mom_3m
            
        if 'mom_6m' in metrics_subset:
            six_month_slice = series.iloc[-six_month_days:] if six_month_days > 0 else series
            mom_6m = six_month_slice.iloc[-1] / six_month_slice.iloc[0] - 1 if len(six_month_slice) > 1 else np.nan
            metric_dict['mom_6m'] = mom_6m

        metrics.append(metric_dict)

    metrics_df = pd.DataFrame(metrics).set_index('ticker')
    return metrics_df

# ----------------------------------------------------------------------------------
# 4. Tab-Specific Metric Requirements
# ----------------------------------------------------------------------------------

def get_required_metrics(tab_key: str) -> List[str]:
    """Return list of metrics required for each tab type."""
    requirements = {
        'consistent': ['cagr_5y', 'sharpe', 'annual_vol', 'max_drawdown'],
        'low_risk': ['annual_vol', 'max_drawdown'],
        'high_growth': ['return_1y', 'cagr_5y'],
        'momentum': ['mom_3m', 'mom_6m']
    }
    # Always include correlation for notes generation
    base = requirements.get(tab_key, [])
    if 'corr_nifty' not in base:
        base.append('corr_nifty')
    return base

def compute_tab_metrics(tab_key: str, price_df: pd.DataFrame, 
                       nifty_series: pd.Series) -> pd.DataFrame:
    """Compute only the metrics needed for a specific tab."""
    required = get_required_metrics(tab_key)
    metrics_df = calculate_metrics(price_df, nifty_series, metrics_subset=required)
    return metrics_df

# ----------------------------------------------------------------------------------
# 5. Ranking Systems
# ----------------------------------------------------------------------------------

def _normalize(series: pd.Series) -> pd.Series:
    s = series.copy()
    if s.isna().all():
        return pd.Series([0] * len(s), index=s.index)
    min_v = s.min()
    max_v = s.max()
    if max_v - min_v == 0:
        return pd.Series([0.5] * len(s), index=s.index)
    return (s - min_v) / (max_v - min_v)


def rank_consistent_performers(metrics_df: pd.DataFrame) -> pd.DataFrame:
    if metrics_df.empty:
        return metrics_df
    # Inverse metrics: volatility, max_drawdown (drawdown is negative number; invert absolute)
    inv_vol = 1 - _normalize(metrics_df['annual_vol'])
    inv_dd = 1 - _normalize(metrics_df['max_drawdown'].abs())
    score = (
        _normalize(metrics_df['cagr_5y']) * 0.40 +
        _normalize(metrics_df['sharpe']) * 0.30 +
        inv_vol * 0.20 +
        inv_dd * 0.10
    )
    ranked = metrics_df.copy()
    ranked['score_consistent'] = score
    return ranked.sort_values('score_consistent', ascending=False)


def rank_low_risk(metrics_df: pd.DataFrame) -> pd.DataFrame:
    if metrics_df.empty:
        return metrics_df
    inv_vol = 1 - _normalize(metrics_df['annual_vol'])
    inv_dd = 1 - _normalize(metrics_df['max_drawdown'].abs())
    score = inv_vol * 0.60 + inv_dd * 0.40
    ranked = metrics_df.copy()
    ranked['score_low_risk'] = score
    return ranked.sort_values('score_low_risk', ascending=False)


def rank_high_growth(metrics_df: pd.DataFrame) -> pd.DataFrame:
    if metrics_df.empty:
        return metrics_df
    score = _normalize(metrics_df['return_1y']) * 0.50 + _normalize(metrics_df['cagr_5y']) * 0.50
    ranked = metrics_df.copy()
    ranked['score_high_growth'] = score
    return ranked.sort_values('score_high_growth', ascending=False)


def rank_momentum(metrics_df: pd.DataFrame) -> pd.DataFrame:
    if metrics_df.empty:
        return metrics_df
    score = _normalize(metrics_df['mom_3m']) * 0.50 + _normalize(metrics_df['mom_6m']) * 0.50
    ranked = metrics_df.copy()
    ranked['score_momentum'] = score
    return ranked.sort_values('score_momentum', ascending=False)

# ----------------------------------------------------------------------------------
# 6. Notes + Suggested Actions (Rule-Based)
# ----------------------------------------------------------------------------------

def generate_notes_and_actions(metrics_df: pd.DataFrame) -> pd.DataFrame:
    if metrics_df.empty:
        return metrics_df
    df = metrics_df.copy()
    notes = []
    actions = []
    for idx, row in df.iterrows():
        n_list = []
        a_list = []
        # CAGR strength (check if column exists)
        if 'cagr_5y' in row and pd.notna(row['cagr_5y']):
            if row['cagr_5y'] > 0.12:
                n_list.append('Strong 5-year CAGR and stable growth potential')
                a_list.append('Suitable for long-term holding')
            elif row['cagr_5y'] > 0.05:
                n_list.append('Moderate long-term growth trajectory')
                a_list.append('Hold and monitor for acceleration')
            else:
                n_list.append('Weak long-term growth performance')
                a_list.append('Review fundamentals before adding')
        # Volatility
        if 'annual_vol' in row and pd.notna(row['annual_vol']):
            if row['annual_vol'] > 0.40:
                n_list.append('Highly volatile compared to peers')
                a_list.append('High risk; diversify before adding')
            elif row['annual_vol'] < 0.20:
                n_list.append('Low volatility profile')
                a_list.append('Candidate for core allocation')
        # Sharpe
        if 'sharpe' in row and pd.notna(row['sharpe']):
            if row['sharpe'] > 1.0:
                n_list.append('Excellent risk-adjusted return')
            elif row['sharpe'] < 0:
                n_list.append('Negative risk-adjusted performance')
                a_list.append('Re-evaluate position; potential underperformer')
        # Momentum
        if 'mom_3m' in row and 'mom_6m' in row and pd.notna(row['mom_3m']) and pd.notna(row['mom_6m']):
            if row['mom_3m'] < 0 and row['mom_6m'] < 0:
                n_list.append('Momentum declining over last 6 months')
                a_list.append('Avoid short-term momentum play')
            elif row['mom_3m'] > 0 and row['mom_6m'] > 0:
                n_list.append('Positive short and medium-term momentum')
                a_list.append('Good for momentum-based strategies')
        # Drawdown
        if 'max_drawdown' in row and pd.notna(row['max_drawdown']):
            if row['max_drawdown'] < -0.50:
                n_list.append('Severe historical drawdowns observed')
                a_list.append('Limit position size due to risk')
        # Correlation
        if 'corr_nifty' in row and pd.notna(row['corr_nifty']):
            if row['corr_nifty'] > 0.80:
                n_list.append('Highly correlated with benchmark')
            elif row['corr_nifty'] < 0.30:
                n_list.append('Low correlation offering diversification')
        notes.append('; '.join(n_list))
        actions.append('; '.join(dict.fromkeys(a_list)))
    df['notes'] = notes
    df['recommended_actions'] = actions
    return df

# ----------------------------------------------------------------------------------
# 7. Category-Level Summaries
# ----------------------------------------------------------------------------------

def generate_section_summary(df: pd.DataFrame, category_name: str) -> str:
    if df.empty:
        return f"No data available for {category_name}."
    lines = []
    lines.append(f"Count: {len(df)} stocks")
    if category_name == 'Consistent Performers':
        if 'cagr_5y' in df.columns:
            lines.append(f"Average 5-year CAGR: {df['cagr_5y'].mean():.2%}")
        if 'sharpe' in df.columns:
            lines.append(f"Median Sharpe: {df['sharpe'].median():.2f}")
        if 'annual_vol' in df.columns:
            lines.append(f"Average volatility: {df['annual_vol'].mean():.2%}")
        if 'max_drawdown' in df.columns:
            lines.append(f"Average max drawdown: {df['max_drawdown'].mean():.2%}")
        lines.append("Emphasizes sustained growth with balanced risk-adjusted returns.")
    elif category_name == 'Low Risk Stocks':
        if 'annual_vol' in df.columns:
            lines.append(f"Average volatility: {df['annual_vol'].mean():.2%}")
        if 'max_drawdown' in df.columns:
            lines.append(f"Average max drawdown: {df['max_drawdown'].mean():.2%}")
        if 'sharpe' in df.columns:
            lines.append(f"Median Sharpe: {df['sharpe'].median():.2f}")
        lines.append("Capital preservation with stability-focused allocations.")
    elif category_name == 'High Growth Stocks':
        if 'return_1y' in df.columns:
            lines.append(f"Average 1-year return: {df['return_1y'].mean():.2%}")
        if 'cagr_5y' in df.columns:
            lines.append(f"Average 5-year CAGR: {df['cagr_5y'].mean():.2%}")
        if 'sharpe' in df.columns:
            lines.append(f"Median Sharpe: {df['sharpe'].median():.2f}")
        lines.append("Focus on appreciation potential and growth acceleration.")
    elif category_name == 'Top Momentum Stocks':
        if 'mom_3m' in df.columns:
            lines.append(f"Avg 3M momentum: {df['mom_3m'].mean():.2%}")
        if 'mom_6m' in df.columns:
            lines.append(f"Avg 6M momentum: {df['mom_6m'].mean():.2%}")
        if 'sharpe' in df.columns:
            lines.append(f"Median Sharpe: {df['sharpe'].median():.2f}")
        lines.append("Short-term tactical opportunities based on momentum signals.")
    return ' \n'.join(lines)

# ----------------------------------------------------------------------------------
# 8. Excel Export
# ----------------------------------------------------------------------------------

def create_excel_file(rankings_dict: Dict[str, pd.DataFrame]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Map symbols to company names for readability
        _, symbol_to_name = get_symbols_list()
        for name, df in rankings_dict.items():
            if df.empty:
                pd.DataFrame({'Message': ['No data']}).to_excel(writer, sheet_name=name[:30])
                continue
            # Prepare DataFrame with Company Name column
            export_df = df.copy()
            # Robustly create Ticker column from index if missing
            if 'Ticker' not in export_df.columns:
                tmp = export_df.reset_index()
                if 'index' in tmp.columns and 'Ticker' not in tmp.columns:
                    tmp = tmp.rename(columns={'index': 'Ticker'})
                if 'Ticker' not in tmp.columns:
                    tmp.insert(0, 'Ticker', export_df.index.astype(str))
                export_df = tmp
            # Add Company Name
            export_df['Company'] = export_df['Ticker'].map(symbol_to_name).fillna(export_df['Ticker'])
            # Move Company to front
            cols = export_df.columns.tolist()
            if 'Company' in cols and 'Ticker' in cols:
                cols.remove('Company')
                cols.insert(0, 'Company')
            export_df = export_df[cols]
            export_df.to_excel(writer, sheet_name=name[:30], index=False)
    output.seek(0)
    return output.read()

# ----------------------------------------------------------------------------------
# 9. PDF Export
# ----------------------------------------------------------------------------------

def create_pdf_file(rankings_dict: Dict[str, pd.DataFrame], summaries_dict: Dict[str, str]) -> bytes:
    bio = BytesIO()
    doc = SimpleDocTemplate(
        bio,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=30,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=1, textColor=colors.HexColor('#2F3C7E'))
    section_header = ParagraphStyle('SectionHeader', parent=styles['Heading2'], textColor=colors.HexColor('#2F3C7E'))
    normal = styles['Normal']
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=8,
        leading=9,
        spaceAfter=0,
        wordWrap='CJK',
    )

    # Content width for A4 with margins: 595pt - 60pt = 535pt
    CONTENT_WIDTH = 535

    # Column width presets per category to avoid overflow; sums kept <= CONTENT_WIDTH
    category_columns = {
        # Notes removed per request; include stock ticker prominently
        'Consistent Performers': (
            ['Ticker', 'cagr_5y', 'sharpe', 'annual_vol', 'max_drawdown'],
            [120, 85, 80, 100, 150],
        ),
        'Low Risk Stocks': (
            ['Ticker', 'annual_vol', 'max_drawdown', 'sharpe'],
            [150, 120, 150, 115],
        ),
        'High Growth Stocks': (
            ['Ticker', 'return_1y', 'cagr_5y', 'sharpe'],
            [150, 120, 120, 145],
        ),
        'Top Momentum Stocks': (
            ['Ticker', 'mom_3m', 'mom_6m', 'sharpe'],
            [150, 120, 120, 145],
        ),
    }

    elems: List = []
    elems.append(Paragraph('Stock Screener Report', title_style))
    elems.append(Paragraph(datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), normal))
    elems.append(Spacer(1, 0.2 * inch))

    for name, df in rankings_dict.items():
        elems.append(Paragraph(name, section_header))
        elems.append(Spacer(1, 0.12 * inch))
        if df.empty:
            elems.append(Paragraph('No data available.', normal))
            elems.append(Spacer(1, 0.2 * inch))
            continue

        # Use only Top 10
        df_top = df.head(10).copy()

        # Determine columns and widths for this category
        wanted_cols, col_widths = category_columns.get(
            name,
            (['Ticker', 'sharpe', 'notes'], [100, 70, CONTENT_WIDTH - 170]),
        )

        # Remove any score columns and reset index to bring ticker as a column
        clean_df = df_top.copy()
        drop_scores = [c for c in ['score_consistent', 'score_low_risk', 'score_high_growth', 'score_momentum'] if c in clean_df.columns]
        if drop_scores:
            clean_df = clean_df.drop(columns=drop_scores)
        # Bring index (tickers) into a 'Ticker' column robustly
        if 'Ticker' not in clean_df.columns:
            # If resetting index yields a generic 'index' column, rename to Ticker
            tmp = clean_df.reset_index()
            if 'index' in tmp.columns and 'Ticker' not in tmp.columns:
                tmp = tmp.rename(columns={'index': 'Ticker'})
            # If still no Ticker, derive from original index values
            if 'Ticker' not in tmp.columns:
                tmp.insert(0, 'Ticker', clean_df.index.astype(str))
            clean_df = tmp
        # Replace Ticker with Company Name where available
        _, symbol_to_name = get_symbols_list()
        clean_df['Company'] = clean_df['Ticker'].map(symbol_to_name).fillna(clean_df['Ticker'])
        # Prefer Company over Ticker for display
        if 'Company' in wanted_cols or 'Ticker' in wanted_cols:
            # If Ticker requested, swap to Company label
            wanted_cols = ['Company' if c == 'Ticker' else c for c in wanted_cols]

        # Ensure all wanted columns exist, some categories may have missing metrics depending on subset
        available_cols = [c for c in wanted_cols if c in clean_df.columns]
        # Build display DataFrame in order
        table_df = clean_df[available_cols].copy()

        # Format numeric columns
        percent_cols = ['return_1y', 'cagr_5y', 'annual_vol', 'max_drawdown', 'mom_3m', 'mom_6m']
        float_cols = ['sharpe', 'corr_nifty']
        for c in table_df.columns:
            if c in percent_cols:
                table_df[c] = table_df[c].apply(lambda x: f"{x:.2%}" if pd.notna(x) else 'N/A')
            elif c in float_cols:
                table_df[c] = table_df[c].apply(lambda x: f"{x:.2f}" if pd.notna(x) else 'N/A')
            # textual columns left as-is

        # Convert text-like cells to Paragraph for wrapping
        def to_cell(val):
            if pd.isna(val):
                return Paragraph('N/A', cell_style)
            sval = str(val)
            return Paragraph(sval, cell_style)

        # Header
        header = [Paragraph(str(h), ParagraphStyle('Header', parent=styles['Normal'], fontSize=9, textColor=colors.whitesmoke)) for h in table_df.columns.tolist()]

        # Rows
        rows = []
        for _, r in table_df.iterrows():
            row_cells = []
            for col in table_df.columns:
                if col in ['Company']:
                    row_cells.append(to_cell(r[col]))
                else:
                    row_cells.append(str(r[col]))
            rows.append(row_cells)

        data = [header] + rows

        # Adjust col widths to present columns; map widths by wanted_cols order
        # Build a map from col name to width
        width_map = {k: w for k, w in zip(wanted_cols, col_widths)}
        # Fallback uniform width if not mapped
        effective_widths = [width_map.get(col, max(50, CONTENT_WIDTH // max(1, len(table_df.columns)))) for col in table_df.columns]

        tbl = Table(data, repeatRows=1, colWidths=effective_widths)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2F3C7E')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ]))
        elems.append(tbl)
        elems.append(Spacer(1, 0.08 * inch))

        # Section summary (wrapped) — already enriched elsewhere
        summary_text = summaries_dict.get(name, '')
        elems.append(Paragraph('<b>Section Summary</b>', normal))
        for line in summary_text.split('\n'):
            elems.append(Paragraph(line, cell_style))
        elems.append(Spacer(1, 0.25 * inch))

    doc.build(elems)
    bio.seek(0)
    return bio.read()

# ----------------------------------------------------------------------------------
# 8. Streamlit UI Page
# ----------------------------------------------------------------------------------

def render_stock_screener_ui():
    # Compact page styling to reduce white space
    st.markdown(
        """
        <style>
        .block-container{padding-top:0.75rem;padding-bottom:0.75rem;}
        .stTabs [data-baseweb="tab"]{padding-top:6px;padding-bottom:6px;}
        .stMarkdown{margin-top:0.25rem;margin-bottom:0.25rem;}
        .stButton>button{margin-top:0.25rem;margin-bottom:0.25rem;}
        .stColumn{padding-top:0.25rem;padding-bottom:0.25rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("### Stock Screener")
    st.caption("Multi-factor ranking across performance, risk, growth, and momentum.")

    # Check if local data exists
    data_exists = check_data_exists()
    
    if data_exists:
        # Load cached data instantly
        price_df, nifty_series, timestamp = load_price_data()
        st.success(f"✅ Data loaded from cache. Last updated: {timestamp}")
    else:
        # First time: download and save
        st.info("No cached data yet. Downloading once (few minutes)...")
        with st.spinner("Downloading stock data..."):
            try:
                available_symbols = get_available_symbols()
            except Exception:
                available_symbols = []
            
            if not available_symbols:
                st.error("Could not fetch symbols. Please check connection.")
                return
            
            price_df, nifty_series = download_price_data(available_symbols)
            save_price_data(price_df, nifty_series)
            st.success("Data downloaded and cached successfully!")
            st.rerun()

    # Tab-based lazy loading
    tab_configs = [
        ('consistent', 'Consistent Performers'),
        ('low_risk', 'Low Risk Stocks'),
        ('high_growth', 'High Growth Stocks'),
        ('momentum', 'Top Momentum Stocks')
    ]
    
    tabs = st.tabs([name for _, name in tab_configs])
    
    for tab, (tab_key, tab_name) in zip(tabs, tab_configs):
        with tab:
            # Try to load cached metrics for this tab
            metrics_df = load_tab_metrics(tab_key)
            
            if metrics_df is None:
                # Compute metrics for this tab only
                with st.spinner(f"Computing {tab_name.lower()} metrics..."):
                    metrics_df = compute_tab_metrics(tab_key, price_df, nifty_series)
                    metrics_df = generate_notes_and_actions(metrics_df)
                    save_tab_metrics(tab_key, metrics_df)
            
            if metrics_df.empty:
                st.warning("No metrics available for this category.")
                continue
            
            # Exclude index from rankings if present
            mdf_for_rank = metrics_df.drop(index=['NIFTY50_INDEX'], errors='ignore')
            
            # Rank based on tab type
            if tab_key == 'consistent':
                ranked_df = rank_consistent_performers(mdf_for_rank)
            elif tab_key == 'low_risk':
                ranked_df = rank_low_risk(mdf_for_rank)
            elif tab_key == 'high_growth':
                ranked_df = rank_high_growth(mdf_for_rank)
            else:  # momentum
                ranked_df = rank_momentum(mdf_for_rank)
            
            # Display Top 10 results (slider removed per request)
            st.markdown(f"#### {tab_name} (Top 10)")
            display_df = ranked_df.head(10)
            st.dataframe(display_df, use_container_width=True, height=350)
            
            # Summary
            summary = generate_section_summary(ranked_df, tab_name)
            st.markdown("**Summary**")
            for line in summary.split('\n'):
                st.write(line)

    # Downloads section
    st.markdown("---")
    st.markdown("#### Export Reports")
    
    col_pdf, col_xl = st.columns(2)
    
    # Load all metrics for export
    all_metrics = {}
    for tab_key, tab_name in tab_configs:
        metrics = load_tab_metrics(tab_key)
        if metrics is not None:
            all_metrics[tab_name] = metrics
    
    if all_metrics:
        # Prepare rankings dict for export
        rankings_dict = {}
        for tab_key, tab_name in tab_configs:
            if tab_name in all_metrics:
                mdf = all_metrics[tab_name].drop(index=['NIFTY50_INDEX'], errors='ignore')
                if tab_key == 'consistent':
                    rankings_dict[tab_name] = rank_consistent_performers(mdf)
                elif tab_key == 'low_risk':
                    rankings_dict[tab_name] = rank_low_risk(mdf)
                elif tab_key == 'high_growth':
                    rankings_dict[tab_name] = rank_high_growth(mdf)
                else:
                    rankings_dict[tab_name] = rank_momentum(mdf)
        
        summaries_dict = {name: generate_section_summary(df, name) for name, df in rankings_dict.items()}
        
        with col_pdf:
            pdf_bytes = create_pdf_file(rankings_dict, summaries_dict)
            st.download_button(
                label="📄 Download PDF Report",
                data=pdf_bytes,
                file_name="stock_screener_report.pdf",
                mime="application/pdf"
            )
        with col_xl:
            excel_bytes = create_excel_file(rankings_dict)
            st.download_button(
                label="📊 Download Excel Report",
                data=excel_bytes,
                file_name="stock_screener_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.info("Navigate through tabs to compute metrics before exporting.")

# ----------------------------------------------------------------------------------
# Formula Explanation (docstring helper)
# ----------------------------------------------------------------------------------
FORMULA_EXPLANATION = """
Return 1Y: P_t / P_{t-252} - 1
CAGR 5Y: (P_end / P_start)^(1/years) - 1
Annualized Volatility: std(daily_returns) * sqrt(252)
Sharpe Ratio: (Annualized Return - 0.06) / Annualized Volatility
Max Drawdown: min(Price / RollingPeak - 1)
Momentum X: P_t / P_{t-Xdays} - 1 (X in {63,126})
Correlation: Pearson correlation of daily returns vs NIFTY benchmark
"""
