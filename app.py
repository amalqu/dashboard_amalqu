import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os, re, glob, datetime, time
from urllib.parse import quote

# ==============================================================================
# 1. KONFIGURASI HALAMAN UTAMA & SESSION STATE
# ==============================================================================
st.set_page_config(
    page_title="AmalQu — Yayasan AmalQu Indonesia Peduli",
    page_icon="https://cdn.jsdelivr.net/npm/remixicon@4.2.0/icons/Finance/funds-box-fill.svg",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

def render_html(raw_html: str):
    cleaned = " ".join(line.strip() for line in raw_html.splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)

def build_logo_html(size_px=44):
    """Merender logo vektor AmalQu yang tajam dan bebas blokir ISP."""
    return (
        f'<div style="position:relative; display:inline-flex; align-items:center; justify-content:center; flex-shrink:0;">'
        f'<div style="width:{size_px}px; height:{size_px}px; border-radius:12px; '
        f'background:linear-gradient(135deg, #FF6B4A 0%, #F97316 100%); '
        f'display:inline-flex; align-items:center; justify-content:center; flex-shrink:0; '
        f'box-shadow:0 4px 14px rgba(249,115,22,0.3);">'
        f'<svg width="{int(size_px*0.56)}" height="{int(size_px*0.56)}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        f'<path d="M12 2L3 7V12C3 17.55 6.84 22.74 12 24C17.16 22.74 21 17.55 21 12V7L12 2ZM12 6.5C13.93 6.5 15.5 8.07 15.5 10C15.5 11.93 13.93 13.5 12 13.5C10.07 13.5 8.5 11.93 8.5 10C8.5 8.07 10.07 6.5 12 6.5ZM18 17.5C16.5 19.3 14.3 20.5 12 20.5C9.7 20.5 7.5 19.3 6 17.5C6.5 15.8 9.8 14.8 12 14.8C14.2 14.8 17.5 15.8 18 17.5Z" fill="white"/>'
        f'</svg></div></div>'
    )

# ==============================================================================
# 2. HELPER FORMATTING & KALKULATOR SATPAM KEUANGAN (WAJIB ADA DI ATAS)
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
    if not s or s in ["-", "None", "nan", "#REF!", "#VALUE!", "#DIV/0!", "#ERROR!", "#N/A"]:
        return 0.0
    try:
        return float(s)
    except:
        pass
    s_clean = re.sub(r'[^0-9.,-]', '', s)
    if not s_clean or s_clean == "-":
        return 0.0
    if '.' in s_clean and ',' in s_clean:
        if s_clean.rfind(',') > s_clean.rfind('.'):
            s_clean = s_clean.replace('.', '').replace(',', '.')
        else:
            s_clean = s_clean.replace(',', '')
    elif ',' in s_clean:
        parts = s_clean.split(',')
        s_clean = s_clean.replace(',', '.') if len(parts[-1]) <= 2 else s_clean.replace(',', '')
    elif s_clean.count('.') > 1:
        s_clean = s_clean.replace('.', '')
    elif '.' in s_clean:
        parts = s_clean.split('.')
        if len(parts[-1]) == 3 and len(parts[0]) >= 1:
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
# 3. KONFIGURASI 4 AKUN LOGIN (RBAC) & 16 ID GOOGLE SHEETS
# ==============================================================================
AUTH_USERS = {
    "amalqu": {
        "username_display": "Amalqu", "pw": "Allah1ahad", "role": "Admin", "title": "Super Administrator",
        "menus": ["Dashboard Overview", "Donasi & Satpam Keuangan", "Performa CS & Leads", "Logistik & Gudang", "Kalender Distribusi", "Database & WA Blast"]
    },
    "finance": {
        "username_display": "Finance", "pw": "timfinancejaya99", "role": "Finance", "title": "Divisi Finance & Audit",
        "menus": ["Dashboard Overview", "Donasi & Satpam Keuangan", "Performa CS & Leads", "Logistik & Gudang", "Kalender Distribusi", "Database & WA Blast"]
    },
    "advertiser": {
        "username_display": "Advertiser", "pw": "ngiklangacor99", "role": "Advertiser", "title": "Divisi Digital Ads & Funnel",
        "menus": ["Dashboard Overview", "Donasi & Satpam Keuangan", "Performa CS & Leads"]
    },
    "warehouse": {
        "username_display": "Warehouse", "pw": "amansulaiman123", "role": "Warehouse", "title": "Divisi Gudang & Distribusi",
        "menus": ["Logistik & Gudang", "Kalender Distribusi"]
    }
}

SHEETS_CONFIG = {
    "leads_cs":        ("11xL6IWq9D_kmgYicQUDI-CH8crpk43GnnJ-pT1M6Lkw", "1318371393"),
    "satpam":          ("1Acu1t704R4Ms3Mwz1NrJ_0x8p9xPnH8QWon1OoaoxxU", "0"),
    "data_cs":         ("1qnPuZvYMQFma-3Wk_-x2iWnrywSUFnxm8QE-riYoWus", "1504147119"),
    "master_db":       ("1zeTDweSHvALQEriL7D1n7JLNAoBcPkq8i57mRKHlS3U", "1827422698"),
    "stok_mushaf":     ("1p2fISiecchH84LUvdpEbzPsa3YQq_HAVCUvbfJTwxvE", "104"),
    "kalender_dist":   ("159nbvj-on-SM5YwcQGHp8ffzJFY7gj7AUAptpRl0wJA", "1940610974"),
    "bulan_januari":   ("1DRt5hyKSPrXDTQ32WYLPJT5Ymn6liaaV1JEeBtgKmXY", "0"),
    "bulan_februari":  ("1LDFAQhTOFBneoQnvABfxtS0cuu-9jpizIwwJh50y59s", "0"),
    "bulan_maret":     ("1FjECEskDf8xLUD8f1JUBvdhFExYsOBFxtnlMGbZAEJw", "72725914"),
    "bulan_april":     ("1qrZ_EzJU2ZFxBDtN3s4aCG_KjZkU8iP36oqKjfvpZTg", "72725914"),
    "bulan_mei":       ("1081ZvEdY0pJ8s5WUrpSNVmG5w1Y2WYdwMf1RSPa7-Rc", "1827422698"),
    "bulan_juni":      ("12BABknQvNDAiOVUQo_Rn4MTLQ67X7ufavULf5Kr-LS4", "838945917"),
    "bulan_juli":      ("15UMuw7YCdvuXhgqBPYeU3rnBZ-Tzcr-MXUOACS9yew4", "838945917"),
    "bulan_agustus":   ("1b-U4A33CqWL0_4NL88xyWgEHHOtS5xL6jmcmNH1oeuI", "198428192"),
    "bulan_september": ("1r2vurU0oQxHRwvxD0DfspfmNmBza6hXlfco65FK8AmY", "170644840"),
    "bulan_oktober":   ("10UJz62vYB4m86TC_WbOIfbgUYLp8gnfFo8-nNk_W180", "170644840"),
}

def build_gsheet_urls(key_name, sheet_name=None, prefer_gid=False):
    """Menghasilkan daftar URL CSV dengan &headers=0 dan cache-buster agar baris judul tidak tergabung."""
    if key_name not in SHEETS_CONFIG:
        return []
    sid, gid = SHEETS_CONFIG[key_name]
    cb = int(time.time() * 1000)
    base = f"https://docs.google.com/spreadsheets/d/{sid}"
    urls = []
    if prefer_gid:
        urls.append(f"{base}/export?format=csv&gid={gid}")
        urls.append(f"{base}/gviz/tq?tqx=out:csv&headers=0&gid={gid}&cb={cb}")
    if sheet_name:
        urls.append(f"{base}/gviz/tq?tqx=out:csv&headers=0&sheet={quote(sheet_name)}&cb={cb}")
        urls.append(f"{base}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}&cb={cb}")
    if not prefer_gid:
        urls.append(f"{base}/export?format=csv&gid={gid}")
        urls.append(f"{base}/gviz/tq?tqx=out:csv&headers=0&gid={gid}&cb={cb}")
    return urls

# ==============================================================================
# 4. PRECISION CSS SYSTEM
# ==============================================================================
is_dark = st.session_state.dark_mode

if is_dark:
    css_vars = """
    :root {
        --bg-main: #0B0F19; --bg-card: #111827; --bg-subcard: #1A2333; --bg-input: #1E293B;
        --text-primary: #F8FAFC; --text-secondary: #CBD5E1; --text-muted: #94A3B8;
        --border-soft: #1E293B; --border-strong: #334155;
        --table-head: #1E293B; --table-hover: #1E293B;
        --cal-active-bg: linear-gradient(180deg, rgba(249,115,22,0.18) 0%, #111827 100%);
        --cal-pill-bg: #1E293B;
    }
    """
else:
    css_vars = """
    :root {
        --bg-main: #F4F7FE; --bg-card: #FFFFFF; --bg-subcard: #F8FAFC; --bg-input: #FFFFFF;
        --text-primary: #0F172A; --text-secondary: #475569; --text-muted: #64748B;
        --border-soft: #E2E8F0; --border-strong: #CBD5E1;
        --table-head: #F8FAFC; --table-hover: #F1F5F9;
        --cal-active-bg: linear-gradient(180deg, #FFF7ED 0%, #FFFFFF 100%);
        --cal-pill-bg: #FFFFFF;
    }
    """

hide_sidebar_css = """
section[data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
""" if st.session_state.auth_user is None else ""

render_html(f"""
<link href="https://cdn.jsdelivr.net/npm/remixicon@4.2.0/fonts/remixicon.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{css_vars}
{hide_sidebar_css}

footer, [data-testid="stFooter"], [data-testid="stStatusWidget"] {{ display: none !important; }}
[data-testid="stHeader"] {{ background-color: transparent !important; height: 2rem !important; }}
.stApp, [data-testid="stAppViewContainer"] {{ background-color: var(--bg-main) !important; color: var(--text-primary) !important; }}
body, p, label, input, th, td, li {{ font-family: 'Plus Jakarta Sans', -apple-system, sans-serif !important; color: var(--text-primary); }}
h1, h2, h3, h4, h5, h6, .metric-num, .brand-title {{ font-family: 'Outfit', sans-serif !important; color: var(--text-primary) !important; }}
[data-testid="stIconMaterial"], .material-symbols-rounded, span[translate="no"] {{ font-family: 'Material Symbols Rounded' !important; font-weight: normal !important; font-style: normal !important; }}
i[class^="ri-"], i[class*=" ri-"] {{ font-family: 'remixicon' !important; font-style: normal !important; }}
.block-container {{ padding-top: 1.2rem !important; padding-bottom: 2rem !important; max-width: 1440px !important; }}
section[data-testid="stSidebar"] {{ background-color: var(--bg-card) !important; border-right: 1px solid var(--border-soft) !important; width: 265px !important; }}
.sub-box {{ background: var(--bg-subcard); border: 1px solid var(--border-soft); }}

section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap: 6px !important; display: flex !important; flex-direction: column !important; }}
section[data-testid="stSidebar"] label[data-baseweb="radio"] {{ background: transparent !important; border: 1px solid transparent !important; border-radius: 12px !important; padding: 11px 16px !important; margin: 0 !important; cursor: pointer !important; width: 100% !important; transition: all 0.15s ease !important; }}
section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:not([data-testid="stMarkdownContainer"]), section[data-testid="stSidebar"] label[data-baseweb="radio"] input {{ display: none !important; width: 0 !important; height: 0 !important; margin: 0 !important; padding: 0 !important; }}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover {{ background: var(--bg-subcard) !important; border-color: var(--border-soft) !important; }}
section[data-testid="stSidebar"] label[data-baseweb="radio"] p {{ font-size: 13.5px !important; font-weight: 600 !important; color: var(--text-secondary) !important; margin: 0 !important; }}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {{ background: linear-gradient(135deg, #FF6B4A 0%, #F97316 100%) !important; box-shadow: 0 6px 16px rgba(249, 115, 22, 0.28) !important; }}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) p {{ color: #FFFFFF !important; font-weight: 700 !important; }}

div[data-testid="stMainBlockContainer"] div[role="radiogroup"] {{ background: var(--bg-subcard) !important; padding: 5px !important; border-radius: 12px !important; display: flex !important; flex-wrap: wrap !important; gap: 6px !important; border: 1px solid var(--border-soft) !important; }}
div[data-testid="stMainBlockContainer"] label[data-baseweb="radio"] {{ background: transparent !important; padding: 7px 14px !important; border-radius: 9px !important; cursor: pointer !important; margin: 0 !important; }}
div[data-testid="stMainBlockContainer"] label[data-baseweb="radio"] > div:not([data-testid="stMarkdownContainer"]), div[data-testid="stMainBlockContainer"] label[data-baseweb="radio"] input {{ display: none !important; }}
div[data-testid="stMainBlockContainer"] label[data-baseweb="radio"] p {{ font-size: 12.5px !important; font-weight: 600 !important; color: var(--text-secondary) !important; margin: 0 !important; }}
div[data-testid="stMainBlockContainer"] label[data-baseweb="radio"]:has(input:checked) {{ background: var(--bg-card) !important; border: 1px solid var(--border-strong) !important; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important; }}
div[data-testid="stMainBlockContainer"] label[data-baseweb="radio"]:has(input:checked) p {{ color: #FF6B4A !important; font-weight: 700 !important; }}

div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, div[data-baseweb="base-input"] {{ background-color: var(--bg-input) !important; border: 1px solid var(--border-strong) !important; border-radius: 11px !important; color: var(--text-primary) !important; }}
div[data-baseweb="select"] span, div[data-baseweb="input"] input, div[data-testid="stWidgetLabel"] p {{ color: var(--text-primary) !important; font-weight: 600 !important; font-size: 13px !important; }}
div[data-baseweb="input"] input::placeholder {{ color: var(--text-muted) !important; opacity: 0.75 !important; font-size: 12.5px !important; }}
div[data-baseweb="popover"], ul[role="listbox"], li[role="option"] {{ background-color: var(--bg-card) !important; color: var(--text-primary) !important; }}
li[role="option"]:hover {{ background-color: var(--bg-subcard) !important; }}
button[kind="primary"], button[kind="secondary"], [data-testid="stDownloadButton"] button {{ background: var(--bg-card) !important; color: var(--text-primary) !important; border: 1px solid var(--border-strong) !important; border-radius: 12px !important; font-weight: 700 !important; padding: 8px 14px !important; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04) !important; }}
[data-testid="stFormSubmitButton"] button {{ background: linear-gradient(135deg, #FF6B4A 0%, #F97316 100%) !important; color: #FFFFFF !important; border: none !important; border-radius: 12px !important; padding: 11px 18px !important; box-shadow: 0 6px 16px rgba(249, 115, 22, 0.3) !important; }}
[data-testid="stFormSubmitButton"] button p {{ color: #FFFFFF !important; font-weight: 700 !important; font-size: 14px !important; }}
button[kind="primary"]:hover, button[kind="secondary"]:hover, [data-testid="stDownloadButton"] button:hover {{ border-color: #FF6B4A !important; color: #FF6B4A !important; }}

.bento-card, [data-testid="stForm"] {{ background: var(--bg-card) !important; border: 1px solid var(--border-soft) !important; border-radius: 18px !important; padding: 18px 20px !important; box-shadow: 0 4px 18px -2px rgba(0, 0, 0, 0.05) !important; margin-bottom: 14px !important; }}
.kpi-uniform {{ height: 148px; display: flex; flex-direction: column; justify-content: space-between; }}
.hero-card {{ background: linear-gradient(135deg, #4F46E5 0%, #6366F1 55%, #8B5CF6 100%); border-radius: 18px; padding: 18px 20px; height: 148px; display: flex; flex-direction: column; justify-content: space-between; color: #FFFFFF !important; box-shadow: 0 10px 24px -6px rgba(79, 70, 229, 0.4); margin-bottom: 14px; }}
.hero-card * {{ color: #FFFFFF !important; }}

.chart-header-box {{ background: var(--bg-card); border: 1px solid var(--border-soft); border-bottom: none; border-radius: 18px 18px 0 0; padding: 16px 20px 8px 20px; margin-bottom: -16px; position: relative; z-index: 2; }}
[data-testid="stPlotlyChart"] {{ background: var(--bg-card) !important; border: 1px solid var(--border-soft) !important; border-top: none !important; border-radius: 0 0 18px 18px !important; padding: 4px 12px 8px 12px !important; box-shadow: 0 4px 18px -2px rgba(0, 0, 0, 0.05) !important; margin-bottom: 14px !important; }}

.icon-box {{ width: 36px; height: 36px; border-radius: 10px; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; font-size: 17px; }}
.ib-indigo {{ background: rgba(79, 70, 229, 0.15); color: #6366F1 !important; }}
.ib-orange {{ background: rgba(249, 115, 22, 0.15); color: #F97316 !important; }}
.ib-emerald {{ background: rgba(16, 185, 129, 0.15); color: #10B981 !important; }}
.ib-rose {{ background: rgba(239, 68, 68, 0.15); color: #EF4444 !important; }}

.badge-pill {{ font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 99px; display: inline-flex; align-items: center; gap: 4px; white-space: nowrap !important; flex-shrink: 0; }}
.bp-green {{ background: rgba(16, 185, 129, 0.16); color: #10B981 !important; }}
.bp-red {{ background: rgba(239, 68, 68, 0.16); color: #EF4444 !important; }}
.bp-orange {{ background: rgba(249, 115, 22, 0.16); color: #F97316 !important; }}
.bp-indigo {{ background: rgba(79, 70, 229, 0.16); color: #6366F1 !important; }}
.nowrap-val {{ white-space: nowrap !important; font-weight: 700; }}

.saas-table-wrap {{ background: var(--bg-card); border: 1px solid var(--border-soft); border-radius: 18px; overflow-x: auto; -webkit-overflow-scrolling: touch; margin-top: 8px; margin-bottom: 16px; }}
.saas-table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 12.5px; }}
.saas-table thead tr {{ background: var(--table-head); border-bottom: 1px solid var(--border-soft); }}
.saas-table th {{ padding: 12px 15px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted) !important; white-space: nowrap; }}
.saas-table td {{ padding: 12px 15px; color: var(--text-primary) !important; font-weight: 500; border-bottom: 1px solid var(--border-soft); white-space: nowrap; }}
.saas-table tbody tr:hover {{ background: var(--table-hover); }}

.cal-desktop-only {{ display: block; }}
.cal-mobile-only {{ display: none; }}
.cal-grid-7 {{ display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }}
.cal-head-cell {{ text-align: center; font-size: 11px; font-weight: 700; color: var(--text-muted) !important; background: var(--bg-subcard); padding: 8px 4px; border-radius: 8px; border: 1px solid var(--border-soft); }}
.cal-cell {{ background: var(--bg-card); border: 1px solid var(--border-soft); border-radius: 12px; min-height: 96px; padding: 8px 10px; display: flex; flex-direction: column; justify-content: space-between; }}
.cal-cell-empty {{ background: var(--bg-subcard); border: 1px dashed var(--border-soft); border-radius: 12px; min-height: 96px; opacity: 0.45; }}
.cal-cell-active {{ background: var(--cal-active-bg); border: 1.5px solid #FB923C; border-radius: 12px; min-height: 96px; padding: 8px 10px; }}
.cal-day-num {{ font-family: 'Outfit', sans-serif !important; font-size: 13px; font-weight: 700; color: var(--text-primary) !important; display: flex; justify-content: space-between; align-items: center; gap: 4px; }}
.cal-item-pill {{ background: var(--cal-pill-bg); border: 1px solid var(--border-soft); border-left: 3px solid #F97316; border-radius: 6px; padding: 4px 6px; margin-top: 4px; font-size: 10.5px; color: var(--text-primary) !important; line-height: 1.25; }}

@media screen and (max-width: 768px) {{
    .block-container {{ padding-left: 12px !important; padding-right: 12px !important; padding-top: 2.8rem !important; }}
    div[data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; }}
    div[data-testid="column"] {{ width: 100% !important; flex: 1 1 100% !important; min-width: 100% !important; }}
    .kpi-uniform, .hero-card {{ height: auto !important; min-height: 132px !important; }}
    .cal-desktop-only {{ display: none !important; }}
    .cal-mobile-only {{ display: block !important; }}
}}
</style>
""")

# ==============================================================================
# 5. HALAMAN GERBANG LOGIN
# ==============================================================================
if st.session_state.auth_user is None:
    top_sp1, top_sp2 = st.columns([8.5, 1])
    with top_sp2:
        theme_lbl = "☀️ Terang" if is_dark else "🌙 Gelap"
        if st.button(theme_lbl, key="login_theme_btn", use_container_width=True):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

    _, login_col, _ = st.columns([1.3, 1.4, 1.3])
    with login_col:
        render_html(f"""
        <div style="text-align:center; margin-top:16px; margin-bottom:18px;">
            <div style="margin-bottom:12px;">{build_logo_html(68)}</div>
            <div style="font-family:'Outfit',sans-serif !important; font-size:30px; font-weight:800; letter-spacing:-0.5px;">AmalQu</div>
            <div style="font-size:13px; font-weight:600; color:var(--text-secondary) !important; margin-top:4px;">
                Yayasan AmalQu Indonesia Peduli • Command Center
            </div>
        </div>
        """)

        with st.form("amalqu_login_form", clear_on_submit=False):
            render_html("""
            <div style="text-align:center; margin-bottom:14px;">
                <div style="font-family:'Outfit',sans-serif !important; font-size:17px; font-weight:700;">
                    <i class="ri-shield-keyhole-line" style="color:#FF6B4A !important;"></i> Portal Akses Resmi Divisi
                </div>
                <div style="font-size:12px; color:var(--text-muted) !important; margin-top:2px;">
                    Silakan masuk menggunakan ID dan Password divisi Anda
                </div>
            </div>
            """)
            inp_user = st.text_input("ID Pengguna (Username)", placeholder="Ketik ID: Amalqu / Finance / Advertiser / Warehouse")
            inp_pass = st.text_input("Password", type="password", placeholder="Ketik Password Divisi Anda")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            submit_login = st.form_submit_button("Masuk ke Command Center", use_container_width=True)

            if submit_login:
                u_clean = str(inp_user).strip().lower()
                p_clean = str(inp_pass).strip()
                if u_clean in AUTH_USERS and AUTH_USERS[u_clean]["pw"] == p_clean:
                    st.session_state.auth_user = AUTH_USERS[u_clean]
                    st.rerun()
                else:
                    st.error("ID Pengguna atau Password salah. Pastikan huruf besar/kecil sesuai.")

        render_html("""
        <div style="text-align:center; font-size:11.5px; color:var(--text-muted) !important; margin-top:12px;">
            <i class="ri-lock-2-line"></i> Koneksi Terenkripsi • Role-Based Access Control (RBAC)
        </div>
        """)
    st.stop()

current_user = st.session_state.auth_user
user_role = current_user.get("role", "Admin")
allowed_menus = current_user.get("menus", ["Dashboard Overview"])

# ==============================================================================
# 6. TRUE REAL-TIME ENGINE & SMART TABLE SCANNER
# ==============================================================================
def fetch_all_candidate_grids(key_name, sheet_name=None, prefer_gid=False):
    """Mengambil daftar grid CSV yang valid dari semua jalur URL (export & gviz headers=0)."""
    grids = []
    for u in build_gsheet_urls(key_name, sheet_name, prefer_gid=prefer_gid):
        try:
            df = pd.read_csv(u, header=None, dtype=str).fillna("")
            if not df.empty and df.shape[1] >= 2:
                first_cell = str(df.iat[0, 0]).strip().lower()
                if "<!doctype" not in first_cell and "<html" not in first_cell:
                    grids.append(df)
        except:
            continue
    return grids

def extract_anchored_table(df_raw, anchor1, anchor2=None, stop_words=None, max_rows=100):
    if df_raw is None or df_raw.empty:
        return pd.DataFrame()
    nrows, ncols = df_raw.shape
    start_r, start_c = None, None

    # Pass 1: Pencarian persis (Exact match)
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

    # Pass 2: Pencarian fleksibel (Substring match jika Pass 1 tidak ketemu)
    if start_r is None:
        for r in range(nrows):
            for c in range(ncols):
                val = str(df_raw.iat[r, c]).strip()
                if anchor1.lower() in val.lower() and len(val) <= len(anchor1) + 15:
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

    if not headers:
        return pd.DataFrame()

    data_rows = []
    empty_streak = 0
    for r in range(start_r + 1, min(nrows, start_r + 1 + max_rows)):
        first_cell = str(df_raw.iat[r, start_c]).strip()
        second_cell = str(df_raw.iat[r, start_c + 1]).strip() if (start_c + 1) < ncols else ""
        if first_cell == "" and second_cell == "":
            empty_streak += 1
            if empty_streak >= 2:
                break
            continue
        empty_streak = 0
        if stop_words and any(sw.lower() in first_cell.lower() for sw in stop_words):
            break
        if first_cell != "":
            row_vals = [str(df_raw.iat[r, c]).strip() for c in range(start_c, end_c)]
            data_rows.append(row_vals)

    return pd.DataFrame(data_rows, columns=headers)

def fetch_table_smart(key_name, sheet_name, anchor1, anchor2=None, stop_words=None, max_rows=100, prefer_gid=False):
    """Mencoba seluruh kandidat URL sampai tabel dengan anchor tersebut benar-benar ditemukan."""
    for g in fetch_all_candidate_grids(key_name, sheet_name, prefer_gid=prefer_gid):
        t = extract_anchored_table(g, anchor1, anchor2, stop_words=stop_words, max_rows=max_rows)
        if not t.empty:
            return t
    return pd.DataFrame()

def parse_live_leads_tab(grid_cs, cs_label):
    if grid_cs is None or grid_cs.empty:
        return []
    rows_extracted = []
    nrows, ncols = grid_cs.shape
    for r in range(nrows):
        row_vals = [str(grid_cs.iat[r, c]).strip() for c in range(min(ncols, 22))]
        tgl_found = None
        tgl_col_idx = None
        for c_idx in range(min(4, len(row_vals))):
            v = row_vals[c_idx]
            if not v:
                continue
            m_iso = re.search(r'(2026-10-\d{1,2})', v)
            m_slash = re.match(r'^(\d{1,2})[/\-](\d{1,2})[/\-]2026$', v)
            m_text = re.search(r'(\d{1,2})\s*(?:okt|oct|oktober|october)', v, re.IGNORECASE)
            if m_iso:
                parts = m_iso.group(1).split("-")
                tgl_found = f"2026-10-{int(parts[2]):02d}"
                tgl_col_idx = c_idx
                break
            elif m_slash:
                d_p, m_p = int(m_slash.group(1)), int(m_slash.group(2))
                if m_p == 10:
                    tgl_found = f"2026-10-{d_p:02d}"
                    tgl_col_idx = c_idx
                    break
                elif d_p == 10 and m_p <= 31:
                    tgl_found = f"2026-10-{m_p:02d}"
                    tgl_col_idx = c_idx
                    break
            elif m_text:
                d_p = int(m_text.group(1))
                if 1 <= d_p <= 31:
                    tgl_found = f"2026-10-{d_p:02d}"
                    tgl_col_idx = c_idx
                    break

        if tgl_found and tgl_col_idx is not None:
            base_c = tgl_col_idx + 1
            def g_num(offset):
                idx = base_c + offset
                return num_clean(row_vals[idx]) if idx < len(row_vals) else 0.0
            c_valid, c_inval, closing, nominal = int(g_num(0)), int(g_num(1)), int(g_num(2)), float(g_num(3))
            sq_l, sq_c, sq_n = int(g_num(4)), int(g_num(5)), float(g_num(6))
            jq_l, jq_c, jq_n = int(g_num(7)), int(g_num(8)), float(g_num(9))
            aq_l, aq_c, aq_n = int(g_num(10)), int(g_num(11)), float(g_num(12))
            tot_fu = int(g_num(13))
            if c_valid > 0 or closing > 0 or nominal > 0 or tot_fu > 0:
                rows_extracted.append((
                    cs_label, tgl_found, c_valid, c_inval, closing, nominal,
                    sq_l, sq_c, sq_n, jq_l, jq_c, jq_n, aq_l, aq_c, aq_n, tot_fu
                ))
    return rows_extracted

def normalize_contacts_df(df_in: pd.DataFrame) -> pd.DataFrame:
    if df_in is None or df_in.empty:
        return pd.DataFrame()
    df = df_in.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if "Nama Donatur" not in df.columns and "Nomor Whatsapp" not in df.columns:
        for r_idx in range(min(10, len(df))):
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

@st.cache_data(ttl=10, show_spinner=False)
def load_all_realtime_data():
    db = {}
    sync_status = {}

    # 1. INISIALISASI STRUKTUR AWAL
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

    # 2. LIVE SYNC 1: DATA CS & FINANCE (Overview_Semua_CS)
    t_fin_live = fetch_table_smart("data_cs", "Overview_Semua_CS", "Bulan", "Target Bulanan", stop_words=["Total Target", "Sisa Target"], max_rows=15, prefer_gid=True)
    if not t_fin_live.empty:
        sync_status["Data CS & Finance"] = f"Live ({len(t_fin_live)} bln)"
        for _, r_live in t_fin_live.iterrows():
            b_name = str(r_live.get("Bulan", "")).strip()
            if b_name in db['macro_monthly']['Bulan'].values:
                v_real = num_clean(r_live.get("Realisasi Omset", 0))
                v_tgt = num_clean(r_live.get("Target Bulanan", 0))
                v_ads = num_clean(r_live.get("Budget Iklan", 0))
                v_out = num_clean(r_live.get("Total Pengeluaran", 0))
                v_net = num_clean(r_live.get("Laba Bersih", 0))
                v_rofi = num_clean(r_live.get("ROFI", 0))
                if v_real > 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'Realisasi Finance'] = v_real
                if v_tgt > 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'Target Bulanan'] = v_tgt
                if v_ads > 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'Budget Iklan'] = v_ads
                if v_out > 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'Total Pengeluaran'] = v_out
                if v_net != 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'Laba Bersih'] = v_net
                if v_rofi > 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'ROFI'] = v_rofi
    else:
        sync_status["Data CS & Finance"] = "Fallback"

    t_cs_live = fetch_table_smart("data_cs", "Overview_Semua_CS", "Nama CS", "Target Omset", stop_words=["Total", "Rata-rata"], max_rows=12, prefer_gid=True)
    if not t_cs_live.empty:
        for _, r_c in t_cs_live.iterrows():
            c_name = str(r_c.get("Nama CS", "")).strip()
            if c_name in db['cs_overview']['Nama CS'].values:
                for m_col in ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September"]:
                    if m_col in t_cs_live.columns:
                        db['cs_overview'].loc[db['cs_overview']['Nama CS'] == c_name, m_col] = num_clean(r_c.get(m_col, 0))
                if "Total Omset" in t_cs_live.columns:
                    db['cs_overview'].loc[db['cs_overview']['Nama CS'] == c_name, "Total Omset (Jan-Sep)"] = num_clean(r_c.get("Total Omset", 0))
                if "Total Closing" in t_cs_live.columns:
                    db['cs_overview'].loc[db['cs_overview']['Nama CS'] == c_name, "Total Closing"] = int(num_clean(r_c.get("Total Closing", 0)))
                if "AOV (Rata-rata Donasi)" in t_cs_live.columns:
                    db['cs_overview'].loc[db['cs_overview']['Nama CS'] == c_name, "AOV"] = int(num_clean(r_c.get("AOV (Rata-rata Donasi)", 0)))

    # 3. LIVE SYNC 2: DASHBOARD CS OKTOBER
    db['okt_kpi'] = {"total_donasi": 108674008, "target": 500000000, "capaian_pct": 21.7, "donasi_final": 102046008, "harian_terbaru": 8861008, "verifikasi_pct": 93.9}
    db['okt_cs_table'] = pd.DataFrame([
        {"CS / CRM": "Salma", "Harian (Total)": 2464008, "Harian (Final)": 2464008, "Mingguan (Total)": 2464008, "Mingguan (Final)": 2464008, "Bulanan (Total)": 32863008, "Bulanan (Final)": 29870008, "% Verifikasi": "90,9%", "Total Transaksi": 227, "Target (Rp)": 200000000, "% Capaian": "16,4%"},
        {"CS / CRM": "Aulia", "Harian (Total)": 453000,  "Harian (Final)": 453000,  "Mingguan (Total)": 453000,  "Mingguan (Final)": 453000,  "Bulanan (Total)": 9813000,  "Bulanan (Final)": 8983000,  "% Verifikasi": "91,5%", "Total Transaksi": 93,  "Target (Rp)": 50000000,  "% Capaian": "19,6%"},
        {"CS / CRM": "Nisa",  "Harian (Total)": 5944000, "Harian (Final)": 5944000, "Mingguan (Total)": 5944000, "Mingguan (Final)": 5944000, "Bulanan (Total)": 65998000, "Bulanan (Final)": 63193000, "% Verifikasi": "95,7%", "Total Transaksi": 440, "Target (Rp)": 200000000, "% Capaian": "33,0%"},
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

    t_cs_okt = fetch_table_smart("bulan_oktober", "Dashboard CS", "CS / CRM", "Harian", stop_words=["TOTAL", "ANALISIS"], max_rows=10, prefer_gid=True)
    if not t_cs_okt.empty and "Bulanan (Total)" in t_cs_okt.columns:
        for col_n in ["Harian (Total)", "Harian (Final)", "Mingguan (Total)", "Mingguan (Final)", "Bulanan (Total)", "Bulanan (Final)", "Target (Rp)"]:
            if col_n in t_cs_okt.columns:
                t_cs_okt[col_n] = t_cs_okt[col_n].apply(num_clean)
        if "Total Transaksi" in t_cs_okt.columns:
            t_cs_okt["Total Transaksi"] = t_cs_okt["Total Transaksi"].apply(lambda x: int(num_clean(x)))
        db['okt_cs_table'] = t_cs_okt
        tot_don_okt = float(t_cs_okt['Bulanan (Total)'].sum())
        tot_fin_okt = float(t_cs_okt['Bulanan (Final)'].sum())
        if tot_don_okt > 0:
            db['okt_kpi']['total_donasi'] = tot_don_okt
            db['okt_kpi']['donasi_final'] = tot_fin_okt
            db['okt_kpi']['verifikasi_pct'] = round(tot_fin_okt / tot_don_okt * 100, 1)
            db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == 'Oktober', 'Omset CS'] = tot_don_okt
            for _, r_ok in t_cs_okt.iterrows():
                c_nm = str(r_ok.get("CS / CRM", "")).strip()
                if c_nm in db['cs_overview']['Nama CS'].values:
                    db['cs_overview'].loc[db['cs_overview']['Nama CS'] == c_nm, 'Oktober'] = float(r_ok.get("Bulanan (Total)", 0))

    t_src_okt = fetch_table_smart("bulan_oktober", "Dashboard CS", "CS / CRM", "Leads Meta", stop_words=["TOTAL", "TREN"], max_rows=10, prefer_gid=True)
    if not t_src_okt.empty and "Leads Meta" in t_src_okt.columns:
        for col_s in ["Leads Meta", "Repeat Order CRM", "Repeat Order non CRM", "Lainnya", "Total Nominal"]:
            if col_s in t_src_okt.columns:
                t_src_okt[col_s] = t_src_okt[col_s].apply(num_clean)
        db['okt_sumber'] = t_src_okt

    t_har_okt = fetch_table_smart("bulan_oktober", "Dashboard CS", "Tanggal", "Salma", stop_words=["TOTAL", "RATA"], max_rows=35, prefer_gid=True)
    if not t_har_okt.empty and "Salma" in t_har_okt.columns:
        har_rows = []
        for _, r_h in t_har_okt.iterrows():
            tgl_v = str(r_h.get("Tanggal", "")).strip()
            v_salma = num_clean(r_h.get("Salma", 0))
            v_aulia = num_clean(r_h.get("Aulia", 0))
            v_nisa = num_clean(r_h.get("Nisa", 0))
            v_tot = num_clean(r_h.get("Total Donasi", v_salma + v_aulia + v_nisa))
            v_fin = num_clean(r_h.get("Donasi Final", 0))
            if v_tot > 0 or v_salma > 0 or v_aulia > 0 or v_nisa > 0:
                har_rows.append({"Tanggal": tgl_v, "Salma": v_salma, "Aulia": v_aulia, "Nisa": v_nisa, "Total Donasi": v_tot, "Donasi Final": v_fin})
        if har_rows:
            db['okt_harian'] = pd.DataFrame(har_rows)
            sync_status["Dashboard CS Oktober"] = f"Live ({len(har_rows)} hari)"
        else:
            sync_status["Dashboard CS Oktober"] = "Live"
    else:
        sync_status["Dashboard CS Oktober"] = "Live" if not t_cs_okt.empty else "Fallback"

    df_m = db['macro_monthly']
    df_m['Selisih Target'] = df_m['Realisasi Finance'] - df_m['Target Bulanan']
    df_m['Selisih Finance vs CS'] = df_m['Realisasi Finance'] - df_m['Omset CS']
    df_m['% Capaian'] = np.where(df_m['Target Bulanan'] > 0, (df_m['Realisasi Finance'] / df_m['Target Bulanan'] * 100).round(1), 0.0)

    # 4. LIVE SYNC 3: PENGELOLAAN LEADS CS AKTIF OKTOBER
    leads_rows_default = [
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
        ("Aulia", "2026-10-05", 4, 0, 2, 224000, 0, 0, 0, 0, 0, 0, 4, 2, 224000, 0),
        ("Aulia", "2026-10-06", 7, 2, 5, 719000, 0, 0, 0, 0, 0, 0, 7, 5, 719000, 0),
    ]

    live_leads_all = []
    for tab_nm, cs_lbl in [("CS NISA", "Nisa"), ("CS SALMA", "Salma"), ("CS AUL", "Aulia")]:
        for g_cs in fetch_all_candidate_grids("leads_cs", tab_nm, prefer_gid=False):
            parsed = parse_live_leads_tab(g_cs, cs_lbl)
            if parsed:
                live_leads_all.extend(parsed)
                break

    if len(live_leads_all) >= 5:
        sync_status["Leads Harian CS"] = f"Live ({len(live_leads_all)} baris)"
        leads_source = live_leads_all
    else:
        sync_status["Leads Harian CS"] = "Fallback"
        leads_source = leads_rows_default

    df_leads = pd.DataFrame(leads_source, columns=[
        "Nama CS", "Tanggal", "Chat Valid", "Chat Invalid", "Closing", "Nominal",
        "SantriQu_Leads", "SantriQu_Closing", "SantriQu_Nominal",
        "JariyahQu_Leads", "JariyahQu_Closing", "JariyahQu_Nominal",
        "AmalQu_Leads", "AmalQu_Closing", "AmalQu_Nominal", "Total Follow Up"
    ])
    df_leads["Conv Rate (%)"] = np.where(df_leads["Chat Valid"] > 0, (df_leads["Closing"] / df_leads["Chat Valid"] * 100).round(1), 0.0)
    db['leads_okt'] = df_leads

    # 5. LIVE SYNC 4: LOGISTIK & GUDANG
    db['master_stok_rt'] = pd.DataFrame([
        {"ID Produk": "ST-META-01", "Nama Produk / Mushaf": "Super Tajwid", "Channel Perolehan": "Meta Ads", "Status Stiker & Fisik": "Sudah Tempel Stiker", "Kategori": "Mushaf Al-Qur'an", "Stok Awal": 861,  "Total Masuk": 0,   "Total Terdistribusi": 60,  "Stok Akhir Real-Time": 801,  "Status Stok": "Tersedia", "Catatan / Lokasi": "Siap distribusi operasional"},
        {"ID Produk": "AW-META-01", "Nama Produk / Mushaf": "Al Wakaf",     "Channel Perolehan": "Meta Ads", "Status Stiker & Fisik": "Sudah Tempel Stiker", "Kategori": "Mushaf Al-Qur'an", "Stok Awal": 288,  "Total Masuk": 50,  "Total Terdistribusi": 40,  "Stok Akhir Real-Time": 298,  "Status Stok": "Tersedia", "Catatan / Lokasi": "Siap kirim ke penerima manfaat"},
        {"ID Produk": "AW-META-02", "Nama Produk / Mushaf": "Al Wakaf",     "Channel Perolehan": "Meta Ads", "Status Stiker & Fisik": "Belum Tempel Stiker", "Kategori": "Mushaf Al-Qur'an", "Stok Awal": 480,  "Total Masuk": 0,   "Total Terdistribusi": 0,   "Stok Akhir Real-Time": 480,  "Status Stok": "Tersedia", "Catatan / Lokasi": "Lokasi: Ruang AmalQu (10 box x 48)"},
        {"ID Produk": "AW-META-03", "Nama Produk / Mushaf": "Al Wakaf",     "Channel Perolehan": "Meta Ads", "Status Stiker & Fisik": "Belum Diambil",       "Kategori": "Mushaf Al-Qur'an", "Stok Awal": 1848, "Total Masuk": 0,   "Total Terdistribusi": 0,   "Stok Akhir Real-Time": 1848, "Status Stok": "Tersedia", "Catatan / Lokasi": "Sisa PO belum diambil percetakan"},
        {"ID Produk": "AW-TIK-01",  "Nama Produk / Mushaf": "Al Wakaf",     "Channel Perolehan": "TikTok",   "Status Stiker & Fisik": "Sudah Tempel Stiker", "Kategori": "Mushaf Al-Qur'an", "Stok Awal": 20,   "Total Masuk": 0,   "Total Terdistribusi": 0,   "Stok Akhir Real-Time": 20,   "Status Stok": "Menipis",  "Catatan / Lokasi": "Stok berjalan TikTok Ads"},
        {"ID Produk": "BT-TIK-01",  "Nama Produk / Mushaf": "Buku Tahsin",  "Channel Perolehan": "TikTok",   "Status Stiker & Fisik": "Sudah Tempel Stiker", "Kategori": "Buku Tahsin",      "Stok Awal": 1288, "Total Masuk": 200, "Total Terdistribusi": 100, "Stok Akhir Real-Time": 1388, "Status Stok": "Tersedia", "Catatan / Lokasi": "Buku Tahsin siap kirim"},
        {"ID Produk": "BT-TIK-02",  "Nama Produk / Mushaf": "Buku Tahsin",  "Channel Perolehan": "TikTok",   "Status Stiker & Fisik": "Belum Tempel Stiker", "Kategori": "Buku Tahsin",      "Stok Awal": 1500, "Total Masuk": 0,   "Total Terdistribusi": 0,   "Stok Akhir Real-Time": 1500, "Status Stok": "Tersedia", "Catatan / Lokasi": "Menunggu penempelan stiker wakaf"},
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

    t_ms = fetch_table_smart("stok_mushaf", "Master_Stok_Real-Time", "ID Produk", "Nama Produk", max_rows=30, prefer_gid=False)
    if not t_ms.empty and "Stok Akhir Real-Time" in t_ms.columns:
        for col_i in ["Stok Awal", "Total Masuk", "Total Terdistribusi", "Stok Akhir Real-Time"]:
            if col_i in t_ms.columns:
                t_ms[col_i] = t_ms[col_i].apply(lambda x: int(num_clean(x)))
        db['master_stok_rt'] = t_ms
        sync_status["Stok Mushaf Gudang"] = f"Live ({len(t_ms)} SKU)"
    else:
        sync_status["Stok Mushaf Gudang"] = "Fallback"

    t_kb = fetch_table_smart("stok_mushaf", "Kebutuhan_Bulanan", "ID Target", "Periode Bulan", max_rows=25, prefer_gid=False)
    if not t_kb.empty:
        db['kebutuhan_bulanan'] = t_kb

    t_mut = fetch_table_smart("stok_mushaf", "Log_Mutasi_Distribusi", "No Mutasi", "Tanggal", max_rows=50, prefer_gid=False)
    if not t_mut.empty:
        db['log_mutasi'] = t_mut

    # 6. LIVE SYNC 5: KALENDER DISTRIBUSI OKTOBER 2026
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

    t_kal = fetch_table_smart("kalender_dist", "Kalender Oktober 2026", "No", "Tanggal Agenda", stop_words=["TOTAL"], max_rows=45, prefer_gid=True)
    if not t_kal.empty and "Nama Lembaga Penerima" in t_kal.columns:
        cols_aj = t_kal.columns[:10].tolist()
        t_kal_aj = t_kal[cols_aj].copy()
        if "Jumlah Mushaf (Pcs)" in t_kal_aj.columns:
            t_kal_aj["Jumlah Mushaf (Pcs)"] = t_kal_aj["Jumlah Mushaf (Pcs)"].apply(lambda x: int(num_clean(x)))
        t_kal_aj = t_kal_aj[t_kal_aj["Nama Lembaga Penerima"].astype(str).str.strip() != ""]
        if not t_kal_aj.empty:
            db['kalender_okt'] = t_kal_aj
            sync_status["Kalender Distribusi"] = f"Live ({len(t_kal_aj)} titik)"
        else:
            sync_status["Kalender Distribusi"] = "Fallback"
    else:
        sync_status["Kalender Distribusi"] = "Fallback"

    # KALKULASI DINAMIS AUDIT STOK SIAP SALUR VS BELUM STIKER TERHADAP JADWAL DISTRIBUSI
    df_ms = db['master_stok_rt']
    df_kal = db['kalender_okt']

    st_siap = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Super Tajwid', case=False, na=False)) & (df_ms['Status Stiker & Fisik'].str.contains('Sudah', case=False, na=False))]['Stok Akhir Real-Time'].sum()) if not df_ms.empty else 0
    st_belum = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Super Tajwid', case=False, na=False)) & (~df_ms['Status Stiker & Fisik'].str.contains('Sudah', case=False, na=False))]['Stok Akhir Real-Time'].sum()) if not df_ms.empty else 0
    aw_meta_siap = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Al Wakaf', case=False, na=False)) & (df_ms['Channel Perolehan'].str.contains('Meta', case=False, na=False)) & (df_ms['Status Stiker & Fisik'].str.contains('Sudah', case=False, na=False))]['Stok Akhir Real-Time'].sum()) if not df_ms.empty else 0
    aw_meta_belum_stiker = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Al Wakaf', case=False, na=False)) & (df_ms['Status Stiker & Fisik'].str.contains('Belum Tempel', case=False, na=False))]['Stok Akhir Real-Time'].sum()) if not df_ms.empty else 0
    aw_meta_belum_ambil = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Al Wakaf', case=False, na=False)) & (df_ms['Status Stiker & Fisik'].str.contains('Belum Diambil', case=False, na=False))]['Stok Akhir Real-Time'].sum()) if not df_ms.empty else 0
    aw_tik_siap = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Al Wakaf', case=False, na=False)) & (df_ms['Channel Perolehan'].str.contains('TikTok', case=False, na=False)) & (df_ms['Status Stiker & Fisik'].str.contains('Sudah', case=False, na=False))]['Stok Akhir Real-Time'].sum()) if not df_ms.empty else 0

    aw_total_siap = aw_meta_siap + aw_tik_siap
    aw_total_belum = aw_meta_belum_stiker + aw_meta_belum_ambil

    bt_siap = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Tahsin', case=False, na=False)) & (df_ms['Status Stiker & Fisik'].str.contains('Sudah', case=False, na=False))]['Stok Akhir Real-Time'].sum()) if not df_ms.empty else 0
    bt_belum = int(df_ms[(df_ms['Nama Produk / Mushaf'].str.contains('Tahsin', case=False, na=False)) & (~df_ms['Status Stiker & Fisik'].str.contains('Sudah', case=False, na=False))]['Stok Akhir Real-Time'].sum()) if not df_ms.empty else 0

    jadwal_st = int(df_kal[df_kal['Variasi Mushaf'].astype(str).str.contains('Super Tajwid', case=False, na=False)]['Jumlah Mushaf (Pcs)'].sum()) if not df_kal.empty and 'Variasi Mushaf' in df_kal.columns else 653
    jadwal_aw = int(df_kal[df_kal['Variasi Mushaf'].astype(str).str.contains('Al Wakaf', case=False, na=False)]['Jumlah Mushaf (Pcs)'].sum()) if not df_kal.empty and 'Variasi Mushaf' in df_kal.columns else 351
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
        {"Kategori": "Mushaf Al-Qur'an", "Jenis Produk": "Mushaf Super Tajwid (Meta Ads)", "Siap Salur (Sudah Stiker)": f"{st_siap:,} Pcs", "Belum Stiker (Di Gudang)": f"{st_belum:,} Pcs", "Belum Diambil (PO Cetak)": "0 Pcs", "Total Stok Fisik": f"{st_siap + st_belum:,} Pcs", "Kebutuhan Jadwal Okt": f"{jadwal_st:,} Pcs", "Selisih Siap Salur": f"{st_siap - jadwal_st:+,} Pcs", "Status Kecukupan": "Siap Salur Cukup" if st_siap >= jadwal_st else f"Defisit ({st_siap - jadwal_st} Pcs)"},
        {"Kategori": "Mushaf Al-Qur'an", "Jenis Produk": "Mushaf Al-Wakaf (TikTok)", "Siap Salur (Sudah Stiker)": f"{aw_tik_siap:,} Pcs", "Belum Stiker (Di Gudang)": "0 Pcs", "Belum Diambil (PO Cetak)": "0 Pcs", "Total Stok Fisik": f"{aw_tik_siap:,} Pcs", "Kebutuhan Jadwal Okt": f"{jadwal_aw:,} Pcs", "Selisih Siap Salur": f"{aw_tik_siap - jadwal_aw:+,} Pcs", "Status Kecukupan": "Siap Salur Cukup" if aw_tik_siap >= jadwal_aw else f"Defisit ({aw_tik_siap - jadwal_aw} Pcs)"},
        {"Kategori": "Mushaf Al-Qur'an", "Jenis Produk": "Mushaf Al-Wakaf (Meta Ads)", "Siap Salur (Sudah Stiker)": f"{aw_meta_siap:,} Pcs", "Belum Stiker (Di Gudang)": f"{aw_meta_belum_stiker:,} Pcs", "Belum Diambil (PO Cetak)": f"{aw_meta_belum_ambil:,} Pcs", "Total Stok Fisik": f"{aw_meta_siap + aw_meta_belum_stiker + aw_meta_belum_ambil:,} Pcs", "Kebutuhan Jadwal Okt": "Subsidi Silang Al-Wakaf", "Selisih Siap Salur": f"{aw_total_siap - jadwal_aw:+,} Pcs (Gabungan)", "Status Kecukupan": "Siap Salur Cukup" if aw_total_siap >= jadwal_aw else f"Perlu Tempel Stiker {abs(aw_total_siap - jadwal_aw)} Pcs"},
        {"Kategori": "Buku Super Tahsin", "Jenis Produk": "Buku Belajar Tahsin AmalQu", "Siap Salur (Sudah Stiker)": f"{bt_siap:,} Pcs", "Belum Stiker (Di Gudang)": f"{bt_belum:,} Pcs", "Belum Diambil (PO Cetak)": "0 Pcs", "Total Stok Fisik": f"{bt_siap + bt_belum:,} Pcs", "Kebutuhan Jadwal Okt": f"{jadwal_bt:,} Pcs (Sisa Target)", "Selisih Siap Salur": f"{bt_siap - jadwal_bt:+,} Pcs", "Status Kecukupan": "Siap Salur Cukup" if bt_siap >= jadwal_bt else f"Defisit ({bt_siap - jadwal_bt} Pcs)"}
    ])

    # 7. LIVE SYNC 6: MASTER DATABASE DONATUR & SEGMENTASI CRM
    db['db_kpi'] = {"total_donatur": 14464, "total_leads": 3416, "total_kontak": 17880, "konversi_pct": 80.9, "total_donasi_kumulatif": 2604405566, "rata_rata_donasi": 180061}
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
    for u_db in build_gsheet_urls("master_db", "DATABASE", prefer_gid=False):
        try:
            df_try = pd.read_csv(u_db, dtype=str)
            if not df_try.empty and df_try.shape[1] >= 4:
                df_contacts_raw = df_try
                break
        except:
            continue

    df_contacts = normalize_contacts_df(df_contacts_raw)
    if not df_contacts.empty and len(df_contacts) >= 5:
        sync_status["Master Database CRM"] = f"Live ({len(df_contacts):,} kontak)"
        db['is_sample_db'] = False
        db['db_kpi']['total_donatur'] = len(df_contacts)
    else:
        sync_status["Master Database CRM"] = "Fallback"
        db['is_sample_db'] = True
        df_contacts = pd.DataFrame([
            {"Nama Donatur": "Donatur Prioritas A1", "Nomor Whatsapp": "628000000001", "PiC": "CS Nisa",  "Program": "Waqaf/Mushaf", "Donasi Terakhir": "1 Oktober 2026",   "Kategori": "Donatur Rutin", "FU1 (Sapaan)": "Sudah", "FU3 (Laporan Penyaluran)": "Sudah", "Prioritas": "A1",      "Reminder": "AMAN"},
            {"Nama Donatur": "Donatur Aktif B1",     "Nomor Whatsapp": "628000000002", "PiC": "CS Salma", "Program": "AmalQu",       "Donasi Terakhir": "2 Oktober 2026",   "Kategori": "Donatur Aktif", "FU1 (Sapaan)": "Sudah", "FU3 (Laporan Penyaluran)": "Belum", "Prioritas": "B1",      "Reminder": "PANTAU"},
            {"Nama Donatur": "Donatur Baru Reguler", "Nomor Whatsapp": "628000000003", "PiC": "CS Aulia", "Program": "AmalQu",       "Donasi Terakhir": "5 Oktober 2026",   "Kategori": "Donatur Baru",  "FU1 (Sapaan)": "Belum", "FU3 (Laporan Penyaluran)": "Belum", "Prioritas": "Reguler", "Reminder": "CALLBACK SEGERA"},
            {"Nama Donatur": "Donatur Reaktivasi D4","Nomor Whatsapp": "628000000004", "PiC": "CRM Olive","Program": "Waqaf/Mushaf", "Donasi Terakhir": "14 Februari 2026", "Kategori": "Donatur Churn", "FU1 (Sapaan)": "Belum", "FU3 (Laporan Penyaluran)": "Belum", "Prioritas": "D4",      "Reminder": "CALLBACK SEGERA"},
        ])

    db['contacts_df'] = df_contacts
    db['sync_status'] = sync_status
    db['live_count'] = sum(1 for v in sync_status.values() if str(v).startswith("Live"))
    db['last_sync'] = datetime.datetime.now().strftime("%d %b %Y • %H:%M:%S WIB")
    return db

db = load_all_realtime_data()
df_macro = db['macro_monthly']
sa = db['stok_audit']

# ==============================================================================
# 7. SIDEBAR NAVIGASI & STATUS DIAGNOSTIK SERVER
# ==============================================================================
with st.sidebar:
    render_html(f"""
    <div style="display:flex; align-items:center; gap:12px; padding:4px 4px 18px 4px; border-bottom:1px solid var(--border-soft); margin-bottom:14px;">
        {build_logo_html(44)}
        <div>
            <div class="brand-title" style="font-family:'Outfit',sans-serif !important; font-weight:800; font-size:21px; line-height:1.15; letter-spacing:-0.3px;">AmalQu</div>
            <div class="brand-sub" style="font-size:11px; font-weight:600; line-height:1.3; margin-top:2px;">Yayasan AmalQu Indonesia Peduli</div>
        </div>
    </div>
    <div style="font-size:11px; font-weight:700; color:var(--text-muted) !important; letter-spacing:0.8px; text-transform:uppercase; padding:4px 6px 8px 6px;">
        MENU DIVISI ({user_role.upper()})
    </div>
    """)

    menu_pilihan = st.radio("Navigasi Utama", allowed_menus, label_visibility="collapsed")

    live_cnt = db.get("live_count", 0)
    tot_mod = len(db.get("sync_status", {}))
    sync_color = "#10B981" if live_cnt == tot_mod else ("#F59E0B" if live_cnt > 0 else "#EF4444")
    sync_label = f"● {live_cnt}/{tot_mod} Modul Live Terbaca" if live_cnt > 0 else "⚠️ Menggunakan Data Fallback"

    render_html(f"""
    <div class="sub-box" style="margin-top:20px; padding:13px 14px; border-radius:14px;">
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
            <i class="ri-shield-user-line" style="color:#6366F1 !important; font-size:16px;"></i>
            <span style="font-size:12.5px; font-weight:700;">{current_user['username_display']} ({user_role})</span>
        </div>
        <div style="font-size:11px; color:var(--text-secondary) !important; line-height:1.45;">
            {current_user['title']}<br>
            <span style="color:{sync_color} !important; font-weight:700;">{sync_label}</span><br>
            <span style="font-size:10.5px; color:var(--text-muted) !important;">Sync: {db['last_sync']}</span>
        </div>
    </div>
    """)

    with st.expander("📡 Cek Detail Baris Live per Sheet"):
        for mod_name, stat_txt in db.get("sync_status", {}).items():
            ic = "🟢" if str(stat_txt).startswith("Live") else "🟠"
            st.caption(f"**{mod_name}**: {ic} {stat_txt}")

    sb_col1, sb_col2 = st.columns(2)
    with sb_col1:
        if st.button("Sync Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with sb_col2:
        if st.button("Logout", use_container_width=True):
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
    <div class="bento-card kpi-uniform">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
            <span style="font-size:12.5px; font-weight:600; color:var(--text-secondary) !important; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{title}</span>
            <div class="icon-box {ib_map.get(color_theme, 'ib-indigo')}"><i class="{icon_cls}"></i></div>
        </div>
        <div class="metric-num" style="font-size:25px; font-weight:800; letter-spacing:-0.5px; white-space:nowrap;">
            {value}
        </div>
        <div style="display:flex; align-items:center; justify-content:space-between; gap:6px; flex-wrap:nowrap;">
            <span class="badge-pill {bp_map.get(badge_theme, 'bp-green')}">
                <i class="{arrow_ic}"></i> {badge_text}
            </span>
            <span style="font-size:11px; color:var(--text-muted) !important; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{subtext}</span>
        </div>
    </div>
    """)

def render_chart_header(title_text, subtitle_text="", badge_text="", badge_theme="indigo"):
    bp_map = {"green": "bp-green", "red": "bp-red", "orange": "bp-orange", "indigo": "bp-indigo"}
    badge_html = f'<span class="badge-pill {bp_map.get(badge_theme, "bp-indigo")}">{badge_text}</span>' if badge_text else ""
    sub_html = f'<div style="font-size:11.5px; color:var(--text-muted) !important; margin-top:2px;">{subtitle_text}</div>' if subtitle_text else ""
    render_html(f"""
    <div class="chart-header-box">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
            <div style="min-width:0;">
                <div style="font-family:'Outfit',sans-serif !important; font-size:15.5px; font-weight:700; color:var(--text-primary) !important;">{title_text}</div>
                {sub_html}
            </div>
            {badge_html}
        </div>
    </div>
    """)

def apply_saas_plotly(fig, height=320, is_currency=False):
    bg_col = "#111827" if is_dark else "#FFFFFF"
    txt_col = "#F8FAFC" if is_dark else "#0F172A"
    sub_col = "#94A3B8" if is_dark else "#475569"
    grid_col = "#1E293B" if is_dark else "#F1F5F9"
    fig.update_layout(
        title=None, height=height, margin=dict(l=10, r=10, t=14, b=48), paper_bgcolor=bg_col, plot_bgcolor=bg_col,
        font=dict(family="Plus Jakarta Sans, sans-serif", size=11.5, color=txt_col), hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5, font=dict(family="Plus Jakarta Sans, sans-serif", size=11.5, color=txt_col), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, linecolor=grid_col, tickfont=dict(color=sub_col, size=11), title=None),
        yaxis=dict(gridcolor=grid_col, zeroline=False, tickfont=dict(color=sub_col, size=11), title=None, tickprefix="Rp " if is_currency else "")
    )
    return fig

def make_gauge_chart(value, max_val=100, suffix="%", bar_color="#10B981"):
    bg_col = "#111827" if is_dark else "#FFFFFF"
    txt_col = "#F8FAFC" if is_dark else "#0F172A"
    track_col = "#1E293B" if is_dark else "#F1F5F9"
    fig = go.Figure(go.Indicator(mode="gauge+number", value=value, number={'suffix': suffix, 'font': {'size': 32, 'color': txt_col, 'family': 'Outfit, sans-serif'}}, gauge={'axis': {'range': [0, max_val], 'visible': False}, 'bar': {'color': bar_color, 'thickness': 0.8}, 'bgcolor': track_col, 'borderwidth': 0, 'shape': 'angular'}))
    fig.update_layout(height=230, margin=dict(l=16, r=16, t=24, b=10), paper_bgcolor=bg_col, plot_bgcolor=bg_col, font=dict(color=txt_col, family="Plus Jakarta Sans, sans-serif"))
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
    render_html(f'<div class="saas-table-wrap"><table class="saas-table"><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></div>')

# ==============================================================================
# 9. TOP HEADER BAR
# ==============================================================================
hdr_col_left, hdr_col_right = st.columns([7.5, 1.1])
with hdr_col_left:
    render_html(f"""
    <div class="bento-card" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; padding:12px 18px !important; margin-bottom:14px !important;">
        <div style="display:flex; align-items:center; gap:12px;">
            {build_logo_html(40)}
            <div>
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <span style="font-family:'Outfit',sans-serif !important; font-size:20px; font-weight:800; letter-spacing:-0.4px;">AmalQu</span>
                    <span class="badge-pill bp-orange">{menu_pilihan}</span>
                </div>
                <div style="font-size:12px; font-weight:600; color:var(--text-secondary) !important;">Yayasan AmalQu Indonesia Peduli • Enterprise Command Center</div>
            </div>
        </div>
        <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
            <span class="badge-pill bp-indigo"><i class="ri-user-star-line"></i> {current_user['username_display']} ({user_role})</span>
            <span class="badge-pill bp-green"><i class="ri-checkbox-blank-circle-fill" style="font-size:8px;"></i> Live Sync 10s</span>
        </div>
    </div>
    """)
with hdr_col_right:
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    theme_icon_btn = "☀️ Terang" if is_dark else "🌙 Gelap"
    if st.button(theme_icon_btn, key="top_theme_toggle", help="Ubah Mode Gelap / Terang", use_container_width=True):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

# ==============================================================================
# HALAMAN 1: DASHBOARD OVERVIEW
# ==============================================================================
if menu_pilihan == "Dashboard Overview":
    okt_r = df_macro[df_macro['Bulan'] == 'Oktober'].iloc[0] if not df_macro.empty else pd.Series(dtype=object)
    real_okt = float(okt_r.get('Realisasi Finance', 0))
    cs_okt_total = float(db['okt_kpi'].get('total_donasi', 0))
    cs_okt_final = float(db['okt_kpi'].get('donasi_final', 0))
    selisih_real_cs_okt = real_okt - cs_okt_total
    target_okt = float(okt_r.get('Target Bulanan', 500000000))
    ads_okt = float(okt_r.get('Budget Iklan', 0))

    df_d_okt = db.get('okt_harian', pd.DataFrame())
    today_dt = datetime.date.today()
    hari_berjalan_kalender = today_dt.day if (today_dt.year == 2026 and today_dt.month == 10) else max(17, len(df_d_okt))
    hari_aktif_data = max(1, len(df_d_okt))
    laju_harian_real = real_okt / max(1, hari_berjalan_kalender)
    proyeksi_akhir_bulan_real = laju_harian_real * 31
    proyeksi_optimis_real = (real_okt / hari_aktif_data) * 31

    satpam_okt = hitung_satpam_keuangan(target_okt, real_okt, ads_okt, okt_r.get('Mushaf Terverifikasi', 0))
    tot_fin_ytd = df_macro['Realisasi Finance'].sum() if not df_macro.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_bento_kpi("ri-bank-line", "indigo", "Realisasi Finance (Okt)", rp_short(real_okt), f"{(real_okt/max(1,target_okt))*100:.1f}% Target", "indigo", f"YTD: {rp_short(tot_fin_ytd)}")
    with c2:
        render_bento_kpi("ri-user-voice-line", "emerald", "Laporan CS (Oktober)", rp_short(cs_okt_total), f"Bank {selisih_real_cs_okt:+,.0f}".replace(",", "."), "green", f"Final: {rp_short(cs_okt_final)}")
    with c3:
        render_bento_kpi("ri-line-chart-line", "orange", "Proyeksi Akhir Bulan", rp_short(proyeksi_akhir_bulan_real), f"{(proyeksi_akhir_bulan_real/max(1,target_okt))*100:.1f}% Target", "orange", f"Optimis: {rp_short(proyeksi_optimis_real)}")
    with c4:
        render_html(f"""
        <div class="hero-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:11.5px; font-weight:700; letter-spacing:0.6px; text-transform:uppercase;">SATPAM KEUANGAN (OKT)</span>
                <i class="ri-shield-star-line" style="font-size:18px;"></i>
            </div>
            <div class="metric-num" style="font-size:26px; font-weight:800; white-space:nowrap;">ROAS {satpam_okt['roas_aktual']:.2f}x</div>
            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.16); padding:6px 10px; border-radius:10px; font-size:11px; font-weight:600; gap:8px;">
                <span class="nowrap-val">DSD: {rp_short(satpam_okt['dsd'])}</span>
                <span class="nowrap-val">HPP: {rp(satpam_okt['plafon_hpp'])}</span>
            </div>
        </div>
        """)

    m_left, m_right = st.columns([1.75, 1.05])
    with m_left:
        render_chart_header("Komparasi Real Finance vs Dashboard CS & Proyeksi Akhir Bulan", f"Mutasi Bank Okt: {rp(real_okt)} • Input CS: {rp(cs_okt_total)} • Proyeksi 31 Okt: {rp(proyeksi_akhir_bulan_real)}", "Jan – Okt 2026", "indigo")
        fig_ov = go.Figure()
        if not df_macro.empty:
            fig_ov.add_trace(go.Scatter(x=df_macro['Bulan'], y=df_macro['Realisasi Finance'], name='Real Finance (Bank)', mode='lines+markers', line=dict(color='#6366F1', width=3, shape='spline'), fill='tozeroy', fillcolor='rgba(99, 102, 241, 0.1)'))
            fig_ov.add_trace(go.Scatter(x=df_macro['Bulan'], y=df_macro['Omset CS'], name='Input Dashboard CS', mode='lines+markers', line=dict(color='#10B981', width=2.6, shape='spline')))
            sep_real = float(df_macro[df_macro['Bulan'] == 'September']['Realisasi Finance'].iloc[0]) if 'September' in df_macro['Bulan'].values else 0
            fig_ov.add_trace(go.Scatter(x=['September', 'Oktober'], y=[sep_real, proyeksi_akhir_bulan_real], name='Proyeksi Akhir Bulan', mode='lines+markers', line=dict(color='#F59E0B', width=3, dash='dash')))
            fig_ov.add_trace(go.Scatter(x=df_macro['Bulan'], y=df_macro['Budget Iklan'], name='Biaya Iklan (Ads)', mode='lines+markers', line=dict(color='#FF6B4A', width=2, dash='dot', shape='spline')))
        apply_saas_plotly(fig_ov, height=340, is_currency=True)
        st.plotly_chart(fig_ov, use_container_width=True)

    with m_right:
        tot_leads_meta = float(db['okt_sumber']['Leads Meta'].sum()) if 'Leads Meta' in db['okt_sumber'].columns else 0
        pct_meta = (tot_leads_meta / cs_okt_total * 100) if cs_okt_total > 0 else 0
        if user_role == "Advertiser":
            bottom_box_html = f"""
            <div class="sub-box" style="border-radius:12px; padding:11px 14px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12px; font-weight:700;"><i class="ri-advertisement-line" style="color:#10B981 !important;"></i> Evaluasi Funnel Iklan</span>
                    <span class="badge-pill bp-green">Live Funnel</span>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px;">
                    <span style="color:var(--text-secondary) !important;">Biaya Iklan Oktober</span><span class="nowrap-val">{rp(ads_okt)}</span>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:12px;">
                    <span style="color:var(--text-secondary) !important;">Kontribusi Leads Meta</span><span class="nowrap-val" style="color:#10B981 !important;">{rp(tot_leads_meta)} ({pct_meta:.1f}%)</span>
                </div>
            </div>
            """
        else:
            bottom_box_html = f"""
            <div class="sub-box" style="border-radius:12px; padding:11px 14px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12px; font-weight:700;"><i class="ri-alarm-warning-line" style="color:#EF4444 !important;"></i> Audit Stok vs Jadwal Salur Okt</span>
                    <span class="badge-pill bp-red">Gap {sa['aw_gap_total_siap']} Pcs</span>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px;">
                    <span style="color:var(--text-secondary) !important;">Super Tajwid (Siap vs Jadwal)</span><span class="nowrap-val" style="color:#10B981 !important;">{sa['st_siap']} vs {sa['st_jadwal']} Pcs ({sa['st_gap_siap']:+d})</span>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:12px;">
                    <span style="color:var(--text-secondary) !important;">Al-Wakaf (Siap vs Jadwal)</span><span class="nowrap-val" style="color:#EF4444 !important;">{sa['aw_total_siap']} vs {sa['aw_jadwal']} Pcs ({sa['aw_gap_total_siap']:+d})</span>
                </div>
            </div>
            """

        render_html(f"""
        <div class="bento-card" style="min-height:392px; display:flex; flex-direction:column; justify-content:space-between;">
            <div>
                <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:12px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <div class="icon-box ib-indigo" style="width:32px; height:32px; font-size:15px;"><i class="ri-scales-3-line"></i></div>
                        <span style="font-family:'Outfit',sans-serif !important; font-weight:700; font-size:15px;">Rekonsiliasi Real vs CS & Proyeksi</span>
                    </div>
                    <span class="badge-pill bp-indigo">HARI KE-{hari_berjalan_kalender} OKT</span>
                </div>
                <div class="sub-box" style="border-radius:12px; padding:11px 14px; margin-bottom:10px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; font-size:12px; margin-bottom:5px;">
                        <span style="color:var(--text-secondary) !important;">1. Realisasi Mutasi Bank</span><span class="nowrap-val" style="color:#6366F1 !important;">{rp(real_okt)}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; font-size:12px; margin-bottom:5px;">
                        <span style="color:var(--text-secondary) !important;">2. Total Input Dashboard CS</span><span class="nowrap-val" style="color:#10B981 !important;">{rp(cs_okt_total)}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; font-size:12px; border-top:1px dashed var(--border-soft); padding-top:5px;">
                        <span style="color:var(--text-secondary) !important;">Selisih Bank vs CS</span><span class="nowrap-val" style="color:#F97316 !important;">{selisih_real_cs_okt:+,.0f}</span>
                    </div>
                </div>
                <div class="sub-box" style="border-radius:12px; padding:11px 14px; margin-bottom:10px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span style="font-size:12px; font-weight:700;"><i class="ri-compass-3-line" style="color:#F59E0B !important;"></i> Proyeksi Akhir Bulan (31 Okt)</span>
                        <span class="badge-pill bp-orange">{(proyeksi_akhir_bulan_real/max(1,target_okt))*100:.1f}% Target</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px;">
                        <span style="color:var(--text-secondary) !important;">Laju Real ({hari_berjalan_kalender} Hari Kalender)</span><span class="nowrap-val">{rp(laju_harian_real)} / hari</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px;">
                        <span style="color:var(--text-secondary) !important;">Proyeksi Kalender (31 Hari)</span><span class="nowrap-val" style="color:#F59E0B !important;">{rp(proyeksi_akhir_bulan_real)}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:12px;">
                        <span style="color:var(--text-secondary) !important;">Proyeksi Hari Aktif ({hari_aktif_data} Hari)</span><span class="nowrap-val" style="color:#10B981 !important;">{rp(proyeksi_optimis_real)}</span>
                    </div>
                </div>
            </div>
            {bottom_box_html}
        </div>
        """)

    b1, b2, b3 = st.columns(3)
    if user_role == "Advertiser":
        with b1:
            render_html(f"""
            <div class="bento-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12.5px; font-weight:700;">Total Omzet CS Aktif (Oktober)</span>
                    <span class="badge-pill bp-indigo">3 CS Ads Aktif</span>
                </div>
                <div class="metric-num" style="font-size:22px; font-weight:800; margin-bottom:8px;">{rp_short(cs_okt_total)}</div>
                <div style="display:flex; height:9px; border-radius:99px; overflow:hidden; gap:3px; margin-bottom:8px; background:var(--bg-subcard);">
                    <div style="width:61%; background:#FF6B4A; border-radius:99px;"></div><div style="width:30%; background:#4F46E5; border-radius:99px;"></div><div style="width:9%; background:#10B981; border-radius:99px;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:600; color:var(--text-secondary) !important;">
                    <span>Nisa</span><span>Salma</span><span>Aulia</span>
                </div>
            </div>
            """)
        with b2:
            render_html(f"""
            <div class="bento-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12.5px; font-weight:700;">Sumber Kontak Donasi (Oktober)</span>
                    <span class="badge-pill bp-green">Dominasi Meta Ads</span>
                </div>
                <div class="metric-num" style="font-size:22px; font-weight:800; margin-bottom:8px;">{rp_short(tot_leads_meta)} Meta Ads</div>
                <div style="display:flex; height:9px; border-radius:99px; overflow:hidden; gap:3px; margin-bottom:8px; background:var(--bg-subcard);">
                    <div style="width:83%; background:#10B981; border-radius:99px;"></div><div style="width:12%; background:#4F46E5; border-radius:99px;"></div><div style="width:5%; background:#F59E0B; border-radius:99px;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:600; color:var(--text-secondary) !important;">
                    <span>Leads Meta: <b>{pct_meta:.1f}%</b></span><span>Repeat Order CRM & Non-CRM</span>
                </div>
            </div>
            """)
        with b3:
            tot_cl_leads = int(db['leads_okt']['Closing'].sum()) if 'Closing' in db['leads_okt'].columns else 0
            tot_nom_leads = float(db['leads_okt']['Nominal'].sum()) if 'Nominal' in db['leads_okt'].columns else 0
            sq_cl = int(db['leads_okt']['SantriQu_Closing'].sum()) if 'SantriQu_Closing' in db['leads_okt'].columns else 0
            aq_cl = int(db['leads_okt']['AmalQu_Closing'].sum()) if 'AmalQu_Closing' in db['leads_okt'].columns else 0
            jq_cl = int(db['leads_okt']['JariyahQu_Closing'].sum()) if 'JariyahQu_Closing' in db['leads_okt'].columns else 0
            render_html(f"""
            <div class="bento-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12.5px; font-weight:700;">Konversi Kampanye Program (Okt)</span>
                    <span class="badge-pill bp-orange">{tot_cl_leads:,} Closing</span>
                </div>
                <div class="metric-num" style="font-size:22px; font-weight:800; margin-bottom:8px;">{rp_short(tot_nom_leads)}</div>
                <div style="display:flex; height:9px; border-radius:99px; overflow:hidden; gap:3px; margin-bottom:8px; background:var(--bg-subcard);">
                    <div style="width:74%; background:#4F46E5; border-radius:99px;"></div><div style="width:25%; background:#10B981; border-radius:99px;"></div><div style="width:1%; background:#F97316; border-radius:99px;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:600; color:var(--text-secondary) !important;">
                    <span>SantriQu: <b>{sq_cl}</b></span><span>AmalQu: <b>{aq_cl}</b></span><span>JariyahQu: <b>{jq_cl}</b></span>
                </div>
            </div>
            """)
    else:
        with b1:
            render_html(f"""
            <div class="bento-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12.5px; font-weight:700;">Mushaf Super Tajwid vs Jadwal Okt</span>
                    <span class="badge-pill bp-green">Surplus {sa['st_gap_siap']:+d} Pcs</span>
                </div>
                <div class="metric-num" style="font-size:22px; font-weight:800; margin-bottom:8px;">{sa['st_siap']:,} Pcs Siap Salur</div>
                <div style="display:flex; height:9px; border-radius:99px; overflow:hidden; gap:3px; margin-bottom:8px; background:var(--bg-subcard);">
                    <div style="width:82%; background:#10B981; border-radius:99px;"></div><div style="width:18%; background:#4F46E5; border-radius:99px;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:600; color:var(--text-secondary) !important;">
                    <span>Sudah Stiker: <b>{sa['st_siap']}</b></span><span>Jadwal Okt: <b>{sa['st_jadwal']}</b></span><span>Belum Stiker: <b>{sa['st_belum']}</b></span>
                </div>
            </div>
            """)
        with b2:
            render_html(f"""
            <div class="bento-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12.5px; font-weight:700;">Mushaf Al-Wakaf vs Jadwal Okt</span>
                    <span class="badge-pill bp-red">Gap {sa['aw_gap_total_siap']:+d} Pcs</span>
                </div>
                <div class="metric-num" style="font-size:22px; font-weight:800; margin-bottom:8px;">{sa['aw_total_siap']} Siap • {sa['aw_total_belum']:,} Belum</div>
                <div style="display:flex; height:9px; border-radius:99px; overflow:hidden; gap:3px; margin-bottom:8px; background:var(--bg-subcard);">
                    <div style="width:12%; background:#10B981; border-radius:99px;"></div><div style="width:18%; background:#F97316; border-radius:99px;"></div><div style="width:70%; background:#64748B; border-radius:99px;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:600; color:var(--text-secondary) !important;">
                    <span>Siap: <b>{sa['aw_total_siap']}</b> (Jadwal <b>{sa['aw_jadwal']}</b>)</span><span>Belum Stiker: <b>{sa['aw_belum_stiker']}</b></span><span>PO: <b>{sa['aw_belum_ambil']:,}</b></span>
                </div>
            </div>
            """)
        with b3:
            render_html(f"""
            <div class="bento-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12.5px; font-weight:700;">Buku Super Tahsin vs Target Okt</span>
                    <span class="badge-pill bp-green">Surplus {sa['bt_gap_siap']:+,d} Pcs</span>
                </div>
                <div class="metric-num" style="font-size:22px; font-weight:800; margin-bottom:8px;">{sa['bt_siap']:,} Siap • {sa['bt_belum']:,} Belum</div>
                <div style="display:flex; height:9px; border-radius:99px; overflow:hidden; gap:3px; margin-bottom:8px; background:var(--bg-subcard);">
                    <div style="width:48%; background:#10B981; border-radius:99px;"></div><div style="width:52%; background:#F59E0B; border-radius:99px;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:600; color:var(--text-secondary) !important;">
                    <span>Sudah Stiker: <b>{sa['bt_siap']:,}</b></span><span>Belum Stiker: <b>{sa['bt_belum']:,}</b></span><span>Sisa Target: <b>{sa['bt_jadwal']}</b></span>
                </div>
            </div>
            """)

# ==============================================================================
# HALAMAN 2: DONASI & SATPAM KEUANGAN
# ==============================================================================
elif menu_pilihan == "Donasi & Satpam Keuangan":
    f1_a, f1_b, f1_c = st.columns(3)
    with f1_a:
        cakupan_fin = st.selectbox("1. Pilih Cakupan Periode Analisis:", ["Bulan Oktober 2026 (Realtime)", "Filter Tanggal Harian (Oktober 2026)", "Pilih Bulan Historis (Januari – September)", "Akumulasi Tahunan (YTD Jan–Okt)"], key="fin_scope")

    df_d_okt = db.get('okt_harian', pd.DataFrame()).copy()
    if not df_d_okt.empty:
        df_d_okt['DT'] = pd.to_datetime(df_d_okt['Tanggal'], errors='coerce').dt.date
        df_d_okt = df_d_okt.dropna(subset=['DT'])
        max_dt_okt = df_d_okt['DT'].max() if not df_d_okt.empty else datetime.date.today()
    else:
        max_dt_okt = datetime.date.today()

    with f1_b:
        if cakupan_fin == "Pilih Bulan Historis (Januari – September)":
            bln_terpilih = st.selectbox("2. Pilih Bulan Historis:", [b for b in df_macro['Bulan'].tolist() if b != "Oktober"], key="fin_hist_m")
            cs_fin_filter = "Semua Tim CS"
            tgl_range_t1 = (datetime.date(2026, 10, 1), max_dt_okt)
        elif cakupan_fin == "Filter Tanggal Harian (Oktober 2026)":
            tgl_range_t1 = st.date_input("2. Pilih Rentang Tanggal Oktober:", value=(datetime.date(2026, 10, 1), max_dt_okt), min_value=datetime.date(2026, 10, 1), max_value=datetime.date(2026, 10, 31), key="fin_dt_range")
            bln_terpilih = "Oktober"
        else:
            bln_terpilih = "Oktober"
            tgl_range_t1 = (datetime.date(2026, 10, 1), max_dt_okt)
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
        rb = df_macro[df_macro['Bulan'] == bln_terpilih].iloc[0] if not df_macro.empty else pd.Series(dtype=object)
        t_omz, d_fin, d_cs, b_ads, m_pcs = float(rb.get('Target Bulanan',0)), float(rb.get('Realisasi Finance',0)), float(rb.get('Omset CS',0)), float(rb.get('Budget Iklan',0)), float(rb.get('Mushaf Terverifikasi',0))
        lbl_badge = f"{bln_terpilih} 2026"
    elif cakupan_fin == "Filter Tanggal Harian (Oktober 2026)":
        if isinstance(tgl_range_t1, (list, tuple)) and len(tgl_range_t1) == 2 and not df_d_okt.empty:
            df_d_okt = df_d_okt[(df_d_okt['DT'] >= tgl_range_t1[0]) & (df_d_okt['DT'] <= tgl_range_t1[1])]
        jml_hari = max(1, len(df_d_okt))
        if cs_fin_filter in ["Nisa", "Salma", "Aulia"]:
            d_cs = df_d_okt[cs_fin_filter].sum() if not df_d_okt.empty and cs_fin_filter in df_d_okt.columns else 0
            d_fin = d_cs
            tgt_cs_map = {"Nisa": 200000000, "Salma": 200000000, "Aulia": 50000000}
            t_omz = tgt_cs_map[cs_fin_filter] * (jml_hari / 30.0)
            base_ads = float(df_macro[df_macro['Bulan'] == 'Oktober']['Budget Iklan'].iloc[0]) if not df_macro.empty and 'Oktober' in df_macro['Bulan'].values else 114820000
            b_ads = (base_ads / 3.0) * (jml_hari / max(1, len(db.get('okt_harian', [1]))))
        else:
            d_cs = df_d_okt['Total Donasi'].sum() if not df_d_okt.empty and 'Total Donasi' in df_d_okt.columns else 0
            d_fin = df_d_okt['Donasi Final'].sum() if not df_d_okt.empty and 'Donasi Final' in df_d_okt.columns and df_d_okt['Donasi Final'].sum() > 0 else d_cs
            t_omz = 500000000 * (jml_hari / 30.0)
            base_ads = float(df_macro[df_macro['Bulan'] == 'Oktober']['Budget Iklan'].iloc[0]) if not df_macro.empty and 'Oktober' in df_macro['Bulan'].values else 114820000
            b_ads = base_ads * (jml_hari / max(1, len(db.get('okt_harian', [1]))))
        m_pcs = max(1, int(round(d_fin / 99000.0)))
        lbl_badge = f"{jml_hari} Hari Okt ({cs_fin_filter})"
    else:
        rb = df_macro[df_macro['Bulan'] == 'Oktober'].iloc[0] if not df_macro.empty and 'Oktober' in df_macro['Bulan'].values else pd.Series(dtype=object)
        if cs_fin_filter in ["Nisa", "Salma", "Aulia"]:
            row_cs_okt = db['okt_cs_table'][db['okt_cs_table']['CS / CRM'] == cs_fin_filter].iloc[0] if not db['okt_cs_table'].empty else pd.Series(dtype=object)
            t_omz = float(row_cs_okt.get('Target (Rp)', 0))
            d_cs = float(row_cs_okt.get('Bulanan (Total)', 0))
            d_fin = float(row_cs_okt.get('Bulanan (Final)', 0))
            base_ads = float(rb.get('Budget Iklan', 0))
            b_ads = base_ads * (d_cs / max(1.0, float(db['okt_kpi'].get('total_donasi', 1))))
            m_pcs = max(1, int(round(d_fin / 99000.0)))
            lbl_badge = f"Okt • CS {cs_fin_filter}"
        else:
            t_omz, d_fin, d_cs, b_ads, m_pcs = float(rb.get('Target Bulanan',0)), float(rb.get('Realisasi Finance',0)), float(rb.get('Omset CS',0)), float(rb.get('Budget Iklan',0)), float(rb.get('Mushaf Terverifikasi',0))
            lbl_badge = "Okt 2026"

    sk = hitung_satpam_keuangan(t_omz, d_fin, b_ads, m_pcs)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_bento_kpi("ri-bank-line", "indigo", f"Realisasi Finance ({lbl_badge})", rp_short(d_fin), f"{(d_fin/max(1,t_omz))*100:.1f}% Target", "green" if d_fin >= t_omz else "orange", f"Target: {rp_short(t_omz)}")
    with c2:
        render_bento_kpi("ri-user-voice-line", "emerald", "Funding Terlapor CS", rp_short(d_cs), f"Selisih: {rp_short(d_fin - d_cs)}", "indigo", "Bank vs Laporan CS")
    with c3:
        render_bento_kpi("ri-advertisement-line", "orange", "Biaya Iklan Terpakai", rp_short(b_ads), f"ROAS: {sk['roas_aktual']:.2f}x", sk['badge_type'], "Min: 1.52x | Aman: 2.63x")
    with c4:
        render_bento_kpi("ri-shield-check-line", "rose", "Dana Siap Salur (DSD)", rp_short(sk['dsd']), f"HPP: {rp(sk['plafon_hpp'])}", "green" if sk['plafon_hpp'] >= 20000 else "red", f"{sk['kebutuhan_mushaf_pcs']:,} Mushaf")

    g_left, g_right = st.columns([1.75, 1.05])
    with g_left:
        if "Oktober" in cakupan_fin:
            render_chart_header("Tren Harian Donasi Oktober 2026", "Grafik otomatis menyesuaikan rentang tanggal dan personel CS yang dipilih", lbl_badge, "orange")
            fig_f2 = go.Figure()
            if not df_d_okt.empty:
                if cs_fin_filter in ["Semua Tim CS", "Nisa"] and 'Nisa' in df_d_okt.columns:
                    fig_f2.add_trace(go.Scatter(x=df_d_okt['Tanggal'], y=df_d_okt['Nisa'], name='CS Nisa', mode='lines+markers', line=dict(color='#FF6B4A', width=2.8, shape='spline')))
                if cs_fin_filter in ["Semua Tim CS", "Salma"] and 'Salma' in df_d_okt.columns:
                    fig_f2.add_trace(go.Scatter(x=df_d_okt['Tanggal'], y=df_d_okt['Salma'], name='CS Salma', mode='lines+markers', line=dict(color='#6366F1', width=2.8, shape='spline')))
                if cs_fin_filter in ["Semua Tim CS", "Aulia"] and 'Aulia' in df_d_okt.columns:
                    fig_f2.add_trace(go.Scatter(x=df_d_okt['Tanggal'], y=df_d_okt['Aulia'], name='CS Aulia', mode='lines+markers', line=dict(color='#10B981', width=2.8, shape='spline')))
            apply_saas_plotly(fig_f2, height=330, is_currency=True)
            st.plotly_chart(fig_f2, use_container_width=True)
        else:
            render_chart_header("Komparasi Bulanan: Finance Real vs Funding CS vs Biaya Iklan", "Perbandingan performa keuangan bulanan sepanjang Januari – Oktober 2026", lbl_badge, "indigo")
            fig_f1 = go.Figure()
            if not df_macro.empty:
                fig_f1.add_trace(go.Bar(x=df_macro['Bulan'], y=df_macro['Realisasi Finance'], name='Realisasi Finance (Bank)', marker_color='#6366F1', marker_cornerradius=6))
                fig_f1.add_trace(go.Bar(x=df_macro['Bulan'], y=df_macro['Omset CS'], name='Funding CS', marker_color='#10B981', marker_cornerradius=6))
                fig_f1.add_trace(go.Bar(x=df_macro['Bulan'], y=df_macro['Budget Iklan'], name='Biaya Iklan', marker_color='#FF6B4A', marker_cornerradius=6))
            apply_saas_plotly(fig_f1, height=330, is_currency=True)
            fig_f1.update_layout(barmode='group')
            st.plotly_chart(fig_f1, use_container_width=True)

    with g_right:
        render_html(f"""
        <div class="bento-card" style="min-height:382px; display:flex; flex-direction:column; justify-content:space-between;">
            <div>
                <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:14px;">
                    <span style="font-family:'Outfit',sans-serif !important; font-weight:700; font-size:15.5px;">
                        <i class="ri-calculator-line" style="color:#6366F1 !important;"></i> Kalkulator Satpam Keuangan
                    </span>
                    <span class="badge-pill bp-{sk['badge_type']}">{lbl_badge}</span>
                </div>
                <div style="font-size:12.5px; color:var(--text-secondary) !important; line-height:2.2;">
                    <div style="display:flex; justify-content:space-between; border-bottom:1px dashed var(--border-soft);"><span>Profit Iklan (Donasi - Ads)</span><span class="nowrap-val" style="color:var(--text-primary) !important;">{rp(sk['profit_iklan'])}</span></div>
                    <div style="display:flex; justify-content:space-between; border-bottom:1px dashed var(--border-soft);"><span>Beban Operasional (10%)</span><span class="nowrap-val" style="color:var(--text-primary) !important;">{rp(sk['beban_ops_10'])}</span></div>
                    <div style="display:flex; justify-content:space-between; border-bottom:1px dashed var(--border-soft);"><span>Dana Siap Salur (DSD)</span><span class="nowrap-val" style="color:#6366F1 !important;">{rp(sk['dsd'])}</span></div>
                    <div style="display:flex; justify-content:space-between; border-bottom:1px dashed var(--border-soft);"><span>Alokasi Mushaf (65% DSD)</span><span class="nowrap-val" style="color:#10B981 !important;">{rp(sk['alokasi_mushaf_65'])}</span></div>
                    <div style="display:flex; justify-content:space-between; border-bottom:1px dashed var(--border-soft);"><span>Cadangan Cashback (35%)</span><span class="nowrap-val" style="color:#F59E0B !important;">{rp(sk['cadangan_cashback_35'])}</span></div>
                    <div style="display:flex; justify-content:space-between;"><span>Target Subsidi CRM CS</span><span class="nowrap-val" style="color:#EF4444 !important;">{rp(sk['target_crm_cs'])}</span></div>
                </div>
            </div>
            <div class="sub-box" style="margin-top:12px; padding:10px 12px; border-radius:10px; font-size:12px;">
                <i class="ri-award-line" style="color:#F97316 !important;"></i> <b>Keputusan Sistem:</b> {sk['rekom_tier']}
            </div>
        </div>
        """)

    opsi_tabel_t1 = ["1. Rekapitulasi Bulanan (Jan–Okt)", "2. Rincian Kinerja CS Oktober", "3. Distribusi Sumber Kontak (Oktober)", "4. Tabel Harian Oktober"]
    if user_role != "Advertiser":
        opsi_tabel_t1.append("5. Pencarian Riwayat Donatur (Mini CRM)")

    sub_t1 = st.radio("Pilih Tabel Detail Keuangan:", opsi_tabel_t1, horizontal=True, key="t1_subtable")

    if sub_t1.startswith("1."):
        df_show = df_macro.copy()
        if user_role == "Advertiser" and "Mushaf Terverifikasi" in df_show.columns:
            df_show.drop(columns=["Mushaf Terverifikasi"], inplace=True)
        for cr in ['Target Bulanan', 'Realisasi Finance', 'Omset CS', 'Selisih Target', 'Selisih Finance vs CS', 'Budget Iklan', 'Total Pengeluaran', 'Laba Bersih']:
            if cr in df_show.columns: df_show[cr] = df_show[cr].apply(rp)
        if '% Capaian' in df_show.columns: df_show['% Capaian'] = df_show['% Capaian'].apply(lambda x: f"{x:.1f}%")
        if 'ROFI' in df_show.columns: df_show['ROFI'] = df_show['ROFI'].apply(lambda x: f"{x:.2f}x")
        render_saas_table(df_show)
    elif sub_t1.startswith("2."):
        df_ok = db['okt_cs_table'].copy()
        if cs_fin_filter != "Semua Tim CS" and 'CS / CRM' in df_ok.columns:
            df_ok = df_ok[df_ok['CS / CRM'] == cs_fin_filter]
        for cr in ['Harian (Total)', 'Harian (Final)', 'Mingguan (Total)', 'Mingguan (Final)', 'Bulanan (Total)', 'Bulanan (Final)', 'Target (Rp)']:
            if cr in df_ok.columns: df_ok[cr] = df_ok[cr].apply(rp)
        render_saas_table(df_ok)
    elif sub_t1.startswith("3."):
        df_sr = db['okt_sumber'].copy()
        if cs_fin_filter != "Semua Tim CS" and 'CS / CRM' in df_sr.columns:
            df_sr = df_sr[df_sr['CS / CRM'] == cs_fin_filter]
        for cr in ['Leads Meta', 'Repeat Order CRM', 'Repeat Order non CRM', 'Lainnya', 'Total Nominal']:
            if cr in df_sr.columns: df_sr[cr] = df_sr[cr].apply(rp)
        render_saas_table(df_sr)
    elif sub_t1.startswith("4."):
        df_h_disp = df_d_okt.drop(columns=['DT']).copy() if not df_d_okt.empty else pd.DataFrame()
        for cr in ['Salma', 'Aulia', 'Nisa', 'Total Donasi', 'Donasi Final']:
            if cr in df_h_disp.columns: df_h_disp[cr] = df_h_disp[cr].apply(rp)
        render_saas_table(df_h_disp)
    else:
        q_d = st.text_input("Ketik Nama Donatur atau Nomor WhatsApp:", placeholder="Contoh: Donatur Prioritas, 628...")
        if q_d:
            dfc = db['contacts_df']
            if not dfc.empty:
                m_d = dfc['Nama Donatur'].astype(str).str.contains(q_d, case=False, na=False) | dfc['Nomor Whatsapp'].astype(str).str.contains(q_d, case=False, na=False)
                render_saas_table(dfc[m_d], max_rows=30)
            else:
                render_saas_table(dfc)

# ==============================================================================
# HALAMAN 3: PERFORMA CS & LEADS
# ==============================================================================
elif menu_pilihan == "Performa CS & Leads":
    mode_evaluasi_cs = st.radio("Pilih Mode Evaluasi Kinerja CS:", ["1. Monitoring Leads Harian Oktober 2026", "2. Rapor & Rekap Omzet Bulanan Seluruh CS (Januari – Oktober 2026)"], horizontal=True, key="cs_eval_mode")

    if mode_evaluasi_cs.startswith("1."):
        df_l = db['leads_okt'].copy()
        if not df_l.empty:
            df_l['DT'] = pd.to_datetime(df_l['Tanggal'], errors='coerce').dt.date
            df_l = df_l.dropna(subset=['DT'])
            max_dt_l = df_l['DT'].max() if not df_l.empty else datetime.date.today()
        else:
            max_dt_l = datetime.date.today()

        f2_1, f2_2, f2_3 = st.columns(3)
        with f2_1:
            pilih_cs = st.selectbox("1. Pilih CS Aktif Oktober:", ["Semua CS Aktif (Nisa, Salma, Aulia)", "Nisa", "Salma", "Aulia"], key="t2_c_okt")
        with f2_2:
            pilih_prog = st.selectbox("2. Filter Program Kampanye:", ["Semua Program", "SantriQu", "AmalQu", "JariyahQu"], key="t2_prog_okt")
        with f2_3:
            tgl_l = st.date_input("3. Rentang Tanggal Leads Oktober:", value=(datetime.date(2026, 10, 1), max_dt_l), min_value=datetime.date(2026, 10, 1), max_value=datetime.date(2026, 10, 31), key="t2_d_okt")

        if not df_l.empty:
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

        tv = int(df_l['Leads_Aktif'].sum()) if not df_l.empty and 'Leads_Aktif' in df_l.columns else 0
        ti = int(df_l['Chat Invalid'].sum()) if not df_l.empty and 'Chat Invalid' in df_l.columns else 0
        tc = int(df_l['Closing_Aktif'].sum()) if not df_l.empty and 'Closing_Aktif' in df_l.columns else 0
        tn = float(df_l['Nominal_Aktif'].sum()) if not df_l.empty and 'Nominal_Aktif' in df_l.columns else 0
        cr_okt = (tc / tv * 100) if tv > 0 else 0.0
        tot_fu = int(df_l['Total Follow Up'].sum()) if not df_l.empty and 'Total Follow Up' in df_l.columns else 0

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_bento_kpi("ri-chat-check-line", "indigo", f"Leads Valid ({pilih_prog})", f"{tv:,} Leads", f"Invalid: {ti:,}", "indigo", pilih_cs)
        with c2:
            render_bento_kpi("ri-check-double-line", "emerald", f"Total Closing ({pilih_prog})", f"{tc:,} Closing", f"Conv. Rate: {cr_okt:.1f}%", "green", "Oktober 2026")
        with c3:
            render_bento_kpi("ri-money-dollar-circle-line", "orange", f"Nominal Closing ({pilih_prog})", rp_short(tn), f"AOV: {rp(tn/tc if tc>0 else 0)}", "orange", "Terverifikasi")
        with c4:
            render_bento_kpi("ri-customer-service-2-line", "emerald", "Total Follow-Up Tercatat", f"{tot_fu:,} Kontak", "3 CS Ads + 1 CRM Aktif", "green", "Oktober 2026")

        cl_l, cl_r = st.columns([1.8, 1])
        with cl_l:
            render_chart_header(f"Tren Harian Perolehan Leads Oktober — {pilih_prog}", f"Menampilkan perolehan harian untuk: {pilih_cs}", pilih_prog, "orange")
            fig_cs = go.Figure()
            if not df_l.empty:
                df_lg = df_l.groupby(['Tanggal', 'Nama CS'], as_index=False).agg({'Nominal_Aktif': 'sum', 'Closing_Aktif': 'sum'})
                fig_cs = px.bar(df_lg, x='Tanggal', y='Nominal_Aktif', color='Nama CS', barmode='group', color_discrete_sequence=['#FF6B4A', '#6366F1', '#10B981'])
            apply_saas_plotly(fig_cs, height=275, is_currency=True)
            st.plotly_chart(fig_cs, use_container_width=True)

        with cl_r:
            render_chart_header("Conversion Rate Leads", f"Rasio Closing {pilih_prog}", f"{cr_okt:.1f}%", "green")
            fig_g_cs = make_gauge_chart(round(cr_okt, 1), max_val=100, suffix="%", bar_color="#10B981")
            st.plotly_chart(fig_g_cs, use_container_width=True)

        render_html('<div style="font-family:\'Outfit\',sans-serif !important; font-size:15.5px; font-weight:700; margin:6px 0;"><i class="ri-table-2" style="color:#FF6B4A !important;"></i> Tabel Harian Pengelolaan Leads Oktober</div>')
        if not df_l.empty:
            df_l_show = df_l[["Tanggal", "Nama CS", "Leads_Aktif", "Chat Invalid", "Closing_Aktif", "Nominal_Aktif", "SantriQu_Closing", "AmalQu_Closing", "JariyahQu_Closing", "Total Follow Up"]].copy()
            df_l_show.rename(columns={"Leads_Aktif": f"Leads ({pilih_prog})", "Closing_Aktif": f"Closing ({pilih_prog})", "Nominal_Aktif": f"Nominal ({pilih_prog})"}, inplace=True)
            df_l_show[f"Nominal ({pilih_prog})"] = df_l_show[f"Nominal ({pilih_prog})"].apply(rp)
            render_saas_table(df_l_show)
        else:
            render_saas_table(pd.DataFrame())

    else:
        r1, r2 = st.columns(2)
        with r1:
            filter_stat_ov = st.selectbox("1. Filter Status Keaktifan CS:", ["Semua Tim CS (8 Orang)", "Hanya CS Aktif Oktober (Nisa, Salma, Aulia, Olive)", "Hanya CS Non-Aktif (Desi, Syafiq, Rida, Sarah)"], key="ov_stat")
        df_ov = db['cs_overview'].copy()
        if "Hanya CS Aktif" in filter_stat_ov and 'Status Okt' in df_ov.columns:
            df_ov = df_ov[df_ov['Status Okt'].str.contains("Aktif")]
        elif "Non-Aktif" in filter_stat_ov and 'Status Okt' in df_ov.columns:
            df_ov = df_ov[df_ov['Status Okt'] == "Non-Aktif"]

        with r2:
            pilih_cs_rapor = st.selectbox("2. Pilih Personel CS:", ["Semua (Tampilkan Perbandingan)"] + df_ov['Nama CS'].tolist() if not df_ov.empty else ["Semua (Tampilkan Perbandingan)"], key="ov_person")

        if pilih_cs_rapor != "Semua (Tampilkan Perbandingan)":
            df_ov_view = df_ov[df_ov['Nama CS'] == pilih_cs_rapor].copy()
        else:
            df_ov_view = df_ov.copy()

        tot_omset_jan_sep = df_ov_view['Total Omset (Jan-Sep)'].sum() if not df_ov_view.empty and 'Total Omset (Jan-Sep)' in df_ov_view.columns else 0
        tot_omset_okt = df_ov_view['Oktober'].sum() if not df_ov_view.empty and 'Oktober' in df_ov_view.columns else 0
        tot_closing_all = int(df_ov_view['Total Closing'].sum()) if not df_ov_view.empty and 'Total Closing' in df_ov_view.columns else 0
        avg_aov = int(df_ov_view['AOV'].mean()) if not df_ov_view.empty and 'AOV' in df_ov_view.columns else 0

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            render_bento_kpi("ri-wallet-3-line", "indigo", "Total Omset (Jan–Sep)", rp_short(tot_omset_jan_sep), f"{len(df_ov_view)} Personel CS", "indigo", pilih_cs_rapor)
        with k2:
            render_bento_kpi("ri-flashlight-line", "orange", "Omset Oktober (Realtime)", rp_short(tot_omset_okt), "Aktif" if tot_omset_okt > 0 else "Non-Aktif", "green" if tot_omset_okt > 0 else "red", "Oktober 2026")
        with k3:
            render_bento_kpi("ri-shopping-bag-3-line", "emerald", "Total Transaksi Closing", f"{tot_closing_all:,} Transaksi", "Akumulasi YTD", "green", "Jan–Sep 2026")
        with k4:
            render_bento_kpi("ri-price-tag-3-line", "indigo", "Rata-rata Donasi (AOV)", rp(avg_aov), "Per Closing", "indigo", "Rata-rata CS")

        months_cols = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober"]
        render_chart_header("Tren Pendapatan Bulanan CS (Januari – Oktober 2026)", "Perbandingan perolehan omzet bulanan masing-masing CS", "Jan–Okt 2026", "indigo")
        fig_ov_cs = go.Figure()
        if not df_ov_view.empty:
            palette = ['#FF6B4A', '#6366F1', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#06B6D4', '#64748B']
            for idx_c, (_, r_cs) in enumerate(df_ov_view.iterrows()):
                y_vals = [float(r_cs.get(m, 0)) for m in months_cols]
                fig_ov_cs.add_trace(go.Bar(x=months_cols, y=y_vals, name=r_cs.get('Nama CS','-'), marker_color=palette[idx_c % len(palette)], marker_cornerradius=5))
        apply_saas_plotly(fig_ov_cs, height=320, is_currency=True)
        fig_ov_cs.update_layout(barmode='group')
        st.plotly_chart(fig_ov_cs, use_container_width=True)

        df_ov_disp = df_ov_view.copy()
        for cr in ["Target Omset", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "Total Omset (Jan-Sep)", "AOV"]:
            if cr in df_ov_disp.columns: df_ov_disp[cr] = df_ov_disp[cr].apply(rp)
        render_saas_table(df_ov_disp)

# ==============================================================================
# HALAMAN 4: LOGISTIK & GUDANG
# ==============================================================================
elif menu_pilihan == "Logistik & Gudang":
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_bento_kpi("ri-book-mark-line", "emerald", "Mushaf Super Tajwid", f"{sa['st_siap']:,} Siap Salur", f"Jadwal: {sa['st_jadwal']} ({sa['st_gap_siap']:+d})", "green", f"Belum Stiker: {sa['st_belum']} Pcs")
    with c2:
        render_bento_kpi("ri-book-2-line", "rose", "Mushaf Al-Wakaf", f"{sa['aw_total_siap']:,} Siap Salur", f"Jadwal: {sa['aw_jadwal']} ({sa['aw_gap_total_siap']:+d} Pcs)", "red" if sa['aw_gap_total_siap'] < 0 else "green", f"Belum Stiker: {sa['aw_belum_stiker']} • PO: {sa['aw_belum_ambil']:,}")
    with c3:
        render_bento_kpi("ri-book-open-line", "indigo", "Buku Super Tahsin", f"{sa['bt_siap']:,} Siap Salur".replace(",", "."), f"Target: {sa['bt_jadwal']} ({sa['bt_gap_siap']:+,d})", "green", f"Belum Stiker: {sa['bt_belum']:,} Pcs".replace(",", "."))
    with c4:
        render_bento_kpi("ri-archive-line", "orange", "Total Mushaf vs Tahsin", f"{sa['mushaf_fisik_total']:,} Mushaf".replace(",", "."), f"Siap: {sa['mushaf_siap_total']:,} • Belum: {sa['mushaf_belum_total']:,}", "orange", f"Total Tahsin: {sa['bt_total']:,} Pcs".replace(",", "."))

    render_html(f"""
    <div class="bento-card" style="border-left: 4px solid #F97316;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;">
            <span style="font-family:'Outfit',sans-serif !important; font-size:15.5px; font-weight:800;">
                <i class="ri-shield-check-fill" style="color:#F97316 !important;"></i> Audit Kesiapan Stok (Sudah Stiker vs Belum Stiker) terhadap Jadwal Distribusi Oktober 2026
            </span>
            <span class="badge-pill bp-red"><i class="ri-alert-line"></i> Action Required: Al-Wakaf</span>
        </div>
        <div style="font-size:12.5px; color:var(--text-secondary) !important; line-height:1.65;">
            1. <b>Mushaf Super Tajwid:</b> Stok Siap Salur (Sudah Stiker) tersedia <b>{sa['st_siap']} Pcs</b> vs kebutuhan <i>Kalender Distribusi Oktober</i> <b>{sa['st_jadwal']} Pcs</b> &rarr; <b style="color:#10B981 !important;">AMAN / CUKUP (Surplus {sa['st_gap_siap']:+d} Pcs siap salur)</b>.<br>
            2. <b>Mushaf Al-Wakaf:</b> Kebutuhan <i>Kalender Distribusi Oktober</i> adalah <b>{sa['aw_jadwal']} Pcs</b>, sedangkan stok Siap Salur TikTok hanya <b>{sa['aw_tik_siap']} Pcs</b> dan gabungan dengan Meta Ads (<b>{sa['aw_meta_siap']} Pcs</b>) baru mencapai <b>{sa['aw_total_siap']} Pcs</b> &rarr; <b style="color:#EF4444 !important;">SELISIH {sa['aw_gap_total_siap']:+d} PCS SIAP SALUR!</b> Segera tempel stiker dari <b>{sa['aw_belum_stiker']} Pcs</b> stok <i>Belum Tempel Stiker</i> di Ruang AmalQu.<br>
            3. <b>Buku Belajar Super Tahsin:</b> Stok Siap Salur tersedia <b>{sa['bt_siap']:,} Pcs</b> (ditambah <b>{sa['bt_belum']:,} Pcs</b> belum stiker) vs sisa target distribusi <b>{sa['bt_jadwal']} Pcs</b> &rarr; <b style="color:#10B981 !important;">AMAN / SURPLUS {sa['bt_gap_siap']:+,d} PCS</b>.
        </div>
    </div>
    """)

    lg_l, lg_r = st.columns([1.55, 1.25])
    with lg_l:
        render_chart_header("Komparasi Stok Siap Salur vs Belum Stiker vs Jadwal Oktober", "Memisahkan Mushaf Super Tajwid, Mushaf Al-Wakaf, dan Buku Super Tahsin", "Audit Gudang vs Jadwal", "indigo")
        df_comp_stok = pd.DataFrame([
            {"Produk": "Mushaf Super Tajwid", "Siap Salur (Sudah Stiker)": sa['st_siap'], "Belum Siap (Belum Stiker/PO)": sa['st_belum'], "Jadwal Distribusi Okt": sa['st_jadwal']},
            {"Produk": "Mushaf Al-Wakaf",     "Siap Salur (Sudah Stiker)": sa['aw_total_siap'], "Belum Siap (Belum Stiker/PO)": sa['aw_total_belum'], "Jadwal Distribusi Okt": sa['aw_jadwal']},
            {"Produk": "Buku Super Tahsin",   "Siap Salur (Sudah Stiker)": sa['bt_siap'], "Belum Siap (Belum Stiker/PO)": sa['bt_belum'], "Jadwal Distribusi Okt": sa['bt_jadwal']},
        ])
        fig_comp_s = go.Figure()
        fig_comp_s.add_trace(go.Bar(x=df_comp_stok['Produk'], y=df_comp_stok['Siap Salur (Sudah Stiker)'], name='Siap Salur (Sudah Stiker)', marker_color='#10B981', marker_cornerradius=6, text=df_comp_stok['Siap Salur (Sudah Stiker)'], textposition='auto'))
        fig_comp_s.add_trace(go.Bar(x=df_comp_stok['Produk'], y=df_comp_stok['Jadwal Distribusi Okt'], name='Kebutuhan Jadwal Okt', marker_color='#6366F1', marker_cornerradius=6, text=df_comp_stok['Jadwal Distribusi Okt'], textposition='auto'))
        fig_comp_s.add_trace(go.Bar(x=df_comp_stok['Produk'], y=df_comp_stok['Belum Siap (Belum Stiker/PO)'], name='Belum Siap (Belum Stiker/PO)', marker_color='#F97316', marker_cornerradius=6, text=df_comp_stok['Belum Siap (Belum Stiker/PO)'], textposition='auto'))
        apply_saas_plotly(fig_comp_s, height=320)
        fig_comp_s.update_layout(barmode='group')
        st.plotly_chart(fig_comp_s, use_container_width=True)

    with lg_r:
        render_chart_header("Progres Master Packing Dus (Jan – Okt 2026)", "Tahap verifikasi, stiker, packing hingga selesai distribusi", "25.824 Mushaf", "emerald")
        df_pk = db['packing_dus_bulanan']
        fig_pk = go.Figure()
        if not df_pk.empty:
            fig_pk.add_trace(go.Bar(x=df_pk['Bulan'], y=df_pk['Distribusi Selesai'], name='Selesai', marker_color='#10B981', marker_cornerradius=4))
            fig_pk.add_trace(go.Bar(x=df_pk['Bulan'], y=df_pk['Packing / Proses Distribusi'], name='Proses/Packing', marker_color='#6366F1', marker_cornerradius=4))
            fig_pk.add_trace(go.Bar(x=df_pk['Bulan'], y=df_pk['Penamaan Mushaf (Stiker)'], name='Stiker', marker_color='#FF6B4A', marker_cornerradius=4))
            fig_pk.add_trace(go.Bar(x=df_pk['Bulan'], y=df_pk['Verifikasi (Belum Stiker)'], name='Verifikasi', marker_color='#94A3B8', marker_cornerradius=4))
        apply_saas_plotly(fig_pk, height=320)
        fig_pk.update_layout(barmode='stack')
        st.plotly_chart(fig_pk, use_container_width=True)

    sub_t3 = st.radio("Pilih Tabel Inventaris & Logistik:", ["1. Tabel Audit Stok (Siap Salur vs Belum Stiker) vs Jadwal Distribusi", "2. Master Stok Real-Time (Per SKU, Status Stiker & Lokasi)", "3. Rekapitulasi Master Packing Dus Bulanan (Jan–Okt)", "4. Log Mutasi Masuk & Distribusi Keluar"], horizontal=True, key="t3_sub")
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
    tot_mushaf_kal = int(df_kal['Jumlah Mushaf (Pcs)'].sum()) if not df_kal.empty and 'Jumlah Mushaf (Pcs)' in df_kal.columns else 0

    kc1, kc2, kc3, kc4 = st.columns(4)
    with kc1:
        render_bento_kpi("ri-calendar-check-line", "indigo", "Total Agenda Oktober", f"{tot_agenda_kal} Titik Lokasi", f"Total: {tot_mushaf_kal:,} Mushaf", "indigo", "Oktober 2026")
    with kc2:
        render_bento_kpi("ri-book-mark-line", "emerald", "Jadwal Super Tajwid", f"{sa['st_jadwal']} Mushaf", f"Siap: {sa['st_siap']} Pcs (Cukup)", "green", f"Surplus {sa['st_gap_siap']:+d} Pcs")
    with kc3:
        render_bento_kpi("ri-book-2-line", "rose", "Jadwal Al-Wakaf TikTok", f"{sa['aw_jadwal']} Mushaf", f"Siap: {sa['aw_total_siap']} ({sa['aw_gap_total_siap']:+d})", "red" if sa['aw_gap_total_siap'] < 0 else "green", f"TikTok: {sa['aw_tik_siap']} • Meta: {sa['aw_meta_siap']}")
    with kc4:
        render_bento_kpi("ri-price-tag-2-line", "orange", "Cadangan Belum Stiker", f"{sa['aw_belum_stiker']} Mushaf", "Ruang AmalQu (10 Box)", "orange", "Siap Ditempel Stiker")

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
                f'<div>{items_html}</div></div>'
            )
        else:
            cells_list.append(f'<div class="cal-cell"><div class="cal-day-num"><span>{day_num} Okt</span></div><div style="font-size:10px; color:var(--text-muted) !important;">-</div></div>')
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
        mobile_cards += f'<div class="cal-cell-active" style="margin-bottom:10px;"><div class="cal-day-num"><span>{day_num} Oktober 2026</span><span class="badge-pill bp-orange">{len(ev_list)} Titik • {tot_pcs_day} Pcs</span></div><div>{items_html}</div></div>'

    render_html(f"""
    <div class="bento-card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <div>
                <span style="font-family:'Outfit',sans-serif !important; font-weight:800; font-size:16.5px;"><i class="ri-calendar-todo-fill" style="color:#FF6B4A !important;"></i> Kalender Visual Distribusi Mushaf — Oktober 2026</span>
                <div style="font-size:12px; color:var(--text-secondary) !important;">Super Tajwid: <b>{sa['st_jadwal']} Pcs</b> (Stok Siap {sa['st_siap']} Pcs) &nbsp;|&nbsp; Al-Wakaf: <b>{sa['aw_jadwal']} Pcs</b> (Stok Siap {sa['aw_total_siap']} Pcs)</div>
            </div>
            <span class="badge-pill bp-orange"><i class="ri-map-pin-time-line"></i> {tot_agenda_kal} Titik Distribusi Aktif</span>
        </div>
        <div class="cal-desktop-only">
            <div class="cal-grid-7">
                <div class="cal-head-cell">SENIN</div><div class="cal-head-cell">SELASA</div><div class="cal-head-cell">RABU</div><div class="cal-head-cell">KAMIS</div><div class="cal-head-cell">JUMAT</div><div class="cal-head-cell">SABTU</div><div class="cal-head-cell">MINGGU</div>
                {desktop_cal_str}
            </div>
        </div>
        <div class="cal-mobile-only" style="margin-top:12px;">{mobile_cards}</div>
    </div>
    """)

    f_kal_1, f_kal_2 = st.columns([2.5, 1])
    with f_kal_1:
        render_html('<div style="font-family:\'Outfit\',sans-serif !important; font-size:15.5px; font-weight:700; padding-top:8px;"><i class="ri-table-line" style="color:#6366F1 !important;"></i> Rincian Agenda Distribusi Scheduled (Sheet Kalender Oktober 2026 • Kolom A–J)</div>')
    with f_kal_2:
        pilih_var_kal = st.selectbox("Filter Variasi Mushaf:", ["Semua Variasi", "Super Tajwid", "Al Wakaf Tiktok"], key="kal_var")

    df_kal_disp = df_kal.copy()
    if pilih_var_kal != "Semua Variasi" and not df_kal_disp.empty and "Variasi Mushaf" in df_kal_disp.columns:
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
        render_bento_kpi("ri-user-follow-line", "emerald", "Donatur Terkonfirmasi", f"{dk['total_donatur']:,}".replace(",", "."), f"Konversi {dk['konversi_pct']}%", "green", f"Kontak: {dk['total_kontak']:,}")
    with d2:
        render_bento_kpi("ri-user-add-line", "orange", "Leads Belum Donasi", f"{dk['total_leads']:,}".replace(",", "."), "Prospek Follow-Up", "orange", "Siap Reaktivasi")
    with d3:
        render_bento_kpi("ri-vip-diamond-line", "indigo", "Total Donasi Kumulatif", rp_short(dk['total_donasi_kumulatif']), f"LTV: {rp(dk['rata_rata_donasi'])}", "indigo", "Rata-rata / Donatur")
    with d4:
        render_bento_kpi("ri-notification-badge-line", "rose", "Status Callback Segera", "12.285 Kontak", "84,94% Database", "red", "Prioritas Broadcast")

    render_html("""
    <div class="bento-card" style="margin-bottom:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <div>
                <span style="font-family:'Outfit',sans-serif !important; font-size:16px; font-weight:800;"><i class="ri-send-plane-fill" style="color:#FF6B4A !important;"></i> Smart Broadcast (BC) Engine — Generator CSV 2 Kolom (Senin & Jumat)</span>
                <div style="font-size:12px; color:var(--text-secondary) !important; margin-top:2px;">Pilih jadwal kampanye BC Anda. Sistem menyaring database otomatis menjadi file CSV 2 kolom (<b>phone number</b>, <b>nama</b>) siap pakai.</div>
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
        if not df_tgt.empty:
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

        st.download_button(label="Download CSV 2 Kolom (WA Blast)", data=df_out.to_csv(index=False).encode('utf-8'), file_name=f"WA_Blast_AmalQu_{datetime.date.today().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)

    sub_t5 = st.radio("Lihat Tabel Komposisi Segmentasi CRM (SETTING DASHBOARD Baris 2–33):", ["Segmentasi Prioritas Donatur (A1 – Reguler)", "Status Reminder & Status Retensi Donatur"], horizontal=True, key="t5_sub")
    if sub_t5 == "Segmentasi Prioritas Donatur (A1 – Reguler)":
        render_saas_table(db['db_segmentasi'])
    else:
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            render_saas_table(db['db_reminder'])
        with col_r2:
            render_saas_table(db['db_status_donatur'])
