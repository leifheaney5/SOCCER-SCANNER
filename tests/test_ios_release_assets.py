"""Validate release-critical native assets without requiring Xcode."""

import json
from pathlib import Path
import struct
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
IOS_ROOT = ROOT / 'clients' / 'ios'


def _plist_value(path, key):
    root = ElementTree.parse(path).getroot()
    dictionary = root.find('dict')
    assert dictionary is not None
    children = list(dictionary)
    for index, child in enumerate(children[:-1]):
        if child.tag == 'key' and child.text == key:
            value = children[index + 1]
            if value.tag in {'true', 'false'}:
                return value.tag == 'true'
            return value.text if value.tag == 'string' else value
    raise AssertionError(f'missing plist key: {key}')


def test_native_info_plist_matches_release_contract():
    path = IOS_ROOT / 'SoccerScanner' / 'Info.plist'

    assert _plist_value(path, 'CFBundleDisplayName') == 'Soccer Scanner'
    assert _plist_value(path, 'CFBundleShortVersionString') == '1.0.0'
    assert _plist_value(path, 'CFBundleVersion') == '1'
    assert _plist_value(path, 'ITSAppUsesNonExemptEncryption') is False
    orientations = _plist_value(path, 'UISupportedInterfaceOrientations')
    assert {item.text for item in orientations} >= {
        'UIInterfaceOrientationPortrait',
        'UIInterfaceOrientationLandscapeLeft',
        'UIInterfaceOrientationLandscapeRight',
    }


def test_native_project_and_entitlements_expose_only_verified_defaults():
    project = (IOS_ROOT / 'project.yml').read_text(encoding='utf-8')
    entitlements = (IOS_ROOT / 'SoccerScanner' / 'SoccerScanner.entitlements').read_text(
        encoding='utf-8'
    )

    assert 'iOS: "17.0"' in project
    assert 'IPHONEOS_DEPLOYMENT_TARGET: "17.0"' in project
    assert 'PRODUCT_BUNDLE_IDENTIFIER: pro.soccerscanner.app' in project
    assert 'ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon' in project
    assert 'APPLE_TEAM_ID' not in entitlements
    assert '<string>applinks:soccerscanner.pro</string>' in entitlements


def test_generated_xcode_artifacts_are_ignored():
    gitignore = (ROOT / '.gitignore').read_text(encoding='utf-8')

    assert 'clients/ios/*.xcodeproj/' in gitignore
    assert 'clients/ios/*.xcworkspace/' in gitignore
    assert '**/*.xcuserstate' in gitignore


def test_observable_app_container_imports_observation_module():
    source = (IOS_ROOT / 'SoccerScanner' / 'App' / 'SoccerScannerApp.swift').read_text(
        encoding='utf-8'
    )

    assert 'import Observation' in source
    assert '@Observable' in source


def test_fixture_detail_uses_shared_spoiler_binding():
    detail = (IOS_ROOT / 'SoccerScanner' / 'Features' / 'FixtureDetail' / 'FixtureDetailView.swift').read_text(
        encoding='utf-8'
    )
    list_view = (IOS_ROOT / 'SoccerScanner' / 'Features' / 'Fixtures' / 'FixtureListView.swift').read_text(
        encoding='utf-8'
    )

    assert '@Binding private var scoresRevealed: Bool' in detail
    assert 'detail-score-toggle' in detail
    assert 'scoresRevealed: Binding(' in list_view


def test_native_state_fixtures_and_broadcast_detail_wiring_are_present():
    app = (IOS_ROOT / 'SoccerScanner' / 'App' / 'SoccerScannerApp.swift').read_text(
        encoding='utf-8'
    )
    preview = (IOS_ROOT / 'SoccerScanner' / 'Support' / 'PreviewSupport.swift').read_text(
        encoding='utf-8'
    )
    detail = (IOS_ROOT / 'SoccerScanner' / 'Features' / 'FixtureDetail' / 'FixtureDetailView.swift').read_text(
        encoding='utf-8'
    )
    ui_tests = (IOS_ROOT / 'SoccerScannerUITests' / 'FixtureFlowUITests.swift').read_text(
        encoding='utf-8'
    )

    for flag in ('UITestPartial', 'UITestStale', 'UITestEmpty'):
        assert flag in app
        assert flag in ui_tests
    assert 'case stale' in preview
    assert 'ForEach(Array(fixture.broadcasts.enumerated())' in detail
    assert 'broadcast.categoryLabel' in detail
    assert 'app.open(URL(string:' in ui_tests
    assert '-UIAccessibilityDifferentiateWithoutColorEnabled' in ui_tests


