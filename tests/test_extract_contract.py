"""The release survey reads an invented temporary git repository only."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import extract_crossink_contract as extract  # noqa: E402


class ExtractContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-q')
        self.commit('v1.0.0', {'src/CrossPointSettings.cpp': 'doc["alpha"] = 1; "/.crosspoint/example-settings.json"',
                               'platformio.ini': '[env:default]\n'})
        self.commit('v1.1.0-rc', {'src/SettingsList.cpp': 'add(Toggle("betaOption"));'})
        self.commit('v1.1.0', {'src/SettingsList.cpp': 'add(Toggle("betaOption"));',
                               'src/ExampleStore.cpp': '"/.crosspoint/example.json"',
                               'platformio.ini': '[env:default]\n[env:example-reader]\n'})

    def git(self, *args):
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Example', '-c', 'user.email=example@example.invalid',
                        *args], check=True, capture_output=True)

    def commit(self, tag, files):
        for name, text in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.git('add', '-A')
        self.git('commit', '-q', '-m', tag)
        self.git('tag', tag)

    def run_main(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = extract.main(['--repo', str(self.repo), *args])
        return code, output.getvalue()

    def test_stable_tags_skip_release_candidates_and_report_changes(self):
        self.assertEqual(extract.stable_tags(self.repo), ['v1.0.0', 'v1.1.0'])
        code, output = self.run_main('--compare')
        self.assertEqual(code, 0)
        baseline, change = json.loads(output)
        self.assertEqual((baseline['change'], baseline['settings_keys'], baseline['sdk']), ('baseline', ['alpha'], ''))
        self.assertEqual(change['since'], 'v1.0.0')
        self.assertEqual(change['settings_keys'], dict(added=['betaOption'], removed=[]))
        self.assertEqual(change['stores'], dict(added=['example.json'], removed=[]))
        self.assertEqual(change['build_environments'], dict(added=['example-reader'], removed=[]))

    def test_unknown_tags_and_non_repositories_fail_without_output(self):
        self.assertEqual(self.run_main('v9.9.9'), (2, ''))
        with tempfile.TemporaryDirectory() as empty, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(extract.main(['--repo', empty]), 2)


if __name__ == '__main__':
    unittest.main()
