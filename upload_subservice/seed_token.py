import os
import redis

# Grab your live cloud host from your environment setup
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
# Fetch sensitive data from environment variables
AUTH_TOKEN = os.environ.get('AUTH_TOKEN')
USER_DATA = os.environ.get('USER_IDENTITY_DATA', 'default_user')

# Ensure we have the necessary config to proceed
if not AUTH_TOKEN:
    print("❌ Error: AUTH_TOKEN must be set in your environment.")
    exit(1)

print(f"📡 Connecting to Redis cluster at {REDIS_HOST}...")

# Open the secure TLS handshake path
if REDIS_HOST == 'localhost':
    redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
else:
    redis_client = redis.Redis(
        host=REDIS_HOST, 
        port=6379, 
        decode_responses=True, 
        ssl=True, 
        ssl_cert_reqs=None
    )

# Set the key in Redis to expire in 3600 seconds (1 hour)
redis_client.set(AUTH_TOKEN, USER_DATA, ex=3600)

print(f"✅ Successfully seeded token for user: {USER_DATA}")
print(f"⏱️ Token is live in the cloud vault for 60 minutes.")