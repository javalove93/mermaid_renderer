import os
import requests
import json
from flask import Flask, request, jsonify, render_template, send_from_directory, make_response, send_file
import base64
from google.cloud import storage
from convert_to_docs import MarkdownToDocxConverter # MarkdownToDocxConverter 임포트
from google import genai
from PIL import Image
import io
from dotenv import load_dotenv

load_dotenv() # .env 파일 로드

app = Flask(__name__, 
    template_folder='templates',
    static_folder='static',
    static_url_path='/static'
)

# CORS 헤더 설정을 위한 데코레이터
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    # 캐시 관련 헤더 추가
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# 정적 파일 서빙을 위한 라우트 추가
@app.route('/static/<path:filename>')
def serve_static(filename):
    response = make_response(send_from_directory('static', filename))
    response.headers['Content-Type'] = 'text/css' if filename.endswith('.css') else 'application/octet-stream'
    return response

# GitHub Personal Access Token (set as environment variable)
# GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GIST_API_URL = 'https://api.github.com/gists'

@app.route('/')
def index():
    """Serves the main HTML page."""
    gist_id = request.args.get('gist_id')
    if gist_id:
        return render_template('index.html', gist_id=gist_id)
    return render_template('index.html')

@app.route('/markdown')
def markdown_editor():
    """Serves the markdown editor HTML page."""
    return render_template('markdown_editor.html')

@app.route('/get-gist/<gist_id>', methods=['GET'])
def get_gist(gist_id):
    """Fetches Mermaid code from a GitHub Gist."""
    try:
        response = requests.get(f'{GIST_API_URL}/{gist_id}')
        response.raise_for_status()
        
        gist_data = response.json()
        files = gist_data.get('files', {})
        
        # Find the first .mermaid file
        mermaid_file = next((file_data for file_data in files.values() 
                           if file_data.get('filename', '').endswith('.mermaid')), None)
        
        if not mermaid_file:
            return jsonify({'error': 'No Mermaid file found in the Gist'}), 404
            
        content = mermaid_file.get('content', '')
        return jsonify({'mermaid_code': content})
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to fetch Gist: {str(e)}'}), 500

