"""Every thing in the game: the built-in ones plus ones you add.

Each object has a picture (an emoji, or your drawing), a name, the name spoken
(downloaded voice or your recording), a sound effect (downloaded or recorded), an
animation and a category. Your changes live in objects/ and sounds/our_*:
    objects/objects.json         new objects and categories, changed animations and
                                 categories, objects switched off
    objects/drawings/<id>.png    your drawing of an object
    sounds/our_voice/<id>.wav    its name in your voice
    sounds/our_sfx/<id>.wav      your recording of what it sounds like
Built-in objects use their word as id ("Dog"); new ones get "custom_<n>".
"""
import copy
import json
import math
import os
import random
from collections import namedtuple

import pygame

from bs_audio import OUR_SFX_DIR, OUR_VOICE_DIR, SOUNDS_DIR, WORDS_DIR
from bs_paths import APP_DIR, DATA_DIR
from bs_system import sys_font

OBJECTS_DIR = os.path.join(DATA_DIR, "objects")
DATA_PATH = os.path.join(OBJECTS_DIR, "objects.json")
DRAWINGS_DIR = os.path.join(OBJECTS_DIR, "drawings")
EMOJI_FONT = r"C:\Windows\Fonts\seguiemj.ttf"  # Windows' own emoji
EMOJI_DIR = os.path.join(APP_DIR, "images", "emoji")  # Noto emoji pictures, for where that font isn't (Android)

