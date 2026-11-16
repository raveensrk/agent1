export const meta = {
  name: 'ishikari-plan',
  description: 'Ishikari stage 1: review the task, draft a requirement, write worker plans',
  whenToUse: 'Start of an Ishikari run. The user answers the review and approves the requirement and plans before ishikari-build.',
  phases: [
    { title: 'Review', detail: 'task review ant critiques the task' },
    { title: 'Plans', detail: 'add requirement ant drafts the requirement and writes one plan per worker ant' },
  ],
}

// args: {
//   task: string,          the task, in the user's words
//   repo: string,          absolute path of the repo the work happens in
//   answers?: string,      the user's answers to an earlier review, if any
// }
// Returns { review, requirement, plans } for the user to approve.
// Nothing is committed here: the main session commits after the user says yes.

const REVIEW = {
  type: 'object',
  properties: {
    summary: { type: 'string' },
    critique: { type: 'array', items: { type: 'string' } },
    questions: {
      type: 'array',
      description: 'Questions for the user, in /ask-simple style: one thing each, plain words, 2-4 answers, recommended first',
      items: {
        type: 'object',
        properties: {
          question: { type: 'string' },
          answers: { type: 'array', items: { type: 'string' } },
          critique: { type: 'string', description: 'the critiques board row this question came from, copied exactly; empty if none' },
        },
        required: ['question', 'answers'],
      },
    },
    ready: { type: 'boolean', description: 'true when no question blocks the requirement' },
    answeredCritiques: {
      type: 'array',
      items: { type: 'string' },
      description: 'critiques board rows the user has now answered, copied exactly',
    },
  },
  required: ['summary', 'critique', 'questions', 'ready'],
}

const REQUIREMENT = {
  type: 'object',
  properties: {
    file: { type: 'string', description: 'requirements org file the entry belongs in' },
    entry: { type: 'string', description: 'the requirement text, ready to paste' },
    proof: { type: 'string', description: 'how it was shown buildable: docs, repo code or spike' },
  },
  required: ['file', 'entry', 'proof'],
}

const PLANS = {
  type: 'object',
  properties: {
    plans: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string', description: 'short kebab-case id, also the branch suffix' },
          title: { type: 'string' },
          file: { type: 'string', description: 'absolute path of the written plan file' },
          workflow: { type: 'string', description: 'optional saved workflow name the worker runs as its job' },
          after: { type: 'array', items: { type: 'string' }, description: 'ids of plans that must be built first; this plan builds on their branches' },
        },
        required: ['id', 'title', 'file'],
      },
    },
  },
  required: ['plans'],
}

const { task, repo, answers } = args

phase('Review')
const review = await agent(
  `You are the task review ant of the Ishikari workflow.
Repo: ${repo}
Task: ${task}
${answers ? `The user already answered earlier questions:\n${answers}\n` : ''}
Read the repo enough to judge the task. Critique it: gaps, risks, unclear scope.
Read ${repo}/boards/critiques.md if it exists. For each critique that matters
for this task, ask the user one question about it and copy the critique's row
into that question's "critique" field. Leave other critiques alone. A question
built from a critique blocks the requirement until the user answers it; list
critiques the user has now answered in "answeredCritiques".
Write all questions the /ask-simple way. Ask nothing the repo answers.
Change no files.`,
  { label: 'task-review-ant', phase: 'Review', schema: REVIEW },
)

if (!review || !review.ready) {
  return { stage: 'review', review }
}

phase('Plans')
// One ant drafts the requirement and writes the plans: one start instead of two.
const out = await agent(
  `You are the add requirement ant of the Ishikari workflow.
Repo: ${repo}
Task: ${task}
Review: ${JSON.stringify(review)}
${answers ? `User answers:\n${answers}\n` : ''}
1. Requirement: follow the /add-requirement skill up to the draft. Prove the
   requirement can be built in this repo, check for duplicates and conflicts.
   Do not write the requirements file; the user approves it first.
2. Plans: split the work into tasks worker ants build in parallel, each in its own git
   worktree. Split by file, so no two tasks edit the same file; only when that
   is impossible, list the earlier task's id in "after" and the later task
   builds on its branch. Worker ants cannot ask questions, so each plan must be
   complete: files to touch, exact behavior, tests to add, the command that
   proves it works. Write each plan to ${repo}/.ishikari/plans/<id>.md.
${(review.answeredCritiques || []).length ? `3. Critiques: the user answered these, so remove their rows from
   ${repo}/boards/critiques.md and keep the table aligned:
   - ${review.answeredCritiques.join('\n   - ')}
` : ''}   Change no other files.`,
  { label: 'add-requirement-ant', phase: 'Plans', schema: {
    type: 'object',
    properties: { requirement: REQUIREMENT, plans: PLANS.properties.plans },
    required: ['requirement', 'plans'],
  } },
)

return { stage: 'plans', review, requirement: out && out.requirement, plans: out ? out.plans : [] }
