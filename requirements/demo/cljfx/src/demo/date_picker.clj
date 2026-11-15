(ns demo.date-picker
  "The part worth copying: a date picker that sets one day, as Date pickers in
  requirements/components.org asks. A reference, not a library: follow what it
  does, and take the code as one way to do it. Nothing here knows about the
  demo's page or its state (demo.date-picker-page).

  One field that is typed into, with a month calendar under it. What is typed
  is read forgivingly, \"20 nov\", \"2026-11-20\", the region's short form, and
  shown in full once it is taken. What is not a date is never guessed at. The
  date is written once, when it is taken.

  What to take:

      date-picker-view   one date picker: its label, its tooltip and the control
      make-date-picker   the control itself, a VBox, for use without cljfx
      parse, show, month-days, step-mark, calendar-place, error-text
                         the reading, the wording and the rules, as plain data
      first-weekday      the day macOS's region starts the week on

  A date is a java.time.LocalDate, or nil where the field may be empty.

  The calendar is a child of the scene's root while it is open, so nothing the
  field sits in can clip it: the root must be a Pane.

  The look is in demo/glass.css, under `.date-field`. Motion comes from
  demo.ui: its tween and its Reduce Motion."
  (:require [cljfx.api :as fx]
            [cljfx.ext.node :as fx.ext.node]
            [cljfx.lifecycle :as lifecycle]
            [cljfx.mutator :as mutator]
            [cljfx.prop :as prop]
            [clojure.java.shell :as shell]
            [clojure.string :as str]
            [demo.ui :as ui])
  (:import [java.time DayOfWeek LocalDate Month YearMonth]
           [java.time.chrono IsoChronology]
           [java.time.format DateTimeFormatter DateTimeFormatterBuilder FormatStyle TextStyle]
           [java.time.temporal WeekFields]
           [java.util Collection Locale]
           [javafx.application Platform]
           [javafx.beans.value ChangeListener]
           [javafx.css PseudoClass]
           [javafx.event Event EventHandler]
           [javafx.geometry Pos]
           [javafx.scene Cursor Node Scene]
           [javafx.scene.control Label TextField]
           [javafx.scene.input KeyCode KeyEvent MouseEvent ScrollEvent]
           [javafx.scene.layout HBox Pane Priority Region StackPane VBox]
           [javafx.scene.shape SVGPath]))

;;; Look and rules: plain data, so they are tested without a window

;; The field's height: that of a button.
(def field-h 44.0)
(def min-width 180.0)
(def field-w 200.0)
;; One day in the calendar.
(def day-w 36.0)
(def day-h 32.0)
;; Between the field and its calendar, and between the calendar and the window's edge.
(def gap 4.0)
(def edge-gap 4.0)

(defn- pattern
  "The region's own pattern for a date of `style`."
  [style ^Locale locale]
  (DateTimeFormatterBuilder/getLocalizedDateTimePattern style nil IsoChronology/INSTANCE locale))

(defn show
  "A date as it is shown: the region's medium date, with the weekday,
  \"Fri, 20 Nov 2026\"."
  [^LocalDate d ^Locale locale]
  (let [p (pattern FormatStyle/MEDIUM locale)
        p (if (str/includes? p "E") p (str "EEE, " p))]
    (.format d (DateTimeFormatter/ofPattern p locale))))

(defn month-title
  "The calendar's heading: \"November 2026\"."
  [^YearMonth ym ^Locale locale]
  (.format ym (DateTimeFormatter/ofPattern "LLLL y" locale)))

(defn day-first?
  "Whether the region's short form puts the day before the month."
  [^Locale locale]
  (let [p (pattern FormatStyle/SHORT locale)]
    (< (str/index-of p "d") (str/index-of p "M"))))

(defn- month-words
  "Every word for a month that is taken, in the region's tongue and English:
  its name, its short name, and the first three letters of its name."
  [^Locale locale]
  (into {}
        (for [^Locale l (distinct [locale Locale/ENGLISH])
              ^Month m (Month/values)
              style [TextStyle/FULL TextStyle/SHORT TextStyle/FULL_STANDALONE TextStyle/SHORT_STANDALONE]
              :let [w (-> (.getDisplayName m style l) str/lower-case (str/replace "." ""))]
              word [w (subs w 0 (min 3 (count w)))]]
          [word (.getValue m)])))

(defn- weekday-words [^Locale locale]
  (set (for [^Locale l (distinct [locale Locale/ENGLISH])
             ^DayOfWeek d (DayOfWeek/values)
             style [TextStyle/FULL TextStyle/SHORT]]
         (-> (.getDisplayName d style l) str/lower-case (str/replace "." "")))))

