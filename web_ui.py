import gradio as gr
import requests
import json
import pandas as pd
import io
import networkx as nx
import matplotlib.pyplot as plt
import time
from threading import Thread, Event
import os
import tempfile

API_URL = "http://localhost:8000/analyze"
TASKS_URL = "http://localhost:8000/tasks/"
RESULTS_URL = "http://localhost:8000/results/"

# 작업 상태 폴링 간격(초)
POLLING_INTERVAL = 1.0

def upload_file_to_text(file_obj):
    """업로드된 파일을 텍스트로 변환"""
    try:
        # 다양한 인코딩 시도
        encodings = ['utf-8', 'utf-8-sig', 'euc-kr', 'cp949', 'latin-1']
        content = None
        
        for enc in encodings:
            try:
                content = file_obj.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            return "파일 인코딩을 인식할 수 없습니다. UTF-8, EUC-KR, CP949 중 하나를 사용해 주세요.", None
        
        file_size_mb = len(content) / (1024 * 1024)
        return f"파일을 성공적으로 불러왔습니다. (크기: {file_size_mb:.2f}MB)", content
    except Exception as e:
        return f"파일 처리 중 오류가 발생했습니다: {str(e)}", None

def poll_task_status(task_id, progress_bar, status_text, result_ready=None):
    """작업 상태를 주기적으로 확인하는 함수"""
    while True:
        try:
            response = requests.get(f"{TASKS_URL}{task_id}")
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                progress = data.get("progress", 0)
                message = data.get("message", "진행 중...")
                
                # UI 업데이트
                progress_bar.update(value=progress)
                status_text.update(value=f"상태: {status} - {message}")
                
                # 작업 완료 또는 실패 시 폴링 종료
                if status in ["completed", "failed"]:
                    if result_ready is not None:
                        result_ready.set()
                    break
                    
            else:
                status_text.update(value=f"상태 확인 실패: {response.status_code}")
                time.sleep(5)  # 오류 시 더 긴 대기 시간
                
        except Exception as e:
            status_text.update(value=f"통신 오류: {str(e)}")
            time.sleep(5)
            
        time.sleep(POLLING_INTERVAL)

