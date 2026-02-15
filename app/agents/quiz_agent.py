"""Quiz agent node — generates and evaluates quizzes."""

import logging
import re
from typing import Any

from app.llm.ollama_client import get_chat_model
from app.models.state import GraphState
from app.prompts.quiz import (
    QUIZ_EVALUATE_SYSTEM_PROMPT,
    QUIZ_EVALUATE_USER_PROMPT,
    QUIZ_GENERATE_SYSTEM_PROMPT,
    QUIZ_GENERATE_USER_PROMPT,
    QUIZ_RAG_RELEVANCE_SYSTEM_PROMPT,
    QUIZ_RAG_RELEVANCE_USER_PROMPT,
)
from app.utils.constants import (
    LINE_START_ANSWER_RE,
    MIN_KEYWORD_OVERLAP,
    NUMBERED_ANSWER_RE,
    STOPWORDS,
)
from app.utils.llm_helpers import invoke_llm

logger = logging.getLogger("uvicorn.error")


def quiz_node(state: GraphState) -> dict:
    """Generate quiz questions or evaluate a quiz answer.

    Populates: specialist_output.

    Parameters
    ----------
    state : GraphState

    Returns
    -------
    dict
        Partial state update with ``specialist_output``.
    """
    user_input = (state.get("user_input") or "").strip()
    db_context = state.get("db_context") or {}
    rag_context = state.get("rag_context", "")

    evaluation_result = _handle_evaluation(user_input)
    if evaluation_result is not None:
        return evaluation_result

    quiz_state = state.get("quiz_state") or {}
    answer_key = quiz_state.get("answer_key") or {}
    user_answers = _parse_answer_list(user_input)
    if quiz_state and not answer_key:
        content = (
            "I couldn't find an answer key for the last quiz, so I can't score your answers. "
            "Please ask for a new quiz or paste the answer key."
        )
        logger.info("quiz_node: next_action=format_response (missing answer key)")
        return {
            "user_response": content,
            "specialist_output": content,
            "quiz_next_action": "format_response",
        }
    if answer_key and user_answers:
        return _handle_scoring(quiz_state, answer_key, user_answers, db_context)

    wrong_questions_raw = db_context.get("wrong_questions") or []
    wrong_questions_text = _format_wrong_questions(wrong_questions_raw)
    topic_name = db_context.get("quiz_topic_name")

    rag_context = _check_rag_relevance(rag_context, topic_name, user_input)

    return _generate_quiz(
        user_input, rag_context, wrong_questions_text, db_context, wrong_questions_raw,
    )


def _handle_evaluation(user_input: str) -> dict | None:
    """Check for evaluation payload, invoke LLM, return result."""
    evaluation = _extract_evaluation_payload(user_input)
    if not evaluation:
        return None
    prompt = QUIZ_EVALUATE_SYSTEM_PROMPT + "\n\n" + QUIZ_EVALUATE_USER_PROMPT.format(
        question=evaluation["question"],
        correct_answer=evaluation["correct_answer"],
        user_answer=evaluation["user_answer"],
    )
    logger.info("Quiz evaluation LLM call started")
    content = invoke_llm(prompt)
    logger.info("Quiz evaluation LLM call finished")
    logger.info("quiz_node: next_action=format_response (evaluation)")
    return {
        "user_response": content,
        "specialist_output": content,
        "quiz_next_action": "format_response",
    }


def _handle_scoring(
    quiz_state: dict[str, Any],
    answer_key: dict[int, str],
    user_answers: dict[int, str],
    db_context: dict[str, Any],
) -> dict:
    """Score answers, build quiz_save payload."""
    score, details, missing = _score_answers(answer_key, user_answers)
    lines = [f"Score: {score:.2f}"]
    correct_lines = []
    wrong_lines = []
    missing_lines = []
    for entry in details:
        status = entry.get("status")
        if status == "error":
            lines.append(entry.get("message", "Scoring error."))
            continue
        number = entry.get("number")
        got = entry.get("got")
        expected = entry.get("expected")
        if status == "correct":
            correct_lines.append(f"{number}. ✅ ({got})")
        elif status == "wrong":
            wrong_lines.append(f"{number}. ❌ (you: {got}, correct: {expected})")
        elif status == "missing":
            missing_lines.append(f"{number}. ⚠️ (no key; you answered {got})")
    if correct_lines:
        lines.append("Correct:")
        lines.extend(correct_lines)
    if wrong_lines:
        lines.append("Wrong:")
        lines.extend(wrong_lines)
    if missing_lines:
        lines.append("No answer key:")
        lines.extend(missing_lines)
    if missing:
        lines.append(
            "Warning: Missing answer key entries for: "
            + ", ".join(str(n) for n in missing)
            + "."
        )
    lines.append("Answer key: " + _format_answer_key(answer_key))
    content = "\n".join(lines).strip()

    # Build quiz_save payload for db_agent
    quiz_save = _build_quiz_save(
        quiz_state, answer_key, user_answers,
    )
    if quiz_save:
        db_context["quiz_save"] = quiz_save

    next_action = "db" if quiz_save else "format_response"
    logger.info("quiz_node: next_action=%s (scoring)", next_action)
    return {
        "user_response": content,
        "specialist_output": content,
        "quiz_state": None,
        "db_context": db_context,
        "quiz_feedback": content,
        "quiz_next_action": next_action,
    }


