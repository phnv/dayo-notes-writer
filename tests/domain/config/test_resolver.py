import pytest
from pathlib import Path
from note_writer.domain.config.resolver import PathResolver
from note_writer.domain.errors import ConfigurationError

def test_resolve_relative_path():
    app_root = Path("/app/root")
    resolver = PathResolver(app_root)
    
    assert resolver.resolve("templates/daily.md") == Path("/app/root/templates/daily.md")
    assert resolver.resolve("./templates/daily.md") == Path("/app/root/templates/daily.md")

def test_resolve_linux_absolute_path():
    app_root = Path("/app/root")
    resolver = PathResolver(app_root)
    
    assert resolver.resolve("/home/user/notes") == Path("/home/user/notes")
    assert resolver.resolve("/mnt/c/notes") == Path("/mnt/c/notes")

def test_resolve_home_directory_path():
    app_root = Path("/app/root")
    resolver = PathResolver(app_root)
    
    resolved = resolver.resolve("~/notes")
    assert resolved.is_absolute()
    assert str(resolved).endswith("notes")

def test_resolve_windows_path_with_wslpath():
    app_root = Path("/app/root")
    resolver = PathResolver(app_root)
    
    # Needs wslpath to exist on the system (which it does in WSL)
    resolved = resolver.resolve(r"C:\Windows\System32")
    assert resolved == Path("/mnt/c/Windows/System32")

def test_resolve_windows_unc_path_with_wslpath():
    app_root = Path("/app/root")
    resolver = PathResolver(app_root)
    
    # Resolving a UNC path C:/...
    resolved = resolver.resolve("C:/Users")
    assert resolved == Path("/mnt/c/Users")
