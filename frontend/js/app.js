// ── STATE ───────────────────────────────────────────────
let config = {}, testcases = [], aiGeneratedCases = [];
let imgBase64 = null, imgMediaType = 'image/png';

const API = () => document.getElementById('apiBase').value.replace(/\/$/, '');

// ── BACKEND PING ────────────────────────────────────────
async function pingBackend() {
  const dot = document.getElementById('statusDot'), txt = document.getElementById('statusText');
  dot.className = 'dot'; txt.textContent = 'Checking…';
  try {
    const r = await fetch(`${API()}/health`);
    if (r.ok) { dot.className='dot on'; txt.textContent='Backend connected'; showToast('✅ Backend reachable','ok'); }
    else throw new Error();
  } catch { dot.className='dot err'; txt.textContent='Backend offline'; showToast('❌ Cannot reach backend','error'); }
}

// ── INIT ────────────────────────────────────────────────
window.addEventListener('load', () => { pingBackend(); refreshProfiles(); });
document.getElementById('jsonEditor').addEventListener('input', validateJSONLive);

// ── NAVIGATION ──────────────────────────────────────────
function goTo(n) {
  if (n>0 && n<4 && !config.org) { showToast('⚠️ Save configuration first','warn'); return; }
  if ((n===2||n===3) && !testcases.length) { showToast('⚠️ Load test cases first','warn'); return; }
  document.querySelectorAll('.page').forEach((p,i) => p.classList.toggle('active', i===n));
  for(let i=0;i<6;i++){
    const si=document.getElementById(`step${i}`), sn=document.getElementById(`snum${i}`);
    if(!si) continue;
    si.classList.remove('active','done');
    if(i===n) si.classList.add('active');
    else if(i<n && i<4) si.classList.add('done');
    if(sn){
      if(i>=4) sn.textContent = i===4?'🤖':'📜';
      else if(si.classList.contains('done')) sn.textContent='✓';
      else sn.textContent = i+1;
    }
  }
  if(n===3) fillUploadSummary();
  if(n===5) loadHistory();
}

// ── CONFIG ──────────────────────────────────────────────
function getFormConfig(){
  return {
    org: document.getElementById('cfgOrg').value.trim(),
    project: document.getElementById('cfgProject').value.trim(),
    pat: document.getElementById('cfgPAT').value.trim(),
    plan_id: parseInt(document.getElementById('cfgPlanId').value)||0,
    story_id: parseInt(document.getElementById('cfgStoryId').value)||0,
    parent_suite_id: parseInt(document.getElementById('cfgParentId').value)||null,
    parent_suite_name: document.getElementById('cfgParentName').value.trim()||null,
    desired_state: document.getElementById('cfgState').value,
    tags: document.getElementById('cfgTags').value.trim(),
  };
}

function saveConfig(){
  const c=getFormConfig();
  if(!c.org||!c.project||!c.pat||!c.plan_id||!c.story_id){ showToast('❌ Fill all required fields','error'); return; }
  config=c; showToast('✅ Configuration saved','ok'); goTo(1);
}

function loadDemo(){
  document.getElementById('cfgOrg').value='ViewpointVSO';
  document.getElementById('cfgProject').value='Platform Apps';
  document.getElementById('cfgPAT').value='replace-with-your-pat';
  document.getElementById('cfgPlanId').value='624343';
  document.getElementById('cfgStoryId').value='678700';
  document.getElementById('cfgParentId').value='685758';
  document.getElementById('cfgParentName').value='E2E Messenger Service';
  document.getElementById('cfgTags').value='QA Testing; CoreServices';
  showToast('📋 Demo values loaded','info');
}

