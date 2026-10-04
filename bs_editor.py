"""Grown-up pages for objects.

  objects  category folders; tap one to see its objects (and add, rename or delete categories)
  edit     draw an object, name it, record its name and sound, pick its animation and
           category, or switch it off
  pick     choose (or create) the category for the object being edited

The "Game parts" folder holds the pieces of the game itself (hello, the peekaboo bush,
bedtime moon, tap sound...); their edit page shows only what can be changed for each.
"""
import os

import pygame

import bs_objects as objs
from bs_audio import MAX_RECORD_SECONDS, MicRecorder, clean_recording, counting_chimes, save_wav
from bs_game import motion_offsets
from bs_log import log_error
from bs_paths import ANDROID

CANVAS = 512  # drawings are stored as 512x512 PNGs with a transparent background
PALETTE = [(30, 30, 35), (255, 255, 255), (229, 57, 53), (251, 140, 0), (253, 216, 53), (67, 160, 71),
           (30, 136, 229), (142, 36, 170), (236, 64, 122), (121, 85, 72), (158, 158, 158), (255, 204, 170)]
ERASER = (0, 0, 0, 0)  # drawing with "transparent" rubs out
BRUSHES = [4, 9, 16, 28]  # brush radius in canvas pixels
COLS, ROWS = 9, 4  # tile grid
MAX_UNDO = 25
MAX_NAME = 20

BG, PANEL, TEXT, DIM = (14, 14, 22), (38, 40, 58), (215, 215, 228), (135, 135, 155)
ACCENT, GOOD, BAD, CANVAS_BG = (88, 108, 200), (70, 160, 100), (200, 70, 70), (52, 54, 74)
FOLDER, NEW = (46, 52, 78), (60, 50, 85)
NO_RECORDING = (95, 97, 115)  # grey dot: nothing recorded yet


