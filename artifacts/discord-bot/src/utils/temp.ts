import fs from 'fs';
import path from 'path';
import os from 'os';
import { randomUUID } from 'crypto';

export function makeTempDir(prefix: string): string {
  const dir = path.join(os.tmpdir(), `ihtx_${prefix}_${randomUUID()}`);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export function cleanupDir(dir: string): void {
  try {
    fs.rmSync(dir, { recursive: true, force: true });
  } catch {
  }
}

export function listDir(dir: string): string[] {
  try {
    return fs.readdirSync(dir).map((f) => path.join(dir, f));
  } catch {
    return [];
  }
}

export function fileSize(filePath: string): number {
  try {
    return fs.statSync(filePath).size;
  } catch {
    return 0;
  }
}

export async function downloadUrl(url: string, destPath: string): Promise<void> {
  const { default: https } = await import('https');
  const { default: http } = await import('http');
  const parsed = new URL(url);
  const client = parsed.protocol === 'https:' ? https : http;

  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(destPath);
    client.get(url, (res) => {
      if (res.statusCode !== 200) {
        reject(new Error(`HTTP ${res.statusCode ?? '?'} downloading attachment`));
        return;
      }
      res.pipe(file);
      file.on('finish', () => file.close(() => resolve()));
      file.on('error', reject);
    }).on('error', reject);
  });
}
