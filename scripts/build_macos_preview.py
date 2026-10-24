#!/usr/bin/env python3
"""Build a local, ad-hoc-signed SwiftUI configuration preview. Never publish it.

Uses the executing python.org CPython 3.12 framework. Copies selected standard
library source and system-linked extensions only, never site-packages or a checkout.
This feasibility spike is not a maintained production runtime distribution.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import sysconfig

ROOT = Path(__file__).resolve().parents[1]
CORE_INPUTS = ('inkkit_config.py', 'inkkit_helper.py', 'inkkit_schema.py', 'inkkit_codec.py',
               'crossink_profile.py', 'inkkit_volume.py', 'disk_safety.py', 'inkkit_snapshots.py')
BUILD_INPUTS = CORE_INPUTS + ('macos/InkKitApp.swift', 'macos/Info.plist',
                             'xteink_sd_migrate.py', 'LICENSE', 'scripts/build_macos_preview.py')


def run(*command):
    return subprocess.check_output(command, stderr=subprocess.STDOUT, text=True)


def software_version(root):
    tree = ast.parse((root / 'xteink_sd_migrate.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                return value
    raise ValueError('Missing software version source.')


def dependencies(path, arch):
    output = run('/usr/bin/otool', '-arch', arch, '-L', str(path))
    return {line.strip().split(' (', 1)[0] for line in output.splitlines()[1:] if ' (compatibility version ' in line}


def system_dependency(path):
    return path.startswith(('/usr/lib/', '/System/Library/'))


def copy_macho(source, destination, arch):
    destination.parent.mkdir(parents=True, exist_ok=True)
    architectures = run('/usr/bin/lipo', '-archs', str(source)).strip().split()
    if arch not in architectures:
        raise ValueError('The local Python runtime does not support this build architecture.')
    if len(architectures) > 1:
        run('/usr/bin/lipo', str(source), '-thin', arch, '-output', str(destination))
    else:
        shutil.copyfile(source, destination)
    destination.chmod(0o755)


def copy_runtime(destination, arch):
    prefix = Path(sys.base_prefix)
    if sys.version_info[:2] != (3, 12) or prefix.parent.name != 'Versions' or prefix.parent.parent.name != 'Python.framework':
        raise ValueError('Use a local python.org CPython 3.12 framework for this development spike.')
    # The framework's bin/python is a launcher that spawns Python.app at a
    # framework-relative path. Bundle the actual interpreter, not that launcher.
    executable = prefix / 'Resources' / 'Python.app' / 'Contents' / 'MacOS' / 'Python'
    library = prefix / 'Python'
    stdlib = Path(sysconfig.get_path('stdlib'))
    if stdlib != prefix / 'lib' / 'python3.12':
        raise ValueError('Unexpected Python standard-library layout.')
    python = destination / 'bin' / 'python3'
    dylib = destination / 'lib' / 'libpython3.12.dylib'
    if any(not system_dependency(dep) and dep != str(library)
           for binary in (executable, library) for dep in dependencies(binary, arch)):
        raise ValueError('The runtime has an unsupported external library dependency.')
    copy_macho(executable, python, arch)
    copy_macho(library, dylib, arch)
    run('/usr/bin/install_name_tool', '-change', str(library),
        '@executable_path/../lib/libpython3.12.dylib', str(python))
    run('/usr/bin/install_name_tool', '-id', '@rpath/libpython3.12.dylib', str(dylib))
    target = destination / 'lib' / 'python3.12'
    target.mkdir(parents=True)
    # Exact stdlib module names exclude user-installed sitecustomize and packages.
    copied = 0
    for name in sorted(sys.stdlib_module_names):
        package = stdlib / name
        module = stdlib / (name + '.py')
        if package.is_dir() and not package.is_symlink():
            for source in sorted(package.rglob('*.py')):
                if source.is_symlink() or any(part in ('__pycache__', 'test', 'tests') for part in source.relative_to(package).parts):
                    continue
                output = target / source.relative_to(stdlib)
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, output)
                copied += 1
        elif module.is_file() and not module.is_symlink():
            shutil.copyfile(module, target / module.name)
            copied += 1
    extension_dir = target / 'lib-dynload'
    extension_dir.mkdir()
    extensions = []
    for source in sorted((stdlib / 'lib-dynload').glob('*.so')):
        if source.is_symlink() or not all(system_dependency(dep) for dep in dependencies(source, arch)):
            continue  # No OpenSSL/Tk or other host-framework library fallback.
        copy_macho(source, extension_dir / source.name, arch)
        extensions.append(source.name)
    license_path = stdlib / 'LICENSE.txt'
    if not license_path.is_file():
        raise ValueError('The Python license text is required.')
    shutil.copyfile(license_path, destination / 'PYTHON-LICENSE.txt')
    for binary in [dylib, *sorted(extension_dir.glob('*.so')), python]:
        run('/usr/bin/codesign', '--force', '--sign', '-', str(binary))
    return dict(version=platform.python_version(), architecture=arch, standard_library_files=copied,
                extensions=extensions, production_runtime=False,
                source_interpreter_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
                source_library_sha256=hashlib.sha256(library.read_bytes()).hexdigest())


def build(output):
    if sys.platform != 'darwin':
        raise ValueError('The preview builder requires macOS.')
    arch = platform.machine()
    if arch not in ('arm64', 'x86_64'):
        raise ValueError('Unsupported local build architecture.')
    output = output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = output / 'InkKit Preview.app'
    if app.exists():
        raise ValueError('The app already exists. Choose a fresh output directory; builds never overwrite artifacts.')
    contents = app / 'Contents'
    resources = contents / 'Resources'
    binary_dir = contents / 'MacOS'
    core = resources / 'core'
    core.mkdir(parents=True)
    binary_dir.mkdir()
    version = software_version(ROOT)
    info = plistlib.loads((ROOT / 'macos/Info.plist').read_bytes())
    info['CFBundleShortVersionString'] = version
    (contents / 'Info.plist').write_bytes(plistlib.dumps(info))
    for relative in CORE_INPUTS:
        shutil.copyfile(ROOT / relative, core / relative)
    shutil.copyfile(ROOT / 'LICENSE', resources / 'INKKIT-LICENSE.txt')
    runtime = copy_runtime(resources / 'runtime', arch)
    # Keep compiler caches in ignored output, not protected home directories.
    cache = output / 'module-cache'
    cache.mkdir()
    run('/usr/bin/xcrun', 'swiftc', '-swift-version', '5', '-parse-as-library',
        '-target', arch + '-apple-macosx14.0', '-module-cache-path', str(cache), '-O',
        str(ROOT / 'macos/InkKitApp.swift'), '-o', str(binary_dir / 'InkKit'))
    hashes = {relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() for relative in BUILD_INPUTS}
    metadata = dict(format='inkkit-preview-build-v1', software_version=version, preview=True,
                    real_card_access=True, runtime=runtime, inputs=hashes)
    (resources / 'BuildInfo.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    run('/usr/bin/codesign', '--force', '--sign', '-', str(app))
    run('/usr/bin/codesign', '--verify', '--deep', '--strict', str(app))
    # Launch the native executable, which in turn uses the bundled helper/runtime.
    result = json.loads(run(str(binary_dir / 'InkKit'), '--self-test'))
    if not result.get('ok'):
        raise ValueError('The app integration self-test failed.')
    return app, metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'work' / 'macos-preview')
    args = parser.parse_args(argv)
    try:
        app, metadata = build(args.output)
        print('Local developer preview built: ' + str(app))
        print('Native launcher + bundled Python synthetic apply/restore: PASS')
        print('Architecture: ' + metadata['runtime']['architecture'])
        print('Ad-hoc signature only; not notarized or approved for public distribution.')
        return 0
    except (OSError, ValueError, subprocess.SubprocessError):
        print('Preview build failed. Check the local CPython framework, Swift tools and fresh output directory.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
