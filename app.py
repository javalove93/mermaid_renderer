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

@app.route('/english')
def english_word():
    """Serves the English word learning HTML page."""
    return render_template('english_word.html')

@app.route('/visualdic')
def visual_dictionary():
    """Serves the visual dictionary HTML page."""
    return render_template('visual_dictionary.html')

@app.route('/words', methods=['GET'])
def get_words():
    """Fetches English words from words.txt file."""
    try:
        # Try to read from local file first
        with open('words.txt', 'r', encoding='utf-8') as file:
            content = file.read().strip()
            print("Loaded words from local file")
            # save jsonified content to local file
            # with open('words.json', 'w', encoding='utf-8') as file:
            #     json.dump({'words': content.strip()}, file, ensure_ascii=False, indent=4)
            return jsonify({'words': content})
    except FileNotFoundError:
        # If local file not found, try to load from GCS
        try:
            client = storage.Client()
            bucket = client.bucket('jerry-argolis-bucket-asia-northeast3')
            blob = bucket.blob('words.txt')
            content = blob.download_as_text(encoding='utf-8')
            print("Loaded words from GCS")
            # save jsonified content to local file
            # with open('words.json', 'w', encoding='utf-8') as file:
            #     json.dump({'words': content.strip()}, file, ensure_ascii=False, indent=4)
            return jsonify({'words': content.strip()})
        except Exception as gcs_error:
            return jsonify({'error': f'Failed to load words from GCS: {str(gcs_error)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Failed to read words file: {str(e)}'}), 500

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

# This is not for English word quiz.
# This is for visual dictionary.
# Never modify this when working on English word quiz.
@app.route('/ask_to_gemini', methods=['POST'])
def ask_to_gemini():
    """캔버스 이미지를 사용하여 Gemini에게 질문하는 엔드포인트"""
    data = request.get_json()
    # api_key = data.get('api_key') # API 키는 서버 환경 변수에서 가져옴
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    image_data_url = data.get('image_data_url')
    # question = data.get('question') # 질문은 서버에서 정의

    # 질문 프롬프트는 서버에서 직접 정의
    question_prompt = """explain the meaning that is 
pointed by red color rectangle, circle or underscore. answer to only one part.
if it's text, translated into korean explanation. as simple as possible.
if it's image explain the image. as simple as possible.
"""

    if not all([gemini_api_key, image_data_url]): # question은 이제 서버에서 정의되므로 검사에서 제외
        return jsonify({'error': '필수 파라미터가 누락되었습니다. (API 키, 이미지)'}), 400

    try:
        client = genai.Client(vertexai=True, project=os.environ.get('GOOGLE_CLOUD_PROJECT'), location=os.get('LOCATION'))

        # Base64 이미지 데이터 디코딩
        header, encoded = image_data_url.split(",", 1)
        image_data = base64.b64decode(encoded)
        image = Image.open(io.BytesIO(image_data))

        # Gemini API 호출
        response = client.models.generate_content(model='gemini-2.5-flash', contents=[question_prompt, image])

        if response.text:
            answer = response.text
            return jsonify({'answer': answer})
        else:
            return jsonify({'error': 'Gemini API로부터 유효한 응답을 받지 못했습니다.'}), 500

    except Exception as e:
        import traceback
        print(f"Gemini API 호출 중 오류 발생: {traceback.format_exc()}")
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

@app.route('/evaluate_answer', methods=['POST'])
def evaluate_answer():
    data = request.get_json()
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    current_word_english = data.get('english')
    current_word_korean = data.get('korean')
    user_answer = data.get('user_answer')

    if not all([gemini_api_key, current_word_english, current_word_korean, user_answer]):
        return jsonify({'error': '필수 파라미터가 누락되었습니다.'}), 400

    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={gemini_api_key}"

    prompt = f"""당신은 영어 단어 전문가입니다. 사용자는 영단어 '{current_word_english}'의 뜻을 '{user_answer}'라고 입력했습니다. 정답은 '{current_word_korean}'입니다. 사용자의 답과 정답이 얼마나 유사한지 0에서 100점 사이의 점수로 평가하고 그 점수와 간단한 이유를 한국어로 설명해 주세요. 예를 들어 '95. 의미가 매우 유사합니다.'와 같이 답변해주세요. 단, 답변은 점수와 이유로만 구성되어야 합니다."""

    try:
        response = requests.post(
            API_URL,
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{
                    'parts': [{'text': prompt}]
                }],
                'systemInstruction': {'parts': [{'text': '한국어로 답변해 주세요.'}]},
            }
        )

        if not response.ok:
            error_data = response.json()
            print(f'Gemini API 호출 실패: {response.status_code} {response.reason} {error_data}')
            return jsonify({'error': f'Gemini API 오류: {response.status_code}', 'details': error_data}), response.status_code

        data = response.json()
        if data.get('candidates') and data['candidates'][0].get('content'):
            llm_response = data['candidates'][0]['content']['parts'][0]['text']
            # llm_response에서 similarity_score와 justification을 추출합니다.
            import re
            match = re.match(r"(\d+)\. (.*)", llm_response)
            if match:
                similarity_score = int(match.group(1))
                justification = match.group(2)
                return jsonify({'similarity_score': similarity_score, 'justification': justification})
            else:
                return jsonify({'error': 'Gemini API 응답을 파싱할 수 없습니다.', 'raw_response': llm_response}), 500
        else:
            return jsonify({'error': 'Gemini API로부터 유효한 응답을 받지 못했습니다.'}), 500

    except Exception as e:
        import traceback
        print(f"Gemini API 호출 중 오류 발생: {traceback.format_exc()}")
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

