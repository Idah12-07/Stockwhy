#!/usr/bin/env python3
"""Swap the fictional facilities for REAL ones from the Government of Kenya facility list.

1. Download the CSV in a browser (CC-BY 4.0), on any computer:
   https://energydata.info/dataset/kenya-healthcare-facilities   (resource: Healthcare_Facilities.csv)
2. Run, for example (30 real facilities from Nakuru county):
   python scripts/import_real_facilities.py --csv Healthcare_Facilities.csv --county Nakuru --dataset data/generated/default
It rewrites facilities.csv in that dataset with real coordinates (so transfer distances are real) and writes
facility_names.csv (FAC-001 -> real name, type, owner, county). Stock, orders and payments stay synthetic.
"""
import argparse
import csv
import random
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True)
ap.add_argument("--dataset", required=True)
ap.add_argument("--county", default=None, help="keep one county, for example Nakuru")
ap.add_argument("--types", default="dispensary,health cent,hospital", help="comma list of words to match in the Type column")
ap.add_argument("--seed", type=int, default=1)
a = ap.parse_args()

ds = Path(a.dataset)
n = sum(1 for _ in open(ds / "facilities.csv")) - 1
raw = Path(a.csv).read_bytes()
try:
    text = raw.decode("utf-8-sig")
except UnicodeDecodeError:
    text = raw.decode("latin-1")
rows = list(csv.DictReader(text.splitlines()))
if not rows:
    raise SystemExit("The CSV has no rows.")


def col(r, *names):
    low = {k.lower(): k for k in r}
    for nme in names:
        if nme.lower() in low:
            return r[low[nme.lower()]]
    return ""


keep = []
words = [w.strip().lower() for w in a.types.split(",") if w.strip()]
for r in rows:
    try:
        lat, lon = float(col(r, "Latitude", "lat")), float(col(r, "Longitude", "lon", "long"))
    except ValueError:
        continue
    if not (-5.0 <= lat <= 5.5 and 33.5 <= lon <= 42.0):  # inside Kenya
        continue
    if a.county and a.county.lower() not in col(r, "County", "County_raw").lower():
        continue
    typ = col(r, "Type").lower()
    if words and not any(w in typ for w in words):
        continue
    keep.append({"name": col(r, "Facility_N", "Facility_Name", "Name"), "type": col(r, "Type"), "owner": col(r, "Owner"),
                 "county": col(r, "County"), "sub_county": col(r, "Sub_County"), "lat": lat, "lon": lon})
if len(keep) < n:
    raise SystemExit(f"Only {len(keep)} usable facilities found but the dataset needs {n}. Remove --county or widen --types.")
random.Random(a.seed).shuffle(keep)
keep = keep[:n]
with open(ds / "facilities.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["facility_id", "lat", "lon"])
    for i, k in enumerate(keep, 1):
        w.writerow([f"FAC-{i:03d}", round(k["lat"], 4), round(k["lon"], 4)])
with open(ds / "facility_names.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["facility_id", "name", "type", "owner", "county", "sub_county"])
    for i, k in enumerate(keep, 1):
        w.writerow([f"FAC-{i:03d}", k["name"], k["type"], k["owner"], k["county"], k["sub_county"]])
print(f"Replaced {n} facilities in {ds} with real ones. Names are in facility_names.csv.")
