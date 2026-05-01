# QSF 검증 규칙 22개

`lib/validate.py:QSFValidator.run()` 가 차례로 적용. 결과는 `ValidationReport.issues`.

| # | 코드 | 심각도 | 점검 |
|---|------|--------|------|
| 1 | `MISSING_TOPLEVEL_KEY` | error | `SurveyEntry`, `SurveyElements` 둘 다 존재 |
| 2 | `MISSING_SURVEY_ENTRY_FIELD` | error | `SurveyID`, `SurveyName`, `SurveyLanguage` |
| 3 | `MISSING_PROLIFIC_PID_EMBED` | error | Survey Flow에 `PROLIFIC_PID` embedded data |
| 4 | `ORPHAN_BLOCK_REF` | error | Survey Flow의 `BL_xxx` 가 BlockElements에 부재 |
| 5 | `ORPHAN_QUESTION_REF` | error | BlockElements의 QID 가 SurveyElements에 부재 |
| 6 | `INVALID_FLOW_ID` | error | FlowID 중복 또는 형식 오류 (`FL_<숫자>` 아님) |
| 7 | `MATRIX_MISSING_ANSWERS` | error | Matrix 질문에 Answers 또는 Choices 누락 |
| 8 | `MATRIX_ANCHOR_COUNT` | warning | 7점 Likert인데 Answers ≠ 7개 |
| 9 | `EMPTY_QUESTION_TEXT` | error | QuestionText 가 빈 문자열 |
| 10 | `INVALID_QUESTION_TYPE` | error | 알려진 type 외 (MC, Matrix, TE, DB 등) |
| 11 | `ENCODING_ARTIFACT` | warning | non-UTF-8, BOM |
| 12 | `BRANCH_REFS_MISSING` | error | Branch flow의 참조 ID 부재 |
| 13 | `DUPLICATE_QID` | error | 같은 QID 중복 |
| 14 | `EMPTY_BLOCK` | warning | 어떤 블록의 BlockElements 가 비어 있음 |
| 15 | `UNUSED_BLOCK` | info | 정의됐지만 Survey Flow에 미등장 |
| 16 | `COMPLETION_CODE_MISSING` | warning | End 블록에 completion code 없음 |
| 17 | `CONSENT_TOO_SHORT` | info | Consent < 100자 |
| 18 | `CONSENT_TOO_LONG` | warning | Consent > 1500자 |
| 19 | `REVERSE_INDEX_OUT_OF_RANGE` | error | 역문항 index 가 statement 개수 초과 |
| 20 | `TEMPLATE_DRIFT` | warning | 표준 템플릿 필수 키 누락 (template 인자 있을 때만) |
| 21 | `SMART_QUOTE_DETECTED` | info | `‘`, `’`, `“`, `”` 등 → ASCII 변환 권장 |
| 22 | `TRAILING_COMMA` | warning | json 모듈은 자동 제거하지만 흔적(빈 문자열 키) 발견 시 경고 |

## 보고서 사용

```python
report = QSFValidator(qsf, template=template).run()

if report.is_blocked:
    # error 가 1개라도 있으면 다운로드 막힘
    for e in report.errors:
        print(e.code, e.message)
else:
    # warning, info 만 있으면 다운로드 가능
    for w in report.warnings:
        print(w.code, w.message)
```

## 심각도 기준

- **error**: QSF 가 Qualtrics 임포트 또는 Prolific 연동에서 실패할 가능성이 높음. 다운로드 차단.
- **warning**: 임포트는 가능하나 데이터 품질·연구 윤리·UX 문제 가능. 다운로드 허용.
- **info**: 권장 사항. 무시 가능.
