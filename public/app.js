const state = { scenario: 'congestion', payload: null, report: null, scenarios: [], loadingScenario: false, scenarioRequest: 0 };
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));

function isTelemetry(value) {
  return Boolean(value && typeof value === 'object' && Array.isArray(value.devices));
}

function setRunState(label, enabled) {
  $('run-button').disabled = !enabled;
  $('run-state').innerHTML = `${label} <i></i>`;
  $('run-state').style.color = enabled ? '' : 'var(--cyan)';
}

function showRunError(message) {
  $('run-error').textContent = message;
  $('run-error').hidden = false;
}

async function loadScenarioCatalog() {
  setRunState('LOADING SCENARIOS', false);
  const response = await fetch('/api/scenarios');
  if (!response.ok) throw new Error('Scenario catalog unavailable.');
  const data = await response.json();
  state.scenarios = data.scenarios;
  $('scenario-strip').innerHTML = state.scenarios.map((item) => `
    <button class="scenario-card ${item.id === state.scenario ? 'active' : ''}" data-scenario="${esc(item.id)}" type="button" role="listitem">
      <strong>${esc(item.title)}</strong><small>${esc(item.signal)}</small>
    </button>`).join('');
  document.querySelectorAll('[data-scenario]').forEach((button) => button.addEventListener('click', () => {
    selectScenario(button.dataset.scenario).catch((error) => showRunError(error.message));
  }));
  await selectScenario(state.scenario);
}

async function selectScenario(name) {
  const requestId = ++state.scenarioRequest;
  state.scenario = name;
  state.payload = null;
  state.loadingScenario = true;
  setRunState('LOADING TELEMETRY', false);
  $('run-error').hidden = true;
  document.querySelectorAll('[data-scenario]').forEach((button) => button.classList.toggle('active', button.dataset.scenario === name));
  try {
    const response = await fetch(`/api/scenarios/${encodeURIComponent(name)}`);
    if (!response.ok) throw new Error(`Could not load the ${name} scenario.`);
    const data = await response.json();
    const telemetry = data.telemetry || data;
    if (requestId !== state.scenarioRequest) return;
    if (!isTelemetry(telemetry)) throw new Error('Scenario response did not contain a telemetry device list.');
    state.payload = telemetry;
    $('active-stream').textContent = `${name} · ${telemetry.devices.length} device${telemetry.devices.length === 1 ? '' : 's'}`;
    $('file-label').textContent = 'Upload telemetry JSON';
    setRunState('READY TO RUN', true);
  } finally {
    if (requestId === state.scenarioRequest) state.loadingScenario = false;
  }
}

function setRunning(running) {
  $('run-button').disabled = running || !state.payload || state.loadingScenario;
  $('run-state').innerHTML = running ? 'AGENTS ANALYZING <i class="pulse"></i>' : 'READY TO RUN <i></i>';
  $('run-state').style.color = running ? 'var(--cyan)' : '';
}

async function runDiagnosis() {
  if (state.loadingScenario) {
    showRunError('The selected telemetry is still loading. Please wait for READY TO RUN.');
    return;
  }
  if (!isTelemetry(state.payload)) {
    showRunError('No telemetry is loaded. Select a scenario or upload a JSON file before running.');
    return;
  }
  setRunning(true);
  $('run-error').hidden = true;
  try {
    const telemetry = state.payload.telemetry && !state.payload.devices ? state.payload.telemetry : state.payload;
    const response = await fetch('/api/diagnose', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(telemetry) });
    if (!response.ok) throw new Error((await response.json()).error || 'Diagnosis request failed.');
    state.report = await response.json();
    renderReport(state.report);
  } catch (error) {
    showRunError(error.message);
  } finally { setRunning(false); }
}

