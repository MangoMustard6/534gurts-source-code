---
name: Building missing frei0r plugins on Nix
description: How to compile and install frei0r plugins that are missing from the Nix package so FFmpeg can discover them at runtime.
---

The Nix `frei0r` package ships many plugins, but it may not include newer or less common ones (e.g., `mirr0r`). FFmpeg searches for frei0r plugins in a few hardcoded paths, including `~/.frei0r-1/lib/<plugin>.so`.

**Why:** Replit’s Nix environment uses an immutable store, so we cannot drop `.so` files into `/nix/store/.../lib/frei0r-1/`. User home is writable and persistent, and FFmpeg checks it first.

**How to apply:**
1. Download the plugin source from the upstream frei0r repo (e.g., `dyne/frei0r` on GitHub).
2. Build the plugin with the matching `frei0r.h`/`frei0r.hpp` headers and link against the installed cairo library.
3. Install the resulting `.so` into `~/.frei0r-1/lib/`.
4. Verify with `ffmpeg -f lavfi -i nullsrc -vf frei0r=<plugin>:<params> -frames:v 1 -f null -`.

**Example for mirr0r:**
```bash
cd /tmp
mkdir mirr0r-build && cd mirr0r-build
curl -sL -o frei0r.h https://raw.githubusercontent.com/dyne/frei0r/master/include/frei0r.h
curl -sL -o frei0r.hpp https://raw.githubusercontent.com/dyne/frei0r/master/include/frei0r.hpp
curl -sL -o mirr0r.cpp https://raw.githubusercontent.com/dyne/frei0r/master/src/filter/mirr0r/mirr0r.cpp
g++ -shared -fPIC -std=c++11 -o mirr0r.so mirr0r.cpp \
  -I/nix/store/<cairo-dev>/include/cairo \
  -I. \
  -L/nix/store/<cairo-out>/lib \
  -lcairo -Wl,-rpath,/nix/store/<cairo-out>/lib
mkdir -p ~/.frei0r-1/lib
cp mirr0r.so ~/.frei0r-1/lib/
```

Use `nix-shell -p cairo` to locate the current cairo dev and lib paths if needed.
