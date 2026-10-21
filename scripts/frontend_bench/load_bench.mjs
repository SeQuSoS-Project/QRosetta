// Page-load benchmark for rosetta-api/static: serves the files the way nginx does
// (no-cache on /js and /css, ETag and Last-Modified with 304s, gzip), adds latency with
// Chromium's network emulation and reports medians of cold and warm loads.

import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import http from 'node:http';
import http2 from 'node:http2';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import zlib from 'node:zlib';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_ROOT = path.resolve(HERE, '../../rosetta-api/static');

function parseArgs(argv) {
    const opts = {
        root: DEFAULT_ROOT,
        page: 'index.html',
        rtts: [50, 150],
        runs: 5,
        protocols: ['h1'],
        modes: ['cold', 'warm'],
        downKbps: 0,
        json: '',
        settleMs: 300,
    };
    for (let i = 0; i < argv.length; i++) {
        const [key, inline] = argv[i].split('=', 2);
        const value = () => (inline !== undefined ? inline : argv[++i]);
        switch (key) {
            case '--root': opts.root = path.resolve(value()); break;
            case '--page': opts.page = value(); break;
            case '--rtt': opts.rtts = value().split(',').map(Number); break;
            case '--runs': opts.runs = Number(value()); break;
            case '--protocol': opts.protocols = value().split(','); break;
            case '--mode': opts.modes = value().split(','); break;
            case '--down-kbps': opts.downKbps = Number(value()); break;
            case '--json': opts.json = value(); break;
            case '--settle-ms': opts.settleMs = Number(value()); break;
            case '--help':
                console.log(readFileSync(path.join(HERE, 'README.md'), 'utf8'));
                process.exit(0);
                break;
            default:
                throw new Error(`unknown option ${argv[i]}`);
        }
    }
    return opts;
}

const IMPORT_RE = /^\s*(?:import|export)\s(?:[^'"]*?from\s+)?['"]\.\/([\w.-]+\.js)['"]/gm;

function moduleGraph(jsDir) {
    const graph = new Map();
    for (const name of readdirSync(jsDir).filter(n => n.endsWith('.js'))) {
        const text = readFileSync(path.join(jsDir, name), 'utf8');
        graph.set(name, new Set([...text.matchAll(IMPORT_RE)].map(m => m[1])));
    }
    return graph;
}

function graphStats(root, page) {
    const html = readFileSync(path.join(root, page), 'utf8');
    const entry = /<script\s+type="module"\s+src="js\/([\w.-]+\.js)[^"]*"/.exec(html)?.[1];
    if (!entry) throw new Error(`no module script in ${page}`);
    const graph = moduleGraph(path.join(root, 'js'));
    const depth = new Map();
    const level = name => {
        if (!depth.has(name)) {
            let d = 1;
            for (const dep of graph.get(name) || []) d = Math.max(d, level(dep) + 1);
            depth.set(name, d);
        }
        return depth.get(name);
    };
    const longest = level(entry);
    const bfs = new Map([[entry, 1]]);
    const queue = [entry];
    while (queue.length) {
        const name = queue.shift();
        for (const dep of graph.get(name) || []) {
            if (!bfs.has(dep)) { bfs.set(dep, bfs.get(name) + 1); queue.push(dep); }
        }
    }
    const fetchLevels = Math.max(...bfs.values());
    const reach = new Set();
    const walk = name => {
        if (reach.has(name)) return;
        reach.add(name);
        for (const dep of graph.get(name) || []) walk(dep);
    };
    walk(entry);
    let bytes = 0;
    let gzipBytes = 0;
    for (const name of reach) {
        const body = readFileSync(path.join(root, 'js', name));
        bytes += body.length;
        gzipBytes += zlib.gzipSync(body, { level: 1 }).length;
    }
    const preloads = [...html.matchAll(/<link\s+rel="modulepreload"\s+href="([^"]+)"/g)].length;
    return { entry, modules: reach.size, fetchLevels, longestChain: longest, bytes, gzipBytes, preloads };
}

const TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
};

