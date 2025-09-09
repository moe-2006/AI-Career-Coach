from fastapi import FastAPI
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional
import openai
import os
import json

app = FastAPI()
load_dotenv()


# ----- Models -----
class UserAnswer(BaseModel):
    question: str
    correct: bool

class AssessmentRequest(BaseModel):
    career: str
    previous_answers: Optional[List[UserAnswer]] = []
    current_stage: Optional[str] = "intro"  # stages: intro, level_1, level_2, jobs

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
    stage = request.current_stage

    # Format previous answers
    previous_answers_text = "\n".join([
        f"{a.question}: {'correct' if a.correct else 'incorrect'}" 
        for a in request.previous_answers
    ]) or "No previous answers yet."

    user_content = f"Previous answers:\n{previous_answers_text}"

    # Build prompt
    prompt = f"""
You are a career coach guiding a user interested in '{request.career}'.
The user is currently at stage '{stage}'.
Previous answers:\n{previous_answers_text}

Instructions:
- Stage 'intro': Provide a general job description and required skills/education. Then explain that we will test their skills to progress.
- Stage 'level_1': Ask a basic question to test a key skill. If user passes, advance. If they fail, provide 3-5 engaging resources (YouTube, project-based learning, interactive exercises) and a retry question.
- Stage 'level_2': Ask a slightly harder question. Same pass/fail rules as above.
- Stage 'jobs': Provide actual job listings or internships suitable for their skill level.
Return a JSON object with fields:
- stage: string (next stage to progress to)
- message: string (text to display)
- next_question: string (if applicable)
- resources: list of objects (type, title, link) (if applicable)
- final_step: boolean (true if stage 'jobs')
"""

    # Call OpenAI
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an adaptive career assessment AI."},
            {"role": "user", "content": prompt + "\n" + user_content}
        ]
    )

    ai_output = response.choices[0].message.content.strip()

    # Parse AI JSON
    try:
        ai_json = json.loads(ai_output)
    except json.JSONDecodeError:
        return AssessmentResponse(
            stage=stage,
            message="Error parsing AI response. Raw output: " + ai_output,
            final_step=(stage == "jobs")
        )

    # Convert resources to Pydantic Resource objects
    resources_list = None
    if "resources" in ai_json and isinstance(ai_json["resources"], list):
        resources_list = [Resource(**r) for r in ai_json["resources"]]

    return AssessmentResponse(
        stage=ai_json.get("stage", stage),
        message=ai_json.get("message", ""),
        next_question=ai_json.get("next_question"),
        resources=resources_list,
        final_step=ai_json.get("final_step", False)
    )