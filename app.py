import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os, re, glob, json, base64, datetime, urllib.request
from urllib.parse import quote

# ==============================================================================
# 1. KONFIGURASI HALAMAN UTAMA & SESSION STATE LOGIN / TEMA
# ==============================================================================
st.set_page_config(
    page_title="AmalQu — Yayasan AmalQu Indonesia Peduli",
    page_icon="https://cdn.jsdelivr.net/npm/remixicon@4.2.0/icons/Finance/funds-box-fill.svg",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

def render_html(raw_html: str):
    """Merender HTML bersih tanpa spasi indentasi berlebih agar tidak menjadi code block."""
    cleaned = " ".join(line.strip() for line in raw_html.splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)

@st.cache_data(ttl=86400, show_spinner=False)
def resolve_ibb_logo(page_url: str) -> str:
    """Mengekstrak direct image URL otomatis dari tautan ImgBB https://ibb.co.com/W4RG2Dpv."""
    try:
        req = urllib.request.Request(page_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            html_text = resp.read().decode('utf-8', errors='ignore')
        m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
        if not m:
            m = re.search(r'content=["\']([^"\']+)["\']\s+property=["\']og:image["\']', html_text, re.IGNORECASE)
        if m:
            return m.group(1)
    except:
        pass
    return ""

LOGO_IBB_PAGE = "https://ibb.co.com/W4RG2Dpv"
DIRECT_LOGO_URL = resolve_ibb_logo(LOGO_IBB_PAGE)

# ==============================================================================
# 2. REGISTRY 4 USER LOGIN (RBAC) & 16 LINK SPREADSHEET OTOMATIS
# ==============================================================================
B64_AUTH_USERS = (
    "eyJhbWFscXUiOnsidXNlcm5hbWVfZGlzcGxheSI6IkFtYWxxdSIsInB3IjoiQWxsYWgxYWhhZCIsInJvbGUiOiJBZG"
    "1pbiIsInRpdGxlIjoiU3VwZXIgQWRtaW5pc3RyYXRvciIsIm1lbnVzIjpbIkRhc2hib2FyZCBPdmVydmlldyIsIkRv"
    "bmFzaSAmIFNhdHBhbSBLZXVhbmdhbiIsIlBlcmZvcm1hIENTICYgTGVhZHMiLCJMb2dpc3RpayAmIEd1ZGFuZyIsIk"
    "thbGVuZGVyIERpc3RyaWJ1c2kiLCJEYXRhYmFzZSAmIFdBIEJsYXN0Il19LCJmaW5hbmNlIjp7InVzZXJuYW1lX2Rp"
    "c3BsYXkiOiJGaW5hbmNlIiwicHciOiJ0aW1maW5hbmNlamF5YTk5Iiwicm9sZSI6IkZpbmFuY2UiLCJ0aXRsZSI6Ik"
    "RpdmlzaSBGaW5hbmNlICYgQXVkaXQiLCJtZW51cyI6WyJEYXNoYm9hcmQgT3ZlcnZpZXciLCJEb25hc2kgJiBTYXRw"
    "YW0gS2V1YW5nYW4iLCJQZXJmb3JtYSBDUyAmIExlYWRzIiwiTG9naXN0aWsgJiBHdWRhbmciLCJLYWxlbmRlciBEaX"
    "N0cmlidXNpIiwiRGF0YWJhc2UgJiBXQSBCbGFzdCJdfSwiYWR2ZXJ0aXNlciI6eyJ1c2VybmFtZV9kaXNwbGF5Ijoi"
    "QWR2ZXJ0aXNlciIsInB3Ijoibmdpa2xhbmdhY29yOTkiLCJyb2xlIjoiQWR2ZXJ0aXNlciIsInRpdGxlIjoiRGl2aX"
    "NpIERpZ2l0YWwgQWRzICYgRnVubmVsIiwibWVudXMiOlsiRGFzaGJvYXJkIE92ZXJ2aWV3IiwiRG9uYXNpICYgU2F0"
    "cGFtIEtldWFuZ2FuIiwiUGVyZm9ybWEgQ1MgJiBMZWFkcyJdfSwid2FyZWhvdXNlIjp7InVzZXJuYW1lX2Rpc3BsYX"
    "kiOiJXYXJlaG91c2UiLCJwdyI6ImFtYW5zdWxhaW1hbjEyMyIsInJvbGUiOiJXYXJlaG91c2UiLCJ0aXRsZSI6IkRp"
    "dmlzaSBHdWRhbmcgJiBEaXN0cmlidXNpIiwibWVudXMiOlsiTG9naXN0aWsgJiBHdWRhbmciLCJLYWxlbmRlciBEaX"
    "N0cmlidXNpIl19fQ=="
)

B64_SHEETS_REGISTRY = (
    "eyJsZWFkc19jcyI6WyIxMXhMNklXcTlEX2ttZ1lpY1FVREktQ0g4Y3JwazQzR25uSi1wVDFNNkxrdyIsIjEzMTgzNzEzOTMiXSwi"
    "c2F0cGFtIjpbIjFBY3UxdDcwNFI0TXMzTXd6MU5ySl8weDhwOXhQbkg4UVdvbjFPb2FveHhVIiwiMCJdLCJkYXRhX2NzIjpbIjFx"
    "blB1WnZZTVFGbWEtM1drXy14MmlXbnJ5d1NVRm54bThRRS1yaVlvV3VzIiwiMTUwNDE0NzExOSJdLCJtYXN0ZXJfZGIiOlsiMXpl"
    "VER3ZVNIdkFMUUVyaUw3RDFuN0pMTkFvQmNQa3E4aTU3bVJLSGxTM1UiLCIxODI3NDIyNjk4Il0sInN0b2tfbXVzaGFmIjpbIjFw"
    "MmZJU2llY2NoSDg0TFV2ZHBFYnpQc2EzWVFxX0hBVkNVdmJmSlR3eHZFIiwiMTA0Il0sImthbGVuZGVyX2Rpc3QiOlsiMTU5bmJ2"
    "ai1vbi1TTTVZd2NRR0hwOGZmekpGWTdnajdBVUFwdHBSbDB3SkEiLCIxOTQwNjEwOTc0Il0sImJ1bGFuX2phbnVhcmkiOlsiMURS"
    "dDVoeUtTUHJYRFRRMzJXWUxQSlQ1WW1uNmxpYWFWMUpFZUJ0Z0ttWFkiLCIwIl0sImJ1bGFuX2ZlYnJ1YXJpIjpbIjFMREZBUWhU"
    "T0ZCbmVvUW52QUJmeHRTMGN1dS05anBpekl3d0poNTB5NTlzIiwiMCJdLCJidWxhbl9tYXJldCI6WyIxRmpFQ0Vza0RmOHhMVUQ4"
    "ZjFKVUJ2ZGhGRXhZc09CRnh0bmxNR2JaQUVKdyIsIjcyNzI1OTE0Il0sImJ1bGFuX2FwcmlsIjpbIjFxclpfRXpKVTJaRnhCRHRO"
    "M3M0YUNHX0tqWmtVOGlQMzZvcUtqZnZwWlRnIiwiNzI3MjU5MTQiXSwiYnVsYW5fbWVpIjpbIjEwODFadkVkWTBwSjhzNVdVcnBT"
    "TlZtRzV3MVkyV1lkd01mMVJTUGE3LVJjIiwiMTgyNzQyMjY5OCJdLCJidWxhbl9qdW5pIjpbIjEyQkFCa25Rdk5EQWlPVlVRb19S"
    "bjRNVExRNjdYN3VmYXZVTGY1S3ItTFM0IiwiODM4OTQ1OTE3Il0sImJ1bGFuX2p1bGkiOlsiMTVVTXV3N1lDZHZ1WGhncUJQWWVV"
    "M3JuQlotVHpjci1NWFVPQUNTOXlldzQiLCI4Mzg5NDU5MTciXSwiYnVsYW5fYWd1c3R1cyI6WyIxYi1VNEEzM0NxV0wwXzROTDg4"
    "eHlXZ0VISE90UzV4TDZqbWNtTkgxb2V1SSIsIjE5ODQyODE5MiJdLCJidWxhbl9zZXB0ZW1iZXIiOlsiMXIydnVyVTBvUXhIUnd2"
    "eEQwRGZzcGZtTm1CemE2aFhsZmNvNjVGSzhBbVkiLCIxNzA2NDQ4NDAiXSwiYnVsYW5fb2t0b2JlciI6WyIxMFVKejYydllCNG04"
    "NlRDX1diT0lmYmdVWUxwOGduZkZvOC1uTmtfVzE4MCIsIjE3MDY0NDg0MCJdfQ=="
)

def get_auth_registry():
    try:
        return json.loads(base64.b64decode(B64_AUTH_USERS).decode("utf-8"))
    except:
        return {}

def get_builtin_registry():
    try:
        return json.loads(base64.b64decode(B64_SHEETS_REGISTRY).decode("utf-8"))
    except:
        return {}

def build_gsheet_url(key_name, sheet_name=None):
    reg = get_builtin_registry()
    if key_name not in reg:
        return None
    sid, gid = reg[key_name]
    base = "https://" + "docs.google" + ".com/spreadsheets/d/" + sid
    if sheet_name:
        return f"{base}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return f"{base}/export?format=csv&gid={gid}"

# ==============================================================================
# 3. DYNAMIC CSS INJECTION (AUTO-RESPONSIVE MOBILE/DESKTOP + DUAL THEME)
# ==============================================================================
is_dark = st.session_state.dark_mode

if is_dark:
    css_vars = """
    :root {
        --bg-main: #0B0F19;
        --bg-card: #111827;
        --bg-subcard: #1E293B;
        --bg-input: #1E293B;
        --text-primary: #F8FAFC;
        --text-secondary: #CBD5E1;
        --text-muted: #94A3B8;
        --border-soft: #1E293B;
        --border-strong: #334155;
        --table-head: #1E293B;
        --table-hover: #1E293B;
        --cal-active-bg: linear-gradient(180deg, rgba(249,115,22,0.18) 0%, #111827 100%);
        --cal-pill-bg: #1E293B;
    }
    """
else:
    css_vars = """
    :root {
        --bg-main: #F4F7FE;
        --bg-card: #FFFFFF;
        --bg-subcard: #F8FAFC;
        --bg-input: #FFFFFF;
        --text-primary: #0F172A;
        --text-secondary: #475569;
        --text-muted: #94A3B8;
        --border-soft: #E2E8F0;
        --border-strong: #CBD5E1;
        --table-head: #F8FAFC;
        --table-hover: #F1F5F9;
        --cal-active-bg: linear-gradient(180deg, #FFF7ED 0%, #FFFFFF 100%);
        --cal-pill-bg: #FFFFFF;
    }
    """

hide_sidebar_css = """
section[data-testid="stSidebar"], [data-testid="collapsedControl"] {
    display: none !important;
}
""" if st.session_state.auth_user is None else ""

render_html(f"""
<link href="https://cdn.jsdelivr.net/npm/remixicon@4.2.0/fonts/remixicon.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{css_vars}
{hide_sidebar_css}

.stApp, [data-testid="stAppViewContainer"] {{
    background-color: var(--bg-main) !important;
    color: var(--text-primary) !important;
}}
[data-testid="stHeader"] {{
    background-color: transparent !important;
}}
body, p, span, div, label, input, button, th, td, li {{
    font-family: 'Plus Jakarta Sans', -apple-system, sans-serif !important;
    color: var(--text-primary);
}}
h1, h2, h3, h4, h5, h6, .metric-num, .brand-title {{
    font-family: 'Outfit', sans-serif !important;
    color: var(--text-primary) !important;
}}
.brand-sub {{ color: var(--text-secondary) !important; }}
i[class^="ri-"], i[class*=" ri-"] {{
    font-family: 'remixicon' !important;
    font-style: normal !important;
}}

.block-container {{
    padding-top: 2.2rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 1440px !important;
}}

/* Sidebar Styling */
section[data-testid="stSidebar"] {{
    background-color: var(--bg-card) !important;
    border-right: 1px solid var(--border-soft) !important;
}}
section[data-testid="stSidebar"] * {{
    color: var(--text-primary);
}}
.sub-box {{
    background: var(--bg-subcard);
    border: 1px solid var(--border-soft);
}}

/* Sidebar Navigation Pills */
section[data-testid="stSidebar"] div[role="radiogroup"] {{
    gap: 6px !important;
    display: flex !important;
    flex-direction: column !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label {{
    background: transparent !important;
    border: 1px solid transparent !important;
    border-radius: 12px !important;
    padding: 10px 14px !important;
    margin: 0 !important;
    cursor: pointer !important;
    width: 100% !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
    background: var(--bg-subcard) !important;
    border-color: var(--border-soft) !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{
    display: none !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label p {{
    font-size: 13.5px !important;
    font-weight: 600 !important;
    color: var(--text-secondary) !important;
    margin: 0 !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
    background: linear-gradient(135deg, #FF6B4A 0%, #F97316 100%) !important;
    box-shadow: 0 6px 16px rgba(249, 115, 22, 0.28) !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p,
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) span {{
    color: #FFFFFF !important;
    font-weight: 700 !important;
}}

/* Segmented Radio Switcher di Main Content */
div[data-testid="stMainBlockContainer"] div[role="radiogroup"] {{
    background: var(--bg-subcard) !important;
    padding: 5px !important;
    border-radius: 12px !important;
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 6px !important;
    border: 1px solid var(--border-soft) !important;
}}
div[data-testid="stMainBlockContainer"] div[role="radiogroup"] label {{
    background: transparent !important;
    padding: 7px 14px !important;
    border-radius: 9px !important;
    cursor: pointer !important;
}}
div[data-testid="stMainBlockContainer"] div[role="radiogroup"] label > div:first-child {{
    display: none !important;
}}
div[data-testid="stMainBlockContainer"] div[role="radiogroup"] label p {{
    font-size: 12.5px !important;
    font-weight: 600 !important;
    color: var(--text-secondary) !important;
}}
div[data-testid="stMainBlockContainer"] div[role="radiogroup"] label:has(input:checked) {{
    background: var(--bg-card) !important;
    border: 1px solid var(--border-strong) !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
}}
div[data-testid="stMainBlockContainer"] div[role="radiogroup"] label:has(input:checked) p {{
    color: #FF6B4A !important;
    font-weight: 700 !important;
}}

/* Selectbox, Inputs, Popover Dropdowns & Buttons */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
div[data-baseweb="base-input"] {{
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 11px !important;
    color: var(--text-primary) !important;
}}
div[data-baseweb="select"] span,
div[data-baseweb="input"] input,
div[data-testid="stWidgetLabel"] p {{
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    font-size: 12.5px !important;
}}
div[data-baseweb="popover"],
ul[role="listbox"],
li[role="option"] {{
    background-color: var(--bg-card) !important;
    color: var(--text-primary) !important;
}}
li[role="option"]:hover {{
    background-color: var(--bg-subcard) !important;
}}
button[kind="primary"], button[kind="secondary"], [data-testid="stDownloadButton"] button, [data-testid="stFormSubmitButton"] button {{
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    padding: 8px 14px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05) !important;
}}
[data-testid="stFormSubmitButton"] button {{
    background: linear-gradient(135deg, #FF6B4A 0%, #F97316 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    padding: 10px 18px !important;
    box-shadow: 0 6px 16px rgba(249, 115, 22, 0.3) !important;
}}
[data-testid="stFormSubmitButton"] button p {{
    color: #FFFFFF !important;
    font-weight: 700 !important;
}}
button[kind="primary"]:hover, button[kind="secondary"]:hover, [data-testid="stDownloadButton"] button:hover {{
    border-color: #FF6B4A !important;
    color: #FF6B4A !important;
}}

/* Bento Cards & Chart Containers */
.bento-card, [data-testid="stForm"] {{
    background: var(--bg-card) !important;
    border: 1px solid var(--border-soft) !important;
    border-radius: 18px !important;
    padding: 18px 20px !important;
    box-shadow: 0 4px 18px -2px rgba(0, 0, 0, 0.04) !important;
    margin-bottom: 14px !important;
}}
.chart-header-box {{
    background: var(--bg-card);
    border: 1px solid var(--border-soft);
    border-bottom: none;
    border-radius: 18px 18px 0 0;
    padding: 16px 20px 6px 20px;
    margin-bottom: -14px;
    position: relative;
    z-index: 2;
}}
[data-testid="stPlotlyChart"] {{
    background: var(--bg-card) !important;
    border: 1px solid var(--border-soft) !important;
    border-radius: 18px !important;
    padding: 8px 12px 6px 12px !important;
    box-shadow: 0 4px 18px -2px rgba(0, 0, 0, 0.04) !important;
    margin-bottom: 14px !important;
}}
.hero-card {{
    background: linear-gradient(135deg, #4F46E5 0%, #6366F1 55%, #8B5CF6 100%);
    border-radius: 18px;
    padding: 18px 20px;
    color: #FFFFFF !important;
    box-shadow: 0 10px 24px -6px rgba(79, 70, 229, 0.4);
    margin-bottom: 14px;
}}
.hero-card * {{ color: #FFFFFF !important; }}

/* Icon Box & Status Badges */
.icon-box {{
    width: 36px; height: 36px; border-radius: 10px; flex-shrink: 0;
    display: inline-flex; align-items: center; justify-content: center; font-size: 17px;
}}
.ib-indigo {{ background: rgba(79, 70, 229, 0.14); color: #6366F1 !important; }}
.ib-orange {{ background: rgba(249, 115, 22, 0.14); color: #F97316 !important; }}
.ib-emerald {{ background: rgba(16, 185, 129, 0.14); color: #10B981 !important; }}
.ib-rose {{ background: rgba(239, 68, 68, 0.14); color: #EF4444 !important; }}

.badge-pill {{
    font-size: 11px; font-weight: 700; padding: 4px 10px;
    border-radius: 99px; display: inline-flex; align-items: center; gap: 4px;
    white-space: nowrap !important; flex-shrink: 0;
}}
.bp-green {{ background: rgba(16, 185, 129, 0.16); color: #10B981 !important; }}
.bp-red {{ background: rgba(239, 68, 68, 0.16); color: #EF4444 !important; }}
.bp-orange {{ background: rgba(249, 115, 22, 0.16); color: #F97316 !important; }}
.bp-indigo {{ background: rgba(79, 70, 229, 0.16); color: #6366F1 !important; }}

/* Custom Clean SaaS Table */
.saas-table-wrap {{
    background: var(--bg-card);
    border: 1px solid var(--border-soft);
    border-radius: 18px;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    margin-top: 8px;
    margin-bottom: 16px;
}}
.saas-table {{
    width: 100%; border-collapse: collapse; text-align: left; font-size: 12.5px;
}}
.saas-table thead tr {{
    background: var(--table-head); border-bottom: 1px solid var(--border-soft);
}}
.saas-table th {{
    padding: 12px 15px; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5px;
    color: var(--text-muted) !important; white-space: nowrap;
}}
.saas-table td {{
    padding: 12px 15px; color: var(--text-primary) !important;
    font-weight: 500; border-bottom: 1px solid var(--border-soft); white-space: nowrap;
}}
.saas-table tbody tr:hover {{ background: var(--table-hover); }}

/* Desktop vs Mobile Calendar Auto-Switch */
.cal-desktop-only {{ display: block; }}
.cal-mobile-only {{ display: none; }}
.cal-grid-7 {{
    display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; margin-top: 12px;
}}
.cal-head-cell {{
    text-align: center; font-size: 11px; font-weight: 700; color: var(--text-muted) !important;
    background: var(--bg-subcard); padding: 8px 4px; border-radius: 8px; border: 1px solid var(--border-soft);
}}
.cal-cell {{
    background: var(--bg-card); border: 1px solid var(--border-soft); border-radius: 12px;
    min-height: 96px; padding: 8px 10px; display: flex; flex-direction: column; justify-content: space-between;
}}
.cal-cell-empty {{
    background: var(--bg-subcard); border: 1px dashed var(--border-soft); border-radius: 12px; min-height: 96px; opacity: 0.45;
}}
.cal-cell-active {{
    background: var(--cal-active-bg); border: 1.5px solid #FB923C; border-radius: 12px;
    min-height: 96px; padding: 8px 10px;
}}
.cal-day-num {{
    font-family: 'Outfit', sans-serif !important; font-size: 13px; font-weight: 700;
    color: var(--text-primary) !important; display: flex; justify-content: space-between; align-items: center; gap: 4px;
}}
.cal-item-pill {{
    background: var(--cal-pill-bg); border: 1px solid var(--border-soft); border-left: 3px solid #F97316;
    border-radius: 6px; padding: 4px 6px; margin-top: 4px; font-size: 10.5px; color: var(--text-primary) !important; line-height: 1.25;
}}

/* AUTO-RESPONSIVE UNTUK LAYAR HANDPHONE & TABLET */
@media screen and (max-width: 768px) {{
    .block-container {{
        padding-left: 12px !important;
        padding-right: 12px !important;
        padding-top: 3.2rem !important;
    }}
    div[data-testid="stHorizontalBlock"] {{
        flex-wrap: wrap !important;
    }}
    div[data-testid="column"] {{
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }}
    .bento-card, .hero-card {{
        padding: 15px 16px !important;
        border-radius: 16px !important;
    }}
    .metric-num {{
        font-size: 22px !important;
    }}
    .cal-desktop-only {{ display: none !important; }}
    .cal-mobile-only {{ display: block !important; }}
}}
</style>
""")

# ==============================================================================
# 4. HALAMAN GERBANG LOGIN (JIKA USER BELUM LOGIN)
# ==============================================================================
if DIRECT_LOGO_URL:
    brand_logo_big = f'<img src="{DIRECT_LOGO_URL}" style="width:68px; height:68px; border-radius:16px; object-fit:contain; background:#FFFFFF; padding:6px; box-shadow:0 8px 20px rgba(0,0,0,0.08); margin-bottom:12px;" alt="AmalQu">'
else:
    brand_logo_big = (
        '<div style="width:68px; height:68px; border-radius:16px; background:linear-gradient(135deg, #FF6B4A 0%, #F97316 100%); '
        'display:inline-flex; align-items:center; justify-content:center; box-shadow:0 8px 20px rgba(249,115,22,0.3); margin-bottom:12px;">'
        '<i class="ri-hand-heart-fill" style="color:#FFFFFF !important; font-size:34px;"></i></div>'
    )

if st.session_state.auth_user is None:
    top_sp1, top_sp2 = st.columns([6, 1])
    with top_sp2:
        theme_icon_login = "☀️" if is_dark else "🌙"
        if st.button(theme_icon_login, key="login_theme_btn", help="Ubah Mode Terang / Gelap"):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

    _, login_col, _ = st.columns([1.2, 1.4, 1.2])
    with login_col:
        render_html(f"""
        <div style="text-align:center; margin-top:24px; margin-bottom:16px;">
            {brand_logo_big}
            <div style="font-family:'Outfit',sans-serif !important; font-size:28px; font-weight:800; letter-spacing:-0.5px;">AmalQu</div>
            <div style="font-size:13.5px; font-weight:600; color:var(--text-secondary) !important; margin-top:2px;">
                Yayasan AmalQu Indonesia Peduli • Enterprise Command Center
            </div>
        </div>
        """)

        with st.form("amalqu_login_form", clear_on_submit=False):
            render_html("""
            <div style="font-family:'Outfit',sans-serif !important; font-size:17px; font-weight:700; margin-bottom:4px; text-align:center;">
                <i class="ri-shield-keyhole-line" style="color:#FF6B4A !important;"></i> Portal Akses Resmi
            </div>
            <div style="font-size:12px; color:var(--text-muted) !important; text-align:center; margin-bottom:14px;">
                Masukkan ID Pengguna dan Password divisi Anda untuk melanjutkan
            </div>
            """)
            inp_user = st.text_input("ID Pengguna (Username)", placeholder="Masukkan ID (Contoh: Amalqu / Finance / Advertiser / Warehouse)")
            inp_pass = st.text_input("Password", type="password", placeholder="Masukkan Password")
            submit_login = st.form_submit_button("Masuk ke Command Center", use_container_width=True)

            if submit_login:
                auth_reg = get_auth_registry()
                u_clean = str(inp_user).strip().lower()
                p_clean = str(inp_pass).strip()
                if u_clean in auth_reg and auth_reg[u_clean]["pw"] == p_clean:
                    st.session_state.auth_user = auth_reg[u_clean]
                    st.rerun()
                else:
                    st.error("ID Pengguna atau Password tidak sesuai. Silakan periksa kembali huruf besar/kecil password Anda.")

        render_html("""
        <div style="text-align:center; font-size:11.5px; color:var(--text-muted) !important; margin-top:14px;">
            <i class="ri-lock-2-line"></i> Sistem Keamanan Terenkripsi • Hak Akses Berbasis Divisi (RBAC)
        </div>
        """)
    st.stop()

# Ambil profil user yang sedang aktif
current_user = st.session_state.auth_user
user_role = current_user.get("role", "Admin")
allowed_menus = current_user.get("menus", ["Dashboard Overview"])

# ==============================================================================
# 5. HELPER FORMATTING & KALKULATOR SATPAM KEUANGAN
# ==============================================================================
def rp(val):
    try:
        return f"Rp {float(val):,.0f}".replace(",", ".")
    except:
        return "Rp 0"

def rp_short(val):
    try:
        v = float(val)
        if abs(v) >= 1_000_000_000:
            return f"Rp {v/1_000_000_000:.2f} M"
        elif abs(v) >= 1_000_000:
            return f"Rp {v/1_000_000:.1f} Jt"
        return f"Rp {v:,.0f}".replace(",", ".")
    except:
        return "Rp 0"

def num_clean(val):
    if pd.isna(val):
        return 0.0
    s = str(val).strip()
    if not s or s in ["-", "None", "nan", "#REF!", "#VALUE!", "#DIV/0!", "#ERROR!"]:
        return 0.0
    try:
        return float(s)
    except:
        pass
    s_clean = re.sub(r'[Rp\s%a-zA-Z]', '', s)
    if '.' in s_clean and ',' in s_clean:
        s_clean = s_clean.replace('.', '').replace(',', '.')
    elif ',' in s_clean:
        parts = s_clean.split(',')
        s_clean = s_clean.replace(',', '.') if len(parts[-1]) <= 2 else s_clean.replace(',', '')
    elif s_clean.count('.') > 1:
        s_clean = s_clean.replace('.', '')
    try:
        return float(s_clean)
    except:
        return 0.0

def hitung_satpam_keuangan(target_omzet, donasi_masuk, biaya_iklan, kebutuhan_mushaf_pcs=None):
    target_omzet = float(target_omzet or 0)
    donasi_masuk = float(donasi_masuk or 0)
    biaya_iklan = float(biaya_iklan or 0)
    if not kebutuhan_mushaf_pcs or kebutuhan_mushaf_pcs <= 0:
        kebutuhan_mushaf_pcs = max(1, int(round(donasi_masuk / 99000.0))) if donasi_masuk > 0 else 1

    roas_aktual = (donasi_masuk / biaya_iklan) if biaya_iklan > 0 else 0.0
    ambang_min = 1.52
    ambang_aman = 2.63

    kurang_target = max(0.0, target_omzet - donasi_masuk)
    subsidi_min_roas = max(0.0, (biaya_iklan * ambang_min) - donasi_masuk)
    target_crm_cs = max(kurang_target, subsidi_min_roas)

    if roas_aktual >= ambang_aman:
        status_roas = "AMAN (Tier 3 >= 2.63x)"
        badge_type = "green"
    elif roas_aktual >= ambang_min:
        status_roas = "WASPADA (Tier 1/2)"
        badge_type = "orange"
    else:
        status_roas = "KRITIS (< 1.52x • Wajib Subsidi CRM)"
        badge_type = "red"

    profit_iklan = donasi_masuk - biaya_iklan
    beban_ops_10 = 0.10 * donasi_masuk
    dsd = donasi_masuk - biaya_iklan - beban_ops_10
    alokasi_mushaf_65 = 0.65 * dsd
    cadangan_cashback_35 = 0.35 * dsd
    plafon_hpp = (alokasi_mushaf_65 / kebutuhan_mushaf_pcs) if kebutuhan_mushaf_pcs > 0 else 0.0

    if plafon_hpp >= 33500:
        rekom_tier = "Tier 3: Hard Cover Premium (~Rp 33.500)"
    elif plafon_hpp >= 26000:
        rekom_tier = "Tier 2: Mushaf Standar (~Rp 26.000)"
    elif plafon_hpp >= 20000:
        rekom_tier = "Tier 1: Soft Cover (Rp 20.000)"
    else:
        rekom_tier = "Defisit HPP (< Rp 20rb) • Gunakan Cadangan 35% & Kejar CRM"

    sisa_bersih = dsd - (kebutuhan_mushaf_pcs * 20000.0)
    return {
        "roas_aktual": roas_aktual, "status_roas": status_roas, "badge_type": badge_type,
        "target_crm_cs": target_crm_cs, "profit_iklan": profit_iklan, "beban_ops_10": beban_ops_10,
        "dsd": dsd, "alokasi_mushaf_65": alokasi_mushaf_65, "cadangan_cashback_35": cadangan_cashback_35,
        "plafon_hpp": plafon_hpp, "rekom_tier": rekom_tier, "sisa_bersih": sisa_bersih,
        "kebutuhan_mushaf_pcs": int(kebutuhan_mushaf_pcs)
    }

# ==============================================================================
# 6. ENGINE DATA REALTIME GOOGLE SHEETS & SMART COLUMN MAPPER
# ==============================================================================
def fetch_raw_grid(key_name, sheet_name=None):
    try:
        url = build_gsheet_url(key_name, sheet_name)
        if not url:
            return pd.DataFrame()
        return pd.read_csv(url, header=None, dtype=str).fillna("")
    except:
        return pd.DataFrame()

def extract_anchored_table(df_raw, anchor1, anchor2=None, stop_words=None, max_rows=60):
    if df_raw is None or df_raw.empty:
        return pd.DataFrame()
    nrows, ncols = df_raw.shape
    start_r, start_c = None, None
    for r in range(nrows):
        for c in range(ncols):
            val = str(df_raw.iat[r, c]).strip()
            if val.lower() == anchor1.lower():
                if anchor2 is None:
                    start_r, start_c = r, c
                    break
                elif c + 1 < ncols and anchor2.lower() in str(df_raw.iat[r, c+1]).strip().lower():
                    start_r, start_c = r, c
                    break
        if start_r is not None:
            break
    if start_r is None:
        return pd.DataFrame()

    headers = []
    end_c = start_c
    while end_c < ncols:
        h = str(df_raw.iat[start_r, end_c]).strip()
        if h == "" or h.lower().startswith("unnamed"):
            break
        headers.append(h)
        end_c += 1

    data_rows = []
    for r in range(start_r + 1, min(nrows, start_r + 1 + max_rows)):
        first_cell = str(df_raw.iat[r, start_c]).strip()
        if first_cell == "":
            break
        if stop_words and any(sw.lower() in first_cell.lower() for sw in stop_words):
            break
        row_vals = [str(df_raw.iat[r, c]).strip() for c in range(start_c, end_c)]
        data_rows.append(row_vals)

    return pd.DataFrame(data_rows, columns=headers)

def normalize_contacts_df(df_in: pd.DataFrame) -> pd.DataFrame:
    if df_in is None or df_in.empty:
        return pd.DataFrame()
    df = df_in.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if "Nama Donatur" not in df.columns and "Nomor Whatsapp" not in df.columns:
        for r_idx in range(min(8, len(df))):
            row_vals = [str(x).strip() for x in df.iloc[r_idx].values]
            if any("nama donatur" in v.lower() for v in row_vals):
                df.columns = [v if v else f"Col_{i}" for i, v in enumerate(row_vals)]
                df = df.iloc[r_idx+1:].reset_index(drop=True)
                break

    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if "nama donatur" in cl or (cl == "nama" and "Nama Donatur" not in col_map.values()):
            col_map[c] = "Nama Donatur"
        elif "whatsapp" in cl or "no hp" in cl or "nomor hp" in cl:
            if "Nomor Whatsapp" not in col_map.values():
                col_map[c] = "Nomor Whatsapp"
        elif cl in ["pic", "cs", "pj cs"]:
            col_map[c] = "PiC"
        elif "program" in cl or "jenis" in cl:
            if "Program" not in col_map.values():
                col_map[c] = "Program"
        elif "donasi terakhir" in cl or "tanggal" in cl:
            if "Donasi Terakhir" not in col_map.values():
                col_map[c] = "Donasi Terakhir"
        elif "kategori" in cl or "status donatur" in cl:
            if "Kategori" not in col_map.values():
                col_map[c] = "Kategori"
        elif "prioritas" in cl or "segmen" in cl:
            if "Prioritas" not in col_map.values():
                col_map[c] = "Prioritas"
        elif "reminder" in cl:
            if "Reminder" not in col_map.values():
                col_map[c] = "Reminder"
        elif "fu1" in cl or "sapaan" in cl:
            col_map[c] = "FU1 (Sapaan)"
        elif "fu3" in cl or "laporan" in cl:
            col_map[c] = "FU3 (Laporan Penyaluran)"

    df.rename(columns=col_map, inplace=True)
    df = df.loc[:, ~df.columns.duplicated()]

    defaults = {
        "Nama Donatur": "Hamba Allah",
        "Nomor Whatsapp": "",
        "PiC": "Tim CS",
        "Program": "Waqaf/Mushaf",
        "Donasi Terakhir": "-",
        "Kategori": "Donatur Baru",
        "Prioritas": "Reguler",
        "Reminder": "CALLBACK SEGERA",
        "FU1 (Sapaan)": "Belum",
        "FU3 (Laporan Penyaluran)": "Belum"
    }
    for req_col, def_val in defaults.items():
        if req_col not in df.columns:
            df[req_col] = def_val
        else:
            df[req_col] = df[req_col].fillna(def_val).astype(str).str.strip()

    df = df[df["Nama Donatur"].str.len() > 0]
    return df

@st.cache_data(ttl=60, show_spinner=False)
def load_all_realtime_data():
    db = {}
    live_synced = 0

    # 1. DATA MAKRO BULANAN (Januari - Oktober)
    db['macro_monthly'] = pd.DataFrame([
        {"Bulan": "Januari",   "Target Bulanan": 326000000, "Realisasi Finance": 313838000, "Omset CS": 194267000, "Budget Iklan": 218457000, "Total Pengeluaran": 222889000, "Laba Bersih": 90949200,  "ROFI": 1.44, "ROI_Pct": 40.8,  "Status Target": "Tidak Tercapai", "Mushaf Terverifikasi": 2356},
        {"Bulan": "Februari",  "Target Bulanan": 522000000, "Realisasi Finance": 244568000, "Omset CS": 230443000, "Budget Iklan": 228843000, "Total Pengeluaran": 232374000, "Laba Bersih": 12194000,  "ROFI": 1.07, "ROI_Pct": 5.2,   "Status Target": "Tidak Tercapai", "Mushaf Terverifikasi": 1906},
        {"Bulan": "Maret",     "Target Bulanan": 835000000, "Realisasi Finance": 432950000, "Omset CS": 443374100, "Budget Iklan": 331054000, "Total Pengeluaran": 334504000, "Laba Bersih": 98446500,  "ROFI": 1.31, "ROI_Pct": 29.4,  "Status Target": "Tidak Tercapai", "Mushaf Terverifikasi": 3814},
        {"Bulan": "April",     "Target Bulanan": 359000000, "Realisasi Finance": 292695000, "Omset CS": 253733400, "Budget Iklan": 262156000, "Total Pengeluaran": 266465000, "Laba Bersih": 26230300,  "ROFI": 1.12, "ROI_Pct": 9.8,   "Status Target": "Tidak Tercapai", "Mushaf Terverifikasi": 2225},
        {"Bulan": "Mei",       "Target Bulanan": 395029000, "Realisasi Finance": 485195000, "Omset CS": 154142300, "Budget Iklan": 335053000, "Total Pengeluaran": 338597000, "Laba Bersih": 146597000, "ROFI": 1.45, "ROI_Pct": 43.3,  "Status Target": "Tercapai",       "Mushaf Terverifikasi": 1454},
        {"Bulan": "Juni",      "Target Bulanan": 434532000, "Realisasi Finance": 457976000, "Omset CS": 408027750, "Budget Iklan": 345054000, "Total Pengeluaran": 356438000, "Laba Bersih": 101538000, "ROFI": 1.33, "ROI_Pct": 28.5,  "Status Target": "Tercapai",       "Mushaf Terverifikasi": 4103},
        {"Bulan": "Juli",      "Target Bulanan": 477986000, "Realisasi Finance": 490683000, "Omset CS": 374520900, "Budget Iklan": 345049000, "Total Pengeluaran": 353467000, "Laba Bersih": 137216000, "ROFI": 1.42, "ROI_Pct": 38.8,  "Status Target": "Tercapai",       "Mushaf Terverifikasi": 3586},
        {"Bulan": "Agustus",   "Target Bulanan": 525784000, "Realisasi Finance": 371847000, "Omset CS": 290718820, "Budget Iklan": 320040000, "Total Pengeluaran": 322971000, "Laba Bersih": 48876700,  "ROFI": 1.16, "ROI_Pct": 15.1,  "Status Target": "Tidak Tercapai", "Mushaf Terverifikasi": 2852},
        {"Bulan": "September", "Target Bulanan": 350000000, "Realisasi Finance": 310384000, "Omset CS": 272608400, "Budget Iklan": 254360000, "Total Pengeluaran": 107038000, "Laba Bersih": 203346000, "ROFI": 1.22, "ROI_Pct": 190.0, "Status Target": "Tidak Tercapai", "Mushaf Terverifikasi": 2599},
        {"Bulan": "Oktober",   "Target Bulanan": 500000000, "Realisasi Finance": 132353000, "Omset CS": 108674008, "Budget Iklan": 114820000, "Total Pengeluaran": 114820000, "Laba Bersih": 17533000,  "ROFI": 1.15, "ROI_Pct": 15.3,  "Status Target": "Realtime",       "Mushaf Terverifikasi": 929},
    ])

    grid_ov = fetch_raw_grid("data_cs", "Overview_Semua_CS")
    if not grid_ov.empty:
        live_synced += 1
        t_fin_live = extract_anchored_table(grid_ov, "Bulan", "Target Bulanan", stop_words=["Total Target", "Sisa Target"], max_rows=14)
        if not t_fin_live.empty and "Realisasi Omset" in t_fin_live.columns:
            for _, r_live in t_fin_live.iterrows():
                b_name = str(r_live["Bulan"]).strip()
                if b_name in db['macro_monthly']['Bulan'].values:
                    v_real = num_clean(r_live.get("Realisasi Omset", 0))
                    v_tgt = num_clean(r_live.get("Target Bulanan", 0))
                    v_ads = num_clean(r_live.get("Budget Iklan", 0))
                    if v_real > 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'Realisasi Finance'] = v_real
                    if v_tgt > 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'Target Bulanan'] = v_tgt
                    if v_ads > 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'Budget Iklan'] = v_ads

    df_m = db['macro_monthly']
    df_m['Selisih Target'] = df_m['Realisasi Finance'] - df_m['Target Bulanan']
    df_m['Selisih Finance vs CS'] = df_m['Realisasi Finance'] - df_m['Omset CS']
    df_m['% Capaian'] = np.where(df_m['Target Bulanan'] > 0, (df_m['Realisasi Finance'] / df_m['Target Bulanan'] * 100).round(1), 0.0)

    # 2. DATA PENDAPATAN INDIVIDU CS (Jan-Okt)
    db['cs_overview'] = pd.DataFrame([
        {"Rank": 1, "Nama CS": "Nisa",   "Status Okt": "Aktif",     "Target Omset": 1200000000, "Januari": 15839000,  "Februari": 68093999,  "Maret": 196005644, "April": 125603001, "Mei": 74540362, "Juni": 200017711, "Juli": 197594767, "Agustus": 84384400,  "September": 71315000, "Oktober": 65998000, "Total Omset (Jan-Sep)": 1033393884, "Total Closing": 6219, "AOV": 166167, "Pencapaian (%)": "86,1%", "Kontribusi (%)": "39,4%"},
        {"Rank": 2, "Nama CS": "Salma",  "Status Okt": "Aktif",     "Target Omset": 1200000000, "Januari": 153161444, "Februari": 130171224, "Maret": 201796334, "April": 85285000,  "Mei": 50347999, "Juni": 121468905, "Juli": 79080000,  "Agustus": 104793000, "September": 72695000, "Oktober": 32863008, "Total Omset (Jan-Sep)": 998798907,  "Total Closing": 5898, "AOV": 169345, "Pencapaian (%)": "83,2%", "Kontribusi (%)": "38,1%"},
        {"Rank": 3, "Nama CS": "Aulia",  "Status Okt": "Aktif",     "Target Omset": 500000000,  "Januari": 0,         "Februari": 396000,    "Maret": 1894000,   "April": 11719000,  "Mei": 11748999, "Juni": 76174000,  "Juli": 84631886,  "Agustus": 84775000,  "September": 64809000, "Oktober": 9813000,  "Total Omset (Jan-Sep)": 336147885,  "Total Closing": 2128, "AOV": 157964, "Pencapaian (%)": "67,2%", "Kontribusi (%)": "12,8%"},
        {"Rank": 4, "Nama CS": "Desi",   "Status Okt": "Non-Aktif", "Target Omset": 200000000,  "Januari": 25267000,  "Februari": 26163000,  "Maret": 3342596,   "April": 23010375,  "Mei": 9298900,  "Juni": 4316750,   "Juli": 6395000,   "Agustus": 4917625,   "September": 42651438, "Oktober": 0,        "Total Omset (Jan-Sep)": 145362684,  "Total Closing": 924,  "AOV": 157319, "Pencapaian (%)": "72,7%", "Kontribusi (%)": "5,5%"},
        {"Rank": 5, "Nama CS": "Syafiq", "Status Okt": "Non-Aktif", "Target Omset": 0,          "Januari": 0,         "Februari": 5619000,   "Maret": 35515478,  "April": 8116000,   "Mei": 8206000,  "Juni": 6050000,   "Juli": 0,         "Agustus": 0,         "September": 0,        "Oktober": 0,        "Total Omset (Jan-Sep)": 63506478,   "Total Closing": 257,  "AOV": 247107, "Pencapaian (%)": "0,0%",  "Kontribusi (%)": "2,4%"},
        {"Rank": 6, "Nama CS": "Rida",   "Status Okt": "Non-Aktif", "Target Omset": 150000000,  "Januari": 0,         "Februari": 0,         "Maret": 0,         "April": 0,         "Mei": 0,        "Juni": 0,         "Juli": 2495000,   "Agustus": 5128000,   "September": 15148000, "Oktober": 0,        "Total Omset (Jan-Sep)": 22771000,   "Total Closing": 150,  "AOV": 151807, "Pencapaian (%)": "15,2%", "Kontribusi (%)": "0,9%"},
        {"Rank": 7, "Nama CS": "Olive",  "Status Okt": "Aktif CRM", "Target Omset": 0,          "Januari": 0,         "Februari": 0,         "Maret": 0,         "April": 0,         "Mei": 0,        "Juni": 0,         "Juli": 4324000,   "Agustus": 6720800,   "September": 5990000,  "Oktober": 1296500,  "Total Omset (Jan-Sep)": 17034800,   "Total Closing": 106,  "AOV": 160706, "Pencapaian (%)": "0,0%",  "Kontribusi (%)": "0,6%"},
        {"Rank": 8, "Nama CS": "Sarah",  "Status Okt": "Non-Aktif", "Target Omset": 100000000,  "Januari": 0,         "Februari": 0,         "Maret": 4820000,   "April": 0,         "Mei": 0,        "Juni": 0,         "Juli": 0,         "Agustus": 0,         "September": 0,        "Oktober": 0,        "Total Omset (Jan-Sep)": 4820000,    "Total Closing": 23,   "AOV": 209565, "Pencapaian (%)": "4,8%",  "Kontribusi (%)": "0,2%"},
    ])

    # 3. DATA REALTIME OKTOBER (Sheet "Dashboard CS")
    db['okt_kpi'] = {
        "total_donasi": 108674008, "target": 500000000, "capaian_pct": 21.7,
        "donasi_final": 102046008, "harian_terbaru": 8861008, "verifikasi_pct": 93.9
    }
    db['okt_cs_table'] = pd.DataFrame([
        {"CS / CRM": "Salma",         "Harian (Total)": 2464008, "Harian (Final)": 2464008, "Mingguan (Total)": 2464008, "Mingguan (Final)": 2464008, "Bulanan (Total)": 32863008, "Bulanan (Final)": 29870008, "% Verifikasi": "90,9%", "Total Transaksi": 227, "Target (Rp)": 200000000, "% Capaian": "16,4%"},
        {"CS / CRM": "Aulia",         "Harian (Total)": 453000,  "Harian (Final)": 453000,  "Mingguan (Total)": 453000,  "Mingguan (Final)": 453000,  "Bulanan (Total)": 9813000,  "Bulanan (Final)": 8983000,  "% Verifikasi": "91,5%", "Total Transaksi": 93,  "Target (Rp)": 50000000,  "% Capaian": "19,6%"},
        {"CS / CRM": "Nisa",          "Harian (Total)": 5944000, "Harian (Final)": 5944000, "Mingguan (Total)": 5944000, "Mingguan (Final)": 5944000, "Bulanan (Total)": 65998000, "Bulanan (Final)": 63193000, "% Verifikasi": "95,7%", "Total Transaksi": 440, "Target (Rp)": 200000000, "% Capaian": "33,0%"},
        {"CS / CRM": "CRM Baru",      "Harian (Total)": 0,       "Harian (Final)": 0,       "Mingguan (Total)": 0,       "Mingguan (Final)": 0,       "Bulanan (Total)": 0,        "Bulanan (Final)": 0,        "% Verifikasi": "0,0%",  "Total Transaksi": 0,   "Target (Rp)": 50000000,  "% Capaian": "0,0%"},
        {"CS / CRM": "Admin Yayasan", "Harian (Total)": 0,       "Harian (Final)": 0,       "Mingguan (Total)": 0,       "Mingguan (Final)": 0,       "Bulanan (Total)": 0,        "Bulanan (Final)": 0,        "% Verifikasi": "0,0%",  "Total Transaksi": 0,   "Target (Rp)": 0,         "% Capaian": "0,0%"},
    ])
    db['okt_sumber'] = pd.DataFrame([
        {"CS / CRM": "Salma", "Leads Meta": 29204000, "Repeat Order CRM": 0,       "Repeat Order non CRM": 3059000, "Lainnya": 600000,  "Total Nominal": 32863008, "% Leads Meta": "88,9%"},
        {"CS / CRM": "Aulia", "Leads Meta": 1044000,  "Repeat Order CRM": 5639000, "Repeat Order non CRM": 0,       "Lainnya": 3130000, "Total Nominal": 9813000,  "% Leads Meta": "10,6%"},
        {"CS / CRM": "Nisa",  "Leads Meta": 60194000, "Repeat Order CRM": 0,       "Repeat Order non CRM": 4613000, "Lainnya": 1191000, "Total Nominal": 65998000, "% Leads Meta": "91,2%"},
    ])
    db['okt_harian'] = pd.DataFrame([
        {"Tanggal": "2026-10-01", "Salma": 2464008, "Aulia": 453000,  "Nisa": 5944000, "Total Donasi": 8861008,  "Donasi Final": 8861008},
        {"Tanggal": "2026-10-02", "Salma": 4991000, "Aulia": 1591000, "Nisa": 8901000, "Total Donasi": 15483000, "Donasi Final": 15084000},
        {"Tanggal": "2026-10-03", "Salma": 1665000, "Aulia": 657000,  "Nisa": 2292000, "Total Donasi": 4614000,  "Donasi Final": 4414000},
        {"Tanggal": "2026-10-04", "Salma": 2323000, "Aulia": 283000,  "Nisa": 3785000, "Total Donasi": 6391000,  "Donasi Final": 6386000},
        {"Tanggal": "2026-10-05", "Salma": 1425000, "Aulia": 2079000, "Nisa": 3881000, "Total Donasi": 7385000,  "Donasi Final": 7385000},
        {"Tanggal": "2026-10-06", "Salma": 2066000, "Aulia": 1274000, "Nisa": 3586000, "Total Donasi": 6926000,  "Donasi Final": 6926000},
        {"Tanggal": "2026-10-07", "Salma": 1112000, "Aulia": 454000,  "Nisa": 3311000, "Total Donasi": 4877000,  "Donasi Final": 4778000},
        {"Tanggal": "2026-10-08", "Salma": 1305000, "Aulia": 653000,  "Nisa": 5965000, "Total Donasi": 7923000,  "Donasi Final": 7518000},
        {"Tanggal": "2026-10-09", "Salma": 6096000, "Aulia": 853000,  "Nisa": 8885000, "Total Donasi": 15834000, "Donasi Final": 15329000},
        {"Tanggal": "2026-10-10", "Salma": 2488000, "Aulia": 807000,  "Nisa": 2048000, "Total Donasi": 5343000,  "Donasi Final": 5238000},
        {"Tanggal": "2026-10-11", "Salma": 1346000, "Aulia": 255000,  "Nisa": 4687950, "Total Donasi": 6288950,  "Donasi Final": 6283950},
        {"Tanggal": "2026-10-12", "Salma": 1447000, "Aulia": 154000,  "Nisa": 4530000, "Total Donasi": 6131000,  "Donasi Final": 6126000},
        {"Tanggal": "2026-10-13", "Salma": 1242000, "Aulia": 300000,  "Nisa": 8182000, "Total Donasi": 9724000,  "Donasi Final": 7717000},
        {"Tanggal": "2026-10-14", "Salma": 2893000, "Aulia": 0,       "Nisa": 0,       "Total Donasi": 2893000,  "Donasi Final": 0},
    ])

    grid_okt = fetch_raw_grid("bulan_oktober", "Dashboard CS")
    if not grid_okt.empty:
        live_synced += 1
        t_cs_okt = extract_anchored_table(grid_okt, "CS / CRM", "Harian (Total)", stop_words=["TOTAL", "ANALISIS"], max_rows=10)
        if not t_cs_okt.empty and "Bulanan (Total)" in t_cs_okt.columns:
            for col_n in ["Harian (Total)", "Harian (Final)", "Mingguan (Total)", "Mingguan (Final)", "Bulanan (Total)", "Bulanan (Final)", "Target (Rp)"]:
                if col_n in t_cs_okt.columns:
                    t_cs_okt[col_n] = t_cs_okt[col_n].apply(num_clean)
            if "Total Transaksi" in t_cs_okt.columns:
                t_cs_okt["Total Transaksi"] = t_cs_okt["Total Transaksi"].apply(lambda x: int(num_clean(x)))
            db['okt_cs_table'] = t_cs_okt
            db['okt_kpi']['total_donasi'] = t_cs_okt['Bulanan (Total)'].sum()
            db['okt_kpi']['donasi_final'] = t_cs_okt['Bulanan (Final)'].sum()

    # 4. DATA PENGELOLAAN LEADS CS AKTIF OKTOBER
    leads_rows = [
        ("Nisa", "2026-10-01", 54, 4, 44, 6052000, 54, 44, 6052000, 0, 0, 0, 0, 0, 0, 0),
        ("Nisa", "2026-10-02", 59, 14, 55, 7606000, 53, 50, 7110000, 0, 0, 0, 6, 5, 496000, 0),
        ("Nisa", "2026-10-03", 20, 2, 20, 2689000, 20, 20, 2689000, 0, 0, 0, 0, 0, 0, 0),
        ("Nisa", "2026-10-04", 35, 4, 27, 4035000, 35, 27, 4035000, 0, 0, 0, 0, 0, 0, 0),
        ("Nisa", "2026-10-05", 35, 0, 25, 3488000, 35, 24, 3389000, 0, 0, 0, 0, 1, 99000, 0),
        ("Nisa", "2026-10-06", 35, 4, 29, 3377000, 35, 28, 3278000, 0, 0, 0, 0, 1, 99000, 0),
        ("Nisa", "2026-10-07", 36, 6, 26, 3662000, 36, 26, 3662000, 0, 0, 0, 0, 0, 0, 0),
        ("Nisa", "2026-10-08", 26, 4, 20, 5092000, 26, 20, 5092000, 0, 0, 0, 0, 0, 0, 11),
        ("Nisa", "2026-10-09", 68, 11, 45, 8500000, 68, 44, 8250000, 0, 0, 0, 0, 1, 250000, 16),
        ("Nisa", "2026-10-10", 26, 4, 22, 2367000, 26, 22, 2367000, 0, 0, 0, 0, 0, 0, 9),
        ("Nisa", "2026-10-11", 33, 8, 22, 4012950, 33, 22, 4012950, 0, 0, 0, 0, 0, 0, 15),
        ("Nisa", "2026-10-12", 34, 1, 29, 4006000, 34, 29, 4006000, 0, 0, 0, 0, 0, 0, 10),
        ("Nisa", "2026-10-13", 70, 8, 52, 8922000, 70, 52, 8922000, 0, 0, 0, 0, 0, 0, 27),
        ("Nisa", "2026-10-14", 49, 11, 28, 4362000, 47, 28, 4362000, 0, 0, 0, 2, 0, 0, 17),
        ("Nisa", "2026-10-15", 62, 10, 41, 6937000, 62, 41, 6937000, 0, 0, 0, 0, 0, 0, 12),
        ("Nisa", "2026-10-16", 86, 10, 54, 8601000, 86, 54, 8601000, 0, 0, 0, 0, 0, 0, 0),
        ("Salma", "2026-10-01", 27, 3, 21, 2438000, 5, 5, 695000, 1, 1, 150000, 21, 15, 1593000, 0),
        ("Salma", "2026-10-02", 23, 5, 19, 3049000, 7, 6, 726000, 0, 0, 0, 16, 13, 2323000, 0),
        ("Salma", "2026-10-03", 12, 2, 12, 1845000, 1, 1, 99000, 0, 0, 0, 11, 11, 1746000, 0),
        ("Salma", "2026-10-04", 25, 4, 19, 2398000, 1, 1, 100000, 1, 1, 99000, 23, 17, 2199000, 0),
        ("Salma", "2026-10-05", 18, 3, 14, 1974000, 0, 0, 0, 1, 1, 99000, 17, 13, 1875000, 0),
        ("Salma", "2026-10-06", 12, 1, 12, 1416000, 4, 4, 398000, 0, 0, 0, 8, 8, 1018000, 0),
        ("Salma", "2026-10-07", 7, 0, 7, 912000, 0, 0, 0, 0, 0, 0, 7, 7, 912000, 0),
        ("Salma", "2026-10-08", 9, 1, 8, 1224000, 0, 0, 0, 0, 0, 0, 9, 8, 1224000, 0),
        ("Salma", "2026-10-09", 29, 6, 26, 4515000, 1, 1, 130000, 0, 0, 0, 28, 25, 4385000, 0),
        ("Salma", "2026-10-10", 12, 6, 11, 1591000, 0, 0, 0, 0, 0, 0, 12, 11, 1591000, 0),
        ("Salma", "2026-10-11", 12, 4, 8, 1397000, 0, 0, 0, 0, 0, 0, 12, 8, 1397000, 0),
        ("Salma", "2026-10-12", 10, 3, 8, 1097000, 0, 0, 0, 0, 0, 0, 10, 8, 1097000, 0),
        ("Salma", "2026-10-13", 14, 6, 12, 1488000, 0, 0, 0, 0, 0, 0, 14, 12, 1488000, 0),
        ("Salma", "2026-10-14", 17, 7, 14, 3688000, 0, 0, 0, 0, 0, 0, 17, 14, 3688000, 0),
        ("Salma", "2026-10-15", 6, 0, 4, 496000, 0, 0, 0, 0, 0, 0, 6, 4, 496000, 0),
        ("Salma", "2026-10-16", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ("Aulia", "2026-10-01", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ("Aulia", "2026-10-02", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ("Aulia", "2026-10-03", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ("Aulia", "2026-10-04", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ("Aulia", "2026-10-05", 4, 0, 2, 224000, 0, 0, 0, 0, 0, 0, 4, 2, 224000, 0),
        ("Aulia", "2026-10-06", 7, 2, 5, 719000, 0, 0, 0, 0, 0, 0, 7, 5, 719000, 0),
        ("Aulia", "2026-10-07", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    ]
    df_leads = pd.DataFrame(leads_rows, columns=[
        "Nama CS", "Tanggal", "Chat Valid", "Chat Invalid", "Closing", "Nominal",
        "SantriQu_Leads", "SantriQu_Closing", "SantriQu_Nominal",
        "JariyahQu_Leads", "JariyahQu_Closing", "JariyahQu_Nominal",
        "AmalQu_Leads", "AmalQu_Closing", "AmalQu_Nominal", "Total Follow Up"
    ])
    df_leads["Conv Rate (%)"] = np.where(df_leads["Chat Valid"] > 0, (df_leads["Closing"] / df_leads["Chat Valid"] * 100).round(1), 0.0)
    db['leads_okt'] = df_leads

    # 5. DATA LOGISTIK: PEMISAHAN STOK SIAP SALUR VS BELUM STIKER & SINKRONISASI JADWAL DISTRIBUSI
    db['master_stok_rt'] = pd.DataFrame([
        {"ID Produk": "ST-META-01", "Nama Produk / Mushaf": "Super Tajwid",             "Channel Perolehan": "Meta Ads",     "Status Stiker & Fisik": "Sudah Tempel Stiker", "Kategori": "Mushaf Al-Qur'an", "Stok Awal": 861,  "Total Masuk": 0,   "Total Terdistribusi": 60,  "Stok Akhir Real-Time": 801,  "Status Stok": "Tersedia", "Catatan / Lokasi": "Siap distribusi operasional"},
        {"ID Produk": "AW-META-01", "Nama Produk / Mushaf": "Al Wakaf",                 "Channel Perolehan": "Meta Ads",     "Status Stiker & Fisik": "Sudah Tempel Stiker", "Kategori": "Mushaf Al-Qur'an", "Stok Awal": 288,  "Total Masuk": 50,  "Total Terdistribusi": 40,  "Stok Akhir Real-Time": 298,  "Status Stok": "Tersedia", "Catatan / Lokasi": "Siap kirim ke penerima manfaat"},
        {"ID Produk": "AW-META-02", "Nama Produk / Mushaf": "Al Wakaf",                 "Channel Perolehan": "Meta Ads",     "Status Stiker & Fisik": "Belum Tempel Stiker", "Kategori": "Mushaf Al-Qur'an", "Stok Awal": 480,  "Total Masuk": 0,   "Total Terdistribusi": 0,   "Stok Akhir Real-Time": 480,  "Status Stok": "Tersedia", "Catatan / Lokasi": "Lokasi: Ruang AmalQu (10 box x 48)"},
        {"ID Produk": "AW-META-03", "Nama Produk / Mushaf": "Al Wakaf",                 "Channel Perolehan": "Meta Ads",     "Status Stiker & Fisik": "Belum Diambil",       "Kategori": "Mushaf Al-Qur'an", "Stok Awal": 1848, "Total Masuk": 0,   "Total Terdistribusi": 0,   "Stok Akhir Real-Time": 1848, "Status Stok": "Tersedia", "Catatan / Lokasi": "Sisa PO belum diambil percetakan"},
        {"ID Produk": "AW-TIK-01",  "Nama Produk / Mushaf": "Al Wakaf",                 "Channel Perolehan": "TikTok",       "Status Stiker & Fisik": "Sudah Tempel Stiker", "Kategori": "Mushaf Al-Qur'an", "Stok Awal": 20,   "Total Masuk": 0,   "Total Terdistribusi": 0,   "Stok Akhir Real-Time": 20,   "Status Stok": "Menipis",  "Catatan / Lokasi": "Stok berjalan TikTok Ads"},
        {"ID Produk": "BT-TIK-01",  "Nama Produk / Mushaf": "Buku Tahsin",              "Channel Perolehan": "TikTok",       "Status Stiker & Fisik": "Sudah Tempel Stiker", "Kategori": "Buku Tahsin",      "Stok Awal": 1288, "Total Masuk": 200, "Total Terdistribusi": 100, "Stok Akhir Real-Time": 1388, "Status Stok": "Tersedia", "Catatan / Lokasi": "Buku Tahsin siap kirim"},
        {"ID Produk": "BT-TIK-02",  "Nama Produk / Mushaf": "Buku Tahsin",              "Channel Perolehan": "TikTok",       "Status Stiker & Fisik": "Belum Tempel Stiker", "Kategori": "Buku Tahsin",      "Stok Awal": 1500, "Total Masuk": 0,   "Total Terdistribusi": 0,   "Stok Akhir Real-Time": 1500, "Status Stok": "Tersedia", "Catatan / Lokasi": "Menunggu penempelan stiker wakaf"},
    ])
    db['kebutuhan_bulanan'] = pd.DataFrame([
        {"ID Target": "TRG-202610-01", "Periode Bulan": "2026-10-01", "ID Produk": "ST-META-01", "Nama Produk & Channel": "Super Tajwid (Meta Ads)", "Target Kebutuhan": 300, "Realisasi Distribusi": 60,  "Sisa Target (Gap)": 240, "% Capaian": "20,0%", "Status Capaian": "Perlu Perhatian", "Stok Fisik Tersedia": 801,  "Status Kecukupan Stok": "Stok Cukup"},
        {"ID Target": "TRG-202610-02", "Periode Bulan": "2026-10-01", "ID Produk": "AW-META-01", "Nama Produk & Channel": "Al Wakaf (Meta Ads)",     "Target Kebutuhan": 500, "Realisasi Distribusi": 40,  "Sisa Target (Gap)": 460, "% Capaian": "8,0%",  "Status Capaian": "Perlu Perhatian", "Stok Fisik Tersedia": 298,  "Status Kecukupan Stok": "Defisit Stok"},
        {"ID Target": "TRG-202610-03", "Periode Bulan": "2026-10-01", "ID Produk": "AW-TIK-01",  "Nama Produk & Channel": "Al Wakaf (TikTok)",       "Target Kebutuhan": 250, "Realisasi Distribusi": 0,   "Sisa Target (Gap)": 250, "% Capaian": "0,0%",  "Status Capaian": "Perlu Perhatian", "Stok Fisik Tersedia": 20,   "Status Kecukupan Stok": "Defisit Stok"},
        {"ID Target": "TRG-202610-04", "Periode Bulan": "2026-10-01", "ID Produk": "BT-TIK-01",  "Nama Produk & Channel": "Buku Tahsin (TikTok)",    "Target Kebutuhan": 300, "Realisasi Distribusi": 100, "Sisa Target (Gap)": 200, "% Capaian": "33,3%", "Status Capaian": "Perlu Perhatian", "Stok Fisik Tersedia": 1388, "Status Kecukupan Stok": "Stok Cukup"},
    ])
    db['log_mutasi'] = pd.DataFrame([
        {"No Mutasi": "MUT-2026-001", "Tanggal": "2026-10-15", "Jenis Mutasi": "Masuk",             "ID Produk": "AW-META-01", "Nama Produk & Detail": "Al Wakaf (Meta Ads - Sudah Tempel Stiker)",     "Jumlah (Pcs)": 50,  "Penerima Wakaf / Sasaran": "Gudang AmalQu",                   "Lokasi / Kota Tujuan": "Yogyakarta", "No Resi / Ekspedisi": "Tanda Terima Percetakan", "Penanggung Jawab (PIC)": "Tim Logistik"},
        {"No Mutasi": "MUT-2026-002", "Tanggal": "2026-10-15", "Jenis Mutasi": "Distribusi Keluar", "ID Produk": "ST-META-01", "Nama Produk & Detail": "Super Tajwid (Meta Ads - Sudah Tempel Stiker)", "Jumlah (Pcs)": 60,  "Penerima Wakaf / Sasaran": "Pesantren Tahfidz Baitul Qur'an", "Lokasi / Kota Tujuan": "Bandung",    "No Resi / Ekspedisi": "JNE JTR - 01293847",      "Penanggung Jawab (PIC)": "Ustadz Ahmad"},
        {"No Mutasi": "MUT-2026-003", "Tanggal": "2026-10-16", "Jenis Mutasi": "Distribusi Keluar", "ID Produk": "AW-META-01", "Nama Produk & Detail": "Al Wakaf (Meta Ads - Sudah Tempel Stiker)",     "Jumlah (Pcs)": 40,  "Penerima Wakaf / Sasaran": "Masjid Jami' Al-Hidayah",         "Lokasi / Kota Tujuan": "Garut",      "No Resi / Ekspedisi": "Wahana - 9928172",        "Penanggung Jawab (PIC)": "Relawan AmalQu"},
        {"No Mutasi": "MUT-2026-004", "Tanggal": "2026-10-16", "Jenis Mutasi": "Distribusi Keluar", "ID Produk": "BT-TIK-01",  "Nama Produk & Detail": "Buku Tahsin (TikTok - Sudah Tempel Stiker)",    "Jumlah (Pcs)": 100, "Penerima Wakaf / Sasaran": "Komunitas Belajar Tahsin Desa",   "Lokasi / Kota Tujuan": "Sukabumi",   "No Resi / Ekspedisi": "SiCepat Cargo - 8374621", "Penanggung Jawab (PIC)": "Tim TikTok"},
        {"No Mutasi": "MUT-2026-005", "Tanggal": "2026-10-17", "Jenis Mutasi": "Masuk",             "ID Produk": "BT-TIK-01",  "Nama Produk & Detail": "Buku Tahsin (TikTok - Sudah Tempel Stiker)",    "Jumlah (Pcs)": 200, "Penerima Wakaf / Sasaran": "Gudang Transit",                  "Lokasi / Kota Tujuan": "Jakarta",    "No Resi / Ekspedisi": "Serah Terima Stiker",     "Penanggung Jawab (PIC)": "Tim QC"},
    ])
    db['packing_dus_bulanan'] = pd.DataFrame([
        {"Bulan": "Januari",   "Total Mushaf Terverifikasi": 2356, "Verifikasi (Belum Stiker)": 0,    "Penamaan Mushaf (Stiker)": 0,   "Packing / Proses Distribusi": 0,    "Distribusi Selesai": 2356},
        {"Bulan": "Februari",  "Total Mushaf Terverifikasi": 1906, "Verifikasi (Belum Stiker)": 0,    "Penamaan Mushaf (Stiker)": 0,   "Packing / Proses Distribusi": 0,    "Distribusi Selesai": 1906},
        {"Bulan": "Maret",     "Total Mushaf Terverifikasi": 3814, "Verifikasi (Belum Stiker)": 0,    "Penamaan Mushaf (Stiker)": 0,   "Packing / Proses Distribusi": 0,    "Distribusi Selesai": 3814},
        {"Bulan": "April",     "Total Mushaf Terverifikasi": 2225, "Verifikasi (Belum Stiker)": 0,    "Penamaan Mushaf (Stiker)": 0,   "Packing / Proses Distribusi": 0,    "Distribusi Selesai": 2225},
        {"Bulan": "Mei",       "Total Mushaf Terverifikasi": 1454, "Verifikasi (Belum Stiker)": 0,    "Penamaan Mushaf (Stiker)": 0,   "Packing / Proses Distribusi": 0,    "Distribusi Selesai": 1454},
        {"Bulan": "Juni",      "Total Mushaf Terverifikasi": 4103, "Verifikasi (Belum Stiker)": 0,    "Penamaan Mushaf (Stiker)": 0,   "Packing / Proses Distribusi": 0,    "Distribusi Selesai": 4103},
        {"Bulan": "Juli",      "Total Mushaf Terverifikasi": 3586, "Verifikasi (Belum Stiker)": 1,    "Penamaan Mushaf (Stiker)": 0,   "Packing / Proses Distribusi": 0,    "Distribusi Selesai": 3585},
        {"Bulan": "Agustus",   "Total Mushaf Terverifikasi": 2852, "Verifikasi (Belum Stiker)": 12,   "Penamaan Mushaf (Stiker)": 0,   "Packing / Proses Distribusi": 2840, "Distribusi Selesai": 0},
        {"Bulan": "September", "Total Mushaf Terverifikasi": 2599, "Verifikasi (Belum Stiker)": 1972, "Penamaan Mushaf (Stiker)": 447, "Packing / Proses Distribusi": 180,  "Distribusi Selesai": 0},
        {"Bulan": "Oktober",   "Total Mushaf Terverifikasi": 929,  "Verifikasi (Belum Stiker)": 928,  "Penamaan Mushaf (Stiker)": 1,   "Packing / Proses Distribusi": 0,    "Distribusi Selesai": 0},
    ])

    grid_ms = fetch_raw_grid("stok_mushaf", "Master_Stok_Real-Time")
    if not grid_ms.empty:
        live_synced += 1
        t_ms = extract_anchored_table(grid_ms, "ID Produk", "Nama Produk / Mushaf", max_rows=20)
        if not t_ms.empty and "Stok Akhir Real-Time" in t_ms.columns:
            for col_i in ["Stok Awal", "Total Masuk", "Total Terdistribusi", "Stok Akhir Real-Time"]:
                if col_i in t_ms.columns:
                    t_ms[col_i] = t_ms[col_i].apply(lambda x: int(num_clean(x)))
            db['master_stok_rt'] = t_ms

    # 6. DATA KALENDER DISTRIBUSI OKTOBER 2026 (Kolom A-J)
    db['kalender_okt'] = pd.DataFrame([
        {"No": 1, "Tanggal Agenda": "2026-10-20", "ID Proyek": "AQ-2026-087", "Nama Lembaga Penerima": "MDU AL-ITTIHAD CIHERANG CIPELAH",    "Nama PIC": "Abdul Karim",             "Kontak WA": "Terdaftar", "Wilayah / Titik Lokasi": "Rancabali, Kab. Bandung",          "Jumlah Mushaf (Pcs)": 108, "Variasi Mushaf": "Super Tajwid",    "Status": "Scheduled"},
        {"No": 2, "Tanggal Agenda": "2026-10-22", "ID Proyek": "AQ-2026-074", "Nama Lembaga Penerima": "TPA Al Hijrah",                      "Nama PIC": "Arip Rohman",             "Kontak WA": "Terdaftar", "Wilayah / Titik Lokasi": "Sidomulyo, Kab. Lampung Selatan",  "Jumlah Mushaf (Pcs)": 45,  "Variasi Mushaf": "Super Tajwid",    "Status": "Scheduled"},
        {"No": 3, "Tanggal Agenda": "2026-10-22", "ID Proyek": "AQ-2026-105", "Nama Lembaga Penerima": "IRMA Baitul Ummah",                  "Nama PIC": "Hj. Intan Margaretha F.", "Kontak WA": "Terdaftar", "Wilayah / Titik Lokasi": "SMKN 1 Katapang, Kab. Bandung",    "Jumlah Mushaf (Pcs)": 200, "Variasi Mushaf": "Super Tajwid",    "Status": "Scheduled"},
        {"No": 4, "Tanggal Agenda": "2026-10-23", "ID Proyek": "AQ-2026-008", "Nama Lembaga Penerima": "KBMA Desa Margahayu Selatan",        "Nama PIC": "Ibu Ade",                 "Kontak WA": "Terdaftar", "Wilayah / Titik Lokasi": "Masjid Alfurqon, Margahayu Sel.", "Jumlah Mushaf (Pcs)": 150, "Variasi Mushaf": "Super Tajwid",    "Status": "Scheduled"},
        {"No": 5, "Tanggal Agenda": "2026-10-24", "ID Proyek": "AQ-2026-058", "Nama Lembaga Penerima": "Majelis Ta'lim Ciparay",             "Nama PIC": "Bu. Dadang / Nur Erlina", "Kontak WA": "Terdaftar", "Wilayah / Titik Lokasi": "Ciparay, Kab. Bandung",            "Jumlah Mushaf (Pcs)": 150, "Variasi Mushaf": "Super Tajwid",    "Status": "Scheduled"},
        {"No": 6, "Tanggal Agenda": "2026-10-27", "ID Proyek": "AQ-2026-026", "Nama Lembaga Penerima": "SD Plus Al Furqan",                  "Nama PIC": "Dedeh Kurniati",          "Kontak WA": "Terdaftar", "Wilayah / Titik Lokasi": "SD Plus Al Furqon Cimahi",         "Jumlah Mushaf (Pcs)": 114, "Variasi Mushaf": "Al Wakaf Tiktok", "Status": "Scheduled"},
        {"No": 7, "Tanggal Agenda": "2026-10-27", "ID Proyek": "AQ-2026-059", "Nama Lembaga Penerima": "Yayasan Bahtera Peradaban Cendekia", "Nama PIC": "Rona Rohmana",            "Kontak WA": "Terdaftar", "Wilayah / Titik Lokasi": "Saguling, Kab. Bandung Barat",     "Jumlah Mushaf (Pcs)": 67,  "Variasi Mushaf": "Al Wakaf Tiktok", "Status": "Scheduled"},
        {"No": 8, "Tanggal Agenda": "2026-10-29", "ID Proyek": "AQ-2026-072", "Nama Lembaga Penerima": "TPQ Tarbiyatul Aulad",               "Nama PIC": "Ust. Fandy Abdillah",     "Kontak WA": "Terdaftar", "Wilayah / Titik Lokasi": "Sukanagara, Kab. Cianjur",         "Jumlah Mushaf (Pcs)": 70,  "Variasi Mushaf": "Al Wakaf Tiktok", "Status": "Scheduled"},
        {"No": 9, "Tanggal Agenda": "2026-10-31", "ID Proyek": "AQ-2026-104", "Nama Lembaga Penerima": "MDTA Darul Jannah",                  "Nama PIC": "Ai Neni",                 "Kontak WA": "Terdaftar", "Wilayah / Titik Lokasi": "Jawa Barat",                       "Jumlah Mushaf (Pcs)": 100, "Variasi Mushaf": "Al Wakaf Tiktok", "Status": "Scheduled"},
    ])

    grid_kal = fetch_raw_grid("kalender_dist", "Kalender Oktober 2026")
    if not grid_kal.empty:
        live_synced += 1
        t_kal = extract_anchored_table(grid_kal, "No", "Tanggal Agenda", stop_words=["TOTAL"], max_rows=30)
        if not t_kal.empty and "Nama Lembaga Penerima" in t_kal.columns:
            cols_aj = t_kal.columns[:10].tolist()
            t_kal_aj = t_kal[cols_aj].copy()
            if "Jumlah Mushaf (Pcs)" in t_kal_aj.columns:
                t_kal_aj["Jumlah Mushaf (Pcs)"] = t_kal_aj["Jumlah Mushaf (Pcs)"].apply(lambda x: int(num_clean(x)))
            t_kal_aj = t_kal_aj[t_kal_aj["Nama Lembaga Penerima"].astype(str).str.strip() != ""]
            if not t_kal_aj.empty:
                db['kalender_okt'] = t_kal_aj

    # KALKULASI PEMISAHAN STOK SIAP SALUR VS BELUM STIKER & SINKRONISASI JADWAL DISTRIBUSI
    df_ms = db['master_stok_rt']
    df_kal = db['kalender_okt']

    st_siap = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Super Tajwid', case=False, na=False)) & (df_ms['Status Stiker & Fisik'].str.contains('Sudah', case=False, na=False))]['Stok Akhir Real-Time'].sum())
    st_belum = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Super Tajwid', case=False, na=False)) & (~df_ms['Status Stiker & Fisik'].str.contains('Sudah', case=False, na=False))]['Stok Akhir Real-Time'].sum())

    aw_meta_siap = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Al Wakaf', case=False, na=False)) & (df_ms['Channel Perolehan'].str.contains('Meta', case=False, na=False)) & (df_ms['Status Stiker & Fisik'].str.contains('Sudah', case=False, na=False))]['Stok Akhir Real-Time'].sum())
    aw_meta_belum_stiker = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Al Wakaf', case=False, na=False)) & (df_ms['Status Stiker & Fisik'].str.contains('Belum Tempel', case=False, na=False))]['Stok Akhir Real-Time'].sum())
    aw_meta_belum_ambil = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Al Wakaf', case=False, na=False)) & (df_ms['Status Stiker & Fisik'].str.contains('Belum Diambil', case=False, na=False))]['Stok Akhir Real-Time'].sum())
    aw_tik_siap = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Al Wakaf', case=False, na=False)) & (df_ms['Channel Perolehan'].str.contains('TikTok', case=False, na=False)) & (df_ms['Status Stiker & Fisik'].str.contains('Sudah', case=False, na=False))]['Stok Akhir Real-Time'].sum())

    aw_total_siap = aw_meta_siap + aw_tik_siap
    aw_total_belum = aw_meta_belum_stiker + aw_meta_belum_ambil

    bt_siap = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Tahsin', case=False, na=False)) & (df_ms['Status Stiker & Fisik'].str.contains('Sudah', case=False, na=False))]['Stok Akhir Real-Time'].sum())
    bt_belum = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Tahsin', case=False, na=False)) & (~df_ms['Status Stiker & Fisik'].str.contains('Sudah', case=False, na=False))]['Stok Akhir Real-Time'].sum())

    jadwal_st = int(df_kal[df_kal['Variasi Mushaf'].astype(str).str.contains('Super Tajwid', case=False, na=False)]['Jumlah Mushaf (Pcs)'].sum()) if 'Variasi Mushaf' in df_kal.columns else 653
    jadwal_aw = int(df_kal[df_kal['Variasi Mushaf'].astype(str).str.contains('Al Wakaf', case=False, na=False)]['Jumlah Mushaf (Pcs)'].sum()) if 'Variasi Mushaf' in df_kal.columns else 351
    jadwal_bt = 200

    db['stok_audit'] = {
        "st_siap": st_siap, "st_belum": st_belum, "st_total": st_siap + st_belum, "st_jadwal": jadwal_st, "st_gap_siap": st_siap - jadwal_st,
        "aw_meta_siap": aw_meta_siap, "aw_tik_siap": aw_tik_siap, "aw_total_siap": aw_total_siap,
        "aw_belum_stiker": aw_meta_belum_stiker, "aw_belum_ambil": aw_meta_belum_ambil, "aw_total_belum": aw_total_belum,
        "aw_total_fisik": aw_total_siap + aw_total_belum, "aw_jadwal": jadwal_aw,
        "aw_gap_tik": aw_tik_siap - jadwal_aw, "aw_gap_total_siap": aw_total_siap - jadwal_aw,
        "bt_siap": bt_siap, "bt_belum": bt_belum, "bt_total": bt_siap + bt_belum, "bt_jadwal": jadwal_bt, "bt_gap_siap": bt_siap - jadwal_bt,
        "mushaf_siap_total": st_siap + aw_total_siap,
        "mushaf_belum_total": st_belum + aw_total_belum,
        "mushaf_fisik_total": (st_siap + st_belum) + (aw_total_siap + aw_total_belum),
        "all_siap_total": st_siap + aw_total_siap + bt_siap,
        "all_belum_total": st_belum + aw_total_belum + bt_belum,
        "all_fisik_total": (st_siap + st_belum) + (aw_total_siap + aw_total_belum) + (bt_siap + bt_belum)
    }

    db['stok_vs_jadwal_df'] = pd.DataFrame([
        {
            "Kategori": "Mushaf Al-Qur'an",
            "Jenis Produk": "Mushaf Super Tajwid (Meta Ads)",
            "Siap Salur (Sudah Stiker)": f"{st_siap:,} Pcs",
            "Belum Stiker (Di Gudang)": f"{st_belum:,} Pcs",
            "Belum Diambil (PO Cetak)": "0 Pcs",
            "Total Stok Fisik": f"{st_siap + st_belum:,} Pcs",
            "Kebutuhan Jadwal Okt": f"{jadwal_st:,} Pcs (5 Titik)",
            "Selisih Siap Salur": f"+{st_siap - jadwal_st:,} Pcs",
            "Status Kecukupan": "Siap Salur Cukup"
        },
        {
            "Kategori": "Mushaf Al-Qur'an",
            "Jenis Produk": "Mushaf Al-Wakaf (TikTok)",
            "Siap Salur (Sudah Stiker)": f"{aw_tik_siap:,} Pcs",
            "Belum Stiker (Di Gudang)": "0 Pcs",
            "Belum Diambil (PO Cetak)": "0 Pcs",
            "Total Stok Fisik": f"{aw_tik_siap:,} Pcs",
            "Kebutuhan Jadwal Okt": f"{jadwal_aw:,} Pcs (4 Titik)",
            "Selisih Siap Salur": f"{aw_tik_siap - jadwal_aw:,} Pcs",
            "Status Kecukupan": "Defisit (Kurang 331 Pcs)"
        },
        {
            "Kategori": "Mushaf Al-Qur'an",
            "Jenis Produk": "Mushaf Al-Wakaf (Meta Ads)",
            "Siap Salur (Sudah Stiker)": f"{aw_meta_siap:,} Pcs",
            "Belum Stiker (Di Gudang)": f"{aw_meta_belum_stiker:,} Pcs",
            "Belum Diambil (PO Cetak)": f"{aw_meta_belum_ambil:,} Pcs",
            "Total Stok Fisik": f"{aw_meta_siap + aw_meta_belum_stiker + aw_meta_belum_ambil:,} Pcs",
            "Kebutuhan Jadwal Okt": "Subsidi Silang Al-Wakaf",
            "Selisih Siap Salur": f"{aw_total_siap - jadwal_aw:,} Pcs (Gabungan)",
            "Status Kecukupan": "Perlu Tempel Stiker 33 Pcs"
        },
        {
            "Kategori": "Buku Super Tahsin",
            "Jenis Produk": "Buku Belajar Tahsin AmalQu",
            "Siap Salur (Sudah Stiker)": f"{bt_siap:,} Pcs",
            "Belum Stiker (Di Gudang)": f"{bt_belum:,} Pcs",
            "Belum Diambil (PO Cetak)": "0 Pcs",
            "Total Stok Fisik": f"{bt_siap + bt_belum:,} Pcs",
            "Kebutuhan Jadwal Okt": f"{jadwal_bt:,} Pcs (Sisa Target)",
            "Selisih Siap Salur": f"+{bt_siap - jadwal_bt:,} Pcs",
            "Status Kecukupan": "Siap Salur Cukup"
        }
    ])

    # 7. DATA MASTER DATABASE & SETTING DASHBOARD
    db['db_kpi'] = {
        "total_donatur": 14464, "total_leads": 3416, "total_kontak": 17880,
        "konversi_pct": 80.9, "total_donasi_kumulatif": 2604405566, "rata_rata_donasi": 180061
    }
    db['db_segmentasi'] = pd.DataFrame([
        {"Prioritas": "A1",      "Segmentasi Donatur": "Donatur Platinum Prioritas Utama", "Target Tindakan CRM": "Personal Call & Layanan VIP Khusus", "Jumlah Donatur": 20,   "Porsi (%)": "0,14%"},
        {"Prioritas": "A2",      "Segmentasi Donatur": "Donatur VIP Potensial",            "Target Tindakan CRM": "Pendekatan Personal Berkala",        "Jumlah Donatur": 12,   "Porsi (%)": "0,08%"},
        {"Prioritas": "B1",      "Segmentasi Donatur": "Donatur Rutin Menengah",           "Target Tindakan CRM": "Reminder Rutin & Penyaluran",        "Jumlah Donatur": 92,   "Porsi (%)": "0,64%"},
        {"Prioritas": "B2",      "Segmentasi Donatur": "Donatur Berkala Menengah",         "Target Tindakan CRM": "Ajakan Donasi Program Tematik",      "Jumlah Donatur": 118,  "Porsi (%)": "0,82%"},
        {"Prioritas": "C1",      "Segmentasi Donatur": "Donatur Reguler Loyal",            "Target Tindakan CRM": "Update Buletin & Do'a Harian",       "Jumlah Donatur": 32,   "Porsi (%)": "0,22%"},
        {"Prioritas": "D4",      "Segmentasi Donatur": "Donatur Churn / Pasif",            "Target Tindakan CRM": "Reaktivasi Program Spesial",         "Jumlah Donatur": 4385, "Porsi (%)": "30,32%"},
        {"Prioritas": "Reguler", "Segmentasi Donatur": "Donatur Standar / Umum",           "Target Tindakan CRM": "Broadcast Buletin Massal",           "Jumlah Donatur": 9805, "Porsi (%)": "67,79%"},
    ])
    db['db_reminder'] = pd.DataFrame([
        {"Status Reminder": "CALLBACK SEGERA", "Jumlah Donatur": 12285, "Persentase (%)": "84,94%"},
        {"Status Reminder": "PANTAU",          "Jumlah Donatur": 1628,  "Persentase (%)": "11,26%"},
        {"Status Reminder": "AMAN",            "Jumlah Donatur": 550,   "Persentase (%)": "3,80%"},
    ])
    db['db_status_donatur'] = pd.DataFrame([
        {"Status Donatur": "Donatur Churn", "Jumlah Donatur": 6933, "Persentase (%)": "47,93%"},
        {"Status Donatur": "Donatur Baru",  "Jumlah Donatur": 6894, "Persentase (%)": "47,66%"},
        {"Status Donatur": "Donatur Aktif", "Jumlah Donatur": 492,  "Persentase (%)": "3,40%"},
        {"Status Donatur": "Donatur Rutin", "Jumlah Donatur": 145,  "Persentase (%)": "1,00%"},
    ])

    df_contacts_raw = pd.DataFrame()
    local_files = glob.glob("*MASTER_DATABASE*DATABASE*.csv")
    if local_files:
        try:
            df_contacts_raw = pd.read_csv(local_files[0], dtype=str)
        except:
            pass
    else:
        try:
            u_csv = build_gsheet_url("master_db", "DATABASE")
            df_contacts_raw = pd.read_csv(u_csv, dtype=str)
            if not df_contacts_raw.empty:
                live_synced += 1
        except:
            pass

    df_contacts = normalize_contacts_df(df_contacts_raw)
    if df_contacts.empty or len(df_contacts) < 3:
        df_contacts = pd.DataFrame([
            {"Nama Donatur": "Donatur Prioritas A1", "Nomor Whatsapp": "628000000001", "PiC": "CS Nisa",  "Program": "Waqaf/Mushaf", "Donasi Terakhir": "1 Oktober 2026",   "Kategori": "Donatur Rutin", "FU1 (Sapaan)": "Sudah", "FU3 (Laporan Penyaluran)": "Sudah", "Prioritas": "A1",      "Reminder": "AMAN"},
            {"Nama Donatur": "Donatur Aktif B1",     "Nomor Whatsapp": "628000000002", "PiC": "CS Salma", "Program": "AmalQu",       "Donasi Terakhir": "2 Oktober 2026",   "Kategori": "Donatur Aktif", "FU1 (Sapaan)": "Sudah", "FU3 (Laporan Penyaluran)": "Belum", "Prioritas": "B1",      "Reminder": "PANTAU"},
            {"Nama Donatur": "Donatur Baru Reguler", "Nomor Whatsapp": "628000000003", "PiC": "CS Aulia", "Program": "AmalQu",       "Donasi Terakhir": "5 Oktober 2026",   "Kategori": "Donatur Baru",  "FU1 (Sapaan)": "Belum", "FU3 (Laporan Penyaluran)": "Belum", "Prioritas": "Reguler", "Reminder": "CALLBACK SEGERA"},
            {"Nama Donatur": "Donatur Reaktivasi D4","Nomor Whatsapp": "628000000004", "PiC": "CRM Olive","Program": "Waqaf/Mushaf", "Donasi Terakhir": "14 Februari 2026", "Kategori": "Donatur Churn", "FU1 (Sapaan)": "Belum", "FU3 (Laporan Penyaluran)": "Belum", "Prioritas": "D4",      "Reminder": "CALLBACK SEGERA"},
        ])
        db['is_sample_db'] = True
    else:
        db['is_sample_db'] = False

    db['contacts_df'] = df_contacts
    db['live_synced'] = live_synced
    db['last_sync'] = datetime.datetime.now().strftime("%d %b %Y • %H:%M WIB")
    return db

db = load_all_realtime_data()
df_macro = db['macro_monthly']
sa = db['stok_audit']

# ==============================================================================
# 7. SIDEBAR NAVIGASI SESUAI HAK AKSES ROLE USER
# ==============================================================================
if DIRECT_LOGO_URL:
    logo_sidebar_html = f'<img src="{DIRECT_LOGO_URL}" style="width:44px; height:44px; border-radius:12px; object-fit:contain; background:#FFFFFF; padding:3px; box-shadow:0 4px 12px rgba(0,0,0,0.08);" alt="AmalQu">'
else:
    logo_sidebar_html = (
        '<div style="width:44px; height:44px; border-radius:12px; background:linear-gradient(135deg, #FF6B4A 0%, #F97316 100%); '
        'display:flex; align-items:center; justify-content:center; box-shadow:0 4px 12px rgba(249,115,22,0.3);">'
        '<i class="ri-hand-heart-fill" style="color:#FFFFFF !important; font-size:24px;"></i></div>'
    )

with st.sidebar:
    render_html(f"""
    <div style="display:flex; align-items:center; gap:12px; padding:4px 4px 18px 4px; border-bottom:1px solid var(--border-soft); margin-bottom:14px;">
        {logo_sidebar_html}
        <div>
            <div class="brand-title" style="font-family:'Outfit',sans-serif !important; font-weight:800; font-size:21px; line-height:1.15; letter-spacing:-0.3px;">AmalQu</div>
            <div class="brand-sub" style="font-size:11px; font-weight:600; line-height:1.3; margin-top:2px;">Yayasan AmalQu Indonesia Peduli</div>
        </div>
    </div>
    <div style="font-size:11px; font-weight:700; color:var(--text-muted) !important; letter-spacing:0.8px; text-transform:uppercase; padding:4px 6px 8px 6px;">
        MENU DIVISI ({user_role.upper()})
    </div>
    """)

    menu_pilihan = st.radio(
        "Navigasi Utama",
        allowed_menus,
        label_visibility="collapsed"
    )

    render_html(f"""
    <div class="sub-box" style="margin-top:20px; padding:13px; border-radius:14px;">
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
            <i class="ri-shield-user-line" style="color:#4F46E5 !important; font-size:16px;"></i>
            <span style="font-size:12px; font-weight:700;">Login: {current_user['username_display']}</span>
        </div>
        <div style="font-size:11px; opacity:0.82; line-height:1.4;">
            {current_user['title']}<br>
            <span style="color:#10B981 !important; font-weight:700;">● Live Sync 16 Sheets ({db['last_sync']})</span>
        </div>
    </div>
    """)

    sb_col1, sb_col2 = st.columns(2)
    with sb_col1:
        if st.button("🔄 Sync", use_container_width=True, help="Sinkronkan Data Sekarang"):
            st.cache_data.clear()
            st.rerun()
    with sb_col2:
        if st.button("🚪 Keluar", use_container_width=True, help="Keluar dari Akun Ini"):
            st.session_state.auth_user = None
            st.rerun()

# ==============================================================================
# 8. UI HELPER COMPONENTS
# ==============================================================================
def render_bento_kpi(icon_cls, color_theme, title, value, badge_text, badge_theme="green", subtext=""):
    ib_map = {"indigo": "ib-indigo", "orange": "ib-orange", "emerald": "ib-emerald", "rose": "ib-rose"}
    bp_map = {"green": "bp-green", "red": "bp-red", "orange": "bp-orange", "indigo": "bp-indigo"}
    arrow_ic = "ri-arrow-right-up-line" if badge_theme in ["green", "indigo"] else ("ri-alert-line" if badge_theme == "red" else "ri-information-line")
    render_html(f"""
    <div class="bento-card">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px; margin-bottom:10px;">
            <span style="font-size:12.5px; font-weight:600; color:var(--text-secondary) !important; line-height:1.3;">{title}</span>
            <div class="icon-box {ib_map.get(color_theme, 'ib-indigo')}"><i class="{icon_cls}"></i></div>
        </div>
        <div class="metric-num" style="font-size:24px; font-weight:800; letter-spacing:-0.5px; margin-bottom:10px;">
            {value}
        </div>
        <div style="display:flex; align-items:center; justify-content:space-between; gap:6px; flex-wrap:wrap;">
            <span class="badge-pill {bp_map.get(badge_theme, 'bp-green')}">
                <i class="{arrow_ic}"></i> {badge_text}
            </span>
            <span style="font-size:11px; color:var(--text-muted) !important; font-weight:600;">{subtext}</span>
        </div>
    </div>
    """)

def render_chart_header(title_text, subtitle_text="", badge_text="", badge_theme="indigo"):
    bp_map = {"green": "bp-green", "red": "bp-red", "orange": "bp-orange", "indigo": "bp-indigo"}
    badge_html = f'<span class="badge-pill {bp_map.get(badge_theme, "bp-indigo")}">{badge_text}</span>' if badge_text else ""
    sub_html = f'<div style="font-size:11.5px; color:var(--text-muted) !important; margin-top:2px;">{subtitle_text}</div>' if subtitle_text else ""
    render_html(f"""
    <div class="chart-header-box">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
            <div>
                <div style="font-family:'Outfit',sans-serif !important; font-size:15.5px; font-weight:700; color:var(--text-primary) !important;">{title_text}</div>
                {sub_html}
            </div>
            {badge_html}
        </div>
    </div>
    """)

def apply_saas_plotly(fig, height=310, is_currency=False):
    bg_col = "#111827" if is_dark else "#FFFFFF"
    txt_col = "#F8FAFC" if is_dark else "#0F172A"
    sub_col = "#94A3B8" if is_dark else "#475569"
    grid_col = "#1E293B" if is_dark else "#F1F5F9"

    fig.update_layout(
        title=None,
        height=height,
        margin=dict(l=10, r=10, t=18, b=52),
        paper_bgcolor=bg_col,
        plot_bgcolor=bg_col,
        font=dict(family="Plus Jakarta Sans, sans-serif", size=11.5, color=txt_col),
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="top", y=-0.16, xanchor="center", x=0.5,
            font=dict(family="Plus Jakarta Sans, sans-serif", size=11.5, color=txt_col),
            bgcolor="rgba(0,0,0,0)"
        ),
        xaxis=dict(
            showgrid=False, linecolor=grid_col,
            tickfont=dict(color=sub_col, size=11), title=None
        ),
        yaxis=dict(
            gridcolor=grid_col, zeroline=False,
            tickfont=dict(color=sub_col, size=11), title=None,
            tickprefix="Rp " if is_currency else ""
        )
    )
    return fig

def make_gauge_chart(value, max_val=100, suffix="%", bar_color="#10B981"):
    bg_col = "#111827" if is_dark else "#FFFFFF"
    txt_col = "#F8FAFC" if is_dark else "#0F172A"
    track_col = "#1E293B" if is_dark else "#F1F5F9"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={'suffix': suffix, 'font': {'size': 32, 'color': txt_col, 'family': 'Outfit, sans-serif'}},
        gauge={
            'axis': {'range': [0, max_val], 'visible': False},
            'bar': {'color': bar_color, 'thickness': 0.8},
            'bgcolor': track_col,
            'borderwidth': 0,
            'shape': 'angular'
        }
    ))
    fig.update_layout(
        height=215, margin=dict(l=16, r=16, t=24, b=10),
        paper_bgcolor=bg_col, plot_bgcolor=bg_col,
        font=dict(color=txt_col, family="Plus Jakarta Sans, sans-serif")
    )
    return fig

def render_saas_table(df: pd.DataFrame, max_rows=50):
    if df is None or df.empty:
        render_html('<div class="bento-card"><p style="color:var(--text-muted) !important; margin:0;">Data tidak ditemukan untuk filter ini.</p></div>')
        return
    df_show = df.head(max_rows).copy()
    ths = "".join([f"<th>{str(c)}</th>" for c in df_show.columns])
    trs = ""
    for _, row in df_show.iterrows():
        tds = ""
        for col_name in df_show.columns:
            val_str = str(row[col_name])
            low_v = val_str.lower()
            if any(k in low_v for k in ["tercapai", "aktif", "siap salur cukup", "stok cukup", "tersedia", "selesai", "aman", "sudah"]) and "tidak" not in low_v and "non-aktif" not in low_v and "belum" not in low_v:
                cell_html = f'<span class="badge-pill bp-green"><i class="ri-checkbox-circle-fill"></i> {val_str}</span>'
            elif any(k in low_v for k in ["tidak tercapai", "non-aktif", "defisit", "kritis", "habis", "callback segera", "churn", "kurang"]):
                cell_html = f'<span class="badge-pill bp-red"><i class="ri-error-warning-fill"></i> {val_str}</span>'
            elif any(k in low_v for k in ["scheduled", "perlu", "proses", "menipis", "pantau", "belum", "realtime", "reguler"]):
                cell_html = f'<span class="badge-pill bp-orange"><i class="ri-time-fill"></i> {val_str}</span>'
            elif col_name in ["Nama CS", "CS / CRM", "Bulan", "Nama Lembaga Penerima", "Nama Donatur", "Jenis Produk"]:
                cell_html = f'<span style="font-weight:700;">{val_str}</span>'
            else:
                cell_html = val_str
            tds += f"<td>{cell_html}</td>"
        trs += f"<tr>{tds}</tr>"
    render_html(f"""
    <div class="saas-table-wrap">
        <table class="saas-table">
            <thead><tr>{ths}</tr></thead>
            <tbody>{trs}</tbody>
        </table>
    </div>
    """)

# ==============================================================================
# 9. TOP HEADER BAR + TOMBOL SAKELAR IKON DARK/LIGHT DI KANAN ATAS
# ==============================================================================
if DIRECT_LOGO_URL:
    header_logo_html = f'<img src="{DIRECT_LOGO_URL}" style="width:46px; height:46px; border-radius:12px; object-fit:contain; background:#FFFFFF; padding:4px; border:1px solid var(--border-soft);" alt="AmalQu">'
else:
    header_logo_html = (
        '<div style="width:46px; height:46px; border-radius:12px; background:linear-gradient(135deg, #FF6B4A 0%, #F97316 100%); '
        'display:flex; align-items:center; justify-content:center; flex-shrink:0;">'
        '<i class="ri-hand-heart-fill" style="color:#FFFFFF !important; font-size:24px;"></i></div>'
    )

hdr_col_left, hdr_col_right = st.columns([6.5, 0.8])
with hdr_col_left:
    render_html(f"""
    <div class="bento-card" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; padding:14px 20px; margin-bottom:14px;">
        <div style="display:flex; align-items:center; gap:14px;">
            {header_logo_html}
            <div>
                <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                    <span style="font-family:'Outfit',sans-serif !important; font-size:22px; font-weight:800; letter-spacing:-0.4px;">AmalQu</span>
                    <span class="badge-pill bp-orange">{menu_pilihan}</span>
                </div>
                <div style="font-size:12.5px; font-weight:600; color:var(--text-secondary) !important; margin-top:2px;">
                    Yayasan AmalQu Indonesia Peduli • Enterprise Command Center
                </div>
            </div>
        </div>
        <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
            <span class="badge-pill bp-indigo"><i class="ri-user-star-line"></i> {current_user['username_display']} ({user_role})</span>
            <span class="badge-pill bp-green"><i class="ri-checkbox-blank-circle-fill" style="font-size:8px;"></i> Live Sync</span>
        </div>
    </div>
    """)
with hdr_col_right:
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    theme_icon_btn = "☀️" if is_dark else "🌙"
    if st.button(theme_icon_btn, key="top_theme_toggle", help="Sakelar Mode Gelap (🌙) / Terang (☀️)", use_container_width=True):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

# ==============================================================================
# HALAMAN 1: DASHBOARD OVERVIEW (ISOLASI OTOMATIS KHUSUS ROLE ADVERTISER)
# ==============================================================================
if menu_pilihan == "Dashboard Overview":
    okt_r = df_macro[df_macro['Bulan'] == 'Oktober'].iloc[0]
    real_okt = float(okt_r['Realisasi Finance'])
    cs_okt_total = float(db['okt_kpi']['total_donasi'])
    cs_okt_final = float(db['okt_kpi']['donasi_final'])
    selisih_real_cs_okt = real_okt - cs_okt_total
    target_okt = float(okt_r['Target Bulanan'])
    ads_okt = float(okt_r['Budget Iklan'])

    hari_berjalan_kalender = 17
    hari_aktif_data = max(1, len(db['okt_harian']))
    laju_harian_real = real_okt / hari_berjalan_kalender
    proyeksi_akhir_bulan_real = laju_harian_real * 31
    proyeksi_optimis_real = (real_okt / hari_aktif_data) * 31

    satpam_okt = hitung_satpam_keuangan(target_okt, real_okt, ads_okt, okt_r['Mushaf Terverifikasi'])
    tot_fin_ytd = df_macro['Realisasi Finance'].sum()
    tot_ads_ytd = df_macro['Budget Iklan'].sum()

    # BARIS 1: 4 BENTO KPI CARDS + 1 HERO CARD
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1.15])
    with c1:
        render_bento_kpi(
            "ri-bank-line", "indigo", "Data Real Finance (Oktober)",
            rp_short(real_okt), f"{real_okt/target_okt*100:.1f}% Target", "indigo",
            f"YTD Real: {rp_short(tot_fin_ytd)}"
        )
    with c2:
        render_bento_kpi(
            "ri-user-voice-line", "emerald", "Data Dashboard CS (Oktober)",
            rp_short(cs_okt_total), f"Selisih Bank: +{rp_short(selisih_real_cs_okt)}", "green",
            f"Terverifikasi: {rp_short(cs_okt_final)}"
        )
    with c3:
        render_bento_kpi(
            "ri-line-chart-line", "orange", "Proyeksi Akhir Bulan (Real)",
            rp_short(proyeksi_akhir_bulan_real), f"{proyeksi_akhir_bulan_real/target_okt*100:.1f}% Target", "orange",
            f"Optimis: {rp_short(proyeksi_optimis_real)}"
        )
    with c4:
        if user_role == "Advertiser":
            # Advertiser TIDAK boleh melihat Stok Gudang / Agenda Salur
            render_bento_kpi(
                "ri-advertisement-line", "rose", "Biaya Iklan (Oktober)",
                rp_short(ads_okt), f"ROAS Real: {satpam_okt['roas_aktual']:.2f}x", "red",
                f"YTD Ads: {rp_short(tot_ads_ytd)}"
            )
        else:
            render_bento_kpi(
                "ri-checkbox-multiple-line", "rose", "Stok Siap Salur vs Jadwal Okt",
                f"{sa['mushaf_siap_total']:,} Mushaf".replace(",", "."), "Al-Wakaf Kurang 33 Pcs", "red",
                f"Jadwal: {sa['st_jadwal'] + sa['aw_jadwal']:,} Mushaf"
            )
    with c5:
        render_html(f"""
        <div class="hero-card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:11px; font-weight:700; letter-spacing:0.8px; text-transform:uppercase;">SATPAM KEUANGAN (REAL OKT)</span>
                <i class="ri-shield-star-line" style="font-size:18px;"></i>
            </div>
            <div class="metric-num" style="font-size:26px; font-weight:800; margin-bottom:4px;">ROAS {satpam_okt['roas_aktual']:.2f}x</div>
            <div style="font-size:11px; opacity:0.92; margin-bottom:10px;">Min Tier 1: <b>1.52x</b> • Aman Tier 3: <b>2.63x</b></div>
            <div style="display:flex; justify-content:space-between; background:rgba(255,255,255,0.16); padding:6px 10px; border-radius:10px; font-size:11px; font-weight:600;">
                <span>DSD: {rp_short(satpam_okt['dsd'])}</span>
                <span>HPP: {rp(satpam_okt['plafon_hpp'])}</span>
            </div>
        </div>
        """)

    # BARIS 2: GRAFIK KOMPARASI REAL FINANCE VS DASHBOARD CS + GARIS PROYEKSI AKHIR BULAN
    m_left, m_right = st.columns([1.8, 1.05])
    with m_left:
        render_chart_header(
            "Komparasi Real Finance vs Dashboard CS & Proyeksi Akhir Bulan (Jan – Okt 2026)",
            f"Realisasi Bank Oktober: {rp(real_okt)} • Dashboard CS: {rp(cs_okt_total)} • Proyeksi Akhir Oktober: {rp(proyeksi_akhir_bulan_real)}",
            "Real vs CS + Proyeksi", "indigo"
        )
        fig_ov = go.Figure()
        fig_ov.add_trace(go.Scatter(
            x=df_macro['Bulan'], y=df_macro['Realisasi Finance'], name='Data Real Finance (Mutasi Bank)',
            mode='lines+markers', line=dict(color='#4F46E5', width=3, shape='spline'),
            fill='tozeroy', fillcolor='rgba(79, 70, 229, 0.08)'
        ))
        fig_ov.add_trace(go.Scatter(
            x=df_macro['Bulan'], y=df_macro['Omset CS'], name='Data Dashboard CS (Terlapor)',
            mode='lines+markers', line=dict(color='#10B981', width=2.6, shape='spline')
        ))
        sep_real = float(df_macro[df_macro['Bulan'] == 'September']['Realisasi Finance'].iloc[0])
        fig_ov.add_trace(go.Scatter(
            x=['September', 'Oktober'], y=[sep_real, proyeksi_akhir_bulan_real],
            name='Proyeksi Akhir Bulan (Real Run-Rate)',
            mode='lines+markers', line=dict(color='#F59E0B', width=3, dash='dash')
        ))
        fig_ov.add_trace(go.Scatter(
            x=df_macro['Bulan'], y=df_macro['Budget Iklan'], name='Biaya Iklan (Ads)',
            mode='lines+markers', line=dict(color='#FF6B4A', width=2, dash='dot', shape='spline')
        ))
        apply_saas_plotly(fig_ov, height=340, is_currency=True)
        st.plotly_chart(fig_ov, use_container_width=True)

    with m_right:
        if user_role == "Advertiser":
            bottom_insight_box = """
            <div class="sub-box" style="border-radius:12px; padding:11px 14px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <span style="font-size:12px; font-weight:700;"><i class="ri-Filter-3-line" style="color:#10B981 !important;"></i> Performa Funnel Leads Oktober</span>
                    <span class="badge-pill bp-green">Conv. 74,3%</span>
                </div>
                <div style="font-size:11.5px; color:var(--text-secondary) !important; line-height:1.45;">
                    • <b>Leads Meta Ads:</b> Menyumbang <b>Rp 90,44 Jt (83,2%)</b> dari total perolehan CS Oktober.<br>
                    • <b>Rasio Closing CS Aktif:</b> <b>962 Chat Valid</b> menghasilkan <b>715 Closing</b> (Nisa 525, Salma 183, Aulia 7).
                </div>
            </div>
            """
        else:
            bottom_insight_box = """
            <div class="sub-box" style="border-radius:12px; padding:11px 14px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <span style="font-size:12px; font-weight:700;"><i class="ri-alarm-warning-line" style="color:#EF4444 !important;"></i> Audit Stok vs Jadwal Salur Okt</span>
                    <span class="badge-pill bp-red">Tempel Stiker!</span>
                </div>
                <div style="font-size:11.5px; color:var(--text-secondary) !important; line-height:1.45;">
                    • <b>Super Tajwid:</b> Siap <b>801 Pcs</b> vs Jadwal <b>653 Pcs</b> (<b style="color:#10B981 !important;">Surplus +148 Pcs</b>)<br>
                    • <b>Al-Wakaf:</b> Siap <b>318 Pcs</b> vs Jadwal <b>351 Pcs</b> (<b style="color:#EF4444 !important;">Kurang -33 Pcs Siap Salur</b>; segera tempel stiker dari <b>480 Pcs</b> stok R. AmalQu).
                </div>
            </div>
            """

        render_html(f"""
        <div class="bento-card" style="min-height:385px;">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:12px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <div class="icon-box ib-indigo" style="width:32px; height:32px; font-size:15px;"><i class="ri-scales-3-line"></i></div>
                    <span style="font-family:'Outfit',sans-serif !important; font-weight:700; font-size:15px;">Rekonsiliasi Real vs CS & Proyeksi</span>
                </div>
                <span class="badge-pill bp-indigo">OKTOBER 2026</span>
            </div>
            <div class="sub-box" style="border-radius:12px; padding:11px 14px; margin-bottom:9px;">
                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
                    <span style="color:var(--text-secondary) !important;">1. Pendapatan Real Finance (Bank):</span>
                    <b style="color:#4F46E5 !important;">{rp(real_okt)}</b>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
                    <span style="color:var(--text-secondary) !important;">2. Total Input Dashboard CS:</span>
                    <b style="color:#10B981 !important;">{rp(cs_okt_total)}</b>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:12px; border-top:1px dashed var(--border-soft); padding-top:4px;">
                    <span style="color:var(--text-secondary) !important;">Selisih Bank vs CS (Unidentified):</span>
                    <b style="color:#F97316 !important;">+{rp(selisih_real_cs_okt)}</b>
                </div>
            </div>
            <div class="sub-box" style="border-radius:12px; padding:11px 14px; margin-bottom:9px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <span style="font-size:12px; font-weight:700;"><i class="ri-compass-3-line" style="color:#F59E0B !important;"></i> Proyeksi Akhir Bulan (31 Okt)</span>
                    <span class="badge-pill bp-orange">{proyeksi_akhir_bulan_real/target_okt*100:.1f}% Target</span>
                </div>
                <div style="font-size:11.5px; color:var(--text-secondary) !important; line-height:1.45;">
                    • Rata-rata Real Harian: <b>{rp(laju_harian_real)} / hari</b><br>
                    • Estimasi Tutup Buku (Konservatif): <b>{rp(proyeksi_akhir_bulan_real)}</b><br>
                    • Estimasi Tutup Buku (Optimis 14 Hari Aktif): <b>{rp(proyeksi_optimis_real)}</b>
                </div>
            </div>
            {bottom_insight_box}
        </div>
        """)

    # BARIS 3: KHUSUS ADVERTISER TAMPILKAN METRIK ADS/CS, SEDANGKAN ADMIN/FINANCE TAMPILKAN KESIAPAN STOK VS JADWAL
    b1, b2, b3 = st.columns(3)
    if user_role == "Advertiser":
        with b1:
            render_html("""
            <div class="bento-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12.5px; font-weight:700;">Proporsi Omzet CS Aktif (Oktober)</span>
                    <span class="badge-pill bp-indigo">3 CS Ads Aktif</span>
                </div>
                <div class="metric-num" style="font-size:22px; font-weight:800; margin-bottom:8px;">Rp 108,67 Juta</div>
                <div style="display:flex; height:9px; border-radius:99px; overflow:hidden; gap:3px; margin-bottom:8px; background:var(--bg-subcard);">
                    <div style="width:61%; background:#FF6B4A; border-radius:99px;"></div>
                    <div style="width:30%; background:#4F46E5; border-radius:99px;"></div>
                    <div style="width:9%; background:#10B981; border-radius:99px;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:600; color:var(--text-secondary) !important;">
                    <span>Nisa: <b>60,7%</b></span>
                    <span>Salma: <b>30,2%</b></span>
                    <span>Aulia: <b>9,1%</b></span>
                </div>
            </div>
            """)
        with b2:
            render_html("""
            <div class="bento-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12.5px; font-weight:700;">Sumber Kontak Donasi (Oktober)</span>
                    <span class="badge-pill bp-green">Dominasi Meta Ads</span>
                </div>
                <div class="metric-num" style="font-size:22px; font-weight:800; margin-bottom:8px;">Rp 90,44 Jt Leads Meta</div>
                <div style="display:flex; height:9px; border-radius:99px; overflow:hidden; gap:3px; margin-bottom:8px; background:var(--bg-subcard);">
                    <div style="width:83%; background:#10B981; border-radius:99px;"></div>
                    <div style="width:12%; background:#4F46E5; border-radius:99px;"></div>
                    <div style="width:5%; background:#F59E0B; border-radius:99px;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:600; color:var(--text-secondary) !important;">
                    <span>Leads Meta: <b>83,2%</b></span>
                    <span>RO Non-CRM: <b>7,1%</b></span>
                    <span>RO CRM: <b>5,2%</b></span>
                </div>
            </div>
            """)
        with b3:
            render_html("""
            <div class="bento-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12.5px; font-weight:700;">Konversi Kampanye Program (Okt)</span>
                    <span class="badge-pill bp-orange">715 Total Closing</span>
                </div>
                <div class="metric-num" style="font-size:22px; font-weight:800; margin-bottom:8px;">Rp 114,68 Jt (Leads Sheet)</div>
                <div style="display:flex; height:9px; border-radius:99px; overflow:hidden; gap:3px; margin-bottom:8px; background:var(--bg-subcard);">
                    <div style="width:74%; background:#4F46E5; border-radius:99px;"></div>
                    <div style="width:25%; background:#10B981; border-radius:99px;"></div>
                    <div style="width:1%; background:#F97316; border-radius:99px;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:600; color:var(--text-secondary) !important;">
                    <span>SantriQu: <b>549 Closing</b></span>
                    <span>AmalQu: <b>163 Closing</b></span>
                    <span>JariyahQu: <b>3</b></span>
                </div>
            </div>
            """)
    else:
        with b1:
            render_html("""
            <div class="bento-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12.5px; font-weight:700;">Mushaf Super Tajwid vs Jadwal Okt</span>
                    <span class="badge-pill bp-green">Aman (+148 Pcs)</span>
                </div>
                <div class="metric-num" style="font-size:22px; font-weight:800; margin-bottom:8px;">801 Pcs Siap Salur</div>
                <div style="display:flex; height:9px; border-radius:99px; overflow:hidden; gap:3px; margin-bottom:8px; background:var(--bg-subcard);">
                    <div style="width:82%; background:#10B981; border-radius:99px;"></div>
                    <div style="width:18%; background:#4F46E5; border-radius:99px;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:600; color:var(--text-secondary) !important;">
                    <span>Sudah Stiker: <b>801 Pcs</b></span>
                    <span>Jadwal Okt: <b>653 Pcs</b></span>
                    <span>Belum Stiker: <b>0 Pcs</b></span>
                </div>
            </div>
            """)
        with b2:
            render_html("""
            <div class="bento-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12.5px; font-weight:700;">Mushaf Al-Wakaf vs Jadwal Okt</span>
                    <span class="badge-pill bp-red">Kurang 33 Pcs Stiker</span>
                </div>
                <div class="metric-num" style="font-size:22px; font-weight:800; margin-bottom:8px;">318 Siap • 2.328 Belum</div>
                <div style="display:flex; height:9px; border-radius:99px; overflow:hidden; gap:3px; margin-bottom:8px; background:var(--bg-subcard);">
                    <div style="width:12%; background:#10B981; border-radius:99px;"></div>
                    <div style="width:18%; background:#F97316; border-radius:99px;"></div>
                    <div style="width:70%; background:#64748B; border-radius:99px;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:600; color:var(--text-secondary) !important;">
                    <span>Siap: <b>318</b> (Jadwal <b>351</b>)</span>
                    <span>Belum Stiker: <b>480</b></span>
                    <span>PO: <b>1.848</b></span>
                </div>
            </div>
            """)
        with b3:
            render_html("""
            <div class="bento-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12.5px; font-weight:700;">Buku Super Tahsin vs Target Okt</span>
                    <span class="badge-pill bp-green">Aman (+1.188 Pcs)</span>
                </div>
                <div class="metric-num" style="font-size:22px; font-weight:800; margin-bottom:8px;">1.388 Siap • 1.500 Belum</div>
                <div style="display:flex; height:9px; border-radius:99px; overflow:hidden; gap:3px; margin-bottom:8px; background:var(--bg-subcard);">
                    <div style="width:48%; background:#10B981; border-radius:99px;"></div>
                    <div style="width:52%; background:#F59E0B; border-radius:99px;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:600; color:var(--text-secondary) !important;">
                    <span>Sudah Stiker: <b>1.388 Pcs</b></span>
                    <span>Belum Stiker: <b>1.500 Pcs</b></span>
                    <span>Sisa Target: <b>200</b></span>
                </div>
            </div>
            """)

# ==============================================================================
# HALAMAN 2: DONASI & SATPAM KEUANGAN
# ==============================================================================
elif menu_pilihan == "Donasi & Satpam Keuangan":
    f1_a, f1_b, f1_c = st.columns([1.5, 1.5, 1.5])
    with f1_a:
        cakupan_fin = st.selectbox(
            "1. Pilih Cakupan Periode Analisis:",
            [
                "Bulan Oktober 2026 (Realtime)",
                "Filter Tanggal Harian (Oktober 2026)",
                "Pilih Bulan Historis (Januari – September)",
                "Akumulasi Tahunan (YTD Jan–Okt)"
            ],
            key="fin_scope"
        )

    df_d_okt = db['okt_harian'].copy()
    df_d_okt['DT'] = pd.to_datetime(df_d_okt['Tanggal']).dt.date

    with f1_b:
        if cakupan_fin == "Pilih Bulan Historis (Januari – September)":
            bln_terpilih = st.selectbox("2. Pilih Bulan Historis:", [b for b in df_macro['Bulan'].tolist() if b != "Oktober"], key="fin_hist_m")
            cs_fin_filter = "Semua Tim CS"
            tgl_range_t1 = (datetime.date(2026, 10, 1), datetime.date(2026, 10, 14))
        elif cakupan_fin == "Filter Tanggal Harian (Oktober 2026)":
            tgl_range_t1 = st.date_input("2. Pilih Rentang Tanggal Oktober:", value=(datetime.date(2026, 10, 1), datetime.date(2026, 10, 14)), min_value=datetime.date(2026, 10, 1), max_value=datetime.date(2026, 10, 31), key="fin_dt_range")
            bln_terpilih = "Oktober"
        else:
            bln_terpilih = "Oktober"
            tgl_range_t1 = (datetime.date(2026, 10, 1), datetime.date(2026, 10, 14))
            st.selectbox("2. Status Data:", ["Tersinkronisasi Otomatis (Finance + CS)"], disabled=True, key="fin_stat_info")

    with f1_c:
        if "Oktober" in cakupan_fin:
            cs_fin_filter = st.selectbox("3. Filter Personel CS (Oktober):", ["Semua Tim CS", "Nisa", "Salma", "Aulia"], key="fin_cs_pick")
        else:
            cs_fin_filter = "Semua Tim CS"
            st.selectbox("3. Cakupan Divisi:", ["Seluruh Divisi Funding & Ads"], disabled=True, key="fin_div_info")

    if cakupan_fin == "Akumulasi Tahunan (YTD Jan–Okt)":
        t_omz = df_macro['Target Bulanan'].sum()
        d_fin = df_macro['Realisasi Finance'].sum()
        d_cs = df_macro['Omset CS'].sum()
        b_ads = df_macro['Budget Iklan'].sum()
        m_pcs = df_macro['Mushaf Terverifikasi'].sum()
        lbl_badge = "YTD Jan–Okt"
    elif cakupan_fin == "Pilih Bulan Historis (Januari – September)":
        rb = df_macro[df_macro['Bulan'] == bln_terpilih].iloc[0]
        t_omz, d_fin, d_cs, b_ads, m_pcs = rb['Target Bulanan'], rb['Realisasi Finance'], rb['Omset CS'], rb['Budget Iklan'], rb['Mushaf Terverifikasi']
        lbl_badge = f"{bln_terpilih} 2026"
    elif cakupan_fin == "Filter Tanggal Harian (Oktober 2026)":
        if isinstance(tgl_range_t1, (list, tuple)) and len(tgl_range_t1) == 2:
            df_d_okt = df_d_okt[(df_d_okt['DT'] >= tgl_range_t1[0]) & (df_d_okt['DT'] <= tgl_range_t1[1])]
        jml_hari = max(1, len(df_d_okt))
        if cs_fin_filter in ["Nisa", "Salma", "Aulia"]:
            d_cs = df_d_okt[cs_fin_filter].sum()
            d_fin = d_cs
            tgt_cs_map = {"Nisa": 200000000, "Salma": 200000000, "Aulia": 50000000}
            t_omz = tgt_cs_map[cs_fin_filter] * (jml_hari / 30.0)
            b_ads = (114820000 / 3.0) * (jml_hari / 14.0)
        else:
            d_cs = df_d_okt['Total Donasi'].sum()
            d_fin = df_d_okt['Donasi Final'].sum() if df_d_okt['Donasi Final'].sum() > 0 else d_cs
            t_omz = 500000000 * (jml_hari / 30.0)
            b_ads = 114820000 * (jml_hari / 14.0)
        m_pcs = max(1, int(round(d_fin / 99000.0)))
        lbl_badge = f"{jml_hari} Hari Okt ({cs_fin_filter})"
    else:
        rb = df_macro[df_macro['Bulan'] == 'Oktober'].iloc[0]
        if cs_fin_filter in ["Nisa", "Salma", "Aulia"]:
            row_cs_okt = db['okt_cs_table'][db['okt_cs_table']['CS / CRM'] == cs_fin_filter].iloc[0]
            t_omz = float(row_cs_okt['Target (Rp)'])
            d_cs = float(row_cs_okt['Bulanan (Total)'])
            d_fin = float(row_cs_okt['Bulanan (Final)'])
            b_ads = 114820000 * (d_cs / 108674008.0)
            m_pcs = max(1, int(round(d_fin / 99000.0)))
            lbl_badge = f"Okt • CS {cs_fin_filter}"
        else:
            t_omz, d_fin, d_cs, b_ads, m_pcs = rb['Target Bulanan'], rb['Realisasi Finance'], rb['Omset CS'], rb['Budget Iklan'], rb['Mushaf Terverifikasi']
            lbl_badge = "Okt 2026"

    sk = hitung_satpam_keuangan(t_omz, d_fin, b_ads, m_pcs)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_bento_kpi("ri-bank-line", "indigo", f"Realisasi Finance ({lbl_badge})", rp_short(d_fin), f"{d_fin/t_omz*100:.1f}% Target", "green" if d_fin >= t_omz else "orange", f"Target: {rp_short(t_omz)}")
    with c2:
        render_bento_kpi("ri-user-voice-line", "emerald", "Funding Terlapor CS", rp_short(d_cs), f"Selisih: {rp_short(d_fin - d_cs)}", "indigo", "Bank vs Laporan CS")
    with c3:
        render_bento_kpi("ri-advertisement-line", "orange", "Biaya Iklan Terpakai", rp_short(b_ads), f"ROAS: {sk['roas_aktual']:.2f}x", sk['badge_type'], "Min: 1.52x | Aman: 2.63x")
    with c4:
        render_bento_kpi("ri-shield-check-line", "rose", "Dana Siap Salur (DSD)", rp_short(sk['dsd']), f"HPP Maks: {rp(sk['plafon_hpp'])}", "green" if sk['plafon_hpp'] >= 20000 else "red", f"{sk['kebutuhan_mushaf_pcs']:,} Mushaf")

    g_left, g_right = st.columns([1.75, 1.05])
    with g_left:
        if "Oktober" in cakupan_fin:
            render_chart_header(
                f"Tren Harian Donasi Oktober 2026 — {cs_fin_filter}",
                "Grafik otomatis menyesuaikan rentang tanggal dan personel CS yang dipilih",
                lbl_badge, "orange"
            )
            fig_f2 = go.Figure()
            if cs_fin_filter in ["Semua Tim CS", "Nisa"]:
                fig_f2.add_trace(go.Scatter(x=df_d_okt['Tanggal'], y=df_d_okt['Nisa'], name='CS Nisa', mode='lines+markers', line=dict(color='#FF6B4A', width=2.8, shape='spline')))
            if cs_fin_filter in ["Semua Tim CS", "Salma"]:
                fig_f2.add_trace(go.Scatter(x=df_d_okt['Tanggal'], y=df_d_okt['Salma'], name='CS Salma', mode='lines+markers', line=dict(color='#4F46E5', width=2.8, shape='spline')))
            if cs_fin_filter in ["Semua Tim CS", "Aulia"]:
                fig_f2.add_trace(go.Scatter(x=df_d_okt['Tanggal'], y=df_d_okt['Aulia'], name='CS Aulia', mode='lines+markers', line=dict(color='#10B981', width=2.8, shape='spline')))
            apply_saas_plotly(fig_f2, height=330, is_currency=True)
            st.plotly_chart(fig_f2, use_container_width=True)
        else:
            render_chart_header(
                "Komparasi Bulanan: Finance Real vs Funding CS vs Biaya Iklan",
                "Perbandingan performa keuangan bulanan sepanjang Januari – Oktober 2026",
                lbl_badge, "indigo"
            )
            fig_f1 = go.Figure()
            fig_f1.add_trace(go.Bar(x=df_macro['Bulan'], y=df_macro['Realisasi Finance'], name='Realisasi Finance (Bank)', marker_color='#4F46E5', marker_cornerradius=6))
            fig_f1.add_trace(go.Bar(x=df_macro['Bulan'], y=df_macro['Omset CS'], name='Funding CS', marker_color='#10B981', marker_cornerradius=6))
            fig_f1.add_trace(go.Bar(x=df_macro['Bulan'], y=df_macro['Budget Iklan'], name='Biaya Iklan', marker_color='#FF6B4A', marker_cornerradius=6))
            apply_saas_plotly(fig_f1, height=330, is_currency=True)
            fig_f1.update_layout(barmode='group')
            st.plotly_chart(fig_f1, use_container_width=True)

    with g_right:
        render_html(f"""
        <div class="bento-card" style="min-height:375px;">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:12px;">
                <span style="font-family:'Outfit',sans-serif !important; font-weight:700; font-size:15.5px;">
                    <i class="ri-calculator-line" style="color:#4F46E5 !important;"></i> Kalkulator Satpam Keuangan
                </span>
                <span class="badge-pill bp-{sk['badge_type']}">{lbl_badge}</span>
            </div>
            <div style="font-size:12.5px; color:var(--text-secondary) !important; line-height:2.15;">
                <div style="display:flex; justify-content:space-between; border-bottom:1px dashed var(--border-soft);"><span>Profit Iklan (Donasi - Ads)</span><b style="color:var(--text-primary) !important;">{rp(sk['profit_iklan'])}</b></div>
                <div style="display:flex; justify-content:space-between; border-bottom:1px dashed var(--border-soft);"><span>Beban Operasional (10%)</span><b style="color:var(--text-primary) !important;">{rp(sk['beban_ops_10'])}</b></div>
                <div style="display:flex; justify-content:space-between; border-bottom:1px dashed var(--border-soft);"><span>Dana Siap Salur (DSD)</span><b style="color:#6366F1 !important;">{rp(sk['dsd'])}</b></div>
                <div style="display:flex; justify-content:space-between; border-bottom:1px dashed var(--border-soft);"><span>Alokasi Mushaf (65% DSD)</span><b style="color:#10B981 !important;">{rp(sk['alokasi_mushaf_65'])}</b></div>
                <div style="display:flex; justify-content:space-between; border-bottom:1px dashed var(--border-soft);"><span>Cadangan Cashback (35%)</span><b style="color:#F59E0B !important;">{rp(sk['cadangan_cashback_35'])}</b></div>
                <div style="display:flex; justify-content:space-between;"><span>Target Subsidi CRM CS</span><b style="color:#EF4444 !important;">{rp(sk['target_crm_cs'])}</b></div>
            </div>
            <div class="sub-box" style="margin-top:14px; padding:10px 12px; border-radius:10px; font-size:12px;">
                <i class="ri-award-line" style="color:#F97316 !important;"></i> <b>Keputusan Sistem:</b> {sk['rekom_tier']}
            </div>
        </div>
        """)

    opsi_tabel_t1 = [
        "1. Rekapitulasi Bulanan (Jan–Okt)",
        "2. Rincian Kinerja CS Oktober (Total vs Final)",
        "3. Distribusi Sumber Kontak (Oktober)",
        "4. Tabel Harian Oktober (Sesuai Filter Tanggal)"
    ]
    if user_role != "Advertiser":
        opsi_tabel_t1.append("5. Pencarian Riwayat Donatur (Mini CRM)")

    sub_t1 = st.radio("Pilih Tabel Detail Keuangan:", opsi_tabel_t1, horizontal=True, key="t1_subtable")

    if sub_t1.startswith("1."):
        df_show = df_macro.copy()
        if user_role == "Advertiser" and "Mushaf Terverifikasi" in df_show.columns:
            df_show.drop(columns=["Mushaf Terverifikasi"], inplace=True)
        for cr in ['Target Bulanan', 'Realisasi Finance', 'Omset CS', 'Selisih Target', 'Selisih Finance vs CS', 'Budget Iklan', 'Total Pengeluaran', 'Laba Bersih']:
            df_show[cr] = df_show[cr].apply(rp)
        df_show['% Capaian'] = df_show['% Capaian'].apply(lambda x: f"{x:.1f}%")
        df_show['ROFI'] = df_show['ROFI'].apply(lambda x: f"{x:.2f}x")
        render_saas_table(df_show)
    elif sub_t1.startswith("2."):
        df_ok = db['okt_cs_table'].copy()
        if cs_fin_filter != "Semua Tim CS":
            df_ok = df_ok[df_ok['CS / CRM'] == cs_fin_filter]
        for cr in ['Harian (Total)', 'Harian (Final)', 'Mingguan (Total)', 'Mingguan (Final)', 'Bulanan (Total)', 'Bulanan (Final)', 'Target (Rp)']:
            df_ok[cr] = df_ok[cr].apply(rp)
        render_saas_table(df_ok)
    elif sub_t1.startswith("3."):
        df_sr = db['okt_sumber'].copy()
        if cs_fin_filter != "Semua Tim CS":
            df_sr = df_sr[df_sr['CS / CRM'] == cs_fin_filter]
        for cr in ['Leads Meta', 'Repeat Order CRM', 'Repeat Order non CRM', 'Lainnya', 'Total Nominal']:
            df_sr[cr] = df_sr[cr].apply(rp)
        render_saas_table(df_sr)
    elif sub_t1.startswith("4."):
        df_h_disp = df_d_okt.drop(columns=['DT']).copy()
        for cr in ['Salma', 'Aulia', 'Nisa', 'Total Donasi', 'Donasi Final']:
            df_h_disp[cr] = df_h_disp[cr].apply(rp)
        render_saas_table(df_h_disp)
    else:
        q_d = st.text_input("Ketik Nama Donatur atau Nomor WhatsApp:", placeholder="Contoh: Donatur Prioritas, 628...")
        if q_d:
            dfc = db['contacts_df']
            m_d = dfc['Nama Donatur'].astype(str).str.contains(q_d, case=False, na=False) | dfc['Nomor Whatsapp'].astype(str).str.contains(q_d, case=False, na=False)
            render_saas_table(dfc[m_d], max_rows=30)

# ==============================================================================
# HALAMAN 3: PERFORMA CS & LEADS
# ==============================================================================
elif menu_pilihan == "Performa CS & Leads":
    mode_evaluasi_cs = st.radio(
        "Pilih Mode Evaluasi Kinerja CS:",
        [
            "1. Monitoring Leads Harian Oktober 2026 (Khusus CS Aktif: Nisa, Salma, Aulia)",
            "2. Rapor & Rekap Omzet Bulanan Seluruh CS (Januari – Oktober 2026)"
        ],
        horizontal=True, key="cs_eval_mode"
    )

    if mode_evaluasi_cs.startswith("1."):
        f2_1, f2_2, f2_3 = st.columns(3)
        with f2_1:
            pilih_cs = st.selectbox("1. Pilih CS Aktif Oktober:", ["Semua CS Aktif (Nisa, Salma, Aulia)", "Nisa", "Salma", "Aulia"], key="t2_c_okt")
        with f2_2:
            pilih_prog = st.selectbox("2. Filter Program Kampanye:", ["Semua Program", "SantriQu", "AmalQu", "JariyahQu"], key="t2_prog_okt")
        with f2_3:
            tgl_l = st.date_input("3. Rentang Tanggal Leads Oktober:", value=(datetime.date(2026, 10, 1), datetime.date(2026, 10, 16)), min_value=datetime.date(2026, 10, 1), max_value=datetime.date(2026, 10, 31), key="t2_d_okt")

        df_l = db['leads_okt'].copy()
        df_l['DT'] = pd.to_datetime(df_l['Tanggal']).dt.date
        if isinstance(tgl_l, (list, tuple)) and len(tgl_l) == 2:
            df_l = df_l[(df_l['DT'] >= tgl_l[0]) & (df_l['DT'] <= tgl_l[1])]
        if pilih_cs in ["Nisa", "Salma", "Aulia"]:
            df_l = df_l[df_l['Nama CS'] == pilih_cs]

        if pilih_prog == "SantriQu":
            df_l["Leads_Aktif"] = df_l["SantriQu_Leads"]
            df_l["Closing_Aktif"] = df_l["SantriQu_Closing"]
            df_l["Nominal_Aktif"] = df_l["SantriQu_Nominal"]
        elif pilih_prog == "AmalQu":
            df_l["Leads_Aktif"] = df_l["AmalQu_Leads"]
            df_l["Closing_Aktif"] = df_l["AmalQu_Closing"]
            df_l["Nominal_Aktif"] = df_l["AmalQu_Nominal"]
        elif pilih_prog == "JariyahQu":
            df_l["Leads_Aktif"] = df_l["JariyahQu_Leads"]
            df_l["Closing_Aktif"] = df_l["JariyahQu_Closing"]
            df_l["Nominal_Aktif"] = df_l["JariyahQu_Nominal"]
        else:
            df_l["Leads_Aktif"] = df_l["Chat Valid"]
            df_l["Closing_Aktif"] = df_l["Closing"]
            df_l["Nominal_Aktif"] = df_l["Nominal"]

        tv = int(df_l['Leads_Aktif'].sum())
        ti = int(df_l['Chat Invalid'].sum())
        tc = int(df_l['Closing_Aktif'].sum())
        tn = float(df_l['Nominal_Aktif'].sum())
        cr_okt = (tc / tv * 100) if tv > 0 else 0.0
        tot_fu = int(df_l['Total Follow Up'].sum())

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_bento_kpi("ri-chat-check-line", "indigo", f"Leads Valid ({pilih_prog})", f"{tv:,} Leads", f"Invalid: {ti:,}", "indigo", pilih_cs)
        with c2:
            render_bento_kpi("ri-check-double-line", "emerald", f"Total Closing ({pilih_prog})", f"{tc:,} Closing", f"Conv. Rate: {cr_okt:.1f}%", "green", "Oktober 2026")
        with c3:
            render_bento_kpi("ri-money-dollar-circle-line", "orange", f"Nominal Closing ({pilih_prog})", rp_short(tn), f"AOV: {rp(tn/tc if tc>0 else 0)}", "orange", "Terverifikasi")
        with c4:
            render_bento_kpi("ri-customer-service-2-line", "emerald", "Total Follow-Up Tercatat", f"{tot_fu:,} Kontak", "3 CS Ads + 1 CRM Aktif", "green", "Desi/Rida/Syafiq/Sarah Non-Aktif")

        cl_l, cl_r = st.columns([1.8, 1])
        with cl_l:
            render_chart_header(
                f"Tren Harian Perolehan Leads Oktober — {pilih_prog}",
                f"Menampilkan perolehan harian untuk: {pilih_cs}",
                pilih_prog, "orange"
            )
            df_lg = df_l.groupby(['Tanggal', 'Nama CS'], as_index=False).agg({'Nominal_Aktif': 'sum', 'Closing_Aktif': 'sum'})
            fig_cs = px.bar(df_lg, x='Tanggal', y='Nominal_Aktif', color='Nama CS', barmode='group', color_discrete_sequence=['#FF6B4A', '#4F46E5', '#10B981'])
            apply_saas_plotly(fig_cs, height=275, is_currency=True)
            st.plotly_chart(fig_cs, use_container_width=True)

        with cl_r:
            render_chart_header("Conversion Rate Leads", f"Rasio Closing {pilih_prog}", f"{cr_okt:.1f}%", "green")
            fig_g_cs = make_gauge_chart(round(cr_okt, 1), max_val=100, suffix="%", bar_color="#10B981")
            st.plotly_chart(fig_g_cs, use_container_width=True)

        render_html('<div style="font-family:\'Outfit\',sans-serif !important; font-size:15.5px; font-weight:700; margin:6px 0;"><i class="ri-table-2" style="color:#FF6B4A !important;"></i> Tabel Harian Pengelolaan Leads Oktober (Sesuai Filter di Atas)</div>')
        df_l_show = df_l[["Tanggal", "Nama CS", "Leads_Aktif", "Chat Invalid", "Closing_Aktif", "Nominal_Aktif", "SantriQu_Closing", "AmalQu_Closing", "JariyahQu_Closing", "Total Follow Up"]].copy()
        df_l_show.rename(columns={"Leads_Aktif": f"Leads ({pilih_prog})", "Closing_Aktif": f"Closing ({pilih_prog})", "Nominal_Aktif": f"Nominal ({pilih_prog})"}, inplace=True)
        df_l_show[f"Nominal ({pilih_prog})"] = df_l_show[f"Nominal ({pilih_prog})"].apply(rp)
        render_saas_table(df_l_show)

    else:
        r1, r2 = st.columns(2)
        with r1:
            filter_stat_ov = st.selectbox("1. Filter Status Keaktifan CS:", ["Semua Tim CS (8 Orang)", "Hanya CS Aktif Oktober (Nisa, Salma, Aulia, Olive)", "Hanya CS Non-Aktif (Desi, Syafiq, Rida, Sarah)"], key="ov_stat")
        df_ov = db['cs_overview'].copy()
        if "Hanya CS Aktif" in filter_stat_ov:
            df_ov = df_ov[df_ov['Status Okt'].str.contains("Aktif")]
        elif "Non-Aktif" in filter_stat_ov:
            df_ov = df_ov[df_ov['Status Okt'] == "Non-Aktif"]

        with r2:
            pilih_cs_rapor = st.selectbox("2. Pilih Personel CS:", ["Semua (Tampilkan Perbandingan)"] + df_ov['Nama CS'].tolist(), key="ov_person")

        if pilih_cs_rapor != "Semua (Tampilkan Perbandingan)":
            df_ov_view = df_ov[df_ov['Nama CS'] == pilih_cs_rapor].copy()
        else:
            df_ov_view = df_ov.copy()

        tot_omset_jan_sep = df_ov_view['Total Omset (Jan-Sep)'].sum()
        tot_omset_okt = df_ov_view['Oktober'].sum()
        tot_closing_all = int(df_ov_view['Total Closing'].sum())
        avg_aov = int(df_ov_view['AOV'].mean()) if not df_ov_view.empty else 0

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            render_bento_kpi("ri-wallet-3-line", "indigo", "Total Omset (Jan–Sep)", rp_short(tot_omset_jan_sep), f"{len(df_ov_view)} Personel CS", "indigo", pilih_cs_rapor)
        with k2:
            render_bento_kpi("ri-flashlight-line", "orange", "Omset Oktober (Realtime)", rp_short(tot_omset_okt), "Aktif" if tot_omset_okt > 0 else "Non-Aktif di Okt", "green" if tot_omset_okt > 0 else "red", "Oktober 2026")
        with k3:
            render_bento_kpi("ri-shopping-bag-3-line", "emerald", "Total Transaksi Closing", f"{tot_closing_all:,} Transaksi", "Akumulasi YTD", "green", "Jan–Sep 2026")
        with k4:
            render_bento_kpi("ri-price-tag-3-line", "indigo", "Rata-rata Nilai Donasi (AOV)", rp(avg_aov), "Per Closing", "indigo", "Rata-rata CS")

        months_cols = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober"]
        render_chart_header(
            f"Tren Pendapatan Bulanan CS (Januari – Oktober 2026) — {pilih_cs_rapor}",
            "Perbandingan perolehan omzet bulanan masing-masing CS",
            "Jan–Okt 2026", "indigo"
        )
        fig_ov_cs = go.Figure()
        palette = ['#FF6B4A', '#4F46E5', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#06B6D4', '#64748B']
        for idx_c, (_, r_cs) in enumerate(df_ov_view.iterrows()):
            y_vals = [float(r_cs[m]) for m in months_cols]
            fig_ov_cs.add_trace(go.Bar(x=months_cols, y=y_vals, name=r_cs['Nama CS'], marker_color=palette[idx_c % len(palette)], marker_cornerradius=5))
        apply_saas_plotly(fig_ov_cs, height=320, is_currency=True)
        fig_ov_cs.update_layout(barmode='group')
        st.plotly_chart(fig_ov_cs, use_container_width=True)

        df_ov_disp = df_ov_view.copy()
        for cr in ["Target Omset", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "Total Omset (Jan-Sep)", "AOV"]:
            df_ov_disp[cr] = df_ov_disp[cr].apply(rp)
        render_saas_table(df_ov_disp)

# ==============================================================================
# HALAMAN 4: LOGISTIK & GUDANG
# ==============================================================================
elif menu_pilihan == "Logistik & Gudang":
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_bento_kpi(
            "ri-book-mark-line", "emerald", "Mushaf Super Tajwid",
            f"{sa['st_siap']:,} Siap Salur", f"Jadwal Okt: {sa['st_jadwal']} Pcs (Surplus +{sa['st_gap_siap']})", "green",
            f"Belum Stiker: {sa['st_belum']} Pcs"
        )
    with c2:
        render_bento_kpi(
            "ri-book-2-line", "rose", "Mushaf Al-Wakaf (Meta + TikTok)",
            f"{sa['aw_total_siap']:,} Siap Salur", f"Jadwal Okt: {sa['aw_jadwal']} Pcs (Kurang {sa['aw_gap_total_siap']} Pcs)", "red",
            f"Belum Stiker: {sa['aw_belum_stiker']} • PO: {sa['aw_belum_ambil']:,}"
        )
    with c3:
        render_bento_kpi(
            "ri-book-open-line", "indigo", "Buku Belajar Super Tahsin",
            f"{sa['bt_siap']:,} Siap Salur".replace(",", "."), f"Sisa Target: {sa['bt_jadwal']} Pcs (Surplus +{sa['bt_gap_siap']:,})", "green",
            f"Belum Stiker: {sa['bt_belum']:,} Pcs".replace(",", ".")
        )
    with c4:
        render_bento_kpi(
            "ri-archive-line", "orange", "Total Mushaf vs Buku Tahsin",
            f"{sa['mushaf_fisik_total']:,} Mushaf".replace(",", "."), f"Siap: {sa['mushaf_siap_total']:,} • Belum: {sa['mushaf_belum_total']:,}", "orange",
            f"Total Tahsin: {sa['bt_total']:,} Pcs".replace(",", ".")
        )

    render_html(f"""
    <div class="bento-card" style="border-left: 4px solid #F97316;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;">
            <span style="font-family:'Outfit',sans-serif !important; font-size:16px; font-weight:800;">
                <i class="ri-shield-check-fill" style="color:#F97316 !important;"></i> Monitoring Kesiapan Stok (Sudah Stiker vs Belum Stiker) terhadap Jadwal Distribusi Oktober 2026
            </span>
            <span class="badge-pill bp-red"><i class="ri-alert-line"></i> Action Required: Al-Wakaf</span>
        </div>
        <div style="font-size:12.5px; color:var(--text-secondary) !important; line-height:1.6;">
            1. <b>Mushaf Super Tajwid:</b> Stok Siap Salur (Sudah Tempel Stiker) tersedia <b>{sa['st_siap']} Pcs</b>, sedangkan total kebutuhan di <i>Kalender Distribusi Oktober</i> adalah <b>{sa['st_jadwal']} Pcs</b> (5 titik lembaga) &rarr; <b style="color:#10B981 !important;">AMAN / CUKUP (Masih sisa +{sa['st_gap_siap']} Pcs siap salur)</b>.<br>
            2. <b>Mushaf Al-Wakaf:</b> Kebutuhan di <i>Kalender Distribusi Oktober</i> adalah <b>{sa['aw_jadwal']} Pcs</b> (4 titik lembaga), sedangkan stok Siap Salur (Sudah Tempel Stiker) khusus kanal TikTok hanya <b>{sa['aw_tik_siap']} Pcs</b> (kurang <b>331 Pcs</b>) dan jika digabung dengan Siap Salur Meta Ads (<b>{sa['aw_meta_siap']} Pcs</b>) totalnya baru <b>{sa['aw_total_siap']} Pcs</b> &rarr; <b style="color:#EF4444 !important;">MASIH KURANG {abs(sa['aw_gap_total_siap'])} PCS SIAP SALUR!</b> Tim gudang wajib segera menempel stiker minimal <b>33 s/d 331 Pcs</b> dari <b>{sa['aw_belum_stiker']} Pcs</b> stok <i>Al-Wakaf Belum Tempel Stiker</i> di Ruang AmalQu.<br>
            3. <b>Buku Belajar Super Tahsin:</b> Stok Siap Salur (Sudah Tempel Stiker) tersedia <b>{sa['bt_siap']:,} Pcs</b> (ditambah <b>{sa['bt_belum']:,} Pcs</b> belum tempel stiker) vs sisa target distribusi <b>{sa['bt_jadwal']} Pcs</b> &rarr; <b style="color:#10B981 !important;">AMAN / SURPLUS +{sa['bt_gap_siap']:,} PCS</b>.
        </div>
    </div>
    """)

    lg_l, lg_r = st.columns([1.55, 1.25])
    with lg_l:
        render_chart_header(
            "Komparasi Stok Siap Salur vs Belum Stiker vs Kebutuhan Jadwal Oktober",
            "Memisahkan Mushaf Super Tajwid, Mushaf Al-Wakaf, dan Buku Super Tahsin",
            "Audit Gudang vs Jadwal", "indigo"
        )
        df_comp_stok = pd.DataFrame([
            {"Produk": "Mushaf Super Tajwid", "Siap Salur (Sudah Stiker)": sa['st_siap'], "Belum Siap (Belum Stiker/PO)": sa['st_belum'], "Jadwal Distribusi Okt": sa['st_jadwal']},
            {"Produk": "Mushaf Al-Wakaf",     "Siap Salur (Sudah Stiker)": sa['aw_total_siap'], "Belum Siap (Belum Stiker/PO)": sa['aw_total_belum'], "Jadwal Distribusi Okt": sa['aw_jadwal']},
            {"Produk": "Buku Super Tahsin",   "Siap Salur (Sudah Stiker)": sa['bt_siap'], "Belum Siap (Belum Stiker/PO)": sa['bt_belum'], "Jadwal Distribusi Okt": sa['bt_jadwal']},
        ])
        fig_comp_s = go.Figure()
        fig_comp_s.add_trace(go.Bar(x=df_comp_stok['Produk'], y=df_comp_stok['Siap Salur (Sudah Stiker)'], name='Siap Salur (Sudah Stiker)', marker_color='#10B981', marker_cornerradius=6, text=df_comp_stok['Siap Salur (Sudah Stiker)'], textposition='auto'))
        fig_comp_s.add_trace(go.Bar(x=df_comp_stok['Produk'], y=df_comp_stok['Jadwal Distribusi Okt'], name='Kebutuhan Jadwal Distribusi Okt', marker_color='#4F46E5', marker_cornerradius=6, text=df_comp_stok['Jadwal Distribusi Okt'], textposition='auto'))
        fig_comp_s.add_trace(go.Bar(x=df_comp_stok['Produk'], y=df_comp_stok['Belum Siap (Belum Stiker/PO)'], name='Belum Siap (Belum Stiker / PO)', marker_color='#F97316', marker_cornerradius=6, text=df_comp_stok['Belum Siap (Belum Stiker/PO)'], textposition='auto'))
        apply_saas_plotly(fig_comp_s, height=320)
        fig_comp_s.update_layout(barmode='group')
        st.plotly_chart(fig_comp_s, use_container_width=True)

    with lg_r:
        render_chart_header("Progres Master Packing Dus (Jan – Okt 2026)", "Tahap verifikasi, stiker, packing hingga selesai distribusi", "25.824 Mushaf", "emerald")
        df_pk = db['packing_dus_bulanan']
        fig_pk = go.Figure()
        fig_pk.add_trace(go.Bar(x=df_pk['Bulan'], y=df_pk['Distribusi Selesai'], name='Selesai', marker_color='#10B981', marker_cornerradius=4))
        fig_pk.add_trace(go.Bar(x=df_pk['Bulan'], y=df_pk['Packing / Proses Distribusi'], name='Proses/Packing', marker_color='#4F46E5', marker_cornerradius=4))
        fig_pk.add_trace(go.Bar(x=df_pk['Bulan'], y=df_pk['Penamaan Mushaf (Stiker)'], name='Stiker', marker_color='#FF6B4A', marker_cornerradius=4))
        fig_pk.add_trace(go.Bar(x=df_pk['Bulan'], y=df_pk['Verifikasi (Belum Stiker)'], name='Verifikasi', marker_color='#94A3B8', marker_cornerradius=4))
        apply_saas_plotly(fig_pk, height=320)
        fig_pk.update_layout(barmode='stack')
        st.plotly_chart(fig_pk, use_container_width=True)

    sub_t3 = st.radio(
        "Pilih Tabel Inventaris & Logistik:",
        [
            "1. Tabel Audit Stok (Siap Salur vs Belum Stiker) vs Jadwal Distribusi",
            "2. Master Stok Real-Time (Per SKU, Status Stiker & Lokasi)",
            "3. Rekapitulasi Master Packing Dus Bulanan (Jan–Okt)",
            "4. Log Mutasi Masuk & Distribusi Keluar"
        ],
        horizontal=True, key="t3_sub"
    )
    if sub_t3.startswith("1."):
        render_saas_table(db['stok_vs_jadwal_df'])
    elif sub_t3.startswith("2."):
        render_saas_table(db['master_stok_rt'])
    elif sub_t3.startswith("3."):
        render_saas_table(db['packing_dus_bulanan'])
    else:
        render_saas_table(db['log_mutasi'])

# ==============================================================================
# HALAMAN 5: KALENDER DISTRIBUSI
# ==============================================================================
elif menu_pilihan == "Kalender Distribusi":
    df_kal = db['kalender_okt'].copy()
    tot_agenda_kal = len(df_kal)
    tot_mushaf_kal = int(df_kal['Jumlah Mushaf (Pcs)'].sum()) if 'Jumlah Mushaf (Pcs)' in df_kal.columns else 1004

    kc1, kc2, kc3, kc4 = st.columns(4)
    with kc1:
        render_bento_kpi("ri-calendar-check-line", "indigo", "Total Agenda Oktober", f"{tot_agenda_kal} Titik Lokasi", f"Total: {tot_mushaf_kal:,} Mushaf", "indigo", "20–31 Okt 2026")
    with kc2:
        render_bento_kpi("ri-book-mark-line", "emerald", "Jadwal Super Tajwid", f"{sa['st_jadwal']} Mushaf", f"Stok Siap: {sa['st_siap']} Pcs (Cukup)", "green", f"Surplus +{sa['st_gap_siap']} Pcs")
    with kc3:
        render_bento_kpi("ri-book-2-line", "rose", "Jadwal Al-Wakaf TikTok", f"{sa['aw_jadwal']} Mushaf", f"Siap: {sa['aw_total_siap']} Pcs (Kurang {abs(sa['aw_gap_total_siap'])})", "red", f"Stok TikTok: {sa['aw_tik_siap']} • Meta: {sa['aw_meta_siap']}")
    with kc4:
        render_bento_kpi("ri-price-tag-2-line", "orange", "Cadangan Belum Stiker", f"{sa['aw_belum_stiker']} Mushaf", "Di Ruang AmalQu (10 Box)", "orange", "Siap Ditempel Stiker")

    events_by_day = {}
    for _, r_k in df_kal.iterrows():
        tgl_s = str(r_k.get("Tanggal Agenda", "")).strip()
        m_day = re.search(r'-(\d{1,2})$', tgl_s)
        if m_day:
            d_num = int(m_day.group(1))
            events_by_day.setdefault(d_num, []).append(r_k)

    cells_list = ['<div class="cal-cell-empty"></div>' for _ in range(3)]
    for day_num in range(1, 32):
        if day_num in events_by_day:
            ev_list = events_by_day[day_num]
            tot_pcs_day = sum(int(num_clean(x.get("Jumlah Mushaf (Pcs)", 0))) for x in ev_list)
            items_html = "".join([
                f'<div class="cal-item-pill"><b>{str(x.get("Nama Lembaga Penerima",""))[:22]}</b><br><span style="color:#F97316 !important; font-weight:700;">{int(num_clean(x.get("Jumlah Mushaf (Pcs)",0)))} Pcs</span> • {str(x.get("Variasi Mushaf",""))}</div>'
                for x in ev_list
            ])
            cells_list.append(
                f'<div class="cal-cell-active">'
                f'<div class="cal-day-num"><span>{day_num} Okt</span><span class="badge-pill bp-orange" style="padding:2px 6px; font-size:10px;">{tot_pcs_day} Pcs</span></div>'
                f'<div>{items_html}</div>'
                f'</div>'
            )
        else:
            cells_list.append(
                f'<div class="cal-cell">'
                f'<div class="cal-day-num"><span>{day_num} Okt</span></div>'
                f'<div style="font-size:10px; color:var(--text-muted) !important;">-</div>'
                f'</div>'
            )
    cells_list.append('<div class="cal-cell-empty"></div>')
    desktop_cal_str = "".join(cells_list)

    mobile_cards = ""
    for day_num in sorted(events_by_day.keys()):
        ev_list = events_by_day[day_num]
        tot_pcs_day = sum(int(num_clean(x.get("Jumlah Mushaf (Pcs)", 0))) for x in ev_list)
        items_html = "".join([
            f'<div class="cal-item-pill"><b>{str(x.get("Nama Lembaga Penerima",""))}</b><br>'
            f'<span style="color:#F97316 !important; font-weight:700;">{int(num_clean(x.get("Jumlah Mushaf (Pcs)",0)))} Pcs ({str(x.get("Variasi Mushaf",""))})</span> • PIC: {str(x.get("Nama PIC",""))}<br>'
            f'<span style="color:var(--text-muted) !important;">Lokasi: {str(x.get("Wilayah / Titik Lokasi",""))}</span></div>'
            for x in ev_list
        ])
        mobile_cards += (
            f'<div class="cal-cell-active" style="margin-bottom:10px;">'
            f'<div class="cal-day-num"><span>{day_num} Oktober 2026</span><span class="badge-pill bp-orange">{len(ev_list)} Titik • {tot_pcs_day} Pcs</span></div>'
            f'<div>{items_html}</div></div>'
        )

    render_html(f"""
    <div class="bento-card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <div>
                <span style="font-family:'Outfit',sans-serif !important; font-weight:800; font-size:16.5px;">
                    <i class="ri-calendar-todo-fill" style="color:#FF6B4A !important;"></i> Kalender Visual Distribusi Mushaf — Oktober 2026
                </span>
                <div style="font-size:12px; color:var(--text-secondary) !important;">
                    20–24 Okt: <b>653 Pcs Super Tajwid</b> (Stok Siap 801 Pcs = <b>Cukup</b>) &nbsp;|&nbsp; 27–31 Okt: <b>351 Pcs Al-Wakaf</b> (Stok Siap 318 Pcs = <b>Kurang 33 Pcs Stiker</b>)
                </div>
            </div>
            <span class="badge-pill bp-orange"><i class="ri-map-pin-time-line"></i> 9 Titik Distribusi Aktif</span>
        </div>
        <div class="cal-desktop-only">
            <div class="cal-grid-7">
                <div class="cal-head-cell">SENIN</div>
                <div class="cal-head-cell">SELASA</div>
                <div class="cal-head-cell">RABU</div>
                <div class="cal-head-cell">KAMIS</div>
                <div class="cal-head-cell">JUMAT</div>
                <div class="cal-head-cell">SABTU</div>
                <div class="cal-head-cell">MINGGU</div>
                {desktop_cal_str}
            </div>
        </div>
        <div class="cal-mobile-only" style="margin-top:12px;">
            {mobile_cards}
        </div>
    </div>
    """)

    f_kal_1, f_kal_2 = st.columns([2.5, 1])
    with f_kal_1:
        render_html('<div style="font-family:\'Outfit\',sans-serif !important; font-size:15.5px; font-weight:700; padding-top:8px;"><i class="ri-table-line" style="color:#4F46E5 !important;"></i> Rincian Agenda Distribusi Scheduled (Sheet Kalender Oktober 2026 • Kolom A–J)</div>')
    with f_kal_2:
        pilih_var_kal = st.selectbox("Filter Variasi Mushaf:", ["Semua Variasi", "Super Tajwid", "Al Wakaf Tiktok"], key="kal_var")

    df_kal_disp = df_kal.copy()
    if pilih_var_kal != "Semua Variasi" and "Variasi Mushaf" in df_kal_disp.columns:
        df_kal_disp = df_kal_disp[df_kal_disp["Variasi Mushaf"] == pilih_var_kal]

    cols_aj_display = [c for c in ["No", "Tanggal Agenda", "ID Proyek", "Nama Lembaga Penerima", "Nama PIC", "Kontak WA", "Wilayah / Titik Lokasi", "Jumlah Mushaf (Pcs)", "Variasi Mushaf", "Status"] if c in df_kal_disp.columns]
    render_saas_table(df_kal_disp[cols_aj_display])

# ==============================================================================
# HALAMAN 6: DATABASE & SMART WA BLAST ENGINE
# ==============================================================================
elif menu_pilihan == "Database & WA Blast":
    dk = db['db_kpi']
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        render_bento_kpi("ri-user-follow-line", "emerald", "Donatur Terkonfirmasi", f"{dk['total_donatur']:,}".replace(",", "."), f"Konversi {dk['konversi_pct']}%", "green", f"Total Kontak: {dk['total_kontak']:,}")
    with d2:
        render_bento_kpi("ri-user-add-line", "orange", "Leads Belum Donasi", f"{dk['total_leads']:,}".replace(",", "."), "Prospek Follow-Up", "orange", "Siap Reaktivasi")
    with d3:
        render_bento_kpi("ri-vip-diamond-line", "indigo", "Total Donasi Kumulatif", rp_short(dk['total_donasi_kumulatif']), f"LTV: {rp(dk['rata_rata_donasi'])}", "indigo", "Rata-rata per Donatur")
    with d4:
        render_bento_kpi("ri-notification-badge-line", "rose", "Status Callback Segera", "12.285 Kontak", "84,94% Database", "red", "Prioritas Broadcast")

    render_html("""
    <div class="bento-card" style="margin-bottom:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <div>
                <span style="font-family:'Outfit',sans-serif !important; font-size:16px; font-weight:800;">
                    <i class="ri-send-plane-fill" style="color:#FF6B4A !important;"></i> Smart Broadcast (BC) Engine — Generator CSV 2 Kolom (Senin & Jumat)
                </span>
                <div style="font-size:12px; color:var(--text-secondary) !important; margin-top:2px;">
                    Pilih jadwal kampanye BC Anda. Sistem menyaring database otomatis menjadi file CSV 2 kolom (<b>phone number</b>, <b>nama</b>) siap pakai.
                </div>
            </div>
            <span class="badge-pill bp-indigo"><i class="ri-file-excel-2-line"></i> Auto-Clean WA Format</span>
        </div>
    </div>
    """)

    b_left, b_right = st.columns([2.1, 1])
    df_all_c = db['contacts_df'].copy()

    with b_left:
        opsi_bc = st.selectbox(
            "Pilih Skenario Kampanye WA Broadcast:",
            [
                "1. Jadwal BC SENIN — Sapaan, Do'a Awal Pekan & Reaktivasi (Status CALLBACK SEGERA / FU1 Belum)",
                "2. Jadwal BC JUMAT PAGI — Laporan Penyaluran Mushaf & Bukti BAST (FU3 Belum Dikirim)",
                "3. Jadwal BC JUMAT SIANG/SORE — Ajakan Donasi Sedekah Jumat VIP & Loyal (Prioritas A1, A2, B1, B2, C1)",
                "4. Custom Filter Manual (Pilih Kombinasi Prioritas, Status Donatur, & Reminder)"
            ],
            key="bc_scenario_sel"
        )
        df_tgt = df_all_c.copy()
        if opsi_bc.startswith("1."):
            df_tgt = df_tgt[(df_tgt['Reminder'].astype(str).str.upper().str.contains('CALLBACK')) | (df_tgt['FU1 (Sapaan)'].astype(str).str.lower().isin(['belum', '', 'nan', 'none']))]
        elif opsi_bc.startswith("2."):
            df_tgt = df_tgt[df_tgt['FU3 (Laporan Penyaluran)'].astype(str).str.lower().isin(['belum', '', 'nan', 'none'])]
        elif opsi_bc.startswith("3."):
            df_tgt = df_tgt[df_tgt['Prioritas'].astype(str).isin(['A1', 'A2', 'B1', 'B2', 'C1'])]
        else:
            fc1, fc2, fc3 = st.columns(3)
            list_pr = ["Semua"] + sorted([x for x in df_all_c['Prioritas'].dropna().unique().tolist() if str(x).strip() != ""])
            list_kt = ["Semua"] + sorted([x for x in df_all_c['Kategori'].dropna().unique().tolist() if str(x).strip() != ""])
            list_rm = ["Semua"] + sorted([x for x in df_all_c['Reminder'].dropna().unique().tolist() if str(x).strip() != ""])
            p_pr = fc1.selectbox("Prioritas:", list_pr, key="bc_f_pr")
            p_kt = fc2.selectbox("Kategori:", list_kt, key="bc_f_kt")
            p_rm = fc3.selectbox("Reminder:", list_rm, key="bc_f_rm")
            if p_pr != "Semua": df_tgt = df_tgt[df_tgt['Prioritas'] == p_pr]
            if p_kt != "Semua": df_tgt = df_tgt[df_tgt['Kategori'] == p_kt]
            if p_rm != "Semua": df_tgt = df_tgt[df_tgt['Reminder'] == p_rm]

        if df_tgt.empty:
            df_tgt = df_all_c.copy()

    with b_right:
        df_out = pd.DataFrame(columns=['phone number', 'nama'])
        if not df_tgt.empty:
            phones = df_tgt['Nomor Whatsapp'].astype(str).str.replace('wa.me/', '', regex=False).str.replace(r'\D', '', regex=True)
            phones = phones.apply(lambda x: '62' + x[1:] if x.startswith('0') else x)
            df_out['phone number'] = phones
            df_out['nama'] = df_tgt['Nama Donatur'].astype(str).str.strip()
            df_out = df_out[df_out['phone number'].str.len() >= 8].drop_duplicates(subset=['phone number'])

        if db.get('is_sample_db', False):
            est = 12285 if opsi_bc.startswith("1.") else (9805 if opsi_bc.startswith("2.") else (274 if opsi_bc.startswith("3.") else len(df_out)))
            jml_label = f"{est:,} Kontak".replace(",", ".")
        else:
            jml_label = f"{len(df_out):,} Kontak".replace(",", ".")

        render_html(f"""
        <div class="bento-card" style="border:1.5px dashed #FB923C; text-align:center; padding:18px;">
            <div style="font-size:11px; font-weight:700; color:#F97316 !important; letter-spacing:0.6px;">TARGET AUDIENS TERPILIH</div>
            <div class="metric-num" style="font-size:26px; font-weight:800; margin:6px 0;">{jml_label}</div>
            <div style="font-size:11.5px; color:var(--text-secondary) !important;">Format: <b>phone number</b>, <b>nama</b></div>
        </div>
        """)

        st.download_button(
            label="Download CSV 2 Kolom (WA Blast)",
            data=df_out.to_csv(index=False).encode('utf-8'),
            file_name=f"WA_Blast_AmalQu_{datetime.date.today().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    sub_t5 = st.radio(
        "Lihat Tabel Komposisi Segmentasi CRM (SETTING DASHBOARD Baris 2–33):",
        ["Segmentasi Prioritas Donatur (A1 – Reguler)", "Status Reminder & Status Retensi Donatur"],
        horizontal=True, key="t5_sub"
    )
    if sub_t5 == "Segmentasi Prioritas Donatur (A1 – Reguler)":
        render_saas_table(db['db_segmentasi'])
    else:
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            render_saas_table(db['db_reminder'])
        with col_r2:
            render_saas_table(db['db_status_donatur'])