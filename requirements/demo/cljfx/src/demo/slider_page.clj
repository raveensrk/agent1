(ns demo.slider-page
  "The slider demo's page: two sliders from demo.slider over a square that one
  of them lights. This half is the demo's own - its state, its events and what
  its sliders set - and is not for copying.

      clojure -M:slider"
  (:require [cljfx.api :as fx]
            [clojure.java.io :as io]
            [demo.slider :refer [slider-view]]
            [demo.ui :as ui :refer [button-view]])
  (:import [javafx.application Platform]
           [javafx.scene.input KeyCode KeyEvent]))

;; :value is what was written, :live what the slider sets as it moves.
;; :undo holds [slider value-before], the newest last.
(def start-state
  {:sliders {:brightness {:value 20.0 :live 20.0}
             :volume {:value 30.0 :live 30.0}}
   :muted true :writes 0 :undo [] :pad 24 :solid false :contrast false})

(defonce *state (atom start-state))

(defn live
  "What a slider sets follows its thumb."
  [state id value]
  (assoc-in state [:sliders id :live] value))

(defn write
  "A value is kept. It is a new step for Undo, unless it belongs to the step
  before it: key presses close together, or the second click of a double one."
  [state id value same-step]
  (let [before (get-in state [:sliders id :value])
        joins (and same-step (= id (first (peek (:undo state)))))]
    (-> state
        (assoc-in [:sliders id] {:value value :live value})
        (update :writes inc)
        (cond-> (not joins) (update :undo conj [id before])))))

(defn undo
  "Takes back the last step."
  [state]
  (if-let [[id value] (peek (:undo state))]
    (-> state
        (assoc-in [:sliders id] {:value value :live value})
        (update :undo pop))
    state))

(declare handle)

(def notes
  ["Drag the thumb, or press the track and keep dragging."
   "Escape during a drag puts it back."
   "A double click puts it at its default, the notch."
   "Arrows move it 1%, with Shift 10%. Home and End go to the ends."
   "Scrolling over a slider scrolls this page."
   "Command-Z takes back the last change."])

(defn page
  "The content: under the glass, and it scrolls."
  [{:keys [sliders muted writes pad]}]
  {:fx/type :scroll-pane
   :id "page"
   :fit-to-width true
   :focus-traversable false
   :hbar-policy :never
   :content
   {:fx/type :v-box
    :spacing 14
    :padding {:top 84 :bottom 24 :left pad :right pad}
    :children
    (into
      [{:fx/type :h-box
        :alignment :center
        :children [{:fx/type :region
                    :id "square"
                    :style-class "square"
                    :opacity (/ (get-in sliders [:brightness :live]) 100.0)}]}
       {:fx/type :label
        :id "writes"
        :text (str "Written " writes (if (= 1 writes) " time" " times"))}
       {:fx/type slider-view :dispatch handle
        :id "brightness" :name "Brightness" :unit "%"
        :default 50.0
        :value (get-in sliders [:brightness :value])
        :live {:event :live :id :brightness}
        :write {:event :write :id :brightness}}
       {:fx/type :check-box
        :id "mute"
        :text "Mute"
        :selected muted
        :on-selected-changed {:event :mute}}
       {:fx/type slider-view :dispatch handle
        :id "volume" :name "Volume" :unit "%"
        :default 30.0
        :disabled muted
        :tip "Muted: untick Mute to change the volume."
        :value (get-in sliders [:volume :value])
        :live {:event :live :id :volume}
        :write {:event :write :id :volume}}]
      (for [note notes]
        {:fx/type :label :style-class ["label" "note"] :wrap-text true :text note}))}})

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
   :title "Slider"
   :width 560
   :height 420
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
    :live (swap! *state live (:id event) (:value event))
    :write (swap! *state write (:id event) (:value event) (:same-step event))
    :undo (swap! *state undo)
    :mute (swap! *state assoc :muted (boolean (:fx/event event)))
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
  (fx/mount-renderer *state renderer))