@app.route('/generate_hint', methods=['POST'])
def generate_hint():
    data = request.get_json()
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    current_word_english = data.get('english')

    if not all([gemini_api_key, current_word_english]):
        return jsonify({'error': '필수 파라미터가 누락되었습니다.'}), 400

    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={gemini_api_key}"

    prompt = f"""영단어 '{current_word_english}'에 대한 뜻을 직접적으로 밝히지 않는 한 문장짜리 한국어 힌트를 제공해주세요. 예를 들어, 관련 단어나 짧은 예문을 제시하거나 단어의 분위기를 설명해 주세요. 답변은 한 문장으로만 구성되어야 합니다."""

    try:
        response = requests.post(
            API_URL,
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{
                    'parts': [{'text': prompt}]
                }],
                'systemInstruction': {'parts': [{'text': '당신은 사용자의 영어 공부를 도와주는 친절한 튜터입니다. 한국어로 응답해 주세요.'}]},
            }
        )

        if not response.ok:
            error_data = response.json()
            print(f'Gemini API 호출 실패: {response.status_code} {response.reason} {error_data}')
            return jsonify({'error': f'Gemini API 오류: {response.status_code}', 'details': error_data}), response.status_code

        data = response.json()
        if data.get('candidates') and data['candidates'][0].get('content'):
            hint_message = data['candidates'][0]['content']['parts'][0]['text']
            return jsonify({'hint_message': hint_message})
        else:
            return jsonify({'error': 'Gemini API로부터 유효한 응답을 받지 못했습니다.'}), 500

    except Exception as e:
        import traceback
        print(f"Gemini API 호출 중 오류 발생: {traceback.format_exc()}")
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

@app.route('/generate_example', methods=['POST'])
def generate_example():
    data = request.get_json()
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    current_word_english = data.get('english')
    current_word_korean = data.get('korean')

    if not all([gemini_api_key, current_word_english, current_word_korean]):
        return jsonify({'error': '필수 파라미터가 누락되었습니다.'}), 400

    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={gemini_api_key}"

    prompt = f"""영단어 '{current_word_english}'의 뜻은 '{current_word_korean}'입니다. 이 단어를 사용한 간단하고 이해하기 쉬운 영어 예문을 하나 만들어주세요. 예문은 한 문장으로만 작성하고, 한국어 번역도 함께 제공해주세요. 형식: "영어 예문 - 한국어 번역"""

    try:
        response = requests.post(
            API_URL,
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{
                    'parts': [{'text': prompt}]
                }],
                'systemInstruction': {'parts': [{'text': '당신은 사용자의 영어 공부를 도와주는 친절한 튜터입니다. 한국어로 응답해 주세요.'}]},
            }
        )

        if not response.ok:
            error_data = response.json()
            print(f'Gemini API 호출 실패: {response.status_code} {response.reason} {error_data}')
            return jsonify({'error': f'Gemini API 오류: {response.status_code}', 'details': error_data}), response.status_code

        data = response.json()
        if data.get('candidates') and data['candidates'][0].get('content'):
            example_sentence = data['candidates'][0]['content']['parts'][0]['text']
            return jsonify({'example_sentence': example_sentence})
        else:
            return jsonify({'error': 'Gemini API로부터 유효한 응답을 받지 못했습니다.'}), 500

    except Exception as e:
        import traceback
        print(f"Gemini API 호출 중 오류 발생: {traceback.format_exc()}")
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

