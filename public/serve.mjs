import http from 'http';
import fs from 'fs';
import fsp from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import { tmpdir } from 'os';
import { randomBytes } from 'crypto';
import { spawn } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.env.PORT ? parseInt(process.env.PORT) : 8080;
const TMP = tmpdir();
const MAX_UPLOAD = 150 * 1024 * 1024; // 150 MB

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css':  'text/css',
  '.js':   'application/javascript',
  '.json': 'application/json',
  '.png':  'image/png',
  '.svg':  'image/svg+xml',
};

// ─── Multipart parser ────────────────────────────────────────────────────────
async function parseMultipart(req) {
  const ct = req.headers['content-type'] || '';
  const bm = ct.match(/boundary=([^\s;,]+)/);
  if (!bm) throw new Error('Missing boundary');
  const boundary = bm[1];

  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > MAX_UPLOAD) throw new Error('Upload too large');
    chunks.push(chunk);
  }
  const body = Buffer.concat(chunks);

  const SEP  = Buffer.from('\r\n--' + boundary);
  const CRFL = Buffer.from('\r\n\r\n');
  const fields = {}, files = {};

  // Find first part
  let pos = body.indexOf('--' + boundary);
  if (pos === -1) return { fields, files };
  pos += ('--' + boundary).length;
  if (body[pos] === 0x0d) pos += 2; // skip \r\n

  while (pos < body.length) {
    // Headers end
    const hdrEnd = body.indexOf(CRFL, pos);
    if (hdrEnd === -1) break;
    const hdrs = body.slice(pos, hdrEnd).toString('utf8');
    const dataStart = hdrEnd + 4;

    // Next boundary
    const nextSep = body.indexOf(SEP, dataStart);
    const dataEnd = nextSep === -1 ? body.length : nextSep;
    const content = body.slice(dataStart, dataEnd);

    const nameM     = hdrs.match(/[Nn]ame="([^"]+)"/);
    const filenameM = hdrs.match(/[Ff]ilename="([^"]+)"/);
    const ctM       = hdrs.match(/[Cc]ontent-[Tt]ype:\s*([^\r\n]+)/);

    if (nameM) {
      if (filenameM) {
        files[nameM[1]] = {
          data:     content,
          filename: filenameM[1],
          type:     ctM ? ctM[1].trim() : 'application/octet-stream',
        };
      } else {
        fields[nameM[1]] = content.toString('utf8');
      }
    }

    if (nextSep === -1) break;
    pos = nextSep + SEP.length;
    // Check for final --
    if (body[pos] === 0x2d && body[pos + 1] === 0x2d) break;
    if (body[pos] === 0x0d) pos += 2;
  }

  return { fields, files };
}

// ─── Pipe → FFmpeg translation ───────────────────────────────────────────────
const NOISE = 'noise=alls=40:allf=t+u';
const SHAKE = 'crop=iw-20:ih-20:10+5*sin(t*30):10+5*cos(t*17),scale=iw+20:ih+20';

