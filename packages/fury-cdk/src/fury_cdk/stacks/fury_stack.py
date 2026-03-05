from __future__ import annotations
import pathlib
from aws_cdk import (
    Fn,
    Duration,
    CfnOutput,
    RemovalPolicy,
    # aws_sqs as sqs,
    aws_iam,
    aws_ssm,
    aws_sqs,
    aws_lambda,
    aws_events,
    aws_events_targets,
    aws_lambda_event_sources,
)
from aws_cdk.aws_ecr_assets import Platform

from fury_cdk.stacks.permission_boundary import FuryStack
# from crimsonking_cdk.stacks.permission_boundary import CrimsonkingStack
# from crimsonking_cdk.stacks.crimsonking_cdk_core import CollectionStrategy, get_root_path

def get_root_path() -> pathlib.Path:
    this_dir = pathlib.Path(__file__).parent
    cur_dir = this_dir
    # Go to the src folder
    while cur_dir.name != "src":
        cur_dir = cur_dir.parent
        # Three levels up to repo folder
    root_dir = (
        cur_dir.parent.parent.parent  # src  # kayfabe-cdk  # packages  # ih root
    )
    print(f"Root dir = {root_dir}")
    return root_dir

class FuryHealthStatusStack(FuryStack):
    def __init__(
        self,
        scope=None,
        id=None,
        *,
        analytics_reporting=None,
        cross_region_references=None,
        description=None,
        env=None,
        notification_arns=None,
        permissions_boundary=None,
        stack_name=None,
        suppress_template_indentation=None,
        synthesizer=None,
        termination_protection=None,
        permissions_boundary_name=None,
        in_prod:bool=False,
        # collection_strategy:CollectionStrategy=CollectionStrategy.IN_COUNTRY_PROXY,
    ):
        super().__init__(            
            scope,
            id,
            analytics_reporting=analytics_reporting,
            cross_region_references=cross_region_references,
            description=description,
            env=env,
            notification_arns=notification_arns,
            permissions_boundary=permissions_boundary,
            stack_name=stack_name,
            suppress_template_indentation=suppress_template_indentation,
            synthesizer=synthesizer,
            termination_protection=termination_protection,
            permissions_boundary_name=permissions_boundary_name
            )
        # event_handler_code = aws_lambda.Code.from_docker_build(
        #     get_root_path().as_posix(),
        #     file="packages/crimsonking-cdk/dockerfiles/crimsonking-lambda.Dockerfile",            
        #     platform="linux/arm64" if in_prod else "linux/amd64"
        # )        

        self.lambda_role = aws_iam.Role(
            self,
            "LambdaRole",
            assumed_by=aws_iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                    managed_policy_name="service-role/AWSLambdaBasicExecutionRole"
                ),
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                    managed_policy_name="service-role/AWSLambdaSQSQueueExecutionRole"
                ),
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                    managed_policy_name="AmazonS3FullAccess"
                ),
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                    managed_policy_name="AmazonSSMReadOnlyAccess"
                ),
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                    managed_policy_name="CloudWatchLogsFullAccess"
                ),
            ],            
        )

        self.lambda_handler_code = aws_lambda.Code.from_docker_build(
            get_root_path().as_posix(),
            file="packages/fury-cdk/dockerfiles/fury-lambda.Dockerfile",    
            cache_disabled=True,        
            platform="linux/arm64" if in_prod else "linux/amd64"
        )


        self.fury_ping_handler = aws_lambda.Function(
            self,
            "FuryPingHandler",
            code=self.lambda_handler_code,
            role=self.lambda_role,
            logging_format=aws_lambda.LoggingFormat.JSON,
            handler="fury.interface.aws.lambda.lambdapinghandler.handler",
            timeout=Duration.minutes(15) if in_prod else Duration.minutes(5),
            runtime=aws_lambda.Runtime.PYTHON_3_14,
            architecture=aws_lambda.Architecture.ARM_64 if in_prod else aws_lambda.Architecture.X86_64,
        )


        schedule_rule = aws_events.Rule(self, "EveryFifteenMinutesRule",
            schedule=aws_events.Schedule.rate(Duration.minutes(15)),
            description="Triggers the Lambda function every 15 minutes"
        )
        schedule_rule.add_target(aws_events_targets.LambdaFunction(self.fury_ping_handler))


        self.fury_website_ping_handler = aws_lambda.Function(
            self,
            "FuryWebsitePingHandler",
            code=self.lambda_handler_code,
            role=self.lambda_role,
            logging_format=aws_lambda.LoggingFormat.JSON,
            handler="fury.interface.aws.lambda.lambdawebsitepinghandler.handler",
            timeout=Duration.minutes(15),
            runtime=aws_lambda.Runtime.PYTHON_3_14,
            architecture=aws_lambda.Architecture.ARM_64 if in_prod else aws_lambda.Architecture.X86_64,
        )

        schedule_rule.add_target(aws_events_targets.LambdaFunction(self.fury_website_ping_handler))

        # bucket_file_handler_version = self.bucket_file_handler.current_version  
        # self.bucket_file_handler_alias = aws_lambda.Alias(self,
        #                                     "CrimsonkingBucketFileHandlerAlias",
        #                                     alias_name="crimsonking-bucket-file-handler",
        #                                     version=bucket_file_handler_version)     

        # infil_queue_arn = Fn.import_value("crimonsomking-infil-file-queue-arn")   
        # infil_queue = aws_sqs.Queue.from_queue_arn(self,"InfilQueue",infil_queue_arn)  
        # infil_queue.grant_consume_messages(self.bucket_file_handler)
        # self.bucket_file_handler.add_event_source(aws_lambda_event_sources.SqsEventSource(infil_queue))
        
        # ###########################################################################################################

        
            
        # data_bucket_name = (
        #     aws_ssm.StringParameter.from_string_parameter_name(
        #         self,
        #         "DataBucketNameParameter",
        #         "/wormhole/audit/mission_data_bucket_name",
        #     )
        # ).string_value            



        # self.download_function_code = aws_lambda.DockerImageCode.from_image_asset(
        #         get_root_path().as_posix(),
        #         file="packages/crimsonking-cdk/dockerfiles/crimsonking-download-lambda.Dockerfile",
        #         exclude=[
        #             "cdk.out",
        #             "**/cdk.out",
        #             ".git",
        #         ],
        #         cmd=["crimsonking_downloader.interface.aws.lambda.lambdahandler.handler"],
        #         platform=Platform.LINUX_ARM64 if in_prod else Platform.LINUX_AMD64
        #     )
        
        # self.download_function_main = aws_lambda.DockerImageFunction(
        #         self,
        #         "DownloadFunctionMain",
        #         code=self.download_function_code,
        #         role=self.lambda_role,
        #         timeout=Duration.minutes(15) if in_prod else Duration.minutes(10),
        #         logging_format=aws_lambda.LoggingFormat.JSON,
        #         environment=dict(             
        #             BROWSER_ACCEPT_LANGUAGE = "zh-CN,zh;q=0.9",
        #             BROWSER_SEC_CH_UA = '"Google Chrome";v="141", "Chromium";v="141", "Not/A)Brand";v="24"',
        #             BROWSER_SEC_CH_UA_PLATFORM = "Windows",
        #             BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",                    
        #             CRIMSONKING_EXPORT_BUCKET = data_bucket_name,
        #             CRIMSONKING_EXPORT_PREFIX = "OUTBOX/crimsonking/incountry",
        #             CRIMSONKING_WARM_URL = "https://x.cnki.net/knavi/",                    

        #             # BROWSER_KWARGS=
        #             # '''
        #             #     {
        #             #         "accept-language":"zh-CN,zh;q=0.9",
        #             #         'sec-ch-ua'  : '"Google Chrome";v="138", "Chromium";v="138", "Not/A)Brand";v="24"',
        #             #         'sec-ch-ua-platform' : "Windows",
        #             #         "user_agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",                        
        #             #     }
        #             # '''
      
        #         ),
        #         memory_size=3008,
        #         architecture=aws_lambda.Architecture.ARM_64 if in_prod else aws_lambda.Architecture.X86_64
        #     )
        # download_function_main_version = self.download_function_main.current_version  
        # self.download_function_main_alias = aws_lambda.Alias(self,
        #                                     "CrimsonkingDownloadFunctionMainAlias",
        #                                     alias_name="crimsonking-download-function-main",
        #                                     version=download_function_main_version)           
        # dynamodb_crimson_queue_arn = Fn.import_value("dynamodb-crimsonking-stream-queue-arn")   
        # dynamodb_crimson_queue = aws_sqs.Queue.from_queue_arn(self,"DynamodbCrimsonKingQueue",dynamodb_crimson_queue_arn)  
        # dynamodb_crimson_queue.grant_consume_messages(self.download_function_main)
        # self.download_function_main.add_event_source(aws_lambda_event_sources.SqsEventSource(dynamodb_crimson_queue,
        #                                                                                      batch_size=5,
        #                                                                                      max_concurrency=2,
        #                                                                                      report_batch_item_failures=True))