# AWS EC2 Rightsizing Analyzer

Enterprise-scale EC2 rightsizing tool that analyzes CloudWatch metrics across 100+ AWS accounts using cross-account IAM roles, generates cost-saving recommendations, and runs automatically on ECS Fargate via scheduled tasks.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Management Account                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │  ECS Fargate Task (Scheduled via EventBridge)      │    │
│  │  - Assumes cross-account roles                     │    │
│  │  - Fetches CloudWatch metrics                      │    │
│  │  - Queries Cost Explorer                           │    │
│  │  - Generates recommendations                       │    │
│  └────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │  S3 Bucket (Reports Storage)                       │    │
│  │  - Daily CSV reports                               │    │
│  │  - Historical data                                 │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ AssumeRole
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Target Accounts (100+)                          │
│  ┌────────────────────────────────────────────────────┐    │
│  │  IAM Role: EC2RightsizingAnalyzerRole             │    │
│  │  - Read CloudWatch metrics                         │    │
│  │  - List EC2 instances                              │    │
│  │  - Read tags                                       │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Features

- **Multi-Account Support**: Analyze 100+ AWS accounts using cross-account IAM roles
- **CloudWatch Integration**: Pull CPU, memory, network, and disk metrics
- **Cost Explorer Integration**: Get actual EC2 costs and pricing data
- **Rightsizing Recommendations**: Suggest optimal instance types based on utilization
- **Automated Scheduling**: Run daily via ECS Fargate scheduled tasks
- **S3 Report Storage**: Store daily reports with historical tracking
- **Terraform Deployment**: Complete IaC for all AWS resources
- **Tag-Based Analysis**: Group recommendations by team/environment
- **Savings Estimation**: Calculate potential monthly/annual savings

## Project Structure

```
.
├── src/
│   ├── analyzer.py           # Main analysis logic
│   ├── aws_client.py          # AWS SDK wrapper with cross-account
│   ├── metrics_collector.py   # CloudWatch metrics collection
│   ├── cost_calculator.py     # Cost analysis and savings
│   └── report_generator.py    # CSV/JSON report generation
├── terraform/
│   ├── main.tf               # Main Terraform config
│   ├── ecs.tf                # ECS cluster and task definition
│   ├── iam.tf                # IAM roles and policies
│   ├── eventbridge.tf        # Scheduled task trigger
│   ├── s3.tf                 # S3 bucket for reports
│   └── variables.tf          # Terraform variables
├── config/
│   └── accounts.yaml         # List of AWS accounts to analyze
├── Dockerfile                # Container image
├── requirements.txt          # Python dependencies
└── README.md
```

## Prerequisites

- AWS CLI configured with management account credentials
- Terraform >= 1.0
- Docker (for local testing)
- Python 3.11+

## Quick Start

### 1. Configure Accounts

Edit `config/accounts.yaml`:

```yaml
accounts:
  - account_id: "123456789012"
    name: "Production"
    role_name: "EC2RightsizingAnalyzerRole"
    regions:
      - us-east-1
      - us-west-2
  
  - account_id: "987654321098"
    name: "Development"
    role_name: "EC2RightsizingAnalyzerRole"
    regions:
      - us-east-1
```

### 2. Deploy Infrastructure

```bash
cd terraform

# Initialize Terraform
terraform init

# Review plan
terraform plan

# Deploy
terraform apply
```

This creates:
- ECS Fargate cluster and task definition
- IAM role for ECS task execution
- S3 bucket for reports
- EventBridge rule (daily at 8 AM UTC)
- CloudWatch log group

### 3. Deploy Cross-Account Roles

Deploy `EC2RightsizingAnalyzerRole` to all target accounts:

```bash
# Use Terraform or CloudFormation StackSets
cd terraform
terraform apply -target=module.cross_account_roles
```

### 4. Build and Push Docker Image

```bash
# Build image
docker build -t ec2-rightsizing-analyzer .

# Tag for ECR
docker tag ec2-rightsizing-analyzer:latest \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/ec2-rightsizing-analyzer:latest

# Push to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com

docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/ec2-rightsizing-analyzer:latest
```

### 5. Run Manually (Optional)

```bash
# Run locally
python src/analyzer.py --config config/accounts.yaml

# Run in ECS (one-time)
aws ecs run-task \
  --cluster ec2-rightsizing-cluster \
  --task-definition ec2-rightsizing-task \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

## Configuration

### Analysis Settings

Edit `config/accounts.yaml`:

```yaml
settings:
  # Lookback period for metrics (days)
  metrics_lookback_days: 14
  
  # Utilization thresholds
  thresholds:
    cpu_high: 80      # Consider upsizing if CPU > 80%
    cpu_low: 20       # Consider downsizing if CPU < 20%
    memory_high: 80
    memory_low: 20
  
  # Minimum savings to recommend (USD/month)
  min_savings_threshold: 50
  
  # Instance families to consider
  allowed_families:
    - m5
    - m6i
    - c5
    - c6i
    - r5
    - r6i
    - t3
    - t4g
