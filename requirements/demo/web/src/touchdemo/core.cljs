(ns touchdemo.core
  "Touch demo: what tap, hold, swipe and drag do on each kind of component.
  One gesture tracker on pointer events; touch events only to stop the
  browser's own pan during a lift or a pull."
  (:require [replicant.dom :as r]))

;; ---------------------------------------------------------------- state

(def tabs [[:buttons "Buttons"] [:list "List"] [:chips "Chips"] [:controls "Controls"]])

(defonce state
  (atom {:tab :buttons
         :tab-dx 0
         :pressed nil          ; id of the control that is sunk
         :fill {}              ; id -> 0..1 hold fill
         :rows (vec (for [i (range 1 9)] {:id i :title (str "Note " i) :pinned false}))
         :row-dx {}            ; id -> live swipe offset
         :open-row nil         ; id whose actions show
         :lift nil             ; {:id :dy}
         :pull 0 :refreshing false
         :chips (into (sorted-map) (for [c ["home" "work" "ideas" "later" "read"]] [c false]))
         :menu nil             ; {:for label :x :y}
         :sheet false :sheet-dy 0
         :slider 40
         :log '()}))

(defonce blk (atom {}))       ; what the touchmove guard blocks

(defn log! [s]
  (swap! state update :log #(take 6 (cons s %))))

;; ---------------------------------------------------------------- tracker

(def slop 10)
(def hold-ms 500)
(def fill-from 150)

(defn- inside? [el x y]
  (let [b (.getBoundingClientRect el)]
    (and (<= (.-left b) x (.-right b)) (<= (.-top b) y (.-bottom b)))))

(defn gesture
  "A pointerdown handler. Phases: pending -> drag | held | lifted | dead.
  axis :x or :y picks the drag direction; the other direction is left to
  the browser's scroll."
  [{:keys [press release tap hold progress axis move end lift-move lift-end claim-x]}]
  (fn [e]
    (when (or (not= "mouse" (.-pointerType e)) (zero? (.-button e)))
      (when claim-x (set! (.-claimedX e) true))
      (when-not (and (= axis :x) (not claim-x) (.-claimedX e))
        (let [el (.-currentTarget e)
              pid (.-pointerId e)
              x0 (.-clientX e) y0 (.-clientY e) t0 (js/Date.now)
              ph (atom :pending)
              trail (atom [x0 t0 x0 t0])
              timers (atom [])
              stop-timers #(do (doseq [t @timers] (js/clearTimeout t) (js/clearInterval t))
                               (when progress (progress 0)))
              listeners (atom nil)
              done (fn []
                     (stop-timers)
                     (swap! blk dissoc :lift)
                     (doseq [[k f] @listeners] (.removeEventListener js/window k f))
                     (when release (release)))
              on-move
              (fn [ev]
                (when (= pid (.-pointerId ev))
                  (let [x (.-clientX ev) y (.-clientY ev) dx (- x x0) dy (- y y0)
                        [lx lt] @trail]
                    (reset! trail [x (js/Date.now) lx lt])
                    (case @ph
                      :pending
                      (when (> (js/Math.hypot dx dy) slop)
                        (stop-timers)
                        (let [hor (> (js/Math.abs dx) (js/Math.abs dy))]
                          (if (and move (= axis (if hor :x :y)))
                            (do (reset! ph :drag) (when release (release)) (move dx dy))
                            (do (reset! ph :dead) (done)))))
                      :drag (move dx dy)
                      :lifted (lift-move dx dy)
                      nil))))
              on-up
              (fn [ev]
                (when (= pid (.-pointerId ev))
                  (let [x (.-clientX ev) y (.-clientY ev) dx (- x x0) dy (- y y0)
                        [_ _ px pt] @trail
                        v (/ (- x px) (max 1 (- (js/Date.now) pt)))
                        p @ph]
                    (done)
                    (case p
                      :pending (when (and tap (inside? el x y)) (tap))
                      :drag (when end (end dx dy v))
                      :lifted (when lift-end (lift-end dx dy))
                      nil))))
              on-cancel
              (fn [ev]
                (when (= pid (.-pointerId ev))
                  (let [p @ph]
                    (done)
                    (cond (= p :drag) (when end (end 0 0 0))
                          (= p :lifted) (when lift-end (lift-end 0 0))))))]
          (reset! listeners [["pointermove" on-move] ["pointerup" on-up] ["pointercancel" on-cancel]])
          (doseq [[k f] @listeners] (.addEventListener js/window k f))
          (when press (press))
          (when hold
            (swap! timers conj
                   (js/setTimeout
                    (fn []
                      (when (= @ph :pending)
                        (stop-timers)
                        (if lift-move
                          (do (reset! ph :lifted) (swap! blk assoc :lift true))
                          (do (reset! ph :held) (when release (release))))
                        (hold x0 y0)))
                    hold-ms))
            (when progress
              (swap! timers conj
                     (js/setInterval
                      #(let [t (- (js/Date.now) t0)]
                         (when (> t fill-from)
                           (progress (min 1 (/ (- t fill-from) (- hold-ms fill-from))))))
                      16)))))))))

(defn- pressable
  "Handlers for a control that sinks on press and may have a hold action."
  [id {:keys [tap hold]}]
  {:pointerdown (gesture {:press #(swap! state assoc :pressed id)
                          :release #(swap! state assoc :pressed nil)
                          :tap tap
                          :hold hold
                          :progress (when hold #(swap! state assoc-in [:fill id] %))})
   :contextmenu #(.preventDefault %)})

;; ---------------------------------------------------------------- history: back closes sheet and menu

(defn- open-layer! [k v]
  (.pushState js/history #js {:layer (name k)} "")
  (swap! state assoc k v))

(defn- close-layer! [] (.back js/history))

(defn- on-popstate [_]
  (swap! state assoc :menu nil :sheet false :sheet-dy 0))

;; ---------------------------------------------------------------- views

(defn- btn [id label s opts & [kind]]
  [:button {:class ["btn" (or kind "plain")
                    (when (= id (:pressed s)) "sunk")
                    (when (:hold opts) "has-hold")]
            :on (pressable id opts)}
   [:span.fill {:style {:transform (str "scaleX(" (get-in s [:fill id] 0) ")")}}]
   [:span.label label]])

(defn- rule [kind & lines]
  [:div.rule [:strong kind] (for [l lines] [:div l])])

(defn- buttons-tab [s]
  [:section
   (rule "Button" "Tap: its action" "Hold 500 ms: second action, fill shows it coming"
         "Slide off before lifting: nothing fires")
   [:div.row-of
    (btn :save "Save" s {:tap #(log! "Save: tap → saved")
                         :hold (fn [_ _] (log! "Save: hold → saved as copy"))} "main")
    (btn :share "Share" s {:tap #(log! "Share: tap → share sheet")})]
   [:div.row-of
    (btn :del "Delete" s {:tap #(log! "Delete: tap → asks first")} "danger")
    (btn :sheet "Open sheet" s {:tap #(open-layer! :sheet true)})]
   (rule "Icon button" "Tap: its action" "Hold: names itself (tooltip)")
   [:div.row-of
    (btn :star "★" s {:tap #(log! "Star: tap → starred")
                      :hold (fn [_ _] (log! "Star: hold → tooltip \"Star this note\""))} "icon")]])

(defn- row-view [s {:keys [id title pinned]} idx]
  (let [dx (get-in s [:row-dx id] (if (= id (:open-row s)) -160 0))
        lift (:lift s)
        lifted? (= id (:id lift))]
    [:div.row-wrap {:replicant/key id
                    :class (when lifted? "lifted")
                    :style {:transform (when lifted? (str "translateY(" (:dy lift) "px)"))}}
     [:div.under-left "📌 Pin"]
     [:div.under-right
      [:button.act.archive {:on {:click #(do (log! (str title ": Archive button")) (swap! state assoc :open-row nil))}} "Archive"]
      [:button.act.delete {:on {:click #(do (log! (str title ": Delete button → asks first")) (swap! state assoc :open-row nil))}} "Delete"]]
     [:div.row
      {:style {:transform (str "translateX(" dx "px)")
               :transition (if (contains? (:row-dx s) id) "none" "transform 220ms ease")}
       :on {:contextmenu #(.preventDefault %)
            :pointerdown
            (gesture
             {:axis :x :claim-x true
              :tap #(if (:open-row s)
                      (do (swap! state assoc :open-row nil) (log! (str title ": tap → closes actions")))
                      (log! (str title ": tap → opens note")))
              :move (fn [mx _]
                      (let [base (if (= id (:open-row @state)) -160 0)]
                        (swap! state assoc-in [:row-dx id] (+ base mx))))
              :end (fn [_ _ v]
                     (let [d (get-in @state [:row-dx id] 0)]
                       (swap! state update :row-dx dissoc id)
                       (cond
                         (< d -260) (do (log! (str title ": full swipe left → archived"))
                                        (swap! state #(-> % (assoc :open-row nil)
                                                          (update :rows (fn [rs] (vec (remove (comp #{id} :id) rs)))))))
                         (or (< d -60) (< v -0.5)) (do (swap! state assoc :open-row id)
                                                       (log! (str title ": swipe left → actions")))
                         (> d 80) (do (swap! state update :rows (fn [rs] (mapv #(if (= id (:id %)) (update % :pinned not) %) rs)))
                                      (swap! state assoc :open-row nil)
                                      (log! (str title ": swipe right → pin toggled")))
                         :else (swap! state assoc :open-row nil))))
              :hold (fn [_ _] (swap! state assoc :lift {:id id :dy 0 :from idx})
                      (log! (str title ": hold → lifted, drag to reorder")))
              :lift-move (fn [_ dy] (swap! state assoc-in [:lift :dy] dy))
              :lift-end (fn [_ dy]
                          (let [to (-> (+ idx (js/Math.round (/ dy 57))) (max 0) (min (dec (count (:rows @state)))))]
                            (swap! state (fn [st]
                                           (let [rs (:rows st) r (rs idx) rs (vec (concat (subvec rs 0 idx) (subvec rs (inc idx))))]
                                             (-> st (assoc :lift nil)
                                                 (assoc :rows (vec (concat (subvec rs 0 to) [r] (subvec rs to))))))))
                            (log! (str title ": dropped at " (inc to)))))})}}
      [:span (when pinned "📌 ") title]
      [:span.hint "›"]]]))

(defn- refresh! []
  (swap! state assoc :refreshing true :pull 0)
  (log! "List: refreshing…")
  (js/setTimeout #(do (swap! state assoc :refreshing false) (log! "List: refreshed")) 900))

(defn- list-tab [s]
  [:section
   (rule "List row" "Tap: open" "Swipe left: actions; full swipe: archive (never delete)"
         "Swipe right: pin" "Hold: lift, then drag to reorder" "Pull down at top: refresh")
   [:div.pull {:style {:height (str (if (:refreshing s) 48 (:pull s)) "px")}}
    (cond (:refreshing s) "Refreshing…" (> (:pull s) 60) "Let go to refresh" (pos? (:pull s)) "Pull to refresh")]
   [:div.rows (map-indexed (fn [i r] (row-view s r i)) (:rows s))]
   [:div.row-of (btn :refresh "Refresh" s {:tap refresh!})]])

(defn- chips-tab [s]
  [:section
   (rule "Chip" "Tap: toggle" "Hold or right click: its menu (Rename, Delete)")
   [:div.chips
    (for [[c on] (:chips s)]
      [:button {:replicant/key c
                :class ["chip" (when on "on") (when (= [:chip c] (:pressed s)) "sunk")]
                :on (assoc (pressable [:chip c]
                                      {:tap #(do (swap! state update-in [:chips c] not) (log! (str "#" c ": tap → toggled")))
                                       :hold (fn [x y] (open-layer! :menu {:for c :x x :y y}) (log! (str "#" c ": hold → menu")))})
                           :contextmenu #(do (.preventDefault %)
                                             (open-layer! :menu {:for c :x (.-clientX %) :y (.-clientY %)})))}
       c])]
   (rule "Text" "Tap: places caret" "Hold: the browser's own select, untouched")
   [:input.field {:type "text" :placeholder "Type here" :inputmode "text" :enterkeyhint "done" :autocomplete "off"}]])

(defn- set-slider! [el x]
  (let [b (.getBoundingClientRect el)]
    (swap! state assoc :slider (-> (/ (- x (.-left b)) (.-width b)) (* 100) js/Math.round (max 0) (min 100)))))

(defn- controls-tab [s]
  [:section
   (rule "Slider" "Tap the track: jumps there" "Drag: moves the thumb; the page never scrolls meanwhile")
   [:div.slider {:on {:pointerdown (fn [e]
                                     (let [el (.-currentTarget e)]
                                       (set-slider! el (.-clientX e))
                                       ((gesture {:axis :x :claim-x true
                                                  :move (fn [_ _] nil)
                                                  :end (fn [_ _ _] (log! (str "Slider: set to " (:slider @state))))
                                                  :tap #(log! (str "Slider: tap → " (:slider @state)))}) e)
                                       (let [mv (fn [ev] (set-slider! el (.-clientX ev)))]
                                         (.addEventListener js/window "pointermove" mv)
                                         (.addEventListener js/window "pointerup"
                                                            #(.removeEventListener js/window "pointermove" mv) #js {:once true}))))}}
    [:div.track [:div.filled {:style {:width (str (:slider s) "%")}}]]
    [:div.thumb {:style {:left (str (:slider s) "%")}}]]
   [:div.value (str (:slider s))]
   (rule "Sheet" "Opens from the bottom" "Drag down the handle: closes" "Back: closes")
   [:div.row-of (btn :sheet2 "Open sheet" s {:tap #(open-layer! :sheet true)})]
   (rule "Tabs" "Tap a tab: switch" "Swipe the page sideways where nothing else takes it: next tab")])

(defn- menu-view [{:keys [for x y]}]
  [:div.scrim {:on {:pointerdown #(when (= (.-target %) (.-currentTarget %)) (close-layer!))}}
   [:div.menu {:style {:left (str (min x (- (.-innerWidth js/window) 180)) "px")
                       :top (str (min y (- (.-innerHeight js/window) 120)) "px")}}
    [:button {:on {:click #(do (log! (str "#" for ": Rename")) (close-layer!))}} "Rename"]
    [:button.danger-text {:on {:click #(do (log! (str "#" for ": Delete → asks first")) (close-layer!))}} "Delete"]]])

(defn- sheet-view [s]
  [:div.scrim {:on {:pointerdown #(when (= (.-target %) (.-currentTarget %)) (close-layer!))}}
   [:div.sheet {:style {:transform (str "translateY(" (max 0 (:sheet-dy s)) "px)")}}
    [:div.handle-area
     {:on {:pointerdown (gesture {:axis :y
                                  :move (fn [_ dy] (swap! state assoc :sheet-dy dy))
                                  :end (fn [_ dy _]
                                         (if (> dy 100)
                                           (do (log! "Sheet: dragged down → closed") (close-layer!))
                                           (swap! state assoc :sheet-dy 0)))})}}
     [:div.handle]]
    [:h3 "Sheet"]
    [:p "Drag the handle down, tap outside, or press back."]
    (btn :close "Close" s {:tap close-layer!})]])

(defn- tab-bar [s]
  [:nav.tabbar
   (for [[k label] tabs]
     [:button {:replicant/key k
               :class ["tab" (when (= k (:tab s)) "on")]
               :on {:click #(do (swap! state assoc :tab k) (log! (str "Tab: tap → " label)))}}
      label])])

(defn- next-tab [k step]
  (let [ks (mapv first tabs) i (.indexOf ks k) j (+ i step)]
    (when (< -1 j (count ks)) (ks j))))

(defn- page [s]
  [:div.app
   [:header.top [:h1 "Touch demo"]]
   [:main.content
    {:style {:transform (str "translateX(" (:tab-dx s) "px)")}
     :on {:pointerdown (gesture {:axis :x
                                 :move (fn [dx _] (swap! state assoc :tab-dx (* 0.5 dx)))
                                 :end (fn [dx _ v]
                                        (swap! state assoc :tab-dx 0)
                                        (when (or (> (js/Math.abs dx) 80) (> (js/Math.abs v) 0.6))
                                          (when-let [k (next-tab (:tab @state) (if (neg? dx) 1 -1))]
                                            (swap! state assoc :tab k)
                                            (log! (str "Page: swipe → " (name k))))))})
          :touchstart (fn [e]
                        (let [sc (.querySelector js/document ".content")]
                          (when (and (= :list (:tab @state)) (<= (.-scrollTop sc) 0))
                            (let [t (aget (.-touches e) 0)]
                              (swap! blk assoc :pull-start [(.-clientX t) (.-clientY t)])))))
          :touchend (fn [_]
                      (swap! blk dissoc :pull-start :pulling)
                      (if (> (:pull @state) 60) (refresh!) (swap! state assoc :pull 0)))}}
    (case (:tab s)
      :buttons (buttons-tab s)
      :list (list-tab s)
      :chips (chips-tab s)
      :controls (controls-tab s))]
   [:aside.log
    (if (empty? (:log s))
      [:div.muted "Gestures show here."]
      (for [[i l] (map-indexed vector (:log s))] [:div {:replicant/key (str i l) :class (when (zero? i) "latest")} l]))]
   (tab-bar s)
   (when (:menu s) (menu-view (:menu s)))
   (when (:sheet s) (sheet-view s))])

;; ---------------------------------------------------------------- boot

(defn- guard-touchmove [e]
  (let [b @blk]
    (cond
      (:lift b) (.preventDefault e)
      (:pull-start b)
      (let [t (aget (.-touches e) 0)
            [x0 y0] (:pull-start b)
            dx (- (.-clientX t) x0) dy (- (.-clientY t) y0)]
        (cond
          (:pulling b) (do (.preventDefault e) (swap! state assoc :pull (min 100 (* 0.5 dy))))
          (and (> dy slop) (> dy (js/Math.abs dx)) (not (:lift @state)))
          (do (.preventDefault e) (swap! blk assoc :pulling true))
          (> (js/Math.hypot dx dy) slop) (swap! blk dissoc :pull-start))))))

(defonce el (js/document.getElementById "app"))

(defn render! [] (r/render el (page @state)))

(defn ^:dev/after-load reload [] (render!))

(defn init []
  (add-watch state ::render (fn [_ _ _ _] (render!)))
  (.addEventListener js/document "touchmove" guard-touchmove #js {:passive false})
  (.addEventListener js/window "popstate" on-popstate)
  (render!))
