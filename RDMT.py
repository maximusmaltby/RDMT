# --- 1. Imports and Constants ---

import os
import re
import sys
import uuid
import json
import time
import toml
import base64
import string
import shutil
import winreg
import zipfile
import difflib
import requests
import patoolib
import threading
import win32pipe
import win32file
import subprocess
import webbrowser
import customtkinter as ctk
import xml.etree.ElementTree as ET

from CTkListbox import *
from CTkToolTip import *
from pathlib import Path
from xml.dom import minidom
from tkinter import filedialog
from PIL import Image, ImageTk
from customtkinter import CTkImage
from websocket import WebSocketApp
from difflib import SequenceMatcher
from collections import defaultdict
from tklinenums import TkLineNumbers
from cryptography.fernet import Fernet
from CTkMessagebox import CTkMessagebox
from datetime import datetime, timedelta, timezone

if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(__file__)
    
lib_path = os.path.join(base_path, "lib")
image_path = os.path.join(base_path, 'lib', 'img')

for root, dirs, files in os.walk(lib_path):
    os.environ["PATH"] += os.pathsep + root
    
sys.path.insert(0, lib_path)
 
application_slug = "rdmt"


# --- 2. Utility Functions ---

def migrate_old_config():
    """Migrate the old configuration from the 'LML Mod Conflict Checker Tool' folder. If lmcct.dat exists, convert it to rdmt.ini and store it in the new 'Red Dead Modding Tool' folder."""
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

def load_image(filename, width, height):
    try:
        img_path = os.path.join(image_path, filename)
        pil_image = Image.open(img_path).resize((width, height), Image.LANCZOS)
        return CTkImage(pil_image, size=(width, height))
    except FileNotFoundError:
        print(f"Error: Image file {filename} not found in {image_path}.")
        return None

def browse_folder(entry):
    folder_path = filedialog.askdirectory(title="Select your RDR2 folder")
    if folder_path:
        entry.delete(0, ctk.END)
        entry.insert(0, folder_path)

def search_lml_folder():
    possible_paths = [
        r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2",
        r"C:\Steam\steamapps\common\Red Dead Redemption 2",
        r"C:\Games\Steam\steamapps\common\Red Dead Redemption 2",
        r"D:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2",
        r"D:\Steam\steamapps\common\Red Dead Redemption 2",
        r"D:\Games\Steam\steamapps\common\Red Dead Redemption 2",
        r"E:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2",
        r"E:\Steam\steamapps\common\Red Dead Redemption 2",
        r"E:\Games\Steam\steamapps\common\Red Dead Redemption 2",
        r"F:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2",
        r"F:\Steam\steamapps\common\Red Dead Redemption 2",
        r"F:\Games\Steam\steamapps\common\Red Dead Redemption 2"
    ]

    for path in possible_paths:
        if os.path.isdir(path) and os.access(path, os.R_OK):
            return path
    return ""
    
def generate_key():
    """Generate a key for encrypting the API key. Store it securely."""
    return base64.urlsafe_b64encode(os.urandom(32))

def get_encryption_key():
    """Retrieve or generate the encryption key."""
    key_path = os.path.join(os.getenv('APPDATA'), 'Red Dead Modding Tool', 'keys', 'encryption.key')
    if not os.path.exists(key_path):
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        key = generate_key()
        with open(key_path, 'wb') as key_file:
            key_file.write(key)
    else:
        with open(key_path, 'rb') as key_file:
            key = key_file.read()
    return key

def encrypt_text(plain_text):
    """Encrypt the given plain text."""
    key = get_encryption_key()
    fernet = Fernet(key)
    return fernet.encrypt(plain_text.encode()).decode()

def decrypt_text(encrypted_text):
    """Decrypt the given encrypted text."""
    key = get_encryption_key()
    fernet = Fernet(key)
    return fernet.decrypt(encrypted_text.encode()).decode()
    
def null_button():
    return

def safe_read_file(file_path, as_lines=False):
    """Read a file trying utf-8-sig first, falling back to latin-1 (which accepts any byte).
    Returns (content_or_lines, encoding_used)."""
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(file_path, "r", encoding=enc) as f:
                if as_lines:
                    return f.readlines(), enc
                else:
                    return f.read(), enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"Could not read file: {file_path}")

def three_way_merge(base_lines, a_lines, b_lines, conflict_resolution='A'):
    """
    Perform a proper three-way merge using sync-region alignment.
    
    base_lines: the original unmodified game file
    a_lines:    modified by mod A
    b_lines:    modified by mod B
    conflict_resolution: 'A' to prefer File A, 'B' to prefer File B, 'original' to keep base
    
    Returns (merged_lines, conflicts) where conflicts is a list of dicts.
    """
    sm_a = SequenceMatcher(None, base_lines, a_lines, autojunk=False)
    sm_b = SequenceMatcher(None, base_lines, b_lines, autojunk=False)
    
    matches_a = sm_a.get_matching_blocks()
    matches_b = sm_b.get_matching_blocks()
    
    sync_regions = []
    for ma in matches_a:
        if ma.size == 0:
            continue
        for mb in matches_b:
            if mb.size == 0:
                continue
            start = max(ma.a, mb.a)
            end = min(ma.a + ma.size, mb.a + mb.size)
            if start < end:
                a_start = ma.b + (start - ma.a)
                b_start = mb.b + (start - mb.a)
                sync_regions.append((start, a_start, b_start, end - start))
    
    sync_regions.sort(key=lambda x: x[0])
    
    cleaned = []
    for region in sync_regions:
        if cleaned and region[0] < cleaned[-1][0] + cleaned[-1][3]:
            if region[3] > cleaned[-1][3]:
                cleaned[-1] = region
        else:
            cleaned.append(region)
    sync_regions = cleaned
    
    merged = []
    conflicts = []
    base_pos = 0
    a_pos = 0
    b_pos = 0
    
    for base_sync, a_sync, b_sync, size in sync_regions:
        base_gap = base_lines[base_pos:base_sync]
        a_gap = a_lines[a_pos:a_sync]
        b_gap = b_lines[b_pos:b_sync]
        
        if a_gap == b_gap:
            merged.extend(a_gap)
        elif a_gap == base_gap:
            merged.extend(b_gap)
        elif b_gap == base_gap:
            merged.extend(a_gap)
        else:
            conflicts.append({'base': base_gap, 'a': a_gap, 'b': b_gap})
            if conflict_resolution == 'A':
                merged.extend(a_gap)
            elif conflict_resolution == 'B':
                merged.extend(b_gap)
            else:
                merged.extend(base_gap)
        
        merged.extend(base_lines[base_sync:base_sync + size])
        base_pos = base_sync + size
        a_pos = a_sync + size
        b_pos = b_sync + size
    
    base_gap = base_lines[base_pos:]
    a_gap = a_lines[a_pos:]
    b_gap = b_lines[b_pos:]
    
    if a_gap == b_gap:
        merged.extend(a_gap)
    elif a_gap == base_gap:
        merged.extend(b_gap)
    elif b_gap == base_gap:
        merged.extend(a_gap)
    else:
        conflicts.append({'base': base_gap, 'a': a_gap, 'b': b_gap})
        if conflict_resolution == 'A':
            merged.extend(a_gap)
        elif conflict_resolution == 'B':
            merged.extend(b_gap)
        else:
            merged.extend(base_gap)
    
    return merged, conflicts

def get_safe_mods_path():
    """Return the path to the safe mods exclusion list file."""
    appdata_dir = os.getenv('APPDATA')
    config_folder = os.path.join(appdata_dir, 'Red Dead Modding Tool', 'config')
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

# NXMProxy
def is_nxmproxy_setup():
    """Check if NXMProxy is set up correctly for RDMT and Red Dead Redemption 2."""
    try:
        appdata_nxmproxy_dir = os.path.join(os.getenv("APPDATA"), "nxmproxy")
        nxmproxy_path = os.path.join(appdata_nxmproxy_dir, "nxmproxy.exe")

        os.makedirs(appdata_nxmproxy_dir, exist_ok=True)
        
        result = subprocess.run(
            [nxmproxy_path, "test"],
            capture_output=True,
            text=True,
            check=True
        )
        output = result.stdout.strip()
        
        if "installed: true" not in output:
            print("NXMProxy is not installed.")
            return False

        config_path = os.path.join(os.getenv("LOCALAPPDATA"), "nxmproxy", "config.toml")
        if not os.path.exists(config_path):
            print(f"NXMProxy config file not found at {config_path}.")
            return False

        with open(config_path, "r") as config_file:
            config = toml.load(config_file)

        managers = config.get("managers", {})
        rdmt_path = os.path.join(base_path, "Red Dead Modding Tool.exe")
        if "rdmt" not in managers or managers["rdmt"] != rdmt_path:
            print("RDMT is not registered correctly in NXMProxy.")
            return False

        games = config.get("games", {})
        if "reddeadredemption2" not in games or games["reddeadredemption2"] != "rdmt":
            print("Red Dead Redemption 2 is not assigned to RDMT.")
            return False

        pipes = config.get("pipes", {})
        if "rdmt" not in pipes or pipes["rdmt"] != "rdmt_download":
            print("Pipe rdmt_download is not set up correctly in NXMProxy.")
            return False

        print("NXMProxy is set up correctly.")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error running nxmproxy test: {e.stderr.strip()}")
        return False
    except FileNotFoundError:
        print("NXMProxy executable not found.")
        return False
    except toml.TomlDecodeError as e:
        print(f"Error parsing NXMProxy config file: {e}")
        return False

def execute_command(command):
    """Execute a shell command and return the output and exit code."""
    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout.strip(), result.returncode
    except Exception as e:
        print(f"Error executing command {command}: {e}")
        return "", 1
        
def get_current_nxm_handler():
    """Retrieve the current program registered to handle NXM links."""
    try:
        reg_key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"nxm\shell\open\command")
        handler, _ = winreg.QueryValueEx(reg_key, None)
        winreg.CloseKey(reg_key)

        match = re.search(r'"([^"]+)"', handler)
        if match:
            handler_path = match.group(1)
            print(f"Extracted NXM handler path: {handler_path}")
            return handler_path
        else:
            print(f"Could not extract NXM handler path from: {handler}")
            return None
    except FileNotFoundError:
        print("No existing NXM handler found.")
        return None
    except Exception as e:
        print(f"Error reading registry for NXM handler: {e}")
        return None

def setup_nxmproxy(button):
    """Setup NXMProxy to forward links to this application."""
    appdata_nxmproxy_dir = os.path.join(os.getenv("APPDATA"), "nxmproxy")
    nxmproxy_path = os.path.join(appdata_nxmproxy_dir, "nxmproxy.exe")

    os.makedirs(appdata_nxmproxy_dir, exist_ok=True)
    
    existing_handler = get_current_nxm_handler()

    if not os.path.isfile(nxmproxy_path):
        print("Copying NXMProxy to %APPDATA%...")
        source_nxmproxy_path = os.path.join(base_path, 'lib', 'nxmproxy', 'nxmproxy.exe')
        try:
            shutil.copy(source_nxmproxy_path, nxmproxy_path)
            print(f"Copied NXMProxy to {nxmproxy_path}")
        except Exception as e:
            print(f"Failed to copy NXMProxy: {e}")
            return False

    print("Checking NXMProxy installation...")
    output, exit_code = execute_command(f'"{nxmproxy_path}" test')
    if exit_code != 0:
        print("NXMProxy not installed. Installing now...")
        output, exit_code = execute_command(f'"{nxmproxy_path}" install')
        if exit_code != 0:
            print(f"Failed to install NXMProxy: {output}")
            return False
            
    if existing_handler and existing_handler != nxmproxy_path:
        existing_handler_name = os.path.splitext(os.path.basename(existing_handler))[0]
        print(f"Adding existing NXM handler to NXMProxy: {existing_handler_name} ({existing_handler})")
        output, exit_code = execute_command(f'"{nxmproxy_path}" register "{existing_handler_name}" "{existing_handler}"')
        if exit_code != 0:
            print(f"Failed to register existing NXM handler: {output}")
            return False

        print(f"Assigning {existing_handler_name} to handle all other games...")
        output, exit_code = execute_command(f'"{nxmproxy_path}" assign "{existing_handler_name}" _')
        if exit_code != 0:
            print(f"Failed to assign {existing_handler_name}: {output}")
            return False

    install_path = os.path.join(base_path, 'Red Dead Modding Tool.exe')
    print("Registering RDMT with NXMProxy...")
    output, exit_code = execute_command(f'"{nxmproxy_path}" register rdmt "{install_path}"')
    if exit_code != 0:
        print(f"Failed to register RDMT: {output}")
        return False

    print("Assigning RDMT to handle Red Dead Redemption 2 NXM links...")
    output, exit_code = execute_command(f'"{nxmproxy_path}" assign rdmt reddeadredemption2')
    if exit_code != 0:
        print(f"Failed to assign RDMT to Red Dead Redemption 2: {output}")
        return False

    print("Setting up NXMProxy pipe...")
    output, exit_code = execute_command(f'"{nxmproxy_path}" pipe rdmt rdmt_download')
    if exit_code != 0:
        print(f"Failed to set up NXMProxy pipe: {output}")
        return False

    print("NXMProxy setup complete!")
    button.pack_forget()
    return True

def handle_nxm_link(link, api_key):
    """
    Handle an NXM link by parsing it and downloading the associated mod.
    """
    try:
        print(f"Received data: {link}")

        if not link.startswith("nxm://reddeadredemption2/"):
            print("Invalid NXM link. It does not match the expected format.")
            return

        match = re.search(r"mods/(\d+)/files/(\d+)", link)
        if not match:
            print("Invalid NXM link format. Could not extract mod_id and file_id.")
            return

        mod_id = match.group(1)
        file_id = match.group(2)

        print(f"Extracted mod_id: {mod_id}, file_id: {file_id}")

        download_mod(None, api_key, mod_id=mod_id, file_id=file_id, install=True)

    except Exception as e:
        print(f"An error occurred while handling the NXM link: {e}")

def start_pipe_listener(pipe_name, handler_function, api_key):
    """Start a named pipe listener to handle incoming NXMProxy links."""
    pipe_full_name = f"\\\\.\\pipe\\{pipe_name}"
    
    def listen():
        while True:
            try:
                pipe = win32pipe.CreateNamedPipe(
                    pipe_full_name,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                    1, 65536, 65536, 0, None
                )
                print(f"Waiting for a connection on {pipe_full_name}...")
                win32pipe.ConnectNamedPipe(pipe, None)
                print("Client connected to the pipe.")
                
                result, data = win32file.ReadFile(pipe, 65536)
                if result == 0:
                    received_data = data.decode("utf-8")
                    print(f"Received data: {received_data}")
                    handler_function(received_data, api_key)
                
                win32file.CloseHandle(pipe)
            except Exception as e:
                print(f"Error with the named pipe: {e}")
                break
    
    threading.Thread(target=listen, daemon=True).start()

    
# --- 3. Data Management Functions ---

def get_mods_and_files(lml_folder):
    """
    Traverse the LML folder to identify mods and their associated files.
    A mod is identified if any folder contains an install.xml file.
    """
    file_map = defaultdict(list)
    ignored_files = {"install.xml", "strings.gxt2", "__folder_managed_by_vortex"}

    def find_mod_folders(folder_path):
        """Recursively scan folders for install.xml and identify mods."""
        mod_folders = []
        for root, dirs, files in os.walk(folder_path):
            if "install.xml" in files:
                mod_folders.append(root)
        return mod_folders

    mod_folders = find_mod_folders(lml_folder)

    for mod_path in mod_folders:
        mod_name = os.path.relpath(mod_path, lml_folder).replace("\\", "/")

        for root, _, files in os.walk(mod_path):
            for file in files:
                if file.lower() not in ignored_files:
                    priority = (
                        2 if "stream" in root.lower() else
                        1 if "replace" in root.lower() else
                        0
                    )
                    file_map[file.lower()].append((mod_name, priority))
    return file_map

def find_conflicts(file_map, safe_mods=None):
    """Find conflicting files between mods, optionally excluding mods marked as safe."""
    if safe_mods is None:
        safe_mods = set()

    def get_root_folder(mod_path):
        """Extract the root folder of a mod from its path."""
        return mod_path.split("/", 1)[0] if "/" in mod_path else mod_path

    conflicts = {}
    for file, mods in file_map.items():
        if file.lower() == "content.xml":
            continue
        
        # Filter out mods that are in the safe list
        filtered_mods = [(mod, pri) for mod, pri in mods if get_root_folder(mod) not in safe_mods]
        
        root_folders = {get_root_folder(mod) for mod, _ in filtered_mods}
        
        if len(root_folders) > 1:
            conflicts[file] = filtered_mods
    return conflicts

def get_load_order(mods_xml_path):
    try:
        tree = ET.parse(mods_xml_path)
        root = tree.getroot()
        load_order_element = root.find("LoadOrder")
        if load_order_element is None:
            print(f"Warning: No <LoadOrder> element found in {mods_xml_path}")
            return []
        return [mod.text.replace("\\", "/") for mod in load_order_element if mod.text]
    except FileNotFoundError:
        print(f"Warning: mods.xml not found at {mods_xml_path}")
        return []
    except ET.ParseError as e:
        print(f"Warning: Failed to parse mods.xml: {e}")
        return []
    
def update_load_order(mods_xml_path, items):
    """Update the load order in the mods.xml file based on the given items list."""
    tree = ET.parse(mods_xml_path)
    root = tree.getroot()

    load_order_element = root.find("LoadOrder")
    if load_order_element is None:
        raise ValueError("No <LoadOrder> element found in mods.xml")

    load_order_element.clear()

    for mod in items:
        mod_element = ET.Element("Mod")
        mod_element.text = mod.replace("\\", "/")
        load_order_element.append(mod_element)

    indent_xml(root)
    tree.write(mods_xml_path, encoding="utf-8", xml_declaration=True)

def indent_xml(elem, level=0):
    """Helper function to indent XML elements for custom formatting."""
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for subelem in elem:
            indent_xml(subelem, level + 1)
            if not subelem.tail or not subelem.tail.strip():
                subelem.tail = i + "  "
        if not subelem.tail or not subelem.tail.strip():
            subelem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


# --- 4. GUI Layout Functions ---