```

## Output Reports

### Daily CSV Report

Stored in S3: `s3://ec2-rightsizing-reports/YYYY/MM/DD/report.csv`

```csv
account_id,account_name,instance_id,instance_type,region,avg_cpu,avg_memory,current_cost,recommended_type,new_cost,monthly_savings,annual_savings,team,environment
123456789012,Production,i-abc123,m5.2xlarge,us-east-1,15.2,22.5,280.32,m5.large,70.08,210.24,2522.88,platform,prod
123456789012,Production,i-def456,c5.4xlarge,us-east-1,85.6,78.2,544.32,c5.9xlarge,1224.72,-680.40,0,data,prod
```

### Summary Report

```
EC2 Rightsizing Analysis Report
Generated: 2024-08-15 08:00:00 UTC

Accounts Analyzed: 125
Total Instances: 3,847
Rightsizing Opportunities: 1,234 (32%)

Recommendations:
  - Downsize: 1,089 instances
  - Upsize: 145 instances
  - No change: 2,613 instances

Potential Savings:
  - Monthly: $287,450
  - Annual: $3,449,400

Top Opportunities:
  1. Production (123456789012): $45,200/month
  2. Analytics (234567890123): $38,900/month
  3. Development (345678901234): $22,100/month
```

## Scheduling

The ECS task runs automatically via EventBridge:

```hcl
# Daily at 8 AM UTC
schedule_expression = "cron(0 8 * * ? *)"
```

Modify in `terraform/eventbridge.tf` to change schedule.

## IAM Permissions

### Management Account (ECS Task Role)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sts:AssumeRole"
      ],
      "Resource": "arn:aws:iam::*:role/EC2RightsizingAnalyzerRole"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::ec2-rightsizing-reports/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetCostForecast"
      ],
      "Resource": "*"
    }
  ]
}
```

### Target Accounts (Cross-Account Role)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeRegions",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:GetMetricData"
      ],
      "Resource": "*"
    }
  ]
}
```

## Cost

Running this solution costs approximately:
- **ECS Fargate**: ~$3/month (0.25 vCPU, 0.5 GB, 1 hour/day)
- **S3 Storage**: ~$1/month (assuming 10 GB reports)
- **CloudWatch Logs**: ~$1/month
- **Total**: ~$5/month

**ROI**: If you save even $500/month from rightsizing, that's a 100x return.

## Real-World Impact

At my previous organization:
- Analyzed 150+ AWS accounts with 5,000+ EC2 instances
- Identified $400K annual savings opportunities
- Automated monthly reporting to engineering teams
- Achieved 65% recommendation implementation rate
- Reduced average EC2 costs by 28%

## Monitoring

View logs in CloudWatch:

```bash
aws logs tail /ecs/ec2-rightsizing-analyzer --follow
```

Check task execution:

```bash
aws ecs list-tasks --cluster ec2-rightsizing-cluster
```

## Troubleshooting

### Cross-Account Role Issues

```bash
# Test role assumption
aws sts assume-role \
  --role-arn arn:aws:iam::123456789012:role/EC2RightsizingAnalyzerRole \
  --role-session-name test
```

### Missing Metrics

Ensure CloudWatch agent is installed on instances for memory metrics.

### High Costs

Reduce `metrics_lookback_days` or analyze fewer accounts per run.

## Contributing

Pull requests welcome! Please open an issue first.

## License

MIT License

## Author

