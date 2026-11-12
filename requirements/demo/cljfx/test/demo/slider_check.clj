(ns demo.slider-check
  "The window checks of Sliders, in requirements/components.org. Opens the real
  window, behind whatever is in front, and sends it mouse, key and scroll
  events through the scene, which picks what is under each as it does for a
  real pointer; nothing moves the pointer and nothing takes the keyboard.

      clojure -M:check-slider"
  (:require [cljfx.api :as fx]
            [demo.slider :as s]
            [demo.slider-page :as p]
            [demo.ui :as ui])
  (:import [javafx.animation AnimationTimer]
           [javafx.application Platform]
           [javafx.css PseudoClass]
           [javafx.event Event EventHandler]
           [javafx.geometry Rectangle2D]
           [javafx.scene AccessibleAttribute AccessibleRole Cursor Node Parent Scene SnapshotParameters]
           [javafx.scene.control Label ScrollPane Tooltip]
           [javafx.scene.input KeyCode KeyEvent MouseButton MouseEvent ScrollEvent
            ScrollEvent$HorizontalTextScrollUnits ScrollEvent$VerticalTextScrollUnits]
           [javafx.scene.layout Region]
           [javafx.scene.paint Color]
           [javafx.stage Window]
           [com.sun.javafx.scene SceneHelper]))

;; The whole run, in seconds: over it, the checks stop and say so.
(def timeout-s 120)

