const TYPE_COLORS = {
    request: '#00bcd4',
    function: '#9c27b0',
    delay: '#9e9e9e',
};

const STATUS_COLORS = {
    pending: '#616161',
    running: '#fdd835',
    success: '#4caf50',
    failed: '#f44336',
};

const NODE_WIDTH = 180;
const NODE_HEIGHT = 64;
const NODE_RADIUS = 10;
const LAYER_GAP_X = 260;
const LAYER_GAP_Y = 100;
const PADDING = 40;

class FlowCanvas {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.nodes = [];
        this.edges = [];
        this.selectedNode = null;
        this.animationPhase = 0;
        this._animating = false;
        this._rafId = null;

        this._onResize = this._resize.bind(this);
        this._onClick = this.handleClick.bind(this);
        window.addEventListener('resize', this._onResize);
        this.canvas.addEventListener('click', this._onClick);

        this._resize();
    }

    destroy() {
        window.removeEventListener('resize', this._onResize);
        this.canvas.removeEventListener('click', this._onClick);
        if (this._rafId) cancelAnimationFrame(this._rafId);
    }

    loadWorkflow(workflow) {
        const steps = workflow.steps || [];
        this.nodes = steps.map((step) => ({
            id: step.id,
            name: step.name || step.id,
            type: step.type || 'request',
            status: step.status || 'pending',
            duration: step.duration ?? null,
            config: step.config || {},
            deps: step.depends_on || [],
            output: step.output || null,
            x: 0,
            y: 0,
            layer: 0,
        }));
        this._buildEdges();
        this._assignLayers();
        this._positionNodes();
        this.selectedNode = null;
        this.render();
    }

    _buildEdges() {
        this.edges = [];
        const idSet = new Set(this.nodes.map((n) => n.id));
        for (const node of this.nodes) {
            for (const dep of node.deps) {
                if (idSet.has(dep)) {
                    this.edges.push({ from: dep, to: node.id });
                }
            }
        }
    }

    _assignLayers() {
        const nodeMap = new Map(this.nodes.map((n) => [n.id, n]));
        const visited = new Set();
        const layers = new Map();

        const getLayer = (id) => {
            if (layers.has(id)) return layers.get(id);
            const node = nodeMap.get(id);
            if (!node || node.deps.length === 0) {
                layers.set(id, 0);
                return 0;
            }
            let maxDep = 0;
            for (const dep of node.deps) {
                if (nodeMap.has(dep)) {
                    maxDep = Math.max(maxDep, getLayer(dep) + 1);
                }
            }
            layers.set(id, maxDep);
            return maxDep;
        };

        for (const node of this.nodes) {
            getLayer(node.id);
        }

        for (const node of this.nodes) {
            node.layer = layers.get(node.id) || 0;
        }
    }

    _positionNodes() {
        const layerBuckets = new Map();
        for (const node of this.nodes) {
            if (!layerBuckets.has(node.layer)) layerBuckets.set(node.layer, []);
            layerBuckets.get(node.layer).push(node);
        }

        for (const [layer, bucket] of layerBuckets) {
            const totalHeight = bucket.length * NODE_HEIGHT + (bucket.length - 1) * (LAYER_GAP_Y - NODE_HEIGHT);
            const startY = PADDING + (this._contentHeight() - totalHeight) / 2;
            bucket.forEach((node, i) => {
                node.x = PADDING + layer * LAYER_GAP_X;
                node.y = startY + i * LAYER_GAP_Y;
            });
        }
    }

    _contentHeight() {
        const layerBuckets = new Map();
        for (const node of this.nodes) {
            if (!layerBuckets.has(node.layer)) layerBuckets.set(node.layer, []);
            layerBuckets.get(node.layer).push(node);
        }
        let maxH = 0;
        for (const bucket of layerBuckets.values()) {
            const h = bucket.length * NODE_HEIGHT + (bucket.length - 1) * (LAYER_GAP_Y - NODE_HEIGHT);
            if (h > maxH) maxH = h;
        }
        return maxH;
    }

    _resize() {
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.parentElement
            ? this.canvas.parentElement.getBoundingClientRect()
            : { width: this.canvas.width, height: this.canvas.height };
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this._fitCanvas();
        this.render();
    }

    _fitCanvas() {
        if (this.nodes.length === 0) return;
        let maxX = 0;
        let maxY = 0;
        for (const n of this.nodes) {
            if (n.x + NODE_WIDTH + PADDING > maxX) maxX = n.x + NODE_WIDTH + PADDING;
            if (n.y + NODE_HEIGHT + PADDING > maxY) maxY = n.y + NODE_HEIGHT + PADDING;
        }
        const cssW = parseInt(this.canvas.style.width, 10) || this.canvas.clientWidth;
        const cssH = parseInt(this.canvas.style.height, 10) || this.canvas.clientHeight;
        const w = Math.max(maxX, cssW);
        const h = Math.max(maxY, cssH);
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    render() {
        const ctx = this.ctx;
        const w = parseInt(this.canvas.style.width, 10);
        const h = parseInt(this.canvas.style.height, 10);
        ctx.clearRect(0, 0, w, h);

        for (const edge of this.edges) {
            this.drawEdge(edge);
        }
        for (const node of this.nodes) {
            this.drawNode(node);
        }
    }

    drawNode(node) {
        const ctx = this.ctx;
        const { x, y, name, type, status, duration } = node;
        const isSelected = this.selectedNode && this.selectedNode.id === node.id;

        ctx.save();
        ctx.shadowColor = 'rgba(0,0,0,0.25)';
        ctx.shadowBlur = 8;
        ctx.shadowOffsetY = 2;

        ctx.fillStyle = this._nodeBackground(type, status);
        this._roundRect(ctx, x, y, NODE_WIDTH, NODE_HEIGHT, NODE_RADIUS);
        ctx.fill();

        ctx.shadowColor = 'transparent';

        if (isSelected) {
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            this._roundRect(ctx, x, y, NODE_WIDTH, NODE_HEIGHT, NODE_RADIUS);
            ctx.stroke();
        }

        const typeColor = TYPE_COLORS[type] || TYPE_COLORS.request;
        ctx.fillStyle = typeColor;
        ctx.beginPath();
        ctx.roundRect(x, y, 6, NODE_HEIGHT, [NODE_RADIUS, 0, 0, NODE_RADIUS]);
        ctx.fill();

        const icon = this._typeIcon(type);
        ctx.font = '16px sans-serif';
        ctx.fillStyle = '#ffffff';
        ctx.textBaseline = 'middle';
        ctx.fillText(icon, x + 16, y + NODE_HEIGHT / 2);

        ctx.font = 'bold 13px sans-serif';
        ctx.fillStyle = '#ffffff';
        ctx.textBaseline = 'middle';
        const maxLabelW = NODE_WIDTH - 60;
        const label = this._truncText(ctx, name, maxLabelW);
        ctx.fillText(label, x + 36, y + NODE_HEIGHT / 2 - (duration != null ? 8 : 0));

        if (duration != null) {
            ctx.font = '11px sans-serif';
            ctx.fillStyle = 'rgba(255,255,255,0.7)';
            ctx.fillText(this._formatDuration(duration), x + 36, y + NODE_HEIGHT / 2 + 10);
        }

        const statusColor = STATUS_COLORS[status] || STATUS_COLORS.pending;
        ctx.beginPath();
        ctx.arc(x + NODE_WIDTH - 16, y + 16, 6, 0, Math.PI * 2);
        ctx.fillStyle = statusColor;
        ctx.fill();

        if (status === 'running') {
            ctx.beginPath();
            const pulse = 6 + Math.sin(this.animationPhase * 0.08) * 4;
            ctx.arc(x + NODE_WIDTH - 16, y + 16, pulse, 0, Math.PI * 2);
            ctx.strokeStyle = STATUS_COLORS.running;
            ctx.lineWidth = 2;
            ctx.globalAlpha = 0.5 + Math.sin(this.animationPhase * 0.08) * 0.3;
            ctx.stroke();
            ctx.globalAlpha = 1;
        }

        ctx.restore();
    }

    drawEdge(edge) {
        const fromNode = this.nodes.find((n) => n.id === edge.from);
        const toNode = this.nodes.find((n) => n.id === edge.to);
        if (!fromNode || !toNode) return;

        const ctx = this.ctx;
        const x1 = fromNode.x + NODE_WIDTH;
        const y1 = fromNode.y + NODE_HEIGHT / 2;
        const x2 = toNode.x;
        const y2 = toNode.y + NODE_HEIGHT / 2;
        const cpx = (x1 + x2) / 2;

        ctx.save();
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.bezierCurveTo(cpx, y1, cpx, y2, x2, y2);
        ctx.strokeStyle = 'rgba(255,255,255,0.2)';
        ctx.lineWidth = 2;

        const isRunning = fromNode.status === 'running' || toNode.status === 'running';
        if (isRunning) {
            ctx.setLineDash([8, 4]);
            ctx.lineDashOffset = -this.animationPhase;
            ctx.strokeStyle = STATUS_COLORS.running;
        }

        ctx.stroke();
        ctx.setLineDash([]);

        const angle = Math.atan2(y2 - y1, x2 - x1);
        const aLen = 10;
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - aLen * Math.cos(angle - 0.4), y2 - aLen * Math.sin(angle - 0.4));
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - aLen * Math.cos(angle + 0.4), y2 - aLen * Math.sin(angle + 0.4));
        ctx.strokeStyle = 'rgba(255,255,255,0.4)';
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.restore();
    }

    handleClick(event) {
        const rect = this.canvas.getBoundingClientRect();
        const mx = event.clientX - rect.left;
        const my = event.clientY - rect.top;

        let hit = null;
        for (const node of this.nodes) {
            if (mx >= node.x && mx <= node.x + NODE_WIDTH && my >= node.y && my <= node.y + NODE_HEIGHT) {
                hit = node;
                break;
            }
        }

        this.selectedNode = hit;
        this.render();

        if (this._onNodeSelected) {
            this._onNodeSelected(hit);
        }
    }

    onNodeSelected(callback) {
        this._onNodeSelected = callback;
    }

    updateStatus(stepId, status, duration) {
        const node = this.nodes.find((n) => n.id === stepId);
        if (!node) return;
        node.status = status;
        if (duration !== undefined) node.duration = duration;
        this.render();
        this._startAnimationLoop();
    }

    _startAnimationLoop() {
        if (this._animating) return;
        this._animating = true;
        const tick = () => {
            this.animationPhase++;
            this.render();
            const hasRunning = this.nodes.some((n) => n.status === 'running');
            if (hasRunning) {
                this._rafId = requestAnimationFrame(tick);
            } else {
                this._animating = false;
            }
        };
        this._rafId = requestAnimationFrame(tick);
    }

    _nodeBackground(type, status) {
        if (status === 'failed') return 'rgba(244,67,54,0.3)';
        if (status === 'success') return 'rgba(76,175,80,0.15)';
        const c = TYPE_COLORS[type] || TYPE_COLORS.request;
        return c + '33';
    }

    _typeIcon(type) {
        switch (type) {
            case 'request':
                return '\u2192';
            case 'function':
                return '\u0192';
            case 'delay':
                return '\u23F1';
            default:
                return '\u25CB';
        }
    }

    _formatDuration(ms) {
        if (ms < 1000) return ms + 'ms';
        if (ms < 60000) return (ms / 1000).toFixed(1) + 's';
        return (ms / 60000).toFixed(1) + 'min';
    }

    _truncText(ctx, text, maxWidth) {
        if (ctx.measureText(text).width <= maxWidth) return text;
        let t = text;
        while (t.length > 1 && ctx.measureText(t + '\u2026').width > maxWidth) {
            t = t.slice(0, -1);
        }
        return t + '\u2026';
    }

    _roundRect(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, r);
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { FlowCanvas, TYPE_COLORS, STATUS_COLORS };
}