function makeHandler(root, counts) {
    const cache = new Map();
    const load = file => {
        const st = statSync(file);
        const key = `${file}:${st.mtimeMs}:${st.size}`;
        if (!cache.has(key)) {
            const body = readFileSync(file);
            const etag = `"${Math.floor(st.mtimeMs / 1000).toString(16)}-${st.size.toString(16)}"`;
            cache.set(key, { body, gz: zlib.gzipSync(body, { level: 1 }), etag, mtime: st.mtime.toUTCString() });
        }
        return cache.get(key);
    };
    return (req, res) => {
        const url = new URL(req.url, 'http://x');
        let rel = decodeURIComponent(url.pathname);
        if (rel === '/') rel = '/index.html';
        const file = path.join(root, path.normalize(rel));
        if (!file.startsWith(root) || !existsSync(file) || !statSync(file).isFile()) {
            res.writeHead(404, { 'Content-Type': 'application/json' });
            res.end('{"detail":"Not Found"}');
            return;
        }
        const ext = path.extname(file);
        const entry = load(file);
        const headers = { 'Content-Type': TYPES[ext] || 'application/octet-stream', 'Last-Modified': entry.mtime };
        if (/^\/(js|css)\//.test(rel) || rel === '/index.html') headers['Cache-Control'] = 'no-cache';
        if (rel === '/share.html') headers['Cache-Control'] = 'no-store';
        const gzip = /\bgzip\b/.test(req.headers['accept-encoding'] || '') && entry.body.length >= 1000
            && ['.html', '.js', '.css', '.json', '.svg'].includes(ext);
        headers.ETag = gzip ? `W/${entry.etag}` : entry.etag;
        if (gzip) { headers['Content-Encoding'] = 'gzip'; headers.Vary = 'Accept-Encoding'; }
        const inm = req.headers['if-none-match'];
        const notModified = inm
            ? inm.split(',').map(s => s.trim().replace(/^W\//, '')).includes(entry.etag)
            : req.headers['if-modified-since'] === entry.mtime;
        if (notModified) {
            delete headers['Content-Type'];
            delete headers['Content-Encoding'];
            counts[304] = (counts[304] || 0) + 1;
            res.writeHead(304, headers);
            res.end();
            return;
        }
        const body = gzip ? entry.gz : entry.body;
        headers['Content-Length'] = body.length;
        counts[200] = (counts[200] || 0) + 1;
        res.writeHead(200, headers);
        res.end(req.method === 'HEAD' ? undefined : body);
    };
}

function selfSignedCert() {
    const dir = path.join(process.env.TMPDIR || path.join(os.homedir(), '.tmp'), 'frontend_bench');
    mkdirSync(dir, { recursive: true });
    const key = path.join(dir, 'key.pem');
    const cert = path.join(dir, 'cert.pem');
    if (!existsSync(cert)) {
        execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', key, '-out', cert,
            '-days', '30', '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1'], { stdio: 'ignore' });
    }
    const spki = execFileSync('sh', ['-c', `openssl x509 -in '${cert}' -pubkey -noout | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64`]).toString().trim();
    return { key: readFileSync(key), cert: readFileSync(cert), spki };
}

async function startServer(root, protocol, tls) {
    const counts = {};
    const handler = makeHandler(root, counts);
    const server = protocol === 'h2'
        ? http2.createSecureServer({ key: tls.key, cert: tls.cert, allowHTTP1: true }, handler)
        : http.createServer({ keepAliveTimeout: 60000 }, handler);
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const scheme = protocol === 'h2' ? 'https' : 'http';
    return { server, counts, origin: `${scheme}://127.0.0.1:${server.address().port}` };
}

function findChrome() {
    if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
    const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, '/opt/pw-browsers', path.join(os.homedir(), '.cache/ms-playwright')]
        .filter(Boolean);
    for (const dir of roots) {
        if (!existsSync(dir)) continue;
        const builds = readdirSync(dir).filter(n => /^chromium-\d+$/.test(n)).sort().reverse();
        for (const build of builds) {
            const exe = path.join(dir, build, 'chrome-linux64', 'chrome');
            if (existsSync(exe)) return exe;
        }
    }
    for (const exe of ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome']) {
        if (existsSync(exe)) return exe;
    }
    throw new Error('no Chromium found; set CHROME_PATH');
}

async function loadPlaywright() {
    const spec = process.env.PLAYWRIGHT_CORE || 'playwright-core';
    const mod = await import(spec.startsWith('/') ? path.join(spec, 'index.mjs') : spec);
    return mod.chromium || mod.default.chromium;
}

