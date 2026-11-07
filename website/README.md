# Tidepath Family landing page

One-page site for Tidepath Family: it finds the same donor across separate gift lists, merges only after staff approve, keeps every gift, and flags regular gifts that are late.

Every donor, email, phone number and amount on the page is made up (`example.com` / `example.org` addresses, `555-01xx` numbers).

## Run

```bash
npm install
npm run dev      # local dev server
npm run build    # type check + static build into dist/
npm run lint
```

## Deploy

`npm run build` makes a static site in `dist/`. Any static host works (Vercel, Netlify, Cloudflare Pages): build command `npm run build`, output folder `dist`. No environment variables, no backend.

## Where to change things

- `src/config.ts`: product name and `DEMO_URL`. Put the demo link there and the "Try the demo" button turns on.
- `src/data/sample.ts`: all sample donors, gifts and dates. Totals are computed.
- `src/components/`: hero merge demo (`MergeStage`), scroll story (`HowItWorks`), note for a late donor (`NoteScene`), failed monthly gift (`FeatureFailed`).
- `src/index.css`: colors, fonts and layout.

Stack: Vite, React, TypeScript, Motion, local fonts (Fraunces, Inter). Respects reduced motion.
