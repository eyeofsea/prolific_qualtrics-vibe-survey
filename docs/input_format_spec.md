# 입력 텍스트 양식

학생이 textarea에 붙여넣는 마크다운 형식. 헤더 단위로 파싱.

## 전체 구조

```markdown
# SURVEY: <연구 제목>

## CONSENT
<동의서 텍스트>

## DEMOGRAPHICS
<인구통계 질문들>

## SCALE: <name>
<척도 문항들>

## ATTENTION_CHECK
<주의 검사>

## END
COMPLETION_CODE: <코드>
```

## 섹션별 규칙

### `# SURVEY: <제목>`
- 최상위 레벨 (`#` 1개) 헤더, 첫 줄에 위치
- `:` 뒤의 텍스트가 `SurveyEntry.SurveyName`이 됨

### `## CONSENT`
- 다음 `##` 전까지 모든 텍스트가 동의서 본문
- 한 단락 또는 여러 단락 모두 가능
- 빈 섹션이면 파싱 실패

### `## DEMOGRAPHICS`
- `Q:`, `TYPE:`, 선택지(`- `)의 반복
- `TYPE:` 허용값: `SingleChoice`, `MultiChoice`, `Text`
- `Text` 타입은 선택지가 없어도 됨

```
Q: 귀하의 연령대는?
TYPE: SingleChoice
- 19-29세
- 30-39세
- 40-49세
- 50세 이상
```

### `## SCALE: <name>`
- 표준 QSF 템플릿의 매트릭스 슬롯에 매핑
- 슬롯 순서: `AS`, `RC`, `ID`, `DV`, `HCD`
- `<name>`이 위 5개 중 하나면 그 슬롯에 매핑
- 그 외 이름이면 빈 슬롯에 순서대로 채움
- SCALE 수는 최대 5개
- `ANCHOR:` 한 줄로 anchor 지정 (예: `7-point Likert`)
- `- 문항. [REVERSE]` 표기 시 그 번호가 `reverse_indices`에 추가

```
## SCALE: AS
ANCHOR: 7-point Likert (전혀 동의하지 않는다 ~ 매우 동의한다)
- 나는 변화에 빠르게 적응한다.
- 새로운 환경이 두렵다. [REVERSE]
- 변화는 기회를 만든다.
```

### `## ATTENTION_CHECK` (선택)
- `TEXT:` — 응답자에게 보일 지시문
- `EXPECTED:` — 정답 (정수)
- 섹션 자체가 없으면 attention check 블록은 QSF에서 제외

```
## ATTENTION_CHECK
TEXT: 주의 깊게 읽고 있다면 '5번 (약간 동의한다)'을 선택해 주세요.
EXPECTED: 5
```

### `## END`
- `COMPLETION_CODE:` 한 줄 — Prolific Completion Code
- 6자 이상 영숫자 권장

```
## END
COMPLETION_CODE: ABC12345
```

## 매트릭스 매핑 예시

학생이 다음과 같이 입력하면:

```
## SCALE: ID
...
## SCALE: AS
...
```

→ AS 슬롯에 두 번째 SCALE, ID 슬롯에 첫 번째 SCALE이 매핑되고, RC/DV/HCD 슬롯의 매트릭스 블록은 Survey Flow에서 제거.

statements 수가 템플릿 슬롯의 기본 statement 수보다 적으면 BlockElements가 축소되고, 많으면 매트릭스 Choices에 추가.
