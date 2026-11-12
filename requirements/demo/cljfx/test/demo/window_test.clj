(ns demo.window-test
  (:require [clojure.test :refer [deftest is]]
            [demo.window :as w]))

(deftest a-pane-stays-within-its-limits
  (is (= 160.0 (w/clamp-size :sidebar 10)))
  (is (= 320.0 (w/clamp-size :sidebar 999)))
  (is (= 250.0 (w/clamp-size :sidebar 250))))

(deftest a-narrow-window-shrinks-the-sidebar-and-hides-the-inspector
  (is (= {:narrow false :sidebar :full :inspector true}
         (w/layout {:width 960 :sidebar-shown true :inspector-shown true})))
  (is (= {:narrow true :sidebar :icons :inspector false}
         (w/layout {:width 719 :sidebar-shown true :inspector-shown true})))
  (is (= :full (:sidebar (w/layout {:width 720 :sidebar-shown true :inspector-shown true})))))

(deftest a-pane-the-user-hid-stays-hidden
  (is (= :hidden (:sidebar (w/layout {:width 960 :sidebar-shown false :inspector-shown true}))))
  (is (= :hidden (:sidebar (w/layout {:width 600 :sidebar-shown false :inspector-shown true}))))
  (is (false? (:inspector (w/layout {:width 960 :sidebar-shown true :inspector-shown false})))))

(deftest the-page-keeps-its-room
  (let [wide {:narrow false :sidebar :full :inspector true}
        sizes {:sidebar 320.0 :inspector 360.0 :bottom 140.0}]
    (is (= {:sidebar 320.0 :inspector 360.0} (w/fit 1200 wide sizes)))
    ;; 760 wide: the inspector gives way first, down to its smallest.
    (is (= {:sidebar 280.0 :inspector 200.0} (w/fit 760 wide sizes)))
    (is (<= (+ 280.0 200.0 w/content-min-width) 760))
    (is (= {:sidebar 56.0 :inspector 0.0}
           (w/fit 600 {:narrow true :sidebar :icons :inspector false} sizes)))))

