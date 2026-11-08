---
name: demo-video
description: Produce a narrated product demo video (1920x1080, brand cards, spotlight captions, AI voiceover, soft music, subtitles, clips) from real app recordings. Use when asked to record, re-cut, narrate or export a demo video of Roomcord rooms, agents, room apps or a public web page, or to make a similar video for another project.
---

# Demo video kit

Pipeline used for the Tidepath hackathon demo (v4). It turns real recordings into a narrated video where every
scene is timed to its voiceover line. All scripts take paths as arguments or from a plan JSON; secrets come only
from environment variables.

```
scripts/
  record_app.py     Roomcord desktop take (1440x900 WebM) from a JSON step list; waits for real, finished agent replies
  record_phone.py   phone take of a public page at 390x844 CSS / 2x (780x1688 MP4); can answer form POSTs locally
  clean_room.sh     delete earlier takes from a room through the API delete route
  overlays.py       renders templates/*.html (caption cards, scene cards) to transparent PNGs with Playwright
  comp.py           compositor: framed app window on the brand plate, light zoom, spotlight + lime ring, captions, cards
  vo.py             TTS per scene (HeyGen default, Gemini or ElevenLabs fallback), voice trials, loudness + sentence timings, STT check
  music.py          generate the music bed (fal), analyse loudness/spectrum, Gemini listening check
  editor.py         plan + takes + voice -> final MP4, SRT, clips (render | mix | clips | plan; --only ID for one scene as a clip)
  verify.py         format, loudness, true peak, subtitle rules, contact sheet, full frames, STT of the mix
templates/          tokens.css, lower-third.html (caption card), scene-card.html
examples/           tidepath.plan.json (full scene plan with narration, incl. a disabled ready-to-insert scene), takes/*.json
style-guide.md      visual and audio rules
```

## Requirements

Python 3.11+ with `playwright` (Chromium installed), `numpy`, `opencv-python`, `pillow`, `faster-whisper`,
`google-genai`, `fal-client`, `requests`; `ffmpeg`/`ffprobe` with libx264; the `workcord` CLI for Roomcord rooms.

Env vars (never write them into files):

| Var | Used by |
|---|---|
| `HEYGEN_API_KEY` | vo.py, default TTS |
| `GEMINI_API_KEY` | vo.py (fallback TTS, STT check), music.py listen, verify.py --stt |
| `FAL_KEY` | music.py generate, vo.py ElevenLabs voices |
| `ROOMCORD_WEB_URL` | record_app.py, web app URL with mode flag, e.g. `https://web.roomcord.com/?m=p` |
| `ROOMCORD_STATE` | record_app.py, path to a Playwright storage-state file of the logged-in demo user (keep outside git) |
| `WORKCORD_API_URL`, `WORKCORD_TOKEN` | record_app.py and clean_room.sh (poll and delete room messages) |
| `SECOND_TOKEN` | optional, clean_room.sh, a bot token for messages the demo user cannot delete |

## Steps

Work in a project folder outside git (for example `~/Movies/<name>/build`) and copy `examples/tidepath.plan.json`
there as `plan.json`. Paths in the plan are relative to it.

1. **Write the narration first.** One line per scene in `plan.json` (`scenes[].narration`). Short sentences, one
   idea each; every sentence becomes one caption. Plan each scene's parts: an optional 1.6 s `pre` card, `card`
   parts bound to sentences, and `shot` parts with beats per sentence (`freeze` time or `a`..`b` range, a `focus`
   rect in source pixels or `{"bubble": "bot"|"me"|"white", "index": n}`, a weight `w`).
2. **Prepare the app state.** Reset app data the take changes (for example room-app decisions) before and after
   the take. Delete earlier takes of the same flow with `clean_room.sh`, so the room history looks natural. Use
   fresh input values (dates, names) that the app has not seen, or agents answer "already done". Agents keep
   memory across deleted messages: if one replies in the wrong language or refers to an old take, send it a short
   setting message, wait for the reply, then delete both messages before recording.
3. **Record the app takes** with `record_app.py take.json takes/`. One take per room flow. Post public-form
   submissions from the take itself (`post` step) so the room receives them live. Read the log: it has the video
   time of every typed message and finished reply. Make a 1 fps contact sheet of each take and pick freeze times
   after the reply is complete; never use frames with a Thinking or Still working bubble.
