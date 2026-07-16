"""
Global tag storage.

All tags live in a single "global" namespace — accessible from every guild.
Per-guild tags (legacy format keyed by guild ID strings) are migrated into the
global namespace on first load.  The `guild_id` parameter on every method is
kept for API compatibility but is ignored.

File: bot/tag_store.json
Structure (after migration):
  {
    "global": {
      "tags":    { "<name>": { ... tag record ... }, ... },
      "aliases": { "<alias>": "<name>", ... }
    }
  }
"""

import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

TAG_STORE_FILE = Path("bot/tag_store.json")
_lock = asyncio.Lock()

# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_raw() -> dict:
    if TAG_STORE_FILE.exists():
        try:
            return json.loads(TAG_STORE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_raw(data: dict):
    TAG_STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    TAG_STORE_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _global_data(data: dict) -> dict:
    """Return (creating if needed) the single global tag namespace."""
    if "global" not in data:
        data["global"] = {"tags": {}, "aliases": {}}
    gd = data["global"]
    gd.setdefault("tags", {})
    gd.setdefault("aliases", {})
    return gd


def _migrate_guild_tags(data: dict) -> bool:
    """
    Migrate per-guild buckets (keys that are numeric guild ID strings) into the
    global namespace.  Tags are merged in no particular order; if a name
    collision occurs the existing global tag wins (first writer wins).
    Returns True if the data dict was modified.
    """
    gd = _global_data(data)
    changed = False

    for key in list(data.keys()):
        if key == "global":
            continue
        # Only migrate keys that look like Discord snowflakes (all digits)
        if not key.isdigit():
            continue

        value = data[key]
        if not isinstance(value, dict):
            continue

        guild_tags    = value.get("tags",    {})
        guild_aliases = value.get("aliases", {})

        for name, tag in guild_tags.items():
            if name not in gd["tags"]:
                tag_copy = dict(tag)
                tag_copy.setdefault("guild_origin", key)  # provenance
                gd["tags"][name] = tag_copy
                changed = True

        for alias, target in guild_aliases.items():
            if alias not in gd["aliases"] and alias not in gd["tags"]:
                gd["aliases"][alias] = target
                changed = True

        # Remove the old per-guild bucket
        del data[key]
        changed = True

    return changed


# ── Public TagStorage class ───────────────────────────────────────────────────

class TagStorage:
    def __init__(self):
        self._data: dict = {}
        self._loaded = False

    async def _ensure_loaded(self):
        if not self._loaded:
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(None, _load_raw)
            # Migrate any legacy per-guild data on first load; flush if changed.
            migrated = _migrate_guild_tags(raw)
            self._data = raw
            self._loaded = True
            if migrated:
                await loop.run_in_executor(None, _save_raw, raw)

    async def _flush(self):
        data = self._data
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _save_raw, data)

    # ── Read ─────────────────────────────────────────────────────────────────

    async def get(self, guild_id: int, name: str) -> Optional[dict]:
        """Return a tag by name or alias (guild_id ignored — global lookup)."""
        async with _lock:
            await self._ensure_loaded()
            gd = _global_data(self._data)
            name = name.lower()
            if name in gd["aliases"]:
                name = gd["aliases"][name]
            return gd["tags"].get(name)

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(
        self, guild_id: int, name: str, content: str, owner_id: int
    ) -> bool:
        """Create a new tag globally.  Returns False if the name already exists."""
        async with _lock:
            await self._ensure_loaded()
            gd = _global_data(self._data)
            name = name.lower()
            if name in gd["tags"] or name in gd["aliases"]:
                return False
            gd["tags"][name] = {
                "name": name,
                "content": content,
                "owner_id": owner_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "uses": 0,
                "aliases": [],
                "allowed_roles": [],
                "denied_users": [],
            }
            await self._flush()
            return True

    async def edit(
        self,
        guild_id: int,
        name: str,
        content: str,
        editor_id: int,
        is_owner: bool,
    ) -> str:
        async with _lock:
            await self._ensure_loaded()
            gd = _global_data(self._data)
            name = name.lower()
            if name in gd["aliases"]:
                name = gd["aliases"][name]
            tag = gd["tags"].get(name)
            if tag is None:
                return "not_found"
            if not is_owner and tag["owner_id"] != editor_id:
                return "not_owner"
            tag["content"] = content
            tag["edited_at"] = datetime.now(timezone.utc).isoformat()
            await self._flush()
            return "ok"

    async def delete(
        self,
        guild_id: int,
        name: str,
        deleter_id: int,
        is_owner: bool,
    ) -> str:
        async with _lock:
            await self._ensure_loaded()
            gd = _global_data(self._data)
            name = name.lower()
            real_name = gd["aliases"].get(name, name)
            tag = gd["tags"].get(real_name)
            if tag is None:
                return "not_found"
            if not is_owner and tag["owner_id"] != deleter_id:
                return "not_owner"
            for alias in tag.get("aliases", []):
                gd["aliases"].pop(alias, None)
            del gd["tags"][real_name]
            await self._flush()
            return "ok"

    async def add_alias(
        self,
        guild_id: int,
        name: str,
        alias: str,
        requester_id: int,
        is_owner: bool,
    ) -> str:
        async with _lock:
            await self._ensure_loaded()
            gd = _global_data(self._data)
            name = name.lower()
            alias = alias.lower()
            if name in gd["aliases"]:
                name = gd["aliases"][name]
            tag = gd["tags"].get(name)
            if tag is None:
                return "not_found"
            if not is_owner and tag["owner_id"] != requester_id:
                return "not_owner"
            if alias in gd["tags"] or alias in gd["aliases"]:
                return "conflict"
            gd["aliases"][alias] = name
            tag.setdefault("aliases", []).append(alias)
            await self._flush()
            return "ok"

    async def remove_alias(
        self,
        guild_id: int,
        alias: str,
        requester_id: int,
        is_owner: bool,
    ) -> str:
        async with _lock:
            await self._ensure_loaded()
            gd = _global_data(self._data)
            alias = alias.lower()
            real_name = gd["aliases"].get(alias)
            if real_name is None:
                return "not_found"
            tag = gd["tags"].get(real_name)
            if tag is None:
                return "not_found"
            if not is_owner and tag["owner_id"] != requester_id:
                return "not_owner"
            del gd["aliases"][alias]
            tag.setdefault("aliases", [])
            if alias in tag["aliases"]:
                tag["aliases"].remove(alias)
            await self._flush()
            return "ok"

    async def increment_uses(self, guild_id: int, name: str):
        async with _lock:
            await self._ensure_loaded()
            gd = _global_data(self._data)
            if name in gd["aliases"]:
                name = gd["aliases"][name]
            tag = gd["tags"].get(name)
            if tag:
                tag["uses"] = tag.get("uses", 0) + 1
                await self._flush()

    async def list_tags(self, guild_id: int) -> list:
        """Return all global tags sorted by name."""
        async with _lock:
            await self._ensure_loaded()
            gd = _global_data(self._data)
            return sorted(gd["tags"].values(), key=lambda t: t["name"])

    async def search_tags(self, guild_id: int, query: str) -> list:
        """Search all global tags by name or content."""
        async with _lock:
            await self._ensure_loaded()
            gd = _global_data(self._data)
            q = query.lower()
            return [
                t
                for t in gd["tags"].values()
                if q in t["name"] or q in t.get("content", "")
            ]

    async def transfer(
        self,
        guild_id: int,
        name: str,
        new_owner_id: int,
        requester_id: int,
        is_owner: bool,
    ) -> str:
        async with _lock:
            await self._ensure_loaded()
            gd = _global_data(self._data)
            name = name.lower()
            if name in gd["aliases"]:
                name = gd["aliases"][name]
            tag = gd["tags"].get(name)
            if tag is None:
                return "not_found"
            if not is_owner and tag["owner_id"] != requester_id:
                return "not_owner"
            tag["owner_id"] = new_owner_id
            await self._flush()
            return "ok"

    async def rename(
        self,
        guild_id: int,
        old_name: str,
        new_name: str,
        requester_id: int,
        is_owner: bool,
    ) -> str:
        async with _lock:
            await self._ensure_loaded()
            gd = _global_data(self._data)
            old_key = old_name.lower()
            new_key = new_name.lower()
            if old_key in gd["aliases"]:
                old_key = gd["aliases"][old_key]
            tag = gd["tags"].get(old_key)
            if tag is None:
                return "not_found"
            if not is_owner and tag["owner_id"] != requester_id:
                return "not_owner"
            if new_key in gd["tags"] or new_key in gd["aliases"]:
                return "conflict"
            tag["name"] = new_key
            gd["tags"][new_key] = tag
            del gd["tags"][old_key]
            for alias, target in list(gd["aliases"].items()):
                if target == old_key:
                    gd["aliases"][alias] = new_key
            await self._flush()
            return "ok"

    async def stats(self, guild_id: int) -> dict:
        """Return global tag statistics."""
        async with _lock:
            await self._ensure_loaded()
            gd = _global_data(self._data)
            tags = list(gd["tags"].values())
            total_uses = sum(t.get("uses", 0) for t in tags)
            top = sorted(tags, key=lambda t: t.get("uses", 0), reverse=True)[:5]
            return {
                "total_tags": len(tags),
                "total_aliases": len(gd["aliases"]),
                "total_uses": total_uses,
                "top_tags": top,
            }

    async def set_perms(
        self,
        guild_id: int,
        name: str,
        allowed_roles: list,
        denied_users: list,
        requester_id: int,
        is_owner: bool,
    ) -> str:
        async with _lock:
            await self._ensure_loaded()
            gd = _global_data(self._data)
            name = name.lower()
            if name in gd["aliases"]:
                name = gd["aliases"][name]
            tag = gd["tags"].get(name)
            if tag is None:
                return "not_found"
            if not is_owner and tag["owner_id"] != requester_id:
                return "not_owner"
            tag["allowed_roles"] = allowed_roles
            tag["denied_users"] = denied_users
            await self._flush()
            return "ok"
