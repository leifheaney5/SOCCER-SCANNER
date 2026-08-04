const fixtureIdPattern = /^fx_[a-f0-9]{24}$/;


export function assertUniqueFixtureIds(matches) {
    if (!Array.isArray(matches)) {
        throw new Error('Fixture matches must be an array.');
    }
    const seen = new Set();
    for (const match of matches) {
        const fixtureId = match?.canonicalFixtureId;
        if (!fixtureIdPattern.test(fixtureId || '')) {
            throw new Error('Fixture has a missing or malformed canonicalFixtureId.');
        }
        if (seen.has(fixtureId)) {
            throw new Error(`Duplicate canonicalFixtureId detected: ${fixtureId}`);
        }
        seen.add(fixtureId);
    }
    return seen.size;
}


export function assertProductionDependenciesReady(readiness) {
    const blocking = readiness?.blocking;
    if (!Array.isArray(blocking) || blocking.length !== 0) {
        throw new Error(`Readiness has blocking dependencies: ${JSON.stringify(blocking)}`);
    }
    const database = readiness?.database;
    if (
        database?.durable !== true
        || database?.reachable !== true
        || database?.status !== 'ready'
        || !database?.schemaVersion
    ) {
        throw new Error('Production readiness does not report a durable database with a current schema.');
    }
    const cache = readiness?.cache;
    if (
        cache?.backend !== 'redis'
        || cache?.shared !== true
        || cache?.status !== 'ready'
    ) {
        throw new Error('Production readiness does not report shared Redis as ready.');
    }
}
