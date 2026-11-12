(ns demo.ui
  "The part worth copying: buttons that answer a press, as requirements/gui.org,
  Buttons and Liquid Glass, ask. A reference, not a library: follow what it
  does, and take the code as one way to do it. Nothing here knows about the
  demo's page or its state (demo.button).

  The colour eases on hover, in the stylesheet. A button sinks on a press, stays
  sunk while held and springs back on release. Dragged off while held it rises,
  and Escape lets go of it. Held for 500 ms, a button with a second action fires
  it in place of its click, and a fill grows across it while it waits. Under
  Reduce Motion a button only changes colour. A disabled one never answers and
  says why. A busy one shows a spinner, does not move and does not fire again.

  What to take:

      button-view     one button: the kinds, the states, the second action
      glass-group     the capsule of glass that a toolbar's buttons share
      answer-press!   the press, the hold and the keys, for any Button
      ext-content     the smooth change of a button's words, Save to Saving
      follow-system!  Reduce Motion and Reduce Transparency, as they change
      press-look, press-timing   the numbers, as plain data

  The look is demo/glass.css: Apple's Liquid Glass, as near as JavaFX gets."
  (:require [cljfx.api :as fx]
            [cljfx.ext.node :as fx.ext.node]
            [cljfx.lifecycle :as lifecycle]
            [cljfx.mutator :as mutator]
            [cljfx.prop :as prop]
            [clojure.java.shell :as shell]
            [clojure.string :as str]
            [demo.icons :as icons])
  (:import [javafx.animation Interpolator KeyFrame KeyValue PauseTransition Timeline]
           [javafx.application Platform]
           [javafx.beans.value ChangeListener WritableValue]
           [javafx.css PseudoClass]
           [javafx.event ActionEvent EventHandler]
           [javafx.scene Node]
           [javafx.scene.control Button]
           [javafx.scene.input KeyCode KeyEvent]
           [javafx.scene.layout Pane Region]
           [javafx.scene.shape Rectangle]
           [javafx.util Duration]))

;;; Look and timing: plain data, so they are tested without a window

(def press-ms 120)
(def spring-ms 420)
(def hold-ms 500)
;; A quick click is over before the fill shows.
(def charge-delay-ms 150)
(def content-ms 220)
(def fade-ms 120)
(defn press-look
  "How the button sits: sunk a little while pressed or held, at rest otherwise.
  Under Reduce Motion it never moves, and neither does a button that is busy."
  [{:keys [pressed reduce inert]}]
  (if (and pressed (not reduce) (not inert))
    {:scale 0.97 :y 1.0}
    {:scale 1.0 :y 0.0}))

(defn press-timing
  "How the button gets to its look: a press answers fast, a release springs
  back, and Reduce Motion moves nothing."
  [{:keys [pressed reduce]}]
  (cond reduce {:ms 0 :spring false}
        pressed {:ms press-ms :spring false}
        :else {:ms spring-ms :spring true}))

;;; Motion

(def ease-out (Interpolator/SPLINE 0.2 0.0 0.0 1.0))
;; Late: the spinner stays faint until there is nearly room for it.
(def ease-in (Interpolator/SPLINE 0.6 0.0 1.0 1.0))

;; A damped spring: overshoots a little, then settles on exactly 1.
(def spring
  (proxy [Interpolator] []
    (curve [t]
      (let [t (double t)]
        (if (>= t 1.0)
          1.0
          (- 1.0 (* (Math/exp (* -6.0 t)) (Math/cos (* 9.0 t)))))))))

(defonce *reduce (atom false))

(defn- handler ^EventHandler [f]
  (reify EventHandler (handle [_ e] (f e))))

(defn tween!
  "Animates each [property target] pair over `ms`, after `delay` ms. Whatever is
  still running under `k` on `node` stops first, so the new tween starts from
  where things are now."
  [^Node node k {:keys [ms delay easing on-done] :or {delay 0 easing ease-out}} pairs]
  (let [props (.getProperties node)]
    (some-> ^Timeline (.get props k) .stop)
    (if (zero? ms)
      (do (doseq [[p v] pairs] (.setValue ^WritableValue p v))
          (when on-done (on-done)))
      (let [values (into-array KeyValue (for [[p v] pairs] (KeyValue. p v easing)))
            timeline (Timeline. (into-array KeyFrame [(KeyFrame. (Duration/millis ms) values)]))]
        (.setDelay timeline (Duration/millis delay))
        (when on-done (.setOnFinished timeline (handler (fn [_] (on-done)))))
        (.put props k timeline)
        (.play timeline)))))

(defn- inert?
  "True while the button's action runs or has just finished: it takes no press."
  [^Button button]
  (boolean (.get (.getProperties button) ::inert)))

