#!/usr/bin/env python3
"""Diagnose server request issues"""

import asyncio
import json
import httpx
from comm.request_builder import RequestBuilder


async def diagnose():
    try:
        rb = RequestBuilder()
        req = rb.build_optimize_request('I need a 2.4 GHz patch antenna')
        
        payload = req.model_dump()
        print("Request payload:")
        print(json.dumps(payload, indent=2))
        print("\n" + "="*60 + "\n")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    'http://192.168.234.89:8000/api/v1/optimize',
                    json=payload,
                    timeout=10
                )
                print(f"Status: {response.status_code}")
                print(f"Response:\n{response.text}")
            except httpx.HTTPError as e:
                print(f"HTTP Error: {e}")
                if hasattr(e, 'response') and e.response:
                    print(f"Status: {e.response.status_code}")
                    print(f"Response:\n{e.response.text}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(diagnose())
