// ─── JARVIS Frontend ────────────────────────────────────────────────────
(() => {
    'use strict';

    // ─── State ──────────────────────────────────────────────────────────
    const state = {
        sessionId: crypto.randomUUID(),
        ws: null,
        connected: false,
        recording: false,
        mediaRecorder: null,
        audioChunks: [],
        attachments: [],
        keysReady: false,
    };

    // ─── DOM ────────────────────────────────────────────────────────────
    const $ = (s) => document.querySelector(s);
    const $$ = (s) => document.querySelectorAll(s);

    const DOM = {
        messages: $('#messages'),
        input: $('#message-input'),
        sendBtn: $('#send-btn'),
        voiceBtn: $('#voice-btn'),
        uploadBtn: $('#upload-btn'),
        linkBtn: $('#link-btn'),
        folderBtn: $('#folder-btn'),
        fileInput: $('#file-input'),
        folderInput: $('#folder-input'),
        attachPreview: $('#attachment-preview'),
        attachItems: $('#attachment-items'),
        typingIndicator: $('#typing-indicator'),
        connectionDot: $('#connection-dot'),
        connectionStatus: $('#connection-status'),
        agentList: $('#agent-list'),
        memoryList: $('#memory-list'),
        evolutionStats: $('#evolution-stats'),
        dropOverlay: $('#drop-overlay'),
        newChatBtn: $('#new-chat-btn'),
        chatContainer: $('#chat-container'),
        // Setup
        setupScreen: $('#setup-screen'),
        setupAnthropicKey: $('#setup-anthropic-key'),
        setupOpenaiKey: $('#setup-openai-key'),
        setupSaveBtn: $('#setup-save-btn'),
        setupError: $('#setup-error'),
        setupValidating: $('#setup-validating'),
        // Settings modal
        settingsBtn: $('#settings-btn'),
        settingsModal: $('#settings-modal'),
        modalCloseBtn: $('#modal-close-btn'),
        modalAnthropicKey: $('#modal-anthropic-key'),
        modalOpenaiKey: $('#modal-openai-key'),
        modalAnthropicStatus: $('#modal-anthropic-status'),
        modalOpenaiStatus: $('#modal-openai-status'),
        modalSaveBtn: $('#modal-save-btn'),
        modalClearBtn: $('#modal-clear-btn'),
        modalError: $('#modal-error'),
        modalValidating: $('#modal-validating'),
    };

    // ─── API Key Management ─────────────────────────────────────────────

    async function checkKeyStatus() {
        try {
            const res = await fetch('/api/keys/status');
            const data = await res.json();
            state.keysReady = data.ready;

            if (!data.ready) {
                showSetupScreen();
            } else {
                hideSetupScreen();
                connect();
            }
            return data;
        } catch (e) {
            console.error('Failed to check key status:', e);
            // Server might be starting up, retry
            setTimeout(checkKeyStatus, 2000);
        }
    }

    function showSetupScreen() {
        DOM.setupScreen.classList.remove('hidden');
    }

    function hideSetupScreen() {
        DOM.setupScreen.classList.add('hidden');
    }

    async function handleSetupSave() {
        const anthropicKey = DOM.setupAnthropicKey.value.trim();
        const openaiKey = DOM.setupOpenaiKey.value.trim();

        // Validate
        if (!anthropicKey) {
            showError(DOM.setupError, 'Anthropic API key is required.');
            return;
        }

        if (!anthropicKey.startsWith('sk-ant-')) {
            showError(DOM.setupError, 'Anthropic key should start with "sk-ant-". Please check your key.');
            return;
        }

        hideError(DOM.setupError);
        DOM.setupSaveBtn.disabled = true;
        DOM.setupValidating.classList.remove('hidden');

        try {
            // Validate key with server
            const valRes = await fetch('/api/keys/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ anthropic: anthropicKey }),
            });
            const valData = await valRes.json();

            if (!valData.results.anthropic) {
                showError(DOM.setupError, 'Invalid Anthropic API key. Please check the key and try again.');
                DOM.setupSaveBtn.disabled = false;
                DOM.setupValidating.classList.add('hidden');
                return;
            }

            // Save keys
            const body = { anthropic: anthropicKey };
            if (openaiKey) body.openai = openaiKey;

            const saveRes = await fetch('/api/keys/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const saveData = await saveRes.json();

            if (saveData.ok) {
                state.keysReady = true;
                hideSetupScreen();
                connect();
            } else {
                showError(DOM.setupError, saveData.error || 'Failed to save keys.');
            }
        } catch (e) {
            showError(DOM.setupError, 'Connection error. Is the server running?');
        }

        DOM.setupSaveBtn.disabled = false;
        DOM.setupValidating.classList.add('hidden');
    }

    // ─── Settings Modal ─────────────────────────────────────────────────

    function openSettings() {
        DOM.settingsModal.classList.remove('hidden');
        hideError(DOM.modalError);
        DOM.modalValidating.classList.add('hidden');

        // Load current status
        fetch('/api/keys/status').then(r => r.json()).then(data => {
            DOM.modalAnthropicStatus.textContent = data.anthropic.set
                ? `Active: ${data.anthropic.preview}`
                : 'Not configured';
            DOM.modalAnthropicStatus.className = `key-status ${data.anthropic.set ? 'ok' : 'missing'}`;

            DOM.modalOpenaiStatus.textContent = data.openai.set
                ? `Active: ${data.openai.preview}`
                : 'Not configured (voice disabled)';
            DOM.modalOpenaiStatus.className = `key-status ${data.openai.set ? 'ok' : 'missing'}`;

            // Clear inputs
            DOM.modalAnthropicKey.value = '';
            DOM.modalOpenaiKey.value = '';
            DOM.modalAnthropicKey.placeholder = data.anthropic.set ? `Current: ${data.anthropic.preview}` : 'sk-ant-...';
            DOM.modalOpenaiKey.placeholder = data.openai.set ? `Current: ${data.openai.preview}` : 'sk-...';
        });
    }

    function closeSettings() {
        DOM.settingsModal.classList.add('hidden');
    }

    async function handleModalSave() {
        const anthropicKey = DOM.modalAnthropicKey.value.trim();
        const openaiKey = DOM.modalOpenaiKey.value.trim();

        if (!anthropicKey && !openaiKey) {
            showError(DOM.modalError, 'Enter at least one key to update.');
            return;
        }

        hideError(DOM.modalError);
        DOM.modalSaveBtn.disabled = true;
        DOM.modalValidating.classList.remove('hidden');

        try {
            // Validate if new anthropic key provided
            if (anthropicKey) {
                const valRes = await fetch('/api/keys/validate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ anthropic: anthropicKey }),
                });
                const valData = await valRes.json();
                if (!valData.results.anthropic) {
                    showError(DOM.modalError, 'Invalid Anthropic API key.');
                    DOM.modalSaveBtn.disabled = false;
                    DOM.modalValidating.classList.add('hidden');
                    return;
                }
            }

            const body = {};
            if (anthropicKey) body.anthropic = anthropicKey;
            if (openaiKey) body.openai = openaiKey;

            const res = await fetch('/api/keys/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await res.json();

            if (data.ok) {
                state.keysReady = true;
                closeSettings();
                // Reconnect websocket to pick up new session
                if (state.ws) state.ws.close();
                connect();
            } else {
                showError(DOM.modalError, data.error || 'Failed to save.');
            }
        } catch (e) {
            showError(DOM.modalError, 'Connection error.');
        }

        DOM.modalSaveBtn.disabled = false;
        DOM.modalValidating.classList.add('hidden');
    }

    async function handleModalClear() {
        if (!confirm('Clear all API keys? JARVIS will stop working until you enter new keys.')) return;

        try {
            await fetch('/api/keys/clear', { method: 'POST' });
            state.keysReady = false;
            closeSettings();
            if (state.ws) state.ws.close();
            showSetupScreen();
        } catch (e) {
            showError(DOM.modalError, 'Failed to clear keys.');
        }
    }

    function showError(el, msg) {
        el.textContent = msg;
        el.classList.remove('hidden');
    }

    function hideError(el) {
        el.classList.add('hidden');
    }

    // Toggle password visibility
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.toggle-vis-btn');
        if (!btn) return;
        const targetId = btn.dataset.target;
        const input = document.getElementById(targetId);
        if (input) {
            input.type = input.type === 'password' ? 'text' : 'password';
        }
    });

    // ─── WebSocket ──────────────────────────────────────────────────────
    function connect() {
        if (!state.keysReady) return;
        if (state.ws && (state.ws.readyState === WebSocket.OPEN || state.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
        state.ws = new WebSocket(`${protocol}://${location.host}/ws/${state.sessionId}`);

        state.ws.onopen = () => {
            state.connected = true;
            DOM.connectionDot.className = 'dot connected';
            DOM.connectionStatus.textContent = 'Connected';
        };

        state.ws.onclose = () => {
            state.connected = false;
            DOM.connectionDot.className = 'dot disconnected';
            DOM.connectionStatus.textContent = 'Disconnected';
            if (state.keysReady) setTimeout(connect, 3000);
        };

        state.ws.onerror = () => {
            DOM.connectionStatus.textContent = 'Error';
        };

        state.ws.onmessage = (evt) => {
            const data = JSON.parse(evt.data);
            handleWSMessage(data);
        };
    }

    function handleWSMessage(data) {
        switch (data.type) {
            case 'thinking':
                showTyping(true);
                break;

            case 'response':
                if (data.data?.partial) {
                    updateStreamingMessage(data.data.text);
                }
                break;

            case 'tool_call':
                appendAgentActivity(data.agent_id || 'orchestrator', 'tool', data.data);
                break;

            case 'tool_result':
                appendAgentActivity(data.agent_id || 'orchestrator', 'result', data.data);
                break;

            case 'agent_spawned':
                updateAgentList(data.data);
                break;

            case 'status':
                if (data.data?.status === 'completed' || data.data?.status === 'failed') {
                    showTyping(false);
                }
                break;

            case 'final_response':
                showTyping(false);
                removeStreamingMessage();
                appendMessage('assistant', data.content);
                if (data.agents) updateAgentSidebar(data.agents);
                break;

            case 'transcript':
                DOM.input.value = data.text;
                break;

            case 'error':
                showTyping(false);
                appendMessage('assistant', `Error: ${data.error || data.data?.error || 'Unknown error'}`);
                break;
        }
    }

    // ─── Messages ───────────────────────────────────────────────────────
    function clearWelcome() {
        const welcome = DOM.messages.querySelector('.welcome-message');
        if (welcome) welcome.remove();
    }

    function appendMessage(role, content) {
        clearWelcome();
        const div = document.createElement('div');
        div.className = `message ${role}`;
        const avatar = role === 'user' ? 'U' : 'J';
        const sender = role === 'user' ? 'You' : 'JARVIS';

        div.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-body">
                <div class="message-sender">${sender}</div>
                <div class="message-content">${formatContent(content)}</div>
            </div>
        `;
        DOM.messages.appendChild(div);
        scrollToBottom();
    }

    function updateStreamingMessage(text) {
        clearWelcome();
        let el = DOM.messages.querySelector('.message.streaming');
        if (!el) {
            el = document.createElement('div');
            el.className = 'message assistant streaming';
            el.innerHTML = `
                <div class="message-avatar">J</div>
                <div class="message-body">
                    <div class="message-sender">JARVIS</div>
                    <div class="message-content"></div>
                </div>
            `;
            DOM.messages.appendChild(el);
        }
        el.querySelector('.message-content').innerHTML = formatContent(text);
        scrollToBottom();
    }

    function removeStreamingMessage() {
        const el = DOM.messages.querySelector('.message.streaming');
        if (el) el.remove();
    }

    function appendAgentActivity(agentId, kind, data) {
        clearWelcome();
        const div = document.createElement('div');
        div.className = 'agent-activity';

        if (kind === 'tool') {
            div.innerHTML = `
                <div class="activity-header">&#9881; ${escapeHtml(data.name)}</div>
                <div class="activity-detail">${escapeHtml(JSON.stringify(data.input, null, 2)).substring(0, 500)}</div>
            `;
        } else {
            div.innerHTML = `
                <div class="activity-header">&#10003; ${escapeHtml(data.name)} result</div>
                <div class="activity-detail">${escapeHtml(String(data.result || '')).substring(0, 1000)}</div>
            `;
        }

        let container = DOM.messages.querySelector('.message.assistant:last-child .message-body');
        if (!container) {
            const msg = document.createElement('div');
            msg.className = 'message assistant';
            msg.innerHTML = `
                <div class="message-avatar">J</div>
                <div class="message-body">
                    <div class="message-sender">JARVIS</div>
                </div>
            `;
            DOM.messages.appendChild(msg);
            container = msg.querySelector('.message-body');
        }
        container.appendChild(div);
        scrollToBottom();
    }

    function formatContent(text) {
        if (!text) return '';
        text = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
            return `<pre><code class="language-${lang}">${escapeHtml(code.trim())}</code></pre>`;
        });
        text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
        text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
        text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
        text = text.replace(/\n/g, '<br>');
        return text;
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function scrollToBottom() {
        DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
    }

    function showTyping(show) {
        DOM.typingIndicator.classList.toggle('hidden', !show);
    }

    // ─── Send Message ───────────────────────────────────────────────────
    async function sendMessage() {
        const text = DOM.input.value.trim();
        if (!text && state.attachments.length === 0) return;

        if (!state.keysReady) {
            showSetupScreen();
            return;
        }

        appendMessage('user', text || '[Attachments]');
        DOM.input.value = '';
        DOM.input.style.height = 'auto';

        const payload = {
            type: 'chat',
            message: text,
            attachments: [],
        };

        for (const att of state.attachments) {
            payload.attachments.push(att);
        }
        clearAttachments();

        showTyping(true);

        if (state.connected) {
            state.ws.send(JSON.stringify(payload));
        }
    }

    window.sendQuick = (text) => {
        DOM.input.value = text;
        sendMessage();
    };

    // ─── Voice ──────────────────────────────────────────────────────────
    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            state.mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            state.audioChunks = [];

            state.mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) state.audioChunks.push(e.data);
            };

            state.mediaRecorder.onstop = async () => {
                const blob = new Blob(state.audioChunks, { type: 'audio/webm' });
                stream.getTracks().forEach(t => t.stop());

                const reader = new FileReader();
                reader.onloadend = () => {
                    const b64 = reader.result.split(',')[1];
                    if (state.connected) {
                        state.ws.send(JSON.stringify({
                            type: 'voice',
                            audio: b64,
                            format: 'webm',
                        }));
                        showTyping(true);
                    }
                };
                reader.readAsDataURL(blob);
            };

            state.mediaRecorder.start();
            state.recording = true;
            DOM.voiceBtn.classList.add('recording');
        } catch (err) {
            console.error('Mic error:', err);
            alert('Microphone access denied. Please allow microphone access.');
        }
    }

    function stopRecording() {
        if (state.mediaRecorder && state.recording) {
            state.mediaRecorder.stop();
            state.recording = false;
            DOM.voiceBtn.classList.remove('recording');
        }
    }

    // ─── File Handling ──────────────────────────────────────────────────
    function handleFiles(files) {
        for (const file of files) {
            const reader = new FileReader();
            reader.onload = (e) => {
                const isImage = file.type.startsWith('image/');
                const att = {
                    type: isImage ? 'image' : 'file',
                    name: file.name,
                    media_type: file.type,
                };

                if (isImage) {
                    att.data = e.target.result.split(',')[1];
                } else {
                    att.content = e.target.result;
                }

                state.attachments.push(att);
                renderAttachments();
            };

            if (file.type.startsWith('image/')) {
                reader.readAsDataURL(file);
            } else {
                reader.readAsText(file);
            }
        }
    }

    function renderAttachments() {
        if (state.attachments.length === 0) {
            DOM.attachPreview.classList.add('hidden');
            DOM.attachPreview.parentElement.classList.remove('has-attachments');
            return;
        }
        DOM.attachPreview.classList.remove('hidden');
        DOM.attachPreview.parentElement.classList.add('has-attachments');
        DOM.attachItems.innerHTML = state.attachments.map((a, i) => `
            <div class="att-item">
                <span>${a.type === 'image' ? '&#128247;' : (a.type === 'link' ? '&#128279;' : '&#128196;')} ${escapeHtml(a.name)}</span>
                <span class="att-remove" onclick="removeAttachment(${i})">&times;</span>
            </div>
        `).join('');
    }

    window.removeAttachment = (idx) => {
        state.attachments.splice(idx, 1);
        renderAttachments();
    };

    function clearAttachments() {
        state.attachments = [];
        renderAttachments();
    }

    function addLink() {
        const url = prompt('Enter URL:');
        if (url) {
            state.attachments.push({
                type: 'file',
                name: url,
                content: `[Link: ${url}] Please fetch and analyze this URL.`,
            });
            renderAttachments();
        }
    }

    // ─── Sidebar Updates ────────────────────────────────────────────────
    function updateAgentList(data) {
        const el = DOM.agentList;
        const existing = el.querySelector('.empty-state');
        if (existing) existing.remove();

        const item = document.createElement('div');
        item.className = 'agent-item';
        item.innerHTML = `
            <span class="agent-dot running"></span>
            <span>${escapeHtml(data.type)} — ${escapeHtml(data.task.substring(0, 40))}</span>
        `;
        el.appendChild(item);
    }

    function updateAgentSidebar(agents) {
        const el = DOM.agentList;
        el.innerHTML = '';
        if (agents.length === 0) {
            el.innerHTML = '<div class="empty-state">No active agents</div>';
            return;
        }
        for (const a of agents) {
            const item = document.createElement('div');
            item.className = 'agent-item';
            item.innerHTML = `
                <span class="agent-dot ${a.status}"></span>
                <span>${escapeHtml(a.type)} (${a.status})</span>
            `;
            el.appendChild(item);
        }
    }

    async function loadMemories() {
        try {
            const res = await fetch('/api/memory');
            const data = await res.json();
            const el = DOM.memoryList;
            if (data.memories.length === 0) return;
            el.innerHTML = '';
            for (const m of data.memories.slice(0, 10)) {
                const item = document.createElement('div');
                item.className = 'memory-item';
                item.innerHTML = `<span class="mem-key">${escapeHtml(m.key)}</span>: ${escapeHtml(m.content.substring(0, 60))}`;
                el.appendChild(item);
            }
        } catch (e) {}
    }

    async function loadEvolution() {
        try {
            const res = await fetch('/api/evolution/stats');
            const data = await res.json();
            const el = DOM.evolutionStats;
            el.innerHTML = `
                <div style="font-size:12px;color:var(--text-secondary)">
                    Tasks: ${data.stats.total_tasks} |
                    Success: ${(data.stats.success_rate * 100).toFixed(0)}%
                </div>
                ${data.suggestions.map(s => `<div style="font-size:11px;color:var(--text-muted);margin-top:4px">${escapeHtml(s)}</div>`).join('')}
            `;
        } catch (e) {}
    }

    // ─── Drag & Drop ────────────────────────────────────────────────────
    let dragCounter = 0;

    document.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragCounter++;
        DOM.dropOverlay.classList.remove('hidden');
    });

    document.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter === 0) DOM.dropOverlay.classList.add('hidden');
    });

    document.addEventListener('dragover', (e) => e.preventDefault());

    document.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        DOM.dropOverlay.classList.add('hidden');
        if (e.dataTransfer.files.length > 0) {
            handleFiles(e.dataTransfer.files);
        }
    });

    // ─── Event Listeners ────────────────────────────────────────────────
    DOM.sendBtn.addEventListener('click', sendMessage);

    DOM.input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    DOM.input.addEventListener('input', () => {
        DOM.input.style.height = 'auto';
        DOM.input.style.height = Math.min(DOM.input.scrollHeight, 200) + 'px';
    });

    // Voice
    DOM.voiceBtn.addEventListener('mousedown', startRecording);
    DOM.voiceBtn.addEventListener('mouseup', stopRecording);
    DOM.voiceBtn.addEventListener('mouseleave', stopRecording);
    DOM.voiceBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); });
    DOM.voiceBtn.addEventListener('touchend', (e) => { e.preventDefault(); stopRecording(); });

    // File uploads
    DOM.uploadBtn.addEventListener('click', () => DOM.fileInput.click());
    DOM.fileInput.addEventListener('change', (e) => handleFiles(e.target.files));
    DOM.folderBtn.addEventListener('click', () => DOM.folderInput.click());
    DOM.folderInput.addEventListener('change', (e) => handleFiles(e.target.files));
    DOM.linkBtn.addEventListener('click', addLink);

    // New chat
    DOM.newChatBtn.addEventListener('click', () => {
        state.sessionId = crypto.randomUUID();
        DOM.messages.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">J</div>
                <h1>Hello, I'm JARVIS</h1>
                <p>New conversation started. How can I help you?</p>
            </div>
        `;
        if (state.ws) state.ws.close();
        connect();
    });

    // Paste images
    document.addEventListener('paste', (e) => {
        const items = e.clipboardData?.items;
        if (!items) return;
        for (const item of items) {
            if (item.type.startsWith('image/')) {
                const file = item.getAsFile();
                if (file) handleFiles([file]);
            }
        }
    });

    // Setup screen
    DOM.setupSaveBtn.addEventListener('click', handleSetupSave);
    DOM.setupAnthropicKey.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleSetupSave();
    });

    // Settings modal
    DOM.settingsBtn.addEventListener('click', openSettings);
    DOM.modalCloseBtn.addEventListener('click', closeSettings);
    DOM.modalSaveBtn.addEventListener('click', handleModalSave);
    DOM.modalClearBtn.addEventListener('click', handleModalClear);
    DOM.settingsModal.addEventListener('click', (e) => {
        if (e.target === DOM.settingsModal) closeSettings();
    });

    // Escape key closes modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (!DOM.settingsModal.classList.contains('hidden')) closeSettings();
        }
    });

    // ─── Init ───────────────────────────────────────────────────────────
    checkKeyStatus();
    setInterval(loadMemories, 30000);
    setInterval(loadEvolution, 30000);
    setTimeout(loadMemories, 2000);
    setTimeout(loadEvolution, 2000);

})();
