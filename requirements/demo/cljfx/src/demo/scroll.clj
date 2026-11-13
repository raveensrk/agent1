(ns demo.scroll
  "The part worth copying: a scroll area and its bars, as Scroll areas and
  scroll bars in requirements/components.org asks. A reference, not a library:
  follow what it does, and take the code as one way to do it. Nothing here
  knows about the demo's page or its state (demo.scroll-page).

  A fixed room with content that moves inside it, up and down, sideways, or
  both, and only along an axis where the content is larger than the room. The
  bars follow macOS: thin and floating while it scrolls, when macOS says so,
  or 15 px beside the content with a track. A swipe follows the fingers one to
  one, glides on as macOS sends it, and gives at an end like a rubber band; a
  notched wheel moves a line and stops at an end. A gesture stays with the
  area it began in. The knob drags, the track pages or jumps, and the keyboard
  scrolls a focused area. A control that takes the focus out of sight is
  brought into sight. Content that changes above what is seen does not move
  it, and a log stays at its newest line.

  What to take:

      scroll-view     one scroll area round a cljfx description
      make-area       the area itself, a Pane, for use without cljfx
      make-rows       content that builds only the rows in view
      reveal!         scrolls the least that brings a node into sight
      watch-settings! macOS's scroll settings, as they change
      knob, offset-at, pull, page-px, key-move, key-target, reveal-offset,
      lock-axis, auto-speed, bounce-px, row-range
                      the numbers and the rules, as plain data

  The look is in demo/glass.css, under `.scroll-bar-x`. Motion comes from
  demo.ui: its tween and its Reduce Motion."
  (:require [cljfx.api :as fx]
            [cljfx.lifecycle :as lifecycle]
            [cljfx.mutator :as mutator]
            [cljfx.prop :as prop]
            [clojure.java.io :as io]
            [clojure.java.shell :as shell]
            [clojure.string :as str]
            [demo.ui :as ui])
  (:import [javafx.animation AnimationTimer Interpolator PauseTransition]
           [javafx.application Platform]
           [javafx.beans.property SimpleDoubleProperty]
           [javafx.beans.value ChangeListener]
           [javafx.event Event EventHandler]
           [javafx.geometry Orientation]
           [javafx.scene AccessibleAction AccessibleAttribute AccessibleRole Cursor Node Parent Scene]
           [javafx.scene.control Label TextInputControl]
           [javafx.scene.input DragEvent KeyCode KeyEvent MouseButton MouseEvent ScrollEvent
            ScrollEvent$VerticalTextScrollUnits ScrollEvent$HorizontalTextScrollUnits]
           [javafx.scene.layout Pane Region]
           [javafx.scene.shape Rectangle]
           [javafx.util Duration]))

;;; Look and rules: plain data, so they are tested without a window

;; A floating bar: thin, 3 px in from the edge, wider under the pointer.
(def bar-thin 7.0)
(def bar-wide 11.0)
(def bar-in 3.0)
;; A bar shown always: its own room beside the content.
(def bar-legacy 15.0)
;; The edge the pointer finds a floating bar in.
(def bar-edge 16.0)
(def knob-least 24.0)
(def line-px 40.0)
;; Shown only when scrolling, a bar fades this long after the last scroll.
(def show-ms 1000)
(def fade-ms 300)
(def grow-ms 120)
(def wheel-ms 100)
(def key-ms 150)
;; The edge springs back in this long.
(def back-ms 300)
;; How far past an end the content may be pulled, as a part of the room.
(def pull-share (/ 1.0 3.0))
;; How stiff the pull is: the first px past an end move it about this much.
(def pull-give 0.55)
(def repeat-ms 100)
(def reveal-gap 16.0)
;; A drag this near an edge scrolls the area, up to `auto-most` px a frame.
(def auto-edge 24.0)
(def auto-most 18.0)
(def glass-fade 16.0)
;; The place is told once it has been still this long.
(def keep-ms 300)
;; A gesture with no event for this long is over, its glide too.
(def latch-ms 160)

(def axes [:x :y])

(defn most
  "The furthest the content can be scrolled: how much larger than the room."
  [content room]
  (max 0.0 (- (double content) (double room))))

(defn clamp [v hi] (-> (double v) (max 0.0) (min (double hi))))

(defn needs?
  "True when the content is larger than its room, so it scrolls and shows a bar."
  [content room]
  (> (double content) (+ (double room) 0.5)))

(defn knob
  "The knob along a `track` px long: its length the room's share of the
  content and never under `knob-least`, and its place the room's place along
  the content. Nil when the content fits."
  [{:keys [track room content offset]}]
  (when (needs? content room)
    (let [len (min track (max knob-least (* track (/ room content))))
          hi (most content room)]
      {:len len :pos (* (- track len) (/ (clamp offset hi) hi))})))

(defn offset-at
  "The place the content is at with the knob's start `pos` px along the track."
  [{:keys [track room content] :as geo} pos]
  (let [{:keys [len]} (knob (assoc geo :offset 0.0))
        run (- track len)
        hi (most content room)]
    (if (and len (pos? run)) (clamp (* hi (/ pos run)) hi) 0.0)))

(defn page-px
  "A page: the room less one line, so the last line seen is still there."
  [room]
  (max (/ room 2.0) (- room line-px)))

(defn pull
  "How far the content is drawn past an end when the fingers have gone `d` px
  past it: less and less the further they go, and never as far as a third of
  the room. The same way as `d`."
  [d room]
  (let [limit (* pull-share (double room))
        a (Math/abs (double d))]
    (if (or (zero? a) (<= limit 0.0))
      0.0
      (* (Math/signum (double d)) limit (- 1.0 (/ 1.0 (+ 1.0 (/ (* pull-give a) limit))))))))

(defn bounce-px
  "How far a glide that reaches an end at `speed` px an event bounces past it."
  [speed room]
  (min (* 0.5 pull-share (double room)) (* 3.0 (Math/abs (double speed)))))

(defn lock-axis
  "The axis a gesture keeps to: the one it moves more along."
  [dx dy]
  (if (> (Math/abs (double dx)) (Math/abs (double dy))) :x :y))

(def key-codes
  {KeyCode/UP :up KeyCode/DOWN :down KeyCode/LEFT :left KeyCode/RIGHT :right
   KeyCode/PAGE_UP :page-up KeyCode/PAGE_DOWN :page-down KeyCode/SPACE :space
   KeyCode/HOME :home KeyCode/END :end})

