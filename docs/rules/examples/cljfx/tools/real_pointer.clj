;; A last proof with the real pointer, for what the window checks send through
;; the scene: it MOVES THE POINTER and brings each demo's window to the front,
;; for about 4 s in all, so it is run by hand and not from the checks.
;;
;;     clojure -M -i tools/real_pointer.clj
(require '[cljfx.api :as fx]
         '[demo.button :as b]
         '[demo.ui :as ui]
         '[demo.window :as w])
(import '[javafx.application Platform]
        '[javafx.scene.input MouseButton]
        '[javafx.scene.robot Robot]
        '[javafx.stage Stage Window])

(defn on-fx [f]
  (let [p (promise)]
    (Platform/runLater #(deliver p (try (f) (catch Throwable t (str t)))))
    (deref p 5000 :timeout)))

(defn stage ^Stage [] (first (filter #(instance? Stage %) (Window/getWindows))))
(defn node [id] (.lookup (.getRoot (.getScene (stage))) (str "#" id)))
(defn on-screen [id dx dy]
  (on-fx #(let [n (node id) b (.localToScreen n (.getLayoutBounds n))]
            [(+ (.getMinX b) dx) (+ (.getMinY b) dy)])))

(def failures (atom 0))
(defn check [what expected actual]
  (when (not= expected actual) (swap! failures inc))
  (println (if (= expected actual) "ok  " "FAIL") what "- expected" expected "got" actual))

(Platform/setImplicitExit false)
(reset! ui/*follow-system false)
(reset! ui/*reduce false)
(def robot (on-fx #(Robot.)))
(def left (into-array MouseButton [MouseButton/PRIMARY]))
(defn move! [[x y]] (on-fx #(.mouseMove robot (double x) (double y))) (Thread/sleep 30))

;; The window demo: drag the sidebar's divider 60 px to the right.
(reset! w/*state w/start-state)
(def window-app (fx/mount-renderer w/*state w/renderer))
(Thread/sleep 2000)
(on-fx #(.toFront (stage)))
(let [[x y] (on-screen "divider-sidebar" 4.5 200)]
  (move! [x y])
  (on-fx #(.mousePress robot left))
  (doseq [dx (range 5 65 5)] (move! [(+ x dx) y]))
  ;; To the nearest pixel: the pointer moves in whole ones.
  (check "a real drag resizes the sidebar" 280 (Math/round (double (get-in @w/*state [:sizes :sidebar]))))
  (on-fx #(.mouseRelease robot left))
  (Thread/sleep 200)
  (check "and lets go" nil (:dragging @w/*state)))
(move! (on-screen "new-float" 22 22))
(on-fx #(.mouseClick robot left))
(Thread/sleep 400)
(check "a real click opens a floating window" 1 (count (get-in @w/*state [:windows 1 :floats])))
(reset! w/*state (assoc w/start-state :windows {} :order []))
(Thread/sleep 500)

;; The button demo: a click adds 1, a hold of 700 ms adds 10 and no click.
(reset! b/*state (assoc @b/*state :count 0))
(fx/mount-renderer b/*state b/renderer)
(Thread/sleep 1500)
(on-fx #(.toFront (stage)))
(move! (on-screen "add" 40 22))
(on-fx #(.mouseClick robot left))
(Thread/sleep 300)
(check "a real click adds 1" 1 (:count @b/*state))
(on-fx #(.mousePress robot left))
(Thread/sleep 700)
(on-fx #(.mouseRelease robot left))
(Thread/sleep 300)
(check "a real hold adds 10, and no click" 11 (:count @b/*state))
(println (if (zero? @failures) "All real-pointer checks passed." (str @failures " failed.")))
(System/exit (if (zero? @failures) 0 1))
