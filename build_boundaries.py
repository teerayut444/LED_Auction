"""
Build GIS Administrative Boundaries (Amphoe & Tambon) for LED Auction Dashboard.
Downloads GeoJSON from OpenGISData-Thailand, simplifies geometry,
and splits into 77 lightweight per-province JS chunks in data/boundaries/
"""

import os
import sys
import json
import urllib.request

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

RAW_DIR = os.path.join("data", "boundaries_raw")
OUT_DIR = os.path.join("data", "boundaries")
SUMMARY_FILE = os.path.join("data", "dashboard_summary.js")

URL_DISTRICTS = "https://raw.githubusercontent.com/chingchai/OpenGISData-Thailand/master/districts.geojson"
URL_SUBDISTRICTS = "https://raw.githubusercontent.com/chingchai/OpenGISData-Thailand/master/subdistricts.geojson"
URL_PROVINCES = "https://raw.githubusercontent.com/chingchai/OpenGISData-Thailand/master/provinces.geojson"

def ensure_dirs():
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

def download_file(url, target_path):
    if os.path.exists(target_path) and os.path.getsize(target_path) > 100000:
        print(f"Using cached: {target_path} ({os.path.getsize(target_path)/1024/1024:.2f} MB)")
        return
    print(f"Downloading {url} -> {target_path}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        content = resp.read()
    with open(target_path, "wb") as f:
        f.write(content)
    print(f"Downloaded: {target_path} ({len(content)/1024/1024:.2f} MB)")

def load_prov_file_map():
    if not os.path.exists(SUMMARY_FILE):
        raise FileNotFoundError(f"Missing {SUMMARY_FILE}")
    with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    json_text = text.replace("window.LED_SUMMARY = ", "").rstrip(";\n ")
    data = json.loads(json_text)
    return data.get("prov_file_map", {})

def round_coords(coords, precision=4):
    """Recursively round polygon coordinates to reduce payload size."""
    if not coords:
        return coords
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], precision), round(coords[1], precision)]
    return [round_coords(c, precision) for c in coords]

def build():
    ensure_dirs()

    raw_districts = os.path.join(RAW_DIR, "districts.geojson")
    raw_subdistricts = os.path.join(RAW_DIR, "subdistricts.geojson")
    raw_provinces = os.path.join(RAW_DIR, "provinces.geojson")

    download_file(URL_DISTRICTS, raw_districts)
    download_file(URL_SUBDISTRICTS, raw_subdistricts)
    download_file(URL_PROVINCES, raw_provinces)

    prov_file_map = load_prov_file_map()
    print(f"Loaded prov_file_map with {len(prov_file_map)} provinces.")

    print("Parsing raw GeoJSON files...")
    with open(raw_districts, "r", encoding="utf-8") as f:
        gj_d = json.load(f)
    with open(raw_subdistricts, "r", encoding="utf-8") as f:
        gj_s = json.load(f)
    with open(raw_provinces, "r", encoding="utf-8") as f:
        gj_p = json.load(f)

    # Map province boundary geometry
    prov_geoms = {}
    for f in gj_p["features"]:
        p_name = f.get("properties", {}).get("pro_th", "").strip()
        if p_name and "geometry" in f and f["geometry"]:
            prov_geoms[p_name] = {
                "type": f["geometry"]["type"],
                "coordinates": round_coords(f["geometry"]["coordinates"])
            }

    # Group districts by province
    districts_by_prov = {}
    for f in gj_d["features"]:
        props = f.get("properties", {})
        prov = props.get("pro_th", "").strip()
        if not prov:
            continue
        feat = {
            "type": "Feature",
            "properties": {
                "name": props.get("amp_th", ""),
                "name_en": props.get("amp_en", ""),
                "code": props.get("amp_code", ""),
                "lat": round(float(props.get("lat", 0)), 4) if props.get("lat") else None,
                "lon": round(float(props.get("lon", 0)), 4) if props.get("lon") else None
            },
            "geometry": {
                "type": f["geometry"]["type"],
                "coordinates": round_coords(f["geometry"]["coordinates"])
            }
        }
        districts_by_prov.setdefault(prov, []).append(feat)

    # Group subdistricts by province
    subdistricts_by_prov = {}
    for f in gj_s["features"]:
        props = f.get("properties", {})
        prov = props.get("pro_th", "").strip()
        if not prov:
            continue
        feat = {
            "type": "Feature",
            "properties": {
                "name": props.get("tam_th", ""),
                "name_en": props.get("tam_en", ""),
                "amp": props.get("amp_th", ""),
                "code": props.get("tam_code", ""),
                "lat": round(float(props.get("lat", 0)), 4) if props.get("lat") else None,
                "lon": round(float(props.get("lon", 0)), 4) if props.get("lon") else None
            },
            "geometry": {
                "type": f["geometry"]["type"],
                "coordinates": round_coords(f["geometry"]["coordinates"])
            }
        }
        subdistricts_by_prov.setdefault(prov, []).append(feat)

    sizes = []
    generated = 0

    print("Generating per-province JS boundary chunks...")
    for prov_name, p_code in prov_file_map.items():
        d_feats = districts_by_prov.get(prov_name, [])
        s_feats = subdistricts_by_prov.get(prov_name, [])

        chunk_data = {
            "prov_name": prov_name,
            "p_code": p_code,
            "prov_boundary": prov_geoms.get(prov_name),
            "amphoe": {
                "type": "FeatureCollection",
                "features": d_feats
            },
            "tambon": {
                "type": "FeatureCollection",
                "features": s_feats
            }
        }

        json_payload = json.dumps(chunk_data, separators=(",", ":"), ensure_ascii=False)
        js_content = f'window.LED_BOUNDARIES=window.LED_BOUNDARIES||{{}};window.LED_BOUNDARIES["{p_code}"]={json_payload};\n'

        out_path = os.path.join(OUT_DIR, f"{p_code}.js")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(js_content)

        sz = os.path.getsize(out_path)
        sizes.append(sz)
        generated += 1

    print(f"\nSuccessfully generated {generated} boundary chunks in {OUT_DIR}/")
    print(f"Total size: {sum(sizes)/1024/1024:.2f} MB")
    print(f"Average size per province: {sum(sizes)/len(sizes)/1024:.1f} KB")
    print(f"Min size: {min(sizes)/1024:.1f} KB, Max size: {max(sizes)/1024:.1f} KB")

if __name__ == "__main__":
    build()
