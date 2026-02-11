#!/bin/bash
# Deploy backend to Google Cloud Run.
# Single service serves both API and worker endpoints.
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - Cloud Tasks queue created: gcloud tasks queues create background-tasks --location=us-central1
#   - Service account has: Vertex AI, Cloud Storage, Cloud Tasks, Firestore roles

set -e

PROJECT_ID="${GCP_PROJECT:-qhacks-486618}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="qhacks-backend"
IMAGE="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "Building and pushing Docker image..."
cd "$(dirname "$0")/.."
gcloud builds submit --tag "$IMAGE" --project "$PROJECT_ID"

echo "Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --platform managed \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --timeout 300

SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.url)')

echo ""
echo "Deployed to: $SERVICE_URL"
echo ""
echo "IMPORTANT: Now set WORKER_SERVICE_URL on the Cloud Run service:"
echo "  gcloud run services update $SERVICE_NAME \\"
echo "    --region=$REGION \\"
echo "    --update-env-vars WORKER_SERVICE_URL=$SERVICE_URL"
echo ""
echo "This makes Cloud Tasks call back to the same service for video generation."
