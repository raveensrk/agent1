(ns demo.scroll-check
  "The window checks of Scroll areas and scroll bars, in
  requirements/components.org. Opens the real window, behind whatever is in
  front, and sends it scrolls, swipes, glides, presses and keys through the
  scene, which picks what is under each as it does for a real pointer; nothing
  moves the pointer and nothing takes the keyboard. macOS's own settings are
  never changed: the checks set the area's copy of them.

      clojure -M:check-scroll"
  (:require [cljfx.api :as fx]
            [demo.scroll :as s]
            [demo.scroll-page :as p]
            [demo.ui :as ui])
  (:import [java.io File]
           [javafx.animation AnimationTimer]
           [javafx.application Platform]
           [javafx.beans.property SimpleDoubleProperty]
           [javafx.event Event EventHandler]
           [javafx.geometry Orientation Rectangle2D]
           [javafx.scene AccessibleAttribute AccessibleRole Cursor Node Scene SnapshotParameters]
           [javafx.scene.control Label]
           [javafx.scene.input KeyCode KeyEvent MouseButton MouseEvent ScrollEvent
            ScrollEvent$HorizontalTextScrollUnits ScrollEvent$VerticalTextScrollUnits]
           [javafx.scene.layout Pane Region]
           [javafx.scene.paint Color]
           [javafx.stage Stage Window]
           [com.sun.javafx.scene SceneHelper]))

;; The whole run, in seconds: over it, the checks stop and say so.
(def timeout-s 150)

