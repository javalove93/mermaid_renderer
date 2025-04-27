# Mermaid Renderer

Mermaid 다이어그램을 렌더링하고 공유할 수 있는 웹 애플리케이션입니다. Google의 Gemini AI를 활용하여 다이어그램 분석과 질문 응답이 가능합니다.

Vibe Coding: Gemini Canvas와 Cursor + Gemini를 써서 만들었습니다.

## 주요 기능

- Mermaid 다이어그램 실시간 렌더링
- GitHub Gist를 통한 다이어그램 저장 및 공유
- Gemini AI를 활용한 다이어그램 분석
- 다이어그램 PNG 이미지 다운로드
- 문법 검사 및 자동 수정 제안

## 기술 스택

- Backend: Python Flask
- Frontend: HTML, JavaScript, Tailwind CSS
- AI: Google Gemini API
- 배포: Docker, Google Cloud Run
- 저장소: GitHub Gist API

## 개발 환경 설정

1. 필수 요구사항:
   - Python 3.9+
   - Node.js 및 npm
   - Docker
   - Google Cloud SDK

2. 프로젝트 클론:
   ```bash
   git clone [repository-url]
   cd mermaid_renderer
   ```

3. Python 가상환경 설정:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. Node.js 패키지 설치:
   ```bash
   npm install
   ```

## CSS 관리

프로젝트는 Tailwind CSS를 사용합니다. CSS 파일 관리는 다음과 같이 진행됩니다:

1. CSS 소스 파일:
   - `static/css/input.css`: Tailwind 지시어가 포함된 소스 파일
   - `static/css/output.css`: 빌드된 최종 CSS 파일

2. CSS 빌드:
   ```bash
   ./build_css.sh
   ```
   - CSS 수정이 필요할 때만 실행
   - 빌드된 `output.css`는 Git에 포함되어 있어 일반적인 경우 재빌드 불필요

## 배포 프로세스

1. 수동 배포:
   ```bash
   ./deploy.sh
   ```
   - Docker 이미지 빌드 및 푸시
   - Google Cloud Run에 배포

2. 자동 배포 (파일 변경 감지):
   ```bash
   ./run_cicd.sh
   ```
   - 주요 파일 변경 시 자동으로 배포 실행
   - 감지 대상: Dockerfile, app.py, requirements.txt, templates/, static/
   - 여러 파일이 연속으로 변경될 경우 마지막 변경 후 1회만 배포

## API 키 설정

1. Gemini API Key:
   - [Google AI Studio](https://aistudio.google.com/app/apikey)에서 발급
   - 웹 인터페이스에서 입력하여 사용

2. GitHub Token (Gist 저장용):
   - [GitHub Token 설정](https://github.com/settings/tokens?type=beta)에서 발급
   - 'gist' 스코프 필요
   - 웹 인터페이스에서 입력하여 사용

## 주의사항

- API 키는 클라이언트 측에서만 사용되며, 서버에 저장되지 않습니다.
- GitHub Token은 Gist 생성 시에만 서버로 전송됩니다.
- CSS 수정이 필요한 경우 `build_css.sh`를 실행하여 빌드 후 커밋하세요.
- `deploy.sh`는 CSS 빌드를 포함하지 않으며, 순수하게 배포만 진행합니다. 