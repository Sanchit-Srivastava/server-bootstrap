"""Isolated regression fixtures; never invoke an installer entrypoint.

Only function libraries (or guarded definitions) are sourced. All mutable data,
Git repositories, HOME/XDG directories and tmux sockets live in TemporaryDirectory
(respects TMPDIR). No network, generated keypairs, sudo, package or account writes.
"""

import hashlib
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash") or "/bin/bash"
TMUX = shutil.which("tmux") or "tmux"


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="server-bootstrap-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        # Do not inherit Git config injection, login shell startup, or a live
        # tmux socket. Keep PATH and relocated-library settings for dev tools.
        self.env = {
            k: v for k, v in os.environ.items()
            if not k.startswith(("GIT_", "XDG_"))
            and k not in ("BASH_ENV", "ENV", "TMUX", "TMUX_PANE", "ZDOTDIR")
        }
        self.env.update(
            HOME=str(self.home),
            XDG_CONFIG_HOME=str(self.home / "config"),
            XDG_DATA_HOME=str(self.home / "data"),
            XDG_STATE_HOME=str(self.home / "state"),
            XDG_CACHE_HOME=str(self.home / "cache"),
            TMPDIR=str(self.root),
            PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_CONFIG_SYSTEM=os.devnull,
            GIT_CONFIG_NOSYSTEM="1",
            GIT_TERMINAL_PROMPT="0",
            GIT_ALLOW_PROTOCOL="file",
            GIT_DEFAULT_HASH="sha1",
            GIT_AUTHOR_NAME="Fixture",
            GIT_AUTHOR_EMAIL="fixture@example.invalid",
            GIT_COMMITTER_NAME="Fixture",
            GIT_COMMITTER_EMAIL="fixture@example.invalid",
            TEST_FORBIDDEN_CALLS=str(self.root / "forbidden-calls"),
        )
        for name in ("sudo", "apt", "apt-get", "chsh", "usermod", "systemctl", "curl", "wget"):
            self.script(self.bin / name, 'printf "%s\\n" "$0" >>"$TEST_FORBIDDEN_CALLS"\nexit 97\n')

    def tearDown(self):
        self.assertFalse((self.root / "forbidden-calls").exists(), "Unsafe command attempted")
        self.assertFalse((self.home / "installer-was-run").exists(), "Installer invoked")

    @staticmethod
    def script(path, body):
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)

    def run_cmd(self, args, *, success=True, env=None, cwd=None):
        result = subprocess.run(
            [str(a) for a in args], cwd=cwd or self.root, env=env or self.env,
            text=True, capture_output=True, timeout=25,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def bash(self, code, *args, **kwargs):
        return self.run_cmd([BASH, "-euo", "pipefail", "-c", code, "fixture", *args], **kwargs)

    def git(self, directory, *args, **kwargs):
        return self.run_cmd(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                             "-C", directory, *args], **kwargs).stdout.strip()


