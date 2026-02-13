#!/usr/bin/env python
"""
Script to run all tests with various options.
"""
import sys
import subprocess
import argparse


def run_tests(args):
    """Run pytest with specified arguments."""
    cmd = ['pytest']
    
    if args.verbose:
        cmd.append('-v')
    
    if args.coverage:
        cmd.extend(['--cov=src', '--cov-report=html', '--cov-report=term'])
    
    if args.failed:
        cmd.append('--lf')  # Run last failed tests
    
    if args.exitfirst:
        cmd.append('-x')  # Exit on first failure
    
    if args.markers:
        cmd.extend(['-m', args.markers])
    
    if args.keyword:
        cmd.extend(['-k', args.keyword])
    
    if args.file:
        cmd.append(args.file)
    
    # Add any additional pytest args
    if args.pytest_args:
        cmd.extend(args.pytest_args)
    
    print(f"Running: {' '.join(cmd)}")
    print("-" * 70)
    
    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description='Run tests for IMU Stream Processing project',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                    # Run all tests
  python run_tests.py -v                 # Verbose output
  python run_tests.py -c                 # With coverage report
  python run_tests.py -f test_config.py  # Run specific file
  python run_tests.py -k "test_init"     # Run tests matching keyword
  python run_tests.py -m "not slow"      # Skip slow tests
  python run_tests.py --failed           # Re-run failed tests
        """
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    parser.add_argument(
        '-c', '--coverage',
        action='store_true',
        help='Generate coverage report'
    )
    
    parser.add_argument(
        '--failed',
        action='store_true',
        help='Run only tests that failed last time'
    )
    
    parser.add_argument(
        '-x', '--exitfirst',
        action='store_true',
        help='Exit on first test failure'
    )
    
    parser.add_argument(
        '-f', '--file',
        type=str,
        help='Run specific test file'
    )
    
    parser.add_argument(
        '-k', '--keyword',
        type=str,
        help='Run tests matching keyword expression'
    )
    
    parser.add_argument(
        '-m', '--markers',
        type=str,
        help='Run tests matching marker expression (e.g., "not slow")'
    )
    
    parser.add_argument(
        'pytest_args',
        nargs='*',
        help='Additional arguments to pass to pytest'
    )
    
    args = parser.parse_args()
    
    # Check if pytest is installed
    try:
        subprocess.run(['pytest', '--version'], 
                      capture_output=True, 
                      check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: pytest is not installed.")
        print("Install with: pip install -r requirements-test.txt")
        return 1
    
    return run_tests(args)


if __name__ == '__main__':
    sys.exit(main())
