# constants.py — Shared paths and application constants

import os
import sys

if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(__file__)

lib_path = os.path.join(base_path, "lib")
image_path = os.path.join(base_path, 'lib', 'img')

for root, dirs, files in os.walk(lib_path):
    os.environ["PATH"] += os.pathsep + root

sys.path.insert(0, lib_path)

APPLICATION_SLUG = "rdmt"
APP_NAME = "Red Dead Modding Tool"
APPDATA_FOLDER = os.path.join(os.getenv('APPDATA'), APP_NAME)
VERSION = "2.0.4"

# Style constants
COLOR_PRIMARY = "#b22222"
COLOR_PRIMARY_DARK = "#8b0000"
FONT_FAMILY = "Segoe UI"

GAME_FILES = {
    "index.bin", "RDR2.exe", "uninstall.exe", "amd_ags_x64.dll", "bink2w64.dll",
    "dxilconv7.dll", "ffx_fsr2_api_dx12_x64.dll", "ffx_fsr2_api_vk_x64.dll",
    "ffx_fsr2_api_x64.dll", "NvLowLatencyVk.dll", "nvngx_dlss.dll", "oo2core_5_win64.dll",
    "anim_0.rpf", "appdata0_update.rpf", "common_0.rpf", "data_0.rpf", "hd_0.rpf",
    "levels_0.rpf", "levels_1.rpf", "levels_2.rpf", "levels_3.rpf", "levels_4.rpf",
    "levels_5.rpf", "levels_6.rpf", "levels_7.rpf", "movies_0.rpf", "packs_0.rpf",
    "packs_1.rpf", "rowpack_0.rpf", "shaders_x64.rpf", "textures_0.rpf", "textures_1.rpf",
    "update_1.rpf", "update_2.rpf", "update_3.rpf", "update_4.rpf", "title.rgl", "steam_appid.txt",
    "EOSSDK-Win64-Shipping.dll", "PlayRDR2.exe", "steam_api64.dll", "installscript.vdf", "installscript_sdk.vdf"
}
