"""Generate fictional email previews without credentials, records or network calls."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.enquiry_mail import enquiry_email

if __name__ == "__main__":
    destination = ROOT / "data" / "local-preview" / "email-drafts"
    destination.mkdir(parents=True, exist_ok=True)
    for kind in ("acknowledgement", "management_follow_up"):
        path = destination / f"{kind}.eml"
        path.write_bytes(enquiry_email(kind, "HV-ENQ-0001", "preview@example.com").as_bytes())
        print(f"Local draft: {path}")
    print("Nothing sent. These are fictional examples for content review.")
