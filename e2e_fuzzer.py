"""utilities for fuzzing monerod RPC endpoints."""

import os
import time
import random
import json
import string
import base64
from operator import itemgetter

import requests

import e2e_serialise

debug = False
WORKDIR = '.'


def gen_random_string(max_length=1024) -> str:
    if gen_random_bool():
        length = random.randint(1, max_length)
        return ''.join(random.choices(string.printable, k=length))
    return ''


def gen_random_hex_string(max_length=64, exact=False) -> str:
    if exact:
        length = max_length
    else:
        length = random.randint(2, max(2, max_length))
    if length % 2 == 1:
        length += 1
    return ''.join(random.choices('0123456789abcdef', k=length))


def gen_random_blob(max_bytes=1024) -> str:
    blob_bytes = bytes(
        random.getrandbits(8) for _ in range(random.randint(1, max_bytes)))
    return blob_bytes.hex()


def gen_random_int(start: int = 0, end: int = 99999999999) -> int:
    return random.randint(start, end)


def gen_random_bool() -> bool:
    return random.choice([True, False])


def get_block_ids() -> str:
    block_ids = get_valid_hashes()

    joined_bytes = b''.join(bytes.fromhex(bid) for bid in block_ids)

    return base64.b64encode(joined_bytes).decode()


def generate_request(method, params):
    request = {'jsonrpc': '2.0', 'id': '1', 'method': method, 'params': params}
    return request


def send_request(request, endpoint) -> tuple[bool, str]:
    # Unbanned localhost
    req, end = clear_localhost_ban()

    try:
        x = requests.post('http://127.0.0.1:38081/%s' % (end),
                          json=req,
                          timeout=30)
    except:
        pass

    # Randomly choose if bootstrap is to be cleared
    if gen_random_bool():
        req, end = clear_boostrap_daemon()
    else:
        req, end = send_set_bootstrap_daemon()

    try:
        x = requests.post('http://127.0.0.1:38081/%s' % (end),
                          json=req,
                          timeout=30)
    except:
        pass

    ex = None

    # Fuzz the chosen target
    if debug:
        print('------------------------------------')
        print('Sending to endpoint: %s' % endpoint)
        print('Parameters: %s ' % json.dumps(request))
    try:
        x = requests.post('http://127.0.0.1:38081/%s' % (endpoint),
                          json=request,
                          timeout=30)
        if debug:
            print('Response: %s ' % x.text)
        return True, x.text
    except requests.exceptions.Timeout:
        # Retry with longer timeout because sometimes some requests may take much longer after some stale calls
        try:
            x = requests.post('http://127.0.0.1:38081/%s' % (endpoint),
                              json=request,
                              timeout=600)
            if debug:
                print('Response: %s ' % x.text)
            return True, x.text
        except Exception as e:
            ex = e
    except Exception as e:
        ex = e

    print(f'FAILED!!!!{str(ex)}')
    return False, ''


def send_bin_request(data, endpoint) -> tuple[bool, str]:
    # Unbanned localhost
    req, end = clear_localhost_ban()

    try:
        x = requests.post('http://127.0.0.1:38081/%s' % (end),
                          json=req,
                          timeout=30)
    except:
        pass

    endpoint = f"http://127.0.0.1:38081/{endpoint}"

    headers = {"Content-Type": "application/octet-stream"}

    if debug:
        print('------------------------------------')
        print('Sending to endpoint: %s' % endpoint)
    try:
        x = requests.post(endpoint, data=data, headers=headers)
        if debug:
            print("Response Status Code:", x.status_code)
            print("Response Headers:", x.headers)
        return True, x.headers
    except:
        pass

    return False, ''


def get_height():
    _, result = send_request({}, 'getheight')
    result_dict = {}

    try:
        result_dict = json.loads(result)
    except:
        # Ignore error from failed getheight
        pass

    return result_dict.get('height', 1024)


def get_valid_hashes():
    _, result = send_request({}, 'getheight')
    ids = []

    try:
        result_dict = json.loads(result)
        hash = result_dict.get('hash')
        if hash:
            ids.append(hash)
    except:
        # Ignore error from failed call
        pass

    if not ids:
        ids.append(
            '0000000000000000000000000000000000000000000000000000000000000000')

    return ids


