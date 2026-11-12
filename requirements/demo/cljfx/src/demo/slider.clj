(ns demo.slider
  "The part worth copying: a slider that sets one value, as Sliders in
  requirements/components.org asks. A reference, not a library: follow what it
  does, and take the code as one way to do it. Nothing here knows about the
  demo's page or its state (demo.slider-page).

  One glass capsule on a level track. The thumb follows a drag at once, grows
  while it is held and stretches while it moves. A press on the track glides
  the thumb to the pointer and goes on as a drag. What the slider sets follows
  the thumb live; the value is written once, when the drag ends. Escape puts it
  back, a double click puts it at its default, and the keyboard moves it. A
  bubble shows the value while it changes.

  What to take:

      slider-view     one slider: its label, its tooltip and the control
      make-slider     the control itself, a Pane, for use without cljfx
      value-at, x-of, key-value, stretch-for, thumb-look, said
                      the numbers and the rules, as plain data

  The look is in demo/glass.css, under `.slider-box`. Motion comes from
  demo.ui: its tween, its spring and its Reduce Motion."
  (:require [cljfx.api :as fx]
            [cljfx.ext.node :as fx.ext.node]
            [cljfx.lifecycle :as lifecycle]
            [cljfx.mutator :as mutator]
            [cljfx.prop :as prop]
            [demo.ui :as ui])
  (:import [javafx.animation PauseTransition]
           [javafx.beans.property SimpleDoubleProperty]
           [javafx.beans.value ChangeListener]
           [javafx.css PseudoClass]
           [javafx.event EventHandler]
           [javafx.scene AccessibleAction AccessibleAttribute AccessibleRole Cursor Node]
           [javafx.scene.control Label]
           [javafx.scene.input KeyCode KeyEvent MouseButton MouseEvent]
           [javafx.scene.layout Pane Region]
           [javafx.util Duration]))

;;; Look and rules: plain data, so they are tested without a window

(def track-px 4.0)
;; The height to take hold of: that of a button.
(def hold-px 44.0)
(def thumb-w 28.0)
(def thumb-h 20.0)
;; Moving, the thumb is up to this much wider.
(def stretch-max 8.0)
(def stretch-ms 220)
(def min-width 120.0)
(def snap-px 4.0)
(def held-scale 1.1)
;; How long the bubble stays after a key press.
(def bubble-ms 1000)
;; Key presses closer than this are one step for Undo.
(def same-step-ms 1000)
;; A double click that follows a click on the track is one step with it.
(def double-click-ms 500)
(def bubble-gap 8.0)
(def edge-gap 4.0)

(defn- travel
  "How far the middle of the thumb runs, in a slider `width` wide."
  [width]
  (max 1.0 (- width thumb-w)))

(defn x-of
  "Where the middle of the thumb sits for `value`, in a slider `width` wide."
  [{lo :min hi :max} width value]
  (+ (/ thumb-w 2.0) (* (travel width) (/ (- value lo) (- hi lo)))))

(defn value-at
  "The value with the middle of the thumb at `x`: no further than either end,
  and the default itself within `snap-px` of its notch."
  [{lo :min hi :max default :default :as model} width x]
  (if (and default (<= (Math/abs (double (- x (x-of model width default)))) snap-px))
    default
    (let [part (-> (/ (- x (/ thumb-w 2.0)) (travel width)) (max 0.0) (min 1.0))]
      (+ lo (* part (- hi lo))))))

(def key-names
  {KeyCode/LEFT :left KeyCode/DOWN :down KeyCode/RIGHT :right KeyCode/UP :up
   KeyCode/HOME :home KeyCode/END :end})

(defn key-value
  "Where a key takes `value`: an arrow 1% of the range, with Shift 10%, Home
  and End the two ends. Never past an end."
  [{lo :min hi :max} value key shift]
  (let [step (* (/ (- hi lo) 100.0) (if shift 10.0 1.0))]
    (case key
      (:left :down) (max lo (- value step))
      (:right :up) (min hi (+ value step))
      :home lo
      :end hi)))

