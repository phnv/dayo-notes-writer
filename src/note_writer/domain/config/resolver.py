import os
import subprocess
from pathlib import Path
from note_writer.domain.errors import ConfigurationError

class PathResolver:
    def __init__(self, app_root: Path):
        self.app_root = app_root

    def is_windows_path(self, path_str: str) -> bool:
        r"""Check if a path string looks like a Windows path (C:\ or C:/ or UNC)."""
        if len(path_str) >= 2 and path_str[1] == ':':
            return True
        if path_str.startswith(r"\\"):
            return True
        return False

    def windows_to_wsl(self, path_str: str) -> Path:
        """Use the wslpath command to convert a Windows path to a WSL path."""
        try:
            result = subprocess.run(
                ["wslpath", "-u", path_str],
                capture_output=True,
                text=True,
                check=True
            )
            return Path(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            raise ConfigurationError(f"Failed to convert Windows path '{path_str}' via wslpath: {e.stderr}")
        except FileNotFoundError:
            raise ConfigurationError("wslpath command not found. Are you running in WSL?")

    def resolve(self, path_str: str) -> Path:
        """Resolve a configuration path string to a canonical absolute Path."""
        # Expand environment variables and ~
        expanded = os.path.expandvars(path_str)
        expanded = os.path.expanduser(expanded)
        
        if self.is_windows_path(expanded):
            return self.windows_to_wsl(expanded)

        p = Path(expanded)
        if p.is_absolute():
            return p
            
        return (self.app_root / p).resolve()