def send_get_blocks():
    height = get_height()
    params = {
        'block_ids': get_block_ids(),
        'prune': gen_random_bool(),
        'start_height': gen_random_int(0, height),
        'no_miner_tx': gen_random_bool(),
        'high_height_ok': gen_random_bool(),
        'pool_info_since': gen_random_int(0, height),
        'max_block_count': gen_random_int(0, height),
        'requested_info': gen_random_int(0, 2),
    }

    bin = e2e_serialise.serialise(params, '/get_blocks.bin', WORKDIR)

    return bin, 'get_blocks.bin'


def send_get_blocks_by_height():
    params = {
        'heights':
        [gen_random_int(0, get_height()) for _ in range(gen_random_int(1, 8))],
    }

    bin = e2e_serialise.serialise(params, '/get_blocks_by_height.bin', WORKDIR)

    return bin, 'get_blocks_by_height.bin'


def send_get_hashes():
    params = {
        'block_ids': get_block_ids(),
        'start_height': gen_random_int(0, get_height()),
    }

    serialised_bin = e2e_serialise.serialise(params, '/get_hashes.bin',
                                             WORKDIR)

    return serialised_bin, 'get_hashes.bin'


def send_get_indexes():
    params = {
        'txs_hashes':
        [gen_random_hex_string(64, True) for _ in range(gen_random_int(1, 8))],
    }

    serialised_bin = e2e_serialise.serialise(params, '/get_o_indexes.bin',
                                             WORKDIR)

    return serialised_bin, 'get_o_indexes.bin'


def send_get_outs_bin():
    params = {
        'outputs': [{
            'amount': gen_random_int(),
            'index': gen_random_int()
        } for _ in range(gen_random_int(1, 8))],
        'get_txid':
        gen_random_bool(),
    }

    serialised_bin = e2e_serialise.serialise(params, '/get_outs.bin', WORKDIR)

    return serialised_bin, 'get_outs.bin'


def send_get_transactions():
    params = {
        'txs_hashes':
        [gen_random_hex_string(64, True) for _ in range(gen_random_int(1, 8))],
        'decode_as_json':
        gen_random_bool(),
        'prune':
        gen_random_bool(),
    }
    return params, 'gettransactions'


def send_get_alt_blocks_hashes():
    params = {}
    return params, 'get_alt_blocks_hashes'


def send_is_key_image_spent():
    params = {
        'key_images':
        [gen_random_hex_string(64, True) for _ in range(gen_random_int(1, 8))],
    }
    return params, 'is_key_image_spent'


def send_send_raw_tx():
    params = {
        'tx_as_hex': gen_random_hex_string(128),
        'do_not_relay': gen_random_bool(),
        'do_sanity_checks': gen_random_bool(),
    }
    return params, 'send_raw_transaction'


def send_start_mining():
    params = {
        'miner_address': gen_random_string(128),
        'threads_count': gen_random_int(),
        'do_background_mining': gen_random_bool(),
        'ignore_battery': gen_random_bool(),
    }
    return params, 'start_mining'


def send_stop_mining():
    params = {}
    return params, 'stop_mining'


def send_mining_status():
    params = {}
    return params, 'mining_status'


def send_save_bc():
    params = {}
    return params, 'save_bc'


def send_get_peer_list():
    params = {}
    return params, 'get_peer_list'


def send_get_public_nodes():
    params = {}
    return params, 'get_public_nodes'


def send_set_log_hash_rate():
    params = {
        'visible': gen_random_bool(),
    }
    return params, 'set_log_hash_rate'


def send_set_log_level():
    params = {
        'level': gen_random_int(),
    }
    return params, 'set_log_level'


def send_set_log_categories():
    params = {
        'categories': gen_random_string(64),
    }
    return params, 'set_log_categories'


def send_get_transaction_pool():
    params = {}
    return params, 'get_transaction_pool'


