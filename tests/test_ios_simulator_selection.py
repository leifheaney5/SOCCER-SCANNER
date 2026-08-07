"""Tests for the dependency-free iOS CI simulator selector."""

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SELECTOR_PATH = ROOT / 'clients' / 'ios' / 'Tools' / 'select_simulator.py'


def selector_module():
    assert SELECTOR_PATH.is_file(), 'the CI simulator selector is missing'
    spec = importlib.util.spec_from_file_location('select_simulator', SELECTOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_selects_the_newest_numeric_ios_runtime_and_shortest_iphone_name():
    payload = {
        'devices': {
            'com.apple.CoreSimulator.SimRuntime.iOS-9-0': [
                {'isAvailable': True, 'name': 'iPhone 17', 'udid': 'old'},
            ],
            'com.apple.CoreSimulator.SimRuntime.iOS-18-6': [
                {'isAvailable': True, 'name': 'iPhone 17 Pro Max', 'udid': 'long'},
                {'isAvailable': True, 'name': 'iPhone 17', 'udid': 'new'},
            ],
        },
    }

    assert selector_module().select_simulator(payload) == (
        'new',
        'iPhone 17',
        'com.apple.CoreSimulator.SimRuntime.iOS-18-6',
    )


def test_selector_rejects_payloads_without_an_available_iphone():
    selector = selector_module()
    with pytest.raises(ValueError, match='no available iPhone simulator'):
        selector.select_simulator({'devices': {}})
