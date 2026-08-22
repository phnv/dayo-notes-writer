import asyncio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.prompts import base
from mcp.types import InputRequiredResult, ElicitRequest, ElicitRequestFormParams

mcp = MCPServer("test")

@mcp.prompt()
def write_note(raw_text: str, template: str = None, prompt: str = None, storage: str = None) -> list[base.Message] | InputRequiredResult:
    return InputRequiredResult(
        inputRequests={
            "missing_args": ElicitRequest(
                params=ElicitRequestFormParams(
                    mode="form",
                    message="Please provide both file_name and storage to update.",
                    requestedSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                )
            )
        }
    )

async def main():
    class DummyContext:
        pass
        
    try:
        res = await mcp._prompt_manager.render_prompt("write_note", {"raw_text": "hello"}, DummyContext())
        print("Success:")
        print(repr(res))
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
