from aws_cdk import (
    Stack,
    Duration,
    aws_apigateway as apigw,
    aws_lambda as _lambda,
    aws_dynamodb as ddb,
    aws_iam as iam,
    aws_logs as logs,
    aws_cognito as cognito,
    aws_xray as xray,
)
from constructs import Construct

class ApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str,
                 table_name: str = "demo_app",
                 enable_xray: bool = True,
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        table = ddb.Table(self, "DemoTable",
                          table_name=table_name,
                          partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
                          sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING),
                          billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
                          point_in_time_recovery=True,
                          removal_policy=None)

        # Lambdas
        common_env = {
            "TABLE_NAME": table.table_name
        }
        runtime = _lambda.Runtime.PYTHON_3_12

        subscribe_fn = _lambda.Function(self, "SubscribeFn",
                                        runtime=runtime,
                                        handler="subscribe.handler",
                                        code=_lambda.Code.from_asset("../functions"),
                                        environment=common_env,
                                        timeout=Duration.seconds(10),
                                        tracing=_lambda.Tracing.ACTIVE if enable_xray else _lambda.Tracing.DISABLED,
                                        log_retention=logs.RetentionDays.TWO_WEEKS)

        contact_fn = _lambda.Function(self, "ContactFn",
                                      runtime=runtime,
                                      handler="contact.handler",
                                      code=_lambda.Code.from_asset("../functions"),
                                      environment=common_env,
                                      timeout=Duration.seconds(10),
                                      tracing=_lambda.Tracing.ACTIVE if enable_xray else _lambda.Tracing.DISABLED,
                                      log_retention=logs.RetentionDays.TWO_WEEKS)

        metrics_fn = _lambda.Function(self, "MetricsFn",
                                      runtime=runtime,
                                      handler="metrics.handler",
                                      code=_lambda.Code.from_asset("../functions"),
                                      environment=common_env,
                                      timeout=Duration.seconds(10),
                                      tracing=_lambda.Tracing.ACTIVE if enable_xray else _lambda.Tracing.DISABLED,
                                      log_retention=logs.RetentionDays.TWO_WEEKS)

        table.grant_read_write_data(subscribe_fn)
        table.grant_read_write_data(contact_fn)
        table.grant_read_data(metrics_fn)

        # Cognito for /metrics auth
        user_pool = cognito.UserPool(self, "UserPool",
                                     self_sign_up_enabled=False,
                                     sign_in_aliases=cognito.SignInAliases(email=True),
                                     standard_attributes=cognito.StandardAttributes(
                                         email=cognito.StandardAttribute(required=True, mutable=False)
                                     ))
        user_pool_client = user_pool.add_client("UserPoolClient",
                                                auth_flows=cognito.AuthFlow(user_password=True),
                                                generate_secret=False)
        authorizer = apigw.CognitoUserPoolsAuthorizer(self, "Authorizer",
                                                      cognito_user_pools=[user_pool])

        # API Gateway
        api = apigw.RestApi(self, "HttpApi",
                            deploy_options=apigw.StageOptions(metrics_enabled=True, logging_level=apigw.MethodLoggingLevel.INFO, tracing_enabled=enable_xray),
                            cloud_watch_role=True)

        # /subscribe
        subscribe = api.root.add_resource("api").add_resource("subscribe")
        subscribe_lambda_integration = apigw.LambdaIntegration(subscribe_fn, proxy=True)
        subscribe.add_method("POST", subscribe_lambda_integration)

        # /contact
        contact = api.root.get_resource("api").add_resource("contact")
        contact_lambda_integration = apigw.LambdaIntegration(contact_fn, proxy=True)
        contact.add_method("POST", contact_lambda_integration)

        # /metrics/summary (protected)
        metrics = api.root.get_resource("api").add_resource("metrics").add_resource("summary")
        metrics_lambda_integration = apigw.LambdaIntegration(metrics_fn, proxy=True)
        metrics.add_method("GET", metrics_lambda_integration,
                           authorizer=authorizer,
                           authorization_type=apigw.AuthorizationType.COGNITO)

        # X-Ray enable
        if enable_xray:
            xray.CfnSamplingRule(self, "DefaultSampling",
                                 rule_name="DefaultRule",
                                 resource_arn="*",
                                 priority=10000,
                                 fixed_rate=0.1,
                                 reservoir_size=1,
                                 service_name="*",
                                 service_type="*",
                                 host="*",
                                 http_method="*",
                                 url_path="*",
                                 version=1)

        self.api_execute_url = f"{api.url}"
        self.user_pool_id = user_pool.user_pool_id
        self.user_pool_client_id = user_pool_client.user_pool_client_id
