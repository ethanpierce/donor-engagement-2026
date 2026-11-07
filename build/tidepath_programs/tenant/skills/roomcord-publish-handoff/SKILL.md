---
name: roomcord-publish-handoff
description: Use when a participant asks to publish or deprecate a skill, to create, publish, list on the market, update, or deprecate a flavor, to make this agent available to others, or to extract this agent, and your flavor does not allow publishing.
---

# Publish handoff

Only the user's personal assistant publishes skills and flavors. Do not run
`autoworker-hub-client skill create`, `skill publish`, `skill deprecate`,
`flavor create`, `flavor publish`, or `flavor rollout`, and do not look for
another way. Say plainly that you cannot do it and that their personal
assistant can. Never show raw errors. `flavor_not_publisher` means only the
personal assistant may publish.

## Help the user prepare

When the user wants help, collect what the personal assistant needs. The
personal assistant cannot read your instructions or files. It works from what
the user gives it.

1. Your flavor: run `autoworker-hub-client flavor current` and give its
   `id@version`. The new flavor starts from it.
2. Your instructions: the text of `$HOME/workspace/AGENTS.md`, if it exists.
3. Your local skills: the folders under `$HOME/.agents/skills/` that you or
   the user wrote. Give each name and its files. Skip skills that
   `autoworker-hub-client skill installed` lists. They come from the market.
4. Leave out secrets, tokens, credentials, personal data, customer data,
   memory files, and workspace data. Point out any that you see in the
   instructions or skills, so the user can remove them.

## Tell the user what to ask

Give the user one message to send to their personal assistant, for example:

- Flavor: "Publish my agent NAME as a new flavor on the market. Base:
  ID@VERSION. Instructions: TEXT. Skills: NAMES, with their files attached."
- New version of a flavor they own: "Publish a new version of flavor ID with
  these changes: CHANGES."
- Skill: "Publish the skill NAME from my agent AGENT."

Published flavors are visible to everyone on the Hub. Other users get one by
creating or hiring an agent from it. An existing agent cannot switch to a
different flavor.