(deftest tabs-open-close-and-move
  (let [s (-> w/start-state
              (w/step {:event :new-tab :window 1})
              (w/step {:event :new-tab :window 1}))
        tabs #(mapv :id (get-in % [:windows 1 :tabs]))
        active #(get-in % [:windows 1 :active])]
    (is (= [1 2 3] (tabs s)))
    (is (= 3 (active s)))
    ;; Closing the last tab in the row moves to the one before it.
    (is (= 2 (active (w/step s {:event :close-tab :window 1}))))
    ;; Closing one in the middle moves to the one that takes its place.
    (is (= 3 (active (w/step (w/step s {:event :select-tab :window 1 :tab 2})
                             {:event :close-tab :window 1}))))
    ;; Closing a tab that is not the active one leaves the active one alone.
    (is (= 3 (active (w/step s {:event :close-tab :window 1 :tab 1}))))
    (is (= 1 (active (w/step s {:event :next-tab :window 1 :by 1}))))
    (is (= 2 (active (w/step s {:event :next-tab :window 1 :by -1}))))))

(deftest each-tab-keeps-its-own-page
  (let [s (-> w/start-state
              (w/step {:event :select-page :window 1 :page :notes})
              (w/step {:event :new-tab :window 1})
              (w/step {:event :select-page :window 1 :page :tags}))]
    (is (= [:notes :tags] (mapv :page (get-in s [:windows 1 :tabs]))))))

(deftest closing-the-last-tab-closes-the-window
  (let [s (w/step w/start-state {:event :new-window})]
    (is (= [1 2] (:order s)))
    (is (= [2] (:order (w/step s {:event :close-tab :window 1}))))
    (is (= [1] (:order (w/step s {:event :close-window :window 2}))))))

(deftest each-window-has-its-own-tabs
  (let [s (-> w/start-state
              (w/step {:event :new-window})
              (w/step {:event :new-tab :window 2}))]
    (is (= 1 (count (get-in s [:windows 1 :tabs]))))
    (is (= 2 (count (get-in s [:windows 2 :tabs]))))))

(deftest a-divider-follows-the-pointer-within-the-limits
  (let [drag #(get-in (w/step w/start-state (merge {:event :drag :w 960.0 :h 572.0 :edge 12.5} %)) [:sizes (:pane %)])]
    (is (= 287.5 (drag {:pane :sidebar :x 300.0})))
    (is (= 320.0 (drag {:pane :sidebar :x 900.0})))
    (is (= 160.0 (drag {:pane :sidebar :x 10.0})))
    (is (= 247.5 (drag {:pane :inspector :x 700.0})))
    (is (= 159.5 (drag {:pane :bottom :y 400.0})))
    (is (= 220.0 (get-in (w/step (assoc-in w/start-state [:sizes :sidebar] 300.0)
                                 {:event :reset-size :pane :sidebar})
                         [:sizes :sidebar])))))

(deftest a-floating-window-stays-inside-its-window
  (let [f {:id 1 :page :inbox :x 40.0 :y 40.0 :w 260.0 :h 160.0}]
    (is (= f (w/clamp-float f [900.0 500.0])))
    ;; Dragged past the right and bottom edges, it stops at them.
    (is (= [640.0 340.0] ((juxt :x :y) (w/clamp-float (assoc f :x 2000.0 :y 2000.0) [900.0 500.0]))))
    (is (= [0.0 0.0] ((juxt :x :y) (w/clamp-float (assoc f :x -50.0 :y -50.0) [900.0 500.0]))))
    ;; No smaller and no larger than its limits.
    (is (= [200.0 120.0] ((juxt :w :h) (w/clamp-float (assoc f :w 10.0 :h 10.0) [900.0 500.0]))))
    (is (= [480.0 360.0] ((juxt :w :h) (w/clamp-float (assoc f :w 999.0 :h 999.0) [900.0 500.0]))))
    ;; Before the window's room is known, only the limits apply.
    (is (= 2000.0 (:x (w/clamp-float (assoc f :x 2000.0) nil))))))

(deftest floating-windows-open-drag-front-and-close
  (let [floats #(get-in % [:windows 1 :floats])
        s (-> w/start-state
              (w/step {:event :layer-resized :window 1 :w 900.0 :h 500.0})
              (w/step {:event :select-page :window 1 :page :notes})
              (w/step {:event :new-float :window 1})
              (w/step {:event :new-float :window 1}))]
    (is (= [1 2] (mapv :id (floats s))))
    ;; Each opens on the page its tab was on, a step away from the last.
    (is (= [:notes :notes] (mapv :page (floats s))))
    ;; Across the middle of a 900 px room, under the toolbar.
    (is (= [[320.0 90.0] [348.0 118.0]] (mapv (juxt :x :y) (floats s))))
    ;; A press on the first brings it to the front: the last of the list.
    (let [pressed (w/step s {:event :float-press :window 1 :float 1 :px 330.0 :py 100.0})]
      (is (= [2 1] (mapv :id (floats pressed))))
      ;; It then follows the pointer, held where it was taken hold of.
      (is (= [300.0 200.0] ((juxt :x :y) (last (floats (w/step pressed {:event :float-drag :window 1 :float 1 :px 310.0 :py 210.0}))))))
      (is (= [640.0 340.0] ((juxt :x :y) (last (floats (w/step pressed {:event :float-drag :window 1 :float 1 :px 5000.0 :py 5000.0})))))))
    (is (= [340.0 200.0] ((juxt :w :h) (last (floats (w/step s {:event :float-resize :window 1 :float 2 :px 688.0 :py 318.0}))))))
    (is (= [2] (mapv :id (floats (w/step s {:event :close-float :window 1 :float 1})))))
    ;; The window shrinks: none is drawn outside it, and the place each was
    ;; left at is kept, so it goes back there when there is room again.
    (let [far (-> s
                  (w/step {:event :float-press :window 1 :float 2 :px 350.0 :py 120.0})
                  (w/step {:event :float-drag :window 1 :float 2 :px 5000.0 :py 5000.0}))
          small (w/step far {:event :layer-resized :window 1 :w 500.0 :h 400.0})
          drawn (map #(w/clamp-float % (get-in small [:windows 1 :layer])) (floats small))]
      (is (every? #(and (<= (+ (:x %) (:w %)) 500.0) (<= (+ (:y %) (:h %)) 400.0)) drawn))
      (is (= (floats far) (floats small)))
      ;; A room that is briefly tiny, as a window opens, moves nothing for good.
      (is (= (floats far) (floats (w/step far {:event :layer-resized :window 1 :w 0.0 :h 0.0}))))
      ;; Taken hold of while squeezed in, where it is drawn becomes its place.
      (is (= [240.0 240.0]
             ((juxt :x :y) (last (floats (w/step small {:event :float-press :window 1 :float 2 :px 250.0 :py 250.0})))))))
    (is (= [200.0 120.0] ((juxt :w :h) (w/clamp-float {:x 0.0 :y 0.0 :w 260.0 :h 160.0} [50.0 50.0]))))
    ;; Another window has none of them.
    (is (= [] (get-in (w/step s {:event :new-window}) [:windows 2 :floats])))))

(def one-screen [{:x 0.0 :y 25.0 :width 1512.0 :height 900.0}])

(deftest a-session-comes-back-as-it-was-left
  (let [left (-> w/start-state
                 (w/step {:event :resized :window 1 :dim :x :value 300.0})
                 (w/step {:event :resized :window 1 :dim :width :value 1100.0})
                 (w/step {:event :select-page :window 1 :page :notes})
                 (w/step {:event :new-tab :window 1})
                 (w/step {:event :select-page :window 1 :page :tags})
                 (w/step {:event :select-tab :window 1 :tab 1})
                 (w/step {:event :new-float :window 1})
                 (w/step {:event :toggle-inspector})
                 (w/step {:event :new-window}))
        kept (w/session left)
        back (w/restore kept one-screen)]
    ;; Plain data, and the same after a trip through text.
    (is (= kept (read-string (pr-str kept))))
    (is (= kept (w/session back)))
    (is (= [1 2] (:order back)))
    (is (= {:x 300.0 :y 120.0 :width 1100.0 :height 600.0} (get-in back [:windows 1 :open])))
    (is (= [:notes :tags] (mapv :page (get-in back [:windows 1 :tabs]))))
    (is (= :notes (:page (first (filter #(= (get-in back [:windows 1 :active]) (:id %))
                                        (get-in back [:windows 1 :tabs]))))))
    (is (= 1 (count (get-in back [:windows 1 :floats]))))
    (is (false? (:inspector-shown back)))
    ;; The panes' sizes are part of it: one file, not two.
    (is (= w/default-sizes (:sizes kept) (:sizes back)))
    ;; Ids are the run's own, and none is used twice.
    (is (apply distinct? (mapcat #(map :id (:tabs %)) (vals (:windows back)))))))

(deftest nothing-in-a-kept-session-is-trusted
  (let [open #(get-in (w/restore {:windows [%]} one-screen) [:windows 1 :open])]
    ;; Off every screen: back at the place a first window opens.
    (is (= {:x 120.0 :y 120.0 :width 960.0 :height 600.0}
           (open {:x 9000.0 :y 9000.0 :width 960.0 :height 600.0})))
    ;; Too small: back at the smallest size.
    (is (= {:width 480.0 :height 400.0}
           (select-keys (open {:x 200.0 :y 200.0 :width 10.0 :height 10.0}) [:width :height])))
    (is (= {:x 120.0 :y 120.0 :width 960.0 :height 600.0} (open {:x "left" :width nil})))
    ;; A page no longer known, no tabs at all, a front tab that is not there.
    (is (= [:inbox :notes] (mapv :page (get-in (w/restore {:windows [{:pages [:gone :notes] :front 9}]} one-screen)
                                               [:windows 1 :tabs]))))
    (is (= [:inbox] (mapv :page (get-in (w/restore {:windows [{}]} one-screen) [:windows 1 :tabs]))))
    (is (= [480.0 360.0] ((juxt :w :h) (first (get-in (w/restore {:windows [{:floats [{:w 9999 :h 9999}]}]} one-screen)
                                                      [:windows 1 :floats])))))
    ;; A pane's size outside its limits, not a number, or not kept at all.
    (is (= {:sidebar 320.0 :inspector 260.0 :bottom 140.0}
           (:sizes (w/restore {:windows [{}] :sizes {:sidebar 999 :inspector "wide"}} one-screen))))
    ;; No window to open, or not a session at all: nothing to restore.
    (is (nil? (w/restore {:windows []} one-screen)))
    (is (nil? (w/restore "nonsense" one-screen)))
    (is (nil? (w/restore nil one-screen)))))

(deftest a-window-counts-as-on-a-screen-when-its-title-bar-can-be-reached
  (is (w/on-a-screen? {:x 100.0 :y 100.0 :width 960.0} one-screen))
  (is (w/on-a-screen? {:x -800.0 :y 100.0 :width 960.0} one-screen))
  (is (not (w/on-a-screen? {:x -900.0 :y 100.0 :width 960.0} one-screen)))
  (is (not (w/on-a-screen? {:x 100.0 :y 2000.0 :width 960.0} one-screen)))
  (is (not (w/on-a-screen? {:x 100.0 :y 100.0 :width 960.0} []))))
