#!/usr/bin/env bb
;; Build ishikari-metro.svg: the metro map, drawn as one open ring.
;; A run goes clockwise from Task at the top to the Run report; loops and
;; spurs bend inside the ring, and each spur names where it goes.
;; Run: bb metro.clj [OUT]  (writes OUT, else ishikari-metro.svg beside it)
(ns metro
  (:require [clojure.string :as str]
            [babashka.fs :as fs]
            [cheshire.core :as json]))

(def W 1700) (def H 1320)
(def BG "#0B1120") (def TXT "#F1F5F9") (def SUB "#A8B3C7")
(def BLUE "#60A5FA") (def GREEN "#4ADE80") (def RED "#F87171") (def GOLD "#FBBF24") (def GREY "#94A3B8")
(def INDIGO "#818CF8")
;; Colour means something: GREEN success or done, RED fail or error, GOLD a warning
;; (a bug being fixed, a low score). BLUE and INDIGO are plain flow.
(def CAR "#E2E8F0") ; train cars: neutral, so yellow keeps meaning warning

(defn esc [s] (-> s (str/replace "&" "&amp;") (str/replace "<" "&lt;") (str/replace ">" "&gt;")))

(defn txt
  "One <text> per line, lh apart (default size + 4)."
  [x y lines & {:keys [fill size anchor weight lh] :or {fill TXT size 14 anchor "start" weight "400"}}]
  (let [lh (or lh (+ size 4))]
    (apply str (map-indexed (fn [i l] (str "<text class=\"h\" x=\"" x "\" y=\"" (+ y (* i lh)) "\" fill=\"" fill
                                           "\" font-size=\"" size "\" text-anchor=\"" anchor "\" font-weight=\"" weight "\">" (esc l) "</text>"))
                            lines))))

(def CURVE 60) ; corner radius: every bend in a line is a smooth curve, not a sharp corner
(defn- fmt [v] (let [r (/ (Math/round (* 10.0 v)) 10.0)] (if (== r (Math/floor r)) (str (long r)) (str r))))
(defn d
  "SVG path through pts; each inner corner is rounded with a quadratic curve
  of up to CURVE px, never more than half of either segment."
  [pts]
  (let [p (fn [[x y]] (str (fmt x) "," (fmt y)))
        toward (fn [[ax ay] [bx by] r]
                 (let [len (Math/hypot (- bx ax) (- by ay))]
                   [(+ ax (* r (/ (- bx ax) len))) (+ ay (* r (/ (- by ay) len)))]))
        dist (fn [[ax ay] [bx by]] (Math/hypot (- bx ax) (- by ay)))]
    (str "M" (p (first pts))
         (apply str
                (for [[a b c] (partition 3 1 pts)
                      :let [r (min CURVE (/ (dist a b) 2) (/ (dist b c) 2))]]
                  (str " L" (p (toward b a r)) " Q" (p b) " " (p (toward b c r)))))
         (when (> (count pts) 1) (str " L" (p (last pts)))))))

;; ---- the ring ----
;; One run goes clockwise round an open ring: Task at the top, Run report just
;; before it, with a gap between so the start and the end stay clear. Angles are
;; degrees clockwise from 12 o'clock. Loops and spurs bend inside the ring;
;; station names sit outside it.
(def CX 850) (def CY 690) (def R 520)
(defn- r1 [v] (/ (Math/round (* 10.0 v)) 10.0))
(defn pt "The point at deg (clockwise from the top) and radius r." [deg r]
  (let [a (Math/toRadians deg)] [(r1 (+ CX (* r (Math/sin a)))) (r1 (- CY (* r (Math/cos a))))]))
