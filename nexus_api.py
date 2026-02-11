# nexus_api.py — Nexus Mods API interactions

import os
import re
import sys
import uuid
import json
import shutil
import zipfile
import requests
import patoolib
import threading
import subprocess
import webbrowser

import customtkinter as ctk

from tkinter import filedialog
from websocket import WebSocketApp
from CTkListbox import *
from CTkMessagebox import CTkMessagebox
from datetime import datetime, timedelta, timezone

from constants import image_path, base_path, APPLICATION_SLUG, APPDATA_FOLDER
from config import load_config, save_config, load_cache, save_cache
from utils import encrypt_text, null_button


# --- API Validation ---

def validate_api_key(api_key):
    """Validate the provided Nexus Mods API key."""
    validation_url = "https://api.nexusmods.com/v1/users/validate.json"
    headers = {'accept': 'application/json', 'apikey': api_key}
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
    headers = {'accept': 'application/json', 'apikey': api_key}
    try:
        response = requests.get(validation_url, headers=headers, timeout=10)
        response.raise_for_status()
        user_data = response.json()
        return user_data.get("is_premium", False)
    except requests.RequestException as req_err:
        print(f"Error validating premium status: {req_err}")
        return False


# --- SSO ---

def sso_retrieve_api_key():
    """Retrieve the API key using Nexus Mods SSO with threading to prevent UI freezing."""
    sso_url = "wss://sso.nexusmods.com"
    unique_id = str(uuid.uuid4())
    connection_token = None
    socket_open = threading.Event()

    def on_message(ws, message):
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
        print("WebSocket Error:", error)

    def on_close(ws, close_status_code, close_msg):
        print("WebSocket Closed:", close_status_code, close_msg)

    def on_open(ws):
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
        ws_app.run_forever()

    threading.Thread(target=websocket_thread, daemon=True).start()
    socket_open.wait()

    sso_auth_url = f"https://www.nexusmods.com/sso?id={unique_id}&application={APPLICATION_SLUG}"
    print("Opening browser for user authorization:", sso_auth_url)
    webbrowser.open(sso_auth_url)


# --- Restart Helpers ---

def restart_for_api(api_key):
    """Restart the program with the updated API key after validating it."""
    keys_directory = os.path.join(APPDATA_FOLDER, "keys")
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


def restart_for_lml(lml_path_entry):
    """Restart the program."""
    save_config(path=lml_path_entry.get().strip())
    python_executable = sys.executable
    script_path = sys.argv[0]
    subprocess.Popen([python_executable, script_path])
    sys.exit()


# --- Endorsement ---

def endorse_mod(api_key, endorse_button, endorse_label):
    """Endorse a specific mod on Nexus Mods for Red Dead Redemption 2."""
    try:
        game_domain_name = "reddeadredemption2"
        mod_id = 5180

        endorse_url = f"https://api.nexusmods.com/v1/games/{game_domain_name}/mods/{mod_id}/endorse.json"
        headers = {'accept': 'application/json', 'apikey': api_key}

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
            headers = {'accept': 'application/json', 'apikey': api_key}

            response = requests.get(endorsements_url, headers=headers, timeout=10)
            response.raise_for_status()
            endorsements = response.json()

            target_domain = "reddeadredemption2"
            target_mod_id = 5180

            for endorsement in endorsements:
                if (endorsement.get("domain_name") == target_domain and
                        endorsement.get("mod_id") == target_mod_id and
                        endorsement.get("status") == "Endorsed"):
                    endorse_button.configure(text="Endorsed!", fg_color="#8b0000", command=null_button, cursor="arrow")
                    endorse_label.configure(text="Thank you for endorsing! :)")

            return
        except requests.RequestException as req_err:
            print(f"Error checking endorsements: {req_err}")
        except ValueError as val_err:
            print(f"Unexpected response format: {val_err}")

    threading.Thread(target=threaded_check, daemon=True).start()


# --- Update Checking ---

def check_for_update(version_label, main_window, config):
    """Check for updates, and if available, present options to download Installer or Portable."""
    from constants import VERSION
    try:
        response = requests.get("https://pastebin.com/raw/gGXu4uA8", timeout=5)
        response.raise_for_status()
        remote_version = response.text.strip()

        if remote_version != VERSION:
            version_label.configure(text=f"Update {remote_version} Available!", text_color="#f88379")

            api_key = config.get("api_key", "")
            if not api_key:
                return

            premium_user = validate_premium_status(api_key)
            if not premium_user:
                return

            game_domain_name = "reddeadredemption2"
            mod_id = 5180
            files_url = f"https://api.nexusmods.com/v1/games/{game_domain_name}/mods/{mod_id}/files.json"
            headers = {'accept': 'application/json', 'apikey': api_key}

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