(defn- sit!
  [^Node box ^Button button pressed]
  (let [state {:pressed pressed :reduce @*reduce :inert (inert? button)}
        {:keys [scale y]} (press-look state)
        {:keys [ms] :as timing} (press-timing state)]
    (tween! box ::press {:ms ms :easing (if (:spring timing) spring ease-out)}
            [[(.scaleXProperty box) scale]
             [(.scaleYProperty box) scale]
             [(.translateYProperty box) y]])))

(defn- charge!
  "The fill that says a hold is counting. `:start` grows it across the button
  by the time the second action fires, `:fired` flashes it full and `:stop`
  takes it away. Under Reduce Motion it fades in where it would have grown."
  [^Region fill step]
  (let [^Rectangle clip (.getClip fill)
        width (.getWidth fill)]
    (case step
      :start (let [calm @*reduce]
               (.setWidth clip (if calm width 0.0))
               (.setOpacity fill (if calm 0.0 1.0))
               (tween! fill ::charge {:ms (- hold-ms charge-delay-ms) :delay charge-delay-ms
                                      :easing Interpolator/LINEAR}
                       [(if calm
                          [(.opacityProperty fill) 1.0]
                          [(.widthProperty clip) width])]))
      :fired (do (.setWidth clip width)
                 (.setOpacity fill 1.0)
                 (tween! fill ::charge {:ms 300} [[(.opacityProperty fill) 0.0]]))
      :stop (tween! fill ::charge {:ms fade-ms} [[(.opacityProperty fill) 0.0]]))))

(def ^PseudoClass pressed-within (PseudoClass/getPseudoClass "pressed-within"))

(defn answer-press!
  "Wires `button`, which sits in `box` with its hold fill and mark; the box is
  what moves.

  The box is sunk while the button is armed: the mouse down over it, or Space
  down with it focused. Return belongs to the main button, wherever the focus is. Dragged off it disarms, so it rises, and back
  over the button it sinks again. Escape lets go of a press: nothing fires, and
  it stays let go until the mouse or key is up.

  `on-hold`, if given, is the second action. It fires once the button has been
  armed for `hold-ms`, `fill` growing meanwhile, and the click that letting go
  would fire is swallowed."
  [^Node box ^Button button ^Region fill on-hold]
  (let [fired (atom false)
        cancelled (atom false)
        key-down (atom false)
        press-key? (fn [^KeyEvent e] (= KeyCode/SPACE (.getCode e)))
        disarmed-at (atom 0)
        rise (PauseTransition. (Duration/millis press-ms))
        timer (PauseTransition. (Duration/millis hold-ms))
        ;; Later, not now: the click of this release must still find `fired` set.
        forget! (fn [] (Platform/runLater
                         #(when-not (or (.isPressed button) (.isArmed button) @key-down)
                            (reset! fired false)
                            (reset! cancelled false))))]
    (when fill
      (let [clip (Rectangle.)]
        (.bind (.heightProperty clip) (.heightProperty fill))
        (.setClip fill clip)
        (.setOpacity fill 0.0)))
    (.setOnFinished timer (handler (fn [_]
                                     (when (and (.isArmed button) (not @fired))
                                       (reset! fired true)
                                       (when fill (charge! fill :fired))
                                       (on-hold)))))
    (.addListener (.armedProperty button)
                  (reify ChangeListener
                    (changed [_ _ _ armed]
                      (if (and armed @cancelled)
                        (.disarm button)
                        (let [counting (and armed on-hold (not @fired) (not (inert? button)))]
                          (sit! box button armed)
                          ;; The glass shows the press at its own rim: the box when the
                          ;; button has glass to itself, else the group it lies on.
                          (.pseudoClassStateChanged box pressed-within (boolean armed))
                          (some-> (.getParent box)
                                  (.pseudoClassStateChanged pressed-within (boolean armed)))
                          (if counting (.playFromStart timer) (.stop timer))
                          (when fill
                            (cond counting (charge! fill :start)
                                  (not @fired) (charge! fill :stop)))
                          (when-not armed
                            (reset! disarmed-at (System/nanoTime))
                            (forget!)))))))
    (.addListener (.pressedProperty button)
                  (reify ChangeListener
                    (changed [_ _ _ pressed] (when-not pressed (forget!)))))
    (.addEventFilter button ActionEvent/ACTION
                     (handler (fn [^ActionEvent e] (when @fired (.consume e)))))
    (.addEventFilter button KeyEvent/KEY_PRESSED
                     (handler (fn [^KeyEvent e]
                                (when (press-key? e) (reset! key-down true))
                                (when (and (= KeyCode/ESCAPE (.getCode e)) (.isArmed button))
                                  (reset! cancelled true)
                                  (.disarm button)
                                  (.consume e)))))
    (.addEventHandler button KeyEvent/KEY_RELEASED
                      (handler (fn [^KeyEvent e]
                                 (when (press-key? e)
                                   (reset! key-down false)
                                   (forget!)))))
    ;; Fired with no press at all - Return on the main button, or the right-click
    ;; menu - it still answers: it sinks once and springs back.
    (.setOnFinished rise (handler (fn [_] (when-not (.isArmed button) (sit! box button false)))))
    (.addEventHandler button ActionEvent/ACTION
                      (handler (fn [_]
                                 (when (and (not (.isArmed button))
                                            (> (- (System/nanoTime) (long @disarmed-at)) 100000000))
                                   (sit! box button true)
                                   (.playFromStart rise)))))))

