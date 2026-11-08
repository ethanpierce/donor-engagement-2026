# Demo video style guide (Tidepath v5)

The reasons behind these rules are in [DECISIONS.md](DECISIONS.md).

## Brand language (from intro.mp4 and outro.mp4)

- Field: violet `#5E28D2` (sampled 94,40,210). Deep: `#1E0957`. Photos are a violet duotone (office, Miami skyline, crowd).
- Accent: lime `#B3E51B` (sampled 179,229,27). Used on one phrase per line ("48 HOURS", "MODIFIED CODEX").
- Display: Montserrat ExtraBold (800). Title case for the big title, uppercase with tracking for statements.
- Body pairing: Inter 500/600 (neutral, legible at small sizes, matches the app UI).
- Motion: centered text that types or rises in, calm photo plates, no bouncing.
- The website (`website/`) uses a different warm palette (Fraunces + Inter, amber). The video follows the intro and outro, not the website.

## Rules applied

1. **One focus at a time.** Each beat has at most one highlighted area. Spotlights narrow attention to a single interaction ([Trainn](https://trainn.co/answers/how-to-add-spotlight-effects-to-your-product-demo-videos/)).
2. **Spotlight, not a box.** Dim and slightly blur everything outside a rounded focus area, with a gradual falloff. A flat grey or a thick border looks unfinished ([Trainn](https://trainn.co/answers/how-to-add-spotlight-effects-to-your-product-demo-videos/), [Document360 spotlight vs highlight](https://docs.document360.com/docs/spotlight.md)). Outside: 30% violet-deep wash and a 1.1 px blur, light enough that the sidebar, header and navigation stay readable. Ring: 2 px lime at 85% plus a 14 px soft glow.
3. **Zoom to clarify, not to decorate.** Zoom only when the focus area is small. Keep zoom light: at most 1.08x for the desktop window (the whole app window, with sidebar, header and navigation, stays in frame) and 1.1x for GitHub. Keep context around the target ([OpenScreen demo guide](https://www.mintlify.com/siddharthvaddem/openscreen/guides/creating-demos), [Screen Studio auto zoom](https://screen.studio/guide/auto-zoom)). Camera moves ease in and out over about 0.7 s.
4. **Combine zoom and spotlight on small targets** such as form fields and buttons ([Trainn](https://trainn.co/answers/how-to-add-spotlight-effects-to-your-product-demo-videos/)).
5. **Short UI motion.** Overlays fade and rise in 200 ms with a standard ease (fast start, slow end), and leave faster (150 ms). Scene transitions are 300 ms crossfades ([Material motion duration and easing](https://m1.material.io/motion/duration-easing.html), [Carbon motion tokens](https://grok.openbmc.org/raw/openbmc/webui-vue/docs/guide/guidelines/motion.md)).
6. **Lower-third hierarchy.** Most important line first and largest. Eyebrow for context, one caption line, one small "who uses it" line. Use the brand typeface and palette, not random colors ([Frame.io lower thirds](https://blog.frame.io/2017/12/04/create-lower-thirds-titles-that-dont-suck/)).
7. **Contrast on busy video.** Text sits on a semi-opaque deep-violet card with a soft shadow, inside the title-safe area, away from the focus ([Frame.io](https://blog.frame.io/2017/12/04/create-lower-thirds-titles-that-dont-suck/), [TechSmith lower thirds](https://www.techsmith.com/blog/edit-videos-lower-thirds/)). The card moves to the corner that does not overlap the focus, and avoids the app sidebar, header and bottom navigation (it prefers the bottom-right, over the composer).
8. **Captions follow the voice.** Each caption is one narration sentence, shown while it is spoken. Subtitle cues are one or two sentences and at least 1.5 s. (Without narration: hold each caption 0.9 s + 0.27 s per word, minimum 2.2 s ([Frame.io](https://blog.frame.io/2017/12/04/create-lower-thirds-titles-that-dont-suck/), [Storyblocks lower thirds](https://www.storyblocks.com/resources/blog/lower-thirds-for-video)). Keep sentences short so a caption stays at two or three lines.
9. **One accent word per caption.** Lime on one key word, same as the intro and outro.
10. **Scene cards are short and minimal.** 1.3 to 1.8 s, violet photo plate from the intro and outro, Montserrat 800 uppercase, one lime phrase, one small Inter line. No badges, no boxes. Each problem section opens with a 1.5 s title card ("P5 · Problem five"; "P1 · Problem one, continued" when a section comes back), and the line names the problem out loud.
11. **Full app UI, never cropped to the text.** Sidebar, header and navigation stay in frame; zoom is light. Overlays say what happens and who the screen is for (staff workspace, public website with no login, restricted room, room agent).
12. **Frame the app like a product shot.** The recording sits as a rounded window with a soft shadow on the violet plate, so the brand surrounds every shot ([Screen Studio](https://screen.studio/guide/auto-zoom) style backgrounds). The phone sits in a clean device frame on the same plate.
13. **Speed badge on sped-up footage.** A small deep-violet pill with "4× SPEED" (lime number, Inter label) at the top-right inside the app window while footage plays at 2x or faster. It fades out when the footage is back to 1x.
14. **Narration sets the pace.** Each scene lasts its narration line plus about 0.4 s, plus a 0.3 s crossfade. Cut dead time, never show a Thinking or Still working bubble: cut from the sent message to the finished reply, and speed up long typing ([Screen Studio SaaS demo guide](https://screenstudio-coupon.pages.dev/saas-demo-guide)).

## Tokens

| Token | Value |
|---|---|
| violet | `#5E28D2` |
| violet-deep | `#1E0957` |
| surface | `rgba(24, 8, 70, 0.84)` + 12 px backdrop blur |
| lime | `#B3E51B` |
| text | `#FFFFFF`, muted `rgba(255,255,255,0.72)` |
| radius | card 18 px, focus 14 px, app window 16 px |
| display | Montserrat 800 |
| body | Inter 500 / 600 |

## Audio

| Item | Value |
|---|---|
| Voice | HeyGen Marshall (native US male), one TTS file per scene, trimmed, loudness-normalised to -16 LUFS, never faster than 1.08x |
| Music bed | instrumental, soft, warm, hopeful; about -30 LUFS overall, about 6 dB ducked under the voice, 0.3 s fade in, 3.5 s fade out; starts past its near-silent opening, loops with a bar-aligned crossfade |
| Final mix | -16 LUFS integrated (master gain step in `editor.py mix`), true peak at or below -1 dBTP, AAC 192 kbps, 48 kHz |
| Intro and outro | their own audio is removed; the music bed plays under both cards at the same level, never music on the cards alone |
| Subtitles | soft mov_text track in the MP4 plus a .srt file; English |
| Title | the first title card starts when the intro ends (the intro's last frame holds through the crossfade) |

## Phone shots

Record public pages at a true 390x844 CSS viewport with 2x pixels. Show the page's own design (it can differ from the video brand). Name it in the caption eyebrow, e.g. "Tidepath's public website".
