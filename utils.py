# utils.py — Encryption, file I/O, image loading, and merge utilities

import os
import base64

from PIL import Image
from tkinter import filedialog
from difflib import SequenceMatcher
from cryptography.fernet import Fernet
from customtkinter import CTkImage

import customtkinter as ctk

from constants import image_path, APPDATA_FOLDER


# --- Encryption ---

def generate_key():
    """Generate a key for encrypting the API key."""
    return base64.urlsafe_b64encode(os.urandom(32))


def get_encryption_key():
    """Retrieve or generate the encryption key."""
    key_path = os.path.join(APPDATA_FOLDER, 'keys', 'encryption.key')
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


# --- File I/O ---

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


# --- Image Helpers ---

def load_image(filename, width, height):
    """Load an image from the image directory and return a CTkImage."""
    try:
        img_path = os.path.join(image_path, filename)
        pil_image = Image.open(img_path).resize((width, height), Image.LANCZOS)
        return CTkImage(pil_image, size=(width, height))
    except FileNotFoundError:
        print(f"Error: Image file {filename} not found in {image_path}.")
        return None


# --- Browse Helpers ---

def browse_folder(entry):
    """Open a folder browser dialog and insert the path into the entry widget."""
    folder_path = filedialog.askdirectory(title="Select your RDR2 folder")
    if folder_path:
        entry.delete(0, ctk.END)
        entry.insert(0, folder_path)


def search_lml_folder():
    """Search common install paths for the RDR2 folder."""
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


# --- Misc ---

def null_button():
    """No-op callback for disabled buttons."""
    return


# --- Three-Way Merge ---

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

    # Handle trailing content
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
