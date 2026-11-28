(ns demo.date-picker-test
  (:require [clojure.test :refer [deftest is]]
            [demo.date-picker :as d]
            [demo.date-picker-page :as p])
  (:import [java.time DayOfWeek LocalDate YearMonth]
           [java.util Locale]))

(def today (LocalDate/of 2026 11 15))
(def nov-20 (LocalDate/of 2026 11 20))

(defn- taken
  ([text] (taken text Locale/UK))
  ([text locale] (:date (d/parse text locale today))))

(deftest what-is-typed-is-read-forgivingly
  (is (= nov-20 (taken "20 nov")))
  (is (= nov-20 (taken "nov 20")))
  (is (= nov-20 (taken "20 November 2026")))
  (is (= nov-20 (taken "2026-11-20")))
  ;; In either case, and the form the field itself shows.
  (is (= nov-20 (taken "20 NOV")))
  (is (= nov-20 (taken "Fri, 20 Nov 2026")))
  (is (= nov-20 (taken "Nov 20, 2026")))
  (is (= nov-20 (taken "20th Nov"))))

(deftest the-short-form-follows-the-region
  (is (= nov-20 (taken "20/11/2026" Locale/UK)))
  (is (= nov-20 (taken "11/20/2026" Locale/US)))
  (is (= nov-20 (taken "20/11/26" Locale/UK)))
  (is (nil? (taken "20/11/2026" Locale/US))))

(deftest a-day-with-no-year-is-the-next-such-day
  (is (= today (taken "15 nov")))
  (is (= (LocalDate/of 2027 11 14) (taken "14 nov")))
  (is (= (LocalDate/of 2027 1 3) (taken "3 jan")))
  (is (= (LocalDate/of 2028 2 29) (taken "29 feb"))))

(deftest what-is-not-a-date-is-not-guessed-at
  (is (= {:error :not-a-date} (d/parse "31 Nov" Locale/UK today)))
  (is (= {:error :not-a-date} (d/parse "abc" Locale/UK today)))
  (is (= {:error :not-a-date} (d/parse "2026-02-30" Locale/UK today)))
  (is (= {:error :not-a-date} (d/parse "tomorrow" Locale/UK today)))
  (is (= {:empty true} (d/parse "  " Locale/UK today)))
  (is (= "Not a date. Try 20 Nov or 2026-11-20" (d/error-text {:error :not-a-date}))))

(deftest a-date-is-shown-the-regions-way-with-its-weekday
  (is (= "Fri, 20 Nov 2026" (d/show nov-20 Locale/UK)))
  (is (= "Fri, Nov 20, 2026" (d/show nov-20 Locale/US)))
  (is (= "November 2026" (d/month-title (YearMonth/of 2026 11) Locale/UK))))

(deftest the-calendar-shows-whole-weeks
  (let [sun (d/month-days (YearMonth/of 2026 11) DayOfWeek/SUNDAY)
        mon (d/month-days (YearMonth/of 2026 11) DayOfWeek/MONDAY)]
    ;; 1 Nov 2026 is a Sunday.
    (is (= [(LocalDate/of 2026 11 1) 35] [(first sun) (count sun)]))
    (is (= [(LocalDate/of 2026 10 26) 42] [(first mon) (count mon)]))
    (is (<= (count mon) 42))
    (is (= ["M" "T" "W" "T" "F" "S" "S"] (d/weekdays DayOfWeek/MONDAY Locale/UK)))))

(deftest keys-move-the-mark
  (is (= (LocalDate/of 2026 11 21) (d/step-mark nov-20 javafx.scene.input.KeyCode/RIGHT)))
  (is (= (LocalDate/of 2026 11 27) (d/step-mark nov-20 javafx.scene.input.KeyCode/DOWN)))
  (is (= (LocalDate/of 2026 12 1) (d/step-mark (LocalDate/of 2026 11 30) javafx.scene.input.KeyCode/RIGHT)))
  (is (= (LocalDate/of 2026 12 20) (d/step-mark nov-20 javafx.scene.input.KeyCode/PAGE_DOWN))))

(deftest the-calendar-stays-whole
  (is (= {:x 4.0 :y 104.0 :over false} (d/calendar-place {:x 0.0 :top 56.0 :bottom 100.0} 280 300 560 560)))
  (is (= {:x 20.0 :y 152.0 :over true} (d/calendar-place {:x 20.0 :top 456.0 :bottom 500.0} 280 300 560 560))))

(deftest the-page-keeps-each-write-for-undo
  (let [s (p/write p/start-state :starts nov-20)]
    (is (= [nov-20 1] [(get-in s [:dates :starts]) (:writes s)]))
    (is (= (get-in p/start-state [:dates :starts]) (get-in (p/undo s) [:dates :starts])))))