async function validateConnection(){
  const el=document.getElementById('connResult');
  el.style.color='var(--muted)'; el.textContent='⏳ Testing…';
  try {
    const r=await fetch(`${API()}/api/config/validate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'_test',config:getFormConfig()})});
    const d=await r.json();
    if(r.ok&&d.connected){ el.style.color='var(--success)'; el.textContent=`✅ Connected — ${d.suite_count} suites in plan ${d.plan_id}`; showToast('✅ Connection OK','ok'); }
    else { el.style.color='var(--danger)'; el.textContent=`❌ ${d.detail||JSON.stringify(d)}`; }
  } catch(e){ el.style.color='var(--danger)'; el.textContent=`❌ Backend error: ${e.message}`; }
}

// ── PROFILES ────────────────────────────────────────────
async function refreshProfiles(){
  try {
    const r=await fetch(`${API()}/api/config/profiles`);
    if(!r.ok) return;
    const profiles=await r.json();
    const sel=document.getElementById('profileSelect');
    sel.innerHTML='<option value="">— select a profile —</option>';
    profiles.forEach(p=>{ const o=document.createElement('option'); o.value=p.name; o.textContent=p.name; sel.appendChild(o); });
  } catch {}
}

async function loadProfileOption(){
  const name=document.getElementById('profileSelect').value;
  document.getElementById('btnDeleteProfile').style.display = name ? 'inline-flex' : 'none';
  if(!name) return;
  try {
    const r=await fetch(`${API()}/api/config/profiles/${encodeURIComponent(name)}`);
    const p=await r.json();
    const d=p.data;
    document.getElementById('cfgOrg').value       = d.org||'';
    document.getElementById('cfgProject').value   = d.project||'';
    document.getElementById('cfgPAT').value        = '';
    document.getElementById('cfgPlanId').value     = d.plan_id||'';
    document.getElementById('cfgStoryId').value    = d.story_id||'';
    document.getElementById('cfgParentId').value   = d.parent_suite_id||'';
    document.getElementById('cfgParentName').value = d.parent_suite_name||'';
    document.getElementById('cfgState').value      = d.desired_state||'Ready';
    document.getElementById('cfgTags').value       = d.tags||'';
    const msg=document.getElementById('profileMsg');
    msg.style.display='block'; msg.textContent=`✅ "${name}" loaded — enter your PAT to continue.`;
    showToast(`📂 Profile "${name}" loaded`,'info');
  } catch { showToast('❌ Failed to load profile','error'); }
}

function openSaveProfileModal(){ document.getElementById('saveProfileModal').classList.add('open'); }
function closeModal(id){ document.getElementById(id).classList.remove('open'); }

async function saveProfile(){
  const name=document.getElementById('profileNameInput').value.trim();
  if(!name){ showToast('❌ Enter a profile name','error'); return; }
  const c=getFormConfig();
  if(!c.org||!c.project){ showToast('❌ Fill org & project first','error'); return; }
  try {
    const r=await fetch(`${API()}/api/config/profiles`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,config:c})});
    if(r.ok){ closeModal('saveProfileModal'); refreshProfiles(); showToast(`✅ Profile "${name}" saved`,'ok'); }
    else throw new Error();
  } catch { showToast('❌ Failed to save profile','error'); }
}

async function deleteProfile(){
  const name=document.getElementById('profileSelect').value;
  if(!name||!confirm(`Delete profile "${name}"?`)) return;
  try {
    const r=await fetch(`${API()}/api/config/profiles/${encodeURIComponent(name)}`,{method:'DELETE'});
    if(r.ok){ refreshProfiles(); document.getElementById('btnDeleteProfile').style.display='none'; showToast(`🗑 "${name}" deleted`,'warn'); }
  } catch { showToast('❌ Failed to delete','error'); }
}

// ── INPUT MODE SWITCH (Paste JSON / AI Generator) ───────
function switchInputMode(mode){
  const pastePane = document.getElementById('inputModePaste');
  const aiPane = document.getElementById('inputModeAI');
  const tabPaste = document.getElementById('modeTabPaste');
  const tabAI = document.getElementById('modeTabAI');
  if(mode==='paste'){
    aiPane.style.display='none'; pastePane.style.display='';
    tabAI.classList.remove('active'); tabPaste.classList.add('active');
  } else {
    aiPane.style.display=''; pastePane.style.display='none';
    tabAI.classList.add('active'); tabPaste.classList.remove('active');
  }
}

// ── JSON EDITOR ─────────────────────────────────────────
function validateJSONLive(){
  const raw=document.getElementById('jsonEditor').value.trim();
  const badge=document.getElementById('jsonBadge'), countBadge=document.getElementById('jsonCount');
  if(!raw){ badge.className='badge badge-warn'; badge.textContent='No JSON'; countBadge.style.display='none'; testcases=[]; return; }
  try {
    const d=JSON.parse(raw);
    if(!Array.isArray(d)) throw 0;
    badge.className='badge badge-green'; badge.textContent='✓ Valid';
    countBadge.style.display='inline'; countBadge.textContent=`${d.length} case${d.length!==1?'s':''}`;
    testcases=d;
  } catch { badge.className='badge badge-red'; badge.textContent='✗ Invalid'; countBadge.style.display='none'; }
}

async function apiValidate(){
  const raw=document.getElementById('jsonEditor').value.trim();
  let parsed; try { parsed=JSON.parse(raw); } catch(e){ showToast('❌ Invalid JSON: '+e.message,'error'); return; }
  try {
    const r=await fetch(`${API()}/api/testcases/validate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({testcases:parsed})});
    const d=await r.json();
    const vb=document.getElementById('jsonValidBadge'); vb.style.display='inline';
    if(d.valid){ vb.className='badge badge-green'; vb.textContent=`✅ ${d.stats.total} cases, ${d.stats.total_steps} steps — OK`; showToast('✅ Validation passed','ok'); }
    else { vb.className='badge badge-red'; vb.textContent=`${d.stats.errors} error(s) ${d.stats.warnings} warn(s)`; showToast(`⚠️ ${d.stats.errors} errors`,'warn'); }
  } catch { showToast('❌ Validate API failed — backend running?','error'); }
}