def update_dialog(main_window):
    """Ask the user to select between Installer or Portable download."""
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


def download_installer(download_url):
    """Download the Installer ZIP file, extract it, and run the installer with /silent command."""
    try:
        lml_folder = os.path.join(APPDATA_FOLDER, 'temp')
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
    """Download the Portable ZIP file and allow the user to save it via a file dialog."""
    try:
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
    """Check for the presence of installer.zip and the installer folder in AppData and delete them if they exist."""
    try:
        zip_file_path = os.path.join(APPDATA_FOLDER, "installer.zip")
        extract_path = os.path.join(APPDATA_FOLDER, "installer")

        if os.path.exists(zip_file_path):
            os.remove(zip_file_path)
            print(f"Deleted: {zip_file_path}")
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
            print(f"Deleted folder: {extract_path}")
    except Exception as e:
        print(f"Error during cleanup: {e}")


# --- Mod Browsing/Downloading ---

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
    """Check for conflicts between a Nexus mod and installed mods."""
    from mod_manager import get_mods_and_files

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

                icon_path_local = os.path.join(image_path, "rdmt.ico")
                conflict_window.after(201, lambda: conflict_window.iconbitmap(icon_path_local))

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

    icon_path_local = os.path.join(image_path, "rdmt.ico")
    progress_dialog.after(201, lambda: progress_dialog.iconbitmap(icon_path_local))

    progress_bar = ctk.CTkProgressBar(progress_dialog, width=300, progress_color="#b22222")
    progress_bar.pack(pady=20, padx=20)
    progress_bar.set(0)
    progress_bar.start()

    threading.Thread(target=detect_conflicts, daemon=True).start()


def download_mod(selected_item, api_key, category=None, mod_id=None, file_id=None, install=False):
    """Download a mod, either selected from a list or specified by mod_id and file_id, and optionally install it."""
    stop_thread = threading.Event()

    def download_install():
        progress_dialog = None
        try:
            nonlocal mod_id, file_id

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

                    icon_path_local = os.path.join(image_path, "rdmt.ico")
                    file_choice_dialog.after(201, lambda: file_choice_dialog.iconbitmap(icon_path_local))

                    result = {"choice": None}

                    def on_file_select(sel_item):
                        try:
                            for fid, file_data in file_options.items():
                                if sel_item == f"{file_data['name']} (v{file_data['version']})":
                                    nonlocal selected_file_id, selected_file_name
                                    selected_file_id = fid
                                    selected_file_name = file_data["file_name"]
                                    break
                            result["choice"] = "selected"
                            file_choice_dialog.after(100, file_choice_dialog.destroy)
                        except Exception as e:
                            print(f"Error in selection callback: {e}")

                    def on_close_dialog():
                        result["choice"] = "cancel"
                        file_choice_dialog.destroy()

                    file_choice_dialog.protocol("WM_DELETE_WINDOW", on_close_dialog)

                    file_listbox = CTkListbox(
                        file_choice_dialog,
                        command=on_file_select,
                        height=400, width=300,
                        highlight_color="#8b0000",
                        hover_color="#b22222"
                    )

                    for fid, file_data in file_options.items():
                        file_listbox.insert(ctk.END, f"{file_data['name']} (v{file_data['version']})")

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
                save_path = os.path.join(APPDATA_FOLDER, "temp", f"{mod_id}_{file_id}{file_extension}")
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

            config = load_config()
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

            for root, dirs, files_list in os.walk(extract_path):
                if any(f.lower().endswith(".asi") for f in files_list):
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

                if "install.xml" in files_list:
                    install_xml_found = True

            if install_xml_found and not has_asi and not has_lml_folder:
                folder_to_copy = None
                for root, dirs, files_list in os.walk(extract_path):
                    if "install.xml" in files_list:
                        folder_to_copy = root
                        break

                if folder_to_copy:
                    dest_path = os.path.join(install_directory, os.path.basename(folder_to_copy))
                    shutil.copytree(folder_to_copy, dest_path, dirs_exist_ok=True)
                    print(f"Copied folder {folder_to_copy} to {dest_path}")
                    mod_installed = True

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


# --- Progress Dialogs ---

