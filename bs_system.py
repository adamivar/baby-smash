"""The system around the game: the fullscreen display everywhere, plus the toddler-proofing
that only Windows allows (bs_windows). On Android those parts do nothing - use Android's
app pinning instead (see README)."""
import pygame

from bs_paths import ANDROID, WINDOWS

if WINDOWS:
    from bs_windows import (AccessibilityShortcuts, KeyBlocker, bring_back,  # noqa: F401
                            disable_touch_feedback, keep_on_top, release_windows_key, windows_key_down)
else:
    class KeyBlocker:
        blocked_presses = 0

        def start(self):
            pass

        def stop(self):
            pass

    class AccessibilityShortcuts:
        def disable(self):
            pass

        def restore(self):
            pass

    def windows_key_down():
        return False

    def release_windows_key():
        pass

    def keep_on_top(_hwnd):
        pass

    def bring_back(_hwnd):
        pass

    def disable_touch_feedback(_hwnd):
        pass


def ask_for_microphone():
    """Android asks the grown-up once whether the game may use the microphone (for recording voices)."""
    if ANDROID:
        try:
            from android.permissions import Permission, request_permissions
            request_permissions([Permission.RECORD_AUDIO])
        except Exception:
            pass


def open_screen(render_height):
    """Fullscreen, drawn at render_height and scaled up by the GPU with vsync.

    On a high-res screen (e.g. a Surface at 2736x1824) drawing every pixel on the CPU
    is the slowest part of each frame; this cuts it ~3x. Returns (screen, vsync_on).
    """
    dw, dh = pygame.display.get_desktop_sizes()[0]
    if ANDROID:  # the app is landscape-only, whichever way the phone reports its size
        dw, dh = max(dw, dh), min(dw, dh)
    if dh > render_height:
        size = (round(render_height * dw / dh), render_height)
        for vsync in (1, 0):
            try:
                return pygame.display.set_mode(size, pygame.FULLSCREEN | pygame.SCALED, vsync=vsync), bool(vsync)
            except pygame.error:
                pass
    return pygame.display.set_mode((0, 0), pygame.FULLSCREEN), False
