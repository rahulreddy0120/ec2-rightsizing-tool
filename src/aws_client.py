#!/usr/bin/env python3
"""
AWS Client wrapper with cross-account role assumption and retry logic.
"""

import time
from typing import Optional

import boto3
import botocore.exceptions
import logging

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds


class AWSClient:
    """Thin wrapper around boto3 providing cross-account STS role assumption
    and paginated EC2 instance listing with automatic retries."""

    def __init__(self) -> None:
        self.sts_client = boto3.client('sts')

    def assume_role(
        self,
        account_id: str,
        role_name: str,
        region: str = 'us-east-1',
    ) -> Optional[boto3.Session]:
        """Assume a cross-account IAM role with exponential-backoff retry.

        Returns:
            A boto3 Session using the temporary credentials, or ``None``
            on failure after all retries are exhausted.
        """
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.sts_client.assume_role(
                    RoleArn=role_arn,
                    RoleSessionName=f'ec2-rightsizing-{account_id}',
                    DurationSeconds=3600,
                )

                credentials = response['Credentials']

                session = boto3.Session(
                    aws_access_key_id=credentials['AccessKeyId'],
                    aws_secret_access_key=credentials['SecretAccessKey'],
                    aws_session_token=credentials['SessionToken'],
                    region_name=region,
                )

                logger.info(f"  Assumed role: {role_arn}")
                return session

            except botocore.exceptions.ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code in ('Throttling', 'RequestLimitExceeded') and attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF_BASE ** attempt
                    logger.warning(f"  Throttled on assume_role (attempt {attempt}), retrying in {wait}s")
                    time.sleep(wait)
                    continue
                logger.error(f"  Failed to assume role {role_arn}: {e}")
                return None
            except Exception as e:
                logger.error(f"  Failed to assume role {role_arn}: {e}")
                return None

        return None

    def get_ec2_instances(self, session: boto3.Session, region: str) -> list[dict]:
        """Return all running EC2 instances, handling pagination and retries."""
        ec2 = session.client('ec2', region_name=region)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                paginator = ec2.get_paginator('describe_instances')
                page_iterator = paginator.paginate(
                    Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
                )

                instances: list[dict] = []
                for page in page_iterator:
                    for reservation in page['Reservations']:
                        instances.extend(reservation['Instances'])

                return instances

            except botocore.exceptions.ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code in ('Throttling', 'RequestLimitExceeded') and attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF_BASE ** attempt
                    logger.warning(f"  Throttled on describe_instances (attempt {attempt}), retrying in {wait}s")
                    time.sleep(wait)
                    continue
                logger.error(f"  Error fetching instances: {e}")
                return []
            except Exception as e:
                logger.error(f"  Error fetching instances: {e}")
                return []

        return []
