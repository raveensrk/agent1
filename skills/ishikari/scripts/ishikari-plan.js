export const meta = {
  name: 'ishikari-plan',
  description: 'Ishikari stage 1: review the task, draft a requirement, write worker plans',
  whenToUse: 'Start of an Ishikari run, then once per answer: the investigator ant asks one question per run. When it has no more, the plans go straight to ishikari-build.',
  phases: [
    { title: 'Review', detail: 'investigator ant, helped by up to 5 researcher ants, asks the next question' },
    { title: 'Plans', detail: 'add requirement ant drafts the requirement and writes one plan per worker ant' },
  ],
}

// args: {
//   env: { repo, state, run, main, tool },  from `ishikari.py setup`
//   task: string,                           the task, in the user's words
//   answered?: [{ question, answer, critique? }],  every question asked so far, in order;
//                                           answer '' if skipped
//   findings?: string[],                    research notes from earlier runs
// }
// The investigator ant asks one question per run, chosen after every earlier
// answer. To answer, run again with the same env and task, answered with the new
// answer appended, and findings from the last result.
// Returns one of:
//   { stage: 'question', question, remaining, findings, review }
//                                           ask question; remaining is the best
//                                           guess of questions left after it
//   { stage: 'blocked', reason, review }   the task cannot be done as asked
//   { stage: 'plans', review, requirement, plans, testCommand, checkCommand, answeredCritiques }
// requirement.needed is false for a change with no new behaviour (a refactor):
// then nothing is written to the requirements file.
//   { stage: 'error', reason }
// Nothing is committed here. Without asking, the main session then commits
// the requirement and removes answeredCritiques from the critiques board.

const EFFORT = { review: 'medium', researcher: 'medium', planner: 'high' }
const MAX_RESEARCHERS = 5  // researcher ants at once
const MAX_RESEARCH = 2     // research bursts per question

const { env = {}, task } = args
const bad = []
if (!/^\//.test(env.repo || '')) bad.push('env.repo must be an absolute path')
if (!/^\//.test(env.state || '')) bad.push('env.state must be an absolute path')
if (!/^[A-Za-z0-9._-]+$/.test(env.run || '')) bad.push('env.run must be a run id')
if (!/^[A-Za-z0-9._\/-]+$/.test(env.main || '')) bad.push('env.main must be a branch name')
if (!task) bad.push('task is missing')
if (bad.length) return { stage: 'error', reason: bad.join('; ') }

const where = `Repo: ${env.repo} (main branch: ${env.main}). Ishikari state folder: ${env.state}.
Use absolute paths only. Change nothing in the repo.`
const critiques = `${env.state}/boards/critiques.md`

const REVIEW = {
  type: 'object',
  properties: {
    summary: { type: 'string' },
    critique: { type: 'array', items: { type: 'string' } },
    research: {
      type: 'array', items: { type: 'string' },
      description: `facts to look up before the next question, one per researcher ant, at most ${MAX_RESEARCHERS}; empty if none are needed`,
    },
    next: {
      type: 'object',
      description: 'the one next question for the user, in /ask-simple style; question empty when the goal is clear',
      properties: {
        question: { type: 'string' },
        why: { type: 'string', description: 'one plain line on why it matters; empty if obvious' },
        answers: { type: 'array', items: { type: 'string' }, description: '2-4 short answers, recommended first and marked (Recommended)' },
        critique: { type: 'string', description: 'the Id of the critiques board row this question came from; empty if none' },
      },
      required: ['question', 'answers'],
    },
    remaining: { type: 'integer', description: 'best guess of questions still to ask after next; 0 if none' },
    blocker: { type: 'string', description: 'why the task cannot be done at all as asked; empty if it can' },
    testCommand: { type: 'string', description: 'the one command that runs the repo\'s tests from its root' },
    checkCommand: { type: 'string', description: 'the one command that builds and checks the real app (install, launch check), from the repo root; empty if the repo has none' },
  },
  required: ['summary', 'critique', 'research', 'next', 'remaining', 'blocker', 'testCommand', 'checkCommand'],
}

const FOUND = {
  type: 'object',
  properties: { findings: { type: 'string', description: 'what you found, with paths and URLs; "nothing found" if so' } },
  required: ['findings'],
}

const PLANNED = {
  type: 'object',
  properties: {
    requirement: {
      type: 'object',
      properties: {
        needed: { type: 'boolean', description: 'false if the change adds no behaviour, so no entry is written' },
        file: { type: 'string', description: 'requirements org file the entry belongs in' },
        entry: { type: 'string', description: 'the requirement text, ready to paste' },
        proof: { type: 'string', description: 'how it was shown buildable: docs, repo code or spike' },
      },
      required: ['needed', 'file', 'entry', 'proof'],
    },
    plans: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string', description: 'lowercase letters, digits and dashes, at most 41 characters' },
          title: { type: 'string' },
          files: { type: 'array', items: { type: 'string' }, description: 'files this task creates or edits' },
          after: { type: 'array', items: { type: 'string' }, description: 'ids of tasks that must be built first because this task edits their files' },
          workflow: { type: 'string', description: 'optional saved workflow the worker runs as its job' },
        },
        required: ['id', 'title', 'files'],
      },
    },
  },
  required: ['requirement', 'plans'],
}

