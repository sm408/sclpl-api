const Sidebar = {
    init() {
        // Keyboard shortcut to toggle search
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                document.getElementById('global-search').focus();
            }
        });
    }
};
