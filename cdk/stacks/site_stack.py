from typing import Optional
from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_cloudfront as cf,
    aws_cloudfront_origins as origins,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_s3_deployment as s3deploy,
    aws_iam as iam,
)
from constructs import Construct

# Minimal CloudFront Function for A/B variant cookie
AB_FUNCTION_CODE = """function handler(event) {
  var req = event.request;
  var headers = req.headers;
  var cookie = headers.cookie && headers.cookie.value || "";
  if (cookie.indexOf("ab-variant=") === -1) {
    // simple 50/50 split
    var variant = Math.random() < 0.5 ? "A" : "B";
    var res = {
      statusCode: 200,
      statusDescription: "OK",
      headers: {
        "set-cookie": { value: "ab-variant=" + variant + "; Path=/; Max-Age=2592000; Secure; SameSite=Lax" }
      }
    };
    // pass through by returning request (can't both set cookie and pass immediately in Function)
    // Use a small redirect to set cookie then continue
    res.statusCode = 302;
    res.statusDescription = "Found";
    res.headers["location"] = { value: req.uri };
    return res;
  }
  return req;
}
"""

class SiteStack(Stack):
    def __init__(self, scope: Construct, construct_id: str,
                 domain_name: str,
                 subdomain: str,
                 api_url: str,
                 distribution_description: str = "Demo",
                 waf_acl_arn: Optional[str] = None,
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Static site bucket (OAC only)
        site_bucket = s3.Bucket(self, "SiteBucket",
                                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                                encryption=s3.BucketEncryption.S3_MANAGED,
                                removal_policy=RemovalPolicy.DESTROY,
                                auto_delete_objects=True)

        # CloudFront OAC
        oac = cf.OriginAccessControl(self, "OAC",
                                     origin_access_control_name="SiteOAC",
                                     origin_access_control_origin_type=cf.OriginAccessControlOriginType.S3,
                                     signing_behavior=cf.OriginAccessControlSigningBehavior.ALWAYS,
                                     signing_protocol=cf.OriginAccessControlSigningProtocol.SIGV4)

        # Policy to allow CloudFront access to S3
        site_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[site_bucket.arn_for_objects("*")],
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                conditions={"StringEquals": {"AWS:SourceArn": f"arn:aws:cloudfront::{self.account}:distribution/*"}}
            )
        )

        # ACM certificate (optional). If you provide a cert_arn via context later, attach it; otherwise use default CF domain.
        cert_arn = self.node.try_get_context("certificate_arn")
        certificate = None
        if cert_arn:
            certificate = acm.Certificate.from_certificate_arn(self, "Cert", cert_arn)

        # CloudFront Function for A/B cookie
        ab_func = cf.Function(self, "ABFunction",
                              code=cf.FunctionCode.from_inline(AB_FUNCTION_CODE))

        # Static site origin
        s3_origin = origins.S3Origin(site_bucket,
                                     origin_access_identity=None)  # Using OAC (modern)

        # API origin (points to execute-api hostname)
        # api_url like https://abc123.execute-api.us-east-1.amazonaws.com/prod/
        import re
        m = re.match(r"https://([^/]+)/?(.*)", api_url)
        api_host = m.group(1) if m else api_url
        api_origin = origins.HttpOrigin(api_host)

        # Distribution
        default_behavior = cf.BehaviorOptions(
            origin=s3_origin,
            viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            function_associations=[cf.FunctionAssociation(
                function=ab_func,
                event_type=cf.FunctionEventType.VIEWER_REQUEST
            )]
        )

        additional_behaviors = {
            "api/*": cf.BehaviorOptions(
                origin=api_origin,
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cf.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER
            )
        }

        distribution = cf.Distribution(self, "Distribution",
                                       default_behavior=default_behavior,
                                       additional_behaviors=additional_behaviors,
                                       certificate=certificate,
                                       domain_names=[f"{subdomain}.{domain_name}"] if certificate else None,
                                       comment=distribution_description,
                                       enable_logging=False)

        # Optional WAF
        if waf_acl_arn:
            cf.CfnDistribution(self, "DistributionAssoc",
                               distribution_config=distribution.node.default_child.distribution_config,
                               )

        # Optionally create Route53 record if the hosted zone is in Route53
        hosted_zone_id = self.node.try_get_context("hosted_zone_id")
        if certificate and hosted_zone_id:
            zone = route53.HostedZone.from_hosted_zone_attributes(
                self, "HZ",
                hosted_zone_id=hosted_zone_id,
                zone_name=domain_name
            )
            route53.ARecord(self, "AliasRecord",
                            zone=zone,
                            record_name=subdomain,
                            target=route53.RecordTarget.from_alias(targets.CloudFrontTarget(distribution)))

        # Deploy starter site content
        s3deploy.BucketDeployment(self, "DeployWebsite",
                                  destination_bucket=site_bucket,
                                  sources=[s3deploy.Source.asset("../frontend")],
                                  distribution=distribution,
                                  distribution_paths=["/*"])

        self.distribution_domain = distribution.distribution_domain_name
