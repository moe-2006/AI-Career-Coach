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

class Resource(BaseModel):
    type: str
    title: str
    link: str

class AssessmentResponse(BaseModel):
    stage: str
    message: str
    next_question: Optional[str] = None
    resources: Optional[List[Resource]] = None
    final_step: bool = False  # <-- type only

# ----- OpenAI API Key -----
openai.api_key = os.getenv("OPENAI_API_KEY")

# ----- Helper: call AI safely -----
def call_ai_debug(prompt: str, max_tokens: int, fallback_question: str) -> dict:
    """
    Call OpenAI safely with debug logs and parse JSON.
    Retries once if AI returns empty or invalid JSON.
    """
    for attempt in range(2):
        try:
            print(f"\n--- AI Call Attempt {attempt + 1} ---")
            print(f"Prompt length: {len(prompt)} characters")
            print(f"Model: gpt-3.5-turbo, Max tokens: {max_tokens}\n")
            
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
            
            if not ai_output or ai_output.strip() == "":
                raise ValueError("AI returned empty response.")

            # Try parsing JSON first
            try:
                ai_json = json.loads(ai_output)
            except json.JSONDecodeError:
                print("Warning: AI output is not valid JSON. Returning fallback.")
                raise ValueError("AI returned invalid JSON.")

            # Only parse resources if it is a list
            resources_list = []
            if isinstance(ai_json.get("resources"), list):
                resources_list = [Resource(**r) for r in ai_json.get("resources")]

            return {
    "stage": ai_json.get("stage", "level_1"),
    "message": ai_json.get("message", ""),
    "next_question": ai_json.get("next_question"),
    "resources": resources_list,
    "final_step": bool(ai_json.get("final_step", False))  # <-- force boolean
}


        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == 1:
                return {
                    "stage": "level_1",
                    "message": f"As a {fallback_question}, here's a starting question to continue.",
                    "next_question": fallback_question,
                    "resources": [],
                    "final_step": False
                }

# ----- Endpoint -----
@app.post("/career-assessment", response_model=AssessmentResponse)
async def career_assessment(request: AssessmentRequest):
    stage = request.current_stage or "intro"

    # Format previous answers
    previous_answers_text = "\n".join([
        f"{a.question}: {'correct' if a.correct else 'incorrect'}" 
        for a in request.previous_answers
    ]) or "No previous answers yet."

    last_answer_correct = True
    if request.previous_answers:
        last_answer_correct = request.previous_answers[-1].correct

    # --- Stage-specific prompt construction ---
    if stage == "intro":
        prompt = f"""
You are a career coach AI.
The user wants to pursue a career as a '{request.career}'.

Task:
- Provide a short introduction describing the role of a {request.career}, including common responsibilities and required skills.
- Generate the first skill-testing question tailored for a beginner in {request.career}.
- Provide output as JSON with keys: stage, message, next_question, final_step.
"""
        fallback_question = "What is the first step in assessing a patient's symptoms?"
    elif stage in ["level_1", "level_2"]:
        if last_answer_correct:
            prompt = f"""
You are a career coach AI guiding a user interested in '{request.career}'.
Stage: {stage}
Previous answers:\n{previous_answers_text}

Instructions:
- Last answer was correct. Provide the next skill-testing question and advance stage.
- Provide output as JSON with keys: stage, message, next_question, final_step.
"""
        else:
            prompt = f"""
You are a career coach AI guiding a user interested in '{request.career}'.
Stage: {stage}
Previous answers:\n{previous_answers_text}

Instructions:
- Last answer was incorrect. Provide 3-5 learning resources and a retry question.
- Provide output as JSON with keys: stage, message, next_question, resources, final_step.
"""
        fallback_question = "Provide a retry question to continue learning."
    elif stage == "jobs":
        prompt = f"""
You are a career coach AI.
The user is at the 'jobs' stage for '{request.career}'.

Task:
- Provide 3-5 job opportunities suitable for the user's skill level.
- Provide output as JSON with keys: stage, message, next_question, resources, final_step=True.
"""
        fallback_question = "Here are example jobs for this skill level."
    else:
        prompt = f"""
You are a career coach AI.
The user is at stage '{stage}' for '{request.career}'.

Task:
- Generate a relevant question or guidance for this stage.
- Provide output as JSON with keys: stage, message, next_question, final_step.
"""
        fallback_question = "Here is a fallback question to continue."

    # --- Call AI safely ---
    ai_result = call_ai_debug(prompt, max_tokens=600, fallback_question=fallback_question)

    return AssessmentResponse(
        stage=ai_result["stage"],
        message=ai_result["message"],
        next_question=ai_result["next_question"],
        resources=ai_result["resources"] if not last_answer_correct else None,
        final_step=ai_result["final_step"]
    )
