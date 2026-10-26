"""Discover and download public city datasets for CarbonWise.

This collector uses OpenCity's CKAN API to discover Chennai and Mumbai datasets,
then downloads directly linked machine-readable resources. It preserves originals
and writes a provenance manifest. It does not merge unlike datasets or invent
project-level costs/benefits.

Run:
    python scripts/collect_multicity_datasets.py
    python scripts/collect_multicity_datasets.py --city Mumbai
    python scripts/collect_multicity_datasets.py --city all --limit 100

Dependencies: requests (install with pip install requests)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw" / "multicity"
MANIFEST_PATH = ROOT / "data" / "collection" / "multicity_download_manifest.jsonl"
API_BASE = "https://data.opencity.in/api/3/action"
CITIES = {
    "chennai": ["chennai", "greater-chennai-corporation", "flood", "stormwater", "parks", "waterbodies", "rainfall"],
    "mumbai": ["mumbai", "brihanmumbai-municipal-corporation", "rainfall", "air-quality", "microwatersheds", "parks"],
}
MACHINE_FORMATS = {
    "csv", "tsv", "json", "geojson", "kml", "kmz", "gpkg", "shp", "zip",
    "parquet", "xlsx", "xls", "xml", "geojsonl",
}
MAX_RESOURCE_BYTES = 250 * 1024 * 1024
TIMEOUT = (15, 90)
USER_AGENT = "CarbonWise-OpenDataCollector/1.0 (research; provenance-preserving)"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(value: str) -> str:
    value = unquote(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value).strip("-")
    return value[:100] or "unnamed-resource"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def api_get(session: requests.Session, action: str, params: dict) -> dict:
    response = session.get(f"{API_BASE}/{action}", params=params, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(f"OpenCity API returned unsuccessful response for {action}")
    return payload["result"]


def discover(session: requests.Session, city: str, per_query: int = 100) -> list[dict]:
    """Search multiple topic terms and deduplicate packages by stable package id."""
    found: dict[str, dict] = {}
    for term in CITIES[city]:
        try:
            result = api_get(session, "package_search", {"q": term, "rows": per_query})
            for package in result.get("results", []):
                package_id = package.get("id") or package.get("name")
                if package_id:
                    found[package_id] = package
        except Exception as exc:
            print(f"[WARN] Search term {term!r} failed: {exc}")
    # Keep datasets whose metadata actually associates them with this city.
    city_terms = ("chennai", "greater chennai") if city == "chennai" else ("mumbai", "brihanmumbai", "mcgm", "bmc")
    filtered = []
    for package in found.values():
        metadata = " ".join(str(package.get(k, "")) for k in ("title", "name", "notes", "organization", "groups")).lower()
        groups = " ".join(str(g.get("name", "")) + " " + str(g.get("title", "")) for g in package.get("groups", [])).lower()
        org = package.get("organization") or {}
        metadata += " " + str(org.get("name", "")) + " " + str(org.get("title", "")) + " " + groups
        if any(term in metadata for term in city_terms):
            filtered.append(package)
    return sorted(filtered, key=lambda item: str(item.get("title", item.get("name", ""))).lower())


def resource_extension(resource: dict) -> str:
    fmt = str(resource.get("format") or "").lower().lstrip(".")
    if fmt in MACHINE_FORMATS:
        return fmt
    url = str(resource.get("url") or "")
    path = urlparse(url).path
    suffix = Path(path).suffix.lower().lstrip(".")
    return suffix if suffix in MACHINE_FORMATS else ""


def append_manifest(record: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def download_resource(session: requests.Session, city: str, package: dict, resource: dict) -> dict:
    url = str(resource.get("url") or "")
    ext = resource_extension(resource)
    title = str(resource.get("name") or resource.get("description") or resource.get("id") or "resource")
    record = {
        "city": city.title(),
        "dataset_title": package.get("title") or package.get("name"),
        "dataset_id": package.get("id") or package.get("name"),
        "dataset_page": package.get("url") or f"https://data.opencity.in/dataset/{package.get('name', '')}",
        "publisher": (package.get("organization") or {}).get("title") or (package.get("organization") or {}).get("name"),
        "license_id": package.get("license_id"),
        "license_title": package.get("license_title"),
        "resource_title": title,
        "resource_id": resource.get("id"),
        "resource_url": url,
        "format_as_published": resource.get("format"),
        "discovered_at_utc": now(),
        "downloaded_at_utc": None,
        "download_status": "skipped",
        "local_path": None,
        "bytes": None,
        "sha256": None,
        "error": None,
    }
    if not url or not ext:
        record["error"] = "No direct URL or unsupported/non-machine-readable format; manual review required."
        append_manifest(record)
        return record

    directory = RAW_ROOT / city / slug(str(package.get("name") or package.get("id") or "dataset"))
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{slug(title)}-{slug(str(resource.get('id') or 'resource'))}.{ext}"
    target = directory / filename
    if target.exists():
        record.update({
            "download_status": "already_present",
            "local_path": str(target.relative_to(ROOT)),
            "bytes": target.stat().st_size,
            "sha256": sha256_file(target),
        })
        append_manifest(record)
        return record

    try:
        with session.get(url, stream=True, timeout=TIMEOUT, allow_redirects=True) as response:
            response.raise_for_status()
            declared = int(response.headers.get("content-length") or 0)
            if declared > MAX_RESOURCE_BYTES:
                raise ValueError(f"Resource exceeds {MAX_RESOURCE_BYTES} byte safety limit")
            temp = target.with_suffix(target.suffix + ".part")
            total = 0
            with temp.open("wb") as stream:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_RESOURCE_BYTES:
                        raise ValueError(f"Resource exceeded {MAX_RESOURCE_BYTES} byte safety limit")
                    stream.write(chunk)
            if total == 0:
                temp.unlink(missing_ok=True)
                raise ValueError("Downloaded resource is empty")
            temp.replace(target)
        record.update({
            "downloaded_at_utc": now(),
            "download_status": "downloaded",
            "local_path": str(target.relative_to(ROOT)),
            "bytes": target.stat().st_size,
            "sha256": sha256_file(target),
        })
    except Exception as exc:
        try:
            target.with_suffix(target.suffix + ".part").unlink(missing_ok=True)
        except OSError:
            pass
        record["download_status"] = "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
    append_manifest(record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", choices=["Chennai", "Mumbai", "all"], default="all")
    parser.add_argument("--limit", type=int, default=100, help="Maximum datasets per city")
    parser.add_argument("--per-query", type=int, default=100, help="OpenCity results per search term")
    parser.add_argument("--delay", type=float, default=0.25, help="Pause between resource downloads")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, */*"})
    cities = list(CITIES) if args.city == "all" else [args.city.lower()]
    totals = {"datasets_discovered": 0, "resources_seen": 0, "downloaded": 0, "failed": 0, "skipped": 0}
    for city in cities:
        packages = discover(session, city, per_query=max(1, args.per_query))[:max(1, args.limit)]
        print(f"\n{city.title()}: discovered {len(packages)} candidate datasets")
        totals["datasets_discovered"] += len(packages)
        for package in packages:
            resources = package.get("resources") or []
            print(f"  - {package.get('title') or package.get('name')} ({len(resources)} resources)")
            for resource in resources:
                totals["resources_seen"] += 1
                record = download_resource(session, city, package, resource)
                status = record["download_status"]
                if status in ("downloaded", "already_present"):
                    totals["downloaded"] += 1
                elif status == "failed":
                    totals["failed"] += 1
                else:
                    totals["skipped"] += 1
                print(f"      {status}: {record.get('resource_title')}")
                time.sleep(max(0, args.delay))
    print("\nSummary:")
    print(json.dumps(totals, indent=2))
    print(f"Manifest: {MANIFEST_PATH.relative_to(ROOT)}")
    print("IMPORTANT: Downloaded files remain raw. Inspect licenses, date coverage, geometry, and schema before analysis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
