import os
import subprocess
import sys
import site
import shutil
from pathlib import Path
import pathspec

def get_site_packages_path():
    """Get the path to the site-packages directory of the current environment."""
    if hasattr(site, 'getsitepackages'):
        paths = site.getsitepackages()
    else:
        paths = [site.getusersitepackages()]

    if paths:
        return paths[0]
    else:
        raise RuntimeError("Couldn't determine the site-packages path.")

def parse_gitignore(gitignore_path):
    """Parse .gitignore file and return a PathSpec object."""
    if not os.path.exists(gitignore_path):
        return pathspec.PathSpec.from_lines('gitwildmatch', [])
    
    with open(gitignore_path, 'r') as f:
        return pathspec.PathSpec.from_lines('gitwildmatch', f)

def copy_project_files(src_dir, dst_dir, spec):
    """Copy project files respecting .gitignore rules using pathspec."""
    src_path = Path(src_dir)

    # Walk through all the directories and files in the source directory
    for root, dirs, files in os.walk(src_dir):
        rel_root = Path(root).relative_to(src_path)

        # Filter out directories and files based on the .gitignore rules
        for file in files:
            rel_path = rel_root / file
            if not spec.match_file(str(rel_path)):
                src_file = src_path / rel_path
                dst_file = Path(dst_dir) / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)


def cleanup_directories(bundle_name, keep_dist=False):
    """Remove build directory and .spec file. Optionally keep dist."""
    if not keep_dist and os.path.exists('dist'):
        shutil.rmtree('dist')
    
    if os.path.exists('build'):
        shutil.rmtree('build')
    
    spec_file = f"{bundle_name}.spec"
    if os.path.exists(spec_file):
        os.remove(spec_file)

def build_executable(script_name, exe_name=None):
    """Run PyInstaller with the correct site-packages path, clean, and additional data."""
    try:
        # Initial cleanup
        cleanup_directories(exe_name, keep_dist=False)

        site_packages_path = get_site_packages_path()
        print(f"Using site-packages path: {site_packages_path}")

        # Parse .gitignore
        gitignore_path = os.path.join(os.getcwd(), '.gitignore')
        spec = parse_gitignore(gitignore_path)

        # Create a temporary directory for project files
        temp_project_dir = os.path.join('build', 'temp_project')
        os.makedirs(temp_project_dir, exist_ok=True)

        # Copy project files respecting .gitignore
        copy_project_files(os.getcwd(), temp_project_dir, spec)

        # Construct the PyInstaller command
        pyinstaller_command = [
            "pyinstaller",
            "--clean",
            "--noconfirm",
            "--onedir",
            f"--paths={site_packages_path}",
            "--workpath=build",  # Specify the build directory
        ]

        # Add custom name if provided
        if exe_name:
            pyinstaller_command.append(f"--name={exe_name}")
        else:
            exe_name = os.path.splitext(script_name)[0]

        # Add the script path
        pyinstaller_command.append(os.path.join(temp_project_dir, script_name))

        # Run the PyInstaller command
        print("Running PyInstaller...")
        subprocess.run(pyinstaller_command, check=True)

        # Post-processing: Manually create the desired structure
        dist_dir = os.path.join('dist', exe_name)
        project_files_dir = os.path.join(dist_dir, exe_name+"-files")

        # Move the executable to the root of dist/
        # shutil.move(os.path.join(temp_exe_dir, exe_name), os.path.join(dist_dir, exe_name))

        # Move _internal and other PyInstaller files to dist/
        # for item in os.listdir(temp_exe_dir):
        #     if item != exe_name:
        #         shutil.move(os.path.join(temp_exe_dir, item), os.path.join(dist_dir, item))

        # Remove the now-empty temporary executable directory
        # os.rmdir(temp_exe_dir)

        # Create project files directory
        os.makedirs(project_files_dir, exist_ok=True)

        # Copy project files
        copy_project_files(temp_project_dir, project_files_dir, spec)

        print(f"PyInstaller finished successfully.")
        print(f"Executable created at: '{os.path.join(dist_dir, exe_name)}'")
        print(f"Project files copied to: '{project_files_dir}'")
        print(f"Bundled contents are in: '{dist_dir}'")

        # Final cleanup (keeping dist folder)
        cleanup_directories(exe_name, keep_dist=True)

    except subprocess.CalledProcessError as e:
        print(f"Error during PyInstaller execution: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    build_executable("run_bundle.py", "agent-zero")