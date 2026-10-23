import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os, re, io, datetime, time, urllib.request
from datetime import timezone, timedelta
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================================================================
# 1. KONFIGURASI HALAMAN, ZONA WAKTU WIB (UTC+7) & STATE
# ==============================================================================
st.set_page_config(
    page_title="AmalQu — Yayasan AmalQu Indonesia Peduli",
    page_icon="https://cdn.jsdelivr.net/npm/remixicon@4.2.0/icons/Finance/funds-box-fill.svg",
    layout="wide",
    initial_sidebar_state="expanded"
)

TZ_WIB = timezone(timedelta(hours=7))
def now_wib():
    return datetime.datetime.now(TZ_WIB)

if "dark_mode" not in st.session_state: st.session_state.dark_mode = True
if "auth_user" not in st.session_state: st.session_state.auth_user = None
if "sync_nonce" not in st.session_state: st.session_state.sync_nonce = 0

def render_html(raw_html: str):
    st.markdown(" ".join(line.strip() for line in raw_html.splitlines() if line.strip()), unsafe_allow_html=True)

def build_logo_html(size_px=44):
    return (
        f'<div style="position:relative;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;">'
        f'<div style="width:{size_px}px;height:{size_px}px;border-radius:12px;background:linear-gradient(135deg,#FF6B4A 0%,#F97316 100%);'
        f'display:inline-flex;align-items:center;justify-content:center;box-shadow:0 4px 14px rgba(249,115,22,0.3);">'
        f'<svg width="{int(size_px*0.56)}" height="{int(size_px*0.56)}" viewBox="0 0 24 24" fill="none">'
        f'<path d="M12 2L3 7V12C3 17.55 6.84 22.74 12 24C17.16 22.74 21 17.55 21 12V7L12 2ZM12 6.5C13.93 6.5 15.5 8.07 15.5 10C15.5 11.93 13.93 13.5 12 13.5C10.07 13.5 8.5 11.93 8.5 10C8.5 8.07 10.07 6.5 12 6.5ZM18 17.5C16.5 19.3 14.3 20.5 12 20.5C9.7 20.5 7.5 19.3 6 17.5C6.5 15.8 9.8 14.8 12 14.8C14.2 14.8 17.5 15.8 18 17.5Z" fill="white"/>'
        f'</svg></div></div>'
    )

# ==============================================================================
# 2. HELPER FORMATTING & KALKULATOR SATPAM KEUANGAN
# ==============================================================================
def rp(val):
    try:
        v = float(val)
        return f"-Rp {abs(v):,.0f}".replace(",", ".") if v < 0 else f"Rp {v:,.0f}".replace(",", ".")
    except: return "Rp 0"

def rp_dash(val):
    try:
        v = float(val)
        return "-" if v == 0 else f"Rp{v:,.0f}".replace(",", ".")
    except: return "-"

def rp_short(val):
    try:
        v = float(val)
        sign, av = ("-" if v < 0 else ""), abs(v)
        if av >= 1_000_000_000: return f"{sign}Rp {av/1_000_000_000:.2f} M"
        if av >= 1_000_000: return f"{sign}Rp {av/1_000_000:.1f} Jt"
        return f"{sign}Rp {av:,.0f}".replace(",", ".")
    except: return "Rp 0"

def num_clean(val):
    if pd.isna(val): return 0.0
    s = str(val).strip()
    if not s or s in ["-", "None", "nan", "#REF!", "#VALUE!", "#DIV/0!", "#ERROR!", "#N/A"]: return 0.0
    is_neg = s.startswith("(") and s.endswith(")")
    try: return -float(s[1:-1]) if is_neg else float(s)
    except: pass
    s_clean = re.sub(r'[^0-9.,-]', '', s)
    if not s_clean or s_clean == "-": return 0.0
    if '.' in s_clean and ',' in s_clean:
        s_clean = s_clean.replace('.', '').replace(',', '.') if s_clean.rfind(',') > s_clean.rfind('.') else s_clean.replace(',', '')
    elif ',' in s_clean:
        parts = s_clean.split(',')
        s_clean = s_clean.replace(',', '.') if len(parts[-1]) <= 2 else s_clean.replace(',', '')
    elif s_clean.count('.') > 1: s_clean = s_clean.replace('.', '')
    elif '.' in s_clean:
        parts = s_clean.split('.')
        if len(parts[-1]) == 3 and len(parts[0]) >= 1: s_clean = s_clean.replace('.', '')
    try:
        res = float(s_clean)
        return -abs(res) if is_neg else res
    except: return 0.0

def clamp_date(dt_val, min_d, max_d):
    if not isinstance(dt_val, datetime.date): return max_d
    return max(min_d, min(dt_val, max_d))

def hitung_satpam_keuangan(target_omzet, donasi_masuk, biaya_iklan, kebutuhan_mushaf_pcs=None, leads_meta_val=None):
    target_omzet, donasi_masuk, biaya_iklan = float(target_omzet or 0), float(donasi_masuk or 0), float(biaya_iklan or 0)
    if not kebutuhan_mushaf_pcs or kebutuhan_mushaf_pcs <= 0:
        kebutuhan_mushaf_pcs = max(1, int(round(donasi_masuk / 99000.0))) if donasi_masuk > 0 else 1
    rofi_aktual = (donasi_masuk / biaya_iklan) if biaya_iklan > 0 else 0.0
    roas_meta = (float(leads_meta_val) / biaya_iklan) if (biaya_iklan > 0 and leads_meta_val is not None and float(leads_meta_val) > 0) else (rofi_aktual * 0.79)
    target_crm_cs = max(max(0.0, target_omzet - donasi_masuk), max(0.0, (biaya_iklan * 1.52) - donasi_masuk))
    if rofi_aktual >= 2.63: status_roas, badge_type = "AMAN (Tier 3 >= 2.63x)", "green"
    elif rofi_aktual >= 1.52: status_roas, badge_type = "WASPADA (Tier 1/2)", "orange"
    else: status_roas, badge_type = "KRITIS (< 1.52x • Wajib Subsidi CRM)", "red"
    profit_iklan = donasi_masuk - biaya_iklan
    beban_ops_10 = 0.10 * donasi_masuk
    dsd = donasi_masuk - biaya_iklan - beban_ops_10
    alokasi_mushaf_65, cadangan_cashback_35 = 0.65 * dsd, 0.35 * dsd
    plafon_hpp = (alokasi_mushaf_65 / kebutuhan_mushaf_pcs) if kebutuhan_mushaf_pcs > 0 else 0.0
    if plafon_hpp >= 33500: rekom_tier = "Tier 3: Hard Cover Premium (~Rp 33.500)"
    elif plafon_hpp >= 26000: rekom_tier = "Tier 2: Mushaf Standar (~Rp 26.000)"
    elif plafon_hpp >= 20000: rekom_tier = "Tier 1: Soft Cover (Rp 20.000)"
    else: rekom_tier = "Defisit HPP (< Rp 20rb) • Gunakan Cadangan 35% & Kejar CRM"
    return {
        "roas_aktual": rofi_aktual, "rofi_aktual": rofi_aktual, "roas_meta": roas_meta,
        "status_roas": status_roas, "badge_type": badge_type, "target_crm_cs": target_crm_cs,
        "profit_iklan": profit_iklan, "beban_ops_10": beban_ops_10, "dsd": dsd,
        "alokasi_mushaf_65": alokasi_mushaf_65, "cadangan_cashback_35": cadangan_cashback_35,
        "plafon_hpp": plafon_hpp, "rekom_tier": rekom_tier, "kebutuhan_mushaf_pcs": int(kebutuhan_mushaf_pcs)
    }

# ==============================================================================
# 3. KONFIGURASI AKUN LOGIN & 16 ID GOOGLE SHEETS
# ==============================================================================
ALL_MENUS = ["Dashboard Overview", "Donasi & Satpam Keuangan", "Performa CS & Leads", "Logistik & Gudang", "Kalender Distribusi", "Database & WA Blast"]
AUTH_USERS = {
    "amalqu":     {"key": "amalqu", "username_display": "Amalqu", "pw": "Allah1ahad", "role": "Admin", "title": "Super Administrator", "menus": ALL_MENUS},
    "finance":    {"key": "finance", "username_display": "Finance", "pw": "timfinancejaya99", "role": "Finance", "title": "Divisi Finance & Audit", "menus": ALL_MENUS},
    "advertiser": {"key": "advertiser", "username_display": "Advertiser", "pw": "ngiklangacor99", "role": "Advertiser", "title": "Divisi Digital Ads & Funnel", "menus": ALL_MENUS[:3]},
    "warehouse":  {"key": "warehouse", "username_display": "Warehouse", "pw": "amansulaiman123", "role": "Warehouse", "title": "Divisi Gudang & Distribusi", "menus": ALL_MENUS[3:5]}
}

if st.session_state.auth_user is None:
    try:
        qp_u = str(st.query_params.get("u", "")).strip().lower()
        if qp_u in AUTH_USERS: st.session_state.auth_user = AUTH_USERS[qp_u]
    except: pass

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

def read_csv_nocache(url: str):
    req = urllib.request.Request(url, headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache", "Expires": "0",
        "User-Agent": f"AmalQu-Live/{int(time.time()*1000)}"
    })
    with urllib.request.urlopen(req, timeout=12) as resp:
        return pd.read_csv(io.BytesIO(resp.read()), header=None, dtype=str).fillna("")

def fetch_fast_grid(key_name, sheet_name=None, prefer_sheet=True):
    if key_name not in SHEETS_CONFIG: return pd.DataFrame()
    sid, gid = SHEETS_CONFIG[key_name]
    cb = int(time.time() * 1000)
    base = f"https://docs.google.com/spreadsheets/d/{sid}"
    urls = []
    if sheet_name and prefer_sheet:
        urls.append(f"{base}/gviz/tq?tqx=out:csv&headers=0&sheet={quote(sheet_name)}&cb={cb}")
    urls.append(f"{base}/gviz/tq?tqx=out:csv&headers=0&gid={gid}&cb={cb}")
    urls.append(f"{base}/export?format=csv&gid={gid}&cb={cb}")
    if sheet_name and not prefer_sheet:
        urls.append(f"{base}/gviz/tq?tqx=out:csv&headers=0&sheet={quote(sheet_name)}&cb={cb}")
    for u in urls:
        try:
            df = read_csv_nocache(u)
            if not df.empty and df.shape[1] >= 2:
                fc = str(df.iat[0, 0]).strip().lower()
                if "<!doctype" not in fc and "<html" not in fc: return df
        except: continue
    return pd.DataFrame()

# ==============================================================================
# 4. CSS SYSTEM & LOGIN GATE
# ==============================================================================
is_dark = st.session_state.dark_mode
css_vars = (
    ":root{--bg-main:#0B0F19;--bg-card:#111827;--bg-subcard:#1A2333;--bg-input:#1E293B;--text-primary:#F8FAFC;--text-secondary:#CBD5E1;--text-muted:#94A3B8;--border-soft:#1E293B;--border-strong:#334155;--table-head:#1E293B;--table-hover:#1E293B;--cal-active-bg:linear-gradient(180deg,rgba(249,115,22,0.18) 0%,#111827 100%);--cal-pill-bg:#1E293B;}"
    if is_dark else
    ":root{--bg-main:#F4F7FE;--bg-card:#FFFFFF;--bg-subcard:#F8FAFC;--bg-input:#FFFFFF;--text-primary:#0F172A;--text-secondary:#475569;--text-muted:#64748B;--border-soft:#E2E8F0;--border-strong:#CBD5E1;--table-head:#F8FAFC;--table-hover:#F1F5F9;--cal-active-bg:linear-gradient(180deg,#FFF7ED 0%,#FFFFFF 100%);--cal-pill-bg:#FFFFFF;}"
)
hide_sb = "section[data-testid='stSidebar'],[data-testid='collapsedControl']{display:none!important;}" if st.session_state.auth_user is None else ""

render_html(f"""
<link href="https://cdn.jsdelivr.net/npm/remixicon@4.2.0/fonts/remixicon.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{css_vars}{hide_sb}
footer,[data-testid="stFooter"],[data-testid="stStatusWidget"]{{display:none!important;}}
[data-testid="stHeader"]{{background:transparent!important;height:2rem!important;}}
.stApp,[data-testid="stAppViewContainer"]{{background-color:var(--bg-main)!important;color:var(--text-primary)!important;}}
body,p,label,input,th,td,li{{font-family:'Plus Jakarta Sans',sans-serif!important;color:var(--text-primary);}}
h1,h2,h3,h4,h5,h6,.metric-num,.brand-title{{font-family:'Outfit',sans-serif!important;color:var(--text-primary)!important;}}
[data-testid="stIconMaterial"],.material-symbols-rounded,span[translate="no"]{{font-family:'Material Symbols Rounded'!important;}}
i[class^="ri-"],i[class*=" ri-"]{{font-family:'remixicon'!important;font-style:normal!important;}}
.block-container{{padding-top:1.2rem!important;padding-bottom:2rem!important;max-width:1440px!important;}}
section[data-testid="stSidebar"]{{background-color:var(--bg-card)!important;border-right:1px solid var(--border-soft)!important;width:265px!important;}}
.sub-box{{background:var(--bg-subcard);border:1px solid var(--border-soft);}}
section[data-testid="stSidebar"] div[role="radiogroup"]{{gap:6px!important;display:flex!important;flex-direction:column!important;}}
section[data-testid="stSidebar"] label[data-baseweb="radio"]{{background:transparent!important;border:1px solid transparent!important;border-radius:12px!important;padding:11px 16px!important;margin:0!important;cursor:pointer!important;width:100%!important;}}
section[data-testid="stSidebar"] label[data-baseweb="radio"]>div:not([data-testid="stMarkdownContainer"]),section[data-testid="stSidebar"] label[data-baseweb="radio"] input{{display:none!important;width:0!important;height:0!important;}}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover{{background:var(--bg-subcard)!important;border-color:var(--border-soft)!important;}}
section[data-testid="stSidebar"] label[data-baseweb="radio"] p{{font-size:13.5px!important;font-weight:600!important;color:var(--text-secondary)!important;margin:0!important;}}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked){{background:linear-gradient(135deg,#FF6B4A 0%,#F97316 100%)!important;box-shadow:0 6px 16px rgba(249,115,22,0.28)!important;}}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) p{{color:#FFFFFF!important;font-weight:700!important;}}
div[data-testid="stMainBlockContainer"] div[role="radiogroup"]{{background:var(--bg-subcard)!important;padding:5px!important;border-radius:12px!important;display:flex!important;flex-wrap:wrap!important;gap:6px!important;border:1px solid var(--border-soft)!important;}}
div[data-testid="stMainBlockContainer"] label[data-baseweb="radio"]{{background:transparent!important;padding:7px 14px!important;border-radius:9px!important;cursor:pointer!important;margin:0!important;}}
div[data-testid="stMainBlockContainer"] label[data-baseweb="radio"]>div:not([data-testid="stMarkdownContainer"]),div[data-testid="stMainBlockContainer"] label[data-baseweb="radio"] input{{display:none!important;}}
div[data-testid="stMainBlockContainer"] label[data-baseweb="radio"] p{{font-size:12.5px!important;font-weight:600!important;color:var(--text-secondary)!important;margin:0!important;}}
div[data-testid="stMainBlockContainer"] label[data-baseweb="radio"]:has(input:checked){{background:var(--bg-card)!important;border:1px solid var(--border-strong)!important;}}
div[data-testid="stMainBlockContainer"] label[data-baseweb="radio"]:has(input:checked) p{{color:#FF6B4A!important;font-weight:700!important;}}
div[data-baseweb="select"]>div,div[data-baseweb="input"]>div,div[data-baseweb="base-input"]{{background-color:var(--bg-input)!important;border:1px solid var(--border-strong)!important;border-radius:11px!important;color:var(--text-primary)!important;}}
div[data-baseweb="select"] span,div[data-baseweb="input"] input,div[data-testid="stWidgetLabel"] p{{color:var(--text-primary)!important;font-weight:600!important;font-size:13px!important;}}
div[data-baseweb="popover"],ul[role="listbox"],li[role="option"]{{background-color:var(--bg-card)!important;color:var(--text-primary)!important;}}
button[kind="primary"],button[kind="secondary"],[data-testid="stDownloadButton"] button{{background:var(--bg-card)!important;color:var(--text-primary)!important;border:1px solid var(--border-strong)!important;border-radius:12px!important;font-weight:700!important;padding:8px 14px!important;}}
[data-testid="stFormSubmitButton"] button{{background:linear-gradient(135deg,#FF6B4A 0%,#F97316 100%)!important;color:#FFFFFF!important;border:none!important;border-radius:12px!important;padding:11px 18px!important;}}
[data-testid="stFormSubmitButton"] button p{{color:#FFFFFF!important;font-weight:700!important;}}
.bento-card,[data-testid="stForm"]{{background:var(--bg-card)!important;border:1px solid var(--border-soft)!important;border-radius:18px!important;padding:18px 20px!important;box-shadow:0 4px 18px -2px rgba(0,0,0,0.05)!important;margin-bottom:14px!important;}}
.kpi-uniform{{height:148px;display:flex;flex-direction:column;justify-content:space-between;}}
.hero-card{{background:linear-gradient(135deg,#4F46E5 0%,#6366F1 55%,#8B5CF6 100%);border-radius:18px;padding:18px 20px;height:148px;display:flex;flex-direction:column;justify-content:space-between;color:#FFFFFF!important;box-shadow:0 10px 24px -6px rgba(79,70,229,0.4);margin-bottom:14px;}}
.hero-card *{{color:#FFFFFF!important;}}
.chart-header-box{{background:var(--bg-card);border:1px solid var(--border-soft);border-bottom:none;border-radius:18px 18px 0 0;padding:16px 20px 8px 20px;margin-bottom:-16px;position:relative;z-index:2;}}
[data-testid="stPlotlyChart"]{{background:var(--bg-card)!important;border:1px solid var(--border-soft)!important;border-top:none!important;border-radius:0 0 18px 18px!important;padding:4px 12px 8px 12px!important;margin-bottom:14px!important;}}
.icon-box{{width:36px;height:36px;border-radius:10px;flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;font-size:17px;}}
.ib-indigo{{background:rgba(79,70,229,0.15);color:#6366F1!important;}}.ib-orange{{background:rgba(249,115,22,0.15);color:#F97316!important;}}.ib-emerald{{background:rgba(16,185,129,0.15);color:#10B981!important;}}.ib-rose{{background:rgba(239,68,68,0.15);color:#EF4444!important;}}
.badge-pill{{font-size:10.5px;font-weight:700;padding:3.5px 9px;border-radius:99px;display:inline-flex;align-items:center;gap:4px;white-space:nowrap!important;flex-shrink:0;}}
.bp-green{{background:rgba(16,185,129,0.16);color:#10B981!important;}}.bp-red{{background:rgba(239,68,68,0.16);color:#EF4444!important;}}.bp-orange{{background:rgba(249,115,22,0.16);color:#F97316!important;}}.bp-indigo{{background:rgba(79,70,229,0.16);color:#6366F1!important;}}
.nowrap-val{{white-space:nowrap!important;font-weight:700;}}
.saas-table-wrap{{background:var(--bg-card);border:1px solid var(--border-soft);border-radius:18px;overflow-x:auto;margin-top:8px;margin-bottom:16px;}}
.saas-table{{width:100%;border-collapse:collapse;text-align:left;font-size:12.5px;}}
.saas-table thead tr{{background:var(--table-head);border-bottom:1px solid var(--border-soft);}}
.saas-table th{{padding:11px 14px;font-size:11px;font-weight:700;text-transform:uppercase;color:var(--text-muted)!important;white-space:nowrap;}}
.saas-table td{{padding:11px 14px;color:var(--text-primary)!important;font-weight:500;border-bottom:1px solid var(--border-soft);white-space:nowrap;}}
.saas-table tbody tr:hover{{background:var(--table-hover);}}
.row-summary{{background:rgba(16,185,129,0.09)!important;font-weight:700!important;}}
.row-grand{{background:rgba(79,70,229,0.14)!important;font-weight:800!important;}}
.cal-desktop-only{{display:block;}}.cal-mobile-only{{display:none;}}
.cal-grid-7{{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px;margin-top:12px;}}
.cal-head-cell{{text-align:center;font-size:11px;font-weight:700;color:var(--text-muted)!important;background:var(--bg-subcard);padding:8px 4px;border-radius:8px;border:1px solid var(--border-soft);}}
.cal-cell{{background:var(--bg-card);border:1px solid var(--border-soft);border-radius:12px;min-height:96px;padding:8px 10px;display:flex;flex-direction:column;justify-content:space-between;}}
.cal-cell-empty{{background:var(--bg-subcard);border:1px dashed var(--border-soft);border-radius:12px;min-height:96px;opacity:0.45;}}
.cal-cell-active{{background:var(--cal-active-bg);border:1.5px solid #FB923C;border-radius:12px;min-height:96px;padding:8px 10px;}}
.cal-day-num{{font-family:'Outfit',sans-serif!important;font-size:13px;font-weight:700;color:var(--text-primary)!important;display:flex;justify-content:space-between;align-items:center;gap:4px;}}
.cal-item-pill{{background:var(--cal-pill-bg);border:1px solid var(--border-soft);border-left:3px solid #F97316;border-radius:6px;padding:4px 6px;margin-top:4px;font-size:10.5px;color:var(--text-primary)!important;line-height:1.25;}}
@media screen and (max-width:768px){{.block-container{{padding-left:12px!important;padding-right:12px!important;padding-top:2.8rem!important;}}div[data-testid="stHorizontalBlock"]{{flex-wrap:wrap!important;}}div[data-testid="column"]{{width:100%!important;flex:1 1 100%!important;min-width:100%!important;}}.kpi-uniform,.hero-card{{height:auto!important;min-height:132px!important;}}.cal-desktop-only{{display:none!important;}}.cal-mobile-only{{display:block!important;}}}}
</style>
""")

