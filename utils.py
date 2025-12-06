import os
import json
import datetime
from typing import Dict, List, Optional, Tuple
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import io
from math import sqrt
from symbols_utils import get_symbols_list

PORTFOLIOS_FILE = "portfolios.json"

# --- Stock Symbols (loaded dynamically) ---
def get_available_symbols() -> List[str]:
    """Get the list of available stock symbols (cached in session state)."""
    if 'available_symbols' not in st.session_state:
        symbols_list, symbol_to_name = get_symbols_list()
        st.session_state.available_symbols = symbols_list
        st.session_state.symbol_to_name = symbol_to_name
    return st.session_state.available_symbols

# --- Navigation helpers ---
def navigate(page_name: str) -> None:
    """Update the session state to navigate to a different page."""
    st.session_state.page = page_name

# --- Weight calculation ---
def compute_equal_weights(selected_symbols: List[str]) -> Dict[str, float]:
    """Return a dict mapping each symbol to an equal weight summing approximately to 100."""
    n = len(selected_symbols)
    if n == 0:
        return {}
    base = round(100.0 / n, 2)
    weights = {s: base for s in selected_symbols}
    diff = round(100.0 - sum(weights.values()), 2)
    if abs(diff) >= 0.01:
        first = selected_symbols[0]
        weights[first] = round(weights[first] + diff, 2)
    return weights

# --- Weight update handlers ---
def on_slider_change(sym: str, prefix: str = "") -> None:
    """Handle slider value changes and update other UI elements.

    prefix: optional namespace for keys (e.g., 'edit_')
    """
    slider_key = f"{prefix}slider_{sym}"
    input_key = f"{prefix}input_{sym}"
    weight_key = f"{prefix}weight_{sym}"
    slider_value = st.session_state.get(slider_key, 0.0)
    st.session_state[input_key] = slider_value
    st.session_state[weight_key] = float(round(slider_value, 4))
    # Update canonical stores
    if prefix == "":
        if 'pf_weights' not in st.session_state:
            st.session_state.pf_weights = {}
        st.session_state.pf_weights[sym] = float(round(slider_value, 4))
    else:
        if 'edit_weights' not in st.session_state:
            st.session_state.edit_weights = {}
        st.session_state.edit_weights[sym] = float(round(slider_value, 4))

def on_input_change(sym: str, prefix: str = "") -> None:
    """Handle number input changes and update other UI elements.

    prefix: optional namespace for keys (e.g., 'edit_')
    """
    input_key = f"{prefix}input_{sym}"
    slider_key = f"{prefix}slider_{sym}"
    weight_key = f"{prefix}weight_{sym}"
    input_value = st.session_state.get(input_key, 0.0)
    st.session_state[slider_key] = input_value
    st.session_state[weight_key] = float(round(input_value, 4))
    if prefix == "":
        if 'pf_weights' not in st.session_state:
            st.session_state.pf_weights = {}
        st.session_state.pf_weights[sym] = float(round(input_value, 4))
    else:
        if 'edit_weights' not in st.session_state:
            st.session_state.edit_weights = {}
        st.session_state.edit_weights[sym] = float(round(input_value, 4))

