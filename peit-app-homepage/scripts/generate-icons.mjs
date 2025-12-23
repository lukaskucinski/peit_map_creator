// Script to generate PNG favicon files from SVG
import { Resvg } from '@resvg/resvg-js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const publicDir = path.join(__dirname, '..', 'public');

// Landcover icon path from layer-landcover.svg
const landcoverPath = "M49.932 22.56a4.725 2.593 0 0 0-3.274.76L1.383 48.166a4.725 2.593 0 0 0 0 3.668L46.658 76.68a4.725 2.593 0 0 0 6.684 0l45.275-24.846a4.725 2.593 0 0 0 0-3.668L53.342 23.32a4.725 2.593 0 0 0-3.41-.76zM50 28.82l8.713 4.782a25.922 25.922 0 0 0-3.606 1.705c-2.827 1.61-5.458 3.774-6.994 6.636c-6.097-.96-12.326-1.538-18.468-1.953L50 28.82zm15.297 8.395L88.596 50l-7.639 4.191c-7.813-5.86-17.33-9.24-27.441-11.29c1.018-1.175 2.451-2.33 4.064-3.249c2.43-1.383 5.237-2.227 6.963-2.304a2.5 2.5 0 0 0 .754-.133zm-43.793 7.244a2.5 2.5 0 0 0 .506.078c19.426 1.07 40.051 2.978 54.074 12.328l-3.334 1.83c-7.592-4.899-16.302-8.454-27.129-7.892c-6.456.335-13.67 2.145-21.84 5.988L11.406 50l10.098-5.541zm27.258 11.08c7.27.138 13.278 2.534 18.96 5.916L50 71.18L29.277 59.807c7.526-3.144 13.88-4.374 19.485-4.268z";

// Generate SVG with specific colors (with padding for app icons)
function generateSvg(size, bgColor, fgColor, rounded = true) {
  const cornerRadius = rounded ? Math.round(size * 0.2) : 0;
  // Scale factor to fit the 100x100 viewBox icon into the size
  const scale = size / 100 * 0.75;
  const offset = size * 0.125;

  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
  <rect width="${size}" height="${size}" rx="${cornerRadius}" fill="${bgColor}" />
  <g transform="translate(${offset}, ${offset + size * 0.05}) scale(${scale})">
    <path d="${landcoverPath}" fill="${fgColor}" />
  </g>
</svg>`;
}

// Generate SVG cropped tightly to icon bounds (for favicons)
function generateCroppedSvg(size, bgColor, fgColor) {
  // The icon path bounds: x: 1.383 to 98.617, y: 22.56 to 76.68
  // Width: ~97.2, Height: ~54.1
  const iconMinX = 1.383;
  const iconMinY = 22.56;
  const iconWidth = 97.234;  // 98.617 - 1.383
  const iconHeight = 54.12;  // 76.68 - 22.56

  // Minimal horizontal padding (2%), no vertical padding - fill full width
  const hPadding = size * 0.02;
  const availableWidth = size - (hPadding * 2);

  // Scale to fit full width
  const scale = availableWidth / iconWidth;
  const scaledHeight = iconHeight * scale;

  // Center vertically in the square
  const offsetX = hPadding - (iconMinX * scale);
  const offsetY = (size - scaledHeight) / 2 - (iconMinY * scale);

  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
  <rect width="${size}" height="${size}" fill="${bgColor}" />
  <g transform="translate(${offsetX}, ${offsetY}) scale(${scale})">
    <path d="${landcoverPath}" fill="${fgColor}" />
  </g>
</svg>`;
}

// Generate OG image (1200x630 with centered icon and title)
function generateOgSvg() {
  const width = 1200;
  const height = 630;
  const iconSize = 280;

  // Calculate vertical centering for icon + title combo
  // Icon height + gap (50px) + title font size (80px) ≈ 410px total
  const totalContentHeight = iconSize + 50 + 80;
  const startY = (height - totalContentHeight) / 2;

  const iconX = (width - iconSize) / 2;
  const iconY = startY;
  const scale = iconSize / 100 * 0.75;
  const offset = iconSize * 0.125;

  return `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="${width}" height="${height}" fill="#000000" />
  <g transform="translate(${iconX + offset}, ${iconY + offset + iconSize * 0.05}) scale(${scale})">
    <path d="${landcoverPath}" fill="white" />
  </g>
  <text x="${width/2}" y="${iconY + iconSize + 70}" font-family="system-ui, sans-serif" font-size="80" font-weight="bold" fill="white" text-anchor="middle">PEIT Map Creator</text>
</svg>`;
}

async function renderPng(svg, outputPath) {
  const resvg = new Resvg(svg);
  const pngData = resvg.render();
  const pngBuffer = pngData.asPng();
  fs.writeFileSync(outputPath, pngBuffer);
  console.log(`Generated: ${outputPath}`);
}

async function main() {
  console.log('Generating favicon PNG files...\n');

  // 48x48 icons - cropped tightly to fill the space (Google prefers multiples of 48px)
  // For dark browser themes: white icon on transparent
  const darkIcon48 = generateCroppedSvg(48, 'transparent', 'white');
  await renderPng(darkIcon48, path.join(publicDir, 'icon-dark-48x48.png'));

  // For light browser themes: black icon on transparent
  const lightIcon48 = generateCroppedSvg(48, 'transparent', 'black');
  await renderPng(lightIcon48, path.join(publicDir, 'icon-light-48x48.png'));

  // Favicon for Google Search / universal use: black icon on white background
  const favicon48 = generateCroppedSvg(48, 'white', 'black');
  await renderPng(favicon48, path.join(publicDir, 'favicon-48x48.png'));

  // 180x180 Apple icon (white bg with black icon to match app branding)
  const appleIcon = generateSvg(180, 'white', 'black');
  await renderPng(appleIcon, path.join(publicDir, 'apple-icon.png'));

  // OG image for social sharing
  const ogImage = generateOgSvg();
  await renderPng(ogImage, path.join(publicDir, 'og-image.png'));

  // High-res 800x800 PNG for favicon.ico conversion (crisp source)
  const hiRes = generateCroppedSvg(800, 'white', 'black');
  await renderPng(hiRes, path.join(publicDir, 'icon-800x800.png'));

  console.log('\nAll icons generated successfully!');
}

main().catch(console.error);
