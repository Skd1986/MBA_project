"""Portfolio correlation & covariance utilities.

This module contains pure computation functions (no Streamlit UI) used by the
Run Analytics screen to display covariance and correlation matrices.

Functions:
  - compute_covariance_matrix
  - compute_pearson_correlation
  - compute_portfolio_correlation_matrix

All functions accept pandas objects and return pandas DataFrames with clear
row/column labels. They perform lightweight validation and return an empty
DataFrame when inputs are missing or insufficient.
"""
from typing import Dict, List

import pandas as pd


def compute_covariance_matrix(all_stock_returns_df: pd.DataFrame) -> pd.DataFrame:
    """Compute covariance matrix for all stocks.

    Parameters
    ----------
    all_stock_returns_df : pd.DataFrame
        DataFrame of daily returns for all stocks. Columns should be tickers/symbols
        and rows indexed by date. Values must be numeric (percent or decimal returns).

    Returns
    -------
    pd.DataFrame
        Covariance matrix with row and column labels preserved as strings. If the
        input is empty or not a DataFrame, an empty DataFrame is returned.
    """
    if not isinstance(all_stock_returns_df, pd.DataFrame):
        raise TypeError("Expected a pandas DataFrame for all_stock_returns_df")
    if all_stock_returns_df.empty:
        raise ValueError("Input returns DataFrame is empty")

    # Ensure numeric columns only (drop non-numeric silently)
    numeric_df = all_stock_returns_df.select_dtypes(include=["number"]).copy()
    if numeric_df.empty:
        raise ValueError("No numeric columns found in returns DataFrame")

    cov = numeric_df.cov()

    # Clear, consistent labels
    cov.index = [str(i) for i in cov.index]
    cov.columns = [str(c) for c in cov.columns]
    return cov


def compute_pearson_correlation(portfolio_returns: Dict[str, pd.Series]) -> pd.DataFrame:
    """Compute Pearson correlation matrix for selected portfolios.

    Parameters
    ----------
    portfolio_returns : Dict[str, pd.Series]
        Mapping from portfolio name to its daily returns series (indexed by date).

    Returns
    -------
    pd.DataFrame
        Pearson correlation matrix between portfolios. If fewer than two portfolios
        are provided, returns an empty DataFrame (UI should only call this when
        multiple portfolios are selected).
    """
    if not portfolio_returns or len(portfolio_returns) < 2:
        raise ValueError("At least two portfolio return series are required to compute Pearson correlation")

    # Combine into a DataFrame aligning on index (dates)
    df = pd.concat(portfolio_returns, axis=1)
    # Ensure columns are named by portfolio keys
    df.columns = [str(c) for c in df.columns]

    if df.dropna(how="all").empty:
        raise ValueError("Combined portfolio returns contain no overlapping data")

    corr = df.corr(method="pearson")
    corr.index = [str(i) for i in corr.index]
    corr.columns = [str(c) for c in corr.columns]
    return corr


def compute_portfolio_correlation_matrix(portfolio_returns: Dict[str, pd.Series]) -> pd.DataFrame:
    """Compute correlation coefficients across selected portfolios.

    Parameters
    ----------
    portfolio_returns : Dict[str, pd.Series]
        Mapping from portfolio name to its daily returns series (indexed by date).

    Returns
    -------
    pd.DataFrame
        Correlation matrix across portfolios (labeled). Returns empty DataFrame if
        fewer than two portfolios are supplied or if data is insufficient.
    """
    # Implementation is identical to Pearson correlation for portfolio-level series
    if not portfolio_returns or len(portfolio_returns) < 2:
        raise ValueError("At least two portfolio return series are required to compute portfolio correlation matrix")

    df = pd.concat(portfolio_returns, axis=1)
    df.columns = [str(c) for c in df.columns]

    if df.dropna(how="all").empty:
        raise ValueError("Combined portfolio returns contain no overlapping data")

    corr = df.corr()
    corr.index = [str(i) for i in corr.index]
    corr.columns = [str(c) for c in corr.columns]
    return corr


def compute_asset_pearson_correlation(selected_portfolios: List[Dict], price_df: pd.DataFrame) -> pd.DataFrame:
    """Compute asset-level (stock-level) Pearson correlation for stocks contained in the selected portfolios.

    Parameters
    ----------
    selected_portfolios : List[Dict]
        List of portfolio objects, each having a 'holdings' dict mapping symbol -> weight.
    price_df : pd.DataFrame
        DataFrame of price data (adjusted close) indexed by date with ticker columns.

    Returns
    -------
    pd.DataFrame
        Pearson correlation matrix between individual stock return series. Empty DataFrame if <2 stocks.
    """
    if not isinstance(price_df, pd.DataFrame) or price_df.empty:
        return pd.DataFrame()

    # Collect unique tickers from holdings that exist in price_df
    tickers = set()
    for p in selected_portfolios:
        holdings = p.get('holdings', {}) if isinstance(p.get('holdings', {}), dict) else {}
        for sym in holdings.keys():
            if sym in price_df.columns:
                tickers.add(sym)

    tickers = sorted(list(tickers))
    if len(tickers) < 2:
        return pd.DataFrame()

    returns_df = price_df[tickers].pct_change().dropna()
    if returns_df.empty:
        return pd.DataFrame()

    corr = returns_df.corr(method='pearson')
    corr.index = [str(i) for i in corr.index]
    corr.columns = [str(c) for c in corr.columns]
    return corr