# key: the keyboard key that always brings it (None for new objects);
# says: for the grown-up tip ("The dog says woof woof!"); move: its animation (see MOVES);
# glyph: letters and numbers are drawn as a big character instead of an emoji;
# part: set for game parts (see PARTS) - which of their features can be customized
Item = namedtuple("Item", "key word emoji says tip move id custom category glyph part", defaults=(None, None))
_BUILTIN = [
    ("a", "Apple", "🍎", "crunch crunch", "Say: Apples are red. Crunch crunch!", "jiggle"),
    ("b", "Ball", "⚽", "bounce bounce", "Ask: Where is your ball?", "bounce"),
    ("c", "Cat", "🐱", "meow", None, "wag"),
    ("d", "Dog", "🐶", "woof woof", None, "wag"),
    ("e", "Elephant", "🐘", "toot toot", "Show: Make a trunk with your arm! Toot toot!", "stomp"),
    ("f", "Frog", "🐸", "ribbit", "Show: Jump like a frog! Ribbit!", "hop"),
    ("g", "Giraffe", "🦒", "munch munch", "Show: Stretch up tall like a giraffe!", "sway"),
    ("h", "Horse", "🐴", "neigh", None, "stomp"),
    ("i", "Ice cream", "🍦", "yum", "Say: Ice cream is cold! Brrr. Yum!", "jiggle"),
    ("j", "Juice", "🧃", "sip sip", "Show: Pretend to drink from a cup. Sip sip!", "jiggle"),
    ("k", "Keys", "🔑", "jingle jingle", "Show: Jingle some real keys!", "jiggle"),
    ("l", "Lion", "🦁", "roar", None, "stomp"),
    ("m", "Monkey", "🐵", "ooh ooh ah ah", None, "swing"),
    ("n", "Nose", "👃", "beep", "Show: Touch his nose, then yours. Beep!", "jiggle"),
    ("o", "Owl", "🦉", "hoo hoo", None, "float"),
    ("p", "Pig", "🐷", "oink oink", None, "stomp"),
    ("q", "Duck", "🦆", "quack quack", None, "swim"),
    ("r", "Bunny", "🐰", "hop hop", "Show: Hop like a bunny! Hop hop!", "hop"),
    ("s", "Sheep", "🐑", "baa", None, "stomp"),
    ("t", "Train", "🚂", "choo choo", None, "drive"),
    ("u", "Bus", "🚌", "beep beep", None, "drive"),
    ("v", "Car", "🚗", "vroom vroom", "Ask: Where is our car? Vroom vroom!", "drive"),
    ("w", "Fish", "🐟", "blub blub", "Show: Make fishy lips! Blub blub!", "swim"),
    ("x", "Baby", "👶", "hee hee", "Ask: Where's the baby? Where are YOU?", "rock"),
    ("y", "Banana", "🍌", "yum", None, "jiggle"),
    ("z", "Bee", "🐝", "buzz buzz", None, "buzz"),
    ("1", "Cow", "🐮", "moo", None, "stomp"),
    ("2", "Bird", "🐦", "tweet tweet", None, "fly"),
    ("3", "Bear", "🐻", "grr", "Show: Give him a big bear hug!", "stomp"),
    ("4", "Chick", "🐤", "peep peep", None, "hop"),
    ("5", "Shoe", "👟", "stomp stomp", "Ask: Where are your shoes?", "stomp"),
    ("6", "Milk", "🥛", "glug glug", None, "jiggle"),
    ("7", "Hat", "🧢", None, "Show: Pat your head. Hat goes here!", "jiggle"),
    ("8", "Moon", "🌙", None, "Say: Night night, moon!", "float"),
    ("9", "Sun", "🌞", None, "Say: Hello, sun! The birds sing in the morning.", "float"),
    ("0", "Book", "📖", None, "Do: Grab a real book together!", "jiggle"),
    # body parts: every letter and digit is taken, so these come up from taps and other keys
    (None, "Eyes", "👀", None, "Show: Point to his eyes, then yours. Peekaboo!", "float"),
    (None, "Ear", "👂", None, "Show: Touch his ears, then yours!", "wag"),
    (None, "Mouth", "👄", None, "Show: Open wide! Ahhh!", "jiggle"),
    (None, "Tongue", "👅", None, "Show: Stick out your tongue! Blehh!", "wag"),
    (None, "Tooth", "🦷", None, "Show: Chomp chomp! Where are his teeth?", "jiggle"),
    (None, "Hand", "✋", None, "Show: Clap your hands! Clap clap!", "wag"),
    (None, "Foot", "🦶", None, "Show: Stomp your feet! Stomp stomp!", "stomp"),
    (None, "Leg", "🦵", None, "Show: Kick your legs! Kick kick!", "swing"),
    (None, "Arm", "💪", None, "Show: Arms up high! So big!", "rock"),
    # everyday first words (people, routines, food, vehicles, outside): also from taps and other keys
    (None, "Mommy", "👩", "mwah", "Show: Point to Mommy! Where's Mommy?", "wag"),
    (None, "Daddy", "👨", "mwah", "Show: Point to Daddy! Where's Daddy?", "wag"),
    (None, "Cup", "🥤", "sip sip", "Do: Hold up his cup. Sip sip!", "jiggle"),
    (None, "Bottle", "🍼", "glug glug", None, "rock"),
    (None, "Spoon", "🥄", "yum yum", "Show: Pretend to eat with a spoon. Yum yum!", "jiggle"),
    (None, "Bath", "🛁", "splash splash", "Show: Splash your hands! Bath time!", "float"),
    (None, "Bed", "🛏", "shh", "Show: Lay your head on your hands. Night night!", "rock"),
    (None, "Teddy", "🧸", None, "Show: Give teddy a big hug!", "rock"),
    (None, "Socks", "🧦", None, "Ask: Where are your socks? On your feet!", "jiggle"),
    (None, "Phone", "📱", "ring ring", "Show: Hold your hand to your ear. Hello!", "jiggle"),
    (None, "Toothbrush", "🪥", "brush brush", "Show: Brush brush your teeth!", "wag"),
    (None, "Cheese", "🧀", "yum", None, "jiggle"),
    (None, "Bread", "🍞", "yum", None, "jiggle"),
    (None, "Water", "💧", "drip drop", None, "float"),
    (None, "Truck", "🚚", "honk honk", None, "drive"),
    (None, "Plane", "✈", "zoom", "Show: Arms out wide, fly like a plane!", "fly"),
    (None, "Boat", "⛵", "toot toot", None, "swim"),
    (None, "Tree", "🌳", "whoosh", "Show: Arms up high, sway like a tree!", "sway"),
    (None, "Flower", "🌸", "sniff sniff", "Show: Smell the flower! Sniff sniff.", "sway"),
]
OUR_OWN = "Our own"  # where new objects go
DEFAULT_CATEGORIES = ["People", "Animals", "Food & drink", "Vehicles", "Body parts", "Letters", "Numbers", "My things",
                      "Outside", "Sky", OUR_OWN]
