# Tidepath Family Alliance website

Public site of the fictional Tidepath Family Alliance, made for the DevDay Exchange Community Hackathon 2026, Miami. Home page for families, volunteers, schools and donors (programs, get involved, workshops, support, news, contact), plus `/how-we-operate/` (Roomcord rooms, specialist agents, demo videos).

Every name, email, phone number and amount on the site is made up (`example.com` / `example.org` addresses, `555-01xx` numbers). A notice at the top of every page and in the footer says so. Forms link to the demo portal https://app.tidepathfamily.org.

Static Hugo site. No backend, no Node, no npm.

## Requirements

Hugo extended **0.155.3** (`brew install hugo`, or the `hugo_extended_0.155.3` release from GitHub). Check with `hugo version`.

The build needs no network access. Fonts (Inter, Fraunces) are self-hosted in `static/fonts/`.

## Run

```bash
hugo server            # local dev server on http://localhost:1313
hugo --minify          # static build into public/
```

## Deploy

Cloudflare Pages, project `tidepathfamily`, custom domain `tidepathfamily.org`.

```bash
hugo --minify
wrangler pages deploy public --project-name tidepathfamily --branch main
```

`wrangler.toml` sets `pages_build_output_dir = "public"`. The GitHub workflow `.github/workflows/deploy-website.yaml` does the same build and deploy. It runs only by hand until the Cloudflare secrets are set.

For a git-integrated Pages build use: build command `hugo --minify`, root directory `website`, output directory `public`, environment variable `HUGO_VERSION=0.155.3`.

## Announcements

`data/announcements.json` holds a list of banners shown above the header. With `[]` the page renders nothing extra.

```json
[
  {
    "id": "giving-day-2026",
    "title": "Give Miami Day is November 20.",
    "body": "Gifts to Tidepath Family Alliance are matched until midnight.",
    "link": "https://example.org/give",
    "linkText": "Give now",
    "tone": "celebrate",
    "startsAt": "2026-11-10T00:00:00-05:00",
    "endsAt": "2026-11-21T00:00:00-05:00",
    "updatedAt": "2026-11-07T12:00:00Z",
    "updatedBy": "denise"
  }
]
```

- `tone`: `info` (quiet grey), `urgent` (orange), or `celebrate` (dark). Default `info`.
- `link` and `linkText` are optional. `linkText` defaults to "Learn more".
- `startsAt` and `endsAt` are optional. The filter runs at build time: an item shows when `startsAt <= build time < endsAt`. A missing bound is open. Rebuild and deploy to apply a new date window.
- Each banner has `data-announcement-id="<id>"` in the HTML.
- Visitors can dismiss a banner. The browser stores this in localStorage per `id` and `updatedAt`, so a changed `updatedAt` shows the banner again.

## Where to change things

- `data/site.yaml`: names, page title and description, portal URL, event name.
- `layouts/index.html`: home page sections. `layouts/_default/operate.html`: How we operate (`content/how-we-operate.md` sets its URL).
- `layouts/partials/event-notice.html`: the demo notice at the top of every page. The footer repeats it.
- `data/videos.yaml` and `static/videos/`: demo videos (`.mp4` H.264 with faststart, `.jpg` poster, `.vtt` captions). Each file must stay under the 25 MiB Cloudflare Pages limit.
- `data/sample.yaml`: sample donors for the merge example on How we operate.
- `assets/css/main.css`: colors, fonts and base layout. `pages.css` holds the site sections and video styles, `motion.css` the entrance states, `announcements.css` the banner, `base.css` the vendored Tailwind preflight.
- `assets/js/site.js`: motion (merge demo, quote, counters). `announcements.js`: banner dismiss.

Respects reduced motion.
