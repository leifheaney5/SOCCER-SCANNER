#!/usr/bin/env node
/**
 * Synthetic production monitor.
 *
 * Railway healthchecks only gate deploys, and `/health/ready` stays green when
 * the application is serving but every upstream provider is failing. This
 * exercises the surface a visitor actually uses and fails loudly when it breaks.
 */

import {pathToFileURL} from 'node:url';

const TODAY = () => new Date().toISOString().slice(0, 10);

export function evaluateChecks(checks) {
    const failures = checks
        .filter(check => !check.ok)
        .map(check => `${check.name}: ${check.detail}`);
    return {ok: failures.length === 0, failures};
}

async function probe(name, url, fetchImpl, validate) {
    try {
        const response = await fetchImpl(url);
        let body = null;
        try {
            body = await response.json();
        } catch {
            body = null;
        }
        return {name, ...validate(response, body)};
    } catch (error) {
        return {name, ok: false, detail: `request failed: ${error.message}`};
    }
}

export async function runMonitor(baseUrl, fetchImpl = fetch) {
    const base = String(baseUrl).replace(/\/$/, '');

    const checks = [
        await probe('live', `${base}/health/live`, fetchImpl, (response, body) => ({
            ok: response.status === 200 && body?.status === 'ok',
            detail: `HTTP ${response.status}`,
        })),
        await probe('ready', `${base}/health/ready`, fetchImpl, (response, body) => ({
            ok: response.status === 200 && body?.status === 'ready',
            detail: `HTTP ${response.status} blocking=${JSON.stringify(body?.blocking ?? null)}`,
        })),
        await probe('providers', `${base}/health/providers`, fetchImpl, (response, body) => ({
            // 'degraded' is tolerated: one provider down is survivable.
            ok: response.status === 200 && body?.status !== 'unavailable',
            detail: `status=${body?.status}`,
        })),
        await probe(
            'fixtures',
            `${base}/api/v2/fixtures?date=${TODAY()}&timezone=UTC`,
            fetchImpl,
            (response, body) => {
                if (response.status !== 200) {
                    return {ok: false, detail: `HTTP ${response.status} ${body?.error?.code ?? ''}`.trim()};
                }
                const matches = Array.isArray(body?.matches) ? body.matches : [];
                // `empty_confirmed` means the providers succeeded and there
                // really are no fixtures today — off-season and quiet days
                // are legitimate and must PASS, not be treated as an outage.
                // Anything else with zero matches (e.g. a provider-failure
                // state that still returned 200) is a genuine problem.
                const ok = matches.length > 0 || body?.state === 'empty_confirmed';
                const detail = matches.length > 0
                    ? `HTTP 200 with ${matches.length} fixtures returned`
                    : `HTTP 200 with 0 fixtures returned, state=${body?.state}`;
                return {ok, detail};
            },
        ),
    ];

    return {...evaluateChecks(checks), checks};
}

// Entry point when run directly. Compare resolved file URLs rather than
// string-matching paths, which breaks on Windows separators.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
    const target = process.env.MONITOR_BASE_URL || 'https://soccerscanner.pro';
    const result = await runMonitor(target);
    for (const check of result.checks) {
        console.log(`${check.ok ? 'PASS' : 'FAIL'} ${check.name} — ${check.detail}`);
    }
    if (!result.ok) {
        console.error(`\nSynthetic monitor FAILED against ${target}`);
        process.exit(1);
    }
    console.log(`\nSynthetic monitor passed against ${target}`);
}
