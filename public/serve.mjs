import http from 'http';
import fs from 'fs';
import fsp from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import { tmpdir } from 'os';
import { randomBytes } from 'crypto';
import { spawn, execFile } from 'child_process';

const __dirname  = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT  = path.resolve(__dirname, '..');
const PORT       = process.env.PORT ? parseInt(process.env.PORT) : 8080;
const TMP        = tmpdir();
const MAX_UPLOAD = 150 * 1024 * 1024;

const TVSIM_MAP  = path.join(REPO_ROOT, 'bot', 'displacemaps', 'tvsimulator.mov');
const FILEAA_BIN = path.join(REPO_ROOT, 'bot', 'fileaa');
const EQ_SAMPLE  = 'https://file.garden/aTXso15ukD3mnuPI/nbfx_earthquake.mp4';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css':  'text/css',
  '.js':   'application/javascript',
  '.json': 'application/json',
  '.png':  'image/png',
  '.svg':  'image/svg+xml',
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function runFFmpeg(args, timeoutMs = 300_000) {
  return new Promise((resolve, reject) => {
    const stderr = [];
    const proc = spawn('ffmpeg', ['-hide_banner', '-loglevel', 'error', ...args]);
    proc.stderr.on('data', d => stderr.push(d.toString()));
    proc.on('close', code => {
      if (code === 0) resolve();
      else reject(new Error(stderr.join('').slice(-3000)));
    });
    proc.on('error', reject);
    if (timeoutMs) setTimeout(() => { proc.kill(); reject(new Error('ffmpeg timeout')); }, timeoutMs);
  });
}

function runCmd(bin, args, timeoutMs = 120_000) {
  return new Promise((resolve, reject) => {
    execFile(bin, args, { timeout: timeoutMs }, (err, stdout, stderr) => {
      if (err) reject(new Error(stderr || err.message));
      else resolve(stdout);
    });
  });
}

function ffprobeInfo(filePath) {
  return new Promise((resolve, reject) => {
    const proc = spawn('ffprobe', [
      '-v', 'quiet', '-print_format', 'json',
      '-show_streams', '-show_format', filePath,
    ]);
    let out = '';
    proc.stdout.on('data', d => out += d);
    proc.on('close', () => {
      try {
        const data = JSON.parse(out);
        const vs = data.streams?.find(s => s.codec_type === 'video') || {};
        const as = data.streams?.find(s => s.codec_type === 'audio') || {};
        const dur = parseFloat(data.format?.duration || vs.duration || '0');
        const [fn, fd] = (vs.r_frame_rate || '30/1').split('/');
        const fps = parseFloat(fn) / (parseFloat(fd) || 1);
        resolve({
          width:    vs.width  || 0,
          height:   vs.height || 0,
          duration: isFinite(dur) ? dur : 0,
          fps:      isFinite(fps) && fps > 0 ? fps : 30,
          hasAudio: !!as.codec_type,
          hasVideo: !!vs.codec_type,
        });
      } catch { reject(new Error('ffprobe parse error')); }
    });
    proc.on('error', reject);
  });
}

function tmpPath(id, ext) { return path.join(TMP, `ihtx_${id}${ext}`); }

// Intermediate step: re-encodes to mkv for lossless-ish quality between steps
async function encodeStep(inPath, outPath, vf, af, isImage) {
  if (isImage) {
    const args = ['-y', '-i', inPath];
    if (vf) args.push('-vf', vf);
    args.push('-frames:v', '1', outPath);
    await runFFmpeg(args);
    return;
  }
  const args = ['-y', '-i', inPath];
  if (vf) args.push('-vf', vf);
  if (af) args.push('-af', af);
  args.push(
    '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '10',
    '-c:a', 'pcm_s16le',
    '-max_muxing_queue_size', '1024',
    outPath,
  );
  await runFFmpeg(args);
}

async function encodeFinal(inPath, outPath, vf, af, isImage) {
  if (isImage) {
    const args = ['-y', '-i', inPath];
    if (vf) args.push('-vf', vf);
    args.push('-frames:v', '1', '-q:v', '2', outPath);
    await runFFmpeg(args);
    return;
  }
  const args = ['-y', '-i', inPath];
  if (vf) args.push('-vf', vf);
  if (af) args.push('-af', af);
  args.push(
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
    '-c:a', 'aac', '-b:a', '128k',
    '-movflags', '+faststart',
    '-max_muxing_queue_size', '1024',
    '-pix_fmt', 'yuv420p',
    outPath,
  );
  await runFFmpeg(args);
}

// ─── Format export helper ─────────────────────────────────────────────────────

const FORMAT_MIME = {
  'mp4': 'video/mp4', 'webm': 'video/webm', 'mov': 'video/quicktime', 'mkv': 'video/x-matroska',
  'gif': 'image/gif', 'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'flac': 'audio/flac',
  'ogg': 'audio/ogg', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp',
};