def _check_rag_relevance(rag_context: str, topic_name: str | None, user_input: str) -> str:
    """Two-pass relevance filter: fast substring match, then LLM judgment.

    First checks if the topic name appears directly in the RAG context (fast path).
    If not found, asks the LLM to judge whether the context is relevant to the
    user's quiz request. Returns the original rag_context if relevant, or empty
    string if not.
    """
    if not rag_context.strip():
        return rag_context
    topic_hint = (topic_name or user_input).strip().lower()
    if topic_hint and topic_hint in rag_context.lower():
        logger.info("quiz_node: rag_context kept (topic match)")
        return rag_context
    relevance_prompt = (
        QUIZ_RAG_RELEVANCE_SYSTEM_PROMPT
        + "\n\n"
        + QUIZ_RAG_RELEVANCE_USER_PROMPT.format(
            user_input=user_input,
            rag_context=rag_context,
        )
    )
    logger.info("Quiz RAG relevance check started")
    relevance = invoke_llm(relevance_prompt).upper()
    logger.info("Quiz RAG relevance check finished")
    if not relevance.startswith("YES"):
        logger.info("quiz_node: rag_context dropped (relevance=%s)", relevance)
        return ""
    logger.info("quiz_node: rag_context kept (relevance=YES)")
    return rag_context


def _generate_quiz(
    user_input: str,
    rag_context: str,
    wrong_questions_text: str,
    db_context: dict[str, Any],
    wrong_questions_raw: list[dict[str, Any]],
) -> dict:
    """Generate quiz, extract/retry answer key."""
    prompt = QUIZ_GENERATE_SYSTEM_PROMPT + "\n\n" + QUIZ_GENERATE_USER_PROMPT.format(
        user_input=user_input,
        rag_context=rag_context,
        wrong_questions=wrong_questions_text,
    )
    llm = get_chat_model()
    logger.info("Quiz generation LLM call started")
    content = invoke_llm(prompt, llm)
    logger.info("Quiz generation LLM call finished")
    generated_answer_key = _extract_answer_key(content)
    question_count = _count_questions(content)
    # Two-stage answer key recovery:
    # 1. Ask the LLM to produce just the answer key for the generated quiz.
    if not generated_answer_key or (question_count and len(generated_answer_key) != question_count):
        content, generated_answer_key = _retry_append_answer_key(llm, content, question_count)
    # 2. If still mismatched, regenerate the entire quiz as MCQ-only with a strict format.
    if question_count and len(generated_answer_key) != question_count:
        content, generated_answer_key = _retry_regenerate_mcq_only(llm, user_input, question_count, rag_context)
        question_count = _count_questions(content)
    display_text = _strip_answer_key(content)

    # Track which generated questions correspond to retry attempt_ids
    retry_attempt_ids = _match_retry_questions(display_text, wrong_questions_raw)

    topic_id = db_context.get("quiz_topic_id")
    topic_name = db_context.get("quiz_topic_name")
    quiz_state_update = {
        "answer_key": generated_answer_key,
        "quiz_text": display_text,
        "question_count": question_count,
        "topic_id": topic_id,
        "topic_name": topic_name,
        "retry_attempt_ids": retry_attempt_ids,
    }
    logger.info("quiz_node: next_action=format_response (generation)")
    return {
        "user_response": display_text,
        "specialist_output": display_text,
        "quiz_state": quiz_state_update,
        "quiz_next_action": "format_response",
    }