(defn arc "Points along the ring from a0 to a1, every 2 degrees." [a0 a1]
  (mapv #(pt % R) (concat (range a0 a1 2) [a1])))
(defn along "The point a fraction t of the way from a to b." [[ax ay] [bx by] t]
  [(r1 (+ ax (* t (- bx ax)))) (r1 (+ ay (* t (- by ay))))])
(defn inward "p moved px towards the middle of the ring." [[x y] px]
  (let [len (Math/hypot (- x CX) (- y CY))] (along [x y] [CX CY] (/ px len))))

;; Stations are spread evenly round the ring, one step apart. The gap between
;; the judge and the docs ant is three steps wide: the judge's fix loop, with
;; its four stations, runs inside it.
(def A {"task" 12 "investigator" 32 "specs" 52 "workers" 72 "detectives" 92
        "integrator" 111 "merger" 131 "janitor" 150 "jurors" 170 "judge" 190 "docs" 249 "finisher" 269
        "main" 289 "check" 308 "retro" 328 "finished" 348})
(defn P [id] (pt (A id) R))
(def REJOIN (- (A "docs") 6))                       ; where the judge-fix loop rejoins the ring
(def JF0 (pt (+ (A "judge") 5) 400)) (def JF1 (pt (- REJOIN 4) 400)) ; the judge-fix loop's inner run
(def FIX0 (pt (- (A "detectives") 3) 420)) (def FIX1 (pt (+ (A "workers") 3) 420)) ; the fix loop's inner run
(def FIXMID (along FIX0 FIX1 0.5))
;; The many-plan rail's own fix loop: Detective ants back to Worker ants. It
;; runs inside the main line's loop, so the two never cross.
(def MW 69) (def MD 96) ; where Worker ants and Detective ants sit on the rail
(def MFIX0 (pt 90 400)) (def MFIX1 (pt 72 400))
(def JURY 160) ; the jury decision, between the janitor and the jurors
(def PLANS 59) ; the plans decision, between the specs and the workers
(def SOLO 476) ; the many-ant lanes' radius: inside the ring, clear of its station names
;; The ring is the single-ant path. Where a run may use several ants, a lane
;; leaves the ring at a decision and rejoins it: `many` (one worker and one
;; detective per plan) and `jury` (one juror per merged task).
(def MANY (vec (concat [(pt PLANS R)] (mapv #(pt % SOLO) (range (+ PLANS 4) (- (A "integrator") 3) 2)) [(P "integrator")])))
(def JLANE (vec (concat [(pt JURY R)] (mapv #(pt % SOLO) (range (+ JURY 4) (- (A "judge") 3) 2)) [(P "judge")])))
;; Many-ant stretches, drawn as a triple rail. [points colour]
(def YOU (pt (- (A "investigator") 6) (+ R 105))) (def RES (pt (A "investigator") (- R 150)))
(def FACTS (pt (A "investigator") (- R 50))) ; the facts decision, half way down the research line
(def RAILS [[[FACTS RES] BLUE] ; researcher ants: 1 to 5 at once
            [MANY INDIGO]     ; 2+ plans: one worker and one detective per plan
            [JLANE INDIGO]])  ; 3+ merged tasks: one juror per task

(def trunk (arc (A "workers") (A "main")))
(def lines ; name, colour, points, width, dash
  [["plan"    BLUE   (arc (A "task") (A "workers")) 12 ""]
   ["ask"     BLUE   [(P "investigator") YOU] 7 ""]
   ["res"     BLUE   [(P "investigator") RES] 7 ""]
   ;; "build" is the trains' route only (drawn invisible).
   ["build"   "none" trunk 12 ""]
   ["g1"      INDIGO trunk 12 ""]
   ;; 2+ plans: one worker ant and one detective ant per plan, on the rail inside the ring
   ["many"    INDIGO MANY 6 ""]
   ["fix"     GOLD   [(P "detectives") FIX0 FIX1 (P "workers")] 8 ""]
   ["mfix"    GOLD   (vec (concat [(pt MD SOLO)] (mapv #(pt % 400) (range 90 71 -2)) [(pt MW SOLO)])) 8 ""]
   ["fixloop" "none" (vec (concat (arc (A "workers") (A "detectives")) [FIX0 FIX1 (P "workers")])) 8 ""]
   ["clash"   GOLD   [(P "integrator") (pt (- (A "integrator") 2) 300) (pt 94 300) MFIX0] 6 "10 6"] ; tasks clash only with 2+ plans: back into the rail's fix loop
   ["drop"    RED    [FIXMID (inward FIXMID 80)] 6 "10 6"] ; crosses the rail's loop: both loops drop here
   ["mback"   RED    [(P "merger") (pt (A "merger") (- R 90))] 6 "10 6"] ; the merger's failed tasks: spur back to the worker ants
   ["tnext"   RED    [(P "janitor") (pt (A "janitor") (- R 150))] 6 "10 6"] ; the janitor's failed cleanup: its note becomes the next Task
   ["jury"    INDIGO JLANE 6 ""] ; 3+ merged tasks: the juror ants, on the rail inside the ring
   ["jfix"    GOLD   [(P "judge") JF0 JF1 (pt REJOIN R)] 9 ""]
   ;; train 11's route: the judge's fix round rejoins and rides on to MAIN (drawn invisible)
   ["jfixrun" "none"  (vec (concat [(P "judge") JF0 JF1] (arc REJOIN (A "main")))) 9 ""]
   ["after"   GREEN  (arc (A "main") (A "finished")) 9 ""]
   ["cfix"    RED    [(P "check") (pt (A "check") (- R 50))] 6 "10 6"] ; a failed check: a new task for the worker ants
   ["fast"    GREEN  [(P "specs") (P "main")] 6 "10 6"]]) ; a trivial task: the main session lands it straight on main

;; id, x, y, name, sub lines, kind, label offset [dx dy anchor].
;; The id never changes and is what spurs, details and links use; the short
;; code (s8: the 8th stop) is its place in this list, clockwise from Task.
(defn on
  "A station on the ring at deg. Its name sits outside the ring, on the same
  spoke: to the right on the right half, to the left on the left half."
  ([deg] (on deg [(pt deg (+ R 34)) nil]))
  ([deg [[lx ly] anchor]]
   (let [[x y] (pt deg R)
         sn (Math/sin (Math/toRadians deg)) cs (Math/cos (Math/toRadians deg))
         an (or anchor (cond (> sn 0.2) "start" (< sn -0.2) "end" :else "middle"))
         dy (cond (not= an "middle") 5 (pos? cs) -6 :else 16)]
     [x y [(r1 (- lx x)) (r1 (+ (- ly y) dy)) an]])))
(defn at "A station off the ring, at point p, with its own label offset." [[x y] lab] [x y lab])
(defn st [id [x y lab] nm sub kind] [id x y nm sub kind lab])
(def stations
  [
(st "task" (on (A "task")) "Task" ["you give it, or a" "dropped cleanup plan"] "task")
   (st "investigator" (on (A "investigator") [(pt (+ (A "investigator") 3.5) (+ R 38)) "start"]) "Investigator ant" ["one live agent on Fable at max effort: it asks you," "proves the task can be built, and writes the product" "spec, the tech spec and every plan; no other ant plans"] "x")
   (st "you" (at YOU [26 -6 "start"]) "You" ["up to 4 questions a round (/ask-simple)," "8 in all; answering approves the whole run"] "you")
   (st "researchers" (at RES [-26 5 "end"]) "Researcher ants  ∥" ["up to 5 at once, web + computer," "read only; the investigator waits"] "end")
   (st "specs" (on (A "specs")) "Specs + worker plans" ["product_spec.md: behaviours B1... and invariants I1...;" "tech_spec.md: the architecture and the code's shape;" "one thin plan per worker (none for one worker), checked before anything is built"] "files")
   (st "workers" (on (A "workers")) "Worker ant" ["one plan: one worker ant builds the whole task," "in its own worktree: code + tests + docs;" "stuck: next fix round"] "x")
   (st "detectives" (on (A "detectives")) "Detective ant" ["checks the built task against plan + tech spec," "runs tests (reuses the worker's if clean);" "finds each bug's cause and plans its fix"] "x")
   (st "integrator" (on (A "integrator")) "Integrator ant" ["merges passing tasks in a scratch" "copy, tests once: the combined test;" "fewer than 2 passing tasks: no combined test"] "x")
   (st "merger" (on (A "merger")) "Merger ant" ["merges in a straight line in a scratch copy," "or reuses build's trial merge; then checks" "its own merge with git cherry"] "x")
   (st "janitor" (on (A "janitor")) "Janitor ant" ["cleans up dead code and mess itself: edits," "runs the tests, commits, lands it only if" "they pass. Skipped under 100 changed lines;" "a cleanup run has no janitor"] "x")
   (st "jurors" (at (pt 175 SOLO) [0 -40 "middle"]) "Juror ants" ["one per merged task, one at a time" "(--parallel: up to 5); only with 3+ merged tasks"] "many")
   (st "judge" (on (A "judge")) "Judge ant" ["scores the run 0-10 against the product spec," "id by id; its own call, not an average;" "lists gaps, and which of them are bugs"] "x")
   (st "judge-fix-worker" (at (along JF0 JF1 0.15) [26 5 "start"]) "Worker ant" ["closes the gaps (below 7)" "or only the bugs (7+)"] "st")
   (st "judge-fix-detective" (at (along JF0 JF1 0.5) [26 5 "start"]) "Detective ant" ["checks the fix, runs the tests, then fast-forwards the" "scratch copy; the fix lands only through this fast-forward"] "st")
   (st "judge-again" (at (along JF0 JF1 0.85) [26 5 "start"]) "Judge ant" ["scores again; still below 7:" "main moves, verdict flagged"] "st")
   (st "docs" (on (A "docs")) "Docs ant" ["updates the docs with /docs, last, on the final code;" "no docs folder: writes docs/ from scratch, from the docs brief;" "lands only docs files, and only if the docs check and tests pass"] "x")
   (st "finisher" (on (A "finisher")) "Finisher ant" ["fast-forwards main to the checked commit," "removes worktrees, appends the stage rows, runs the check"] "x")
   (st "main" (on (A "main")) "MAIN" ["fast-forward only," "never pushed"] "main")
   (st "check" (on (A "check")) "checkCommand" ["the finisher ant builds and checks the app," "only when main moved and checkCommand is set"] "st")
   (st "retro" (on (A "retro")) "Retrospective ant" ["reviews how this run went, read only;" "writes retrospective.md: ranked fixes" "to the Ishikari flow; never after a fast path"] "x")
   (st "finished" (on (A "finished")) "Run report" ["the main session reports what landed," "the checks, the docs, the verdict and the retrospective"] "done")
   (st "logbook" (at [(- W 330) 50] [26 -4 "start"]) "Logbook" ["logbook clerk ant: appends each ant's entry" "the moment the ant replies, one clerk at a time, in plan, build, finish and the retrospective." "The live investigator gets only an investigated entry." "Build and finish add a summary at the end. No ant reads it." "~/.ishikari/<repo>-<hash>/logbook.rec"] "log")
   ;; the many-ant lane's stops: listed last, so the ring's stop codes never move
   (st "workers-many" (at (pt MW SOLO) [-26 -2 "end"]) "Worker ants" ["2+ plans: one worker ant per plan, one at a time" "(--parallel: up to 5), one worktree each;" "code + tests + docs; stuck: next fix round"] "many")
   (st "detectives-many" (at (pt MD SOLO) [-26 9 "end"]) "Detective ants" ["one per built task, one at a time by default: checks it" "against plan + tech spec, runs tests (reuses the worker's" "if clean); finds each bug's cause and plans its fix"] "many")])

;; Decision nodes: diamonds where the run picks how many ants a station uses,
;; or whether it is skipped. Not stations: they have no ant and no stop code.
;; id, point, label [dx dy anchor], the question, the answers drawn under it,
;; tooltip, the full story of each path.
(defn on-d "A decision on the ring at deg, labelled outside like a station." [deg]
  (let [[x y lab] (on deg)] [[x y] lab]))
(def decisions
  [["d-facts" [FACTS [-20 -1 "end"]]
    "facts missing?" "no: none  ·  yes: rail, 1 to 5 at once"
    "Decides whether any researcher ant runs."
    "The investigator decides while it reads the repo. Nothing missing: no researcher ant runs, and the path stays on the ring. Facts missing: the triple rail from the decision to the researcher ants. It starts 1 to 5 researcher ants at once and waits for them. They are the only ants that always run in parallel, with or without --parallel, because they only read."]
   ["d-plans" (on-d 59)
    "how many plans?" "1: main line, one worker  ·  2+: rail, one per plan"
    "Decides how many worker and detective ants there are."
    "The investigator decides when it writes the plans. One plan: the main line, on the ring. One worker ant builds the whole task straight from the two specs, with no plan file, and one detective ant checks it; with a single task there is no combined test, so the integrator is passed. Two or more plans: the triple rail inside the ring, which rejoins at the integrator. One worker ant and one detective ant per plan, each worker in its own worktree. A fix round reuses the task's own worker and detective. Whether they run together is the next decision."]
   ["d-parallel" [(pt 64.5 SOLO) [-22 -6 "end"]]
    "--parallel <n>?" "no: one at a time  ·  yes: up to n at once"
    "Decides whether worker, detective and juror ants run one at a time or together."
    "You decide, in the skill's arguments. Without --parallel: a single worker or detective ant runs at any moment, each task's detective waiting in the same line, and later a single juror at a time. With --parallel <n>, n from 2 to 5: up to n workers run at once, each detective starts the moment its task is built, and up to n jurors run at once, reading only. The number of ants is the same either way; only the order changes."]
   ["d-jury" (on-d JURY)
    "3+ merged tasks?" "no: main line, judge alone  ·  yes: rail, one juror per task"
    "Decides whether juror ants run."
    "The finish script counts the merged tasks. One or two: no juror ant runs; the main line goes straight to the judge ant, which reads everything itself. Three or more: the triple rail inside the ring. One juror ant per merged task scores its own task first, one at a time or up to n at once with --parallel, and the judge decides from their reports."]])

;; Skills each station's ant uses, drawn beside its name. List every one.
(def station-skills
  {"investigator"    ["/ask-simple"]
   "docs"            ["/docs"]
   "researchers"     ["/ux"]})

;; What a click on a station shows: a short line for the hover tooltip, the
;; full story for the panel, and where it lives. Keyed by [name x]: some names
;; appear twice. Every station needs one; the build fails without it.
(def details
  {"task" {:tip "The work you hand Ishikari."
                 :about "Your task in your own words, or the note of a cleanup the last run dropped. Setup makes the run's state folder and env first; the main checkout must be on the main branch with no uncommitted changes."
                 :src "SKILL.md#1-setup"}
   "investigator" {:tip "Asks you questions, then writes the two specs and every plan."
                             :about "One live agent run by the skill, not a workflow, on Fable at max effort; every other ant runs on Opus at low effort. It reads the repo once and gets each answer as a message. Part 1: it critiques the task, finds the test command, asks up to 4 independent questions at a time, 8 in all, writes the product spec and judges whether the task is trivial. Part 2, when told to go on: it proves the task can be built, writes the tech spec and one plan per worker ant, and may ask you again when the design needs a choice. No other ant plans, so nothing is lost between ants. It stays alive until its plans pass the check or a fast path lands. Ishikari needs the Agent tool for it."
                             :src "assets/prompts/investigator.md, SKILL.md#2a-investigate"}
   "you" {:tip "You answer the investigator's questions."
                :about "The only time Ishikari asks you anything. Questions come through /ask-simple, up to 4 at a time, about 8 in all. Answering approves the whole run, merge to main included."
                :src "SKILL.md#2a-investigate"}
   "researchers" {:tip "Look up facts for the investigator."
                               :about "Up to 5 at once, with or without --parallel: they only read, so nothing can collide. On Opus at low effort. They search the web and the whole computer, read only, never secrets, and report back. The investigator starts them and waits for them. They are not logged."
                               :src "SKILL.md#limits"}
   "specs" {:tip "Everything the investigator writes: the product spec, the tech spec and one plan per worker."
            :about "All written by the investigator, in this order. product_spec.md, once nothing important is unclear: two lists and nothing else. Behaviours, what the product does once the task is done, each with an id (B1, B2...) and written as given / when / then; invariants, what must always hold, each with an id (I1, I2...). Every one is written so an ant can check it, and each answer you gave shows up as the behaviour it led to. A task that changes no behaviour has invariants only. Then the trivial verdict: a trivial task is built from the product spec alone. tech_spec.md, once the investigator has proved the task can be built (from the repo's code and docs, a throwaway spike outside the repo only if needed): the parts of the change, the files each part owns, every name, interface and data shape between parts, and each id mapped to the part that delivers it. If the task cannot be built as asked it asks you; only when no answer can fix it, the run stops. Then docs_brief.md, for the docs ant, which cannot ask you anything: the purpose, readers, scope and non-goals, the reason behind each main design choice, and your answer for each root note and requirement file. Every docs question is asked while planning, inside the same 8. Last, one thin plan per worker ant: only that worker's slice of the specs, with its files, the spec ids it covers, the interfaces it uses, its tests and after; nothing is copied from the specs, which the worker reads for the detail. A run with one worker has no plan file: it builds straight from the specs. The plan script, which runs no ant, rejects bad or unknown ids, loops in after, two tasks on one file, paths outside the repo, a behaviour or invariant no plan covers, and a plan that covers none, before anything is built. Problems go back to the investigator once; still wrong, the run stops. Detectives check tasks against the plan and the tech spec; the judge scores the run against the product spec, id by id."
            :src "<state>/plans/<run>/product_spec.md, tech_spec.md, <task>.md"}
   "logbook" {:tip "Every ant's reply, one entry each."
                     :about "A recfile the logbook clerk appends to the moment an ant replies, one clerk at a time. Build and finish add a summary at the end. No ant reads it; read it with ishikari.py log status, recsel or an editor."
                     :src "~/.ishikari/<repo>-<hash>/logbook.rec"}
   "workers" {:tip "Build the plans, one worktree each."
                           :about "The main line: a run with one plan has one worker ant. It builds the whole task straight from the two specs, with no plan file, in its own git worktree. Two or more plans take the rail inside the ring, to the Worker ants. Writes code, tests and the docs its change affects, decides on its own and commits all its work. A worker that gets stuck says why, and that becomes a bug for the next fix round. A plan may name a saved workflow to run instead."
                           :src "scripts/ishikari-build.js"}
   "detectives" {:tip "Check each built task and plan every fix."
                              :about "The main line: a run with one plan has one detective ant, started once the task is built. Two or more plans take the rail inside the ring, to the Detective ants. Checks the work against its plan and the tech spec, and runs the tests. Each bug comes back with how to see it, its cause and a fix plan; a worker builds the fix and the detective re-checks. 3 tries per bug, 3 fix rounds, then the task drops. Never changes code. A dropped task's branch is kept for a later look, tasks built on it drop too, and the final report lists them."
                              :src "scripts/ishikari-build.js"}
   "workers-many" {:tip "Build the plans, one worker ant per plan."
                   :about "The rail: a run with two or more plans has one worker ant per plan, each in its own git worktree. By default one at a time: a single worker or detective runs at any moment. With --parallel <n> (2 to 5) up to n run at once. Each writes code, tests and the docs its change affects, decides on its own and commits all its work. A worker that gets stuck says why, and that becomes a bug for the next fix round. A plan may name a saved workflow to run instead. Each task has its own fix loop, the yellow line from the Detective ants back here."
                   :src "scripts/ishikari-build.js"}
   "detectives-many" {:tip "Check each built task and plan every fix, one detective ant per task."
                      :about "The rail: one detective ant per task, next in line once its task is built: by default it shares the one slot with the workers, and with --parallel it starts at once. Each checks its task against its plan and the tech spec, and runs the tests. Each bug comes back with how to see it, its cause and a fix plan; that task's worker builds the fix and the detective re-checks. 3 tries per bug, 3 fix rounds, then the task drops. Never changes code."
                      :src "scripts/ishikari-build.js"}
   "integrator" {:tip "Merges all passing tasks in a scratch copy and tests once."
                            :about "Two tasks can pass alone and break together. It merges every passing task in a straight line in a throwaway copy and runs the tests once. A clashing task takes in the tasks it clashes with and goes back through the fix loop; 2 rounds. Skipped with fewer than 2 passing tasks."
                            :src "scripts/ishikari-build.js (Combined phase)"}
   "merger" {:tip "Merges the approved tasks for real, then checks with git; failures go back to the workers."
                       :about "Adds every passing task's commits in a straight line, in dependency order, in a scratch copy, and tests once. It reuses build's trial merge when nothing moved. Then it checks its own merge with git cherry and counts changed lines with git diff --shortstat. Never touches main. A conflict, failed tests, or a task git finds missing goes back to the worker ant on its own branch: it merges the current main, fixes the bug, the detective re-checks, the integrator tests again, and finish retries the merge. Tasks that merged cleanly are not rebuilt. At most 2 extra build rounds; what is left drops and is reported."
                       :src "scripts/ishikari-finish.js (Merge phase)"}
   "docs" {:tip "Updates the repo's docs for the merged tasks, or writes them from scratch, last, on the final code."
           :about "Runs the /docs skill on the merged scratch copy, in its own worktree: update mode when the repo has docs/ or doc/, create mode when it has neither, writing docs/ from scratch. It never asks you: docs_brief.md, written by the investigator while planning, holds your answers and stands in for the skill's interview and its OK on the outline. It changes only files under docs/ or doc/ and Markdown or Org files elsewhere, never code, tests or data, and never asks the user: open questions go in the docs' Open questions chapter. It runs docs/build.sh diagrams and check when present, then the tests, and fast-forwards the scratch copy only if all pass. The script refuses the landing if a changed file is not a docs file, and a refused or failed update is put back on the scratch copy. It installs no tool, and moves or deletes a root note only where the brief says so. Failed: its branch is kept and main moves without it."
           :src "scripts/ishikari-finish.js (Upkeep phase)"}
   "janitor" {:tip "Cleans up mess the run left, by itself."
                        :about "Finds dead code, bloat and duplication from the merged tasks only. In its own worktree it edits, runs the tests and commits, and lands the cleanup only if they pass. Skipped under 100 changed lines, and a cleanup run gets no janitor. Tests failing: the cleanup is dropped, main moves with the tasks alone, its branch is kept, and its note goes to the next run's Task, where the investigator may ask about it."
                        :src "scripts/ishikari-finish.js (Upkeep phase)"}
   "jurors" {:tip "Score each merged task against its plan."
                          :about "One per merged task, only with 3 or more merged tasks; with one or two the judge works alone. By default one at a time. With --parallel <n> up to n at once, and then they only read: they never build or run the tests in the shared scratch copy. Each scores its task against that task's plan, and the judge weighs their reports."
                          :src "scripts/ishikari-finish.js"}
   "judge" {:tip "Scores the whole run 0-10 against the product spec."
                      :about "Reads the product spec and the merged code with the cleanup on top. One question, id by id: does the code behave as each behaviour says, and does each invariant hold? The tech spec and the plans are not what it scores. The score is its own call, not an average. It lists every gap, and repeats as bugs the gaps where the code itself behaves wrongly; a missing or weak test is a gap, not a bug. Below 7 with gaps: one fix round for every gap, then a second score. 7 or more with bugs: the same round, for the bugs only. Main always moves; a score still below 7 is flagged in the report."
                      :src "scripts/ishikari-finish.js"}
   "judge-fix-worker" {:tip "Closes the judge's gaps or bugs."
                       :about "Builds one fix on top of the merged scratch copy: every gap when the score is below 7, only the bugs when it is 7 or more."
                       :src "scripts/ishikari-finish.js"}
   "judge-fix-detective" {:tip "Checks the judge fix and lands it."
                          :about "Checks the fix and runs the tests. No bug and the tests pass: it fast-forwards the scratch copy to the fix itself. The fix lands only through this fast-forward. A failed fix keeps its branch and the verdict says why."
                          :src "scripts/ishikari-finish.js"}
   "judge-again" {:tip "Scores again after the fix."
                       :about "Scores the run a second time. Still below 7: main moves anyway and the verdict is flagged. The judge never blocks main."
                       :src "scripts/ishikari-finish.js"}
   "finisher" {:tip "Moves main, cleans up, runs the check."
                          :about "Fast-forwards main to the last checked commit, never to a branch by name; git refuses if it would overwrite local edits. A retry sees main already moved and carries on. Removes the worktrees, appends the stage's logbook rows, and runs checkCommand when it is set."
                          :src "scripts/ishikari-finish.js (Main phase)"}
   "main" {:tip "Your main branch, moved forward."
                  :about "Moves only as a fast-forward, never a merge commit, and is never pushed. Push it yourself when you are happy."
                  :src "SKILL.md#4-finish"}
   "check" {:tip "Builds and checks the app after main moves."
                          :about "The finisher ant runs the repo's saved checkCommand, only when main moved and the command is set. A failure starts one check-fix round. The check-fix round is one build round from the moved main, as a new task named check-fix. If the check still fails after it, the run stops and reports the output."
                          :src "ishikari.py config <state> checkCommand <cmd>"}
   "retro" {:tip "Reviews how this run went and suggests fixes to the Ishikari flow. Read only."
            :about "Runs once, as the very last step of every full run, however it ended: main moved, stopped, blocked or error; never after a fast path. It reads this run's logbook, the plans folder (product spec, tech spec, plans, cleanup note, every stage result), the run's git history and Ishikari's own source. It looks for bugs, errors, wasted or repeated ant calls, retries, dead ants, slow stages, misleading plans or prompts, weak checks and missing steps, each backed by evidence from the run. It writes retrospective.md in the run's plans folder, ranked costliest first, each finding naming the Ishikari file and rule to change. It changes nothing else; you decide what to act on."
            :src "scripts/ishikari-retro.js"}
   "finished" {:tip "The run ends with one report."
               :about "The main session reports what landed on main, the tests and the app check, the docs ant's update, the cleanup, the judge's verdict and the retrospective's top findings."
               :src "SKILL.md"}})

(defn detail [id]
  (or (details id) (throw (ex-info (str "no detail for station " id) {}))))

(def by-id
  (let [m (into {} (map (juxt first identity) stations))]
    (doseq [[id] stations] (when-not (re-matches #"[a-z][a-z0-9-]*" id) (throw (ex-info (str "bad station id " id) {}))))
    (when (not= (count m) (count stations)) (throw (ex-info "station ids must be unique" {})))
    m))

(def code
  "id -> short position code like s8: the station's place in the list."
  (into {} (map-indexed (fn [k [id]] [id (str "s" (inc k))]) stations)))

;; spurs: a short dashed line from a station to a label naming where it goes.
;; line name (in lines), target station id (nil: the line ends here), extra
;; words, lead-in, lines below, where the label sits [point anchor], end cap
;; (:bin: a bin drawn at the end).
(def spurs [["mback" "workers" "" "merge failed: " ["the worker merges main and fixes it;" "max 2 extra build rounds"] [(pt (A "merger") (- R 112)) "middle"]]
            ["drop" nil "" "dropped" ["after 3 tries on a bug or 3 fix rounds," "a blocked or failed worker, or a task" "built on a dropped one; branch kept"] [(let [[x y] (inward FIXMID 80)] [(- x 26) (+ y 5)]) "end"] :bin]
            ["tnext" "task" " (next run)" "cleanup failed: " ["branch kept; its note is offered"] [(pt (A "janitor") (- R 172)) "middle"]]
            ["cfix" "workers" " (new task)" "check failed: " ["one build round from the moved main;" "still failing: the run stops"] [(let [[x y] (pt (A "check") (- R 50))] [(+ x 14) (+ y 5)]) "start"]]
            ["fast" "main" "" "fast path: " ["trivial task, you confirm; the main session" "edits, tests, checks and lands it"] [(let [[x y] (along (P "specs") (P "main") 0.72)] [(+ x 40) (+ y 38)]) "middle"]]])

(defn ant? [nm] (str/includes? (str/lower-case nm) " ant"))

(defn hexm [x y r fill stroke sw]
  (let [pts (str/join " " (for [[dx dy] [[-1 0] [-0.5 -0.87] [0.5 -0.87] [1 0] [0.5 0.87] [-0.5 0.87]]]
                            (format "%.1f,%.1f" (double (+ x (* r dx))) (double (+ y (* r dy))))))]
    (str "<polygon points=\"" pts "\" fill=\"" fill "\" stroke=\"" stroke "\" stroke-width=\"" sw "\"/>")))

(def ICON {"drop" RED "done" GREEN "main" GREEN}) ; icon colour by meaning

(defn page
  "A page with a folded corner."
  [px py sw]
  (str "<path d=\"M" (- px 11) "," (- py 15) " L" (+ px 5) "," (- py 15) " L" (+ px 11) "," (- py 9) " L" (+ px 11) "," (+ py 15) " L" (- px 11) "," (+ py 15) " Z\" fill=\"" BG "\" stroke=\"" TXT "\" stroke-width=\"" sw "\" stroke-linejoin=\"round\"/>"
       "<path d=\"M" (+ px 5) "," (- py 15) " L" (+ px 5) "," (- py 9) " L" (+ px 11) "," (- py 9) "\" fill=\"none\" stroke=\"" TXT "\" stroke-width=\"" sw "\" stroke-linejoin=\"round\"/>"))

(defn icon
  "The station's shape, as SVG strings."
  [x y nm kind]
  (let [IC (get ICON kind TXT)]
    (cond
      (ant? (str/replace nm "  ∥" ""))
      (concat (when (or (str/includes? nm "∥") (= kind "many")) ; several ants: a stack of hexagons
                [(str (hexm (+ x 10) (- y 10) 16 BG TXT 3) (hexm (+ x 5) (- y 5) 16 BG TXT 3))])
              [(hexm x y 16 BG TXT 5)])

      (= kind "x")
      [(str "<circle cx=\"" x "\" cy=\"" y "\" r=\"14\" fill=\"" BG "\" stroke=\"" TXT "\" stroke-width=\"5\"/>")]

      (= kind "log") ; an open logbook: two pages, a spine, ruled lines
      (let [pg (fn [sx] (str "<path d=\"M" x "," (- y 10) " Q" (+ x (* sx 9)) "," (- y 15) " " (+ x (* sx 18)) "," (- y 11)
                             " L" (+ x (* sx 18)) "," (+ y 13) " Q" (+ x (* sx 9)) "," (+ y 9) " " x "," (+ y 14)
                             " Z\" fill=\"" BG "\" stroke=\"" TXT "\" stroke-width=\"3\" stroke-linejoin=\"round\"/>"))]
        [(str (pg -1) (pg 1) "<line x1=\"" x "\" y1=\"" (- y 10) "\" x2=\"" x "\" y2=\"" (+ y 14) "\" stroke=\"" TXT "\" stroke-width=\"3\"/>")
         (apply str (for [sx [-1 1] k (range 3)]
                      (str "<line x1=\"" (+ x (* sx 4)) "\" y1=\"" (+ (- y 4) (* k 6)) "\" x2=\"" (+ x (* sx 14)) "\" y2=\"" (+ (- y 5) (* k 6))
                           "\" stroke=\"" GREY "\" stroke-width=\"1.5\"/>")))])

      (#{"file" "files"} kind) ; "files" stacks two pages behind it
      (concat (when (= kind "files") [(str (page (+ x 8) (- y 8) 3) (page (+ x 4) (- y 4) 3))])
              [(page x y 4)
               (apply str (for [k (range 3)]
                            (str "<line x1=\"" (- x 6) "\" y1=\"" (+ (- y 3) (* k 6)) "\" x2=\"" (+ x 6) "\" y2=\"" (+ (- y 3) (* k 6))
                                 "\" stroke=\"" GREY "\" stroke-width=\"1.5\"/>")))])

      (= kind "drop") ; a bin: lid, handle, body with ribs
      [(str "<path d=\"M" (- x 11) "," (- y 8) " L" (+ x 11) "," (- y 8) " L" (+ x 8) "," (+ y 15) " L" (- x 8) "," (+ y 15)
            " Z\" fill=\"" BG "\" stroke=\"" IC "\" stroke-width=\"4\" stroke-linejoin=\"round\"/>"
            "<line x1=\"" (- x 15) "\" y1=\"" (- y 12) "\" x2=\"" (+ x 15) "\" y2=\"" (- y 12) "\" stroke=\"" IC "\" stroke-width=\"4\" stroke-linecap=\"round\"/>"
            "<path d=\"M" (- x 5) "," (- y 12) " L" (- x 5) "," (- y 17) " L" (+ x 5) "," (- y 17) " L" (+ x 5) "," (- y 12)
            "\" fill=\"none\" stroke=\"" IC "\" stroke-width=\"3\" stroke-linejoin=\"round\"/>")
       (apply str (for [k [-1 0 1]]
                    (str "<line x1=\"" (+ x (* k 5)) "\" y1=\"" (- y 3) "\" x2=\"" (+ x (* k 4.4)) "\" y2=\"" (+ y 10)
                         "\" stroke=\"" GREY "\" stroke-width=\"2\"/>")))]

      (= kind "task") ; a clipboard: board, clip, two ruled lines
      [(str "<rect x=\"" (- x 12) "\" y=\"" (- y 14) "\" width=\"24\" height=\"30\" rx=\"3\" fill=\"" BG "\" stroke=\"" TXT "\" stroke-width=\"4\"/>"
            "<rect x=\"" (- x 6) "\" y=\"" (- y 18) "\" width=\"12\" height=\"7\" rx=\"2\" fill=\"" TXT "\"/>"
            (apply str (for [k (range 2)]
                         (str "<line x1=\"" (- x 6) "\" y1=\"" (+ (- y 2) (* k 7)) "\" x2=\"" (+ x 6) "\" y2=\"" (+ (- y 2) (* k 7))
                              "\" stroke=\"" GREY "\" stroke-width=\"2\"/>"))))]

      (= kind "you") ; a person: head and shoulders
      [(str "<circle cx=\"" x "\" cy=\"" y "\" r=\"17\" fill=\"" BG "\"/>"
            "<circle cx=\"" x "\" cy=\"" (- y 7) "\" r=\"6.5\" fill=\"" BG "\" stroke=\"" TXT "\" stroke-width=\"4\"/>"
            "<path d=\"M" (- x 13) "," (+ y 15) " Q" (- x 13) "," (+ y 2) " " x "," (+ y 2) " Q" (+ x 13) "," (+ y 2) " " (+ x 13) "," (+ y 15)
            " Z\" fill=\"" BG "\" stroke=\"" TXT "\" stroke-width=\"4\" stroke-linejoin=\"round\"/>")]

      (= kind "main") ; a finish flag on a pole
      [(str "<line x1=\"" (- x 9) "\" y1=\"" (- y 16) "\" x2=\"" (- x 9) "\" y2=\"" (+ y 16) "\" stroke=\"" IC "\" stroke-width=\"4\" stroke-linecap=\"round\"/>"
            "<rect x=\"" (- x 9) "\" y=\"" (- y 16) "\" width=\"22\" height=\"16\" fill=\"" BG "\" stroke=\"" IC "\" stroke-width=\"3\"/>"
            (apply str (for [i (range 4) j (range 3) :when (even? (+ i j))]
                         (str "<rect x=\"" (+ (- x 9) (* i 5.5)) "\" y=\"" (+ (- y 16) (* j 5.33)) "\" width=\"5.5\" height=\"5.33\" fill=\"" IC "\"/>"))))]

      (= kind "done") ; a bold check mark
      [(str "<circle cx=\"" x "\" cy=\"" y "\" r=\"16\" fill=\"" BG "\"/>"
            "<path d=\"M" (- x 13) "," (+ y 1) " L" (- x 4) "," (+ y 11) " L" (+ x 14) "," (- y 12)
            "\" fill=\"none\" stroke=\"" IC "\" stroke-width=\"6\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>")]

      (= kind "end")
      [(str "<line x1=\"" (- x 16) "\" y1=\"" y "\" x2=\"" (+ x 16) "\" y2=\"" y "\" stroke=\"" TXT "\" stroke-width=\"7\" stroke-linecap=\"round\"/>")]

      :else
      [(str "<circle cx=\"" x "\" cy=\"" y "\" r=\"9\" fill=\"" TXT "\"/>")])))

;; numbered trains: number, route, colour, seconds per trip, start offset
(def trains [[1 "plan" BLUE 20 0] [2 "build" INDIGO 28 0] [3 "build" INDIGO 28 5.6] [4 "build" INDIGO 28 11.2]
             [5 "build" INDIGO 28 16.8] [6 "build" INDIGO 28 22.4] [7 "fixloop" GOLD 8 0] [8 "fixloop" GOLD 8 4]
             [10 "after" GREEN 5 0] [11 "jfixrun" GOLD 7 0]])

(def KX (- CX 250)) (def KY (- CY 90)) ; the key's top left corner

(defn legend
  "The key box in the middle of the ring."
  []
  (let [kx KX ky KY
        rows [[BLUE "1" "task on the plan line"] [INDIGO "2-6" "tasks on the main line to MAIN"] [GOLD "7-8" "a bug through the fix loop"]
              [GREEN "10" "after main moves"] [GOLD "11" "the judge's fix round"]]
        ;; right column: each symbol drawn, not typed, so every browser shows the same
        lx (+ kx 360) ly (+ ky 30)
        key (fn [i label] [(txt (+ lx 16) (+ ly (* i 16)) [label] :fill SUB :size 12) (+ lx 6) (+ ly (* i 16) -4)])
        [k2 ax ay] (key 2 "an ant (AI agent)")
        [k4 cx cy] (key 3 "dropped")
        [k5 ix iy] (key 4 "interchange")]
    (concat
     [(str "<rect x=\"" kx "\" y=\"" ky "\" width=\"500\" height=\"160\" rx=\"12\" fill=\"#0F172A\" stroke=\"#334155\"/>")]
     (mapcat (fn [i [c n t]]
               (let [y (+ ky 24 (* i 20))]
                 [(str "<line x1=\"" (+ kx 16) "\" y1=\"" y "\" x2=\"" (+ kx 60) "\" y2=\"" y "\" stroke=\"" c "\" stroke-width=\"7\" stroke-linecap=\"round\"/>")
                  (str "<rect x=\"" (+ kx 70) "\" y=\"" (- y 9) "\" width=\"34\" height=\"18\" rx=\"5\" fill=\"" CAR "\" stroke=\"" c "\" stroke-width=\"2\"/>"
                       "<text x=\"" (+ kx 87) "\" y=\"" (+ y 4) "\" font-size=\"11\" font-weight=\"800\" fill=\"" BG "\" text-anchor=\"middle\">" n "</text>")
                  (txt (+ kx 114) (+ y 5) [t] :size 13)]))
             (range) rows)
     [(txt lx ly ["dashed:" "a side branch"] :fill SUB :size 12 :lh 16)
      k2 (hexm ax ay 6 "none" SUB 1.5)
      k4 (str "<path d=\"M" (- cx 4) "," (- cy 2) " L" (+ cx 4) "," (- cy 2) " L" (+ cx 3) "," (+ cy 6) " L" (- cx 3) "," (+ cy 6)
              " Z\" fill=\"none\" stroke=\"" SUB "\" stroke-width=\"1.5\" stroke-linejoin=\"round\"/>"
              "<line x1=\"" (- cx 5.5) "\" y1=\"" (- cy 4) "\" x2=\"" (+ cx 5.5) "\" y2=\"" (- cy 4) "\" stroke=\"" SUB "\" stroke-width=\"1.5\" stroke-linecap=\"round\"/>"
              "<path d=\"M" (- cx 2) "," (- cy 4) " L" (- cx 2) "," (- cy 6) " L" (+ cx 2) "," (- cy 6) " L" (+ cx 2) "," (- cy 4)
              "\" fill=\"none\" stroke=\"" SUB "\" stroke-width=\"1.2\"/>")
      k5 (str "<circle cx=\"" ix "\" cy=\"" iy "\" r=\"5\" fill=\"none\" stroke=\"" SUB "\" stroke-width=\"1.5\"/>")
      (txt lx (+ ly (* 5 16)) ["stacked: several ants"] :fill SUB :size 12)
      (let [x (+ lx 6) y (+ ly (* 6 16) -4)]
        (str "<path d=\"M" x "," (- y 6) " L" (+ x 6) "," y " L" x "," (+ y 6) " L" (- x 6) "," y " Z\" fill=\"none\" stroke=\"" SUB "\" stroke-width=\"1.5\"/>"))
      (txt (+ lx 16) (+ ly (* 6 16)) ["a decision"] :fill SUB :size 12)
      (let [y (+ ly (* 7 16) -4)]
        (apply str (for [k [-3 0 3]] (str "<line x1=\"" lx "\" y1=\"" (+ y k) "\" x2=\"" (+ lx 12) "\" y2=\"" (+ y k) "\" stroke=\"" SUB "\" stroke-width=\"1.5\"/>"))))
      (txt (+ lx 16) (+ ly (* 7 16)) ["rail: many ants"] :fill SUB :size 12)]
     ;; colour key: what each colour means
     (loop [x (+ kx 16) [[c t] & more] [[GREEN "done"] [RED "failed"] [GOLD "warning"] [BLUE "plan"] [INDIGO "build"]] out []]
       (if-not c
         out
         (recur (+ x 22 (* (count t) 7)) more
                (conj out (str "<circle cx=\"" (+ x 5) "\" cy=\"" (+ ky 136) "\" r=\"5\" fill=\"" c "\"/>")
                      (txt (+ x 14) (+ ky 140) [t] :fill SUB :size 12))))))))

;; ---- everything on the map is clickable ----
;; Each clickable thing registers {id name code tip about src x y} here while
;; the map is drawn; the panel script gets the whole list. Stations come from
;; `details`; the rest from `about-lines`, `about-notes` and the items below.

(def about-lines
  "Line name -> [name tip about]. \"none\" lines are invisible train routes."
  {"plan"    ["Plan line" "The first stretch of the ring: from your task to the specs and worker plans." "The blue line carries one task from Task through the investigator and what it writes, the two specs and the worker plans, on to the worker ants, where building starts."]
   "ask"     ["Question line" "The investigator asks you, you answer." "The investigator's questions go up to you and your answers come back as messages to the same live agent. The dot riding it is one round of questions."]
   "res"     ["Research line" "The investigator sends researcher ants." "Up to 5 researcher ants at once look things up and report back down this line while the investigator waits. From the facts decision on it is a triple rail: several ants at once. The dot riding it is one burst of research."]
   "g1"      ["Build line" "The long stretch of the ring: build, check, merge, judge, finish." "The indigo trunk carries every task from the worker ants through checking, the combined test, the merge, the cleanup and the judge to MAIN. It is the single-ant path: one worker ant, one detective ant, the judge alone. Where a run uses several ants a triple rail leaves it at a decision and rejoins it. The numbered cars on it are tasks."]
   "fix"     ["Fix loop" "A bug goes back to the worker and is re-checked." "Yellow means a warning: the detective found a bug and planned its fix. The worker builds the fix and the detective re-checks, up to 3 tries per bug and 3 fix rounds."]
   "clash"   ["Clash line" "Tasks that break together go back to the fix loop." "Only a run with two or more plans can clash, so this line joins the many-plan rail's fix loop. When the integrator's combined test shows two passing tasks clash, the task takes in the tasks it clashes with and goes back through that loop: its worker fixes it, its detective re-checks. 2 rounds at most."]
   "mfix"    ["Fix loop, many plans" "A bug goes from the Detective ants back to the Worker ants." "Yellow means a warning. On the many-plan rail each task has its own loop: its detective ant finds a bug and plans the fix, that task's worker ant builds it, and the detective re-checks, up to 3 tries per bug and 3 fix rounds. One at a time by default, or several tasks at once with --parallel. A task that still has bugs leaves down the dropped spur."]
   "drop"    ["Dropped spur" "A task that could not be fixed leaves here." "A task drops when a bug is still open after 3 tries, when 3 fix rounds end with bugs open (both: escalated), when its worker is blocked or hits an error, or when its after names a task that dropped: tasks built on it drop too. The main session drops it without asking; it never reaches finish or main and nothing sends it back. Its branch is kept for a later look, and the final report lists it with why it dropped, its bugs and fix history."]
   "mback"   ["Merge failed spur" "A failed merge goes back to the worker ants." "A conflict, failed tests, or a task git cannot find goes back to the worker ant on its own branch: it merges main and fixes it, then the detective, integrator and merger run again. At most 2 extra build rounds."]
   "tnext"   ["Cleanup failed spur" "A failed cleanup becomes a suggested next task." "If the janitor's tests fail, main moves with the tasks alone, the cleanup branch is kept, and its note is offered as the Task of the next run."]
   "jury"    ["Jury rail" "3+ merged tasks: one juror ant per task." "A triple rail means several ants. With 3 or more merged tasks the run leaves the main line at the jury decision: one juror ant per merged task scores its own task, one at a time or up to n at once with --parallel, and the rail rejoins at the judge ant. With 1 or 2 merged tasks the run stays on the main line and the judge works alone."]
   "many"    ["Many-plan rail" "2+ plans: one worker ant and one detective ant per plan." "A triple rail means several ants. With two or more plans the run leaves the main line at the plans decision: one worker ant per plan builds it, one detective ant per task checks it, one at a time or up to n at once with --parallel, and the rail rejoins at the integrator, which tests the passing tasks together. The rail has its own fix loop, from the Detective ants back to the Worker ants, and the clash line joins it. With one plan the run stays on the main line: one worker ant, one detective ant."]
   "jfix"    ["Judge fix loop" "Below 7 with gaps, or 7+ with bugs: one fix round." "Yellow means a warning: the judge scored the run below 7 and listed gaps, or passed it but listed bugs, gaps where the code behaves wrongly. A worker closes the gaps, or at 7 or more only the bugs, a detective checks and fast-forwards the fix, and the judge scores again. Only one round."]
   "after"   ["After main moves" "Green: the run's work is on main." "After MAIN moves the finisher runs the check, the retrospective ant reviews the run, and the main session reports it."]
   "fast"    ["Fast path" "A trivial task skips the planning and build ants: straight across the ring to MAIN." "Once the product spec is written the investigator judges the task: trivial means a small, known scope (1-2 files), no design choice and one task; any question asked makes it not trivial. You confirm once. The main session then builds from the product spec alone: it edits on a branch in a worktree, runs the test and check commands, fast-forwards main only when both pass and logs it through ishikari.py. If it turns out bigger or a check keeps failing, the edits are thrown away and the full plan runs, told why."]
   "cfix"    ["Check failed spur" "A failed app check starts one new task." "If checkCommand fails after main moved, one build round runs as a new task named check-fix, from the moved main. Still failing: the run stops."]})

(def about-notes
  "Note id -> [name about] for notes drawn on the map. The ring needs none."
  {})

(def line-notes
  "Line name -> the short rules once written beside it, now shown in its panel."
  {"g1"    ["a plan may run a saved workflow in place of a worker ant" "built: its detective is next in line (--parallel: starts at once)" "no gaps, or 7+ with no bugs: no fix round"]
   "fix"   ["bugs: the detective's fix plan goes back to the worker;" "the worker builds it, the detective re-checks; 3 tries per bug"]
   "mfix"  ["bugs: each task's detective sends its fix plan back to that task's worker;" "3 tries per bug, 3 fix rounds"]
   "clash" ["fail: tasks clash: the task takes them in, then the fix loop; 2 rounds"]
   "jfix"  ["below 7 and gaps: one fix round for every gap" "7+ and bugs: one fix round for the bugs only" "a failed fix keeps its branch; the verdict says why"]})

(def items (atom []))

(defn clickable
  "Wrap body in a clickable group with a tooltip, and register what it is."
  [{:keys [id name code tip about src sub x y cls]} & body]
  (when (some #(= id (:id %)) @items) (throw (ex-info (str "duplicate clickable id " id) {})))
  (let [i (count @items)]
    (swap! items conj {:id id :name name :code (or code "") :tip tip :about about :src (or src "") :sub (vec sub) :x x :y y})
    (str "<g class=\"ck" (when cls (str " " cls)) "\" id=\"" (if (= cls "st") "st-" "it-") id "\" data-i=\"" i "\" tabindex=\"0\" role=\"button\">"
         "<title>" (esc (str name (when code (str " (" code ")")) ": " tip " Click for more.")) "</title>"
         (apply str body) "</g>")))

(defn panel
  "The click panel: an HTML box in a foreignObject, filled by a small script.
  Scripts run only when the SVG is opened directly; as an <img> the map stays
  plain and the hover tooltips still work."
  []
  (let [data (json/generate-string @items)]
    [(str "<style>.ck{cursor:pointer}.ck:hover text,.ck:focus text{text-decoration:underline}.ck:focus{outline:none}"
          ".hit{stroke:transparent;fill:none;pointer-events:stroke}"
          "#pn{display:none}#pn.on{display:block}"
          "#pn div{box-sizing:border-box;width:420px;padding:14px 16px;border-radius:12px;background:#111A2E;border:1.5px solid " INDIGO ";"
          "color:" TXT ";font:14px/1.45 ui-sans-serif,-apple-system,Helvetica,Arial,sans-serif;box-shadow:0 8px 30px #000a}"
          "#pn b{display:block;font-size:17px}#pn small{display:block;color:" SUB ";font:12px ui-monospace,monospace;margin:2px 0 8px}#pn p{margin:0 0 10px}#pn p.sum{color:" SUB "}#pn p.sum:empty{display:none}#pn code{color:" SUB ";font-size:12px}"
          "#pn i{float:right;font-style:normal;color:" SUB ";cursor:pointer}</style>")
     "<foreignObject id=\"pn\" x=\"0\" y=\"0\" width=\"420\" height=\"400\"><div xmlns=\"http://www.w3.org/1999/xhtml\"><i title=\"Close (Esc)\">✕</i><b></b><small></small><p class=\"sum\"></p><p class=\"about\"></p><code></code></div></foreignObject>"
     (str "<script><![CDATA[\n"
          "(function(){\n"
          "var D=" (str/replace data "]]>" "]]\\u003e") ";\n"
          "var W=" W ",H=" H ",svg=document.documentElement,pn=document.getElementById('pn'),box=pn.firstChild;\n"
          "function show(i,px,py){var d=D[i];box.querySelector('b').textContent=d.name;\n"
          " box.querySelector('small').textContent=d.id+(d.code?' \\u00b7 '+d.code:'');\n"
          " box.querySelector('p.sum').textContent=(d.sub||[]).join(' ');box.querySelector('p.about').textContent=d.about;\n"
          " box.querySelector('code').textContent=d.src;box.querySelector('code').style.display=d.src?'':'none';pn.classList.add('on');\n"
          " var ax=px==null?d.x:px,ay=py==null?d.y:py,h=box.offsetHeight||200,x=ax+30,y=ay-20;\n"
          " if(x+420>W-10)x=ax-450;if(x<10)x=10;if(y+h>H-10)y=H-10-h;if(y<10)y=10;\n"
          " pn.setAttribute('x',x);pn.setAttribute('y',y);pn.setAttribute('height',h+4);}\n"
          "function at(e){var p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;return p.matrixTransform(svg.getScreenCTM().inverse());}\n"
          "function hide(){pn.classList.remove('on');}\n"
          "document.querySelectorAll('.ck').forEach(function(g){\n"
          " g.addEventListener('click',function(e){e.stopPropagation();var p=at(e);show(+g.dataset.i,p.x,p.y);});\n"
          " g.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();show(+g.dataset.i);}});});\n"
          "pn.addEventListener('click',function(e){e.stopPropagation();if(e.target.tagName==='i')hide();});\n"
          "document.addEventListener('click',hide);\n"
          "document.addEventListener('keydown',function(e){if(e.key==='Escape')hide();});\n"
          "function fromHash(){var id=location.hash.replace(/^#((st|it)-)?/,'');for(var i=0;i<D.length;i++)if(D[i].id===id||D[i].code===id){show(i);return;}}\n"
          "window.addEventListener('hashchange',fromHash);fromHash();\n"
          "})();\n"
          "]]></script>")]))

(defn note [id x y lines & opts]
  (let [[nm about] (or (about-notes id) (throw (ex-info (str "no about for note " id) {})))]
    (clickable {:id id :name nm :tip (first lines) :about about :x x :y y} (apply txt x y lines opts))))

(defn svg-body []
  (concat
   [(str "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 " W " " H "\" width=\"" W "\" height=\"" H "\" font-family=\"ui-sans-serif,-apple-system,Helvetica,Arial,sans-serif\">")
    "<title>Ishikari metro map, readable</title>"
    "<defs><filter id=\"g\" x=\"-100%\" y=\"-100%\" width=\"300%\" height=\"300%\"><feGaussianBlur stdDeviation=\"3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter></defs>"
    (str "<style>.h{paint-order:stroke;stroke:" BG ";stroke-width:5px;stroke-linejoin:round}.flow{animation:f 1.2s linear infinite}@keyframes f{to{stroke-dashoffset:-32}}</style>")
    (str "<rect width=\"" W "\" height=\"" H "\" fill=\"" BG "\"/>")
    (clickable {:id "title" :name "Ishikari metro map" :tip "How to read this map."
                :about "Ishikari runs a task with many ants, one worker, detective or juror at a time unless you pass --parallel. The map is one open ring: read it clockwise from Task at the top, round to the Run report. The gap at the top says a run ends; the next one is yours to start. Loops and spurs bend inside the ring. Hexagons are ants (AI agents), diamonds are decisions, the ring is the single-ant path and a triple rail leaving it is a many-ant path, pages are files, dashed lines are side branches, and colour means something: green done, red failed, yellow warning. Click anything to learn what it is; Esc closes this panel."
                :src "skills/ishikari/design/index.md" :x CX :y (- CY 140)}
               (txt CX (- CY 140) ["ISHIKARI METRO"] :size 28 :anchor "middle" :weight "800")
               (txt CX (- CY 112) ["Read it clockwise, from Task at the top."] :fill SUB :size 15 :anchor "middle"))]
   ;; the three parts of the ring, named in the corners
   (for [[k x y an label c about] [[1 (- W 30) 150 "end" "1 ASK  ·  2 PLAN" BLUE "Steps 1 and 2, the blue stretch from Task to the worker plans: the investigator asks you its questions, then writes the product spec, the tech spec and one plan per task; the plan stage only checks the plans. The only part where you are asked anything."]
                                   [2 (- W 30) (- H 40) "end" "3 BUILD  ·  4 CHECK  ·  5 FIX  ·  6 MERGE" INDIGO "Steps 3 to 5 and the first half of step 6, the indigo stretch down the right and along the bottom: worker ants build the plans, one at a time or up to 5 at once with --parallel, detective ants check each one and plan fixes, the integrator tests all passing tasks together, then the merger lands them in a scratch copy and the janitor cleans up. Main has not moved yet."]
                                   [3 30 (- H 40) "start" "6 FINISH: JUDGE  ·  MAIN MOVES" INDIGO "Step 6, second half, up the left side: the judge scores the run against the product spec, the docs ant updates the docs, the finisher moves main forward and runs the check, the retrospective ant reviews the run, and the run is reported."]]]
     (clickable {:id (str "part-" k) :name (str "Part " k) :tip label :about about :src "skills/ishikari/SKILL.md" :x x :y y}
                (txt x y [label] :fill c :size 13 :anchor an :weight "800")))
   (for [[name c pts w dash] lines
         :let [path (str "<path id=\"L-" name "\" d=\"" (d pts) "\" fill=\"none\" stroke=\"" c "\" stroke-width=\"" w "\" stroke-linejoin=\"round\" stroke-linecap=\"round\""
                         (when (seq dash) (str " stroke-dasharray=\"" dash "\" class=\"flow\"")) "/>")]]
     (if (= c "none")
       path
       (let [[nm tip about] (or (about-lines name) (throw (ex-info (str "no about for line " name) {})))
             [x y] (nth pts (quot (count pts) 2))]
         (clickable {:id (str "line-" name) :name nm :tip tip :about about :sub (line-notes name) :x x :y y}
                    path (str "<path class=\"hit\" d=\"" (d pts) "\" stroke-width=\"20\"/>")))))
   (for [[pts c] RAILS
         :let [p (d pts)]]
     ;; wider than the trunk, so the many-ant path reads as the heavier one
     (apply str (for [[col w] [[c 20] [BG 13] [c 4.5]]]
                  (str "<path d=\"" p "\" fill=\"none\" stroke=\"" col "\" stroke-width=\"" w "\" pointer-events=\"none\"/>"))))
   (for [[ln to more lead below [[lx ly] lan] cap] spurs
         :let [[_ c pts] (or (some #(when (= (first %) ln) %) lines) (throw (ex-info (str "no line " ln) {})))
               [x y] (last pts)
               [_ _ ty nm] (when to (or (by-id to) (throw (ex-info (str "spur " ln " goes to unknown station " to) {}))))
               head (str lead (when to (str "to " (str/replace nm "  ∥" "") " " (code to) more)))
               [lname _ labout] (about-lines ln)]]
     (str
      ;; a spur that leaves a line between stations gets a junction dot, so it never branches from nowhere
      (let [[sx sy] (first pts)]
        (when-not (some (fn [[_ x2 y2]] (and (= x2 sx) (= y2 sy))) stations)
          (clickable {:id (str "junction-" ln) :name "Junction" :tip (str "Where the " (str/lower-case lname) " leaves the line.")
                      :about (str "Not a station: the point where the " (str/lower-case lname) " branches off. " labout) :x sx :y sy}
                     (str "<circle cx=\"" sx "\" cy=\"" sy "\" r=\"8\" fill=\"" TXT "\" stroke=\"" c "\" stroke-width=\"3\"/>"))))
      (clickable {:id (str "spur-" ln) :name lname :tip head :about labout :sub below :x x :y y}
                 (str (when (= cap :bin) (apply str (icon x y "" "drop")))
                      (txt lx ly [head] :fill c :size 13 :anchor lan :weight "700")))))
   ;; a loop that rejoins a line between stations gets a junction dot too
   (for [ln ["jfix" "clash"]
         :let [[_ c pts] (some #(when (= (first %) ln) %) lines)
               [sx sy] (last pts)
               [lname _ labout] (about-lines ln)]
         :when (not-any? (fn [[_ x2 y2]] (and (= x2 sx) (= y2 sy))) stations)]
     (clickable {:id (str "junction-" ln "-end") :name "Junction" :tip (str "Where the " (str/lower-case lname) " rejoins the line.")
                 :about (str "Not a station: the point where the " (str/lower-case lname) " rejoins. " labout) :x sx :y sy}
                (str "<circle cx=\"" sx "\" cy=\"" sy "\" r=\"8\" fill=\"" TXT "\" stroke=\"" c "\" stroke-width=\"3\"/>")))
   (for [[id x y nm sub kind [dx dy an]] stations
         :let [{:keys [tip about src]} (detail id)]]
     (clickable {:id id :cls "st" :name (str/replace nm "  ∥" "") :code (code id) :tip tip :about about :src src :sub sub :x x :y y}
                (apply str (icon x y nm kind))
                (str/replace (txt (+ x dx) (+ y dy) [nm] :size 16 :anchor an :weight "700")
                             "</text>" (str "<tspan dx=\"5\" font-size=\"11\" font-weight=\"400\" fill=\"" GREY "\">" (code id) "</tspan>"
                                             (when-let [sk (station-skills id)]
                                               (str "<tspan dx=\"6\" font-size=\"12\" font-weight=\"600\" fill=\"" INDIGO "\">" (esc (str/join " " sk)) "</tspan>"))
                                             "</text>"))
                ))
   [(let [[x y] (inward FIXMID 17)]
      (clickable {:id "junction-drop-rail" :name "Junction" :tip "Where the many-plan fix loop meets the dropped spur."
                  :about "Not a station: a task on the many-plan rail that cannot be fixed leaves its fix loop here too, down the same dropped spur as a task on the main line." :x x :y y}
                 (str "<circle cx=\"" x "\" cy=\"" y "\" r=\"8\" fill=\"" TXT "\" stroke=\"" RED "\" stroke-width=\"3\"/>")))]
   (for [[id [[x y] [dx dy an]] q answers tip about] decisions]
     (clickable {:id id :name (str "Decision: " q) :tip tip :about about :sub [answers] :x x :y y}
                (str "<path d=\"M" x "," (- y 14) " L" (+ x 14) "," y " L" x "," (+ y 14) " L" (- x 14) "," y " Z\" fill=\"" BG "\" stroke=\"" TXT "\" stroke-width=\"4\" stroke-linejoin=\"round\"/>"
                     "<text x=\"" x "\" y=\"" (+ y 5) "\" font-size=\"14\" font-weight=\"800\" fill=\"" TXT "\" text-anchor=\"middle\">?</text>")
                (txt (+ x dx) (+ y dy) [q] :size 13 :anchor an :weight "700")
                (txt (+ x dx) (+ y dy 15) [answers] :fill SUB :size 12 :anchor an :weight "600")))
   (for [[n path c sec beg] trains
         :let [[lname] (about-lines (if (= path "build") "g1" (case path "fixloop" "fix" "jfixrun" "jfix" path)))]]
     (clickable {:id (str "train-" n) :name (str "Car " n) :tip (str "A sample task riding the " (str/lower-case lname) ".")
                 :about (str "The numbered cars are sample tasks moving through the run, so you can follow one. Car " n " rides the " (str/lower-case lname) "; the key in the middle of the ring says what each number shows.") :x 0 :y 0}
                ;; the car body turns with the track (rotate="auto"), its nose pointing the way it goes;
                ;; the number rides the same path without turning, so it never reads upside down
                (let [move (fn [rot] (str "<animateMotion dur=\"" sec "s\" begin=\"" (- beg) "s\" repeatCount=\"indefinite\"" rot "><mpath href=\"#L-" path "\"/></animateMotion>"))]
                  (str "<g filter=\"url(#g)\"><path d=\"M-16,-11 H6 Q9,-11 11,-8 L18,0 L11,8 Q9,11 6,11 H-16 Q-19,11 -19,8 V-8 Q-19,-11 -16,-11 Z\" fill=\"" CAR "\" stroke=\"" c "\" stroke-width=\"3\" stroke-linejoin=\"round\"/>"
                       (move " rotate=\"auto\"") "</g>"
                       "<g><text y=\"5\" font-size=\"14\" font-weight=\"800\" fill=\"" BG "\" text-anchor=\"middle\">" n "</text>"
                       (move "") "</g>"))))
   (for [[path sec what] [["ask" 6 "a round of questions"] ["res" 5 "a burst of research"]]]
     (clickable {:id (str "dot-" path) :name "Moving dot" :tip (str "Shows " what ".")
                 :about (str "The small dot going back and forth shows " what " travelling between the ants.") :x (first (P "investigator")) :y (second (P "investigator"))}
                (str "<circle r=\"7\" fill=\"" CAR "\" filter=\"url(#g)\"><animateMotion dur=\"" sec "s\" repeatCount=\"indefinite\" keyPoints=\"0;1;0\" keyTimes=\"0;0.5;1\" calcMode=\"linear\"><mpath href=\"#L-" path "\"/></animateMotion></circle>")))
   [(clickable {:id "key" :name "Key" :tip "What the cars, symbols and colours mean."
                :about "Left: what each numbered car shows. Right: the symbols: hexagon an ant, bin dropped, circle an interchange, diamond a decision about how many ants run or whether a stop is skipped, triple rail a lane where several ants run, leaving the single-ant main line at a decision and rejoining it, stacked hexagons a stop where several ants run (the mark ∥ after a name: always at once), dashed a side branch. Bottom: green done, red failed, yellow warning, blue plan, indigo build."
                :x KX :y KY}
               (apply str (legend)))]))

(defn svg []
  (reset! items [])
  (let [body (doall (svg-body))]
    (concat body (panel) ["</svg>"])))

(def short-help "metro.clj: build ishikari-metro.svg, the Ishikari metro map. Usage: bb metro.clj [OUT]")
(def full-help (str short-help "

One open ring, read clockwise from Task at the top to the Run report. Loops and
spurs bend inside the ring, and each spur names the station it goes to.

  bb metro.clj          write ishikari-metro.svg beside this script
  bb metro.clj OUT      write the map to OUT
  bb metro.clj -h       short help;  help: this text

Run it after a flow change. test_metro_map in tests/test_ishikari.py checks
the committed SVG matches a fresh build."))

(case (first *command-line-args*)
  ("-h" "--help") (do (println short-help) (System/exit 0))
  "help" (do (println full-help) (System/exit 0))
  nil)

(let [out (or (first *command-line-args*)
              (str (fs/path (fs/parent (fs/absolutize *file*)) "ishikari-metro.svg")))]
  (spit out (str/join "\n" (svg))))
