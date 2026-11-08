#!/bin/bash
# Delete earlier demo takes from Roomcord rooms through the API delete route, so the history looks natural.
# usage: clean_room.sh <roomId> [<messageId> ...]   (no message ids = every visible message and thread reply in the room)
# Env: WORKCORD_API_URL, WORKCORD_TOKEN (the demo user; deletes its own messages and agent replies it owns).
#      Optional SECOND_TOKEN: a bot token (e.g. the public form's poster) for messages the demo user cannot delete.
set -u
R=$1; shift
del() { workcord messages delete-message --room-id "$R" --message-id "$1" >/dev/null 2>&1 && return 0
  [ -n "${SECOND_TOKEN:-}" ] && WORKCORD_TOKEN=$SECOND_TOKEN workcord messages delete-message --room-id "$R" --message-id "$1" >/dev/null 2>&1; }
ids=("$@")
if [ ${#ids[@]} -eq 0 ]; then
  for id in $(workcord messages list --room "$R" --limit 100 | python3 -c "import json,sys;[print(m['id']) for m in json.load(sys.stdin)['data']]"); do
    for t in $(workcord messages thread --room "$R" --message "$id" 2>/dev/null | python3 -c "import json,sys
try: [print(m['id']) for m in json.load(sys.stdin)['data']]
except Exception: pass"); do ids+=("$t"); done
    ids+=("$id")
  done
fi
for id in "${ids[@]}"; do del "$id" && echo "deleted $id" || echo "LEFT $id"; done