def _extract_evaluation_payload(text: str) -> dict[str, Any] | None:
    question = None
    correct_answer = None
    user_answer = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if lower.startswith("question:"):
            question = line.split(":", 1)[1].strip()
        elif lower.startswith("correct answer:"):
            correct_answer = line.split(":", 1)[1].strip()
        elif lower.startswith("user answer:") or lower.startswith("my answer:"):
            user_answer = line.split(":", 1)[1].strip()

    if question and correct_answer and user_answer:
        return {
            "question": question,
            "correct_answer": correct_answer,
            "user_answer": user_answer,
        }

    return None


def _extract_answer_key(text: str) -> dict[int, str]:
    answer_key: dict[int, str] = {}
    lines = text.splitlines()
    start_idx = None
    for idx, line in enumerate(lines):
        if "answer key" in line.lower():
            start_idx = idx
            break

    if start_idx is not None:
        key_block = " ".join(lines[start_idx : start_idx + 5])
    else:
        key_block = text

    for match in NUMBERED_ANSWER_RE.finditer(key_block):
        number = int(match.group(1))
        letter = match.group(2).upper()
        answer_key[number] = letter

    if not answer_key:
        for line in lines:
            match = LINE_START_ANSWER_RE.search(line)
            if match:
                number = int(match.group(1))
                letter = match.group(2).upper()
                answer_key[number] = letter

    if not answer_key:
        for match in NUMBERED_ANSWER_RE.finditer(text):
            number = int(match.group(1))
            letter = match.group(2).upper()
            answer_key[number] = letter

    return answer_key


def _parse_answer_list(text: str) -> dict[int, str]:
    answers: dict[int, str] = {}
    for match in NUMBERED_ANSWER_RE.finditer(text):
        answers[int(match.group(1))] = match.group(2).upper()
    return answers


def _score_answers(
    answer_key: dict[int, str],
    user_answers: dict[int, str],
) -> tuple[float, list[dict[str, Any]], list[int]]:
    total = len(answer_key)
    if total == 0:
        return 0.0, [{"status": "error", "message": "No answer key found to score against."}], []
    correct = 0
    details: list[dict[str, Any]] = []
    missing: list[int] = []
    for number in sorted(answer_key.keys()):
        expected = answer_key[number]
        got = user_answers.get(number)
        if got == expected:
            correct += 1
            details.append(
                {"number": number, "status": "correct", "got": got, "expected": expected}
            )
        else:
            details.append(
                {"number": number, "status": "wrong", "got": got or "—", "expected": expected}
            )
    for number in sorted(user_answers.keys()):
        if number not in answer_key:
            missing.append(number)
            details.append(
                {
                    "number": number,
                    "status": "missing",
                    "got": user_answers[number],
                    "expected": None,
                }
            )
    score = correct / total
    return score, details, missing


def _format_answer_key(answer_key: dict[int, str]) -> str:
    parts = [f"{k}:{answer_key[k]}" for k in sorted(answer_key)]
    return ", ".join(parts)


def _strip_answer_key(text: str) -> str:
    lines = text.splitlines()
    cleaned: list[str] = []
    for line in lines:
        if "answer key" in line.lower():
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _retry_append_answer_key(llm, quiz_text: str, question_count: int | None) -> tuple[str, dict[int, str]]:
    key_example = "Answer key: 1:A, 2:B"
    if question_count and question_count > 2:
        pairs = [f"{i}:A" for i in range(1, question_count + 1)]
        key_example = "Answer key: " + ", ".join(pairs)
    prompt = (
        "You generated the quiz below. Return ONLY the answer key in this exact format:\n"
        f"{key_example}\n\n"
        "Quiz:\n"
        f"{quiz_text}"
    )
    logger.info("Quiz answer key retry LLM call started")
    key_text = invoke_llm(prompt, llm)
    logger.info("Quiz answer key retry LLM call finished")
    answer_key = _extract_answer_key(key_text)
    if answer_key:
        if "answer key" not in quiz_text.lower():
            quiz_text = quiz_text.rstrip() + "\n\n" + key_text
        return quiz_text, answer_key
    return quiz_text, {}


