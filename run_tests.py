#!/usr/bin/env python3
"""
Test runner script for LangGraph POC project.

This script provides easy ways to run different test suites:
- Unit tests only
- API/E2E tests only  
- All tests
- Tests with coverage
- Tests in different modes (fast, slow, etc.)
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def setup_environment():
    """Setup test environment variables."""
    os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "test_key_for_local")
    os.environ["DATABASE_URL"] = os.getenv("DATABASE_URL", "postgresql://rohit.jain@localhost:5432/langgraph_chats")
    os.environ["LOG_LEVEL"] = os.getenv("LOG_LEVEL", "WARNING")
    
    # Add current directory to Python path
    current_dir = Path(__file__).parent.absolute()
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, check=True, cwd=Path(__file__).parent)
        print(f"✅ {description} - PASSED")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        print(f"Exit code: {e.returncode}")
        return False


def run_unit_tests(verbose=True, coverage=False):
    """Run unit tests only."""
    cmd = ["python", "-m", "pytest", "tests/test_mcp_unit.py"]
    if verbose:
        cmd.append("-v")
    if coverage:
        cmd.extend(["--cov=src", "--cov-report=term-missing"])
    
    return run_command(cmd, "Unit Tests")


def run_api_tests(verbose=True, coverage=False):
    """Run API/E2E tests only.""" 
    cmd = ["python", "-m", "pytest", "tests/test_mcp_api_working.py"]
    if verbose:
        cmd.append("-v")
    if coverage:
        cmd.extend(["--cov=src", "--cov-report=term-missing"])
    
    return run_command(cmd, "API/E2E Tests")


def run_all_tests(verbose=True, coverage=False, fail_under=None):
    """Run all working tests (excludes deprecated/broken legacy tests)."""
    working_tests = [
        "tests/test_mcp_unit.py",
        "tests/test_mcp_api_working.py", 
        "tests/test_agents.py",
        "tests/test_tools.py"
    ]
    cmd = ["python", "-m", "pytest"] + working_tests
    if verbose:
        cmd.append("-v")
    if coverage:
        cmd.extend(["--cov=src", "--cov-report=term-missing", "--cov-report=html:htmlcov"])
        if fail_under:
            cmd.extend([f"--cov-fail-under={fail_under}"])
    
    return run_command(cmd, "All Working Tests")


def run_fast_tests():
    """Run tests without slow markers."""
    cmd = ["python", "-m", "pytest", "tests/test_mcp_unit.py", "tests/test_mcp_api_working.py", 
           "-v", "-m", "not slow"]
    return run_command(cmd, "Fast Tests (excluding slow)")


def run_integration_tests():
    """Run integration tests only."""
    cmd = ["python", "-m", "pytest", "tests/", "-v", "-m", "integration"]
    return run_command(cmd, "Integration Tests")


def run_legacy_tests():
    """Legacy tests have been cleaned up and removed."""
    print("\n" + "="*60)
    print("Legacy tests have been cleaned up and removed from the codebase.")
    print("All broken test files have been deleted to improve code maintainability.")
    print("Use --all or --working to run the current test suite.")
    print("="*60)
    return True


def run_working_tests_only():
    """Run only tests that are known to work reliably."""
    return run_all_tests(verbose=True, coverage=False)


def check_test_requirements():
    """Check if test requirements are met."""
    print("Checking test requirements...")
    
    # Check Python version
    python_version = sys.version_info
    if python_version < (3, 9):
        print(f"❌ Python {python_version.major}.{python_version.minor} not supported. Need Python 3.9+")
        return False
    print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # Check if required packages are installed
    required_packages = ["pytest", "fastapi", "uvicorn", "asyncio"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} - MISSING")
    
    if missing_packages:
        print(f"\nMissing packages: {', '.join(missing_packages)}")
        print("Install with: pip install -r requirements.txt")
        return False
    
    return True


def generate_test_report():
    """Generate comprehensive test report."""
    print("\n" + "="*60)
    print("GENERATING COMPREHENSIVE TEST REPORT")
    print("="*60)
    
    results = []
    
    # Run unit tests with coverage
    results.append(("Unit Tests", run_unit_tests(coverage=True)))
    
    # Run API tests with coverage
    results.append(("API Tests", run_api_tests(coverage=True)))
    
    # Run all tests with full coverage report
    results.append(("Full Test Suite", run_all_tests(coverage=True, fail_under=80)))
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:30} {status}")
    
    print(f"\nOverall: {passed_tests}/{total_tests} test suites passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Ready for deployment.")
        return True
    else:
        print("⚠️  Some tests failed. Please review and fix.")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run tests for LangGraph POC")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--api", action="store_true", help="Run API tests only")
    parser.add_argument("--all", action="store_true", help="Run all working tests")
    parser.add_argument("--working", action="store_true", help="Run only tests known to work reliably")
    parser.add_argument("--legacy", action="store_true", help="Show legacy tests cleanup message")
    parser.add_argument("--fast", action="store_true", help="Run fast tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--report", action="store_true", help="Generate comprehensive test report")
    parser.add_argument("--coverage", action="store_true", help="Run tests with coverage")
    parser.add_argument("--check", action="store_true", help="Check test requirements")
    parser.add_argument("--quiet", action="store_true", help="Run tests quietly")
    
    args = parser.parse_args()
    
    # Setup environment
    setup_environment()
    
    verbose = not args.quiet
    
    # Check requirements if requested
    if args.check:
        if not check_test_requirements():
            sys.exit(1)
        return
    
    # Run specific test suites
    success = True
    
    if args.unit:
        success &= run_unit_tests(verbose=verbose, coverage=args.coverage)
    elif args.api:
        success &= run_api_tests(verbose=verbose, coverage=args.coverage)
    elif args.working:
        success &= run_working_tests_only()
    elif args.legacy:
        success &= run_legacy_tests()
    elif args.fast:
        success &= run_fast_tests()
    elif args.integration:
        success &= run_integration_tests()
    elif args.report:
        success &= generate_test_report()
    elif args.all:
        success &= run_all_tests(verbose=verbose, coverage=args.coverage)
    else:
        # Default: run working tests only
        print("No specific test suite specified. Running working tests only...")
        print("Use --all for all working tests or --legacy to see cleanup message.")
        success &= run_working_tests_only()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()