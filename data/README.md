# Mesa — popular-times data pipeline

This folder contains the one-time data-fetching pipeline that powers Mesa's
"best now" feature. It is **not** part of the live web app — it runs on your
laptop, produces a `popular_times.json` file, and that file ships with the app.

## What it does

1. Queries SerpAPI's Google Maps endpoint for each of the 30 Mesa spots.
2. Extracts each spot's hourly "popular times" busyness data (7 days × 24 hours).
3. Computes each spot's average weekday rhythm (24-element feature vector).
4. Runs **k-means clustering (k=4)** on those vectors to discover natural
   temporal categories — without us defining them manually. Spots with similar
   rhythms end up in the same cluster.
5. Names each cluster by its peak hour (morning / midday / afternoon / evening
   / late_night).
6. Saves everything to `../popular_times.json`, which the app reads at runtime.

## Setup (one time)

```bash
# from this folder
cp .env.example .env
# open .env and paste your real SerpAPI key

pip3 install -r requirements.txt   # or:
pip3 install requests scikit-learn numpy python-dotenv
```

## Run

```bash
python3 fetch_and_cluster.py
```

Takes about a minute (30 API calls with 1-second pause between each, plus
~1 second of clustering math). Prints progress as it goes and a summary at
the end:

```
Cluster 0 — morning   (peak hour 10h)  6 spots
  · Slow Coffee
  · Faraday Coffee
  · ACID café
  ...
Cluster 1 — evening   (peak hour 21h)  12 spots
  ...
```

When it's done, `../popular_times.json` exists in your Mesa folder. Push your
Mesa repo and the live app will use the new data.

## Cost

~30 SerpAPI searches per run. Free tier covers 100/month — re-run as often as
you want, though once a year is plenty since Google's popular-times data is
itself a long-term rolling average.

## Editing the spots

Edit the `SPOTS` list near the top of `fetch_and_cluster.py`. Keep it in sync
with `leafletsData` in `../index.html` if you change either one.

## Troubleshooting

**`SERPAPI_KEY not found`** — you forgot to create `.env` from `.env.example`,
or your `.env` is missing the key.

**A spot says MISSING** — Google doesn't have popular-times data for that place
(too new, too quiet, not enough visit data). Try refining its `query` field to
include a more specific address. If still missing, the spot will appear in the
app with zero busyness and won't show up in the "best now" rankings.

**`ModuleNotFoundError`** — run the `pip3 install …` line above.
