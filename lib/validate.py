"""QSF 검증 — 22개 규칙."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel


Severity = Literal["error", "warning", "info"]


class ValidationIssue(BaseModel):
    severity: Severity
    code: str
    location: str
    message: str
    suggestion: str | None = None


class ValidationReport(BaseModel):
    issues: list[ValidationIssue]

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def infos(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "info"]

    @property
    def is_blocked(self) -> bool:
        return len(self.errors) > 0


# ─── 알려진 Qualtrics 질문 type ───
KNOWN_QUESTION_TYPES = {
    "MC", "Matrix", "TE", "DB", "RO", "SBS", "Slider", "DD",
    "Timing", "Captcha", "FileUpload", "Draw", "HotSpot",
    "HeatMap", "GAP", "PGR", "ML", "CS", "TextEntry",
}

# Smart quotes 문자
SMART_QUOTES = ["‘", "’", "“", "”", "–", "—"]


class QSFValidator:
    def __init__(self, qsf: dict, template: dict | None = None):
        self.qsf = qsf
        self.template = template
        self.issues: list[ValidationIssue] = []

    # ─── 헬퍼 ───────────────────────────────────────────────

    def _add(
        self,
        severity: Severity,
        code: str,
        location: str,
        message: str,
        suggestion: str | None = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                severity=severity,
                code=code,
                location=location,
                message=message,
                suggestion=suggestion,
            )
        )

    def _find_element(self, element: str, primary: str) -> dict | None:
        for el in self.qsf.get("SurveyElements", []):
            if el.get("Element") == element and el.get("PrimaryAttribute") == primary:
                return el
        return None

    def _all_blocks(self) -> list[dict]:
        be = self._find_element("BL", "Survey Blocks")
        if be is None:
            return []
        payload = be.get("Payload", [])
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            # Qualtrics emits BL Payload as a dict keyed by string indices.
            return list(payload.values())
        return []

    def _all_questions(self) -> list[dict]:
        return [
            e for e in self.qsf.get("SurveyElements", [])
            if e.get("Element") == "SQ"
        ]

    def _flow_payload(self) -> dict | None:
        fl = self._find_element("FL", "Survey Flow")
        if fl is None:
            return None
        return fl.get("Payload")

    def _walk_flow(self, node: dict | None) -> list[dict]:
        if node is None:
            return []
        out = [node]
        for child in node.get("Flow", []) or []:
            out.extend(self._walk_flow(child))
        return out

    # ─── 22개 규칙 ──────────────────────────────────────────

    def _check_toplevel_keys(self) -> None:
        for key in ("SurveyEntry", "SurveyElements"):
            if key not in self.qsf:
                self._add(
                    "error",
                    "MISSING_TOPLEVEL_KEY",
                    "root",
                    f"최상위 키 '{key}' 누락.",
                    suggestion=f"'{key}' 추가.",
                )

    def _check_survey_entry_fields(self) -> None:
        entry = self.qsf.get("SurveyEntry", {})
        if not isinstance(entry, dict):
            return
        for field in ("SurveyID", "SurveyName", "SurveyLanguage"):
            v = entry.get(field)
            if not v:
                self._add(
                    "error",
                    "MISSING_SURVEY_ENTRY_FIELD",
                    f"SurveyEntry.{field}",
                    f"SurveyEntry 의 '{field}' 가 비어 있거나 없음.",
                )

    def _check_prolific_pid_embed(self) -> None:
        flow = self._flow_payload()
        if flow is None:
            self._add(
                "error",
                "MISSING_PROLIFIC_PID_EMBED",
                "Survey Flow",
                "Survey Flow가 없음.",
            )
            return
        for node in self._walk_flow(flow):
            if node.get("Type") != "EmbeddedData":
                continue
            for ed in node.get("EmbeddedData", []) or []:
                if ed.get("Field") == "PROLIFIC_PID":
                    return
        self._add(
            "error",
            "MISSING_PROLIFIC_PID_EMBED",
            "Survey Flow",
            "Survey Flow에 PROLIFIC_PID embedded data 가 없음.",
            suggestion="EmbeddedData 노드에 Field='PROLIFIC_PID' 추가.",
        )

    def _check_orphan_block_ref(self) -> None:
        blocks = self._all_blocks()
        block_ids = {b.get("ID") for b in blocks}
        flow = self._flow_payload()
        if flow is None:
            return
        for node in self._walk_flow(flow):
            if node.get("Type") == "Standard":
                bid = node.get("ID")
                if bid and bid not in block_ids:
                    self._add(
                        "error",
                        "ORPHAN_BLOCK_REF",
                        f"Survey Flow / {node.get('FlowID', '?')}",
                        f"Survey Flow의 블록 '{bid}' 가 BlockElements에 부재.",
                    )

    def _check_orphan_question_ref(self) -> None:
        question_ids = {
            q.get("PrimaryAttribute") for q in self._all_questions()
        }
        for block in self._all_blocks():
            for be in block.get("BlockElements", []) or []:
                if be.get("Type") != "Question":
                    continue
                qid = be.get("QuestionID")
                if qid and qid not in question_ids:
                    self._add(
                        "error",
                        "ORPHAN_QUESTION_REF",
                        f"Block {block.get('ID', '?')}",
                        f"BlockElements의 QID '{qid}' 가 SurveyElements에 부재.",
                    )

    def _check_invalid_flow_id(self) -> None:
        flow = self._flow_payload()
        if flow is None:
            return
        seen: set[str] = set()
        for node in self._walk_flow(flow):
            fid = node.get("FlowID")
            if fid is None:
                continue
            if not re.match(r"^FL_\d+$", str(fid)):
                self._add(
                    "error",
                    "INVALID_FLOW_ID",
                    f"FlowID {fid}",
                    f"FlowID 형식 오류: '{fid}'. 기대: FL_<숫자>",
                )
            if fid in seen:
                self._add(
                    "error",
                    "INVALID_FLOW_ID",
                    f"FlowID {fid}",
                    f"FlowID '{fid}' 중복.",
                )
            seen.add(fid)

    def _check_matrix_missing_answers(self) -> None:
        for q in self._all_questions():
            payload = q.get("Payload", {})
            if payload.get("QuestionType") != "Matrix":
                continue
            qid = q.get("PrimaryAttribute", "?")
            if not payload.get("Answers"):
                self._add(
                    "error",
                    "MATRIX_MISSING_ANSWERS",
                    f"Question {qid}",
                    "Matrix 질문에 Answers 누락.",
                )
            if not payload.get("Choices"):
                self._add(
                    "error",
                    "MATRIX_MISSING_ANSWERS",
                    f"Question {qid}",
                    "Matrix 질문에 Choices 누락.",
                )

    def _check_matrix_anchor_count(self) -> None:
        for q in self._all_questions():
            payload = q.get("Payload", {})
            if payload.get("QuestionType") != "Matrix":
                continue
            answers = payload.get("Answers", {})
            if not answers:
                continue
            qid = q.get("PrimaryAttribute", "?")
            desc = (
                payload.get("QuestionDescription", "")
                + " " + str(payload.get("Selector", ""))
            ).lower()
            if "likert" in desc and len(answers) != 7:
                self._add(
                    "warning",
                    "MATRIX_ANCHOR_COUNT",
                    f"Question {qid}",
                    f"7점 Likert로 보이지만 Answers가 {len(answers)}개.",
                    suggestion="7점이 표준. Answers 7개 확인.",
                )

    def _check_empty_question_text(self) -> None:
        for q in self._all_questions():
            payload = q.get("Payload", {})
            qid = q.get("PrimaryAttribute", "?")
            text = payload.get("QuestionText", "")
            if not isinstance(text, str) or not text.strip():
                self._add(
                    "error",
                    "EMPTY_QUESTION_TEXT",
                    f"Question {qid}",
                    "QuestionText 가 빈 문자열.",
                )

    def _check_invalid_question_type(self) -> None:
        for q in self._all_questions():
            payload = q.get("Payload", {})
            qid = q.get("PrimaryAttribute", "?")
            qtype = payload.get("QuestionType")
            if qtype is None:
                self._add(
                    "error",
                    "INVALID_QUESTION_TYPE",
                    f"Question {qid}",
                    "QuestionType 누락.",
                )
            elif qtype not in KNOWN_QUESTION_TYPES:
                self._add(
                    "error",
                    "INVALID_QUESTION_TYPE",
                    f"Question {qid}",
                    f"알 수 없는 QuestionType: '{qtype}'.",
                    suggestion=f"허용: {sorted(KNOWN_QUESTION_TYPES)}",
                )

    def _check_encoding_artifact(self) -> None:
        # SurveyName, QuestionText 등에 BOM이 들어있는지 확인
        text = ""
        for q in self._all_questions():
            text += str(q.get("Payload", {}).get("QuestionText", ""))
        if "﻿" in text:
            self._add(
                "warning",
                "ENCODING_ARTIFACT",
                "SurveyElements",
                "BOM (\\ufeff) 문자 발견.",
                suggestion="텍스트에서 BOM 제거.",
            )

    def _check_branch_refs_missing(self) -> None:
        flow = self._flow_payload()
        if flow is None:
            return
        block_ids = {b.get("ID") for b in self._all_blocks()}
        question_ids = {q.get("PrimaryAttribute") for q in self._all_questions()}
        for node in self._walk_flow(flow):
            if node.get("Type") != "Branch":
                continue
            for cond in node.get("BranchLogic", {}).get("0", {}).values() if isinstance(node.get("BranchLogic"), dict) else []:
                if not isinstance(cond, dict):
                    continue
                qid = cond.get("LeftOperand", "")
                m = re.search(r"q://(QID\w+)", str(qid))
                if m and m.group(1) not in question_ids:
                    self._add(
                        "error",
                        "BRANCH_REFS_MISSING",
                        f"Branch {node.get('FlowID', '?')}",
                        f"Branch 가 참조하는 질문 '{m.group(1)}' 부재.",
                    )
            for child in node.get("Flow", []) or []:
                if child.get("Type") == "Standard":
                    bid = child.get("ID")
                    if bid and bid not in block_ids:
                        self._add(
                            "error",
                            "BRANCH_REFS_MISSING",
                            f"Branch {node.get('FlowID', '?')}",
                            f"Branch 가 참조하는 블록 '{bid}' 부재.",
                        )

    def _check_duplicate_qid(self) -> None:
        seen: dict[str, int] = {}
        for q in self._all_questions():
            qid = q.get("PrimaryAttribute")
            if qid is None:
                continue
            seen[qid] = seen.get(qid, 0) + 1
        for qid, count in seen.items():
            if count > 1:
                self._add(
                    "error",
                    "DUPLICATE_QID",
                    f"Question {qid}",
                    f"같은 QID '{qid}' 가 {count}번 등장.",
                )

    def _check_empty_block(self) -> None:
        for block in self._all_blocks():
            if not block.get("BlockElements"):
                self._add(
                    "warning",
                    "EMPTY_BLOCK",
                    f"Block {block.get('ID', '?')}",
                    "BlockElements 가 비어 있음.",
                )

    def _check_unused_block(self) -> None:
        flow = self._flow_payload()
        if flow is None:
            return
        used_ids = {
            n.get("ID") for n in self._walk_flow(flow)
            if n.get("Type") == "Standard"
        }
        for block in self._all_blocks():
            bid = block.get("ID")
            if bid and bid not in used_ids:
                self._add(
                    "info",
                    "UNUSED_BLOCK",
                    f"Block {bid}",
                    f"블록 '{bid}' 가 정의됐지만 Survey Flow에 미등장.",
                )

    def _check_completion_code_missing(self) -> None:
        end_block = None
        for b in self._all_blocks():
            desc = (b.get("Description") or "").lower()
            bid = (b.get("ID") or "").lower()
            if "end" in desc or "end" in bid:
                end_block = b
                break
        if end_block is None:
            return
        end_qids = [
            be.get("QuestionID")
            for be in end_block.get("BlockElements", []) or []
            if be.get("Type") == "Question"
        ]
        for q in self._all_questions():
            if q.get("PrimaryAttribute") not in end_qids:
                continue
            text = q.get("Payload", {}).get("QuestionText", "") or ""
            # "completion code" or "코드" 단어 + 영숫자 6자 이상
            has_token = re.search(
                r"(completion\s*code|코드)[^\w]*[A-Za-z0-9]{6,}",
                text,
                re.IGNORECASE,
            )
            placeholder = "COMPLETION_CODE_PLACEHOLDER" in text
            if has_token and not placeholder:
                return
        self._add(
            "warning",
            "COMPLETION_CODE_MISSING",
            "End block",
            "End 블록에 completion code 가 보이지 않음.",
            suggestion="End 질문 텍스트에 6자 이상 영숫자 코드 삽입.",
        )

    def _check_consent_length(self) -> None:
        consent_block = None
        for b in self._all_blocks():
            desc = (b.get("Description") or "").lower()
            bid = (b.get("ID") or "").lower()
            if "consent" in desc or "consent" in bid:
                consent_block = b
                break
        if consent_block is None:
            return
        consent_qids = [
            be.get("QuestionID")
            for be in consent_block.get("BlockElements", []) or []
            if be.get("Type") == "Question"
        ]
        text = ""
        for q in self._all_questions():
            if q.get("PrimaryAttribute") in consent_qids:
                text += q.get("Payload", {}).get("QuestionText", "") or ""
        if not text:
            return
        if len(text) < 100:
            self._add(
                "info",
                "CONSENT_TOO_SHORT",
                "Consent block",
                f"Consent 길이 {len(text)}자 — IRB 권장 100자 이상.",
            )
        if len(text) > 1500:
            self._add(
                "warning",
                "CONSENT_TOO_LONG",
                "Consent block",
                f"Consent 길이 {len(text)}자 — 1500자 초과.",
            )

    def _check_reverse_index_out_of_range(self) -> None:
        for q in self._all_questions():
            payload = q.get("Payload", {})
            if payload.get("QuestionType") != "Matrix":
                continue
            recode = payload.get("RecodeValues")
            if not isinstance(recode, dict):
                continue
            choices = payload.get("Choices", {})
            n = len(choices) if isinstance(choices, dict) else 0
            qid = q.get("PrimaryAttribute", "?")
            for k in recode.keys():
                try:
                    idx = int(k)
                except (TypeError, ValueError):
                    continue
                if idx < 1 or idx > n:
                    self._add(
                        "error",
                        "REVERSE_INDEX_OUT_OF_RANGE",
                        f"Question {qid}",
                        f"역문항 index {idx} 가 statement 개수({n}) 초과.",
                    )

    def _check_template_drift(self) -> None:
        if self.template is None:
            return
        required_keys = {"SurveyEntry", "SurveyElements"}
        for key in required_keys:
            if key in self.template and key not in self.qsf:
                self._add(
                    "warning",
                    "TEMPLATE_DRIFT",
                    "root",
                    f"표준 템플릿에 있는 '{key}' 가 현재 QSF에 누락.",
                )
        # 템플릿의 PROLIFIC_PID embedded data 가 있었는데 사라졌는지
        tpl_flow = None
        for el in self.template.get("SurveyElements", []):
            if el.get("Element") == "FL":
                tpl_flow = el.get("Payload")
                break
        if tpl_flow is not None:
            tpl_has_pid = any(
                ed.get("Field") == "PROLIFIC_PID"
                for n in self._walk_flow(tpl_flow)
                if n.get("Type") == "EmbeddedData"
                for ed in (n.get("EmbeddedData") or [])
            )
            cur_flow = self._flow_payload()
            cur_has_pid = False
            if cur_flow is not None:
                cur_has_pid = any(
                    ed.get("Field") == "PROLIFIC_PID"
                    for n in self._walk_flow(cur_flow)
                    if n.get("Type") == "EmbeddedData"
                    for ed in (n.get("EmbeddedData") or [])
                )
            if tpl_has_pid and not cur_has_pid:
                self._add(
                    "warning",
                    "TEMPLATE_DRIFT",
                    "Survey Flow",
                    "표준 템플릿의 PROLIFIC_PID embedded data 가 현재 QSF에 없음.",
                )

    def _check_smart_quote(self) -> None:
        all_text = ""
        for q in self._all_questions():
            payload = q.get("Payload", {}) or {}
            all_text += str(payload.get("QuestionText", ""))
            for choice in (payload.get("Choices") or {}).values():
                all_text += str(choice.get("Display", ""))
            for ans in (payload.get("Answers") or {}).values():
                all_text += str(ans.get("Display", ""))
        for ch in SMART_QUOTES:
            if ch in all_text:
                self._add(
                    "info",
                    "SMART_QUOTE_DETECTED",
                    "SurveyElements",
                    f"Smart quote 문자 '{ch}' 발견. ASCII 변환 권장.",
                )
                break

    def _check_trailing_comma(self) -> None:
        # json 모듈은 trailing comma 를 허용하지 않으므로 dict 단계에서는 검출 불가.
        # 대신 현재 dict 가 None 이나 빈 문자열 키를 가지면 경고.
        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "":
                        return True
                    if walk(v):
                        return True
            elif isinstance(obj, list):
                for v in obj:
                    if walk(v):
                        return True
            return False

        if walk(self.qsf):
            self._add(
                "warning",
                "TRAILING_COMMA",
                "root",
                "빈 문자열 키 발견 — 원본 JSON 에 trailing comma 흔적일 수 있음.",
            )

    # ─── 실행 ───────────────────────────────────────────────

    def run(self) -> ValidationReport:
        self.issues = []
        self._check_toplevel_keys()
        self._check_survey_entry_fields()
        self._check_prolific_pid_embed()
        self._check_orphan_block_ref()
        self._check_orphan_question_ref()
        self._check_invalid_flow_id()
        self._check_matrix_missing_answers()
        self._check_matrix_anchor_count()
        self._check_empty_question_text()
        self._check_invalid_question_type()
        self._check_encoding_artifact()
        self._check_branch_refs_missing()
        self._check_duplicate_qid()
        self._check_empty_block()
        self._check_unused_block()
        self._check_completion_code_missing()
        self._check_consent_length()
        self._check_reverse_index_out_of_range()
        self._check_template_drift()
        self._check_smart_quote()
        self._check_trailing_comma()
        return ValidationReport(issues=self.issues)
