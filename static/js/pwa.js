const assetVersion = new URL(import.meta.url).searchParams.get('v') || 'development';

function showUpdateNotice() {
    if (document.querySelector('.pwa-update-notice')) return;
    const notice = document.createElement('div');
    notice.className = 'pwa-update-notice';
    notice.setAttribute('role', 'status');
    notice.textContent = 'Soccer Scanner updated. Refresh when convenient.';
    document.body.append(notice);
}

if ('serviceWorker' in navigator) {
    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (refreshing) return;
        refreshing = true;
        showUpdateNotice();
    });
    navigator.serviceWorker.register(
        `/static/sw.js?v=${encodeURIComponent(assetVersion)}`,
        {scope: '/', type: 'module', updateViaCache: 'none'},
    ).catch(() => {
        // PWA support is optional; the network application remains fully usable.
    });
}