def analyze_text(text, characters_str, emotion_lex_json, chapter_pattern, progress_bar, status_text, progress_container):
    """텍스트 분석 실행하고 결과 반환"""
    try:
        if not text or not text.strip():
            return None, "❌ 텍스트가 비어있습니다.", None, None, None
            
        characters = [c.strip() for c in characters_str.split(",") if c.strip()]
        if not characters:
            return None, "❌ 등장인물이 비어있습니다.", None, None, None
            
        try:
            emotion_lexicon = json.loads(emotion_lex_json)
        except json.JSONDecodeError:
            return None, "❌ 감정어 사전 JSON 형식이 올바르지 않습니다.", None, None, None
            
        # 텍스트 크기 계산
        text_size_mb = len(text) / (1024 * 1024)
        status_text.update(value=f"📤 텍스트 전송 중... ({text_size_mb:.2f}MB)")
        progress_container.update(visible=True)
        
        payload = {
            "text": text,
            "characters": characters,
            "emotion_lexicon": emotion_lexicon,
            "chapter_pattern": chapter_pattern
        }
        
        # API 요청 보내기
        response = requests.post(API_URL, json=payload, timeout=30)
        response_data = response.json()
        
        # 대용량 텍스트인 경우 백그라운드 작업 처리
        if "task_id" in response_data:
            task_id = response_data["task_id"]
            status_text.update(value=f"🔄 백그라운드 작업 시작됨 (ID: {task_id})")
            
            # 상태 확인 스레드 시작
            thread = Thread(target=poll_task_status, args=(task_id, progress_bar, status_text))
            thread.daemon = True
            thread.start()
            
            # 폴링 중에 UI 차단 방지
            time.sleep(2)
            
            # 결과 준비 이벤트
            result_ready = Event()
            
            # 상태 확인 스레드 업데이트
            thread = Thread(target=poll_task_status, args=(task_id, progress_bar, status_text, result_ready))
            thread.daemon = True
            thread.start()
            
            # 작업 완료 대기 (타임아웃 추가)
            max_wait_time = 7200  # 최대 2시간 대기
            result_ready.wait(timeout=max_wait_time)
            
            # 결과 가져오기
            try:
                status_response = requests.get(f"{TASKS_URL}{task_id}")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data["status"] == "completed":
                        # 완료된 결과 가져오기
                        result_response = requests.get(f"{RESULTS_URL}{task_id}")
                        if result_response.status_code == 200:
                            result = result_response.json()
                        else:
                            return None, f"❌ 결과 획득 실패: {result_response.status_code}", None, None, None
                    elif status_data["status"] == "failed":
                        return None, f"❌ 작업 실패: {status_data.get('message', '알 수 없는 오류')}", None, None, None
                    else:
                        return None, f"❌ 시간 초과: 작업이 {max_wait_time}초 내에 완료되지 않았습니다.", None, None, None
                else:
                    return None, f"❌ 상태 확인 실패: {status_response.status_code}", None, None, None
            except Exception as e:
                return None, f"❌ 상태 확인 중 오류: {str(e)}", None, None, None
        else:
            # 일반 동기 응답 처리
            result = response_data
            
        # 분석 결과 처리
        relations = result.get("relations", [])
        summary_relations = result.get("summary_relations", [])
        chapter_emotions = result.get("chapter_emotions", {})
        
        if not relations:
            return None, "⚠️ 관계 데이터가 없습니다.", None, None, None
        
        df = pd.DataFrame(relations)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
        csv_data = csv_buffer.getvalue()
        
        # 요약 관계로 그래프 그리기
        graph_path = None
        try:
            fig, ax = plt.subplots(figsize=(10, 10))
            G = nx.DiGraph()
            
            for rel in summary_relations:
                src = rel["from"]
                tgt = rel["to"]
                label = rel["attitude"]
                count = rel["count"]
                G.add_edge(src, tgt, label=f"{label} ({count})", weight=count)
        
            if G.number_of_nodes() > 0:  # 노드가 있을 때만 그래프 그리기
                # 노드 수에 따른 최적 레이아웃 선택
                if G.number_of_nodes() < 10:
                    pos = nx.spring_layout(G, seed=42, k=0.5)  # 스프링 레이아웃 (적은 노드용)
                elif G.number_of_nodes() < 20:
                    pos = nx.kamada_kawai_layout(G)  # Kamada-Kawai (중간 노드용)
                else:
                    pos = nx.fruchterman_reingold_layout(G, seed=42)  # Fruchterman-Reingold (많은 노드용)
                
                # 노드 색상 및 크기 조정
                node_sizes = [2000 + G.degree(n) * 200 for n in G.nodes()]
                nx.draw(G, pos, with_labels=True, 
                       node_color="lightgreen", 
                       edge_color="gray",
                       node_size=node_sizes,
                       font_size=10, 
                       font_weight='bold',
                       ax=ax)
                
                # 엣지 레이블 추가
                edge_labels = nx.get_edge_attributes(G, "label")
                nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, ax=ax)
                
                plt.tight_layout()
                
                # 임시 파일에 저장 (중복 방지)
                timestamp = int(time.time())
                graph_path = f"graph_{timestamp}.png"
                plt.savefig(graph_path, dpi=300, bbox_inches='tight')
                plt.close()
        except Exception as e:
            print(f"그래프 생성 중 오류: {str(e)}")
            graph_path = None
        
        # 챕터별 감정 테이블 생성
        chapter_emotion_rows = []
        for chapter, emotions in chapter_emotions.items():
            row = {"chapter": chapter}
            row.update(emotions)
            chapter_emotion_rows.append(row)
        
        if chapter_emotion_rows:
            chapter_df = pd.DataFrame(chapter_emotion_rows)
        else:
            chapter_df = None
        
        return df, "✅ 분석 성공!", csv_data, graph_path, chapter_df
    
    except requests.exceptions.RequestException as e:
        return None, f"❌ API 서버 통신 오류: {str(e)}", None, None, None
    except Exception as e:
        return None, f"❌ 예외 발생: {str(e)}", None, None, None

def download_csv_file(csv_str):
    """CSV 파일 저장"""
    if not csv_str:
        return None
    
    try:
        timestamp = int(time.time())
        filename = f"relations_output_{timestamp}.csv"
        with open(filename, "w", encoding="utf-8-sig") as f:
            f.write(csv_str)
        return filename
    except Exception as e:
        print(f"CSV 저장 중 오류: {str(e)}")
        return None

def process_large_text_file(file_obj, chars, lex, pat, progress_bar, status_text, progress_container):
    """대용량 텍스트 파일 처리"""
    status_msg, text_content = upload_file_to_text(file_obj)
    
    if text_content is None:
        return None, status_msg, None, None, None
    
    # 일반 텍스트 분석과 동일한 프로세스 수행
    return analyze_text(text_content, chars, lex, pat, progress_bar, status_text, progress_container)