class AuthorizedKeysTests(Fixture):
    def setUp(self):
        super().setUp()
        self.keys = self.root / "incoming"
        self.keys.mkdir()
        self.ssh = self.home / "authorization-fixture"
        self.target = self.ssh / "authorized_keys"
        self.key1 = (REPO / "keys/primary.pub").read_text().strip()
        self.key2 = (REPO / "keys/fido-fallback.pub").read_text().strip()
        (self.keys / "first.pub").write_text(self.key1 + "\n")

    def existing(self, text):
        self.ssh.mkdir(exist_ok=True)
        self.target.write_text(text)

    def authorize(self, **kwargs):
        return self.bash('source "$1"; source "$2"; authorize_keys "$3" "$4"',
                         REPO / "infra/lib/common.sh", REPO / "infra/lib/authorized-keys.sh",
                         self.keys, self.ssh, **kwargs)

    def test_option_prefixed_keys_keep_restrictions(self):
        for prefix in ('restrict ', 'no-port-forwarding,no-pty ',
                       'command="printf \\"hello world\\"",from="192.0.2.0/24" ',
                       'cert-authority,principals="fixture user" '):
            with self.subTest(prefix=prefix):
                original = prefix + self.key1 + "\n"
                self.existing(original)
                self.authorize()
                self.authorize()
                self.assertEqual(self.target.read_text(), original)

    def test_key_in_comment_or_option_value_is_not_an_authorization(self):
        original = '# ' + self.key1 + '\ncommand="echo ' + self.key1 + '" ' + self.key2 + '\n'
        self.existing(original)
        self.authorize()
        self.assertEqual(self.target.read_text(), original + self.key1 + "\n")

    def test_missing_final_newline_gets_separator(self):
        for original in (self.key2, '# existing comment'):
            with self.subTest(original=original[:15]):
                self.existing(original)
                self.authorize()
                self.assertEqual(self.target.read_text(), original + "\n" + self.key1 + "\n")

    def test_existing_duplicate_without_newline_is_preserved(self):
        original = 'restrict ' + self.key1
        self.existing(original)
        self.authorize()
        self.assertEqual(self.target.read_text(), original)

    def test_invalid_later_key_leaves_existing_content_and_modes_unchanged(self):
        self.existing('restrict ' + self.key2 + "\n")
        before = self.target.read_bytes()
        self.target.chmod(0o640)
        self.ssh.chmod(0o750)
        (self.keys / "z-invalid.pub").write_text("ssh-ed25519 invalid-key-data\n")
        self.authorize(success=False)
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o640)
        self.assertEqual(stat.S_IMODE(self.ssh.stat().st_mode), 0o750)
        self.assertEqual(list(self.ssh.iterdir()), [self.target])

    def test_invalid_batch_does_not_create_authorization_directory(self):
        (self.keys / "z-invalid.pub").write_text(self.key1 + "\n" + self.key2 + "\n")
        self.authorize(success=False)
        self.assertFalse(self.ssh.exists())

    def test_incoming_options_are_rejected_not_reinterpreted(self):
        for prefix in ('restrict ', 'ssh-option="value" '):
            with self.subTest(prefix=prefix):
                (self.keys / "first.pub").write_text(prefix + self.key1 + "\n")
                self.authorize(success=False)
                self.assertFalse(self.ssh.exists())

    def test_duplicate_input_and_repeated_run_are_idempotent(self):
        (self.keys / "second.pub").write_text(self.key1.rsplit(" ", 1)[0] + " another-comment\n")
        (self.keys / "third.pub").write_text(self.key2)  # no incoming newline
        self.authorize()
        self.authorize()
        self.assertEqual(self.target.read_text(), self.key1 + "\n" + self.key2 + "\n")
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.ssh.stat().st_mode), 0o700)

    def test_empty_key_set_makes_no_writes(self):
        (self.keys / "first.pub").unlink()
        self.authorize(success=False)
        self.assertFalse(self.ssh.exists())

    def test_unparseable_existing_options_fail_without_replacing_target(self):
        original = 'command="unterminated ' + self.key2 + '\n'
        self.existing(original)
        self.authorize(success=False)
        self.assertEqual(self.target.read_text(), original)
        self.assertEqual(list(self.ssh.iterdir()), [self.target])

    def test_symlinked_target_is_refused(self):
        self.ssh.mkdir()
        elsewhere = self.root / "untouched"
        elsewhere.write_text(self.key2)
        self.target.symlink_to(elsewhere)
        self.authorize(success=False)
        self.assertEqual(elsewhere.read_text(), self.key2)


