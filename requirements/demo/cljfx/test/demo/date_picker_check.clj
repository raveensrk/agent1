(ns demo.date-picker-check
  "The window checks of Date pickers, in requirements/components.org. Opens the
  real window, behind whatever is in front, and sends it mouse, key and scroll
  events through the scene, which picks what is under each as it does for a
  real pointer; nothing moves the pointer and nothing takes the keyboard.

      clojure -M:check-date-picker"
  (:require [cljfx.api :as fx]
            [demo.date-picker :as d]
            [demo.date-picker-page :as p]
            [demo.ui :as ui])
  (:import [java.time DayOfWeek LocalDate]
           [java.util Locale]
           [javafx.animation AnimationTimer]
           [javafx.application Platform]
           [javafx.css PseudoClass]
           [javafx.event Event EventHandler]
           [javafx.geometry Bounds Rectangle2D]
           [javafx.scene Cursor Node Parent Scene SnapshotParameters]
           [javafx.scene.control Label ScrollPane TextField Tooltip]
           [javafx.scene.input KeyCode KeyEvent MouseButton MouseEvent ScrollEvent
            ScrollEvent$HorizontalTextScrollUnits ScrollEvent$VerticalTextScrollUnits]
           [javafx.scene.layout Region]
           [javafx.scene.paint Color]
           [javafx.stage Window]
           [com.sun.javafx.scene SceneHelper]))

(def timeout-s 120)

