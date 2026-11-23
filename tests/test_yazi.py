"""Yazi fixtures: simulated downloads/APT and real zsh, never an installer."""

import shutil
from pathlib import Path

from test_regressions import Fixture, REPO


class YaziInstallTests(Fixture):
    def setUp(self):
        super().setUp()
        self.env['TEST_LOG'] = str(self.root / 'calls')
        self.script(self.bin / 'dpkg', 'printf "%s\\n" "${TEST_ARCH:-amd64}"\n')
        self.script(self.bin / 'curl', '''
printf 'download %s\\n' "$*" >> "$TEST_LOG"
[ "${TEST_DOWNLOAD_FAIL:-0}" = 0 ] || exit 22
while [ "$1" != -o ]; do shift; done
printf 'fixture package' > "$2"
''')
        self.script(self.bin / 'sha256sum', '''
[ "$*" = '--check --status' ] || exit 97
IFS= read -r line
printf 'verify %s\\n' "$line" >> "$TEST_LOG"
exit "${TEST_CHECKSUM_FAIL:-0}"
''')
        self.script(self.bin / 'sudo', '''
[ "$#" = 5 ] && [ "$1 $2 $3 $4" = 'apt-get install -y --no-install-recommends' ] || exit 97
[ -r "$5" ] || exit 97
printf 'install %s\\n' "$5" >> "$TEST_LOG"
stat -c '%a' "$5" >> "$TEST_LOG"
exit "${TEST_APT_FAIL:-0}"
''')
        for name in ('yazi', 'ya'):
            self.script(self.bin / name,
                        '[ "$*" = --version ] || exit 97\nprintf "version\\n" >> "$TEST_LOG"\n')

    def install(self, **kwargs):
        return self.bash('source "$1"; source "$2"; install_yazi',
                         REPO / 'infra/lib/common.sh', REPO / 'infra/lib/yazi.sh', **kwargs)

    def test_source_has_no_side_effects(self):
        self.bash('source "$1"', REPO / 'infra/lib/yazi.sh')
        self.assertFalse((self.root / 'calls').exists())

    def test_both_architectures_and_reruns_verify_before_apt(self):
        for arch, target, digest in (
            ('amd64', 'x86_64', '331d6247c0a0fd549f14cd599a928a529b8b22eded1bb1f61a518376c7621b45'),
            ('arm64', 'aarch64', '0384a3b7c28ad6aa05ac1bb434dd4e7594051b6be4a1b07d43ca19a86826a315'),
        ):
            with self.subTest(arch=arch):
                log = self.root / 'calls'
                log.unlink(missing_ok=True)
                for _ in range(2):
                    self.install(env={**self.env, 'TEST_ARCH': arch})
                    self.assertEqual(list(self.root.glob('tmp.*')), [])
                lines = log.read_text().splitlines()
                package = f'yazi-{target}-unknown-linux-gnu.deb'
                for offset in (0, 6):
                    self.assertTrue(lines[offset].endswith('/v26.9.1/' + package))
                    self.assertEqual(lines[offset + 1], f'verify {digest}  {package}')
                    self.assertTrue(lines[offset + 2].startswith('install '))
                    self.assertEqual(lines[offset + 3:offset + 6], ['644', 'version', 'version'])

    def test_failed_download_or_checksum_never_installs_and_cleans_up(self):
        for flag in ('TEST_DOWNLOAD_FAIL', 'TEST_CHECKSUM_FAIL'):
            with self.subTest(flag=flag):
                (self.root / 'calls').unlink(missing_ok=True)
                self.install(env={**self.env, flag: '1'}, success=False)
                self.assertNotIn('install ', (self.root / 'calls').read_text())
                self.assertEqual(list(self.root.glob('tmp.*')), [])

    def test_unsupported_architecture_fails_before_download(self):
        self.install(env={**self.env, 'TEST_ARCH': 'riscv64'}, success=False)
        self.assertFalse((self.root / 'calls').exists())
        self.assertEqual(list(self.root.glob('tmp.*')), [])

    def test_apt_failure_is_not_reported_as_success(self):
        self.install(env={**self.env, 'TEST_APT_FAIL': '100'}, success=False)
        self.assertNotIn('version', (self.root / 'calls').read_text())
        self.assertEqual(list(self.root.glob('tmp.*')), [])

    def test_bootstrap_wiring(self):
        script = (REPO / 'infra/bootstrap.sh').read_text()
        self.assertIn('. "${SCRIPT_DIR}/lib/yazi.sh"', script)
        self.assertIn('\tinstall_github_cli\n\tinstall_yazi\n', script)


