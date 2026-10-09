import copy
import hashlib
import http.client
import json
from pathlib import Path
import re
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import APP, Guide, EU, EXPORT, safe_partner, clean_key
from import_data import build, DEFAULT_WORKBOOK, DEFAULT_CSV, HEADERS
from brief import brief
from server import DemoServer

class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = build()
        cls.guide = Guide(cls.data)

    def test_exact_coverage(self):
        d = self.data
        self.assertEqual(set(d['sheets']), set(HEADERS))
        self.assertEqual(d['coverage']['total_cells'], 14754)
        self.assertEqual(len(d['sources']), 999)
        self.assertEqual(len(d['questions']), 321)
        self.assertEqual(len(d['certifications']), 64)
        self.assertEqual(len(d['matrix']), 51 * 2 * 8)
        self.assertEqual(len(d['gaps']), 51 * 2 * 8)
        self.assertEqual(len(d['qshield']), 19 * 2 * 6)

    def test_independent_original_cell_reconciliation(self):
        try:
            from openpyxl import load_workbook
        except ImportError:
            self.skipTest('Run bundled Python for independent openpyxl comparison')
        workbook = load_workbook(DEFAULT_WORKBOOK, data_only=False)
        for sheet in workbook:
            original = {c.coordinate: str(c.value) for row in sheet for c in row if c.value is not None}
            self.assertEqual(self.data['sheets'][sheet.title]['cells'], original, sheet.title)
        workbook.close()

    def test_original_hashes_unchanged(self):
        self.assertEqual(hashlib.sha256(DEFAULT_WORKBOOK.read_bytes()).hexdigest(), '3c1136d71e616d4023073d0f65bafb7cfead675a2bfabccd97dd452f5010aa7a')
        self.assertEqual(hashlib.sha256(DEFAULT_CSV.read_bytes()).hexdigest()[:12], '17abfef89066')

    def test_merged_country_traceability(self):
        row = next(r for r in self.data['matrix'] if r['ref'] == 'Matrix!D5')
        self.assertEqual(row['country'], 'Singapore')
        self.assertEqual(row['country_ref'], 'Matrix!A4')

    def test_source_ids_resolve(self):
        self.assertEqual(self.data['coverage']['unresolved_source_ids'], [])
        for rows in ('matrix', 'qshield', 'country_notes', 'questions'):
            for r in self.data[rows]:
                for sid in re.findall(r'\bS\d+\b', r['text']):
                    self.assertIn(sid, self.data['sources'])

    def test_csv_encoding_and_separate_status_fields(self):
        r = next(r for r in self.data['certifications'] if r['product'] == 'QKDN' and r['category'] == 'TEC')
        self.assertEqual(r['compliant'], 'Yes')
        self.assertEqual(r['status'], 'Planned')
        self.assertNotIn('�', json.dumps(self.data['certifications'], ensure_ascii=False))
        self.assertEqual(sum(r['status'] == 'Certified' for r in self.data['certifications']), 3)

    def test_qrng_bundle_no_duplicate_requirements(self):
        r = self.guide.result({'country':'Singapore','product':'QConnect','export_india':'no'}, 'employee')
        keys = [clean_key(x['text']) for x in r['requirements']]
        self.assertEqual(len(keys), len(set(keys)))
        importer = next(x for x in r['requirements'] if 'Every telecom-equipment import' in x['text'])
        self.assertIn('Matrix!D5', importer['refs'])
        self.assertIn('Matrix!J5', importer['refs'])
        self.assertEqual(len(r['gaps']), 2)

    def test_requirements_grouped_mandatory_first(self):
        rank = {'M': 0, 'E': 1, 'R': 2, 'U': 3}
        for role in ('employee', 'partner'):
            for query in ({'country': 'Singapore', 'product': 'QConnect'},
                          {'country': 'Germany', 'product': 'QHSM'},
                          {'country': 'Singapore', 'product': 'QShield 2.0', 'modules': list(self.data['modules'])}):
                with self.subTest(role=role, query=query):
                    result = self.guide.result(query, role)
                    kinds = [rank[r['kind']] for r in result['requirements']]
                    self.assertEqual(kinds, sorted(kinds))
                    self.assertEqual(result['requirements'][0]['kind'], 'M')
                    self.assertNotIn('Not assigned in source', brief(result))

    def test_green_is_conditional(self):
        r = self.guide.result({'country':'Singapore','product':'QConnect','export_india':'no'}, 'employee')
        self.assertEqual(r['summary']['assessment'], 'GREEN')
        self.assertEqual(r['summary']['title'], 'Conditions remain')
        self.assertIn('not unconditional permission', r['summary']['text'])
        self.assertTrue(r['actions'])

    def test_segment_na_is_not_unknown(self):
        r = self.guide.result({'country':'Singapore','product':'QVPN'}, 'employee')
        self.assertEqual(r['summary']['assessment'], 'NA')
        self.assertEqual(r['requirements'], [])
        unknown = self.guide.result({'country':'United States','product':'QVPN'}, 'employee')
        # Explicit source segment exclusion still applies, even with missing market.
        self.assertEqual(unknown['summary']['assessment'], 'NA')
        self.assertFalse(unknown['summary']['known_destination'])

    def test_missing_destination_and_qshield(self):
        r = self.guide.result({'country':'United States','product':'QHSM'}, 'employee')
        self.assertEqual(r['summary']['assessment'], 'UNKNOWN')
        self.assertFalse(r['summary']['known_destination'])
        r = self.guide.result({'country':'Australia','product':'QShield 2.0'}, 'employee')
        self.assertFalse(r['summary']['module_coverage'])
        self.assertEqual(r['summary']['assessment'], 'UNKNOWN')

    def test_regional_and_export_scopes_deduplicate(self):
        r = self.guide.result({'country':'Germany','product':'QHSM'}, 'employee')
        self.assertEqual(r['scopes'], ['Germany','EU-wide',EXPORT])
        keys = [clean_key(x['text']) for x in r['requirements']]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(any(len(x['refs']) > 1 for x in r['requirements']))
        dubai = self.guide.result({'country':'Dubai','product':'QHSM'}, 'employee')
        self.assertIn('UAE', dubai['scopes'])
        norway = self.guide.result({'country':'Norway','product':'QHSM'}, 'employee')
        self.assertNotIn('EU-wide', norway['scopes'])

    def test_india_export_toggle(self):
        r = self.guide.result({'country':'Singapore','product':'QHSM','export_india':'no'}, 'employee')
        self.assertNotIn(EXPORT, r['scopes'])
        r = self.guide.result({'country':'Singapore','product':'QHSM','export_india':'yes'}, 'employee')
        self.assertIn(EXPORT, r['scopes'])
        self.assertTrue(any('SCOMET' in x['text'] for x in r['requirements']))

    def test_qshield_shared_modules_and_bundle(self):
        q = {'country':'Singapore','product':'QShield 2.0','modules':['Quantum PKI','Quantum Entropy'],'hardware':'yes','export_india':'no'}
        r = self.guide.result(q, 'employee')
        self.assertTrue(any('Shared software gates' in x['components'] for x in r['requirements']))
        self.assertTrue(any('Quantum PKI' in x['components'] for x in r['requirements']))
        self.assertTrue(any('QRNG (Tropos)' in x['components'] for x in r['requirements']))
        self.assertFalse(any(x['product'] in ['QHSM','QKMS'] for x in r['certifications']))

    def test_qshield_cloud_supplement(self):
        r = self.guide.result({'country':'Singapore','product':'QShield 2.0','deployment':'cloud','modules':['Quantum Vault'],'export_india':'no'}, 'employee')
        self.assertTrue(any('SaaS cloud supplement (Digital QKD clauses)' in x['components'] for x in r['requirements']))
        self.assertTrue(any('Quantum Vault' in x['components'] for x in r['requirements']))
        self.assertFalse(any(x['product'] == 'QKMS' for x in r['certifications']))

    def test_sector_predicate_retained_and_labeled(self):
        r = self.guide.result({'sector':'general'}, 'employee')
        banks = [x for x in r['requirements'] if x['text'].startswith('Banks:')]
        self.assertTrue(banks)
        self.assertTrue(all(x['applicability'] == 'Not applicable to selected sector' for x in banks))
        r = self.guide.result({'sector':'finance'}, 'employee')
        self.assertTrue(all(x['applicability'] == 'Relevant' for x in r['requirements'] if x['text'].startswith('Banks:')))

    def test_conflicting_milestones_preserved(self):
        for product, words in [('QHSM','Q2 2028'),('QRNG (Tropos)','Q4 2027'),('QConnect','Q2 2027')]:
            r = self.guide.result({'product':product}, 'employee')
            self.assertIn(words, json.dumps(r['conflicts']))
        r = self.guide.result({'product':'QConnect'}, 'employee')
        self.assertIn('future-dated', json.dumps(r['conflicts']))

    def test_duplicate_conflicts_keep_all_evidence(self):
        result = self.guide.result({'country': 'Germany', 'product': 'QHSM'}, 'employee')
        conflicts = [r for r in result['conflicts'] if 'certification target Q2 2028' in r['text']]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(set(conflicts[0]['refs']), {
            'Internal CSV row 7, columns 5–8',
            'Internal CSV row 7, columns 9–12',
            'Gap!E4',
        })
        self.assertEqual(len({r['text'] for r in result['conflicts']}), len(result['conflicts']))

    def test_actions_omit_boilerplate_and_unknown_owners(self):
        for role in ('employee', 'partner'):
            result = self.guide.result({'country': 'Singapore', 'product': 'QConnect'}, role)
            self.assertNotIn('Review and document applicability:', json.dumps(result['actions']))
            self.assertNotIn('Not assigned in source', json.dumps(result))
            clauses = {r['text'] for r in result['requirements'] if r['kind'] == 'M'}
            self.assertTrue(any(r['text'] in clauses for r in result['actions']))

    def test_resolved_questions_are_not_counted_open(self):
        self.assertTrue(any(r['state'] == 'resolved' for r in self.data['questions']))
        self.assertLess(sum(r['state'] == 'open' for r in self.data['questions']), 321)

    def test_radio_and_unknown_hardware(self):
        r = self.guide.result({'product':'QHSM','radio':'yes'}, 'employee')
        self.assertIn('Radio present', json.dumps(r['caveats']))
        r = self.guide.result({'product':'QKMS','hardware':'yes'}, 'employee')
        self.assertIn('separate appliance', json.dumps(r['caveats']))

    def test_all_partner_combinations_are_projected(self):
        for country in self.guide.catalog('partner')['countries']:
            for product in self.guide.catalog('partner')['products']:
                for segment in ('Commercial','Government/Defence/CI'):
                    r = self.guide.result({'country':country,'product':product,'segment':segment,'modules':list(self.data['modules'])}, 'partner')
                    for field in ('certifications','gaps','conflicts','questions','status_assertions'):
                        self.assertEqual(r[field], [], (country,product,segment,field))
                    for x in r['requirements'] + r['notes']:
                        self.assertTrue(safe_partner(x['text']))
                    for x in r['sources']:
                        self.assertNotIn('raw_ref', x)
                    text = brief(r)
                    self.assertNotIn('Q3 2027 (planned)', text)
                    self.assertNotIn('Started Q1 2027', text)
                    self.assertNotIn('QNu status:', text)

    def test_partner_raw_evidence_is_restricted(self):
        for ref in ('Gap!D4','Gap!D6','QShield 2.0!H14','Open questions!C2','Sources!C2','Matrix!A2'):
            with self.assertRaises(PermissionError):
                self.guide.evidence(ref, 'partner')
        self.assertIn('Software by download', self.guide.evidence('Matrix!D5','partner')['text'])

    def test_invalid_context(self):
        for q in ({'product':'invented'}, {'modules':['unknown']}, {'segment':'unknown'}, {'deployment':'unknown'}, {'country':123}, {'product':'QShield 2.0','modules':[]}):
            with self.assertRaises(ValueError):
                self.guide.result(q,'employee')

    def test_source_version_and_hash_available(self):
        r = self.guide.evidence('Matrix!D5','employee')
        self.assertEqual(r['source_sha256'], self.data['workbook_sha256'])
        self.assertEqual(r['version'], self.data['version'])

    def test_tag_qualifications_not_silently_deduplicated(self):
        self.assertNotEqual(clean_key('Clause [M/H] (S1)'), clean_key('Clause [E/H] (S1)'))
        self.assertNotEqual(clean_key('Clause [M/H] (S1)'), clean_key('Clause [M/L] (S1)'))
        self.assertEqual(clean_key('Clause [M/H] (S1)'), clean_key('Clause [M/H] (S2)'))

    def test_csv_evidence_and_partner_denial(self):
        ref = next(r['ref'] for r in self.data['certifications'] if r['product'] == 'QConnect' and 'VAPT' in r['category'])
        self.assertIn('Q3 2027', self.guide.evidence(ref,'employee')['text'])
        with self.assertRaises(PermissionError):
            self.guide.evidence(ref,'partner')

    def test_normalized_requirement_and_status_collections(self):
        self.assertTrue(self.data['requirements'])
        self.assertEqual(len(self.data['certification_assertions_by_status']['source_reported_certified']),3)
        self.assertEqual(len(self.data['certification_assertions_by_status']['planned']),7)
        self.assertEqual(len(self.data['certification_assertions_by_status']['in_progress']),6)

    def test_radio_and_classified_do_not_inherit_conditional_green(self):
        r=self.guide.result({'product':'QHSM','country':'Singapore','radio':'yes','export_india':'no'},'employee')
        self.assertEqual(r['summary']['assessment'],'GREY')
        r=self.guide.result({'product':'QShield 2.0','country':'Malaysia','segment':'Government/Defence/CI','sector':'classified','export_india':'no'},'employee')
        self.assertNotEqual(r['summary']['assessment'],'GREEN')

    def test_staged_review_tracks_exact_changed_cells(self):
        from manage_data import review
        candidate=copy.deepcopy(self.data)
        candidate['sheets']['Matrix']['cells']['D5'] += ' changed'
        r=review(self.data,candidate)
        self.assertEqual(r['changes']['Matrix']['changed'],['Matrix!D5'])

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        private = Path(cls.temp.name) / 'private'
        private.mkdir()
        # Admin mutations are isolated: no actual app approval or invitation is created.
        cls.patches = [patch('server.APP',Path(cls.temp.name)),patch('engine.APP',Path(cls.temp.name))]
        cls.guide = Guide()
        for p in cls.patches: p.start()
        cls.server = DemoServer(('127.0.0.1',0),cls.guide)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()
        for p in cls.patches: p.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.cookie=''; self.csrf=''
        status,data,headers=self.request('/api/session')
        self.cookie=headers['Set-Cookie'].split(';')[0]
        self.csrf=data['csrf']

    def request(self,path,body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port)
        base={'Cookie':self.cookie}
        if body is not None: base.update({'Content-Type':'application/json','X-CSRF-Token':self.csrf,'Origin':'http://127.0.0.1:' + str(self.port)})
        base.update(headers or {})
        conn.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,base)
        response=conn.getresponse(); data=response.read(); status=response.status; hdr=dict(response.getheaders()); conn.close()
        return status,json.loads(data) if hdr.get('Content-Type','').startswith('application/json') else data.decode(errors='replace'),hdr

    def switch(self,role):
        status,data,headers=self.request('/api/demo-role',{'role':role})
        self.assertEqual(status,200)
        self.cookie=headers['Set-Cookie'].split(';')[0]; self.csrf=data['csrf']

    def test_unauthenticated_denied(self):
        self.cookie=''
        self.assertEqual(self.request('/api/results')[0],401)

    def test_no_header_or_query_role_spoofing(self):
        self.switch('partner')
        status,r,_=self.request('/api/results?role=admin&product=QHSM',headers={'X-Role':'admin'})
        self.assertEqual(status,200); self.assertEqual(r['certifications'],[])
        self.assertEqual(self.request('/api/admin?role=admin')[0],403)

    def test_partner_evidence_downloads_export_and_brief(self):
        self.switch('partner')
        for route in ('/api/evidence?ref=Gap!E4','/api/download?file=status-csv','/api/download?file=workbook'):
            self.assertEqual(self.request(route)[0],403)
        for route in ('/private/active.json','/private/versions/x.json','/../engine.py'):
            self.assertEqual(self.request(route)[0],404)
        status,r,headers=self.request('/api/export?product=QHSM')
        self.assertEqual(status,200);self.assertEqual(r['certifications'],[])
        self.assertIn('attachment',headers['Content-Disposition'])
        status,html,headers=self.request('/brief?product=QHSM')
        self.assertEqual(status,200);self.assertIn('PARTNER REQUIREMENTS BRIEF',html)
        self.assertNotIn('Q2 2028 (planned)',html)
        self.assertEqual(headers['Cache-Control'],'no-store, max-age=0')

    def test_csrf_cross_origin_and_host(self):
        self.assertEqual(self.request('/api/demo-role',{'role':'admin'},{'X-CSRF-Token':'wrong'})[0],403)
        self.assertEqual(self.request('/api/demo-role',{'role':'admin'},{'Origin':'https://evil.invalid'})[0],403)
        self.assertEqual(self.request('/api/results',headers={'Host':'evil.invalid'})[0],403)

    def test_invalidated_role_session(self):
        old=self.cookie
        self.switch('partner')
        self.cookie=old
        self.assertEqual(self.request('/api/results')[0],401)

    def test_admin_drafts_approvals_and_revocation(self):
        self.switch('admin')
        status,r,_=self.request('/api/admin/invitations',{'email':'partner@example.invalid','role':'partner'})
        self.assertEqual(status,201);self.assertIn('not sent',r['state'])
        status,admin,_=self.request('/api/admin')
        candidate=admin['candidates'][0]
        status,a,_=self.request('/api/admin/approvals',{'ref':candidate['ref'],'review_note':'INTERNAL REVIEW ONLY — scope tested','confirm':'publish-local-demo'})
        self.assertEqual(status,201)
        self.switch('partner')
        status,r,_=self.request('/api/results?product=' + candidate['product'])
        self.assertTrue(r['approved_statements']);self.assertNotIn('review_note',r['approved_statements'][0])
        self.assertEqual(self.request('/api/admin/revoke',{'id':a['id']})[0],403)
        self.switch('admin')
        self.assertEqual(self.request('/api/admin/revoke',{'id':a['id']})[0],200)
        self.assertEqual(self.guide.approved_statements(),[])

    def test_approvals_expire_on_new_version(self):
        self.switch('admin')
        _,admin,_=self.request('/api/admin')
        candidate=admin['candidates'][0]
        _,a,_=self.request('/api/admin/approvals',{'ref':candidate['ref'],'review_note':'Verified test scope in isolated demo','confirm':'publish-local-demo'})
        new=copy.deepcopy(self.guide.data);new['version']='new-snapshot'
        self.assertEqual(Guide(new).approved_statements(),[])
        self.request('/api/admin/revoke',{'id':a['id']})

if __name__ == '__main__':
    unittest.main(verbosity=2)