// A dead ant (null) is retried once.
async function twice(fn) {
  const first = await fn()
  return first != null ? first : fn()
}

// ---- review: one question per run, research when facts are missing ----
const answered = (args.answered || []).map(q => ({ ...q, answer: String(q.answer || '').trim() }))
const findings = [...(args.findings || [])]
const asked = answered.length
  ? `Questions asked so far, with the user's answers:\n${answered.map(q => `- ${q.question} -> ${q.answer || '(skipped: use the recommended answer)'}`).join('\n')}\n`
  : ''

function researcher(topic, k, round) {
  return agent(
    `You are a researcher ant of the Ishikari workflow. Find facts for the
investigator ant, so it can ask the user better questions about this task:
${task}
Look up: ${topic}
Search the web and anywhere on this computer: ${env.repo}, other repos, notes,
docs and config. Read only; change nothing. Never open or quote secrets:
passwords, keys, tokens, ~/.ssh, keychains, .env files, credential and login
files, browser profiles. Return short facts with their paths and URLs.`,
    { label: `researcher-ant:${answered.length}:${round}:${k}`, phase: 'Review', effort: EFFORT.researcher, schema: FOUND },
  )
}

phase('Review')
let review = null
for (let round = 0; round <= MAX_RESEARCH; round++) {
  const known = findings.length ? `Research so far:\n${findings.map(f => `- ${f}`).join('\n')}\n` : ''
  review = await twice(() => agent(
    `You are the investigator ant of the Ishikari workflow.
${where}
Task: ${task}
Your goal: understand what the user wants, well enough that every later ant
can finish the task with no more questions. Read the repo enough to judge it.
Critique it: gaps, risks, unclear scope.
${asked}${known}Read ${critiques}. A critique that matters for this task becomes a question;
put that row's Id in the question's "critique" field. Leave the rest alone.
Ask nothing the repo, the research or an earlier answer already settles.
${round < MAX_RESEARCH ? `If facts you need are missing, list them in research, at most ${MAX_RESEARCHERS}, and leave next empty: researcher ants look them up and you run again.` : 'Research is done for this question: leave research empty.'}
Otherwise give the single most important next question in next, the
/ask-simple way, and guess how many remain after it. Leave next.question
empty once nothing important is unclear.
If the task cannot be done at all as asked, say why in blocker.
${env.testCommand ? `The repo's test command is \`${env.testCommand}\`: return it as testCommand.` : 'Find the one command that runs the repo\'s tests from its root.'}
${env.checkCommand ? `The repo's app check is \`${env.checkCommand}\`: return it as checkCommand.` : 'Find the one command that builds and checks the real app (install hook, launch check); empty if there is none.'}`,
    { label: `investigator-ant:${answered.length}:${round}`, phase: 'Review', effort: EFFORT.review, schema: REVIEW },
  ))
  if (!review) return { stage: 'error', reason: 'the investigator ant died twice' }
  const topics = round < MAX_RESEARCH ? (review.research || []).slice(0, MAX_RESEARCHERS) : []
  if (!topics.length) break
  log(`research round ${round + 1}: ${topics.length} researcher ants`)
  const found = await parallel(topics.map((t, k) => () => twice(() => researcher(t, k, round))))
  topics.forEach((t, k) => findings.push(`${t}: ${found[k] ? found[k].findings : 'the researcher ant died twice'}`))
}
if (review.blocker) return { stage: 'blocked', reason: review.blocker, review, findings }
if (review.next && review.next.question) {
  return { stage: 'question', question: review.next, remaining: Math.max(0, review.remaining || 0), findings, review }
}

// ---- requirement and plans, in one ant ----
phase('Plans')
const decided = answered.length
  ? `The user's answers:\n${answered.map(q => `- ${q.question} -> ${q.answer || '(skipped: use the recommended answer)'}`).join('\n')}\n`
  : ''
const planDir = `${env.state}/plans/${env.run}`
const out = await twice(() => agent(
  `You are the add requirement ant of the Ishikari workflow.
${where}
Task: ${task}
Review: ${JSON.stringify({ summary: review.summary, critique: review.critique })}
${findings.length ? `Research:\n${findings.map(f => `- ${f}`).join('\n')}\n` : ''}${decided}1. Requirement: follow the /add-requirement skill up to the draft. Show it can be
   built with evidence from the repo's code and docs. Only if that is not enough,
   write a throwaway spike in a temporary folder outside the repo, and delete it
   after. Check for duplicates and conflicts. Do not write the requirements file:
   the main session writes it from your entry.
2. Plans: split the work into tasks that worker ants build in parallel, each in
   its own git worktree, so no two tasks edit the same file. Give each task its
   own test file. Merge tasks that would be too small to stand alone. Only when a
   task must edit a file another task creates, put that task's id in its "after".
   Worker ants cannot ask questions, so each plan must be complete: files to
   touch, exact behaviour, tests to add, and the test command
   \`${review.testCommand || 'the repo\'s test command'}\`.
   Write each plan to ${planDir}/<id>.md. Change no other files.`,
  { label: 'add-requirement-ant', phase: 'Plans', effort: EFFORT.planner, schema: PLANNED },
))
if (!out) return { stage: 'error', reason: 'the add requirement ant died twice' }

// ---- check the plans before anyone builds them ----
const problems = []
const ids = new Set()
for (const p of out.plans) {
  if (!/^[a-z0-9][a-z0-9-]{0,40}$/.test(p.id)) problems.push(`bad id "${p.id}"`)
  if (ids.has(p.id)) problems.push(`two plans have the id "${p.id}"`)
  ids.add(p.id)
}
for (const p of out.plans) {
  for (const d of p.after || []) if (!ids.has(d) || d === p.id) problems.push(`${p.id}: after names unknown plan "${d}"`)
}
const byId = Object.fromEntries(out.plans.map(p => [p.id, p]))
const seen = {}
const visit = (id, path) => {
  if (seen[id] === 'done' || !byId[id]) return
  if (seen[id] === 'open') { problems.push(`loop in after: ${[...path.slice(path.indexOf(id)), id].join(' -> ')}`); return }
  seen[id] = 'open'
  ;(byId[id].after || []).forEach(d => visit(d, [...path, id]))
  seen[id] = 'done'
}
out.plans.forEach(p => visit(p.id, []))
if (!out.plans.length) problems.push('the planner returned no plans')
if (problems.length) return { stage: 'error', reason: `the plans need fixing: ${problems.join('; ')}`, review, requirement: out.requirement, plans: out.plans }

return {
  stage: 'plans',
  review,
  requirement: out.requirement,
  plans: out.plans.map(p => ({ id: p.id, title: p.title, files: p.files, after: p.after || [], workflow: p.workflow || undefined, file: `${planDir}/${p.id}.md` })),
  testCommand: review.testCommand,
  checkCommand: review.checkCommand || '',
  answeredCritiques: answered.filter(q => q.answer && q.critique).map(q => q.critique),
}
