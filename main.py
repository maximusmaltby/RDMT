# main.py — Application entry point

import os
import sys
import time
import subprocess

import customtkinter as ctk

from constants import image_path, VERSION
from config import load_config, save_config, migrate_old_config, load_safe_mods
from utils import load_image, browse_folder, search_lml_folder
from mod_manager import get_mods_and_files, find_conflicts
from nexus_api import cleanup_installer_files
from CTkMessagebox import CTkMessagebox


def show_splash():
    """Display a splash screen with a progress bar."""
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


def check_conflicts(app, entry_or_path, config):
    """Load mods, detect conflicts, and launch the main window."""
    from ui_main import display_main_window

    selected_folder = entry_or_path.get() if hasattr(entry_or_path, "get") else entry_or_path
    lml_folder = os.path.join(selected_folder, "lml") if os.path.basename(selected_folder).lower() == "red dead redemption 2" else selected_folder
    if not os.path.isdir(lml_folder) or not os.access(lml_folder, os.R_OK):
        CTkMessagebox(title="Error", message="Invalid or inaccessible folder path. Please select a valid LML folder.", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")
        return

    file_map = get_mods_and_files(lml_folder)
    safe_mods = load_safe_mods()
    conflicts = find_conflicts(file_map, safe_mods)
    mods = [mod for mod in os.listdir(lml_folder) if os.path.isdir(os.path.join(lml_folder, mod))]

    display_main_window(app, mods, conflicts, lml_folder, config)
    app.withdraw()


def check_and_save_path(app, entry, config):
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
            config = load_config()
            check_conflicts(app, lml_folder, config)
        except Exception as e:
            print(f"Error loading mod data: {e}")
            CTkMessagebox(title="Error", message=f"Failed to load mod data from the selected folder:\n{e}\n\nPlease ensure LML is installed correctly.", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")
    else:
        CTkMessagebox(title="Error", message="Invalid or inaccessible folder path. Please select a valid RDR2 folder.", button_color="#b22222", button_hover_color="#8b0000", fade_in_duration=0.05, icon="cancel")


def main():
    app = ctk.CTk()
    app.withdraw()
    app.title("Red Dead Modding Tool")

    icon_path = os.path.join(image_path, "rdmt.ico")
    app.iconbitmap(icon_path)

    splash_root = show_splash()
    cleanup_installer_files()

    def after_splash():
        try:
            if splash_root:
                splash_root.destroy()

            migrate_old_config()
            config = load_config()
            saved_path = config["path"]
            theme = config["theme"]

            ctk.set_appearance_mode(theme)

            if saved_path and os.path.isdir(saved_path) and os.access(saved_path, os.R_OK):
                check_conflicts(app, saved_path, config)
            else:
                raise ValueError("Invalid or inaccessible LML folder path in configuration.")
        except Exception as e:
            print(f"Error during initialization: {e}")

            save_config()
            config = load_config()

            ctk.CTkLabel(app, text="Enter RDR2 Folder Path:", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, padx=10, pady=10, sticky="e")
            lml_path = search_lml_folder()
            entry = ctk.CTkEntry(app, width=400, font=("Segoe UI", 16))
            entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

            browse_button = ctk.CTkButton(app, text="Browse", command=lambda: browse_folder(entry), fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 16, "bold"))
            browse_button.grid(row=0, column=2, padx=10, pady=10, sticky="w")

            check_button = ctk.CTkButton(app, text="Continue", command=lambda: check_and_save_path(app, entry, config), fg_color="#b22222", hover_color="#8b0000", font=("Segoe UI", 16, "bold"))
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