def send_get_transaction_pool_hashes_bin():
    params = {}
    return params, 'get_transaction_pool_hashes.bin'


def send_get_transaction_pool_hashes():
    params = {}
    return params, 'get_transaction_pool_hashes'


def send_get_transaction_pool_stats():
    params = {}
    return params, 'get_transaction_pool_stats'


def send_set_bootstrap_daemon():
    params = {
        'address': 'auto',
        'username': gen_random_string(64),
        'password': gen_random_string(64),
        'proxy': gen_random_string(32),
    }
    return params, 'set_bootstrap_daemon'


def clear_boostrap_daemon():
    params = {
        'address': '',
        'username': '',
        'password': '',
        'proxy': '',
    }
    return params, 'set_bootstrap_daemon'


def send_stop_daemon():
    params = {}
    return params, 'stop_daemon'


def send_get_info():
    params = {}
    return params, 'get_info'


def send_get_net_stats():
    params = {}
    return params, 'get_net_stats'


def send_get_limit():
    params = {}
    return params, 'get_limit'


def send_set_limit():
    params = {
        'limit_down': gen_random_int(),
        'limit_up': gen_random_int(),
    }
    return params, 'set_limit'


def send_out_peers():
    params = {
        'white': gen_random_bool(),
        'gray': gen_random_bool(),
    }
    return params, 'out_peers'


def send_in_peers():
    params = {
        'white': gen_random_bool(),
        'gray': gen_random_bool(),
    }
    return params, 'in_peers'


def send_get_outs():
    params = {
        'outputs': [{
            'amount': gen_random_int(),
            'index': gen_random_int()
        } for _ in range(gen_random_int(1, 8))],
    }
    return params, 'get_outs'


def send_update():
    params = {
        'command': gen_random_string(128),
    }
    return params, 'update'


def send_get_output_distribution_bin():
    params = {
        'amounts': [gen_random_int() for _ in range(gen_random_int(1, 8))],
        'cumulative': gen_random_bool(),
        'from_height': gen_random_int(0, get_height()),
        'to_height': gen_random_int(0, get_height()),
    }

    serialised_bin = e2e_serialise.serialise(params,
                                             '/get_output_distribution.bin',
                                             WORKDIR)

    return serialised_bin, 'get_output_distribution.bin'


def send_pop_blocks():
    params = {
        'nblocks': gen_random_int(),
    }
    return params, 'pop_blocks'


def send_getblockcount():
    request = generate_request(method='getblockcount', params={})
    return request, 'json_rpc'


def send_getblockhash():
    request = generate_request(method='on_get_block_hash',
                               params=[gen_random_int()])
    return request, 'json_rpc'


def send_getblocktemplate():
    request = generate_request(method='getblocktemplate',
                               params={
                                   'wallet_address':
                                   gen_random_hex_string(128),
                                   'reserve_size': gen_random_int(0, 512),
                               })
    return request, 'json_rpc'


def send_getminerdata():
    request = generate_request(method='get_miner_data', params={})
    return request, 'json_rpc'


def send_calc_pow():
    request = generate_request(method='calc_pow',
                               params={
                                   'major_version': gen_random_int(0, 255),
                                   'height': gen_random_int(0, get_height()),
                                   'block_blob': gen_random_blob(),
                                   'seed_hash': gen_random_hex_string(64),
                               })
    return request, 'json_rpc'


def send_add_aux_pow():
    request = generate_request(method='add_aux_pow',
                               params={
                                   'blocktemplate_blob':
                                   gen_random_string(128),
                                   'aux_pow': [{
                                       'id':
                                       gen_random_hex_string(64, True),
                                       'hash':
                                       gen_random_hex_string(64, True)
                                   }],
                               })
    return request, 'json_rpc'


def send_submitblock():
    request = generate_request(method='submitblock',
                               params=[gen_random_hex_string(64, True)])
    return request, 'json_rpc'


def send_generateblocks():
    request = generate_request(method='generateblocks',
                               params={
                                   'amount_of_blocks':
                                   gen_random_int(0, get_height()),
                                   'wallet_address':
                                   gen_random_hex_string(64),
                                   'prev_block':
                                   gen_random_hex_string(64, True),
                                   'starting_nonce':
                                   gen_random_int(0, get_height()),
                               })
    return request, 'json_rpc'