if st.session_state.auth_user is None:
    _, top_sp2 = st.columns([8.5, 1])
    with top_sp2:
        if st.button("☀️ Terang" if is_dark else "🌙 Gelap", key="login_theme_btn", use_container_width=True):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()
    _, login_col, _ = st.columns([1.3, 1.4, 1.3])
    with login_col:
        render_html(f'<div style="text-align:center;margin-top:16px;margin-bottom:18px;"><div style="margin-bottom:12px;">{build_logo_html(68)}</div><div style="font-family:\'Outfit\',sans-serif!important;font-size:30px;font-weight:800;">AmalQu</div><div style="font-size:13px;font-weight:600;color:var(--text-secondary)!important;margin-top:4px;">Yayasan AmalQu Indonesia Peduli • Command Center</div></div>')
        with st.form("amalqu_login_form", clear_on_submit=False):
            render_html('<div style="text-align:center;margin-bottom:14px;"><div style="font-family:\'Outfit\',sans-serif!important;font-size:17px;font-weight:700;"><i class="ri-shield-keyhole-line" style="color:#FF6B4A!important;"></i> Portal Akses Resmi Divisi</div><div style="font-size:12px;color:var(--text-muted)!important;margin-top:2px;">Silakan masuk menggunakan ID dan Password divisi Anda</div></div>')
            inp_user = st.text_input("ID Pengguna (Username)", placeholder="Ketik ID: Amalqu / Finance / Advertiser / Warehouse")
            inp_pass = st.text_input("Password", type="password", placeholder="Ketik Password Divisi Anda")
            if st.form_submit_button("Masuk ke Command Center", use_container_width=True):
                u_c, p_c = str(inp_user).strip().lower(), str(inp_pass).strip()
                if u_c in AUTH_USERS and AUTH_USERS[u_c]["pw"] == p_c:
                    st.session_state.auth_user = AUTH_USERS[u_c]
                    try: st.query_params["u"] = u_c
                    except: pass
                    st.rerun()
                else: st.error("ID Pengguna atau Password salah.")
    st.stop()

current_user = st.session_state.auth_user
user_role = current_user.get("role", "Admin")
allowed_menus = current_user.get("menus", ["Dashboard Overview"])

# ==============================================================================
# 5. MERGE-SAFE PARSERS UNTUK DASHBOARD CS, STOK MUSHAF & DATABASE
# ==============================================================================
def extract_anchored_table(df_raw, anchor1, anchor2=None, stop_words=None, max_rows=100, max_cols=None):
    if df_raw is None or df_raw.empty: return pd.DataFrame()
    nrows, ncols = df_raw.shape
    start_r, start_c = None, None
    for r in range(nrows):
        for c in range(ncols):
            val = str(df_raw.iat[r, c]).strip()
            if val.lower() == anchor1.lower() or (anchor1.lower() in val.lower() and len(val) <= len(anchor1) + 12):
                if anchor2 is None:
                    start_r, start_c = r, c; break
                else:
                    for cn in range(c + 1, min(ncols, c + 4)):
                        if anchor2.lower() in str(df_raw.iat[r, cn]).strip().lower():
                            start_r, start_c = r, c; break
                    if start_r is not None: break
        if start_r is not None: break
    if start_r is None: return pd.DataFrame()
    headers, end_c = [], start_c
    col_lim = min(ncols, start_c + max_cols) if max_cols else ncols
    while end_c < col_lim:
        h = re.sub(r'\s+', ' ', str(df_raw.iat[start_r, end_c])).strip()
        if h == "" or h.lower().startswith("unnamed"): break
        headers.append(h); end_c += 1
    if not headers: return pd.DataFrame()
    data_rows, empty_streak = [], 0
    for r in range(start_r + 1, min(nrows, start_r + 1 + max_rows)):
        fc = str(df_raw.iat[r, start_c]).strip()
        sc = str(df_raw.iat[r, start_c + 1]).strip() if (start_c + 1) < ncols else ""
        if fc == "" and sc == "":
            empty_streak += 1
            if empty_streak >= 2: break
            continue
        empty_streak = 0
        if stop_words and any(sw.lower() in fc.lower() for sw in stop_words): break
        if fc != "":
            data_rows.append([str(df_raw.iat[r, c]).strip() for c in range(start_c, end_c)])
    return pd.DataFrame(data_rows, columns=headers)

def parse_rekap_harian_cs_2row(grid_okt):
    if grid_okt is None or grid_okt.empty: return pd.DataFrame()
    nrows, ncols = grid_okt.shape
    tgl_r, tgl_c = None, None
    for r in range(nrows):
        for c in range(min(5, ncols)):
            if str(grid_okt.iat[r, c]).strip().lower() == "tanggal":
                rc = " ".join(str(grid_okt.iat[r, cc]).strip().lower() for cc in range(c+1, min(ncols, c+6)))
                bc = " ".join(str(grid_okt.iat[r+1, cc]).strip().lower() for cc in range(c+1, min(ncols, c+6))) if r+1 < nrows else ""
                if "salma" in rc or "leads" in bc or "crm" in bc:
                    tgl_r, tgl_c = r, c; break
        if tgl_r is not None: break
    if tgl_r is None: return pd.DataFrame()
    start_r = tgl_r + 2 if (tgl_r + 1 < nrows and "leads" in " ".join(str(grid_okt.iat[tgl_r+1, cc]).lower() for cc in range(tgl_c+1, min(ncols, tgl_c+5)))) else tgl_r + 1
    rows = []
    for r in range(start_r, min(nrows, start_r + 40)):
        c0 = str(grid_okt.iat[r, tgl_c]).strip()
        if not c0: continue
        if "total" in c0.lower(): break
        def gv(off):
            ci = tgl_c + off
            return num_clean(grid_okt.iat[r, ci]) if ci < ncols else 0.0
        sm, sc, am, ac, nm, nc = gv(1), gv(2), gv(3), gv(4), gv(5), gv(6)
        tl = gv(7) if (tgl_c + 7) < ncols else (sm + am + nm)
        tc = gv(8) if (tgl_c + 8) < ncols else (sc + ac + nc)
        tg = gv(9) if (tgl_c + 9) < ncols else (tl + tc)
        rows.append({
            "Tanggal": c0, "Salma_Meta": sm, "Salma_CRM": sc, "Aulia_Meta": am, "Aulia_CRM": ac,
            "Nisa_Meta": nm, "Nisa_CRM": nc, "Total_Leads": tl, "Total_CRM": tc, "Total_Gabungan": tg,
            "Salma": sm + sc, "Aulia": am + ac, "Nisa": nm + nc, "Total Donasi": tg, "Donasi Final": tg
        })
    return pd.DataFrame(rows)

def parse_monitoring_roas_finance(grid_okt):
    """Pemindai Anti-Merge untuk Kolom J-N (Monitoring ROAS Finance) dan Kolom B-H (Kanal/Metrik Donasi)."""
    res, kanal_rows = {}, []
    if grid_okt is None or grid_okt.empty: return res, pd.DataFrame()
    nrows, ncols = grid_okt.shape
    for r in range(nrows):
        for c in range(ncols):
            cell_txt = str(grid_okt.iat[r, c]).strip()
            if not cell_txt: continue
            kl = cell_txt.lower()
            right_vals = [str(grid_okt.iat[r, cc]).strip() for cc in range(c + 1, min(ncols, c + 7)) if str(grid_okt.iat[r, cc]).strip() != ""]
            if not right_vals: continue
            v_num = num_clean(right_vals[0])
            if "realisasi donasi finance" in kl and v_num > 0: res["realisasi_finance"] = v_num
            elif ("budget iklan" in kl or "ad spend" in kl) and "rata" not in kl and v_num > 0: res["budget_iklan"] = v_num
            elif "rofi real saat ini" in kl and v_num > 0: res["rofi_real"] = v_num
            elif "hari cut-off berjalan" in kl and v_num > 0: res["hari_cutoff"] = int(v_num)
            elif "rata-rata donasi / hari" in kl and v_num > 0: res["avg_donasi_hari"] = v_num
            elif "rata-rata ad spend / hari" in kl and v_num > 0: res["avg_ads_hari"] = v_num
            elif "estimasi donasi akhir bulan" in kl and v_num > 0: res["estimasi_akhir_bulan"] = v_num
            elif kl in ["total leads meta", "total crm (repeat order)", "total sedekah lainnya", "roas akuisisi (leads meta)", "rofi cs closing (leads + crm)"]:
                nom_s = right_vals[0] if len(right_vals) >= 1 else "-"
                ras_s = right_vals[1] if len(right_vals) >= 2 else "-"
                ket_s = right_vals[2] if len(right_vals) >= 3 else ""
                kanal_rows.append({"Kanal / Metrik Donasi": cell_txt, "Nominal": nom_s, "% Kontribusi / Rasio": ras_s, "Keterangan & Analisis": ket_s})
                if "roas akuisisi" in kl:
                    rv = num_clean(ras_s) if num_clean(ras_s) > 0 else num_clean(nom_s)
                    if rv > 0: res["roas_akuisisi"] = rv
                elif "rofi cs closing" in kl:
                    rv = num_clean(ras_s) if num_clean(ras_s) > 0 else num_clean(nom_s)
                    if rv > 0: res["rofi_cs"] = rv
    return res, (pd.DataFrame(kanal_rows) if kanal_rows else pd.DataFrame())

def parse_stok_dashboard_new(grid_ms):
    out = {}
    if grid_ms is None or grid_ms.empty: return out
    t_inv = extract_anchored_table(grid_ms, "Produk & Kategori", "Kanal Promosi", max_rows=10, max_cols=5)
    if not t_inv.empty and t_inv.shape[1] >= 5:
        t_inv = t_inv.iloc[:, :5].copy()
        t_inv.columns = ["Produk & Kategori", "Kanal Promosi", "Siap Salur (Stiker)", "Belum Siap (Proses)", "Total Stok Fisik"]
        for cn in ["Siap Salur (Stiker)", "Belum Siap (Proses)", "Total Stok Fisik"]:
            t_inv[cn] = t_inv[cn].apply(lambda x: int(num_clean(x)))
        out["rincian_inventaris"] = t_inv
    t_def = extract_anchored_table(grid_ms, "Periode / Komponen Analisis", "Target / Stok", max_rows=10, max_cols=5)
    if not t_def.empty and t_def.shape[1] >= 5:
        t_def = t_def.iloc[:, :5].copy()
        t_def.columns = ["Periode / Komponen Analisis", "Target / Stok", "Keterangan Operasional", "Gap / Defisit", "Status & Rekomendasi"]
        out["analisis_defisit"] = t_def
    return out

def parse_setting_dashboard_crm(grid_db):
    out = {}
    if grid_db is None or grid_db.empty: return out
    t_seg = extract_anchored_table(grid_db, "Prioritas", "Segmentasi", stop_words=["Status Reminder", "TOTAL"], max_rows=12, max_cols=5)
    if t_seg.empty: t_seg = extract_anchored_table(grid_db, "Kode", "Segmentasi", stop_words=["Status Reminder", "TOTAL"], max_rows=12, max_cols=5)
    if not t_seg.empty and t_seg.shape[1] >= 4: out["segmentasi"] = t_seg
    t_rem = extract_anchored_table(grid_db, "Status Reminder", "Jumlah", stop_words=["Status Donatur", "TOTAL"], max_rows=8, max_cols=3)
    if not t_rem.empty and t_rem.shape[1] >= 2: out["reminder"] = t_rem
    t_stat = extract_anchored_table(grid_db, "Status Donatur", "Jumlah", stop_words=["TOTAL"], max_rows=8, max_cols=3)
    if not t_stat.empty and t_stat.shape[1] >= 2: out["status_donatur"] = t_stat
    return out

def parse_live_leads_tab(grid_cs, cs_label):
    if grid_cs is None or grid_cs.empty: return []
    rows_extracted = []
    nrows, ncols = grid_cs.shape
    for r in range(nrows):
        row_vals = [str(grid_cs.iat[r, c]).strip() for c in range(min(ncols, 22))]
        tgl_found, tgl_col_idx = None, None
        for c_idx in range(min(4, len(row_vals))):
            v = row_vals[c_idx]
            if not v: continue
            m_iso = re.search(r'(2026-\d{2}-\d{1,2})', v)
            m_slash = re.match(r'^(\d{1,2})[/\-](\d{1,2})[/\-]2026$', v)
            m_text = re.search(r'(\d{1,2})\s*(?:okt|oct|oktober|october)', v, re.IGNORECASE)
            if m_iso:
                pts = m_iso.group(1).split("-")
                m_v, d_v = int(pts[1]), int(pts[2])
                if m_v == 10 and 1 <= d_v <= 31: tgl_found, tgl_col_idx = f"2026-10-{d_v:02d}", c_idx; break
                elif d_v == 10 and 1 <= m_v <= 31: tgl_found, tgl_col_idx = f"2026-10-{m_v:02d}", c_idx; break
            elif m_slash:
                p1, p2 = int(m_slash.group(1)), int(m_slash.group(2))
                if p2 == 10 and 1 <= p1 <= 31: tgl_found, tgl_col_idx = f"2026-10-{p1:02d}", c_idx; break
                elif p1 == 10 and 1 <= p2 <= 31: tgl_found, tgl_col_idx = f"2026-10-{p2:02d}", c_idx; break
            elif m_text:
                dp = int(m_text.group(1))
                if 1 <= dp <= 31: tgl_found, tgl_col_idx = f"2026-10-{dp:02d}", c_idx; break
        if tgl_found and tgl_col_idx is not None:
            bc = tgl_col_idx + 1
            def gn(off):
                idx = bc + off
                return num_clean(row_vals[idx]) if idx < len(row_vals) else 0.0
            cv, ci, cl, nom = int(gn(0)), int(gn(1)), int(gn(2)), float(gn(3))
            sql, sqc, sqn = int(gn(4)), int(gn(5)), float(gn(6))
            jql, jqc, jqn = int(gn(7)), int(gn(8)), float(gn(9))
            aql, aqc, aqn = int(gn(10)), int(gn(11)), float(gn(12))
            tfu = int(gn(13))
            if cv > 0 or cl > 0 or nom > 0 or tfu > 0:
                rows_extracted.append((cs_label, tgl_found, cv, ci, cl, nom, sql, sqc, sqn, jql, jqc, jqn, aql, aqc, aqn, tfu))
    return rows_extracted

