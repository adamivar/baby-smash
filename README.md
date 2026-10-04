# Baby Smash

A calm, full-screen first-words game for babies and toddlers (made for a 15-month-old) on a
Windows PC with a keyboard and touchscreen, or an Android phone or tablet. Mash the keys or
slap the screen and something friendly happens - and the little one can't accidentally escape
to the desktop.

## Download

Get the latest version from [Releases](https://github.com/adamivar/baby-smash/releases/latest):

- **Windows:** `BabySmash-vX.exe` - just run it. It isn't signed, so SmartScreen may warn:
  click *More info*, then *Run anyway*. Your recordings, drawings and settings are kept in
  `%LOCALAPPDATA%\Baby Smash`.
- **Android:** `BabySmash-vX.apk` - open it on the phone or tablet and allow *Install unknown
  apps* for your browser when asked. It plays in landscape.

## What it does

- **Who's that?** A thing appears as a shaking silhouette while its real sound plays (a dog
  barking, a cow mooing), then it's revealed as a real human voice says its name, and the sound
  plays again. Revealed things move in character: frogs hop, fish swim, cars drive.
- **Peekaboo** An animal hides behind a bush; any tap or key reveals it.
- **100 built-in things** in categories (people, animals, food, vehicles, body parts, everyday
  things like cup, bath and teddy, letters A-Z, numbers 1-10 with counting dots and chimes,
  and more). Each letter/number key always brings the
  same thing; pressing it again alternates with the letter itself (A: Apple, then "A").
- **Night (default) or day look**, a gentle 10-minute play time that ends on a calm
  "All done!" moon, and small "Say: ..." tips for the grown-up playing along.

### For grown-ups (start screen)

- Choose the look, game, play time and which categories to play with.
- **Record your own voices** for every word - babies respond best to their own family.
- **Objects editor:** draw any object with a simple paint palette, add new ones (name,
  recorded name, recorded sound, animation from a preset list), organise them in categories,
  switch any off. **Game parts** (the hello wave, peekaboo bush, bedtime moon, tap sound...)
  can be customised the same way.

Your recordings, drawings and settings are kept locally in `sounds/our_voice/`,
`sounds/our_sfx/`, `objects/` and `settings.json` (not part of this repository).

### Toddler-proofing

While playing, it blocks the Windows key, Alt+Tab, Alt+F4, Ctrl+Esc, Task Manager's shortcut,
browser/media/volume keys and the Sticky/Filter Keys pop-ups, keeps itself on top, and
turns off Windows touch gestures inside its window. Everything is restored when you leave.
Ctrl+Alt+Del always works (Windows doesn't let apps block it).

**On Android** the home and recent-apps buttons can't be blocked by an app. Turn on *App
pinning* (Settings > Security > App pinning, or search the settings for "pin"), then pin the
game before handing it over; unpin by holding Back and Overview (or swiping up and holding).

**Grown-up secret words** - just type them while playing:

| Type | What it does |
|------|--------------|
| `quit` | back to the start screen |
| `peek` | switch between Who's that? and Peekaboo |
| `more` | 5 more minutes after the bedtime screen |

No keyboard? **Tap the four corners clockwise, starting top-left** (top-left, top-right,
bottom-right, bottom-left) within 5 seconds to get back to the start screen.

## Running it

Windows 10/11 and Python 3.10+.

```
pip install -r requirements.txt
pythonw baby_smash.pyw
```

If something goes wrong, details are written to `crash_log.txt` next to the game (the .exe
writes it to `%LOCALAPPDATA%\Baby Smash`).

`tools/get_sounds.py` re-downloads and processes the built-in recordings (they're already
included in `sounds/`), and `tools/get_emoji.py` the emoji pictures used on Android (in
`images/emoji/`).

**Building the downloads:** pushing a tag like `v1.0.0` makes GitHub Actions
(`.github/workflows/release.yml`) build the .exe (PyInstaller) and the .apk (Buildozer,
`buildozer.spec`; `main.py` is the Android entry point) and publish them as a release.

## Code

| File | What's in it |
|------|--------------|
| `baby_smash.pyw` | start-up, the play loop, secret words |
| `bs_game.py` | the game: silhouettes, reveals, animations, peekaboo, bedtime |
| `bs_objects.py` | the objects, categories and game parts, plus your changes to them |
| `bs_menu.py` | the start screen and voice recording page |
| `bs_editor.py` | the Objects editor (drawing, recording, animations, categories) |
| `bs_audio.py` | sounds, chimes, microphone recording |
| `bs_system.py` | the display, and the toddler-proofing each system allows |
| `bs_windows.py` | Windows key blocking, accessibility pop-ups, touch feedback |
| `bs_paths.py` | where the game's files and your family's files live |
| `bs_log.py` | error log |

## License

The code is released under the [MIT License](LICENSE). The recordings in `sounds/` are not
covered by it - each keeps its own license, listed in [`sounds/CREDITS.txt`](sounds/CREDITS.txt).
The pictures in `images/emoji/` are Noto Emoji (Apache License 2.0).

## Credits

Pictures are Microsoft's Segoe UI Emoji font (built into Windows); on Android they're
[Noto Emoji](https://github.com/googlefonts/noto-emoji) by Google. Real-world sound effects
come from [BigSoundBank](https://bigsoundbank.com) (CC0) and Wikimedia Commons; spoken words
come from [Lingua Libre](https://lingualibre.org) and Wiktionary via Wikimedia Commons. Each
recording's author and license (CC0, public domain, CC BY 4.0, CC BY-SA 3.0/4.0) is listed in
[`sounds/CREDITS.txt`](sounds/CREDITS.txt).