class RemoteCheckoutTests(Fixture):
    def setUp(self):
        super().setUp()
        self.origin = self.root / "origin"
        self.origin.mkdir()
        self.git(self.origin, "init", "-b", "main")
        self.script(self.origin / "install.sh", 'touch "$HOME/installer-was-run"\nexit 97\n')
        (self.origin / ".gitignore").write_text("ignored-artifact\n")
        (self.origin / "revision").write_text("first\n")
        self.git(self.origin, "add", ".")
        self.git(self.origin, "commit", "-m", "First fixture")
        self.first = self.git(self.origin, "rev-parse", "HEAD")
        self.git(self.origin, "tag", "-a", "release", "-m", "Fixture release")
        self.git(self.origin, "tag", "lightweight")
        (self.origin / "revision").write_text("second\n")
        self.git(self.origin, "commit", "-am", "Second fixture")
        self.second = self.git(self.origin, "rev-parse", "HEAD")
        self.target = self.root / "checkout with spaces"

    def clone(self):
        self.run_cmd(["git", "clone", "--", self.origin, self.target])

    def prepare(self, ref="main", **kwargs):
        return self.bash('source "$1"; prepare_repository "$2" "$3" "$4"',
                         REPO / "remote-install.sh", self.target, self.origin, ref, **kwargs)

    def test_sourcing_does_not_execute_main(self):
        self.bash('source "$1"', REPO / "remote-install.sh")
        self.assertFalse((self.home / "server-bootstrap").exists())

    def test_matching_existing_clone_is_verified_without_switching(self):
        self.clone()
        self.prepare()
        self.assertEqual(self.git(self.target, "rev-parse", "HEAD"), self.second)
        self.assertEqual(self.git(self.target, "branch", "--show-current"), "main")

    def test_mismatched_revision_does_not_run_or_switch_existing_checkout(self):
        self.clone()
        result = self.prepare("release", success=False)
        self.assertIn("does not match requested ref", result.stderr)
        self.assertEqual(self.git(self.target, "rev-parse", "HEAD"), self.second)
        self.assertEqual((self.target / "revision").read_text(), "second\n")
        self.assertEqual(self.git(self.target, "status", "--porcelain"), "")

    def test_wrong_origin_is_rejected_before_fetch(self):
        self.clone()
        self.git(self.target, "remote", "set-url", "origin", str(self.root / "other-origin"))
        result = self.prepare(success=False)
        self.assertIn("origin does not match", result.stderr)
        self.assertFalse((self.target / ".git/FETCH_HEAD").exists())

    def test_multiple_origin_urls_are_rejected(self):
        self.clone()
        self.git(self.target, "remote", "set-url", "--add", "origin", str(self.origin))
        self.prepare(success=False)
        self.assertFalse((self.target / ".git/FETCH_HEAD").exists())

    def check_dirty(self, path, staged=False):
        self.clone()
        (self.target / path).write_text("local work\n")
        if staged:
            self.git(self.target, "add", path)
        result = self.prepare(success=False)
        self.assertIn("dirty", result.stderr)
        self.assertEqual((self.target / path).read_text(), "local work\n")
        self.assertFalse((self.target / ".git/FETCH_HEAD").exists())

    def test_modified_file_is_refused(self):
        self.check_dirty("revision")

    def test_staged_file_is_refused(self):
        self.check_dirty("revision", staged=True)

    def test_untracked_file_is_refused(self):
        self.check_dirty("untracked")

    def test_ignored_file_is_refused(self):
        self.check_dirty("ignored-artifact")

    def test_index_flags_cannot_hide_modified_files(self):
        self.clone()
        for flag in ("assume-unchanged", "skip-worktree"):
            with self.subTest(flag=flag):
                self.git(self.target, "update-index", "--" + flag, "revision")
                (self.target / "revision").write_text("hidden local work\n")
                result = self.prepare(success=False)
                self.assertIn("index checks", result.stderr)
                self.assertEqual((self.target / "revision").read_text(), "hidden local work\n")
                self.git(self.target, "update-index", "--no-" + flag, "revision")
                self.git(self.target, "checkout", "--", "revision")

    def test_fresh_branch_tracks_requested_origin_branch(self):
        self.prepare()
        self.assertEqual(self.git(self.target, "rev-parse", "HEAD"), self.second)
        self.assertEqual(self.git(self.target, "rev-parse", "--abbrev-ref", "@{upstream}"), "origin/main")
        self.git(self.target, "pull", "--ff-only")

    def test_annotated_tag_creates_detached_checkout(self):
        self.prepare("release")
        self.assertEqual(self.git(self.target, "rev-parse", "HEAD"), self.first)
        self.assertEqual(self.git(self.target, "branch", "--show-current"), "")
        self.prepare("refs/tags/release")

    def test_lightweight_tag_creates_detached_checkout(self):
        self.prepare("lightweight")
        self.assertEqual(self.git(self.target, "rev-parse", "HEAD"), self.first)
        self.assertEqual(self.git(self.target, "branch", "--show-current"), "")

    def test_full_commit_id_selects_older_commit_and_is_repeatable(self):
        self.prepare(self.first)
        self.assertEqual(self.git(self.target, "rev-parse", "HEAD"), self.first)
        self.assertEqual(self.git(self.target, "branch", "--show-current"), "")
        self.prepare(self.first)

    def test_ambiguous_short_ref_requires_qualification(self):
        self.git(self.origin, "branch", "release")
        self.prepare("release", success=False)
        self.assertFalse(self.target.exists())
        self.prepare("refs/heads/release")
        self.assertEqual(self.git(self.target, "rev-parse", "HEAD"), self.second)
        self.prepare("refs/tags/release", success=False)

    def test_invalid_or_missing_ref_fails_before_creating_checkout(self):
        for ref in ("", "--upload-pack=anything", "main~1", "refs/notes/test", "does-not-exist"):
            with self.subTest(ref=ref):
                self.prepare(ref, success=False)
                self.assertFalse(self.target.exists())

    def test_failed_fetch_never_changes_existing_checkout(self):
        self.clone()
        self.prepare("f" * 40, success=False)
        self.assertEqual(self.git(self.target, "rev-parse", "HEAD"), self.second)
        self.assertEqual(self.git(self.target, "status", "--porcelain"), "")

    def test_non_repository_target_is_not_overwritten(self):
        self.target.mkdir()
        (self.target / "keep").write_text("keep\n")
        self.prepare(success=False)
        self.assertEqual((self.target / "keep").read_text(), "keep\n")


