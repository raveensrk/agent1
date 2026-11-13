(ns demo.time-picker
  "The part worth copying: a time picker that sets one time of day, as Time
  pickers in requirements/components.org asks. A reference, not a library:
  follow what it does, and take the code as one way to do it. Nothing here
  knows about the demo's page or its state (demo.time-picker-page).

  One field that is typed into, with a list of times under it. What is typed
  is read forgivingly, \"9a\", \"930a\", \"2130\", \"noon\", and shown in full
  once it is taken. An hour that could be morning or afternoon is never
  guessed at: the field asks. The list holds the day in 15 minute steps and
  narrows as the text grows. The time is written once, when it is taken.

  What to take:

      time-picker-view   one time picker: its label, its tooltip and the control
      make-time-picker   the control itself, a VBox, for use without cljfx
      parse, show, offer, error-text, list-place, offset-for, said
                         the reading, the wording and the rules, as plain data
      clock-24?          whether macOS shows a 24-hour clock

  A time is a whole number of minutes after midnight, 0 to 1439, or nil where
  the field may be empty.

  The list is a child of the scene's root while it is open, so nothing the
  field sits in can clip it: the root must be a Pane.

  The look is in demo/glass.css, under `.time-field`. Motion comes from
  demo.ui: its tween and its Reduce Motion."
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
           [javafx.application Platform]
           [javafx.beans.property SimpleDoubleProperty]
           [javafx.beans.value ChangeListener]
           [javafx.css PseudoClass]
           [javafx.event Event EventHandler]
           [javafx.scene AccessibleAttribute Node Scene]
           [javafx.scene.control Label TextField]
           [javafx.scene.input KeyCode KeyEvent MouseEvent ScrollEvent]
           [javafx.scene.layout Pane StackPane VBox]
           [javafx.scene.shape Rectangle]))

;;; Look and rules: plain data, so they are tested without a window

;; The field's height: that of a button.
(def field-h 44.0)
(def min-width 120.0)
(def field-w 160.0)
;; The list holds the day in steps of this many minutes.
(def step 15)
(def row-h 32.0)
;; How many rows are seen at once; the rest are scrolled to.
(def rows-seen 8)
;; The list is never narrower than this: "12:00 AM, midnight" fits.
(def list-min-w 190.0)
;; Between the field and its list, and between the list and the window's edge.
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

(def steps (vec (range 0 day step)))