_DEFAULT_CATEGORY = {word: cat for cat, words in {
    "People": ["Mommy", "Daddy", "Baby"],
    "Animals": ["Cat", "Dog", "Elephant", "Frog", "Giraffe", "Horse", "Lion", "Monkey", "Owl", "Pig", "Duck",
                "Bunny", "Sheep", "Fish", "Bee", "Cow", "Bird", "Bear", "Chick"],
    "Food & drink": ["Apple", "Ice cream", "Juice", "Banana", "Milk", "Cup", "Bottle", "Spoon", "Cheese", "Bread",
                     "Water"],
    "Vehicles": ["Train", "Bus", "Car", "Truck", "Plane", "Boat"],
    "Body parts": ["Nose", "Eyes", "Ear", "Mouth", "Tongue", "Tooth", "Hand", "Foot", "Leg", "Arm"],
    "My things": ["Ball", "Keys", "Shoe", "Hat", "Book", "Bath", "Bed", "Teddy", "Socks", "Phone", "Toothbrush"],
    "Outside": ["Tree", "Flower"],
    "Sky": ["Moon", "Sun"],
}.items() for word in words}
BUILTIN = [Item(*fields, fields[1], False, _DEFAULT_CATEGORY[fields[1]]) for fields in _BUILTIN]

# Letters and numbers share their keys with the objects above: pressing A again and again
# alternates Apple / A (see Game.press).
_FOR = {key: word for key, word, *_rest in _BUILTIN if key}


def _letter_tip(ch):
    partner = _FOR[ch.lower()]
    if partner.upper().startswith(ch):  # "A is for apple" only when it's true
        return f"Say: {ch} is for {partner.lower()}! Can you find {ch} on the keys?"
    return f"Say: This is the letter {ch}! Can you find {ch} on the keys?"


