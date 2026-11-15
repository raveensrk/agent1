(ns demo.clock-dial-test
  (:require [clojure.test :refer [deftest is]]
            [demo.clock-dial :as cd]
            [demo.clock-dial-page :as page]))

(defn- run [actions]
  (reduce cd/act cd/blank actions))

(deftest three-picks-make-a-time
  (is (= (+ (* 21 60) 30) (cd/minutes (run [[:pick 9] [:pick 30] [:pick 1]]))))
  (is (= 0 (cd/minutes (run [[:pick 0] [:pick 0] [:pick 0]]))) "12:00 AM is midnight")
  (is (= 720 (cd/minutes (run [[:pick 0] [:pick 0] [:pick 1]]))) "12:00 PM is noon")
  (is (nil? (cd/minutes (run [[:pick 9] [:pick 30]])))))

(deftest steps-advance-and-go-back
  (is (= 1 (:step (run [[:pick 3]]))))
  (is (= 0 (:step (run [[:pick 3] [:back]]))))
  (is (= 3 (:cursor (run [[:pick 3] [:back]]))) "back keeps the hour")
  (is (= 0 (:step (run [[:back]])))))

(deftest keys-turn-the-hand
  (is (= 10 (:cursor (run [[:next]]))))
  (is (= 0 (:cursor (run [[:next] [:next] [:next]]))) "wraps past 11 to 12")
  (is (= 59 (:cursor (run [[:pick 9] [:prev]]))) "back from :00 is :59"))

(deftest angle-picks-the-option
  (is (= 0 (cd/index-at 0 cd/mid 10)) "top is 12")
  (is (= 3 (cd/index-at 0 250 cd/mid)) "right is 3")
  (is (= 9 (cd/index-at 0 10 cd/mid)) "left is 9")
  (is (= 30 (cd/index-at 1 cd/mid 250)) "bottom is :30")
  (is (= 15 (cd/index-at 1 250 cd/mid)) "right is :15")
  (is (= 0 (cd/index-at 2 cd/mid 50)) "top half is AM")
  (is (= 1 (cd/index-at 2 cd/mid 200)) "bottom half is PM"))

(defn- frames
  "Each anim, one 60 Hz frame apart, until it rests."
  [anim dial]
  (take-while some? (iterate #(cd/tick % dial (/ 1 60.0)) anim)))

(deftest the-hand-sweeps-the-short-way
  (let [dial (assoc cd/blank :cursor 0)
        a (cd/tick (assoc (cd/still dial) :angle 330.0) dial (/ 1 60.0))]
    (is (< 330.0 (:angle a) 360.0) "330 to 0 goes forward, not back round")))

(deftest a-pick-sweeps-rests-fades-out-then-in
  (let [before cd/blank
        after (cd/act before [:pick 3])
        start (cd/begin (cd/still before) before after 3)
        fs (frames start after)
        phases (dedupe (map :phase fs))]
    (is (= [:sweep :hold :out :in :idle] phases))
    (is (= 90.0 (:angle (first (filter #(= :hold (:phase %)) fs)))) "hand lands on 3 first")
    (is (= 1 (:step (:shown (last fs)))) "then the minute step shows")
    (is (< 0.9 (/ (count fs) 60.0) 2.5) "slow: about a second or more, under 2.5 s")
    (is (nil? (cd/tick (last fs) after (/ 1 60.0))) "at rest it draws nothing more")))

(deftest any-minute-can-be-picked
  (is (= (+ 600 37) (cd/minutes (run [[:pick 10] [:pick 37] [:pick 0]]))) "10:37 AM")
  (is (= 1 (:cursor (run [[:pick 10] [:next]]))) "arrows step one minute"))

(deftest a-time-shows-on-the-dial
  (is (= ["9" "30" "PM"] (:vals (cd/from-minutes 1290))))
  (is (= ["9" "07" "AM"] (:vals (cd/from-minutes 547))) "any minute, 9:07"))

(deftest the-page-writes-at-am-pm
  (let [s (reduce page/step page/start-state [[:pick 9] [:pick 30] [:pick 1]])]
    (is (= 1290 (:time s)))
    (is (= 1 (:writes s)))
    (is (= "9:30 PM" (page/show-time (:time s))))))
