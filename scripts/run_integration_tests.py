#!/usr/bin/env python
"""
Integration Test Runner & Validator

Validates the client implementation against test requirements and runs integration tests.
Can be executed directly: python run_integration_tests.py
"""

import asyncio
import sys
import json
from pathlib import Path
from typing import Dict, Any

# Add src and project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from utils.logger import get_logger
from tests.integration.test_integration_suite import (
    run_all_integration_tests,
    print_test_report,
    IntegrationTestResults
)

logger = get_logger(__name__)


class ClientImplementationValidator:
    """Validates that client has all required implementations"""
    
    def __init__(self):
        self.checks: Dict[str, bool] = {}
    
    def check_module_exists(self, module_path: str, module_name: str) -> bool:
        """Check if required module exists"""
        try:
            __import__(module_path)
            self.checks[f"Module: {module_name}"] = True
            logger.info(f"✓ {module_name} module exists")
            return True
        except ImportError as e:
            self.checks[f"Module: {module_name}"] = False
            logger.error(f"✗ {module_name} module missing: {e}")
            return False
    
    def check_class_exists(self, module_path: str, class_name: str) -> bool:
        """Check if required class exists"""
        try:
            module = __import__(module_path, fromlist=[class_name])
            getattr(module, class_name)
            self.checks[f"Class: {class_name}"] = True
            logger.info(f"✓ {class_name} class exists")
            return True
        except (ImportError, AttributeError) as e:
            self.checks[f"Class: {class_name}"] = False
            logger.error(f"✗ {class_name} class missing: {e}")
            return False
    
    def check_file_exists(self, file_path: str, description: str) -> bool:
        """Check if required file exists"""
        path = Path(file_path)
        if path.exists():
            self.checks[f"File: {description}"] = True
            logger.info(f"✓ {description} file exists")
            return True
        else:
            self.checks[f"File: {description}"] = False
            logger.error(f"✗ {description} file missing: {file_path}")
            return False
    
    def validate_all(self) -> bool:
        """Run all validation checks"""
        logger.info("\n" + "=" * 70)
        logger.info("CLIENT IMPLEMENTATION VALIDATION")
        logger.info("=" * 70 + "\n")
        
        all_valid = True
        
        # Check core modules
        logger.info("Checking core modules...")
        required_modules = [
            ("comm.ws_client", "WebSocket Client"),
            ("comm.initializer", "Client Initializer"),
            ("comm.error_handler", "Error Handler"),
            ("session.session_store", "Session Store"),
            ("executor.execution_engine", "Execution Engine"),
        ]
        
        for module_path, name in required_modules:
            if not self.check_module_exists(module_path, name):
                all_valid = False
        
        # Check key classes
        logger.info("\nChecking key classes...")
        required_classes = [
            ("comm.ws_client", "SessionEventListener"),
            ("comm.initializer", "ClientInitializer"),
            ("comm.error_handler", "ErrorHandler"),
            ("session.session_store", "SessionStore"),
            ("executor.execution_engine", "ExecutionEngine"),
        ]
        
        for module_path, class_name in required_classes:
            if not self.check_class_exists(module_path, class_name):
                all_valid = False
        
        # Check persistence directory
        logger.info("\nChecking persistence...")
        if not self.check_file_exists("test_checkpoints", "Session persistence"):
            Path("test_checkpoints").mkdir(parents=True, exist_ok=True)
            logger.info("✓ Created test_checkpoints directory")
        
        # Check documentation
        logger.info("\nChecking documentation...")
        docs = [
            ("docs/API.md", "API documentation"),
            ("docs/DEVELOPMENT.md", "Development guide"),
            ("docs/ARCHITECTURE.md", "Architecture guide"),
        ]
        
        for doc_file, desc in docs:
            doc_path = PROJECT_ROOT / doc_file
            self.check_file_exists(str(doc_path), desc)
        
        logger.info("\n" + "=" * 70)
        total_checks = len(self.checks)
        passed_checks = sum(1 for v in self.checks.values() if v)
        logger.info(f"Validation Complete: {passed_checks}/{total_checks} checks passed")
        logger.info("=" * 70 + "\n")
        
        return all_valid


async def run_tests():
    """Main test runner"""
    
    # Step 1: Validate implementation
    print("\n" + "=" * 70)
    print("STEP 1: VALIDATING CLIENT IMPLEMENTATION")
    print("=" * 70 + "\n")
    
    validator = ClientImplementationValidator()
    if not validator.validate_all():
        logger.error("\n❌ CLIENT VALIDATION FAILED - Cannot proceed with tests")
        logger.error("Please ensure all required modules and classes are implemented")
        return False
    
    logger.info("\n✅ CLIENT VALIDATION PASSED\n")
    
    # Step 2: Run integration tests
    print("\n" + "=" * 70)
    print("STEP 2: RUNNING INTEGRATION TESTS")
    print("=" * 70 + "\n")
    
    try:
        results = await run_all_integration_tests()
        print_test_report(results)
        
        # Step 3: Generate test report
        print("\n" + "=" * 70)
        print("STEP 3: SAVING TEST RESULTS")
        print("=" * 70 + "\n")
        
        report_file = PROJECT_ROOT / "artifacts" / "reports" / "test_results.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_data = {}
        
        for suite_name, suite_results in results.items():
            report_data[suite_name] = suite_results.summary()
        
        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)
        
        logger.info(f"✓ Test results saved to {report_file}")
        
        # Determine success
        total_failed = sum(
            suite.summary()["failed"] 
            for suite in results.values()
        )
        
        if total_failed == 0:
            logger.info("\n" + "=" * 70)
            logger.info("✅ ALL INTEGRATION TESTS PASSED")
            logger.info("=" * 70)
            logger.info("\nThe client is ready for production integration with antenna_server!")
            logger.info("\nNext Steps:")
            logger.info(f"1. Review test results in {report_file}")
            logger.info("2. Review the current architecture and API docs under docs/")
            logger.info("3. Begin Phase 2: Joint integration testing")
            logger.info("=" * 70 + "\n")
            return True
        else:
            logger.error("\n" + "=" * 70)
            logger.error(f"❌ {total_failed} INTEGRATION TEST(S) FAILED")
            logger.error("=" * 70)
            logger.error("\nPlease review failures and fix before proceeding")
            logger.error("=" * 70 + "\n")
            return False
            
    except Exception as e:
        logger.error(f"\n❌ Error running integration tests: {e}", exc_info=True)
        return False


def print_usage():
    """Print usage information"""
    print("""
Integration Test Runner
=======================

Usage:
  python run_integration_tests.py

This script will:
1. Validate client implementation
2. Run 3 integration test suites:
   - End-to-End Flow (health → optimize → execute → feedback)
   - Session Recovery (persistence & reload)
   - Payload Validation (schema compliance)
3. Generate test report (artifacts/reports/test_results.json)

Requirements:
- Server running at http://localhost:8000
- Python 3.7+
- All client modules installed

For more info, see:
- docs/API.md
- docs/DEVELOPMENT.md
- docs/archive/
    """)


def main():
    """Entry point"""
    
    # Check for help flag
    if "--help" in sys.argv or "-h" in sys.argv:
        print_usage()
        return 0
    
    # Run tests
    try:
        success = asyncio.run(run_tests())
        return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("\n\nTest run cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"\n\nUnexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
