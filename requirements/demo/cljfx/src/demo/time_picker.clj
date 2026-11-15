(ns demo.time-picker
  "The part worth copying: a time picker that sets one time of day, as Time
  pickers in requirements/components.org asks. A reference, not a library:
  follow what it does, and take the code as one way to do it. Nothing here
  knows about the demo's page or its state (demo.time-picker-page).

  One field that is typed into, with wheels under it. What is typed is read
  forgivingly, \"9a\", \"930a\", \"2130\", \"noon\", and shown in full once it
  is taken. An hour that could be morning or afternoon is never guessed at:
  the field asks. The wheels - hour, minute and AM/PM, or hour and minute on a
  24-hour clock - turn like a drum: dragged, flung, scrolled, clicked or
  stepped with Up and Down. The time is written once, when it is taken.

  What to take:

      time-picker-view   one time picker: its label, its tooltip and the control
      make-time-picker   the control itself, a VBox, for use without cljfx
      parse, show, error-text, wheel-specs, rows-for, wheels-time, turn,
      tick, wheels-place
                         the reading, the wording and the rules, as plain data
      clock-24?          whether macOS shows a 24-hour clock

  A time is a whole number of minutes after midnight, 0 to 1439, or nil where
  the field may be empty.

  The wheels are a child of the scene's root while they are open, so nothing
  the field sits in can clip them: the root must be a Pane.

  The look is in demo/glass.css, under `.time-field` and `.time-wheels`.
  Motion comes from demo.ui: its tween and its Reduce Motion."
  (:require [cljfx.api :as fx]
            [cljfx.ext.node :as fx.ext.node]
            [cljfx.lifecycle :as lifecycle]
            [cljfx.mutator :as mutator]
            [cljfx.prop :as prop]
            [clojure.java.shell :as shell]
            [clojure.string :as str]
            [demo.ui :as ui])
  (:import [java.time LocalTime]
           [java.time.chrono IsoChronology]
           [java.time.format DateTimeFormatterBuilder FormatStyle]
           [java.util Collection Locale]
           [javafx.animation AnimationTimer]
           [javafx.application Platform]
           [javafx.beans.value ChangeListener]
           [javafx.css PseudoClass]
           [javafx.event Event EventHandler]
           [javafx.geometry Pos]
           [javafx.scene Node Scene]
           [javafx.scene.control Label TextField]
           [javafx.scene.input KeyCode KeyEvent MouseEvent ScrollEvent]
           [javafx.scene.layout HBox Pane Region StackPane VBox]))

;;; Look and rules: plain data, so they are tested without a window

;; The field's height: that of a button.
(def field-h 44.0)
(def min-width 120.0)
(def field-w 160.0)
;; Between the field and its wheels, and between the wheels and the window's edge.
(def gap 4.0)
(def edge-gap 4.0)
(def day 1440)

(defn show
  "A time as it is shown: \"9:30 AM\", or \"09:30\" on a 24-hour clock. On a
  12-hour clock twelve o'clock is shown with its word."
  [m h24]
  (let [h (quot m 60)
        mm (rem m 60)]
    (if h24
      (format "%02d:%02d" h mm)
      (str (let [h12 (rem h 12)] (if (zero? h12) 12 h12))
           (format ":%02d " mm)
           (if (< h 12) "AM" "PM")
           (cond (= 0 m) ", midnight" (= 720 m) ", noon" :else "")))))