def populate_listbox(listbox, items):
    """Helper function to populate the listbox with items, temporarily hiding it during redraw."""
    listbox.pack_forget()
    listbox.delete(0, ctk.END)

    for item in items:
        listbox.insert(ctk.END, item)

    listbox.pack(fill="both", expand=True)

def get_listbox_items(listbox):
    """Retrieve all items from the listbox as a list."""
    return [listbox.get(i) for i in range(listbox.size())]

def move_up(listbox, mods_xml_path):
    """Move the selected item up in the list and update the listbox."""
    try:
        selected_index = listbox.curselection()
        if selected_index > 0:
            listbox.move_up(selected_index)
            items = get_listbox_items(listbox)
            update_load_order(mods_xml_path, items)
    except (IndexError, AttributeError):
        pass

def move_down(listbox, mods_xml_path):
    """Move the selected item down in the list and update the listbox."""
    try:
        selected_index = listbox.curselection()
        if selected_index < listbox.size() - 1:
            listbox.move_down(selected_index)
            items = get_listbox_items(listbox)
            update_load_order(mods_xml_path, items)
    except (IndexError, AttributeError):
        pass


# --- 5. Application Logic Functions ---

def open_nexus_link():
    webbrowser.open("https://www.nexusmods.com/reddeadredemption2/mods/5180")

def check_for_update(version_label, main_window):
    """Check for updates, and if available, present options to download Installer or Portable."""
    try:
        response = requests.get("https://pastebin.com/raw/gGXu4uA8", timeout=5)
        response.raise_for_status()
        remote_version = response.text.strip()

        if remote_version != "2.0.4":
            version_label.configure(
                text=f"Update {remote_version} Available!",
                text_color="#f88379",
            )
            
            api_key = config.get("api_key", "")
            if not api_key:
                return
            
            premium_user = validate_premium_status(api_key)
            if not premium_user:
                return

            game_domain_name = "reddeadredemption2"
            mod_id = 5180
            files_url = f"https://api.nexusmods.com/v1/games/{game_domain_name}/mods/{mod_id}/files.json"
            headers = {
                'accept': 'application/json',
                'apikey': api_key
            }

            files_response = requests.get(files_url, headers=headers)
            files_response.raise_for_status()
            files_data = files_response.json()

            installer_file_id = None
            portable_file_id = None

            for file_entry in files_data.get("files", []):
                if "Installer" in file_entry.get("name", ""):
                    installer_file_id = file_entry["file_id"]
                elif "Portable" in file_entry.get("name", ""):
                    portable_file_id = file_entry["file_id"]

            if not installer_file_id or not portable_file_id:
                raise ValueError("Failed to find file IDs for Installer or Portable.")

            def download_update(event):
                choice = update_dialog(main_window)
                if choice in ["installer", "portable"]:
                    selected_file_id = installer_file_id if choice == "installer" else portable_file_id
                    download_url = f"https://api.nexusmods.com/v1/games/{game_domain_name}/mods/{mod_id}/files/{selected_file_id}/download_link.json"

                    download_response = requests.get(download_url, headers=headers)
                    download_response.raise_for_status()
                    download_links = download_response.json()

                    if download_links:
                        download_link = download_links[0]['URI']

                        if choice == "installer":
                            download_installer(download_link)
                        else:
                            download_portable(download_link)
                    else:
                        print("No download links found.")
                elif choice == "cancel":
                    print("Update download cancelled.")
            if api_key:
                version_label.configure(cursor="hand2")
                version_label.bind("<Button-1>", download_update)
        else:
            print("No updates available.")
    except requests.exceptions.RequestException as err:
        print(f"Failed to check for updates: {err}")
    except KeyError as key_err:
        print(f"Unexpected response format: Missing key {key_err}")
    except ValueError as val_err:
        print(val_err)

