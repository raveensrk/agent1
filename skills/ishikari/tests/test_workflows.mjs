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
function run(name, args, ant, clerk = () => ({})) {
  const src = readFileSync(join(SCRIPTS, name), 'utf8').replace('export const meta', 'const meta')
  const calls = []
  const instant = []
  // Instant logbook appends go to their own list, so call order reads as the run.
  const agent = async (p, o) => {
    if (o.label === 'logbook-clerk:now') { instant.push(p); return clerk(p) }
    calls.push(o.label); return ant(p, o)
  }
  const parallel = fns => Promise.all(fns.map(f => f()))
  const body = new Function('args', 'agent', 'parallel', 'phase', 'log', 'workflow', `return (async () => {${src}})()`)
  return body(args, agent, parallel, () => {}, () => {}, async () => ({})).then(out => ({ out, calls, instant }))
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
    if (o.label.startsWith('worker')) return { status: 'built', notes: 'n' }
    if (o.label.startsWith('detective')) return { fixed: [{ id: 'check-fix#1', fixed: true }], bugs: [] }
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
    if (o.label.startsWith('worker')) return { status: 'built', notes: 'n' }
    if (o.label === 'detective-ant:a:check') return { bugs: ['broken'], cause: 'c', plan: 'p' }
    if (o.label.startsWith('detective')) return { fixed: [{ id: 'a#1', fixed: false }], bugs: [] }
    return {}
  })
  assert.equal(out.tasks[0].status, 'escalated')
  assert.equal(out.tasks[0].tries, 3)
})

test('build: a task that keeps finding new bugs gives up after MAX_ROUNDS (3) rounds', async () => {
  let n = 0
  const { out, calls } = await run('ishikari-build.js', { env, plans: [{ id: 'a', title: 'A' }] }, (p, o) => {
    if (o.label.startsWith('worker')) return { status: 'built', notes: 'n', sha: 'abc1234', testsPassed: true, testSummary: 'ok' }
    if (o.label === 'detective-ant:a:check') return { bugs: ['bug0'], cause: 'c', plan: 'p' }
    n++
    return { fixed: [{ id: `a#${n}`, fixed: true }], bugs: [`bug${n}`] }
  })
  assert.equal(out.tasks[0].status, 'escalated')
  assert.deepEqual(calls.filter(c => c.startsWith('worker-ant:a:fix')), ['worker-ant:a:fix1', 'worker-ant:a:fix2', 'worker-ant:a:fix3'])
  assert.equal(out.tasks[0].tries, 1)
  assert.ok(calls.includes('detective-ant:a:recheck3'))
  assert.ok(!calls.some(c => c.includes('fix4')))
})

// Prompts by label for a build run; worker(label) gives each worker's extra reply fields.
async function buildPrompts(args, worker, inspector = () => ({ bugs: [] })) {
  const prompts = {}
  await run('ishikari-build.js', { env, ...args }, (p, o) => {
    prompts[o.label] = p
    if (o.label.startsWith('worker')) return { status: 'built', notes: 'n', ...worker(o.label) }
    return inspector(o.label)
  })
  return prompts
}

test('build: no valid worker sha means the inspector runs the tests itself', async () => {
  for (const extra of [{}, { sha: 'zzz', testsPassed: true, testSummary: 's' }]) {
    const ins = (await buildPrompts({ plans: [{ id: 'a' }] }, () => extra))['detective-ant:a:check']
    assert.ok(ins.includes("Run the repo's tests inside that worktree."))
    assert.ok(!ins.includes('reuse'))
  }
})

test('build: each recheck gets that round\'s worker sha', async () => {
  const pr = await buildPrompts({ plans: [{ id: 'a' }] },
    l => ({ sha: l.endsWith('build') ? 'aaa1111' : 'bbb2222', testsPassed: true, testSummary: 's' }),
    l => l === 'detective-ant:a:check' ? { bugs: ['x'], cause: 'c', plan: 'p' } : { fixed: [{ id: 'a#1', fixed: true }], bugs: [] })
  assert.ok(pr['detective-ant:a:check'].includes('aaa1111'))
  assert.ok(pr['detective-ant:a:recheck1'].includes('bbb2222'))
  assert.ok(!pr['detective-ant:a:recheck1'].includes('aaa1111'))
  assert.ok(pr['detective-ant:a:recheck1'].includes('status --porcelain'))
})

test('build: after a merge update the check uses the update worker sha', async () => {
  const pr = await buildPrompts({ plans: [{ id: 'a' }, { id: 'b', after: ['a'] }] },
    l => ({ sha: l === 'worker-ant:b:update' ? 'ccc3333' : 'aaa1111', testsPassed: true, testSummary: 's' }),
    l => l === 'detective-ant:a:check' ? { bugs: ['x'], cause: 'c', plan: 'p' } : { fixed: [{ id: 'a#1', fixed: true }], bugs: [] })
  assert.ok(pr['worker-ant:b:update'])
  assert.ok(pr['detective-ant:b:check'].includes('ccc3333'))
})

