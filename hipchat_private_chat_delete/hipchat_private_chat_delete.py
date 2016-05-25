#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Robin Schneider <robin.schneider@hamcos.de>
# hamcos IT Service GmbH http://www.hamcos.de
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    1. Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#
#    2. Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

__license__ = 'BSD-2-Clause'
__author__ = 'Robin Schneider <robin.schneider@hamcos.de>'

"""
Script which allows to delete private messages between two users (user A and
user B) sent over a HipChat appliance.
It was written because HipChat did not provide a feature to do this on
it’s own in bulk.

Internals:
The script does it’s job by utilizing access to the backend, namely the
database (Elasticsearch 1.5.2) and the in-memory cache (Redis 2.8.4).

This was done because the HipChat API does not provide the necessary calls.
Note that HipChat is aware of this script and messing with the backend by
circumventing the provided HipChat API is not supported in any way.

Use at your own risk!

Lets hope this feature gets implemented in HipChat at some point.
This script can be used as a starting point for such a feature.

Tested against: Atlassian HipChat 2.0 build 1.4.1 (2016.05.04.071348)
"""

__version__ = '0.8'
__status__ = 'Production'

# core modules {{{
import logging
import sys
import json
import re
#  import dateutil.parser
# }}}

# additional modules {{{
from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan, bulk
from redis import Redis
# }}}


class HipChatPrivateMessagesDeleter:

    _affected_private_chat_ids = set()
    _documents_to_delete = []

    def __init__(
        self,
        user_a_user_id,
        user_b_user_id,
        clear_affected_redis_keys=True,
        interactive=False,
        show_messages=False,
    ):

        self._user_a_user_id = user_a_user_id
        self._user_b_user_id = user_b_user_id
        self._clear_affected_redis_keys = clear_affected_redis_keys
        self._interactive = interactive
        self._show_messages = show_messages

        self._filter_query_for_users = self._get_filter_query_for_users()

    def _get_filter_query_for_users(self):
        """
        Returns the Elasticsearch query filter to search for all private
        messages between two users.
        """

        query_filter = {
            'filter': {
                'bool': {
                    'should': [
                        {'bool': {'must': [
                            {'term': {'from.user_id': self._user_a_user_id}},
                            {'term': {'to.user_id': self._user_b_user_id}},
                        ]}},
                        {'bool': {'must': [
                            {'term': {'from.user_id': self._user_b_user_id}},
                            {'term': {'to.user_id': self._user_a_user_id}},
                        ]}},
                    ],
                }
            }
        }

        query_fields = [
            'from.user_id',
            'to.user_id',
            'date',
            'privatechat_id',
        ]

        if self._show_messages:
            query_fields.append('stanza_data.body')
            query_fields.append('deleted.user_id')

        return {
            'fields': query_fields,
            'query': {
                'filtered': query_filter
            }
        }

    def fetch_messages_to_delete(
        self,
        es,
        r,
        elastic_search_indices='private-*',
    ):
        """
        Fetch messages and populate the list of documents to delete in
        Elasticsearch and affected keys in the Redis cache.

        Returns the number of messages marked for deletion.
        """

        scroll = scan(
            client=es,
            index=elastic_search_indices,
            query=self._filter_query_for_users,
        )

        for hit in scroll:
            if logger.isEnabledFor(logging.DEBUG):
                print(json.dumps(hit, sort_keys=True, indent=5))

            doc_fields = hit['fields']

            self._documents_to_delete.append({
                '_op_type': 'delete',
                '_index': hit['_index'],
                '_type': hit['_type'],
                '_id': hit['_id'],
            })

            for privatechat_id in doc_fields['privatechat_id']:
                self._affected_private_chat_ids.add(privatechat_id)

            if self._interactive:
                message = ''
                if self._show_messages:
                    if 'stanza_data.body' in doc_fields:
                        message = doc_fields['stanza_data.body'][0]
                        message = message.encode('utf-8')
                    elif 'deleted.user_id' in doc_fields:
                        message = "[Message deleted from user_id {}]".format(
                            doc_fields['deleted.user_id'][0],
                        )

                print(
                    "Message from user_id {from_user_id}"
                    " to user_id {to_user_id}, date {date}{message}".format(
                        from_user_id=doc_fields['from.user_id'][0],
                        to_user_id=doc_fields['to.user_id'][0],
                        date=re.sub(r"Z.*$", "", doc_fields['date'][0]),
                        #  date=dateutil.parser.parse(doc_fields['date'][0])
                        #  .strftime("%Y-%m-%d %H:%M:%S"),
                        message=": {}".format(message[:50])
                        if self._show_messages else '',
                    )
                )

        logger.debug("Effected private chat IDs: {}".format(
            self._affected_private_chat_ids,
        ))
        logger.debug("Documents to delete: {}".format(
            json.dumps(self._documents_to_delete, sort_keys=True, indent=5)
        ))

        return len(self._documents_to_delete)

    def _do_clear_affected_redis_keys(self, r):
        """
        Delete all keys in Redis cache which did became stale.
        """

        if len(self._affected_private_chat_ids):
            affected_redis_keys = ['history:pchat:' + x
                                   for x in self._affected_private_chat_ids]
            r.delete(*affected_redis_keys)

    def delete_messages(self, es, r):
        """
        Delete all messages using the Elasticsearch bulk API.
        """

        # Not using Delete By Query API because it is deprecated in 1.5.3.

        # To optimize this, an generator could also be passed to `actions`.
        bulk_call = bulk(client=es, actions=self._documents_to_delete)
        logger.debug(bulk_call)

        if self._clear_affected_redis_keys:
            self._do_clear_affected_redis_keys(r)