function renderReport(report) {
  const summary = report.summary;
  $('empty-state').hidden = true;
  $('results').hidden = false;
  $('result-title').textContent = report.status === 'input_error' ? 'Input validation stopped the run' : 'Diagnosis consolidated';
  $('result-subtitle').textContent = `${report.incident_id} · ${report.agent_findings.length} structured agent messages · ${report.validation_messages.length ? 'warnings present' : 'validation passed'}`;
  const status = $('status-value');
  status.textContent = report.status === 'diagnosed' ? 'ANOMALY DETECTED' : report.status === 'no_anomaly_detected' ? 'NO ANOMALY' : 'INPUT ERROR';
  status.className = `big-status ${report.status === 'input_error' ? 'error' : report.status === 'no_anomaly_detected' ? '' : 'warning'}`;
  $('status-caption').textContent = report.status === 'input_error' ? 'The agent layer did not run.' : report.status === 'diagnosed' ? 'Evidence crossed the configured thresholds.' : 'Telemetry stayed within the configured baseline.';
  $('confidence-value').textContent = summary.confidence_label.toUpperCase();
  $('confidence-meter').style.width = `${Math.round(summary.confidence * 100)}%`;
  $('device-count').textContent = summary.affected_devices.length;
  $('device-list').textContent = summary.affected_devices.join(' · ') || 'No affected devices identified';
  $('evidence-count').textContent = summary.supporting_evidence.length;
  $('message-count').textContent = `${report.agent_findings.length} messages exchanged`;
  $('root-cause').textContent = summary.suspected_root_cause;
  $('evidence-pill').textContent = `${summary.supporting_evidence.length} ITEMS`;
  $('evidence-list').innerHTML = summary.supporting_evidence.length ? summary.supporting_evidence.map((item) => `<div class="evidence-item"><b>${esc(item.metric)}</b><span>${esc(item.value)} ${esc(item.unit)}</span><small>${esc(item.device_id)} · ${esc(item.interpretation)}</small></div>`).join('') : '<div class="no-evidence">No threshold breach was found in the supplied telemetry.</div>';
  $('action-list').innerHTML = summary.recommended_actions.map((action) => `<li>${esc(action)}</li>`).join('');
  $('alternative-list').innerHTML = summary.alternative_causes.map((item) => `<li>${esc(item)}</li>`).join('');
  renderAgents(report.agent_findings);
  $('json-viewer').textContent = JSON.stringify(report, null, 2);
  $('report').scrollIntoView({behavior: 'smooth', block: 'start'});
}

function renderAgents(findings) {
  const grouped = [
    { id: 'performance_agent', name: 'Performance Agent', glyph: 'P', scope: 'latency · loss · jitter · utilization' },
    { id: 'infrastructure_agent', name: 'Infrastructure Agent', glyph: 'I', scope: 'cpu · interfaces · queues · Wi-Fi' },
  ];
  $('agent-grid').innerHTML = grouped.map((agent) => {
    const messages = findings.filter((item) => item.agent_id === agent.id);
    const evidence = messages.flatMap((item) => item.evidence.map((entry) => ({...entry, device_id: item.device_id})));
    const issue = messages.find((item) => item.evidence)?.issue || messages[0]?.issue || 'no_finding';
    return `<article class="agent-card"><div class="agent-card-head"><div class="agent-avatar">${agent.glyph}</div><div><strong>${agent.name}</strong><small>${agent.scope}</small></div></div><div class="agent-card-body"><div class="message-line"><span>${messages.length} structured message${messages.length === 1 ? '' : 's'}</span><b>${esc(issue)}</b></div><div class="agent-evidence">${evidence.length ? evidence.map((item) => `<div class="agent-evidence-row"><span>${esc(item.metric)} · ${esc(item.device_id)}</span><b>${esc(item.value)} ${esc(item.unit)}</b></div>`).join('') : '<div class="no-evidence">No threshold breaches reported.</div>'}</div></div><div class="handoff-line">handoff <strong>${agent.id}</strong> → <strong>orchestrator</strong> · structured-json</div></article>`;
  }).join('');
}

function downloadReport() {
  if (!state.report) return;
  const blob = new Blob([JSON.stringify(state.report, null, 2)], {type: 'application/json'});
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `${state.report.incident_id.toLowerCase()}-netcoop-report.json`; link.click(); URL.revokeObjectURL(link.href);
}

async function copyReport() {
  if (!state.report) return;
  await navigator.clipboard.writeText(JSON.stringify(state.report, null, 2));
  $('toast').textContent = 'JSON report copied to clipboard'; $('toast').classList.add('show');
  setTimeout(() => $('toast').classList.remove('show'), 2200);
}

$('file-input').addEventListener('change', async (event) => {
  const file = event.target.files[0]; if (!file) return;
  try {
    const uploaded = JSON.parse(await file.text());
    const telemetry = uploaded.telemetry || uploaded;
    if (!isTelemetry(telemetry)) throw new Error('JSON must contain a devices array.');
    state.payload = telemetry;
    state.loadingScenario = false;
    $('file-label').textContent = file.name;
    $('active-stream').textContent = `custom upload · ${telemetry.devices.length} device${telemetry.devices.length === 1 ? '' : 's'}`;
    $('run-error').hidden = true;
    setRunState('READY TO RUN', true);
  } catch (error) { showRunError(`Could not load ${file.name}: ${error.message}`); }
});
$('run-button').addEventListener('click', runDiagnosis);
$('download-button').addEventListener('click', downloadReport);
$('copy-button').addEventListener('click', copyReport);
setRunState('LOADING SCENARIOS', false);
loadScenarioCatalog().catch((error) => showRunError(error.message));
