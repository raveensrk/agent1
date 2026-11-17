// Checks for the workflow scripts' own logic, with stand-in ants: no model runs.
// Run: timeout 120 node --test skills/ishikari/tests/test_workflows.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const SCRIPTS = join(dirname(fileURLToPath(import.meta.url)), '..', 'scripts')
const env = { repo: '/r', state: '/s', run: 'r1', main: 'main', tool: '/t/ishikari.py' }

// Run a workflow script body with a fake runtime. ant(prompt, opts) answers each agent call.
function run(name, args, ant) {
  const src = readFileSync(join(SCRIPTS, name), 'utf8').replace('export const meta', 'const meta')
  const calls = []
  const agent = async (p, o) => { calls.push(o.label); return ant(p, o) }
  const parallel = fns => Promise.all(fns.map(f => f()))
  const body = new Function('args', 'agent', 'parallel', 'phase', 'log', 'workflow', `return (async () => {${src}})()`)
  return body(args, agent, parallel, () => {}, () => {}, async () => ({})).then(out => ({ out, calls }))
}

const clear = { summary: '', critique: [], research: [], next: { question: '', answers: [] }, remaining: 0, reportWritten: true, blocker: '', testCommand: 't', checkCommand: '' }
const goodReq = { requirement: { needed: true, file: '/r/requirements.org', entry: '* OPEN X\n:PROPERTIES:\n:ID: X-1\n:END:', proof: 'repo' } }

function planWith(plans, req = goodReq, review = clear) {
  return run('ishikari-plan.js', { env, task: 't' }, (p, o) =>
    o.label.startsWith('investigator') ? review
      : o.label === 'add-requirement-ant' ? req
      : o.label.startsWith('researcher') ? { findings: 'f' }
      : { designWritten: true, plans })
}

test('plan: asks one question at a time', async () => {
  const { out } = await planWith([], goodReq, { ...clear, next: { question: 'Q?', answers: ['a'] }, remaining: 3 })
  assert.equal(out.stage, 'question')
  assert.equal(out.question.question, 'Q?')
  assert.equal(out.remaining, 3)
})

test('plan: research runs before the question, at most 5 ants', async () => {
  let n = 0
  const { out, calls } = await run('ishikari-plan.js', { env, task: 't' }, (p, o) => {
    if (o.label.startsWith('researcher')) return { findings: 'f' }
    n++
    return n === 1 ? { ...clear, research: ['a', 'b', 'c', 'd', 'e', 'f', 'g'] } : { ...clear, next: { question: 'Q?', answers: ['a'] } }
  })
  assert.equal(calls.filter(c => c.startsWith('researcher')).length, 5)
  assert.equal(out.findings.length, 5)
  assert.equal(out.stage, 'question')
})

test('plan: a missing report is an error', async () => {
  const { out } = await planWith([], goodReq, { ...clear, reportWritten: false })
  assert.equal(out.stage, 'error')
})

test('plan: good plans pass', async () => {
  const { out } = await planWith([{ id: 'a', title: 'A', files: ['x'] }, { id: 'b', title: 'B', files: ['x', 'y'], after: ['a'] }])
  assert.equal(out.stage, 'plans')
  assert.equal(out.design, '/s/plans/r1/architecture.md')
})

test('plan: two parallel tasks on one file are refused', async () => {
  const { out } = await planWith([{ id: 'a', title: 'A', files: ['x'] }, { id: 'b', title: 'B', files: ['x'] }])
  assert.equal(out.stage, 'error')
  assert.match(out.reason, /both edit x/)
})

test('plan: loops and unknown ids in after are refused', async () => {
  let { out } = await planWith([{ id: 'a', title: 'A', files: ['x'], after: ['b'] }, { id: 'b', title: 'B', files: ['y'], after: ['a'] }])
  assert.match(out.reason, /loop in after/)
  ;({ out } = await planWith([{ id: 'a', title: 'A', files: ['x'], after: ['zz'] }]))
  assert.match(out.reason, /unknown plan/)
})

test('plan: a requirement outside the repo or without :ID: is refused', async () => {
  let { out } = await planWith([{ id: 'a', title: 'A', files: ['x'] }], { requirement: { ...goodReq.requirement, file: '/etc/x.org' } })
  assert.match(out.reason, /inside \/r/)
  ;({ out } = await planWith([{ id: 'a', title: 'A', files: ['x'] }], { requirement: { ...goodReq.requirement, entry: '* OPEN X' } }))
  assert.match(out.reason, /no :ID:/)
})

test('build: a failed app check becomes its own task from main', async () => {
  const prompts = []
  const { out } = await run('ishikari-build.js', { env, bugs: [{ task: 'check-fix', bug: 'app does not start' }] }, (p, o) => {
    prompts.push(p)
    if (o.label.startsWith('detective')) return { cause: 'c', plan: 'p' }
    if (o.label.startsWith('worker')) return { status: 'built', notes: 'n' }
    if (o.label.startsWith('inspector')) return { fixed: [{ id: 'check-fix#1', fixed: true }], bugs: [] }
    return {}
  })
  assert.equal(out.stage, 'build')
  assert.equal(out.tasks.length, 1)
  assert.equal(out.tasks[0].branch, 'ishikari/r1/check-fix')
  assert.equal(out.tasks[0].status, 'awaiting review')
  assert.ok(prompts.some(p => p.includes('worktree add -b ishikari/r1/check-fix') && p.includes(' main')))
})