(defn key-move
  "What a key does to a focused area: which axis, and a line, a page or an end
  that way. Nil for a key that scrolls nothing."
  [key {:keys [shift alt shortcut]}]
  (case key
    :up (cond shortcut {:axis :y :to :start} alt {:axis :y :by :page :dir -1}
              :else {:axis :y :by :line :dir -1})
    :down (cond shortcut {:axis :y :to :end} alt {:axis :y :by :page :dir 1}
                :else {:axis :y :by :line :dir 1})
    :left {:axis :x :by :line :dir -1}
    :right {:axis :x :by :line :dir 1}
    :page-up {:axis :y :by :page :dir -1}
    :page-down {:axis :y :by :page :dir 1}
    :space {:axis :y :by :page :dir (if shift -1 1)}
    :home {:axis :y :to :start}
    :end {:axis :y :to :end}
    nil))

(defn key-target
  "Where a key's move takes the place `offset`: never past an end."
  [{:keys [offset room content]} {:keys [by dir to]}]
  (let [hi (most content room)]
    (clamp (case to
             :start 0.0
             :end hi
             (+ offset (* dir (if (= by :page) (page-px room) line-px))))
           hi)))

(defn reveal-offset
  "The place that brings the span from `lo` to `hi` into a room `room` long,
  `reveal-gap` clear of its edges, by the least move; where it is in sight
  already, the place stays. A span longer than the room stays where some of
  it is seen, and shows its start where none is."
  [offset room lo hi]
  (let [top (- lo reveal-gap)
        bottom (+ hi reveal-gap)]
    (cond
      (and (>= top offset) (<= bottom (+ offset room))) (double offset)
      ;; Longer than the room: where some of it is seen, it stays.
      (> (- bottom top) room) (if (and (< lo (+ offset room)) (> hi offset)) (double offset) (double top))
      (< top offset) (double top)
      :else (double (- bottom room)))))

(defn auto-speed
  "How many px a frame a drag `d` px in from an edge scrolls the area: faster
  the nearer the edge, the most at it and past it, and none from `auto-edge`."
  [d]
  (when (< d auto-edge)
    (max 2.0 (* auto-most (min 1.0 (- 1.0 (/ (max 0.0 d) auto-edge)))))))

(defn bar-look
  "How a bar is drawn: how thick its knob is, whether its track shows, and
  whether it takes its own room beside the content."
  [{:keys [overlay hovered]}]
  {:thick (cond (not overlay) bar-legacy hovered bar-wide :else bar-thin)
   :track (boolean (or (not overlay) hovered))
   :own-room (not overlay)})

(defn row-range
  "The rows to build, `row-h` px each, of `n`, with the room `room` px long at
  `offset`: those in view and a screen's worth either side."
  [n row-h offset room]
  (if (or (zero? n) (<= room 0.0))
    [0 0]
    [(int (max 0 (Math/floor (/ (- offset room) row-h))))
     (int (min n (Math/ceil (/ (+ offset (* 2.0 room)) row-h))))]))

;;; macOS's settings

;; :overlay - bars float and show when scrolling, as macOS decides it from
;;            "Show scroll bars" and what is plugged in
;; :jump    - a click in the track goes to the spot clicked, not a page
(defonce *settings (atom {:overlay true :jump false}))
;; Off in the checks, which set the settings themselves.
(defonce *follow-settings (atom true))

(defn parse-paging
  "What `defaults read -g AppleScrollerPagingBehavior` prints, as whether a
  click in the track goes to the spot clicked. Unset, it goes a page."
  [out]
  (= "1" (str/trim (str out))))

(defn parse-style
  "What NSScroller's preferredScrollerStyle prints, as whether the bars float:
  1 is overlay, 0 is legacy. Unread, they float, as macOS's do with a trackpad."
  [out]
  (not= "0" (str/trim (str out))))

