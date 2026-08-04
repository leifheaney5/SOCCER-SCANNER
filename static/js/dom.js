/* Minimal allow-list sanitizer for HTML assembled by the legacy renderers. */
const BLOCKED_ELEMENTS = 'script,style,iframe,object,embed,link,meta,base,form';
const URL_ATTRIBUTES = new Set(['href', 'src', 'action', 'formaction']);

function isSafeUrl(value) {
    try {
        const url = new URL(value, window.location.origin);
        return ['http:', 'https:', 'data:'].includes(url.protocol);
    } catch {
        return false;
    }
}

function sanitize(fragment) {
    fragment.querySelectorAll(BLOCKED_ELEMENTS).forEach(element => element.remove());
    fragment.querySelectorAll('*').forEach(element => {
        [...element.attributes].forEach(attribute => {
            const name = attribute.name.toLowerCase();
            if (name.startsWith('on') || name === 'style'
                || (URL_ATTRIBUTES.has(name) && !isSafeUrl(attribute.value))) {
                element.removeAttribute(attribute.name);
            }
        });
    });
    return fragment;
}

function setHTML(element, html) {
    const template = document.createElement('template');
    template.innerHTML = String(html);
    element.replaceChildren(sanitize(template.content));
}

window.safeDOM = Object.freeze({setHTML});

const navToggle = document.getElementById('nav-toggle');
const navigation = document.getElementById('primary-navigation');
if (navToggle && navigation) {
    const closeNavigation = () => {
        navToggle.setAttribute('aria-expanded', 'false');
        navToggle.querySelector('.sr-only').textContent = 'Open navigation';
        navigation.classList.remove('is-open');
    };
    navToggle.addEventListener('click', () => {
        const opening = navToggle.getAttribute('aria-expanded') !== 'true';
        navToggle.setAttribute('aria-expanded', String(opening));
        navToggle.querySelector('.sr-only').textContent = opening ? 'Close navigation' : 'Open navigation';
        navigation.classList.toggle('is-open', opening);
    });
    navigation.addEventListener('click', event => {
        if (event.target.closest('a')) closeNavigation();
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && navigation.classList.contains('is-open')) {
            closeNavigation();
            navToggle.focus();
        }
    });
    document.addEventListener('click', event => {
        if (!event.target.closest('.nav-container')) closeNavigation();
    });
}