def test_native_icon_privacy_and_release_lane_assets_are_present():
    asset_catalog = IOS_ROOT / 'SoccerScanner' / 'Resources' / 'Assets.xcassets'
    icon_set = asset_catalog / 'AppIcon.appiconset'
    icon_contents = json.loads((icon_set / 'Contents.json').read_text(encoding='utf-8'))
    images = icon_contents.get('images') or []
    assert images
    for image in images:
        filename = image.get('filename')
        assert filename
        image_path = icon_set / filename
        payload = image_path.read_bytes()
        assert payload.startswith(b'\x89PNG\r\n\x1a\n')
        width, height = struct.unpack('>II', payload[16:24])
        assert (width, height) == (1024, 1024)

    privacy = ElementTree.parse(IOS_ROOT / 'SoccerScanner' / 'PrivacyInfo.xcprivacy').getroot()
    privacy_dictionary = privacy.find('dict')
    assert privacy_dictionary is not None
    privacy_keys = {
        item.text for item in privacy_dictionary.findall('key')
    }
    assert {'NSPrivacyTracking', 'NSPrivacyCollectedDataTypes'} <= privacy_keys

    fastfile = (IOS_ROOT / 'fastlane' / 'Fastfile').read_text(encoding='utf-8')
    assert 'xcodegen generate --spec project.yml' in fastfile

    workflow = (ROOT / '.github' / 'workflows' / 'ios.yml').read_text(encoding='utf-8')
    assert "      - 'tests/test_ios_release_assets.py'" in workflow
    assert "      - 'templates/terms.html'" in workflow
    assert 'tee build/xcodebuild.log' in workflow
    assert 'xcpretty' not in workflow
    assert "runpy.run_path('Tools/select_simulator.py')" in workflow
    assert 'runtime.rsplit' not in workflow
    assert 'permissions:\n  contents: read' in workflow
    assert 'timeout-minutes: 30' in workflow
    assert 'timeout-minutes: 45' in workflow


def test_native_testflight_metadata_templates_are_present_and_nonempty():
    metadata = IOS_ROOT / 'fastlane' / 'metadata' / 'en-US'
    required_templates = (
        'name.txt',
        'subtitle.txt',
        'description.txt',
        'keywords.txt',
        'primary_category.txt',
        'marketing_url.txt',
        'privacy_url.txt',
        'terms_of_service_url.txt',
        'release_notes.txt',
        'beta_notes.txt',
    )
    for filename in required_templates:
        content = (metadata / filename).read_text(encoding='utf-8').strip()
        assert content


def test_beta_lane_wires_canonical_testflight_changelog():
    fastfile = (IOS_ROOT / 'fastlane' / 'Fastfile').read_text(encoding='utf-8')

    assert 'File.expand_path("metadata/en-US/beta_notes.txt", __dir__)' in fastfile
    assert 'changelog: File.read(beta_notes_path)' in fastfile


def test_submission_lanes_have_a_legal_and_support_preflight():
    fastfile = (IOS_ROOT / 'fastlane' / 'Fastfile').read_text(encoding='utf-8')

    assert 'def release_preflight!' in fastfile
    assert fastfile.count('release_preflight!') >= 3
    assert 'templates/terms.html' in fastfile
    assert '[TO BE COMPLETED BY LEGAL OWNER]' in fastfile
    assert 'metadata/en-US/support_url.txt' in fastfile
    assert 'support_url.txt must contain one verified HTTPS URL' in fastfile
    assert 'python3 ../../tests/test_ios_release_assets.py' in fastfile


def test_archive_lane_has_an_explicit_runtime_signing_contract():
    fastfile = (IOS_ROOT / 'fastlane' / 'Fastfile').read_text(encoding='utf-8')

    assert 'def release_signing_xcargs' in fastfile
    assert 'APPLE_TEAM_ID' in fastfile
    assert 'APPLE_BUNDLE_ID' in fastfile
    assert 'BUILD_NUMBER' in fastfile
    assert 'CODE_SIGN_STYLE=Automatic' in fastfile
    assert '-allowProvisioningUpdates' in fastfile
    assert 'signingStyle: "automatic"' in fastfile
    assert 'xcargs: \'CODE_SIGNING_ALLOWED=NO CODE_SIGN_IDENTITY=""\'' in fastfile
    assert 'lane :preflight' in fastfile
    assert 'def asset_preflight!' in fastfile


def test_submission_lanes_leave_screenshots_portal_managed():
    fastfile = (IOS_ROOT / 'fastlane' / 'Fastfile').read_text(encoding='utf-8')

    assert fastfile.count('skip_screenshots: true') >= 2


def test_upload_lanes_validate_app_store_credentials_before_building():
    fastfile = (IOS_ROOT / 'fastlane' / 'Fastfile').read_text(encoding='utf-8')

    assert 'key = api_key\n    build' in fastfile
    assert fastfile.count('api_key: key') >= 3


if __name__ == '__main__':
    test_native_info_plist_matches_release_contract()
    test_native_project_and_entitlements_expose_only_verified_defaults()
    test_observable_app_container_imports_observation_module()
    test_fixture_detail_uses_shared_spoiler_binding()
    test_native_state_fixtures_and_broadcast_detail_wiring_are_present()
    test_native_icon_privacy_and_release_lane_assets_are_present()
    test_native_testflight_metadata_templates_are_present_and_nonempty()
    test_beta_lane_wires_canonical_testflight_changelog()
    test_submission_lanes_have_a_legal_and_support_preflight()
    print('iOS release assets validated')
