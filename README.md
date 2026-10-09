# QNu Market Access Guide

Private repository for the country/product market-access guide, with employee, partner and administrator demo views.

## Run locally

Python 3.9 or newer is required. The application uses the Python standard library.

```sh
cd apps/qnu-market-access
python3 import_data.py --activate
python3 server.py
```

Open [the guide](http://127.0.0.1:8765).

## Repository contents

- `apps/qnu-market-access/`: application, interface assets, tests and design/validation documentation.
- `originals/Qnu/Certification References/`: the supplied country compliance XLSX and Internal Only certification CSV, preserved unchanged.
- Imported datasets, local sessions/approvals/invitation drafts and generated test artifacts stay out of Git.

The role selector is a local permissions demonstration. Production authentication and invitations are described in the [application README](apps/qnu-market-access/README.md).

Requirements remain grounded in the supplied research snapshot. Source details retain evidence references and uncertainty; ingestion does not independently verify regulations or certifications.

See the [application guide](apps/qnu-market-access/README.md) for data review, validation, exports and production requirements.
