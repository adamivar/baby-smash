"""The game itself.

Words mode ("Who's that?"): a thing appears as a shaking silhouette while its real
sound plays, then it's revealed as a voice names it, and the sound plays again. Once
revealed it moves in character - frogs hop, fish swim, cars drive.
Peekaboo mode: an animal hides behind a bush; any tap or key pulls the bush away.
"""
import math
import random

import pygame

from bs_audio import PENTATONIC, counting_chimes, make_tone
from bs_objects import PARTS, object_art
from bs_paths import ANDROID

NEW_ITEM_COOLDOWN = 1.6  # seconds before a new thing can replace the current one
MORE_MINUTES = 5         # added by typing "more"
BRIGHTNESS = 0.85        # pictures at 85% brightness - gentler on little eyes
MAX_PARTICLES = 300      # sparkles on screen at once
PARTICLE_BUDGET = 40     # new sparkles per frame, so palming the screen can't bog it down
NO_SOUND_SUSPENSE = 1.2  # how long the silhouette waits when a thing has no real sound

THEMES = {
    "night": {"bg": (0, 0, 0), "text": (191, 191, 202), "shadow": (45, 45, 60), "hint": (120, 120, 130),
              "rays": (24, 28, 56), "silhouette": (6, 6, 16), "rim": (130, 140, 200), "flash": (190, 195, 245),
              "sky": (70, 75, 100)},
    "day": {"bg": (118, 160, 200), "text": (30, 36, 66), "shadow": (170, 200, 228), "hint": (40, 55, 85),
            "rays": (150, 190, 226), "silhouette": (28, 34, 70), "rim": (232, 240, 255), "flash": (250, 250, 255),
            "sky": (196, 216, 236)},
}
NIGHT = THEMES["night"]
COLORS = [tuple(int(v * BRIGHTNESS) for v in c) for c in
          [(255, 70, 70), (255, 150, 30), (255, 215, 0), (80, 200, 80), (40, 170, 255),
           (120, 90, 255), (230, 80, 200), (0, 200, 190), (255, 110, 150)]]
WHITE = tuple(int(255 * BRIGHTNESS) for _ in range(3))


# ------------------------------------------------------------------- drawing
def lerp_color(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def dim_surface(surf):
    """Scale a picture's brightness down (alpha untouched)."""
    k = int(255 * BRIGHTNESS)
    surf.fill((k, k, k), special_flags=pygame.BLEND_RGB_MULT)
    return surf


def ease_out_back(x):
    c1 = 1.70158
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_in_out(x):
    return x * x * (3 - 2 * x)


def render_picture(art, theme):
    """art (an emoji or a drawing) -> (picture on a faint halo, silhouette with a thin rim), same size so they line up."""
    size = int(max(art.get_size()) * 1.25)
    center = (size / 2, size / 2)
    pos = art.get_rect(center=center).topleft

    pic = pygame.Surface((size, size), pygame.SRCALPHA)
    for i in range(12, 0, -1):  # faint glow: stacked translucent circles
        pygame.draw.circle(pic, (255, 255, 255, 5), center, size / 2 * i / 12)
    pic.blit(art, pos)

    mask = pygame.mask.from_surface(art, 60)
    shape = mask.to_surface(setcolor=(*theme["silhouette"], 255), unsetcolor=(0, 0, 0, 0))
    rim = mask.to_surface(setcolor=(*theme["rim"], 255), unsetcolor=(0, 0, 0, 0))
    sil = pygame.Surface((size, size), pygame.SRCALPHA)
    r = max(3, round(size * 0.01))
    for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r), (r, r), (-r, r), (r, -r), (-r, -r)):
        sil.blit(rim, (pos[0] + dx, pos[1] + dy))
    sil.blit(shape, pos)
    return dim_surface(pic).convert_alpha(), sil.convert_alpha()


def label_text(item):
    """The word under the picture; letters show both cases ("Q q") instead of repeating the big letter."""
    if item.glyph and item.glyph.isalpha():
        return f"{item.glyph.upper()} {item.glyph.lower()}"
    return item.word


def render_label(word, font, theme):
    main = font.render(word, True, theme["text"])
    shadow = font.render(word, True, theme["shadow"])
    w, h = main.get_size()
    surf = pygame.Surface((w + 6, h + 6), pygame.SRCALPHA)
    surf.blit(shadow, (6, 6))
    surf.blit(main, (0, 0))
    return surf.convert_alpha()


