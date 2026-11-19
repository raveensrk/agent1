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

// The plan stage only checks the investigator's plan list: no ant plans there.
const PLAN = { id: 'a', title: 'A', files: ['x'], covers: ['B1'] }
function planWith(plans, more = {}) {
  return run('ishikari-plan.js', { env, task: 't', ids: ['B1'], plans, testCommand: 'npm test', checkCommand: '', ...more }, () => { throw new Error('the plan stage runs no ant') })
}

test('plan: a good plan list passes, with each plan file and the commands', async () => {
  const { out, calls } = await planWith([PLAN, { id: 'b', title: 'B', files: ['x', 'y'], covers: ['I1', 'B1'], after: ['a'], workflow: 'saved' }], { ids: ['B1', 'I1'] })
  assert.equal(out.stage, 'plans')
  assert.equal(calls.length, 0)  // no planning ant: the investigator planned
  assert.equal(out.productSpec, '/s/plans/r1/product_spec.md')
  assert.equal(out.techSpec, '/s/plans/r1/tech_spec.md')
  assert.deepEqual(out.ids, ['B1', 'I1'])
  assert.deepEqual(out.plans[1], { id: 'b', title: 'B', files: ['x', 'y'], covers: ['I1', 'B1'], after: ['a'], workflow: 'saved', file: '/s/plans/r1/b.md' })
  assert.equal(out.testCommand, 'npm test')
  const solo = await planWith([PLAN])  // one worker: no plan file, it builds from the specs
  assert.equal(solo.out.stage, 'plans')
  assert.equal(solo.out.plans[0].file, null)
})

test('plan: plans that would clash or leave the repo come back as problems, never as an error or a pass', async () => {
  const problems = async plans => { const { out } = await planWith(plans); assert.equal(out.stage, 'problems', JSON.stringify(plans)); return out.problems.join(' | ') }
  assert.match(await problems([PLAN, { ...PLAN, id: 'b' }]), /both edit x but neither is after the other/)
  assert.match(await problems([{ ...PLAN, files: ['./x'] }, { ...PLAN, id: 'b' }]), /both edit x/)  // "./x" and "x" are one file
  assert.match(await problems([{ ...PLAN, after: ['b'] }, { ...PLAN, id: 'b', files: ['y'], after: ['a'] }]), /loop in after/)
  assert.match(await problems([{ ...PLAN, after: ['zz'] }]), /unknown plan/)
  assert.match(await problems([{ ...PLAN, after: ['a'] }]), /after names itself/)
  assert.match(await problems([{ ...PLAN, after: 'b' }]), /after must be a list/)
  assert.match(await problems([PLAN, PLAN]), /two plans have the id/)
  assert.match(await problems([{ ...PLAN, id: 'Bad Id' }]), /bad id/)
  assert.match(await problems([{ ...PLAN, workflow: 5 }]), /workflow must be a name/)
  for (const files of [['/etc/passwd'], ['../x'], ['a/../../x'], ['./'], []]) assert.match(await problems([{ ...PLAN, files }]), /inside the repo|lists no files/)
  assert.match(await problems([]), /there are no plans/)
  assert.match(await problems([PLAN, 'junk']), /every plan must be an object/)
})

test('plan: every behaviour and invariant needs a worker, and no plan may claim an unknown one', async () => {
  const problems = async (plans, ids) => { const { out } = await planWith(plans, { ids }); assert.equal(out.stage, 'problems', JSON.stringify([plans, ids])); return out.problems.join(' | ') }
  assert.match(await problems([PLAN], ['B1', 'B2', 'I1']), /no plan covers B2, I1/)
  assert.match(await problems([{ ...PLAN, covers: ['B1', 'B9'] }], ['B1']), /covers "B9", which is not in the product spec/)
  assert.match(await problems([{ ...PLAN, covers: [] }], ['B1']), /covers no behaviour or invariant/)
  assert.match(await problems([{ id: 'a', title: 'A', files: ['x'] }], ['B1']), /covers no behaviour or invariant/)
  assert.match(await problems([PLAN], []), /lists no behaviour or invariant ids/)
  assert.match(await problems([PLAN], ['B1', 'behaviour 2']), /bad spec id/)
  assert.match(await problems([PLAN], ['B1', 'B1']), /lists an id twice/)
  const { out } = await planWith([{ ...PLAN, covers: ['I1'] }], { ids: ['I1'] })  // a refactor: invariants only
  assert.equal(out.stage, 'plans')
  assert.equal((await run('ishikari-plan.js', { env, task: 't', plans: [PLAN] }, () => ({}))).out.stage, 'error')  // no ids at all
})

test('plan: bad arguments are an error', async () => {
  for (const more of [{ task: '   ' }, { task: { a: 1 } }, { plans: 'a' }, { plans: undefined }, { ids: 'B1' }, { testCommand: 'make\ntest' }, { checkCommand: 'echo `id`' }]) {
    const { out } = await run('ishikari-plan.js', { env, task: 't', ids: ['B1'], plans: [PLAN], ...more }, () => ({}))
    assert.equal(out.stage, 'error', JSON.stringify(more))
  }
})

