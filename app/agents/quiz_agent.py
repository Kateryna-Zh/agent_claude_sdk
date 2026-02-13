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
        logger.info("quiz_node: next_action=format_response (evaluation)")
        print("quiz_node next_action -> format_response (evaluation)")
        return {
            "user_response": content,
            "specialist_output": content,
            "quiz_next_action": "format_response",
        }

    quiz_state = state.get("quiz_state") or {}
    answer_key = quiz_state.get("answer_key") or {}
    user_answers = _parse_answer_list(user_input)
    if quiz_state and not answer_key:
        content = (
            "I couldn't find an answer key for the last quiz, so I can't score your answers. "
            "Please ask for a new quiz or paste the answer key."
        )
        logger.info("quiz_node: next_action=format_response (missing answer key)")
        print("quiz_node next_action -> format_response (missing answer key)")
        return {
            "user_response": content,
            "specialist_output": content,
            "quiz_next_action": "format_response",
        }
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

        # Build quiz_save payload for db_agent
        quiz_save = _build_quiz_save(
            quiz_state, answer_key, user_answers,
        )
        if quiz_save:
            db_context["quiz_save"] = quiz_save

        next_action = "db" if quiz_save else "format_response"
        logger.info("quiz_node: next_action=%s (scoring)", next_action)
        print(f"quiz_node next_action -> {next_action} (scoring)")
        return {
            "user_response": content,
            "specialist_output": content,
            "quiz_state": None,
            "db_context": db_context,
            "quiz_next_action": next_action,
        }

    # Format wrong questions from db_context for the prompt
    wrong_questions_raw = db_context.get("wrong_questions") or []
    wrong_questions_text = _format_wrong_questions(wrong_questions_raw)
    topic_id = db_context.get("quiz_topic_id")
    topic_name = db_context.get("quiz_topic_name")

    # Agentic KB relevance check: drop rag_context if it doesn't match topic.
    if rag_context.strip():
        relevance_prompt = (
            QUIZ_RAG_RELEVANCE_SYSTEM_PROMPT
            + "\n\n"
            + QUIZ_RAG_RELEVANCE_USER_PROMPT.format(
                user_input=user_input,
                rag_context=rag_context,
            )
        )
        llm = get_chat_model()
        logger.info("Quiz RAG relevance check started")
        relevance_resp = llm.invoke(relevance_prompt)
        logger.info("Quiz RAG relevance check finished")
        relevance = getattr(relevance_resp, "content", str(relevance_resp)).strip().upper()
        if not relevance.startswith("YES"):
            rag_context = ""
            logger.info("quiz_node: rag_context dropped (relevance=%s)", relevance)
            print(f"quiz_node rag_context -> dropped (relevance={relevance})")
        else:
            logger.info("quiz_node: rag_context kept (relevance=YES)")
            print("quiz_node rag_context -> kept (relevance=YES)")

    prompt = QUIZ_GENERATE_SYSTEM_PROMPT + "\n\n" + QUIZ_GENERATE_USER_PROMPT.format(
        user_input=user_input,
        rag_context=rag_context,
        wrong_questions=wrong_questions_text,
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
        content, generated_answer_key = _retry_regenerate_mcq_only(llm, user_input, question_count, rag_context)
        question_count = _count_questions(content)
    display_text = _strip_answer_key(content)

    # Track which generated questions correspond to retry attempt_ids
    retry_attempt_ids = _match_retry_questions(display_text, wrong_questions_raw)

    quiz_state_update = {
        "answer_key": generated_answer_key,
        "quiz_text": display_text,
        "question_count": question_count,
        "topic_id": topic_id,
        "topic_name": topic_name,
        "retry_attempt_ids": retry_attempt_ids,
    }
    logger.info("quiz_node: next_action=format_response (generation)")
    print("quiz_node next_action -> format_response (generation)")
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
        wq_words = set(re.findall(r"\w+", wq_text)) - {"the", "a", "an", "is", "of", "in", "to", "and", "or"}
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
        if best_num is not None and best_overlap >= 2:
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
