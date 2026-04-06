#!/usr/bin/env python3
"""
Health Check - Verify server and CST availability

Usage:
    python health_check.py
"""

import sys
import json
from pathlib import Path
import asyncio

# Add src and project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from comm.server_connector import ServerConnector
from utils.logger import get_logger


logger = get_logger(__name__)


async def check_server_health():
    """Check if antenna_server is running and healthy"""
    try:
        with open(PROJECT_ROOT / "config.json", "r") as f:
            config = json.load(f)
        
        server_config = config.get("server", {})
        base_url = server_config.get("base_url", "http://localhost:8000")
        
        print(f"🔍 Checking server at: {base_url}")
        
        async with ServerConnector(base_url, timeout_sec=5) as connector:
            try:
                result = await connector.get("/api/v1/health")
                print(f"✅ Server is HEALTHY")
                print(f"   Response: {result}")
                return True
            except Exception as e:
                print(f"❌ Server is NOT RESPONDING")
                print(f"   Error: {str(e)}")
                return False
    except Exception as e:
        print(f"❌ Error checking server: {str(e)}")
        return False


def check_cst_availability():
    """Check if CST Studio is installed"""
    try:
        import json
        with open(PROJECT_ROOT / "config.json", "r") as f:
            config = json.load(f)
        
        cst_config = config.get("cst", {})
        cst_exe = Path(cst_config.get("executable_path", ""))
        
        print(f"🔍 Checking CST at: {cst_exe}")
        
        if cst_exe.exists():
            print(f"✅ CST Studio FOUND")
            print(f"   Path: {cst_exe}")
            return True
        else:
            print(f"❌ CST Studio NOT FOUND")
            print(f"   Expected at: {cst_exe}")
            print(f"   Please install CST Studio 2024 or update config.json")
            return False
    except Exception as e:
        print(f"❌ Error checking CST: {str(e)}")
        return False


async def main():
    """Run all health checks"""
    print("=" * 60)
    print("Antenna Client - Health Check")
    print("=" * 60)
    print()
    
    # Check server
    print("1. Server Connection")
    print("-" * 60)
    server_ok = await check_server_health()
    print()
    
    # Check CST
    print("2. CST Studio Availability")
    print("-" * 60)
    cst_ok = check_cst_availability()
    print()
    
    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    if server_ok:
        print("✅ Server: Ready")
    else:
        print("❌ Server: Not available")
        print("   👉 Start antenna_server with: python main.py")
    
    if cst_ok:
        print("✅ CST Studio: Ready")
    else:
        print("❌ CST Studio: Not installed")
        print("   👉 Install from: https://www.3ds.com/products/simulia/cst")
    
    print()
    
    if server_ok and cst_ok:
        print("🎉 All systems ready! Run antenna_client with full features.")
    elif server_ok:
        print("⚠️  Server is ready. CST features will be disabled.")
    else:
        print("ℹ️  Run antenna_client in demo mode (UI only).")
    
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nHealthcheck cancelled.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Healthcheck failed: {e}")
        print(f"\n❌ Healthcheck failed: {e}")
        sys.exit(1)
