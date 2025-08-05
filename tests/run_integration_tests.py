#!/usr/bin/env python3
"""
Integration test runner for Homebrew Bottles Sync System.

This script runs all integration tests and provides detailed reporting
on test results, coverage, and performance metrics.
"""

import sys
import os
import time
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Any

# Add project paths
sys.path.append('.')
sys.path.append('shared')


def run_pytest_command(test_files: List[str], extra_args: List[str] = None) -> Dict[str, Any]:
    """
    Run pytest with specified test files and arguments.
    
    Args:
        test_files: List of test file paths
        extra_args: Additional pytest arguments
        
    Returns:
        Dictionary with test results
    """
    cmd = ['python', '-m', 'pytest'] + test_files
    
    # Default pytest arguments
    default_args = [
        '-v',  # Verbose output
        '--tb=short',  # Short traceback format
        '--strict-markers',  # Strict marker checking
        '--disable-warnings',  # Disable warnings for cleaner output
        '--color=yes',  # Colored output
    ]
    
    if extra_args:
        cmd.extend(extra_args)
    else:
        cmd.extend(default_args)
    
    print(f"Running command: {' '.join(cmd)}")
    print("-" * 80)
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'duration': duration
        }
        
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'returncode': -1,
            'stdout': '',
            'stderr': 'Test execution timed out after 5 minutes',
            'duration': 300
        }
    except Exception as e:
        return {
            'success': False,
            'returncode': -1,
            'stdout': '',
            'stderr': f'Error running tests: {str(e)}',
            'duration': 0
        }


def check_dependencies() -> bool:
    """
    Check if required dependencies are available.
    
    Returns:
        True if all dependencies are available, False otherwise
    """
    required_modules = [
        'pytest',
        'boto3',
        'requests',
        'aiohttp',
        'aiofiles'
    ]
    
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"❌ Missing required modules: {', '.join(missing_modules)}")
        print("Install them with: pip install " + ' '.join(missing_modules))
        return False
    
    print("✅ All required dependencies are available")
    return True


def validate_test_files() -> List[str]:
    """
    Validate and return list of integration test files.
    
    Returns:
        List of valid test file paths
    """
    test_dir = Path('tests')
    integration_test_files = [
        'test_integration_e2e.py',
        'test_integration_error_scenarios.py',
        'test_integration.py'  # Existing integration test
    ]
    
    valid_files = []
    
    for test_file in integration_test_files:
        test_path = test_dir / test_file
        if test_path.exists():
            valid_files.append(str(test_path))
            print(f"✅ Found test file: {test_file}")
        else:
            print(f"⚠️  Test file not found: {test_file}")
    
    return valid_files


def print_test_summary(results: Dict[str, Dict[str, Any]]) -> None:
    """
    Print a summary of test results.
    
    Args:
        results: Dictionary of test results by test suite
    """
    print("\n" + "=" * 80)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 80)
    
    total_duration = 0
    total_suites = len(results)
    passed_suites = 0
    
    for suite_name, result in results.items():
        status = "✅ PASSED" if result['success'] else "❌ FAILED"
        duration = result['duration']
        total_duration += duration
        
        if result['success']:
            passed_suites += 1
        
        print(f"{suite_name:<40} {status:<10} ({duration:.2f}s)")
        
        if not result['success'] and result['stderr']:
            print(f"  Error: {result['stderr'][:100]}...")
    
    print("-" * 80)
    print(f"Total test suites: {total_suites}")
    print(f"Passed: {passed_suites}")
    print(f"Failed: {total_suites - passed_suites}")
    print(f"Total duration: {total_duration:.2f}s")
    print(f"Success rate: {(passed_suites / total_suites * 100):.1f}%")
    
    if passed_suites == total_suites:
        print("\n🎉 All integration tests passed!")
    else:
        print(f"\n⚠️  {total_suites - passed_suites} test suite(s) failed")


def run_specific_test_categories(categories: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Run specific test categories.
    
    Args:
        categories: List of test categories to run
        
    Returns:
        Dictionary of test results
    """
    category_mapping = {
        'lambda': 'TestLambdaBasedSyncWorkflow',
        'ecs': 'TestECSBasedSyncWorkflow',
        'errors': 'TestErrorHandlingAndRecovery',
        'communication': 'TestCrossServiceCommunication',
        'network': 'TestNetworkErrorScenarios',
        'corruption': 'TestDataCorruptionScenarios',
        'resources': 'TestResourceExhaustionScenarios',
        'concurrency': 'TestConcurrencyAndRaceConditions',
        'edge': 'TestEdgeCaseScenarios'
    }
    
    results = {}
    test_files = validate_test_files()
    
    for category in categories:
        if category in category_mapping:
            class_name = category_mapping[category]
            print(f"\n🧪 Running {category} tests ({class_name})...")
            
            result = run_pytest_command(
                test_files,
                ['-k', class_name, '-v']
            )
            
            results[f"{category}_tests"] = result
            
            if result['success']:
                print(f"✅ {category} tests passed")
            else:
                print(f"❌ {category} tests failed")
                if result['stderr']:
                    print(f"Error: {result['stderr']}")
        else:
            print(f"⚠️  Unknown test category: {category}")
    
    return results


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description='Run integration tests for Homebrew Bottles Sync System'
    )
    
    parser.add_argument(
        '--categories',
        nargs='+',
        choices=['lambda', 'ecs', 'errors', 'communication', 'network', 
                'corruption', 'resources', 'concurrency', 'edge', 'all'],
        default=['all'],
        help='Test categories to run'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Run with coverage reporting'
    )
    
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Run tests in parallel'
    )
    
    args = parser.parse_args()
    
    print("🚀 Starting Homebrew Bottles Sync Integration Tests")
    print("=" * 80)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Validate test files
    test_files = validate_test_files()
    if not test_files:
        print("❌ No valid test files found")
        sys.exit(1)
    
    # Prepare pytest arguments
    pytest_args = []
    
    if args.verbose:
        pytest_args.extend(['-v', '-s'])
    
    if args.coverage:
        pytest_args.extend(['--cov=shared', '--cov=lambda', '--cov=ecs', '--cov-report=html'])
    
    if args.parallel:
        pytest_args.extend(['-n', 'auto'])
    
    # Run tests
    results = {}
    
    if 'all' in args.categories:
        print("\n🧪 Running all integration tests...")
        
        # Run each test file separately for better reporting
        for test_file in test_files:
            test_name = Path(test_file).stem
            print(f"\n📋 Running {test_name}...")
            
            result = run_pytest_command([test_file], pytest_args)
            results[test_name] = result
            
            if result['stdout']:
                print(result['stdout'])
            
            if not result['success'] and result['stderr']:
                print(f"❌ Error in {test_name}:")
                print(result['stderr'])
    else:
        # Run specific categories
        results = run_specific_test_categories(args.categories)
    
    # Print summary
    print_test_summary(results)
    
    # Exit with appropriate code
    all_passed = all(result['success'] for result in results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()