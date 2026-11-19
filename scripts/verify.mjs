import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import { createReadStream, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';

const base = process.env.BASE_URL || 'http://127.0.0.1:4173';
const out = process.env.REPORT_DIR || 'reports/portfolio/browser';
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || undefined,
  args: ['--no-sandbox'],
});
const results = [];
const problems = [];

try {
  for (const width of [360, 400, 768, 1280, 1536]) {
    for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: theme });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(String(error)));
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
      for (const route of ['/', '/release/']) {
        await page.goto(new URL(route, base).href, { waitUntil: 'networkidle' });
        await page.evaluate(() => document.fonts.ready);
        assert.equal(await page.locator('h1').count(), 1, `${route}: one h1`);
        assert.equal(await page.locator('main').count(), 1, `${route}: one main`);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false,
          `${route} ${width} ${theme}: horizontal overflow`);
        const broken = await page.locator('img').evaluateAll(images => images.filter(image => image.complete && !image.naturalWidth).map(image => image.src));
        assert.deepEqual(broken, [], `${route}: images load`);
        const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
        if (axe.violations.length) problems.push({ route, width, theme, axe: axe.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.map(n => n.target) })) });
        if ([400, 1280].includes(width)) await page.screenshot({ path: `${out}/${route === '/' ? 'home' : 'release'}-${width}-${theme}.png`, fullPage: true });
        results.push({ route, width, theme, axeViolations: axe.violations.length, errors: [...errors] });
      }
      assert.deepEqual(errors, [], `no browser errors at ${width}px ${theme}`);
      await context.close();
    }
  }

  const context = await browser.newContext({ viewport: { width: 400, height: 900 }, reducedMotion: 'reduce', acceptDownloads: true });
  const page = await context.newPage();
  await page.goto(base, { waitUntil: 'networkidle' });
  await page.keyboard.press('Tab');
  const skip = await page.evaluate(() => ({ text: document.activeElement.textContent, href: document.activeElement.getAttribute('href') }));
  assert.match(skip.href || '', /^#/, 'first keyboard destination is skip link');
  await page.keyboard.press('Enter');
  const tabs = page.getByRole('tab');
  assert.ok(await tabs.count() >= 3, 'interactive feature showcase exists');
  for (let i = 0; i < await tabs.count(); i++) {
    const tab = tabs.nth(i);
    await tab.click();
    assert.equal(await tab.getAttribute('aria-selected'), 'true');
    const panelId = await tab.getAttribute('aria-controls');
    assert.ok(panelId, 'tab identifies its panel');
    assert.equal(await page.locator(`#${panelId}`).isVisible(), true);
    assert.equal(await page.getByRole('tab', { selected: true }).count(), 1);
  }
  await tabs.first().focus();
  await page.keyboard.press('ArrowRight');
  const secondFocused = await tabs.nth(1).evaluate(element => document.activeElement === element);
  assert.equal(secondFocused, true, 'arrow keys move through tabs');
  await page.keyboard.press('Enter');
  assert.equal(await tabs.nth(1).getAttribute('aria-selected'), 'true');
  const themeToggle = page.getByRole('button', { name: /theme|dark|light/i }).first();
  assert.ok(await themeToggle.count(), 'theme control exists');
  const before = await page.locator('html').getAttribute('data-theme');
  await themeToggle.click();
  assert.notEqual(await page.locator('html').getAttribute('data-theme'), before, 'theme toggles');
  await page.reload({ waitUntil: 'networkidle' });
  assert.notEqual(await page.locator('html').getAttribute('data-theme'), before, 'chosen theme persists');
  const summary = page.locator('summary').first();
  await summary.focus();
  await page.keyboard.press('Enter');
  assert.equal(await summary.evaluate(element => element.parentElement.open), true, 'FAQ works by keyboard');

  const downloadLink = page.locator('a[href="/release"], a[href="/release/"]').first();
  await downloadLink.click();
  await page.waitForURL(/\/release\/?$/);
  const manifestResponse = await context.request.get(new URL('/release/manifest.json', base).href);
  assert.equal(manifestResponse.status(), 200);
  const manifest = await manifestResponse.json();
  const file = page.locator('a[download]').first();
  assert.ok(await file.count(), 'release exposes a native download link');
  const href = await file.getAttribute('href');
  assert.equal(new URL(href, base).origin, new URL(base).origin, 'APK stays on the website');
  assert.match(href, /^\/release\/files\/MaiChat-.*\.apk$/);
  const [download] = await Promise.all([page.waitForEvent('download'), file.click()]);
  const filePath = await download.path();
  assert.ok(filePath && existsSync(filePath), 'browser downloaded the complete file');
  assert.equal(await download.failure(), null);
  const digest = createHash('sha256');
  for await (const chunk of createReadStream(filePath)) digest.update(chunk);
  const actualHash = digest.digest('hex');
  const expected = manifest.sha256 || manifest.asset?.sha256 || manifest.checksum || manifest.digest?.replace(/^sha256:/, '');
  assert.equal(actualHash, expected, 'download bytes match the official release checksum');
  assert.match(page.url(), /\/release\/?$/, 'download keeps visitor on release page');
  results.push({ path: 'home → release → complete APK download', filename: download.suggestedFilename(), sha256: actualHash });
  await context.close();
  assert.deepEqual(problems, [], 'axe WCAG violations');
  console.log(JSON.stringify({ status: 'PASS', results }, null, 2));
} catch (error) {
  problems.push({ error: String(error), stack: error.stack });
  console.error(error);
  process.exitCode = 1;
} finally {
  writeFileSync(`${out}/results.json`, JSON.stringify({ results, problems }, null, 2));
  await browser.close();
}