# --- Portfolio file operations ---
def load_portfolios() -> List[Dict]:
    """Load portfolios from the JSON file."""
    out_file = os.path.join(os.getcwd(), PORTFOLIOS_FILE)
    try:
        if os.path.exists(out_file):
            with open(out_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    except Exception as e:
        st.error(f"Failed to read {PORTFOLIOS_FILE}: {e}")
        return []

def save_portfolios(portfolios: List[Dict]) -> bool:
    """Save portfolios to the JSON file. Returns True if successful."""
    out_file = os.path.join(os.getcwd(), PORTFOLIOS_FILE)
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(portfolios, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Failed to save to {PORTFOLIOS_FILE}: {e}")
        return False

def create_portfolio(name: str, holdings: Dict[str, float]) -> Dict:
    """Create a new portfolio dictionary with the given name and holdings."""
    return {
        "name": name,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "holdings": {sym: float(round(w, 4)) for sym, w in holdings.items()}
    }

# --- Portfolio management helpers ---
def update_portfolio_name(portfolios: List[Dict], old_name: str, new_name: str) -> bool:
    """Update a portfolio's name in the list. Returns True if successful."""
    for p in portfolios:
        if p.get('name') == old_name:
            p['name'] = new_name
            return save_portfolios(portfolios)
    return False

def update_portfolio_holdings(portfolios: List[Dict], name: str, holdings: Dict[str, float]) -> bool:
    """Update a portfolio's holdings in the list. Returns True if successful."""
    for p in portfolios:
        if p.get('name') == name:
            p['holdings'] = {s: float(round(w, 4)) for s, w in holdings.items()}
            return save_portfolios(portfolios)
    return False

def delete_portfolio(portfolios: List[Dict], name: str) -> bool:
    """Delete a portfolio from the list. Returns True if successful."""
    updated = [p for p in portfolios if p.get('name') != name]
    return save_portfolios(updated)

# --- Session state helpers ---
def init_session_state() -> None:
    """Initialize required session state variables if not present."""
    if "page" not in st.session_state:
        st.session_state.page = "home"
    if "pf_weights" not in st.session_state:
        st.session_state.pf_weights = {}
    if "prev_selected" not in st.session_state:
        st.session_state.prev_selected = []

def init_weight_widgets(selected_symbols: List[str], weights: Dict[str, float], prefix: str = "") -> None:
    """Initialize weight-related widgets in session state.

    prefix: optional namespace to set keys for edit mode (e.g., 'edit_')
    This will create keys: f"{prefix}slider_{sym}", f"{prefix}input_{sym}", f"{prefix}weight_{sym}".
    If prefix is empty, also keeps `st.session_state.pf_weights` in sync.
    """
    for sym in selected_symbols:
        slider_key = f"{prefix}slider_{sym}"
        input_key = f"{prefix}input_{sym}"
        weight_key = f"{prefix}weight_{sym}"
        if slider_key not in st.session_state and input_key not in st.session_state:
            initial_weight = float(weights.get(sym, 0.0))
            st.session_state[slider_key] = initial_weight
            st.session_state[input_key] = initial_weight
            st.session_state[weight_key] = float(round(initial_weight, 4))
            if prefix == "":
                if 'pf_weights' not in st.session_state:
                    st.session_state.pf_weights = {}
                st.session_state.pf_weights[sym] = float(round(initial_weight, 4))

def get_weights_from_session(selected_symbols: List[str], prefix: str = "") -> Dict[str, float]:
    """Collect current weights from session_state for the given symbols.

    If prefix is 'edit_' the function reads from st.session_state.edit_weights.
    Otherwise it reads from st.session_state.pf_weights.
    """
    if prefix == "":
        return {s: float(st.session_state.pf_weights.get(s, 0.0)) for s in selected_symbols}
    else:
        ew = st.session_state.get('edit_weights', {})
        return {s: float(ew.get(s, 0.0)) for s in selected_symbols}


# --------------------- Analytics helpers ---------------------
@st.cache_data(ttl=3600)
def fetch_price_data(tickers: List[str]) -> pd.DataFrame:
    """Fetch 5 years of daily adjusted close prices for given tickers using yfinance.

    Downloads historical data from January 2020 to present (or most recent available).
    Returns DataFrame indexed by date with columns for each ticker. Missing tickers are dropped.
    """
    if not tickers:
        return pd.DataFrame()
    # Ensure unique and remove empty
    ticks = sorted(list({t for t in tickers if t}))
    
    # Fetch 5 years of data (2020-01-01 to today)
    start_date = "2020-01-01"
    end_date = datetime.datetime.today().strftime("%Y-%m-%d")
    
    try:
        df = yf.download(ticks, start=start_date, end=end_date, interval='1d', auto_adjust=True, threads=True)
    except Exception:
        # fallback single-thread
        df = yf.download(ticks, start=start_date, end=end_date, interval='1d', auto_adjust=True)

    # yf returns a DataFrame with columns like ('Close', ticker) when multiple; normalize
    if isinstance(df.columns, pd.MultiIndex):
        if 'Close' in df.columns.levels[0]:
            price = df['Close'].copy()
        else:
            # fallback to last level
            price = df.xs('Close', axis=1, level=0, drop_level=False)
    else:
        # single ticker returns Series
        price = df['Close'] if 'Close' in df.columns else df

    # Ensure DataFrame and drop columns fully NA
    price = pd.DataFrame(price)
    price.dropna(axis=1, how='all', inplace=True)
    # Rename columns to simple tickers if needed
    price.columns = [str(c) for c in price.columns]
    return price


def calc_portfolio_returns(holdings: Dict[str, float], price_df: pd.DataFrame) -> pd.Series:
    """Calculate daily portfolio returns series for holdings dict (weights in percent).

    holdings: {'TICKER': weight_percent}
    price_df: DataFrame of prices indexed by date with columns tickers
    Returns: pd.Series of daily returns
    """
    if price_df.empty:
        return pd.Series(dtype=float)
    weights = {s: w / 100.0 for s, w in holdings.items()}
    # intersect available tickers
    avail = [c for c in price_df.columns if c in weights]
    if not avail:
        return pd.Series(dtype=float)
    rets = price_df[avail].pct_change().dropna()
    w_arr = np.array([weights[c] for c in avail])
    # weighted returns
    port_ret = rets.values.dot(w_arr)
    return pd.Series(port_ret, index=rets.index)


def compute_metrics_from_returns(returns: pd.Series) -> Dict[str, float]:
    """Compute annualized return, cumulative return, annualized volatility, and Sharpe ratio.

    Assumes daily returns and 252 trading days.
    """
    if returns.empty:
        return {"annual_return": np.nan, "cumulative_return": np.nan, "annual_vol": np.nan, "sharpe": np.nan}
    n = returns.shape[0]
    cumulative = (1 + returns).prod() - 1
    # annualized return
    annual_return = (1 + cumulative) ** (252.0 / n) - 1 if n > 0 else np.nan
    annual_vol = returns.std(ddof=0) * sqrt(252)
    sharpe = annual_return / annual_vol if annual_vol and not np.isnan(annual_vol) and annual_vol != 0 else np.nan
    return {"annual_return": float(annual_return), "cumulative_return": float(cumulative), "annual_vol": float(annual_vol), "sharpe": float(sharpe)}


def build_portfolios_summary(portfolios: List[Dict], price_df: pd.DataFrame, market_ticker: str = 'NIFTY50.NS') -> Tuple[pd.DataFrame, Dict[str, pd.Series]]:
    """Return a summary DataFrame and dict of cumulative return series per portfolio and market.

    summary columns: name, n_stocks, annual_return, cumulative_return, annual_vol, sharpe
    series_dict contains cumulative return series (1+cumprod -1) for plotting.
    """
    rows = []
    series = {}
    # market series
    if market_ticker in price_df.columns:
        market_rets = price_df[market_ticker].pct_change().dropna()
        market_cum = (1 + market_rets).cumprod() - 1
        series['Market'] = market_cum
    for p in portfolios:
        name = p.get('name', 'Unnamed')
        holdings = p.get('holdings', {}) if isinstance(p.get('holdings', {}), dict) else {}
        nstocks = len(holdings)
        port_ret = calc_portfolio_returns(holdings, price_df)
        metrics = compute_metrics_from_returns(port_ret)
        rows.append({
            'name': name,
            'n_stocks': nstocks,
            'annual_return': metrics['annual_return'],
            'cumulative_return': metrics['cumulative_return'],
            'annual_vol': metrics['annual_vol'],
            'sharpe': metrics['sharpe']
        })
        if not port_ret.empty:
            series[name] = (1 + port_ret).cumprod() - 1
        else:
            series[name] = pd.Series(dtype=float)
    df = pd.DataFrame(rows)
    # format percentages maybe later in UI
    return df, series


def generate_portfolio_analysis_sections(comp_df: pd.DataFrame,
                                         pearson_corr: pd.DataFrame,
                                         cov_matrix: pd.DataFrame,
                                         portfolios: List[Dict] = None,
                                         price_df: pd.DataFrame = None) -> Dict[str, str]:
    """Generate intelligent Findings, Suggestions and Conclusion text for selected portfolios.
    
    Automatically adapts analysis based on number of portfolios:
    - Single portfolio: Compare against NIFTY50 benchmark
    - Multiple portfolios: Compare among portfolios and include NIFTY50 as reference
    
    Parameters
    ----------
    comp_df : pd.DataFrame
        Comparison summary DataFrame (name, n_stocks, annual_return, cumulative_return, annual_vol, sharpe)
    pearson_corr : pd.DataFrame
        Correlation matrix between selected portfolios
    cov_matrix : pd.DataFrame
        Covariance matrix for stocks involved in the compared portfolios
    portfolios : List[Dict], optional
        List of portfolio objects with holdings
    price_df : pd.DataFrame, optional
        Price DataFrame to compute stock-level annual returns
        
    Returns
    -------
    Dict[str, str]
        Dictionary with keys: 'findings', 'suggestions', 'conclusion'
    """
    findings_parts = []
    suggestions_parts = []
    conclusion_parts = []
    
    # Separate user portfolios from NIFTY50 benchmark
    user_comp = comp_df[comp_df['name'] != 'NIFTY50'].copy()
    nifty50_row = comp_df[comp_df['name'] == 'NIFTY50']
    
    if user_comp.empty:
        return {
            "findings": "No user portfolios selected for analysis.",
            "suggestions": "Create and select at least one portfolio to generate insights.",
            "conclusion": "Select portfolios to view comparative analysis."
        }
    
    # Determine analysis mode
    num_portfolios = len(user_comp)
    is_single_portfolio = (num_portfolios == 1)
    
    # Get NIFTY50 metrics for comparison (if available)
    has_nifty50 = not nifty50_row.empty
    nifty50_return = nifty50_row.iloc[0]['annual_return'] * 100 if has_nifty50 and 'annual_return' in nifty50_row.columns else None
    nifty50_vol = nifty50_row.iloc[0]['annual_vol'] * 100 if has_nifty50 and 'annual_vol' in nifty50_row.columns else None
    nifty50_sharpe = nifty50_row.iloc[0]['sharpe'] if has_nifty50 and 'sharpe' in nifty50_row.columns else None
    
    # --- FINDINGS ---
    if is_single_portfolio:
        # SINGLE PORTFOLIO ANALYSIS - Compare against NIFTY50
        portfolio_name = user_comp.iloc[0]['name']
        portfolio_return = user_comp.iloc[0]['annual_return'] * 100 if 'annual_return' in user_comp.columns else None
        portfolio_vol = user_comp.iloc[0]['annual_vol'] * 100 if 'annual_vol' in user_comp.columns else None
        portfolio_sharpe = user_comp.iloc[0]['sharpe'] if 'sharpe' in user_comp.columns else None
        portfolio_stocks = user_comp.iloc[0]['n_stocks'] if 'n_stocks' in user_comp.columns else None
        
        # 1. Return comparison vs NIFTY50
        if portfolio_return is not None and nifty50_return is not None:
            return_diff = portfolio_return - nifty50_return
            if return_diff > 0:
                findings_parts.append(
                    f"**{portfolio_name}** outperformed the NIFTY50 benchmark with an annual return of **{portfolio_return:.2f}%** "
                    f"(vs. NIFTY50's **{nifty50_return:.2f}%**), achieving an **{abs(return_diff):.2f}%** excess return."
                )
            elif return_diff < -5:
                findings_parts.append(
                    f"**{portfolio_name}** underperformed the NIFTY50 benchmark, posting an annual return of **{portfolio_return:.2f}%** "
                    f"compared to NIFTY50's **{nifty50_return:.2f}%**, trailing by **{abs(return_diff):.2f}%**."
                )
            else:
                findings_parts.append(
                    f"**{portfolio_name}** delivered returns of **{portfolio_return:.2f}%**, closely tracking the NIFTY50 benchmark at **{nifty50_return:.2f}%**."
                )
        
        # 2. Risk comparison vs NIFTY50
        if portfolio_vol is not None and nifty50_vol is not None:
            vol_diff = portfolio_vol - nifty50_vol
            if abs(vol_diff) < 3:
                findings_parts.append(
                    f"The portfolio exhibits volatility of **{portfolio_vol:.2f}%**, similar to NIFTY50's **{nifty50_vol:.2f}%**, "
                    f"indicating comparable risk levels."
                )
            elif vol_diff > 5:
                findings_parts.append(
                    f"With volatility at **{portfolio_vol:.2f}%**, the portfolio is **{abs(vol_diff):.2f}%** more volatile than NIFTY50 "
                    f"(**{nifty50_vol:.2f}%**), suggesting higher risk exposure."
                )
            elif vol_diff < -3:
                findings_parts.append(
                    f"The portfolio demonstrates lower volatility at **{portfolio_vol:.2f}%** compared to NIFTY50's **{nifty50_vol:.2f}%**, "
                    f"indicating a more conservative risk profile with **{abs(vol_diff):.2f}%** less volatility."
                )
        
        # 3. Sharpe ratio vs NIFTY50
        if portfolio_sharpe is not None and nifty50_sharpe is not None:
            sharpe_diff = portfolio_sharpe - nifty50_sharpe
            if sharpe_diff > 0.2:
                findings_parts.append(
                    f"**{portfolio_name}** achieves a Sharpe ratio of **{portfolio_sharpe:.2f}**, outperforming NIFTY50's **{nifty50_sharpe:.2f}**, "
                    f"demonstrating superior risk-adjusted returns."
                )
            elif sharpe_diff < -0.2:
                findings_parts.append(
                    f"The portfolio's Sharpe ratio of **{portfolio_sharpe:.2f}** falls short of NIFTY50's **{nifty50_sharpe:.2f}**, "
                    f"indicating suboptimal risk-adjusted performance."
                )
            else:
                findings_parts.append(
                    f"The portfolio's Sharpe ratio of **{portfolio_sharpe:.2f}** is comparable to NIFTY50's **{nifty50_sharpe:.2f}**."
                )
        
        # 4. Diversification assessment
        if portfolio_stocks is not None:
            if portfolio_stocks < 5:
                findings_parts.append(
                    f"With only **{portfolio_stocks} stocks**, the portfolio exhibits high concentration risk and limited diversification."
                )
            elif portfolio_stocks < 10:
                findings_parts.append(
                    f"The portfolio holds **{portfolio_stocks} stocks**, providing moderate diversification but still susceptible to individual stock volatility."
                )
            else:
                findings_parts.append(
                    f"The portfolio contains **{portfolio_stocks} stocks**, offering good diversification across multiple holdings."
                )
        
        # 5. Stock-level performance
        if portfolios and price_df is not None and not price_df.empty:
            stock_returns = {}
            for p in portfolios:
                if p.get('name', '') == portfolio_name:
                    holdings = p.get('holdings', {}) if isinstance(p.get('holdings', {}), dict) else {}
                    for sym in holdings.keys():
                        if sym in price_df.columns:
                            try:
                                ser = price_df[sym].dropna()
                                if ser.shape[0] >= 2:
                                    ann_ret = (ser.iloc[-1] / ser.iloc[0] - 1.0) * 100.0
                                    stock_returns[sym] = ann_ret
                            except Exception:
                                pass
            if stock_returns:
                best_stock = max(stock_returns, key=stock_returns.get)
                worst_stock = min(stock_returns, key=stock_returns.get)
                best_ret = stock_returns[best_stock]
                worst_ret = stock_returns[worst_stock]
                findings_parts.append(
                    f"Within the portfolio, **{best_stock}** was the top performer with **{best_ret:.2f}%** returns, "
                    f"while **{worst_stock}** lagged at **{worst_ret:.2f}%**."
                )
    
    else:
        # MULTIPLE PORTFOLIOS ANALYSIS - Compare among portfolios
        # 1. Performance leaders
        if 'annual_return' in user_comp.columns and not user_comp['annual_return'].isna().all():
            best_idx = user_comp['annual_return'].idxmax()
            worst_idx = user_comp['annual_return'].idxmin()
            best_name = user_comp.loc[best_idx, 'name']
            best_ret = user_comp.loc[best_idx, 'annual_return'] * 100
            worst_name = user_comp.loc[worst_idx, 'name']
            worst_ret = user_comp.loc[worst_idx, 'annual_return'] * 100
            
            findings_parts.append(
                f"Among the selected portfolios, **{best_name}** achieved the highest annual return of **{best_ret:.2f}%**, "
                f"while **{worst_name}** posted the lowest return at **{worst_ret:.2f}%**."
            )
            
            # Compare best to NIFTY50
            if nifty50_return is not None:
                if best_ret > nifty50_return:
                    findings_parts.append(
                        f"**{best_name}** outperformed the NIFTY50 benchmark (**{nifty50_return:.2f}%**) by **{best_ret - nifty50_return:.2f}%**."
                    )
                else:
                    findings_parts.append(
                        f"Even the top-performing portfolio falls short of NIFTY50's **{nifty50_return:.2f}%** return."
                    )
        
        # 2. Risk (volatility) comparison
        if 'annual_vol' in user_comp.columns and not user_comp['annual_vol'].isna().all():
            low_vol_idx = user_comp['annual_vol'].idxmin()
            high_vol_idx = user_comp['annual_vol'].idxmax()
            low_vol_name = user_comp.loc[low_vol_idx, 'name']
            low_vol_val = user_comp.loc[low_vol_idx, 'annual_vol'] * 100
            high_vol_name = user_comp.loc[high_vol_idx, 'name']
            high_vol_val = user_comp.loc[high_vol_idx, 'annual_vol'] * 100
            findings_parts.append(
                f"**{low_vol_name}** exhibits the lowest volatility at **{low_vol_val:.2f}%**, "
                f"whereas **{high_vol_name}** shows higher volatility at **{high_vol_val:.2f}%**, "
                f"indicating a **{high_vol_val - low_vol_val:.2f}%** risk spread between portfolios."
            )
        
        # 3. Sharpe ratio (risk-adjusted performance)
        if 'sharpe' in user_comp.columns and not user_comp['sharpe'].isna().all():
            best_sharpe_idx = user_comp['sharpe'].idxmax()
            best_sharpe_name = user_comp.loc[best_sharpe_idx, 'name']
            best_sharpe_val = user_comp.loc[best_sharpe_idx, 'sharpe']
            findings_parts.append(
                f"**{best_sharpe_name}** demonstrates the best risk-adjusted performance with a Sharpe ratio of **{best_sharpe_val:.2f}**, "
                f"indicating superior returns per unit of risk among the compared portfolios."
            )
        
        # 4. Correlation insights (portfolio diversification)
        if not pearson_corr.empty and pearson_corr.shape[0] >= 2:
            corr_vals = []
            names = list(pearson_corr.index)
            for i in range(len(names)):
                for j in range(i+1, len(names)):
                    if names[i] != 'NIFTY50' and names[j] != 'NIFTY50':  # Exclude NIFTY50 pairs
                        corr_vals.append((names[i], names[j], pearson_corr.iloc[i, j]))
            if corr_vals:
                corr_vals_sorted = sorted(corr_vals, key=lambda x: abs(x[2]), reverse=True)
                top_corr = corr_vals_sorted[0]
                avg_corr = np.mean([abs(c[2]) for c in corr_vals])
                
                if abs(top_corr[2]) > 0.7:
                    findings_parts.append(
                        f"**{top_corr[0]}** and **{top_corr[1]}** exhibit high correlation (**{top_corr[2]:.2f}**), "
                        f"suggesting limited diversification benefits between these portfolios."
                    )
                elif abs(top_corr[2]) < 0.3:
                    findings_parts.append(
                        f"**{top_corr[0]}** and **{top_corr[1]}** show low correlation (**{top_corr[2]:.2f}**), "
                        f"indicating strong diversification potential when combined."
                    )
                
                findings_parts.append(
                    f"The average correlation across portfolios is **{avg_corr:.2f}**, "
                    f"{'indicating moderate diversification opportunities' if avg_corr < 0.6 else 'suggesting similar risk exposures'}."
                )
    
    # 5. Stock-level performance (if available)
    if portfolios and price_df is not None and not price_df.empty:
        stock_returns = {}
        for p in portfolios:
            if p.get('name', '') == 'NIFTY50':
                continue
            holdings = p.get('holdings', {}) if isinstance(p.get('holdings', {}), dict) else {}
            for sym in holdings.keys():
                if sym in price_df.columns and sym not in stock_returns:
                    try:
                        ser = price_df[sym].dropna()
                        if ser.shape[0] >= 2:
                            ann_ret = (ser.iloc[-1] / ser.iloc[0] - 1.0) * 100.0
                            stock_returns[sym] = ann_ret
                    except Exception:
                        pass
        if stock_returns:
            best_stock = max(stock_returns, key=stock_returns.get)
            best_stock_ret = stock_returns[best_stock]
            findings_parts.append(
                f"At the stock level, **{best_stock}** delivered the highest annual return of **{best_stock_ret:.2f}%**."
            )
    
    findings = " ".join(findings_parts) if findings_parts else "Insufficient data to generate detailed findings."
    
    # --- SUGGESTIONS ---
    if is_single_portfolio:
        # SINGLE PORTFOLIO SUGGESTIONS - Focus on improving vs NIFTY50
        portfolio_name = user_comp.iloc[0]['name']
        portfolio_return = user_comp.iloc[0]['annual_return'] * 100 if 'annual_return' in user_comp.columns else None
        portfolio_vol = user_comp.iloc[0]['annual_vol'] * 100 if 'annual_vol' in user_comp.columns else None
        portfolio_sharpe = user_comp.iloc[0]['sharpe'] if 'sharpe' in user_comp.columns else None
        portfolio_stocks = user_comp.iloc[0]['n_stocks'] if 'n_stocks' in user_comp.columns else None
        
        # 1. Performance improvement
        if portfolio_return is not None and nifty50_return is not None:
            if portfolio_return < nifty50_return:
                gap = nifty50_return - portfolio_return
                suggestions_parts.append(
                    f"To close the **{gap:.2f}%** performance gap with NIFTY50, consider rotating into higher-growth sectors "
                    f"such as Technology, Banking, or Consumer Discretionary."
                )
            else:
                suggestions_parts.append(
                    f"The portfolio is outperforming NIFTY50. Maintain current allocation while monitoring for sector concentration risks."
                )
        
        # 2. Diversification enhancement
        if portfolio_stocks is not None:
            if portfolio_stocks < 5:
                suggestions_parts.append(
                    f"Increase diversification by adding **5-10 more stocks** across different sectors to reduce concentration risk. "
                    f"Target sectors like Healthcare, IT, Energy, and FMCG for better balance."
                )
            elif portfolio_stocks < 10:
                suggestions_parts.append(
                    f"Consider adding **3-5 more stocks** from uncorrelated sectors to further diversify and stabilize returns."
                )
            else:
                suggestions_parts.append(
                    f"Current diversification level is adequate. Focus on periodic rebalancing to maintain target weights."
                )
        
        # 3. Risk management
        if portfolio_vol is not None and nifty50_vol is not None:
            if portfolio_vol > nifty50_vol + 5:
                suggestions_parts.append(
                    f"Portfolio volatility is significantly higher than NIFTY50. Add defensive stocks from sectors like FMCG, Pharma, "
                    f"and Utilities to reduce volatility. Consider including blue-chip stocks with stable earnings."
                )
            elif portfolio_vol < nifty50_vol - 3:
                suggestions_parts.append(
                    f"Lower volatility indicates conservative positioning. If higher returns are desired, gradually increase allocation "
                    f"to growth stocks while maintaining risk tolerance."
                )
        
        # 4. Stock-level rebalancing
        if portfolios and price_df is not None and not price_df.empty:
            stock_returns = {}
            for p in portfolios:
                if p.get('name', '') == portfolio_name:
                    holdings = p.get('holdings', {}) if isinstance(p.get('holdings', {}), dict) else {}
                    for sym, weight in holdings.items():
                        if sym in price_df.columns:
                            try:
                                ser = price_df[sym].dropna()
                                if ser.shape[0] >= 2:
                                    ann_ret = (ser.iloc[-1] / ser.iloc[0] - 1.0) * 100.0
                                    stock_returns[sym] = (ann_ret, float(weight))
                            except Exception:
                                pass
            if stock_returns and len(stock_returns) >= 3:
                sorted_stocks = sorted(stock_returns.items(), key=lambda x: x[1][0], reverse=True)
                top_performer = sorted_stocks[0]
                bottom_performer = sorted_stocks[-1]
                
                if bottom_performer[1][0] < 0:  # Negative return
                    suggestions_parts.append(
                        f"**{bottom_performer[0]}** posted negative returns of **{bottom_performer[1][0]:.2f}%**. "
                        f"Consider reducing its weight (currently **{bottom_performer[1][1]:.1f}%**) and reallocating to better performers."
                    )
                
                if top_performer[1][0] > 30:  # Strong performer
                    suggestions_parts.append(
                        f"**{top_performer[0]}** delivered exceptional returns of **{top_performer[1][0]:.2f}%**. "
                        f"Consider taking partial profits if weight has grown beyond target allocation to maintain balance."
                    )
        
        # 5. Sharpe ratio improvement
        if portfolio_sharpe is not None and nifty50_sharpe is not None:
            if portfolio_sharpe < nifty50_sharpe:
                suggestions_parts.append(
                    f"Improve risk-adjusted returns by focusing on stocks with strong fundamentals and lower volatility. "
                    f"Consider quality stocks with consistent earnings growth and stable dividend payouts."
                )
    
    else:
        # MULTIPLE PORTFOLIOS SUGGESTIONS - Compare and optimize allocation
        # 1. Allocation recommendations
        if 'sharpe' in user_comp.columns and not user_comp['sharpe'].isna().all():
            best_sharpe_idx = user_comp['sharpe'].idxmax()
            best_sharpe_name = user_comp.loc[best_sharpe_idx, 'name']
            best_sharpe_val = user_comp.loc[best_sharpe_idx, 'sharpe']
            
            worst_sharpe_idx = user_comp['sharpe'].idxmin()
            worst_sharpe_name = user_comp.loc[worst_sharpe_idx, 'name']
            
            suggestions_parts.append(
                f"Prioritize allocation to **{best_sharpe_name}** (Sharpe: **{best_sharpe_val:.2f}**) for optimal risk-adjusted returns. "
                f"Consider reducing exposure to **{worst_sharpe_name}** or rebalancing its holdings to improve performance."
            )
        
        # 2. Diversification across portfolios
        if not pearson_corr.empty and pearson_corr.shape[0] >= 2:
            corr_vals = []
            names = list(pearson_corr.index)
            for i in range(len(names)):
                for j in range(i+1, len(names)):
                    if names[i] != 'NIFTY50' and names[j] != 'NIFTY50':
                        corr_vals.append((names[i], names[j], pearson_corr.iloc[i, j]))
            if corr_vals:
                avg_corr = np.mean([abs(c[2]) for c in corr_vals])
                if avg_corr > 0.6:
                    suggestions_parts.append(
                        f"Average portfolio correlation is **{avg_corr:.2f}**, indicating overlapping holdings. "
                        f"Enhance diversification by including low-correlated sectors such as IT, Pharma, FMCG, or Metals across different portfolios."
                    )
                elif avg_corr < 0.3:
                    suggestions_parts.append(
                        f"Excellent diversification with average correlation of **{avg_corr:.2f}**. "
                        f"Consider combining portfolios for a well-balanced multi-strategy approach."
                    )
        
        # 3. Volatility management across portfolios
        if 'annual_vol' in user_comp.columns and not user_comp['annual_vol'].isna().all():
            high_vol_idx = user_comp['annual_vol'].idxmax()
            high_vol_name = user_comp.loc[high_vol_idx, 'name']
            high_vol_val = user_comp.loc[high_vol_idx, 'annual_vol'] * 100
            
            low_vol_idx = user_comp['annual_vol'].idxmin()
            low_vol_name = user_comp.loc[low_vol_idx, 'name']
            
            if high_vol_val > 25.0:
                suggestions_parts.append(
                    f"**{high_vol_name}** shows elevated volatility (**{high_vol_val:.2f}%**). "
                    f"Balance overall portfolio risk by increasing allocation to lower-volatility **{low_vol_name}** "
                    f"or adding defensive stocks to the high-volatility portfolio."
                )
        
        # 4. Performance-based rebalancing
        if 'annual_return' in user_comp.columns:
            best_ret_idx = user_comp['annual_return'].idxmax()
            worst_ret_idx = user_comp['annual_return'].idxmin()
            best_ret_name = user_comp.loc[best_ret_idx, 'name']
            worst_ret_name = user_comp.loc[worst_ret_idx, 'name']
            worst_ret_val = user_comp.loc[worst_ret_idx, 'annual_return'] * 100
            
            if worst_ret_val < 0:
                suggestions_parts.append(
                    f"**{worst_ret_name}** posted negative returns. Consider restructuring this portfolio by "
                    f"adopting successful strategies from **{best_ret_name}**, or reduce its allocation in favor of better-performing portfolios."
                )
        
        # 5. Combined stock-level insights
        if portfolios and price_df is not None and not price_df.empty:
            stock_returns = {}
            for p in portfolios:
                if p.get('name', '') == 'NIFTY50':
                    continue
                holdings = p.get('holdings', {}) if isinstance(p.get('holdings', {}), dict) else {}
                for sym in holdings.keys():
                    if sym in price_df.columns and sym not in stock_returns:
                        try:
                            ser = price_df[sym].dropna()
                            if ser.shape[0] >= 2:
                                ann_ret = (ser.iloc[-1] / ser.iloc[0] - 1.0) * 100.0
                                stock_returns[sym] = ann_ret
                        except Exception:
                            pass
            if stock_returns and len(stock_returns) >= 5:
                sorted_stocks = sorted(stock_returns.items(), key=lambda x: x[1], reverse=True)
                top_stocks = sorted_stocks[:3]
                bottom_stocks = sorted_stocks[-2:]
                top_names = ', '.join([f"{s[0]} (+{s[1]:.1f}%)" for s in top_stocks])
                bottom_names = ', '.join([f"{s[0]} ({s[1]:.1f}%)" for s in bottom_stocks])
                suggestions_parts.append(
                    f"Across all portfolios, increase exposure to top performers: **{top_names}**. "
                    f"Review and consider reducing weight on underperformers: **{bottom_names}**."
                )
    
    suggestions = " ".join(suggestions_parts) if suggestions_parts else "No specific suggestions available based on current data."
    
    # --- CONCLUSION ---
    if is_single_portfolio:
        # SINGLE PORTFOLIO CONCLUSION
        portfolio_name = user_comp.iloc[0]['name']
        portfolio_return = user_comp.iloc[0]['annual_return'] * 100 if 'annual_return' in user_comp.columns else None
        portfolio_vol = user_comp.iloc[0]['annual_vol'] * 100 if 'annual_vol' in user_comp.columns else None
        portfolio_sharpe = user_comp.iloc[0]['sharpe'] if 'sharpe' in user_comp.columns else None
        portfolio_cum_ret = user_comp.iloc[0]['cumulative_return'] * 100 if 'cumulative_return' in user_comp.columns else None
        
        # 1. Overall performance assessment
        if portfolio_cum_ret is not None:
            if portfolio_cum_ret > 0:
                conclusion_parts.append(
                    f"**{portfolio_name}** delivered a cumulative return of **{portfolio_cum_ret:.2f}%** over the analysis period."
                )
            else:
                conclusion_parts.append(
                    f"**{portfolio_name}** experienced a cumulative loss of **{abs(portfolio_cum_ret):.2f}%** over the analysis period."
                )
        
        # 2. Benchmark comparison summary
        if portfolio_return is not None and nifty50_return is not None and portfolio_sharpe is not None:
            if portfolio_return > nifty50_return and portfolio_sharpe > (nifty50_sharpe or 0):
                conclusion_parts.append(
                    f"The portfolio successfully outperformed NIFTY50 with both higher returns and superior risk-adjusted performance. "
                    f"This indicates effective stock selection and portfolio construction."
                )
            elif portfolio_return > nifty50_return:
                conclusion_parts.append(
                    f"While the portfolio achieved higher returns than NIFTY50, risk-adjusted performance could be improved by "
                    f"optimizing the risk-return tradeoff through better diversification."
                )
            elif portfolio_sharpe > (nifty50_sharpe or 0):
                conclusion_parts.append(
                    f"Despite lower absolute returns than NIFTY50, the portfolio demonstrates better risk-adjusted performance, "
                    f"making it suitable for risk-conscious investors."
                )
            else:
                conclusion_parts.append(
                    f"The portfolio underperformed NIFTY50 on both absolute and risk-adjusted metrics. "
                    f"Significant restructuring is recommended to improve performance."
                )
        
        # 3. Investor suitability
        if portfolio_vol is not None and nifty50_vol is not None:
            if portfolio_vol < nifty50_vol:
                conclusion_parts.append(
                    f"With below-market volatility, **{portfolio_name}** is well-suited for conservative investors prioritizing capital preservation."
                )
            elif portfolio_vol > nifty50_vol * 1.3:
                conclusion_parts.append(
                    f"The portfolio's higher volatility profile makes it appropriate for aggressive investors with higher risk tolerance seeking greater returns."
                )
            else:
                conclusion_parts.append(
                    f"The portfolio's moderate risk profile aligns with balanced investment strategies suitable for most investors."
                )
        
        # 4. Action plan
        if portfolio_return is not None and nifty50_return is not None:
            if portfolio_return < nifty50_return - 3:
                conclusion_parts.append(
                    f"**Immediate action required:** Review holdings, eliminate underperformers, increase diversification, and consider sector rotation to improve returns."
                )
            elif portfolio_return < nifty50_return:
                conclusion_parts.append(
                    f"**Action recommended:** Fine-tune holdings by adding growth stocks and rebalancing weights to close the performance gap with NIFTY50."
                )
            else:
                conclusion_parts.append(
                    f"**Maintain and monitor:** Continue current strategy with quarterly rebalancing, monitor for concentration risks, and gradually take profits from top performers."
                )
        else:
            conclusion_parts.append(
                f"Regularly monitor portfolio performance, rebalance quarterly to maintain target weights, and adjust strategy based on market conditions."
            )
    
    else:
        # MULTIPLE PORTFOLIOS CONCLUSION
        # 1. Overall assessment
        if 'cumulative_return' in user_comp.columns:
            avg_cum_ret = user_comp['cumulative_return'].mean() * 100
            max_cum_ret = user_comp['cumulative_return'].max() * 100
            min_cum_ret = user_comp['cumulative_return'].min() * 100
            
            if avg_cum_ret > 0:
                conclusion_parts.append(
                    f"The selected portfolios collectively show positive performance with an average cumulative return of **{avg_cum_ret:.2f}%** "
                    f"(ranging from **{min_cum_ret:.2f}%** to **{max_cum_ret:.2f}%**) over the analysis period."
                )
            else:
                conclusion_parts.append(
                    f"The portfolios experienced an average cumulative loss of **{abs(avg_cum_ret):.2f}%**, "
                    f"indicating challenging market conditions or suboptimal portfolio construction."
                )
        
        # 2. Best choice recommendation
        if 'sharpe' in user_comp.columns and not user_comp['sharpe'].isna().all():
            best_sharpe_idx = user_comp['sharpe'].idxmax()
            best_sharpe_name = user_comp.loc[best_sharpe_idx, 'name']
            best_sharpe_val = user_comp.loc[best_sharpe_idx, 'sharpe']
            best_return = user_comp.loc[best_sharpe_idx, 'annual_return'] * 100 if 'annual_return' in user_comp.columns else None
            
            conclusion_parts.append(
                f"**{best_sharpe_name}** (Sharpe: **{best_sharpe_val:.2f}**, Return: **{best_return:.2f}%**) emerges as the top choice, "
                f"offering the best balance of risk and return among the compared portfolios."
            )
        
        # 3. Risk profile matching
        if 'annual_vol' in user_comp.columns:
            low_vol_idx = user_comp['annual_vol'].idxmin()
            low_vol_name = user_comp.loc[low_vol_idx, 'name']
            high_vol_idx = user_comp['annual_vol'].idxmax()
            high_vol_name = user_comp.loc[high_vol_idx, 'name']
            
            conclusion_parts.append(
                f"Conservative investors should favor **{low_vol_name}** for stability, "
                f"while aggressive investors may prefer **{high_vol_name}** for higher return potential despite increased volatility."
            )
        
        # 4. Diversification strategy
        if not pearson_corr.empty and pearson_corr.shape[0] >= 2:
            corr_vals = []
            names = list(pearson_corr.index)
            for i in range(len(names)):
                for j in range(i+1, len(names)):
                    if names[i] != 'NIFTY50' and names[j] != 'NIFTY50':
                        corr_vals.append(pearson_corr.iloc[i, j])
            if corr_vals:
                avg_corr = np.mean([abs(c) for c in corr_vals])
                if avg_corr < 0.4:
                    conclusion_parts.append(
                        f"Low average correlation (**{avg_corr:.2f}**) presents an opportunity to combine portfolios for enhanced diversification benefits."
                    )
                elif avg_corr > 0.7:
                    conclusion_parts.append(
                        f"High average correlation (**{avg_corr:.2f}**) limits diversification benefits. Focus on a single well-constructed portfolio rather than spreading across similar strategies."
                    )
        
        # 5. Next steps and action plan
        if 'annual_return' in user_comp.columns and nifty50_return is not None:
            outperformers = user_comp[user_comp['annual_return'] * 100 > nifty50_return]
            underperformers = user_comp[user_comp['annual_return'] * 100 < nifty50_return]
            
            if len(underperformers) > len(outperformers):
                conclusion_parts.append(
                    f"**Action required:** Most portfolios underperformed NIFTY50. Conduct thorough portfolio reviews, "
                    f"restructure holdings, improve diversification, and consider adopting strategies from top-performing portfolios."
                )
            elif len(outperformers) > 0:
                conclusion_parts.append(
                    f"Moving forward, consolidate investments into top-performing portfolios, rebalance underperformers, "
                    f"and maintain disciplined risk management through regular monitoring and quarterly rebalancing."
                )
            else:
                conclusion_parts.append(
                    f"Implement regular portfolio reviews (monthly), systematic rebalancing (quarterly), "
                    f"and consider sector rotation strategies to maintain optimal risk-adjusted returns."
                )
    
    conclusion = " ".join(conclusion_parts) if conclusion_parts else "Review portfolio metrics and adjust allocations based on investment objectives."
    
    return {
        "findings": findings,
        "suggestions": suggestions,
        "conclusion": conclusion
    }


def export_comparison_to_excel_bytes(summary_df: pd.DataFrame, 
                                    series_dict: Dict[str, pd.Series], 
                                    portfolios: List[Dict] = None,
                                    price_df: pd.DataFrame = None,
                                    pearson_corr: pd.DataFrame = None,
                                    cov_matrix: pd.DataFrame = None,
                                    analysis_sections: Dict[str, str] = None) -> bytes:
    """Export comprehensive portfolio comparison to Excel workbook in-memory and return bytes."""
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='openpyxl') as writer:
        # 1. Summary Sheet with metrics
        summary_display = summary_df.copy()
        for col in ['annual_return', 'cumulative_return', 'annual_vol']:
            if col in summary_display.columns:
                summary_display[col] = (summary_display[col] * 100).round(3)
        summary_display['sharpe'] = summary_display['sharpe'].round(3)
        
        # Rename columns for better readability
        summary_display = summary_display.rename(columns={
            'name': 'Portfolio Name',
            'n_stocks': 'Number of Stocks',
            'annual_return': 'Annual Return (%)',
            'cumulative_return': 'Cumulative Return (%)',
            'annual_vol': 'Annual Volatility (%)',
            'sharpe': 'Sharpe Ratio'
        })
        summary_display.to_excel(writer, sheet_name='Summary', index=False)
        
        # 2. Holdings Sheet - detailed composition of each portfolio with annual returns
        if portfolios and price_df is not None:
            holdings_rows = []
            for p in portfolios:
                name = p.get('name', 'Unnamed')
                if name in summary_df['name'].values:  # Only include selected portfolios
                    holdings = p.get('holdings', {})
                    for symbol, weight in holdings.items():
                        ann_ret = 'N/A'
                        try:
                            if symbol in price_df.columns:
                                series = price_df[symbol].dropna()
                                if series.shape[0] >= 2:
                                    ann_ret_val = (series.iloc[-1] / series.iloc[0] - 1.0) * 100.0
                                    ann_ret = round(ann_ret_val, 2)
                        except Exception:
                            ann_ret = 'N/A'
                        holdings_rows.append({
                            'Portfolio': name,
                            'Symbol': symbol,
                            'Weight (%)': round(float(weight), 2),
                            'Annual Return (%)': ann_ret
                        })
            if holdings_rows:
                holdings_df = pd.DataFrame(holdings_rows)
                holdings_df.to_excel(writer, sheet_name='Holdings', index=False)
        
        # 3. Performance Sheet - cumulative returns over time
        performance_df = pd.DataFrame()
        for name, series in series_dict.items():
            if not series.empty:
                series = series * 100  # Convert to percentage
                if performance_df.empty:
                    performance_df = pd.DataFrame({'Date': series.index})
                performance_df[f'{name} (%)'] = series.values.round(2)
        
        if not performance_df.empty:
            performance_df.to_excel(writer, sheet_name='Performance', index=False)
        
        # 4. Stock-Level Covariance Matrix
        if cov_matrix is not None and not cov_matrix.empty:
            cov_matrix.to_excel(writer, sheet_name='Covariance Matrix', index=True)
        
        # 5. Portfolio Pearson Correlation
        if pearson_corr is not None and not pearson_corr.empty:
            pearson_corr.to_excel(writer, sheet_name='Pearson Correlation', index=True)
        
        # 6. Portfolio Insights (Findings, Suggestions, Conclusion)
        if analysis_sections:
            insights_rows = []
            if analysis_sections.get('findings'):
                insights_rows.append({'Section': 'Findings', 'Content': analysis_sections['findings']})
            if analysis_sections.get('suggestions'):
                insights_rows.append({'Section': 'Suggestions', 'Content': analysis_sections['suggestions']})
            if analysis_sections.get('conclusion'):
                insights_rows.append({'Section': 'Conclusion', 'Content': analysis_sections['conclusion']})
            if insights_rows:
                insights_df = pd.DataFrame(insights_rows)
                insights_df.to_excel(writer, sheet_name='Portfolio Insights', index=False)
        
        # 7. Individual Portfolio Sheets
        for name, ser in series_dict.items():
            if ser.empty:
                continue
            # Convert to percentage and create individual sheet
            df = ser.rename(f'{name} (%)').reset_index()
            df.iloc[:, 1] = (df.iloc[:, 1] * 100).round(2)
            df.columns = ['Date', f'{name} Cumulative Return (%)']
            sheet_name = str(name)[:31]  # Excel sheet name length limitation
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    bio.seek(0)
    return bio.read()


def export_comparison_to_pdf_bytes(summary_df: pd.DataFrame,
                                   portfolios: List[Dict],
                                   series_dict: Dict[str, pd.Series],
                                   price_df: pd.DataFrame,
                                   pearson_corr: pd.DataFrame = None,
                                   cov_matrix: pd.DataFrame = None,
                                   analysis_sections: Dict[str, str] = None) -> bytes:
    """Generate a comprehensive PDF report for selected portfolios.

    Sections (in order):
      1. Title + generation date
      2. Comparison summary table (Annual Return %, Cumulative Return %, Annual Volatility %, Sharpe)
      3. Cumulative returns chart (portfolio vs market) as embedded image
      4. Covariance matrix (stocks across selected portfolios)
      5. Pearson correlation matrix (portfolio-level) [skip if <2 portfolios]
      6. Portfolio correlation matrix [skip if <2 portfolios]
      7. Holdings list per portfolio including annual return (%) per stock
      8. Portfolio Insights (Findings, Suggestions, Conclusion)

    Graceful handling of missing/insufficient data; returns bytes suitable for Streamlit download.
    """
    if pearson_corr is None:
        pearson_corr = pd.DataFrame()
    if cov_matrix is None:
        cov_matrix = pd.DataFrame()
    if analysis_sections is None:
        analysis_sections = {}
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                        Spacer, Image, PageBreak)
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        import matplotlib.pyplot as plt  # type: ignore
        no_matplotlib = False
    except Exception:
        # Allow PDF generation without the chart if matplotlib/reportlab sub-import fails
        no_matplotlib = True
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                        Spacer, PageBreak)
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch

    bio = io.BytesIO()
    doc = SimpleDocTemplate(bio, pagesize=letter, rightMargin=30, leftMargin=30,
                            topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elems = []

    # ---------- 1. Title ----------
    elems.append(Paragraph('Portfolio Comparison Report', styles['Title']))
    elems.append(Spacer(1, 0.15 * inch))
    elems.append(Paragraph(f'Generated on: {datetime.datetime.now().strftime("%B %d, %Y")}', styles['Normal']))
    elems.append(Spacer(1, 0.25 * inch))

    # ---------- 2. Summary Table ----------
    elems.append(Paragraph('Comparison Summary', styles['Heading1']))
    elems.append(Spacer(1, 0.12 * inch))
    summary_display = summary_df.copy()
    for col in ['annual_return', 'cumulative_return', 'annual_vol']:
        if col in summary_display.columns:
            summary_display[col] = (summary_display[col] * 100).round(2)
    if 'sharpe' in summary_display.columns:
        summary_display['sharpe'] = summary_display['sharpe'].round(2)
    summary_display = summary_display.rename(columns={
        'name': 'Portfolio',
        'n_stocks': '# Stocks',
        'annual_return': 'Annual<br/>Return (%)',
        'cumulative_return': 'Cumulative<br/>Return (%)',
        'annual_vol': 'Annual<br/>Volatility (%)',
        'sharpe': 'Sharpe'
    })
    headers = list(summary_display.columns)
    # Convert headers to Paragraph objects for text wrapping
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    # Create a copy of Normal style for headers to avoid modifying the original
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        alignment=1,  # Center alignment
        fontSize=8,
        textColor=colors.whitesmoke
    )
    header_paragraphs = [Paragraph(str(h), header_style) for h in headers]
    rows = [header_paragraphs]
    for _, r in summary_display.iterrows():
        formatted = []
        for c in headers:
            v = r[c]
            if c in ('Annual Return (%)', 'Cumulative Return (%)', 'Annual Volatility (%)'):
                formatted.append('N/A' if pd.isna(v) else f"{float(v):.2f}%")
            elif c == 'Sharpe':
                formatted.append('N/A' if pd.isna(v) else f"{float(v):.2f}")
            else:
                formatted.append(str(v))
        rows.append(formatted)
    col_widths = []
    for c in headers:
        if c == 'Portfolio':
            col_widths.append(1.8 * inch)
        elif c == '# Stocks':
            col_widths.append(0.6 * inch)
        else:
            col_widths.append(1.0 * inch)
    summary_tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    summary_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2F3C7E')),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ])
    for i, c in enumerate(headers):
        if c in ('Portfolio'):
            summary_style.add('ALIGN', (i, 0), (i, -1), 'LEFT')
        elif c in ('# Stocks'):
            summary_style.add('ALIGN', (i, 0), (i, -1), 'CENTER')
        else:
            summary_style.add('ALIGN', (i, 0), (i, -1), 'RIGHT')
    summary_tbl.setStyle(summary_style)
    elems.append(summary_tbl)
    elems.append(Spacer(1, 0.25 * inch))

    # ---------- 3. Cumulative Returns Chart ----------
    if no_matplotlib:
        elems.append(Paragraph('Cumulative Returns (Chart unavailable - matplotlib missing)', styles['Heading1']))
        elems.append(Spacer(1, 0.12 * inch))
        elems.append(Paragraph('Install matplotlib to include the chart in the PDF.', styles['Normal']))
        elems.append(Spacer(1, 0.3 * inch))
    else:
        try:
            elems.append(Paragraph('Cumulative Returns (Portfolio vs Market)', styles['Heading1']))
            elems.append(Spacer(1, 0.12 * inch))
            fig, ax = plt.subplots(figsize=(7.2, 4.0), dpi=110)
            plotted = False
            selected_names = [p.get('name', 'Unnamed') for p in portfolios]
            ordered = []
            for n in selected_names:
                if n in series_dict:
                    ordered.append(n)
            if 'NIFTY50' in series_dict and 'NIFTY50' not in ordered:
                ordered.append('NIFTY50')
            for name in ordered:
                s = series_dict.get(name)
                if s is not None and not s.empty:
                    ax.plot(s.index, (s * 100.0), label=name)
                    plotted = True
            if plotted:
                ax.set_ylabel('Cumulative Return (%)')
                ax.set_xlabel('Date')
                ax.grid(alpha=0.3, linestyle='--')
                ax.legend(loc='best', fontsize=8)
                fig.autofmt_xdate()
                img_bio = io.BytesIO()
                plt.tight_layout()
                fig.savefig(img_bio, format='png')
                plt.close(fig)
                img_bio.seek(0)
                elems.append(Image(img_bio, width=6.5 * inch, height=3.6 * inch))
            else:
                elems.append(Paragraph('No cumulative return series available.', styles['Normal']))
            elems.append(Spacer(1, 0.3 * inch))
        except Exception:
            elems.append(Paragraph('Failed to render cumulative returns chart.', styles['Normal']))
            elems.append(Spacer(1, 0.2 * inch))

    # Skip stock-level covariance matrix in PDF (available in Excel export only)

    # ---------- 5. Pearson Correlation Matrix ----------
    elems.append(Paragraph('Portfolio Pearson Correlation', styles['Heading1']))
    elems.append(Spacer(1, 0.12 * inch))
    if pearson_corr.empty:
        elems.append(Paragraph('At least two portfolios required.', styles['Normal']))
    else:
        try:
            pr_headers = [''] + list(pearson_corr.columns)
            pr_rows = [pr_headers]
            for idx in pearson_corr.index:
                pr_rows.append([idx] + [f"{pearson_corr.loc[idx, c]:.4f}" for c in pearson_corr.columns])
            pr_tbl = Table(pr_rows, colWidths=[1.3 * inch] + [0.9 * inch] * len(pearson_corr.columns), repeatRows=1)
            pr_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2F3C7E')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ])
            pr_tbl.setStyle(pr_style)
            elems.append(pr_tbl)
        except Exception:
            elems.append(Paragraph('Failed to render Pearson correlation matrix.', styles['Normal']))
    elems.append(Spacer(1, 0.3 * inch))

    # ---------- 6. Portfolio Correlation Matrix ----------
    elems.append(Paragraph('Portfolio Correlation Matrix', styles['Heading1']))
    elems.append(Spacer(1, 0.12 * inch))
    if pearson_corr.empty:
        elems.append(Paragraph('At least two portfolios required.', styles['Normal']))
    else:
        try:
            # Use pearson_corr as portfolio correlation (they're the same computation)
            pf_headers = [''] + list(pearson_corr.columns)
            pf_rows = [pf_headers]
            for idx in pearson_corr.index:
                pf_rows.append([idx] + [f"{pearson_corr.loc[idx, c]:.4f}" for c in pearson_corr.columns])
            pf_tbl = Table(pf_rows, colWidths=[1.3 * inch] + [0.9 * inch] * len(pearson_corr.columns), repeatRows=1)
            pf_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F628E')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ])
            pf_tbl.setStyle(pf_style)
            elems.append(pf_tbl)
        except Exception:
            elems.append(Paragraph('Failed to render portfolio correlation matrix.', styles['Normal']))
    elems.append(Spacer(1, 0.3 * inch))

    # ---------- 7. Holdings with Annual Return per Stock ----------
    elems.append(Paragraph('Portfolio Holdings (with Annual Return)', styles['Heading1']))
    elems.append(Spacer(1, 0.12 * inch))
    for p in portfolios:
        name = p.get('name', 'Unnamed')
        if name not in summary_df['name'].values:
            continue
        holdings = p.get('holdings', {}) if isinstance(p.get('holdings', {}), dict) else {}
        elems.append(Paragraph(f'Portfolio: {name}', styles['Heading2']))
        if not holdings:
            elems.append(Paragraph('No holdings.', styles['Normal']))
            elems.append(Spacer(1, 0.15 * inch))
            continue
        stock_rows = [['Symbol', 'Weight (%)', 'Annual Return (%)']]
        for sym, w in holdings.items():
            ann = 'N/A'
            try:
                if sym in price_df.columns:
                    series = price_df[sym].dropna()
                    if series.shape[0] >= 2:
                        ann_ret = (series.iloc[-1] / series.iloc[0] - 1.0) * 100.0
                        ann = f"{ann_ret:.2f}%"
            except Exception:
                ann = 'N/A'
            stock_rows.append([sym, f"{float(w):.2f}", ann])
        stock_tbl = Table(stock_rows, colWidths=[1.5 * inch, 1.2 * inch, 1.5 * inch], repeatRows=1)
        stock_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2F3C7E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ])
        stock_tbl.setStyle(stock_style)
        elems.append(stock_tbl)
        elems.append(Spacer(1, 0.25 * inch))

    # ---------- 8. Portfolio Insights (Findings, Suggestions, Conclusion) ----------
    if analysis_sections and any(analysis_sections.values()):
        elems.append(Spacer(1, 0.25 * inch))
        elems.append(Paragraph('Portfolio Insights', styles['Heading1']))
        elems.append(Spacer(1, 0.12 * inch))
        
        def format_markdown_bold(text):
            """Convert markdown **bold** to proper reportlab <b>bold</b> tags."""
            import re
            # Replace **text** with <b>text</b> properly handling pairs
            parts = text.split('**')
            result = []
            for i, part in enumerate(parts):
                if i % 2 == 1:  # odd indices are inside bold markers
                    result.append(f'<b>{part}</b>')
                else:
                    result.append(part)
            return ''.join(result)
        
        # Create custom style for insights text with black color
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_LEFT
        insights_style = ParagraphStyle(
            'InsightsText',
            parent=styles['Normal'],
            textColor=colors.black,
            fontSize=10,
            leading=14,
            leftIndent=20,
            bulletIndent=10,
            alignment=TA_LEFT
        )
        
        def split_into_sentences(text):
            """Split text into sentences, treating each sentence as a bullet point."""
            import re
            # Split on period followed by space and capital letter, or period at end
            sentences = re.split(r'\. (?=[A-Z])', text)
            bullets = []
            for s in sentences:
                s = s.strip()
                if s and not s.endswith('.'):
                    s += '.'
                if s:
                    bullets.append(s)
            return bullets
        
        # Findings
        if analysis_sections.get('findings'):
            elems.append(Paragraph('Findings', styles['Heading2']))
            elems.append(Spacer(1, 0.08 * inch))
            findings_bullets = split_into_sentences(analysis_sections['findings'])
            for bullet in findings_bullets:
                bullet_text = format_markdown_bold(bullet)
                elems.append(Paragraph(f'• {bullet_text}', insights_style))
                elems.append(Spacer(1, 0.05 * inch))
            elems.append(Spacer(1, 0.15 * inch))
        
        # Suggestions
        if analysis_sections.get('suggestions'):
            elems.append(Paragraph('Suggestions', styles['Heading2']))
            elems.append(Spacer(1, 0.08 * inch))
            suggestions_bullets = split_into_sentences(analysis_sections['suggestions'])
            for bullet in suggestions_bullets:
                bullet_text = format_markdown_bold(bullet)
                elems.append(Paragraph(f'• {bullet_text}', insights_style))
                elems.append(Spacer(1, 0.05 * inch))
            elems.append(Spacer(1, 0.15 * inch))
        
        # Conclusion
        if analysis_sections.get('conclusion'):
            elems.append(Paragraph('Conclusion', styles['Heading2']))
            elems.append(Spacer(1, 0.08 * inch))
            conclusion_bullets = split_into_sentences(analysis_sections['conclusion'])
            for bullet in conclusion_bullets:
                bullet_text = format_markdown_bold(bullet)
                elems.append(Paragraph(f'• {bullet_text}', insights_style))
                elems.append(Spacer(1, 0.05 * inch))
            elems.append(Spacer(1, 0.15 * inch))

    # Optional explanatory notes
    elems.append(Paragraph('Notes', styles['Heading2']))
    # Create a style for notes with explicit black text color
    notes_style = ParagraphStyle(
        'NotesStyle',
        parent=styles['Normal'],
        textColor=colors.black,
        fontSize=10,
        leading=12
    )
    for txt in [
        'Annual Return (%) per portfolio is annualized from daily returns.',
        'Cumulative Return (%) is total growth over the fetched 5-year period.',
        'Annual Volatility (%) is the annualized standard deviation of daily returns.',
        'Sharpe uses return divided by annual volatility (risk-free assumed 0).'
    ]:
        elems.append(Paragraph(f'• {txt}', notes_style))
    elems.append(Spacer(1, 0.15 * inch))

    doc.build(elems)
    bio.seek(0)
    return bio.read()