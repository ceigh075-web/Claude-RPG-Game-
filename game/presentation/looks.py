"""Who looks like what: character looks built from roles (occupations), factions, towns, age and personality.

Everything is deterministic (seeded by NPC id / spawn seed), purely visual, and expressed as a `look` dict
for charsprites + wardrobe. Named NPCs get a hand-tuned identity on top of their role; anonymous townsfolk
and enemies draw from role pools so a crowd never looks like one sprite recoloured.
"""
from ..core.rng import stable_rng

EARTH = [(122, 86, 54), (96, 78, 60), (140, 110, 70), (90, 100, 60), (110, 120, 80), (150, 130, 96), (80, 70, 64),
         (128, 96, 72), (104, 84, 50)]
MUTED = [(90, 96, 110), (70, 84, 100), (110, 110, 118), (84, 96, 84), (120, 104, 96), (66, 70, 84), (140, 130, 120)]
RICH = [(150, 40, 52), (110, 50, 140), (40, 110, 120), (60, 80, 160), (170, 120, 40), (40, 100, 60), (160, 70, 110)]
BRIGHT = [(220, 120, 50), (200, 60, 90), (70, 160, 200), (230, 200, 80), (120, 190, 90), (180, 90, 200)]
PANTS = [(70, 60, 50), (60, 56, 64), (84, 70, 52), (50, 50, 60), (96, 84, 66), (70, 76, 60), (40, 40, 46)]
BOOTS = [(54, 40, 32), (40, 34, 30), (70, 52, 36), (30, 30, 34), (90, 66, 44)]
STRAW, LEATHER, IRON, STEEL, DARKSTEEL = (214, 184, 112), (120, 82, 50), (150, 154, 166), (176, 182, 194), (60, 60, 70)
FACTION_COL = {"crown": (70, 100, 180), "ironhold": (170, 100, 50), "caravans": (40, 150, 150), "ashen": (120, 80, 170),
               "thornblood": (120, 90, 40), "hollow": (60, 60, 66)}

