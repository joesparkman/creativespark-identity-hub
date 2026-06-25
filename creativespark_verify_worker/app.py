import json
import boto3
import os
import traceback
import logging

# Initialize logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS services (Inherits region from Lambda environment)
rekognition = boto3.client('rekognition')
dynamodb = boto3.resource('dynamodb')

# Fetch configuration from Environment Variables
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

def update_verification_ledger(user_id, status, similarity):
    """Updates the DynamoDB table with the biometric result."""
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
    logger.info("Database records synchronized successfully.")

def lambda_handler(event, context):
    """
    Worker Service: Performs biometric face comparison.
    """
    logger.info(f"Processing verification for event: {json.dumps(event)}")
    
    try:
        # 1. Parse Input
        user_id = event.get('user_id', 'unknown-client')
        bucket_name = S3_BUCKET_NAME 
        id_key = event.get('id_key', f"unzipped/{user_id}_id.png")
        selfie_key = event.get('selfie_key', f"unzipped/{user_id}_selfie.png")
        
        # 2. Perform Biometric Comparison
        try:
            rek_response = rekognition.compare_faces(
                SourceImage={'S3Object': {'Bucket': bucket_name, 'Name': id_key}},
                TargetImage={'S3Object': {'Bucket': bucket_name, 'Name': selfie_key}},
                SimilarityThreshold=80.0
            )
        except rekognition.exceptions.InvalidParameterException as rek_err:
            logger.error(f"Face detection failed: {str(rek_err)}")
            update_verification_ledger(user_id, "FAILED_NO_FACE", "0.0")
            return {"status": "FAILED", "message": "No recognizable faces found."}
        except Exception as file_err:
            logger.error(f"S3/Rekognition Access Failure: {str(file_err)}")
            update_verification_ledger(user_id, "FAILED", "0.0")
            return {"status": "FAILED", "message": "Required files could not be retrieved."}

        # 3. Handle Results
        face_matches = rek_response.get('FaceMatches', [])
        if face_matches:
            similarity_score = face_matches[0]['Similarity']
            logger.info(f"Biometric Match Established! Confidence: {similarity_score}%")
            update_verification_ledger(user_id, "VERIFIED", f"{similarity_score:.2f}")
            return {"status": "SUCCESS"}
        else:
            logger.warning("Biometric Verification Violation: Features do not match.")
            update_verification_ledger(user_id, "REJECTED", "0.0")
            return {"status": "REJECTED"}
            
    except Exception as e:
        logger.error(f"Fatal Verification runtime crash:\n{traceback.format_exc()}")
        return {"status": "ERROR", "message": str(e)}