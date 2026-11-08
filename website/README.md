# Tidepath Family landing page

One-page site for Tidepath Family: it finds the same donor across separate gift lists, merges only after staff approve, keeps every gift, and flags regular gifts that are late.

Every donor, email, phone number and amount on the page is made up (`example.com` / `example.org` addresses, `555-01xx` numbers).

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

- `data/site.yaml`: product name, page title and description, and `demoUrl`. Put the demo link there and the "Try the demo" button turns on.
- `data/sample.yaml`: all sample donors, gifts, dates and step copy. Totals are computed in the templates.
- `layouts/partials/sections/`: one partial per page section. `merge-stage.html` is the hero merge demo.
- `assets/css/main.css`: colors, fonts and layout. `motion.css` holds the entrance states, `announcements.css` the banner, `base.css` the vendored Tailwind preflight.
- `assets/js/site.js`: all motion (merge demo, scroll story, counters). `announcements.js`: banner dismiss.

Respects reduced motion.
