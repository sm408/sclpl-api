class NodeDetail {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = containerId;
            document.body.appendChild(this.container);
        }
        this._injectStyles();
        this.hide();
    }

    show(node) {
        if (!node) {
            this.hide();
            return;
        }
        this.container.innerHTML = '';

        const panel = document.createElement('div');
        panel.className = 'nd-panel';

        const header = this._header(node);
        const meta = this._meta(node);
        const config = this._config(node.config);

        panel.appendChild(header);
        panel.appendChild(meta);
        panel.appendChild(config);
        this.container.appendChild(panel);
        this.container.style.display = 'block';
    }

    hide() {
        this.container.innerHTML = '';
        this.container.style.display = 'none';
    }

    _header(node) {
        const el = document.createElement('div');
        el.className = 'nd-header';

        const title = document.createElement('span');
        title.className = 'nd-title';
        title.textContent = node.name;

        const close = document.createElement('button');
        close.className = 'nd-close';
        close.textContent = '\u00D7';
        close.addEventListener('click', () => this.hide());

        el.appendChild(title);
        el.appendChild(close);
        return el;
    }

    _meta(node) {
        const el = document.createElement('div');
        el.className = 'nd-meta';

        const rows = [
            ['Type', node.type],
            ['Status', this._statusLabel(node.status)],
            ['Duration', node.duration != null ? this._formatDuration(node.duration) : '\u2014'],
            ['Deps', node.deps.length > 0 ? node.deps.join(', ') : '\u2014'],
            ['Output', node.output || '\u2014'],
        ];

        for (const [label, value] of rows) {
            const row = document.createElement('div');
            row.className = 'nd-row';

            const lbl = document.createElement('span');
            lbl.className = 'nd-label';
            lbl.textContent = label + ':';

            const val = document.createElement('span');
            val.className = 'nd-value';

            if (label === 'Status') {
                val.innerHTML = value;
            } else {
                val.textContent = value;
            }

            row.appendChild(lbl);
            row.appendChild(val);
            el.appendChild(row);
        }

        return el;
    }

    _statusLabel(status) {
        const colors = {
            pending: '#616161',
            running: '#fdd835',
            success: '#4caf50',
            failed: '#f44336',
        };
        const color = colors[status] || colors.pending;
        return `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${color};margin-right:6px;vertical-align:middle;"></span>${status}`;
    }

    _config(config) {
        const el = document.createElement('div');
        el.className = 'nd-config-section';

        const label = document.createElement('div');
        label.className = 'nd-config-label';
        label.textContent = 'Config:';

        const pre = document.createElement('pre');
        pre.className = 'nd-config-json';
        pre.textContent = JSON.stringify(config, null, 2);

        el.appendChild(label);
        el.appendChild(pre);
        return el;
    }

    _formatDuration(ms) {
        if (ms < 1000) return ms + 'ms';
        if (ms < 60000) return (ms / 1000).toFixed(1) + 's';
        return (ms / 60000).toFixed(1) + 'min';
    }

    _injectStyles() {
        if (document.getElementById('nd-styles')) return;
        const style = document.createElement('style');
        style.id = 'nd-styles';
        style.textContent = `
            #${this.container.id} {
                position: fixed;
                top: 16px;
                right: 16px;
                z-index: 1000;
                width: 320px;
                max-height: calc(100vh - 32px);
                overflow-y: auto;
            }
            .nd-panel {
                background: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 10px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 13px;
                color: #cdd6f4;
                box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            }
            .nd-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 14px 16px;
                border-bottom: 1px solid #313244;
            }
            .nd-title {
                font-weight: 700;
                font-size: 15px;
                color: #ffffff;
            }
            .nd-close {
                background: none;
                border: none;
                color: #6c7086;
                font-size: 20px;
                cursor: pointer;
                line-height: 1;
                padding: 0 4px;
            }
            .nd-close:hover {
                color: #f44336;
            }
            .nd-meta {
                padding: 12px 16px;
                border-bottom: 1px solid #313244;
            }
            .nd-row {
                display: flex;
                gap: 8px;
                margin-bottom: 6px;
                align-items: center;
            }
            .nd-row:last-child {
                margin-bottom: 0;
            }
            .nd-label {
                min-width: 70px;
                color: #6c7086;
                font-weight: 600;
            }
            .nd-value {
                color: #cdd6f4;
                word-break: break-all;
            }
            .nd-config-section {
                padding: 12px 16px;
            }
            .nd-config-label {
                color: #6c7086;
                font-weight: 600;
                margin-bottom: 8px;
            }
            .nd-config-json {
                background: #181825;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 10px;
                margin: 0;
                font-family: 'Cascadia Code', 'Fira Code', monospace;
                font-size: 12px;
                color: #a6e3a1;
                overflow-x: auto;
                white-space: pre-wrap;
                max-height: 240px;
                overflow-y: auto;
            }
        `;
        document.head.appendChild(style);
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { NodeDetail };
}
