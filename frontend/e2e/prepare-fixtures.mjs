// Generate synthetic preview fixtures in ignored local storage; no real user files.
import { chromium } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const directory = path.resolve(
  import.meta.dirname,
  '../../.cache/stage5-browser-fixtures',
);
fs.mkdirSync(directory, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const page = await browser.newPage();
  const result = await page.evaluate(async () => {
    const canvas = document.createElement('canvas');
    canvas.width = 320;
    canvas.height = 240;
    const context = canvas.getContext('2d');
    context.fillStyle = '#b9adf0';
    context.fillRect(0, 0, 320, 240);
    context.fillStyle = '#263452';
    context.fillRect(60, 60, 200, 120);
    const image = canvas.toDataURL('image/png').split(',')[1];
    const chunks = [];
    const stream = canvas.captureStream(10);
    const recorder = new MediaRecorder(stream, {
      mimeType: 'video/webm;codecs=vp8',
    });
    recorder.ondataavailable = (event) => chunks.push(event.data);
    const done = new Promise((resolve) => {
      recorder.onstop = resolve;
    });
    recorder.start();
    await new Promise((resolve) => setTimeout(resolve, 400));
    context.fillStyle = '#afc7e8';
    context.fillRect(60, 60, 200, 120);
    await new Promise((resolve) => setTimeout(resolve, 400));
    recorder.stop();
    await done;
    stream.getTracks().forEach((track) => track.stop());
    const video = await new Blob(chunks).arrayBuffer();
    return { image, video: Array.from(new Uint8Array(video)) };
  });
  fs.writeFileSync(
    path.join(directory, 'scene.png'),
    Buffer.from(result.image, 'base64'),
  );
  fs.writeFileSync(
    path.join(directory, 'icon.png'),
    Buffer.from(result.image, 'base64'),
  );
  fs.writeFileSync(
    path.join(directory, 'clip.webm'),
    Buffer.from(result.video),
  );
} finally {
  await browser.close();
}
// Two vector-only pages; no font files, external resources or user documents.
function pdfStream(content) {
  return `<< /Length ${Buffer.byteLength(content)} >>\nstream\n${content}endstream`;
}
const objects = [
  '<< /Type /Catalog /Pages 2 0 R /OpenAction << /S /JavaScript /JS (globalThis.stage5PdfExecuted=true) >> >>',
  '<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>',
  '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 500] /Resources << >> /Contents 4 0 R >>',
  pdfStream('0.7 0.6 0.9 rg 40 80 320 340 re f\n'),
  '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 500] /Resources << >> /Contents 6 0 R >>',
  pdfStream('0.6 0.7 0.9 rg 40 80 320 340 re f\n'),
];
let pdf = '%PDF-1.7\n';
const offsets = [0];
for (const [index, object] of objects.entries()) {
  offsets.push(Buffer.byteLength(pdf));
  pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
}
const start = Buffer.byteLength(pdf);
pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
pdf += offsets
  .slice(1)
  .map((offset) => `${String(offset).padStart(10, '0')} 00000 n \n`)
  .join('');
pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${start}\n%%EOF\n`;
fs.writeFileSync(path.join(directory, 'document.pdf'), pdf);
console.log('Synthetic PNG, WebM and two-page PDF fixtures generated.');
