import json
import boto3
import os
import traceback
import logging

# Initialize logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

rekognition = boto3.client('rekognition')
dynamodb = boto3.resource('dynamodb')

DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

def update_verification_ledger(user_id, status, similarity):
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    table.put_item(
        Item={
            'UserId': user_id,
            'VerificationStatus': status,
            'status': 'PROCESSED' if status == 'VERIFIED' else 'FAILED',
            'verified': True if status == 'VERIFIED' else False,
            'SimilarityScore': similarity
        }
    )
    logger.info(f"Database sync complete for {user_id}. Status: {status}")

def lambda_handler(event, context):
    # ADDED THIS: This confirms if the new code is actually running
    logger.info("--- VERIFY WORKER V2 STARTED ---")
    logger.info(f"Processing verification for event: {json.dumps(event)}")
    
    try:
        user_id = event.get('user_id', 'unknown-client')
        bucket_name = S3_BUCKET_NAME 
        id_key = event.get('id_key', f"unzipped/{user_id}_id.png")
        selfie_key = event.get('selfie_key', f"unzipped/{user_id}_selfie.png")
        
        rek_response = rekognition.compare_faces(
            SourceImage={'S3Object': {'Bucket': bucket_name, 'Name': id_key}},
            TargetImage={'S3Object': {'Bucket': bucket_name, 'Name': selfie_key}},
            SimilarityThreshold=70.0 
        )
        
        # DEBUG LOG: This will print the raw data to logs
        logger.info(f"Full Rekognition Response: {json.dumps(rek_response)}")
        
        face_matches = rek_response.get('FaceMatches', [])
        
        if face_matches:
            # FIXED: Changed 'similarity' to 'Similarity' (capital S)
            similarity_score = face_matches[0]['Similarity']
            logger.info(f"Biometric Match Established! Confidence: {similarity_score}%")
            update_verification_ledger(user_id, "VERIFIED", f"{similarity_score:.2f}")
            return {"status": "SUCCESS"}
        else:
            logger.warning("Biometric Verification Violation: No matches found.")
            update_verification_ledger(user_id, "REJECTED", "0.0")
            return {"status": "REJECTED"}
            
    except Exception as e:
        logger.error(f"Fatal Verification runtime crash:\n{traceback.format_exc()}")
        return {"status": "ERROR", "message": str(e)}