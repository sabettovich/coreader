const log = document.getElementById('log');
const form = document.getElementById('chat-form');
const input = document.getElementById('message');
const boundaryInput = document.getElementById('boundary');
const boundaryStatus = document.getElementById('boundary-status');
const saveBtn = document.getElementById('save-settings');
const saveBtn2 = document.getElementById('save-settings-2');
const clearBtn = document.getElementById('clear-boundary');
const saveNoteBtn = document.getElementById('save-note');
const saveStatus = document.getElementById('save-status');
const offlineCheckbox = document.getElementById('offline');
const offlineBanner = document.getElementById('offline-banner');
const sectionsWrap = document.getElementById('sections');
const socraticSelect = document.getElementById('socratic');
const replyLimitInput = document.getElementById('reply-limit');
const badgeOpenAI = document.getElementById('badge-openai');
const badgeZotero = document.getElementById('badge-zotero');
// Logs elements
const logRole = document.getElementById('log-role');
const logQ = document.getElementById('log-q');
const logRefresh = document.getElementById('log-refresh');
const logsList = document.getElementById('logs-list');
const logFiles = document.getElementById('log-files');
// Metrics elements
const mStart = document.getElementById('m-start');
const mEnd = document.getElementById('m-end');
const mRefresh = document.getElementById('m-refresh');
const mSummary = document.getElementById('m-summary');
const mTable = document.getElementById('m-table');
const mCsv = document.getElementById('m-csv');
// Preview modal elements
const modal = document.getElementById('preview-modal');
const modalContent = document.getElementById('preview-content');
const modalPath = document.getElementById('preview-path');
const modalCancel = document.getElementById('preview-cancel');
const modalConfirm = document.getElementById('preview-confirm');
// Zotero search elements
const zoteroInput = document.getElementById('zotero-q');
const zoteroBtn = document.getElementById('zotero-search');
const zoteroResults = document.getElementById('zotero-results');
let selectedBookMeta = null; // {zotero_key,title,authors,year,tags}

function append(role, text) {
  const el = document.createElement('div');
  el.className = `msg ${role}`;
  el.textContent = `${role}: ${text}`;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  return el;
}

function renderCitations(parent, citations = []) {
  if (!Array.isArray(citations) || citations.length === 0) return;
  const wrap = document.createElement('div');
  wrap.className = 'cites';
  citations.forEach((c) => {
    const item = document.createElement('div');
    item.className = 'cite-item';

    const title = document.createElement('div');
    title.className = 'cite-title';
    title.textContent = c.title || 'Фрагмент книги';

    const quote = document.createElement('blockquote');
    quote.textContent = c.quote || '';

    const meta = document.createElement('div');
    meta.className = 'cite-meta';
    const file = (c.file || '').split('/').slice(-1)[0];
    const href = `/book?file=${encodeURIComponent(c.file || '')}#${c.anchor}`;
    const openLink = document.createElement('a');
    openLink.href = href;
    openLink.target = '_blank';
    openLink.rel = 'noopener noreferrer';
    openLink.textContent = 'Открыть';

    const info = document.createElement('span');
    info.textContent = ` ${file} · #${c.anchor} `;

    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.textContent = 'Копировать ссылку';
    copyBtn.addEventListener('click', async () => {
      try {
        const abs = new URL(href, window.location.origin).toString();
        await navigator.clipboard.writeText(abs);
        copyBtn.textContent = 'Скопировано';
        setTimeout(() => (copyBtn.textContent = 'Копировать ссылку'), 1500);
      } catch (e) {
        alert('Не удалось скопировать ссылку');
      }
    });

// -------- Logs ---------
async function loadLogs() {
  if (!logsList) return;
  const role = (logRole?.value || '').trim();
  const q = (logQ?.value || '').trim();
  const params = new URLSearchParams();
  if (role) params.set('role', role);
  if (q) params.set('q', q);
  try {
    logsList.textContent = 'Загружаю…';
    const res = await fetch('/logs' + (params.toString() ? ('?' + params.toString()) : ''));
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    const entries = data.entries || [];
    const files = data.files || [];
    if (logFiles) logFiles.textContent = files.length ? `Файлы: ${files.join(', ')}` : 'Файлы журнала отсутствуют';
    logsList.innerHTML = '';
    entries.forEach((e) => {
      const item = document.createElement('div');
      item.className = `log-item ${e.role || ''}`;
      const meta = document.createElement('div');
      meta.className = 'meta';
      meta.textContent = `${e.ts || ''} · ${e.role || ''}`;
      const text = document.createElement('div');
      text.textContent = e.text || '';
      item.appendChild(meta);
      item.appendChild(text);
      if (Array.isArray(e.citations) && e.citations.length) {
        const cites = document.createElement('div');
        cites.className = 'cites';
        renderCitations(cites, e.citations);
        item.appendChild(cites);
      }
      logsList.appendChild(item);
    });
    if (!entries.length) {
      logsList.textContent = 'Нет записей.';
    }
  } catch (e) {
    logsList.textContent = `Ошибка загрузки: ${e}`;
  }
}

logRefresh?.addEventListener('click', loadLogs);
logRole?.addEventListener('change', loadLogs);
logQ?.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); loadLogs(); } });

