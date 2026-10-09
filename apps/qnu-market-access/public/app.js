'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let session, catalog, result, activeTab = 'requirements', filter = 'all', search = '', requestId = 0, evidenceRequestId = 0;
const selectors = [];
function searchableSelector(inputId, listId, values, labelFor = value => value) {
  const input = $(inputId), list = $(listId), wrapper = input.parentElement;
  const toggle = wrapper.querySelector('.combo-toggle');
  let matches = [], highlighted = -1;
  function close() {
    list.hidden = true;
    input.setAttribute('aria-expanded', 'false'); toggle.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant'); highlighted = -1;
  }
  function highlight(index) {
    highlighted = index;
    list.querySelectorAll('[role="option"]').forEach((option, i) => option.classList.toggle('highlighted', i === index));
    if (index >= 0) {
      input.setAttribute('aria-activedescendant', `${listId}-${index}`);
      list.children[index].scrollIntoView({block:'nearest'});
    } else input.removeAttribute('aria-activedescendant');
  }
  function choose(value) {
    input.value = labelFor(value); input.dataset.value = value; close(); input.focus(); close();
    input.dispatchEvent(new Event('change', {bubbles:true}));
  }
  function open(term = '') {
    selectors.forEach(selector => selector.close());
    matches = values().filter(value => value.toLowerCase().includes(term.toLowerCase()));
    list.innerHTML = matches.map((value, i) => `<button type="button" class="combo-option" role="option" tabindex="-1" id="${listId}-${i}" aria-selected="${value === (input.readOnly ? input.dataset.value : input.value)}">${esc(labelFor(value))}</button>`).join('') || `<div class="combo-empty">${inputId === 'country' ? 'No matching countries. Unlisted markets can still be checked.' : 'No matching products. Choose an available product.'}</div>`;
    list.querySelectorAll('[role="option"]').forEach((option, i) => {
      option.addEventListener('mousedown', event => event.preventDefault());
      option.addEventListener('click', () => choose(matches[i]));
    });
    list.hidden = false; input.setAttribute('aria-expanded', 'true'); toggle.setAttribute('aria-expanded', 'true');
  }
  input.addEventListener('focus', () => open());
  input.addEventListener('click', () => open());
  input.addEventListener('input', () => open(input.value));
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape') { close(); event.preventDefault(); }
    if (event.key === 'Tab') close();
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault(); if (list.hidden) open();
      if (matches.length) highlight(highlighted < 0 ? (event.key === 'ArrowDown' ? 0 : matches.length - 1) : (highlighted + (event.key === 'ArrowDown' ? 1 : -1) + matches.length) % matches.length);
    }
    if (event.key === 'Enter' && !list.hidden && highlighted >= 0) { event.preventDefault(); choose(matches[highlighted]); }
  });
  toggle.addEventListener('mousedown', event => event.preventDefault());
  toggle.addEventListener('click', () => { if (list.hidden) { input.focus(); open(); } else close(); });
  document.addEventListener('pointerdown', event => { if (!wrapper.contains(event.target)) close(); });
  wrapper.addEventListener('focusout', event => { if (!wrapper.contains(event.relatedTarget)) close(); });
  selectors.push({close});
}
async function api(path, body) {
  const options = body ? {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf}, body:JSON.stringify(body)} : {};
  const response = await fetch(path, {...options, cache:'no-store'});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}
