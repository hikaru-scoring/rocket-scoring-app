"""Fetch all launcher configs from Launch Library 2 and save to local cache."""
import requests
import json
import time


def fetch_all():
    results = []
    url = "https://ll.thespacedevs.com/2.2.0/config/launcher/"
    params = {"limit": 100, "offset": 0}

    while True:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("results", []))
        if data.get("next") is None:
            break
        params["offset"] += 100
        time.sleep(5)  # Be respectful of rate limits

    return results


if __name__ == "__main__":
    print("Fetching launcher data...")
    launchers = fetch_all()
    with open("launcher_cache.json", "w") as f:
        json.dump(launchers, f, indent=2)
    print(f"Saved {len(launchers)} launchers to launcher_cache.json")