BUILTIN += [Item(ch.lower(), ch, None, None, _letter_tip(ch), "wag", f"Letter {ch}", False, "Letters", ch)
            for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
# Game parts: the pieces of the game itself. They can be drawn / recorded / animated like
# objects (only in the ways that make sense for each), but never come up as things to find.
# features: p = picture, v = voice, s = sound, m = animation, o = can be switched off
GAME_PARTS = "Game parts"
_PARTS = [
    # id (also its voice file), name, icon, features, animation, what it does
    ("hello", "Hello", "👋", "pvsmo", "wag", "Pops up waving at the start of play and says hello."),
    ("where", "Peekaboo bush", None, "pvs", "jiggle",
     "Hides things in Peekaboo and asks where it is. Its sound plays as it covers up."),
    ("peekaboo", "Peekaboo!", "🙉", "vso", "jiggle", "Said (then its sound played) when the bush drops."),
    ("bye", "Bedtime moon", "🌙", "pvsm", "float", "The All done! screen when play time is up. Says bye twice."),
    ("star", "Bedtime stars", "⭐", "p", "float", "The stars twinkling around the moon at bedtime."),
    ("mystery", "Mystery sound", "❓", "so", "jiggle",
     "Plays behind the silhouette when a thing has no sound of its own. Built in: a chime."),
    ("reveal", "Ta-da sound", "🎉", "so", "jiggle", "Plays the moment a silhouette turns into its picture."),
    ("tap", "Tap sound", "🔔", "so", "jiggle",
     "The little sound for taps, drags and extra key presses. Built in: soft chimes."),
]
PARTS = [Item(None, name, icon, None, what, move, pid, False, GAME_PARTS, None, features)
         for pid, name, icon, features, move, what in _PARTS]


def has(item, feature):
    """Whether an object/part has a customizable feature: picture p, voice v, sound s, animation m, switch-off o."""
    return item.part is None or feature in item.part


NUMBER_WORDS = ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"]
BUILTIN += [Item(str(n % 10), word, None, None,
                 f"Count the dots together: {', '.join(str(i) for i in range(1, n + 1))}!",
                 "bounce", f"Number {n}", False, "Numbers", str(n))
            for n, word in enumerate(NUMBER_WORDS, 1)]
BUILTIN_IDS = {it.id for it in BUILTIN}
_DEFAULTS = {it.id: it for it in BUILTIN + PARTS}
EXTRA_WORDS = ("hello", "bye", "where", "peekaboo")  # also spoken by the voices

MOVES = [("hop", "Hop"), ("bounce", "Bounce"), ("wag", "Wiggle"), ("stomp", "Stomp"), ("swim", "Swim"),
         ("fly", "Fly"), ("buzz", "Buzz"), ("drive", "Drive"), ("swing", "Swing"), ("sway", "Sway"),
         ("float", "Float"), ("rock", "Rock"), ("jiggle", "Jiggle")]
MOVE_IDS = {m for m, _label in MOVES}


# ---------------------------------------------------------------- the data
_cache = {"mtime": None, "data": None}


def _load():
    """objects.json (re-read only when it changes - the start screen asks every frame)."""
    try:
        mtime = os.path.getmtime(DATA_PATH)
    except OSError:
        mtime = None
    if _cache["data"] is None or _cache["mtime"] != mtime:
        data = {"custom": [], "moves": {}, "disabled": [], "categories": [], "category_of": {}}
        try:
            with open(DATA_PATH, encoding="utf-8") as f:
                data.update(json.load(f))
        except (OSError, ValueError):
            pass
        _cache.update(mtime=mtime, data=data)
    return copy.deepcopy(_cache["data"])


def _save(data):
    os.makedirs(OBJECTS_DIR, exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    _cache.update(mtime=None, data=None)  # re-read next time (mtime can be too coarse to notice)


def load_items(enabled_only=True, include_parts=False):
    """Built-in objects (with any changed animation or category), then your new ones (then the game parts)."""
    data = _load()
    known = set(categories(data))
    items = []
    for it in BUILTIN:
        category = data["category_of"].get(it.id, it.category)
        items.append(it._replace(move=data["moves"].get(it.id, it.move),
                                 category=category if category in known else OUR_OWN))
    for c in data["custom"]:
        move = c.get("move") if c.get("move") in MOVE_IDS else "jiggle"
        category = c.get("category") if c.get("category") in known else OUR_OWN
        items.append(Item(None, c.get("word") or "New thing", None, None, None, move, c["id"], True, category))
    if enabled_only:
        items = [it for it in items if it.id not in data["disabled"]]
    if include_parts:
        items += load_parts(data)
    return items


def load_parts(data=None):
    """The game parts, with any changed animation (switched-off ones included - see is_enabled)."""
    data = data or _load()
    return [it._replace(move=data["moves"].get(it.id, it.move)) for it in PARTS]


def get_item(item_id):
    return next((it for it in load_items(enabled_only=False, include_parts=True) if it.id == item_id), None)


def is_enabled(item_id):
    return item_id not in _load()["disabled"]


def set_enabled(item_id, on):
    data = _load()
    disabled = [i for i in data["disabled"] if i != item_id]
    data["disabled"] = disabled if on else disabled + [item_id]
    _save(data)


def set_move(item_id, move):
    data = _load()
    defaults = {it.id: it for it in BUILTIN + PARTS}
    if item_id in defaults:
        default = defaults[item_id].move
        data["moves"].pop(item_id, None)
        if move != default:
            data["moves"][item_id] = move
    else:
        for c in data["custom"]:
            if c["id"] == item_id:
                c["move"] = move
    _save(data)


def set_word(item_id, word):
    data = _load()
    for c in data["custom"]:
        if c["id"] == item_id:
            c["word"] = word
    _save(data)


def add_custom(category=OUR_OWN):
    data = _load()
    n = 1 + max([int(c["id"].split("_")[1]) for c in data["custom"]] + [0])
    item_id = f"custom_{n}"
    data["custom"].append({"id": item_id, "word": "New thing", "move": "jiggle", "category": category})
    _save(data)
    return item_id


# ----------------------------------------------------------------- categories
def categories(data=None, include_parts=False):
    """The built-in categories, then yours, in order (then "Game parts", for the editor)."""
    data = data or _load()
    return (DEFAULT_CATEGORIES + [c for c in data["categories"] if c not in DEFAULT_CATEGORIES + [GAME_PARTS]]
            + ([GAME_PARTS] if include_parts else []))


def is_custom_category(name):
    return name not in DEFAULT_CATEGORIES and name != GAME_PARTS


def _unique(name, taken):
    name = name.strip()[:24] or "New category"
    base, n = name, 2
    while name in taken:
        name, n = f"{base} {n}", n + 1
    return name


def add_category(name):
    data = _load()
    name = _unique(name, categories(data, include_parts=True))
    data["categories"].append(name)
    _save(data)
    return name


def rename_category(old, new):
    """Rename one of your categories (moving its objects along). Returns the name actually used."""
    data = _load()
    if not is_custom_category(old) or old not in data["categories"]:
        return old
    new = _unique(new, [c for c in categories(data, include_parts=True) if c != old])
    data["categories"] = [new if c == old else c for c in data["categories"]]
    for c in data["custom"]:
        if c.get("category") == old:
            c["category"] = new
    data["category_of"] = {k: (new if v == old else v) for k, v in data["category_of"].items()}
    _save(data)
    return new


def delete_category(name):
    """Delete one of your categories; anything still in it moves to "Our own"."""
    data = _load()
    if not is_custom_category(name):
        return
    data["categories"] = [c for c in data["categories"] if c != name]
    for c in data["custom"]:
        if c.get("category") == name:
            c["category"] = OUR_OWN
    data["category_of"] = {k: v for k, v in data["category_of"].items() if v != name}
    _save(data)


def set_category(item_id, category):
    data = _load()
    if item_id in BUILTIN_IDS:
        default = next(it.category for it in BUILTIN if it.id == item_id)
        data["category_of"].pop(item_id, None)
        if category != default:
            data["category_of"][item_id] = category
    else:
        for c in data["custom"]:
            if c["id"] == item_id:
                c["category"] = category
    _save(data)


def delete_custom(item_id):
    data = _load()
    data["custom"] = [c for c in data["custom"] if c["id"] != item_id]
    data["disabled"] = [i for i in data["disabled"] if i != item_id]
    _save(data)
    for path in (drawing_path(item_id), our_voice_path(item_id), our_sfx_path(item_id)):
        if os.path.exists(path):
            os.remove(path)


# ------------------------------------------------------------ files per object
def drawing_path(item_id):
    return os.path.join(DRAWINGS_DIR, f"{item_id}.png")


def our_voice_path(item_id):
    return os.path.join(OUR_VOICE_DIR, f"{item_id}.wav")


def our_sfx_path(item_id):
    return os.path.join(OUR_SFX_DIR, f"{item_id}.wav")


def builtin_voice_path(item_id):
    return os.path.join(WORDS_DIR, f"{item_id}.wav")


def builtin_sfx_path(item_id):
    return os.path.join(SOUNDS_DIR, f"{item_id}.wav")


def load_drawing(item_id):
    """Your drawing, cropped to what you drew (None if there isn't one)."""
    path = drawing_path(item_id)
    if not os.path.exists(path):
        return None
    surf = pygame.image.load(path).convert_alpha()
    box = surf.get_bounding_rect()
    return surf.subsurface(box).copy() if box.w and box.h else None


def bush_art(w, h):
    """The built-in peekaboo bush."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    dark, mid, light = (46, 125, 50), (67, 160, 71), (102, 187, 106)
    rng = random.Random(7)  # same bush every time
    blobs = [(rng.uniform(0.22, 0.78) * w, rng.uniform(0.3, 0.6) * h, rng.uniform(0.15, 0.21) * w)
             for _ in range(14)]
    for x, y, r in blobs:
        pygame.draw.circle(surf, dark, (x, y + r * 0.08), r)
    pygame.draw.rect(surf, dark, (0, h * 0.5, w, h * 0.5), border_radius=int(h * 0.1))
    for x, y, r in blobs:
        pygame.draw.circle(surf, mid, (x, y), r * 0.9)
    pygame.draw.rect(surf, mid, (w * 0.02, h * 0.55, w * 0.96, h * 0.45), border_radius=int(h * 0.1))
    for x, y, r in blobs[::3]:
        pygame.draw.circle(surf, light, (x - r * 0.25, y - r * 0.3), r * 0.3)
    for x, y, _r in blobs[1::4]:  # little flowers
        for a in range(5):
            pygame.draw.circle(surf, (255, 235, 238),
                               (x + math.cos(a * 1.257) * w * 0.012, y + math.sin(a * 1.257) * w * 0.012), w * 0.012)
        pygame.draw.circle(surf, (255, 202, 40), (x, y), w * 0.01)
    return surf


_emoji_fonts = {}
_glyph_fonts = {}
GLYPH_COLORS = [(255, 82, 82), (255, 160, 40), (255, 214, 0), (90, 205, 90), (40, 170, 255), (140, 110, 255),
                (236, 90, 200), (0, 200, 190)]


def render_glyph(item, height):
    """A letter or number drawn big and colorful; numbers get that many dots underneath to count."""
    digits = item.glyph.isdigit()
    count = int(item.glyph) if digits else 0
    text_h = int(height * (0.68 if digits else 1.0))
    size = max(8, int(text_h * 1.15))
    if size not in _glyph_fonts:
        _glyph_fonts[size] = sys_font("arialroundedmtbold,comicsansms,arialblack,arial", size, bold=True)
    font = _glyph_fonts[size]
    n = ord(item.glyph[-1]) + len(item.glyph)
    color = GLYPH_COLORS[n % len(GLYPH_COLORS)]
    edge = tuple(int(v * 0.55) for v in color)
    main = font.render(item.glyph, True, color)
    outline = font.render(item.glyph, True, edge)
    box = main.get_bounding_rect()  # fonts leave space above and below; trim it
    main, outline = main.subsurface(box).copy(), outline.subsurface(box).copy()
    k = text_h / box.h
    main = pygame.transform.smoothscale(main, (max(1, int(box.w * k)), text_h))
    outline = pygame.transform.smoothscale(outline, main.get_size())
    r_dot = height * 0.055
    rows = (count + 4) // 5
    dots_h = int(rows * r_dot * 2.6) if count else 0
    w = max(main.get_width() + 12, int(min(count, 5) * r_dot * 2.6) + 4)
    surf = pygame.Surface((w, text_h + 12 + (dots_h + int(height * 0.04) if count else 0)), pygame.SRCALPHA)
    x = (w - main.get_width()) // 2
    for dx, dy in ((0, 0), (12, 0), (0, 12), (12, 12), (6, 0), (0, 6), (12, 6), (6, 12)):
        surf.blit(outline, (x + dx - 6, dy))
    surf.blit(main, (x, 6))
    for i in range(count):  # counting dots, rows of five
        row, col = divmod(i, 5)
        in_row = min(5, count - row * 5)
        cx = w / 2 + (col - (in_row - 1) / 2) * r_dot * 2.6
        cy = text_h + 12 + int(height * 0.04) + r_dot * 1.3 + row * r_dot * 2.6
        pygame.draw.circle(surf, edge, (cx, cy), r_dot)
        pygame.draw.circle(surf, color, (cx, cy), r_dot * 0.8)
    return surf


def object_art(item, height):
    """The object's picture (drawing if there is one, else its emoji or big letter/number), about `height` px tall."""
    drawing = load_drawing(item.id)
    if drawing is not None:
        w, h = drawing.get_size()
        k = min(height / h, height * 1.25 / w)
        return pygame.transform.smoothscale(drawing, (max(1, int(w * k)), max(1, int(h * k))))
    if item.glyph:
        return render_glyph(item, height)
    if item.id == "where":  # the bush is drawn, not an emoji
        return bush_art(int(height * 1.9), height)
    return render_emoji(item.emoji or "❓", height)


def emoji_file(emoji):
    """The Noto picture of an emoji: images/emoji/emoji_u1f436.png (tools/get_emoji.py fetches them)."""
    codes = [f"{ord(c):x}" for c in emoji if ord(c) != 0xFE0F]  # Noto names leave out the emoji-style marker
    return os.path.join(EMOJI_DIR, "emoji_u" + "_".join(codes) + ".png")


def render_emoji(emoji, height):
    """An emoji about `height` px tall: Windows' emoji font if there is one, else the Noto picture."""
    if os.path.exists(EMOJI_FONT):
        size = max(8, int(height / 1.1))
        if size not in _emoji_fonts:
            _emoji_fonts[size] = pygame.font.Font(EMOJI_FONT, size)
        return _emoji_fonts[size].render(emoji, True, (0, 0, 0))
    path = emoji_file(emoji)
    if not os.path.exists(path):
        path = emoji_file("❓")
    pic = pygame.image.load(path).convert_alpha()
    k = height * 0.92 / pic.get_height()  # the font's emoji fill about this much of their height
    return pygame.transform.smoothscale(pic, (max(1, int(pic.get_width() * k)), max(1, int(pic.get_height() * k))))
