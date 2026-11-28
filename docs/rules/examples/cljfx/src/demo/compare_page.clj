(ns demo.compare-page
  "Two time picker experiments side by side: the clock dial (demo.clock-dial)
  and iOS-style wheels (demo.wheel-picker). Each writes its own time.

      clojure -M:compare"
  (:require [cljfx.api :as fx]
            [clojure.java.io :as io]
            [demo.clock-dial :refer [clock-dial-view]]
            [demo.clock-dial-page :as dial-page]
            [demo.ui :as ui]
            [demo.wheel-picker :as wp :refer [wheel-picker-view]])
  (:import [javafx.application Platform]))

(def start-state
  {:dial dial-page/start-state
   :wheels wp/start :wheel-time nil :wheel-writes 0
   :solid false})

(defonce *state (atom start-state))

(defn- now [] (/ (System/nanoTime) 1e9))

(defn advance-wheels
  "The wheels one frame later; a time is written when all come to rest on a
  new one."
  [{:keys [wheels wheel-time] :as s} dt]
  (let [ws (reduce (fn [ws {:keys [key] :as spec}]
                     (if-let [w (wp/tick spec (ws key) dt)] (assoc ws key w) ws))
                   wheels wp/wheels)
        t (when (wp/at-rest? ws) (wp/minutes ws))]
    (cond-> (assoc s :wheels ws)
      (and t (not= t wheel-time)) (-> (assoc :wheel-time t) (update :wheel-writes inc)))))

(defn advance [s dt]
  (let [s' (-> s (update :dial dial-page/advance dt) (advance-wheels dt))]
    (if (= s' s) s s')))

(defn- written [id t n]
  {:fx/type :label :id id
   :text (str "Written: " (dial-page/show-time t) "  (" n (if (= 1 n) " time)" " times)"))})

(defn- column [title & children]
  {:fx/type :v-box
   :spacing 16
   :alignment :top-center
   :min-width 320 :pref-width 320
   :children (into [{:fx/type :label :style-class ["label" "compare-title"] :text title}]
                   children)})

(defn root [{:keys [dial wheels wheel-time wheel-writes solid]}]
  {:fx/type :stage
   :showing true
   :title "Time pickers, side by side"
   :width 760
   :height 620
   :scene
   {:fx/type :scene
    :stylesheets (mapv #(str (io/resource %))
                       ["demo/glass.css" "demo/clock_dial.css" "demo/wheel_picker.css"])
    :root
    {:fx/type :h-box
     :style-class (cond-> ["root" "page"] solid (conj "solid"))
     :alignment :top-center
     :spacing 40
     :padding 32
     :children
     [(column "Clock dial"
              {:fx/type clock-dial-view :id "dial" :dial (:dial dial) :anim (:anim dial)
               :on {:event :dial}}
              (written "dial-written" (:time dial) (:writes dial)))
      {:fx/type :separator :orientation :vertical}
      (column "Wheels"
              {:fx/type :region :min-height 56 :pref-height 56}
              {:fx/type wheel-picker-view :id "wheels" :wheels-state wheels
               :on {:event :wheel}}
              (written "wheels-written" wheel-time wheel-writes))]}}})

(defn handle [{:keys [event] :as e}]
  (case event
    :dial (swap! *state update :dial dial-page/on-input e)
    :wheel (let [{:keys [wheel input]} e
                 spec (first (filter #(= wheel (:key %)) wp/wheels))
                 t (now)]
             (swap! *state update-in [:wheels wheel]
                    #(wp/on-input spec % input (:fx/event e) t)))))

(def renderer
  (fx/create-renderer
    :middleware (fx/wrap-map-desc #'root)
    :opts {:fx.opt/map-event-handler handle}))

(defn -main [& _]
  (Platform/setImplicitExit true)
  (Platform/runLater (fn [] (ui/follow-system! #(swap! *state assoc :solid %))))
  (fx/mount-renderer *state renderer)
  (Platform/runLater #(dial-page/start-motion! (fn [dt] (swap! *state advance dt)))))
