# config.py — Configuration management, migration, safe mods, and caching

import os
import json
import shutil

from constants import APPDATA_FOLDER
from utils import encrypt_text, decrypt_text


# --- Config Paths ---

def get_config_path():
    """Return the path to the configuration file in a user-writable location."""
    config_folder = os.path.join(APPDATA_FOLDER, 'config')
    os.makedirs(config_folder, exist_ok=True)
    return os.path.join(config_folder, 'rdmt.ini')


def get_key_path():
    """Return the path to the key.dat file in a user-writable location."""
    app_folder = os.path.join(APPDATA_FOLDER, 'keys')
    os.makedirs(app_folder, exist_ok=True)
    return os.path.join(app_folder, 'api.key')


# --- Config Load/Save ---

def load_config():
    """Load the configuration from rdmt.ini, decrypting the API key if present."""
    config_path = get_config_path()
    key_path = get_key_path()
    default_config = {"path": None, "theme": "Dark", "api_key": None}

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as file:
                lines = file.readlines()

            config = default_config.copy()
            for line in lines:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"')
                if key in config:
                    config[key] = value

            if os.path.exists(key_path):
                try:
                    with open(key_path, 'r') as key_file:
                        encrypted_key = key_file.read().strip()
                        config["api_key"] = decrypt_text(encrypted_key)
                except Exception as e:
                    print(f"Error decrypting API key: {e}")
                    config["api_key"] = None

            if config["path"]:
                if not config["path"].lower().endswith("\\lml"):
                    config["path"] = os.path.join(config["path"], "lml")

            if not config["path"] or not os.path.isdir(config["path"]) or not os.access(config["path"], os.R_OK):
                print("Invalid LML folder path in configuration.")
                raise ValueError("Invalid LML folder path")

            return config
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            print(f"Error loading configuration: {e}")
    else:
        print("Configuration file not found. Creating a new one.")

    save_config()
    return default_config


def save_config(path=None, theme=None, api_key=None):
    """Save the configuration to rdmt.ini and the API key to key.dat."""
    config_path = get_config_path()
    key_path = get_key_path()

    current_config = {"path": None, "theme": "Dark"}
    if os.path.exists(config_path):
        with open(config_path, 'r') as file:
            lines = file.readlines()
        for line in lines:
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"')
            if key in current_config:
                current_config[key] = value

    if path is not None:
        current_config["path"] = path
    if theme is not None:
        current_config["theme"] = theme

    with open(config_path, 'w') as file:
        for key, value in current_config.items():
            value_str = value if value is not None else ""
            file.write(f'{key}="{value_str}"\n')

    if api_key is not None:
        try:
            encrypted_key = encrypt_text(api_key)
            with open(key_path, 'w') as key_file:
                key_file.write(encrypted_key)
        except Exception as e:
            print(f"Error encrypting API key: {e}")


# --- Migration ---

