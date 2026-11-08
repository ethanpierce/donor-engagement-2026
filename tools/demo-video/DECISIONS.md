# Decisions (Tidepath videos, Nov 2026)

Short rules from the Tidepath main demo, the calendar video and the Dots video, each with its reason.
Read this before you write a script. `SKILL.md` has the workflow, `style-guide.md` the visual and audio values.

## Voice

- **HeyGen "Marshall", `1c7ede0bc6ed48f2891b74424b2f1fe3`, legacy route.** It is a native US male voice.
  "Marina" (the earlier default) was rejected because it does not sound US native. Gemini TTS "Sulafat" was the
  earlier fallback and stays as the fallback in `vo.py`.
- **Send "Tidepath’s" with a typographic apostrophe (’).** With a straight apostrophe HeyGen reads
  "Tide-a-path's". Check every proper noun with STT (`vo.py check`, `verify.py --stt`), and listen to the ones STT
  spells oddly before you change the text.
- **Never speed the voice past 1.08x.** Faster speech sounds rushed and unnatural. Make the scene as long as its
  line instead: the editor times every scene to its narration.
- **Re-render only the lines that changed** (`vo.py line`, `vo.py drop`). The other lines keep their takes and
  pauses, so an approved read does not change.

## Language, music, loudness

- **English everywhere**: narration, captions, app UI in the recordings, subtitles. Judges and viewers read English.
- **No music on the intro or outro cards alone.** A soft AI music bed (ElevenLabs Music via fal, instrumental) plays
  under the whole video, also under the intro and outro cards at the same level, and ducks about 6 dB under the
  voice. The bed starts past its near-silent opening, and repeats with a bar-aligned crossfade when the video is
  longer than the bed, so it never drops out or jumps off the beat.
- **-16 LUFS integrated, true peak under -1 dBTP.** This is the usual target for online video; the editor sets the
  master gain to reach it and `verify.py` fails outside 1 LU.
- **Soft subtitles plus a .srt file.** The MP4 carries a mov_text track; upload the .srt to YouTube as the English
  track. Burned-in text would duplicate the captions on the cards.

## Visual style

- **Full app UI, never cropped to the text.** Sidebar, header and navigation stay in frame, so viewers see a real
  product, not a mock-up. Zoom stays light (1.08x max on desktop).
- **Overlays explain what happens and who each screen is for.** Every shot has a caption (what happens, from the
  narration) and a small "who" line (staff workspace, public website with no login, restricted room, room agent).
- **Thin, soft highlights.** A spotlight with a 2 px lime ring and a soft glow. No thick yellow borders: they looked
  unfinished.
- **Short scene cuts**, 0.3 s crossfades, the scene as long as its line.
- **Brand:** violet `#5E28D2`, deep violet `#1E0957`, lime `#B3E51B`, Montserrat 800 + Inter. Cards, captions and
  the speed badge match the intro and outro, so the video looks like one piece.

## Script process

- **Write the narration and review it with the user before you render.** A render is expensive; a script change
  after recording often means new takes.
- **Map each scene to the hackathon problem it solves, and say it out loud** ("Problem five: ..."). Each section
  opens with a short title card ("P5 · Problem five"). Judges score per problem.
- **Never interrupt a scene's flow with another topic.** The calendar build first sat inside the CRM tour (P1) and
  broke it; it moved to the end of P3, where the workshop agent lives.

## Honesty: claim only what the screen shows

- The CRM room app was coded, not built by chat. So the script says room apps "can be built" by talking to a room
  agent, and points to the calendar video, which shows a build from chat.
- No "open source" claim. The repository is on GitHub; the script says that and nothing more.
- "Builds a pattern" from past gifts, not "learned": the agent compares new gifts with each donor's history; it does
  not train.
- "One monthly gift failed yesterday" needed real data (a failed gift dated the day before) and a skill change (flag
  failed gifts the next day) before the line could say it.
- When a recording shows history (things done before the take), the narration does not present it as live.

## Data before recording

- **Check that each scripted line has data behind it** before you record: names, counts, dates, amounts.
- **Ingest only the missing made-up rows.** Do not reset or regenerate data that other scenes already show.
- **Back up the live DB first**, so a bad ingest can be undone.

## Recording on Roomcord

- **Address the specialist agent by its mention name** (for example `@Tidepath Workshops`), so the right agent
  answers.
- **Word messages so the generic RoomAgent does not answer** (no general questions to "the room", no "assistant").
- **Ask the agent to "run the check again"** on a retake, so it checks the data again and does not repeat its last
  reply from memory.
- **Room apps are saved as drafts.** A room admin approves the draft in the UI before it installs; show that step,
  it is part of the story ("nothing installs without approval").

## Output and publishing

- **Videos go to YouTube, never to git.** The repo keeps the kit, plans and scripts only (`.gitignore` blocks media).
- **Keep a backup of each version** in `_<name>-backup/` next to the output (for example `_v5a-backup/`) before you
  replace a file.
- **Companion videos:** one main video plus short focused ones (calendar app built from chat, Dots through the API).
  Link all of them in each YouTube description, so a viewer can go from the overview to the detail.
