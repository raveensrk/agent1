(ns demo.window-check
  "The window checks of Buttons, in requirements/components.org, and of Liquid
  Glass, in requirements/gui.org. Opens the real window and sends it mouse and
  key events through the scene, which picks what is under each as it does for a
  real pointer; nothing moves the pointer.

      clojure -M:check"
  (:require [cljfx.api :as fx]
            [demo.button :as b]
            [demo.ui :as ui])
  (:import [javafx.animation AnimationTimer]
           [javafx.application Platform]
           [javafx.css PseudoClass]
           [javafx.event Event]
           [javafx.geometry Rectangle2D]
           [javafx.scene AccessibleRole Node SnapshotParameters]
           [javafx.scene.control Button Tooltip]
           [javafx.scene.input KeyCode KeyEvent MouseButton MouseEvent]
           [javafx.scene.paint Color]
           [javafx.stage Window]
           [com.sun.javafx.scene SceneHelper]))

(defn- on-fx [f]
  (let [p (promise)]
    (Platform/runLater #(deliver p (try (f) (catch Throwable t t))))
    (deref p 5000 :timeout)))

(defn- button ^Button [id]
  (on-fx #(.lookup (.getRoot (.getScene ^Window (first (Window/getWindows)))) (str "#" id))))

(def ^:private at
  "Where the simulated pointer last was, in the window."
  (atom [0.0 0.0]))

(defn- pointer!
  "One mouse event at a place in the window, sent the way a real pointer's is:
  the scene picks what is under it. Nothing is sent to a button directly, so a
  button that something else covers is found out. The pointer is not moved."
  [type [x y]]
  (reset! at [x y])
  (on-fx #(SceneHelper/processMouseEvent
            (.getScene ^Window (first (Window/getWindows)))
            (MouseEvent. type x y x y MouseButton/PRIMARY 1
                         false false false false
                         (not= type MouseEvent/MOUSE_RELEASED) false false
                         false false false nil))))

(defn- centre [^Button btn]
  (on-fx #(let [b (.localToScene btn (.getLayoutBounds btn))]
            [(/ (+ (.getMinX b) (.getMaxX b)) 2.0) (/ (+ (.getMinY b) (.getMaxY b)) 2.0)])))

(defn- mouse!
  "A press on the middle of the button; a release wherever the pointer is; a
  leave as a drag to 150 px under the button, and an enter as a drag back."
  [^Button btn type]
  (condp = type
    MouseEvent/MOUSE_PRESSED (pointer! type (centre btn))
    MouseEvent/MOUSE_RELEASED (pointer! type @at)
    MouseEvent/MOUSE_EXITED (pointer! MouseEvent/MOUSE_DRAGGED (update (centre btn) 1 + 150.0))
    MouseEvent/MOUSE_ENTERED (pointer! MouseEvent/MOUSE_DRAGGED (centre btn))))

(defn- press! [btn] (mouse! btn MouseEvent/MOUSE_PRESSED))
(defn- release! [btn] (mouse! btn MouseEvent/MOUSE_RELEASED))

(defn- key!
  "A key, sent to the scene as a real one is: whatever has the focus gets it.
  The button is given the focus first, as Tab would give it."
  [^Button btn type ^KeyCode code]
  (on-fx #(do (.requestFocus btn)
              (SceneHelper/processKeyEvent
                (.getScene btn)
                (KeyEvent. type "" "" code false false false false)))))

