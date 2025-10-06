import os, json, time, hashlib, uuid, boto3

TABLE = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        email = (body.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return {"statusCode": 400, "body": json.dumps({"error": "invalid email"})}

        idem_key = (event.get("headers") or {}).get("Idempotency-Key") or hashlib.sha256((email+str(int(time.time())//60)).encode()).hexdigest()

        item = {
            "pk": "tenant#default",
            "sk": f"sub#{email}",
            "type": "subscribe",
            "email": email,
            "idem": idem_key,
            "created_at": int(time.time())
        }
        TABLE.put_item(Item=item)
        return {"statusCode": 200, "body": json.dumps({"ok": True})}
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
