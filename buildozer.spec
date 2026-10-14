[app]
title = Pocket Calculator
package.name = pocketcalculatormv82p4sp
package.domain = app.lovable
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt,ttf
version = 0.1
requirements = python3,kivy==2.3.0
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
orientation = portrait
fullscreen = 0
android.presplash_color = #FFFFFF
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.accept_sdk_license = True
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 0