def refresh_download_progress_dialog(stop_thread):
    def on_close():
        stop_thread.set()
        progress_dialog.destroy()

    progress_dialog = ctk.CTkToplevel()
    progress_dialog.title("Downloading mod...")
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

    icon_path_local = os.path.join(image_path, "rdmt.ico")
    progress_dialog.after(201, lambda: progress_dialog.iconbitmap(icon_path_local))

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
    progress_dialog.title("Building mod cache...")
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

    icon_path_local = os.path.join(image_path, "rdmt.ico")
    progress_dialog.after(201, lambda: progress_dialog.iconbitmap(icon_path_local))

    progress_bar = ctk.CTkProgressBar(progress_dialog, width=300, progress_color="#b22222")
    progress_bar.pack(pady=20, padx=20)
    progress_bar.set(0)
    progress_bar.start()
    return progress_dialog


# --- Nexus List Refresh Functions ---

def populate_listbox(listbox, items):
    """Helper function to populate the listbox with items."""
    listbox.pack_forget()
    listbox.delete(0, ctk.END)
    for item in items:
        listbox.insert(ctk.END, item)
    listbox.pack(fill="both", expand=True)


def refresh_tracked(tracked_listbox, tracked_description, api_key, show_frame, nexus_frame, nexus_button):
    stop_thread = threading.Event()

    def fetch_tracked_mods():
        tracked_url = "https://api.nexusmods.com/v1/user/tracked_mods.json"
        headers = {'accept': 'application/json', 'apikey': api_key}

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
                        stored_mod_details[str(mod_id)] = mod_response.json()
                    except requests.RequestException as mod_err:
                        print(f"Error fetching details for mod ID {mod_id}: {mod_err}")

            cache["tracked_mods"] = current_tracked
            cache["mod_details"] = stored_mod_details
            save_cache(cache, 'tracked')

            items = [
                f"{md.get('name', 'Unknown Mod')} (v{md.get('version', 'Unknown Version')})"
                for mid, md in stored_mod_details.items()
                if md.get("domain_name") == domain_name and md.get('name', 'Unknown Mod') != 'Unknown Mod' and md.get('version', 'Unknown Version') != 'Unknown Version'
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
        updated_url = "https://api.nexusmods.com/v1/games/reddeadredemption2/mods/updated.json?period=1w"
        headers = {'accept': 'application/json', 'apikey': api_key}

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

                if mod_id not in stored_mod_details or latest_file_update > stored_mod_details[mod_id].get("updated_timestamp", 0):
                    mod_details_url = f"https://api.nexusmods.com/v1/games/reddeadredemption2/mods/{mod_id}.json"
                    try:
                        mod_response = requests.get(mod_details_url, headers=headers, timeout=10)
                        mod_response.raise_for_status()
                        mod_details = mod_response.json()
                        mod_details["updated_timestamp"] = latest_file_update
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

                if mod_updated_time >= seven_days_ago and mod_name != "Unknown Mod" and mod_version != "Unknown Version":
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
        updated_url = "https://api.nexusmods.com/v1/games/reddeadredemption2/mods/trending.json"
        headers = {'accept': 'application/json', 'apikey': api_key}

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
                        stored_mod_details[str(mod_id)] = mod_response.json()
                    except requests.RequestException as mod_err:
                        print(f"Error fetching details for mod ID {mod_id}: {mod_err}")

            cache["mod_details"] = stored_mod_details
            save_cache(cache, 'trending')

            items = [
                f"{md.get('name', 'Unknown Mod')} (v{md.get('version', 'Unknown Version')})"
                for mid, md in stored_mod_details.items()
                if md.get('name', 'Unknown Mod') != 'Unknown Mod' and md.get('version', 'Unknown Version') != 'Unknown Version'
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
        updated_url = "https://api.nexusmods.com/v1/games/reddeadredemption2/mods/latest_added.json"
        headers = {'accept': 'application/json', 'apikey': api_key}

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
                        stored_mod_details[str(mod_id)] = mod_response.json()
                    except requests.RequestException as mod_err:
                        print(f"Error fetching details for mod ID {mod_id}: {mod_err}")

            cache["mod_details"] = stored_mod_details
            save_cache(cache, 'added')

            items = [
                f"{md.get('name', 'Unknown Mod')} (v{md.get('version', 'Unknown Version')})"
                for mid, md in stored_mod_details.items()
                if md.get('name', 'Unknown Mod') != 'Unknown Mod' and md.get('version', 'Unknown Version') != 'Unknown Version'
            ]

            added_listbox.after(0, lambda: populate_listbox(added_listbox, items))
        except requests.RequestException as req_err:
            print(f"Error fetching updated mods: {req_err}")
        finally:
            progress_dialog.destroy()

    progress_dialog = refresh_nexus_progress_dialog(show_frame, nexus_frame, nexus_button, stop_thread)
    threading.Thread(target=fetch_added_mods, daemon=True).start()
