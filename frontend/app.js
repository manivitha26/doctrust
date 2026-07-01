const API = 'http://127.0.0.1:8005/api/v1';

// ─── Application State ──────────────────────────────────────────────
let currentWorkspace = 'default';
let currentChatSessionId = null;
let selectedDocIds = [];
let lastSourcesMetadata = [];

// ─── Token Management ──────────────────────────────────────────────
const Auth = {
    // In auth‑less mode we consider the user always logged in.
    isLoggedIn: () => true,
    // No real tokens; API calls will omit Authorization header.
    getAccess: () => null,
    getRefresh: () => null,
    set: () => {},
    clear: () => {},
};

// ─── API Helper ────────────────────────────────────────────────────
async function apiFetch(path, options = {}, retry = true) {
    const headers = { ...(options.headers || {}) };
    if (Auth.getAccess()) headers['Authorization'] = `Bearer ${Auth.getAccess()}`;
    if (!(options.body instanceof FormData)) headers['Content-Type'] = headers['Content-Type'] || 'application/json';

    const res = await fetch(`${API}${path}`, { ...options, headers });

    if (res.status === 401 && retry) {
        // Try to refresh tokens
        const refreshToken = Auth.getRefresh();
        if (!refreshToken) { handleSessionExpired(); return null; }

        const refreshRes = await fetch(`${API}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (refreshRes.ok) {
            const data = await refreshRes.json();
            Auth.set(data.access_token, data.refresh_token);
            return apiFetch(path, options, false); // Retry once
        } else {
            handleSessionExpired();
            return null;
        }
    }
    return res;
}

// ─── Toast Notifications ───────────────────────────────────────────
function toast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');
    const t = document.createElement('div');
    t.className = `toast toast-${type}`;
    const icons = { success: 'ri-check-circle-line', error: 'ri-error-warning-line', info: 'ri-information-line', warning: 'ri-alert-line' };
    t.innerHTML = `<i class="${icons[type] || icons.info}"></i><span>${message}</span><button class="toast-close"><i class="ri-close-line"></i></button>`;
    t.querySelector('.toast-close').onclick = () => t.remove();
    container.appendChild(t);
    requestAnimationFrame(() => t.classList.add('show'));
    setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 400); }, duration);
}

// ─── Theme ─────────────────────────────────────────────────────────
function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const btn = document.getElementById('themeToggleBtn');
    btn.innerHTML = theme === 'dark' ? '<i class="ri-sun-line"></i>' : '<i class="ri-moon-line"></i>';
    localStorage.setItem('dt_theme', theme);
}

// ─── Main App Init ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Theme
    applyTheme(localStorage.getItem('dt_theme') || 'dark');
    document.getElementById('themeToggleBtn').addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        applyTheme(current === 'dark' ? 'light' : 'dark');
    });

    // Show overlay or app
    if (Auth.isLoggedIn()) {
        showApp();
    } else {
        showAuth();
    }

    setupAuth();
    setupApp();
});

// ─── Auth ──────────────────────────────────────────────────────────
function showAuth() {
    document.getElementById('authOverlay').classList.remove('hidden');
}
function showApp() {
    document.getElementById('authOverlay').classList.add('hidden');
    loadUserProfile().catch(() => console.warn('User profile endpoint unavailable, proceeding anonymously.'));
    initChatSessions();
    loadDocuments();
}
function handleSessionExpired() {
    Auth.clear();
    showAuth();
    toast('Your session expired. Please log in again.', 'warning');
}

function setupAuth() {
    const authOverlay = document.getElementById('authOverlay');
    const loginForm = document.getElementById('loginForm');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const authError = document.getElementById('authError');
    const authSuccess = document.getElementById('authSuccess');
    const authSubmitBtn = document.getElementById('authSubmitBtn');
    const authBtnText = document.getElementById('authBtnText');
    const authBtnIcon = document.getElementById('authBtnIcon');
    const authSpinner = document.getElementById('authSpinner');
    const tabLogin = document.getElementById('tabLogin');
    const tabRegister = document.getElementById('tabRegister');
    const togglePwd = document.getElementById('togglePwd');

    let authMode = 'login';

    // Password visibility toggle
    togglePwd.addEventListener('click', () => {
        const isText = passwordInput.type === 'text';
        passwordInput.type = isText ? 'password' : 'text';
        togglePwd.innerHTML = `<i class="ri-eye${isText ? '' : '-off'}-line"></i>`;
    });

    tabLogin.addEventListener('click', () => {
        authMode = 'login';
        tabLogin.classList.add('active'); tabRegister.classList.remove('active');
        authBtnText.textContent = 'Sign In'; authBtnIcon.className = 'ri-arrow-right-line';
        authError.textContent = ''; authSuccess.textContent = '';
    });

    tabRegister.addEventListener('click', () => {
        authMode = 'register';
        tabRegister.classList.add('active'); tabLogin.classList.remove('active');
        authBtnText.textContent = 'Create Account'; authBtnIcon.className = 'ri-user-add-line';
        authError.textContent = ''; authSuccess.textContent = '';
    });

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        authError.textContent = ''; authSuccess.textContent = '';
        authSpinner.classList.remove('hidden');
        authSubmitBtn.disabled = true;

        const email = emailInput.value;
        const password = passwordInput.value;

        try {
            if (authMode === 'register') {
                const res = await fetch(`${API}/auth/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password }),
                });
                const data = await res.json();
                if (res.ok) {
                    authSuccess.textContent = '✓ Account created! Please sign in.';
                    tabLogin.click();
                } else {
                    authError.textContent = data.detail || 'Registration failed.';
                }
            } else {
                const formData = new URLSearchParams();
                formData.append('username', email);
                formData.append('password', password);
                const res = await fetch(`${API}/auth/token`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData,
                });
                const data = await res.json();
                if (res.ok) {
                    Auth.set(data.access_token, data.refresh_token);
                    showApp();
                    toast('Welcome back! You\'re now signed in.', 'success');
                } else {
                    authError.textContent = data.detail || 'Invalid credentials.';
                }
            }
        } catch {
            authError.textContent = 'Cannot connect to the server. Is the backend running?';
        } finally {
            authSpinner.classList.add('hidden');
            authSubmitBtn.disabled = false;
        }
    });
}

