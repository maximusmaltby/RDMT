# ui_main.py — Main application window and all GUI layout

import os
import re
import time
import threading

import customtkinter as ctk

from PIL import Image
from tkinter import filedialog
from difflib import SequenceMatcher
from CTkListbox import *
from CTkToolTip import *
from CTkMessagebox import CTkMessagebox
from tklinenums import TkLineNumbers

from constants import image_path, VERSION
from config import (
    load_config, save_config, load_safe_mods,
    clean_cache, update_clean_cache_button_state, load_cache
)
from utils import load_image, safe_read_file, three_way_merge
from mod_manager import (
    get_mods_and_files, find_conflicts, get_load_order, update_load_order,
    populate_listbox, get_listbox_items, move_up, move_down,
    open_nexus_link, open_mod_folder, open_lml_folder, open_game_folder,
    refresh_modlist, refresh_asi, toggle_asi_mod,
    refresh_conflicts, export_conflicts, manage_safe_mods_dialog,
    clean_mods, restore_mods,
    update_clean_button_state, update_restore_button_state
)
from nexus_api import (
    validate_premium_status, check_for_update, sso_retrieve_api_key,
    restart_for_api, restart_for_lml,
    endorse_mod, check_endorsement,
    open_mod_page, check_nexus_conflicts, download_mod,
    refresh_tracked, refresh_updated, refresh_trending, refresh_added
)
from nxmproxy import is_nxmproxy_setup, setup_nxmproxy, handle_nxm_link, start_pipe_listener


def display_main_window(app, mods, conflicts, lml_folder, config):
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
    
    check_for_update(version_label, main_window, config)
    
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

