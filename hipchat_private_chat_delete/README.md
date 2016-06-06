# hipchat_private_chat_delete

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

## Synopsis

```
usage: hipchat_private_chat_delete.py [-h] [-V] [-d] [-v] -a USER_ID_A -b
                                      USER_ID_B [-m] [-n]

optional arguments:
  -h, --help            show this help message and exit
  -V, --version         show program's version number and exit
  -d, --debug           Print lots of debugging statements.
  -v, --verbose         Be verbose.
  -a USER_ID_A, --user-id-a USER_ID_A
                        User ID of user A.
  -b USER_ID_B, --user-id-b USER_ID_B
                        User ID of user B.
  -m, --show-messages   Show private messages truncated to 50 characters.
                        Warning: This might violate the privacy of the
                        involved users. The default is to not show any
                        messages, just meta information about the
                        communication.
  -n, --non-interactive
                        Don’t ask for confirmation before deleting private
                        messages. Make absolutely sure that you specified the
                        correct user IDs!!!
```

## Example usage

First you will need to find out the user IDs for the two users for whom you want to delete all private chats they had between each other. One way to do this is to login to the web interface, select the user from `/people` (URL path) and there you have it `/people/show/<ID>`.

Now login to your HipChat appliance via SSH, copy the script `hipchat_private_chat_delete.py` to it if it does not already exist on the HipChat server and execute it.

Here is an example (note that you will need to change the user IDs):

```
./hipchat_private_chat_delete.py --user-id-a 53 --user-id-b 1 --show-messages
Message from user_id 53 to user_id 1, date 2016-05-25T14:46:49: Hi there,
Message from user_id 1 to user_id 53, date 2016-05-25T14:47:57: Shit …
Message from user_id 1 to user_id 53, date 2016-05-25T14:47:10: Hey,
Message from user_id 53 to user_id 1, date 2016-05-25T14:47:32: Can you send all your passwords?
Message from user_id 1 to user_id 53, date 2016-05-25T14:47:52: Sure, pal. Here you go: 42
Do you want to delete the shown messages (type all uppercase yes)? YES
WARNING: Deleting messages …
```

The messages are unsorted. This is the default when using the Elasticsearch scan and bulk APIs. It should be enough to verify that you are deleting the correct messages.

## Source code

The latest version of the script together with documentation can be found on https://github.com/hamcos/helper-scripts/tree/master/hipchat_private_chat_delete

## Authors

Autor                                      | Contact                     | Note
-------------                              | -------------               | -------------
[Robin Schneider](https://github.com/ypid) | <robin.schneider@hamcos.de> | Initial coding and design, current maintainer.

## License

[BSD 2-clause "Simplified" License](https://spdx.org/licenses/BSD-2-Clause.html)
