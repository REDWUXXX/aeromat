#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打包脚本 - 航材库存管理系统 v2.0
"""

import PyInstaller.__main__
import os
import sys
import io
# 修复Windows中文编码问题
if sys.platform == 'win32':
      sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
      sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
os.chdir(os.path.dirname(os.path.abspath(__file__)))

params = [
    'main.py',
    '--onefile',
    '--windowed',
    '--name=areomat_v2.0',
    '--hidden-import=pandas',
    '--hidden-import=sqlite3',
    '--hidden-import=tkinter',
    '--collect-all=pandas',
    '--distpath=./dist',
    '--workpath=./build',
    '--specpath=./',
]

print("=" * 60)
print("航材库存管理系统 v2.0 - 打包脚本")
print("=" * 60)
print("\n开始打包...")
print(f"参数: {' '.join(params)}\n")

PyInstaller.__main__.run(params)

print("\n" + "=" * 60)
print("✅ 打包完成！")
print(f"📁 exe文件位置: {os.path.abspath('./dist/areomat_v2.0.exe')}")
print("=" * 60)
