(ns demo.time-picker-page
  "The time picker demo's page: three time pickers from demo.time-picker. This
  half is the demo's own - its state, its events and what its pickers set -
  and is not for copying.

      clojure -M:time-picker"
  (:require [cljfx.api :as fx]
            [clojure.java.io :as io]
            [demo.time-picker :as tp :refer [time-picker-view]]
            [demo.ui :as ui :refer [button-view]])
  (:import [javafx.application Platform]
           [javafx.scene.input KeyCode KeyEvent]))

;; A time is minutes after midnight, or nil where none is set.
;; :undo holds [picker time-before], the newest last.
;; :now stands in for the clock, and :drop pushes the page down: for the checks.
(def start-state
  {:times {:starts 570 :ends nil :reminder 540}
   :remind false :writes 0 :undo [] :h24 false :now nil :drop 0
   :solid false :contrast false})

(defonce *state (atom start-state))

(defn write
  "A time is kept: one step for Undo."
  [state id value]
  (-> state
      (update :undo conj [id (get-in state [:times id])])
      (assoc-in [:times id] value)
      (update :writes inc)))

(defn undo
  "Takes back the last step."
  [state]
  (if-let [[id value] (peek (:undo state))]
    (-> state
        (assoc-in [:times id] value)
        (update :undo pop))
    state))

(declare handle)

(def notes
  ["Type a time: 9a, 930a, 9:30 pm, 2130, noon, midnight."
   "An hour alone, as 3, is not guessed at: the field asks AM or PM."
   "The list narrows as you type. Down and Up move its mark, Return takes it."
   "Escape closes the list; a second Escape puts the old time back."
   "Ends may be left empty."
   "Command-Z takes back the last change."])

(defn page
  "The content: under the glass, and it scrolls."
  [{:keys [times remind writes h24 now drop]}]
  (let [picker (fn [id name more]
                 (merge {:fx/type time-picker-view :dispatch handle
                         :id (clojure.core/name id) :name name
                         :value (get times id) :h24 h24 :now now
                         :write {:event :write :id id}}
                        more))]
    {:fx/type :scroll-pane
     :id "page"
     :fit-to-width true
     :focus-traversable false
     :hbar-policy :never
     :content
     {:fx/type :v-box
      :spacing 14
      :padding {:top (+ 84 drop) :bottom 24 :left 24 :right 24}
      :children
      (into
        [(picker :starts "Starts" {})
         (picker :ends "Ends" {:optional true})
         {:fx/type :check-box
          :id "remind"
          :text "Remind me"
          :selected remind
          :on-selected-changed {:event :remind}}
         (picker :reminder "Reminder" {:disabled (not remind)
                                       :tip "Off: tick Remind me to set a time."})
         {:fx/type :label
          :id "writes"
          :text (str "Written " writes (if (= 1 writes) " time" " times"))}]
        (for [note notes]
          {:fx/type :label :style-class ["label" "note"] :wrap-text true :text note}))}}))

(defn toolbar
  "The layer of glass: it floats above the page."
  [{:keys [undo]}]
  {:fx/type button-view :dispatch handle
   :id "undo" :text "Undo" :glass :regular
   :disabled (empty? undo)
   :tip (if (empty? undo) "Nothing to undo yet." "Take back the last change")
   :click {:event :undo}})

(defn root [{:keys [solid contrast] :as state}]
  {:fx/type :stage
   :showing true
   :title "Time picker"
   :width 560
   :height 560
   :scene
   {:fx/type :scene
    :stylesheets [(str (io/resource "demo/glass.css"))]
    :root
    {:fx/type :stack-pane
     :style-class (cond-> ["root" "page"] solid (conj "solid") contrast (conj "contrast"))
     :on-key-pressed {:event :key}
     :children [(assoc state :fx/type page)
                (assoc state :fx/type toolbar
                       :stack-pane/alignment :top-center
                       :stack-pane/margin {:top 16})]}}})

(defn handle [event]
  (case (:event event)
    :write (swap! *state write (:id event) (:value event))
    :undo (swap! *state undo)
    :remind (swap! *state assoc :remind (boolean (:fx/event event)))
    :key (let [^KeyEvent e (:fx/event event)]
           (when (and (.isShortcutDown e) (= KeyCode/Z (.getCode e)))
             (.consume e)
             (swap! *state undo)))))

(def renderer
  (fx/create-renderer
    :middleware (fx/wrap-map-desc #'root)
    :opts {:fx.opt/map-event-handler handle}))

(defn -main [& _]
  (Platform/setImplicitExit true)
  (Platform/runLater (fn [] (ui/follow-system! #(swap! *state assoc :solid %))))
  (future (swap! *state assoc :contrast (ui/increase-contrast?)))
  (future (swap! *state assoc :h24 (tp/clock-24?)))
  (fx/mount-renderer *state renderer))
