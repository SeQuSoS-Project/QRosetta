# Frontend load benchmark

`load_bench.mjs` serves `rosetta-api/static` from an in-process Node server that answers the
way `nginx/nginx.conf` does for static files (`Cache-Control: no-cache` on `/`, `/js/` and
`/css/`, `no-store` on `share.html`, ETag and Last-Modified with 304 answers, gzip at level 1
for files of 1000 bytes or more). `infra/nginx-frontend.conf` differs only in sending
`no-store` for `/`, so there a warm load fetches `index.html` in full. Any path that is not a file gets a JSON 404, so the
page's API calls fail fast and do not affect the module timings. It loads the page in headless
Chromium with the DevTools latency emulation and prints medians.

Per load it records:

- `DCL`: `domContentLoadedEventEnd` of the navigation. Module scripts are deferred, so this
  includes fetching and evaluating the whole static import graph.
- `modules done`: the latest `responseEnd` of a `/js/*.js` resource.
- `load`: `loadEventEnd`.
- static requests (HTML, CSS, JS) and how many the server answered with 200 and with 304.
- js request waves: groups of `/js/` requests separated by more than half the emulated RTT,
  i.e. the number of sequential discovery steps the browser actually took.

A cold load disables the cache. A warm load primes the cache with one load in the same
browser context, then loads again in a new page with the cache on, so every `no-cache` file
is revalidated.

## Running

Needs Node 18+, `playwright-core` (any recent version) and a Chromium build. Nothing is
installed by the script.

```bash
PLAYWRIGHT_CORE=/path/to/node_modules/playwright-core \
TMPDIR=$HOME/.tmp/frontend_bench \
node scripts/frontend_bench/load_bench.mjs --rtt 50,150 --runs 7 --protocol h1,h2
```

Options:

| Option | Default | Meaning |
|---|---|---|
| `--page` | `index.html` | page under the static root (`share.html` for the share page) |
| `--rtt` | `50,150` | added latency per request in ms, comma-separated |
| `--runs` | `5` | loads per cell; medians are reported |
| `--protocol` | `h1` | `h1` (plain HTTP/1.1, like the local nginx) and/or `h2` (HTTPS with HTTP/2, like the Cloud Run front end) |
| `--mode` | `cold,warm` | which loads to measure |
| `--down-kbps` | `0` | download throughput cap; 0 means none |
| `--json` | none | also write every median to this file |
| `--root` | `rosetta-api/static` | static directory to serve |

Chromium is taken from `CHROME_PATH`, else the newest `chromium-*/chrome-linux64/chrome` under
`PLAYWRIGHT_BROWSERS_PATH`, `/opt/pw-browsers` or `~/.cache/ms-playwright`, else the system
`chromium` or `google-chrome`. For `h2` the script creates a self-signed certificate in
`$TMPDIR/frontend_bench/` and passes its SPKI hash to Chromium
(`--ignore-certificate-errors-spki-list`); with a plain certificate error Chromium would not
cache the responses and the warm loads would be cold loads.

One browser runs at a time. On a shared machine, run it under a memory cap.

The latency emulation delays each response; it does not model TCP or TLS handshakes or
bandwidth unless `--down-kbps` is given. Under HTTP/1.1 Chromium opens at most six connections
per origin, so the number of files matters there as well as the depth of the import graph.