// авто-старт логов
loadLogs();

// -------- Metrics ---------
function buildCsvUrl() {
  const params = new URLSearchParams();
  if (mStart?.value) params.set('start', mStart.value);
  if (mEnd?.value) params.set('end', mEnd.value);
  return '/metrics.csv' + (params.toString() ? ('?' + params.toString()) : '');
}

async function loadMetrics() {
  if (!mTable) return;
  const params = new URLSearchParams();
  if (mStart?.value) params.set('start', mStart.value);
  if (mEnd?.value) params.set('end', mEnd.value);
  if (mCsv) mCsv.href = buildCsvUrl();
  try {
    mTable.textContent = 'Загружаю…';
    const res = await fetch('/metrics' + (params.toString() ? ('?' + params.toString()) : ''));
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    const total = data.total_assistant || 0;
    const withCite = data.with_citation || 0;
    const ratio = data.ratio || 0;
    if (mSummary) mSummary.textContent = `Ответов ассистента: ${total}; с цитатой: ${withCite}; доля: ${(ratio*100).toFixed(1)}%`;
    const per = data.per_file || {};
    const table = document.createElement('table');
    const thead = document.createElement('thead');
    thead.innerHTML = '<tr><th>Файл</th><th>Ответов</th><th>С цитатой</th><th>Доля</th></tr>';
    table.appendChild(thead);
    const tbody = document.createElement('tbody');
    Object.entries(per).forEach(([file, vals]) => {
      const tr = document.createElement('tr');
      const t = vals.assistant || 0;
      const w = vals.with_citation || 0;
      const r = t ? (w/t) : 0;
      tr.innerHTML = `<td>${file}</td><td>${t}</td><td>${w}</td><td>${(r*100).toFixed(1)}%</td>`;
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    mTable.innerHTML = '';
    const box = document.createElement('div');
    box.className = 'metrics-table';
    box.appendChild(table);
    mTable.appendChild(box);
  } catch (e) {
    if (mSummary) mSummary.textContent = `Ошибка: ${e}`;
    if (mTable) mTable.textContent = '';
  }
}

mRefresh?.addEventListener('click', loadMetrics);
mStart?.addEventListener('change', loadMetrics);
mEnd?.addEventListener('change', loadMetrics);

// авто-старт метрик
loadMetrics();

    meta.appendChild(info);
    meta.appendChild(openLink);
    meta.appendChild(document.createTextNode(' · '));
    meta.appendChild(copyBtn);

    item.appendChild(title);
    if (quote.textContent) item.appendChild(quote);
    item.appendChild(meta);
    wrap.appendChild(item);
  });

async function loadSettings() {
  try {
    const res = await fetch('/settings');
    const st = await res.json();
    // инфо о провайдерах
    try {
      const infoRes = await fetch('/settings/info');
      const info = await infoRes.json();
      if (badgeOpenAI) badgeOpenAI.classList.toggle('ok', !!info.openai_configured);
      if (badgeZotero) badgeZotero.classList.toggle('ok', !!info.zotero_configured);
    } catch {}
    // Применим локальное сохранённое значение оффлайна, если есть
    const lsOffline = localStorage.getItem('coreader_offline');
    if (lsOffline === 'true' || lsOffline === 'false') {
      st.offline = (lsOffline === 'true');
    }
    if (typeof st.read_boundary_seq === 'number') {
      boundaryInput.value = String(st.read_boundary_seq);
      if (boundaryStatus) boundaryStatus.textContent = st.read_boundary_seq;
    } else {
      boundaryInput.value = '';
      if (boundaryStatus) boundaryStatus.textContent = 'не задана';
    }
    if (typeof st.offline === 'boolean') {
      if (offlineCheckbox) offlineCheckbox.checked = !!st.offline;
      if (offlineBanner) offlineBanner.classList.toggle('hidden', !st.offline);
    }
    if (typeof st.socratic_level === 'number' && socraticSelect) {
      socraticSelect.value = String(st.socratic_level);
    }
    if (typeof st.reply_limit_chars === 'number' && replyLimitInput) {
      replyLimitInput.value = String(st.reply_limit_chars);
    }
    // Если было локальное значение, протолкнём его на сервер один раз
    if (lsOffline === 'true' || lsOffline === 'false') {
      await saveSettings();
    }
  } catch {}
}

