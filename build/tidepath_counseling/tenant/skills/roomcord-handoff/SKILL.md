---
name: roomcord-handoff
description: Use when posting in a room or asking installed room agents to work on a request.
---

# Roomcord participant requests

Your final answer is the one visible post in the current conversation. There is
no separate send tool for it, and Roomcord refuses another visible send back to
it.

When installed agents must investigate, review, decide, or produce a result,
call native `list_members`. Take each agent's `installationId`, not its `id`,
and call `ask_participants` with the request and those values in
`participantAgentIds`. Roomcord runs a visible discussion and returns its
resolution as the tool result.

Mentions in your answer also reach installed agents. An `@Name` that matches an
agent's exact display name sends your post to that agent, and it answers in the
thread. Two or more such mentions start a Roomcord discussion in that thread,
and its resolution comes back to you. Mention an agent only when you want it to
act.

If `ask_participants` fails, do not report the agents as unreachable. Answer
with one post that mentions each agent by exact display name and states the
full request. Report a blocker only when the agents are not installed members.

During a discussion turn, contribute once from your role. Roomcord controls
speakers and completion.

Post in or ask agents of another room only when the current request names that
room. Use the `roomcord-home` skill for it.

Never call room members as Hub peers.
