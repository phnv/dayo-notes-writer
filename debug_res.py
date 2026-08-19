import asyncio
from pathlib import Path
from note_writer.interfaces.mcp import build_server, AppState, _state
from note_writer.domain.config.models import Config
from note_writer.domain.config.resolver import PathResolver
from note_writer.infrastructure.filesystem import PathlibFilesystem
import note_writer.interfaces.mcp as mcp_module

config = Config(templates={'weekly': 'weekly.md'})
fs = PathlibFilesystem()
resolver = PathResolver(Path('.'))
server = build_server(config, fs, resolver, Path('.'), Path('.'))

mcp_module._state = AppState(config, fs, resolver, Path('.'), Path('.'))

async def main():
    try:
        Path('weekly.md').write_text('Weekly Template')
        res = await server.read_resource('templates://weekly')
        print("Type:", type(res))
        if isinstance(res, list):
            print("First element type:", type(res[0]))
            print("Has text:", hasattr(res[0], 'text'))
            print("Dict:", getattr(res[0], '__dict__', None))
    finally:
        Path('weekly.md').unlink()

asyncio.run(main())
