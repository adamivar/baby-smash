"""Start screen for grown-ups: settings, recording your own voice for every word,
and the Objects pages (bs_editor) for drawing, adding and editing objects."""
import json
import os
import time

import pygame

import bs_objects as objs
from bs_audio import MAX_RECORD_SECONDS, MicRecorder, clean_recording, save_wav
from bs_editor import ObjectPages
from bs_log import log_error
from bs_paths import ANDROID, DATA_DIR
from bs_system import sys_font

SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
# categories: [] = play with every category, else the chosen category names
DEFAULTS = {"theme": "night", "mode": "words", "voice": "ours", "minutes": 10, "tips": True, "categories": []}
CHOICES = {  # setting: [(button text, value)]
    "theme": [("Night", "night"), ("Day", "day")],
    "mode": [("Who's that? (silhouette)", "words"), ("Peekaboo", "peekaboo")],
    "voice": [("Our voices", "ours"), ("Built-in voices", "builtin")],
    "minutes": [("5 min", 5), ("10 min", 10), ("15 min", 15), ("20 min", 20), ("No limit", 0)],
    "tips": [("On", True), ("Off", False)],
}
ROWS = [("Look", "theme"), ("Game", "mode"), ("Play with", "categories"), ("Voice", "voice"),
        ("Play time", "minutes"), ("Grown-up tips", "tips")]

# the extra phrases: (emoji, what to say)
EXTRA_PROMPTS = {"hello": ("👋", '"Hello!"  (when the game starts)'),
                 "bye": ("👋", '"Bye!"  (played twice at bedtime)'),
                 "where": ("🙈", '"Where is it?"  (Peekaboo: something is hiding)'),
                 "peekaboo": ("🙉", '"Peekaboo!"  (Peekaboo: the reveal)')}

BG, PANEL, TEXT, DIM = (14, 14, 22), (38, 40, 58), (215, 215, 228), (135, 135, 155)
ACCENT, GOOD, BAD = (88, 108, 200), (70, 160, 100), (200, 70, 70)


def load_settings():
    settings = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            saved = json.load(f)
        for key, options in CHOICES.items():
            if saved.get(key) in [v for _t, v in options]:
                settings[key] = saved[key]
        if isinstance(saved.get("categories"), list):
            settings["categories"] = [c for c in saved["categories"] if isinstance(c, str)]
    except (OSError, ValueError):
        pass
    return settings


def save_settings(settings):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=1)


def voice_names():
    """Everything a voice can say: every object's name, then the extra phrases."""
    return [it.id for it in objs.load_items(enabled_only=False)] + list(objs.EXTRA_WORDS)


def count_voices(names):
    return sum(os.path.exists(objs.our_voice_path(n)) for n in names)


class Button:
    def __init__(self, rect, text, action, color=PANEL, font="normal"):
        self.rect, self.text, self.action, self.color, self.font = pygame.Rect(rect), text, action, color, font


