const Collections = {
    init() {
        this.container = document.getElementById('view-collections');
        this.render();
    },

    render() {
        this.container.innerHTML = `
            <div class="view-header">
                <h1>Collections</h1>
                <p class="subtitle">Organize your API requests</p>
            </div>
            <div class="filter-bar">
                <input type="text" class="input" id="collection-search" placeholder="Search collections...">
                <button class="btn btn-primary" id="btn-new-collection">
                    <i class="fas fa-plus"></i> New Collection
                </button>
                <button class="btn" id="btn-refresh-collections">
                    <i class="fas fa-rotate"></i> Refresh
                </button>
            </div>
            <div id="collection-tree"></div>
        `;

        document.getElementById('btn-new-collection').addEventListener('click', () => this.createCollection());
        document.getElementById('btn-refresh-collections').addEventListener('click', () => this.refresh());
        document.getElementById('collection-search').addEventListener('input', (e) => this.filter(e.target.value));
    },

    async refresh() {
        const tree = document.getElementById('collection-tree');
        tree.innerHTML = '<div style="text-align:center;padding:24px"><span class="spinner"></span></div>';

        try {
            const collections = await App.api('/api/collections');
            App.state.collections = Array.isArray(collections) ? collections : [];
            this.renderTree(App.state.collections);
        } catch {
            tree.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-folder-tree"></i>
                    <h3>No collections yet</h3>
                    <p>Create a collection to start organizing your requests</p>
                </div>`;
        }
    },

    renderTree(collections) {
        const tree = document.getElementById('collection-tree');
        if (!collections.length) {
            tree.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-folder-tree"></i>
                    <h3>No collections yet</h3>
                    <p>Create a collection to start organizing your requests</p>
                </div>`;
            return;
        }

        tree.innerHTML = `<div class="tree-view">${collections.map(col => this.renderCollectionNode(col)).join('')}</div>`;

        // Toggle expand/collapse
        tree.querySelectorAll('.collection-toggle').forEach(el => {
            el.addEventListener('click', (e) => {
                const children = el.closest('.tree-item').nextElementSibling;
                if (children) {
                    children.style.display = children.style.display === 'none' ? 'block' : 'none';
                    el.querySelector('i').classList.toggle('fa-chevron-right');
                    el.querySelector('i').classList.toggle('fa-chevron-down');
                }
            });
        });

        // Open request in editor
        tree.querySelectorAll('.request-item').forEach(el => {
            el.addEventListener('click', () => {
                const data = JSON.parse(el.dataset.request || '{}');
                this.openInEditor(data);
            });
        });

        // Delete collection
        tree.querySelectorAll('.btn-delete-col').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteCollection(el.dataset.colId);
            });
        });
    },

    renderCollectionNode(col) {
        const requests = col.requests || [];
        return `
            <div class="tree-item collection-item" data-col-id="${col.id || ''}">
                <span class="collection-toggle" style="cursor:pointer">
                    <i class="fas fa-chevron-right" style="font-size:10px;width:12px"></i>
                </span>
                <i class="fas fa-folder"></i>
                <span class="tree-label">${this.escape(col.name || 'Unnamed')}</span>
                <button class="btn btn-icon btn-sm btn-delete-col" data-col-id="${col.id || ''}" title="Delete">
                    <i class="fas fa-trash" style="font-size:11px"></i>
                </button>
            </div>
            <div class="tree-children" style="display:none">
                ${requests.map(req => `
                    <div class="tree-item request-item" data-request='${JSON.stringify(req)}'>
                        <span class="method-badge method-${req.method || 'GET'}" style="font-size:10px">${req.method || 'GET'}</span>
                        <span class="tree-label">${this.escape(req.name || req.url || 'Unnamed')}</span>
                    </div>
                `).join('')}
                ${!requests.length ? '<div style="padding:8px 12px;font-size:12px;color:var(--text-muted)">No requests</div>' : ''}
            </div>`;
    },

    async createCollection() {
        const name = prompt('Collection name:');
        if (!name) return;

        try {
            await App.api('/api/collections', {
                method: 'POST',
                body: { name }
            });
            App.toast('Collection created', 'success');
            this.refresh();
        } catch {
            App.toast('Failed to create collection', 'error');
        }
    },

    async deleteCollection(id) {
        if (!id || !confirm('Delete this collection?')) return;
        try {
            await App.api(`/api/collections/${id}`, { method: 'DELETE' });
            App.toast('Collection deleted', 'success');
            this.refresh();
        } catch {
            App.toast('Failed to delete collection', 'error');
        }
    },

    openInEditor(request) {
        Router.navigate('editor');
        setTimeout(() => {
            if (request.method) {
                document.getElementById('req-method').value = request.method;
            }
            if (request.url) {
                document.getElementById('req-url').value = request.url;
            }
            if (request.body) {
                document.getElementById('req-body').value = typeof request.body === 'string' ? request.body : JSON.stringify(request.body, null, 2);
            }
        }, 100);
    },

    filter(query) {
        const q = query.toLowerCase();
        const filtered = App.state.collections.filter(col =>
            (col.name || '').toLowerCase().includes(q)
        );
        this.renderTree(filtered);
    },

    escape(str) {
        const d = document.createElement('div');
        d.textContent = str || '';
        return d.innerHTML;
    }
};
