# Fonts

The site's three typefaces, self-hosted (no request to Google). Each file is the Latin subset Google Fonts served
for the site's old stylesheet link on 2026-11-06, unchanged, so the page renders as before:

| File | Font | Weights | Source |
| --- | --- | --- | --- |
| `newsreader-latin.woff2` | Newsreader (variable: `wght`, `opsz` 6 to 72) | 400, 500 | fonts.gstatic.com/s/newsreader/v26 |
| `inter-latin.woff2` | Inter (variable: `wght`) | 400, 500, 600 | fonts.gstatic.com/s/inter/v20 |
| `ibm-plex-mono-latin-400.woff2`, `-500`, `-600` | IBM Plex Mono | one each | fonts.gstatic.com/s/ibmplexmono/v20 |

All three are under the SIL Open Font License 1.1: `OFL-Newsreader.txt`, `OFL-Inter.txt`, `OFL-IBM-Plex-Mono.txt`
(from github.com/google/fonts). The `@font-face` rules are at the top of `../site.css`; the page head preloads the
two hero fonts (Newsreader and Inter). Characters outside the Latin subset (the replay's `→`) fall back to a
system font, as they did with Google's stylesheet.
