# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['askGeminiPrompto.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('build_web/index.html', 'build_web'),
        ('build_web/static', 'build_web/static'),
        ('build_web/fonts', 'build_web/fonts'),
        ('build_web/asset-manifest.json', 'build_web'),
        ('build_web/favicon.png', 'build_web'),
        ('prompto.dys', '.'),
        ('GeminiKey.txt', '.'),
        ('assets/prompto.png', 'assets'),  # Icône et logo de l'application
    ],
    hiddenimports=[
        'eel',
        'google.genai',
        'reportlab',
        'markdown',
        'gevent',
        'gevent.socket',
        'gevent.ssl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PromptoDYS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # ⚠️ UPX désactivé pour réduire faux positifs antivirus
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Mode fenêtré pour version finale (pas de console)
    # version='version_info.txt',  # Métadonnées Windows pour authentification (temporairement désactivé)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)