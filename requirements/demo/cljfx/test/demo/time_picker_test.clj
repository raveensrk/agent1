(ns demo.time-picker-test
  (:require [clojure.test :refer [deftest is]]
            [demo.time-picker :as t]
            [demo.time-picker-page :as p]))

(defn- taken [text] (:time (t/parse text false)))

(deftest what-is-typed-is-read-forgivingly
  (is (= 540 (taken "9a")))
  (is (= 570 (taken "930a")))
  (is (= 570 (taken "9:30 am")))
  (is (= 1290 (taken "9.30p")))
  (is (= 1260 (taken "9p")))
  (is (= 1290 (taken "2130")))
  (is (= 1290 (taken "21:30")))
  (is (= 720 (taken "noon")))
  (is (= 0 (taken "midnight")))
  ;; In either case, with or without a space.
  (is (= 1290 (taken " 9:30 PM ")))
  (is (= 1290 (taken "9:30pm")))
  (is (= 720 (taken "12p")))
  (is (= 0 (taken "12a"))))

(deftest an-hour-with-no-am-or-pm-is-never-guessed-at
  (is (= {:error :am-pm :hour 3 :minute nil} (t/parse "3" false)))
  (is (= {:error :am-pm :hour 3 :minute 30} (t/parse "3:30" false)))
  (is (= {:error :am-pm :hour 9 :minute 30} (t/parse "930" false)))
  (is (= :am-pm (:error (t/parse "12" false))))
  (is (= :am-pm (:error (t/parse "930" false))))
  (is (= "AM or PM? Type 3a or 3p" (t/error-text (t/parse "3:30" false)))))

(deftest hours-of-the-24-hour-clock-stand
  (is (= 780 (taken "13")))
  (is (= 0 (taken "0")))
  (is (= 1439 (taken "2359")))
  ;; On a 24-hour clock every hour is taken as it stands.
  (is (= {:time 180} (t/parse "3" true)))
  (is (= {:time 570} (t/parse "9:30" true)))
  ;; AM and PM are still taken there.
  (is (= {:time 1260} (t/parse "9p" true))))

(deftest what-is-not-a-time-is-not-taken
  (doseq [text ["abc" "25" "9:75" "13p" "0a" "12345" "9:3" "9 30"]]
    (is (= {:error :not-a-time} (t/parse text false)) text))
  (is (= "Not a time. Try 9:30 or 2130" (t/error-text {:error :not-a-time})))
  (is (= {:empty true} (t/parse "  " false))))

(deftest a-time-is-shown-in-full
  (is (= "9:30 AM" (t/show 570 false)))
  (is (= "9:05 PM" (t/show 1265 false)))
  (is (= "09:30" (t/show 570 true)))
  (is (= "21:00" (t/show 1260 true)))
  ;; Twelve o'clock is shown with its word, on a 12-hour clock.
  (is (= "12:00 PM, noon" (t/show 720 false)))
  (is (= "12:00 AM, midnight" (t/show 0 false)))
  (is (= "12:15 PM" (t/show 735 false)))
  (is (= "12:00" (t/show 720 true)))
  ;; What the field shows is read back as the same time.
  (doseq [m [0 570 720 735 1265]]
    (is (= m (taken (t/show m false))))
    (is (= m (:time (t/parse (t/show m true) true))))))

(deftest the-list-holds-the-day-in-15-minute-steps
  (let [{:keys [rows mark]} (t/offer {:typed false :value 570 :now 600})]
    (is (= 96 (count rows)))
    (is (= [0 15 30] (take 3 rows)))
    (is (= 570 (nth rows mark))))
  ;; A time on no step is in the list all the same, and marked.
  (let [{:keys [rows mark]} (t/offer {:typed false :value 577 :now 600})]
    (is (= 97 (count rows)))
    (is (= 577 (nth rows mark))))
  ;; From an empty field, the step after now.
  (let [{:keys [rows mark]} (t/offer {:typed false :value nil :now 600})]
    (is (= 615 (nth rows mark))))
  (is (= 615 (t/after-now 607)))
  (is (= 0 (t/after-now 1439))))

(deftest typing-narrows-the-list
  ;; An hour alone: both halves of the day, afternoon first, neither marked.
  (is (= {:rows [840 855 870 885 120 135 150 165] :mark nil}
         (t/offer {:typed true :text "2" :now 600})))
  ;; A whole time is the first row, and marked, though it is on no step.
  (is (= {:rows [847 840 855 870 885] :mark 0}
         (t/offer {:typed true :text "207p" :now 600})))
  (is (= {:rows [840 855 870 885] :mark 0}
         (t/offer {:typed true :text "2p" :now 600})))
  (is (= {:rows [870 150] :mark nil} (t/offer {:typed true :text "2:30" :now 600})))
  (is (= {:rows [870 150] :mark nil} (t/offer {:typed true :text "2:3" :now 600})))
  (is (= {:rows [720 735 750 765 0 15 30 45] :mark nil}
         (t/offer {:typed true :text "12" :now 600})))
  (is (= {:rows [720] :mark nil} (t/offer {:typed true :text "no" :now 600})))
  (is (= {:rows [] :mark nil} (t/offer {:typed true :text "abc" :now 600})))
  ;; Emptied by hand, it is the whole day again, with nothing marked.
  (is (= {:rows t/steps :mark nil} (t/offer {:typed true :text "" :now 600})))
  ;; On a 24-hour clock an hour stands, so there is one half.
  (is (= {:rows [120 135 150 165] :mark 0}
         (t/offer {:typed true :text "2" :now 600 :h24 true}))))

(deftest the-marked-row-opens-in-the-middle
  ;; Row 38 of 96, eight seen: 3.5 rows above it.
  (is (= (* 34.5 t/row-h) (t/offset-for 38 96)))
  ;; Never past either end.
  (is (= 0.0 (t/offset-for 1 96)))
  (is (= (* 88 t/row-h) (t/offset-for 95 96)))
  (is (= 0.0 (t/offset-for 3 5))))

(deftest the-list-stays-whole-in-the-window
  (let [field {:x 24.0 :top 100.0 :bottom 144.0}]
    ;; Under the field, 4 px from it.
    (is (= {:x 24.0 :y 148.0 :over false} (t/list-place field 190.0 264.0 560.0 520.0)))
    ;; With no room under, over it.
    (is (= {:x 24.0 :y 132.0 :over true}
           (t/list-place {:x 24.0 :top 400.0 :bottom 444.0} 190.0 264.0 560.0 520.0)))
    ;; Near the side it slides in, 4 px clear.
    (is (= 366.0 (:x (t/list-place (assoc field :x 500.0) 190.0 264.0 560.0 520.0))))))

(deftest one-taken-time-is-one-step-for-undo
  (let [once (p/write p/start-state :starts 600)]
    (is (= 600 (get-in once [:times :starts])))
    (is (= 1 (:writes once)))
    (is (= [[:starts 570]] (:undo once)))
    (is (= 570 (get-in (p/undo once) [:times :starts])))
    ;; An emptied field is taken back to its time, and a set one to empty.
    (is (= nil (get-in (p/undo (p/write p/start-state :ends 600)) [:times :ends])))
    ;; With nothing to take back, Undo changes nothing.
    (is (= p/start-state (p/undo p/start-state)))))
