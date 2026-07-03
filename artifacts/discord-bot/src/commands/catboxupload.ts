const ENV_USERHASH = process.env.CATBOX_USERHASH ?? '';

export async function uploadToCatbox(buffer: Buffer, filename: string, userhash?: string): Promise<string> {
  const hash = userhash ?? ENV_USERHASH;
  const blob = new Blob([new Uint8Array(buffer)]);

  const form = new FormData();
  form.append('reqtype', 'fileupload');
  form.append('userhash', hash);
  form.append('fileToUpload', blob, filename);

  const res = await fetch('https://catbox.moe/user/api.php', {
    method: 'POST',
    body: form,
    signal: AbortSignal.timeout(120_000),
  });

  if (!res.ok) throw new Error(`catbox.moe returned HTTP ${res.status}`);
  const text = await res.text();
  if (!text.trim().startsWith('https://')) throw new Error(`Unexpected catbox response: ${text.slice(0, 200)}`);
  return text.trim();
}
