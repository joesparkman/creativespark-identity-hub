import json
import boto3
import os
import logging
import traceback

logger = logging.getLogger()
logger.setLevel(logging.INFO)

rekognition = boto3.client('rekognition')
dynamodb = boto3.resource('dynamodb')

DYNAMODB_TABLE_NAME = os.environ['DYNAMODB_TABLE_NAME']
S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']

def update_verification_ledger(user_id: str, status: str, similarity: str):
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    table.put_item(Item={
        'UserId': user_id,
        'VerificationStatus': status,
        'status': 'PROCESSED' if status == 'VERIFIED' else 'FAILED',
        'verified': status == 'VERIFIED',
        'SimilarityScore': similarity
    })  # <-- closing paren was missing in original
    logger.info(f"Ledger updated for {user_id}: {status}")

def lambda_handler(event, context):
    logger.info("--- VERIFY WORKER V2 STARTED ---")
    logger.info(f"Event: {json.dumps(event)}")

    try:
        user_id = event.get('user_id', 'unknown')
        id_key = event.get('id_key', f"unzipped/{user_id}_id.png")
        selfie_key = event.get('selfie_key', f"unzipped/{user_id}_selfie.png")

        rek_response = rekognition.compare_faces(
            SourceImage={'S3Object': {'Bucket': S3_BUCKET_NAME, 'Name': id_key}},
            TargetImage={'S3Object': {'Bucket': S3_BUCKET_NAME, 'Name': selfie_key}},
            SimilarityThreshold=70.0
        )  # <-- closing paren was missing in original

        logger.info(f"Rekognition response: {json.dumps(rek_response)}")
        face_matches = rek_response.get('FaceMatches', [])

        if face_matches:
            similarity_score = face_matches[0]['Similarity']
            logger.info(f"Match found! Confidence: {similarity_score:.2f}%")
            update_verification_ledger(user_id, "VERIFIED", f"{similarity_score:.2f}")
            return {"status": "SUCCESS", "similarity": similarity_score}
        else:
            logger.warning("No face match found.")
            update_verification_ledger(user_id, "REJECTED", "0.0")
            return {"status": "REJECTED"}

    except Exception as e:
        logger.error(f"Verify worker crash:\n{traceback.format_exc()}")
        return {"status": "ERROR", "message": str(e)}