(def spinner-size 14.0)
(def spinner-gap 6.0)

(defn- content!
  "Makes a change of the button's words smooth: Save, Saving, Saved. The button
  always holds its spinner; idle, the spinner has no width and cannot be seen.
  Going busy, the button glides to its new width while the spinner opens beside
  the words and fades in, so the words never blank and neither the button nor
  its neighbours jump. Each frame has room for the words it had, so they are
  never cut shorter. Under Reduce Motion the sizes change at once and the
  spinner only fades."
  [^Button button {:keys [busy inert]}]
  (let [props (.getProperties button)
        first? (not (.containsKey props ::busy))
        ^Region spinner (.getGraphic button)
        size (if busy spinner-size 0.0)
        gap (if busy spinner-gap 0.0)
        opacity (if busy 1.0 0.0)
        ;; Read now: the render that changed the words has not been laid out yet.
        from (.getWidth button)]
    (.put props ::busy busy)
    (.put props ::inert inert)
    (if first?
      (do (.setMinWidth spinner 0.0)
          (.setPrefWidth spinner size)
          (.setGraphicTextGap button gap)
          (.setOpacity spinner opacity)
          (.setVisible spinner (boolean busy)))
      ;; Later: by then the words of this render are in, whichever was set first.
      (Platform/runLater
        (fn []
          (some-> ^Timeline (.get props ::content) .stop)
          (let [calm @*reduce
                size-now (.getPrefWidth spinner)
                gap-now (.getGraphicTextGap button)
                ;; The width it is going to: measured with the spinner as it will be.
                to (do (.setPrefWidth spinner size)
                       (.setGraphicTextGap button gap)
                       (.setPrefWidth button Region/USE_COMPUTED_SIZE)
                       (.applyCss button)
                       (.prefWidth button -1.0))
                fade [(.opacityProperty spinner) opacity]
                glide? (and (pos? from) (not calm))]
            (when glide?
              (.setPrefWidth spinner size-now)
              (.setGraphicTextGap button gap-now)
              (.setPrefWidth button from))
            (when busy (.setVisible spinner true))
            (tween! button ::content
                    {:ms (if calm fade-ms content-ms)
                     :on-done (fn []
                                (.setPrefWidth button Region/USE_COMPUTED_SIZE)
                                (when-not (.get props ::busy) (.setVisible spinner false)))}
                    (if glide?
                      [fade
                       [(.prefWidthProperty button) to]
                       [(.prefWidthProperty spinner) size]
                       [(.graphicTextGapProperty button) gap]]
                      [fade]))))))))

(def ext-content
  (fx/make-ext-with-props
    {::content (prop/make (mutator/setter content!) lifecycle/scalar)}))

;;; The system's settings

(defonce *follow-system (atom true))

(defn increase-contrast?
  "macOS's Increase Contrast setting, which JavaFX does not report. Elsewhere,
  and when it cannot be read, off. It runs a process: call it off the UI thread."
  []
  (try
    (= "1" (str/trim (:out (shell/sh "defaults" "read" "com.apple.universalaccess"
                                     "increaseContrast"))))
    (catch Exception _ false)))

(defn follow-system!
  "Keeps the app in step with Reduce Motion and Reduce Transparency as they
  change, while it runs. Reduce Motion is kept here, in `*reduce`.
  `on-transparency` is called with true or false, now and at every change.
  Call it on the UI thread."
  [on-transparency]
  (let [prefs (Platform/getPreferences)
        sync! (fn []
                (when @*follow-system
                  (reset! *reduce (.isReducedMotion prefs))
                  (on-transparency (.isReducedTransparency prefs))))
        on-change (reify ChangeListener (changed [_ _ _ _] (sync!)))]
    (.addListener (.reducedMotionProperty prefs) on-change)
    (.addListener (.reducedTransparencyProperty prefs) on-change)
    (sync!)))

;;; The views

(def icon-size 18.0)

