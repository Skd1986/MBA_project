import streamlit as st
import matplotlib.pyplot as plt
import os
import json
import datetime
import streamlit.components.v1 as components
import urllib.parse
import textwrap
from portfolio_utils import (
    compute_covariance_matrix,
    compute_pearson_correlation,
    compute_portfolio_correlation_matrix,
    compute_asset_pearson_correlation,
)
from utils import (
    navigate, get_available_symbols, load_portfolios,
    save_portfolios, create_portfolio, update_portfolio_name,
    update_portfolio_holdings, delete_portfolio, init_session_state,
    compute_equal_weights, init_weight_widgets,
    on_slider_change, on_input_change, get_weights_from_session,
    fetch_price_data, build_portfolios_summary, calc_portfolio_returns,
    compute_metrics_from_returns, generate_portfolio_analysis_sections,
    export_comparison_to_excel_bytes, export_comparison_to_pdf_bytes
)
from symbols_utils import refresh_symbols
from screener_utils import (
    render_stock_screener_ui,
    download_price_data,
    save_price_data,
    clear_all_metrics,
)
from ui_components import inject_button_css, small_button

# -----------------------------
# Theme Injection (Light/Dark)
# -----------------------------
def inject_theme(dark: bool):
    if dark:
        st.markdown(
            """
            <style>
            body, .block-container { background-color:#0f172a !important; color:#e2e8f0 !important; }
            h1,h2,h3,h4,h5,h6 { color:#f1f5f9 !important; }
            .stMarkdown, .stText, .stCaption, p, label { color:#e2e8f0 !important; }
            .stDataFrame, div[data-testid="stDataFrame"] { background:#1e293b !important; }
            .stDataFrame [data-testid="stTable"] { background:#1e293b !important; color:#e2e8f0 !important; }
            .st-emotion-cache-13ln4jf, .st-emotion-cache-1y4p8pa { background:#1e293b !important; }
            .stTabs [data-baseweb="tab"] { background:#1e293b; color:#e2e8f0; }
            .stTabs [aria-selected="true"] { background:#334155 !important; }
            .stButton > button { background:#1e293b; color:#e2e8f0; border:1px solid #334155; }
            .stButton > button:hover { background:#334155; }
            .stDownloadButton > button { background:#1e293b; color:#e2e8f0; border:1px solid #334155; }
            .stDownloadButton > button:hover { background:#334155; }
            .stSelectbox, .stMultiSelect, .stTextInput, .stNumberInput, .stDateInput { color:#e2e8f0; }
            .stSelectbox > div[data-baseweb="select"] { background:#1e293b !important; }
            .stSlider > div { color:#e2e8f0 !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        # Light theme minimal override (optional; keep default)
        st.markdown(
            """
            <style>
            body { background-color:#ffffff; }
            </style>
            """,
            unsafe_allow_html=True,
        )
import pandas as pd

# /C:/Users/SKD/Python Project/MBA_Project/Analyzeapp.py

st.set_page_config(page_title="📈 Stock Analyzer", layout="wide")

# Popup helper: lightweight JS toast/modal (auto-dismiss) using components.html so JS runs reliably
def show_popup(message: str, duration: int = 3500) -> None:
        """Show a transient toast using an embedded HTML iframe.

        Uses Streamlit components.html which executes JS inside an iframe and is reliable across Streamlit versions.
        """
        uid = int(datetime.datetime.utcnow().timestamp() * 1000)
        safe_msg = str(message).replace("\n", "\\n").replace("\"", '\\"')
        html = f"""
        <html>
            <body>
                <div id='popup-{uid}' style='position:fixed;top:12px;right:12px;z-index:9999;'>
                    <div style='background:#2F3C7E;color:white;padding:10px 14px;border-radius:8px;box-shadow:0 6px 18px rgba(0,0,0,0.12);font-family:Helvetica,Arial,sans-serif;font-size:14px;'>
                        {safe_msg}
                    </div>
                </div>
                <script>
                    setTimeout(function() {{
                        var el = document.getElementById('popup-{uid}');
                        if (el) el.style.display = 'none';
                    }}, {duration});
                </script>
            </body>
        </html>
        """
        try:
                # small height so iframe doesn't take much vertical space
                components.html(html, height=80)
        except Exception:
                # fallback to st.write if components fails
                st.write(message)

# Initialize session state and show pending message (if any)
init_session_state()
if st.session_state.get('show_msg'):
        try:
                show_popup(st.session_state.pop('show_msg'))
        except Exception:
                # ignore popup errors during startup
                st.session_state.pop('show_msg', None)

# --- Header (persistent) ---
def render_header():
    header = st.container()
    with header:
        st.markdown("<h1 style='text-align: left; margin: 0;'>📈 Stock Analyzer</h1>", unsafe_allow_html=True)
    st.markdown("---")

# --- Page functions (skeletons) ---
def show_home():
    # Welcome section with professional styling (dedented to avoid Markdown code blocks)
    welcome_html = textwrap.dedent("""
<div style='text-align: center; padding: 2rem 0 1.5rem 0; max-width: 1400px; margin: 0 auto;'>
    <h1 style='color: #2F3C7E; margin-bottom: 1rem; font-size: 2.5rem;'>Welcome to Stock Analyzer</h1>
    <p style='color: #666; font-size: 1.2em; max-width: 800px; margin: 0 auto;'>Your comprehensive portfolio management and analysis solution</p>
</div>
    """)
    st.markdown(welcome_html, unsafe_allow_html=True)
    # Inject CSS separately to avoid it being rendered as code
    css = """
    <style>
    .home-container { max-width: 1400px; margin: 0 auto; padding: 0 1rem; }
    .section-title { color: #2F3C7E; margin-bottom: 1.5rem; font-size: 1.8rem; font-weight: 600; }
    .features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem; margin: 2rem 0; }
    .feature-card { background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); padding: 2rem; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); transition: transform 0.3s ease, box-shadow 0.3s ease; border: 1px solid rgba(47, 60, 126, 0.1); }
    .feature-card:hover { transform: translateY(-5px); box-shadow: 0 8px 24px rgba(0,0,0,0.12); }
    .feature-card h3 { color: #2F3C7E; margin-bottom: 1rem; font-size: 1.3rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem; }
    .feature-card ul { color: #555; margin-left: 1.2rem; line-height: 1.8; }
    .feature-card li { margin-bottom: 0.5rem; }
    .capabilities-container { background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); padding: 2rem; border-radius: 16px; margin: 2rem 0; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid rgba(47, 60, 126, 0.1); }
    .capabilities-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1.5rem; margin-top: 1rem; }
    .capability-item { padding: 1rem; background-color: white; border-radius: 10px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
    .capability-item p { color: #555; margin: 0.5rem 0; font-size: 0.95rem; }
    .getting-started { background: linear-gradient(135deg, #2F3C7E 0%, #4a5a99 100%); padding: 2.5rem; border-radius: 16px; margin: 2rem 0; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
    .getting-started h2 { color: white; margin-bottom: 1.5rem; font-size: 1.8rem; }
    .steps-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; margin-top: 1rem; }
    .step-card { background-color: rgba(255, 255, 255, 0.95); padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    .step-number { display: inline-block; width: 32px; height: 32px; background-color: #2F3C7E; color: white; border-radius: 50%; text-align: center; line-height: 32px; font-weight: 600; margin-bottom: 0.5rem; }
    .step-card p { color: #333; margin: 0.5rem 0; line-height: 1.6; }
    @media (max-width: 768px) { .features-grid { grid-template-columns: 1fr; gap: 1rem; } .capabilities-grid { grid-template-columns: 1fr; } .steps-grid { grid-template-columns: 1fr; } .feature-card { padding: 1.5rem; } .section-title { font-size: 1.5rem; } .getting-started { padding: 1.5rem; } }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

    content_html = textwrap.dedent("""
    <div class='home-container'>
        <h2 class='section-title'>Key Features</h2>
        <div class='features-grid'>
            <div class='feature-card'>
                <h3>📊 Portfolio Management</h3>
                <ul>
                    <li>Create custom stock portfolios</li>
                    <li>Select from NIFTY50 stocks</li>
                    <li>Flexible weight allocation</li>
                    <li>Easy portfolio editing and updates</li>
                </ul>
            </div>
            <div class='feature-card'>
                <h3>📈 Performance Analytics</h3>
                <ul>
                    <li>Real-time market data integration</li>
                    <li>Compare multiple portfolios</li>
                    <li>Advanced performance metrics</li>
                    <li>Market benchmark comparison</li>
                </ul>
            </div>
            <div class='feature-card'>
                <h3>🔗 Correlation Analysis</h3>
                <ul>
                    <li>Stock covariance matrices</li>
                    <li>Portfolio correlation tracking</li>
                    <li>Risk diversification insights</li>
                    <li>Multi-portfolio comparisons</li>
                </ul>
            </div>
        </div>
        <h2 class='section-title'>Analysis Capabilities</h2>
        <div class='capabilities-container'>
            <p style='color: #666; font-size: 1.05rem; margin-bottom: 1rem;'>Comprehensive portfolio analysis including:</p>
            <div class='capabilities-grid'>
                <div class='capability-item'>
                    <p><strong>📊 Returns Analysis</strong></p>
                    <p>• Annual Returns</p>
                    <p>• Cumulative Returns</p>
                </div>
                <div class='capability-item'>
                    <p><strong>📉 Risk Metrics</strong></p>
                    <p>• Volatility Analysis</p>
                    <p>• Sharpe Ratio</p>
                </div>
                <div class='capability-item'>
                    <p><strong>📈 Visualization</strong></p>
                    <p>• Interactive Charts</p>
                    <p>• Comparison Plots</p>
                </div>
                <div class='capability-item'>
                    <p><strong>📄 Reporting</strong></p>
                    <p>• Excel Export</p>
                    <p>• PDF Reports</p>
                </div>
            </div>
            <div class='getting-started'>
                <h2>Getting Started</h2>
                <div class='steps-grid'>
                    <div class='step-card'>
                        <div class='step-number'>1</div>
                        <p><strong>Create Portfolio</strong></p>
                        <p>Build your portfolio by selecting stocks and assigning weights</p>
                    </div>
                    <div class='step-card'>
                        <div class='step-number'>2</div>
                        <p><strong>Manage & Edit</strong></p>
                        <p>Update holdings, rename, or delete portfolios as needed</p>
                    </div>
                    <div class='step-card'>
                        <div class='step-number'>3</div>
                        <p><strong>Analyze Performance</strong></p>
                        <p>Compare portfolios and view detailed metrics with charts</p>
                    </div>
                    <div class='step-card'>
                        <div class='step-number'>4</div>
                        <p><strong>Export Reports</strong></p>
                        <p>Download comprehensive reports in Excel or PDF format</p>
                    </div>
                </div>
            </div>
        </div>
<div style='text-align: center; padding: 2rem 0; color: #999; font-size: 0.9em;'>
            <p><strong>Data powered by Yahoo Finance</strong></p>
            <p>Updated daily with real-time market data</p>
        </div>
    """)
    st.markdown(content_html, unsafe_allow_html=True)

def show_create_portfolio():
    """Render the Create Portfolio screen.

    Features:
    - Multi-select dropdown for stock symbols
    - Slider per selected stock to assign weight (%) with live display
    - Portfolio name input
    - Validation to ensure total weights == 100%
    - Save portfolios to local JSON file `portfolios.json`
    """
    st.subheader("Create Portfolio")
    st.write("Build a new portfolio by selecting stocks and assigning weights.")

    # (Refresh Symbols removed per request)
    
    # Get available symbols
    try:
        available_symbols = get_available_symbols()
        
        if not available_symbols:
            st.warning("⚠️ No stock symbols available. Please click 'Refresh Symbols' to load symbols.")
            return
        
        # Show count of available symbols
        st.caption(f"📊 {len(available_symbols)} stock symbols available")
        
        # Multi-select for stocks
        default_selection = available_symbols[:3] if len(available_symbols) >= 3 else available_symbols
        selected = st.multiselect("Select stocks / indices", options=available_symbols, default=default_selection)
        
    except Exception as e:
        st.error(f"❌ Error loading symbols: {str(e)}")
        st.info("Please click 'Refresh Symbols' to reload the symbol list.")
        return

    # Early bail-out message when nothing selected
    if not selected:
        st.info("Select one or more symbols to assign weights.")
        return

    st.markdown("---")
    
    # Update weights when selection changes
    if set(selected) != set(st.session_state.prev_selected):
        # Compute equal weights for new selection
        eq = compute_equal_weights(selected)
        st.session_state.pf_weights = eq
        st.session_state.prev_selected = list(selected)

    st.markdown("### Assign weights")
    st.write("Adjust weights per symbol. Values are in percent and should sum to 100%.")

    # Initialize weights in session state if needed
    init_weight_widgets(selected, st.session_state.pf_weights)

    # Render each selected symbol with a slider and live percentage display
    for sym in selected:
        cols = st.columns([3, 1, 1])  # Three columns: slider, input box, percentage
        
        with cols[0]:
            st.slider(
                f"{sym}",
                min_value=0.0,
                max_value=100.0,
                key=f"slider_{sym}",
                step=0.1,
                on_change=on_slider_change,
                args=(sym,)
            )
            
        with cols[1]:
            st.number_input(
                " ",  # blank label for cleaner layout
                min_value=0.0,
                max_value=100.0,
                key=f"input_{sym}",
                step=0.1,
                format="%.1f",
                on_change=on_input_change,
                args=(sym,)
            )
            
        with cols[2]:
            current_weight = st.session_state.pf_weights.get(sym, 0.0)
            st.markdown(f"**{current_weight:.2f}%**")

    # Sum up weights and expose `total`
    total = sum(st.session_state.pf_weights.values())
    total_display = round(total, 2)

    st.markdown("---")
    st.write(f"**Total weight:** {total_display}%")

    # Validation: require total == 100 (with a small tolerance on rounding)
    if round(total, 2) != 100.00:
        st.warning("Total should add up to 100%. Please adjust the weights.")
    else:
        st.success("Total equals 100%. You can save the portfolio.")

    # Portfolio name input
    pf_name = st.text_input("Portfolio name", value="My Portfolio")

    # Save button
    from ui_components import small_button
    if small_button("Create Portfolio", icon="➕", key="create_portfolio_btn"):
        # Basic validations
        if not pf_name or str(pf_name).strip() == "":
            st.error("Please provide a name for the portfolio.")
        elif round(total, 4) != 100.0:
            st.error(f"Total weight is {total_display}%. Adjust sliders so total equals 100% before saving.")
        else:
            # Create new portfolio
            portfolio = create_portfolio(pf_name, st.session_state.pf_weights)
            
            # Load existing portfolios
            existing = load_portfolios()

            # Check if portfolio with same name exists
            portfolio_exists = any(p["name"] == pf_name for p in existing)
            
            should_save = True
            if portfolio_exists:
                should_save = st.checkbox(f"Portfolio '{pf_name}' already exists. Check to overwrite")
                if should_save:
                    # Remove existing portfolio with same name
                    existing = [p for p in existing if p["name"] != pf_name]
                else:
                    st.info("Please choose a different portfolio name or check the box to overwrite")

            # Append and save if confirmed
            if should_save:
                existing.append(portfolio)
                # Save updated portfolio list
                if save_portfolios(existing):
                    # Use session-state popup so message survives rerun
                    st.session_state['show_msg'] = f"Portfolio '{pf_name}' saved to portfolios.json"
                    if not should_save:
                        st.info("Please choose a different portfolio name or check the box to overwrite")
                    st.rerun()

def show_manage_portfolio():
    """Render the Manage Portfolio screen.

    Features:
    - Load portfolios from `portfolios.json` (local file)
    - Dropdown to select a portfolio
    - Display holdings (symbol + weight)
    - Edit Portfolio: add/remove symbols and adjust weights, then save
    - Rename Portfolio: change name and save
    - Run Analytics: set session state to navigate to analytics page with selected portfolio
    """
    st.subheader("Manage Portfolio")

    portfolios = load_portfolios()

    if not portfolios:
        st.info("No saved portfolios found. Create one from the Home -> Create Portfolio screen.")
        return

    # Build name -> portfolio map for convenience
    name_map = {p.get("name", f"Portfolio {i}"): p for i, p in enumerate(portfolios)}
    names = list(name_map.keys())

    # If navigated via hyperlink, preselect the requested portfolio
    preselect = st.session_state.get('manage_selected_name')
    if preselect not in names:
        preselect = names[0]
    selected_name = st.selectbox("Select a portfolio", options=names, index=names.index(preselect))
    if not selected_name:
        st.info("No portfolio selected.")
        return

    portfolio = name_map[selected_name]
    holdings = portfolio.get("holdings", {}) if isinstance(portfolio.get("holdings", {}), dict) else {}

    # Portfolio details
    st.markdown("### Portfolio Details")
    meta_cols = st.columns([2, 2, 2])
    with meta_cols[0]:
        st.write(f"Name: **{portfolio.get('name','Unnamed')}**")
    with meta_cols[1]:
        st.write(f"Created: {portfolio.get('created_at','-')}")
    with meta_cols[2]:
        st.write(f"Holdings count: {len(holdings)}")

    st.markdown("### Holdings")
    if holdings:
        # Fetch 5-year historical price data for involved symbols and compute annual returns
        symbols = [s for s in holdings.keys() if s]
        stock_returns = {}
        try:
            price_subset = fetch_price_data(symbols)
            for s in symbols:
                ser = price_subset.get(s)
                if ser is None:
                    stock_returns[s] = float('nan')
                    continue
                # Ensure Series form
                if not isinstance(ser, (pd.Series, pd.DataFrame)):
                    stock_returns[s] = float('nan')
                    continue
                if isinstance(ser, pd.DataFrame):
                    # If DataFrame, take first column
                    if ser.empty:
                        stock_returns[s] = float('nan')
                        continue
                    ser_vals = ser.iloc[:,0].dropna()
                else:
                    ser_vals = ser.dropna()
                if ser_vals.shape[0] < 2:
                    stock_returns[s] = float('nan')
                else:
                    cumulative = ser_vals.iloc[-1] / ser_vals.iloc[0] - 1.0
                    stock_returns[s] = round(cumulative * 100.0, 2)  # percentage over the fetched year
        except Exception:
            # If price fetch fails, leave returns as NaN
            for s in symbols:
                stock_returns[s] = float('nan')

        # Build display rows including annual return percentage
        df_rows = [
            {"Symbol": s, "Weight (%)": float(w), "Annual Return (%)": stock_returns.get(s, float('nan'))}
            for s, w in holdings.items()
        ]
        st.table(df_rows)
    else:
        st.write("(No holdings in this portfolio)")

    st.markdown("---")
    # Action buttons
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        from ui_components import small_button
        if small_button("Edit Portfolio", icon="✏️", key="edit_pf"):
            st.session_state.manage_action = {"mode": "edit", "name": selected_name}
    with c2:
        if small_button("Rename Portfolio", icon="🔤", key="rename_pf"):
            st.session_state.manage_action = {"mode": "rename", "name": selected_name}
    with c3:
        if small_button("Delete Portfolio", icon="🗑️", key="delete_pf"):
            st.session_state.manage_action = {"mode": "delete", "name": selected_name}
    with c4:
        if small_button("Run Analytics", icon="📊", key="run_analytics_pf"):
            # Store selected portfolio in session_state and navigate
            st.session_state['selected_portfolio'] = portfolio
            st.session_state.page = 'analytics'
            st.rerun()

    # Provide a place to perform the chosen action
    action = st.session_state.get('manage_action')
    if action and action.get('name') == selected_name:
        mode = action.get('mode')
        if mode == 'delete':
            st.markdown("### Delete Portfolio")
            st.warning(f"Are you sure you want to delete portfolio '{selected_name}'? This action cannot be undone.")
            
            col1, col2 = st.columns(2)
            with col1:
                if small_button("Yes, Delete Portfolio", icon="✔️", key="confirm_delete_pf"):
                    # Delete the portfolio
                    try:
                        if delete_portfolio(portfolios, selected_name):
                            st.session_state['show_msg'] = f"Portfolio '{selected_name}' has been deleted."
                            st.session_state.manage_action = None
                            st.rerun()
                        else:
                            st.error("Failed to delete portfolio.")
                    except Exception as e:
                        st.error(f"Failed to delete portfolio: {e}")
            with col2:
                if small_button("Cancel", icon="✖", key="cancel_delete_pf"):
                    st.session_state.manage_action = None
                    st.rerun()
                    
        elif mode == 'rename':
            st.markdown("### Rename Portfolio")
            new_name = st.text_input("New name", value=selected_name)
            if small_button("Save new name", icon="💾", key="save_new_name_pf"):
                if not new_name or new_name.strip() == "":
                    st.error("Portfolio name cannot be empty")
                else:
                    # Update the portfolio name
                    if update_portfolio_name(portfolios, selected_name, new_name):
                        st.session_state['show_msg'] = f"Renamed portfolio to '{new_name}'"
                        st.session_state.manage_action = None
                        st.rerun()
                    else:
                        st.error("Failed to rename portfolio.")

        elif mode == 'edit':
            st.markdown("### Edit Portfolio")
            
            # Get available symbols
            try:
                available_symbols = get_available_symbols()
                
                if not available_symbols:
                    st.warning("⚠️ No stock symbols available. Please go to Create Portfolio and click 'Refresh Symbols'.")
                    return
                    
            except Exception as e:
                st.error(f"❌ Error loading symbols: {str(e)}")
                return
            
            current_symbols = list(holdings.keys())
            edited_selected = st.multiselect("Edit symbols", options=available_symbols, default=current_symbols)

            # Initialize edit weights in session state (so shared handlers can update them)
            prev_edit_sel = st.session_state.get('edit_prev_selected', [])
            if set(prev_edit_sel) != set(edited_selected):
                # If this is the very first time opening edit (no prev), and holdings exist, keep holdings
                if not prev_edit_sel and edited_selected and sum([float(v) for v in holdings.values()]) > 0:
                    ew = {s: float(holdings.get(s, 0.0)) for s in edited_selected}
                else:
                    # selection changed after initial load -> rebalance equally
                    ew = compute_equal_weights(edited_selected)
                st.session_state.edit_weights = ew
                st.session_state.edit_prev_selected = list(edited_selected)

            # Initialize edit widgets (namespaced with prefix 'edit_')
            init_weight_widgets(edited_selected, st.session_state.edit_weights, prefix='edit_')

            # Allow adjusting weights via sliders and number inputs (namespaced with 'edit_')
            for s in edited_selected:
                cols = st.columns([3, 1, 1])  # Three columns: slider, input box, percentage
                key_slider = f"edit_slider_{s}"
                key_input = f"edit_input_{s}"

                # session_state.edit_weights drives initial values; init_weight_widgets already set keys
                with cols[0]:
                    st.slider(
                        f"{s}",
                        min_value=0.0,
                        max_value=100.0,
                        step=0.1,
                        key=key_slider,
                        on_change=on_slider_change,
                        args=(s, 'edit_')
                    )

                with cols[1]:
                    st.number_input(
                        " ",  # blank label for cleaner layout
                        min_value=0.0,
                        max_value=100.0,
                        step=0.1,
                        format="%.1f",
                        key=key_input,
                        on_change=on_input_change,
                        args=(s, 'edit_')
                    )

                # display current edit weight
                current_edit_weight = float(st.session_state.edit_weights.get(s, 0.0))
                with cols[2]:
                    st.markdown(f"**{current_edit_weight:.2f}%**")

            st.markdown("---")
            save_col, cancel_col = st.columns([1,1])
            with save_col:
                if small_button("Save changes", icon="💾", key="save_changes_pf"):
                    # collect current edit weights from session
                    current_edits = get_weights_from_session(edited_selected, prefix='edit_')
                    total = round(sum(current_edits.values()), 4)
                    if round(total, 2) != 100.00:
                        st.error(f"Total weight is {total}%. Adjust so sum = 100% before saving.")
                    else:
                        # Update portfolio holdings
                        if update_portfolio_holdings(portfolios, selected_name, current_edits):
                            st.session_state['show_msg'] = "Portfolio updated"
                            st.session_state.manage_action = None
                            st.rerun()
                        else:
                            st.error("Failed to update portfolio holdings.")
            with cancel_col:
                if small_button("Cancel", icon="✖", key="cancel_edit_pf"):
                    st.session_state.manage_action = None
                    st.rerun()
    else:
        # clear action when selection changes
        st.session_state.manage_action = None

def show_run_analytics():
    st.subheader("Run Analytics")
    st.write("Compare saved portfolios over the past year. Select portfolios to compare metrics and download results.")

    portfolios = load_portfolios()
    if not portfolios:
        st.info("No saved portfolios found. Create one from the Home -> Create Portfolio screen.")
        return

    # Gather all tickers from portfolios
    all_tickers = set()
    for p in portfolios:
        holdings = p.get('holdings', {}) if isinstance(p.get('holdings', {}), dict) else {}
        for s in holdings.keys():
            all_tickers.add(s)
    # Attempt to include a valid NIFTY50 benchmark; try multiple possible Yahoo symbols.
    # Yahoo Finance commonly uses '^NSEI' for NIFTY50. Add broader fallbacks.
    candidate_market_tickers = ['^NSEI', '^N50', '^NIFTY50', '^Nifty50', 'NIFTY50.NS']
    for ct in candidate_market_tickers:
        all_tickers.add(ct)

    with st.spinner("Downloading 5-year historical price data (may take a moment)..."):
        price_df = fetch_price_data(list(all_tickers))

    # Determine which market ticker actually resolved
    market_ticker = None
    for ct in candidate_market_tickers:
        if ct in price_df.columns:
            market_ticker = ct
            break
    if market_ticker is None:
        st.warning("Benchmark index (NIFTY50) not found among fetched tickers; showing portfolios only.")
    else:
        st.caption(f"Benchmark detected: {market_ticker}")

    # Build summary + return series (user portfolios + market series)
    summary_df, series_dict = build_portfolios_summary(portfolios, price_df, market_ticker=market_ticker if market_ticker else 'INVALID_TICKER')
    # Rename market series to NIFTY50 for display
    if 'Market' in series_dict:
        series_dict['NIFTY50'] = series_dict.pop('Market')
    # Append NIFTY50 metrics row if benchmark resolved
    if market_ticker and market_ticker in price_df.columns:
        market_rets = price_df[market_ticker].pct_change().dropna()
        if market_rets.empty:
            st.caption("Benchmark price data fetched but has insufficient points for return metrics.")
        else:
            metrics = compute_metrics_from_returns(market_rets)
            market_row = {
                'name': 'NIFTY50',
                'n_stocks': 50,
                'annual_return': metrics['annual_return'],
                'cumulative_return': metrics['cumulative_return'],
                'annual_vol': metrics['annual_vol'],
                'sharpe': metrics['sharpe']
            }
            if 'NIFTY50' not in summary_df['name'].values:
                summary_df = pd.concat([pd.DataFrame([market_row]), summary_df], ignore_index=True)

    # Portfolio selection
    # Move selection to the top of the page (right after header/description)
    st.markdown("---")
    st.markdown("### Select portfolios to compare")
    st.caption("Tip: Click a portfolio name to open Manage.")
    # Inject badge CSS (once) for index highlighting
    st.markdown("""
    <style>
    .badge-index { 
        display:inline-block; 
        background:#2F3C7E; 
        color:#fff; 
        padding:2px 6px; 
        border-radius:6px; 
        font-size:0.65rem; 
        letter-spacing:0.5px; 
        vertical-align:middle; 
        margin-left:6px; 
        font-weight:600; 
    }
    </style>
    """, unsafe_allow_html=True)
    selected = []

    cols = st.columns([0.1, 2, 1, 1, 1, 1])
    cols[1].markdown("**Portfolio**")
    cols[2].markdown("**# Stocks**")
    cols[3].markdown("**Ann Return %**")
    cols[4].markdown("**Cum Return %**")
    cols[5].markdown("**Sharpe**")

    for i, row in summary_df.iterrows():
        c0, c1, c2, c3, c4, c5 = st.columns([0.1, 2, 1, 1, 1, 1])
        key = f"select_pf_{i}"
        if c0.checkbox("", key=key):
            selected.append(row['name'])
        # For user portfolios provide hyperlink; for NIFTY50 just show label
        if row['name'] == 'NIFTY50':
            c1.markdown("**NIFTY50** <span class='badge-index'>INDEX</span>", unsafe_allow_html=True)
        else:
            encoded = urllib.parse.quote(str(row['name']))
            link_md = f"[{row['name']}](?page=manage&portfolio={encoded})"
            c1.markdown(link_md)
        c2.write(int(row['n_stocks']))
        c3.write(f"{row['annual_return']*100:.2f}%")
        c4.write(f"{row['cumulative_return']*100:.2f}%")
        c5.write(f"{row['sharpe']:.2f}")

    if not selected:
        st.info("Select one or more portfolios above to compute comparison metrics and charts.")
        # (Refresh price cache button removed per request)
        return

    # ENHANCEMENT: Auto-include NIFTY50 benchmark when only one portfolio is selected
    original_selection_count = len(selected)
    if len(selected) == 1 and 'NIFTY50' not in selected:
        # Automatically include NIFTY50 for single portfolio comparison
        if 'NIFTY50' in summary_df['name'].values:
            selected.append('NIFTY50')
            st.info("📊 **Single portfolio mode**: NIFTY50 benchmark automatically included for comparison.")

    # Build comparison summary for selected portfolios
    comp_df = summary_df[summary_df['name'].isin(selected)].copy()
    comp_display = comp_df.copy()
    for col in ['annual_return', 'cumulative_return', 'annual_vol']:
        comp_display[col] = (comp_display[col] * 100).round(3)
    comp_display['sharpe'] = comp_display['sharpe'].round(3)

    # (Refresh price cache button removed per request)

    # ---- NEW: TABS UI ----
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Summary",
        "📈 Cumulative Returns",
        "📘 Covariance Matrix",
        "🔗 Pearson Correlation",
        "🧩 Portfolio Correlation",
        "💡 Analysis"
    ])

    # --- TAB 1: Summary ---
    with tab1:
        st.markdown("### Comparison summary")
        st.dataframe(
            comp_display.rename(columns={
                'name': 'Portfolio', 'n_stocks': '# Stocks',
                'annual_return': 'Annual Return (%)',
                'cumulative_return': 'Cumulative Return (%)',
                'annual_vol': 'Annual Vol (%)', 'sharpe': 'Sharpe'
            }).set_index('Portfolio')
        )

    # --- TAB 2: Cumulative Returns Plot ---
    with tab2:
        plot_series = {}
        for name in selected:
            s = series_dict.get(name)
            if s is not None and not s.empty:
                plot_series[name] = s

        # For single portfolio mode, ensure NIFTY50 is included
        if original_selection_count == 1 and 'NIFTY50' in series_dict and not series_dict['NIFTY50'].empty:
            if 'NIFTY50' not in plot_series:
                plot_series['NIFTY50'] = series_dict['NIFTY50']

        # Set appropriate title based on selection mode
        if original_selection_count == 1:
            st.markdown("### Cumulative Returns (Portfolio vs NIFTY50 Benchmark)")
        else:
            st.markdown("### Cumulative Returns (Portfolio Comparison)")
        
        if plot_series:
            plot_df = pd.concat(plot_series.values(), axis=1)
            plot_df.columns = list(plot_series.keys())
            st.line_chart(plot_df.fillna(method='ffill').fillna(0))
        else:
            st.info("No cumulative return series available.")

    # Prepare selected portfolio objects + daily returns for portfolio-level correlations
    selected_portfolios_objs = [p for p in portfolios if p.get('name', '') in selected]
    portfolio_returns = {}
    for portfolio_obj in selected_portfolios_objs:
        name = portfolio_obj.get('name', 'Unnamed')
        holdings = portfolio_obj.get('holdings', {})
        if holdings:
            daily_ret = calc_portfolio_returns(holdings, price_df)
            if not daily_ret.empty:
                portfolio_returns[name] = daily_ret
    
    # Include NIFTY50 returns (always included for single portfolio, or when explicitly selected)
    if ('NIFTY50' in selected or original_selection_count == 1) and market_ticker and market_ticker in price_df.columns:
        m_rets = price_df[market_ticker].pct_change().dropna()
        if not m_rets.empty:
            portfolio_returns['NIFTY50'] = m_rets

    # Compute matrices once for both UI and PDF export
    returns_df = price_df.pct_change().dropna()
    cov_matrix = pd.DataFrame()
    try:
        cov_matrix = compute_covariance_matrix(returns_df)
    except Exception:
        pass
    
    # Compute portfolio-level Pearson correlation
    pearson_corr = pd.DataFrame()
    if len(portfolio_returns) >= 2:
        try:
            from portfolio_utils import compute_pearson_correlation
            pearson_corr = compute_pearson_correlation(portfolio_returns)
        except Exception:
            pass
    
    # --- TAB 3: Stock-level Covariance Matrix ---
    with tab3:
        st.markdown("### Stock-level Covariance Matrix")
        if cov_matrix.empty:
            st.error("Could not compute covariance matrix.")
        else:
            st.dataframe(cov_matrix.style.format("{:.6f}"))
            cov_csv = cov_matrix.to_csv()
            st.download_button(
                label="Download Stock Covariance (CSV)",
                data=cov_csv,
                file_name="stock_covariance.csv",
                mime="text/csv",
                key="download_stock_cov_csv"
            )


    # --- TAB 4: Asset-Level Pearson Correlation ---
    with tab4:
        st.markdown("### Asset-Level Pearson Correlation (Stocks in Selected Portfolios)")
        try:
            asset_corr = compute_asset_pearson_correlation(selected_portfolios_objs, price_df)
            if asset_corr.empty:
                st.info("Not enough overlapping stock data to compute asset-level correlation (need ≥ 2 stocks).")
            else:
                st.dataframe(asset_corr.style.format("{:.4f}"))
                # Heatmap visualization
                try:
                    fig, ax = plt.subplots(figsize=(min(12, 0.5*len(asset_corr.columns)+3), min(8, 0.5*len(asset_corr.index)+3)))
                    # Attempt seaborn for better aesthetics
                    # Use matplotlib directly (avoid seaborn dependency)
                    try:
                        import numpy as np
                        im = ax.imshow(asset_corr.values, cmap="RdBu", vmin=-1, vmax=1)
                        ax.set_xticks(range(len(asset_corr.columns)))
                        ax.set_yticks(range(len(asset_corr.index)))
                        ax.set_xticklabels(asset_corr.columns, rotation=45, ha='right')
                        ax.set_yticklabels(asset_corr.index)
                        fig.colorbar(im, ax=ax)
                    except Exception:
                        im = ax.imshow(asset_corr.values, cmap="RdBu", vmin=-1, vmax=1)
                        ax.set_xticks(range(len(asset_corr.columns)))
                        ax.set_yticks(range(len(asset_corr.index)))
                        ax.set_xticklabels(asset_corr.columns, rotation=45, ha='right')
                        ax.set_yticklabels(asset_corr.index)
                        fig.colorbar(im, ax=ax)
                    ax.set_title("Asset Correlation Heatmap", fontsize=12)
                    st.pyplot(fig, use_container_width=True)
                except Exception as hh_err:
                    st.caption(f"Heatmap rendering skipped: {hh_err}")
                # Download button for CSV export of asset-level correlation
                csv_data = asset_corr.to_csv()
                st.download_button(
                    label="Download Asset Correlation (CSV)",
                    data=csv_data,
                    file_name="asset_correlation.csv",
                    mime="text/csv",
                    key="download_asset_corr_csv"
                )
        except Exception as e:
            st.error(f"Could not compute asset-level Pearson correlation: {e}")

    # --- TAB 5: Portfolio Correlation Matrix ---
    with tab5:
        if original_selection_count == 1:
            st.markdown("### Portfolio vs NIFTY50 Correlation")
        else:
            st.markdown("### Portfolio Correlation Matrix")
        
        if len(portfolio_returns) < 2:
            st.info("Select at least two portfolios (or one portfolio with NIFTY50 benchmark) to compute correlation.")
        else:
            try:
                pf_corr = compute_portfolio_correlation_matrix(portfolio_returns)
                st.dataframe(pf_corr.style.format("{:.4f}"))
                # Portfolio correlation heatmap
                try:
                    fig2, ax2 = plt.subplots(figsize=(min(10, 0.7*len(pf_corr.columns)+3), min(6, 0.7*len(pf_corr.index)+3)))
                    try:
                        im2 = ax2.imshow(pf_corr.values, cmap="RdBu", vmin=-1, vmax=1)
                        ax2.set_xticks(range(len(pf_corr.columns)))
                        ax2.set_yticks(range(len(pf_corr.index)))
                        ax2.set_xticklabels(pf_corr.columns, rotation=45, ha='right')
                        ax2.set_yticklabels(pf_corr.index)
                        for i in range(len(pf_corr.index)):
                            for j in range(len(pf_corr.columns)):
                                ax2.text(j, i, f"{pf_corr.values[i, j]:.2f}", ha='center', va='center', color='black', fontsize=8)
                        fig2.colorbar(im2, ax=ax2)
                    except Exception:
                        im2 = ax2.imshow(pf_corr.values, cmap="RdBu", vmin=-1, vmax=1)
                        ax2.set_xticks(range(len(pf_corr.columns)))
                        ax2.set_yticks(range(len(pf_corr.index)))
                        ax2.set_xticklabels(pf_corr.columns, rotation=45, ha='right')
                        ax2.set_yticklabels(pf_corr.index)
                        for i in range(len(pf_corr.index)):
                            for j in range(len(pf_corr.columns)):
                                ax2.text(j, i, f"{pf_corr.values[i, j]:.2f}", ha='center', va='center', color='black', fontsize=8)
                        fig2.colorbar(im2, ax=ax2)
                    ax2.set_title("Portfolio Correlation Heatmap", fontsize=12)
                    st.pyplot(fig2, use_container_width=True)
                except Exception as pf_hh_err:
                    st.caption(f"Portfolio heatmap skipped: {pf_hh_err}")
                
                # For single portfolio, highlight correlation with NIFTY50
                if original_selection_count == 1 and len(pf_corr) == 2:
                    portfolio_name = [n for n in pf_corr.index if n != 'NIFTY50'][0] if 'NIFTY50' in pf_corr.index else None
                    if portfolio_name and 'NIFTY50' in pf_corr.columns:
                        corr_value = pf_corr.loc[portfolio_name, 'NIFTY50']
                        st.metric(
                            label=f"{portfolio_name} ↔ NIFTY50 Correlation",
                            value=f"{corr_value:.4f}",
                            help="Correlation coefficient: 1.0 = perfect positive, 0 = no correlation, -1.0 = perfect negative"
                        )
                        if abs(corr_value) > 0.7:
                            st.caption("🔗 High correlation - portfolio closely tracks the benchmark")
                        elif abs(corr_value) < 0.3:
                            st.caption("📊 Low correlation - portfolio provides diversification vs benchmark")
                        else:
                            st.caption("⚖️ Moderate correlation with the benchmark")
                
                pf_corr_csv = pf_corr.to_csv()
                st.download_button(
                    label="Download Portfolio Correlation (CSV)",
                    data=pf_corr_csv,
                    file_name="portfolio_correlation.csv",
                    mime="text/csv",
                    key="download_pf_corr_csv"
                )
            except Exception as e:
                st.error(f"Could not compute portfolio correlation matrix: {e}")
    
    # --- TAB 6: Analysis (Findings, Suggestions, Conclusion) ---
    with tab6:
        st.markdown("### Portfolio Analysis & Insights")
        try:
            analysis_sections = generate_portfolio_analysis_sections(
                comp_df=comp_df,
                pearson_corr=pearson_corr,
                cov_matrix=cov_matrix,
                portfolios=selected_portfolios_objs,
                price_df=price_df
            )
            
            st.markdown("#### 🔍 Findings")
            st.write(analysis_sections["findings"])
            st.markdown("---")
            
            st.markdown("#### 💡 Suggestions")
            st.write(analysis_sections["suggestions"])
            st.markdown("---")
            
            st.markdown("#### 🎯 Conclusion")
            st.write(analysis_sections["conclusion"])
        except Exception as e:
            st.error(f"Failed to generate analysis insights: {e}")


    # Download results
    st.markdown("### Download Results")

    selected_portfolios = [p for p in portfolios if p.get('name', '') in selected]

    excel_bytes = None
    pdf_bytes = None

    # Generate analysis sections once for both Excel and PDF
    analysis_sections = {}
    try:
        analysis_sections = generate_portfolio_analysis_sections(
            comp_df=comp_df,
            pearson_corr=pearson_corr,
            cov_matrix=cov_matrix,
            portfolios=selected_portfolios_objs,
            price_df=price_df
        )
    except Exception:
        pass
    
    try:
        excel_bytes = export_comparison_to_excel_bytes(
            comp_df,
            {n: series_dict.get(n, pd.Series(dtype=float)) for n in selected},
            selected_portfolios,
            price_df=price_df,
            pearson_corr=pearson_corr,
            cov_matrix=cov_matrix,
            analysis_sections=analysis_sections
        )
        show_popup("Excel report generated and ready to download.")
    except Exception as e:
        st.error(f"Excel export failed: {e}")

    try:
        pdf_bytes = export_comparison_to_pdf_bytes(
            comp_df, selected_portfolios, series_dict, price_df,
            pearson_corr=pearson_corr,
            cov_matrix=cov_matrix,
            analysis_sections=analysis_sections
        )
        show_popup("PDF report generated and ready to download.")
    except Exception as e:
        st.error(f"PDF export failed (reportlab may be missing): {e}")

    left, center, right = st.columns([1, 3, 1])
    with center:
        btn_col1, btn_col2 = st.columns([1, 1])
        with btn_col1:
            if excel_bytes is not None:
                st.download_button(
                    label="Download Excel (.xlsx)",
                    data=excel_bytes,
                    file_name="portfolio_comparison.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_excel"
                )
        with btn_col2:
            if pdf_bytes is not None:
                st.download_button(
                    label="Download PDF",
                    data=pdf_bytes,
                    file_name="portfolio_comparison.pdf",
                    mime="application/pdf",
                    key="download_pdf"
                )
                
# --- Simple nav bar under header (persistent) ---
def render_sidebar_nav():
    with st.sidebar:
        st.markdown("### 🧭 Navigation")
        st.caption("Choose a section to view content.")

        main_sections = {
            "🏦 Portfolio": "Portfolio",
            "📊 Analytics": "Analytics",
            "📈 Stock Screener": "Stock Screener",
            "⚙️ Settings": "Settings",
        }

        selected_main_label = st.selectbox(
            "Main Section",
            options=list(main_sections.keys()),
            index=0,
            help="Select a section to navigate",
        )
        selected_main = main_sections[selected_main_label]

        st.markdown("<hr>", unsafe_allow_html=True)

        selected_sub = None
        if selected_main == "Portfolio":
            st.markdown("#### 🏦 Portfolio")
            selected_sub = st.radio(
                "Choose an action",
                options=["Create Portfolio", "Manage Portfolios"],
                index=0,
            )
        elif selected_main == "Analytics":
            st.markdown("#### 📊 Analytics")
            selected_sub = st.radio(
                "Choose a view",
                options=["Run Analytics"],
                index=0,
            )
        elif selected_main == "Stock Screener":
            st.markdown("#### 📈 Stock Screener")
            selected_sub = "Stock Screener"
        elif selected_main == "Settings":
            st.markdown("#### ⚙️ Settings")
            selected_sub = st.radio(
                "Choose a setting",
                options=["General", "Data Cache", "About"],
                index=0,
            )

    return selected_main, selected_sub

# --- Main layout ---
def main():
    render_header()
    inject_button_css()
    # Ensure dark mode state initialized
    if 'dark_mode' not in st.session_state:
        st.session_state['dark_mode'] = False
    selected_main, selected_sub = render_sidebar_nav()
    inject_theme(st.session_state.get('dark_mode', False))

    # Main content area
    with st.container():
        content_cols = st.columns([1, 2, 1])
        with content_cols[1]:
            # Route based on sidebar selection
            if selected_main == "Portfolio":
                if selected_sub == "Create Portfolio":
                    show_create_portfolio()
                elif selected_sub == "Manage Portfolios":
                    show_manage_portfolio()

            elif selected_main == "Analytics":
                if selected_sub == "Run Analytics":
                    show_run_analytics()
                # Removed NIFTY50 Comparison per user request

            elif selected_main == "Stock Screener":
                render_stock_screener_ui()

            elif selected_main == "Settings":
                if selected_sub == "General":
                    st.header("General Settings")
                    dm = st.checkbox("Dark Mode", value=st.session_state.get('dark_mode', False))
                    if dm != st.session_state.get('dark_mode'):
                        st.session_state['dark_mode'] = dm
                        st.rerun()
                elif selected_sub == "Data Cache":
                    st.header("Data Cache")
                    if small_button("Clear Screener Cache", icon="🧹", key="btn_clear_cache"):
                        st.session_state['show_msg'] = "Cache clear requested (implement logic)."
                    if small_button("Refresh Symbols", icon="🔁", key="btn_refresh_symbols"):
                        ok, msg = refresh_symbols()
                        st.session_state['show_msg'] = msg
                    if small_button("Refresh Screener Data", icon="🔄", key="btn_refresh_screener_data"):
                        with st.spinner("Refreshing screener price data..."):
                            try:
                                syms = get_available_symbols()
                            except Exception:
                                syms = []
                            if not syms:
                                st.error("Could not fetch symbols. Please check connection.")
                            else:
                                price_df, nifty_series = download_price_data(syms)
                                save_price_data(price_df, nifty_series)
                                clear_all_metrics()
                                st.success("Screener data refreshed successfully.")
                                st.rerun()
                elif selected_sub == "About":
                    st.header("About")
                    st.markdown("Stock Analyzer — Streamlit app for portfolio analytics and stock screening.")
                    st.caption("Version 2.0 — © 2025")

    st.markdown("---")
    st.markdown("<div style='text-align: center; color: gray;'>Developed by Deepak SK – 2025</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()

    