# role -> template: each key is a list of options (or a fixed value); "p_*" keys are probabilities
ROLES = {
    "citizen": {"outfit": ["tunic", "tunic", "vest", "dress", "coat"], "palette": [EARTH, MUTED, BRIGHT], "p_hat": 0.25,
                "hat": ["cap", "wide", "bandana", "feather_cap"], "p_acc": 0.4, "acc": ["scarf", "satchel", "necklace", "earring"]},
    "farmer": {"outfit": ["vest", "tunic", "apron"], "palette": [EARTH], "p_hat": 0.7, "hat": ["wide"], "hat_col": [STRAW],
               "p_acc": 0.3, "acc": ["satchel", "scarf"], "belt": LEATHER},
    "miner": {"outfit": ["vest", "tunic"], "palette": [MUTED, EARTH], "p_hat": 0.9, "hat": ["miner"], "hat_col": [(196, 160, 50)],
              "p_acc": 0.5, "acc": ["satchel"], "build": "stout"},
    "smith": {"outfit": ["apron"], "accent": [(110, 70, 40), (80, 60, 44)], "palette": [MUTED, EARTH], "p_hat": 0.2,
              "hat": ["bandana"], "build": "stout", "p_beard": 0.7, "hair_style": [2, 3, 3, 6]},
    "merchant": {"outfit": ["coat", "vest", "dress"], "palette": [RICH, BRIGHT], "p_hat": 0.45, "hat": ["feather_cap", "wide", "cap"],
                 "p_acc": 0.9, "acc": ["necklace", "satchel", "earring"], "belt": (90, 60, 40)},
    "guard": {"outfit": ["tabard"], "armor": IRON, "palette": [MUTED], "p_helm": 0.6, "p_acc": 1.0, "acc": ["pauldrons"],
              "belt": LEATHER, "hair_style": [0, 2, 2, 3]},
    "noble": {"outfit": ["coat", "dress"], "palette": [RICH], "p_cape": 0.7, "p_acc": 1.0, "acc": ["necklace", "earring"],
              "p_hat": 0.3, "hat": ["circlet", "feather_cap"], "hat_col": [(210, 210, 230), (120, 40, 60)]},
    "scholar": {"outfit": ["robe", "coat", "vest"], "palette": [MUTED, RICH], "p_acc": 0.9, "acc": ["glasses", "satchel"],
                "p_hat": 0.2, "hat": ["cap"]},
    "mage": {"outfit": ["robe"], "palette": [RICH], "p_hat": 0.7, "hat": ["wizard", "circlet"], "p_acc": 0.5,
             "acc": ["necklace", "glasses"], "p_cape": 0.3, "height": "tall"},
    "healer": {"outfit": ["robe", "dress"], "palette": [[(230, 230, 220), (200, 220, 200), (180, 210, 190), (240, 236, 214)]],
               "p_hat": 0.5, "hat": ["hood_up"], "hat_col": [(220, 220, 210), (150, 190, 150)], "p_acc": 0.6, "acc": ["satchel", "necklace"]},
    "hunter": {"outfit": ["vest", "coat", "tunic"], "palette": [EARTH, [(70, 90, 60), (90, 110, 70), (60, 80, 60)]],
               "p_hat": 0.7, "hat": ["hood_up", "feather_cap"], "hat_col": [(70, 90, 60), (110, 80, 50)], "p_acc": 1.0,
               "acc": ["quiver", "fur", "satchel"], "belt": LEATHER},
    "sailor": {"outfit": ["vest", "apron", "tunic"], "palette": [[(60, 90, 140), (220, 220, 210), (150, 50, 50), (60, 120, 130)], MUTED],
               "p_hat": 0.6, "hat": ["bandana", "cap"], "p_acc": 0.5, "acc": ["earring", "scarf"]},
    "bard": {"outfit": ["vest", "coat"], "palette": [BRIGHT], "p_hat": 0.9, "hat": ["feather_cap"], "p_acc": 1.0,
             "acc": ["scarf", "earring", "satchel"]},
    "warrior": {"outfit": ["tunic", "vest", "bare"], "armor": LEATHER, "palette": [EARTH, MUTED], "p_acc": 0.9,
                "acc": ["pauldrons", "eyepatch", "belt"], "belt": (70, 50, 36), "p_beard": 0.6, "hair_style": [2, 3, 6, 9, 4]},
    "rogue": {"outfit": ["vest", "coat"], "palette": [[(50, 50, 56), (70, 60, 56), (60, 70, 60), (80, 50, 50)]],
              "p_hat": 0.7, "hat": ["hood_up", "bandana"], "hat_col": [(50, 50, 56), (90, 40, 40)], "p_acc": 0.9,
              "acc": ["scarf", "satchel", "eyepatch"]},
    "priest": {"outfit": ["robe"], "palette": [[(200, 190, 160), (120, 110, 90), (220, 220, 210)]], "hair_style": [3, 3, 2],
               "p_beard": 0.8, "p_acc": 0.6, "acc": ["necklace"]},
    "witch": {"outfit": ["robe", "dress"], "palette": [[(60, 50, 70), (50, 70, 50), (80, 60, 50)]], "p_hat": 0.9,
              "hat": ["wizard"], "hat_col": [(40, 36, 50), (60, 50, 40)], "hair_style": [1, 7, 8], "p_acc": 0.8, "acc": ["necklace"]},
    "shaman": {"outfit": ["robe", "bare"], "palette": [EARTH], "p_hat": 0.6, "hat": ["horns"], "p_acc": 1.0,
               "acc": ["fur", "necklace"], "necklace": (230, 220, 190), "warpaint": [(170, 40, 40), (230, 230, 220)]},
    "raider": {"outfit": ["bare", "vest", "tunic"], "palette": [EARTH], "p_hat": 0.35, "hat": ["horns"], "p_acc": 1.0,
               "acc": ["fur", "pauldrons", "belt"], "armor": LEATHER, "warpaint": [(170, 40, 40), (40, 40, 40), (230, 230, 220)],
               "hair_style": [6, 3, 4, 9, 2], "build": "stout", "p_beard": 0.4},
}

