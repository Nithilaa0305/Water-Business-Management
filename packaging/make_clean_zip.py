import os
import zipfile
from pathlib import Path

def create_clean_zip():
    project_root = Path(r"D:\stock").resolve()
    dest_zip_paths = [
        Path(r"D:\stock.zip"),
        Path(r"D:\stock\stock.zip"),
        Path(r"D:\stock\dist\stock.zip"),
    ]
    
    # Excluded directory and file names
    EXCLUDE_DIRS = {
        'venv', '.git', '__pycache__', 'build', 'dist', 
        '.pytest_cache', '.idea', '.vscode'
    }
    EXCLUDE_EXTS = {'.pyc', '.pyo', '.pyd', '.zip'}

    for dest_path in dest_zip_paths:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if dest_path.exists():
            try:
                dest_path.unlink()
            except Exception as e:
                print(f"Warning removing {dest_path}: {e}")

    primary_zip = dest_zip_paths[0]
    print(f"Creating clean zip archive at: {primary_zip}")
    
    file_count = 0
    with zipfile.ZipFile(primary_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(project_root):
            # Prune excluded directories in-place
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
            
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in EXCLUDE_EXTS:
                    continue
                if file.startswith('.'):
                    continue
                
                rel_path = file_path.relative_to(project_root)
                # Store with forward slashes for cross-platform compatibility
                arcname = str(rel_path).replace('\\', '/')
                zf.write(file_path, arcname)
                file_count += 1

    file_size_kb = primary_zip.stat().st_size / 1024
    print(f"Successfully archived {file_count} files into {primary_zip} ({file_size_kb:.1f} KB)")
    
    # Duplicate to D:\stock\stock.zip and D:\stock\dist\stock.zip
    import shutil
    for copy_target in dest_zip_paths[1:]:
        shutil.copy2(primary_zip, copy_target)
        print(f"Copied clean zip to: {copy_target}")

if __name__ == "__main__":
    create_clean_zip()
