# -*- coding: utf-8 -*-
"""
LED Auction Data Pipeline & Preprocessor for Interactive HTML Dashboard
Reads the 6 raw CSV files from LED_Lega_2026_10 and LED_Lega_2026_11,
performs Smart Multi-Stage Matching, parses land area (Rai-Ngan-Wa -> Sq.Wa),
calculates spatial price benchmarks and Multi-Factor Deal Scores,
and exports compact JavaScript data chunks into ./data/ for zero-CORS offline HTML usage.
"""

import os
import json
import re
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_OUT_DIR = os.path.join(BASE_DIR, "data")
PROV_OUT_DIR = os.path.join(DATA_OUT_DIR, "provinces")

os.makedirs(DATA_OUT_DIR, exist_ok=True)
os.makedirs(PROV_OUT_DIR, exist_ok=True)


def parse_rai_ngan_wa(val):
    """Convert 'ไร่-งาน-ตารางวา' string (e.g. '13-2-47' or '0-0-33.8') to total sq.wa (float)."""
    if pd.isna(val):
        return np.nan
    s = str(val).strip().replace(",", "")
    if not s or s == "-":
        return np.nan
    parts = s.split("-")
    try:
        if len(parts) == 3:
            r = float(parts[0]) if parts[0] else 0.0
            n = float(parts[1]) if parts[1] else 0.0
            w = float(parts[2]) if parts[2] else 0.0
            total = r * 400.0 + n * 100.0 + w
            return round(total, 2) if total > 0 else np.nan
        elif len(parts) == 1:
            v = float(parts[0])
            return round(v, 2) if v > 0 else np.nan
    except Exception:
        return np.nan
    return np.nan


def clean_num_series(s):
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


def normalize_prop_type(pt):
    if pd.isna(pt):
        return "อื่นๆ"
    s = str(pt).strip()
    if "ห้องชุด" in s:
        return "ห้องชุด"
    if "พร้อมสิ่งปลูกสร้าง" in s:
        return "ที่ดินพร้อมสิ่งปลูกสร้าง"
    if "ที่ดินเปล่า" in s or "ที่ดินว่างเปล่า" in s:
        return "ที่ดินว่างเปล่า"
    if "สิ่งปลูกสร้าง" in s:
        return "สิ่งปลูกสร้าง"
    return s


def normalize_sale_type(st):
    if pd.isna(st):
        return "ไม่ระบุ"
    s = str(st).strip()
    if "จำนองติดไป" in s:
        return "การจำนองติดไป"
    if "ปลอดการจำนอง" in s or "ปลอดจำนอง" in s:
        return "ปลอดการจำนอง"
    if "ไม่มีภาระจำนอง" in s:
        return "ไม่มีภาระจำนอง"
    if "ปลอดภาระผูกพัน" in s:
        return "ปลอดภาระผูกพัน"
    return s


