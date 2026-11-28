(ns demo.clock-dial
  "An experiment: a time picker on a round clock dial, in three taps - the
  hour, then the minute (any, 00 to 59), then AM or PM. Not part of
  requirements/components.org, which rules out a clock face for the time
  picker; this tries the idea out beside it.

  What to take:

      clock-dial-view   the dial: its field, its face and its buttons
      act, input        the rules, as plain data, tested without a window

  A dial's state is a map: {:step 0..2 :cursor i :vals [hour minute half]}.
  Its time is whole minutes after midnight once all three are picked.

  The look is in demo/clock_dial.css."
  (:import [javafx.scene.input KeyCode KeyEvent MouseEvent]))

;;; Rules: plain data

(def size 260.0)
(def mid (/ size 2))
(def face-r 125.0)
(def ring-r 95.0)

(def steps
  [{:label "STEP 1 - HOUR" :opts (mapv str (cons 12 (range 1 12)))}
   {:label "STEP 2 - MINUTE" :opts (mapv #(format "%02d" %) (range 60))}
   {:label "STEP 3 - AM / PM" :opts ["AM" "PM"]}])

(defn opts [step] (:opts (steps step)))

(def blank {:step 0 :cursor 9 :vals [nil nil nil]})

(defn place
  "Where option i of n sits on a ring of radius r: 0 at the top, clockwise."
  [i n r]
  (let [a (* 2 Math/PI (/ i n))]
    [(+ mid (* r (Math/sin a))) (- mid (* r (Math/cos a)))]))

(defn place-deg
  "Where a point at `deg` degrees sits on a ring of radius r: 0 at the top."
  [deg r]
  (let [a (Math/toRadians deg)]
    [(+ mid (* r (Math/sin a))) (- mid (* r (Math/cos a)))]))

(defn target-deg
  "The angle the hand points to for the dial's cursor."
  [{:keys [step cursor]}]
  (* 360.0 (/ cursor (count (opts step)))))

;; Motion, slow on purpose. A pick plays in order: the hand sweeps to it, rests,
;; the step fades out, and the next step fades in.
(def sweep-rate 6.0)   ; per second; higher is faster
(def hold-s 0.25)
(def out-s 0.30)
(def in-s 0.45)

(defn smooth [t] (let [t (max 0.0 (min 1.0 t))] (* t t (- 3.0 (* 2.0 t)))))

(defn still
  "Motion at rest on a dial."
  [dial]
  {:phase :idle :shown dial :angle (target-deg dial) :fade 1.0 :t 0.0})

(defn begin
  "Motion for a change from dial `before` to `after`: a pick that moves to the
  next step sweeps first; another change of step only fades."
  [anim before after picked]
  (cond
    (= (:step before) (:step after)) (assoc anim :shown after)
    picked (assoc anim :phase :sweep :shown (assoc before :cursor picked) :t 0.0)
    :else (assoc anim :phase :out :shown before :t 0.0)))

(defn- toward [angle target k]
  (let [goal (+ target (* 360.0 (Math/round (/ (- angle target) 360.0))))
        a (+ angle (* k (- goal angle)))]
    (if (< (Math/abs (- goal a)) 0.3) [(mod goal 360.0) true] [a false])))

(defn tick
  "One frame of motion after `dt` seconds toward `dial`; nil once at rest."
  [{:keys [phase shown angle fade t] :as anim} dial dt]
  (let [k (- 1.0 (Math/exp (- (* sweep-rate dt))))
        t (+ t dt)]
    (case phase
      :idle (let [[a done] (toward angle (target-deg dial) k)]
              (when-not (and done (= angle a) (= shown dial))
                (assoc anim :angle a :shown dial)))
      :sweep (let [[a done] (toward angle (target-deg shown) k)]
               (if done (assoc anim :angle a :phase :hold :t 0.0) (assoc anim :angle a)))
      :hold (if (>= t hold-s) (assoc anim :phase :out :t 0.0) (assoc anim :t t))
      :out (if (>= t out-s)
             (assoc anim :phase :in :t 0.0 :fade 0.0 :shown dial :angle (target-deg dial))
             (assoc anim :t t :fade (- 1.0 (/ t out-s))))
      :in (if (>= t in-s)
            (assoc anim :phase :idle :t 0.0 :fade 1.0)
            (assoc anim :t t :fade (/ t in-s))))))

(defn index-at
  "The option under a point of the dial, by its angle from the centre."
  [step x y]
  (let [dx (- x mid) dy (- y mid)]
    (if (= step 2)
      (if (neg? dy) 0 1)
      (let [n (count (opts step))
            a (Math/atan2 dx (- dy))
            a (if (neg? a) (+ a (* 2 Math/PI)) a)]
        (mod (Math/round (* n (/ a (* 2 Math/PI)))) n)))))

(defn minutes
  "The time picked, or nil until all three are."
  [{:keys [vals]}]
  (let [[h m half] vals]
    (when (and h m half)
      (+ (* 60 (+ (mod (parse-long h) 12) (if (= half "PM") 12 0)))
         (parse-long m)))))

(defn cursor-for [{:keys [vals]} step]
  (if-let [v (get vals step)]
    (.indexOf ^java.util.List (opts step) v)
    (if (zero? step) 9 0)))

(defn go [dial step]
  (assoc dial :step step :cursor (cursor-for dial step)))

(defn from-minutes
  "A dial showing a time."
  [m]
  (if (nil? m)
    blank
    (let [h (quot m 60) mm (rem m 60) h12 (mod h 12)
          minute (some #{(format "%02d" mm)} (opts 1))]
      (go (assoc blank :vals [(str (if (zero? h12) 12 h12)) minute (if (< h 12) "AM" "PM")])
          0))))

(defn pick [{:keys [step] :as dial} i]
  (let [dial (assoc-in dial [:vals step] (get (opts step) i))]
    (if (< step 2) (go dial (inc step)) (assoc dial :cursor i))))

(defn act
  "The dial after one action."
  [{:keys [step cursor] :as dial} [op arg]]
  (let [n (count (opts step))]
    (case op
      :aim (assoc dial :cursor arg)
      :pick (pick dial arg)
      :pick-cursor (pick dial cursor)
      :next (assoc dial :cursor (mod (inc cursor) n))
      :prev (assoc dial :cursor (mod (dec cursor) n))
      :back (if (pos? step) (go dial (dec step)) dial)
      :goto (go dial arg)
      :clear blank
      dial)))

(defn input
  "The action a pointer or key event on the face asks for, or nil."
  [{:keys [step]} kind e]
  (case kind
    :press (when (< step 2)
             (let [^MouseEvent e e] [:aim (index-at step (.getX e) (.getY e))]))
    :drag (when (< step 2)
            (let [^MouseEvent e e] [:aim (index-at step (.getX e) (.getY e))]))
    :release (let [^MouseEvent e e] [:pick (index-at step (.getX e) (.getY e))])
    :key (let [^KeyEvent e e]
           (condp = (.getCode e)
             KeyCode/RIGHT [:next] KeyCode/DOWN [:next]
             KeyCode/LEFT [:prev] KeyCode/UP [:prev]
             KeyCode/ENTER [:pick-cursor] KeyCode/SPACE [:pick-cursor]
             KeyCode/ESCAPE [:back]
             nil))))

;;; The view

(defn- mark
  "A word centred on a point; the face takes the pointer, not the word."
  [[x y] text classes]
  {:fx/type :label :text text :mouse-transparent true
   :style-class (into ["label" "dial-num"] classes)
   :alignment :center :min-width 48 :pref-width 48 :pref-height 30
   :layout-x (- x 24) :layout-y (- y 15)})

(defn- ring-face [{:keys [step cursor vals]} angle]
  (let [os (opts step) n (count os)
        [hx hy :as hand] (place-deg angle ring-r)]
    (concat
      [{:fx/type :circle :center-x mid :center-y mid :radius face-r :style-class ["dial-face"]}
       {:fx/type :line :start-x mid :start-y mid :end-x hx :end-y hy
        :mouse-transparent true :style-class ["dial-hand"]}
       {:fx/type :circle :center-x mid :center-y mid :radius 5
        :mouse-transparent true :style-class ["dial-knob"]}
       {:fx/type :circle :center-x hx :center-y hy :radius (if (= step 1) 24 20)
        :mouse-transparent true :style-class ["dial-knob"]}]
      (when (= step 1)
        [(mark [mid (- mid 30)] (str (vals 0) " : --") ["dial-hint"])])
      ;; Sixty minutes: a tick for each, a number every five.
      (when (= n 60)
        (for [i (range 60) :when (pos? (mod i 5))
              :let [[x1 y1] (place i n 120.0) [x2 y2] (place i n 114.0)]]
          {:fx/type :line :start-x x1 :start-y y1 :end-x x2 :end-y y2
           :mouse-transparent true :style-class ["dial-tick"]}))
      (keep-indexed (fn [i o]
                      (when (or (< n 60) (zero? (mod i 5)))
                        (mark (place i n ring-r) o (if (= i cursor) ["sel"] []))))
                    os)
      [(mark hand (get os cursor) ["sel"])])))

(defn- half-face [{:keys [cursor vals]}]
  (let [half (fn [i start]
               {:fx/type :arc :center-x mid :center-y mid :radius-x face-r :radius-y face-r
                :start-angle start :length 180 :type :round
                :style-class ["dial-half" (if (= i cursor) "on" "off")]})]
    [(half 0 0) (half 1 180)
     (mark [mid (- mid 55)] "AM" (if (zero? cursor) ["big" "sel"] ["big"]))
     (mark [mid (+ mid 55)] "PM" (if (= 1 cursor) ["big" "sel"] ["big"]))
     {:fx/type :rectangle :x (- mid 44) :y (- mid 15) :width 88 :height 30
      :arc-width 30 :arc-height 30 :mouse-transparent true :style-class ["dial-pill"]}
     (mark [mid mid] (str (vals 0) " : " (vals 1)) ["dial-pill-text"])]))

(defn clock-dial-view
  "One dial. `on` is the event map its inputs are sent with: the page adds
  :input and the JavaFX event, as :fx/event."
  [{:keys [dial on id anim]}]
  (let [dial (or (:shown anim) dial)
        {:keys [step vals]} dial
        {:keys [angle fade] :or {fade 1.0}} anim
        angle (or angle (target-deg dial))
        fade (smooth fade)
        part (fn [i]
               {:fx/type :button :id (str id "-part-" i)
                :text (or (get vals i) "--")
                :style-class (cond-> ["button" "dial-part"]
                               (some? (get vals i)) (conj "set")
                               (= i step) (conj "active"))
                :on-action (assoc on :input :goto :step i)})]
    {:fx/type :v-box
     :id id
     :spacing 12
     :alignment :top-center
     :max-width size
     :children
     [{:fx/type :h-box :style-class ["dial-field"] :alignment :center-left :spacing 2
       :children [(part 0) {:fx/type :label :text ":"} (part 1) (part 2)]}
      {:fx/type :label :style-class ["label" "dial-step"] :text (:label (steps step))}
      {:fx/type :pane
       :id (str id "-face")
       :focus-traversable true
       :style-class ["dial"]
       :min-width size :pref-width size :max-width size
       :min-height size :pref-height size :max-height size
       :on-mouse-pressed (assoc on :input :press)
       :on-mouse-dragged (assoc on :input :drag)
       :on-mouse-released (assoc on :input :release)
       :on-key-pressed (assoc on :input :key)
       :opacity fade
       :scale-x (+ 0.9 (* 0.1 fade))
       :scale-y (+ 0.9 (* 0.1 fade))
       :children (vec (if (= step 2) (half-face dial) (ring-face dial angle)))}
      {:fx/type :h-box :spacing 10 :alignment :center
       :children [{:fx/type :button :text "← Back" :disable (zero? step)
                   :on-action (assoc on :input :back)}
                  {:fx/type :button :text "Clear" :on-action (assoc on :input :clear)}]}
      {:fx/type :label :style-class ["label" "note"] :wrap-text true
       :text "Tap or drag the hand. Arrows turn it, Return picks, Escape goes back."}]}))
