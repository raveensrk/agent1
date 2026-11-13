(ns demo.scroll-test
  (:require [clojure.test :refer [deftest is]]
            [demo.scroll :as s]
            [demo.scroll-page :as p]))

(deftest content-that-fits-does-not-scroll
  (is (not (s/needs? 300.0 300.0)))
  (is (s/needs? 301.0 300.0))
  (is (nil? (s/knob {:track 300.0 :room 300.0 :content 200.0 :offset 0.0})))
  (is (= 0.0 (s/most 200.0 300.0))))

(deftest the-knob-is-the-rooms-share
  ;; A room of a quarter of the content: a knob a quarter of the track.
  (is (= {:len 100.0 :pos 0.0} (s/knob {:track 400.0 :room 300.0 :content 1200.0 :offset 0.0})))
  (is (= {:len 100.0 :pos 300.0} (s/knob {:track 400.0 :room 300.0 :content 1200.0 :offset 900.0})))
  (is (= 150.0 (:pos (s/knob {:track 400.0 :room 300.0 :content 1200.0 :offset 450.0}))))
  ;; Never shorter than 24 px, however long the content.
  (is (= 24.0 (:len (s/knob {:track 400.0 :room 300.0 :content 3200000.0 :offset 0.0})))))

(deftest a-knob-place-gives-the-content-place
  (let [geo {:track 400.0 :room 300.0 :content 1200.0}]
    (is (= 450.0 (s/offset-at geo 150.0)))
    (is (= 0.0 (s/offset-at geo -50.0)))
    (is (= 900.0 (s/offset-at geo 900.0)))))

(deftest a-page-is-the-room-less-a-line
  (is (= 260.0 (s/page-px 300.0)))
  (is (= 30.0 (s/page-px 60.0))))

(deftest the-edge-gives-less-and-less
  (let [room 300.0]
    (is (= 0.0 (s/pull 0.0 room)))
    (is (< 0.0 (s/pull 10.0 room) 10.0))
    (is (< (s/pull 100.0 room) (s/pull 400.0 room) (* s/pull-share room)))
    (is (< (s/pull 1e9 room) 100.0))
    ;; Each further px gives less than the one before.
    (is (> (- (s/pull 20.0 room) (s/pull 10.0 room)) (- (s/pull 210.0 room) (s/pull 200.0 room))))
    (is (= (- (s/pull 50.0 room)) (s/pull -50.0 room)))))

(deftest a-bounce-is-small
  (is (= 30.0 (s/bounce-px 10.0 300.0)))
  (is (= 50.0 (s/bounce-px 500.0 300.0))))

(deftest a-gesture-keeps-to-its-axis
  (is (= :y (s/lock-axis 3.0 -20.0)))
  (is (= :x (s/lock-axis -20.0 3.0))))

(deftest keys-scroll-a-line-a-page-or-to-an-end
  (let [geo {:offset 400.0 :room 300.0 :content 2000.0}
        go #(s/key-target geo (s/key-move %1 %2))]
    (is (= 440.0 (go :down {})))
    (is (= 360.0 (go :up {})))
    (is (= 660.0 (go :page-down {})))
    (is (= 140.0 (go :page-up {})))
    (is (= 660.0 (go :space {})))
    (is (= 140.0 (go :space {:shift true})))
    (is (= 660.0 (go :down {:alt true})))
    (is (= 0.0 (go :home {})))
    (is (= 1700.0 (go :end {})))
    (is (= 0.0 (go :up {:shortcut true})))
    (is (= 1700.0 (go :down {:shortcut true})))
    (is (= {:axis :x :by :line :dir 1} (s/key-move :right {})))
    (is (nil? (s/key-move :tab {})))
    ;; Never past an end.
    (is (= 0.0 (s/key-target {:offset 10.0 :room 300.0 :content 2000.0} (s/key-move :page-up {}))))))

(deftest reveal-moves-the-least
  ;; In sight already: it stays.
  (is (= 100.0 (s/reveal-offset 100.0 300.0 150.0 200.0)))
  ;; Below: its foot 16 px above the room's.
  (is (= 216.0 (s/reveal-offset 100.0 300.0 450.0 500.0)))
  ;; Above: its top 16 px below the room's.
  (is (= 34.0 (s/reveal-offset 100.0 300.0 50.0 80.0)))
  ;; Longer than the room: where some is seen it stays; else its start.
  (is (= 100.0 (s/reveal-offset 100.0 300.0 0.0 1000.0)))
  (is (= 1984.0 (s/reveal-offset 100.0 300.0 2000.0 3000.0))))

(deftest a-drag-near-an-edge-scrolls-faster-the-nearer
  (is (nil? (s/auto-speed 30.0)))
  (is (< (s/auto-speed 20.0) (s/auto-speed 5.0) (s/auto-speed 0.0)))
  (is (= s/auto-most (s/auto-speed -40.0))))

(deftest bars-look-as-macos-draws-them
  (is (= {:thick 7.0 :track false :own-room false} (s/bar-look {:overlay true})))
  (is (= {:thick 11.0 :track true :own-room false} (s/bar-look {:overlay true :hovered true})))
  (is (= {:thick 15.0 :track true :own-room true} (s/bar-look {:overlay false}))))

(deftest only-the-rows-in-view-are-built
  (is (= [0 20] (s/row-range 100000 32.0 0.0 320.0)))
  (is (= [3115 3145] (s/row-range 100000 32.0 100000.0 320.0)))
  (is (= [99980 100000] (s/row-range 100000 32.0 (- (* 100000 32.0) 320.0) 320.0)))
  (is (= [0 0] (s/row-range 0 32.0 0.0 320.0))))

(deftest macos-settings-are-read
  (is (s/parse-paging "1\n"))
  (is (not (s/parse-paging "0")))
  (is (not (s/parse-paging "")))
  (is (s/parse-style "1\n"))
  (is (not (s/parse-style "0\n")))
  (is (s/parse-style "")))

(deftest rows-added-above-and-a-log
  (is (= {:lo -20 :n 100020} (:rows (p/add-above p/start-state 20))))
  (let [state (nth (iterate p/log-line p/start-state) (+ 5 p/log-most))]
    (is (= p/log-most (count (:log state))))
    (is (= 6 (:id (first (:log state)))))))
