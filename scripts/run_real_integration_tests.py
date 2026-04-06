#!/usr/bin/env python3
"""
Real Integration Test Runner

Runs actual server communication tests against antenna_server.
Uses config.json to load server URL.

Usage: python run_real_integration_tests.py
"""

import asyncio
import sys
import json
from pathlib import Path

# Add src and project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from tests.integration.test_integration_suite import (
    run_all_integration_tests,
    print_test_report
)
from utils.logger import get_logger

logger = get_logger(__name__)

def main():
    """Main test runner"""
    
    # Load config
    config_path = PROJECT_ROOT / "config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    server_url = config.get("server", {}).get("base_url", "http://192.168.29.147:8000")
    
    print("\n" + "=" * 70)
    print("REAL INTEGRATION TEST SUITE")
    print("=" * 70)
    print(f"Server URL: {server_url}")
    print(f"Timeout: {config.get('server', {}).get('timeout_sec', 60)}s")
    print("=" * 70 + "\n")
    
    # Run tests
    try:
        results = asyncio.run(run_all_integration_tests())
        print_test_report(results)
        
        # Determine exit code
        total_failed = sum(
            suite_results.summary()["failed"]
            for suite_results in results.values()
        )
        
        sys.exit(0 if total_failed == 0 else 1)
        
    except Exception as e:
        logger.error(f"Test suite failed with error: {e}")
        print(f"\n[ERROR] Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
