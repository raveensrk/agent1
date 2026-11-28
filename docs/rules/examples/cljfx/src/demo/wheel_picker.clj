(ns demo.wheel-picker
  "An experiment: a time picker of spinning wheels, after the iOS Clock app's
  alarm picker and Apple's Human Interface Guidelines for pickers - hour,
  minute and AM/PM wheels side by side, one band across the middle marking
  what is picked, rows curving away as on a drum. Built to compare with
  demo.clock-dial, so it offers the same times: any minute, 00 to 59.
  Not part of requirements/components.org, which rules out wheels.

  Drag a wheel and let go to fling it, scroll over it, or click a row to bring
  it to the band. A wheel coasts, slows and snaps onto a row; the time is
  written when every wheel rests.

  What to take:

      wheel-picker-view   the three wheels and their band
      on-input, tick      the rules, as plain data, tested without a window

  A wheel is {:offset rows :vel rows-per-s :target rows-or-nil :quiet s
  :drag nil-or-map}: the row at the band is the offset rounded."
  (:import [javafx.scene.input MouseEvent ScrollEvent]))

;;; Rules: plain data

(def row-h 36.0)
(def visible 5)
(def wheel-h (* row-h visible))
(def mid (/ wheel-h 2))
;; Each row turns the drum this far; the radius makes a row row-h tall at the band.
(def step-rad (Math/toRadians 24.0))
(def radius (/ row-h step-rad))

