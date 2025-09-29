import asyncio
import edge_tts

async def main():
    vm = await edge_tts.VoicesManager.create()
    print("edge-tts version check OK")
    print("Total voices:", len(vm.voices))
    sample = [v["ShortName"] for v in vm.voices[:8]]
    print("Sample voices:", sample)

if __name__ == "__main__":
    asyncio.run(main())