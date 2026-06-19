const App = {
    state: {
        currentRoute: 'home',
        baseUrl: 'http://localhost:8000',
        collections: [],
        workflows: [],
        functions: [],
        history: [],
        currentRequest: {
            method: 'GET',
            url: '',
            params: [],
            headers: [],
            body: '',
            auth: { type: 'none' }
        },
        currentResponse: null,
        theme: localStorage.getItem('sclplapi-theme') || 'light'
    },

    init() {
        this.applyTheme(this.state.theme);
        Sidebar.init();
        Router.init();
        RequestEditor.init();
        WorkflowRunner.init();
        Collections.init();
        History.init();
        Functions.init();
        FlowBuilder.init();
        this.bindGlobal();
        this.loadStats();
    },

    bindGlobal() {
        document.getElementById('btn-new-request').addEventListener('click', () => {
            Router.navigate('editor');
        });

        document.getElementById('btn-import').addEventListener('click', () => {
            App.toast('Import coming soon', 'info');
        });

        document.getElementById('btn-settings').addEventListener('click', () => {
            Router.navigate('settings');
        });

        // Theme toggle
        document.getElementById('btn-theme-toggle').addEventListener('click', () => {
            const newTheme = this.state.theme === 'dark' ? 'light' : 'dark';
            this.applyTheme(newTheme);
            App.toast(`Switched to ${newTheme} theme`, 'info');
        });

        // Mobile menu
        const mobileBtn = document.getElementById('btn-mobile-menu');
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebar-overlay');
        if (mobileBtn) {
            mobileBtn.addEventListener('click', () => {
                sidebar.classList.toggle('open');
                overlay.classList.toggle('active');
            });
        }
        if (overlay) {
            overlay.addEventListener('click', () => {
                sidebar.classList.remove('open');
                overlay.classList.remove('active');
            });
        }

        // Close mobile sidebar on nav
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                sidebar.classList.remove('open');
                overlay.classList.remove('active');
            });
        });

        document.querySelectorAll('.dash-card').forEach(card => {
            card.addEventListener('click', () => {
                const nav = card.dataset.nav;
                if (nav) Router.navigate(nav);
            });
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl+K: focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                document.getElementById('global-search').focus();
            }
            // Ctrl+N: new request
            if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
                e.preventDefault();
                Router.navigate('editor');
                setTimeout(() => document.getElementById('req-url')?.focus(), 100);
            }
            // Ctrl+Enter: send request (when in editor)
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                if (App.state.currentRoute === 'editor') {
                    e.preventDefault();
                    document.getElementById('btn-send')?.click();
                }
            }
            // Escape: close modals / blur
            if (e.key === 'Escape') {
                document.activeElement?.blur();
                document.querySelectorAll('.modal-overlay').forEach(m => m.remove());
            }
        });

        // Settings theme sync
        const settingTheme = document.getElementById('setting-theme');
        if (settingTheme) {
            settingTheme.value = this.state.theme;
            settingTheme.addEventListener('change', (e) => {
                this.applyTheme(e.target.value);
            });
        }
    },

    applyTheme(theme) {
        this.state.theme = theme;
        localStorage.setItem('sclplapi-theme', theme);
        document.documentElement.setAttribute('data-theme', theme);
        const icon = document.querySelector('#btn-theme-toggle i');
        if (icon) {
            icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
        const settingTheme = document.getElementById('setting-theme');
        if (settingTheme) settingTheme.value = theme;
    },

    async loadStats() {
        try {
            const [colls, flows, funcs] = await Promise.all([
                App.api('/api/collections').catch(() => []),
                App.api('/api/workflows').catch(() => []),
                App.api('/api/functions').catch(() => [])
            ]);
            this.state.collections = Array.isArray(colls) ? colls : [];
            this.state.workflows = Array.isArray(flows) ? flows : [];
            this.state.functions = Array.isArray(funcs) ? funcs : [];

            document.getElementById('stat-collections').textContent = this.state.collections.length;
            document.getElementById('stat-workflows').textContent = this.state.workflows.length;
            document.getElementById('stat-functions').textContent = this.state.functions.length;
        } catch (e) {
            // API not available
        }
    },

    async api(path, options = {}) {
        const url = this.state.baseUrl + path;
        const config = {
            headers: { 'Content-Type': 'application/json' },
            ...options
        };
        if (options.body && typeof options.body === 'object') {
            config.body = JSON.stringify(options.body);
        }
        const res = await fetch(url, config);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const contentType = res.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return res.json();
        }
        return res.text();
    },

    toast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        const icons = { success: 'fa-check-circle', error: 'fa-exclamation-circle', info: 'fa-info-circle', warning: 'fa-exclamation-triangle' };
        toast.innerHTML = `
            <i class="fas ${icons[type] || icons.info} toast-icon"></i>
            <span>${message}</span>
            <button class="toast-close" onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>
        `;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(20px)';
            toast.style.transition = '0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    },

    formatJson(obj) {
        try {
            if (typeof obj === 'string') obj = JSON.parse(obj);
            return JSON.stringify(obj, null, 2);
        } catch {
            return obj;
        }
    },

    highlightJson(obj) {
        const str = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2);
        if (!str) return '';
        return str.replace(/("(?:\\.|[^"\\])*")\s*:/g, '<span class="json-key">$1</span><span class="json-colon">:</span>')
            .replace(/:\s*("(?:\\.|[^"\\])*")/g, ': <span class="json-string">$1</span>')
            .replace(/:\s*(\d+\.?\d*)/g, ': <span class="json-number">$1</span>')
            .replace(/:\s*(true|false)/g, ': <span class="json-boolean">$1</span>')
            .replace(/:\s*(null)/g, ': <span class="json-null">$1</span>')
            .replace(/([{}\[\]])/g, '<span class="json-bracket">$1</span>');
    },

    formatBytes(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    },

    formatDuration(ms) {
        if (ms < 1000) return ms + ' ms';
        return (ms / 1000).toFixed(2) + ' s';
    },

    getStatusClass(code) {
        if (code >= 200 && code < 300) return 'status-2xx';
        if (code >= 300 && code < 400) return 'status-3xx';
        if (code >= 400 && code < 500) return 'status-4xx';
        return 'status-5xx';
    }
};

const Router = {
    init() {
        window.addEventListener('hashchange', () => this.handleRoute());
        document.querySelectorAll('[data-route]').forEach(el => {
            el.addEventListener('click', (e) => {
                e.preventDefault();
                this.navigate(el.dataset.route);
            });
        });
        this.handleRoute();
    },

    navigate(route) {
        window.location.hash = route;
    },

    handleRoute() {
        const hash = window.location.hash.slice(1) || 'home';
        const route = hash.split('/')[0];
        App.state.currentRoute = route;

        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        const view = document.getElementById(`view-${route}`);
        if (view) view.classList.add('active');

        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        const nav = document.querySelector(`.nav-item[data-route="${route}"]`);
        if (nav) nav.classList.add('active');

        if (route === 'collections') Collections.refresh();
        if (route === 'flows') WorkflowRunner.refresh();
        if (route === 'functions') Functions.refresh();
        if (route === 'history') History.refresh();
        if (route === 'flow-builder') FlowBuilder.refresh();
    }
};
