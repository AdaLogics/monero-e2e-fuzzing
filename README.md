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
  --workdir ./result
```


## Monerod server log

Monerod server log (including crashes) can be found in `~/.bitmonero/bitmonero.log`.

## License

The code in this repository is licensed according to License.md, specifically MIT license.