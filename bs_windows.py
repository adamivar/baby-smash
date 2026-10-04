"""Windows integration: blocking system shortcuts, accessibility pop-ups, the stuck
Windows key and touch feedback. Only imported on Windows (see bs_system)."""
import ctypes
import threading
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ---------------------------------------------------------------- key blocking
WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_SYSKEYDOWN, WM_QUIT = 0x0100, 0x0104, 0x0012
LLKHF_INJECTED, LLKHF_ALTDOWN = 0x10, 0x20
KEYEVENTF_KEYUP = 0x0002
VK_MASK = 0xE8  # unassigned key; tapping it stops a Windows-key release from opening Start
VK_TAB, VK_ESCAPE, VK_SPACE, VK_F4 = 0x09, 0x1B, 0x20, 0x73
VK_CONTROL, VK_LWIN, VK_RWIN, VK_APPS, VK_SLEEP = 0x11, 0x5B, 0x5C, 0x5D, 0x5F
# Browser, volume, media and "launch app" keys: 0xA6 - 0xB7
ALWAYS_BLOCKED = {VK_LWIN, VK_RWIN, VK_APPS, VK_SLEEP, *range(0xA6, 0xB8)}


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t]
user32.SetPropW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.HANDLE]
if hasattr(user32, "SetWindowFeedbackSetting"):  # Windows 8+
    user32.SetWindowFeedbackSetting.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.DWORD,
                                                wintypes.UINT, ctypes.c_void_p]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


def windows_key_down():
    return any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (VK_LWIN, VK_RWIN))


def release_windows_key():
    """Tell Windows the Windows key is up.

    Windows can end up believing the Windows key is still held - e.g. after the
    lock screen swallowed its release - and then every L becomes Win+L (lock).
    """
    user32.keybd_event(VK_MASK, 0, 0, 0)
    user32.keybd_event(VK_MASK, 0, KEYEVENTF_KEYUP, 0)
    for vk in (VK_LWIN, VK_RWIN):
        if user32.GetAsyncKeyState(vk) & 0x8000:
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


class KeyBlocker:
    """Low-level keyboard hook that swallows system shortcuts."""

    def __init__(self):
        self.blocked_presses = 0  # the game still reacts to swallowed keys
        self._thread_id = None
        self._proc = HOOKPROC(self._hook)  # keep a reference so it isn't GC'd
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        self._thread.join(timeout=2)

    def _hook(self, n_code, w_param, l_param):
        if n_code == 0:
            kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if kb.flags & LLKHF_INJECTED:  # our own release_windows_key() - let it through
                return user32.CallNextHookEx(None, n_code, w_param, l_param)
            vk = kb.vkCode
            alt = kb.flags & LLKHF_ALTDOWN
            ctrl = user32.GetAsyncKeyState(VK_CONTROL) & 0x8000
            if (vk in ALWAYS_BLOCKED
                    or (alt and vk in (VK_TAB, VK_ESCAPE, VK_F4, VK_SPACE))
                    or (ctrl and vk == VK_ESCAPE)):
                if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    self.blocked_presses += 1
                return 1
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _run(self):
        self._thread_id = kernel32.GetCurrentThreadId()
        hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0)
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        user32.UnhookWindowsHookEx(hook)


# ------------------------------------------- Sticky/Filter/Toggle Keys pop-ups
class _STICKYKEYS(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwFlags", wintypes.DWORD)]


class _FILTERKEYS(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwFlags", wintypes.DWORD),
                ("iWaitMSec", wintypes.DWORD), ("iDelayMSec", wintypes.DWORD),
                ("iRepeatMSec", wintypes.DWORD), ("iBounceMSec", wintypes.DWORD)]


HOTKEYACTIVE, FEATURE_ON = 0x04, 0x01
# (struct, SPI_GET*, SPI_SET*) for Sticky, Toggle and Filter Keys
_ACCESSIBILITY = [(_STICKYKEYS, 0x3A, 0x3B), (_STICKYKEYS, 0x34, 0x35), (_FILTERKEYS, 0x32, 0x33)]


class AccessibilityShortcuts:
    """Stops 'press Shift 5 times' style pop-ups; restores them afterwards.

    Changes are not written to the user profile, so a reboot also restores them.
    """

    def __init__(self):
        self._saved = []

    def disable(self):
        for struct, spi_get, spi_set in _ACCESSIBILITY:
            s = struct(cbSize=ctypes.sizeof(struct))
            if not user32.SystemParametersInfoW(spi_get, s.cbSize, ctypes.byref(s), 0):
                continue
            self._saved.append((spi_set, s))
            if not s.dwFlags & FEATURE_ON:  # leave it alone if the feature is actually in use
                off = struct.from_buffer_copy(s)
                off.dwFlags &= ~HOTKEYACTIVE
                user32.SystemParametersInfoW(spi_set, off.cbSize, ctypes.byref(off), 0)

    def restore(self):
        for spi_set, s in self._saved:
            user32.SystemParametersInfoW(spi_set, s.cbSize, ctypes.byref(s), 0)
        self._saved.clear()


# --------------------------------------------------------------------- window
def keep_on_top(hwnd):
    user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)  # HWND_TOPMOST, no move/size


def bring_back(hwnd):
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)


def disable_touch_feedback(hwnd):
    """No Windows touch circles, press-and-hold right-click or flicks on our window, so every tap lands instantly."""
    off = wintypes.BOOL(False)
    try:
        for feedback in range(1, 12):  # FEEDBACK_TOUCH_CONTACTVISUALIZATION .. FEEDBACK_GESTURE_PRESSANDTAP
            user32.SetWindowFeedbackSetting(wintypes.HWND(hwnd), feedback, 0, ctypes.sizeof(off), ctypes.byref(off))
    except AttributeError:
        pass
    # TABLET_DISABLE_PRESSANDHOLD | PENTAPFEEDBACK | PENBARRELFEEDBACK | TOUCHSWITCH | FLICKS | FLICKFALLBACKKEYS
    user32.SetPropW(wintypes.HWND(hwnd), "MicrosoftTabletPenServiceProperty",
                    wintypes.HANDLE(0x1 | 0x8 | 0x10 | 0x8000 | 0x10000 | 0x100000))
