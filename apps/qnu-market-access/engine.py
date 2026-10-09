"""Deterministic workbook retrieval and audience projection, independent of HTTP/UI."""
import copy
import json
import re
from pathlib import Path

APP = Path(__file__).resolve().parent
EXPORT = 'Cross-cutting: India export (SCOMET)'
EU = {'Austria', 'Belgium', 'Bulgaria', 'Croatia', 'Cyprus', 'Czechia', 'Denmark', 'Estonia', 'Finland', 'France', 'Germany', 'Greece', 'Hungary', 'Ireland', 'Italy', 'Latvia', 'Lithuania', 'Luxembourg', 'Malta', 'Netherlands', 'Poland', 'Portugal', 'Romania', 'Slovakia', 'Slovenia', 'Spain', 'Sweden'}
INTERNAL = re.compile(r'QNu|roadmap|internal.only|certified|in progress|submission.{0,30}pending|certification.{0,15}planned', re.I)
KINDS = {'M': 'Mandatory', 'E': 'Buyer-expected', 'R': 'Recommended', 'U': 'Qualification / unknown'}
COLOR = {'C6EFCE': 'GREEN', 'FFEB9C': 'YELLOW', 'FFC7CE': 'RED', 'D9D9D9': 'GREY'}
STATUS = {'GREEN': 'Conditions remain', 'YELLOW': 'Further certification / approval needed', 'RED': 'Source-reported blocker', 'GREY': 'Unconfirmed', 'UNKNOWN': 'No source assessment', 'NA': 'Not applicable'}

def load_data():
    active = json.loads((APP / 'private/active.json').read_text())
    return json.loads((APP / 'private/versions' / (active['version'] + '.json')).read_text())

def safe_partner(text):
    return not INTERNAL.search(text)

def clean_key(text):
    tag = re.search(r'\[([MER])/([HML])\]', text)
    classification = tag[0] if tag else '[UNTAGGED]'
    text = re.sub(r'\[[MER]/[HML]\]|\(S\d+(?:,\s*S\d+)*\)', '', text)
    return classification + ' ' + re.sub(r'\s+', ' ', text).strip().lower()

def bullets(record):
    # Every line survives, including untagged qualifications. Verdict introductions
    # are separate gap assertions; headings keep context for following bullets.
    context = ''
    for line in record['text'].splitlines():
        text = line.strip().lstrip('•').strip()
        if not text:
            continue
        if text.startswith('Accompanying QRNG device:'):
            context = 'Accompanying QRNG'
            continue
        if record['ref'].startswith('QShield 2.0!') and re.match(r'^(GREEN|YELLOW|RED|GREY)\b', text):
            continue
        tag = re.search(r'\[([MER])/([HML])\]', text)
        yield {'text': text, 'kind': tag[1] if tag else 'U', 'confidence': tag[2] if tag else 'Not tagged', 'sources': sorted(set(re.findall(r'\bS\d+\b', text)), key=lambda s: int(s[1:])), 'refs': [record['ref']], 'scopes': [record['country']], 'components': [context or record['product']], 'qualification': 'Unconfirmed; verify before relying on this' if re.search(r'UNCONFIRMED|not checked|confirm with|classification call', text, re.I) else ''}

def applicability(item, query):
    # Only explicit, narrowly recognizable predicates are evaluated. Broader
    # prose remains conditional and visible instead of guessing legal scope.
    text = item['text']
    if item['qualification']:
        return 'Unconfirmed applicability', item['qualification']
    predicates = [(r'^(?:FIs:|Banks:|Bank buyers|Buyer-expectation note.*bank buyers)', 'finance'), (r'^(?:Healthcare|Health sector|Hospitals):', 'health'), (r'^(?:Telecom operators|Telecom sector):', 'telecom')]
    for pattern, sector in predicates:
        if re.search(pattern, text, re.I):
            if query['sector'] == 'unspecified':
                return 'Review applicability', 'Applies to ' + sector + '; sector not specified'
            if query['sector'] != sector:
                return 'Not applicable to selected sector', 'Explicit ' + sector + ' clause retained for traceability'
            return 'Relevant', 'Selected sector: ' + sector
    if re.search(r'\bonly\b|\bif\b|\bwhere\b|\bunless\b|\bclassified\b|\bcloud\b|\bSaaS\b|\bCII\b|\bNCII\b|\bcritical\b', text, re.I):
        return 'Conditional — review', 'Read the condition in the source wording'
    return 'Relevant', 'According to the selected source scope'