(defn- on-fx
  "Runs `f` on the UI thread and waits for it; already there, it runs at once."
  [f]
  (if (Platform/isFxApplicationThread)
    (f)
    (let [p (promise)]
      (Platform/runLater #(deliver p (try (f) (catch Throwable t t))))
      (deref p 5000 :timeout))))

(defn- scene ^Scene [] (.getScene ^Window (first (Window/getWindows))))

(defn- node ^Node [id] (on-fx #(.lookup (.getRoot (scene)) (str "#" id))))

(defn- mouse-event [type x y clicks]
  (MouseEvent. type x y x y MouseButton/PRIMARY (int clicks)
               false false false false
               (boolean (#{MouseEvent/MOUSE_PRESSED MouseEvent/MOUSE_DRAGGED} type)) false false
               false false false nil))

(defn- pointer!
  "One mouse event at a place in the window, sent the way a real pointer's is:
  the scene picks what is under it. The pointer is not moved."
  [type [x y]]
  (on-fx #(SceneHelper/processMouseEvent (scene) (mouse-event type (double x) (double y) 1))))

(defn- click! [place]
  (pointer! MouseEvent/MOUSE_PRESSED place)
  (pointer! MouseEvent/MOUSE_RELEASED place))

(defn- key!
  "A key, sent to the scene as a real one is: whatever has the focus gets it."
  [type ^KeyCode code & {:keys [shortcut]}]
  (on-fx #(SceneHelper/processKeyEvent
            (scene) (KeyEvent. type "" "" code false false false (boolean shortcut)))))

(defn- tap! [code & opts]
  (apply key! KeyEvent/KEY_PRESSED code opts)
  (apply key! KeyEvent/KEY_RELEASED code opts))

(defn- type!
  "Text, typed a key at a time into whatever has the focus."
  [text]
  (doseq [c text]
    (on-fx #(SceneHelper/processKeyEvent
              (scene) (KeyEvent. KeyEvent/KEY_TYPED (str c) "" KeyCode/UNDEFINED false false false false)))))

(defn- scroll!
  "A scroll at a place in the window, given to whatever the scene picks there."
  [[x y] dy]
  (on-fx #(let [seen (atom nil)
                see (reify EventHandler (handle [_ e] (reset! seen (.getTarget ^Event e))))]
            (.addEventFilter (scene) MouseEvent/MOUSE_MOVED see)
            (SceneHelper/processMouseEvent (scene) (mouse-event MouseEvent/MOUSE_MOVED (double x) (double y) 0))
            (.removeEventFilter (scene) MouseEvent/MOUSE_MOVED see)
            (Event/fireEvent @seen
                             (ScrollEvent. ScrollEvent/SCROLL x y x y false false false false false false
                                           0.0 dy 0.0 dy
                                           ScrollEvent$HorizontalTextScrollUnits/NONE 0.0
                                           ScrollEvent$VerticalTextScrollUnits/NONE 0.0 0 nil)))))

;;; What the window shows

(defn- bounds
  "Where a node is in the window: [left top right bottom]."
  [^Node n]
  (on-fx #(let [^Bounds b (.localToScene n (.getLayoutBounds n))]
            [(.getMinX b) (.getMinY b) (.getMaxX b) (.getMaxY b)])))

(defn- centre [n]
  (let [[l t r b] (bounds n)]
    [(/ (+ l r) 2.0) (/ (+ t b) 2.0)]))

(defn- text [^TextField f] (on-fx #(.getText f)))

;; The calendar of a picker: there only while it is open or fading.
(defn- cal ^Parent [id] (node (str id "-calendar")))

(defn- open? [id]
  (boolean (when-let [l (cal id)] (on-fx #(and (= 1.0 (.getOpacity l)) (not (.isMouseTransparent l)))))))

(defn- day ^Label [id ^LocalDate d] (node (str id "-day-" d)))

(defn- has? [^Node n state] (on-fx #(.contains (.getPseudoClassStates n) (PseudoClass/getPseudoClass state))))

(defn- marked-day
  "The day the calendar marks, or nil."
  [id]
  (when-let [c (cal id)]
    (on-fx #(some (fn [^Node n] (when (.contains (.getPseudoClassStates n) d/marked)
                                  (LocalDate/parse (subs (.getId n) (+ 5 (count id))))))
                  (.lookupAll c ".date-day")))))

(defn- first-weekday [id]
  (on-fx #(.getText ^Label (first (.lookupAll (cal id) ".date-weekday")))))

(defn- line
  "The line under a field, or nil when it shows none."
  [id]
  (let [^Label l (node (str id "-line"))]
    (on-fx #(when (.isVisible l) (.getText l)))))

(defn- edge
  "The colour of a field's edge."
  [^Region f]
  (on-fx #(.getTopStroke (first (.getStrokes (.getBorder f))))))

(def red (Color/web "#ff6b60"))

(defn- label-of
  "The label that names a field: the first thing in its box."
  ^Label [^Node f]
  (on-fx #(first (.getChildrenUnmodifiable (.getParent (.getParent f))))))

(defn- whole [x] (Math/round (double x)))

(defn- luminance [^Color c]
  (let [lin #(if (<= % 0.03928) (/ % 12.92) (Math/pow (/ (+ % 0.055) 1.055) 2.4))]
    (+ (* 0.2126 (lin (.getRed c))) (* 0.7152 (lin (.getGreen c))) (* 0.0722 (lin (.getBlue c))))))

(defn- contrast
  "The lowest contrast between a row's words and what is drawn behind them:
  the row is drawn without its words, and the middle of it is read."
  [^Label lbl & {:keys [inset] :or {inset 8}}]
  (on-fx
    (fn []
      (let [text (luminance (.getTextFill lbl))
            ^Node glyphs (.lookup lbl ".text")
            b (.localToScene lbl (.getLayoutBounds lbl))
            x (+ (.getMinX b) inset) y (+ (.getMinY b) (* 0.25 (.getHeight b)))
            w (- (.getWidth b) (* 2 inset)) h (* 0.5 (.getHeight b))]
        (.setOpacity glyphs 0.0)
        (let [img (.snapshot (.getRoot (.getScene lbl))
                             (doto (SnapshotParameters.) (.setViewport (Rectangle2D. x y w h))) nil)
              reader (.getPixelReader img)
              worst (apply min (for [px (range (int (.getWidth img))) py (range (int (.getHeight img)))
                                     :let [bg (luminance (.getColor reader px py))]]
                                 (/ (+ 0.05 (max text bg)) (+ 0.05 (min text bg)))))]
          (.setOpacity glyphs 1.0)
          worst)))))

(def failures (atom 0))

(defn- check [what expected actual]
  (let [ok (= expected actual)]
    (when-not ok (swap! failures inc))
    (println (if ok "ok  " "FAIL") what "- expected" expected "got" actual)))

(defn- frames
  "Runs `f` while counting the window's frames. Returns the frames a second it
  kept up, and its slowest frame in ms."
  [f]
  (let [times (atom [])
        timer (proxy [AnimationTimer] [] (handle [now] (swap! times conj now)))]
    (on-fx #(.start timer))
    (f)
    (on-fx #(.stop timer))
    (let [gaps (map - (rest @times) @times)]
      {:fps (/ (count gaps) (/ (reduce + gaps) 1e9))
       :slowest-ms (/ (apply max gaps) 1e6)})))

(defn- pseudo! [^Node n state on]
  (on-fx #(.pseudoClassStateChanged n (PseudoClass/getPseudoClass state) on)))

(defn- wait [ms] (Thread/sleep (long ms)))

(defn -main [& _]
  (future (Thread/sleep (* 1000 (long timeout-s)))
          (println "timeout: the checks ran over" timeout-s "s")
          (System/exit 2))
  (reset! ui/*follow-system false)
  (reset! ui/*reduce false)
  ;; Today is Sunday 15 Nov 2026 for the whole run, in a British region whose
  ;; week starts on Sunday.
  (let [today (LocalDate/of 2026 11 15)
        on (fn [m dd] (LocalDate/of 2026 (int m) (int dd)))
        base (assoc p/start-state :today today :locale Locale/UK :first-day DayOfWeek/SUNDAY)]
    (reset! p/*state base)
    (fx/mount-renderer p/*state p/renderer)
    (wait 1500)
    (let [s ^TextField (node "starts")
          e ^TextField (node "ends")
          r ^TextField (node "reminder")
          state #(deref p/*state)
          date-of #(get-in (state) [:dates %])
          writes #(:writes (state))
          focus! (fn [^Node n] (on-fx #(.requestFocus n)) (wait 150))
          enter! (fn [typed] (type! typed) (tap! KeyCode/ENTER) (wait 200))
          back! (fn [] (tap! KeyCode/ESCAPE) (tap! KeyCode/ESCAPE) (wait 300))
          esc! (fn [] (tap! KeyCode/ESCAPE) (wait 300))
          fresh! (fn [& {:as more}]
                   (swap! p/*state merge (select-keys base [:dates :remind :writes :undo :drop :first-day]) more)
                   (wait 400))]

      (println "Typing sets the date")
      (focus! s)
      (check "focus selects all of the field's text" "Fri, 20 Nov 2026" (on-fx #(.getSelectedText s)))
      (doseq [[typed shown date] [["2 dec" "Wed, 2 Dec 2026" (on 12 2)]
                                  ["nov 21" "Sat, 21 Nov 2026" (on 11 21)]
                                  ["20 November 2026" "Fri, 20 Nov 2026" (on 11 20)]
                                  ["2026-11-25" "Wed, 25 Nov 2026" (on 11 25)]
                                  ["24/11/2026" "Tue, 24 Nov 2026" (on 11 24)]]]
        (enter! typed)
        (check (str "\"" typed "\"") [shown date] [(text s) (date-of :starts)]))
      (let [before (writes)]
        (enter! "20 nov")
        (check "\"20 nov\" and Return: the date in full, written once"
               ["Fri, 20 Nov 2026" (on 11 20) (inc before)] [(text s) (date-of :starts) (writes)])
        (type! "22 nov")
        (wait 100)
        (check "nothing is written while it is typed" [(on 11 20) (inc before)] [(date-of :starts) (writes)])
        (back!)
        (enter! "20 nov")
        (check "taking the date it already had writes nothing" (inc before) (writes)))

      (println "What is not a date")
      (let [before (writes)]
        (enter! "31 Nov")
        (check "\"31 Nov\": the text stays, a red edge, the line says so, nothing written"
               ["31 Nov" red "Not a date. Try 20 Nov or 2026-11-20" before]
               [(text s) (edge s) (line "starts") (writes)])
        (type! "1")
        (wait 300)
        (check "typing again clears the red edge and the line" [false nil] [(= red (edge s)) (line "starts")])
        (back!)
        (check "Escape puts the old date back" ["Fri, 20 Nov 2026" before] [(text s) (writes)])
        (on-fx #(.selectAll s))
        (tap! KeyCode/BACK_SPACE)
        (tap! KeyCode/ENTER)
        (wait 200)
        (check "emptied, a field that is not optional says so, and nothing is written"
               ["" "Not a date. Try 20 Nov or 2026-11-20" before] [(text s) (line "starts") (writes)])
        (back!))

      (println "The calendar")
      (click! (centre s))
      (wait 300)
      (check "a click in the field opens it, on the field's month" [true "November 2026"]
             [(open? "starts") (on-fx #(.getText ^Label (node "starts-month")))])
      (check "the field's day is marked, today is ringed" [(on 11 20) true]
             [(marked-day "starts") (has? (day "starts" today) "today")])
      (check "the week starts on the region's day: Sunday" "S" (first-weekday "starts"))
      (check "six weeks at most" true (<= (count (on-fx #(.lookupAll (cal "starts") ".date-day"))) 42))
      (let [[_ _ _ field-bottom] (bounds s)
            [_ top _ _] (bounds (cal "starts"))]
        (check "it is under the field, 4 px from it" d/gap (- top field-bottom)))
      (tap! KeyCode/RIGHT)
      (tap! KeyCode/DOWN)
      (check "Right and Down move the mark a day and a week" (on 11 28) (marked-day "starts"))
      (tap! KeyCode/ENTER)
      (wait 300)
      (check "Return takes the marked day, eight days on" [(on 11 28) "Sat, 28 Nov 2026" nil]
             [(date-of :starts) (text s) (cal "starts")])
      (tap! KeyCode/DOWN)
      (wait 300)
      (check "Down opens it" true (open? "starts"))
      (tap! KeyCode/PAGE_DOWN)
      (check "Page Down shows the next month" "December 2026" (on-fx #(.getText ^Label (node "starts-month"))))
      (let [dimmed (day "starts" (on 11 29))]
        (check "a day of the month before is dim" true (has? dimmed "dim"))
        (click! (centre dimmed))
        (wait 300)
        (check "a click on a dim day takes it" [(on 11 29) nil] [(date-of :starts) (cal "starts")]))
      (click! (centre (node "starts-mark")))
      (wait 300)
      (check "a click on the calendar mark opens it" true (open? "starts"))
      (click! (centre (node "starts-next")))
      (wait 100)
      (check "› goes a month on" "December 2026" (on-fx #(.getText ^Label (node "starts-month"))))
      (click! (centre (node "starts-prev")))
      (click! (centre (node "starts-prev")))
      (wait 100)
      (check "‹ goes a month back" "October 2026" (on-fx #(.getText ^Label (node "starts-month"))))
      (click! (centre (node "starts-today")))
      (wait 300)
      (check "Today marks and takes today, and closes the calendar" [today "Sun, 15 Nov 2026" nil]
             [(date-of :starts) (text s) (cal "starts")])
      (tap! KeyCode/TAB)
      (wait 300)
      (check "Tab into a field opens no calendar" nil (cal "ends"))

      (println "Escape")
      (focus! s)
      (let [before (writes)]
        (type! "3 dec")
        (tap! KeyCode/DOWN)
        (wait 300)
        (check "an open calendar follows what is typed" (on 12 3) (marked-day "starts"))
        (esc!)
        (check "Escape closes the calendar and leaves the typed text" [nil "3 dec"] [(cal "starts") (text s)])
        (esc!)
        (check "a second Escape puts the field back, and writes nothing" ["Sun, 15 Nov 2026" before]
               [(text s) (writes)]))

      (println "A click elsewhere")
      (type! "1 dec")
      (click! (centre (node "writes")))
      (wait 300)
      (check "takes what is typed" ["Tue, 1 Dec 2026" (on 12 1)] [(text s) (date-of :starts)])

      (println "The window's edge")
      (let [[_ top _ _] (bounds s)
            height (on-fx #(.getHeight (scene)))]
        (swap! p/*state assoc :drop (long (- height 12 d/field-h top)))
        (wait 400)
        (click! (centre s))
        (wait 300)
        (let [[l t rr b] (bounds (cal "starts"))
              [_ field-top _ _] (bounds s)]
          (check "with no room under the field, the calendar opens over it" true (<= b field-top))
          (check "and stays whole, inside the window" true
                 (and (>= l d/edge-gap) (>= t d/edge-gap) (<= rr (on-fx #(.getWidth (scene)))) (<= b height))))
        (esc!))

      (println "A Monday-first region")
      (fresh! :first-day DayOfWeek/MONDAY)
      (click! (centre s))
      (wait 300)
      (check "the first weekday column is Monday" ["M" (on 10 26)]
             [(first-weekday "starts")
              (on-fx #(LocalDate/parse (subs (.getId ^Node (first (.lookupAll (cal "starts") ".date-day"))) 11)))])
      (esc!)

      (println "A field that may be empty")
      (fresh!)
      (focus! e)
      (enter! "5 dec")
      (check "a date is taken" (on 12 5) (date-of :ends))
      (let [before (writes)]
        (tap! KeyCode/BACK_SPACE)
        (tap! KeyCode/ENTER)
        (wait 200)
        (check "emptied, no date is written" ["" nil (inc before)] [(text e) (date-of :ends) (writes)]))
      (check "it shows a hint" "Fri, 20 Nov 2026" (on-fx #(.getPromptText e)))

      (println "Undo")
      (fresh!)
      (focus! s)
      (enter! "7 dec")
      (check "one taken date is one step" [(on 12 7) 1] [(date-of :starts) (count (:undo (state)))])
      (tap! KeyCode/Z :shortcut true)
      (wait 300)
      (check "Undo: the date from before, in the field too" ["Fri, 20 Nov 2026" (on 11 20)]
             [(text s) (date-of :starts)])

      (println "Disabled")
      (focus! (node "remind"))
      (check "disabled, at 45% opacity" [true 0.45] (on-fx #(vector (.isDisabled r) (.getOpacity r))))
      (let [before (writes)]
        (click! (centre r))
        (click! (centre (node "reminder-mark")))
        (type! "5 dec")
        (wait 300)
        (check "it answers no click and no key, and opens no calendar" ["Wed, 18 Nov 2026" nil before]
               [(text r) (cal "reminder") (writes)]))

      (println "States and sizes")
      (check "its height is that of a button" d/field-h (on-fx #(.getHeight s)))
      (check "180 px wide or wider" true (>= (double (on-fx #(.getWidth s))) d/min-width))
      (check "over the field the pointer is a text cursor" Cursor/TEXT (on-fx #(.getCursor s)))
      (check "over the calendar mark it is an arrow" Cursor/DEFAULT (on-fx #(.getCursor (node "starts-mark"))))
      (pseudo! s "focus-visible" true)
      (wait 300)
      (check "on keyboard focus, a ring in the accent colour" (Color/web "#4aa3ff") (edge s))
      (pseudo! s "focus-visible" false)
      (check "each has a label that names it" ["Starts" "Ends" "Reminder"]
             (mapv #(let [l (label-of %)] (on-fx (fn [] (.getText l)))) [s e r]))
      (check "a disabled date picker's tooltip says why" "Off: tick Remind me to set a date."
             (on-fx #(some-> ^Tooltip (.get (.getProperties (.getParent (.getParent r))) "javafx.scene.control.Tooltip")
                             .getText)))

      (println "The calendar's words")
      (focus! s)
      (click! (centre s))
      (wait 300)
      (doseq [[what n] [["the marked day" (day "starts" (on 11 20))]
                        ["a plain day" (day "starts" (on 11 19))]
                        ["a dim day" (day "starts" (on 12 1))]]]
        (let [ratio (contrast n :inset 10)]
          (check (str "contrast on " what ": 4.5 or more (" (format "%.1f" ratio) ")") true (>= ratio 4.5))))
      (esc!)

      (println "Frames")
      (let [{:keys [fps slowest-ms]}
            (frames (fn []
                      (dotimes [_ 3]
                        (click! (centre s))
                        (wait 400)
                        (esc!)
                        (wait 100))))]
        (check (str "55 frames a second or more through three openings of the calendar ("
                    (format "%.1f" fps) ", slowest frame " (format "%.1f" slowest-ms) " ms)")
               true (>= fps 55.0)))

      (println "The fade, and Reduce Motion")
      (click! (centre s))
      (wait 40)
      (check "40 ms on, the calendar is fading in" true (< 0.0 (double (on-fx #(.getOpacity (cal "starts")))) 1.0))
      (esc!)
      (reset! ui/*reduce true)
      (click! (centre s))
      (wait 20)
      (check "with Reduce Motion on, 20 ms on it is fully there" 1.0 (on-fx #(.getOpacity (cal "starts"))))))
  (println (if (zero? @failures) "All checks passed." (str @failures " checks failed.")))
  (System/exit (if (zero? @failures) 0 1)))