class PublicAuditTests(Fixture):
    def setUp(self):
        super().setUp()
        self.audit_root = self.root / "audit"
        (self.audit_root / "infra/lib").mkdir(parents=True)
        for relative in ("infra/public-audit.sh", "infra/lib/common.sh"):
            shutil.copy2(REPO / relative, self.audit_root / relative)
        # Harmless detector strings, assembled to avoid self-matching tests.
        self.marker = "-----BEGIN OPENSSH " + "PRIVATE KEY-----\nNO KEY DATA\n"

    def audit(self, **kwargs):
        return self.run_cmd([BASH, self.audit_root / "infra/public-audit.sh"], **kwargs)

    def test_clean_tree_passes(self):
        self.assertIn("audit passed", self.audit().stdout)

    def test_missing_scanner_fails_closed(self):
        isolated = self.root / "missing-scanner-bin"
        isolated.mkdir()
        for name in ("dirname", "find"):
            (isolated / name).symlink_to(shutil.which(name) or name)
        (self.audit_root / "marker.txt").write_text(self.marker)
        result = self.audit(env={**self.env, "PATH": str(isolated)}, success=False)
        self.assertIn("ripgrep", result.stderr)
        self.assertNotIn("audit passed", result.stdout)

    def test_scanner_errors_fail_closed_without_echoing_diagnostics(self):
        for status in (2, 127):
            with self.subTest(status=status):
                self.script(self.bin / "rg", 'printf "sensitive diagnostic\\n" >&2\nexit ' + str(status) + '\n')
                result = self.audit(success=False)
                self.assertIn("scanner failed", result.stderr)
                self.assertNotIn("sensitive diagnostic", result.stderr)
                self.assertNotIn("audit passed", result.stdout)

    def test_scanner_no_matches_status_is_success(self):
        self.script(self.bin / "rg", "exit 1\n")
        self.audit()

    def test_markers_are_reported_by_filename_only(self):
        for marker in (self.marker, 'AGE-SECRET-' + 'KEY-HARMLESSMARKER', 'ghp_' + 'HARMLESSMARKER'):
            with self.subTest(marker_kind=marker[:5]):
                (self.audit_root / "marker.txt").write_text(marker)
                result = self.audit(success=False)
                self.assertIn("./marker.txt", result.stderr)
                self.assertNotIn(marker, result.stdout + result.stderr)

    def test_ignored_hidden_and_binary_files_are_scanned(self):
        self.run_cmd(["git", "init", self.audit_root])
        (self.audit_root / ".gitignore").write_text(".hidden-marker\n")
        (self.audit_root / ".hidden-marker").write_bytes(b"\x00" + self.marker.encode())
        result = self.audit(success=False)
        self.assertIn(".hidden-marker", result.stderr)

    def test_user_ripgrep_config_cannot_disable_scan(self):
        config = self.root / "rg-config"
        config.write_text("--glob=!**\n")
        (self.audit_root / "marker.txt").write_text(self.marker)
        self.audit(env={**self.env, "RIPGREP_CONFIG_PATH": str(config)}, success=False)

    def test_git_metadata_is_excluded(self):
        (self.audit_root / ".git").mkdir()
        (self.audit_root / ".git/marker.txt").write_text(self.marker)
        self.audit()

    def test_forbidden_filename_and_find_errors_fail(self):
        marker = self.audit_root / ".env"
        marker.write_text("harmless fixture\n")
        self.assertIn("Forbidden", self.audit(success=False).stderr)
        marker.unlink()
        self.script(self.bin / "find", "exit 2\n")
        self.audit(success=False)


