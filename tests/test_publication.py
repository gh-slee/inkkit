"""Publication tests use disposable Git repositories and invented data only."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import tarfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('publication', Path(__file__).resolve().parents[1] / 'scripts/check_publication.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Synthetic Contributor')
        self.git('config', 'user.email', '123+synthetic@users.noreply.github.com')
        (self.root / '.gitignore').write_text('xteink-x3-backup/\nwork/\nAGENTS.override.md\n')
        (self.root / 'README.md').write_text('Synthetic public project.\n')
        self.git('add', '--', '.gitignore', 'README.md')
        self.git('commit', '-qm', 'Synthetic initial source')

    def git(self, *args):
        return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null', '-C', str(self.root), *args],
                                       stderr=subprocess.PIPE)

    def test_clean_worktree_index_and_history(self):
        for mode in ('worktree', 'staged', 'history'):
            with self.subTest(mode=mode):
                count, errors = guard.audit(self.root, mode)
                self.assertEqual(errors, [])
                self.assertEqual(count, 2)

    def test_ignored_backup_not_read_or_changed(self):
        backup = self.root / 'xteink-x3-backup'
        backup.mkdir()
        private = backup / 'synthetic.zip'
        private.write_bytes(b'synthetic private payload')
        before = private.stat()
        original_read = Path.read_bytes
        def read(path):
            if path == private:
                raise AssertionError('A private backup must never be read by the guard')
            return original_read(path)
        with patch.object(Path, 'read_bytes', read):
            self.assertEqual(guard.audit(self.root, 'worktree')[1], [])
        self.assertEqual(private.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(private.read_bytes(), b'synthetic private payload')

    def test_force_added_backup_blocked_without_reading_blob(self):
        path = self.root / 'xteink-x3-backup/synthetic.zip'
        path.parent.mkdir()
        path.write_bytes(b'synthetic private payload')
        self.git('add', '-f', '--', 'xteink-x3-backup/synthetic.zip')
        self.assertTrue(guard.audit(self.root, 'staged')[1])
        with patch.object(guard, 'git', side_effect=AssertionError('must not read rejected blob')):
            self.assertTrue(guard.inspect_entry(self.root, 'xteink-x3-backup/synthetic.zip', '100644', 'fake', '0'))

    def test_secret_in_index_not_hidden_by_clean_worktree(self):
        (self.root / 'README.md').write_text('ghp_' + 'X' * 36)
        self.git('add', '--', 'README.md')
        (self.root / 'README.md').write_text('Clean synthetic worktree.\n')
        self.assertTrue(guard.audit(self.root, 'staged')[1])
        self.assertEqual(guard.audit(self.root, 'worktree')[1], [])

    def test_deleted_private_history_still_blocked(self):
        (self.root / 'private.txt').write_text('Invented sensitive data')
        self.git('add', '--', 'private.txt')
        self.git('commit', '-qm', 'Synthetic private addition')
        self.git('rm', '-q', 'private.txt')
        self.git('commit', '-qm', 'Synthetic private removal')
        self.assertEqual(guard.audit(self.root, 'staged')[1], [])
        self.assertTrue(guard.audit(self.root, 'history')[1])

    def test_same_blob_under_unapproved_historical_name(self):
        self.git('mv', 'README.md', 'private.txt')
        self.git('commit', '-qm', 'Synthetic rename')
        self.git('mv', 'private.txt', 'README.md')
        self.git('commit', '-qm', 'Synthetic restore name')
        self.assertTrue(guard.audit(self.root, 'history')[1])

    def test_symlink_rejected_in_worktree_and_index(self):
        (self.root / 'README.md').unlink()
        (self.root / 'README.md').symlink_to('.gitignore')
        self.git('add', '--', 'README.md')
        for mode in ('staged','worktree'):
            self.assertTrue(guard.audit(self.root, mode)[1])

    def test_secret_and_home_path_patterns(self):
        cases = [b'ghp_' + b'X' * 36, b'AKIA' + b'A' * 16,
                 b'https://' + b'user:synthetic-password@example.invalid',
                 b'/Users/' + b'synthetic-user/project/',
                 b'password = "' + b'synthetic-secret-value' + b'"']
        for payload in cases:
            with self.subTest(payload=payload[:5]):
                self.assertTrue(guard.content_issues(payload))
        self.assertEqual(guard.content_issues(b'password = "example-placeholder"'), [])

    def test_binary_and_size_limits(self):
        self.assertTrue(guard.content_issues(b'\0'))
        with patch.object(guard, 'MAX_BYTES', 1):
            self.assertTrue(guard.audit(self.root, 'staged')[1])

    def test_unknown_nonignored_source_rejected(self):
        (self.root / 'unreviewed.txt').write_text('Synthetic unknown file')
        self.assertTrue(guard.audit(self.root, 'worktree')[1])

    def test_noreply_commit_identity_required(self):
        self.git('config', 'user.email', 'synthetic@example.invalid')
        self.git('commit', '--allow-empty', '-qm', 'Synthetic private identity')
        self.assertTrue(guard.audit(self.root, 'history')[1])

    def test_pre_push_checks_outgoing_history(self):
        head = self.git('rev-parse', 'HEAD').decode().strip()
        stream = 'refs/heads/main ' + head + ' refs/heads/main ' + '0' * 40 + '\n'
        with patch.object(guard.sys, 'stdin', io.StringIO(stream)), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(guard.main(['--root', str(self.root), '--pre-push']), 0)
        with patch.object(guard.sys, 'stdin', io.StringIO('malformed')), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(guard.main(['--root', str(self.root), '--pre-push']), 2)

    def test_pre_push_deletion_has_no_outgoing_source(self):
        stream = 'refs/heads/main ' + '0' * 40 + ' refs/heads/main ' + '1' * 40 + '\n'
        with patch.object(guard.sys, 'stdin', io.StringIO(stream)), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(guard.main(['--root', str(self.root), '--pre-push']), 0)

    def test_git_failure_redacts_error_output(self):
        with contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(guard.main(['--root', str(self.root / 'absent'), '--staged']), 2)
        self.assertNotIn(str(self.root), output.getvalue())


    def test_root_and_nested_private_guidance_ignored_without_reading(self):
        private_paths = []
        for relative in ('AGENTS.override.md', 'docs/AGENTS.override.md', 'nested/deeper/AGENTS.override.md'):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Synthetic private instructions, not owner guidance.')
            private_paths.append(path)
            self.git('check-ignore', '-q', '--', relative)
        self.assertEqual(self.git('ls-files', '--', 'AGENTS.override.md', ':(glob)**/AGENTS.override.md'), b'')
        original_read = Path.read_bytes
        def read(path):
            if path in private_paths:
                raise AssertionError('The worktree audit must not read private guidance')
            return original_read(path)
        with patch.object(Path, 'read_bytes', read):
            self.assertEqual(guard.audit(self.root, 'worktree')[1], [])

    def test_force_added_root_and_nested_override_rejected(self):
        for relative in ('AGENTS.override.md', 'docs/AGENTS.override.md'):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Synthetic private instructions.')
            self.git('add', '-f', '--', relative)
        self.assertTrue(guard.audit(self.root, 'staged')[1])
        self.assertTrue(guard.audit(self.root, 'worktree')[1])

    def test_private_override_cannot_be_allowlisted(self):
        paths = {'AGENTS.override.md', 'docs/AGENTS.override.md', 'nested/agents.override.md'}
        with patch.object(guard, 'PUBLIC_PATHS', guard.PUBLIC_PATHS | paths):
            for path in paths:
                self.assertFalse(guard.allowed(path))
                with patch.object(guard, 'git', side_effect=AssertionError('must not read private blob')):
                    self.assertTrue(guard.inspect_entry(self.root, path, '100644', 'fake', '0'))

    def test_deleted_root_and_nested_override_still_block_history_and_push(self):
        for relative in ('AGENTS.override.md', 'docs/AGENTS.override.md'):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Synthetic private instructions.')
            self.git('add', '-f', '--', relative)
        self.git('commit', '-qm', 'Synthetic forbidden instructions')
        self.git('rm', '-q', '--', 'AGENTS.override.md', 'docs/AGENTS.override.md')
        self.git('commit', '-qm', 'Synthetic instruction removal')
        self.assertEqual(guard.audit(self.root, 'staged')[1], [])
        self.assertTrue(guard.audit(self.root, 'history')[1])
        head = self.git('rev-parse', 'HEAD').decode().strip()
        stream = 'refs/heads/main ' + head + ' refs/heads/main ' + '0' * 40 + '\n'
        with patch.object(guard.sys, 'stdin', io.StringIO(stream)), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(guard.main(['--root', str(self.root), '--pre-push']), 1)

    def test_shallow_history_is_not_a_clean_audit(self):
        copy = tempfile.TemporaryDirectory()
        self.addCleanup(copy.cleanup)
        destination = Path(copy.name) / 'synthetic-shallow'
        self.git('clone', '-q', '--no-local', '--depth', '1', str(self.root), str(destination))
        self.assertEqual(guard.git(destination, 'rev-parse', '--is-shallow-repository').strip(), b'true')
        with self.assertRaisesRegex(guard.AuditError, 'shallow'):
            guard.audit(destination, 'history')
        for option in (['--all-history'], ['--outgoing', 'HEAD']):
            with contextlib.redirect_stderr(io.StringIO()) as error:
                self.assertEqual(guard.main(['--root', str(destination)] + option), 2)
            self.assertIn('shallow', error.getvalue())

    def test_explicit_outgoing_range_and_empty_range(self):
        base = self.git('rev-parse', 'HEAD').decode().strip()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(guard.main(['--root', str(self.root), '--outgoing', base]), 0)
        (self.root / 'README.md').write_text('Updated synthetic public source.\n')
        self.git('add', '--', 'README.md')
        self.git('commit', '-qm', 'Synthetic public change')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(guard.main(['--root', str(self.root), '--outgoing', base]), 0)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(guard.main(['--root', str(self.root), '--outgoing', 'missing-synthetic-ref']), 2)

    def test_outgoing_range_rejects_deleted_private_instructions(self):
        base = self.git('rev-parse', 'HEAD').decode().strip()
        path = self.root / 'AGENTS.override.md'
        path.write_text('Synthetic private instructions.')
        self.git('add', '-f', '--', 'AGENTS.override.md')
        self.git('commit', '-qm', 'Synthetic forbidden addition')
        self.git('rm', '-q', '--', 'AGENTS.override.md')
        self.git('commit', '-qm', 'Synthetic forbidden removal')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(guard.main(['--root', str(self.root), '--outgoing', base]), 1)

    def test_detached_head_history_is_also_checked(self):
        self.git('checkout', '--detach', '-q', 'HEAD')
        (self.root / 'private.txt').write_text('Synthetic private content.')
        self.git('add', '--', 'private.txt')
        self.git('commit', '-qm', 'Synthetic detached addition')
        self.assertTrue(guard.audit(self.root, 'history')[1])

    def test_source_archive_excludes_forced_root_and_nested_private_guidance(self):
        project_root = Path(__file__).resolve().parents[1]
        (self.root / '.gitattributes').write_bytes((project_root / '.gitattributes').read_bytes())
        self.git('add', '--', '.gitattributes')
        for relative in ('AGENTS.override.md', 'docs/AGENTS.override.md'):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Synthetic private archive marker.')
            self.git('add', '-f', '--', relative)
        self.git('commit', '-qm', 'Synthetic archive boundary fixture')
        self.assertTrue(guard.audit(self.root, 'staged')[1])
        archive = self.git('archive', '--format=tar', 'HEAD')
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            names = source.getnames()
        self.assertIn('README.md', names)
        self.assertFalse(any(Path(name).name == 'AGENTS.override.md' for name in names))
        self.assertNotIn(b'Synthetic private archive marker.', archive)



if __name__ == '__main__':
    unittest.main()
