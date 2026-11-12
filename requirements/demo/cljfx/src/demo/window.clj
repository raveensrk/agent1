(ns demo.window
  "A window, as requirements/gui.org, The app must have a Window, asks: tabs,
  several windows, panes that resize, and a narrow window that keeps its room.
  A reference, like demo.ui, whose buttons and glass it is built from.

  A window holds a sidebar, the page, a notes pane under the page and an
  inspector beside it. Floating windows open inside it, over everything: each
  drags by its title bar, resizes by its corner, comes to the front on a press
  and never leaves the window. A divider drags to resize a pane, within the pane's
  smallest and largest size, and the sizes are kept between runs. Below 720 px
  the sidebar shrinks to icons and the inspector hides.

  A window comes back as it was left: its place and size, its tabs and their
  pages, its floating windows, and which panes were hidden.

  The rules are plain data and pure functions - `layout`, `fit`, `clamp-size`,
  `clamp-float`, `step`, `session` and `restore` - so they are tested without a
  window.

      clojure -M:window"
  (:require [cljfx.api :as fx]
            [cljfx.ext.node :as fx.ext.node]
            [cljfx.lifecycle :as lifecycle]
            [cljfx.mutator :as mutator]
            [cljfx.prop :as prop]
            [clojure.edn :as edn]
            [clojure.java.io :as io]
            [demo.ui :as ui :refer [button-view glass-group]])
  (:import [java.nio.file Files StandardCopyOption]
           [java.util Timer TimerTask]
           [java.util.prefs Preferences]
           [javafx.application Platform]
           [javafx.scene Node]
           [javafx.scene.input MouseEvent]
           [javafx.scene.layout Region]
           [javafx.scene.shape Rectangle]
           [javafx.stage Screen]))

;;; The rules: plain data

;; Below this width a window is narrow.
(def narrow-width 720)
;; The sidebar, shrunk to icons.
(def icons-width 56)
;; The page never gets less room than this.
(def content-min-width 280)
(def content-min-height 160)
(def glide-ms 200)

(def limits
  "Each pane's smallest and largest size, and the size it starts at."
  {:sidebar {:min 160 :max 320 :default 220}
   :inspector {:min 200 :max 360 :default 260}
   :bottom {:min 80 :max 300 :default 140}})

(def float-limits
  "A floating window's smallest and largest size, and the size it starts at."
  {:min-w 200 :max-w 480 :w 260
   :min-h 120 :max-h 360 :h 160})

;; Where the first floating window opens, down from the top, and how far each
;; next one steps from the last.
(def float-top 90.0)
(def float-step 28.0)

(defn clamp-float
  "A floating window brought within its limits and wholly inside the window:
  `layer` is the room it floats in, [width height], or nil before that is known.
  In a room smaller than its smallest size it keeps that size, at the corner."
  [{:keys [x y w h] :as float} layer]
  (let [[lw lh] layer
        {:keys [min-w max-w min-h max-h]} float-limits
        w (max min-w (cond-> (min max-w w) lw (min lw)))
        h (max min-h (cond-> (min max-h h) lh (min lh)))
        x (max 0.0 (cond-> x lw (min (- lw w))))
        y (max 0.0 (cond-> y lh (min (- lh h))))]
    (assoc float :x (double x) :y (double y) :w (double w) :h (double h))))

(def default-sizes
  (into {} (for [[pane {:keys [default]}] limits] [pane (double default)])))

(def pages
  [{:id :inbox :title "Inbox" :icon "M0 2h14v10H0zM1 3v5h3l1 2h4l1-2h3V3z"}
   {:id :today :title "Today" :icon "M0 1h14v12H0zM1 4v8h12V4z"}
   {:id :notes :title "Notes" :icon "M0 1h14v2H0zM0 6h14v2H0zM0 11h9v2H0z"}
   {:id :tags :title "Tags" :icon "M7 0l7 7-7 7-7-7z"}
   {:id :archive :title "Archive" :icon "M0 0h14v4H0zM1 5h12v9H1zM5 7v2h4V7z"}])

