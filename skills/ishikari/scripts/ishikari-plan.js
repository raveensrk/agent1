export const meta = {
  name: 'ishikari-plan',
  description: 'Ishikari stage 1: investigate the task, draft a requirement, design it and write worker plans',
  whenToUse: 'Start of an Ishikari run, then once per answer: the investigator ant asks one question per run. When it has no more, the plans go straight to ishikari-build.',
  phases: [
    { title: 'Review', detail: 'investigator ant, helped by up to 5 researcher ants, asks the next question' },
    { title: 'Requirement', detail: 'add requirement ant drafts the requirement from the investigation report' },
    { title: 'Design', detail: 'architect ant writes architecture.md and one plan per worker ant' },
  ],
}

// args: {
//   env: { repo, state, run, main, tool, requirements? },  from `ishikari.py setup`;
//                                           requirements: [] skips the add requirement ant
//   task: string,                           the task, in the user's words
//   answered?: [{ question, answer }],     every question asked so far, in order;
//                                           answer '' if skipped
//   findings?: string[],                    research notes from earlier runs
//   investigated?: { testCommand, checkCommand },
//                                           set when a live investigator agent,
//                                           run by the skill, already asked the
//                                           user and wrote the investigation
//                                           report: Review is skipped
//   escalated?: string,                     why a fast path was given up; the
//                                           requirement and architect ants are told
// }
// The investigator ant asks one question per run, chosen after every earlier
// answer. To answer, run again with the same env and task, answered with the new
// answer appended, and findings from the last result.
// Returns one of:
//   { stage: 'question', question, remaining, findings, review }
//                                           ask question; remaining is the best
//                                           guess of questions left after it
//   { stage: 'blocked', reason, review }   the task cannot be done as asked
//   { stage: 'trivial', why, report, review, testCommand, checkCommand }
//                                           the investigator judged the task trivial
//                                           (fallback only): the main session asks the
//                                           user and takes the fast path, or runs again
//                                           with investigated set for the full plan
//   { stage: 'plans', report, design, review, requirement, plans, testCommand, checkCommand }
// requirement.needed is false for a change with no new behaviour (a refactor):
// then nothing is written to the requirements file.
//   { stage: 'error', reason }
// Nothing is committed here. Without asking, the main session then commits
// the requirement.

// For now every ant runs on the latest Opus at low effort. To tune one ant,
// change its entry here.
const MODEL = 'opus'
const EFFORT = { review: 'low', researcher: 'low', requirement: 'low', architect: 'low' }
const MAX_RESEARCHERS = 5  // researcher ants at once
const MAX_RESEARCH = 2     // research bursts per question

const { env = {}, task } = args
const bad = []
if (!/^\//.test(env.repo || '')) bad.push('env.repo must be an absolute path')
if (!/^\//.test(env.state || '')) bad.push('env.state must be an absolute path')
if (!/^[A-Za-z0-9._-]+$/.test(env.run || '')) bad.push('env.run must be a run id')
if (!/^[A-Za-z0-9._\/-]+$/.test(env.main || '')) bad.push('env.main must be a branch name')
if (!/^\//.test(env.tool || '')) bad.push('env.tool must be an absolute path')
if (!task) bad.push('task is missing')
if (bad.length) return { stage: 'error', reason: bad.join('; ') }

const where = `Repo: ${env.repo} (main branch: ${env.main}). Ishikari state folder: ${env.state}.
Use absolute paths only. Change nothing in the repo.`
const planDir = `${env.state}/plans/${env.run}`
const reportFile = `${planDir}/investigation_report.md`
const designFile = `${planDir}/architecture.md`

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
      },
      required: ['question', 'answers'],
    },
    reportWritten: { type: 'boolean', description: 'true once next.question is empty and the investigation report is written' },
    remaining: { type: 'integer', description: 'best guess of questions still to ask after next; 0 if none' },
    blocker: { type: 'string', description: 'why the task cannot be done at all as asked; empty if it can' },
    testCommand: { type: 'string', description: 'the one command that runs the repo\'s tests from its root' },
    checkCommand: { type: 'string', description: 'the one command that builds and checks the real app (install, launch check), from the repo root; empty if the repo has none' },
    trivial: { type: 'boolean', description: 'true only when all hold: small, known scope (1-2 files, easy to find); one sensible way to do it, no design choice; one task that cannot be split. Docs or config only is a plus, not a must. Any question asked of the user makes it false' },
    trivialWhy: { type: 'string', description: 'one plain line on why the task is or is not trivial' },
  },
  required: ['summary', 'critique', 'research', 'next', 'remaining', 'blocker', 'testCommand', 'checkCommand'],
}

