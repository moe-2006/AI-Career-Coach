from urllib.parse import quote_plus
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from serpapi import GoogleSearch # New import
import openai
import os
import json
from dotenv import load_dotenv

# ----- Load environment variables -----
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY") # New env var

app = FastAPI()

# ... (Your Pydantic models UserAnswer, AssessmentRequest, etc. remain the same) ...
class UserAnswer(BaseModel):
    question: str
    correct: bool

class AssessmentRequest(BaseModel):
    career: str
    previous_answers: Optional[List[UserAnswer]] = []
    total_questions: Optional[int] = 3

class Resource(BaseModel):
    type: str
    title: str
    link: Optional[str] = None

class AssessmentResponse(BaseModel):
    message: str
    next_question: Optional[str] = None
    resources: Optional[List[Resource]] = None
    final_step: bool = False
# ... (Your call_ai function remains the same) ...
def call_ai(prompt: str, max_tokens: int = 600) -> dict:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a career coach AI. Provide valid JSON outputs."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.7
        )
        output = response.choices[0].message.content
        return json.loads(output)
    except Exception as e:
        print(f"AI call failed: {e}")
        return {"message": "AI failed to generate a response.", "next_question": None, "resources": None}

#Getting listings from serp api woo hooo
def get_jobs_from_serpapi(career: str, results: int = 10) -> List[Resource]:
    """
    Fetches job listings from Google Jobs via SerpApi, checking multiple keys for a valid link.
    """
    params = {
      "engine": "google_jobs",
      "q": career,
      "api_key": SERPAPI_API_KEY
    }

    print(f"Attempting to fetch jobs from SerpApi for query: {career}")
    try:
        search = GoogleSearch(params)
        data = search.get_dict()
        jobs = []
        
        for job in data.get("jobs_results", [])[:results]:
            # --- START OF RESILIENT METHOD ---
            job_link = "" # Default to an empty string

            # 1. First, try to get the link from 'apply_options'
            if 'apply_options' in job and job['apply_options']:
                job_link = job['apply_options'][0].get('link', '')

            # 2. If that fails, try the first 'related_links'
            if not job_link and 'related_links' in job and job['related_links']:
                job_link = job['related_links'][0].get('link', '')

            # 3. As a last resort, check for a top-level 'link'
            if not job_link:
                job_link = job.get('link', '')
            # --- END OF RESILIENT METHOD ---
            
            jobs.append(Resource(
                type="job",
                title=f"{job.get('title', 'Job')} at {job.get('company_name', '')}",
                link=job_link
            ))
        
        print(f"Found {len(jobs)} jobs from SerpApi.")
        return jobs
    except Exception as e:
        print(f"AN ERROR OCCURRED with SerpApi: {e}")
        return []
    
# ----- Endpoint -----
@app.post("/career-assessment", response_model=AssessmentResponse)
async def career_assessment(request: AssessmentRequest):
    total_questions = request.total_questions or 3
    correct_count = sum(1 for a in request.previous_answers if a.correct)
    last_answer_correct = True if not request.previous_answers else request.previous_answers[-1].correct
    final_step = correct_count >= total_questions

    if final_step:
        # Final change: call the new SerpApi function
        jobs = get_jobs_from_serpapi(request.career)
        
        return AssessmentResponse(
            message=f"Congratulations on completing the assessment for {request.career}! Here are some job opportunities:",
            resources=jobs,
            final_step=True
        )

    # ... (The rest of your AI prompt logic remains the same) ...
    # Construct AI prompt for next question
    if not request.previous_answers:
        # Intro
        prompt = f"""
You are a career coach AI.
Introduce the role of a {request.career} and provide a technical question (no personal/motivation).
Output JSON: message, next_question
"""
    elif last_answer_correct:
        prompt = f"""
You are a career coach AI.
The user is pursuing a career as a {request.career}.
Previous answers: {chr(10).join([f"{a.question}: {'correct' if a.correct else 'incorrect'}" for a in request.previous_answers])}
Provide the next technical question.
Output JSON: message, next_question
"""
    else:
        # Provide resources and retry question
        prompt = f"""
You are a career coach AI.
The user is pursuing a career as a {request.career}.
Previous answers: {chr(10).join([f"{a.question}: {'correct' if a.correct else 'incorrect'}" for a in request.previous_answers])}
Last answer was incorrect.
Provide 3-5 learning resources (type: book/course/website/video, title, optional link) and a retry technical question.
Output JSON: message, next_question, resources
"""

    ai_result = call_ai(prompt)

    # Convert resources if present
    resources_list = None
    raw_resources = ai_result.get("resources")
    if raw_resources:
        resources_list = []
        for r in raw_resources:
            if isinstance(r, dict):
                resources_list.append(Resource(**r))
            elif isinstance(r, str):
                resources_list.append(Resource(type="resource", title=r))

    return AssessmentResponse(
        message=ai_result.get("message", ""),
        next_question=ai_result.get("next_question"),
        resources=resources_list,
        final_step=False
    )