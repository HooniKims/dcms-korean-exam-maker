"""Prefer installed Hancom; only provision the editor when Hancom is absent.

Uses Codex's skill-installer for the pinned public HWPX editor skill. Never
overwrites an existing skill, launches Hancom, or changes the system PATH.
"""
from __future__ import annotations
import argparse
import json
import os
import plistlib
from pathlib import Path
import re
import shutil
import subprocess
import sys

REPO = 'imsebeom/hwpx'
REF = 'abea249f05f4982a40bc56adf765ea5d32538c82'
REQUIRED = ('SKILL.md', 'editor/cli.mjs', 'editor/setup.mjs', 'editor/blank.hwpx',
            'scripts/validate.py', 'scripts/verify_hwpx.py')
BUILT = ('editor/studio-dist/index.html', 'editor/studio-dist/node/rhwp.js',
         'editor/studio-dist/node/rhwp_bg.wasm', 'editor/sdk/index.js')
MODULES = {'lxml': 'lxml', 'hwpx': 'python-hwpx', 'fitz': 'PyMuPDF', 'PIL': 'Pillow'}
PACKAGES = {'git': 'Git.Git', 'node': 'OpenJS.NodeJS.LTS'}


def run(args, *, env=None, timeout=120, cwd=None):
    result = subprocess.run([str(a) for a in args], env=env, cwd=cwd, timeout=timeout,
                            capture_output=True, text=True, encoding='utf8', errors='replace')
    if result.returncode:
        raise RuntimeError(f'{Path(args[0]).name} failed ({result.returncode}): '
                           + (result.stdout + result.stderr)[-5000:])
    return result.stdout.strip()


def version_ok(name, value):
    match = re.search(r'(\d+)\.(\d+)', value)
    if not match:
        return False
    major, minor = map(int, match.groups())
    return name != 'node' or (major, minor) >= (22, 12)


def tool_candidates(name, extra=()):
    found = shutil.which(name)
    if found:
        yield Path(found)
    suffix = '.exe' if os.name == 'nt' else ''
    for folder in extra:
        yield Path(folder) / (name + suffix)
    if os.name == 'nt':
        for base in (os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)'),
                     str(Path.home() / 'AppData/Local/Programs')):
            if base:
                yield Path(base) / {'git': 'Git/cmd/git.exe', 'node': 'nodejs/node.exe'}[name]


def find_tool(name, extra=()):
    for candidate in dict.fromkeys(tool_candidates(name, extra)):
        if candidate.is_file():
            try:
                version = run([candidate, '--version'], timeout=15)
                if version_ok(name, version):
                    result = {'path': str(candidate.resolve()), 'version': version}
                    if name == 'node':
                        base = candidate.resolve().parent
                        npm_options = [base / 'node_modules/npm/bin/npm-cli.js',
                                       base.parent / 'lib/node_modules/npm/bin/npm-cli.js']
                        npm_cmd = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
                        if npm_cmd:
                            npm_options.append(Path(npm_cmd).resolve() if os.name != 'nt' else
                                               Path(npm_cmd).parent / 'node_modules/npm/bin/npm-cli.js')
                        npm_js = next((p for p in npm_options if p.is_file()), None)
                        if npm_js is None:
                            continue
                        result['npm_version'] = run([candidate, npm_js, '--version'], timeout=15)
                    return result
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                pass
    return None


def ensure_tools(apply, extra=(), resolver=find_tool, runner=run):
    result, actions = {}, []
    for name, package in PACKAGES.items():
        tool = resolver(name, extra)
        if not tool and apply:
            winget = shutil.which('winget') if os.name == 'nt' else None
            if not winget:
                raise RuntimeError(f'{name} missing; no Windows winget available. '
                                   'Use the bundled runtime or the official platform installer.')
            print(f'{name} is required. Installing {package} from winget.', flush=True)
            runner([winget, 'install', '--id', package, '-e', '--source', 'winget',
                    '--silent', '--accept-package-agreements', '--accept-source-agreements',
                    '--disable-interactivity', '--no-upgrade'], timeout=1200)
            # Installers update persistent PATH, not this process. Read it back
            # locally only; never overwrite machine/user environment settings.
            if os.name == 'nt':
                refresh_process_path()
            tool = resolver(name, extra)
            if not tool:
                raise RuntimeError(f'{name} installation returned but executable verification failed')
            actions.append('installed ' + package)
        result[name] = tool
    return result, actions


