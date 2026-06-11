#!/usr/bin/env python3
"""
Evaluation test runner.
"""

import sys
import json
import argparse
import importlib.util
from pathlib import Path
from typing import Dict, Any, List


def load_input_config(input_path: str) -> Dict[str, Any]:
    """
    Load input configuration from JSON file.

    Args:
        input_path: Path to input.json file

    Returns:
        Parsed configuration dictionary

    Raises:
        FileNotFoundError: If input file doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with open(input_file, 'r') as f:
        return json.load(f)


def resolve_test_module(test_name: str, base_path: Path) -> Path:
    """
    Resolve test name to module path.

    Args:
        test_name: Test identifier (e.g., "categorization/evaluate_categorization")
        base_path: Base directory for evaluation tests

    Returns:
        Path to the Python module

    Raises:
        FileNotFoundError: If module doesn't exist
    """
    # Convert test name to module path
    # e.g., "categorization/evaluate_categorization" -> "categorization/evaluate_categorization.py"
    module_path = base_path / f"{test_name}.py"

    if not module_path.exists():
        raise FileNotFoundError(
            f"Test module not found: {module_path}\n"
            f"Available tests:\n{list_available_tests(base_path)}"
        )

    return module_path


def list_available_tests(base_path: Path) -> str:
    """
    List all available test modules.

    Args:
        base_path: Base directory for evaluation tests

    Returns:
        Formatted string of available tests
    """
    tests = []
    for py_file in base_path.rglob("evaluate_*.py"):
        # Convert path to test identifier
        relative = py_file.relative_to(base_path)
        test_id = str(relative.with_suffix(''))
        tests.append(f"  - {test_id}")

    if not tests:
        return "  (no tests found)"

    return "\n".join(sorted(tests))


def build_argv(args_config: Dict[str, Any]) -> List[str]:
    """
    Build sys.argv list from args configuration.

    Args:
        args_config: Dictionary of argument name -> value

    Returns:
        List of command-line arguments
    """
    argv = []

    for key, value in args_config.items():
        # Convert underscores to dashes for CLI args
        arg_name = f"--{key.replace('_', '-')}"

        if isinstance(value, bool):
            # Boolean flags: only add if True
            if value:
                argv.append(arg_name)
        elif isinstance(value, list):
            # List values: add multiple times or as comma-separated
            for item in value:
                argv.extend([arg_name, str(item)])
        else:
            # Regular key-value pairs
            argv.extend([arg_name, str(value)])

    return argv


def run_test_module(module_path: Path, args: List[str]) -> int:
    """
    Dynamically load and run a test module.

    Args:
        module_path: Path to the Python module
        args: Command-line arguments to pass

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Load the module dynamically
    spec = importlib.util.spec_from_file_location("test_module", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module: {module_path}")

    module = importlib.util.module_from_spec(spec)

    # Set up sys.argv for the module's argparse
    original_argv = sys.argv
    sys.argv = [str(module_path)] + args

    try:
        # Execute the module
        spec.loader.exec_module(module)

        # Call main() if it exists
        if hasattr(module, 'main'):
            module.main()
            return 0
        else:
            print(f"Warning: Module {module_path} has no main() function")
            return 1

    except SystemExit as e:
        # Handle sys.exit() calls from the module
        return e.code if isinstance(e.code, int) else 0

    except Exception as e:
        print(f"Error running test module: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Restore original sys.argv
        sys.argv = original_argv


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(
        description="Run evaluation tests from input.json configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run.py input.json
    python run.py --input input.json
    python run.py --list

Input JSON format:
{
    "test": "categorization/evaluate_categorization",
    "args": {
        "dataset": "path/to/dataset.json",
        "output_dir": "path/to/output"
    }
}
        """
    )

    parser.add_argument(
        "input",
        nargs="?",
        type=str,
        help="Path to input.json configuration file"
    )
    parser.add_argument(
        "--input",
        dest="input_flag",
        type=str,
        help="Path to input.json configuration file (alternative to positional arg)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available tests and exit"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without running"
    )

    args = parser.parse_args()

    # Determine base path (directory containing this script)
    base_path = Path(__file__).parent

    # Handle --list flag
    if args.list:
        print("Available evaluation tests:")
        print(list_available_tests(base_path))
        return 0

    # Get input file path
    input_path = args.input or args.input_flag
    if not input_path:
        parser.error("Input file is required. Use 'python run.py input.json' or 'python run.py --input input.json'")

    try:
        # Load input configuration
        print(f"Loading configuration from: {input_path}")
        config = load_input_config(input_path)

        # Validate required fields
        if "test" not in config:
            raise ValueError("Input configuration must contain 'test' field")

        test_name = config["test"]
        test_args = config.get("args", {})

        # Resolve test module path
        module_path = resolve_test_module(test_name, base_path)
        print(f"Test module: {module_path}")

        # Build command-line arguments
        argv = build_argv(test_args)
        print(f"Arguments: {' '.join(argv)}")

        # Handle dry-run
        if args.dry_run:
            print("\n[Dry run] Would execute:")
            print(f"  python {module_path} {' '.join(argv)}")
            return 0

        # Run the test module
        print(f"\n{'='*80}")
        print(f"Running test: {test_name}")
        print(f"{'='*80}\n")

        exit_code = run_test_module(module_path, argv)

        print(f"\n{'='*80}")
        print(f"Test completed with exit code: {exit_code}")
        print(f"{'='*80}")

        return exit_code

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"Error parsing input JSON: {e}")
        return 1
    except ValueError as e:
        print(f"Configuration error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())