class DotfileTests(Fixture):
    def link(self, **kwargs):
        return self.bash('source "$1"; link_user_dotfiles', REPO / "infra/dotfiles.sh", **kwargs)

    def assert_links(self, config):
        for target, source in (("tmux/tmux.conf", "tmux/tmux.conf"), ("nvim", "nvim"),
                               ("lazygit/config.yml", "lazygit/config.yml"), ("bat/config", "bat/config")):
            self.assertEqual((config / target).readlink(), REPO / "dots" / source)
        self.assertEqual((self.home / ".zshenv").readlink(), REPO / "dots/zsh/.zshenv")

    def test_custom_xdg_destinations_and_repeated_links(self):
        self.link()
        self.link()
        self.assert_links(Path(self.env["XDG_CONFIG_HOME"]))
        self.assertFalse((self.home / ".config").exists())
        self.assertEqual(list(self.home.rglob("*.bak")), [])

    def test_default_xdg_destinations(self):
        env = {k: v for k, v in self.env.items() if k != "XDG_CONFIG_HOME"}
        self.link(env=env)
        self.assert_links(self.home / ".config")

    def test_relative_xdg_fails_before_any_links(self):
        self.link(env={**self.env, "XDG_CONFIG_HOME": "relative"}, success=False)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_existing_config_is_backed_up(self):
        config = Path(self.env["XDG_CONFIG_HOME"])
        (config / "bat").mkdir(parents=True)
        (config / "bat/config").write_text("original\n")
        self.link()
        self.assertEqual((config / "bat/config.pre-server-bootstrap.bak").read_text(), "original\n")

    def test_existing_shell_dependency_is_never_implicitly_updated(self):
        target = self.root / "dependency"
        target.mkdir()
        self.git(target, "init")
        (target / "local-work").write_text("untouched\n")
        self.bash('source "$1"; clone_if_missing "$2" "$3"', REPO / "infra/dotfiles.sh",
                  self.root / "nonexistent-origin", target)
        self.assertEqual((target / "local-work").read_text(), "untouched\n")
        zshrc = (REPO / "dots/zsh/.zshrc").read_text()
        self.assertLess(zshrc.index("zstyle ':omz:update' mode disabled"), zshrc.index('source "${ZSH}/oh-my-zsh.sh"'))

    def test_lazygit_050_paging_schema(self):
        # The packaged release uses this schema. No third-party YAML dependency
        # is needed for a small, deliberately fixed config contract.
        lines = (REPO / "dots/lazygit/config.yml").read_text().splitlines()
        self.assertIn("  paging:", lines)
        self.assertIn("    colorArg: always", lines)
        self.assertIn("    pager: delta --dark --paging=never --line-numbers", lines)
        self.assertIn("    useConfig: false", lines)
        self.assertNotIn("diffRenderers", "\n".join(lines))