def render_cloud(w, color, seed):
    rng = random.Random(seed)
    h = int(w * 0.6)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for _ in range(7):  # puffs, kept inside the surface so the tops stay round
        r = rng.uniform(0.12, 0.2) * w
        pygame.draw.circle(surf, color, (rng.uniform(0.3, 0.7) * w, rng.uniform(0.5, 0.62) * h), r)
    pygame.draw.rect(surf, color, (w * 0.12, h * 0.6, w * 0.76, h * 0.22), border_radius=int(h * 0.11))
    return surf.convert_alpha()


# ------------------------------------------------------------------- motion
# How far each kind of movement travels sideways (fraction of the screen's short side).
MOTION_REACH = {"swim": 0.2, "fly": 0.14, "buzz": 0.16, "drive": 0.16, "swing": 0.03}
MOTION_RISE = {"hop": 0.09, "bounce": 0.13, "fly": 0.08, "buzz": 0.07}


def motion_offsets(kind, t, u):
    """How a revealed thing moves at time t -> (dx, dy, angle, sx, sy, flip).

    u is the screen's short side in pixels. The emoji all face left, so things that
    travel flip to face the way they're going.
    """
    s = math.sin
    dx = dy = angle = 0.0
    sx = sy = 1.0
    flip = False
    if kind == "hop":  # jump, then squash on landing
        p = (t % 1.3) / 1.3
        if p < 0.45:
            h = s(p / 0.45 * math.pi)
            dy, sx, sy = -h * 0.09 * u, 1 - 0.04 * h, 1 + 0.06 * h
        elif p < 0.6:
            q = s((p - 0.45) / 0.15 * math.pi)
            sx, sy = 1 + 0.08 * q, 1 - 0.1 * q
    elif kind == "bounce":  # ball: gravity bounce with a squash at the floor
        p = (t % 0.8) / 0.8
        h = 4 * p * (1 - p)
        dy = -h * 0.13 * u
        if h < 0.15:
            q = (0.15 - h) / 0.15
            sx, sy = 1 + 0.1 * q, 1 - 0.12 * q
    elif kind == "wag":  # happy wiggle
        angle, dy = 7 * s(t * 5), -abs(s(t * 5)) * 0.008 * u
    elif kind == "stomp":  # heavy side-to-side steps
        angle, dy = 4 * s(t * 2.2), -abs(s(t * 2.2)) * 0.02 * u
    elif kind == "swim":
        dx, dy, angle = 0.2 * u * s(t * 0.55), 0.025 * u * s(t * 2.2), 5 * s(t * 2.2)
        flip = math.cos(t * 0.55) > 0
    elif kind == "fly":
        dx, dy, angle = 0.14 * u * s(t * 0.8), -0.03 * u + 0.05 * u * s(t * 1.6), 8 * s(t * 3.2)
        flip = math.cos(t * 0.8) > 0
    elif kind == "buzz":  # figure-eight with a buzzy tilt
        dx, dy, angle = 0.16 * u * s(t * 1.2), 0.07 * u * s(t * 2.4), 10 * s(t * 9)
        flip = math.cos(t * 1.2) > 0
    elif kind == "drive":  # back and forth with a bumpy ride
        dx, dy, angle = 0.16 * u * s(t * 0.5), -abs(s(t * 9)) * 0.006 * u, 1.5 * s(t * 9)
        flip = math.cos(t * 0.5) > 0
    elif kind == "swing":  # monkey swinging
        angle, dx = 14 * s(t * 2.0), 0.02 * u * s(t * 2.0)
    elif kind == "sway":
        angle = 6 * s(t * 1.1)
    elif kind == "float":
        dy, angle = 0.025 * u * s(t * 1.1), 4 * s(t * 0.6)
    elif kind == "rock":  # baby rocking
        angle, dy = 8 * s(t * 1.8), -abs(s(t * 1.8)) * 0.01 * u
    else:  # "jiggle"
        angle = 6 * s(t * 4.5) * (0.6 + 0.4 * s(t * 0.9))
    breathe = 0.018 * s(t * 2.4)  # everything gently breathes
    return dx, dy, angle, sx * (1 - breathe / 2), sy * (1 + breathe), flip


