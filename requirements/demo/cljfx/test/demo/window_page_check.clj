(ns demo.window-page-check
  "The window checks of requirements/windows.org: The app must have a Window,
  and Panes. Opens the real windows and sends them mouse events; nothing moves the pointer.

      clojure -M:check-window"
  (:require [cljfx.api :as fx]
            [demo.ui :as ui]
            [demo.window :as w])
  (:import [javafx.animation AnimationTimer]
           [javafx.application Platform]
           [javafx.event Event]
           [javafx.scene Cursor Node Parent]
           [javafx.scene.control Button ButtonBase Labeled MenuBar MenuItem Tooltip]
           [javafx.scene.input MouseButton MouseEvent]
           [javafx.scene.layout Region]
           [javafx.stage Stage Window]))

(defn- on-fx [f]
  (let [p (promise)]
    (Platform/runLater #(deliver p (try (f) (catch Throwable t t))))
    (deref p 5000 :timeout)))

(defn- stages*
  "The app's windows. On the FX thread."
  []
  (vec (filter #(instance? Stage %) (Window/getWindows))))

(defn- node*
  "The node with `id` in the first window, or nil. On the FX thread."
  [id]
  (.lookup (.getRoot (.getScene ^Stage (first (stages*)))) (str "#" id)))

(defn- bar*
  "The title bar of the floating window with `id`. On the FX thread."
  ^Parent [id]
  (-> ^Parent (node* id) .getChildrenUnmodifiable ^Parent (.get 0) .getChildrenUnmodifiable (.get 0)))

(defn- stages [] (on-fx stages*))

(defn- node [id] (on-fx #(node* id)))

(defn- width [id] (Math/round (double (on-fx #(.getWidth ^Region (node* id))))))
(defn- height [id] (Math/round (double (on-fx #(.getHeight ^Region (node* id))))))

(defn- mouse! [^Node target type x y clicks]
  (on-fx #(Event/fireEvent target (MouseEvent. type x y x y MouseButton/PRIMARY clicks
                                               false false false false
                                               (= type MouseEvent/MOUSE_DRAGGED) false false
                                               true false false nil))))

(defn- drag!
  "Drags the divider of `pane` to a place in the window, and lets go."
  [pane x y]
  (let [d (node (str "divider-" (name pane)))]
    (mouse! d MouseEvent/MOUSE_DRAGGED x y 0)
    (Thread/sleep 150)))

(defn- let-go! [pane]
  (mouse! (node (str "divider-" (name pane))) MouseEvent/MOUSE_RELEASED 0 0 0)
  (Thread/sleep 150))

(defn- scene-size [] (on-fx #(let [s (.getScene ^Stage (first (stages*)))] [(.getWidth s) (.getHeight s)])))

(defn- set-width! [w] (on-fx #(.setWidth ^Stage (first (stages*)) w)))

(defn- send! [event] (on-fx #(w/handle event)) (Thread/sleep 250))

(def session-file
  "The checks' own kept session, so a run neither reads nor spoils the demo's."
  (clojure.java.io/file (System/getProperty "user.home") "tmp" "agent1-window-check" "session.edn"))

(defn- kept
  "The size of `pane` in the kept session, or nil if nothing is kept."
  [pane]
  (get-in (w/read-session) [:sizes pane]))

(def failures (atom 0))

(defn- check [what expected actual]
  (let [ok (= expected actual)]
    (when-not ok (swap! failures inc))
    (println (if ok "ok  " "FAIL") what "- expected" expected "got" actual)))

(defn- frames [f]
  (let [times (atom [])
        timer (proxy [AnimationTimer] [] (handle [now] (swap! times conj now)))]
    (on-fx #(.start timer))
    (f)
    (on-fx #(.stop timer))
    (let [gaps (map - (rest @times) @times)]
      {:fps (/ (count gaps) (/ (reduce + gaps) 1e9))
       :slowest-ms (/ (apply max gaps) 1e6)})))

(defn -main [& _]
  ;; The checks close every window on the way; the app must outlive that.
  (Platform/setImplicitExit false)
  (reset! ui/*follow-system false)
  (reset! ui/*reduce false)
  (doseq [^java.io.File f [session-file (clojure.java.io/file (str session-file ".bad"))]] (.delete f))
  (reset! w/*session-file session-file)
  (reset! w/*state w/start-state)
  (w/keep-session!)
  (fx/mount-renderer w/*state w/renderer)
  (Thread/sleep 1800)
  (let [state #(deref w/*state)
        half (+ w/edge (/ w/divider-size 2.0))
        [scene-w scene-h] (scene-size)]

    (println "A window, and its panes")
    (check "one window" 1 (count (stages)))
    (check "sidebar at the size it starts at" 220 (width "sidebar"))
    (check "inspector at the size it starts at" 260 (width "inspector"))
    (check "notes pane at the size it starts at" 140 (height "bottom"))
    (check "one tab: no tab bar" nil (node "tab-bar"))

    (println "Panes resize")
    (check "the divider shows a resize pointer" Cursor/H_RESIZE (on-fx #(.getCursor ^Node (node* "divider-sidebar"))))
    (drag! :sidebar 300 200)
    (check "the sidebar follows the pointer" (Math/round (- 300 half)) (width "sidebar"))
    (check "its divider is marked while dragged" true
           (on-fx #(.contains (.getStyleClass ^Node (node* "divider-sidebar")) "dragging")))
    (drag! :sidebar 900 200)
    (check "no wider than its largest" 320 (width "sidebar"))
    (drag! :sidebar 10 200)
    (check "no narrower than its smallest" 160 (width "sidebar"))
    (Thread/sleep 700)
    (check "nothing is kept while it is dragged, however long" nil (kept :sidebar))
    (let-go! :sidebar)
    (Thread/sleep 700)
    (check "the size is kept when let go" 160.0 (kept :sidebar))
    (drag! :inspector 700 200)
    (check "the inspector follows the pointer" (Math/round (- scene-w 700 half)) (width "inspector"))
    (drag! :inspector 0 200)
    (check "no wider than its largest" 360 (width "inspector"))
    (let-go! :inspector)
    (drag! :bottom 400 (- scene-h 200 half))
    (check "the notes pane follows the pointer, up and down" 200 (height "bottom"))
    (drag! :bottom 400 (- scene-h 10))
    (check "no shorter than its smallest" 80 (height "bottom"))
    (let-go! :bottom)
    (Thread/sleep 700)
    (check "a height is kept too" 80.0 (kept :bottom))
    (mouse! (node "divider-sidebar") MouseEvent/MOUSE_CLICKED 0 0 2)
    (Thread/sleep 200)
    (check "a double click puts the pane back" 220 (width "sidebar"))

    (println "Sizes between runs")
    (Thread/sleep 700)
    (check "the next run starts with the kept sizes" {:sidebar 220.0 :inspector 360.0 :bottom 80.0}
           (:sizes (w/restore (w/read-session) (on-fx w/screens))))
    (check "one kept outside the limits comes back within them" {:sidebar 320.0 :inspector 360.0 :bottom 80.0}
           (:sizes (w/restore (assoc-in (assoc-in (w/read-session) [:sizes :sidebar] 999.0) [:sizes :bottom] 5.0)
                              (on-fx w/screens))))
    (check "sizes and windows are kept in one file" [true true]
           [(contains? (w/read-session) :sizes) (contains? (w/read-session) :windows)])

    (println "The page keeps its room")
    (swap! w/*state assoc :sizes {:sidebar 320.0 :inspector 360.0 :bottom 140.0})
    (set-width! 760)
    (Thread/sleep 500)
    (check "at 760 px, both panes at their largest, the page has 280 px or more" true (>= (width "content") 280))
    (swap! w/*state assoc :sizes w/default-sizes)
    (set-width! 960)
    (Thread/sleep 500)

    (println "A narrow window")
    (set-width! 600)
    (Thread/sleep 100)
    (check "the sidebar glides to icons" true (< 56 (width "sidebar") 220))
    (Thread/sleep 600)
    (check "narrow: the sidebar is icons only, 56 px" 56 (width "sidebar"))
    (let [rows (on-fx #(vec (.getChildrenUnmodifiable ^Parent (node* "sidebar"))))]
      (check "its rows show no words" true (every? #(empty? (str (on-fx (fn [] (.getText ^Labeled %))))) rows))
      (check "each row keeps its name as a tooltip" "Inbox"
             (on-fx #(some-> ^Tooltip (.get (.getProperties ^Node (first rows)) "javafx.scene.control.Tooltip") .getText))))
    (check "narrow: the inspector hides" [0 false]
           [(width "inspector") (on-fx #(.isVisible ^Node (node* "inspector")))])
    (check "its divider goes with it" nil (node "divider-inspector"))
    (check "its button says why it is off" true (on-fx #(.isDisabled ^Node (node* "toggle-inspector"))))
    (set-width! 960)
    (Thread/sleep 700)
    (check "wide again: the sidebar is back" 220 (width "sidebar"))
    (check "wide again: the inspector is back" 260 (width "inspector"))
    (reset! ui/*reduce true)
    (set-width! 600)
    (Thread/sleep 70)
    (check "Reduce Motion: the sidebar changes at once" 56 (width "sidebar"))
    (set-width! 960)
    (Thread/sleep 300)
    (reset! ui/*reduce false)

    (println "Hiding a pane")
    (on-fx #(.fire ^ButtonBase (node* "toggle-sidebar")))
    (Thread/sleep 600)
    (check "the toolbar button hides the sidebar" [0 false]
           [(width "sidebar") (on-fx #(.isVisible ^Node (node* "sidebar")))])
    ;; Read on the FX thread in one go: a menu's items, as [text item has-key].
    (let [menu (fn [n]
                 (on-fx #(let [^MenuBar bar (first (.getChildrenUnmodifiable (.getRoot (.getScene ^Stage (first (stages*))))))]
                           (vec (for [^MenuItem item (.getItems ^javafx.scene.control.Menu (nth (.getMenus bar) n))]
                                  [(.getText item) item (some? (.getAccelerator item))])))))
          show-sidebar (first (menu 1))]
      (check "the View menu offers to show it again" "Show Sidebar" (first show-sidebar))
      (on-fx #(.fire ^MenuItem (second show-sidebar)))
      (Thread/sleep 600)
      (check "the menu brings it back" 220 (width "sidebar"))
      (check "the File menu" ["New Window" "New Tab" nil "Close Tab" "Close Window"] (mapv first (menu 0)))
      (check "each command has a key" true
             (every? #(nth % 2) (filter first (concat (menu 0) (menu 1) (menu 2))))))

    (println "Tabs")
    (on-fx #(.fire ^ButtonBase (node* "new-tab")))
    (Thread/sleep 300)
    (check "a new tab" 2 (count (get-in (state) [:windows 1 :tabs])))
    (check "two tabs: the tab bar shows both" 2
           (on-fx #(count (.getChildrenUnmodifiable ^Parent (node* "tab-bar")))))
    (on-fx #(.fire ^ButtonBase (.get (.getChildrenUnmodifiable ^Parent (node* "sidebar")) 2)))
    (Thread/sleep 300)
    (check "the new tab goes to Notes" "Notes" (on-fx #(.getText ^Labeled (node* "page-title"))))
    (check "the window is named for the page" "Notes" (on-fx #(.getTitle ^Stage (first (stages*)))))
    (mouse! (on-fx #(first (.getChildrenUnmodifiable ^Parent (node* "tab-bar")))) MouseEvent/MOUSE_CLICKED 5 5 1)
    (Thread/sleep 300)
    (check "the first tab kept its own page" "Inbox" (on-fx #(.getText ^Labeled (node* "page-title"))))
    (on-fx #(.fire ^ButtonBase (second (.getChildrenUnmodifiable ^Parent (first (.getChildrenUnmodifiable ^Parent (node* "tab-bar")))))))
    (Thread/sleep 300)
    (check "its close button closes it" [1 "Notes"]
           [(count (get-in (state) [:windows 1 :tabs])) (on-fx #(.getText ^Labeled (node* "page-title")))])
    (check "one tab again: no tab bar" nil (node "tab-bar"))

    (println "Several windows")
    (send! {:event :new-window})
    (Thread/sleep 800)
    (check "a second window" 2 (count (stages)))
    (send! {:event :new-tab :window 2})
    (check "each window has its own tabs" [1 2]
           [(count (get-in (state) [:windows 1 :tabs])) (count (get-in (state) [:windows 2 :tabs]))])
    (check "both share the kept pane sizes" (width "sidebar")
           (Math/round (double (on-fx #(.getWidth ^Region (.lookup (.getRoot (.getScene ^Stage (second (stages*)))) "#sidebar"))))))
    (send! {:event :close-tab :window 2})
    (send! {:event :close-tab :window 2})
    (Thread/sleep 500)
    (check "closing its last tab closes the window" 1 (count (stages)))
    (check "the first window is untouched" "Notes" (on-fx #(.getText ^Labeled (node* "page-title"))))

    (println "Floating windows")
    (let [layer-size #(on-fx (fn [] (let [^Region l (node* "float-layer")] [(.getWidth l) (.getHeight l)])))
          place (fn [id] (on-fx #(let [^Region f (node* id)]
                                   (mapv (fn [v] (Math/round (double v)))
                                         [(.getLayoutX f) (.getLayoutY f) (.getWidth f) (.getHeight f)]))))
          ;; A point of a floating window, in the window: its corner plus dx, dy.
          point (fn [id dx dy] (on-fx #(let [^Node f (node* id)
                                             p (.localToScene f 0.0 0.0)]
                                         [(+ (.getX p) dx) (+ (.getY p) dy)])))
          bar (fn [id] (on-fx #(bar* id)))
          grip (fn [id] (on-fx #(-> ^Parent (node* id) .getChildrenUnmodifiable (.get 1))))
          front (fn [] (on-fx #(.getId ^Node (last (.getChildrenUnmodifiable ^Parent (node* "float-layer"))))))]
      (on-fx #(.fire ^ButtonBase (node* "new-float")))
      (Thread/sleep 500)
      (let [[lw _] (layer-size)
            x0 (Math/round (/ (- lw 260.0) 2.0))]
        (check "a floating window opens over the page, at the size it starts at" [x0 90 260 160] (place "float-1"))
        (check "clear of the sidebar" true (> x0 (width "sidebar"))))
      (check "it is named for the page it opened on" "Notes"
             (on-fx #(.getText ^Labeled (.get (.getChildrenUnmodifiable ^Parent (bar* "float-1")) 0))))
      (check "it has faded in" 1.0 (on-fx #(.getOpacity ^Node (node* "float-1"))))
      (let [[x y] (point "float-1" 30 12)]
        (mouse! (bar "float-1") MouseEvent/MOUSE_PRESSED x y 1)
        (mouse! (bar "float-1") MouseEvent/MOUSE_DRAGGED (+ x 100) (+ y 60) 0)
        (Thread/sleep 200)
        (check "its title bar drags it" [(+ 100 (Math/round (/ (- (first (layer-size)) 260.0) 2.0))) 150]
               (subvec (place "float-1") 0 2))
        (mouse! (bar "float-1") MouseEvent/MOUSE_DRAGGED 5000 5000 0)
        (Thread/sleep 200)
        (let [[lw lh] (layer-size)]
          (check "it stops at the window's edges" [(Math/round (- lw 260.0)) (Math/round (- lh 160.0))]
                 (subvec (place "float-1") 0 2)))
        (mouse! (bar "float-1") MouseEvent/MOUSE_DRAGGED -5000 -5000 0)
        (Thread/sleep 200)
        (check "at every edge" [0 0] (subvec (place "float-1") 0 2))
        (mouse! (bar "float-1") MouseEvent/MOUSE_RELEASED 0 0 0))
      (let [[x y] (point "float-1" 340 200)]
        (mouse! (grip "float-1") MouseEvent/MOUSE_DRAGGED x y 0)
        (Thread/sleep 200)
        (check "its corner resizes it" [340 200] (subvec (place "float-1") 2 4)))
      (let [[x y] (point "float-1" 2000 2000)]
        (mouse! (grip "float-1") MouseEvent/MOUSE_DRAGGED x y 0)
        (Thread/sleep 200)
        (check "no larger than its largest" [480 360] (subvec (place "float-1") 2 4)))
      (let [[x y] (point "float-1" 5 5)]
        (mouse! (grip "float-1") MouseEvent/MOUSE_DRAGGED x y 0)
        (Thread/sleep 200)
        (check "no smaller than its smallest" [200 120] (subvec (place "float-1") 2 4))
        (mouse! (grip "float-1") MouseEvent/MOUSE_RELEASED 0 0 0))
      (on-fx #(.fire ^ButtonBase (node* "new-float")))
      (Thread/sleep 400)
      (check "a second opens a step away, in front"
             ["float-2" [(+ 28 (Math/round (/ (- (first (layer-size)) 260.0) 2.0))) 118]]
             [(front) (subvec (place "float-2") 0 2)])
      (mouse! (node "float-1") MouseEvent/MOUSE_PRESSED 5 5 1)
      (Thread/sleep 200)
      (check "a press brings the first to the front" "float-1" (front))
      (let [[x y] (point "float-2" 30 12)]
        (mouse! (bar "float-2") MouseEvent/MOUSE_PRESSED x y 1)
        (mouse! (bar "float-2") MouseEvent/MOUSE_DRAGGED 5000 5000 0)
        (mouse! (bar "float-2") MouseEvent/MOUSE_RELEASED 0 0 0))
      (set-width! 600)
      (Thread/sleep 700)
      (let [[lw lh] (layer-size)]
        (check "the window shrinks: none is left outside it" true
               (every? (fn [[x y w h]] (and (<= (+ x w) (Math/ceil lw)) (<= (+ y h) (Math/ceil lh))))
                       [(place "float-1") (place "float-2")])))
      (set-width! 960)
      (Thread/sleep 500)
      (check "the page under them still takes a click" true
             (do (on-fx #(.fire ^ButtonBase (.get (.getChildrenUnmodifiable ^Parent (node* "sidebar")) 3)))
                 (Thread/sleep 200)
                 (= "Tags" (on-fx #(.getText ^Labeled (node* "page-title"))))))
      (check "an open one keeps the page it opened on" "Notes"
             (on-fx #(.getText ^Labeled (.get (.getChildrenUnmodifiable ^Parent (bar* "float-1")) 0))))
      (on-fx #(.fire ^ButtonBase (.get (.getChildrenUnmodifiable ^Parent (bar* "float-1")) 1)))
      (Thread/sleep 300)
      (check "its close button closes it" [nil "float-2"] [(node "float-1") (front)])
      (on-fx #(.fire ^ButtonBase (.get (.getChildrenUnmodifiable ^Parent (bar* "float-2")) 1)))
      (Thread/sleep 300)
      (on-fx #(.fire ^ButtonBase (.get (.getChildrenUnmodifiable ^Parent (node* "sidebar")) 2)))
      (Thread/sleep 200))

    (println "Frames")
    (let [{:keys [fps slowest-ms]}
          (frames (fn []
                    (dotimes [_ 2]
                      (set-width! 600) (Thread/sleep 450)
                      (set-width! 960) (Thread/sleep 450))
                    (doseq [x (range 200 320 6)] (drag! :sidebar x 200))
                    (let-go! :sidebar)))]
      (check (str "55 frames a second or more through glides and a drag ("
                  (format "%.1f" fps) ", slowest frame " (format "%.1f" slowest-ms) " ms)")
             true (>= fps 55.0))))
  (println "A window comes back as it was left")
  (let [file session-file
        bad (clojure.java.io/file (str file ".bad"))
        stage-box #(on-fx (fn [] (let [^Stage st (first (stages*))]
                                   (mapv (fn [v] (Math/round (double v))) [(.getX st) (.getY st) (.getWidth st) (.getHeight st)]))))]
    ;; Let any write on its way land, then start from nothing kept.
    (Thread/sleep 700)
    (doseq [^java.io.File f [file bad]] (.delete f))
    (check "no kept session: nothing to restore" nil (w/read-session))
    ;; Leave the window somewhere else, another size, two tabs, a floating window.
    (on-fx #(doto ^Stage (first (stages*)) (.setX 300) (.setY 180) (.setWidth 1000) (.setHeight 640)))
    (send! {:event :select-page :window 1 :page :today})
    (send! {:event :new-tab :window 1})
    (send! {:event :select-page :window 1 :page :archive})
    (send! {:event :new-float :window 1})
    (send! {:event :toggle-inspector})
    (Thread/sleep 400)
    (let [left (w/session @w/*state)]
      (check "the window's place and size are followed" [300.0 180.0 1000.0 640.0]
             ((juxt :x :y :width :height) (first (:windows left))))
      (w/write-session! left)
      (check "the session is kept as plain text, read back the same" left (w/read-session))
      (check "one line of it, ending in a newline" true (clojure.string/ends-with? (slurp file) "}\n"))
      ;; Quit, in effect: every window gone. Then open what was kept.
      (reset! w/*state (assoc w/start-state :windows {} :order []))
      (Thread/sleep 600)
      (check "every window closed" 0 (count (stages)))
      (reset! w/*state (w/restore (w/read-session) (on-fx w/screens)))
      (Thread/sleep 1200)
      (check "it reopens at the same place and size" [300 180 1000 640] (stage-box))
      (check "with the same tabs" 2 (on-fx #(count (.getChildrenUnmodifiable ^Parent (node* "tab-bar")))))
      (check "on the same page" "Archive" (on-fx #(.getText ^Labeled (node* "page-title"))))
      (check "its floating window with it" true (some? (node "float-1")))
      (check "and the inspector still hidden" [0 false]
             [(width "inspector") (on-fx #(.isVisible ^Node (node* "inspector")))])
      (check "nothing lost on the way" left (w/session @w/*state)))
    ;; Kept while it runs: after 400 ms of quiet, not at every change.
    (Thread/sleep 700)
    (send! {:event :select-page :window 1 :page :tags})
    (check "a change is not written at once" :archive (last (:pages (first (:windows (w/read-session))))))
    (Thread/sleep 700)
    (check "it is written once things are still" :tags (last (:pages (first (:windows (w/read-session))))))
    (reset! w/*state (assoc w/start-state :windows {} :order []))
    (Thread/sleep 800)
    (check "closing the last window does not empty the kept session" 1 (count (:windows (w/read-session))))
    ;; Off every screen, and a file that cannot be read.
    (check "kept off every screen: back where a first window opens" [120.0 120.0]
           ((juxt :x :y) (get-in (w/restore {:windows [{:x 99999.0 :y 99999.0 :width 960.0 :height 600.0}]} (on-fx w/screens))
                                 [:windows 1 :open])))
    (spit file "{{{ not a session")
    (check "a file that cannot be read counts as none" nil (w/read-session))
    (check "and is moved aside, not written over" [false "{{{ not a session"] [(.exists file) (slurp bad)])
    ;; Leave nothing behind, and nothing for the write at quit to put back.
    (remove-watch w/*state :demo.window/session)
    (Thread/sleep 600)
    (doseq [^java.io.File f [file bad]] (.delete f))
    (.delete (.getParentFile file)))
  (println (if (zero? @failures) "All checks passed." (str @failures " checks failed.")))
  (System/exit (if (zero? @failures) 0 1)))