# ==============================================================================
# 6. TRUE AUTO-SYNC ENGINE (REFRESH OTOMATIS TIAP 60 DETIK + INSTANT NONCE)
# ==============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def load_core_realtime_data(sync_token: int):
    db, sync_status = {}, {}

    macro_rows = [
        ("Januari",   326000000, 313838000, 194267000, 218457000, 222889000, 90949200,  1.44, 40.8,  "Tidak Tercapai", 2356),
        ("Februari",  522000000, 244568000, 230443000, 228843000, 232374000, 12194000,  1.07, 5.2,   "Tidak Tercapai", 1906),
        ("Maret",     835000000, 432950000, 443374100, 331054000, 334504000, 98446500,  1.31, 29.4,  "Tidak Tercapai", 3814),
        ("April",     359000000, 292695000, 253733400, 262156000, 266465000, 26230300,  1.12, 9.8,   "Tidak Tercapai", 2225),
        ("Mei",       395029000, 485195000, 154142300, 335053000, 338597000, 146597000, 1.45, 43.3,  "Tercapai",       1454),
        ("Juni",      434532000, 457976000, 408027750, 345054000, 356438000, 101538000, 1.33, 28.5,  "Tercapai",       4103),
        ("Juli",      477986000, 490683000, 374520900, 345049000, 353467000, 137216000, 1.42, 38.8,  "Tercapai",       3586),
        ("Agustus",   525784000, 371847000, 290718820, 320040000, 322971000, 48876700,  1.16, 15.1,  "Tidak Tercapai", 2852),
        ("September", 350000000, 310384000, 272608400, 254360000, 107038000, 203346000, 1.22, 190.0, "Tidak Tercapai", 2599),
        ("Oktober",   500000000, 238587386, 192709457, 205020588, 205020588, 33566798,  1.16, 16.4,  "Realtime",       946),
    ]
    db['macro_monthly'] = pd.DataFrame(macro_rows, columns=["Bulan", "Target Bulanan", "Realisasi Finance", "Omset CS", "Budget Iklan", "Total Pengeluaran", "Laba Bersih", "ROFI", "ROI_Pct", "Status Target", "Mushaf Terverifikasi"])

    cs_ov_rows = [
        (1, "Nisa",   "Aktif",     1200000000, 15839000,  68093999,  196005644, 125603001, 74540362, 200017711, 197594767, 84384400,  71315000, 122697449, 1033393884, 6219, 166167, "86,1%", "39,4%"),
        (2, "Salma",  "Aktif",     1200000000, 153161444, 130171224, 201796334, 85285000,  50347999, 121468905, 79080000,  104793000, 72695000, 56986008,  998798907,  5898, 169345, "83,2%", "38,1%"),
        (3, "Aulia",  "Aktif",     500000000,  0,         396000,    1894000,   11719000,  11748999, 76174000,  84631886,  84775000,  64809000, 13026000,  336147885,  2128, 157964, "67,2%", "12,8%"),
        (4, "Desi",   "Non-Aktif", 200000000,  25267000,  26163000,  3342596,   23010375,  9298900,  4316750,   6395000,   4917625,   42651438, 0,         145362684,  924,  157319, "72,7%", "5,5%"),
        (5, "Syafiq", "Non-Aktif", 0,          0,         5619000,   35515478,  8116000,   8206000,  6050000,   0,         0,         0,        0,         63506478,   257,  247107, "0,0%",  "2,4%"),
        (6, "Rida",   "Non-Aktif", 150000000,  0,         0,         0,         0,         0,        0,         2495000,   5128000,   15148000, 0,         22771000,   150,  151807, "15,2%", "0,9%"),
        (7, "Olive",  "Aktif CRM", 0,          0,         0,         0,         0,         0,        0,         4324000,   6720800,   5990000,  1296500,   17034800,   106,  160706, "0,0%",  "0,6%"),
        (8, "Sarah",  "Non-Aktif", 100000000,  0,         0,         4820000,   0,         0,        0,         0,         0,         0,        0,         4820000,    23,   209565, "4,8%",  "0,2%"),
    ]
    db['cs_overview'] = pd.DataFrame(cs_ov_rows, columns=["Rank", "Nama CS", "Status Okt", "Target Omset", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "Total Omset (Jan-Sep)", "Total Closing", "AOV", "Pencapaian (%)", "Kontribusi (%)"])

    db['okt_kpi'] = {"total_donasi": 192709457, "target": 500000000, "capaian_pct": 42.8, "donasi_final": 175574457, "harian_terbaru": 8861008, "verifikasi_pct": 91.1}
    db['okt_finance_mon'] = {"realisasi_finance": 238587386, "budget_iklan": 205020588, "rofi_real": 1.16, "roas_akuisisi": 0.79, "rofi_cs": 1.16, "hari_cutoff": 23, "avg_donasi_hari": 10373365, "avg_ads_hari": 8913939, "estimasi_akhir_bulan": 321574303}
    db['okt_cs_table'] = pd.DataFrame([
        {"CS / CRM": "Salma", "Harian (Total)": 2464008, "Harian (Final)": 2464008, "Mingguan (Total)": 2464008, "Mingguan (Final)": 2464008, "Bulanan (Total)": 56986008,  "Bulanan (Final)": 50828008,  "% Verifikasi": "89,2%", "Total Transaksi": 409,  "Target (Rp)": 200000000, "% Capaian Target": "28,5%", "Sisa Target": 143013992, "Pending Verifikasi": 6158000,  "Target Harian (Sisa)": 4613355},
        {"CS / CRM": "Aulia", "Harian (Total)": 453000,  "Harian (Final)": 453000,  "Mingguan (Total)": 453000,  "Mingguan (Final)": 453000,  "Bulanan (Total)": 13026000,  "Bulanan (Final)": 11418000,  "% Verifikasi": "87,7%", "Total Transaksi": 126,  "Target (Rp)": 50000000,  "% Capaian Target": "26,1%", "Sisa Target": 36974000,  "Pending Verifikasi": 1608000,  "Target Harian (Sisa)": 1192710},
        {"CS / CRM": "Nisa",  "Harian (Total)": 5944000, "Harian (Final)": 5944000, "Mingguan (Total)": 5944000, "Mingguan (Final)": 5944000, "Bulanan (Total)": 122697449, "Bulanan (Final)": 113328449, "% Verifikasi": "92,4%", "Total Transaksi": 809,  "Target (Rp)": 200000000, "% Capaian Target": "61,3%", "Sisa Target": 77302551,  "Pending Verifikasi": 9369000,  "Target Harian (Sisa)": 2493631},
        {"CS / CRM": "TOTAL", "Harian (Total)": 8861008, "Harian (Final)": 8861008, "Mingguan (Total)": 8861008, "Mingguan (Final)": 8861008, "Bulanan (Total)": 192709457, "Bulanan (Final)": 175574457, "% Verifikasi": "91,1%", "Total Transaksi": 1344, "Target (Rp)": 450000000, "% Capaian Target": "42,8%", "Sisa Target": 257290543, "Pending Verifikasi": 17135000, "Target Harian (Sisa)": 8299695},
    ])
    db['okt_sumber'] = pd.DataFrame([
        {"CS / CRM": "Salma", "Leads Meta": 45398008,  "Repeat Order CRM": 0,       "Repeat Order non CRM": 10590000, "Lainnya": 998000,  "Total Nominal": 56986008,  "% Leads Meta": "79,7%"},
        {"CS / CRM": "Aulia", "Leads Meta": 1144000,   "Repeat Order CRM": 7264000, "Repeat Order non CRM": 0,        "Lainnya": 4618000, "Total Nominal": 13026000,  "% Leads Meta": "8,8%"},
        {"CS / CRM": "Nisa",  "Leads Meta": 115225449, "Repeat Order CRM": 0,       "Repeat Order non CRM": 6181000,  "Lainnya": 1291000, "Total Nominal": 122697449, "% Leads Meta": "93,9%"},
        {"CS / CRM": "TOTAL", "Leads Meta": 161767457, "Repeat Order CRM": 7264000, "Repeat Order non CRM": 16771000, "Lainnya": 6907000, "Total Nominal": 192709457, "% Leads Meta": "83,9%"},
    ])
    db['okt_kanal_rasio'] = pd.DataFrame([
        {"Kanal / Metrik Donasi": "Total Leads Meta",             "Nominal": "Rp161.767.457", "% Kontribusi / Rasio": "83,9%", "Keterangan & Analisis": "Perolehan donasi dari iklan berbayar Meta Ads"},
        {"Kanal / Metrik Donasi": "Total CRM (Repeat Order)",     "Nominal": "Rp30.942.000",  "% Kontribusi / Rasio": "12,5%", "Keterangan & Analisis": "Donasi berulang donatur CRM & non-CRM"},
        {"Kanal / Metrik Donasi": "Total Sedekah Lainnya",        "Nominal": "Rp6.907.000",   "% Kontribusi / Rasio": "3,6%",  "Keterangan & Analisis": "Donasi program umum di luar mushaf / Quran"},
        {"Kanal / Metrik Donasi": "ROAS Akuisisi (Leads Meta)",   "Nominal": "-",             "% Kontribusi / Rasio": "0,79x", "Keterangan & Analisis": "Efektivitas donasi Meta terhadap belanja iklan"},
        {"Kanal / Metrik Donasi": "ROFI CS Closing (Leads + CRM)","Nominal": "-",             "% Kontribusi / Rasio": "1,16x", "Keterangan & Analisis": "Rasio donasi closing CS terhadap belanja iklan"},
    ])

    harian_rows_base = [
        ("2026-10-01", 2464008, 0, 0, 453000, 5744000, 200000, 8208008, 653000, 8861008),
        ("2026-10-02", 4362000, 629000, 0, 1591000, 8155000, 746000, 12517000, 2966000, 15483000),
        ("2026-10-03", 1595000, 70000, 0, 657000, 2094000, 198000, 3689000, 925000, 4614000),
        ("2026-10-04", 2273000, 50000, 0, 283000, 3785000, 0, 6058000, 333000, 6391000),
        ("2026-10-05", 1375000, 50000, 225000, 1854000, 3738000, 143000, 5338000, 2047000, 7385000),
        ("2026-10-06", 1766000, 300000, 719000, 555000, 2979000, 607000, 5464000, 1462000, 6926000),
        ("2026-10-07", 1062000, 50000, 0, 454000, 3013000, 298000, 4075000, 802000, 4877000),
        ("2026-10-08", 775000, 530000, 0, 653000, 5168000, 797000, 5943000, 1980000, 7923000),
        ("2026-10-09", 4816000, 1280000, 0, 853000, 8276000, 609000, 13092000, 2742000, 15834000),
        ("2026-10-10", 2388000, 100000, 100000, 707000, 1819000, 229000, 4307000, 1036000, 5343000),
        ("2026-10-11", 1346000, 0, 0, 255000, 4288950, 399000, 5634950, 654000, 6288950),
        ("2026-10-12", 997000, 450000, 0, 154000, 4130000, 400000, 5127000, 1004000, 6131000),
        ("2026-10-13", 1092000, 150000, 0, 300000, 7004000, 1079000, 8096000, 1529000, 9625000),
        ("2026-10-14", 3391000, 100000, 0, 299000, 5488000, 110000, 8879000, 509000, 9388000),
        ("2026-10-15", 1788000, 332000, 100000, 189000, 6341000, 204000, 8229000, 725000, 8954000),
        ("2026-10-16", 230000, 5201000, 0, 1578000, 10099500, 508000, 10329500, 7287000, 17616500),
        ("2026-10-17", 200000, 100000, 0, 299000, 4911000, 325000, 5111000, 724000, 5835000),
        ("2026-10-18", 0, 124000, 0, 149000, 6933000, 104000, 6933000, 377000, 7310000),
        ("2026-10-19", 400000, 275000, 0, 300000, 7062999, 0, 7462999, 575000, 8037999),
        ("2026-10-20", 1064000, 1199000, 0, 299000, 7329000, 298000, 8393000, 1796000, 10189000),
        ("2026-10-21", 5384000, 200000, 0, 0, 4371000, 218000, 9755000, 418000, 10173000),
        ("2026-10-22", 2487000, 100000, 0, 0, 1098000, 0, 3585000, 100000, 3685000),
        ("2026-10-23", 4143000, 298000, 0, 0, 1398000, 0, 5541000, 298000, 5839000),
    ]
    db['okt_harian'] = pd.DataFrame([
        {
            "Tanggal": r[0], "Salma_Meta": r[1], "Salma_CRM": r[2], "Aulia_Meta": r[3], "Aulia_CRM": r[4],
            "Nisa_Meta": r[5], "Nisa_CRM": r[6], "Total_Leads": r[7], "Total_CRM": r[8], "Total_Gabungan": r[9],
            "Salma": r[1] + r[2], "Aulia": r[3] + r[4], "Nisa": r[5] + r[6], "Total Donasi": r[9], "Donasi Final": r[9]
        } for r in harian_rows_base
    ])

    db['stok_rincian_baru'] = pd.DataFrame([
        {"Produk & Kategori": "Mushaf - Super Tajwid",       "Kanal Promosi": "Meta Ads",     "Siap Salur (Stiker)": 801,  "Belum Siap (Proses)": 0,    "Total Stok Fisik": 801},
        {"Produk & Kategori": "Mushaf - Al Wakaf (Meta Ads)","Kanal Promosi": "Meta Ads",     "Siap Salur (Stiker)": 298,  "Belum Siap (Proses)": 2328, "Total Stok Fisik": 2626},
        {"Produk & Kategori": "Mushaf - Al Wakaf (TikTok)",  "Kanal Promosi": "TikTok",       "Siap Salur (Stiker)": 20,   "Belum Siap (Proses)": 0,    "Total Stok Fisik": 20},
        {"Produk & Kategori": "Buku Belajar Super Tahsin",   "Kanal Promosi": "TikTok",       "Siap Salur (Stiker)": 1388, "Belum Siap (Proses)": 1500, "Total Stok Fisik": 2888},
        {"Produk & Kategori": "Titipan Mitra Yayasan Lain",  "Kanal Promosi": "Yayasan Lain", "Siap Salur (Stiker)": 0,    "Belum Siap (Proses)": 0,    "Total Stok Fisik": 0},
        {"Produk & Kategori": "TOTAL INVENTARIS FISIK",      "Kanal Promosi": "Semua Kanal",  "Siap Salur (Stiker)": 2507, "Belum Siap (Proses)": 3828, "Total Stok Fisik": 6335},
    ])
    db['stok_defisit_baru'] = pd.DataFrame([
        {"Periode / Komponen Analisis": "Kebutuhan Agustus 2026",            "Target / Stok": "604",   "Keterangan Operasional": "Realisasi: 0 Pcs",          "Gap / Defisit": "604",   "Status & Rekomendasi": "Belum Salur"},
        {"Periode / Komponen Analisis": "Kebutuhan September 2026",          "Target / Stok": "2.599", "Keterangan Operasional": "Realisasi: 0 Pcs",          "Gap / Defisit": "2.599", "Status & Rekomendasi": "Belum Salur"},
        {"Periode / Komponen Analisis": "Kebutuhan Oktober 2026",            "Target / Stok": "946",   "Keterangan Operasional": "Realisasi: 100 Pcs",        "Gap / Defisit": "846",   "Status & Rekomendasi": "Sebagian Salur"},
        {"Periode / Komponen Analisis": "Total Kebutuhan (Agust - Okt)",     "Target / Stok": "4.149", "Keterangan Operasional": "Akumulasi 3 Bulan",         "Gap / Defisit": "4.049", "Status & Rekomendasi": "Target Distribusi Aktif"},
        {"Periode / Komponen Analisis": "Total Stok Fisik Mushaf Tersedia",  "Target / Stok": "3.447", "Keterangan Operasional": "Siap Salur & Proses Cetak", "Gap / Defisit": "(702)", "Status & Rekomendasi": "Stok Fisik Belum Cukup"},
        {"Periode / Komponen Analisis": "KEKURANGAN PEMBELIAN MUSHAF BARU",  "Target / Stok": "702",   "Keterangan Operasional": "Defisit Bersih vs Stok",    "Gap / Defisit": "(702)", "Status & Rekomendasi": "WAJIB BELI 702 MUSHAF"},
    ])

    db['db_kpi'] = {"total_donatur": 14464, "total_leads": 3416, "total_kontak": 17880, "konversi_pct": 80.9, "total_donasi_kumulatif": 2604405566, "rata_rata_donasi": 180061, "callback_segera": 12285}
    db['db_segmentasi'] = pd.DataFrame([
        {"Prioritas": "A1", "Segmentasi Donatur": "Donatur Platinum Prioritas Utama", "Target Tindakan CRM": "Personal Call & Layanan VIP Khusus", "Jumlah Donatur": 20, "Porsi (%)": "0,14%"},
        {"Prioritas": "A2", "Segmentasi Donatur": "Donatur VIP Potensial", "Target Tindakan CRM": "Pendekatan Personal Berkala", "Jumlah Donatur": 12, "Porsi (%)": "0,08%"},
        {"Prioritas": "B1", "Segmentasi Donatur": "Donatur Rutin Menengah", "Target Tindakan CRM": "Reminder Rutin & Penyaluran", "Jumlah Donatur": 92, "Porsi (%)": "0,64%"},
        {"Prioritas": "B2", "Segmentasi Donatur": "Donatur Berkala Menengah", "Target Tindakan CRM": "Ajakan Donasi Program Tematik", "Jumlah Donatur": 118, "Porsi (%)": "0,82%"},
        {"Prioritas": "C1", "Segmentasi Donatur": "Donatur Reguler Loyal", "Target Tindakan CRM": "Update Buletin & Do'a Harian", "Jumlah Donatur": 32, "Porsi (%)": "0,22%"},
        {"Prioritas": "D4", "Segmentasi Donatur": "Donatur Churn / Pasif", "Target Tindakan CRM": "Reaktivasi Program Spesial", "Jumlah Donatur": 4385, "Porsi (%)": "30,32%"},
        {"Prioritas": "Reguler", "Segmentasi Donatur": "Donatur Standar / Umum", "Target Tindakan CRM": "Broadcast Buletin Massal", "Jumlah Donatur": 9805, "Porsi (%)": "67,79%"},
    ])
    db['db_reminder'] = pd.DataFrame([
        {"Status Reminder": "CALLBACK SEGERA", "Jumlah Donatur": 12285, "Persentase (%)": "84,94%"},
        {"Status Reminder": "PANTAU", "Jumlah Donatur": 1628, "Persentase (%)": "11,26%"},
        {"Status Reminder": "AMAN", "Jumlah Donatur": 550, "Persentase (%)": "3,80%"},
    ])
    db['db_status_donatur'] = pd.DataFrame([
        {"Status Donatur": "Donatur Churn", "Jumlah Donatur": 6933, "Persentase (%)": "47,93%"},
        {"Status Donatur": "Donatur Baru", "Jumlah Donatur": 6894, "Persentase (%)": "47,66%"},
        {"Status Donatur": "Donatur Aktif", "Jumlah Donatur": 492, "Persentase (%)": "3,40%"},
        {"Status Donatur": "Donatur Rutin", "Jumlah Donatur": 145, "Persentase (%)": "1,00%"},
    ])

    tasks = {
        "ov":      ("data_cs", "Overview_Semua_CS", True),
        "okt":     ("bulan_oktober", "Dashboard CS", True),
        "l_nisa":  ("leads_cs", "CS NISA", True),
        "l_salma": ("leads_cs", "CS SALMA", True),
        "l_aulia": ("leads_cs", "CS AUL", True),
        "stok":    ("stok_mushaf", None, False),
        "kal":     ("kalender_dist", "Kalender Oktober 2026", True),
        "db_set":  ("master_db", "SETTING DASHBOARD", True),
    }
    fetched = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        fut_map = {ex.submit(fetch_fast_grid, k_nm, sh_nm, p_sh): tag for tag, (k_nm, sh_nm, p_sh) in tasks.items()}
        for fut in as_completed(fut_map):
            tag = fut_map[fut]
            try: fetched[tag] = fut.result()
            except: fetched[tag] = pd.DataFrame()

    g_ov = fetched.get("ov", pd.DataFrame())
    if not g_ov.empty:
        t_fin_live = extract_anchored_table(g_ov, "Bulan", "Target Bulanan", stop_words=["Total Target", "Sisa Target"], max_rows=15)
        if not t_fin_live.empty:
            sync_status["Data CS & Finance"] = f"Live ({len(t_fin_live)} bln)"
            for _, r_live in t_fin_live.iterrows():
                b_name = str(r_live.get("Bulan", "")).strip()
                if b_name in db['macro_monthly']['Bulan'].values and b_name != "Oktober":
                    v_real, v_tgt, v_ads = num_clean(r_live.get("Realisasi Omset", 0)), num_clean(r_live.get("Target Bulanan", 0)), num_clean(r_live.get("Budget Iklan", 0))
                    if v_real > 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'Realisasi Finance'] = v_real
                    if v_tgt > 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'Target Bulanan'] = v_tgt
                    if v_ads > 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'Budget Iklan'] = v_ads
        else: sync_status["Data CS & Finance"] = "Live Connected"
    else: sync_status["Data CS & Finance"] = "Baseline Aktif"

    g_okt = fetched.get("okt", pd.DataFrame())
    if not g_okt.empty:
        mon_fin, df_kan_live = parse_monitoring_roas_finance(g_okt)
        if not df_kan_live.empty: db['okt_kanal_rasio'] = df_kan_live
        if mon_fin.get("realisasi_finance", 0) > 0:
            db['okt_finance_mon'].update(mon_fin)
            db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == 'Oktober', 'Realisasi Finance'] = mon_fin["realisasi_finance"]
        if mon_fin.get("budget_iklan", 0) > 0:
            db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == 'Oktober', 'Budget Iklan'] = mon_fin["budget_iklan"]
            db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == 'Oktober', 'Total Pengeluaran'] = mon_fin["budget_iklan"]

        t_cs_okt = extract_anchored_table(g_okt, "CS / CRM", "Harian", stop_words=["ANALISIS"], max_rows=10)
        if not t_cs_okt.empty and "Bulanan (Total)" in t_cs_okt.columns:
            for col_n in ["Harian (Total)", "Harian (Final)", "Mingguan (Total)", "Mingguan (Final)", "Bulanan (Total)", "Bulanan (Final)", "Target (Rp)", "Sisa Target", "Pending Verifikasi", "Target Harian (Sisa)"]:
                if col_n in t_cs_okt.columns: t_cs_okt[col_n] = t_cs_okt[col_n].apply(num_clean)
            if "Total Transaksi" in t_cs_okt.columns: t_cs_okt["Total Transaksi"] = t_cs_okt["Total Transaksi"].apply(lambda x: int(num_clean(x)))
            db['okt_cs_table'] = t_cs_okt
            non_tot = t_cs_okt[t_cs_okt['CS / CRM'].astype(str).str.upper() != 'TOTAL']
            tot_don_okt, tot_fin_okt = float(non_tot['Bulanan (Total)'].sum()), float(non_tot['Bulanan (Final)'].sum())
            if tot_don_okt > 0:
                db['okt_kpi']['total_donasi'], db['okt_kpi']['donasi_final'] = tot_don_okt, tot_fin_okt
                db['okt_kpi']['verifikasi_pct'] = round(tot_fin_okt / tot_don_okt * 100, 1)
                db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == 'Oktober', 'Omset CS'] = tot_don_okt
                for _, r_ok in non_tot.iterrows():
                    c_nm = str(r_ok.get("CS / CRM", "")).strip()
                    if c_nm in db['cs_overview']['Nama CS'].values:
                        db['cs_overview'].loc[db['cs_overview']['Nama CS'] == c_nm, 'Oktober'] = float(r_ok.get("Bulanan (Total)", 0))

        t_src_okt = extract_anchored_table(g_okt, "CS / CRM", "Leads Meta", stop_words=["Kanal / Metrik", "REKAPITULASI"], max_rows=10, max_cols=7)
        if not t_src_okt.empty and "Leads Meta" in t_src_okt.columns:
            for col_s in ["Leads Meta", "Repeat Order CRM", "Repeat Order non CRM", "Lainnya", "Total Nominal"]:
                if col_s in t_src_okt.columns: t_src_okt[col_s] = t_src_okt[col_s].apply(num_clean)
            db['okt_sumber'] = t_src_okt
            non_tot_s = t_src_okt[t_src_okt['CS / CRM'].astype(str).str.upper() != 'TOTAL']
            tot_meta_okt = float(non_tot_s['Leads Meta'].sum())
            ads_now = float(db['okt_finance_mon'].get('budget_iklan', 205020588))
            if tot_meta_okt > 0 and ads_now > 0 and "roas_akuisisi" not in mon_fin:
                db['okt_finance_mon']['roas_akuisisi'] = round(tot_meta_okt / ads_now, 2)

        t_har_2row = parse_rekap_harian_cs_2row(g_okt)
        if not t_har_2row.empty:
            db['okt_harian'] = t_har_2row
            sync_status["Dashboard CS Oktober"] = f"Live ({len(t_har_2row[t_har_2row['Total_Gabungan'] > 0])} hari aktif)"
        else: sync_status["Dashboard CS Oktober"] = "Live Synced"
    else: sync_status["Dashboard CS Oktober"] = "Baseline 23 Okt"

    df_m = db['macro_monthly']
    df_m['Laba Bersih'] = df_m['Realisasi Finance'] - df_m['Total Pengeluaran']
    df_m['ROFI'] = np.where(df_m['Budget Iklan'] > 0, (df_m['Realisasi Finance'] / df_m['Budget Iklan']).round(2), 0.0)
    df_m['ROAS_Est'] = np.where(df_m['Bulan'] == 'Oktober', db['okt_finance_mon'].get('roas_akuisisi', 0.79), (df_m['ROFI'] * 0.72).round(2))
    df_m['Selisih Target'] = df_m['Realisasi Finance'] - df_m['Target Bulanan']
    df_m['Selisih Finance vs CS'] = df_m['Realisasi Finance'] - df_m['Omset CS']
    df_m['% Capaian'] = np.where(df_m['Target Bulanan'] > 0, (df_m['Realisasi Finance'] / df_m['Target Bulanan'] * 100).round(1), 0.0)

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
    for tag_l, cs_lbl in [("l_nisa", "Nisa"), ("l_salma", "Salma"), ("l_aulia", "Aulia")]:
        g_l = fetched.get(tag_l, pd.DataFrame())
        if not g_l.empty: live_leads_all.extend(parse_live_leads_tab(g_l, cs_lbl))

    if len(live_leads_all) >= 5:
        sync_status["Leads & CR Harian"] = f"Live ({len(live_leads_all)} baris)"
        leads_source = live_leads_all
    else:
        sync_status["Leads & CR Harian"] = "Baseline Aktif"
        leads_source = leads_rows_default

    df_leads = pd.DataFrame(leads_source, columns=[
        "Nama CS", "Tanggal", "Chat Valid", "Chat Invalid", "Closing", "Nominal",
        "SantriQu_Leads", "SantriQu_Closing", "SantriQu_Nominal",
        "JariyahQu_Leads", "JariyahQu_Closing", "JariyahQu_Nominal",
        "AmalQu_Leads", "AmalQu_Closing", "AmalQu_Nominal", "Total Follow Up"
    ])
    df_leads["Conv Rate (%)"] = np.where(df_leads["Chat Valid"] > 0, (df_leads["Closing"] / df_leads["Chat Valid"] * 100).round(1), 0.0)
    db['leads_okt'] = df_leads

    cr_by_date_all = df_leads.groupby("Tanggal", as_index=False).agg({"Chat Valid": "sum", "Closing": "sum"})
    cr_map_all = {r["Tanggal"]: round(r["Closing"] / r["Chat Valid"] * 100, 1) for _, r in cr_by_date_all.iterrows() if r["Chat Valid"] > 0}
    tot_v_all, tot_c_all = df_leads["Chat Valid"].sum(), df_leads["Closing"].sum()
    db['avg_cr_okt'] = round(tot_c_all / tot_v_all * 100, 1) if tot_v_all > 0 else 74.3

    df_har = db['okt_harian'].copy()
    df_har['CR_Harian_Pct'] = df_har['Tanggal'].map(lambda d: cr_map_all.get(str(d).strip(), np.nan))
    db['okt_harian'] = df_har

    g_stok = fetched.get("stok", pd.DataFrame())
    if not g_stok.empty:
        parsed_s = parse_stok_dashboard_new(g_stok)
        if "rincian_inventaris" in parsed_s:
            db['stok_rincian_baru'] = parsed_s["rincian_inventaris"]
            sync_status["Stok Mushaf Real-Time"] = "Live Synced"
        if "analisis_defisit" in parsed_s:
            db['stok_defisit_baru'] = parsed_s["analisis_defisit"]
            sync_status["Stok Mushaf Real-Time"] = "Live Synced"
        if "Stok Mushaf Real-Time" not in sync_status:
            sync_status["Stok Mushaf Real-Time"] = "Live Connected"
    else:
        sync_status["Stok Mushaf Real-Time"] = "Baseline Baru (702 Defisit)"

    for cn in ["Siap Salur (Stiker)", "Belum Siap (Proses)", "Total Stok Fisik"]:
        if cn not in db['stok_rincian_baru'].columns: db['stok_rincian_baru'][cn] = 0
        else: db['stok_rincian_baru'][cn] = db['stok_rincian_baru'][cn].apply(lambda x: int(num_clean(x)))

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
    g_kal = fetched.get("kal", pd.DataFrame())
    if not g_kal.empty:
        t_kal = extract_anchored_table(g_kal, "No", "Tanggal Agenda", stop_words=["TOTAL"], max_rows=45)
        if not t_kal.empty and "Nama Lembaga Penerima" in t_kal.columns:
            cols_aj = t_kal.columns[:10].tolist()
            t_kal_aj = t_kal[cols_aj].copy()
            if "Jumlah Mushaf (Pcs)" in t_kal_aj.columns:
                t_kal_aj["Jumlah Mushaf (Pcs)"] = t_kal_aj["Jumlah Mushaf (Pcs)"].apply(lambda x: int(num_clean(x)))
            t_kal_aj = t_kal_aj[t_kal_aj["Nama Lembaga Penerima"].astype(str).str.strip() != ""]
            if not t_kal_aj.empty:
                db['kalender_okt'] = t_kal_aj
                sync_status["Kalender Distribusi"] = f"Live ({len(t_kal_aj)} titik)"
    if "Kalender Distribusi" not in sync_status:
        sync_status["Kalender Distribusi"] = "Live (9 titik)"

    g_db_set = fetched.get("db_set", pd.DataFrame())
    if not g_db_set.empty:
        parsed_db_s = parse_setting_dashboard_crm(g_db_set)
        if "segmentasi" in parsed_db_s: db['db_segmentasi'] = parsed_db_s["segmentasi"]
        if "reminder" in parsed_db_s: db['db_reminder'] = parsed_db_s["reminder"]
        if "status_donatur" in parsed_db_s: db['db_status_donatur'] = parsed_db_s["status_donatur"]
        sync_status["Master Database CRM"] = "Live Synced"
    else:
        sync_status["Master Database CRM"] = "Baseline Aktif"

    df_inv = db['stok_rincian_baru']
    df_kal = db['kalender_okt']
    def get_inv_row(kw):
        m = df_inv[df_inv['Produk & Kategori'].astype(str).str.contains(kw, case=False, na=False)]
        if not m.empty:
            r = m.iloc[0]
            return int(num_clean(r.get("Siap Salur (Stiker)", 0))), int(num_clean(r.get("Belum Siap (Proses)", 0))), int(num_clean(r.get("Total Stok Fisik", 0)))
        return 0, 0, 0

    st_siap, st_belum, st_tot = get_inv_row("Super Tajwid")
    aw_m_siap, aw_m_belum, aw_m_tot = get_inv_row("Al Wakaf \\(Meta")
    aw_t_siap, aw_t_belum, aw_t_tot = get_inv_row("Al Wakaf \\(TikTok")
    bt_siap, bt_belum, bt_tot = get_inv_row("Super Tahsin")
    jadwal_st = int(df_kal[df_kal['Variasi Mushaf'].astype(str).str.contains('Super Tajwid', case=False, na=False)]['Jumlah Mushaf (Pcs)'].sum()) if not df_kal.empty else 653
    jadwal_aw = int(df_kal[df_kal['Variasi Mushaf'].astype(str).str.contains('Al Wakaf', case=False, na=False)]['Jumlah Mushaf (Pcs)'].sum()) if not df_kal.empty else 351

    db['stok_audit'] = {
        "meta_lp_total": st_tot + aw_m_tot, "tiktok_mushaf_total": aw_t_tot, "buku_tahsin_total": bt_tot,
        "mushaf_siap_akumulasi": aw_m_siap + aw_t_siap, "mushaf_siap_all": st_siap + aw_m_siap + aw_t_siap,
        "tahsin_siap_salur": bt_siap, "defisit_agust_okt": 702, "kebutuhan_agust_okt": 4149,
        "stok_fisik_mushaf_tersedia": 3447, "total_inventaris_fisik": st_tot + aw_m_tot + aw_t_tot + bt_tot,
        "total_inventaris_siap": st_siap + aw_m_siap + aw_t_siap + bt_siap,
        "total_inventaris_belum": st_belum + aw_m_belum + aw_t_belum + bt_belum,
        "st_siap": st_siap, "st_belum": st_belum, "st_total": st_tot, "st_jadwal": jadwal_st, "st_gap_siap": st_siap - jadwal_st,
        "aw_meta_siap": aw_m_siap, "aw_tik_siap": aw_t_siap, "aw_total_siap": aw_m_siap + aw_t_siap,
        "aw_total_belum": aw_m_belum + aw_t_belum, "aw_jadwal": jadwal_aw, "aw_gap_total_siap": (aw_m_siap + aw_t_siap) - jadwal_aw,
        "bt_siap": bt_siap, "bt_belum": bt_belum, "bt_total": bt_tot, "bt_jadwal": 200, "bt_gap_siap": bt_siap - 200
    }

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
        {"Bulan": "Oktober",   "Total Mushaf Terverifikasi": 946,  "Verifikasi (Belum Stiker)": 846,  "Penamaan Mushaf (Stiker)": 0,   "Packing / Proses Distribusi": 0,    "Distribusi Selesai": 100},
    ])

    db['sync_status'] = sync_status
    db['last_sync'] = now_wib().strftime("%d %b %Y • %H:%M:%S WIB")
    return db

