'use strict';
const $ = (selector) => document.querySelector(selector);
const state = { data: null, selectedWeek: null, view: 'overview', requestId: null, loading: false };
const weekNames = ['工程基础', '原生 Agent', '知识检索', '检索评测', '流程编排', '审批与恢复', '工具服务', 'API 与数据库', '系统评测', '可靠性', '部署与演示', '简历与面试'];
const colors = ['#345df1', '#7396f4', '#29a78a', '#f1b655'];
const labels = { todo: '未开始', active: '进行中', review: '待验收', done: '已验收' };
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const stripMarkdown = (value) => String(value ?? '').replace(/\*\*/g, '').replace(/`/g, '');
const shortTitle = (id) => weekNames[Number(id.slice(1)) - 1] || id;
const text = (selector, value) => { $(selector).textContent = value ?? ''; };
const pill = (status) => `<span class="status-pill ${escapeHTML(status)}">${labels[status] || '未开始'}</span>`;
const pending = (entry) => entry.status !== 'reviewed';
const duration = (minutes) => minutes < 60 ? `${minutes} 分钟` : `${Math.floor(minutes / 60)} 小时${minutes % 60 ? ` ${minutes % 60} 分钟` : ''}`;

function render(data) {
  const currentTask = data.tasks.find((task) => task.id === data.currentTask);
  text('#current-week', data.currentWeek);
  text('#current-title', currentTask?.title || data.meta['当前子任务'] || data.meta['当前阶段']);
  text('#next-step', data.meta['下一任务']);
  text('#current-task-id', data.currentTask);
  text('.current-status', labels[currentTask?.status || 'active']);
  const gatesDone = data.gates.filter((gate) => gate.status === 'done').length;
  $('#gates-number').innerHTML = `${gatesDone}<span>/ ${data.gates.length}</span>`;
  text('#gates-caption', `${gatesDone} / ${data.gates.length}`);
  $('#gate-ring').style.background = `conic-gradient(#fff ${(gatesDone / data.gates.length) * 360}deg, #ffffff24 0deg)`;
  $('#gate-ring').setAttribute('aria-label', `${data.gates.length} 个阶段中已有 ${gatesDone} 个通过验收`);
  $('#task-count').innerHTML = `${data.tasks.filter((task) => task.status === 'done').length}<span>/ ${data.tasks.length || '—'} 步</span>`;
  const pendingCount = data.entries.filter(pending).length;
  $('#pending-count').innerHTML = `${pendingCount}<span>条</span>`;
  const minutes = data.entries.reduce((sum, entry) => sum + (Number(entry.minutes) || 0), 0);
  $('#time-count').textContent = data.entries.length ? duration(minutes) : '—';
  $('#time-count').style.fontSize = minutes > 600 ? '1.2rem' : '';
  text('#journal-count', data.entries.length);
  text('#verified', data.meta['已验证成果']);
  text('#needs', data.meta['待验收内容']);
  text('#updated-label', `进度更新于 ${data.meta['更新时间']?.split('，')[0] || '尚未记录'}`);
  renderRoadmap();
  renderWeek();
  renderGates();
  renderJournal();
  renderSchedule();
}

function renderRoadmap() {
  $('#roadmap').innerHTML = state.data.weeks.map((week) => `<button class="week-button ${week.id === state.data.currentWeek ? 'current' : ''} ${week.status === 'done' ? 'done' : ''} ${week.id === state.selectedWeek ? 'selected' : ''}" data-week="${escapeHTML(week.id)}" aria-pressed="${week.id === state.selectedWeek}" aria-label="${escapeHTML(week.id)} ${escapeHTML(shortTitle(week.id))}，${labels[week.status]}${week.id === state.data.currentWeek ? '，当前学习阶段' : ''}"><span class="week-number">${escapeHTML(week.id)}</span><span class="week-name">${escapeHTML(shortTitle(week.id))}</span><span class="week-mark" aria-hidden="true"></span></button>`).join('');
}

function renderWeek() {
  const data = state.data;
  const week = data.weeks.find((item) => item.id === state.selectedWeek) || data.weeks[0];
  text('#selected-week-label', `${week.id} / ${week.id === data.currentWeek ? '当前阶段' : '学习路线'}`);
  text('#selected-week-title', shortTitle(week.id));
  const statusElement = $('#selected-week-status');
  statusElement.className = `status-pill ${week.status}`;
  statusElement.textContent = labels[week.status];
  text('#week-topics', week.topics);
  $('#week-outcome').innerHTML = `<strong>本周完成标准</strong>${escapeHTML(week.outcome)}`;
  const current = week.id === data.currentWeek;
  $('#task-list').innerHTML = current ? data.tasks.map((task, index) => {
    const logs = data.entries.filter((entry) => entry.taskId === task.id && pending(entry)).length;
    return `<div class="task-row ${task.status}"><div class="task-indicator" aria-hidden="true">${task.status === 'done' ? '✓' : String(index + 1).padStart(2, '0')}</div><div class="task-text"><div class="task-topline"><div class="task-title">${escapeHTML(task.title)}</div>${pill(task.status)}</div><div class="task-id">${escapeHTML(task.id)}</div><p class="task-criteria">${escapeHTML(task.criteria)}</p><div class="task-actions">${task.id === data.currentTask ? `<button class="text-button" data-record-task="${escapeHTML(task.id)}">记录这项练习</button>` : ''}${logs ? `<span class="task-log-count">${logs} 条记录待 Review</span>` : ''}</div></div></div>`;
  }).join('') : '';
  $('#week-plan-detail').innerHTML = !current || !data.tasks.length ? `<div class="empty-week">${week.checklist.length ? week.checklist.map((item, index) => `<div class="task-row"><div class="task-indicator" aria-hidden="true">${item.checked ? '✓' : String(index + 1).padStart(2, '0')}</div><div class="task-text"><div class="task-title">${escapeHTML(stripMarkdown(item.text))}</div></div></div>`).join('') : '进入这个阶段时，导师会将目标拆成可独立验证的小任务。'}</div>` : '';
}

function renderGates() {
  $('#gate-list').innerHTML = state.data.gates.map((gate, index) => `<div class="gate-item ${gate.status}"><div class="gate-marker" aria-hidden="true">${gate.status === 'done' ? '✓' : index + 1}</div><div class="gate-title">${escapeHTML(gate.title)}</div><div class="gate-meta"><span>${escapeHTML(gate.when)}</span><span>${gate.status === 'done' ? '已验收' : '未验收'}</span></div><details><summary>查看验收要求</summary><p>${escapeHTML(gate.criteria)}</p></details></div>`).join('');
}

function renderJournal() {
  const data = state.data;
  const entries = [...data.entries].sort((a, b) => b.date.localeCompare(a.date) || b.createdAt.localeCompare(a.createdAt));
  $('#journal-list').innerHTML = entries.length ? entries.map((entry) => `<article class="journal-entry"><div class="entry-head"><div class="entry-meta"><strong>${escapeHTML(entry.taskId)}</strong><span>${escapeHTML(entry.date)}</span><span>${duration(Number(entry.minutes) || 0)}</span></div><span class="status-pill ${pending(entry) ? 'review' : 'done'}">${pending(entry) ? '待 Review' : '已 Review'}</span></div><p>${escapeHTML(entry.note)}</p>${entry.evidence ? `<div class="entry-evidence"><strong>成果或待解决问题</strong>${escapeHTML(entry.evidence)}</div>` : ''}</article>`).join('') : '<div class="empty-state"><div aria-hidden="true">▤</div><h2>从第一条学习记录开始</h2><p>写下你对 Git 的理解、实际操作结果，或遇到的问题。</p><button class="button primary" data-action="record">记录本次学习</button></div>';
  $('#mentor-history').innerHTML = data.history.map((entry) => `<div class="history-row"><strong>${escapeHTML(entry['日期'])} · ${escapeHTML(entry['任务'])}</strong><p>${escapeHTML(entry['成果和证据'])}</p><p><small>待掌握：${escapeHTML(entry['待掌握内容'])}</small></p></div>`).join('') || '<p class="secondary">还没有导师记录。</p>';
}

function renderSchedule() {
  const data = state.data;
  const budget = data.budget.map((row) => ({ ...row, hours: Number(row['暂定时间']?.match(/\d+(?:\.\d+)?/)?.[0]) || 0 }));
  const total = budget.reduce((sum, row) => sum + row.hours, 0);
  $('#budget-bar').replaceChildren(...budget.map((row, index) => {
    const piece = document.createElement('div');
    piece.style.width = `${total ? row.hours / total * 100 : 0}%`;
    piece.style.backgroundColor = colors[index % colors.length];
    return piece;
  }));
  $('#budget-bar').setAttribute('aria-label', budget.map((row) => `${row['模块']} ${row.hours} 小时`).join('，'));
  $('#budget-list').innerHTML = budget.map((row, index) => `<div class="budget-item"><h3><span class="swatch budget-swatch-${index}" aria-hidden="true"></span>${escapeHTML(row['模块'])}</h3><strong>${escapeHTML(row['暂定时间'])}</strong><p>${escapeHTML(row['持续产出'])}</p></div>`).join('');
  $$('.swatch').forEach((element, index) => { element.style.backgroundColor = colors[index % colors.length]; });
  $('#fundamentals-list').innerHTML = data.fundamentals.map((row) => `<div class="fundamental-row"><strong>${escapeHTML(row['周次'])}</strong><div><span>算法</span>${escapeHTML(row['算法主线'])}</div><div><span>计算机基础</span>${escapeHTML(row['计算机基础主线'])}</div></div>`).join('');
  $('#job-list').innerHTML = data.jobs.map((row) => `<div class="job-row"><strong>${escapeHTML(row['阶段'])}</strong><p>${escapeHTML(row['原计划中的行动'])}</p><span class="status-pill">${escapeHTML(row['当前状态'])}</span></div>`).join('');
}

const $$ = (selector) => Array.from(document.querySelectorAll(selector));
function switchView(view) {
  state.view = view;
  $$('.view').forEach((element) => { element.hidden = element.id !== `view-${view}`; });
  $$('.nav-item').forEach((element) => { element.classList.toggle('selected', element.dataset.view === view); element.setAttribute('aria-current', element.dataset.view === view ? 'page' : 'false'); });
  text('#view-label', { overview: '学习总览', journal: '学习记录', schedule: '每周安排' }[view]);
}

async function fetchJSON(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 7000);
  try {
    const response = await fetch(url, { cache: 'no-store', ...options, signal: controller.signal });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || '请求失败，请稍后重试。');
    return body;
  } finally { clearTimeout(timeout); }
}

