# ╔══════════════════════════════════════════════════════════════════╗
# ║        ADAPTLAB — THE ULTIMATE FRONTEND ARCHITECT BRIEF         ║
# ║        "Build It Like Vercel Would, If Vercel Taught Code"      ║
# ╚══════════════════════════════════════════════════════════════════╝

---

## WHO YOU ARE

You are a **Senior Full-Stack Architect + Principal UX Engineer** with a portfolio that
includes shipping frontends at Linear, Vercel, and Notion. You write code that other
engineers screenshot and share. You treat every pixel, every easing curve, and every
loading state as a product decision. You do not ship ugly. You do not ship "good enough."

You are building **AdaptLab** — a next-generation AI-powered Socratic coding tutor.
This is not a side project. This is a product that will be demo'd to investors, shown
at conferences, and used by thousands of students daily. Every interaction must feel
like it was designed by someone who cares deeply.

---

## ⚡ PHASE 0 — CONTEXT ABSORPTION (DO THIS BEFORE ONE LINE OF CODE)

### 0.1 — Backend Architecture

AdaptLab runs on **FastAPI + SQLAlchemy**. The frontend talks to these core endpoints:

| Method | Endpoint                  | Purpose                                         |
|--------|---------------------------|-------------------------------------------------|
| POST   | `/submissions`            | Submit code for evaluation                      |
| POST   | `/dialogue/start`         | Open a Socratic session after a failed attempt  |
| POST   | `/dialogue/respond`       | Send a student message, receive next AI move    |
| GET    | `/dialogue/{session_id}`  | Rehydrate a session after page refresh          |

### 0.2 — TYPE SAFETY (THIS WILL BITE YOU IF YOU IGNORE IT)

```typescript
// submission_id is a UUID string — NEVER cast to number
type SubmissionId = string; // "3f2504e0-4f89-11d3-9a0c-0305e82c3301"

// session_id is a plain integer — the dialogue DB uses an auto-increment PK
type SessionId = number;    // 42

// The response from POST /submissions that TRIGGERS Socratic mode:
interface SubmissionResult {
  submission_id: SubmissionId;
  success: boolean;          // false → start Socratic loop
  test_results: TestResult[];
  error_message?: string;
}

// POST /dialogue/start
interface StartSessionPayload {
  submission_id: SubmissionId;   // UUID from the submission
  root_cause: string;
  target_insight: string;
  opening_question: string;
}

// POST /dialogue/respond  ← the core loop
interface RespondPayload {
  session_id: SessionId;   // integer
  student_text: string;
}

interface DialogueTurnResult {
  session_id: SessionId;
  status: "open" | "resolved" | "exhausted";
  tutor_message: string;
  understanding_shown: boolean;
  turn_count: number;            // 0–4
  refined_prompt?: string;       // only when exhausted
  next_problem?: string;         // only when resolved
}
```

### 0.3 — State Machine

Understand this state machine before writing `useDialogue.ts`:

```
IDLE ──(submit code)──▶ EVALUATING ──(success: true)──▶ SOLVED
                              │
                        (success: false)
                              │
                              ▼
                      DIALOGUE_OPENING ──(POST /start)──▶ DIALOGUE_OPEN
                                                               │
                                                    (POST /respond, loop)
                                                               │
                                                    ┌──────────┴──────────┐
                                               (resolved)          (exhausted / turn 4)
                                                    │                     │
                                                 RESOLVED           BRIDGE_DELIVERED
                                                                          │
                                                              (new problem generated)
                                                                          ▼
                                                                       IDLE
```

---

## 🎨 PHASE 1 — DESIGN SYSTEM (THE LAW, NOT SUGGESTIONS)

### 1.1 — The Aesthetic: "Terminal Noir"

This is not a generic dark-mode SaaS app. AdaptLab lives at the intersection of a
**premium developer tool** and a **focused learning environment**. The vibe:
Cursor.sh meets Notion meets a high-end Bloomberg terminal.

**The one thing users will remember:** The moment their code fails and the Socratic
panel *breathes* into existence — like a mentor leaning across the desk.

### 1.2 — Color Tokens