(defn- hour-steps [h]
  (mapv #(+ (* 60 h) %) (range 0 60 step)))

(defn after-now
  "The step after `now`."
  [now]
  (rem (* step (inc (quot now step))) day))

(defn- index-of [coll x]
  (first (keep-indexed (fn [i y] (when (= x y) i)) coll)))

(defn offer
  "The list for a field: {:rows [times] :mark index-or-nil}.

  Before anything is typed it is the whole day, with the field's time marked,
  or the step after `now` from an empty field. Typed text narrows it: a whole
  time is the first row and marked, ahead of the steps of its hour; an hour
  with no AM or PM leaves both halves of the day, afternoon first, and marks
  neither."
  [{:keys [text typed value now h24]}]
  (let [t (clean text)
        halves (fn [h] (if (or h24 (zero? h) (> h 12)) [h] [(+ 12 (rem h 12)) (rem h 12)]))]
    (cond
      (not typed)
      (let [all (if (and value (pos? (rem value step))) (vec (sort (conj steps value))) steps)]
        {:rows all :mark (index-of all (or value (after-now now)))})

      (= "" t) {:rows steps :mark nil}

      :else
      (let [{:keys [time error hour minute]} (parse t h24)]
        (cond
          time {:rows (vec (distinct (cons time (hour-steps (quot time 60))))) :mark 0}

          (= :am-pm error)
          {:rows (vec (for [h (halves hour)
                            m (if minute [(+ (* 60 h) minute)] (hour-steps h))]
                        m))
           :mark nil}

          :else
          (if-let [[_ digits begun] (re-matches #"(\d{1,2})[:.](\d?)" t)]
            ;; An hour and the start of its minutes, "2:3".
            (let [hour (parse-long digits)]
              {:rows (if (> hour 23)
                       []
                       (vec (for [h (halves hour)
                                  m (hour-steps h)
                                  :when (str/starts-with? (format "%02d" (rem m 60)) begun)]
                              m)))
               :mark nil})
            ;; The start of a word, "no".
            {:rows (vec (keep (fn [[word m]] (when (str/starts-with? word t) m))
                              [["noon" 720] ["midnight" 0]]))
             :mark nil}))))))

(defn offset-for
  "How far a list of `n` rows is scrolled to put row `mark` in the middle of
  what is seen: never past either end."
  [mark n]
  (let [seen (min n rows-seen)]
    (-> (- (* mark row-h) (/ (* (dec seen) row-h) 2.0))
        (min (* (- n seen) row-h))
        (max 0.0))))

(defn list-place
  "Where the list goes, in the window: under the field, and over it when there
  is no room under. It stays whole, `edge-gap` clear of the window's edges."
  [{:keys [x top bottom]} list-w list-h scene-w scene-h]
  (let [under (+ bottom gap)
        fits (<= (+ under list-h edge-gap) scene-h)]
    {:x (-> x (min (- scene-w edge-gap list-w)) (max edge-gap))
     :y (if fits under (max edge-gap (- top gap list-h)))
     :over (not fits)}))

(defn said
  "What a screen reader says for a time picker, as its name and the kind of
  thing it is. The name is what the picker sets, with no time in it: macOS is
  given the field's text as its value, and says it. The name is spoken from
  the field's label, never set on the field: a name set on a JavaFX text field
  is given to macOS in place of its text, and the time is lost. macOS is given
  no help text, so the line under the field and the reason a picker is off go
  in the name; one that is off is called dimmed."
  [{:keys [name disabled tip error]}]
  {:name (cond
           (and disabled tip) (str name ". " tip)
           error (str name ". " error)
           :else name)
   :kind (when disabled "dimmed text field")})

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

(defn make-time-picker
  "The control: a VBox with the label, the field and, when it has something
  to say, the line under it. The list joins the scene's root while it is open. The control
  is told what it is with `set-model!`, and it tells the app through the
  model's `dispatch`: the `write` event, once, when a time is taken."
  ^VBox []
  (let [model (atom {:name "" :value nil})
        ;; True once the text has been changed by hand, until it is taken or put back.
        typed (atom false)
        quiet (atom false)
        open (atom false)
        offered (atom {:rows [] :mark nil})
        offset (SimpleDoubleProperty. 0.0)
        said-row (volatile! nil)
        ;; The marked row is what a screen reader is sent to, as in a combo box.
        ;; An empty field is given as empty: JavaFX would give its hint as the
        ;; time, and a screen reader would say a time that is not set.
        field (proxy [TextField] []
                (queryAccessibleAttribute [attr params]
                  (let [^TextField this this]
                    (cond
                      (and (= AccessibleAttribute/FOCUS_ITEM attr) @said-row) @said-row
                      (and (= AccessibleAttribute/TEXT attr) (empty? (.getText this))) ""
                      :else (proxy-super queryAccessibleAttribute attr params)))))
        ;; The label names the field, to the eye and to a screen reader.
        label (doto (Label.)
                (-> .getStyleClass (.add "time-label")))
        line (doto (Label.)
               (.setVisible false)
               (.setManaged false)
               (-> .getStyleClass (.add "time-line")))
        rows-box (doto (VBox.) (.setManaged false))
        clip (Rectangle.)
        port (doto (Pane.)
               (.setClip clip)
               (-> .getChildren (.add rows-box)))
        lst (doto (StackPane.)
              (.setManaged false)
              (.setOpacity 0.0)
              (-> .getStyleClass (.add "time-list"))
              (-> .getChildren (.add port)))
        box (VBox.)
        seen #(min rows-seen (count (:rows @offered)))
        value-text #(let [{:keys [value h24]} @model] (if value (show value h24) ""))
        say! (fn []
               (let [{:keys [name kind]} (said @model)]
                 (.setAccessibleText label name)
                 (.setAccessibleRoleDescription field kind)))
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
               (.pseudoClassStateChanged field invalid (boolean text))
               (say!))
        ;; The rows sit in the port, moved up by how far the list is scrolled.
        lay! (fn []
               (let [w (.getWidth port)]
                 (.setWidth clip w)
                 (.setHeight clip (.getHeight port))
                 (.resizeRelocate rows-box 0.0 (- (.get offset)) w (* (count (:rows @offered)) row-h))))
        scroll! (fn [to]
                  (.set offset (-> (double to)
                                   (min (* (- (count (:rows @offered)) (seen)) row-h))
                                   (max 0.0))))
        place! (fn []
                 (when-let [scene (.getScene field)]
                   (let [root (.getRoot scene)
                         b (.localToScene field (.getLayoutBounds field))
                         ins (.getInsets lst)
                         w (max (.getWidth b) list-min-w)
                         h (+ (* (seen) row-h) (.getTop ins) (.getBottom ins))
                         {:keys [x y]} (list-place {:x (.getMinX b) :top (.getMinY b) :bottom (.getMaxY b)}
                                                   w h (.getWidth scene) (.getHeight scene))
                         p (.sceneToLocal root (double x) (double y))]
                     (.resizeRelocate lst (.getX p) (.getY p) w h))))
        fade-ms #(if @ui/*reduce 0 ui/fade-ms)
        leave! (fn []
                 (when-let [p (.getParent lst)]
                   (.remove (.getChildren ^Pane p) lst)))
        close! (fn []
                 (when @open
                   (reset! open false)
                   (vreset! said-row nil)
                   (.setMouseTransparent lst true)
                   (ui/tween! lst ::fade {:ms (fade-ms) :on-done #(when-not @open (leave!))}
                              [[(.opacityProperty lst) 0.0]])))
        show! (fn []
                (when-let [scene (.getScene field)]
                  (let [root (.getRoot scene)]
                    (when (instance? Pane root)
                      (let [kids (.getChildren ^Pane root)]
                        (when-not (.contains kids lst) (.add kids lst)))
                      (.applyCss lst)
                      (place!)
                      (when-not @open
                        (reset! open true)
                        (.setMouseTransparent lst false)
                        (ui/tween! lst ::fade {:ms (fade-ms)} [[(.opacityProperty lst) 1.0]]))))))
        mark! (fn [i]
                (swap! offered assoc :mark i)
                (let [kids (.getChildren rows-box)]
                  (dotimes [k (count kids)]
                    (.pseudoClassStateChanged ^Node (.get kids k) marked (= k i)))
                  (when i
                    (let [top (* i row-h)
                          view (* (seen) row-h)
                          o (.get offset)]
                      (cond (< top o) (scroll! top)
                            (> (+ top row-h) (+ o view)) (scroll! (- (+ top row-h) view))))
                    (vreset! said-row (.get kids i))
                    (.notifyAccessibleAttributeChanged field AccessibleAttribute/FOCUS_ITEM))))
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
                (set-text! (value-text))
                (close!)
                (.selectAll field))
        fill! (fn []
                (let [{:keys [rows mark]} @offered
                      h24 (:h24 @model)]
                  (.setAll (.getChildren rows-box)
                           ^Collection
                           (vec (map-indexed
                                  (fn [i m]
                                    (doto (Label. (show m h24))
                                      (.setMinHeight row-h)
                                      (.setPrefHeight row-h)
                                      (.setMaxWidth Double/MAX_VALUE)
                                      (-> .getStyleClass (.add "time-row"))
                                      (.pseudoClassStateChanged marked (= i mark))
                                      (.setOnMouseClicked (handler (fn [_] (take! m))))))
                                  rows)))))
        ;; Works out the list anew, and opens it; with nothing to offer it closes.
        refresh! (fn []
                   (let [m @model
                         o (offer {:text (.getText field) :typed @typed :value (:value m)
                                   :now (or (:now m) (current-minute)) :h24 (:h24 m)})]
                     (reset! offered o)
                     (if (empty? (:rows o))
                       (close!)
                       (do (fill!)
                           (show!)
                           (.set offset (if (:mark o) (offset-for (:mark o) (count (:rows o))) 0.0))
                           (lay!)))))
        ;; Takes what is typed, or says why it cannot.
        commit! (fn []
                  (let [{:keys [optional h24]} @model
                        r (parse (.getText field) h24)]
                    (cond
                      (:time r) (take! (:time r))
                      (and (:empty r) optional) (take! nil)
                      :else (do (err! (error-text (if (:empty r) {:error :not-a-time} r)))
                                (close!)))))
        restore! (fn []
                   (err! nil)
                   (set-text! (value-text))
                   (close!)
                   (.selectAll field))
        on-key (fn [^KeyEvent e]
                 (let [code (.getCode e)
                       {:keys [rows mark]} @offered
                       n (count rows)]
                   (cond
                     (= KeyCode/DOWN code)
                     (do (.consume e)
                         (if @open
                           (mark! (if mark (min (inc mark) (dec n)) 0))
                           (refresh!)))

                     (and (= KeyCode/UP code) @open)
                     (do (.consume e)
                         (mark! (if mark (max 0 (dec mark)) (dec n))))

                     (= KeyCode/ENTER code)
                     (cond
                       (and @open mark) (do (.consume e) (take! (nth rows mark)))
                       @typed (do (.consume e) (commit!))
                       @open (do (.consume e) (close!)))

                     (= KeyCode/ESCAPE code)
                     (cond
                       ;; The first Escape closes the list and leaves the text.
                       @open (do (.consume e) (close!))
                       (or @typed (:error @model)) (do (.consume e) (restore!)))

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
                       (when @typed (commit!))
                       (close!))
        ;; Followed on the scene, so it holds in a window that is not in front.
        on-owner (listener (fn [old new]
                             (cond
                               (identical? new field)
                               (when-not (identical? old field)
                                 (Platform/runLater #(.selectAll field)))
                               (identical? old field) (leave-field!))))
        ;; A click elsewhere takes what is typed, also where it moves no focus.
        on-outside (handler (fn [^MouseEvent e]
                              (when (and (some-> (.getScene field) .getFocusOwner (identical? field))
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
                                (refresh!)))))
    (.addListener offset (listener (fn [_ _] (lay!))))
    (.addListener (.widthProperty port) (listener (fn [_ _] (lay!))))
    (.addListener (.heightProperty port) (listener (fn [_ _] (lay!))))
    (.addListener (.sceneProperty field) (listener wire!))
    (.addListener (.localToSceneTransformProperty field) on-moved)
    (.addEventFilter field KeyEvent/KEY_PRESSED (handler on-key))
    (.addEventHandler field MouseEvent/MOUSE_PRESSED (handler (fn [_] (when-not @open (refresh!)))))
    ;; Scrolling over the open list scrolls the list, and nothing under it.
    (.addEventHandler lst ScrollEvent/SCROLL
                      (handler (fn [^ScrollEvent e]
                                 (.consume e)
                                 (scroll! (- (.get offset) (.getDeltaY e))))))
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
           :value-text value-text :set-text! set-text! :say! say! :close! close!})
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
  (let [{:keys [model ^TextField field ^Label label ^Label line ^Node lst typed value-text set-text! say! close!]}
        (.get (.getProperties box) ::parts)
        old @model
        given (:value m)
        fresh (not= given (:given old))
        clock (not= (boolean (:h24 m)) (boolean (:h24 old)))]
    (reset! model (assoc m :given given :value (if fresh given (:value old)) :error (:error old)))
    (.setId field (:id m))
    (.setText label (:name m))
    (.setId line (str (:id m) "-line"))
    (.setId lst (str (:id m) "-list"))
    (.setDisable field (boolean (:disabled m)))
    (when (:disabled m) (close!))
    ;; The hint, in grey, where the field may be empty.
    (.setPromptText field (when (:optional m) (show 570 (:h24 m))))
    (when (and (or fresh clock) (not @typed) (not= (.getText field) (value-text)))
      (set-text! (value-text))
      ;; Under the focus, the new text is ready to be typed over.
      (when (some-> (.getScene field) .getFocusOwner (identical? field))
        (.selectAll field)))
    (say!)))

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
