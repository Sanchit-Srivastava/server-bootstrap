"""Exercise the CLI helper with simulated network/APT and temporary files only."""

import stat

from test_regressions import Fixture, REPO


class GitHubCliTests(Fixture):
    def setUp(self):
        super().setUp()
        self.apt = self.root / "apt"
        self.apt.mkdir()
        self.env.update(TEST_APT_ROOT=str(self.apt), TEST_LOG=str(self.root / "calls"))
        self.script(self.bin / "curl", '''
[ "${TEST_DOWNLOAD_FAIL:-0}" = 0 ] || exit 22
while [ "$1" != -o ]; do shift; done
if [ "${TEST_EMPTY_KEY:-0}" = 1 ]; then
    : > "$2"
else
    printf 'fixture public keyring' > "$2"
fi
''')
        self.script(self.bin / "dpkg", 'printf "%s\\n" "${TEST_ARCH:-amd64}"\n')
        # Never execute privileged commands: translate only the expected install
        # destinations into the fixture and record simulated APT operations.
        self.script(self.bin / "sudo", '''
printf '%s\\n' "$*" >> "$TEST_LOG"
case "$1 $2" in
    'install -d')
        mkdir -p "$TEST_APT_ROOT/keyrings" "$TEST_APT_ROOT/sources.list.d" ;;
    'install -m')
        case "$5" in
            /etc/apt/keyrings/githubcli-archive-keyring.gpg)
                install -m "$3" "$4" "$TEST_APT_ROOT/keyrings/githubcli-archive-keyring.gpg" ;;
            /etc/apt/sources.list.d/github-cli.list)
                install -m "$3" "$4" "$TEST_APT_ROOT/sources.list.d/github-cli.list" ;;
            *) exit 97 ;;
        esac ;;
    'apt-get update') exit "${TEST_APT_FAIL:-0}" ;;
    'apt-get install') [ "$*" = 'apt-get install -y --no-install-recommends gh' ] ;;
    *) exit 97 ;;
esac
''')
        self.script(self.bin / "gh", '''
[ "$*" = --version ] || exit 97
printf 'gh --version\\n' >> "$TEST_LOG"
''')

    def install_cli(self, **kwargs):
        return self.bash('source "$1"; source "$2"; install_github_cli',
                         REPO / "infra/lib/common.sh", REPO / "infra/lib/github-cli.sh",
                         **kwargs)

    def test_sourcing_has_no_side_effects(self):
        self.bash('source "$1"', REPO / "infra/lib/github-cli.sh")
        self.assertEqual(list(self.apt.iterdir()), [])
        self.assertFalse((self.root / "calls").exists())

    def test_install_and_rerun_for_supported_architectures(self):
        for arch in ("amd64", "arm64"):
            with self.subTest(architecture=arch):
                env = {**self.env, "TEST_ARCH": arch}
                self.install_cli(env=env)
                self.install_cli(env=env)
                source = self.apt / "sources.list.d/github-cli.list"
                self.assertEqual(source.read_text(),
                    f"deb [arch={arch} signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] "
                    "https://cli.github.com/packages stable main\n")
                key = self.apt / "keyrings/githubcli-archive-keyring.gpg"
                self.assertEqual(key.read_text(), "fixture public keyring")
                for path in (source, key):
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
                self.assertEqual(list(self.root.glob("tmp.*")), [])
        calls = (self.root / "calls").read_text()
        self.assertEqual(calls.count("apt-get install -y --no-install-recommends gh\n"), 4)
        self.assertTrue(calls.endswith("gh --version\n"))

    def test_failed_or_empty_download_never_changes_apt(self):
        for flag in ("TEST_DOWNLOAD_FAIL", "TEST_EMPTY_KEY"):
            with self.subTest(flag=flag):
                self.install_cli(env={**self.env, flag: "1"}, success=False)
                self.assertEqual(list(self.apt.iterdir()), [])
                self.assertFalse((self.root / "calls").exists())
                self.assertEqual(list(self.root.glob("tmp.*")), [])

    def test_failed_apt_update_stops_before_install(self):
        self.install_cli(env={**self.env, "TEST_APT_FAIL": "100"}, success=False)
        calls = (self.root / "calls").read_text()
        self.assertNotIn("apt-get install", calls)
        self.assertNotIn("gh --version", calls)
        self.assertEqual(list(self.root.glob("tmp.*")), [])

    def test_bootstrap_installs_cli_after_download_prerequisites(self):
        script = (REPO / "infra/bootstrap.sh").read_text()
        self.assertIn('. "${SCRIPT_DIR}/lib/github-cli.sh"', script)
        self.assertIn("\tinstall_packages\n\tinstall_github_cli\n\tset_login_shell", script)