(defn stretch-for
  "How much wider the thumb is while it moves at `speed`, in px a ms: more the
  faster, and nothing under Reduce Motion."
  [speed reduce]
  (if reduce 0.0 (min stretch-max (* stretch-max speed))))

(defn thumb-look
  "How the thumb sits: grown a little while held. Under Reduce Motion it never
  grows."
  [{:keys [held reduce]}]
  {:scale (if (and held (not reduce)) held-scale 1.0)})

(defn value-text
  "The value as it is shown: a whole number in its unit."
  [{:keys [unit]} value]
  (str (Math/round (double value)) unit))

(defn said
  "What a screen reader says for a slider, as its name and the kind of thing it
  is. The value goes in the name, and so does the reason a slider is off; one
  that is off is called dimmed, as macOS calls its own."
  [{:keys [name disabled tip] :as model} value]
  {:name (if (and disabled tip)
           (str name ". " tip)
           (str name ", " (value-text model value)))
   :kind (when disabled "dimmed slider")})

(defn tip-text
  "The tooltip: the value, since a slider at rest shows no number, or why the
  slider is off."
  [{:keys [name disabled tip] :as model} value]
  (if (and disabled tip) tip (str name ": " (value-text model value))))

(defn bubble-left
  "The left edge of a bubble `width` wide, centred over `centre` and kept whole
  between `lo` and `hi`: near an edge it slides sideways."
  [centre width lo hi]
  (-> (- centre (/ width 2.0))
      (min (- hi edge-gap width))
      (max (+ lo edge-gap))))

;;; The control

(def ^PseudoClass dragging (PseudoClass/getPseudoClass "dragging"))

(defn- handler ^EventHandler [f]
  (reify EventHandler (handle [_ e] (f e))))

(defn- listener ^ChangeListener [f]
  (reify ChangeListener (changed [_ _ _ _] (f))))

(defn- part
  "One piece of the slider, placed by hand."
  ^Region [class]
  (doto (Region.)
    (.setManaged false)
    (.setMouseTransparent true)
    (-> .getStyleClass (.add class))))

(defn- stop!
  "Stops whatever tween runs under `k` on `node`, where it is."
  [node k]
  (ui/tween! node k {:ms 0} []))