# main {{{
if __name__ == '__main__':
    from argparse import ArgumentParser

    # Script Arguments {{{
    args_parser = ArgumentParser(
        description=__doc__,
        # epilog=__doc__,
    )
    args_parser.add_argument(
        '-V', '--version',
        action='version',
        version='%(prog)s {version}'.format(version=__version__)
    )
    args_parser.add_argument(
        '-d', '--debug',
        help="Print lots of debugging statements.",
        action='store_const',
        dest='loglevel',
        const=logging.DEBUG,
        default=logging.WARNING,
    )
    args_parser.add_argument(
        '-v', '--verbose',
        help="Be verbose.",
        action='store_const',
        dest='loglevel',
        const=logging.INFO,
    )
    args_parser.add_argument(
        '-a', '--user-id-a',
        help="User ID of user A.",
        required=True,
    )
    args_parser.add_argument(
        '-b', '--user-id-b',
        help="User ID of user B.",
        required=True,
    )
    args_parser.add_argument(
        '-m', '--show-messages',
        help="Show private messages truncated to 50 characters."
        " Warning: This might violate the privacy of the involved users."
        " The default is to not show any messages,"
        " just meta information about the communication.",
        action='store_true',
        default=False,
    )
    args_parser.add_argument(
        '-n', '--non-interactive',
        help="Don’t ask for confirmation before deleting private messages."
        " Make absolutely sure that you specified the correct user IDs!!!",
        action='store_true',
        default=False,
    )
    args = args_parser.parse_args()
    logger = logging.getLogger(__file__)
    logging.basicConfig(
        format='%(levelname)s: %(message)s',
        level=args.loglevel,
    )
    # }}}

    hc_deleter = HipChatPrivateMessagesDeleter(
        args.user_id_a,
        args.user_id_b,
        interactive=not args.non_interactive,
        show_messages=args.show_messages,
    )

    logger.info("ElasticSearch query: {}".format(
        json.dumps(
            hc_deleter._filter_query_for_users,
            sort_keys=True,
            indent=5
        ),
    ))

    es = Elasticsearch()
    r = Redis()

    if hc_deleter.fetch_messages_to_delete(es, r,) == 0:
        print("No messages to delete.")
        sys.exit(0)

    if not args.non_interactive:
        user_confirm = raw_input(
            "Do you want to delete the shown messages"
            " (type all uppercase yes)? "
        )
        if user_confirm != "YES":
            print("Exiting without deleting anything.")
            sys.exit(1)

    logger.warning("Deleting messages …")
    hc_deleter.delete_messages(es, r,)

# }}}