function formatJSON(){
  try { document.getElementById('jsonEditor').value=JSON.stringify(JSON.parse(document.getElementById('jsonEditor').value.trim()),null,2); showToast('🎨 Formatted','ok'); }
  catch { showToast('❌ Invalid JSON','error'); }
}

function clearJSON(){ document.getElementById('jsonEditor').value=''; testcases=[]; validateJSONLive(); }

function loadSample(){
  const s=[
    {title:'Verify user can send a direct message',preconditions:'User logged in; Messenger enabled; contact exists',steps:[{action:'Navigate to Messenger',expected:'Contact list loads'},{action:"Tap contact's name",expected:'Chat window opens'},{action:"Type 'Hello!'",expected:'Text appears in input'},{action:'Tap Send',expected:'Message appears in chat'}]},
    {title:'Verify empty message cannot be sent',preconditions:'User in active chat window',steps:[{action:'Leave input empty',expected:'Send button disabled'},{action:'Attempt to tap Send',expected:'No message sent'}]},
    {title:'Verify message character limit',preconditions:'Chat window open',steps:[{action:'Type 500+ characters',expected:'Character counter appears'},{action:'Exceed 1000 chars',expected:'Input blocked; warning shown'}]}
  ];
  document.getElementById('jsonEditor').value=JSON.stringify(s,null,2);
  testcases=s; validateJSONLive(); showToast('📋 Sample loaded','info');
}

function switchTab(e,id){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active')); e.target.classList.add('active');
  document.getElementById('tplJson').style.display   = id==='tplJson'   ?'':'none';
  document.getElementById('tplPrompt').style.display = id==='tplPrompt' ?'':'none';
}

async function goToPreview(){
  const raw=document.getElementById('jsonEditor').value.trim();
  if(!raw){ showToast('❌ JSON is empty','error'); return; }
  try {
    const d=JSON.parse(raw);
    if(!Array.isArray(d)||!d.length) throw new Error('Empty array');
    testcases=d; await buildPreview(); goTo(2);
  } catch(e){ showToast('❌ '+e.message,'error'); }
}

// ── PREVIEW ─────────────────────────────────────────────
let selectedTC = -1;

async function buildPreview(){
  const list=document.getElementById('previewList');
  list.innerHTML='';
  let totalSteps=0;
  selectedTC=-1;

  testcases.forEach((tc,i)=>{
    const steps=tc.steps||[]; totalSteps+=steps.length;
    // Row wrapper (row + expandable detail)
    const wrapper=document.createElement('div');
    wrapper.className='preview-wrapper';
    wrapper.setAttribute('data-idx',i);

    // Clickable row
    const item=document.createElement('div');
    item.className='preview-item';
    item.innerHTML=`<div class="preview-item-num">${i+1}</div><div class="preview-item-body"><div class="preview-item-title">${esc(tc.title||'Untitled')}</div><div class="preview-item-meta">${esc(tc.preconditions||'No preconditions')}</div></div><span class="preview-chevron">▼</span>`;
    item.onclick=()=>selectTestCase(i);
    wrapper.appendChild(item);

    // Detail card (hidden by default)
    const detail=document.createElement('div');
    detail.className='preview-detail-card';
    detail.id=`previewDetail-${i}`;
    detail.style.display='none';
    wrapper.appendChild(detail);

    list.appendChild(wrapper);
  });
  document.getElementById('previewListCount').textContent=`${testcases.length} cases`;
  document.getElementById('metricTotal').textContent=testcases.length;
  document.getElementById('metricSteps').textContent=totalSteps;
  try {
    const r=await fetch(`${API()}/api/testcases/validate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({testcases})});
    const d=await r.json();
    const cnt=d.stats.errors+d.stats.warnings;
    document.getElementById('metricIssues').textContent=cnt;
    document.getElementById('metricIssues').className=`metric-value ${cnt===0?'mv-green':'mv-red'}`;
    if(cnt>0){
      document.getElementById('issuesBanner').style.display='block';
      document.getElementById('issuesList').innerHTML=d.issues.map(iss=>{
        const col=iss.level==='error'?'var(--danger)':iss.level==='warning'?'var(--warn)':'var(--muted)';
        return `<div style="color:${col}">TC #${iss.index}: ${esc(iss.message)}</div>`;
      }).join('');
    } else document.getElementById('issuesBanner').style.display='none';
  } catch { document.getElementById('metricIssues').textContent='?'; }
}

