#!/usr/bin/env python3
"""CLI wrapper: upload a local file to catbox.moe via catboxpy.
Usage: python3 bot/catbox_upload.py <file_path> [userhash]
Prints the catbox URL to stdout on success, or exits with code 1 on failure.
"""
import sys
import os

def main():
    if len(sys.argv) < 2:
        print("Usage: catbox_upload.py <file_path> [userhash]", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    userhash = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    try:
        from catboxpy.catbox import CatboxClient
        client = CatboxClient(userhash=userhash)
        url = client.file_upload(file_path)
        print(url, end="")
    except Exception as e:
        print(f"Upload failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
