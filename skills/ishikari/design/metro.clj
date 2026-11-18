#!/usr/bin/env bb
;; Build ishikari-metro.svg: the metro map laid out for reading.
;; Four rows read left to right like text; cross-row links are short
;; transfer spurs with a named destination instead of long lines.
;; Run: bb metro.clj [OUT]  (writes OUT, else ishikari-metro.svg beside it)
(ns metro
  (:require [clojure.string :as str]
            [babashka.fs :as fs]))

(def W 2000) (def H 1960)
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

(defn d [pts] (str "M" (str/join " L" (map (fn [[x y]] (str x "," y)) pts))))

(def R1 200) (def R2 540) (def R3 1080) (def R4 1520)
(def X 1900)              ; where each row wraps down to the next
(def J1 400) (def J2 1000) ; first and second Judge ant (the gold judge-fix dip runs between)
(def DIP4 1610)           ; y of the judge-fix dip (row 4)

(def trunk [[200 R2] [X R2] [X 860] [60 860] [60 R3] [X R3] [X 1400] [60 1400] [60 R4] [1340 R4]])
(def lines ; name, colour, points, width, dash
  [["plan"    BLUE   [[120 R1] [X R1] [X 370] [60 370] [60 R2] [200 R2]] 12 ""]
   ["ask"     BLUE   [[440 R1] [440 90]] 7 ""]
   ["res"     BLUE   [[440 R1] [440 300]] 7 ""]
   ;; "build" is the trains' route only (drawn invisible).
   ["build"   "none" trunk 12 ""]
   ["g1"      INDIGO trunk 12 ""]
   ["fix"     GOLD   [[760 R2] [730 640] [230 640] [200 R2]] 8 ""]
   ["fixloop" "none" [[200 R2] [760 R2] [730 640] [230 640] [200 R2]] 8 ""]
   ["clash"   GOLD   [[1200 R2] [1200 700] [800 700] [760 R2]] 6 "10 6"]
   ["drop"    RED    [[660 640] [660 740]] 6 ""]
   ["mfail"   RED    [[480 R3] [480 1180]] 6 "10 6"]
   ["tdrop"   RED    [[760 R3] [760 1200]] 6 "10 6"]
   ["jfix"    GOLD   [[J1 R4] [460 DIP4] [J2 DIP4] [1060 R4]] 9 ""]
   ["after"   GREEN  [[1340 R4] [1780 R4]] 9 ""]
   ["cfix"    RED    [[1580 R4] [1580 1660]] 6 "10 6"]])

