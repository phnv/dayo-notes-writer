import asyncio
from mcp.server.mcpserver import MCPServer, Context
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(server: MCPServer):
    yield {'hello': 'world'}

mcp = MCPServer('test', lifespan=lifespan)

@mcp.tool()
def test_tool(ctx: Context) -> str:
    print('ctx attributes:', dir(ctx))
    if hasattr(ctx, 'session'):
        print('ctx.session attributes:', dir(ctx.session))
    if hasattr(ctx, 'request_context'):
        print('ctx.request_context attributes:', dir(ctx.request_context))
    return 'ok'

async def main():
    async with mcp._lifespan(mcp):
        try:
            # We must pass a Context to call_tool manually if we want to simulate it, but the SDK creates it.
            # Let's just create a mock request.
            # Actually call_tool might not create a full context in standalone test, let's see.
            res = await mcp.call_tool('test_tool', {})
        except Exception as e:
            print("Error:", e)

asyncio.run(main())