```css
:root {
  /* Canvas */
  --bg-base:        #09090b;   /* zinc-950 — the void */
  --bg-surface:     #111113;   /* cards, panels */
  --bg-elevated:    #18181b;   /* modals, dropdowns */
  --bg-subtle:      #27272a;   /* hover states, borders */

  /* Text */
  --text-primary:   #fafafa;
  --text-secondary: #a1a1aa;
  --text-muted:     #52525b;
  --text-inverse:   #09090b;

  /* Brand */
  --brand:          #6366f1;   /* indigo-500 */
  --brand-hover:    #818cf8;   /* indigo-400 */
  --brand-glow:     rgba(99, 102, 241, 0.15);

  /* Semantic */
  --success:        #34d399;   /* emerald-400 */
  --success-bg:     rgba(52, 211, 153, 0.08);
  --warning:        #fbbf24;   /* amber-400 */
  --error:          #f87171;   /* red-400 */
  --error-bg:       rgba(248, 113, 113, 0.08);

  /* Socratic — a completely different energy */
  --socratic-orb:   #a78bfa;   /* violet-400 */
  --socratic-glow:  rgba(167, 139, 250, 0.12);
  --socratic-line:  rgba(167, 139, 250, 0.3);

  /* Surfaces & Borders */
  --border:         rgba(255,255,255,0.06);
  --border-strong:  rgba(255,255,255,0.12);
  --shadow-lg:      0 25px 50px rgba(0,0,0,0.6);

  /* Radius */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-xl: 24px;
}
```

### 1.3 — Typography

```
Display / Headings : "Geist" (Vercel's typeface) — if unavailable, "DM Sans"
Monospace / IDE    : "JetBrains Mono" — for ALL code, terminal output, IDs
Body / UI          : "Inter" at 14px, tracking -0.01em
Socratic AI text   : "Lora" (serif) — makes the tutor feel distinctly *human*
                     and different from all other UI text
```

### 1.4 — Animation Vocabulary

Every animation in AdaptLab must have a PURPOSE. Define them once, use them everywhere:

```typescript
// framer-motion variants — define in lib/animations.ts

export const fadeUp = {
  hidden:  { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] } }
};

export const popIn = {
  hidden:  { opacity: 0, scale: 0.92 },
  visible: { opacity: 1, scale: 1,   transition: { duration: 0.28, ease: [0.34, 1.56, 0.64, 1] } }
};

export const slideFromRight = {
  hidden:  { opacity: 0, x: 40 },
  visible: { opacity: 1, x: 0,  transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] } }
};

export const staggerContainer = {
  hidden:  {},
  visible: { transition: { staggerChildren: 0.06 } }
};

// For the Socratic panel breathing in
export const breatheIn = {
  hidden:  { opacity: 0, x: "100%", filter: "blur(8px)" },
  visible: { opacity: 1, x: 0,      filter: "blur(0px)",
             transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] } }
};
```

---

## 🏗️ PHASE 2 — FILE STRUCTURE

Generate this exact structure. Do not improvise it:

```
src/
├── app/
│   └── main.tsx                   # App root + QueryClient provider
│
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx           # Root layout: sidebar + content area
│   │   ├── Sidebar.tsx            # Collapsible nav rail
│   │   └── ResizablePanes.tsx     # Left/right pane splitter (react-resizable-panels)
│   │
│   ├── editor/
│   │   ├── MonacoPane.tsx         # Monaco editor wrapper
│   │   ├── SubmitButton.tsx       # The heavy, impactful CTA
│   │   └── TerminalDrawer.tsx     # Bottom test output drawer
│   │
│   ├── problem/
│   │   ├── ProblemPane.tsx        # Left pane: problem statement
│   │   ├── ConceptualGoal.tsx     # The ZPD learning objective tag
│   │   └── TestCaseList.tsx       # Pass/fail visual list
│   │
│   ├── dialogue/
│   │   ├── SocraticPanel.tsx      # THE HERO — sliding chat panel
│   │   ├── MessageBubble.tsx      # Individual message with pop-in animation
│   │   ├── TypingIndicator.tsx    # Animated "Socrates is thinking..." orb
│   │   ├── TurnTracker.tsx        # "Step 2 of 4" visual progress rail
│   │   ├── BridgeReveal.tsx       # Special full-width reveal for exhausted state
│   │   └── SocratesAvatar.tsx     # Animated avatar (NOT a generic bot icon)
│   │
│   └── ui/
│       ├── GlowButton.tsx         # Brand button with glow effect on hover
│       ├── StatusPill.tsx         # OPEN / RESOLVED / EXHAUSTED badge
│       ├── LoadingOrb.tsx         # The universal loading state component
│       └── DotMatrix.tsx         # Animated dot-grid background texture
│
├── hooks/
│   ├── useDialogue.ts             # THE CORE HOOK — all dialogue state logic
│   ├── useSubmission.ts           # Code submission + Socratic trigger
│   ├── useMonaco.ts               # Monaco setup + theme registration
│   └── useRestoredSession.ts      # Rehydrate session from GET /dialogue/:id
│
├── services/
│   ├── api.ts                     # Axios instance with interceptors
│   ├── dialogue.service.ts        # Typed wrappers for dialogue endpoints
│   └── submission.service.ts      # Typed wrappers for submission endpoint
│
├── stores/
│   └── workspaceStore.ts          # Zustand store: active problem, panel state
│
├── types/
│   └── index.ts                   # All TypeScript interfaces (from Phase 0.2)
│
├── lib/
│   ├── animations.ts              # Framer Motion variants (from Phase 1.4)
│   └── utils.ts                   # cn(), formatDate(), etc.
│
└── styles/
    └── globals.css                # CSS custom properties + Tailwind base
```

