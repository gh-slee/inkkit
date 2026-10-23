"""Real helper subprocesses on invented temporary data; no device commands."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

import inkkit_helper as helper


class HelperTests(unittest.TestCase):
    def invoke(self, raw):
        result = subprocess.run([sys.executable, '-B', 'inkkit_helper.py'], input=raw,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                cwd=Path(__file__).resolve().parents[1], timeout=10)
        self.assertEqual(result.stderr, b'')
        return result.returncode, json.loads(result.stdout)

    def test_subprocess_roundtrip_and_protocol(self):
        code, result = self.invoke(b'{"protocol":2,"action":"demo.create"}')
        self.assertEqual(code, 0)
        root = result['data']['root']
        try:
            snapshot = result['data']['snapshot']
            payload = dict(protocol=2, action='config.apply', root=root, expected=snapshot['token'],
                           changes={'lineHeightPercent': 112})
            code, result = self.invoke(json.dumps(payload).encode())
            self.assertEqual(code, 0)
            self.assertEqual(result['data']['snapshot']['values']['lineHeightPercent'], 112)
        finally:
            shutil.rmtree(root)

    def test_malformed_protocol_action_credentials_and_real_root_fail_safely(self):
        for raw in (b'{}', b'{"protocol":true,"action":"demo.create"}',
                    b'{"protocol":999,"action":"demo.create"}',
                    b'{"protocol":2,"action":"erase"}',
                    b'{"protocol":2,"action":"demo.create","password":"example-secret"}',
                    b'{"protocol":2,"action":"config.read","root":"/Volumes/EXAMPLE"}',
                    b'{"protocol":2,"action":"config.read","root":[]}',
                    b'{"protocol":2,"protocol":2}', b' ' * 65537):
            code, result = self.invoke(raw)
            self.assertEqual(code, 1)
            self.assertFalse(result['ok'])
            public = json.dumps(result)
            self.assertNotIn('example-secret', public)
            self.assertNotIn('/Volumes/EXAMPLE', public)
            self.assertNotIn('Traceback', public)

    def test_selftest_roundtrip(self):
        result = helper.self_test()
        self.assertTrue(result['synthetic_roundtrip'])
        self.assertEqual(len(result['snapshot']['fields']), 148)
        self.assertEqual(result['differences'][0]['after'], 115)


if __name__ == '__main__':
    unittest.main()