(defn- size
  "The size of the box that moves, as a percentage."
  [^Button btn]
  (Math/round (* 100.0 (double (on-fx #(.getScaleX ^Node (.getParent btn)))))))

(defn- width [^Button btn] (on-fx #(.getWidth btn)))

(defn- fill-of [^Button btn] (on-fx #(first (.getFills (.getBackground btn)))))

(defn- luminance [^Color c]
  (let [lin #(if (<= % 0.03928) (/ % 12.92) (Math/pow (/ (+ % 0.055) 1.055) 2.4))]
    (+ (* 0.2126 (lin (.getRed c))) (* 0.7152 (lin (.getGreen c))) (* 0.0722 (lin (.getBlue c))))))

(defn- contrast
  "The lowest contrast between the button's words and what is drawn behind
  them: the button is drawn without its words, icon and mark, and the middle of
  it is read."
  [^Button btn]
  (on-fx
    (fn []
      (let [text (luminance (.getTextFill btn))
            ;; By opacity: the button's skin sets the visibility of its words itself.
            hidden (for [^Node n (concat [(.lookup btn ".text") (.getGraphic btn)]
                                         (rest (.getChildrenUnmodifiable (.getParent btn))))
                         :when n]
                     [n (.getOpacity n)])
            ;; Layout bounds: the local ones take in the shadow as well.
            b (.localToScene btn (.getLayoutBounds btn))
            x (+ (.getMinX b) 14) y (+ (.getMinY b) (* 0.25 (.getHeight b)))
            w (- (.getWidth b) 28) h (* 0.5 (.getHeight b))]
        (doseq [[^Node n _] hidden] (.setOpacity n 0.0))
        (let [img (.snapshot (.getRoot (.getScene btn))
                             (doto (SnapshotParameters.) (.setViewport (Rectangle2D. x y w h))) nil)
              reader (.getPixelReader img)
              worst (apply min (for [px (range (int (.getWidth img))) py (range (int (.getHeight img)))
                                     :let [bg (luminance (.getColor reader px py))]]
                                 (/ (+ 0.05 (max text bg)) (+ 0.05 (min text bg)))))]
          (doseq [[^Node n opacity] hidden] (.setOpacity n opacity))
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

(defn -main [& _]
  (reset! ui/*follow-system false)
  (reset! ui/*reduce false)
  (swap! b/*state assoc :look "glass" :solid false :contrast false)
  (fx/mount-renderer b/*state b/renderer)
  (Thread/sleep 1500)
  (let [add (button "add") save (button "save") subtract (button "subtract")
        delete (button "delete")
        state #(deref b/*state)]

    (println "Buttons answer a press")
    (check "size at rest" 100 (size add))
    (press! add)
    (Thread/sleep 300)
    (check "size pressed" 97 (size add))
    (check "held, it shows no edge inside the glass" Color/TRANSPARENT
           (on-fx #(.getTopStroke (first (.getStrokes (.getBorder add))))))
    (check "held, it shows no lighter shape inside the glass" Color/TRANSPARENT (.getFill (fill-of add)))
    ;; Up to the rim: the glass less its 1 px edge on each side.
    (check "the hold fill reaches the rim of the glass" 2.0
           (on-fx #(let [box (.getParent add)
                         fill ^Node (second (.getChildrenUnmodifiable box))]
                     (- (.getWidth (.getLayoutBounds box)) (.getWidth (.getLayoutBounds fill))))))
    (let [fill ^Node (on-fx #(second (.getChildrenUnmodifiable (.getParent add))))
          clip-width #(on-fx (fn [] (.getWidth (.getClip fill))))]
      (check "the hold fill has started, and is not yet full" true (< 0.0 (clip-width) (width add)))
      (Thread/sleep 1200)
      (check "size after 1.5 s held" 97 (size add))
      (check "one second action" 10 (:count (state))))
    (release! add)
    (Thread/sleep 700)
    (check "size once released" 100 (size add))
    (check "no click after the hold" 10 (:count (state)))

    (println "Dragged off, Escape, Return")
    (press! add)
    (Thread/sleep 200)
    (mouse! add MouseEvent/MOUSE_EXITED)
    (Thread/sleep 600)
    (check "dragged off, it rises" 100 (size add))
    (mouse! add MouseEvent/MOUSE_ENTERED)
    (Thread/sleep 200)
    (check "back over it, it sinks" 97 (size add))
    (mouse! add MouseEvent/MOUSE_EXITED)
    (release! add)
    (Thread/sleep 100)
    (check "let go off the button, nothing fires" 10 (:count (state)))
    (press! add)
    (Thread/sleep 100)
    (key! add KeyEvent/KEY_PRESSED KeyCode/ESCAPE)
    (Thread/sleep 700)
    (check "Escape lets go: it rises" 100 (size add))
    (release! add)
    (Thread/sleep 100)
    (check "Escape lets go: nothing fires" 10 (:count (state)))
    ;; Return belongs to the main button, wherever the focus is: here, on Save.
    (on-fx #(.requestFocus save))
    (key! save KeyEvent/KEY_PRESSED KeyCode/ENTER)
    (Thread/sleep 90)
    (check "Return sinks the main button" true (< (size add) 100))
    (key! save KeyEvent/KEY_RELEASED KeyCode/ENTER)
    (Thread/sleep 100)
    (check "Return is one click of the main button" 11 (:count (state)))
    (check "Return does not press the focused button" :idle (:save (state)))
    (Thread/sleep 600)
    (key! save KeyEvent/KEY_PRESSED KeyCode/SPACE)
    (Thread/sleep 200)
    (check "Space sinks the focused button" 97 (size save))
    (key! save KeyEvent/KEY_PRESSED KeyCode/ESCAPE)
    (key! save KeyEvent/KEY_RELEASED KeyCode/SPACE)
    (Thread/sleep 600)
    (check "Space, then Escape: nothing fires" :idle (:save (state)))

    (println "Busy, Saved, Retry")
    (press! save)
    (Thread/sleep 700)
    (check "nothing fires while held" :idle (:save (state)))
    (let [before (width save)]
      (release! save)
      (Thread/sleep 110)
      (let [during (width save)]
        (Thread/sleep 90)
        (check "one click on release" :saving (:save (state)))
        (Thread/sleep 300)
        (check "width glides to Saving" true (< before during (width save)))
        (check "spinner fully shown" 1.0 (on-fx #(.getOpacity (.getGraphic save))))))
    (press! save)
    (Thread/sleep 200)
    (check "a busy button does not sink" 100 (size save))
    (release! save)
    (Thread/sleep (+ 200 (long b/save-ms)))
    (check "it says Saved" "Saved" (on-fx #(.getText save)))
    (check "with a tick in the spinner's place, and the spinner at rest" [2 false 1.0]
           (on-fx #(let [slot ^javafx.scene.Parent (.getGraphic save)
                         kids (.getChildrenUnmodifiable slot)]
                     [(count kids) (.isVisible ^Node (.get kids 0)) (.getOpacity slot)])))
    (check "a busy button fires once" 1 (:saves (state)))
    (Thread/sleep (+ 300 (long b/saved-ms)))
    (check "then Save again" "Save" (on-fx #(.getText save)))
    (swap! b/*state assoc :fail-next true)
    (on-fx #(.fire save))
    (Thread/sleep (+ 300 (long b/save-ms)))
    (check "a failed save offers Retry" "Retry" (on-fx #(.getText save)))
    (check "nothing was saved" 1 (:saves (state)))
    (on-fx #(.fire save))
    (Thread/sleep 100)
    (check "Retry saves again" :saving (:save (state)))
    (Thread/sleep (+ 300 (long b/save-ms) (long b/saved-ms)))
    (check "the retry saved" 2 (:saves (state)))

    (println "Disabled, tooltips, the menu, the screen reader")
    (swap! b/*state assoc :count 0)
    (Thread/sleep 200)
    (check "disabled" true (on-fx #(.isDisabled subtract)))
    ;; A press on it, as a real pointer's: picking passes a disabled button by.
    (press! subtract)
    (Thread/sleep 100)
    (release! subtract)
    (Thread/sleep 100)
    (check "a disabled button counts nothing" 0 (:count (state)))
    (check "disabled size" 100 (size subtract))
    (check "off, it is called dimmed and says why, in its name"
           ["Subtract 1. Nothing to subtract: the count is 0." "dimmed button"]
           (on-fx #(vector (.getAccessibleText subtract) (.getAccessibleRoleDescription subtract))))
    (let [tip #(on-fx (fn [] (some-> ^Tooltip (.get (.getProperties (.getParent ^Button %))
                                                    "javafx.scene.control.Tooltip")
                                     .getText)))]
      (check "a disabled button says why" "Nothing to subtract: the count is 0." (tip subtract))
      (check "the tooltip names click and hold" "Click or Return: add 1. Hold: add 10." (tip add)))
    (on-fx #(.fire ^javafx.scene.control.MenuItem (first (.getItems (.getContextMenu add)))))
    (Thread/sleep 100)
    (check "the second action is on the right-click menu" 10 (:count (state)))
    (check "every button is a button to a screen reader" true
           (every? #(= AccessibleRole/BUTTON (on-fx (fn [] (.getAccessibleRole ^Button %))))
                   [add save subtract delete]))
    (check "the icon button has a name; on again, it is no longer called dimmed" ["Subtract 1" nil]
           (on-fx #(vector (.getAccessibleText subtract) (.getAccessibleRoleDescription subtract))))
    (check "the second action is said with the name" "Add 1. Hold: Add 10" (on-fx #(.getAccessibleText add)))
    (check "the hold is said out loud" "Click or Return: add 1. Hold: add 10." (on-fx #(.getAccessibleHelp add)))

    (println "Kinds and sizes")
    (check "one height" 1 (count (set (map #(on-fx (fn [] (.getHeight ^Button %))) [add save subtract delete]))))
    (check "an icon button is a circle" (on-fx #(.getHeight subtract)) (width subtract))
    (check "words: 76 px or wider" true (every? #(>= (width %) 76.0) [add save delete]))
    (on-fx #(.fire delete))
    (Thread/sleep 300)
    (let [cancel (button "cancel") confirm (button "confirm")]
      (check "Delete asks first" 10 (:count (state)))
      (check "a pair is equal width" (width cancel) (width confirm))
      (check "Return presses neither" false (on-fx #(or (.isDefaultButton cancel) (.isDefaultButton confirm))))
      (check "while it asks, Return presses nothing at all" false (on-fx #(.isDefaultButton add)))
      (check "Delete is red" true (on-fx #(let [^Color c (.getTextFill confirm)] (> (.getRed c) (.getGreen c) 0.0))))
      (on-fx #(.fire confirm))
      (Thread/sleep 200)
      (check "then it deletes" 0 (:count (state))))
    (swap! b/*state assoc :count 3)
    (Thread/sleep 300)

    (println "Liquid Glass")
    (let [group (on-fx #(.getParent (.getParent save)))
          group-fill #(on-fx (fn [] (first (.getFills (.getBackground ^javafx.scene.layout.Region group)))))
          radius #(.getTopLeftHorizontalRadius (.getRadii %))
          height #(on-fx (fn [] (.getHeight ^javafx.scene.layout.Region %)))]
      (check "the glass is a capsule: radius of half its height or more" true
             (>= (radius (group-fill)) (/ (height group) 2.0)))
      (check "a button on it is a capsule too" true (>= (radius (fill-of save)) (/ (height save) 2.0)))
      (check "the two share a centre: the same gap all round" true
             (on-fx #(let [g (.localToScene ^Node group (.getLayoutBounds ^Node group))
                           b (.localToScene save (.getLayoutBounds save))]
                       (= (- (.getMinY b) (.getMinY g)) (- (.getMaxY g) (.getMaxY b)) (- (.getMinX b) (.getMinX g))))))
      (check "glass is see-through" false (.isOpaque (.getFill (group-fill))))
      (check "a button on the glass has no glass of its own" Color/TRANSPARENT (.getFill (fill-of save)))
      (swap! b/*state assoc :confirm true)
      (Thread/sleep 300)
      (check "a button in the page is solid, not glass" true (.isOpaque (.getFill (fill-of (button "cancel")))))
      (swap! b/*state assoc :confirm false :solid true)
      (Thread/sleep 400)
      (check "solid under Reduce Transparency" true (.isOpaque (.getFill (group-fill))))
      (swap! b/*state assoc :solid false)
      (Thread/sleep 400))
    (let [rest-fill (str (.getFill (fill-of save)))]
      (on-fx #(.pseudoClassStateChanged save (PseudoClass/getPseudoClass "hover") true))
      (Thread/sleep 300)
      (check "it changes colour under the pointer" false (= rest-fill (str (.getFill (fill-of save)))))
      ;; The main button's glass is its box, and lightens as one piece.
      (doseq [^Node n [add save delete subtract (on-fx #(.getParent add))]]
        (on-fx #(.pseudoClassStateChanged n (PseudoClass/getPseudoClass "hover") true)))
      (Thread/sleep 300)
      (doseq [[what btn] [["Add 1" add] ["Save" save] ["Delete" delete]]]
        (let [ratio (contrast btn)]
          (check (str "contrast under the pointer, " what ": 4.5 or more (" (format "%.1f" ratio) ")") true (>= ratio 4.5))))
      (doseq [^Node n [add save delete subtract (on-fx #(.getParent add))]]
        (on-fx #(.pseudoClassStateChanged n (PseudoClass/getPseudoClass "hover") false)))
      (Thread/sleep 300))
    (doseq [[what btn] [["Add 1" add] ["Save" save] ["Delete" delete]]]
      (let [ratio (contrast btn)]
        (check (str "contrast at rest, " what ": 4.5 or more (" (format "%.1f" ratio) ")") true (>= ratio 4.5))))

    (println "Frames")
    (alter-var-root #'b/save-ms (constantly 300))
    (alter-var-root #'b/saved-ms (constantly 300))
    (let [{:keys [fps slowest-ms]}
          (frames (fn []
                    (dotimes [_ 3]
                      (on-fx #(.fire save))
                      (press! add) (Thread/sleep 250) (release! add)
                      (Thread/sleep 900))))]
      (check (str "55 frames a second or more through presses and glides ("
                  (format "%.1f" fps) ", slowest frame " (format "%.1f" slowest-ms) " ms)")
             true (>= fps 55.0)))
    (alter-var-root #'b/save-ms (constantly 1500))
    (alter-var-root #'b/saved-ms (constantly 1000))
    (Thread/sleep 500)

    (println "The system's settings")
    (reset! ui/*reduce true)
    (let [count-before (:count (state))]
      (press! add)
      (Thread/sleep 300)
      (check "size pressed, Reduce Motion" 100 (size add))
      (release! add)
      (Thread/sleep 200)
      (check "a short press is one click" (inc count-before) (:count (state))))
    (let [before (width save)]
      (on-fx #(.fire save))
      (Thread/sleep 80)
      (let [early (width save)]
        (Thread/sleep 500)
        (check "Reduce Motion: the width changes at once" true (and (> early before) (= early (width save)))))))
  (println (if (zero? @failures) "All checks passed." (str @failures " checks failed.")))
  (System/exit (if (zero? @failures) 0 1)))
