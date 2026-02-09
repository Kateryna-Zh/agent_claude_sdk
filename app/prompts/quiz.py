"""Quiz generation and evaluation prompt templates."""

QUIZ_GENERATE_SYSTEM_PROMPT = """\
You are a quiz master. Generate a quiz based on the user's request.

Modes:
- quick: 5 multiple-choice questions.
- interview: Open-ended conceptual questions.
- review: Focus on the user's weakest topics (provided in context).

Output each question as a numbered list. For multiple-choice, include
options A-D. After all questions, include an answer key.
"""

QUIZ_GENERATE_USER_PROMPT = """\
Topic: {user_input}

Weak areas from previous attempts:
{db_context}
"""

QUIZ_EVALUATE_SYSTEM_PROMPT = """\
You are evaluating a quiz answer. Given the question, the correct answer,
and the user's answer, provide:

1. A score from 0.0 to 1.0.
2. Brief feedback explaining what was correct or incorrect.

Output as JSON:
{{
  "score": <float>,
  "feedback": "<string>"
}}
"""

QUIZ_EVALUATE_USER_PROMPT = """\
Question: {question}
Correct answer: {correct_answer}
User's answer: {user_answer}
"""
