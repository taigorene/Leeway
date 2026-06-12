"""Empacotamento do Leeway.app via py2app (bundle nativo, ícone no Dock = Leeway,
LSUIElement honrado → só barra de menus, sem ícone no Dock).

    python setup.py py2app
"""

import sys

sys.path.insert(0, "src")

from setuptools import setup

setup(
    app=["app_main.py"],
    name="Leeway",
    options={
        "py2app": {
            "iconfile": "assets/AppIcon.icns",
            "packages": ["rumps", "leeway"],
            "plist": {
                "CFBundleName": "Leeway",
                "CFBundleDisplayName": "Leeway",
                "CFBundleIdentifier": "app.leeway",
                "CFBundleVersion": "0.1.0",
                "CFBundleShortVersionString": "0.1.0",
                "LSUIElement": True,
                "LSMinimumSystemVersion": "13.0",
            },
        }
    },
    setup_requires=["py2app"],
)
