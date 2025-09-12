// --- Part 1: Interfaces ---
interface UserAnswer {
    question: string;
    correct: boolean;
}

interface AssessmentState {
    career: string;
    previous_answers: UserAnswer[];
    total_questions: number;
    // New property for the backend to recognize a retry
    is_retry: boolean; 
}

interface ApiResponse {
    message: string;
    next_question?: string;
    resources?: { type: string, title: string, link?: string }[];
    final_step: boolean;
    answer?: string;
}

// --- Part 2: Get HTML Elements and Create State ---
const startScreen = document.getElementById('start-screen') as HTMLDivElement;
const questionScreen = document.getElementById('question-screen') as HTMLDivElement;
const resultsScreen = document.getElementById('results-screen') as HTMLDivElement;
const loadingIndicator = document.getElementById('loading-indicator') as HTMLDivElement;

const careerInput = document.getElementById('career-input') as HTMLInputElement;
const startBtn = document.getElementById('start-btn') as HTMLButtonElement;
const revealBtn = document.getElementById('reveal-btn') as HTMLButtonElement;
const correctBtn = document.getElementById('correct-btn') as HTMLButtonElement;
const incorrectBtn = document.getElementById('incorrect-btn') as HTMLButtonElement;
const retryBtn = document.getElementById('retry-btn') as HTMLButtonElement;

const aiMessageEl = document.getElementById('ai-message') as HTMLParagraphElement;
const aiQuestionEl = document.getElementById('ai-question') as HTMLHeadingElement;
const aiAnswerEl = document.getElementById('ai-answer') as HTMLParagraphElement;
const answerBox = document.getElementById('answer-box') as HTMLDivElement;
const jobList = document.getElementById('job-list') as HTMLUListElement;
const resourcesBox = document.getElementById('resources-box') as HTMLDivElement;

let assessmentState: AssessmentState = {
    career: "",
    previous_answers: [],
    total_questions: 3,
    is_retry: false
};

// --- Part 3: Event Listeners and Handlers ---
startBtn.addEventListener('click', startAssessment);
revealBtn.addEventListener('click', fetchAnswer);
correctBtn.addEventListener('click', () => handleAnswer(true));
incorrectBtn.addEventListener('click', () => handleAnswer(false));

// Updated: callApi with the retry flag set to true
retryBtn.addEventListener('click', () => {
    assessmentState.is_retry = true;
    callApi();
});

function startAssessment() {
    assessmentState.career = careerInput.value;
    if (!assessmentState.career) {
        alert("Please enter a career.");
        return;
    }
    startScreen.classList.add('hidden');
    questionScreen.classList.remove('hidden');
    callApi();
}

function handleAnswer(isCorrect: boolean) {
    const lastQuestion = aiQuestionEl.textContent || "";
    assessmentState.previous_answers.push({
        question: lastQuestion,
        correct: isCorrect
    });
    // Reset the retry flag after each standard answer
    assessmentState.is_retry = false;
    callApi();
}

// --- Part 4: API Communication and UI Updates ---
async function callApi() {
    loadingIndicator.classList.remove('hidden');
    try {
        const apiUrl = 'https://ai-career-coach-1vtz.onrender.com/career-assessment';
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(assessmentState)
        });
        const data: ApiResponse = await response.json();
        updateUI(data);
    } catch (error) {
        console.error("API call to /career-assessment failed:", error);
    } finally {
        loadingIndicator.classList.add('hidden');
    }
}

async function fetchAnswer() {
    loadingIndicator.classList.remove('hidden');
    try {
        const question = aiQuestionEl.textContent || "";
        const apiUrl = 'https://ai-career-coach-1vtz.onrender.com/reveal-answer';
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: question })
        });
        const data: { answer: string } = await response.json();
        
        aiAnswerEl.textContent = data.answer;
        answerBox.classList.remove('hidden');
    } catch (error) {
        console.error("API call to /reveal-answer failed:", error);
        aiAnswerEl.textContent = "Error fetching answer.";
        answerBox.classList.remove('hidden');
    } finally {
        loadingIndicator.classList.add('hidden');
    }
}

function updateUI(data: ApiResponse) {
    if (data.final_step) {
        questionScreen.classList.add('hidden');
        resultsScreen.classList.remove('hidden');
        
        jobList.innerHTML = '';
        
        data.resources?.forEach(job => {
            const listItem = document.createElement('li');
            listItem.innerHTML = `<a href="${job.link}" target="_blank">${job.title}</a>`;
            jobList.appendChild(listItem);
        });

    } else {
        if (data.resources && data.resources.length > 0) {
            // Case 1: The API returned learning resources
            aiMessageEl.textContent = data.message || '';
            aiQuestionEl.textContent = "Please review the resources below, then click 'Retry Question' to continue.";
            revealBtn.classList.add('hidden');
            answerBox.classList.add('hidden');
            retryBtn.classList.remove('hidden');
            
            resourcesBox.innerHTML = '';
            const title = document.createElement('h4');
            title.textContent = "Here are some resources to help:";
            resourcesBox.appendChild(title);
            
            const list = document.createElement('ul');
            data.resources.forEach(resource => {
                const listItem = document.createElement('li');
                listItem.innerHTML = `<a href="${resource.link}" target="_blank" style="color: #dc3545;">${resource.title}</a> (${resource.type})`;
                list.appendChild(listItem);
            });
            resourcesBox.appendChild(list);
        } else if (data.next_question) {
            // Case 2: The API returned a new question
            aiMessageEl.textContent = data.message || '';
            aiQuestionEl.textContent = data.next_question;
            answerBox.classList.add('hidden');
            revealBtn.classList.remove('hidden');
            retryBtn.classList.add('hidden');
            resourcesBox.innerHTML = '';
        }
    }
}