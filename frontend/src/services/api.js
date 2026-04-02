// src/services/api.js
// API layer with graceful mock fallback when backend is unreachable.

import axios from 'axios';
import {
  mockProblem,
  mockCapability,
  mockSubmitResponse,
  mockDialogueResponse,
  mockSubmissionHistory,
} from '../mock/mockData';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: BASE,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// Intercept to detect backend availability
let _backendOnline = true;
export const isBackendOnline = () => _backendOnline;

client.interceptors.response.use(
  (res) => { _backendOnline = true; return res; },
  (err) => {
    if (!err.response || err.code === 'ERR_NETWORK') {
      _backendOnline = false;
    }
    return Promise.reject(err);
  }
);

// ─── Problem ─────────────────────────────────────────────────────────────────

export async function fetchCurrentProblem(topic = null) {
  try {
    const params = topic ? { topic } : {};
    const res = await client.get('/student/problem/current', { params });
    return res.data;
  } catch {
    console.warn('[api] fetchCurrentProblem fallback to mock');
    return mockProblem;
  }
}

export async function fetchProblemsForTopic(topic, studentVector = {}) {
  try {
    const res = await client.post('/problems/select', {
      target_topic: topic,
      student_vector: studentVector,
    });
    return res.data;
  } catch {
    return { ...mockProblem, topic };
  }
}

// ─── Submission ───────────────────────────────────────────────────────────────

export async function submitSolution(problemId, code) {
  try {
    const res = await client.post('/student/submit', {
      problem_id: problemId,
      code,
    });
    return res.data;
  } catch (err) {
    console.warn('[api] submitSolution fallback to mock');
    // Simulate a quick network delay feel
    await new Promise(r => setTimeout(r, 800));
    return mockSubmitResponse;
  }
}

// ─── Socratic Help ────────────────────────────────────────────────────────────

export async function requestHelp(submissionId, userMessage = null) {
  try {
    const payload = { submission_id: submissionId };
    if (userMessage) payload.message = userMessage;
    const res = await client.post('/student/help', payload);
    return res.data;
  } catch {
    console.warn('[api] requestHelp fallback to mock');
    await new Promise(r => setTimeout(r, 600));
    return mockDialogueResponse;
  }
}

export async function continueDialogue(sessionId, message) {
  try {
    const res = await client.post(`/dialogue/${sessionId}/respond`, { message });
    return res.data;
  } catch {
    await new Promise(r => setTimeout(r, 700));
    return {
      ...mockDialogueResponse,
      socratic_question: 'Good observation — now what would that mean for your loop invariant?',
    };
  }
}

// ─── Capability ───────────────────────────────────────────────────────────────

export async function fetchCapability(userId) {
  try {
    const res = await client.get(`/capability/${userId}`);
    return res.data;
  } catch {
    console.warn('[api] fetchCapability fallback to mock');
    return mockCapability;
  }
}

export async function fetchSubmissionHistory(userId, limit = 20) {
  try {
    const res = await client.get(`/submissions`, { params: { user_id: userId, limit } });
    return res.data;
  } catch {
    return mockSubmissionHistory;
  }
}

// ─── Health ───────────────────────────────────────────────────────────────────

export async function checkHealth() {
  try {
    const res = await client.get('/health', { timeout: 3000 });
    _backendOnline = true;
    return res.data;
  } catch {
    _backendOnline = false;
    return null;
  }
}
