"""Set AI: append-only structured world memory (SQLite). NOT a language model.

Tables
  records  - immutable history. UPDATE/DELETE are blocked by triggers.
  facts    - append-only key/value facts (e.g. "npc:garrow:alive" = "false"); the newest row wins.
  chatter  - low-importance conversational snippets; bounded rolling buffer, may be pruned, never history.
"""
import json
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,          -- character id, faction id, location id or 'world'
    location TEXT,
    event_type TEXT NOT NULL,       -- conversation, gift, promise, promise_broken, battle, death, discovery ...
    description TEXT NOT NULL,
    day INTEGER NOT NULL,
    minute INTEGER NOT NULL DEFAULT 0,
    importance INTEGER NOT NULL,    -- 1 minor .. 5 world-changing
    related TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL DEFAULT 'set_system'
);
CREATE INDEX IF NOT EXISTS idx_records_subject ON records(subject);
CREATE TRIGGER IF NOT EXISTS records_no_update BEFORE UPDATE ON records
BEGIN SELECT RAISE(ABORT, 'Set AI history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS records_no_delete BEFORE DELETE ON records
BEGIN SELECT RAISE(ABORT, 'Set AI history is append-only'); END;

CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    day INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(key);
CREATE TRIGGER IF NOT EXISTS facts_no_update BEFORE UPDATE ON facts
BEGIN SELECT RAISE(ABORT, 'Set AI facts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS facts_no_delete BEFORE DELETE ON facts
BEGIN SELECT RAISE(ABORT, 'Set AI facts are append-only'); END;

CREATE TABLE IF NOT EXISTS chatter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    text TEXT NOT NULL,
    day INTEGER NOT NULL
);
"""

CHATTER_LIMIT_PER_SUBJECT = 12
MIN_HISTORY_IMPORTANCE = 2  # conversation-type records below this go to chatter instead
CHATTY_TYPES = {"conversation", "smalltalk"}

EVENT_TYPES = {
    # NPC memories
    "conversation", "witnessed", "promise", "promise_broken", "promise_kept", "gift", "relationship",
    "significant", "personal",
    # companion memories
    "recruited", "dismissed", "battle", "travel", "companion_bond", "companion_conflict",
    # enemy memories
    "encounter", "escaped", "defeated",
    # world history
    "war", "faction_change", "death", "settlement", "political", "accomplishment", "world_event",
    # player journey
    "discovery", "kindness", "defiance", "reputation", "trade", "arrival",
}


class MemoryError_(Exception):
    pass


class MemoryStore:
    def __init__(self, path=":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ------------------------------------------------------------------ writing
    def record(self, subject, event_type, description, day, minute=0, importance=1, related=None,
               location=None, source="set_system"):
        """Append a history record. Low-importance chatter is diverted to the prunable chatter table."""
        if event_type not in EVENT_TYPES:
            raise MemoryError_(f"unknown event type '{event_type}'")
        importance = max(1, min(5, int(importance)))
        if event_type in CHATTY_TYPES and importance < MIN_HISTORY_IMPORTANCE:
            self.add_chatter(subject, description, day)
            return None
        cur = self.conn.execute(
            "INSERT INTO records(subject, location, event_type, description, day, minute, importance, related, source)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (subject, location, event_type, description, day, minute, importance, json.dumps(related or []), source))
        self.conn.commit()
        return cur.lastrowid

    def set_fact(self, key, value, day):
        self.conn.execute("INSERT INTO facts(key, value, day) VALUES (?,?,?)", (key, json.dumps(value), day))
        self.conn.commit()

    def add_chatter(self, subject, text, day):
        self.conn.execute("INSERT INTO chatter(subject, text, day) VALUES (?,?,?)", (subject, text, day))
        self.conn.execute(
            "DELETE FROM chatter WHERE subject = ? AND id NOT IN "
            "(SELECT id FROM chatter WHERE subject = ? ORDER BY id DESC LIMIT ?)",
            (subject, subject, CHATTER_LIMIT_PER_SUBJECT))
        self.conn.commit()

    # ------------------------------------------------------------------ reading
    def fact(self, key, default=None):
        row = self.conn.execute("SELECT value FROM facts WHERE key = ? ORDER BY id DESC LIMIT 1", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def facts_with_prefix(self, prefix):
        rows = self.conn.execute(
            "SELECT key, value FROM facts f WHERE key LIKE ? AND id = (SELECT MAX(id) FROM facts WHERE key = f.key)",
            (prefix + "%",)).fetchall()
        return {k: json.loads(v) for k, v in rows}

    def _rows(self, sql, args):
        cols = ("id", "subject", "location", "event_type", "description", "day", "minute", "importance", "related", "source")
        out = []
        for r in self.conn.execute(sql, args).fetchall():
            d = dict(zip(cols, r))
            d["related"] = json.loads(d["related"])
            out.append(d)
        return out

    def about(self, subject, limit=10, min_importance=1):
        """Records where `subject` is the subject or among related characters, most important then newest."""
        like = f'%"{subject}"%'
        return self._rows(
            "SELECT id, subject, location, event_type, description, day, minute, importance, related, source FROM records"
            " WHERE (subject = ? OR related LIKE ?) AND importance >= ?"
            " ORDER BY importance DESC, day DESC, minute DESC, id DESC LIMIT ?",
            (subject, like, min_importance, limit))

    def recent(self, limit=20, min_importance=1):
        return self._rows(
            "SELECT id, subject, location, event_type, description, day, minute, importance, related, source FROM records"
            " WHERE importance >= ? ORDER BY id DESC LIMIT ?", (min_importance, limit))

    def world_history(self, limit=30, min_importance=3):
        return self.recent(limit, min_importance)

    def chatter(self, subject, limit=5):
        rows = self.conn.execute("SELECT text, day FROM chatter WHERE subject = ? ORDER BY id DESC LIMIT ?",
                                 (subject, limit)).fetchall()
        return [{"text": t, "day": d} for t, d in rows]

    def count(self):
        return self.conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]

    # ------------------------------------------------------------------ persistence
    def save_to(self, path):
        tmp = path + ".tmp"
        if os.path.exists(tmp):
            os.remove(tmp)
        dst = sqlite3.connect(tmp)
        with dst:
            self.conn.backup(dst)
        dst.close()
        os.replace(tmp, path)

    @classmethod
    def load_from(cls, path):
        store = cls(":memory:")
        src = sqlite3.connect(path)
        with store.conn:
            src.backup(store.conn)
        src.close()
        store.conn.executescript(SCHEMA)  # ensure triggers exist on old files
        return store

    def close(self):
        self.conn.close()

    def __del__(self):
        try:
            self.conn.close()
        except Exception:
            pass
