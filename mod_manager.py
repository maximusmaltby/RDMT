# mod_manager.py — Mod scanning, conflict detection, load order, ASI management, and mod enable/disable

import os
import re
import shutil
import webbrowser

import customtkinter as ctk
import xml.etree.ElementTree as ET

from collections import defaultdict
from datetime import datetime
from tkinter import filedialog
from CTkMessagebox import CTkMessagebox

from constants import image_path, GAME_FILES
from config import load_safe_mods, save_safe_mods


# --- Mod Scanning ---

def get_mods_and_files(lml_folder):
    """
    Traverse the LML folder to identify mods and their associated files.
    A mod is identified if any folder contains an install.xml file.
    """
    file_map = defaultdict(list)
    ignored_files = {"install.xml", "strings.gxt2", "__folder_managed_by_vortex"}

    def find_mod_folders(folder_path):
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


# --- Conflict Detection ---

def find_conflicts(file_map, safe_mods=None):
    """Find conflicting files between mods, optionally excluding mods marked as safe."""
    if safe_mods is None:
        safe_mods = set()

    def get_root_folder(mod_path):
        return mod_path.split("/", 1)[0] if "/" in mod_path else mod_path

    conflicts = {}
    for file, mods in file_map.items():
        if file.lower() == "content.xml":
            continue

        filtered_mods = [(mod, pri) for mod, pri in mods if get_root_folder(mod) not in safe_mods]
        root_folders = {get_root_folder(mod) for mod, _ in filtered_mods}

        if len(root_folders) > 1:
            conflicts[file] = filtered_mods
    return conflicts


# --- Load Order ---

def get_load_order(mods_xml_path):
    """Get the load order from mods.xml."""
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


# --- Listbox Helpers ---

def populate_listbox(listbox, items):
    """Helper function to populate the listbox with items."""
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


# --- Mod Folder Operations ---

def open_nexus_link():
    webbrowser.open("https://www.nexusmods.com/reddeadredemption2/mods/5180")


def open_mod_folder(selected_mod, lml_folder):
    selected_mod = selected_mod.replace(" (Lowest Priority)", "").replace(" (Highest Priority)", "")
    mod_folder_path = os.path.join(lml_folder, selected_mod)
    if os.path.isdir(mod_folder_path):
        os.startfile(mod_folder_path)
    else:
        print(f"Error: Folder '{mod_folder_path}' does not exist.")


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


# --- Refresh Functions ---

def refresh_modlist(mod_listbox, lml_folder, mods_xml_path, browse_button):
    """Refresh the mod list by reloading mods from the LML folder."""
    try:
        file_map = get_mods_and_files(lml_folder)
        mods = {mod.replace("\\", "/") for _, mod_list in file_map.items() for mod, _ in mod_list}
        load_order = get_load_order(mods_xml_path)
        sorted_mods = [mod for mod in load_order if mod in mods] + [mod for mod in mods if mod not in load_order]
        populate_listbox(mod_listbox, sorted_mods)
        browse_button.configure(state="disabled")
    except Exception as e:
        CTkMessagebox(title="Error", message=f"Error refreshing mod list: {str(e)}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")


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
        CTkMessagebox(title="Error", message=f"Failed to refresh ASI mods: {e}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")


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


# --- Conflict Display ---

def refresh_conflicts(conflict_text, conflicts, lml_folder):
    """Refresh the conflicts display, sorting mods by load order priority and filtering safe mods."""
    try:
        conflict_text.configure(state="normal")
        file_map = get_mods_and_files(lml_folder)
        safe_mods = load_safe_mods()
        conflicts = find_conflicts(file_map, safe_mods)

        mods_xml_path = os.path.join(lml_folder, "mods.xml")
        load_order = get_load_order(mods_xml_path)
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
                idx = load_order_index.get(mod, load_order_index.get(root, 999999))
                return idx

            sorted_mods = sorted(mods, key=sort_key)

            for i, (mod, priority) in enumerate(sorted_mods):
                label = f"{mod} (stream)" if priority == 2 else (f"{mod} (replace)" if priority == 1 else mod)

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
        CTkMessagebox(title="Error", message=f"Error refreshing conflicts: {str(e)}", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")


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
            f.write("Red Dead Modding Tool - Conflicts Report\n")
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

    icon_path_local = os.path.join(image_path, "rdmt.ico")
    dialog.after(201, lambda: dialog.iconbitmap(icon_path_local))

    safe_mods = load_safe_mods()

    header_frame = ctk.CTkFrame(dialog)
    header_frame.pack(fill="x", padx=10, pady=(10, 5))
    ctk.CTkLabel(header_frame, text="Check mods to exclude from conflict detection:", font=("Segoe UI", 14, "bold")).pack(side="left", padx=5)

    scroll_frame = ctk.CTkScrollableFrame(dialog, width=550, height=350)
    scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

    all_mods = sorted([
        mod for mod in os.listdir(lml_folder)
        if os.path.isdir(os.path.join(lml_folder, mod))
    ], key=str.lower)

    checkbox_vars = {}
    for mod_name in all_mods:
        var = ctk.BooleanVar(value=(mod_name in safe_mods))
        checkbox_vars[mod_name] = var
        cb = ctk.CTkCheckBox(scroll_frame, text=mod_name, variable=var, font=("Segoe UI", 14), fg_color="#b22222", hover_color="#8b0000")
        cb.pack(anchor="w", padx=10, pady=2)

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


# --- Clean / Restore Mods ---

def clean_mods(lml_folder):
    """Move non-game files from the game root to the RDMT backup folder."""
    root_dir = os.path.dirname(lml_folder)
    backup_dir = os.path.join(root_dir, "RDMT")

    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    for filename in os.listdir(root_dir):
        file_path = os.path.join(root_dir, filename)
        if os.path.isfile(file_path) and filename not in GAME_FILES:
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
    """Enable or disable the clean button based on the presence of non-game files."""
    root_dir = os.path.dirname(lml_folder)
    non_game_files_exist = any(
        os.path.isfile(os.path.join(root_dir, filename)) and filename not in GAME_FILES
        for filename in os.listdir(root_dir)
    )
    clean_button.configure(state="normal" if non_game_files_exist else "disabled")


def update_restore_button_state(lml_folder, restore_button):
    """Enable or disable the restore button based on the presence of the RDMT folder."""
    root_dir = os.path.dirname(lml_folder)
    rdmt_dir = os.path.join(root_dir, "RDMT")
    if os.path.exists(rdmt_dir) and os.path.isdir(rdmt_dir):
        restore_button.configure(state="normal")
    else:
        restore_button.configure(state="disabled")
