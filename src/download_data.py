"""Download a pinned StatsBomb snapshot with a restartable compressed cache."""
from __future__ import annotations
import argparse, concurrent.futures, csv, gzip, hashlib, json, os, time
from pathlib import Path
from urllib.request import Request, urlopen
ROOT = Path(__file__).resolve().parents[1]
def fetch(url):
    for attempt in range(8):
        try:
            with urlopen(Request(url, headers={"User-Agent": "FootballScoutingPortfolio/1.0"}), timeout=35) as r:
                return r.read()
        except Exception:
            if attempt == 7: raise
            time.sleep(min(8,2 ** attempt))
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", type=Path, default=ROOT / "data/raw")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    meta = ROOT / "data/source"
    meta.mkdir(parents=True, exist_ok=True)
    revfile = meta / "revision.json"
    if revfile.exists(): revision = json.loads(revfile.read_text())["sha"]
    else:
        info = json.loads(fetch("https://api.github.com/repos/statsbomb/open-data/commits/master"))
        revision = info["sha"]
        revfile.write_text(json.dumps({"sha": revision, "repository": "https://github.com/statsbomb/open-data"}, indent=2))
    base = f"https://raw.githubusercontent.com/statsbomb/open-data/{revision}/"
    for remote, local in [("data/competitions.json", "competitions.json"), ("data/matches/2/27.json", "matches.json"), ("README.md", "SOURCE_README.md"), ("LICENSE.pdf", "LICENSE.pdf")]:
        p = meta / local
        if not p.exists(): p.write_bytes(fetch(base + remote))
    matches = json.loads((meta / "matches.json").read_bytes())
    manifest_path = meta / "manifest.csv"
    expected = {}
    if manifest_path.exists():
        with manifest_path.open(encoding="utf-8-sig",newline="") as f:
            expected = {(r["kind"],int(r["match_id"])):r["sha256"] for r in csv.DictReader(f)}
    tasks = [(kind, m["match_id"]) for m in matches for kind in ["events", "lineups"]]
    def get(task):
        kind, mid = task
        path = args.cache_dir / kind / f"{mid}.json.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            with gzip.open(path, "rb") as f: raw = f.read()
            json.loads(raw)
        else:
            raw = fetch(base + f"data/{kind}/{mid}.json")
            json.loads(raw)
            tmp = path.with_suffix(".tmp")
            with gzip.open(tmp, "wb", compresslevel=5) as f: f.write(raw)
            os.replace(tmp, path)
        digest = hashlib.sha256(raw).hexdigest()
        if (kind,mid) in expected and digest != expected[(kind,mid)]:
            raise ValueError(f"Cached source hash differs from manifest: {kind}/{mid}. Remove that cached file and rerun.")
        return {"kind": kind, "match_id": mid, "bytes": len(raw), "sha256": digest, "url": base + f"data/{kind}/{mid}.json"}
    rows = []; errors = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, future in enumerate(concurrent.futures.as_completed([pool.submit(get,t) for t in tasks]), 1):
            try: rows.append(future.result())
            except Exception as exc: errors.append(str(exc)); print('Will need retry: '+str(exc)[:180],flush=True)
            if i % 40 == 0 or i == len(tasks): print(f"Downloaded/verified {i}/{len(tasks)} files", flush=True)
    if errors: raise RuntimeError(f'{len(errors)} downloads failed; rerun to resume the cache.')
    with (meta / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["match_id"], r["kind"])))
    print(f"Complete: {len(matches)} matches, revision {revision}", flush=True)
if __name__ == "__main__": main()