// ─── App Logic ─────────────────────────────────────────────────────
function setupApp() {
    const queryForm = document.getElementById('queryForm');
    const queryInput = document.getElementById('queryInput');
    const sendBtn = document.getElementById('sendBtn');
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const logoutBtn = document.getElementById('logoutBtn');
    const clearChatBtn = document.getElementById('clearChatBtn');
    const refreshDocsBtn = document.getElementById('refreshDocsBtn');
    const closeModal = document.querySelector('.close-modal');
    const docModal = document.getElementById('docModal');

    // Logout
    logoutBtn.addEventListener('click', async () => {
        const refreshToken = Auth.getRefresh();
        if (refreshToken) {
            await apiFetch('/auth/logout', {
                method: 'POST',
                body: JSON.stringify({ refresh_token: refreshToken }),
            });
        }
        Auth.clear();
        showAuth();
        toast('Signed out successfully.', 'info');
    });

    // Clear Chat
    clearChatBtn.addEventListener('click', () => {
        const sessions = getSessions();
        const session = sessions.find(s => s.id === currentChatSessionId);
        if (session) {
            session.messages = [];
            session.title = 'New Chat Session';
            saveSessions(sessions);
            renderSessionsList();
            loadCurrentSession();
            toast('Chat session cleared.', 'info');
        }
    });

    // Workspace Selector
    document.getElementById('workspaceSelect').addEventListener('change', (e) => {
        const val = e.target.value;
        if (val === 'new') {
            const newWs = prompt('Enter a name for the new workspace:');
            if (newWs) {
                const cleanWs = newWs.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '');
                if (cleanWs) {
                    const select = e.target;
                    const opt = document.createElement('option');
                    opt.value = cleanWs;
                    opt.textContent = `📁 ${newWs}`;
                    select.insertBefore(opt, select.lastElementChild);
                    select.value = cleanWs;
                    currentWorkspace = cleanWs;
                    toast(`Workspace "${newWs}" created.`, 'success');
                }
            } else {
                e.target.value = currentWorkspace;
            }
        } else {
            currentWorkspace = val;
        }
        selectedDocIds = [];
        initChatSessions();
        loadDocuments();
    });

    // New Chat Session
    document.getElementById('newChatBtn').addEventListener('click', () => {
        const sessions = getSessions();
        const newSession = {
            id: 'session_' + Date.now(),
            title: 'New Chat Session',
            messages: []
        };
        sessions.push(newSession);
        saveSessions(sessions);
        currentChatSessionId = newSession.id;
        renderSessionsList();
        loadCurrentSession();
        toast('New chat session created.', 'success');
    });

    // Export Chat
    document.getElementById('exportChatBtn').addEventListener('click', () => {
        window.print();
    });

    // Refresh docs
    refreshDocsBtn.addEventListener('click', () => loadDocuments());

    // Modal close
    closeModal.addEventListener('click', () => docModal.classList.remove('show'));
    window.addEventListener('click', (e) => { if (e.target === docModal) docModal.classList.remove('show'); });

    // Upload
    uploadZone.addEventListener('click', () => fileInput.click());
    uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('dragover'); });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault(); uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleFileUpload(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener('change', () => { if (fileInput.files.length) handleFileUpload(fileInput.files[0]); });

    // Chat submit
    queryForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const q = queryInput.value.trim();
        if (!q) return;
        appendUserMessage(q);
        queryInput.value = '';
        queryInput.disabled = true; sendBtn.disabled = true;
        fetchQuery(q);
    });
}