;; x, y, name, sub lines, kind, label anchor [dx dy anchor]
(def L-UP [0 -60 "middle"]) (def L-DN [0 34 "middle"]) (def RIGHT [26 -4 "start"])
(def stations
  [;; row 1: ask and plan
   [120 R1 "Task" ["you give it, or a" "dropped cleanup plan"] "task" L-DN]
   [440 R1 "Investigator ant" ["one live agent run by the skill: reads" "the repo once, gets each answer as a message;" "no Agent tool: the plan workflow runs it"] "x" [-22 -74 "end"]]
   [440 90 "You" ["up to 4 questions a round (/ask-simple)," "8 in all; answering approves the whole run"] "you" [26 -6 "start"]]
   [440 300 "Researcher ants  ∥" ["up to 5 at once, web + computer," "read only; the investigator waits"] "end" [24 -4 "start"]]
   [780 R1 "investigation_report.md" ["written when nothing is unclear;" "the investigator is stopped"] "file" L-DN]
   [1100 R1 "Add requirement ant" ["drafts the requirement entry;" "the main session pipes it into ishikari.py req add;" "no requirements file: no add requirement ant"] "st" L-DN]
   [1420 R1 "Architect ant" ["writes architecture.md" "and one plan per task"] "st" L-UP]
   [1700 R1 "Worker plans" ["one per task: title, files, after;" "checked before anything is built"] "files" L-DN]
   [1370 40 "Logbook" ["logbook clerk ant: appends each ant's entry" "the moment the ant replies, one clerk at a time, in plan, build and finish." "The live investigator gets only an investigated entry." "Build and finish add a summary at the end. No ant reads it." "~/.ishikari/<repo>-<hash>/logbook.rec"] "log" RIGHT]
   ;; row 2: build, check, fix
   [200 R2 "Worker ants  ∥" ["max 5, one worktree each," "code + tests + docs;" "stuck: next fix round"] "x" [0 -84 "middle"]]
   [760 R2 "Detective ants  ∥" ["one per built task: checks it against plan +" "design, runs tests (reuses the worker's if clean);" "finds each bug's cause and plans its fix"] "x" [0 -86 "middle"]]
   [1200 R2 "Integrator ant" ["merges passing tasks in a scratch" "copy, tests once: the combined test;" "fewer than 2 passing tasks: no combined test"] "x" [0 -78 "middle"]]
   [660 750 "Dropped" ["after 3 tries on a bug or" "3 fix rounds; branch kept"] "drop" RIGHT]
   ;; row 3: merge and cleanup
   [200 R3 "Merger ant" ["merges in a straight line in a scratch copy," "or reuses build's trial merge; then checks" "its own merge with git cherry"] "x" [0 -70 "middle"]]
   [480 1180 "merge failed" ["a conflict, failed tests, or a task" "git finds missing: next build round;" "max 2 extra build rounds"] "retry" RIGHT]
   [760 R3 "Janitor ant" ["cleans up dead code and mess itself: edits," "runs the tests, commits, lands it only if" "they pass. Skipped under 100 changed lines;" "a cleanup run has no janitor"] "x" [0 -88 "middle"]]
   [760 1210 "Dropped cleanup" ["tests failed: branch kept," "its note offered as the next Task"] "drop" RIGHT]
   ;; row 4: judge, then main moves
   [160 R4 "Juror ants  ∥" ["one per merged task, 5 at once;" "only with 3+ merged tasks"] "x" L-DN]
   [J1 R4 "Judge ant" ["scores the run 0-10: does the code" "match the plans? its own call, not an average"] "x" L-UP]
   [500 DIP4 "Worker ant" ["closes the judge's gaps"] "st" L-DN]
   [660 DIP4 "Detective ant" ["checks the fix, runs the tests"] "st" L-UP]
   [820 DIP4 "Merger ant" ["fast-forwards the scratch copy to the fix;" "the fix lands only through this fast-forward"] "st" L-DN]
   [J2 DIP4 "Judge ant" ["scores again; still below 7:" "main moves, verdict flagged"] "st" [14 34 "start"]]
   [1180 R4 "Finisher ant" ["fast-forwards main, removes worktrees," "appends the stage rows, runs the check"] "x" L-UP]
   [1340 R4 "MAIN" ["fast-forward only," "never pushed"] "main" L-DN]
   [1580 R4 "checkCommand" ["the finisher ant builds and checks the app," "only when main moved and checkCommand is set"] "st" L-UP]
   [1580 1660 "check-fix round" ["a failed check: one build round" "from the moved main"] "retry" RIGHT]
   [1780 R4 "req done" ["the main session marks the kept :ID:s" "once the check passed, or there is none"] "done" L-DN]])

(defn ant? [nm] (str/includes? (str/lower-case nm) " ant"))

(defn hexm [x y r fill stroke sw]
  (let [pts (str/join " " (for [[dx dy] [[-1 0] [-0.5 -0.87] [0.5 -0.87] [1 0] [0.5 0.87] [-0.5 0.87]]]
                            (format "%.1f,%.1f" (double (+ x (* r dx))) (double (+ y (* r dy))))))]
    (str "<polygon points=\"" pts "\" fill=\"" fill "\" stroke=\"" stroke "\" stroke-width=\"" sw "\"/>")))

(def ICON {"drop" RED "retry" RED "done" GREEN "main" GREEN}) ; icon colour by meaning

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
      (concat (when (str/includes? nm "∥")
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

      (= kind "retry") ; a loop arrow: an open circle with an arrowhead, back to build
      [(str "<circle cx=\"" x "\" cy=\"" y "\" r=\"16\" fill=\"" BG "\"/>"
            "<path d=\"M" (+ x 12) "," (- y 7) " A13,13 0 1 0 " (+ x 13) "," (+ y 3) "\" fill=\"none\" stroke=\"" IC "\" stroke-width=\"4\" stroke-linecap=\"round\"/>"
            "<path d=\"M" (+ x 5) "," (- y 10) " L" (+ x 14) "," (- y 9) " L" (+ x 15) "," (- y 18)
            "\" fill=\"none\" stroke=\"" IC "\" stroke-width=\"4\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>")]

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
             [10 "after" GREEN 5 0] [11 "jfix" GOLD 5 0]])

