"""The Adventurer's Guide (H): a parchment book of tutorials and everything you've learned about the world.

Chapters are generated from live game data and your progress (discovered places, active jobs, tips seen),
so the advice is always accurate and grows as you explore.
"""
import pygame

from ...core.scene import Scene
from ...set_system import aggression, spells
from .. import knowledge
from ..ui import widgets as ui
from .common import CONTROLS, is_close

W, H = 1280, 720
KEY_ITEMS = ["rustite_ore", "greyvein_ore", "sunsilver_ore", "voidglass_ore", "wood", "herbs", "mirelight_herb",
             "berries", "mushrooms", "hide", "meat", "fish", "salt", "mana_crystal", "scrap", "enchanted_ink"]


def chapters(scene):
    st, data = scene.state, scene.data
    p = st.player
    out = []
    out.append(("Getting Started", [
        ("", "Welcome to the roads. You start in Brackenford with a little food, a knife and 25 marks."),
        ("First steps", "Talk to people (E). Check the job board on the town square. Buy a pickaxe or hatchet at "
                        "the Provisions so you can mine and chop. Head into nearby Meadowrun Fields to forage and hunt."),
        ("Stay alive", "Watch Food and Water (top left). Eat and drink from your Inventory (I). Rest at inns or "
                       "your own house. If you fall in battle you lose some marks and wake up somewhere safe."),
        ("Get stronger", "Skills improve by doing: fighting trains weapon skills, crafting trains Crafting, casting "
                         "trains Magic. Your level rises with experience and unlocks bigger spell books and spell tiers."),
        ("Lost?", "This guide (H) knows where to find every resource you've heard of, how to earn money, and what "
                  "your current jobs need. The Journal (J) keeps your log, news and history."),
    ]))
    out.append(("Earning Money", [("", "Ways to earn marks, roughly from easiest to most lucrative:")] +
                [(t, d) for t, d in knowledge.money_methods(st)]))
    res = [("", "Where the main resources come from. Places you haven't been yet are marked (unexplored).")]
    for item in KEY_ITEMS:
        if item in data.items:
            res.append((data.item(item)["name"], "; ".join(knowledge.sources(st, item)[:2])))
    out.append(("Resources", res))
    regen_c = spells.regen_per_second(p, False)
    regen_f = spells.regen_per_second(p, True)
    out.append(("Magic & Mana", [
        ("Your mana", f"You hold {p.max_mana} mana (80 + 2 per Magic skill point + 5 per level). The blue bar shows it; "
                      f"white ticks on the bar mark what each hotbar spell costs."),
        ("Elements", "Fire is power and destruction; Water is recovery and slowing; Earth is defense, shields and "
                     "durability; Air is speed, reach and displacement; Light is the strongest healing and "
                     "protection. You can cast with an element alone - a sub-element (Ice, Lightning, Mending...) "
                     "is an optional specialisation."),
        ("Shaping spells", "Movement: bolt, seeker, beam, wave, explosion, field, orbit, ward, aura, burst (nova), "
                           "chain, trap, barrier or self. Focus: power, speed, range, duration, area, efficiency or "
                           "control - each element favours one (+10%). Size: from a pinpoint to a vast blast; "
                           "bigger costs much more mana. The designer shows the cost as you go."),
        ("Refilling", f"Mana refills by itself: {regen_c:.1f}/s out of combat, {regen_f:.1f}/s while fighting. "
                      f"Every weapon hit you land restores {int(spells.HIT_MANA_RATIO * 100)}% of the damage as mana "
                      f"(up to {int(spells.HIT_MANA_CAP)} per hit). Resting and Mana Crystals also help."),
        ("Designing spells", "Open the spell book (B) anywhere. N designs a new spell, E edits any spell; Enter "
                             "inscribes a draft. It's free. Spells only need a split second between casts: mana is "
                             "the real limit."),
        ("Your book", "Inscribed spells go on the 1-4 hotbar. The book holds more spells as you level up. "
                      "Practice yards (barracks, arenas, your house) let you test drafts safely."),
    ]))
    out.append(("Combat", [
        ("Basics", "Left mouse / K attacks (press again for combos), right mouse / L blocks, Space dodges "
                   "(brief invulnerability), F kicks to break guards. Q swaps melee and ranged weapons."),
        ("Read the enemy", "Enemies wind up before striking: block or dodge then. Heavy foes show a red '!' "
                           "before big hits. Hits from behind deal extra damage."),
        ("Everyone can be fought", "Normal attacks only hit enemies. Press G for hostile intent to attack anyone, "
                                   "including townsfolk and companions. People fight back, flee or call for help, "
                                   "and you lose standing with their faction."),
        ("Defeat and death", f"At 0 health people are knocked down, not killed: they recover and stay home "
                             f"injured for {aggression.INJURY_DAYS} day. Only a finishing blow with hostile intent "
                             f"kills, and that is permanent."),
    ]))
    stations = [("", "Crafting stations and where to find them:")]
    for stn in ("furnace", "anvil", "workbench", "stove", "alchemy", "campfire"):
        stations.append((stn.title() if stn != "alchemy" else "Alchemy table", knowledge.station_places(st, stn)))
    stations.append(("How", "Use a station (E) to see recipes. Missing ingredients are listed in red, along with "
                            "where to get them. Smelt ore into bars at a furnace, then forge at an anvil."))
    out.append(("Crafting", stations))
    out.append(("Law, Crime & Conquest", [
        ("Crime", "Stealing from barrels, crates and other people's chests, robbing the fallen, and attacking or "
                  "killing people in town are crimes if anyone sees. You lose standing and the town puts a bounty on "
                  "you. In the wilds, searching containers is fair game."),
        ("Guards", "Every town has guards. They challenge wanted criminals ('Pay your fine!') and fight if you refuse "
                   "or walk away. Pay a guard (E) or the job board to clear your name."),
        ("Seizing a town", "Beat a town's guards and you can seize it at its job board. It pays you taxes every day "
                           "and its merchants give you 15% better prices, but its old faction turns on you and may "
                           "take it back unless you keep at least 3 retainers."),
        ("Equipment shops", "Every town sells weapons and armour (Armorer, Smithy or Outfitter). Bigger towns stock "
                            "better ore; each faction's towns carry their favourite gear."),
    ]))
    out.append(("Morale & Prisoners", [
        ("Morale", "Human foes lose heart when badly hurt, when allies fall or their leader goes down. Then they "
                   "flee, or yield if they're cornered. Beasts and the dead never yield."),
        ("When they yield", "Approach (E): take them prisoner (needs a free cell), ask them to join if "
                            "they're willing, demand their purse, or let them go (their faction remembers mercy)."),
        ("Prisoners", "Open the Tab menu, Prisoners. Captives grow loyal with time, kindness (a ration a day) and "
                      "talk; hungry, resentful captives escape. Loyal captives become retainers who earn marks daily "
                      "and help hold seized towns."),
        ("Cells & beds", "A house cellar holds 1 captive in cramped conditions (resentment grows); an outpost "
                         "Stockade holds 4 in decent conditions (they warm to you faster). Retainers need beds: 1 per "
                         "house, 2 at the outpost and 4 per Bunkhouse. Full? Release someone or build more."),
    ]))
    out.append(("Looting", [
        ("Drops", "Beaten foes spill coins and materials on the ground: walk over them to pick them up. Gear stays "
                  "on the body (a bag floats over it): press E to search."),
        ("Containers", "Barrels, crates and chests open a loot list: take one thing (E) or everything (A). What you "
                       "leave stays there; emptied containers refill after a few days. In towns that's theft if seen."),
        ("Storage", "At your house chest or outpost storage, press Q to store every raw material at once."),
    ]))
    out.append(("Companions & People", [
        ("Recruiting", "Everyone can join you. Ask them what it would take: some want marks, standing, a duel or "
                       "a favor. Up to 4 travel with you; others can wait, work or guard your outpost."),
        ("Relationships", "Talking, gifts they like and finishing their favors raise friendship and trust. Attacking "
                          "people, or companions seeing you do it, lowers them. R shows everyone you know."),
        ("Your squad", "P manages tasks and gear. Companions fight beside you, heal if they know magic, and eat "
                       "from your packs."),
    ]))
    out.append(("Travel & Survival", [
        ("The road", "Walk off a map edge or press M to choose a destination. Travel takes hours; you'll eat and "
                     "drink on the way, and events can happen. Pick a pace that suits your supplies."),
        ("Weather and night", "Storms and snow slow you and make you thirsty. Night is dangerous: camp or find a bed."),
        ("Saving", "F5 quick-saves, F9 loads. The game also autosaves when you arrive somewhere and after sleeping."),
    ]))
    out.append(("Home & Outpost", [
        ("A house", "Buy the house for sale in Brackenford or another town: free bed, storage chest, workbench, "
                    "desk and a training dummy."),
        ("An outpost", "Found your own outpost at Widow's Crossing. Build farms, workshops and walls, assign "
                       "companions, research upgrades and defend it from raids."),
    ]))
    places = [("", "Places you've been. Visit more to fill this chapter.")]
    for lid in sorted(st.discovered, key=lambda i: data.location(i)["name"]):
        places.append((data.location(lid)["name"], knowledge.place_summary(st, lid)))
    out.append(("Places You Know", places))
    obj = []
    for j in st.jobs:
        if j["status"] == "active":
            obj.append((j["title"], knowledge.job_next_step(st, j)))
    from ...set_system import favors
    for fid, f in st.favors.items():
        if f["status"] == "active":
            d = favors.defs(data)[fid]
            done, detail = favors.progress(st, fid)
            obj.append((d["title"], f"For {data.npcs[f['npc']]['name']}: {detail}" + (" - ready to hand in!" if done else "")))
    if not obj:
        obj = [("", "No active jobs or favors. Read a town's job board, or ask people if they need help.")]
    out.append(("Current Objectives", obj))
    from . import hints
    seen = [(h[0].title(), h[2]) for h in hints.HINTS if st.flags.get(f"tip:{h[0]}")]
    out.append(("Tips You've Seen", seen or [("", "Tips appear as you play.")]))
    out.append(("Controls", [(k, d) for k, d in CONTROLS] + [("G", "Hostile intent (attack anyone)"),
                                                              ("H", "This guide"), ("Tab", "Quick menu"),
                                                              ("F11", "Full screen")]))
    return out


