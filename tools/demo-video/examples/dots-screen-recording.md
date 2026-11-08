# Example: a narrated edit of someone else's screen recording (Tidepath x OpenAI Dots)

Output: `tidepath-dots-api.mp4`, 99 s (5 s intro card, 84 s body, 10 s outro), 1920x1080, 30 fps, -16.0 LUFS,
true peak -1.5 dBTP, 12 voice lines, published on YouTube (not in git).

## The source

- One screen recording: `<DOTS_SOURCE>.mov`, 396 s, 2404x2258 (near-square), 120 fps, with no useful audio
  (mean level -54 dB, so the audio was dropped).
- It shows OpenAI Dots (the agent is named "Dotty" in the session) reading the Tidepath Roomcord server through the
  public Roomcord API: sign-in, the room list, a Volunteers room summary, a drafted reply that waits for an OK, the
  posted reply, an hours check against the check-in forms and an author check.
- Much of it was history already in the chat when the recording started. The narration shows it as history and does
  not claim that it happened live.

## How it was built

1. **Timeline first.** A contact sheet (one frame every 5 s) and a Gemini pass gave a table: source time -> what is on
   screen. Each narration line was then written against one row of that table, and only for what the screen shows.
2. **Lines.** 12 short lines, HeyGen Marshall, speed 1.0. The TTS text for "Tidepath" was sent as "Tide path" in two
   lines; the subtitles keep the script text. The problem the session solves (P5) is named only because the screen
   makes it clear.
3. **Beats.** One beat per line. A beat is a list of pieces: `play a..b` at 1x, `play a..b` at 4x or 8x (waits and
   typing), and a `hold` on the final frame. Beat length = max(voice + 0.3 s lead + 0.5 s gap, played time + 2 s), so
   a result stays readable at 1x for at least 2 s. The voice sits at the end of the beat, after the action.
4. **Framing.** The near-square source sits in a 1600x1000 rounded window on the blurred violet plate. Each beat has
   a camera `(cx, cy, w)` in source px (a view on the chat column, 1700 px wide, so text is near 1:1). The camera
   eases 0.8 s between beats. A spotlight on the result fades in after the camera settles.
5. **Speed badge.** While a piece plays faster than 1x, a small "4× SPEED" pill sits at the top-right inside the
   window, and fades out when the footage is back to 1x.
6. **Cards.** A 5 s intro card ("Tidepath × *OpenAI Dots*", "Roomcord as a data source, through the API") and the
   main demo outro clip. The same music bed plays under both cards and the whole body, ducked under the voice.
7. **Mix.** Voice + ducked bed, then a two-pass `loudnorm` to -16 LUFS (linear) and a limiter at -1.5 dBTP.
8. **Cuts left out:** an idle stretch, a detour to a new chat, most "Thinking" waits, and a link that opened a "Room
   not found" page. A caption says that Dots gave the room link and message ID, not a direct message link.

Beat table (source times in seconds; speeds per piece):

| Line | Pieces | Camera view | Spotlight |
|---|---|---|---|
| N1 agent named Dotty | hold 5.0 | wide (w 2300) | agent panel |
| N2 public Roomcord API | hold 5.0 | top of chat | API base URL message |
| N3 signs in, nine rooms | hold 5.0 | middle | sign-in reply, room list |
| N4 Alex asks about Volunteers | 11.3-12.6 at 1x, hold 60 | question | Alex's question |
| N5 five check-ins, seven hours | hold 60 | summary | summary block |
| N6 urgent food request | hold 60 | summary | urgent item |
| N7 drafts a reply, asks first | 112.6-116.6 1x, 116.6-120.6 4x, hold 121 | bottom | "OK to send?" draft |
| N8 posts after OK | 136.2-140.2 1x, 140.2-152.2 8x, 181.6-184.2 1x, hold 185 | bottom | "Sent your reply" |
| N9 check hours vs. forms | 189.2-194.0 1x, hold 194 | bottom | Alex's request |
| N10 one mismatch | 270.0-289.6 8x, hold 295 | bottom, panel closed | mismatch reply |
| N11 author is Alex Su | 305.4-309.6 1x, 309.6-321.6 8x, 366.6-369.4 1x, hold 375 | bottom, panel closed | author reply |
| N12 the data source for Dots | hold 375 | wide end view | none |

## The same edit with the kit today

The one-off `build.py` is not in the repo: it hard-coded the source size, the beats and local paths. Its reusable
parts are now in the kit:

- `"layout": "pan"` in `comp.py`: a large or near-square source in a 1600x1000 window. Each beat takes
  `"view": [cx, cy, w]` in source px (default: the full source width, centred on the focus). The view eases between
  beats and the spotlight waits until it settles.
- `"speed_badge_min": 2` in `project`: every `a..b` beat that plays at 2x or faster shows the "N× SPEED" badge.
  A beat can force a label with `"badge": "8×"` or hide it with `"badge": false`.
- Music bed under the cards, master gain to -16 LUFS: done by `editor.py mix`.

Two differences remain. The kit fits footage into the voice length (a long range plays faster), while the Dots edit
made a beat longer than its line when the footage needed it. To get that in the kit, split the sentence into beats
with weights (`w`) and keep each `a..b` range short, or put a short pause into the line. And the kit puts a card
before the first scene only as a `pre` card of that scene; a longer intro card is a `card` part bound to the first
sentence.

Plan sketch for line N8 (one scene, one sentence, three beats):

```json
{"id": "N8", "narration": "After Alex says OK, Dots posts the reply in the Volunteers room.",
 "captions": ["After Alex says OK, Dots posts the reply in the *Volunteers room*."],
 "parts": [{"type": "shot", "layout": "pan", "take": "dots", "eyebrow": "Roomcord API · reply posted",
            "who": "Posted in the room through the API",
            "beats": [{"sent": 0, "w": 0.25, "a": 136.2, "b": 140.2, "view": [900, 1650, 1700]},
                      {"sent": 0, "w": 0.25, "a": 140.2, "b": 152.2, "view": [900, 1650, 1700]},
                      {"sent": 0, "w": 0.5, "freeze": 185.0, "view": [900, 1650, 1700], "focus": [184, 2021, 667, 2099]}]}]}
```
