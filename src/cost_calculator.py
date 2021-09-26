#!/usr/bin/env python3
"""
Cost calculator and instance type recommendations.
"""

from typing import Optional
import logging

logger = logging.getLogger(__name__)


class CostCalculator:
    """Provides instance pricing lookups and family-aware resize suggestions."""

    # Simplified pricing (USD/month for us-east-1)
    PRICING: dict[str, float] = {
        't3.micro': 7.59,
        't3.small': 15.18,
        't3.medium': 30.37,
        't3.large': 60.74,
        't3.xlarge': 121.47,
        't3.2xlarge': 242.94,
        'm5.large': 70.08,
        'm5.xlarge': 140.16,
        'm5.2xlarge': 280.32,
        'm5.4xlarge': 560.64,
        'm5.8xlarge': 1121.28,
        'm5.12xlarge': 1681.92,
        'm5.16xlarge': 2242.56,
        'm5.24xlarge': 3363.84,
        'm6i.large': 69.35,
        'm6i.xlarge': 138.70,
        'm6i.2xlarge': 277.39,
        'm6i.4xlarge': 554.78,
        'm6i.8xlarge': 1109.57,
        'c5.large': 62.05,
        'c5.xlarge': 124.10,
        'c5.2xlarge': 248.20,
        'c5.4xlarge': 496.40,
        'c5.9xlarge': 1116.90,
        'c5.18xlarge': 2233.80,
        'r5.large': 91.98,
        'r5.xlarge': 183.96,
        'r5.2xlarge': 367.92,
        'r5.4xlarge': 735.84,
        'r5.8xlarge': 1471.68,
    }

    INSTANCE_HIERARCHY: dict[str, list[str]] = {
        't3': ['t3.micro', 't3.small', 't3.medium', 't3.large', 't3.xlarge', 't3.2xlarge'],
        'm5': ['m5.large', 'm5.xlarge', 'm5.2xlarge', 'm5.4xlarge', 'm5.8xlarge', 'm5.12xlarge', 'm5.16xlarge', 'm5.24xlarge'],
        'm6i': ['m6i.large', 'm6i.xlarge', 'm6i.2xlarge', 'm6i.4xlarge', 'm6i.8xlarge'],
        'c5': ['c5.large', 'c5.xlarge', 'c5.2xlarge', 'c5.4xlarge', 'c5.9xlarge', 'c5.18xlarge'],
        'r5': ['r5.large', 'r5.xlarge', 'r5.2xlarge', 'r5.4xlarge', 'r5.8xlarge'],
    }

    def get_instance_cost(self, instance_type: str, region: str = 'us-east-1') -> float:
        """Return monthly cost for *instance_type*.

        Logs a warning and returns 0 for unknown types.
        """
        if not instance_type or '.' not in instance_type:
            logger.warning(f"Invalid instance type format: {instance_type!r}")
            return 0.0

        cost = self.PRICING.get(instance_type)
        if cost is None:
            logger.warning(f"No pricing data for {instance_type} in {region}")
            return 0.0
        return cost

    def get_instance_family(self, instance_type: str) -> str:
        """Extract instance family (e.g. 'm5' from 'm5.2xlarge')."""
        parts = instance_type.split('.')
        if len(parts) != 2:
            logger.warning(f"Cannot parse instance family from {instance_type!r}")
            return ''
        return parts[0]

    def get_smaller_instance(self, instance_type: str) -> Optional[str]:
        """Return the next smaller instance in the same family, or None."""
        family = self.get_instance_family(instance_type)
        if not family or family not in self.INSTANCE_HIERARCHY:
            return None

        hierarchy = self.INSTANCE_HIERARCHY[family]
        try:
            idx = hierarchy.index(instance_type)
            return hierarchy[idx - 1] if idx > 0 else None
        except ValueError:
            logger.warning(f"{instance_type} not found in {family} hierarchy")
            return None

    def get_larger_instance(self, instance_type: str) -> Optional[str]:
        """Return the next larger instance in the same family, or None."""
        family = self.get_instance_family(instance_type)
        if not family or family not in self.INSTANCE_HIERARCHY:
            return None

        hierarchy = self.INSTANCE_HIERARCHY[family]
        try:
            idx = hierarchy.index(instance_type)
            return hierarchy[idx + 1] if idx < len(hierarchy) - 1 else None
        except ValueError:
            logger.warning(f"{instance_type} not found in {family} hierarchy")
            return None

    # -- generation-aware upgrade paths --
    GENERATION_UPGRADES: dict[str, str] = {
        'm5': 'm6i',
        'c5': 'c5',   # placeholder until c6i pricing added
        'r5': 'r5',
    }

    def suggest_generation_upgrade(self, instance_type: str) -> Optional[str]:
        """Suggest a newer-generation equivalent when available.

        Returns the equivalent instance type in the newer family, or None
        if no upgrade path is defined.
        """
        family = self.get_instance_family(instance_type)
        new_family = self.GENERATION_UPGRADES.get(family)
        if not new_family or new_family == family:
            return None

        size = instance_type.split('.', 1)[1]
        candidate = f"{new_family}.{size}"
        if candidate in self.PRICING:
            return candidate
        return None
