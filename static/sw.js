import {sanitizeFixturePayload} from './js/offline-cache.js';

const version = new URL(self.location.href).searchParams.get('v') || 'development';
const shellCacheName = `soccer-scanner-shell-${version}`;
const fixtureCacheName = `soccer-scanner-fixtures-${version}`;
const shellUrls = [
    '/',
    '/offline',
    '/static/manifest.webmanifest',
    '/static/favicon.svg',
    '/static/icons/favicon-32.png',
    '/static/icons/apple-touch-icon.png',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/static/icons/icon-maskable-512.png',
    `/static/css/base.css?v=${encodeURIComponent(version)}`,
    `/static/js/dom.js?v=${encodeURIComponent(version)}`,
    `/static/js/pwa.js?v=${encodeURIComponent(version)}`,
];

self.addEventListener('install', event => {
    event.waitUntil(caches.open(shellCacheName).then(cache => cache.addAll(shellUrls)));
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil((async () => {
        const current = new Set([shellCacheName, fixtureCacheName]);
        const names = await caches.keys();
        await Promise.all(names
            .filter(name => name.startsWith('soccer-scanner-') && !current.has(name))
            .map(name => caches.delete(name)));
        await self.clients.claim();
    })());
});

async function cacheSpoilerSafeSnapshot(request, response) {
    try {
        const payload = await response.json();
        const sanitized = sanitizeFixturePayload(payload);
        const cachedResponse = new Response(JSON.stringify(sanitized), {
            status: 200,
            headers: {'Content-Type': 'application/json', 'X-Soccer-Scanner-Offline': '1'},
        });
        const cache = await caches.open(fixtureCacheName);
        await cache.put(request, cachedResponse);
    } catch {
        // Invalid or non-fixture responses are never persisted.
    }
}

async function fixtureRequest(request) {
    try {
        const response = await fetch(request);
        if (response.ok) await cacheSpoilerSafeSnapshot(request, response.clone());
        return response;
    } catch {
        const cached = await caches.match(request, {cacheName: fixtureCacheName});
        return cached || new Response(JSON.stringify({
            error: {code: 'offline', message: 'No spoiler-safe fixture snapshot is available.', retryable: true},
        }), {status: 503, headers: {'Content-Type': 'application/json'}});
    }
}

async function navigationRequest(request) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(shellCacheName);
            await cache.put(request, response.clone());
        }
        return response;
    } catch {
        return (await caches.match(request)) || (await caches.match('/offline'));
    }
}

async function staticRequest(request) {
    const cached = await caches.match(request);
    if (cached) return cached;
    const response = await fetch(request);
    if (response.ok) {
        const cache = await caches.open(shellCacheName);
        await cache.put(request, response.clone());
    }
    return response;
}

self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
    if (url.pathname === '/api/v2/fixtures') {
        event.respondWith(fixtureRequest(event.request));
    } else if (event.request.mode === 'navigate') {
        event.respondWith(navigationRequest(event.request));
    } else if (url.pathname.startsWith('/static/')) {
        event.respondWith(staticRequest(event.request));
    }
});
