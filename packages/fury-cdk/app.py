#!/usr/bin/env python3
from __future__ import annotations
import os
import logging
import aws_cdk as cdk

from fury_cdk.stacks import FuryHealthStatusStack

# Configure Python's standard logging to output to the console
logging.basicConfig(
    level=logging.INFO,  # Change to logging.DEBUG for more verbose logs
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

app = cdk.App()
default_account = os.environ.get("CDK_DEFAULT_ACCOUNT")

_permissions_boundary = app.node.try_get_context("permission-boundary") or None 

FuryHealthStatusStack(app,"fury-stack", permissions_boundary_name=_permissions_boundary)

if _permissions_boundary:
    from fury_cdk.stacks import FuryHealthAlertStack
    _data_bucket = app.node.try_get_context("data-bucket") or None 
    FuryHealthAlertStack(app,"fury-stack-health", permissions_boundary_name=_permissions_boundary, data_bucket=_data_bucket)






app.synth()
