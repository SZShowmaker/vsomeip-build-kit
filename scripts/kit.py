#!/usr/bin/env python3
"""Reproducible vSomeIP SDK builder. Python >= 3.9; no third-party Python modules."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'sources.lock.json').read_text())
WINDOWS = os.name == 'nt'
TARGETS = ('native', 'aarch64-linux', 'windows-x64')


def run(args, cwd=None, env=None):
    args = [str(x) for x in args]
    print('+', subprocess.list2cmdline(args), flush=True)
    subprocess.run(args, cwd=cwd, env=env, check=True)


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def windows_env():
    if not WINDOWS:
        raise RuntimeError('windows-x64 must build with native Windows Python and MSVC 2022')
    vswhere = Path(os.environ['ProgramFiles(x86)']) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    vs = Path(subprocess.check_output([str(vswhere), '-latest', '-products', '*', '-version', '[17,18)', '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'], text=True).strip())
    vcvars = vs / 'VC/Auxiliary/Build/vcvars64.bat'
    if not vcvars.is_file():
        raise RuntimeError('Install Visual Studio 2022 Build Tools: C++ x64, Windows SDK, CMake tools')
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / 'env.cmd'
        script.write_text('@echo off\ncall "' + str(vcvars) + '" >nul\nif errorlevel 1 exit /b 1\nset\n')
        raw = subprocess.check_output(['cmd.exe', '/d', '/u', '/c', str(script)], cwd=tmp)
        for line in raw.decode('utf-16-le').splitlines():
            if '=' in line and not line.startswith('='):
                k, v = line.split('=', 1)
                os.environ[k] = v
    os.environ['VSK_VCVARS'] = str(vcvars.with_name('vcvarsall.bat'))
    for sub in ('CMake/bin', 'Ninja'):
        path = vs / 'Common7/IDE/CommonExtensions/Microsoft/CMake' / sub
        os.environ['PATH'] = str(path) + os.pathsep + os.environ['PATH']


def config():
    path = ROOT / 'config.local.json'
    return json.loads(path.read_text()) if path.exists() else {}


def target_setup(target):
    if target == 'windows-x64':
        windows_env()
        return ['-DCMAKE_CXX_FLAGS=-DBOOST_ALL_NO_LIB']
    if WINDOWS:
        raise RuntimeError('Use Linux for native/aarch64-linux builds')
    settings = config().get(target, {})
    if target == 'native':
        return ['-DCMAKE_C_COMPILER=' + settings.get('cc', 'gcc-11'), '-DCMAKE_CXX_COMPILER=' + settings.get('cxx', 'g++-11')]
    tc = Path(settings.get('toolchain_root', ''))
    prefix = settings.get('compiler_prefix', 'aarch64-none-linux-gnu')
    cxx = tc / 'bin' / (prefix + '-g++')
    if not cxx.is_file():
        raise RuntimeError('Set aarch64-linux.toolchain_root in config.local.json (see config.example.json)')
    toolchain = ROOT / 'out' / target / 'toolchain.cmake'
    toolchain.parent.mkdir(parents=True, exist_ok=True)
    toolchain.write_text('set(CMAKE_SYSTEM_NAME Linux)\nset(CMAKE_SYSTEM_PROCESSOR aarch64)\n'
        + 'set(CMAKE_C_COMPILER "' + (tc / 'bin' / (prefix + '-gcc')).as_posix() + '")\n'
        + 'set(CMAKE_CXX_COMPILER "' + cxx.as_posix() + '")\n'
        + 'set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)\n')
    return ['-DCMAKE_TOOLCHAIN_FILE=' + str(toolchain)]


def fetch():
    cache = ROOT / '.cache'
    cache.mkdir(exist_ok=True)
    for dep in LOCK.values():
        archive = cache / dep['archive']
        if not archive.exists():
            part = archive.with_suffix(archive.suffix + '.part')
            run(['curl.exe' if WINDOWS else 'curl', '-fL', '--retry', '4', '--retry-all-errors', '--connect-timeout', '20', '--max-time', '900', dep['url'], '-o', part])
            if digest(part) != dep['sha256']:
                raise RuntimeError('Source checksum mismatch: ' + str(part))
            part.replace(archive)
        if digest(archive) != dep['sha256']:
            raise RuntimeError('Source checksum mismatch: ' + str(archive))
        print('verified', archive.name, flush=True)


def extract(archive, dest):
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                resolved = (Path(tmp) / member.name).resolve()
                if not resolved.is_relative_to(Path(tmp).resolve()) or member.issym() or member.islnk() or member.isdev():
                    raise RuntimeError('Unsafe archive member: ' + member.name)
            # Documentation has paths beyond legacy Windows MAX_PATH; no build inputs live there.
            members = [m for m in tf.getmembers() if not ({'doc', 'html'} & set(Path(m.name).parts[1:]))]
            tf.extractall(tmp, members=members)
        entries = list(Path(tmp).iterdir())
        if len(entries) != 1 or not entries[0].is_dir():
            raise RuntimeError('Source archive must contain one directory')
        entries[0].rename(dest)


def sdk_path(target):
    return ROOT / 'out' / target / 'sdk'


def apply_patches(source):
    # Exact replacements are reviewed in patches.json and fail closed on source drift.
    for patch in json.loads((ROOT / 'patches.json').read_text()):
        path = source / patch['file']
        text = path.read_text()
        if patch['after'] in text:
            continue
        if text.count(patch['before']) != 1:
            raise RuntimeError('Patch preimage mismatch: ' + patch['id'])
        path.write_text(text.replace(patch['before'], patch['after']))


def build(target, jobs):
    opts = target_setup(target)
    fetch()
    work = ROOT / 'out' / target
    sdk = sdk_path(target)
    boost = work / 'sources' / 'boost'
    source = work / 'sources' / 'vsomeip'
    for dep, dest in (('boost', boost), ('vsomeip', source)):
        extract(ROOT / '.cache' / LOCK[dep]['archive'], dest)
    apply_patches(source)
    boost_install = work / 'boost'
    marker = boost_install / '.complete'
    boost_identity = {'source':LOCK['boost'], 'target':target, 'settings':config().get(target,{}), 'msvc':os.environ.get('VCToolsVersion','')}
    previous = marker.read_text().strip() if marker.exists() else ''
    if previous and previous != 'complete' and json.loads(previous) != boost_identity:
        raise RuntimeError('Boost compiler/source configuration changed; move out/'+target+' aside and rebuild')
    if not previous or previous == 'complete':
        if WINDOWS:
            if not (boost/'b2.exe').exists():
                run(['cmd.exe', '/d', '/c', 'bootstrap.bat'], cwd=boost)
            toolset = 'msvc-14.3'
            usercfg = work / 'boost-user-config.jam'
            setup = Path(os.environ['VSK_VCVARS']).as_posix()
            usercfg.write_text('using msvc : 14.3 : : <setup>"' + setup + '" <rewrite-setup-scripts>off ;\n')
            (boost/'project-config.jam').write_text('# Explicit toolset is configured by --user-config.\n')
            extra = ['define=_WIN32_WINNT=0x0600', '--user-config='+str(usercfg), '--reconfigure']
        else:
            if not (boost/'b2').exists():
                run(['sh', 'bootstrap.sh', '--with-libraries=filesystem', '--with-toolset=gcc'], cwd=boost)
            cc = config().get('native', {}).get('cxx', 'g++-11')
            if target == 'aarch64-linux':
                c = config()['aarch64-linux']
                cc = str(Path(c['toolchain_root']) / 'bin' / (c.get('compiler_prefix', 'aarch64-none-linux-gnu') + '-g++'))
            usercfg = work / 'boost-user-config.jam'
            usercfg.write_text('using gcc : kit : "' + cc + '" ;\n')
            toolset = 'gcc-kit'
            extra = ['--user-config=' + str(usercfg), 'cxxflags=-fPIC', 'target-os=linux']
            if target == 'aarch64-linux':
                extra += ['architecture=arm', 'abi=aapcs']
        run([boost / ('b2.exe' if WINDOWS else 'b2'), '-j' + str(jobs), '--with-filesystem', '--prefix=' + str(boost_install), '--layout=system', 'variant=release', 'link=static', 'runtime-link=shared', 'threading=multi', 'address-model=64', 'cxxstd=17', 'toolset=' + toolset] + extra + ['install'], cwd=boost)
        marker.write_text(json.dumps(boost_identity,sort_keys=True)+'\n')
    build_dir = work / 'build'
    run(['cmake', '-S', source, '-B', build_dir, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=' + str(sdk), '-DCMAKE_INSTALL_RPATH=$ORIGIN', '-DCMAKE_EXPORT_PACKAGE_REGISTRY=OFF', '-DDISABLE_DLT=ON', '-DDISABLE_SYSTEMD=ON', '-DBOOST_ROOT=' + str(boost_install), '-DBoost_NO_SYSTEM_PATHS=ON', '-DBoost_NO_BOOST_CMAKE=ON', '-DBoost_USE_STATIC_LIBS=ON', '-DINSTALL_CMAKE_DIR:STRING=lib/cmake/vsomeip3'] + opts)
    run(['cmake', '--build', build_dir, '--parallel', jobs, '--target', 'all'])
    run(['cmake', '--install', build_dir])
    if not WINDOWS:
        strip = 'strip'
        if target == 'aarch64-linux':
            tc = config()['aarch64-linux']
            strip = str(Path(tc['toolchain_root'])/'bin'/(tc.get('compiler_prefix','aarch64-none-linux-gnu')+'-strip'))
        for library in (sdk/'lib').glob('*.so.*'):
            if not library.is_symlink():
                run([strip, '--strip-unneeded', library])
    licenses = sdk / 'licenses'
    licenses.mkdir(exist_ok=True)
    shutil.copy2(source / 'LICENSE', licenses / 'vsomeip-MPL-2.0.txt')
    modified = licenses/'source-modifications'
    modified.mkdir(exist_ok=True)
    shutil.copy2(source/'CMakeLists.txt',modified/'CMakeLists.txt')
    shutil.copy2(boost / 'LICENSE_1_0.txt', licenses / 'boost-BSL-1.0.txt')
    shutil.copy2(ROOT / 'sources.lock.json', sdk / 'sources.lock.json')
    shutil.copy2(ROOT / 'patches.json', sdk / 'patches.json')
    shutil.copytree(ROOT / 'examples', sdk / 'examples', dirs_exist_ok=True)
    shutil.copytree(ROOT/'docs',sdk/'docs',dirs_exist_ok=True)
    for name in ('docs/SDK.md',):
        if (ROOT / name).exists():
            dest = sdk / ('README.md' if name.endswith('SDK.md') else 'BUILD_KIT.md')
            shutil.copy2(ROOT / name, dest)
    # Public vSomeIP headers use only the standard library; Boost is linked privately/static.
    pc = sdk / 'lib/pkgconfig/vsomeip3.pc'
    if pc.exists():
        content = pc.read_text().splitlines()
        replacements = {'prefix':'${pcfiledir}/../..', 'exec_prefix':'${prefix}', 'libdir':'${prefix}/lib', 'includedir':'${prefix}/include'}
        pc.write_text('\n'.join(x.split('=',1)[0]+'='+replacements[x.split('=',1)[0]] if x.split('=',1)[0] in replacements else x for x in content)+'\n')
    manifest = {'target': target, 'sources': LOCK, 'configuration': 'Release', 'cpp': 17, 'boost_link': 'static', 'runtime': '/MD' if WINDOWS else 'dynamic libstdc++', 'built_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    compiler = 'cl' if WINDOWS else config().get('native', {}).get('cxx', 'g++-11')
    if target == 'aarch64-linux':
        tc = config()['aarch64-linux']
        compiler = str(Path(tc['toolchain_root'])/'bin'/(tc.get('compiler_prefix','aarch64-none-linux-gnu')+'-g++'))
    manifest['compiler'] = subprocess.run([compiler] if WINDOWS else [compiler, '--version'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout.splitlines()[0]
    manifest['patches_sha256'] = digest(ROOT / 'patches.json')
    manifest['builder_sha256'] = digest(Path(__file__))
    (sdk / 'build-info.json').write_text(json.dumps(manifest, indent=2) + '\n')
    checksums = {p.relative_to(sdk).as_posix(): digest(p) for p in sorted(sdk.rglob('*')) if p.is_file() and p.name != 'manifest.sha256.json'}
    (sdk/'manifest.sha256.json').write_text(json.dumps(checksums,indent=2)+'\n')
    print('SDK:', sdk)


def example(target, jobs, sdk=None, build_dir=None):
    opts = target_setup(target)
    prefix = Path(sdk).resolve() if sdk else sdk_path(target)
    output = Path(build_dir).resolve() if build_dir else ROOT / 'out' / target / 'example'
    run(['cmake', '-S', ROOT / 'examples/smoke', '-B', output, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_PREFIX_PATH=' + str(prefix)] + opts)
    run(['cmake', '--build', output, '--parallel', jobs])
    print('Example:', output)


def package(target):
    sdk = sdk_path(target)
    if not (sdk / 'build-info.json').exists():
        raise RuntimeError('Build SDK before packaging')
    from verify_sdk import verify
    verify(sdk)
    output = ROOT / 'out/packages'
    output.mkdir(exist_ok=True)
    base = output / ('vsomeip-3.6.4-' + target)
    # Tar preserves the Linux SONAME symlinks. Windows zip is easier to extract natively.
    if target == 'windows-x64':
        archive = Path(shutil.make_archive(str(base), 'zip', root_dir=sdk))
    else:
        archive = Path(str(base) + '.tar.gz')
        with tarfile.open(archive, 'w:gz') as tf:
            tf.add(sdk, arcname='sdk')
    archive.with_name(archive.name + '.sha256').write_text(digest(archive) + '  ' + archive.name + '\n')
    print(archive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('fetch', help='Download and SHA256 verify pinned sources')
    for name in ('doctor', 'build', 'prefix', 'example', 'package'):
        p = sub.add_parser(name)
        p.add_argument('--target', choices=TARGETS, default='windows-x64' if WINDOWS else 'native')
        if name in ('build', 'example'):
            p.add_argument('--jobs', type=int, default=4)
        if name == 'example':
            p.add_argument('--sdk', help='Use a relocated SDK')
            p.add_argument('--build-dir', help='Separate consumer build directory')
    args = parser.parse_args()
    if getattr(args, 'jobs', 1) < 1:
        parser.error('--jobs must be positive')
    if args.command == 'fetch':
        fetch()
    elif args.command == 'build':
        build(args.target, args.jobs)
    elif args.command == 'example':
        example(args.target, args.jobs, args.sdk, args.build_dir)
    elif args.command == 'prefix':
        print(sdk_path(args.target))
    elif args.command == 'package':
        package(args.target)
    else:
        opts = target_setup(args.target)
        for name in ('cmake', 'ninja', 'cl' if WINDOWS else 'g++-11', 'curl.exe' if WINDOWS else 'curl'):
            tool = shutil.which(name)
            if not tool:
                raise RuntimeError('Missing tool: ' + name)
            print(name, tool)
        print('Target:', args.target, opts)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError, ValueError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
