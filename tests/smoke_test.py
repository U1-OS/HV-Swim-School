#!/usr/bin/env python3
"""Read-only smoke checks for a running HV Swim server."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar


BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8765"


def request(opener, path, method="GET", body=None, csrf=None):
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if csrf:
        headers["X-CSRF-Token"] = csrf
    response = opener.open(
        urllib.request.Request(BASE + path, data=data, headers=headers, method=method),
        timeout=30,
    )
    return response.status, json.loads(response.read().decode("utf-8"))


def expect(label, condition):
    if not condition:
        raise AssertionError(label)
    print(f"PASS  {label}")


def main():
    public = urllib.request.build_opener()
    status, health = request(public, "/api/health")
    expect("health endpoint", status == 200 and health.get("version") == "5.1.0")
    home_page = public.open(BASE + "/index.html", timeout=30).read().decode("utf-8")
    expect("live homepage day view", "Today at HV Swim" in home_page and "today-grid" in home_page and "staff-verified" in home_page)
    about_page = public.open(BASE + "/about.html", timeout=30).read().decode("utf-8")
    expect("Laura-led teaching approach", "Led by Laura" in about_page and "Confidence grows when swimmers feel" in about_page and "How a lesson should feel" in about_page)
    programs_page = public.open(BASE + "/programs.html", timeout=30).read().decode("utf-8")
    expect("premium programs and pricing page", "Every swimmer has" in programs_page and "Guided lesson matcher" in programs_page and "program-availability" in programs_page)
    shop_page = public.open(BASE + "/shop.html", timeout=30).read().decode("utf-8")
    expect("premium commerce storefront", "Preview cart" in shop_page and "The right supplier for each product" in shop_page and "cart-drawer" in shop_page)
    expect("guided merchandise kit builder", "First Splash Kit" in shop_page and "Lesson Day Kit" in shop_page and "data-kit-add" in shop_page and "Size it, care for it" in shop_page)
    enquire_page = public.open(BASE + "/enquire.html", timeout=30).read().decode("utf-8")
    expect("guided enrolment concierge", "Four clear steps" in enquire_page and "wizard-class-grid" in enquire_page and "enrolment-success" in enquire_page)
    mobile_shell = public.open(BASE + "/mobile-shell.html", timeout=30).read().decode("utf-8")
    expect("native mobile launch shell", "Open connected app" in mobile_shell and "V5.1" in mobile_shell)
    manifest = json.loads(public.open(BASE + "/manifest.webmanifest", timeout=30).read().decode("utf-8"))
    expect("installable app manifest", manifest.get("display") == "standalone" and len(manifest.get("icons", [])) >= 3)
    for path, key in (("/api/public/locations", "locations"), ("/api/classes", "classes")):
        status, payload = request(public, path)
        expect(path, status == 200 and isinstance(payload.get(key), list))
    status, site = request(public, "/api/public/site-settings")
    expect("public website settings", status == 200 and site.get("settings", {}).get("hero_heading"))

    roles = {
        "customer": ("parent@hvswim.demo", "FamilyDemo!26", "/api/customer/swimmers", "swimmers"),
        "staff": ("staff@hvswim.demo", "StaffDemo!26", "/api/staff/roster", "roster"),
        "admin": ("admin@hvswim.demo", "AdminDemo!26", "/api/admin/metrics", "metrics"),
    }
    for role, (email, password, protected_path, result_key) in roles.items():
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        status, _ = request(opener, "/api/auth/login", "POST", {"email": email, "password": password})
        expect(f"{role} login", status == 200)
        status, auth = request(opener, "/api/auth/me")
        expect(f"{role} session and role", status == 200 and auth["user"]["role"] == role)
        status, payload = request(opener, protected_path)
        expect(f"{role} protected data", status == 200 and result_key in payload)
        if role == "admin":
            status, dashboard = request(opener, "/api/admin/dashboard")
            expect("admin command-centre metrics", status == 200 and dashboard.get("source", {}).get("mode") == "Local SQLite preview")
            status, enrolments = request(opener, "/api/admin/enrolments")
            expect("admin enrolment desk", status == 200 and isinstance(enrolments.get("waitlist"), list) and len(enrolments.get("classes", [])) >= 5)
            status, locations = request(opener, "/api/admin/locations")
            expect("admin location manager", status == 200 and len(locations.get("locations", [])) >= 2)
            status, merch = request(opener, "/api/admin/merch-production")
            expect("admin merchandise workspace", status == 200 and len(merch.get("catalogue", [])) >= 9 and merch.get("launch_readiness", {}).get("total_products") >= 9)
            status, website = request(opener, "/api/admin/site-settings")
            expect("admin website editor", status == 200 and website.get("settings", {}).get("primary_cta"))
            status, inbox = request(opener, "/api/admin/enquiries")
            expect("admin enquiry inbox", status == 200 and isinstance(inbox.get("enquiries"), list))

        try:
            request(opener, "/api/auth/logout", "POST")
        except urllib.error.HTTPError as error:
            expect(f"{role} CSRF rejection", error.code == 403)
        else:
            raise AssertionError(f"{role} CSRF rejection")

    print("\nHV Swim read-only smoke suite passed.")


if __name__ == "__main__":
    main()
