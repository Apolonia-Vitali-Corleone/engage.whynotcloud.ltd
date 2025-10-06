import os, json, boto3
from boto3.dynamodb.conditions import Key

TABLE = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

def handler(event, context):
    # very basic metrics: counts (subscribe, contact) in last N items
    # In real use, you'd maintain aggregates or query by time via GSI
    # For demo simplicity, just scan a small page
    try:
        resp = TABLE.scan(Limit=50)
        items = resp.get("Items", [])
        subs = sum(1 for it in items if it.get("type") == "subscribe")
        msgs = sum(1 for it in items if it.get("type") == "contact")
        return {"statusCode": 200, "body": json.dumps({"subscribe_count_sample": subs, "contact_count_sample": msgs})}
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
