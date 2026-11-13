(ns demo.time-picker-check
  "The window checks of Time pickers, in requirements/components.org. Opens the
  real window, behind whatever is in front, and sends it mouse, key and scroll
  events through the scene, which picks what is under each as it does for a
  real pointer; nothing moves the pointer and nothing takes the keyboard.

      clojure -M:check-time-picker"
  (:require [cljfx.api :as fx]
            [demo.time-picker :as t]
            [demo.time-picker-page :as p]
            [demo.ui :as ui])
  (:import [javafx.animation AnimationTimer]
           [javafx.application Platform]
           [javafx.css PseudoClass]
           [javafx.event Event EventHandler]
           [javafx.geometry Bounds Rectangle2D]
           [javafx.scene AccessibleAttribute AccessibleRole Cursor Node Parent Scene SnapshotParameters]
           [javafx.scene.control Label ScrollPane TextField Tooltip]
           [javafx.scene.input KeyCode KeyEvent MouseButton MouseEvent ScrollEvent
            ScrollEvent$HorizontalTextScrollUnits ScrollEvent$VerticalTextScrollUnits]
           [javafx.scene.layout Region]
           [javafx.scene.paint Color]
           [javafx.scene.text Text]
           [javafx.stage Window]
           [com.sun.javafx.scene SceneHelper]))

;; The whole run, in seconds: over it, the checks stop and say so.
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

;; The list of a picker: there only while it is open or fading.
(defn- lst ^Parent [id] (node (str id "-list")))

