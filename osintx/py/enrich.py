#!/usr/bin/env python3
"""Offline enrichment: phone graph metadata. No network calls."""
import argparse, json, sys

try:
    import phonenumbers
    from phonenumbers import carrier, geocoder, timezone
except ImportError:
    phonenumbers = None


def phone(raw):
    if not phonenumbers:
        return {"error": "phonenumbers not installed"}
    try:
        n = phonenumbers.parse(raw, None)
    except Exception as e:
        return {"valid": False, "error": str(e)}
    if not phonenumbers.is_valid_number(n):
        return {"valid": False}
    return {
        "valid": True,
        "e164": phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164),
        "national": phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.NATIONAL),
        "region": phonenumbers.region_code_for_number(n),
        "carrier": carrier.name_for_number(n, "en"),
        "geo": geocoder.description_for_number(n, "en"),
        "timezones": list(timezone.time_zones_for_number(n)),
        "type": str(phonenumbers.number_type(n)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phone")
    ap.add_argument("--email")
    a = ap.parse_args()
    json.dump(phone(a.phone) if a.phone else {}, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