function selectTestCase(idx){
  if(selectedTC===idx){
    // Toggle close
    const panel=document.getElementById(`previewDetail-${idx}`);
    panel.style.display='none';
    document.querySelector(`.preview-wrapper[data-idx="${idx}"] .preview-item`).classList.remove('selected');
    document.querySelector(`.preview-wrapper[data-idx="${idx}"] .preview-chevron`).textContent='▼';
    selectedTC=-1;
    return;
  }
  // Close previously open
  if(selectedTC>=0){
    const prev=document.getElementById(`previewDetail-${selectedTC}`);
    if(prev) prev.style.display='none';
    const prevItem=document.querySelector(`.preview-wrapper[data-idx="${selectedTC}"] .preview-item`);
    if(prevItem) prevItem.classList.remove('selected');
    const prevChev=document.querySelector(`.preview-wrapper[data-idx="${selectedTC}"] .preview-chevron`);
    if(prevChev) prevChev.textContent='▼';
  }
  selectedTC=idx;
  // Highlight row
  document.querySelector(`.preview-wrapper[data-idx="${idx}"] .preview-item`).classList.add('selected');
  document.querySelector(`.preview-wrapper[data-idx="${idx}"] .preview-chevron`).textContent='▲';
  // Open detail below
  renderDetail(idx);
  const panel=document.getElementById(`previewDetail-${idx}`);
  panel.style.display='block';
  panel.scrollIntoView({behavior:'smooth',block:'nearest'});
}

let editingDetail = false;
let editSnapshot = null;