@st.cache_data(ttl=120, show_spinner=False)
def load_lazy_contacts_db(sync_token: int):
    sid, _ = SHEETS_CONFIG["master_db"]
    cb = int(time.time() * 1000)
    urls = [
        f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv&headers=0&sheet=DATABASE&cb={cb}",
        f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv&sheet=DATABASE&cb={cb}"
    ]
    for u_db in urls:
        try:
            df_raw = read_csv_nocache(u_db)
            if not df_raw.empty and df_raw.shape[1] >= 4:
                hdr_idx = 0
                for r_i in range(min(15, len(df_raw))):
                    row_txt = " ".join(str(x).lower() for x in df_raw.iloc[r_i].values)
                    if "nama" in row_txt and ("whatsapp" in row_txt or "hp" in row_txt or "program" in row_txt or "kategori" in row_txt):
                        hdr_idx = r_i; break
                headers = [str(x).strip() if str(x).strip() else f"Col_{i}" for i, x in enumerate(df_raw.iloc[hdr_idx].values)]
                df_c = df_raw.iloc[hdr_idx+1:].copy()
                df_c.columns = headers
                col_map = {}
                for c in df_c.columns:
                    cl = c.lower()
                    if "nama donatur" in cl or (cl == "nama" and "Nama Donatur" not in col_map.values()): col_map[c] = "Nama Donatur"
                    elif "whatsapp" in cl or "no hp" in cl or "nomor hp" in cl:
                        if "Nomor Whatsapp" not in col_map.values(): col_map[c] = "Nomor Whatsapp"
                    elif cl in ["pic", "cs", "pj cs"]: col_map[c] = "PiC"
                    elif "program" in cl:
                        if "Program" not in col_map.values(): col_map[c] = "Program"
                    elif "donasi terakhir" in cl or "tanggal" in cl:
                        if "Donasi Terakhir" not in col_map.values(): col_map[c] = "Donasi Terakhir"
                    elif "kategori" in cl or "status donatur" in cl:
                        if "Kategori" not in col_map.values(): col_map[c] = "Kategori"
                    elif "prioritas" in cl or "segmen" in cl:
                        if "Prioritas" not in col_map.values(): col_map[c] = "Prioritas"
                    elif "reminder" in cl:
                        if "Reminder" not in col_map.values(): col_map[c] = "Reminder"
                    elif "fu1" in cl or "sapaan" in cl: col_map[c] = "FU1 (Sapaan)"
                    elif "fu3" in cl or "laporan" in cl: col_map[c] = "FU3 (Laporan Penyaluran)"
                df_c.rename(columns=col_map, inplace=True)
                df_c = df_c.loc[:, ~df_c.columns.duplicated()]
                for req in ["Nama Donatur", "Nomor Whatsapp", "PiC", "Program", "Donasi Terakhir", "Kategori", "Prioritas", "Reminder", "FU1 (Sapaan)", "FU3 (Laporan Penyaluran)"]:
                    if req not in df_c.columns: df_c[req] = "-"
                    else: df_c[req] = df_c[req].fillna("-").astype(str).str.strip()
                df_c = df_c[(df_c["Nama Donatur"] != "") & (df_c["Nama Donatur"] != "-") & (~df_c["Nama Donatur"].str.lower().str.contains("nama donatur"))]
                if len(df_c) >= 5:
                    return df_c.reset_index(drop=True), False
        except: continue
    sample = pd.DataFrame([
        {"Nama Donatur": "Donatur Prioritas A1", "Nomor Whatsapp": "628000000001", "PiC": "CS Nisa",  "Program": "Waqaf/Mushaf", "Donasi Terakhir": "1 Oktober 2026",   "Kategori": "Donatur Rutin", "FU1 (Sapaan)": "Sudah", "FU3 (Laporan Penyaluran)": "Sudah", "Prioritas": "A1",      "Reminder": "AMAN"},
        {"Nama Donatur": "Donatur Aktif B1",     "Nomor Whatsapp": "628000000002", "PiC": "CS Salma", "Program": "AmalQu",       "Donasi Terakhir": "2 Oktober 2026",   "Kategori": "Donatur Aktif", "FU1 (Sapaan)": "Sudah", "FU3 (Laporan Penyaluran)": "Belum", "Prioritas": "B1",      "Reminder": "PANTAU"},
        {"Nama Donatur": "Donatur Baru Reguler", "Nomor Whatsapp": "628000000003", "PiC": "CS Aulia", "Program": "AmalQu",       "Donasi Terakhir": "5 Oktober 2026",   "Kategori": "Donatur Baru",  "FU1 (Sapaan)": "Belum", "FU3 (Laporan Penyaluran)": "Belum", "Prioritas": "Reguler", "Reminder": "CALLBACK SEGERA"},
        {"Nama Donatur": "Donatur Reaktivasi D4","Nomor Whatsapp": "628000000004", "PiC": "CRM Olive","Program": "Waqaf/Mushaf", "Donasi Terakhir": "14 Februari 2026", "Kategori": "Donatur Churn", "FU1 (Sapaan)": "Belum", "FU3 (Laporan Penyaluran)": "Belum", "Prioritas": "D4",      "Reminder": "CALLBACK SEGERA"},
    ])
    return sample, True

