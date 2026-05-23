"""
Mesa — Popular Times fetcher + clustering pipeline.

Reads the 30 Mesa spots, queries SerpAPI for each one's Google "popular times"
data, then runs k-means clustering on the spots' weekday busyness rhythms to
discover natural temporal categories (morning / afternoon / evening / late-night
etc). Writes the result to ../popular_times.json which the live app reads.

Run from inside the data/ folder:
    python3 fetch_and_cluster.py

Cost: ~30 SerpAPI searches (free tier covers up to 100/month).
Re-run only when spots change, or once a year to refresh data.
"""

import json
import time
import os
import sys
from pathlib import Path

# ── Third-party imports ──────────────────────────────────────────
try:
    import requests
    import numpy as np
    from sklearn.cluster import KMeans
    from dotenv import load_dotenv
except ImportError as e:
    print(f"\n[!] Missing dependency: {e}")
    print("[!] Run: pip3 install requests scikit-learn numpy python-dotenv")
    sys.exit(1)

# ── Load secrets from .env ───────────────────────────────────────
load_dotenv()
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
if not SERPAPI_KEY:
    print("\n[!] SERPAPI_KEY not found.")
    print("[!] Copy .env.example to .env and paste your SerpAPI key.")
    sys.exit(1)

# ── Mesa spots (keep in sync with leafletsData in index.html) ─────
# Each spot: name, leaflet index, lat, lng, query (what to search on Google Maps)
SPOTS = [
    # Leaflet 1 — downtown brunch
    {"name": "Slow Coffee",    "leaflet": 1, "lat": 40.4108, "lng": -3.7136,
     "query": "Slow Cafe Mediodía Grande 20 Madrid"},
    {"name": "Casa Victoria",  "leaflet": 1, "lat": 40.4128, "lng": -3.7027,
     "query": "Casa Victoria Olmo 20 Madrid"},
    {"name": "Faraday Coffee", "leaflet": 1, "lat": 40.4234, "lng": -3.6961,
     "query": "Faraday Coffee San Lucas 9 Madrid"},
    {"name": "FELIZ Coffee",   "leaflet": 1, "lat": 40.4137, "lng": -3.6975,
     "query": "FELIZ Coffee Lope de Vega 2 Madrid"},
    {"name": "Casa Neutrale",  "leaflet": 1, "lat": 40.4256, "lng": -3.6968,
     "query": "Casa Neutrale Regueros 13 Madrid"},

    # Leaflet 2 — downtown cocktail/wine
    {"name": "GildaHaus",      "leaflet": 2, "lat": 40.4220, "lng": -3.6975,
     "query": "GildaHaus Hortaleza 63 Madrid"},
    {"name": "Casa Música",    "leaflet": 2, "lat": 40.4242, "lng": -3.6975,
     "query": "Casa Música San Mateo 22 Madrid"},
    {"name": "Gota Wine",      "leaflet": 2, "lat": 40.4232, "lng": -3.6920,
     "query": "Gota Wine Prim 5 Madrid"},
    {"name": "Casa Salesas",   "leaflet": 2, "lat": 40.4250, "lng": -3.6948,
     "query": "Casa Salesas Fernando VI 6 Madrid"},
    {"name": "Gabo's",         "leaflet": 2, "lat": 40.4232, "lng": -3.6920,
     "query": "Gabo's Prim 5 Madrid"},

    # Leaflet 3 — wine bars / nightlife
    {"name": "Snake Bar",          "leaflet": 3, "lat": 40.4253, "lng": -3.6917,
     "query": "Snake Bar Marqués de la Ensenada 16 Madrid"},
    {"name": "ChinChin",           "leaflet": 3, "lat": 40.4220, "lng": -3.7045,
     "query": "ChinChin Andrés Borrego Madrid"},
    {"name": "El Internacional",   "leaflet": 3, "lat": 40.4172, "lng": -3.7022,
     "query": "El Internacional Cedaceros 11 Madrid"},
    {"name": "The Madrid Edition", "leaflet": 3, "lat": 40.4178, "lng": -3.7045,
     "query": "The Madrid Edition hotel Plaza Celenque Madrid"},
    {"name": "1862 Dry Bar",       "leaflet": 3, "lat": 40.4248, "lng": -3.7068,
     "query": "1862 Dry Bar Pez 27 Madrid"},

    # Leaflet 4 — cards/cocktails
    {"name": "Sala X",                       "leaflet": 4, "lat": 40.4230, "lng": -3.7078,
     "query": "Sala Equis Miguel Moya 8 Madrid"},
    {"name": "Bastardo Hostel",              "leaflet": 4, "lat": 40.4253, "lng": -3.6995,
     "query": "Bastardo Hostel San Mateo 3 Madrid"},
    {"name": "Mkt San Ildefonso",            "leaflet": 4, "lat": 40.4250, "lng": -3.7015,
     "query": "Mercado San Ildefonso Fuencarral 57 Madrid"},
    {"name": "Café Central",                 "leaflet": 4, "lat": 40.4143, "lng": -3.7008,
     "query": "Café Central Plaza del Ángel 10 Madrid"},
    {"name": "Círculo de las Bellas Artes",  "leaflet": 4, "lat": 40.4192, "lng": -3.6968,
     "query": "Círculo de Bellas Artes Alcalá 42 Madrid"},

    # Leaflet 5
    {"name": "ACID café",         "leaflet": 5, "lat": 40.4124, "lng": -3.6970,
     "query": "ACID Café Verónica 9 Madrid"},
    {"name": "Chez Madrid",       "leaflet": 5, "lat": 40.4153, "lng": -3.6939,
     "query": "Chez Madrid Plaza Cánovas del Castillo 4"},
    {"name": "Bucólico",          "leaflet": 5, "lat": 40.4205, "lng": -3.6985,
     "query": "Bucólico Café Barbieri 4 Madrid"},
    {"name": "Friends in Common", "leaflet": 5, "lat": 40.4282, "lng": -3.6905,
     "query": "Friends in Common Fernando el Santo 24 Madrid"},
    {"name": "Keli",              "leaflet": 5, "lat": 40.4319, "lng": -3.6890,
     "query": "Keli restaurante Castellana 12 Madrid"},

    # Leaflet 6
    {"name": "Sala de Despiece", "leaflet": 6, "lat": 40.4188, "lng": -3.7008,
     "query": "Sala de Despiece Virgen de los Peligros Madrid"},
    {"name": "Her",              "leaflet": 6, "lat": 40.4244, "lng": -3.6845,
     "query": "Her restaurante Hermosilla 4 Madrid"},
    {"name": "LA PAPA",          "leaflet": 6, "lat": 40.4232, "lng": -3.6963,
     "query": "LA PAPA Barquillo 20 Madrid"},
    {"name": "fismuler",         "leaflet": 6, "lat": 40.4282, "lng": -3.6974,
     "query": "Fismuler Sagasta 29 Madrid"},
    {"name": "El Gordito",       "leaflet": 6, "lat": 40.4254, "lng": -3.7045,
     "query": "El Gordito Palma 41 Madrid"},
]

