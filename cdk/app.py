#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.site_stack import SiteStack
from stacks.api_stack import ApiStack

app = cdk.App()

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION", "us-east-1")  # For ACM cert on CloudFront, cert must be in us-east-1
)

domain_name = app.node.try_get_context("domain_name") or "example.com"
subdomain = app.node.try_get_context("subdomain") or "www"

# Deploy API (Lambda + API GW + DDB + Cognito + WAF option deferred)
api = ApiStack(app, "ApiStack",
               env=env,
               table_name="demo_app",
               enable_xray=True)

# Deploy static site + CloudFront (OAC) + attach /api/* to API Gateway as second origin
site = SiteStack(app, "SiteStack",
                 env=env,
                 domain_name=domain_name,
                 subdomain=subdomain,
                 api_url=api.api_execute_url,
                 distribution_description="Serverless Landing Demo",
                 waf_acl_arn=None)

app.synth()
