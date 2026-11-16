# Tracefix — Logo Guidelines

## 1. The logo

**Idea:** nine inputs, eight pass, one doesn't fit. The red square is the counterexample — the input that breaks
the fix. It's what Break My Fix does, drawn as one shape.

**Versions**

| Version | File | Use it for |
|---|---|---|
| Horizontal (primary) | `masters/tracefix-horizontal.svg` | Website header, README, docs, slides |
| Stacked | `masters/tracefix-stacked.svg` | Square or tall spaces: covers, stickers, posters |
| Symbol | `masters/tracefix-symbol.svg` | Where the name is already nearby, or space is tight |
| Wordmark | `masters/tracefix-wordmark.svg` | Running text-like contexts where the symbol would crowd |
| App icon / avatar | `masters/tracefix-app-icon.svg`, `masters/tracefix-avatar.svg` | GitHub org/app avatar, Action icon, social profiles |
| Favicon | `web/` (uses `masters/tracefix-favicon-small.svg`) | Browser tabs, bookmarks, home-screen icons |

Every version comes in **full colour** (black + red, for light backgrounds), **reversed** (white + red, for dark
backgrounds), **black** and **white** (one colour, for when only one ink is available).
SVGs are the masters; PNGs in `png/` are for places that don't take SVG.

## 2. Clear space

Keep a clear zone of **one dot** around the logo on all sides (the diameter of one circle in the symbol). The zone
scales with the logo — never use a fixed distance.

## 3. Minimum size

| Version | Screen | Print |
|---|---|---|
| Horizontal | 96 px wide | 25 mm wide |
| Stacked | 64 px wide | 18 mm wide |
| Symbol | 24 px (below that, use the favicon files) | 6 mm |

## 4. Colour

| Name | HEX | RGB | CMYK | Pantone |
|---|---|---|---|---|
| Black | `#000000` | 0 0 0 | 0 0 0 100 (large areas: 60 40 40 100) | Black 6 C |
| Counterexample red | `#CF222E` | 207 34 46 | 0 84 78 19 | 186 C (closest — check against a swatch book) |
| White | `#FFFFFF` | 255 255 255 | 0 0 0 0 | — |

- The red is the same red as the receipt's **COUNTEREXAMPLE** badge. Keep it for findings and the logo's square; don't
  use it for buttons or decoration, so it keeps meaning "something broke".
- Contrast: red on white 5.4 : 1 (passes WCAG AA for text), red on black 3.9 : 1 (fine for graphics like the square).

**Approved pairs:** full colour on white · reversed on black · black on white · white on black.
On photos or busy backgrounds, use the app-icon tile.

## 5. Typography

- Wordmark: **Inter Bold**, outlined, tracking −4/120. Don't retype it — use the files.
- Headlines: Inter Bold / SemiBold · Body: Inter Regular · Code: JetBrains Mono or the system monospace.
- Licence: Inter is under the SIL Open Font License — free for logos, web and print.

## 6. Don'ts

- Don't move the red square to another position, or make more than one square red.
- Don't change the dots to squares, or the square to a dot.
- Don't recolour outside the palette, or put the red square on a red background.
- Don't stretch, rotate, outline, add shadows or gradients.
- Don't rearrange or resize the parts of a lockup.
- Don't retype the wordmark.

## 7. System ideas

The grid is a kit of parts: black dots for passing inputs, a red square for a finding. It can be used in receipt
headers, loading states (dots filling in) and evidence-level badges — always one red square at most.

## 8. Before launch

**Reverse image search (Google Lens, 5 Nov 2026):** no exact matches. The "grid of dots with one odd one out" idea is
used elsewhere, so the mark's distinctiveness rests on its specific form (3×3, black circles, sharp red square in the
bottom-right). Closest relatives found:

- **FinKnight (finknight.ai)** — software/AI: 3×3 black dots with a red rounded square in the **centre**. The closest
  match, and in a nearby category.
- **Red Dot Group** (hotels) — 3×3 black dots, one red dot top-right.
- **Victim Support Denmark** — a taller dot grid with one red dot.
- **10th Dot** (consultancy) — a dot grid with one red dot below.

A reverse image search is not a trademark search. Before using the logo commercially, search the UKIPO / EUIPO / USPTO
databases for similar figurative marks in software (classes 9 and 42), ideally with a trademark attorney.

## 9. Social banners

`social/` holds the profile banners, rendered from `social/banners.html` by `node scripts/brand_banners.js`
(edit the HTML, rerun the script, never edit a PNG).

| File | Size | Where |
|---|---|---|
| `tracefix-x-header-1500x500.png` | 1500 × 500 | X and Bluesky profile header |
| `tracefix-linkedin-company-1128x191.png` | 1128 × 191 | LinkedIn company page cover |
| `tracefix-linkedin-personal-1584x396.png` | 1584 × 396 | LinkedIn personal profile background |
| `tracefix-github-social-1280x640.png` | 1280 × 640 | GitHub repository social preview (Settings, General) |

- Each banner is the site's headline beside a field of dots with **one** red square: the logo's idea drawn wide.
- No banner carries the symbol, so an image never shows two red squares. The two that stand alone (LinkedIn
  personal, GitHub) carry the white wordmark; on X and a company page the avatar and the name are beside it.
- The bottom left stays empty on the three profile banners: X, Bluesky and LinkedIn lay the avatar over it.
- Avatar for all of them: `png/tracefix-avatar-1024.png` (GitHub: `png/tracefix-github-avatar-500.png`).
