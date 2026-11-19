export const meta = {
  name: 'ishikari-retro',
  description: 'Ishikari last step: the retrospective ant reviews how this run went and reports ranked improvements to the Ishikari flow; read only',
  whenToUse: 'Once, at the very end of a full Ishikari run, however it ended (main moved, stopped, blocked or error). Never after a fast path.',
  phases: [
    { title: 'Retrospective', detail: 'retrospective ant reads the run and writes retrospective.md' },
  ],
}

// args: {
//   env: { repo, state, run, main, tool },  from `ishikari.py setup`
//   outcome: string,                        how the run ended, in a few words
//                                           (e.g. "main moved", "blocked: <why>")
// }
// The main session saved each stage's result as <state>/plans/<run>/<stage>-<n>.json.
// Returns { stage: 'retro', file, summary, findings } or { stage: 'error', reason }.
// findings are ranked, costliest first: { category, title, evidence, impact, change, where }.
//
// Read only: the ant changes no code, branch, logbook entry or repo file. Its one
// write is retrospective.md in the run's plans folder, outside the repo.

// For now every ant runs on the latest Opus at low effort.
const MODEL = 'opus'
const EFFORT = { retrospective: 'low' }
const CATEGORIES = ['bug', 'error', 'inefficiency', 'gap', 'missing', 'improvement']

const { env = {}, outcome = '' } = args
const bad = []
if (!/^\//.test(env.repo || '')) bad.push('env.repo must be an absolute path')
if (!/^\//.test(env.state || '')) bad.push('env.state must be an absolute path')
if (!/^\//.test(env.tool || '')) bad.push('env.tool must be an absolute path')
if (!/^[A-Za-z0-9._-]+$/.test(env.run || '')) bad.push('env.run must be a run id')
if (!/^[A-Za-z0-9._\/-]+$/.test(env.main || '')) bad.push('env.main must be a branch name')
if (bad.length) return { stage: 'error', reason: bad.join('; ') }

const planDir = `${env.state}/plans/${env.run}`
const file = `${planDir}/retrospective.md`
const skill = env.tool.replace(/\/scripts\/[^/]+$/, '')

// One logbook entry for the ant, appended the moment it replies; a failed
// append never blocks or fails the run.
const logNow = entries => agent(
  `You are Ishikari's logbook clerk. Run exactly this command and nothing else:
python3 ${env.tool} log append ${env.state} <<'ISHIKARI_ROWS_END'
${JSON.stringify(entries)}
ISHIKARI_ROWS_END`,
  { label: 'logbook-clerk:now', phase: 'Logbook', model: MODEL, effort: 'low' },
).catch(() => null)

const RETRO = {
  type: 'object',
  properties: {
    written: { type: 'boolean', description: `true once ${file} is written` },
    summary: { type: 'string', description: 'two or three lines: how the run went overall' },
    findings: {
      type: 'array',
      description: 'ranked, costliest first',
      items: {
        type: 'object',
        properties: {
          category: { type: 'string', enum: CATEGORIES },
          title: { type: 'string' },
          evidence: { type: 'string', description: 'what in this run shows it: logbook entry, result field, plan, commit' },
          impact: { type: 'string', description: 'what it cost: ant calls, rounds, time, a dropped task, a wrong result' },
          change: { type: 'string', description: 'the suggested change to the Ishikari flow' },
          where: { type: 'string', description: 'the Ishikari file and rule to change, e.g. scripts/ishikari-build.js MAX_TRIES' },
        },
        required: ['category', 'title', 'evidence', 'impact', 'change', 'where'],
      },
    },
  },
  required: ['written', 'summary', 'findings'],
}

phase('Retrospective')
const prompt = `You are the retrospective ant of the Ishikari workflow. The run is over
(${String(outcome).trim() || 'outcome not given'}). Review how the Ishikari flow ran this time and
report where it can improve. You judge the flow, not the repo's code: the judge
and the janitor cover the code.
Repo: ${env.repo} (main branch: ${env.main}). Run id: ${env.run}.
Read only. Change no code, branch, worktree, logbook entry or repo file, and run
no command that writes. Your one write is ${file}.
Read:
- this run's logbook entries: \`python3 ${env.tool} log status ${env.state} ${env.run}\` and
  the entries with Run: ${env.run} in ${env.state}/logbook.rec;
- ${planDir}: investigation_report.md, architecture.md, the worker plans, any
  cleanup.md, and every stage result <stage>-<n>.json;
- the run's git history: \`git -C ${env.repo} log --oneline ${env.main}\`, the
  branches \`git -C ${env.repo} branch --list 'ishikari/${env.run}/*'\` and their commits;
- Ishikari's own source, to name what to change: ${skill}/SKILL.md, ${skill}/scripts/,
  ${skill}/assets/prompts/ and ${skill}/design/index.md.
Look for: bugs and errors in the flow, wasted or repeated ant calls, retries and
loops, ants that died, slow stages, plans or prompts that misled an ant, checks
that were missing or too weak, rules that did not fit this task, and gaps or
missing steps. Every finding needs evidence from this run; never guess.
Write ${file}: a two or three line summary, then the findings ranked costliest
first, each with category (${CATEGORIES.join(', ')}), title, evidence, impact,
suggested change and where (file and rule). Nothing to improve: say so.
Return the same findings.`
let r = await agent(prompt, { label: 'retrospective-ant', phase: 'Retrospective', model: MODEL, effort: EFFORT.retrospective, schema: RETRO })
if (r == null) r = await agent(prompt, { label: 'retrospective-ant', phase: 'Retrospective', model: MODEL, effort: EFFORT.retrospective, schema: RETRO })
const ok = r && r.written === true && Array.isArray(r.findings)
await logNow([{ run: env.run, who: 'retrospective ant', event: r == null ? 'died' : ok ? `${r.findings.length} finding${r.findings.length === 1 ? '' : 's'}` : 'no report',
  ...(r != null ? { detail: String(r.summary || '').slice(0, 400) } : {}) }])
if (r == null) return { stage: 'error', reason: 'the retrospective ant died twice' }
if (!ok) return { stage: 'error', reason: `the retrospective ant did not write ${file} or gave no findings list` }
const findings = r.findings.filter(f => f && typeof f === 'object').map(f => ({
  category: CATEGORIES.includes(f.category) ? f.category : 'improvement',
  title: String(f.title || ''), evidence: String(f.evidence || ''), impact: String(f.impact || ''),
  change: String(f.change || ''), where: String(f.where || ''),
}))
return { stage: 'retro', file, summary: String(r.summary || ''), findings }