@app.route('/save-gist', methods=['POST'])
def save_gist():
    """Receives Mermaid code and saves it as a GitHub Gist."""
    # if not GITHUB_TOKEN:
    #     return jsonify({'error': 'GitHub token not configured on the server.'}), 500

    data = request.get_json()
    mermaid_code = data.get('mermaid_code')
    github_token = data.get('github_token') # Get token from request body
    description = data.get('description', 'Mermaid diagram created by Mermaid Renderer') # Optional description
    filename = data.get('filename', 'diagram.mermaid') # Optional filename

    if not github_token:
        return jsonify({'error': 'GitHub token is missing in the request.'}), 400
    if not mermaid_code:
        return jsonify({'error': 'Mermaid code is missing.'}), 400

    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json',
    }
    payload = {
        'description': description,
        'public': True,  # Create a public gist
        'files': {
            filename: {
                'content': mermaid_code
            }
        }
    }

    try:
        response = requests.post(GIST_API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        gist_data = response.json()
        gist_id = gist_data.get('id')
        
        # Return the renderer URL with the Gist ID
        render_url = f"{request.host_url}?gist_id={gist_id}"
        return jsonify({'render_url': render_url})

    except requests.exceptions.RequestException as e:
        # response 객체가 로컬 변수에 있는지, None이 아닌지 확인
        status_code = 500
        error_message = f'GitHub API request failed: {e}'
        raw_response_text = None # 원시 응답 텍스트 저장용

        if 'response' in locals() and response is not None:
            status_code = response.status_code # 실제 GitHub 응답 코드 사용 시도
            raw_response_text = response.text # 디버깅을 위해 원시 텍스트 저장
            try:
                # GitHub의 에러 메시지를 파싱 시도
                error_details = response.json()
                error_message += f" (Status: {status_code}). Details: {error_details.get('message', 'No details provided.')}"
            except ValueError: # JSON 파싱 실패 시
                error_message += f" (Status: {status_code}). Could not parse GitHub error response."
                print(f"Raw GitHub error response (status {status_code}): {raw_response_text}") # 로그에 원시 응답 기록
        else:
             error_message += " (No response object from GitHub API call available)"

        print(f"Gist creation error: {error_message}")
        # 클라이언트에게는 status_code와 에러 메시지를 JSON으로 반환
        return jsonify({'error': error_message}), status_code # GitHub 에러 코드를 최대한 반영

    except Exception as e:
        # 기타 예상치 못한 모든 에러 처리
        import traceback
        print(f"Unexpected error during Gist creation: {traceback.format_exc()}") # 전체 트레이스백 로그 기록
        return jsonify({'error': 'An unexpected server error occurred during Gist creation.'}), 500

# this function intentionally use apikey parameter. never remove this code.
@app.route('/chat-with-diagram', methods=['POST'])
def chat_with_diagram():
    """다이어그램에 대해 Gemini와 대화하는 엔드포인트"""
    data = request.get_json()
    # this function intentionally use apikey parameter. never remove this code or never get a key from server.
    api_key = data.get('api_key')
    diagram = data.get('diagram')
    question = data.get('question')

    if not all([api_key, diagram, question]):
        return jsonify({'error': '필수 파라미터가 누락되었습니다.'}), 400

    # Gemini API 엔드포인트
    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    # 프롬프트 구성
    prompt = f"""다음은 Mermaid 다이어그램입니다:

```mermaid
{diagram}
```

이 다이어그램에 대한 질문에 답변해주세요. 다이어그램의 구조와 내용을 기반으로 상세히 설명해주세요.

질문: {question}

응답 형식:
1. 다이어그램의 관련 부분을 구체적으로 언급하면서 답변해주세요.
2. 노드나 연결 관계를 구체적으로 설명할 때는 정확한 이름을 인용해주세요.
3. 한국어로 자연스럽게 답변해주세요."""

    try:
        response = requests.post(
            API_URL,
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{
                    'parts': [{'text': prompt}]
                }]
            }
        )

        if not response.ok:
            return jsonify({'error': f'Gemini API 오류: {response.status_code}'}), response.status_code

        data = response.json()
        if data.get('candidates') and data['candidates'][0].get('content'):
            answer = data['candidates'][0]['content']['parts'][0]['text']
            return jsonify({'answer': answer})
        else:
            return jsonify({'error': 'Gemini API로부터 유효한 응답을 받지 못했습니다.'}), 500

    except Exception as e:
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500



@app.route('/convert-markdown-to-docx', methods=['POST'])
def convert_markdown_to_docx_route():
    """마크다운을 DOCX로 변환하여 반환하는 엔드포인트"""
    data = request.get_json()
    markdown_text = data.get('markdown_text')
    save_images_to_disk = data.get('save_images_to_disk', False)

    if not markdown_text:
        return jsonify({'error': '마크다운 텍스트가 필요합니다.'}), 400

    try:
        converter = MarkdownToDocxConverter()
        # output_path=None으로 설정하여 BytesIO 객체를 반환받음
        docx_buffer = converter.convert_markdown_to_docx(markdown_text, output_path=None, save_images_to_disk=save_images_to_disk)

        if docx_buffer:
            return send_file(
                docx_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                as_attachment=True,
                download_name='document.docx'
            )
        else:
            return jsonify({'error': 'DOCX 변환에 실패했습니다.'}), 500

    except Exception as e:
        import traceback
        print(f"Markdown to DOCX 변환 중 오류 발생: {traceback.format_exc()}")
        return jsonify({'error': f'서버 오류 발생: {str(e)}'}), 500

if __name__ == '__main__':
    # Cloud Run이 제공하는 PORT 환경 변수 사용, 없으면 5000번 기본 사용
    port = int(os.environ.get("PORT", 5000))
    # 개발 서버 대신 프로덕션용 WSGI 서버(예: gunicorn) 사용을 권장하지만,
    # 여기서는 Flask 개발 서버를 PORT 변수에 맞춰 실행합니다.
    # Gunicorn 등을 사용하려면 Dockerfile의 CMD도 수정해야 합니다.
    app.run(host='0.0.0.0', port=port)
