"""Buying and selling with a merchant."""
import pygame

from ...core.scene import Scene
from ...set_system import economy
from .. import knowledge
from ..ui import widgets as ui
from .common import is_close

W, H = 1280, 720


class ShopScene(Scene):
    overlay = True

    def __init__(self, game, loc_id, shop_type, keeper):
        super().__init__(game)
        self.loc_id, self.shop_type, self.keeper = loc_id, shop_type, keeper
        self.sdef = self.data.shops[shop_type]
        self.buy_menu = ui.ListMenu([], (70, 150, 520, 400), 23)
        self.sell_menu = ui.ListMenu([], (690, 150, 520, 400), 23)
        self.focus = 0
        self.refresh()

    def refresh(self):
        st = self.state
        s = economy.shop_state(st, self.loc_id, self.shop_type)
        buy = []
        for item, qty in s["stock"].items():
            if qty <= 0:
                continue
            price = economy.buy_price(st, self.loc_id, self.shop_type, item)
            short = price - st.gold
            buy.append((f"{self.data.item(item)['name']}  x{qty}", item, True,
                        f"{price}m" if short <= 0 else f"{price}m (need {short} more)"))
        sell, nope = [], []
        for item, qty in st.player.inventory.items.items():
            name = f"{self.data.item(item)['name']}  x{qty}"
            if economy.will_buy(st, self.shop_type, item):
                price = economy.sell_price(st, self.loc_id, self.shop_type, item)
                if price <= 0:
                    nope.append((name, item, True, "worthless"))
                    continue
                worn = item in st.player.equipment.values()
                sell.append((name + ("  (worn)" if worn else ""), item, True,
                             f"{price}m" if price <= s["cash"] else f"{price}m (they can't afford)"))
            else:
                nope.append((name, item, True, "won't buy"))
        self.buy_menu.set_entries(buy)
        self.sell_menu.set_entries(sell + nope)
        self.unsellable = {e[1] for e in nope}

    def handle(self, ev):
        if is_close(ev):
            self.close()
            return
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_TAB, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
            self.focus = 1 - self.focus
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.focus = 0 if ev.pos[0] < W // 2 else 1
        menu = self.buy_menu if self.focus == 0 else self.sell_menu
        v = menu.handle(ev)
        if v and self.focus == 1 and v in getattr(self, "unsellable", ()):
            it = self.data.item(v)
            buyers = [b for b in knowledge.uses(self.state, v) if b.startswith("Sell to")]
            self.game.notify(f"{self.sdef['name']} doesn't buy {it['type']} goods like {it['name']}."
                             + (f" {buyers[0]}." if buyers else ""))
            return
        if v:
            qty = 5 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
            fn = economy.buy if self.focus == 0 else economy.sell
            have = (economy.shop_state(self.state, self.loc_id, self.shop_type)["stock"].get(v, 0) if self.focus == 0
                    else self.state.player.inventory.count(v))
            ok, msg = fn(self.state, self.loc_id, self.shop_type, v, max(1, min(qty, have)))
            if ok:
                from .. import audio
                audio.play("coin")
            self.game.notify(msg)
            self.refresh()

    def draw(self, screen):
        st = self.state
        s = economy.shop_state(st, self.loc_id, self.shop_type)
        ui.dim(screen, 150)
        who = self.keeper["name"] if self.keeper else "Shopkeeper"
        r = ui.panel(screen, (40, 40, W - 80, H - 80), f"{self.sdef['name']} - {who}")
        for i, (label, sub, x) in enumerate((("Buy", "you pay", 70), ("Sell", "they pay you", 690))):
            col = ui.ACCENT if self.focus == i else ui.TEXT_DIM
            w = ui.text(screen, label, (x, 100), 30, col, bold=True)
            ui.text(screen, sub, (x + w + 12, 108), 20, ui.TEXT_DIM)
        ui.text(screen, "Buys: " + ", ".join(self.sdef.get("buys", [])), (1210, 108), 19, ui.TEXT_DIM, right=True)
        pygame.draw.line(screen, ui.BORDER, (W // 2, 120), (W // 2, 560))
        self.buy_menu.draw(screen)
        self.sell_menu.draw(screen)
        if not self.buy_menu.entries:
            ui.text(screen, "Sold out until the weekly restock.", (70, 176), 22, ui.TEXT_DIM)
        if not self.sell_menu.entries:
            ui.text(screen, "Your pack is empty.", (690, 176), 22, ui.TEXT_DIM)
        menu = self.buy_menu if self.focus == 0 else self.sell_menu
        sel = menu.selected()
        box = pygame.Rect(70, 568, W - 140, 64)
        ui.parchment(screen, box)
        if sel:
            it = self.data.item(sel)
            ui.ink(screen, it["name"], (box.x + 12, box.y + 6), 24, ui.INK, bold=True)
            have = st.player.inventory.count(sel)
            ui.ink(screen, f"You have {have}   |   base value {it['value']}m", (box.right - 12, box.y + 9), 19, ui.INK_DIM,
                   right=True)
            if getattr(self, "_use_key", None) != sel:
                self._use_key, self._use = sel, knowledge.uses(st, sel)
            use = self._use
            ui.ink_block(screen, it.get("desc", "") + ("  " + use[0] + "." if use else ""), (box.x + 12, box.y + 32,
                                                                                         box.w - 24, 30), 18, ui.INK_DIM)
        ui.text(screen, f"Your marks: {st.gold}", (70, 646), 24, ui.ACCENT)
        ui.text(screen, f"Merchant's marks: {s['cash']}", (W - 70, 646), 24, ui.TEXT, right=True)
        ui.text(screen, "[Tab] switch   [Enter] trade 1   [Shift+Enter] trade 5   [Esc] leave",
                (W // 2, 650), 21, ui.TEXT_DIM, center=True)
