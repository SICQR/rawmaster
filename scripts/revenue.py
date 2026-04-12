#!/usr/bin/env python3
"""
RAWMASTER - Revenue Report
Usage: python scripts/revenue.py [--access-token YOUR_TOKEN]
       or set GUMROAD_ACCESS_TOKEN env var
"""

import argparse, os, sys, time
from datetime import datetime, timedelta, timezone
from typing import Optional
import requests

PRODUCTS = {
    "rawmaster-cli":    "RAWMASTER CLI (19 GBP)",
    "rawmaster":        "RAWMASTER Desktop (29 GBP)",
    "rawmaster-bundle": "RAWMASTER Toolkit Bundle (39 GBP)",
}
GUMROAD_API = "https://api.gumroad.com/v2"


def _get(endpoint, token, params=None):
    resp = requests.get(
        f"{GUMROAD_API}/{endpoint}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_sales(token, product_id, after=None):
    sales, page = [], 1
    while True:
        params = {"product_id": product_id, "page": page}
        if after:
            params["after"] = after
        data = _get("sales", token, params)
        batch = data.get("sales", [])
        if not batch:
            break
        sales.extend(batch)
        if not data.get("next_page_url"):
            break
        page += 1
    return sales


def fetch_products(token):
    return _get("products", token).get("products", [])


def print_report(token):
    now = datetime.now(tz=timezone.utc)
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    print()
    print("RAWMASTER - Revenue Report")
    print(f"   Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print("-" * 52)

    all_products = fetch_products(token)
    slug_to_id = {
        p.get("custom_permalink") or p["url"].split("/l/")[-1]: p["id"]
        for p in all_products
    }

    total_revenue = total_sales = total_7d = 0
    total_revenue_7d = 0.0
    rows = []

    for slug, label in PRODUCTS.items():
        product_id = slug_to_id.get(slug)
        if not product_id:
            rows.append((label, "-", "-", "-", "NOT FOUND"))
            continue
        all_s  = fetch_sales(token, product_id)
        recent = fetch_sales(token, product_id, after=week_ago)
        revenue    = sum(float(s.get("price", 0)) / 100 for s in all_s)
        revenue_7d = sum(float(s.get("price", 0)) / 100 for s in recent)
        total_revenue    += revenue
        total_sales      += len(all_s)
        total_7d         += len(recent)
        total_revenue_7d += revenue_7d
        rows.append((label, f"{len(all_s):>4} sales", f"GBP{revenue:>8.2f}",
                     f"{len(recent):>3} / GBP{revenue_7d:.2f}", "OK"))

    print(f"\n{'Product':<30} {'All-time':>10} {'Revenue':>12} {'Last 7d':>18}")
    print("-" * 76)
    for label, sales, revenue, last7d, status in rows:
        print(f"{label:<30} {sales:>10} {revenue:>12} {last7d:>18}  {status}")
    print("-" * 76)
    print(f"{'TOTAL':<30} {total_sales:>4} sales  GBP{total_revenue:>8.2f}  "
          f"{total_7d:>3} / GBP{total_revenue_7d:.2f}")
    print()
    if total_sales == 0:
        print("No sales yet. Products may not be live.")
    else:
        avg = total_revenue / total_sales
        print(f"{total_sales} total sales | GBP{total_revenue:.2f} all-time | avg GBP{avg:.2f}/sale")
        print(f"Last 7 days: {total_7d} sales | GBP{total_revenue_7d:.2f}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAWMASTER revenue report")
    parser.add_argument("--access-token", "-t",
                        default=os.environ.get("GUMROAD_ACCESS_TOKEN", ""))
    parser.add_argument("--watch", "-w", action="store_true")
    args = parser.parse_args()

    if not args.access_token:
        print("No Gumroad access token.\n"
              "Set GUMROAD_ACCESS_TOKEN or pass --access-token TOKEN\n"
              "Get it: gumroad.com -> Settings -> Advanced -> Access Tokens")
        sys.exit(1)

    if args.watch:
        while True:
            os.system("clear")
            print_report(args.access_token)
            print("(refreshing every 60s - Ctrl+C to stop)")
            time.sleep(60)
    else:
        print_report(args.access_token)