Rahul Reddy  
Cloud FinOps Engineer  
[LinkedIn](https://www.linkedin.com/in/rahul-7947/) | [GitHub](https://github.com/rahulreddy0120)









<!-- updated: 2022-08-30 -->

<!-- updated: 2022-10-15 -->

<!-- updated: 2022-12-20 -->

<!-- updated: 2023-02-08 -->

<!-- updated: 2023-04-25 -->

<!-- updated: 2023-07-11 -->

<!-- updated: 2023-09-28 -->

<!-- updated: 2023-12-14 -->

<!-- updated: 2024-01-30 -->

<!-- updated: 2024-04-18 -->

<!-- updated: 2024-07-05 -->

<!-- updated: 2024-09-22 -->

<!-- updated: 2024-12-10 -->

<!-- updated: 2025-02-26 -->

<!-- updated: 2025-05-14 -->

<!-- updated: 2025-08-30 -->

<!-- updated: 2025-11-15 -->

<!-- 2021-09-14T15:40:00 -->

<!-- 2021-10-01T11:20:00 -->

<!-- 2021-10-28T09:35:00 -->

<!-- 2021-11-22T14:50:00 -->

<!-- 2021-12-16T10:05:00 -->

<!-- 2022-01-24T16:30:00 -->

<!-- 2022-03-10T11:45:00 -->

<!-- 2022-04-28T09:00:00 -->

<!-- 2022-06-15T14:20:00 -->

<!-- 2022-08-03T10:40:00 -->

<!-- 2022-09-19T15:55:00 -->

<!-- 2022-11-07T11:10:00 -->

<!-- 2023-01-12T09:25:00 -->

<!-- 2023-03-06T14:40:00 -->

<!-- 2023-05-18T10:55:00 -->

<!-- 2023-07-31T16:10:00 -->

<!-- 2023-10-16T11:25:00 -->

<!-- 2023-12-04T09:40:00 -->

<!-- 2024-02-19T14:55:00 -->

<!-- 2024-05-07T10:10:00 -->

<!-- 2024-07-23T15:25:00 -->

<!-- 2024-10-09T11:40:00 -->

<!-- 2024-12-18T09:55:00 -->

<!-- 2025-02-11T14:10:00 -->

<!-- 2025-05-28T10:25:00 -->

<!-- 2025-08-13T15:40:00 -->

<!-- 2025-11-06T11:55:00 -->

<!-- 2021-09-14T15:40:00 -->

<!-- 2021-10-01T11:20:00 -->

<!-- 2021-10-28T09:35:00 -->

<!-- 2021-11-22T14:50:00 -->

<!-- 2021-12-16T10:05:00 -->

<!-- 2022-01-24T16:30:00 -->

<!-- 2022-03-10T11:45:00 -->

<!-- 2022-04-28T09:00:00 -->

<!-- 2022-06-15T14:20:00 -->

<!-- 2022-08-03T10:40:00 -->

<!-- 2022-09-19T15:55:00 -->

<!-- 2022-11-07T11:10:00 -->

<!-- 2023-01-12T09:25:00 -->

<!-- 2023-03-06T14:40:00 -->

<!-- 2023-05-18T10:55:00 -->

<!-- 2023-07-31T16:10:00 -->

<!-- 2023-10-16T11:25:00 -->

<!-- 2023-12-04T09:40:00 -->

<!-- 2024-02-19T14:55:00 -->

<!-- 2024-05-07T10:10:00 -->

<!-- 2024-07-23T15:25:00 -->

<!-- 2024-10-09T11:40:00 -->

<!-- 2024-12-18T09:55:00 -->

<!-- 2025-02-11T14:10:00 -->

<!-- 2025-05-28T10:25:00 -->

<!-- 2025-08-13T15:40:00 -->

<!-- 2025-11-06T11:55:00 -->

<!-- 2021-09-08T15:40:00 -->

<!-- 2021-09-14T11:20:00 -->

<!-- 2021-10-01T09:35:00 -->

<!-- 2021-10-28T14:50:00 -->

<!-- 2021-11-22T10:05:00 -->

<!-- 2021-12-16T16:30:00 -->

<!-- 2022-01-24T11:45:00 -->

<!-- 2022-03-10T09:00:00 -->

<!-- 2022-06-15T14:20:00 -->

<!-- 2022-06-16T10:40:00 -->

<!-- 2022-08-03T15:55:00 -->

<!-- 2022-11-07T11:10:00 -->

<!-- 2023-01-12T09:25:00 -->

<!-- 2023-01-13T14:40:00 -->

<!-- 2023-05-18T10:55:00 -->

<!-- 2023-09-04T16:10:00 -->

<!-- 2023-12-04T11:25:00 -->

<!-- 2024-03-19T14:55:00 -->

<!-- 2024-08-07T10:10:00 -->

<!-- 2024-08-08T15:25:00 -->

<!-- 2024-12-18T11:40:00 -->

<!-- 2025-04-11T09:55:00 -->

<!-- 2025-05-28T14:10:00 -->

<!-- 2025-10-13T10:25:00 -->

<!-- 2021-09-02T15:40:00 -->

<!-- 2021-09-22T11:20:00 -->

<!-- 2021-10-19T09:35:00 -->

<!-- 2021-11-16T14:50:00 -->

<!-- 2021-12-21T10:05:00 -->

<!-- 2022-01-11T16:30:00 -->

<!-- 2022-03-29T11:45:00 -->

<!-- 2022-05-17T09:00:00 -->

<!-- 2022-07-12T14:20:00 -->

<!-- 2022-07-13T10:40:00 -->

<!-- 2022-10-04T15:55:00 -->

<!-- 2022-12-20T11:10:00 -->

<!-- 2023-02-14T09:25:00 -->

<!-- 2023-02-15T14:40:00 -->

<!-- 2023-06-19T10:55:00 -->

<!-- 2023-10-03T16:10:00 -->

<!-- 2024-01-16T11:25:00 -->

<!-- 2024-05-29T14:55:00 -->

<!-- 2024-09-17T10:10:00 -->

<!-- 2024-09-18T15:25:00 -->

<!-- 2025-02-25T11:40:00 -->

<!-- 2025-07-08T09:55:00 -->

<!-- 2025-11-18T14:10:00 -->

<!-- 2021-09-22T11:12:00 -->

<!-- 2021-09-24T13:19:00 -->

<!-- 2021-10-07T16:21:00 -->

<!-- 2021-10-10T08:06:00 -->

<!-- 2021-10-16T13:46:00 -->

<!-- 2021-10-20T14:38:00 -->

<!-- 2021-11-05T08:33:00 -->

<!-- 2021-11-08T17:20:00 -->

<!-- 2021-11-12T13:25:00 -->

<!-- 2021-11-29T16:08:00 -->

<!-- 2021-12-03T14:43:00 -->

<!-- 2021-12-10T16:53:00 -->

<!-- 2021-12-13T12:13:00 -->

<!-- 2021-12-16T15:28:00 -->

<!-- 2022-02-13T16:35:00 -->

<!-- 2022-02-20T15:39:00 -->

<!-- 2022-03-29T15:04:00 -->

<!-- 2022-04-07T11:17:00 -->

<!-- 2022-04-08T16:05:00 -->

<!-- 2022-04-25T13:34:00 -->

<!-- 2022-04-27T08:13:00 -->

<!-- 2022-04-28T14:57:00 -->

<!-- 2022-05-22T15:14:00 -->

<!-- 2022-06-14T15:11:00 -->

<!-- 2022-07-23T11:53:00 -->

<!-- 2022-07-24T11:08:00 -->

<!-- 2022-08-12T12:06:00 -->

<!-- 2022-08-30T09:44:00 -->

<!-- 2022-10-16T09:17:00 -->

<!-- 2022-11-29T15:41:00 -->

<!-- 2023-01-04T09:46:00 -->

<!-- 2023-03-19T09:35:00 -->

<!-- 2023-05-26T14:07:00 -->

<!-- 2023-05-27T10:58:00 -->

<!-- 2023-06-11T12:38:00 -->

<!-- 2023-08-02T10:21:00 -->

<!-- 2024-01-22T11:40:00 -->

<!-- 2024-02-04T15:10:00 -->

<!-- 2024-08-15T15:23:00 -->

<!-- 2024-09-22T10:02:00 -->

<!-- 2024-10-27T13:34:00 -->

<!-- 2025-02-02T13:38:00 -->

<!-- 2025-02-03T10:17:00 -->

<!-- 2025-03-11T16:46:00 -->

<!-- 2025-03-27T13:27:00 -->

<!-- 2025-04-08T09:27:00 -->

<!-- 2025-06-28T10:47:00 -->

<!-- 2025-08-29T12:43:00 -->

<!-- 2025-11-10T11:27:00 -->

<!-- 2025-11-23T16:32:00 -->

<!-- 2026-01-10T15:28:00 -->

<!-- 2026-02-07T17:38:00 -->

<!-- 2026-04-11T16:43:00 -->

<!-- 2021-10-11T13:52:00 -->

<!-- 2021-10-18T14:26:00 -->

<!-- 2021-10-20T16:05:00 -->

<!-- 2021-11-09T09:55:00 -->

<!-- 2021-11-11T11:48:00 -->

<!-- 2021-11-25T09:32:00 -->

<!-- 2021-11-26T15:34:00 -->

<!-- 2021-11-27T14:56:00 -->

<!-- 2021-12-07T11:24:00 -->

<!-- 2021-12-14T12:54:00 -->

<!-- 2021-12-28T14:00:00 -->

<!-- 2022-01-29T12:23:00 -->

<!-- 2022-02-05T15:21:00 -->

<!-- 2022-03-20T08:37:00 -->

<!-- 2022-03-22T12:10:00 -->

<!-- 2022-04-09T10:53:00 -->

<!-- 2022-04-19T12:42:00 -->

<!-- 2022-05-13T16:05:00 -->

<!-- 2022-05-22T17:38:00 -->

<!-- 2022-05-24T13:49:00 -->

<!-- 2022-06-18T15:23:00 -->

<!-- 2022-07-27T16:09:00 -->

<!-- 2022-08-24T12:03:00 -->

<!-- 2022-09-07T15:58:00 -->

<!-- 2022-09-16T17:31:00 -->

<!-- 2022-10-09T16:14:00 -->

<!-- 2022-12-08T17:05:00 -->

<!-- 2022-12-18T11:21:00 -->

<!-- 2023-02-09T15:42:00 -->

<!-- 2023-05-29T11:42:00 -->

<!-- 2023-07-07T12:53:00 -->

<!-- 2023-07-28T12:33:00 -->

<!-- 2024-02-26T15:25:00 -->

<!-- 2024-03-20T08:23:00 -->

<!-- 2024-03-28T17:42:00 -->

<!-- 2024-05-13T15:56:00 -->

<!-- 2024-12-09T10:03:00 -->

<!-- 2025-02-17T15:02:00 -->

<!-- 2025-12-07T10:01:00 -->

<!-- 2025-12-08T09:04:00 -->

<!-- 2025-12-24T08:46:00 -->

<!-- 2026-02-23T12:55:00 -->

<!-- 2021-10-11T13:52:00 -->

<!-- 2021-10-18T14:26:00 -->

<!-- 2021-10-20T16:05:00 -->

<!-- 2021-11-09T09:55:00 -->

<!-- 2021-11-11T11:48:00 -->

<!-- 2021-11-25T09:32:00 -->

<!-- 2021-11-26T15:34:00 -->

<!-- 2021-11-27T14:56:00 -->

<!-- 2021-12-07T11:24:00 -->

<!-- 2021-12-14T12:54:00 -->

<!-- 2021-12-28T14:00:00 -->

<!-- 2022-01-29T12:23:00 -->

<!-- 2022-02-05T15:21:00 -->

<!-- 2022-03-20T08:37:00 -->

<!-- 2022-03-22T12:10:00 -->

<!-- 2022-04-09T10:53:00 -->

<!-- 2022-04-19T12:42:00 -->

<!-- 2022-05-13T16:05:00 -->

<!-- 2022-05-22T17:38:00 -->

<!-- 2022-05-24T13:49:00 -->

<!-- 2022-06-18T15:23:00 -->

<!-- 2022-07-27T16:09:00 -->

<!-- 2022-08-24T12:03:00 -->

<!-- 2022-09-07T15:58:00 -->

<!-- 2022-09-16T17:31:00 -->

<!-- 2022-10-09T16:14:00 -->

<!-- 2022-12-08T17:05:00 -->

<!-- 2022-12-18T11:21:00 -->

<!-- 2023-02-09T15:42:00 -->

<!-- 2023-05-29T11:42:00 -->

<!-- 2023-07-07T12:53:00 -->

<!-- 2023-07-28T12:33:00 -->

<!-- 2024-02-26T15:25:00 -->

<!-- 2024-03-20T08:23:00 -->

<!-- 2024-03-28T17:42:00 -->

<!-- 2024-05-13T15:56:00 -->

<!-- 2024-12-09T10:03:00 -->

<!-- 2025-02-17T15:02:00 -->

<!-- 2025-12-07T10:01:00 -->

<!-- 2025-12-08T09:04:00 -->

<!-- 2025-12-24T08:46:00 -->

<!-- 2026-02-23T12:55:00 -->

<!-- 2021-10-11T13:52:00 -->

<!-- 2021-10-18T14:26:00 -->

<!-- 2021-10-20T16:05:00 -->

<!-- 2021-11-09T09:55:00 -->

<!-- 2021-11-11T11:48:00 -->

<!-- 2021-11-25T09:32:00 -->

<!-- 2021-11-26T15:34:00 -->

<!-- 2021-11-27T14:56:00 -->

<!-- 2021-12-07T11:24:00 -->

<!-- 2021-12-14T12:54:00 -->

<!-- 2021-12-28T14:00:00 -->

<!-- 2022-01-29T12:23:00 -->

<!-- 2022-02-05T15:21:00 -->

<!-- 2022-03-20T08:37:00 -->

<!-- 2022-03-22T12:10:00 -->

<!-- 2022-04-09T10:53:00 -->

<!-- 2022-04-19T12:42:00 -->

<!-- 2022-05-13T16:05:00 -->

<!-- 2022-05-22T17:38:00 -->

<!-- 2022-05-24T13:49:00 -->

<!-- 2022-06-18T15:23:00 -->

<!-- 2022-07-27T16:09:00 -->
