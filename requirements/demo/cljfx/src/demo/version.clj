(ns demo.version
  "About: the app menu's first item opens a window with the app's name, its
  release version and the commit it was built from, and a Copy button. The
  part worth copying.

  The build writes the version and the commit into `demo/build.edn` on the
  class path, with tools/stamp.clj; the app reads that file and never asks git
  while it runs.

  JavaFX has no public way into the macOS app menu, the one named for the app.
  Glass, its window layer, keeps it, and `install-about!` adds the item there."
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io])
  (:import [com.sun.glass.ui Application MenuItem MenuItem$Callback]
           [javafx.scene.input Clipboard ClipboardContent KeyCode KeyEvent]))

;; How long a commit is shown.
(def hash-length 7)

(defn short-hash [commit] (subs commit 0 (min hash-length (count commit))))

(defn parse-build
  "The build's facts from the text of build.edn, or nil when they are not there."
  [text]
  (let [data (try (edn/read-string text) (catch Exception _ nil))]
    (when (and (map? data) (string? (:version data)) (string? (:commit data))
               (re-matches #"[0-9a-f]{40}" (:commit data)))
      (select-keys data [:version :commit]))))

(defn read-build
  "The facts the build wrote, from the class path; nil when there was no build."
  []
  (some-> (io/resource "demo/build.edn") slurp parse-build))

(defn about-lines
  "What the About window says under the name; \"unknown\" with no build."
  [{:keys [version commit]}]
  {:version (str "Version " (or version "unknown"))
   :commit (str "Commit " (if commit (short-hash commit) "unknown"))})

(defn copy-text
  "What Copy puts on the clipboard: `v1.4.2 · 91274ba`, for a bug report."
  [{:keys [version commit]}]
  (str "v" (or version "unknown") " · " (if commit (short-hash commit) "unknown")))

(defn copy!
  "Puts the words on the clipboard. Call it on the UI thread."
  [text]
  (.setContent (Clipboard/getSystemClipboard)
               (doto (ClipboardContent.) (.putString text))))

;;; The app menu

(defn app-menu
  "The macOS app menu, as Glass keeps it; nil elsewhere, or before it is made.
  Call it on the UI thread."
  []
  (let [app (Application/GetApplication)]
    ;; MacApplication is not public, so its method is reached by reflection.
    (when (= "com.sun.glass.ui.mac.MacApplication" (.getName (class app)))
      (let [m (doto (.getMethod (class app) "getAppleMenu" (make-array Class 0)) (.setAccessible true))]
        (.invoke m app (object-array 0))))))

(defn install-about!
  "Puts \"About <app-name>\" first in the app menu, a separator under it, and
  calls `on-choose` on the UI thread when it is chosen. Call it on the UI thread
  once a window is showing. Returns true when the menu was there."
  [app-name on-choose]
  (if-let [^com.sun.glass.ui.Menu menu (app-menu)]
    (let [item (.createMenuItem (Application/GetApplication) (str "About " app-name)
                                (reify MenuItem$Callback
                                  (action [_] (on-choose))
                                  (validate [_])))]
      (.insert menu ^MenuItem item 0)
      (.insert menu MenuItem/Separator 1)
      true)
    false))

;;; The About window

(defn about-window
  "The About window: `showing` while it is open; `on-close` when its close
  button or Escape asks to close it."
  [{:keys [app-name build showing on-close]}]
  (let [{:keys [version commit]} (about-lines build)]
    {:fx/type :stage
     :showing showing
     :title (str "About " app-name)
     :resizable false
     :width 320
     :height 240
     :on-close-request (fn [_] (on-close))
     :scene
     {:fx/type :scene
      :stylesheets [(str (io/resource "demo/glass.css"))]
      :root
      {:fx/type :v-box
       :id "about"
       :style-class ["root" "page"]
       :alignment :center
       :spacing 8
       :padding 24
       :on-key-pressed (fn [^KeyEvent e]
                         (when (= KeyCode/ESCAPE (.getCode e))
                           (.consume e)
                           (on-close)))
       :children [{:fx/type :label :id "about-name" :style-class ["label" "section-head"] :text app-name}
                  {:fx/type :label :id "about-version" :text version}
                  {:fx/type :label :id "about-commit" :text commit}
                  {:fx/type :button
                   :id "about-copy"
                   :text "Copy"
                   :v-box/margin {:top 8}
                   :on-action (fn [_] (copy! (copy-text build)))}]}}}))
