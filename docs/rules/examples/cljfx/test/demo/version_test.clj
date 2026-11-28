(ns demo.version-test
  (:require [clojure.java.io :as io]
            [clojure.test :refer [deftest is]]
            [demo.version :as v]))

(def commit "91274baac06ffe0117e1f61ff8bb02968f6cf29f")
(def build {:version "1.4.2" :commit commit})

(deftest about-says-the-version-and-seven-characters-of-the-commit
  (is (= {:version "Version 1.4.2" :commit "Commit 91274ba"} (v/about-lines build)))
  (is (= {:version "Version unknown" :commit "Commit unknown"} (v/about-lines nil))))

(deftest copy-puts-the-version-a-middle-dot-and-the-short-hash
  (is (= "v1.4.2 · 91274ba" (v/copy-text build))))

(deftest the-build-facts-are-read-from-what-the-build-wrote
  (is (= build (v/parse-build (pr-str (assoc build :extra 1)))))
  ;; Nothing, or something that is not a build's facts: unknown.
  (is (nil? (v/parse-build "")))
  (is (nil? (v/parse-build "{:version \"1.4.2\"}")))
  (is (nil? (v/parse-build (pr-str {:version "1.4.2" :commit "91274ba"}))))
  (is (nil? (v/parse-build "not edn {"))))

(deftest the-app-never-asks-git-while-it-runs
  (let [code (str (slurp (io/resource "demo/version.clj")) (slurp (io/resource "demo/version_page.clj")))]
    (is (not (re-find #"clojure\.java\.shell|ProcessBuilder|Runtime/getRuntime|\"git\"" code)))))
