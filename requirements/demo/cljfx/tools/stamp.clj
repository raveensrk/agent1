(ns stamp
  "The build step of the version stamp: writes the release version, from
  VERSION, and the commit HEAD names into build/demo/build.edn, where the app
  reads them from the class path. Run it before the app, after every commit.

      clojure -M:stamp"
  (:require [clojure.java.io :as io]
            [clojure.java.shell :as shell]
            [clojure.string :as str]))

(def out (io/file "build" "demo" "build.edn"))

(defn facts
  "The release version and the full commit hash, as the working tree has them."
  []
  (let [{:keys [exit out err]} (shell/sh "git" "rev-parse" "HEAD")]
    (when-not (zero? exit)
      (throw (ex-info (str "git rev-parse HEAD failed: " err) {})))
    {:version (str/trim (slurp "VERSION"))
     :commit (str/trim out)}))

(defn write!
  "Writes build.edn and returns what it wrote."
  []
  (let [data (facts)]
    (io/make-parents out)
    (spit out (str (pr-str data) "\n"))
    data))

(defn -main [& _]
  (let [{:keys [version commit]} (write!)]
    (println "wrote" (.getPath out) "- version" version "commit" commit)
    (shutdown-agents)))
