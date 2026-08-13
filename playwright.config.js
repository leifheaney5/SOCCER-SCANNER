import {defineConfig} from '@playwright/test';

export default defineConfig({
    testDir: './tests/browser',
    timeout: 30_000,
    expect: {timeout: 5_000},
    fullyParallel: false,
    workers: 1,
    outputDir: 'test-results',
    preserveOutput: 'always',
    projects: [
        {name: 'chromium', use: {browserName: 'chromium'}},
        {name: 'webkit', use: {browserName: 'webkit'}},
    ],
    use: {
        baseURL: 'http://127.0.0.1:5100',
        colorScheme: 'dark',
        locale: 'en-US',
        timezoneId: 'America/New_York',
        trace: 'retain-on-failure',
        serviceWorkers: 'block',
    },
    webServer: {
        command: 'python app.py',
        url: 'http://127.0.0.1:5100/health/live',
        reuseExistingServer: true,
        timeout: 30_000,
        env: {
            ...process.env,
            FLASK_DEBUG: 'false',
            PORT: '5100',
            FEATURE_SEARCH: 'true',
        },
    },
});