test('plan: the investigator gets its one logbook entry, the escalation is logged, and a recheck logs neither twice', async () => {
  const first = await planWith([PLAN], { escalated: 'touches 6 files' })
  assert.deepEqual(first.instant.flatMap(p => logged(p)).map(e => `${e.who}: ${e.event}`),
    ['investigator ant: investigated', 'main session: fast path escalated', 'plan script: 1 plan checked'])
  assert.equal(first.instant.flatMap(p => logged(p))[0].detail, '/s/plans/r1/product_spec.md')
  const refused = await planWith([{ ...PLAN, id: 'A' }], { recheck: true })
  assert.deepEqual(refused.instant.flatMap(p => logged(p)).map(e => `${e.who}: ${e.event}`), ['plan script: plans refused'])
  const lost = await run('ishikari-plan.js', { env, task: 't', ids: ['B1'], plans: [PLAN] }, () => ({}), () => { throw new Error('logbook down') })
  assert.equal(lost.out.stage, 'plans')  // a dead clerk never blocks the stage
  assert.equal(lost.out.logLost.length, 2)
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
async function buildPrompts(args, worker, detective = () => ({ bugs: [] })) {
  const prompts = {}
  await run('ishikari-build.js', { env, ...args }, (p, o) => {
    prompts[o.label] = p
    if (o.label.startsWith('worker')) return { status: 'built', notes: 'n', ...worker(o.label) }
    return detective(o.label)
  })
  return prompts
}

test('build: no valid worker sha means the detective runs the tests itself', async () => {
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

test('build: the detective gets the worker sha and reuses its test result', async () => {
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
    if (o.label === 'merger-ant') return { sha: 'abc1234', results: [{ id: 'a', outcome: 'merged', detail: '' }] }
    if (o.label.startsWith('judge-ant')) return { score: 9, gaps: [] }
    return { moved: true, reason: '' }
  })
  assert.equal(out.mainMoved, true)
  const fin = prompts.find(p => p.includes("finisher ant"))
  assert.ok(fin.includes('   - ishikari/r1/a'))
  assert.ok(!fin.includes('   - ishikari/r1/b'))
})

const NO_DOCS = { changed: false, title: '', testsPassed: true, landed: false, files: [] }
function finishWith(jan) {
  const prompts = {}
  return run('ishikari-finish.js', { env, approved: [{ id: 'a', branch: 'ishikari/r1/a' }] }, (p, o) => {
    prompts[o.label] = p
    if (o.label === 'merger-ant') return { sha: 'abc1234', results: [{ id: 'a', outcome: 'merged', detail: '' }] }
    if (o.label === 'janitor-ant') return jan
    if (o.label === 'docs-ant') return NO_DOCS
    if (o.label === 'merger-ant:rewind') return { sha: 'abc1234' }
    if (o.label.startsWith('judge-ant')) return { score: 9, gaps: [] }
    return { moved: true, reason: '' }
  }).then(r => ({ ...r, prompts, fin: prompts['finisher-ant'] }))
}

test('finish: the janitor cleans, tests, commits and lands its cleanup alone, judge after it', async () => {
  const { out, calls, fin, prompts } = await finishWith({ changed: true, title: 'tidy', testsPassed: true, landed: true, sha: 'def0123' })
  assert.deepEqual(out.cleanup, { title: 'tidy', landed: true })
  assert.equal(out.sha, 'def0123')
  assert.deepEqual(calls.slice(1, 4), ['janitor-ant', 'judge-ant:1', 'docs-ant'])
  assert.ok(!calls.some(c => c.includes('cleanup')))  // no worker, detective or merger for it
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
  assert.equal(out.sha, 'abc1234')
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
    if (o.label === 'merger-ant') return { sha: 'abc1234', results: [{ id: 'a', outcome: 'merged', detail: '' }] }
    if (o.label.startsWith('judge-ant')) return scores[k++]
    if (o.label === 'docs-ant') return answer(o) || NO_DOCS
    if (o.label === 'merger-ant:rewind') return answer(o) || { sha: 'abc1234' }
    return answer(o) || (o.label.startsWith('worker') ? { status: 'built', notes: '' }
      : o.label.startsWith('detective') ? { bugs: [] }
      : o.label === 'merger-ant:judge-fix' ? { ok: true, sha: 'fff1234' } : { moved: true, reason: '' })
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
  assert.equal(out.sha, 'fff1234')
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


// ---- finish: judge after cleanup, trial-merge reuse, verified merges, check-fix cap ----
const SHA = 'aaaaaaa', TOG = 'bbbbbbb'
const T = id => ({ id, branch: `ishikari/r1/${id}` })
function finishRun(args, answer) {
  const prompts = {}
  return run('ishikari-finish.js', { env, cleanup: true, ...args }, (p, o) => {
    prompts[o.label] = p
    return answer(o, p) || (o.label.startsWith('judge-ant') ? { score: 9, gaps: [] } : o.label === 'docs-ant' ? NO_DOCS : o.label === 'merger-ant:rewind' ? { sha: SHA } : { moved: true, reason: '' })
  }).then(r => ({ ...r, prompts }))
}

test('finish: the judge starts only after the janitor ends', async () => {
  let janitorDone = false
  const { out } = await run('ishikari-finish.js', { env, approved: [T('a')] }, async (p, o) => {
    if (o.label === 'merger-ant') return { sha: 'abc1234', results: [{ id: 'a', outcome: 'merged', detail: '' }] }
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
  const failing = o => o.label === 'merger-ant' ? { sha: 'abc1234', results: [{ id: 'a', outcome: 'merged', detail: '' }] }
    : o.label === 'finisher-ant' ? { moved: true, reason: '', check: { ran: true, ok: false, output: 'boom' } } : null
  let { out } = await finishRun({ approved: [T('a')], env: { ...env, checkCommand: 'make' } }, failing)
  assert.deepEqual(out.checkFix, { task: 'check-fix', bug: 'boom' })
  assert.equal(out.checkFixDone, false)
  ;({ out } = await finishRun({ approved: [T('a')], checkFixDone: true, env: { ...env, checkCommand: 'make' } }, failing))
  assert.equal(out.checkFix, null)
  assert.equal(out.checkFixRefused, true)
  assert.equal(out.checkFixDone, true)
  ;({ out } = await finishRun({ approved: [T('check-fix')], env: { ...env, checkCommand: 'make' } }, o =>
    o.label === 'merger-ant' ? { sha: 'abc1234', results: [{ id: 'check-fix', outcome: 'merged', detail: '' }] } : failing(o)))
  assert.equal(out.checkFix, null)
  ;({ out } = await finishRun({ approved: [T('a')], checkFixDone: 'yes' }, failing))
  assert.equal(out.stage, 'error')
})

// ---- judge round 1: judge after the ff, tip checks, git cherry strictness ----
// ---- finish: the docs ant runs last and nothing unchecked reaches main ----
const DOCS_OK = { changed: true, title: 'docs', testsPassed: true, landed: true, files: ['docs/02-arch.md', 'README.md'], sha: 'd0c0123' }
function docsRun(d, extra = {}, more = () => null) {
  const prompts = {}
  return run('ishikari-finish.js', { env, approved: [T('a')], ...extra }, (p, o) => {
    prompts[o.label] = p
    return more(o) || (o.label === 'merger-ant' ? { sha: 'abc1234', results: [{ id: 'a', outcome: 'merged', detail: '' }] }
      : o.label === 'docs-ant' ? d
      : o.label === 'janitor-ant' ? { changed: false, title: '', testsPassed: true, landed: false }
      : o.label === 'merger-ant:rewind' ? { sha: 'abc1234' }
      : o.label.startsWith('judge-ant') ? { score: 9, gaps: [] } : { moved: true, reason: '' })
  }).then(r => ({ ...r, prompts }))
}

test('finish: the docs ant runs last, after the judge, and lands only when its checks pass', async () => {
  const ok = await docsRun(DOCS_OK)
  assert.ok(ok.calls.indexOf('docs-ant') > ok.calls.indexOf('judge-ant:1'))
  assert.ok(ok.calls.indexOf('judge-ant:1') > ok.calls.indexOf('janitor-ant'))
  assert.deepEqual(ok.out.docs, { title: 'docs', landed: true })
  assert.equal(ok.out.sha, 'd0c0123')
  assert.ok(!ok.calls.includes('merger-ant:rewind'))
  assert.ok(ok.prompts['finisher-ant'].includes('   - ishikari/r1/_docs'))
  const p = ok.prompts['docs-ant']
  assert.ok(p.includes('Skip the docs-only') && p.includes('doc/build.sh') && p.includes('never code'))
})

test('finish: a docs update that is not accepted is put back, its branch kept, and main moves without it', async () => {
  for (const d of [
    { ...DOCS_OK, testsPassed: false },            // said landed, checks failed
    { ...DOCS_OK, sha: undefined },                // said landed, no commit
    { ...DOCS_OK, files: ['docs/a.md', 'src/app.py'] },  // touched code
    { ...DOCS_OK, files: ['../x.md'] },
    { ...DOCS_OK, files: [] },
    null,                                          // died
  ]) {
    const { out, calls, prompts } = await docsRun(d)
    assert.equal(out.docs.landed, false, JSON.stringify(d))
    assert.equal(out.docs.branch, 'ishikari/r1/_docs')
    assert.ok(calls.includes('merger-ant:rewind'), JSON.stringify(d))
    assert.ok(prompts['merger-ant:rewind'].includes('reset --hard abc1234'))
    assert.equal(out.sha, 'abc1234')
    assert.equal(out.mainMoved, true)
    assert.ok(!prompts['finisher-ant'].includes('   - ishikari/r1/_docs'))  // kept, not removed
  }
  const code = await docsRun({ ...DOCS_OK, files: ['src/app.py'] })
  assert.match(code.out.docs.reason, /not docs: src\/app\.py/)
})

test('finish: main moves to the checked commit, never to a branch name, and a retry sees it already moved', async () => {
  const { prompts } = await docsRun(DOCS_OK)
  const f = prompts['finisher-ant']
  assert.ok(f.includes('merge --ff-only d0c0123') && f.includes('branch -f main d0c0123'))
  assert.ok(!f.includes('merge --ff-only ishikari/r1/_finish'))
  assert.ok(f.indexOf('merge-base --is-ancestor d0c0123 main') < f.indexOf('merge --ff-only d0c0123'))
  assert.ok(f.includes('count it as moved'))
})

test('finish: a rejected cleanup is put back before the judge reads, and a failed put-back stops upkeep', async () => {
  const bad = { changed: true, title: 'tidy', testsPassed: false, landed: true, sha: 'bad1234' }
  const a = await docsRun(NO_DOCS, {}, o => o.label === 'janitor-ant' ? bad : null)
  assert.ok(a.calls.indexOf('merger-ant:rewind') < a.calls.indexOf('judge-ant:1'))
  assert.equal(a.out.cleanup.landed, false)
  assert.equal(a.out.sha, 'abc1234')
  assert.ok(a.prompts['finisher-ant'].includes('merge --ff-only abc1234'))
  const b = await docsRun(DOCS_OK, {}, o => o.label === 'janitor-ant' ? bad : o.label === 'merger-ant:rewind' ? { sha: 'bad1234' } : null)
  assert.match(b.out.upkeepStopped, /could not be put back to abc1234/)
  assert.ok(!b.calls.some(c => c.startsWith('judge-ant')) && !b.calls.includes('docs-ant'))
  assert.equal(b.out.sha, 'abc1234')
  assert.equal(b.out.mainMoved, true)
})

test('finish: a later round uses its own upkeep branches and counts earlier landed tasks as in main', async () => {
  const { prompts } = await docsRun(DOCS_OK, { round: 2, landed: ['z', 'bad id'], approved: [{ ...T('a'), after: ['z'] }] })
  assert.ok(prompts['docs-ant'].includes('ishikari/r1/_docs-2'))
  assert.ok(prompts['janitor-ant'].includes('ishikari/r1/_cleanup-2') && prompts['janitor-ant'].includes('cleanup-2.md'))
  const fin = prompts['finisher-ant']
  assert.ok(!/ishikari\/r1\/_(docs|cleanup|judgefix)\n/.test(fin))  // round 1's branches are left alone
  const m = prompts['merger-ant']
  assert.ok(m.includes('its id is one of z (an earlier finish') && !m.includes('bad id'))
  assert.ok(m.includes('cherry main <its branch>') && !m.includes('--is-ancestor <its branch>'))
  for (const args of [{ round: 0 }, { round: 'x' }, { landed: 'a' }]) {
    const { out } = await docsRun(DOCS_OK, args)
    assert.equal(out.stage, 'error', JSON.stringify(args))
  }
})

test('finish: scratch branches are refused as tasks, and merged tasks need a commit', async () => {
  const a = await docsRun(DOCS_OK, { approved: [{ id: 'x', branch: 'ishikari/r1/_together' }] })
  assert.equal(a.out.stage, 'error')
  const b = await docsRun(DOCS_OK, {}, o => o.label === 'merger-ant' ? { sha: 'nope', results: [{ id: 'a', outcome: 'merged', detail: '' }] } : null)
  assert.equal(b.out.stage, 'error')
  assert.match(b.out.reason, /gave no commit/)
  assert.ok(!b.calls.includes('finisher-ant'))
})

test('finish: the judge fix is rebuilt from the checked commit and a bad fast-forward is put back', async () => {
  const { out, calls, prompts } = await judgeRun([{ score: 4, gaps: ['g'] }], o => o.label === 'merger-ant:judge-fix' ? { ok: true, sha: '' } : null)
  assert.ok(prompts['worker-ant:judge-fix'].includes('If either exists, remove'))
  assert.ok(prompts['worker-ant:judge-fix'].includes('ishikari/r1/_judgefix /s/worktrees/ishikari__r1___judgefix abc1234'))
  assert.ok(calls.includes('merger-ant:rewind'))
  assert.equal(out.verdict.fixed, false)
  assert.equal(out.sha, 'abc1234')
})

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
    assert.ok(m.includes(`cherry ${TOG} <branch>`) && !m.includes(`--is-ancestor <branch>`))
    assert.ok(/If any (ancestor )?check or the worktree add fails, do the normal steps/.test(m))
  }
})

test('finish: a stale branch tip leads the merger to the full merge, and git is still asked', async () => {
  const { out, calls } = await finishRun({ approved: [T('a'), T('b')], together: { sha: TOG, tasks: ['a', 'b'] } }, o =>
    o.label === 'merger-ant' ? { sha: SHA, fastPath: false, results: [{ id: 'a', outcome: 'merged', detail: '' }, { id: 'b', outcome: 'merged', detail: '' }], landed: ['a', 'b'], missing: [] } : null)
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
    if (o.label === 'merger-ant') return { sha: 'abc1234', results: ids.map(id => ({ id, outcome: 'merged', detail: '' })) }
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
function logged(p) { return JSON.parse(p.split("<<'ISHIKARI_ROWS_END'\n")[1].split('\nISHIKARI_ROWS_END')[0]) }

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
    'detective ant: passed', 'merger ant: fast-forwarded', 'judge ant: score 8', 'docs ant: nothing changed',
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





// ---- speed: smaller plans, lighter plans, jury only for 3+ tasks ----
test('finish: two tasks, the judge still works alone; three get a jury', async () => {
  const go = ids => run('ishikari-finish.js', { env, approved: ids.map(T), cleanup: true }, (p, o) => {
    if (o.label === 'merger-ant') return { sha: 'abc1234', results: ids.map(id => ({ id, outcome: 'merged', detail: '' })) }
    if (o.label.startsWith('juror') || o.label.startsWith('judge')) return { score: 9, gaps: [] }
    return { moved: true, reason: '' }
  })
  assert.ok(!(await go(['a', 'b'])).calls.some(c => c.startsWith('juror')))
  assert.equal((await go(['a', 'b', 'c'])).calls.filter(c => c.startsWith('juror')).length, 3)
})


// ---- every ant: latest Opus, low effort ----
test('every workflow ant in all four scripts runs on opus at low effort', async () => {
  const seen = []
  const spy = (name, args, answer) => {
    const src = readFileSync(join(SCRIPTS, name), 'utf8').replace('export const meta', 'const meta')
    const agent = async (p, o) => { seen.push([name, o.label, o.model, o.effort]); return answer(p, o) }
    const parallel = fns => Promise.all(fns.map(f => f()))
    return new Function('args', 'agent', 'parallel', 'phase', 'log', 'workflow', `return (async () => {${src}})()`)(args, agent, parallel, () => {}, () => {}, async () => ({}))
  }
  await spy('ishikari-plan.js', { env, task: 't', ids: ['B1'], plans: [PLAN] }, () => ({}))
  await spy('ishikari-build.js', { env, plans: [{ id: 'a', title: 'A' }] }, (p, o) =>
    o.label.startsWith('worker') ? { status: 'built', notes: '' } : o.label.startsWith('detective') ? { bugs: [] } : {})
  await spy('ishikari-finish.js', { env, approved: ['a', 'b', 'c'].map(T) }, (p, o) =>
    o.label === 'merger-ant' ? { sha: 'abc1234', results: ['a', 'b', 'c'].map(id => ({ id, outcome: 'merged', detail: '' })) }
      : o.label === 'janitor-ant' ? { changed: false, title: '', testsPassed: true, landed: false }
      : o.label === 'docs-ant' ? { changed: true, title: 'd', testsPassed: false, landed: false, files: [] }
      : o.label.startsWith('juror') || o.label.startsWith('judge') ? { score: 9, gaps: [] } : { moved: true, reason: '' })
  await spy('ishikari-retro.js', { env }, () => null)
  for (const s of ['ishikari-plan.js', 'ishikari-build.js', 'ishikari-finish.js', 'ishikari-retro.js']) assert.ok(seen.some(x => x[0] === s), s)
  for (const label of ['docs-ant', 'merger-ant:rewind', 'retrospective-ant', 'juror-ant:1:a', 'logbook-clerk:now']) assert.ok(seen.some(x => x[1] === label), label)
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

// ---- fast path: a trivial task skips the plan, and an escalation reaches the planners ----



// ---- retrospective: one read-only ant at the very end ----
test('retro: one read-only ant writes only retrospective.md and returns ranked findings', async () => {
  const prompts = {}
  const f = { category: 'inefficiency', title: 't', evidence: 'e', impact: 'i', change: 'c', where: 'scripts/ishikari-build.js MAX_TRIES' }
  const { out, calls, instant } = await run('ishikari-retro.js', { env: { ...env, tool: '/k/scripts/ishikari.py' }, outcome: 'main moved' }, (p, o) => {
    prompts[o.label] = p
    assert.equal(o.model, 'opus')
    assert.equal(o.effort, 'low')
    return { written: true, lines: 12, before: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  -', after: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  -', summary: 's', findings: [f, { ...f, category: 'nonsense' }] }
  })
  assert.deepEqual(calls, ['retrospective-ant'])
  assert.equal(out.stage, 'retro')
  assert.equal(out.file, '/s/plans/r1/retrospective.md')
  assert.deepEqual(out.findings[0], f)
  assert.equal(out.findings[1].category, 'improvement')
  const p = prompts['retrospective-ant']
  assert.ok(p.includes('Read only') && p.includes('Your one write is /s/plans/r1/retrospective.md'))
  assert.ok(p.includes('main moved') && p.includes('/k/SKILL.md') && p.includes("Run: r1"))
  assert.deepEqual(logged(instant[0])[0].event, '2 findings')
})

test('retro: a dead or shapeless retrospective ant is an error, never a silent pass', async () => {
  const dead = await run('ishikari-retro.js', { env }, () => null)
  assert.equal(dead.out.stage, 'error')
  assert.equal(dead.calls.length, 2)  // retried once
  const R = { written: true, lines: 3, before: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  -', after: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  -', summary: '', findings: [] }
  assert.equal((await run('ishikari-retro.js', { env }, () => R)).out.stage, 'retro')
  for (const bad of [{ written: false }, { lines: 0 }, { findings: 'none' }, { after: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' }, { before: '', after: '' }]) {
    const { out } = await run('ishikari-retro.js', { env }, () => ({ ...R, ...bad }))
    assert.equal(out.stage, 'error', JSON.stringify(bad))
  }
  const changed = await run('ishikari-retro.js', { env }, () => ({ ...R, after: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' }))
  assert.match(changed.out.reason, /was to change nothing/)
  const thrown = await run('ishikari-retro.js', { env }, () => { throw new Error('down') }, () => { throw new Error('clerk down') })
  assert.equal(thrown.out.stage, 'error')
  assert.equal(thrown.out.logLost.length, 1)
  const badEnv = await run('ishikari-retro.js', { env: { ...env, repo: 'r' } }, () => ({}))
  assert.equal(badEnv.out.stage, 'error')
  assert.equal(badEnv.calls.length, 0)
})

// ---- build hardening: no lost results, no stale bases, nothing trusted blindly ----
const W = { status: 'built', notes: 'n' }
const buildWith = (args, answer, clerk) => run('ishikari-build.js', { env, ...args }, (p, o) =>
  answer(o, p) ?? (o.label.startsWith('worker') ? W : o.label.startsWith('detective') ? { bugs: [] } : {}), clerk)

test('build: an ant call that throws is a dead ant, never a lost stage', async () => {
  let n = 0
  const { out } = await run('ishikari-build.js', { env, plans: [{ id: 'a' }, { id: 'b' }] }, (p, o) => {
    if (o.label.startsWith('integrator')) throw new Error('runtime down')
    if (o.label === 'worker-ant:a:build' && ++n === 1) throw new Error('boom')
    return o.label.startsWith('worker') ? W : { bugs: [] }
  }, () => { throw new Error('clerk down') })
  assert.equal(out.stage, 'build')
  assert.deepEqual(out.tasks.map(t => t.status), ['awaiting review', 'awaiting review'])
  assert.equal(out.together, null)
})

test('build: replies of the wrong shape count as dead ants, not silent passes', async () => {
  for (const [who, reply] of [['worker', {}], ['worker', { status: 'done', notes: '' }], ['detective', {}], ['detective', { bugs: 'none' }], ['detective', { bugs: [], nits: 'x' }]]) {
    const { out, calls } = await buildWith({ plans: [{ id: 'a' }] }, o => o.label.startsWith(who) ? reply : undefined)
    assert.equal(out.tasks[0].status, 'error', JSON.stringify(reply))
    assert.equal(calls.filter(c => c.startsWith(who)).length, 2)  // retried once
  }
  const { out } = await buildWith({ plans: [{ id: 'a' }, { id: 'b' }] }, o =>
    o.label.startsWith('integrator') ? { sha: 'abc1234', results: [{ id: 'a', outcome: 'conflict', detail: 'd', with: 'b' }] } : undefined)
  assert.equal(out.together, null)
  assert.deepEqual(out.tasks.map(t => t.status), ['awaiting review', 'awaiting review'])
})

test('build: a branch with no commit of its own is a bug', async () => {
  const { out, calls } = await buildWith({ plans: [{ id: 'a' }] }, o =>
    o.label === 'detective-ant:a:check' ? { bugs: [], ownCommits: 0 }
      : o.label.startsWith('detective') ? { fixed: [{ id: 'a#1', fixed: true }], bugs: [] } : undefined)
  assert.ok(calls.includes('worker-ant:a:fix1'))
  assert.equal(out.tasks[0].status, 'awaiting review')
  assert.match(out.tasks[0].history[0].bugs[0], /no commit of its own/)
})

test('build: a first build that was stuck still gets the full check', async () => {
  const { out, calls } = await buildWith({ plans: [{ id: 'a' }] }, o =>
    o.label === 'worker-ant:a:build' ? { status: 'stuck', notes: 'no idea' }
      : o.label === 'detective-ant:a:recheck1' ? { fixed: [{ id: 'a#1', fixed: true }], bugs: [] } : undefined)
  assert.ok(calls.indexOf('detective-ant:a:check') > calls.indexOf('detective-ant:a:recheck1'))
  assert.equal(out.tasks[0].status, 'awaiting review')
})

test('build: a saved workflow that fails or returns nothing is stuck, and is logged', async () => {
  const src = readFileSync(join(SCRIPTS, 'ishikari-build.js'), 'utf8').replace('export const meta', 'const meta')
  for (const result of [null, { stage: 'error', reason: 'x' }]) {
    const calls = [], logs = []
    const agent = async (p, o) => {
      if (o.label === 'logbook-clerk:now') { logs.push(p); return {} }
      calls.push(o.label)
      return o.label.startsWith('worker') ? W : o.label.endsWith('recheck1') ? { fixed: [{ id: 'a#1', fixed: true }], bugs: [] } : { bugs: [] }
    }
    const body = new Function('args', 'agent', 'parallel', 'phase', 'log', 'workflow', `return (async () => {${src}})()`)
    const out = await body({ env, plans: [{ id: 'a', workflow: 'saved' }] }, agent, fns => Promise.all(fns.map(f => f())), () => {}, () => {}, async () => result)
    assert.ok(calls.includes('worker-ant:a:fix1'), JSON.stringify(result))  // stuck: the fix loop took over
    assert.ok(logs.some(p => p.includes('workflow stuck')))
    assert.equal(out.tasks[0].status, 'awaiting review')
  }
})

test('build: bad plans and bugs are refused, each with its reason', async () => {
  const none = await buildWith({}, () => undefined)
  assert.equal(none.out.stage, 'error')
  const reason = async args => (await buildWith(args, () => undefined)).out.tasks.map(t => t.bugs[0]).join(' | ')
  assert.match(await reason({ plans: [{ id: 'a', after: 'b' }] }), /after must be a list/)
  assert.match(await reason({ plans: [{ id: 'a', workflow: 7 }] }), /workflow must be a name/)
  assert.match(await reason({ bugs: [{ task: 'a', branch: 'ishikari/r1/a' }] }), /has no text/)
  assert.match(await reason({ bugs: [{ task: 'x', branch: 'ishikari/r1/_together', bug: 'b' }] }), /does not match|bad branch/)
  assert.match(await reason({ bugs: [{ branch: 'ishikari/r1/_together', bug: 'b' }] }), /bad task id|bad branch/)
  assert.match(await reason({ bugs: [{ task: 'b', branch: 'ishikari/r1/a', bug: 'b' }] }), /does not match its branch/)
  assert.match(await reason({ bugs: [{ branch: 'ishikari/r1/a', bug: 'b' }, { branch: 'ishikari/r0/a', bug: 'b' }] }), /two bug tasks have the id/)
  assert.match(await reason({ plans: [{ id: 'a' }], bugs: [{ branch: 'ishikari/r0/a', bug: 'b' }] }), /both a new plan and an open bug/)
  assert.match(await reason({ bugs: [{ branch: 'ishikari/r1/a', bug: 'x', after: ['b'] }, { branch: 'ishikari/r1/b', bug: 'y', after: ['a'] }] }), /loop in after/)
})

test('build: a bug task built on another bug task waits for it, builds on it, and is blocked when it fails', async () => {
  const bugs = [{ branch: 'ishikari/r1/b', bug: 'y', after: ['a', 'gone'], history: [{ round: 1, bugs: ['old'], cause: 'c', plan: 'p' }, 'junk'] }, { branch: 'ishikari/r1/a', bug: 'x' }]
  const prompts = {}
  const ok = await buildWith({ bugs }, (o, p) => {
    prompts[o.label] = p
    return o.label.startsWith('detective') ? { fixed: [{ id: `${o.label.split(':')[1]}#1`, fixed: true }], bugs: [] } : undefined
  })
  assert.ok(ok.calls.indexOf('worker-ant:b:fix2') > ok.calls.indexOf('detective-ant:a:recheck1'))  // b waits; its history runs on
  assert.ok(prompts['worker-ant:b:fix2'].includes('Merge the latest ishikari/r1/a into your branch'))
  assert.ok(prompts['detective-ant:b:recheck2'].includes('It is built on ishikari/r1/a'))
  assert.deepEqual(ok.out.tasks.map(t => t.status), ['awaiting review', 'awaiting review'])
  const bad = await buildWith({ bugs }, o => o.label.startsWith('detective-ant:a') ? { fixed: [{ id: 'a#1', fixed: false }], bugs: [] } : undefined)
  assert.equal(bad.out.tasks.find(t => t.id === 'b').status, 'blocked')
  assert.ok(!bad.calls.some(c => c.startsWith('worker-ant:b')))
})

test('build: clash fixes run one at a time, and tasks built on a fixed task take it in and are checked again', async () => {
  let round = 0, busy = 0, peak = 0
  const plans = [{ id: 'a' }, { id: 'b' }, { id: 'c', after: ['b'] }]
  const run1 = await run('ishikari-build.js', { env, plans }, async (p, o) => {
    if (o.label.startsWith('integrator')) {
      return ++round === 1
        ? { sha: 'abc1234', results: [{ id: 'a', outcome: 'conflict', detail: 'd', with: [] }, { id: 'b', outcome: 'conflict', detail: 'd', with: ['a'] }, { id: 'c', outcome: 'merged', detail: '' }] }
        : { sha: 'abc1234', results: plans.map(x => ({ id: x.id, outcome: 'merged', detail: '' })) }
    }
    if (/^worker-ant:[ab]:fix/.test(o.label)) { peak = Math.max(peak, ++busy); await new Promise(r => setTimeout(r, 3)); busy--; return W }
    if (o.label.startsWith('worker')) return W
    return o.label.includes('recheck') ? { fixed: [{ id: `${o.label.split(':')[1]}#1`, fixed: true }], bugs: [] } : { bugs: [] }
  })
  assert.equal(peak, 1)
  assert.ok(run1.calls.includes('worker-ant:c:update2') && run1.calls.includes('detective-ant:c:check2'))
  assert.ok(run1.calls.indexOf('worker-ant:c:update2') > run1.calls.indexOf('detective-ant:b:recheck1'))
  assert.deepEqual(run1.out.together.tasks.sort(), ['a', 'b', 'c'])
  const rows = run1.instant.concat().length  // per-reply entries exist; the stage summary logs each task once
  assert.ok(rows > 0)
})

test('build: a task built on a clash task that no longer passes is blocked, and ends are logged once', async () => {
  const prompts = {}
  let round = 0
  const { out } = await run('ishikari-build.js', { env, plans: [{ id: 'a' }, { id: 'b' }, { id: 'c', after: ['b'] }] }, (p, o) => {
    prompts[o.label] = p
    if (o.label.startsWith('integrator')) return ++round === 1
      ? { sha: 'abc1234', results: [{ id: 'a', outcome: 'merged', detail: '' }, { id: 'b', outcome: 'tests failed', detail: 'd', with: ['a'] }, { id: 'c', outcome: 'merged', detail: '' }] }
      : { sha: 'abc1234', results: [{ id: 'a', outcome: 'merged', detail: '' }] }
    if (o.label.startsWith('worker')) return W
    return o.label.includes('recheck') ? { fixed: [{ id: 'b#1', fixed: false }], bugs: [] } : { bugs: [] }
  })
  const by = Object.fromEntries(out.tasks.map(t => [t.id, t.status]))
  assert.deepEqual(by, { a: 'awaiting review', b: 'escalated', c: 'blocked' })
  const rows = logged(prompts['logbook-clerk'])
  for (const id of ['a', 'b', 'c']) {
    const ev = rows.filter(r => r.task === id).map(r => r.event)
    assert.equal(new Set(ev).size, ev.length, `${id}: ${ev.join(', ')}`)  // nothing logged twice
  }
})

test('build: a re-check that fixed nothing is not logged as passed', async () => {
  const { instant } = await buildWith({ plans: [{ id: 'a' }] }, o =>
    o.label === 'detective-ant:a:check' ? { bugs: ['x'], cause: 'c', plan: 'p' }
      : o.label.startsWith('detective') ? { fixed: [{ id: 'a#1', fixed: false }], bugs: [] } : undefined)
  const ev = instant.flatMap(p => logged(p)).filter(e => e.who === 'detective ant').map(e => e.event)
  assert.ok(ev.includes('1 still open') && !ev.slice(1).includes('passed'))
})

// ---- plan and env hardening ----
test('every script refuses paths, branches and commands the ants\' shell cannot carry', async () => {
  const good = {}
  const cases = [{ repo: '/my app' }, { state: '/s;rm' }, { tool: '/t/$(id).py' }, { main: '-x' }, { main: 'a b' }, { testCommand: 'make\ntest' }, { checkCommand: 'echo `id`' }, { testCommand: 7 }]
  const args = { 'ishikari-plan.js': { task: 't', ids: ['B1'], plans: [PLAN] }, 'ishikari-build.js': { plans: [{ id: 'a' }] }, 'ishikari-finish.js': { approved: [T('a')] }, 'ishikari-retro.js': {} }
  for (const [name, more] of Object.entries(args)) for (const c of cases) {
    const { out, calls } = await run(name, { env: { ...env, ...c }, ...more }, () => good)
    assert.equal(out.stage, 'error', `${name} ${JSON.stringify(c)}`)
    assert.equal(calls.length, 0)
  }
})



// ---- the two specs: detectives use the tech spec, the judge scores the product spec ----
test('build: workers and detectives get the tech spec, and workers the product spec for their ids', async () => {
  const prompts = await buildPrompts({ plans: [{ id: 'a', title: 'A' }] }, () => ({}))
  const w = prompts['worker-ant:a:build'], d = prompts['detective-ant:a:check']
  assert.ok(w.includes('/s/plans/r1/tech_spec.md') && w.includes('/s/plans/r1/product_spec.md'))
  assert.ok(d.includes('/s/plans/r1/tech_spec.md') && d.includes('differs from the tech spec is a bug'))
  assert.ok(![w, d].some(p => /architecture\.md|investigation_report/.test(p)))
  for (const p of [w, d]) assert.ok(/thin slice of the two specs/.test(p) && /plan file does not exist/.test(p) && /whole of the two specs/.test(p))
})

test('finish: the judge and jurors score against the product spec, id by id', async () => {
  const prompts = {}
  await run('ishikari-finish.js', { env, cleanup: true, approved: ['a', 'b', 'c'].map(T) }, (p, o) => {
    prompts[o.label] = p
    return o.label === 'merger-ant' ? { sha: 'abc1234', results: ['a', 'b', 'c'].map(id => ({ id, outcome: 'merged', detail: '' })) }
      : o.label.startsWith('juror') ? { score: 9, gaps: [] }
      : o.label.startsWith('judge') ? { score: 4, gaps: ['B2: missing'] }
      : o.label === 'docs-ant' ? NO_DOCS : o.label.startsWith('worker') ? { status: 'stuck', notes: 'n' } : { moved: true, reason: '' }
  })
  for (const label of ['judge-ant:1', 'juror-ant:1:a']) {
    assert.ok(prompts[label].includes('/s/plans/r1/product_spec.md'), label)
    assert.ok(/each behaviour/.test(prompts[label]) && /invariant/.test(prompts[label]), label)
    assert.ok(!/architecture\.md|investigation_report/.test(prompts[label]), label)
  }
  assert.ok(prompts['judge-ant:1'].includes('they are not what you score'))
  assert.ok(prompts['worker-ant:judge-fix'].includes('product_spec.md') && prompts['worker-ant:judge-fix'].includes('tech_spec.md'))
})
