"""Baby Smash - a calm first-words game for keyboard + touchscreen, with real voices.

Opens on a start screen for grown-ups (night/day look, game mode, voices, play
time, recording your own voice for each word, and Objects: draw any object, add
new ones with their own name, recordings and animation). Press Play, and:

  Who's that?  a thing appears as a shaking silhouette while its real sound plays,
               then it's revealed as a voice names it, and the sound plays again.
               Revealed things move in character - frogs hop, fish swim, cars drive.
  Peekaboo     an animal hides behind a bush; any tap or key reveals it.

Each letter key always brings the same thing (D = dog, C = cat...).

GROWN-UP SECRET WORDS while playing (just type them):
    quit  - back to the start screen
    peek  - switch between Who's that? and Peekaboo
    more  - add 5 more minutes after the "All done!" bedtime screen
No keyboard (phone, tablet)? Tap the four corners in order - top-left, top-right,
bottom-right, bottom-left - within 5 seconds to get back to the start screen.

(Ctrl+Alt+Del always works too - Windows never lets apps block it.)

While playing it blocks: Windows key, Alt+Tab, Alt+Esc, Alt+F4, Alt+Space,
Ctrl+Esc, Ctrl+Shift+Esc, the menu key, browser/mail/media/volume/sleep keys,
and the Sticky/Filter/Toggle Keys pop-ups. Everything is restored afterwards.

Modules: bs_game (the game), bs_objects (the objects + your changes to them),
bs_menu (start screen + voice recording), bs_editor (the Objects pages),
bs_audio (sounds, microphone), bs_system (display; Windows key blocking lives in bs_windows),
bs_paths (where the game's files and your family's files live).
Sounds: sounds/ (tools/get_sounds.py fetches them; credits in sounds/CREDITS.txt).
"""
import ctypes
import os

os.environ["SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS"] = "0"
import pygame  # noqa: E402

from bs_audio import load_sound_effects, load_voices  # noqa: E402
from bs_log import start_logging  # noqa: E402
from bs_game import Game  # noqa: E402
from bs_menu import Menu, load_settings  # noqa: E402
from bs_objects import BUILTIN, EXTRA_WORDS, is_enabled, load_items, load_parts  # noqa: E402
from bs_paths import ANDROID  # noqa: E402
from bs_system import (AccessibilityShortcuts, KeyBlocker, ask_for_microphone, bring_back,  # noqa: E402
                       disable_touch_feedback, keep_on_top, open_screen, release_windows_key, windows_key_down)

RENDER_HEIGHT = 1080  # draw at this many lines and let the GPU scale up (big speed win on hi-res screens)
SECRET_WORDS = ("quit", "peek", "more")
CORNERS = ("top-left", "top-right", "bottom-right", "bottom-left")  # tapped in this order = quit, without a keyboard
CORNER_SIZE = 0.12  # of the screen's short side
CORNER_SECONDS = 5.0


def main():
    start_logging()  # errors go to crash_log.txt (pythonw has no console)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    pygame.mixer.set_num_channels(16)
    pygame.mixer.set_reserved(1)  # channel 0 = voice
    screen, vsync = open_screen(RENDER_HEIGHT)
    pygame.display.set_caption("Baby Smash")
    unused = ("TEXTEDITING", "MOUSEWHEEL", "MULTIGESTURE") + (() if ANDROID else ("TEXTINPUT",))
    for kind in unused:  # (Android's on-screen keyboard types with TEXTINPUT)
        if hasattr(pygame, kind):
            pygame.event.set_blocked(getattr(pygame, kind))
    if ANDROID:
        pygame.key.stop_text_input()  # no on-screen keyboard until a grown-up taps a name box
        ask_for_microphone()
    hwnd = pygame.display.get_wm_info().get("window")
    keep_on_top(hwnd)
    disable_touch_feedback(hwnd)

    settings = load_settings()
    menu = Menu(screen, settings)
    try:
        while menu.run() == "play":
            play(screen, hwnd, vsync, settings)
    finally:
        if windows_key_down():  # never leave the PC thinking the Windows key is held
            release_windows_key()
        pygame.quit()