(defn read-settings
  "macOS's scroll settings now. It runs two processes: call it off the UI
  thread. Elsewhere than macOS, and where they cannot be read, the defaults."
  []
  (let [run #(try (:out (apply shell/sh %&)) (catch Exception _ ""))]
    {:overlay (parse-style (run "osascript" "-l" "JavaScript" "-e"
                                "ObjC.import('AppKit'); $.NSScroller.preferredScrollerStyle"))
     :jump (parse-paging (run "defaults" "read" "-g" "AppleScrollerPagingBehavior"))}))

(defonce ^:private *watching (atom false))

(defn watch-settings!
  "Keeps `*settings` in step with macOS while the app runs: read now, again
  within 500 ms of a change to the global preferences, and every 5 s for a
  mouse or trackpad plugged in or out. Off the UI thread."
  []
  (when (compare-and-set! *watching false true)
    (let [prefs (io/file (System/getProperty "user.home") "Library" "Preferences"
                         ".GlobalPreferences.plist")]
      (doto (Thread. ^Runnable
                     (fn []
                       (loop [stamp -1 n 0]
                         (let [now (.lastModified prefs)]
                           (when (and @*follow-settings (or (not= now stamp) (zero? (mod n 10))))
                             (let [s (read-settings)]
                               (when (not= s @*settings) (reset! *settings s))))
                           (Thread/sleep 500)
                           (recur now (inc n)))))
                     "scroll-settings")
        (.setDaemon true)
        (.start)))))

;;; The area

(defn- handler ^EventHandler [f] (reify EventHandler (handle [_ e] (f e))))
(defn- listener ^ChangeListener [f] (reify ChangeListener (changed [_ _ _ _] (f))))

(defn- part ^Region [& classes]
  (doto (Region.)
    (.setManaged false)
    (.setMouseTransparent true)
    (-> .getStyleClass (.addAll ^java.util.Collection classes))))

;; The gesture under way, wherever it is: the area it stays with, and the axis.
(defonce ^:private *gesture (atom nil))

(defn area-of
  "The scroll area a node is in, the innermost, or nil."
  [^Node n]
  (loop [n (some-> n .getParent)]
    (cond (nil? n) nil
          (.containsKey (.getProperties n) ::parts) n
          :else (recur (.getParent n)))))

(defn- parts [^Node area] (.get (.getProperties area) ::parts))

(defn- within? [^Node outer ^Node n]
  (loop [n n] (cond (nil? n) false (identical? n outer) true :else (recur (.getParent n)))))

(defn reveal!
  "Scrolls `area` the least that brings `node`, inside its content, into sight,
  `reveal-gap` clear of the edge; and the areas round it, for the area."
  [^Node area ^Node node]
  (loop [area area node node]
    (when area
      ((:reveal! (parts area)) node)
      (recur (area-of area) area))))

(defn- install-scene!
  "Once a scene: a gesture goes on to the area it began in wherever the pointer
  goes, and a control given the focus out of sight is brought into sight."
  [^Scene scene]
  (when-not (.containsKey (.getProperties scene) ::installed)
    (.put (.getProperties scene) ::installed true)
    (.addEventFilter scene ScrollEvent/ANY
                     (handler (fn [^ScrollEvent e]
                                (let [{:keys [^Node area]} @*gesture
                                      target (.getTarget e)]
                                  (when (and area (instance? Node target)
                                             (not (within? area target))
                                             (not= ScrollEvent/SCROLL_STARTED (.getEventType e))
                                             (or (.isInertia e) (:touch @*gesture) (pos? (.getTouchCount e))
                                                 (= ScrollEvent/SCROLL_FINISHED (.getEventType e))))
                                    (.consume e)
                                    (Event/fireEvent area (.copyFor e area area)))))))
    ;; A click gives the focus where the pointer is, in sight already: only the
    ;; keyboard's focus scrolls.
    (.addEventFilter scene MouseEvent/MOUSE_PRESSED
                     (handler (fn [_] (.put (.getProperties scene) ::pressed-at (System/nanoTime)))))
    (.addListener (.focusOwnerProperty scene)
                  (reify ChangeListener
                    (changed [_ _ _ n]
                      (let [pressed (or (.get (.getProperties scene) ::pressed-at) 0)]
                        (when (and n (> (- (System/nanoTime) (long pressed)) 200000000))
                          (when-let [a (area-of n)] (reveal! a n)))))))))

(defn make-area
  "The control: a Pane that holds its content, clipped, and a bar for each
  axis. It is told what it is with `set-model!` and given its content with
  `set-content!`. It tells the app its place through the model's `on-place`."
  ^Pane []
  (let [model (atom {:axes #{:y}})
        content (atom nil)
        off {:x (SimpleDoubleProperty. 0.0) :y (SimpleDoubleProperty. 0.0)}
        ;; How far the content is drawn past an end, and where the fingers are.
        drawn {:x (SimpleDoubleProperty. 0.0) :y (SimpleDoubleProperty. 0.0)}
        stretch (volatile! {:x 0.0 :y 0.0})
        ;; Where an eased scroll is going, while it goes.
        aim (volatile! {})
        ;; The sizes of the last layout: the content's, the room's.
        geo (volatile! {:cw 0.0 :ch 0.0 :rw 0.0 :rh 0.0 :need #{}})
        anchor (volatile! nil)
        restored (volatile! false)
        bounced (volatile! false)
        hovered (atom #{})
        shown (atom #{})
        grab (atom nil)
        paging (atom nil)
        auto (volatile! nil)
        clip (Rectangle.)
        thick {:x (SimpleDoubleProperty. bar-thin) :y (SimpleDoubleProperty. bar-thin)}
        seen {:x (SimpleDoubleProperty. 0.0) :y (SimpleDoubleProperty. 0.0)}
        area-ref (volatile! nil)
        bar (fn [axis]
              (let [track (part "scroll-track")
                    k (part "scroll-knob")
                    holder (proxy [Pane] []
                             (queryAccessibleAttribute [attr params]
                               (let [{:keys [rw rh cw ch]} @geo
                                     [room c] (if (= axis :y) [rh ch] [rw cw])
                                     hi (most c room)]
                                 (condp = attr
                                   AccessibleAttribute/ORIENTATION
                                   (if (= axis :y) Orientation/VERTICAL Orientation/HORIZONTAL)
                                   AccessibleAttribute/VALUE (if (pos? hi) (/ (.get ^SimpleDoubleProperty (off axis)) hi) 0.0)
                                   AccessibleAttribute/MIN_VALUE 0.0
                                   AccessibleAttribute/MAX_VALUE 1.0
                                   AccessibleAttribute/VISIBLE true
                                   (let [^Pane this this] (proxy-super queryAccessibleAttribute attr params)))))
                             (executeAccessibleAction [action params]
                               (condp = action
                                 AccessibleAction/INCREMENT ((:page! (parts @area-ref)) axis 1)
                                 AccessibleAction/DECREMENT ((:page! (parts @area-ref)) axis -1)
                                 (let [^Pane this this] (proxy-super executeAccessibleAction action params)))))]
                (doto holder
                  (.setManaged false)
                  (.setCursor Cursor/DEFAULT)
                  (.setAccessibleRole AccessibleRole/SCROLL_BAR)
                  (.setAccessibleText (if (= axis :y) "Vertical scroll bar" "Horizontal scroll bar"))
                  (-> .getStyleClass (.addAll ^java.util.Collection ["scroll-bar-x" (name axis)]))
                  (-> .getChildren (.addAll ^java.util.Collection [track k])))
                {:holder holder :track track :knob k}))
        bars {:x (bar :x) :y (bar :y)}
        corner (part "scroll-corner")
        band (part "scroll-glass-edge")
        hide {:x (PauseTransition. (Duration/millis show-ms)) :y (PauseTransition. (Duration/millis show-ms))}
        keep-timer (PauseTransition. (Duration/millis keep-ms))
        latch-timer (PauseTransition. (Duration/millis latch-ms))
        repeat-timer (PauseTransition. (Duration/millis repeat-ms))
        ;; Along an axis it scrolls, the area is the size it is given; along
        ;; the other, its content's, and a bar's that takes room.
        pref-w (fn []
                 (let [{:keys [axes width]} @model]
                   (if (axes :x) (double (or width 200.0))
                       (+ (if-let [^Node c @content] (.prefWidth c -1.0) 0.0)
                          (if (and (axes :y) (not (:overlay @*settings))) bar-legacy 0.0)))))
        pref-h (fn []
                 (let [{:keys [axes height]} @model]
                   (if (axes :y) (double (or height 200.0))
                       (+ (if-let [^Node c @content] (.prefHeight c -1.0) 0.0)
                          (if (and (axes :x) (not (:overlay @*settings))) bar-legacy 0.0)))))
        area (proxy [Pane] []
               (layoutChildren [] ((:layout! (parts this))))
               (computePrefWidth [_] (pref-w))
               (computePrefHeight [_] (pref-h))
               (computeMinWidth [_] (if (:x (:axes @model)) 0.0 (pref-w)))
               (computeMinHeight [_] (if (:y (:axes @model)) 0.0 (pref-h)))
               (queryAccessibleAttribute [attr params]
                 (condp = attr
                   AccessibleAttribute/VERTICAL_SCROLLBAR (when ((:need @geo) :y) (:holder (:y bars)))
                   AccessibleAttribute/HORIZONTAL_SCROLLBAR (when ((:need @geo) :x) (:holder (:x bars)))
                   AccessibleAttribute/CONTENTS @content
                   (let [^Pane this this] (proxy-super queryAccessibleAttribute attr params)))))
        g (fn [k] (get @geo k))
        room-of (fn [axis] (g (if (= axis :y) :rh :rw)))
        size-of (fn [axis] (g (if (= axis :y) :ch :cw)))
        hi-of (fn [axis] (most (size-of axis) (room-of axis)))
        scrolls? (fn [axis] (boolean ((:need @geo) axis)))
        at (fn [axis] (.get ^SimpleDoubleProperty (off axis)))
        ;; Can the content move `d` px the way a scroll of `d` moves it.
        can-move? (fn [axis d]
                    (and (scrolls? axis)
                         (if (pos? d) (> (at axis) 0.0) (< (at axis) (hi-of axis)))))
        outer-can? (fn [axis d]
                     (loop [a (area-of area)]
                       (cond (nil? a) false
                             ((:can-move? (parts a)) axis d) true
                             :else (recur (area-of a)))))
        overlay? #(boolean (:overlay @*settings))
        ;;; Drawing
        place! (fn []
                 (when-let [^Node c @content]
                   (let [{:keys [rw rh cw ch need]} @geo
                         w (.getWidth area) h (.getHeight area)
                         legacy (not (overlay?))]
                     (.relocate c (+ (- (at :x)) (.get ^SimpleDoubleProperty (drawn :x)))
                                (+ (- (at :y)) (.get ^SimpleDoubleProperty (drawn :y))))
                     (doseq [axis axes
                             :let [{^Pane holder :holder ^Region track :track ^Region kn-node :knob} (bars axis)
                                   on (boolean (need axis))
                                   both (and legacy (need :x) (need :y))
                                   t (.get ^SimpleDoubleProperty (thick axis))
                                   edge (if legacy bar-legacy bar-edge)
                                   len (if (= axis :y) (if both rh h) (if both rw w))
                                   inset (if legacy 0.0 bar-in)
                                   track-len (- len (* 2.0 inset) (if (and (not legacy) (need :x) (need :y)) bar-edge 0.0))
                                   kn (knob {:track track-len :room (room-of axis) :content (size-of axis)
                                             :offset (at axis)})]]
                       (.setVisible holder on)
                       (when (and on kn)
                         (let [;; Across the bar: the knob sits `inset` px in from the outer edge.
                               across (- edge inset t)
                               {klen :len kpos :pos} kn
                               lead (+ inset kpos)]
                           (if (= axis :y)
                             (do (.resizeRelocate holder (- w edge) 0.0 edge len)
                                 (.resizeRelocate track 0.0 0.0 edge len)
                                 (.resizeRelocate kn-node (if legacy (/ (- edge t) 2.0) across) lead (if legacy (- t 6.0) t) klen))
                             (do (.resizeRelocate holder 0.0 (- h edge) len edge)
                                 (.resizeRelocate track 0.0 0.0 len edge)
                                 (.resizeRelocate kn-node lead (if legacy (/ (- edge t) 2.0) across) klen (if legacy (- t 6.0) t)))))))
                     (.setVisible corner (boolean (and legacy (need :x) (need :y))))
                     (.resizeRelocate corner (- w bar-legacy) (- h bar-legacy) bar-legacy bar-legacy)
                     (when-let [f (.get (.getProperties c) ::on-view)]
                       (f (at :x) (at :y) rw rh)))))
        ;;; The bars show, fade and grow
        look! (fn [axis]
                (let [legacy (not (overlay?))
                      looks (bar-look {:overlay (not legacy) :hovered (@hovered axis)})
                      {:keys [^Pane holder ^Region track]} (bars axis)
                      v (if (or legacy (@shown axis)) 1.0 0.0)]
                  (ui/tween! holder ::grow {:ms (if (or legacy @ui/*reduce) 0 grow-ms)}
                             [[(thick axis) (:thick looks)]
                              [(.opacityProperty track) (if (:track looks) 1.0 0.0)]])
                  (.setMouseTransparent holder (and (not legacy) (zero? v) (not (@hovered axis))))))
        fade! (fn [axis]
                (when-not (or (@hovered axis) (= axis (:axis @grab)))
                  (let [{:keys [^Pane holder]} (bars axis)]
                    (ui/tween! holder ::fade {:ms (if @ui/*reduce 0 fade-ms)
                                              :on-done (fn [] (swap! shown disj axis) (look! axis))}
                               [[(.opacityProperty holder) 0.0]]))))
        show! (fn [axis]
                (let [{:keys [^Pane holder]} (bars axis)]
                  (if (overlay?)
                    (do (swap! shown conj axis)
                        (ui/tween! holder ::fade {:ms 0} [[(.opacityProperty holder) 1.0]])
                        (look! axis)
                        (.playFromStart ^PauseTransition (hide axis)))
                    (.setOpacity holder 1.0))))
        settle-bars! (fn []
                       (doseq [axis axes]
                         (if (overlay?)
                           (when-not (@shown axis) (.setOpacity ^Pane (:holder (bars axis)) 0.0))
                           (.setOpacity ^Pane (:holder (bars axis)) 1.0))
                         (look! axis)))
        ;;; Moving
        set-at! (fn [axis v] (.set ^SimpleDoubleProperty (off axis) (clamp v (hi-of axis))))
        stop-ease! (fn [axis] (ui/tween! area [::ease axis] {:ms 0} []) (vswap! aim dissoc axis))
        ease! (fn [axis to ms]
                (let [to (clamp to (hi-of axis))]
                  (vswap! aim assoc axis to)
                  (ui/tween! area [::ease axis] {:ms (if @ui/*reduce 0 ms)
                                                 :on-done #(vswap! aim dissoc axis)}
                             [[(off axis) to]])))
        spring-back! (fn [axis]
                       (vswap! stretch assoc axis 0.0)
                       (ui/tween! area [::pull axis] {:ms (if (zero? (.get ^SimpleDoubleProperty (drawn axis))) 0 back-ms)}
                                  [[(drawn axis) 0.0]]))
        ;; The fingers move the content `d` px: one to one, and past an end
        ;; with less and less give.
        touch! (fn [axis d]
                 (ui/tween! area [::pull axis] {:ms 0} [])
                 (stop-ease! axis)
                 (let [hi (hi-of axis)
                       raw (- (+ (at axis) (get @stretch axis)) d)
                       edge (clamp raw hi)
                       over (- raw edge)]
                   (set-at! axis edge)
                   (vswap! stretch assoc axis over)
                   (.set ^SimpleDoubleProperty (drawn axis) (- (pull over (room-of axis))))))
        ;; macOS's glide after the fingers lift: on to an end, and a bounce there.
        glide! (fn [axis d]
                 (when-not @bounced
                   (let [hi (hi-of axis)
                         raw (- (at axis) d)]
                     (if (<= 0.0 raw hi)
                       (set-at! axis raw)
                       (do (set-at! axis (clamp raw hi))
                           (vreset! bounced true)
                           (when-not @ui/*reduce
                             (let [amp (* (if (neg? raw) 1.0 -1.0) (bounce-px d (room-of axis)))]
                               (ui/tween! area [::pull axis]
                                          {:ms grow-ms
                                           :on-done #(ui/tween! area [::pull axis] {:ms back-ms}
                                                                [[(drawn axis) 0.0]])}
                                          [[(drawn axis) amp]]))))))))
        ;; A notched wheel: a line a notch, eased, and no give at an end.
        wheel! (fn [axis d]
                 (ease! axis (- (get @aim axis (at axis)) d) wheel-ms))
        release-latch! (fn []
                         (when (identical? area (:area @*gesture))
                           (reset! *gesture nil))
                         (doseq [axis axes]
                           (when-not (zero? (get @stretch axis)) (spring-back! axis))))
        on-scroll (fn [^ScrollEvent e]
                    (let [type (.getEventType e)
                          gest @*gesture]
                      (cond
                        (= type ScrollEvent/SCROLL_STARTED)
                        ;; Fingers down: a glide under way stops where it is.
                        (do (when (and (:area gest) (:glide gest))
                              (reset! *gesture nil))
                            (when-not (:touch @*gesture)
                              (reset! *gesture {:touch true}))
                            (vreset! bounced false))

                        (= type ScrollEvent/SCROLL_FINISHED)
                        (when (identical? area (:area gest))
                          (.consume e)
                          (swap! *gesture assoc :touch false)
                          (doseq [axis axes]
                            (when-not (zero? (get @stretch axis)) (spring-back! axis)))
                          (.playFromStart latch-timer))

                        :else
                        (let [lines? (= ScrollEvent$VerticalTextScrollUnits/LINES (.getTextDeltaYUnits e))
                              lines-x? (= ScrollEvent$HorizontalTextScrollUnits/CHARACTERS (.getTextDeltaXUnits e))
                              dy (if lines? (* line-px (.getTextDeltaY e)) (.getDeltaY e))
                              dx (.getDeltaX e)
                              ;; Shift and the wheel scroll sideways.
                              [dx dy] (if (and (.isShiftDown e) (zero? dx)) [dy 0.0] [dx dy])
                              inertia (.isInertia e)
                              kind (cond inertia :glide
                                         (or (:touch gest) (pos? (.getTouchCount e))) :touch
                                         :else :wheel)]
                          (cond
                            ;; Taken by an area already: it stays there.
                            (and (not= kind :wheel) (:area gest))
                            (when (identical? area (:area gest))
                              (.consume e)
                              (let [axis (:axis gest)
                                    d (if (= axis :y) dy dx)]
                                (if (= kind :glide)
                                  (do (swap! *gesture assoc :glide true) (glide! axis d))
                                  (touch! axis d)))
                              (.playFromStart latch-timer))

                            (= kind :wheel)
                            (let [axis (if (zero? dy) :x (lock-axis dx dy))
                                  d (if (= axis :y) dy dx)]
                              (when (and (not (zero? d)) (can-move? axis d))
                                (.consume e)
                                (wheel! axis d)))

                            ;; A new gesture: the area takes it if it can move
                            ;; that way, or if no area round it can.
                            :else
                            (let [axis (lock-axis dx dy)
                                  d (if (= axis :y) dy dx)]
                              (when (and (not (zero? d)) (scrolls? axis)
                                         (or (can-move? axis d) (not (outer-can? axis d))))
                                (.consume e)
                                (vreset! bounced false)
                                (reset! *gesture {:area area :axis axis :touch (= kind :touch)
                                                  :glide (= kind :glide)})
                                (if (= kind :glide) (glide! axis d) (touch! axis d))
                                (.playFromStart latch-timer))))))))
        ;;; The knob and the track
        along (fn [axis ^MouseEvent e]
                (let [p (.sceneToLocal area (.getSceneX e) (.getSceneY e))]
                  (if (= axis :y) (.getY p) (.getX p))))
        bar-geo (fn [axis]
                  (let [{:keys [^Region knob ^Pane holder]} (bars axis)]
                    {:track (- (if (= axis :y) (.getHeight holder) (.getWidth holder))
                               (* 2.0 (if (overlay?) bar-in 0.0))
                               (if (and (overlay?) (scrolls? :x) (scrolls? :y)) bar-edge 0.0))
                     :inset (if (overlay?) bar-in 0.0)
                     :lead (if (= axis :y) (.getLayoutY knob) (.getLayoutX knob))
                     :len (if (= axis :y) (.getHeight knob) (.getWidth knob))
                     :room (room-of axis) :content (size-of axis)}))
        page! (fn [axis dir]
                (ease! axis (+ (get @aim axis (at axis)) (* dir (page-px (room-of axis)))) key-ms))
        page-on! (fn []
                   (when-let [{:keys [axis dir p]} @paging]
                     (let [{:keys [lead len]} (bar-geo axis)]
                       (if (if (pos? dir) (> p (+ lead len)) (< p lead))
                         (do (set-at! axis (+ (at axis) (* dir (page-px (room-of axis)))))
                             (show! axis)
                             (.playFromStart repeat-timer))
                         (reset! paging nil)))))
        on-bar-press (fn [axis ^MouseEvent e]
                       (when (= MouseButton/PRIMARY (.getButton e))
                         (.consume e)
                         (stop-ease! axis)
                         (let [p (along axis e)
                               {:keys [lead len inset] :as bg} (bar-geo axis)
                               jump (not= (boolean (:jump @*settings)) (.isAltDown e))]
                           (cond
                             (<= lead p (+ lead len))
                             (reset! grab {:axis axis :start (at axis) :grab (- p lead)})
                             jump
                             (do (set-at! axis (offset-at bg (- p inset (/ len 2.0))))
                                 (reset! grab {:axis axis :start (at axis) :grab (/ len 2.0)}))
                             :else
                             (do (reset! paging {:axis axis :dir (if (< p lead) -1 1) :p p})
                                 (page-on!)))
                           (show! axis))))
        on-bar-drag (fn [axis ^MouseEvent e]
                      (.consume e)
                      (when-let [{:keys [grab] :as gr} @grab]
                        (when (= axis (:axis gr))
                          (let [{:keys [inset] :as bg} (bar-geo axis)]
                            (set-at! axis (offset-at bg (- (along axis e) inset grab))))))
                      (when @paging (swap! paging assoc :p (along axis e))))
        on-bar-release (fn [axis ^MouseEvent e]
                         (.consume e)
                         (reset! grab nil)
                         (reset! paging nil)
                         (.stop repeat-timer)
                         (.playFromStart ^PauseTransition (hide axis)))
        ;;; The pointer near a floating bar
        on-move (fn [^MouseEvent e]
                  (when (overlay?)
                    (let [p (.sceneToLocal area (.getSceneX e) (.getSceneY e))
                          near {:y (and (scrolls? :y) (>= (.getX p) (- (.getWidth area) bar-edge)))
                                :x (and (scrolls? :x) (>= (.getY p) (- (.getHeight area) bar-edge)))}]
                      (doseq [axis axes]
                        (cond
                          (and (near axis) (not (@hovered axis)))
                          (do (swap! hovered conj axis) (show! axis))
                          (and (not (near axis)) (@hovered axis) (not= axis (:axis @grab)))
                          (do (swap! hovered disj axis) (look! axis)
                              (.playFromStart ^PauseTransition (hide axis))))))))
        on-exit (fn [_]
                  (doseq [axis axes]
                    (when (and (@hovered axis) (not= axis (:axis @grab)))
                      (swap! hovered disj axis) (look! axis)
                      (.playFromStart ^PauseTransition (hide axis)))))
        ;;; Keys
        on-key (fn [^KeyEvent e]
                 (let [code (.getCode e)]
                   (cond
                     (and (= KeyCode/ESCAPE code) @grab)
                     (let [{:keys [axis start]} @grab]
                       (.consume e)
                       (reset! grab nil)
                       (set-at! axis start))

                     (instance? TextInputControl (.getTarget e)) nil

                     :else
                     (when-let [mv (key-move (key-codes code)
                                             {:shift (.isShiftDown e) :alt (.isAltDown e)
                                              :shortcut (.isShortcutDown e)})]
                       (let [axis (:axis mv)
                             from (get @aim axis (at axis))
                             to (when (scrolls? axis)
                                  (key-target {:offset from :room (room-of axis) :content (size-of axis)} mv))]
                         (when (and to (not= to from))
                           (.consume e)
                           (ease! axis to key-ms)))))))
        ;;; Bringing into sight
        reveal-node! (fn [^Node n]
                       (when-let [^Node c @content]
                         (when (within? c n)
                           (let [b (.sceneToLocal c (.localToScene n (.getLayoutBounds n)))]
                             (doseq [axis axes :when (scrolls? axis)]
                               (let [[lo hi] (if (= axis :y) [(.getMinY b) (.getMaxY b)] [(.getMinX b) (.getMaxX b)])
                                     from (get @aim axis (at axis))
                                     to (clamp (reveal-offset from (room-of axis) lo hi) (hi-of axis))]
                                 (when (> (Math/abs (- to from)) 0.5) (ease! axis to key-ms))))))))
        reveal-span! (fn [axis lo hi]
                       (when (scrolls? axis)
                         (let [from (get @aim axis (at axis))
                               to (clamp (reveal-offset from (room-of axis) lo hi) (hi-of axis))]
                           (when (> (Math/abs (- to from)) 0.5) (ease! axis to key-ms)))))
        ;;; A drag near an edge
        auto-timer (proxy [AnimationTimer] []
                     (handle [_]
                       (when-let [{:keys [axis speed]} @auto]
                         (set-at! axis (+ (at axis) speed)))))
        auto! (fn [^double sx ^double sy]
                (let [p (.sceneToLocal area sx sy)
                      pick (fn [axis]
                             (when (scrolls? axis)
                               (let [v (if (= axis :y) (.getY p) (.getX p))
                                     len (room-of axis)]
                                 (or (some-> (auto-speed v) (* -1.0) (#(hash-map :axis axis :speed %)))
                                     (some->> (auto-speed (- len v)) (hash-map :axis axis :speed))))))
                      a (or (pick :y) (pick :x))]
                  (vreset! auto a)
                  (if a (.start auto-timer) (.stop auto-timer))))
        stop-auto! (fn [] (vreset! auto nil) (.stop auto-timer))
        drag-selects? (fn [^Node n]
                        (loop [n n]
                          (cond (or (nil? n) (identical? n area)) false
                                (.get (.getProperties n) ::drag-selects) true
                                :else (recur (.getParent n)))))
        ;; The row first seen, so a change above it leaves it where it is.
        note-anchor! (fn []
                       (when-let [^Node c @content]
                         (vreset! anchor
                                  (if-let [f (.get (.getProperties c) ::anchor)]
                                    (f (at :y))
                                    (when (instance? Parent c)
                                      (let [y (at :y)]
                                        (some (fn [^Node k]
                                                (let [b (.getBoundsInParent k)]
                                                  (when (> (.getMaxY b) y)
                                                    {:rel (- (.getMinY b) y)
                                                     :anchor-at #(when (identical? (.getParent k) c)
                                                                   (.getMinY (.getBoundsInParent k)))})))
                                              (.getChildrenUnmodifiable ^Parent c))))))))
        ;;; Layout
        layout! (fn []
                  (when-let [^Node c @content]
                    (let [{:keys [axes follow-end place on-place]} @model
                          w (.getWidth area) h (.getHeight area)
                          legacy (not (overlay?))
                          before @geo
                          size (fn [need]
                                 (let [rw (- w (if (and legacy (need :y)) bar-legacy 0.0))
                                       rh (- h (if (and legacy (need :x)) bar-legacy 0.0))
                                       cw (if (axes :x) (max rw (.prefWidth c -1.0)) rw)
                                       ch (if (axes :y) (max rh (.prefHeight c cw)) rh)]
                                   {:rw rw :rh rh :cw cw :ch ch}))
                          need-of (fn [{:keys [rw rh cw ch]}]
                                    (cond-> #{}
                                      (and (axes :x) (needs? cw rw)) (conj :x)
                                      (and (axes :y) (needs? ch rh)) (conj :y)))
                          s0 (size #{})
                          n0 (need-of s0)
                          s1 (size n0)
                          n1 (need-of s1)
                          s (if (= n0 n1) s1 (size n1))
                          need (need-of s)
                          {:keys [cw ch rw rh]} s
                          ;; Where the content stood before this change: its end, or the
                          ;; row first seen.
                          was-end (and follow-end ((:need before) :y)
                                       (>= (at :y) (- (most (:ch before) (:rh before)) 1.0)))
                          was-anchor @anchor]
                      (.resize c cw ch)
                      (when (instance? Parent c) (.layout ^Parent c))
                      (vreset! geo (assoc s :need need))
                      (.setWidth clip rw)
                      (.setHeight clip rh)
                      (cond
                        (and place (not @restored) (pos? ch))
                        (do (vreset! restored true)
                            (set-at! :x (first place))
                            (set-at! :y (second place)))
                        (and follow-end (or was-end (and (not ((:need before) :y)) (need :y))))
                        (set-at! :y (most ch rh))
                        (and was-anchor (not= (:ch before) ch))
                        (when-let [y ((:anchor-at was-anchor))]
                          (stop-ease! :y)
                          (set-at! :y (- y (:rel was-anchor))))
                        :else (doseq [axis axes] (set-at! axis (at axis))))
                      ;; Content that grows, or an area first seen with more: the bar shows for 1 s.
                      (doseq [axis [:x :y]]
                        (when (and (need axis)
                                   (or (not ((:need before) axis))
                                       (> (size-of axis) (+ 1.0 (get before (if (= axis :y) :ch :cw))))))
                          (when (overlay?) (show! axis))))
                      (when-not (= (:need before) need) (settle-bars!))
                      (place!)
                      (note-anchor!))))
        moved! (fn [axis]
                 (place!)
                 (show! axis)
                 (note-anchor!)
                 (.notifyAccessibleAttributeChanged ^Pane (:holder (bars axis)) AccessibleAttribute/VALUE)
                 (.playFromStart keep-timer))]
    (vreset! area-ref area)
    (doseq [axis axes]
      (.addListener ^SimpleDoubleProperty (off axis) (listener #(moved! axis)))
      (.addListener ^SimpleDoubleProperty (drawn axis) (listener place!))
      (.addListener ^SimpleDoubleProperty (thick axis) (listener place!))
      (.setOnFinished ^PauseTransition (hide axis) (handler (fn [_] (fade! axis))))
      (let [{:keys [^Pane holder ^Region track]} (bars axis)]
        (.setOpacity track 0.0)
        (.setOpacity holder 0.0)
        (.addEventHandler holder MouseEvent/MOUSE_PRESSED (handler #(on-bar-press axis %)))
        (.addEventHandler holder MouseEvent/MOUSE_DRAGGED (handler #(on-bar-drag axis %)))
        (.addEventHandler holder MouseEvent/MOUSE_RELEASED (handler #(on-bar-release axis %)))))
    (.setOnFinished keep-timer (handler (fn [_] (when-let [f (:on-place @model)] (f [(at :x) (at :y)])))))
    (.setOnFinished latch-timer (handler (fn [_] (release-latch!))))
    (.setOnFinished repeat-timer (handler (fn [_] (page-on!))))
    (.addEventHandler area ScrollEvent/ANY (handler on-scroll))
    (.addEventFilter area MouseEvent/MOUSE_MOVED (handler on-move))
    (.addEventHandler area MouseEvent/MOUSE_EXITED (handler on-exit))
    (.addEventHandler area KeyEvent/KEY_PRESSED (handler on-key))
    ;; A click in the area gives it the keys, unless it lands on a control.
    (.addEventFilter area MouseEvent/MOUSE_PRESSED
                     (handler (fn [^MouseEvent e]
                                (let [t (.getTarget e)]
                                  (when (and (instance? Node t)
                                             (not (loop [^Node n t]
                                                    (cond (or (nil? n) (identical? n area)) false
                                                          (.isFocusTraversable n) true
                                                          :else (recur (.getParent n))))))
                                    (.requestFocus area))))))
    (.addEventFilter area MouseEvent/MOUSE_DRAGGED
                     (handler (fn [^MouseEvent e]
                                (if (and (not @grab) (drag-selects? (.getTarget e)))
                                  (auto! (.getSceneX e) (.getSceneY e))
                                  (stop-auto!)))))
    (.addEventFilter area MouseEvent/MOUSE_RELEASED (handler (fn [_] (stop-auto!))))
    (.addEventFilter area DragEvent/DRAG_OVER
                     (handler (fn [^DragEvent e] (auto! (.getSceneX e) (.getSceneY e)))))
    (.addEventFilter area DragEvent/DRAG_EXITED (handler (fn [_] (stop-auto!))))
    (.addEventFilter area DragEvent/DRAG_DROPPED (handler (fn [_] (stop-auto!))))
    (.addListener (.sceneProperty area)
                  (reify ChangeListener (changed [_ _ _ s] (when s (install-scene! s)))))
    (add-watch *settings area (fn [_ _ old new]
                                (when (not= old new)
                                  (Platform/runLater (fn [] (.requestLayout area) (settle-bars!))))))
    (.put (.getProperties area) ::parts
          {:model model :content content :off off :drawn drawn :geo geo :bars bars
           :shown shown :hovered hovered :band band :corner corner
           :can-move? can-move? :reveal! reveal-node! :reveal-span! reveal-span!
           :page! page! :layout! layout! :place! place! :settle-bars! settle-bars!
           :thick thick})
    (doto area
      (.setClip clip)
      (-> .getStyleClass (.add "scroll-area"))
      (.setAccessibleRole AccessibleRole/SCROLL_PANE)
      (.setFocusTraversable true)
      (-> .getChildren (.addAll ^java.util.Collection
                                [band corner (:holder (:x bars)) (:holder (:y bars))])))))

(defn set-content!
  "Gives the area its content: one node, which it sizes and moves."
  [^Pane area ^Node node]
  (let [{:keys [content]} (parts area)
        kids (.getChildren area)]
    (when-let [^Node old @content] (.remove kids old))
    (reset! content node)
    (when node (.add kids 0 node))
    (.requestLayout area)))

(defn set-model!
  "Tells the area what it is: `:id`; `:axes`, the set of :x and :y it scrolls
  along; `:width` and `:height`, its size along an axis it scrolls; `:name`,
  what a screen reader calls it; `:follow-end`, a log's: it stays at its
  newest line while it is at the bottom; `:glass`, how far down from its top
  glass floats over it; `:place`, the [x y] it opens at, used once; and
  `:on-place`, called with [x y] once the place has been still for `keep-ms`."
  [^Pane area m]
  (let [{:keys [model ^Region band]} (parts area)
        m (update m :axes #(set (or % #{:y})))
        old @model]
    (reset! model m)
    (.setId area (:id m))
    (.setAccessibleText area (:name m))
    (when-let [glass (:glass m)]
      (.setStyle band (format "-fx-background-color: linear-gradient(to bottom, rgba(14,14,18,0.62) 0%%, rgba(14,14,18,0.62) %.1f%%, transparent 100%%);"
                              (* 100.0 (/ glass (+ glass glass-fade))))))
    (when (not= (select-keys old [:axes :width :height :glass]) (select-keys m [:axes :width :height :glass]))
      (.requestLayout area))))

;; Content under glass softens at the glass's edge once something is under it.
(defn- glass-band! [^Pane area]
  (let [{:keys [model ^Region band off]} (parts area)]
    (.addListener ^SimpleDoubleProperty (:y off)
                  (listener (fn []
                              (when-let [glass (:glass @model)]
                                (.resizeRelocate band 0.0 0.0 (.getWidth area) (+ glass glass-fade))
                                (ui/tween! band ::under {:ms (if @ui/*reduce 0 ui/fade-ms)}
                                           [[(.opacityProperty band)
                                             (if (> (.get ^SimpleDoubleProperty (:y off)) 0.5) 1.0 0.0)]])))))
    (.setOpacity band 0.0)))

(def ext-area
  (fx/make-ext-with-props
    {::model (prop/make (mutator/setter set-model!) lifecycle/scalar)
     ::content (prop/make (mutator/setter set-content!) lifecycle/dynamic)}))

(defn- new-area
  "One var, so cljfx keeps the same area from render to render: a new
  function each time would build a new area each time, at the top."
  []
  (doto (make-area) glass-band!))

(defn scroll-view
  "One scroll area round `content`, a cljfx description; the rest is the model
  `set-model!` takes."
  [{:keys [content] :as props}]
  {:fx/type ext-area
   :props {::model (dissoc props :content :fx/type) ::content content}
   :desc {:fx/type fx/ext-instance-factory :create new-area}})

;;; Rows: content that builds only those in view

(declare reveal-row!)

(defn make-rows
  "Content for a scroll area that holds `n` rows, `row-h` px each, and builds
  only those in view and a screen's worth either side, so a list of 100,000
  scrolls as one of 100 does. Told what it is with `set-rows!`. A press marks
  a row and a drag chooses the rows it runs over, scrolling the area near its
  edge; Up and Down move the mark."
  ^Pane []
  (let [model (atom {:n 0 :row-h 32.0})
        built (atom {})
        view (volatile! [0.0 0.0 0.0 0.0])
        pane (proxy [Pane] []
               (computePrefHeight [_] (* (:n @model) (:row-h @model)))
               (computePrefWidth [_] 240.0)
               (layoutChildren [] ((:draw! (.get (.getProperties ^Pane this) ::rows)))))
        draw! (fn []
                (let [{:keys [n row-h text-of key-of marked chosen]} @model
                      [_ oy _ rh] @view
                      [lo hi] (row-range n row-h oy rh)
                      w (.getWidth pane)
                      kids (.getChildren pane)
                      keep (set (range lo hi))
                      old @built
                      spare (atom (vec (for [[i l] old :when (not (keep i))] l)))
                      now (into {} (for [i (range lo hi)]
                                     [i (or (old i)
                                            (if-let [l (peek @spare)]
                                              (do (swap! spare pop) l)
                                              (let [l (doto (Label.)
                                                        (.setManaged false)
                                                        (-> .getStyleClass (.add "scroll-row")))]
                                                (.add kids l)
                                                l)))]))]
                  (.removeAll kids ^java.util.Collection @spare)
                  (reset! built now)
                  (doseq [[i ^Label l] now
                          :let [t (when text-of (text-of i))
                                k (when key-of (key-of i))]]
                    (.setText l (or t "Loading"))
                    (.pseudoClassStateChanged l (javafx.css.PseudoClass/getPseudoClass "pending") (nil? t))
                    (.pseudoClassStateChanged l (javafx.css.PseudoClass/getPseudoClass "marked") (and k (= k marked)))
                    (.pseudoClassStateChanged l (javafx.css.PseudoClass/getPseudoClass "chosen") (boolean (and k chosen (chosen k))))
                    (.resizeRelocate l 0.0 (* i row-h) w row-h))))]
    (.put (.getProperties pane) ::rows {:model model :built built :draw! draw!})
    (.put (.getProperties pane) ::on-view (fn [ox oy rw rh]
                                            (let [[_ py _ ph] @view]
                                              (vreset! view [ox oy rw rh])
                                              (when (or (not= py oy) (not= ph rh)) (draw!)))))
    (.put (.getProperties pane) ::drag-selects true)
    ;; A press marks a row, a drag chooses the rows it runs over, and Up and
    ;; Down move the mark, bringing it into sight.
    (let [index-at (fn [^MouseEvent e]
                     (let [{:keys [n row-h]} @model
                           y (.getY (.sceneToLocal pane (.getSceneX e) (.getSceneY e)))]
                       (-> (Math/floor (/ y row-h)) int (max 0) (min (dec n)))))
          from (volatile! nil)
          tell (fn [k & args] (when-let [f (k @model)] (apply f args)))]
      (.addEventHandler pane MouseEvent/MOUSE_PRESSED
                        (handler (fn [^MouseEvent e]
                                   (when (pos? (:n @model))
                                     (.requestFocus pane)
                                     (let [i (index-at e)]
                                       (vreset! from i)
                                       (tell :on-mark i)
                                       (tell :on-choose i i))))))
      (.addEventHandler pane MouseEvent/MOUSE_DRAGGED
                        (handler (fn [^MouseEvent e]
                                   (when-let [i0 @from]
                                     (let [i (index-at e)] (tell :on-choose (min i0 i) (max i0 i)))))))
      (.addEventHandler pane MouseEvent/MOUSE_RELEASED (handler (fn [_] (vreset! from nil))))
      (.addEventHandler pane KeyEvent/KEY_PRESSED
                        (handler (fn [^KeyEvent e]
                                   (let [{:keys [n marked index-of]} @model
                                         now (if (and marked index-of) (index-of marked) -1)
                                         step ({KeyCode/DOWN 1 KeyCode/UP -1} (.getCode e))]
                                     (when (and step (pos? n) (not (.isShortcutDown e)) (not (.isAltDown e)))
                                       (.consume e)
                                       (let [i (-> (+ now step) (max 0) (min (dec n)))]
                                         (tell :on-mark i)
                                         (tell :on-choose i i)
                                         (reveal-row! pane i))))))))
    (.setFocusTraversable pane true)
    ;; The row first seen, by its key, so rows added above leave it in place.
    (.put (.getProperties pane) ::anchor
          (fn [y]
            (let [{:keys [row-h key-of index-of n]} @model]
              (when (and key-of index-of (pos? n))
                (let [i (min (dec n) (int (Math/floor (/ y row-h))))
                      k (key-of i)]
                  {:rel (- (* i row-h) y)
                   :anchor-at #(some-> (:index-of @model) (apply [k]) (* (:row-h @model)))})))))
    (-> pane .getStyleClass (.add "scroll-rows"))
    pane))

(defn set-rows!
  "Tells the rows what they are: `:n` of them, `:row-h` px each, `:text-of`
  the words of row i or nil while they load, `:key-of` and `:index-of` a row's
  key and back, the `:marked` key and the `:chosen` set of keys, and
  `:on-mark` with a row's index and `:on-choose` with the first and last."
  [^Pane pane m]
  (let [{:keys [model draw!]} (.get (.getProperties pane) ::rows)
        old @model]
    (reset! model (merge {:row-h 32.0} m))
    (.setId pane (:id m))
    (when (not= (:n old) (:n m)) (.requestLayout pane))
    (draw!)))

(defn rows-built
  "How many rows are built now."
  [^Pane pane]
  (count @(:built (.get (.getProperties pane) ::rows))))

(def ext-rows
  (fx/make-ext-with-props
    {::rows (prop/make (mutator/setter set-rows!) lifecycle/scalar)}))

(defn rows-view
  "The rows, as a cljfx description: the model `set-rows!` takes, and `:id`."
  [props]
  {:fx/type ext-rows
   :props {::rows (dissoc props :fx/type)}
   :desc {:fx/type fx/ext-instance-factory :create make-rows}})

(defn reveal-row!
  "Scrolls the area round `rows` the least that brings row `i` into sight."
  [^Pane rows i]
  (let [{:keys [model]} (.get (.getProperties rows) ::rows)
        h (:row-h @model)]
    (when-let [a (area-of rows)]
      ((:reveal-span! (parts a)) :y (* i h) (* (inc i) h)))))
