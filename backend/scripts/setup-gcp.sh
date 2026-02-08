#!/bin/bash
set -e

PROJECT_ID="qhacks-486618"
REGION="us-central1"
BUCKET_NAME="${PROJECT_ID}-storage"
QUEUE_NAME="background-tasks"

echo "Setting up GCP resources for project: $PROJECT_ID"
echo ""

echo "📋 Setting default project..."
gcloud config set project $PROJECT_ID

echo "🔌 Enabling required APIs..."
gcloud services enable \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  cloudtasks.googleapis.com

echo "Creating Cloud Storage bucket 🪣 ..."
gsutil mb -l $REGION gs://$BUCKET_NAME 2>/dev/null || echo "Bucket already exists"

echo "Creating Cloud Tasks queue..."
gcloud tasks queues create $QUEUE_NAME --location=$REGION 2>/dev/null || echo "Queue already exists"

echo "Creating service account..."
SERVICE_ACCOUNT_NAME="video-pipeline-worker"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
  --display-name="Video Pipeline Worker Service Account" 2>/dev/null || echo "Service account already exists"

echo "👤 Granting IAM roles..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/aiplatform.user" \
  --condition=None

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/storage.admin" \
  --condition=None

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/cloudtasks.enqueuer" \
  --condition=None

echo "💾 Downloading service account key..."
KEY_FILE="firebase-service-account.json"
gcloud iam service-accounts keys create $KEY_FILE \
  --iam-account=$SERVICE_ACCOUNT_EMAIL

echo ""
echo "✅ Setup complete... ✅ ✅ ✅ ✅ ✅ ✅ ✅ ✅ ✅ "
echo ""
echo "GOOGLE_CLOUD_PROJECT=$PROJECT_ID"
echo "GOOGLE_CLOUD_LOCATION=$REGION"
echo "GOOGLE_CLOUD_BUCKET_NAME=$BUCKET_NAME"
echo "GOOGLE_APPLICATION_CREDENTIALS=./$KEY_FILE"
echo "CLOUD_TASKS_QUEUE=$QUEUE_NAME"
echo "CLOUD_TASKS_LOCATION=$REGION"
echo "WORKER_SERVICE_URL=https://your-worker-service-url.run.app"
echo "FRONTEND_URL=http://localhost:5173"