class ObjectPages:
    def __init__(self, menu):
        self.m = menu
        self.folder = None  # the category being browsed (None = all the folders)
        self.grid_page = 0
        self.thumbs = {}  # (id, height) -> (drawing mtime, surface)
        self.item = None
        self.canvas = None
        self.canvas_rect = pygame.Rect(0, 0, 1, 1)
        self.undo = []
        self.dirty = False
        self.stroke_last = None
        self.color = PALETTE[0]
        self.brush = 1
        self.typing = None  # {"target": "name"/"new_category"/"rename_category", "value": str, "fresh": bool}
        self.recording = None  # "voice" / "sfx" while recording
        self.message = ""
        self.confirm_delete = False

    # ------------------------------------------------------------- helpers
    def thumb(self, item, height):
        path = objs.drawing_path(item.id)
        mtime = os.path.getmtime(path) if os.path.exists(path) else 0
        cached = self.thumbs.get((item.id, height))
        if not cached or cached[0] != mtime:
            art = objs.object_art(item, height)
            if art.get_width() > height * 1.3:  # wide pictures (the bush) still fit their tile
                k = height * 1.3 / art.get_width()
                art = pygame.transform.smoothscale(art, (int(art.get_width() * k), max(1, int(art.get_height() * k))))
            cached = (mtime, art)
            self.thumbs[(item.id, height)] = cached
        return cached[1]

    def _say(self, message):
        self.message = message
        self.confirm_delete = False

    def _tiles(self, tiles, draw_tile):
        """Lay out tiles in pages of COLS x ROWS; draw_tile(thing, rect) draws one and returns its action."""
        m, w, h = self.m, self.m.w, self.m.h
        per_page = COLS * ROWS
        pages = (len(tiles) - 1) // per_page + 1
        self.grid_page = min(self.grid_page, pages - 1)
        tw, th = w * 0.9 / COLS, h * 0.17
        for n, thing in enumerate(tiles[self.grid_page * per_page:(self.grid_page + 1) * per_page]):
            x, y = w * 0.05 + (n % COLS) * tw, h * 0.19 + (n // COLS) * (th + h * 0.01)
            rect = pygame.Rect(x + 4, y, tw - 8, th)
            m.buttons.append(_Button(rect, draw_tile(thing, rect)))
        if pages > 1:
            m._text(f"Page {self.grid_page + 1} of {pages}", "small", DIM, center=(w / 2, h * 0.93))
            pw, ph = m._fit("Previous page", "small")
            m._button((w / 2 - pw - w * 0.09, h * 0.905, pw, ph), "Previous page",
                      lambda: self._flip(-1, pages), PANEL, "small")
            m._button((w / 2 + w * 0.09, h * 0.905, pw, ph), "Next page", lambda: self._flip(1, pages), PANEL, "small")

    def _flip(self, step, pages):
        self.grid_page = (self.grid_page + step) % pages

    def _new_tile(self, rect, label):
        pygame.draw.rect(self.m.screen, NEW, rect, border_radius=14)
        self.m._text("+", "big", TEXT, center=(rect.centerx, rect.centery - rect.h * 0.12))
        self.m._text(label, "small", TEXT, center=(rect.centerx, rect.bottom - rect.h * 0.15))

    # ---------------------------------------------------------- typing text
    def _start_typing(self, target, value, fresh=False):
        self.typing = {"target": target, "value": value, "fresh": fresh}

    def _text_box(self, rect, target, placeholder, font="normal"):
        """A text field; tap to type in it."""
        m = self.m
        rect = pygame.Rect(rect)
        active = self.typing and self.typing["target"] == target
        pygame.draw.rect(m.screen, PANEL, rect, border_radius=10)
        if active:
            pygame.draw.rect(m.screen, ACCENT, rect, 3, border_radius=10)
            value = "" if self.typing["fresh"] else self.typing["value"]
            caret = "|" if int(pygame.time.get_ticks() / 500) % 2 == 0 else ""
            m._text(value + caret, font, TEXT, midleft=(rect.x + m.w * 0.012, rect.centery))
        else:
            m._text(placeholder, font, TEXT, midleft=(rect.x + m.w * 0.012, rect.centery))
        return rect

    def key(self, e):
        if self.typing:
            t = self.typing
            if e.key == pygame.K_BACKSPACE:
                t["value"] = "" if t["fresh"] else t["value"][:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                self._finish_typing()
                return
            elif e.key == pygame.K_ESCAPE:
                self.typing = None
                return
            elif e.unicode and not ANDROID:  # (Android's keyboard sends TEXTINPUT instead: type_text)
                self.type_text(e.unicode)
                return
            else:
                return
            t["fresh"] = False
            if t["target"] == "name":
                self.item = self.item._replace(word=t["value"])
        elif self.m.page == "edit" and e.key == pygame.K_z and e.mod & pygame.KMOD_CTRL:
            self._undo()
        elif e.key == pygame.K_ESCAPE:
            {"edit": self.close_edit, "pick": self._close_picker}.get(self.m.page, self._back)()

    def type_text(self, text):
        t = self.typing
        text = "".join(c for c in text if c.isprintable())
        if not t or not text:
            return
        t["value"] = (text if t["fresh"] else t["value"] + text)[:MAX_NAME]
        t["fresh"] = False
        if t["target"] == "name":
            self.item = self.item._replace(word=t["value"])

    def _finish_typing(self):
        """Save what was typed."""
        if not self.typing:
            return
        target, value = self.typing["target"], self.typing["value"].strip()
        fresh = self.typing["fresh"]
        self.typing = None
        if target == "name" and self.item and self.item.custom:
            word = value if value and not fresh else (self.item.word.strip() or "New thing")
            objs.set_word(self.item.id, word)
            self._refresh()
        elif target == "new_category" and value and not fresh:
            name = objs.add_category(value)
            objs.set_category(self.item.id, name)
            self._refresh()
            self._close_picker()
        elif target == "rename_category" and value and not fresh:
            self.folder = objs.rename_category(self.folder, value)

    # ------------------------------------------------------ folders + grid
    def open_list(self):
        self.m.page = "objects"
        self.message = ""
        self.typing = None

    def _back(self):
        self._finish_typing()
        if self.folder is None:
            self.m.page = "menu"
        else:
            self.folder, self.grid_page = None, 0

    def _open_folder(self, name):
        self.folder, self.grid_page = name, 0

    def _new_category(self):
        self._open_folder(objs.add_category("New category"))
        self._start_typing("rename_category", self.folder, fresh=True)

    def _delete_category(self):
        objs.delete_category(self.folder)
        self.folder, self.grid_page = None, 0

    def draw_list(self):
        m, w, h = self.m, self.m.w, self.m.h
        items = objs.load_items(enabled_only=False, include_parts=True)
        label = "Done" if self.folder is None else "Back"
        dw, dh = m._fit(label)
        m._button((w * 0.97 - dw, h * 0.04, dw, dh), label, self._back, ACCENT)
        if self.folder is None:
            self._draw_folders(items)
        else:
            self._draw_folder(items)

    def _draw_folders(self, items):
        m, w, h = self.m, self.m.w, self.m.h
        m._text("Objects", "big", TEXT, center=(w / 2, h * 0.07))
        m._text("Tap a category to see its objects.", "small", DIM, center=(w / 2, h * 0.13))

        def tile(name, rect):
            if name is None:
                self._new_tile(rect, "New category")
                return self._new_category
            inside = [it for it in items if it.category == name]
            on = sum(objs.is_enabled(it.id) for it in inside)
            pygame.draw.rect(m.screen, FOLDER, rect, border_radius=14)
            pygame.draw.rect(m.screen, FOLDER, (rect.x, rect.y - rect.h * 0.06, rect.w * 0.45, rect.h * 0.2),
                             border_radius=10)  # folder tab
            for k, it in enumerate(inside[:3]):  # a peek at what's inside
                pic = self.thumb(it, int(rect.h * 0.34))
                m.screen.blit(pic, pic.get_rect(center=(rect.x + rect.w * (0.28 + 0.22 * k), rect.y + rect.h * 0.4)))
            m._text(name[:16], "small", TEXT, center=(rect.centerx, rect.bottom - rect.h * 0.25))
            m._text(f"{on} of {len(inside)} on" if inside else "empty", "small", DIM,
                    center=(rect.centerx, rect.bottom - rect.h * 0.1))
            return lambda n=name: self._open_folder(n)

        self._tiles([None] + objs.categories(include_parts=True), tile)

    def _draw_folder(self, items):
        m, w, h = self.m, self.m.w, self.m.h
        inside = [it for it in items if it.category == self.folder]
        if objs.is_custom_category(self.folder):  # your categories can be renamed (and deleted when empty)
            box = pygame.Rect(w / 2 - w * 0.18, h * 0.035, w * 0.36, h * 0.075)
            self._text_box(box, "rename_category", self.folder, "big")
            m.buttons.append(_Button(box, lambda: self._start_typing("rename_category", self.folder)))
            hint = ("Type a name, then press Enter" if self.typing else "Tap the name to rename it")
            if not inside:
                bw, bh = m._fit("Delete category", "small")
                m._button((w * 0.03, h * 0.04, bw, bh), "Delete category", self._delete_category, PANEL, "small")
        elif self.folder == objs.GAME_PARTS:
            m._text(self.folder, "big", TEXT, center=(w / 2, h * 0.07))
            hint = "The pieces of the game itself. Tap one to change its picture, voice, sound or animation."
        else:
            m._text(self.folder, "big", TEXT, center=(w / 2, h * 0.07))
            hint = "Tap one to draw it, record its sounds or change how it moves.  Faded ones are switched off."
        m._text(hint, "small", DIM, center=(w / 2, h * 0.14))

        def tile(item, rect):
            if item is None:
                self._new_tile(rect, "New object")
                return self._new_object
            on = objs.is_enabled(item.id)
            pygame.draw.rect(m.screen, PANEL if on else (24, 25, 36), rect, border_radius=14)
            pic = self.thumb(item, int(rect.h * 0.55))
            if not on:
                pic = pic.copy()
                pic.set_alpha(70)
            m.screen.blit(pic, pic.get_rect(center=(rect.centerx, rect.y + rect.h * 0.4)))
            m._text(item.word[:14], "small", TEXT if on else DIM, center=(rect.centerx, rect.bottom - rect.h * 0.13))
            self._recording_dot(item, (rect.right - rect.h * 0.11, rect.y + rect.h * 0.11), rect.h * 0.045)
            return lambda i=item.id: self.open_edit(i)

        self._tiles(inside if self.folder == objs.GAME_PARTS else [None] + inside, tile)
        # legend for the dots
        x, y, r = w * 0.03, h * 0.955, h * 0.012
        for color, text in ((GOOD, "your own recording"), (NO_RECORDING, "not recorded yet")):
            pygame.draw.circle(m.screen, color, (x + r, y), r)
            x = m._text(text, "small", DIM, midleft=(x + r * 3, y)).right + w * 0.02

    def _recording_dot(self, item, center, radius):
        """Green if you've recorded its name or its sound yourself, grey if not."""
        recorded = any(os.path.exists(p) for p in (objs.our_voice_path(item.id), objs.our_sfx_path(item.id)))
        pygame.draw.circle(self.m.screen, GOOD if recorded else NO_RECORDING, center, radius)

    def _new_object(self):
        self._finish_typing()
        self.open_edit(objs.add_custom(self.folder or objs.OUR_OWN))
        self._start_typing("name", "New thing", fresh=True)

    # ------------------------------------------------------------ the editor
    def open_edit(self, item_id):
        self._finish_typing()
        self.item = objs.get_item(item_id)
        self.canvas = pygame.Surface((CANVAS, CANVAS), pygame.SRCALPHA)
        path = objs.drawing_path(item_id)
        if os.path.exists(path):
            saved = pygame.image.load(path).convert_alpha()
            if saved.get_size() != (CANVAS, CANVAS):
                saved = pygame.transform.smoothscale(saved, (CANVAS, CANVAS))
            self.canvas.blit(saved, (0, 0))
        self.undo, self.dirty, self.stroke_last = [], False, None
        self.message, self.confirm_delete = "", False
        self.m.page = "edit"

    def close_edit(self):
        self._stop_recording(save=False)
        self._finish_typing()
        if self.dirty:
            path = objs.drawing_path(self.item.id)
            if self.canvas.get_bounding_rect().w == 0:  # nothing drawn: use the emoji again
                if os.path.exists(path):
                    os.remove(path)
            else:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                pygame.image.save(self.canvas, path)
        self.dirty = False
        if self.item and objs.get_item(self.item.id):
            self.folder = self.item.category  # back to the category it's in (it may have moved)
        self.open_list()

    def _refresh(self):
        self.item = objs.get_item(self.item.id)

    # -------------------------------------------------------------- drawing
    def mouse(self, e):
        """Drawing: press, drag and release on the canvas (a finger works too)."""
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.canvas_rect.collidepoint(e.pos):
            self._finish_typing()
            self.undo = (self.undo + [self.canvas.copy()])[-MAX_UNDO:]
            self.stroke_last = self._to_canvas(e.pos)
            self._paint(self.stroke_last, self.stroke_last)
        elif e.type == pygame.MOUSEMOTION and self.stroke_last is not None:
            p = self._to_canvas(e.pos)
            self._paint(self.stroke_last, p)
            self.stroke_last = p
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.stroke_last = None

    def _to_canvas(self, pos):
        r = self.canvas_rect
        return ((pos[0] - r.x) * CANVAS / r.w, (pos[1] - r.y) * CANVAS / r.h)

    def _paint(self, a, b):
        radius = BRUSHES[self.brush]
        pygame.draw.line(self.canvas, self.color, a, b, radius * 2)
        pygame.draw.circle(self.canvas, self.color, a, radius)
        pygame.draw.circle(self.canvas, self.color, b, radius)
        self.dirty = True
        self.confirm_delete = False

    def tick(self):
        if self.recording and self.m.recorder.seconds() >= MAX_RECORD_SECONDS:
            self._stop_recording()

    def _pick_color(self, color):
        self.color = color

    def _pick_brush(self, i):
        self.brush = i

    def _undo(self):
        if self.undo:
            self.canvas = self.undo.pop()
            self.dirty = True

    def _clear(self):
        self.undo = (self.undo + [self.canvas.copy()])[-MAX_UNDO:]
        self.canvas.fill((0, 0, 0, 0))
        self.dirty = True

    def _use_original(self):
        path = objs.drawing_path(self.item.id)
        if os.path.exists(path):
            os.remove(path)
        self.canvas.fill((0, 0, 0, 0))
        self.undo, self.dirty = [], False
        self._say("Back to the original picture.")

    # ------------------------------------------------------------ recording
    def _paths(self, what):
        """(your recording, the built-in one) for "voice" or "sfx"."""
        if what == "voice":
            return objs.our_voice_path(self.item.id), objs.builtin_voice_path(self.item.id)
        return objs.our_sfx_path(self.item.id), objs.builtin_sfx_path(self.item.id)

    def _toggle(self, what):
        if self.recording == what:
            self._stop_recording()
            return
        self._stop_recording(save=False)
        if not MicRecorder.available():
            self._say("No microphone found.")
            return
        self.m.channel.stop()
        try:
            self.m.recorder.start()
        except Exception:
            log_error("opening the microphone")
            self._say("Couldn't open the microphone - is another app using it?")
            return
        self.recording = what
        self._say("Recording... tap Stop when you're done.")

    def _stop_recording(self, save=True):
        if not self.recording:
            return
        what, self.recording = self.recording, None
        samples = self.m.recorder.stop()
        if not save:
            self.message = ""
            return
        cleaned = clean_recording(samples)
        if cleaned is None:
            self._say("Didn't hear anything - try again a little louder or closer.")
            return
        save_wav(self._paths(what)[0], cleaned)
        self._say("Saved!")
        self._listen(what)

    def _listen(self, what):
        if self.recording:
            return
        path = next((p for p in self._paths(what) if os.path.exists(p)), None)
        if path:
            self.m.channel.play(pygame.mixer.Sound(path))
        elif what == "sfx" and self.item.id in ("tap", "mystery"):  # their built-in chime
            self.m.channel.play(counting_chimes(1))
        elif what == "sfx" and self._counts():
            self.m.channel.play(counting_chimes(int(self.item.glyph)))
        else:
            self._say("Nothing recorded yet.")

    def _delete_recording(self, what):
        ours = self._paths(what)[0]
        if not self.recording and os.path.exists(ours):
            os.remove(ours)
            self._say("Deleted.")

    def _status(self, what):
        ours, builtin = self._paths(what)
        if os.path.exists(ours):
            return "Your recording", GOOD
        if os.path.exists(builtin):
            return ("Built-in voice" if what == "voice" else "Built-in sound"), DIM
        if what == "sfx" and self._counts():
            return f"Counting chimes ({self.item.glyph} dings)", DIM
        if what == "sfx" and self.item.part:
            return {"tap": "Built in: soft chimes", "mystery": "Built in: a chime"}.get(
                self.item.id, "None yet - record one if you like"), DIM
        return (("Not recorded yet - record it!" if what == "voice"
                 else "None yet - it gets a little chime instead"), DIM)

    def _counts(self):
        return bool(self.item.glyph and self.item.glyph.isdigit())

    # ------------------------------------------------------- object settings
    def _set_move(self, move):
        objs.set_move(self.item.id, move)
        self._refresh()

    def _set_enabled(self, on):
        objs.set_enabled(self.item.id, on)

    def _delete_object(self):
        if not self.confirm_delete:
            self.confirm_delete = True
            self.message = "Tap Delete again to delete this object for good."
            return
        self._stop_recording(save=False)
        folder = self.item.category
        objs.delete_custom(self.item.id)
        self.dirty = False
        self.item = None
        self.folder = folder
        self.open_list()

    # ------------------------------------------------------- category picker
    def _open_picker(self):
        self._finish_typing()
        self._stop_recording(save=False)
        self.m.page = "pick"

    def _close_picker(self):
        self.typing = None
        self.m.page = "edit"

    def _pick_category(self, name):
        objs.set_category(self.item.id, name)
        self._refresh()
        self._close_picker()

    def draw_picker(self):
        m, w, h = self.m, self.m.w, self.m.h
        m._text(f"Which category is {self.item.word} in?", "big", TEXT, center=(w / 2, h * 0.1))
        dw, dh = m._fit("Back")
        m._button((w * 0.97 - dw, h * 0.04, dw, dh), "Back", self._close_picker, ACCENT)
        x, y = w * 0.1, h * 0.24
        for name in objs.categories():
            bw, bh = m._fit(name)
            if x + bw > w * 0.9:
                x, y = w * 0.1, y + bh + h * 0.02
            m._button((x, y, bw, bh), name, lambda n=name: self._pick_category(n),
                      ACCENT if name == self.item.category else PANEL)
            x += bw + w * 0.015
        y += h * 0.14
        m._text("Or make a new category:", "normal", TEXT, midleft=(w * 0.1, y))
        box = pygame.Rect(w * 0.1, y + h * 0.04, w * 0.4, h * 0.075)
        self._text_box(box, "new_category", "Tap here and type its name")
        m.buttons.append(_Button(box, lambda: self._start_typing("new_category", "")))
        if self.typing:
            m._text("then press Enter", "small", DIM, midleft=(box.right + w * 0.015, box.centery))

    # ----------------------------------------------------------------- draw
    def draw_edit(self, now):
        m, w, h = self.m, self.m.w, self.m.h
        item = self.item
        dw, dh = m._fit("Done")
        m._button((w * 0.97 - dw, h * 0.9, dw, dh), "Done", self.close_edit, ACCENT)

        # canvas + tools on the left (or, for sound-only game parts, what the part does)
        s = int(h * 0.6)
        if not objs.has(item, "p"):
            self.canvas_rect = pygame.Rect(0, 0, 0, 0)
            r = pygame.Rect(int(w * 0.04), int(h * 0.1), s, s)
            pygame.draw.rect(m.screen, CANVAS_BG, r, border_radius=12)
            icon = self.thumb(item, int(s * 0.35))
            m.screen.blit(icon, icon.get_rect(center=(r.centerx, r.y + s * 0.35)))
            m._text("No picture - this part is a sound", "normal", DIM, center=(r.centerx, r.y + s * 0.72))
            if self.message:
                m._text(self.message, "small", BAD if self.recording else TEXT, midleft=(r.x, r.bottom + h * 0.05))
        else:
            self._draw_canvas(item, s)
        self._draw_details(item, now)

    def _draw_canvas(self, item, s):
        m, w, h = self.m, self.m.w, self.m.h
        self.canvas_rect = pygame.Rect(int(w * 0.04), int(h * 0.1), s, s)
        r = self.canvas_rect
        pygame.draw.rect(m.screen, CANVAS_BG, r, border_radius=12)
        if self.canvas.get_bounding_rect().w == 0:
            if not item.custom and not os.path.exists(objs.drawing_path(item.id)):  # trace the original
                ghost = self.thumb(item, int(s * 0.5)).copy()
                ghost.set_alpha(35)
                m.screen.blit(ghost, ghost.get_rect(center=r.center))
            m._text(f"Draw your {item.word.lower()} here", "normal", DIM, center=(r.centerx, r.bottom - s * 0.07))
        m.screen.blit(pygame.transform.smoothscale(self.canvas, r.size), r)
        instead = ("" if item.custom else "  (instead of the built-in one)" if item.part or item.glyph
                   else f"  (instead of the {item.word.lower()} emoji)")
        m._text("Drawing" + instead, "small", DIM, midbottom=(r.centerx, r.y - h * 0.01))

        step = s / (len(PALETTE) + 1)
        y = r.bottom + h * 0.045
        for i, color in enumerate(PALETTE + [ERASER]):
            cx = r.x + step * (i + 0.5)
            rad = step * 0.36
            if self.color == color:
                pygame.draw.circle(m.screen, TEXT, (cx, y), rad + 5, 3)
            if color == ERASER:
                pygame.draw.circle(m.screen, CANVAS_BG, (cx, y), rad)
                pygame.draw.circle(m.screen, DIM, (cx, y), rad, 2)
                m._text("x", "small", TEXT, center=(cx, y))
            else:
                pygame.draw.circle(m.screen, color, (cx, y), rad)
            m.buttons.append(_Button((cx - step / 2, y - step / 2, step, step), lambda c=color: self._pick_color(c)))
        y2 = y + h * 0.075
        x = r.x
        for i, radius in enumerate(BRUSHES):
            box = pygame.Rect(x, y2 - h * 0.03, h * 0.06, h * 0.06)
            pygame.draw.rect(m.screen, ACCENT if i == self.brush else PANEL, box, border_radius=10)
            dot = self.color if self.color != ERASER else DIM
            pygame.draw.circle(m.screen, dot, box.center, max(2, radius * box.w / 80))
            m.buttons.append(_Button(box, lambda i=i: self._pick_brush(i)))
            x += box.w + w * 0.006
        x += w * 0.01
        tools = [("Undo", self._undo), ("Clear", self._clear)]
        if not item.custom and (os.path.exists(objs.drawing_path(item.id)) or self.dirty):
            tools.append(("Use original", self._use_original))
        for text, action in tools:
            bw, bh = m._fit(text, "small")
            m._button((x, y2 - bh / 2, bw, bh), text, action, PANEL, "small")
            x += bw + w * 0.006
        if self.message:
            m._text(self.message, "small", BAD if self.recording else TEXT, midleft=(r.x, y2 + h * 0.065))

    def _wrap(self, text, font, width):
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if self.m.fonts[font].size(trial)[0] > width and line:
                lines.append(line)
                line = word
            else:
                line = trial
        return lines + [line]

    def _draw_details(self, item, now):
        """The right-hand side: name, recordings, animation, on/off."""
        m, w, h = self.m, self.m.w, self.m.h
        x0 = w * 0.5
        if item.custom:
            m._text("Name", "small", DIM, midleft=(x0, h * 0.075))
            box = self._text_box((x0, h * 0.1, w * 0.27, h * 0.07), "name", item.word)
            m.buttons.append(_Button(box, lambda: self._start_typing("name", self.item.word)))
            if self.typing and self.typing["target"] == "name":
                m._text("then press Enter", "small", DIM, midleft=(box.right + w * 0.01, box.centery))
        elif item.part:  # a game part: its name and what it does
            m._text(item.word, "big", TEXT, midleft=(x0, h * 0.1))
            for i, line in enumerate(self._wrap(item.tip, "small", w * 0.46)[:2]):
                m._text(line, "small", DIM, midleft=(x0, h * (0.155 + 0.035 * i)))
        else:
            m._text(item.word, "big", TEXT, midleft=(x0, h * 0.1))
            key = f"  ·  the {item.key.upper()} key" if item.key else "  ·  comes up from taps and other keys"
            m._text("built-in" + key, "small", DIM, midleft=(x0, h * 0.155))
        if not item.part:
            m._text("Category", "small", DIM, midleft=(x0, h * 0.215))
            cw, ch = m._fit(item.category + "   (change)", "small")
            m._button((x0 + w * 0.06, h * 0.215 - ch / 2, cw, ch), item.category + "   (change)", self._open_picker,
                      FOLDER, "small")

        rows = [(("What it says" if item.part else "Its name, in your voice"), "voice"),
                (("Its sound" if item.part else "What it sounds like"), "sfx")]
        rows = [(label, what, y) for (label, what), y in
                zip([r for r in rows if objs.has(item, "v" if r[1] == "voice" else "s")], (h * 0.28, h * 0.395))]
        for label, what, y in rows:
            m._text(label, "normal", TEXT, midleft=(x0, y))
            bx = x0
            recording_this = self.recording == what
            for text, action, color in [("Stop" if recording_this else "Record", lambda wh=what: self._toggle(wh),
                                         BAD if recording_this else (150, 60, 70)),
                                        ("Listen", lambda wh=what: self._listen(wh), PANEL),
                                        ("Delete", lambda wh=what: self._delete_recording(wh), PANEL)]:
                bw, bh = m._fit(text, "small")
                m._button((bx, y + h * 0.028, bw, bh), text, action, color, "small")
                bx += bw + w * 0.008
            if recording_this:
                mw = w * 0.18
                pygame.draw.rect(m.screen, PANEL, (bx + w * 0.01, y + h * 0.048, mw, h * 0.018), border_radius=6)
                pygame.draw.rect(m.screen, GOOD, (bx + w * 0.01, y + h * 0.048,
                                                  mw * min(1.0, m.recorder.level * 3), h * 0.018), border_radius=6)
                left = max(0.0, MAX_RECORD_SECONDS - m.recorder.seconds())
                m._text(f"{left:.1f} s", "small", DIM, midleft=(bx + w * 0.2, y + h * 0.057))
            else:
                status, color = self._status(what)
                m._text(status, "small", color, midleft=(bx + w * 0.01, y + h * 0.057))

        if objs.has(item, "m"):
            self._draw_moves(item, now, x0)
        if item.part and not objs.has(item, "o"):
            return
        tx = x0 + h * 0.2 + w * 0.03 if objs.has(item, "m") else x0
        m._text("In the game", "normal", TEXT, midleft=(tx, h * 0.8))
        on = objs.is_enabled(item.id)
        bx = tx
        for text, value in (("On", True), ("Off", False)):
            bw, bh = m._fit(text, "small")
            m._button((bx, h * 0.83, bw, bh), text, lambda v=value: self._set_enabled(v),
                      ACCENT if on == value else PANEL, "small")
            bx += bw + w * 0.006
        if item.custom:
            text = "Tap again to delete" if self.confirm_delete else "Delete object"
            bw, bh = m._fit(text, "small")
            m._button((tx, h * 0.91, bw, bh), text, self._delete_object, BAD if self.confirm_delete else PANEL, "small")

    def _draw_moves(self, item, now, x0):
        """Animation buttons + a live preview."""
        m, w, h = self.m, self.m.w, self.m.h
        m._text("How it moves", "normal", TEXT, midleft=(x0, h * 0.515))
        bx, by = x0, h * 0.54
        for move, label in objs.MOVES:
            bw, bh = m._fit(label, "small")
            if bx + bw > w * 0.97:
                bx, by = x0, by + bh + h * 0.008
            m._button((bx, by, bw, bh), label, lambda mv=move: self._set_move(mv),
                      ACCENT if item.move == move else PANEL, "small")
            bx += bw + w * 0.006

        # live preview of the animation
        pv = pygame.Rect(x0, h * 0.775, h * 0.2, h * 0.2)
        pygame.draw.rect(m.screen, CANVAS_BG, pv, border_radius=12)
        art = self._preview_art(int(pv.h * 0.45))
        dx, dy, angle, sx, sy, flip = motion_offsets(item.move, now, pv.w * 0.9)
        if flip:
            art = pygame.transform.flip(art, True, False)
        art = pygame.transform.rotozoom(art, angle, 1)
        art = pygame.transform.smoothscale(art, (max(1, int(art.get_width() * sx)), max(1, int(art.get_height() * sy))))
        m.screen.set_clip(pv)
        m.screen.blit(art, art.get_rect(center=(pv.centerx + dx, pv.centery + pv.h * 0.08 + dy)))
        m.screen.set_clip(None)
        m._text("Preview", "small", DIM, topleft=(pv.x + h * 0.01, pv.y + h * 0.005))

    def _preview_art(self, height):
        """What the object looks like right now: the drawing in progress, or its normal picture."""
        box = self.canvas.get_bounding_rect()
        if box.w and box.h:
            art = self.canvas.subsurface(box)
            k = min(height / box.h, height * 1.25 / box.w)
            return pygame.transform.smoothscale(art, (max(1, int(box.w * k)), max(1, int(box.h * k))))
        return self.thumb(self.item, height)


class _Button:
    """A tappable area (drawn separately)."""

    def __init__(self, rect, action):
        self.rect, self.action = pygame.Rect(rect), action
