(ns demo.wheel-picker-test
  (:require [clojure.test :refer [deftest is]]
            [demo.compare-page :as page]
            [demo.wheel-picker :as wp]))

(def hours (first wp/wheels))
(def mins (second wp/wheels))
(def halves (nth wp/wheels 2))

(defn- settle
  "A wheel run frame by frame at 60 Hz until it rests; [wheel seconds]."
  [spec w]
  (loop [w w n 0]
    (if-let [w' (and (< n 2000) (wp/tick spec w (/ 1 60.0)))]
      (recur w' (inc n))
      [w (/ n 60.0)])))

(deftest the-start-reads-9-00-am
  (is (= 540 (wp/minutes wp/start)))
  (is (wp/at-rest? wp/start)))

(deftest a-fling-coasts-then-snaps-onto-a-row
  (let [[w s] (settle hours (assoc (wp/wheel-at 9) :vel 12.0))]
    (is (== (:offset w) (Math/round (:offset w))) "rests on a whole row")
    (is (< 11 (:offset w) 16) "coasts a few rows past where it was let go")
    (is (< 0.5 s 4.0) "slows over a second or two")))

(deftest the-hour-wheel-loops
  (is (= "1" (get (:opts hours) (wp/index hours (wp/wheel-at 13))))))

(deftest the-minute-wheel-holds-every-minute-and-loops
  (is (= 60 (count (:opts mins))))
  (is (= "37" (get (:opts mins) (wp/index mins (wp/wheel-at 37)))))
  (is (= "01" (get (:opts mins) (wp/index mins (wp/wheel-at 61)))) "59 runs on to 00, 01"))

(deftest the-am-pm-wheel-stops-at-its-ends
  (let [[w] (settle halves (assoc (wp/wheel-at 0) :vel 30.0))]
    (is (= 1.0 (:offset w)) "PM is the last row"))
  (let [[w] (settle halves (assoc (wp/wheel-at 0) :offset -0.3 :quiet 1.0))]
    (is (= 0.0 (:offset w)) "pulled past AM springs back")))

(deftest a-scroll-snaps-once-it-goes-quiet
  (let [w (assoc (wp/wheel-at 9) :offset 9.4 :quiet 0.0)
        [rest] (settle hours w)]
    (is (some? (wp/tick hours w (/ 1 60.0))) "waits, still moving")
    (is (= 9.0 (:offset rest)))))

(deftest a-click-below-the-band-picks-the-next-row
  (is (= 10.0 (wp/snap-to hours (wp/row-under 9.0 (+ wp/mid wp/row-h))))))

(deftest the-page-writes-when-the-wheels-rest
  (let [s (assoc page/start-state :wheels (assoc wp/start :p (assoc (wp/wheel-at 1) :offset 0.6 :quiet 1.0)))
        s (nth (iterate #(page/advance % (/ 1 60.0)) s) 120)]
    (is (= 1260 (:wheel-time s)) "9:00 PM")
    (is (= 1 (:wheel-writes s)))))
