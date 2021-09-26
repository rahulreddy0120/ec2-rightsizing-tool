#!/usr/bin/env python3
"""
AWS EC2 Rightsizing Analyzer
Main orchestration logic for analyzing EC2 instances across multiple
AWS accounts and generating cost optimization recommendations.
"""

from typing import Optional
import yaml
import logging
from datetime import datetime
from aws_client import AWSClient
from metrics_collector import MetricsCollector
from cost_calculator import CostCalculator
from report_generator import ReportGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EC2RightsizingAnalyzer:
    """Orchestrates EC2 rightsizing analysis across AWS accounts.

    Collects CloudWatch metrics, compares against configurable thresholds,
    and produces actionable resize / terminate recommendations with
    projected cost savings.
    """

    def __init__(self, config_file: str = 'config/accounts.yaml') -> None:
        with open(config_file, 'r') as f:
            self.config: dict = yaml.safe_load(f)

        self.aws_client = AWSClient()
        self.metrics_collector = MetricsCollector(self.config)
        self.cost_calculator = CostCalculator()
        self.report_generator = ReportGenerator()

    def analyze_account(self, account: dict) -> list[dict]:
        """Analyze all EC2 instances in a single AWS account.

        Args:
            account: Account configuration dict containing account_id,
                     name, role_name, and regions list.

        Returns:
            List of recommendation dicts for instances that should be resized.
        """
        account_id: str = account['account_id']
        account_name: str = account['name']
        role_name: str = account['role_name']

        logger.info(f"Analyzing account: {account_name} ({account_id})")

        recommendations: list[dict] = []

        for region in account['regions']:
            logger.info(f"  Region: {region}")

            session = self.aws_client.assume_role(account_id, role_name, region)
            if not session:
                logger.error(f"  Failed to assume role in {account_id}")
                continue

            instances = self.aws_client.get_ec2_instances(session, region)
            logger.info(f"  Found {len(instances)} instances")

            for instance in instances:
                instance_id: str = instance['InstanceId']
                instance_type: str = instance['InstanceType']

                metrics = self.metrics_collector.collect_metrics(
                    session, region, instance_id, instance_type
                )

                if not metrics:
                    continue

                current_cost = self.cost_calculator.get_instance_cost(
                    instance_type, region
                )

                recommendation = self._generate_recommendation(
                    account_id, account_name, instance, metrics, current_cost, region
                )

                if recommendation:
                    recommendations.append(recommendation)

        return recommendations

    def _generate_recommendation(
        self,
        account_id: str,
        account_name: str,
        instance: dict,
        metrics: dict,
        current_cost: float,
        region: str,
    ) -> Optional[dict]:
        """Generate a rightsizing recommendation for a single instance.

        Returns:
            Recommendation dict or ``None`` when no action is needed.
        """
        instance_id: str = instance['InstanceId']
        instance_type: str = instance['InstanceType']

        avg_cpu: float = metrics['avg_cpu']
        avg_memory: float = metrics.get('avg_memory', 0)

        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        team: str = tags.get('Team', 'Unknown')
        environment: str = tags.get('Environment', 'Unknown')

        thresholds = self.config['settings']['thresholds']
        cpu_low: float = thresholds['cpu_low']
        cpu_high: float = thresholds['cpu_high']

        recommended_type: Optional[str] = None
        action = 'no_change'

        if avg_cpu < cpu_low and avg_memory < thresholds['memory_low']:
            recommended_type = self.cost_calculator.get_smaller_instance(instance_type)
            action = 'downsize'
        elif avg_cpu > cpu_high or avg_memory > thresholds['memory_high']:
            recommended_type = self.cost_calculator.get_larger_instance(instance_type)
            action = 'upsize'

        if not recommended_type or recommended_type == instance_type:
            return None

        new_cost: float = self.cost_calculator.get_instance_cost(recommended_type, region)
        monthly_savings: float = current_cost - new_cost

        if monthly_savings < self.config['settings']['min_savings_threshold']:
            return None

        annual_savings: float = monthly_savings * 12

        return {
            'account_id': account_id,
            'account_name': account_name,
            'instance_id': instance_id,
            'instance_type': instance_type,
            'region': region,
            'avg_cpu': round(avg_cpu, 2),
            'avg_memory': round(avg_memory, 2),
            'current_cost': round(current_cost, 2),
            'recommended_type': recommended_type,
            'new_cost': round(new_cost, 2),
            'monthly_savings': round(monthly_savings, 2),
            'annual_savings': round(annual_savings, 2),
            'action': action,
            'team': team,
            'environment': environment,
        }

    def run(self) -> list[dict]:
        """Execute the full analysis pipeline across all configured accounts.

        Returns:
            Aggregated list of recommendations from every account.
        """
        logger.info("=" * 70)
        logger.info("EC2 Rightsizing Analysis Started")
        logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
        logger.info("=" * 70)

        all_recommendations: list[dict] = []

        for account in self.config['accounts']:
            try:
                recommendations = self.analyze_account(account)
                all_recommendations.extend(recommendations)
            except Exception as e:
                logger.error(f"Error analyzing account {account['name']}: {e}")
                continue

        logger.info(f"\nTotal recommendations: {len(all_recommendations)}")

        if all_recommendations:
            csv_file = self.report_generator.generate_csv(all_recommendations)
            logger.info(f"CSV report: {csv_file}")

            summary = self.report_generator.generate_summary(all_recommendations)
            logger.info(f"\n{summary}")

            s3_path = self.report_generator.upload_to_s3(csv_file)
            logger.info(f"Uploaded to S3: {s3_path}")

        logger.info("=" * 70)
        logger.info("Analysis Complete")
        logger.info("=" * 70)

        return all_recommendations


if __name__ == '__main__':
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='EC2 Rightsizing Analyzer')
    parser.add_argument('--config', default='config/accounts.yaml', help='Config file')
    parser.add_argument('--dry-run', action='store_true', help='Print recommendations without uploading to S3')
    parser.add_argument('--output-format', choices=['csv', 'json', 'both'], default='csv',
                        help='Report output format (default: csv)')

    args = parser.parse_args()

    analyzer = EC2RightsizingAnalyzer(config_file=args.config)
    results = analyzer.run()

    if args.dry_run:
        logger.info("Dry-run mode — skipping S3 upload")
        sys.exit(0)
