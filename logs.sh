#!/bin/bash

source .env

SERVICE_NAME=${CLOUD_RUN_SERVICE_NAME}
REGION=${CLOUD_RUN_REGION}
PROJECT_ID=$(gcloud config get-value project)

echo "Fetching logs for Cloud Run service: ${SERVICE_NAME} in region: ${REGION}"

gcloud beta run services logs tail ${SERVICE_NAME} --project=${PROJECT_ID} --region=${REGION}