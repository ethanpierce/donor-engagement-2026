# Mock data seeds — real patterns for Tidepath's made-up donor list

Every person below is invented. Only the pattern comes from a real public page.
Tests: **D** = duplicates · **L** = late gift · **F** = failed/expiring card. Accessed 2026-11-07.
"GMD" = Give Miami Day. Strength: **site** = from the GMD site or its platform docs (strong) · **web** = vendor blog or secondhand summary (weaker; use for shape, not exact numbers).

## 1. Gift sizes and amounts

| # | Pattern to seed | Source | Tests |
|---|---|---|---|
| 1 | Most giving-day gifts sit at a $25 floor. Seed many gifts of exactly $25, a few of $50, $100 and $250. | GMD Donor FAQ: $25 minimum per nonprofit — https://www.givemiamiday.org/p/DonorFaq | L |
| 2 | Bank-transfer (ACH) gifts are never under $50. | GMD Donor FAQ: $50 minimum for bank account — /p/DonorFaq | — (realism) |
| 3 | Typical monthly gift ≈ $24; typical one-time online gift ≈ $126. Seed monthly donors at $10/$20/$25/$50, one-time at $50–$250. | M+R Benchmarks 2025 (via nonprofitpro.com) — https://www.nonprofitpro.com/article/mr-benchmarks-2026-what-online-giving-growth-means-for-your-donor-file/ (web) | F, L |
| 4 | One big donor among many small ones: one $1,000+ gift, rest $25–$250. GMD says "Whether you give $25 or $25,000." | /p/DonorFaq | L (big donor going quiet hurts most) |

## 2. How often and when people give

| # | Pattern to seed | Source | Tests |
|---|---|---|---|
| 5 | **Annual giving-day donor**: gives every mid-November (Early Giving Nov 14–18, GMD Nov 19). Gave 2024 and 2025, nothing in 2026 → should flag as late. | GMD Donor FAQ key dates — /p/DonorFaq | **L** |
| 6 | **"Give Again" repeat donor**: gives to the same nonprofit at the same amount each year (the site's "Refill My Cart" button repeats last year's cart). | GMD How do I give? — https://www.givemiamiday.org/p/give | L |
| 7 | **Early bird vs day-of**: some annual donors give during Early Giving (Nov 14–18), others on the day. The "due date" window should cover both. | /p/DonorFaq; /p/prizes | L (avoid false alarms) |
| 8 | **December giver**: big share of gifts land in December (about 37–40% of yearly online money). Seed a donor who gives every Dec 20–31. | M+R 2025/2026 via nonprofitpro.com + neonone.com/resources/blog/year-end-giving-statistics (web) | **L** |
| 9 | **Holiday-event timing**: a nonprofit runs a big Christmas event right after the giving day; donors give to fund it. | /p/stories/norasandigochildrenfoundation | L |
| 10 | **Monthly donor**: charged the same day each month; gets an email before and a receipt after. | Mightycause help — https://support.mightycause.com/hc/en-us/articles/360015176772 | **F**, L |
| 11 | **First-timer who never returns**: only 2 in 10 first-time donors give again next year. Seed ~10 first-timers from last giving day; only 2 give again. | GMD guide *Loving Your Donors* — https://bit.ly/4y6DEQX | L (not "regular" → don't flag) |
| 12 | **Half the list doesn't come back** ("more than half of your donors will not give next year"). Keep the lapse rate around 50%, so Denise's list isn't flooded. | same guide | L |

## 3. Channels (where a gift comes from)

