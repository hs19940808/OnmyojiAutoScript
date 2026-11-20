import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from deploy.config import ConfigModel, DeployConfig, ExecutionError
from deploy.git import GitManager
from deploy.utils import poor_yaml_read
from module.server.updater import Updater


ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which('git')


class LocalGitManager(GitManager):
    def __init__(self, checkout, hooks):
        self.checkout = checkout
        self.hooks = hooks
        self.git = Path(GIT).as_posix()
        self.commands = []

    def execute(self, command, allow_failure=False, output=True):
        self.commands.append(command)
        args = shlex.split(command)
        result = subprocess.run(
            [args[0], '-c', f'core.hooksPath={self.hooks.as_posix()}', *args[1:]],
            cwd=self.checkout, capture_output=True, text=True, encoding='utf-8',
        )
        if result.returncode and not allow_failure:
            raise ExecutionError(result.stderr)
        return result.returncode == 0


class StartupPreservationTests(unittest.TestCase):
    def test_disabled_startup_does_not_execute_git(self):
        manager = GitManager.__new__(GitManager)
        manager.AutoUpdate = False
        manager.git_repository_init = Mock()
        manager.git_install()
        manager.git_repository_init.assert_not_called()

    def test_new_configuration_keeps_startup_updates_disabled(self):
        test_dir = ROOT / 'outputs' / 'startup-preserve-20261112'
        with tempfile.TemporaryDirectory(dir=test_dir, prefix='config-test-') as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(test_dir.resolve()))
            config = DeployConfig(file=str(Path(folder) / 'deploy.yaml'))
            self.assertFalse(config.AutoUpdate)
            self.assertTrue(config.KeepLocalChanges)
        self.assertFalse(ConfigModel.AutoUpdate)
        self.assertFalse(poor_yaml_read(ROOT / 'config' / 'deploy.yaml')['AutoUpdate'])

    def test_manual_update_is_fast_forward_only(self):
        updater = Updater.__new__(Updater)
        updater.config = {}
        updater.git = 'git'
        updater.Branch = 'main'
        updater.execute = Mock(return_value=True)
        self.assertTrue(updater.execute_pull())
        updater.execute.assert_called_once_with('"git" pull --ff-only origin main', allow_failure=True)

    def test_failed_manual_update_reports_failure_without_reset(self):
        updater = Updater.__new__(Updater)
        updater.config = {}
        updater.git = 'git'
        updater.Branch = 'main'
        updater.execute = Mock(return_value=False)
        self.assertFalse(updater.execute_pull())
        self.assertEqual(updater.execute.call_count, 3)
        self.assertTrue(all(' pull --ff-only ' in call.args[0] for call in updater.execute.call_args_list))


@unittest.skipUnless(GIT, 'Git is required for local update integration tests')
class RealGitPreservationTests(unittest.TestCase):
    def setUp(self):
        test_dir = ROOT / 'outputs' / 'startup-preserve-20261112'
        self.temp = tempfile.TemporaryDirectory(dir=test_dir, prefix='git-test-')
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(test_dir.resolve()))
        self.addCleanup(self.temp.cleanup)
        self.hooks = self.base / 'empty-hooks'
        self.hooks.mkdir()
        self.remote, self.seed, self.local = [self.base / name for name in ('remote', 'seed', 'local')]
        self.run_git(self.base, 'init', '-q', '--bare', self.remote.as_posix())
        self.run_git(self.base, 'init', '-q', '-b', 'main', self.seed.as_posix())
        self.run_git(self.seed, 'config', 'user.name', 'OAS local regression test')
        self.run_git(self.seed, 'config', 'user.email', 'oas-test@localhost')
        self.run_git(self.seed, 'config', 'commit.gpgsign', 'false')
        (self.seed / 'target.py').write_text('base target\n', encoding='utf-8')
        (self.seed / 'other.py').write_text('base other\n', encoding='utf-8')
        self.commit_seed()
        self.run_git(self.seed, 'remote', 'add', 'origin', self.remote.as_posix())
        self.run_git(self.seed, 'push', '-q', '-u', 'origin', 'main')
        self.run_git(self.base, 'clone', '-q', '-b', 'main', self.remote.as_posix(), self.local.as_posix())
        self.customized = b'user customization: five beans\n'
        (self.local / 'target.py').write_bytes(self.customized)

    def run_git(self, cwd, *args):
        result = subprocess.run(
            [GIT, '-c', f'core.hooksPath={self.hooks.as_posix()}', *args],
            cwd=cwd, capture_output=True, text=True, encoding='utf-8',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit_seed(self):
        self.run_git(self.seed, 'add', '.')
        self.run_git(self.seed, 'commit', '-q', '-m', 'local fixture update')

    def test_overlapping_update_preserves_local_file_with_either_legacy_flag(self):
        (self.seed / 'target.py').write_text('incoming upstream target\n', encoding='utf-8')
        self.commit_seed()
        self.run_git(self.seed, 'push', '-q', 'origin', 'main')
        original_head = self.run_git(self.local, 'rev-parse', 'HEAD')
        for keep_changes in (True, False):
            with self.subTest(keep_changes=keep_changes):
                manager = LocalGitManager(self.local, self.hooks)
                with self.assertRaises(ExecutionError):
                    manager.git_repository_init(self.remote.as_posix(), branch='main', keep_changes=keep_changes)
                self.assertEqual((self.local / 'target.py').read_bytes(), self.customized)
                self.assertEqual(self.run_git(self.local, 'rev-parse', 'HEAD'), original_head)
                self.assertEqual(self.run_git(self.local, 'stash', 'list'), '')
                self.assertFalse(any(' reset ' in command or ' stash' in command for command in manager.commands))

    def test_nonoverlapping_update_keeps_customization_and_updates_other_file(self):
        (self.seed / 'other.py').write_text('incoming other file\n', encoding='utf-8')
        self.commit_seed()
        self.run_git(self.seed, 'push', '-q', 'origin', 'main')
        manager = LocalGitManager(self.local, self.hooks)
        manager.git_repository_init(self.remote.as_posix(), branch='main', keep_changes=False)
        self.assertEqual((self.local / 'target.py').read_bytes(), self.customized)
        self.assertEqual((self.local / 'other.py').read_text(encoding='utf-8'), 'incoming other file\n')
        self.assertEqual(self.run_git(self.local, 'stash', 'list'), '')


if __name__ == '__main__':
    unittest.main()