@app.route('/generate_round_summary', methods=['POST'])
def generate_round_summary():
    data = request.get_json()
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    total_words_in_round = data.get('total_words_in_round')
    correct_count = data.get('correct_count')
    incorrect_words_list = data.get('incorrect_words_list') # List of English words

    if not all([gemini_api_key, total_words_in_round is not None, correct_count is not None]):
        return jsonify({'error': '필수 파라미터가 누락되었습니다.'}), 400

    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={gemini_api_key}"

    prompt = f"""
    이번 라운드에서 사용자는 {total_words_in_round}개 중 {correct_count}개를 맞혔습니다.
    이 점수에 맞는 격려 메시지를 한 문장으로 작성해 주세요.
    """

    if incorrect_words_list:
        prompt += f"""
    사용자가 틀린 단어들은 다음과 같습니다: {', '.join(incorrect_words_list)}.
    이 단어들을 더 잘 이해할 수 있도록 각 단어에 대한 간결한 설명을 '단어: 설명' 형태로 제공해주세요.
    """
    else:
        prompt += f"""
    사용자가 모든 문제를 맞혔습니다! 전체 퀴즈가 성공적으로 끝났습니다. 축하 메시지를 작성해 주세요.
    """

    try:
        response = requests.post(
            API_URL,
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{
                    'parts': [{'text': prompt}]
                }],
                'systemInstruction': {'parts': [{'text': '당신은 사용자의 영어 공부를 도와주는 친절한 튜터입니다. 한국어로 응답해 주세요.'}]},
            }
        )

        if not response.ok:
            error_data = response.json()
            print(f'Gemini API 호출 실패: {response.status_code} {response.reason} {error_data}')
            return jsonify({'error': f'Gemini API 오류: {response.status_code}', 'details': error_data}), response.status_code

        data = response.json()
        if data.get('candidates') and data['candidates'][0].get('content'):
            llm_message = data['candidates'][0]['content']['parts'][0]['text']
            return jsonify({'llm_message': llm_message})
        else:
            return jsonify({'error': 'Gemini API로부터 유효한 응답을 받지 못했습니다.'}), 500

    except Exception as e:
        import traceback
        print(f"Gemini API 호출 중 오류 발생: {traceback.format_exc()}")
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

@app.route('/ask_word_ai', methods=['POST'])
def ask_word_ai():
    data = request.get_json()
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    current_word_english = data.get('english')
    current_word_korean = data.get('korean')
    question = data.get('question')

    if not all([gemini_api_key, current_word_english, current_word_korean, question]):
        return jsonify({'error': '필수 파라미터가 누락되었습니다.'}), 400

    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={gemini_api_key}"

    prompt = f"""영단어 '{current_word_english}'의 뜻은 '{current_word_korean}'입니다. 사용자가 "{question}"라고 질문했습니다. 이 질문에 대해 친절하고 도움이 되는 답변을 한국어로 제공해 주세요. 단어의 의미, 사용법, 예문, 어원 등에 대한 질문일 수 있습니다. 답변은 마크다운 형식으로 작성해 주세요. 제목은 ##, 소제목은 ###, 강조는 **굵게**, 예문은 > 인용문으로 표시해 주세요."""

    try:
        response = requests.post(
            API_URL,
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{
                    'parts': [{'text': prompt}]
                }],
                'systemInstruction': {'parts': [{'text': '당신은 사용자의 영어 공부를 도와주는 친절한 튜터입니다. 한국어로 응답해 주세요.'}]},
            }
        )

        if not response.ok:
            error_data = response.json()
            print(f'Gemini API 호출 실패: {response.status_code} {response.reason} {error_data}')
            return jsonify({'error': f'Gemini API 오류: {response.status_code}', 'details': error_data}), response.status_code

        data = response.json()
        if data.get('candidates') and data['candidates'][0].get('content'):
            ai_answer = data['candidates'][0]['content']['parts'][0]['text']
            return jsonify({'ai_answer': ai_answer})
        else:
            return jsonify({'error': 'Gemini API로부터 유효한 응답을 받지 못했습니다.'}), 500

    except Exception as e:
        import traceback
        print(f"Gemini API 호출 중 오류 발생: {traceback.format_exc()}")
        return jsonify({'error': f'서버 오류: {str(e)}'}), 500

