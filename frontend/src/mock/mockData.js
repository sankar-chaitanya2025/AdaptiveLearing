// src/mock/mockData.js
// Offline mode fallback — loaded when the backend is unreachable.

export const TOPICS = [
  'arrays', 'hash_maps', 'recursion', 'dp',
  'backtracking', 'sorting', 'binary_search',
  'two_pointers', 'sliding_window', 'graphs'
];

export const mockProblem = {
  id: 'aaaaaaaa-0000-0000-0000-000000000001',
  title: 'Two Sum',
  topic: 'hash_maps',
  difficulty: 0.45,
  statement: `## Two Sum

Given an array of integers \`nums\` and an integer \`target\`, return the **indices** of the two numbers such that they add up to \`target\`.

You may assume that each input would have **exactly one solution**, and you may not use the same element twice.

### Constraints
- \`2 ≤ nums.length ≤ 10^4\`
- \`-10^9 ≤ nums[i] ≤ 10^9\`
- \`-10^9 ≤ target ≤ 10^9\`
- Only one valid answer exists.

### Examples

\`\`\`
Input:  nums = [2, 7, 11, 15], target = 9
Output: [0, 1]
\`\`\`

\`\`\`
Input:  nums = [3, 2, 4], target = 6
Output: [1, 2]
\`\`\``,
  visible_tests: [
    { input: '[2,7,11,15], target=9', expected: '[0,1]' },
    { input: '[3,2,4], target=6',    expected: '[1,2]' },
  ],
  hidden_tests: [
    { input: '[3,3], target=6',      expected: '[0,1]' },
  ],
  insight: 'Use a hash map to store complements in O(n) time instead of nested loops.',
};

export const mockCapability = {
  userId: 'mock-user-01',
  radar: TOPICS.map(topic => ({
    topic,
    score: Math.round((0.1 + Math.random() * 0.85) * 100) / 100,
  })),
  streak: 5,
  sessions_total: 28,
  problems_solved: 17,
};

export const mockSubmissionHistory = [
  {
    id: 'sub-001',
    problem: 'Two Sum',
    topic: 'hash_maps',
    visible_score: 1.0,
    hidden_score: 0.75,
    brain_a_feedback: 'Correct approach. Consider edge cases with duplicate values.',
    created_at: new Date(Date.now() - 3600_000).toISOString(),
  },
  {
    id: 'sub-002',
    problem: 'Binary Search',
    topic: 'binary_search',
    visible_score: 0.5,
    hidden_score: 0.25,
    brain_a_feedback: 'Off-by-one error in the loop termination condition.',
    created_at: new Date(Date.now() - 7200_000).toISOString(),
  },
  {
    id: 'sub-003',
    problem: 'Maximum Subarray',
    topic: 'dp',
    visible_score: 1.0,
    hidden_score: 1.0,
    brain_a_feedback: 'Excellent Kadane implementation. Clean and optimal.',
    created_at: new Date(Date.now() - 86400_000).toISOString(),
  },
  {
    id: 'sub-004',
    problem: 'Valid Parentheses',
    topic: 'arrays',
    visible_score: 1.0,
    hidden_score: 0.5,
    brain_a_feedback: 'Stack logic is correct but not handling all bracket types.',
    created_at: new Date(Date.now() - 172800_000).toISOString(),
  },
  {
    id: 'sub-005',
    problem: 'Longest Substring No Repeat',
    topic: 'sliding_window',
    visible_score: 0.75,
    hidden_score: 0.6,
    brain_a_feedback: 'Sliding window direction is correct; window shrink logic is off.',
    created_at: new Date(Date.now() - 259200_000).toISOString(),
  },
];

export const mockDialogueResponse = {
  session_id: 1,
  socratic_question: 'Think about what happens when you encounter a number you\'ve already seen. What data structure lets you check this in O(1) time?',
  history: [
    { role: 'plato', content: 'Let\'s examine your submission. You\'re using a nested loop — what is the time complexity of that approach?' },
    { role: 'student', content: 'It\'s O(n²) I think.' },
    { role: 'plato', content: 'Correct. Now — what if you needed to solve this in linear time? What would you need to track as you scan through the array?' },
  ],
  status: 'OPEN',
};

export const mockSubmitResponse = {
  submission_id: 'bbbbbbbb-0000-0000-0000-000000000002',
  feedback: 'Your visible tests pass but the hidden tests reveal an edge case with duplicate values.',
  visible_score: 1.0,
  hidden_score: 0.5,
  tests: { visible_passed: 2, visible_total: 2, hidden_passed: 1, hidden_total: 2 },
  capability_delta: { hash_maps: +0.04 },
  status: 'partial',
  failure_mode: 'edge_case_missed',
};
