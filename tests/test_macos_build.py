"""Packaging policy tests; no recursive checkout copies or runtime installation."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('macos_builder', Path(__file__).resolve().parents[1] / 'scripts/build_macos_preview.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class MacBuildTests(unittest.TestCase):
    def test_only_named_sources_are_payload_inputs(self):
        self.assertEqual(builder.CORE_INPUTS, ('inkkit_config.py', 'inkkit_helper.py'))
        for path in builder.BUILD_INPUTS:
            self.assertTrue((builder.ROOT / path).is_file())
            self.assertNotIn('backup', path)
            self.assertNotIn('override', path)

    def test_framework_and_home_dependencies_not_treated_as_system(self):
        self.assertTrue(builder.system_dependency('/usr/lib/libSystem.B.dylib'))
        self.assertTrue(builder.system_dependency('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation'))
        self.assertFalse(builder.system_dependency('/Library/Frameworks/Python.framework/Python'))
        self.assertFalse(builder.system_dependency('/tmp/example/library.dylib'))
        self.assertFalse(builder.system_dependency('@rpath/example.dylib'))

    def test_version_comes_from_existing_constant_without_import(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'xteink_sd_migrate.py'
            path.write_text("raise RuntimeError('must not execute')\n__version__ = '2.3.4'\n")
            self.assertEqual(builder.software_version(Path(root)), '2.3.4')


if __name__ == '__main__':
    unittest.main()
