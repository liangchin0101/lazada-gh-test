"""
Lazada GitHub test: can a GitHub Actions runner read the Lazada store?

Opens a real Chromium browser (inside a virtual screen), visits the
Pokemon Store Online Singapore shop page, then fetches the product list
a few times. Each round reports OK / BLOCKED / ERROR.
The result appears in the run's Summary page.

Read-only. No login, no captcha solving, no buying.
"""
import json
import os
import time
import urllib.request

from playwright.sync_api import sync_playwright

STORE = "pokemon-store-online-singapore"
SHOP_URL = f"https://www.lazada.sg/shop/{STORE}/"
LIST_URL = (f"https://www.lazada.sg/{STORE}/?ajax=true&from=wangpu&langFlag=en"
            "&page=1&pageTypeId=2&q=trading%20card%20game")
BLOCK_SIGNS = ("punish", "x5secdata", "captcha", "rgv587", "baxia",
               "fail_sys_user_validate")

ROUNDS = int(os.getenv("ROUNDS", "3"))
GAP = int(os.getenv("GAP", "90"))  # seconds between rounds


def public_ip():
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=10) as r:
            return r.read().decode()
    except Exception:
        return "unknown"


def check(page):
    try:
        resp = page.goto(LIST_URL, wait_until="domcontentloaded", timeout=45000)
        body = resp.text() if resp else ""
        status = resp.status if resp else "none"
    except Exception as e:
        return "ERROR", f"page load failed: {str(e)[:150]}"

    low = body.lower()
    try:
        data = json.loads(body)
    except ValueError:
        data = None

    items = []
    if isinstance(data, dict):
        items = (data.get("mods") or {}).get("listItems") or []

    if items:
        in_stock = sum(1 for i in items if i.get("inStock"))
        return "OK", f"{len(items)} products listed, {in_stock} in stock"
    if any(sign in low for sign in BLOCK_SIGNS):
        return "BLOCKED", f"anti-bot / captcha page (HTTP {status})"
    return "ERROR", f"unexpected reply (HTTP {status}, {len(body)} chars): {body[:120]!r}"


def main():
    ip = public_ip()
    print(f"Runner public IP: {ip}")
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            locale="en-SG",
            timezone_id="Asia/Singapore",
            viewport={"width": 1366, "height": 800},
        )
        page = context.new_page()

        # Visit the shop like a normal visitor first
        try:
            page.goto(SHOP_URL, wait_until="domcontentloaded", timeout=45000)
            time.sleep(8)
            print("Shop page opened")
        except Exception as e:
            print(f"Shop page failed: {str(e)[:150]}")

        for n in range(1, ROUNDS + 1):
            status, detail = check(page)
            stamp = time.strftime("%H:%M:%S", time.gmtime(time.time() + 8 * 3600))
            line = f"Round {n} ({stamp} SGT): {status} - {detail}"
            print(line, flush=True)
            results.append((n, stamp, status, detail))
            if n < ROUNDS:
                time.sleep(GAP)

        browser.close()

    ok = sum(1 for r in results if r[2] == "OK")
    if ok == len(results):
        verdict = "✅ PASSED - GitHub can read the Lazada store (run it a few more times to be sure)"
    elif ok == 0:
        verdict = "❌ BLOCKED - GitHub's servers can't read Lazada; use the home mini PC"
    else:
        verdict = "⚠️ MIXED - some rounds blocked; not reliable enough"

    print("\n===== GITHUB LAZADA TEST SUMMARY =====")
    print(f"IP: {ip}")
    for n, stamp, status, detail in results:
        print(f"Round {n} {stamp}: {status} - {detail}")
    print(verdict)

    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write("## Lazada GitHub test\n\n")
            f.write(f"**{verdict}**\n\n")
            f.write(f"Runner IP: `{ip}`\n\n")
            f.write("| Round | Time (SGT) | Result | Detail |\n|---|---|---|---|\n")
            for n, stamp, status, detail in results:
                f.write(f"| {n} | {stamp} | {status} | {detail.replace('|', '/')} |\n")


if __name__ == "__main__":
    main()
