"""Utility to serialise JSON RPC requests using the monero_rpc_serialiser C++ binary."""

import subprocess
import tempfile
import json
import os


def serialise(json_obj: dict, endpoint: str, workdir: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmpdir:
        serialiser_path = os.path.join(workdir, 'monero_rpc_serialiser')
        json_path = os.path.join(tmpdir, "input.json")
        output_path = os.path.join(tmpdir, "output.bin")

        # Write JSON to temp file
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_obj, f)

        # Call the C++ binary
        try:
            subprocess.run(
                [serialiser_path, json_path, endpoint, output_path],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception:
            pass

        if os.path.exists(output_path):
            with open(output_path, 'rb') as f:
                return f.read()
        print(f'serialisation failed for endpoint {endpoint}')
        return b''
