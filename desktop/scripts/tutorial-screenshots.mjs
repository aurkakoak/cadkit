// Recreate documentation screenshots from the real app and tutorial snapshots.
// Run from desktop: CADKIT_TEST_NO_SANDBOX=1 CADKIT_TEST_SOFTWARE_RENDERING=1
// node scripts/tutorial-screenshots.mjs (requires a display, or xvfb-run on CI).
import { _electron as electron, expect as playwrightExpect } from '@playwright/test';
import { mkdir, mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { electronTestArgs } from './electron-test-options.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.join(root, 'docs/assets/tutorial');
await mkdir(output, { recursive: true });
await mkdir(path.join(root, 'build'), { recursive: true });
const work = await mkdtemp(path.join(root, 'build/tutorial-screenshots-'));
const expect = playwrightExpect.configure({ timeout: 120000 });
const selected = new Set(process.argv.slice(2));

async function capture(snapshot, filename, prepare, transform = source => source) {
  if (selected.size && !selected.has(snapshot)) return;
  const directory = path.join(work, filename.replace('.png', ''));
  await mkdir(directory);
  const source = await readFile(path.join(root, 'examples/tutorial', `${snapshot}.py`), 'utf8');
  await writeFile(path.join(directory, 'enclosure.py'), transform(source));
  const app = await electron.launch({
    args: electronTestArgs([
      path.join(root, 'desktop'), '--project-dir', directory,
      '--project', 'enclosure:PROJECT', '--python', path.join(root, '.venv/bin/python'),
    ], process.env),
    env: { ...process.env, CADKIT_USER_DATA: path.join(directory, 'profile') },
  });
  try {
    const page = await app.firstWindow();
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(1440, 960));
    await expect(page.getByText('Build up to date', { exact: true })).toBeVisible();
    await expect(page.locator('.viewport-host canvas').first()).toBeVisible();
    await page.getByRole('button', { name: 'Isometric view', exact: true }).click();
    await page.getByRole('button', { name: 'Fit visible objects', exact: true }).click();
    await page.locator('.viewport-host').hover();
    await page.mouse.wheel(0, 150);
    await prepare(page);
    // Let the renderer present the UI changes before capturing the native view.
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await page.screenshot({ path: path.join(output, filename), scale: 'css' });
    console.log(`Captured ${filename} from ${snapshot}.py`);
  } finally {
    await app.close();
  }
}

try {
  await capture('02_project', 'box-and-lid.png', async page => {
    await page.getByRole('button', { name: 'Select box', exact: true }).click();
  });
  await capture('02_project', 'box-interior.png', async page => {
    await page.getByRole('button', { name: 'Hide lid', exact: true }).click();
    await page.getByRole('button', { name: 'Select box', exact: true }).click();
  });
  await capture('03_export', 'inspect-and-export.png', async page => {
    await page.getByRole('button', { name: 'Select box', exact: true }).click();
    await page.getByRole('button', { name: 'Select lid', exact: true }).click({ modifiers: ['Shift'] });
    await expect(page.getByLabel('Measurement object A')).toHaveValue(/.+/);
    await expect(page.getByLabel('Measurement object B')).toHaveValue(/.+/);
    await expect(page.getByTestId('measurement-result')).toBeVisible();
  });
  await capture('04_fasteners', 'fasteners.png', async page => {
    await page.getByRole('button', { name: 'Connections', exact: true }).click();
    await page.getByRole('button', { name: 'Inspect fastening lid-mount', exact: true }).click();
    await page.getByLabel('Hardware visibility').selectOption('all');
  });
  await capture('05_checks', 'checks.png', async page => {
    await page.getByRole('button', { name: 'Connections', exact: true }).click();
    await page.getByRole('button', { name: 'Run assembly checks', exact: true }).click();
    await expect(page.locator('.validation-counts[data-validation-status="incomplete"]')).toBeVisible();
  });
  await capture('06_agent', 'taller-box.png', async page => {
    await page.getByRole('button', { name: 'Hide lid', exact: true }).click();
    await page.getByRole('button', { name: 'Select box', exact: true }).click();
  }, source => source.replace('HEIGHT = 20', 'HEIGHT = 24'));
} finally {
  await rm(work, { recursive: true, force: true });
}