# ── Settings ─────────────────────────────────────────────────────
SERPAPI_URL = "https://serpapi.com/search.json"
DAYS = ["sunday", "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday"]
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
OUTPUT_PATH = Path(__file__).parent.parent / "popular_times.json"
NUM_CLUSTERS = 4  # how many temporal categories to find


# ── Step 1: fetch popular times from SerpAPI ─────────────────────
def fetch_popular_times(spot):
    """Calls SerpAPI Google Maps endpoint, returns the popular_times graph_results
    (a dict mapping day name → list of 24 hourly entries) or None if missing."""
    params = {
        "engine": "google_maps",
        "q": spot["query"],
        "type": "search",
        "ll": f"@{spot['lat']},{spot['lng']},16z",
        "api_key": SERPAPI_KEY,
    }
    try:
        r = requests.get(SERPAPI_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"   [!] Request failed: {e}")
        return None

    # SerpAPI sometimes returns a single 'place_results' object, sometimes a list.
    place = data.get("place_results")
    if not place and data.get("local_results"):
        place = data["local_results"][0]

    if not place:
        print(f"   [!] No place_results in response")
        return None

    pop = place.get("popular_times", {})
    graph = pop.get("graph_results")
    if not graph:
        print(f"   [!] No popular_times.graph_results (place is too quiet or new)")
        return None

    return graph


def normalize_busyness(graph_results):
    """Convert SerpAPI's per-day busyness lists into a clean dict:
       { 'monday': [0..100 for 24 hours], ... }
       Missing entries (closed hours) become 0.
    """
    by_day = {}
    for day in DAYS:
        entries = graph_results.get(day, [])
        scores_by_hour = {}
        for entry in entries:
            # Each entry has a 'time' like "9 AM", "12 PM", etc., and a busyness_score
            time_label = entry.get("time", "")
            score = entry.get("busyness_score", 0) or 0
            hour = parse_hour(time_label)
            if hour is not None:
                scores_by_hour[hour] = int(score)
        # Build the 24-hour array
        hourly = [scores_by_hour.get(h, 0) for h in range(24)]
        by_day[day] = hourly
    return by_day


def parse_hour(label):
    """Parse strings like '6 AM', '12 PM', '11 PM' into 0..23."""
    if not label:
        return None
    label = label.strip().upper().replace(".", "")
    try:
        if "AM" in label:
            n = int(label.replace("AM", "").strip())
            return 0 if n == 12 else n
        elif "PM" in label:
            n = int(label.replace("PM", "").strip())
            return 12 if n == 12 else n + 12
    except ValueError:
        return None
    return None