def play(screen, hwnd, vsync, settings):
    """One play session, with system keys blocked, until a grown-up types quit."""
    items = load_items() or BUILTIN  # the objects switched on (all of them if a grown-up switched off everything)
    chosen = settings.get("categories") or []  # [] = every category
    if chosen:
        items = [it for it in items if it.category in chosen] or items  # (chosen categories might be empty)
    ids = [it.id for it in items]
    parts = load_parts()  # hello, peekaboo bush, bedtime moon... with your pictures, recordings, animations
    part_ids = [p.id for p in parts]
    voices = load_voices(ids + list(EXTRA_WORDS), prefer_ours=settings["voice"] == "ours")
    game = Game(screen, items, voices, load_sound_effects(ids + part_ids), settings,
                parts=parts, parts_on={pid: is_enabled(pid) for pid in part_ids})
    pygame.mouse.set_visible(False)
    pygame.event.clear()
    shortcuts = AccessibilityShortcuts()
    blocker = KeyBlocker()
    shortcuts.disable()
    blocker.start()  # after loading: the key hook needs a responsive app
    try:
        run(screen, blocker, hwnd, game, vsync)
    finally:
        blocker.stop()
        shortcuts.restore()
        if windows_key_down():
            release_windows_key()
        pygame.mixer.stop()


def run(screen, blocker, hwnd, game, vsync=False):
    w, h = screen.get_size()
    clock = pygame.time.Clock()
    typed = ""
    seen_blocked = 0
    focus_timer = 0.0
    win_held = 0.0
    had_focus = True
    longest = max(len(word) for word in SECRET_WORDS)
    corners = []  # (time, corner) of recent corner taps
    clock_s = 0.0
    while True:
        dt = min(clock.tick(120 if vsync else 60) / 1000, 0.1)  # with vsync the display sets the pace
        clock_s += dt
        drags = {}  # finger -> latest position; a sliding palm sends dozens of moves per frame
        for e in pygame.event.get():  # pygame.QUIT is deliberately ignored
            if e.type == pygame.KEYDOWN:
                ch = e.unicode
                if ch and ch.isprintable() and not ch.isspace():
                    typed = (typed + ch.lower())[-longest:]
                    if typed.endswith("quit"):
                        return
                    if typed.endswith("peek"):
                        typed = ""
                        game.toggle_mode()
                        continue
                    if typed.endswith("more"):
                        typed = ""
                        game.add_time()
                        continue
                game.press(ch)
            elif e.type == pygame.FINGERDOWN:
                if corner_quit(corners, corner_of(e.x * w, e.y * h, w, h), clock_s):
                    return
                game.tap(e.x * w, e.y * h)
            elif e.type == pygame.FINGERMOTION:
                drags[e.finger_id] = (e.x * w, e.y * h)
            elif e.type == pygame.MOUSEBUTTONDOWN and not getattr(e, "touch", False):
                if corner_quit(corners, corner_of(*e.pos, w, h), clock_s):
                    return
                game.tap(*e.pos)
            elif e.type == pygame.MOUSEMOTION and e.buttons[0] and not getattr(e, "touch", False):
                drags["mouse"] = e.pos
        for x, y in drags.values():
            game.drag(x, y)

        # Swallowed system keys (Windows key etc.) still count as a press.
        blocked = blocker.blocked_presses
        if blocked != seen_blocked:
            game.press("")
        seen_blocked = blocked

        # The Windows key is blocked, so if Windows thinks it's held for over a
        # second (or right after we get focus back, e.g. from the lock screen),
        # it's stuck - release it so L doesn't turn into Win+L (lock).
        has_focus = pygame.key.get_focused()
        win_held = win_held + dt if windows_key_down() else 0.0
        if win_held > 1.0 or (has_focus and not had_focus and windows_key_down()):
            release_windows_key()
            win_held = 0.0
        had_focus = has_focus

        # If something steals focus, grab it back.
        focus_timer += dt
        if focus_timer > 1:
            focus_timer = 0
            if not has_focus:
                bring_back(hwnd)

        game.update(dt)
        game.draw()


def corner_of(x, y, w, h):
    """Which corner (if any) a tap landed in."""
    size = min(w, h) * CORNER_SIZE
    side = "left" if x < size else "right" if x > w - size else None
    end = "top" if y < size else "bottom" if y > h - size else None
    return f"{end}-{side}" if side and end else None


def corner_quit(corners, corner, now):
    """Remember a tap; True once the four corners were tapped in order within CORNER_SECONDS."""
    if corner is None:
        return False
    corners[:] = [(t, c) for t, c in corners if now - t < CORNER_SECONDS]
    expected = CORNERS[len(corners)] if len(corners) < len(CORNERS) else None
    if corner != expected:  # out of order: start again (this tap may be a new first corner)
        corners[:] = []
        if corner != CORNERS[0]:
            return False
    corners.append((now, corner))
    return len(corners) == len(CORNERS)


if __name__ == "__main__":
    main()
