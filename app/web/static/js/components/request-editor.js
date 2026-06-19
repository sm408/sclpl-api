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
                <input type="text" class="input url-input" id="req-url" placeholder="Enter request URL...">
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
        // Tabs
        this.container.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.container.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                this.container.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
            });
        });

        // Add rows
        document.getElementById('btn-add-param').addEventListener('click', () => this.addRow('params-table'));
        document.getElementById('btn-add-header').addEventListener('click', () => this.addRow('headers-table'));

        // Send
        document.getElementById('btn-send').addEventListener('click', () => this.send());

        // Method color
        document.getElementById('req-method').addEventListener('change', (e) => {
            e.target.className = `input method-select method-${e.target.value}`;
        });

        // Auth type
        document.getElementById('auth-type').addEventListener('change', (e) => {
            this.renderAuthFields(e.target.value);
        });
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

        // Build params
        const params = this.getKvPairs('params-table');
        if (Object.keys(params).length) {
            const qs = new URLSearchParams(params).toString();
            url += (url.includes('?') ? '&' : '?') + qs;
        }

        // Build headers
        const headers = this.getKvPairs('headers-table');

        // Auth
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

        // Body
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
            const res = await fetch(url, {
                method,
                headers,
                body: method !== 'GET' ? body : undefined
            });
            const duration = Math.round(performance.now() - startTime);
            const responseText = await res.text();
            const size = new Blob([responseText]).size;

            let responseBody;
            try { responseBody = JSON.parse(responseText); } catch { responseBody = responseText; }

            this.renderResponse({
                status: res.status,
                statusText: res.statusText,
                duration,
                size,
                headers: Object.fromEntries(res.headers.entries()),
                body: responseBody
            });

            // Save to history
            History.addEntry({
                method, url, status: res.status, duration, size,
                timestamp: new Date().toISOString()
            });
        } catch (err) {
            const duration = Math.round(performance.now() - startTime);
            this.renderResponse({
                status: 0,
                statusText: 'Error',
                duration,
                size: 0,
                headers: {},
                body: { error: err.message }
            });
        } finally {
            btn.innerHTML = '<i class="fas fa-paper-plane"></i> Send';
            btn.disabled = false;
        }
    },

    renderResponse(res) {
        const container = document.getElementById('response-container');
        const statusClass = res.status ? App.getStatusClass(res.status) : 'status-5xx';
        container.innerHTML = `
            <div class="response-panel">
                <div class="response-header">
                    <div class="response-meta">
                        <span><span class="status-badge ${statusClass}">${res.status} ${res.statusText}</span></span>
                        <span><i class="fas fa-clock"></i> ${App.formatDuration(res.duration)}</span>
                        <span><i class="fas fa-weight-hanging"></i> ${App.formatBytes(res.size)}</span>
                    </div>
                </div>
                <div class="response-body">${App.formatJson(res.body)}</div>
            </div>
        `;
    }
};