def send_get_last_block_header():
    request = generate_request(method='get_last_block_header',
                               params={
                                   'fill_pow_hash': gen_random_bool(),
                               })
    return request, 'json_rpc'


def send_get_block_header_by_hash():
    request = generate_request(method='get_block_header_by_hash',
                               params={
                                   'hash': gen_random_hex_string(64, True),
                                   'fill_pow_hash': gen_random_bool(),
                               })
    return request, 'json_rpc'


def send_get_block_header_by_height():
    request = generate_request(method='get_block_header_by_height',
                               params={
                                   'height': gen_random_int(0, get_height()),
                                   'fill_pow_hash': gen_random_bool(),
                               })
    return request, 'json_rpc'


def send_get_block_headers_range():
    start_height = gen_random_int(0, get_height() - 1)
    end_height = gen_random_int(start_height,
                                max(get_height() - 1, start_height))
    request = generate_request(method='get_block_headers_range',
                               params={
                                   'start_height': start_height,
                                   'end_height': end_height,
                                   'fill_pow_hash': gen_random_bool(),
                               })
    return request, 'json_rpc'


def send_get_block():
    request = generate_request(method='get_block',
                               params={
                                   'height': gen_random_int(0, get_height()),
                                   'hash': gen_random_hex_string(64, True),
                                   'fill_pow_hash': gen_random_bool(),
                               })
    return request, 'json_rpc'


def send_get_connections():
    request = generate_request(method='get_connections', params={})
    return request, 'json_rpc'


def send_get_info_json():
    request = generate_request(method='get_info', params={})
    return request, 'json_rpc'


def send_hard_fork_info():
    request = generate_request(method='hard_fork_info', params={})
    return request, 'json_rpc'


def clear_localhost_ban():
    request = generate_request(method='set_bans',
                               params={
                                   'bans': [{
                                       'host': '127.0.0.1',
                                       'ip': 0,
                                       'ban': False,
                                       'seconds': 0
                                   }],
                               })
    return request, 'json_rpc'


def send_set_bans():
    request = generate_request(method='set_bans',
                               params={
                                   'bans': [{
                                       'host': gen_random_string(128),
                                       'ip': gen_random_int(0, 0xFFFFFFFF),
                                       'ban': gen_random_bool(),
                                       'seconds': gen_random_int(0, 72000)
                                   }, {
                                       'host': gen_random_string(128),
                                       'ip': gen_random_int(0, 0xFFFFFFFF),
                                       'ban': gen_random_bool(),
                                       'seconds': gen_random_int(0, 72000)
                                   }],
                               })
    return request, 'json_rpc'


def send_get_bans():
    request = generate_request(method='get_bans', params={})
    return request, 'json_rpc'


def send_banned():
    request = generate_request(method='banned',
                               params={
                                   'bans': gen_random_string(128),
                               })
    return request, 'json_rpc'


def send_flush_txpool():
    request = generate_request(method='flush_txpool',
                               params={
                                   'txids': [
                                       gen_random_hex_string(64, True)
                                       for _ in range(gen_random_int(1, 8))
                                   ],
                               })
    return request, 'json_rpc'


def send_get_output_histogram():
    request = generate_request(
        method='get_output_histogram',
        params={
            'amounts': [gen_random_int() for _ in range(gen_random_int(1, 8))],
            'min_count': gen_random_int(),
            'max_count': gen_random_int(),
            'unlocked': gen_random_bool(),
            'recent_cutoff': gen_random_int(),
        })
    return request, 'json_rpc'


def send_get_version():
    request = generate_request(method='get_version', params={})
    return request, 'json_rpc'


def send_get_coinbase_tx_sum():
    request = generate_request(method='get_coinbase_tx_sum',
                               params={
                                   'height': gen_random_int(0, get_height()),
                                   'count': gen_random_int(0, get_height()),
                               })
    return request, 'json_rpc'


