[app]
title = Baby Smash
package.name = babysmash
package.domain = io.github.adamivar
source.dir = .
source.include_exts = py,pyw,wav,png,txt
source.exclude_dirs = tools, .github, bin, .buildozer, __pycache__, objects, sounds/our_voice, sounds/our_sfx, build, dist
source.exclude_patterns = settings.json, crash_log.txt, bs_windows.py, image_compare.png
version = 1.0.0
requirements = python3,pygame,android
p4a.bootstrap = sdl2
orientation = landscape
fullscreen = 1
icon.filename = %(source.dir)s/images/emoji/emoji_u1f9f8.png
android.permissions = RECORD_AUDIO
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.ndk = 25b
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
