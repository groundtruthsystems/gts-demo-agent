"""
Categorization agent evaluator.

Runs categorization agent against labeled dataset and evaluates performance.
"""

import asyncio
import sys
import json
import html as html_module
import argparse
import traceback
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

from deepeval.evaluate import AsyncConfig

from deepeval.test_case import LLMTestCase
from deepeval import evaluate

from demo.common.config import Config

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


class EchoEvaluator:
    """
    Evaluates categorization agent performance across multiple model configurations.
    """

    def __init__(self, evaluation_config: Dict[str, Any], config_template: Dict[str, Any], agent_configs: List[Any]):
        """
        Initialize evaluator with model configurations.

        Args:
            evaluation_config: Evaluation config with multiple model configurations
            config_template: Base application config template (services, gateways, etc.)
        """
        self.evaluation_config = evaluation_config
        self.config_template = config_template['parameters']
        self.agent_configs = agent_configs
        self.results = {}

        # Validate configs
        self._validate_template_config(self.config_template)
        for model_config in agent_configs:
            self._validate_model_config(model_config)

    def _validate_template_config(self, template_config: Dict[str, Any]) -> bool:
        """
        Validate template configuration structure.

        Args:
            template_config: Template config to validate

        Returns:
            True if valid

        Raises:
            ValueError: If validation fails
        """

        # TODO: Validate template config

        return True

    def _validate_model_config(self, model_config: Dict[str, Any]) -> bool:
        """
        Validate model configuration structure.

        Args:
            model_config: Model config to validate

        Returns:
            True if valid

        Raises:
            ValueError: If validation fails
        """

        # TODO: Validate model config

        return True

    def load_dataset(self, dataset_path: Path) -> List[Dict[str, Any]]:
        """
        Load labeled dataset from JSON, JSONL file, or directory of JSONL files.

        Supports three modes:
        - JSON file: A file containing a JSON array of test cases
        - JSONL file: A file where each line is a separate JSON object
        - Directory: Loads all .jsonl files in the directory and combines them

        Args:
            dataset_path: Path to labeled dataset (JSON, JSONL, or directory)

        Returns:
            List of labeled test cases
        """
        dataset_path = Path(dataset_path)

        if dataset_path.is_dir():
            # Directory mode: load all .jsonl files
            dataset = []
            jsonl_files = sorted(dataset_path.glob('*.jsonl'))

            if not jsonl_files:
                raise FileNotFoundError(f"No .jsonl files found in directory: {dataset_path}")

            for jsonl_file in jsonl_files:
                print(f"  Loading: {jsonl_file.name}")
                dataset.extend(self._load_jsonl_file(jsonl_file))

            return dataset

        with open(dataset_path, 'r') as f:
            if dataset_path.suffix.lower() == '.jsonl':
                # JSONL format: each line is a separate JSON object
                dataset = self._load_jsonl_file(dataset_path)
            else:
                # JSON format: file contains a JSON array
                dataset = json.load(f)

        return dataset

    def _load_jsonl_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Load a single JSONL file.

        Args:
            file_path: Path to JSONL file

        Returns:
            List of parsed JSON objects
        """
        dataset = []
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:  # Skip empty lines
                    try:
                        dataset.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        raise json.JSONDecodeError(
                            f"Invalid JSON on line {line_num} in {file_path}",
                            e.doc,
                            e.pos
                        )
        return dataset


    async def create_test_cases(self, dataset: List[Dict[str, Any]], config: Config) -> tuple[List[LLMTestCase], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Create DeepEval test cases from labeled dataset and collect cost data.

        Args:
            dataset: Labeled dataset
            config: Config object with LLM configuration

        Returns:
            Tuple of (LLMTestCase objects, call_summaries for each test, test_failures for each test)
        """
        test_cases = []
        all_call_summaries = []
        test_failures = []

        # TODO: Create your test cases

        return test_cases, all_call_summaries, test_failures

    def evaluate_model(
        self,
        model_config: Dict[str, Any],
        dataset_path: Path,
        strict_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Run evaluation for a specific model configuration.

        Args:
            model_config: Model-specific configuration
            dataset_path: Path to labeled dataset JSON
            strict_mode: If True, require exact matches for categories/locations

        Returns:
            Evaluation results for this model
        """
        model_name = model_config['name']
        print(f"\n{'='*80}")
        print(f"Evaluating model: {model_name}")
        print(f"{'='*80}")

        # Start timing
        import time
        start_time = time.time()

        print("Create config...")
        # TODO: Create config data
        config: Config = Config(config_data={})

        # Load dataset
        print("Loading dataset...")
        dataset = self.load_dataset(dataset_path)
        print(f"Loaded {len(dataset)} test cases")

        # Run categorization and create test cases
        print("\nRunning categorization agent...")
        test_cases, all_call_summaries, test_failures = asyncio.run(self.create_test_cases(dataset, config))
        print(f"Created {len(test_cases)} test cases")

        # Report individual test failures
        failed_count = sum(1 for f in test_failures if f is not None)
        if failed_count > 0:
            print(f"\n[WARNING] {failed_count} test(s) failed during agent execution (will be marked as failed in evaluation)")

        # Evaluate
        print("\nEvaluating results...")
        metrics = [
        #    TODO: Add metrics
        ]

        results = evaluate(
            test_cases=test_cases,
            metrics=metrics,
            async_config=AsyncConfig(run_async=False),
        )

        # Calculate duration
        end_time = time.time()
        duration_seconds = end_time - start_time

        print(f"\nEvaluation completed in {duration_seconds:.2f} seconds ({duration_seconds/60:.2f} minutes)")

        return {
            'model_name': model_name,
            'test_cases': test_cases,
            'test_failures': test_failures,  # Individual test execution failures (with stacktraces)
            'results': results,
            'duration_seconds': duration_seconds,
            'start_time': datetime.fromtimestamp(start_time).isoformat(),
            'end_time': datetime.fromtimestamp(end_time).isoformat()
        }

    def evaluate_all_models(
        self,
        dataset_path: Path,
        output_dir: Path,
        strict_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Run evaluation for all models in the evaluation config.

        Args:
            dataset_path: Path to labeled dataset JSON
            output_dir: Directory to save evaluation reports
            strict_mode: If True, require exact matches for categories/locations

        Returns:
            Dictionary of results per model
        """
        models = self.agent_configs

        if not models:
            raise ValueError("No models found in evaluation config")

        # Generate timestamp for this evaluation run
        run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"\nEvaluating {len(models)} model configurations...")
        print(f"Run timestamp: {run_timestamp}")

        failed_models = []

        for model_config in models:
            model_name = model_config.get('name', 'unknown')

            try:
                # Run evaluation for this model
                model_result = self.evaluate_model(model_config, dataset_path, strict_mode)

                # Store results
                model_name = model_result['model_name']
                self.results[model_name] = model_result

                # Generate and save report for this model with timestamp
                output_path = output_dir / f"{run_timestamp}_{model_name}_echo_evaluation.json"
                self.generate_report(
                    model_result['results'],
                    output_path,
                    model_name,
                    model_result['test_cases'],
                    model_result.get('duration_seconds'),
                    model_result.get('start_time'),
                    model_result.get('end_time')
                )

                print(f"\n✓ Successfully evaluated model: {model_name}")

            except Exception as e:
                # Capture full stacktrace
                error_trace = traceback.format_exc()

                # Log failure
                print(f"\n✗ Failed to evaluate model: {model_name}")
                print(f"Error: {str(e)}")
                print(f"Stacktrace:\n{error_trace}")

                # Store failure information
                failed_models.append({
                    'model_name': model_name,
                    'error': str(e),
                    'stacktrace': error_trace,
                    'timestamp': datetime.now().isoformat()
                })

                # Store failed result in results dict for reporting
                self.results[model_name] = {
                    'model_name': model_name,
                    'status': 'failed',
                    'error': str(e),
                    'stacktrace': error_trace,
                    'timestamp': datetime.now().isoformat()
                }

                # Continue with next model
                continue

        # Report summary of failures
        if failed_models:
            print(f"\n{'='*80}")
            print(f"EVALUATION FAILURES: {len(failed_models)} model(s) failed")
            print(f"{'='*80}")
            for failure in failed_models:
                print(f"  - {failure['model_name']}: {failure['error']}")

            # Save failure report
            failure_report_path = output_dir / "failed_models.json"
            failure_report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(failure_report_path, 'w') as f:
                json.dump(failed_models, f, indent=2)
            print(f"\nFailure details saved to: {failure_report_path}")

        # Generate comparison report only if we have successful results
        successful_results = {
            k: v for k, v in self.results.items()
            if v.get('status') != 'failed'
        }

        if successful_results:
            comparison_path = output_dir / f"model_comparison_{run_timestamp}.json"
            comparison = self.generate_comparison_report(comparison_path)

            # Generate HTML visualization with timestamp
            html_path = output_dir / f"model_comparison_{run_timestamp}.html"
            self.generate_html_visualization(html_path, comparison)

            # Generate combined results file for reporting systems
            combined_path = output_dir / f"{run_timestamp}-result.json"
            self.generate_combined_results(combined_path, comparison, run_timestamp)
        else:
            print("\nNo successful model evaluations to compare.")

        return self.results

    def generate_report(
        self,
        results,
        output_path: Path,
        model_name: str,
        test_cases: List[LLMTestCase],
        duration_seconds: float = None,
        start_time: str = None,
        end_time: str = None
    ):
        """
        Generate evaluation report for a specific model.

        Args:
            results: Evaluation results
            output_path: Path to save report
            model_name: Name of the model being evaluated
            test_cases: List of test cases
            duration_seconds: Time taken for evaluation in seconds
            start_time: Start time ISO format
            end_time: End time ISO format
        """
        report = {
            "model_name": model_name,
            "timestamp": datetime.now().isoformat(),
            "test_cases": len(test_cases),
            "summary": {
                "total_tests": len(test_cases),
                "passed": sum(1 for tc in results.test_results if all(m.success for m in tc.metrics_data)),
                "failed": sum(1 for tc in results.test_results if any(not m.success for m in tc.metrics_data))
            },
            "metrics": {},
            "detailed_results": []
        }

        # Add timing information if provided
        if duration_seconds is not None:
            report["performance"] = {
                "duration_seconds": duration_seconds,
                "duration_minutes": duration_seconds / 60,
                "start_time": start_time,
                "end_time": end_time
            }

        # Aggregate metrics
        for metric_name in ["Accuracy"]:
            scores = []
            successes = []

            for tc in results.test_results:
                for metric in tc.metrics_data:
                    if metric.name == metric_name:
                        scores.append(metric.score)
                        successes.append(metric.success)

            if scores:
                report["metrics"][metric_name] = {
                    "mean_score": sum(scores) / len(scores),
                    "min_score": min(scores),
                    "max_score": max(scores),
                    "success_rate": sum(successes) / len(successes)
                }

        # Detailed results
        for idx, tc in enumerate(results.test_results):
            test_result = {
                "input": tc.input,
                "actual_output": json.loads(tc.actual_output),
                "expected_output": json.loads(tc.expected_output),
                "metrics": {}
            }

            for metric in tc.metrics_data:
                test_result["metrics"][metric.name] = {
                    "score": metric.score,
                    "success": metric.success,
                    "reason": metric.reason
                }

            report["detailed_results"].append(test_result)

        # Save report
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\nReport saved to: {output_path}")
        return report

    def generate_comparison_report(self, output_path: Path):
        """
        Generate comparison report across all evaluated models.

        Args:
            output_path: Path to save comparison report
        """
        if not self.results:
            print("No results to compare")
            return

        # Filter out failed models for comparison
        successful_results = {
            k: v for k, v in self.results.items()
            if v.get('status') != 'failed'
        }

        if not successful_results:
            print("No successful results to compare")
            return

        comparison = {
            "timestamp": datetime.now().isoformat(),
            "models_evaluated": len(successful_results),
            "total_models_attempted": len(self.results),
            "failed_models_count": len(self.results) - len(successful_results),
            "model_summaries": {},
            "metric_comparison": {},
            "rankings": {}
        }

        # Collect metrics from all successful models
        all_metrics = {}
        for model_name, model_result in successful_results.items():
            results = model_result['results']
            test_cases = model_result['test_cases']

            # Calculate summary for this model
            comparison["model_summaries"][model_name] = {
                "total_tests": len(test_cases),
                "passed": sum(1 for tc in results.test_results if all(m.success for m in tc.metrics_data)),
                "failed": sum(1 for tc in results.test_results if any(not m.success for m in tc.metrics_data)),
                "success_rate": sum(1 for tc in results.test_results if all(m.success for m in tc.metrics_data)) / len(test_cases),
                "duration_seconds": model_result.get('duration_seconds', 0),
                "duration_minutes": model_result.get('duration_seconds', 0) / 60
            }

            # Collect metrics
            for metric_name in ["Accuracy"]:
                if metric_name not in all_metrics:
                    all_metrics[metric_name] = {}

                scores = []
                for tc in results.test_results:
                    for metric in tc.metrics_data:
                        if metric.name == metric_name:
                            scores.append(metric.score)

                if scores:
                    all_metrics[metric_name][model_name] = {
                        "mean_score": sum(scores) / len(scores),
                        "min_score": min(scores),
                        "max_score": max(scores)
                    }

        # Create metric comparison
        comparison["metric_comparison"] = all_metrics

        # Create rankings based on mean scores
        for metric_name, model_scores in all_metrics.items():
            ranked = sorted(
                model_scores.items(),
                key=lambda x: x[1]["mean_score"],
                reverse=True
            )
            comparison["rankings"][metric_name] = [
                {"rank": idx + 1, "model": model, "mean_score": scores["mean_score"]}
                for idx, (model, scores) in enumerate(ranked)
            ]

        # Overall ranking based on success rate
        overall_ranked = sorted(
            comparison["model_summaries"].items(),
            key=lambda x: x[1]["success_rate"],
            reverse=True
        )
        comparison["rankings"]["overall"] = [
            {"rank": idx + 1, "model": model, "success_rate": summary["success_rate"]}
            for idx, (model, summary) in enumerate(overall_ranked)
        ]

        # Save comparison report
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(comparison, f, indent=2)

        print(f"\nComparison report saved to: {output_path}")

        # Print comparison summary
        print("\n" + "="*80)
        print("MODEL COMPARISON SUMMARY")
        print("="*80)
        print("\nOverall Rankings:")
        for rank_info in comparison["rankings"]["overall"]:
            print(f"  {rank_info['rank']}. {rank_info['model']}: {rank_info['success_rate']:.1%}")

        return comparison

    def generate_combined_results(
        self,
        output_path: Path,
        comparison: Dict[str, Any],
        run_timestamp: str
    ) -> Dict[str, Any]:
        """
        Generate a combined results file containing all model evaluations for reporting systems.

        This method combines all individual model evaluation results into a single JSON file
        with a standardized format suitable for publishing to reporting systems.

        Args:
            output_path: Path to save the combined results file
            comparison: Comparison data from generate_comparison_report
            run_timestamp: Timestamp string for the evaluation run

        Returns:
            Combined results dictionary
        """
        # Build combined results structure
        combined = {
            "$schema": "./echo_evaluation_result.schema.json",
            "metadata": {
                "run_id": run_timestamp,
                "timestamp": datetime.now().isoformat(),
                "evaluation_type": "echo",
                "total_models_attempted": len(self.results),
                "total_models_succeeded": comparison.get('models_evaluated', 0),
                "total_models_failed": comparison.get('failed_models_count', 0)
            },
            "summary": comparison.get('model_summaries', {}),
            "rankings": comparison.get('rankings', {}),
            "metric_comparison": comparison.get('metric_comparison', {}),
            "model_results": []
        }

        # Add individual model results
        for model_name, model_result in self.results.items():
            if model_result.get('status') == 'failed':
                # Add failed model entry
                combined["model_results"].append({
                    "model_name": model_name,
                    "status": "failed",
                    "error": model_result.get('error'),
                    "stacktrace": model_result.get('stacktrace'),
                    "timestamp": model_result.get('timestamp')
                })
            else:
                # Build successful model result
                results = model_result['results']
                test_cases = model_result['test_cases']
                test_costs = model_result.get('test_costs', [])
                cost_stats = model_result.get('cost_stats', {})

                # Calculate summary metrics
                model_entry = {
                    "model_name": model_name,
                    "status": "success",
                    "timestamp": model_result.get('start_time'),
                    "test_cases_count": len(test_cases),
                    "summary": {
                        "total_tests": len(test_cases),
                        "passed": sum(1 for tc in results.test_results if all(m.success for m in tc.metrics_data)),
                        "failed": sum(1 for tc in results.test_results if any(not m.success for m in tc.metrics_data))
                    },
                    "metrics": {},
                    "performance": {
                        "duration_seconds": model_result.get('duration_seconds', 0),
                        "duration_minutes": model_result.get('duration_seconds', 0) / 60,
                        "start_time": model_result.get('start_time'),
                        "end_time": model_result.get('end_time')
                    },
                    "cost": cost_stats,
                    "detailed_results": []
                }

                # Aggregate metrics
                for metric_name in ["Accuracy"]:
                    scores = []
                    successes = []

                    for tc in results.test_results:
                        for metric in tc.metrics_data:
                            if metric.name == metric_name:
                                scores.append(metric.score)
                                successes.append(metric.success)

                    if scores:
                        model_entry["metrics"][metric_name] = {
                            "mean_score": sum(scores) / len(scores),
                            "min_score": min(scores),
                            "max_score": max(scores),
                            "success_rate": sum(successes) / len(successes)
                        }

                # Add detailed test results
                for idx, tc in enumerate(results.test_results):
                    test_result = {
                        "input": tc.input,
                        "actual_output": json.loads(tc.actual_output),
                        "expected_output": json.loads(tc.expected_output),
                        "metrics": {}
                    }

                    for metric in tc.metrics_data:
                        test_result["metrics"][metric.name] = {
                            "score": metric.score,
                            "success": metric.success,
                            "reason": metric.reason
                        }

                    model_entry["detailed_results"].append(test_result)

                combined["model_results"].append(model_entry)

        # Save combined results
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(combined, f, indent=2)

        print(f"\nCombined results saved to: {output_path}")

        return combined

    def generate_html_visualization(self, output_path: Path, comparison: Dict[str, Any]):
        """
        Generate interactive HTML visualization of evaluation results.

        Args:
            output_path: Path to save HTML report
            comparison: Comparison data from generate_comparison_report
        """
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Categorization Agent Evaluation Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
            border-bottom: 2px solid #ddd;
            padding-bottom: 8px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .metric-box {{
            display: inline-block;
            margin: 10px;
            padding: 20px;
            background-color: #f9f9f9;
            border-left: 4px solid #4CAF50;
            border-radius: 4px;
        }}
        .metric-label {{
            font-size: 14px;
            color: #666;
        }}
        .metric-value {{
            font-size: 28px;
            font-weight: bold;
            color: #333;
        }}
        .success {{
            color: #4CAF50;
        }}
        .warning {{
            color: #ff9800;
        }}
        .error {{
            color: #f44336;
        }}
        .timestamp {{
            color: #999;
            font-size: 12px;
        }}
        .failed-section {{
            background-color: #fff3cd;
            border-left: 4px solid #f44336;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .failed-section h3 {{
            color: #f44336;
            margin-top: 0;
        }}
        .failed-model {{
            background-color: white;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
            border: 1px solid #f44336;
        }}
        .failed-model-name {{
            font-weight: bold;
            color: #f44336;
        }}
        .error-details {{
            font-family: monospace;
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }}
        .stacktrace {{
            background-color: #f9f9f9;
            padding: 10px;
            margin-top: 10px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 11px;
            overflow-x: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-height: 200px;
            overflow-y: auto;
        }}
        .filter-btn {{
            background-color: #e0e0e0;
            border: none;
            padding: 10px 20px;
            margin: 5px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: background-color 0.3s;
        }}
        .filter-btn:hover {{
            background-color: #d0d0d0;
        }}
        .filter-btn.active {{
            background-color: #4CAF50;
            color: white;
        }}
        .test-case {{
            background-color: #f9f9f9;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 15px;
            margin: 15px 0;
        }}
        .test-case.test-passed {{
            border-left: 4px solid #4CAF50;
        }}
        .test-case.test-failed {{
            border-left: 4px solid #f44336;
        }}
        .test-header {{
            padding-bottom: 10px;
            border-bottom: 1px solid #ddd;
            margin-bottom: 10px;
        }}
        .test-content {{
            padding-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Categorization Agent Evaluation Report</h1>
        <p class="timestamp">Generated: {comparison['timestamp']}</p>


        <div class="metric-box">
            <div class="metric-label">Models Evaluated</div>
            <div class="metric-value">{comparison['models_evaluated']}</div>
        </div>
"""

        # Add summary metrics
        if comparison['model_summaries']:
            first_model = list(comparison['model_summaries'].values())[0]
            html_content += f"""
        <div class="metric-box">
            <div class="metric-label">Total Test Cases</div>
            <div class="metric-value">{first_model['total_tests']}</div>
        </div>
"""

        if comparison['rankings'].get('overall'):
            best_model = comparison['rankings']['overall'][0]
            html_content += f"""
        <div class="metric-box">
            <div class="metric-label">Best Model</div>
            <div class="metric-value" style="font-size: 20px;">{best_model['model']}</div>
        </div>
"""

        # Add failed models section if there are any
        if comparison.get('failed_models_count', 0) > 0:
            html_content += f"""
        <div class="failed-section">
            <h3>⚠ Failed Models ({comparison['failed_models_count']})</h3>
            <p>The following models failed during evaluation:</p>
"""
            # Get failed models from self.results
            failed_models = [
                {'model_name': k, **v}
                for k, v in self.results.items()
                if v.get('status') == 'failed'
            ]

            for failed in failed_models:
                html_content += f"""
            <div class="failed-model">
                <div class="failed-model-name">{failed['model_name']}</div>
                <div class="error-details">
                    <strong>Error:</strong> {failed.get('error', 'Unknown error')}
                </div>
                <div class="error-details">
                    <strong>Time:</strong> {failed.get('timestamp', 'N/A')}
                </div>
                <details>
                    <summary style="cursor: pointer; color: #666; margin-top: 5px;">View Stacktrace</summary>
                    <div class="stacktrace">{failed.get('stacktrace', 'No stacktrace available')}</div>
                </details>
            </div>
"""

            html_content += """
        </div>
"""

        html_content += """
        <h2>Model Comparison</h2>
        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Model</th>
                    <th>Success Rate</th>
                    <th>Category Accuracy</th>
                    <th>Location Accuracy</th>
                    <th>Duration (min)</th>
                    <th>Cost ($)</th>
                    <th>Input Tokens</th>
                    <th>Output Tokens</th>
                    <th>Passed</th>
                    <th>Failed</th>
                </tr>
            </thead>
            <tbody>
"""

        # Add table rows
        metric_names = ["Accuracy"]
        for rank_info in comparison['rankings']['overall']:
            model_name = rank_info['model']
            model_summary = comparison['model_summaries'][model_name]

            # Get metric scores
            cat_accuracy = comparison['metric_comparison'].get('Category Accuracy', {}).get(model_name, {}).get('mean_score', 0)
            loc_accuracy = comparison['metric_comparison'].get('Location Accuracy', {}).get(model_name, {}).get('mean_score', 0)
            duration_minutes = model_summary.get('duration_minutes', 0)
            total_cost = model_summary.get('total_cost', 0)
            total_input_tokens = model_summary.get('total_input_tokens', 0)
            total_output_tokens = model_summary.get('total_output_tokens', 0)

            # Determine CSS class for success rate
            success_class = 'success' if rank_info['success_rate'] >= 0.9 else ('warning' if rank_info['success_rate'] >= 0.7 else 'error')

            html_content += f"""
                <tr>
                    <td>{rank_info['rank']}</td>
                    <td><strong>{model_name}</strong></td>
                    <td class="{success_class}">{rank_info['success_rate']:.1%}</td>
                    <td>{cat_accuracy:.3f}</td>
                    <td>{loc_accuracy:.3f}</td>
                    <td>{duration_minutes:.2f}</td>
                    <td>${total_cost:.4f}</td>
                    <td>{total_input_tokens:,}</td>
                    <td>{total_output_tokens:,}</td>
                    <td>{model_summary['passed']}</td>
                    <td>{model_summary['failed']}</td>
                </tr>
"""

        html_content += """
            </tbody>
        </table>

        <h2>Detailed Metrics</h2>
        <table>
            <thead>
                <tr>
                    <th>Model</th>
                    <th>Category Accuracy</th>
                    <th>Location Accuracy</th>
                    <th>Confidence Calibration</th>
                    <th>Manual Review Precision</th>
                </tr>
            </thead>
            <tbody>
"""

        # Add detailed metrics for each model
        for model_name in comparison['model_summaries'].keys():
            html_content += f"""
                <tr>
                    <td><strong>{model_name}</strong></td>
"""
            for metric_name in metric_names:
                if metric_name in comparison['metric_comparison'] and model_name in comparison['metric_comparison'][metric_name]:
                    mean_score = comparison['metric_comparison'][metric_name][model_name]['mean_score']
                    score_class = 'success' if mean_score >= 0.9 else ('warning' if mean_score >= 0.7 else 'error')
                    html_content += f"""
                    <td class="{score_class}">{mean_score:.3f}</td>
"""
                else:
                    html_content += """
                    <td>-</td>
"""
            html_content += """
                </tr>
"""

        html_content += """
            </tbody>
        </table>

        <h2>Detailed Test Results by Model</h2>
        <p>Click on a model to view its individual test cases and results.</p>
"""

        # Add detailed test results for each model
        for model_name in comparison['model_summaries'].keys():
            model_summary = comparison['model_summaries'][model_name]
            model_result = self.results[model_name]

            # Get test results, costs, token stats, and failures
            test_results = []
            test_costs = model_result.get('test_costs', [])
            test_token_stats = model_result.get('test_token_stats', [])
            test_failures = model_result.get('test_failures', [])

            for idx, tc in enumerate(model_result['results'].test_results):
                # Determine if test passed (all metrics successful)
                passed = all(m.success for m in tc.metrics_data)

                # Parse input/output
                actual = json.loads(tc.actual_output)
                expected = json.loads(tc.expected_output)

                # Collect metrics
                metrics = {}
                for metric in tc.metrics_data:
                    metrics[metric.name] = {
                        'score': metric.score,
                        'success': metric.success,
                        'reason': metric.reason
                    }

                # Get cost for this test if available
                cost_data = None
                if test_costs and idx < len(test_costs):
                    total_cost, cost_breakdown = test_costs[idx]
                    cost_data = {
                        'total_cost': total_cost,
                        'cost_breakdown': cost_breakdown
                    }

                # Get token stats for this test if available
                token_stats = None
                if test_token_stats and idx < len(test_token_stats):
                    token_stats = test_token_stats[idx]

                test_results.append({
                    'input': tc.input,
                    'passed': passed,
                    'actual': actual,
                    'expected': expected,
                    'metrics': metrics,
                    'cost': cost_data,
                    'token_stats': token_stats
                })

            html_content += f"""
        <div class="model-section">
            <h3 class="model-header" onclick="toggleModel('{model_name}')" style="cursor: pointer; background-color: #f0f0f0; padding: 15px; border-radius: 4px; margin-top: 20px;">
                ▶ {model_name} ({model_summary['passed']} passed, {model_summary['failed']} failed)
            </h3>
            <div id="model-{model_name}" class="model-details" style="display: none;">
                <div class="filter-buttons" style="margin: 15px 0;">
                    <button onclick="filterTests('{model_name}', 'all')" class="filter-btn active" id="{model_name}-btn-all">All ({model_summary['total_tests']})</button>
                    <button onclick="filterTests('{model_name}', 'passed')" class="filter-btn" id="{model_name}-btn-passed">Passed ({model_summary['passed']})</button>
                    <button onclick="filterTests('{model_name}', 'failed')" class="filter-btn" id="{model_name}-btn-failed">Failed ({model_summary['failed']})</button>
                </div>
                <div id="tests-{model_name}">
"""

            # Add each test case
            for idx, test in enumerate(test_results):
                status_class = 'test-passed' if test['passed'] else 'test-failed'
                status_text = '✓ PASSED' if test['passed'] else '✗ FAILED'
                status_color = '#4CAF50' if test['passed'] else '#f44336'

                html_content += f"""
                    <div class="test-case {status_class}" data-status="{'passed' if test['passed'] else 'failed'}">
                        <div class="test-header">
                            <span style="color: {status_color}; font-weight: bold;">{status_text}</span>
                            <span style="float: right; color: #666;">Test #{idx + 1}</span>
                        </div>
                        <div class="test-content">
                            <div class="test-input">
                                <strong>Request:</strong>
                                <div style="background-color: #f9f9f9; padding: 10px; margin-top: 5px; border-radius: 4px;">
                                    {test['input']}
                                </div>
                            </div>
                            <div class="test-results" style="margin-top: 15px;">
                                <table style="width: 100%; font-size: 14px;">
                                    <tr>
                                        <th style="background-color: #e0e0e0; color: #333;">Aspect</th>
                                        <th style="background-color: #e0e0e0; color: #333;">Expected</th>
                                        <th style="background-color: #e0e0e0; color: #333;">Actual</th>
                                    </tr>
                                    <tr>
                                        <td><strong>Categories</strong></td>
                                        <td>{', '.join(test['expected'].get('expected_categories', []))}</td>
                                        <td>{', '.join(test['actual'].get('categories', []))}</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Locations</strong></td>
                                        <td>{', '.join(test['expected'].get('expected_anatomical_locations', []))}</td>
                                        <td>{', '.join(test['actual'].get('anatomical_locations', []))}</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Confidence</strong></td>
                                        <td>{test['expected'].get('expected_confidence_range', 'N/A') if isinstance(test['expected'].get('expected_confidence_range'), str) else f"{test['expected'].get('expected_confidence_range', ['N/A'])[0]:.2f}-{test['expected'].get('expected_confidence_range', ['N/A', 'N/A'])[1]:.2f}" if test['expected'].get('expected_confidence_range') else 'N/A'}</td>
                                        <td>{test['actual'].get('confidence', 'N/A')}</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Manual Review</strong></td>
                                        <td>{'Yes' if test['expected'].get('expected_requires_manual_review') else 'No'}</td>
                                        <td>{'Yes' if test['actual'].get('requires_manual_review') else 'No'}</td>
                                    </tr>
"""

                # Add cost row if available
                if test.get('cost'):
                    html_content += f"""
                                    <tr>
                                        <td><strong>Cost</strong></td>
                                        <td colspan="2">${test['cost']['total_cost']:.6f}</td>
                                    </tr>
"""

                html_content += """
                                </table>
                            </div>
                            <div class="metrics-section" style="margin-top: 15px;">
                                <strong>Metrics:</strong>
                                <table style="width: 100%; font-size: 13px; margin-top: 5px;">
                                    <tr>
                                        <th style="background-color: #e0e0e0; color: #333;">Metric</th>
                                        <th style="background-color: #e0e0e0; color: #333;">Score</th>
                                        <th style="background-color: #e0e0e0; color: #333;">Status</th>
                                        <th style="background-color: #e0e0e0; color: #333;">Reason</th>
                                    </tr>
"""

                for metric_name, metric_data in test['metrics'].items():
                    metric_status_color = '#4CAF50' if metric_data['success'] else '#f44336'
                    metric_status_text = '✓' if metric_data['success'] else '✗'

                    html_content += f"""
                                    <tr>
                                        <td>{metric_name}</td>
                                        <td>{metric_data['score']:.3f}</td>
                                        <td style="color: {metric_status_color}; font-weight: bold;">{metric_status_text}</td>
                                        <td style="font-size: 12px;">{metric_data['reason']}</td>
                                    </tr>
"""

                html_content += """
                                </table>
                            </div>
"""

                # Add token usage and reflection turns if available
                if test.get('token_stats'):
                    tokens = test['token_stats']
                    html_content += f"""
                            <div class="token-section" style="margin-top: 15px;">
                                <strong>Token Usage & Reflection:</strong>
                                <div style="background-color: #f9f9f9; padding: 10px; margin-top: 5px; border-radius: 4px; font-size: 12px;">
                                    <div style="margin: 5px 0;"><strong>Input Tokens:</strong> {tokens.get('input_tokens', 0):,}</div>
                                    <div style="margin: 5px 0;"><strong>Output Tokens:</strong> {tokens.get('output_tokens', 0):,}</div>
                                    <div style="margin: 5px 0;"><strong>Cached Input Tokens:</strong> {tokens.get('cached_input_tokens', 0):,}</div>
                                    <div style="margin: 5px 0;"><strong>Cached Read Input Tokens:</strong> {tokens.get('cached_read_input_tokens', 0):,}</div>
                                    <div style="margin: 5px 0;"><strong>Total Tokens:</strong> {tokens.get('total_tokens', 0):,}</div>
                                    <div style="margin: 5px 0; padding-top: 5px; border-top: 1px solid #ddd;"><strong>Reflection Turns:</strong> {tokens.get('reflection_turns', 0)}</div>
                                </div>
                            </div>
"""

                # Show execution failure with stacktrace if this test had an agent execution error
                test_failure = test_failures[idx] if test_failures and idx < len(test_failures) else None
                if test_failure is not None:
                    escaped_error = html_module.escape(str(test_failure.get('error', 'Unknown error')))
                    escaped_stacktrace = html_module.escape(str(test_failure.get('stacktrace', 'No stacktrace available')))
                    html_content += f"""
                            <div class="failed-section" style="margin-top: 15px;">
                                <h4 style="color: #f44336; margin-top: 0;">Agent Execution Failed</h4>
                                <div class="error-details">
                                    <strong>Error:</strong> {escaped_error}
                                </div>
                                <div class="error-details">
                                    <strong>Timestamp:</strong> {test_failure.get('timestamp', 'N/A')}
                                </div>
                                <details>
                                    <summary style="cursor: pointer; color: #666; margin-top: 10px; font-weight: bold;">View Stacktrace</summary>
                                    <div class="stacktrace">{escaped_stacktrace}</div>
                                </details>
                            </div>
"""

                html_content += """
                        </div>
                    </div>
"""

            html_content += """
                </div>
            </div>
        </div>
"""

        html_content += """
    </div>

    <script>
        function toggleModel(modelName) {
            const element = document.getElementById('model-' + modelName);
            const header = element.previousElementSibling;

            if (element.style.display === 'none') {
                element.style.display = 'block';
                header.innerHTML = header.innerHTML.replace('▶', '▼');
            } else {
                element.style.display = 'none';
                header.innerHTML = header.innerHTML.replace('▼', '▶');
            }
        }

        function filterTests(modelName, filter) {
            const testsContainer = document.getElementById('tests-' + modelName);
            const testCases = testsContainer.getElementsByClassName('test-case');

            // Update button states
            ['all', 'passed', 'failed'].forEach(f => {
                const btn = document.getElementById(modelName + '-btn-' + f);
                if (f === filter) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });

            // Filter test cases
            for (let testCase of testCases) {
                if (filter === 'all') {
                    testCase.style.display = 'block';
                } else {
                    if (testCase.dataset.status === filter) {
                        testCase.style.display = 'block';
                    } else {
                        testCase.style.display = 'none';
                    }
                }
            }
        }
    </script>
</body>
</html>
"""

        # Save HTML file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(html_content)

        print(f"\nHTML visualization saved to: {output_path}")
        return html_content


def load_evaluation_config(config_file: str) -> Dict[str, Any]:
    """
    Load evaluation configuration from JSON file.

    Args:
        config_file: Path to evaluation config JSON

    Returns:
        Parsed configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        return config_data
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in configuration file: {config_file}", e.doc, e.pos)



def load_evaluation_list_config(config_file: str) -> List[Any]:
    """
    Load evaluation configuration from JSON file.

    Args:
        config_file: Path to evaluation config JSON

    Returns:
        Parsed configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        return config_data
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in configuration file: {config_file}", e.doc, e.pos)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Evaluate categorization agent across multiple models"
    )
    parser.add_argument(
        "--evaluation-config",
        type=str,
        default="configs/evaluation/categorization/evaluation_config.json",
        help="Path to evaluation config file with model configurations"
    )
    parser.add_argument(
        "--agent-configs",
        type=str,
        default="configs/evaluation/categorization/agent_configs.json",
        help="Path to evaluation config file with agent configurations"
    )
    parser.add_argument(
        "--template-config",
        type=str,
        default="configs/evaluation/categorization/template_config.json",
        help="Path to template config file (base configuration)"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/evaluation/echo/dataset/sample.json",
        help="Path to labeled dataset"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/evaluation/echo/results",
        help="Output directory for results (will create per-model files)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Use strict mode (require exact matches)"
    )

    args = parser.parse_args()

    # Load configurations
    print("Loading configurations...")
    evaluation_config = load_evaluation_config(args.evaluation_config)
    template_config = load_evaluation_config(args.template_config)
    agent_configs = load_evaluation_list_config(args.agent_configs)

    # Create evaluator
    evaluator = EchoEvaluator(
        evaluation_config=evaluation_config,
        config_template=template_config,
        agent_configs=agent_configs,
    )

    # Run evaluation for all models
    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir)

    print(f"\nDataset: {dataset_path}")
    print(f"Output directory: {output_dir}")

    evaluator.evaluate_all_models(
        dataset_path=dataset_path,
        output_dir=output_dir,
        strict_mode=args.strict
    )

    print("\n" + "="*80)
    print("EVALUATION COMPLETE")
    print("="*80)
    print(f"\nResults saved to: {output_dir}")
    print(f"Models evaluated: {len(evaluator.results)}")
    print(f"\nOutput files:")
    print(f"  - Individual model results: {output_dir}/<timestamp>_<model>_echo_evaluation.json")
    print(f"  - Combined results (for reporting): {output_dir}/<timestamp>-result.json")
    print(f"  - Model comparison: {output_dir}/model_comparison_<timestamp>.json")
    print(f"  - Interactive HTML report: {output_dir}/model_comparison_<timestamp>.html")
    print(f"\nJSON Schema for combined results: {output_dir}/echo_evaluation_result.schema.json")


if __name__ == "__main__":
    main()