OCCUPATION = [  # (keyword in occupation, role, extra overrides)
    ("queen", "noble", {"hat": "crown", "outfit": "dress", "cape": (110, 40, 130)}),
    ("chief of the hollow", "warrior", {"armor": (40, 38, 46), "cape": (90, 20, 30), "acc": ["pauldrons", "scarf"],
                                        "scarf": (60, 20, 24), "outfit": "tunic", "beard": 2}),
    ("archmage", "mage", {"hat": "wizard", "beard": 4, "outfit": "robe", "cape": None}),
    ("spell tutor", "mage", {"hat": "circlet", "hair_style": 5}),
    ("guard captain", "guard", {"cape": (40, 60, 140), "helm": None, "hair_style": 4}),
    ("sergeant", "guard", {"helm": IRON}),
    ("retired soldier", "guard", {"acc": ["eyepatch", "pauldrons"], "beard": 2, "helm": None, "armor": (120, 122, 130)}),
    ("wandering knight", "guard", {"armor": STEEL, "helm": STEEL, "cape": (150, 140, 100), "outfit": "tabard"}),
    ("frontier warden", "hunter", {"cape": (60, 90, 60), "hat": "hood_up", "hat_col": (60, 90, 60)}),
    ("warchief", "raider", {"hat": "horns", "acc": ["fur", "pauldrons", "necklace"], "necklace": (230, 220, 190),
                            "cape": (110, 70, 40)}),
    ("shaman", "shaman", {"hair_style": 8}),
    ("pit fighter", "raider", {"outfit": "bare", "hat": None, "hair_style": 6}),
    ("mercenary boss", "warrior", {"cape": (140, 40, 40), "outfit": "vest"}),
    ("sellsword", "warrior", {"acc": ["eyepatch", "pauldrons"], "beard": 2}),
    ("mercenary archer", "hunter", {"hat": "hood_up", "hat_col": (60, 60, 66)}),
    ("hunter", "hunter", {}),
    ("caravan guard", "warrior", {"hat": "bandana", "hat_col": (40, 150, 150)}),
    ("smuggler", "sailor", {"hat": "wide", "hat_col": (50, 44, 44), "outfit": "coat", "acc": ["eyepatch", "earring"], "beard": 2}),
    ("fishmonger", "sailor", {"outfit": "apron", "hat": "bandana"}),
    ("mistress", "merchant", {"outfit": "dress", "hat": "wide", "hat_col": (40, 150, 150), "acc": ["necklace", "earring"]}),
    ("guildmaster", "merchant", {"outfit": "coat", "acc": ["necklace"], "beard": 4, "hat": None}),
    ("information broker", "rogue", {"hat": "hood_up"}),
    ("young trader", "merchant", {"hat": "cap", "acc": ["satchel"]}),
    ("scavenger", "rogue", {"hat": "cap", "outfit": "coat", "acc": ["satchel", "scarf"]}),
    ("ruin delver", "rogue", {"hat": "bandana", "acc": ["satchel", "glasses"]}),
    ("captive thief", "rogue", {"hat": "bandana", "outfit": "tunic", "acc": ["scarf"]}),
    ("disgraced noble", "noble", {"cape": (90, 70, 60), "outfit": "coat", "hat": None}),
    ("archivist", "scholar", {"outfit": "robe", "acc": ["glasses"], "hair_style": 5}),
    ("bounty clerk", "scholar", {"outfit": "vest", "acc": ["glasses"]}),
    ("assayer", "scholar", {"outfit": "apron", "acc": ["glasses"], "accent": (150, 130, 100)}),
    ("tinkerer", "smith", {"acc": ["glasses", "satchel"], "build": None, "hat": "bandana"}),
    ("apprentice smith", "smith", {"height": "short", "beard": 0, "hair_style": 9}),
    ("master smith", "smith", {"beard": 2, "hair_style": 3}),
    ("leatherworker", "smith", {"outfit": "vest", "build": None, "hat": "bandana", "beard": 0}),
    ("forewoman", "miner", {"acc": ["pauldrons"]}),
    ("ex-raider", "miner", {"warpaint": (170, 40, 40)}),
    ("miner", "miner", {}),
    ("herbalist", "healer", {"outfit": "dress", "hat": None, "acc": ["satchel"], "outfit_col": (90, 140, 80)}),
    ("circle healer", "healer", {}),
    ("hermit priest", "priest", {"beard": 4}),
    ("bog witch", "witch", {}),
    ("bog guide", "hunter", {"hat": "wide", "hat_col": (90, 80, 60), "outfit": "coat"}),
    ("innkeeper", "smith", {"outfit": "apron", "accent": (220, 210, 190), "build": "stout", "beard": 3, "hat": None}),
    ("provisioner", "merchant", {"outfit": "apron", "accent": (214, 204, 182), "hat": "bandana", "hat_col": (150, 60, 60)}),
    ("farmhand", "farmer", {}),
    ("street bard", "bard", {}),
    ("noble", "noble", {}),
]

