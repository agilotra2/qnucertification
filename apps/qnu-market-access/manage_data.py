"""Review staged snapshots and explicitly activate a reviewed local dataset."""
import argparse
import datetime
import json
from pathlib import Path
from engine import APP, Guide

def review(active, candidate):
    changes = {}
    for sn, sheet in candidate['sheets'].items():
        before = active['sheets'][sn]['cells']
        after = sheet['cells']
        changes[sn] = {'added': [sn + '!' + c for c in after if c not in before], 'removed': [sn + '!' + c for c in before if c not in after], 'changed': [sn + '!' + c for c in after if c in before and before[c] != after[c]], 'fill_changes': [sn + '!' + c for c in sheet['fills'] if active['sheets'][sn]['fills'].get(c) != sheet['fills'][c]], 'merges_changed': active['sheets'][sn]['merges'] != sheet['merges']}
    return {'active': active['version'], 'candidate': candidate['version'], 'research_dates': candidate['research_dates'], 'coverage': candidate['coverage'], 'changes': changes, 'csv_changed': active['csv_sha256'] != candidate['csv_sha256'], 'note': 'Inspect changed evidence and applicability before activation. Source assertions are not verified by import; all partner approvals must be re-reviewed for the new version.'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['list','review','activate'])
    parser.add_argument('version', nargs='?')
    parser.add_argument('--reviewer')
    parser.add_argument('--note')
    args = parser.parse_args()
    versions = APP / 'private/versions'
    if args.action == 'list':
        print(json.dumps({'active': Guide().data['version'], 'available': [p.stem for p in versions.glob('*.json')]}, indent=2))
        return
    # Select by an exact version already present; no caller-controlled path.
    path = next((p for p in versions.glob('*.json') if p.stem == args.version), None)
    if path is None:
        parser.error('Choose an existing staged version from list')
    candidate = json.loads(path.read_text())
    active = Guide().data
    review_dir = APP / 'private/reviews'
    review_dir.mkdir(exist_ok=True)
    report = review_dir / (args.version + '.json')
    if args.action == 'review':
        summary = review(active, candidate)
        report.write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps(summary, indent=2))
    else:
        if not report.exists() or json.loads(report.read_text())['active'] != active['version']:
            parser.error('Run review against the current active snapshot first')
        if not args.reviewer or not args.note or len(args.note.strip()) < 15:
            parser.error('Activation requires --reviewer and --note (15+ characters)')
        audit = {'version': args.version, 'reviewer': args.reviewer, 'review_note': args.note, 'reviewed_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        (APP / 'private/active.json').write_text(json.dumps(audit, indent=2) + '\n')
        print('Activated reviewed local snapshot. Restart the server. Partner approvals do not transfer.')

if __name__ == '__main__':
    main()
