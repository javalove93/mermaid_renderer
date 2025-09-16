#!/bin/bash

SERVICE_NAME=mermaid-renderer
REGION=asia-northeast3
PROJECT_ID=$(gcloud config get-value project)

echo "Fetching logs for Cloud Run service: ${SERVICE_NAME} in region: ${REGION}"

gcloud beta run services logs tail ${SERVICE_NAME} --project=${PROJECT_ID} --region=${REGION}