TOWN_ROLES = {"farming": ["farmer", "farmer", "citizen"], "military": ["guard", "citizen", "citizen", "noble"],
              "mining": ["miner", "miner", "citizen"], "crafting": ["smith", "merchant", "citizen"],
              "trading": ["merchant", "sailor", "citizen"], "magic": ["mage", "healer", "citizen"],
              "mercenary": ["warrior", "rogue", "citizen"], "hunting": ["hunter", "shaman", "raider"],
              "frontier": ["hunter", "rogue", "citizen"]}


def _pick(rng, v):
    return rng.choice(v) if isinstance(v, list) else v


def _greyed(c, f):
    g = sum(c) / 3 * 0.6 + 120
    return [max(0, min(255, int(v * (1 - f) + g * f))) for v in c]


def build(rng, race_data, race_id, role="citizen", faction=None, age=30, pronouns="they/them", personality=None):
    """A full look for a role. `rng` should be a seeded stable_rng."""
    T = ROLES.get(role, ROLES["citizen"])
    pal = rng.choice(T["palette"])
    look = {"race": race_id, "skin": list(rng.choice(race_data["skin"])), "hair": list(rng.choice(race_data["hair"]))}
    styles = T.get("hair_style") or [0, 1, 2, 4, 5, 7, 8, 9, 0, 1, 2]
    if pronouns == "she/her" and "hair_style" not in T:
        styles = [1, 1, 4, 5, 7, 8, 0, 2]
    look["hair_style"] = rng.choice(styles)
    beard_p = T.get("p_beard", 0.35) if pronouns == "he/him" else (0.08 if pronouns == "they/them" else 0.0)
    look["beard"] = rng.choice([1, 2, 2, 3, 4]) if rng.random() < beard_p else 0
    # age
    if age >= 45:
        look["hair"] = _greyed(look["hair"], min(1.0, (age - 40) / 35))
        if pronouns == "he/him" and age >= 55 and rng.random() < 0.35:
            look["hair_style"] = 3
    # clothes
    shirt = rng.choice(pal)
    look["outfit"] = _pick(rng, T["outfit"])
    look["shirt"] = list(shirt)
    look["outfit_col"] = list(shirt)
    look["accent"] = list(_pick(rng, T["accent"])) if "accent" in T else list(rng.choice(RICH if pal is not RICH else MUTED))
    look["pants"] = list(rng.choice(PANTS))
    look["boots"] = list(rng.choice(BOOTS))
    if "belt" in T or rng.random() < 0.4:
        look["belt"] = list(T.get("belt", (70, 50, 36)))
    if T.get("armor"):
        look["armor"] = list(T["armor"])
    if T.get("p_helm") and rng.random() < T["p_helm"]:
        look["helm"] = list(T.get("armor", IRON))
    if rng.random() < T.get("p_hat", 0):
        look["hat"] = _pick(rng, T["hat"])
        look["hat_col"] = list(_pick(rng, T["hat_col"])) if "hat_col" in T else list(rng.choice(EARTH + MUTED))
    if rng.random() < T.get("p_cape", 0):
        look["cape"] = list(rng.choice(RICH))
    acc = []
    if T.get("acc") and rng.random() < T.get("p_acc", 0):
        pool = list(T["acc"])
        rng.shuffle(pool)
        acc = pool[:rng.randint(1, min(2, len(pool)))]
    if "pauldrons" in T.get("acc", ()) and role in ("guard",):
        acc = sorted(set(acc) | {"pauldrons"})
    look["acc"] = [a for a in acc if a != "belt"]
    if "necklace" in T:
        look["necklace"] = list(T["necklace"])
    if "scarf" in look["acc"]:
        look["scarf"] = list(rng.choice(BRIGHT + RICH))
    if "warpaint" in T and rng.random() < 0.8:
        look["warpaint"] = list(_pick(rng, T["warpaint"]))
    for k in ("build", "height"):
        if T.get(k) and rng.random() < 0.7:
            look[k] = T[k]
    # race tendencies: murrok broad, sylth willowy, kethari compact
    if race_id == "murrok" and rng.random() < 0.6:
        look["build"] = "stout"
    elif race_id == "sylth" and rng.random() < 0.5:
        look["height"] = "tall"
        look.setdefault("build", "slim")
    elif race_id == "kethari" and rng.random() < 0.4:
        look["height"] = "short"
    # faction colours on what they wear
    fc = FACTION_COL.get(faction)
    if fc:
        if look["outfit"] == "tabard":
            look["outfit_col"] = list(fc)
            look["accent"] = [240, 210, 90] if faction != "hollow" else [150, 150, 160]
        elif rng.random() < 0.6:
            look["shirt"] = list(fc)
            look["outfit_col"] = list(fc)
        elif "cape" in look:
            look["cape"] = list(fc)
    # personality touches
    p = personality or {}
    if p.get("greed", 5) >= 7 and "necklace" not in look["acc"]:
        look["acc"].append("necklace")
    if p.get("sociability", 5) >= 8 and rng.random() < 0.5:
        look["shirt"] = list(rng.choice(BRIGHT))
        look["outfit_col"] = look["shirt"]
    if p.get("honesty", 5) <= 3 and "scarf" not in look["acc"] and rng.random() < 0.6:
        look["acc"].append("scarf")
        look["scarf"] = list(rng.choice(MUTED))
    if p.get("intelligence", 5) >= 9 and "glasses" not in look["acc"] and rng.random() < 0.4:
        look["acc"].append("glasses")
    return look


