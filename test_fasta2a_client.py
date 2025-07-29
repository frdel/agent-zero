import asyncio
import sys
from typing import Any, Dict

from python.helpers.fasta2a_client import (
    connect_to_agent,
    is_client_available,
)


async def chat_loop(base_url: str):
    if not is_client_available():
        print("FastA2A client library not available – install `fasta2a httpx` first.")
        return

    # Establish connection (agent card is fetched internally)
    async with await connect_to_agent(base_url) as conn:
        print(f"[✓] Connected to {base_url}")
        print('Type "exit" to quit.')

        while True:
            try:
                user_msg = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if user_msg.lower() in {"exit", "quit"}:
                break

            try:
                # Send message & get immediate task response
                task_response: Dict[str, Any] = await conn.send_message(message=user_msg)
                task_id = task_response.get("result", {}).get("id")
                if not task_id:
                    print("[!] No task ID returned – response: ", task_response)
                    continue

                # Wait for the task to complete and fetch final result
                final = await conn.wait_for_completion(task_id)
                latest_history = final["result"].get("history", [])
                assistant_parts = latest_history[-1].get("parts", []) if latest_history else []
                assistant_text = "\n".join(
                    p.get("text", "") for p in assistant_parts if p.get("kind") == "text"
                )
                print(f"Assistant: {assistant_text}\n")
            except Exception as e:
                print(f"[!] Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_fasta2a_client.py <AGENT_BASE_URL>")
        sys.exit(1)

    asyncio.run(chat_loop(sys.argv[1]))