async function saveSettings() {
  try {
    const res = await fetch('/settings');
    const st = await res.json();
    const seq = boundaryInput.value ? parseInt(boundaryInput.value, 10) : null;
    st.read_boundary_seq = Number.isFinite(seq) ? seq : null;
    if (offlineCheckbox) st.offline = !!offlineCheckbox.checked;
    if (socraticSelect) st.socratic_level = parseInt(socraticSelect.value || '2', 10);
    if (replyLimitInput) st.reply_limit_chars = parseInt(replyLimitInput.value || '500', 10);
    // Сохраним оффлайн в localStorage, чтобы переживать рестарты сервера
    if (typeof st.offline === 'boolean') {
      localStorage.setItem('coreader_offline', st.offline ? 'true' : 'false');
    }
    const r2 = await fetch('/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(st)
    });
    if (!r2.ok) throw new Error(await r2.text());
    if (boundaryStatus) boundaryStatus.textContent = st.read_boundary_seq ?? 'не задана';
    if (offlineBanner) offlineBanner.classList.toggle('hidden', !st.offline);
  } catch (e) {
    append('assistant', `Не удалось сохранить настройки: ${e}`);
  }
}

saveBtn?.addEventListener('click', saveSettings);
saveBtn2?.addEventListener('click', saveSettings);
clearBtn?.addEventListener('click', () => { boundaryInput.value = ''; saveSettings(); });
offlineCheckbox?.addEventListener('change', () => { saveSettings(); });

loadSettings();
  parent.appendChild(wrap);
  log.scrollTop = log.scrollHeight;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = input.value.trim();
  if (!msg) return;
  append('user', msg);
  input.value = '';
  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    const el = append('assistant', data.reply);
    renderCitations(el, data.citations);
    // сохраняем последний ответ и цитаты на элементе для экспорта
    el.dataset.reply = data.reply;
    el.dataset.citations = JSON.stringify(data.citations || []);
  } catch (err) {
    append('assistant', `Ошибка: ${err}`);
  }
});

async function exportLastNote() {
  // ищем последний ответ ассистента с данными
  const nodes = Array.from(log.querySelectorAll('.msg.assistant'));
  const last = nodes.reverse().find(n => n.dataset && n.dataset.reply);
  if (!last) {
    saveStatus.textContent = 'Нет ответа для сохранения';
    return;
  }
  const reply = last.dataset.reply;
  const citations = JSON.parse(last.dataset.citations || '[]');
  // 1) Предпросмотр
  try {
    saveStatus.textContent = 'Готовлю предпросмотр…';
    const pr = await fetch('/export/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reply, citations, title: 'Coreader', book: selectedBookMeta })
    });
    if (!pr.ok) throw new Error(await pr.text());
    const preview = await pr.json();
    // показать модалку
    modalContent.value = preview.content || '';
    modalPath.textContent = preview.suggested_path || '';
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');

    const onCancel = () => {
      modal.classList.add('hidden');
      modal.setAttribute('aria-hidden', 'true');
      modalCancel.removeEventListener('click', onCancel);
      modalConfirm.removeEventListener('click', onConfirm);
      saveStatus.textContent = '';
    };
    const onConfirm = async () => {
      try {
        saveStatus.textContent = 'Сохраняю…';
        const r = await fetch('/export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reply, citations, title: 'Coreader', book: selectedBookMeta })
        });
        if (!r.ok) throw new Error(await r.text());
        const out = await r.json();
        saveStatus.textContent = out.status === 'ok' ? `Сохранено: ${out.path}` : `Ошибка: ${out.message}`;
      } catch (e) {
        saveStatus.textContent = `Ошибка экспорта: ${e}`;
      } finally {
        onCancel();
      }
    };
    modalCancel.addEventListener('click', onCancel);
    modalConfirm.addEventListener('click', onConfirm);
  } catch (e) {
    saveStatus.textContent = `Ошибка предпросмотра: ${e}`;
  }
}

