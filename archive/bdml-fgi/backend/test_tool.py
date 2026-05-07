from agents import Agent, Runner
from agents.tool import function_tool
import asyncio

@function_tool
def test(x: int) -> int:
    """Test function"""
    return x

a = Agent(name="test", model="gpt-4o-mini", tools=[test])

async def main():
    try:
        res = await Runner.run(a, "test 5")
        print("Success:", res.final_output)
    except Exception as e:
        print("Runner Execution Error:", type(e).__name__, ":", e)

asyncio.run(main())
