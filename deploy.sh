#!/bin/bash

# 타임스탬프를 변수에 저장
TAG=$(date +%Y%m%d%H%M%S)

# 변수로 이미지 빌드 및 푸시
docker build -t javalove93/mermaid_renderer:$TAG .
docker push javalove93/mermaid_renderer:$TAG

# Cloud Run에 배포
gcloud run deploy mermaid-renderer \
  --image docker.io/javalove93/mermaid_renderer:$TAG \
  --platform managed \
  --region asia-northeast3 \
  --allow-unauthenticated

