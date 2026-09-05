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
    expect("health endpoint", status == 200 and health.get("version") == "5.13.0")
    status, account_providers = request(public, "/api/auth/oauth/providers")
    expect(
        "family Google and Apple account boundary",
        status == 200
        and account_providers.get("signup_role") == "customer"
        and account_providers.get("team_accounts") == "invitation_only"
        and {item.get("id") for item in account_providers.get("providers", [])} == {"google", "apple"},
    )
    home_page = public.open(BASE + "/index.html", timeout=30).read().decode("utf-8")
    expect("live homepage day view", "Today at HV Swim" in home_page and "today-grid" in home_page and "staff reading" in home_page)
    about_page = public.open(BASE + "/about.html", timeout=30).read().decode("utf-8")
    expect("Laura-led teaching approach", "Led by Laura" in about_page and "Confidence grows when swimmers feel" in about_page and "How a lesson should feel" in about_page)
    programs_page = public.open(BASE + "/programs.html", timeout=30).read().decode("utf-8")
    expect("premium programs and pricing page", "Every swimmer has" in programs_page and "Guided lesson matcher" in programs_page and "program-availability" in programs_page)
    shop_page = public.open(BASE + "/shop.html", timeout=30).read().decode("utf-8")
    shop_script = public.open(BASE + "/assets/shop.js", timeout=30).read().decode("utf-8")
    expect("premium commerce storefront", "Shopping bag" in shop_page and "The right maker for every item" in shop_page and "shop-load-more" in shop_page and "cart-drawer" in shop_page)
    expect("embroidered towels and POD shop", "The towel edit" in shop_page and "POD family wear" in shop_page and "Printify → Shopify" in shop_page)
    expect("guided merchandise kit builder", "First Splash Kit" in shop_script and "Lesson Day Kit" in shop_script and "data-kit-add" in shop_script and "Size it, care for it" in shop_page)
    enquire_page = public.open(BASE + "/enquire.html", timeout=30).read().decode("utf-8")
    expect("guided lesson enquiry", "Four clear steps" in enquire_page and "wizard-class-grid" in enquire_page and "No instant booking" in enquire_page)
    platform_script = public.open(BASE + "/assets/platform.js", timeout=30).read().decode("utf-8")
    expect("family enrolment is enquiry-only", "No online enrolment" in platform_script and "Enquire about this class" in platform_script and "data-action=\"book-class\"" not in platform_script)
    for paused_path in ("/app.html", "/mobile-shell.html"):
        try:
            public.open(BASE + paused_path, timeout=30)
            paused_status = 200
        except urllib.error.HTTPError as exc:
            paused_status = exc.code
        expect(f"paused mobile route {paused_path}", paused_status == 404)
    manifest = json.loads(public.open(BASE + "/manifest.webmanifest", timeout=30).read().decode("utf-8"))
    expect("website identity manifest", len(manifest.get("icons", [])) >= 3)
    for path, key in (("/api/public/locations", "locations"), ("/api/classes", "classes")):
        status, payload = request(public, path)
        expect(path, status == 200 and isinstance(payload.get(key), list) and payload.get("term_calendar", {}).get("configured") is True)
    status, alerts = request(public, "/api/public/alerts")
    expect("urgent public alert feed", status == 200 and isinstance(alerts.get("alerts"), list) and alerts.get("delivery", {}).get("website_polling") == "live")
    status, site = request(public, "/api/public/site-settings")
    expect("public website settings", status == 200 and site.get("settings", {}).get("hero_heading"))
    status, badges = request(public, "/api/public/association-badges")
    expect("association marks fail closed", status == 200 and badges == {"badges": [], "published": False})
    status, public_products = request(public, "/api/products")
    expect(
        "public shop excludes staff merchandise",
        status == 200
        and public_products.get("products")
        and all(item.get("audience") != "staff" for item in public_products["products"]),
    )

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
        if role == "customer":
            expect(
                "family child safety profiles",
                bool(payload.get("swimmers"))
                and all(
                    field in payload["swimmers"][0]
                    for field in ("emergency_contact", "allergies", "medications", "medical_notes", "support_notes")
                ),
            )
            status, absences = request(opener, "/api/customer/absences")
            expect("family absence-credit workspace", status == 200 and absences.get("policy", {}).get("make_up_classes") is False and isinstance(absences.get("usage"), list))
            status, messages = request(opener, "/api/support-tickets")
            expect("family secure messages", status == 200 and isinstance(messages.get("tickets"), list))
            status, achievements = request(opener, "/api/customer/achievements")
            expect("family achievement certificates", status == 200 and achievements.get("certificate_rendering") == "html_print")
            status, billing = request(opener, "/api/customer/billing")
            expect("family Xero invoice ledger", status == 200 and billing.get("lesson_provider") == "Xero" and billing.get("merchandise_provider") == "Shopify" and billing.get("card_data_stored") is False)
        if role == "staff":
            status, staff_merch = request(opener, "/api/staff/merchandise")
            expect(
                "private staff merchandise",
                status == 200
                and staff_merch.get("audience") == "staff_only"
                and staff_merch.get("products")
                and all(item.get("audience") == "staff" for item in staff_merch["products"]),
            )
            status, register = request(opener, "/api/staff/lesson-register")
            expect("staff lesson register", status == 200 and register.get("policy", {}).get("photo_clearance") and isinstance(register.get("classes"), list))
            status, tickets = request(opener, "/api/staff/support-tickets")
            expect("staff support ticket queue", status == 200 and isinstance(tickets.get("tickets"), list))
            status, achievements = request(opener, "/api/staff/achievements")
            expect("staff achievement studio", status == 200 and len(achievements.get("templates", [])) == 8)
        if role == "admin":
            status, system_health = request(opener, "/api/admin/system-health")
            expect(
                "management backend health",
                status == 200
                and system_health.get("ok") is True
                and system_health.get("database", {}).get("integrity") == "ok"
                and system_health.get("security", {}).get("integration_token_encryption") == "current",
            )
            status, terms = request(opener, "/api/admin/term-operations")
            expect("management term operations", status == 200 and terms.get("policy", {}).get("payment_route") == "xero_invoice_workflow" and isinstance(terms.get("terms"), list))
            status, integrations = request(opener, "/api/admin/integrations")
            providers = {item.get("provider") for item in integrations.get("payment_routing", [])}
            expect("Xero and Shopify payment routing", status == 200 and providers == {"Xero", "Shopify"})
            status, billing = request(opener, "/api/admin/billing")
            expect("management invoice ledger", status == 200 and isinstance(billing.get("invoices"), list) and billing.get("xero", {}).get("sync_mode") == "draft_invoices_only")
            status, dashboard = request(opener, "/api/admin/dashboard")
            expect("admin command-centre metrics", status == 200 and dashboard.get("source", {}).get("mode") == "Local SQLite preview")
            status, enrolments = request(opener, "/api/admin/enrolments")
            expect("admin enrolment desk", status == 200 and isinstance(enrolments.get("waitlist"), list) and len(enrolments.get("classes", [])) >= 5)
            status, locations = request(opener, "/api/admin/locations")
            expect("admin location manager", status == 200 and len(locations.get("locations", [])) >= 2)
            status, merch = request(opener, "/api/admin/merch-production")
            expect("admin merchandise workspace", status == 200 and len(merch.get("catalogue", [])) >= 24 and merch.get("launch_readiness", {}).get("total_products") >= 24)
            status, tickets = request(opener, "/api/staff/support-tickets")
            expect("management support ticket queue", status == 200 and isinstance(tickets.get("tickets"), list))
            status, alerts = request(opener, "/api/admin/alerts")
            expect("management alert publisher", status == 200 and isinstance(alerts.get("alerts"), list))
            status, website = request(opener, "/api/admin/site-settings")
            expect("admin website editor", status == 200 and website.get("settings", {}).get("primary_cta") and website.get("feature_controls", {}).get("association_badges", {}).get("can_enable") is False)
            status, badge_register = request(opener, "/api/admin/association-badges")
            expect("association evidence register", status == 200 and len(badge_register.get("credentials", [])) == 3 and badge_register.get("feature_control", {}).get("ready_items") == 0)
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
