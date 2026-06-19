const WorkflowRunner = {
    init() {
        this.container = document.getElementById('view-flows');
        this.render();
    },

    render() {
        this.container.innerHTML = `
            <div class="view-header">
                <h1>Workflows</h1>
                <p class="subtitle">Run and monitor workflow pipelines</p>
            </div>
            <div class="filter-bar">
                <input type="text" class="input" id="workflow-search" placeholder="Search workflows...">
                <button class="btn btn-primary" id="btn-refresh-workflows">
                    <i class="fas fa-rotate"></i> Refresh
                </button>
            </div>
            <div id="workflow-list"></div>
        `;

        document.getElementById('btn-refresh-workflows').addEventListener('click', () => this.refresh());
        document.getElementById('workflow-search').addEventListener('input', (e) => this.filter(e.target.value));
    },

    async refresh() {
        const list = document.getElementById('workflow-list');
        list.innerHTML = '<div style="text-align:center;padding:24px"><span class="spinner"></span></div>';

        try {
            const workflows = await App.api('/api/workflows');
            App.state.workflows = Array.isArray(workflows) ? workflows : [];
            this.renderList(App.state.workflows);
        } catch {
            list.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-diagram-project"></i>
                    <h3>No workflows found</h3>
                    <p>Create workflows in the Flow Builder or define them in Python</p>
                </div>`;
        }
    },

    renderList(workflows) {
        const list = document.getElementById('workflow-list');
        if (!workflows.length) {
            list.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-diagram-project"></i>
                    <h3>No workflows found</h3>
                    <p>Create workflows in the Flow Builder or define them in Python</p>
                </div>`;
            return;
        }

        list.innerHTML = workflows.map(wf => `
            <div class="workflow-card" data-wf-id="${wf.id || wf.name}">
                <div class="workflow-header">
                    <span class="workflow-name">${this.escapeHtml(wf.name || 'Unnamed')}</span>
                    <div style="display:flex;gap:8px">
                        <button class="btn btn-primary btn-sm btn-run-wf" data-wf-id="${wf.id || wf.name}">
                            <i class="fas fa-play"></i> Run
                        </button>
                    </div>
                </div>
                <div style="font-size:13px;color:var(--text-secondary);margin-bottom:8px">
                    ${this.escapeHtml(wf.description || 'No description')}
                </div>
                <div class="workflow-steps" id="wf-steps-${this.safeId(wf.id || wf.name)}"></div>
                <div id="wf-status-${this.safeId(wf.id || wf.name)}" style="margin-top:8px;font-size:12px;color:var(--text-muted)"></div>
            </div>
        `).join('');

        list.querySelectorAll('.btn-run-wf').forEach(btn => {
            btn.addEventListener('click', () => this.runWorkflow(btn.dataset.wfId));
        });
    },

    async runWorkflow(wfId) {
        const stepsEl = document.getElementById(`wf-steps-${this.safeId(wfId)}`);
        const statusEl = document.getElementById(`wf-status-${this.safeId(wfId)}`);
        if (!stepsEl) return;

        statusEl.innerHTML = '<span class="spinner"></span> Running...';

        try {
            const result = await App.api(`/api/workflows/${encodeURIComponent(wfId)}/run`, {
                method: 'POST',
                body: {}
            });

            if (result.steps) {
                this.renderSteps(stepsEl, result.steps);
            }
            statusEl.innerHTML = `<span style="color:var(--success)"><i class="fas fa-check"></i> Completed</span>`;
            App.toast('Workflow completed', 'success');
        } catch (err) {
            statusEl.innerHTML = `<span style="color:var(--danger)"><i class="fas fa-times"></i> Failed: ${err.message}</span>`;
            App.toast('Workflow failed', 'error');
        }
    },

    renderSteps(container, steps) {
        container.innerHTML = steps.map((step, i) => `
            <div class="workflow-step">
                <div class="step-icon ${step.status || ''}">
                    ${step.status === 'success' ? '<i class="fas fa-check"></i>' :
                      step.status === 'error' ? '<i class="fas fa-times"></i>' :
                      step.status === 'running' ? '<i class="fas fa-spinner fa-spin"></i>' :
                      (i + 1)}
                </div>
                <span>${this.escapeHtml(step.name || `Step ${i + 1}`)}</span>
                <span class="step-duration">${step.duration ? App.formatDuration(step.duration) : ''}</span>
            </div>
        `).join('');
    },

    filter(query) {
        const q = query.toLowerCase();
        const filtered = App.state.workflows.filter(wf =>
            (wf.name || '').toLowerCase().includes(q) ||
            (wf.description || '').toLowerCase().includes(q)
        );
        this.renderList(filtered);
    },

    escapeHtml(str) {
        const d = document.createElement('div');
        d.textContent = str || '';
        return d.innerHTML;
    },

    safeId(id) {
        return String(id).replace(/[^a-zA-Z0-9]/g, '_');
    }
};
