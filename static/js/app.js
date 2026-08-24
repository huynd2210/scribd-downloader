/**
 * Scribd Downloader Web Application - Frontend Client
 */

let currentTaskId = null;
let eventSource = null;
let currentPreviewFilename = null;
let historyItemsCache = [];

document.addEventListener('DOMContentLoaded', () => {
    fetchDownloadsHistory();
});

/* URL Validation & Input Handling */
function handleUrlInput(url) {
    url = url.trim();
    const validationMsg = document.getElementById('url-validation-msg');
    const embedBox = document.getElementById('embed-preview-box');
    const embedUrlText = document.getElementById('embed-url-text');
    const filenameText = document.getElementById('output-filename-text');
    const clearBtn = document.getElementById('clear-url-btn');

    clearBtn.style.display = url ? 'block' : 'none';

    if (!url) {
        validationMsg.textContent = '';
        validationMsg.className = 'url-validation-msg';
        embedBox.classList.add('hidden');
        return;
    }

    fetch('/api/validate-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
    })
    .then(res => res.json())
    .then(data => {
        if (data.valid) {
            validationMsg.textContent = '✓ Valid Scribd Document Link';
            validationMsg.className = 'url-validation-msg valid';
            embedUrlText.textContent = data.embed_url;
            filenameText.textContent = data.filename;
            embedBox.classList.remove('hidden');
        } else {
            validationMsg.textContent = '✕ Invalid Scribd URL format (Use document or doc link)';
            validationMsg.className = 'url-validation-msg invalid';
            embedBox.classList.add('hidden');
        }
    })
    .catch(() => {
        validationMsg.textContent = '';
    });
}

function clearUrlInput() {
    const input = document.getElementById('scribd-url');
    input.value = '';
    handleUrlInput('');
    input.focus();
}

/* Settings Drawer Toggle */
function toggleSettingsDrawer() {
    const drawer = document.getElementById('settings-drawer');
    const arrow = document.getElementById('settings-arrow');
    drawer.classList.toggle('hidden');
    arrow.classList.toggle('rotated');
}

/* Download Form Submission */
function handleDownload(e) {
    e.preventDefault();

    const url = document.getElementById('scribd-url').value.trim();
    if (!url) return;

    const scroll_delay = parseFloat(document.getElementById('scroll-delay').value) || 0.15;
    const cdp_timeout = parseInt(document.getElementById('cdp-timeout').value) || 600;
    const settle_timeout = parseInt(document.getElementById('settle-timeout').value) || 30;
    const headless = document.getElementById('headless-mode').checked;

    const submitBtn = document.getElementById('submit-btn');
    submitBtn.disabled = true;
    submitBtn.querySelector('span').textContent = 'Initializing Export...';

    fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, scroll_delay, cdp_timeout, settle_timeout, headless })
    })
    .then(res => {
        if (!res.ok) throw new Error('Server returned invalid response.');
        return res.json();
    })
    .then(data => {
        currentTaskId = data.task_id;
        showTaskCard(data.filename);
        connectEventSource(data.task_id);
    })
    .catch(err => {
        alert('Failed to start download task: ' + err.message);
        submitBtn.disabled = false;
        submitBtn.querySelector('span').textContent = 'Start PDF Export';
    });
}

/* Task Progress UI & Streaming Log Reader */
function showTaskCard(filename) {
    const taskCard = document.getElementById('task-card');
    taskCard.classList.remove('hidden');

    document.getElementById('task-filename-text').textContent = filename;
    document.getElementById('task-title').textContent = 'Exporting Document...';
    document.getElementById('task-stage-badge').textContent = 'INITIALIZING';
    document.getElementById('progress-percent').textContent = '0%';
    document.getElementById('progress-bar-fill').style.width = '0%';
    document.getElementById('page-counter-text').textContent = 'Scrolled 0 pages';
    document.getElementById('completion-actions').classList.add('hidden');

    clearConsoleLog();
    addConsoleLog('[System] Initiating headless browser session...', 'log-info');

    resetStepper();
    updateStepper('step-browser');

    // Scroll to task card
    taskCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function connectEventSource(taskId) {
    if (eventSource) eventSource.close();

    eventSource = new EventSource(`/api/events/${taskId}`);

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateTaskProgressUI(data);

        if (data.status === 'COMPLETED' || data.status === 'FAILED') {
            eventSource.close();
            const submitBtn = document.getElementById('submit-btn');
            submitBtn.disabled = false;
            submitBtn.querySelector('span').textContent = 'Start PDF Export';
        }
    };

    eventSource.onerror = () => {
        eventSource.close();
        // Fallback polling if EventSource fails
        pollTaskStatus(taskId);
    };
}

