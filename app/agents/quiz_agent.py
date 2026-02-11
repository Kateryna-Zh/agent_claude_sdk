"""Quiz agent node — generates and evaluates quizzes."""

import json
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
)

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

    evaluation = _extract_evaluation_payload(user_input)
    if evaluation:
        prompt = QUIZ_EVALUATE_SYSTEM_PROMPT + "\n\n" + QUIZ_EVALUATE_USER_PROMPT.format(
            question=evaluation["question"],
            correct_answer=evaluation["correct_answer"],
            user_answer=evaluation["user_answer"],
        )
        llm = get_chat_model()
        logger.info("Quiz evaluation LLM call started")
        response = llm.invoke(prompt)
        logger.info("Quiz evaluation LLM call finished")
        content = getattr(response, "content", str(response)).strip()
        return {"user_response": content, "specialist_output": content}

    quiz_state = state.get("quiz_state") or {}
    answer_key = quiz_state.get("answer_key") or {}
    user_answers = _parse_answer_list(user_input)
    if quiz_state and not answer_key:
        content = (
            "I couldn't find an answer key for the last quiz, so I can't score your answers. "
            "Please ask for a new quiz or paste the answer key."
        )
        return {"user_response": content, "specialist_output": content}
    if answer_key and user_answers:
        score, details, missing = _score_answers(answer_key, user_answers)
        lines = [
            f"Score: {score:.2f}",
            "Results:",
        ]
        lines.extend(details)
        if missing:
            lines.append(
                "Warning: Missing answer key entries for: "
                + ", ".join(str(n) for n in missing)
                + "."
            )
        lines.append("Answer key: " + _format_answer_key(answer_key))
        content = "\n".join(lines).strip()
        return {"user_response": content, "specialist_output": content, "quiz_state": None}

    prompt = QUIZ_GENERATE_SYSTEM_PROMPT + "\n\n" + QUIZ_GENERATE_USER_PROMPT.format(
        user_input=user_input,
        db_context=json.dumps(db_context, ensure_ascii=False),
    )
    llm = get_chat_model()
    logger.info("Quiz generation LLM call started")
    response = llm.invoke(prompt)
    logger.info("Quiz generation LLM call finished")
    content = getattr(response, "content", str(response)).strip()
    generated_answer_key = _extract_answer_key(content)
    question_count = _count_questions(content)
    if not generated_answer_key or (question_count and len(generated_answer_key) != question_count):
        content, generated_answer_key = _retry_append_answer_key(llm, content, question_count)
    if question_count and len(generated_answer_key) != question_count:
        content, generated_answer_key = _retry_regenerate_mcq_only(llm, user_input, question_count)
        question_count = _count_questions(content)
    display_text = _strip_answer_key(content)
    quiz_state_update = {
        "answer_key": generated_answer_key,
        "quiz_text": display_text,
        "question_count": question_count,
    }
    return {"user_response": display_text, "specialist_output": display_text, "quiz_state": quiz_state_update}


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

    inline_pattern = r"(\d+)\s*[\).:-]?\s*([A-D])"
    for match in re.finditer(inline_pattern, key_block, flags=re.IGNORECASE):
        number = int(match.group(1))
        letter = match.group(2).upper()
        answer_key[number] = letter

    if not answer_key:
        line_pattern = re.compile(r"^\s*(\d+)\s*[:\)\.\-]\s*([A-D])\b", re.IGNORECASE)
        for line in lines:
            match = line_pattern.search(line)
            if match:
                number = int(match.group(1))
                letter = match.group(2).upper()
                answer_key[number] = letter

    if not answer_key:
        for match in re.finditer(inline_pattern, text, flags=re.IGNORECASE):
            number = int(match.group(1))
            letter = match.group(2).upper()
            answer_key[number] = letter

    return answer_key


def _parse_answer_list(text: str) -> dict[int, str]:
    answers: dict[int, str] = {}
    for match in re.finditer(r"(\d+)\s*[\).:-]?\s*([A-D])", text, flags=re.IGNORECASE):
        answers[int(match.group(1))] = match.group(2).upper()
    return answers


def _score_answers(
    answer_key: dict[int, str],
    user_answers: dict[int, str],
) -> tuple[float, list[str], list[int]]:
    total = len(answer_key)
    if total == 0:
        return 0.0, ["No answer key found to score against."], []
    correct = 0
    details: list[str] = []
    missing: list[int] = []
    for number in sorted(answer_key.keys()):
        expected = answer_key[number]
        got = user_answers.get(number)
        if got == expected:
            correct += 1
            details.append(f"{number}. ✅ ({got})")
        else:
            details.append(f"{number}. ❌ (you: {got or '—'}, correct: {expected})")
    for number in sorted(user_answers.keys()):
        if number not in answer_key:
            missing.append(number)
            details.append(f"{number}. ⚠️ (no answer key entry; you answered {user_answers[number]})")
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
    response = llm.invoke(prompt)
    logger.info("Quiz answer key retry LLM call finished")
    key_text = getattr(response, "content", str(response)).strip()
    answer_key = _extract_answer_key(key_text)
    if answer_key:
        if "answer key" not in quiz_text.lower():
            quiz_text = quiz_text.rstrip() + "\n\n" + key_text
        return quiz_text, answer_key
    return quiz_text, {}


def _retry_regenerate_mcq_only(llm, user_input: str, question_count: int | None) -> tuple[str, dict[int, str]]:
    count_hint = f"{question_count}" if question_count else "the requested"
    prompt = (
        "Regenerate the quiz as multiple-choice questions only.\n"
        "Rules:\n"
        f"- Produce exactly {count_hint} questions.\n"
        "- Each question must have options A-D.\n"
        "- Do NOT include any open-ended questions.\n"
        "- Provide an answer key that matches the number of questions exactly.\n"
        "Format the answer key as: Answer key: 1:A, 2:B\n\n"
        f"Topic: {user_input}"
    )
    logger.info("Quiz regeneration LLM call started")
    response = llm.invoke(prompt)
    logger.info("Quiz regeneration LLM call finished")
    quiz_text = getattr(response, "content", str(response)).strip()
    answer_key = _extract_answer_key(quiz_text)
    return quiz_text, answer_key


def _count_questions(text: str) -> int:
    numbers = set()
    for match in re.finditer(r"^\s*(\d+)\s*[\).]", text, flags=re.MULTILINE):
        numbers.add(int(match.group(1)))
    return len(numbers)