def _retry_regenerate_mcq_only(llm, user_input: str, question_count: int | None, rag_context: str = "") -> tuple[str, dict[int, str]]:
    count_hint = f"{question_count}" if question_count else "the requested"
    context_block = f"\n\nKnowledge base context:\n{rag_context}" if rag_context.strip() else ""
    prompt = (
        "Regenerate the quiz as multiple-choice questions only.\n"
        "Rules:\n"
        f"- Produce exactly {count_hint} questions.\n"
        "- Each question must have options A-D.\n"
        "- Do NOT include any open-ended questions.\n"
        "- Provide an answer key that matches the number of questions exactly.\n"
        "Format the answer key as: Answer key: 1:A, 2:B\n\n"
        f"Topic: {user_input}"
        f"{context_block}"
    )
    logger.info("Quiz regeneration LLM call started")
    quiz_text = invoke_llm(prompt, llm)
    logger.info("Quiz regeneration LLM call finished")
    answer_key = _extract_answer_key(quiz_text)
    return quiz_text, answer_key


def _count_questions(text: str) -> int:
    numbers = set()
    for match in re.finditer(r"^\s*(\d+)\s*[\).]", text, flags=re.MULTILINE):
        numbers.add(int(match.group(1)))
    return len(numbers)


def _extract_questions(text: str) -> dict[int, str]:
    """Parse quiz text into {question_number: question_text} dict."""
    questions: dict[int, str] = {}
    pattern = re.compile(r"^\s*(\d+)\s*[\).]\s*(.+)", re.MULTILINE)
    for match in pattern.finditer(text):
        number = int(match.group(1))
        question_text = match.group(2).strip()
        # Only capture the question line (before options A-D)
        if not re.match(r"^[A-D][\).:]", question_text, re.IGNORECASE):
            questions[number] = question_text
    return questions


def _format_wrong_questions(wrong_questions: list[dict[str, Any]]) -> str:
    """Format wrong questions from DB into numbered text for the prompt."""
    if not wrong_questions:
        return "None"
    lines = []
    for i, wq in enumerate(wrong_questions, 1):
        lines.append(f"{i}. {wq.get('question', '')}")
    return "\n".join(lines)


def _match_retry_questions(
    quiz_text: str, wrong_questions: list[dict[str, Any]],
) -> dict[int, int]:
    """Map generated question numbers to DB attempt_ids for retry questions.

    Uses simple keyword overlap to match generated questions with previously
    wrong questions from the DB.

    Returns {question_number: attempt_id}.
    """
    if not wrong_questions:
        return {}

    generated = _extract_questions(quiz_text)
    retry_map: dict[int, int] = {}

    for wq in wrong_questions:
        attempt_id = wq.get("attempt_id")
        wq_text = (wq.get("question") or "").lower()
        if not wq_text or not attempt_id:
            continue
        # Remove common stopwords to focus overlap on meaningful content words.
        wq_words = set(re.findall(r"\w+", wq_text)) - STOPWORDS
        best_num = None
        best_overlap = 0
        for num, gen_text in generated.items():
            if num in retry_map:
                continue
            gen_words = set(re.findall(r"\w+", gen_text.lower()))
            overlap = len(wq_words & gen_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_num = num
        # Require at least MIN_KEYWORD_OVERLAP matching words to consider it a retry.
        if best_num is not None and best_overlap >= MIN_KEYWORD_OVERLAP:
            retry_map[best_num] = attempt_id

    return retry_map


def _build_quiz_save(
    quiz_state: dict[str, Any],
    answer_key: dict[int, str],
    user_answers: dict[int, str],
) -> dict[str, Any] | None:
    """Build a quiz_save payload for the db_agent after scoring."""
    topic_id = quiz_state.get("topic_id")
    if topic_id is None:
        return None

    quiz_text = quiz_state.get("quiz_text") or ""
    questions = _extract_questions(quiz_text)
    retry_attempt_ids = quiz_state.get("retry_attempt_ids") or {}

    wrong_answers: list[dict[str, Any]] = []
    correct_retries: list[int] = []

    for number in sorted(answer_key.keys()):
        expected = answer_key[number]
        got = user_answers.get(number)
        question_text = questions.get(number, f"Question {number}")

        if got == expected:
            # Correct — if this was a retry, mark for deletion
            if number in retry_attempt_ids:
                correct_retries.append(retry_attempt_ids[number])
        else:
            # Wrong — save for future re-quiz (skip if already a retry in DB)
            if number not in retry_attempt_ids:
                wrong_answers.append({
                    "question": question_text,
                    "user_answer": got,
                })

    if not wrong_answers and not correct_retries:
        return None

    return {
        "topic_id": topic_id,
        "wrong_answers": wrong_answers,
        "correct_retries": correct_retries,
    }
