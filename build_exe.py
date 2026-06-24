#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import PyInstaller.__main__
import os
import sys

if sys.platform != 'win32':
    import locale
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

os.chdir(os.path.dirname(os.path.abspath(__file__)))

params = [
    'main.py',
    '--onefile',
    '--windowed',
    '--name=AeroMat_v3.0',
    '--hidden-import=pandas',
    '--hidden-import=sqlite3',
    '--hidden-import=tkinter',
    '--hidden-import=PIL',
    '--hidden-import=shutil',
    '--hidden-import=hashlib',
    '--collect-all=pandas',
    '--collect-all=PIL',
    '--distpath=./dist',
    '--workpath=./build',
    '--specpath=./',
]

print("=" * 60)
print("AeroMat v3.0 - Build Script")
print("=" * 60)
print("\nBuilding...\n")

PyInstaller.__main__.run(params)

print("\n" + "=" * 60)
print("Build complete!")
print("Location: " + os.path.abspath("./dist/AeroMat_v3.0.exe"))
print("=" * 60)
