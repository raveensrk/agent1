(ns demo.version-page
  "The About demo: a main window, and About in the app menu. This half is the
  demo's own - its state and its window - and is not for copying;
  demo.version is.

      clojure -M:stamp && clojure -M:version"
  (:require [cljfx.api :as fx]
            [clojure.java.io :as io]
            [demo.ui :as ui :refer [button-view]]
            [demo.version :as v :refer [about-window]])
  (:import [javafx.application Platform]
           [javafx.stage Stage Window]))

(def app-name "Version")

(def start-state {:build nil :about-open false :solid false :contrast false})

(defonce *state (atom start-state))

(declare handle)

(defn page [_]
  {:fx/type :scroll-pane
   :id "page"
   :fit-to-width true
   :hbar-policy :never
   :content
   {:fx/type :v-box
    :spacing 10
    :padding 24
    :children
    (into [{:fx/type :label :wrap-text true :style-class ["label" "note"]
            :text (str "The app menu, " app-name ", has About " app-name ": the version and the commit.")}]
          (for [i (range 1 21)]
            {:fx/type :h-box
             :spacing 12
             :alignment :center-left
             :children [{:fx/type :label :text (format "Row %d" i) :h-box/hgrow :always :max-width Double/MAX_VALUE}
                        {:fx/type button-view :dispatch handle :id (str "row-" i) :text "Open"
                         :click {:event :noop}}]}))}})

(defn main-window [{:keys [solid contrast] :as state}]
  {:fx/type :stage
   :showing true
   :title app-name
   :width 560
   :height 480
   :on-close-request (fn [_] (Platform/exit))
   :scene
   {:fx/type :scene
    :stylesheets [(str (io/resource "demo/glass.css"))]
    :root
    {:fx/type :stack-pane
     :id "main"
     :style-class (cond-> ["root" "page"] solid (conj "solid") contrast (conj "contrast"))
     :children [(assoc state :fx/type page)]}}})

(defn root [{:keys [build about-open] :as state}]
  {:fx/type fx/ext-many
   :desc [(assoc state :fx/type main-window)
          {:fx/type about-window :app-name app-name :build build :showing about-open
           :on-close #(swap! *state assoc :about-open false)}]})

(defn choose-about!
  "About was chosen: opens the window, or brings the open one to the front."
  []
  (if (:about-open @*state)
    (some-> (first (filter #(and (instance? Stage %) (= (str "About " app-name) (.getTitle ^Stage %)))
                           (Window/getWindows)))
            (.toFront))
    (swap! *state assoc :about-open true)))

(defn handle [event]
  (case (:event event)
    :noop nil))

(def renderer
  (fx/create-renderer
    :middleware (fx/wrap-map-desc #'root)
    :opts {:fx.opt/map-event-handler handle}))

(defn start!
  "Reads the build, opens the main window, and adds About to the app menu."
  []
  (let [build (v/read-build)]
    (when-not build
      (binding [*out* *err*]
        (println "No build facts on the class path: run clojure -M:stamp first. About says unknown.")))
    (swap! *state assoc :build build)
    (fx/mount-renderer *state renderer)
    (Platform/runLater #(when-not (v/install-about! app-name choose-about!)
                          (binding [*out* *err*] (println "No app menu: About is not added."))))))

(defn -main [& _]
  (Platform/setImplicitExit true)
  (Platform/runLater (fn [] (ui/follow-system! #(swap! *state assoc :solid %))))
  (future (swap! *state assoc :contrast (ui/increase-contrast?)))
  (start!))