function renderDetail(idx){
  const tc=testcases[idx];
  const steps=tc.steps||[];
  const panel=document.getElementById(`previewDetail-${idx}`);
  editingDetail = false;
  panel.innerHTML=`
    <div class="detail-header">
      <div class="detail-num">#${idx+1}</div>
      <div class="detail-header-body">
        <div class="detail-title-text" id="tcTitle-${idx}">${esc(tc.title||'Untitled')}</div>
        <div class="detail-precond-text" id="tcPrecond-${idx}">${esc(tc.preconditions||'No preconditions')}</div>
      </div>
    </div>
    <div class="detail-steps-header">
      <div style="font-size:12px;color:var(--muted);font-weight:600">${steps.length} step${steps.length!==1?'s':''}</div>
      <div style="display:flex;gap:6px">
        <button class="btn btn-ghost btn-sm" id="btnEditTC-${idx}" onclick="toggleEditDetail(${idx})">✏️ Edit</button>
        <button class="btn btn-primary btn-sm" id="btnSaveTC-${idx}" style="display:none" onclick="saveDetailEdits(${idx})">💾 Save</button>
        <button class="btn btn-ghost btn-sm" id="btnCancelTC-${idx}" style="display:none" onclick="cancelDetailEdits(${idx})">✕ Cancel</button>
        <button class="btn btn-ghost btn-sm" id="btnAddStep-${idx}" style="display:none" onclick="addStep(${idx})">+ Add Step</button>
        <button class="btn btn-danger btn-sm" onclick="deleteTestCase(${idx})">🗑 Delete</button>
      </div>
    </div>
    <div class="table-wrap">
      <table class="steps-table">
        <thead>
          <tr><th style="width:55px">Steps</th><th>Action</th><th>Expected result</th><th style="width:40px"></th></tr>
        </thead>
        <tbody>
          ${steps.length===0?'<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:20px">No steps yet — click Edit then + Add Step</td></tr>':steps.map((s,si)=>`
            <tr class="step-table-row" data-step="${si}">
              <td class="step-num-cell">${si+1}.</td>
              <td class="step-action-cell"><span class="step-cell-text" data-tc="${idx}" data-si="${si}" data-field="action">${esc(s.action||'')}</span></td>
              <td class="step-expected-cell"><span class="step-cell-text" data-tc="${idx}" data-si="${si}" data-field="expected">${esc(s.expected||'')}</span></td>
              <td class="step-delete-cell"><button class="btn btn-danger btn-sm step-delete" style="display:none" onclick="deleteStep(${idx},${si})" title="Remove step">✕</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function toggleEditDetail(idx){
  editingDetail = true;
  editSnapshot = JSON.parse(JSON.stringify(testcases[idx]));
  enterEditMode(idx);
}

function enterEditMode(idx){
  const tc=testcases[idx];
  const panel=document.getElementById(`previewDetail-${idx}`);
  // Swap title and preconditions to textareas
  const titleEl=document.getElementById(`tcTitle-${idx}`);
  const precondEl=document.getElementById(`tcPrecond-${idx}`);
  titleEl.outerHTML=`<textarea class="detail-title-input" id="tcTitle-${idx}" oninput="editTCField(${idx},'title',this.value);autoGrow(this)">${esc(tc.title||'')}</textarea>`;
  precondEl.outerHTML=`<textarea class="detail-precond-input" id="tcPrecond-${idx}" oninput="editTCField(${idx},'preconditions',this.value);autoGrow(this)">${esc(tc.preconditions||'')}</textarea>`;
  // Auto-grow title/precond
  const newTitle=document.getElementById(`tcTitle-${idx}`);
  const newPrecond=document.getElementById(`tcPrecond-${idx}`);
  if(newTitle) autoGrow(newTitle);
  if(newPrecond) autoGrow(newPrecond);
  // Swap step cells to textareas
  panel.querySelectorAll('.step-cell-text').forEach(el=>{
    const ti=el.dataset.tc, si=el.dataset.si, field=el.dataset.field;
    const val=tc.steps[parseInt(si)][field]||'';
    const ta=document.createElement('textarea');
    ta.className='step-edit-input';
    ta.value=val;
    ta.oninput=function(){ editStep(parseInt(ti),parseInt(si),field,this.value); autoGrow(this); };
    el.replaceWith(ta);
    autoGrow(ta);
  });
  // Show delete buttons
  panel.querySelectorAll('.step-delete').forEach(el=>el.style.display='inline-flex');
  // Toggle buttons
  document.getElementById(`btnEditTC-${idx}`).style.display='none';
  document.getElementById(`btnSaveTC-${idx}`).style.display='inline-flex';
  document.getElementById(`btnCancelTC-${idx}`).style.display='inline-flex';
  document.getElementById(`btnAddStep-${idx}`).style.display='inline-flex';
}

function saveDetailEdits(idx){
  editingDetail=false;
  editSnapshot=null;
  renderDetail(idx);
  updateMetrics();
  const wrapper=document.querySelector(`.preview-wrapper[data-idx="${idx}"]`);
  if(wrapper){
    wrapper.querySelector('.preview-item-title').textContent=testcases[idx].title||'Untitled';
    wrapper.querySelector('.preview-item-meta').textContent=testcases[idx].preconditions||'No preconditions';
  }
  showToast('✅ Changes saved','ok');
}

function cancelDetailEdits(idx){
  if(editSnapshot){
    testcases[idx] = JSON.parse(JSON.stringify(editSnapshot));
    editSnapshot = null;
  }
  editingDetail=false;
  renderDetail(idx);
  updateMetrics();
  const wrapper=document.querySelector(`.preview-wrapper[data-idx="${idx}"]`);
  if(wrapper){
    wrapper.querySelector('.preview-item-title').textContent=testcases[idx].title||'Untitled';
    wrapper.querySelector('.preview-item-meta').textContent=testcases[idx].preconditions||'No preconditions';
  }
  showToast('↩️ Changes cancelled','info');
}

function editTCField(idx, field, value){
  testcases[idx][field]=value;
}

function editStep(tcIdx, stepIdx, field, value){
  testcases[tcIdx].steps[stepIdx][field]=value;
}

function addStep(tcIdx){
  if(!testcases[tcIdx].steps) testcases[tcIdx].steps=[];
  testcases[tcIdx].steps.push({action:'',expected:''});
  renderDetail(tcIdx);
  enterEditMode(tcIdx);
  updateMetrics();
  const panel=document.getElementById(`previewDetail-${tcIdx}`);
  const inputs=panel?panel.querySelectorAll('tr:last-child .step-edit-input'):[];
  if(inputs.length) inputs[0].focus();
}

function deleteStep(tcIdx, stepIdx){
  testcases[tcIdx].steps.splice(stepIdx,1);
  renderDetail(tcIdx);
  enterEditMode(tcIdx);
  updateMetrics();
}

function deleteTestCase(idx){
  if(!confirm(`Delete test case #${idx+1} "${testcases[idx].title||'Untitled'}"?`)) return;
  testcases.splice(idx,1);
  selectedTC=-1;
  buildPreview();
  showToast('🗑 Test case deleted','warn');
}

function updateMetrics(){
  let totalSteps=0;
  testcases.forEach(tc=>totalSteps+=(tc.steps||[]).length);
  document.getElementById('metricTotal').textContent=testcases.length;
  document.getElementById('metricSteps').textContent=totalSteps;
}

function syncEditsToJSON(){
  document.getElementById('jsonEditor').value=JSON.stringify(testcases,null,2);
  validateJSONLive();
  showToast('✅ JSON updated with your edits','ok');
}

// ── UPLOAD ──────────────────────────────────────────────
function fillUploadSummary(){
  document.getElementById('upOrg').textContent   = config.org||'—';
  document.getElementById('upPlan').textContent  = config.plan_id||'—';
  document.getElementById('upCount').textContent = testcases.length;
}

async function startUpload(){
  document.getElementById('btnUpload').disabled=true;
  document.getElementById('btnBack3').disabled=true;
  document.getElementById('logWrap').innerHTML='';
  setProgress(0,'Connecting to backend…');

  try {
    const resp=await fetch(`${API()}/api/upload/stream`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({config,testcases})});
    if(!resp.ok){
      const err=await resp.json().catch(()=>({detail:resp.statusText}));
      log('err',`Upload failed: ${err.detail}`); setProgress(0,'Upload failed');
      document.getElementById('btnUpload').disabled=false; document.getElementById('btnBack3').disabled=false; return;
    }
    const reader=resp.body.getReader(), decoder=new TextDecoder();
    let buf='';
    while(true){
      const{done,value}=await reader.read(); if(done) break;
      buf+=decoder.decode(value,{stream:true});
      const lines=buf.split('\n'); buf=lines.pop();
      for(const line of lines){
        if(!line.startsWith('data: ')) continue;
        try {
          const ev=JSON.parse(line.slice(6));
          if(ev.progress!=null) setProgress(ev.progress, ev.message);
          if(ev.type&&ev.type!=='done'&&ev.type!=='progress') log(ev.type, ev.message);
          if(ev.type==='done'){ document.getElementById('btnReset').style.display='inline-flex'; showToast('🎉 Upload complete!','ok'); }
        } catch {}
      }
    }
  } catch(e){
    log('err',`Network error: ${e.message}`);
    log('warn','Is the backend running? Check the API URL above.');
    setProgress(0,'Failed — backend unreachable');
    document.getElementById('btnUpload').disabled=false; document.getElementById('btnBack3').disabled=false;
  }
}

