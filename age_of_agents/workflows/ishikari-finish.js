export const meta = {
  name: 'ishikari-finish',
  description: 'Ishikari stage 3: merger ant merges approved tasks, then the always-on ants run once',
  whenToUse: 'After the user approves tasks in their final review of ishikari-build.',
  phases: [
    { title: 'Merge', detail: 'merger ant, one task at a time' },
    { title: 'Upkeep', detail: 'janitor, librarian and philosopher ants' },
  ],
}

// args: {
//   repo: string,                      absolute repo path
//   approved: [{id, branch}],          tasks the user approved
// }
// Returns { merged, bugs, cleanupPlan } — bugs feed the next ishikari-build run.

const MERGE = {
  type: 'object',
  properties: {
    merged: { type: 'boolean' },
    broke: { type: 'string', description: 'what broke on main after the merge, empty if nothing' },
  },
  required: ['merged', 'broke'],
}

const { repo, approved = [] } = args

phase('Merge')
const merged = []
const bugs = []
// One merge at a time: each merge must see the main the last one left.
for (const t of approved) {
  const r = await agent(
    `You are the merger ant of the Ishikari workflow. Repo: ${repo}.
Merge branch ${t.branch} into main. Run the repo's tests on main after.
If the merge or the tests fail, leave main as it was before this merge and
report what broke. Then set row "${t.id}" in ${repo}/boards/bulletin.md to
status "done" if merged.`,
    { label: `merger-ant:${t.id}`, phase: 'Merge', schema: MERGE },
  )
  if (r && r.merged && !r.broke) merged.push(t.id)
  else bugs.push({ id: t.id, task: t.id, branch: t.branch, bug: `merge broke main: ${r ? r.broke : 'merger ant died'}` })
}

phase('Upkeep')
const [cleanupPlan] = await parallel([
  () => agent(
    `You are the janitor ant of the Ishikari workflow. Repo: ${repo}.
Find dead code, bloat and mess left by the tasks just merged (${merged.join(', ')}).
Only worker ants write code, so return a complete cleanup plan for one; change no files.`,
    { label: 'janitor-ant', phase: 'Upkeep' },
  ),
  () => agent(
    `You are the librarian ant of the Ishikari workflow. Repo: ${repo}.
Update the docs for the tasks just merged (${merged.join(', ')}). Change docs only.`,
    { label: 'librarian-ant', phase: 'Upkeep' },
  ),
  () => agent(
    `You are the philosopher ant of the Ishikari workflow. Repo: ${repo}.
Question and critique the work just merged (${merged.join(', ')}). Add rows to
${repo}/boards/critiques.md. Never block or change anything else.`,
    { label: 'philosopher-ant', phase: 'Upkeep' },
  ),
])

return { merged, bugs, cleanupPlan }
