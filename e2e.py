"""Main end-to-end testing script for fuzzing monerod RPC endpoints."""

import argparse
import os
import subprocess
import signal
import time
import shutil

import e2e_fuzzer

END_TO_END_BUILD_ADDITINS = """# End-to-end build script
cd $SRC/monero/monero

export BOOST_ROOT=/src/monero/boost_1_70_0
export OPENSSL_ROOT_DIR=/src/monero/openssl-1.1.1g

sed -i -e 's/include(FindCcache)/# include(FindCcache)/' CMakeLists.txt
git submodule init
git submodule update

# Build monerod
mkdir -p $SRC/monero/monero/build2
cd $SRC/monero/monero/build2
export CXXFLAGS="$CXXFLAGS --coverage -fprofile-instr-generate -fcoverage-mapping"
cmake -D OSSFUZZ=ON -D STATIC=ON -D BUILD_TESTS=ON -D USE_LTO=OFF -D SANITIZE=ON \
-D ARCH="default" -DCMAKE_CXX_FLAGS="$CXXFLAGS" -DCMAKE_EXE_LINKER_FLAGS="--coverage" ..
make -j$(nproc) -C src/daemon
cp bin/monerod $OUT/monerod
mkdir -p $SRC/monero/monero/tools
cp -r $SRC/monero_rpc_serialiser $SRC/monero/monero/tools

# Build the serialiser
mkdir -p $SRC/monero/monero/build3
cd $SRC/monero/monero/build3
echo "add_subdirectory(tools/monero_rpc_serialiser)" >> $SRC/monero/monero/CMakeLists.txt
export CXXFLAGS="$CXXFLAGS -fPIC"
cmake -D OSSFUZZ=ON -D STATIC=ON -D BUILD_TESTS=ON -D USE_LTO=OFF -D SANITIZE=ON -D ARCH="default" ..
make -j$(nproc) monero_rpc_serialiser
cp $SRC/monero/monero/build3/tools/monero_rpc_serialiser/monero_rpc_serialiser $OUT/monero_rpc_serialiser
"""


def build_end_to_end_setup(ossfuzzdir: str, workdir: str, proj: str) -> str:
    """Builds monerod and the RPC serialiser for end-to-end testing."""
    if not os.path.isdir(ossfuzzdir):
        raise NotADirectoryError(f'OSS-Fuzz directory not found: {ossfuzzdir}')

    os.makedirs(workdir, exist_ok=True)

    # Prepare the OSS-Fuzz project:
    # - overwrite the build script
    # - overwrite the dockerfile
    # - add the serialiser code.
    build_path = os.path.join(ossfuzzdir, 'projects', proj, 'build.sh')
    with open(build_path, 'r', encoding='utf-8') as f:
        existing_build_script = f.read()
    if '# End-to-end build additions' not in existing_build_script:
        with open(build_path, 'w', encoding='utf-8') as f:
            f.write('\n' + END_TO_END_BUILD_ADDITINS + '\n')

    docker_path = os.path.join(ossfuzzdir, 'projects', proj, 'Dockerfile')
    with open(docker_path, 'r', encoding='utf-8') as f:
        existing_dockerfile = f.read()
    if 'COPY monero_rpc_serialiser $SRC/monero_rpc_serialiser' not in existing_dockerfile:
        with open(docker_path, 'a', encoding='utf-8') as f:
            f.write('\n' +
                    'COPY monero_rpc_serialiser $SRC/monero_rpc_serialiser\n')

    rpc_serialiser_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'monero_rpc_serialiser')
    target_rpc_serialiser_path = os.path.join(ossfuzzdir, 'projects', proj,
                                              'monero_rpc_serialiser')
    shutil.copytree(src=rpc_serialiser_path,
                    dst=target_rpc_serialiser_path,
                    dirs_exist_ok=True)

    # Build the set up using OSS-Fuzz's helper script.
    subprocess.check_call(f'python3 infra/helper.py build_fuzzers {proj}',
                          shell=True,
                          cwd=ossfuzzdir)

    # Copy the built monerod and serialiser to the workdir
    monerod_path = os.path.join(ossfuzzdir, 'build', 'out', proj, 'monerod')
    target_monerod_path = os.path.join(workdir, 'monerod')
    if os.path.isfile(monerod_path):
        shutil.copy(monerod_path, target_monerod_path)

    serialiser_path = os.path.join(ossfuzzdir, 'build', 'out', proj,
                                   'monero_rpc_serialiser')
    target_serialiser_path = os.path.join(workdir, 'monero_rpc_serialiser')
    if os.path.isfile(serialiser_path):
        shutil.copy(serialiser_path, target_serialiser_path)

    return target_monerod_path


def generate_coverage_html_report(workdir) -> str:
    """Run llvm-cov to generate HTML coverage report. This done by
    running coverage collection from inside the OSS-Fuzz docker build
    image. As such, the monero-rpc docker container must be available."""
    workdir = os.path.abspath(workdir)
    coverage_dir = os.path.join(workdir, 'coverage')
    os.makedirs(coverage_dir, exist_ok=True)

    # Get current UID and GID for file ownership adjustment
    uid = os.getuid()
    gid = os.getgid()

    # Define the command script that will be run inside the container
    script = ('cd $SRC/monero/monero && '
              'git submodule init && '
              'git submodule update && '
              'llvm-profdata merge -sparse $(find /data -name "*.profraw") '
              '-o /data/monerod.profdata && '
              'llvm-cov show '
              '-format=html '
              '-output-dir=/data/coverage '
              '-Xdemangler c++filt '
              '-instr-profile=/data/monerod.profdata '
              '/data/monerod && '
              f'chown -R {uid}:{gid} /data/coverage')

    # Run coverage generation in docker image
    command = [
        'docker', 'run', '--rm', '-it', '-v', f'{workdir}:/data',
        'gcr.io/oss-fuzz/monero-rpc', 'bash', '-c', script
    ]

    subprocess.check_call(command)

    return coverage_dir