(defn make-slider
  "The control: a Pane with its track, fill, notch, thumb and bubble. It is
  told what it is with `set-model!`, and it tells the app through the model's
  `dispatch`: the `live` event at every move, the `write` event once."
  ^Pane []
  (let [model (atom {:min 0.0 :max 100.0 :value 0.0 :unit ""})
        value (SimpleDoubleProperty. 0.0)
        stretch (SimpleDoubleProperty. 0.0)
        ;; A press in progress: where it began and how it holds the thumb.
        ;; {:dead true} is a press that Escape or a double click has ended.
        drag (atom nil)
        keyed (atom false)
        quiet (atom false)
        last-write (atom {:at 0 :by nil})
        nudge (volatile! nil)
        track (part "slider-track")
        fill (part "slider-fill")
        notch (part "slider-notch")
        thumb (doto (part "slider-thumb") (.setMouseTransparent false))
        bubble (doto (Label.)
                 (.setManaged false)
                 (.setMouseTransparent true)
                 (.setOpacity 0.0)
                 (.setVisible false)
                 (-> .getStyleClass (.add "slider-bubble")))
        ;; The value, its ends and its two actions, for a screen reader.
        pane (proxy [Pane] []
               (queryAccessibleAttribute [attr params]
                 (condp = attr
                   AccessibleAttribute/VALUE (.get value)
                   AccessibleAttribute/MIN_VALUE (double (:min @model))
                   AccessibleAttribute/MAX_VALUE (double (:max @model))
                   (let [^Pane this this]
                     (proxy-super queryAccessibleAttribute attr params))))
               (executeAccessibleAction [action params]
                 (condp = action
                   AccessibleAction/INCREMENT (@nudge :right)
                   AccessibleAction/DECREMENT (@nudge :left)
                   (let [^Pane this this]
                     (proxy-super executeAccessibleAction action params)))))
        hide (PauseTransition. (Duration/millis bubble-ms))
        ;; Between which two places the bubble stays whole: the window, or the
        ;; scrolling area the slider is in.
        edges (fn []
                (let [scene (.getScene pane)
                      ^Node clipper (loop [n (.getParent pane)]
                                      (cond (nil? n) nil
                                            (.contains (.getStyleClass n) "viewport") n
                                            :else (recur (.getParent n))))
                      local #(.getX (.sceneToLocal pane (double %) 0.0))
                      inf Double/POSITIVE_INFINITY]
                  (if-not scene
                    [(- inf) inf]
                    (let [b (some-> clipper (.localToScene (.getLayoutBounds clipper)))]
                      [(local (max 0.0 (if b (.getMinX b) 0.0)))
                       (local (min (.getWidth scene) (if b (.getMaxX b) inf)))]))))
        place! (fn []
                 (let [m @model
                       w (.getWidth pane)
                       cy (/ (.getHeight pane) 2.0)
                       x (x-of m w (.get value))
                       tw (+ thumb-w (.get stretch))
                       top (- cy (/ track-px 2.0))]
                   (.resizeRelocate track 0.0 top w track-px)
                   (.resizeRelocate fill 0.0 top x track-px)
                   (.setVisible notch (boolean (:default m)))
                   (when-let [d (:default m)]
                     (.resizeRelocate notch (- (x-of m w d) 1.0) (- cy 5.0) 2.0 10.0))
                   (.resizeRelocate thumb (- x (/ tw 2.0)) (- cy (/ thumb-h 2.0)) tw thumb-h)
                   (let [bw (.prefWidth bubble -1.0)
                         bh (.prefHeight bubble -1.0)
                         [lo hi] (edges)]
                     (.resizeRelocate bubble (bubble-left x bw lo hi)
                                      (- cy (/ thumb-h 2.0) bubble-gap bh) bw bh))))
        say! (fn []
               (let [{:keys [name kind]} (said @model (.get value))]
                 (.setAccessibleText pane name)
                 (.setAccessibleRoleDescription pane kind)))
        tell! (fn [k extra]
                (let [{:keys [dispatch] :as m} @model]
                  (when (and dispatch (k m))
                    (dispatch (merge (k m) extra)))))
        ;; Written once, and only a value that changed. `by` says what moved it.
        write! (fn [v by]
                 (let [v (double v)
                       now (System/nanoTime)
                       {:keys [at] before :by} @last-write
                       within #(< (- now at) (* 1000000 %))
                       same (case by
                              :key (and (= :key before) (within same-step-ms))
                              :reset (and (= :click before) (within double-click-ms))
                              false)]
                   (when (not= v (double (:value @model)))
                     (swap! model assoc :value v)
                     (reset! last-write {:at now :by by})
                     (tell! :write {:value v :same-step (boolean same)}))))
        glide! (fn [to]
                 (ui/tween! pane ::glide {:ms (if @ui/*reduce 0 ui/press-ms)} [[value (double to)]]))
        ;; Faded out it is not there at all: a screen reader finds no number at rest.
        bubble! (fn [on]
                  (when on (.setVisible bubble true))
                  (ui/tween! bubble ::fade
                             {:ms ui/fade-ms :on-done #(when-not on (.setVisible bubble false))}
                             [[(.opacityProperty bubble) (if on 1.0 0.0)]]))
        ;; Held, the thumb grows; let go, it springs back to its size.
        look! (fn [held]
                (let [calm @ui/*reduce
                      {:keys [scale]} (thumb-look {:held held :reduce calm})]
                  (when-not held (stop! thumb ::stretch))
                  (ui/tween! thumb ::look
                             {:ms (cond calm 0 held ui/press-ms :else ui/spring-ms)
                              :easing (if held ui/ease-out ui/spring)}
                             (cond-> [[(.scaleXProperty thumb) scale]
                                      [(.scaleYProperty thumb) scale]]
                               (not held) (conj [stretch 0.0])))
                  (.pseudoClassStateChanged pane dragging (boolean held))
                  ;; Closed for the whole drag, wherever the pointer goes.
                  (some-> (.getScene pane) (.setCursor (when held Cursor/CLOSED_HAND)))))
        ;; Moving, the thumb is wider, and eases back once it is still.
        stretch! (fn [px since now]
                   (let [ms (max 1.0 (/ (- now since) 1e6))]
                     (.set stretch (max (.get stretch)
                                        (stretch-for (/ (Math/abs (double px)) ms) @ui/*reduce)))
                     (ui/tween! thumb ::stretch {:ms stretch-ms} [[stretch 0.0]])))
        local-x (fn [^MouseEvent e] (.getX (.sceneToLocal pane (.getSceneX e) (.getSceneY e))))
        on-press (fn [^MouseEvent e]
                   (when (= MouseButton/PRIMARY (.getButton e))
                     (.consume e)
                     (.requestFocus pane)
                     (let [m @model
                           w (.getWidth pane)
                           px (local-x e)
                           tx (x-of m w (.get value))
                           now (System/nanoTime)]
                       (cond
                         ;; A double click: back to the default.
                         (and (= 2 (.getClickCount e)) (:default m))
                         (do (reset! drag {:dead true})
                             (glide! (:default m))
                             (write! (:default m) :reset))
                         ;; On the thumb: it is held where it was taken.
                         (<= (Math/abs (double (- px tx))) (/ (+ thumb-w (.get stretch)) 2.0))
                         (do (reset! drag {:start (.get value) :grab (- px tx) :x px :t now})
                             (look! true)
                             (bubble! true))
                         ;; On the track: the thumb glides to the pointer.
                         :else
                         (let [to (value-at m w px)]
                           (reset! drag {:start (.get value) :grab 0.0 :x px :t now :to to})
                           (glide! to)
                           (look! true)
                           (bubble! true))))))
        on-drag (fn [^MouseEvent e]
                  (when-let [d @drag]
                    (.consume e)
                    (when-not (:dead d)
                      (let [px (local-x e)
                            now (System/nanoTime)]
                        (stop! pane ::glide)
                        (stretch! (- px (:x d)) (:t d) now)
                        (swap! drag assoc :x px :t now :to nil :moved true)
                        (.set value (double (value-at @model (.getWidth pane) (- px (:grab d)))))))))
        on-release (fn [^MouseEvent e]
                     (when-let [d @drag]
                       (.consume e)
                       (reset! drag nil)
                       (when-not (:dead d)
                         ;; A click on the track is written where the glide ends.
                         (write! (or (:to d) (.get value)) (if (:moved d) :drag :click))
                         (look! false)
                         (bubble! false))))
        on-key (fn [^KeyEvent e]
                 (let [code (.getCode e)
                       d @drag]
                   (cond
                     ;; Escape during a drag: back to where it began, nothing written.
                     (and (= KeyCode/ESCAPE code) d (not (:dead d)))
                     (do (.consume e)
                         (stop! pane ::glide)
                         (reset! drag {:dead true})
                         (.set value (double (:start d)))
                         (look! false)
                         (bubble! false))
                     (key-names code)
                     (do (.consume e)
                         (when-not d
                           (reset! keyed true)
                           (.set value (double (key-value @model (.get value) (key-names code)
                                                          (.isShiftDown e))))
                           (bubble! true)
                           (.playFromStart hide))))))
        ;; A held key writes once, when it is let go.
        on-key-up (fn [^KeyEvent e]
                    (when (key-names (.getCode e))
                      (.consume e)
                      (when @keyed
                        (reset! keyed false)
                        (write! (.get value) :key))))]
    (vreset! nudge (fn [key]
                     (when-not (.isDisabled pane)
                       (.set value (double (key-value @model (.get value) key false)))
                       (write! (.get value) :key))))
    (.setOnFinished hide (handler (fn [_] (when-not @drag (bubble! false)))))
    (.addListener value (listener (fn []
                                    (.setText bubble (value-text @model (.get value)))
                                    (place!)
                                    (say!)
                                    (when-not @quiet (tell! :live {:value (.get value)})))))
    (.addListener stretch (listener place!))
    (.addListener (.widthProperty pane) (listener place!))
    (.addListener (.heightProperty pane) (listener place!))
    (.addEventHandler pane MouseEvent/MOUSE_PRESSED (handler on-press))
    (.addEventHandler pane MouseEvent/MOUSE_DRAGGED (handler on-drag))
    (.addEventHandler pane MouseEvent/MOUSE_RELEASED (handler on-release))
    (.addEventHandler pane KeyEvent/KEY_PRESSED (handler on-key))
    (.addEventHandler pane KeyEvent/KEY_RELEASED (handler on-key-up))
    (.put (.getProperties pane) ::parts
          {:model model :value value :quiet quiet :drag drag :place! place! :say! say!})
    (doto pane
      (-> .getStyleClass (.add "slider-box"))
      (-> .getChildren (.addAll ^java.util.Collection [track fill notch thumb bubble]))
      (.setAccessibleRole AccessibleRole/SLIDER)
      (.setFocusTraversable true)
      (.setMinHeight hold-px)
      (.setPrefHeight hold-px)
      (.setMaxHeight hold-px)
      (.setMinWidth min-width)
      (.setPrefWidth 240.0)
      (.setMaxWidth Double/MAX_VALUE))))

(defn set-model!
  "Tells the slider what it is: `:id`, `:name`, `:min`, `:max`, `:default`,
  `:unit`, `:disabled`, `:tip`, the written `:value`, and `:dispatch` with the
  `:live` and `:write` events it sends through it. The thumb moves only when
  the value given has changed, as after an Undo: never under a drag."
  [^Pane pane m]
  (let [{:keys [model ^SimpleDoubleProperty value quiet drag place! say!]}
        (.get (.getProperties pane) ::parts)
        m (-> (merge {:min 0.0 :max 100.0 :unit ""} m)
              (update :min double) (update :max double) (update :value double))
        old @model
        given (:value m)
        changed (not= given (:given old))]
    (reset! model (assoc m :given given :value (if changed given (:value old))))
    (.setId pane (:id m))
    (.setDisable pane (boolean (:disabled m)))
    (when (and changed (not @drag))
      (reset! quiet true)
      (.set value (double given))
      (reset! quiet false))
    (.setText ^Label (last (.getChildren pane)) (value-text m (.get value)))
    (place!)
    (say!)))

(def ext-model
  (fx/make-ext-with-props
    {::model (prop/make (mutator/setter set-model!) lifecycle/scalar)}))

(defn slider-view
  "One slider, under the label that names what it sets. `live` and `write` are
  events, as the app's event handler takes them, and `dispatch` is the function
  that fires them: `live` at every move with the `:value` so far, `write` once
  with the `:value` to keep and `:same-step` when it belongs to the Undo step
  before it. `value` is the written value. `tip` says why a `disabled` slider
  is off; the tooltip is on the box, so that one still shows it."
  [{:keys [value] :as props}]
  {:fx/type fx.ext.node/with-tooltip-props
   :props {:tooltip {:fx/type :tooltip :text (tip-text props value)}}
   :desc
   {:fx/type :v-box
    :spacing 2
    :max-width Double/MAX_VALUE
    :children [{:fx/type :label
                :style-class ["label" "slider-label"]
                :text (:name props)}
               {:fx/type ext-model
                :props {::model (select-keys props [:id :name :min :max :default :unit :disabled
                                                    :tip :value :dispatch :live :write])}
                :desc {:fx/type fx/ext-instance-factory :create make-slider}}]}})