function showError(err) { $('error').textContent = err.message; $('error').hidden = false; }
function readerText(value) {
  const names = {'Matrix':'the requirements source','Gap':'the gap assessment','QShield 2.0':'the module assessment','Country notes':'the market notes','Sources':'the cited source','Open questions':'the research questions'};
  return String(value ?? '').replace(/\b(Matrix|Gap|QShield 2\.0|Country notes|Sources|Open questions)![A-Z]+\d+(?::[A-Z]+\d+)?/g, (_, sheet) => names[sheet]).replace(/\bGap row \d+/g, 'the gap assessment').replace(/\. the /g, '. The ').replace(/\s*\[(?:M|E|R|U)\/[HML]\]/g, '').replace(/\s*\(S\d+(?:\s*[,;]\s*S\d+)*\)/g, '');
}
function sourceDetails(references = [], sources = [], notes = []) {
  const data = {refs:references.flatMap(ref => ref.split(/,\s*(?=(?:Matrix|Gap|QShield 2\.0|Country notes|Sources|Open questions)!)/)), sources, notes};
  return data.refs.length || data.sources.length || data.notes.length ? `<button class="evidence-link" data-details="${esc(JSON.stringify(data))}">Source details</button>` : '';
}
function refs(list) { return sourceDetails(list); }
function conditionText(row) { return [...new Set([row.applicability, row.condition, row.qualification].filter(Boolean).map(readerText))].join(' · '); }
function ownerMeta(row) { return row.owner && !row.owner.startsWith('Not assigned in source') ? `<span>Responsibility: ${esc(row.owner)}</span>` : ''; }
function card(text, meta = '', classes = '') { return `<article class="requirement ${classes}"><p>${esc(readerText(text))}</p><div class="requirement-footer">${meta}</div></article>`; }
function bindEvidence(root) {
  root.querySelectorAll('[data-details]').forEach(button => button.addEventListener('click', () => evidence(JSON.parse(button.dataset.details))));
}
async function evidence(details) {
  const id = ++evidenceRequestId, csrf = session.csrf;
  $('evidence-content').textContent = 'Loading source details…';
  $('evidence-dialog').showModal();
  const records = await Promise.all([
    ...details.refs.map(async ref => {
      if (!/^[^!]+![A-Z]+\d+$/.test(ref) && !ref.startsWith('Internal CSV row ')) return ref;
      try {
        const data = await api('/api/evidence?ref=' + encodeURIComponent(ref));
        return data.ref + '\n' + data.text + (data.classification ? '\n' + data.classification : '') + '\nVersion: ' + data.version;
      } catch (err) { return 'Source detail unavailable: ' + err.message; }
    }),
    ...details.sources.map(async source => {
      try { return JSON.stringify(await api('/api/sources/' + encodeURIComponent(source)), null, 2); }
      catch (err) { return 'Source detail unavailable: ' + err.message; }
    })
  ]);
  if (id === evidenceRequestId && csrf === session.csrf && $('evidence-dialog').open) $('evidence-content').textContent = [...details.notes, ...records].join('\n\n');
}
function contextFields() {
  const product = $('product').value;
  const shield = product === 'QShield 2.0';
  const bundle = catalog.bundled_products.includes(product);
  const hardware = catalog.hardware_products.includes(product) || bundle;
  $('module-field').hidden = !shield;
  $('deployment-field').hidden = hardware && !bundle;
  $('hardware-field').hidden = hardware;
  $('bundle-notice').hidden = !bundle;
  $('bundle-notice').textContent = `${product} is assumed to include a QRNG appliance. Confirm the configuration; software and hardware requirements both apply.`;
  $('radio-field').hidden = !hardware && $('hardware').value !== 'yes';
  $('hardware-help').textContent = shield ? 'Entropy with QRNG adds the QRNG column. Other appliances need a separate product brief.' : 'Select the actual appliance product separately; coverage does not transfer from this software row.';
  contextDefaults();
}
function contextDefaults() {
  const settings = [$('deployment-field').hidden ? 'Appliance' : $('deployment').selectedOptions[0].textContent];
  if ($('export_india').value === 'yes') settings.push('India exports included');
  if ($('sector').value !== 'unspecified') settings.push($('sector').selectedOptions[0].textContent);
  if (!$('hardware-field').hidden && $('hardware').value === 'yes') settings.push('Hardware included');
  if (!$('radio-field').hidden && $('radio').value === 'yes') settings.push('Radio present');
  $('context-defaults').textContent = settings.join(' · ');
}
function query() {
  const data = Object.fromEntries(new FormData($('guide-form')));
  data.country = data.country.trim(); data.product = data.product.trim();
  data.segment = $('segment').dataset.value;
  data.modules = [...document.querySelectorAll('[name="module"]:checked')].map(x => x.value).join('|');
  delete data.module;
  if ($('hardware-field').hidden) data.hardware = 'no';
  if ($('radio-field').hidden) data.radio = 'no';
  if ($('deployment-field').hidden) data.deployment = 'on-prem';
  return new URLSearchParams(data).toString();
}
function resultQuery() {
  const q = {...result.query, modules: result.query.modules.join('|')};
  return new URLSearchParams(q).toString();
}
async function buildBrief() {
  const id = ++requestId;
  $('run').disabled = true; $('error').hidden = true; $('loading').hidden = false;
  $('result-content').hidden = true;
  try {
    const data = await api('/api/results?' + query());
    if (id !== requestId) return;
    result = data; filter = 'all'; search = ''; renderResult();
    $('result-content').hidden = false;
  } catch (err) { if (id === requestId) showError(err); }
  finally { if (id === requestId) { $('loading').hidden = true; $('run').disabled = false; } }
}
function renderResult() {
  $('classification').textContent = result.role === 'partner' ? 'PARTNER REQUIREMENTS VIEW' : 'INTERNAL ONLY';
  $('result-title').textContent = result.query.country;
  $('result-product').textContent = result.query.product;
  $('result-context').textContent = result.query.segment + ' · ' + result.query.deployment + (result.query.product === 'QShield 2.0' ? ' · ' + result.query.modules.join(', ') : '');
  const s = result.summary;
  $('assessment').className = 'assessment status-' + s.assessment;
  $('assessment').innerHTML = `<span class="assessment-icon" aria-hidden="true">${{GREEN:'✓',YELLOW:'◷',RED:'!',GREY:'?',UNKNOWN:'?',NA:'—',RESTRICTED:'◇'}[s.assessment]}</span><strong>${esc(s.title)}</strong>`;
  $('summary-note').textContent = s.text;
  $('scope-summary').textContent = 'Applied: ' + result.scopes.join(' + ');
  $('stats').innerHTML = [['M','Mandatory'],['E','Buyer-expected'],['R','Recommended'],['U','Qualifications']].map(([k,t]) => `<div class="stat"><strong>${result.counts[k]}</strong><span>${t}</span></div>`).join('');
  $('assumption-count').textContent = result.assumptions.length + result.caveats.length;
  $('assumption-body').innerHTML = result.assumptions.map(a => `<article><p>${esc(readerText(a.text))}</p><small>${esc(a.kind)} · ${sourceDetails([a.ref], [], [a.text])}</small></article>`).join('') + result.caveats.map(c => `<article><p>${esc(readerText(c))}</p><small>Application review — uncertainty remains</small></article>`).join('');
  bindEvidence($('assumption-body'));
  const dates = result.research_dates;
  document.querySelector('.source-notice p').textContent = `Matrix research: ${dates.Matrix} · QShield: ${dates['QShield 2.0']} · assumptions updated: ${dates.assumption_update}. Ingestion is not independent regulatory verification.`;
  $('snapshot-date').textContent = 'Source snapshot received ' + dates.received;
  renderTab();
}
function renderRequirements() {
  const panel = $('tab-content');
  panel.innerHTML = `<h2 class="visually-hidden">Requirements & qualifications</h2><div class="list-tools"><div class="filters">${[['all','All'],['M','Mandatory'],['E','Buyer-expected'],['R','Recommended'],['U','Qualifications']].map(([k,t]) => `<button class="filter" data-filter="${k}" aria-pressed="${filter === k}">${t}</button>`).join('')}</div><label class="visually-hidden" for="requirement-search">Filter requirement text</label><input class="list-search" id="requirement-search" type="search" placeholder="Filter requirements…" value="${esc(search)}"></div><div id="requirements-list"></div>`;
  function list() {
    const rows = result.requirements.filter(r => (filter === 'all' || r.kind === filter) && (r.text + r.owner + r.refs.join(' ') + r.sources.join(' ')).toLowerCase().includes(search.toLowerCase()));
    $('requirements-list').innerHTML = rows.map(r => {
      return `<article class="requirement ${r.applicability.startsWith('Not applicable') ? 'muted-item' : ''}"><div class="requirement-head"><span class="badge kind-${r.kind}">${esc(r.category)}</span><span class="badge">Confidence ${esc(r.confidence)}</span><span class="number">${esc(r.id)}</span></div><p>${esc(readerText(r.text))}</p><div class="requirement-footer">${ownerMeta(r)}${sourceDetails(r.refs, r.sources)}</div>${r.applicability !== 'Relevant' || r.qualification ? `<div class="conditional">${esc(conditionText(r))}</div>` : ''}</article>`;
    }).join('') || '<div class="empty">No requirements match this view. Missing data is not confirmation of compliance.</div>';
    bindEvidence($('requirements-list'));
  }
  $('requirement-search').addEventListener('input', event => { search = event.target.value; list(); });
  panel.querySelectorAll('[data-filter]').forEach(b => b.addEventListener('click', () => { filter = b.dataset.filter; panel.querySelectorAll('[data-filter]').forEach(x => x.setAttribute('aria-pressed', x.dataset.filter === filter)); list(); }));
  list();
}
function renderTab() {
  document.querySelectorAll('[data-tab]').forEach(b => { const active = b.dataset.tab === activeTab; b.setAttribute('aria-selected', active); b.tabIndex = active ? 0 : -1; });
  $('tab-content').setAttribute('aria-labelledby','tab-' + activeTab);
  if (activeTab === 'requirements') return renderRequirements();
  const panel = $('tab-content');
  if (activeTab === 'actions') {
    panel.innerHTML = '<h2>Before selling or deploying</h2><p class="section-intro">Confirm which mandatory requirements apply and record how each will be met. Responsibility is shown where specified.</p>' + result.actions.map((r,i) => card(r.text, `<span>Check ${i+1}</span>${ownerMeta(r)}${sourceDetails([r.ref], [], [r.text])}`)).join('');
  } else if (activeTab === 'status') {
    panel.innerHTML = '<h2>QNu status & source-reported gaps</h2><p class="section-intro">' + esc(result.certification_notice) + '</p>';
    if (result.role === 'partner') {
      panel.innerHTML += '<div class="empty">Internal certification status, dates, roadmap and gap assessments are withheld. Partner approval is empty by default.</div>' + result.approved_statements.map(r => card(r.text, esc(r.scope))).join('');
    } else {
      panel.innerHTML += result.conflicts.map(r => card(r.text, refs(r.refs), 'conflict')).join('');
      panel.innerHTML += '<h3>Source-reported QNu status</h3>' + result.status_assertions.map(r => card(r.text, refs([r.ref]))).join('');
      panel.innerHTML += '<h3>Certification / evaluation matrix · Internal Only</h3>' + result.certifications.map(r => `<article class="requirement certification"><div class="requirement-head"><span class="badge kind-E">${esc(r.status === '-' ? 'Not applicable in source' : r.status)}</span><span class="number">${esc(r.product)}</span></div><h3>${esc(r.category)}</h3><p>Compliant? ${esc(r.compliant)} · Completion / planned date: ${esc(r.date)}</p><p>${esc(readerText(r.remarks))}</p><div class="requirement-footer">${sourceDetails([r.ref], [], ['Effective date not stated in the certification record.'])}</div></article>`).join('');
      panel.innerHTML += '<h3>Gap assessments & module verdicts</h3>' + result.gaps.map(r => card(r.text, `<span>Assessment: ${esc(r.verdict)}</span>${sourceDetails([r.ref], [], [r.text])}`)).join('');
    }
  } else if (activeTab === 'sources') {
    panel.innerHTML = '<h2>Supporting sources</h2><p class="section-intro">Links, confidence H/M/L and verifier statuses come from the supplied research. Referenced external files were not supplied or fetched.</p>';
    panel.innerHTML += result.sources.map(r => {
      if (r.restricted) return card(r.claim, sourceDetails([], [r.id]));
      let link = esc(r.url);
      try { if (['http:','https:'].includes(new URL(r.url).protocol)) link = `<a href="${esc(r.url)}" target="_blank" rel="noreferrer">${esc(r.url)} ↗</a>`; } catch (_) {}
      return `<article class="requirement source-card"><h3>${esc(r.publisher)} <span class="badge">${esc(r.type)}</span></h3><p>${esc(readerText(r.claim))}</p><p>${link}</p><small>Checked ${esc(r.checked)} · confidence ${esc(r.confidence)} · ${esc(readerText(r.verifier))}</small><div class="requirement-footer">${sourceDetails([], [r.id])}</div></article>`;
    }).join('') || '<div class="empty">No cited sources are available in this view.</div>';
    panel.innerHTML += '<h2>Country context</h2>' + result.notes.map(r => card(r.text, `<span>${esc(r.heading)}</span>${refs([r.ref])}`)).join('');
    if (result.role !== 'partner') {
      const open = result.questions.filter(r => r.state === 'open');
      const resolved = result.questions.filter(r => r.state === 'resolved');
      panel.innerHTML += `<h2>Open questions <span class="badge">${open.length} open · ${resolved.length} resolved</span></h2>` + result.questions.map(r => card(r.text, `<span>${esc(r.state)} · Source owner: ${esc(readerText(r.owner))}<br>${esc(readerText(r.impact))}</span>${sourceDetails([r.ref], [], [r.text])}`)).join('');
    }
  }
  bindEvidence(panel);
}
async function governance() {
  $('guide-view').hidden = true; $('data-view').hidden = false;
  $('guide-nav').classList.remove('active'); $('data-nav').classList.add('active');
  const d = catalog;
  let html = `<div class="data-card"><h2>Supplied workbook · October 2026</h2><p>${esc(d.notice)}</p><p><strong>${d.scope_count} country, regional and export scopes</strong> in the Matrix · 8 product columns · QShield has its own module coverage.</p><p>Active dataset <code>${esc(d.version)}</code></p><p>Originals are preserved. New imports stage as immutable snapshots; a reviewer explicitly activates them. Source assertions and achieved/planned certifications remain separate. Partner approvals expire when the dataset version changes.</p></div>`;
  if (session.role !== 'partner') {
    html += `<div class="data-card"><h2>Extraction coverage</h2><table><thead><tr><th>Sheet</th><th>Populated cells</th><th>Range</th></tr></thead><tbody>${Object.entries(d.coverage).filter(([,v]) => typeof v === 'object' && v?.nonempty_cells).map(([sn,v]) => `<tr><td>${esc(sn)}</td><td>${v.nonempty_cells}</td><td>${esc(v.dimension)}</td></tr>`).join('')}</tbody></table><p>${d.coverage.total_cells.toLocaleString()} cells · ${d.coverage.source_records} source records · ${d.coverage.question_records} questions · ${d.coverage.certification_records} product/category certification records · 0 unresolved source IDs.</p><a href="/api/download?file=workbook">Download original workbook</a> · <a href="/api/download?file=status-csv">Download Internal Only CSV</a></div>`;
  } else html += '<div class="data-card"><h2>Partner permissions</h2><p>Requirements and permitted source details are projected by the server. Internal CSV, raw mixed-content evidence, roadmaps, gap assessments and internal question records are excluded from APIs and downloads. Only reviewed, version-bound statements can be shared.</p></div>';
  $('data-content').innerHTML = html;
  if (session.role === 'admin') await renderAdmin();
}
async function renderAdmin() {
  const data = await api('/api/admin');
  const container = document.createElement('div');
  container.innerHTML = `<div class="data-card"><h2>Invitation drafts</h2><p>Prepare a local draft. This prototype sends no email and creates no production account.</p><form id="invite-form" class="admin-form"><label for="invite-email">Employee or partner email</label><input id="invite-email" type="email" required><label for="invite-role">Intended role</label><select id="invite-role"><option value="partner">Authorised partner</option><option value="employee">Employee</option></select><button class="primary" type="submit">Save local invitation draft</button></form><div id="invite-list">${data.invitations.map(r => card(r.email,esc(r.role + ' · ' + r.state))).join('')}</div></div><div class="data-card"><h2>Approve a partner statement</h2><p>Explicit approval affects this local demo only. Review original evidence, certificate scope and wording first. Dates and roadmap do not transfer into the approved statement.</p><form id="approval-form" class="admin-form"><label for="approval-ref">Internal assertion to review</label><select id="approval-ref">${data.candidates.map(r => `<option value="${esc(r.ref)}">${esc(r.product + ' / ' + r.category + ' / ' + r.status)}</option>`).join('')}</select><div id="approval-evidence"></div><label for="review-note">Review note: certificate scope and approved wording</label><textarea id="review-note" required minlength="15"></textarea><label class="consent"><input type="checkbox" id="publish-consent" required> I explicitly approve this single source assertion for the local partner demo. This is not external publication or certificate verification.</label><button class="primary" type="submit">Approve & publish in local demo</button></form><div id="approval-list">${data.approvals.map(a => card(a.text,`<span>${esc(a.scope)}</span><button class="text-button" data-revoke="${esc(a.id)}">Revoke approval</button>`)).join('')}</div><p id="admin-message" role="status"></p></div>`;
  $('data-content').appendChild(container);
  function preview() {
    const row = data.candidates.find(r => r.ref === $('approval-ref').value);
    $('approval-evidence').innerHTML = `<article class="requirement"><p>${esc(row.category)} · Compliant? ${esc(row.compliant)} · Status ${esc(row.status)} · Date ${esc(row.date)}</p><p>${esc(row.remarks)}</p><small>${esc(row.ref)} · Internal Only · effective date not stated</small></article>`;
  }
  $('approval-ref').addEventListener('change',preview); preview();
  $('invite-form').addEventListener('submit', async event => { event.preventDefault(); try { const r = await api('/api/admin/invitations',{email:$('invite-email').value,role:$('invite-role').value}); $('invite-list').insertAdjacentHTML('beforeend',card(r.email,esc(r.state))); $('invite-form').reset(); } catch(err) { $('admin-message').textContent = err.message; } });
  $('approval-form').addEventListener('submit', async event => { event.preventDefault(); try { await api('/api/admin/approvals',{ref:$('approval-ref').value,review_note:$('review-note').value,confirm:'publish-local-demo'}); await governance(); } catch(err) { $('admin-message').textContent = err.message; } });
  container.querySelectorAll('[data-revoke]').forEach(b => b.addEventListener('click',async () => { try { await api('/api/admin/revoke',{id:b.dataset.revoke}); await governance(); } catch(err) { $('admin-message').textContent=err.message; } }));
}
function guideView() { $('guide-view').hidden=false; $('data-view').hidden=true; $('guide-nav').classList.add('active'); $('data-nav').classList.remove('active'); }
async function init() {
  try {
    session = await api('/api/session');
    catalog = await api('/api/catalog');
    $('demo-role').value = session.role;
    searchableSelector('country', 'countries', () => catalog.countries);
    searchableSelector('product', 'products', () => catalog.products);
    searchableSelector('segment', 'segments', () => ['Commercial', 'Government/Defence/CI'], value => value === 'Commercial' ? value : 'Government / Defence / CI');
    $('module-options').innerHTML = catalog.modules.map((m,i) => `<label><input type="checkbox" name="module" value="${esc(m)}" ${i === 0 ? 'checked' : ''}>${esc(m)}</label>`).join('');
    contextFields(); await buildBrief();
  } catch(err) { $('loading').hidden=true; showError(err); }
}
$('guide-form').addEventListener('submit',event => { event.preventDefault(); buildBrief(); });
$('product').addEventListener('input',() => catalog && contextFields());
$('product').addEventListener('change',() => catalog && contextFields());
$('hardware').addEventListener('change',() => catalog && contextFields());
$('context-settings').addEventListener('change', contextDefaults);
$('demo-role').addEventListener('change',async event => {
  ++evidenceRequestId;
  selectors.forEach(selector => selector.close());
  ++requestId; result=null; $('result-content').hidden=true; $('tab-content').innerHTML=''; $('data-content').innerHTML=''; $('assumption-body').innerHTML=''; $('evidence-content').textContent=''; if ($('evidence-dialog').open) $('evidence-dialog').close();
  try { session=await api('/api/demo-role',{role:event.target.value}); catalog=await api('/api/catalog'); guideView(); await buildBrief(); } catch(err) { event.target.value=session.role; showError(err); }
});
document.querySelectorAll('[data-tab]').forEach((b,i,buttons) => {
  b.addEventListener('click',() => { activeTab=b.dataset.tab; renderTab(); });
  b.addEventListener('keydown',event => { if (['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) { event.preventDefault(); const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(i+(event.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length; activeTab=buttons[next].dataset.tab; renderTab(); buttons[next].focus(); } });
});
$('print-brief').addEventListener('click',() => result && window.open('/brief?' + resultQuery(),'_blank','noopener'));
$('json-export').addEventListener('click',() => result && (window.location.href='/api/export?' + resultQuery()));
$('close-dialog').addEventListener('click',() => { ++evidenceRequestId; $('evidence-dialog').close(); });
$('data-nav').addEventListener('click',() => governance().catch(showError));
$('guide-nav').addEventListener('click',guideView);
init();
