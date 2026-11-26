"""ShopEase order worker (Module 5: SQS and SNS).

The API puts a message on an SQS queue for every new order (when ORDER_QUEUE_URL is set).
This worker reads those messages, "processes" each order, and sends a notification
through SNS (when ORDER_TOPIC_ARN is set), for example an email to the shop team.

Run it:  ORDER_QUEUE_URL=... ORDER_TOPIC_ARN=... AWS_REGION=ap-south-1 python worker/order_worker.py
"""
import json
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("order-worker")


def process_message(body, sns=None, topic_arn=""):
    """Handle one order message. Raises an error if the message is broken."""
    order = json.loads(body)
    order_id, email, total = order["order_id"], order["email"], order["total"]
    log.info("processing order %s for %s (Rs %s)", order_id, email, total)
    if sns and topic_arn:
        sns.publish(
            TopicArn=topic_arn,
            Subject=f"ShopEase: new order #{order_id}",
            Message=f"New order #{order_id} from {email}, total Rs {total}. Please pack and ship it.",
        )
        log.info("order %s: notification sent via SNS", order_id)
    return order_id


def main():
    import boto3
    queue_url = os.environ["ORDER_QUEUE_URL"]
    topic_arn = os.getenv("ORDER_TOPIC_ARN", "")
    region = os.getenv("AWS_REGION", "ap-south-1")
    sqs = boto3.client("sqs", region_name=region)
    sns = boto3.client("sns", region_name=region) if topic_arn else None
    log.info("waiting for orders on %s", queue_url)
    while True:
        response = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=20)
        for message in response.get("Messages", []):
            try:
                process_message(message["Body"], sns, topic_arn)
                sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])
            except Exception:  # noqa: BLE001
                # not deleted: SQS shows it again later, and after too many tries moves it to the dead-letter queue
                log.exception("could not process message %s", message.get("MessageId"))


if __name__ == "__main__":
    main()