saveNoteBtn?.addEventListener('click', exportLastNote);

async function loadSections() {
  if (!sectionsWrap) return;
  sectionsWrap.textContent = 'Загружаю…';
  try {
    const res = await fetch('/progress');
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    const { sections = [], current_seq = null } = data;
    sectionsWrap.innerHTML = '';
    if (!sections.length) {
      sectionsWrap.textContent = 'Разделы не найдены. Выполните переиндексацию.';
      return;
    }
    // Обновим статус в шапке по current_seq
    if (boundaryStatus) boundaryStatus.textContent = (current_seq ?? 'не задана');
    const list = document.createElement('div');
    list.className = 'sections-list';
    sections.forEach((s) => {
      const row = document.createElement('div');
      row.className = 'section-row';
      const title = document.createElement('div');
      title.className = 'section-title';
      title.textContent = s.title;
      const meta = document.createElement('div');
      meta.className = 'section-meta';
      meta.textContent = `seq ${s.min_seq}–${s.max_seq} · ${s.count} фрагм.`;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = 'Считать прочитанным';
      btn.addEventListener('click', async () => {
        if (boundaryInput) boundaryInput.value = String(s.max_seq);
        // Мгновенно обновим статус в шапке
        if (boundaryStatus) boundaryStatus.textContent = String(s.max_seq);
        await saveSettings();
        await loadSections();
      });
      if (current_seq !== null && typeof current_seq === 'number') {
        if (s.min_seq <= current_seq && current_seq <= s.max_seq) {
          row.classList.add('current');
        } else if (s.max_seq <= current_seq) {
          row.classList.add('done');
        }
      }
      const left = document.createElement('div');
      left.className = 'section-left';
      left.appendChild(title);
      left.appendChild(meta);
      row.appendChild(left);
      row.appendChild(btn);
      list.appendChild(row);
    });
    sectionsWrap.appendChild(list);
  } catch (e) {
    sectionsWrap.textContent = `Ошибка загрузки: ${e}`;
  }
}

// начальная загрузка
loadSections();

// -------- Zotero search in preview modal ---------
function renderZotero(items = []) {
  if (!zoteroResults) return;
  zoteroResults.innerHTML = '';
  if (!items.length) {
    zoteroResults.textContent = 'Ничего не найдено';
    return;
  }
  const list = document.createElement('div');
  list.className = 'zotero-list';
  items.forEach((it) => {
    const row = document.createElement('div');
    row.className = 'zotero-row';
    const info = document.createElement('div');
    info.className = 'zotero-info';
    const authors = Array.isArray(it.authors) ? it.authors.join(', ') : (it.authors || '');
    info.textContent = `${it.title || ''}${it.year ? ' (' + it.year + ')' : ''}${authors ? ' — ' + authors : ''}`;
    const pick = document.createElement('button');
    pick.type = 'button';
    pick.textContent = 'Выбрать';
    pick.addEventListener('click', async () => {
      selectedBookMeta = {
        zotero_key: it.zotero_key,
        title: it.title,
        authors: it.authors,
        year: it.year,
        tags: it.tags,
      };
      // перегенерируем предпросмотр с выбранной книгой
      try {
        const last = Array.from(log.querySelectorAll('.msg.assistant')).pop();
        if (!last) return;
        const reply = last.dataset.reply;
        const citations = JSON.parse(last.dataset.citations || '[]');
        const pr = await fetch('/export/preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reply, citations, title: 'Coreader', book: selectedBookMeta })
        });
        if (!pr.ok) throw new Error(await pr.text());
        const preview = await pr.json();
        modalContent.value = preview.content || '';
        modalPath.textContent = preview.suggested_path || '';
      } catch (e) {
        // отрисуем заметку как есть, но сообщим об ошибке
        const warn = document.createElement('div');
        warn.className = 'hint';
        warn.textContent = `Не удалось обновить предпросмотр: ${e}`;
        zoteroResults.prepend(warn);
      }
    });
    row.appendChild(info);
    row.appendChild(pick);
    list.appendChild(row);
  });
  zoteroResults.appendChild(list);
}

zoteroBtn?.addEventListener('click', async () => {
  const q = (zoteroInput?.value || '').trim();
  if (!q) return;
  zoteroResults.textContent = 'Ищу…';
  try {
    const res = await fetch('/zotero/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    renderZotero(data.items || []);
  } catch (e) {
    zoteroResults.textContent = `Ошибка поиска: ${e}`;
  }
});
