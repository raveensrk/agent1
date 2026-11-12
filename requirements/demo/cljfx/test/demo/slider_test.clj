(ns demo.slider-test
  (:require [clojure.test :refer [deftest is]]
            [demo.slider :as s]
            [demo.slider-page :as p]))

(def ends {:min 0.0 :max 100.0})
;; 228 px wide: the middle of the thumb runs 200 px, from 14 to 214.
(def width 228.0)

(deftest the-thumb-runs-from-end-to-end
  (is (= 14.0 (s/x-of ends width 0.0)))
  (is (= 114.0 (s/x-of ends width 50.0)))
  (is (= 214.0 (s/x-of ends width 100.0)))
  (is (= 25.0 (s/value-at ends width 64.0))))

(deftest past-an-end-it-stops-there
  (is (= 0.0 (s/value-at ends width -300.0)))
  (is (= 100.0 (s/value-at ends width 900.0))))

(deftest it-snaps-to-the-default-within-4-px
  (let [model (assoc ends :default 50.0)]
    (is (= 50.0 (s/value-at model width 117.0)))
    (is (= 50.0 (s/value-at model width 110.0)))
    (is (not= 50.0 (s/value-at model width 120.0)))
    ;; With no default there is nothing to snap to.
    (is (not= 50.0 (s/value-at ends width 117.0)))))

(deftest keys-move-it-1-percent-and-10-with-shift
  (is (= 21.0 (s/key-value ends 20.0 :right false)))
  (is (= 21.0 (s/key-value ends 20.0 :up false)))
  (is (= 19.0 (s/key-value ends 20.0 :left false)))
  (is (= 19.0 (s/key-value ends 20.0 :down false)))
  (is (= 30.0 (s/key-value ends 20.0 :right true)))
  (is (= 0.0 (s/key-value ends 20.0 :home false)))
  (is (= 100.0 (s/key-value ends 20.0 :end false)))
  ;; 1% of the range, whatever the range is.
  (is (= -11.5 (s/key-value {:min -12.0 :max 38.0} -12.0 :right false))))

(deftest a-key-never-passes-an-end
  (is (= 0.0 (s/key-value ends 0.0 :left false)))
  (is (= 100.0 (s/key-value ends 95.0 :right true))))

(deftest the-thumb-grows-held-and-stretches-moving
  (is (= {:scale 1.1} (s/thumb-look {:held true :reduce false})))
  (is (= {:scale 1.0} (s/thumb-look {:held false :reduce false})))
  (is (= 0.0 (s/stretch-for 0.0 false)))
  (is (< 0.0 (s/stretch-for 0.2 false) (s/stretch-for 0.6 false)))
  ;; Never wider than 36 px, however fast.
  (is (= 8.0 (s/stretch-for 50.0 false)))
  (is (= 36.0 (+ s/thumb-w s/stretch-max))))

(deftest reduce-motion-neither-grows-nor-stretches
  (is (= {:scale 1.0} (s/thumb-look {:held true :reduce true})))
  (is (= 0.0 (s/stretch-for 50.0 true))))

(deftest the-bubble-stays-whole
  ;; Centred over the thumb, away from an edge.
  (is (= 76.0 (s/bubble-left 100.0 48.0 0.0 500.0)))
  ;; Near an edge it slides sideways, 4 px clear of it.
  (is (= 4.0 (s/bubble-left 10.0 48.0 0.0 500.0)))
  (is (= 448.0 (s/bubble-left 495.0 48.0 0.0 500.0))))

(deftest a-screen-reader-is-told-the-value-in-the-name
  (is (= {:name "Volume, 40%" :kind nil} (s/said {:name "Volume" :unit "%"} 40.2)))
  ;; A slider that is off is called dimmed, and says why.
  (is (= {:name "Volume. Muted." :kind "dimmed slider"}
         (s/said {:name "Volume" :unit "%" :disabled true :tip "Muted."} 40.0)))
  ;; The tooltip says the value, or why the slider is off.
  (is (= "Volume: 40%" (s/tip-text {:name "Volume" :unit "%"} 40.0)))
  (is (= "Muted." (s/tip-text {:name "Volume" :unit "%" :disabled true :tip "Muted."} 40.0))))

(deftest what-it-sets-follows-live-and-is-written-once
  (let [moved (p/live p/start-state :brightness 64.0)]
    (is (= {:value 20.0 :live 64.0} (get-in moved [:sliders :brightness])))
    (is (= 0 (:writes moved)))
    (let [kept (p/write moved :brightness 64.0 false)]
      (is (= {:value 64.0 :live 64.0} (get-in kept [:sliders :brightness])))
      (is (= 1 (:writes kept))))))

(deftest one-drag-is-one-step-for-undo
  (let [once (p/write p/start-state :brightness 64.0 false)]
    (is (= [[:brightness 20.0]] (:undo once)))
    (is (= {:value 20.0 :live 20.0} (get-in (p/undo once) [:sliders :brightness])))
    (is (= [] (:undo (p/undo once))))
    ;; With nothing to take back, Undo changes nothing.
    (is (= p/start-state (p/undo p/start-state)))))

(deftest writes-of-one-step-are-taken-back-together
  (let [keys (-> p/start-state
                 (p/write :brightness 21.0 false)
                 (p/write :brightness 22.0 true)
                 (p/write :brightness 23.0 true))]
    (is (= 1 (count (:undo keys))))
    (is (= 20.0 (get-in (p/undo keys) [:sliders :brightness :value])))
    ;; A write to another slider is never part of this one's step.
    (is (= 2 (count (:undo (p/write keys :volume 31.0 true)))))))
