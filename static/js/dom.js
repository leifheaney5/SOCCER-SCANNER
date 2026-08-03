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
