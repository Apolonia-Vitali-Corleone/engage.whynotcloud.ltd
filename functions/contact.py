import os, json, time, uuid, boto3

TABLE = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        name = (body.get("name") or "").strip()
        msg = (body.get("message") or "").strip()
        email = (body.get("email") or "").strip().lower()
        if not msg:
            return {"statusCode": 400, "body": json.dumps({"error": "message required"})}
        item = {
            "pk": "tenant#default",
            "sk": f"msg#{uuid.uuid4()}",
            "type": "contact",
            "name": name,
            "email": email,
            "message": msg,
            "created_at": int(time.time())
        }
        TABLE.put_item(Item=item)
        return {"statusCode": 200, "body": json.dumps({"ok": True})}
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