// ─── Load User Profile ─────────────────────────────────────────────
async function loadUserProfile() {
    // Auth‑less demo: skip fetching user profile, display mock user.
    document.getElementById('userEmail').textContent = 'guest@docutrust.com';
    document.getElementById('userAvatar').textContent = 'GS';
}

// ─── Documents ─────────────────────────────────────────────────────
let currentDocs = [];

async function loadDocuments() {
    const docItems = document.getElementById('docItems');
    // Show skeletons
    docItems.innerHTML = `
        <li class="skeleton-item"><div class="skeleton skeleton-icon"></div><div class="skeleton-text"><div class="skeleton skeleton-line-long"></div><div class="skeleton skeleton-line-short"></div></div></li>
        <li class="skeleton-item"><div class="skeleton skeleton-icon"></div><div class="skeleton-text"><div class="skeleton skeleton-line-long"></div><div class="skeleton skeleton-line-short"></div></div></li>
    `;

    const res = await apiFetch(`/documents/?workspace=${currentWorkspace}`);
    if (!res) return;

    if (!res.ok) {
        docItems.innerHTML = `<li class="empty-state"><i class="ri-error-warning-line"></i> Failed to load documents.</li>`;
        return;
    }

    const docs = await res.json();
    currentDocs = docs;
    renderDocumentList(docs);
}

function renderDocumentList(docs) {
    const docItems = document.getElementById('docItems');
    const badge = document.getElementById('docCountBadge');
    badge.textContent = docs.length;

    if (docs.length === 0) {
        docItems.innerHTML = `<li class="empty-state"><i class="ri-file-add-line"></i> No documents indexed yet.</li>`;
        return;
    }

    docItems.innerHTML = '';
    docs.forEach(doc => {
        const li = document.createElement('li');
        li.className = 'doc-item';
        li.dataset.docId = doc.id;
        const size = formatFileSize(doc.file_size_bytes);
        const isChecked = selectedDocIds.includes(doc.id);
        
        li.innerHTML = `
            <input type="checkbox" class="doc-item-checkbox" ${isChecked ? 'checked' : ''} onclick="event.stopPropagation(); toggleDocSelect('${doc.id}')">
            <i class="ri-file-pdf-fill doc-pdf-icon"></i>
            <div class="doc-info">
                <div class="doc-name" title="${doc.filename}">${doc.filename}</div>
                <div class="doc-meta">
                    <span class="doc-chunks"><i class="ri-stack-line"></i> ${doc.num_chunks} chunks</span>
                    <span class="doc-size">${size}</span>
                    ${doc.is_scanned ? '<span class="doc-chunks" title="OCR Recovered"><i class="ri-scan-line"></i> OCR</span>' : ''}
                </div>
            </div>
            <span class="doc-status-dot ${doc.status === 'indexed' ? 'indexed' : 'failed'}" title="${doc.status}"></span>
        `;
        li.addEventListener('click', (e) => {
            if (e.target.tagName !== 'INPUT') openDocModal(doc);
        });
        docItems.appendChild(li);
    });

    // Enable chat if there are documents
    document.getElementById('queryInput').disabled = false;
    document.getElementById('sendBtn').disabled = false;
    document.getElementById('queryInput').placeholder = 'Ask a question about your documents...';
}

