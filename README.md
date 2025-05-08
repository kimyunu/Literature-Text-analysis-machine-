# Literature-Text-analysis-machine-



문학 텍스트 감정·관계 분석기 (대용량 처리 버전)



이 시스템은 방대한 크기의 문학 텍스트를 처리--> 등장인물 간의 관계와 감정을 분석할 수 있습니다.  

FastAPI에 Gradio를 곁들인 웹 애플리케이션 --> 수 MB 크기의 텍스트도 안정적으로 처리 가능합니다. 

주요 기능

- 대용량 텍스트 처리: 청크 단위 스트리밍 처리로 메모리 효율성 확보




   (비동기 처리: 긴 시간이 걸리는 대용량 분석을 백그라운드에서 처리)

  - 실시간 진행 상황 처리 과정을 실시간으로 확인 가능

  - 인물 관계 그래프: 등장인물 간의 관계를 '시각화'

  --> 감정 분석: 챕터별 감정 분포 제공

  -------->>> 결과 저장: CSV 형태


  
설치 방법

1. 필요한 패키지 설치:

```bash
pip install fastapi uvicorn gradio pandas matplotlib networkx requests
```

2. 서버 실행:

```bash
# FastAPI 서버 실행 (백엔드)
python app.py

# 다른 터미널에서 Gradio 웹 UI 실행 (프론트엔드)
python web_ui.py
```

사용 방법(= 테스트 방법)







1. 웹 UI 접속: `http://localhost:7860`

2. 텍스트 입력 또는 파일 업로드:
      텍스트 입력 탭: 직접 텍스트를 붙여넣기
         파일 업로드 탭: `.txt` 파일 업로드

3. 필수 정보 입력:
   등장인물: 쉼표로 구분된 인물 이름 목록
      감정어 사전: JSON 형식의 감정어 목록
         챕터 정규식: 챕터 구분을 위한 정규식 패턴

4. "분석 시작" 버튼을 눌러 처리를 시작합니다.

5. 결과 확인:
   관계 결과 탭: 등장인물 간의 관계 목록
      그래프 탭: 인물 관계도 시각화
         감정 분석 탭: 챕터별 감정 분포



시스템 구조






- app.py: FastAPI 백엔드 서버
- core_analysis.py: 텍스트 분석 핵심 로직 (최적화된 알고리즘)
- web_ui.py: Gradio 기반 웹 인터페이스





입력에 관하여 

- 등장인물: `Victor, Elizabeth, Creature, Clerval, Justine`
- 감정어 사전: `attitude_lexicon.json` 파일 참조
- 챕터 정규식: `(Letter \d+|Chapter \d+)`



주의사항






- 매우 큰 텍스트(수십 MB)는 처리 시간이 길어질 수 있습니다.
- 메모리 사용량을 줄이기 위해 청크 단위로 처리됩니다. 챕터 경계를 넘어서는 문장은 분석이 부정확할 수 있습니다.
















## 라이선스

이 프로젝트는 **CC BY-NC-SA 4.0** 라이선스를 따릅니다.

- 자유롭게 열람, 복제, 수정 및 공유 가능
- 상업적 사용 금지
-  변경 시 동일한 라이선스로만 재배포 가능
- [전체 라이선스 보기](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.ko)







# requirements.txt 




 참고: 일부 Windows 환경에서는 `uvicorn` 명령어가 정상적으로 동작하지 않을 수 있습니다.  
이 경우 `python app.py` 명령어를 사용하면 동일한 FastAPI 서버가 실행됩니다.  


(내장된 `uvicorn.run()` 코드가 포함되어 있기 때문입니다.)
(쉬운설명: 처음 FastAPI를 접하시는 분들은 `uvicorn app:app` 명령어가 잘 작동하지 않을 수 있습니다.  
특히 Windows 환경에서는 PATH 설정 문제로 인식되지 않는 경우가 있습니다.  
이 경우 `python app.py` 명령어만 실행하셔도 동일하게 서버가 시작되니 안심하고 사용하세요.)


 Note: On some Windows setups, the `uvicorn` CLI command may not work properly due to environment issues.  
In such cases, you can simply run `python app.py` to start the FastAPI server.  
(This works because `uvicorn.run()` is already embedded inside the script.)




fastapi
uvicorn
gradio
pandas
matplotlib
networkx
requests
