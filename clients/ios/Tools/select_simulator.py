"""Select a deterministic available iPhone from simctl JSON output."""

import json
import re
import sys


_IOS_RUNTIME = re.compile(r'\biOS-(\d+)-(\d+)(?:-(\d+))?\b')


def _runtime_version(runtime):
    match = _IOS_RUNTIME.search(runtime)
    if match is None:
        return None
    return tuple(int(value or 0) for value in match.groups())


def select_simulator(payload):
    """Return ``(udid, name, runtime)`` for the preferred available iPhone."""
    candidates = []
    devices_by_runtime = payload.get('devices') or {}
    for runtime, devices in devices_by_runtime.items():
        version = _runtime_version(runtime)
        if version is None:
            continue
        for device in devices or []:
            name = str(device.get('name') or '')
            udid = device.get('udid')
            if device.get('isAvailable') and name.startswith('iPhone') and udid:
                candidates.append((version, -len(name), name, str(udid), runtime))

    if not candidates:
        raise ValueError('no available iPhone simulator')

    version, _, name, udid, runtime = max(candidates)
    return udid, name, runtime


def main():
    udid, name, runtime = select_simulator(json.load(sys.stdin))
    print(udid)
    print(f'selected {name} on {runtime}', file=sys.stderr)


if __name__ == '__main__':
    main()