(defn- clean
  "What was typed, without its case, its outer spaces or the word the field
  itself puts after twelve o'clock."
  [text]
  (-> (str text) str/trim str/lower-case (str/replace #",\s*(noon|midnight)$" "")))

(def ^:private whole #"(\d{1,4})(?:[:.](\d\d))?\s*(a\.?m?\.?|p\.?m?\.?)?")

(defn parse
  "Reads what was typed. One of
      {:time m}                      a time
      {:empty true}                  nothing typed
      {:error :am-pm :hour h}        an hour from 1 to 12 with no AM or PM
      {:error :not-a-time}           anything else
  An hour that could be either half of the day is never guessed at, unless the
  clock is a 24-hour one: there every hour is taken as it stands."
  [text h24]
  (let [t (clean text)]
    (cond
      (= "" t) {:empty true}
      (= "noon" t) {:time 720}
      (= "midnight" t) {:time 0}
      :else
      (if-let [[_ digits mins meridiem] (re-matches whole t)]
        (let [n (count digits)
              [h m] (cond
                      mins (when (<= n 2) [(parse-long digits) (parse-long mins)])
                      (<= n 2) [(parse-long digits) 0]
                      :else [(parse-long (subs digits 0 (- n 2))) (parse-long (subs digits (- n 2)))])]
          (cond
            (or (nil? h) (> m 59) (> h 23)) {:error :not-a-time}
            meridiem (if (<= 1 h 12)
                       {:time (+ (* 60 (+ (rem h 12) (if (str/starts-with? meridiem "p") 12 0))) m)}
                       {:error :not-a-time})
            (or h24 (zero? h) (> h 12)) {:time (+ (* 60 h) m)}
            :else {:error :am-pm :hour h :minute (when (or mins (> n 2)) m)}))
        {:error :not-a-time}))))

(defn error-text
  "The line under the field, for what `parse` could not take."
  [{:keys [error hour]}]
  (case error
    :am-pm (str "AM or PM? Type " hour "a or " hour "p")
    :not-a-time "Not a time. Try 9:30 or 2130"
    nil))

;;; The wheels

;; A row's height, and how many are seen on each wheel.
(def row-h 34.0)
(def rows-seen 5)
(def wheels-h (* row-h rows-seen))
(def wheel-w 64.0)
;; Each row turns the drum this far; the radius keeps a row row-h tall at the band.
(def step-rad (Math/toRadians 24.0))
(def drum-r (/ row-h step-rad))
;; How fast a turn eases onto its row: it is there in about 200 ms.
(def snap-rate 30.0)
;; How fast a fling slows, and how long a scroll must stop before it settles.
(def coast-drag 2.6)
(def quiet-s 0.08)

(defn- two [n] (format "%02d" n))

(defn wheel-specs
  "The wheels for a clock: hour, minute and AM/PM, or hour and minute on a
  24-hour clock. Hour and minute go round; AM/PM stops at its ends."
  [h24]
  (let [minute {:key :m :opts (mapv two (range 60)) :loop true}]
    (if h24
      [{:key :h :opts (mapv two (range 24)) :loop true} minute]
      [{:key :h :opts (mapv str (cons 12 (range 1 12))) :loop true}
       minute
       {:key :p :opts ["AM" "PM"] :loop false}])))

(defn wheels-w [specs] (* wheel-w (count specs)))

(defn rows-for
  "The row each wheel shows for a time."
  [m h24]
  (let [h (quot m 60) mm (rem m 60)]
    (if h24 [h mm] [(rem h 12) mm (if (< h 12) 0 1)])))

(defn row-at
  "The row a wheel shows at the band."
  [{:keys [opts loop]} offset]
  (let [n (count opts) i (Math/round (double offset))]
    (if loop (mod i n) (max 0 (min (dec n) i)))))

(defn wheels-time
  "The time the wheels show, from each wheel's offset."
  [specs offsets h24]
  (let [[h m p] (map row-at specs offsets)]
    (if h24
      (+ (* 60 h) m)
      (+ (* 60 (+ h (if (= 1 p) 12 0))) m))))

(defn after-now
  "The next whole minute: what the wheels show from an empty field."
  [now]
  (rem (inc now) day))

(defn nearest
  "The offset nearest `offset` at which a wheel shows `row`: a wheel that goes
  round turns the short way."
  [{:keys [opts loop]} offset row]
  (if loop
    (let [n (count opts)
          here (Math/round (double offset))
          d (mod (- row (mod here n)) n)]
      (double (+ here (if (> d (/ n 2)) (- d n) d))))
    (double row)))

(defn wheel-at [row] {:offset (double row) :vel 0.0 :target nil :quiet 1.0 :drag nil})

(defn- bounded
  "A wheel that stops at its ends, kept to its rows, with `give` past them."
  [{:keys [opts loop]} o give]
  (if loop o (max (- give) (min (+ (dec (count opts)) give) o))))

(defn- snap [spec o] (double (bounded spec (Math/round (double o)) 0)))

(defn turn
  "A wheel set to ease to `rows` rows on, as Up and Down do."
  [spec {:keys [offset target] :as w} rows]
  (assoc w :target (snap spec (+ (or target offset) rows)) :vel 0.0 :drag nil))

(defn aim
  "A wheel set to ease to show `row`, as typing a time does."
  [spec w row]
  (assoc w :target (nearest spec (:offset w) row) :vel 0.0))

(defn moving? [{:keys [offset vel target drag]}]
  (boolean (or drag target (not (zero? vel)) (not= offset (Math/rint offset)))))

(defn tick
  "One frame of a wheel after `dt` seconds; nil once at rest. With `calm`, for
  Reduce Motion, a turn lands at once."
  [spec {:keys [offset vel target quiet drag] :as w} dt calm]
  (cond
    drag nil
    (and calm (or target (not (zero? vel)) (not= offset (snap spec offset))))
    (assoc w :offset (or target (snap spec offset)) :target nil :vel 0.0)
    target (let [o (+ offset (* (- 1.0 (Math/exp (- (* snap-rate dt)))) (- target offset)))]
             (if (< (Math/abs (- target o)) 0.002)
               (assoc w :offset target :target nil :vel 0.0)
               (assoc w :offset o)))
    (> (Math/abs vel) 0.6)
    (let [o (+ offset (* vel dt))
          b (bounded spec o 0.0)]
      (if (not= o b)
        (assoc w :offset b :vel 0.0 :target (snap spec b))
        (assoc w :offset o :vel (* vel (Math/exp (- (* coast-drag dt)))))))
    (not (zero? vel)) (assoc w :vel 0.0 :target (snap spec (+ offset (* vel 0.15))))
    (not= offset (snap spec offset))
    (if (< quiet quiet-s)
      (assoc w :quiet (+ quiet dt))
      (assoc w :target (snap spec offset)))
    :else nil))

(defn row-under
  "Which offset a point at height `y` on a wheel shows: the drum's curve undone."
  [offset y]
  (let [s (max -0.99 (min 0.99 (/ (- y (/ wheels-h 2)) drum-r)))]
    (+ offset (/ (Math/asin s) step-rad))))

(defn press [w y now]
  (assoc w :drag {:y0 y :o0 (:offset w) :y y :t now :v 0.0} :vel 0.0 :target nil))

(defn drag [spec w y now]
  (if-let [{:keys [y0 o0 t v] :as d} (:drag w)]
    (let [dt (max 1e-3 (- now t))
          v' (+ (* 0.7 (/ (- (- y (:y d))) row-h dt)) (* 0.3 v))]
      (assoc w :offset (bounded spec (- o0 (/ (- y y0) row-h)) 0.4)
             :drag (assoc d :y y :t now :v v')))
    w))

(defn release
  "A wheel let go: a click brings the row under it to the band, a fling
  coasts, and a slow drag settles where it is."
  [spec w y now]
  (if-let [{:keys [y0 t v]} (:drag w)]
    (let [w (assoc w :drag nil)]
      (cond
        (< (Math/abs (- y y0)) 4) (assoc w :target (snap spec (row-under (:offset w) y)))
        (> (- now t) 0.08) (assoc w :target (snap spec (:offset w)))
        :else (assoc w :vel (max -40.0 (min 40.0 v)))))
    w))

(defn scroll [spec w dy]
  (assoc w :offset (bounded spec (- (:offset w) (/ dy row-h)) 0.3)
         :vel 0.0 :target nil :quiet 0.0))

(defn wheels-place
  "Where the wheels go, in the window: under the field, and over it when there
  is no room under. They stay whole, `edge-gap` clear of the window's edges."
  [{:keys [x top bottom]} w h scene-w scene-h]
  (let [under (+ bottom gap)
        fits (<= (+ under h edge-gap) scene-h)]
    {:x (-> x (min (- scene-w edge-gap w)) (max edge-gap))
     :y (if fits under (max edge-gap (- top gap h)))
     :over (not fits)}))

(defn current-minute []
  (let [now (LocalTime/now)]
    (+ (* 60 (.getHour now)) (.getMinute now))))

(defn clock-24?
  "Whether macOS shows a 24-hour clock: its own switch, or else what the region
  uses. It runs a process: call it off the UI thread."
  []
  (let [read (fn [k]
               (try (str/trim (:out (shell/sh "defaults" "read" "-g" k)))
                    (catch Exception _ "")))]
    (cond
      (= "1" (read "AppleICUForce24HourTime")) true
      (= "1" (read "AppleICUForce12HourTime")) false
      :else (boolean (re-find #"[Hk]" (DateTimeFormatterBuilder/getLocalizedDateTimePattern
                                        nil FormatStyle/SHORT IsoChronology/INSTANCE (Locale/getDefault)))))))

;;; The control

(def ^PseudoClass marked (PseudoClass/getPseudoClass "marked"))
(def ^PseudoClass invalid (PseudoClass/getPseudoClass "invalid"))

(defn- handler ^EventHandler [f]
  (reify EventHandler (handle [_ e] (f e))))

(defn- listener ^ChangeListener [f]
  (reify ChangeListener (changed [_ _ old new] (f old new))))

;;; The control

(def ^PseudoClass marked (PseudoClass/getPseudoClass "marked"))
(def ^PseudoClass invalid (PseudoClass/getPseudoClass "invalid"))

(defn- handler ^EventHandler [f]
  (reify EventHandler (handle [_ e] (f e))))

(defn- listener ^ChangeListener [f]
  (reify ChangeListener (changed [_ _ old new] (f old new))))

;; Labels kept on each wheel: enough for the rows seen, and those curving away.
(def ^:private slots 9)

(defn- seconds [] (/ (System/nanoTime) 1e9))

(defn- goal
  "Where the wheels are headed: each one's target, or where it is."
  [ws]
  (map #(or (:target %) (:offset %)) ws))

(defn make-time-picker
  "The control: a VBox with the label, the field and, when it has something
  to say, the line under it. The wheels join the scene's root while they are
  open. The control is told what it is with `set-model!`, and it tells the app
  through the model's `dispatch`: the `write` event, once, when a time is
  taken."
  ^VBox []
  (let [model (atom {:name "" :value nil})
        ;; True once the text has been changed by hand, until it is taken or put back.
        typed (atom false)
        quiet (atom false)
        open (atom false)
        specs (atom (wheel-specs false))
        wheels (atom [])
        ;; Each wheel's pane and its labels.
        panes (atom [])
        ;; True once a wheel has been turned by hand, until it is taken or put back.
        touched (atom false)
        ;; True while the wheels turn to a typed time: settling leaves the text alone.
        by-typing (atom false)
        ;; The time the wheels last put in the field.
        shown (atom nil)
        field (TextField.)
        ;; The label names the field.
        label (doto (Label.)
                (-> .getStyleClass (.add "time-label")))
        line (doto (Label.)
               (.setVisible false)
               (.setManaged false)
               (-> .getStyleClass (.add "time-line")))
        band (doto (Region.)
               (.setMouseTransparent true)
               (.setPrefHeight row-h)
               (.setMaxHeight row-h)
               (-> .getStyleClass (.add "time-band")))
        row-box (doto (HBox.) (.setAlignment Pos/CENTER))
        lst (doto (StackPane.)
              (.setManaged false)
              (.setOpacity 0.0)
              (-> .getStyleClass (.add "time-wheels"))
              (-> .getChildren (.addAll ^Collection [band row-box])))
        box (VBox.)
        h24? #(boolean (:h24 @model))
        value-text #(let [{:keys [value h24]} @model] (if value (show value h24) ""))
        set-text! (fn [s]
                    (reset! quiet true)
                    (.setText field s)
                    (reset! quiet false)
                    (reset! typed false))
        err! (fn [text]
               (swap! model assoc :error text)
               (.setText line (or text ""))
               (.setVisible line (boolean text))
               (.setManaged line (boolean text))
               (.pseudoClassStateChanged field invalid (boolean text)))
        ;; Each label where its row sits on the drum: shorter and fainter away
        ;; from the band.
        draw! (fn []
                (doseq [[spec w [_ labels]] (map vector @specs @wheels @panes)]
                  (let [{:keys [opts loop]} spec
                        n (count opts)
                        offset (:offset w)
                        c (Math/round (double offset))]
                    (dotimes [j slots]
                      (let [^Label l (nth labels j)
                            k (+ c (- j (quot slots 2)))
                            d (- k offset)
                            a (* d step-rad)
                            ;; Five rows are seen; one coming in or going out fades.
                            edge (/ rows-seen 2.0)
                            seen (and (< (Math/abs d) edge) (or loop (< -1 k n)))]
                        (.setVisible l seen)
                        (when seen
                          (let [cos (Math/cos a)]
                            (.setText l (nth opts (mod k n)))
                            (.resizeRelocate l 0.0 (- (+ (/ wheels-h 2) (* drum-r (Math/sin a))) (/ row-h 2))
                                             wheel-w row-h)
                            (.setScaleY l cos)
                            (.setOpacity l (* (Math/pow cos 1.6) (min 1.0 (* 2.0 (- edge (Math/abs d))))))
                            (.pseudoClassStateChanged l marked (< (Math/abs d) 0.5)))))))))
        place! (fn []
                 (when-let [scene (.getScene field)]
                   (let [root (.getRoot scene)
                         b (.localToScene field (.getLayoutBounds field))
                         ins (.getInsets lst)
                         w (max (.getWidth b) (+ (wheels-w @specs) (.getLeft ins) (.getRight ins)))
                         h (+ wheels-h (.getTop ins) (.getBottom ins))
                         {:keys [x y]} (wheels-place {:x (.getMinX b) :top (.getMinY b) :bottom (.getMaxY b)}
                                                     w h (.getWidth scene) (.getHeight scene))
                         p (.sceneToLocal root (double x) (double y))]
                     (.resizeRelocate lst (.getX p) (.getY p) w h))))
        fade-ms #(if @ui/*reduce 0 ui/fade-ms)
        timer-box (atom nil)
        leave! (fn []
                 (some-> ^AnimationTimer @timer-box .stop)
                 (when-let [p (.getParent lst)]
                   (.remove (.getChildren ^Pane p) lst)))
        close! (fn []
                 (when @open
                   (reset! open false)
                   (.setMouseTransparent lst true)
                   (ui/tween! lst ::fade {:ms (fade-ms) :on-done #(when-not @open (leave!))}
                              [[(.opacityProperty lst) 0.0]])))
        ;; Written once, and only a time that changed.
        write! (fn [m]
                 (let [{:keys [dispatch write value]} @model]
                   (when (not= m value)
                     (swap! model assoc :value m)
                     (when (and dispatch write)
                       (dispatch (assoc write :value m))))))
        take! (fn [m]
                (write! m)
                (err! nil)
                (reset! touched false)
                (set-text! (value-text))
                (close!)
                (.selectAll field))
        wheel-time #(wheels-time @specs (goal @wheels) (h24?))
        ;; Takes what is typed, or says why it cannot.
        commit! (fn []
                  (let [{:keys [optional h24]} @model
                        r (parse (.getText field) h24)]
                    (cond
                      (:time r) (take! (:time r))
                      (and (:empty r) optional) (take! nil)
                      :else (do (err! (error-text (if (:empty r) {:error :not-a-time} r)))
                                (close!)))))
        ;; Return, Tab or a click elsewhere: what is typed, else what the wheels show.
        accept! (fn []
                  (cond
                    @typed (commit!)
                    @touched (take! (wheel-time))
                    :else (close!)))
        restore! (fn []
                   (err! nil)
                   (reset! touched false)
                   (set-text! (value-text))
                   (close!)
                   (.selectAll field))
        ;; Each frame, while open: the wheels move, and once they rest on a time
        ;; turned by hand, the field shows it, all selected.
        frame! (fn [dt]
                 (let [calm @ui/*reduce
                       before @wheels
                       after (mapv (fn [spec w] (or (tick spec w dt calm) w)) @specs before)]
                   (when (not= before after)
                     (reset! wheels after)
                     (draw!))
                   (when (and @touched (not @by-typing) (not-any? moving? after))
                     (let [t (wheels-time @specs (map :offset after) (h24?))]
                       (when (not= t @shown)
                         (reset! shown t)
                         (set-text! (show t (h24?)))
                         (.selectAll field))))))
        timer (let [last (atom 0)]
                (proxy [AnimationTimer] []
                  (start [] (reset! last 0) (proxy-super start))
                  (handle [now]
                    (let [dt (if (zero? @last) 0.0 (/ (- now @last) 1e9))]
                      (reset! last now)
                      (frame! (min dt 0.05))))))
        _ (reset! timer-box timer)
        focus-wheel! (fn [i]
                       (when-let [[^Pane p] (get @panes (max 0 (min (dec (count @panes)) i)))]
                         (.requestFocus p)))
        index-of-pane (fn [^Node n] (first (keep-indexed (fn [i [p]] (when (identical? p n) i)) @panes)))
        hand! (fn [i f]
                (reset! touched true)
                (reset! by-typing false)
                (swap! wheels update i f))
        on-wheel-key (fn [i ^KeyEvent e]
                       (let [spec (nth @specs i)
                             code (.getCode e)]
                         (cond
                           (= KeyCode/UP code) (hand! i #(turn spec % -1))
                           (= KeyCode/DOWN code) (hand! i #(turn spec % 1))
                           (= KeyCode/LEFT code) (focus-wheel! (dec i))
                           (= KeyCode/RIGHT code) (focus-wheel! (inc i))
                           (= KeyCode/ENTER code) (do (accept!) (.requestFocus field))
                           (= KeyCode/TAB code) (do (accept!) (.requestFocus field))
                           (= KeyCode/ESCAPE code) (do (restore!) (.requestFocus field)))
                         (when (#{KeyCode/UP KeyCode/DOWN KeyCode/LEFT KeyCode/RIGHT
                                  KeyCode/ENTER KeyCode/TAB KeyCode/ESCAPE} code)
                           (.consume e))))
        build! (fn []
                 (let [id (:id @model)]
                   (reset! panes
                           (vec (for [[i {:keys [key]}] (map-indexed vector @specs)]
                                  (let [labels (vec (repeatedly slots #(doto (Label.)
                                                                         (.setManaged false)
                                                                         (.setAlignment Pos/CENTER)
                                                                         (-> .getStyleClass (.add "time-row")))))
                                        p (doto (Pane.)
                                            (.setId (str id "-wheel-" (name key)))
                                            (.setMinSize wheel-w wheels-h)
                                            (.setPrefSize wheel-w wheels-h)
                                            (.setMaxSize wheel-w wheels-h)
                                            (-> .getStyleClass (.add "time-wheel"))
                                            (-> .getChildren (.addAll ^Collection labels)))]
                                    (.addEventHandler p MouseEvent/MOUSE_PRESSED
                                                      (handler (fn [^MouseEvent e]
                                                                 (let [y (.getY e)] (hand! i #(press % y (seconds)))))))
                                    (.addEventHandler p MouseEvent/MOUSE_DRAGGED
                                                      (handler (fn [^MouseEvent e]
                                                                 (let [y (.getY e) spec (nth @specs i)]
                                                                   (hand! i #(drag spec % y (seconds)))))))
                                    (.addEventHandler p MouseEvent/MOUSE_RELEASED
                                                      (handler (fn [^MouseEvent e]
                                                                 (let [y (.getY e) spec (nth @specs i)]
                                                                   (hand! i #(release spec % y (seconds)))))))
                                    ;; Scrolling over a wheel turns it, and nothing under it.
                                    (.addEventHandler p ScrollEvent/SCROLL
                                                      (handler (fn [^ScrollEvent e]
                                                                 (.consume e)
                                                                 (let [dy (.getDeltaY e) spec (nth @specs i)]
                                                                   (hand! i #(scroll spec % dy))))))
                                    (.addEventHandler p KeyEvent/KEY_PRESSED (handler #(on-wheel-key i %)))
                                    [p labels])))))
                 (.setAll (.getChildren row-box) ^Collection (mapv first @panes))
                 (draw!))
        ;; The wheels open showing the field's time; from an empty field, the
        ;; next whole minute.
        open! (fn []
                (when (and (not @open) (not (.isDisabled field)))
                  (when-let [scene (.getScene field)]
                    (let [root (.getRoot scene)
                          {:keys [value now]} @model
                          h24 (h24?)
                          start (or (when @typed (:time (parse (.getText field) h24)))
                                    value
                                    (after-now (or now (current-minute))))]
                      (when (instance? Pane root)
                        (reset! specs (wheel-specs h24))
                        (reset! wheels (mapv wheel-at (rows-for start h24)))
                        (reset! touched false)
                        (reset! by-typing false)
                        (reset! shown start)
                        (build!)
                        (let [kids (.getChildren ^Pane root)]
                          (when-not (.contains kids lst) (.add kids lst)))
                        (.applyCss lst)
                        (place!)
                        (reset! open true)
                        (.setMouseTransparent lst false)
                        (.start ^AnimationTimer timer)
                        (ui/tween! lst ::fade {:ms (fade-ms)} [[(.opacityProperty lst) 1.0]]))))))
        ;; A whole typed time turns the wheels to it.
        follow-typing! (fn []
                         (when @open
                           (when-let [m (:time (parse (.getText field) (h24?)))]
                             (reset! by-typing true)
                             (reset! touched false)
                             (reset! wheels (mapv (fn [spec w row] (aim spec w row))
                                                  @specs @wheels (rows-for m (h24?)))))))
        on-key (fn [^KeyEvent e]
                 (let [code (.getCode e)]
                   (cond
                     (#{KeyCode/DOWN KeyCode/UP} code)
                     (do (.consume e)
                         (if @open (focus-wheel! 0) (open!)))

                     (= KeyCode/ENTER code)
                     (when (or @open @typed)
                       (.consume e)
                       (accept!))

                     (= KeyCode/ESCAPE code)
                     (when (or @open @typed (:error @model))
                       (.consume e)
                       (restore!))

                     ;; With nothing typed, Undo is the app's, not the field's.
                     (and (= KeyCode/Z code) (.isShortcutDown e) (not @typed))
                     (do (.consume e)
                         (when-let [p (.getParent box)]
                           (Event/fireEvent p (.copyFor e p p)))))))
        within? (fn [target]
                  (loop [n target]
                    (cond
                      (not (instance? Node n)) false
                      (or (identical? n field) (identical? n lst)) true
                      :else (recur (.getParent ^Node n)))))
        leave-field! (fn []
                       (accept!)
                       (close!))
        ;; Followed on the scene, so it holds in a window that is not in front.
        ;; The focus may move between the field and its wheels.
        on-owner (listener (fn [old new]
                             (let [was (within? old) is (within? new)]
                               (cond
                                 (and (identical? new field) (not was))
                                 (Platform/runLater #(.selectAll field))
                                 (and was (not is)) (leave-field!)))))
        ;; A click elsewhere takes the time, also where it moves no focus.
        on-outside (handler (fn [^MouseEvent e]
                              (when (and (within? (some-> (.getScene field) .getFocusOwner))
                                         (not (within? (.getTarget e))))
                                (leave-field!))))
        on-moved (listener (fn [_ _] (when @open (place!))))
        wire! (fn [^Scene old ^Scene new]
                (when old
                  (.removeListener (.focusOwnerProperty old) on-owner)
                  (.removeEventFilter old MouseEvent/MOUSE_PRESSED on-outside)
                  (.removeListener (.widthProperty old) on-moved)
                  (.removeListener (.heightProperty old) on-moved)
                  (reset! open false)
                  (leave!))
                (when new
                  (.addListener (.focusOwnerProperty new) on-owner)
                  (.addEventFilter new MouseEvent/MOUSE_PRESSED on-outside)
                  (.addListener (.widthProperty new) on-moved)
                  (.addListener (.heightProperty new) on-moved)))]
    (.addListener (.textProperty field)
                  (listener (fn [_ _]
                              (when-not @quiet
                                (reset! typed true)
                                (when (:error @model) (err! nil))
                                (open!)
                                (follow-typing!)))))
    (.addListener (.sceneProperty field) (listener wire!))
    (.addListener (.localToSceneTransformProperty field) on-moved)
    (.addEventFilter field KeyEvent/KEY_PRESSED (handler on-key))
    (.addEventHandler field MouseEvent/MOUSE_PRESSED (handler (fn [_] (open!))))
    (doto field
      (-> .getStyleClass (.add "time-field"))
      (.setMinHeight field-h)
      (.setPrefHeight field-h)
      (.setMaxHeight field-h)
      (.setMinWidth min-width)
      (.setPrefWidth field-w))
    (.setLabelFor label field)
    (.put (.getProperties box) ::parts
          {:model model :field field :label label :line line :lst lst :typed typed
           :value-text value-text :set-text! set-text! :close! close!})
    (doto box
      (.setFillWidth false)
      (.setSpacing 2.0)
      (-> .getStyleClass (.add "time-box"))
      (-> .getChildren (.addAll ^Collection [label field line])))))

(defn set-model!
  "Tells the time picker what it is: `:id`, `:name`, the written `:value`,
  `:optional`, `:disabled`, `:tip`, `:h24`, `:now` in place of the clock, and
  `:dispatch` with the `:write` event it sends through it. The field's text
  follows only a value that has changed, as after an Undo: never under typing."
  [^VBox box m]
  (let [{:keys [model ^TextField field ^Label label ^Label line ^Node lst typed value-text set-text! close!]}
        (.get (.getProperties box) ::parts)
        old @model
        given (:value m)
        fresh (not= given (:given old))
        clock (not= (boolean (:h24 m)) (boolean (:h24 old)))]
    (reset! model (assoc m :given given :value (if fresh given (:value old)) :error (:error old)))
    (.setId field (:id m))
    (.setText label (:name m))
    (.setId line (str (:id m) "-line"))
    (.setId lst (str (:id m) "-wheels"))
    (.setDisable field (boolean (:disabled m)))
    (when (:disabled m) (close!))
    ;; The hint, in grey, where the field may be empty.
    (.setPromptText field (when (:optional m) (show 570 (:h24 m))))
    (when (and (or fresh clock) (not @typed) (not= (.getText field) (value-text)))
      (set-text! (value-text))
      ;; Under the focus, the new text is ready to be typed over.
      (when (some-> (.getScene field) .getFocusOwner (identical? field))
        (.selectAll field)))))

(def ext-model
  (fx/make-ext-with-props
    {::model (prop/make (mutator/setter set-model!) lifecycle/scalar)}))

(defn time-picker-view
  "One time picker, with the label that names what it sets. `write` is an
  event, as the app's event handler takes it, and `dispatch` is the function
  that fires it: once, with the `:value` to keep, minutes after midnight or
  nil. `value` is the written time. `optional` lets the field be empty. `h24`
  is whether the clock is a 24-hour one. `tip` says why a `disabled` picker is
  off; the tooltip is on the box, so that one still shows it."
  [{:keys [disabled tip] :as props}]
  {:fx/type fx.ext.node/with-tooltip-props
   :props (if (and disabled tip) {:tooltip {:fx/type :tooltip :text tip}} {})
   :desc
   {:fx/type ext-model
    :props {::model (select-keys props [:id :name :value :optional :disabled :tip
                                        :h24 :now :dispatch :write])}
    :desc {:fx/type fx/ext-instance-factory :create make-time-picker}}})
