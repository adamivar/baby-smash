"""Download the Noto emoji pictures the game needs where Windows' emoji font isn't there (Android).

Re-run any time (after adding a built-in object): files already downloaded are skipped.
Output: ../images/emoji/emoji_u<code>.png (512 px) and ../images/emoji/LICENSE.txt
Noto Emoji by Google - Apache License 2.0 - https://github.com/googlefonts/noto-emoji
"""
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
os.environ["SDL_VIDEODRIVER"] = "dummy"
import bs_menu  # noqa: E402
import bs_objects  # noqa: E402

URL = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/2D/png/512/{}"
LICENSE = ("These pictures are from Noto Emoji by Google (https://github.com/googlefonts/noto-emoji),\n"
           "licensed under the Apache License 2.0: https://www.apache.org/licenses/LICENSE-2.0\n")


def main():
    emoji = {it.emoji for it in bs_objects.BUILTIN + bs_objects.PARTS if it.emoji}
    emoji |= {e for e, _say in bs_menu.EXTRA_PROMPTS.values()} | {"❓"}
    os.makedirs(bs_objects.EMOJI_DIR, exist_ok=True)
    for e in sorted(emoji):
        dest = bs_objects.emoji_file(e)
        if not os.path.exists(dest):
            with urllib.request.urlopen(URL.format(os.path.basename(dest)), timeout=60) as r:
                data = r.read()
            with open(dest, "wb") as f:
                f.write(data)
            print(f"{os.path.basename(dest):28} {len(data) // 1024} KB")
    with open(os.path.join(bs_objects.EMOJI_DIR, "LICENSE.txt"), "w", encoding="utf-8") as f:
        f.write(LICENSE)
    print(f"{len(emoji)} emoji in {bs_objects.EMOJI_DIR}")


if __name__ == "__main__":
    main()
