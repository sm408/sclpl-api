const Functions = {
    init() {
        this.container = document.getElementById('view-functions');
        this.render();
    },

    render() {
        this.container.innerHTML = `
            <div class="view-header">
                <h1>Functions</h1>
                <p class="subtitle">Python-powered request transforms and workflow steps</p>
            </div>
            <div class="filter-bar">
                <input type="text" class="input" id="function-search" placeholder="Search functions...">
                <button class="btn" id="btn-refresh-functions">
                    <i class="fas fa-rotate"></i> Refresh
                </button>
            </div>
            <div id="function-list"></div>
        `;

        document.getElementById('btn-refresh-functions').addEventListener('click', () => this.refresh());
        document.getElementById('function-search').addEventListener('input', (e) => this.filter(e.target.value));
    },

    async refresh() {
        const list = document.getElementById('function-list');
        list.innerHTML = '<div style="text-align:center;padding:24px"><span class="spinner"></span></div>';

        try {
            const functions = await App.api('/api/functions');
            App.state.functions = Array.isArray(functions) ? functions : [];
            this.renderList(App.state.functions);
        } catch {
            list.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-code"></i>
                    <h3>No functions found</h3>
                    <p>Add Python functions to the functions/ directory</p>
                </div>`;
        }
    },

    renderList(functions) {
        const list = document.getElementById('function-list');
        if (!functions.length) {
            list.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-code"></i>
                    <h3>No functions found</h3>
                    <p>Add Python functions to the functions/ directory</p>
                </div>`;
            return;
        }

        // Store functions for later lookup
        this._functions = functions;

        list.innerHTML = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Version</th>
                        <th>Description</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${functions.map((fn, i) => `
                        <tr>
                            <td style="font-family:var(--font-mono);font-weight:600">${this.escape(fn.name || fn.id || '')}</td>
                            <td><span class="method-badge method-POST" style="font-size:10px">${this.escape(fn.type || 'transform')}</span></td>
                            <td style="font-size:12px;color:var(--text-secondary)">${this.escape(fn.version || '1.0')}</td>
                            <td style="font-size:13px;color:var(--text-secondary)">${this.escape(fn.description || '')}</td>
                            <td>
                                <button class="btn btn-sm btn-view-fn" data-fn-idx="${i}">
                                    <i class="fas fa-eye"></i> View
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        list.querySelectorAll('.btn-view-fn').forEach(btn => {
            btn.addEventListener('click', () => {
                const idx = parseInt(btn.dataset.fnIdx);
                const fn = this._functions[idx];
                if (fn) this.viewFunction(fn);
            });
        });
    },

    async viewFunction(fn) {
        const modal = document.createElement('div');
        modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:1000;display:flex;align-items:center;justify-content:center';
        modal.innerHTML = `
            <div style="background:var(--bg-card);border-radius:var(--radius-lg);width:90%;max-width:700px;max-height:80vh;overflow:auto;padding:24px;box-shadow:var(--shadow-lg)">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                    <h2 style="font-size:18px">${this.escape(fn.name || fn.id || 'Function')}</h2>
                    <button class="btn btn-icon" id="close-fn-modal"><i class="fas fa-times"></i></button>
                </div>
                <div style="font-size:13px;color:var(--text-secondary);margin-bottom:16px">${this.escape(fn.description || 'No description')}</div>
                <div id="fn-source-container"><span class="spinner"></span> Loading source...</div>
            </div>
        `;
        document.body.appendChild(modal);
        modal.querySelector('#close-fn-modal').addEventListener('click', () => modal.remove());
        modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });

        try {
            const source = await App.api(`/api/functions/${encodeURIComponent(fn.name || fn.id)}/source`);
            const srcText = typeof source === 'string' ? source : (source.source || JSON.stringify(source, null, 2));
            document.getElementById('fn-source-container').innerHTML = `<div class="code-block">${this.escape(srcText)}</div>`;
        } catch {
            document.getElementById('fn-source-container').innerHTML = `<div style="color:var(--text-muted);font-size:13px">Source not available</div>`;
        }
    },

    filter(query) {
        const q = query.toLowerCase();
        const filtered = App.state.functions.filter(fn =>
            (fn.name || fn.id || '').toLowerCase().includes(q) ||
            (fn.description || '').toLowerCase().includes(q)
        );
        this.renderList(filtered);
    },

    escape(str) {
        const d = document.createElement('div');
        d.textContent = str || '';
        return d.innerHTML;
    }
};
