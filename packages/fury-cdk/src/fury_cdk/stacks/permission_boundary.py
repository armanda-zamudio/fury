
from aws_cdk import (
    # Duration,
    Stack,
    aws_iam
)
from constructs import Construct

class FuryStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        permissions_boundary_name: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        if permissions_boundary_name:
            print(f"Using the following permission boundary: {permissions_boundary_name}")
            aws_iam.PermissionsBoundary.of(self).apply(
                aws_iam.ManagedPolicy.from_managed_policy_name(
                    self, "PermissionsBoundaryManagedPolicy", permissions_boundary_name
                )
            )