function pollTaskStatus(taskId) {
    const interval = setInterval(() => {
        fetch(`/api/status/${taskId}`)
            .then(res => res.json())
            .then(data => {
                updateTaskProgressUI(data);
                if (data.status === 'COMPLETED' || data.status === 'FAILED') {
                    clearInterval(interval);
                    const submitBtn = document.getElementById('submit-btn');
                    submitBtn.disabled = false;
                    submitBtn.querySelector('span').textContent = 'Start PDF Export';
                }
            });
    }, 1000);
}

function updateTaskProgressUI(data) {
    const stageBadge = document.getElementById('task-stage-badge');
    const percentText = document.getElementById('progress-percent');
    const progressFill = document.getElementById('progress-bar-fill');
    const counterText = document.getElementById('page-counter-text');
    const statusText = document.getElementById('progress-status-text');

    stageBadge.textContent = data.stage || data.status;
    percentText.textContent = `${data.progress_percent || 0}%`;
    progressFill.style.width = `${data.progress_percent || 0}%`;

    if (data.total_pages > 0) {
        counterText.textContent = `Scrolled ${data.current_page} / ${data.total_pages} pages`;
    }

    // Process new log lines
    if (data.new_logs && data.new_logs.length > 0) {
        data.new_logs.forEach(msg => addConsoleLog(msg));
    }

    // Update Stage Stepper & Descriptions
    switch (data.stage) {
        case 'STARTING_BROWSER':
        case 'LOADING_PAGE':
            statusText.textContent = 'Launching browser and loading embed...';
            updateStepper('step-browser');
            break;
        case 'SCROLLING_PAGES':
            statusText.textContent = 'Scrolling through lazy-loaded document pages...';
            updateStepper('step-scroll');
            break;
        case 'PREPARING_PRINT':
        case 'WAITING_RENDER':
            statusText.textContent = 'Cleaning overlays & stabilizing typography/math...';
            updateStepper('step-style');
            break;
        case 'GENERATING_PDF':
            statusText.textContent = 'Exporting PDF via Chrome DevTools Protocol...';
            updateStepper('step-cdp');
            break;
        case 'COMPLETED':
            statusText.textContent = 'PDF generated successfully!';
            document.getElementById('task-title').textContent = 'Export Complete!';
            document.getElementById('task-spinner').className = 'fa-solid fa-circle-check icon-success';
            completeAllStepper();
            showCompletionActions(data.result);
            fetchDownloadsHistory();
            break;
        case 'ERROR':
            statusText.textContent = 'Export failed: ' + (data.error || 'Unknown error');
            document.getElementById('task-title').textContent = 'Export Failed';
            document.getElementById('task-spinner').className = 'fa-solid fa-triangle-exclamation icon-error';
            break;
    }
}

function showCompletionActions(result) {
    if (!result) return;
    currentPreviewFilename = result.filename;
    const actionsBox = document.getElementById('completion-actions');
    const downloadBtn = document.getElementById('btn-download-task');
    downloadBtn.href = `/api/downloads/${encodeURIComponent(result.filename)}`;
    actionsBox.classList.remove('hidden');
}

function previewCurrentTask() {
    if (currentPreviewFilename) {
        openPdfModal(currentPreviewFilename);
    }
}

/* Stepper logic */
function resetStepper() {
    ['step-browser', 'step-scroll', 'step-style', 'step-cdp'].forEach(id => {
        document.getElementById(id).className = 'step-item';
    });
    ['line-1', 'line-2', 'line-3'].forEach(id => {
        document.getElementById(id).className = 'step-line';
    });
}

function updateStepper(activeId) {
    const steps = ['step-browser', 'step-scroll', 'step-style', 'step-cdp'];
    const lines = ['line-1', 'line-2', 'line-3'];

    let activeFound = false;
    steps.forEach((id, idx) => {
        const el = document.getElementById(id);
        if (id === activeId) {
            el.className = 'step-item active';
            activeFound = true;
        } else if (!activeFound) {
            el.className = 'step-item completed';
            if (idx > 0) document.getElementById(lines[idx - 1]).className = 'step-line active';
        } else {
            el.className = 'step-item';
        }
    });
}

