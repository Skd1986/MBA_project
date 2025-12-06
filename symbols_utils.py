"""
Utility functions for fetching, saving, and loading stock symbols dynamically.
"""
import json
import os
from typing import List, Dict, Optional, Tuple
import pandas as pd
import requests
from datetime import datetime

SYMBOLS_FILE = "symbols.json"

def fetch_nse_symbols() -> List[Dict[str, str]]:
    """
    Fetch the list of NSE stock symbols from Yahoo Finance.
    
    Returns a list of dictionaries with 'symbol' and 'name' keys.
    Falls back to a comprehensive list if live fetch fails.
    """
    symbols_data = []
    
    try:
        # Try to fetch from NSE India website using their public API
        # Note: NSE's API structure may change; this uses a known endpoint
        url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20500"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        # Create a session to handle cookies
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if 'data' in data:
            for item in data['data']:
                symbol = item.get('symbol', '')
                company_name = item.get('meta', {}).get('companyName', item.get('symbol', ''))
                if symbol:
                    symbols_data.append({
                        'symbol': f"{symbol}.NS",
                        'name': company_name
                    })
        
        if symbols_data:
            return sorted(symbols_data, key=lambda x: x['symbol'])
            
    except Exception as e:
        print(f"Failed to fetch from NSE API: {e}")
    
    # Fallback: Use a comprehensive static list of popular NSE stocks
    fallback_symbols = [
        ('RELIANCE.NS', 'Reliance Industries Ltd'),
        ('TCS.NS', 'Tata Consultancy Services Ltd'),
        ('INFY.NS', 'Infosys Ltd'),
        ('HDFCBANK.NS', 'HDFC Bank Ltd'),
        ('ICICIBANK.NS', 'ICICI Bank Ltd'),
        ('LT.NS', 'Larsen & Toubro Ltd'),
        ('SBIN.NS', 'State Bank of India'),
        ('BHARTIARTL.NS', 'Bharti Airtel Ltd'),
        ('ITC.NS', 'ITC Ltd'),
        ('KOTAKBANK.NS', 'Kotak Mahindra Bank Ltd'),
        ('ASIANPAINT.NS', 'Asian Paints Ltd'),
        ('HINDUNILVR.NS', 'Hindustan Unilever Ltd'),
        ('SUNPHARMA.NS', 'Sun Pharmaceutical Industries Ltd'),
        ('TITAN.NS', 'Titan Company Ltd'),
        ('ULTRACEMCO.NS', 'UltraTech Cement Ltd'),
        ('NESTLEIND.NS', 'Nestle India Ltd'),
        ('BAJFINANCE.NS', 'Bajaj Finance Ltd'),
        ('WIPRO.NS', 'Wipro Ltd'),
        ('MARUTI.NS', 'Maruti Suzuki India Ltd'),
        ('HCLTECH.NS', 'HCL Technologies Ltd'),
        ('AXISBANK.NS', 'Axis Bank Ltd'),
        ('ADANIPORTS.NS', 'Adani Ports and Special Economic Zone Ltd'),
        ('TATAMOTORS.NS', 'Tata Motors Ltd'),
        ('NTPC.NS', 'NTPC Ltd'),
        ('POWERGRID.NS', 'Power Grid Corporation of India Ltd'),
        ('ONGC.NS', 'Oil and Natural Gas Corporation Ltd'),
        ('COALINDIA.NS', 'Coal India Ltd'),
        ('M&M.NS', 'Mahindra & Mahindra Ltd'),
        ('TECHM.NS', 'Tech Mahindra Ltd'),
        ('BAJAJFINSV.NS', 'Bajaj Finserv Ltd'),
        ('DRREDDY.NS', 'Dr. Reddy\'s Laboratories Ltd'),
        ('DIVISLAB.NS', 'Divi\'s Laboratories Ltd'),
        ('CIPLA.NS', 'Cipla Ltd'),
        ('EICHERMOT.NS', 'Eicher Motors Ltd'),
        ('HEROMOTOCO.NS', 'Hero MotoCorp Ltd'),
        ('APOLLOHOSP.NS', 'Apollo Hospitals Enterprise Ltd'),
        ('BRITANNIA.NS', 'Britannia Industries Ltd'),
        ('JSWSTEEL.NS', 'JSW Steel Ltd'),
        ('TATASTEEL.NS', 'Tata Steel Ltd'),
        ('HINDALCO.NS', 'Hindalco Industries Ltd'),
        ('INDUSINDBK.NS', 'IndusInd Bank Ltd'),
        ('GRASIM.NS', 'Grasim Industries Ltd'),
        ('BPCL.NS', 'Bharat Petroleum Corporation Ltd'),
        ('IOC.NS', 'Indian Oil Corporation Ltd'),
        ('ADANIENT.NS', 'Adani Enterprises Ltd'),
        ('BAJAJ-AUTO.NS', 'Bajaj Auto Ltd'),
        ('TATACONSUM.NS', 'Tata Consumer Products Ltd'),
        ('SHREECEM.NS', 'Shree Cement Ltd'),
        ('SBILIFE.NS', 'SBI Life Insurance Company Ltd'),
        ('HDFCLIFE.NS', 'HDFC Life Insurance Company Ltd'),
    ]
    
    return [{'symbol': sym, 'name': name} for sym, name in sorted(fallback_symbols)]