def role_for(npc):
    occ = npc.get("occupation", "").lower()
    for key, role, extra in OCCUPATION:
        if key in occ:
            return role, extra
    return "citizen", {}


def npc_identity(data, npc):
    """The look of a named NPC: their role, faction, age, pronouns and personality, plus a hand-set signature."""
    rng = stable_rng("look2", npc["id"])
    role, extra = role_for(npc)
    look = build(rng, data.races[npc["race"]], npc["race"], role, npc.get("faction"), npc.get("age", 30),
                 npc.get("pronouns", "they/them"), npc.get("personality"))
    for k, v in extra.items():
        if v is None:
            look.pop(k, None)
        elif k == "acc":
            look["acc"] = sorted(set(look.get("acc", [])) | set(v))
        else:
            look[k] = list(v) if isinstance(v, tuple) else v
    if "scarf" in look.get("acc", []) and "scarf" not in look:
        look["scarf"] = [170, 60, 50]
    if look.get("hat") and "hat_col" not in look:
        look["hat_col"] = [120, 80, 50]
    if look.get("beard") and npc.get("pronouns") == "she/her":
        look["beard"] = 0
    if npc.get("faction") == "thornblood" and "warpaint" not in look:
        look["warpaint"] = [170, 40, 40]
    return look


def townsfolk(data, rng, specialty, race_id=None):
    role = rng.choice(TOWN_ROLES.get(specialty, ["citizen"]))
    race_id = race_id or rng.choice(list(data.races))
    pron = rng.choice(["he/him", "she/her", "they/them"])
    return build(rng, data.races[race_id], race_id, role, None, rng.randint(18, 75), pron), role