(defn- date-of [y m d]
  (try (LocalDate/of (int y) (int m) (int d)) (catch Exception _ nil)))

(defn- next-such
  "The next day `m`/`d` from `today`, today included; nil where there is none."
  [^LocalDate today m d]
  (some (fn [y] (when-let [x (date-of y m d)] (when-not (.isBefore x today) x)))
        (range (.getYear today) (+ 9 (.getYear today)))))

(defn- year-of [s]
  (let [y (parse-long s)] (if (= 2 (count s)) (+ 2000 y) y)))

(defn parse
  "Reads what was typed. One of
      {:date d}              a date
      {:empty true}          nothing typed
      {:error :not-a-date}   anything else
  A day and month with no year is the next such day from `today`."
  [text ^Locale locale ^LocalDate today]
  (let [t (-> (str text) str/trim str/lower-case (str/replace #"[,.]\s*" " ") str/trim)
        words (str/split t #"\s+")
        words (if (and (> (count words) 1) ((weekday-words locale) (first words))) (rest words) words)
        t (str/join " " words)
        months (month-words locale)
        day-num #(when-let [[_ n] (re-matches #"(\d{1,2})(?:st|nd|rd|th)?" %)] (parse-long n))
        whole (fn [y m d] (if-let [x (if y (date-of y m d) (next-such today m d))]
                            {:date x}
                            {:error :not-a-date}))]
    (cond
      (= "" t) {:empty true}

      :else
      (or
        (when-let [[_ y m d] (re-matches #"(\d{4})-(\d{1,2})-(\d{1,2})" t)]
          (whole (parse-long y) (parse-long m) (parse-long d)))
        (when-let [[_ a b y] (re-matches #"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}|\d{2}))?" t)]
          (let [[d m] (if (day-first? locale) [a b] [b a])]
            (whole (some-> y year-of) (parse-long m) (parse-long d))))
        (let [[p q r & more] words
              year (when (and r (re-matches #"\d{4}" r)) (parse-long r))]
          (when (and (nil? more) (or (nil? r) year))
            (cond
              (and (day-num p) (months q)) (whole year (months q) (day-num p))
              (and (months p) (day-num q)) (whole year (months p) (day-num q)))))
        {:error :not-a-date}))))

(defn error-text
  "The line under the field, for what `parse` could not take."
  [{:keys [error]}]
  (when (= :not-a-date error) "Not a date. Try 20 Nov or 2026-11-20"))

(defn month-days
  "The days a calendar of `ym` shows: whole weeks from `first-day`, six at most,
  with the days of the months either side that fill them."
  [^YearMonth ym ^DayOfWeek first-day]
  (let [start (.atDay ym 1)
        lead (mod (- (.getValue (.getDayOfWeek start)) (.getValue first-day)) 7)
        weeks (long (Math/ceil (/ (+ lead (.lengthOfMonth ym)) 7.0)))]
    (vec (for [i (range (* 7 weeks))] (.plusDays start (- i lead))))))

(defn weekdays
  "The weekday initials over the calendar's columns."
  [^DayOfWeek first-day ^Locale locale]
  (vec (for [i (range 7)] (.getDisplayName (.plus first-day (long i)) TextStyle/NARROW locale))))

(defn step-mark
  "Where a key moves the mark: a day, a week, or a month."
  [^LocalDate d ^KeyCode code]
  (condp = code
    KeyCode/LEFT (.minusDays d 1)
    KeyCode/RIGHT (.plusDays d 1)
    KeyCode/UP (.minusWeeks d 1)
    KeyCode/DOWN (.plusWeeks d 1)
    KeyCode/PAGE_UP (.minusMonths d 1)
    KeyCode/PAGE_DOWN (.plusMonths d 1)
    nil))

(defn calendar-place
  "Where the calendar goes, in the window: under the field, and over it when
  there is no room under. It stays whole, `edge-gap` clear of the window's edges."
  [{:keys [x top bottom]} w h scene-w scene-h]
  (let [under (+ bottom gap)
        fits (<= (+ under h edge-gap) scene-h)]
    {:x (-> x (min (- scene-w edge-gap w)) (max edge-gap))
     :y (if fits under (max edge-gap (- top gap h)))
     :over (not fits)}))

(defn first-weekday
  "The day macOS's region starts the week on: its own setting, or else what
  the region uses. It runs a process: call it off the UI thread."
  []
  (let [out (try (:out (shell/sh "defaults" "read" "-g" "AppleFirstWeekday")) (catch Exception _ ""))]
    (if-let [[_ n] (re-find #"gregorian\s*=\s*(\d)" (str out))]
      ;; macOS counts from Sunday, 1.
      (.plus DayOfWeek/SUNDAY (long (dec (parse-long n))))
      (.getFirstDayOfWeek (WeekFields/of (Locale/getDefault))))))

;;; The control

(def ^PseudoClass marked (PseudoClass/getPseudoClass "marked"))
(def ^PseudoClass today-class (PseudoClass/getPseudoClass "today"))
(def ^PseudoClass dim (PseudoClass/getPseudoClass "dim"))
(def ^PseudoClass invalid (PseudoClass/getPseudoClass "invalid"))

(defn- handler ^EventHandler [f]
  (reify EventHandler (handle [_ e] (f e))))

(defn- listener ^ChangeListener [f]
  (reify ChangeListener (changed [_ _ old new] (f old new))))

(defn- classed [^Node n & classes]
  (.addAll (.getStyleClass n) ^Collection (vec classes))
  n)

(defn- calendar-mark
  "The calendar drawn at the field's right end."
  ^Node []
  (doto (SVGPath.)
    (.setContent "M3 2h12a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H3a3 3 0 0 1-3-3V5a3 3 0 0 1 3-3z M0 7h18 M5 0v4 M13 0v4")
    (classed "date-mark")))

(defn make-date-picker
  "The control: a VBox with the label, the field and, when it has something to
  say, the line under it. The calendar joins the scene's root while it is
  open. The control is told what it is with `set-model!`, and it tells the app
  through the model's `dispatch`: the `write` event, once, when a date is taken."
  ^VBox []
  (let [model (atom {:name "" :value nil :locale (Locale/getDefault) :first-day DayOfWeek/MONDAY})
        ;; True once the text has been changed by hand, until it is taken or put back.
        typed (atom false)
        quiet (atom false)
        open (atom false)
        ;; The month the calendar shows, and its marked day.
        view (atom {:month nil :mark nil})
        field (TextField.)
        mark-icon (calendar-mark)
        icon (doto (StackPane. (into-array Node [mark-icon]))
               (.setCursor Cursor/DEFAULT)
               (.setMaxSize 34.0 field-h)
               (.setPrefSize 34.0 field-h))
        wrap (doto (StackPane. (into-array Node [field icon]))
               (classed "date-wrap"))
        label (classed (Label.) "date-label")
        line (doto (Label.)
               (.setVisible false)
               (.setManaged false)
               (classed "date-line"))
        title (classed (Label.) "date-title")
        prev (classed (Label. "‹") "date-step")
        next (classed (Label. "›") "date-step")
        grow (doto (Region.) (HBox/setHgrow Priority/ALWAYS))
        head (doto (HBox. (into-array Node [title grow prev next]))
               (.setAlignment Pos/CENTER_LEFT)
               (classed "date-head"))
        names (classed (HBox.) "date-names")
        weeks (VBox.)
        today-link (classed (Label. "Today") "date-today")
        foot (classed (HBox. (into-array Node [today-link])) "date-foot")
        cal (doto (VBox. (into-array Node [head names weeks foot]))
              (.setManaged false)
              (.setOpacity 0.0)
              (classed "date-calendar"))
        box (VBox.)
        today #(or (:today @model) (LocalDate/now))
        value-text #(let [{:keys [value locale]} @model] (if value (show value locale) ""))
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
        place! (fn []
                 (when-let [scene (.getScene field)]
                   (let [root (.getRoot scene)
                         b (.localToScene field (.getLayoutBounds field))
                         w (.prefWidth cal -1)
                         h (.prefHeight cal w)
                         {:keys [x y]} (calendar-place {:x (.getMinX b) :top (.getMinY b) :bottom (.getMaxY b)}
                                                       w h (.getWidth scene) (.getHeight scene))
                         p (.sceneToLocal root (double x) (double y))]
                     (.resizeRelocate cal (.getX p) (.getY p) w h)
                     (.layout cal))))
        fade-ms #(if @ui/*reduce 0 ui/fade-ms)
        leave! (fn []
                 (when-let [p (.getParent cal)]
                   (.remove (.getChildren ^Pane p) cal)))
        close! (fn []
                 (when @open
                   (reset! open false)
                   (.setMouseTransparent cal true)
                   (ui/tween! cal ::fade {:ms (fade-ms) :on-done #(when-not @open (leave!))}
                              [[(.opacityProperty cal) 0.0]])))
        ;; Written once, and only a date that changed.
        write! (fn [d]
                 (let [{:keys [dispatch write value]} @model]
                   (when (not= d value)
                     (swap! model assoc :value d)
                     (when (and dispatch write)
                       (dispatch (assoc write :value d))))))
        take! (fn [d]
                (write! d)
                (err! nil)
                (set-text! (value-text))
                (close!)
                (.selectAll field))
        fill! (fn []
                (let [{:keys [locale first-day value]} @model
                      {:keys [^YearMonth month mark]} @view
                      now (today)
                      id (.getId field)]
                  (.setText title (month-title month locale))
                  (.setAll (.getChildren names)
                           ^Collection (mapv #(doto (Label. %)
                                                (.setPrefWidth day-w)
                                                (.setAlignment Pos/CENTER)
                                                (classed "date-weekday"))
                                             (weekdays first-day locale)))
                  (.setAll (.getChildren weeks)
                           ^Collection
                           (vec (for [week (partition 7 (month-days month first-day))]
                                  (HBox. (into-array
                                           Node
                                           (for [^LocalDate d week]
                                             (doto (Label. (str (.getDayOfMonth d)))
                                               (.setId (str id "-day-" d))
                                               (.setPrefSize day-w day-h)
                                               (.setMinSize day-w day-h)
                                               (.setAlignment Pos/CENTER)
                                               (classed "date-day")
                                               (.pseudoClassStateChanged dim (not= month (YearMonth/from d)))
                                               (.pseudoClassStateChanged today-class (= d now))
                                               (.pseudoClassStateChanged marked (= d mark))
                                               (cond-> (= d value) (classed "taken"))
                                               (.setOnMouseClicked (handler (fn [_] (take! d))))))))))))
                (when @open (place!)))
        ;; Shows the month of `d`, with `d` marked.
        show-day! (fn [^LocalDate d]
                    (reset! view {:month (YearMonth/from d) :mark d})
                    (fill!))
        show! (fn []
                (when-let [scene (.getScene field)]
                  (let [root (.getRoot scene)]
                    (when (instance? Pane root)
                      (let [kids (.getChildren ^Pane root)]
                        (when-not (.contains kids cal) (.add kids cal)))
                      (show-day! (or (:date (parse (.getText field) (:locale @model) (today)))
                                     (:value @model) (today)))
                      (.applyCss cal)
                      (place!)
                      (when-not @open
                        (reset! open true)
                        (.setMouseTransparent cal false)
                        (ui/tween! cal ::fade {:ms (fade-ms)} [[(.opacityProperty cal) 1.0]]))))))
        ;; ‹ and ›: the month back or on, with the same day marked where it has one.
        turn! (fn [n]
                (let [{:keys [^YearMonth month mark]} @view
                      m (.plusMonths month (long n))
                      day (if mark (.getDayOfMonth ^LocalDate mark) 1)]
                  (reset! view {:month m :mark (.atDay m (min day (.lengthOfMonth m)))})
                  (fill!)))
        ;; Takes what is typed, or says why it cannot.
        commit! (fn []
                  (let [{:keys [optional locale]} @model
                        r (parse (.getText field) locale (today))]
                    (cond
                      (:date r) (take! (:date r))
                      (and (:empty r) optional) (take! nil)
                      :else (do (err! (error-text {:error :not-a-date}))
                                (close!)))))
        restore! (fn []
                   (err! nil)
                   (set-text! (value-text))
                   (close!)
                   (.selectAll field))
        on-key (fn [^KeyEvent e]
                 (let [code (.getCode e)
                       mark (:mark @view)]
                   (cond
                     (and @open (step-mark (or mark (today)) code))
                     (do (.consume e)
                         (show-day! (step-mark (or mark (:value @model) (today)) code)))

                     (= KeyCode/DOWN code)
                     (do (.consume e) (show!))

                     (= KeyCode/ENTER code)
                     (cond
                       (and @open mark) (do (.consume e) (take! mark))
                       @typed (do (.consume e) (commit!))
                       @open (do (.consume e) (close!)))

                     (= KeyCode/ESCAPE code)
                     (cond
                       ;; The first Escape closes the calendar and leaves the text.
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
                      (or (identical? n wrap) (identical? n cal)) true
                      :else (recur (.getParent ^Node n)))))
        leave-field! (fn []
                       (when @typed (commit!))
                       (close!))
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
                                ;; An open calendar follows what is typed.
                                (when @open
                                  (if-let [d (:date (parse (.getText field) (:locale @model) (today)))]
                                    (show-day! d)
                                    (do (swap! view assoc :mark nil) (fill!))))))))
    (.addListener (.sceneProperty field) (listener wire!))
    (.addListener (.localToSceneTransformProperty field) on-moved)
    (.addEventFilter field KeyEvent/KEY_PRESSED (handler on-key))
    (.addEventHandler field MouseEvent/MOUSE_PRESSED (handler (fn [_] (when-not @open (show!)))))
    (.addEventHandler icon MouseEvent/MOUSE_PRESSED
                      (handler (fn [^MouseEvent e]
                                 (.consume e)
                                 (.requestFocus field)
                                 (if @open (close!) (show!)))))
    (.setOnMouseClicked prev (handler (fn [_] (turn! -1))))
    (.setOnMouseClicked next (handler (fn [_] (turn! 1))))
    (.setOnMouseClicked today-link (handler (fn [_] (take! (today)))))
    ;; Scrolling over the open calendar moves nothing under it.
    (.addEventHandler cal ScrollEvent/SCROLL (handler (fn [^ScrollEvent e] (.consume e))))
    (StackPane/setAlignment icon Pos/CENTER_RIGHT)
    (doto field
      (classed "date-field")
      (.setMinHeight field-h)
      (.setPrefHeight field-h)
      (.setMaxHeight field-h)
      (.setMinWidth min-width)
      (.setPrefWidth field-w))
    (.setLabelFor label field)
    (.put (.getProperties box) ::parts
          {:model model :field field :label label :line line :cal cal :icon icon :wrap wrap
           :prev prev :next next :today today-link :title title :typed typed
           :value-text value-text :set-text! set-text! :close! close! :fill! fill! :open open})
    (doto box
      (.setFillWidth false)
      (.setSpacing 2.0)
      (classed "date-box")
      (-> .getChildren (.addAll ^Collection [label wrap line])))))

(defn set-model!
  "Tells the date picker what it is: `:id`, `:name`, the written `:value`,
  `:optional`, `:disabled`, `:tip`, `:locale`, `:first-day`, `:today` in place
  of the clock, and `:dispatch` with the `:write` event it sends through it.
  The field's text follows only a value that has changed, as after an Undo:
  never under typing."
  [^VBox box m]
  (let [{:keys [model ^TextField field ^Label label ^Label line ^Node cal ^Node icon ^Node wrap
                ^Node prev ^Node next ^Node today ^Node title typed value-text set-text! close!]}
        (.get (.getProperties box) ::parts)
        m (merge {:locale (Locale/getDefault)
                  :first-day (.getFirstDayOfWeek (WeekFields/of (Locale/getDefault)))}
                 (into {} (remove (comp nil? val) m)))
        old @model
        given (:value m)
        fresh (not= given (:given old))
        region (not= (:locale m) (:locale old))]
    (reset! model (assoc m :given given :value (if fresh given (:value old)) :error (:error old)))
    (let [id (:id m)]
      (.setId field id)
      (.setId line (str id "-line"))
      (.setId cal (str id "-calendar"))
      (.setId icon (str id "-mark"))
      (.setId prev (str id "-prev"))
      (.setId next (str id "-next"))
      (.setId today (str id "-today"))
      (.setId title (str id "-month")))
    (.setText label (:name m))
    (.setDisable wrap (boolean (:disabled m)))
    (when (:disabled m) (close!))
    ;; The hint, in grey, where the field may be empty.
    (.setPromptText field (when (:optional m) (show (LocalDate/of 2026 11 20) (:locale m))))
    (when (and (or fresh region) (not @typed) (not= (.getText field) (value-text)))
      (set-text! (value-text))
      (when (some-> (.getScene field) .getFocusOwner (identical? field))
        (.selectAll field)))))

(def ext-model
  (fx/make-ext-with-props
    {::model (prop/make (mutator/setter set-model!) lifecycle/scalar)}))

(defn date-picker-view
  "One date picker, with the label that names what it sets. `write` is an
  event, as the app's event handler takes it, and `dispatch` is the function
  that fires it: once, with the `:value` to keep, a LocalDate or nil. `value`
  is the written date. `optional` lets the field be empty. `locale` and
  `first-day` are the region's; `today` stands in for the clock. `tip` says
  why a `disabled` picker is off; the tooltip is on the box, so that one
  still shows it."
  [{:keys [disabled tip] :as props}]
  {:fx/type fx.ext.node/with-tooltip-props
   :props (if (and disabled tip) {:tooltip {:fx/type :tooltip :text tip}} {})
   :desc
   {:fx/type ext-model
    :props {::model (select-keys props [:id :name :value :optional :disabled :tip
                                        :locale :first-day :today :dispatch :write])}
    :desc {:fx/type fx/ext-instance-factory :create make-date-picker}}})