(defn legend
  "The key box in the bottom right."
  []
  (let [kx 1440 ky 1770
        rows [[BLUE "1" "task on the plan line"] [INDIGO "2-6" "five worker tasks to MAIN"] [GOLD "7-8" "a bug through the fix loop"]
              [GREEN "10" "after main moves"] [GOLD "11" "the judge's fix round, below 7"]]
        ;; right column: each symbol drawn, not typed, so every browser shows the same
        lx (+ kx 360) ly (+ ky 30)
        key (fn [i label] [(txt (+ lx 16) (+ ly (* i 16)) [label] :fill SUB :size 12) (+ lx 6) (+ ly (* i 16) -4)])
        [k2 ax ay] (key 2 "an ant (AI agent)")
        [k3 bx by] (key 3 "back to build")
        [k4 cx cy] (key 4 "dropped")
        [k5 ix iy] (key 5 "interchange")]
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
      k3 (str "<path d=\"M" (+ bx 4.5) "," (- by 3) " A5,5 0 1 0 " (+ bx 5) "," (+ by 1) "\" fill=\"none\" stroke=\"" SUB "\" stroke-width=\"1.5\" stroke-linecap=\"round\"/>"
              "<path d=\"M" (+ bx 2) "," (- by 4) " L" (+ bx 5) "," (- by 3.5) " L" (+ bx 5.5) "," (- by 7)
              "\" fill=\"none\" stroke=\"" SUB "\" stroke-width=\"1.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>")
      k4 (str "<path d=\"M" (- cx 4) "," (- cy 2) " L" (+ cx 4) "," (- cy 2) " L" (+ cx 3) "," (+ cy 6) " L" (- cx 3) "," (+ cy 6)
              " Z\" fill=\"none\" stroke=\"" SUB "\" stroke-width=\"1.5\" stroke-linejoin=\"round\"/>"
              "<line x1=\"" (- cx 5.5) "\" y1=\"" (- cy 4) "\" x2=\"" (+ cx 5.5) "\" y2=\"" (- cy 4) "\" stroke=\"" SUB "\" stroke-width=\"1.5\" stroke-linecap=\"round\"/>"
              "<path d=\"M" (- cx 2) "," (- cy 4) " L" (- cx 2) "," (- cy 6) " L" (+ cx 2) "," (- cy 6) " L" (+ cx 2) "," (- cy 4)
              "\" fill=\"none\" stroke=\"" SUB "\" stroke-width=\"1.2\"/>")
      k5 (str "<circle cx=\"" ix "\" cy=\"" iy "\" r=\"5\" fill=\"none\" stroke=\"" SUB "\" stroke-width=\"1.5\"/>")
      (txt lx (+ ly (* 6 16)) ["stacked ∥: parallel"] :fill SUB :size 12)]
     ;; colour key: what each colour means
     (loop [x (+ kx 16) [[c t] & more] [[GREEN "done"] [RED "failed"] [GOLD "warning"] [BLUE "plan"] [INDIGO "build"]] out []]
       (if-not c
         out
         (recur (+ x 22 (* (count t) 7)) more
                (conj out (str "<circle cx=\"" (+ x 5) "\" cy=\"" (+ ky 136) "\" r=\"5\" fill=\"" c "\"/>")
                      (txt (+ x 14) (+ ky 140) [t] :fill SUB :size 12))))))))