const FOUND = {
  type: 'object',
  properties: { findings: { type: 'string', description: 'what you found, with paths and URLs; "nothing found" if so' } },
  required: ['findings'],
}

const REQUIRED = {
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
  },
  required: ['requirement'],
}

const PLANNED = {
  type: 'object',
  properties: {
    designWritten: { type: 'boolean', description: 'true once architecture.md is written' },
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
  required: ['designWritten', 'plans'],
}

// A dead ant (null) is retried once.
async function twice(fn) {
  const first = await fn()
  return first != null ? first : fn()
}

// ---- logbook, written the moment each ant replies ----
// Every workflow ant call goes through ant(): when the ant replies, a
// entry for it is queued, and a single clerk appends the queue at once, without holding up the
// run. The live investigator runs outside this script, so it gets one
// 'investigated' entry instead.
const summarize = r => {
  if (r == null) return 'died'
  if (typeof r.findings === 'string') return 'found'
  if (r.requirement && typeof r.requirement === 'object') return r.requirement.needed ? 'requirement drafted' : 'no requirement needed'
  if (Array.isArray(r.plans)) return `${r.plans.length} plan${r.plans.length === 1 ? '' : 's'} written`
  if (r.blocker) return 'blocked'
  if (r.next && r.next.question) return 'question asked'
  if (Array.isArray(r.research) && r.research.length) return 'research needed'
  if (r.reportWritten === true) return 'report written'
  return 'finished'
}
// One logbook clerk at a time: entries that arrive while it writes wait in
// a queue, and the next clerk appends them all in one go as soon as it ends.
const logQueue = []
let logWriter = null
const logNow = entries => {
  logQueue.push(...entries)
  if (!logWriter) logWriter = (async () => {
    while (logQueue.length) {
      const batch = logQueue.splice(0)
      await agent(
        `You are Ishikari's logbook clerk. Run exactly this command and nothing else:
python3 ${env.tool} log append ${env.state} <<'ISHIKARI_ROWS_END'
${JSON.stringify(batch)}
ISHIKARI_ROWS_END`,
        { label: 'logbook-clerk:now', phase: 'Logbook', model: MODEL, effort: 'low' },
      ).catch(() => null)
    }
    logWriter = null
  })()
}
async function ant(prompt, opts) {
  const r = await agent(prompt, { ...opts, model: MODEL })
  const kind = String(opts.label).split(':')[0]
  logNow([{ run: env.run, who: kind.replace('-ant', ' ant'), event: summarize(r),
    ...(r != null ? { detail: JSON.stringify(r).slice(0, 400) } : {}) }])
  return r
}
const logsDone = async () => { while (logWriter) await logWriter }
const done = async result => { await logsDone(); return result }

// ---- review: one question per run, research when facts are missing ----
const list = v => Array.isArray(v) ? v : []
const answered = list(args.answered).filter(q => q && typeof q === 'object').map(q => ({ ...q, answer: String(q.answer || '').trim() }))
const findings = list(args.findings).map(String)
const asked = answered.length
  ? `Questions asked so far, with the user's answers:\n${answered.map(q => `- ${q.question} -> ${q.answer || '(skipped: use the recommended answer)'}`).join('\n')}\n`
  : ''

function researcher(topic, k, round) {
  return ant(
    `You are a researcher ant of the Ishikari workflow. Find facts for the
investigator ant, so it can ask the user better questions about this task:
${task}
Look up: ${topic}
Search the web and anywhere on this computer: ${env.repo}, other repos, notes,
docs and config. Read only; change nothing. Never open or quote secrets:
passwords, keys, tokens, ~/.ssh, keychains, .env files, credential and login
files, browser profiles. If the fact is about a user interface (GUI, CLI or
TUI), use the /ux skill in review mode to judge it; never its plan mode, which
asks the user. Return short facts with their paths and URLs.`,
    { label: `researcher-ant:${answered.length}:${round}:${k}`, phase: 'Review', effort: EFFORT.researcher, schema: FOUND },
  )
}

let review = null
const inv = args.investigated && typeof args.investigated === 'object' ? args.investigated : null
if (inv) {
  review = { summary: 'investigated by the live investigator', testCommand: String(inv.testCommand || env.testCommand || ''), checkCommand: String(inv.checkCommand || env.checkCommand || '') }
  logNow([{ run: env.run, who: 'investigator ant', event: 'investigated', detail: reportFile }])
} else {
phase('Review')
for (let round = 0; round <= MAX_RESEARCH; round++) {
  const known = findings.length ? `Research so far:\n${findings.map(f => `- ${f}`).join('\n')}\n` : ''
  review = await twice(() => ant(
    `You are the investigator ant of the Ishikari workflow.
${where}
Task: ${task}
Your goal: collect every fact and decision the task needs, so your
investigation report is bulletproof: the add requirement ant plans from it
alone, and no later ant ever needs to ask. Read the repo enough to judge it.
Critique it: gaps, risks, unclear scope.
${asked}${known}Ask nothing the repo, the research or an earlier answer already settles.
${round < MAX_RESEARCH ? `If facts you need are missing, list them in research, at most ${MAX_RESEARCHERS}, and leave next empty: researcher ants look them up and you run again.` : 'Research is done for this question: leave research empty.'}
Otherwise give the single most important next question in next, the
/ask-simple way, and guess how many remain after it. Leave next.question
empty once nothing important is unclear. Then, and only then, write the
investigation report to ${reportFile} (make the folder if needed; write no
other file) and set reportWritten. The report has these sections:
Goal (in the user's words, then restated); Scope (in, out); Decisions (every
question, the answer, and what it means; a skipped answer takes the
recommended one); Facts (each with its path or URL); Constraints; Risks and
how to handle each; Assumptions (anything not confirmed, with why it is safe);
Acceptance (testable checks that prove the task is done); Commands (test and
app check). Every claim cites an answer, a fact or the repo. No secrets.
With the report written, judge whether the task is trivial: small, known scope
(1-2 files, easy to find), one sensible way to do it, and one task that cannot
be split. Docs or config only helps but is not needed. If you asked the user
anything, it is not trivial. Set trivial and say why in trivialWhy.
If the task cannot be done at all as asked, say why in blocker.
${env.testCommand ? `The repo's test command is \`${env.testCommand}\`: return it as testCommand.` : 'Find the one command that runs the repo\'s tests from its root.'}
${env.checkCommand ? `The repo's app check is \`${env.checkCommand}\`: return it as checkCommand.` : 'Find the one command that builds and checks the real app (install hook, launch check); empty if there is none.'}`,
    { label: `investigator-ant:${answered.length}:${round}`, phase: 'Review', effort: EFFORT.review, schema: REVIEW },
  ))
  if (!review) return done({ stage: 'error', reason: 'the investigator ant died twice' })
  const topics = round < MAX_RESEARCH ? (review.research || []).slice(0, MAX_RESEARCHERS) : []
  if (!topics.length) break
  log(`research round ${round + 1}: ${topics.length} researcher ants`)
  const found = await parallel(topics.map((t, k) => () => twice(() => researcher(t, k, round))))
  topics.forEach((t, k) => findings.push(`${t}: ${found[k] ? found[k].findings : 'the researcher ant died twice'}`))
}
if (review.blocker) return done({ stage: 'blocked', reason: review.blocker, review, findings })
if (review.next && review.next.question) {
  // The same question twice means the investigator is going round in circles.
  const same = q => String(q).trim().toLowerCase()
  if (answered.some(q => same(q.question) === same(review.next.question))) {
    return done({ stage: 'error', reason: `the investigator ant asked the same question again: ${review.next.question}`, review, findings })
  }
  return done({ stage: 'question', question: review.next, remaining: Math.max(0, review.remaining || 0), findings, review })
}
if (!review.reportWritten) return done({ stage: 'error', reason: `the investigator ant did not write ${reportFile}`, review, findings })
if (review.trivial === true && !answered.length) {
  return done({ stage: 'trivial', why: String(review.trivialWhy || ''), report: reportFile, review, findings,
    testCommand: review.testCommand || '', checkCommand: review.checkCommand || '' })
}
}

// A fast path given up part way: the later ants learn why it was not trivial.
const escalated = typeof args.escalated === 'string' && args.escalated.trim() ? args.escalated.trim() : ''
const escalatedNote = escalated ? `A fast path was tried and given up: ${escalated}\nPlan for that.\n` : ''
if (escalated) logNow([{ run: env.run, who: 'main session', event: 'fast path escalated', detail: escalated }])

// ---- requirement: the add requirement ant only adds ----
// A repo with no requirements files (env.requirements is []) has no
// requirements approach: no add requirement ant, nothing to write or mark done.
const noReqs = Array.isArray(env.requirements) && !env.requirements.length
if (noReqs) log('add requirement ant skipped: the repo has no requirements file')
else phase('Requirement')
const req = noReqs ? { requirement: { needed: false, file: '', entry: '', proof: 'the repo has no requirements file' } } : await twice(() => ant(
  `You are the add requirement ant of the Ishikari workflow. Your one job: the
requirement. Do not design or plan the work.
${where}
Task: ${task}
Read the investigation report ${reportFile} first. Build only on it and the
repo. Where the report and your own idea differ, the report wins.
${escalatedNote}Follow the /add-requirement skill up to the draft. Show it can be built with
evidence from the repo's code and docs. Only if that is not enough, write a
throwaway spike in a temporary folder outside the repo, and delete it after.
Check for duplicates and conflicts. Give file as an absolute path to an .org
file inside ${env.repo}${Array.isArray(env.requirements) ? `, one of: ${env.requirements.join(', ')}` : ''}, and give the entry an :ID: property. Write no files:
the main session writes the requirements file from your entry.`,
  { label: 'add-requirement-ant', phase: 'Requirement', effort: EFFORT.requirement, schema: REQUIRED },
))
if (!req || !req.requirement || typeof req.requirement !== 'object') return done({ stage: 'error', reason: 'the add requirement ant died twice or returned no requirement' })
// The main session appends the entry to this file and commits it: it must be
// an org file inside this repo, and the entry must carry an :ID: for req done.
if (req.requirement.needed) {
  const rf = String(req.requirement.file || '')
  const why = []
  if (!rf.startsWith(env.repo + '/') || rf.includes('/../') || !rf.endsWith('.org')) why.push(`file "${rf}" is not an .org file inside ${env.repo}`)
  if (!String(req.requirement.entry || '').trim()) why.push('the entry is empty')
  else if (!/^:ID:\s+\S+/m.test(req.requirement.entry)) why.push('the entry has no :ID: line')
  if (why.length) return done({ stage: 'error', reason: `the requirement needs fixing: ${why.join('; ')}`, review, requirement: req.requirement })
}

// ---- design and plans: the architect ant ----
phase('Design')
const out = await twice(() => ant(
  `You are the architect ant of the Ishikari workflow.
${where}
Task: ${task}
Read the investigation report ${reportFile} first. Where the report and your
own idea differ, the report wins.
${escalatedNote}${req.requirement.needed ? `The requirement, from the add requirement ant (${req.requirement.file}):\n${req.requirement.entry}\n` : noReqs ? 'This repo keeps no requirements file, so the change has no requirement.\n' : 'This change adds no behaviour, so it has no requirement.\n'}1. Design: write ${designFile}: the parts of the change, the files each part
   owns, and every name, interface and data shape that crosses between parts,
   exact, so worker ants building in parallel fit together. Map each of the
   report's acceptance checks to the part that proves it.
2. Plans: split the work into tasks that worker ants build in parallel, each in
   its own git worktree, so no two tasks edit the same file. Keep tasks small so
   more run at once: at most about 3 files per task, splitting a big change by
   files. Give each task its own test file. Merge tasks that would be too small
   to stand alone. Only when a
   task must edit a file another task creates, put that task's id in its "after".
   Worker ants cannot ask questions, so each plan must be complete: files to
   touch, the behaviour wanted, the interfaces from the design it uses or
   provides, the acceptance checks it covers, tests to add, and the test command
   \`${review.testCommand || 'the repo\'s test command'}\`.
   Say what and where, not exact wording: never write out the text, labels or
   code a worker writes. Keep each plan short.
   Write each plan to ${planDir}/<id>.md. Change no other files.`,
  { label: 'architect-ant', phase: 'Design', effort: EFFORT.architect, schema: PLANNED },
))
if (!out || !Array.isArray(out.plans)) return done({ stage: 'error', reason: 'the architect ant died twice or returned no plan list' })
// Normalise what the ant gave, so the checks below never trip on its shape:
// files become clean repo-relative paths, so "./a.py" and "a.py" are one file.
const norm = f => String(f).replace(/^\.\/+/, '').replace(/\/\.\//g, '/').replace(/\/+/g, '/').replace(/\/$/, '')
out.plans = out.plans.filter(p => p && typeof p === 'object').map(p => ({
  ...p, id: String(p.id || ''), title: String(p.title || ''),
  files: [...new Set(list(p.files).map(norm))], after: list(p.after).map(String),
}))
if (!out.designWritten) return done({ stage: 'error', reason: `the architect ant did not write ${designFile}` })

// ---- check the plans before anyone builds them ----
const problems = []
const ids = new Set()
for (const p of out.plans) {
  if (!/^[a-z0-9][a-z0-9-]{0,40}$/.test(p.id)) problems.push(`bad id "${p.id}"`)
  if (!p.files.length) problems.push(`${p.id}: lists no files`)
  if (ids.has(p.id)) problems.push(`two plans have the id "${p.id}"`)
  ids.add(p.id)
}
for (const p of out.plans) {
  for (const d of p.after) if (!ids.has(d) || d === p.id) problems.push(`${p.id}: after names unknown plan "${d}"`)
}
const byId = new Map(out.plans.map(p => [p.id, p]))
const seen = new Map()
const visit = (id, path) => {
  if (seen.get(id) === 'done' || !byId.has(id)) return
  if (seen.get(id) === 'open') { problems.push(`loop in after: ${[...path.slice(path.indexOf(id)), id].join(' -> ')}`); return }
  seen.set(id, 'open')
  byId.get(id).after.forEach(d => visit(d, [...path, id]))
  seen.set(id, 'done')
}
out.plans.forEach(p => visit(p.id, []))
// Two tasks that edit the same file must run in order, one after the other;
// in parallel, their merge would conflict.
const before = id => {
  const acc = new Set()
  const walk = x => (byId.has(x) ? byId.get(x).after : []).forEach(d => { if (!acc.has(d)) { acc.add(d); walk(d) } })
  walk(id)
  return acc
}
if (!problems.length) {
  const owner = new Map()
  for (const p of out.plans) for (const f of p.files) (owner.get(f) || owner.set(f, []).get(f)).push(p.id)
  for (const [f, who] of owner) {
    for (let a = 0; a < who.length; a++) for (let b = a + 1; b < who.length; b++) {
      if (!before(who[a]).has(who[b]) && !before(who[b]).has(who[a])) problems.push(`${who[a]} and ${who[b]} both edit ${f} but neither is after the other`)
    }
  }
}
if (!out.plans.length) problems.push('the planner returned no plans')
if (problems.length) return done({ stage: 'error', reason: `the plans need fixing: ${problems.join('; ')}`, review, requirement: req.requirement, plans: out.plans })

return done({
  stage: 'plans',
  report: reportFile,
  design: designFile,
  review,
  requirement: req.requirement,
  plans: out.plans.map(p => ({ id: p.id, title: p.title, files: p.files, after: p.after || [], workflow: p.workflow || undefined, file: `${planDir}/${p.id}.md` })),
  testCommand: review.testCommand,
  checkCommand: review.checkCommand || '',
})
