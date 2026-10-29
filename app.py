import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import re, io, json, datetime, time, urllib.request
from datetime import timezone, timedelta
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(
    page_title="AmalQu — Yayasan AmalQu Indonesia Peduli",
    page_icon="https://cdn.jsdelivr.net/npm/remixicon@4.2.0/icons/Finance/funds-box-fill.svg",
    layout="wide", initial_sidebar_state="expanded"
)

FIREBASE_BASE_URL = "https://amalqu-dashboard-default-rtdb.asia-southeast1.firebasedatabase.app"
TZ_WIB = timezone(timedelta(hours=7))
def now_wib(): return datetime.datetime.now(TZ_WIB)

for k, v in [("dark_mode", True), ("auth_user", None), ("sync_nonce", 0)]:
    if k not in st.session_state: st.session_state[k] = v

def render_html(raw_html: str):
    st.markdown(" ".join(line.strip() for line in raw_html.splitlines() if line.strip()), unsafe_allow_html=True)

def build_logo_html(sz=42):
    return (f'<div style="display:inline-flex;align-items:center;justify-content:center;width:{sz}px;height:{sz}px;border-radius:12px;'
            f'background:linear-gradient(135deg,#FF6B4A 0%,#F97316 100%);box-shadow:0 4px 14px rgba(249,115,22,0.3);flex-shrink:0;">'
            f'<svg width="{int(sz*0.56)}" height="{int(sz*0.56)}" viewBox="0 0 24 24" fill="none">'
            f'<path d="M12 2L3 7V12C3 17.55 6.84 22.74 12 24C17.16 22.74 21 17.55 21 12V7L12 2ZM12 6.5C13.93 6.5 15.5 8.07 15.5 10C15.5 11.93 13.93 13.5 12 13.5C10.07 13.5 8.5 11.93 8.5 10C8.5 8.07 10.07 6.5 12 6.5ZM18 17.5C16.5 19.3 14.3 20.5 12 20.5C9.7 20.5 7.5 19.3 6 17.5C6.5 15.8 9.8 14.8 12 14.8C14.2 14.8 17.5 15.8 18 17.5Z" fill="white"/></svg></div>')

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
        s, av = ("-" if v < 0 else ""), abs(v)
        if av >= 1e9: return f"{s}Rp {av/1e9:.2f} M"
        if av >= 1e6: return f"{s}Rp {av/1e6:.1f} Jt"
        return f"{s}Rp {av:,.0f}".replace(",", ".")
    except: return "Rp 0"

def num_clean(val):
    if pd.isna(val): return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).strip()
    if not s or s in ["-", "None", "nan", "#REF!", "#VALUE!", "#DIV/0!", "#ERROR!", "#N/A"]: return 0.0
    is_neg = (s.startswith("(") and s.endswith(")")) or s.startswith("-")
    sc = re.sub(r'[^0-9.,]', '', s)
    if not sc: return 0.0
    if '.' in sc and ',' in sc:
        sc = sc.replace('.', '').replace(',', '.') if sc.rfind(',') > sc.rfind('.') else sc.replace(',', '')
    elif ',' in sc:
        pts = sc.split(',')
        sc = sc.replace(',', '.') if (len(pts) == 2 and len(pts[-1]) <= 2) else sc.replace(',', '')
    elif '.' in sc:
        if re.match(r'^\d{1,3}(\.\d{3})+$', sc) or sc.count('.') > 1: sc = sc.replace('.', '')
    try:
        res = float(sc)
        return -abs(res) if is_neg else res
    except: return 0.0

def clamp_date(dt_val, min_d, max_d):
    if not isinstance(dt_val, datetime.date): return max_d
    return max(min_d, min(dt_val, max_d))

