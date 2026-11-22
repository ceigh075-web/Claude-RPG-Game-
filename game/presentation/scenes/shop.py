"""Buying and selling with a merchant."""
import pygame

from ...core.scene import Scene
from ...set_system import economy
from ..ui import widgets as ui
from .common import is_close

W, H = 1280, 720


class ShopScene(Scene):
    overlay = True

    def __init__(self, game, loc_id, shop_type, keeper):
        super().__init__(game)
        self.loc_id, self.shop_type, self.keeper = loc_id, shop_type, keeper
        self.sdef = self.data.shops[shop_type]
        self.buy_menu = ui.ListMenu([], (70, 170, 520, 430), 23)
        self.sell_menu = ui.ListMenu([], (690, 170, 520, 430), 23)
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
            buy.append((f"{self.data.item(item)['name']} (x{qty})", item, st.gold >= price, f"{price}m"))
        sell = []
        for item, qty in st.player.inventory.items.items():
            if economy.will_buy(st, self.shop_type, item):
                price = economy.sell_price(st, self.loc_id, self.shop_type, item)
                if price <= 0:
                    continue
                sell.append((f"{self.data.item(item)['name']} (x{qty})", item, True, f"{price}m"))
        self.buy_menu.set_entries(buy)
        self.sell_menu.set_entries(sell)

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
        for i, (label, x) in enumerate((("Buy", 70), ("Sell", 690))):
            col = ui.ACCENT if self.focus == i else ui.TEXT_DIM
            ui.text(screen, label, (x, 124), 30, col, bold=True)
        pygame.draw.line(screen, ui.BORDER, (W // 2, 120), (W // 2, 610))
        self.buy_menu.draw(screen)
        self.sell_menu.draw(screen)
        if not self.sell_menu.entries:
            ui.text(screen, "Nothing they'd buy from you.", (690, 176), 22, ui.TEXT_DIM)
        menu = self.buy_menu if self.focus == 0 else self.sell_menu
        sel = menu.selected()
        if sel:
            ui.text(screen, self.data.item(sel).get("desc", ""), (70, 620), 21, ui.TEXT_DIM)
        ui.text(screen, f"Your marks: {st.gold}", (70, 650), 24, ui.ACCENT)
        ui.text(screen, f"Merchant's marks: {s['cash']}", (W - 70, 650), 24, ui.TEXT, right=True)
        ui.text(screen, "[Tab] switch   [Enter] trade 1   [Shift+Enter] trade 5   [Esc] leave",
                (W // 2, 650), 21, ui.TEXT_DIM, center=True)
