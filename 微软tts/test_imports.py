#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

print("Python version:", sys.version)
print("Python executable:", sys.executable)
print("Current directory:", os.getcwd())

try:
    import asyncio
    print("asyncio imported successfully")
except ImportError as e:
    print("asyncio import failed:", e)

try:
    from PySide6.QtWidgets import QApplication
    print("PySide6 imported successfully")
except ImportError as e:
    print("PySide6 import failed:", e)

try:
    import edge_tts
    print("edge_tts imported successfully")
except ImportError as e:
    print("edge_tts import failed:", e)

print("Test completed")