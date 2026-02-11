# nxmproxy.py — NXMProxy setup, pipe listener, and NXM link handling

import os
import re
import toml
import shutil
import winreg
import threading
import subprocess
import win32pipe
import win32file

from constants import base_path


# --- NXMProxy ---

def is_nxmproxy_setup():
    """Check if NXMProxy is set up correctly for RDMT and Red Dead Redemption 2."""
    try:
        appdata_nxmproxy_dir = os.path.join(os.getenv("APPDATA"), "nxmproxy")
        nxmproxy_path = os.path.join(appdata_nxmproxy_dir, "nxmproxy.exe")

        os.makedirs(appdata_nxmproxy_dir, exist_ok=True)

        result = subprocess.run(
            [nxmproxy_path, "test"],
            capture_output=True, text=True, check=True
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


# --- NXM Link Handling ---

def handle_nxm_link(link, api_key):
    """Handle an NXM link by parsing it and downloading the associated mod."""
    from nexus_api import download_mod

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
