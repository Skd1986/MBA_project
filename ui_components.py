import streamlit as st
import uuid

def inject_button_css():
    st.markdown(
        """
        <style>
        :root {
            --btn-bg: #ffffff;
            --btn-border: #d0d7de;
            --btn-hover-bg: #f5f7fa;
            --btn-active-bg: #eef1f4;
            --btn-text: #1f2429;
            --btn-shadow: 0 1px 2px rgba(0,0,0,0.04);
            --btn-radius: 9px;
            --btn-transition: 120ms ease;
        }
        [data-small-btn] .stButton > button {
            background: var(--btn-bg);
            color: var(--btn-text);
            padding: 6px 14px;
            border: 1px solid var(--btn-border);
            border-radius: var(--btn-radius);
            font-size: 0.85rem;
            font-weight: 500;
            line-height: 1.1;
            box-shadow: var(--btn-shadow);
            cursor: pointer;
            transition: background var(--btn-transition), border-color var(--btn-transition), transform var(--btn-transition);
            display: inline-flex;
            align-items: center;
            gap: 6px;
            letter-spacing: 0.25px;
        }
        [data-small-btn] .stButton > button:hover { background: var(--btn-hover-bg); border-color: #c2c9d1; }
        [data-small-btn] .stButton > button:active { background: var(--btn-active-bg); transform: translateY(1px); }
        [data-small-btn] .stButton > button:focus { outline: 2px solid #b3c7ff; outline-offset: 1px; }
        [data-small-btn] .stButton { margin: 0; padding: 0; }
        [data-small-btn] .stButton > button span.icon { font-size: 0.95em; opacity: 0.85; display: inline-flex; align-items: center; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def small_button(label: str, icon: str = "", key: str | None = None, help: str | None = None) -> bool:
    if key is None:
        key = f"small_btn_{uuid.uuid4().hex}"
    wrapper = st.container()
    wrapper.markdown("<div data-small-btn>", unsafe_allow_html=True)
    text = f"{icon} {label}".strip()
    clicked = st.button(text, key=key, help=help)
    wrapper.markdown("</div>", unsafe_allow_html=True)
    return clicked
