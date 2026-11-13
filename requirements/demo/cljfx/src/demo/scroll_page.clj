(ns demo.scroll-page
  "The scroll demo's page: scroll areas from demo.scroll inside one that is
  the page. A wide table that scrolls sideways, a list of 100,000 rows, a log
  that grows, a field, and controls below the fold. This half is the demo's
  own - its state, its events and its rows - and is not for copying.

      clojure -M:scroll"
  (:require [cljfx.api :as fx]
            [clojure.edn :as edn]
            [clojure.java.io :as io]
            [demo.scroll :as s :refer [scroll-view rows-view]]
            [demo.ui :as ui :refer [button-view glass-group]])
  (:import [java.nio.file Files StandardCopyOption]
           [java.util Timer TimerTask]
           [java.util.concurrent Executors ExecutorService]
           [javafx.application Platform]))

(def row-count 100000)
(def log-most 300)

;; :places is each area's place, by its id, as it was left.
;; :rows runs from the key :lo, :n of them; :marked is a row's key, :chosen a set.
;; :loaded counts rows that have come in, so the page draws them.
(def start-state
  {:page :scroll :places {} :rows {:lo 0 :n row-count} :marked nil :chosen #{}
   :log [] :log-next 1 :loaded 0 :solid false :contrast false :logging true})

(defonce *state (atom start-state))

;;; The rows' words load off the UI thread, a few ms a batch, as from a disk.