# ── Step 2: build feature vectors and cluster ────────────────────
def build_feature_vector(busyness_by_day):
    """Average busyness across Mon-Fri for each of 24 hours.
    Returns a 24-element list — the spot's weekday rhythm signature."""
    weekday_arrays = [busyness_by_day[d] for d in WEEKDAYS]
    avg = np.mean(weekday_arrays, axis=0)
    return avg.tolist()


def cluster_spots(spots_with_data, k=NUM_CLUSTERS):
    """Run k-means on the weekday feature vectors. Returns cluster assignments
    and centroids."""
    vectors = np.array([s["features"] for s in spots_with_data])
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(vectors)
    return labels.tolist(), km.cluster_centers_.tolist()


def name_clusters(centroids):
    """Look at each centroid's peak hour and assign a human-readable label."""
    names = []
    palette = ["#e0a55a", "#a8c098", "#c87060", "#5a6b8a", "#8a6ba0"]
    for i, c in enumerate(centroids):
        peak_hour = int(np.argmax(c))
        if peak_hour < 13:
            label = "morning"
        elif peak_hour < 19:
            label = "afternoon"
        elif peak_hour < 21:
            label = "early_evening"
        elif peak_hour < 23:
            label = "late_evening"
        else:
            label = "late_night"
        names.append({
            "id": i,
            "label": label,
            "peak_hour": peak_hour,
            "color": palette[i % len(palette)],
            "centroid": c,
        })
    return names


# ── MAIN ─────────────────────────────────────────────────────────
def main():
    print(f"\n▶ Mesa popular-times pipeline")
    print(f"  {len(SPOTS)} spots to fetch")
    print(f"  Output: {OUTPUT_PATH.resolve()}\n")

    enriched = []
    missing = []

    # Step 1 — Fetch
    for i, spot in enumerate(SPOTS, 1):
        print(f"[{i:>2}/{len(SPOTS)}] {spot['name']:<32s} …", end=" ", flush=True)
        graph = fetch_popular_times(spot)
        if graph is None:
            print("MISSING")
            missing.append(spot["name"])
            # Still include the spot in output, just with zeros (so the app can still pin it)
            zero_hours = [0] * 24
            busyness = {day: zero_hours for day in DAYS}
        else:
            busyness = normalize_busyness(graph)
            peak = max(max(busyness[d]) for d in DAYS)
            print(f"ok (peak {peak})")

        features = build_feature_vector(busyness)
        enriched.append({**spot, "busyness": busyness, "features": features})
        time.sleep(1.0)  # polite rate limiting

    # Step 2 — Cluster only spots that have real data
    with_data = [s for s in enriched if any(s["features"])]
    print(f"\n▶ Clustering {len(with_data)} spots with data into "
          f"{NUM_CLUSTERS} clusters …")

    if len(with_data) < NUM_CLUSTERS:
        print(f"  [!] Not enough data to form {NUM_CLUSTERS} clusters; "
              f"setting cluster=null for everyone.")
        for s in enriched:
            s["cluster"] = None
        clusters_info = []
    else:
        labels, centroids = cluster_spots(with_data)
        # Assign cluster labels back to spots with data
        for s, label in zip(with_data, labels):
            s["cluster"] = int(label)
        # Spots without data get None
        for s in enriched:
            if "cluster" not in s:
                s["cluster"] = None
        clusters_info = name_clusters(centroids)

    # Step 3 — Print summary
    if clusters_info:
        print("\n▶ Discovered clusters:")
        for c in clusters_info:
            members = [s["name"] for s in enriched if s["cluster"] == c["id"]]
            print(f"  Cluster {c['id']} — {c['label']:<10s} "
                  f"(peak hour {c['peak_hour']:>2}h)  {len(members)} spots")
            for m in members:
                print(f"    · {m}")

    if missing:
        print(f"\n  [!] {len(missing)} spots had no popular-times data:")
        for n in missing:
            print(f"      - {n}")

    # Step 4 — Save JSON
    # We strip the 'features' array from the final JSON since it's intermediate.
    # The app only needs: name, lat, lng, leaflet, busyness, cluster.
    output_spots = []
    for s in enriched:
        output_spots.append({
            "name":     s["name"],
            "leaflet":  s["leaflet"],
            "lat":      s["lat"],
            "lng":      s["lng"],
            "busyness": s["busyness"],
            "cluster":  s["cluster"],
        })

    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "spots":        output_spots,
        "clusters":     [
            {"id": c["id"], "label": c["label"],
             "peak_hour": c["peak_hour"], "color": c["color"]}
            for c in clusters_info
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Wrote {OUTPUT_PATH}")
    print(f"  Drop this file into your Mesa repo and git push.\n")


if __name__ == "__main__":
    main()