function resetUpload(){
  testcases=[]; document.getElementById('jsonEditor').value='';
  setProgress(0,'Ready to upload'); document.getElementById('logWrap').innerHTML='';
  document.getElementById('btnReset').style.display='none';
  document.getElementById('btnUpload').disabled=false; document.getElementById('btnBack3').disabled=false;
  validateJSONLive(); goTo(1);
}

// ── AI GENERATOR (standalone Page 4 — kept for backward compat) ──
function handleDragOver(e){ e.preventDefault(); document.getElementById('imgDrop')?.classList.add('drag-over'); }
function handleDragLeave(){ document.getElementById('imgDrop')?.classList.remove('drag-over'); }
function handleImgDrop(e){ e.preventDefault(); handleDragLeave(); if(e.dataTransfer.files[0]) processImg(e.dataTransfer.files[0]); }
function handleImgSelect(e){ if(e.target.files[0]) processImg(e.target.files[0]); }

function processImg(file){
  imgMediaType=file.type||'image/png';
  const reader=new FileReader();
  reader.onload=ev=>{
    imgBase64=ev.target.result.split(',')[1];
    const prev=document.getElementById('imgPreview');
    if(prev){ prev.src=ev.target.result; prev.style.display='block'; }
    const lbl=document.getElementById('imgDropLabel');
    if(lbl) lbl.textContent=`✅ ${file.name}`;
    document.getElementById('imgDrop')?.classList.add('has-img');
    const btn=document.getElementById('btnClearImg');
    if(btn) btn.style.display='inline-flex';
  };
  reader.readAsDataURL(file);
}

function clearImg(){
  imgBase64=null;
  const prev=document.getElementById('imgPreview');
  if(prev) prev.style.display='none';
  const lbl=document.getElementById('imgDropLabel');
  if(lbl) lbl.textContent='🖼 Click or drag & drop a screenshot here';
  document.getElementById('imgDrop')?.classList.remove('has-img');
  const btn=document.getElementById('btnClearImg');
  if(btn) btn.style.display='none';
  const inp=document.getElementById('imgInput');
  if(inp) inp.value='';
}

