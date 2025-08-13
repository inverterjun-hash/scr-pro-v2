[app]
title = SCR Calculator Pro v2
package.name = scrcalcprov2
package.domain = com.gridforming
source.dir = app
source.include_exts = py,kv,html,json,csv,txt,md
version = 2.0.0
orientation = all
fullscreen = 0
log_level = 2

requirements = python3,kivy,kivymd,kivy_garden.matplotlib,matplotlib,numpy

android.api = 34
android.minapi = 26
android.arch = arm64-v8a
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

[buildozer]
log_level = 2
warn_on_root = 1