def check_build_paths(skill):
    # setup.mjs replaces these generated directories. Resolve each first so a
    # junction/symlink cannot redirect recursive removal outside this skill.
    root = skill.resolve()
    for rel in ('editor/.build', 'editor/.build/rhwp/rhwp-studio/dist', 'editor/studio-dist'):
        target = (skill / rel).resolve()
        if target == root or root not in target.parents:
            raise RuntimeError('Unsafe editor build target: ' + str(target))


def prepare_editor_source(skill, git, env):
    source = skill / 'editor/.build/rhwp'
    cargo = Path.home() / '.cargo/bin'
    suffix = '.exe' if os.name == 'nt' else ''
    rust = all((cargo / (name + suffix)).exists() for name in ('cargo', 'wasm-pack'))
    if source.exists() or rust:
        return
    setup = (skill / 'editor/setup.mjs').read_text(encoding='utf8')
    match = re.search(r"const RHWP_VERSION = '([0-9]+\.[0-9]+\.[0-9]+)'", setup)
    if not match:
        return  # Unknown upstream setup: let its own version logic run.
    source.parent.mkdir(parents=True, exist_ok=True)
    run([git, 'clone', '--depth', '1', '--filter=blob:none', '--sparse',
         '--branch', 'v' + match[1], 'https://github.com/edwardkim/rhwp.git', source],
        env=env, timeout=600)
    # Prebuilt-WASM path needs only the browser studio and JS SDK, not the
    # repository's multi-gigabyte PDF/HWP regression corpus.
    run([git, '-C', source, 'sparse-checkout', 'set', 'rhwp-studio', 'npm'], env=env, timeout=600)


def registry_values(root, path, view=0):
    import winreg
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | view) as key:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                except OSError:
                    break
                yield name, value
                i += 1
    except OSError:
        return