(defn page-title [page]
  (:title (first (filter #(= page (:id %)) pages))))

(defn clamp-size
  "`size` brought within the pane's smallest and largest."
  [pane size]
  (let [{lo :min hi :max} (limits pane)]
    (double (min hi (max lo size)))))

(defn layout
  "What a window of this width shows. Narrow, the sidebar shrinks to icons and
  the inspector hides. A pane the user has hidden stays hidden at any width."
  [{:keys [width sidebar-shown inspector-shown]}]
  (let [narrow (< width narrow-width)]
    {:narrow narrow
     :sidebar (cond (not sidebar-shown) :hidden narrow :icons :else :full)
     :inspector (boolean (and inspector-shown (not narrow)))}))

(defn fit
  "The width each side pane really gets. The kept sizes are what the user asked
  for; when the window has no room for them and the page too, the inspector
  gives way first and then the sidebar, each down to its smallest."
  [width {:keys [sidebar inspector]} sizes]
  (let [side (case sidebar :hidden 0.0 :icons (double icons-width) :full (:sidebar sizes))
        insp (if inspector (:inspector sizes) 0.0)
        over (max 0.0 (- (+ side insp content-min-width) width))
        insp-give (if inspector (min over (- insp (:min (limits :inspector)))) 0.0)
        side-give (if (= :full sidebar)
                    (min (- over insp-give) (- side (:min (limits :sidebar))))
                    0.0)]
    {:sidebar (- side side-give) :inspector (- insp insp-give)}))

(defn fit-bottom
  "The height the notes pane really gets: the page above it keeps its room."
  [height sizes]
  (max (double (:min (limits :bottom)))
       (min (:bottom sizes) (- height content-min-height))))

;;; The state, and what each event does to it

(def start-state
  {:windows {1 {:id 1 :tabs [{:id 1 :page :inbox}] :active 1
                :open {:x 120.0 :y 120.0 :width 960.0 :height 600.0}
                :x 120.0 :y 120.0 :width 960.0 :height 600.0
                :floats [] :layer nil}}
   :order [1]
   :next-window 2
   :next-tab 2
   :next-float 1
   :grab nil
   :sizes default-sizes
   :dragging nil
   :sidebar-shown true
   :inspector-shown true
   :solid false
   :contrast false})

(defn- close-window [state id]
  (-> state
      (update :windows dissoc id)
      (update :order #(vec (remove #{id} %)))))

(defn- update-float
  "Applies `f` to one floating window, then keeps it inside its window."
  [state window float f]
  (let [layer (get-in state [:windows window :layer])]
    (update-in state [:windows window :floats]
               (fn [floats] (mapv #(if (= float (:id %)) (clamp-float (f %) layer) %) floats)))))

(defn- front-float
  "The last floating window in the list is the one in front."
  [state window float]
  (update-in state [:windows window :floats]
             (fn [floats] (vec (sort-by #(= float (:id %)) floats)))))

(defn step
  "The state after `event`. Pure: no window, no disk."
  [state {:keys [event window] :as e}]
  (case event
    ;; A floating window opens on the page the tab is on: across the middle of
    ;; the window and under its toolbar, clear of the sidebar, and a step down
    ;; and across from the last, so none hides another.
    :new-float
    (let [{:keys [tabs active floats layer]} (get-in state [:windows window])
          page (:page (first (filter #(= active (:id %)) tabs)))
          step (* float-step (mod (count floats) 6))
          x (+ step (if layer (/ (- (first layer) (:w float-limits)) 2.0) 40.0))
          y (+ step float-top)
          float (clamp-float {:id (:next-float state) :page page :x x :y y
                              :w (:w float-limits) :h (:h float-limits)}
                             layer)]
      (-> state
          (update-in [:windows window :floats] conj float)
          (update :next-float inc)))

    :close-float
    (update-in state [:windows window :floats]
               (fn [floats] (vec (remove #(= (:float e) (:id %)) floats))))

    :front-float (front-float state window (:float e))

    ;; A press on its title bar takes hold of it: where in it the pointer is.
    ;; It is taken hold of where it is drawn, which becomes its place.
    :float-press
    (let [state (update-float state window (:float e) identity)
          float (first (filter #(= (:float e) (:id %)) (get-in state [:windows window :floats])))]
      (-> (front-float state window (:float e))
          (assoc :grab {:float (:float e) :dx (- (:px e) (:x float)) :dy (- (:py e) (:y float))})))

    :float-drag
    (let [{:keys [float dx dy]} (:grab state)]
      (cond-> state
        (= float (:float e))
        (update-float window float #(assoc % :x (- (:px e) dx) :y (- (:py e) dy)))))

    ;; Its corner drags to resize it: the corner follows the pointer.
    :float-resize
    (update-float (update-float (front-float state window (:float e)) window (:float e) identity)
                  window (:float e)
                  #(assoc % :w (- (:px e) (:x %)) :h (- (:py e) (:y %))))

    :float-drop (assoc state :grab nil)

    ;; The room they float in changed, with the window. Only the room is noted:
    ;; each is drawn inside it, but the place it was left at is kept, so it goes
    ;; back there when there is room again, and a window that is briefly small
    ;; as it opens moves nothing for good.
    :layer-resized
    (cond-> state
      (get-in state [:windows window])
      (assoc-in [:windows window :layer] [(:w e) (:h e)]))

    :new-window
    (let [id (:next-window state)
          tab (:next-tab state)
          n (count (:order state))]
      (-> state
          (assoc-in [:windows id]
                    (let [at (+ 120.0 (* 28.0 n))
                          open {:x at :y at :width 960.0 :height 600.0}]
                      (merge open {:id id :tabs [{:id tab :page :inbox}] :active tab
                                   :open open :floats [] :layer nil})))
          (update :order conj id)
          (update :next-window inc)
          (update :next-tab inc)))

    :close-window (close-window state window)

    :new-tab
    (let [tab (:next-tab state)]
      (-> state
          (update-in [:windows window :tabs] conj {:id tab :page :inbox})
          (assoc-in [:windows window :active] tab)
          (update :next-tab inc)))

    ;; Closing a tab moves to the one that takes its place, else the one
    ;; before it. Closing the last tab closes the window.
    :close-tab
    (let [{:keys [tabs active]} (get-in state [:windows window])
          tab (or (:tab e) active)
          at (first (keep-indexed #(when (= tab (:id %2)) %1) tabs))
          left (vec (remove #(= tab (:id %)) tabs))]
      (cond
        (nil? at) state
        (empty? left) (close-window state window)
        :else (-> state
                  (assoc-in [:windows window :tabs] left)
                  (assoc-in [:windows window :active]
                            (if (= tab active)
                              (:id (get left (min at (dec (count left)))))
                              active)))))

    :select-tab (assoc-in state [:windows window :active] (:tab e))

    :next-tab
    (let [{:keys [tabs active]} (get-in state [:windows window])
          ids (mapv :id tabs)
          at (.indexOf ^java.util.List ids active)]
      (assoc-in state [:windows window :active]
                (get ids (mod (+ at (:by e 1)) (count ids)))))

    :select-page
    (update-in state [:windows window :tabs]
               (fn [tabs]
                 (let [active (get-in state [:windows window :active])]
                   (mapv #(cond-> % (= active (:id %)) (assoc :page (:page e))) tabs))))

    :toggle-sidebar (update state :sidebar-shown not)
    :toggle-inspector (update state :inspector-shown not)

    :resized (cond-> state
               (get-in state [:windows window])
               (assoc-in [:windows window (:dim e)] (:value e)))

    ;; A divider follows the pointer: `x` and `y` are where the pointer is in
    ;; the window, `w` and `h` the window's own size, `edge` the room around it.
    :drag
    (let [{:keys [pane x y w h edge]} e
          size (case pane
                 :sidebar (- x edge)
                 :inspector (- w x edge)
                 :bottom (- h y edge))]
      (-> state
          (assoc :dragging pane)
          (assoc-in [:sizes pane] (clamp-size pane size))))

    :drag-end (assoc state :dragging nil)

    ;; A double click on a divider puts its pane back to the size it started at.
    :reset-size (assoc-in state [:sizes (:pane e)] (double (:default (limits (:pane e)))))

    state))

;;; A window comes back as it was left

(def window-min {:width 480.0 :height 400.0})

(defn session
  "What is kept of the state between runs, as plain data: each window's place
  and size, its tabs' pages and which is in front, its floating windows, and
  which panes are hidden. Ids are not kept; a run makes its own."
  [state]
  {:version 1
   :sidebar-shown (:sidebar-shown state)
   :inspector-shown (:inspector-shown state)
   :windows (vec (for [id (:order state)
                       :let [{:keys [tabs active floats] :as window} (get-in state [:windows id])]]
                   (assoc (select-keys window [:x :y :width :height])
                          :pages (mapv :page tabs)
                          :front (max 0 (.indexOf ^java.util.List (mapv :id tabs) active))
                          :floats (mapv #(select-keys % [:page :x :y :w :h]) floats))))})

(defn on-a-screen?
  "True if enough of the window's title bar is on one of the screens to take
  hold of: 100 px of its width, and its top edge."
  [{:keys [x y width]} screens]
  (boolean (some (fn [{sx :x sy :y sw :width sh :height}]
                   (and (<= sy y (- (+ sy sh) 40))
                        (>= (- (min (+ x width) (+ sx sw)) (max x sx)) 100)))
                 screens)))

(defn restore
  "The state a kept session opens as, or nil if it holds no window to open.
  Nothing in it is trusted: a window off every screen comes back at the place
  a first window opens, one too small comes back at the smallest size, a page
  no longer known becomes the first page, and a floating window comes back
  within its limits. `screens` are the screens there are now, as maps of :x :y
  :width :height."
  [data screens]
  (let [known (set (map :id pages))
        page #(if (known %) % (:id (first pages)))
        number #(if (number? %1) (double %1) %2)
        windows (when (map? data) (filter map? (:windows data)))]
    (when (seq windows)
      (reduce
        (fn [state [n kept]]
          (let [id (:next-window state)
                size {:width (max (:width window-min) (number (:width kept) 960.0))
                      :height (max (:height window-min) (number (:height kept) 600.0))}
                place (merge size {:x (number (:x kept) 120.0) :y (number (:y kept) 120.0)})
                at (+ 120.0 (* 28.0 n))
                open (if (on-a-screen? place screens) place (merge size {:x at :y at}))
                kept-pages (if (sequential? (:pages kept)) (:pages kept) [])
                tabs (vec (map-indexed (fn [i p] {:id (+ (:next-tab state) i) :page (page p)})
                                       (if (seq kept-pages) kept-pages [(:id (first pages))])))
                front (min (dec (count tabs)) (max 0 (long (number (:front kept) 0.0))))
                floats (vec (map-indexed
                              (fn [i f]
                                (clamp-float {:id (+ (:next-float state) i) :page (page (:page f))
                                              :x (number (:x f) 40.0) :y (number (:y f) float-top)
                                              :w (number (:w f) (:w float-limits))
                                              :h (number (:h f) (:h float-limits))}
                                             nil))
                              (if (sequential? (:floats kept)) (filter map? (:floats kept)) [])))]
            (-> state
                (assoc-in [:windows id] (merge open {:id id :tabs tabs :active (:id (get tabs front))
                                                    :open open :floats floats :layer nil}))
                (update :order conj id)
                (update :next-window inc)
                (update :next-tab + (count tabs))
                (update :next-float + (count floats)))))
        (assoc start-state
               :windows {} :order [] :next-window 1 :next-tab 1 :next-float 1
               :sidebar-shown (not (false? (:sidebar-shown data)))
               :inspector-shown (not (false? (:inspector-shown data))))
        (map-indexed vector windows)))))

;;; The session on disk: plain text, written whole or not at all

(defonce *session-file
  (atom (io/file (System/getProperty "user.home")
                 "Library" "Application Support" "agent1-demo-window" "session.edn")))

(defn read-session
  "The kept session, or nil if there is none. A file that cannot be read is
  moved aside, never written over, and counts as none."
  []
  (let [^java.io.File file @*session-file]
    (when (.exists file)
      (try
        (let [data (edn/read-string (slurp file))]
          (when-not (map? data) (throw (ex-info "not a session" {})))
          data)
        (catch Exception _
          (Files/move (.toPath file) (.toPath (io/file (str file ".bad")))
                      (into-array StandardCopyOption [StandardCopyOption/REPLACE_EXISTING]))
          nil)))))

(defn write-session!
  "Writes the session beside its file and moves it into place, so a reader
  never sees half of one."
  [data]
  (let [^java.io.File file @*session-file
        part (io/file (str file ".part"))]
    (io/make-parents file)
    (spit part (str (pr-str data) "\n"))
    (Files/move (.toPath part) (.toPath file)
                (into-array StandardCopyOption [StandardCopyOption/ATOMIC_MOVE
                                                StandardCopyOption/REPLACE_EXISTING]))))

;;; Sizes kept between runs

(defonce *prefs-node (atom "agent1/demo/window"))

(defn- prefs ^Preferences [] (.node (Preferences/userRoot) @*prefs-node))

(defn load-sizes
  "The sizes kept from the last run. One kept outside the limits comes back
  within them; one never kept is the size the pane starts at."
  []
  (let [p (prefs)]
    (into {} (for [[pane {:keys [default]}] limits]
               [pane (clamp-size pane (.getDouble p (name pane) (double default)))]))))

(defn save-sizes! [sizes]
  (let [p (prefs)]
    (doseq [[pane size] sizes] (.putDouble p (name pane) (double size)))
    (.flush p)))

;;; Motion

(defn- glide-width!
  "Sets a pane's width. A change of kind - full to icons, shown to hidden -
  glides; a change of size alone, a drag or a window being resized, follows at
  once. Under Reduce Motion nothing glides. A pane of no width is not drawn."
  [^Region node [width kind]]
  (let [props (.getProperties node)
        first? (not (.containsKey props ::kind))
        same? (= kind (.get props ::kind))
        width (double width)]
    (.put props ::kind kind)
    (when first?
      (.setMinWidth node 0.0)
      (.setMaxWidth node Region/USE_PREF_SIZE)
      ;; Side panels are clipped as they close; glass keeps its shadow instead.
      (when (.contains (.getStyleClass node) "panel")
        (let [clip (Rectangle.)]
          (.bind (.widthProperty clip) (.widthProperty node))
          (.bind (.heightProperty clip) (.heightProperty node))
          (.setClip node clip))))
    (when (pos? width) (.setVisible node true))
    (ui/tween! node ::width
               {:ms (if (or first? same? @ui/*reduce) 0 glide-ms)
                :on-done #(.setVisible node (pos? width))}
               [[(.prefWidthProperty node) width]])))

(defn- enter!
  "A floating window fades in and grows a little as it opens. Under Reduce
  Motion it only fades."
  [^Node node]
  (.setOpacity node 0.0)
  (when-not @ui/*reduce
    (.setScaleX node 0.96)
    (.setScaleY node 0.96))
  (ui/tween! node ::enter {:ms 180}
             [[(.opacityProperty node) 1.0]
              [(.scaleXProperty node) 1.0]
              [(.scaleYProperty node) 1.0]]))

(def ext-width
  (fx/make-ext-with-props
    {::width (prop/make (mutator/setter glide-width!) lifecycle/scalar)}))

;;; The views

(defonce *state (atom start-state))

(declare handle)

;; The room around the panes, and half a divider: where a pane's edge is.
(def edge 8)
(def divider-size 9)

(def sidebar-icon "M0 0h16v12H0zM1 1v10h14V1zM1 1h4v10H1z")
(def inspector-icon "M0 0h16v12H0zM1 1v10h14V1zM11 1h4v10h-4z")
(def plus-icon "M5 0h2v5h5v2H7v5H5V7H0V5h5z")
(def float-icon "M0 4h10v8H0zM1 5v6h8V5zM4 0h10v8h-3V7h2V1H5v2H4z")

(defn divider
  "One pixel to look at, nine to take hold of. It drags to resize `pane`, and a
  double click puts the pane back to the size it started at."
  [{:keys [pane across dragging]}]
  {:fx/type :region
   :id (str "divider-" (name pane))
   :style-class (cond-> [(if across "divider-v" "divider-h")] dragging (conj "dragging"))
   :cursor (if across :v-resize :h-resize)
   (if across :min-height :min-width) divider-size
   (if across :pref-height :pref-width) divider-size
   :on-mouse-dragged {:event :drag :pane pane}
   :on-mouse-released {:event :drag-end :pane pane}
   :on-mouse-clicked {:event :reset-size :pane pane}})

(defn sidebar-view
  "The sidebar: glass. Shrunk to icons, each row keeps its name as a tooltip."
  [{:keys [window mode width page]}]
  (let [icons (= :icons mode)]
    {:fx/type ext-width
     :props {::width [width mode]}
     :desc {:fx/type :v-box
            :id "sidebar"
            :style-class ["glass-pane"]
            :spacing 2
            :padding 8
            :children
            (for [{:keys [id title icon]} pages]
              {:fx/type fx.ext.node/with-tooltip-props
               :fx/key id
               :props (if icons {:tooltip {:fx/type :tooltip :text title}} {})
               :desc {:fx/type :button
                      :style-class (cond-> ["button" "sidebar-item"]
                                     (= id page) (conj "on")
                                     icons (conj "icons"))
                      :text (when-not icons title)
                      :accessible-help title
                      :graphic {:fx/type :svg-path :style-class "icon" :content icon}
                      :alignment (if icons :center :center-left)
                      :max-width Double/MAX_VALUE
                      :on-action {:event :select-page :window window :page id}}})}}))

(defn toolbar
  "The window's glass: a way to hide each side pane, and a new tab."
  [{:keys [window sidebar-shown inspector-shown narrow]}]
  {:fx/type :h-box
   :alignment :center-left
   :spacing 10
   :children
   [{:fx/type glass-group
     :children [{:fx/type button-view :dispatch handle
                 :id "toggle-sidebar" :icon sidebar-icon
                 :name (if sidebar-shown "Hide Sidebar" "Show Sidebar")
                 :tip (if sidebar-shown "Hide the sidebar" "Show the sidebar")
                 :click {:event :toggle-sidebar}}]}
    {:fx/type :region :h-box/hgrow :always}
    {:fx/type glass-group
     :children [{:fx/type button-view :dispatch handle
                 :id "new-tab" :icon plus-icon :name "New Tab" :tip "New tab"
                 :click {:event :new-tab :window window}}
                {:fx/type button-view :dispatch handle
                 :id "new-float" :icon float-icon :name "New Floating Window"
                 :tip "New floating window, on this page"
                 :click {:event :new-float :window window}}
                {:fx/type button-view :dispatch handle
                 :id "toggle-inspector" :icon inspector-icon
                 :name (if inspector-shown "Hide Inspector" "Show Inspector")
                 :disabled narrow
                 :tip (cond narrow "The window is too narrow for the inspector."
                            inspector-shown "Hide the inspector"
                            :else "Show the inspector")
                 :click {:event :toggle-inspector}}]}]})

(defn tab-bar
  "One tab for each page open in the window. Shown once there are two."
  [{:keys [window tabs active]}]
  {:fx/type :h-box
   :id "tab-bar"
   :style-class ["tab-bar"]
   :spacing 2
   :children
   (for [{:keys [id page]} tabs]
     {:fx/type :h-box
      :fx/key id
      :style-class (cond-> ["tab-item"] (= id active) (conj "on"))
      :alignment :center-left
      :spacing 6
      :h-box/hgrow :always
      :accessible-role :tab-item
      :on-mouse-clicked {:event :select-tab :window window :tab id}
      :children [{:fx/type :label :text (page-title page) :max-width Double/MAX_VALUE :h-box/hgrow :always}
                 {:fx/type :button
                  :style-class ["button" "tab-close"]
                  :text "×"
                  :accessible-help (str "Close the tab " (page-title page))
                  :on-action {:event :close-tab :window window :tab id}}]})})

(defn float-view
  "A floating window: glass, with a title bar that names it and drags it, a
  close button and no minimise, as Apple's panels have, and a corner that
  resizes it. A press anywhere on it brings it to the front."
  [{:keys [window float]}]
  (let [{:keys [id page x y w h]} float
        on (fn [event] {:event event :window window :float id})]
    {:fx/type fx/ext-on-instance-lifecycle
     :on-created enter!
     :desc
     {:fx/type :stack-pane
      :id (str "float-" id)
      :style-class ["glass-pane" "floater"]
      :layout-x x
      :layout-y y
      :pref-width w
      :pref-height h
      :on-mouse-pressed (on :front-float)
      :children
      [{:fx/type :v-box
        :children [{:fx/type :h-box
                    :style-class ["floater-bar"]
                    :alignment :center-left
                    :on-mouse-pressed (on :float-press)
                    :on-mouse-dragged (on :float-drag)
                    :on-mouse-released (on :float-drop)
                    :children [{:fx/type :label :style-class ["label" "heading"]
                                :text (page-title page)
                                :max-width Double/MAX_VALUE :h-box/hgrow :always}
                               {:fx/type :button
                                :style-class ["button" "tab-close"]
                                :text "×"
                                :accessible-help (str "Close the floating window " (page-title page))
                                :on-action (on :close-float)}]}
                   {:fx/type :v-box
                    :v-box/vgrow :always
                    :padding 12
                    :spacing 4
                    :children [{:fx/type :label :text (str "Floating window " id)}
                               {:fx/type :label :text "Drag the bar. Drag the corner."}]}]}
       {:fx/type :region
        :style-class ["float-grip"]
        :cursor :se-resize
        :max-width 16 :max-height 16
        :stack-pane/alignment :bottom-right
        :on-mouse-dragged (on :float-resize)
        :on-mouse-released (on :float-drop)}]}}))

(defn float-layer
  "The room the floating windows are in: the whole window, over everything.
  It takes no clicks itself, so what is under it still works."
  [{:keys [window floats layer]}]
  {:fx/type fx/ext-on-instance-lifecycle
   :on-created (fn [^Region layer]
                 (let [tell (reify javafx.beans.value.ChangeListener
                              (changed [_ _ _ _]
                                (handle {:event :layer-resized :window window
                                         :w (.getWidth layer) :h (.getHeight layer)})))]
                   (.addListener (.widthProperty layer) tell)
                   (.addListener (.heightProperty layer) tell)))
   :desc {:fx/type :pane
          :id "float-layer"
          :pick-on-bounds false
          :children (for [float floats]
                      ;; Drawn inside the room there is now, wherever it was left.
                      {:fx/type float-view :fx/key (:id float) :window window
                       :float (clamp-float float layer)})}})

(defn window-view
  "One window: its own tabs, the panes at the sizes all windows share."
  [{:keys [window state]}]
  (let [{:keys [id tabs active width height open floats]} window
        {:keys [sizes dragging sidebar-shown inspector-shown look solid contrast]} state
        shown (layout {:width width :sidebar-shown sidebar-shown :inspector-shown inspector-shown})
        widths (fit (- width (* 2 edge)) shown sizes)
        tab (first (filter #(= active (:id %)) tabs))
        page (:page tab)
        at (inc (.indexOf ^java.util.List (mapv :id tabs) active))]
    {:fx/type :stage
     :showing true
     :title (page-title page)
     ;; Where it opens. Where it is now is read back below, and never set from
     ;; here again, so a window being moved is not pulled back.
     :x (:x open)
     :y (:y open)
     :width (:width open)
     :height (:height open)
     :min-width (:width window-min)
     :min-height (:height window-min)
     :on-x-changed {:event :resized :window id :dim :x}
     :on-y-changed {:event :resized :window id :dim :y}
     :on-width-changed {:event :resized :window id :dim :width}
     :on-height-changed {:event :resized :window id :dim :height}
     :on-close-request {:event :close-window :window id}
     :scene
     {:fx/type :scene
      :stylesheets [(str (io/resource "demo/glass.css")) (str (io/resource "demo/window.css"))]
      :root
      {:fx/type :v-box
       :style-class (cond-> ["root" "page"] solid (conj "solid") contrast (conj "contrast"))
       :children
       [{:fx/type :menu-bar
         :use-system-menu-bar true
         :menus
         [{:fx/type :menu
           :text "File"
           :items [{:fx/type :menu-item :text "New Window" :accelerator [:shortcut :n]
                    :on-action {:event :new-window}}
                   {:fx/type :menu-item :text "New Tab" :accelerator [:shortcut :t]
                    :on-action {:event :new-tab :window id}}
                   {:fx/type :separator-menu-item}
                   {:fx/type :menu-item :text "Close Tab" :accelerator [:shortcut :w]
                    :on-action {:event :close-tab :window id}}
                   {:fx/type :menu-item :text "Close Window" :accelerator [:shortcut :shift :w]
                    :on-action {:event :close-window :window id}}]}
          {:fx/type :menu
           :text "View"
           :items [{:fx/type :menu-item
                    :text (if sidebar-shown "Hide Sidebar" "Show Sidebar")
                    :accelerator [:shortcut :ctrl :s]
                    :on-action {:event :toggle-sidebar}}
                   {:fx/type :menu-item
                    :text (if inspector-shown "Hide Inspector" "Show Inspector")
                    :accelerator [:shortcut :alt :i]
                    :on-action {:event :toggle-inspector}}]}
          {:fx/type :menu
           :text "Window"
           :items [{:fx/type :menu-item :text "Show Next Tab" :accelerator [:shortcut :shift :close-bracket]
                    :on-action {:event :next-tab :window id :by 1}}
                   {:fx/type :menu-item :text "Show Previous Tab" :accelerator [:shortcut :shift :open-bracket]
                    :on-action {:event :next-tab :window id :by -1}}
                   {:fx/type :separator-menu-item}
                   {:fx/type :menu-item :text "New Floating Window" :accelerator [:shortcut :shift :f]
                    :on-action {:event :new-float :window id}}]}]}
        {:fx/type :stack-pane
         :v-box/vgrow :always
         :children
         [{:fx/type :h-box
         :padding edge
         :children
         (cond->
           [{:fx/type sidebar-view
             :window id :mode (:sidebar shown) :width (:sidebar widths) :page page}]
           (= :full (:sidebar shown))
           (conj {:fx/type divider :pane :sidebar :dragging (= :sidebar dragging)})
           (not= :full (:sidebar shown))
           (conj {:fx/type :region :min-width (if (= :icons (:sidebar shown)) divider-size 0)})
           true
           (conj
             {:fx/type :v-box
              :h-box/hgrow :always
              :min-width 0
              :spacing 10
              :children
              (cond->
                [(assoc shown :fx/type toolbar :window id
                        :sidebar-shown sidebar-shown :inspector-shown inspector-shown)]
                (< 1 (count tabs))
                (conj {:fx/type tab-bar :window id :tabs tabs :active active})
                true
                (conj
                  {:fx/type :h-box
                   :v-box/vgrow :always
                   :children
                   (cond->
                     [{:fx/type :v-box
                       :h-box/hgrow :always
                       :min-width 0
                       :children
                       [{:fx/type :v-box
                         :id "content"
                         :v-box/vgrow :always
                         :min-height 0
                         :alignment :center
                         :spacing 8
                         :children [{:fx/type :label :id "page-title" :style-class ["label" "page-title"]
                                     :text (page-title page)}
                                    {:fx/type :label
                                     :text (str "Tab " at " of " (count tabs) " - window " id)}]}
                        {:fx/type divider :pane :bottom :across true :dragging (= :bottom dragging)}
                        {:fx/type :v-box
                         :id "bottom"
                         :style-class ["panel"]
                         :min-height 0
                         :pref-height (fit-bottom (- height 120) sizes)
                         :max-height :use-pref-size
                         :children [{:fx/type :label :style-class ["label" "heading"] :text "Notes"}
                                    {:fx/type :label :text "A pane under the page. Drag its top edge."}]}]}]
                     (:inspector shown)
                     (conj {:fx/type divider :pane :inspector :dragging (= :inspector dragging)})
                     true
                     (conj {:fx/type ext-width
                            :props {::width [(:inspector widths) (if (:inspector shown) :shown :hidden)]}
                            :desc {:fx/type :v-box
                                   :id "inspector"
                                   :style-class ["panel"]
                                   :spacing 6
                                   :children [{:fx/type :label :style-class ["label" "heading"] :text "Inspector"}
                                              {:fx/type :label :text (str "Page: " (page-title page))}
                                              {:fx/type :label :text "A side panel. Drag its left edge."}]}}))}))}))}
          ;; Last, so over everything else in the window.
          {:fx/type float-layer :window id :floats floats :layer (:layer window)}]}]}}}))

(defn root [state]
  {:fx/type fx/ext-many
   :desc (for [id (:order state)]
           {:fx/type window-view
            :fx/key id
            :window (get-in state [:windows id])
            :state state})})

(defn handle
  "Reads what an event needs from the window, then steps the state. Sizes are
  written when a drag ends, not at every move of it."
  [event]
  (let [e (:fx/event event)]
    (case (:event event)
      :drag (let [^MouseEvent m e
                  scene (.getScene ^Node (.getSource m))]
              (swap! *state step (assoc event
                                        :x (.getSceneX m) :y (.getSceneY m)
                                        :w (.getWidth scene) :h (.getHeight scene)
                                        :edge (+ edge (/ divider-size 2.0)))))
      :drag-end (save-sizes! (:sizes (swap! *state step event)))
      :reset-size (when (= 2 (.getClickCount ^MouseEvent e))
                    (save-sizes! (:sizes (swap! *state step event))))
      :resized (swap! *state step (assoc event :value (double e)))
      ;; Where the pointer is in the room the floating windows are in.
      (:float-press :float-drag :float-resize)
      (let [^MouseEvent m e
            ^Node layer (.lookup (.getScene ^Node (.getSource m)) "#float-layer")
            at (.sceneToLocal layer (.getSceneX m) (.getSceneY m))]
        (swap! *state step (assoc event :px (.getX at) :py (.getY at))))
      (swap! *state step event))))

(defn screens
  "The screens there are now, as `restore` takes them. On the UI thread."
  []
  (vec (for [^Screen screen (Screen/getScreens)
             :let [b (.getVisualBounds screen)]]
         {:x (.getMinX b) :y (.getMinY b) :width (.getWidth b) :height (.getHeight b)})))

(defn keep-session!
  "Writes the session whenever it has been still for 400 ms, off the UI thread,
  and once more at quit. A state with no window is never kept: closing the last
  window quits, and the session to come back to is the one before it."
  []
  (let [wanted (atom nil)
        written (atom nil)
        timer (Timer. "session" true)
        flush! (fn [] (let [data @wanted]
                        (when (and data (not= data @written))
                          (write-session! data)
                          (reset! written data))))]
    (add-watch *state ::session
               (fn [_ _ old new]
                 (let [before (session old) after (session new)]
                   (when (and (not= before after) (seq (:windows after)))
                     (reset! wanted after)
                     (.schedule timer (proxy [TimerTask] []
                                        (run [] (when (= after @wanted) (flush!))))
                                (long 400))))))
    (.addShutdownHook (Runtime/getRuntime) (Thread. ^Runnable flush!))))

(def renderer
  (fx/create-renderer
    :middleware (fx/wrap-map-desc #'root)
    :opts {:fx.opt/map-event-handler handle}))

(defn -main [& _]
  (Platform/setImplicitExit true)
  (let [kept (read-session)
        opened (promise)]
    ;; The screens are read on the UI thread; the windows open after.
    (Platform/runLater
      (fn []
        (reset! *state (assoc (or (restore kept (screens)) start-state) :sizes (load-sizes)))
        (ui/follow-system! #(swap! *state assoc :solid %))
        (deliver opened true)))
    @opened
    (keep-session!)
    (fx/mount-renderer *state renderer)))
