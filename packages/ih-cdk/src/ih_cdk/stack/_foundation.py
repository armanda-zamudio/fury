import typing

import aws_cdk
from constructs import Construct

from ih.util.types import copy_method_signature


class FoundationStack(aws_cdk.Stack):
    @copy_method_signature(aws_cdk.Stack.__init__)
    def __init__(
        self,
        scope: typing.Optional[Construct] = None,
        id: typing.Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)
        self.create_table()
        self.events_table_stream_arn = self.events_table.table_stream_arn
        self.events_table_stream_arn_export_name = (
            self.stack_id + "EventsTableStreamArn"
        )
        aws_cdk.CfnOutput(
            self,
            "EventsTableStreamArnOutput",
            value=self.events_table.table_stream_arn,
            export_name=self.events_table_stream_arn_export_name,
        )

    def create_table(self):
        from aws_cdk.aws_dynamodb import (
            Attribute,
            AttributeType,
            BillingMode,
            StreamViewType,
            Table,
        )
        # self.events_table = Table(
        #     self,
        #     "EventsDynamoDBTable",
        #     stream=StreamViewType.NEW_IMAGES,
        #     partition_key=Attribute(name="PK", type=AttributeType.NUMBER),
        #     sort_key=Attribute(name="SK", type=AttributeType.NUMBER),
        #     billing_mode=BillingMode.PAY_PER_REQUEST,
        # )
        # self.events_table.add_global_secondary_index(
        #     sort_key=Attribute(name="global_id", type=AttributeType.STRING),
        #     partition_key=Attribute(name="PK", type=AttributeType.STRING),
        # )

        self.events_table = Table(
            self,
            "EventsDynamoDBTable",
            stream=StreamViewType.NEW_IMAGE,
            partition_key=Attribute(name="id", type=AttributeType.STRING),
            sort_key=Attribute(name="version", type=AttributeType.NUMBER),
            billing_mode=BillingMode.PAY_PER_REQUEST,
        )
        self.events_table.add_global_secondary_index(
            partition_key=Attribute(name="global_id", type=AttributeType.NUMBER),
        )