test('build: a bug still open after 3 tries escalates', async () => {
  const { out } = await run('ishikari-build.js', { env, plans: [{ id: 'a', title: 'A' }] }, (p, o) => {
    if (o.label.startsWith('detective')) return { cause: 'c', plan: 'p' }
    if (o.label.startsWith('worker')) return { status: 'built', notes: 'n' }
    if (o.label === 'inspector-ant:a:check') return { bugs: ['broken'], cause: 'c', plan: 'p' }
    if (o.label.startsWith('inspector')) return { fixed: [{ id: 'a#1', fixed: false }], bugs: [] }
    return {}
  })
  assert.equal(out.tasks[0].status, 'escalated')
  assert.equal(out.tasks[0].tries, 3)
})

test('finish: dropped branches are kept, merged ones removed', async () => {
  const prompts = []
  const { out } = await run('ishikari-finish.js', {
    env, approved: [{ id: 'a', branch: 'ishikari/r1/a' }], drop: [{ id: 'b', branch: 'ishikari/r1/b' }], cleanup: true,
  }, (p, o) => {
    prompts.push(p)
    if (o.label === 'merger-ant') return { sha: 'abc', results: [{ id: 'a', outcome: 'merged', detail: '' }] }
    if (o.label === 'philosopher-ant') return { critiques: [] }
    return { moved: true, reason: '' }
  })
  assert.equal(out.mainMoved, true)
  const fin = prompts.find(p => p.includes("finisher ant"))
  assert.ok(fin.includes('   - ishikari/r1/a'))
  assert.ok(!fin.includes('   - ishikari/r1/b'))
})

// ---- stress: malformed input and half answers never crash or pass silently ----

test('stress: plan survives broken ant replies', async () => {
  for (const reply of [{}, { requirement: null }, { designWritten: true, plans: null }, { designWritten: true, plans: [{ id: 'a', files: null, after: 'b' }] }]) {
    const { out } = await run('ishikari-plan.js', { env, task: 't', answered: 'x', findings: 'y' }, (p, o) =>
      o.label.startsWith('investigator') ? clear : o.label === 'add-requirement-ant' ? (reply.requirement === null ? reply : goodReq) : reply)
    assert.equal(out.stage, 'error', JSON.stringify(reply))
  }
})

test('stress: plan sees "./x" and "x" as one file', async () => {
  const { out } = await planWith([{ id: 'a', title: 'A', files: ['./x'] }, { id: 'b', title: 'B', files: ['x'] }])
  assert.match(out.reason, /both edit x/)
})

test('stress: plan stops a repeated question', async () => {
  const { out } = await run('ishikari-plan.js', { env, task: 't', answered: [{ question: 'Q?', answer: 'a' }] },
    () => ({ ...clear, next: { question: ' q? ', answers: ['a'] } }))
  assert.match(out.reason, /same question/)
})

test('stress: build refuses bad input and foreign branches', async () => {
  let { out } = await run('ishikari-build.js', { env, plans: 'a' }, () => ({}))
  assert.equal(out.stage, 'error')
  ;({ out } = await run('ishikari-build.js', { env, bugs: [{ task: 'a', branch: 'x; rm -rf /', bug: 'b' }] }, () => ({})))
  assert.match(out.tasks[0].bugs[0], /bad branch/)
})

test('stress: a half answer from the integrator is not a combined pass', async () => {
  const { out } = await run('ishikari-build.js', { env, plans: [{ id: 'a' }, { id: 'b' }] }, (p, o) =>
    o.label.startsWith('worker') ? { status: 'built', notes: '' }
      : o.label.startsWith('inspector') ? { bugs: [] }
      : o.label.startsWith('integrator') ? { sha: 's', results: [{ id: 'a', outcome: 'merged', detail: '' }] } : {})
  assert.equal(out.together, null)
})

test('stress: finish refuses bad lists, foreign branches and duplicates', async () => {
  const cases = [{ drop: 'x' }, { approved: [{ id: 'a', branch: 'main' }] },
    { approved: [{ id: 'a', branch: 'ishikari/r1/a' }, { id: 'a', branch: 'ishikari/r1/a' }] }]
  for (const c of cases) {
    const { out } = await run('ishikari-finish.js', { env, ...c }, () => ({ moved: true }))
    assert.equal(out.stage, 'error', JSON.stringify(c))
  }
})

test('stress: finish never claims main moved when nothing merged', async () => {
  const { out } = await run('ishikari-finish.js', { env, approved: [{ id: 'a', branch: 'ishikari/r1/a' }] }, (p, o) =>
    o.label === 'merger-ant' ? { sha: '', results: [] } : { moved: true, reason: '' })
  assert.equal(out.mainMoved, false)
  assert.equal(out.waiting.length, 1)
})
