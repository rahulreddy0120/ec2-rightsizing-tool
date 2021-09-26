#!/usr/bin/env python3
"""
Report generator - CSV, JSON, and summary reports.
"""

import csv
import json
import os
from typing import Optional

import boto3
import logging
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates CSV / JSON reports and uploads them to S3."""

    def __init__(self) -> None:
        self.s3_client = boto3.client('s3')
        self.bucket_name = 'ec2-rightsizing-reports'

    def generate_csv(self, recommendations: list[dict], output_dir: str = 'reports') -> str:
        """Write recommendations to a timestamped CSV file."""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(output_dir, f'ec2_rightsizing_{timestamp}.csv')

        fieldnames = [
            'account_id', 'account_name', 'instance_id', 'instance_type', 'region',
            'avg_cpu', 'avg_memory', 'current_cost', 'recommended_type', 'new_cost',
            'monthly_savings', 'annual_savings', 'action', 'team', 'environment',
        ]

        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(recommendations)

        logger.info(f"CSV report written to {filename}")
        return filename

    def generate_json(self, recommendations: list[dict], output_dir: str = 'reports') -> str:
        """Write recommendations to a timestamped JSON file for programmatic consumption."""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(output_dir, f'ec2_rightsizing_{timestamp}.json')

        payload = {
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'total_recommendations': len(recommendations),
            'recommendations': recommendations,
        }

        with open(filename, 'w') as f:
            json.dump(payload, f, indent=2, default=str)

        logger.info(f"JSON report written to {filename}")
        return filename

    def generate_summary(self, recommendations: list[dict]) -> str:
        """Return a human-readable text summary."""
        total_instances = len(recommendations)

        actions: dict[str, int] = defaultdict(int)
        for rec in recommendations:
            actions[rec['action']] += 1

        total_monthly = sum(rec['monthly_savings'] for rec in recommendations)
        total_annual = sum(rec['annual_savings'] for rec in recommendations)

        by_account: dict[str, dict] = defaultdict(lambda: {'count': 0, 'savings': 0.0})
        for rec in recommendations:
            by_account[rec['account_name']]['count'] += 1
            by_account[rec['account_name']]['savings'] += rec['monthly_savings']

        top_accounts = sorted(by_account.items(), key=lambda x: x[1]['savings'], reverse=True)[:5]

        lines = [
            '',
            'EC2 Rightsizing Analysis Summary',
            '=' * 70,
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            '',
            f"Total Recommendations: {total_instances}",
            '',
            'Actions:',
            f"  - Downsize: {actions['downsize']} instances",
            f"  - Upsize: {actions['upsize']} instances",
            '',
            'Potential Savings:',
            f"  - Monthly: ${total_monthly:,.2f}",
            f"  - Annual: ${total_annual:,.2f}",
            '',
            'Top 5 Accounts by Savings:',
        ]

        for i, (account, data) in enumerate(top_accounts, 1):
            lines.append(f"  {i}. {account}: ${data['savings']:,.2f}/month ({data['count']} instances)")

        lines.append('=' * 70)
        return '\n'.join(lines)

    def upload_to_s3(self, local_file: str) -> Optional[str]:
        """Upload a local report file to S3."""
        date = datetime.utcnow()
        s3_key = f"{date.year}/{date.month:02d}/{date.day:02d}/{os.path.basename(local_file)}"

        try:
            self.s3_client.upload_file(local_file, self.bucket_name, s3_key)
            return f"s3://{self.bucket_name}/{s3_key}"
        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            return None