def refresh_process_path():
    import winreg
    for root, key in ((winreg.HKEY_CURRENT_USER, 'Environment'),
                      (winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')):
        for name, value in registry_values(root, key):
            if name.lower() == 'path' and isinstance(value, str):
                os.environ['PATH'] += os.pathsep + os.path.expandvars(value)


def exe_from_command(value):
    if not isinstance(value, str):
        return None
    match = re.search(r'^\s*"([^"]+\.exe)"|^\s*(.*?\.exe)(?=\s|,|$)', value, re.I)
    return os.path.expandvars(next(x for x in match.groups() if x)) if match else None


def scan_hancom(roots, records=()):
    """Read only; fixture roots make version/name/space-path behavior testable."""
    found = {}
    def add(path, source):
        p = Path(path)
        if p.name.lower() != 'hwp.exe' or not p.is_file():
            return
        if any('viewer' in part.lower() or '뷰어' in part for part in p.parts):
            return
        key = str(p.resolve())
        found.setdefault(key, {'path': key, 'sources': [], 'app': 'process:' + key})['sources'].append(source)
    for value, source in records:
        exe = exe_from_command(value)
        if exe:
            add(exe, source)
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for folder, dirs, files in os.walk(root, followlinks=False):
            depth = len(Path(folder).relative_to(root).parts)
            dirs[:] = [d for d in dirs if depth < 7 and not Path(folder, d).is_symlink()
                       and 'viewer' not in d.lower() and '뷰어' not in d]
            for name in files:
                if name.lower() == 'hwp.exe':
                    add(Path(folder, name), 'installation scan')
    def rank(item):
        # HOffice major versions sort naturally, not lexicographically.
        nums = tuple(map(int, re.findall(r'\d+', item['path'])))
        return (any('COM' in s for s in item['sources']), nums)
    return sorted(found.values(), key=rank, reverse=True)


def scan_macos_hancom(roots):
    """Recognize installed editor bundles, not viewers or name-only folders."""
    found = {}
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for bundle in root.glob('*.app'):
            if not re.search(r'hancom|hanword|hwp|한글|한컴', bundle.name, re.I):
                continue
            if re.search(r'viewer|뷰어', bundle.name, re.I):
                continue
            try:
                info = plistlib.loads((bundle / 'Contents/Info.plist').read_bytes())
                executable = info['CFBundleExecutable']
                if not isinstance(executable, str) or Path(executable).name != executable:
                    continue
                binary = bundle / 'Contents/MacOS' / executable
                if not binary.is_file():
                    continue
                # Office suites/other Hancom apps are not proof of Hanword.
                identity = ' '.join([bundle.name, executable, str(info.get('CFBundleIdentifier', ''))])
                if not re.search(r'hanword|hwp|한글', identity, re.I):
                    continue
                key = str(bundle.resolve())
                found[key] = {'path': str(binary.resolve()), 'app': key,
                              'sources': ['macOS application bundle']}
            except (OSError, ValueError, KeyError, plistlib.InvalidFileException):
                continue
    return list(found.values())


def discover_hancom():
    if sys.platform == 'darwin':
        return scan_macos_hancom([Path('/Applications'), Path.home() / 'Applications'])
    if os.name != 'nt':
        return []
    import winreg
    records, roots = [], []
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            for _, value in registry_values(root, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Hwp.exe', view):
                records.append((value, 'App Paths'))
            uninstall = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
            try:
                with winreg.OpenKey(root, uninstall, 0, winreg.KEY_READ | view) as key:
                    names = [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]
            except OSError:
                names = []
            for name in names:
                values = dict(registry_values(root, uninstall + '\\' + name, view))
                if re.search(r'hancom|hangeul|hanword|한컴|한글', str(values.get('DisplayName', '')), re.I):
                    records.append((values.get('DisplayIcon', ''), 'installed product'))
                    location = values.get('InstallLocation')
                    if location and Path(location).is_dir() and len(Path(location).parts) >= 3:
                        roots.append(location)
            for progid in ('HWPFrame.HwpObject', 'HWPFrame.HwpObject.1'):
                cls = dict(registry_values(root, 'SOFTWARE\\Classes\\' + progid + '\\CLSID', view)).get('')
                if cls:
                    command = dict(registry_values(root, 'SOFTWARE\\Classes\\CLSID\\' + cls + '\\LocalServer32', view)).get('')
                    records.append((command, 'COM registration'))
    for base in (os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)'),
                 str(Path.home() / 'AppData/Local/Programs')):
        if base and Path(base).is_dir():
            roots.extend(p for p in Path(base).iterdir() if p.is_dir() and
                         re.search(r'hnc|hancom|hangeul|hanword|한글|한컴', p.name, re.I))
    return scan_hancom(dict.fromkeys(roots), records)


def ensure_skill(dest, installer, apply, runner=run):
    skill = dest / 'hwpx'
    if skill.exists():
        missing = [x for x in REQUIRED if not (skill / x).is_file()]
        if missing:
            raise RuntimeError('Existing hwpx skill preserved; required files missing: ' + ', '.join(missing))
        return skill, 'reused existing skill (no pull or overwrite)'
    if not apply:
        return skill, 'missing'
    if not installer.is_file():
        raise RuntimeError('Codex skill-installer helper not found: ' + str(installer))
    print(f'Installing HWPX editor skill: https://github.com/{REPO} @ {REF}', flush=True)
    runner([sys.executable, '-X', 'utf8', installer, '--repo', REPO, '--ref', REF,
            '--path', '.', '--name', 'hwpx', '--dest', dest, '--method', 'download'], timeout=600)
    if not all((skill / x).is_file() for x in REQUIRED):
        raise RuntimeError('Installed skill is incomplete; retained for diagnosis')
    return skill, 'installed pinned skill; available in Codex on the next turn'


def missing_modules(python):
    script = 'import importlib.util,json;print(json.dumps([x for x in '+repr(list(MODULES))+' if importlib.util.find_spec(x) is None]))'
    return json.loads(run([python, '-c', script]))


def provision(args):
    home = Path(args.codex_home).expanduser().resolve()
    dest = Path(args.skills_dir).expanduser().resolve() if args.skills_dir else home / 'skills'
    installer = Path(args.installer).resolve() if args.installer else home / 'skills/.system/skill-installer/scripts/install-skill-from-github.py'
    report = {'status': 'CHECKING', 'apply': args.apply, 'actions': [], 'hancom': discover_hancom()}
    # Native editing does not depend on rhwp, Git, Node, or Python document
    # packages. An incomplete pre-existing editor must not block this route.
    if report['hancom'] and not getattr(args, 'editor', False):
        report.update(status='READY', workflow='hancom', editor_required=False,
                      editor_smoke={'status': 'SKIPPED_NATIVE'},
                      native_layout_status='AVAILABLE_NOT_YET_VERIFIED',
                      computer_use_status='CHECK_IN_AGENT',
                      python=str(Path(sys.executable)))
        return report
    report.update(workflow='editor', editor_required=True)
    tools, actions = ensure_tools(args.apply, args.runtime_bin)
    report.update(tools=tools)
    report['actions'].extend(actions)
    skill, action = ensure_skill(dest, installer, args.apply)
    report.update(skill=str(skill), skill_action=action, source={'repo': REPO, 'ref': REF})
    env = os.environ.copy()
    env['PATH'] = os.pathsep.join(str(Path(t['path']).parent) for t in tools.values() if t) + os.pathsep + env.get('PATH', '')
    # Upstream LFS is only pdf-large/**/*.pdf (test corpora, not editor assets).
    # Do not download large unrelated regression PDFs during editor setup.
    env['GIT_LFS_SKIP_SMUDGE'] = '1'
    python = Path(sys.executable)
    missing = missing_modules(python)
    if missing and args.apply:
        venv = home / 'cache/exam-maker/python'
        python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if not python.exists():
            print('Installing isolated Python document dependencies.', flush=True)
            run([sys.executable, '-m', 'venv', '--system-site-packages', venv])
        missing = missing_modules(python)
        if missing:
            run([python, '-m', 'pip', 'install', '--disable-pip-version-check',
                 '--index-url', 'https://pypi.org/simple', *[MODULES[x] for x in missing]], timeout=900)
            report['actions'].append('installed missing Python document modules in isolated venv')
        missing = missing_modules(python)
    report.update(python=str(python), missing_python_modules=missing)
    built = all((skill / x).is_file() for x in BUILT)
    if args.apply and not built and all(tools.values()):
        check_build_paths(skill)
        print('Building the HWPX editor once (Git + Node.js/npm); may take several minutes.', flush=True)
        prepare_editor_source(skill, tools['git']['path'], env)
        log = run([tools['node']['path'], skill / 'editor/setup.mjs'], env=env, timeout=1800)
        log_path = home / 'cache/exam-maker/editor-setup.log'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(log, encoding='utf8')
        report['actions'].append('built HWPX editor')
        built = all((skill / x).is_file() for x in BUILT)
    report['editor_built'] = built
    if built and tools['node']:
        smoke = Path(__file__).with_name('check_editor.mjs')
        report['editor_smoke'] = json.loads(run([tools['node']['path'], smoke, skill], env=env))
    report['native_layout_status'] = 'AVAILABLE_NOT_YET_VERIFIED' if report['hancom'] else 'NOT_AVAILABLE'
    report['status'] = 'READY' if (all(tools.values()) and action != 'missing' and built
                                  and not missing and report.get('editor_smoke', {}).get('status') == 'PASS') else 'MISSING'
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--editor', action='store_true', help='Explicitly requested editor even if Hancom is installed')
    p.add_argument('--codex-home', default=os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    p.add_argument('--skills-dir', help='Isolated install destination for testing')
    p.add_argument('--installer', help='Actual Codex skill-installer helper path')
    p.add_argument('--runtime-bin', action='append', default=[])
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    try:
        result = provision(args)
    except Exception as exc:
        result = {'status': 'ERROR', 'error': str(exc), 'apply': args.apply}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'READY' else 1


if __name__ == '__main__':
    raise SystemExit(main())