function toggleDocSelect(id) {
    const index = selectedDocIds.indexOf(id);
    if (index > -1) {
        selectedDocIds.splice(index, 1);
    } else {
        selectedDocIds.push(id);
    }
    renderDocumentList(currentDocs);
}

function openDocModal(doc) {
    document.getElementById('modalDocName').textContent = doc.filename;
    document.getElementById('modalDocChunks').textContent = doc.num_chunks;
    document.getElementById('modalDocSize').textContent = formatFileSize(doc.file_size_bytes);
    document.getElementById('modalDocDate').textContent = `Indexed ${formatDate(doc.created_at)}`;
    
    const deleteBtn = document.getElementById('modalDeleteBtn');
    deleteBtn.onclick = () => deleteDocument(doc.id, doc.filename);
    
    document.getElementById('docModal').classList.add('show');
}

async function deleteDocument(docId, filename) {
    if (!confirm(`Delete "${filename}"? This cannot be undone.`)) return;
    const res = await apiFetch(`/documents/${docId}?workspace=${currentWorkspace}`, { method: 'DELETE' });
    if (res && (res.ok || res.status === 204)) {
        document.getElementById('docModal').classList.remove('show');
        toast(`"${filename}" deleted.`, 'success');
        loadDocuments();
    } else {
        toast('Failed to delete document.', 'error');
    }
}

async function handleFileUpload(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        toast('Only PDF files are supported.', 'error'); return;
    }
    if (file.size > 50 * 1024 * 1024) {
        toast('File exceeds 50MB limit.', 'error'); return;
    }

    const uploadZone = document.getElementById('uploadZone');
    const originalHTML = uploadZone.innerHTML;
    uploadZone.innerHTML = `<div class="upload-content"><div class="upload-progress-ring"></div><h3>Processing...</h3><p>${file.name}</p></div>`;
    uploadZone.classList.add('uploading');

    try {
        const formData = new FormData();
        formData.append('file', file);
        const res = await apiFetch(`/documents/upload?workspace=${currentWorkspace}`, { method: 'POST', body: formData });

        if (!res) return;
        if (!res.ok) {
            const err = await res.json();
            toast(err.detail || 'Upload failed.', 'error');
            return;
        }

        const data = await res.json();
        toast(`✓ "${data.filename}" indexed with ${data.num_chunks} chunks.`, 'success', 6000);
        loadDocuments();
    } catch (err) {
        toast('Upload failed. Is the backend running?', 'error');
    } finally {
        uploadZone.innerHTML = originalHTML;
        uploadZone.classList.remove('uploading');
    }
}

// ─── Chat Sessions & History ───────────────────────────────────────
function getSessions() {
    const allSessions = JSON.parse(localStorage.getItem('dt_sessions') || '{}');
    if (!allSessions[currentWorkspace]) {
        allSessions[currentWorkspace] = [];
    }
    return allSessions[currentWorkspace];
}

function saveSessions(sessions) {
    const allSessions = JSON.parse(localStorage.getItem('dt_sessions') || '{}');
    allSessions[currentWorkspace] = sessions;
    localStorage.setItem('dt_sessions', JSON.stringify(allSessions));
}

function initChatSessions() {
    const sessions = getSessions();
    if (sessions.length === 0) {
        const newSession = {
            id: 'session_' + Date.now(),
            title: 'New Chat Session',
            messages: []
        };
        sessions.push(newSession);
        saveSessions(sessions);
    }
    currentChatSessionId = sessions[0].id;
    renderSessionsList();
    loadCurrentSession();
}

function renderSessionsList() {
    const container = document.getElementById('chatSessions');
    container.innerHTML = '';
    const sessions = getSessions();
    
    sessions.forEach(session => {
        const li = document.createElement('li');
        li.className = `session-item ${session.id === currentChatSessionId ? 'active' : ''}`;
        li.innerHTML = `
            <span class="session-name" title="${session.title}"><i class="ri-chat-3-line"></i> ${session.title}</span>
            <button class="session-delete-btn" onclick="event.stopPropagation(); deleteSession('${session.id}')" title="Delete session"><i class="ri-delete-bin-line"></i></button>
        `;
        li.addEventListener('click', () => {
            currentChatSessionId = session.id;
            renderSessionsList();
            loadCurrentSession();
        });
        container.appendChild(li);
    });
}

