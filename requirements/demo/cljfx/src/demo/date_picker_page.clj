(ns demo.date-picker-page
  "The date picker demo's page: three date pickers from demo.date-picker. This
  half is the demo's own - its state, its events and what its pickers set -
  and is not for copying.

      clojure -M:date-picker"
  (:require [cljfx.api :as fx]
            [clojure.java.io :as io]
            [demo.date-picker :as dp :refer [date-picker-view]]
            [demo.ui :as ui :refer [button-view]])
  (:import [java.time LocalDate]
           [javafx.application Platform]
           [javafx.scene.input KeyCode KeyEvent]))

;; A date is a LocalDate, or nil where none is set.
;; :undo holds [picker date-before], the newest last.
;; :today stands in for the clock, :locale and :first-day for the region, and
;; :drop pushes the page down: for the checks.
(def start-state
  {:dates {:starts (LocalDate/of 2026 11 20) :ends nil :reminder (LocalDate/of 2026 11 18)}
   :remind false :writes 0 :undo [] :today nil :locale nil :first-day nil :drop 0
   :solid false :contrast false})

(defonce *state (atom start-state))

(defn write
  "A date is kept: one step for Undo."
  [state id value]
  (-> state
      (update :undo conj [id (get-in state [:dates id])])
      (assoc-in [:dates id] value)
      (update :writes inc)))

(defn undo
  "Takes back the last step."
  [state]
  (if-let [[id value] (peek (:undo state))]
    (-> state
        (assoc-in [:dates id] value)
        (update :undo pop))
    state))

(declare handle)

(def notes
  ["Type a date: 20 nov, nov 20, 2026-11-20, or the region's 20/11/2026."
   "A day with no year is the next such day."
   "Click the field or press Down for the calendar. Arrows move a day or a week, Page Up and Page Down a month."
   "Escape closes the calendar; a second Escape puts the old date back."
   "Ends may be left empty."
   "Command-Z takes back the last change."])

(defn page
  "The content: under the glass, and it scrolls."
  [{:keys [dates remind writes today locale first-day drop]}]
  (let [picker (fn [id name more]
                 (merge {:fx/type date-picker-view :dispatch handle
                         :id (clojure.core/name id) :name name
                         :value (get dates id) :today today
                         :locale locale :first-day first-day
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
                                       :tip "Off: tick Remind me to set a date."})
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
   :title "Date picker"
   :width 560
   :height 640
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
  (future (swap! *state assoc :first-day (dp/first-weekday)))
  (fx/mount-renderer *state renderer))