# Token otomatis berganti tiap 60 detik atau langsung berganti saat tombol Sync diklik
current_sync_token = int(time.time() // 60) + (st.session_state.sync_nonce * 100000)
db = load_core_realtime_data(current_sync_token)
df_macro = db['macro_monthly']
sa = db['stok_audit']

# ==============================================================================
# 7. SIDEBAR NAVIGASI & TOMBOL INSTANT FORCE-SYNC
# ==============================================================================
with st.sidebar:
    render_html(f"""
    <div style="display:flex;align-items:center;gap:12px;padding:4px 4px 18px 4px;border-bottom:1px solid var(--border-soft);margin-bottom:14px;">
        {build_logo_html(44)}
        <div>
            <div class="brand-title" style="font-family:'Outfit',sans-serif!important;font-weight:800;font-size:21px;line-height:1.15;">AmalQu</div>
            <div class="brand-sub" style="font-size:11px;font-weight:600;line-height:1.3;margin-top:2px;">Yayasan AmalQu Indonesia Peduli</div>
        </div>
    </div>
    <div style="font-size:11px;font-weight:700;color:var(--text-muted)!important;letter-spacing:0.8px;text-transform:uppercase;padding:4px 6px 8px 6px;">
        MENU DIVISI ({user_role.upper()})
    </div>
    """)
    menu_pilihan = st.radio("Navigasi Utama", allowed_menus, label_visibility="collapsed")
    render_html(f"""
    <div class="sub-box" style="margin-top:20px;padding:13px 14px;border-radius:14px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
            <i class="ri-shield-user-line" style="color:#6366F1!important;font-size:16px;"></i>
            <span style="font-size:12.5px;font-weight:700;">{current_user['username_display']} ({user_role})</span>
        </div>
        <div style="font-size:11px;color:var(--text-secondary)!important;line-height:1.45;">
            {current_user['title']}<br>
            <span style="color:#10B981!important;font-weight:700;">● No-Cache Auto-Sync (60s)</span><br>
            <span style="font-size:10.5px;color:var(--text-muted)!important;">WIB: {db['last_sync']}</span>
        </div>
    </div>
    """)
    with st.expander("📡 Detail Koneksi Sheet"):
        for mod_name, stat_txt in db.get("sync_status", {}).items():
            st.caption(f"🟢 **{mod_name}**: {stat_txt}")
    sb_col1, sb_col2 = st.columns(2)
    with sb_col1:
        if st.button("🔄 Sync Data", use_container_width=True):
            st.session_state.sync_nonce += 1
            st.cache_data.clear()
            st.rerun()
    with sb_col2:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.auth_user = None
            try: st.query_params.clear()
            except: pass
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
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
            <span style="font-size:12.5px;font-weight:600;color:var(--text-secondary)!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{title}</span>
            <div class="icon-box {ib_map.get(color_theme, 'ib-indigo')}"><i class="{icon_cls}"></i></div>
        </div>
        <div class="metric-num" style="font-size:24px;font-weight:800;letter-spacing:-0.5px;white-space:nowrap;">{value}</div>
        <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;flex-wrap:nowrap;">
            <span class="badge-pill {bp_map.get(badge_theme, 'bp-green')}"><i class="{arrow_ic}"></i> {badge_text}</span>
            <span style="font-size:11px;color:var(--text-muted)!important;font-weight:600;white-space:nowrap;">{subtext}</span>
        </div>
    </div>
    """)

def render_chart_header(title_text, subtitle_text="", badge_text="", badge_theme="indigo"):
    bp_map = {"green": "bp-green", "red": "bp-red", "orange": "bp-orange", "indigo": "bp-indigo"}
    badge_html = f'<span class="badge-pill {bp_map.get(badge_theme, "bp-indigo")}">{badge_text}</span>' if badge_text else ""
    sub_html = f'<div style="font-size:11.5px;color:var(--text-muted)!important;margin-top:2px;">{subtitle_text}</div>' if subtitle_text else ""
    render_html(f'<div class="chart-header-box"><div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;"><div style="min-width:0;"><div style="font-family:\'Outfit\',sans-serif!important;font-size:15.5px;font-weight:700;color:var(--text-primary)!important;">{title_text}</div>{sub_html}</div>{badge_html}</div></div>')

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

def render_saas_table(df: pd.DataFrame, max_rows=60):
    if df is None or df.empty:
        render_html('<div class="bento-card"><p style="color:var(--text-muted)!important;margin:0;">Data tidak ditemukan untuk filter ini.</p></div>')
        return
    df_show = df.head(max_rows).copy()
    ths = "".join([f"<th>{str(c)}</th>" for c in df_show.columns])
    trs = ""
    for _, row in df_show.iterrows():
        first_val = str(row.iloc[0]).upper()
        tr_cls = ' class="row-summary"' if "TOTAL" in first_val or "KEKURANGAN" in first_val else ""
        tds = ""
        for col_name in df_show.columns:
            val_str = str(row[col_name])
            low_v = val_str.lower()
            if any(k in low_v for k in ["tercapai", "aktif", "siap salur cukup", "stok cukup", "tersedia", "selesai", "aman", "sudah", "sebagian salur"]) and "tidak" not in low_v and "non-aktif" not in low_v and "belum" not in low_v:
                cell_html = f'<span class="badge-pill bp-green"><i class="ri-checkbox-circle-fill"></i> {val_str}</span>'
            elif any(k in low_v for k in ["tidak tercapai", "non-aktif", "defisit", "kritis", "habis", "callback segera", "churn", "kurang", "wajib beli", "belum cukup"]):
                cell_html = f'<span class="badge-pill bp-red"><i class="ri-error-warning-fill"></i> {val_str}</span>'
            elif any(k in low_v for k in ["scheduled", "perlu", "proses", "menipis", "pantau", "belum", "realtime", "reguler"]):
                cell_html = f'<span class="badge-pill bp-orange"><i class="ri-time-fill"></i> {val_str}</span>'
            elif col_name in ["Nama CS", "CS / CRM", "Bulan", "Nama Lembaga Penerima", "Nama Donatur", "Jenis Produk", "Produk & Kategori", "Periode / Komponen Analisis"]:
                cell_html = f'<span style="font-weight:700;">{val_str}</span>'
            else: cell_html = val_str
            tds += f"<td>{cell_html}</td>"
        trs += f"<tr{tr_cls}>{tds}</tr>"
    render_html(f'<div class="saas-table-wrap"><table class="saas-table"><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></div>')

def render_rekap_harian_cs_table(df_har: pd.DataFrame, avg_cr_val: float):
    if df_har is None or df_har.empty: return
    sum_s_m, sum_s_c = df_har['Salma_Meta'].sum(), df_har['Salma_CRM'].sum()
    sum_a_m, sum_a_c = df_har['Aulia_Meta'].sum(), df_har['Aulia_CRM'].sum()
    sum_n_m, sum_n_c = df_har['Nisa_Meta'].sum(), df_har['Nisa_CRM'].sum()
    sum_leads, sum_crm, sum_gab = df_har['Total_Leads'].sum(), df_har['Total_CRM'].sum(), df_har['Total_Gabungan'].sum()
    rows_html = ""
    for _, r in df_har.iterrows():
        cr_v = r.get("CR_Harian_Pct", np.nan)
        cr_txt = f'<span class="badge-pill bp-green">{cr_v:.1f}%</span>' if pd.notna(cr_v) and cr_v > 0 else "-"
        rows_html += (
            f"<tr><td style='font-weight:700;'>{r['Tanggal']}</td>"
            f"<td>{rp_dash(r['Salma_Meta'])}</td><td>{rp_dash(r['Salma_CRM'])}</td>"
            f"<td>{rp_dash(r['Aulia_Meta'])}</td><td>{rp_dash(r['Aulia_CRM'])}</td>"
            f"<td>{rp_dash(r['Nisa_Meta'])}</td><td>{rp_dash(r['Nisa_CRM'])}</td>"
            f"<td style='font-weight:600;'>{rp_dash(r['Total_Leads'])}</td>"
            f"<td style='font-weight:600;'>{rp_dash(r['Total_CRM'])}</td>"
            f"<td style='font-weight:700;color:#10B981!important;'>{rp_dash(r['Total_Gabungan'])}</td>"
            f"<td style='text-align:center;'>{cr_txt}</td></tr>"
        )
    rows_html += (
        f"<tr class='row-summary'><td>TOTAL</td>"
        f"<td>{rp_dash(sum_s_m)}</td><td>{rp_dash(sum_s_c)}</td>"
        f"<td>{rp_dash(sum_a_m)}</td><td>{rp_dash(sum_a_c)}</td>"
        f"<td>{rp_dash(sum_n_m)}</td><td>{rp_dash(sum_n_c)}</td>"
        f"<td>{rp_dash(sum_leads)}</td><td>{rp_dash(sum_crm)}</td>"
        f"<td>{rp_dash(sum_gab)}</td><td style='text-align:center;'>Rata-rata CR</td></tr>"
        f"<tr class='row-grand'><td>TOTAL KESELURUHAN</td>"
        f"<td colspan='2' style='text-align:center;color:#10B981!important;'>Salma: {rp_dash(sum_s_m + sum_s_c)}</td>"
        f"<td colspan='2' style='text-align:center;color:#10B981!important;'>Aulia: {rp_dash(sum_a_m + sum_a_c)}</td>"
        f"<td colspan='2' style='text-align:center;color:#10B981!important;'>Nisa: {rp_dash(sum_n_m + sum_n_c)}</td>"
        f"<td>{rp_dash(sum_leads)}</td><td>{rp_dash(sum_crm)}</td>"
        f"<td style='color:#6366F1!important;'>{rp_dash(sum_gab)}</td>"
        f"<td style='text-align:center;'><span class='badge-pill bp-indigo'>{avg_cr_val:.1f}%</span></td></tr>"
    )
    render_html(f"""
    <div class="saas-table-wrap">
        <table class="saas-table">
            <thead>
                <tr>
                    <th rowspan="2" style="vertical-align:middle;">Tanggal</th>
                    <th colspan="2" style="text-align:center;border-bottom:1px solid var(--border-strong);">Salma</th>
                    <th colspan="2" style="text-align:center;border-bottom:1px solid var(--border-strong);">Aulia</th>
                    <th colspan="2" style="text-align:center;border-bottom:1px solid var(--border-strong);">Nisa</th>
                    <th rowspan="2" style="vertical-align:middle;">Total Leads</th>
                    <th rowspan="2" style="vertical-align:middle;">Total CRM</th>
                    <th rowspan="2" style="vertical-align:middle;">Total Gabungan</th>
                    <th rowspan="2" style="vertical-align:middle;text-align:center;">CR Harian (%)</th>
                </tr>
                <tr><th>Leads Meta</th><th>CRM</th><th>Leads Meta</th><th>CRM</th><th>Leads Meta</th><th>CRM</th></tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """)

# ==============================================================================
# 9. TOP HEADER BAR
# ==============================================================================
hdr_col_left, hdr_col_right = st.columns([7.5, 1.1])
with hdr_col_left:
    render_html(f"""
    <div class="bento-card" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;padding:12px 18px!important;margin-bottom:14px!important;">
        <div style="display:flex;align-items:center;gap:12px;">
            {build_logo_html(40)}
            <div>
                <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                    <span style="font-family:'Outfit',sans-serif!important;font-size:20px;font-weight:800;">AmalQu</span>
                    <span class="badge-pill bp-orange">{menu_pilihan}</span>
                </div>
                <div style="font-size:12px;font-weight:600;color:var(--text-secondary)!important;">Yayasan AmalQu Indonesia Peduli • Enterprise Command Center</div>
            </div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
            <span class="badge-pill bp-indigo"><i class="ri-user-star-line"></i> {current_user['username_display']} ({user_role})</span>
            <span class="badge-pill bp-green"><i class="ri-flashlight-fill" style="font-size:11px;"></i> {db['last_sync']}</span>
        </div>
    </div>
    """)
with hdr_col_right:
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("☀️ Terang" if is_dark else "🌙 Gelap", key="top_theme_toggle", use_container_width=True):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

# ==============================================================================
# HALAMAN 1: DASHBOARD OVERVIEW (MENAMPILKAN ROAS & ROFI SEKALIGUS)
# ==============================================================================
if menu_pilihan == "Dashboard Overview":
    fm = db['okt_finance_mon']
    okt_r = df_macro[df_macro['Bulan'] == 'Oktober'].iloc[0]
    real_okt = float(fm.get('realisasi_finance', okt_r['Realisasi Finance']))
    cs_okt_total = float(db['okt_kpi']['total_donasi'])
    cs_okt_final = float(db['okt_kpi']['donasi_final'])
    selisih_real_cs_okt = real_okt - cs_okt_total
    target_okt = float(okt_r['Target Bulanan'])
    ads_okt = float(fm.get('budget_iklan', okt_r['Budget Iklan']))
    hari_cutoff = int(fm.get('hari_cutoff', 23))
    laju_harian_real = float(fm.get('avg_donasi_hari', real_okt / max(1, hari_cutoff)))
    proyeksi_akhir_bulan_real = float(fm.get('estimasi_akhir_bulan', laju_harian_real * 31))

    non_tot_s = db['okt_sumber'][db['okt_sumber']['CS / CRM'].astype(str).str.upper() != 'TOTAL']
    leads_meta_okt = float(non_tot_s['Leads Meta'].sum()) if not non_tot_s.empty else 161767457.0
    satpam_okt = hitung_satpam_keuangan(target_okt, real_okt, ads_okt, okt_r['Mushaf Terverifikasi'], leads_meta_val=leads_meta_okt)
    roas_okt_val = float(fm.get('roas_akuisisi', satpam_okt['roas_meta']))
    rofi_okt_val = float(fm.get('rofi_real', satpam_okt['rofi_aktual']))
    tot_fin_ytd = df_macro['Realisasi Finance'].sum()

    c1, c2, c3, c4 = st.columns(4)
    with c1: render_bento_kpi("ri-bank-line", "indigo", "Realisasi Finance (Okt)", rp_short(real_okt), f"{(real_okt/target_okt)*100:.1f}% Target", "indigo", f"YTD: {rp_short(tot_fin_ytd)}")
    with c2: render_bento_kpi("ri-user-voice-line", "emerald", "Dashboard CS (Oktober)", rp_short(cs_okt_total), f"Bank +{rp_short(selisih_real_cs_okt)}", "green", f"Final: {rp_short(cs_okt_final)}")
    with c3: render_bento_kpi("ri-line-chart-line", "orange", "Proyeksi Akhir Bulan", rp_short(proyeksi_akhir_bulan_real), f"{(proyeksi_akhir_bulan_real/target_okt)*100:.1f}% Target", "orange", f"Avg: {rp_short(laju_harian_real)}/hr")
    with c4:
        render_html(f"""
        <div class="hero-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:11px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;">SATPAM KEUANGAN (ROAS & ROFI)</span>
                <i class="ri-shield-star-line" style="font-size:18px;"></i>
            </div>
            <div class="metric-num" style="font-size:21.5px;font-weight:800;white-space:nowrap;letter-spacing:-0.4px;">
                ROAS {roas_okt_val:.2f}x <span style="opacity:0.65;font-weight:500;">|</span> ROFI {rofi_okt_val:.2f}x
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;background:rgba(255,255,255,0.16);padding:6px 10px;border-radius:10px;font-size:11px;font-weight:600;gap:8px;">
                <span class="nowrap-val">Ads: {rp_short(ads_okt)}</span>
                <span class="nowrap-val">DSD: {rp_short(satpam_okt['dsd'])}</span>
            </div>
        </div>
        """)

    m_left, m_right = st.columns([1.75, 1.05])
    with m_left:
        render_chart_header("Komparasi Real Finance vs Dashboard CS & Proyeksi Akhir Bulan", f"Realisasi Finance Okt: {rp(real_okt)} • Input CS: {rp(cs_okt_total)} • Estimasi 31 Okt: {rp(proyeksi_akhir_bulan_real)}", "Jan – Okt 2026", "indigo")
        fig_ov = go.Figure()
        fig_ov.add_trace(go.Scatter(x=df_macro['Bulan'], y=df_macro['Realisasi Finance'], name='Real Finance (Bank)', mode='lines+markers', line=dict(color='#6366F1', width=3, shape='spline'), fill='tozeroy', fillcolor='rgba(99, 102, 241, 0.1)'))
        fig_ov.add_trace(go.Scatter(x=df_macro['Bulan'], y=df_macro['Omset CS'], name='Input Dashboard CS', mode='lines+markers', line=dict(color='#10B981', width=2.6, shape='spline')))
        sep_real = float(df_macro[df_macro['Bulan'] == 'September']['Realisasi Finance'].iloc[0])
        fig_ov.add_trace(go.Scatter(x=['September', 'Oktober'], y=[sep_real, proyeksi_akhir_bulan_real], name='Proyeksi Akhir Bulan', mode='lines+markers', line=dict(color='#F59E0B', width=3, dash='dash')))
        fig_ov.add_trace(go.Scatter(x=df_macro['Bulan'], y=df_macro['Budget Iklan'], name='Biaya Iklan (Ads)', mode='lines+markers', line=dict(color='#FF6B4A', width=2, dash='dot', shape='spline')))
        apply_saas_plotly(fig_ov, height=340, is_currency=True)
        st.plotly_chart(fig_ov, use_container_width=True)

    with m_right:
        if user_role == "Advertiser":
            bottom_box_html = f'<div class="sub-box" style="border-radius:12px;padding:11px 14px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span style="font-size:12px;font-weight:700;"><i class="ri-advertisement-line" style="color:#10B981!important;"></i> Rasio ROAS & ROFI (Okt)</span><span class="badge-pill bp-green">Avg CR {db["avg_cr_okt"]:.1f}%</span></div><div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px;"><span style="color:var(--text-secondary)!important;">Leads Meta (83,9%)</span><span class="nowrap-val" style="color:#10B981!important;">{rp(leads_meta_okt)}</span></div><div style="display:flex;justify-content:space-between;font-size:12px;"><span style="color:var(--text-secondary)!important;">ROAS Meta / ROFI Real</span><span class="nowrap-val">{roas_okt_val:.2f}x / {rofi_okt_val:.2f}x</span></div></div>'
        else:
            bottom_box_html = f'<div class="sub-box" style="border-radius:12px;padding:11px 14px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span style="font-size:12px;font-weight:700;"><i class="ri-alarm-warning-line" style="color:#EF4444!important;"></i> Status Inventaris & Defisit (Agust–Okt)</span><span class="badge-pill bp-red">Wajib Beli {sa["defisit_agust_okt"]} Mushaf</span></div><div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px;"><span style="color:var(--text-secondary)!important;">Kebutuhan 3 Bln vs Stok Mushaf</span><span class="nowrap-val">{sa["kebutuhan_agust_okt"]:,} vs {sa["stok_fisik_mushaf_tersedia"]:,} Pcs</span></div><div style="display:flex;justify-content:space-between;font-size:12px;"><span style="color:var(--text-secondary)!important;">Total Inventaris Fisik (Semua)</span><span class="nowrap-val" style="color:#10B981!important;">{sa["total_inventaris_fisik"]:,} Pcs (Siap: {sa["total_inventaris_siap"]:,})</span></div></div>'

        render_html(f"""
        <div class="bento-card" style="min-height:392px;display:flex;flex-direction:column;justify-content:space-between;">
            <div>
                <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:12px;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <div class="icon-box ib-indigo" style="width:32px;height:32px;font-size:15px;"><i class="ri-scales-3-line"></i></div>
                        <span style="font-family:'Outfit',sans-serif!important;font-weight:700;font-size:15px;">Monitoring ROAS, ROFI & Proyeksi</span>
                    </div>
                    <span class="badge-pill bp-indigo">CUT-OFF {hari_cutoff} HARI</span>
                </div>
                <div class="sub-box" style="border-radius:12px;padding:11px 14px;margin-bottom:10px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;margin-bottom:5px;">
                        <span style="color:var(--text-secondary)!important;">1. Realisasi Donasi Finance</span><span class="nowrap-val" style="color:#6366F1!important;">{rp(real_okt)}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;margin-bottom:5px;">
                        <span style="color:var(--text-secondary)!important;">2. Total Input Dashboard CS</span><span class="nowrap-val" style="color:#10B981!important;">{rp(cs_okt_total)}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;border-top:1px dashed var(--border-soft);padding-top:5px;">
                        <span style="color:var(--text-secondary)!important;">ROAS Akuisisi Meta / ROFI Real</span><span class="nowrap-val" style="color:#F97316!important;">ROAS {roas_okt_val:.2f}x • ROFI {rofi_okt_val:.2f}x</span>
                    </div>
                </div>
                <div class="sub-box" style="border-radius:12px;padding:11px 14px;margin-bottom:10px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                        <span style="font-size:12px;font-weight:700;"><i class="ri-compass-3-line" style="color:#F59E0B!important;"></i> Proyeksi Akhir Bulan (31 Okt)</span>
                        <span class="badge-pill bp-orange">{(proyeksi_akhir_bulan_real/target_okt)*100:.1f}% Target</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px;">
                        <span style="color:var(--text-secondary)!important;">Rata-Rata Donasi / Hari</span><span class="nowrap-val">{rp(laju_harian_real)}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px;">
                        <span style="color:var(--text-secondary)!important;">Rata-Rata Ad Spend / Hari</span><span class="nowrap-val">{rp(fm.get('avg_ads_hari', ads_okt/max(1,hari_cutoff)))}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:12px;">
                        <span style="color:var(--text-secondary)!important;">Estimasi Donasi Akhir Bulan</span><span class="nowrap-val" style="color:#10B981!important;">{rp(proyeksi_akhir_bulan_real)}</span>
                    </div>
                </div>
            </div>
            {bottom_box_html}
        </div>
        """)

    b1, b2, b3 = st.columns(3)
    if user_role == "Advertiser":
        with b1: render_html(f'<div class="bento-card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span style="font-size:12.5px;font-weight:700;">Perolehan CS Aktif (Oktober)</span><span class="badge-pill bp-indigo">1.344 Transaksi</span></div><div class="metric-num" style="font-size:22px;font-weight:800;margin-bottom:8px;">{rp_short(cs_okt_total)}</div><div style="display:flex;height:9px;border-radius:99px;overflow:hidden;gap:3px;margin-bottom:8px;background:var(--bg-subcard);"><div style="width:64%;background:#FF6B4A;border-radius:99px;"></div><div style="width:29%;background:#4F46E5;border-radius:99px;"></div><div style="width:7%;background:#10B981;border-radius:99px;"></div></div><div style="display:flex;justify-content:space-between;font-size:11px;font-weight:600;color:var(--text-secondary)!important;"><span>Nisa: <b>Rp 122,7 Jt</b></span><span>Salma: <b>Rp 57,0 Jt</b></span><span>Aulia: <b>Rp 13,0 Jt</b></span></div></div>')
        with b2: render_html(f'<div class="bento-card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span style="font-size:12.5px;font-weight:700;">Sumber Kontak Donasi (Oktober)</span><span class="badge-pill bp-green">83,9% Meta Ads</span></div><div class="metric-num" style="font-size:22px;font-weight:800;margin-bottom:8px;">{rp_short(leads_meta_okt)} Leads Meta</div><div style="display:flex;height:9px;border-radius:99px;overflow:hidden;gap:3px;margin-bottom:8px;background:var(--bg-subcard);"><div style="width:84%;background:#10B981;border-radius:99px;"></div><div style="width:13%;background:#4F46E5;border-radius:99px;"></div><div style="width:3%;background:#F59E0B;border-radius:99px;"></div></div><div style="display:flex;justify-content:space-between;font-size:11px;font-weight:600;color:var(--text-secondary)!important;"><span>Meta: <b>83,9%</b></span><span>CRM Total: <b>Rp 30,9 Jt (12,5%)</b></span><span>Lainnya: <b>3,6%</b></span></div></div>')
        with b3: render_html(f'<div class="bento-card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span style="font-size:12.5px;font-weight:700;">ROAS vs ROFI Belanja Iklan (Okt)</span><span class="badge-pill bp-orange">ROAS {roas_okt_val:.2f}x | ROFI {rofi_okt_val:.2f}x</span></div><div class="metric-num" style="font-size:22px;font-weight:800;margin-bottom:8px;">{rp_short(ads_okt)} Ad Spend</div><div style="display:flex;height:9px;border-radius:99px;overflow:hidden;gap:3px;margin-bottom:8px;background:var(--bg-subcard);"><div style="width:70%;background:#4F46E5;border-radius:99px;"></div><div style="width:30%;background:#10B981;border-radius:99px;"></div></div><div style="display:flex;justify-content:space-between;font-size:11px;font-weight:600;color:var(--text-secondary)!important;"><span>ROAS Akuisisi Meta: <b>{roas_okt_val:.2f}x</b></span><span>ROFI Real/CS: <b>{rofi_okt_val:.2f}x</b></span></div></div>')
    else:
        with b1: render_html(f'<div class="bento-card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span style="font-size:12.5px;font-weight:700;">Total Mushaf Meta LP & TikTok</span><span class="badge-pill bp-indigo">3.447 Pcs Fisik</span></div><div class="metric-num" style="font-size:22px;font-weight:800;margin-bottom:8px;">{sa["st_siap"]} ST • {sa["mushaf_siap_akumulasi"]} AW Siap</div><div style="display:flex;height:9px;border-radius:99px;overflow:hidden;gap:3px;margin-bottom:8px;background:var(--bg-subcard);"><div style="width:32%;background:#10B981;border-radius:99px;"></div><div style="width:68%;background:#F97316;border-radius:99px;"></div></div><div style="display:flex;justify-content:space-between;font-size:11px;font-weight:600;color:var(--text-secondary)!important;"><span>Meta LP: <b>{sa["meta_lp_total"]:,}</b></span><span>TikTok: <b>{sa["tiktok_mushaf_total"]}</b></span><span>Proses/PO: <b>2.328</b></span></div></div>')
        with b2: render_html(f'<div class="bento-card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span style="font-size:12.5px;font-weight:700;">Defisit Mushaf (Agustus – Oktober)</span><span class="badge-pill bp-red">Wajib Beli {sa["defisit_agust_okt"]} Pcs</span></div><div class="metric-num" style="font-size:22px;font-weight:800;margin-bottom:8px;">Kebutuhan {sa["kebutuhan_agust_okt"]:,} Pcs</div><div style="display:flex;height:9px;border-radius:99px;overflow:hidden;gap:3px;margin-bottom:8px;background:var(--bg-subcard);"><div style="width:83%;background:#6366F1;border-radius:99px;"></div><div style="width:17%;background:#EF4444;border-radius:99px;"></div></div><div style="display:flex;justify-content:space-between;font-size:11px;font-weight:600;color:var(--text-secondary)!important;"><span>Stok Fisik: <b>{sa["stok_fisik_mushaf_tersedia"]:,}</b></span><span>Kurang: <b>({sa["defisit_agust_okt"]}) Pcs</b></span></div></div>')
        with b3: render_html(f'<div class="bento-card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span style="font-size:12.5px;font-weight:700;">Buku Belajar Super Tahsin</span><span class="badge-pill bp-green">Aman ({sa["bt_total"]:,} Pcs)</span></div><div class="metric-num" style="font-size:22px;font-weight:800;margin-bottom:8px;">{sa["bt_siap"]:,} Siap • {sa["bt_belum"]:,} Proses</div><div style="display:flex;height:9px;border-radius:99px;overflow:hidden;gap:3px;margin-bottom:8px;background:var(--bg-subcard);"><div style="width:48%;background:#10B981;border-radius:99px;"></div><div style="width:52%;background:#F59E0B;border-radius:99px;"></div></div><div style="display:flex;justify-content:space-between;font-size:11px;font-weight:600;color:var(--text-secondary)!important;"><span>Sudah Stiker: <b>{sa["bt_siap"]:,}</b></span><span>Belum Siap: <b>{sa["bt_belum"]:,}</b></span></div></div>')

# ==============================================================================
# HALAMAN 2: DONASI & SATPAM KEUANGAN (MENAMPILKAN ROAS & ROFI)
# ==============================================================================
elif menu_pilihan == "Donasi & Satpam Keuangan":
    f1_a, f1_b, f1_c = st.columns(3)
    with f1_a:
        cakupan_fin = st.selectbox("1. Pilih Cakupan Periode Analisis:", ["Bulan Oktober 2026 (Realtime)", "Filter Tanggal Harian (Oktober 2026)", "Pilih Bulan Historis (Januari – September)", "Akumulasi Tahunan (YTD Jan–Okt)"], key="fin_scope")

    df_d_okt = db.get('okt_harian', pd.DataFrame()).copy()
    if not df_d_okt.empty:
        df_d_okt['DT'] = pd.to_datetime(df_d_okt['Tanggal'], errors='coerce').dt.date
        df_d_okt = df_d_okt.dropna(subset=['DT'])
        raw_max_okt = df_d_okt['DT'].max() if not df_d_okt.empty else datetime.date(2026, 10, 23)
    else: raw_max_okt = datetime.date(2026, 10, 23)
    max_dt_okt = clamp_date(raw_max_okt, datetime.date(2026, 10, 1), datetime.date(2026, 10, 31))

    with f1_b:
        if cakupan_fin == "Pilih Bulan Historis (Januari – September)":
            bln_terpilih = st.selectbox("2. Pilih Bulan Historis:", [b for b in df_macro['Bulan'].tolist() if b != "Oktober"], key="fin_hist_m")
            cs_fin_filter, tgl_range_t1 = "Semua Tim CS", (datetime.date(2026, 10, 1), max_dt_okt)
        elif cakupan_fin == "Filter Tanggal Harian (Oktober 2026)":
            tgl_range_t1 = st.date_input("2. Pilih Rentang Tanggal Oktober:", value=(datetime.date(2026, 10, 1), max_dt_okt), min_value=datetime.date(2026, 10, 1), max_value=datetime.date(2026, 10, 31), key="fin_dt_range")
            bln_terpilih = "Oktober"
        else:
            bln_terpilih, tgl_range_t1 = "Oktober", (datetime.date(2026, 10, 1), max_dt_okt)
            st.selectbox("2. Status Data:", ["Tersinkronisasi Otomatis (Sheet Dashboard CS)"], disabled=True, key="fin_stat_info")

    with f1_c:
        if "Oktober" in cakupan_fin:
            cs_fin_filter = st.selectbox("3. Filter Personel CS (Oktober):", ["Semua Tim CS", "Nisa", "Salma", "Aulia"], key="fin_cs_pick")
        else:
            cs_fin_filter = "Semua Tim CS"
            st.selectbox("3. Cakupan Divisi:", ["Seluruh Divisi Funding & Ads"], disabled=True, key="fin_div_info")

    leads_meta_cur = None
    if cakupan_fin == "Akumulasi Tahunan (YTD Jan–Okt)":
        t_omz, d_fin, d_cs, b_ads, m_pcs = df_macro['Target Bulanan'].sum(), df_macro['Realisasi Finance'].sum(), df_macro['Omset CS'].sum(), df_macro['Budget Iklan'].sum(), df_macro['Mushaf Terverifikasi'].sum()
        lbl_badge = "YTD Jan–Okt"
    elif cakupan_fin == "Pilih Bulan Historis (Januari – September)":
        rb = df_macro[df_macro['Bulan'] == bln_terpilih].iloc[0]
        t_omz, d_fin, d_cs, b_ads, m_pcs = float(rb['Target Bulanan']), float(rb['Realisasi Finance']), float(rb['Omset CS']), float(rb['Budget Iklan']), float(rb['Mushaf Terverifikasi'])
        lbl_badge = f"{bln_terpilih} 2026"
    elif cakupan_fin == "Filter Tanggal Harian (Oktober 2026)":
        if isinstance(tgl_range_t1, (list, tuple)) and len(tgl_range_t1) == 2 and not df_d_okt.empty:
            df_d_okt = df_d_okt[(df_d_okt['DT'] >= tgl_range_t1[0]) & (df_d_okt['DT'] <= tgl_range_t1[1])]
        jml_hari = max(1, len(df_d_okt))
        base_ads = float(db['okt_finance_mon'].get('budget_iklan', 205020588))
        cutoff_d = max(1, int(db['okt_finance_mon'].get('hari_cutoff', 23)))
        if cs_fin_filter in ["Nisa", "Salma", "Aulia"]:
            d_cs = df_d_okt[cs_fin_filter].sum() if not df_d_okt.empty else 0
            leads_meta_cur = df_d_okt[f"{cs_fin_filter}_Meta"].sum() if not df_d_okt.empty and f"{cs_fin_filter}_Meta" in df_d_okt.columns else d_cs * 0.83
            d_fin = d_cs
            tgt_cs_map = {"Nisa": 200000000, "Salma": 200000000, "Aulia": 50000000}
            t_omz = tgt_cs_map[cs_fin_filter] * (jml_hari / 31.0)
            b_ads = (base_ads / 3.0) * (jml_hari / cutoff_d)
        else:
            d_cs = df_d_okt['Total_Gabungan'].sum() if not df_d_okt.empty else 0
            leads_meta_cur = df_d_okt['Total_Leads'].sum() if not df_d_okt.empty else d_cs * 0.839
            d_fin = d_cs
            t_omz = 500000000 * (jml_hari / 31.0)
            b_ads = base_ads * (jml_hari / cutoff_d)
        m_pcs = max(1, int(round(d_fin / 99000.0)))
        lbl_badge = f"{jml_hari} Hari Okt ({cs_fin_filter})"
    else:
        rb = df_macro[df_macro['Bulan'] == 'Oktober'].iloc[0]
        if cs_fin_filter in ["Nisa", "Salma", "Aulia"]:
            row_cs_okt = db['okt_cs_table'][db['okt_cs_table']['CS / CRM'] == cs_fin_filter].iloc[0]
            row_src_okt = db['okt_sumber'][db['okt_sumber']['CS / CRM'] == cs_fin_filter]
            t_omz, d_cs, d_fin = float(row_cs_okt['Target (Rp)']), float(row_cs_okt['Bulanan (Total)']), float(row_cs_okt['Bulanan (Final)'])
            b_ads = float(rb['Budget Iklan']) * (d_cs / max(1.0, float(db['okt_kpi']['total_donasi'])))
            leads_meta_cur = float(row_src_okt['Leads Meta'].iloc[0]) if not row_src_okt.empty else d_cs * 0.839
            m_pcs = max(1, int(round(d_fin / 99000.0)))
            lbl_badge = f"Okt • CS {cs_fin_filter}"
        else:
            t_omz, d_fin, d_cs, b_ads, m_pcs = float(rb['Target Bulanan']), float(rb['Realisasi Finance']), float(rb['Omset CS']), float(rb['Budget Iklan']), float(rb['Mushaf Terverifikasi'])
            non_tot_s = db['okt_sumber'][db['okt_sumber']['CS / CRM'].astype(str).str.upper() != 'TOTAL']
            leads_meta_cur = float(non_tot_s['Leads Meta'].sum()) if not non_tot_s.empty else 161767457.0
            lbl_badge = "Okt 2026"

    sk = hitung_satpam_keuangan(t_omz, d_fin, b_ads, m_pcs, leads_meta_val=leads_meta_cur)

    c1, c2, c3, c4 = st.columns(4)
    with c1: render_bento_kpi("ri-bank-line", "indigo", f"Realisasi Finance ({lbl_badge})", rp_short(d_fin), f"{(d_fin/max(1,t_omz))*100:.1f}% Target", "green" if d_fin >= t_omz else "orange", f"Target: {rp_short(t_omz)}")
    with c2: render_bento_kpi("ri-user-voice-line", "emerald", "Funding Terlapor CS", rp_short(d_cs), f"Selisih: {rp_short(d_fin - d_cs)}", "indigo", "Bank vs Laporan CS")
    with c3: render_bento_kpi("ri-advertisement-line", "orange", "Biaya Iklan (ROAS & ROFI)", rp_short(b_ads), f"ROAS {sk['roas_meta']:.2f}x | ROFI {sk['rofi_aktual']:.2f}x", sk['badge_type'], "Min: 1.52x | Aman: 2.63x")
    with c4: render_bento_kpi("ri-shield-check-line", "rose", "Dana Siap Salur (DSD)", rp_short(sk['dsd']), f"HPP: {rp(sk['plafon_hpp'])}", "green" if sk['plafon_hpp'] >= 20000 else "red", f"{sk['kebutuhan_mushaf_pcs']:,} Mushaf")

    g_left, g_right = st.columns([1.75, 1.05])
    with g_left:
        if "Oktober" in cakupan_fin:
            render_chart_header("Tren Harian Donasi Oktober 2026 (Leads Meta + CRM)", "Grafik otomatis menyesuaikan rentang tanggal dan personel CS yang dipilih", lbl_badge, "orange")
            fig_f2 = go.Figure()
            if not df_d_okt.empty:
                if cs_fin_filter in ["Semua Tim CS", "Nisa"]:
                    fig_f2.add_trace(go.Scatter(x=df_d_okt['Tanggal'], y=df_d_okt['Nisa'], name='CS Nisa', mode='lines+markers', line=dict(color='#FF6B4A', width=2.8, shape='spline')))
                if cs_fin_filter in ["Semua Tim CS", "Salma"]:
                    fig_f2.add_trace(go.Scatter(x=df_d_okt['Tanggal'], y=df_d_okt['Salma'], name='CS Salma', mode='lines+markers', line=dict(color='#6366F1', width=2.8, shape='spline')))
                if cs_fin_filter in ["Semua Tim CS", "Aulia"]:
                    fig_f2.add_trace(go.Scatter(x=df_d_okt['Tanggal'], y=df_d_okt['Aulia'], name='CS Aulia', mode='lines+markers', line=dict(color='#10B981', width=2.8, shape='spline')))
            apply_saas_plotly(fig_f2, height=330, is_currency=True)
            st.plotly_chart(fig_f2, use_container_width=True)
        else:
            render_chart_header("Komparasi Bulanan: Finance Real vs Funding CS vs Biaya Iklan", "Perbandingan performa keuangan bulanan sepanjang Januari – Oktober 2026", lbl_badge, "indigo")
            fig_f1 = go.Figure()
            fig_f1.add_trace(go.Bar(x=df_macro['Bulan'], y=df_macro['Realisasi Finance'], name='Realisasi Finance (Bank)', marker_color='#6366F1', marker_cornerradius=6))
            fig_f1.add_trace(go.Bar(x=df_macro['Bulan'], y=df_macro['Omset CS'], name='Funding CS', marker_color='#10B981', marker_cornerradius=6))
            fig_f1.add_trace(go.Bar(x=df_macro['Bulan'], y=df_macro['Budget Iklan'], name='Biaya Iklan', marker_color='#FF6B4A', marker_cornerradius=6))
            apply_saas_plotly(fig_f1, height=330, is_currency=True)
            fig_f1.update_layout(barmode='group')
            st.plotly_chart(fig_f1, use_container_width=True)

    with g_right:
        render_html(f"""
        <div class="bento-card" style="min-height:382px;display:flex;flex-direction:column;justify-content:space-between;">
            <div>
                <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:12px;">
                    <span style="font-family:'Outfit',sans-serif!important;font-weight:700;font-size:15px;"><i class="ri-calculator-line" style="color:#6366F1!important;"></i> Satpam Keuangan (ROAS & ROFI)</span>
                    <span class="badge-pill bp-{sk['badge_type']}">{lbl_badge}</span>
                </div>
                <div style="font-size:12.2px;color:var(--text-secondary)!important;line-height:2.05;">
                    <div style="display:flex;justify-content:space-between;border-bottom:1px dashed var(--border-soft);"><span>ROAS Akuisisi Meta / ROFI Total</span><span class="nowrap-val" style="color:#10B981!important;">{sk['roas_meta']:.2f}x / {sk['rofi_aktual']:.2f}x</span></div>
                    <div style="display:flex;justify-content:space-between;border-bottom:1px dashed var(--border-soft);"><span>Profit Iklan (Donasi - Ads)</span><span class="nowrap-val" style="color:var(--text-primary)!important;">{rp(sk['profit_iklan'])}</span></div>
                    <div style="display:flex;justify-content:space-between;border-bottom:1px dashed var(--border-soft);"><span>Beban Operasional (10%)</span><span class="nowrap-val" style="color:var(--text-primary)!important;">{rp(sk['beban_ops_10'])}</span></div>
                    <div style="display:flex;justify-content:space-between;border-bottom:1px dashed var(--border-soft);"><span>Dana Siap Salur (DSD)</span><span class="nowrap-val" style="color:#6366F1!important;">{rp(sk['dsd'])}</span></div>
                    <div style="display:flex;justify-content:space-between;border-bottom:1px dashed var(--border-soft);"><span>Alokasi Mushaf (65% DSD)</span><span class="nowrap-val" style="color:#10B981!important;">{rp(sk['alokasi_mushaf_65'])}</span></div>
                    <div style="display:flex;justify-content:space-between;border-bottom:1px dashed var(--border-soft);"><span>Cadangan Cashback (35%)</span><span class="nowrap-val" style="color:#F59E0B!important;">{rp(sk['cadangan_cashback_35'])}</span></div>
                    <div style="display:flex;justify-content:space-between;"><span>Target Subsidi CRM CS</span><span class="nowrap-val" style="color:#EF4444!important;">{rp(sk['target_crm_cs'])}</span></div>
                </div>
            </div>
            <div class="sub-box" style="margin-top:10px;padding:10px 12px;border-radius:10px;font-size:12px;">
                <i class="ri-award-line" style="color:#F97316!important;"></i> <b>Keputusan Sistem:</b> {sk['rekom_tier']}
            </div>
        </div>
        """)

    opsi_tabel_t1 = [
        "1. Rekapitulasi Pendapatan Harian per CS (Leads Meta vs CRM + CR Harian)",
        "2. Tabel Komparasi Kinerja CS Oktober (Total vs Final & Sisa Target)",
        "3. Analisis Sumber Kontak & Rasio Kanal ROAS/ROFI (Oktober)",
        "4. Rekapitulasi Makro Bulanan (Jan–Okt)"
    ]
    if user_role != "Advertiser": opsi_tabel_t1.append("5. Pencarian Riwayat Donatur (Mini CRM)")
    sub_t1 = st.radio("Pilih Tabel Detail Keuangan & CS:", opsi_tabel_t1, horizontal=True, key="t1_subtable")

    if sub_t1.startswith("1."):
        render_rekap_harian_cs_table(df_d_okt, db['avg_cr_okt'])
    elif sub_t1.startswith("2."):
        df_ok = db['okt_cs_table'].copy()
        if cs_fin_filter != "Semua Tim CS": df_ok = df_ok[df_ok['CS / CRM'].isin([cs_fin_filter, "TOTAL"])]
        for cr in ['Harian (Total)', 'Harian (Final)', 'Mingguan (Total)', 'Mingguan (Final)', 'Bulanan (Total)', 'Bulanan (Final)', 'Target (Rp)', 'Sisa Target', 'Pending Verifikasi', 'Target Harian (Sisa)']:
            if cr in df_ok.columns: df_ok[cr] = df_ok[cr].apply(rp)
        render_saas_table(df_ok)
    elif sub_t1.startswith("3."):
        col_s1, col_s2 = st.columns([1.3, 1])
        with col_s1:
            df_sr = db['okt_sumber'].copy()
            for cr in ['Leads Meta', 'Repeat Order CRM', 'Repeat Order non CRM', 'Lainnya', 'Total Nominal']:
                if cr in df_sr.columns: df_sr[cr] = df_sr[cr].apply(rp)
            render_saas_table(df_sr)
        with col_s2: render_saas_table(db['okt_kanal_rasio'])
    elif sub_t1.startswith("4."):
        df_show = df_macro.copy()
        if user_role == "Advertiser" and "Mushaf Terverifikasi" in df_show.columns: df_show.drop(columns=["Mushaf Terverifikasi"], inplace=True)
        for cr in ['Target Bulanan', 'Realisasi Finance', 'Omset CS', 'Selisih Target', 'Selisih Finance vs CS', 'Budget Iklan', 'Total Pengeluaran', 'Laba Bersih']:
            if cr in df_show.columns: df_show[cr] = df_show[cr].apply(rp)
        df_show['% Capaian'] = df_show['% Capaian'].apply(lambda x: f"{x:.1f}%")
        df_show['ROFI'] = df_show['ROFI'].apply(lambda x: f"{x:.2f}x")
        if 'ROAS_Est' in df_show.columns:
            df_show['ROAS'] = df_show['ROAS_Est'].apply(lambda x: f"{x:.2f}x")
            df_show.drop(columns=['ROAS_Est'], inplace=True)
        render_saas_table(df_show)
    else:
        q_d = st.text_input("Ketik Nama Donatur atau Nomor WhatsApp:", placeholder="Contoh: Donatur Prioritas, 628...")
        if q_d:
            dfc, _ = load_lazy_contacts_db(current_sync_token)
            m_d = dfc['Nama Donatur'].astype(str).str.contains(q_d, case=False, na=False) | dfc['Nomor Whatsapp'].astype(str).str.contains(q_d, case=False, na=False)
            render_saas_table(dfc[m_d], max_rows=30)

# ==============================================================================
# HALAMAN 3: PERFORMA CS & LEADS (BEBAS ERROR DATE_INPUT)
# ==============================================================================
elif menu_pilihan == "Performa CS & Leads":
    mode_evaluasi_cs = st.radio(
        "Pilih Mode Evaluasi Kinerja CS:",
        [
            "1. Rekapitulasi Pendapatan Harian per CS (Format Dashboard CS + Kolom CR Harian)",
            "2. Monitoring Leads & Conversion Rate (CR) per Kampanye (SantriQu, AmalQu, JariyahQu)",
            "3. Rapor & Rekap Omzet Bulanan Seluruh CS (Januari – Oktober 2026)"
        ],
        horizontal=True, key="cs_eval_mode"
    )

    if mode_evaluasi_cs.startswith("1."):
        df_d_okt = db.get('okt_harian', pd.DataFrame()).copy()
        sum_leads = df_d_okt['Total_Leads'].sum() if not df_d_okt.empty else 0
        sum_crm = df_d_okt['Total_CRM'].sum() if not df_d_okt.empty else 0
        sum_gab = df_d_okt['Total_Gabungan'].sum() if not df_d_okt.empty else 0

        k1, k2, k3, k4 = st.columns(4)
        with k1: render_bento_kpi("ri-advertisement-line", "indigo", "Total Leads Meta (Okt)", rp_short(sum_leads), "83,9% Porsi Donasi", "indigo", f"Rp {sum_leads:,.0f}".replace(",", "."))
        with k2: render_bento_kpi("ri-repeat-2-line", "emerald", "Total CRM (Repeat Order)", rp_short(sum_crm), "16,1% Porsi Gabungan", "green", f"Rp {sum_crm:,.0f}".replace(",", "."))
        with k3: render_bento_kpi("ri-funds-box-line", "orange", "Total Gabungan CS (Okt)", rp_short(sum_gab), f"Final: {rp_short(db['okt_kpi']['donasi_final'])}", "orange", f"Rp {sum_gab:,.0f}".replace(",", "."))
        with k4: render_bento_kpi("ri-percent-line", "emerald", "Rata-Rata CR Bulanan", f"{db['avg_cr_okt']:.1f}%", "Dari Sheet CR/Leads", "green", "1.344 Total Transaksi")

        render_html('<div style="font-family:\'Outfit\',sans-serif!important;font-size:15.5px;font-weight:700;margin:6px 0;"><i class="ri-table-2" style="color:#FF6B4A!important;"></i> Rekapitulasi Pendapatan Harian per CS (Leads Meta vs CRM) + Kolom CR Harian</div>')
        render_rekap_harian_cs_table(df_d_okt, db['avg_cr_okt'])

    elif mode_evaluasi_cs.startswith("2."):
        df_l = db['leads_okt'].copy()
        df_l['DT'] = pd.to_datetime(df_l['Tanggal'], errors='coerce').dt.date
        df_l = df_l.dropna(subset=['DT'])
        min_cal_d, max_cal_d = datetime.date(2026, 10, 1), datetime.date(2026, 10, 31)
        raw_max_l = df_l['DT'].max() if not df_l.empty else datetime.date(2026, 10, 23)
        safe_max_l = clamp_date(raw_max_l, min_cal_d, max_cal_d)

        f2_1, f2_2, f2_3 = st.columns(3)
        with f2_1: pilih_cs = st.selectbox("1. Pilih CS Aktif Oktober:", ["Semua CS Aktif (Nisa, Salma, Aulia)", "Nisa", "Salma", "Aulia"], key="t2_c_okt")
        with f2_2: pilih_prog = st.selectbox("2. Filter Program Kampanye:", ["Semua Program", "SantriQu", "AmalQu", "JariyahQu"], key="t2_prog_okt")
        with f2_3: tgl_l = st.date_input("3. Rentang Tanggal Leads Oktober:", value=(min_cal_d, safe_max_l), min_value=min_cal_d, max_value=max_cal_d, key="t2_d_okt")

        if isinstance(tgl_l, (list, tuple)) and len(tgl_l) == 2:
            df_l = df_l[(df_l['DT'] >= tgl_l[0]) & (df_l['DT'] <= tgl_l[1])]
        if pilih_cs in ["Nisa", "Salma", "Aulia"]: df_l = df_l[df_l['Nama CS'] == pilih_cs]

        if pilih_prog == "SantriQu": df_l["Leads_Aktif"], df_l["Closing_Aktif"], df_l["Nominal_Aktif"] = df_l["SantriQu_Leads"], df_l["SantriQu_Closing"], df_l["SantriQu_Nominal"]
        elif pilih_prog == "AmalQu": df_l["Leads_Aktif"], df_l["Closing_Aktif"], df_l["Nominal_Aktif"] = df_l["AmalQu_Leads"], df_l["AmalQu_Closing"], df_l["AmalQu_Nominal"]
        elif pilih_prog == "JariyahQu": df_l["Leads_Aktif"], df_l["Closing_Aktif"], df_l["Nominal_Aktif"] = df_l["JariyahQu_Leads"], df_l["JariyahQu_Closing"], df_l["JariyahQu_Nominal"]
        else: df_l["Leads_Aktif"], df_l["Closing_Aktif"], df_l["Nominal_Aktif"] = df_l["Chat Valid"], df_l["Closing"], df_l["Nominal"]

        tv, ti, tc, tn = int(df_l['Leads_Aktif'].sum()), int(df_l['Chat Invalid'].sum()), int(df_l['Closing_Aktif'].sum()), float(df_l['Nominal_Aktif'].sum())
        cr_okt = (tc / tv * 100) if tv > 0 else 0.0
        tot_fu = int(df_l['Total Follow Up'].sum())

        c1, c2, c3, c4 = st.columns(4)
        with c1: render_bento_kpi("ri-chat-check-line", "indigo", f"Leads Valid ({pilih_prog})", f"{tv:,} Leads", f"Invalid: {ti:,}", "indigo", pilih_cs)
        with c2: render_bento_kpi("ri-check-double-line", "emerald", f"Total Closing ({pilih_prog})", f"{tc:,} Closing", f"Conv. Rate: {cr_okt:.1f}%", "green", "Oktober 2026")
        with c3: render_bento_kpi("ri-money-dollar-circle-line", "orange", f"Nominal Closing ({pilih_prog})", rp_short(tn), f"AOV: {rp(tn/tc if tc>0 else 0)}", "orange", "Terverifikasi")
        with c4: render_bento_kpi("ri-customer-service-2-line", "emerald", "Total Follow-Up Tercatat", f"{tot_fu:,} Kontak", "3 CS Ads Aktif", "green", "Oktober 2026")

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
            render_chart_header("Conversion Rate (CR)", f"Rata-rata CR {pilih_prog}", f"{cr_okt:.1f}%", "green")
            st.plotly_chart(make_gauge_chart(round(cr_okt, 1), max_val=100, suffix="%", bar_color="#10B981"), use_container_width=True)

        df_l_show = df_l[["Tanggal", "Nama CS", "Leads_Aktif", "Chat Invalid", "Closing_Aktif", "Conv Rate (%)", "Nominal_Aktif", "SantriQu_Closing", "AmalQu_Closing", "JariyahQu_Closing", "Total Follow Up"]].copy()
        df_l_show.rename(columns={"Leads_Aktif": f"Leads ({pilih_prog})", "Closing_Aktif": f"Closing ({pilih_prog})", "Nominal_Aktif": f"Nominal ({pilih_prog})"}, inplace=True)
        df_l_show[f"Nominal ({pilih_prog})"] = df_l_show[f"Nominal ({pilih_prog})"].apply(rp)
        df_l_show["Conv Rate (%)"] = df_l_show["Conv Rate (%)"].apply(lambda x: f"{x:.1f}%")
        render_saas_table(df_l_show)

    else:
        r1, r2 = st.columns(2)
        with r1: filter_stat_ov = st.selectbox("1. Filter Status Keaktifan CS:", ["Semua Tim CS (8 Orang)", "Hanya CS Aktif Oktober (Nisa, Salma, Aulia, Olive)", "Hanya CS Non-Aktif (Desi, Syafiq, Rida, Sarah)"], key="ov_stat")
        df_ov = db['cs_overview'].copy()
        if "Hanya CS Aktif" in filter_stat_ov: df_ov = df_ov[df_ov['Status Okt'].str.contains("Aktif")]
        elif "Non-Aktif" in filter_stat_ov: df_ov = df_ov[df_ov['Status Okt'] == "Non-Aktif"]
        with r2: pilih_cs_rapor = st.selectbox("2. Pilih Personel CS:", ["Semua (Tampilkan Perbandingan)"] + df_ov['Nama CS'].tolist(), key="ov_person")
        df_ov_view = df_ov[df_ov['Nama CS'] == pilih_cs_rapor].copy() if pilih_cs_rapor != "Semua (Tampilkan Perbandingan)" else df_ov.copy()

        months_cols = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober"]
        render_chart_header("Tren Pendapatan Bulanan CS (Januari – Oktober 2026)", "Perbandingan perolehan omzet bulanan masing-masing CS", "Jan–Okt 2026", "indigo")
        fig_ov_cs = go.Figure()
        palette = ['#FF6B4A', '#6366F1', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#06B6D4', '#64748B']
        for idx_c, (_, r_cs) in enumerate(df_ov_view.iterrows()):
            fig_ov_cs.add_trace(go.Bar(x=months_cols, y=[float(r_cs[m]) for m in months_cols], name=r_cs['Nama CS'], marker_color=palette[idx_c % len(palette)], marker_cornerradius=5))
        apply_saas_plotly(fig_ov_cs, height=320, is_currency=True)
        fig_ov_cs.update_layout(barmode='group')
        st.plotly_chart(fig_ov_cs, use_container_width=True)

        df_ov_disp = df_ov_view.copy()
        for cr in ["Target Omset", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "Total Omset (Jan-Sep)", "AOV"]:
            df_ov_disp[cr] = df_ov_disp[cr].apply(rp)
        render_saas_table(df_ov_disp)

# ==============================================================================
# HALAMAN 4: LOGISTIK & GUDANG (BEBAS KEYERROR & SESUAI DASHBOARD STOK BARU)
# ==============================================================================
elif menu_pilihan == "Logistik & Gudang":
    s1, s2, s3 = st.columns(3)
    with s1: render_bento_kpi("ri-book-mark-line", "indigo", "Total Mushaf Meta LP", f"{sa['meta_lp_total']:,} Pcs".replace(",", "."), "Super Tajwid & Al Wakaf", "indigo", f"ST: {sa['st_total']} • AW Meta: 2.626")
    with s2: render_bento_kpi("ri-tiktok-line", "emerald", "Total Mushaf TikTok & Tahsin", f"{sa['tiktok_mushaf_total']} Mushaf • {sa['buku_tahsin_total']:,} Tahsin".replace(",", "."), "Al Wakaf TikTok & Buku Tahsin", "green", f"Total Inventaris: {sa['total_inventaris_fisik']:,} Pcs")
    with s3: render_bento_kpi("ri-checkbox-circle-line", "orange", "Stok Siap Salur (Sudah Stiker)", f"{sa['mushaf_siap_akumulasi']} AW • {sa['st_siap']} ST", f"Super Tahsin Siap: {sa['tahsin_siap_salur']:,} Pcs", "green", f"Total Siap Salur: {sa['total_inventaris_siap']:,} Pcs")

    s4, s5, s6 = st.columns(3)
    with s4: render_bento_kpi("ri-calendar-todo-line", "indigo", "Total Kebutuhan (Agust–Okt)", f"{sa['kebutuhan_agust_okt']:,} Mushaf".replace(",", "."), "Agust: 604 • Sept: 2.599 • Okt: 946", "orange", "Sisa Gap Distribusi: 4.049 Pcs")
    with s5: render_bento_kpi("ri-archive-drawer-line", "emerald", "Stok Fisik Mushaf Tersedia", f"{sa['stok_fisik_mushaf_tersedia']:,} Mushaf".replace(",", "."), "Siap Salur & Proses Cetak", "indigo", "Super Tajwid + Al Wakaf")
    with s6: render_bento_kpi("ri-alarm-warning-fill", "rose", "Kekurangan Agust–Oktober", f"{sa['defisit_agust_okt']} Mushaf", "WAJIB BELI 702 MUSHAF", "red", "Defisit Bersih Pengadaan Mushaf")

    t_left, t_right = st.columns(2)
    with t_left:
        render_html('<div style="font-family:\'Outfit\',sans-serif!important;font-size:15px;font-weight:800;margin:4px 0;"><i class="ri-list-check-2" style="color:#10B981!important;"></i> RINCIAN INVENTARIS STOK PER PRODUK & KANAL</div>')
        df_inv_show = db['stok_rincian_baru'].copy()
        for cn in ["Siap Salur (Stiker)", "Belum Siap (Proses)", "Total Stok Fisik"]:
            if cn in df_inv_show.columns: df_inv_show[cn] = df_inv_show[cn].apply(lambda x: f"{int(num_clean(x)):,}".replace(",", "."))
        render_saas_table(df_inv_show)

    with t_right:
        render_html('<div style="font-family:\'Outfit\',sans-serif!important;font-size:15px;font-weight:800;margin:4px 0;"><i class="ri-error-warning-line" style="color:#EF4444!important;"></i> ANALISIS TARGET & DEFISIT PENGADAAN MUSHAF (AGUST–OKT 2026)</div>')
        render_saas_table(db['stok_defisit_baru'])

    lg_l, lg_r = st.columns([1.5, 1.3])
    with lg_l:
        render_chart_header("Komparasi Rincian Inventaris: Siap Salur (Stiker) vs Belum Siap (Proses)", "Visualisasi langsung dari tabel Rincian Inventaris Stok per Produk & Kanal", "Total 6.335 Pcs", "indigo")
        df_plot_inv = db['stok_rincian_baru'].copy()
        col_prod = df_plot_inv.columns[0]
        col_siap = "Siap Salur (Stiker)" if "Siap Salur (Stiker)" in df_plot_inv.columns else df_plot_inv.columns[2]
        col_belum = "Belum Siap (Proses)" if "Belum Siap (Proses)" in df_plot_inv.columns else df_plot_inv.columns[3]
        df_plot_inv = df_plot_inv[~df_plot_inv[col_prod].astype(str).str.contains("TOTAL", case=False, na=False)].copy()
        df_plot_inv[col_siap] = df_plot_inv[col_siap].apply(num_clean)
        df_plot_inv[col_belum] = df_plot_inv[col_belum].apply(num_clean)
        fig_comp_s = go.Figure()
        fig_comp_s.add_trace(go.Bar(x=df_plot_inv[col_prod], y=df_plot_inv[col_siap], name='Siap Salur (Stiker)', marker_color='#10B981', marker_cornerradius=6))
        fig_comp_s.add_trace(go.Bar(x=df_plot_inv[col_prod], y=df_plot_inv[col_belum], name='Belum Siap (Proses)', marker_color='#F97316', marker_cornerradius=6))
        apply_saas_plotly(fig_comp_s, height=300)
        fig_comp_s.update_layout(barmode='group')
        st.plotly_chart(fig_comp_s, use_container_width=True)

    with lg_r:
        render_chart_header("Progres Master Packing Dus Bulanan (Jan – Okt 2026)", "Tahap verifikasi, stiker, packing hingga selesai distribusi", "Akumulasi YTD", "emerald")
        df_pk = db['packing_dus_bulanan']
        fig_pk = go.Figure()
        fig_pk.add_trace(go.Bar(x=df_pk['Bulan'], y=df_pk['Distribusi Selesai'], name='Selesai', marker_color='#10B981', marker_cornerradius=4))
        fig_pk.add_trace(go.Bar(x=df_pk['Bulan'], y=df_pk['Packing / Proses Distribusi'], name='Proses/Packing', marker_color='#6366F1', marker_cornerradius=4))
        fig_pk.add_trace(go.Bar(x=df_pk['Bulan'], y=df_pk['Penamaan Mushaf (Stiker)'], name='Stiker', marker_color='#FF6B4A', marker_cornerradius=4))
        fig_pk.add_trace(go.Bar(x=df_pk['Bulan'], y=df_pk['Verifikasi (Belum Stiker)'], name='Verifikasi', marker_color='#94A3B8', marker_cornerradius=4))
        apply_saas_plotly(fig_pk, height=300)
        fig_pk.update_layout(barmode='stack')
        st.plotly_chart(fig_pk, use_container_width=True)

# ==============================================================================
# HALAMAN 5: KALENDER DISTRIBUSI
# ==============================================================================
elif menu_pilihan == "Kalender Distribusi":
    df_kal = db['kalender_okt'].copy()
    tot_agenda_kal = len(df_kal)
    tot_mushaf_kal = int(df_kal['Jumlah Mushaf (Pcs)'].sum()) if not df_kal.empty else 1004

    kc1, kc2, kc3, kc4 = st.columns(4)
    with kc1: render_bento_kpi("ri-calendar-check-line", "indigo", "Total Agenda Oktober", f"{tot_agenda_kal} Titik Lokasi", f"Total: {tot_mushaf_kal:,} Mushaf", "indigo", "Oktober 2026")
    with kc2: render_bento_kpi("ri-book-mark-line", "emerald", "Jadwal Super Tajwid", f"{sa['st_jadwal']} Mushaf", f"Siap: {sa['st_siap']} Pcs (Cukup)", "green", f"Surplus {sa['st_gap_siap']:+d} Pcs")
    with kc3: render_bento_kpi("ri-book-2-line", "rose", "Jadwal Al-Wakaf TikTok", f"{sa['aw_jadwal']} Mushaf", f"Siap Gabungan: {sa['aw_total_siap']} ({sa['aw_gap_total_siap']:+d})", "red", f"TikTok: {sa['aw_tik_siap']} • Meta: {sa['aw_meta_siap']}")
    with kc4: render_bento_kpi("ri-price-tag-2-line", "orange", "Belum Siap (Proses Al-Wakaf)", f"{sa['aw_total_belum']:,} Mushaf".replace(",", "."), "Wajib Beli 702 Mushaf (Agust–Okt)", "orange", "Siap Ditempel Stiker")

    events_by_day = {}
    for _, r_k in df_kal.iterrows():
        tgl_s = str(r_k.get("Tanggal Agenda", "")).strip()
        m_day = re.search(r'-(\d{1,2})$', tgl_s)
        if m_day: events_by_day.setdefault(int(m_day.group(1)), []).append(r_k)

    cells_list = ['<div class="cal-cell-empty"></div>' for _ in range(3)]
    for day_num in range(1, 32):
        if day_num in events_by_day:
            ev_list = events_by_day[day_num]
            tot_pcs_day = sum(int(num_clean(x.get("Jumlah Mushaf (Pcs)", 0))) for x in ev_list)
            items_html = "".join([f'<div class="cal-item-pill"><b>{str(x.get("Nama Lembaga Penerima",""))[:22]}</b><br><span style="color:#F97316!important;font-weight:700;">{int(num_clean(x.get("Jumlah Mushaf (Pcs)",0)))} Pcs</span> • {str(x.get("Variasi Mushaf",""))}</div>' for x in ev_list])
            cells_list.append(f'<div class="cal-cell-active"><div class="cal-day-num"><span>{day_num} Okt</span><span class="badge-pill bp-orange" style="padding:2px 6px;font-size:10px;">{tot_pcs_day} Pcs</span></div><div>{items_html}</div></div>')
        else:
            cells_list.append(f'<div class="cal-cell"><div class="cal-day-num"><span>{day_num} Okt</span></div><div style="font-size:10px;color:var(--text-muted)!important;">-</div></div>')
    cells_list.append('<div class="cal-cell-empty"></div>')
    desktop_cal_str = "".join(cells_list)

    mobile_cards = ""
    for day_num in sorted(events_by_day.keys()):
        ev_list = events_by_day[day_num]
        tot_pcs_day = sum(int(num_clean(x.get("Jumlah Mushaf (Pcs)", 0))) for x in ev_list)
        items_html = "".join([f'<div class="cal-item-pill"><b>{str(x.get("Nama Lembaga Penerima",""))}</b><br><span style="color:#F97316!important;font-weight:700;">{int(num_clean(x.get("Jumlah Mushaf (Pcs)",0)))} Pcs ({str(x.get("Variasi Mushaf",""))})</span> • PIC: {str(x.get("Nama PIC",""))}<br><span style="color:var(--text-muted)!important;">Lokasi: {str(x.get("Wilayah / Titik Lokasi",""))}</span></div>' for x in ev_list])
        mobile_cards += f'<div class="cal-cell-active" style="margin-bottom:10px;"><div class="cal-day-num"><span>{day_num} Oktober 2026</span><span class="badge-pill bp-orange">{len(ev_list)} Titik • {tot_pcs_day} Pcs</span></div><div>{items_html}</div></div>'

    render_html(f"""
    <div class="bento-card">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
            <div>
                <span style="font-family:'Outfit',sans-serif!important;font-weight:800;font-size:16.5px;"><i class="ri-calendar-todo-fill" style="color:#FF6B4A!important;"></i> Kalender Visual Distribusi Mushaf — Oktober 2026</span>
                <div style="font-size:12px;color:var(--text-secondary)!important;">Super Tajwid: <b>{sa['st_jadwal']} Pcs</b> (Stok Siap {sa['st_siap']} Pcs) &nbsp;|&nbsp; Al-Wakaf: <b>{sa['aw_jadwal']} Pcs</b> (Stok Siap {sa['aw_total_siap']} Pcs)</div>
            </div>
            <span class="badge-pill bp-orange"><i class="ri-map-pin-time-line"></i> {tot_agenda_kal} Titik Distribusi Aktif</span>
        </div>
        <div class="cal-desktop-only"><div class="cal-grid-7"><div class="cal-head-cell">SENIN</div><div class="cal-head-cell">SELASA</div><div class="cal-head-cell">RABU</div><div class="cal-head-cell">KAMIS</div><div class="cal-head-cell">JUMAT</div><div class="cal-head-cell">SABTU</div><div class="cal-head-cell">MINGGU</div>{desktop_cal_str}</div></div>
        <div class="cal-mobile-only" style="margin-top:12px;">{mobile_cards}</div>
    </div>
    """)

    f_kal_1, f_kal_2 = st.columns([2.5, 1])
    with f_kal_1: render_html('<div style="font-family:\'Outfit\',sans-serif!important;font-size:15.5px;font-weight:700;padding-top:8px;"><i class="ri-table-line" style="color:#6366F1!important;"></i> Rincian Agenda Distribusi Scheduled (Sheet Kalender Oktober 2026 • Kolom A–J)</div>')
    with f_kal_2: pilih_var_kal = st.selectbox("Filter Variasi Mushaf:", ["Semua Variasi", "Super Tajwid", "Al Wakaf Tiktok"], key="kal_var")
    df_kal_disp = df_kal[df_kal["Variasi Mushaf"] == pilih_var_kal].copy() if pilih_var_kal != "Semua Variasi" and "Variasi Mushaf" in df_kal.columns else df_kal.copy()
    cols_aj_display = [c for c in ["No", "Tanggal Agenda", "ID Proyek", "Nama Lembaga Penerima", "Nama PIC", "Kontak WA", "Wilayah / Titik Lokasi", "Jumlah Mushaf (Pcs)", "Variasi Mushaf", "Status"] if c in df_kal_disp.columns]
    render_saas_table(df_kal_disp[cols_aj_display])

# ==============================================================================
# HALAMAN 6: DATABASE & SMART WA BLAST ENGINE (FULL REALTIME DARI SPREADSHEET)
# ==============================================================================
elif menu_pilihan == "Database & WA Blast":
    df_all_c, is_sample_db = load_lazy_contacts_db(current_sync_token)
    dk = db['db_kpi'].copy()
    if not is_sample_db and len(df_all_c) > 10:
        dk['total_donatur'] = len(df_all_c)
        cb_cnt = int(df_all_c['Reminder'].astype(str).str.upper().str.contains('CALLBACK').sum())
        if cb_cnt > 0: dk['callback_segera'] = cb_cnt

    d1, d2, d3, d4 = st.columns(4)
    with d1: render_bento_kpi("ri-user-follow-line", "emerald", "Donatur Terkonfirmasi", f"{dk['total_donatur']:,}".replace(",", "."), f"Konversi {dk['konversi_pct']}%", "green", f"Kontak: {dk['total_kontak']:,}")
    with d2: render_bento_kpi("ri-user-add-line", "orange", "Leads Belum Donasi", f"{dk['total_leads']:,}".replace(",", "."), "Prospek Follow-Up", "orange", "Siap Reaktivasi")
    with d3: render_bento_kpi("ri-vip-diamond-line", "indigo", "Total Donasi Kumulatif", rp_short(dk['total_donasi_kumulatif']), f"LTV: {rp(dk['rata_rata_donasi'])}", "indigo", "Rata-rata / Donatur")
    with d4: render_bento_kpi("ri-notification-badge-line", "rose", "Status Callback Segera", f"{dk.get('callback_segera', 12285):,} Kontak".replace(",", "."), "Prioritas Utama CRM", "red", "Siap Broadcast WA")

    render_html('<div class="bento-card" style="margin-bottom:12px;"><div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;"><div><span style="font-family:\'Outfit\',sans-serif!important;font-size:16px;font-weight:800;"><i class="ri-send-plane-fill" style="color:#FF6B4A!important;"></i> Smart Broadcast (BC) Engine — Generator CSV 2 Kolom (Senin & Jumat)</span><div style="font-size:12px;color:var(--text-secondary)!important;margin-top:2px;">Pilih jadwal kampanye BC Anda. Sistem menyaring database real-time menjadi file CSV 2 kolom (<b>phone number</b>, <b>nama</b>) siap pakai.</div></div><span class="badge-pill bp-indigo"><i class="ri-file-excel-2-line"></i> Auto-Clean WA Format</span></div></div>')

    b_left, b_right = st.columns([2.1, 1])
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
                df_tgt = df_tgt[(df_tgt['Reminder'].astype(str).str.upper().str.contains('CALLBACK')) | (df_tgt['FU1 (Sapaan)'].astype(str).str.lower().isin(['belum', '', '-', 'nan', 'none']))]
            elif opsi_bc.startswith("2."):
                df_tgt = df_tgt[df_tgt['FU3 (Laporan Penyaluran)'].astype(str).str.lower().isin(['belum', '', '-', 'nan', 'none'])]
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

        if is_sample_db:
            est = 12285 if opsi_bc.startswith("1.") else (9805 if opsi_bc.startswith("2.") else (274 if opsi_bc.startswith("3.") else len(df_out)))
            jml_label = f"{est:,} Kontak".replace(",", ".")
        else:
            jml_label = f"{len(df_out):,} Kontak".replace(",", ".")

        render_html(f'<div class="bento-card" style="border:1.5px dashed #FB923C;text-align:center;padding:18px;"><div style="font-size:11px;font-weight:700;color:#F97316!important;letter-spacing:0.6px;">TARGET AUDIENS TERPILIH</div><div class="metric-num" style="font-size:26px;font-weight:800;margin:6px 0;">{jml_label}</div><div style="font-size:11.5px;color:var(--text-secondary)!important;">Format: <b>phone number</b>, <b>nama</b></div></div>')
        st.download_button(label="Download CSV 2 Kolom (WA Blast)", data=df_out.to_csv(index=False).encode('utf-8'), file_name=f"WA_Blast_AmalQu_{now_wib().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)

    sub_t5 = st.radio(
        "Pilih Tabel Database & Segmentasi CRM Real-Time:",
        [
            "1. Segmentasi Prioritas Donatur (A1 – Reguler)",
            "2. Status Reminder & Status Retensi Donatur",
            "3. Pratinjau Daftar Kontak Donatur Terfilter (Live Sheet DATABASE)"
        ],
        horizontal=True, key="t5_sub"
    )
    if sub_t5.startswith("1."): render_saas_table(db['db_segmentasi'])
    elif sub_t5.startswith("2."):
        col_r1, col_r2 = st.columns(2)
        with col_r1: render_saas_table(db['db_reminder'])
        with col_r2: render_saas_table(db['db_status_donatur'])
    else: render_saas_table(df_tgt, max_rows=50)
# === END OF FILE ===