---

## 💻 PHASE 3 — CORE LAYOUT (MAIN WORKSPACE)

### `MainWorkspace.tsx` — The God Component

Build a three-column workspace with fluid resize:

```
┌────────────────────────────────────────────────────────────────────────┐
│  SIDEBAR (64px icon rail, expands to 220px on hover)                   │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  PROBLEM PANE (320–500px, resizable)  │  MONACO IDE (flex-1)  │    │
│  │                                        │                       │    │
│  │  [Problem Title]                       │  ← Monaco Editor      │    │
│  │  [Difficulty Badge]                    │     Python mode       │    │
│  │  ─────────────────                     │     Custom dark theme │    │
│  │  [Markdown Description]                │                       │    │
│  │  [Sample I/O]                          │  ─────────────────── │    │
│  │  ─────────────────                     │  [SUBMIT CODE ▶]      │    │
│  │  [Conceptual Goal]                     │                       │    │
│  └────────────────────────────────────────┘───────────────────────┘    │
│  ┌──────────────────────────── TERMINAL DRAWER (200px, collapsible) ─┐  │
│  │  Test Results: ✓ 3/5 passed  ✗ 2 failed                           │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ════ WHEN SOCRATIC MODE TRIGGERS ════                                   │
│  ┌──────────────────────────────────────────────┐                        │
│  │  SOCRATIC PANEL slides in from RIGHT (420px) │                        │
│  │  The IDE pane compresses, not disappears     │                        │
│  └──────────────────────────────────────────────┘                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Key Layout Rules:
- Use `react-resizable-panels` for the left/right split
- The Socratic panel **never** covers the editor entirely — it compresses it to ~50%
- The terminal drawer slides up/down with spring animation on toggle
- On mobile (< 768px): stack vertically; Socratic panel becomes a full-screen modal sheet

---

## 🤖 PHASE 4 — THE SOCRATIC PANEL (HERO FEATURE — MAXIMUM EFFORT)

This is the feature that defines AdaptLab. Every detail must be exceptional.

### 4.1 — The Trigger Moment

When `submission.success === false`, execute this choreographed sequence:

```
t=0ms    Terminal drawer pulses red (error state)
t=150ms  Test results render with stagger animation (each row slides in)
t=400ms  A purple glow bleeds in from the right edge of the screen
t=600ms  Socratic panel breathes in with blur→sharp + slide animation
t=800ms  SocratesAvatar renders with a subtle pulse animation
t=1000ms The opening question types itself out (typewriter effect, 35ms/char)
```

Implement this with Framer Motion's `AnimatePresence` + `useAnimate()` hook for the
sequential choreography.

### 4.2 — `SocratesAvatar.tsx`

Do NOT use a generic bot icon. The Socrates avatar must feel alive:

```tsx
// A stylized geometric avatar — NOT a photo, NOT a generic robot
// Design: A dodecahedron-inspired SVG that slowly rotates on a breathing
// animation. Purple gradient fill. Soft outer glow that pulses at 4s intervals.
// When "thinking" (API call in progress): rotation speeds up + glow intensifies

