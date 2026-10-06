import tempfile
from pathlib import Path
import unittest
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
