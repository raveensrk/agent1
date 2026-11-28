# Dev Tools

The list of dev tools I prefer. This file is the source.

Only current tools and AI tools go here. Tools I tried, used before, or want
to try go in work dev_tools_archive.md:
<https://github.com/raveensrk/work/blob/main/deck/tools/dev_tools_archive.md>
A tool lives in one file only.

The list is ordered: of two tools that share a tag, the one written first
is preferred. The Needs line lists the prerequisites: all of the
comma-separated items are needed; "a or b" needs only one of them.

## Tools by group

### Basics

#### Computer

- Tags: ROOT, GUI

#### Touch Typing

- Tags: Skills
- Needs: [Computer](#computer)

### Shell

#### Bash

- Tags: Environment, core
- Needs: [Ghostty](#ghostty)

also stands for shell scripting; prefer Bash over POSIX sh

##### shellcheck

- Tags: core
- Needs: [Bash](#bash)

Bash linter

##### shfmt

- Tags: core
- Needs: [Bash](#bash)

Bash formatter

#### zsh

- Tags: Environment, core
- Needs: [Ghostty](#ghostty)

Default shell on macOS

### Terminal

#### Ghostty

- Tags: Terminal, core
- Url: <https://github.com/ghostty-org/ghostty>
- Needs: [Touch Typing](#touch-typing)

#### iterm2

- Tags: optional

### AI

- Needs: [Ghostty](#ghostty)

#### LLM data

##### models

- Tags: AI
- Url: <https://github.com/reyamira/models>
- Needs: [AI](#ai)

TUI and CLI for browsing AI models and comparing benchmarks

##### llmfit

- Tags: AI
- Url: <https://github.com/AlexsJones/llmfit>
- Needs: [AI](#ai)

TUI and CLI for finding LLMs that fit local hardware

#### AI Coding Agents

##### pi

- Tags: core
- Needs: [AI](#ai)

##### Claude Code

- Tags: core
- Needs: [AI](#ai)
- `/workflows`

##### Codex and ChatGPT

- Tags: core
- Needs: [AI](#ai)

##### Crush

- Tags: AI
- Url: <https://github.com/charmbracelet/crush>
- Needs: [AI](#ai)

##### opencode

- Tags: core
- Url: <https://github.com/sst/opencode>
- Needs: [AI](#ai)

##### ollama

- Tags: AI, core
- Url: <https://github.com/ollama/ollama>
- Needs: [AI](#ai)

Run LLMs locally

### Browser

#### Firefox

- Tags: Web Browser, core
- Needs: [Computer](#computer)

#### Chrome

- Tags: Web Browser, core
- Needs: [Computer](#computer)

#### Safari

- Tags: Web Browser
- Needs: [Computer](#computer)

### VPN

- Needs: [Bash](#bash)

#### WireGuard

- Tags: intermediate, Network
- Needs: [VPN](#vpn)

#### Tailscale

- Tags: intermediate, Network, Web, core
- Needs: [VPN](#vpn)

#### Mullvad

- Url: <https://mullvad.net/en>
- Needs: [VPN](#vpn)

### Editor

- Needs: [Bash](#bash)

#### Vim

- Tags: core
- Needs: [Editor](#editor)

#### universal-ctags

- Tags: core
- Needs: [Editor](#editor)

#### Vim script

- Tags: intermediate, Programming Languages, Editor and Tooling Extension
- Needs: [Vim](#vim)

#### Emacs

- Tags: core
- Needs: [Editor](#editor)

### Productivity

- Needs: [Bash](#bash)

#### fzf

- Tags: core
- Needs: [Productivity](#productivity)

Text filtering

#### ripgrep

- Tags: core
- Needs: [Productivity](#productivity)

Faster grep

#### fd

- Tags: core
- Needs: [Productivity](#productivity)

Faster find

#### urlview

- Needs: [Productivity](#productivity)

#### zoxide

- Tags: core
- Needs: [Productivity](#productivity)

Faster directory switching

#### ranger

- Tags: core
- Needs: [Productivity](#productivity)

File manager

#### direnv

- Tags: core
- Needs: [Productivity](#productivity)

Per-folder environment variables

#### parallel

- Tags: core
- Needs: [Productivity](#productivity)

GNU parallel

#### newsboat

#### E-Mail

##### Himalaya

- Tags: E Mail
- Url: <https://github.com/pimalaya/himalaya>
- Needs: [newsboat](#newsboat)

##### Himalaya-Tui

- Tags: E Mail
- Url: <https://github.com/pimalaya/himalaya-tui>
- Needs: [Himalaya](#himalaya)

##### Mutt / Neomutt

- Tags: expert, E Mail
- Needs: [newsboat](#newsboat)

#### Multiplexer

##### tmux

- Tags: core
- Needs: [Productivity](#productivity)

##### Rex

##### Herdr

- Tags: core
- Needs: [pi](#pi) or [Claude Code](#claude-code) or [Codex and ChatGPT](#codex-and-chatgpt) or [Crush](#crush)

terminal multiplexer for coding agents

### Communication

#### Chat

##### Whatsapp

###### wacli

### Data interchange File Format

#### JSON

- Tags: Programming Languages, Data and Query
- Needs: [Programming Languages](#programming-languages)

#### YAML

- Tags: Programming Languages, Data and Query
- Needs: [JSON](#json)

#### TOML

- Tags: intermediate, Formats, Markup Data and Config
- Needs: [JSON](#json)

#### JSON Lines

- Tags: intermediate, Formats, Markup Data and Config
- Needs: [JSON](#json)

### Database

- Needs: [Ghostty](#ghostty)

#### recfile (GNU recutils)

- Tags: core
- Needs: [Database](#database)

plain-text records; recsel, recfix, rec2csv

### SCM

- Needs: [Bash](#bash)

#### Git

- Tags: core
- Needs: [SCM](#scm)

#### lazygit

- Tags: core
- Needs: [Git](#git)

#### Forgejo

- Tags: core
- Needs: [lazygit](#lazygit)

#### fj

- Tags: core
- Needs: [Forgejo](#forgejo)

#### gh

- Tags: core
- Url: <https://cli.github.com>
- Needs: [Git](#git)

GitHub CLI

### Structured Query Language

#### jq

- Tags: core
- Needs: [JSON](#json)

#### yq

- Tags: core

#### SQL

- Tags: intermediate, Programming Languages, Data and Query
- Needs: [JSON](#json)

#### SQLite

- Tags: core
- Needs: [SQL](#sql)

### Game Engine

#### LÖVE (love2d)

- Tags: Programming Languages, Games and 2D Graphics
- Needs: [Lua](#lua)

#### Bevy

- Tags: expert, Programming Languages, Games and 2D Graphics
- Needs: [Rust](#rust)

#### Gadot

### HDL

- Needs: [Programming Languages](#programming-languages)

#### verible

- Tags: core
- Needs: [SystemVerilog](#systemverilog)

#### verilator

- Tags: core
- Needs: [SystemVerilog](#systemverilog)

#### SystemVerilog

- Tags: intermediate, Programming Languages, Hardware Design and Verification
- Needs: [HDL](#hdl)

#### peakrdl

- Tags: core
- Url: <https://github.com/SystemRDL/PeakRDL>
- Needs: [SystemVerilog](#systemverilog)

SystemRDL register generator

#### gtkwave

- Tags: core
- Url: <https://gtkwave.github.io/gtkwave/>
- Needs: [SystemVerilog](#systemverilog)

Waveform viewer

### Requirements

#### doorstop

- Tags: core
- Url: <https://github.com/doorstop-dev/doorstop>
- Needs: [Python](#python)

Requirements management; doorstop-gui for the GUI

### Finance

- Needs: [Bash](#bash)

#### hledger

- Tags: intermediate, Finance
- Needs: [Ledger CLI](#ledger-cli)

#### Ledger CLI

- Tags: intermediate, Finance
- Needs: [Finance](#finance)

### System Admin

- Needs: [Bash](#bash)

#### rsync

- Tags: core
- Needs: [System Admin](#system-admin)

#### GNU Stow

- Tags: core
- Needs: [System Admin](#system-admin)

#### Homebrew

- Tags: macos, core
- Needs: [System Admin](#system-admin)

### Entertainment

#### mpv :

- Needs: [Productivity](#productivity)

#### qBittorrent

- Tags: Torrent
- Needs: [Computer](#computer)

### Security

#### Bitwarden

- Tags: core
- Needs: [Computer](#computer)

### Documentation

#### pandoc

- Tags: core
- Needs: [Markdown](#markdown)

#### Mermaid

- Tags: Diagrams Flowcharts and Drawings, Diagram Formats
- Needs: [Markdown](#markdown)

#### Markdown

- Tags: Formats, Markup Data and Config
- Needs: [Vim](#vim)

#### LaTeX

- Tags: intermediate, Formats, Markup Data and Config
- Needs: [Markdown](#markdown)

#### PDF

- Tags: advanced, Formats, Publish
- Needs: [LaTeX](#latex)

### GUI Library

#### egui

- Tags: expert, gui
- Needs: [Rust](#rust)

#### GTK

- Tags: library, gui

#### imgui

- Tags: gui, library
- Needs: [C++](#c-1)

#### Nuklear

- Tags: gui, library
- Url: <https://immediate-mode-ui.github.io/Nuklear/index.html>
- Needs: [C](#c)

### Data Visualization

#### Graphviz

- Url: <https://graphviz.org>
- Needs: [JSON](#json)

dot lays out dev_tools_path.svg

#### d2

#### Excalidraw

- Tags: advanced, Diagrams Flowcharts and Drawings, Drawing
- Url: <https://github.com/excalidraw/excalidraw>
- Needs: [SVG](#svg)

hand-drawn style whiteboard, self-hosted from ~/dot/config/excalidraw/compose.yaml

#### d3

- Tags: library
- Needs: [JavaScript](#javascript)

#### SVG

- Tags: intermediate, Diagrams Flowcharts and Drawings, Diagram Formats
- Needs: [YAML](#yaml)

##### SVG with Animation

- Url: <https://en.wikipedia.org/wiki/SVG_animation>
- Needs: [SVG](#svg)

### Programming Languages

- Needs: [Bash](#bash)

#### Systems Programming Languages

##### Zig

- Tags: expert, Programming Languages, Systems and Native
- Needs: [Programming Languages](#programming-languages)

##### Rust

- Tags: expert, Programming Languages, Systems and Native, core
- Needs: [Programming Languages](#programming-languages)

Rust and its tooling: rustup, cargo, clippy, rustfmt

##### Go

- Tags: expert, Programming Languages, Systems and Native
- Needs: [Programming Languages](#programming-languages)

##### C

- Tags: Programming Languages, Systems and Native
- Needs: [Programming Languages](#programming-languages)

##### C++

- Tags: avoid
- Needs: [Programming Languages](#programming-languages)

##### Makefile

- Tags: Formats, Markup Data and Config, core
- Needs: [Bash](#bash)

#### General Purpose Programming Language

##### Swift

- Tags: expert, Programming Languages, Apple Platforms
- Needs: [Programming Languages](#programming-languages)

##### Python

- Tags: Programming Languages, Automation and Scripting, core
- Needs: [Programming Languages](#programming-languages)

Python and its tooling: pytest, pylint, black

#### Scripting Languages

##### Lua

- Tags: Programming Languages, Games and 2D Graphics
- Needs: [Programming Languages](#programming-languages)

#### Experimental Programming Languages

##### Jai

- Tags: advanced, Programming Languages, Games and 2D Graphics
- Needs: [Programming Languages](#programming-languages)

#### Web

- Needs: [Programming Languages](#programming-languages)

##### JavaScript

- Tags: intermediate, Programming Languages, Web
- Needs: [Web](#web)

##### TypeScript

- Tags: intermediate, Programming Languages, Web
- Needs: [Web](#web)

##### HTML

- Tags: Formats, Markup Data and Config
- Needs: [Web](#web)

##### CSS

- Tags: intermediate, Formats, Markup Data and Config
- Needs: [Web](#web)

##### video.js

- Tags: library
- Url: <https://videojs.org/>
- Needs: [JavaScript](#javascript)

Video.js v10 - open source media player framework for HTML and React.

### Lisp Family of Languages

#### REPL

#### Fennel

- Tags: expert, Programming Languages, Games and 2D Graphics
- Needs: [Lua](#lua)

#### Lisp

- Tags: adv
- Needs: [Programming Languages](#programming-languages)

#### Racket

- Tags: expert, avoid
- Needs: [Lisp](#lisp)

Avoid: lack of good libraries

#### Emacs Lisp

- Tags: expert
- Needs: [Lisp](#lisp), [Emacs](#emacs)

#### Tauri

- Tags: gui, library
- Needs: [Rust](#rust)

Desktop apps: a Rust core with a web view window. Used by diet_tracker.

#### Svelte

- Tags: web, library
- Needs: [TypeScript](#typescript)

Small, fast web UI components. diet_tracker's window.

#### cljfx

- Tags: gui, library
- Needs: [Clojure](#clojure)

#### HumbleUI

- Tags: library, gui
- Needs: [Clojure](#clojure)

#### Clojure

- Needs: [Lisp](#lisp)

#### Jank

- Tags: lisp
- Url: <https://youtu.be/tHgApFhevrQ>
- Needs: [Clojure](#clojure)

Clojure Dialect with c++ interop

### Fonts

- Needs: [Computer](#computer)

#### Freetype

- Url: <https://freetype.org/index.html>
- Needs: [Fonts](#fonts)

### Build Systems

#### Bazel

- Tags: core

#### Chisel

- Tags: experimental

#### FuseSOC

- Tags: experimental

#### PULP

- Tags: experimental

## Notes

### Note 1

Reduce Abstractions

<https://www.youtube.com/watch?v=48DqkAx86Vg>

### Avoid

Programming Languages to avoid:

c++, go, c#, dart, kotlin

racket: lack of good libraries

- PULP: <https://pulp-platform.org/index.html>
  License issues
