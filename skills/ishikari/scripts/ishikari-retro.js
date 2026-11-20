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
// write is retrospective.md in the run's plans folder, outside the repo. That is
// checked, not only asked: the ant takes a digest of the repo's refs and
// worktrees before and after, and a difference is a stage error.

// For now every ant runs on the latest Opus at low effort.
const MODEL = 'opus'
const EFFORT = { retrospective: 'low' }
const CATEGORIES = ['bug', 'error', 'inefficiency', 'gap', 'missing', 'improvement']

const { env = {}, outcome = '' } = args
const bad = []
// Paths, the branch and the commands go into shell commands inside the ants'
// prompts: only safe characters are let through (ishikari.py setup checks too).
for (const k of ['repo', 'state', 'tool']) if (!/^\/[A-Za-z0-9._\/+-]+$/.test(env[k] || '')) bad.push(`env.${k} must be an absolute path of letters, digits and . _ / + -`)
if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(env.run || '')) bad.push('env.run must be a run id')
if (!/^[A-Za-z0-9._][A-Za-z0-9._\/-]*$/.test(env.main || '')) bad.push('env.main must be a branch name')
for (const k of ['testCommand', 'checkCommand']) if (env[k] != null && (typeof env[k] !== 'string' || /[\n\r`]/.test(env[k]))) bad.push(`env.${k} must be one line with no backtick`)
if (bad.length) return { stage: 'error', reason: bad.join('; ') }

const planDir = `${env.state}/plans/${env.run}`
const file = `${planDir}/retrospective.md`
const skill = env.tool.replace(/\/scripts\/[^/]+$/, '')

// One logbook entry for the ant, returned as the result's log; the main
// session's `ishikari.py save` appends it, with no ant.
const entries = []
const logNow = rows => entries.push(...rows)
const out = r => ({ ...r, log: entries })

const RETRO = {
  type: 'object',
  properties: {
    written: { type: 'boolean', description: `true once ${file} is written` },
    lines: { type: 'integer', description: `line count of ${file} after you wrote it` },
    before: { type: 'string', description: 'the digest taken before you read anything' },
    after: { type: 'string', description: 'the same digest, taken after you wrote the report' },
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
  required: ['written', 'lines', 'before', 'after', 'summary', 'findings'],
}

phase('Retrospective')
const prompt = `You are the retrospective ant of the Ishikari workflow. The run is over
(${String(outcome).trim() || 'outcome not given'}). Review how the Ishikari flow ran this time and
report where it can improve. You judge the flow, not the repo's code: the judge
and the janitor cover the code.
Load the /retrospective-ant skill and follow its Ishikari mode (if it is
unavailable, read ${skill}/../retrospective-ant/SKILL.md).
Repo: ${env.repo} (main branch: ${env.main}). Run id: ${env.run}.
Read only. Change no code, branch, worktree, logbook entry or repo file, and run
no command that writes. Your one write is ${file}
(make its folder if it is missing).
First, before reading anything, take this digest and return its output as "before":
\`{ git -C ${env.repo} for-each-ref; git -C ${env.repo} worktree list --porcelain; git -C ${env.repo} status --porcelain; } | shasum\`
After writing the report, run it again and return that as "after".
Some of the files below may be missing (a run that stopped early has few):
that is normal, and worth a finding only if the flow should have made them.
Read:
- this run's logbook entries: \`python3 ${env.tool} log status ${env.state} ${env.run}\` and
  the entries with Run: ${env.run} in ${env.state}/logbook.rec;
- ${planDir}: product_spec.md, tech_spec.md, the worker plans, any
  cleanup.md, and every stage result <stage>-<n>.json;
- the run's git history: the branches \`git -C ${env.repo} branch --list 'ishikari/${env.run}/*'\`
  and their commits, and the last 30 commits of ${env.main} (\`git -C ${env.repo} log --oneline -30 ${env.main}\`);
- Ishikari's own source, to name what to change: ${skill}/SKILL.md, ${skill}/scripts/,
  ${skill}/assets/prompts/ and ${skill}/design/index.md.
Look for what the skill lists, in this run's flow.
Write ${file}: a two or three line summary, then the findings ranked costliest
first, each with category (${CATEGORIES.join(', ')}), title, evidence, impact,
suggested change and where (file and rule). Nothing to improve: say so.
Return the same findings, and the report's line count as lines.`
const ask = () => agent(prompt, { label: 'retrospective-ant', phase: 'Retrospective', model: MODEL, effort: EFFORT.retrospective, schema: RETRO }).catch(() => null)
let r = await ask()
if (r == null) r = await ask()
const digest = x => typeof x === 'string' && /^[0-9a-f]{40}/.test(x.trim()) ? x.trim().slice(0, 40) : ''
const touched = r != null && (!digest(r.before) || digest(r.before) !== digest(r.after))
const ok = r && r.written === true && Number.isInteger(r.lines) && r.lines > 0 && Array.isArray(r.findings) && !touched
logNow([{ run: env.run, who: 'retrospective ant', event: r == null ? 'died' : touched ? 'repo changed' : ok ? `${r.findings.length} finding${r.findings.length === 1 ? '' : 's'}` : 'no report',
  ...(r != null ? { detail: String(r.summary || '').slice(0, 400) } : {}) }])
if (r == null) return out({ stage: 'error', reason: 'the retrospective ant died twice' })
if (touched) return out({ stage: 'error', reason: `the retrospective ant was to change nothing, but the repo's refs, worktrees or status differ before and after it (or it gave no digest). Check ${env.repo}; ${file} is not trusted.` })
if (!ok) return out({ stage: 'error', reason: `the retrospective ant did not write ${file} or gave no findings list` })
const findings = r.findings.filter(f => f && typeof f === 'object').map(f => ({
  category: CATEGORIES.includes(f.category) ? f.category : 'improvement',
  title: String(f.title || ''), evidence: String(f.evidence || ''), impact: String(f.impact || ''),
  change: String(f.change || ''), where: String(f.where || ''),
}))
return out({ stage: 'retro', file, summary: String(r.summary || ''), findings })
