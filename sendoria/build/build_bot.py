#!/usr/bin/env python3
"""
Build script for Sendoria Discord Bot
Compiles discord_bot.py into SendoriaBot.exe
"""

import subprocess
import sys
import os
import shutil

def check_pyinstaller():
    """Check if PyInstaller is installed, install if needed"""
    try:
        import PyInstaller
        print("✅ PyInstaller found")
        return True
    except ImportError:
        print("⚠️  PyInstaller not found. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("✅ PyInstaller installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install PyInstaller")
            print("Please install manually: pip install pyinstaller")
            return False

def build_executable():
    """Build the Discord bot executable"""
    print("\n🔨 Building SendoriaBot.exe...")
    
    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",           # Single executable
        "--console",           # Keep console window
        "--name", "SendoriaBot",  # Output name
        "discord_bot.py"       # Source file
    ]
    
    try:
        # Run PyInstaller
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Build successful!")
            
            # Check if exe was created
            exe_path = os.path.join("dist", "SendoriaBot.exe")
            if os.path.exists(exe_path):
                print(f"✅ Executable created: {exe_path}")
                
                # Optional: Copy to current directory
                current_exe = "SendoriaBot.exe"
                if os.path.exists(current_exe):
                    backup = "SendoriaBot_old.exe"
                    print(f"📁 Backing up old executable to {backup}")
                    shutil.copy2(current_exe, backup)
                
                print(f"📁 Copying new executable to current directory")
                shutil.copy2(exe_path, current_exe)
                print("✅ Build complete! You can now run the updated bot.")
                
            else:
                print("❌ Executable not found after build")
                return False
                
        else:
            print("❌ Build failed!")
            print("Error output:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Build error: {e}")
        return False
    
    return True

def cleanup():
    """Clean up build artifacts"""
    print("\n🧹 Cleaning up build files...")
    
    dirs_to_remove = ["build", "__pycache__"]
    files_to_remove = ["SendoriaBot.spec"]
    
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"🗑️  Removed {dir_name}/")
    
    for file_name in files_to_remove:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"🗑️  Removed {file_name}")

def main():
    print("🚀 Sendoria Discord Bot Builder")
    print("=" * 40)
    
    # Check if source file exists
    if not os.path.exists("discord_bot.py"):
        print("❌ discord_bot.py not found in current directory")
        return False
    
    # Install PyInstaller if needed
    if not check_pyinstaller():
        return False
    
    # Build executable
    if not build_executable():
        return False
    
    # Clean up
    cleanup()
    
    print("\n🎉 Build process complete!")
    print("You can now run SendoriaBot.exe with your updated changes.")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
