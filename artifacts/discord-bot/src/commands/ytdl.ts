import { Message } from "discord.js";
import { spawn } from "node:child_process";
import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { uploadToCatbox } from "./catboxupload.js";
import { logger } from "../lib/logger.js";

const DISCORD_MAX_BYTES = 8 * 1024 * 1024;
const MAX_FILESIZE_BYTES = 200 * 1024 * 1024;

function runYtDlp(args: string[]): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const proc = spawn("yt-dlp", args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d: Buffer) => { stdout += d.toString(); });
    proc.stderr.on("data", (d: Buffer) => { stderr += d.toString(); });
    proc.on("close", (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(stderr.slice(-800) || `yt-dlp exited with code ${code}`));
    });
    proc.on("error", reject);
  });
}

export async function runYtdl(message: Message): Promise<void> {
  const trimmed = message.content.trim();

  const PREFIXES = ["roxi youtubedownload", "roxi ytdl"];
  const matchedPrefix = PREFIXES.find((p) =>
    trimmed.toLowerCase().startsWith(p + " ") || trimmed.toLowerCase() === p
  );
  if (!matchedPrefix) return;

  const query = trimmed.slice(matchedPrefix.length).trim();

  if (!query) {
    await message.reply(
      "❌ **Usage:** `t!ytdl <URL or search query>` / `t!youtubedownload <URL or search query>`\n" +
      "Examples:\n" +
      "• `t!ytdl https://youtube.com/watch?v=...`\n" +
      "• `t!ytdl never gonna give you up`",
    );
    return;
  }

  const isUrl = /^https?:\/\//i.test(query);
  const target = isUrl ? query : `ytsearch1:${query}`;

  let statusMsg: Message;
  try {
    statusMsg = await message.reply(`⏳ Searching and downloading: \`${query}\`…`);
  } catch { return; }

  const tmpDir = await mkdtemp(join(tmpdir(), "ytdl-"));

  try {
    const outTemplate = join(tmpDir, "%(title).80s.%(ext)s");

    const args = [
      target,
      "-f", "bestvideo[ext=mp4][filesize<?200M]+bestaudio[ext=m4a]/bestvideo[filesize<?200M]+bestaudio/best[filesize<?200M]/best",
      "--merge-output-format", "mp4",
      "--no-playlist",
      "--max-filesize", "200m",
      "--output", outTemplate,
      "--no-warnings",
      "--age-limit", "99",
      "--socket-timeout", "30",
      "--extractor-args", "youtube:player_client=ios,android_vr,web_embedded,tv_embedded",
    ];

    logger.info({ target }, "Starting yt-dlp download");
    await statusMsg.edit(`⏳ Downloading: \`${query}\`…`);

    await runYtDlp(args);

    const files = await readdir(tmpDir);
    const dlFile = files[0];

    if (!dlFile) {
      await statusMsg.edit("❌ Download completed but no output file was found.");
      return;
    }

    const filePath = join(tmpDir, dlFile);
    const fileBuffer = await readFile(filePath);

    if (fileBuffer.length > MAX_FILESIZE_BYTES) {
      await statusMsg.edit(`❌ File is too large (${(fileBuffer.length / 1024 / 1024).toFixed(1)} MB). Max is 200 MB.`);
      return;
    }

    const title = dlFile.replace(/\.[^.]+$/, "");
    const ext = dlFile.match(/\.([^.]+)$/)?.[1] ?? "mp4";
    const safeFilename = `${title.slice(0, 80)}.${ext}`;

    logger.info({ filename: safeFilename, size: fileBuffer.length }, "yt-dlp download complete");

    if (fileBuffer.length <= DISCORD_MAX_BYTES) {
      await statusMsg.delete().catch(() => {});
      const { AttachmentBuilder } = await import("discord.js");
      const attachment = new AttachmentBuilder(fileBuffer, { name: safeFilename });
      await message.reply({ content: `✅ **${title}**`, files: [attachment] });
    } else {
      await statusMsg.edit(`📦 File too large for Discord (${(fileBuffer.length / 1024 / 1024).toFixed(1)} MB) — uploading to catbox.moe…`);
      const catboxUrl = await uploadToCatbox(fileBuffer, safeFilename);
      await statusMsg.delete().catch(() => {});
      await message.reply(`✅ **${title}**\n📦 Too large for Discord → ${catboxUrl}`);
    }
  } catch (err) {
    logger.error({ err }, "t!ytdl failed");
    const msg = err instanceof Error ? err.message : "Unknown error";
    const msgLower = msg.toLowerCase();
    // Classify common yt-dlp errors into user-friendly messages
    if (msgLower.includes("not available") || msgLower.includes("not found")) {
      await statusMsg.edit(`❌ This video is not available. It may have been removed or made private.\n-# \`${msg.slice(0, 200)}\``);
    } else if (msgLower.includes("private")) {
      await statusMsg.edit(`❌ This video is private and cannot be downloaded.\n-# \`${msg.slice(0, 200)}\``);
    } else if (msgLower.includes("age") || msgLower.includes("sign in") || msgLower.includes("inappropriate")) {
      await statusMsg.edit(`❌ This video is age-restricted and cannot be downloaded without authentication.\n-# \`${msg.slice(0, 200)}\``);
    } else if (msgLower.includes("geo") || msgLower.includes("country") || msgLower.includes("region")) {
      await statusMsg.edit(`❌ This video is geo-blocked and not available in this region.\n-# \`${msg.slice(0, 200)}\``);
    } else if (msgLower.includes("copyright") || msgLower.includes("takedown")) {
      await statusMsg.edit(`❌ This video has been removed due to a copyright claim.\n-# \`${msg.slice(0, 200)}\``);
    } else if (msgLower.includes("live") && (msgLower.includes("stream") || msgLower.includes("broadcast"))) {
      await statusMsg.edit(`❌ Live streams cannot be downloaded while in progress.\n-# \`${msg.slice(0, 200)}\``);
    } else if (msgLower.includes("premium") || msgLower.includes("members") || msgLower.includes("subscriber")) {
      await statusMsg.edit(`❌ This video requires a premium/membership and cannot be downloaded.\n-# \`${msg.slice(0, 200)}\``);
    } else if (msgLower.includes("playlist")) {
      await statusMsg.edit(`❌ Playlists are not supported. Please provide a single video URL.\n-# \`${msg.slice(0, 200)}\``);
    } else {
      await statusMsg.edit(`❌ Download failed: \`${msg.slice(0, 400)}\``);
    }
  } finally {
    await rm(tmpDir, { recursive: true, force: true }).catch(() => {});
  }
}
