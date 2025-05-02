# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = [('static', 'static'), ('templates', 'templates'), ('.env', '.'), ('data.db', '.'), ('log', 'log'), ('server.py', '.')]
hiddenimports = ['sqlite3', 'netifaces', 'requests', 'flask', 'flask_sqlalchemy', 'flask_login', 'werkzeug.security', 'jinja2', 'markupsafe', 'itsdangerous', 'click', 'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets']
datas += collect_data_files('python-dotenv')
hiddenimports += collect_submodules('scripts')


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
    excludes=['pkg_resources', 'jaraco', 'backports'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='vote_system',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Projects\\vote_system\\static\\favicon.ico'],
)