function translatePipe(pipeStr) {
  const parts   = pipeStr.split(',').map(s => s.trim()).filter(Boolean);
  const vf = [], af = [], unsupported = [];

  for (const part of parts) {
    const eq   = part.indexOf('=');
    const name = (eq === -1 ? part : part.slice(0, eq)).toLowerCase().trim();
    const val  = eq === -1 ? '' : part.slice(eq + 1).trim();

    switch (name) {
      // ── Presets ──────────────────────────────────────────────────────────
      case 'chaos':
        vf.push(`${SHAKE},${NOISE},hue=h=t*180:s=2,eq=contrast=1.5:brightness=0.05:saturation=3`); break;
      case 'glitch':
        vf.push(`rgbashift=rh=8:rv=-8:gh=-4:gv=4:bh=6:bv=-6,${NOISE},eq=contrast=1.8:saturation=0`); break;
      case 'shake':
        vf.push(`${SHAKE},${NOISE},eq=contrast=1.3:saturation=1.5`); break;
      case 'static':
        vf.push(`${NOISE},curves=vintage,eq=contrast=1.2`); break;
      case 'melt':
        vf.push(`perspective=x0=0:y0=0:x1=iw:y1=20*sin(t*3):x2=0:y2=ih:x3=iw:y3=ih-20*sin(t*3),${NOISE}`); break;
      case 'corrupt':
        vf.push(`drawgrid=x=0:y=0:w=iw:h=5:t=1:color=white@0.1,${NOISE},eq=gamma=1.5:saturation=0.3:contrast=2`); break;

      // ── Color ─────────────────────────────────────────────────────────────
      case 'invert': case 'negate':
        vf.push('negate'); break;
      case 'grayscale':
        vf.push('format=gray,format=yuv420p'); break;
      case 'sepia':
        vf.push('colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131'); break;
      case 'brightness':
        vf.push(`eq=brightness=${val || 0.2}`); break;
      case 'contrast':
        vf.push(`eq=contrast=${val || 1.5}`); break;
      case 'saturation':
        vf.push(`eq=saturation=${val || 2}`); break;
      case 'huehsv':
        vf.push(`hue=h=${(parseFloat(val) || 0.5) * 360}`); break;
      case 'swapuv':
        vf.push('swapuv'); break;
      case 'invertrgb': case 'invlum': case 'il':
        vf.push('negate=components=7'); break; // negate RGB only (not alpha)

      // ── Transform ─────────────────────────────────────────────────────────
      case 'hflip':
        vf.push('hflip'); break;
      case 'vflip':
        vf.push('vflip'); break;
      case 'rotate': {
        const d = parseInt(val) || 90;
        if (d === 90)  vf.push('transpose=1');
        else if (d === 180) vf.push('hflip,vflip');
        else if (d === 270 || d === -90) vf.push('transpose=2');
        else vf.push(`rotate=${d}*PI/180:fillcolor=black`);
        break;
      }
      case 'zoom': {
        const z = parseFloat(val) || 1.5;
        vf.push(`scale=iw*${z}:ih*${z},crop=iw/${z}:ih/${z}`); break;
      }
      case 'mirror':
        vf.push('crop=iw/2:ih:0:0,split[l][tmp];[tmp]hflip[r];[l][r]hstack'); break;
      case 'spherize': case 'bulge':
        vf.push('lenscorrection=k1=-0.3:k2=-0.05'); break;
      case 'tile':
        vf.push(`tile=${val || '2x2'}`); break;
      case 'scroll': {
        const s = parseFloat(val) || 0.02;
        vf.push(`scroll=h=${s}`); break;
      }

      // ── Distort ───────────────────────────────────────────────────────────
      case 'wave': {
        const wt = val.toLowerCase();
        const waves = {
          large:          `geq=lum_expr='lum(X+40*sin(Y/20+T*3)\\,Y)':cb_expr='cb(X+40*sin(Y/20+T*3)\\,Y)':cr_expr='cr(X+40*sin(Y/20+T*3)\\,Y)'`,
          medium:         `geq=lum_expr='lum(X+20*sin(Y/15+T*3)\\,Y)':cb_expr='cb(X+20*sin(Y/15+T*3)\\,Y)':cr_expr='cr(X+20*sin(Y/15+T*3)\\,Y)'`,
          small:          `geq=lum_expr='lum(X+10*sin(Y/10+T*4)\\,Y)':cb_expr='cb(X+10*sin(Y/10+T*4)\\,Y)':cr_expr='cr(X+10*sin(Y/10+T*4)\\,Y)'`,
          horizontalonly: `geq=lum_expr='lum(X+30*sin(Y/20+T*3)\\,Y)':cb_expr='cb(X+30*sin(Y/20+T*3)\\,Y)':cr_expr='cr(X+30*sin(Y/20+T*3)\\,Y)'`,
          verticalonly:   `geq=lum_expr='lum(X\\,Y+30*sin(X/20+T*3))':cb_expr='cb(X\\,Y+30*sin(X/20+T*3))':cr_expr='cr(X\\,Y+30*sin(X/20+T*3))'`,
        };
        vf.push(waves[wt] || waves.large); break;
      }
      case 'wave2':
        vf.push(`geq=lum_expr='lum(X+20*sin(Y/12+T*5)\\,Y+10*sin(X/18+T*3))':cb_expr='cb(X+20*sin(Y/12+T*5)\\,Y+10*sin(X/18+T*3))':cr_expr='cr(X+20*sin(Y/12+T*5)\\,Y+10*sin(X/18+T*3))'`); break;
      case 'ripple':
        vf.push(`geq=lum_expr='lum(X+10*sin(Y/10+T*5)\\,Y)':cb_expr='cb(X+10*sin(Y/10+T*5)\\,Y)':cr_expr='cr(X+10*sin(Y/10+T*5)\\,Y)'`); break;
      case 'jitter': case 'randomjitter': case 'rj':
        vf.push(`setpts=N/FRAME_RATE/TB+random(1)*0.08`); break;
      case 'timecode':
        vf.push(`drawtext=text='%{pts\\:hms}':fontsize=24:fontcolor=white:x=10:y=10:box=1:boxcolor=black@0.6`); break;

      // ── Audio ─────────────────────────────────────────────────────────────
      case 'volume':
        af.push(`volume=${val || 2}`); break;
      case 'vibrato': {
        const [f, d] = (val || '5:0.5').split(':');
        af.push(`vibrato=f=${f || 5}:d=${d || 0.5}`); break;
      }
      case 'areverse':
        af.push('areverse'); break;
      case 'vreverse':
        vf.push('reverse'); af.push('areverse'); break;
      case 'acontrast':
        af.push(`acontrast=${val || 33}`); break;
      case 'alimiter':
        af.push('alimiter'); break;

      // ── Speed ─────────────────────────────────────────────────────────────
      case 'speed': {
        const s = parseFloat(val) || 1;
        vf.push(`setpts=${(1 / s).toFixed(6)}*PTS`);
        if (s >= 0.5 && s <= 2) {
          af.push(`atempo=${s}`);
        } else if (s > 2) {
          af.push(`atempo=2.0,atempo=${Math.min(2, s / 2).toFixed(4)}`);
        } else if (s < 0.5 && s > 0) {
          af.push(`atempo=0.5,atempo=${Math.max(0.5, s * 2).toFixed(4)}`);
        }
        break;
      }

      // ── Complex / unsupported in web ──────────────────────────────────────
      case 'rainbow': case 'srw': case 'sierpinskiransomware':
      case 'tvsim': case 'tv':
      case 'freakzinga': case 'fzgm156':
      case 'earthquake': case 'nbfx':
      case 'multipitch': case 'mp':
      case 'multipitch2': case 'mp2': case 'multipitch3': case 'mp3':
      case 'imagemagick': case 'im':
      case 'ccshue': case 'huehsv_im':
      case 'frei0r': case 'gradientmap': case 'gmap': case 'gm':
      case 'vocoder': case 'swirl': case 'realgm4': case 'gm4':
      case 'ssmp': case 'folkvalley': case 'fv':
      case 'nepeta': case 'radar': case 'mirror':
      case 'ffmpeg':
        unsupported.push(name); break;

      default:
        // Pass through as raw vf filter
        vf.push(val ? `${name}=${val}` : name);
    }
  }

  return { vf, af, unsupported };
}

