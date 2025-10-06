# Serverless Global Landing (AWS CDK + Python Lambda)

This is a minimal, working skeleton for your demo:
- **CloudFront + S3 (OAC)** for static site
- **CloudFront Function** for A/B cookie
- **API Gateway + Lambda (Python 3.12)** for `/api/*`
- **DynamoDB (single-table)** for storing subscribe/contact entries
- **Cognito** user pool (hook to `/api/metrics/*` if you require auth)
- **CDK (Python)** IaC

## Getting Started

### Prereqs
- `AWS CLI` configured
- `cdk bootstrap` done for your account/region
- Python 3.11+ and node installed

### Install CDK deps
```bash
cd cdk
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Context
Set your domain/subdomain (optional; if you don't attach a cert, it will use the default CloudFront domain):
```bash
cdk synth -c domain_name=yourdomain.com -c subdomain=www
```

If you already have an **ACM certificate in us-east-1**, pass its ARN:
```bash
cdk deploy SiteStack -c domain_name=yourdomain.com -c subdomain=www -c certificate_arn=arn:aws:acm:us-east-1:123:certificate/abc
```

### Deploy all
```bash
cdk deploy ApiStack
cdk deploy SiteStack   -c domain_name=yourdomain.com   -c subdomain=www   -c certificate_arn=arn:aws:acm:us-east-1:... # optional
```

### DNS on Aliyun
Create a CNAME for `www.yourdomain.com` -> the CloudFront domain shown after `SiteStack` deploy (like `dxxxxx.cloudfront.net`). For apex domain, either 301 redirect to `www` or move DNS to Route53 (optional).

### Test
Open `https://<your-distribution-domain-or-custom-domain>/`
- `/` static site
- `/admin.html` placeholder
- `/api/subscribe` POST with `{ "email": "a@b.com" }`
- `/api/contact` POST with `{ "name": "...", "email": "...", "message": "..." }`
- `/api/metrics/summary` GET
```