class GuideScene(Scene):
    overlay = True

    def __init__(self, game, chapter=0):
        super().__init__(game)
        self.ch = chapter
        self.scroll = 0
        self.data_cache = chapters(self)

    def handle(self, ev):
        if is_close(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_h):
            self.close()
            return
        n = len(self.data_cache)
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_UP, pygame.K_w):
                self.ch, self.scroll = (self.ch - 1) % n, 0
            elif ev.key in (pygame.K_DOWN, pygame.K_s, pygame.K_TAB):
                self.ch, self.scroll = (self.ch + 1) % n, 0
            elif ev.key in (pygame.K_PAGEDOWN, pygame.K_RIGHT, pygame.K_d):
                self.scroll += 6
            elif ev.key in (pygame.K_PAGEUP, pygame.K_LEFT, pygame.K_a):
                self.scroll = max(0, self.scroll - 6)
        elif ev.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - ev.y * 3)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            x, y = ev.pos
            if 96 <= x <= 400 and 120 <= y < 120 + n * 34:
                self.ch, self.scroll = (y - 120) // 34, 0

    def draw(self, screen):
        ui.dim(screen, 160)
        r = ui.panel(screen, (40, 30, W - 80, H - 60), "Adventurer's Guide")
        left = ui.parchment(screen, (r.x + 30, r.y + 56, 350, r.h - 100))
        right = ui.parchment(screen, (left.right + 16, r.y + 56, r.right - left.right - 46, r.h - 100))
        pygame.draw.line(screen, (90, 66, 40), (left.right + 8, left.y + 4), (left.right + 8, left.bottom - 4), 3)
        ui.ink(screen, "Contents", (left.x + 20, left.y + 12), 26, ui.INK_RED, bold=True)
        for i, (title, _) in enumerate(self.data_cache):
            y = left.y + 50 + i * 34
            if i == self.ch:
                band = pygame.Rect(left.x + 10, y - 4, left.w - 20, 30)
                pygame.draw.rect(screen, ui.PARCH_DARK, band, border_radius=4)
                pygame.draw.rect(screen, (120, 80, 40), band, 1, border_radius=4)
            ui.ink(screen, f"{i + 1:>2}. {title}", (left.x + 20, y), 22, ui.INK if i == self.ch else ui.INK_DIM, bold=i == self.ch)
        title, entries = self.data_cache[self.ch]
        ui.ink(screen, title, (right.x + 24, right.y + 12), 30, ui.INK, bold=True)
        pygame.draw.line(screen, (150, 110, 70), (right.x + 20, right.y + 46), (right.right - 20, right.y + 46))
        # lay out entries as wrapped lines, then scroll
        lines = []
        for head, body in entries:
            if head:
                lines.append((head, True))
            for ln in ui.wrap(body, 21, right.w - 70):
                lines.append((ln, False))
            lines.append(("", False))
        per_page = (right.h - 80) // 22
        self.scroll = min(self.scroll, max(0, len(lines) - per_page))
        y = right.y + 56
        for text, is_head in lines[self.scroll:self.scroll + per_page]:
            if is_head:
                ui.ink(screen, text, (right.x + 24, y), 22, ui.INK_RED, bold=True)
            else:
                ui.ink(screen, text, (right.x + 40, y), 21, ui.INK)
            y += 22
        if len(lines) > per_page:
            ui.ink(screen, f"more below - scroll ({self.scroll + 1}-{min(len(lines), self.scroll + per_page)} of {len(lines)})",
                   (right.right - 20, right.bottom - 26), 18, ui.INK_DIM, right=True)
        ui.text(screen, "[Up/Down] chapter   [Left/Right / wheel] scroll   [H / Esc] close", (r.centerx, r.bottom - 32),
                21, ui.TEXT_DIM, center=True)
