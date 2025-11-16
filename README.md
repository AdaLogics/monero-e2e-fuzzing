# Fuzzing Monerod RPC endpoints by setting up Local Monerod server

This project is used for dumb end-to-end fuzzing of Monero. The goal is to launch a monero
server in the way one would normally launch this server, and then send an arbitrary number of
random RPC requests to this server in order to stress test it. More specifically,
the goal of this project is to fuzz the Monero server.

To fuzz Monero, the project builds the `monerod` binary using the Monero oss-fuzz integration,
in order to ensure the `monerod` binary gets build with Address sanitiser and coverage sanitiser. 

To fuzz Monero, the `monerod` binary is launched as a local server and 
fuzzed with random requests using a python module. Lastly it generate coverage HTML
report in the work directory.

## Run the fuzzing

From the root of this repository, the first step is to prepare OSS-Fuzz:

```sh
git clone https://github.com/google/oss-fuzz
```

Next, execute the `e2e.py` module, which will build `monerod`, launch the server, start fuzzing for
a limited amount of time or number of requests, and then extract code coverage reports:

```sh
python3 e2e-testing/e2e.py \
  --oss-fuzz ./oss-fuzz/ \
  --debug --round 1000 \
  --proj monero \
  --workdir ./result1
```


Following the exeuction of above, you will see output related to covergae report genreation:

```sh
Cloning into '/src/monero/monero/external/supercop'...
Submodule path 'external/gtest': checked out 'b514bdc898e2951020cbdca1304b75f5950d1f59'
Submodule path 'external/miniupnp': checked out '544e6fcc73c5ad9af48a8985c94f0f1d742ef2e0'
Submodule path 'external/randomx': checked out '102f8acf90a7649ada410de5499a7ec62e49e1da'
Submodule path 'external/rapidjson': checked out '129d19ba7f496df5e33658527a7158c79b99c21c'
Submodule path 'external/supercop': checked out '633500ad8c8759995049ccd022107d1fa8a1bbc9'
error: /src/monero/monero/build2/generated_include/crypto/wallet/ops.h: No such file or directory
warning: The file '/src/monero/monero/build2/generated_include/crypto/wallet/ops.h' isn't covered.
error: /src/monero/monero/build2/translations/translation_files.h: No such file or directory
warning: The file '/src/monero/monero/build2/translations/translation_files.h' isn't covered.
Coverage report available at: /home/user/code/monero-e2e-fuzzing/result1/coverage
```

At this point, you can launch a webserver in the reported directory:

```
python3 -m http.server 8013 --directory /home/user/code/monero-e2e-fuzzing/result1/coverage
```

Navigating to `http://localhost:8013/` in your local browser, you will then see a coverage report, e.g:

<img width="1384" height="285" alt="Screenshot from 2025-11-16 13-21-19" src="https://github.com/user-attachments/assets/78f69ae8-5080-4e5b-9934-db42498fb001" />


## Monerod server log

Monerod server log (including crashes) can be found in `~/.bitmonero/bitmonero.log`.

## License

The code in this repository is licensed according to License.md, specifically MIT license.