| # | Pattern to seed | Source | Tests |
|---|---|---|---|
| 13 | Online donation page with many ways to pay: card, PayPal, Venmo, Google Pay, bank transfer, donor-advised fund, IRA. | /p/DonorFaq | D (one person, two payment methods) |
| 14 | **Event ticket channel**: a 5K race fee routed to the nonprofit. The runner list is a separate roster from the donation list. | GMD 5K page — https://www.givemiamiday.org/p/5KFAQ | **D** |
| 15 | **Hand-entered checks and cash**: typed in with name, email, source, notes. | Mightycause help — https://support.mightycause.com/hc/en-us/articles/360017259552 | **D** (typos) |
| 16 | **Friend-run fundraiser page** (peer-to-peer): a supporter raises money from friends; gifts arrive under the fundraiser's page. | /p/orgFAQ; /p/resources-library | D |
| 17 | **Employer match**: a second gift for the same donor arrives later from their employer. | /p/DonorFaq | D, totals |

## 4. Donor problems nonprofits talk about publicly

| # | Pattern to seed | Source | Tests |
|---|---|---|---|
| 18 | **Same donor gives twice and counts once.** GMD's match: "If a donor gives to the same organization twice, their gift will be matched once." Seed a donor with two gifts on GMD under slightly different names. The match should count them once. | GMD Prizes — https://www.givemiamiday.org/p/prizes | **D** |
| 19 | **Card about to expire, flagged by a tiny "!" nobody checks.** Seed a $25 monthly donor whose card expires next month. | Mightycause help 360024641091 — https://support.mightycause.com/hc/en-us/articles/360024641091 | **F** |
| 20 | **Card expired and nobody noticed for months.** "The card simply expired and nobody caught it." Seed a $25 monthly donor with 4 missed months (Jul–Oct). | apiant.com blog (DonorPerfect sustainer recovery) — https://apiant.com/blog/posts/donorperfect-hubspot-lapsed-sustainer-recovery/ (web) | **F**, L |
| 21 | **Nobody tries to save the gift.** 47% of charities made no attempt to keep a monthly donor after their card was canceled (2018 study). | Chronicle of Philanthropy — https://www.philanthropy.com/news/a-third-of-charities-dont-let-monthly-donors-pay-directly-from-their-banks/ (web) | F |
| 22 | **Bank-transfer monthly donors stick better than card donors.** Seed most failures on cards, almost none on bank transfer. | Chronicle — https://www.philanthropy.com/article/charity-raises-more-monthly-gifts-from-bank-transfers-than-from-credit-cards/ (web) | F |
| 23 | **Monthly status is only "Active" or "Canceled"** — no "failed." Seed a donor who still shows Active but whose last 2 charges failed. | Mightycause help 360024641091 | **F** |
| 24 | **Repeated failed tries lock the card** (fraud protection). Seed one donor with 3 declined tries in one hour, then a gift on a different card → looks like 2 people. | GMD Donor FAQ — /p/DonorFaq | F, **D** |
| 25 | **Two records, each with part of the giving** ($25 on one, $50 on the other) → nobody sees the true $75 total. | Reddit post via earlier recon — `../domain-donor-dedup-and-lapsed-giving-2026-11-07/digests/d1-dedup-r1-1.md` claim 17 (web) | **D**, totals |
| 26 | **Gifts counted twice on the year-end receipt.** Software put gifts already thanked during the year onto the year-end summary again. | PowerChurch forum — https://powerchurch.com/forum/viewtopic.php?p=30091 (web) | **D**, totals |
| 27 | **Year-end date mix-up**: card charged Dec 28, receipt dated Jan 5. Seed one late-December gift recorded in January. | AAFRC guide — https://aafrc.org/can-a-nonprofit-correct-an-incorrect-donation-receipt/ (web) | L (don't call a December giver "late" because of a date error), totals |
| 28 | **Platform total ≠ payout total** (fees, bonuses, matches). Seed one gift where the donated amount and the received amount differ. | GMD Nonprofit FAQ — https://www.givemiamiday.org/p/orgFAQ | totals |

## Not found
- Any public story from a small Miami nonprofit about duplicates or failed cards. The 9 GMD stories never mention donor tracking.
- A trustworthy duplicate rate. The only number is a vendor's "25%", with no method (earlier recon, d1 claim 14). Pick a small, clear number for the demo instead, e.g. 6 duplicate pairs in 120 donors.