# ----------------------------------------------------------------------------- enemies
ENEMY_ROLE = {"bandit_cutthroat": "rogue", "bandit_archer": "hunter", "hollow_shieldbearer": "guard",
              "hollow_captain": "warrior", "thornblood_raider": "raider", "hollow_hexer": "witch",
              "hollow_stormcaller": "mage", "thornblood_shaman": "shaman", "frost_witch": "witch"}


def enemy_variant(data, enemy_id, seed):
    """A varied look for one humanoid enemy (stable per spawned combatant)."""
    rng = stable_rng("enemy_look", enemy_id, seed)
    role = ENEMY_ROLE.get(enemy_id, "rogue")
    race = "murrok" if enemy_id in ("thornblood_raider", "thornblood_shaman") else rng.choice(["human", "human", "kethari", "murrok", "sylth"])
    pron = rng.choice(["he/him", "she/her", "they/them"])
    look = build(rng, data.races[race], race, role, "hollow" if enemy_id.startswith("hollow") else
                 ("thornblood" if enemy_id.startswith("thornblood") else None), rng.randint(20, 55), pron)
    if enemy_id == "bandit_cutthroat":
        look["hat"] = rng.choice(["hood_up", "hood_up", "bandana", None])
        look["hat_col"] = list(rng.choice([(78, 58, 46), (60, 50, 44), (90, 40, 36), (50, 50, 56)]))
        look["acc"] = sorted(set(look.get("acc", [])) | {"scarf"})
        look["scarf"] = list(rng.choice([(70, 50, 40), (90, 30, 30), (40, 40, 44)]))
    elif enemy_id == "bandit_archer":
        look["acc"] = sorted(set(look.get("acc", [])) | {"quiver"})
        look["hat"] = rng.choice(["hood_up", "feather_cap"])
        look["hat_col"] = list(rng.choice([(64, 90, 56), (80, 70, 50), (60, 60, 50)]))
    elif enemy_id == "hollow_shieldbearer":
        look["armor"] = list(rng.choice([(118, 122, 134), (100, 104, 114), (130, 126, 120)]))
        look["helm"] = list(rng.choice([(104, 108, 120), (90, 92, 100)]))
        look["outfit"] = "tabard"
        look["outfit_col"] = [56, 56, 62]
        look["accent"] = [150, 150, 160]
        look["acc"] = ["pauldrons"]
    elif enemy_id == "hollow_captain":
        look["armor"] = [52, 50, 62]
        look["helm"] = [40, 38, 48] if rng.random() < 0.5 else None
        look["cape"] = list(rng.choice([(110, 24, 30), (40, 30, 40)]))
        look["acc"] = ["pauldrons"]
        look["smear"] = [255, 150, 150]
        if look["helm"] is None:
            look.pop("helm")
    elif enemy_id == "frost_witch":
        look["hat"] = rng.choice(["wizard", "hood_up"])
        look["hat_col"] = list(rng.choice([(200, 220, 240), (120, 150, 190)]))
        look["outfit"], look["outfit_col"] = "robe", list(rng.choice([(170, 200, 230), (110, 140, 190)]))
        look["hair"] = [230, 236, 245]
    elif enemy_id in ("hollow_hexer", "hollow_stormcaller"):
        look["outfit"], look["outfit_col"] = "robe", [52, 50, 60]
        look["hat"] = "hood_up" if enemy_id == "hollow_hexer" else "wizard"
        look["hat_col"] = [40, 38, 46] if enemy_id == "hollow_hexer" else [70, 80, 110]
        look["smear"] = [190, 150, 255]
    elif enemy_id in ("thornblood_raider", "thornblood_shaman"):
        look["skin"] = list(rng.choice(data.races["murrok"]["skin"]))
        look.setdefault("warpaint", [170, 40, 40])
    return look
