import re
import json
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Generator, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === 텍스트 스트리밍 처리 유틸 ===
def split_into_chapters_stream(text: str, pattern: str) -> Generator[Tuple[str, str], None, None]:
    """대용량 텍스트를 챕터 단위로 스트리밍 방식으로 분할"""
    chapter_titles = re.findall(pattern, text)
    chunks = re.split(pattern, text)
    
    if len(chunks) <= 1:
        # 챕터 구분이 없는 경우 전체를 하나의 챕터로 처리
        yield ("전체 텍스트", text)
        return
        
    for i in range(1, min(len(chunks), len(chapter_titles) + 1)):
        try:
            title = chapter_titles[i-1]
            content = chunks[i] if i < len(chunks) else ""
            yield (title, content.strip())
        except IndexError:
            logger.warning(f"인덱스 에러 발생. i={i}, chunks_len={len(chunks)}, titles_len={len(chapter_titles)}")
            continue

def split_sentences(text: str) -> List[str]:
    """텍스트를 문장 단위로 분할"""
    # 문장 분할 패턴 확장 (한글 포함)
    return re.split(r'[.?!。？！]\s*', text)

def chunk_text(text: str, chunk_size: int = 100000) -> Generator[str, None, None]:
    """대용량 텍스트를 청크 단위로 분할하여 메모리 부담 감소"""
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]

# === 관계 추출 최적화 ===
def extract_relations(text: str, characters: List[str], emotions: List[str], chapter_title: str) -> List[Dict]:
    """한 챕터 내에서 등장인물 관계 추출"""
    relations = []
    sentences = split_sentences(text)
    
    # 인물 이름 패턴 미리 컴파일
    char_patterns = {char: re.compile(r'\b' + re.escape(char) + r'\b', re.IGNORECASE) for char in characters}
    emotion_patterns = {emo: re.compile(r'\b' + re.escape(emo) + r'\b', re.IGNORECASE) for emo in emotions}
    
    for sent_idx, sent in enumerate(sentences):
        if not sent.strip():  # 빈 문장 건너뛰기
            continue
            
        # 각 문장에 어떤 캐릭터가 존재하는지 확인
        present = []
        for char in characters:
            if char_patterns[char].search(sent):
                present.append(char)
                
        if len(present) < 2:
            continue
            
        # 감정어 확인
        for emo in emotions:
            if emotion_patterns[emo].search(sent):
                source = present[0]
                for target in present[1:]:
                    relations.append({
                        "from": source,
                        "to": target,
                        "attitude": emo,
                        "sentence": sent.strip(),
                        "chapter": chapter_title
                    })
                    
    return relations

# === 분석 진행 상황 추적 클래스 ===
class ProgressTracker:
    def __init__(self, total_chapters=0):
        self.total_chapters = total_chapters
        self.processed_chapters = 0
        self.relations_count = 0
        
    def update(self, chapter_title, new_relations):
        self.processed_chapters += 1
        self.relations_count += len(new_relations)
        progress = (self.processed_chapters / self.total_chapters) * 100 if self.total_chapters > 0 else 0
        logger.info(f"처리 중: {chapter_title} 완료 ({self.processed_chapters}/{self.total_chapters}, {progress:.1f}%, 관계 {self.relations_count}개 발견)")
        return {
            "progress": progress,
            "chapter": chapter_title,
            "processed": self.processed_chapters,
            "total": self.total_chapters,
            "relations": self.relations_count
        }

# === 핵심 분석 함수 (최적화) ===
def run_analysis(
    text: str,
    characters: List[str],
    emotion_lexicon: Dict[str, List[str]],
    chapter_pattern: str = r"(Letter \d+|Chapter \d+)",
    progress_callback=None
) -> Dict:
    """대용량 텍스트를 처리하도록 최적화된 분석 함수"""
    # 전체 텍스트 길이 로깅
    text_mb = len(text) / (1024 * 1024)
    logger.info(f"텍스트 분석 시작: {text_mb:.2f}MB, 등장인물 {len(characters)}명")
    
    # 챕터 수 미리 계산하여 진행률 추적
    chapter_count = len(re.findall(chapter_pattern, text))
    if chapter_count == 0:
        chapter_count = 1  # 챕터 구분이 없는 경우
        
    # 진행 상황 추적 초기화
    tracker = ProgressTracker(chapter_count)
    
    emotions = emotion_lexicon.get("positive", []) + emotion_lexicon.get("negative", [])
    if not emotions:
        logger.warning("감정어 사전이 비어있습니다.")
    
    all_relations = []
    chapter_emotions = defaultdict(lambda: defaultdict(int))
    relation_map = defaultdict(list)  # (from, to) -> list of attitudes
    
    try:
        # 챕터별 스트리밍 처리
        for title, content in split_into_chapters_stream(text, chapter_pattern):
            logger.info(f"챕터 처리 시작: {title} ({len(content) / 1024:.1f}KB)")
            
            # 대용량 챕터는 청크 단위로 처리
            chapter_relations = []
            for chunk in chunk_text(content):
                chunk_relations = extract_relations(chunk, characters, emotions, title)
                chapter_relations.extend(chunk_relations)
            
            # 챕터 단위 처리 결과 통합
            all_relations.extend(chapter_relations)
            for r in chapter_relations:
                chapter_emotions[title][r["attitude"]] += 1
                relation_map[(r["from"], r["to"])].append(r["attitude"])
            
            # 진행 상황 업데이트 및 콜백
            progress_info = tracker.update(title, chapter_relations)
            if progress_callback:
                progress_callback(progress_info)
    
    except Exception as e:
        logger.error(f"텍스트 분석 중 오류 발생: {str(e)}")
        raise
    
    # 대표 감정 계산
    logger.info("관계 요약 생성 중...")
    summarized_relations = []
    for (src, tgt), att_list in relation_map.items():
        counter = Counter(att_list)
        if counter:  # 비어있지 않은 경우만
            representative = counter.most_common(1)[0][0]  # 가장 많이 등장한 감정
            summarized_relations.append({
                "from": src,
                "to": tgt,
                "attitude": representative,
                "count": counter[representative]
            })
    
    logger.info(f"분석 완료: 관계 {len(all_relations)}개, 요약 관계 {len(summarized_relations)}개")
    
    return {
        "relations": all_relations,
        "chapter_emotions": dict(chapter_emotions),  # defaultdict를 일반 dict로 변환
        "summary_relations": summarized_relations
    }

# === 테스트 실행용 ===
if __name__ == "__main__":
    with open("sample_text.txt", "r", encoding="utf-8") as f:
        sample = f.read()
    with open("characters.txt", "r", encoding="utf-8") as f:
        char_list = [line.strip() for line in f if line.strip()]
    with open("attitude_lexicon.json", "r", encoding="utf-8") as f:
        emo_dict = json.load(f)

    def progress_printer(info):
        print(f"진행률: {info['progress']:.1f}% - {info['chapter']} 처리 완료")

    result = run_analysis(sample, char_list, emo_dict, progress_callback=progress_printer)
    print(json.dumps(result, indent=2, ensure_ascii=False))