(defn icon-view
  "One icon, by name, `size` px square. It keeps the whole box it was drawn on,
  so icons of different shapes line up, and its colour comes from the
  stylesheet (`.icon`). `flip` mirrors it left to right."
  [{:keys [icon size flip] :or {size icon-size}}]
  (let [scale (/ size icons/box)]
    ;; The outer group has the scaled size; a group's own scale is not in its own.
    {:fx/type :group
     :children [{:fx/type :group
                 :scale-x (if flip (- scale) scale)
                 :scale-y scale
                 :children [{:fx/type :rectangle :width icons/box :height icons/box :fill :transparent}
                            {:fx/type :svg-path :style-class "icon" :content (icons/path icon)}]}]}))

(def glass-padding 4)

(defn button-view
  "One button. `click` and `hold` are events, as the app's event handler takes
  them; `hold` is the second action, and `dispatch` is the function that fires
  it, the app's event handler as a rule. A button that has a second action
  shows a mark at its trailing edge, a fill that grows while it is held, and
  offers the second action on its right-click menu as well.

  `icon` is the name of an icon in demo.icons, and `icon-flip` mirrors it; with
  no `text` the button is a circle, and `name` is
  what a screen reader calls it. `tip` is the tooltip, on the box so that a
  disabled button still shows why it is off. `fill` makes the button as wide as
  its place, for a pair of equal width. A button given `:busy` can be busy.

  `glass` gives the button a capsule of glass to itself, `:tinted` for the main
  action. The glass is then the box: all of it sinks, lightens and fills, so no
  smaller shape ever shows inside it."
  [{:keys [id text name icon primary destructive failed click hold hold-text tip
           disabled busy inert fill default glass dispatch icon-flip] :as props}]
  {:fx/type fx/ext-on-instance-lifecycle
   :on-created (fn [^Pane box]
                 (let [[^Button button & more] (.getChildren box)]
                   (.setAccessibleText button (or name text))
                   (answer-press! box button (when hold (first more))
                                  (when hold #(dispatch hold)))))
   :desc
   {:fx/type fx.ext.node/with-tooltip-props
    :props (if tip {:tooltip {:fx/type :tooltip :text tip}} {})
    :desc
    {:fx/type :stack-pane
     :style-class (case glass
                    :tinted ["glass-group" "tinted"]
                    :regular ["glass-group"]
                    [])
     :padding (if glass glass-padding 0)
     :max-width (if fill Double/MAX_VALUE :use-pref-size)
     :max-height :use-pref-size
     :children
     (cond-> [(cond-> {:fx/type :button
                       :id id
                       :style-class (cond-> ["button"]
                                      primary (conj "primary")
                                      destructive (conj "destructive")
                                      failed (conj "destructive")
                                      inert (conj "inert")
                                      hold (conj "has-hold")
                                      (not text) (conj "icon-only"))
                       :text text
                       :max-width (if fill Double/MAX_VALUE :use-pref-size)
                       :disable (boolean disabled)
                       ;; The main button: Return presses it, wherever the focus is.
                       :default-button (boolean default)
                       :on-action click}
                tip (assoc :accessible-help tip)
                icon (assoc :graphic {:fx/type icon-view :icon icon :flip icon-flip})
                hold (assoc :context-menu
                            {:fx/type :context-menu
                             :items [{:fx/type :menu-item :text hold-text :on-action hold}]})
                ;; A button that can be busy always holds its spinner.
                (contains? props :busy)
                (#(hash-map :fx/type ext-content
                            :props {::content {:busy (boolean busy) :inert (boolean inert) :text text}}
                            :desc (assoc % :graphic {:fx/type :progress-indicator
                                                     :pref-height spinner-size}))))]
       hold (conj {:fx/type :region
                   :style-class "hold-fill"
                   :mouse-transparent true
                   ;; Out to the edge of the glass, when the button has its own.
                   :stack-pane/margin (if glass (- glass-padding) 0)}
                  {:fx/type :polygon
                   :style-class "hold-mark"
                   ;; At the trailing edge: a capsule has no corner to hold it.
                   :points [0 0 7 0 3.5 4.5]
                   :mouse-transparent true
                   :stack-pane/alignment :center-right
                   :stack-pane/margin {:right 12}}))}}})

(defn glass-group
  "One capsule of glass that the buttons of a toolbar share. They have no glass
  of their own: glass is never stacked on glass. Each is a capsule inside it,
  on the same centre."
  [{:keys [tinted children]}]
  {:fx/type :h-box
   :style-class (cond-> ["glass-group"] tinted (conj "tinted"))
   :alignment :center
   :spacing 2
   :padding glass-padding
   :max-width :use-pref-size
   :max-height :use-pref-size
   :children children})