class YaziWrapperTests(Fixture):
    def setUp(self):
        super().setUp()
        self.zsh = shutil.which('zsh')
        self.assertIsNotNone(self.zsh, 'zsh is required for wrapper tests')
        framework = self.home / '.oh-my-zsh'
        framework.mkdir()
        (framework / 'oh-my-zsh.sh').write_text(':\n')
        (self.home / '.zshrc.local').write_text(':\n')
        for name in ('fzf', 'zoxide', 'fastfetch'):
            self.script(self.bin / name, 'exit 0\n')
        self.env.update(TEST_ARGS=str(self.root / 'args'), TEST_CWD_FILE=str(self.root / 'cwd-file'))
        self.script(self.bin / 'yazi', '''
printf '%s\\0' "$@" > "$TEST_ARGS"
for arg do
    case "$arg" in --cwd-file=*) tmp=${arg#--cwd-file=};; esac
done
printf '%s' "$tmp" > "$TEST_CWD_FILE"
[ "${TEST_NO_CWD:-0}" = 1 ] || printf '%s' "${TEST_DEST:-}" > "$tmp"
exit "${TEST_EXIT:-0}"
''')

    def wrapper(self, destination: str | Path = '', exit_code=0, extra=None):
        env = {**self.env, 'TEST_DEST': str(destination), 'TEST_EXIT': str(exit_code), **(extra or {})}
        code = '''
[[ -z ${TEST_ZSH_MODULE_PATH:-} ]] || module_path=("$TEST_ZSH_MODULE_PATH" $module_path)
source "$1"
setopt ERR_EXIT NO_UNSET
result=0
y 'argument with spaces' --hidden || result=$?
printf '%s' "$PWD" > "$HOME/final-cwd"
printf '%s' "$result" > "$HOME/result"
'''
        self.run_cmd([self.zsh, '-dfc', code, 'fixture', REPO / 'dots/zsh/.zshrc'], env=env)
        self.assertEqual((self.home / 'result').read_text(), str(exit_code))
        self.assertEqual(list(self.root.glob('yazi-cwd.*')), [])
        return (self.home / 'final-cwd').read_text()

    def test_changes_current_shell_directory_and_preserves_arguments(self):
        destination = self.root / 'directory with spaces'
        destination.mkdir()
        self.assertEqual(self.wrapper(destination), str(destination))
        args = (self.root / 'args').read_bytes().split(b'\0')
        self.assertEqual(args[:2], [b'argument with spaces', b'--hidden'])
        self.assertTrue(args[2].startswith(b'--cwd-file='))
        self.assertEqual(len(args), 4)

    def test_unusual_directory_names_are_not_split_or_trimmed(self):
        destination = self.root / ' -directory \\ with\nnewlines\n'
        destination.mkdir()
        self.assertEqual(self.wrapper(destination), str(destination))

    def test_empty_missing_and_unchanged_directory_keep_pwd(self):
        for destination in ('', self.root / 'missing', self.root):
            with self.subTest(destination=destination):
                self.assertEqual(self.wrapper(destination), str(self.root))

    def test_quit_without_cwd_keeps_pwd(self):
        self.assertEqual(self.wrapper(extra={'TEST_NO_CWD': '1'}), str(self.root))

    def test_failure_preserves_status_and_cleans_up(self):
        self.assertEqual(self.wrapper(exit_code=42), str(self.root))

    def test_mktemp_failure_does_not_launch_yazi(self):
        self.script(self.bin / 'mktemp', 'exit 1\n')
        self.wrapper(exit_code=1)
        self.assertFalse((self.root / 'args').exists())
