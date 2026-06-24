#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打包脚本 - 北京维护中心乘务航材管理 v3.0
"""

import PyInstaller.__main__
import os

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
print("北京维护中心乘务航材管理 v3.0 - 打包脚本")
print("=" * 60)
print("\n开始打包...\n")

PyInstaller.__main__.run(params)

print("\n" + "=" * 60)
print("✅ 打包完成！")
print(f"📁 exe文件位置: {os.path.abspath('./dist/AeroMat_v3.0.exe')}")
print("=" * 60)