test('build: the test command is kept exactly', async () => {
  const pr = await buildPrompts({ env: { ...env, testCommand: 'make TEST=Foo' }, plans: [{ id: 'a' }] },
    () => ({ sha: 'aaa1111', testsPassed: false, testSummary: 's' }))
  assert.ok(pr['worker-ant:a:build'].includes('`make TEST=Foo`'))
  assert.ok(pr['detective-ant:a:check'].includes('run the tests with `make TEST=Foo`'))
})

test('build: the inspector gets the worker sha and reuses its test result', async () => {
  const prompts = {}
  await run('ishikari-build.js', { env, plans: [{ id: 'a', title: 'A' }] }, (p, o) => {
    prompts[o.label] = p
    if (o.label.startsWith('worker')) return { status: 'built', notes: 'n', sha: 'deadbee1', testsPassed: true, testSummary: '12 passed' }
    return { bugs: [] }
  })
  const ins = prompts['detective-ant:a:check']
  assert.ok(ins.includes('deadbee1'))
  assert.ok(ins.includes('12 passed'))
  assert.ok(ins.includes('reuse that result'))
  assert.ok(prompts['worker-ant:a:build'].includes('as sha'))
})

test('finish: dropped branches are kept, merged ones removed', async () => {
  const prompts = []
  const { out } = await run('ishikari-finish.js', {
    env, approved: [{ id: 'a', branch: 'ishikari/r1/a' }], drop: [{ id: 'b', branch: 'ishikari/r1/b' }], cleanup: true,
  }, (p, o) => {
    prompts.push(p)
    if (o.label === 'merger-ant') return { sha: 'abc', results: [{ id: 'a', outcome: 'merged', detail: '' }] }
    if (o.label.startsWith('judge-ant')) return { score: 9, gaps: [] }
    return { moved: true, reason: '' }
  })
  assert.equal(out.mainMoved, true)
  const fin = prompts.find(p => p.includes("finisher ant"))
  assert.ok(fin.includes('   - ishikari/r1/a'))
  assert.ok(!fin.includes('   - ishikari/r1/b'))
})

function finishWith(jan) {
  const prompts = {}
  return run('ishikari-finish.js', { env, approved: [{ id: 'a', branch: 'ishikari/r1/a' }] }, (p, o) => {
    prompts[o.label] = p
    if (o.label === 'merger-ant') return { sha: 'abc', results: [{ id: 'a', outcome: 'merged', detail: '' }] }
    if (o.label === 'janitor-ant') return jan
    if (o.label.startsWith('judge-ant')) return { score: 9, gaps: [] }
    return { moved: true, reason: '' }
  }).then(r => ({ ...r, prompts, fin: prompts['finisher-ant'] }))
}

test('finish: the janitor cleans, tests, commits and lands its cleanup alone, judge after it', async () => {
  const { out, calls, fin, prompts } = await finishWith({ changed: true, title: 'tidy', testsPassed: true, landed: true, sha: 'def0123' })
  assert.deepEqual(out.cleanup, { title: 'tidy', landed: true })
  assert.equal(out.sha, 'def0123')
  assert.deepEqual(calls.slice(1, 3), ['janitor-ant', 'judge-ant:1'])
  assert.ok(!calls.some(c => c.includes('cleanup')))  // no worker, inspector, detective or merger for it
  assert.ok(prompts['janitor-ant'].includes('merge --ff-only ishikari/r1/_cleanup'))
  assert.ok(fin.includes('   - ishikari/r1/_cleanup'))
})

test('finish: a janitor cleanup that fails its tests is dropped, branch kept, main still moves', async () => {
  const { out, fin } = await finishWith({ changed: true, title: 'tidy', testsPassed: false, landed: false, reason: 'broke x' })
  assert.equal(out.mainMoved, true)
  assert.equal(out.cleanup.landed, false)
  assert.equal(out.cleanup.reason, 'broke x')
  assert.equal(out.cleanup.branch, 'ishikari/r1/_cleanup')
  assert.ok(!fin.includes('   - ishikari/r1/_cleanup'))
})

test('finish: a janitor that says landed but gives no commit is not trusted', async () => {
  const { out } = await finishWith({ changed: true, title: 'tidy', testsPassed: true, landed: true })
  assert.equal(out.cleanup.landed, false)
  assert.equal(out.sha, 'abc')
})

test('finish: nothing to clean leaves no cleanup', async () => {
  const { out } = await finishWith({ changed: false, title: '', testsPassed: true, landed: false })
  assert.equal(out.cleanup, null)
})