async function refresh(force = false) {
  if (state.loading) return;
  state.loading = true;
  const button = $('#refresh-button');
  button.disabled = true;
  try {
    const data = await fetchJSON('/api/progress');
    const old = state.data;
    if (!state.selectedWeek || (old && old.currentWeek !== data.currentWeek && state.selectedWeek === old.currentWeek)) state.selectedWeek = data.currentWeek;
    if (!data.weeks.some((week) => week.id === state.selectedWeek)) state.selectedWeek = data.currentWeek;
    state.data = data;
    if (force || !old || old.version !== data.version) render(data);
    text('#sync-state', '已同步本地进度');
    $('#sync-state').className = 'sync-state connected';
    $('#error-banner').hidden = true;
  } catch (error) {
    text('#sync-state', '更新暂时中断');
    $('#sync-state').className = 'sync-state offline';
    text('#error-banner', `${state.data ? '暂时无法更新，当前保留上次读取的进度。' : '暂时无法读取学习进度。'} ${error.name === 'AbortError' ? '连接超时，请确认本机进度页已启动后重试。' : error.message}`);
    $('#error-banner').hidden = false;
  } finally { state.loading = false; button.disabled = false; }
}

function openRecord(taskId) {
  if (!state.data) { toast('进度尚未读取，请先刷新页面。'); return; }
  const form = $('#record-form');
  form.reset();
  state.requestId = crypto.randomUUID();
  const choices = [...state.data.tasks.map((task) => ({ value: task.id, text: `${task.id} · ${task.title}` })), ...state.data.weeks.map((week) => ({ value: week.id, text: `${week.id} · ${shortTitle(week.id)}` }))];
  $('#record-task').replaceChildren(...choices.map((choice) => new Option(choice.text, choice.value)));
  $('#record-task').value = taskId || state.data.currentTask || state.data.currentWeek;
  $('#record-date').value = state.data.today;
  $('#record-date').max = state.data.today;
  $('#form-error').hidden = true;
  $('#record-dialog').showModal();
}