def owner(text):
    # Responsibility is assigned only where the wording names an actor.
    if re.search(r'importer|local partner|reseller|distributor|Malaysian supplier', text, re.I):
        return 'Importer / partner (named in source)'
    if re.search(r'CII owners|duties (?:fall )?on|buyer.{0,60}(?:needs|must|requires|acting|operating)|entities must|customer must|operator.{0,30}(?:must|dut)', text, re.I):
        return 'Customer (named in source)'
    if re.search(r'manufacturer|maker|exporter|QNu.{0,30}(?:must|self.classifies)', text, re.I):
        return 'QNu / manufacturer or exporter (confirm contractual role)'
    return ''

def verdict(record):
    if re.search(r'^Not applicable:', record['text'], re.I):
        return 'NA'
    rgb = record.get('fill', {}).get('rgb', '')[-6:]
    return COLOR.get(rgb, re.match(r'^(GREEN|YELLOW|RED|GREY)', record['text'])[1] if re.match(r'^(GREEN|YELLOW|RED|GREY)', record['text']) else 'UNKNOWN')

class Guide:
    def __init__(self, data=None):
        self.data = data or load_data()

    def catalog(self, role):
        d = self.data
        countries = sorted({r['country'] for r in d['matrix'] if r['country'] != EXPORT})
        result = {'title': 'QNu Market Access Guide', 'version': d['version'], 'role': role, 'countries': countries, 'scope_count': len({r['country'] for r in d['matrix']}), 'products': list(d['products']) + ['QShield 2.0'], 'modules': list(d['modules']), 'qshield_countries': sorted({r['country'] for r in d['qshield']}), 'research_dates': d['research_dates'], 'notice': 'Based on the supplied research snapshot. Source dates are recorded; the findings are not independently verified or continuously updated.', 'hardware_products': ['QHSM', 'QKD (Armos)', 'QRNG (Tropos)'], 'bundled_products': ['QVPN', 'QConnect']}
        if role != 'partner':
            result['coverage'] = d['coverage']
        return result

    def validate(self, raw):
        q = {'country': raw.get('country', 'Singapore'), 'product': raw.get('product', 'QConnect'), 'segment': raw.get('segment', 'Commercial'), 'deployment': raw.get('deployment', 'on-prem'), 'sector': raw.get('sector', 'unspecified'), 'hardware': raw.get('hardware', 'no'), 'radio': raw.get('radio', 'no'), 'export_india': raw.get('export_india', 'yes'), 'modules': raw.get('modules', ['Readiness Assessment'])}
        if q['product'] not in list(self.data['products']) + ['QShield 2.0']:
            raise ValueError('Choose a product from the available list')
        if q['segment'] not in ('Commercial', 'Government/Defence/CI') or q['deployment'] not in ('on-prem', 'cloud') or q['sector'] not in ('unspecified', 'general', 'finance', 'health', 'telecom', 'classified'):
            raise ValueError('Invalid customer or deployment selection')
        for name in ('hardware', 'radio', 'export_india'):
            if q[name] not in ('yes', 'no'):
                raise ValueError('Invalid applicability answer')
        if not isinstance(q['modules'], list) or any(m not in self.data['modules'] for m in q['modules']):
            raise ValueError('Invalid module')
        q['modules'] = list(dict.fromkeys(q['modules']))
        if q['product'] == 'QShield 2.0' and not q['modules']:
            raise ValueError('Select at least one QShield module')
        if not isinstance(q['country'], str) or len(q['country']) > 160:
            raise ValueError('Invalid country')
        return q

    def approved_statements(self):
        path = APP / 'private/approvals.json'
        values = json.loads(path.read_text()) if path.exists() else []
        return [a for a in values if a['version'] == self.data['version']]

    def result(self, raw, role):
        q = self.validate(raw)
        d = self.data
        available = {r['country'] for r in d['matrix']}
        # A missing destination must not become a complete answer merely because
        # some export or regional evidence exists.
        known = q['country'] in available
        scopes = [q['country']]
        if q['country'] in EU:
            scopes.append('EU-wide')
        if q['country'] == 'Dubai':
            scopes.append('UAE')
        if q['export_india'] == 'yes' and EXPORT not in scopes:
            scopes.append(EXPORT)
        selected, gaps, caveats = [], [], []
        assumptions = [{'text': 'Selected context: ' + q['deployment'] + '; sector: ' + q['sector'] + '; exports from India: ' + q['export_india'] + '.', 'ref': 'User selection', 'kind': 'User input'}]
        is_shield = q['product'] == 'QShield 2.0'
        is_bundle = q['product'] in ('QVPN', 'QConnect')
        na = (q['product'] == 'QVPN' and q['segment'] == 'Commercial') or (q['product'] == 'QConnect' and q['segment'] != 'Commercial')
        if is_bundle:
            assumptions.append({'text': 'Source assumption: QVPN serves Government/Defence/CI and QConnect serves Commercial; both always accompany a QRNG appliance. Software and hardware gates apply together.', 'ref': 'Matrix!A2', 'kind': 'Versioned source assertion'})
        else:
            assumptions.append({'text': 'Source form factor: QHSM, QKD and QRNG are appliances; QKMS, QKDN and Digital QKD are software/cloud. Confirm the actual product version and SKU.', 'ref': 'Matrix!A2', 'kind': 'Versioned source assertion'})
        hardware = is_bundle or q['product'] in ('QHSM', 'QKD (Armos)', 'QRNG (Tropos)') or q['hardware'] == 'yes'
        if is_shield:
            assumptions.append({'text': 'QShield sheet assumes on-premises delivery. SaaS adds Digital QKD cloud clauses. Readiness and AI Security do not encrypt; PKI encryption depends on KEM certificates or escrow; Vault encrypts; Entropy supplies randomness.', 'ref': 'QShield 2.0!A2', 'kind': 'Versioned source assertion'})
            if 'Quantum PKI' in q['modules']:
                caveats.append('Confirm whether PKI issues KEM certificates or escrows keys; signature-only and encryption paths differ.')
        if hardware:
            assumptions.append({'text': 'The source assumes no radio. A radio SKU needs additional type-approval review.', 'ref': 'Matrix!A2', 'kind': 'Versioned source assertion'})
            if q['radio'] == 'yes':
                caveats.append('Radio present: the source has no SKU-specific radio approvals. Confirm local type approval before shipment.')
        if q['hardware'] == 'yes' and not is_shield and not is_bundle and q['product'] not in ('QHSM', 'QKD (Armos)', 'QRNG (Tropos)'):
            caveats.append('Accompanying hardware requires a separate appliance/SKU review; select the actual appliance product separately.')
        if not known:
            caveats.append('Destination is absent from the main Matrix. Export evidence does not establish destination requirements.')
        shield_known = any(r['country'] == q['country'] for r in d['qshield'])
        if is_shield and not shield_known:
            caveats.append('No QShield module row for this destination. Regional or export clauses are partial evidence only; local module applicability remains unknown.')
        for scope in scopes:
            if is_shield:
                records = [r for r in d['qshield'] if r['country'] == scope and r['segment'] == q['segment'] and r['product'] in ['Shared software gates'] + q['modules']]
                selected.extend(records)
                gaps.extend(r for r in records if r['product'] != 'Shared software gates')
                if q['deployment'] == 'cloud':
                    for r in d['matrix']:
                        if r['country'] == scope and r['segment'] == q['segment'] and r['product'] == 'Digital QKD (Hodos)':
                            cloud_lines = [line for line in r['text'].splitlines() if re.search(r'cloud|SaaS|outsourc|PDPA|GDPR|localis|localiz|data transfer|cross.border', line, re.I)]
                            if cloud_lines:
                                selected.append({**r, 'text': '\n'.join(cloud_lines), 'product': 'SaaS cloud supplement (Digital QKD clauses)'})
                if 'Quantum Vault' in q['modules']:
                    for r in d['matrix']:
                        if r['country'] == scope and r['segment'] == q['segment'] and r['product'] == 'QKMS':
                            lines = [line for line in r['text'].splitlines() if re.search(r'\[E/[HML]\]', line) and re.search(r'crypto|FIPS|HSM|validat', line, re.I)]
                            if lines:
                                selected.append({**r, 'text': '\n'.join(lines), 'product': 'Vault buyer expectations referenced to QKMS'})
                if q['hardware'] == 'yes' and 'Quantum Entropy' in q['modules']:
                    selected.extend(r for r in d['matrix'] if r['country'] == scope and r['segment'] == q['segment'] and r['product'] == 'QRNG (Tropos)')
                    gaps.extend(r for r in d['gaps'] if r['country'] == scope and r['segment'] == q['segment'] and r['product'] == 'QRNG (Tropos)')
                elif q['hardware'] == 'yes':
                    caveats.append('Accompanying hardware is unspecified. Select its product separately; QRNG gates are only added for Entropy with QRNG.')
            else:
                products = [q['product']] + (['QRNG (Tropos)'] if is_bundle and not na else [])
                selected.extend(r for r in d['matrix'] if r['country'] == scope and r['segment'] == q['segment'] and r['product'] in products)
                gaps.extend(r for r in d['gaps'] if r['country'] == scope and r['segment'] == q['segment'] and r['product'] in products)
                if q['hardware'] == 'yes' and not hardware:
                    caveats.append('Hardware is outside this software row; review the actual appliance product separately.')
        if na:
            selected = []
            caveats.append('The selected customer segment is explicitly not applicable under Matrix!A2; choose the counterpart product.')
        unique = {}
        withheld = 0
        for record in selected:
            for item in bullets(record):
                if role == 'partner' and not safe_partner(item['text']):
                    withheld += 1
                    continue
                key = clean_key(item['text'])
                if key in unique:
                    for field in ('refs', 'scopes', 'components', 'sources'):
                        unique[key][field] = list(dict.fromkeys(unique[key][field] + item[field]))
                else:
                    unique[key] = item
        requirements = list(unique.values())
        # Stable category grouping preserves source order inside each group.
        requirements.sort(key=lambda item: list(KINDS).index(item['kind']))
        for i, item in enumerate(requirements, 1):
            item['id'] = 'R' + str(i)
            item['category'] = KINDS[item['kind']]
            item['applicability'], item['condition'] = applicability(item, q)
            item['owner'] = owner(item['text'])
        if role == 'partner':
            caveats.append('Certification status, roadmap, gap assessments and internal questions are withheld pending approval. Some mixed source text may also be withheld; this is not a complete internal assessment.')
        gap_records = [{**r, 'verdict': verdict(r)} for r in gaps] if role != 'partner' else []
        worst = max((verdict(r) for r in gaps), key=lambda v: {'NA': 0, 'GREEN': 1, 'YELLOW': 2, 'GREY': 3, 'UNKNOWN': 3, 'RED': 4}[v], default='UNKNOWN')
        if na:
            assessment = 'NA'
        elif not known or (is_shield and not shield_known):
            assessment = 'UNKNOWN'
        elif role == 'partner':
            assessment = 'RESTRICTED'
        else:
            assessment = worst
        title = 'Requirements view — readiness withheld' if assessment == 'RESTRICTED' else STATUS[assessment]
        if q['sector'] == 'classified' and any(re.search(r'classified|Official Secret|VS.NfD|sensitive government', r['text'], re.I) for r in requirements):
            caveats.append('Classified / sensitive use is selected. Any GREEN verdict limited to unclassified use does not establish approval for this scenario; obtain the named classified-use approvals.')
            if assessment in ('GREEN', 'YELLOW'):
                assessment = 'GREY'
                title = 'Classified-use approval needs confirmation'
        if hardware and q['radio'] == 'yes' and assessment in ('GREEN', 'YELLOW'):
            assessment = 'GREY'
            title = 'Radio SKU approval needs confirmation'
        source_ids = list(dict.fromkeys(s for r in requirements for s in r['sources']))
        sources = [self.source(s, role, strict=False) for s in source_ids]
        notes = [r for r in d['country_notes'] if r['country'] in scopes and (role != 'partner' or safe_partner(r['text']))]
        questions = []
        if role != 'partner':
            tokens = {'QKD (Armos)': ['QKD', 'all'], 'Digital QKD (Hodos)': ['dQKD', 'digital', 'all'], 'QRNG (Tropos)': ['QRNG', 'Tropos', 'all']}.get(q['product'], [q['product'], 'all'])
            for r in d['questions']:
                text = r['products'] + ' ' + r['text']
                if r['country'] in scopes + ['All countries'] + (['QShield 2.0'] if is_shield else []) and any(t.lower() in text.lower() for t in tokens):
                    questions.append(r)
        related = [q['product']] + (['QRNG (Tropos)'] if is_bundle or (is_shield and q['hardware'] == 'yes' and 'Quantum Entropy' in q['modules']) else [])
        # Related source labels are shown verbatim, never asserted as proof of a
        # named workbook version or inherited by a QShield module.
        labels = {'QKD (Armos)': 'QKD', 'Digital QKD (Hodos)': 'Digital QKD'}
        certifications = [r for r in d['certifications'] if r['product'] in [labels.get(p, p) for p in related]] if role != 'partner' else []
        status_assertions = [r for r in d['status_assertions'] if r['product'] in related] if role != 'partner' else []
        conflicts = []
        if role != 'partner':
            for r in certifications:
                if 'Q2 2028' in r['date']:
                    col = 'E' if r['product'] == 'QHSM' else 'F'
                    conflicts.append({'text': r['product'] + ': internal CSV certification target Q2 2028; compliance target Q3 2027. Gap row 4 instead says certification planned Jul–Sep 2027. Confirm milestone and effective date.', 'refs': [r['ref'], 'Gap!' + col + '4']})
                if r['product'] == 'QRNG (Tropos)' and 'Entropy' in r['category']:
                    conflicts.append({'text': 'Tropos ESV: internal CSV plans Q4 2027; Gap!J4 plans Jan–Mar 2027. Neither source establishes achieved NIST validation.', 'refs': [r['ref'], 'Gap!J4']})
                if r['product'] == 'QConnect' and 'VAPT' in r['category']:
                    conflicts.append({'text': 'QConnect VAPT: CSV date Q3 2027; its remark flags Q2 2027. Gap!D4 instead targets Oct–Dec 2026 for TTP + VAPT. Confirm before quoting any date.', 'refs': [r['ref'], 'Gap!D4']})
                if 'Started Q1 2027' in r['remarks']:
                    conflicts.append({'text': r['product'] + ' ' + r['category'] + ': “In progress” with “Started Q1 2027”, future-dated relative to receipt on 6 October 2026. Reporting date/year is unresolved.', 'refs': [r['ref']]})
        # Show each conflict once, retaining every independent supporting record.
        combined_conflicts = {}
        for conflict in conflicts:
            key = conflict['text']
            if key not in combined_conflicts:
                combined_conflicts[key] = {**conflict, 'refs': list(conflict['refs'])}
            else:
                combined_conflicts[key]['refs'] = list(dict.fromkeys(combined_conflicts[key]['refs'] + conflict['refs']))
        conflicts = list(combined_conflicts.values())
        actions = [{'text': 'Confirm the selected SKU, deployment, sector and remaining conditional clauses against current primary authorities before a selling or deployment decision.', 'owner': 'QNu + importer/partner + customer (application review recommendation)', 'ref': 'Application review guidance'}]
        for r in requirements:
            if r['kind'] == 'M' and r['applicability'] != 'Not applicable to selected sector':
                actions.append({'text': r['text'], 'owner': r['owner'], 'ref': ', '.join(r['refs'])})
        for c in dict.fromkeys(caveats):
            actions.append({'text': c, 'owner': 'Confirm responsible owner', 'ref': 'Application applicability review'})
        approvals = [a for a in self.approved_statements() if a['product'] in related + (['QShield 2.0'] if is_shield else [])]
        if role == 'partner':
            approvals = [{k: a[k] for k in ('id', 'product', 'text', 'ref', 'scope', 'approved_at')} for a in approvals]
        return {'query': q, 'version': d['version'], 'role': role, 'research_dates': d['research_dates'], 'notice': self.catalog(role)['notice'], 'summary': {'assessment': assessment, 'title': title, 'text': 'All stated conditions require review. A positive source assessment is not unconditional permission to sell.', 'known_destination': known, 'module_coverage': shield_known if is_shield else None}, 'scopes': scopes, 'assumptions': assumptions, 'requirements': requirements, 'counts': {k: sum(r['kind'] == k for r in requirements) for k in KINDS}, 'gaps': gap_records, 'certifications': certifications, 'status_assertions': status_assertions, 'conflicts': conflicts, 'questions': questions, 'notes': notes, 'sources': sources, 'actions': actions, 'caveats': list(dict.fromkeys(caveats)), 'partner_withheld_items': withheld, 'approved_statements': approvals, 'certification_notice': 'Source-reported labels, not independently verified certificates. Compliance and certification are distinct. CSV version coverage is not stated; related labels do not establish coverage for Armos, Hodos or QShield.' if role != 'partner' else 'Only explicitly approved statements may appear; no internal certification assertion is shared by default.'}

    def source(self, sid, role, strict=True):
        r = self.data['sources'].get(sid)
        if r is None:
            raise KeyError('Source not found')
        if role == 'partner':
            if not safe_partner(r['claim']):
                if strict:
                    raise PermissionError('Source contains information pending partner approval')
                return {'id': sid, 'restricted': True, 'ref': r['ref'], 'claim': 'Source details pending partner review'}
            return {k: v for k, v in r.items() if k != 'raw_ref'}
        return copy.deepcopy(r)

    def evidence(self, ref, role):
        if ref.startswith('Internal CSV row '):
            if role == 'partner':
                raise PermissionError('Internal Only CSV evidence is not approved for partner viewing')
            row = next((r for r in self.data['certifications'] if r['ref'] == ref), None)
            if row is None:
                raise KeyError('CSV evidence not found')
            return {'ref': ref, 'text': row['product'] + ' / ' + row['category'] + '\nCompliant? ' + row['compliant'] + '\nCertification status: ' + row['status'] + '\nCompletion / planned date: ' + row['date'] + '\nRemarks: ' + row['remarks'], 'version': self.data['version'], 'source_sha256': self.data['csv_sha256'], 'classification': 'INTERNAL ONLY; effective date not stated'}
        if '!' not in ref:
            raise KeyError('Use an exact workbook cell reference')
        sn, coord = ref.split('!', 1)
        if not re.fullmatch(r'[A-Z]+\d+', coord) or sn not in self.data['sheets']:
            raise KeyError('Cell not found')
        text = self.data['sheets'][sn]['cells'].get(coord)
        if text is None:
            raise KeyError('Empty or missing cell')
        if role == 'partner' and (sn not in ('Matrix', 'Country notes') or not safe_partner(text) or int(re.search(r'\d+', coord)[0]) <= (3 if sn == 'Matrix' else 1)):
            raise PermissionError('Raw cell is internal or has mixed unapproved content; use the filtered requirements view')
        return {'ref': ref, 'text': text, 'fill': self.data['sheets'][sn]['fills'][coord], 'version': self.data['version'], 'source_sha256': self.data['workbook_sha256'], 'classification': 'Internal source evidence' if role != 'partner' else 'Partner requirement evidence'}
