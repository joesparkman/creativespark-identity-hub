import json
import boto3
import os
import base64
import traceback

# Initialize AWS services
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')

# Configuration fetched from Environment Variables (set these in AWS Lambda console)
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'creativespark-onboarding-users')
AUTH_TOKEN = os.environ.get('AUTH_TOKEN')
VERIFY_WORKER_FUNCTION = os.environ.get('VERIFY_WORKER_FUNCTION')

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization"
}

def lambda_handler(event, context):
    """
    CreativeSpark Upload & Status Subservice: Secure Production Edition
    """
    # 1. HTTP Method Extraction
    http_method = (
        event.get('httpMethod') or 
        event.get('requestContext', {}).get('http', {}).get('method') or 
        ""
    ).upper()

    if http_method == 'OPTIONS':
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        # 2. Payload Parsing
        body = {}
        if isinstance(event, dict):
            raw_body = event.get('body', '{}')
            body = json.loads(raw_body) if isinstance(raw_body, str) else raw_body
        
        action = body.get('action', 'UPLOAD')
        session_token = body.get('session_token')
        user_id = body.get('user_id')

        # 3. Security Authorization
        if session_token != AUTH_TOKEN:
            return {
                "statusCode": 401,
                "headers": CORS_HEADERS,
                "body": json.dumps({"status": "Error", "message": "Unauthorized access."})
            }

        # 4. Route A: Fetch Status
        if action == 'STATUS':
            table = dynamodb.Table(DYNAMODB_TABLE_NAME)
            response = table.get_item(Key={'UserId': user_id})
            item = response.get('Item', {})
            
            return {
                "statusCode": 200,
                "headers": CORS_HEADERS,
                "body": json.dumps({
                    "status": item.get('VerificationStatus', 'PENDING'),
                    "verified": (item.get('VerificationStatus') == 'VERIFIED'),
                    "similarity": f"{item.get('SimilarityScore', '0.0')}%"
                })
            }

        # 5. Route B & C: Upload Handlers
        target_key = f"unzipped/{user_id}_{'id' if action == 'UPLOAD_ID' else 'selfie'}.png"
        image_data = body.get('id_image_base64' if action == 'UPLOAD_ID' else 'selfie_image_base64')
        
        if image_data:
            if "," in image_data:
                image_data = image_data.split(",")[1]
            image_data = image_data.strip().replace(" ", "+")
            image_bytes = base64.b64decode(image_data + "=" * ((4 - len(image_data) % 4) % 4), validate=False)
            
            s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=target_key, Body=image_bytes, ContentType='image/png')
            
            # Async Handoff for Selfie Route
            if action != 'UPLOAD_ID':
                lambda_client.invoke(
                    FunctionName=VERIFY_WORKER_FUNCTION,
                    InvocationType='Event',
                    Payload=json.dumps({"user_id": user_id, "id_key": f"unzipped/{user_id}_id.png", "selfie_key": target_key})
                )

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"status": "Success", "message": "Asset vaulted successfully."})
        }
            
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"status": "Error", "message": str(e)})
        }