function judgeRun(scores, answer = () => null) {
  const prompts = {}
  let k = 0
  return run('ishikari-finish.js', { env, approved: [{ id: 'a', branch: 'ishikari/r1/a' }], cleanup: true }, (p, o) => {
    prompts[o.label] = p
    if (o.label === 'merger-ant') return { sha: 'abc', results: [{ id: 'a', outcome: 'merged', detail: '' }] }
    if (o.label.startsWith('judge-ant')) return scores[k++]
    return answer(o) || (o.label.startsWith('worker') ? { status: 'built', notes: '' }
      : o.label.startsWith('detective') ? { bugs: [] }
      : o.label === 'merger-ant:judge-fix' ? { ok: true, sha: 'fff' } : { moved: true, reason: '' })
  }).then(r => ({ ...r, prompts }))
}

test('finish: a judge score of 7 or more needs no fix round', async () => {
  const { out, calls, prompts } = await judgeRun([{ score: 7, gaps: ['small'] }])
  assert.deepEqual(out.verdict, { score: 7, gaps: ['small'], fixed: false, flagged: false })
  assert.ok(!calls.some(c => c.includes('judge-fix')))
  assert.ok(prompts['judge-ant:1'].includes('/s/plans/r1'))
  assert.equal(out.mainMoved, true)
})

test('finish: a low judge score gets one fix round, then a second score', async () => {
  const { out, calls, prompts } = await judgeRun([{ score: 4, gaps: ['x missing'] }, { score: 8, gaps: [] }])
  assert.deepEqual(calls.slice(1, 6), ['judge-ant:1', 'worker-ant:judge-fix', 'detective-ant:judge-fix', 'merger-ant:judge-fix', 'judge-ant:2'])
  assert.ok(prompts['worker-ant:judge-fix'].includes('- x missing'))
  assert.deepEqual(out.verdict, { score: 8, gaps: [], fixed: true, flagged: false, first: 4 })
  assert.equal(out.sha, 'fff')
  assert.ok(prompts['finisher-ant'].includes('   - ishikari/r1/_judgefix'))
})

test('finish: still low after the fix round, main moves and the verdict is flagged', async () => {
  const { out, calls } = await judgeRun([{ score: 3, gaps: ['g'] }, { score: 5, gaps: ['g'] }])
  assert.equal(out.verdict.flagged, true)
  assert.equal(out.verdict.score, 5)
  assert.equal(calls.filter(c => c.startsWith('judge-ant')).length, 2)
  assert.equal(out.mainMoved, true)
})

test('finish: a judge fix that fails its check is not landed, branch kept, flagged', async () => {
  const { out, calls, prompts } = await judgeRun([{ score: 2, gaps: ['g'] }],
    o => o.label === 'detective-ant:judge-fix' ? { bugs: ['broke y'] } : null)
  assert.ok(!calls.includes('merger-ant:judge-fix'))
  assert.ok(!calls.includes('judge-ant:2'))
  assert.equal(out.verdict.flagged, true)
  assert.equal(out.verdict.reason, 'broke y')
  assert.ok(!prompts['finisher-ant'].includes('_judgefix'))
  assert.equal(out.mainMoved, true)
})