def migrate_old_config():
    """Migrate the old configuration from the 'LML Mod Conflict Checker Tool' folder."""
    appdata_dir = os.getenv('APPDATA')
    old_folder = os.path.join(appdata_dir, 'LML Mod Conflict Checker Tool')
    new_folder = os.path.join(appdata_dir, 'Red Dead Modding Tool')
    old_config_path = os.path.join(old_folder, 'lmcct.dat')
    new_config_path = os.path.join(new_folder, 'config', 'rdmt.ini')

    if os.path.exists(old_folder) and not os.path.exists(new_folder):
        try:
            os.makedirs(os.path.dirname(new_config_path), exist_ok=True)

            if os.path.isfile(old_config_path):
                try:
                    with open(old_config_path, 'r', encoding='utf-8') as old_file:
                        old_lines = old_file.readlines()

                    old_config = {}
                    for line in old_lines:
                        key, _, value = line.partition('=')
                        old_config[key.strip()] = value.strip().strip('"')

                    path = old_config.get("path")
                    if path:
                        path = path.strip('"')
                        if os.path.basename(path.lower()) == "lml":
                            path = os.path.dirname(path)
                        path = path if os.path.isdir(path) else None

                    converted_config = {
                        "path": path,
                        "theme": old_config.get("theme", "Dark"),
                        "api_key": None
                    }

                    with open(new_config_path, 'w', encoding='utf-8') as new_file:
                        for key, value in converted_config.items():
                            if key == "api_key" and value:
                                value_str = f'"{encrypt_text(value)}"'
                            else:
                                value_str = f'"{value}"' if value is not None else '""'
                            new_file.write(f'{key}={value_str}\n')

                    print(f"Converted configuration saved to: {new_config_path}")
                except Exception as e:
                    print(f"Error converting configuration: {e}")

            for item in os.listdir(old_folder):
                old_path = os.path.join(old_folder, item)
                new_path = os.path.join(new_folder, item)
                if os.path.isfile(old_path) and item != 'lmcct.dat':
                    shutil.move(old_path, new_path)
                elif os.path.isdir(old_path):
                    shutil.move(old_path, new_folder)
            print(f"Configuration migrated from '{old_folder}' to '{new_folder}'")

            shutil.rmtree(old_folder)
            print(f"Deleted old configuration folder: '{old_folder}'")
        except Exception as e:
            print(f"Error migrating configuration: {e}")
    elif os.path.exists(new_folder):
        if os.path.exists(old_folder):
            shutil.rmtree(old_folder)
    else:
        print("No old configuration folder found. Skipping migration.")


# --- Safe Mods ---

def get_safe_mods_path():
    """Return the path to the safe mods exclusion list file."""
    config_folder = os.path.join(APPDATA_FOLDER, 'config')
    os.makedirs(config_folder, exist_ok=True)
    return os.path.join(config_folder, 'safe_mods.json')


def load_safe_mods():
    """Load the list of mods marked as safe from conflicts."""
    safe_path = get_safe_mods_path()
    if os.path.exists(safe_path):
        try:
            with open(safe_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error loading safe mods list: {e}")
    return set()


def save_safe_mods(safe_mods):
    """Save the list of mods marked as safe from conflicts."""
    safe_path = get_safe_mods_path()
    try:
        with open(safe_path, 'w', encoding='utf-8') as f:
            json.dump(sorted(list(safe_mods)), f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving safe mods list: {e}")


# --- Cache ---

def get_cache_path(category):
    """Get the path for the tracked mods cache file in AppData."""
    cache_folder = os.path.join(APPDATA_FOLDER, 'cache')
    os.makedirs(cache_folder, exist_ok=True)
    return os.path.join(cache_folder, f'{category}.cache')


def load_cache(category):
    """Load the tracked mods cache from the cache file."""
    cache_path = get_cache_path(category)
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}
    return {}


def save_cache(cache, category):
    """Save the tracked mods cache to the cache file."""
    cache_path = get_cache_path(category)
    with open(cache_path, 'w', encoding='utf-8') as file:
        json.dump(cache, file, ensure_ascii=False, indent=4)


def clean_cache():
    """Delete the 'cache' folder and its contents."""
    cache_folder = os.path.join(APPDATA_FOLDER, 'cache')
    try:
        if os.path.exists(cache_folder):
            shutil.rmtree(cache_folder)
            print(f"Cache folder '{cache_folder}' has been successfully deleted.")
        else:
            print(f"Cache folder '{cache_folder}' does not exist.")
    except Exception as e:
        print(f"Failed to delete the cache folder: {e}")


def update_clean_cache_button_state(clean_cache_button):
    """Enable or disable the clean cache button based on the presence of the cache folder."""
    cache_folder = os.path.join(APPDATA_FOLDER, 'cache')
    if os.path.exists(cache_folder) and os.listdir(cache_folder):
        clean_cache_button.configure(state="normal")
    else:
        clean_cache_button.configure(state="disabled")