function deleteSession(sessionId) {
    let sessions = getSessions();
    if (sessions.length <= 1) {
        toast('Cannot delete the last chat session.', 'warning');
        return;
    }
    if (!confirm('Are you sure you want to delete this chat session?')) return;
    sessions = sessions.filter(s => s.id !== sessionId);
    saveSessions(sessions);
    if (currentChatSessionId === sessionId) {
        currentChatSessionId = sessions[0].id;
    }
    renderSessionsList();
    loadCurrentSession();
}

function loadCurrentSession() {
    const sessions = getSessions();
    const session = sessions.find(s => s.id === currentChatSessionId);
    const messagesDiv = document.getElementById('messages');
    messagesDiv.innerHTML = '';
    
    document.getElementById('sourceDrawer').classList.add('hidden');
    
    if (!session || session.messages.length === 0) {
        messagesDiv.innerHTML = `<div class="message system-msg welcome-msg"><div class="msg-avatar"><i class="ri-shield-check-line"></i></div><div class="msg-content"><p>Welcome! Ask a question about your documents in this workspace.</p></div></div>`;
        document.getElementById('confidenceMeter').classList.add('hidden');
        return;
    }
    
    session.messages.forEach(m => {
        if (m.role === 'user') appendUserMessage(m.content, false);
        else appendSystemMessage(m.content, false, m.id, m.confidence);
    });
    
    const lastMsg = session.messages[session.messages.length - 1];
    if (lastMsg && lastMsg.role === 'system' && lastMsg.confidence) {
        showConfidence(lastMsg.confidence);
    } else {
        document.getElementById('confidenceMeter').classList.add('hidden');
    }
}

// ─── Confidence Meter ──────────────────────────────────────────────
function showConfidence(score) {
    const meter = document.getElementById('confidenceMeter');
    const bar = document.getElementById('meterBar');
    const val = document.getElementById('meterVal');
    
    meter.classList.remove('hidden');
    val.textContent = Math.round(score) + '%';
    bar.style.width = score + '%';
    
    meter.classList.remove('confidence-high', 'confidence-medium', 'confidence-low');
    if (score >= 80) meter.classList.add('confidence-high');
    else if (score >= 50) meter.classList.add('confidence-medium');
    else meter.classList.add('confidence-low');
}

// ─── Source Preview Drawer ─────────────────────────────────────────
function previewSource(citationStr) {
    const parts = citationStr.split(',');
    const docName = parts[0].trim();
    const pageNum = parts[1] ? parts[1].replace(/Page/i, '').trim() : '1';
    
    const drawer = document.getElementById('sourceDrawer');
    const body = document.getElementById('sourceDrawerBody');
    
    drawer.classList.remove('hidden');
    
    const match = lastSourcesMetadata.find(s => 
        s.source.toLowerCase().includes(docName.toLowerCase()) && 
        String(s.page) === pageNum
    );
    
    if (match) {
        const query = document.getElementById('queryInput').value || "";
        let text = escapeHtml(match.text);
        const terms = query.toLowerCase().split(/\s+/).filter(t => t.length > 2);
        terms.forEach(term => {
            const regex = new RegExp(`(${term})`, 'gi');
            text = text.replace(regex, '<span class="highlight">$1</span>');
        });
        
        body.innerHTML = `
            <div class="source-item">
                <div class="source-meta">
                    <span>📄 ${match.source}</span>
                    <span>Page ${match.page}</span>
                </div>
                <div class="source-text">${text}</div>
            </div>
        `;
    } else {
        body.innerHTML = `
            <div class="source-item">
                <div class="source-meta">
                    <span>📄 ${docName}</span>
                    <span>Page ${pageNum}</span>
                </div>
                <div class="source-text">Source text unavailable. Make sure the document search was completed.</div>
            </div>
        `;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('closeDrawerBtn');
    if (btn) btn.addEventListener('click', () => {
        document.getElementById('sourceDrawer').classList.add('hidden');
    });
});

