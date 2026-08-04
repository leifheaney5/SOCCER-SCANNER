export function createDialogManager({documentRef = document} = {}) {
    const stack = [];
    const restoreRules = new WeakMap();
    const initialized = new WeakSet();

    function sync() {
        stack.forEach((entry, index) => {
            entry.dialog.toggleAttribute('inert', index !== stack.length - 1);
        });
        documentRef.body.classList.toggle('dialog-open', stack.length > 0);
    }

    function initialize(dialog) {
        if (initialized.has(dialog)) return;
        initialized.add(dialog);
        dialog.addEventListener('close', () => {
            const index = stack.findIndex(entry => entry.dialog === dialog);
            const [entry] = index >= 0 ? stack.splice(index, 1) : [];
            dialog.removeAttribute('inert');
            sync();
            const shouldRestore = restoreRules.get(dialog) !== false;
            restoreRules.delete(dialog);
            if (shouldRestore && entry?.trigger?.isConnected) entry.trigger.focus();
        });
    }

    function open(dialog, trigger = null) {
        initialize(dialog);
        const existing = stack.find(entry => entry.dialog === dialog);
        if (existing) {
            existing.trigger = trigger || existing.trigger;
            return;
        }
        stack.push({dialog, trigger});
        sync();
        if (!dialog.open) dialog.showModal();
    }

    function close(dialog, {restoreFocus = true} = {}) {
        if (!dialog.open) return;
        restoreRules.set(dialog, restoreFocus);
        dialog.close();
    }

    function closeTop() {
        const top = stack.at(-1);
        if (top) close(top.dialog);
    }

    return {open, close, closeTop, depth: () => stack.length};
}
