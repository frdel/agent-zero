import os
import subprocess
import sys
import site
import shutil
from pathlib import Path
import pathspec
import importlib
import importlib.metadata as metadata

def get_package_data_folder(package_name):
    """Return the package path if it contains data files."""
    try:
        package = importlib.import_module(package_name)
        package_path = os.path.dirname(package.__file__)  # type: ignore
        if not package_path.endswith("site-packages"):
            has_data = any(
                file.endswith((".json", ".txt", ".csv", ".yml", ".yaml"))
                for root, dirs, files in os.walk(package_path)
                for file in files
            )
            if has_data:
                return package_path
    except ImportError:
        print(f"Warning: Unable to import {package_name}. Skipping data folder discovery for this package.")
    return None

def get_add_data_args():
    """Return an array of --add-data arguments for PyInstaller, one per package."""
    add_data_args = []
    installed_packages = [dist.metadata["Name"] for dist in metadata.distributions()]
    for package in installed_packages:
        package_data_folder = get_package_data_folder(package)
        if package_data_folder:
            add_data_args.append(f"--add-data={package_data_folder}{os.pathsep}{package}")
    return add_data_args

def get_site_packages_path():
    """Get the path to the site-packages directory of the current environment."""
    if hasattr(site, "getsitepackages"):
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
        return pathspec.PathSpec.from_lines("gitwildmatch", [])
    with open(gitignore_path, "r") as f:
        return pathspec.PathSpec.from_lines("gitwildmatch", f)

def copy_project_files(src_dir, dst_dir, spec):
    """Copy project files respecting .gitignore rules using pathspec."""
    src_path = Path(src_dir)
    for root, dirs, files in os.walk(src_dir):
        rel_root = Path(root).relative_to(src_path)
        for file in files:
            rel_path = rel_root / file
            if not spec.match_file(str(rel_path)):
                src_file = src_path / rel_path
                dst_file = Path(dst_dir) / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)

def cleanup_directories(bundle_name, build_dir, dist_dir, keep_dist=False):
    """Remove build directory and .spec file. Optionally keep dist."""
    if not keep_dist and os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    spec_file = f"{bundle_name}.spec"
    if os.path.exists(spec_file):
        os.remove(spec_file)

def build_executable(script_path, exe_name=None):
    """Run PyInstaller with the correct site-packages path, clean, and additional data."""
    try:
        # Resolve the absolute path to the script, relative to the current file location (__file__)
        bundling_script_dir = Path(__file__).parent.resolve()
        script_path = (bundling_script_dir / script_path).resolve()
        script_name = script_path.name  # run_bundle.py
        project_dir = script_path.parent  # Folder containing run_bundle.py
        
        # Define build and dist paths under the /bundle directory (bundling_script_dir)
        build_dir = bundling_script_dir / "build"
        dist_dir = bundling_script_dir / "dist"

        # Initial cleanup
        cleanup_directories(exe_name, build_dir, dist_dir, keep_dist=False)

        site_packages_path = get_site_packages_path()
        print(f"Using site-packages path: {site_packages_path}")
        print(f"Bundling project from: {project_dir}")
        print(f"Build directory: {build_dir}")
        print(f"Dist directory: {dist_dir}")

        # Parse .gitignore in the project directory
        gitignore_path = project_dir / ".gitignore"
        spec = parse_gitignore(gitignore_path)

        # Create a temporary directory for project files inside build
        temp_project_dir = build_dir / "temp_project"
        os.makedirs(temp_project_dir, exist_ok=True)

        # Copy project files respecting .gitignore
        copy_project_files(project_dir, temp_project_dir, spec)

        # Construct the PyInstaller command
        pyinstaller_command = [
            "pyinstaller",
            "--clean",
            "--noconfirm",
            "--onedir",
            f"--paths={site_packages_path}",
            f"--workpath={build_dir}",  # Specify the build directory under /bundle
            f"--distpath={dist_dir}",   # Specify the dist directory under /bundle
        ]

        # Add data arguments
        pyinstaller_command.extend(get_add_data_args())

        # Add custom name if provided
        if exe_name:
            pyinstaller_command.append(f"--name={exe_name}")
        else:
            exe_name = os.path.splitext(script_name)[0]

        # Add the script path (in the temp_project directory)
        pyinstaller_command.append(os.path.join(temp_project_dir, script_name))

        # Run the PyInstaller command
        print("Running PyInstaller...")
        subprocess.run(pyinstaller_command, check=True)

        # Post-processing: Create a folder for project files inside dist/
        project_files_dir = dist_dir / exe_name / f"{exe_name}-files"
        os.makedirs(project_files_dir, exist_ok=True)

        # Copy project files to the dist folder
        copy_project_files(temp_project_dir, project_files_dir, spec)

        print(f"PyInstaller finished successfully.")
        print(f"Executable created at: '{dist_dir}/{exe_name}'")
        print(f"Project files copied to: '{project_files_dir}'")

        # Final cleanup (keeping dist folder)
        cleanup_directories(exe_name, build_dir, dist_dir, keep_dist=True)

    except subprocess.CalledProcessError as e:
        print(f"Error during PyInstaller execution: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    build_executable("../run_bundle.py", "agent-zero")
