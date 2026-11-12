(ns demo.button
  "The demo's page: a toolbar of glass over a count, built from demo.ui. This
  half is the demo's own - its state, its events and what its buttons do - and
  is not for copying.

      clojure -M:run         the Liquid Glass look
      clojure -M:run flat    the flat look"
  (:require [cljfx.api :as fx]
            [clojure.java.io :as io]
            [demo.ui :as ui :refer [button-view glass-group]])
  (:import [javafx.application Platform]))

(def save-ms 1500)
(def saved-ms 1000)

(defn save-look
  "What the Save button says and does in each state of a save."
  [save]
  (case save
    :idle {:text "Save" :busy false :inert false}
    :saving {:text "Saving…" :busy true :inert true}
    :saved {:text "Saved" :busy false :inert true :mark :check}
    :failed {:text "Retry" :busy false :inert false :failed true
             :tip "The save failed. Click to try again."}))

;; :look is the stylesheet: "glass", or "button" for the flat look.
;; :save is :idle, :saving, :saved or :failed.
(defonce *state (atom {:count 0 :save :idle :saves 0 :fail-next false :confirm false
                       :look "glass" :solid false :contrast false}))

(declare handle)

(defn toolbar
  "The layer of glass: it floats above the page, and only it is glass."
  [{:keys [count save confirm]}]
  {:fx/type :h-box
   :alignment :center
   :spacing 12
   :max-height :use-pref-size
   :pick-on-bounds false
   :children
   [{:fx/type glass-group
     :children [(merge {:fx/type button-view :dispatch handle
                        :id "save"
                        :busy false
                        :click {:event :save}}
                       (save-look save))
                {:fx/type button-view :dispatch handle
                 :id "subtract" :name "Subtract 1" :icon :minus
                 :disabled (zero? count)
                 :tip (if (zero? count)
                        "Nothing to subtract: the count is 0."
                        "Subtract 1")
                 :click {:event :add :n -1}}
                {:fx/type button-view :dispatch handle
                 :id "delete" :text "Delete…" :destructive true
                 :disabled confirm
                 :tip (if confirm "Answer the question below first." "Delete the count and its saves")
                 :click {:event :ask-delete}}]}
    {:fx/type button-view :dispatch handle
     :id "add" :text "Add 1" :icon :plus :primary true :glass :tinted
     ;; While a delete is being asked, Return presses nothing.
     :default (not confirm)
     :click {:event :add :n 1}
     :hold {:event :add :n 10}
     :hold-text "Add 10"
     :tip "Click or Return: add 1. Hold: add 10."}]})

(defn page
  "The content: under the glass, and never glass itself. Its buttons are plain."
  [{:keys [count save saves fail-next confirm]}]
  {:fx/type :v-box
   :alignment :center
   :spacing 14
   :padding {:top 76}
   :children
   [{:fx/type :label :style-class ["label" "count"] :text (str count)}
    {:fx/type :label
     :text (str "Saved " saves (if (= 1 saves) " time" " times")
                (when (= :failed save) " - the last save failed"))}
    {:fx/type :check-box
     :text "Make the next save fail"
     :selected fail-next
     :on-selected-changed {:event :fail-next}}
    ;; Always in its place, so asking moves nothing.
    {:fx/type :h-box
     :alignment :center
     :spacing 14
     :visible confirm
     :children [{:fx/type :label :text "Delete the count and its saves?"}
                ;; A pair: both as wide as the wider one. Return presses neither.
                {:fx/type :tile-pane
                 :pref-columns 2
                 :hgap 10
                 :max-width :use-pref-size
                 :children [{:fx/type button-view :dispatch handle
                             :id "cancel" :text "Cancel" :fill true
                             :click {:event :cancel-delete}}
                            {:fx/type button-view :dispatch handle
                             :id "confirm" :text "Delete" :destructive true :fill true
                             :click {:event :delete}}]}]}]})

(defn root [{:keys [look solid contrast] :as state}]
  {:fx/type :stage
   :showing true
   :title "Button"
   :width 560
   :height 380
   :on-focused-changed {:event :focused}
   :scene
   {:fx/type :scene
    :stylesheets [(str (io/resource (str "demo/" look ".css")))]
    :root
    {:fx/type :stack-pane
     ;; Reduce Transparency and Increase Contrast restyle the glass.
     :style-class (cond-> ["root" "page"] solid (conj "solid") contrast (conj "contrast"))
     :children [(assoc state :fx/type page)
                (assoc state :fx/type toolbar
                       :stack-pane/alignment :top-center
                       :stack-pane/margin {:top 16})]}}})

(defn- finish-save!
  "The end of a save: Saved for a moment, or failed until it is tried again."
  []
  (let [[before _] (swap-vals! *state #(if (:fail-next %)
                                         (assoc % :save :failed :fail-next false)
                                         (-> % (assoc :save :saved) (update :saves inc))))]
    (when-not (:fail-next before)
      (Thread/sleep (long saved-ms))
      (swap! *state #(cond-> % (= :saved (:save %)) (assoc :save :idle))))))

(defn- read-contrast!
  "Increase Contrast cannot be watched, so it is read again whenever the window
  comes to the front."
  []
  (when @ui/*follow-system
    (future (swap! *state assoc :contrast (ui/increase-contrast?)))))

(defn handle [event]
  (case (:event event)
    :add (swap! *state update :count #(max 0 (+ % (:n event))))
    ;; Busy: a save still running, or just done, swallows the next click.
    :save (let [[before _] (swap-vals! *state #(cond-> % (#{:idle :failed} (:save %)) (assoc :save :saving)))]
            (when (#{:idle :failed} (:save before))
              (future
                (Thread/sleep (long save-ms))
                (finish-save!))))
    :fail-next (swap! *state assoc :fail-next (boolean (:fx/event event)))
    :ask-delete (swap! *state assoc :confirm true)
    :cancel-delete (swap! *state assoc :confirm false)
    :delete (swap! *state assoc :count 0 :saves 0 :confirm false)
    :focused (when (:fx/event event) (read-contrast!))))

(def renderer
  (fx/create-renderer
    :middleware (fx/wrap-map-desc #'root)
    :opts {:fx.opt/map-event-handler handle}))

(defn -main
  "`clojure -M:run` opens the Liquid Glass look, `clojure -M:run flat` the flat one."
  [& [look]]
  (Platform/setImplicitExit true)
  (swap! *state assoc :look (if (= "flat" look) "button" "glass"))
  (Platform/runLater (fn [] (ui/follow-system! #(swap! *state assoc :solid %))))
  (read-contrast!)
  (fx/mount-renderer *state renderer))
