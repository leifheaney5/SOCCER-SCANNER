"""Tests for the App Store screenshot simulator selector."""

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SELECTOR_PATH = ROOT / 'clients' / 'ios' / 'Tools' / 'select_screenshot_simulator.py'
IPHONE_11_PRO_MAX = 'com.apple.CoreSimulator.SimDeviceType.iPhone-11-Pro-Max'
IPHONE_14_PLUS = 'com.apple.CoreSimulator.SimDeviceType.iPhone-14-Plus'
IPAD_PRO_13_M4 = 'com.apple.CoreSimulator.SimDeviceType.iPad-Pro-13-inch-M4-8GB'


def selector_module():
    assert SELECTOR_PATH.is_file(), 'the screenshot simulator selector is missing'
    spec = importlib.util.spec_from_file_location('select_screenshot_simulator', SELECTOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DEVICE_TYPES = [
    {'name': 'iPhone 11 Pro Max', 'identifier': IPHONE_11_PRO_MAX},
    {'name': 'iPhone 14 Plus', 'identifier': IPHONE_14_PLUS},
    {'name': 'iPad Pro 13-inch (M4)', 'identifier': IPAD_PRO_13_M4},
]


def runtime(version, supported, available=True, platform='iOS'):
    return {
        'identifier': f'com.apple.CoreSimulator.SimRuntime.{platform}-{version.replace(".", "-")}',
        'version': version,
        'isAvailable': available,
        'supportedDeviceTypes': [{'identifier': item} for item in supported],
    }


def test_prefers_first_candidate_on_newest_supporting_ios_runtime():
    runtimes = [
        runtime('18.6', [IPHONE_11_PRO_MAX, IPHONE_14_PLUS]),
        runtime('26.0', [IPHONE_11_PRO_MAX, IPHONE_14_PLUS]),
        runtime('26.1', [IPHONE_11_PRO_MAX], platform='watchOS'),
    ]

    chosen = selector_module().choose(DEVICE_TYPES, runtimes, ['iPhone 11 Pro Max', 'iPhone 14 Plus'])

    assert chosen == (IPHONE_11_PRO_MAX, 'com.apple.CoreSimulator.SimRuntime.iOS-26-0', 'iPhone 11 Pro Max')


def test_falls_back_when_newest_runtime_drops_the_preferred_device():
    runtimes = [
        runtime('27.0', [IPHONE_14_PLUS]),
        runtime('18.6', [IPHONE_11_PRO_MAX, IPHONE_14_PLUS], available=False),
    ]

    chosen = selector_module().choose(DEVICE_TYPES, runtimes, ['iPhone 11 Pro Max', 'iPhone 14 Plus'])

    assert chosen == (IPHONE_14_PLUS, 'com.apple.CoreSimulator.SimRuntime.iOS-27-0', 'iPhone 14 Plus')


def test_reports_when_no_candidate_is_available():
    with pytest.raises(ValueError, match='no available simulator'):
        selector_module().choose(DEVICE_TYPES, [runtime('26.0', [IPAD_PRO_13_M4])], ['iPhone 11 Pro Max'])
