# Delivery validation — 9 October 2026

Local preview: http://127.0.0.1:8765

Active dataset: `3c1136d71e61-17abfef89066-schema1-2540c788-rules-a93096a2`.

## Data and backend

**37 automated tests passed**, using the installed bundled Python, with no skipped independent comparison.

- Independently reconciled every populated cell in all six sheets against `openpyxl`: 14,754 cells, original references and values identical. Original XLSX and CSV hashes match supplied evidence.
- 51 Matrix scopes × 2 segments × 8 columns; Gap has the same coverage. QShield has 19 scopes × 2 segments × 6 columns (shared gates + five modules).
- All 999 source records and source IDs resolve; 321 questions retain resolved/open distinctions. All 64 CSV product/category entries retain compliance, certification status, dates and remarks separately. The CSV's Windows-1252 encoding is decoded without replacement characters.
- Normalized requirement assertions retain tags, confidence, IDs and references independently of gap assertions and certification status collections. Source-reported Certified = 3, In progress = 6, Planned = 7; these labels are not verified certificates.
- Tested QRNG bundles, exact-text regional deduplication with contributing references, India export scope, Dubai federal rules, QShield shared/module/cloud/QRNG combinations, Vault referenced buyer expectations, uncertain radio/sector/classified conditions, missing destinations/module coverage and not-applicable segments.
- Roadmap conflicts and future-dated reporting remain visible. Classified/radio scenarios cannot inherit a GREEN or dated approval assumption when the additional approval is unconfirmed.
- Tested partner projection for all 900 searchable country/product/segment combinations, with all QShield modules selected. Raw CSV, gap/status/roadmap/questions and unapproved mixed text are withheld. Direct evidence, source, download, JSON and HTML print routes enforce the same audience boundary.
- Tested unauthenticated access, spoofed role headers/query values, invalidated sessions, host/Origin restrictions, CSRF, admin-only mutations, approved-statement projection, approval revocation and expiry after version change. Admin mutation tests used temporary files; no actual app approval or invitation was created.
- Staged dataset review identifies exact changed cell references. Changed tags or confidence are not silently collapsed as equivalent clauses.

## Browser and print

**14 browser checks passed** in isolated headless Chromium, against the compact interface and running server.

- Desktop 1280 × 720 fits two complete requirements without scrolling. Mobile 390 × 844 shows the start of requirement text on the first screen, with no horizontal document overflow. Actual screenshots reviewed.
- Country and product menus show all options when clicked, even with an existing selection. Search, option selection, Arrow keys, Enter and Escape work. Deployment and applicability are expandable; active context is summarised beside the apply button.
- Replaced the oversized hero, sidebar, tiles and controls with compact navigation, 13px body text and 32px form controls. Repeated “workbook” wording is absent from the default guide; original source text, references, assumptions and provenance remain available.
- Requirements follow Mandatory → Buyer-expected → Recommended → Qualifications, preserving source order within each category. Search keeps this order. Result rows omit repeated country/product metadata and unassigned-owner placeholders; explicitly stated responsibilities and original references remain. Print briefs omit the same placeholder.
- Technical references (including Gap coordinates and internal CSV rows), repeated missing-date metadata and inline citation shorthand are hidden from normal requirements, actions, status and source cards. Source details still opens exact authorised cell/CSV/source evidence. Readable print briefs keep technical provenance in closed source disclosures.
- Identical conflict messages appear once and retain both certification records plus their gap reference. Actions omit repetitive prefixes; unspecified owners are blank in returned data. Customer type uses the same combobox rendering as Country/Product and retains the backend segment values. The main footer has no dataset hash.
- Filters, text search, exact-cell evidence, QShield module and SaaS/hardware controls, missing-country results and role changes update correctly.
- Partner role removes previously displayed internal status. Direct server results contain no internal certification/gap/conflict fields.
- Partner print route generated an A4 PDF without internal milestone dates; sources, assumptions and action sections survive text extraction. The comprehensive Germany/QHSM partner export is 22 pages because it includes full clauses and source claims.
- Administrator extraction totals, invitation-draft form and approval-review form render. Browser checks did not submit real drafts/approvals.
- No browser runtime errors and no third-party network requests.
- Desktop also inspected in the user's local Chrome. Automated browser testing uses its own isolated process, not the user's profile. The Codex preview panel was requested; the host queued opening it.

Generated screenshots, PDF and machine-readable browser report live in `tests/artifacts/`, excluded from Git. Backend tests can be rerun using the commands in the application README.

## Limits before production

This is an explicitly local role demonstration, not an invitation-only production service. Roles are intentionally selectable; the local server cannot prove employee/partner identity. Production needs an identity provider, invitation delivery, authenticated roles and organisation membership, persisted session/revocation controls, proper application server/storage, an audit trail, private hosting and operational safeguards.

Applicability evaluation is deliberately conservative: explicit narrow sector predicates are evaluated; broader conditions remain visible for review. Ownership is displayed only when an actor is named, and unassigned responsibility requires confirmation. Partner projection withholds mixed/internal text conservatively; production widening of access requires reviewed assertion-level audience classifications and approved wording.

The workbook was not independently legally reverified. Original certificates, product-version scopes, primary authorities, current applicability and conflicting milestone dates need review before a customer commitment. The GBrain CLI reported a live MCP database lock while its MCP tools were unavailable in this session; no competing database process was started. Supplied originals and indexed notes were used directly.

No public deployment, invitations sent, external publication, background updating or new backup was configured. Runtime invitations and approvals remain empty.
