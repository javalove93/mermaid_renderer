#!/bin/bash

# 스크립트가 실행 중인지 확인하는 파일
LOCK_FILE="/tmp/mermaid_renderer_cicd.lock"

# 스크립트가 이미 실행 중이면 종료
if [ -f "$LOCK_FILE" ]; then
    echo "CI/CD 스크립트가 이미 실행 중입니다."
    exit 0
fi

# 락 파일 생성
touch "$LOCK_FILE"

# 스크립트 종료 시 락 파일 삭제
trap 'rm -f "$LOCK_FILE"; exit' EXIT

# 변경 감지 후 대기 시간 (초)
WAIT_TIME=10

echo "Mermaid Renderer CI/CD 시작 - 파일 변경 감지 중..."

# 배포 관련 파일이 변경되었는지 확인하는 함수
is_deployment_related() {
    local file="$1"
    
    # 배포와 관련된 파일 패턴들
    local patterns=(
        "Dockerfile"
        "app.py"
        "requirements.txt"
        "^templates/.*\.html$"
        "^static/.*\.(css|js)$"
    )
    
    # 각 패턴에 대해 확인
    for pattern in "${patterns[@]}"; do
        if echo "$file" | grep -qE "$pattern"; then
            return 0  # 매치되면 true (0)
        fi
    done
    
    return 1  # 매치되지 않으면 false (1)
}

# inotifywait를 사용하여 파일 변경 감지
inotifywait -m -r -e modify,create,delete "." --exclude '\.git|\.idea|__pycache__|node_modules|\.DS_Store' |
while read -r directory event file; do
    # 전체 파일 경로 구성
    filepath="${directory}${file}"
    
    # 배포 관련 파일이 아니면 건너뛰기
    if ! is_deployment_related "$filepath"; then
        echo "무시된 파일 변경: $filepath"
        continue
    fi

    echo "배포 관련 파일 변경 감지: $filepath ($event)"
    echo "$WAIT_TIME초 동안 추가 변경을 기다립니다..."
    
    # 대기 중에 추가 변경이 있었는지 확인하는 플래그
    additional_changes=false
    
    # $WAIT_TIME 초 동안 추가 변경을 감지
    for ((i=0; i<$WAIT_TIME; i++)); do
        if read -t 1 -r next_dir next_event next_file; then
            # 추가 변경된 파일이 배포 관련 파일인지 확인
            if is_deployment_related "${next_dir}${next_file}"; then
                additional_changes=true
                echo "추가 배포 관련 파일 변경 감지: ${next_dir}${next_file}"
            fi
            # 추가 변경을 계속 읽어들임
            while read -t 0.1 -r _; do
                :
            done
        fi
        sleep 1
    done
    
    if [ "$additional_changes" = true ]; then
        echo "추가 변경이 감지되었습니다. 모든 변경이 완료된 후 배포를 시작합니다."
    fi
    
    echo "재배포 시작..."
    ./deploy.sh
    echo "재배포 완료"
done 