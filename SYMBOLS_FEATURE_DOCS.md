# Dynamic Stock Symbol Loading - Documentation

## Overview
The application now loads stock symbols dynamically from live data sources instead of using a hardcoded list. This allows for always up-to-date stock listings and supports a much larger universe of stocks.

## Files Modified/Created

### New Files:
1. **`symbols_utils.py`** - Core module for symbol management
2. **`test_symbols.py`** - Test script to verify functionality
3. **`symbols.json`** - Auto-generated cache file (not committed to repo)

### Modified Files:
1. **`utils.py`** - Removed hardcoded NIFTY50_SYMBOLS, added get_available_symbols()
2. **`Analyzeapp.py`** - Updated Create and Edit Portfolio screens with dynamic loading
3. **`requirements.txt`** - Already includes required `requests` library

## Key Features

### 1. Dynamic Symbol Fetching
- Fetches symbols from NSE India API (NIFTY 500 index)
- Falls back to comprehensive static list if API fails
- Returns sorted list for better UX

### 2. Local Caching
- Symbols saved to `symbols.json` with timestamp
- Includes symbol and company name for each stock
- Reduces API calls and improves performance

### 3. User-Triggered Refresh
- "⟳ Refresh Symbols" button in Create Portfolio screen
- Fetches latest symbols and updates cache
- Shows success/error messages
- Automatically reloads UI after refresh

### 4. Error Handling
- Falls back to symbols.json if live fetch fails
- Shows warning if no symbols available
- Provides clear error messages and recovery instructions
- Graceful degradation with fallback list

### 5. Session State Caching
- Symbols cached in Streamlit session state
- Prevents repeated file reads
- Cleared on refresh for immediate updates

## API Functions (symbols_utils.py)

### `fetch_nse_symbols() -> List[Dict[str, str]]`
Fetches stock symbols from NSE India API or returns fallback list.

**Returns:**
```python
[
    {'symbol': 'RELIANCE.NS', 'name': 'Reliance Industries Ltd'},
    {'symbol': 'TCS.NS', 'name': 'Tata Consultancy Services Ltd'},
    ...
]
```

### `save_symbols_to_json(symbols_data, filepath='symbols.json') -> bool`
Saves symbols to JSON file with timestamp.

**Parameters:**
- `symbols_data`: List of dicts with 'symbol' and 'name' keys
- `filepath`: Path to save JSON file

**Returns:** True if successful, False otherwise

### `load_symbols_from_json(filepath='symbols.json') -> Optional[List[Dict[str, str]]]`
Loads symbols from JSON cache file.

**Returns:** List of symbol dicts or None if file doesn't exist

### `get_symbols_list() -> Tuple[List[str], Dict[str, str]]`
Main function to get symbols list. Loads from cache or fetches live.

**Returns:**
```python
(
    ['RELIANCE.NS', 'TCS.NS', ...],  # Sorted symbol list
    {'RELIANCE.NS': 'Reliance Industries Ltd', ...}  # Symbol to name mapping
)
```

### `refresh_symbols() -> Tuple[bool, str]`
Refreshes symbols from live source and updates cache.

**Returns:**
```python
(True, "Stock symbols updated successfully! (50 symbols loaded)")
# or
(False, "Failed to fetch symbols from live source")
```

### `format_symbol_with_name(symbol, symbol_to_name) -> str`
Formats a symbol with company name for display.

**Example:**
```python
format_symbol_with_name('RELIANCE.NS', symbol_to_name)
# Returns: "RELIANCE.NS - Reliance Industries Ltd"
```

## UI Changes

### Create Portfolio Screen
- Added "⟳ Refresh Symbols" button (top right)
- Shows count of available symbols
- Dynamic dropdown populated from symbols.json
- Error handling with user-friendly messages

### Edit Portfolio Screen
- Uses same dynamic symbol list
- Falls back gracefully if symbols unavailable
- Maintains existing portfolio holdings

## Testing

Run the test script to verify functionality:

```powershell
cd "c:\Users\SKD\Python Project\MBA_Project"
python test_symbols.py
```

