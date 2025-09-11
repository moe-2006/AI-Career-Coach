from fastapi import FastAPI
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional
import openai
import os
import json

# Load environment variables
load_dotenv()

app = FastAPI()

# ----- Models -----
class UserAnswer(BaseModel):
    question: str
    correct: bool

class AssessmentRequest(BaseModel):
    career: str
    previous_answers: Optional[List[UserAnswer]] = []
    current_stage: Optional[str] = "intro"
    total_questions: Optional[int] = 3

class Resource(BaseModel):
    type: str
    title: str
    link: Optional[str] = None

class AssessmentResponse(BaseModel):
    stage: str
    message: str
    next_question: Optional[str] = None
    resources: Optional[List[Resource]] = None
    final_step: bool = False

# ----- OpenAI API Key -----
openai.api_key = os.getenv("OPENAI_API_KEY")

# ----- Helper: safe AI call -----
def call_ai_debug(prompt: str, max_tokens: int, fallback_question: str, stage: str = "") -> dict:
    """
    Call OpenAI safely with debug logs and parse JSON.
    Ensures 'stage' is always a string and resources are properly handled.
    """
    for attempt in range(2):
        try:
            print(f"\n--- AI Call Attempt {attempt + 1} ---")
            print(f"Prompt length: {len(prompt)} characters")

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a career assessment AI. Provide output as JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )

            ai_output = response.choices[0].message.content
            print("Raw AI output:", repr(ai_output))

            ai_json = json.loads(ai_output)

            # Ensure 'stage' is a string
            ai_stage = ai_json.get("stage", stage)
            if not isinstance(ai_stage, str):
                ai_stage = str(ai_stage)

            # Handle resources/jobs
            resources_list: Optional[List[Resource]] = None
            raw_resources = ai_json.get("resources")
            if raw_resources and isinstance(raw_resources, list):
                resources_list = []
                for r in raw_resources:
                    if isinstance(r, dict):
                        try:
                            resources_list.append(Resource(**r))
                        except Exception as e:
                            print(f"Skipping invalid resource dict: {r}, reason: {e}")
                    elif isinstance(r, str):
                        resources_list.append(Resource(type="job", title=r, link=""))

            return {
                "stage": ai_stage,
                "message": ai_json.get("message", ""),
                "next_question": ai_json.get("next_question"),
                "resources": resources_list,
                "final_step": bool(ai_json.get("final_step", False))
            }

        except Exception as e:
            print(f"AI call failed on attempt {attempt + 1}: {e}")
            if attempt == 1:
                return {
                    "stage": stage or "intro",
                    "message": f"An error occurred. ({e})",
                    "next_question": fallback_question,
                    "resources": None,
                    "final_step": False
                }

# ----- Endpoint -----
@app.post("/career-assessment", response_model=AssessmentResponse)
async def career_assessment(request: AssessmentRequest):
    stage = request.current_stage or "intro"
    total_questions = request.total_questions or 3

    previous_answers_text = "\n".join([
        f"{a.question}: {'correct' if a.correct else 'incorrect'}" 
        for a in request.previous_answers
    ]) or "No previous answers yet."

    last_answer_correct = True
    if request.previous_answers:
        last_answer_correct = request.previous_answers[-1].correct

    correct_answers_count = sum(1 for a in request.previous_answers if a.correct)

    # Move to jobs stage only when correct answers reach total_questions
    if correct_answers_count >= total_questions:
        stage = "jobs"

    # --- Stage-specific prompts ---
    if stage == "intro":
        prompt = f"""
You are a career coach AI.
The user wants to pursue a career as a '{request.career}'.
Your response must be a valid JSON object.

Task:
- Introduce the role of a {request.career}.
- Provide the first **technical/skill-testing question** for a beginner in this career.
  Do NOT ask motivational or personal questions.
- Ensure 'stage' is a string.
- Output keys: stage, message, next_question, final_step.
"""
        fallback_question = "What is the first step in assessing a patient?"

    elif stage in ["level_1", "level_2", "level_3"]:
        if last_answer_correct:
            prompt = f"""
You are a career coach AI guiding a user interested in '{request.career}'.
Stage: {stage}
Previous answers:\n{previous_answers_text}

Instructions:
- Last answer was correct. Provide the next technical question.
- Ensure 'stage' is a string.
- Output keys: stage, message, next_question, final_step.
"""
        else:
            prompt = f"""
You are a career coach AI guiding a user interested in '{request.career}'.
Stage: {stage}
Previous answers:\n{previous_answers_text}

Instructions:
- Last answer was incorrect. Provide 3-5 learning resources and a retry technical question.
- Ensure 'stage' is a string.
- Output keys: stage, message, next_question, resources, final_step.
"""
        fallback_question = "Provide a retry question to continue learning."

    elif stage == "jobs":
        prompt = f"""
You are a career coach AI.
The user has completed the required number of correct answers for '{request.career}'.
Provide 3-5 job opportunities suitable for the user's skill level.
Ensure 'stage' is a string.
Output keys: stage, message, next_question, resources, final_step=True.
"""
        fallback_question = "Here are example jobs for this skill level."
    else:
        prompt = f"""
You are a career coach AI.
The user is at stage '{stage}' for '{request.career}'.
Generate a relevant technical question or guidance for this stage.
Ensure 'stage' is a string.
Output keys: stage, message, next_question, final_step.
"""
        fallback_question = "Here is a fallback question to continue."

    ai_result = call_ai_debug(prompt, max_tokens=600, fallback_question=fallback_question, stage=stage)

    return AssessmentResponse(
        stage=ai_result["stage"],
        message=ai_result["message"],
        next_question=ai_result["next_question"],
        resources=ai_result["resources"],
        final_step=ai_result["final_step"]
    )