async function exportTo(inPath, outPath, fmt, info, isImage) {
  const fmtNorm = fmt.toLowerCase().replace(/^\./, '');
  const args = ['-y'];
  if (isImage) {
    args.push('-i', inPath, '-frames:v', '1');
  } else {
    args.push('-i', inPath);
  }

  switch (fmtNorm) {
    case 'mp4':
      args.push('-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'aac', '-b:a', '128k', '-pix_fmt', 'yuv420p', '-movflags', '+faststart');
      break;
    case 'webm':
      args.push('-c:v', 'libvpx-vp9', '-deadline', 'good', '-cpu-used', '4', '-b:v', '0', '-crf', '30', '-c:a', 'libopus', '-b:a', '128k', '-pix_fmt', 'yuv420p');
      break;
    case 'mov':
      args.push('-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'aac', '-b:a', '128k', '-pix_fmt', 'yuv420p');
      break;
    case 'mkv':
      args.push('-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'flac', '-pix_fmt', 'yuv420p');
      break;
    case 'gif':
      args.push('-vf', 'split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse', '-loop', '0');
      break;
    case 'mp3':
      args.push('-vn', '-c:a', 'libmp3lame', '-b:a', '192k');
      break;
    case 'wav':
      args.push('-vn', '-c:a', 'pcm_s16le');
      break;
    case 'flac':
      args.push('-vn', '-c:a', 'flac');
      break;
    case 'ogg':
      args.push('-vn', '-c:a', 'libopus', '-b:a', '128k');
      break;
    case 'jpg': case 'jpeg':
      args.push('-q:v', '2', '-pix_fmt', 'yuvj420p');
      break;
    case 'png':
      args.push('-compression_level', '3');
      break;
    case 'webp':
      args.push('-q:v', '85');
      break;
    default:
      args.push('-c:a', 'aac', '-b:a', '128k', '-c:v', 'libx264', '-crf', '23', '-pix_fmt', 'yuv420p');
  }

  args.push(outPath);
  await runFFmpeg(args);
}

// ─── Duration / repetitions / trim helper ─────────────────────────────────────

async function applyPostEffects(inPath, outPath, { reps, duration, noTrim, format }, info, tmpDir) {
  const isAudioOnly = ['mp3', 'wav', 'flac', 'ogg'].includes(format);
  const isImageFmt  = ['jpg', 'jpeg', 'png', 'webp'].includes(format);
  const isImageInput = !info.hasVideo && !info.hasAudio && /\.(jpg|jpeg|png|webp|gif|bmp)$/i.test(inPath);
  const isImage = isImageFmt || isImageInput;
  const isVideo = !isImage && !isAudioOnly;

  let current = inPath;
  let stepN = 0;
  const step = (ext) => tmpPath(`post_${stepN++}`, ext);

  // 1) Duration trimming / looping
  if (!noTrim && duration && isFinite(parseFloat(duration)) && parseFloat(duration) > 0) {
    const target = parseFloat(duration);
    const inputDur = info.duration || 0;
    stepN++;
    const outDur = step(isVideo ? '.mkv' : (isImage ? '.png' : '.wav'));
    if (target < inputDur || target > inputDur * 1.01) {
      // Need to trim or loop; use stream_loop for loop-friendly media and -t target
      if (isVideo) {
        await runFFmpeg(['-y', '-stream_loop', '-1', '-i', current, '-t', String(target),
          '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'aac', '-b:a', '128k',
          '-pix_fmt', 'yuv420p', outDur]);
      } else if (isImage) {
        // For images, just re-encode to the chosen format; duration irrelevant
        await runFFmpeg(['-y', '-i', current, '-frames:v', '1', outDur]);
      } else {
        // Audio: trim/loop with apad
        await runFFmpeg(['-y', '-i', current, '-filter_complex',
          `[0:a]aloop=loop=-1:size=2147483647,atrim=0:${target}[a]`,
          '-map', '[a]', '-c:a', 'pcm_s16le', outDur]);
      }
      current = outDur;
    } else if (target < inputDur) {
      // Just trim shorter
      if (isVideo) {
        await runFFmpeg(['-y', '-i', current, '-t', String(target),
          '-c:v', 'copy', '-c:a', 'copy', outDur]);
      } else if (isAudioOnly) {
        await runFFmpeg(['-y', '-i', current, '-t', String(target), '-c:a', 'copy', outDur]);
      } else {
        await runFFmpeg(['-y', '-i', current, '-frames:v', '1', outDur]);
      }
      current = outDur;
    }
  }

  // 2) Repetitions (concat loop)
  if (reps > 1 && !isImage) {
    stepN++;
    const outRep = step(isVideo ? '.mkv' : '.wav');
    // Build concat list file
    const listFile = path.join(tmpDir, `concat_list_${stepN}.txt`);
    const list = [];
    for (let i = 0; i < reps; i++) list.push(`file '${current.replace(/'/g, "'\\''")}'`);
    await fsp.writeFile(listFile, list.join('\n'));
    await runFFmpeg(['-y', '-f', 'concat', '-safe', '0', '-i', listFile,
      '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
      '-c:a', 'aac', '-b:a', '128k', '-pix_fmt', 'yuv420p', outRep]);
    await fsp.unlink(listFile).catch(() => {});
    current = outRep;
  }

  // 3) Final export to requested format
  await exportTo(current, outPath, format, info, isImage);
  return { isImage, isAudioOnly, isVideo };
}

// ─── Wave presets (exact from bot) ────────────────────────────────────────────
const WAVE_PRESETS = {
  large:         `format=yuv444p,geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*5.4)))*(-15*2)),Y-((sin((T*5*0+(0*15))+(X/W)*(PI*5.4)))*(-15*2)))',setsar=1:1,format=yuv420p`,
  medium:        `format=yuv444p,geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*14)))*(-15*2)),Y-((sin((T*5*0+(0*15))+(X/W)*(PI*14)))*(-15*2)))',setsar=1:1,format=yuv420p`,
  small:         `format=yuv444p,geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*20)))*(-15*1.2)),Y-((sin((T*5*0+(0*15))+(X/W)*(PI*20)))*(-15*1.2)))',setsar=1:1,format=yuv420p`,
  horizontalonly:`format=yuv444p,geq='p(X-((sin((T*5*0+(0.053*15))+(Y/H)*(PI*10)))*(-15*1.5)),Y-((sin((T*5*0+(0*15))+(X/W)*(PI*0)))*(-15*0)))',setsar=1:1,format=yuv420p`,
  verticalonly:  `format=yuv444p,geq='p(X-((sin((T*5*0+(0*15))+(Y/H)*(PI*0)))*(-15*0)),Y-((sin((T*5*0+(0.053*15))+(X/W)*(PI*10)))*(-15*1.6)))',setsar=1:1,format=yuv420p`,
};

// ─── Effect resolver ──────────────────────────────────────────────────────────
// Returns one of:
//   { kind:'vf', filter }                       — batchable video filter
//   { kind:'af', filter }                       — batchable audio filter
//   { kind:'vf+af', vf, af }                    — both (e.g. speed, vreverse)
//   { kind:'fc', fc, maps?, extra? }            — filter_complex (own step)
//   { kind:'run', fn: async(inPath,outPath,tmpDir) }  — arbitrary multi-step
//   { kind:'skip', reason }                     — unsupported

function resolveEffect(name, val) {
  const NOISE = 'noise=alls=40:allf=t+u';
  const SHAKE = 'crop=iw-20:ih-20:10+5*sin(t*30):10+5*cos(t*17),scale=iw+20:ih+20';

  switch (name) {
    // ── Presets ───────────────────────────────────────────────────────────────
    case 'chaos':
      return { kind:'vf', filter:`${SHAKE},${NOISE},hue=h=t*180:s=2,eq=contrast=1.5:brightness=0.05:saturation=3` };
    case 'glitch':
      return { kind:'vf', filter:`rgbashift=rh=8:rv=-8:gh=-4:gv=4:bh=6:bv=-6,${NOISE},eq=contrast=1.8:saturation=0` };
    case 'shake':
      return { kind:'vf', filter:`${SHAKE},${NOISE},eq=contrast=1.3:saturation=1.5` };
    case 'static':
      return { kind:'vf', filter:`${NOISE},curves=vintage,eq=contrast=1.2` };
    case 'melt':
      return { kind:'vf', filter:`perspective=x0=0:y0=0:x1=iw:y1=20*sin(t*3):x2=0:y2=ih:x3=iw:y3=ih-20*sin(t*3),${NOISE}` };
    case 'corrupt':
      return { kind:'vf', filter:`drawgrid=x=0:y=0:w=iw:h=5:t=1:color=white@0.1,${NOISE},eq=gamma=1.5:saturation=0.3:contrast=2` };

    // ── Rainbow ───────────────────────────────────────────────────────────────
    case 'rainbow':
      return { kind:'fc',
        fc: '[0:v]split=3[r][g][b];[r]lutrgb=r=val:g=0:b=0,pad=iw+6:ih:3:0[ro];[g]lutrgb=r=0:g=val:b=0[go];[b]lutrgb=r=0:g=0:b=val,pad=iw+6:ih:0:0[bo];[ro][go]blend=all_mode=addition[rg];[rg][bo]blend=all_mode=addition[outv]',
        maps: ['[outv]', '0:a?'],
      };

    // ── Mirror ────────────────────────────────────────────────────────────────
    case 'mirror': {
      const mode = (val || 'left').toLowerCase();
      let fc;
      if (mode === 'top') {
        fc = '[0:v]split[_ma][_mb];[_ma]crop=iw:ih/2:0:0[_mT];[_mb]crop=iw:ih/2:0:0,vflip[_mB];[_mT][_mB]vstack[outv]';
      } else if (mode === 'bottom') {
        fc = '[0:v]split[_ma][_mb];[_ma]crop=iw:ih/2:0:ih/2[_mT];[_mb]crop=iw:ih/2:0:ih/2,vflip[_mB];[_mT][_mB]vstack[outv]';
      } else { // left (default) / right
        fc = '[0:v]split[_ma][_mb];[_ma]crop=iw/2:ih:0:0[_mL];[_mb]crop=iw/2:ih:0:0,hflip[_mR];[_mL][_mR]hstack[outv]';
      }
      return { kind:'fc', fc, maps:['[outv]','0:a?'] };
    }

    // ── SRW ───────────────────────────────────────────────────────────────────
    case 'sierpinskiransomware': case 'srw':
      return {
        kind: 'run',
        fn: async (inPath, outPath, _tmpDir) => {
          const info = await ffprobeInfo(inPath);
          const d  = info.duration > 0 ? info.duration.toFixed(6) : '10';
          const fr = Math.round(info.fps) || 30;
          const fc = (
            `[0:v]null,trim=0:${d}[outv1];[0:a]atrim=0:${d}[outa1];`+
            `[0:v]trim=0:${d}[v1];[0:v]negate,trim=0:${d}[v2];`+
            `[v1][v2]concat=2:1:0,setpts=1/2*PTS,fps=${fr},trim=0:${d}[outv2];`+
            `[0:a]rubberband=pitch=2:tempo=2,atrim=0:${d}[a1];`+
            `[0:a]rubberband=pitch=2:tempo=2,atrim=0:${d}[a2];`+
            `[a1][a2]concat=2:0:1,atrim=0:${d}[outa2];`+
            `[0:v]null,trim=0:${d}[v3];[0:v]negate,trim=0:${d}[v4];`+
            `[v3][v4]concat=2:1:0,setpts=1/1.333*PTS,fps=${fr},trim=0:${d}[outv3];`+
            `[0:a]rubberband=pitch=1.333:tempo=1.333,atrim=0:${d}[a3];`+
            `[0:a]rubberband=pitch=1.333:tempo=1.333,atrim=0:${d}[a4];`+
            `[a3][a4]concat=2:0:1,atrim=0:${d}[outa3];`+
            `[0:v]setpts=1/0.5*PTS,fps=${fr},trim=0:${d}[outv4];`+
            `[0:a]rubberband=pitch=0.5:tempo=0.5,atrim=0:${d}[outa4];`+
            `[outv1][outv2]hstack[tmp1];[outv3][outv4]hstack[tmp2];`+
            `[tmp1][tmp2]vstack,scale=iw/2:ih/2[outv];`+
            `[outa1][outa2][outa3][outa4]amix=inputs=4,alimiter=level_in=2:latency=1,highpass=f=40[outa]`
          );
          await runFFmpeg(['-y','-i',inPath,'-filter_complex',fc,
            '-map','[outv]','-map','[outa]',
            '-c:v','libx264','-preset','ultrafast','-crf','23',
            '-c:a','aac','-pix_fmt','yuv420p',outPath]);
        },
      };

    // ── TV Simulator ──────────────────────────────────────────────────────────
    case 'tvsim': case 'tv':
      return {
        kind: 'run',
        fn: async (inPath, outPath) => {
          const ps = val.split(':');
          const lineSync   = Math.max(0, Math.min(1, parseFloat(ps[0]) || 0.5));
          const detailZoom = parseFloat(ps[1]) || 1.0;
          const info = await ffprobeInfo(inPath);
          const w = info.width  || 854;
          const h = info.height || 480;
          const contrast = (1.0 - lineSync) * 2.366666;
          const fc = (
            `[0]scale=854:854,format=bgr32[_tv00];`+
            `[1]crop=iw:ih/${detailZoom}:0:0,scale=854:854,`+
            `eq=contrast=${contrast.toFixed(6)},format=bgr32,hue=b=-0.033[_tvx];`+
            `color=s=854x854:c=gray,format=bgr32[_tvy];`+
            `[_tv00][_tvx][_tvy]displace=edge=wrap,scale=${w}:${h},setsar=1,format=yuv444p`
          );
          await runFFmpeg(['-y','-i',inPath,'-stream_loop','-1','-i',TVSIM_MAP,
            '-filter_complex',fc,'-map','0:a?','-pix_fmt','yuv420p',
            '-c:v','libx264','-preset','ultrafast','-crf','23','-c:a','aac',outPath]);
        },
      };

    // ── Earthquake ────────────────────────────────────────────────────────────
    case 'earthquake': case 'nbfx':
      return {
        kind: 'run',
        fn: async (inPath, outPath, tmpDir) => {
          const info = await ffprobeInfo(inPath);
          const w   = info.width  || 1920;
          const h   = info.height || 1080;
          const fr  = Math.round(info.fps) || 30;
          const dur = Math.min(info.duration || 5, 30);
          const trf = path.join(tmpDir, `eq_${randomBytes(4).toString('hex')}.trf`);
          // Pass 1: detect transforms from earthquake sample
          await runFFmpeg(['-y','-stream_loop','-1','-i',EQ_SAMPLE,
            '-vf',`fps=${fr},scale=${w}:${h},setsar=1:1,vidstabdetect=shakiness=10:accuracy=1:mincontrast=0:show=0:result=${trf}`,
            '-c:v','libx264','-preset','ultrafast','-t',String(dur),'-f','null','-']);
          // Pass 2: apply inverted (=destabilize) transform
          await runFFmpeg(['-y','-i',inPath,
            '-vf',`format=yuv444p,vidstabtransform=input=${trf}:optalgo=avg:optzoom=0:zoom=15:invert=1,scale=iw:ih,format=yuv420p`,
            '-c:v','libx264','-preset','fast','-crf','23','-c:a','copy',outPath]);
          await fsp.unlink(trf).catch(() => {});
        },
      };

    // ── Multipitch2 ───────────────────────────────────────────────────────────
    case 'multipitch2': case 'mp2': case 'multipitch3': case 'mp3': {
      // Parse semitones: "1|7|8" or "-3|0|3" or "0|7"
      const semStr = val || '0|7';
      const semitones = semStr.split(/[|,\s]+/).map(Number).filter(n => !isNaN(n));
      if (!semitones.length) return { kind:'skip', reason:'mp2: no valid pitches' };
      const n = semitones.length;
      const PCM = 'aformat=sample_fmts=s16:sample_rates=44100,';
      const RB  = 'rubberband=tempo=1:formant=6942000/634';
      let fc;
      if (n === 1) {
        const pitch = Math.pow(2, semitones[0] / 12).toFixed(6);
        fc = `[0:a]${PCM}${RB}:pitch=${pitch},asetpts=PTS-STARTPTS[mp2aout]`;
      } else {
        const inLabels  = semitones.map((_, j) => `[mp2ps${j}]`).join('');
        const split     = `[0:a]${PCM}asplit=${n}${inLabels}`;
        const chains    = semitones.map((st, j) => {
          const pitch = Math.pow(2, st / 12).toFixed(6);
          return `[mp2ps${j}]${RB}:pitch=${pitch},asetpts=PTS-STARTPTS,dynaudnorm[mp2rb${j}]`;
        });
        const mixIn = semitones.map((_, j) => `[mp2rb${j}]`).join('');
        const mix   = `${mixIn}amix=inputs=${n}:normalize=0[mp2aout]`;
        fc = [split, ...chains, mix].join(';');
      }
      return {
        kind: 'run',
        fn: async (inPath, outPath) => {
          await runFFmpeg(['-y','-i',inPath,'-filter_complex',fc,
            '-map','0:v?','-map','[mp2aout]',
            '-c:v','copy','-c:a','pcm_s16le',outPath]);
        },
      };
    }

    // ── Multipitch (uses bot/fileaa binary) ───────────────────────────────────
    case 'multipitch': case 'mp': case 'multi': {
      const semStr = val || '0|7|-7';
      const semitones = semStr.split(/[|,\s]+/).map(Number).filter(n => !isNaN(n));
      if (!semitones.length) return { kind:'skip', reason:'multipitch: no pitches' };
      return {
        kind: 'run',
        fn: async (inPath, outPath, tmpDir) => {
          const id  = randomBytes(4).toString('hex');
          const info = await ffprobeInfo(inPath);
          // Extract audio
          const wavIn = tmpPath(`mp_in_${id}`, '.wav');
          await runFFmpeg(['-y','-i',inPath,wavIn]);
          // Run fileaa for each semitone voice
          const voices = [];
          for (let i = 0; i < semitones.length; i++) {
            const st  = semitones[i];
            const out = tmpPath(`mp_v${i}_${id}`, '.wav');
            await runCmd(FILEAA_BIN, ['-3', `-p${st.toFixed(4)}`, '-t1', wavIn, out]);
            voices.push(out);
          }
          // Mix voices with amix
          const mixedAudio = tmpPath(`mp_mix_${id}`, '.wav');
          const ffArgs = ['-y'];
          for (const v of voices) ffArgs.push('-i', v);
          ffArgs.push('-filter_complex', `amix=inputs=${voices.length}:normalize=0`, mixedAudio);
          await runFFmpeg(ffArgs);
          // Remux video + mixed audio
          if (info.hasVideo) {
            await runFFmpeg(['-y','-i',inPath,'-i',mixedAudio,
              '-map','0:v','-map','1:a','-c:v','copy','-c:a','pcm_s16le',outPath]);
          } else {
            await fsp.copyFile(mixedAudio, outPath);
          }
          // Cleanup
          await Promise.all([wavIn, ...voices, mixedAudio].map(f => fsp.unlink(f).catch(()=>{})));
        },
      };
    }

    // ── Gradient Map ──────────────────────────────────────────────────────────
    case 'gradientmap': case 'gmap': case 'gm': {
      const colorStr = val || '#000000,#ffffff';
      const colors   = colorStr.split(',').map(c => c.trim()).filter(Boolean);
      const parsed   = colors.map(c => {
        if (c.startsWith('#') && c.length >= 7) {
          return [parseInt(c.slice(1,3),16)/255, parseInt(c.slice(3,5),16)/255, parseInt(c.slice(5,7),16)/255];
        }
        const nc = { black:[0,0,0], white:[1,1,1], red:[1,0,0], green:[0,0.5,0], lime:[0,1,0],
          blue:[0,0,1], yellow:[1,1,0], cyan:[0,1,1], magenta:[1,0,1],
          orange:[1,0.65,0], purple:[0.5,0,0.5], pink:[1,0.75,0.8] };
        return nc[c.toLowerCase()] || [0,0,0];
      });
      if (parsed.length < 2) return { kind:'skip', reason:'gradientmap: need ≥2 colors' };
      const stops = parsed.map(([r,g,b], i) => ({ r, g, b, pos: i/(parsed.length-1) }));
      const rC = stops.map(s => `${s.pos.toFixed(4)}/${s.r.toFixed(4)}`).join(' ');
      const gC = stops.map(s => `${s.pos.toFixed(4)}/${s.g.toFixed(4)}`).join(' ');
      const bC = stops.map(s => `${s.pos.toFixed(4)}/${s.b.toFixed(4)}`).join(' ');
      return { kind:'vf', filter:`format=gray,curves=r='${rC}':g='${gC}':b='${bC}',format=yuv420p` };
    }

    // ── Swirl ─────────────────────────────────────────────────────────────────
    case 'swirl': {
      const strength = parseFloat(val) || 180;
      const radius   = 0.5, xc = 0.5, yc = 0.5;
      const atten   = `(if(lt(hypot(X-W*${xc},Y-H*${yc})+1e-6,min(W,H)*${radius}),1-(hypot(X-W*${xc},Y-H*${yc})+1e-6)/(min(W,H)*${radius}),0)^2)`;
      const angle   = `((${strength})*(PI^2)*(-255/180))`;
      const ccos    = `cos((atan2(Y-H*${yc},X-W*${xc}))+${angle}*${atten})`;
      const csin    = `sin((atan2(Y-H*${yc},X-W*${xc}))+${angle}*${atten})`;
      const geq     = `geq='p(W*${xc}+(hypot(X-W*${xc},Y-H*${yc})+1e-6)*${ccos},H*${yc}+(hypot(X-W*${xc},Y-H*${yc})+1e-6)*${csin})'`;
      // Needs own step because we need to square-scale first (dimension-dependent)
      return {
        kind: 'run',
        fn: async (inPath, outPath) => {
          const info = await ffprobeInfo(inPath);
          const w = info.width || 854, h = info.height || 480;
          const vf = `format=yuv444p,scale=${h}:${h},${geq},scale=${w}:${h},setsar=1:1,format=yuv420p`;
          const args = ['-y', '-i', inPath, '-vf', vf,
            '-c:v','libx264','-preset','fast','-crf','23','-c:a','copy',outPath];
          await runFFmpeg(args);
        },
      };
    }

    // ── CCShue (ImageMagick haldclut) ─────────────────────────────────────────
    case 'ccshue': {
      const ps = val.split(':');
      const hue    = parseFloat(ps[0]) || 0;
      const sat    = parseFloat(ps[1]) || 1;
      const gamma  = parseFloat(ps[2]) || 1;
      const gain   = parseFloat(ps[3]) || 1;
      const offset = parseFloat(ps[4]) || 0;
      return {
        kind: 'run',
        fn: async (inPath, outPath, tmpDir) => {
          const id      = randomBytes(4).toString('hex');
          const haldPpm = path.join(tmpDir, `ccs_${id}.ppm`);
          const cmd     = ['hald:8'];
          if (Math.abs(hue) > 0.001) {
            const afxHue = `angle=${hue}*pi/180; channel(u,.5+(u.g-.5)*cos(angle)-(u.b-.5)*sin(angle),.5+(u.g-.5)*sin(angle)+(u.b-.5)*cos(angle))`;
            cmd.push('-colorspace','yuv','-fx',afxHue,'-colorspace','srgb');
          }
          if (Math.abs(sat - 1) > 0.001) {
            cmd.push('-colorspace','yuv','-fx',`sat=${sat}; channel(u,(u-.5)*sat+.5,(u-.5)*sat+.5)`,'-colorspace','srgb');
          }
          if (Math.abs(gamma - 1) > 0.001) cmd.push('-gamma', String(gamma));
          if (Math.abs(gain  - 1) > 0.001) cmd.push('-evaluate','multiply',String(gain));
          if (Math.abs(offset)    > 0.001) cmd.push('-evaluate','add',String(offset * 127.5));
          cmd.push(haldPpm);
          await runCmd('magick', cmd);
          await runFFmpeg(['-y','-i',inPath,'-vf',`movie=${haldPpm},[in]haldclut`,
            '-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p','-c:a','copy',outPath]);
          await fsp.unlink(haldPpm).catch(() => {});
        },
      };
    }

    // ── ImageMagick (frame-by-frame) ──────────────────────────────────────────
    case 'imagemagick': case 'im': {
      const magickArgs = val.split(/\||\s+/).filter(Boolean);
      return {
        kind: 'run',
        fn: async (inPath, outPath, tmpDir) => {
          const id  = randomBytes(4).toString('hex');
          const ext = path.extname(inPath).toLowerCase();
          const isVid = ['.mp4','.mov','.webm','.mkv','.avi'].includes(ext) ||
                        !['.jpg','.jpeg','.png','.gif','.webp','.bmp'].includes(ext);
          if (!isVid) {
            await runCmd('magick', [inPath, ...magickArgs, outPath]);
            return;
          }
          const info      = await ffprobeInfo(inPath);
          const fps       = `${Math.round(info.fps * 1000)}/${1000}`;
          const framesTpl = path.join(tmpDir, `im_${id}_frame_%04d.ppm`);
          const audioWav  = path.join(tmpDir, `im_${id}_audio.wav`);
          // Extract frames
          await runFFmpeg(['-y','-r',fps,'-i',inPath,framesTpl]);
          // Extract audio
          if (info.hasAudio) {
            await runFFmpeg(['-y','-i',inPath,audioWav]).catch(()=>{});
          }
          // Apply magick to each frame in parallel (batched)
          const frames = (await fsp.readdir(tmpDir))
            .filter(f => f.startsWith(`im_${id}_frame_`) && f.endsWith('.ppm'))
            .sort()
            .map(f => path.join(tmpDir, f));
          const BATCH = 8;
          for (let i = 0; i < frames.length; i += BATCH) {
            await Promise.all(frames.slice(i, i + BATCH).map(fp =>
              runCmd('magick', [fp, ...magickArgs, fp]).catch(() => {})));
          }
          // Reassemble
          const hasAudio = info.hasAudio && fs.existsSync(audioWav);
          const assemArgs = ['-y','-r',fps,'-i',framesTpl];
          if (hasAudio) assemArgs.push('-i',audioWav);
          assemArgs.push('-vf','scale=-1:floor(ih/2)*2,setsar=1:1');
          if (hasAudio) assemArgs.push('-map','0:v','-map','1:a');
          assemArgs.push('-pix_fmt','yuv420p','-movflags','+faststart',outPath);
          await runFFmpeg(assemArgs);
        },
      };
    }

    // ── Freakzinga ────────────────────────────────────────────────────────────
    case 'freakzinga': case 'fzgm156': case 'fgm156':
      return {
        kind: 'run',
        fn: async (inPath, outPath, tmpDir) => {
          const id  = randomBytes(4).toString('hex');
          const info = await ffprobeInfo(inPath);
          if (info.duration <= 0) throw new Error('freakzinga: could not probe duration');
          const trimS   = info.duration * 0.5;
          const sr      = 44100;
          const haldPpm = path.join(tmpDir, `fz_hald_${id}.ppm`);
          const vidStep = path.join(tmpDir, `fz_vid_${id}.mkv`);
          const aDn     = path.join(tmpDir, `fz_dn_${id}.wav`);
          const aPos    = path.join(tmpDir, `fz_pos_${id}.wav`);
          const aNeg    = path.join(tmpDir, `fz_neg_${id}.wav`);
          const aMix    = path.join(tmpDir, `fz_mix_${id}.wav`);
          // Step 1: generate hald LUT
          await runCmd('magick', ['hald:6','-define','modulate:colorspace=hsl','-modulate','100,100,200',haldPpm]);
          // Step 2: palindrome video + haldclut
          const fzVf = (
            `movie=${haldPpm},[in]haldclut,hue=b=.045,format=yuv444p[bruh];`+
            `[bruh]split=2[invcol][invcol2];`+
            `[invcol]trim=0:${trimS.toFixed(6)},format=rgb24,shuffleplanes=0:2:1,format=yuv420p[first_s];`+
            `[invcol2]reverse,trim=0:${trimS.toFixed(6)},format=yuv420p[second_s];`+
            `[first_s][second_s]concat=2:1:0,format=yuv420p`
          );
          await runFFmpeg(['-y','-i',inPath,'-filter_complex',fzVf,
            '-c:v','libx264','-preset','ultrafast','-crf','1','-c:a','pcm_s16le',vidStep]);
          // Step 3: downsample audio
          await runFFmpeg(['-y','-i',vidStep,'-af',`asetrate=${Math.floor(sr/2)}`,aDn]);
          // Step 4: dual pitch shift with fileaa
          await runCmd(FILEAA_BIN, [aDn, aPos, '0.5,4.5']);
          await runCmd(FILEAA_BIN, [aDn, aNeg, '-0.5,-4.5']);
          // Step 5: mix audio
          const fzAf = (
            `[0]asetrate=${sr},bass=g=2.5,atrim=end=${trimS.toFixed(6)}[a];`+
            `[1]asetrate=${sr},bass=g=2.5,areverse,atrim=end=${trimS.toFixed(6)}[b];`+
            `[a][b]concat=n=2:v=0:a=1`
          );
          await runFFmpeg(['-y','-i',aPos,'-i',aNeg,'-filter_complex',fzAf,aMix]);
          // Step 6: remux
          await runFFmpeg(['-y','-i',vidStep,'-i',aMix,
            '-map','0:v','-map','1:a',
            '-c:v','libx264','-preset','fast','-crf','23',
            '-pix_fmt','yuv420p','-c:a','pcm_s16le',outPath]);
          await Promise.all([haldPpm,vidStep,aDn,aPos,aNeg,aMix].map(f=>fsp.unlink(f).catch(()=>{})));
        },
      };

    // ── Simple color ──────────────────────────────────────────────────────────
    case 'invert': case 'negate':  return { kind:'vf', filter:'negate' };
    case 'grayscale':              return { kind:'vf', filter:'format=gray,format=yuv420p' };
    case 'sepia':                  return { kind:'vf', filter:'colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131' };
    case 'brightness':             return { kind:'vf', filter:`eq=brightness=${val||0.2}` };
    case 'contrast':               return { kind:'vf', filter:`eq=contrast=${val||1.5}` };
    case 'saturation':             return { kind:'vf', filter:`eq=saturation=${val||2}` };
    case 'huehsv':                 return { kind:'vf', filter:`hue=h=${(parseFloat(val)||0.5)*360}` };
    case 'swapuv':                 return { kind:'vf', filter:'swapuv' };
    case 'invertrgb': case 'invlum': case 'il': return { kind:'vf', filter:'negate=components=7' };

    // ── Transform ─────────────────────────────────────────────────────────────
    case 'hflip':    return { kind:'vf', filter:'hflip' };
    case 'vflip':    return { kind:'vf', filter:'vflip' };
    case 'rotate': {
      const d = parseInt(val) || 90;
      if (d ===  90) return { kind:'vf', filter:'transpose=1' };
      if (d === 180) return { kind:'vf', filter:'hflip,vflip' };
      if (d === 270 || d === -90) return { kind:'vf', filter:'transpose=2' };
      return { kind:'vf', filter:`rotate=${d}*PI/180:fillcolor=black` };
    }
    case 'zoom': {
      const z = parseFloat(val) || 1.5;
      return { kind:'vf', filter:`scale=iw*${z}:ih*${z},crop=iw/${z}:ih/${z}` };
    }
    case 'spherize': case 'bulge': return { kind:'vf', filter:'lenscorrection=k1=-0.3:k2=-0.05' };
    case 'ripple':   return { kind:'vf', filter:`geq=lum_expr='lum(X+10*sin(Y/10+T*5)\\,Y)':cb_expr='cb(X+10*sin(Y/10+T*5)\\,Y)':cr_expr='cr(X+10*sin(Y/10+T*5)\\,Y)'` };
    case 'scroll':   return { kind:'vf', filter:`scroll=h=${parseFloat(val)||0.02}` };
    case 'tile':     return { kind:'vf', filter:`tile=${val||'2x2'}` };
    case 'timecode': return { kind:'vf', filter:`drawtext=text='%{pts\\:hms}':fontsize=24:fontcolor=white:x=10:y=10:box=1:boxcolor=black@0.6` };
    case 'watermark': case 'caption':
      return { kind:'vf', filter:`drawtext=text='${(val||'text').replace(/'/g,"\\'")}':fontsize=36:fontcolor=white:x=(w-tw)/2:y=h-th-20:box=1:boxcolor=black@0.5` };

    // ── Wave ──────────────────────────────────────────────────────────────────
    case 'wave': {
      const wt = (val || 'large').toLowerCase().replace(/\s+/g,'');
      const vf = WAVE_PRESETS[wt] || WAVE_PRESETS.large;
      return { kind:'vf', filter:vf };
    }
    case 'wave2':
      return { kind:'vf', filter:`format=yuv444p,geq='p(X+20*sin(Y/12+T*5)\\,Y+10*sin(X/18+T*3))':cb_expr='cb(X+20*sin(Y/12+T*5)\\,Y+10*sin(X/18+T*3))':cr_expr='cr(X+20*sin(Y/12+T*5)\\,Y+10*sin(X/18+T*3))',setsar=1:1,format=yuv420p` };

    // ── Distort ───────────────────────────────────────────────────────────────
    case 'jitter': {
      const s = parseFloat(val) || 15;
      const margin = Math.max(4, Math.ceil(s * 2 / 2) * 2);
      const half   = margin >> 1;
      return { kind:'vf', filter:`pad=iw+${margin}:ih+${margin}:${half}:${half},crop=iw-${margin}:ih-${margin}:max(0\\,${half}+${s}*sin(n*69)):max(0\\,${half}+${s}*sin(n*671))` };
    }
    case 'randomjitter': case 'rj': {
      const s = parseFloat(val) || 10;
      const indexX = 68, indexY = 671, div = 2.6666666666666665;
      const ex = `(${s}/(25/3)/${div})*(2*mod(1000*sin(N*${indexX}),1)-1)`;
      const ey = `(${s}/${div})*(2*mod(1000*sin(N+1000)*${indexY},1)-1)`;
      return { kind:'vf', filter:`rotate=0:iw*1.1:ih*1.1,format=yuv444p,geq='p(X+${ex}\\,Y+${ey})',crop=iw/1.1:ih/1.1,format=yuv420p` };
    }

    // ── Audio ─────────────────────────────────────────────────────────────────
    case 'volume':       return { kind:'af', filter:`volume=${val||2}` };
    case 'vibrato': {
      const [f,d] = (val||'5:0.5').split(':');
      return { kind:'af', filter:`vibrato=f=${f||5}:d=${d||0.5}` };
    }
    case 'areverse':     return { kind:'af', filter:'areverse' };
    case 'acontrast':    return { kind:'af', filter:`acontrast=${val||33}` };
    case 'alimiter':     return { kind:'af', filter:'alimiter' };

    // ── Speed ─────────────────────────────────────────────────────────────────
    case 'speed': {
      const s = parseFloat(val) || 1;
      const vf = `setpts=${(1/s).toFixed(6)}*PTS`;
      let atempo;
      if (s >= 0.5 && s <= 2) atempo = `atempo=${s}`;
      else if (s > 2)          atempo = `atempo=2.0,atempo=${Math.min(2, s/2).toFixed(4)}`;
      else if (s < 0.5 && s > 0) atempo = `atempo=0.5,atempo=${Math.max(0.5,s*2).toFixed(4)}`;
      return { kind:'vf+af', vf, af:atempo||`atempo=1` };
    }

    // ── Reverse ───────────────────────────────────────────────────────────────
    case 'vreverse': return { kind:'vf+af', vf:'reverse', af:'areverse' };

    // ── Frei0r (pass through as vf) ───────────────────────────────────────────
    case 'frei0r':
      return { kind:'vf', filter: val ? `frei0r=${val}` : 'frei0r=zerocrossing' };

    // ── Raw ffmpeg injection ──────────────────────────────────────────────────
    case 'ffmpeg':
      return val ? { kind:'vf', filter:val } : { kind:'skip', reason:'ffmpeg: empty filter' };

    // ── Default: try as raw vf ────────────────────────────────────────────────
    default:
      if (val) return { kind:'vf', filter:`${name}=${val}` };
      return { kind:'vf', filter:name };
  }
}

// ─── Pipeline engine ──────────────────────────────────────────────────────────

async function applyPipeline(inputPath, finalOutPath, pipeStr, tmpDir, isImage) {
  const parts = pipeStr.split(',').map(s => s.trim()).filter(Boolean);
  if (!parts.length) throw new Error('No effects specified');

  let current   = inputPath;
  let pendingVf = [];
  let pendingAf = [];
  let stepN     = 0;
  const unsupported = [];
  const midExt  = isImage ? '.png' : '.mkv';

  const flushBatch = async (isFinal) => {
    if (!pendingVf.length && !pendingAf.length) return;
    stepN++;
    const out = isFinal ? finalOutPath : tmpPath(`batch_${stepN}`, midExt);
    const vf  = pendingVf.length ? pendingVf.join(',') : null;
    const af  = pendingAf.length ? pendingAf.join(',') : null;
    if (isFinal) await encodeFinal(current, out, vf, af, isImage);
    else         await encodeStep(current, out, vf, af, isImage);
    current   = out;
    pendingVf = []; pendingAf = [];
  };

  for (let i = 0; i < parts.length; i++) {
    const part   = parts[i];
    const eqIdx  = part.indexOf('=');
    const name   = (eqIdx === -1 ? part : part.slice(0, eqIdx)).toLowerCase().trim();
    const val    = eqIdx === -1 ? '' : part.slice(eqIdx + 1).trim();
    const isLast = i === parts.length - 1;

    const resolved = resolveEffect(name, val);

    if (resolved.kind === 'skip') {
      unsupported.push(name); continue;
    }
    if (resolved.kind === 'vf') {
      // If this is the last part and we have pending, merge and flush final
      pendingVf.push(resolved.filter);
      if (isLast) await flushBatch(true);
      continue;
    }
    if (resolved.kind === 'af') {
      pendingAf.push(resolved.filter);
      if (isLast) await flushBatch(true);
      continue;
    }
    if (resolved.kind === 'vf+af') {
      pendingVf.push(resolved.vf);
      pendingAf.push(resolved.af);
      if (isLast) await flushBatch(true);
      continue;
    }
    // complex: fc or run — flush pending batch first
    await flushBatch(false);
    stepN++;
    const out = isLast ? finalOutPath : tmpPath(`step_${stepN}`, midExt);

    if (resolved.kind === 'fc') {
      const fcArgs = ['-y', '-i', current, '-filter_complex', resolved.fc];
      for (const m of (resolved.maps || [])) fcArgs.push('-map', m);
      if (!isImage) {
        fcArgs.push('-c:v','libx264','-preset', isLast ? 'fast' : 'ultrafast',
          '-crf', isLast ? '23' : '10',
          '-c:a','aac','-pix_fmt','yuv420p');
      } else {
        fcArgs.push('-frames:v','1','-q:v','2');
      }
      fcArgs.push(out);
      await runFFmpeg(fcArgs);
    } else if (resolved.kind === 'run') {
      await resolved.fn(current, out, tmpDir);
    }
    current = out;
  }

  // Edge case: nothing batched yet (all steps were complex and handled final output)
  if (current !== finalOutPath && current !== inputPath && parts.length > 0) {
    // last step already wrote to finalOutPath via isLast logic
  }
  // If nothing happened at all (all skipped), copy input
  if (current === inputPath) {
    await fsp.copyFile(inputPath, finalOutPath);
  }

  return unsupported;
}

// ─── Multipart parser ─────────────────────────────────────────────────────────

async function parseMultipart(req) {
  const ct  = req.headers['content-type'] || '';
  const bm  = ct.match(/boundary=([^\s;,]+)/);
  if (!bm) throw new Error('Missing boundary');
  const boundary = bm[1];
  const chunks = []; let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > MAX_UPLOAD) throw new Error('Upload too large (max 150 MB)');
    chunks.push(chunk);
  }
  const body = Buffer.concat(chunks);
  const SEP  = Buffer.from('\r\n--' + boundary);
  const CRFL = Buffer.from('\r\n\r\n');
  const fields = {}, files = {};
  let pos = body.indexOf('--' + boundary);
  if (pos === -1) return { fields, files };
  pos += ('--' + boundary).length;
  if (body[pos] === 0x0d) pos += 2;
  while (pos < body.length) {
    const hdrEnd = body.indexOf(CRFL, pos);
    if (hdrEnd === -1) break;
    const hdrs      = body.slice(pos, hdrEnd).toString('utf8');
    const dataStart = hdrEnd + 4;
    const nextSep   = body.indexOf(SEP, dataStart);
    const content   = body.slice(dataStart, nextSep === -1 ? body.length : nextSep);
    const nameM     = hdrs.match(/[Nn]ame="([^"]+)"/);
    const fileM     = hdrs.match(/[Ff]ilename="([^"]+)"/);
    const ctM       = hdrs.match(/[Cc]ontent-[Tt]ype:\s*([^\r\n]+)/);
    if (nameM) {
      if (fileM) files[nameM[1]]  = { data:content, filename:fileM[1], type:ctM?.[1]?.trim()||'application/octet-stream' };
      else       fields[nameM[1]] = content.toString('utf8');
    }
    if (nextSep === -1) break;
    pos = nextSep + SEP.length;
    if (body[pos] === 0x2d && body[pos+1] === 0x2d) break;
    if (body[pos] === 0x0d) pos += 2;
  }
  return { fields, files };
}

