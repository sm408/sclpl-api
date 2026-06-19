const History = {
    entries: [],

    init() {
        this.container = document.getElementById('view-history');
        this.render();
    },

    render() {
        this.container.innerHTML = `
            <div class="view-header">
                <h1>History</h1>
                <p class="subtitle">Past request executions</p>
            </div>
            <div class="filter-bar">
                <input type="text" class="input" id="history-search" placeholder="Filter by URL...">
                <select class="input" id="history-method-filter" style="width:120px">
                    <option value="">All Methods</option>
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="DELETE">DELETE</option>
                    <option value="PATCH">PATCH</option>
                </select>
                <select class="input" id="history-status-filter" style="width:130px">
                    <option value="">All Status</option>
                    <option value="2xx">2xx Success</option>
                    <option value="3xx">3xx Redirect</option>
                    <option value="4xx">4xx Client Error</option>
                    <option value="5xx">5xx Server Error</option>
                </select>
                <button class="btn btn-sm" id="btn-clear-history">
                    <i class="fas fa-trash"></i> Clear
                </button>
            </div>
            <div id="history-table-container"></div>
        `;

        document.getElementById('history-search').addEventListener('input', () => this.applyFilters());
        document.getElementById('history-method-filter').addEventListener('change', () => this.applyFilters());
        document.getElementById('history-status-filter').addEventListener('change', () => this.applyFilters());
        document.getElementById('btn-clear-history').addEventListener('click', () => {
            this.entries = [];
            this.renderTable([]);
            App.toast('History cleared', 'info');
        });
    },

    refresh() {
        this.renderTable(this.entries);
    },

    addEntry(entry) {
        this.entries.unshift(entry);
        if (this.entries.length > 200) this.entries = this.entries.slice(0, 200);
    },

    applyFilters() {
        const urlQuery = (document.getElementById('history-search').value || '').toLowerCase();
        const methodFilter = document.getElementById('history-method-filter').value;
        const statusFilter = document.getElementById('history-status-filter').value;

        let filtered = this.entries;

        if (urlQuery) {
            filtered = filtered.filter(e => (e.url || '').toLowerCase().includes(urlQuery));
        }
        if (methodFilter) {
            filtered = filtered.filter(e => e.method === methodFilter);
        }
        if (statusFilter) {
            filtered = filtered.filter(e => {
                const code = e.status;
                if (statusFilter === '2xx') return code >= 200 && code < 300;
                if (statusFilter === '3xx') return code >= 300 && code < 400;
                if (statusFilter === '4xx') return code >= 400 && code < 500;
                if (statusFilter === '5xx') return code >= 500;
                return true;
            });
        }

        this.renderTable(filtered);
    },

    renderTable(entries) {
        const container = document.getElementById('history-table-container');
        if (!entries.length) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-clock-rotate-left"></i>
                    <h3>No history yet</h3>
                    <p>Send a request from the editor to see it here</p>
                </div>`;
            return;
        }

        container.innerHTML = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Method</th>
                        <th>URL</th>
                        <th>Status</th>
                        <th>Duration</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(entry => `
                        <tr class="history-row" data-entry='${JSON.stringify(entry)}' style="cursor:pointer">
                            <td><span class="method-badge method-${entry.method}">${entry.method}</span></td>
                            <td style="font-family:var(--font-mono);font-size:12px;max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${this.escape(entry.url)}</td>
                            <td><span class="status-badge ${App.getStatusClass(entry.status)}">${entry.status}</span></td>
                            <td style="font-family:var(--font-mono);font-size:12px">${App.formatDuration(entry.duration)}</td>
                            <td style="font-size:12px;color:var(--text-secondary)">${this.formatTime(entry.timestamp)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        container.querySelectorAll('.history-row').forEach(row => {
            row.addEventListener('click', () => {
                const entry = JSON.parse(row.dataset.entry);
                this.openInEditor(entry);
            });
        });
    },

    openInEditor(entry) {
        Router.navigate('editor');
        setTimeout(() => {
            if (entry.method) document.getElementById('req-method').value = entry.method;
            if (entry.url) document.getElementById('req-url').value = entry.url;
        }, 100);
    },

    formatTime(ts) {
        if (!ts) return '';
        const d = new Date(ts);
        return d.toLocaleTimeString();
    },

    escape(str) {
        const d = document.createElement('div');
        d.textContent = str || '';
        return d.innerHTML;
    }
};
