import json
import boto3
import os
import base64
import logging
import re

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')

S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']
DYNAMODB_TABLE_NAME = os.environ['DYNAMODB_TABLE_NAME']
VERIFY_WORKER_FUNCTION = os.environ['VERIFY_WORKER_FUNCTION']
AUTH_TOKEN_SECRET_ARN = os.environ['AUTH_TOKEN_SECRET_ARN']

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "https://app.joesparkman.com",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization"
}

VALID_ACTIONS = {"UPLOAD_ID", "UPLOAD", "STATUS"}

def get_auth_token():
    """Fetch auth token from Secrets Manager (cached per warm container)."""
    secret = secrets_client.get_secret_value(SecretId=AUTH_TOKEN_SECRET_ARN)
    return secret['SecretString']

def is_valid_user_id(user_id: str) -> bool:
    """Only allow alphanumeric, hyphens, underscores — prevents path traversal."""
    return bool(re.match(r'^[a-zA-Z0-9_\-]{3,64}$', user_id))

def build_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body)
    }

def lambda_handler(event, context):
    http_method = (
        event.get('httpMethod') or
        event.get('requestContext', {}).get('http', {}).get('method', '')
    ).upper()

    if http_method == 'OPTIONS':
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        raw_body = event.get('body', '{}')
        body = json.loads(raw_body) if isinstance(raw_body, str) else raw_body

        action = body.get('action', 'UPLOAD').upper()
        session_token = body.get('session_token')
        user_id = body.get('user_id')

        # --- Input Validation ---
        if action not in VALID_ACTIONS:
            return build_response(400, {"status": "Error", "message": "Invalid action."})

        if not user_id or not is_valid_user_id(user_id):
            return build_response(400, {"status": "Error", "message": "Invalid or missing user_id."})

        # --- Auth Check via Secrets Manager ---
        expected_token = get_auth_token()
        if session_token != expected_token:
            logger.warning(f"Unauthorized attempt for user_id: {user_id}")
            return build_response(401, {"status": "Error", "message": "Unauthorized."})

        # --- STATUS Route ---
        if action == 'STATUS':
            table = dynamodb.Table(DYNAMODB_TABLE_NAME)
            response = table.get_item(Key={'UserId': user_id})
            item = response.get('Item', {})
            return build_response(200, {
                "status": item.get('VerificationStatus', 'PENDING'),
                "verified": item.get('VerificationStatus') == 'VERIFIED',
                "similarity": f"{item.get('SimilarityScore', '0.0')}%"
            })

        # --- UPLOAD Route ---
        is_id_upload = action == 'UPLOAD_ID'
        image_field = 'id_image_base64' if is_id_upload else 'selfie_image_base64'
        target_key = f"unzipped/{user_id}_{'id' if is_id_upload else 'selfie'}.png"
        image_data = body.get(image_field)

        if not image_data:
            return build_response(400, {"status": "Error", "message": f"Missing field: {image_field}"})

        if "," in image_data:
            image_data = image_data.split(",")[1]
        image_data = image_data.strip().replace(" ", "+")
        padding = "=" * ((4 - len(image_data) % 4) % 4)
        image_bytes = base64.b64decode(image_data + padding, validate=False)

        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=target_key,
            Body=image_bytes,
            ContentType='image/png',
            ServerSideEncryption='AES256'
        )
        logger.info(f"Uploaded {target_key} to S3 for user {user_id}")

        if not is_id_upload:
            lambda_client.invoke(
                FunctionName=VERIFY_WORKER_FUNCTION,
                InvocationType='Event',
                Payload=json.dumps({
                    "user_id": user_id,
                    "id_key": f"unzipped/{user_id}_id.png",
                    "selfie_key": target_key
                })
            )
            logger.info(f"Async verify worker triggered for {user_id}")

        return build_response(200, {"status": "Success", "message": "Asset uploaded successfully."})

    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        return build_response(500, {"status": "Error", "message": "Internal server error."})