def send_get_base_fee_estimate():
    request = generate_request(method='get_fee_estimate',
                               params={
                                   'grace_blocks': gen_random_int(),
                               })
    return request, 'json_rpc'


def send_get_alternate_chains():
    request = generate_request(method='get_alternate_chains', params={})
    return request, 'json_rpc'


def send_relay_tx():
    request = generate_request(method='relay_tx',
                               params={
                                   'txids': [
                                       gen_random_hex_string(64, True)
                                       for _ in range(gen_random_int(1, 8))
                                   ],
                               })
    return request, 'json_rpc'


def send_sync_info():
    request = generate_request(method='sync_info', params={})
    return request, 'json_rpc'


def send_get_txpool_backlog():
    request = generate_request(method='get_txpool_backlog', params={})
    return request, 'json_rpc'


def send_get_output_distribution():
    request = generate_request(
        method='get_output_distribution',
        params={
            'amounts': [gen_random_int() for _ in range(gen_random_int(1, 8))],
            'cumulative': gen_random_bool(),
            'from_height': gen_random_int(0, get_height()),
            'to_height': gen_random_int(0, get_height()),
        })
    return request, 'json_rpc'


def send_prune_blockchain():
    request = generate_request(method='prune_blockchain',
                               params={
                                   'check': gen_random_bool(),
                               })
    return request, 'json_rpc'


def send_flush_cache():
    request = generate_request(method='flush_cache',
                               params={
                                   'bad_txs': gen_random_bool(),
                                   'bad_blocks': gen_random_bool(),
                               })
    return request, 'json_rpc'


def send_get_txids_loose():
    request = generate_request(method='get_txids_loose', params={})
    return request, 'json_rpc'


def send_rpc_access_info():
    request = generate_request(method='rpc_access_info', params={})
    return request, 'json_rpc'


def send_rpc_access_submit_nonce():
    request = generate_request(method='rpc_access_submit_nonce',
                               params=[gen_random_string(64)])
    return request, 'json_rpc'


def send_rpc_access_pay():
    request = generate_request(method='rpc_access_pay',
                               params={
                                   'payment': gen_random_int(),
                                   'paying_for': gen_random_string(64),
                               })
    return request, 'json_rpc'


def send_rpc_access_tracking():
    request = generate_request(method='rpc_access_tracking',
                               params={
                                   'client': gen_random_string(64),
                               })
    return request, 'json_rpc'


def send_rpc_access_data():
    request = generate_request(method='rpc_access_data',
                               params={
                                   'client': gen_random_string(64),
                               })
    return request, 'json_rpc'


def send_rpc_access_account():
    request = generate_request(method='rpc_access_account',
                               params={
                                   'client': gen_random_string(64),
                               })
    return request, 'json_rpc'


