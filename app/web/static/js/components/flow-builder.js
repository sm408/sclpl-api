const FlowBuilder = {
    canvas: null,
    ctx: null,
    nodes: [],
    connections: [],
    dragging: null,
    offset: { x: 0, y: 0 },
    selectedNode: null,
    nextId: 1,
    nodeColors: {
        request: '#00d2ff',
        function: '#3a7bd5',
        condition: '#f59e0b',
        output: '#10b981'
    },

    init() {
        this.container = document.getElementById('view-flow-builder');
        this.render();
    },

    render() {
        this.container.innerHTML = `
            <div class="view-header">
                <h1>Flow Builder</h1>
                <p class="subtitle">Visually compose workflow pipelines</p>
            </div>
            <div class="flow-toolbar">
                <button class="btn btn-sm" id="fb-add-request" title="Add Request Node">
                    <i class="fas fa-code" style="color:var(--accent)"></i> Request
                </button>
                <button class="btn btn-sm" id="fb-add-function" title="Add Function Node">
                    <i class="fas fa-code" style="color:var(--accent-dark)"></i> Function
                </button>
                <button class="btn btn-sm" id="fb-add-condition" title="Add Condition Node">
                    <i class="fas fa-code-branch" style="color:var(--warning)"></i> Condition
                </button>
                <button class="btn btn-sm" id="fb-add-output" title="Add Output Node">
                    <i class="fas fa-file-export" style="color:var(--success)"></i> Output
                </button>
                <div style="width:1px;background:var(--border);margin:0 4px"></div>
                <button class="btn btn-sm" id="fb-clear" title="Clear Canvas">
                    <i class="fas fa-trash"></i>
                </button>
                <button class="btn btn-sm" id="fb-save" title="Save Flow">
                    <i class="fas fa-save"></i> Save
                </button>
            </div>
            <div class="flow-canvas-container">
                <canvas id="flow-canvas" class="flow-canvas"></canvas>
            </div>
            <div id="fb-node-properties" style="margin-top:16px"></div>
        `;

        this.canvas = document.getElementById('flow-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();

        window.addEventListener('resize', () => this.resizeCanvas());

        // Toolbar
        document.getElementById('fb-add-request').addEventListener('click', () => this.addNode('request'));
        document.getElementById('fb-add-function').addEventListener('click', () => this.addNode('function'));
        document.getElementById('fb-add-condition').addEventListener('click', () => this.addNode('condition'));
        document.getElementById('fb-add-output').addEventListener('click', () => this.addNode('output'));
        document.getElementById('fb-clear').addEventListener('click', () => {
            this.nodes = [];
            this.connections = [];
            this.selectedNode = null;
            this.draw();
        });
        document.getElementById('fb-save').addEventListener('click', () => this.saveFlow());

        // Canvas events
        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', () => this.onMouseUp());
        this.canvas.addEventListener('dblclick', (e) => this.onDblClick(e));
    },

    resizeCanvas() {
        if (!this.canvas) return;
        const parent = this.canvas.parentElement;
        this.canvas.width = parent.clientWidth;
        this.canvas.height = parent.clientHeight;
        this.draw();
    },

    addNode(type, x, y) {
        const node = {
            id: this.nextId++,
            type,
            x: x || 60 + Math.random() * 300,
            y: y || 60 + Math.random() * 200,
            width: 160,
            height: 60,
            label: `${type.charAt(0).toUpperCase() + type.slice(1)} ${this.nextId - 1}`
        };
        this.nodes.push(node);
        this.draw();
    },

    draw() {
        if (!this.ctx) return;
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Grid
        ctx.strokeStyle = '#e9ecef';
        ctx.lineWidth = 0.5;
        for (let x = 0; x < this.canvas.width; x += 20) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, this.canvas.height);
            ctx.stroke();
        }
        for (let y = 0; y < this.canvas.height; y += 20) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(this.canvas.width, y);
            ctx.stroke();
        }

        // Connections
        ctx.strokeStyle = '#adb5bd';
        ctx.lineWidth = 2;
        this.connections.forEach(conn => {
            const from = this.nodes.find(n => n.id === conn.from);
            const to = this.nodes.find(n => n.id === conn.to);
            if (from && to) {
                const fx = from.x + from.width / 2;
                const fy = from.y + from.height;
                const tx = to.x + to.width / 2;
                const ty = to.y;
                ctx.beginPath();
                ctx.moveTo(fx, fy);
                ctx.bezierCurveTo(fx, fy + 40, tx, ty - 40, tx, ty);
                ctx.stroke();

                // Arrowhead
                const angle = Math.atan2(ty - (ty - 40), tx - tx);
                ctx.fillStyle = '#adb5bd';
                ctx.beginPath();
                ctx.moveTo(tx, ty);
                ctx.lineTo(tx - 6, ty - 10);
                ctx.lineTo(tx + 6, ty - 10);
                ctx.fill();
            }
        });

        // Nodes
        this.nodes.forEach(node => {
            const color = this.nodeColors[node.type] || '#6c757d';
            const isSelected = this.selectedNode === node;

            // Shadow
            ctx.shadowColor = isSelected ? color : 'rgba(0,0,0,0.08)';
            ctx.shadowBlur = isSelected ? 12 : 4;
            ctx.shadowOffsetY = 2;

            // Body
            ctx.fillStyle = '#ffffff';
            ctx.strokeStyle = isSelected ? color : '#e9ecef';
            ctx.lineWidth = isSelected ? 2 : 1;
            this.roundRect(ctx, node.x, node.y, node.width, node.height, 8);
            ctx.fill();
            ctx.stroke();

            // Reset shadow
            ctx.shadowColor = 'transparent';
            ctx.shadowBlur = 0;
            ctx.shadowOffsetY = 0;

            // Type indicator bar
            ctx.fillStyle = color;
            this.roundRect(ctx, node.x, node.y, 4, node.height, 8);
            ctx.fill();

            // Icon
            ctx.fillStyle = color;
            ctx.font = '13px FontAwesome';
            const icons = { request: '\uf121', function: '\uf02b', condition: '\uf126', output: '\uf15c' };
            ctx.fillText(icons[node.type] || '\uf121', node.x + 16, node.y + 26);

            // Label
            ctx.fillStyle = '#1a1a2e';
            ctx.font = '13px -apple-system, sans-serif';
            ctx.fillText(node.label, node.x + 36, node.y + 26);

            // Type tag
            ctx.fillStyle = color;
            ctx.font = '10px -apple-system, sans-serif';
            ctx.fillText(node.type.toUpperCase(), node.x + 36, node.y + 44);

            // Connection anchor (bottom)
            ctx.beginPath();
            ctx.arc(node.x + node.width / 2, node.y + node.height, 4, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();
        });
    },

    roundRect(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
    },

    getNodeAt(x, y) {
        for (let i = this.nodes.length - 1; i >= 0; i--) {
            const n = this.nodes[i];
            if (x >= n.x && x <= n.x + n.width && y >= n.y && y <= n.y + n.height) {
                return n;
            }
        }
        return null;
    },

    onMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const node = this.getNodeAt(x, y);

        if (node) {
            this.dragging = node;
            this.offset = { x: x - node.x, y: y - node.y };
            this.selectedNode = node;
            this.showProperties(node);
        } else {
            this.selectedNode = null;
            document.getElementById('fb-node-properties').innerHTML = '';
        }
        this.draw();
    },

    onMouseMove(e) {
        if (!this.dragging) return;
        const rect = this.canvas.getBoundingClientRect();
        this.dragging.x = e.clientX - rect.left - this.offset.x;
        this.dragging.y = e.clientY - rect.top - this.offset.y;
        this.draw();
    },

    onMouseUp() {
        this.dragging = null;
    },

    onDblClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const node = this.getNodeAt(x, y);
        if (node) {
            const newLabel = prompt('Node label:', node.label);
            if (newLabel !== null) {
                node.label = newLabel;
                this.draw();
            }
        }
    },

    showProperties(node) {
        const container = document.getElementById('fb-node-properties');
        container.innerHTML = `
            <div class="settings-section">
                <h3>Node Properties</h3>
                <div class="setting-row">
                    <label>Label</label>
                    <input type="text" class="input" id="fb-prop-label" value="${node.label}" style="width:250px">
                </div>
                <div class="setting-row">
                    <label>Type</label>
                    <select class="input" id="fb-prop-type" style="width:250px">
                        <option value="request" ${node.type === 'request' ? 'selected' : ''}>Request</option>
                        <option value="function" ${node.type === 'function' ? 'selected' : ''}>Function</option>
                        <option value="condition" ${node.type === 'condition' ? 'selected' : ''}>Condition</option>
                        <option value="output" ${node.type === 'output' ? 'selected' : ''}>Output</option>
                    </select>
                </div>
                <div style="margin-top:12px;display:flex;gap:8px">
                    <button class="btn btn-sm btn-danger" id="fb-delete-node"><i class="fas fa-trash"></i> Delete</button>
                </div>
            </div>
        `;

        document.getElementById('fb-prop-label').addEventListener('input', (e) => {
            node.label = e.target.value;
            this.draw();
        });
        document.getElementById('fb-prop-type').addEventListener('change', (e) => {
            node.type = e.target.value;
            this.draw();
        });
        document.getElementById('fb-delete-node').addEventListener('click', () => {
            this.nodes = this.nodes.filter(n => n.id !== node.id);
            this.connections = this.connections.filter(c => c.from !== node.id && c.to !== node.id);
            this.selectedNode = null;
            container.innerHTML = '';
            this.draw();
        });
    },

    saveFlow() {
        const flow = {
            nodes: this.nodes,
            connections: this.connections
        };
        const json = JSON.stringify(flow, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'flow.json';
        a.click();
        URL.revokeObjectURL(url);
        App.toast('Flow exported', 'success');
    },

    refresh() {
        setTimeout(() => this.resizeCanvas(), 50);
    }
};
