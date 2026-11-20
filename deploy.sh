#!/usr/bin/env bash
# Deploy to Cloud Run from the Antigravity terminal.  Usage:  GEMINI_API_KEY=xxx REVIEWER_PIN=yyy ./deploy.sh
set -euo pipefail
PROJECT="${GOOGLE_CLOUD_PROJECT:-claimback-515215}"
REGION="${REGION:-asia-south1}"
gcloud config set project "$PROJECT"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
ENVV="REVIEWER_PIN=${REVIEWER_PIN:-claimback}"
[ -n "${GEMINI_API_KEY:-}" ] && ENVV="$ENVV,GEMINI_API_KEY=$GEMINI_API_KEY"
# To use Vertex AI credits instead:  ENVV="$ENVV,USE_VERTEX=1,GOOGLE_CLOUD_PROJECT=$PROJECT"
# max-instances 1: cases live in this instance's temporary SQLite file, so one instance keeps them consistent.
gcloud run deploy claimback --source . --region "$REGION" --allow-unauthenticated \
  --max-instances 1 --min-instances 0 --memory 512Mi --set-env-vars "$ENVV"
gcloud run services describe claimback --region "$REGION" --format 'value(status.url)'