def fuzz(max_rpc_requests_to_send: int, workdir: str, need_debug: bool,
         rpc_call_stats: dict[str, tuple[int, int]],
         duration: int) -> dict[str, tuple[int, int]]:
    """Launch a fuzzing campaign for the Monero RPC endpoints."""
    print('Fuzzing launching with max of %d rpc requests.' %
          max_rpc_requests_to_send)
    global debug
    debug = need_debug

    global WORKDIR
    WORKDIR = workdir

    rpc_calls = [
        send_get_transactions,
        send_get_alt_blocks_hashes,
        send_is_key_image_spent,
        send_send_raw_tx,
        send_start_mining,
        send_stop_mining,
        send_mining_status,
        send_save_bc,
        send_get_peer_list,
        send_get_public_nodes,
        send_set_log_hash_rate,
        send_set_log_categories,
        send_get_transaction_pool,
        send_get_transaction_pool_hashes_bin,
        send_get_transaction_pool_hashes,
        send_get_transaction_pool_stats,
        send_get_info,
        send_get_net_stats,
        send_get_limit,
        send_set_limit,
        send_out_peers,
        send_in_peers,
        send_get_outs,
        send_update,
        send_pop_blocks,
        send_getblockcount,
        send_getblockhash,
        send_add_aux_pow,
        send_calc_pow,
        send_get_block_header_by_hash,
        send_get_block_header_by_height,
        send_get_block_headers_range,
        send_get_block,
        send_get_connections,
        send_get_info_json,
        send_hard_fork_info,
        send_get_bans,
        send_banned,
        send_set_bans,
        send_flush_txpool,
        send_get_output_histogram,
        send_get_version,
        send_get_coinbase_tx_sum,
        send_get_base_fee_estimate,
        send_get_alternate_chains,
        send_relay_tx,
        send_sync_info,
        send_get_txpool_backlog,
        send_get_output_distribution,
        send_flush_cache,
        send_get_txids_loose,
        send_rpc_access_tracking,
    ]

    rpc_calls_need_core = [
        send_getblocktemplate,
        send_getminerdata,
        send_submitblock,
        send_generateblocks,
        send_get_last_block_header,
    ]

    rpc_calls_need_payment = [
        send_rpc_access_info,
        send_rpc_access_submit_nonce,
        send_rpc_access_pay,
        send_rpc_access_data,
        send_rpc_access_account,
    ]

    rpc_calls_with_binary = [
        send_get_blocks,
        send_get_blocks_by_height,
        send_get_hashes,
        send_get_indexes,
        send_get_outs_bin,
        send_get_output_distribution_bin,
    ]

    rpc_calls.extend(rpc_calls_need_core)
    rpc_calls.extend(rpc_calls_need_payment)
    rpc_calls.extend(rpc_calls_with_binary)

    # Initialise a statistics tracker where we keep note of
    # the number of successful and failed calls.
    if not rpc_call_stats:
        rpc_call_stats = {call.__name__: (0, 0) for call in rpc_calls}

    start_time = time.time()
    rpc_calls_made = []
    for rpc_request_counter in range(max(max_rpc_requests_to_send, 1)):
        if debug:
            print('Fuzzing request %d of %d' %
                  (rpc_request_counter + 1, max_rpc_requests_to_send))
        if rpc_request_counter % 1000 == 0:
            print('Package: %d' % (rpc_request_counter))

        rpc_index = random.randint(0, len(rpc_calls) - 1)

        t0 = time.time()

        if duration > 0 and (time.time() - start_time) > duration:
            print('Fuzzing duration reached, stopping fuzzing.')
            break

        # rpc_call_to_do = send_getblocktemplate# rpc_calls[rpc_index]
        rpc_call_to_do = rpc_calls[rpc_index]
        request, endpoint = rpc_call_to_do()
        if isinstance(request, bytes):
            success, _ = send_bin_request(request, endpoint)
        else:
            success, _ = send_request(request, endpoint)

        t1 = time.time()
        rpc_calls_made.append({
            'name': rpc_call_to_do.__name__,
            'endpoint': endpoint,
            #'request': request,
            'success': success,
            'time': t1 - t0,
        })
        print('Request %s took %f seconds' %
              (rpc_call_to_do.__name__, t1 - t0))
        old_success, old_fail = rpc_call_stats[rpc_calls[rpc_index].__name__]
        if success:
            old_success += 1
        else:
            old_fail += 1
        rpc_call_stats[rpc_calls[rpc_index].__name__] = (old_success, old_fail)
        if not success:
            break

    # Write stats files
    with open(os.path.join(workdir, 'rpc_calls_made.json'),
              'w',
              encoding='utf-8') as f:
        json.dump(rpc_calls_made, f, indent=2)

    sorted_rpc_calls = sorted(rpc_calls_made,
                              key=itemgetter('time'),
                              reverse=True)
    with open(os.path.join(workdir, 'rpc_calls_made_sorted.json'),
              'w',
              encoding='utf-8') as f:
        json.dump(sorted_rpc_calls, f, indent=2)

    # Log high level stats.
    print('Fuzzing finished with %d requests.' % max_rpc_requests_to_send)
    print('Sending prune request')
    send_request(*send_prune_blockchain())
    print('Sending stop daemon request')
    send_request(*send_stop_daemon())
    print('Fuzzing step finished')
    print('Fuzzed for a total of %d seconds.' % (time.time() - start_time))
    return rpc_call_stats
