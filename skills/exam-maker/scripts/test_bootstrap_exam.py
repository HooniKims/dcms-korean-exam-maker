import tempfile
from pathlib import Path
import unittest
import argparse
import json
import plistlib
import shutil
import subprocess
from unittest.mock import patch
import bootstrap_exam as b


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='exam bootstrap ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def exe(self, relative):
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'fixture only; not executable')
        return p

    def test_2020_and_2024_names_and_spaces(self):
        old = self.exe('한컴오피스 2020/HOffice110/Bin/Hwp.exe')
        new = self.exe('한글 2024/HOffice130/Bin/Hwp.exe')
        got = b.scan_hancom([self.root])
        self.assertEqual({x['path'] for x in got}, {str(old), str(new)})
        self.assertEqual(got[0]['path'], str(new))

    def test_com_preferred_over_folder_version(self):
        old = self.exe('2020/Hwp.exe')
        self.exe('2024/Hwp.exe')
        got = b.scan_hancom([self.root], [(f'"{old}" /Automation', 'COM registration')])
        self.assertEqual(got[0]['path'], str(old))

    def test_registry_only_custom_drive(self):
        p = self.exe('Custom Install/한글/Hwp.exe')
        got = b.scan_hancom([], [(f'"{p}",0', 'App Paths')])
        self.assertEqual(got[0]['app'], 'process:' + str(p))

    def test_viewers_and_other_office_apps_excluded(self):
        self.exe('Hnc/HwpViewer/Hwp.exe')
        self.exe('한글 뷰어/Hwp.exe')
        self.exe('Hnc/HCell.exe')
        self.assertEqual(b.scan_hancom([self.root]), [])

    def test_missing_hancom(self):
        self.assertEqual(b.scan_hancom([self.root / 'missing']), [])

    def test_duplicate_paths_collapsed(self):
        p = self.exe('Hnc/Hwp.exe')
        got = b.scan_hancom([self.root, self.root], [(str(p), 'App Paths')])
        self.assertEqual(len(got), 1)
        self.assertIn('App Paths', got[0]['sources'])

    def test_command_extraction(self):
        self.assertEqual(b.exe_from_command('"D:\\Apps\\한글 2020\\Hwp.exe" /Automation'), 'D:\\Apps\\한글 2020\\Hwp.exe')
        self.assertEqual(b.exe_from_command('C:\\Program Files\\Hnc\\Hwp.exe,0'), 'C:\\Program Files\\Hnc\\Hwp.exe')
        self.assertIsNone(b.exe_from_command(None))
        self.assertIsNone(b.exe_from_command('not an executable'))

    def test_minimum_node(self):
        for v in ('v22.12.0', 'v24.13.0'):
            self.assertTrue(b.version_ok('node', v))
        for v in ('v22.0.0', 'v18.19.0', 'error'):
            self.assertFalse(b.version_ok('node', v))

    def test_existing_tools_do_not_install(self):
        calls = []
        got, actions = b.ensure_tools(True, resolver=lambda *a: {'path':'existing'}, runner=lambda *a, **k: calls.append(a))
        self.assertTrue(all(got.values()))
        self.assertEqual(actions, [])
        self.assertEqual(calls, [])

    def test_missing_tools_plan_is_read_only(self):
        calls = []
        got, _ = b.ensure_tools(False, resolver=lambda *a: None, runner=lambda *a, **k: calls.append(a))
        self.assertEqual(calls, [])
        self.assertIsNone(got['node'])

    def test_missing_tool_install_exact_id_and_recheck(self):
        installed, calls = set(), []
        def resolve(name, extra):
            return {'path':name} if name in installed else None
        def runner(args, **kw):
            calls.append(args)
            installed.add('git' if 'Git.Git' in args else 'node')
        with patch.object(b.shutil, 'which', return_value='winget.exe'), patch.object(b, 'refresh_process_path'):
            tools, actions = b.ensure_tools(True, resolver=resolve, runner=runner)
        self.assertEqual(len(actions), 2)
        self.assertTrue(all(tools.values()))
        for call in calls:
            self.assertIn('--source', call)
            self.assertIn('-e', call)
            self.assertNotIn('--ignore-security-hash', call)

    def test_installer_success_without_executable_is_failure(self):
        with patch.object(b.shutil, 'which', return_value='winget.exe'), patch.object(b, 'refresh_process_path'):
            with self.assertRaisesRegex(RuntimeError, 'verification failed'):
                b.ensure_tools(True, resolver=lambda *a:None, runner=lambda *a, **k:'')

    def test_existing_skill_not_overwritten(self):
        for file in b.REQUIRED:
            p = self.root / 'hwpx' / file
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('local custom content', encoding='utf8')
        def forbidden(*a, **kw):
            self.fail('Installer called for existing skill')
        _, action = b.ensure_skill(self.root, self.root/'absent.py', True, runner=forbidden)
        self.assertIn('reused', action)
        self.assertEqual((self.root/'hwpx/SKILL.md').read_text(), 'local custom content')

    def test_partial_existing_skill_preserved(self):
        (self.root/'hwpx').mkdir()
        with self.assertRaisesRegex(RuntimeError, 'preserved'):
            b.ensure_skill(self.root, self.root/'installer.py', True)
        self.assertTrue((self.root/'hwpx').exists())

    def test_skill_install_uses_pinned_helper(self):
        helper = self.root/'installer.py'
        helper.write_text('fixture')
        calls=[]
        def runner(args, **kw):
            calls.append(args)
            for file in b.REQUIRED:
                p=self.root/'hwpx'/file
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text('fixture')
        b.ensure_skill(self.root, helper, True, runner=runner)
        self.assertIn(b.REF, calls[0])
        self.assertIn(helper, calls[0])
        self.assertIn('download', calls[0])

    def test_skill_missing_plan_does_not_create_directory(self):
        _, action=b.ensure_skill(self.root, self.root/'absent', False)
        self.assertEqual(action, 'missing')
        self.assertFalse((self.root/'hwpx').exists())

    def test_build_targets_resolve_inside_skill(self):
        b.check_build_paths(self.root)
        with patch.object(Path,'resolve', side_effect=[self.root, self.root.parent/'outside']):
            with self.assertRaisesRegex(RuntimeError,'Unsafe'):
                b.check_build_paths(self.root)

    def args(self, **overrides):
        values = dict(codex_home=str(self.root), skills_dir=None, installer=None,
                      apply=True, runtime_bin=[], editor=False)
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_native_route_skips_all_editor_and_package_installation(self):
        native = [{'path': 'verified Hwp.exe', 'app': 'native'}]
        with patch.object(b, 'discover_hancom', return_value=native), \
             patch.object(b, 'ensure_tools', side_effect=AssertionError('tool installation')), \
             patch.object(b, 'ensure_skill', side_effect=AssertionError('editor installation')), \
             patch.object(b, 'missing_modules', side_effect=AssertionError('package installation')), \
             patch.object(b, 'run', side_effect=AssertionError('subprocess')):
            report = b.provision(self.args())
        self.assertEqual(report['status'], 'READY')
        self.assertEqual(report['workflow'], 'hancom')
        self.assertEqual(report['actions'], [])
        self.assertFalse(report['editor_required'])
        self.assertEqual(report['editor_smoke']['status'], 'SKIPPED_NATIVE')

    def test_explicit_editor_request_does_not_take_native_shortcut(self):
        with patch.object(b, 'discover_hancom', return_value=[{'path': 'native'}]), \
             patch.object(b, 'ensure_tools', side_effect=RuntimeError('editor route')):
            with self.assertRaisesRegex(RuntimeError, 'editor route'):
                b.provision(self.args(editor=True))

    def bundle(self, name, executable='Hwp', binary=True):
        app = self.root / name
        (app / 'Contents/MacOS').mkdir(parents=True)
        (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable':executable}))
        if binary:
            (app / 'Contents/MacOS' / executable).write_bytes(b'fixture')
        return app

    def test_mac_bundle_requires_editor_executable_not_viewer_or_folder(self):
        app = self.bundle('한컴 한글.app')
        self.bundle('Hancom HwpViewer.app')
        self.bundle('Hancom Hcell.app', 'Hcell')
        self.bundle('Hanword Broken.app', binary=False)
        self.assertEqual([x['app'] for x in b.scan_macos_hancom([self.root])], [str(app)])

    def test_mac_without_hancom_selects_editor_and_stays_read_only(self):
        with patch.object(b.sys, 'platform', 'darwin'), \
             patch.object(b, 'scan_macos_hancom', return_value=[]) as scan, \
             patch.object(b, 'ensure_tools', return_value=({'git':None,'node':None},[])) as tools, \
             patch.object(b, 'missing_modules', return_value=[]):
            report=b.provision(self.args(apply=False))
        scan.assert_called_once()
        tools.assert_called_once_with(False, [])
        self.assertEqual(report['workflow'], 'editor')
        self.assertTrue(report['editor_required'])
        self.assertEqual(report['status'], 'MISSING')
        self.assertFalse((self.root/'skills').exists())

    def test_mac_with_hancom_skips_editor(self):
        app=self.bundle('Hancom Hanword.app')
        native=b.scan_macos_hancom([self.root])
        with patch.object(b.sys,'platform','darwin'), \
             patch.object(b,'scan_macos_hancom',return_value=native), \
             patch.object(b,'ensure_tools',side_effect=AssertionError('unnecessary setup')):
            report=b.provision(self.args())
        self.assertEqual(report['hancom'][0]['app'], str(app))
        self.assertEqual(report['workflow'],'hancom')

    def test_mac_without_hancom_apply_provisions_and_checks_editor(self):
        skill=self.root/'skills/hwpx'
        for name in b.BUILT:
            path=skill/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
        with patch.object(b.sys,'platform','darwin'), \
             patch.object(b,'scan_macos_hancom',return_value=[]), \
             patch.object(b,'ensure_tools',return_value=({'git':{'path':'git'},'node':{'path':'node'}},[])), \
             patch.object(b,'ensure_skill',return_value=(skill,'installed')) as install, \
             patch.object(b,'missing_modules',return_value=[]), \
             patch.object(b,'run',return_value='{"status":"PASS"}') as smoke:
            report=b.provision(self.args())
        self.assertTrue(install.call_args.args[2])
        self.assertTrue(any('check_editor.mjs' in str(x) for x in smoke.call_args.args[0]))
        self.assertEqual(report['workflow'],'editor')
        self.assertEqual(report['status'],'READY')
        self.assertEqual(report['editor_smoke']['status'],'PASS')

    def test_windows_launcher_does_not_require_python_with_hancom(self):
        shell=shutil.which('pwsh') or shutil.which('powershell')
        if not shell:
            self.skipTest('PowerShell is unavailable')
        launcher=Path(b.__file__).with_name('bootstrap_windows.ps1').read_text(encoding='utf8')
        launcher=launcher.replace('function Find-ExamPython {', "function Find-ExamPython { throw 'Python must not be required for native editing'")
        script=self.root/'bootstrap_windows.ps1';script.write_text(launcher,encoding='utf-8-sig')
        (self.root/'find_hancom_windows.ps1').write_text("function Find-ExamNativeHancom { @{path='fixture Hwp.exe';app='fixture';sources=@('fixture')} }",encoding='utf-8-sig')
        output=self.root/'report.json'
        result=subprocess.run([shell,'-NoProfile','-File',str(script),'-Apply','-Report',str(output)],capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        report=json.loads(output.read_text(encoding='utf-8-sig'))
        self.assertEqual(report['workflow'],'hancom')
        self.assertEqual(report['actions'],[])


if __name__ == '__main__':
    unittest.main(verbosity=2)