(defn- on-fx [f]
  (let [pr (promise)]
    (Platform/runLater #(deliver pr (try (f) (catch Throwable t t))))
    (deref pr 5000 :timeout)))

(defn- scene ^Scene []
  (.getScene ^Window (first (filter #(and (instance? Stage %) (.isShowing ^Window %)) (Window/getWindows)))))

(defn- node ^Node [id] (on-fx #(.lookup (.getRoot (scene)) (str "#" id))))

(def failures (atom 0))

(defn- check [what expected actual]
  (let [ok (= expected actual)]
    (when-not ok (swap! failures inc))
    (println (if ok "ok  " "FAIL") what "- expected" expected "got" actual)))

(defn- whole [x] (Math/round (double x)))
(defn- near [a b] (<= (Math/abs (- (double a) (double b))) 1.0))

;;; An area's insides, read on the UI thread

(defn- parts [^Node a] (.get (.getProperties a) :demo.scroll/parts))
(defn- off [a axis] (on-fx #(.get ^SimpleDoubleProperty ((:off (parts a)) axis))))
(defn- drawn [a axis] (on-fx #(.get ^SimpleDoubleProperty ((:drawn (parts a)) axis))))
(defn- geo [a] (on-fx #(deref (:geo (parts a)))))
(defn- most [a axis] (let [{:keys [rh ch rw cw]} (geo a)] (if (= axis :y) (s/most ch rh) (s/most cw rw))))
;; The pieces themselves are fixed once made: read where called from.
(defn- holder ^Pane [a axis] (:holder ((:bars (parts a)) axis)))
(defn- knob-node ^Region [a axis] (:knob ((:bars (parts a)) axis)))
(defn- track-node ^Region [a axis] (:track ((:bars (parts a)) axis)))
(defn- shown [a axis] (on-fx #(.getOpacity (holder a axis))))
(defn- set-off! [a axis v]
  (on-fx #(.set ^SimpleDoubleProperty ((:off (parts a)) axis) (double v)))
  (Thread/sleep 60))

(defn- scene-box
  "A node's edges in the window: [left top right bottom]."
  [^Node n]
  (on-fx #(let [b (.localToScene n (.getLayoutBounds n))] [(.getMinX b) (.getMinY b) (.getMaxX b) (.getMaxY b)])))

(defn- mid [n] (let [[l t r b] (scene-box n)] [(/ (+ l r) 2.0) (/ (+ t b) 2.0)]))

;;; Events, sent the way a real pointer's and keyboard's are

(defn- mouse-event [type x y clicks alt]
  (MouseEvent. type x y x y MouseButton/PRIMARY (int clicks)
               false false (boolean alt) false
               (boolean (#{MouseEvent/MOUSE_PRESSED MouseEvent/MOUSE_DRAGGED} type)) false false
               false false false nil))

(defn- pointer!
  "One mouse event at a place in the window: the scene picks what is under it."
  [type [x y] & {:keys [alt]}]
  (on-fx #(SceneHelper/processMouseEvent (scene) (mouse-event type (double x) (double y) 1 alt))))

(defn- move! [place] (pointer! MouseEvent/MOUSE_MOVED place) (Thread/sleep 20))
(defn- press! [place & opts] (apply pointer! MouseEvent/MOUSE_PRESSED place opts))
(defn- drag! [place] (pointer! MouseEvent/MOUSE_DRAGGED place))
(defn- release! [place] (pointer! MouseEvent/MOUSE_RELEASED place))

(defn- key! [type ^KeyCode code & {:keys [shift alt shortcut]}]
  (on-fx #(SceneHelper/processKeyEvent
            (scene) (KeyEvent. type "" "" code (boolean shift) false (boolean alt) (boolean shortcut)))))

(defn- tap! [code & opts]
  (apply key! KeyEvent/KEY_PRESSED code opts)
  (apply key! KeyEvent/KEY_RELEASED code opts))

(defn- scroll-event [type [x y] dx dy {:keys [inertia touch lines shift]}]
  (ScrollEvent. type x y x y (boolean shift) false false false false (boolean inertia)
                (double dx) (double dy) (double dx) (double dy)
                ScrollEvent$HorizontalTextScrollUnits/NONE 0.0
                (if lines ScrollEvent$VerticalTextScrollUnits/LINES ScrollEvent$VerticalTextScrollUnits/NONE)
                (if lines (/ (double dy) s/line-px) 0.0)
                (int (or touch 0)) nil))

(defn- scroll-at!
  "A scroll event at a place, given to whatever the scene picks there."
  [type [x y] dx dy opts]
  (on-fx #(let [seen (atom nil)
                see (reify EventHandler (handle [_ e] (reset! seen (.getTarget ^Event e))))]
            (.addEventFilter (scene) MouseEvent/MOUSE_MOVED see)
            (SceneHelper/processMouseEvent (scene) (mouse-event MouseEvent/MOUSE_MOVED (double x) (double y) 0 false))
            (.removeEventFilter (scene) MouseEvent/MOUSE_MOVED see)
            (Event/fireEvent @seen (scroll-event type [x y] dx dy opts)))))

(defn- wheel!
  "Notches of a wheel: down is positive, a line each."
  [place notches & {:keys [shift]}]
  (scroll-at! ScrollEvent/SCROLL place 0.0 (* -1.0 s/line-px notches) {:lines true :shift shift}))

(defn- touching!
  "The fingers on the trackpad, moving the content by each [dx dy] of `steps`, a
  frame apart; the gesture goes on until `lift!`."
  [place steps]
  (scroll-at! ScrollEvent/SCROLL_STARTED place 0.0 0.0 {:touch 2})
  (doseq [[dx dy] steps]
    (scroll-at! ScrollEvent/SCROLL place dx dy {:touch 2})
    (Thread/sleep 16)))

(defn- lift! [place] (scroll-at! ScrollEvent/SCROLL_FINISHED place 0.0 0.0 {:touch 2}))

(defn- swipe! [place steps] (touching! place steps) (lift! place))

(defn- glide!
  "macOS's glide after the fingers lift: each step a frame apart."
  [place steps]
  (doseq [[dx dy] steps]
    (scroll-at! ScrollEvent/SCROLL place dx dy {:inertia true})
    (Thread/sleep 16)))

(defn- down [n px] (repeat n [0.0 (- px)]))

;;; Pixels

(defn- luminance [^Color c]
  (let [lin #(if (<= % 0.03928) (/ % 12.92) (Math/pow (/ (+ % 0.055) 1.055) 2.4))]
    (+ (* 0.2126 (lin (.getRed c))) (* 0.7152 (lin (.getGreen c))) (* 0.0722 (lin (.getBlue c))))))

(defn- ratio [a b] (/ (+ 0.05 (max a b)) (+ 0.05 (min a b))))

(defn- knob-contrast
  "The most the knob's pixels stand out from the content beside its bar."
  [a]
  (on-fx
    (fn []
      (let [k (knob-node a :y)
            b (.localToScene k (.getLayoutBounds k))
            snap (fn [x y w h] (.snapshot (.getRoot (scene))
                                          (doto (SnapshotParameters.) (.setViewport (Rectangle2D. x y w h))) nil))
            img (snap (.getMinX b) (+ (.getMinY b) 4) (.getWidth b) (- (.getHeight b) 8))
            bg (luminance (.getColor (.getPixelReader (snap (- (.getMinX b) 24) (.getCenterY b) 1 1)) 0 0))
            reader (.getPixelReader img)]
        (apply max (for [px (range (int (.getWidth img))) py (range (int (.getHeight img)))]
                     (ratio bg (luminance (.getColor reader px py)))))))))

(defn- frames
  "Runs `f` while counting the window's frames: the frames a second it kept up."
  [f]
  (let [times (atom [])
        timer (proxy [AnimationTimer] [] (handle [now] (swap! times conj now)))]
    (on-fx #(.start timer))
    (f)
    (on-fx #(.stop timer))
    (let [gaps (map - (rest @times) @times)]
      {:fps (/ (count gaps) (/ (reduce + gaps) 1e9))
       :slowest-ms (/ (apply max gaps) 1e6)})))

(defn- bring-into-view!
  "Scrolls the page so `n` sits `from-top` px under the page's top."
  [page n from-top]
  (let [[_ t] (scene-box n)
        [_ pt] (scene-box page)]
    (set-off! page :y (+ (off page :y) (- t pt from-top)))
    (Thread/sleep 100)))

(defn- mount! []
  (fx/mount-renderer p/*state p/renderer)
  (Thread/sleep 1500))

(defn -main [& _]
  (future (Thread/sleep (* 1000 (long timeout-s)))
          (println "timeout: the checks ran over" timeout-s "s")
          (System/exit 2))
  (reset! ui/*follow-system false)
  (reset! ui/*reduce false)
  (reset! s/*follow-settings false)
  (reset! s/*settings {:overlay true :jump false})
  (reset! p/*places-file (doto (File/createTempFile "scroll-places" ".edn") (.delete)))
  (reset! p/*load-ms 5)
  (reset! p/*state (assoc p/start-state :logging false))
  (p/keep-places!)
  (mount!)

  (println "Content that fits")
  (swap! p/*state assoc :page :about)
  (Thread/sleep 600)
  (let [about (node "about")]
    (check "an area whose content fits shows no bar" [#{} false false]
           [(:need (geo about)) (on-fx #(.isVisible (holder about :y))) (on-fx #(.isVisible (holder about :x)))])
    (wheel! (mid about) 3)
    (Thread/sleep 200)
    (check "and a scroll moves nothing" [0.0 0.0] [(off about :y) (drawn about :y)]))
  (swap! p/*state assoc :page :scroll)
  (Thread/sleep 800)

  (let [page (node "page")
        rows (node "rows")
        grid (node "grid")
        table (node "table")
        log (node "log")
        row-list (node "row-list")
        [pl pt pr pb] (scene-box page)
        room (:rh (geo page))
        edge-place [(- pr 6.0) (+ pt (/ room 2.0))]
        away [(+ pl 200.0) (+ pt 200.0)]]

    (println "The bar shows while it is needed")
    (Thread/sleep 1500)
    (check "first seen, it shows for 1 s, then it is gone" 0.0 (shown page :y))
    (wheel! away 1)
    (Thread/sleep 30)
    (check "it shows the moment the area scrolls" 1.0 (shown page :y))
    (Thread/sleep 120)
    (Thread/sleep 950)
    (check "1 s on with no scroll: still there" 1.0 (shown page :y))
    (Thread/sleep 500)
    (check "1.4 s on: gone" 0.0 (shown page :y))
    (check "a wheel notch moves a line" s/line-px (off page :y))

    (println "macOS's Show scroll bars")
    (let [w (on-fx #(.getWidth page))]
      (reset! s/*settings {:overlay false :jump false})
      (Thread/sleep 400)
      (check "always shown: 15 px beside the content, with a track, there at rest"
             [15.0 1.0 1.0 (- w 15.0)]
             [(on-fx #(.getWidth (holder page :y))) (on-fx #(.getOpacity (track-node page :y)))
              (shown page :y) (:rw (geo page))])
      (check "where both bars show, a square fills the corner" true
             (on-fx #(.isVisible ^Region (:corner (parts grid)))))
      (reset! s/*settings {:overlay true :jump false})
      (Thread/sleep 400)
      (check "only when scrolling: it floats over the content, its knob 7 px, with no track"
             [7.0 0.0 w]
             [(on-fx #(.getWidth (knob-node page :y))) (on-fx #(.getOpacity (track-node page :y))) (:rw (geo page))])
      (check "3 px in from the edge" (- w s/bar-in)
             (on-fx #(let [k (knob-node page :y)] (+ (.getLayoutX (holder page :y)) (.getLayoutX k) (.getWidth k)))))
      (check "no arrow buttons: a track and a knob, and nothing else" 2
             (on-fx #(.size (.getChildren (holder page :y)))))
      (check "over a bar the pointer is the arrow" Cursor/DEFAULT (on-fx #(.getCursor (holder page :y)))))

    (println "The pointer over the bar")
    (move! edge-place)
    (Thread/sleep 250)
    (check "the knob grows to 11 px and a track shows under it" [11.0 1.0 1.0]
           [(on-fx #(.getWidth (knob-node page :y))) (on-fx #(.getOpacity (track-node page :y))) (shown page :y)])
    (Thread/sleep 2000)
    (check "2 s on, it stays while the pointer is there" 1.0 (shown page :y))
    (move! away)
    (Thread/sleep 1500)
    (check "the pointer gone, it fades after 1 s" [0.0 7.0] [(shown page :y) (on-fx #(.getWidth (knob-node page :y)))])

    (println "The knob's length")
    (let [{:keys [rh ch]} (geo page)
          track (- (on-fx #(.getHeight (holder page :y))) (* 2 s/bar-in))]
      (check "the room's share of the content" (whole (* track (/ rh ch)))
             (whole (on-fx #(.getHeight (knob-node page :y))))))
    (check "over 100,000 rows: never under 24 px" 24.0 (on-fx #(.getHeight (knob-node rows :y))))

    (println "A swipe follows the fingers, then glides")
    (set-off! page :y 0.0)
    (swipe! away (down 10 10.0))
    (Thread/sleep 50)
    (check "the content follows the fingers one to one" 100.0 (off page :y))
    (touching! away (down 5 20.0))
    (lift! away)
    (let [lifted (off page :y)]
      (glide! away (down 3 30.0))
      (let [during (off page :y)]
        (glide! away [[0.0 -20.0] [0.0 -12.0] [0.0 -6.0] [0.0 -2.0]])
        (Thread/sleep 300)
        (let [still (off page :y)]
          (Thread/sleep 200)
          (check "let go with speed it glides on, then stops, further than the swipe went" [true true true]
                 [(> during lifted) (> still during) (= still (off page :y))]))))

    (println "The edge gives, then springs back")
    (set-off! page :y (most page :y))
    (touching! away (down 10 60.0))
    (let [pulled (- (drawn page :y))]
      (check (str "past the bottom it is pulled on, by no more than a third of the room (" (whole pulled) " px)")
             true (< 20.0 pulled (/ room 3.0))))
    (lift! away)
    (Thread/sleep 400)
    (check "400 ms after the lift: at the end again" [0.0 (most page :y)] [(drawn page :y) (off page :y)])
    (wheel! away 1)
    (Thread/sleep 40)
    (check "a wheel notch at the bottom: no give" [0.0 (most page :y)] [(drawn page :y) (off page :y)])

    (println "A gesture keeps to its axis, and goes to the right area")
    (bring-into-view! page grid 140.0)
    (set-off! grid :x 0.0)
    (set-off! grid :y 0.0)
    (swipe! (mid grid) (repeat 5 [3.0 -20.0]))
    (Thread/sleep 200)
    (check "a down swipe with a little drift: down, and no sideways move" [100.0 0.0] [(off grid :y) (off grid :x)])
    (bring-into-view! page table 140.0)
    (set-off! table :x 0.0)
    (wheel! (mid table) 1 :shift true)
    (Thread/sleep 200)
    (check "Shift and the wheel scroll sideways" s/line-px (off table :x))
    (let [before (off page :y)]
      (swipe! (mid table) (repeat 3 [2.0 -20.0]))
      (Thread/sleep 200)
      (check "an up swipe over the wide table scrolls the page; the table stays" [(+ before 60.0) s/line-px]
             [(off page :y) (off table :x)]))
    (bring-into-view! page rows 120.0)
    (set-off! rows :y (- (most rows :y) 50.0))
    (let [before (off page :y)]
      (touching! (mid rows) (down 10 20.0))
      (check "a swipe over the rows runs them to their end, and the page stays" [true before]
             [(>= (off rows :y) (most rows :y)) (off page :y)])
      (lift! (mid rows))
      (Thread/sleep 500)
      (swipe! (mid rows) (down 3 20.0))
      (Thread/sleep 200)
      (check "a new swipe there, pushing on, scrolls the page" [(+ before 60.0) (most rows :y)]
             [(off page :y) (off rows :y)]))

    (println "A drag on the knob")
    (set-off! page :y 0.0)
    (move! edge-place)
    (Thread/sleep 200)
    (let [k (knob-node page :y)
          [kx ky] (mid k)
          len (on-fx #(.getHeight k))
          track (- (on-fx #(.getHeight (holder page :y))) (* 2 s/bar-in))
          half [kx (+ ky (/ (- track len) 2.0))]]
      (press! [kx ky])
      (drag! [kx (+ ky 10.0)])
      (drag! half)
      (Thread/sleep 50)
      (check "dragged halfway: half the content, within 1 px" true (near (/ (most page :y) 2.0) (off page :y)))
      (drag! [(- kx 900.0) (second half)])
      (Thread/sleep 30)
      (check "off the window the drag goes on, with no jump" true (near (/ (most page :y) 2.0) (off page :y)))
      (drag! half)
      (release! half)
      (Thread/sleep 100)
      (let [[kx ky] (mid k)
            start (off page :y)]
        (press! [kx ky])
        (drag! [kx (+ ky 80.0)])
        (Thread/sleep 50)
        (check "dragged" true (> (off page :y) start))
        (key! KeyEvent/KEY_PRESSED KeyCode/ESCAPE)
        (Thread/sleep 50)
        (check "Escape puts the content back where the drag began" start (off page :y))
        (release! [kx (+ ky 80.0)])))

    (println "A click in the track")
    (let [spot [(first edge-place) (+ pt (* 0.6 room))]
          k (knob-node page :y)
          click! (fn [& opts]
                   (set-off! page :y 0.0)
                   (move! edge-place)
                   (Thread/sleep 150)
                   (apply press! spot opts)
                   (Thread/sleep 30)
                   (release! spot)
                   (Thread/sleep 250)
                   (off page :y))
          centred #(let [[_ ky] (mid k)] (whole (- ky (second spot))))]
      (reset! s/*settings {:overlay true :jump false})
      (check "set to go a page: a page" (s/page-px room) (click!))
      (click! :alt true)
      (check "Option and a click: the spot clicked" 0 (centred))
      (reset! s/*settings {:overlay true :jump true})
      (Thread/sleep 100)
      (click!)
      (check "set to go to the spot: the knob there" 0 (centred))
      (check "Option and a click: a page" (s/page-px room) (click! :alt true))
      (reset! s/*settings {:overlay true :jump false})
      (Thread/sleep 100)
      (set-off! page :y 0.0)
      (move! edge-place)
      (Thread/sleep 150)
      (press! spot)
      (Thread/sleep 600)
      (let [[_ top _ bottom] (scene-box k)]
        (check "held, it pages on until the knob is under the pointer, no further" [true true]
               [(<= top (second spot) bottom) (< (off page :y) (most page :y))]))
      (release! spot))

    (println "The keyboard")
    (on-fx #(.requestFocus page))
    (set-off! page :y 0.0)
    (doseq [[code what want] [[KeyCode/DOWN "Down: a line" s/line-px]
                              [KeyCode/PAGE_DOWN "Page Down: a page less a line" (+ s/line-px (s/page-px room))]
                              [KeyCode/SPACE "Space: a page less a line" (+ s/line-px (* 2 (s/page-px room)))]
                              [KeyCode/END "End: the bottom" (most page :y)]
                              [KeyCode/HOME "Home: the top" 0.0]]]
      (tap! code)
      (Thread/sleep 250)
      (check what want (off page :y)))
    (let [field (node "field")] (on-fx #(.requestFocus field)))
    (Thread/sleep 300)
    (let [before (off page :y)]
      (tap! KeyCode/DOWN)
      (Thread/sleep 200)
      (check "in a text field Down moves the caret, not the page" before (off page :y)))

    (println "Brought into sight")
    (set-off! page :y 0.0)
    (let [field (node "field")] (on-fx #(.requestFocus field)))
    (Thread/sleep 300)
    (tap! KeyCode/TAB)
    (Thread/sleep 300)
    (let [far (node "far")
          [_ top _ bottom] (scene-box far)]
      (check "Tab gives the focus to a control out of sight" true (on-fx #(identical? far (.getFocusOwner (scene)))))
      (check "and it is brought into the room, 16 px clear" true
             (and (>= top (+ pt 15.5)) (<= bottom (- (+ pt room) 15.5)))))
    (bring-into-view! page rows 120.0)
    (set-off! rows :y 0.0)
    (let [[rl rt rr rb] (scene-box rows)
          x (/ (+ rl rr) 2.0)]
      (press! [x (+ rt 40.0)])
      (drag! [x (- rb 30.0)])
      (drag! [x (- rb 10.0)])
      (Thread/sleep 500)
      (let [moved (off rows :y)]
        (check "a drag held 10 px from the bottom edge scrolls the rows down" true (> moved 100.0))
        (release! [x (- rb 10.0)])
        (Thread/sleep 100)
        (check "and stops once let go" (off rows :y) (do (Thread/sleep 100) (off rows :y)))
        (check "choosing the rows it ran over" true (> (count (:chosen @p/*state)) 5))))

    (println "The place is kept")
    (set-off! rows :y 3200.0)
    (let [first-seen #(+ (get-in @p/*state [:rows :lo]) (int (Math/floor (/ (off rows :y) 32.0))))
          seen (first-seen)]
      (p/handle {:event :add-above})
      (Thread/sleep 300)
      (check "rows added above: the first row seen stays where it was" [seen 3840.0] [(first-seen) (off rows :y)]))
    (dotimes [_ 20] (swap! p/*state p/log-line))
    (Thread/sleep 300)
    (check "a log at its newest line stays there as lines come in" (most log :y) (off log :y))
    (set-off! log :y 0.0)
    (dotimes [_ 3] (swap! p/*state p/log-line))
    (Thread/sleep 300)
    (check "scrolled up, it stays put" 0.0 (off log :y))
    (set-off! page :y 300.0)
    (Thread/sleep 900)
    (swap! p/*state assoc :page :about)
    (Thread/sleep 400)
    (swap! p/*state assoc :page :scroll)
    (Thread/sleep 600)
    (check "going back to a page: the place it was left at" 300.0 (off (node "page") :y))
    (check "and it is on disk" [0.0 300.0] (get (p/read-places) "page"))
    (fx/unmount-renderer p/*state p/renderer)
    (Thread/sleep 500)
    (reset! p/*state (assoc p/start-state :logging false :places (p/read-places)))
    (mount!)
    (check "after a restart: the same" 300.0 (off (node "page") :y)))

  (let [page (node "page")
        rows (node "rows")
        grid (node "grid")
        [pl pt _ _] (scene-box page)
        away [(+ pl 200.0) (+ pt 200.0)]
        room (:rh (geo page))]

    (println "Content under glass")
    (set-off! page :y 0.0)
    (Thread/sleep 200)
    (let [band ^Region (on-fx #(:band (parts page)))
          alpha (fn [y] (on-fx #(let [img (.snapshot band (doto (SnapshotParameters.) (.setFill Color/TRANSPARENT)) nil)]
                                  (.getOpacity (.getColor (.getPixelReader img) 20 (int y))))))]
      (check "at the top, nothing under the glass: no fade" 0.0 (on-fx #(.getOpacity band)))
      (set-off! page :y 200.0)
      (Thread/sleep 300)
      (check "scrolled under: the fade shows" 1.0 (on-fx #(.getOpacity band)))
      (check "content is seen through it, and it fades over 16 px at the glass's edge" [true true]
             (let [top (alpha 10) foot (alpha (+ 72 14))]
               [(< 0.3 top 0.9) (< foot (* 0.3 top))])))

    (println "The knob reads over dark content and light")
    (wheel! away 1)
    (Thread/sleep 100)
    (let [dark (knob-contrast page)]
      (check (str "over dark: 3 or more (" (format "%.1f" dark) ")") true (>= dark 3.0)))
    (on-fx #(.setStyle ^Region (.get (.getChildren page) 0) "-fx-background-color: #f4f4f8;"))
    (wheel! away 1)
    (Thread/sleep 100)
    (let [light (knob-contrast page)]
      (check (str "over light: 3 or more (" (format "%.1f" light) ")") true (>= light 3.0)))
    (on-fx #(.setStyle ^Region (.get (.getChildren page) 0) ""))

    (println "The screen reader")
    (check "a scroll area is a scroll area" AccessibleRole/SCROLL_PANE (on-fx #(.getAccessibleRole page)))
    (let [ask (fn [^Node n attr] (on-fx #(.queryAccessibleAttribute n attr (object-array 0))))
          bar (ask page AccessibleAttribute/VERTICAL_SCROLLBAR)]
      (check "its bar is a scroll bar, up and down" [AccessibleRole/SCROLL_BAR Orientation/VERTICAL]
             [(on-fx #(.getAccessibleRole ^Node bar)) (ask bar AccessibleAttribute/ORIENTATION)])
      (check "a page that scrolls only up and down has no sideways bar" nil
             (ask page AccessibleAttribute/HORIZONTAL_SCROLLBAR))
      (check "the grid has both" [Orientation/HORIZONTAL Orientation/VERTICAL]
             [(ask (ask grid AccessibleAttribute/HORIZONTAL_SCROLLBAR) AccessibleAttribute/ORIENTATION)
              (ask (ask grid AccessibleAttribute/VERTICAL_SCROLLBAR) AccessibleAttribute/ORIENTATION)])
      (set-off! page :y 0.0)
      (Thread/sleep 1500)
      (check "faded out, its place is still read: the top" 0.0 (ask bar AccessibleAttribute/VALUE))
      (set-off! page :y (/ (most page :y) 2.0))
      (check "after a scroll: halfway" 0.5 (ask bar AccessibleAttribute/VALUE))
      (on-fx #(.executeAccessibleAction ^Node bar javafx.scene.AccessibleAction/INCREMENT (object-array 0)))
      (Thread/sleep 250)
      (check "a screen reader's page down moves it a page" (whole (+ (/ (most page :y) 2.0) (s/page-px room)))
             (whole (off page :y))))

    (println "Reduce Motion")
    (reset! ui/*reduce true)
    (on-fx #(.requestFocus page))
    (set-off! page :y 0.0)
    (tap! KeyCode/PAGE_DOWN)
    (Thread/sleep 20)
    (check "Page Down: already a page on" (s/page-px room) (off page :y))
    (set-off! page :y (- (most page :y) 100.0))
    (scroll-at! ScrollEvent/SCROLL_STARTED away 0.0 0.0 {:touch 2})
    (lift! away)
    (let [pulls (atom [])]
      (doseq [d [-40.0 -40.0 -40.0 -30.0 -20.0]]
        (glide! away [[0.0 d]])
        (swap! pulls conj (drawn page :y)))
      (Thread/sleep 100)
      (check "a glide into the end stops there, with no bounce" [#{0.0} (most page :y)] [(set @pulls) (off page :y)]))
    (reset! ui/*reduce false)

    (println "Frames, and rows built")
    (bring-into-view! page rows 120.0)
    (set-off! rows :y 0.0)
    (let [row-list (node "row-list")
          built (atom [])
          {:keys [fps slowest-ms]}
          (frames (fn []
                    (dotimes [_ 3]
                      (touching! (mid rows) (down 12 25.0))
                      (lift! (mid rows))
                      (glide! (mid rows) (for [v (range 60 0 -3)] [0.0 (- v)]))
                      (swap! built conj (on-fx #(s/rows-built row-list)))
                      (Thread/sleep 200))))]
      (check (str "55 frames a second or more through three swipes and three glides over 100,000 rows ("
                  (format "%.1f" fps) ", slowest frame " (format "%.1f" slowest-ms) " ms)")
             true (>= fps 55.0))
      (let [screen (/ (:rh (geo rows)) 32.0)]
        (check (str "rows built: a screen's worth and the rows either side, never all " @built)
               true (every? #(<= % (+ 2 (* 3 screen))) @built)))))

  (println (if (zero? @failures) "All checks passed." (str @failures " checks failed.")))
  (System/exit (if (zero? @failures) 0 1)))
