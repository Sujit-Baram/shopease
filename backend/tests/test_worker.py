"""Tests for the order worker, using a fake SNS client (no AWS account needed)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "worker"))
from order_worker import process_message  # noqa: E402


class FakeSNS:
    def __init__(self):
        self.sent = []

    def publish(self, **kwargs):
        self.sent.append(kwargs)


def test_process_message_sends_notification():
    sns = FakeSNS()
    body = json.dumps({"order_id": 7, "email": "asha@example.com", "total": 2499})
    assert process_message(body, sns, "arn:aws:sns:ap-south-1:123456789012:shopease-orders") == 7
    assert sns.sent[0]["Subject"] == "ShopEase: new order #7"
    assert "Rs 2499" in sns.sent[0]["Message"]


def test_broken_message_raises():
    with pytest.raises(Exception):
        process_message("not json")
