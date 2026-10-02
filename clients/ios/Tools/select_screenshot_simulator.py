"""Pick an App Store screenshot simulator: device type plus newest supporting iOS runtime."""

import json
import subprocess
import sys


def _version(runtime):
    return tuple(int(part) for part in str(runtime.get('version', '0')).split('.') if part.isdigit())


def choose(device_types, runtimes, candidates):
    """Return ``(device_type_id, runtime_id, name)`` for the first candidate name a runtime supports."""
    ios_runtimes = sorted(
        (
            runtime for runtime in runtimes
            if runtime.get('isAvailable')
            and str(runtime.get('identifier', '')).startswith('com.apple.CoreSimulator.SimRuntime.iOS')
        ),
        key=_version,
        reverse=True,
    )
    for name in candidates:
        device_type = next((item for item in device_types if item.get('name') == name), None)
        if device_type is None:
            continue
        for runtime in ios_runtimes:
            supported = {item.get('identifier') for item in runtime.get('supportedDeviceTypes', [])}
            if device_type['identifier'] in supported:
                return device_type['identifier'], runtime['identifier'], name
    raise ValueError('no available simulator for: ' + ', '.join(candidates))


def _simctl(kind):
    output = subprocess.check_output(['xcrun', 'simctl', 'list', kind, '-j'])
    return json.loads(output)[kind]


def main(argv):
    candidates = [name for name in argv[1].split('|') if name]
    device_type, runtime, name = choose(_simctl('devicetypes'), _simctl('runtimes'), candidates)
    sys.stderr.write(f'selected {name} on {runtime}\n')
    print(f'{device_type}\t{runtime}\t{name}')


if __name__ == '__main__':
    main(sys.argv)
