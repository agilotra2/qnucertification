"""Read-only, repeatable XLSX/CSV ingestion. No workbook content is executed."""
import argparse
import csv
import hashlib
import io
import json
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parents[1]
DEFAULT_WORKBOOK = ROOT / 'originals/Qnu/Certification References/qnu-country-compliance-matrix-9Oct2026.xlsx'
DEFAULT_CSV = ROOT / 'originals/Qnu/Certification References/QNu Certification Matrix_Internal Only(Certification Matrix).csv'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
HEADERS = {'Matrix': 3, 'Gap': 3, 'Country notes': 1, 'Sources': 1, 'Open questions': 1, 'QShield 2.0': 4}
PRODUCTS = {'QVPN': 'C', 'QConnect': 'D', 'QHSM': 'E', 'QKMS': 'F', 'QKD (Armos)': 'G', 'QKDN': 'H', 'Digital QKD (Hodos)': 'I', 'QRNG (Tropos)': 'J'}
MODULES = {'Readiness Assessment': 'D', 'AI Security': 'E', 'Quantum PKI': 'F', 'Quantum Vault': 'G', 'Quantum Entropy': 'H'}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def xlsx(path):
    result = {}
    with zipfile.ZipFile(path) as archive:
        def xml(name):
            return ET.fromstring(archive.read(name))
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(t.text or '' for t in si.findall('.//s:t', NS)) for si in xml('xl/sharedStrings.xml')]
        styles = xml('xl/styles.xml')
        fills = []
        for fill in styles.find('s:fills', NS):
            color = fill.find('.//s:fgColor', NS)
            fills.append(dict(color.attrib) if color is not None else {})
        formats = [int(x.attrib.get('fillId', 0)) for x in styles.find('s:cellXfs', NS)]
        rels = {x.attrib['Id']: x.attrib['Target'] for x in xml('xl/_rels/workbook.xml.rels')}
        for sheet in xml('xl/workbook.xml').find('s:sheets', NS):
            rid = sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            target = rels[rid]
            name = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            doc = xml(name)
            cells, colors = {}, {}
            for c in doc.findall('.//s:sheetData/s:row/s:c', NS):
                if c.find('s:f', NS) is not None:
                    raise ValueError('Formula requires review: ' + sheet.attrib['name'] + '!' + c.attrib['r'])
                v = c.find('s:v', NS)
                if c.attrib.get('t') == 'inlineStr':
                    value = ''.join(t.text or '' for t in c.findall('.//s:t', NS))
                elif v is not None and v.text is not None:
                    value = strings[int(v.text)] if c.attrib.get('t') == 's' else v.text
                else:
                    continue
                if value == '':
                    continue
                cells[c.attrib['r']] = value
                colors[c.attrib['r']] = fills[formats[int(c.attrib.get('s', 0))]]
            result[sheet.attrib['name']] = {'cells': cells, 'fills': colors, 'merges': [m.attrib['ref'] for m in doc.findall('s:mergeCells/s:mergeCell', NS)], 'dimension': doc.find('s:dimension', NS).attrib['ref']}
    if set(result) != set(HEADERS):
        raise ValueError('Workbook sheets changed; review schema before import')
    return result

def rows(sheet, start):
    cells = sheet['cells']
    inherited = {}
    for m in sheet['merges']:
        match = re.fullmatch(r'A(\d+):A(\d+)', m)
        if match:
            for n in range(int(match[1]), int(match[2]) + 1):
                inherited[n] = (cells.get('A' + match[1]), 'A' + match[1])
    last = max(int(re.search(r'\d+', c)[0]) for c in cells)
    for n in range(start, last + 1):
        values = {re.sub(r'\d+', '', c): v for c, v in cells.items() if int(re.search(r'\d+', c)[0]) == n}
        if not values:
            continue
        country, country_cell = inherited.get(n, (values.get('A'), 'A' + str(n)))
        yield n, country, country_cell, values