class Menu:
    def __init__(self, screen, settings):
        self.screen = screen
        self.settings = settings
        self.w, self.h = screen.get_size()
        u = min(self.w, self.h)
        self.fonts = {"title": sys_font("segoeui", int(u * 0.07), bold=True),
                      "big": sys_font("segoeui", int(u * 0.05), bold=True),
                      "normal": sys_font("segoeui", int(u * 0.031)),
                      "small": sys_font("segoeui", int(u * 0.024))}
        self.emoji_size = int(u * 0.2)
        self.page = "menu"
        self.buttons = []
        self.result = None
        self.recorder = MicRecorder()
        self.channel = pygame.mixer.Channel(0)
        self.objects = ObjectPages(self)
        self.keyboard_up = False  # Android's on-screen keyboard
        # "record our voices" page
        self.names = voice_names()
        self.index = 0
        self.recording = False
        self.message = ""

    # ------------------------------------------------------------ plumbing
    def run(self):
        """Show the start screen until Play or Exit -> "play" / "exit"."""
        pygame.mouse.set_visible(True)
        clock = pygame.time.Clock()
        self.result = None
        self.page = "menu"
        while self.result is None:
            clock.tick(60)
            try:
                self._frame()
            except Exception:  # never close the game over a problem here - log it and carry on
                log_error(f"start screen, page {self.page}")
                self._recover()
        if self.recording:
            self.recorder.stop()
            self.recording = False
        return self.result

    def _frame(self):
        for e in pygame.event.get():
            if self.page == "edit" and e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
                drawing = self.objects.stroke_last is not None
                self.objects.mouse(e)
                if drawing:  # the end of a brush stroke isn't a button tap
                    continue
            if e.type == pygame.MOUSEBUTTONUP and e.button == 1:  # also what a touchscreen tap sends
                self._click(e.pos)
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_AC_BACK:  # Android's back button
                    e = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="", mod=0)
                self._key(e)
            elif e.type == pygame.TEXTINPUT:  # Android's on-screen keyboard types this way
                self.objects.type_text(e.text)
        if ANDROID and bool(self.objects.typing) != self.keyboard_up:  # on-screen keyboard up while typing
            self.keyboard_up = bool(self.objects.typing)
            (pygame.key.start_text_input if self.keyboard_up else pygame.key.stop_text_input)()
        if self.recording and self.recorder.seconds() >= MAX_RECORD_SECONDS:
            self._stop_recording()
        self.objects.tick()
        self._draw()

    def _recover(self):
        """After an error: stop any recording and say what happened."""
        note = "Something went wrong - details saved in crash_log.txt"
        for stop in (lambda: self.recorder.stop(), lambda: setattr(self.objects, "recording", None),
                     lambda: setattr(self, "recording", False), lambda: setattr(self.objects, "stroke_last", None)):
            try:
                stop()
            except Exception:
                pass
        self.message = self.objects.message = note

    def _click(self, pos):
        for b in reversed(self.buttons):  # topmost first
            if b.rect.collidepoint(pos):
                b.action()
                return

    def _key(self, e):
        if self.page == "menu":
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.result = "play"
        elif self.page in ("objects", "edit", "pick"):
            self.objects.key(e)
        else:
            if e.key == pygame.K_SPACE:
                self._toggle_recording()
            elif e.key == pygame.K_RIGHT:
                self._go(1)
            elif e.key == pygame.K_LEFT:
                self._go(-1)
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._listen()
            elif e.key == pygame.K_ESCAPE:
                self._leave_recording()

    def _set(self, key, value):
        self.settings[key] = value
        save_settings(self.settings)

    def _toggle_category(self, name):
        """Tap a category to add it to (or take it out of) what's played with; All = every category."""
        chosen = []
        if name is not None:
            chosen = self._chosen_categories()
            chosen = [c for c in chosen if c != name] if name in chosen else chosen + [name]
            if set(chosen) >= set(objs.categories()):  # everything picked = All
                chosen = []
        self._set("categories", chosen)

    def _chosen_categories(self):
        known = objs.categories()
        return [c for c in self.settings["categories"] if c in known]

    def _text(self, text, font, color, **pos):
        surf = self.fonts[font].render(text, True, color)
        rect = surf.get_rect(**pos)
        self.screen.blit(surf, rect)
        return rect

    def _button(self, rect, text, action, color=PANEL, font="normal"):
        b = Button(rect, text, action, color, font)
        self.buttons.append(b)
        pygame.draw.rect(self.screen, color, b.rect, border_radius=int(b.rect.h * 0.3))
        self._text(text, font, TEXT, center=b.rect.center)
        return b

    def _fit(self, text, font="normal"):
        tw, th = self.fonts[font].size(text)
        return tw + int(self.h * 0.05), th + int(self.h * 0.03)

    def _draw(self):
        self.screen.fill(BG)
        self.buttons = []
        if self.page == "menu":
            self._draw_menu()
        elif self.page == "record":
            self._draw_record()
        elif self.page == "objects":
            self.objects.draw_list()
        elif self.page == "pick":
            self.objects.draw_picker()
        else:
            self.objects.draw_edit(time.monotonic())
        pygame.display.flip()

    # ---------------------------------------------------------- start page
    def _draw_menu(self):
        w, h = self.w, self.h
        self._text("Baby Smash", "title", TEXT, center=(w / 2, h * 0.08))
        self._text("Settings for grown-ups", "normal", DIM, center=(w / 2, h * 0.15))
        y = h * 0.21
        row_h = h * 0.076
        for label, key in ROWS:
            self._text(label, "normal", TEXT, midleft=(w * 0.08, y))
            if key == "categories":
                y = self._draw_category_chips(y)
                y += row_h
                continue
            x = w * 0.3
            for text, value in CHOICES[key]:
                bw, bh = self._fit(text)
                selected = self.settings[key] == value
                self._button((x, y - bh / 2, bw, bh), text, lambda k=key, v=value: self._set(k, v),
                             ACCENT if selected else PANEL)
                x += bw + w * 0.012
            if key == "voice":  # the recording button sits right under the voice choice
                y += row_h
                names = self.names
                done = count_voices(names)
                text = f"Record our voices  ({done} of {len(names)} done)"
                bw, bh = self._fit(text)
                self._button((w * 0.3, y - bh / 2, bw, bh), text, self._open_recording, (70, 55, 95))
                if self.settings["voice"] == "ours" and done < len(names):
                    note = "Words you haven't recorded use the built-in voice."
                    self._text(note, "small", DIM, midleft=(w * 0.3 + bw + w * 0.015, y))
            y += row_h
        self._text("Objects", "normal", TEXT, midleft=(w * 0.08, y))
        items = objs.load_items(enabled_only=False)
        on = sum(objs.is_enabled(it.id) for it in items)
        text = f"Draw, add & edit objects  ({on} of {len(items)} in the game)"
        bw, bh = self._fit(text)
        self._button((w * 0.3, y - bh / 2, bw, bh), text, self.objects.open_list, (55, 85, 95))

        bw, bh = w * 0.26, h * 0.09
        self._button((w / 2 - bw / 2, h * 0.87, bw, bh), "Play", self._play, GOOD, "big")
        ew, eh = self._fit("Exit", "small")
        self._button((w * 0.03, h * 0.93, ew, eh), "Exit", self._exit, PANEL, "small")
        back = ("In the game, tap the 4 corners clockwise from top-left to come back here." if ANDROID
                else "In the game, type  quit  to come back here.")
        self._text(back, "small", DIM, midright=(w * 0.97, h * 0.95))

    def _draw_category_chips(self, y):
        """The "Play with" row: All, or any mix of categories (wraps to a second line if needed)."""
        w, h = self.w, self.h
        chosen = self._chosen_categories()
        x = w * 0.3
        for name in [None] + objs.categories():
            text = "All" if name is None else name
            bw, bh = self._fit(text, "small")
            if x + bw > w * 0.97:
                x, y = w * 0.3, y + bh + h * 0.008
            on = (not chosen) if name is None else (name in chosen)
            self._button((x, y - bh / 2, bw, bh), text, lambda n=name: self._toggle_category(n),
                         ACCENT if on else PANEL, "small")
            x += bw + w * 0.008
        return y

    def _play(self):
        self.result = "play"

    def _exit(self):
        self.result = "exit"

    # ------------------------------------------------------ recording page
    def _open_recording(self):
        self.names = voice_names()
        self.page = "record"
        self.message = ""
        missing = [i for i, n in enumerate(self.names) if not os.path.exists(objs.our_voice_path(n))]
        self.index = missing[0] if missing else 0

    def _leave_recording(self):
        if self.recording:
            self.recorder.stop()
            self.recording = False
        self.page = "menu"

    def _go(self, step):
        if not self.recording:
            self.index = (self.index + step) % len(self.names)
            self.message = ""

    def _jump(self, i):
        if not self.recording:
            self.index = i
            self.message = ""

    def _toggle_recording(self):
        if self.recording:
            self._stop_recording()
            return
        if not MicRecorder.available():
            self.message = "No microphone found."
            return
        self.channel.stop()
        try:
            self.recorder.start()
        except Exception:
            log_error("opening the microphone")
            self.message = "Couldn't open the microphone - is another app using it?"
            return
        self.recording = True
        self.message = "Recording... tap Stop when you're done."

    def _stop_recording(self):
        samples = self.recorder.stop()
        self.recording = False
        cleaned = clean_recording(samples)
        if cleaned is None:
            self.message = "Didn't hear anything - try again a little louder or closer."
            return
        save_wav(objs.our_voice_path(self.names[self.index]), cleaned)
        self.message = "Saved!"
        self._listen()

    def _listen(self):
        if self.recording:
            return
        name = self.names[self.index]
        path = next((p for p in (objs.our_voice_path(name), objs.builtin_voice_path(name)) if os.path.exists(p)), None)
        if path:
            self.channel.play(pygame.mixer.Sound(path))
        else:
            self.message = "No recording for this one yet."

    def _delete(self):
        path = objs.our_voice_path(self.names[self.index])
        if not self.recording and os.path.exists(path):
            os.remove(path)
            self.message = "Deleted - the built-in voice will be used."

    def _prompt(self, name):
        """(picture, word to show, what to say)"""
        if name in EXTRA_PROMPTS:
            emoji, say = EXTRA_PROMPTS[name]
            return objs.render_emoji(emoji, self.emoji_size), name.capitalize(), say
        item = objs.get_item(name)
        return self.objects.thumb(item, int(self.h * 0.24)), item.word, f'"{item.word}!"'

    def _draw_record(self):
        w, h = self.w, self.h
        name = self.names[self.index]
        pic, word, say = self._prompt(name)
        recorded = os.path.exists(objs.our_voice_path(name))
        has_builtin = os.path.exists(objs.builtin_voice_path(name))
        done = count_voices(self.names)

        self._text("Record our voices", "big", TEXT, center=(w / 2, h * 0.07))
        self._text(f"{done} of {len(self.names)} recorded  ·  word {self.index + 1} of {len(self.names)}",
                   "small", DIM, center=(w / 2, h * 0.13))
        dw, dh = self._fit("Done")
        self._button((w * 0.97 - dw, h * 0.04, dw, dh), "Done", self._leave_recording, ACCENT)

        self.screen.blit(pic, pic.get_rect(center=(w / 2, h * 0.33)))
        self._text(word, "big", TEXT, center=(w / 2, h * 0.52))
        self._text(f"Say it the way you'd say it to him:  {say}", "normal", DIM, center=(w / 2, h * 0.59))
        if recorded:
            status, color = "Recorded - tap Listen to hear it", GOOD
        elif has_builtin:
            status, color = "Not recorded yet - the built-in voice is used", DIM
        else:
            status, color = "Not recorded yet - this one has no built-in voice", DIM
        self._text(self.message or status, "normal", BAD if self.recording else color, center=(w / 2, h * 0.65))

        labels = [("Previous", lambda: self._go(-1), PANEL),
                  ("■  Stop" if self.recording else "●  Record", self._toggle_recording,
                   BAD if self.recording else (150, 60, 70)),
                  ("Listen", self._listen, PANEL),
                  ("Delete", self._delete, PANEL),
                  ("Next", lambda: self._go(1), PANEL)]
        sizes = [self._fit(t) for t, _a, _c in labels]
        gap = w * 0.015
        x = w / 2 - (sum(s[0] for s in sizes) + gap * (len(sizes) - 1)) / 2
        for (text, action, color), (bw, bh) in zip(labels, sizes):
            self._button((x, h * 0.72, bw, bh), text, action, color)
            x += bw + gap

        if self.recording:  # level meter + time left
            mw = w * 0.4
            pygame.draw.rect(self.screen, PANEL, (w / 2 - mw / 2, h * 0.83, mw, h * 0.02), border_radius=6)
            pygame.draw.rect(self.screen, GOOD, (w / 2 - mw / 2, h * 0.83, mw * min(1.0, self.recorder.level * 3),
                                                 h * 0.02), border_radius=6)
            left = max(0.0, MAX_RECORD_SECONDS - self.recorder.seconds())
            self._text(f"{left:.1f} s", "small", DIM, midleft=(w / 2 + mw / 2 + w * 0.01, h * 0.84))
        else:
            self._text("Keys: Space = record/stop · ← → = previous/next · Enter = listen",
                       "small", DIM, center=(w / 2, h * 0.84))

        # every word as a dot: filled = recorded; tap one to jump to it
        n = len(self.names)
        r = min(h * 0.012, w * 0.9 / n / 2.6)
        step = w * 0.9 / n
        for i, word_id in enumerate(self.names):
            cx, cy = w * 0.05 + step * (i + 0.5), h * 0.93
            filled = os.path.exists(objs.our_voice_path(word_id))
            if i == self.index:
                pygame.draw.circle(self.screen, TEXT, (cx, cy), r * 1.7, 2)
            pygame.draw.circle(self.screen, GOOD if filled else PANEL, (cx, cy), r)
            self.buttons.append(Button((cx - step / 2, cy - r * 2, step, r * 4), "", lambda i=i: self._jump(i)))
