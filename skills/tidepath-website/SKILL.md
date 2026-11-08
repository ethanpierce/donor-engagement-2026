---
name: tidepath-website
description: Website editor procedures for tidepathfamily.org. Use in the Website room to draft an announcement, show its preview, publish or remove it only after Alex writes "approve", verify it on the live site, list announcements, and answer "where is X on the site" or "what changed" from the read-only public repo.
---

# Tidepath Website

Scripts run as `python3 <this skill dir>/scripts/<name>.py <cmd>`. State lives
in `~/workspace/website/` (drafts, the published list, an audit log, and a
read-only copy of the repo). Never print credentials.

## How the site changes

The site is static. An announcement goes live by a new build and deploy:

1. The script updates the repo copy from the public repo (`main`, read-only).
2. It writes the published list to the site's announcements data file.
3. It builds the site (`SITE_BUILD_CMD`, default `hugo --minify`).
4. It deploys the output (`SITE_DEPLOY_CMD`, default
   `wrangler pages deploy public --project-name $CF_PAGES_PROJECT`).
5. It fetches the live page and checks each active announcement id.

The repo is never written. The announcement list lives only in the workspace
and in the deployed site.

## Add an announcement

1. Write the text from the request. Title at most 80 characters, body at most
   280. Pick the tone: `info`, `urgent` or `celebrate`.
2. Find the link target. Run `repo.py grep <word>` to find the page or section
   id (for example `donate`). Use a site path such as `/#donate`. If no page
   matches, ask. Do not invent a URL.
3. Run `announce.py preview --title ... --body ... [--link /#donate --link-text
   "Donate"] [--tone celebrate] [--starts YYYY-MM-DD] [--ends YYYY-MM-DD]`.
   An event date is a good `--ends` (the end date is inclusive).
4. Post the preview card from the output and the draft id. End with:
   "Reply **approve** to publish."
5. Stop. Wait for Alex.

## Publish

Only when Alex writes "approve" (or "approve <draft id>") in the Website room
after the preview. If there are several drafts and Alex does not name one, ask
which one.

1. Run `announce.py publish <draft-id> --approved-by Alex`. It builds,
   deploys and verifies (up to 90 s).
2. `PUBLISHED ... VERIFY OK`: reply "Live on tidepathfamily.org" with the
   title and the announcement id.
3. `VERIFY FAILED`: say it is deployed but not visible yet. Run
   `announce.py verify --wait 120` once more, then report the result.
4. `ERROR: build failed` or `deploy failed`: nothing changed on the site.
   Report the first error line. Do not retry more than once.

## Remove

Show what will be removed (`announce.py list`) and ask for "approve". Then run
`announce.py remove <id> --approved-by Alex` and report the verify line.

## List and verify

- `announce.py list` shows published items (active, scheduled, expired) and
  drafts that wait for approval. Post it as a short list.
- `announce.py verify` checks the live page against the published list.
- `announce.py build` builds without deploy, to check that the build works.

## Questions about the site (read-only)

- `repo.py sync` updates the copy. Run it first in a new conversation.
- `repo.py grep <text>`: where a word, section or link is on the site.
- `repo.py tree [path]`, `repo.py cat <path> [--lines 10:40]`: read files.
- `repo.py log [-n 10] [path]`, `repo.py show <sha>`: what changed and when.

Answer with the file path and a one-line summary. Do not paste whole files.

## Change requests

You cannot change site code, styles or pages. When asked, post a change
request for a human:

```
Change request (needs a developer)
What: <one sentence>
Where: <file path(s) from repo.py>
Why: <one sentence>
Check: <how to see it on the site>
```

## Environment

`SITE_URL`, `REPO_URL`, `CF_PAGES_PROJECT`, `CLOUDFLARE_ACCOUNT_ID` and
`CLOUDFLARE_API_TOKEN` come from the tenant environment. The token can only
deploy Cloudflare Pages. If it is missing or rejected, say "deploy credentials
missing or rejected" and stop. Optional overrides: `SITE_SUBDIR`,
`ANNOUNCEMENTS_FILE`, `SITE_BUILD_CMD`, `SITE_DEPLOY_CMD`.
