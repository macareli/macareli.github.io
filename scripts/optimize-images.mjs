// Generate delivery copies only; preserve the unaltered native Android PNGs.
import sharp from 'sharp';
import { stat } from 'node:fs/promises';

const all = ['chat', 'studio', 'discover', 'home'];
const selected = process.argv.slice(2);
for (const name of selected.length ? selected : all) {
  if (!all.includes(name)) throw new Error(`Unknown capture: ${name}`);
  const source = `assets/images/${name}.png`;
  const metadata = await sharp(source).metadata();
  if (metadata.width !== 1440 || metadata.height !== 3120) {
    throw new Error(`${source} must be a fresh 1440 × 3120 native capture`);
  }
  for (const width of [240, 320, 480, 720, 1440]) {
    const destination = `assets/images/${name}-${width}.webp`;
    await sharp(source).resize({ width, withoutEnlargement: true }).webp({ quality: 92, effort: 6 }).toFile(destination);
    console.log(`${destination}: ${(await stat(destination)).size.toLocaleString()} bytes`);
  }
}
