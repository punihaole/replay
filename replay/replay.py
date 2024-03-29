#!/usr/bin/env python3
import argparse
import sys
import base64

import requests
from parse_bt_payload import ParseBTPayload
from normalized_webhook_data import NormalizedWebhookData

from rehook import RehookGateway
from rehook.webhook import Webhook


def replay_webhook(session: requests.Session, webhook: Webhook, target: str):
    kwargs = {}
    if webhook.body_base64:
        kwargs['data'] = base64.b64decode(webhook.body_base64)
    elif webhook.body:
        kwargs['data'] = webhook.body
    elif webhook.data:
        kwargs['json'] = webhook.data

    req = requests.Request(method=webhook.method,
                           url=target,
                           headers=webhook.headers,
                           params=webhook.query_params,
                           **kwargs)
    response = session.send(req.prepare())
    if response.status_code >= 400:
        print(f'Error replaying webhook {webhook}: {response}.')
        return False
    return True


def main(cmd, argv):
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-x', '--host', required=False)
    arg_parser.add_argument('-p', '--path', required=True)
    arg_parser.add_argument('-t', '--target', required=True)
    arg_parser.add_argument('--cleanup', dest='cleanup', action='store_true')
    arg_parser.add_argument('--pause', dest='pause', action='store_true')
    arg_parser.add_argument('-f', '--filter', help='filter out hooks..provide url formatted query parameters with keys (id, provider, raw_type, date, user_name, user_id) operators =, <, >, :in-> and value following...ex. id=83zq6w&raw_type:in->subscription_canceled,subscription_went_active')

    args = arg_parser.parse_args()
    gw_kwargs = {}
    if args.host:
        host_str = args.host
        if host_str.startswith(':'):
            host, port = None, host_str[1:]
        elif ':' in host_str:
            host, port = host_str.split(':')
        else:
            host, port = host_str, None
        if host:
            gw_kwargs['host'] = host
        if port:
            gw_kwargs['port'] = port
    gateway = RehookGateway(**gw_kwargs)
    replayed = 0
    success = 0
    removed = 0
    session = requests.Session()
    webhooks = gateway.webhooks.search().filter(path=args.path).execute()
    # used just for data filtering / listing
    if args.filter is not None:
        webhooks_normalized = list(map(lambda x: NormalizedWebhookData(x), webhooks))
        orig_count = len(list(webhooks_normalized))
        webhooks_normalized = list(filter(lambda x: x.meets_criteria(args.filter), webhooks_normalized))
        # adjust webhooks if going to do replay..
        webhooks = list(map(lambda x: x.raw_webhook, webhooks_normalized))
        print(f'\nFiltered down to {len(webhooks_normalized)}/{orig_count} hooks..')
    for webhook in webhooks:
        if args.pause:
            print(webhook)
            input(f'Press Enter to confirm replay to {args.target}: ')
        replayed += 1
        if replay_webhook(session, webhook, args.target):
            success += 1
        if args.cleanup:
            if not gateway.webhooks.delete(webhook.id):
                print(f'Error cleaning up webhook {webhook}.')
            else:
                removed += 1
    print(f'Replayed {replayed} webhooks.')
    print(f'Removed {removed} webhooks.')

if __name__ == '__main__':
    main(sys.argv[0], sys.argv[1:])