def build(workbook=DEFAULT_WORKBOOK, status_csv=DEFAULT_CSV):
    sheets = xlsx(workbook)
    for product, col in PRODUCTS.items():
        expected = {'QVPN': 'QVPN (defence, with QRNG)', 'QConnect': 'QConnect (enterprise, with QRNG)'}.get(product, product)
        if sheets['Matrix']['cells'].get(col + '3') != expected or sheets['Gap']['cells'].get(col + '3') != expected:
            raise ValueError('Product column changed; review schema: ' + col)
    for col, label in zip('ABCDEFGHIJ', ['ID', 'Country', 'Claim supported', 'URL', 'Publisher', 'Primary/Secondary (type)', 'Date checked', 'Confidence', 'Verifier status', 'Raw file / local ref']):
        if sheets['Sources']['cells'].get(col + '1') != label:
            raise ValueError('Source schema changed: ' + col)
    for sn, header in [('Matrix', 'C3'), ('QShield 2.0', 'F4'), ('Sources', 'A1')]:
        expected = {'Matrix': 'QVPN (defence, with QRNG)', 'QShield 2.0': 'Quantum PKI', 'Sources': 'ID'}[sn]
        if sheets[sn]['cells'].get(header) != expected:
            raise ValueError('Column schema changed: ' + sn)
    data = {'schema_version': 1, 'version': digest(workbook)[:12] + '-' + digest(status_csv)[:12] + '-schema1-' + digest(Path(__file__))[:8], 'workbook_sha256': digest(workbook), 'csv_sha256': digest(status_csv), 'original_workbook': str(workbook), 'original_csv': str(status_csv), 'research_dates': {'Matrix': '2026-10-06', 'QShield 2.0': '2026-10-07', 'assumption_update': '2026-10-08', 'received': '2026-10-09', 'internal_csv_effective': 'Not stated'}, 'sheets': sheets, 'products': PRODUCTS, 'modules': MODULES, 'matrix': [], 'gaps': [], 'qshield': [], 'country_notes': [], 'questions': [], 'sources': {}, 'certifications': [], 'assumptions': [], 'status_assertions': []}
    for sn in ('Matrix', 'QShield 2.0'):
        match = re.search(r'as of (\d{4}-\d{2}-\d{2})', sheets[sn]['cells']['A1'])
        if not match:
            raise ValueError('Research date missing; review ' + sn + '!A1')
        data['research_dates'][sn] = match[1]
    dates = re.findall(r'\d{4}-\d{2}-\d{2}', sheets['Matrix']['cells']['A2'])
    data['research_dates']['assumption_update'] = max(dates) if dates else 'Not stated'
    for sn, key, start, cols in [('Matrix', 'matrix', 4, PRODUCTS), ('Gap', 'gaps', 5, PRODUCTS), ('QShield 2.0', 'qshield', 5, {'Shared software gates': 'C', **MODULES})]:
        for n, country, country_cell, values in rows(sheets[sn], start):
            if not country or 'B' not in values:
                continue
            if values['B'] not in ('Commercial', 'Government/Defence/CI'):
                raise ValueError('Unexpected segment: ' + sn + '!B' + str(n))
            for product, col in cols.items():
                if col in values:
                    coord = col + str(n)
                    data[key].append({'country': country, 'country_ref': sn + '!' + country_cell, 'segment': values['B'], 'product': product, 'text': values[col], 'ref': sn + '!' + coord, 'fill': sheets[sn]['fills'][coord]})
    for n, country, _, values in rows(sheets['Sources'], 2):
        sid = values['A']
        if sid in data['sources'] or not re.fullmatch(r'S\d+', sid):
            raise ValueError('Invalid source ID: ' + sid)
        data['sources'][sid] = {key: values.get(col, '') for col, key in zip('ABCDEFGHIJ', ['id', 'country', 'claim', 'url', 'publisher', 'type', 'checked', 'confidence', 'verifier', 'raw_ref'])}
        data['sources'][sid]['ref'] = 'Sources!A' + str(n) + ':J' + str(n)
    for n, country, _, values in rows(sheets['Country notes'], 2):
        for col, text in values.items():
            if col != 'A':
                data['country_notes'].append({'country': country, 'heading': sheets['Country notes']['cells'][col + '1'], 'text': text, 'ref': 'Country notes!' + col + str(n)})
    for n, country, _, values in rows(sheets['Open questions'], 2):
        data['questions'].append({'country': country, 'products': values.get('B', ''), 'text': values.get('C', ''), 'owner': values.get('D', ''), 'impact': values.get('E', ''), 'raw_ref': values.get('F', ''), 'ref': 'Open questions!A' + str(n) + ':F' + str(n), 'state': 'resolved' if re.search(r'^RESOLVED\b', values.get('C', ''), re.I) or re.search(r'^Resolved\b', values.get('D', ''), re.I) else 'open'})
    for sn in ('Matrix', 'QShield 2.0'):
        data['assumptions'].append({'text': sheets[sn]['cells']['A2'], 'ref': sn + '!A2'})
    for product, col in PRODUCTS.items():
        data['status_assertions'].append({'product': product, 'text': sheets['Gap']['cells'][col + '4'], 'ref': 'Gap!' + col + '4', 'visibility': 'internal'})
    raw_csv = status_csv.read_bytes()
    try:
        csv_text = raw_csv.decode('utf-8-sig')
        encoding = 'utf-8-sig'
    except UnicodeDecodeError:
        csv_text = raw_csv.decode('cp1252')
        encoding = 'cp1252'
    csv_rows = list(csv.reader(io.StringIO(csv_text)))
    data['csv_encoding'] = encoding
    data['csv_cells'] = {str(n) + ':' + str(i): v for n, row in enumerate(csv_rows, 1) for i, v in enumerate(row, 1) if v}
    if csv_rows[2][0] != 'Product' or len(csv_rows[3]) != 36:
        raise ValueError('Internal matrix schema changed')
    for n, row in enumerate(csv_rows[4:], 5):
        if not row[0] or not row[1].isdigit():
            continue
        for col in range(4, 36, 4):
            compliant, status, date, remarks = row[col:col+4]
            data['certifications'].append({'product': row[0], 'category': csv_rows[2][col], 'compliant': compliant, 'status': status, 'date': date, 'remarks': remarks, 'ref': 'Internal CSV row ' + str(n) + ', columns ' + str(col+1) + '–' + str(col+4), 'visibility': 'internal'})
    # Store tagged requirements independently of source-reported gap and
    # certification assertions, with stable within-snapshot identifiers.
    from engine import bullets
    data['version'] += '-rules-' + digest(APP / 'engine.py')[:8]
    data['requirements'] = []
    for record in data['matrix'] + data['qshield']:
        for n, item in enumerate(bullets(record), 1):
            data['requirements'].append({**item, 'id': record['ref'] + '#item' + str(n), 'country': record['country'], 'segment': record['segment'], 'product': record['product'], 'assertion_type': 'Supplied workbook requirement / qualification'})
    data['certification_assertions_by_status'] = {
        'source_reported_certified': [r for r in data['certifications'] if r['status'] == 'Certified'],
        'planned': [r for r in data['certifications'] if r['status'] == 'Planned'],
        'in_progress': [r for r in data['certifications'] if r['status'] == 'In progress'],
        'not_applicable': [r for r in data['certifications'] if r['status'] == '-'],
    }
    if data['workbook_sha256'] != '3c1136d71e616d4023073d0f65bafb7cfead675a2bfabccd97dd452f5010aa7a':
        data['research_dates']['received'] = 'Not stated for this revision'
    ids = set(data['sources'])
    cited = {sid for sn, sheet in sheets.items() if sn != 'Sources' for value in sheet['cells'].values() for sid in re.findall(r'\bS\d+\b', value)}
    missing = sorted(cited - ids)
    if missing:
        raise ValueError('Unresolved source IDs: ' + ', '.join(missing))
    data['coverage'] = {sn: {'nonempty_cells': len(s['cells']), 'dimension': s['dimension'], 'merges': len(s['merges'])} for sn, s in sheets.items()}
    data['coverage'].update({'total_cells': sum(len(s['cells']) for s in sheets.values()), 'source_records': len(ids), 'question_records': len(data['questions']), 'certification_records': len(data['certifications']), 'unresolved_source_ids': missing})
    return data

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument('--status-csv', type=Path, default=DEFAULT_CSV)
    parser.add_argument('--activate', action='store_true', help='Explicitly activate a reviewed local snapshot; otherwise stage only')
    args = parser.parse_args()
    data = build(args.workbook.resolve(), args.status_csv.resolve())
    target = APP / 'private/versions' / (data['version'] + '.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    if target.exists() and target.read_text() != serialized:
        raise ValueError('Immutable snapshot differs; review importer schema/version')
    target.write_text(serialized)
    if args.activate:
        (APP / 'private/active.json').write_text(json.dumps({'version': data['version']}) + '\n')
    print(json.dumps({'version': data['version'], 'activated': args.activate, 'coverage': data['coverage']}, indent=2))

if __name__ == '__main__':
    main()