# 샘플 감정어 사전
DEFAULT_EMOTION_LEXICON = {
    "positive": ["love", "like", "happy", "joy", "pleasure", "trust", "admire", "respect", "사랑", "좋아", "행복", "기쁨", "신뢰", "존경"],
    "negative": ["hate", "dislike", "fear", "anger", "sadness", "disgust", "contempt", "distrust", "미움", "싫어", "두려움", "분노", "슬픔", "역겨움", "경멸", "불신"]
}

# Gradio UI 생성
if __name__ == "__main__":
    print("문학 텍스트 감정·관계 분석기 웹 UI 시작 중...")
    
    with gr.Blocks(title="문학 텍스트 감정·관계 분석기") as demo:
        gr.Markdown("# 문학 텍스트 감정·관계 분석기")
        gr.Markdown("대용량 문학 텍스트에서 등장인물 간의 감정 관계를 추출하고 시각화합니다.")
        
        with gr.Tabs():
            with gr.TabItem("텍스트 입력"):
                text_input = gr.Textbox(
                    label="분석할 텍스트를 입력하세요 (대용량 텍스트도 가능)",
                    placeholder="여기에 텍스트를 붙여넣으세요...",
                    lines=10
                )
                
            with gr.TabItem("파일 업로드"):
                file_input = gr.File(label="분석할 텍스트 파일 (.txt)")
                file_status = gr.Textbox(label="파일 상태", interactive=False)
                
        characters_input = gr.Textbox(
            label="등장인물 목록 (쉼표로 구분)",
            placeholder="예: Victor, Elizabeth, Creature, Clerval, Justine",
            value="Victor, Elizabeth, Creature, Clerval, Justine"
        )
        
        emotion_lexicon_input = gr.Code(
            label="감정어 사전 (JSON 형식)",
            language="json",
            value=json.dumps(DEFAULT_EMOTION_LEXICON, indent=2, ensure_ascii=False)
        )
        
        chapter_pattern_input = gr.Textbox(
            label="챕터 구분 정규식",
            value=r"(Letter \d+|Chapter \d+)",
            placeholder="예: (Letter \\d+|Chapter \\d+)"
        )
        
        with gr.Row():
            analyze_button = gr.Button("텍스트 분석 시작", variant="primary")
            analyze_file_button = gr.Button("파일 분석 시작", variant="primary")
        
        # 진행 상태 표시 UI
        with gr.Group(visible=False) as progress_container:
            progress_bar = gr.Slider(minimum=0, maximum=100, value=0, label="진행 상태")
            status_text = gr.Textbox(label="상태 메시지", value="준비 중...")
        
        with gr.Tab("분석 결과"):
            result_text = gr.Textbox(label="처리 결과")
            
            with gr.Row():
                with gr.Column():
                    relations_df = gr.DataFrame(label="관계 데이터")
                    csv_download_button = gr.Button("CSV 파일로 다운로드")
                    download_path = gr.File(label="다운로드된 파일")
                
                with gr.Column():
                    graph_output = gr.Image(label="관계 그래프", type="filepath")
        
        with gr.Tab("감정 분석"):
            emotion_df = gr.DataFrame(label="챕터별 감정 분포")
        
        # 이벤트 설정
        file_input.upload(
            fn=upload_file_to_text,
            inputs=[file_input],
            outputs=[file_status, text_input]
        )
        
        analyze_button.click(
            fn=analyze_text,
            inputs=[text_input, characters_input, emotion_lexicon_input, 
                   chapter_pattern_input, progress_bar, status_text, progress_container],
            outputs=[relations_df, result_text, download_path, graph_output, emotion_df]
        )
        
        analyze_file_button.click(
            fn=process_large_text_file,
            inputs=[file_input, characters_input, emotion_lexicon_input, 
                   chapter_pattern_input, progress_bar, status_text, progress_container],
            outputs=[relations_df, result_text, download_path, graph_output, emotion_df]
        )
        
        csv_download_button.click(
            fn=download_csv_file,
            inputs=[download_path],
            outputs=[download_path]
        )
    
    # Gradio 웹 서버 시작
    demo.launch(server_port=7860, share=False)
    print("Gradio 웹 서버가 http://localhost:7860 에서 실행 중입니다.")