(defn- open? [id]
  (boolean (when-let [l (lst id)] (on-fx #(and (= 1.0 (.getOpacity l)) (not (.isMouseTransparent l)))))))

(defn- port ^Region [id]
  (when-let [l (lst id)] (on-fx #(first (.getChildrenUnmodifiable l)))))

(defn- rows
  "The list's rows, top to bottom."
  [id]
  (when-let [^Parent pt (port id)]
    (on-fx #(vec (.getChildrenUnmodifiable ^Parent (first (.getChildrenUnmodifiable pt)))))))

(defn- words [id] (mapv (fn [^Label l] (on-fx #(.getText l))) (rows id)))

(defn- marked
  "Which row is marked, or nil."
  [id]
  (first (keep-indexed (fn [i ^Node l] (when (on-fx #(.contains (.getPseudoClassStates l) t/marked)) i))
                       (rows id))))

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
  (on-fx #(first (.getChildrenUnmodifiable (.getParent f)))))

(defn- spoken-name
  "A field's name, as a screen reader is given it: what its label says."
  [^Node f]
  (let [l (label-of f)]
    (on-fx #(when (identical? f (.getLabelFor l)) (.getAccessibleText l)))))

(defn- whole [x] (Math/round (double x)))

(defn- luminance [^Color c]
  (let [lin #(if (<= % 0.03928) (/ % 12.92) (Math/pow (/ (+ % 0.055) 1.055) 2.4))]
    (+ (* 0.2126 (lin (.getRed c))) (* 0.7152 (lin (.getGreen c))) (* 0.0722 (lin (.getBlue c))))))

(defn- contrast
  "The lowest contrast between a row's words and what is drawn behind them:
  the row is drawn without its words, and the middle of it is read."
  [^Label lbl]
  (on-fx
    (fn []
      (let [text (luminance (.getTextFill lbl))
            ^Node glyphs (.lookup lbl ".text")
            b (.localToScene lbl (.getLayoutBounds lbl))
            x (+ (.getMinX b) 8) y (+ (.getMinY b) (* 0.25 (.getHeight b)))
            w (- (.getWidth b) 16) h (* 0.5 (.getHeight b))]
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
  ;; The clock stands at 10:00 for the whole run.
  (reset! p/*state (assoc p/start-state :now 600))
  (fx/mount-renderer p/*state p/renderer)
  (wait 1500)
  (let [s ^TextField (node "starts")
        e ^TextField (node "ends")
        r ^TextField (node "reminder")
        page ^ScrollPane (node "page")
        state #(deref p/*state)
        time-of #(get-in (state) [:times %])
        writes #(:writes (state))
        focus! (fn [^Node n] (on-fx #(.requestFocus n)) (wait 150))
        owner #(on-fx (fn [] (.getFocusOwner (scene))))
        ;; Types, and takes it with Return.
        enter! (fn [typed] (type! typed) (tap! KeyCode/ENTER) (wait 200))
        ;; Closes the list and puts the old time back.
        back! (fn [] (tap! KeyCode/ESCAPE) (tap! KeyCode/ESCAPE) (wait 300))
        fresh! (fn [& {:as more}]
                 (swap! p/*state merge
                        (select-keys p/start-state [:times :remind :writes :undo :h24 :drop]) more)
                 (wait 400))]

    (println "Typing sets the time")
    (focus! s)
    (check "focus selects all of the field's text" "9:30 AM" (on-fx #(.getSelectedText s)))
    (doseq [[typed shown minutes] [["9a" "9:00 AM" 540]
                                   ["930a" "9:30 AM" 570]
                                   ["9:30 am" "9:30 AM" 570]
                                   ["9.30p" "9:30 PM" 1290]
                                   ["9p" "9:00 PM" 1260]
                                   ["2130" "9:30 PM" 1290]
                                   ["21:30" "9:30 PM" 1290]
                                   ["noon" "12:00 PM, noon" 720]
                                   ["midnight" "12:00 AM, midnight" 0]]]
      (enter! typed)
      (check (str "\"" typed "\"") [shown minutes] [(text s) (time-of :starts)]))

    (println "An hour with no AM or PM is never guessed at")
    (let [before (writes)]
      (doseq [typed ["3" "3:30"]]
        (enter! typed)
        (check (str "\"" typed "\": the text stays, a red edge, the line asks, nothing written")
               [typed red "AM or PM? Type 3a or 3p" before 0]
               [(text s) (edge s) (line "starts") (writes) (time-of :starts)])
        (back!)))
    (let [before (writes)]
      (on-fx #(.selectAll s))
      (tap! KeyCode/BACK_SPACE)
      (tap! KeyCode/ENTER)
      (wait 200)
      (check "emptied, a field that is not optional says so, and nothing is written"
             ["" "Not a time. Try 9:30 or 2130" before] [(text s) (line "starts") (writes)])
      (back!))
    (enter! "13")
    (check "\"13\" stands on the 24-hour clock" ["1:00 PM" 780] [(text s) (time-of :starts)])
    (enter! "0")
    (check "\"0\" is midnight" ["12:00 AM, midnight" 0] [(text s) (time-of :starts)])

    (println "The time is written when it is taken")
    (let [before (writes)]
      (type! "8a")
      (wait 100)
      (check "nothing is written while it is typed" [0 before] [(time-of :starts) (writes)])
      (tap! KeyCode/ENTER)
      (wait 200)
      (check "Return writes it, once" [480 (inc before)] [(time-of :starts) (writes)])
      (enter! "8a")
      (check "taking the time it already had writes nothing" [480 (inc before)] [(time-of :starts) (writes)]))

    (println "What is not a time")
    (let [before (writes)]
      (enter! "abc")
      (check "\"abc\": the text stays, a red edge, the line says so, nothing written"
             ["abc" red "Not a time. Try 9:30 or 2130" before]
             [(text s) (edge s) (line "starts") (writes)])
      (check "and a screen reader hears it, in the name" "Starts. Not a time. Try 9:30 or 2130"
             (spoken-name s))
      (type! "1")
      (wait 300)
      (check "typing again clears the red edge and the line" [false nil] [(= red (edge s)) (line "starts")])
      (back!)
      (check "Escape puts the old time back" ["8:00 AM" before] [(text s) (writes)]))

    (println "Escape")
    (let [before (writes)]
      (type! "4p")
      (wait 300)
      (check "typing opens the list" true (open? "starts"))
      (tap! KeyCode/ESCAPE)
      (wait 300)
      (check "Escape closes the list and leaves the typed text" [nil "4p"] [(lst "starts") (text s)])
      (tap! KeyCode/ESCAPE)
      (wait 200)
      (check "a second Escape puts the field back, and writes nothing" ["8:00 AM" 480 before]
             [(text s) (time-of :starts) (writes)]))

    (println "A click elsewhere")
    (type! "6p")
    (click! (centre (node "writes")))
    (wait 300)
    (check "takes what is typed" ["6:00 PM" 1080 nil] [(text s) (time-of :starts) (lst "starts")])

    (println "The list")
    (click! (centre s))
    (wait 300)
    (check "a click in the field opens it" true (open? "starts"))
    (check "eight rows to be seen" (* t/rows-seen t/row-h) (on-fx #(.getHeight (port "starts"))))
    (check "it holds the day in 15 minute steps" 96 (count (rows "starts")))
    (let [i (marked "starts")
          row (nth (rows "starts") i)]
      (check "the field's time is marked" "6:00 PM" (on-fx #(.getText ^Label row)))
      (check "and in the middle" (whole (second (centre (port "starts")))) (whole (second (centre row)))))
    (let [[_ _ _ field-bottom] (bounds s)
          [_ list-top _ _] (bounds (lst "starts"))]
      (check "it is under the field, 4 px from it" t/gap (- list-top field-bottom)))
    (tap! KeyCode/ESCAPE)
    (wait 300)
    (check "Escape closes it" nil (lst "starts"))
    (tap! KeyCode/TAB)
    (wait 300)
    (check "Tab goes to the next field, and opens no list" [true nil] [(identical? e (owner)) (lst "ends")])
    (tap! KeyCode/DOWN)
    (wait 300)
    (check "Down opens it" true (open? "ends"))
    (check "from an empty field, the step after now is marked" "10:15 AM"
           (nth (words "ends") (marked "ends")))
    (tap! KeyCode/ESCAPE)
    (wait 300)

    (println "Typing narrows the list")
    (focus! s)
    (type! "2")
    (wait 300)
    (check "\"2\": 2:00 PM first, eight rows, none marked" ["2:00 PM" 8 nil]
           [(first (words "starts")) (count (rows "starts")) (marked "starts")])
    (check "both halves of the day" ["2:00 PM" "2:15 PM" "2:30 PM" "2:45 PM" "2:00 AM" "2:15 AM" "2:30 AM" "2:45 AM"]
           (words "starts"))
    (tap! KeyCode/UP)
    (check "Up with no row marked marks the last" 7 (marked "starts"))
    (back!)
    (type! "2")
    (wait 300)
    (dotimes [_ 3] (tap! KeyCode/DOWN))
    (check "Down three times marks the third row" 2 (marked "starts"))
    (check "and a screen reader is sent to it" "2:30 PM"
           (on-fx #(.getText ^Label (.queryAccessibleAttribute s AccessibleAttribute/FOCUS_ITEM (object-array 0)))))
    (tap! KeyCode/ENTER)
    (wait 300)
    (check "Return takes the marked row" ["2:30 PM" 870 nil] [(text s) (time-of :starts) (lst "starts")])
    (type! "207p")
    (wait 300)
    (check "\"207p\": 2:07 PM first, and marked" ["2:07 PM" 0] [(first (words "starts")) (marked "starts")])
    (back!)
    (type! "12")
    (wait 300)
    (check "twelve is shown with its word in the list"
           ["12:00 PM, noon" "12:00 AM, midnight"] [(nth (words "starts") 0) (nth (words "starts") 4)])
    (back!)

    (println "A click takes a row")
    (click! (centre s))
    (wait 300)
    (let [row (nth (rows "starts") (inc (marked "starts")))]
      (click! (centre row))
      (wait 300)
      (check "the row under the click" ["2:45 PM" 885 nil] [(text s) (time-of :starts) (lst "starts")]))

    (println "The window's edge, and scrolling")
    (let [[_ top _ _] (bounds s)
          height (on-fx #(.getHeight (scene)))]
      (swap! p/*state assoc :drop (long (- height 12 t/field-h top)))
      (wait 400)
      (click! (centre s))
      (wait 300)
      (let [[l t r b] (bounds (lst "starts"))
            [_ field-top _ _] (bounds s)]
        (check "with no room under the field, the list opens over it" true (<= b field-top))
        (check "and stays whole, inside the window" true
               (and (>= l t/edge-gap) (>= t t/edge-gap) (<= r (on-fx #(.getWidth (scene)))) (<= b height))))
      (let [first-row (first (rows "starts"))
            [_ before _ _] (bounds first-row)]
        (scroll! (centre (lst "starts")) -40.0)
        (wait 200)
        (check "scrolling over the open list scrolls the list" -40.0 (- (second (bounds first-row)) before))
        (check "and not the page" 0.0 (on-fx #(.getVvalue page))))
      (tap! KeyCode/ESCAPE)
      (wait 300)
      (scroll! (centre s) -40.0)
      (wait 200)
      (check "scrolling over the field alone scrolls the page" true (pos? (double (on-fx #(.getVvalue page)))))
      (check "and the time does not change" ["2:45 PM" 885] [(text s) (time-of :starts)])
      (on-fx #(.setVvalue page 0.0)))

    (println "A 24-hour clock")
    (fresh! :h24 true)
    (check "the field shows it" "09:30" (text s))
    (focus! s)
    (enter! "9p")
    (check "\"9p\"" ["21:00" 1260] [(text s) (time-of :starts)])
    (enter! "3")
    (check "an hour alone is taken as it stands" ["03:00" 180] [(text s) (time-of :starts)])

    (println "A field that may be empty")
    (fresh!)
    (focus! e)
    (enter! "5p")
    (check "a time is taken" ["5:00 PM" 1020] [(text e) (time-of :ends)])
    (let [before (writes)]
      (tap! KeyCode/BACK_SPACE)
      (tap! KeyCode/ENTER)
      (wait 200)
      (check "emptied, no time is written" ["" nil (inc before)] [(text e) (time-of :ends) (writes)]))
    (focus! s)
    (check "it shows a hint" "9:30 AM" (on-fx #(.getPromptText e)))
    (check "in grey" (Color/color 1.0 1.0 1.0 0.45)
           (on-fx #(some (fn [^Node n] (when (and (instance? Text n) (= "9:30 AM" (.getText ^Text n)))
                                         (.getFill ^Text n)))
                         (.lookupAll e ".text"))))

    (println "Undo")
    (fresh!)
    (focus! s)
    (enter! "7a")
    (check "one taken time is one step" [420 1] [(time-of :starts) (count (:undo (state)))])
    (tap! KeyCode/Z :shortcut true)
    (wait 300)
    (check "Undo: the time from before, in the field too" ["9:30 AM" 570] [(text s) (time-of :starts)])

    (println "Disabled")
    (focus! (node "remind"))
    (check "disabled, at 45% opacity" [true 0.45] (on-fx #(vector (.isDisabled r) (.getOpacity r))))
    (let [before (writes)]
      (click! (centre r))
      (type! "5p")
      (wait 300)
      (check "it answers no click and no key, and opens no list" ["9:00 AM" 540 nil before]
             [(text r) (time-of :reminder) (lst "reminder") (writes)]))

    (println "States, sizes and the screen reader")
    (check "its height is that of a button" t/field-h (on-fx #(.getHeight s)))
    (check "120 px wide or wider" true (>= (double (on-fx #(.getWidth s))) t/min-width))
    (check "over the field the pointer is a text cursor" Cursor/TEXT (on-fx #(.getCursor s)))
    (pseudo! s "focus-visible" true)
    (wait 300)
    (check "on keyboard focus, a ring in the accent colour" (Color/web "#4aa3ff") (edge s))
    (pseudo! s "focus-visible" false)
    (check "each has a label that names it" ["Starts" "Ends" "Reminder"]
           (mapv #(let [l (label-of %)] (on-fx (fn [] (.getText l)))) [s e r]))
    (check "a disabled time picker's tooltip says why" "Off: tick Remind me to set a time."
           (on-fx #(some-> ^Tooltip (.get (.getProperties (.getParent r)) "javafx.scene.control.Tooltip")
                           .getText)))
    (check "each is a text field to a screen reader" (repeat 3 AccessibleRole/TEXT_FIELD)
           (on-fx #(mapv (fn [^Node n] (.getAccessibleRole n)) [s e r])))
    (check "an empty field is given as empty, not as its hint" ""
           (on-fx #(.queryAccessibleAttribute e AccessibleAttribute/TEXT (object-array 0))))
    (let [spoken #(vector (spoken-name s)
                          (on-fx (fn [] (.queryAccessibleAttribute s AccessibleAttribute/TEXT (object-array 0)))))]
      (check "its name is what it sets, and its value the time as shown" ["Starts" "9:30 AM"] (spoken))
      (focus! s)
      (enter! "10a")
      (check "after a change: the same name, the new time" ["Starts" "10:00 AM"] (spoken)))
    (check "off, it is called dimmed and says why, in its name"
           ["Reminder. Off: tick Remind me to set a time." "dimmed text field"]
           [(spoken-name r) (on-fx #(.getAccessibleRoleDescription r))])

    (println "The list's words")
    (click! (centre s))
    (wait 300)
    (let [i (marked "starts")]
      (doseq [[what row] [["the marked row" (nth (rows "starts") i)]
                          ["a plain row" (nth (rows "starts") (inc i))]]]
        (let [ratio (contrast row)]
          (check (str "contrast on " what ": 4.5 or more (" (format "%.1f" ratio) ")") true (>= ratio 4.5)))))
    (tap! KeyCode/ESCAPE)
    (wait 300)

    (println "Frames")
    (let [{:keys [fps slowest-ms]}
          (frames (fn []
                    (dotimes [_ 3]
                      (click! (centre s))
                      (wait 400)
                      (tap! KeyCode/ESCAPE)
                      (wait 400))))]
      (check (str "55 frames a second or more through three openings of the list ("
                  (format "%.1f" fps) ", slowest frame " (format "%.1f" slowest-ms) " ms)")
             true (>= fps 55.0)))

    (println "The fade, and Reduce Motion")
    (click! (centre s))
    (wait 40)
    (check "40 ms on, the list is fading in" true (< 0.0 (double (on-fx #(.getOpacity (lst "starts")))) 1.0))
    (tap! KeyCode/ESCAPE)
    (wait 300)
    (reset! ui/*reduce true)
    (click! (centre s))
    (wait 20)
    (check "with Reduce Motion on, 20 ms on it is fully there" 1.0 (on-fx #(.getOpacity (lst "starts")))))
  (println (if (zero? @failures) "All checks passed." (str @failures " checks failed.")))
  (System/exit (if (zero? @failures) 0 1)))