def start_monerod(monerod_path, workdir, index):
    """Starts the monerod process so it's ready for receiving RPC calls."""
    # Set LLVM_PROFILE_FILE for coverage output
    env = os.environ.copy()
    env['LLVM_PROFILE_FILE'] = os.path.join(workdir, f'monerod{index}.profraw')

    log_path = os.path.join(workdir, f'monerod{index}.log')
    log_file = open(log_path, 'w', encoding='utf-8')

    # Start monerod in the foreground
    print('Starting monerod')
    monerod_proc = subprocess.Popen([
        monerod_path, '--offline', '--regtest', '--rpc-bind-port', '38081',
        '--confirm-external-bind', '--disable-rpc-ban'
    ],
                                    env=env,
                                    stdout=log_file,
                                    stderr=log_file)
    print('Sleeping 45 sec')

    # Wait for monerod initialise
    time.sleep(45)
    print('Done sleeping')

    return monerod_proc, log_file


def stop_monerod(monerod_proc, log_file):
    """Stops the monerod process by first sending a SIGINT
    and if it does not terminate, sending a SIGKILL."""
    print('stopping monerod')
    if monerod_proc is not None and monerod_proc.poll() is None:
        print('sending SIGINT signal')
        # Try kill monerod by SIGINT first
        monerod_proc.send_signal(signal.SIGINT)

        try:
            print('Waiting 60 sec for monerod to terminate')
            monerod_proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            print('Monerod did not terminate in time, sending SIGKILL')
            # Monerod failed to terminiate by SIGINT
            # Force killing the monerod
            monerod_proc.kill()

    if log_file:
        log_file.close()
    print('Monerod stopped')


def dump_called_functions(target_dir, results):
    """Dump the functions called count to a file."""
    # The results is a dictionary where the key is the function name
    # and the value is a tuple of (success_count, fail_count).
    results = dict(
        sorted(results.items(),
               key=lambda item:
               (item[1][0] + item[1][1], item[1][0], item[1][1]),
               reverse=True))

    called_func = [
        func for func, (success, fail) in results.items()
        if (success + fail) > 0
    ]

    func_count_path = os.path.join(target_dir, 'func_call_count.log')
    with open(func_count_path, 'w', encoding='utf-8') as file:
        file.write(f'#Function calls reached: {len(called_func)}\n')
        file.write(f'Function calls reached: {called_func}\n')
        for func, (success, fail) in results.items():
            file.write(f'{func}: \n')
            file.write(f'    Total: {success + fail}\n')
            file.write(f'    Success: {success}\n')
            file.write(f'    Fail: {fail}\n')


def parse_args():
    """CLI interface for the script."""
    # Arguments
    parser = argparse.ArgumentParser(
        description='E2e for manual fuzzing of monero-rpc project')
    parser.add_argument('--oss-fuzz', required=True, help='OSS-Fuzz directory')
    parser.add_argument(
        '--workdir',
        default='./work',
        help='Directory to copy final outputs (default: ./work)')
    parser.add_argument('--proj',
                        default='monero-rpc',
                        help='Project name used for the monerod build')
    parser.add_argument('--round',
                        type=int,
                        default=1000000,
                        help='Number of fuzzing round to run.')
    parser.add_argument('--debug',
                        action='store_true',
                        help='Enable debug mode')
    parser.add_argument('--not-rebuild-monerod',
                        action='store_true',
                        help='Stop rebuild of monerod')
    parser.add_argument('--duration',
                        type=int,
                        default=0,
                        help='Seconds to fuzz in total')
    args = parser.parse_args()
    return args


def main():
    """Main function to run the end-to-end fuzzing."""

    args = parse_args()

    # Extract arguments
    abs_workdir = os.path.abspath(args.workdir)

    rpc_call_stats = {}
    log_file = None
    monerod_proc = None

    # Build and prepare monerod from OSS-Fuzz or reuse built monerod in workdir
    if args.not_rebuild_monerod:
        monerod_path = os.path.join(abs_workdir, 'monerod')
    else:
        monerod_path = build_end_to_end_setup(os.path.abspath(args.oss_fuzz),
                                              abs_workdir, args.proj)

    # Launch the monero server and start fuzzing.
    monerod_proc, log_file = start_monerod(monerod_path, abs_workdir, 0)

    # Perform the actual fuzzing.
    rpc_call_stats = e2e_fuzzer.fuzz(args.round, abs_workdir, args.debug,
                                     rpc_call_stats, args.duration)

    # Ensure monerod is stopped
    stop_monerod(monerod_proc, log_file)

    # Dumping functions called count.
    dump_called_functions(abs_workdir, rpc_call_stats)

    # Process coverage report
    coverage_dir = generate_coverage_html_report(abs_workdir)
    print(f'Coverage report available at: {coverage_dir}')
    print('Finished end-to-end fuzzing!')


if __name__ == '__main__':
    main()
