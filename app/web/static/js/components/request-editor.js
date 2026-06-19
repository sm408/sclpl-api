const RequestEditor = {
    init() {
        this.container = document.getElementById('view-editor');
        this.render();
    },

    render() {
        this.container.innerHTML = `
            <div class="view-header">
                <h1>Request Editor</h1>
            </div>
            <div class="request-bar">
                <select class="input method-select" id="req-method">
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="PATCH">PATCH</option>
                    <option value="DELETE">DELETE</option>
                </select>
                <input type="text" class="input url-input" id="req-url" placeholder="Enter request URL... (Ctrl+Enter to send)">
                <button class="btn btn-primary send-btn" id="btn-send">
                    <i class="fas fa-paper-plane"></i> Send
                </button>
                <button class="btn btn-sm" id="btn-save-req" title="Save to Collection">
                    <i class="fas fa-save"></i>
                </button>
            </div>
            <div class="tabs" id="req-tabs">
                <button class="tab active" data-tab="params">Params</button>
                <button class="tab" data-tab="headers">Headers</button>
                <button class="tab" data-tab="body">Body</button>
                <button class="tab" data-tab="auth">Auth</button>
            </div>
            <div id="tab-params" class="tab-content active">
                <table class="kv-table" id="params-table">
                    <thead><tr><th>Key</th><th>Value</th><th></th></tr></thead>
                    <tbody></tbody>
                </table>
                <button class="btn btn-sm" id="btn-add-param" style="margin-top:8px">
                    <i class="fas fa-plus"></i> Add Parameter
                </button>
            </div>
            <div id="tab-headers" class="tab-content">
                <table class="kv-table" id="headers-table">
                    <thead><tr><th>Key</th><th>Value</th><th></th></tr></thead>
                    <tbody></tbody>
                </table>
                <button class="btn btn-sm" id="btn-add-header" style="margin-top:8px">
                    <i class="fas fa-plus"></i> Add Header
                </button>
            </div>
            <div id="tab-body" class="tab-content">
                <div style="margin-bottom:8px">
                    <select class="input" id="body-type" style="width:150px">
                        <option value="json">JSON</option>
                        <option value="text">Raw Text</option>
                        <option value="form">Form Data</option>
                    </select>
                </div>
                <textarea class="input" id="req-body" rows="10" placeholder='{\n  "key": "value"\n}'></textarea>
            </div>
            <div id="tab-auth" class="tab-content">
                <div style="margin-bottom:12px">
                    <select class="input" id="auth-type" style="width:200px">
                        <option value="none">No Auth</option>
                        <option value="bearer">Bearer Token</option>
                        <option value="basic">Basic Auth</option>
                        <option value="api-key">API Key</option>
                    </select>
                </div>
                <div id="auth-fields"></div>
            </div>
            <div id="response-container"></div>
        `;
        this.bindEvents();
        this.addRow('params-table');
        this.addRow('headers-table');
    },

    bindEvents() {
        this.container.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.container.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                this.container.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
            });
        });

        document.getElementById('btn-add-param').addEventListener('click', () => this.addRow('params-table'));
        document.getElementById('btn-add-header').addEventListener('click', () => this.addRow('headers-table'));
        document.getElementById('btn-send').addEventListener('click', () => this.send());

        document.getElementById('req-method').addEventListener('change', (e) => {
            e.target.className = `input method-select method-${e.target.value}`;
        });

        document.getElementById('auth-type').addEventListener('change', (e) => {
            this.renderAuthFields(e.target.value);
        });

        document.getElementById('btn-save-req').addEventListener('click', () => this.saveToCollection());
    },

    addRow(tableId) {
        const tbody = document.querySelector(`#${tableId} tbody`);
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><input type="text" placeholder="Key"></td>
            <td><input type="text" placeholder="Value"></td>
            <td><button class="btn btn-icon btn-sm" onclick="this.closest('tr').remove()"><i class="fas fa-times"></i></button></td>
        `;
        tbody.appendChild(tr);
    },

    renderAuthFields(type) {
        const container = document.getElementById('auth-fields');
        switch (type) {
            case 'bearer':
                container.innerHTML = '<input type="text" class="input" id="auth-token" placeholder="Token" style="width:100%;max-width:500px">';
                break;
            case 'basic':
                container.innerHTML = `
                    <div style="display:flex;gap:8px;max-width:500px">
                        <input type="text" class="input" id="auth-user" placeholder="Username" style="flex:1">
                        <input type="password" class="input" id="auth-pass" placeholder="Password" style="flex:1">
                    </div>`;
                break;
            case 'api-key':
                container.innerHTML = `
                    <div style="display:flex;gap:8px;max-width:500px">
                        <input type="text" class="input" id="auth-key-name" placeholder="Header Name" style="flex:1">
                        <input type="text" class="input" id="auth-key-value" placeholder="Value" style="flex:2">
                    </div>`;
                break;
            default:
                container.innerHTML = '';
        }
    },

    getKvPairs(tableId) {
        const pairs = {};
        document.querySelectorAll(`#${tableId} tbody tr`).forEach(row => {
            const inputs = row.querySelectorAll('input');
            const key = inputs[0].value.trim();
            const val = inputs[1].value.trim();
            if (key) pairs[key] = val;
        });
        return pairs;
    },

    async send() {
        const method = document.getElementById('req-method').value;
        let url = document.getElementById('req-url').value.trim();
        if (!url) {
            App.toast('Please enter a URL', 'error');
            return;
        }

        const params = this.getKvPairs('params-table');
        if (Object.keys(params).length) {
            const qs = new URLSearchParams(params).toString();
            url += (url.includes('?') ? '&' : '?') + qs;
        }

        const headers = this.getKvPairs('headers-table');

        const authType = document.getElementById('auth-type').value;
        if (authType === 'bearer') {
            const token = document.getElementById('auth-token')?.value;
            if (token) headers['Authorization'] = `Bearer ${token}`;
        } else if (authType === 'basic') {
            const user = document.getElementById('auth-user')?.value || '';
            const pass = document.getElementById('auth-pass')?.value || '';
            headers['Authorization'] = 'Basic ' + btoa(`${user}:${pass}`);
        } else if (authType === 'api-key') {
            const name = document.getElementById('auth-key-name')?.value;
            const val = document.getElementById('auth-key-value')?.value;
            if (name && val) headers[name] = val;
        }

        const bodyType = document.getElementById('body-type').value;
        let body = null;
        if (method !== 'GET' && method !== 'DELETE') {
            body = document.getElementById('req-body').value;
            if (bodyType === 'json' && body) {
                headers['Content-Type'] = 'application/json';
            }
        }

        const btn = document.getElementById('btn-send');
        btn.innerHTML = '<span class="spinner"></span> Sending';
        btn.disabled = true;

        const startTime = performance.now();
        try {
            // Use backend proxy to avoid CORS and get history
            const proxyRes = await App.api('/api/requests/send', {
                method: 'POST',
                body: {
                    url,
                    method,
                    headers,
                    body: method !== 'GET' ? body : undefined
                }
            });
            const duration = proxyRes.duration_ms || Math.round(performance.now() - startTime);
            const responseText = proxyRes.body || '';
            const size = new Blob([responseText]).size;

            let responseBody;
            try { responseBody = JSON.parse(responseText); } catch { responseBody = responseText; }

            this.renderResponse({
                status: proxyRes.status_code,
                statusText: proxyRes.error ? 'Error' : 'OK',
                duration,
                size,
                headers: proxyRes.headers || {},
                body: responseBody,
                raw: responseText,
                error: proxyRes.error
            });

            App.toast(`${proxyRes.status_code} - ${App.formatDuration(duration)}`, proxyRes.error ? 'warning' : 'success');
        } catch (err) {
            const duration = Math.round(performance.now() - startTime);
            this.renderResponse({
                status: 0,
                statusText: 'Error',
                duration,
                size: 0,
                headers: {},
                body: { error: err.message },
                raw: err.message
            });
            App.toast(`Request failed: ${err.message}`, 'error');
        } finally {
            btn.innerHTML = '<i class="fas fa-paper-plane"></i> Send';
            btn.disabled = false;
        }
    },

    renderResponse(res) {
        const container = document.getElementById('response-container');
        const statusClass = res.status ? App.getStatusClass(res.status) : 'status-5xx';
        const isJson = typeof res.body === 'object';

        const headersHtml = Object.entries(res.headers || {}).map(([k, v]) =>
            `<tr><td>${this.escapeHtml(k)}</td><td>${this.escapeHtml(v)}</td></tr>`
        ).join('');

        container.innerHTML = `
            <div class="response-panel">
                <div class="response-header">
                    <div class="response-meta">
                        <span><span class="status-badge ${statusClass}">${res.status} ${res.statusText}</span></span>
                        <span><i class="fas fa-clock"></i> ${App.formatDuration(res.duration)}</span>
                        <span><i class="fas fa-weight-hanging"></i> ${App.formatBytes(res.size)}</span>
                    </div>
                    <button class="btn btn-sm btn-copy-response" title="Copy response body">
                        <i class="fas fa-copy"></i> Copy
                    </button>
                </div>
                <div class="response-tabs" id="response-tabs">
                    <button class="response-tab active" data-rtab="pretty">Pretty</button>
                    <button class="response-tab" data-rtab="raw">Raw</button>
                    <button class="response-tab" data-rtab="headers">Headers <span style="opacity:0.6">(${Object.keys(res.headers || {}).length})</span></button>
                </div>
                <div id="rtab-pretty" class="response-tab-content active">
                    <div class="response-body-wrapper">
                        <div class="response-body">${isJson ? App.highlightJson(res.body) : this.escapeHtml(String(res.body))}</div>
                    </div>
                </div>
                <div id="rtab-raw" class="response-tab-content">
                    <div class="response-body-wrapper">
                        <div class="response-body">${this.escapeHtml(res.raw || (isJson ? JSON.stringify(res.body) : String(res.body)))}</div>
                    </div>
                </div>
                <div id="rtab-headers" class="response-tab-content">
                    <table class="response-headers-table">
                        ${headersHtml || '<tr><td colspan="2" style="color:var(--text-muted);text-align:center;padding:24px">No headers</td></tr>'}
                    </table>
                </div>
            </div>
        `;

        // Response tab switching
        container.querySelectorAll('.response-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                container.querySelectorAll('.response-tab').forEach(t => t.classList.remove('active'));
                container.querySelectorAll('.response-tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                container.querySelector(`#rtab-${tab.dataset.rtab}`).classList.add('active');
            });
        });

        // Copy button
        container.querySelector('.btn-copy-response').addEventListener('click', () => {
            const textToCopy = isJson ? JSON.stringify(res.body, null, 2) : String(res.body || res.raw);
            navigator.clipboard.writeText(textToCopy).then(() => {
                App.toast('Response copied to clipboard', 'success');
            }).catch(() => {
                App.toast('Failed to copy', 'error');
            });
        });
    },

    async saveToCollection() {
        const method = document.getElementById('req-method').value;
        const url = document.getElementById('req-url').value.trim();
        if (!url) {
            App.toast('Enter a URL first', 'error');
            return;
        }

        const request = {
            method,
            url,
            headers: this.getKvPairs('headers-table'),
            body: document.getElementById('req-body').value
        };

        try {
            const collections = await App.api('/api/collections').catch(() => []);
            const cols = Array.isArray(collections) ? collections : [];

            if (!cols.length) {
                App.toast('Create a collection first', 'info');
                return;
            }

            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:1000;display:flex;align-items:center;justify-content:center';
            modal.innerHTML = `
                <div style="background:var(--bg-card);border-radius:var(--radius-lg);width:400px;max-width:90%;padding:24px;box-shadow:var(--shadow-lg)">
                    <h3 style="font-size:16px;margin-bottom:16px">Save to Collection</h3>
                    <div style="margin-bottom:12px">
                        <label style="font-size:13px;color:var(--text-secondary);display:block;margin-bottom:4px">Request Name</label>
                        <input type="text" class="input" id="save-req-name" value="${method} ${url}" style="width:100%">
                    </div>
                    <div style="margin-bottom:16px">
                        <label style="font-size:13px;color:var(--text-secondary);display:block;margin-bottom:4px">Collection</label>
                        <select class="input" id="save-req-collection" style="width:100%">
                            ${cols.map(c => `<option value="${c.id || c.name}">${this.escapeHtml(c.name || 'Unnamed')}</option>`).join('')}
                        </select>
                    </div>
                    <div style="display:flex;gap:8px;justify-content:flex-end">
                        <button class="btn" id="save-req-cancel">Cancel</button>
                        <button class="btn btn-primary" id="save-req-confirm">Save</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            modal.querySelector('#save-req-cancel').addEventListener('click', () => modal.remove());
            modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });

            modal.querySelector('#save-req-confirm').addEventListener('click', async () => {
                const name = modal.querySelector('#save-req-name').value;
                const colId = modal.querySelector('#save-req-collection').value;
                try {
                    await App.api(`/api/collections/${encodeURIComponent(colId)}/requests`, {
                        method: 'POST',
                        body: {
                            url: request.url,
                            method: request.method,
                            headers: request.headers || {},
                            body: request.body || null
                        }
                    });
                    App.toast('Request saved to collection', 'success');
                    modal.remove();
                } catch (e) {
                    App.toast('Failed to save request: ' + e.message, 'error');
                }
            });
        } catch {
            App.toast('Failed to load collections', 'error');
        }
    },

    escapeHtml(str) {
        const d = document.createElement('div');
        d.textContent = str || '';
        return d.innerHTML;
    }
};