class Shown:
    """The one thing currently on screen (plus the previous one, while it leaves)."""
    POP, LEAVE, BOUNCE, REVEAL = 0.45, 0.35, 0.6, 0.5

    def __init__(self, item, pic, sil, label, x, y, unit, hidden):
        self.item, self.pic, self.sil, self.label = item, pic, sil, label
        self.x, self.y, self.unit = x, y, unit
        self.cx, self.cy = x, y  # where it's drawn right now (moves with the animation)
        self.t = 0.0
        self.hidden = hidden  # a silhouette until reveal()
        self.reveal_t = None
        self.moving = False
        self.energy = 0.0  # 0..1, eases the movement in and out
        self.move_t = 0.0
        self.bounce_t = None
        self.leave_t = None
        self.show_label = not hidden
        self.frames = {}  # rotated/flipped copies, cached: rotating big pictures every frame is slow
        self.made_frame = False

    def reveal(self):
        self.hidden = False
        self.reveal_t = 0.0
        self.show_label = True
        self.moving = True

    def hit(self, x, y):
        r = self.pic.get_width() * 0.45
        return (x - self.cx) ** 2 + (y - self.cy) ** 2 < r * r

    def poke(self):
        # Don't restart the wiggle on every key of a mash, or it looks frozen.
        if self.bounce_t is None or self.bounce_t > 0.3:
            self.bounce_t = 0.0

    def leave(self):
        if self.leave_t is None:
            self.leave_t = 0.0

    def update(self, dt):
        self.t += dt
        if self.reveal_t is not None:
            self.reveal_t += dt
        self.energy += ((1.0 if self.moving else 0.0) - self.energy) * min(1.0, dt * 3)
        self.move_t += dt * self.energy
        if self.bounce_t is not None:
            self.bounce_t += dt
            if self.bounce_t > self.BOUNCE:
                self.bounce_t = None
        if self.leave_t is not None:
            self.leave_t += dt
            return self.leave_t < self.LEAVE
        return True

    def _frame(self, which, angle, flip):
        angle = int(round(angle / 3)) * 3
        key = (which, angle, flip)
        frame = self.frames.get(key)
        if frame is None and self.made_frame:  # one new rotation per frame; meanwhile use the closest one
            near = [k for k in self.frames if k[0] == which and k[2] == flip]
            if near:
                return self.frames[min(near, key=lambda k: abs(k[1] - angle))]
        if frame is None:
            self.made_frame = True
            if len(self.frames) > 80:
                self.frames.clear()
            src = self.sil if which == "sil" else self.pic
            if flip:
                src = pygame.transform.flip(src, True, False)
            frame = pygame.transform.rotozoom(src, angle, 1) if angle else src
            self.frames[key] = frame
        return frame

    def draw(self, screen):
        self.made_frame = False
        scale = ease_out_back(self.t / self.POP) if self.t < self.POP else 1.0
        if self.hidden:  # anticipation: the silhouette shakes in little bursts
            burst = max(0.0, math.sin(self.t * 2.6))
            dx = dy = 0.0
            angle = 6 * math.sin(self.t * 18) * burst
            sx = sy = 1 + 0.02 * math.sin(self.t * 3)
            flip = False
        else:
            dx, dy, angle, sx, sy, flip = motion_offsets(self.item.move, self.move_t, self.unit)
            e = self.energy
            dx, dy, angle = dx * e, dy * e, angle * e
            sx, sy = 1 + (sx - 1) * e, 1 + (sy - 1) * e
            flip = flip and e > 0.5
        sx, sy = sx * scale, sy * scale
        if self.bounce_t is not None:
            k = self.bounce_t / self.BOUNCE
            squash = 0.14 * math.sin(k * math.pi * 3) * (1 - k)
            sx, sy = sx * (1 + squash), sy * (1 - squash)
        alpha = 1.0
        if self.leave_t is not None:
            k = self.leave_t / self.LEAVE
            sx, sy, alpha = sx * (1 - 0.5 * k), sy * (1 - 0.5 * k), 1 - k

        if self.hidden:
            layers = [("sil", 1.0)]
        elif self.reveal_t is not None and self.reveal_t < self.REVEAL:  # silhouette melts into the picture
            k = self.reveal_t / self.REVEAL
            pulse = 1 + 0.18 * math.sin(k * math.pi)
            sx, sy = sx * pulse, sy * pulse
            layers = [("sil", 1 - k), ("pic", k)]
        else:
            layers = [("pic", 1.0)]

        self.cx, self.cy = self.x + dx, self.y + dy
        for which, layer_alpha in layers:
            img = self._frame(which, angle, flip)
            cached = True
            if abs(sx - 1) > 0.004 or abs(sy - 1) > 0.004:
                w, h = img.get_size()
                img = pygame.transform.smoothscale(img, (max(1, int(w * sx)), max(1, int(h * sy))))
                cached = False
            a = int(255 * alpha * layer_alpha)
            if a < 255:
                img.set_alpha(a)
            screen.blit(img, img.get_rect(center=(self.cx, self.cy)))
            if cached and a < 255:
                img.set_alpha(255)

        if self.show_label and not self.hidden:
            since = self.reveal_t if self.reveal_t is not None else self.t
            a = int(255 * alpha * min(1.0, max(0.0, (since - 0.15) / 0.3)))
            if a > 0:
                self.label.set_alpha(a)
                screen.blit(self.label, self.label.get_rect(midtop=(self.x, self.y + self.pic.get_height() * 0.42)))