// ── AI GENERATOR (inline — in Page 1) ──────────────────
function handleDragOverInline(e){ e.preventDefault(); document.getElementById('imgDropInline').classList.add('drag-over'); }
function handleDragLeaveInline(){ document.getElementById('imgDropInline').classList.remove('drag-over'); }
function handleImgDropInline(e){ e.preventDefault(); handleDragLeaveInline(); if(e.dataTransfer.files[0]) processImgInline(e.dataTransfer.files[0]); }
function handleImgSelectInline(e){ if(e.target.files[0]) processImgInline(e.target.files[0]); }

function processImgInline(file){
  imgMediaType=file.type||'image/png';
  const reader=new FileReader();
  reader.onload=ev=>{
    imgBase64=ev.target.result.split(',')[1];
    const prev=document.getElementById('imgPreviewInline');
    prev.src=ev.target.result; prev.style.display='block';
    document.getElementById('imgDropLabelInline').textContent=`✅ ${file.name}`;
    document.getElementById('imgDropInline').classList.add('has-img');
    document.getElementById('btnClearImgInline').style.display='inline-flex';
  };
  reader.readAsDataURL(file);
}

function clearImgInline(){
  imgBase64=null;
  document.getElementById('imgPreviewInline').style.display='none';
  document.getElementById('imgDropLabelInline').textContent='🖼 Click or drag & drop a screenshot here';
  document.getElementById('imgDropInline').classList.remove('has-img');
  document.getElementById('btnClearImgInline').style.display='none';
  document.getElementById('imgInputInline').value='';
}

async function generateWithAIInline(){
  const desc=document.getElementById('aiDescInline').value.trim();
  if(!desc&&!imgBase64){ showToast('❌ Add a description or screenshot','error'); return; }
  const btn=document.getElementById('btnGenerateInline'), spinner=document.getElementById('aiSpinnerInline');
  btn.disabled=true; spinner.style.display='inline'; document.getElementById('aiResultInline').style.display='none';
  try {
    const r=await fetch(`${API()}/api/ai/generate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      description:desc, image_base64:imgBase64, image_media_type:imgMediaType,
      count:parseInt(document.getElementById('aiCountInline').value),
      context:document.getElementById('aiContextInline').value.trim()||null
    })});
    const d=await r.json();
    if(!r.ok) throw new Error(d.detail||'AI generation failed');
    aiGeneratedCases=d.testcases; renderAIResultInline(d); showToast(`🤖 ${d.count} test cases generated`,'ok');
  } catch(e){ showToast(`❌ ${e.message}`,'error'); }
  finally { btn.disabled=false; spinner.style.display='none'; }
}

function renderAIResultInline(d){
  document.getElementById('aiResultInline').style.display='block';
  document.getElementById('aiResultMetaInline').innerHTML=`<span class="badge badge-green">${d.count} generated</span> <span class="badge badge-blue" style="margin-left:5px">${d.model}</span> <span class="badge badge-purple" style="margin-left:5px">${d.tokens_used} tokens</span>`;
  const body=document.getElementById('aiResultBodyInline'); body.innerHTML='';
  d.testcases.forEach((tc,i)=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td style="color:var(--muted)">${i+1}</td><td style="font-weight:600;max-width:300px">${esc(tc.title)}</td><td><span class="badge badge-purple">${(tc.steps||[]).length} steps</span></td>`;
    body.appendChild(tr);
  });
}

function useAIResultInline(){
  testcases=aiGeneratedCases;
  document.getElementById('jsonEditor').value=JSON.stringify(testcases,null,2);
  validateJSONLive();
  goToPreview();
}

function loadAIResultToEditor(){
  testcases=aiGeneratedCases;
  document.getElementById('jsonEditor').value=JSON.stringify(testcases,null,2);
  validateJSONLive();
  switchInputMode('paste');
  showToast('✅ Loaded into JSON editor','ok');
}

