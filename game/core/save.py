"""Versioned, atomic save slots: saves/slot_N/state.json + memory.sqlite."""
import datetime
import json
import os
import shutil

from .state import GameState
from ..set_ai.memory import MemoryStore

SAVE_VERSION = 2
NUM_SLOTS = 3
AUTOSAVE_SLOT = 0
from .paths import SAVE_DIR as DEFAULT_DIR


# Migration functions upgrade a raw save dict from version N to N+1.
def _v1_to_v2(payload):
    """Phase 3: spellbook and weapon mode added."""
    from ..set_system.spells import starter_spellbook
    st = payload["state"]
    st.setdefault("spellbook", starter_spellbook())
    st["settings"].setdefault("weapon_mode", "melee")
    if st.get("travel"):
        st["travel"].setdefault("pending_combat", None)
    payload["version"] = 2
    return payload


MIGRATIONS = {
    1: _v1_to_v2,
}


class SaveError(Exception):
    pass


class SaveManager:
    def __init__(self, root=None):
        self.root = os.path.normpath(root or os.environ.get("KINDRED_SAVE_DIR") or DEFAULT_DIR)

    def slot_dir(self, slot):
        return os.path.join(self.root, "autosave" if slot == AUTOSAVE_SLOT else f"slot_{slot}")

    def exists(self, slot):
        return os.path.exists(os.path.join(self.slot_dir(slot), "state.json"))

    def save(self, state, slot):
        d = self.slot_dir(slot)
        os.makedirs(d, exist_ok=True)
        payload = {
            "version": SAVE_VERSION,
            "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "summary": {
                "name": state.player.name, "location": state.data.location(state.location)["name"],
                "date": state.clock.date_str(), "level": state.player.level, "gold": state.gold,
            },
            "state": state.to_dict(),
        }
        tmp = os.path.join(d, "state.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        # keep the previous save as a backup in case the new one is ever damaged
        cur = os.path.join(d, "state.json")
        if os.path.exists(cur):
            shutil.copyfile(cur, cur + ".bak")
            mem = os.path.join(d, "memory.sqlite")
            if os.path.exists(mem):
                shutil.copyfile(mem, mem + ".bak")
        state.memory.save_to(os.path.join(d, "memory.sqlite"))
        os.replace(tmp, cur)

    def load(self, slot, data):
        try:
            return self._load(slot, data, "")
        except SaveError as first:
            if os.path.exists(os.path.join(self.slot_dir(slot), "state.json.bak")):
                try:
                    return self._load(slot, data, ".bak")
                except SaveError:
                    pass
            raise first

    def _load(self, slot, data, suffix):
        d = self.slot_dir(slot)
        try:
            with open(os.path.join(d, "state.json" + suffix), encoding="utf-8") as f:
                payload = json.load(f)
            if "state" not in payload:
                raise ValueError("missing state")
        except (OSError, json.JSONDecodeError, ValueError) as e:
            raise SaveError(f"Could not read save slot {slot}: {e}") from e
        version = payload.get("version", 0)
        if version > SAVE_VERSION:
            raise SaveError(f"Save version {version} is newer than this game ({SAVE_VERSION}).")
        while version < SAVE_VERSION:
            if version not in MIGRATIONS:
                raise SaveError(f"No migration from save version {version}.")
            payload = MIGRATIONS[version](payload)
            version += 1
        mem_path = os.path.join(d, "memory.sqlite" + suffix)
        if not os.path.exists(mem_path):
            mem_path = os.path.join(d, "memory.sqlite")
        try:
            memory = MemoryStore.load_from(mem_path) if os.path.exists(mem_path) else MemoryStore()
            return GameState.from_dict(data, payload["state"], memory)
        except Exception as e:  # damaged content: report as a save error so the backup can be tried
            raise SaveError(f"Save slot {slot} is damaged: {e}") from e

    def summary(self, slot):
        if not self.exists(slot):
            return None
        try:
            with open(os.path.join(self.slot_dir(slot), "state.json"), encoding="utf-8") as f:
                payload = json.load(f)
            return dict(payload.get("summary", {}), saved_at=payload.get("saved_at", "?"))
        except (OSError, json.JSONDecodeError):
            return {"name": "(corrupt save)", "location": "", "date": "", "level": 0, "gold": 0, "saved_at": "?"}

    def most_recent_slot(self):
        best, best_t = None, None
        for s in range(0, NUM_SLOTS + 1):
            p = os.path.join(self.slot_dir(s), "state.json")
            if os.path.exists(p):
                t = os.path.getmtime(p)
                if best_t is None or t > best_t:
                    best, best_t = s, t
        return best