// ─── User Feedback ─────────────────────────────────────────────────
async function submitFeedback(messageId, type, btn) {
    const parent = btn.parentElement;
    parent.querySelectorAll('.feedback-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    
    try {
        const res = await apiFetch('/documents/feedback', {
            method: 'POST',
            body: JSON.stringify({ message_id: messageId, feedback: type })
        });
        if (res && res.ok) {
            toast('✓ Feedback submitted. Thank you!', 'success');
        }
    } catch {
        toast('Failed to record feedback.', 'error');
    }
}

// ─── Query Pipeline ────────────────────────────────────────────────
async function fetchQuery(query) {
    const messages = document.getElementById('messages');
    const msgId = 'msg_' + Date.now();
    
    const msgWrapper = document.createElement('div');
    msgWrapper.className = 'message system-msg';
    msgWrapper.dataset.messageId = msgId;
    
    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.innerHTML = '<i class="ri-shield-check-line"></i>';
    
    const content = document.createElement('div');
    content.className = 'msg-content';
    
    const loader = document.createElement('div');
    loader.className = 'typing-indicator';
    loader.innerHTML = '<span></span><span></span><span></span>';
    content.appendChild(loader);
    
    msgWrapper.appendChild(avatar); msgWrapper.appendChild(content);
    messages.appendChild(msgWrapper);
    scrollToBottom();

    let finalAnswer = '';
    let lastConfidence = 0;
    
    const answerTextDiv = document.createElement('div');
    answerTextDiv.className = 'answer-text';
    content.appendChild(answerTextDiv);

    try {
        const res = await fetch(`${API}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${Auth.getAccess()}`,
            },
            body: JSON.stringify({
                query,
                document_ids: selectedDocIds.length > 0 ? selectedDocIds : null
            }),
        });

        if (res.status === 401) { handleSessionExpired(); return; }
        if (!res.ok) { toast('Query failed. Please try again.', 'error'); loader.remove(); return; }

        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let currentEvent = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const lines = decoder.decode(value, { stream: true }).split('\n');
            for (const line of lines) {
                if (line.startsWith('event: ')) { currentEvent = line.substring(7).trim(); }
                else if (line.startsWith('data: ')) {
                    const data = line.substring(6).trim();
                    
                    if (currentEvent === 'log') {
                        const logDiv = document.createElement('div');
                        logDiv.className = 'agent-log';
                        if (data.toLowerCase().includes('grad')) logDiv.classList.add('grading');
                        else if (data.toLowerCase().includes('rewrit')) logDiv.classList.add('rewriting');
                        else if (data.toLowerCase().includes('generat')) logDiv.classList.add('generating');
                        else if (data.toLowerCase().includes('search')) logDiv.classList.add('searching');
                        logDiv.innerHTML = `<i class="ri-terminal-line"></i> ${data}`;
                        content.insertBefore(logDiv, loader);
                    } 
                    else if (currentEvent === 'metadata') {
                        const meta = JSON.parse(data);
                        lastConfidence = meta.confidence_score;
                        lastSourcesMetadata = meta.sources;
                        showConfidence(lastConfidence);
                    }
                    else if (currentEvent === 'token') {
                        loader.remove();
                        finalAnswer += data;
                        
                        let html = typeof marked !== 'undefined' ? marked.parse(finalAnswer) : escapeHtml(finalAnswer).replace(/\n/g, '<br>');
                        html = html.replace(/\[Source:[^\]]+\]/g, m =>
                            `<span class="citation" onclick="previewSource('${m.slice(8, -1).replace(/'/g, "\\'")}')"><i class="ri-bookmark-3-line"></i> ${m.slice(1,-1)}</span>`
                        );
                        answerTextDiv.innerHTML = html;
                    }
                    else if (currentEvent === 'result') {
                        loader.remove();
                        if (!finalAnswer) {
                            finalAnswer = data;
                            let html = typeof marked !== 'undefined' ? marked.parse(finalAnswer) : escapeHtml(finalAnswer).replace(/\n/g, '<br>');
                            html = html.replace(/\[Source:[^\]]+\]/g, m =>
                                `<span class="citation" onclick="previewSource('${m.slice(8, -1).replace(/'/g, "\\'")}')"><i class="ri-bookmark-3-line"></i> ${m.slice(1,-1)}</span>`
                            );
                            answerTextDiv.innerHTML = html;
                        }
                    }
                    scrollToBottom();
                }
            }
        }

        const feedbackDiv = document.createElement('div');
        feedbackDiv.className = 'msg-feedback';
        feedbackDiv.innerHTML = `
            <button class="feedback-btn like" onclick="submitFeedback('${msgId}', 'like', this)" title="Thumbs Up"><i class="ri-thumb-up-line"></i></button>
            <button class="feedback-btn dislike" onclick="submitFeedback('${msgId}', 'dislike', this)" title="Thumbs Down"><i class="ri-thumb-down-line"></i></button>
        `;
        content.appendChild(feedbackDiv);

        if (finalAnswer) {
            const sessions = getSessions();
            const session = sessions.find(s => s.id === currentChatSessionId);
            if (session) {
                if (session.messages.length === 1 && session.title === 'New Chat Session') {
                    session.title = session.messages[0].content.slice(0, 25) + '...';
                    renderSessionsList();
                }
                session.messages.push({
                    id: msgId,
                    role: 'system',
                    content: finalAnswer,
                    confidence: lastConfidence
                });
                saveSessions(sessions);
            }
        }
    } catch (err) {
        loader.remove();
        const errP = document.createElement('p');
        errP.className = 'error-msg';
        errP.textContent = 'Failed to process query.';
        content.appendChild(errP);
        toast('Query failed. Check backend connection.', 'error');
    } finally {
        document.getElementById('queryInput').disabled = false;
        document.getElementById('sendBtn').disabled = false;
        document.getElementById('queryInput').focus();
        scrollToBottom();
    }
}