(def wheels
  [{:key :h :opts (mapv str (cons 12 (range 1 12))) :loop true :width 74}
   {:key :m :opts (mapv #(format "%02d" %) (range 60)) :loop true :width 74}
   {:key :p :opts ["AM" "PM"] :loop false :width 64}])

(defn wheel-at [i] {:offset (double i) :vel 0.0 :target nil :quiet 1.0 :drag nil})

(def start {:h (wheel-at 9) :m (wheel-at 0) :p (wheel-at 0)})

(defn index
  "The row at the band."
  [{:keys [opts loop]} {:keys [offset target]}]
  (let [n (count opts) i (Math/round (double (or target offset)))]
    (if loop (mod i n) (max 0 (min (dec n) i)))))

(defn minutes [ws]
  (let [[h m p] (map (fn [spec] (get (:opts spec) (index spec (ws (:key spec))))) wheels)]
    (+ (* 60 (+ (mod (parse-long h) 12) (if (= p "PM") 12 0))) (parse-long m))))

(defn at-rest? [ws] (every? (fn [{:keys [offset target vel drag]}]
                              (and (nil? target) (nil? drag) (zero? vel)
                                   (== offset (Math/round offset))))
                            (vals ws)))

(defn- bounded
  "A non-looping wheel's offset kept to its rows, with a little give past the
  ends while dragged."
  [{:keys [opts loop]} o give]
  (if loop o (max (- give) (min (+ (dec (count opts)) give) o))))

(defn snap-to [spec o]
  (double (bounded spec (Math/round (double o)) 0)))

(defn tick
  "One frame of a wheel after dt seconds; nil once at rest."
  [spec {:keys [offset vel target quiet drag] :as w} dt]
  (cond
    drag nil
    target (let [k (- 1.0 (Math/exp (* -9.0 dt)))
                 o (+ offset (* k (- target offset)))]
             (if (< (Math/abs (- target o)) 0.002)
               (assoc w :offset target :target nil :vel 0.0)
               (assoc w :offset o)))
    (> (Math/abs vel) 0.6)
    (let [o (+ offset (* vel dt))
          b (bounded spec o 0.0)]
      (if (not= o b)
        (assoc w :offset b :vel 0.0 :target (snap-to spec b))
        (assoc w :offset o :vel (* vel (Math/exp (* -2.6 dt))))))
    (not (zero? vel)) (assoc w :vel 0.0 :target (snap-to spec (+ offset (* vel 0.15))))
    (not= offset (snap-to spec offset))
    (if (< quiet 0.12)
      (assoc w :quiet (+ quiet dt))
      (assoc w :target (snap-to spec offset)))
    :else nil))

(defn row-under
  "Which row offset a point on the wheel shows: the drum's curve undone."
  [offset y]
  (let [s (max -0.99 (min 0.99 (/ (- y mid) radius)))]
    (+ offset (/ (Math/asin s) step-rad))))

(defn on-input
  "A wheel after a pointer or scroll event; `now` in seconds."
  [spec w kind e now]
  (case kind
    :press (let [^MouseEvent e e]
             (assoc w :drag {:y0 (.getY e) :o0 (:offset w) :y (.getY e) :t now :v 0.0}
                    :vel 0.0 :target nil))
    :drag (if-let [{:keys [y0 o0 y t v] :as d} (:drag w)]
            (let [^MouseEvent e e
                  y' (.getY e) dt (max 1e-3 (- now t))
                  v' (+ (* 0.7 (/ (- (- y' y)) row-h dt)) (* 0.3 v))]
              (assoc w :offset (bounded spec (- o0 (/ (- y' y0) row-h)) 0.4)
                     :drag (assoc d :y y' :t now :v v')))
            w)
    :release (if-let [{:keys [y0 t v]} (:drag w)]
               (let [^MouseEvent e e
                     moved (Math/abs (- (.getY e) y0))
                     w (assoc w :drag nil)]
                 (cond
                   (< moved 4) (assoc w :target (snap-to spec (row-under (:offset w) (.getY e))))
                   (> (- now t) 0.08) (assoc w :target (snap-to spec (:offset w)))
                   :else (assoc w :vel (max -40.0 (min 40.0 v)))))
               w)
    :scroll (let [^ScrollEvent e e]
              (assoc w :offset (bounded spec (- (:offset w) (/ (.getDeltaY e) row-h)) 0.3)
                     :vel 0.0 :target nil :quiet 0.0))))

;;; The view

(defn- rows [spec {:keys [offset]}]
  (let [n (count (:opts spec)) c (Math/round offset) w (:width spec)]
    (for [k (range (- c 4) (+ c 5))
          :let [d (- k offset) a (* d step-rad)]
          :when (< (Math/abs a) (/ Math/PI 2))
          :when (or (:loop spec) (< -1 k n))
          :let [cos (Math/cos a)
                on (< (Math/abs d) 0.5)]]
      {:fx/type :label
       :text (get (:opts spec) (mod k n))
       :mouse-transparent true
       :style-class ["label" "wheel-row" (if on "on" "off")]
       :alignment :center
       :min-width w :pref-width w :pref-height row-h
       :layout-x 0 :layout-y (- (+ mid (* radius (Math/sin a))) (/ row-h 2))
       :scale-y cos
       :opacity (* (Math/pow cos 1.6) (if on 1.0 0.62))})))

(defn wheel-picker-view
  "The wheels. `on` is the event map their inputs are sent with: the page adds
  :wheel, :input and the JavaFX event."
  [{:keys [wheels-state on id]}]
  {:fx/type :v-box
   :id id
   :spacing 12
   :alignment :top-center
   :children
   [{:fx/type :stack-pane
     :style-class ["wheels"]
     :max-width (+ 24 (reduce + (map :width wheels)))
     :children
     [{:fx/type :region :style-class ["wheel-band"]
       :max-height row-h :pref-height row-h :mouse-transparent true}
      {:fx/type :h-box
       :alignment :center
       :children
       (vec (for [{:keys [key width] :as spec} wheels]
              (let [on (assoc on :wheel key)]
                {:fx/type :pane
                 :id (str id "-" (name key))
                 :min-width width :pref-width width :max-width width
                 :min-height wheel-h :pref-height wheel-h :max-height wheel-h
                 :style-class ["wheel"]
                 :on-mouse-pressed (assoc on :input :press)
                 :on-mouse-dragged (assoc on :input :drag)
                 :on-mouse-released (assoc on :input :release)
                 :on-scroll (assoc on :input :scroll)
                 :children (vec (rows spec (wheels-state key)))})))}]}
    {:fx/type :label :style-class ["label" "note"] :wrap-text true :max-width 260
     :text "Drag and let go to spin, scroll, or click a row."}]})
