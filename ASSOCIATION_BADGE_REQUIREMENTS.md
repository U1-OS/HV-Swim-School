# Association badge activation — V5.10.0

The public site reserves polished space for HV Swim's aquatic-industry listings, but it
does not include copied, redrawn or generic organisation logos. That is intentional.
Membership and provider badges may be displayed only after HV Swim supplies the exact
current artwork issued to the business and the evidence below has been recorded.

## Required evidence

| Listing | File required | Evidence required before display | Safe public wording now |
|---|---|---|---|
| AUSTSWIM Swim School Network | Current digital member badge issued to HV Swim | Renewal/current-to date and the issuing email or account record | AUSTSWIM Swim School Network — view the public finder |
| SWIM Coaches & Teachers Australia / SWIM Schools Australia | Current member logo issued to HV Swim | Current membership record and expiry/renewal date | SWIM Coaches & Teachers Australia — view HV Swim's public school record |
| Autism Swim | Current Approved Provider artwork issued to HV Swim | Current membership term, expiry date and confirmation that the public record has been corrected | Autism Swim provider-directory record — renewal and listing details are being confirmed |

Never use a general corporate logo as a substitute for an issued membership/provider
badge. Never describe the AUSTSWIM Swim School Network as an accreditation or audit.
Do not add a Swimming Australia logo unless HV Swim documents a separate, current
affiliation with that organisation.

## File handoff

Ask the organisation or the HV Swim account owner for an original SVG, PDF or high-
resolution transparent PNG. Record the supplied filename, issuing source, authorised
wording, renewal/expiry date and reviewer in the launch register before publishing it.
Do not scrape artwork from a website, social post or search result.

## Management workflow now available

V5.10.0 implements the protected register under **Management → Staff compliance**. For
each organisation, management must enter the membership/certificate reference, valid-until
date, an internal evidence note and an explicit confirmation that the exact supplied mark
may currently be displayed. The register accepts PNG only (64–2400 pixels and no larger
than 1 MB), validates the PNG structure, stores a SHA-256 integrity hash and records the
reviewing management user and time in the audit log.

The uploaded files live in the private runtime data directory, not in Git. **Management →
Website content** remains the separate final release control. The API fails closed: unless
all three required records are current, authorised, verified and hash-matched, the public
endpoint returns no badges and both the homepage section and footer strip stay hidden. An
expiry, missing file or changed file automatically disables the complete public section.

For production, ensure the application data volume is encrypted, backed up and persistent,
or replace local badge storage with private object storage while preserving the same hash,
authorisation and public-release checks.

The current Autism Swim directory page still contains former-team and older venue
details. HV Swim should have that record corrected before its Approved Provider badge is
promoted on the production site.

## Official references

- AUSTSWIM Swim School Network: <https://austswim.com.au/swim-school-network>
- AUSTSWIM finder: <https://austswim.com.au/australian-swim-school-finder>
- SWIM Schools Australia membership: <https://swim.org.au/swim-schools/>
- Autism Swim Approved Provider terms: <https://learn.autism-swim.org/autism-swim-approved-provider-membership-terms/>
- HV Swim Autism Swim record: <https://autism-swim.org/providers/aquatic-centre-hidden-valley-swim-school-bendigo/>