(defn svg []
  (concat
   [(str "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 " W " " H "\" width=\"" W "\" height=\"" H "\" font-family=\"ui-sans-serif,-apple-system,Helvetica,Arial,sans-serif\">")
    "<title>Ishikari metro map, readable</title>"
    "<defs><filter id=\"g\" x=\"-100%\" y=\"-100%\" width=\"300%\" height=\"300%\"><feGaussianBlur stdDeviation=\"3\" result=\"b\"/><feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter></defs>"
    (str "<style>.h{paint-order:stroke;stroke:" BG ";stroke-width:5px;stroke-linejoin:round}.flow{animation:f 1.2s linear infinite}@keyframes f{to{stroke-dashoffset:-32}}</style>")
    (str "<rect width=\"" W "\" height=\"" H "\" fill=\"" BG "\"/>")
    (txt 40 44 ["ISHIKARI METRO"] :size 28 :weight "800")
    (txt 330 44 ["Read it like a page: each row left to right, then wrap to the next row."] :fill SUB :size 15)]
   ;; row bands
   (for [[y label c] [[R1 "1 ASK  ·  2 PLAN" BLUE] [R2 "3 BUILD  ·  4 CHECK  ·  5 FIX" INDIGO]
                      [R3 "6 FINISH: MERGE  ·  CLEANUP" INDIGO] [R4 "6 FINISH: JUDGE  ·  MAIN MOVES" INDIGO]]]
     (txt (- W 30) (if (= y R1) 120 (- y 100)) [label] :fill c :size 13 :anchor "end" :weight "800"))
   (for [[name c pts w dash] lines]
     (str "<path id=\"L-" name "\" d=\"" (d pts) "\" fill=\"none\" stroke=\"" c "\" stroke-width=\"" w "\" stroke-linejoin=\"round\" stroke-linecap=\"round\""
          (when (seq dash) (str " stroke-dasharray=\"" dash "\" class=\"flow\"")) "/>"))
   [(txt (+ X 12) 290 ["to row 2"] :fill BLUE :size 13 :weight "700")
    (txt 262 (- R2 108) ["a plan may run a saved workflow in place of a worker ant"] :fill SUB :size 13 :anchor "middle")
    (txt 480 494 ["built: the script starts" "its detective at once"] :fill INDIGO :size 13 :anchor "middle")
    (txt 240 664 ["bugs: the detective's fix plan goes back to the worker;" "the worker builds it, the detective re-checks; 3 tries per bug"] :fill GOLD :size 13)
    (txt (+ X 12) 700 ["to row 3"] :fill INDIGO :size 13 :weight "700")
    (txt (+ X 12) 1240 ["to row 4"] :fill INDIGO :size 13 :weight "700")
    (txt 1212 690 ["fail: tasks clash: the task takes" "them in, then the fix loop; 2 rounds"] :fill GOLD :size 13)
    (txt 720 (- R4 14) ["7+, or no gaps: no fix round"] :fill GREEN :size 13 :anchor "middle" :weight "700")
    (txt 440 1612 ["below 7 and gaps: one fix round"] :fill GOLD :size 13 :anchor "end" :weight "700")
    (txt 740 1720 ["a failed fix keeps its branch;" "the verdict says why"] :fill RED :size 13 :anchor "middle")]
   (mapcat (fn [[x y nm sub kind [dx dy an]]]
             (concat (icon x y nm kind)
                     [(txt (+ x dx) (+ y dy) [nm] :size 16 :anchor an :weight "700")
                      (txt (+ x dx) (+ y dy 19) sub :fill SUB :size 13 :anchor an :lh 16)]))
           stations)
   (for [[n path c sec beg] trains]
     (str "<g filter=\"url(#g)\"><rect x=\"-14\" y=\"-11\" width=\"28\" height=\"22\" rx=\"6\" fill=\"" CAR "\" stroke=\"" c "\" stroke-width=\"3\"/>"
          "<text y=\"5\" font-size=\"14\" font-weight=\"800\" fill=\"" BG "\" text-anchor=\"middle\">" n "</text>"
          "<animateMotion dur=\"" sec "s\" begin=\"" (- beg) "s\" repeatCount=\"indefinite\"><mpath href=\"#L-" path "\"/></animateMotion></g>"))
   (for [[path sec] [["ask" 6] ["res" 5]]]
     (str "<circle r=\"7\" fill=\"" CAR "\" filter=\"url(#g)\"><animateMotion dur=\"" sec "s\" repeatCount=\"indefinite\" keyPoints=\"0;1;0\" keyTimes=\"0;0.5;1\" calcMode=\"linear\"><mpath href=\"#L-" path "\"/></animateMotion></circle>"))
   (legend)
   ["</svg>"]))

(let [out (or (first *command-line-args*)
              (str (fs/path (fs/parent (fs/absolutize *file*)) "ishikari-metro.svg")))]
  (spit out (str/join "\n" (svg))))
