"""Reviewable enquiry email drafts. This module has no transport or network access."""
import re
from email.message import EmailMessage
from email.headerregistry import Address


def enquiry_email(kind: str, reference: str, recipient: str) -> EmailMessage:
    if not re.fullmatch(r"HV-(?:ENQ|MERCH)-[0-9]{4,}", reference):
        raise ValueError("Invalid enquiry reference")
    address = Address(addr_spec=recipient)
    if not address.username or not address.domain or any(c in recipient for c in "\r\n"):
        raise ValueError("Invalid recipient")
    if kind == "acknowledgement":
        subject = f"Your HV Swim enquiry · {reference}"
        body = f"""Thanks for getting in touch with HV Swim Bendigo.

We have received your enquiry, {reference}. Our team will review it and contact you
using your preferred reply method. A class placement and any fees are confirmed
personally before enrolment.

If you need to add anything, quote your reference when contacting the team on
0413 462 112 or bendigo@hvswimschool.com.

HV Swim Bendigo
"""
    elif kind == "management_follow_up":
        subject = f"HV Swim enquiry follow-up · {reference}"
        body = f"""An enquiry needs a management follow-up: {reference}.

Open your usual HV Swim management workspace and search for this reference.
Review the current owner, next action and contact preference before responding.
This reminder does not confirm a booking or send a message to the family.

HV Swim Bendigo
"""
    else:
        raise ValueError("Unknown enquiry email kind")
    message = EmailMessage()
    message["To"] = str(address)
    message["Subject"] = subject
    # No From or delivery headers: the owner must configure a verified sender first.
    message["X-HV-Swim-Draft"] = "local-preview-only"
    message.set_content(body)
    return message
