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

(defn- settle
  "A wheel run frame by frame at 60 Hz until it rests: [wheel seconds]."
  [spec w calm]
  (loop [w w n 0]
    (if-let [w' (and (< n 2000) (t/tick spec w (/ 1 60.0) calm))]
      (recur w' (inc n))
      [w (/ n 60.0)])))

(def specs12 (t/wheel-specs false))
(def specs24 (t/wheel-specs true))

(deftest the-wheels-suit-the-clock
  (is (= [:h :m :p] (map :key specs12)))
  (is (= ["12" "1" "11"] (map (:opts (first specs12)) [0 1 11])))
  (is (= 60 (count (:opts (second specs12)))))
  (is (= ["AM" "PM"] (:opts (nth specs12 2))))
  (is (= [:h :m] (map :key specs24)))
  (is (= ["00" "23"] (map (:opts (first specs24)) [0 23]))))

(deftest the-wheels-show-a-time-and-read-it-back
  (is (= [9 30 1] (t/rows-for 1290 false)))
  (is (= [0 0 0] (t/rows-for 0 false)) "midnight: 12, 00, AM")
  (is (= [0 0 1] (t/rows-for 720 false)) "noon: 12, 00, PM")
  (is (= [21 30] (t/rows-for 1290 true)))
  (doseq [m [0 1 59 547 720 1290 1439]]
    (is (= m (t/wheels-time specs12 (t/rows-for m false) false)))
    (is (= m (t/wheels-time specs24 (t/rows-for m true) true))))
  (is (= 601 (t/after-now 600)) "from an empty field, the next whole minute")
  (is (= 0 (t/after-now 1439))))

(deftest hour-and-minute-go-round-am-pm-stops
  (let [[h m p] specs12]
    (is (= "59" ((:opts m) (t/row-at m -1))) "Up from 00 is 59")
    (is (= "12" ((:opts h) (t/row-at h (dec 1)))) "Up from 1 is 12")
    (is (= "11" ((:opts h) (t/row-at h -1))) "and on to 11")
    (is (= "PM" ((:opts p) (t/row-at p 5))))
    (is (= "59" ((:opts m) (t/row-at m (:target (t/turn m (t/wheel-at 0) -1))))) "a wheel that loops turns past its first row")
    (is (= 1.0 (:target (t/turn p (t/wheel-at 1) 1))) "AM/PM stops at its end")))

(deftest a-typed-time-turns-the-short-way
  (let [m (second specs12)]
    (is (= -1.0 (t/nearest m 0.0 59)) "00 to 59 goes back one row, not round")
    (is (= 62.0 (t/nearest m 58.0 2)))))

(deftest a-fling-coasts-then-settles-on-a-row
  (let [m (second specs12)
        [w s] (settle m (assoc (t/wheel-at 10) :vel 12.0) false)]
    (is (== (:offset w) (Math/rint (:offset w))) "on a whole row")
    (is (< 12 (:offset w) 17) "a few rows on")
    (is (< 0.5 s 4.0))))

(deftest a-turn-eases-onto-its-row-in-250-ms
  (let [m (second specs12)
        [w s] (settle m (t/turn m (t/wheel-at 10) 1) false)]
    (is (= 11.0 (:offset w)))
    (is (<= s 0.25) (str s " s"))))

(deftest a-scroll-settles-once-it-stops
  (let [m (second specs12)
        w (t/scroll m (t/wheel-at 10) -20.0)
        [rest s] (settle m w false)]
    (is (< 10.0 (:offset w) 11.0) "it turns with the scroll")
    (is (= 11.0 (:offset rest)))
    (is (< s 0.3) "settled within 300 ms")))

(deftest am-pm-springs-back-past-its-end
  (let [p (nth specs12 2)
        w (t/drag p (t/press (t/wheel-at 0) 100.0 0.0) 130.0 0.5)
        w (t/release p w 130.0 1.0)
        [rest] (settle p w false)]
    (is (neg? (:offset w)) "pulled a little past AM")
    (is (= 0.0 (:offset rest)))))

(deftest a-click-brings-its-row-to-the-band
  (let [m (second specs12)
        y (+ (/ t/wheels-h 2) t/row-h)
        w (t/release m (t/press (t/wheel-at 10) y 0.0) y 0.1)]
    (is (= 11.0 (:target w)))))

(deftest under-reduce-motion-a-turn-lands-at-once
  (let [m (second specs12)]
    (is (= 11.0 (:offset (t/tick m (t/turn m (t/wheel-at 10) 1) (/ 1 60.0) true))) "in one frame")
    (is (= 13.0 (:offset (t/tick m (assoc (t/wheel-at 10) :offset 12.6 :vel 9.0) (/ 1 60.0) true))) "a fling too")))

(deftest the-wheels-stay-whole-in-the-window
  (let [field {:x 24.0 :top 100.0 :bottom 144.0}]
    ;; Under the field, 4 px from it.
    (is (= {:x 24.0 :y 148.0 :over false} (t/wheels-place field 210.0 176.0 560.0 520.0)))
    ;; With no room under, over it.
    (is (= {:x 24.0 :y 220.0 :over true}
           (t/wheels-place {:x 24.0 :top 400.0 :bottom 444.0} 210.0 176.0 560.0 520.0)))
    ;; Near the side it slides in, 4 px clear.
    (is (= 346.0 (:x (t/wheels-place (assoc field :x 500.0) 210.0 176.0 560.0 520.0))))))

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
