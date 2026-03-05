from __future__ import annotations
from fury_cdk.stacks.fury_stack import FuryHealthStatusStack
# from fury_cdk.stacks.fury_alert import FuryHealthAlertStack
# __all__ = ["FuryHealthStatusStack","FuryHealthAlertStack"]
try:
    from fury_cdk.stacks.fury_alert import FuryHealthAlertStack
    __all__ = ["FuryHealthStatusStack","FuryHealthAlertStack"]
except:
    __all__ = ["FuryHealthStatusStack"]