def main():
    print("1. Loading CSV files...")
    f_merge_09 = os.path.join(BASE_DIR, "LED_Lega_2026_10", "LED_Legal_merge_2026_09.csv")
    f_report_09 = os.path.join(BASE_DIR, "LED_Lega_2026_10", "LED_Legal_report_2026_09.csv")
    f_npa_10 = os.path.join(BASE_DIR, "LED_Lega_2026_10", "LED_NPA_New_2026_10.csv")

    f_merge_10 = os.path.join(BASE_DIR, "LED_Lega_2026_11", "LED_Legal_merge_2026_10.csv")
    f_report_10 = os.path.join(BASE_DIR, "LED_Lega_2026_11", "LED_Legal_report_2026_10.csv")
    f_npa_11 = os.path.join(BASE_DIR, "LED_Lega_2026_11", "LED_NPA_New_2026_11.csv")

    merge_09 = pd.read_csv(f_merge_09, low_memory=False)
    report_09 = pd.read_csv(f_report_09, low_memory=False)
    npa_10 = pd.read_csv(f_npa_10, low_memory=False)

    merge_10 = pd.read_csv(f_merge_10, low_memory=False)
    report_10 = pd.read_csv(f_report_10, low_memory=False)
    npa_11 = pd.read_csv(f_npa_11, low_memory=False)

    print("2. Cleaning & Normalizing fields...")
    for df, m_label in [(report_09, "2026-09"), (report_10, "2026-10")]:
        df["month"] = m_label
        df["appraisal_num"] = clean_num_series(df["ราคาประเมิน"])
        df["sold_num"] = clean_num_series(df["ราคาขายได้ / ราคาเสนอสูงสุด"])
        df["ratio"] = np.where(df["appraisal_num"] > 0, df["sold_num"] / df["appraisal_num"], np.nan)
        df["prop_type_clean"] = df["ประเภททรัพย์"].apply(normalize_prop_type)
        df["case_clean"] = df["เลขคดีแดง"].astype(str).str.strip()
        df["deed_clean"] = df["ที่ดินโฉนด"].astype(str).str.strip()

    for df, m_label in [(merge_09, "2026-09"), (merge_10, "2026-10")]:
        df["month"] = m_label
        df["case_clean"] = df["รหัสทรัพย์"].astype(str).str.split("_").str[0].str.strip()
        df["prop_type_clean"] = df["ประเภททรัพย์"].apply(normalize_prop_type)
        df["sale_type_clean"] = df["ประเภทการขาย"].apply(normalize_sale_type)
        df["area_sqw"] = df["เนื้อที่ (ตร.ว.)"].apply(parse_rai_ngan_wa)
        df["area_sqm"] = pd.to_numeric(df["พื้นที่ใช้สอย (ตร.ม.)"], errors="coerce")
        df["appraisal_num"] = pd.to_numeric(df["ราคา"], errors="coerce")
        df["sold_num"] = pd.to_numeric(df["ราคาขายได้"], errors="coerce")
        df["ratio"] = np.where(df["appraisal_num"] > 0, df["sold_num"] / df["appraisal_num"], np.nan)
        df["วันประกาศ_dt"] = pd.to_datetime(df["วันประกาศ"], errors="coerce")
        df["วันที่ขาย_dt"] = pd.to_datetime(df["วันที่ขาย"], errors="coerce")
        df["days_to_sell"] = (df["วันที่ขาย_dt"] - df["วันประกาศ_dt"]).dt.days

    for df in [npa_10, npa_11]:
        df["case_clean"] = df["รหัสทรัพย์"].astype(str).str.split("_").str[0].str.strip()
        df["prop_type_clean"] = df["ประเภททรัพย์"].apply(normalize_prop_type)
        df["sale_type_clean"] = df["ประเภทการขาย"].apply(normalize_sale_type)
        df["area_sqw"] = df["เนื้อที่ (ตร.ว.)"].apply(parse_rai_ngan_wa)
        df["area_sqm"] = pd.to_numeric(df["พื้นที่ใช้สอย (ตร.ม.)"], errors="coerce")
        df["appraisal_num"] = pd.to_numeric(df["ราคา"], errors="coerce")

    # 3. Smart Multi-Stage Matching Recovery Analysis
    # Let's build a master lookup pool from merge_09, merge_10, npa_10, npa_11 to see how many additional report rows we can enrich
    print("3. Running Smart Multi-Stage Matcher to enrich sold properties...")
    pool_cols = [
        "ID", "case_clean", "เลขโฉนด", "prop_type_clean", "sale_type_clean",
        "appraisal_num", "ตำบล", "อำเภอ", "จังหวัด", "ละติจูด", "ลองจิจูด",
        "ชื่อประกาศ", "ลิงก์", "เนื้อที่ (ตร.ว.)", "area_sqw", "area_sqm", "วันประกาศ"
    ]
    pool_df = pd.concat(
        [merge_09[pool_cols], merge_10[pool_cols], npa_10[pool_cols], npa_11[pool_cols]],
        ignore_index=True
    ).drop_duplicates(subset=["ID"], keep="first")

    # Combine existing merge_09 + merge_10 as base enriched sold dataset
    sold_enriched = pd.concat([merge_09, merge_10], ignore_index=True)

    # Also check how many unmatched report_09 and report_10 rows can be matched via (case_clean + exact appraisal_num)
    # against pool_df (especially condos with deed == '-' or multi-deed properties)
    existing_keys_09 = set(zip(merge_09["case_clean"], merge_09["appraisal_num"].round(0)))
    existing_keys_10 = set(zip(merge_10["case_clean"], merge_10["appraisal_num"].round(0)))

    pool_by_case_price = pool_df.dropna(subset=["case_clean", "appraisal_num"]).copy()
    pool_by_case_price["price_round"] = pool_by_case_price["appraisal_num"].round(0)
    pool_by_case_price = pool_by_case_price.drop_duplicates(subset=["case_clean", "price_round"])

    recovered_rows = []
    for rep_df, m_label, exist_k in [(report_09, "2026-09", existing_keys_09), (report_10, "2026-10", existing_keys_10)]:
        rep_sub = rep_df.dropna(subset=["case_clean", "appraisal_num"]).copy()
        rep_sub["price_round"] = rep_sub["appraisal_num"].round(0)
        unmatched = rep_sub[~rep_sub.set_index(["case_clean", "price_round"]).index.isin(exist_k)].copy()
        merged_rec = pd.merge(
            unmatched,
            pool_by_case_price,
            on=["case_clean", "price_round"],
            how="inner",
            suffixes=("_rep", "")
        )
        if len(merged_rec) > 0:
            # Convert date format DD/MM/2569 -> 2026-MM-DD
            def parse_thai_date(d_str):
                try:
                    p = str(d_str).strip().split("/")
                    if len(p) == 3:
                        y = int(p[2]) - 543
                        return f"{y:04d}-{int(p[1]):02d}-{int(p[0]):02d}"
                except Exception:
                    pass
                return None

            merged_rec["วันที่ขาย"] = merged_rec["วันที่ขาย"].apply(parse_thai_date)
            merged_rec["วันประกาศ_dt"] = pd.to_datetime(merged_rec["วันประกาศ"], errors="coerce")
            merged_rec["วันที่ขาย_dt"] = pd.to_datetime(merged_rec["วันที่ขาย"], errors="coerce")
            merged_rec["days_to_sell"] = (merged_rec["วันที่ขาย_dt"] - merged_rec["วันประกาศ_dt"]).dt.days
            merged_rec["ราคา"] = merged_rec["appraisal_num_rep"]
            merged_rec["ราคาขายได้"] = merged_rec["sold_num"]
            merged_rec["appraisal_num"] = merged_rec["appraisal_num_rep"]
            merged_rec["รหัสทรัพย์"] = merged_rec["case_clean"]
            merged_rec["recovered"] = 1
            recovered_rows.append(merged_rec)

    sold_enriched["recovered"] = 0
    if recovered_rows:
        rec_df = pd.concat(recovered_rows, ignore_index=True)
        common_cols = [c for c in sold_enriched.columns if c in rec_df.columns]
        sold_enriched = pd.concat([sold_enriched, rec_df[common_cols]], ignore_index=True)

    # Calculate unit prices on sold_enriched
    sold_enriched["unit_area"] = np.where(
        sold_enriched["prop_type_clean"] == "ห้องชุด",
        sold_enriched["area_sqm"],
        sold_enriched["area_sqw"],
    )
    sold_enriched["appraisal_per_unit"] = np.where(
        sold_enriched["unit_area"] > 0,
        sold_enriched["appraisal_num"] / sold_enriched["unit_area"],
        np.nan,
    )
    sold_enriched["sold_per_unit"] = np.where(
        sold_enriched["unit_area"] > 0,
        sold_enriched["sold_num"] / sold_enriched["unit_area"],
        np.nan,
    )

    print(f"   Total Enriched Sold Properties: {len(sold_enriched):,} (Original: {len(merge_09)+len(merge_10):,}, Recovered: {(sold_enriched['recovered']==1).sum():,})")

    # 4. Calculate Spatial / Regional Price Benchmarks (by Province + Amphoe + Property Type, and Province + Property Type)
    print("4. Computing Spatial Price Benchmarks & Deal Scores for Active NPA (Nov 2026)...")
    valid_sold_unit = sold_enriched[
        (sold_enriched["sold_per_unit"] > 100) & (sold_enriched["sold_per_unit"] < 1e7)
    ]
    bench_amp = (
        valid_sold_unit.groupby(["จังหวัด", "อำเภอ", "prop_type_clean"])["sold_per_unit"]
        .agg(med_sold_unit="median", cnt_sold="count")
        .reset_index()
    )
    bench_amp = bench_amp[bench_amp["cnt_sold"] >= 3]  # require at least 3 sold properties in amphoe

    bench_prov = (
        valid_sold_unit.groupby(["จังหวัด", "prop_type_clean"])["sold_per_unit"]
        .agg(prov_med_sold_unit="median")
        .reset_index()
    )

    # Also compute median appraisal per unit in npa_11 by (จังหวัด, อำเภอ, prop_type_clean) as secondary benchmark
    npa_11["unit_area"] = np.where(
        npa_11["prop_type_clean"] == "ห้องชุด",
        npa_11["area_sqm"],
        npa_11["area_sqw"],
    )
    npa_11["appraisal_per_unit"] = np.where(
        npa_11["unit_area"] > 0,
        npa_11["appraisal_num"] / np.where(npa_11["unit_area"] > 0, npa_11["unit_area"], np.nan),
        np.nan,
    )
    valid_npa_unit = npa_11[(npa_11["appraisal_per_unit"] > 100) & (npa_11["appraisal_per_unit"] < 1e7)]
    bench_npa_amp = (
        valid_npa_unit.groupby(["จังหวัด", "อำเภอ", "prop_type_clean"])["appraisal_per_unit"]
        .agg(med_npa_unit="median")
        .reset_index()
    )

    # Merge benchmarks into npa_11
    npa_11 = npa_11.merge(bench_amp[["จังหวัด", "อำเภอ", "prop_type_clean", "med_sold_unit"]], on=["จังหวัด", "อำเภอ", "prop_type_clean"], how="left")
    npa_11 = npa_11.merge(bench_prov, on=["จังหวัด", "prop_type_clean"], how="left")
    npa_11 = npa_11.merge(bench_npa_amp, on=["จังหวัด", "อำเภอ", "prop_type_clean"], how="left")

    # Benchmark unit price: prefer amphoe sold median -> amphoe npa median -> province sold median
    npa_11["benchmark_unit_price"] = (
        npa_11["med_sold_unit"]
        .fillna(npa_11["med_npa_unit"])
        .fillna(npa_11["prov_med_sold_unit"])
    )

    # Calculate discount % vs benchmark unit price: positive means cheaper than benchmark!
    npa_11["discount_vs_bench_pct"] = np.where(
        (npa_11["benchmark_unit_price"] > 0) & (npa_11["appraisal_per_unit"] > 0),
        (1.0 - (npa_11["appraisal_per_unit"] / npa_11["benchmark_unit_price"])) * 100.0,
        0.0,
    )
    npa_11["discount_vs_bench_pct"] = npa_11["discount_vs_bench_pct"].clip(-100.0, 95.0)

    # Calculate days since announcement (as of 2026-11-06)
    ref_date = pd.Timestamp("2026-11-06")
    npa_11["วันประกาศ_dt"] = pd.to_datetime(npa_11["วันประกาศ"], errors="coerce")
    npa_11["days_listed"] = (ref_date - npa_11["วันประกาศ_dt"]).dt.days.fillna(60).clip(0, 1000)

    # Estimate Auction Round based on days_listed (LED typically schedules rounds every ~21-30 days after announcement)
    # <60d: Round 1 (100%), 60-89d: Round 2 (90%), 90-119d: Round 3 (80%), >=120d: Round 4+ (70%)
    npa_11["est_round"] = np.select(
        [
            npa_11["days_listed"] < 60,
            npa_11["days_listed"] < 90,
            npa_11["days_listed"] < 120,
        ],
        [1, 2, 3],
        default=4,
    )
    npa_11["est_round_pct"] = np.select(
        [
            npa_11["est_round"] == 1,
            npa_11["est_round"] == 2,
            npa_11["est_round"] == 3,
        ],
        [100, 90, 80],
        default=70,
    )

    # Province Sell-Through Rate for Liquidity Score
    prov_sold_cnt = sold_enriched["จังหวัด"].value_counts()
    prov_npa_cnt = npa_11["จังหวัด"].value_counts()
    prov_sell_rate = (prov_sold_cnt / prov_npa_cnt * 100.0).fillna(2.0)
    npa_11["prov_liquidity_rate"] = npa_11["จังหวัด"].map(prov_sell_rate).fillna(2.0)

    # Multi-Factor Deal Score (0 - 100)
    # 1. Price Discount vs Local Benchmark (0 - 35 pts): 0% discount -> 10 pts, +50% cheaper -> 35 pts
    s_price = ((npa_11["discount_vs_bench_pct"] + 20.0) / 70.0 * 35.0).clip(0.0, 35.0)
    # 2. Auction Round Discount Potential (0 - 25 pts): Round 4 (70%) -> 25 pts, Round 3 (80%) -> 20 pts, Round 2 -> 12 pts, Round 1 -> 5 pts
    s_round = np.select(
        [npa_11["est_round"] == 4, npa_11["est_round"] == 3, npa_11["est_round"] == 2],
        [25.0, 20.0, 12.0],
        default=5.0,
    )
    # 3. Mortgage-Free Sale Condition (0 - 20 pts): ปลอดจำนอง / ไม่มีภาระจำนอง -> 20 pts, จำนองติดไป -> 2 pts
    s_cond = np.where(npa_11["sale_type_clean"] == "การจำนองติดไป", 2.0, 20.0)
    # 4. Location Liquidity Score (0 - 20 pts): scaled against top province sell-through rate (~25% over 2 months)
    s_liq = (npa_11["prov_liquidity_rate"] / 25.0 * 20.0).clip(2.0, 20.0)

    npa_11["deal_score"] = (s_price + s_round + s_cond + s_liq).round(1)

    # 5. Build Summary Statistics & Aggregations for Charts
    print("5. Building Summary Statistics & Chart Data...")
    comb_rep = pd.concat([report_09, report_10], ignore_index=True)
    valid_rep = comb_rep[(comb_rep["ratio"] > 0.05) & (comb_rep["ratio"] < 5.0)].copy()

    # Bracket distribution
    bins = [0, 0.699, 0.799, 0.899, 0.999, 1.0001, 1.2, 1.5, 5.0]
    labels = [
        "<70% (จำนองติดไป/ส่วนลดลึก)",
        "70–79.9% (นัดที่ 4+)",
        "80–89.9% (นัดที่ 3)",
        "90–99.9% (นัดที่ 2)",
        "100% พอดี (ราคาเปิดนัด 1)",
        "100.1–120% (สู้ราคา 1-5 ยก)",
        "120.1–150% (แข่งขันสูง)",
        ">150% (สงครามราคาเดือด)",
    ]
    valid_rep["bracket"] = pd.cut(valid_rep["ratio"], bins=bins, labels=labels)
    b_cnt = valid_rep["bracket"].value_counts().reindex(labels).fillna(0).astype(int)
    b_pct = (b_cnt / b_cnt.sum() * 100.0).round(2)

    # Monthly comparison
    m_stats = {}
    for m_key, r_df, m_df in [("2026-09", report_09, merge_09), ("2026-10", report_10, merge_10)]:
        v_r = r_df[(r_df["appraisal_num"] > 0) & (r_df["sold_num"] > 0)]
        m_stats[m_key] = {
            "sold_count": int(len(r_df)),
            "total_appraisal": float(r_df["appraisal_num"].sum()),
            "total_sold": float(r_df["sold_num"].sum()),
            "median_ratio": round(float(v_r["ratio"].median()), 4),
            "pct_above_appraisal": round(float((v_r["ratio"] > 1.0).mean() * 100), 2),
            "pct_below_appraisal": round(float((v_r["ratio"] < 1.0).mean() * 100), 2),
            "pct_equal_appraisal": round(float((v_r["ratio"] == 1.0).mean() * 100), 2),
            "orig_merged_count": int(len(m_df)),
            "smart_merged_count": int((sold_enriched["month"] == m_key).sum()),
        }

    # Property Type Summary
    prop_summary = []
    for pt in ["ที่ดินพร้อมสิ่งปลูกสร้าง", "ที่ดินว่างเปล่า", "ห้องชุด", "สิ่งปลูกสร้าง"]:
        sub_s = sold_enriched[(sold_enriched["prop_type_clean"] == pt) & (sold_enriched["ratio"] > 0)]
        sub_n = npa_11[npa_11["prop_type_clean"] == pt]
        prop_summary.append({
            "type": pt,
            "active_count": int(len(sub_n)),
            "active_total_val": float(sub_n["appraisal_num"].sum()),
            "sold_count_enriched": int(len(sub_s)),
            "sold_count_report": int((comb_rep["prop_type_clean"] == pt).sum()),
            "median_appraisal": float(sub_s["appraisal_num"].median()) if len(sub_s) else 0,
            "median_sold": float(sub_s["sold_num"].median()) if len(sub_s) else 0,
            "median_ratio": round(float(sub_s["ratio"].median()), 3) if len(sub_s) else 0,
            "pct_above_appraisal": round(float((sub_s["ratio"] > 1.0).mean() * 100), 1) if len(sub_s) else 0,
            "pct_below_appraisal": round(float((sub_s["ratio"] < 1.0).mean() * 100), 1) if len(sub_s) else 0,
            "median_days_to_sell": round(float(sub_s["days_to_sell"].median()), 0) if len(sub_s) else 0,
            "median_unit_price_sold": round(float(sub_s["sold_per_unit"].median()), 0) if sub_s["sold_per_unit"].notna().sum() > 0 else 0,
        })

    # Sale Type Summary
    sale_summary = []
    for st in ["ปลอดการจำนอง", "ไม่มีภาระจำนอง", "ปลอดภาระผูกพัน", "การจำนองติดไป"]:
        sub_s = sold_enriched[(sold_enriched["sale_type_clean"] == st) & (sold_enriched["ratio"] > 0)]
        sub_n = npa_11[npa_11["sale_type_clean"] == st]
        sale_summary.append({
            "sale_type": st,
            "active_count": int(len(sub_n)),
            "sold_count": int(len(sub_s)),
            "median_ratio": round(float(sub_s["ratio"].median()), 3) if len(sub_s) else 0,
            "pct_below_appraisal": round(float((sub_s["ratio"] < 1.0).mean() * 100), 1) if len(sub_s) else 0,
            "pct_above_appraisal": round(float((sub_s["ratio"] > 1.0).mean() * 100), 1) if len(sub_s) else 0,
            "mean_appraisal": round(float(sub_s["appraisal_num"].mean()), 0) if len(sub_s) else 0,
            "mean_sold": round(float(sub_s["sold_num"].mean()), 0) if len(sub_s) else 0,
        })

    # Province Summary (All 77 Provinces)
    all_provs = sorted(npa_11["จังหวัด"].dropna().unique().tolist())
    prov_summary = []
    prov_file_map = {}

    for idx, pv in enumerate(all_provs, start=1):
        p_code = f"p_{idx:02d}"
        prov_file_map[pv] = p_code
        sub_n11 = npa_11[npa_11["จังหวัด"] == pv]
        sub_n10 = npa_10[npa_10["จังหวัด"] == pv]
        sub_s = sold_enriched[sold_enriched["จังหวัด"] == pv]
        sub_s_oct = sub_s[sub_s["month"] == "2026-10"]
        sub_s_sep = sub_s[sub_s["month"] == "2026-09"]

        lat_med = float(sub_n11["ละติจูด"].median()) if sub_n11["ละติจูด"].notna().sum() > 0 else 13.75
        lon_med = float(sub_n11["ลองจิจูด"].median()) if sub_n11["ลองจิจูด"].notna().sum() > 0 else 100.50

        n10_cnt = max(len(sub_n10), 1)
        sell_rate_2m = round(len(sub_s) / n10_cnt * 100.0, 2)
        sell_rate_oct = round(len(sub_s_oct) / n10_cnt * 100.0, 2)

        prov_summary.append({
            "code": p_code,
            "province": pv,
            "lat": round(lat_med, 5),
            "lon": round(lon_med, 5),
            "active_npa10": int(len(sub_n10)),
            "active_npa11": int(len(sub_n11)),
            "active_total_val": round(float(sub_n11["appraisal_num"].sum()), 0),
            "sold_sep": int(len(sub_s_sep)),
            "sold_oct": int(len(sub_s_oct)),
            "sold_total": int(len(sub_s)),
            "sold_total_val": round(float(sub_s["sold_num"].sum()), 0),
            "sell_rate_2m_pct": sell_rate_2m,
            "sell_rate_oct_pct": sell_rate_oct,
            "median_ratio": round(float(sub_s["ratio"].median()), 3) if len(sub_s) > 0 else 1.0,
            "pct_below_appraisal": round(float((sub_s["ratio"] < 1.0).mean() * 100.0), 1) if len(sub_s) > 0 else 0.0,
            "median_days": round(float(sub_s["days_to_sell"].median()), 0) if sub_s["days_to_sell"].notna().sum() > 0 else 0,
            "avg_deal_score": round(float(sub_n11["deal_score"].mean()), 1) if len(sub_n11) > 0 else 0.0,
            "top_deals_count": int((sub_n11["deal_score"] >= 70.0).sum()),
        })

    # Plaintiff / Creditor Summary (Top 25 across Report & Active NPA)
    rep_p_grp = comb_rep.groupby("โจทก์").agg(
        sold_count=("sold_num", "count"),
        sold_val=("sold_num", "sum"),
        appraisal_val=("appraisal_num", "sum"),
        median_ratio=("ratio", "median"),
        pct_below=("ratio", lambda x: (x < 1.0).mean() * 100.0),
    )
    npa_p_grp = npa_11.groupby("โจทก์").agg(
        active_count=("ID", "count"),
        active_val=("appraisal_num", "sum"),
    )
    cred_df = rep_p_grp.join(npa_p_grp, how="outer").fillna(0)
    cred_df["total_activity"] = cred_df["sold_count"] + cred_df["active_count"]
    cred_df["turnover_pct"] = np.where(
        (cred_df["active_count"] + cred_df["sold_count"]) > 0,
        cred_df["sold_count"] / (cred_df["active_count"] + cred_df["sold_count"]) * 100.0,
        0.0,
    )
    cred_top = cred_df.sort_values("sold_count", ascending=False).head(25).reset_index()
    creditor_summary = []
    for _, row in cred_top.iterrows():
        creditor_summary.append({
            "plaintiff": str(row["โจทก์"]),
            "sold_count": int(row["sold_count"]),
            "sold_val": round(float(row["sold_val"]), 0),
            "active_count": int(row["active_count"]),
            "active_val": round(float(row["active_val"]), 0),
            "median_ratio": round(float(row["median_ratio"]), 3),
            "pct_below": round(float(row["pct_below"]), 1),
            "turnover_pct": round(float(row["turnover_pct"]), 1),
        })

    # Inventory Churn Summary (Oct -> Nov)
    id_10 = set(npa_10["ID"])
    id_11 = set(npa_11["ID"])
    inventory_churn = {
        "npa10_total": int(len(id_10)),
        "npa11_total": int(len(id_11)),
        "retained": int(len(id_10 & id_11)),
        "exited_oct": int(len(id_10 - id_11)),
        "new_inflow_nov": int(len(id_11 - id_10)),
        "retained_pct": round(len(id_10 & id_11) / len(id_10) * 100.0, 2),
        "exited_pct": round(len(id_10 - id_11) / len(id_10) * 100.0, 2),
    }

    # Daily Sale Trend & Match Rate in Sep vs Oct (for Data Pipeline Health Chart)
    r10_dates = report_10["วันที่ขาย"].value_counts().to_dict()
    m10_dates = merge_10["วันที่ขาย"].value_counts().to_dict()
    oct_daily_pipeline = []
    for d_thai, r_cnt in sorted(r10_dates.items(), key=lambda x: x[0]):
        p = str(d_thai).split("/")
        iso_d = f"{int(p[2])-543:04d}-{int(p[1]):02d}-{int(p[0]):02d}" if len(p) == 3 else d_thai
        m_cnt = int(m10_dates.get(iso_d, 0))
        s_cnt = int(((sold_enriched["month"] == "2026-10") & (sold_enriched["วันที่ขาย"] == iso_d)).sum())
        oct_daily_pipeline.append({
            "date": iso_d,
            "date_thai": d_thai,
            "report_sold": int(r_cnt),
            "orig_merged": m_cnt,
            "smart_merged": s_cnt,
            "orig_rate_pct": round(m_cnt / max(r_cnt, 1) * 100.0, 1),
            "smart_rate_pct": round(s_cnt / max(r_cnt, 1) * 100.0, 1),
        })
    oct_daily_pipeline.sort(key=lambda x: x["date"])

    summary_payload = {
        "generated_at": "2026-11-06",
        "monthly": m_stats,
        "brackets": {
            "labels": labels,
            "counts": b_cnt.tolist(),
            "percents": b_pct.tolist(),
        },
        "property_types": prop_summary,
        "sale_types": sale_summary,
        "provinces": prov_summary,
        "prov_file_map": prov_file_map,
        "creditors": creditor_summary,
        "inventory_churn": inventory_churn,
        "oct_daily_pipeline": oct_daily_pipeline,
        "pipeline_health": {
            "report_09_rows": int(len(report_09)),
            "merge_09_orig": int(len(merge_09)),
            "merge_09_smart": int((sold_enriched["month"] == "2026-09").sum()),
            "report_10_rows": int(len(report_10)),
            "merge_10_orig": int(len(merge_10)),
            "merge_10_smart": int((sold_enriched["month"] == "2026-10").sum()),
            "condos_missing_deed_09": int((report_09["ที่ดินโฉนด"] == "-").sum()),
            "condos_missing_deed_10": int((report_10["ที่ดินโฉนด"] == "-").sum()),
            "npa_11_underscore_cases": int(npa_11["รหัสทรัพย์"].astype(str).str.contains("_").sum()),
        },
    }

    with open(os.path.join(DATA_OUT_DIR, "dashboard_summary.js"), "w", encoding="utf-8") as fp:
        fp.write("window.LED_SUMMARY = ")
        json.dump(summary_payload, fp, ensure_ascii=False, separators=(",", ":"))
        fp.write(";\n")

    # 6. Export Compact Sold Points for Full-Screen Map (`data/map_sold.js`)
    # Schema for compact sold array item:
    # [0:id, 1:case_clean, 2:prop_type, 3:sale_type, 4:appraisal, 5:sold, 6:ratio,
    #  7:tambon, 8:amphoe, 9:province, 10:lat, 11:lon, 12:area_str, 13:unit_area,
    #  14:unit_price_sold, 15:deed, 16:plaintiff, 17:court, 18:announce_date, 19:sold_date, 20:days_to_sell, 21:month]
    print("6. Exporting geolocated Sold Properties (data/map_sold.js)...")
    sold_geo = sold_enriched.dropna(subset=["ละติจูด", "ลองจิจูด", "appraisal_num", "sold_num"]).copy()
    sold_geo = sold_geo[(sold_geo["ละติจูด"] > 5.0) & (sold_geo["ละติจูด"] < 21.0) & (sold_geo["ลองจิจูด"] > 97.0) & (sold_geo["ลองจิจูด"] < 106.0)]

    def fast_export_sold(df_s):
        ids = df_s["ID"].fillna(0).astype(int).tolist()
        cases = df_s["case_clean"].fillna("-").astype(str).tolist()
        ptypes = df_s["prop_type_clean"].fillna("-").astype(str).tolist()
        stypes = df_s["sale_type_clean"].fillna("-").astype(str).tolist()
        apps = df_s["appraisal_num"].fillna(0).round(0).astype(int).tolist()
        solds = df_s["sold_num"].fillna(0).round(0).astype(int).tolist()
        ratios = df_s["ratio"].fillna(1.0).round(3).tolist()
        tambons = df_s["ตำบล"].fillna("-").astype(str).tolist()
        amphoes = df_s["อำเภอ"].fillna("-").astype(str).tolist()
        provs = df_s["จังหวัด"].fillna("-").astype(str).tolist()
        lats = df_s["ละติจูด"].round(5).tolist()
        lons = df_s["ลองจิจูด"].round(5).tolist()
        area_strs = np.where(
            df_s["เนื้อที่ (ตร.ว.)"].notna(),
            df_s["เนื้อที่ (ตร.ว.)"].astype(str),
            np.where(df_s["area_sqm"].notna(), df_s["area_sqm"].astype(str) + " ตร.ม.", "-"),
        ).tolist()
        u_areas = df_s["unit_area"].fillna(0).round(2).tolist()
        u_solds = df_s["sold_per_unit"].fillna(0).round(0).astype(int).tolist()
        deeds = df_s["เลขโฉนด"].fillna("-").astype(str).tolist()
        plaints = df_s["โจทก์"].fillna("-").astype(str).tolist()
        courts = df_s["ศาล"].fillna("-").astype(str).tolist()
        ann_dates = df_s["วันประกาศ"].fillna("-").astype(str).tolist()
        sold_dates = df_s["วันที่ขาย"].fillna("-").astype(str).tolist()
        days = df_s["days_to_sell"].fillna(0).astype(int).tolist()
        months = df_s["month"].fillna("-").astype(str).tolist()
        return [list(x) for x in zip(
            ids, cases, ptypes, stypes, apps, solds, ratios,
            tambons, amphoes, provs, lats, lons, area_strs, u_areas,
            u_solds, deeds, plaints, courts, ann_dates, sold_dates, days, months
        )]

    sold_records = fast_export_sold(sold_geo)

    with open(os.path.join(DATA_OUT_DIR, "map_sold.js"), "w", encoding="utf-8") as fp:
        fp.write("window.LED_SOLD = ")
        json.dump(sold_records, fp, ensure_ascii=False, separators=(",", ":"))
        fp.write(";\n")

    print("7. Exporting Top 3,000 Deals & 77 Per-Province Active NPA chunks...")
    npa_geo = npa_11.dropna(subset=["ละติจูด", "ลองจิจูด", "appraisal_num"]).copy()

    def fast_export_npa(df_n):
        ids = df_n["ID"].fillna(0).astype(int).tolist()
        cases = df_n["case_clean"].fillna("-").astype(str).tolist()
        ptypes = df_n["prop_type_clean"].fillna("-").astype(str).tolist()
        stypes = df_n["sale_type_clean"].fillna("-").astype(str).tolist()
        apps = df_n["appraisal_num"].fillna(0).round(0).astype(int).tolist()
        scores = df_n["deal_score"].fillna(50.0).round(1).tolist()
        discs = df_n["discount_vs_bench_pct"].fillna(0.0).round(1).tolist()
        tambons = df_n["ตำบล"].fillna("-").astype(str).tolist()
        amphoes = df_n["อำเภอ"].fillna("-").astype(str).tolist()
        provs = df_n["จังหวัด"].fillna("-").astype(str).tolist()
        lats = df_n["ละติจูด"].round(5).tolist()
        lons = df_n["ลองจิจูด"].round(5).tolist()
        area_strs = np.where(
            df_n["เนื้อที่ (ตร.ว.)"].notna(),
            df_n["เนื้อที่ (ตร.ว.)"].astype(str),
            np.where(df_n["area_sqm"].notna(), df_n["area_sqm"].astype(str) + " ตร.ม.", "-"),
        ).tolist()
        u_areas = df_n["unit_area"].fillna(0).round(2).tolist()
        u_apps = df_n["appraisal_per_unit"].fillna(0).round(0).astype(int).tolist()
        u_benchs = df_n["benchmark_unit_price"].fillna(0).round(0).astype(int).tolist()
        deeds = df_n["เลขโฉนด"].fillna("-").astype(str).tolist()
        plaints = df_n["โจทก์"].fillna("-").astype(str).tolist()
        courts = df_n["ศาล"].fillna("-").astype(str).tolist()
        ann_dates = df_n["วันประกาศ"].fillna("-").astype(str).tolist()
        days_l = df_n["days_listed"].fillna(0).astype(int).tolist()
        est_r = df_n["est_round"].fillna(1).astype(int).tolist()
        est_p = df_n["est_round_pct"].fillna(100).astype(int).tolist()
        return [list(x) for x in zip(
            ids, cases, ptypes, stypes, apps, scores, discs,
            tambons, amphoes, provs, lats, lons, area_strs, u_areas,
            u_apps, u_benchs, deeds, plaints, courts, ann_dates, days_l, est_r, est_p
        )]

    # Top 3,000 deals (filter out extreme outliers and require positive benchmark comparison)
    top_candidates = npa_geo[
        (npa_geo["appraisal_num"] >= 50000)
        & (npa_geo["unit_area"] > 0)
        & (npa_geo["benchmark_unit_price"] > 0)
    ].sort_values(["deal_score", "discount_vs_bench_pct"], ascending=[False, False]).head(3000)

    top_deals_list = fast_export_npa(top_candidates)
    with open(os.path.join(DATA_OUT_DIR, "top_deals.js"), "w", encoding="utf-8") as fp:
        fp.write("window.LED_TOP_DEALS = ")
        json.dump(top_deals_list, fp, ensure_ascii=False, separators=(",", ":"))
        fp.write(";\n")

    # Per-province chunks for all 94,659 rows
    for pv, p_code in prov_file_map.items():
        sub_p = npa_geo[npa_geo["จังหวัด"] == pv].sort_values("deal_score", ascending=False)
        p_records = fast_export_npa(sub_p)
        p_path = os.path.join(PROV_OUT_DIR, f"{p_code}.js")
        with open(p_path, "w", encoding="utf-8") as fp:
            fp.write("window.LED_PROV_DATA = window.LED_PROV_DATA || {};\n")
            fp.write(f"window.LED_PROV_DATA[{json.dumps(pv, ensure_ascii=False)}] = ")
            json.dump(p_records, fp, ensure_ascii=False, separators=(",", ":"))
            fp.write(";\n")

    print("8. Done! All compact JS files generated successfully in ./data/")


if __name__ == "__main__":
    main()
