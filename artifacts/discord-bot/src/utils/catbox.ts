import fs from 'fs';
import path from 'path';

const ENV_USERHASH = process.env.CATBOX_USERHASH ?? '';

export async function uploadToUguu(filePath: string): Promise<string | null> {
  try {
    const fileBytes = fs.readFileSync(filePath);
    const form = new FormData();
    form.append('files[]', new Blob([fileBytes]), path.basename(filePath));
    const res = await fetch('https://uguu.se/upload.php', {
      method: 'POST',
      body: form,
      signal: AbortSignal.timeout(120_000),
    });
    if (!res.ok) return null;
    const payload = await res.json() as { files?: Array<{ url?: string }> };
    const url = payload.files?.[0]?.url;
    return typeof url === 'string' && url.startsWith('https://') ? url : null;
  } catch {
    return null;
  }
}

export async function _upload_to_catbox(filePath: string, userhash?: string): Promise<string | null> {
  try {
    const hash = userhash ?? ENV_USERHASH;
    const fileBytes = fs.readFileSync(filePath);
    const blob = new Blob([fileBytes]);

    const form = new FormData();
    form.append('reqtype', 'fileupload');
    form.append('userhash', hash);
    form.append('fileToUpload', blob, path.basename(filePath));

    const res = await fetch('https://catbox.moe/user/api.php', {
      method: 'POST',
      body: form,
      signal: AbortSignal.timeout(60_000),
    });

    if (!res.ok) return uploadToUguu(filePath);
    const text = await res.text();
    return text.trim().startsWith('https://') ? text.trim() : uploadToUguu(filePath);
  } catch {
    return uploadToUguu(filePath);
  }
}
