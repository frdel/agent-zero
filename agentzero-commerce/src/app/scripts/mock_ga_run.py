import asyncio

from ..ga_client import run_report


async def main():
    data = await run_report("demo", ["eventName"], ["eventCount"])
    print(data)


if __name__ == "__main__":
    asyncio.run(main())
