#!/usr/bin/env python3
"""
CloudWatch metrics collector with robust error handling.
"""

import time
from typing import Optional

import boto3
import botocore.exceptions
import logging
from datetime import datetime, timedelta
from statistics import mean

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2


class MetricsCollector:
    """Collects CPU and memory utilisation metrics from CloudWatch."""

    def __init__(self, config: dict) -> None:
        self.config = config
        self.lookback_days: int = config['settings']['metrics_lookback_days']

    def collect_metrics(
        self,
        session: boto3.Session,
        region: str,
        instance_id: str,
        instance_type: str,
    ) -> Optional[dict]:
        """Collect CloudWatch metrics for an EC2 instance.

        Returns:
            Dict with avg_cpu, avg_memory, and datapoints_count,
            or ``None`` when CPU metrics are unavailable.
        """
        cloudwatch = session.client('cloudwatch', region_name=region)

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=self.lookback_days)

        avg_cpu = self._get_cpu_utilization(cloudwatch, instance_id, start_time, end_time)
        if avg_cpu is None:
            return None

        max_cpu = self._get_peak_cpu(cloudwatch, instance_id, start_time, end_time)
        avg_memory = self._get_memory_utilization(cloudwatch, instance_id, start_time, end_time)

        return {
            'avg_cpu': avg_cpu,
            'max_cpu': max_cpu,
            'avg_memory': avg_memory,
            'datapoints_count': -1,  # kept for backward compat
        }

    def _get_cpu_utilization(
        self,
        cloudwatch,
        instance_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[float]:
        """Fetch average CPU utilisation with retry."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/EC2',
                    MetricName='CPUUtilization',
                    Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,
                    Statistics=['Average'],
                )

                datapoints = response.get('Datapoints', [])
                if not datapoints:
                    logger.warning(f"    No CPU datapoints for {instance_id}")
                    return None

                return mean(dp['Average'] for dp in datapoints)

            except botocore.exceptions.ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code in ('Throttling', 'RequestLimitExceeded') and attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF_BASE ** attempt
                    logger.warning(f"    Throttled fetching CPU for {instance_id}, retry in {wait}s")
                    time.sleep(wait)
                    continue
                logger.error(f"    Error collecting CPU metrics for {instance_id}: {e}")
                return None
            except Exception as e:
                logger.error(f"    Error collecting CPU metrics for {instance_id}: {e}")
                return None

        return None

    def _get_peak_cpu(
        self,
        cloudwatch,
        instance_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> float:
        """Fetch peak (Maximum) CPU utilisation over the lookback window."""
        try:
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Maximum'],
            )
            datapoints = response.get('Datapoints', [])
            if not datapoints:
                return 0.0
            return max(dp['Maximum'] for dp in datapoints)
        except Exception:
            return 0.0

    def _get_memory_utilization(
        self,
        cloudwatch,
        instance_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> float:
        """Fetch average memory utilisation (requires CW Agent). Returns 0 when unavailable."""
        try:
            response = cloudwatch.get_metric_statistics(
                Namespace='CWAgent',
                MetricName='mem_used_percent',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Average'],
            )

            datapoints = response.get('Datapoints', [])
            if not datapoints:
                return 0.0

            return mean(dp['Average'] for dp in datapoints)

        except botocore.exceptions.ClientError:
            logger.debug(f"    Memory metrics unavailable for {instance_id} (CWAgent not installed)")
            return 0.0
        except Exception:
            return 0.0