def save_symbols_to_json(symbols_data: List[Dict[str, str]], filepath: str = SYMBOLS_FILE) -> bool:
    """
    Save the symbols list to a JSON file.
    
    Args:
        symbols_data: List of dictionaries with 'symbol' and 'name' keys
        filepath: Path to the JSON file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        data = {
            'last_updated': datetime.now().isoformat(),
            'symbols': symbols_data
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving symbols to JSON: {e}")
        return False


def load_symbols_from_json(filepath: str = SYMBOLS_FILE) -> Optional[List[Dict[str, str]]]:
    """
    Load symbols from a JSON file.
    
    Args:
        filepath: Path to the JSON file
        
    Returns:
        List of dictionaries with 'symbol' and 'name' keys, or None if file doesn't exist
    """
    if not os.path.exists(filepath):
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('symbols', [])
    except Exception as e:
        print(f"Error loading symbols from JSON: {e}")
        return None


def get_symbols_list() -> Tuple[List[str], Dict[str, str]]:
    """
    Get the list of available stock symbols.
    
    First tries to load from symbols.json. If that fails, fetches from live source
    and saves to JSON.
    
    Returns:
        Tuple of (symbol_list, symbol_to_name_dict)
        - symbol_list: Sorted list of symbol strings (e.g., ['RELIANCE.NS', 'TCS.NS'])
        - symbol_to_name_dict: Dictionary mapping symbols to company names
    """
    symbols_data = load_symbols_from_json()
    
    # If no local file exists, fetch from live source
    if symbols_data is None:
        symbols_data = fetch_nse_symbols()
        save_symbols_to_json(symbols_data)
    
    # Extract symbol list and create mapping
    symbol_list = [item['symbol'] for item in symbols_data]
    symbol_to_name = {item['symbol']: item['name'] for item in symbols_data}
    
    return sorted(symbol_list), symbol_to_name


def format_symbol_with_name(symbol: str, symbol_to_name: Dict[str, str]) -> str:
    """
    Format a symbol with its company name for display.
    
    Args:
        symbol: Stock symbol (e.g., 'RELIANCE.NS')
        symbol_to_name: Dictionary mapping symbols to company names
        
    Returns:
        Formatted string like "RELIANCE.NS - Reliance Industries Ltd"
    """
    name = symbol_to_name.get(symbol, '')
    if name:
        return f"{symbol} - {name}"
    return symbol


def refresh_symbols() -> Tuple[bool, str]:
    """
    Refresh symbols by fetching from live source and saving to JSON.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        symbols_data = fetch_nse_symbols()
        
        if not symbols_data:
            return False, "Failed to fetch symbols from live source"
        
        success = save_symbols_to_json(symbols_data)
        
        if success:
            return True, f"Stock symbols updated successfully! ({len(symbols_data)} symbols loaded)"
        else:
            return False, "Failed to save symbols to file"
            
    except Exception as e:
        return False, f"Error refreshing symbols: {str(e)}"