Expected output:
```
Testing symbols_utils...

1. Fetching NSE symbols...
   ✓ Fetched 50 symbols
   First 5: ['RELIANCE.NS', 'TCS.NS', ...]

2. Saving symbols to JSON...
   ✓ Saved successfully

3. Loading symbols from JSON...
   ✓ Loaded 50 symbols

4. Getting symbols list...
   ✓ Got 50 symbols
   Sample mapping: [('RELIANCE.NS', 'Reliance Industries Ltd'), ...]

5. Formatting symbols with names...
   ✓ Formatted: RELIANCE.NS - Reliance Industries Ltd

6. Testing refresh...
   ✓ Stock symbols updated successfully! (50 symbols loaded)

✅ All tests completed!
```

## Usage Flow

1. **First Launch:**
   - App calls `get_available_symbols()`
   - No symbols.json exists
   - Fetches from NSE API
   - Saves to symbols.json
   - Displays in dropdown

2. **Subsequent Launches:**
   - Loads from symbols.json (fast)
   - No API call needed
   - Cached in session state

3. **User Refreshes:**
   - Clicks "⟳ Refresh Symbols"
   - Fetches latest from API
   - Updates symbols.json
   - Clears session cache
   - Reloads UI

## Error Scenarios

### Scenario 1: API Unavailable
- Fetch fails
- Falls back to static list (50 symbols)
- Saves fallback to symbols.json
- App continues normally

### Scenario 2: symbols.json Missing
- Auto-fetches on first load
- Creates symbols.json
- No user intervention needed

### Scenario 3: symbols.json Corrupted
- Load fails
- Triggers fresh fetch
- Overwrites corrupted file
- Shows error but recovers

## Data Source

### Primary: NSE India API
- Endpoint: `https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20500`
- Returns NIFTY 500 constituents
- Includes company names
- Requires session/cookie handling

### Fallback: Static List
- 50 popular NSE stocks
- Manually curated
- Includes NIFTY 50 constituents
- Used when API fails

## Performance Considerations

1. **Caching Strategy:**
   - File cache (symbols.json): Persistent across sessions
   - Session cache (st.session_state): Fast in-memory access
   - Only fetches on user action (Refresh button)

2. **Load Time:**
   - First load: ~2-3 seconds (API fetch)
   - Subsequent loads: <100ms (file read)
   - Session state: <1ms (memory)

3. **API Limits:**
   - NSE API: No official rate limit documented
   - Fetch only on user action (not automatic)
   - Respectful delays between requests

## Future Enhancements

1. **Scheduled Auto-Refresh:**
   - Background task to refresh daily
   - Update cache without user action

2. **Multiple Exchanges:**
   - BSE support
   - US stocks (NASDAQ, NYSE)
   - International markets

3. **Search/Filter:**
   - Search by company name
   - Filter by sector/industry
   - Advanced symbol picker UI

4. **Symbol Metadata:**
   - Sector information
   - Market cap
   - Trading status (active/suspended)

5. **Smart Fallback:**
   - Use last known good data
   - Timestamp-based cache invalidation
   - Configurable cache expiry

## Troubleshooting

### Issue: "No stock symbols available"
**Solution:** Click "⟳ Refresh Symbols" button

### Issue: Refresh button doesn't work
**Solution:** Check internet connection, API may be down. App will use fallback list.

### Issue: Symbols not updating after refresh
**Solution:** Check browser console for errors. Delete symbols.json and restart app.

### Issue: Import error for symbols_utils
**Solution:** Ensure symbols_utils.py is in same directory as Analyzeapp.py

## Migration Notes

### Breaking Changes:
- `NIFTY50_SYMBOLS` constant removed from utils.py
- All references updated to use `get_available_symbols()`

### Backward Compatibility:
- Existing portfolios with old symbols still work
- Edit screen shows only available symbols but preserves holdings
- No data migration needed

## Security Considerations

1. **API Calls:**
   - Uses requests with proper headers
   - Session handling for NSE API
   - Timeout protection (10 seconds)

2. **File Operations:**
   - JSON file created in app directory
   - No user input in file paths
   - UTF-8 encoding for international characters

3. **Error Handling:**
   - All exceptions caught and logged
   - Graceful degradation
   - No sensitive data exposed

## Maintenance

### Regular Tasks:
1. Monitor NSE API changes
2. Update fallback list periodically
3. Review error logs for fetch failures

### When NSE API Changes:
1. Update URL in `fetch_nse_symbols()`
2. Adjust response parsing logic
3. Test with new structure
4. Update fallback list as needed
