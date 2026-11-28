(ns demo.version-check
  "The window checks of About shows the app's version and commit, in
  requirements/gui.org. Builds build.edn as the build does, then opens the
  real windows behind whatever is in front. Mouse and key events go through
  each scene, which picks what is under them as it does for a real pointer;
  nothing moves the pointer and nothing takes the keyboard. The app menu is
  macOS's, outside any scene: About is chosen there by calling the item's own
  action, as macOS does when it is clicked. The clipboard's text is put back
  at the end.

      clojure -M:check-version"
  (:require [clojure.java.shell :as shell]
            [clojure.string :as str]
            [demo.ui :as ui]
            [demo.version :as v]
            [demo.version-page :as p]
            [stamp])
  (:import [com.sun.glass.ui MenuItem]
           [javafx.application Platform]
           [javafx.geometry Bounds]
           [javafx.scene Node Parent Scene]
           [javafx.scene.control Labeled]
           [javafx.scene.input Clipboard ClipboardContent KeyCode KeyEvent MouseButton MouseEvent]
           [javafx.stage Stage Window]
           [com.sun.javafx.scene SceneHelper]))

;; The whole run, in seconds: over it, the checks stop and say so.
(def timeout-s 60)

(defn- on-fx [f]
  (let [pr (promise)]
    (Platform/runLater #(deliver pr (try (f) (catch Throwable t t))))
    (deref pr 5000 :timeout)))

(defn- windows [title]
  (on-fx #(vec (filter (fn [^Window w] (and (instance? Stage w) (.isShowing w) (= title (.getTitle ^Stage w))))
                       (Window/getWindows)))))

(defn- scene ^Scene [title] (some-> ^Stage (first (windows title)) .getScene))

(defn- node ^Node [title id] (when-let [s (scene title)] (on-fx #(.lookup (.getRoot s) (str "#" id)))))

(defn- text [title id] (some-> (node title id) (#(on-fx (fn [] (.getText ^Labeled %))))))

(def failures (atom 0))

(defn- check [what expected actual]
  (let [ok (= expected actual)]
    (when-not ok (swap! failures inc))
    (println (if ok "ok  " "FAIL") what "- expected" expected "got" actual)))

;;; The pointer and the keys, through the scene

(defn- mouse-event [type x y]
  (MouseEvent. type x y x y MouseButton/PRIMARY (int 1)
               false false false false
               (boolean (= MouseEvent/MOUSE_PRESSED type)) false false
               true false false nil))

(defn- click! [title ^Node n]
  (let [s (scene title)
        [x y] (on-fx #(let [^Bounds b (.localToScene n (.getLayoutBounds n))] [(.getCenterX b) (.getCenterY b)]))]
    (doseq [type [MouseEvent/MOUSE_PRESSED MouseEvent/MOUSE_RELEASED MouseEvent/MOUSE_CLICKED]]
      (on-fx #(SceneHelper/processMouseEvent s (mouse-event type (double x) (double y)))))
    (Thread/sleep 150)))

(defn- tap! [title ^KeyCode code]
  (let [s (scene title)]
    (doseq [type [KeyEvent/KEY_PRESSED KeyEvent/KEY_RELEASED]]
      (on-fx #(SceneHelper/processKeyEvent s (KeyEvent. type "" "" code false false false false))))
    (Thread/sleep 300)))

;;; The app menu

(defn- menu-items [] (on-fx #(vec (.getItems (v/app-menu)))))

(defn- choose-about! []
  (on-fx #(.action (.getCallback ^MenuItem (first (.getItems (v/app-menu))))))
  (Thread/sleep 400))

;;; What the windows say

(defn- all-words
  "Every piece of text a window's scene shows."
  [^Scene s]
  (on-fx #(letfn [(walk [^Node n]
                    (concat (when (instance? Labeled n) [(.getText ^Labeled n)])
                            (when (instance? Parent n) (mapcat walk (.getChildrenUnmodifiable ^Parent n)))))]
            (vec (remove nil? (walk (.getRoot s)))))))

(defn- clip [] (on-fx #(.getString (Clipboard/getSystemClipboard))))
(defn- clip! [t] (on-fx #(.setContent (Clipboard/getSystemClipboard) (doto (ClipboardContent.) (.putString t)))))

(defn -main [& _]
  (future (Thread/sleep (* 1000 (long timeout-s)))
          (println "timeout: the checks ran over" timeout-s "s")
          (System/exit 2))
  (reset! ui/*follow-system false)
  (stamp/write!)
  (let [version (str/trim (slurp "VERSION"))
        hash7 (subs (str/trim (:out (shell/sh "git" "rev-parse" "HEAD"))) 0 7)
        about (str "About " p/app-name)
        kept-clip (atom nil)]
    (Platform/setImplicitExit false)
    (p/start!)
    (Thread/sleep 1500)
    (reset! kept-clip (clip))

    (println "The app menu has About")
    (let [items (menu-items)]
      (check "the app menu's first item" about (on-fx #(.getTitle ^MenuItem (first items))))
      (check "a separator under it" true (identical? MenuItem/Separator (second items))))
    (check "no About window before it is chosen" 0 (count (windows about)))
    (check "the main window shows no version or commit" []
           (filterv #(or (str/includes? % version) (str/includes? % hash7)) (all-words (scene p/app-name))))

    (println "The About window shows the name, the version and the commit")
    (choose-about!)
    (check "choosing About opens one About window" 1 (count (windows about)))
    (check "it shows the app's name" p/app-name (text about "about-name"))
    (check "the version" (str "Version " version) (text about "about-version"))
    (check "the commit, 7 characters" (str "Commit " hash7) (text about "about-commit"))
    (check "it is a fixed size" false (let [^Stage w (first (windows about))] (on-fx #(.isResizable w))))
    (choose-about!)
    (check "chosen again, still one About window" 1 (count (windows about)))

    (println "A Copy button copies them")
    (clip! "before")
    (click! about (node about "about-copy"))
    (check "Copy puts the version, a middle dot and the short hash on the clipboard"
           (str "v" version " · " hash7) (clip))

    (println "Escape closes it")
    (tap! about KeyCode/ESCAPE)
    (check "Escape: the About window is gone" 0 (count (windows about)))
    (choose-about!)
    (check "chosen once more, it opens again" 1 (count (windows about)))

    (when @kept-clip (clip! @kept-clip))
    (println (if (zero? @failures) "All checks passed." (str @failures " checks failed.")))
    (System/exit (if (zero? @failures) 0 1))))