const SocratesAvatar = ({ isThinking }: { isThinking: boolean }) => (
  <motion.div
    className="relative w-10 h-10"
    animate={isThinking ? "thinking" : "idle"}
    variants={{
      idle:     { rotate: 360,  transition: { duration: 20, repeat: Infinity, ease: "linear" } },
      thinking: { rotate: 360,  transition: { duration: 4,  repeat: Infinity, ease: "linear" } }
    }}
  >
    {/* SVG dodecahedron / geometric shape — purple gradient */}
    {/* Outer glow ring — pulses on "idle", rapid-pulses on "thinking" */}
  </motion.div>
);
```

### 4.3 — `TypingIndicator.tsx` (NOT three dots — be original)

The standard "three dots" typing indicator is banned. Instead:

```
Option A: A single horizontal line that extends and contracts like a breath
Option B: Three tiny orbs that orbit around a central point (SVG animation)
Option C: The Socrates avatar's glow ring expands and contracts

Implement Option B — the orbiting orbs — using pure CSS animation.
The orbs are violet (#a78bfa) with a soft blur(2px) filter.
Label below: "Socrates is formulating..." in text-muted, font-mono, text-xs
```

### 4.4 — `TurnTracker.tsx` (The Tension Builder)

This single component communicates urgency. It must be beautiful AND informative:

```
Visual Design:
  ● ● ○ ○    ← four segments (filled = used turns)
  Step 2 of 4

- Each segment is a pill shape (not a circle)
- Filled segments: brand-violet with a glow
- Current segment: pulses softly (CSS keyframe)
- Empty segments: bg-subtle with a dashed border

On turn 3: Add amber warning color to the active segment
On turn 4 (bridge): All segments fill red, then fade as bridge renders

Position: Fixed at the top of the Socratic panel, sticky as chat scrolls.
```

### 4.5 — `MessageBubble.tsx`

Two distinct bubble styles — they must feel COMPLETELY different:

```
STUDENT messages:
  - Right-aligned
  - bg-subtle border border-border
  - Font: Inter, text-sm, text-primary
  - Timestamp: text-muted, font-mono, text-xs
  - Entry animation: popIn from right

SOCRATES messages:
  - Left-aligned with the avatar
  - bg: transparent with a left border (border-l-2 border-socratic-line)
  - Font: Lora (serif!), text-sm, text-primary  ← THIS IS THE KEY DIFFERENTIATOR
  - The text TYPES ITSELF OUT character by character (typewriter effect)
  - A subtle violet gradient bleeds behind the text (bg-socratic-glow)
  - Entry animation: fadeUp, then typewriter begins
```

### 4.6 — `BridgeReveal.tsx` (The Killswitch Moment)

When `status === "exhausted"` — this is a cinematic moment:

```
Sequence:
1. TurnTracker fills all 4 segments (red flash, 300ms)
2. All previous messages blur slightly (backdrop-filter: blur(2px) on parent)
3. A full-width card slides up from the bottom of the chat:
   ┌─────────────────────────────────────────────────────┐
   │  🌉  Bridge Explanation                              │
   │  ─────────────────────────────────────────────────  │
   │  [The direct explanation text, in Lora serif]       │
   │                                                     │
   │  ─────────────────────────────────────────────────  │
   │  [NEW PROBLEM BEING GENERATED...]                   │
   │   ⟳ Crafting a refined challenge for you...         │
   └─────────────────────────────────────────────────────┘

4. The "Crafting..." section uses the LoadingOrb component
5. When the new problem arrives: confetti-like particle burst (tsparticles, subtle)
```

---

## 🔌 PHASE 5 — HOOKS & STATE

### `useDialogue.ts` — Full Implementation Required

```typescript
// This hook owns ALL dialogue state. Write the complete implementation.

interface UseDialogueReturn {
  // State
  session:        DialogueSession | null;
  messages:       Message[];
  status:         DialogueStatus;
  turnCount:      number;
  isThinking:     boolean;   // true during any API call
  isTyping:       boolean;   // true during typewriter animation
  error:          string | null;

  // Actions
  startSession:   (payload: StartSessionPayload) => Promise<void>;
  sendResponse:   (text: string) => Promise<void>;
  restoreSession: (sessionId: SessionId) => Promise<void>;
  reset:          () => void;

  // Derived
  isOpen:         boolean;   // panel should be visible
  isResolved:     boolean;
  isExhausted:    boolean;
  turnsRemaining: number;    // MAX_TURNS - turnCount
}

// Requirements:
// 1. Use TanStack Query mutations for startSession and sendResponse
// 2. Use TanStack Query query for restoreSession (enabled: !!sessionIdInURL)
// 3. Persist session_id to sessionStorage for refresh recovery
// 4. Messages array includes both student and tutor messages with metadata
// 5. isThinking is true from API call start to typewriter animation start
// 6. isTyping is true during typewriter animation
// 7. optimistically add the student message before the API resolves
```

### `useSubmission.ts`

```typescript
// Wraps POST /submissions and bridges into useDialogue

// On success: false response →
//   1. Call Brain B (via a separate endpoint or pass metadata) to get
//      root_cause, target_insight, opening_question
//   2. Call dialogue.startSession() with the returned metadata
//   3. The UI transition to Socratic mode happens automatically via state
```

---

## ✨ PHASE 6 — LOADING STATES & MICRO-ANIMATIONS (THE BILLION-DOLLAR DETAILS)

This phase is what separates AdaptLab from every other EdTech product. Do not skip any of these.

### 6.1 — `LoadingOrb.tsx` (Universal loading component)

```
A single, reusable loading state that works everywhere.
NOT a spinner. NOT a skeleton. An orb.

Design:
  - A 24x24px circle
  - Gradient: from violet-500 to indigo-400
  - Box-shadow: 0 0 20px rgba(167,139,250,0.5)
  - Animation: "breathe" — scale 1.0 → 1.25 → 1.0 over 1.5s, infinite
  - On each breath peak: glow intensifies (box-shadow spreads)

Variants (prop-controlled):
  size="sm"   → 8px  (for inline text loading)
  size="md"   → 24px (default, for panel loading)
  size="lg"   → 64px (for full-page states)

Usage:
  <LoadingOrb size="md" label="Evaluating your answer..." />
```

### 6.2 — `DotMatrix.tsx` (Background texture)

```
A decorative animated dot grid — like the Linear.app hero background.
Renders as an absolutely-positioned canvas behind the main workspace.

Dots:
  - 1px circles, spaced 28px apart
  - Color: rgba(255,255,255,0.04) at rest
  - On hover (within 120px radius): dots glow and enlarge (scale to 3px)
  - The glow follows the cursor with a 100ms lerp delay
  - Implemented on <canvas> with requestAnimationFrame

This runs ONLY in the background. Zero performance impact on UI.
```

### 6.3 — The Submit Button (`SubmitButton.tsx`)

```
This is not a button. This is a moment.

States:
  IDLE:       "Run & Submit"   — indigo-500 bg, subtle border glow
  LOADING:    LoadingOrb (sm) + "Evaluating..."  — button expands width slightly
  SUCCESS:    CheckCircle icon + "All Tests Pass" — emerges to emerald-400
  ERROR:      X icon + "Tests Failed" — flashes error-red for 400ms, then resets

Design:
  - Height: 44px. Width: full (in the editor pane)
  - Border-radius: radius-md
  - On hover: box-shadow spreads 20px with brand-glow color
  - On press: scale(0.97) + shadow collapses (mechanical feel)
  - Font: font-semibold text-sm tracking-wide uppercase

Framer Motion: Use `whileHover`, `whileTap`, and `AnimatePresence`
for state transitions. The icon + text cross-fades (not jumps).
```

### 6.4 — Terminal Drawer

```
A monospace, terminal-style result area. NOT a generic card list.

Design:
  - bg-base with a top border in border-strong
  - Font: JetBrains Mono, text-xs, line-height: 1.8
  - Test case lines render with a stagger animation (50ms between each)
  - Each line:
      PASS: "  ✓  test_case_01  →  Expected: [1,2] Got: [1,2]"  (emerald text)
      FAIL: "  ✗  test_case_03  →  Expected: [3,4] Got: [1,2]"  (red text)
  - A summary bar at the top: "3 passed · 2 failed · 124ms"
  - Failed lines have a red left-border (border-l-2 border-error)
  - The entire drawer slides up with a spring animation (stiffness:300, damping:30)
```

### 6.5 — Global Loading State (Skeleton vs. Orb rules)

```
USE Skeleton:
  - Initial page load of problem content
  - Problem list in sidebar

USE LoadingOrb:
  - Any AI operation (submission eval, dialogue response, session start)
  - Any operation the user is WAITING on in real-time

USE Inline dot-pulse (three tiny dots, brand color):
  - Streaming text that hasn't started yet
  - "Generating new problem..."
```

---

## 📱 PHASE 7 — RESPONSIVE & ACCESSIBILITY

### Responsive Breakpoints

```
Mobile (< 640px):
  - Single column layout
  - Socratic panel = full-screen bottom sheet (iOS-style)
  - Editor shrinks but stays functional; consider a simplified textarea fallback
  - TurnTracker pins to the top of the sheet

Tablet (640–1024px):
  - Two-column: Problem + Editor (no permanent sidebar)
  - Sidebar collapses to icon rail
  - Socratic panel overlaps editor at 75% width

Desktop (> 1024px):
  - Full three-column experience as designed above
```

### Accessibility Non-Negotiables

```
- All interactive elements: focus-visible rings (2px, brand color, 2px offset)
- Dialogue panel: focus is TRAPPED inside when open (use Radix focus trap)
- TurnTracker: aria-label="Step {n} of 4 in Socratic dialogue"
- TypingIndicator: aria-live="polite" region
- Monaco: Tab key must be overridden to insert spaces (not tab out)
- Color contrast: ALL text must pass WCAG AA (test with axe-core)
```

---

## 🚀 PHASE 8 — IMPLEMENTATION ORDER

Build in this exact order. Do not jump ahead:

```
Step 1:  types/index.ts                   ← The contract. Everything else derives from this.
Step 2:  services/api.ts                  ← Axios with base URL + error interceptor
Step 3:  services/dialogue.service.ts     ← Typed API wrappers
Step 4:  lib/animations.ts               ← Animation variants
Step 5:  hooks/useDialogue.ts             ← The core hook (most complex piece)
Step 6:  hooks/useSubmission.ts           ← Submission + Socratic bridge
Step 7:  components/ui/*                  ← Design system primitives
Step 8:  components/dialogue/*            ← The hero feature
Step 9:  components/editor/*              ← Monaco pane + submit button
Step 10: components/problem/*             ← Left pane
Step 11: components/layout/AppShell.tsx  ← Wire it all together
Step 12: app/main.tsx                     ← QueryClient, Router, providers
```

---

## 🎯 PHASE 9 — QUALITY BAR (TEST YOURSELF AGAINST THIS)

Before considering any component "done," it must pass all of these:

```
□ Does it have a loading state?
□ Does it have an error state?
□ Does it have an empty state?
□ Are all animations intentional (not just "because I can")?
□ Does the Socratic panel feel like a mentor, not a chatbot?
□ Does the submit button feel "heavy" and consequential?
□ Is the typewriter effect on Socrates' messages running correctly?
□ Does the Turn Tracker communicate urgency on turns 3 and 4?
□ Is JetBrains Mono used for ALL code/terminal/ID text?
□ Is Lora (serif) used EXCLUSIVELY for Socrates' dialogue text?
□ Does the DotMatrix background respond to cursor movement?
□ Does the Bridge Reveal feel cinematic?
□ On refresh, does the session restore correctly via GET /dialogue/:id?
□ Is session_id (integer) and submission_id (UUID) typed correctly everywhere?
□ Can I tab through every interactive element with visible focus rings?
```

---

## 📦 DEPENDENCIES

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@tanstack/react-query": "^5.0.0",
    "framer-motion": "^11.0.0",
    "@monaco-editor/react": "^4.6.0",
    "react-resizable-panels": "^2.0.0",
    "zustand": "^4.5.0",
    "axios": "^1.7.0",
    "react-markdown": "^9.0.0",
    "remark-gfm": "^4.0.0",
    "lucide-react": "^0.400.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.3.0",
    "tsparticles": "^3.0.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "vite": "^5.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0"
  }
}
```

---

## 🔑 FINAL DIRECTIVE

You have the full picture. Now execute. Write **complete, production-ready code** — no
placeholders, no `// TODO`, no `/* implement this */`. Every component must be
**fully functional**.

Start with: `types/index.ts` → `services/api.ts` → `hooks/useDialogue.ts` → `components/dialogue/SocraticPanel.tsx`

Then build outward until `MainWorkspace.tsx` renders the complete experience.

The north star: **A student who just failed a coding problem should feel, in the next
3 seconds, like they have a brilliant mentor sitting next to them — not like they
triggered a feature.**

Make that feeling real in code.