test('finish: a dead or nonsense judge flags the run but never blocks main', async () => {
  for (const bad of [null, { score: 'nine', gaps: [] }]) {
    const { out } = await judgeRun([bad])
    assert.equal(out.verdict.flagged, true)
    assert.equal(out.mainMoved, true)
  }
  const { out } = await judgeRun([{ score: 42, gaps: [] }])
  assert.equal(out.verdict.score, 10)
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
      : o.label.startsWith('detective') ? { bugs: [] }
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

test('plan: a live investigation skips Review', async () => {
  const { out, calls } = await run('ishikari-plan.js', { env, task: 't', investigated: { testCommand: 'npm test', checkCommand: '' } }, (p, o) =>
    o.label === 'add-requirement-ant' ? goodReq : { designWritten: true, plans: [{ id: 'a', title: 'A', files: ['x'] }] })
  assert.equal(out.stage, 'plans')
  assert.equal(out.testCommand, 'npm test')
  assert.ok(!calls.some(c => c.startsWith('investigator')))
})

// ---- finish: judge after cleanup, trial-merge reuse, verified merges, check-fix cap ----
const SHA = 'aaaaaaa', TOG = 'bbbbbbb'
const T = id => ({ id, branch: `ishikari/r1/${id}` })
function finishRun(args, answer) {
  const prompts = {}
  return run('ishikari-finish.js', { env, cleanup: true, ...args }, (p, o) => {
    prompts[o.label] = p
    return answer(o, p) || (o.label.startsWith('judge-ant') ? { score: 9, gaps: [] } : { moved: true, reason: '' })
  }).then(r => ({ ...r, prompts }))
}

test('finish: the judge starts only after the janitor ends', async () => {
  let janitorDone = false
  const { out } = await run('ishikari-finish.js', { env, approved: [T('a')] }, async (p, o) => {
    if (o.label === 'merger-ant') return { sha: 'abc', results: [{ id: 'a', outcome: 'merged', detail: '' }] }
    if (o.label === 'janitor-ant') { await new Promise(r => setTimeout(r, 5)); janitorDone = true; return { changed: false, title: '', testsPassed: true, landed: false } }
    if (o.label.startsWith('judge-ant')) { assert.ok(janitorDone); return { score: 8, gaps: [] } }
    return { moved: true, reason: '' }
  })
  assert.equal(out.verdict.score, 8)
  assert.equal(out.mainMoved, true)
})

test('finish: an added task goes on top of the reused trial merge', async () => {
  const { prompts } = await finishRun({ approved: [T('a'), T('b'), { ...T('c'), after: ['a'] }], together: { sha: TOG, tasks: ['a', 'b'] } },
    o => o.label === 'merger-ant' ? { sha: SHA, results: [] } : null)
  const m = prompts['merger-ant']
  assert.ok(m.includes(`worktree add -b ishikari/r1/_finish /s/worktrees/ishikari__r1___finish ${TOG}`))
  assert.ok(m.includes('add only these tasks on top, in this order, as\nin the steps below: c.'))
})

test('finish: a dropped task inside the trial merge, or an added task it is built on, means a full merge', async () => {
  for (const args of [
    { approved: [T('a')], together: { sha: TOG, tasks: ['a', 'b'] } },
    { approved: [T('a'), { ...T('b'), after: ['c'] }, T('c')], together: { sha: TOG, tasks: ['a', 'b'] } },
    { approved: [T('a'), T('b')], together: { sha: 'not a sha', tasks: ['a'] } },
  ]) {
    const { prompts } = await finishRun(args, o => o.label === 'merger-ant' ? { sha: SHA, results: [] } : null)
    assert.ok(!prompts['merger-ant'].includes(TOG), JSON.stringify(args))
  }
})

test('finish: git decides what merged, not the merger report', async () => {
  const { out } = await finishRun({ approved: [T('a'), T('b'), T('c')] }, (o, p) =>
    o.label === 'merger-ant' ? (assert.ok(p.includes('cherry <sha> <branch>') && p.includes('- a: ishikari/r1/a')),
      { sha: SHA, results: [{ id: 'b', outcome: 'merged', detail: '' }, { id: 'c', outcome: 'conflict', detail: 'x' }], landed: ['a'], missing: ['b', 'c'] }) : null)
  assert.deepEqual(out.merged, ['a'])
  assert.deepEqual(out.waiting, [])
  assert.deepEqual(out.bugs.map(b => b.task), ['b', 'c'])
  assert.match(out.bugs[0].bug, /conflict.*said merged/)
})

test('finish: a garbled git cherry check falls back to the merger report', async () => {
  const { out } = await finishRun({ approved: [T('a'), T('b')] }, o =>
    o.label === 'merger-ant' ? { sha: SHA, results: [{ id: 'a', outcome: 'merged', detail: '' }, { id: 'b', outcome: 'merged', detail: '' }], landed: ['a'], missing: [] } : null)
  assert.deepEqual(out.merged, ['a', 'b'])
})

test('finish: one check-fix round, a second is refused', async () => {
  const failing = o => o.label === 'merger-ant' ? { sha: 'abc', results: [{ id: 'a', outcome: 'merged', detail: '' }] }
    : o.label === 'finisher-ant' ? { moved: true, reason: '', check: { ran: true, ok: false, output: 'boom' } } : null
  let { out } = await finishRun({ approved: [T('a')], env: { ...env, checkCommand: 'make' } }, failing)
  assert.deepEqual(out.checkFix, { task: 'check-fix', bug: 'boom' })
  assert.equal(out.checkFixDone, false)
  ;({ out } = await finishRun({ approved: [T('a')], checkFixDone: true, env: { ...env, checkCommand: 'make' } }, failing))
  assert.equal(out.checkFix, null)
  assert.equal(out.checkFixRefused, true)
  assert.equal(out.checkFixDone, true)
  ;({ out } = await finishRun({ approved: [T('check-fix')], env: { ...env, checkCommand: 'make' } }, o =>
    o.label === 'merger-ant' ? { sha: 'abc', results: [{ id: 'check-fix', outcome: 'merged', detail: '' }] } : failing(o)))
  assert.equal(out.checkFix, null)
  ;({ out } = await finishRun({ approved: [T('a')], checkFixDone: 'yes' }, failing))
  assert.equal(out.stage, 'error')
})

// ---- judge round 1: judge after the ff, tip checks, git cherry strictness ----
test('finish: the judge reads after the janitor has landed its cleanup', async () => {
  const { calls, prompts } = await finishWith({ changed: true, title: 'tidy', testsPassed: true, landed: true, sha: 'def0123' })
  assert.ok(calls.indexOf('judge-ant:1') > calls.indexOf('janitor-ant'))
  assert.ok(prompts['judge-ant:1'].includes('cleanup on top'))
})

test('finish: both trial-merge reuse paths check each reused branch tip', async () => {
  for (const approved of [[T('a'), T('b')], [T('a'), T('b'), T('c')]]) {
    const { prompts } = await finishRun({ approved, together: { sha: TOG, tasks: ['a', 'b'] } },
      o => o.label === 'merger-ant' ? { sha: SHA, results: [] } : null)
    const m = prompts['merger-ant']
    assert.ok(m.includes(`merge-base --is-ancestor <branch> ${TOG}`))
    assert.ok(/If any (ancestor )?check or the worktree add fails, do the normal steps/.test(m))
  }
})

test('finish: a stale branch tip leads the merger to the full merge, and git is still asked', async () => {
  const { out, calls } = await finishRun({ approved: [T('a'), T('b')], together: { sha: TOG, tasks: ['a', 'b'] } }, o =>
    o.label === 'merger-ant' ? { sha: SHA, fastPath: false, results: [{ id: 'a', outcome: 'merged', detail: '' }, { id: 'b', outcome: 'merged', detail: '' }], landed: ['a', 'b'], missing: [] } : null)
  assert.ok(!calls.includes('verifier-ant'))
  assert.deepEqual(out.merged, ['a', 'b'])
})

test('finish: an exact fast path is trusted over its git cherry check', async () => {
  const { out } = await finishRun({ approved: [T('a'), T('b')], together: { sha: TOG, tasks: ['a', 'b'] } }, o =>
    o.label === 'merger-ant' ? { sha: TOG, fastPath: true, results: [{ id: 'a', outcome: 'merged', detail: '' }, { id: 'b', outcome: 'merged', detail: '' }], landed: [], missing: ['a', 'b'] } : null)
  assert.deepEqual(out.merged, ['a', 'b'])
})

test('finish: unknown or extra git cherry ids fall back to the merger report', async () => {
  for (const v of [{ landed: ['a', 'zz'], missing: ['b'] }, { landed: ['a', 'b'], missing: ['b'] }]) {
    const { out } = await finishRun({ approved: [T('a'), T('b')] }, o =>
      o.label === 'merger-ant' ? { sha: SHA, results: [{ id: 'a', outcome: 'merged', detail: '' }, { id: 'b', outcome: 'conflict', detail: 'x' }], ...v } : null)
    assert.deepEqual(out.merged, ['a'], JSON.stringify(v))
    assert.deepEqual(out.bugs.map(b => b.task), ['b'])
  }
})

test('finish: checkFixDone must be a boolean', async () => {
  const { out } = await finishRun({ approved: [T('a')], checkFixDone: 'yes' }, () => null)
  assert.equal(out.stage, 'error')
  assert.match(out.reason, /checkFixDone/)
})

// ---- jury: one juror ant per task, the judge decides ----
test('finish: one task, the judge works alone', async () => {
  const { calls } = await judgeRun([{ score: 9, gaps: [] }])
  assert.ok(!calls.some(c => c.startsWith('juror')))
})

test('finish: many tasks, one juror per task, at most 5 at once, judge sees their reports', async () => {
  const ids = ['a', 'b', 'c', 'd', 'e', 'f', 'g']
  let live = 0, peak = 0
  const prompts = {}
  const { out, calls } = await run('ishikari-finish.js', { env, approved: ids.map(T), cleanup: true }, async (p, o) => {
    prompts[o.label] = p
    if (o.label === 'merger-ant') return { sha: 'abc', results: ids.map(id => ({ id, outcome: 'merged', detail: '' })) }
    if (o.label.startsWith('juror')) {
      live++; peak = Math.max(peak, live)
      await new Promise(r => setTimeout(r, 2)); live--
      return o.label.endsWith(':c') ? null : { score: 6, gaps: [`gap in ${o.label.split(':')[2]}`] }
    }
    if (o.label.startsWith('judge')) return { score: 8, gaps: [] }
    return { moved: true, reason: '' }
  })
  assert.equal(calls.filter(c => c.startsWith('juror-ant:1:')).length, 7)
  assert.ok(peak <= 5)
  assert.ok(prompts['juror-ant:1:b'].includes('/s/plans/r1/b.md'))
  const j = prompts['judge-ant:1']
  assert.ok(j.includes('- a: 6/10; gaps: gap in a'))
  assert.ok(j.includes('- c: no report'))
  assert.ok(j.includes('not an average'))
  assert.equal(out.verdict.score, 8)
})

// ---- logbook: one append per stage, through the tool ----
const logged = p => JSON.parse(p.split("<<'ISHIKARI_ROWS_END'\n")[1].split('\nISHIKARI_ROWS_END')[0])

test('build: the logbook clerk appends each task and each bug once', async () => {
  const prompts = {}
  await run('ishikari-build.js', { env, plans: [{ id: 'a', title: 'A' }] }, (p, o) => {
    prompts[o.label] = p
    if (o.label.startsWith('worker')) return { status: 'built', notes: 'n' }
    if (o.label === 'detective-ant:a:check') return { bugs: ['broken'], cause: 'c', plan: 'p' }
    if (o.label.startsWith('detective')) return { fixed: [{ id: 'a#1', fixed: false }], bugs: [] }
    return {}
  })
  const p = prompts['logbook-clerk']
  assert.ok(p.includes('python3 /t/ishikari.py log append /s'))
  assert.deepEqual(logged(p), [
    { run: 'r1', task: 'a', who: 'detective ant', event: 'bug escalated', detail: 'a#1: broken', tries: 3 },
    { run: 'r1', task: 'a', who: 'detective ant', event: 'escalated' },
  ])
})

test('finish: the logbook gets the tasks, the cleanup, the verdict and the main move', async () => {
  const { prompts } = await judgeRun([{ score: 5, gaps: ['g1'] }, { score: 6, gaps: ['g2'] }])
  const moved = logged(prompts['finisher-ant'])
  assert.deepEqual(moved.map(e => e.event), ['done', 'verdict flagged', 'main moved'])
  assert.equal(moved[1].score, 6)
  assert.equal(moved[1].detail, 'after one fix round (first score 5)\ng2')
  assert.ok(prompts['finisher-ant'].includes('log append /s'))
})

// ---- logbook: one entry the moment each ant finishes ----
test('finish: every ant gets its own logbook entry at once, the finisher excepted', async () => {
  const { out, instant } = await judgeRun([{ score: 4, gaps: ['g'] }, { score: 8, gaps: [] }])
  const got = instant.flatMap(p => logged(p))
  assert.deepEqual(got.map(e => `${e.who}: ${e.event}`), [
    'merger ant: merged 1 of 1', 'judge ant: score 4', 'worker ant: built',
    'detective ant: passed', 'merger ant: fast-forwarded', 'judge ant: score 8',
  ])
  assert.ok(got.every(e => e.run === 'r1'))
  assert.equal(out.mainMoved, true)
})

test('build: an ant entry names its task, and a dead ant is logged as died', async () => {
  const { instant } = await run('ishikari-build.js', { env, plans: [{ id: 'a', title: 'A' }] }, (p, o) =>
    o.label.startsWith('worker') ? null : {})
  const got = instant.flatMap(p => logged(p))
  assert.deepEqual(got.slice(0, 2), [{ run: 'r1', task: 'a', who: 'worker ant', event: 'died' }, { run: 'r1', task: 'a', who: 'worker ant', event: 'died' }])
})

// ---- plan: every planning ant writes the logbook ----
const onePlan = { designWritten: true, plans: [{ id: 'a', title: 'A', files: ['x'] }] }
const live = { testCommand: 'npm test', checkCommand: '' }

test('plan: every planning ant gets its own logbook entry at once', async () => {
  let settled = 0
  let n = 0
  const slowClerk = () => new Promise(r => setTimeout(() => { settled++; r({}) }, 5))
  const { out, instant } = await run('ishikari-plan.js', { env, task: 't' }, (p, o) => {
    if (o.label.startsWith('investigator')) return ++n === 1 ? { ...clear, reportWritten: false, research: ['a', 'b'] } : clear
    if (o.label.startsWith('researcher')) return { findings: 'f' }
    if (o.label === 'add-requirement-ant') return goodReq
    return onePlan
  }, slowClerk)
  assert.equal(out.stage, 'plans')
  const got = instant.flatMap(p => logged(p))
  assert.deepEqual(got.map(e => `${e.who}: ${e.event}`), [
    'investigator ant: research needed', 'researcher ant: found', 'researcher ant: found',
    'investigator ant: report written', 'add-requirement ant: requirement drafted', 'architect ant: 1 plan written',
  ])
  assert.ok(got.every(e => e.run === 'r1' && !('task' in e) && typeof e.detail === 'string' && e.detail.length <= 400))
  assert.ok(instant.every(p => p.includes('python3 /t/ishikari.py log append /s')))
  assert.equal(settled, instant.length)
  const { out: noTool } = await run('ishikari-plan.js', { env: { ...env, tool: '' }, task: 't' }, () => clear)
  assert.equal(noTool.stage, 'error')
  assert.match(noTool.reason, /env.tool/)
})

test('plan: a live investigation logs one investigated entry', async () => {
  const { out, instant } = await run('ishikari-plan.js', { env, task: 't', investigated: live }, (p, o) =>
    o.label === 'add-requirement-ant' ? goodReq : onePlan)
  const got = instant.flatMap(p => logged(p))
  assert.deepEqual(got[0], { run: 'r1', who: 'investigator ant', event: 'investigated', detail: '/s/plans/r1/investigation_report.md' })
  assert.equal(got.filter(e => e.who === 'investigator ant').length, 1)
  assert.equal(got.filter(e => e.who === 'researcher ant').length, 0)
  assert.deepEqual(got.map(e => e.who), ['investigator ant', 'add-requirement ant', 'architect ant'])
  assert.equal(out.stage, 'plans')
})

test('plan: a dead planning ant is logged as died and never blocks the run', async () => {
  let r = 0
  const { out, instant } = await run('ishikari-plan.js', { env, task: 't', investigated: live }, (p, o) =>
    o.label === 'add-requirement-ant' ? (++r === 1 ? null : goodReq) : onePlan,
  () => { throw new Error('logbook down') })
  assert.equal(out.stage, 'plans')
  const reqs = instant.flatMap(p => logged(p)).filter(e => e.who === 'add-requirement ant')
  assert.equal(reqs.length, 2)
  assert.deepEqual(reqs[0], { run: 'r1', who: 'add-requirement ant', event: 'died' })
  assert.equal(reqs[1].event, 'requirement drafted')

  let settled = 0
  const second = await run('ishikari-plan.js', { env, task: 't', investigated: live }, (p, o) =>
    o.label === 'add-requirement-ant' ? goodReq : null,
  () => new Promise(res => setTimeout(() => { settled++; res({}) }, 5)))
  assert.equal(second.out.stage, 'error')
  const arch = second.instant.flatMap(p => logged(p)).filter(e => e.who === 'architect ant')
  assert.deepEqual(arch.map(e => `${e.who}: ${e.event}`), ['architect ant: died', 'architect ant: died'])
  assert.equal(settled, second.instant.length)
})

// ---- speed: smaller plans, lighter plans, jury only for 3+ tasks ----
test('finish: two tasks, the judge still works alone; three get a jury', async () => {
  const go = ids => run('ishikari-finish.js', { env, approved: ids.map(T), cleanup: true }, (p, o) => {
    if (o.label === 'merger-ant') return { sha: 'abc', results: ids.map(id => ({ id, outcome: 'merged', detail: '' })) }
    if (o.label.startsWith('juror') || o.label.startsWith('judge')) return { score: 9, gaps: [] }
    return { moved: true, reason: '' }
  })
  assert.ok(!(await go(['a', 'b'])).calls.some(c => c.startsWith('juror')))
  assert.equal((await go(['a', 'b', 'c'])).calls.filter(c => c.startsWith('juror')).length, 3)
})

test('plan: the architect keeps plans small and says what and where, not exact words', async () => {
  const prompts = {}
  await run('ishikari-plan.js', { env, task: 't', investigated: { testCommand: 'npm test', checkCommand: '' } }, (p, o) => {
    prompts[o.label] = p
    return o.label === 'add-requirement-ant' ? goodReq : { designWritten: true, plans: [{ id: 'a', title: 'A', files: ['x'] }] }
  })
  const a = prompts['architect-ant']
  assert.ok(a.includes('at most about 3 files per task'))
  assert.ok(a.includes('what and where, not exact wording'))
})

// ---- every ant: latest Opus, low effort ----
test('every ant in all three scripts runs on opus at low effort', async () => {
  const seen = []
  const spy = (name, args, answer) => {
    const src = readFileSync(join(SCRIPTS, name), 'utf8').replace('export const meta', 'const meta')
    const agent = async (p, o) => { seen.push([name, o.label, o.model, o.effort]); return answer(p, o) }
    const parallel = fns => Promise.all(fns.map(f => f()))
    return new Function('args', 'agent', 'parallel', 'phase', 'log', 'workflow', `return (async () => {${src}})()`)(args, agent, parallel, () => {}, () => {}, async () => ({}))
  }
  await spy('ishikari-plan.js', { env, task: 't', investigated: { testCommand: 't', checkCommand: '' } }, (p, o) =>
    o.label === 'add-requirement-ant' ? goodReq : { designWritten: true, plans: [{ id: 'a', title: 'A', files: ['x'] }] })
  await spy('ishikari-build.js', { env, plans: [{ id: 'a', title: 'A' }] }, (p, o) =>
    o.label.startsWith('worker') ? { status: 'built', notes: '' } : o.label.startsWith('detective') ? { bugs: [] } : {})
  await spy('ishikari-finish.js', { env, approved: ['a', 'b', 'c'].map(T) }, (p, o) =>
    o.label === 'merger-ant' ? { sha: 'abc', results: ['a', 'b', 'c'].map(id => ({ id, outcome: 'merged', detail: '' })) }
      : o.label === 'janitor-ant' ? { changed: false, title: '', testsPassed: true, landed: false }
      : o.label.startsWith('juror') || o.label.startsWith('judge') ? { score: 9, gaps: [] } : { moved: true, reason: '' })
  for (const s of ['ishikari-plan.js', 'ishikari-build.js', 'ishikari-finish.js']) assert.ok(seen.some(x => x[0] === s), s)
  const off = seen.filter(([, , model, effort]) => model !== 'opus' || effort !== 'low')
  assert.deepEqual(off, [])
})

// ---- speed: janitor only for bigger changes; one logbook writer at a time ----
test('finish: the janitor is skipped under 100 changed lines, runs at 100, runs when lines are unknown', async () => {
  const go = lines => finishRun({ approved: [T('a')], cleanup: false }, o =>
    o.label === 'merger-ant' ? { sha: SHA, results: [{ id: 'a', outcome: 'merged', detail: '' }], landed: ['a'], missing: [], ...(lines == null ? {} : { lines }) }
      : o.label === 'janitor-ant' ? { changed: false, title: '', testsPassed: true, landed: false } : null)
  assert.ok(!(await go(99)).calls.includes('janitor-ant'))
  assert.ok((await go(100)).calls.includes('janitor-ant'))
  assert.ok((await go()).calls.includes('janitor-ant'))
  const { prompts } = await go(5)
  assert.ok(prompts['merger-ant'].includes('diff --shortstat main <sha>'))
})

test('logbook: one clerk at a time, later entries batched, none lost', async () => {
  let live = 0, peak = 0
  const slow = () => { live++; peak = Math.max(peak, live); return new Promise(r => setTimeout(() => { live--; r({}) }, 5)) }
  const ids = ['a', 'b', 'c', 'd']
  const { instant } = await run('ishikari-finish.js', { env, approved: ids.map(T), cleanup: true }, async (p, o) =>
    o.label === 'merger-ant' ? { sha: SHA, results: ids.map(id => ({ id, outcome: 'merged', detail: '' })), landed: ids, missing: [] }
      : o.label.startsWith('juror') || o.label.startsWith('judge') ? { score: 9, gaps: [] } : { moved: true, reason: '' }, slow)
  assert.equal(peak, 1)
  const entries = instant.flatMap(p => logged(p))
  assert.equal(entries.filter(e => e.who === 'juror ant').length, 4)
  assert.ok(instant.length < entries.length)  // the jurors' entries were batched
})

// ---- one detective: it checks, and plans every fix ----
test('build: the detective checks and plans each fix itself, with the history, no other ant', async () => {
  let k = 0
  const prompts = {}
  const { out, calls } = await run('ishikari-build.js', { env, plans: [{ id: 'a', title: 'A' }] }, (p, o) => {
    prompts[o.label] = p
    if (o.label.startsWith('worker')) return { status: 'built', notes: 'n' }
    if (o.label === 'detective-ant:a:check') return { bugs: ['broken'], cause: 'c1', plan: 'plan one' }
    return ++k === 1 ? { fixed: [{ id: 'a#1', fixed: false }], bugs: [], cause: 'c2', plan: 'plan two' }
      : { fixed: [{ id: 'a#1', fixed: true }], bugs: [] }
  })
  assert.equal(out.tasks[0].status, 'awaiting review')
  assert.ok(!calls.some(c => c.startsWith('inspector')))
  assert.deepEqual(calls.filter(c => c.startsWith('detective')), ['detective-ant:a:check', 'detective-ant:a:recheck1', 'detective-ant:a:recheck2'])
  assert.ok(prompts['worker-ant:a:fix1'].includes('plan one'))
  assert.ok(prompts['worker-ant:a:fix2'].includes('plan two'))
  assert.ok(prompts['detective-ant:a:recheck2'].includes('fix plan: plan one'))
  assert.ok(prompts['detective-ant:a:recheck2'].includes('Do not repeat a cause or plan that already failed'))
})

test('build: a re-check with no plan still gives the worker the open bugs', async () => {
  const prompts = {}
  await run('ishikari-build.js', { env, plans: [{ id: 'a', title: 'A' }] }, (p, o) => {
    prompts[o.label] = p
    if (o.label.startsWith('worker')) return { status: 'built', notes: 'n' }
    if (o.label === 'detective-ant:a:check') return { bugs: ['broken'], cause: 'c', plan: 'p' }
    return { fixed: [{ id: 'a#1', fixed: false }], bugs: [] }
  })
  assert.ok(prompts['worker-ant:a:fix2'].includes('Fix these bugs:\n- a#1: broken'))
})
