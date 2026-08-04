---
name: Discord voice-message payload
description: Native voice-message upload constraints in the installed discord.py version.
---

The installed discord.py 2.7.1 does not expose `MessageFlags(voice_message=True)` or a `flags` argument on `Messageable.send`. Native voice messages therefore require the HTTP multipart message endpoint with raw `flags: 8192`, an Ogg/Opus attachment, and attachment metadata containing `duration_secs` and a base64 waveform.

**Why:** Sending the Ogg file through the normal `discord.File` API creates a regular audio attachment, not Discord's voice-message UI.

**How to apply:** Keep the low-level upload isolated, use mono 48 kHz Opus at an appropriate voice bitrate, generate and normalize a 256-sample RMS waveform, and fail explicitly if Discord rejects the raw payload rather than silently downgrading.

Native voice messages require Discord's three-stage upload flow: reserve the attachment at `/channels/{id}/attachments`, PUT the Ogg bytes to the returned upload URL, then send a JSON-only message referencing `uploaded_filename` with flag 8192 and waveform metadata. A direct multipart message upload can produce a voice message without a visible waveform.