4. **Record the phone takes last**, after the public page design is final, with `record_phone.py`. Use
   `mock_submit` with the same payload the app take posted, so nothing is posted twice.
5. **Voice.** Reuse the voice of earlier videos when one exists (for HeyGen: the scripts that made the videos in
   `GET /v1/video.list`; names and ids from `GET /v2/voices`). Compare 2-3 voices on one line:
   `vo.py plan.json trial S1 heygen:<id> heygen:<id> gemini:Sulafat` and listen (Gemini also rates them).
   Set `voice` in the plan, then `vo.py plan.json tts`, `vo.py plan.json check` (re-generate any scene below
   0.95 match, and any scene where a product name is mispronounced), and `vo.py plan.json align` (writes
   `vo/n_<scene>.wav` at -16 LUFS and `vo/timing.json`). Re-generating one scene: delete `vo/<id>.wav`, run `tts <id>`
   and `align <id>`; the editor re-times that scene.
6. **Music.** `music.py plan.json generate music/bed.mp3` (prompt in the plan), then `music.py analyse` and
   `music.py listen` on each candidate. Keep a bed with no vocals, steady level, low 2-5 kHz presence, and a length
   longer than the video.
7. **Plates.** Put three 1920x1080 brand photo plates in `plates/` (`skyline.png`, `office_a.png`, `office_b.png`,
   for example frames grabbed from the intro and outro). Without them the cards use a violet gradient.
8. **Edit.** `editor.py plan.json plan` prints the timeline. Then `editor.py plan.json render mix clips`.
   Segments cache in `work/seg`; change one scene and only that scene re-renders.
9. **Verify.** `verify.py out --sheet --stt`. Read the contact sheet and the five full frames: English UI only, no
   Thinking bubbles, no title overlap, sidebar, header and navigation readable. Read the STT transcript: complete
   narration, no word masked by music. Fix and re-run.
10. **Export for YouTube.** The MP4 is upload-ready (H.264 High, AAC 192k, faststart). Upload the `.srt` as the
    English subtitle track. Write `youtube.md` with a title, a description of about 150 words, chapter timestamps
    from `work/plan.json` (`scenes[id][0]`, first chapter at 0:00), and tags. Do not commit media to git.

## Model choices (Tidepath v4)

- Voice (default): HeyGen TTS, voice `Marina` (`c5ee8a405d7e460380cdb8e368a1cbff`), the voice of the account's
  earlier English videos, through `POST /v1/audio/text_to_speech` (`model: "legacy"` in the plan). HeyGen marks this
  route legacy; for v3 voices set `model` to `heygen-voice-1` (or `heygen-voice-1-turbo-free`) and a v3 voice id.
  If neither works, render a voice-only video with `POST /v2/video/generate` (color background) and extract the audio.
- Voice (fallback, in `voice.fallback`): Gemini TTS `gemini-2.5-pro-preview-tts`, voice `Sulafat`, with the style
  prefix. In blind listening checks it was rated warmer and more natural than Marina and than ElevenLabs
  multilingual v2 `Sarah`, `Brian` and `Alice`.
- Music: ElevenLabs Music via fal (`fal-ai/elevenlabs/music`, 300 s, `force_instrumental`), prompt in the plan.
  It beat Stable Audio 2.5 (`fal-ai/stable-audio-25/text-to-audio`), which was brighter in the voice band.
- Sentence timing: faster-whisper `small.en` word timestamps aligned to the script.

## Inserting a ready scene

`tidepath.plan.json` has scene `S12a` (website announcements) with `"enabled": false`. It renders alone as a clip
with `editor.py plan.json render mix --only S12a --name website-announcements`. To put it in the main video, set
`enabled` to true (it sits before `S12`) and run `render mix clips`: cached segments of the other scenes are reused,
only the new scene, the final assembly, the mix and the clips are rebuilt.

## Known limits

- `comp.bubbles()` finds chat bubbles by Roomcord's colors; other apps need rect focus values.
- Covers paint over small UI text in source pixels; use them only for noise such as system previews.