// ─── Run FFmpeg ───────────────────────────────────────────────────────────────
function runFFmpeg(args) {
  return new Promise((resolve, reject) => {
    const stderr = [];
    const proc = spawn('ffmpeg', args);
    proc.stderr.on('data', d => stderr.push(d.toString()));
    proc.on('close', code => {
      if (code === 0) resolve();
      else reject(new Error(stderr.join('').slice(-2000)));
    });
    proc.on('error', reject);
  });
}

// ─── Process endpoint ─────────────────────────────────────────────────────────
async function handleProcess(req, res) {
  let inPath, outPath;
  try {
    const { fields, files } = await parseMultipart(req);
    const fileEntry = files.file;
    if (!fileEntry) throw new Error('No file uploaded');

    const pipeStr = (fields.pipe || '').trim();
    if (!pipeStr) throw new Error('No pipe effects provided');

    const id   = randomBytes(8).toString('hex');
    const ext  = path.extname(fileEntry.filename).toLowerCase() || '.mp4';
    const mime = fileEntry.type;
    const isImage = /^image\//.test(mime) || ['.jpg','.jpeg','.png','.gif','.webp','.bmp'].includes(ext);

    inPath  = path.join(TMP, `ihtx-in-${id}${ext}`);
    outPath = path.join(TMP, `ihtx-out-${id}${isImage ? '.jpg' : '.mp4'}`);

    await fsp.writeFile(inPath, fileEntry.data);

    const { vf, af, unsupported } = translatePipe(pipeStr);

    // Build ffmpeg args
    const args = ['-y', '-i', inPath];

    if (isImage) {
      if (vf.length) args.push('-vf', vf.join(','));
      args.push('-frames:v', '1', '-q:v', '2', outPath);
    } else {
      const hasAudio = af.length > 0 || vf.some(f => f.includes('areverse'));
      if (vf.length) args.push('-vf', vf.join(','));
      if (af.length) args.push('-af', af.join(','));
      args.push(
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        '-max_muxing_queue_size', '1024',
        outPath
      );
    }

    await runFFmpeg(args);

    const outData = await fsp.readFile(outPath);
    const outMime = isImage ? 'image/jpeg' : 'video/mp4';
    const outName = `ihtx-${id}${isImage ? '.jpg' : '.mp4'}`;

    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    });
    res.end(JSON.stringify({
      ok:          true,
      data:        outData.toString('base64'),
      mime:        outMime,
      filename:    outName,
      unsupported: unsupported,
    }));
  } catch (err) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: false, error: err.message }));
  } finally {
    // Cleanup temp files
    if (inPath)  fsp.unlink(inPath).catch(() => {});
    if (outPath) fsp.unlink(outPath).catch(() => {});
  }
}

// ─── HTTP server ──────────────────────────────────────────────────────────────
http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');

  if (req.method === 'POST' && req.url === '/process') {
    return handleProcess(req, res);
  }

  // Static files
  let filePath = path.join(__dirname, req.url === '/' ? 'index.html' : req.url);
  const ext = path.extname(filePath).toLowerCase();
  if (!fs.existsSync(filePath)) {
    res.writeHead(404); res.end('Not found'); return;
  }
  res.writeHead(200, { 'Content-Type': MIME[ext] ?? 'application/octet-stream' });
  fs.createReadStream(filePath).pipe(res);

}).listen(PORT, () => console.log(`Static server on port ${PORT}`));
