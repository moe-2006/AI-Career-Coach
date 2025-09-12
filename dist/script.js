"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
// --- Part 2: Get HTML Elements and Create State ---
const startScreen = document.getElementById('start-screen');
const questionScreen = document.getElementById('question-screen');
const resultsScreen = document.getElementById('results-screen');
const loadingIndicator = document.getElementById('loading-indicator');
const careerInput = document.getElementById('career-input');
const startBtn = document.getElementById('start-btn');
const revealBtn = document.getElementById('reveal-btn');
const correctBtn = document.getElementById('correct-btn');
const incorrectBtn = document.getElementById('incorrect-btn');
const retryBtn = document.getElementById('retry-btn');
const aiMessageEl = document.getElementById('ai-message');
const aiQuestionEl = document.getElementById('ai-question');
const aiAnswerEl = document.getElementById('ai-answer');
const answerBox = document.getElementById('answer-box');
const jobList = document.getElementById('job-list');
const resourcesBox = document.getElementById('resources-box');
let assessmentState = {
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
function handleAnswer(isCorrect) {
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
function callApi() {
    return __awaiter(this, void 0, void 0, function* () {
        loadingIndicator.classList.remove('hidden');
        try {
            const apiUrl = 'http://127.0.0.1:8000/career-assessment';
            const response = yield fetch(apiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(assessmentState)
            });
            const data = yield response.json();
            updateUI(data);
        }
        catch (error) {
            console.error("API call to /career-assessment failed:", error);
        }
        finally {
            loadingIndicator.classList.add('hidden');
        }
    });
}
function fetchAnswer() {
    return __awaiter(this, void 0, void 0, function* () {
        loadingIndicator.classList.remove('hidden');
        try {
            const question = aiQuestionEl.textContent || "";
            const apiUrl = 'http://127.0.0.1:8000/reveal-answer';
            const response = yield fetch(apiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: question })
            });
            const data = yield response.json();
            aiAnswerEl.textContent = data.answer;
            answerBox.classList.remove('hidden');
        }
        catch (error) {
            console.error("API call to /reveal-answer failed:", error);
            aiAnswerEl.textContent = "Error fetching answer.";
            answerBox.classList.remove('hidden');
        }
        finally {
            loadingIndicator.classList.add('hidden');
        }
    });
}
function updateUI(data) {
    var _a;
    if (data.final_step) {
        questionScreen.classList.add('hidden');
        resultsScreen.classList.remove('hidden');
        jobList.innerHTML = '';
        (_a = data.resources) === null || _a === void 0 ? void 0 : _a.forEach(job => {
            const listItem = document.createElement('li');
            listItem.innerHTML = `<a href="${job.link}" target="_blank">${job.title}</a>`;
            jobList.appendChild(listItem);
        });
    }
    else {
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
        }
        else if (data.next_question) {
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
