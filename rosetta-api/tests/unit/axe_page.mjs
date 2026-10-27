// Runs axe-core (WCAG 2.0-2.2 A and AA rules, target size included) over the page states a
// browser reaches without a run: load, each settings popover, Bench, Auto-Gen, sign-in and
// register, the manual and the share page; and checks that text with a bidi override is moved
// into a <bdi>. Usage: node axe_page.mjs <base url> <node_modules dir> <chrome binary>
// stdout: {states: [{name, violations: [{id, impact, targets}]}], bidi: {...}}
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const [base, modules, chrome] = process.argv.slice(2);
const require = createRequire(join(modules, 'noop.js'));
const { chromium } = require('playwright-core');
const AXE = readFileSync(join(modules, 'axe-core', 'axe.min.js'), 'utf8');
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const states = [];

async function axe(page, name) {
    await page.evaluate(AXE);
    const violations = await page.evaluate(async tags => {
        const res = await window.axe.run(document, { runOnly: { type: 'tag', values: tags }, rules: { 'target-size': { enabled: true } } });
        return res.violations.map(v => ({ id: v.id, impact: v.impact, targets: v.nodes.map(n => ({ target: n.target.join(' '), html: n.html.slice(0, 200) })) }));
    }, TAGS);
    states.push({ name, violations });
}

const browser = await chromium.launch({ executablePath: chrome, headless: true, args: ['--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'] });
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
const page = await context.newPage();
await page.goto(`${base}/`, { waitUntil: 'networkidle' });
await page.waitForTimeout(800);
await axe(page, 'load');
for (const pop of ['pop-backends', 'pop-execution', 'pop-preprocessing', 'pop-compilers', 'pop-thresholds', 'pop-seed']) {
    await page.click(`[data-popover="${pop}"]`);
    await page.waitForTimeout(300);
    await axe(page, pop);
    await page.keyboard.press('Escape');
}
await page.click('#btn-bench');
await page.waitForTimeout(800);
await axe(page, 'bench');
await page.keyboard.press('Escape');
await page.click('#btn-open-generator');
await axe(page, 'auto-gen');
await page.keyboard.press('Escape');
await page.click('#btn-login-modal');
await axe(page, 'sign-in');
await page.click('#btn-show-register');
await axe(page, 'register');
await page.keyboard.press('Escape');

const bidi = await page.evaluate(async () => {
    const host = document.createElement('p');
    host.id = 'bidi-probe';
    host.append('Error: ', '‮gnp.exe', ' (qulacs)');
    const plain = document.createElement('p');
    plain.textContent = 'Qiskit 1.4.4';
    document.getElementById('main-content').append(host, plain);
    await new Promise(r => setTimeout(r, 0));
    return {
        isolated: Array.from(host.childNodes).map(n => n.nodeName),
        text: host.textContent,
        plainUntouched: plain.firstChild?.nodeName === '#text',
    };
});

for (const path of ['/static/docs.html', '/static/share.html']) {
    await page.goto(`${base}${path}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(300);
    await axe(page, path);
}
await browser.close();
process.stdout.write(JSON.stringify({ states, bidi }));
