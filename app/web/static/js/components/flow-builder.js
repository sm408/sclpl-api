const FlowBuilder = {
    canvas: null,
    ctx: null,
    nodes: [],
    connections: [],
    dragging: null,
    panning: null,
    offset: { x: 0, y: 0 },
    selectedNode: null,
    nextId: 1,
    zoom: 1,
    panOffset: { x: 0, y: 0 },
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
                <button class="btn btn-sm" id="fb-export-image" title="Export as Image">
                    <i class="fas fa-image"></i> Image
                </button>
            </div>
            <div class="flow-canvas-container">
                <canvas id="flow-canvas" class="flow-canvas"></canvas>
                <div class="flow-zoom-controls">
                    <button class="btn btn-sm" id="fb-zoom-in" title="Zoom In"><i class="fas fa-plus"></i></button>
                    <button class="btn btn-sm" id="fb-zoom-reset" title="Reset Zoom"><i class="fas fa-compress"></i></button>
                    <button class="btn btn-sm" id="fb-zoom-out" title="Zoom Out"><i class="fas fa-minus"></i></button>
                    <button class="btn btn-sm" id="fb-fit" title="Fit to Screen"><i class="fas fa-expand"></i></button>
                </div>
                <div class="flow-zoom-info" id="fb-zoom-info">100%</div>
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
            document.getElementById('fb-node-properties').innerHTML = '';
            this.draw();
        });
        document.getElementById('fb-save').addEventListener('click', () => this.saveFlow());
        document.getElementById('fb-export-image').addEventListener('click', () => this.exportAsImage());

        // Zoom controls
        document.getElementById('fb-zoom-in').addEventListener('click', () => this.setZoom(this.zoom + 0.1));
        document.getElementById('fb-zoom-out').addEventListener('click', () => this.setZoom(this.zoom - 0.1));
        document.getElementById('fb-zoom-reset').addEventListener('click', () => { this.zoom = 1; this.panOffset = {x:0,y:0}; this.draw(); this.updateZoomInfo(); });
        document.getElementById('fb-fit').addEventListener('click', () => this.fitToScreen());

        // Canvas events
        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', () => this.onMouseUp());
        this.canvas.addEventListener('dblclick', (e) => this.onDblClick(e));
        this.canvas.addEventListener('wheel', (e) => this.onWheel(e));
    },

    resizeCanvas() {
        if (!this.canvas) return;
        const parent = this.canvas.parentElement;
        this.canvas.width = parent.clientWidth;
        this.canvas.height = parent.clientHeight;
        this.draw();
    },

    setZoom(val) {
        this.zoom = Math.max(0.2, Math.min(3, val));
        this.draw();
        this.updateZoomInfo();
    },

    updateZoomInfo() {
        const el = document.getElementById('fb-zoom-info');
        if (el) el.textContent = Math.round(this.zoom * 100) + '%';
    },

    onWheel(e) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.08 : 0.08;
        this.setZoom(this.zoom + delta);
    },

    fitToScreen() {
        if (!this.nodes.length) {
            this.zoom = 1;
            this.panOffset = { x: 0, y: 0 };
            this.draw();
            this.updateZoomInfo();
            return;
        }
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        this.nodes.forEach(n => {
            minX = Math.min(minX, n.x);
            minY = Math.min(minY, n.y);
            maxX = Math.max(maxX, n.x + n.width);
            maxY = Math.max(maxY, n.y + n.height);
        });
        const pad = 40;
        const contentW = maxX - minX + pad * 2;
        const contentH = maxY - minY + pad * 2;
        const scaleX = this.canvas.width / contentW;
        const scaleY = this.canvas.height / contentH;
        this.zoom = Math.min(scaleX, scaleY, 1.5);
        this.panOffset = {
            x: -minX * this.zoom + pad + (this.canvas.width - contentW * this.zoom) / 2,
            y: -minY * this.zoom + pad + (this.canvas.height - contentH * this.zoom) / 2
        };
        this.draw();
        this.updateZoomInfo();
    },

    addNode(type, x, y) {
        const node = {
            id: this.nextId++,
            type,
            x: x || (60 + Math.random() * 300 - this.panOffset.x / this.zoom),
            y: y || (60 + Math.random() * 200 - this.panOffset.y / this.zoom),
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

        ctx.save();
        ctx.translate(this.panOffset.x, this.panOffset.y);
        ctx.scale(this.zoom, this.zoom);

        // Grid
        const gridSize = 20;
        const startX = Math.floor(-this.panOffset.x / this.zoom / gridSize) * gridSize;
        const startY = Math.floor(-this.panOffset.y / this.zoom / gridSize) * gridSize;
        const endX = startX + this.canvas.width / this.zoom + gridSize * 2;
        const endY = startY + this.canvas.height / this.zoom + gridSize * 2;

        ctx.strokeStyle = '#e9ecef';
        ctx.lineWidth = 0.5;
        for (let x = startX; x < endX; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x, startY);
            ctx.lineTo(x, endY);
            ctx.stroke();
        }
        for (let y = startY; y < endY; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(startX, y);
            ctx.lineTo(endX, y);
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

            ctx.shadowColor = isSelected ? color : 'rgba(0,0,0,0.08)';
            ctx.shadowBlur = isSelected ? 12 : 4;
            ctx.shadowOffsetY = 2;

            ctx.fillStyle = '#ffffff';
            ctx.strokeStyle = isSelected ? color : '#e9ecef';
            ctx.lineWidth = isSelected ? 2 : 1;
            this.roundRect(ctx, node.x, node.y, node.width, node.height, 8);
            ctx.fill();
            ctx.stroke();

            ctx.shadowColor = 'transparent';
            ctx.shadowBlur = 0;
            ctx.shadowOffsetY = 0;

            ctx.fillStyle = color;
            this.roundRect(ctx, node.x, node.y, 4, node.height, 8);
            ctx.fill();

            ctx.fillStyle = color;
            ctx.font = '13px FontAwesome';
            const icons = { request: '\uf121', function: '\uf02b', condition: '\uf126', output: '\uf15c' };
            ctx.fillText(icons[node.type] || '\uf121', node.x + 16, node.y + 26);

            ctx.fillStyle = '#1a1a2e';
            ctx.font = '13px -apple-system, sans-serif';
            ctx.fillText(node.label, node.x + 36, node.y + 26);

            ctx.fillStyle = color;
            ctx.font = '10px -apple-system, sans-serif';
            ctx.fillText(node.type.toUpperCase(), node.x + 36, node.y + 44);

            ctx.beginPath();
            ctx.arc(node.x + node.width / 2, node.y + node.height, 4, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();
        });

        ctx.restore();
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

    screenToCanvas(x, y) {
        return {
            x: (x - this.panOffset.x) / this.zoom,
            y: (y - this.panOffset.y) / this.zoom
        };
    },

    getNodeAt(x, y) {
        const pt = this.screenToCanvas(x, y);
        for (let i = this.nodes.length - 1; i >= 0; i--) {
            const n = this.nodes[i];
            if (pt.x >= n.x && pt.x <= n.x + n.width && pt.y >= n.y && pt.y <= n.y + n.height) {
                return n;
            }
        }
        return null;
    },

    onMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;
        const node = this.getNodeAt(sx, sy);

        if (node) {
            const pt = this.screenToCanvas(sx, sy);
            this.dragging = node;
            this.offset = { x: pt.x - node.x, y: pt.y - node.y };
            this.selectedNode = node;
            this.showProperties(node);
        } else if (e.button === 0) {
            this.panning = { startX: sx, startY: sy, origX: this.panOffset.x, origY: this.panOffset.y };
            this.selectedNode = null;
            document.getElementById('fb-node-properties').innerHTML = '';
        }
        this.draw();
    },

    onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;

        if (this.dragging) {
            const pt = this.screenToCanvas(sx, sy);
            this.dragging.x = pt.x - this.offset.x;
            this.dragging.y = pt.y - this.offset.y;
            this.draw();
        } else if (this.panning) {
            this.panOffset.x = this.panning.origX + (sx - this.panning.startX);
            this.panOffset.y = this.panning.origY + (sy - this.panning.startY);
            this.draw();
        }
    },

    onMouseUp() {
        this.dragging = null;
        this.panning = null;
    },

    onDblClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;
        const node = this.getNodeAt(sx, sy);
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
        App.toast('Flow exported as JSON', 'success');
    },

    exportAsImage() {
        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');

        if (!this.nodes.length) {
            App.toast('No nodes to export', 'info');
            return;
        }

        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        this.nodes.forEach(n => {
            minX = Math.min(minX, n.x);
            minY = Math.min(minY, n.y);
            maxX = Math.max(maxX, n.x + n.width);
            maxY = Math.max(maxY, n.y + n.height);
        });

        const pad = 40;
        tempCanvas.width = maxX - minX + pad * 2;
        tempCanvas.height = maxY - minY + pad * 2;

        tempCtx.fillStyle = '#ffffff';
        tempCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);

        tempCtx.translate(-minX + pad, -minY + pad);

        // Draw grid
        tempCtx.strokeStyle = '#e9ecef';
        tempCtx.lineWidth = 0.5;
        for (let x = Math.floor(minX / 20) * 20; x < maxX + 20; x += 20) {
            tempCtx.beginPath();
            tempCtx.moveTo(x, minY - pad);
            tempCtx.lineTo(x, maxY + pad);
            tempCtx.stroke();
        }
        for (let y = Math.floor(minY / 20) * 20; y < maxY + 20; y += 20) {
            tempCtx.beginPath();
            tempCtx.moveTo(minX - pad, y);
            tempCtx.lineTo(maxX + pad, y);
            tempCtx.stroke();
        }

        // Draw connections
        tempCtx.strokeStyle = '#adb5bd';
        tempCtx.lineWidth = 2;
        this.connections.forEach(conn => {
            const from = this.nodes.find(n => n.id === conn.from);
            const to = this.nodes.find(n => n.id === conn.to);
            if (from && to) {
                const fx = from.x + from.width / 2;
                const fy = from.y + from.height;
                const tx = to.x + to.width / 2;
                const ty = to.y;
                tempCtx.beginPath();
                tempCtx.moveTo(fx, fy);
                tempCtx.bezierCurveTo(fx, fy + 40, tx, ty - 40, tx, ty);
                tempCtx.stroke();
                tempCtx.fillStyle = '#adb5bd';
                tempCtx.beginPath();
                tempCtx.moveTo(tx, ty);
                tempCtx.lineTo(tx - 6, ty - 10);
                tempCtx.lineTo(tx + 6, ty - 10);
                tempCtx.fill();
            }
        });

        // Draw nodes
        this.nodes.forEach(node => {
            const color = this.nodeColors[node.type] || '#6c757d';

            tempCtx.shadowColor = 'rgba(0,0,0,0.08)';
            tempCtx.shadowBlur = 4;
            tempCtx.shadowOffsetY = 2;

            tempCtx.fillStyle = '#ffffff';
            tempCtx.strokeStyle = '#e9ecef';
            tempCtx.lineWidth = 1;
            this.roundRect(tempCtx, node.x, node.y, node.width, node.height, 8);
            tempCtx.fill();
            tempCtx.stroke();

            tempCtx.shadowColor = 'transparent';
            tempCtx.shadowBlur = 0;
            tempCtx.shadowOffsetY = 0;

            tempCtx.fillStyle = color;
            this.roundRect(tempCtx, node.x, node.y, 4, node.height, 8);
            tempCtx.fill();

            tempCtx.fillStyle = '#1a1a2e';
            tempCtx.font = '13px -apple-system, sans-serif';
            tempCtx.fillText(node.label, node.x + 16, node.y + 26);

            tempCtx.fillStyle = color;
            tempCtx.font = '10px -apple-system, sans-serif';
            tempCtx.fillText(node.type.toUpperCase(), node.x + 16, node.y + 44);
        });

        const a = document.createElement('a');
        a.href = tempCanvas.toDataURL('image/png');
        a.download = 'flow.png';
        a.click();
        App.toast('Flow exported as image', 'success');
    },

    refresh() {
        setTimeout(() => this.resizeCanvas(), 50);
    }
};