// ─── Process endpoint ─────────────────────────────────────────────────────────

async function handleProcess(req, res) {
  const id     = randomBytes(8).toString('hex');
  const tmpDir = path.join(TMP, `ihtx_run_${id}`);
  await fsp.mkdir(tmpDir, { recursive: true });
  let inPath, stagePath, finalPath;
  try {
    const { fields, files } = await parseMultipart(req);
    const fe = files.file;
    if (!fe) throw new Error('No file uploaded');
    const pipeStr = (fields.pipe || '').trim();
    if (!pipeStr) throw new Error('No pipe effects provided');
    const reps     = Math.max(1, parseInt(fields.reps || '1', 10) || 1);
    const duration = (fields.duration || '').trim();
    const noTrim   = fields.noTrim === '1' || fields.noTrim === 'true';
    const format   = (fields.format || 'mp4').toLowerCase().replace(/^\./, '');

    const ext     = path.extname(fe.filename).toLowerCase() || '.mp4';
    const isImage = /^image\//.test(fe.type) || ['.jpg','.jpeg','.png','.gif','.webp','.bmp'].includes(ext);
    inPath    = tmpPath(`in_${id}`, ext);
    stagePath = tmpPath(`stage_${id}`, isImage ? '.png' : '.mkv');
    finalPath = tmpPath(`final_${id}`, format === 'jpg' ? '.jpeg' : `.${format}`);
    await fsp.writeFile(inPath, fe.data);

    const info = await ffprobeInfo(inPath);
    const unsupported = await applyPipeline(inPath, stagePath, pipeStr, tmpDir, isImage);
    const { isImage: finalIsImage, isAudioOnly } = await applyPostEffects(stagePath, finalPath,
      { reps, duration, noTrim, format }, info, tmpDir);

    const outData = await fsp.readFile(finalPath);
    const outMime = FORMAT_MIME[format] || (finalIsImage ? 'image/jpeg' : isAudioOnly ? 'audio/mpeg' : 'video/mp4');
    const finalExt = format || (finalIsImage ? 'jpg' : isAudioOnly ? 'mp3' : 'mp4');

    res.writeHead(200, { 'Content-Type':'application/json', 'Access-Control-Allow-Origin':'*' });
    res.end(JSON.stringify({ ok:true, data:outData.toString('base64'), mime:outMime,
      filename:`ihtx_${id}.${finalExt}`, unsupported }));
  } catch (err) {
    res.writeHead(200, { 'Content-Type':'application/json', 'Access-Control-Allow-Origin':'*' });
    res.end(JSON.stringify({ ok:false, error:err.message }));
  } finally {
    if (inPath)    fsp.unlink(inPath).catch(() => {});
    if (stagePath) fsp.unlink(stagePath).catch(() => {});
    if (finalPath) fsp.unlink(finalPath).catch(() => {});
    fsp.rm(tmpDir, { recursive:true, force:true }).catch(() => {});
  }
}

// ─── HTTP server ──────────────────────────────────────────────────────────────

http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'POST' && req.url === '/process') return handleProcess(req, res);
  let filePath = path.join(__dirname, req.url === '/' ? 'index.html' : req.url);
  const ext    = path.extname(filePath).toLowerCase();
  if (!fs.existsSync(filePath)) { res.writeHead(404); res.end('Not found'); return; }
  res.writeHead(200, { 'Content-Type': MIME[ext] ?? 'application/octet-stream' });
  fs.createReadStream(filePath).pipe(res);
}).listen(PORT, () => console.log(`Static server on port ${PORT}`));
