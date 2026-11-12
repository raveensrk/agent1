(ns demo.button-test
  (:require [clojure.test :refer [deftest is]]
            [demo.button :as button]
            [demo.icons :as icons]
            [demo.ui :as ui]
            [demo.window :as window]))

(deftest sinks-while-pressed-or-held
  (is (= {:scale 0.97 :y 1.0} (ui/press-look {:pressed true :reduce false})))
  (is (= {:scale 1.0 :y 0.0} (ui/press-look {:pressed false :reduce false}))))

(deftest reduce-motion-never-moves
  (is (= {:scale 1.0 :y 0.0} (ui/press-look {:pressed true :reduce true})))
  (is (= {:ms 0 :spring false} (ui/press-timing {:pressed true :reduce true})))
  (is (= {:ms 0 :spring false} (ui/press-timing {:pressed false :reduce true}))))

(deftest a-busy-button-never-moves
  (is (= {:scale 1.0 :y 0.0} (ui/press-look {:pressed true :reduce false :inert true}))))

(deftest press-is-fast-and-release-springs
  (is (= {:ms 120 :spring false} (ui/press-timing {:pressed true :reduce false})))
  (is (= {:ms 420 :spring true} (ui/press-timing {:pressed false :reduce false}))))

(deftest a-save-ends-in-saved-or-retry
  (is (= "Save" (:text (button/save-look :idle))))
  (is (= {:text "Saving…" :busy true :inert true} (button/save-look :saving)))
  (is (= {:text "Saved" :busy false :inert true :mark :check} (button/save-look :saved)))
  (is (= "Retry" (:text (button/save-look :failed))))
  (is (false? (:inert (button/save-look :failed)))))

(deftest the-fill-waits-out-a-quick-click
  (is (< ui/charge-delay-ms ui/hold-ms)))

(deftest every-icon-is-one-phosphor-path
  (is (= 256.0 icons/box))
  (is (every? #(re-matches #"M[-0-9A-Za-z,. ]+Z" %) (vals icons/paths)))
  ;; Every page's icon is one there is, and an unknown name fails at once.
  (is (every? #(string? (icons/path (:icon %))) window/pages))
  (is (thrown? clojure.lang.ExceptionInfo (icons/path :no-such-icon))))

(deftest a-screen-reader-is-told-what-macos-will-pass-on
  ;; A plain button: its name, and no word for its kind but the system's.
  (is (= {:name "Save" :kind nil} (ui/said {:text "Save"})))
  ;; An icon alone is named in words.
  (is (= {:name "Subtract 1" :kind nil} (ui/said {:name "Subtract 1" :tip "Subtract 1"})))
  ;; A second action is said with the name.
  (is (= {:name "Add 1. Hold: Add 10" :kind nil}
         (ui/said {:text "Add 1" :hold-text "Add 10" :tip "Click or Return: add 1. Hold: add 10."})))
  ;; A button that is off is called dimmed, and says why.
  (is (= {:name "Subtract 1. Nothing to subtract: the count is 0." :kind "dimmed button"}
         (ui/said {:name "Subtract 1" :disabled true :tip "Nothing to subtract: the count is 0."}))))
