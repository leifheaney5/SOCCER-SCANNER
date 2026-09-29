import os
import subprocess
from pathlib import Path


root = Path(__file__).resolve().parents[1]
license_text = (root / 'LICENSE').read_text(encoding='utf-8')
holder = os.environ.get('LICENSE_HOLDER', '').strip()
if not holder:
    raise SystemExit('Set LICENSE_HOLDER to the exact copyright-holder name.')
if holder not in license_text:
    raise SystemExit('The LICENSE does not name LICENSE_HOLDER exactly.')
if 'proprietary' not in license_text.casefold():
    raise SystemExit('The root LICENSE must state that the project is proprietary.')
if 'all rights reserved' not in license_text.casefold():
    raise SystemExit('The root LICENSE must reserve all rights.')
if 'no license is granted' not in license_text.casefold():
    raise SystemExit('The root LICENSE must state that no license is granted.')

font_license_path = root / 'clients/ios/Tools/fonts/OFL.txt'
font_license = font_license_path.read_text(encoding='utf-8')
if 'SIL OPEN FONT LICENSE Version 1.1' not in font_license:
    raise SystemExit('The Orbitron SIL Open Font License notice is missing.')
if not (root / 'clients/ios/Tools/fonts/Orbitron-Variable.ttf').is_file():
    raise SystemExit('The licensed Orbitron font asset is missing.')
original_font_license = subprocess.run(
    ['git', 'show', 'HEAD:clients/ios/Tools/fonts/OFL.txt'],
    check=True,
    capture_output=True,
).stdout
if font_license_path.read_bytes() != original_font_license:
    raise SystemExit('The Orbitron SIL Open Font License file was changed.')

print(f'Root proprietary license names holder: {holder}')
print('Orbitron font and SIL Open Font License 1.1 notice are present.')