function completeAllStepper() {
    ['step-browser', 'step-scroll', 'step-style', 'step-cdp'].forEach(id => {
        document.getElementById(id).className = 'step-item completed';
    });
    ['line-1', 'line-2', 'line-3'].forEach(id => {
        document.getElementById(id).className = 'step-line active';
    });
}

/* Console Log feed */
function addConsoleLog(msg, customClass = '') {
    const logsBox = document.getElementById('console-logs');
    const div = document.createElement('div');

    let className = 'log-line ' + customClass;
    if (msg.includes('Error') || msg.includes('failed')) className += ' log-error';
    else if (msg.includes('Successfully') || msg.includes('complete')) className += ' log-success';

    div.className = className;
    div.textContent = msg;
    logsBox.appendChild(div);
    logsBox.scrollTop = logsBox.scrollHeight;
}

function clearConsoleLog() {
    document.getElementById('console-logs').innerHTML = '';
}

/* History Gallery & Manager */
function fetchDownloadsHistory() {
    fetch('/api/downloads')
        .then(res => res.json())
        .then(data => {
            historyItemsCache = data.downloads || [];
            renderHistoryList(historyItemsCache);
        })
        .catch(() => {});
}

function renderHistoryList(items) {
    const listContainer = document.getElementById('history-list');
    const emptyState = document.getElementById('history-empty-state');

    if (!items || items.length === 0) {
        listContainer.innerHTML = '';
        listContainer.appendChild(emptyState);
        emptyState.classList.remove('hidden');
        return;
    }

    listContainer.innerHTML = '';
    items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'history-item';
        div.innerHTML = `
            <div class="history-item-main">
                <div class="file-icon"><i class="fa-solid fa-file-pdf"></i></div>
                <div class="file-details">
                    <div class="file-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</div>
                    <div class="file-meta">
                        <span><i class="fa-solid fa-file"></i> ${item.filename}</span>
                        <span><i class="fa-solid fa-hard-drive"></i> ${item.size_mb} MB</span>
                        ${item.pages !== 'N/A' ? `<span><i class="fa-solid fa-book-open"></i> ${item.pages} p.</span>` : ''}
                    </div>
                </div>
            </div>
            <div class="history-actions">
                <button type="button" class="btn btn-sm btn-secondary" onclick="openPdfModal('${escapeHtml(item.filename)}')">
                    <i class="fa-solid fa-eye"></i> Preview
                </button>
                <a href="/api/downloads/${encodeURIComponent(item.filename)}" class="btn btn-sm btn-primary" download>
                    <i class="fa-solid fa-download"></i>
                </a>
                <button type="button" class="btn-icon" onclick="deleteHistoryItem('${escapeHtml(item.filename)}')">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </div>
        `;
        listContainer.appendChild(div);
    });
}

function filterHistory(query) {
    query = query.toLowerCase().trim();
    if (!query) {
        renderHistoryList(historyItemsCache);
        return;
    }
    const filtered = historyItemsCache.filter(item => 
        item.title.toLowerCase().includes(query) || 
        item.filename.toLowerCase().includes(query)
    );
    renderHistoryList(filtered);
}

function deleteHistoryItem(filename) {
    if (!confirm(`Delete "${filename}"?`)) return;
    fetch(`/api/downloads/${encodeURIComponent(filename)}`, { method: 'DELETE' })
        .then(res => res.json())
        .then(() => fetchDownloadsHistory());
}

/* PDF Viewer Modal */
function openPdfModal(filename) {
    const modal = document.getElementById('pdf-modal');
    const iframe = document.getElementById('pdf-iframe');
    const filenameLabel = document.getElementById('modal-filename');
    const downloadLink = document.getElementById('modal-download-link');

    filenameLabel.textContent = filename;
    downloadLink.href = `/api/downloads/${encodeURIComponent(filename)}`;
    iframe.src = `/api/downloads/${encodeURIComponent(filename)}`;

    modal.classList.remove('hidden');
}

function closePdfModal() {
    const modal = document.getElementById('pdf-modal');
    const iframe = document.getElementById('pdf-iframe');
    iframe.src = '';
    modal.classList.add('hidden');
}

function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, function (m) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
    });
}
