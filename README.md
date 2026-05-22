# vibe-survey-studio

Streamlit 멀티페이지 앱.

1. **📝 QSF 변환·검증**: 마크다운 텍스트 → 표준 Qualtrics QSF
2. **🚀 Prolific 제어**: 스터디 생성·모니터링·응답자 승인
3. **🎓 Qualtrics 실습**: 학생용 — Qualtrics API 로 서베이를 직접 만들고 질문·블록·플로우 관리 (yrvelez/qualtrics-mcp-server 의 핵심 도구를 Python 으로 옮긴 학습용 페이지)

QSF, Prolific, Qualtrics 실습 세 모듈은 서로 import 하지 않음. `shared/state.py` 로만 데이터를 공유.

## 실행

```bash
pip install -r requirements.txt
streamlit run Home.py
```

## 폴더 구조

```
vibe-survey-studio/
├── Home.py
├── pages/
│   ├── 1_📝_QSF_변환.py
│   ├── 2_🚀_Prolific_제어.py
│   └── 3_🎓_Qualtrics_실습.py
├── lib/
│   ├── qsf.py          # 마크다운 파서 + 템플릿 주입 + 내보내기
│   ├── validate.py     # 22개 QSF 검증 규칙
│   ├── prolific.py     # Prolific API 클라이언트
│   ├── screening.py    # 사전 스크리닝 프리셋
│   ├── monitor.py      # 진행 상황 스냅샷 + 경고 플래그
│   └── qualtrics_api.py # Qualtrics REST API v3 래퍼 (실습용)
├── shared/
│   └── state.py        # 페이지 간 세션 상태 공유
├── templates/
│   └── standard.qsf    # 표준 QSF 템플릿
├── tests/
│   ├── test_qsf.py
│   ├── test_validate.py
│   ├── test_prolific.py
│   └── test_qualtrics_api.py
└── docs/
    ├── input_format_spec.md
    └── validation_rules.md
```

## 모듈 import 규칙

- `lib/qsf.py`, `lib/validate.py` → `lib/prolific.py` 등 import 금지
- `lib/prolific.py`, `lib/screening.py`, `lib/monitor.py` → `lib/qsf.py` 등 import 금지 (단, monitor → prolific 은 동일 도메인이므로 허용)
- `lib/qualtrics_api.py` → 독립 모듈, 다른 lib 파일 import 금지
- `shared/state.py` → `lib/` 어떤 파일도 import 금지
- 페이지 파일만 `lib/` 와 `shared/` 둘 다 import

## 사용 흐름

### A. QSF 다운로드 → Prolific 배포 (기존)

1. **QSF 변환** 페이지에서 설문 텍스트 붙여넣기 → "변환 + 검증"
2. error 0개면 QSF 다운로드 가능
3. Qualtrics에 임포트 → Survey URL 복사 (앱 밖)
4. **Prolific 제어** 페이지에서 API key 저장 → 스터디 DRAFT 생성
5. 같은 페이지에서 Publish, 진행 모니터링, 응답자 승인

### B. Qualtrics 직접 실습 (학생용)

1. 강사는 `.streamlit/secrets.toml` (또는 `.env`) 에 `QUALTRICS_API_TOKEN` 과 `QUALTRICS_DATA_CENTER` 설정. 예시는 `.streamlit/secrets.toml.example` / `.env.example`.
2. **🎓 Qualtrics 실습** 페이지 진입 → Tab 1 에서 새 서베이 생성 (또는 기존 서베이 선택)
3. Tab 2 에서 객관식·텍스트·Likert 매트릭스 질문 추가
4. Tab 3 에서 블록 생성·이름 변경, 플로우 순서 조정
5. Tab 1 에서 활성화/비활성화·삭제 관리

## 입력 형식

`docs/input_format_spec.md` 참고.

## 검증 규칙

`docs/validation_rules.md` 참고. 22개 규칙 × pass/fail 케이스로 테스트.

## 테스트

```bash
pytest tests/
```

`test_qsf.py` + `test_validate.py` + `test_prolific.py` + `test_qualtrics_api.py` 가 모두 통과해야 함. (`test_qualtrics_api.py` 는 httpx MockTransport 로 모킹하므로 토큰 없이 실행 가능.)
