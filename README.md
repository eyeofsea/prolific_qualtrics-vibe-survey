# vibe-survey-studio

Streamlit 멀티페이지 앱.

1. **📝 QSF 변환·검증**: 마크다운 텍스트 → 표준 Qualtrics QSF
2. **🚀 Prolific 제어**: 스터디 생성·모니터링·응답자 승인

QSF 모듈과 Prolific 모듈은 서로 import 하지 않음. `shared/state.py` 로만 데이터를 공유.

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
│   └── 2_🚀_Prolific_제어.py
├── lib/
│   ├── qsf.py          # 마크다운 파서 + 템플릿 주입 + 내보내기
│   ├── validate.py     # 22개 QSF 검증 규칙
│   ├── prolific.py     # Prolific API 클라이언트
│   ├── screening.py    # 사전 스크리닝 프리셋
│   └── monitor.py      # 진행 상황 스냅샷 + 경고 플래그
├── shared/
│   └── state.py        # 페이지 간 세션 상태 공유
├── templates/
│   └── standard.qsf    # 표준 QSF 템플릿
├── tests/
│   ├── test_qsf.py
│   ├── test_validate.py
│   └── test_prolific.py
└── docs/
    ├── input_format_spec.md
    └── validation_rules.md
```

## 모듈 import 규칙

- `lib/qsf.py`, `lib/validate.py` → `lib/prolific.py` 등 import 금지
- `lib/prolific.py`, `lib/screening.py`, `lib/monitor.py` → `lib/qsf.py` 등 import 금지 (단, monitor → prolific 은 동일 도메인이므로 허용)
- `shared/state.py` → `lib/` 어떤 파일도 import 금지
- 페이지 파일만 `lib/` 와 `shared/` 둘 다 import

## 사용 흐름

1. **QSF 변환** 페이지에서 설문 텍스트 붙여넣기 → "변환 + 검증"
2. error 0개면 QSF 다운로드 가능
3. Qualtrics에 임포트 → Survey URL 복사 (앱 밖)
4. **Prolific 제어** 페이지에서 API key 저장 → 스터디 DRAFT 생성
5. 같은 페이지에서 Publish, 진행 모니터링, 응답자 승인

## 입력 형식

`docs/input_format_spec.md` 참고.

## 검증 규칙

`docs/validation_rules.md` 참고. 22개 규칙 × pass/fail 케이스로 테스트.

## 테스트

```bash
pytest tests/
```

94개 테스트 모두 통과해야 함.
