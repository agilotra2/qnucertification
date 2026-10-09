"""Server-generated, role-projected print document; no client-side hidden data."""
from html import escape
import json
import re
from urllib.parse import urlparse

def reader_text(value):
    names = {'Matrix': 'the requirements source', 'Gap': 'the gap assessment',
             'QShield 2.0': 'the module assessment', 'Country notes': 'the market notes',
             'Sources': 'the cited source', 'Open questions': 'the research questions'}
    text = re.sub(r'\b(Matrix|Gap|QShield 2\.0|Country notes|Sources|Open questions)![A-Z]+\d+(?::[A-Z]+\d+)?',
                  lambda match: names[match.group(1)], str(value))
    text = re.sub(r'\bGap row \d+', 'the gap assessment', text).replace('. the ', '. The ')
    text = re.sub(r'\s*\[(?:M|E|R|U)/[HML]\]', '', text)
    return re.sub(r'\s*\(S\d+(?:\s*[,;]\s*S\d+)*\)', '', text)

def brief(result):
    e = lambda x: escape(str(x))
    q = result['query']
    dates = result['research_dates']
    classification = 'PARTNER REQUIREMENTS BRIEF' if result['role'] == 'partner' else 'INTERNAL ONLY — EMPLOYEE BRIEF'
    def section(title, records, render):
        return '<section><h2>' + e(title) + '</h2>' + (''.join(render(r) for r in records) if records else '<p>No records in this view. Absence is not confirmation of compliance.</p>') + '</section>'
    def item(r):
        return '<article><p>' + e(reader_text(r['text'])) + '</p><small>' + owner_note(r) + '</small>' + source_details(r) + '</article>'
    def owner_note(r):
        value = r.get('owner', '')
        return e(value) + ' · ' if value and not value.startswith('Not assigned in source') else ''
    def source_details(r):
        ref = r.get('ref', ', '.join(r.get('refs', [])))
        raw = r.get('text', r.get('remarks', ''))
        return '<details class="source-details"><summary>Source details</summary><small>' + e(ref) + '</small><p>' + e(raw) + '</p></details>' if ref else ''
    body = '<p class="label">' + classification + '</p><h1>QNu Market Access Guide</h1><h2>' + e(q['country']) + ' / ' + e(q['product']) + '</h2><p>' + e(q['segment']) + ' · ' + e(', '.join(q['modules']) if q['product'] == 'QShield 2.0' else q['deployment']) + '</p><div class="notice"><strong>' + e(result['summary']['title']) + '</strong><p>' + e(result['summary']['text']) + '</p><p>' + e(result['notice']) + '</p></div><p>Research: ' + e(dates['Matrix']) + ' · QShield research: ' + e(dates['QShield 2.0']) + ' · assumptions updated: ' + e(dates['assumption_update']) + '.</p><details class="source-details"><summary>Source details</summary><small>Dataset ' + e(result['version']) + '. Certification record effective date: not stated.</small></details><p>Applied scopes: ' + e(', '.join(result['scopes'])) + '</p>'
    body += section('Assumptions', result['assumptions'], item)
    body += section('Gaps and qualifications', [{'text': x} for x in result['caveats']], item)
    for kind, title in [('M', 'Mandatory requirements — source classifications'), ('E', 'Buyer-expected requirements'), ('R', 'Recommended measures'), ('U', 'Other qualifications / unknown')]:
        body += section(title, [r for r in result['requirements'] if r['kind'] == kind], lambda r: '<article><p>' + e(reader_text(r['text'])) + '</p><small>' + e(reader_text(r['applicability'] + ': ' + r['condition'])) + '<br>' + owner_note(r) + 'Confidence: ' + e(r['confidence']) + '</small>' + source_details(r) + '</article>')
    body += section('Actions before selling / deploying', result['actions'], item)
    body += '<p>' + e(result['certification_notice']) + '</p>'
    body += section('QNu approved partner statements' if result['role'] == 'partner' else 'Internal certification assertions', result['approved_statements'] if result['role'] == 'partner' else result['certifications'], lambda r: item(r) if 'text' in r else '<article><strong>' + e(r['product'] + ' — ' + r['category']) + '</strong><p>Compliant? ' + e(r['compliant']) + ' · Status: ' + e(r['status']) + ' · Date: ' + e(r['date']) + '</p><p>' + e(reader_text(r['remarks'])) + '</p>' + source_details(r) + '</article>')
    body += section('Source-reported gap assessments', result['gaps'], item)
    body += section('Conflicting dates', result['conflicts'], item)
    body += section('Open and resolved source questions', result['questions'], lambda r: '<article><strong>' + e(r['state']) + '</strong>' + item(r) + '</article>')
    body += section('Country context', result['notes'], lambda r: '<article><strong>' + e(r['heading']) + '</strong>' + item(r) + '</article>')
    def source(r):
        if r.get('restricted'):
            return '<article>' + e(r['id'] + ' — ' + r['claim']) + '</article>'
        url = r['url']
        link = '<a href="' + escape(url, quote=True) + '">' + e(url) + '</a>' if urlparse(url).scheme in ('http', 'https') else e(url)
        return '<article><strong>' + e(r['publisher']) + '</strong><p>' + e(reader_text(r['claim'])) + '</p><p>' + link + '</p><small>' + e('Checked: ' + r['checked'] + ' · confidence: ' + r['confidence'] + ' · verifier: ' + reader_text(r['verifier'])) + '</small>' + source_details({**r, 'text':r['claim']}) + '</article>'
    body += section('Supporting sources (not independently reverified)', result['sources'], source)
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + e(q['country'] + ' — QNu market access brief') + '</title><link rel="stylesheet" href="/brief.css"></head><body><nav><button id="print">Print / save as PDF</button><a href="/">Back to guide</a></nav><main>' + body + '</main><script src="/print.js"></script></body></html>'