# ----------------------------------------------------------------------- game
class Game:
    def __init__(self, screen, items, voice, sfx, settings, parts=None, parts_on=None):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.unit = min(self.w, self.h)
        self.theme = THEMES.get(settings.get("theme"), NIGHT)
        self.items = items  # the objects that are switched on (see bs_objects)
        # game parts (bs_objects.PARTS): hello, peekaboo bush, moon... possibly customized or switched off
        self.parts = {p.id: p for p in (parts or PARTS)}
        parts_on = parts_on or {}
        self.voice = dict(voice)  # spoken names, by object id (and by part id: hello / where / peekaboo / bye)
        self.sfx = dict(sfx)  # sound effects, by object id (and part id)
        self.off = {pid for pid in self.parts if not parts_on.get(pid, True)}  # parts switched off
        for pid in self.off:
            self.voice.pop(pid, None)
            self.sfx.pop(pid, None)
        for it in items:  # numbers without a recorded sound count out loud in chimes
            if it.glyph and it.glyph.isdigit() and it.id not in self.sfx:
                self.sfx[it.id] = counting_chimes(int(it.glyph))
        self.voice_ch = pygame.mixer.Channel(0)  # reserved for speech + real sounds
        self.sequence = []  # clips still to play on voice_ch, in order
        self.talk_until = 0.0  # when the spoken part ends (real sounds may be cut off after this)
        self.chimes = [make_tone(523.25 * 2 ** (s / 12), dur=0.4, vol=0.12) for s in PENTATONIC]

        label_font = pygame.font.SysFont("arialroundedmtbold,comicsansms,arialblack,arial",
                                         int(self.unit * 0.09), bold=True)
        self.small_font = pygame.font.SysFont("segoeui,arial", max(16, int(self.h * 0.024)))
        self.pictures, self.silhouettes = {}, {}
        shown_parts = [self.parts["hello"]] if "hello" not in self.off else []
        for it in items + shown_parts:  # your drawing if there is one, else the emoji
            art = object_art(it, int(self.unit * 0.4))
            self.pictures[it.id], self.silhouettes[it.id] = render_picture(art, self.theme)
        self.labels = {it.id: render_label(label_text(it), label_font, self.theme) for it in items + shown_parts}
        self.by_key = {}  # key -> the objects it brings, taken in turn (A: Apple, then the letter A...)
        for it in items:
            if it.key:
                self.by_key.setdefault(it.key, []).append(it)
        self.key_turn = {}
        self.moon = render_picture(object_art(self.parts["bye"], int(self.unit * 0.4)), NIGHT)[0]
        self.moon_frames = {}  # rotated copies, for the moon's animation
        self.star = dim_surface(object_art(self.parts["star"], int(self.unit * 0.055))).convert_alpha()
        # bedtime: twinkly stars on both sides of the moon, never on top of it
        self.stars = [(random.choice((random.uniform(0.04, 0.3), random.uniform(0.7, 0.96))),
                       random.uniform(0.06, 0.85), random.uniform(0, 6)) for _ in range(16)]
        self.alldone_label = render_label("All done!", label_font, NIGHT)
        self.bush = dim_surface(object_art(self.parts["where"], int(self.unit * 0.5))).convert_alpha()
        # the sky behind everything: faint stars at night, drifting clouds by day
        self.sky_stars = [(random.uniform(0, self.w), random.uniform(0, self.h), random.uniform(0.8, 2.0),
                           random.uniform(0, 6.3)) for _ in range(70)]
        self.clouds = []
        if self.theme is not NIGHT:
            for i in range(4):
                cloud = render_cloud(int(self.unit * random.uniform(0.3, 0.45)), self.theme["sky"], i)
                self.clouds.append([cloud, random.uniform(-cloud.get_width(), self.w),
                                    random.uniform(0.02, 0.6) * self.h, random.uniform(6, 14)])

        self.shown = None
        self.leaving = []
        self.particles = []  # [x, y, vx, vy, life, color, radius]
        self.budget = PARTICLE_BUDGET  # new particles allowed this frame
        self.clock_t = 0.0
        self.last_new = -99.0
        self.last_chime = -99.0
        self.deck = []  # shuffled order for keys/taps that don't map to an item
        self.reveal_at = None  # when the current silhouette gets revealed
        self.rays = 0.0  # 0..1, the "who's that?" light rays behind a silhouette
        self.flash = None  # (x, y, t) ring of light at the moment of the reveal

        self.peekaboo = settings.get("mode") == "peekaboo"
        self.peek_state = None  # "hidden" / "revealed" / "covering"
        self.peek_t = 0.0
        self.bush_down = 0.0  # 0 = bush covering, 1 = bush fully lowered

        minutes = settings.get("minutes", 10)
        self.session_left = minutes * 60 if minutes else None
        self.show_tips = settings.get("tips", True)
        self.sleeping = False
        self.sleep_t = 0.0

        if self.peekaboo:
            self._start_peekaboo()
        elif "hello" not in self.off:  # a friendly wave to start
            hello = self._show(self.parts["hello"], self.w / 2, self.h * 0.45)
            hello.moving = True
            self._say("hello", then_sfx="hello")

    # --------------------------------------------------------------- helpers
    def _next_item(self):
        if not self.deck:
            self.deck = random.sample(self.items, len(self.items))
        return self.deck.pop()

    def _speak(self, *steps):
        """Play clips in order - steps like ("voice", "Dog"), ("sfx", "Dog"). Missing ones are skipped.
        Nothing new can replace the current thing until the last spoken clip has finished."""
        clips, talk = [], 0.0
        for kind, key in steps:
            clip = (self.voice if kind == "voice" else self.sfx).get(key)
            if clip:
                clips.append(clip)
                if kind == "voice":
                    talk = sum(c.get_length() for c in clips)
        self.talk_until = self.clock_t + talk
        self._play(clips)

    def _say(self, *keys, then_sfx=None):
        """Speak voice clips in order, optionally followed by a sound."""
        self._speak(*[("voice", k) for k in keys], *([("sfx", then_sfx)] if then_sfx else []))

    def _play(self, clips):
        self.sequence = list(clips[1:])
        if clips:
            self.voice_ch.play(clips[0])
        else:
            self.voice_ch.stop()

    def _replay(self, item_id):
        """Tapping the picture: its sound if there is one, else its name."""
        if item_id in self.sfx:
            self._play([self.sfx[item_id]])
        else:
            self._say(item_id)

    def _chime(self, soft=False):
        """The tap sound: your recording if there is one, else soft chimes (or nothing if switched off)."""
        if "tap" in self.off or self.clock_t - self.last_chime <= (0.25 if soft else 0.1):
            return
        self.last_chime = self.clock_t
        if "tap" in self.sfx:
            self.sfx["tap"].play()
        else:
            random.choice(self.chimes[:6] if soft else self.chimes).play()

    def _burst(self, x, y, count=10, speed=350):
        count = min(count, self.budget)  # a whole palm on the screen can't flood the frame
        self.budget -= count
        for _ in range(count):
            a = random.uniform(0, 2 * math.pi)
            v = random.uniform(0.3, 1) * speed
            self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v, random.uniform(0.5, 0.9),
                                   random.choice(COLORS + [WHITE]), random.uniform(0.008, 0.016) * self.unit])

    def _show(self, item, x=None, y=None, hidden=False):
        if x is None:
            x = self.w / 2 + random.uniform(-0.08, 0.08) * self.unit
            y = self.h * 0.45 + random.uniform(-0.04, 0.04) * self.unit
        pic = self.pictures[item.id]
        # keep it on screen even at the far end of its movement
        margin_x = pic.get_width() * 0.5 + MOTION_REACH.get(item.move, 0.02) * self.unit
        margin_top = pic.get_height() * 0.5 + MOTION_RISE.get(item.move, 0.02) * self.unit
        margin_bottom = pic.get_height() * 0.5 + self.labels[item.id].get_height()
        x = min(max(x, margin_x), self.w - margin_x) if self.w > 2 * margin_x else self.w / 2
        y = min(max(y, margin_top), self.h - margin_bottom)
        if self.shown:
            self.shown.leave()
            self.leaving.append(self.shown)
        self.shown = Shown(item, pic, self.silhouettes[item.id], self.labels[item.id], x, y, self.unit, hidden)
        self.last_new = self.clock_t
        return self.shown

    def _can_replace(self):
        # A new thing may cut off the last real sound, but never the spoken word or the suspense.
        if self.shown and self.shown.item.part:  # the hello wave steps aside as soon as it has said hello
            return self.clock_t >= self.talk_until
        return (self.clock_t - self.last_new >= NEW_ITEM_COOLDOWN and self.clock_t >= self.talk_until
                and not (self.shown and self.shown.hidden))

    # --------------------------------------------------- words: who's that?
    def _surprise(self, item, x, y):
        """Silhouette + its real sound now; reveal + the word + the sound again once the sound ends."""
        shown = self._show(item, x, y, hidden=True)
        sound = self.sfx.get(item.id)
        if sound:
            self._play([sound])
            wait = sound.get_length() + 0.25
        elif "mystery" in self.sfx:  # your mystery sound
            self._play([self.sfx["mystery"]])
            wait = max(NO_SOUND_SUSPENSE, self.sfx["mystery"].get_length() + 0.25)
        else:
            self._play([])
            if "mystery" not in self.off:
                random.choice(self.chimes).play()
            wait = NO_SOUND_SUSPENSE
        self.reveal_at = self.clock_t + wait
        voice = self.voice.get(item.id)
        self.talk_until = self.reveal_at + (voice.get_length() if voice else 0.5)
        self._burst(shown.x, shown.y, count=6, speed=250)

    def _reveal_word(self):
        shown = self.shown
        shown.reveal()
        self.reveal_at = None
        self.flash = (shown.x, shown.y, 0.0)
        self._burst(shown.x, shown.y, count=20, speed=500)
        if "reveal" in self.sfx:  # ta-da, on its own channel so the word isn't delayed
            self.sfx["reveal"].play()
        self._say(shown.item.id, then_sfx=shown.item.id)

    # ----------------------------------------------------------- peekaboo
    def _start_peekaboo(self):
        self.leaving.clear()
        self.shown = None
        self._hide_new_item()

    def _hide_new_item(self):
        item = self._next_item()
        shown = self._show(item, self.w / 2, self.h * 0.42)
        shown.t = Shown.POP  # no pop-in; it's already behind the bush
        shown.show_label = False
        self.leaving.clear()  # the old one is behind the bush; swap it instantly
        self.peek_state, self.peek_t, self.bush_down = "hidden", 0.0, 0.0
        self._say("where", then_sfx="where")

    def _reveal_peekaboo(self):
        self.peek_state, self.peek_t = "revealed", 0.0
        self.shown.show_label = True
        self.shown.moving = True
        self.shown.poke()
        self._burst(self.shown.x, self.shown.y, count=16, speed=450)
        item_id = self.shown.item.id
        self._speak(("voice", "peekaboo"), ("sfx", "peekaboo"), ("voice", item_id), ("sfx", item_id))

    # --------------------------------------------------------------- input
    def toggle_mode(self):
        self.peekaboo = not self.peekaboo
        self.reveal_at = None
        if self.peekaboo:
            self._start_peekaboo()
        else:
            self.peek_state = None
            self.bush_down = 1.0
            if self.shown:
                self.shown.hidden = False
                self.shown.show_label = True
                self.shown.moving = True

    def add_time(self):
        if self.session_left is not None:
            self.session_left = max(self.session_left, 0) + MORE_MINUTES * 60
            if self.sleeping:
                self.sleeping = False
                if self.peekaboo:  # bedtime cleared the screen; hide a fresh animal
                    self._start_peekaboo()

    def press(self, ch):
        """A keyboard key. Letters/digits always bring the same thing."""
        if self.sleeping:
            return
        choices = self.by_key.get(ch.lower()) if ch else None
        if not choices:
            self._interact(self._next_item(), None, None)
            return
        turn = self.key_turn.get(ch.lower(), 0)
        if self._interact(choices[turn % len(choices)], None, None):
            self.key_turn[ch.lower()] = turn + 1  # next press of this key brings the next one

    def tap(self, x, y):
        if self.sleeping:
            return
        self._burst(x, y, count=4, speed=200)  # instant sparkle under every finger
        shown = self.shown
        if shown and shown.hit(x, y) and not shown.hidden and self.peek_state != "hidden":
            shown.poke()
            self._burst(x, y, count=6, speed=250)
            if self.clock_t >= self.talk_until:
                self._replay(shown.item.id)
            return
        self._interact(self._next_item(), x, y)

    def _interact(self, item, x, y):
        """-> True if `item` was brought on screen."""
        if self.peekaboo:
            if self.peek_state == "hidden" and self.clock_t - self.last_new > 0.8:
                self._reveal_peekaboo()
            else:
                self._chime(soft=True)
            return False
        if not self.shown or self._can_replace():
            self._surprise(item, x, y)
            return True
        self.shown.poke()  # too soon (or mid-surprise): a little wiggle instead of a pile-up
        self._chime(soft=True)
        return False

    def drag(self, x, y):
        if self.sleeping:
            return
        if self.budget > 0:
            self.budget -= 1
            self.particles.append([x, y, random.uniform(-60, 60), random.uniform(-60, 60),
                                   random.uniform(0.6, 1.0), random.choice(COLORS),
                                   random.uniform(0.012, 0.022) * self.unit])
        self._chime(soft=True)

    # ------------------------------------------------------------- update
    def update(self, dt):
        self.clock_t += dt
        self.budget = PARTICLE_BUDGET
        if self.sequence and not self.voice_ch.get_busy():
            self.voice_ch.play(self.sequence.pop(0))

        if self.session_left is not None and not self.sleeping:
            self.session_left -= dt
            if self.session_left <= 0:
                self.sleeping, self.sleep_t = True, 0.0
                self.reveal_at = None
                if self.shown:
                    self.shown.leave()
                    self.leaving.append(self.shown)
                    self.shown = None
                self._say("bye", "bye", then_sfx="bye")
        if self.sleeping:
            self.sleep_t += dt

        if self.reveal_at is not None and self.shown and self.shown.hidden and self.clock_t >= self.reveal_at:
            self._reveal_word()
        want_rays = 1.0 if self.shown and self.shown.hidden else 0.0
        self.rays += (want_rays - self.rays) * min(1.0, dt * (6 if want_rays else 3))
        if self.flash:
            x, y, t = self.flash
            self.flash = (x, y, t + dt) if t + dt < 0.6 else None

        if self.peekaboo and not self.sleeping and self.shown:
            self.peek_t += dt
            if self.peek_state == "revealed":
                self.bush_down = min(1.0, self.bush_down + dt / 0.5)
                if self.peek_t > 4.5 and not self.sequence and not self.voice_ch.get_busy():
                    self.peek_state, self.peek_t = "covering", 0.0
                    self.shown.show_label = False
                    self.shown.moving = False
            elif self.peek_state == "covering":
                self.bush_down = max(0.0, self.bush_down - dt / 0.8)
                if self.bush_down == 0.0:
                    self._hide_new_item()
        elif self.peekaboo and self.sleeping and self.shown is None:
            self.bush_down = 1.0

        if self.shown:
            self.shown.update(dt)
        self.leaving = [s for s in self.leaving if s.update(dt)]
        for cloud in self.clouds:
            cloud[1] += cloud[3] * dt
            if cloud[1] > self.w:
                cloud[1] = -cloud[0].get_width()

        alive = []
        for p in self.particles:
            p[4] -= dt
            if p[4] > 0:
                p[0] += p[2] * dt
                p[1] += p[3] * dt
                p[2] *= 0.94
                p[3] = p[3] * 0.94 + 250 * dt
                alive.append(p)
        self.particles = alive[-MAX_PARTICLES:]

    # --------------------------------------------------------------- draw
    def draw(self):
        night_k = min(1.0, self.sleep_t / 2.5) if self.sleeping else 0.0  # bedtime fades to night
        bg = lerp_color(self.theme["bg"], NIGHT["bg"], night_k)
        self.screen.fill(bg)
        if self.shown and self.rays > 0.01:
            self._draw_rays(bg)  # behind the stars/clouds, so fading rays never cut into them
        self._draw_sky(bg, night_k)
        if self.sleeping:
            self._draw_bedtime(night_k)
        if self.flash:
            x, y, t = self.flash
            k = t / 0.6
            pygame.draw.circle(self.screen, lerp_color(self.theme["flash"], bg, k), (x, y),
                               self.unit * (0.12 + 0.45 * k), max(2, int(self.unit * 0.03 * (1 - k))))
        for s in self.leaving:
            s.draw(self.screen)
        if self.shown:
            self.shown.draw(self.screen)
        if self.peekaboo and not self.sleeping and self.shown:
            covered_top = self.shown.y - self.shown.pic.get_height() * 0.18
            top = covered_top + ease_in_out(self.bush_down) * (self.h - covered_top + 10)
            self.screen.blit(self.bush, self.bush.get_rect(midtop=(self.shown.x, top)))
        for x, y, _vx, _vy, life, color, r in self.particles:
            pygame.draw.circle(self.screen, color, (x, y), max(1, r * min(1, life * 2)))
        self._draw_parent_text()
        pygame.display.flip()

    def _draw_sky(self, bg, night_k):
        if self.theme is NIGHT or night_k > 0:
            k = 1.0 if self.theme is NIGHT else night_k
            for x, y, r, phase in self.sky_stars:
                twinkle = 0.55 + 0.45 * math.sin(self.clock_t * 0.8 + phase)
                pygame.draw.circle(self.screen, lerp_color(bg, NIGHT["sky"], twinkle * k), (x, y), r)
        for cloud, x, y, _speed in self.clouds:
            cloud.set_alpha(int(255 * (1 - night_k)))
            self.screen.blit(cloud, (x, y))

    def _draw_rays(self, bg):
        """Slowly turning light rays behind the silhouette - the "who's that?" moment."""
        color = lerp_color(bg, self.theme["rays"], self.rays)
        cx, cy = self.shown.x, self.shown.y
        r = self.unit * 0.62
        rot = self.clock_t * 0.35
        n = 14
        for i in range(n):
            a0 = rot + i * 2 * math.pi / n
            a1 = a0 + math.pi / n
            pygame.draw.polygon(self.screen, color, [(cx, cy), (cx + r * math.cos(a0), cy + r * math.sin(a0)),
                                                     (cx + r * math.cos(a1), cy + r * math.sin(a1))])

    def _draw_bedtime(self, k):
        a = int(255 * k)
        for fx, fy, phase in self.stars:
            self.star.set_alpha(int(a * (0.55 + 0.45 * math.sin(self.clock_t * 1.5 + phase))))
            self.screen.blit(self.star, self.star.get_rect(center=(fx * self.w, fy * self.h)))
        dx, dy, angle, _sx, _sy, flip = motion_offsets(self.parts["bye"].move, self.sleep_t, self.unit * 0.5)
        key = (int(round(angle / 3)) * 3, flip)
        if key not in self.moon_frames:
            moon = pygame.transform.flip(self.moon, True, False) if flip else self.moon
            self.moon_frames[key] = pygame.transform.rotozoom(moon, key[0], 1) if key[0] else moon
        moon = self.moon_frames[key]
        moon.set_alpha(a)
        self.screen.blit(moon, moon.get_rect(center=(self.w / 2 + dx, self.h * 0.42 + dy)))
        self.alldone_label.set_alpha(a)
        self.screen.blit(self.alldone_label, self.alldone_label.get_rect(midtop=(self.w / 2, self.h * 0.66)))

    def _draw_parent_text(self):
        color = NIGHT["hint"] if self.sleeping else self.theme["hint"]
        pad = int(self.h * 0.015)
        shown = self.shown
        if (self.show_tips and shown and not self.sleeping and shown.show_label and not shown.hidden
                and not shown.item.part):
            it = shown.item
            tip = it.tip
            if tip is None:
                tip = (f"Say: The {it.word.lower()} says {it.says}! Can you say {it.says}?" if it.says
                       else f"Ask: Can you say {it.word.lower()}?")
            text = self.small_font.render(tip, True, color)
            self.screen.blit(text, text.get_rect(bottomleft=(pad * 2, self.h - pad)))
        mode = "peekaboo" if self.peekaboo else "who's that"
        if ANDROID:  # no keyboard: the corner taps (see baby_smash.pyw) are the way out
            info = "grown-ups: tap the 4 corners clockwise from top-left for the menu"
        else:
            info = f"grown-ups type:  quit (menu) · peek (now: {mode})"
        if self.session_left is not None:
            if not self.sleeping:
                info += f" · {max(0, math.ceil(self.session_left / 60))} min left"
            elif not ANDROID:
                info += " · more (+5 min)"
        text = self.small_font.render(info, True, color)
        text.set_alpha(150)
        self.screen.blit(text, text.get_rect(bottomright=(self.w - pad * 2, self.h - pad)))