def download_installer(download_url):
    """
    Download the Installer ZIP file, extract it, and run the installer with /silent command.
    """
    try:
        appdata_dir = os.getenv('APPDATA')
        lml_folder = os.path.join(appdata_dir, 'Red Dead Modding Tool', 'temp')
        os.makedirs(lml_folder, exist_ok=True)
        zip_file_path = os.path.join(lml_folder, "installer.zip")
        extract_path = os.path.join(lml_folder, "installer")

        print("Starting download...")
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        with open(zip_file_path, 'wb') as zip_file:
            for chunk in response.iter_content(chunk_size=8192):
                zip_file.write(chunk)
        print(f"Downloaded installer ZIP to: {zip_file_path}")

        os.makedirs(extract_path, exist_ok=True)
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        print(f"Extracted installer to: {extract_path}")

        installer_exe = None
        for root, dirs, files in os.walk(extract_path):
            for file in files:
                if file.lower().endswith('.exe'):
                    installer_exe = os.path.join(root, file)
                    break
            if installer_exe:
                break

        if not installer_exe:
            raise FileNotFoundError("Installer executable not found in the extracted files.")

        print(f"Found installer executable: {installer_exe}")

        print("Running installer...")
        subprocess.Popen([installer_exe, "/silent", "/norestart", "/closeapplications", "/restartapplications"])

    except requests.RequestException as req_err:
        print(f"Error downloading the installer: {req_err}")
    except zipfile.BadZipFile as zip_err:
        print(f"Error extracting the installer ZIP: {zip_err}")
    except subprocess.CalledProcessError as sub_err:
        print(f"Error running the installer: {sub_err}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def download_portable(download_url):
    """
    Download the Portable ZIP file and allow the user to save it via a file dialog.
    """
    try:
        default_save_path = os.path.join(os.path.expanduser("~"), "Downloads", "RDMT - Portable.zip")

        save_path = filedialog.asksaveasfilename(
            title="Download RDMT - Portable",
            defaultextension=".zip",
            initialfile="RDMT - Portable.zip",
            initialdir=os.path.join(os.path.expanduser("~"), "Downloads"),
            filetypes=[("ZIP Files", "*.zip"), ("All Files", "*.*")]
        )

        if not save_path:
            print("Download cancelled by user.")
            return

        print("Starting download...")
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        with open(save_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"Downloaded portable version to: {save_path}")

        CTkMessagebox(title="Red Dead Modding Tool", message=f"RDMT downloaded successfully to:\n{save_path}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05)

    except requests.RequestException as req_err:
        print(f"Error downloading the portable version: {req_err}")
        CTkMessagebox(title="Error", message=f"Failed to download the portable version:\n{req_err}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        CTkMessagebox(title="Error", message=f"An unexpected error occurred:\n{e}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")

def cleanup_installer_files():
    """
    Check for the presence of installer.zip and the installer folder in AppData.
    Delete them if they exist.
    """
    try:
        appdata_dir = os.getenv('APPDATA')
        lml_folder = os.path.join(appdata_dir, 'Red Dead Modding Tool')
        zip_file_path = os.path.join(lml_folder, "installer.zip")
        extract_path = os.path.join(lml_folder, "installer")

        if os.path.exists(zip_file_path):
            os.remove(zip_file_path)
            print(f"Deleted: {zip_file_path}")

        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
            print(f"Deleted folder: {extract_path}")
    except Exception as e:
        print(f"Error during cleanup: {e}")

def update_dialog(main_window):
    """Ask the user to select between manual conflict resolution or auto-merge."""
    dialog = ctk.CTkToplevel(main_window)
    
    dialog.withdraw()
    
    dialog.title("Download RDMT")
    
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    initial_width = min(480, int(screen_width * 0.9))
    initial_height = min(100, int(screen_height * 0.9))

    x = max(0, (screen_width - initial_width) // 2)
    y = max(0, (screen_height - initial_height) // 2)

    dialog.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
    dialog.wm_minsize(initial_width, initial_height)
    dialog.resizable(False, False)
    
    icon_path = os.path.join(image_path, "rdmt.ico")
    dialog.after(201, lambda: dialog.iconbitmap(icon_path))

    result = {"choice": "cancel"}

    def set_choice(choice):
        result["choice"] = choice
        dialog.destroy()

    ctk.CTkLabel(dialog, text="Please select which version to download:", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=3, padx=10, pady=10)
    
    ctk.CTkButton(dialog, text="Portable", command=lambda: set_choice("portable"), fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 14, "bold")).grid(row=1, column=0, padx=10)
    ctk.CTkButton(dialog, text="Installer", command=lambda: set_choice("installer"), fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 14, "bold")).grid(row=1, column=1, padx=10)
    ctk.CTkButton(dialog, text="Cancel", command=lambda: set_choice("cancel"), fg_color="darkgrey", hover_color="grey", font=("Segoe UI", 14, "bold")).grid(row=1, column=2, padx=10)

    dialog.transient(main_window)
    dialog.grab_set()
    dialog.deiconify()
    dialog.wait_window()

    return result["choice"]

def open_mod_folder(selected_mod, lml_folder):
    selected_mod = selected_mod.replace(" (Lowest Priority)", "").replace(" (Highest Priority)", "")
    mod_folder_path = os.path.join(lml_folder, selected_mod)
    if os.path.isdir(mod_folder_path):
        os.startfile(mod_folder_path)
    else:
        print(f"Error: Folder '{mod_folder_path}' does not exist.")
        
def open_mod_page(selected_item, api_key, category):
    """Open the Nexus Mods page for the selected mod in a web browser."""
    if not selected_item:
        print("No mod selected.")
        return

    mod_name = selected_item.split(" (v")[0]

    cache = load_cache(category)
    
    stored_mod_details = cache.get("mod_details", {})

    for mod_id, mod_details in stored_mod_details.items():
        if mod_details.get("name") == mod_name:
            mod_page_url = f"https://www.nexusmods.com/reddeadredemption2/mods/{mod_id}"
            webbrowser.open(mod_page_url)
            return

    print("Mod details not found in the cache")

def check_nexus_conflicts(selected_item, api_key, category):
    stop_thread = threading.Event()

    def detect_conflicts():
        try:
            if stop_thread.is_set():
                return

            mod_name = selected_item.split(" (v")[0]
            cache = load_cache(category)
            stored_mod_details = cache.get("mod_details", {})

            mod_id = None
            for mod_id_str, mod_details in stored_mod_details.items():
                if mod_details.get("name") == mod_name:
                    mod_id = mod_id_str
                    break

            if not mod_id or stop_thread.is_set():
                print(f"Mod ID for '{mod_name}' not found or process interrupted.")
                progress_dialog.destroy()
                return

            base_url = f"https://api.nexusmods.com/v1/games/reddeadredemption2/mods/{mod_id}/files.json"
            headers = {"accept": "application/json", "apikey": api_key}
            response = requests.get(base_url, headers=headers)
            response.raise_for_status()

            if stop_thread.is_set():
                return

            files = response.json().get("files", [])
            if not files:
                print(f"No files found for mod ID {mod_id}.")
                progress_dialog.destroy()
                return

            tracked_mod_files = set()
            for file in files:
                content_preview_url = file.get("content_preview_link")
                if content_preview_url:
                    preview_response = requests.get(content_preview_url)
                    preview_response.raise_for_status()
                    preview_data = preview_response.json()

                    def extract_files(node):
                        if isinstance(node, dict) and node.get("type") == "file":
                            file_path = node.get("path", "").lower()
                            tracked_mod_files.add(os.path.basename(file_path))
                        elif isinstance(node, dict) and "children" in node:
                            for child in node["children"]:
                                extract_files(child)

                    extract_files(preview_data)

            if stop_thread.is_set():
                return

            installed_files = get_mods_and_files(load_config().get("path", ""))
            conflict_map = {}

            for file_name in tracked_mod_files:
                if file_name in installed_files:
                    conflict_map[file_name] = [mod for mod, _ in installed_files[file_name]]

            if stop_thread.is_set():
                return

            progress_dialog.destroy()

            if not stop_thread.is_set():
                conflict_window = ctk.CTkToplevel()
                
                conflict_window.withdraw()
                
                conflict_window.title(f"Conflicts for {mod_name}")

                conflict_textbox = ctk.CTkTextbox(conflict_window, wrap="word", font=("Segoe UI", 18), width=600, height=400)
                conflict_textbox.pack(fill="both", expand=True, padx=10, pady=10)

                conflict_textbox.bind("<Button-1>", lambda e: "break")
                conflict_textbox.bind("<B1-Motion>", lambda e: "break")
                conflict_textbox.bind("<Control-a>", lambda e: "break")
                conflict_textbox.bind("<Shift-Left>", lambda e: "break")
                conflict_textbox.bind("<Shift-Right>", lambda e: "break")

                conflict_window.attributes('-topmost', True)
                conflict_window.focus_set()
                conflict_window.grab_set()

                screen_width = conflict_window.winfo_screenwidth()
                screen_height = conflict_window.winfo_screenheight()
                initial_width = min(800, int(screen_width * 0.9))
                initial_height = min(600, int(screen_height * 0.9))

                x = max(0, (screen_width - initial_width) // 2)
                y = max(0, (screen_height - initial_height) // 2)

                conflict_window.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
                conflict_window.wm_minsize(initial_width, initial_height)
                conflict_window.resizable(False, False)

                icon_path = os.path.join(image_path, "rdmt.ico")
                conflict_window.after(201, lambda: conflict_window.iconbitmap(icon_path))

                if conflict_map:
                    conflict_text = "Conflicts detected:\n\n"
                    for file, mods in conflict_map.items():
                        conflict_text += f"{file}:\n - Conflicts with: {', '.join(mods)}\n\n"
                    conflict_textbox.insert("1.0", conflict_text)
                else:
                    conflict_textbox.insert("1.0", "No conflicts detected.")

                conflict_textbox.configure(state="disabled")
                conflict_window.transient()
                conflict_window.grab_set()
                conflict_window.deiconify()
                conflict_window.wait_window()

        except requests.RequestException as e:
            progress_dialog.destroy()
            print(f"Error fetching mod conflicts: {e}")

    def on_close():
        stop_thread.set()
        progress_dialog.destroy()

    progress_dialog = ctk.CTkToplevel()
    progress_dialog.title(f"Analyzing {selected_item}...")

    progress_dialog.protocol("WM_DELETE_WINDOW", on_close)

    progress_dialog.attributes('-topmost', True)
    progress_dialog.focus_set()
    progress_dialog.grab_set()

    screen_width = progress_dialog.winfo_screenwidth()
    screen_height = progress_dialog.winfo_screenheight()
    initial_width = min(400, int(screen_width * 0.9))
    initial_height = min(50, int(screen_height * 0.9))

    x = max(0, (screen_width - initial_width) // 2)
    y = max(0, (screen_height - initial_height) // 2)
    progress_dialog.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
    progress_dialog.resizable(False, False)

    icon_path = os.path.join(image_path, "rdmt.ico")
    progress_dialog.after(201, lambda: progress_dialog.iconbitmap(icon_path))

    progress_bar = ctk.CTkProgressBar(progress_dialog, width=300, progress_color="#b22222")
    progress_bar.pack(pady=20, padx=20)
    progress_bar.set(0)
    progress_bar.start()

    thread = threading.Thread(target=detect_conflicts, daemon=True)
    thread.start()

def download_mod(selected_item, api_key, category=None, mod_id=None, file_id=None, install=False):
    """Download a mod, either selected from a list or specified by mod_id and file_id, and optionally install it."""
    stop_thread = threading.Event()

    def download_install():
        progress_dialog = None

        try:
            nonlocal mod_id
            nonlocal file_id
            if mod_id is None:
                if not selected_item:
                    print("No mod selected.")
                    return

                mod_name = selected_item.split(" (v")[0]
                cache = load_cache(category)
                stored_mod_details = cache.get("mod_details", {})

                for mod_id_str, mod_details in stored_mod_details.items():
                    if mod_details.get("name") == mod_name:
                        mod_id = mod_id_str
                        break

                if not mod_id:
                    print(f"Mod ID for '{mod_name}' not found.")
                    return

            if not file_id:
                base_url = f"https://api.nexusmods.com/v1/games/reddeadredemption2/mods/{mod_id}/files.json"
                headers = {"accept": "application/json", "apikey": api_key}
                response = requests.get(base_url, headers=headers)
                response.raise_for_status()

                files = response.json().get("files", [])
                if not files:
                    print(f"No files found for mod ID {mod_id}.")
                    return

                valid_files = [file for file in files if file.get("category_name") != "ARCHIVED"]
                if not valid_files:
                    CTkMessagebox(title="Warning", message="All files for this mod are archived and unavailable for download.", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="warning")
                    return

                file_options = {
                    file["file_id"]: {"name": file["name"], "version": file["version"], "file_name": file["file_name"]}
                    for file in valid_files
                }

                file_ids = list(file_options.keys())
                selected_file_id = None
                selected_file_name = None

                if len(file_options) > 1:
                    file_choice_dialog = ctk.CTkToplevel()
                    file_choice_dialog.title("Select File to Download")
                    file_choice_dialog.attributes('-topmost', True)
                    file_choice_dialog.focus_set()
                    file_choice_dialog.grab_set()

                    screen_width = file_choice_dialog.winfo_screenwidth()
                    screen_height = file_choice_dialog.winfo_screenheight()
                    initial_width = min(400, int(screen_width * 0.9))
                    initial_height = min(300, int(screen_height * 0.9))

                    x = max(0, (screen_width - initial_width) // 2)
                    y = max(0, (screen_height - initial_height) // 2)
                    file_choice_dialog.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
                    file_choice_dialog.resizable(False, False)

                    icon_path = os.path.join(image_path, "rdmt.ico")
                    file_choice_dialog.after(201, lambda: file_choice_dialog.iconbitmap(icon_path))

                    result = {"choice": None}

                    def on_file_select(selected_item):
                        """Handle file selection directly from the listbox."""
                        try:
                            for file_id, file_data in file_options.items():
                                if selected_item == f"{file_data['name']} (v{file_data['version']})":
                                    nonlocal selected_file_id, selected_file_name
                                    selected_file_id = file_id
                                    selected_file_name = file_data["file_name"]
                                    break
                            result["choice"] = "selected"
                            file_choice_dialog.after(100, file_choice_dialog.destroy)
                        except Exception as e:
                            print(f"Error in selection callback: {e}")

                    def on_close_dialog():
                        """Handle closing the dialog without selection."""
                        result["choice"] = "cancel"
                        file_choice_dialog.destroy()

                    file_choice_dialog.protocol("WM_DELETE_WINDOW", on_close_dialog)

                    file_listbox = CTkListbox(
                        file_choice_dialog,
                        command=on_file_select,
                        height=400,
                        width=300,
                        highlight_color="#8b0000",
                        hover_color="#b22222"
                    )

                    for file_id, file_data in file_options.items():
                        file_name = file_data["name"]
                        file_version = file_data["version"]
                        file_listbox.insert(ctk.END, f"{file_name} (v{file_version})")

                    file_listbox.pack(pady=10)

                    file_choice_dialog.transient()
                    file_choice_dialog.grab_set()
                    file_choice_dialog.wait_window()

                    if result["choice"] == "cancel":
                        print("File selection cancelled.")
                        return

                if len(file_options) == 1:
                    selected_file_id = file_ids[0]
                    selected_file_name = file_options[selected_file_id]["file_name"]

                if not selected_file_id or not selected_file_name:
                    print("No file selected.")
                    return

                file_id = selected_file_id

            download_url = f"https://api.nexusmods.com/v1/games/reddeadredemption2/mods/{mod_id}/files/{file_id}/download_link.json"
            headers = {"accept": "application/json", "apikey": api_key}
            download_response = requests.get(download_url, headers=headers)
            download_response.raise_for_status()

            download_links = download_response.json()
            if not download_links:
                print("No download links found.")
                return

            download_link = download_links[0]["URI"]
            file_extension = os.path.splitext(download_link.split("?")[0])[-1]

            if install:
                save_path = os.path.join(os.getenv("APPDATA"), "Red Dead Modding Tool", "temp", f"{mod_id}_{file_id}{file_extension}")
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
            else:
                save_path = filedialog.asksaveasfilename(
                    title=f"Save {selected_file_name if selected_file_name else f'{mod_id}_{file_id}{file_extension}'}",
                    defaultextension=file_extension,
                    initialfile=selected_file_name if selected_file_name else f"{mod_id}_{file_id}{file_extension}",
                    initialdir=os.path.join(os.path.expanduser("~"), "Downloads"),
                    filetypes=[(f"{file_extension.upper()} Files", f"*{file_extension}"), ("All Files", "*.*")]
                )

            if not save_path:
                print("Download cancelled by user.")
                return

            print("Starting download...")
            progress_dialog = refresh_download_progress_dialog(stop_thread)

            with requests.get(download_link, stream=True) as response:
                response.raise_for_status()
                with open(save_path, "wb") as file:
                    shutil.copyfileobj(response.raw, file)

            print(f"Downloaded to: {save_path}")

            if not install:
                progress_dialog.destroy()
                CTkMessagebox(title="Red Dead Modding Tool", message=f"Mod downloaded successfully to {save_path}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05)
                return

            install_directory = config["path"]
            game_directory = os.path.dirname(install_directory)

            extract_path = os.path.join(os.path.dirname(save_path), f"extracted_{mod_id}_{file_id}")
            os.makedirs(extract_path, exist_ok=True)

            try:
                patoolib.extract_archive(save_path, outdir=extract_path)
                print(f"Extracted {save_path} to {extract_path}")
            except Exception as e:
                print(f"Error extracting archive: {e}")
                progress_dialog.destroy()
                CTkMessagebox(title="Error", message=f"Failed to extract archive:\n{e}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")
                return

            has_asi = False
            has_lml_folder = False
            install_xml_found = False
            mod_installed = False

            for root, dirs, files in os.walk(extract_path):
                if any(file.lower().endswith(".asi") for file in files):
                    has_asi = True
                    shutil.copytree(root, game_directory, dirs_exist_ok=True)
                    print(f"Copied ASI mod files from {root} to {game_directory}")
                    mod_installed = True

                if "lml" in dirs:
                    has_lml_folder = True
                    lml_path = os.path.join(root, "lml")
                    shutil.copytree(lml_path, install_directory, dirs_exist_ok=True)
                    print(f"Merged LML folder from {lml_path} to {install_directory}")
                    mod_installed = True

                if "install.xml" in files:
                    install_xml_found = True

            if install_xml_found and not has_asi and not has_lml_folder:
                mod_root_folder = extract_path
                folder_to_copy = None

                for root, dirs, files in os.walk(mod_root_folder):
                    if "install.xml" in files:
                        folder_to_copy = root
                        break

                if folder_to_copy:
                    dest_path = os.path.join(install_directory, os.path.basename(folder_to_copy))
                    shutil.copytree(folder_to_copy, dest_path, dirs_exist_ok=True)
                    print(f"Copied folder {folder_to_copy} to {dest_path}")
                    mod_installed = True
                else:
                    print(f"No folder containing 'install.xml' found in {mod_root_folder}.")

            shutil.rmtree(extract_path)
            os.remove(save_path)
            
            if mod_installed:
                print("Installation completed successfully.")
                progress_dialog.destroy()
                CTkMessagebox(title="Red Dead Modding Tool", message="Mod installed successfully.", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05)
            else:
                progress_dialog.destroy()
                CTkMessagebox(title="Error", message="Mod not installed due to unrecognized file structure. Please download and install manually.", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")

        except requests.RequestException as req_err:
            print(f"Error downloading mod: {req_err}")
            CTkMessagebox(title="Error", message=f"Failed to download mod:\n{req_err}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            CTkMessagebox(title="Error", message=f"An unexpected error occurred:\n{e}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")
            
    threading.Thread(target=download_install, daemon=True).start()

def open_lml_folder(lml_folder):
    if os.path.isdir(lml_folder):
        os.startfile(lml_folder)
    else:
        print(f"Error: LML folder '{lml_folder}' does not exist.")
        
def open_game_folder(lml_folder):
    if os.path.isdir(lml_folder):
        os.startfile(os.path.dirname(lml_folder))
    else:
        print(f"Error: LML folder '{lml_folder}' does not exist.")

def check_conflicts(app, entry_or_path):
    selected_folder = entry_or_path.get() if hasattr(entry_or_path, "get") else entry_or_path
    lml_folder = os.path.join(selected_folder, "lml") if os.path.basename(selected_folder).lower() == "red dead redemption 2" else selected_folder
    if not os.path.isdir(lml_folder) or not os.access(lml_folder, os.R_OK):
        CTkMessagebox(title="Error", message="Invalid or inaccessible folder path. Please select a valid LML folder.", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")
        return

    file_map = get_mods_and_files(lml_folder)
    safe_mods = load_safe_mods()                          # <-- NEW LINE
    conflicts = find_conflicts(file_map, safe_mods)       # <-- CHANGED: pass safe_mods
    mods = [mod for mod in os.listdir(lml_folder) if os.path.isdir(os.path.join(lml_folder, mod))]
    
    display_main_window(app, mods, conflicts, lml_folder)
    app.withdraw()
    
def get_cache_path(category):
    """Get the path for the tracked mods cache file in AppData."""
    appdata_dir = os.getenv('APPDATA')
    cache_folder = os.path.join(appdata_dir, 'Red Dead Modding Tool', 'cache')
    os.makedirs(cache_folder, exist_ok=True)
    return os.path.join(cache_folder, f'{category}.cache')
    
def load_cache(category):
    """Load the tracked mods cache from the tracked.dat file."""
    cache_path = get_cache_path(category)
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}
    return {}
    
def save_cache(cache, category):
    """Save the tracked mods cache to the tracked.dat file."""
    cache_path = get_cache_path(category)
    with open(cache_path, 'w', encoding='utf-8') as file:
        json.dump(cache, file, ensure_ascii=False, indent=4)
        
def clean_cache():
    """Delete the 'cache' folder and its contents."""
    appdata_dir = os.getenv('APPDATA')
    cache_folder = os.path.join(appdata_dir, 'Red Dead Modding Tool', 'cache')

    try:
        if os.path.exists(cache_folder):
            shutil.rmtree(cache_folder)
            print(f"Cache folder '{cache_folder}' has been successfully deleted.")
        else:
            print(f"Cache folder '{cache_folder}' does not exist.")
    except Exception as e:
        print(f"Failed to delete the cache folder: {e}")
        
def update_clean_cache_button_state(clean_cache_button):
    """Enable or disable the clean cache button based on the presence of the cache folder and its contents."""
    appdata_dir = os.getenv('APPDATA')
    cache_folder = os.path.join(appdata_dir, 'Red Dead Modding Tool', 'cache')

    if os.path.exists(cache_folder) and os.listdir(cache_folder):
        clean_cache_button.configure(state="normal")
    else:
        clean_cache_button.configure(state="disabled")

def get_config_path():
    """Return the path to the configuration file in a user-writable location."""
    appdata_dir = os.getenv('APPDATA')
    config_folder = os.path.join(appdata_dir, 'Red Dead Modding Tool', 'config')
    os.makedirs(config_folder, exist_ok=True)
    return os.path.join(config_folder, 'rdmt.ini')
    
def get_key_path():
    """Return the path to the key.dat file in a user-writable location."""
    appdata_dir = os.getenv('APPDATA')
    app_folder = os.path.join(appdata_dir, 'Red Dead Modding Tool', 'keys')
    os.makedirs(app_folder, exist_ok=True)
    return os.path.join(app_folder, 'api.key')

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

def check_and_save_path(app, entry):
    """Check the provided LML path, save it if valid, and display conflicts if accessible."""
    selected_folder = entry.get().strip()
    if not selected_folder:
        CTkMessagebox(title="Error", message="Please enter or browse to your RDR2 folder path.", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")
        return
    lml_folder = os.path.join(selected_folder, "lml") if os.path.basename(selected_folder).lower() == "red dead redemption 2" else selected_folder
    if not os.path.exists(lml_folder):
        try:
            os.makedirs(lml_folder, exist_ok=True)
            print(f"Created missing LML folder at: {lml_folder}")
        except Exception as e:
            CTkMessagebox(title="Error", message=f"Failed to create LML folder: {e}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")
            return
    if os.path.isdir(lml_folder) and os.access(lml_folder, os.R_OK):
        try:
            save_config(path=selected_folder)
            check_conflicts(app, lml_folder)
        except Exception as e:
            print(f"Error loading mod data: {e}")
            CTkMessagebox(title="Error", message=f"Failed to load mod data from the selected folder:\n{e}\n\nPlease ensure LML is installed correctly.", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")
    else:
        CTkMessagebox(title="Error", message="Invalid or inaccessible folder path. Please select a valid RDR2 folder.", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")
        
def endorse_mod(api_key, endorse_button, endorse_label):
    """Endorse a specific mod on Nexus Mods for Red Dead Redemption 2."""
    try:
        game_domain_name = "reddeadredemption2"
        mod_id = 5180
        
        endorse_url = f"https://api.nexusmods.com/v1/games/{game_domain_name}/mods/{mod_id}/endorse.json"
        headers = {
            'accept': 'application/json',
            'apikey': api_key
        }

        response = requests.post(endorse_url, headers=headers, timeout=10)
        response.raise_for_status()

        if response.status_code == 200:
            print(f"Successfully endorsed mod ID {mod_id} for game {game_domain_name}.")
            endorse_button.configure(text="Endorsed!", fg_color="#8b0000", command="", cursor="arrow")
            endorse_label.configure(text="Thank you for endorsing! :)")
            return True
        else:
            print(f"Failed to endorse mod ID {mod_id}. Response code: {response.status_code}")
            return False

    except requests.RequestException as req_err:
        print(f"Error endorsing mod: {req_err}")
        return False
        
def check_endorsement(api_key, endorse_button, endorse_label):
    """Check if the user has endorsed the specified mod on Nexus Mods."""
    def threaded_check():
        try:
            endorsements_url = "https://api.nexusmods.com/v1/user/endorsements.json"
            headers = {
                'accept': 'application/json',
                'apikey': api_key
            }

            response = requests.get(endorsements_url, headers=headers, timeout=10)
            response.raise_for_status()
            endorsements = response.json()

            target_domain = "reddeadredemption2"
            target_mod_id = 5180

            for endorsement in endorsements:
                if endorsement.get("domain_name") == target_domain and endorsement.get("mod_id") == target_mod_id and endorsement.get("status") == "Endorsed":
                    endorse_button.configure(text="Endorsed!", fg_color="#8b0000", command=null_button, cursor="arrow")
                    endorse_label.configure(text="Thank you for endorsing! :)")
                    
            return

        except requests.RequestException as req_err:
            print(f"Error checking endorsements: {req_err}")
            return
        except ValueError as val_err:
            print(f"Unexpected response format: {val_err}")
            return

    thread = threading.Thread(target=threaded_check, daemon=True)
    thread.start()

def refresh_modlist(mod_listbox, lml_folder, mods_xml_path, browse_button):
    """Refresh the mod list by reloading mods from the LML folder and updating the listbox."""
    try:
        file_map = get_mods_and_files(lml_folder)
        mods = {mod.replace("\\", "/") for _, mod_list in file_map.items() for mod, _ in mod_list}

        load_order = get_load_order(mods_xml_path)

        sorted_mods = [mod for mod in load_order if mod in mods] + [mod for mod in mods if mod not in load_order]

        populate_listbox(mod_listbox, sorted_mods)

        browse_button.configure(state="disabled")
    except Exception as e:
        error_message = f"Error refreshing mod list: {str(e)}"
        CTkMessagebox(title="Error", message=error_message, button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")   

def refresh_asi(asi_listbox, lml_folder):
    """Refresh the list of ASI mods in the game folder and RDMT folder."""
    try:
        game_folder = os.path.dirname(lml_folder)
        rdmt_folder = os.path.join(game_folder, "RDMT")
        
        if not os.path.isdir(game_folder):
            raise FileNotFoundError(f"Game root folder '{game_folder}' does not exist or is inaccessible.")
        
        asi_files_in_game = [file for file in os.listdir(game_folder) if file.lower().endswith(".asi")]
        asi_files_in_rdmt = [file for file in os.listdir(rdmt_folder) if file.lower().endswith(".asi")] if os.path.isdir(rdmt_folder) else []

        all_asi_files = asi_files_in_game + [f"{file} (DISABLED)" for file in asi_files_in_rdmt]

        all_asi_files.sort(key=lambda x: x.lower())

        asi_listbox.pack_forget()
        asi_listbox.delete(0, ctk.END)

        if all_asi_files:
            for asi_file in all_asi_files:
                asi_listbox.insert(ctk.END, asi_file)
        else:
            asi_listbox.insert(ctk.END, "No ASI mods found.")
        
        asi_listbox.pack(side="left", fill="both", expand=True)
    
    except Exception as e:
        CTkMessagebox(
            title="Error",
            message=f"Failed to refresh ASI mods: {e}",
            button_color="#b22222",
            button_hover_color="#8b0000",
            fade_in_duration=0.05,
            icon="cancel"
        )

def toggle_asi_mod(asi_listbox, lml_folder, button):
    """Toggle the state of an ASI mod by moving it between the game folder and RDMT subfolder."""
    try:
        game_folder = os.path.dirname(lml_folder)
        rdmt_folder = os.path.join(game_folder, "RDMT")
        
        selected_index = asi_listbox.curselection()
        if not selected_index:
            raise ValueError("No ASI mod selected.")
        
        asi_mod = asi_listbox.get(selected_index)
        if asi_mod.endswith(" (DISABLED)"):
            asi_mod = asi_mod.rsplit(" (DISABLED)", 1)[0]
            asi_listbox.delete(selected_index)
            asi_listbox.insert(selected_index, asi_mod)
        
        if not os.path.exists(rdmt_folder):
            os.makedirs(rdmt_folder, exist_ok=True)
        
        mod_in_game_folder = os.path.join(game_folder, asi_mod)
        mod_in_rdmt_folder = os.path.join(rdmt_folder, asi_mod)

        if os.path.exists(mod_in_game_folder):
            shutil.move(mod_in_game_folder, mod_in_rdmt_folder)
            print(f"Moved {asi_mod} to the RDMT folder.")
            asi_listbox.insert(selected_index, f"{asi_mod} (DISABLED)")
        elif os.path.exists(mod_in_rdmt_folder):
            shutil.move(mod_in_rdmt_folder, mod_in_game_folder)
            print(f"Moved {asi_mod} back to the game folder.")
            asi_listbox.delete(selected_index)
            asi_listbox.insert(selected_index, asi_mod)
        else:
            raise FileNotFoundError(f"{asi_mod} not found in either the game folder or RDMT folder.")
        
        if os.path.exists(rdmt_folder) and not os.listdir(rdmt_folder):
            os.rmdir(rdmt_folder)
            print("RDMT folder is empty and has been deleted.")
            
        button.configure(state="disabled")
    
    except Exception as e:
        print(f"Error toggling ASI mod: {e}")

def refresh_download_progress_dialog(stop_thread):
    def on_close():
        stop_thread.set()
        progress_dialog.destroy()

    progress_dialog = ctk.CTkToplevel()
    progress_dialog.title(f"Downloading mod...")

    progress_dialog.protocol("WM_DELETE_WINDOW", on_close)

    progress_dialog.attributes('-topmost', True)
    progress_dialog.focus_set()
    progress_dialog.grab_set()

    screen_width = progress_dialog.winfo_screenwidth()
    screen_height = progress_dialog.winfo_screenheight()
    initial_width = min(400, int(screen_width * 0.9))
    initial_height = min(50, int(screen_height * 0.9))

    x = max(0, (screen_width - initial_width) // 2)
    y = max(0, (screen_height - initial_height) // 2)
    progress_dialog.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
    progress_dialog.resizable(False, False)

    icon_path = os.path.join(image_path, "rdmt.ico")
    progress_dialog.after(201, lambda: progress_dialog.iconbitmap(icon_path))

    progress_bar = ctk.CTkProgressBar(progress_dialog, width=300, progress_color="#b22222")
    progress_bar.pack(pady=20, padx=20)
    progress_bar.set(0)
    progress_bar.start()
    
    return progress_dialog
        
def refresh_nexus_progress_dialog(show_frame, nexus_frame, nexus_button, stop_thread):
    def on_close():
        stop_thread.set()
        progress_dialog.destroy()
        show_frame(nexus_frame, nexus_button)

    progress_dialog = ctk.CTkToplevel()
    progress_dialog.title(f"Building mod cache...")

    progress_dialog.protocol("WM_DELETE_WINDOW", on_close)

    progress_dialog.attributes('-topmost', True)
    progress_dialog.focus_set()
    progress_dialog.grab_set()

    screen_width = progress_dialog.winfo_screenwidth()
    screen_height = progress_dialog.winfo_screenheight()
    initial_width = min(400, int(screen_width * 0.9))
    initial_height = min(50, int(screen_height * 0.9))

    x = max(0, (screen_width - initial_width) // 2)
    y = max(0, (screen_height - initial_height) // 2)
    progress_dialog.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
    progress_dialog.resizable(False, False)

    icon_path = os.path.join(image_path, "rdmt.ico")
    progress_dialog.after(201, lambda: progress_dialog.iconbitmap(icon_path))

    progress_bar = ctk.CTkProgressBar(progress_dialog, width=300, progress_color="#b22222")
    progress_bar.pack(pady=20, padx=20)
    progress_bar.set(0)
    progress_bar.start()
    
    return progress_dialog
        
def refresh_tracked(tracked_listbox, tracked_description, api_key, show_frame, nexus_frame, nexus_button):
    stop_thread = threading.Event()
    
    def fetch_tracked_mods():
        """Refresh the list of tracked mods for the user and display their names with version in the tracked_listbox."""
        tracked_url = "https://api.nexusmods.com/v1/user/tracked_mods.json"
        headers = {
            'accept': 'application/json',
            'apikey': api_key
        }

        try:
            tracked_description.pack_forget()
            
            response = requests.get(tracked_url, headers=headers, timeout=10)
            response.raise_for_status()
            tracked_mods = response.json()

            domain_name = "reddeadredemption2"
            current_tracked = [mod for mod in tracked_mods if mod["domain_name"] == domain_name]

            cache = load_cache('tracked')
            stored_tracked = cache.get("tracked_mods", [])
            stored_mod_details = cache.get("mod_details", {})

            current_tracked_ids = {mod["mod_id"] for mod in current_tracked}
            stored_tracked_ids = {mod["mod_id"] for mod in stored_tracked if mod["domain_name"] == domain_name}

            new_mod_ids = current_tracked_ids - stored_tracked_ids
            removed_mod_ids = stored_tracked_ids - current_tracked_ids

            for removed_id in removed_mod_ids:
                stored_mod_details.pop(str(removed_id), None)

            for mod in current_tracked:
                mod_id = mod["mod_id"]
                if mod_id in new_mod_ids:
                    mod_details_url = f"https://api.nexusmods.com/v1/games/{domain_name}/mods/{mod_id}.json"
                    try:
                        mod_response = requests.get(mod_details_url, headers=headers, timeout=10)
                        mod_response.raise_for_status()
                        mod_details = mod_response.json()
                        stored_mod_details[str(mod_id)] = mod_details
                    except requests.RequestException as mod_err:
                        print(f"Error fetching details for mod ID {mod_id}: {mod_err}")

            cache["tracked_mods"] = current_tracked
            cache["mod_details"] = stored_mod_details
            save_cache(cache, 'tracked')

            items = [
                f"{mod_details.get('name', 'Unknown Mod')} (v{mod_details.get('version', 'Unknown Version')})"
                for mod_id, mod_details in stored_mod_details.items()
                if mod_details.get("domain_name") == domain_name and mod_details.get('name', 'Unknown Mod') != 'Unknown Mod' and mod_details.get('version', 'Unknown Version') != 'Unknown Version'
            ]

            tracked_listbox.after(0, lambda: populate_listbox(tracked_listbox, items))

        except requests.RequestException as req_err:
            print(f"Error fetching tracked mods: {req_err}")
        finally:
            progress_dialog.destroy()
            
    progress_dialog = refresh_nexus_progress_dialog(show_frame, nexus_frame, nexus_button, stop_thread)
    
    threading.Thread(target=fetch_tracked_mods, daemon=True).start()
        
def refresh_updated(updated_listbox, updated_description, api_key, show_frame, nexus_frame, nexus_button):
    stop_thread = threading.Event()

    def fetch_updated_mods():
        """Fetch and prepare the list of updated mods."""
        updated_url = "https://api.nexusmods.com/v1/games/reddeadredemption2/mods/updated.json?period=1w"
        headers = {
            'accept': 'application/json',
            'apikey': api_key
        }

        try:
            updated_description.pack_forget()

            response = requests.get(updated_url, headers=headers, timeout=10)
            response.raise_for_status()
            updated_mods = response.json()

            cache = load_cache('updated')
            stored_mod_details = cache.get("mod_details", {})

            for mod in updated_mods:
                mod_id = str(mod["mod_id"])
                latest_file_update = mod.get("latest_file_update", 0)

                if (
                    mod_id not in stored_mod_details or 
                    latest_file_update > stored_mod_details[mod_id].get("updated_timestamp", 0)
                ):
                    mod_details_url = f"https://api.nexusmods.com/v1/games/reddeadredemption2/mods/{mod_id}.json"
                    try:
                        mod_response = requests.get(mod_details_url, headers=headers, timeout=10)
                        mod_response.raise_for_status()
                        mod_details = mod_response.json()
                        mod_details["updated_timestamp"] = latest_file_update  # Update timestamp in cache
                        stored_mod_details[mod_id] = mod_details
                    except requests.RequestException as mod_err:
                        print(f"Error fetching details for mod ID {mod_id}: {mod_err}")

            cache["mod_details"] = stored_mod_details
            save_cache(cache, 'updated')

            current_time = datetime.now(timezone.utc)
            seven_days_ago = current_time - timedelta(days=7)

            sorted_mods = []
            for mod_id, mod_details in stored_mod_details.items():
                mod_name = mod_details.get("name", "Unknown Mod")
                mod_version = mod_details.get("version", "Unknown Version")
                mod_updated_time = datetime.fromtimestamp(mod_details.get("updated_timestamp", 0), timezone.utc)

                if mod_updated_time >= seven_days_ago:
                    if mod_name != "Unknown Mod" and mod_version != "Unknown Version":
                        sorted_mods.append((mod_updated_time, f"{mod_name} (v{mod_version})"))

            sorted_mods.sort(key=lambda x: x[0], reverse=True)

            display_items = [mod_display for _, mod_display in sorted_mods]

            updated_listbox.after(0, lambda: populate_listbox(updated_listbox, display_items))

        except requests.RequestException as req_err:
            print(f"Error fetching updated mods: {req_err}")
        finally:
            progress_dialog.destroy()

    progress_dialog = refresh_nexus_progress_dialog(show_frame, nexus_frame, nexus_button, stop_thread)
    
    threading.Thread(target=fetch_updated_mods, daemon=True).start()
    
def refresh_trending(trending_listbox, trending_description, api_key, show_frame, nexus_frame, nexus_button):
    stop_thread = threading.Event()
    
    def fetch_trending_mods():
        """Refresh the list of 10 trending mods."""
        updated_url = "https://api.nexusmods.com/v1/games/reddeadredemption2/mods/trending.json"
        headers = {
            'accept': 'application/json',
            'apikey': api_key
        }

        try:
            trending_description.pack_forget()
            
            response = requests.get(updated_url, headers=headers, timeout=10)
            response.raise_for_status()
            updated_mods = response.json()

            cache = load_cache('trending')
            stored_mod_details = cache.get("mod_details", {})

            for mod in updated_mods:
                mod_id = mod["mod_id"]
                if str(mod_id) not in stored_mod_details:
                    mod_details_url = f"https://api.nexusmods.com/v1/games/reddeadredemption2/mods/{mod_id}.json"
                    try:
                        mod_response = requests.get(mod_details_url, headers=headers, timeout=10)
                        mod_response.raise_for_status()
                        mod_details = mod_response.json()
                        stored_mod_details[str(mod_id)] = mod_details
                    except requests.RequestException as mod_err:
                        print(f"Error fetching details for mod ID {mod_id}: {mod_err}")

            cache["mod_details"] = stored_mod_details
            save_cache(cache, 'trending')

            items = [
                f"{mod_details.get('name', 'Unknown Mod')} (v{mod_details.get('version', 'Unknown Version')})"
                for mod_id, mod_details in stored_mod_details.items()
                if mod_details.get('name', 'Unknown Mod') != 'Unknown Mod' and mod_details.get('version', 'Unknown Version') != 'Unknown Version'
            ]
                    
            trending_listbox.after(0, lambda: populate_listbox(trending_listbox, items))

        except requests.RequestException as req_err:
            print(f"Error fetching updated mods: {req_err}")
        finally:
            progress_dialog.destroy()
           
    progress_dialog = refresh_nexus_progress_dialog(show_frame, nexus_frame, nexus_button, stop_thread)
            
    threading.Thread(target=fetch_trending_mods, daemon=True).start()
    
def refresh_added(added_listbox, added_description, api_key, show_frame, nexus_frame, nexus_button):
    stop_thread = threading.Event()
    
    def fetch_added_mods():
        """Refresh the list of 10 trending mods."""
        updated_url = "https://api.nexusmods.com/v1/games/reddeadredemption2/mods/latest_added.json"
        headers = {
            'accept': 'application/json',
            'apikey': api_key
        }

        try:
            added_description.pack_forget()
            
            response = requests.get(updated_url, headers=headers, timeout=10)
            response.raise_for_status()
            updated_mods = response.json()

            cache = load_cache('added')
            stored_mod_details = cache.get("mod_details", {})

            for mod in updated_mods:
                mod_id = mod["mod_id"]
                if str(mod_id) not in stored_mod_details:
                    mod_details_url = f"https://api.nexusmods.com/v1/games/reddeadredemption2/mods/{mod_id}.json"
                    try:
                        mod_response = requests.get(mod_details_url, headers=headers, timeout=10)
                        mod_response.raise_for_status()
                        mod_details = mod_response.json()
                        stored_mod_details[str(mod_id)] = mod_details
                    except requests.RequestException as mod_err:
                        print(f"Error fetching details for mod ID {mod_id}: {mod_err}")

            cache["mod_details"] = stored_mod_details
            save_cache(cache, 'added')

            items = [
                f"{mod_details.get('name', 'Unknown Mod')} (v{mod_details.get('version', 'Unknown Version')})"
                for mod_id, mod_details in stored_mod_details.items()
                if mod_details.get('name', 'Unknown Mod') != 'Unknown Mod' and mod_details.get('version', 'Unknown Version') != 'Unknown Version'
            ]
                    
            added_listbox.after(0, lambda: populate_listbox(added_listbox, items))

        except requests.RequestException as req_err:
            print(f"Error fetching updated mods: {req_err}")
        finally:
            progress_dialog.destroy()
                  
    progress_dialog = refresh_nexus_progress_dialog(show_frame, nexus_frame, nexus_button, stop_thread)
            
    threading.Thread(target=fetch_added_mods, daemon=True).start()
        
def refresh_conflicts(conflict_text, conflicts, lml_folder):
    """Refresh the conflicts display, sorting mods by load order priority and filtering safe mods."""
    try:
        conflict_text.configure(state="normal")
        file_map = get_mods_and_files(lml_folder)
        safe_mods = load_safe_mods()
        conflicts = find_conflicts(file_map, safe_mods)
        
        # Get load order for priority sorting
        mods_xml_path = os.path.join(lml_folder, "mods.xml")
        load_order = get_load_order(mods_xml_path)
        
        # Build a priority index: lower index = loaded first = lower priority (overwritten by later mods)
        load_order_index = {mod.replace("\\", "/"): idx for idx, mod in enumerate(load_order)}
        
        conflict_text.delete('1.0', ctk.END)
        
        if safe_mods:
            conflict_text.insert(ctk.END, f"[{len(safe_mods)} mod(s) excluded as safe]\n\n")
        
        for file, mods in conflicts.items():
            conflict_text.insert(ctk.END, f"File '{file}' is modified by:\n")
            
            def get_root_folder(mod_path):
                return mod_path.split("/", 1)[0] if "/" in mod_path else mod_path
            
            def sort_key(mod_tuple):
                mod, priority = mod_tuple
                root = get_root_folder(mod)
                # Check both full path and root folder against load order
                idx = load_order_index.get(mod, load_order_index.get(root, 999999))
                return idx
            
            sorted_mods = sorted(mods, key=sort_key)
            
            for i, (mod, priority) in enumerate(sorted_mods):
                label = f"{mod} (stream)" if priority == 2 else (f"{mod} (replace)" if priority == 1 else mod)
                
                # Add priority annotation
                if len(sorted_mods) > 1:
                    if i == 0:
                        label += " (Lowest Priority)"
                    elif i == len(sorted_mods) - 1:
                        label += " (Highest Priority)"
                
                conflict_text.insert(ctk.END, f" - {label}\n")
            conflict_text.insert(ctk.END, "\n")
        
        if not conflicts:
            conflict_text.insert(ctk.END, "No conflicts found.")
        
        conflict_text.configure(state="disabled")
    except Exception as e:
        error_message = f"Error refreshing conflicts: {str(e)}"
        CTkMessagebox(title="Error", message=error_message, button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")

def export_conflicts(conflict_text):
    """Export the conflicts report to a text file."""
    try:
        content = conflict_text.get("1.0", ctk.END).strip()
        if not content:
            CTkMessagebox(title="Warning", message="No conflict data to export.", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="warning")
            return
        
        save_path = filedialog.asksaveasfilename(
            title="Export Conflicts Report",
            defaultextension=".txt",
            initialfile="RDMT_Conflicts_Report.txt",
            initialdir=os.path.join(os.path.expanduser("~"), "Downloads"),
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        
        if not save_path:
            return
        
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(f"Red Dead Modding Tool - Conflicts Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'=' * 50}\n\n")
            f.write(content)
        
        CTkMessagebox(title="Red Dead Modding Tool", message=f"Conflicts report exported to:\n{save_path}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05)
    except Exception as e:
        CTkMessagebox(title="Error", message=f"Failed to export conflicts report:\n{e}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")


def manage_safe_mods_dialog(main_window, lml_folder, conflict_text, conflicts):
    """Open a dialog to manage the list of mods excluded from conflict checking."""
    dialog = ctk.CTkToplevel(main_window)
    
    dialog.withdraw()
    
    dialog.title("Manage Safe Mods (Excluded from Conflicts)")
    
    dialog.focus_set()
    dialog.grab_set()

    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    initial_width = min(600, int(screen_width * 0.9))
    initial_height = min(500, int(screen_height * 0.9))

    x = max(0, (screen_width - initial_width) // 2)
    y = max(0, (screen_height - initial_height) // 2)

    dialog.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
    dialog.wm_minsize(initial_width, initial_height)
    dialog.resizable(True, True)
    
    icon_path = os.path.join(image_path, "rdmt.ico")
    dialog.after(201, lambda: dialog.iconbitmap(icon_path))
    
    safe_mods = load_safe_mods()
    
    # Header
    header_frame = ctk.CTkFrame(dialog)
    header_frame.pack(fill="x", padx=10, pady=(10, 5))
    
    ctk.CTkLabel(header_frame, text="Check mods to exclude from conflict detection:", font=("Segoe UI", 14, "bold")).pack(side="left", padx=5)
    
    # Scrollable frame for mod checkboxes
    scroll_frame = ctk.CTkScrollableFrame(dialog, width=550, height=350)
    scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Get all mods from the LML folder
    all_mods = sorted([
        mod for mod in os.listdir(lml_folder)
        if os.path.isdir(os.path.join(lml_folder, mod))
    ], key=str.lower)
    
    checkbox_vars = {}
    for mod_name in all_mods:
        var = ctk.BooleanVar(value=(mod_name in safe_mods))
        checkbox_vars[mod_name] = var
        cb = ctk.CTkCheckBox(
            scroll_frame,
            text=mod_name,
            variable=var,
            font=("Segoe UI", 14),
            fg_color="#b22222",
            hover_color="#8b0000"
        )
        cb.pack(anchor="w", padx=10, pady=2)
    
    # Buttons
    button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    button_frame.pack(fill="x", padx=10, pady=10)
    
    def save_and_refresh():
        new_safe_mods = {mod for mod, var in checkbox_vars.items() if var.get()}
        save_safe_mods(new_safe_mods)
        refresh_conflicts(conflict_text, conflicts, lml_folder)
        dialog.destroy()
    
    def select_all():
        for var in checkbox_vars.values():
            var.set(True)
    
    def deselect_all():
        for var in checkbox_vars.values():
            var.set(False)
    
    ctk.CTkButton(button_frame, text="Select All", command=select_all, fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 14, "bold")).pack(side="left", padx=5)
    ctk.CTkButton(button_frame, text="Deselect All", command=deselect_all, fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 14, "bold")).pack(side="left", padx=5)
    ctk.CTkButton(button_frame, text="Save & Refresh", command=save_and_refresh, fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 14, "bold")).pack(side="right", padx=5)
    ctk.CTkButton(button_frame, text="Cancel", command=dialog.destroy, fg_color="darkgrey", hover_color="grey", font=("Segoe UI", 14, "bold")).pack(side="right", padx=5)
    
    dialog.transient(main_window)
    dialog.grab_set()
    dialog.deiconify()
    dialog.wait_window()

def clean_mods(lml_folder):
    """Move non-game files from the game root to the RDMT backup folder."""
    root_dir = os.path.dirname(lml_folder)
    backup_dir = os.path.join(root_dir, "RDMT")

    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    game_files = {
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

    for filename in os.listdir(root_dir):
        file_path = os.path.join(root_dir, filename)
        
        if os.path.isfile(file_path) and filename not in game_files:
            try:
                shutil.move(file_path, os.path.join(backup_dir, filename))
                print(f"Moved: {filename}")
            except Exception as e:
                print(f"Failed to move {filename}: {e}")

def restore_mods(lml_folder):
    """Restore files from the RDMT backup folder to the game root."""
    root_dir = os.path.dirname(lml_folder)
    backup_dir = os.path.join(root_dir, "RDMT")

    if os.path.exists(backup_dir):
        for filename in os.listdir(backup_dir):
            file_path = os.path.join(backup_dir, filename)
            try:
                shutil.move(file_path, os.path.join(root_dir, filename))
                print(f"Restored: {filename}")
            except Exception as e:
                print(f"Failed to restore {filename}: {e}")
        try:
            os.rmdir(backup_dir)
            print(f"Removed backup directory: {backup_dir}")
        except Exception as e:
            print(f"Failed to remove backup directory: {e}")
    else:
        print(f"No backup folder found at {backup_dir}")
        
def update_clean_button_state(lml_folder, clean_button):
    """Enable or disable the clean button based on the presence of non-game files in the game folder."""
    root_dir = os.path.dirname(lml_folder)

    game_files = {
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

    non_game_files_exist = any(
        os.path.isfile(os.path.join(root_dir, filename)) and filename not in game_files
        for filename in os.listdir(root_dir)
    )

    if non_game_files_exist:
        clean_button.configure(state="normal")
    else:
        clean_button.configure(state="disabled")
        
def update_restore_button_state(lml_folder, restore_button):
    """Enable or disable the restore button based on the presence of the RDMT folder."""
    root_dir = os.path.dirname(lml_folder)
    rdmt_dir = os.path.join(root_dir, "RDMT")
    
    if os.path.exists(rdmt_dir) and os.path.isdir(rdmt_dir):
        restore_button.configure(state="normal")
    else:
        restore_button.configure(state="disabled")
 
def restart_for_lml(lml_path_entry):
    """Restart the program."""
    save_config(path=lml_path_entry.get().strip())
    python_executable = sys.executable
    script_path = sys.argv[0]
    subprocess.Popen([python_executable, script_path])
    sys.exit()

def restart_for_api(api_key):
    """Restart the program with the updated API key after validating it."""
    keys_directory = os.path.join(os.getenv("APPDATA"), "Red Dead Modding Tool", "keys")
    api_key_path = os.path.join(keys_directory, "api.key")
    encryption_key_path = os.path.join(keys_directory, "encryption.key")

    if api_key is None:
        try:
            if os.path.exists(api_key_path):
                os.remove(api_key_path)
                print("Deleted api.key.")
            if os.path.exists(encryption_key_path):
                os.remove(encryption_key_path)
                print("Deleted encryption.key.")
        except Exception as e:
            print(f"Error deleting key files: {e}")
            CTkMessagebox(title="Error", message=f"Failed to delete key files:\n{e}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")
    elif validate_api_key(api_key):
        save_config(api_key=api_key)
    else:
        CTkMessagebox(title="Error", message="Invalid API key.", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")
        return

    python_executable = sys.executable
    script_path = os.path.abspath(sys.argv[0])
    try:
        print(f"Restarting program: {python_executable} {script_path}")
        subprocess.Popen([python_executable, script_path], close_fds=True)
        os._exit(0)
    except Exception as e:
        print(f"Failed to restart the program: {e}")
        CTkMessagebox(title="Error", message=f"Failed to restart the program:\n{e}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")
        
def sso_retrieve_api_key():
    """Retrieve the API key using Nexus Mods SSO with threading to prevent UI freezing."""
    sso_url = "wss://sso.nexusmods.com"
    unique_id = str(uuid.uuid4())
    connection_token = None
    socket_open = threading.Event()

    def on_message(ws, message):
        """
        Handle incoming messages from the WebSocket.
        """
        try:
            response = json.loads(message)
            if response.get("success"):
                if "connection_token" in response.get("data", {}):
                    nonlocal connection_token
                    connection_token = response["data"]["connection_token"]
                elif "api_key" in response.get("data", {}):
                    api_key = response["data"]["api_key"]
                    print("API Key Received:", api_key)
                    ws.close()
                    restart_for_api(api_key)
            else:
                error_message = response.get("error", "Unknown error occurred")
                print("SSO Error:", error_message)
        except json.JSONDecodeError:
            print("Failed to decode WebSocket message:", message)

    def on_error(ws, error):
        """
        Handle WebSocket errors.
        """
        print("WebSocket Error:", error)

    def on_close(ws, close_status_code, close_msg):
        """
        Handle WebSocket closure.
        """
        print("WebSocket Closed:", close_status_code, close_msg)

    def on_open(ws):
        """
        Handle WebSocket opening and send initial data.
        """
        nonlocal socket_open
        request_data = {
            "id": unique_id,
            "token": connection_token,
            "protocol": 2
        }
        ws.send(json.dumps(request_data))
        socket_open.set()

    ws_app = WebSocketApp(
        sso_url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws_app.on_open = on_open

    def websocket_thread():
        """
        Run WebSocket in a separate thread.
        """
        ws_app.run_forever()

    threading.Thread(target=websocket_thread, daemon=True).start()

    socket_open.wait()

    sso_auth_url = f"https://www.nexusmods.com/sso?id={unique_id}&application={application_slug}"
    print("Opening browser for user authorization:", sso_auth_url)
    webbrowser.open(sso_auth_url)
    
def validate_api_key(api_key):
    """Validate the provided Nexus Mods API key."""
    validation_url = "https://api.nexusmods.com/v1/users/validate.json"
    headers = {
        'accept': 'application/json',
        'apikey': api_key
    }

    try:
        response = requests.get(validation_url, headers=headers, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as req_err:
        print(f"API key validation error: {req_err}")
        return False
        
def validate_premium_status(api_key):
    """Check if the user is a Nexus Mods Premium member."""
    validation_url = "https://api.nexusmods.com/v1/users/validate.json"
    headers = {
        'accept': 'application/json',
        'apikey': api_key
    }
    try:
        response = requests.get(validation_url, headers=headers, timeout=10)
        response.raise_for_status()
        user_data = response.json()
        return user_data.get("is_premium", False)
    except requests.RequestException as req_err:
        print(f"Error validating premium status: {req_err}")
        return False

def show_splash():
    splash_duration = 1500
    update_interval = 10

    splash_root = ctk.CTkToplevel()
    splash_root.overrideredirect(True)
    screen_width, screen_height = splash_root.winfo_screenwidth(), splash_root.winfo_screenheight()
    splash_width, splash_height = 600, 350
    x, y = (screen_width - splash_width) // 2, (screen_height - splash_height) // 2
    splash_root.geometry(f"{splash_width}x{splash_height}+{x}+{y}")

    header_img = load_image("header.webp", splash_width, splash_height)
    if header_img:
        progressbar = ctk.CTkProgressBar(splash_root, width=600, progress_color="#b22222")
        progressbar.pack(side="bottom")
        progressbar.set(0)
        splash_label = ctk.CTkLabel(splash_root, image=header_img, text="")
        splash_label.pack()

    start_time = time.time()

    def update_progress():
        elapsed_time = (time.time() - start_time) * 1000
        progress = min(elapsed_time / splash_duration, 1.0)
        progressbar.set(progress)
        if elapsed_time < splash_duration:
            splash_root.after(update_interval, update_progress)

    update_progress()
    return splash_root


# --- 6. Main Functions ---

def display_main_window(app, mods, conflicts, lml_folder):
    global config
    
    load_order = get_load_order(os.path.join(lml_folder, "mods.xml"))
    sorted_mods = [mod for mod in load_order if mod in mods] + [mod for mod in mods if mod not in load_order]
    
    api_key = config.get("api_key", "")
    if api_key:
        premium_user = validate_premium_status(api_key)
    
    main_window = ctk.CTkToplevel()
    
    main_window.withdraw()
    
    main_window.title("Red Dead Modding Tool")
    
    is_fullscreen = False

    def toggle_fullscreen(event=None):
        nonlocal is_fullscreen
        is_fullscreen = not is_fullscreen
        main_window.attributes("-fullscreen", is_fullscreen)

    main_window.bind("<F11>", toggle_fullscreen)
    main_window.bind("<Alt-Return>", toggle_fullscreen)
    main_window.bind("<Escape>", lambda event: main_window.attributes("-fullscreen", False))
    
    main_window.grid_rowconfigure(0, weight=1)
    main_window.grid_rowconfigure(1, weight=1)
    main_window.grid_rowconfigure(2, weight=1)
    
    main_window.grid_columnconfigure(0, weight=0)
    main_window.grid_columnconfigure(1, weight=1)
    main_window.grid_columnconfigure(2, weight=7)
    main_window.grid_columnconfigure(4, weight=1)

    icon_path = os.path.join(image_path, "rdmt.ico")
    main_window.after(201, lambda: main_window.iconbitmap(icon_path))

    sidebar_frame = ctk.CTkFrame(main_window, corner_radius=0)
    sidebar_frame.grid(row=0, column=0, rowspan=5, sticky="nsw")
    sidebar_frame.grid_rowconfigure(0, weight=1)
    sidebar_frame.grid_rowconfigure(1, weight=1)
    sidebar_frame.grid_rowconfigure(2, weight=1)
    sidebar_frame.grid_rowconfigure(3, weight=1)
    sidebar_frame.grid_rowconfigure(4, weight=1)
    sidebar_frame.grid_rowconfigure(5, weight=1)

    sidebar_dark_image_path = os.path.join(image_path, "rdmt_dark.webp")
    sidebar_light_image_path = os.path.join(image_path, "rdmt_light.webp")
    sidebar_dark_image = Image.open(sidebar_dark_image_path).convert("RGBA")
    sidebar_light_image = Image.open(sidebar_light_image_path).convert("RGBA")
    sidebar_ctk_image = ctk.CTkImage(dark_image=sidebar_dark_image, light_image=sidebar_light_image, size=(249, 106))
    sidebar_image_label = ctk.CTkLabel(sidebar_frame, image=sidebar_ctk_image, fg_color="transparent", text="")
    sidebar_image_label.grid(row=0, column=0, padx=25, pady=(40, 0), sticky="n")

    home_frame = ctk.CTkFrame(main_window, fg_color="transparent")
    
    background_image_path = os.path.join(image_path, "background.webp")
    background_image = ctk.CTkImage(Image.open(background_image_path), size=(3840, 2160))

    background_label = ctk.CTkLabel(home_frame, image=background_image, text="", fg_color="transparent")
    background_label.grid(row=0, column=0, rowspan=3, columnspan=1, sticky="nsew")
    
    home_frame.grid_rowconfigure(0, weight=0)
    home_frame.grid_rowconfigure(1, weight=1)
    home_frame.grid_columnconfigure(0, weight=1)

    mods_frame = ctk.CTkFrame(main_window, fg_color="transparent")
    asi_frame = ctk.CTkFrame(main_window, fg_color="transparent")
    nexus_frame = ctk.CTkFrame(main_window, fg_color="transparent")
    conflicts_frame = ctk.CTkFrame(main_window, fg_color="transparent")
    merge_frame = ctk.CTkFrame(main_window, fg_color="transparent")
    settings_frame = ctk.CTkFrame(main_window, fg_color="transparent")
    
    tracked_frame = ctk.CTkFrame(main_window, fg_color="transparent")
    updated_frame = ctk.CTkFrame(main_window, fg_color="transparent")
    trending_frame = ctk.CTkFrame(main_window, fg_color="transparent")
    added_frame = ctk.CTkFrame(main_window, fg_color="transparent")
    
    def show_frame(target_frame, active_button):
        """Show the target frame and hide all others. Update the active button's color while resetting others."""
        frames = [home_frame, mods_frame, asi_frame, nexus_frame, tracked_frame, updated_frame, trending_frame, added_frame, conflicts_frame, merge_frame, settings_frame]
        buttons = [home_button, mods_button, asi_button, nexus_button, conflicts_button, merge_button, settings_button]

        for frame in frames:
            frame.grid_forget()
        
        if active_button.cget("text") != "Home":
            target_frame.grid(row=0, column=2, columnspan=1, pady=10, rowspan=3, sticky="nswe")
        else:
            target_frame.grid(row=0, column=2, columnspan=1, rowspan=3, sticky="nswe")

        for button in buttons:
            button.configure(fg_color="#b22222")
            
        active_button.configure(fg_color="#8b0000")
    
    def change_appearance_mode(new_mode):
        ctk.set_appearance_mode(new_mode)
        save_config(theme=new_mode)
    
    
    # Sidebar frame
    button_frame = ctk.CTkFrame(sidebar_frame, fg_color="transparent")
    button_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(75, 10))
    
    home_button = ctk.CTkButton(button_frame, text="Home", font=("Segoe UI", 18, "bold"), fg_color="#b22222", hover_color="#8b0000", height=40, border_spacing=10)
    home_button.pack(fill="x", padx=10, pady=5)  
    
    asi_button = ctk.CTkButton(button_frame, text="ASI Mods", font=("Segoe UI", 18, "bold"), fg_color="#b22222", hover_color="#8b0000", height=40, border_spacing=10)
    asi_button.pack(fill="x", padx=10, pady=5)

    mods_button = ctk.CTkButton(button_frame, text="LML Mods", font=("Segoe UI", 18, "bold"), fg_color="#b22222", hover_color="#8b0000", height=40, border_spacing=10)
    mods_button.pack(fill="x", padx=10, pady=5)

    conflicts_button = ctk.CTkButton(button_frame, text="Conflicts", font=("Segoe UI", 18, "bold"), fg_color="#b22222", hover_color="#8b0000", height=40, border_spacing=10)
    conflicts_button.pack(fill="x", padx=10, pady=5)

    merge_button = ctk.CTkButton(button_frame, text="Merge", font=("Segoe UI", 18, "bold"), fg_color="#b22222", hover_color="#8b0000", height=40, border_spacing=10)
    merge_button.pack(fill="x", padx=10, pady=5)
    
    nexus_button = ctk.CTkButton(button_frame, text="Nexus", font=("Segoe UI", 18, "bold"), fg_color="#b22222", hover_color="#8b0000", height=40, border_spacing=10)
    nexus_button.pack(fill="x", padx=10, pady=5)
    
    settings_button = ctk.CTkButton(button_frame, text="Settings", font=("Segoe UI", 18, "bold"), fg_color="#b22222", hover_color="#8b0000", height=40, border_spacing=10)
    settings_button.pack(fill="x", padx=10, pady=5)
    
    version_label = ctk.CTkLabel(sidebar_frame, text="Version 2.0.4", font=("Segoe UI", 18, "bold"))
    version_label.grid(row=5, column=0, sticky="s", padx=10, pady=0)
    
    check_for_update(version_label, main_window)
    
    nexus_link_label = ctk.CTkButton(
        sidebar_frame,
        text="Nexus Mods",
        font=("Segoe UI", 18, "bold"),
        fg_color="transparent",
        hover_color=sidebar_frame.cget("fg_color"),
        text_color="#b22222",
        command=open_nexus_link
    )
    nexus_link_label.grid(row=6, column=0, sticky="s", padx=10, pady=(0, 10))
    
    home_button.configure(command=lambda: show_frame(home_frame, home_button))
    mods_button.configure(command=lambda: show_frame(mods_frame, mods_button))
    asi_button.configure(command=lambda: show_frame(asi_frame, asi_button))
    nexus_button.configure(command=lambda: show_frame(nexus_frame, nexus_button))
    conflicts_button.configure(command=lambda: show_frame(conflicts_frame, conflicts_button))
    merge_button.configure(command=lambda: show_frame(merge_frame, merge_button))
    settings_button.configure(command=lambda: show_frame(settings_frame, settings_button))
    
    if api_key:
        nexus_button.configure(command=lambda: (show_frame(nexus_frame, nexus_button), update_clean_cache_button_state(clean_cache_button)))
    
    
    # Home frame
    home_textbox_container = ctk.CTkFrame(home_frame, fg_color="transparent")
    home_textbox_container.grid(row=1, column=0, padx=20, pady=20, sticky="")
    
    home_textbox = ctk.CTkLabel(
        home_textbox_container, 
        text="Welcome to Red Dead Modding Tool (formerly LML Mod Conflict Checker Tool), a mod manager\nand conflict resolution tool for Red Dead Redemption 2.\n\n"
             "Not only can you manage both your ASI and LML mods, this tool will also iterate through your\n"
             "LML folder and check for any conflicting mods. RDMT even has an auto-merge function to resolve these!\n\n"
             "Now with many new features, including Nexus Mods API integration, which will allow you to check for\n"
             "conflicts with mods you haven't even downloaded yet! RDMT also offers download and\n"
             "install support for both ASI and LML mods from Nexus Mods\n"
             "(non-premium users must download through the Nexus Mods website).\n\n\n"
             "Version 2.0.4 changelog:\n"
             "-----\n"
             "- Mods are now sorted from lowest to highest priority and labelled accordingly.\n"
             "- Conflicts report can now be exported to a text file.\n"
             "- Added option to manage 'safe mods' (mods excluded from conflict checking).\n"
             "- Conflict textbox now supports text selection and copying.\n"
             "- Rebuilt merge tool logic and fixed crashes.\n"
             "- Fixed first-time setup bugs.\n"
             "-----",
        font=("Segoe UI", 17),
        fg_color="transparent"
    )
    home_textbox.pack(fill="both", expand=True, padx=20, pady=20)
    
    
    # Mods frame
    mods_header_frame = ctk.CTkFrame(mods_frame)
    mods_header_frame.pack(fill="x", anchor="n", padx=10, pady=(0, 5))
    ctk.CTkLabel(mods_header_frame, text="LML Mods", font=("Segoe UI", 22, "bold")).pack(side="left", padx=5, pady=10)

    refresh_mods_button = ctk.CTkButton(
        mods_header_frame,
        text="Refresh",
        fg_color="#b22222",
        hover_color="#8b0000",
        font=("Segoe UI", 16, "bold"),
        height=30,
        command=lambda: refresh_modlist(mod_listbox, lml_folder, os.path.join(lml_folder, "mods.xml"), browse_button)
    )
    refresh_mods_button.pack(side="right", padx=10, pady=10)

    open_lml_button = ctk.CTkButton(
        mods_header_frame,
        text="Browse LML Folder",
        fg_color="#b22222",
        hover_color="#8b0000",
        font=("Segoe UI", 16, "bold"),
        height=30,
        command=lambda: open_lml_folder(lml_folder)
    )
    open_lml_button.pack(side="right")

    browse_button = ctk.CTkButton(
        mods_header_frame,
        text="Open Mod Folder",
        state="disabled",
        fg_color="#b22222",
        hover_color="#8b0000",
        font=("Segoe UI", 16, "bold"),
        height=30,
        command=lambda: open_mod_folder(mod_listbox.get(), lml_folder)
    )
    browse_button.pack(side="right", padx=10)
    
    mods_container_frame = ctk.CTkFrame(mods_frame, fg_color="transparent")
    mods_container_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    mod_button_frame = ctk.CTkFrame(mods_container_frame, fg_color="transparent")
    mod_button_frame.pack(side="right", padx=10, pady=10, anchor="center")

    up_button = ctk.CTkButton(
        mod_button_frame,
        text="â–²",
        width=30,
        height=30,
        fg_color="#b22222",
        hover_color="#8b0000",
        command=lambda: move_up(mod_listbox, os.path.join(lml_folder, "mods.xml"))
    )
    up_button.grid(row=0, column=0, padx=5, pady=5)

    down_button = ctk.CTkButton(
        mod_button_frame,
        text="â–¼",
        width=30,
        height=30,
        fg_color="#b22222",
        hover_color="#8b0000",
        command=lambda: move_down(mod_listbox, os.path.join(lml_folder, "mods.xml"))
    )
    down_button.grid(row=1, column=0, padx=5, pady=5)
    
    mod_listbox_font = ctk.CTkFont(family="Segoe UI", size=16)
    
    mod_listbox = CTkListbox(
        mods_container_frame,
        command=lambda x: browse_button.configure(state="normal"),
        height=650,
        width=500,
        highlight_color="#8b0000",
        hover_color="#b22222",
        border_width=2,
        border_color="#545454",
        font=mod_listbox_font
    )
    mod_listbox.pack(side="left", fill="both", expand=True)

    refresh_modlist(mod_listbox, lml_folder, os.path.join(lml_folder, "mods.xml"), browse_button)
    
    # ASI Frame
    asi_header_frame = ctk.CTkFrame(asi_frame)
    asi_header_frame.pack(fill="x", anchor="n", padx=10, pady=(0, 5))
    ctk.CTkLabel(asi_header_frame, text="ASI Mods", font=("Segoe UI", 22, "bold")).pack(side="left", padx=5, pady=10)
    
    refresh_asi_button = ctk.CTkButton(
        asi_header_frame,
        text="Refresh",
        fg_color="#b22222",
        hover_color="#8b0000",
        font=("Segoe UI", 16, "bold"),
        height=30,
        command=lambda: refresh_asi(asi_listbox, lml_folder)
    )
    refresh_asi_button.pack(side="right", padx=10, pady=10)
    
    asi_game_folder_button = ctk.CTkButton(
        asi_header_frame,
        text="Browse RDR2 Folder",
        fg_color="#b22222",
        hover_color="#8b0000",
        font=("Segoe UI", 16, "bold"),
        height=30,
        command=lambda: open_game_folder(lml_folder)
    )
    asi_game_folder_button.pack(side="right")    

    toggle_asi_button = ctk.CTkButton(
        asi_header_frame,
        text="Toggle",
        fg_color="#b22222",
        hover_color="#8b0000",
        font=("Segoe UI", 16, "bold"),
        height=30,
        command=lambda: (toggle_asi_mod(asi_listbox, lml_folder, toggle_asi_button), update_restore_button_state(lml_folder, restore_button), update_clean_button_state(lml_folder, clean_button)),
        state="disabled"
    )
    toggle_asi_button.pack(side="right", padx=10)
    
    asi_container_frame = ctk.CTkFrame(asi_frame, fg_color="transparent")
    asi_container_frame.pack(fill="both", expand=True, padx=10, pady=10)    
    
    asi_listbox = CTkListbox(
        asi_container_frame,
        height=650,
        width=500,
        highlight_color="#8b0000",
        hover_color="#b22222",
        border_width=2,
        border_color="#545454",
        font=mod_listbox_font,
        command=lambda x: toggle_asi_button.configure(state="normal"),
    )
    asi_listbox.pack(side="left", fill="both", expand=True)
    
    refresh_asi(asi_listbox, lml_folder)
    
    
    # Nexus frame
    nexus_header_frame = ctk.CTkFrame(nexus_frame)
    nexus_header_frame.pack(fill="x", anchor="n", padx=10, pady=(0, 5))
    
    if api_key:
        nexus_logout_button = ctk.CTkButton(
            nexus_header_frame,
            text="Logout",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: restart_for_api(api_key=None)
        )
        nexus_logout_button.pack(side="right", padx=10, pady=10)
        
        clean_cache_button = ctk.CTkButton(
            nexus_header_frame,
            text="Clean Nexus Cache",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: [clean_cache(), update_clean_cache_button_state(clean_cache_button)]
        )
        clean_cache_button.pack(side="right")

        update_clean_cache_button_state(clean_cache_button)
        
        setup_nxmproxy_button = ctk.CTkButton(nexus_header_frame, text="Setup NXMProxy", command=lambda: setup_nxmproxy(setup_nxmproxy_button), fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 16, "bold"))
        if not is_nxmproxy_setup():
            setup_nxmproxy_button.pack(side="right", padx=10)
            nxmproxy_tooltip = CTkToolTip(setup_nxmproxy_button, message="This will setup RDMT as the default NXM handler for Red Dead Redemption 2 mods using NXMProxy.").show()
    
    nexus_image_path = os.path.join(image_path, "nexus.webp")
    nexus_image = Image.open(nexus_image_path).convert("RGBA")
    nexus_ctk_image = ctk.CTkImage(dark_image=nexus_image, light_image=nexus_image, size=(135, 36))
    nexus_image_label = ctk.CTkLabel(nexus_header_frame, image=nexus_ctk_image, fg_color="transparent", text="")
    nexus_image_label.pack(side="left", padx=5, pady=10)
    
    nexus_container_frame = ctk.CTkFrame(nexus_frame, fg_color="transparent")
    nexus_container_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    for i in range(7):
        nexus_container_frame.grid_rowconfigure(i, weight=1)
        nexus_container_frame.grid_columnconfigure(i, weight=1)
        
    if api_key:    
        tracked_button = ctk.CTkButton(nexus_container_frame, text="Tracked\nMods", font=("Segoe UI", 18, "bold"), fg_color="#b22222", hover_color="#8b0000", width=250, height=250, border_spacing=10)
        tracked_button.grid(row=2, column=2, pady=30)
        
        updated_button = ctk.CTkButton(nexus_container_frame, text="Recently Updated\n(7 Days)", font=("Segoe UI", 18, "bold"), fg_color="#b22222", hover_color="#8b0000", width=250, height=250, border_spacing=10)
        updated_button.grid(row=2, column=3)
        
        trending_button = ctk.CTkButton(nexus_container_frame, text="Trending\nMods", font=("Segoe UI", 18, "bold"), fg_color="#b22222", hover_color="#8b0000", width=250, height=250, border_spacing=10)
        trending_button.grid(row=3, column=2)
        
        added_button = ctk.CTkButton(nexus_container_frame, text="Recently\nUploaded", font=("Segoe UI", 18, "bold"), fg_color="#b22222", hover_color="#8b0000", width=250, height=250, border_spacing=10)
        added_button.grid(row=3, column=3)
        
        tracked_button.configure(command=lambda: (show_frame(tracked_frame, nexus_button), refresh_tracked(tracked_listbox, tracked_description_textbox, api_key, show_frame, nexus_frame, nexus_button)))
        updated_button.configure(command=lambda: (show_frame(updated_frame, nexus_button), refresh_updated(updated_listbox, updated_description_textbox, api_key, show_frame, nexus_frame, nexus_button)))
        trending_button.configure(command=lambda: (show_frame(trending_frame, nexus_button), refresh_trending(trending_listbox, trending_description_textbox, api_key, show_frame, nexus_frame, nexus_button)))
        added_button.configure(command=lambda: (show_frame(added_frame, nexus_button), refresh_added(added_listbox, added_description_textbox, api_key, show_frame, nexus_frame, nexus_button)))
        
    else:
        nexus_login_button = ctk.CTkButton(nexus_container_frame, text="Login to Nexus Mods", command=lambda: sso_retrieve_api_key(), fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 16, "bold"), width=250, height=250, border_spacing=10)
        nexus_login_button.grid(row=3, column=3, sticky="n", padx=10, pady=10)
    
    def strip_bbcode(text):
        text = re.sub(r'\[img\].*?\[/img\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[.*?\]', '', text)
        return text

    def on_mod_select(listbox, mod_page_button, check_button, download_button, install_button, textbox, container_frame, api_key, cache_category):
        selected_item = listbox.get()
        if not selected_item:
            return

        mod_page_button.configure(state="normal")
        check_button.configure(state="normal")
        download_button.configure(state="normal" if premium_user else "disabled")
        install_button.configure(state="normal" if premium_user else "disabled")

        mod_name = selected_item.split(" (v")[0]

        cache = load_cache(cache_category)
        stored_mod_details = cache.get("mod_details", {})
        mod_details = next((details for details in stored_mod_details.values() if details.get("name") == mod_name), None)

        if mod_details and mod_details.get("description"):
            description = strip_bbcode(mod_details["description"]).replace("<br />", "\n")
            textbox.configure(state="normal")
            textbox.delete("1.0", "end")
            textbox.insert("1.0", description)
            textbox.configure(state="disabled")

            for widget in container_frame.pack_slaves():
                widget.pack_forget()

            listbox.pack(side="left", fill="both", expand=True)
            textbox.pack(side="right", fill="both", expand=True)
        else:
            for widget in container_frame.pack_slaves():
                widget.pack_forget()

            listbox.pack(fill="both", expand=True)

            
    # Tracked frame
    if api_key:
        tracked_header_frame = ctk.CTkFrame(tracked_frame)
        tracked_header_frame.pack(fill="x", anchor="n", padx=10, pady=(0, 5))
        ctk.CTkLabel(tracked_header_frame, text="Tracked Mods", font=("Segoe UI", 22, "bold")).pack(side="left", padx=5, pady=10)
        
        tracked_mod_page_button = ctk.CTkButton(
            tracked_header_frame,
            text="Open Mod Page",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: open_mod_page(tracked_listbox.get(), api_key, 'tracked')
        )
        tracked_mod_page_button.pack(side="right", padx=10, pady=10)
        
        check_tracked_conflicts_button = ctk.CTkButton(
            tracked_header_frame,
            text="Check Conflicts",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: check_nexus_conflicts(tracked_listbox.get(), api_key, 'tracked')
        )
        check_tracked_conflicts_button.pack(side="right")
        
        download_tracked_mod_button = ctk.CTkButton(
            tracked_header_frame,
            text="Download",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: download_mod(tracked_listbox.get(), api_key, 'tracked')
        )
        download_tracked_mod_button.pack(side="right", padx=10)
        
        install_tracked_mod_button = ctk.CTkButton(
            tracked_header_frame,
            text="Install",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: download_mod(tracked_listbox.get(), api_key, 'tracked', install=True)
        )
        install_tracked_mod_button.pack(side="right")
        
        tracked_container_frame = ctk.CTkFrame(tracked_frame, fg_color="transparent")
        tracked_container_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        tracked_listbox = CTkListbox(
            tracked_container_frame,
            command=lambda x: on_mod_select(tracked_listbox, tracked_mod_page_button, check_tracked_conflicts_button, download_tracked_mod_button, install_tracked_mod_button, tracked_description_textbox, tracked_container_frame, api_key, 'tracked'),
            height=650,
            width=500,
            highlight_color="#8b0000",
            hover_color="#b22222",
            border_width=2,
            border_color="#545454",
            font=mod_listbox_font
        )
        tracked_listbox.pack(side="left", fill="both", expand=True)

        tracked_description_textbox = ctk.CTkTextbox(
            tracked_container_frame,
            wrap="word",
            font=("Segoe UI", 14),
            state="disabled"
        )
        tracked_description_textbox.pack_forget()

        if not premium_user:
            tracked_download_tooltip = CTkToolTip(download_tracked_mod_button, message="This feature is available to Nexus Mods Premium users only.\nThis is a decision made by Nexus Mods, not myself.").show()
            tracked_install_tooltip = CTkToolTip(install_tracked_mod_button, message="This feature is available to Nexus Mods Premium users only.\nThis is a decision made by Nexus Mods, not myself.").show()

    # Updated frame
    if api_key:
        updated_header_frame = ctk.CTkFrame(updated_frame)
        updated_header_frame.pack(fill="x", anchor="n", padx=10, pady=(0, 5))
        ctk.CTkLabel(updated_header_frame, text="Recently Updated (7 Days)", font=("Segoe UI", 22, "bold")).pack(side="left", padx=5, pady=10)
        
        updated_mod_page_button = ctk.CTkButton(
            updated_header_frame,
            text="Open Mod Page",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: open_mod_page(updated_listbox.get(), api_key, 'updated')
        )
        updated_mod_page_button.pack(side="right", padx=10, pady=10)
        
        check_updated_conflicts_button = ctk.CTkButton(
            updated_header_frame,
            text="Check Conflicts",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: check_nexus_conflicts(updated_listbox.get(), api_key, 'updated')
        )
        check_updated_conflicts_button.pack(side="right")
        
        download_updated_mod_button = ctk.CTkButton(
            updated_header_frame,
            text="Download",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: download_mod(updated_listbox.get(), api_key, 'updated')
        )
        download_updated_mod_button.pack(side="right", padx=10)\
        
        install_updated_mod_button = ctk.CTkButton(
            updated_header_frame,
            text="Install",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: download_mod(updated_listbox.get(), api_key, 'updated', install=True)
        )
        install_updated_mod_button.pack(side="right")
        
        updated_container_frame = ctk.CTkFrame(updated_frame, fg_color="transparent")
        updated_container_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        updated_listbox = CTkListbox(
            updated_container_frame,
            command=lambda x: on_mod_select(updated_listbox, updated_mod_page_button, check_updated_conflicts_button, download_updated_mod_button, install_updated_mod_button, updated_description_textbox, updated_container_frame, api_key, 'updated'),
            height=650,
            width=500,
            highlight_color="#8b0000",
            hover_color="#b22222",
            border_width=2,
            border_color="#545454",
            font=mod_listbox_font
        )
        updated_listbox.pack(side="left", fill="both", expand=True)
        
        updated_description_textbox = ctk.CTkTextbox(
            updated_container_frame,
            wrap="word",
            font=("Segoe UI", 14),
            state="disabled"
        )
        updated_description_textbox.pack_forget()
            
        if not premium_user:
            updated_download_tooltip = CTkToolTip(download_updated_mod_button, message="This feature is available to Nexus Mods Premium users only.\nThis is a decision made by Nexus Mods, not myself.").show()
            updated_install_tooltip = CTkToolTip(install_updated_mod_button, message="This feature is available to Nexus Mods Premium users only.\nThis is a decision made by Nexus Mods, not myself.").show()
            
    # Trending frame
    if api_key:
        trending_header_frame = ctk.CTkFrame(trending_frame)
        trending_header_frame.pack(fill="x", anchor="n", padx=10, pady=(0, 5))
        ctk.CTkLabel(trending_header_frame, text="Trending Mods", font=("Segoe UI", 22, "bold")).pack(side="left", padx=5, pady=10)
        
        trending_mod_page_button = ctk.CTkButton(
            trending_header_frame,
            text="Open Mod Page",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: open_mod_page(trending_listbox.get(), api_key, 'trending')
        )
        trending_mod_page_button.pack(side="right", padx=10, pady=10)
        
        check_trending_conflicts_button = ctk.CTkButton(
            trending_header_frame,
            text="Check Conflicts",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: check_nexus_conflicts(trending_listbox.get(), api_key, 'trending')
        )
        check_trending_conflicts_button.pack(side="right")
        
        download_trending_mod_button = ctk.CTkButton(
            trending_header_frame,
            text="Download",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: download_mod(trending_listbox.get(), api_key, 'trending')
        )
        download_trending_mod_button.pack(side="right", padx=10)
        
        install_trending_mod_button = ctk.CTkButton(
            trending_header_frame,
            text="Install",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: download_mod(trending_listbox.get(), api_key, 'trending', install=True)
        )
        install_trending_mod_button.pack(side="right")
        
        trending_container_frame = ctk.CTkFrame(trending_frame, fg_color="transparent")
        trending_container_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        trending_listbox = CTkListbox(
            trending_container_frame,
            command=lambda x: on_mod_select(trending_listbox, trending_mod_page_button, check_trending_conflicts_button, download_trending_mod_button, install_trending_mod_button, trending_description_textbox, trending_container_frame, api_key, 'trending'),
            height=650,
            width=500,
            highlight_color="#8b0000",
            hover_color="#b22222",
            border_width=2,
            border_color="#545454",
            font=mod_listbox_font
        )
        trending_listbox.pack(side="left", fill="both", expand=True)
        
        trending_description_textbox = ctk.CTkTextbox(
            trending_container_frame,
            wrap="word",
            font=("Segoe UI", 14),
            state="disabled"
        )
        trending_description_textbox.pack_forget()
            
        if not premium_user:
            trending_download_tooltip = CTkToolTip(download_trending_mod_button, message="This feature is available to Nexus Mods Premium users only.\nThis is a decision made by Nexus Mods, not myself.").show()
            trending_install_tooltip = CTkToolTip(install_trending_mod_button, message="This feature is available to Nexus Mods Premium users only.\nThis is a decision made by Nexus Mods, not myself.").show()
            
    # Added frame
    if api_key:
        added_header_frame = ctk.CTkFrame(added_frame)
        added_header_frame.pack(fill="x", anchor="n", padx=10, pady=(0, 5))
        ctk.CTkLabel(added_header_frame, text="Recently Uploaded", font=("Segoe UI", 22, "bold")).pack(side="left", padx=5, pady=10)
        
        added_mod_page_button = ctk.CTkButton(
            added_header_frame,
            text="Open Mod Page",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: open_mod_page(added_listbox.get(), api_key, 'added')
        )
        added_mod_page_button.pack(side="right", padx=10, pady=10)
        
        check_added_conflicts_button = ctk.CTkButton(
            added_header_frame,
            text="Check Conflicts",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: check_nexus_conflicts(added_listbox.get(), api_key, 'added')
        )
        check_added_conflicts_button.pack(side="right")
        
        download_added_mod_button = ctk.CTkButton(
            added_header_frame,
            text="Download",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: download_mod(added_listbox.get(), api_key, 'added')
        )
        download_added_mod_button.pack(side="right", padx=10)
        
        install_added_mod_button = ctk.CTkButton(
            added_header_frame,
            text="Install",
            state="disabled",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 16, "bold"),
            height=30,
            command=lambda: download_mod(added_listbox.get(), api_key, 'added', install=True)
        )
        install_added_mod_button.pack(side="right")        
        
        added_container_frame = ctk.CTkFrame(added_frame, fg_color="transparent")
        added_container_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        added_listbox = CTkListbox(
            added_container_frame,
            command=lambda x: on_mod_select(added_listbox, added_mod_page_button, check_added_conflicts_button, download_added_mod_button, install_added_mod_button, added_description_textbox, added_container_frame, api_key, 'added'),
            height=650,
            width=500,
            highlight_color="#8b0000",
            hover_color="#b22222",
            border_width=2,
            border_color="#545454",
            font=mod_listbox_font
        )
        added_listbox.pack(side="left", fill="both", expand=True)
        
        added_description_textbox = ctk.CTkTextbox(
            added_container_frame,
            wrap="word",
            font=("Segoe UI", 14),
            state="disabled"
        )
        added_description_textbox.pack_forget()
            
        if not premium_user:
            added_download_tooltip = CTkToolTip(download_added_mod_button, message="This feature is available to Nexus Mods Premium users only.\nThis is a decision made by Nexus Mods, not myself.").show()
            added_install_tooltip = CTkToolTip(install_added_mod_button, message="This feature is available to Nexus Mods Premium users only.\nThis is a decision made by Nexus Mods, not myself.").show()
            
    # Conflicts frame

    conflicts_header_frame = ctk.CTkFrame(conflicts_frame)
    conflicts_header_frame.pack(fill="x", anchor="n", padx=10, pady=(0, 5))
    ctk.CTkLabel(conflicts_header_frame, text="Conflicts", font=("Segoe UI", 22, "bold")).pack(side="left", padx=5, pady=10)
    
    refresh_conflicts_button = ctk.CTkButton(
        conflicts_header_frame,
        text="Refresh",
        fg_color="#b22222",
        hover_color="#8b0000",
        font=("Segoe UI", 16, "bold"),
        height=30,
        command=lambda: refresh_conflicts(conflict_text, conflicts, lml_folder)
    )
    refresh_conflicts_button.pack(side="right", padx=10, pady=10)
    
    export_conflicts_button = ctk.CTkButton(
        conflicts_header_frame,
        text="Export",
        fg_color="#b22222",
        hover_color="#8b0000",
        font=("Segoe UI", 16, "bold"),
        height=30,
        command=lambda: export_conflicts(conflict_text)
    )
    export_conflicts_button.pack(side="right")
    
    safe_mods_button = ctk.CTkButton(
        conflicts_header_frame,
        text="Safe Mods",
        fg_color="#b22222",
        hover_color="#8b0000",
        font=("Segoe UI", 16, "bold"),
        height=30,
        command=lambda: manage_safe_mods_dialog(main_window, lml_folder, conflict_text, conflicts)
    )
    safe_mods_button.pack(side="right", padx=10)
    safe_mods_tooltip = CTkToolTip(safe_mods_button, message="Mark mods as safe to exclude them from conflict detection.")
    
    conflicts_container_frame = ctk.CTkFrame(conflicts_frame, fg_color="transparent")
    conflicts_container_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    conflict_text = ctk.CTkTextbox(conflicts_container_frame, wrap="none", font=("Segoe UI", 17), height=650, width=500, border_width=2, border_color="#545454")
    conflict_text.pack(side="left", fill="both", expand=True)

    if conflicts:
        refresh_conflicts(conflict_text, conflicts, lml_folder)
    else:
        conflict_text.insert(ctk.END, "No conflicts found.")

    conflict_text.configure(state=ctk.DISABLED)
    
    
    # Merge frame

    def auto_merge(fileA_path, fileB_path, main_window):
        """Merge two files using proper 3-way merge (with original game file) or manual 2-way merge."""
        stop_thread = threading.Event()

        def merge_files():
            progress_dialog = None
            try:
                merge_mode = None
                def ask_merge_mode():
                    nonlocal merge_mode
                    merge_mode = merge_mode_dialog(main_window)

                main_window.after(0, ask_merge_mode)
                while merge_mode is None:
                    if stop_thread.is_set():
                        return
                    time.sleep(0.1)

                if merge_mode == "cancel":
                    return

                fileA_lines, enc_a = safe_read_file(fileA_path.get(), as_lines=True)
                fileB_lines, enc_b = safe_read_file(fileB_path.get(), as_lines=True)
                write_encoding = enc_a if enc_a != "latin-1" else enc_b if enc_b != "latin-1" else "latin-1"

                merged_lines = []
                conflicts = []

                if merge_mode == "auto-merge":
                    original_file = None
                    def ask_original_file():
                        nonlocal original_file
                        original_file = filedialog.askopenfilename(
                            title="Select the Original Game File",
                            filetypes=[("All Files", "*.*")]
                        )

                    main_window.after(0, ask_original_file)
                    while original_file is None:
                        if stop_thread.is_set():
                            return
                        time.sleep(0.1)

                    if not original_file:
                        return

                    fileC_lines, _ = safe_read_file(original_file, as_lines=True)

                    progress_ready = threading.Event()
                    progress_bar_holder = [None]
                    progress_dialog_holder = [None]

                    def show_progress():
                        dlg = ctk.CTkToplevel(main_window)
                        dlg.title("Merging Files...")
                        dlg.attributes('-topmost', True)
                        dlg.focus_set()
                        dlg.grab_set()

                        screen_width = dlg.winfo_screenwidth()
                        screen_height = dlg.winfo_screenheight()
                        initial_width = min(400, int(screen_width * 0.9))
                        initial_height = min(50, int(screen_height * 0.9))
                        x = max(0, (screen_width - initial_width) // 2)
                        y = max(0, (screen_height - initial_height) // 2)
                        dlg.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
                        dlg.resizable(False, False)

                        icon_path = os.path.join(image_path, "rdmt.ico")
                        dlg.after(201, lambda: dlg.iconbitmap(icon_path))

                        pbar = ctk.CTkProgressBar(dlg, width=300, progress_color="#b22222")
                        pbar.pack(pady=10)
                        pbar.set(0)

                        def on_close():
                            stop_thread.set()
                            dlg.destroy()

                        dlg.protocol("WM_DELETE_WINDOW", on_close)
                        progress_bar_holder[0] = pbar
                        progress_dialog_holder[0] = dlg
                        progress_ready.set()

                    main_window.after(0, show_progress)
                    progress_ready.wait()
                    progress_dialog = progress_dialog_holder[0]

                    if stop_thread.is_set():
                        return

                    main_window.after(0, lambda: progress_bar_holder[0].set(0.1))

                    merged_lines, conflicts = three_way_merge(
                        fileC_lines, fileA_lines, fileB_lines, conflict_resolution='A'
                    )

                    if stop_thread.is_set():
                        return

                    main_window.after(0, lambda: progress_bar_holder[0].set(0.7))

                    if conflicts:
                        resolution_mode = None
                        def ask_resolution_mode():
                            nonlocal resolution_mode
                            resolution_mode = conflict_resolution_mode_dialog(main_window)

                        main_window.after(0, ask_resolution_mode)
                        while resolution_mode is None:
                            if stop_thread.is_set():
                                return
                            time.sleep(0.1)

                        if resolution_mode == "cancel":
                            main_window.after(0, progress_dialog.destroy)
                            return

                        if resolution_mode in ("A", "B", "original"):
                            merged_lines, conflicts = three_way_merge(
                                fileC_lines, fileA_lines, fileB_lines,
                                conflict_resolution=resolution_mode
                            )
                        elif resolution_mode == "manual":
                            merged_lines = []

                            sm_a = SequenceMatcher(None, fileC_lines, fileA_lines, autojunk=False)
                            sm_b = SequenceMatcher(None, fileC_lines, fileB_lines, autojunk=False)
                            matches_a = sm_a.get_matching_blocks()
                            matches_b = sm_b.get_matching_blocks()

                            sync_regions = []
                            for ma in matches_a:
                                if ma.size == 0:
                                    continue
                                for mb in matches_b:
                                    if mb.size == 0:
                                        continue
                                    start = max(ma.a, mb.a)
                                    end = min(ma.a + ma.size, mb.a + mb.size)
                                    if start < end:
                                        a_start = ma.b + (start - ma.a)
                                        b_start = mb.b + (start - mb.a)
                                        sync_regions.append((start, a_start, b_start, end - start))

                            sync_regions.sort(key=lambda x: x[0])
                            cleaned = []
                            for region in sync_regions:
                                if cleaned and region[0] < cleaned[-1][0] + cleaned[-1][3]:
                                    if region[3] > cleaned[-1][3]:
                                        cleaned[-1] = region
                                else:
                                    cleaned.append(region)
                            sync_regions = cleaned

                            base_pos = 0
                            a_pos = 0
                            b_pos = 0

                            for base_sync, a_sync, b_sync, size in sync_regions:
                                if stop_thread.is_set():
                                    return

                                base_gap = fileC_lines[base_pos:base_sync]
                                a_gap = fileA_lines[a_pos:a_sync]
                                b_gap = fileB_lines[b_pos:b_sync]

                                if a_gap == b_gap:
                                    merged_lines.extend(a_gap)
                                elif a_gap == base_gap:
                                    merged_lines.extend(b_gap)
                                elif b_gap == base_gap:
                                    merged_lines.extend(a_gap)
                                else:
                                    choice = None
                                    def ask_manual(a=a_gap, b=b_gap):
                                        nonlocal choice
                                        choice = manual_conflict_resolution_dialog(main_window, a, b)

                                    main_window.after(0, ask_manual)
                                    while choice is None:
                                        if stop_thread.is_set():
                                            return
                                        time.sleep(0.1)

                                    if choice == "A":
                                        merged_lines.extend(a_gap)
                                    elif choice == "B":
                                        merged_lines.extend(b_gap)
                                    elif choice == "cancel":
                                        main_window.after(0, progress_dialog.destroy)
                                        return
                                    else:
                                        merged_lines.extend(a_gap)

                                merged_lines.extend(fileC_lines[base_sync:base_sync + size])
                                base_pos = base_sync + size
                                a_pos = a_sync + size
                                b_pos = b_sync + size

                            base_gap = fileC_lines[base_pos:]
                            a_gap = fileA_lines[a_pos:]
                            b_gap = fileB_lines[b_pos:]

                            if a_gap == b_gap:
                                merged_lines.extend(a_gap)
                            elif a_gap == base_gap:
                                merged_lines.extend(b_gap)
                            elif b_gap == base_gap:
                                merged_lines.extend(a_gap)
                            else:
                                choice = None
                                def ask_manual_tail(a=a_gap, b=b_gap):
                                    nonlocal choice
                                    choice = manual_conflict_resolution_dialog(main_window, a, b)

                                main_window.after(0, ask_manual_tail)
                                while choice is None:
                                    if stop_thread.is_set():
                                        return
                                    time.sleep(0.1)

                                if choice == "A":
                                    merged_lines.extend(a_gap)
                                elif choice == "B":
                                    merged_lines.extend(b_gap)
                                else:
                                    merged_lines.extend(a_gap)

                    main_window.after(0, lambda: progress_bar_holder[0].set(1.0))
                    main_window.after(0, progress_dialog.destroy)

                elif merge_mode == "manual":
                    def manual_conflict_resolution(lines_a, lines_b):
                        choice = None

                        def ask_conflict_resolution():
                            nonlocal choice
                            choice = manual_conflict_resolution_dialog(main_window, lines_a, lines_b)

                        main_window.after(0, ask_conflict_resolution)
                        while choice is None:
                            if stop_thread.is_set():
                                return None
                            time.sleep(0.1)

                        return choice

                    matcher_a_to_b = SequenceMatcher(None, fileA_lines, fileB_lines, autojunk=False)

                    for tag, i1, i2, j1, j2 in matcher_a_to_b.get_opcodes():
                        if stop_thread.is_set():
                            return

                        if tag == "equal":
                            merged_lines.extend(fileA_lines[i1:i2])
                        elif tag == "replace":
                            block_a = fileA_lines[i1:i2]
                            block_b = fileB_lines[j1:j2]
                            choice = manual_conflict_resolution(block_a, block_b)
                            if choice == "A":
                                merged_lines.extend(block_a)
                            elif choice == "B":
                                merged_lines.extend(block_b)
                            elif choice == "cancel":
                                return
                            else:
                                merged_lines.extend(block_a)
                                merged_lines.extend(block_b)
                        elif tag == "delete":
                            merged_lines.extend(fileA_lines[i1:i2])
                        elif tag == "insert":
                            merged_lines.extend(fileB_lines[j1:j2])

                default_file_name = os.path.basename(fileA_path.get())
                file_extension = os.path.splitext(default_file_name)[-1]
                filetypes = [(f"{file_extension.upper()} Files", f"*{file_extension}"), ("All Files", "*.*")]
                save_path = None
                def ask_save_path():
                    nonlocal save_path
                    save_path = filedialog.asksaveasfilename(
                        title="Save Merged File",
                        defaultextension=file_extension,
                        initialfile=default_file_name,
                        filetypes=filetypes
                    )

                main_window.after(0, ask_save_path)
                while save_path is None:
                    if stop_thread.is_set():
                        return
                    time.sleep(0.1)

                if save_path:
                    with open(save_path, "w", encoding=write_encoding) as f_out:
                        f_out.writelines(merged_lines)

                    conflict_msg = ""
                    if conflicts:
                        conflict_msg = f"\n\n{len(conflicts)} conflict(s) were resolved."

                    main_window.after(0, lambda: CTkMessagebox(
                        title="Red Dead Modding Tool",
                        message=f"Files merged successfully to:\n{save_path}{conflict_msg}",
                        button_color="#b22222",
                        button_hover_color="#8b0000",
                        fade_in_duration=0.05
                    ))

            except Exception as exc:
                error_msg = str(exc)
                if progress_dialog:
                    main_window.after(0, progress_dialog.destroy)
                main_window.after(0, lambda msg=error_msg: CTkMessagebox(
                    title="Error",
                    message=f"An error occurred during the merge:\n{msg}",
                    button_color="#b22222",
                    button_hover_color="#8b0000",
                    fade_in_duration=0.05,
                    icon="cancel"
                ))

        threading.Thread(target=merge_files, daemon=True).start()

    def merge_mode_dialog(main_window):
        """Ask the user to select between manual conflict resolution or auto-merge."""
        dialog = ctk.CTkToplevel(main_window)
        
        dialog.withdraw()
        
        dialog.title("Merge Mode")
        
        dialog.focus_set()
        dialog.grab_set()
        
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        initial_width = min(480, int(screen_width * 0.9))
        initial_height = min(100, int(screen_height * 0.9))

        x = max(0, (screen_width - initial_width) // 2)
        y = max(0, (screen_height - initial_height) // 2)

        dialog.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
        dialog.wm_minsize(initial_width, initial_height)
        dialog.resizable(False, False)
        
        icon_path = os.path.join(image_path, "rdmt.ico")
        dialog.after(201, lambda: dialog.iconbitmap(icon_path))

        result = {"choice": "cancel"}

        def set_choice(choice):
            result["choice"] = choice
            dialog.destroy()

        ctk.CTkLabel(dialog, text="Choose merge mode:", font=("Segoe UI", 14, "bold")).grid(row=0, column=1, padx=10, pady=10)
        
        ctk.CTkButton(dialog, text="Auto-Merge", command=lambda: set_choice("auto-merge"), fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 14, "bold")).grid(row=1, column=0, padx=10)
        ctk.CTkButton(dialog, text="Manual Merge", command=lambda: set_choice("manual"), fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 14, "bold")).grid(row=1, column=1, padx=10)
        ctk.CTkButton(dialog, text="Cancel", command=lambda: set_choice("cancel"), fg_color="darkgrey", hover_color="grey", font=("Segoe UI", 14, "bold")).grid(row=1, column=2, padx=10)

        dialog.transient(main_window)
        dialog.grab_set()
        dialog.deiconify()
        dialog.wait_window()

        return result["choice"]

    def conflict_resolution_mode_dialog(main_window):
        """Display a dialog to select the conflict resolution mode."""
        dialog = ctk.CTkToplevel(main_window)
        
        dialog.withdraw()
        
        dialog.title("Conflict Resolution Mode")
        
        dialog.focus_set()
        dialog.grab_set()

        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        initial_width = min(720, int(screen_width * 0.9))
        initial_height = min(150, int(screen_height * 0.9))

        x = max(0, (screen_width - initial_width) // 2)
        y = max(0, (screen_height - initial_height) // 2)

        dialog.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
        dialog.wm_minsize(initial_width, initial_height)
        dialog.resizable(False, False)
        
        icon_path = os.path.join(image_path, "rdmt.ico")
        dialog.after(201, lambda: dialog.iconbitmap(icon_path))

        result = {"choice": "cancel"}

        def set_choice(choice):
            result["choice"] = choice
            dialog.destroy()

        label = ctk.CTkLabel(
            dialog,
            text="Both mods edit the same lines. Select how you want to resolve conflicts:",
            font=("Segoe UI", 14, "bold"),
            wraplength=550
        )
        label.pack(pady=20)

        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=10)

        ctk.CTkButton(button_frame, text="Always File A", fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 14, "bold"), command=lambda: set_choice("A")).grid(row=0, column=0, padx=10)
        ctk.CTkButton(button_frame, text="Always File B", fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 14, "bold"), command=lambda: set_choice("B")).grid(row=0, column=1, padx=10)
        ctk.CTkButton(button_frame, text="Keep Original", fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 14, "bold"), command=lambda: set_choice("original")).grid(row=0, column=2, padx=10)
        ctk.CTkButton(button_frame, text="Resolve Manually", fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 14, "bold"), command=lambda: set_choice("manual")).grid(row=0, column=3, padx=10)

        dialog.transient(main_window)
        dialog.grab_set()
        dialog.deiconify()
        dialog.wait_window()

        return result["choice"]

    def manual_conflict_resolution_dialog(main_window, fileA_lines, fileB_lines):
        """Display a dialog to manually resolve a conflict."""
        dialog = ctk.CTkToplevel(main_window)
        
        dialog.withdraw()
        
        dialog.title("Resolve Conflict")
        
        dialog.focus_set()
        dialog.grab_set()

        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        initial_width = min(800, int(screen_width * 0.9))
        initial_height = min(400, int(screen_height * 0.9))

        x = max(0, (screen_width - initial_width) // 2)
        y = max(0, (screen_height - initial_height) // 2)

        dialog.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
        dialog.wm_minsize(initial_width, initial_height)
        dialog.resizable(True, True)
        
        icon_path = os.path.join(image_path, "rdmt.ico")
        dialog.after(201, lambda: dialog.iconbitmap(icon_path))

        result = {"choice": "cancel"}

        def set_choice(choice):
            result["choice"] = choice
            dialog.destroy()

        label = ctk.CTkLabel(
            dialog,
            text="A conflict has been detected. Choose which version to keep:",
            font=("Segoe UI", 14, "bold"),
            wraplength=550
        )
        label.pack(pady=10)

        text_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)

        fileA_textbox = ctk.CTkTextbox(
            text_frame, wrap="none", font=("Segoe UI", 12), height=150
        )
        fileA_textbox.insert("1.0", "".join(fileA_lines))
        fileA_textbox.configure(state="disabled")
        fileA_textbox.pack(side="left", fill="both", expand=True, padx=5)

        fileB_textbox = ctk.CTkTextbox(
            text_frame, wrap="none", font=("Segoe UI", 12), height=150
        )
        fileB_textbox.insert("1.0", "".join(fileB_lines))
        fileB_textbox.configure(state="disabled")
        fileB_textbox.pack(side="right", fill="both", expand=True, padx=5)

        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=10)

        file_a_button = ctk.CTkButton(
            button_frame,
            text="Keep File A",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 14, "bold"),
            command=lambda: set_choice("A")
        )
        file_a_button.grid(row=0, column=0, padx=10)

        file_b_button = ctk.CTkButton(
            button_frame,
            text="Keep File B",
            fg_color="#b22222",
            hover_color="#8b0000",
            font=("Segoe UI", 14, "bold"),
            command=lambda: set_choice("B")
        )
        file_b_button.grid(row=0, column=1, padx=10)

        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            fg_color="darkgray",
            hover_color="gray",
            font=("Segoe UI", 14, "bold"),
            command=lambda: set_choice("cancel")
        )
        cancel_button.grid(row=0, column=2, padx=10)

        dialog.transient(main_window)
        dialog.grab_set()
        dialog.deiconify()
        dialog.wait_window()

        return result["choice"]

    merge_header_frame = ctk.CTkFrame(merge_frame)
    merge_header_frame.pack(fill="x", anchor="n", padx=10, pady=(0, 5))
    ctk.CTkLabel(merge_header_frame, text="Merge (BETA)", font=("Segoe UI", 22, "bold")).pack(side="left", padx=10, pady=10)
    ctk.CTkLabel(merge_header_frame, text="Auto-Merge requires original game file. More information on Nexus Mods.", font=("Segoe UI", 16), text_color="grey").pack(side="left", padx=10, pady=(3,0))
    
    auto_merge_button = ctk.CTkButton(
        merge_header_frame,
        text="Merge",
        fg_color="#b22222",
        hover_color="#8b0000",
        font=("Segoe UI", 16, "bold"),
        height=30,
        state="disabled",
        command=lambda: auto_merge(fileA_path, fileB_path, main_window)
    )
    auto_merge_button.pack(side="right", padx=10, pady=10)
    
    fileA_frame = ctk.CTkFrame(merge_frame, border_width=2, border_color="#545454")
    fileA_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

    fileB_frame = ctk.CTkFrame(merge_frame, border_width=2, border_color="#545454")
    fileB_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    fileA_label = ctk.CTkLabel(fileA_frame, text="File A:", font=("Segoe UI", 16, "bold"))
    fileA_label.pack(anchor="nw", padx=10, pady=(10, 5))

    fileA_path = ctk.CTkEntry(fileA_frame, width=400, font=("Segoe UI", 14, "bold"))
    fileA_path.pack(anchor="nw", padx=10, pady=(0, 5))

    browse_fileA_button = ctk.CTkButton(
        fileA_frame, text="Browse", fg_color="#b22222", hover_color="#8b0000",
        font=("Segoe UI", 16, "bold"), command=lambda: browse_file(fileA_path, fileA_textbox)
    )
    browse_fileA_button.pack(anchor="nw", padx=10, pady=(5, 10))

    fileA_textbox = ctk.CTkTextbox(fileA_frame, wrap="none", font=("Segoe UI", 14), height=650, state="disabled", cursor="arrow")
    fileA_textbox.pack(side="right", fill="both", expand=True, padx=10, pady=10)
    
    fileA_linenums = TkLineNumbers(fileA_frame, fileA_textbox, justify="right", border=False, width=5, colors=("#7f7f7f", "#2b2b2b"))
    fileA_linenums.pack(side="left", fill="y", padx=(10,0), pady=10)

    fileA_textbox.bind("<<Modified>>", lambda event: main_window.after_idle(fileA_linenums.redraw), add=True)
    
    fileA_textbox.bind("<Button-1>", lambda e: "break")
    fileA_textbox.bind("<B1-Motion>", lambda e: "break")
    fileA_textbox.bind("<Control-a>", lambda e: "break")
    fileA_textbox.bind("<Shift-Left>", lambda e: "break")
    fileA_textbox.bind("<Shift-Right>", lambda e: "break")

    fileB_label = ctk.CTkLabel(fileB_frame, text="File B:", font=("Segoe UI", 16, "bold"))
    fileB_label.pack(anchor="nw", padx=10, pady=(10, 5))

    fileB_path = ctk.CTkEntry(fileB_frame, width=400, font=("Segoe UI", 14, "bold"))
    fileB_path.pack(anchor="nw", padx=10, pady=(0, 5))

    browse_fileB_button = ctk.CTkButton(
        fileB_frame, text="Browse", fg_color="#b22222", hover_color="#8b0000",
        font=("Segoe UI", 16, "bold"), command=lambda: browse_file(fileB_path, fileB_textbox)
    )
    browse_fileB_button.pack(anchor="nw", padx=10, pady=(5, 10))

    fileB_textbox = ctk.CTkTextbox(fileB_frame, wrap="none", font=("Segoe UI", 14), height=650, state="disabled", cursor="arrow")
    fileB_textbox.pack(side="right", fill="both", expand=True, padx=10, pady=10)
    
    fileB_linenums = TkLineNumbers(fileB_frame, fileB_textbox, justify="right", border=False, width=5, colors=("#7f7f7f", "#2b2b2b"))
    fileB_linenums.pack(side="left", fill="y", padx=(10,0), pady=10)
    
    fileB_textbox.bind("<<Modified>>", lambda event: main_window.after_idle(fileB_linenums.redraw), add=True)
    
    fileB_textbox.bind("<Button-1>", lambda e: "break")
    fileB_textbox.bind("<B1-Motion>", lambda e: "break")
    fileB_textbox.bind("<Control-a>", lambda e: "break")
    fileB_textbox.bind("<Shift-Left>", lambda e: "break")
    fileB_textbox.bind("<Shift-Right>", lambda e: "break")

    def browse_file(entry_field, textbox):
        """Open file dialog, load file path into entry, and display contents in textbox."""
        file_path = filedialog.askopenfilename(title="Select a file to merge")
        
        if file_path:
            entry_field.delete(0, ctk.END)
            entry_field.insert(0, file_path)
            entry_field.xview_moveto(1.0)

            textbox.configure(state="normal", cursor="")
            textbox.unbind("<Button-1>", None)
            textbox.unbind("<B1-Motion>", None)
            textbox.unbind("<Control-a>", None)
            textbox.unbind("<Shift-Left>", None)
            textbox.unbind("<Shift-Right>", None)
            textbox.delete("1.0", ctk.END)
            try:
                content, _ = safe_read_file(file_path)
                textbox.insert("1.0", content)
            except Exception as read_err:
                textbox.insert("1.0", f"Error reading file: {read_err}")
            textbox.configure(state="disabled")
        
            update_merge_state()
    
    DIFF_PREVIEW_LINE_LIMIT = 10000
    
    def update_merge_state():
        """Enable the merge button as soon as both files are selected, and optionally run a diff preview."""
        path1 = fileA_path.get().strip()
        path2 = fileB_path.get().strip()
        
        if path1 and path2 and os.path.isfile(path1) and os.path.isfile(path2):
            auto_merge_button.configure(state="normal")
            threading.Thread(target=run_diff_preview, args=(path1, path2), daemon=True).start()
        else:
            auto_merge_button.configure(state="disabled")

    def run_diff_preview(path_a, path_b):
        """Compute a diff preview in a background thread, then push results to UI."""
        try:
            content_a, _ = safe_read_file(path_a)
            content_b, _ = safe_read_file(path_b)
            lines_a = content_a.splitlines()
            lines_b = content_b.splitlines()
            
            if len(lines_a) + len(lines_b) > DIFF_PREVIEW_LINE_LIMIT:
                print(f"Skipping diff preview: files too large")
                return
            
            matcher = SequenceMatcher(None, lines_a, lines_b)
            opcodes = matcher.get_opcodes()
            
            set_a = set(lines_a)
            set_b = set(lines_b)
            
            a_segments = []
            b_segments = []
            
            for tag, i1, i2, j1, j2 in opcodes:
                if tag == "equal":
                    chunk = "\n".join(lines_a[i1:i2])
                    a_segments.append((chunk + "\n", None))
                    b_segments.append((chunk + "\n", None))
                elif tag == "replace":
                    a_segments.append(("\n".join(lines_a[i1:i2]) + "\n", "conflict"))
                    b_segments.append(("\n".join(lines_b[j1:j2]) + "\n", "conflict"))
                elif tag == "delete":
                    for line in lines_a[i1:i2]:
                        t = "unique" if line not in set_b else None
                        a_segments.append((line + "\n", t))
                elif tag == "insert":
                    for line in lines_b[j1:j2]:
                        t = "unique" if line not in set_a else None
                        b_segments.append((line + "\n", t))
            
            if fileA_path.get().strip() == path_a and fileB_path.get().strip() == path_b:
                main_window.after(0, lambda: apply_diff_to_ui(a_segments, b_segments))
            
        except Exception as diff_err:
            print(f"Diff preview error: {diff_err}")
    
    def apply_diff_to_ui(a_segments, b_segments):
        """Apply pre-computed diff highlighting to the textboxes (runs on main thread)."""
        try:
            fileA_textbox.configure(state="normal")
            fileB_textbox.configure(state="normal")
            
            fileA_textbox.delete("1.0", "end")
            fileB_textbox.delete("1.0", "end")

            fileA_textbox.tag_config("unique", foreground="#4488ff")
            fileB_textbox.tag_config("unique", foreground="#4488ff")
            fileA_textbox.tag_config("conflict", foreground="#ff4444")
            fileB_textbox.tag_config("conflict", foreground="#ff4444")
            
            for text, t in a_segments:
                if t:
                    fileA_textbox.insert("end", text, t)
                else:
                    fileA_textbox.insert("end", text)

            for text, t in b_segments:
                if t:
                    fileB_textbox.insert("end", text, t)
                else:
                    fileB_textbox.insert("end", text)
            
            fileA_textbox.configure(state="disabled")
            fileB_textbox.configure(state="disabled")
            
            try:
                fileA_linenums.redraw()
                fileB_linenums.redraw()
            except Exception:
                pass
        except Exception as ui_err:
            print(f"Error applying diff to UI: {ui_err}")
        
        
    # Settings frame
    
    settings_header_frame = ctk.CTkFrame(settings_frame)
    settings_header_frame.pack(fill="x", anchor="n", padx=10, pady=(0, 5))
    ctk.CTkLabel(settings_header_frame, text="Settings", font=("Segoe UI", 22, "bold")).pack(side="left", padx=5, pady=10)
    
    settings_game_folder_button = ctk.CTkButton(
        settings_header_frame,
        text="Browse RDR2 Folder",
        fg_color="#b22222",
        hover_color="#8b0000",
        font=("Segoe UI", 16, "bold"),
        height=30,
        command=lambda: open_game_folder(lml_folder)
    )
    settings_game_folder_button.pack(side="right", padx=10, pady=10)
    
    settings_container_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
    settings_container_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    lml_path_label = ctk.CTkLabel(settings_container_frame, text="RDR2 Folder Path:", font=("Segoe UI", 17, "bold"))
    lml_path_label.grid(row=0, column=0, sticky="nw", padx=10, pady=10)
    lml_path_entry = ctk.CTkEntry(settings_container_frame, width=500, font=("Segoe UI", 16))
    lml_path_entry.grid(row=0, column=1, sticky="nw", padx=10, pady=10)
    lml_path = config["path"]
    if lml_path and lml_path.lower().endswith("\\lml"):
        lml_path = lml_path[:-4]
    lml_path_entry.insert(0, lml_path if lml_path else "")
    lml_browse_button = ctk.CTkButton(settings_container_frame, text="Browse", command=lambda: browse_folder(lml_path_entry), fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 16, "bold"))
    lml_browse_button.grid(row=0, column=2, sticky="nw", padx=10, pady=10)
    lml_restart_button = ctk.CTkButton(settings_container_frame, text="Apply", command=lambda: restart_for_lml(lml_path_entry), fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 16, "bold"))
    lml_restart_button.grid(row=1, column=2, sticky="n")
    
    appearance_mode_label = ctk.CTkLabel(settings_container_frame, text="Theme:", font=("Segoe UI", 18, "bold"))
    appearance_mode_label.grid(row=3, column=0, sticky="nw", padx=10, pady=10)
    appearance_mode_menu = ctk.CTkOptionMenu(
        settings_container_frame,
        values=["Light", "Dark", "System"],
        command=change_appearance_mode,
        fg_color="#b22222",
        button_color="#b22222",
        button_hover_color="#8b0000",
        font=("Segoe UI", 16, "bold"),
        dropdown_text_color="white",
        dropdown_fg_color="#2b2b2b"
    )
    appearance_mode_menu.grid(row=3, column=1, sticky="nw", padx=10, pady=10)
    appearance_mode_menu.set(load_config()["theme"])
    
    restore_button = ctk.CTkButton(settings_container_frame, text="Enable All Mods", command=lambda: [restore_mods(lml_folder), update_restore_button_state(lml_folder, restore_button), update_clean_button_state(lml_folder, clean_button)], fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 16, "bold"))
    restore_button.grid(row=5, column=0, sticky="n", pady=(50, 15))
    
    clean_button = ctk.CTkButton(settings_container_frame, text="Disable All Mods", command=lambda: [clean_mods(lml_folder), update_restore_button_state(lml_folder, restore_button), update_clean_button_state(lml_folder, clean_button)], fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 16, "bold"))
    clean_button.grid(row=5, column=1, sticky="nw", pady=(50, 15), padx=10)
    
    update_clean_button_state(lml_folder, clean_button)
    update_restore_button_state(lml_folder, restore_button)
    
    backup_label = ctk.CTkLabel(settings_container_frame, text="Allows you to play RDO safely.\nMods are stored in 'Red Dead Redemption 2\\RDMT'.\nRun as Administrator or Take Ownership of your game folder if you have issues.", justify="left", text_color="grey", font=("Segoe UI", 16, "bold"))
    backup_label.grid(row=6, columnspan=2, column=0, sticky="nw", padx=10)
    
    endorse_button = ctk.CTkButton(settings_container_frame, text="Endorse", command=lambda: endorse_mod(api_key, endorse_button, endorse_label), fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 16, "bold"))
    endorse_label = ctk.CTkLabel(settings_container_frame, text="Please consider endorsing! :)", justify="left", text_color="grey", font=("Segoe UI", 16, "bold"))
    if api_key:
        endorse_button.grid(row=7, column=0, sticky="n", pady=(50, 10))
        endorse_label.grid(row=8, columnspan=2, column=0, sticky="nw", padx=10)
        check_endorsement(api_key, endorse_button, endorse_label)
            
    credit_label = ctk.CTkLabel(settings_container_frame, text="generatedmax - Nexus Mods", justify="left", text_color="grey", font=("Segoe UI", 16, "bold")).grid(row=9, columnspan=2, column=0, sticky="sw", padx=10, pady=10)
    
    show_frame(home_frame, home_button)
    
    if api_key:
        start_pipe_listener("rdmt_download", handle_nxm_link, api_key)
        print("Application is now running and listening for NXM links.")

    main_window.update_idletasks()
    
    screen_width = main_window.winfo_screenwidth()
    screen_height = main_window.winfo_screenheight()
    initial_width = min(1400, int(screen_width * 0.9))
    initial_height = min(800, int(screen_height * 0.9))

    x = max(0, (screen_width - initial_width) // 2)
    y = max(0, (screen_height - initial_height) // 2)

    main_window.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
    main_window.wm_minsize(1200, 700)
    main_window.resizable(True, True)

    main_window.deiconify()
    main_window.protocol("WM_DELETE_WINDOW", app.quit)

def main():
    app = ctk.CTk()
    
    app.withdraw()
    
    app.title("Red Dead Modding Tool")
    
    icon_path = os.path.join(image_path, "rdmt.ico")
    app.iconbitmap(icon_path)

    splash_root = show_splash()
    
    cleanup_installer_files()

    def after_splash():
        global config

        try:
            if splash_root:
                splash_root.destroy()

            migrate_old_config()
            config = load_config()
            saved_path = config["path"]
            theme = config["theme"]

            ctk.set_appearance_mode(theme)

            if saved_path and os.path.isdir(saved_path) and os.access(saved_path, os.R_OK):
                check_conflicts(app, saved_path)
            else:
                raise ValueError("Invalid or inaccessible LML folder path in configuration.")
        except Exception as e:
            print(f"Error during initialization: {e}")

            save_config()

            ctk.CTkLabel(app, text="Enter RDR2 Folder Path:", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, padx=10, pady=10, sticky="e")
            lml_path = search_lml_folder()
            entry = ctk.CTkEntry(app, width=400, font=("Segoe UI", 16))
            entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

            browse_button = ctk.CTkButton(app, text="Browse", command=lambda: browse_folder(entry), fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 16, "bold"))
            browse_button.grid(row=0, column=2, padx=10, pady=10, sticky="w")

            check_button = ctk.CTkButton(app, text="Continue", command=lambda: check_and_save_path(app, entry), fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 16, "bold"))
            check_button.grid(row=1, column=0, columnspan=3, pady=20)

            if lml_path:
                entry.insert(0, lml_path)

            app.update_idletasks()

            screen_width = app.winfo_screenwidth()
            screen_height = app.winfo_screenheight()
            initial_width = min(800, int(screen_width * 0.9))
            initial_height = min(120, int(screen_height * 0.9))

            x = max(0, (screen_width - initial_width) // 2)
            y = max(0, (screen_height - initial_height) // 2)

            app.geometry(f"{initial_width}x{initial_height}+{x}+{y}")
            app.wm_minsize(initial_width, initial_height)
            app.resizable(True, True)

            app.deiconify()

    splash_root.after(1500, after_splash)

    app.withdraw()
    app.mainloop()

if __name__ == "__main__":
    main()
