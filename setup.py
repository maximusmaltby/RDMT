import os
import sys
import shutil
from cx_Freeze import setup, Executable
# FIX 1: Import the lowercase 'build_exe' command class
from cx_Freeze.command.build_exe import build_exe

# FIX 2: "Win32GUI" is deprecated in cx_Freeze 7+. Use "gui" instead.
base = "gui"

project_dir = os.path.abspath(os.path.dirname(__file__))
lib_dir = os.path.join(project_dir, "lib")

executables = [
    Executable(
        script="RDMT.py",
        base=base,
        icon=os.path.join(lib_dir, "img", "rdmt.ico"),
        target_name="Red Dead Modding Tool.exe",
        manifest="app.manifest",
    )
]

build_options = {
    "packages": [
        "os", "re", "sys", "uuid", "json", "time", "toml", "base64",
        "string", "shutil", "winreg", "zipfile", "difflib", "requests",
        "patoolib", "threading", "win32pipe", "win32file", "subprocess",
        "webbrowser", "customtkinter", "PIL", "xml.etree.ElementTree",
        "pathlib", "xml.dom.minidom", "tkinter", "collections",
        "websocket", "cryptography", "CTkListbox", "CTkToolTip",
        "CTkMessagebox", "tklinenums", "datetime",
    ],
    "excludes": [
        "tkinter.test", 
        "unittest", 
        "websocket.policyserver", 
        "websocket.server"
    ],
    "include_files": [
        (lib_dir, "lib"),
    ],
    "build_exe": os.path.join(project_dir, "build"),
}

# FIX 3: Subclass the lowercase 'build_exe' class
class CustomBuild(build_exe):
    def run(self):
        # Run the standard build process first
        super().run()
        # Then run our custom cleanup
        self.run_cleanup()

    def run_cleanup(self):
        print("Running post-build clean-up...")
        # In the new class, the build directory is stored in self.build_exe
        build_dir = self.build_exe
        
        lib_target_dir = os.path.join(build_dir, "lib", "msvcr")
        os.makedirs(lib_target_dir, exist_ok=True)
        
        if os.path.exists(build_dir):
            # Find DLLs to move
            msvcr_files = [
                f for f in os.listdir(build_dir) 
                if f.startswith("api-ms-win") or f.startswith("vcruntime")
            ]
            
            for dll in msvcr_files:
                dll_path = os.path.join(build_dir, dll)
                try:
                    shutil.move(dll_path, os.path.join(lib_target_dir, dll))
                except Exception as e:
                    print(f"Warning: Could not move {dll}: {e}")
            
            # Remove license file
            license_file = os.path.join(build_dir, "frozen_application_license.txt")
            if os.path.exists(license_file):
                try:
                    os.remove(license_file)
                except OSError:
                    pass

setup(
    name="Red Dead Modding Tool",
    version="2.0.4",
    description="Red Dead Modding Tool",
    author="generatedmax - Nexus Mods",
    options={"build_exe": build_options},
    executables=executables,
    # Register the custom command
    cmdclass={"build_exe": CustomBuild}
)