(defonce ^:private cache (atom {}))
(defonce ^:private pending (atom #{}))
(defonce ^:private ^ExecutorService loader (Executors/newSingleThreadExecutor))
;; How long a batch takes to come in: the checks set it.
(defonce *load-ms (atom 12))

(defn row-text [k] (format "Row %,d" (long k)))

(defn- want! [k]
  (when-not (@pending k)
    (swap! pending conj k)
    (.submit loader ^Runnable
             (fn []
               (Thread/sleep (long @*load-ms))
               (let [ks @pending]
                 (swap! cache into (for [k ks] [k (row-text k)]))
                 (swap! pending #(reduce disj % ks))
                 (Platform/runLater #(swap! *state update :loaded inc)))))))

(defn text-of
  "Row `k`'s words, or nil while they load."
  [k]
  (or (@cache k) (do (want! k) nil)))

(defn forget-rows! [] (reset! cache {}) (reset! pending #{}))

;;; Steps

(defn add-above
  "Rows come in above the rest, as from a reload: the row first seen stays put."
  [state n]
  (-> state (update-in [:rows :lo] - n) (update-in [:rows :n] + n)))

(defn log-line
  "A line is added at the log's end; past `log-most`, the oldest goes."
  [{:keys [log-next] :as state}]
  (-> state
      (update :log #(vec (take-last log-most (conj % {:id log-next :text (format "%05d  saved a step" log-next)}))))
      (update :log-next inc)))

(defn keep-place [state id place] (assoc-in state [:places id] place))

(declare handle)

;;; The places on disk: plain text, written whole or not at all

(defonce *places-file
  (atom (io/file (System/getProperty "user.home")
                 "Library" "Application Support" "agent1-demo-scroll" "places.edn")))

(defn read-places
  "The places as they were left, or {} if there are none or they cannot be read."
  []
  (let [^java.io.File file @*places-file]
    (or (when (.exists file)
          (try (let [data (edn/read-string (slurp file))]
                 (when (map? data)
                   (into {} (for [[k v] data
                                  :when (and (string? k) (vector? v) (= 2 (count v)) (every? number? v))]
                              [k (mapv double v)]))))
               (catch Exception _ nil)))
        {})))

(defn write-places! [data]
  (let [^java.io.File file @*places-file
        part (io/file (str file ".part"))]
    (io/make-parents file)
    (spit part (str (pr-str data) "\n"))
    (Files/move (.toPath part) (.toPath file)
                (into-array StandardCopyOption [StandardCopyOption/ATOMIC_MOVE
                                                StandardCopyOption/REPLACE_EXISTING]))))

(defn keep-places!
  "Writes the places once they have been still for 400 ms, off the UI thread."
  []
  (let [timer (Timer. "places" true)
        written (atom (:places @*state))]
    (add-watch *state ::places
               (fn [_ _ old new]
                 (let [places (:places new)]
                   (when (not= (:places old) places)
                     (.schedule timer (proxy [TimerTask] []
                                        (run [] (when (and (= places (:places @*state)) (not= places @written))
                                                  (write-places! places)
                                                  (reset! written places))))
                                (long 400))))))))

;;; The page

(def notes
  ["Swipe or use the wheel. Shift and the wheel scroll sideways."
   "Swipe past an end: it gives, and springs back."
   "A swipe over the table that is more up than across scrolls this page."
   "Drag a bar's knob, or click its track. Option and a click does the other."
   "Click the page, then Up, Down, Page Up, Page Down, Space, Home and End."
   "System Settings, Appearance: Show scroll bars and Click in the scroll bar to."])

(defn- head [text] {:fx/type :label :style-class ["label" "section-head"] :text text})

(def columns ["Name" "Kind" "Size" "Made" "Changed" "Owner" "Place" "Tags" "Colour" "Rating" "Notes" "Shared"])

(defn table
  "Twelve columns: wider than the page, so it scrolls sideways in its own area."
  [_]
  {:fx/type :grid-pane
   :style-class ["scroll-box"]
   :children (for [[c title] (map-indexed vector columns)
                   r (range 6)]
               {:fx/type :label
                :style-class (cond-> ["label" "scroll-cell"] (zero? r) (conj "head"))
                :grid-pane/column c
                :grid-pane/row r
                :text (if (zero? r) title (str title " " r))})})

(defn grid
  "Sixteen by sixteen: larger than its room both ways."
  [_]
  {:fx/type :grid-pane
   :style-class ["scroll-box"]
   :children (for [c (range 16) r (range 16)]
               {:fx/type :label :style-class ["label" "scroll-cell"]
                :grid-pane/column c :grid-pane/row r
                :text (str (char (+ 65 c)) (inc r))})})

(defn log-view [{:keys [log]}]
  {:fx/type :v-box
   :style-class ["scroll-box"]
   :padding {:top 6 :bottom 6}
   :children (if (seq log)
               (for [{:keys [id text]} log]
                 {:fx/type :label :fx/key id :style-class ["label" "log-line"] :text text})
               [{:fx/type :label :style-class ["label" "log-line"] :text "Nothing yet"}])})

(defn scroll-page [{:keys [places rows marked chosen loaded] :as state}]
  (let [{:keys [lo n]} rows
        area (fn [id m] (merge {:fx/type scroll-view :id id :place (get places id)
                                :on-place #(handle {:event :place :id id :place %})}
                               m))]
    (area "page"
          {:axes #{:y} :glass 72
           :content
           {:fx/type :v-box
            :spacing 14
            :padding {:top 84 :bottom 32 :left 24 :right 24}
            :children
            (concat
              (for [note notes]
                {:fx/type :label :style-class ["label" "note"] :wrap-text true :text note})
              [(head "A wide table")
               (area "table" {:axes #{:x} :width 400
                              :content {:fx/type table}})
               (head "Both ways")
               (area "grid" {:axes #{:x :y} :width 400 :height 220
                             :content {:fx/type grid}})
               (head "100,000 rows")
               (area "rows" {:axes #{:y} :height 280
                             :content {:fx/type rows-view :id "row-list"
                                       :n n :row-h 32.0
                                       ;; Read again when a row comes in.
                                       :loaded loaded
                                       :text-of #(text-of (+ lo %))
                                       :key-of #(+ lo %)
                                       :index-of #(- % lo)
                                       :marked marked :chosen chosen
                                       :on-mark #(handle {:event :mark :key (+ lo %)})
                                       :on-choose #(handle {:event :choose :from (+ lo %1) :to (+ lo %2)})}})
               (head "A log")
               (area "log" {:axes #{:y} :height 160 :follow-end true
                            :content (assoc state :fx/type log-view)})
               (head "Light content")
               {:fx/type :v-box :style-class ["light-block"] :padding 16
                :children [{:fx/type :label :wrap-text true
                            :text "The knob reads over light content as over dark."}]}
               (head "A field")
               {:fx/type :text-field :id "field" :pref-height 44
                :text "Arrows here move the caret, not the page"}]
              (for [i (range 1 9)]
                {:fx/type :label :style-class ["label" "note"] :text (str "Further down, line " i)})
              [{:fx/type button-view :dispatch handle :id "far" :text "Out of sight"
                :click {:event :noop}}
               {:fx/type :label :style-class ["label" "note"] :text "The end of the page."}])}})))

(defn about-page [{:keys [places]}]
  {:fx/type scroll-view :id "about" :axes #{:y} :glass 72
   :place (get places "about")
   :on-place #(handle {:event :place :id "about" :place %})
   :content {:fx/type :v-box
             :spacing 14
             :padding {:top 84 :bottom 24 :left 24 :right 24}
             :children [{:fx/type :label :style-class ["label" "note"] :wrap-text true
                         :text "A page that fits: no bar shows, and a scroll moves nothing."}
                        {:fx/type :label :style-class ["label" "note"] :wrap-text true
                         :text "Go back to Scrolling: it is where it was left."}]}})

(defn toolbar [{:keys [page]}]
  {:fx/type glass-group
   :children [{:fx/type button-view :dispatch handle :id "to-scroll" :text "Scrolling"
               :disabled (= page :scroll) :click {:event :page :page :scroll}}
              {:fx/type button-view :dispatch handle :id "to-about" :text "About"
               :disabled (= page :about) :click {:event :page :page :about}}
              {:fx/type button-view :dispatch handle :id "add-above" :text "Add rows above"
               :tip "20 rows come in above the list's first: what is seen stays put"
               :click {:event :add-above}}]})

(defn root [{:keys [solid contrast page] :as state}]
  {:fx/type :stage
   :showing true
   :title "Scroll"
   :width 640
   :height 560
   :scene
   {:fx/type :scene
    :stylesheets [(str (io/resource "demo/glass.css"))]
    :root
    {:fx/type :stack-pane
     :style-class (cond-> ["root" "page"] solid (conj "solid") contrast (conj "contrast"))
     :children [(assoc state :fx/type (if (= page :about) about-page scroll-page) :fx/key page)
                (assoc state :fx/type toolbar
                       :stack-pane/alignment :top-center
                       :stack-pane/margin {:top 16})]}}})

(defn handle [event]
  (case (:event event)
    :place (swap! *state keep-place (:id event) (:place event))
    :page (swap! *state assoc :page (:page event))
    :add-above (swap! *state add-above 20)
    :mark (swap! *state assoc :marked (:key event))
    :choose (swap! *state assoc :chosen (set (range (:from event) (inc (:to event)))))
    :noop nil))

(def renderer
  (fx/create-renderer
    :middleware (fx/wrap-map-desc #'root)
    :opts {:fx.opt/map-event-handler handle}))

(defn start-log!
  "A line comes into the log every second."
  []
  (doto (Timer. "log" true)
    (.scheduleAtFixedRate (proxy [TimerTask] []
                            (run [] (when (:logging @*state)
                                      (Platform/runLater #(swap! *state log-line)))))
                          1000 1000)))

(defn -main [& _]
  (Platform/setImplicitExit true)
  (swap! *state assoc :places (read-places))
  (keep-places!)
  (s/watch-settings!)
  (Platform/runLater (fn [] (ui/follow-system! #(swap! *state assoc :solid %))))
  (future (swap! *state assoc :contrast (ui/increase-contrast?)))
  (start-log!)
  (fx/mount-renderer *state renderer))