# ==============================================================================
# 2. RUMUS BAKU SATPAM KEUANGAN & AUTO-PILOT SMART ADS ADVISOR
# ==============================================================================
def hitung_satpam_spreadsheet(donasi_masuk, biaya_iklan, sa_dict, hpp_unit=20000.0, leads_meta_val=None, mode_kebutuhan="meta_lp"):
    donasi, iklan, hpp = float(donasi_masuk or 0.0), float(biaya_iklan or 0.0), float(hpp_unit or 20000.0)
    rofi_real = (donasi / iklan) if iklan > 0 else 0.0
    roas_meta = (float(leads_meta_val) / iklan) if (iklan > 0 and leads_meta_val and float(leads_meta_val) > 0) else (rofi_real * 0.72)

    pct_iklan = (iklan / donasi * 100.0) if donasi > 0 else 0.0
    profit_iklan = donasi - iklan
    pct_profit = (profit_iklan / donasi * 100.0) if donasi > 0 else 0.0
    beban_ops_10 = 0.10 * donasi
    dsd = profit_iklan - beban_ops_10
    pct_dsd = (dsd / donasi * 100.0) if donasi > 0 else 0.0

    saldo_beli_mushaf_65 = 0.65 * dsd
    saldo_cashback_awal_35 = 0.35 * dsd
    total_alokasi_dsd = saldo_beli_mushaf_65 + saldo_cashback_awal_35

    keb_meta_lp_kurang = int(sa_dict.get("kekurangan_meta_lp", 1947))
    keb_okt_sisa = int(sa_dict.get("gap_okt", 1718))
    keb_okt_total = int(sa_dict.get("kebutuhan_okt", 1818))

    if mode_kebutuhan == "okt_sisa":
        jml_mushaf, lbl_kebutuhan = keb_okt_sisa, f"{keb_okt_sisa:,} Mushaf (Sisa Kebutuhan Oktober)".replace(",", ".")
    elif mode_kebutuhan == "okt_total":
        jml_mushaf, lbl_kebutuhan = keb_okt_total, f"{keb_okt_total:,} Mushaf (Total Kebutuhan Oktober)".replace(",", ".")
    else:
        jml_mushaf, lbl_kebutuhan = keb_meta_lp_kurang, f"{keb_meta_lp_kurang:,} Mushaf (Kekurangan Meta LP)".replace(",", ".")

    biaya_beli_mushaf = jml_mushaf * hpp
    selisih_saldo_beli = saldo_beli_mushaf_65 - biaya_beli_mushaf

    if selisih_saldo_beli >= 0:
        kekurangan_saldo_beli, surplus_saldo_beli, potong_dari_cashback = 0.0, selisih_saldo_beli, 0.0
    else:
        kekurangan_saldo_beli, surplus_saldo_beli = abs(selisih_saldo_beli), 0.0
        potong_dari_cashback = min(max(0.0, saldo_cashback_awal_35), kekurangan_saldo_beli)

    cashback_akhir = max(0.0, saldo_cashback_awal_35 - kekurangan_saldo_beli) + surplus_saldo_beli
    sisa_defisit_setelah_cb = max(0.0, kekurangan_saldo_beli - max(0.0, saldo_cashback_awal_35))
    mushaf_terbeli_saldo65 = int(max(0.0, saldo_beli_mushaf_65) // hpp) if hpp > 0 else 0

    if selisih_saldo_beli >= 0:
        status_txt, badge_col = "AMAN (Saldo 65% Cukup Tanpa Potong CB)", "green"
    elif sisa_defisit_setelah_cb == 0:
        status_txt, badge_col = f"POTONG CASHBACK ({rp_short(potong_dari_cashback)})", "orange"
    else:
        status_txt, badge_col = f"DEFISIT ({rp_short(sisa_defisit_setelah_cb)} stlh Potong CB)", "red"

    df_8_komponen = pd.DataFrame([
        {"Komponen Arus Kas Yayasan": "1. Total Donasi Masuk (Tercatat)",      "Basis / Formula Acuan": "Input Donasi Terhimpun",       "Alokasi %": "100,0%",            "Jumlah Nominal (Rp)": rp(donasi),                "Status Arus Kas": "Sumber Donasi Utama",     "Pedoman & Kebijakan Keuangan Yayasan": "1. Beban Operasional: Dipatok flat 10% dari total donasi masuk yayasan."},
        {"Komponen Arus Kas Yayasan": "2. Biaya Iklan Terpakai (Meta Ads)",    "Basis / Formula Acuan": "Input Spending Kampanye",      "Alokasi %": f"{pct_iklan:.1f}%", "Jumlah Nominal (Rp)": rp(iklan),                 "Status Arus Kas": "Beban Iklan (Maks 50%)",  "Pedoman & Kebijakan Keuangan Yayasan": "2. Donasi Siap Disalurkan (DSD): Profit Iklan dikurangi Beban Operasional."},
        {"Komponen Arus Kas Yayasan": "3. Profit Iklan Yayasan",               "Basis / Formula Acuan": "Total Donasi - Biaya Iklan",   "Alokasi %": f"{pct_profit:.1f}%","Jumlah Nominal (Rp)": rp(profit_iklan),          "Status Arus Kas": "Surplus Iklan",           "Pedoman & Kebijakan Keuangan Yayasan": "3. Budget Beli Mushaf: Wajib tepat 65% dari DSD (alokasi utama aman)."},
        {"Komponen Arus Kas Yayasan": "4. Beban Operasional Yayasan (10%)",    "Basis / Formula Acuan": "10% x Total Donasi Masuk",     "Alokasi %": "10,0%",             "Jumlah Nominal (Rp)": rp(beban_ops_10),          "Status Arus Kas": "Plafon Operasional 10%",  "Pedoman & Kebijakan Keuangan Yayasan": "4. Cashback Cadangan: Wajib 35% dari DSD untuk kas cadangan abadi."},
        {"Komponen Arus Kas Yayasan": "5. Donasi Siap Disalurkan (DSD)",       "Basis / Formula Acuan": "Profit Iklan - Beban Ops 10%", "Alokasi %": f"{pct_dsd:.1f}%",   "Jumlah Nominal (Rp)": rp(dsd),                   "Status Arus Kas": "Dana Siap Salur (DSD)",   "Pedoman & Kebijakan Keuangan Yayasan": "5. Standar ROAS Sehat: Minimal 2,00x (Beban iklan maksimal 50%)."},
        {"Komponen Arus Kas Yayasan": "6. Budget Pengadaan Mushaf (65%)",      "Basis / Formula Acuan": "65% x Donasi Siap Disalurkan", "Alokasi %": "65,0% DSD",         "Jumlah Nominal (Rp)": rp(saldo_beli_mushaf_65),  "Status Arus Kas": "Saldo Pembelian Mushaf",  "Pedoman & Kebijakan Keuangan Yayasan": "6. Di Bawah 2,00x: Wajib aktivasi tim CRM CS untuk subsidi donasi."},
        {"Komponen Arus Kas Yayasan": "7. Cadangan Kas Abadi (Cashback 35%)",  "Basis / Formula Acuan": "35% x Donasi Siap Disalurkan", "Alokasi %": "35,0% DSD",         "Jumlah Nominal (Rp)": rp(saldo_cashback_awal_35),"Status Arus Kas": "Saldo Cashback Awal",     "Pedoman & Kebijakan Keuangan Yayasan": "7. Opsi Mushaf: Tier 3 (Rp 49rb), Tier 2 (Rp 35rb), Tier 1 (Rp 20rb)."},
        {"Komponen Arus Kas Yayasan": "8. Total Alokasi Terserap (Budget+Kas)","Basis / Formula Acuan": "Budget 65% + Cadangan 35%",    "Alokasi %": "100,0% DSD",        "Jumlah Nominal (Rp)": rp(total_alokasi_dsd),     "Status Arus Kas": "Alokasi Sempurna (100%)", "Pedoman & Kebijakan Keuangan Yayasan": "8. Protokol Darurat: Tarik kas cashback 35% jika budget 65% defisit."},
    ])

    return {
        "donasi": donasi, "iklan": iklan, "profit_iklan": profit_iklan, "beban_ops_10": beban_ops_10, "dsd": dsd,
        "roas_meta": roas_meta, "rofi_real": rofi_real,
        "saldo_beli_mushaf_65": saldo_beli_mushaf_65, "saldo_cashback_awal_35": saldo_cashback_awal_35,
        "jml_mushaf": jml_mushaf, "lbl_kebutuhan": lbl_kebutuhan, "hpp": hpp,
        "biaya_beli_mushaf": biaya_beli_mushaf, "selisih_saldo_beli": selisih_saldo_beli,
        "kekurangan_saldo_beli": kekurangan_saldo_beli, "potong_dari_cashback": potong_dari_cashback,
        "cashback_akhir": cashback_akhir, "sisa_defisit_setelah_cb": sisa_defisit_setelah_cb,
        "mushaf_terbeli_saldo65": mushaf_terbeli_saldo65, "status_txt": status_txt, "badge_col": badge_col,
        "df_8_komponen": df_8_komponen
    }

def hitung_autopilot_ads(real_okt, spend_aktif, nom_closing_meta, leads_closing_cnt, tot_leads_valid, avg_cr_pct, hari_berjalan, df_har):
    cr_dec = (avg_cr_pct / 100.0) if avg_cr_pct > 0 else 0.743
    avg_spend_harian = spend_aktif / max(1, hari_berjalan)
    roas_meta = (nom_closing_meta / spend_aktif) if spend_aktif > 0 else 0.83
    rofi_fin = (real_okt / spend_aktif) if spend_aktif > 0 else 1.20
    aov_meta = nom_closing_meta / max(1, leads_closing_cnt)

    cpr_aktual = spend_aktif / max(1, tot_leads_valid)
    cpa_closing = spend_aktif / max(1, leads_closing_cnt)

    # Standar Aman CPR terhadap Paket Donasi Minimal Rp 99.000 (99K)
    batas_cpr_sehat_99k = 49500.0 * cr_dec
    batas_cpr_maks_99k = 58331.0 * cr_dec

    if rofi_fin >= 2.0 and cpr_aktual <= batas_cpr_sehat_99k:
        mode_keputusan, badge_keputusan, faktor_kali = "SCALE UP OTOMATIS (+20% BUDGET)", "green", 1.20
        alasan_utama = f"ROFI Finance ({rofi_fin:.2f}x) sudah >= 2,00x dan CPR ({rp(cpr_aktual)}) aman di bawah batas donasi 99K ({rp(batas_cpr_sehat_99k)})."
    elif rofi_fin >= 1.50 or cpr_aktual <= batas_cpr_maks_99k:
        mode_keputusan, badge_keputusan, faktor_kali = "TAHAN BUDGET STABIL (100% RATA-RATA)", "orange", 1.00
        alasan_utama = f"ROFI ({rofi_fin:.2f}x) cukup menutup HPP dasar, namun CPR ({rp(cpr_aktual)}) mendekati batas toleransi donasi 99K ({rp(batas_cpr_maks_99k)})."
    else:
        mode_keputusan, badge_keputusan, faktor_kali = "REM EFISIENSI OTOMATIS (-15% SPEND) & INJEKSI CRM", "red", 0.85
        alasan_utama = f"Rata-rata CPR ({rp(cpr_aktual)}/lead) melampaui batas aman donasi 99K ({rp(batas_cpr_sehat_99k)}/lead) dan ROFI ({rofi_fin:.2f}x) di bawah standar sehat 2,00x."

    rekom_budget_hari_ini = round((avg_spend_harian * faktor_kali) / 100000.0) * 100000.0
    target_donasi_hari_ini_2x = rekom_budget_hari_ini * 2.00
    est_donasi_meta_hari_ini = rekom_budget_hari_ini * roas_meta
    wajib_subsidi_crm_hari_ini = max(0.0, target_donasi_hari_ini_2x - est_donasi_meta_hari_ini)

    target_leads_hari_ini = max(1, int(np.ceil(rekom_budget_hari_ini / batas_cpr_sehat_99k)))
    target_closing_hari_ini = max(1, int(np.ceil(target_leads_hari_ini * cr_dec)))
    min_paket_mushaf = max(2, int(np.ceil((cpa_closing * 2.0) / 99000.0)))

    return {
        "cpr_aktual": cpr_aktual, "cpa_closing": cpa_closing,
        "batas_cpr_sehat_99k": batas_cpr_sehat_99k, "batas_cpr_maks_99k": batas_cpr_maks_99k,
        "mode_keputusan": mode_keputusan, "badge_keputusan": badge_keputusan, "alasan_utama": alasan_utama,
        "rekom_budget_hari_ini": rekom_budget_hari_ini, "avg_spend_harian": avg_spend_harian,
        "target_donasi_hari_ini_2x": target_donasi_hari_ini_2x,
        "est_donasi_meta_hari_ini": est_donasi_meta_hari_ini, "wajib_subsidi_crm_hari_ini": wajib_subsidi_crm_hari_ini,
        "target_leads_hari_ini": target_leads_hari_ini, "target_closing_hari_ini": target_closing_hari_ini,
        "min_paket_mushaf": min_paket_mushaf, "aov_meta": aov_meta, "roas_meta": roas_meta, "rofi_fin": rofi_fin
    }

# ==============================================================================
# 3. KONFIGURASI AKUN LOGIN & ID GOOGLE SHEETS
# ==============================================================================
ALL_MENUS = ["Dashboard Overview", "Donasi & Satpam Keuangan", "Iklan & Strategi Ads", "Performa CS & Leads", "Logistik & Gudang", "Kalender Distribusi", "Database & WA Blast"]
AUTH_USERS = {
    "amalqu":     {"key": "amalqu", "username_display": "Amalqu", "pw": "Allah1ahad", "role": "Admin", "title": "Super Administrator", "menus": ALL_MENUS},
    "finance":    {"key": "finance", "username_display": "Finance", "pw": "timfinancejaya99", "role": "Finance", "title": "Divisi Finance & Audit", "menus": ALL_MENUS},
    "advertiser": {"key": "advertiser", "username_display": "Advertiser", "pw": "ngiklangacor99", "role": "Advertiser", "title": "Divisi Digital Ads & Funnel", "menus": ALL_MENUS[:4]},
    "warehouse":  {"key": "warehouse", "username_display": "Warehouse", "pw": "amansulaiman123", "role": "Warehouse", "title": "Divisi Gudang & Distribusi", "menus": ALL_MENUS[4:6]}
}

if st.session_state.auth_user is None:
    try:
        qp_u = str(st.query_params.get("u", "")).strip().lower()
        if qp_u in AUTH_USERS: st.session_state.auth_user = AUTH_USERS[qp_u]
    except: pass

SHEETS_CONFIG = {
    "leads_cs":      ("11xL6IWq9D_kmgYicQUDI-CH8crpk43GnnJ-pT1M6Lkw", "1318371393"),
    "satpam":        ("1Acu1t704R4Ms3Mwz1NrJ_0x8p9xPnH8QWon1OoaoxxU", "0"),
    "data_cs":       ("1qnPuZvYMQFma-3Wk_-x2iWnrywSUFnxm8QE-riYoWus", "1504147119"),
    "master_db":     ("1zeTDweSHvALQEriL7D1n7JLNAoBcPkq8i57mRKHlS3U", "1827422698"),
    "stok_mushaf":   ("1p2fISiecchH84LUvdpEbzPsa3YQq_HAVCUvbfJTwxvE", "104"),
    "kalender_dist": ("159nbvj-on-SM5YwcQGHp8ffzJFY7gj7AUAptpRl0wJA", "1940610974"),
    "bulan_oktober": ("10UJz62vYB4m86TC_WbOIfbgUYLp8gnfFo8-nNk_W180", "170644840"),
}

def fetch_firebase_json():
    url = f"{FIREBASE_BASE_URL.rstrip('/')}/amalqu_live.json?cb={int(time.time()*1000)}"
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache, no-store", "Pragma": "no-cache"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data if isinstance(data, dict) else {}

def grid_to_df(grid_obj):
    if not grid_obj or not isinstance(grid_obj, list): return pd.DataFrame()
    max_len = max((len(r) for r in grid_obj if isinstance(r, list)), default=0)
    if max_len == 0: return pd.DataFrame()
    norm_rows = []
    for r in grid_obj:
        if isinstance(r, list):
            row_s = [str(x).strip() if x is not None else "" for x in r]
            if len(row_s) < max_len: row_s.extend([""] * (max_len - len(row_s)))
            norm_rows.append(row_s)
    return pd.DataFrame(norm_rows, dtype=str).fillna("")

def read_csv_nocache(url: str):
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": f"AmalQu-Live/{int(time.time())}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return pd.read_csv(io.BytesIO(resp.read()), header=None, dtype=str).fillna("")

def fetch_direct_sheet(key_name, sheet_name=None):
    if key_name not in SHEETS_CONFIG: return pd.DataFrame()
    sid, gid = SHEETS_CONFIG[key_name]
    cb = int(time.time() * 1000)
    base = f"https://docs.google.com/spreadsheets/d/{sid}"
    urls = ([f"{base}/gviz/tq?tqx=out:csv&headers=0&sheet={quote(sheet_name)}&cb={cb}"] if sheet_name else []) + [f"{base}/gviz/tq?tqx=out:csv&headers=0&gid={gid}&cb={cb}"]
    for u in urls:
        try:
            df = read_csv_nocache(u)
            if not df.empty and df.shape[1] >= 2 and "<!doctype" not in str(df.iat[0, 0]).lower():
                return df
        except: continue
    return pd.DataFrame()

# ==============================================================================
# 4. CSS SYSTEM
# ==============================================================================
is_dark = st.session_state.dark_mode
css_vars = (
    ":root{--bg-main:#0B0F19;--bg-card:#111827;--bg-subcard:#1A2333;--bg-input:#1E293B;--text-primary:#F8FAFC;--text-secondary:#CBD5E1;--text-muted:#94A3B8;--border-soft:#1E293B;--border-strong:#334155;--table-head:#1E293B;--table-hover:#1E293B;--cal-active-bg:linear-gradient(180deg,rgba(249,115,22,0.18) 0%,#111827 100%);--cal-success-bg:linear-gradient(180deg,rgba(16,185,129,0.22) 0%,#111827 100%);--cal-pill-bg:#1E293B;}"
    if is_dark else
    ":root{--bg-main:#F4F7FE;--bg-card:#FFFFFF;--bg-subcard:#F8FAFC;--bg-input:#FFFFFF;--text-primary:#0F172A;--text-secondary:#475569;--text-muted:#64748B;--border-soft:#E2E8F0;--border-strong:#CBD5E1;--table-head:#F8FAFC;--table-hover:#F1F5F9;--cal-active-bg:linear-gradient(180deg,#FFF7ED 0%,#FFFFFF 100%);--cal-success-bg:linear-gradient(180deg,#ECFDF5 0%,#FFFFFF 100%);--cal-pill-bg:#FFFFFF;}"
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
.block-container{{padding-top:1.1rem!important;padding-bottom:2rem!important;max-width:1440px!important;}}
section[data-testid="stSidebar"]{{background-color:var(--bg-card)!important;border-right:1px solid var(--border-soft)!important;width:265px!important;}}
.sub-box{{background:var(--bg-subcard);border:1px solid var(--border-soft);}}
section[data-testid="stSidebar"] div[role="radiogroup"]{{gap:6px!important;display:flex!important;flex-direction:column!important;}}
section[data-testid="stSidebar"] label[data-baseweb="radio"]{{background:transparent!important;border:1px solid transparent!important;border-radius:12px!important;padding:10px 15px!important;margin:0!important;cursor:pointer!important;width:100%!important;}}
section[data-testid="stSidebar"] label[data-baseweb="radio"]>div:not([data-testid="stMarkdownContainer"]),section[data-testid="stSidebar"] label[data-baseweb="radio"] input{{display:none!important;width:0!important;height:0!important;}}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover{{background:var(--bg-subcard)!important;border-color:var(--border-soft)!important;}}
section[data-testid="stSidebar"] label[data-baseweb="radio"] p{{font-size:13px!important;font-weight:600!important;color:var(--text-secondary)!important;margin:0!important;}}
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
.bento-card,[data-testid="stForm"]{{background:var(--bg-card)!important;border:1px solid var(--border-soft)!important;border-radius:18px!important;padding:16px 18px!important;box-shadow:0 4px 18px -2px rgba(0,0,0,0.05)!important;margin-bottom:12px!important;overflow:hidden!important;}}
.kpi-uniform{{min-height:136px;height:auto!important;display:flex;flex-direction:column;justify-content:space-between;gap:6px;}}
.hero-card{{background:linear-gradient(135deg,#4F46E5 0%,#6366F1 55%,#8B5CF6 100%);border-radius:18px;padding:16px 18px;min-height:136px;height:auto!important;display:flex;flex-direction:column;justify-content:space-between;gap:6px;color:#FFFFFF!important;box-shadow:0 10px 24px -6px rgba(79,70,229,0.4);margin-bottom:12px;overflow:hidden!important;}}
.hero-card *{{color:#FFFFFF!important;}}
.kpi-val-fluid{{font-family:'Outfit',sans-serif!important;font-size:clamp(17px,1.55vw,22.5px)!important;font-weight:800!important;line-height:1.2!important;letter-spacing:-0.4px;word-break:break-word!important;}}
.section-divider{{font-family:'Outfit',sans-serif!important;font-size:12.5px;font-weight:800;letter-spacing:0.7px;text-transform:uppercase;color:var(--text-muted)!important;margin:8px 0 8px 2px;display:flex;align-items:center;gap:8px;}}
.satpam-step{{background:var(--bg-subcard);border:1px solid var(--border-soft);border-radius:12px;padding:10px 14px;margin-bottom:7px;display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;}}
.satpam-val{{font-family:'Outfit',sans-serif!important;font-size:16px;font-weight:800;white-space:nowrap;}}
.chart-header-box{{background:var(--bg-card);border:1px solid var(--border-soft);border-bottom:none;border-radius:18px 18px 0 0;padding:16px 20px 8px 20px;margin-bottom:-16px;position:relative;z-index:2;}}
[data-testid="stPlotlyChart"]{{background:var(--bg-card)!important;border:1px solid var(--border-soft)!important;border-top:none!important;border-radius:0 0 18px 18px!important;padding:4px 12px 8px 12px!important;margin-bottom:12px!important;}}
.icon-box{{width:34px;height:34px;border-radius:10px;flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;font-size:16px;}}
.ib-indigo{{background:rgba(79,70,229,0.15);color:#6366F1!important;}}.ib-orange{{background:rgba(249,115,22,0.15);color:#F97316!important;}}.ib-emerald{{background:rgba(16,185,129,0.15);color:#10B981!important;}}.ib-rose{{background:rgba(239,68,68,0.15);color:#EF4444!important;}}
.badge-pill{{font-size:10.5px;font-weight:700;padding:3px 8px;border-radius:99px;display:inline-flex;align-items:center;gap:4px;white-space:nowrap!important;max-width:100%;overflow:hidden;text-overflow:ellipsis;}}
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
.cal-cell-success{{background:var(--cal-success-bg);border:1.5px solid #10B981;border-radius:12px;min-height:96px;padding:8px 10px;}}
.cal-day-num{{font-family:'Outfit',sans-serif!important;font-size:13px;font-weight:700;color:var(--text-primary)!important;display:flex;justify-content:space-between;align-items:center;gap:4px;}}
.cal-item-pill{{background:var(--cal-pill-bg);border:1px solid var(--border-soft);border-left:3px solid #F97316;border-radius:6px;padding:4px 6px;margin-top:4px;font-size:10.5px;color:var(--text-primary)!important;line-height:1.25;}}
.cal-item-pill-success{{background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.35);border-left:3px solid #10B981;border-radius:6px;padding:4px 6px;margin-top:4px;font-size:10.5px;color:var(--text-primary)!important;line-height:1.25;}}
@media screen and (max-width:768px){{.block-container{{padding-left:12px!important;padding-right:12px!important;padding-top:2.8rem!important;}}div[data-testid="stHorizontalBlock"]{{flex-wrap:wrap!important;}}div[data-testid="column"]{{width:100%!important;flex:1 1 100%!important;min-width:100%!important;}}.cal-desktop-only{{display:none!important;}}.cal-mobile-only{{display:block!important;}}}}
</style>
""")

if st.session_state.auth_user is None:
    _, top_sp2 = st.columns([8.5, 1])
    with top_sp2:
        if st.button("☀️ Terang" if is_dark else "🌙 Gelap", key="login_theme_btn", use_container_width=True):
            st.session_state.dark_mode = not st.session_state.dark_mode; st.rerun()
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
# 5. MERGE-SAFE PARSERS
# ==============================================================================
def extract_anchored_table(df_raw, anchor1, anchor2=None, stop_words=None, max_rows=100, max_cols=None):
    if df_raw is None or df_raw.empty: return pd.DataFrame()
    nrows, ncols = df_raw.shape
    start_r, start_c = None, None
    for r in range(nrows):
        for c in range(ncols):
            val = str(df_raw.iat[r, c]).strip()
            if val.lower() == anchor1.lower() or (anchor1.lower() in val.lower() and len(val) <= len(anchor1) + 12):
                if anchor2 is None: start_r, start_c = r, c; break
                else:
                    for cn in range(c + 1, min(ncols, c + 4)):
                        if anchor2.lower() in str(df_raw.iat[r, cn]).strip().lower(): start_r, start_c = r, c; break
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
        row_slice = [str(df_raw.iat[r, c]).strip() for c in range(start_c, end_c)]
        if all(x == "" for x in row_slice):
            empty_streak += 1
            if empty_streak >= 3: break
            continue
        empty_streak = 0
        if stop_words and any(sw.lower() in row_slice[0].lower() for sw in stop_words): break
        data_rows.append(row_slice)
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
                if "salma" in rc or "leads" in bc or "crm" in bc: tgl_r, tgl_c = r, c; break
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
        rows.append({"Tanggal": c0, "Salma_Meta": sm, "Salma_CRM": sc, "Aulia_Meta": am, "Aulia_CRM": ac, "Nisa_Meta": nm, "Nisa_CRM": nc, "Total_Leads": tl, "Total_CRM": tc, "Total_Gabungan": tg, "Salma": sm + sc, "Aulia": am + ac, "Nisa": nm + nc, "Total Donasi": tg, "Donasi Final": tg})
    return pd.DataFrame(rows)

def parse_monitoring_roas_finance(grid_okt):
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
                nom_s, ras_s = (right_vals[0] if len(right_vals) >= 1 else "-"), (right_vals[1] if len(right_vals) >= 2 else "-")
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
    nrows, ncols = grid_ms.shape
    inv_rows, def_rows = [], []
    for r in range(nrows):
        c0 = str(grid_ms.iat[r, 0]).strip() if ncols > 0 else ""
        if any(k in c0.lower() for k in ["mushaf -", "buku belajar", "titipan mitra", "total inventaris fisik"]):
            c1 = str(grid_ms.iat[r, 1]).strip() if ncols > 1 else ""
            c2 = int(num_clean(grid_ms.iat[r, 2])) if ncols > 2 else 0
            c3 = int(num_clean(grid_ms.iat[r, 3])) if ncols > 3 else 0
            c4 = int(num_clean(grid_ms.iat[r, 4])) if ncols > 4 else (c2 + c3)
            inv_rows.append({"Produk & Kategori": c0, "Kanal Promosi": c1, "Siap Salur (Stiker)": c2, "Belum Siap (Proses)": c3, "Total Stok Fisik": c4})
        for c in range(4, min(ncols, 8)):
            txt_f = str(grid_ms.iat[r, c]).strip()
            if any(k in txt_f.lower() for k in ["kebutuhan agustus", "kebutuhan september", "kebutuhan oktober", "total kebutuhan", "total stok fisik mushaf", "kekurangan pembelian"]):
                r_vals = [str(grid_ms.iat[r, cc]).strip() for cc in range(c + 1, ncols) if str(grid_ms.iat[r, cc]).strip() != ""]
                if len(r_vals) >= 3:
                    def_rows.append({"Periode / Komponen Analisis": txt_f, "Target / Stok": r_vals[0], "Keterangan Operasional": r_vals[1] if len(r_vals) >= 4 else "-", "Gap / Defisit": r_vals[2] if len(r_vals) >= 4 else r_vals[1], "Status & Rekomendasi": r_vals[3] if len(r_vals) >= 4 else r_vals[2]})
                break
    if inv_rows: out["rincian_inventaris"] = pd.DataFrame(inv_rows)
    if def_rows: out["analisis_defisit"] = pd.DataFrame(def_rows)
    return out

def parse_data_spend_oktober(grid_sp):
    kpi_sp = {"total_spending": 0.0, "total_leads": 0, "avg_cpr": 0.0, "leads_closing": 1298, "nominal_closing": 205624456.0, "total_roas": 0.0, "avg_cpr_harian": 0.0, "spend_per_hari": 0.0, "leads_per_hari": 0.0}
    if grid_sp is None or grid_sp.empty: return kpi_sp, pd.DataFrame()
    nrows, ncols = grid_sp.shape
    for r in range(min(10, nrows - 1)):
        row_up = [str(grid_sp.iat[r, c]).strip().upper() for c in range(ncols)]
        if "TOTAL SPENDING" in row_up or "LEADS CLOSING" in row_up:
            for c_i, h_txt in enumerate(row_up):
                vn = num_clean(grid_sp.iat[r + 1, c_i])
                if "TOTAL SPENDING" in h_txt: kpi_sp["total_spending"] = vn
                elif "TOTAL LEADS" in h_txt: kpi_sp["total_leads"] = int(vn)
                elif "RATA-RATA CPR" in h_txt: kpi_sp["avg_cpr"] = vn
                elif "LEADS CLOSING" in h_txt: kpi_sp["leads_closing"] = int(vn)
                elif "NOMINAL CLOSING" in h_txt: kpi_sp["nominal_closing"] = vn
                elif "TOTAL ROAS" in h_txt: kpi_sp["total_roas"] = vn
                elif "RATA2 CPR" in h_txt: kpi_sp["avg_cpr_harian"] = vn
                elif "SPEND / HARI" in h_txt: kpi_sp["spend_per_hari"] = vn
                elif "LEADS / HARI" in h_txt: kpi_sp["leads_per_hari"] = vn
            break
    rows_sp = []
    for r in range(nrows):
        for c in range(min(4, ncols)):
            v_t = str(grid_sp.iat[r, c]).strip()
            if re.match(r'^2026-10-\d{2}$', v_t):
                def gs(off):
                    ci = c + off
                    return str(grid_sp.iat[r, ci]).strip() if ci < ncols else ""
                rows_sp.append({"Tanggal": v_t, "Hari": gs(1), "Spending (Rp)": num_clean(gs(2)), "Leads": int(num_clean(gs(3))), "Rata-Rata CPR": num_clean(gs(4)), "Leads Closing": int(num_clean(gs(5))), "Nominal Closing (Rp)": num_clean(gs(6)), "ROAS": num_clean(gs(7)), "Catatan / Evaluasi": gs(8) if gs(8) else "-"})
                break
    df_sp = pd.DataFrame(rows_sp)
    if not df_sp.empty:
        if kpi_sp["total_spending"] == 0 and df_sp["Spending (Rp)"].sum() > 0: kpi_sp["total_spending"] = float(df_sp["Spending (Rp)"].sum())
        if kpi_sp["total_leads"] == 0 and df_sp["Leads"].sum() > 0: kpi_sp["total_leads"] = int(df_sp["Leads"].sum())
        if df_sp["Leads Closing"].sum() > 0: kpi_sp["leads_closing"] = int(df_sp["Leads Closing"].sum())
        if df_sp["Nominal Closing (Rp)"].sum() > 0: kpi_sp["nominal_closing"] = float(df_sp["Nominal Closing (Rp)"].sum())
    return kpi_sp, df_sp

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
            m_iso = re.search(r'(2026-\d{1,2}-\d{1,2})', v)
            m_slash = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-]2026', v)
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

def extract_day_okt(val_str):
    s = str(val_str).strip()
    if not s: return None
    m_iso = re.search(r'2026-10-(\d{1,2})', s)
    if m_iso: return int(m_iso.group(1))
    m_sl = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-]2026', s)
    if m_sl:
        p1, p2 = int(m_sl.group(1)), int(m_sl.group(2))
        if p2 == 10 and 1 <= p1 <= 31: return p1
        if p1 == 10 and 1 <= p2 <= 31: return p2
    m_txt = re.search(r'(\d{1,2})\s*(?:okt|oct|oktober|october)', s, re.IGNORECASE)
    if m_txt: return int(m_txt.group(1))
    m_end = re.search(r'-(\d{1,2})$', s)
    if m_end and 1 <= int(m_end.group(1)) <= 31: return int(m_end.group(1))
    return None

# ==============================================================================
# 6. FIREBASE REALTIME ENGINE
# ==============================================================================
@st.cache_data(ttl=30, show_spinner=False)
def load_core_realtime_data(sync_token: int):
    db, sync_status = {}, {}

    macro_rows = [
        ("Januari", 326000000, 313838000, 194267000, 218457000, 222889000, 90949200, 1.44, 40.8, "Tidak Tercapai", 2356),
        ("Februari", 522000000, 244568000, 230443000, 228843000, 232374000, 12194000, 1.07, 5.2, "Tidak Tercapai", 1906),
        ("Maret", 835000000, 432950000, 443374100, 331054000, 334504000, 98446500, 1.31, 29.4, "Tidak Tercapai", 3814),
        ("April", 359000000, 292695000, 253733400, 262156000, 266465000, 26230300, 1.12, 9.8, "Tidak Tercapai", 2225),
        ("Mei", 395029000, 485195000, 154142300, 335053000, 338597000, 146597000, 1.45, 43.3, "Tercapai", 1454),
        ("Juni", 434532000, 457976000, 408027750, 345054000, 356438000, 101538000, 1.33, 28.5, "Tercapai", 4103),
        ("Juli", 477986000, 490683000, 374520900, 345049000, 353467000, 137216000, 1.42, 38.8, "Tercapai", 3586),
        ("Agustus", 525784000, 371847000, 290718820, 320040000, 322971000, 48876700, 1.16, 15.1, "Tidak Tercapai", 2852),
        ("September", 350000000, 310384000, 272608400, 254360000, 107038000, 203346000, 1.22, 190.0, "Tidak Tercapai", 2599),
        ("Oktober", 500000000, 298201574, 249458456, 248087884, 248087884, 50113690, 1.20, 20.2, "Realtime", 1818),
    ]
    db['macro_monthly'] = pd.DataFrame(macro_rows, columns=["Bulan", "Target Bulanan", "Realisasi Finance", "Omset CS", "Budget Iklan", "Total Pengeluaran", "Laba Bersih", "ROFI", "ROI_Pct", "Status Target", "Mushaf Terverifikasi"])

    cs_ov_rows = [
        (1, "Nisa", "Aktif", 1200000000, 15839000, 68093999, 196005644, 125603001, 74540362, 200017711, 197594767, 84384400, 71315000, 150200000, 1033393884, 6219, 166167, "86,1%", "39,4%"),
        (2, "Salma", "Aktif", 1200000000, 153161444, 130171224, 201796334, 85285000, 50347999, 121468905, 79080000, 104793000, 72695000, 72000000, 998798907, 5898, 169345, "83,2%", "38,1%"),
        (3, "Aulia", "Aktif", 500000000, 0, 396000, 1894000, 11719000, 11748999, 76174000, 84631886, 84775000, 64809000, 27258456, 336147885, 2128, 157964, "67,2%", "12,8%"),
        (4, "Desi", "Non-Aktif", 200000000, 25267000, 26163000, 3342596, 23010375, 9298900, 4316750, 6395000, 4917625, 42651438, 0, 145362684, 924, 157319, "72,7%", "5,5%"),
        (5, "Syafiq", "Non-Aktif", 0, 0, 5619000, 35515478, 8116000, 8206000, 6050000, 0, 0, 0, 0, 63506478, 257, 247107, "0,0%", "2,4%"),
        (6, "Rida", "Non-Aktif", 150000000, 0, 0, 0, 0, 0, 0, 2495000, 5128000, 15148000, 0, 22771000, 150, 151807, "15,2%", "0,9%"),
        (7, "Olive", "Aktif CRM", 0, 0, 0, 0, 0, 0, 0, 4324000, 6720800, 5990000, 1296500, 17034800, 106, 160706, "0,0%", "0,6%"),
        (8, "Sarah", "Non-Aktif", 100000000, 0, 0, 4820000, 0, 0, 0, 0, 0, 0, 0, 4820000, 23, 209565, "4,8%", "0,2%"),
    ]
    db['cs_overview'] = pd.DataFrame(cs_ov_rows, columns=["Rank", "Nama CS", "Status Okt", "Target Omset", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "Total Omset (Jan-Sep)", "Total Closing", "AOV", "Pencapaian (%)", "Kontribusi (%)"])

    db['okt_kpi'] = {"total_donasi": 249458456, "target": 500000000, "capaian_pct": 49.9, "donasi_final": 223500000, "harian_terbaru": 7948000, "verifikasi_pct": 89.6}
    db['okt_finance_mon'] = {"realisasi_finance": 298201574, "budget_iklan": 248087884, "rofi_real": 1.20, "roas_akuisisi": 0.83, "rofi_cs": 1.01, "hari_cutoff": 28, "avg_donasi_hari": 10650056, "avg_ads_hari": 8860281, "estimasi_akhir_bulan": 330151743}
    db['okt_cs_table'] = pd.DataFrame([
        {"CS / CRM": "Salma", "Harian (Total)": 2464008, "Harian (Final)": 2464008, "Mingguan (Total)": 2464008, "Mingguan (Final)": 2464008, "Bulanan (Total)": 56986008, "Bulanan (Final)": 50828008, "% Verifikasi": "89,2%", "Total Transaksi": 409, "Target (Rp)": 200000000, "% Capaian Target": "28,5%", "Sisa Target": 143013992, "Pending Verifikasi": 6158000, "Target Harian (Sisa)": 4613355},
        {"CS / CRM": "Aulia", "Harian (Total)": 453000, "Harian (Final)": 453000, "Mingguan (Total)": 453000, "Mingguan (Final)": 453000, "Bulanan (Total)": 13026000, "Bulanan (Final)": 11418000, "% Verifikasi": "87,7%", "Total Transaksi": 126, "Target (Rp)": 50000000, "% Capaian Target": "26,1%", "Sisa Target": 36974000, "Pending Verifikasi": 1608000, "Target Harian (Sisa)": 1192710},
        {"CS / CRM": "Nisa", "Harian (Total)": 5944000, "Harian (Final)": 5944000, "Mingguan (Total)": 5944000, "Mingguan (Final)": 5944000, "Bulanan (Total)": 122697449, "Bulanan (Final)": 113328449, "% Verifikasi": "92,4%", "Total Transaksi": 809, "Target (Rp)": 200000000, "% Capaian Target": "61,3%", "Sisa Target": 77302551, "Pending Verifikasi": 9369000, "Target Harian (Sisa)": 2493631},
        {"CS / CRM": "TOTAL", "Harian (Total)": 8861008, "Harian (Final)": 8861008, "Mingguan (Total)": 8861008, "Mingguan (Final)": 8861008, "Bulanan (Total)": 249458456, "Bulanan (Final)": 223500000, "% Verifikasi": "89,6%", "Total Transaksi": 1344, "Target (Rp)": 450000000, "% Capaian Target": "55,4%", "Sisa Target": 200541544, "Pending Verifikasi": 25958456, "Target Harian (Sisa)": 8299695},
    ])
    db['okt_sumber'] = pd.DataFrame([
        {"CS / CRM": "Salma", "Leads Meta": 45398008, "Repeat Order CRM": 0, "Repeat Order non CRM": 10590000, "Lainnya": 998000, "Total Nominal": 56986008, "% Leads Meta": "79,7%"},
        {"CS / CRM": "Aulia", "Leads Meta": 1144000, "Repeat Order CRM": 7264000, "Repeat Order non CRM": 0, "Lainnya": 4618000, "Total Nominal": 13026000, "% Leads Meta": "8,8%"},
        {"CS / CRM": "Nisa", "Leads Meta": 159082448, "Repeat Order CRM": 0, "Repeat Order non CRM": 6181000, "Lainnya": 1291000, "Total Nominal": 166554448, "% Leads Meta": "95,5%"},
        {"CS / CRM": "TOTAL", "Leads Meta": 205624456, "Repeat Order CRM": 7264000, "Repeat Order non CRM": 16771000, "Lainnya": 6907000, "Total Nominal": 249458456, "% Leads Meta": "82,4%"},
    ])
    db['okt_kanal_rasio'] = pd.DataFrame([
        {"Kanal / Metrik Donasi": "Total Leads Meta", "Nominal": "Rp205.624.456", "% Kontribusi / Rasio": "82,4%", "Keterangan & Analisis": "Perolehan donasi dari iklan berbayar Meta Ads"},
        {"Kanal / Metrik Donasi": "Total CRM (Repeat Order)", "Nominal": "Rp36.927.000", "% Kontribusi / Rasio": "14,8%", "Keterangan & Analisis": "Donasi berulang donatur CRM & non-CRM"},
        {"Kanal / Metrik Donasi": "Total Sedekah Lainnya", "Nominal": "Rp6.907.000", "% Kontribusi / Rasio": "2,8%", "Keterangan & Analisis": "Donasi program umum di luar mushaf / Quran"},
        {"Kanal / Metrik Donasi": "ROAS Akuisisi (Leads Meta)", "Nominal": "-", "% Kontribusi / Rasio": "0,83x", "Keterangan & Analisis": "Efektivitas donasi Meta terhadap belanja iklan"},
        {"Kanal / Metrik Donasi": "ROFI Real Finance", "Nominal": "-", "% Kontribusi / Rasio": "1,20x", "Keterangan & Analisis": "Rasio realisasi donasi terhadap belanja iklan"},
    ])

    harian_rows_base = [
        ("2026-10-01", "Kamis", 2464008, 0, 0, 453000, 5744000, 200000, 8208008, 653000, 8861008, 66),
        ("2026-10-02", "Jum'at", 4362000, 629000, 0, 1591000, 8155000, 746000, 12517000, 2966000, 15483000, 74),
        ("2026-10-03", "Sabtu", 1595000, 70000, 0, 657000, 2094000, 198000, 3689000, 925000, 4614000, 32),
        ("2026-10-04", "Minggu", 2273000, 50000, 0, 283000, 3785000, 0, 6058000, 333000, 6391000, 46),
        ("2026-10-05", "Senin", 1375000, 50000, 225000, 1854000, 3738000, 143000, 5338000, 2047000, 7385000, 41),
        ("2026-10-06", "Selasa", 1766000, 300000, 719000, 555000, 2979000, 607000, 5464000, 1462000, 6926000, 46),
        ("2026-10-07", "Rabu", 1062000, 50000, 0, 454000, 3013000, 298000, 4075000, 802000, 4877000, 33),
        ("2026-10-08", "Kamis", 775000, 530000, 0, 653000, 5168000, 797000, 5943000, 1980000, 7923000, 28),
        ("2026-10-09", "Jum'at", 4816000, 1280000, 0, 853000, 8276000, 609000, 13092000, 2742000, 15834000, 73),
        ("2026-10-10", "Sabtu", 2388000, 100000, 100000, 707000, 1819000, 229000, 4307000, 1036000, 5343000, 33),
        ("2026-10-11", "Minggu", 1346000, 0, 0, 255000, 4288950, 399000, 5634950, 654000, 6288950, 31),
        ("2026-10-12", "Senin", 997000, 450000, 0, 154000, 4130000, 400000, 5127000, 1004000, 6131000, 37),
        ("2026-10-13", "Selasa", 1092000, 150000, 0, 300000, 7004000, 1079000, 8096000, 1529000, 9625000, 64),
        ("2026-10-14", "Rabu", 3391000, 100000, 0, 299000, 5488000, 110000, 8879000, 509000, 9388000, 43),
        ("2026-10-15", "Kamis", 1788000, 332000, 100000, 189000, 6341000, 204000, 8229000, 725000, 8954000, 46),
        ("2026-10-16", "Jum'at", 230000, 5201000, 0, 1578000, 10099500, 508000, 10329500, 7287000, 17616500, 67),
        ("2026-10-17", "Sabtu", 200000, 100000, 0, 299000, 4911000, 325000, 5111000, 724000, 5835000, 24),
        ("2026-10-18", "Minggu", 0, 124000, 0, 149000, 6933000, 104000, 6933000, 377000, 7310000, 49),
        ("2026-10-19", "Senin", 400000, 275000, 0, 300000, 7062999, 0, 7462999, 575000, 8037999, 51),
        ("2026-10-20", "Selasa", 1064000, 1199000, 0, 399000, 7329000, 298000, 8393000, 1896000, 10289000, 61),
        ("2026-10-21", "Rabu", 5483000, 200000, 0, 948000, 4595000, 218000, 10078000, 1366000, 11444000, 53),
        ("2026-10-22", "Kamis", 2663000, 398000, 0, 2845000, 4191000, 108000, 6854000, 3351000, 10205000, 36),
        ("2026-10-23", "Jum'at", 9795000, 180000, 0, 4507000, 5530999, 601000, 15325999, 5288000, 20613999, 102),
        ("2026-10-24", "Sabtu", 5742000, 100000, 0, 400000, 2246000, 0, 7988000, 500000, 8488000, 28),
        ("2026-10-25", "Minggu", 3095000, 30000, 0, 700000, 2470000, 0, 5565000, 730000, 6295000, 31),
        ("2026-10-26", "Senin", 3331000, 100000, 0, 1349000, 2960000, 0, 6291000, 1449000, 7740000, 43),
        ("2026-10-27", "Selasa", 3966000, 0, 0, 299000, 3583000, 100000, 7549000, 399000, 7948000, 45),
        ("2026-10-28", "Rabu", 1500000, 0, 0, 0, 1587000, 0, 3087000, 0, 3087000, 15),
    ]
    db['okt_harian'] = pd.DataFrame([{"Tanggal": r[0], "Salma_Meta": r[2], "Salma_CRM": r[3], "Aulia_Meta": r[4], "Aulia_CRM": r[5], "Nisa_Meta": r[6], "Nisa_CRM": r[7], "Total_Leads": r[8], "Total_CRM": r[9], "Total_Gabungan": r[10], "Salma": r[2]+r[3], "Aulia": r[4]+r[5], "Nisa": r[6]+r[7], "Total Donasi": r[10], "Donasi Final": r[10]} for r in harian_rows_base])

    db['spend_okt_kpi'] = {"total_spending": 0.0, "total_leads": 0, "avg_cpr": 0.0, "leads_closing": 1298, "nominal_closing": 205624456.0, "total_roas": 0.0, "avg_cpr_harian": 0.0, "spend_per_hari": 0.0, "leads_per_hari": 0.0}
    db['spend_okt_df'] = pd.DataFrame([{"Tanggal": r[0], "Hari": r[1], "Spending (Rp)": 0.0, "Leads": 0, "Rata-Rata CPR": 0.0, "Leads Closing": r[11], "Nominal Closing (Rp)": float(r[8]), "ROAS": 0.0, "Catatan / Evaluasi": "-"} for r in harian_rows_base])

    db['stok_rincian_baru'] = pd.DataFrame([
        {"Produk & Kategori": "Mushaf - Super Tajwid", "Kanal Promosi": "Meta Ads", "Siap Salur (Stiker)": 458, "Belum Siap (Proses)": 0, "Total Stok Fisik": 458},
        {"Produk & Kategori": "Mushaf - Al Wakaf (Meta Ads)", "Kanal Promosi": "Meta Ads", "Siap Salur (Stiker)": 2565, "Belum Siap (Proses)": 51, "Total Stok Fisik": 2616},
        {"Produk & Kategori": "Mushaf - Al Wakaf (TikTok)", "Kanal Promosi": "TikTok", "Siap Salur (Stiker)": 479, "Belum Siap (Proses)": 0, "Total Stok Fisik": 479},
        {"Produk & Kategori": "Buku Belajar Super Tahsin", "Kanal Promosi": "TikTok", "Siap Salur (Stiker)": 2224, "Belum Siap (Proses)": 0, "Total Stok Fisik": 2224},
        {"Produk & Kategori": "Titipan Mitra Yayasan Lain", "Kanal Promosi": "Yayasan Lain", "Siap Salur (Stiker)": 0, "Belum Siap (Proses)": 0, "Total Stok Fisik": 0},
        {"Produk & Kategori": "TOTAL INVENTARIS FISIK", "Kanal Promosi": "Semua Kanal", "Siap Salur (Stiker)": 5726, "Belum Siap (Proses)": 51, "Total Stok Fisik": 5777},
    ])
    db['stok_defisit_baru'] = pd.DataFrame([
        {"Periode / Komponen Analisis": "Kebutuhan Agustus 2026", "Target / Stok": "604", "Keterangan Operasional": "Realisasi: 0 Pcs", "Gap / Defisit": "604", "Status & Rekomendasi": "Belum Salur"},
        {"Periode / Komponen Analisis": "Kebutuhan September 2026", "Target / Stok": "2.599", "Keterangan Operasional": "Realisasi: 0 Pcs", "Gap / Defisit": "2.599", "Status & Rekomendasi": "Belum Salur"},
        {"Periode / Komponen Analisis": "Kebutuhan Oktober 2026", "Target / Stok": "1.818", "Keterangan Operasional": "Realisasi: 100 Pcs", "Gap / Defisit": "1.718", "Status & Rekomendasi": "Sebagian Salur"},
        {"Periode / Komponen Analisis": "Total Kebutuhan (Agust - Okt)", "Target / Stok": "5.021", "Keterangan Operasional": "Akumulasi 3 Bulan", "Gap / Defisit": "4.921", "Status & Rekomendasi": "Target Distribusi Aktif"},
        {"Periode / Komponen Analisis": "Total Stok Mushaf Meta LP", "Target / Stok": "3.074", "Keterangan Operasional": "Siap 3.023 + Proses 51", "Gap / Defisit": "(1.947)", "Status & Rekomendasi": "Kekurangan Meta LP"},
        {"Periode / Komponen Analisis": "KEKURANGAN MUSHAF META LP", "Target / Stok": "1.947", "Keterangan Operasional": "Defisit vs Stok Meta LP", "Gap / Defisit": "(1.947)", "Status & Rekomendasi": "WAJIB BELI 1.947 MUSHAF"},
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
    db['db_reminder'] = pd.DataFrame([{"Status Reminder": "CALLBACK SEGERA", "Jumlah Donatur": 12285, "Persentase (%)": "84,94%"}, {"Status Reminder": "PANTAU", "Jumlah Donatur": 1628, "Persentase (%)": "11,26%"}, {"Status Reminder": "AMAN", "Jumlah Donatur": 550, "Persentase (%)": "3,80%"}])
    db['db_status_donatur'] = pd.DataFrame([{"Status Donatur": "Donatur Churn", "Jumlah Donatur": 6933, "Persentase (%)": "47,93%"}, {"Status Donatur": "Donatur Baru", "Jumlah Donatur": 6894, "Persentase (%)": "47,66%"}, {"Status Donatur": "Donatur Aktif", "Jumlah Donatur": 492, "Persentase (%)": "3,40%"}, {"Status Donatur": "Donatur Rutin", "Jumlah Donatur": 145, "Persentase (%)": "1,00%"}])
    db['packing_dus_bulanan'] = pd.DataFrame([
        {"Bulan": "Januari", "Total Mushaf Terverifikasi": 2356, "Verifikasi (Belum Stiker)": 0, "Penamaan Mushaf (Stiker)": 0, "Packing / Proses Distribusi": 0, "Distribusi Selesai": 2356},
        {"Bulan": "Februari", "Total Mushaf Terverifikasi": 1906, "Verifikasi (Belum Stiker)": 0, "Penamaan Mushaf (Stiker)": 0, "Packing / Proses Distribusi": 0, "Distribusi Selesai": 1906},
        {"Bulan": "Maret", "Total Mushaf Terverifikasi": 3814, "Verifikasi (Belum Stiker)": 0, "Penamaan Mushaf (Stiker)": 0, "Packing / Proses Distribusi": 0, "Distribusi Selesai": 3814},
        {"Bulan": "April", "Total Mushaf Terverifikasi": 2225, "Verifikasi (Belum Stiker)": 0, "Penamaan Mushaf (Stiker)": 0, "Packing / Proses Distribusi": 0, "Distribusi Selesai": 2225},
        {"Bulan": "Mei", "Total Mushaf Terverifikasi": 1454, "Verifikasi (Belum Stiker)": 0, "Penamaan Mushaf (Stiker)": 0, "Packing / Proses Distribusi": 0, "Distribusi Selesai": 1454},
        {"Bulan": "Juni", "Total Mushaf Terverifikasi": 4103, "Verifikasi (Belum Stiker)": 0, "Penamaan Mushaf (Stiker)": 0, "Packing / Proses Distribusi": 0, "Distribusi Selesai": 4103},
        {"Bulan": "Juli", "Total Mushaf Terverifikasi": 3586, "Verifikasi (Belum Stiker)": 1, "Penamaan Mushaf (Stiker)": 0, "Packing / Proses Distribusi": 0, "Distribusi Selesai": 3585},
        {"Bulan": "Agustus", "Total Mushaf Terverifikasi": 2852, "Verifikasi (Belum Stiker)": 12, "Penamaan Mushaf (Stiker)": 0, "Packing / Proses Distribusi": 2840, "Distribusi Selesai": 0},
        {"Bulan": "September", "Total Mushaf Terverifikasi": 2599, "Verifikasi (Belum Stiker)": 1972, "Penamaan Mushaf (Stiker)": 447, "Packing / Proses Distribusi": 180, "Distribusi Selesai": 0},
        {"Bulan": "Oktober", "Total Mushaf Terverifikasi": 1818, "Verifikasi (Belum Stiker)": 1718, "Penamaan Mushaf (Stiker)": 0, "Packing / Proses Distribusi": 0, "Distribusi Selesai": 100},
    ])

    fb_data = {}
    try: fb_data = fetch_firebase_json()
    except: fb_data = {}

    db['firebase_connected'] = bool(fb_data and len(fb_data) >= 2)
    fb_time_str = str(fb_data.get("updated_at", "")).strip()

    g_ov = grid_to_df(fb_data.get("overview_semua_cs", []))
    g_okt = grid_to_df(fb_data.get("okt_dashboard_cs", []))
    g_spend = grid_to_df(fb_data.get("spend_okt", []))
    g_l_nisa = grid_to_df(fb_data.get("leads_nisa", []))
    g_l_salma = grid_to_df(fb_data.get("leads_salma", []))
    g_l_aulia = grid_to_df(fb_data.get("leads_aulia", []))
    g_stok = grid_to_df(fb_data.get("stok_monitoring", []))
    g_kal = grid_to_df(fb_data.get("kalender_okt", []))
    g_db_set = grid_to_df(fb_data.get("db_setting", []))

    if not g_ov.empty:
        t_fin_live = extract_anchored_table(g_ov, "Bulan", "Target Bulanan", stop_words=["Total Target", "Sisa Target"], max_rows=15)
        if not t_fin_live.empty:
            sync_status["Data Makro (Jan–Sep)"] = f"Firebase Live ({len(t_fin_live)} bln)"
            for _, r_live in t_fin_live.iterrows():
                b_name = str(r_live.get("Bulan", "")).strip()
                if b_name in db['macro_monthly']['Bulan'].values and b_name != "Oktober":
                    v_real, v_tgt, v_ads = num_clean(r_live.get("Realisasi Omset", 0)), num_clean(r_live.get("Target Bulanan", 0)), num_clean(r_live.get("Budget Iklan", 0))
                    if v_real > 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'Realisasi Finance'] = v_real
                    if v_tgt > 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'Target Bulanan'] = v_tgt
                    if v_ads > 0: db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == b_name, 'Budget Iklan'] = v_ads
        t_cs_live = extract_anchored_table(g_ov, "Nama CS", "Target Omset", stop_words=["Total", "Rata-rata"], max_rows=12)
        if not t_cs_live.empty:
            for _, r_c in t_cs_live.iterrows():
                c_name = str(r_c.get("Nama CS", "")).strip()
                if c_name in db['cs_overview']['Nama CS'].values:
                    for m_col in ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September"]:
                        if m_col in t_cs_live.columns: db['cs_overview'].loc[db['cs_overview']['Nama CS'] == c_name, m_col] = num_clean(r_c.get(m_col, 0))
    else: sync_status["Data Makro (Jan–Sep)"] = "Baseline Aktif"

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
            ads_now = float(db['okt_finance_mon'].get('budget_iklan', 248087884))
            if tot_meta_okt > 0 and ads_now > 0 and "roas_akuisisi" not in mon_fin:
                db['okt_finance_mon']['roas_akuisisi'] = round(tot_meta_okt / ads_now, 2)

        t_har_2row = parse_rekap_harian_cs_2row(g_okt)
        if not t_har_2row.empty:
            db['okt_harian'] = t_har_2row
            sync_status["Dashboard CS Oktober"] = f"Firebase Live ({len(t_har_2row[t_har_2row['Total_Gabungan'] > 0])} hari)"
        else: sync_status["Dashboard CS Oktober"] = "Firebase Live"
    else: sync_status["Dashboard CS Oktober"] = "Baseline Aktif"

    if g_spend.empty: g_spend = fetch_direct_sheet("leads_cs", "DATA SPEND OKTOBER")
    if not g_spend.empty:
        kpi_sp_live, df_sp_live = parse_data_spend_oktober(g_spend)
        if not df_sp_live.empty:
            db['spend_okt_kpi'], db['spend_okt_df'] = kpi_sp_live, df_sp_live
            sync_status["Data Spend Oktober"] = f"Live ({len(df_sp_live)} hari)"
        else: sync_status["Data Spend Oktober"] = "Live Connected"
    else: sync_status["Data Spend Oktober"] = "Baseline 28 Okt"

    live_leads_all = []
    for g_l, cs_lbl in [(g_l_nisa, "Nisa"), (g_l_salma, "Salma"), (g_l_aulia, "Aulia")]:
        if not g_l.empty: live_leads_all.extend(parse_live_leads_tab(g_l, cs_lbl))

    active_har_dates = db['okt_harian'][db['okt_harian']['Total_Gabungan'] > 0]['Tanggal'].tolist() if not db['okt_harian'].empty else []
    max_har_date = max(active_har_dates) if active_har_dates else "2026-10-16"
    max_lead_date = max([x[1] for x in live_leads_all], default="2026-10-01")

    if max_lead_date < max_har_date:
        direct_leads = []
        with ThreadPoolExecutor(max_workers=3) as ex:
            f_map = {ex.submit(fetch_direct_sheet, "leads_cs", t_nm): c_lb for t_nm, c_lb in [("CS NISA", "Nisa"), ("CS SALMA", "Salma"), ("CS AUL", "Aulia")]}
            for f in as_completed(f_map):
                try:
                    df_d = f.result()
                    if not df_d.empty: direct_leads.extend(parse_live_leads_tab(df_d, f_map[f]))
                except: pass
        if len(direct_leads) > len(live_leads_all): live_leads_all = direct_leads

    cols_leads = ["Nama CS", "Tanggal", "Chat Valid", "Chat Invalid", "Closing", "Nominal", "SantriQu_Leads", "SantriQu_Closing", "SantriQu_Nominal", "JariyahQu_Leads", "JariyahQu_Closing", "JariyahQu_Nominal", "AmalQu_Leads", "AmalQu_Closing", "AmalQu_Nominal", "Total Follow Up"]
    df_leads = pd.DataFrame(live_leads_all, columns=cols_leads) if len(live_leads_all) >= 3 else pd.DataFrame(columns=cols_leads)
    df_leads["Conv Rate (%)"] = np.where(df_leads["Chat Valid"] > 0, (df_leads["Closing"] / df_leads["Chat Valid"] * 100).round(1), 0.0)
    db['leads_okt'] = df_leads
    sync_status["Leads & CR Harian"] = f"Live ({len(df_leads)} baris)" if not df_leads.empty else "Menunggu Input"

    cr_by_date_all = df_leads.groupby("Tanggal", as_index=False).agg({"Chat Valid": "sum", "Closing": "sum"}) if not df_leads.empty else pd.DataFrame(columns=["Tanggal", "Chat Valid", "Closing"])
    cr_map_all = {r["Tanggal"]: round(r["Closing"] / r["Chat Valid"] * 100, 1) for _, r in cr_by_date_all.iterrows() if r["Chat Valid"] > 0}
    tot_v_all, tot_c_all = int(df_leads["Chat Valid"].sum()), int(df_leads["Closing"].sum())
    db['tot_leads_valid_okt'] = tot_v_all if tot_v_all > 0 else 1747
    db['avg_cr_okt'] = round(tot_c_all / tot_v_all * 100, 1) if tot_v_all > 0 else 74.3

    df_har = db['okt_harian'].copy()
    df_har['CR_Harian_Pct'] = df_har['Tanggal'].map(lambda d: cr_map_all.get(str(d).strip(), np.nan))
    db['okt_harian'] = df_har

    if not g_stok.empty:
        parsed_s = parse_stok_dashboard_new(g_stok)
        if "rincian_inventaris" in parsed_s: db['stok_rincian_baru'] = parsed_s["rincian_inventaris"]
        if "analisis_defisit" in parsed_s: db['stok_defisit_baru'] = parsed_s["analisis_defisit"]
        sync_status["Stok Mushaf Real-Time"] = "Firebase Live"
    else: sync_status["Stok Mushaf Real-Time"] = "Baseline 28 Okt"

    for cn in ["Siap Salur (Stiker)", "Belum Siap (Proses)", "Total Stok Fisik"]:
        if cn not in db['stok_rincian_baru'].columns: db['stok_rincian_baru'][cn] = 0
        else: db['stok_rincian_baru'][cn] = db['stok_rincian_baru'][cn].apply(lambda x: int(num_clean(x)))

    kal_base = [
        (1, "2026-10-15", "AQ-2026-081", "Penyaluran Jatikramat Bekasi", "PIC Lembaga", "Terdaftar", "Jatikramat, Kec. Jatiasih, Kota Bekasi", 5, "Al Wakaf Tiktok", "[Success]"),
        (2, "2026-10-16", "AQ-2026-082", "Muhammadiyah Wil Jabar", "PIC Muhammadiyah", "Terdaftar", "Muhammadiyah Wil Jabar", 200, "Super Tajwid", "[Success]"),
        (3, "2026-10-17", "AQ-2026-083", "Al Qosbah Bandung", "PIC Al Qosbah", "Terdaftar", "Al Qosbah Bandung", 150, "Al Wakaf Tiktok", "[Success]"),
        (4, "2026-10-18", "AQ-2026-084", "SMP Plus Ibnu Rusyd", "PIC Ibnu Rusyd", "Terdaftar", "SMP Plus Ibnu Rusyd", 450, "Al Wakaf Tiktok", "[Success]"),
        (5, "2026-10-19", "AQ-2026-085", "Lembaga Mitra Wakaf", "PIC Mitra", "Terdaftar", "Jawa Barat", 200, "Al Wakaf Tiktok", "[Success]"),
        (6, "2026-10-20", "AQ-2026-087", "MDU AL-ITTIHAD CIHERANG CIPELAH", "Abdul Karim", "Terdaftar", "Rancabali, Kab. Bandung", 108, "Super Tajwid", "[Success]"),
        (7, "2026-10-22", "AQ-2026-074", "TPA Al Hijrah", "Arip Rohman", "Terdaftar", "Sidomulyo, Kab. Lampung Selatan", 45, "Super Tajwid", "[Success]"),
        (8, "2026-10-22", "AQ-2026-105", "IRMA Baitul Ummah", "Hj. Intan Margaretha F.", "Terdaftar", "SMKN 1 Katapang, Kab. Bandung", 200, "Super Tajwid", "[Success]"),
        (9, "2026-10-23", "AQ-2026-008", "KBMA Desa Margahayu Selatan", "Ibu Ade", "Terdaftar", "Masjid Alfurqon", 50, "Super Tajwid", "[Success]"),
        (10, "2026-10-24", "AQ-2026-058", "Majelis Ta'lim Ciparay", "Bu. Dadang / Nur Erlina", "Terdaftar", "Ciparay, Kab. Bandung", 150, "Super Tajwid", "[Success]"),
        (11, "2026-10-27", "AQ-2026-026", "SD Plus Al Furqan", "Dedeh Kurniati", "Terdaftar", "SD PLUS AL FURQON CIMAHI", 114, "Al Wakaf Tiktok", "[Success]"),
        (12, "2026-10-27", "AQ-2026-059", "Yayasan Bahtera Peradaban Cendekia", "Rona Rohmana", "Terdaftar", "Saguling, Kab. Bandung Barat", 67, "Al Wakaf Tiktok", "[Scheduled]"),
        (13, "2026-10-29", "AQ-2026-072", "TPQ Tarbiyatul Aulad", "Ust. Fandy Abdillah", "Terdaftar", "Sukanagara, Kab. Cianjur", 70, "Al Wakaf Tiktok", "[Scheduled]"),
        (14, "2026-10-31", "AQ-2026-104", "MDTA Darul Jannah", "Ai Neni", "Terdaftar", "Jawa Barat", 100, "Al Wakaf Tiktok", "[Scheduled]"),
    ]
    db['kalender_okt'] = pd.DataFrame(kal_base, columns=["No", "Tanggal Agenda", "ID Proyek", "Nama Lembaga Penerima", "Nama PIC", "Kontak WA", "Wilayah / Titik Lokasi", "Jumlah Mushaf (Pcs)", "Variasi Mushaf", "Status"])

    if not g_kal.empty:
        t_kal = extract_anchored_table(g_kal, "No", "Tanggal Agenda", stop_words=["TOTAL"], max_rows=80)
        if t_kal.empty: t_kal = extract_anchored_table(g_kal, "Tanggal Agenda", "ID Proyek", stop_words=["TOTAL"], max_rows=80)
        if not t_kal.empty:
            cols_aj = t_kal.columns[:10].tolist()
            t_kal_aj = t_kal[cols_aj].copy()
            if "Jumlah Mushaf (Pcs)" in t_kal_aj.columns: t_kal_aj["Jumlah Mushaf (Pcs)"] = t_kal_aj["Jumlah Mushaf (Pcs)"].apply(lambda x: int(num_clean(x)))
            if "Tanggal Agenda" in t_kal_aj.columns: t_kal_aj["Tanggal Agenda"] = t_kal_aj["Tanggal Agenda"].replace("", np.nan).ffill().fillna("")
            t_kal_aj = t_kal_aj[t_kal_aj["Jumlah Mushaf (Pcs)"] > 0]
            if not t_kal_aj.empty:
                db['kalender_okt'] = t_kal_aj.reset_index(drop=True)
                sync_status["Kalender Distribusi"] = f"Firebase Live ({len(t_kal_aj)} titik)"
    if "Kalender Distribusi" not in sync_status: sync_status["Kalender Distribusi"] = f"Live ({len(db['kalender_okt'])} titik)"

    if not g_db_set.empty:
        parsed_db_s = parse_setting_dashboard_crm(g_db_set)
        if "segmentasi" in parsed_db_s: db['db_segmentasi'] = parsed_db_s["segmentasi"]
        if "reminder" in parsed_db_s: db['db_reminder'] = parsed_db_s["reminder"]
        if "status_donatur" in parsed_db_s: db['db_status_donatur'] = parsed_db_s["status_donatur"]
        sync_status["Master Database CRM"] = "Firebase Live"
    else: sync_status["Master Database CRM"] = "Baseline Aktif"

    df_inv, df_def, df_kal = db['stok_rincian_baru'], db['stok_defisit_baru'], db['kalender_okt']

    def get_inv_row(kw):
        m = df_inv[df_inv['Produk & Kategori'].astype(str).str.contains(kw, case=False, na=False)]
        if not m.empty:
            r = m.iloc[0]
            return int(num_clean(r.get("Siap Salur (Stiker)", 0))), int(num_clean(r.get("Belum Siap (Proses)", 0))), int(num_clean(r.get("Total Stok Fisik", 0)))
        return 0, 0, 0

    def get_def_val(kw, col_name="Target / Stok", default_v=0):
        m = df_def[df_def['Periode / Komponen Analisis'].astype(str).str.contains(kw, case=False, na=False)]
        if not m.empty and col_name in m.columns:
            v = int(abs(num_clean(m.iloc[0][col_name])))
            if v > 0: return v
        return default_v

    st_siap, st_belum, st_tot = get_inv_row("Super Tajwid")
    aw_m_siap, aw_m_belum, aw_m_tot = get_inv_row("Al Wakaf \\(Meta")
    aw_t_siap, aw_t_belum, aw_t_tot = get_inv_row("Al Wakaf \\(TikTok")
    bt_siap, bt_belum, bt_tot = get_inv_row("Super Tahsin")

    keb_agust = get_def_val("Agustus", "Target / Stok", 604)
    keb_sept = get_def_val("September", "Target / Stok", 2599)
    keb_okt = get_def_val("Oktober", "Target / Stok", 1818)
    gap_okt = get_def_val("Oktober", "Gap / Defisit", 1718)
    keb_3bln = get_def_val("Total Kebutuhan", "Target / Stok", keb_agust + keb_sept + keb_okt)
    gap_3bln = get_def_val("Total Kebutuhan", "Gap / Defisit", 4921)

    meta_lp_siap = st_siap + aw_m_siap
    meta_lp_belum = st_belum + aw_m_belum
    meta_lp_total = st_tot + aw_m_tot
    kekurangan_meta_lp = max(0, keb_3bln - meta_lp_total)

    stok_mushaf_gabungan = meta_lp_total + aw_t_tot
    selisih_gabungan_vs_3bln = stok_mushaf_gabungan - keb_3bln
    selisih_gabungan_vs_okt = stok_mushaf_gabungan - keb_okt
    tot_jadwal_kalender = int(df_kal['Jumlah Mushaf (Pcs)'].sum()) if not df_kal.empty else 1909
    selisih_gabungan_vs_kalender = stok_mushaf_gabungan - tot_jadwal_kalender

    db['macro_monthly'].loc[db['macro_monthly']['Bulan'] == 'Oktober', 'Mushaf Terverifikasi'] = keb_okt
    df_m = db['macro_monthly']
    df_m['Laba Bersih'] = df_m['Realisasi Finance'] - df_m['Total Pengeluaran']
    df_m['ROFI'] = np.where(df_m['Budget Iklan'] > 0, (df_m['Realisasi Finance'] / df_m['Budget Iklan']).round(2), 0.0)
    df_m['ROAS_Est'] = np.where(df_m['Bulan'] == 'Oktober', db['okt_finance_mon'].get('roas_akuisisi', 0.83), (df_m['ROFI'] * 0.72).round(2))
    df_m['Selisih Target'] = df_m['Realisasi Finance'] - df_m['Target Bulanan']
    df_m['Selisih Finance vs CS'] = df_m['Realisasi Finance'] - df_m['Omset CS']
    df_m['% Capaian'] = np.where(df_m['Target Bulanan'] > 0, (df_m['Realisasi Finance'] / df_m['Target Bulanan'] * 100).round(1), 0.0)

    db['stok_audit'] = {
        "meta_lp_siap": meta_lp_siap, "meta_lp_belum": meta_lp_belum, "meta_lp_total": meta_lp_total,
        "kekurangan_meta_lp": kekurangan_meta_lp,
        "tiktok_mushaf_siap": aw_t_siap, "tiktok_mushaf_belum": aw_t_belum, "tiktok_mushaf_total": aw_t_tot,
        "buku_tahsin_siap": bt_siap, "buku_tahsin_belum": bt_belum, "buku_tahsin_total": bt_tot,
        "mushaf_siap_all": meta_lp_siap + aw_t_siap,
        "keb_agust": keb_agust, "keb_sept": keb_sept, "kebutuhan_okt": keb_okt, "gap_okt": gap_okt,
        "kebutuhan_agust_okt": keb_3bln, "gap_agust_okt": gap_3bln,
        "stok_fisik_mushaf_tersedia": stok_mushaf_gabungan,
        "defisit_agust_okt": abs(min(0, selisih_gabungan_vs_3bln)),
        "selisih_gabungan_vs_3bln": selisih_gabungan_vs_3bln,
        "selisih_gabungan_vs_okt": selisih_gabungan_vs_okt,
        "tot_jadwal_kalender": tot_jadwal_kalender,
        "selisih_gabungan_vs_kalender": selisih_gabungan_vs_kalender,
        "total_inventaris_fisik": stok_mushaf_gabungan + bt_tot,
        "total_inventaris_siap": meta_lp_siap + aw_t_siap + bt_siap,
        "st_siap": st_siap, "st_belum": st_belum, "st_total": st_tot,
        "aw_meta_siap": aw_m_siap, "aw_meta_belum": aw_m_belum, "aw_meta_total": aw_m_tot,
        "bt_siap": bt_siap, "bt_belum": bt_belum, "bt_total": bt_tot
    }

    db['sync_status'] = sync_status
    db['last_sync'] = fb_time_str if fb_time_str else now_wib().strftime("%d %b %Y • %H:%M:%S WIB")
    return db

@st.cache_data(ttl=120, show_spinner=False)
def load_lazy_contacts_db(sync_token: int):
    sid, _ = SHEETS_CONFIG["master_db"]
    cb = int(time.time() * 1000)
    for u_db in [f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv&headers=0&sheet=DATABASE&cb={cb}"]:
        try:
            df_raw = read_csv_nocache(u_db)
            if not df_raw.empty and df_raw.shape[1] >= 4:
                hdr_idx = 0
                for r_i in range(min(15, len(df_raw))):
                    row_txt = " ".join(str(x).lower() for x in df_raw.iloc[r_i].values)
                    if "nama" in row_txt and ("whatsapp" in row_txt or "hp" in row_txt or "program" in row_txt): hdr_idx = r_i; break
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
                    elif "program" in cl and "Program" not in col_map.values(): col_map[c] = "Program"
                    elif ("donasi terakhir" in cl or "tanggal" in cl) and "Donasi Terakhir" not in col_map.values(): col_map[c] = "Donasi Terakhir"
                    elif ("kategori" in cl or "status donatur" in cl) and "Kategori" not in col_map.values(): col_map[c] = "Kategori"
                    elif ("prioritas" in cl or "segmen" in cl) and "Prioritas" not in col_map.values(): col_map[c] = "Prioritas"
                    elif "reminder" in cl and "Reminder" not in col_map.values(): col_map[c] = "Reminder"
                    elif "fu1" in cl or "sapaan" in cl: col_map[c] = "FU1 (Sapaan)"
                    elif "fu3" in cl or "laporan" in cl: col_map[c] = "FU3 (Laporan Penyaluran)"
                df_c.rename(columns=col_map, inplace=True)
                df_c = df_c.loc[:, ~df_c.columns.duplicated()]
                for req in ["Nama Donatur", "Nomor Whatsapp", "PiC", "Program", "Donasi Terakhir", "Kategori", "Prioritas", "Reminder", "FU1 (Sapaan)", "FU3 (Laporan Penyaluran)"]:
                    if req not in df_c.columns: df_c[req] = "-"
                    else: df_c[req] = df_c[req].fillna("-").astype(str).str.strip()
                df_c = df_c[(df_c["Nama Donatur"] != "") & (df_c["Nama Donatur"] != "-") & (~df_c["Nama Donatur"].str.lower().str.contains("nama donatur"))]
                if len(df_c) >= 5: return df_c.reset_index(drop=True), False
        except: continue
    sample = pd.DataFrame([
        {"Nama Donatur": "Donatur Prioritas A1", "Nomor Whatsapp": "628000000001", "PiC": "CS Nisa", "Program": "Waqaf/Mushaf", "Donasi Terakhir": "1 Oktober 2026", "Kategori": "Donatur Rutin", "FU1 (Sapaan)": "Sudah", "FU3 (Laporan Penyaluran)": "Sudah", "Prioritas": "A1", "Reminder": "AMAN"},
        {"Nama Donatur": "Donatur Aktif B1", "Nomor Whatsapp": "628000000002", "PiC": "CS Salma", "Program": "AmalQu", "Donasi Terakhir": "2 Oktober 2026", "Kategori": "Donatur Aktif", "FU1 (Sapaan)": "Sudah", "FU3 (Laporan Penyaluran)": "Belum", "Prioritas": "B1", "Reminder": "PANTAU"},
        {"Nama Donatur": "Donatur Baru Reguler", "Nomor Whatsapp": "628000000003", "PiC": "CS Aulia", "Program": "AmalQu", "Donasi Terakhir": "5 Oktober 2026", "Kategori": "Donatur Baru", "FU1 (Sapaan)": "Belum", "FU3 (Laporan Penyaluran)": "Belum", "Prioritas": "Reguler", "Reminder": "CALLBACK SEGERA"},
        {"Nama Donatur": "Donatur Reaktivasi D4", "Nomor Whatsapp": "628000000004", "PiC": "CRM Olive", "Program": "Waqaf/Mushaf", "Donasi Terakhir": "14 Februari 2026", "Kategori": "Donatur Churn", "FU1 (Sapaan)": "Belum", "FU3 (Laporan Penyaluran)": "Belum", "Prioritas": "D4", "Reminder": "CALLBACK SEGERA"},
    ])
    return sample, True

current_sync_token = int(time.time() // 30) + (st.session_state.sync_nonce * 100000)
db = load_core_realtime_data(current_sync_token)
df_macro = db['macro_monthly']
sa = db['stok_audit']

# ==============================================================================
# 7. SIDEBAR NAVIGASI & STATUS FIREBASE
# ==============================================================================
with st.sidebar:
    render_html(f'<div style="display:flex;align-items:center;gap:12px;padding:4px 4px 18px 4px;border-bottom:1px solid var(--border-soft);margin-bottom:14px;">{build_logo_html(44)}<div><div class="brand-title" style="font-family:\'Outfit\',sans-serif!important;font-weight:800;font-size:21px;line-height:1.15;">AmalQu</div><div class="brand-sub" style="font-size:11px;font-weight:600;line-height:1.3;margin-top:2px;">Yayasan AmalQu Indonesia Peduli</div></div></div><div style="font-size:11px;font-weight:700;color:var(--text-muted)!important;letter-spacing:0.8px;text-transform:uppercase;padding:4px 6px 8px 6px;">MENU DIVISI ({user_role.upper()})</div>')
    menu_pilihan = st.radio("Navigasi Utama", allowed_menus, label_visibility="collapsed")
    fb_lbl = "● Firebase Realtime Aktif" if db.get("firebase_connected") else "● Mode Cadangan (Run Apps Script)"
    fb_col = "#10B981" if db.get("firebase_connected") else "#F59E0B"
    render_html(f'<div class="sub-box" style="margin-top:16px;padding:13px 14px;border-radius:14px;"><div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;"><i class="ri-shield-user-line" style="color:#6366F1!important;font-size:16px;"></i><span style="font-size:12.5px;font-weight:700;">{current_user["username_display"]} ({user_role})</span></div><div style="font-size:11px;color:var(--text-secondary)!important;line-height:1.45;">{current_user["title"]}<br><span style="color:{fb_col}!important;font-weight:700;">{fb_lbl}</span><br><span style="font-size:10.5px;color:var(--text-muted)!important;">Update: {db["last_sync"]}</span></div></div>')
    with st.expander("📡 Detail Koneksi Modul"):
        for mod_name, stat_txt in db.get("sync_status", {}).items():
            st.caption(f"🟢 **{mod_name}**: {stat_txt}")
    sb_col1, sb_col2 = st.columns(2)
    with sb_col1:
        if st.button("🔄 Sync Data", use_container_width=True):
            st.session_state.sync_nonce += 1; st.cache_data.clear(); st.rerun()
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
    render_html(f'<div class="bento-card kpi-uniform"><div style="display:flex;justify-content:space-between;align-items:center;gap:8px;"><span style="font-size:12px;font-weight:600;color:var(--text-secondary)!important;line-height:1.25;">{title}</span><div class="icon-box {ib_map.get(color_theme, "ib-indigo")}"><i class="{icon_cls}"></i></div></div><div class="kpi-val-fluid">{value}</div><div style="display:flex;align-items:center;justify-content:space-between;gap:6px;flex-wrap:wrap;"><span class="badge-pill {bp_map.get(badge_theme, "bp-green")}"><i class="{arrow_ic}"></i> {badge_text}</span><span style="font-size:10.5px;color:var(--text-muted)!important;font-weight:600;">{subtext}</span></div></div>')

def step_item_html(title, sub, val, color, is_last=False):
    mb = "0" if is_last else "7px"
    return f'<div class="satpam-step" style="border-left:4px solid {color};margin-bottom:{mb};"><div><div style="font-size:12px;font-weight:700;">{title}</div><div style="font-size:10.5px;color:var(--text-muted)!important;">{sub}</div></div><div class="satpam-val" style="color:{color}!important;">{val}</div></div>'

def render_satpam_5_highlight_card(sm_dict, title_box="Satpam Keuangan: 5 Indikator Utama"):
    if sm_dict['selisih_saldo_beli'] >= 0:
        lbl_no4 = "4. Surplus Saldo Pembelian (Tanpa Potong Cashback)"
        sub_no4 = f"Saldo Pembelian 65% berlebih +{rp(sm_dict['selisih_saldo_beli'])} • Potong Cashback: Rp 0"
        val_no4, col_no4 = f"+{rp(sm_dict['selisih_saldo_beli'])}", "#10B981"
    else:
        lbl_no4 = "4. Kekurangan Saldo Pembelian & Potong Cashback"
        sub_no4 = f"Kurang {rp(sm_dict['kekurangan_saldo_beli'])} • Dipotong dari Cashback: {rp(sm_dict['potong_dari_cashback'])}" + (f" (Sisa Defisit: {rp(sm_dict['sisa_defisit_setelah_cb'])})" if sm_dict['sisa_defisit_setelah_cb'] > 0 else "")
        val_no4, col_no4 = f"-{rp(sm_dict['kekurangan_saldo_beli'])}", "#EF4444"
    col_cb_akhir = "#10B981" if sm_dict['cashback_akhir'] > 0 else "#EF4444"

    s1 = step_item_html("1. Saldo Pembelian Mushaf (65% dari DSD)", "Sudah dipotong Biaya Iklan, Operasional 10% & Cashback 35%", rp(sm_dict['saldo_beli_mushaf_65']), "#6366F1")
    s2 = step_item_html("2. Saldo Cashback Awal (35% dari DSD)", "Kas cadangan abadi sebelum dipotong untuk talangan beli mushaf", rp(sm_dict['saldo_cashback_awal_35']), "#10B981")
    s3 = step_item_html(f"3. Biaya Pembelian Mushaf ({sm_dict['jml_mushaf']:,} Pcs × {rp(sm_dict['hpp'])})", sm_dict['lbl_kebutuhan'], rp(sm_dict['biaya_beli_mushaf']), "#F97316")
    s4 = step_item_html(lbl_no4, sub_no4, val_no4, col_no4)
    s5 = step_item_html("5. Cashback Akhir (Kalau Dipotong Kekurangan Beli)", "Sisa bersih Saldo Cashback 35% setelah talangan beli mushaf", rp(sm_dict['cashback_akhir']), col_cb_akhir, is_last=True)

    render_html(f'<div class="bento-card" style="min-height:400px;display:flex;flex-direction:column;justify-content:space-between;"><div><div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap;"><span style="font-family:\'Outfit\',sans-serif!important;font-weight:800;font-size:14.8px;"><i class="ri-shield-star-fill" style="color:#6366F1!important;"></i> {title_box}</span><span class="badge-pill bp-{sm_dict["badge_col"]}">{sm_dict["status_txt"]}</span></div><div style="font-size:11px;color:var(--text-secondary)!important;margin-bottom:8px;padding:6px 10px;background:var(--bg-subcard);border-radius:8px;">Donasi: <b>{rp_short(sm_dict["donasi"])}</b> − Iklan: <b>{rp_short(sm_dict["iklan"])}</b> − Ops 10%: <b>{rp_short(sm_dict["beban_ops_10"])}</b> → <b>DSD: {rp(sm_dict["dsd"])}</b></div>{s1}{s2}{s3}{s4}{s5}</div></div>')

def render_chart_header(title_text, subtitle_text="", badge_text="", badge_theme="indigo"):
    bp_map = {"green": "bp-green", "red": "bp-red", "orange": "bp-orange", "indigo": "bp-indigo"}
    badge_html = f'<span class="badge-pill {bp_map.get(badge_theme, "bp-indigo")}">{badge_text}</span>' if badge_text else ""
    sub_html = f'<div style="font-size:11.5px;color:var(--text-muted)!important;margin-top:2px;">{subtitle_text}</div>' if subtitle_text else ""
    render_html(f'<div class="chart-header-box"><div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;"><div style="min-width:0;"><div style="font-family:\'Outfit\',sans-serif!important;font-size:15.5px;font-weight:700;color:var(--text-primary)!important;">{title_text}</div>{sub_html}</div>{badge_html}</div></div>')

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

def render_saas_table(df: pd.DataFrame, max_rows=80):
    if df is None or df.empty:
        render_html('<div class="bento-card"><p style="color:var(--text-muted)!important;margin:0;">Data tidak ditemukan untuk filter ini.</p></div>')
        return
    df_show = df.head(max_rows).copy()
    ths = "".join([f"<th>{str(c)}</th>" for c in df_show.columns])
    trs = ""
    for _, row in df_show.iterrows():
        first_val = str(row.iloc[0]).upper()
        tr_cls = ' class="row-summary"' if "TOTAL" in first_val or "KEKURANGAN" in first_val or "5. DONASI SIAP" in first_val else ""
        tds = ""
        for col_name in df_show.columns:
            val_str = str(row[col_name])
            low_v = val_str.lower()
            if any(k in low_v for k in ["success", "sukses", "tercapai", "aktif", "siap salur cukup", "stok cukup", "tersedia", "selesai", "aman", "sudah", "sebagian salur", "surplus", "sempurna"]) and "tidak" not in low_v and "non-aktif" not in low_v and "belum" not in low_v:
                cell_html = f'<span class="badge-pill bp-green"><i class="ri-checkbox-circle-fill"></i> {val_str}</span>'
            elif any(k in low_v for k in ["tidak tercapai", "non-aktif", "defisit", "kritis", "habis", "callback segera", "churn", "kurang", "wajib beli", "belum cukup", "kekurangan"]):
                cell_html = f'<span class="badge-pill bp-red"><i class="ri-error-warning-fill"></i> {val_str}</span>'
            elif any(k in low_v for k in ["scheduled", "perlu", "proses", "menipis", "pantau", "belum", "realtime", "reguler", "plafon", "saldo"]):
                cell_html = f'<span class="badge-pill bp-orange"><i class="ri-time-fill"></i> {val_str}</span>'
            elif col_name in ["Nama CS", "CS / CRM", "Bulan", "Nama Lembaga Penerima", "Nama Donatur", "Jenis Produk", "Produk & Kategori", "Periode / Komponen Analisis", "Komponen Arus Kas Yayasan"]:
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
        rows_html += (f"<tr><td style='font-weight:700;'>{r['Tanggal']}</td><td>{rp_dash(r['Salma_Meta'])}</td><td>{rp_dash(r['Salma_CRM'])}</td>"
                      f"<td>{rp_dash(r['Aulia_Meta'])}</td><td>{rp_dash(r['Aulia_CRM'])}</td><td>{rp_dash(r['Nisa_Meta'])}</td><td>{rp_dash(r['Nisa_CRM'])}</td>"
                      f"<td style='font-weight:600;'>{rp_dash(r['Total_Leads'])}</td><td style='font-weight:600;'>{rp_dash(r['Total_CRM'])}</td>"
                      f"<td style='font-weight:700;color:#10B981!important;'>{rp_dash(r['Total_Gabungan'])}</td><td style='text-align:center;'>{cr_txt}</td></tr>")
    rows_html += (f"<tr class='row-summary'><td>TOTAL</td><td>{rp_dash(sum_s_m)}</td><td>{rp_dash(sum_s_c)}</td><td>{rp_dash(sum_a_m)}</td><td>{rp_dash(sum_a_c)}</td>"
                  f"<td>{rp_dash(sum_n_m)}</td><td>{rp_dash(sum_n_c)}</td><td>{rp_dash(sum_leads)}</td><td>{rp_dash(sum_crm)}</td><td>{rp_dash(sum_gab)}</td><td style='text-align:center;'>Rata-rata CR</td></tr>"
                  f"<tr class='row-grand'><td>TOTAL KESELURUHAN</td><td colspan='2' style='text-align:center;color:#10B981!important;'>Salma: {rp_dash(sum_s_m + sum_s_c)}</td>"
                  f"<td colspan='2' style='text-align:center;color:#10B981!important;'>Aulia: {rp_dash(sum_a_m + sum_a_c)}</td><td colspan='2' style='text-align:center;color:#10B981!important;'>Nisa: {rp_dash(sum_n_m + sum_n_c)}</td>"
                  f"<td>{rp_dash(sum_leads)}</td><td>{rp_dash(sum_crm)}</td><td style='color:#6366F1!important;'>{rp_dash(sum_gab)}</td><td style='text-align:center;'><span class='badge-pill bp-indigo'>{avg_cr_val:.1f}%</span></td></tr>")
    render_html(f'<div class="saas-table-wrap"><table class="saas-table"><thead><tr><th rowspan="2" style="vertical-align:middle;">Tanggal</th><th colspan="2" style="text-align:center;border-bottom:1px solid var(--border-strong);">Salma</th><th colspan="2" style="text-align:center;border-bottom:1px solid var(--border-strong);">Aulia</th><th colspan="2" style="text-align:center;border-bottom:1px solid var(--border-strong);">Nisa</th><th rowspan="2" style="vertical-align:middle;">Total Leads</th><th rowspan="2" style="vertical-align:middle;">Total CRM</th><th rowspan="2" style="vertical-align:middle;">Total Gabungan</th><th rowspan="2" style="vertical-align:middle;text-align:center;">CR Harian (%)</th></tr><tr><th>Leads Meta</th><th>CRM</th><th>Leads Meta</th><th>CRM</th><th>Leads Meta</th><th>CRM</th></tr></thead><tbody>{rows_html}</tbody></table></div>')

# ==============================================================================
# 9. TOP HEADER BAR
# ==============================================================================
hdr_col_left, hdr_col_right = st.columns([7.5, 1.1])
with hdr_col_left:
    render_html(f'<div class="bento-card" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;padding:12px 18px!important;margin-bottom:12px!important;"><div style="display:flex;align-items:center;gap:12px;">{build_logo_html(40)}<div><div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;"><span style="font-family:\'Outfit\',sans-serif!important;font-size:20px;font-weight:800;">AmalQu</span><span class="badge-pill bp-orange">{menu_pilihan}</span></div><div style="font-size:12px;font-weight:600;color:var(--text-secondary)!important;">Yayasan AmalQu Indonesia Peduli • Enterprise Command Center</div></div></div><div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;"><span class="badge-pill bp-indigo"><i class="ri-user-star-line"></i> {current_user["username_display"]} ({user_role})</span><span class="badge-pill bp-green"><i class="ri-database-2-fill" style="font-size:11px;"></i> {db["last_sync"]}</span></div></div>')
with hdr_col_right:
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("☀️ Terang" if is_dark else "🌙 Gelap", key="top_theme_toggle", use_container_width=True):
        st.session_state.dark_mode = not st.session_state.dark_mode; st.rerun()

# ==============================================================================
# HALAMAN 1: DASHBOARD OVERVIEW (ZERO DROPDOWN, 3 ZONA BERSIH & FOKUS META LP)
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
    hari_cutoff = int(fm.get('hari_cutoff', 28))
    laju_harian_real = float(fm.get('avg_donasi_hari', real_okt / max(1, hari_cutoff)))
    proyeksi_akhir_bulan_real = float(fm.get('estimasi_akhir_bulan', laju_harian_real * 31))

    non_tot_s = db['okt_sumber'][db['okt_sumber']['CS / CRM'].astype(str).str.upper() != 'TOTAL']
    leads_meta_okt = float(non_tot_s['Leads Meta'].sum()) if not non_tot_s.empty else 205624456.0
    sm_ov = hitung_satpam_spreadsheet(real_okt, ads_okt, sa, hpp_unit=20000.0, leads_meta_val=leads_meta_okt, mode_kebutuhan="meta_lp")
    roas_okt_val = float(fm.get('roas_akuisisi', sm_ov['roas_meta']))
    rofi_okt_val = float(fm.get('rofi_real', sm_ov['rofi_real']))
    tot_fin_ytd = df_macro['Realisasi Finance'].sum()

    render_html('<div class="section-divider"><i class="ri-funds-box-line" style="color:#6366F1!important;"></i> 1. RINGKASAN EKSEKUTIF KEUANGAN & TARGET BULAN INI</div>')
    c1, c2, c3, c4 = st.columns(4)
    with c1: render_bento_kpi("ri-bank-line", "indigo", "Realisasi Finance (Okt)", rp_short(real_okt), f"{(real_okt/target_okt)*100:.1f}% Target", "indigo", f"YTD: {rp_short(tot_fin_ytd)}")
    with c2: render_bento_kpi("ri-user-voice-line", "emerald", "Input Dashboard CS (Okt)", rp_short(cs_okt_total), f"Bank +{rp_short(selisih_real_cs_okt)}", "green", f"Final: {rp_short(cs_okt_final)}")
    with c3: render_bento_kpi("ri-line-chart-line", "orange", "Proyeksi Akhir Bulan (31 Okt)", rp_short(proyeksi_akhir_bulan_real), f"{(proyeksi_akhir_bulan_real/target_okt)*100:.1f}% Target", "orange", f"Avg: {rp_short(laju_harian_real)}/hr")
    with c4:
        render_html(f'<div class="hero-card"><div style="display:flex;justify-content:space-between;align-items:center;"><span style="font-size:11px;font-weight:700;letter-spacing:0.4px;text-transform:uppercase;">EFEKTIVITAS IKLAN (OKT)</span><i class="ri-shield-star-line" style="font-size:17px;"></i></div><div class="kpi-val-fluid">ROAS {roas_okt_val:.2f}x <span style="opacity:0.65;font-weight:500;">|</span> ROFI {rofi_okt_val:.2f}x</div><div style="display:flex;justify-content:space-between;align-items:center;background:rgba(255,255,255,0.16);padding:5px 10px;border-radius:10px;font-size:10.5px;font-weight:600;gap:6px;flex-wrap:wrap;"><span class="nowrap-val">Ads: {rp_short(ads_okt)}</span><span class="nowrap-val">DSD: {rp_short(sm_ov["dsd"])}</span></div></div>')

    render_html('<div class="section-divider"><i class="ri-shield-check-line" style="color:#10B981!important;"></i> 2. TREN KEUANGAN BULANAN & 5 INDIKATOR UTAMA SATPAM KEUANGAN</div>')
    m_left, m_right = st.columns([1.45, 1.35])
    with m_left:
        render_chart_header("Komparasi Real Finance vs Input CS & Proyeksi Akhir Bulan", f"Realisasi Finance Okt: {rp(real_okt)} • Input CS: {rp(cs_okt_total)} • Estimasi 31 Okt: {rp(proyeksi_akhir_bulan_real)}", "Jan – Okt 2026", "indigo")
        fig_ov = go.Figure()
        fig_ov.add_trace(go.Scatter(x=df_macro['Bulan'], y=df_macro['Realisasi Finance'], name='Real Finance (Bank)', mode='lines+markers', line=dict(color='#6366F1', width=3, shape='spline'), fill='tozeroy', fillcolor='rgba(99, 102, 241, 0.1)'))
        fig_ov.add_trace(go.Scatter(x=df_macro['Bulan'], y=df_macro['Omset CS'], name='Input Dashboard CS', mode='lines+markers', line=dict(color='#10B981', width=2.6, shape='spline')))
        sep_real = float(df_macro[df_macro['Bulan'] == 'September']['Realisasi Finance'].iloc[0])
        fig_ov.add_trace(go.Scatter(x=['September', 'Oktober'], y=[sep_real, proyeksi_akhir_bulan_real], name='Proyeksi Akhir Bulan', mode='lines+markers', line=dict(color='#F59E0B', width=3, dash='dash')))
        fig_ov.add_trace(go.Scatter(x=df_macro['Bulan'], y=df_macro['Budget Iklan'], name='Biaya Iklan (Ads)', mode='lines+markers', line=dict(color='#FF6B4A', width=2, dash='dot', shape='spline')))
        apply_saas_plotly(fig_ov, height=355, is_currency=True)
        st.plotly_chart(fig_ov, use_container_width=True)

    with m_right:
        render_satpam_5_highlight_card(sm_ov, "Satpam Keuangan: 5 Indikator Utama (HPP Standar Rp 20rb)")

    render_html('<div class="section-divider"><i class="ri-book-mark-line" style="color:#F97316!important;"></i> 3. STATUS STOK MUSHAF META LP & PERBANDINGAN TOTAL DISTRIBUSI</div>')
    l1, l2, l3, l4 = st.columns(4)
    with l1:
        render_bento_kpi("ri-checkbox-circle-line", "emerald", "Meta LP Siap Disalurkan", f"{sa['meta_lp_siap']:,} Mushaf".replace(",", "."), f"ST: {sa['st_siap']} • AW Meta: {sa['aw_meta_siap']:,}".replace(",", "."), "green", "Sudah Tempel Stiker")
    with l2:
        render_bento_kpi("ri-time-line", "orange", "Meta LP Belum Siap Salur", f"{sa['meta_lp_belum']:,} Mushaf".replace(",", "."), f"Total Meta LP: {sa['meta_lp_total']:,} Pcs".replace(",", "."), "orange", f"ST: {sa['st_belum']} • AW Meta: {sa['aw_meta_belum']}")
    with l3:
        render_bento_kpi("ri-alarm-warning-fill", "rose", "Total Kekurangan (Meta LP)", f"{sa['kekurangan_meta_lp']:,} Mushaf".replace(",", "."), f"Wajib Beli {sa['kekurangan_meta_lp']:,} Pcs".replace(",", "."), "red", f"Kebutuhan {sa['kebutuhan_agust_okt']:,} - Meta LP {sa['meta_lp_total']:,}".replace(",", "."))
    with l4:
        lbl_3bln = f"Kurang {sa['selisih_gabungan_vs_3bln']:,} Pcs" if sa['selisih_gabungan_vs_3bln'] < 0 else f"Berlebih +{sa['selisih_gabungan_vs_3bln']:,} Pcs"
        lbl_okt_d = f"Berlebih +{sa['selisih_gabungan_vs_okt']:,} Pcs" if sa['selisih_gabungan_vs_okt'] >= 0 else f"Kurang {sa['selisih_gabungan_vs_okt']:,} Pcs"
        render_bento_kpi("ri-scales-3-line", "indigo", "Distribusi vs (Meta LP + TikTok)", f"{sa['stok_fisik_mushaf_tersedia']:,} Mushaf".replace(",", "."), f"vs 3 Bln ({sa['kebutuhan_agust_okt']:,}): {lbl_3bln}".replace(",", "."), "orange" if sa['selisih_gabungan_vs_3bln'] < 0 else "green", f"vs Okt ({sa['kebutuhan_okt']:,}): {lbl_okt_d}".replace(",", "."))

# ==============================================================================
# HALAMAN 2: DONASI & SATPAM KEUANGAN (MURNI FINANCE — TANPA DATA CS/LEADS)
# ==============================================================================
elif menu_pilihan == "Donasi & Satpam Keuangan":
    f1_a, f1_b, f1_c = st.columns(3)
    with f1_a:
        cakupan_fin = st.selectbox("1. Pilih Periode Keuangan:", ["Bulan Oktober 2026 (Realtime)", "Pilih Bulan Historis (Januari – September)", "Akumulasi Tahunan (YTD Jan–Okt)"], key="fin_scope")
    with f1_b:
        if cakupan_fin == "Pilih Bulan Historis (Januari – September)":
            bln_terpilih = st.selectbox("2. Pilih Bulan Historis:", [b for b in df_macro['Bulan'].tolist() if b != "Oktober"], key="fin_hist_m")
            mode_keb_val = "meta_lp"
        else:
            bln_terpilih = "Oktober"
            opsi_keb_f = st.selectbox("2. Acuan Kebutuhan Mushaf:", [f"Kekurangan Mushaf Meta LP ({sa['kekurangan_meta_lp']:,} Mushaf)", f"Sisa Kebutuhan Oktober ({sa['gap_okt']:,} Mushaf)", f"Total Kebutuhan Oktober ({sa['kebutuhan_okt']:,} Mushaf)"], key="fin_mode_mushaf")
            mode_keb_val = "okt_sisa" if "Sisa Kebutuhan" in opsi_keb_f else ("okt_total" if "Total Kebutuhan" in opsi_keb_f else "meta_lp")
    with f1_c:
        opsi_hpp = st.selectbox("3. Pilih HPP Pembelian Mushaf (Pedoman No.7):", ["Tier 1: Rp 20.000 / Mushaf (Soft Cover)", "Tier 2: Rp 35.000 / Mushaf (Standar)", "Tier 3: Rp 49.000 / Mushaf (Premium)"], key="fin_hpp_sel")
        hpp_terpilih = 20000.0 if "20.000" in opsi_hpp else (35000.0 if "35.000" in opsi_hpp else 49000.0)

    if cakupan_fin == "Akumulasi Tahunan (YTD Jan–Okt)":
        d_fin, b_ads = float(df_macro['Realisasi Finance'].sum()), float(df_macro['Budget Iklan'].sum())
        leads_meta_cur, lbl_badge = d_fin * 0.80, "YTD Jan–Okt"
    elif cakupan_fin == "Pilih Bulan Historis (Januari – September)":
        rb = df_macro[df_macro['Bulan'] == bln_terpilih].iloc[0]
        d_fin, b_ads = float(rb['Realisasi Finance']), float(rb['Budget Iklan'])
        leads_meta_cur, lbl_badge = d_fin * 0.80, f"{bln_terpilih} 2026"
    else:
        rb = df_macro[df_macro['Bulan'] == 'Oktober'].iloc[0]
        d_fin, b_ads = float(rb['Realisasi Finance']), float(rb['Budget Iklan'])
        non_tot_s = db['okt_sumber'][db['okt_sumber']['CS / CRM'].astype(str).str.upper() != 'TOTAL']
        leads_meta_cur, lbl_badge = (float(non_tot_s['Leads Meta'].sum()) if not non_tot_s.empty else 205624456.0), "Oktober 2026"

    sm = hitung_satpam_spreadsheet(d_fin, b_ads, sa, hpp_unit=hpp_terpilih, leads_meta_val=leads_meta_cur, mode_kebutuhan=mode_keb_val)

    render_html('<div class="section-divider"><i class="ri-exchange-dollar-line" style="color:#6366F1!important;"></i> TAHAP 1: ALUR POTONGAN IKLAN & BEBAN OPERASIONAL 10% (MENUJU DANA SIAP DISALURKAN)</div>')
    c1, c2, c3, c4 = st.columns(4)
    with c1: render_bento_kpi("ri-bank-card-line", "indigo", f"1. Total Donasi Masuk ({lbl_badge})", rp_short(sm['donasi']), "100% Sumber Donasi Utama", "indigo", rp(sm['donasi']))
    with c2: render_bento_kpi("ri-advertisement-line", "orange", "2. Biaya Iklan & Profit Iklan", rp_short(sm['iklan']), f"Profit Iklan: {rp_short(sm['profit_iklan'])}", "orange", f"ROFI: {sm['rofi_real']:.2f}x")
    with c3: render_bento_kpi("ri-File-shield-2-line", "rose", "3. Beban Operasional (10%)", rp_short(sm['beban_ops_10']), "Flat 10% × Total Donasi", "red", rp(sm['beban_ops_10']))
    with c4: render_bento_kpi("ri-wallet-3-line", "emerald", "4. Donasi Siap Disalurkan (DSD)", rp_short(sm['dsd']), "Profit Iklan − Operasional 10%", "green" if sm['dsd'] > 0 else "red", rp(sm['dsd']))

    render_html('<div class="section-divider"><i class="ri-shield-star-line" style="color:#10B981!important;"></i> TAHAP 2: 5 INDIKATOR UTAMA SATPAM KEUANGAN (ALOKASI MUSHAF 65% vs CASHBACK 35%)</div>')
    g_left, g_right = st.columns([1.35, 1.45])
    with g_left:
        render_satpam_5_highlight_card(sm, f"5 Indikator Inti Satpam Keuangan ({lbl_badge})")
    with g_right:
        render_chart_header("Komparasi Bulanan: Realisasi Donasi Finance vs Biaya Iklan vs Laba Bersih", "Murni data keuangan yayasan sepanjang Januari – Oktober 2026", "Jan – Okt 2026", "indigo")
        fig_f1 = go.Figure()
        fig_f1.add_trace(go.Bar(x=df_macro['Bulan'], y=df_macro['Realisasi Finance'], name='Realisasi Finance', marker_color='#6366F1', marker_cornerradius=6))
        fig_f1.add_trace(go.Bar(x=df_macro['Bulan'], y=df_macro['Budget Iklan'], name='Biaya Iklan', marker_color='#FF6B4A', marker_cornerradius=6))
        fig_f1.add_trace(go.Bar(x=df_macro['Bulan'], y=df_macro['Laba Bersih'], name='Profit Iklan', marker_color='#10B981', marker_cornerradius=6))
        apply_saas_plotly(fig_f1, height=360, is_currency=True)
        fig_f1.update_layout(barmode='group')
        st.plotly_chart(fig_f1, use_container_width=True)

    render_html('<div class="section-divider"><i class="ri-table-2" style="color:#F97316!important;"></i> TABEL LENGKAP 8 KOMPONEN ARUS KAS & PEDOMAN KEBIJAKAN KEUANGAN YAYASAN</div>')
    render_saas_table(sm['df_8_komponen'])

    render_html('<div class="section-divider"><i class="ri-calendar-check-line" style="color:#6366F1!important;"></i> REKAPITULASI MAKRO FINANCE BULANAN (JANUARI – OKTOBER 2026)</div>')
    df_fin_only = df_macro[["Bulan", "Target Bulanan", "Realisasi Finance", "Selisih Target", "% Capaian", "Budget Iklan", "Laba Bersih", "ROFI", "Status Target"]].copy()
    for cr in ["Target Bulanan", "Realisasi Finance", "Selisih Target", "Budget Iklan", "Laba Bersih"]:
        df_fin_only[cr] = df_fin_only[cr].apply(rp)
    df_fin_only["% Capaian"] = df_fin_only["% Capaian"].apply(lambda x: f"{x:.1f}%")
    df_fin_only["ROFI"] = df_fin_only["ROFI"].apply(lambda x: f"{x:.2f}x")
    render_saas_table(df_fin_only)

# ==============================================================================
# HALAMAN 3: IKLAN & STRATEGI ADS (100% AUTO-PILOT TANPA INPUT MANUAL)
# ==============================================================================
elif menu_pilihan == "Iklan & Strategi Ads":
    sp_kpi = db['spend_okt_kpi']
    df_sp = db['spend_okt_df'].copy()
    fm = db['okt_finance_mon']
    df_har_okt = db.get('okt_harian', pd.DataFrame())

    real_okt = float(fm.get('realisasi_finance', 298201574))
    ads_finance_okt = float(fm.get('budget_iklan', 248087884))
    hari_berjalan = max(1, int(fm.get('hari_cutoff', 28)))
    spend_sheet_val = float(sp_kpi.get("total_spending", 0.0))
    spend_aktif = spend_sheet_val if spend_sheet_val > 0 else ads_finance_okt
    nom_closing_meta = float(sp_kpi.get("nominal_closing", 205624456.0))
    leads_closing_cnt = int(sp_kpi.get("leads_closing", 1298))
    tot_leads_valid = int(sp_kpi.get("total_leads", 0)) if int(sp_kpi.get("total_leads", 0)) > 0 else int(db.get("tot_leads_valid_okt", 1747))

    ap = hitung_autopilot_ads(real_okt, spend_aktif, nom_closing_meta, leads_closing_cnt, tot_leads_valid, db['avg_cr_okt'], hari_berjalan, df_har_okt)
    cpr_badge = "green" if ap['cpr_aktual'] <= ap['batas_cpr_sehat_99k'] else ("orange" if ap['cpr_aktual'] <= ap['batas_cpr_maks_99k'] else "red")

    render_html('<div class="section-divider"><i class="ri-advertisement-line" style="color:#6366F1!important;"></i> 1. INDIKATOR UTAMA IKLAN & EVALUASI RATA-RATA CPR TERHADAP DONASI MINIMAL 99K</div>')
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        render_bento_kpi("ri-funds-box-line", "indigo", "Total Spending Iklan (Okt)", rp_short(spend_aktif), f"Avg: {rp_short(ap['avg_spend_harian'])}/hr", "indigo", f"Nominal Meta: {rp_short(nom_closing_meta)}")
    with a2:
        render_bento_kpi("ri-price-tag-3-line", "rose", "Rata-Rata CPR (Cost Per Lead)", rp(ap['cpr_aktual']), f"Batas Aman 99K: {rp(ap['batas_cpr_sehat_99k'])}", cpr_badge, f"Toleransi Maks 99K: {rp(ap['batas_cpr_maks_99k'])}")
    with a3:
        render_bento_kpi("ri-shopping-cart-check-line", "emerald", "Leads Closing & Cost/Closing", f"{leads_closing_cnt:,} Closing".replace(",", "."), f"Cost/Closing: {rp(ap['cpa_closing'])}", "green", f"AOV Meta: {rp(ap['aov_meta'])}")
    with a4:
        render_bento_kpi("ri-rocket-2-line", "orange", "Keputusan Budget Hari Ini (Auto)", rp_short(ap['rekom_budget_hari_ini']), ap['mode_keputusan'], ap['badge_keputusan'], f"ROAS Meta {ap['roas_meta']:.2f}x | ROFI {ap['rofi_fin']:.2f}x")

    render_html('<div class="section-divider"><i class="ri-cpu-line" style="color:#10B981!important;"></i> 2. KEPUTUSAN OTOMATIS HARI INI & STRATEGI PENGAMANAN ROAS / CPR 99K</div>')
    ad_l, ad_r = st.columns([1.4, 1.4])
    with ad_l:
        st1 = step_item_html("1. Rekomendasi Gas Budget Iklan Hari Ini (Otomatis)", ap['alasan_utama'], rp(ap['rekom_budget_hari_ini']), "#6366F1")
        st2 = step_item_html("2. Batas Maksimal CPR Hari Ini (Acuan Donasi Minimal Rp 99.000)", f"Agar ROAS Sehat 2,00x pada donasi 99K (Toleransi maks HPP 20rb: {rp(ap['batas_cpr_maks_99k'])}/lead)", f"<= {rp(ap['batas_cpr_sehat_99k'])} / lead", "#10B981")
        st3 = step_item_html(f"3. Target Minimal Leads & Closing Hari Ini (CR {db['avg_cr_okt']:.1f}%)", f"Target Donasi Harian agar ROAS 2,00x: {rp(ap['target_donasi_hari_ini_2x'])}", f"{ap['target_leads_hari_ini']} Leads → {ap['target_closing_hari_ini']} Closing", "#F97316")
        st4 = step_item_html("4. Target Subsidi CRM / Repeat Order Hari Ini", f"Estimasi perolehan iklan Meta hari ini: {rp(ap['est_donasi_meta_hari_ini'])} (Sisanya wajib ditutup CRM)", rp(ap['wajib_subsidi_crm_hari_ini']), "#EF4444", is_last=True)
        render_html(f'<div class="bento-card" style="min-height:365px;"><div><div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap;"><span style="font-family:\'Outfit\',sans-serif!important;font-weight:800;font-size:15px;"><i class="ri-robot-2-fill" style="color:#6366F1!important;"></i> Komando Budget & Target Harian Otomatis</span><span class="badge-pill bp-{ap["badge_keputusan"]}">{ap["mode_keputusan"]}</span></div>{st1}{st2}{st3}{st4}</div></div>')

    with ad_r:
        render_html(f"""
        <div class="bento-card" style="min-height:365px;display:flex;flex-direction:column;justify-content:space-between;">
            <div>
                <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap;">
                    <span style="font-family:'Outfit',sans-serif!important;font-weight:800;font-size:15px;"><i class="ri-lightbulb-flash-fill" style="color:#F59E0B!important;"></i> Analisis CPR 99K & Instruksi Taktis Hari Ini</span>
                    <span class="badge-pill bp-indigo">Auto-Diagnostic</span>
                </div>
                <div class="sub-box" style="padding:11px 14px;border-radius:12px;margin-bottom:9px;font-size:12px;line-height:1.55;">
                    <b>🔍 Mengapa CPR Harus Diukur Terhadap Donasi Minimal 99K (Rp 99.000)?</b><br>
                    • Pada donasi 1 mushaf (<b>Rp 99.000</b>), potongan operasional 10% adalah <b>Rp 9.900</b>.<br>
                    • Agar mencapai <b>Standar ROAS Sehat 2,00x</b> (biaya iklan maks 50% = <b>Rp 49.500/closing</b>), maka dengan CR CS <b>{db['avg_cr_okt']:.1f}%</b>, biaya per lead (CPR) tidak boleh melebihi <b>{rp(ap['batas_cpr_sehat_99k'])}</b>.<br>
                    • Saat ini rata-rata CPR Anda berada di <b>{rp(ap['cpr_aktual'])}/lead</b> (setara <b>{rp(ap['cpa_closing'])}/closing</b>). Jika donatur hanya berdonasi Rp 99.000, maka sisa DSD hanya <b>{rp(99000 - 9900 - ap['cpa_closing'])}</b>.
                </div>
                <div class="sub-box" style="padding:11px 14px;border-radius:12px;font-size:12px;line-height:1.55;">
                    <b>⚡ 3 Langkah Eksekusi Wajib Hari Ini:</b><br>
                    1. <b>Aturan Matikan AdSet (Cut-Off CPR):</b> Evaluasi iklan pukul 12.00 WIB; matikan AdSet yang memiliki <b>CPR > {rp(ap['batas_cpr_maks_99k'])}</b> dan belum menghasilkan closing.<br>
                    2. <b>Kunci Paket Bundling Minimal {ap['min_paket_mushaf']} Mushaf ({rp(ap['min_paket_mushaf']*99000)}):</b> Dengan biaya per closing saat ini ({rp(ap['cpa_closing'])}), CS wajib mengarahkan donatur mengambil minimal <b>{ap['min_paket_mushaf']} Mushaf</b> agar ROAS otomatis naik ke <b>>= 2,00x</b>.<br>
                    3. <b>Kuota Harian CRM CS:</b> Tim CS & CRM wajib menyumbang minimal <b>{rp(ap['wajib_subsidi_crm_hari_ini'])}</b> hari ini dari *follow-up* donatur lama untuk mengamankan Saldo Pembelian Mushaf 65%.
                </div>
            </div>
        </div>
        """)

    render_chart_header("Tren Harian Nominal Closing & Leads Closing (Sheet DATA SPEND OKTOBER)", "Otomatis menampilkan garis Spending & CPR begitu kolom Spending diisi di spreadsheet", "Oktober 2026", "indigo")
    fig_sp = go.Figure()
    if not df_sp.empty:
        fig_sp.add_trace(go.Bar(x=df_sp['Tanggal'], y=df_sp['Nominal Closing (Rp)'], name='Nominal Closing Meta (Rp)', marker_color='#10B981', marker_cornerradius=5))
        if df_sp['Spending (Rp)'].sum() > 0:
            fig_sp.add_trace(go.Scatter(x=df_sp['Tanggal'], y=df_sp['Spending (Rp)'], name='Spending Iklan (Rp)', mode='lines+markers', line=dict(color='#FF6B4A', width=3)))
    apply_saas_plotly(fig_sp, height=280, is_currency=True)
    st.plotly_chart(fig_sp, use_container_width=True)

    render_html('<div class="section-divider"><i class="ri-table-2" style="color:#6366F1!important;"></i> TABEL HARIAN SHEET DATA SPEND OKTOBER (OTOMATIS SINKRON SAAT DIISI)</div>')
    df_sp_disp = df_sp.copy()
    if not df_sp_disp.empty:
        df_sp_disp["Spending (Rp)"] = df_sp_disp["Spending (Rp)"].apply(rp)
        df_sp_disp["Rata-Rata CPR"] = df_sp_disp["Rata-Rata CPR"].apply(rp)
        df_sp_disp["Nominal Closing (Rp)"] = df_sp_disp["Nominal Closing (Rp)"].apply(rp)
        df_sp_disp["ROAS"] = df_sp_disp["ROAS"].apply(lambda x: f"{float(x):.2f}x")
    render_saas_table(df_sp_disp)

# ==============================================================================
# HALAMAN 4: PERFORMA CS & LEADS (LENGKAP DENGAN TABEL KOMPARASI & SUMBER KONTAK)
# ==============================================================================
elif menu_pilihan == "Performa CS & Leads":
    mode_evaluasi_cs = st.radio(
        "Pilih Mode Evaluasi Kinerja CS & Leads:",
        [
            "1. Rekapitulasi Pendapatan Harian per CS (Leads Meta vs CRM + CR Harian)",
            "2. Tabel Komparasi Kinerja CS Oktober & Analisis Sumber Kontak",
            "3. Monitoring Leads & Conversion Rate (CR) per Kampanye (SantriQu, AmalQu, JariyahQu)",
            "4. Rapor & Rekap Omzet Bulanan Seluruh CS (Januari – Oktober 2026)"
        ],
        horizontal=True, key="cs_eval_mode"
    )

    if mode_evaluasi_cs.startswith("1."):
        df_d_okt = db.get('okt_harian', pd.DataFrame()).copy()
        sum_leads = df_d_okt['Total_Leads'].sum() if not df_d_okt.empty else 0
        sum_crm = df_d_okt['Total_CRM'].sum() if not df_d_okt.empty else 0
        sum_gab = df_d_okt['Total_Gabungan'].sum() if not df_d_okt.empty else 0

        k1, k2, k3, k4 = st.columns(4)
        with k1: render_bento_kpi("ri-advertisement-line", "indigo", "Total Leads Meta (Okt)", rp_short(sum_leads), "82,4% Porsi Donasi", "indigo", rp(sum_leads))
        with k2: render_bento_kpi("ri-repeat-2-line", "emerald", "Total CRM (Repeat Order)", rp_short(sum_crm), "17,6% Porsi Gabungan", "green", rp(sum_crm))
        with k3: render_bento_kpi("ri-funds-box-line", "orange", "Total Gabungan CS (Okt)", rp_short(sum_gab), f"Final: {rp_short(db['okt_kpi']['donasi_final'])}", "orange", rp(sum_gab))
        with k4: render_bento_kpi("ri-percent-line", "emerald", "Rata-Rata CR Bulanan", f"{db['avg_cr_okt']:.1f}%", "Dari Sheet CR/Leads", "green", f"{len(db['leads_okt'])} Baris CR Aktif")

        render_rekap_harian_cs_table(df_d_okt, db['avg_cr_okt'])

    elif mode_evaluasi_cs.startswith("2."):
        render_html('<div class="section-divider"><i class="ri-user-star-line" style="color:#6366F1!important;"></i> TABEL KOMPARASI KINERJA PENDAPATAN PER CS (TOTAL vs FINAL TERVERIFIKASI)</div>')
        df_ok = db['okt_cs_table'].copy()
        for cr in ['Harian (Total)', 'Harian (Final)', 'Mingguan (Total)', 'Mingguan (Final)', 'Bulanan (Total)', 'Bulanan (Final)', 'Target (Rp)', 'Sisa Target', 'Pending Verifikasi', 'Target Harian (Sisa)']:
            if cr in df_ok.columns: df_ok[cr] = df_ok[cr].apply(rp)
        render_saas_table(df_ok)

        render_html('<div class="section-divider"><i class="ri-pie-chart-2-line" style="color:#10B981!important;"></i> ANALISIS DISTRIBUSI PENDAPATAN BERDASARKAN SUMBER KONTAK & RASIO KANAL</div>')
        col_s1, col_s2 = st.columns([1.3, 1])
        with col_s1:
            df_sr = db['okt_sumber'].copy()
            for cr in ['Leads Meta', 'Repeat Order CRM', 'Repeat Order non CRM', 'Lainnya', 'Total Nominal']:
                if cr in df_sr.columns: df_sr[cr] = df_sr[cr].apply(rp)
            render_saas_table(df_sr)
        with col_s2:
            render_saas_table(db['okt_kanal_rasio'])

    elif mode_evaluasi_cs.startswith("3."):
        df_l = db['leads_okt'].copy()
        df_l['DT'] = pd.to_datetime(df_l['Tanggal'], errors='coerce').dt.date
        df_l = df_l.dropna(subset=['DT'])
        min_cal_d, max_cal_d = datetime.date(2026, 10, 1), datetime.date(2026, 10, 31)
        raw_max_l = df_l['DT'].max() if not df_l.empty else datetime.date(2026, 10, 28)
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
# HALAMAN 5: LOGISTIK & GUDANG (PEMISAHAN META LP, TIKTOK, TAHSIN & DEFISIT META LP)
# ==============================================================================
elif menu_pilihan == "Logistik & Gudang":
    render_html('<div class="section-divider"><i class="ri-archive-drawer-line" style="color:#6366F1!important;"></i> 1. PEMISAHAN STOK PER KATEGORI: MUSHAF META LP vs MUSHAF TIKTOK vs BUKU TAHSIN</div>')
    s1, s2, s3 = st.columns(3)
    with s1:
        render_bento_kpi("ri-book-mark-line", "indigo", "1. Mushaf Meta LP (ST & Al-Wakaf)", f"{sa['meta_lp_total']:,} Pcs".replace(",", "."), f"Siap: {sa['meta_lp_siap']:,} • Belum: {sa['meta_lp_belum']} Pcs".replace(",", "."), "indigo", f"ST: {sa['st_total']} | AW Meta: {sa['aw_meta_total']:,}".replace(",", "."))
    with s2:
        render_bento_kpi("ri-tiktok-line", "emerald", "2. Mushaf TikTok (Hanya Pendataan)", f"{sa['tiktok_mushaf_total']:,} Pcs".replace(",", "."), f"Siap: {sa['tiktok_mushaf_siap']:,} • Belum: {sa['tiktok_mushaf_belum']} Pcs".replace(",", "."), "green", "Al-Wakaf TikTok (Tanpa Beban Defisit)")
    with s3:
        render_bento_kpi("ri-book-open-line", "orange", "3. Buku Belajar Super Tahsin", f"{sa['buku_tahsin_total']:,} Pcs".replace(",", "."), f"Siap: {sa['buku_tahsin_siap']:,} • Belum: {sa['buku_tahsin_belum']} Pcs".replace(",", "."), "green", "Inventaris Buku Tahsin TikTok")

    render_html('<div class="section-divider"><i class="ri-alarm-warning-line" style="color:#EF4444!important;"></i> 2. KEKURANGAN PENGADAAN MUSHAF META LP & PERBANDINGAN DISTRIBUSI</div>')
    s4, s5, s6 = st.columns(3)
    with s4:
        render_bento_kpi("ri-calendar-todo-line", "indigo", "Total Kebutuhan Distribusi (Agust–Okt)", f"{sa['kebutuhan_agust_okt']:,} Mushaf".replace(",", "."), f"Agust: {sa['keb_agust']} • Sept: {sa['keb_sept']:,} • Okt: {sa['kebutuhan_okt']:,}".replace(",", "."), "orange", f"Sisa Gap Distribusi: {sa['gap_agust_okt']:,} Pcs".replace(",", "."))
    with s5:
        render_bento_kpi("ri-alarm-warning-fill", "rose", "Total Kekurangan Mushaf (Meta LP)", f"{sa['kekurangan_meta_lp']:,} Mushaf".replace(",", "."), f"WAJIB BELI {sa['kekurangan_meta_lp']:,} MUSHAF".replace(",", "."), "red", f"Kebutuhan {sa['kebutuhan_agust_okt']:,} - Meta LP {sa['meta_lp_total']:,}".replace(",", "."))
    with s6:
        lbl_gab = f"Kurang {sa['selisih_gabungan_vs_3bln']:,} Pcs" if sa['selisih_gabungan_vs_3bln'] < 0 else f"Berlebih +{sa['selisih_gabungan_vs_3bln']:,} Pcs"
        render_bento_kpi("ri-scales-3-line", "emerald", "Distribusi vs (Meta LP + TikTok)", f"{sa['stok_fisik_mushaf_tersedia']:,} Mushaf".replace(",", "."), f"vs 3 Bln: {lbl_gab}".replace(",", "."), "orange" if sa['selisih_gabungan_vs_3bln'] < 0 else "green", f"vs Okt ({sa['kebutuhan_okt']:,}): +{sa['selisih_gabungan_vs_okt']:,} Pcs".replace(",", "."))

    t_left, t_right = st.columns(2)
    with t_left:
        render_html('<div style="font-family:\'Outfit\',sans-serif!important;font-size:15px;font-weight:800;margin:4px 0;"><i class="ri-list-check-2" style="color:#10B981!important;"></i> RINCIAN INVENTARIS STOK PER PRODUK & KANAL (SIAP VS BELUM SIAP)</div>')
        df_inv_show = db['stok_rincian_baru'].copy()
        for cn in ["Siap Salur (Stiker)", "Belum Siap (Proses)", "Total Stok Fisik"]:
            if cn in df_inv_show.columns: df_inv_show[cn] = df_inv_show[cn].apply(lambda x: f"{int(num_clean(x)):,}".replace(",", "."))
        render_saas_table(df_inv_show)

    with t_right:
        render_html('<div style="font-family:\'Outfit\',sans-serif!important;font-size:15px;font-weight:800;margin:4px 0;"><i class="ri-error-warning-line" style="color:#EF4444!important;"></i> ANALISIS KEBUTUHAN & KEKURANGAN MUSHAF (ACUAN META LP vs GABUNGAN)</div>')
        df_def_custom = pd.DataFrame([
            {"Periode / Komponen Analisis": "Kebutuhan Agustus 2026", "Target / Stok": f"{sa['keb_agust']:,}".replace(",", "."), "Keterangan Operasional": "Realisasi: 0 Pcs", "Gap / Selisih": f"{sa['keb_agust']:,}".replace(",", "."), "Status & Rekomendasi": "Belum Salur"},
            {"Periode / Komponen Analisis": "Kebutuhan September 2026", "Target / Stok": f"{sa['keb_sept']:,}".replace(",", "."), "Keterangan Operasional": "Realisasi: 0 Pcs", "Gap / Selisih": f"{sa['keb_sept']:,}".replace(",", "."), "Status & Rekomendasi": "Belum Salur"},
            {"Periode / Komponen Analisis": "Kebutuhan Oktober 2026", "Target / Stok": f"{sa['kebutuhan_okt']:,}".replace(",", "."), "Keterangan Operasional": "Realisasi: 100 Pcs", "Gap / Selisih": f"{sa['gap_okt']:,}".replace(",", "."), "Status & Rekomendasi": "Sebagian Salur"},
            {"Periode / Komponen Analisis": "Total Kebutuhan Distribusi (Agust–Okt)", "Target / Stok": f"{sa['kebutuhan_agust_okt']:,}".replace(",", "."), "Keterangan Operasional": "Akumulasi 3 Bulan", "Gap / Selisih": f"{sa['gap_agust_okt']:,}".replace(",", "."), "Status & Rekomendasi": "Target Distribusi Aktif"},
            {"Periode / Komponen Analisis": "Total Mushaf Meta LP (Siap + Belum)", "Target / Stok": f"{sa['meta_lp_total']:,}".replace(",", "."), "Keterangan Operasional": f"Siap {sa['meta_lp_siap']:,} + Belum {sa['meta_lp_belum']}", "Gap / Selisih": f"({sa['kekurangan_meta_lp']:,})".replace(",", "."), "Status & Rekomendasi": f"WAJIB BELI {sa['kekurangan_meta_lp']:,} MUSHAF".replace(",", ".")},
            {"Periode / Komponen Analisis": "Total Mushaf Meta LP + TikTok", "Target / Stok": f"{sa['stok_fisik_mushaf_tersedia']:,}".replace(",", "."), "Keterangan Operasional": f"Meta {sa['meta_lp_total']:,} + TikTok {sa['tiktok_mushaf_total']}", "Gap / Selisih": f"({sa['defisit_agust_okt']:,})".replace(",", "."), "Status & Rekomendasi": f"Kurang {sa['defisit_agust_okt']:,} vs 3 Bln".replace(",", ".")},
        ])
        render_saas_table(df_def_custom)

    lg_l, lg_r = st.columns([1.5, 1.3])
    with lg_l:
        render_chart_header("Komparasi Stok Terpisah: Mushaf Meta LP vs Mushaf TikTok vs Buku Tahsin", "Memisahkan antara yang Siap Disalurkan (Stiker) dan Belum Siap Disalurkan (Proses)", f"Total {sa['total_inventaris_fisik']:,} Pcs".replace(",", "."), "indigo")
        df_kat3 = pd.DataFrame([
            {"Kategori": "1. Mushaf Meta LP", "Siap Disalurkan": sa['meta_lp_siap'], "Belum Siap": sa['meta_lp_belum']},
            {"Kategori": "2. Mushaf TikTok", "Siap Disalurkan": sa['tiktok_mushaf_siap'], "Belum Siap": sa['tiktok_mushaf_belum']},
            {"Kategori": "3. Buku Super Tahsin", "Siap Disalurkan": sa['buku_tahsin_siap'], "Belum Siap": sa['buku_tahsin_belum']},
        ])
        fig_comp_s = go.Figure()
        fig_comp_s.add_trace(go.Bar(x=df_kat3['Kategori'], y=df_kat3['Siap Disalurkan'], name='Siap Disalurkan (Stiker)', marker_color='#10B981', marker_cornerradius=6))
        fig_comp_s.add_trace(go.Bar(x=df_kat3['Kategori'], y=df_kat3['Belum Siap'], name='Belum Siap Disalurkan (Proses)', marker_color='#F97316', marker_cornerradius=6))
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
# HALAMAN 6: KALENDER DISTRIBUSI
# ==============================================================================
elif menu_pilihan == "Kalender Distribusi":
    df_kal = db['kalender_okt'].copy()
    tot_agenda_kal = len(df_kal)
    tot_mushaf_kal = int(df_kal['Jumlah Mushaf (Pcs)'].sum()) if not df_kal.empty else 0

    mask_succ = df_kal['Status'].astype(str).str.lower().str.contains('success|sukses|selesai', na=False) if 'Status' in df_kal.columns else pd.Series([False]*len(df_kal))
    pcs_success = int(df_kal[mask_succ]['Jumlah Mushaf (Pcs)'].sum()) if not df_kal.empty else 0
    titik_success = int(mask_succ.sum())
    pcs_sched = tot_mushaf_kal - pcs_success
    titik_sched = tot_agenda_kal - titik_success

    kc1, kc2, kc3, kc4 = st.columns(4)
    with kc1: render_bento_kpi("ri-calendar-check-line", "indigo", "Total Jadwal Kalender Okt", f"{tot_mushaf_kal:,} Mushaf".replace(",", "."), f"{tot_agenda_kal} Titik Lokasi", "indigo", f"Target Okt: {sa['kebutuhan_okt']:,} Pcs".replace(",", "."))
    with kc2: render_bento_kpi("ri-checkbox-circle-fill", "emerald", "Distribusi Sukses [Success]", f"{pcs_success:,} Mushaf".replace(",", "."), f"{titik_success} Titik Selesai", "green", f"Scheduled: {pcs_sched:,} Pcs ({titik_sched} titik)")
    with kc3: render_bento_kpi("ri-archive-drawer-line", "orange", "Total Mushaf (Meta LP + TikTok)", f"{sa['stok_fisik_mushaf_tersedia']:,} Mushaf".replace(",", "."), f"Siap Salur: {sa['mushaf_siap_all']:,} Pcs".replace(",", "."), "green", f"Meta LP: {sa['meta_lp_total']:,} • TikTok: {sa['tiktok_mushaf_total']}")
    with kc4:
        sel_kal = sa['stok_fisik_mushaf_tersedia'] - tot_mushaf_kal
        lbl_k_kal = f"Berlebih +{sel_kal:,} Pcs" if sel_kal >= 0 else f"Kurang {sel_kal:,} Pcs"
        render_bento_kpi("ri-scales-3-line", "rose", "Stok Gabungan vs Jadwal Okt", lbl_k_kal.replace(",", "."), f"vs 3 Bln ({sa['kebutuhan_agust_okt']:,}): -{sa['defisit_agust_okt']:,} Pcs".replace(",", "."), "green" if sel_kal >= 0 else "red", f"Kekurangan Meta LP: {sa['kekurangan_meta_lp']:,} Pcs")

    events_by_day = {}
    for _, r_k in df_kal.iterrows():
        d_num = extract_day_okt(r_k.get("Tanggal Agenda", ""))
        if d_num: events_by_day.setdefault(d_num, []).append(r_k)

    cells_list = ['<div class="cal-cell-empty"></div>' for _ in range(3)]
    for day_num in range(1, 32):
        if day_num in events_by_day:
            ev_list = events_by_day[day_num]
            tot_pcs_day = sum(int(num_clean(x.get("Jumlah Mushaf (Pcs)", 0))) for x in ev_list)
            all_day_success = all(any(k in str(x.get("Status", "")).lower() for k in ["success", "sukses", "selesai"]) for x in ev_list)
            cell_cls = "cal-cell-success" if all_day_success else "cal-cell-active"
            badge_cls = "bp-green" if all_day_success else "bp-orange"

            items_html = ""
            for x in ev_list:
                st_str = str(x.get("Status", ""))
                is_s = any(k in st_str.lower() for k in ["success", "sukses", "selesai"])
                p_cls = "cal-item-pill-success" if is_s else "cal-item-pill"
                c_txt = "#10B981" if is_s else "#F97316"
                ic_s = "✓ " if is_s else "⏳ "
                lm_nm = str(x.get("Nama Lembaga Penerima", ""))
                if not lm_nm or lm_nm == "-": lm_nm = str(x.get("Wilayah / Titik Lokasi", "Titik Distribusi"))
                items_html += f'<div class="{p_cls}"><b>{ic_s}{lm_nm[:22]}</b><br><span style="color:{c_txt}!important;font-weight:700;">{int(num_clean(x.get("Jumlah Mushaf (Pcs)",0)))} Pcs</span> • {str(x.get("Variasi Mushaf",""))}</div>'

            cells_list.append(f'<div class="{cell_cls}"><div class="cal-day-num"><span>{day_num} Okt</span><span class="badge-pill {badge_cls}" style="padding:2px 6px;font-size:10px;">{tot_pcs_day} Pcs</span></div><div>{items_html}</div></div>')
        else:
            cells_list.append(f'<div class="cal-cell"><div class="cal-day-num"><span>{day_num} Okt</span></div><div style="font-size:10px;color:var(--text-muted)!important;">-</div></div>')
    cells_list.append('<div class="cal-cell-empty"></div>')
    desktop_cal_str = "".join(cells_list)

    mobile_cards = ""
    for day_num in sorted(events_by_day.keys()):
        ev_list = events_by_day[day_num]
        tot_pcs_day = sum(int(num_clean(x.get("Jumlah Mushaf (Pcs)", 0))) for x in ev_list)
        all_day_success = all(any(k in str(x.get("Status", "")).lower() for k in ["success", "sukses", "selesai"]) for x in ev_list)
        cell_cls = "cal-cell-success" if all_day_success else "cal-cell-active"
        badge_cls = "bp-green" if all_day_success else "bp-orange"
        items_html = ""
        for x in ev_list:
            st_str = str(x.get("Status", ""))
            is_s = any(k in st_str.lower() for k in ["success", "sukses", "selesai"])
            p_cls = "cal-item-pill-success" if is_s else "cal-item-pill"
            c_txt = "#10B981" if is_s else "#F97316"
            items_html += f'<div class="{p_cls}"><b>{str(x.get("Nama Lembaga Penerima",""))} ({st_str})</b><br><span style="color:{c_txt}!important;font-weight:700;">{int(num_clean(x.get("Jumlah Mushaf (Pcs)",0)))} Pcs ({str(x.get("Variasi Mushaf",""))})</span> • Lokasi: {str(x.get("Wilayah / Titik Lokasi",""))}</div>'
        mobile_cards += f'<div class="{cell_cls}" style="margin-bottom:10px;"><div class="cal-day-num"><span>{day_num} Oktober 2026</span><span class="badge-pill {badge_cls}">{len(ev_list)} Titik • {tot_pcs_day} Pcs</span></div><div>{items_html}</div></div>'

    render_html(f'<div class="bento-card"><div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;"><div><span style="font-family:\'Outfit\',sans-serif!important;font-weight:800;font-size:16.5px;"><i class="ri-calendar-todo-fill" style="color:#10B981!important;"></i> Kalender Visual Distribusi Mushaf — Oktober 2026 (Hijau = [Success] • Oranye = [Scheduled])</span><div style="font-size:12px;color:var(--text-secondary)!important;">Total Jadwal Kalender: <b>{tot_mushaf_kal:,} Pcs</b> (Success: <b style="color:#10B981!important;">{pcs_success:,} Pcs</b> | Scheduled: <b style="color:#F97316!important;">{pcs_sched:,} Pcs</b>) &nbsp;•&nbsp; Total Mushaf (Meta LP + TikTok): <b>{sa["stok_fisik_mushaf_tersedia"] :,} Pcs</b></div></div><div style="display:flex;gap:6px;flex-wrap:wrap;"><span class="badge-pill bp-green"><i class="ri-checkbox-circle-fill"></i> {titik_success} Titik [Success]</span><span class="badge-pill bp-orange"><i class="ri-time-fill"></i> {titik_sched} Titik [Scheduled]</span></div></div><div class="cal-desktop-only"><div class="cal-grid-7"><div class="cal-head-cell">SENIN</div><div class="cal-head-cell">SELASA</div><div class="cal-head-cell">RABU</div><div class="cal-head-cell">KAMIS</div><div class="cal-head-cell">JUMAT</div><div class="cal-head-cell">SABTU</div><div class="cal-head-cell">MINGGU</div>{desktop_cal_str}</div></div><div class="cal-mobile-only" style="margin-top:12px;">{mobile_cards}</div></div>')

    f_kal_1, f_kal_2, f_kal_3 = st.columns([2.0, 1.0, 1.0])
    with f_kal_1: render_html('<div style="font-family:\'Outfit\',sans-serif!important;font-size:15.5px;font-weight:700;padding-top:8px;"><i class="ri-table-line" style="color:#6366F1!important;"></i> Rincian Agenda Distribusi Mushaf (Sheet Kalender Oktober 2026)</div>')
    with f_kal_2: pilih_var_kal = st.selectbox("Filter Variasi Mushaf:", ["Semua Variasi", "Super Tajwid", "Al Wakaf Tiktok"], key="kal_var")
    with f_kal_3: pilih_stat_kal = st.selectbox("Filter Status Distribusi:", ["Semua Status", "[Success]", "[Scheduled]"], key="kal_stat")

    df_kal_disp = df_kal.copy()
    if pilih_var_kal != "Semua Variasi" and "Variasi Mushaf" in df_kal_disp.columns:
        df_kal_disp = df_kal_disp[df_kal_disp["Variasi Mushaf"].astype(str).str.contains(pilih_var_kal, case=False, na=False)]
    if pilih_stat_kal != "Semua Status" and "Status" in df_kal_disp.columns:
        kw_s = "success" if "Success" in pilih_stat_kal else "scheduled"
        df_kal_disp = df_kal_disp[df_kal_disp["Status"].astype(str).str.lower().str.contains(kw_s, na=False)]

    render_saas_table(df_kal_disp)

# ==============================================================================
# HALAMAN 7: DATABASE & SMART WA BLAST ENGINE
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

        render_html(f'<div class="bento-card" style="border:1.5px dashed #FB923C;text-align:center;padding:18px;"><div style="font-size:11px;font-weight:700;color:#F97316!important;letter-spacing:0.6px;">TARGET AUDIENS TERPILIH</div><div class="kpi-val-fluid" style="margin:6px 0;">{jml_label}</div><div style="font-size:11.5px;color:var(--text-secondary)!important;">Format: <b>phone number</b>, <b>nama</b></div></div>')
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