// ── HISTORY ─────────────────────────────────────────────
async function loadHistory(){
  const el=document.getElementById('historyList');
  el.innerHTML='<div style="color:var(--muted);font-size:13px">Loading…</div>';
  try {
    const r=await fetch(`${API()}/api/history/`);
    const entries=await r.json();
    if(!entries.length){ el.innerHTML='<div style="color:var(--muted);font-size:13px">No uploads yet.</div>'; return; }
    el.innerHTML='';
    entries.forEach(e=>{
      const div=document.createElement('div'); div.className='history-row';
      const dotCls=e.status==='success'?'hs-success':e.status==='partial'?'hs-partial':'hs-failed';
      const date=new Date(e.uploaded_at).toLocaleString();
      div.innerHTML=`<span class="hist-dot ${dotCls}"></span><div><div style="font-size:13px;font-weight:600">${esc(e.org)} / ${esc(e.project)}</div><div style="font-size:11px;color:var(--muted);font-family:var(--mono)">Plan ${e.plan_id} · Story ${e.story_id} · Suite ${e.suite_id||'N/A'}</div></div><span class="badge ${e.status==='success'?'badge-green':e.status==='partial'?'badge-warn':'badge-red'}">${e.status}</span><span class="badge badge-blue">${e.created_count} created</span><span style="font-size:11px;color:var(--muted);font-family:var(--mono)">${date}</span><button class="btn btn-danger btn-sm" onclick="deleteHistory(event,${e.id})">✕</button>`;
      div.onclick=ev=>{ if(!ev.target.closest('button')) openHistoryLog(e.id,`${e.org}/${e.project}`); };
      el.appendChild(div);
    });
  } catch { el.innerHTML='<div style="color:var(--danger);font-size:13px">❌ Could not load — is the backend running?</div>'; }
}

async function openHistoryLog(id, title){
  document.getElementById('historyModalTitle').innerHTML=`Logs — <span>${esc(title)}</span>`;
  const logEl=document.getElementById('historyModalLog');
  logEl.innerHTML='<div style="color:var(--muted)">Loading…</div>';
  document.getElementById('historyModal').classList.add('open');
  try {
    const r=await fetch(`${API()}/api/history/${id}`);
    const e=await r.json();
    const lines=(e.logs||'').split('\n').filter(Boolean);
    logEl.innerHTML=lines.map(l=>{
      const t=l.startsWith('[OK]')?'ok':l.startsWith('[ERR]')?'err':l.startsWith('[WARN]')?'warn':'info';
      return `<div class="log-line"><span class="log-ts">—</span><span class="log-${t}">${esc(l)}</span></div>`;
    }).join('')||'<div style="color:var(--muted)">No logs.</div>';
  } catch { logEl.innerHTML='<div style="color:var(--danger)">Failed to load logs.</div>'; }
}

async function deleteHistory(ev,id){
  ev.stopPropagation();
  if(!confirm('Delete this entry?')) return;
  try {
    const r=await fetch(`${API()}/api/history/${id}`,{method:'DELETE'});
    if(r.ok){ showToast('🗑 Deleted','warn'); loadHistory(); }
  } catch { showToast('❌ Failed to delete','error'); }
}

// ── HELPERS ─────────────────────────────────────────────
function esc(s){ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function autoGrow(el){ el.style.height='auto'; el.style.height=el.scrollHeight+'px'; }
function setProgress(pct,txt){ document.getElementById('progressBar').style.width=pct+'%'; document.getElementById('progressText').textContent=txt; }

function log(type,msg){
  const wrap=document.getElementById('logWrap'), now=new Date().toLocaleTimeString('en-GB');
  const div=document.createElement('div'); div.className='log-line';
  div.innerHTML=`<span class="log-ts">${now}</span><span class="log-${type}">${esc(msg)}</span>`;
  if(wrap.firstChild?.style?.fontStyle==='italic') wrap.innerHTML='';
  wrap.appendChild(div); wrap.scrollTop=wrap.scrollHeight;
}

// ── THEME TOGGLE ────────────────────────────────────────
function toggleTheme(){
  const next=document.documentElement.getAttribute('data-theme')==='light'?'dark':'light';
  document.documentElement.setAttribute('data-theme',next);
  document.getElementById('themeIcon').textContent=next==='light'?'🌙':'☀️';
  localStorage.setItem('theme',next);
}
{const t=localStorage.getItem('theme')||'dark';const i=document.getElementById('themeIcon');if(i)i.textContent=t==='light'?'🌙':'☀️';}

// ── TOAST ───────────────────────────────────────────────
function showToast(msg,type){
  const c=document.getElementById('toast'), div=document.createElement('div');
  div.className='toast-msg';
  const colors={ok:'#10b981',error:'#ef4444',info:'#00d4ff',warn:'#f59e0b'};
  div.style.borderLeftColor=colors[type]||'#00d4ff'; div.style.borderLeftWidth='3px';
  div.textContent=msg; c.appendChild(div); setTimeout(()=>div.remove(),3600);
}
