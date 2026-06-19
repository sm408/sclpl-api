const Sidebar = {
    collapsed: false,

    init() {
        this.sidebar = document.getElementById('sidebar');
        this.mainContent = document.getElementById('main-content');

        // Add collapse toggle button
        const toggle = document.createElement('button');
        toggle.className = 'sidebar-toggle';
        toggle.innerHTML = '<i class="fas fa-angles-left"></i>';
        toggle.title = 'Collapse sidebar';
        this.sidebar.appendChild(toggle);

        toggle.addEventListener('click', () => this.toggle());

        // Restore state from localStorage
        const saved = localStorage.getItem('sclplapi-sidebar-collapsed');
        if (saved === 'true') {
            this.collapse();
        }
    },

    toggle() {
        if (this.collapsed) {
            this.expand();
        } else {
            this.collapse();
        }
    },

    collapse() {
        this.collapsed = true;
        this.sidebar.classList.add('collapsed');
        if (this.mainContent) this.mainContent.classList.add('sidebar-collapsed');
        const icon = this.sidebar.querySelector('.sidebar-toggle i');
        if (icon) icon.className = 'fas fa-angles-right';
        localStorage.setItem('sclplapi-sidebar-collapsed', 'true');
    },

    expand() {
        this.collapsed = false;
        this.sidebar.classList.remove('collapsed');
        if (this.mainContent) this.mainContent.classList.remove('sidebar-collapsed');
        const icon = this.sidebar.querySelector('.sidebar-toggle i');
        if (icon) icon.className = 'fas fa-angles-left';
        localStorage.setItem('sclplapi-sidebar-collapsed', 'false');
    }
};
