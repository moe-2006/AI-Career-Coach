from urllib.parse import quote_plus
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from serpapi import GoogleSearch
import openai
import os
import json
from dotenv import load_dotenv

# ----- Load environment variables -----
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Pydantic Models -----
class AnswerRequest(BaseModel):
    question: str

class UserAnswer(BaseModel):
    question: str
    correct: bool

class AssessmentRequest(BaseModel):
    career: str
    previous_answers: Optional[List[UserAnswer]] = []
    total_questions: Optional[int] = 3
    is_retry: Optional[bool] = False

class Resource(BaseModel):
    type: str
    title: str
    link: Optional[str] = None

class AssessmentResponse(BaseModel):
    message: str
    next_question: Optional[str] = None
    resources: Optional[List[Resource]] = None
    final_step: bool = False

# ----- Helper Functions -----
def call_ai(prompt: str, career: str, max_tokens: int = 600) -> dict:
    """
    Calls the OpenAI API with improved error handling and a dynamic system message.
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are a career coach AI who asks technical questions based off the {career} field. Provide valid JSON outputs."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.7
        )
        output = response.choices[0].message.content
        return json.loads(output)
    except json.JSONDecodeError as e:
        print(f"AI returned invalid JSON: {e}")
        print(f"Raw output from AI: {output}")
        return {"message": "Sorry, there was a technical glitch generating the response. Please try again.", "next_question": None, "resources": None}
    except Exception as e:
        print(f"An unexpected AI call error failed: {e}")
        return {"message": "The AI failed to generate a response. Please try again later.", "next_question": None, "resources": None}

def get_jobs_from_serpapi(career: str, results: int = 10) -> List[Resource]:
    """
    Fetches job listings from Google Jobs via SerpApi.
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
            job_link = job.get('apply_options', [{}])[0].get('link') or \
                       job.get('related_links', [{}])[0].get('link') or \
                       job.get('link', '')
            
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

# ----- API Endpoints -----
@app.get("/")
def read_root():
    return {"status": "API is running"}

@app.post("/career-assessment", response_model=AssessmentResponse)
async def career_assessment(request: AssessmentRequest):
    total_questions = request.total_questions or 3
    correct_count = sum(1 for a in request.previous_answers if a.correct)
    
    # --- Prompt Selection Logic ---
    if request.is_retry:
        prompt = f"""
        You are a career coach AI. The user is pursuing a career as a {request.career}.
        Previous answers: {chr(10).join([f"{a.question}: {'correct' if a.correct else 'incorrect'}" for a in request.previous_answers])}
        The user has reviewed learning resources and is ready to try a new question. Provide the next technical question. The question must be objective with a clear, verifiable answer.
        Output JSON: "message", "next_question"
        """
    elif correct_count >= total_questions:
        jobs = get_jobs_from_serpapi(request.career)
        return AssessmentResponse(
            message=f"Congratulations on completing the assessment for {request.career}! Here are some job opportunities to explore:",
            resources=jobs,
            final_step=True
        )
    elif request.previous_answers and request.previous_answers[-1].correct:
        prompt = f"""
        You are a career coach AI. The user is pursuing a career as a {request.career}.
        Previous answers: {chr(10).join([f"{a.question}: {'correct' if a.correct else 'incorrect'}" for a in request.previous_answers])}
        The user answered the last question correctly. Provide the next technical question. Ensure the question is objective and has a clear, correct answer, as it is being graded.
        Output JSON: "message", "next_question"
        """
    elif request.previous_answers and not request.previous_answers[-1].correct:
        prompt = f"""
        You are a career coach AI. The user is pursuing a career as a {request.career}.
        Previous answers: {chr(10).join([f"{a.question}: {'correct' if a.correct else 'incorrect'}" for a in request.previous_answers])}
        The last answer was incorrect. Provide a supportive message explaining that they can review the resources to prepare. Also provide 3-5 learning resources (type: book/course/website/video, title, optional link). Do NOT provide a new question.
        Output JSON: "message", "resources"
        """
    else: # This is the first question
        prompt = f"""
        You are a career coach AI. Provide a concise, engaging message that introduces the career of a {request.career} and then poses the first technical question. The question must have no subjective information as it is being graded for correctness.
        Output JSON: "message", "next_question"
        """
    
    ai_result = call_ai(prompt, request.career)

    resources_list = None
    if raw_resources := ai_result.get("resources"): # Walrus operator for cleaner code
        resources_list = [Resource(**r) for r in raw_resources if isinstance(r, dict)]

    return AssessmentResponse(
        message=ai_result.get("message", "An error occurred."),
        next_question=ai_result.get("next_question"),
        resources=resources_list,
        final_step=False
    )
    
@app.post("/reveal-answer")
async def reveal_answer(request: AnswerRequest):
    prompt = f"""
    You are a subject matter expert. A user has requested the answer to the following question:
    "{request.question}"

    Please provide a concise, correct, and easy-to-understand answer. Return it in a simple JSON object with a single key: "answer".
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0.3 # Low temperature for factual answers
        )
        output = response.choices[0].message.content
        return json.loads(output)
    except Exception as e:
        print(f"Reveal answer failed: {e}")
        return {"answer": "Sorry, I was unable to retrieve the answer at this time."}