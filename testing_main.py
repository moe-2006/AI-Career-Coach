from fastapi import FastAPI
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional
import openai
import os
import json

# Load environment variables
load_dotenv()
print("RUNNING testing_main.py")
print("Working directory:", os.getcwd())
print("OPENAI_API_KEY loaded?", bool(os.getenv("OPENAI_API_KEY")))
print("OPENAI_MODEL loaded?", os.getenv("OPENAI_MODEL"))

app = FastAPI()

# ----- Models -----
class UserAnswer(BaseModel):
    question: str
    correct: bool

class AssessmentRequest(BaseModel):
    career: str
    previous_answers: Optional[List[UserAnswer]] = []
    current_stage: Optional[str] = "intro"

class Resource(BaseModel):
    type: str
    title: str
    link: str

class AssessmentResponse(BaseModel):
    stage: str
    message: str
    next_question: Optional[str] = None
    resources: Optional[List[Resource]] = None
    final_step: bool = False

# ----- OpenAI API Key -----
openai.api_key = os.getenv("OPENAI_API_KEY")

# ----- Endpoint -----
@app.post("/career-assessment", response_model=AssessmentResponse)
async def career_assessment(request: AssessmentRequest):
    stage = request.current_stage or "intro"

    # Format previous answers
    previous_answers_text = "\n".join([
        f"{a.question}: {'correct' if a.correct else 'incorrect'}" 
        for a in request.previous_answers
    ]) or "No previous answers yet."

    # Detect last answer correctness
    last_answer_correct = True
    if request.previous_answers:
        last_answer_correct = request.previous_answers[-1].correct

    # --- Auto-advance for intro stage ---
    if stage == "intro":
        return AssessmentResponse(
            stage="level_1",
            message=(
                f"As a {request.career}, you will develop skills and knowledge relevant to this field. "
                "Let's start testing your abilities!"
            ),
            next_question="What is the primary purpose of using loops in programming?",
            resources=[],
            final_step=False
        )

    # --- Build prompt for AI ---
    prompt = f"""
You are a career coach guiding a user interested in '{request.career}'.
Stage: {stage}
Previous answers: {previous_answers_text}

Instructions:
- Stage 'level_1' and 'level_2': if last answer was correct, advance stage; if incorrect, provide 3-5 learning resources and a retry question.
- Stage 'jobs': provide job listings suitable for skill level.

Return ONLY a JSON object with keys: stage, message, next_question, resources (only if last answer was incorrect), final_step.
"""

    # --- Model selection from .env ---
    allowed_models = ["gpt-3.5-turbo", "gpt-5-nano"]
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    if model not in allowed_models:
        model = "gpt-3.5-turbo"

    max_tokens = 600 if model == "gpt-3.5-turbo" else 1000

    # --- Build OpenAI arguments dynamically ---
    completion_args = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a career assessment AI. Respond only with valid JSON."},
            {"role": "user", "content": prompt + f"\nLast answer was {'correct' if last_answer_correct else 'incorrect'}."}
        ]
    }

    if model == "gpt-3.5-turbo":
        completion_args["max_tokens"] = max_tokens
        completion_args["temperature"] = 0.7
    else:  # GPT-5 nano
        completion_args["max_completion_tokens"] = max_tokens

    # --- Call OpenAI safely ---
    try:
        response = openai.ChatCompletion.create(**completion_args)
        ai_output = response.choices[0].message.content.strip()
        print("AI raw output:", ai_output)
    except openai.error.OpenAIError as e:
        return AssessmentResponse(
            stage=stage,
            message=f"OpenAI API error: {e}",
            final_step=(stage == "jobs")
        )

    # --- Parse AI JSON safely ---
    try:
        ai_json = json.loads(ai_output)
    except json.JSONDecodeError:
        return AssessmentResponse(
            stage=stage,
            message=f"Error parsing AI response. Raw output: {ai_output or 'EMPTY RESPONSE'}",
            final_step=(stage == "jobs")
        )

    # --- Convert resources if last answer was incorrect ---
    resources_list = None
    if not last_answer_correct and "resources" in ai_json and isinstance(ai_json["resources"], list):
        resources_list = [Resource(**r) for r in ai_json["resources"]]

    # --- Return AI response ---
    return AssessmentResponse(
        stage=ai_json.get("stage", stage),
        message=ai_json.get("message", ""),
        next_question=ai_json.get("next_question"),
        resources=resources_list,
        final_step=ai_json.get("final_step", False)
    )