(defn- on-fx [f]
  (let [p (promise)]
    (Platform/runLater #(deliver p (try (f) (catch Throwable t t))))
    (deref p 5000 :timeout)))

(defn- scene ^Scene [] (.getScene ^Window (first (Window/getWindows))))

(defn- node ^Node [id] (on-fx #(.lookup (.getRoot (scene)) (str "#" id))))

(defn- mouse-event [type x y clicks]
  (MouseEvent. type x y x y MouseButton/PRIMARY (int clicks)
               false false false false
               (boolean (#{MouseEvent/MOUSE_PRESSED MouseEvent/MOUSE_DRAGGED} type)) false false
               false false false nil))

(defn- pointer!
  "One mouse event at a place in the window, sent the way a real pointer's is:
  the scene picks what is under it. Nothing is sent to a slider directly, so a
  slider that something else covers is found out. The pointer is not moved."
  ([type place] (pointer! type place 1))
  ([type [x y] clicks]
   (on-fx #(SceneHelper/processMouseEvent (scene) (mouse-event type (double x) (double y) clicks)))))

(defn- press! [place] (pointer! MouseEvent/MOUSE_PRESSED place))
(defn- drag! [place] (pointer! MouseEvent/MOUSE_DRAGGED place))
(defn- release! [place] (pointer! MouseEvent/MOUSE_RELEASED place))

(defn- key!
  "A key, sent to the scene as a real one is: whatever has the focus gets it."
  [type ^KeyCode code & {:keys [shift shortcut]}]
  (on-fx #(SceneHelper/processKeyEvent
            (scene) (KeyEvent. type "" "" code (boolean shift) false false (boolean shortcut)))))

(defn- tap! [code & opts]
  (apply key! KeyEvent/KEY_PRESSED code opts)
  (apply key! KeyEvent/KEY_RELEASED code opts))

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

;;; The slider's pieces

;; Read where it is called from: never a second trip to the UI thread.
(defn- piece ^Region [^Parent pane i] (.get (.getChildrenUnmodifiable pane) i))
(defn- fill ^Region [pane] (piece pane 1))
(defn- notch ^Region [pane] (piece pane 2))
(defn- thumb ^Region [pane] (piece pane 3))
(defn- bubble ^Label [pane] (piece pane 4))

(def ^:private ends {:min 0.0 :max 100.0})

(defn- place-of
  "Where in the window the middle of the thumb is for `value`."
  [^Region pane value]
  (on-fx #(let [pt (.localToScene pane (double (s/x-of ends (.getWidth pane) value)) (/ (.getHeight pane) 2.0))]
            [(.getX pt) (.getY pt)])))

(defn- thumb-place
  "Where in the window the middle of the thumb is now."
  [^Region pane]
  (on-fx #(let [^Region t (.get (.getChildrenUnmodifiable pane) 3)
                pt (.localToScene pane (+ (.getLayoutX t) (/ (.getWidth t) 2.0)) (/ (.getHeight pane) 2.0))]
            [(.getX pt) (.getY pt)])))

(defn- shift [[x y] dx dy] [(+ x dx) (+ y dy)])
(defn- size [pane] (Math/round (* 100.0 (double (on-fx #(.getScaleX (thumb pane)))))))
(defn- shown [pane] (on-fx #(.getOpacity (bubble pane))))
(defn- words [pane] (on-fx #(.getText (bubble pane))))
(defn- whole [x] (Math/round (double x)))

(defn- luminance [^Color c]
  (let [lin #(if (<= % 0.03928) (/ % 12.92) (Math/pow (/ (+ % 0.055) 1.055) 2.4))]
    (+ (* 0.2126 (lin (.getRed c))) (* 0.7152 (lin (.getGreen c))) (* 0.0722 (lin (.getBlue c))))))

(defn- contrast
  "The lowest contrast between the bubble's words and what is drawn behind
  them: the bubble is drawn without its words, and the middle of it is read."
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

(defn -main [& _]
  (future (Thread/sleep (* 1000 (long timeout-s)))
          (println "timeout: the checks ran over" timeout-s "s")
          (System/exit 2))
  (reset! ui/*follow-system false)
  (reset! ui/*reduce false)
  (reset! p/*state p/start-state)
  (fx/mount-renderer p/*state p/renderer)
  (Thread/sleep 1500)
  (let [b ^Region (node "brightness")
        v ^Region (node "volume")
        page ^ScrollPane (node "page")
        state #(deref p/*state)
        value #(get-in (state) [:sliders % :value])
        live #(get-in (state) [:sliders % :live])
        writes #(:writes (state))
        fresh! (fn []
                 (swap! p/*state assoc :sliders (:sliders p/start-state) :writes 0 :undo [])
                 (Thread/sleep 700))]

    (println "A drag moves the thumb")
    (check "at rest it shows no number" 0.0 (shown b))
    (check "size at rest" 100 (size b))
    (press! (thumb-place b))
    (Thread/sleep 300)
    (check "size held" 110 (size b))
    (check "held, the bubble shows the value in its unit" [1.0 "20%"] [(shown b) (words b)])
    (check "held, the pointer is a closed hand" Cursor/CLOSED_HAND (on-fx #(.getCursor (scene))))
    (let [middle (place-of b 50.0)]
      (drag! (place-of b 35.0))
      (drag! middle)
      (Thread/sleep 100)
      (check "dragged to the middle: half the range" 50 (whole (live :brightness)))
      (check "the thumb is under the pointer" (whole (first middle)) (whole (first (thumb-place b))))
      (check "the fill reaches the thumb" (whole (- (first middle) (first (place-of b 0.0)) (- (/ s/thumb-w 2.0))))
             (whole (on-fx #(.getWidth (fill b)))))
      (check "the bubble follows" "50%" (words b))
      (check "what it sets follows live: the square" 0.5 (let [square (node "square")] (on-fx #(.getOpacity square))))
      (check "nothing is written during the drag" [20.0 0] [(value :brightness) (writes)])
      (Thread/sleep 1100)
      (check "size after 1.5 s held" 110 (size b))
      (release! middle))
    (Thread/sleep 700)
    (check "size once released" 100 (size b))
    (check "written once, on the release" [50.0 1] [(value :brightness) (writes)])
    (check "released, the bubble is gone" 0.0 (shown b))
    (check "released, the pointer is let go" nil (on-fx #(.getCursor (scene))))

    (println "Past the ends, off the slider")
    (press! (thumb-place b))
    (drag! (shift (place-of b 0.0) -100 150))
    (Thread/sleep 50)
    (check "past the low end it stops there, the pointer far below" 0.0 (live :brightness))
    (drag! (shift (place-of b 100.0) 100 -150))
    (Thread/sleep 50)
    (check "past the high end it stops there, the pointer far above" 100.0 (live :brightness))
    (drag! (place-of b 75.0))
    (Thread/sleep 50)
    (check "it takes up again when the pointer comes back" 75 (whole (live :brightness)))
    (release! (place-of b 75.0))
    (Thread/sleep 700)
    (check "written" [75 2] [(whole (value :brightness)) (writes)])

    (println "Escape")
    (let [before (value :brightness)]
      (press! (thumb-place b))
      (drag! (place-of b 30.0))
      (Thread/sleep 50)
      (check "dragged" 30 (whole (live :brightness)))
      (key! KeyEvent/KEY_PRESSED KeyCode/ESCAPE)
      (Thread/sleep 700)
      (check "Escape puts it back, and what it sets" before (live :brightness))
      (check "Escape lets go of the thumb" [100 0.0] [(size b) (shown b)])
      (drag! (place-of b 10.0))
      (Thread/sleep 50)
      (check "the rest of that press does nothing" before (live :brightness))
      (release! (place-of b 10.0))
      (Thread/sleep 100)
      (check "nothing written" [before 2] [(value :brightness) (writes)]))

    (println "A press on the track")
    (let [[from _] (thumb-place b)
          to (place-of b 10.0)]
      (press! to)
      (Thread/sleep 30)
      (let [[early _] (thumb-place b)]
        (check "30 ms on, the thumb has left its place and is not yet under the pointer" true
               (< (first to) early from)))
      (Thread/sleep 250)
      (check "then it is under the pointer" (whole (first to)) (whole (first (thumb-place b))))
      (drag! (place-of b 25.0))
      (Thread/sleep 50)
      (check "the same press goes on as a drag" 25 (whole (live :brightness)))
      (release! (place-of b 25.0))
      (Thread/sleep 700)
      (check "written once" [25 3] [(whole (value :brightness)) (writes)]))

    (println "The notch, and a double click")
    (check "the notch marks the default" (whole (first (place-of b 50.0)))
           (whole (on-fx #(let [n (notch b)
                                pt (.localToScene b (+ (.getLayoutX n) (/ (.getWidth n) 2.0)) 0.0)]
                            (.getX pt)))))
    (press! (thumb-place b))
    (drag! (shift (place-of b 50.0) 6 0))
    (Thread/sleep 50)
    (check "6 px from the notch it does not snap" false (= 50.0 (live :brightness)))
    (drag! (shift (place-of b 50.0) 3 0))
    (Thread/sleep 50)
    (check "3 px from the notch it snaps to the default" 50.0 (live :brightness))
    (drag! (place-of b 80.0))
    (release! (place-of b 80.0))
    (Thread/sleep 700)
    (let [before (writes)
          place (thumb-place b)]
      (pointer! MouseEvent/MOUSE_PRESSED place 1)
      (pointer! MouseEvent/MOUSE_RELEASED place 1)
      (pointer! MouseEvent/MOUSE_PRESSED place 2)
      (pointer! MouseEvent/MOUSE_RELEASED place 2)
      (Thread/sleep 700)
      (check "a double click puts it at its default, written once" [50.0 (inc before)]
             [(value :brightness) (writes)])
      (check "and the thumb is there" (whole (first (place-of b 50.0))) (whole (first (thumb-place b)))))

    (println "Scrolling")
    (let [before (value :brightness)]
      (scroll! (thumb-place b) -40.0)
      (Thread/sleep 200)
      (check "scrolling over a slider does not move it" before (live :brightness))
      (check "the page under it scrolls" true (pos? (double (on-fx #(.getVvalue page)))))
      (on-fx #(.setVvalue page 0.0))
      (Thread/sleep 200))

    (println "The thumb stretches while it moves")
    (press! (thumb-place b))
    (Thread/sleep 300)
    (let [place (thumb-place b)]
      (drag! (shift place 4 0))
      (drag! (shift place 120 0))
      (check "in a fast drag it is wider than 28 px" true (> (double (on-fx #(.getWidth (thumb b)))) s/thumb-w))
      (Thread/sleep 600)
      (check "once settled it is 28 px" s/thumb-w (on-fx #(.getWidth (thumb b))))
      (release! (shift place 120 0)))
    (Thread/sleep 700)

    (println "The bubble stays whole")
    (swap! p/*state assoc :pad 2)
    (Thread/sleep 400)
    (let [edges #(on-fx (fn [] (let [l (bubble b) r (.localToScene l (.getLayoutBounds l))]
                                 [(.getMinX r) (.getMaxX r)])))
          width (on-fx #(.getWidth (scene)))]
      (press! (thumb-place b))
      (drag! (shift (place-of b 0.0) -50 0))
      (Thread/sleep 100)
      (let [[lo _] (edges)]
        (check "at the low end the bubble is inside the window" true (>= lo 0.0))
        (check "it slid sideways: it is no longer centred on the thumb" true
               (> (+ lo (/ (on-fx #(.getWidth (bubble b))) 2.0)) (first (thumb-place b)))))
      (drag! (shift (place-of b 100.0) 50 0))
      (Thread/sleep 100)
      (check "at the high end the bubble is inside the window" true (<= (second (edges)) width))
      (release! (place-of b 100.0)))
    (swap! p/*state assoc :pad 24)
    (fresh!)

    (println "The keyboard")
    (on-fx #(.requestFocus b))
    (tap! KeyCode/RIGHT)
    (Thread/sleep 200)
    (check "Right raises it 1%" [21.0 1] [(value :brightness) (writes)])
    (check "a key press shows the bubble" [1.0 "21%"] [(shown b) (words b)])
    (Thread/sleep 1300)
    (check "for 1 s" 0.0 (shown b))
    (tap! KeyCode/RIGHT :shift true)
    (check "Shift+Right raises it 10%" 31.0 (value :brightness))
    (tap! KeyCode/DOWN)
    (check "Down lowers it 1%" 30.0 (value :brightness))
    (tap! KeyCode/END)
    (check "End goes to the high end" 100.0 (value :brightness))
    (tap! KeyCode/HOME)
    (check "Home goes to the low end" 0.0 (value :brightness))
    (let [before (writes)]
      (tap! KeyCode/LEFT)
      (check "Left at the low end writes nothing" [0.0 before] [(value :brightness) (writes)])
      (dotimes [_ 5] (key! KeyEvent/KEY_PRESSED KeyCode/RIGHT))
      (check "a held key moves it and writes nothing yet" [5.0 before] [(live :brightness) (writes)])
      (key! KeyEvent/KEY_RELEASED KeyCode/RIGHT)
      (check "let go, it writes once" [5.0 (inc before)] [(value :brightness) (writes)]))

    (println "Undo")
    (fresh!)
    (on-fx #(.requestFocus b))
    (dotimes [_ 3] (tap! KeyCode/RIGHT))
    (check "key presses close together are one step" [23.0 1] [(value :brightness) (count (:undo (state)))])
    (tap! KeyCode/Z :shortcut true)
    (Thread/sleep 300)
    (check "Undo takes them back together" 20.0 (value :brightness))
    (press! (thumb-place b))
    (drag! (place-of b 70.0))
    (release! (place-of b 70.0))
    (Thread/sleep 700)
    (check "one drag" 70 (whole (value :brightness)))
    (tap! KeyCode/Z :shortcut true)
    (Thread/sleep 300)
    (check "Undo: the value before the drag" 20.0 (value :brightness))
    (check "and the thumb is back" (whole (first (place-of b 20.0))) (whole (first (thumb-place b))))

    (println "Disabled")
    (fresh!)
    (on-fx #(.requestFocus (node "mute")))
    (check "disabled, at 45% opacity" [true 0.45] (on-fx #(vector (.isDisabled v) (.getOpacity v))))
    (press! (thumb-place v))
    (Thread/sleep 200)
    (check "pressed, it does not grow and shows no bubble" [100 0.0] [(size v) (shown v)])
    (drag! (place-of v 80.0))
    (release! (place-of v 80.0))
    (on-fx #(.requestFocus v))
    (tap! KeyCode/END)
    (Thread/sleep 200)
    (check "a disabled slider answers no drag and no key" [30.0 30.0 0] [(value :volume) (live :volume) (writes)])

    (println "States, sizes and the screen reader")
    (check "its height is that of a button" s/hold-px (on-fx #(.getHeight b)))
    (check "the track is 4 px" s/track-px (on-fx #(.getHeight (fill b))))
    (check "the thumb is 28 by 20 px" [s/thumb-w s/thumb-h] (on-fx #(vector (.getWidth (thumb b)) (.getHeight (thumb b)))))
    (check "120 px wide or wider" true (>= (double (on-fx #(.getWidth b))) s/min-width))
    (check "over the thumb the pointer is an open hand" Cursor/OPEN_HAND (on-fx #(.getCursor (thumb b))))
    (let [paint #(str (on-fx (fn [] (.getFill (first (.getFills (.getBackground (thumb b))))))))
          at-rest (paint)]
      (pseudo! (thumb b) "hover" true)
      (Thread/sleep 300)
      (check "the thumb changes colour under the pointer" false (= at-rest (paint)))
      (pseudo! (thumb b) "hover" false))
    (pseudo! b "focus-visible" true)
    (Thread/sleep 200)
    (check "on keyboard focus, a ring in the accent colour round the thumb" (Color/web "#4aa3ff")
           (on-fx #(.getTopStroke (first (.getStrokes (.getBorder (thumb b)))))))
    (pseudo! b "focus-visible" false)
    (check "each has a label that names it" ["Brightness" "Volume"]
           (on-fx #(mapv (fn [^Node n] (.getText ^Label (first (.getChildrenUnmodifiable (.getParent n))))) [b v])))
    (check "each is a slider to a screen reader" [AccessibleRole/SLIDER AccessibleRole/SLIDER]
           (on-fx #(mapv (fn [^Node n] (.getAccessibleRole n)) [b v])))
    (check "its name is what it sets, with no value in it" "Brightness" (on-fx #(.getAccessibleText b)))
    (check "and a screen reader can ask for the value itself" 20.0
           (on-fx #(.queryAccessibleAttribute b AccessibleAttribute/VALUE (object-array 0))))
    (on-fx #(.requestFocus b))
    (tap! KeyCode/RIGHT)
    (Thread/sleep 200)
    (check "after a change, it is asked again: the new value, and the same name" [21.0 "Brightness"]
           (on-fx #(vector (.queryAccessibleAttribute b AccessibleAttribute/VALUE (object-array 0))
                           (.getAccessibleText b))))
    (check "off, it is called dimmed and says why, in its name"
           ["Volume. Muted: untick Mute to change the volume." "dimmed slider"]
           (on-fx #(vector (.getAccessibleText v) (.getAccessibleRoleDescription v))))
    (let [tip #(on-fx (fn [] (some-> ^Tooltip (.get (.getProperties (.getParent ^Node %))
                                                    "javafx.scene.control.Tooltip")
                                     .getText)))]
      (check "the tooltip says the value" "Brightness: 21%" (tip b))
      (check "a disabled slider's tooltip says why" "Muted: untick Mute to change the volume." (tip v)))

    (println "The bubble's words")
    (doseq [at [15.0 85.0]]
      (press! (thumb-place b))
      (drag! (place-of b at))
      (Thread/sleep 300)
      (let [ratio (contrast (bubble b))]
        (check (str "contrast at " (whole at) "%: 4.5 or more (" (format "%.1f" ratio) ")") true (>= ratio 4.5)))
      (release! (place-of b at))
      (Thread/sleep 300))

    (println "Frames")
    (fresh!)
    (let [{:keys [fps slowest-ms]}
          (frames (fn []
                    (dotimes [i 3]
                      (press! (thumb-place b))
                      (doseq [at (range 20 81 4)] (drag! (place-of b at)) (Thread/sleep 16))
                      (release! (place-of b 80.0))
                      (Thread/sleep 500)
                      (let [to (place-of b (+ 5.0 i))]
                        (press! to) (Thread/sleep 150) (release! to))
                      (Thread/sleep 500))))]
      (check (str "55 frames a second or more through drags and track presses ("
                  (format "%.1f" fps) ", slowest frame " (format "%.1f" slowest-ms) " ms)")
             true (>= fps 55.0)))

    (println "Reduce Motion")
    (reset! ui/*reduce true)
    (fresh!)
    (press! (thumb-place b))
    (Thread/sleep 200)
    (check "held, the thumb does not grow" 100 (size b))
    (drag! (shift (thumb-place b) 4 0))
    (drag! (shift (thumb-place b) 100 0))
    (check "moving, it does not stretch" s/thumb-w (on-fx #(.getWidth (thumb b))))
    (release! (thumb-place b))
    (Thread/sleep 700)
    (let [to (place-of b 90.0)]
      (press! to)
      (Thread/sleep 20)
      (check "a press on the track lands the thumb at once" (whole (first to)) (whole (first (thumb-place b))))
      (release! to)))
  (println (if (zero? @failures) "All checks passed." (str @failures " checks failed.")))
  (System/exit (if (zero? @failures) 0 1)))
