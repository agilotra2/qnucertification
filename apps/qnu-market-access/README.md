# QNu Market Access Guide

Working local prototype, using the supplied country workbook and Internal Only certification CSV. No public deployment, external services, email delivery or production authentication. Original source files are read unchanged.

## Start

Python 3.9 or newer is enough; the application and importer use only the standard library.

```sh
cd apps/qnu-market-access
python3 import_data.py --activate
python3 server.py
```

Open [the local guide](http://127.0.0.1:8765). Stop the server with Ctrl-C. Use `python3 server.py --port 8766` if the default port is occupied. The server deliberately binds only to `127.0.0.1` and rejects other hosts.

Run the commands above from the repository root. The supplied XLSX and Internal Only CSV are preserved under `originals/Qnu/Certification References/` in the private repository; importing creates the local dataset. For other input files, use the explicit `--workbook` and `--status-csv` options below.

The clearly labelled demo role switch offers employee, partner and administrator views. **It is not authentication or invitation-based access.** Anyone with access to this local demo can select a role. Do not run it behind a public proxy or tunnel. Runtime datasets, local approval records, invitation drafts and browser test artefacts are Git-ignored inside this isolated application directory.

## What works

- Search country/region and product; select Commercial or Government/Defence/CI, relevant deployment and hardware conditions, regulated sector, radio presence and India export scope.
- QShield module selection combines shared gates with module evidence. SaaS adds relevant Digital QKD cloud clauses. Entropy with hardware adds QRNG; Vault includes explicitly referenced QKMS buyer expectations. No certification coverage transfers between these products.
- Results retain M/E/R categories, source-reported confidence, conditions, responsible actors where named, source IDs, checked dates, verifier statuses and exact cells. Untagged/uncertain clauses remain visible.
- Country and region/export scopes combine with exact-text deduplication; every supporting reference remains. Differing tags, confidence or qualifications stay separate. EU member-state rules add EU-wide evidence; Dubai adds UAE evidence. Norway is not silently treated as an EU member.
- Internal certification/compliance/date/remarks fields and source-reported gap verdicts remain distinct. Planned dates, future-dated “In progress” entries and conflicting milestones are shown together. A GREEN source verdict means conditions remain, and classified or radio scenarios do not automatically inherit it.
- Missing destinations and QShield module rows stay unknown, even when export or regional evidence exists. Not applicable segments are distinct from missing coverage.
- Print / save PDF opens a server-generated country–product brief under the current role. JSON exports use the same projection. Briefs include full qualifications and supporting source records; filters do not silently remove evidence from exports.
- Employees can inspect exact workbook/CSV evidence and download originals. Partner API responses, evidence and exports exclude raw CSV, Gap, Open questions and mixed internal text. Only safe requirement/source projections are shared by default. Some source cells are deliberately unavailable because they contain mixed unapproved information.
- Administrators can create **local unsent invitation drafts**, review a certification assertion, explicitly publish a narrow statement to the local partner demo, and revoke it. No approval or invitation was created in the delivered app. Approval notes remain internal; approvals are bound to a dataset version and expire when it changes.

## Dataset and source controls

The snapshot contains all six sheets and 14,754 populated cells, 999 sources, 321 question records (including resolved records), 64 product/category certification records and the original CSV's populated cells. Country labels inherit only through actual merges. All source IDs resolve. Matrix covers 51 country/regional/export entries; the searchable selector has 50 entries plus the separately selected India export scope. QShield has 19 covered scopes, each with two customer segments, shared gates and five modules.

`private/versions/<version>.json` retains raw cells, fills, merges and dimensions alongside structured Matrix requirements, QShield records, country notes, questions, source records, normalized requirement assertions, separate certification assertion collections by status, Gap assertions and versioned product assumptions. Version identity includes workbook/CSV hashes and importer/retrieval-rule code hashes. Dataset ingestion does not validate legal claims, possession of certificates, or product-version scope.

Workbook research is dated **6 October 2026** for Matrix and **7 October 2026** for QShield; assumptions include **8 October 2026**. Source records retain their individual checked dates and verifier statuses. The Internal Only CSV's effective date is not stated. The application does not continuously update or independently reverify the workbook. Current legal/customer advice needs primary-authority verification.

## Import and review a revision

Stage a new workbook first; this command does not change the active dataset:

```sh
python3 import_data.py --workbook '/absolute/path/revised-workbook.xlsx' --status-csv '/absolute/path/status-matrix.csv'
python3 manage_data.py list
python3 manage_data.py review '<candidate-version-from-list>'
```

Inspect the exact changed/added/removed cell references, fills/merges, source dates and CSV-change flag in the printed report and `private/reviews/`. Read the candidate snapshot's changed cell values and original workbook. Run tests, review applicability/wording and resolve source conflicts; indexing alone is not approval.

Then explicitly activate the reviewed local snapshot:

```sh
python3 manage_data.py activate '<candidate-version-from-list>' --reviewer 'Reviewer name' --note 'Reviewed changed cells, dates, applicability and source qualifications.'
```

Restart the server. Old partner approvals never transfer. Schema changes, formulas, unresolved source IDs and mismatched immutable snapshots fail ingestion instead of being silently interpreted. Initial `--activate` is a bootstrap/explicit activation option; use the staged review path for ongoing revisions. Original downloads also verify that the file still matches the active snapshot's hash.

## Validation

```sh
python3 -m unittest discover -s tests -v
```

The independent full-cell comparison needs `openpyxl`. The installed Codex bundled Python includes it:

```sh
/Users/ash/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests -v
```

While the server runs, use the installed bundled Playwright for isolated browser checks:

```sh
/Users/ash/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tests/browser.mjs
```

For another machine, set `QNU_NODE_PACKAGES` to a directory containing an installed `playwright` package and Chromium. Browser reports, screenshots and sample PDFs are saved in `tests/artifacts/`. Backend admin mutations run only against temporary storage. Browser tests inspect admin forms without submitting real approvals or invitations.

See [validation.md](docs/validation.md) for the delivery checks and limitations.

## Before production use

Choose an identity/invitation provider and authenticated server stack; replace the demo-role endpoints with verified employee/partner/admin identities and organisation membership. Add expiry, revocation, MFA policy as applicable, audit history and robust storage/backup for invitations and approval decisions. Validate original certificates and exact product/version scope, independently verify applicable primary authorities, and approve partner wording/source records explicitly. Replace conservative text-based condition/partner projections with reviewed structured rules and explicit audience classifications for every source assertion before widening access. Provision a private deployment and operational controls only after explicit authorisation. No credentials or provider decision were needed for this local release.
