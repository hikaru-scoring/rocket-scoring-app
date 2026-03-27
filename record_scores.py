"""
Daily score recorder for ROCKET-1000 — runs via GitHub Actions.
Fetches current scores for all rockets and appends to scores_history.json.
"""
import json
import os
import sys
import requests
from datetime import datetime, timezone

# Add project root to path so we can import data_logic without streamlit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_logic import score_launcher

HISTORY_FILE = "scores_history.json"
CACHE_FILE = "launcher_cache.json"
API_BASE = "https://ll.thespacedevs.com/2.2.0/config/launcher/"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def fetch_launchers():
    """Fetch from cache first, then API."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)

    all_results = []
    offset = 0
    limit = 100
    try:
        while True:
            resp = requests.get(API_BASE, params={"limit": limit, "offset": offset}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            all_results.extend(data.get("results", []))
            if not data.get("next"):
                break
            offset += limit
    except Exception as e:
        print(f"API error: {e}")
    return all_results


def main():
    print(f"Recording ROCKET-1000 scores for {TODAY}")

    # Load existing history
    history = {}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)

    if TODAY in history:
        print(f"Scores for {TODAY} already recorded. Skipping.")
        return

    launchers = fetch_launchers()
    print(f"Loaded {len(launchers)} launchers")

    today_scores = {}
    for launcher in launchers:
        total_launches = launcher.get("total_launch_count") or 0
        if total_launches < 1:
            continue
        result = score_launcher(launcher)
        name = result["full_name"]
        today_scores[name] = int(result["total"])

    print(f"Scored {len(today_scores)} rockets")

    # Top 10
    top = sorted(today_scores.items(), key=lambda x: x[1], reverse=True)[:10]
    for name, score in top:
        print(f"  {name}: {score}")

    history[TODAY] = today_scores

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

    print(f"Saved to {HISTORY_FILE}")


if __name__ == "__main__":
    main()
