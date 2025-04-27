#!/bin/bash

# 환경 변수 로드
if [ -f .env ]; then
    source .env
else
    echo "Error: .env file not found"
    exit 1
fi

# 타임스탬프를 변수에 저장
TAG=$(date +%Y%m%d%H%M%S)

# 변수로 이미지 빌드 및 푸시
docker build -t ${DOCKER_USERNAME}/mermaid_renderer:${TAG} .
docker push ${DOCKER_USERNAME}/mermaid_renderer:${TAG}

# Cloud Run에 배포
gcloud run deploy ${CLOUD_RUN_SERVICE_NAME} \
  --image docker.io/${DOCKER_USERNAME}/mermaid_renderer:${TAG} \
  --platform managed \
  --region ${CLOUD_RUN_REGION} \
  --allow-unauthenticated