async function saveRecord(payload) {
  if (!state.data) throw new Error('请先读取进度。');
  const result = await fetchJSON('/api/journal', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Learning-Token': state.data.csrfToken }, body: JSON.stringify(payload) });
  if (!state.data.entries.some((entry) => entry.id === result.entry.id)) state.data.entries.push(result.entry);
  render(state.data);
  return result.entry;
}

$('#record-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const button = $('#save-button');
  button.disabled = true;
  button.textContent = '正在保存';
  $('#form-error').hidden = true;
  try {
    await saveRecord({ requestId: state.requestId, taskId: $('#record-task').value, date: $('#record-date').value, minutes: Number($('#record-minutes').value), note: $('#record-note').value, evidence: $('#record-evidence').value });
    $('#record-dialog').close();
    switchView('journal');
    toast('学习记录已保存，等待导师 Review。');
    await refresh();
  } catch (error) {
    text('#form-error', error.name === 'AbortError' ? '连接超时，输入已保留。可以点击保存重试。' : error.message);
    $('#form-error').hidden = false;
  } finally { button.disabled = false; button.textContent = '保存学习记录'; }
});

let toastTimer;
function toast(message) { text('#toast', message); $('#toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 4200); }

async function openDocument(kind) {
  text('#document-title', kind === 'plan' ? '原学习计划' : '学习进度记录');
  text('#document-content', '正在读取文档…');
  $('#document-dialog').showModal();
  try {
    const response = await fetch(`/api/documents/${kind}`, { cache: 'no-store' });
    if (!response.ok) throw new Error('文档暂时无法读取，请稍后重试。');
    text('#document-content', await response.text());
  } catch (error) { text('#document-content', error.message); }
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.dataset.view) switchView(button.dataset.view);
  if (button.dataset.week) { state.selectedWeek = button.dataset.week; renderRoadmap(); renderWeek(); }
  if (button.dataset.action === 'record') openRecord();
  if (button.dataset.recordTask) openRecord(button.dataset.recordTask);
  if (button.dataset.close) document.getElementById(button.dataset.close).close();
  if (button.dataset.document) openDocument(button.dataset.document);
});
$('#refresh-button').addEventListener('click', () => refresh(true));
$('#current-detail').addEventListener('click', () => { if (!state.data) { toast('进度尚未读取，请先刷新页面。'); return; } state.selectedWeek = state.data.currentWeek; switchView('overview'); renderRoadmap(); renderWeek(); $('#task-panel').scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' }); });
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
setInterval(() => { if (!document.hidden) refresh(); }, 5000);
refresh();

const modelContext = document.modelContext;
if (modelContext?.registerTool) {
  const lifecycle = new AbortController();
  const register = (tool) => { try { Promise.resolve(modelContext.registerTool(tool, { signal: lifecycle.signal })).catch(() => {}); } catch (_) {} };
  register({ name: 'get_learning_progress', title: '查看学习进度', description: '读取当前任务、验收进度和学习路线，不修改任何记录。', inputSchema: { type: 'object', properties: {}, additionalProperties: false }, annotations: { readOnlyHint: true, untrustedContentHint: false }, async execute(input) { if (!input || typeof input !== 'object' || Object.keys(input).length) throw new Error('不需要输入参数。'); await refresh(); if (!state.data) throw new Error('进度暂时无法读取。'); return { currentWeek: state.data.currentWeek, currentTask: state.data.currentTask, meta: state.data.meta, tasks: state.data.tasks, gates: state.data.gates }; } });
  register({ name: 'record_learning_session', title: '保存学习记录', description: '保存一次学习用时、心得和成果，状态为待 Review，不会将任务自动标记为已验收。', inputSchema: { type: 'object', properties: { taskId: { type: 'string' }, date: { type: 'string', format: 'date' }, minutes: { type: 'integer', minimum: 0, maximum: 1440 }, note: { type: 'string', minLength: 1, maxLength: 4000 }, evidence: { type: 'string', maxLength: 2000 } }, required: ['taskId', 'date', 'minutes', 'note', 'evidence'], additionalProperties: false }, annotations: { readOnlyHint: false, untrustedContentHint: true }, async execute(input) { if (!input || typeof input !== 'object' || Object.keys(input).sort().join(',') !== 'date,evidence,minutes,note,taskId') throw new Error('记录字段不完整或包含额外字段。'); const entry = await saveRecord({ ...input, requestId: crypto.randomUUID() }); switchView('journal'); return { id: entry.id, status: entry.status, taskId: entry.taskId }; } });
  window.addEventListener('pagehide', () => lifecycle.abort(), { once: true });
}
