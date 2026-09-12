import pytest
from backend.enquiry_mail import enquiry_email

@pytest.mark.parametrize("kind", ["acknowledgement", "management_follow_up"])
def test_drafts_are_minimal_and_have_no_delivery_identity(kind):
    message = enquiry_email(kind, "HV-ENQ-0042", "preview@example.com")
    assert message["From"] is None
    assert message["X-HV-Swim-Draft"] == "local-preview-only"
    assert "HV-ENQ-0042" in message.get_content()
    assert "preview@example.com" not in message.get_content()
    assert message.get_content_type() == "text/plain"

@pytest.mark.parametrize("reference", ["HV-ENQ-1", "HV-ENQ-0042\nBcc: someone@example.com", "<script>"])
def test_reference_cannot_inject_headers_or_markup(reference):
    with pytest.raises(ValueError):
        enquiry_email("acknowledgement", reference, "preview@example.com")

def test_unknown_template_and_invalid_recipient_fail():
    with pytest.raises(ValueError):
        enquiry_email("marketing", "HV-ENQ-0042", "preview@example.com")
    with pytest.raises(ValueError):
        enquiry_email("acknowledgement", "HV-ENQ-0042", "preview@example.com\nBcc: other@example.com")
