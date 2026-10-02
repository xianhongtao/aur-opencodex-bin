"""The publication script must explain why it refuses to publish.

These guards exist because a missing Git checkout used to surface as a bare
"fatal: not a git repository" message with no hint about the cause.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'scripts' / 'publish-aur.sh'


def publish_env(**overrides):
    env = {
        'PATH': os.environ['PATH'],
        'HOME': os.environ.get('HOME') or tempfile.gettempdir(),
        'AUR_SSH_PRIVATE_KEY': 'test-only-key',
        'AUR_USERNAME': 'tester',
        'AUR_EMAIL': 'tester@example.com',
    }
    env.update(overrides)
    return env


def run_script(script, cwd, env):
    return subprocess.run(
        ['bash', str(script)], cwd=str(cwd), env=env, capture_output=True, text=True, check=False
    )


def make_throwaway_checkout(directory):
    """Copy the script and recipe into a tree whose Git state we control."""
    scripts = Path(directory) / 'scripts'
    scripts.mkdir()
    shutil.copy(SCRIPT, scripts / 'publish-aur.sh')
    shutil.copy(REPO_ROOT / 'PKGBUILD', directory)
    return scripts / 'publish-aur.sh'


class PublishAurGuardTests(unittest.TestCase):
    def test_each_missing_setting_is_reported(self):
        for variable in ('AUR_SSH_PRIVATE_KEY', 'AUR_USERNAME', 'AUR_EMAIL'):
            with self.subTest(variable=variable):
                env = publish_env()
                del env[variable]
                result = run_script(SCRIPT, REPO_ROOT, env)
                self.assertEqual(result.returncode, 1)
                self.assertIn(variable, result.stderr)

    @unittest.skipIf(os.geteuid() == 0, 'requires an unprivileged user')
    def test_directory_without_git_checkout_is_reported(self):
        with tempfile.TemporaryDirectory() as work:
            script = make_throwaway_checkout(work)
            result = run_script(script, work, publish_env())
            self.assertEqual(result.returncode, 1)
            self.assertIn('Not a Git checkout', result.stderr)
            self.assertNotIn('not a git repository', result.stderr)

    @unittest.skipIf(os.geteuid() == 0, 'requires an unprivileged user')
    def test_stale_srcinfo_stops_publication_before_any_network_use(self):
        with tempfile.TemporaryDirectory() as work:
            script = make_throwaway_checkout(work)
            (Path(work) / '.SRCINFO').write_text(
                'pkgbase = opencodex-bin\n\tpkgver = 0.0.0\n', encoding='utf-8'
            )
            env = publish_env()
            subprocess.run(['git', 'init', '-q', '-b', 'main', '.'], cwd=work, env=env, check=True)
            subprocess.run(
                [
                    'git', '-c', 'user.email=test@example.com', '-c', 'user.name=Test',
                    '-c', 'commit.gpgsign=false', 'commit', '-q', '--allow-empty', '-m', 'init',
                ],
                cwd=work,
                env=env,
                check=True,
            )
            result = run_script(script, work, env)
            self.assertEqual(result.returncode, 1)
            self.assertIn('Stale .SRCINFO', result.stderr)
            self.assertNotIn('not a git repository', result.stderr)

    @unittest.skipUnless(os.geteuid() == 0, 'requires root')
    def test_root_is_refused(self):
        result = run_script(SCRIPT, REPO_ROOT, publish_env())
        self.assertEqual(result.returncode, 1)
        self.assertIn('unprivileged', result.stderr)


if __name__ == '__main__':
    unittest.main()