class TerminalTests(Fixture):
    def setUp(self):
        super().setUp()
        self.zsh = shutil.which("zsh")
        self.assertIsNotNone(self.zsh, "zsh is required for terminal startup tests")
        framework = self.home / ".oh-my-zsh"
        framework.mkdir()
        # Observe capabilities at the exact point real plugins would load.
        (framework / "oh-my-zsh.sh").write_text(
            'zmodload zsh/terminfo\n'
            'print -r -- "plugin-term=$TERM"\n'
            'print -r -- "plugin-up=${terminfo[cuu1]}"\n'
        )
        (self.home / ".zshrc.local").write_text(":\n")
        for name in ("fzf", "zoxide", "fastfetch"):
            self.script(self.bin / name, "exit 0\n")

    def shell(self, term, interactive=True):
        # Relocated development binaries may need their extracted module tree.
        code = ('[[ -z ${TEST_ZSH_MODULE_PATH:-} ]] || '
                'module_path=("$TEST_ZSH_MODULE_PATH" $module_path); '
                'source "$1"; print -r -- "final-term=${TERM-unset}"')
        env = {**self.env, "TERM": term}
        if term is None:
            env.pop("TERM")
        return self.run_cmd([self.zsh, "-dfic" if interactive else "-dfc", code,
                             "fixture", REPO / "dots/zsh/.zshrc"], env=env)

    def test_unknown_xterm_recovers_cursor_motion_before_plugins(self):
        result = self.shell("xterm-server-bootstrap-missing-fixture")
        self.assertIn("plugin-term=xterm-256color\n", result.stdout)
        self.assertIn("plugin-up=\x1b[A\n", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_known_and_non_xterm_types_are_preserved(self):
        for term in ("xterm-256color", "tmux-256color", "screen-256color", "dumb",
                     "vt100", "unknown-fixture", "", None):
            with self.subTest(term=term):
                self.assertIn("final-term=" + ("unset" if term is None else term) + "\n",
                              self.shell(term).stdout)

    def test_installed_ghostty_entry_is_preserved(self):
        # A private terminfo entry models a server with Ghostty support installed.
        source = self.root / "ghostty.terminfo"
        source.write_text("xterm-ghostty|fixture terminal, use=xterm-256color,\n")
        database = self.root / "terminfo"
        self.run_cmd(["tic", "-x", "-o", database, source])
        self.env["TERMINFO"] = str(database)
        self.assertIn("plugin-term=xterm-ghostty\n", self.shell("xterm-ghostty").stdout)

    def test_unavailable_fallback_does_not_change_term(self):
        self.script(self.bin / "infocmp", "exit 1\n")
        self.assertIn("plugin-term=xterm-missing\n", self.shell("xterm-missing").stdout)

    def test_noninteractive_shell_keeps_term(self):
        self.assertIn("final-term=xterm-missing\n",
                      self.shell("xterm-missing", interactive=False).stdout)


class SessionizerTests(Fixture):
    def setUp(self):
        super().setUp()
        self.assertIsNotNone(shutil.which(TMUX), "tmux is required for isolated sessionizer tests")
        self.socket = self.root / "tmux.sock"
        self.env["TEST_ATTACH_LOG"] = str(self.root / "attach-log")
        self.tmux("new-session", "-d", "-s", "fixture-seed", "/bin/sleep 120")
        self.addCleanup(self.stop_tmux)
        self.tmux("set-option", "-g", "default-shell", "/bin/sh")
        self.tmux("set-option", "-g", "default-command", "/bin/sleep 120")
        # All session operations go to a real, private tmux socket. Only the
        # interactive client attach/switch calls are replaced by a log entry.
        self.script(self.bin / "tmux", '''case "$1" in
attach-session|switch-client) printf '%s\\n' "$*" >>"$TEST_ATTACH_LOG"; exit 0;;
esac
exec ''' + shlex.quote(TMUX) + " -S " + shlex.quote(str(self.socket)) + ' -f /dev/null "$@"\n')

    def tmux(self, *args):
        return self.run_cmd([TMUX, "-S", self.socket, "-f", os.devnull, *args]).stdout.strip()

    def stop_tmux(self):
        subprocess.run([TMUX, "-S", str(self.socket), "kill-server"], env=self.env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)

    def select(self, directory, **kwargs):
        return self.run_cmd([BASH, REPO / "dots/bin/tmux-sessionizer", directory], **kwargs)

    def projects(self):
        paths = [self.root / "projects/api", self.root / "services/api"]
        for path in paths:
            path.mkdir(parents=True)
        return paths

    def sessions(self):
        return [s for s in self.tmux("list-sessions", "-F", "#{session_name}").splitlines()
                if s != "fixture-seed"]

    def test_same_basename_projects_have_distinct_sessions_and_paths(self):
        first, second = self.projects()
        self.select(first)
        self.select(second, env={**self.env, "TMUX": "isolated-client"})
        sessions = self.sessions()
        self.assertEqual(len(sessions), 2)
        self.assertEqual({self.tmux("display-message", "-p", "-t", "=" + s + ":", "#{pane_current_path}")
                          for s in sessions}, {str(first), str(second)})
        log = (self.root / "attach-log").read_text()
        self.assertIn("attach-session", log)
        self.assertIn("switch-client", log)

    def test_symlink_relative_and_trailing_slash_share_one_identity(self):
        first, _ = self.projects()
        alias = self.root / "alias"
        alias.symlink_to(first, target_is_directory=True)
        for path in (first, alias, "projects/api/"):
            self.select(path)
        self.assertEqual(len(self.sessions()), 1)

    def test_unsafe_basename_characters_are_sanitized(self):
        directory = self.root / "project .: [brackets]"
        directory.mkdir()
        self.select(directory)
        self.assertEqual(len(self.sessions()), 1)
        self.assertRegex(self.sessions()[0], r"^[A-Za-z0-9_-]+$")

    def test_existing_session_with_wrong_path_is_never_attached(self):
        first, _ = self.projects()
        digest = hashlib.sha256(str(first).encode()).hexdigest()[:16]
        name = "api-" + digest
        self.tmux("new-session", "-d", "-s", name, "-c", str(self.root))
        self.tmux("set-option", "-t", "=" + name + ":", "@sessionizer-path", str(self.root))
        self.select(first, success=False)
        self.assertFalse((self.root / "attach-log").exists())

    def test_missing_directory_creates_no_session(self):
        self.select(self.root / "missing", success=False)
        self.assertEqual(self.sessions(), [])

    def test_tmux_config_loads_and_reload_respects_xdg(self):
        config = Path(self.env["XDG_CONFIG_HOME"]) / "tmux/tmux.conf"
        config.parent.mkdir(parents=True)
        config.write_text((REPO / "dots/tmux/tmux.conf").read_text())
        self.tmux("source-file", str(config))
        self.assertEqual(self.tmux("show-options", "-gv", "prefix"), "C-Space")
        binding = self.tmux("list-keys", "-T", "prefix", "e")
        self.assertIn("XDG_CONFIG_HOME", binding)
        self.tmux("set-option", "-g", "prefix", "C-b")
        # Execute the exact shell body bound to reload on the private server.
        reload_line = next(line for line in config.read_text().splitlines() if line.startswith("bind e "))
        command = shlex.split(reload_line)[-1]
        self.bash(command)
        self.assertEqual(self.tmux("show-options", "-gv", "prefix"), "C-Space")


if __name__ == "__main__":
    unittest.main(verbosity=2)
