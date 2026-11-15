(ns demo.clock-dial-page
  "The clock dial experiment's page: one dial from demo.clock-dial, and the
  time it wrote.

      clojure -M:clock-dial"
  (:require [cljfx.api :as fx]
            [clojure.java.io :as io]
            [demo.clock-dial :as cd :refer [clock-dial-view]]
            [demo.ui :as ui])
  (:import [javafx.animation AnimationTimer]
           [javafx.application Platform]))

(def start-state
  {:dial (cd/from-minutes nil) :time nil :writes 0 :solid false
   :anim (cd/still (cd/from-minutes nil))})

(defonce *state (atom start-state))

(defn show-time [m]
  (if (nil? m)
    "No time yet"
    (let [h (quot m 60) h12 (mod h 12)]
      (format "%d:%02d %s" (if (zero? h12) 12 h12) (rem m 60) (if (< h 12) "AM" "PM")))))

(defn step
  "The page after one dial action: a full pick at AM/PM writes the time."
  [state action]
  (let [before (:dial state)
        dial (cd/act before action)
        [op arg] action
        picked (case op :pick arg :pick-cursor (:cursor before) nil)
        done (and picked (= 2 (:step before)))]
    (cond-> (assoc state :dial dial
                   :anim (if @ui/*reduce
                           (cd/still dial)
                           (cd/begin (:anim state) before dial picked)))
      done (-> (assoc :time (cd/minutes dial)) (update :writes inc)))))

(defn moving?
  "True while a pick plays out: the dial takes no input until it rests."
  [state]
  (not= :idle (get-in state [:anim :phase])))

(defn advance
  "The state one frame later: the same map while at rest, so nothing redraws."
  [{:keys [dial anim] :as s} dt]
  (if-let [a (cd/tick anim dial dt)] (assoc s :anim a) s))

(defn on-input
  "The state after one input event from the dial."
  [state {:keys [input] :as event}]
  (let [action (case input
                 :goto [:goto (:step event)]
                 :back [:back]
                 :clear [:clear]
                 (cd/input (:dial state) input (:fx/event event)))]
    (if (and action (not (moving? state)))
      (step state action)
      state)))

(defn start-motion!
  "Calls (f dt) on every frame, dt in seconds."
  [f]
  (let [last (atom 0)]
    (.start (proxy [AnimationTimer] []
              (handle [now]
                (let [dt (if (zero? @last) 0.0 (/ (- now @last) 1e9))]
                  (reset! last now)
                  (f (min dt 0.05))))))))

(defn root [{:keys [dial time writes solid anim]}]
  {:fx/type :stage
   :showing true
   :title "Clock dial"
   :width 400
   :height 600
   :scene
   {:fx/type :scene
    :stylesheets [(str (io/resource "demo/glass.css")) (str (io/resource "demo/clock_dial.css"))]
    :root
    {:fx/type :v-box
     :style-class (cond-> ["root" "page"] solid (conj "solid"))
     :alignment :top-center
     :spacing 16
     :padding 32
     :children
     [{:fx/type clock-dial-view :id "dial" :dial dial :anim anim :on {:event :dial}}
      {:fx/type :label :id "written"
       :text (str "Written: " (show-time time) "  (" writes (if (= 1 writes) " time)" " times)"))}]}}})

(defn handle [event]
  (swap! *state on-input event))

(def renderer
  (fx/create-renderer
    :middleware (fx/wrap-map-desc #'root)
    :opts {:fx.opt/map-event-handler handle}))

(defn -main [& _]
  (Platform/setImplicitExit true)
  (Platform/runLater (fn [] (ui/follow-system! #(swap! *state assoc :solid %))))
  (fx/mount-renderer *state renderer)
  (Platform/runLater #(start-motion! (fn [dt] (swap! *state advance dt)))))