function appendUserMessage(text, save = true) {
    if (save) {
        const sessions = getSessions();
        const session = sessions.find(s => s.id === currentChatSessionId);
        if (session) {
            session.messages.push({ role: 'user', content: text });
            saveSessions(sessions);
        }
    }
    const msg = document.createElement('div');
    msg.className = 'message user-msg';
    msg.innerHTML = `<div class="msg-avatar"><i class="ri-user-line"></i></div><div class="msg-content"><p>${escapeHtml(text)}</p></div>`;
    document.getElementById('messages').appendChild(msg);
    scrollToBottom();
}

function appendSystemMessage(text, save = true, messageId = null, confidence = 0) {
    const msgId = messageId || 'msg_' + Date.now();
    if (save) {
        const sessions = getSessions();
        const session = sessions.find(s => s.id === currentChatSessionId);
        if (session) {
            session.messages.push({ id: msgId, role: 'system', content: text, confidence });
            saveSessions(sessions);
        }
    }
    const msg = document.createElement('div');
    msg.className = 'message system-msg';
    msg.dataset.messageId = msgId;
    
    let html = typeof marked !== 'undefined' ? marked.parse(text) : escapeHtml(text).replace(/\n/g, '<br>');
    html = html.replace(/\[Source:[^\]]+\]/g, m =>
        `<span class="citation" onclick="previewSource('${m.slice(8, -1).replace(/'/g, "\\'")}')"><i class="ri-bookmark-3-line"></i> ${m.slice(1,-1)}</span>`
    );
    
    msg.innerHTML = `
        <div class="msg-avatar"><i class="ri-shield-check-line"></i></div>
        <div class="msg-content">
            <div class="answer-text">${html}</div>
            <div class="msg-feedback">
                <button class="feedback-btn like" onclick="submitFeedback('${msgId}', 'like', this)" title="Thumbs Up"><i class="ri-thumb-up-line"></i></button>
                <button class="feedback-btn dislike" onclick="submitFeedback('${msgId}', 'dislike', this)" title="Thumbs Down"><i class="ri-thumb-down-line"></i></button>
            </div>
        </div>
    `;
    document.getElementById('messages').appendChild(msg);
    scrollToBottom();
}

// ─── Utilities ─────────────────────────────────────────────────────
function scrollToBottom() {
    const m = document.getElementById('messages');
    m.scrollTop = m.scrollHeight;
}

function formatFileSize(bytes) {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(isoString) {
    if (!isoString) return '';
    const d = new Date(isoString);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function escapeHtml(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