async function measure(context, url, rtt, downKbps, cold, settleMs, counts) {
    for (const key of Object.keys(counts)) delete counts[key];
    const page = await context.newPage();
    const cdp = await context.newCDPSession(page);
    await cdp.send('Network.enable');
    await cdp.send('Network.setCacheDisabled', { cacheDisabled: cold });
    await cdp.send('Network.emulateNetworkConditions', {
        offline: false,
        latency: rtt,
        downloadThroughput: downKbps > 0 ? (downKbps * 1000) / 8 : -1,
        uploadThroughput: -1,
    });
    const requests = new Map();
    cdp.on('Network.requestWillBeSent', e => {
        requests.set(e.requestId, { url: e.request.url, sent: e.timestamp, bytes: 0 });
    });
    cdp.on('Network.responseReceived', e => {
        const r = requests.get(e.requestId);
        if (r) r.protocol = e.response.protocol;
    });
    cdp.on('Network.loadingFinished', e => {
        const r = requests.get(e.requestId);
        if (r) { r.done = e.timestamp; r.bytes = e.encodedDataLength; }
    });
    await page.goto(url, { waitUntil: 'load' });
    await page.waitForTimeout(settleMs);
    const nav = await page.evaluate(() => {
        const [n] = performance.getEntriesByType('navigation');
        const js = performance.getEntriesByType('resource').filter(r => /\/js\/[^/]+\.js(\?|$)/.test(r.name));
        return {
            dcl: n.domContentLoadedEventEnd,
            load: n.loadEventEnd,
            jsDone: js.reduce((m, r) => Math.max(m, r.responseEnd), 0),
        };
    });
    await page.close();
    const all = [...requests.values()];
    const statics = all.filter(r => /\.(js|css|html)(\?|$)|\/$/.test(new URL(r.url).pathname + new URL(r.url).search));
    const js = statics.filter(r => /\/js\//.test(r.url)).sort((a, b) => a.sent - b.sent);
    let waves = js.length ? 1 : 0;
    for (let i = 1; i < js.length; i++) {
        if ((js[i].sent - js[i - 1].sent) * 1000 > Math.max(rtt * 0.5, 5)) waves++;
    }
    return {
        dcl: nav.dcl,
        load: nav.load,
        jsDone: nav.jsDone,
        requests: all.length,
        staticRequests: statics.length,
        jsRequests: js.length,
        served200: counts[200] || 0,
        served304: counts[304] || 0,
        transferred: statics.reduce((s, r) => s + (r.bytes || 0), 0),
        waves,
        protocol: js[0]?.protocol || '',
    };
}

const median = xs => {
    const s = [...xs].sort((a, b) => a - b);
    const m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

async function main() {
    const opts = parseArgs(process.argv.slice(2));
    const stats = graphStats(opts.root, opts.page);
    console.log(`${opts.page}: entry ${stats.entry}, ${stats.modules} modules in the static graph, `
        + `${stats.fetchLevels} fetch levels (longest import chain ${stats.longestChain}), ${(stats.bytes / 1024).toFixed(0)} KiB raw, ${(stats.gzipBytes / 1024).toFixed(0)} KiB gzip, `
        + `${stats.preloads} modulepreload links`);
    const chromium = await loadPlaywright();
    const tls = opts.protocols.includes('h2') ? selfSignedCert() : null;
    const browser = await chromium.launch({
        executablePath: findChrome(),
        headless: true,
        args: ['--disable-extensions', '--no-first-run',
            ...(tls ? [`--ignore-certificate-errors-spki-list=${tls.spki}`] : [])],
    });
    const rows = [];
    try {
        for (const protocol of opts.protocols) {
            const { server, counts, origin } = await startServer(opts.root, protocol, tls);
            try {
                for (const rtt of opts.rtts) {
                    for (const mode of opts.modes) {
                        const samples = [];
                        for (let i = 0; i < opts.runs; i++) {
                            const context = await browser.newContext();
                            const url = `${origin}/${opts.page === 'index.html' ? '' : opts.page}`;
                            if (mode === 'warm') await measure(context, url, rtt, opts.downKbps, false, opts.settleMs, counts);
                            samples.push(await measure(context, url, rtt, opts.downKbps, mode === 'cold', opts.settleMs, counts));
                            await context.close();
                        }
                        const row = { page: opts.page, protocol, rtt, mode, runs: samples.length };
                        for (const key of Object.keys(samples[0])) {
                            row[key] = typeof samples[0][key] === 'number' ? median(samples.map(s => s[key])) : samples[0][key];
                        }
                        row.dclSamples = samples.map(s => Math.round(s.dcl));
                        rows.push(row);
                        console.log(`${protocol} rtt=${rtt}ms ${mode}: DCL ${row.dcl.toFixed(0)} ms, modules done ${row.jsDone.toFixed(0)} ms, `
                            + `load ${row.load.toFixed(0)} ms, ${row.staticRequests} static requests (${row.jsRequests} js, `
                            + `server sent ${row.served200} x 200, ${row.served304} x 304), ${row.waves} js request waves, ${(row.transferred / 1024).toFixed(0)} KiB `
                            + `[${row.protocol}] DCL samples ${row.dclSamples.join(' ')}`);
                    }
                }
            } finally {
                server.close();
            }
        }
    } finally {
        await browser.close();
    }
    if (opts.json) {
        mkdirSync(path.dirname(path.resolve(opts.json)), { recursive: true });
        writeFileSync(opts.json, JSON.stringify({ when: new Date().toISOString(), graph: stats, rows }, null, 2) + '\n');
    }
}

main().catch(err => {
    console.error(err);
    process.exit(1);
});