@app.route('/list_wordbooks', methods=['GET'])
def list_wordbooks():
    """GCS에서 지정된 접두사를 가진 단어장 파일 목록을 반환합니다."""
    gcs_path = os.environ.get('ENGDICT_GCSPATH')
    file_prefix = os.environ.get('ENGDICT_FILE_PREFIX')

    if not all([gcs_path, file_prefix]):
        return jsonify({'error': '환경 변수 (ENGDICT_GCSPATH, ENGDICT_FILE_PREFIX)가 설정되지 않았습니다.'}), 500

    print(f"DEBUG: GCS Path: {gcs_path}")
    print(f"DEBUG: File Prefix: {file_prefix}")

    try:
        # GCS 경로에서 버킷 이름과 폴더 경로 추출
        # 예: gs://jerry-argolis-bucket-asia-northeast3/words/wordbooks/
        if not gcs_path.startswith('gs://'):
            return jsonify({'error': '유효하지 않은 GCS 경로 형식입니다. "gs://"로 시작해야 합니다.'}), 500
        
        path_parts = gcs_path[len('gs://'):].split('/', 1)
        bucket_name = path_parts[0]
        prefix_path = path_parts[1] if len(path_parts) > 1 else ''

        print(f"DEBUG: Bucket Name: {bucket_name}")
        print(f"DEBUG: Prefix Path for GCS: {prefix_path}")

        client = storage.Client()
        bucket = client.bucket(bucket_name)

        # GCS 버킷에서 파일 목록 가져오기
        blobs = list(bucket.list_blobs(prefix=f'{prefix_path}/{file_prefix}')) # 이터레이터를 리스트로 변환하여 여러 번 사용할 수 있도록 합니다.
        print(f"DEBUG: Blobs found: {[blob.name for blob in blobs]}") # Debug print for all blob names
        
        wordbook_titles = []
        for blob in blobs:
            print(f"DEBUG: Found Blob: {blob.name}")
            # .json 확장자로 끝나는 파일만 필터링
            if blob.name.endswith('.json'):
                # 파일 이름에서 접두사와 확장자 제거
                # 예: words/wordbooks/wordbook_22 amiss 0125.json -> wordbook_22 amiss 0125
                raw_title = blob.name[len(prefix_path):].lstrip('/').replace('.json', '')
                print(f"DEBUG: Raw Title after prefix removal and .json strip: {raw_title}")
                if raw_title.startswith(file_prefix):
                    title = raw_title[len(file_prefix):].strip()
                    print(f"DEBUG: Extracted Title: {title}")
                    if title: # 빈 문자열이 아닌 경우에만 추가
                        wordbook_titles.append(title)

        return jsonify({'wordbooks': wordbook_titles})

    except Exception as e:
        import traceback
        print(f"GCS 단어장 목록 조회 중 오류 발생: {traceback.format_exc()}")
        return jsonify({'error': f'단어장 목록 조회 중 서버 오류 발생: {str(e)}'}), 500

@app.route('/words_json', methods=['GET'])
def get_wordbook_json():
    """GCS에서 특정 단어장 JSON 파일을 불러와 반환합니다."""
    word_book_title = request.args.get('title')

    if not word_book_title:
        return jsonify({'error': '단어장 제목(title)이 필요합니다.'}), 400

    gcs_path = os.environ.get('ENGDICT_GCSPATH')
    file_prefix = os.environ.get('ENGDICT_FILE_PREFIX')

    if not all([gcs_path, file_prefix]):
        return jsonify({'error': '환경 변수 (ENGDICT_GCSPATH, ENGDICT_FILE_PREFIX)가 설정되지 않았습니다.'}), 500

    try:
        if not gcs_path.startswith('gs://'):
            return jsonify({'error': '유효하지 않은 GCS 경로 형식입니다. "gs://"로 시작해야 합니다.'}), 500
        
        path_parts = gcs_path[len('gs://'):].split('/', 1)
        bucket_name = path_parts[0]
        prefix_path = path_parts[1] if len(path_parts) > 1 else ''

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        
        # 파일 이름 구성: engdic/wordbook_22 amiss 0125.json
        full_blob_name = f'{prefix_path}/{file_prefix}{word_book_title}.json'
        # 이중 슬래시 방지: prefix_path가 빈 문자열일 경우, 혹은 이미 /로 끝나는 경우를 대비
        if prefix_path.endswith('/') and full_blob_name.startswith('/'):
             full_blob_name = full_blob_name[1:]
        elif not prefix_path and full_blob_name.startswith('/'):
             full_blob_name = full_blob_name[1:]

        blob = bucket.blob(full_blob_name)

        if not blob.exists():
            return jsonify({'error': f'단어장 파일을 찾을 수 없습니다: {word_book_title}'}), 404

        content = blob.download_as_text(encoding='utf-8')
        return jsonify(json.loads(content))

    except Exception as e:
        import traceback
        print(f"GCS 단어장 파일 로드 중 오류 발생: {traceback.format_exc()}")
        return jsonify({'error': f'단어장 파일 로드 중 서버 오류 발생: {str(e)}'}), 500


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
