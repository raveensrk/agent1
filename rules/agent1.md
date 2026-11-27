# Agent1 requirements

A heading that starts with `planned:` is not proven yet.
A `Proof:` item under a rule says how it is checked;
`Proof (draft):` is one not passing yet.

## Goal

Agent1 gives any agent, in any harness, one public set of rules, skills and checks it can follow.

- Asked by the owner on 2026-11-25

## Architecture

### Core and UI are decoupled

- Every app is a core (back end) and one or more UIs (front end: GUI, CLI, TUI, web)
- Core and UI are separate programs that talk only by messages, so a UI can be in any language
- The core has no UI, and the UI has no business logic and never touches the data files
- The core tests headless, and adding a UI changes no core file

## GUI

Not all of this is applicable to all apps. So pick and choose which is necessary for a well designed and performant app.

Every feature implemented must have atleast 1 test for it. 1 test can cover more than 1 feature.

Before starting UI/UX design follow the principles mentioned in this book - Laws of UX - Using Psychology to Design Better Products - Jon Yablonski - [2nd Ed ], 2024 (`~/Library/Mobile Documents/com~apple~CloudDocs/Shared_Documents/Work/Books/Design/Laws of UX - Using Psychology to Design Better Products - Jon Yablonski - [2nd Ed ], 2024.epub`).

### General

- Research the web when you plan
- Plan before implementation

#### Follow Apple Design as much as possible

- The AI agent must consult [Apple Design](https://developer.apple.com/design/) before designing anything

#### No screen reader or VoiceOver support

- Not in the owner's use case, decided on 2026-11-14: no control is built, named or checked for a screen reader, and no code tells macOS what a control is for one
- Reduce Motion, Reduce Transparency, Increase Contrast and the contrast of words stay: they are for the eye

#### The GUI toolkit is JavaFX, through cljfx

- Chosen on 2026-11-13 over a native SwiftUI window, for its checks: a window check runs inside the app, reads any control mid-animation and sends clicks and keys without moving the pointer
- Given up for it: true Liquid Glass. JavaFX cannot blur or bend what is behind a control, so glass is drawn as [Glass shows what is behind it](#glass-shows-what-is-behind-it) says
- Everything the system would have given is built and checked by hand: the press, the glass, Reduce Motion, Reduce Transparency and Increase Contrast
- To be looked at again if native window checks prove to run from one command, with no pointer taken over

##### planned: elimination_tracker uses Tauri, not JavaFX

- Decided by the owner on 2026-11-14: this repo is exempt from the JavaFX/cljfx line above; every other app keeps it
- The window is Tauri 2 with TypeScript; the core and CLI are Rust, a separate program the window starts and talks to by JSON lines
- Given up: the checks run inside the app. Window checks drive the real window code in jsdom over the real core, and a webview run is by hand with a screenshot
- Glass, Reduce Motion, Reduce Transparency and Increase Contrast, where an app wants them, are drawn in CSS and checked by hand
- Proof (draft): elimination_tracker uses Tauri, not JavaFX
  - Tests: cargo test -p elimination_tracker, and npm run check in app, run in elimination_tracker

### Coding Guidelines

- Follow KISS (Keep it simple stupid) philosophy
- Less code better than more code
- Fast code is better than slow code
- No code is better than bad code

### Performance

#### App must run at 60 fps

#### Scrolling must be smooth

#### Stability of the app is important

#### Never compromise performance for visuals

#### Slow work runs off the UI thread

### Appearance

#### Dark Theme

#### Liquid Glass

The look follows Apple's Liquid Glass design language, the native style of macOS 26.

##### Glass is the layer that floats above content

- Toolbars, the sidebar, sheets, menus and pop-ups are glass
- Content is never glass: text, lists, tables and pictures sit under it
- A button is glass only in a toolbar; a button in the page is plain, with a solid fill
- Glass is never stacked on glass: the buttons of a toolbar share one capsule of glass and have none of their own

##### Glass shows what is behind it

- What is behind a glass control shows through it, softened
- A bright rim follows its top left edge, and a soft shadow lies under it
- A shadow takes no click: glass is picked on its shape, and a container on what it holds, never on bounds that a shadow has widened
- Where the toolkit cannot blur or bend what is behind, glass is a see-through fill with the rim and the shadow, and the docs say so

##### Shapes are capsules and concentric

- A control is a capsule: its corner radius is half its height
- A shape inside another shares its centre: its radius is the outer radius less the padding between them

##### Colour is for the main action

- The main action is tinted glass in the accent colour; everything else is regular glass
- Regular glass dims what is behind it, so words on it stay readable
- Clear glass is only for controls over photos and video
- Words and icons on glass keep a contrast of 4.5:1 or more over whatever is behind

##### Glass answers the pointer

- It lightens under the pointer and lightens more on a press, in 120 ms
- Tinted glass lightens only as far as its words stay at 4.5:1; past that a press brightens its rim
- Glass that holds one button answers as one piece: all of it lightens, sinks and fills, and no smaller shape or edge shows inside it
- Glass that several buttons share lightens only under the button the pointer is on, a capsule on the same centre
- It sinks and springs back as [Buttons answer a press](#component) says

##### The system's settings are respected

- Reduce Transparency: glass turns solid, and nothing shows through
- Increase Contrast: every control gets a plain edge all the way round
- A change to any of them is followed while the app runs: Reduce Motion and Reduce Transparency at once, Increase Contrast when the window next comes to the front
- Reduce Motion: as [Reduce Motion is respected](#reduce-motion-is-respected) says

##### Verification

- A window check reads the corner radius of a toolbar's glass and of a button on it: half the height or more
- It reads the gap between the two, above, below and at the side: the same
- It reads the fill of the glass: less than fully opaque. Of a button on it: none. Of a button in the page: fully opaque
- With Reduce Transparency on, it reads the fill of the glass: fully opaque
- It holds the main button and reads the button on its glass: no fill and no edge of its own, and the hold fill as wide as the glass

### Animation

#### Animation types

##### Glide

##### Smooth

##### Bounce

##### Rubber Band

##### Pop-up

##### Spinner

##### Progress bar

##### Lift

#### Animation where possible

##### On hover

##### pop-up

##### Drop down menu

##### Button

- See [Buttons](#component)

##### etc…

#### planned: The motion catalogue

Each motion has one job. A motion is used where it fits that job, and nowhere else.

- Enter: new items rise 14 px and fade in, 80 ms apart, 520 ms each
- Press: sinks in 120 ms, springs back in 420 ms with a small overshoot
- Tab: the highlight pill slides to the picked tab, with a small overshoot
- Value: a score ring or bar fills from empty to its value, 900 ms
- Loading: a shimmer where content will come; never a blank screen
- Sheet: slides up from the bottom; dragged down, it follows the finger
- Done: a tick draws itself, then "Saved" fades after 1 s
- Swipe: a row slides to show its actions
- Open: a tapped photo grows into the page it opens
- Notice: a toast drops in from the top and leaves on its own after 3 s
- New: a soft glow pulses on a dot beside something new
- Every motion runs at 60 fps, and only moves position, size or opacity
- Under Reduce Motion each one becomes a plain fade, or nothing
- Reference: <https://claude.ai/artifact/6frbVe74iMYWVotmbrCfZL>, the Motion catalogue board

Evidence: the mockups use plain CSS keyframes and transitions, which Safari and Chrome both run.

- Proof (draft): The motion catalogue
  - Tests: a window check reads each motion's duration and easing from the app's motion tokens

#### The progress bar and spinners must be smooth

#### Reduce Motion is respected

- With the system's Reduce Motion setting on, things fade and never slide

### Behaviour

#### The app must react to my actions

#### Whatever is running shows a spinner beside the words that say what it does

### Features

#### A way to restart the app

- Restarts the way it was started, on the same data
- Unsaved scratch work is saved first

#### Save and restore state/session

- See [A window comes back as it was left](#window)

### planned: About shows the app's version and commit

Every GUI app does this: a hard requirement.

- Proof (draft): About shows the app's version and commit
  - Tests: clojure -M:test (demo.version-test), clojure -M:check-version (demo.version-check), run in demo/cljfx

#### A reference shows one way to build it

- [demo/cljfx](../requirements/demo/cljfx/) is a working reference in cljfx, not a library: an app follows what it does, and takes its code as an example
- The part worth copying is [version.clj](../requirements/demo/cljfx/src/demo/version.clj), with the build step [stamp.clj](../requirements/demo/cljfx/tools/stamp.clj); [version_page.clj](../requirements/demo/cljfx/src/demo/version_page.clj) is the demo's own window
- Its window checks, [version_check.clj](../requirements/demo/cljfx/test/demo/version_check.clj), are the Verification lines below as code; an app's own checks ask the same
- `clojure -M:stamp && clojure -M:version`, run in `demo/cljfx`, opens it
- This requirement decides, not the reference: where the two differ, the reference is wrong

#### The app menu has About

- The first item of the app menu, the one named for the app left of File, is "About \<app name>", with a separator under it, as on every Mac app
- It opens the About window; chosen again while it is open, it brings that window to the front, and never opens a second
- No window of the app shows the version anywhere else

#### The About window shows the name, the version and the commit

- The app's name, large; under it "Version 1.4.2" and "Commit 91274ba", the short commit hash, 7 characters
- The commit is the one the app was built from, read at build time and built into the app; the app never asks git while it runs
- The release version is the one line of the app's `VERSION` file; the build writes it and the full commit hash into a file the app reads
- With no such file, as before a first build, both read "unknown", and the app says why on its error output
- A small window of its own, of a fixed size; its close button and Escape close it

#### A Copy button copies them

- Copy puts `v1.4.2 · 91274ba` on the clipboard: the release version, a middle dot, the short hash; for a bug report

#### Decided

- On 2026-11-14, by the owner:
- A 7 character hash: chosen over the full 40, and over a `-dirty` mark for a build from uncommitted changes
- In About, in the app menu: chosen over the File menu, which is not where a Mac app keeps it
- First tried as words in the main window's bottom right corner, on a dark capsule, with a switch in Settings, Appearance; the owner tried it and found it odd, so the corner shows nothing and there is no switch
- The window shows the name, the version, the commit and Copy: chosen over the same with no Copy

#### Verification

- A unit test reads the build's facts: the release version and the commit's first 7 characters, and the words Copy puts on the clipboard
- A window check reads the app menu: "About \<app name>" first, a separator under it
- It chooses About: one About window, with the name, the version and the commit; chosen again, still one
- It presses Copy and reads the clipboard: `v<version> · <hash>`
- It presses Escape: the About window is gone
- It reads every window: no version shown anywhere but About

### UI/UX

#### Windows and panes

- See [Window requirements](#window): tabs, several windows, floating windows, a session that comes back, and panes

#### Alignment, positioning and centering must be proper

#### Add a native file menu

#### The menu bar and the sidebar are each one list in the requirements

- Each is written down once, as a tree in its own requirement, in order
- A change that adds, moves, renames or removes an item updates that tree in the same change, so it always says what is there
- The sidebar's groups are the menu's, in the same order, so the two never disagree

#### Each titled sidebar section folds and unfolds

- Every section with a header folds; the top group, which has no header, always shows
- A chevron shows beside the header's name while the pointer is over the header; a click anywhere on the header folds or unfolds it
- A folded header keeps its name and shows the count of the rows it hides
- With a header focused, ← folds it and → unfolds it; the View menu has Fold All Sections and Unfold All Sections; all are keys Settings can rebind
- A selected row inside a folded section stays selected, and its folded header shows as selected, so the selection is never lost from sight
- Rows slide closed and open and the chevron turns in about 200 ms; with Reduce Motion or the app's animations off, it happens at once
- Which sections are folded is saved with the app's prefs and comes back on the next run

#### Try to follow native os style.

#### Use dividers and seperators where applicable

For example:

- Between panes, as [Panes resize](#window) says
- Between sections

#### Use icons when possible

- Icons come from [Phosphor Icons](https://phosphoricons.com), regular weight; one set, so every icon is drawn the same way
- Each is one filled path on a 256 px box, copied unchanged from [its repo](https://github.com/phosphor-icons/core) and named for its file there
- Its colour comes from the stylesheet, never from the path
- Its licence, MIT, is kept beside the icons and goes wherever they go
- [SF Symbols](https://developer.apple.com/sf-symbols/) are not used: their licence covers apps on Apple platforms, not a public repo or another platform
- The reference is [icons.clj](../requirements/demo/cljfx/src/demo/icons.clj), drawn by `icon-view` in [ui.clj](../requirements/demo/cljfx/src/demo/ui.clj)
- A unit test reads every icon as one path, and an unknown name as an error

#### Lists

- Each page remembers its view and sort between runs
- Any sort can be reversed
- Rows with no value sort last, whichever way the sort runs
- In a table, a click on a column heading sorts by that column: first click its natural way, second click reversed, third click back to no sort
- The sorted heading shows an arrow, ↓ its natural way and ↑ reversed; a click on another heading starts that column at its first click

#### A wide table scrolls sideways in its own area

- A table wider than its room scrolls sideways inside its own area, and never draws over the sidebar or another panel
- The first column stays in place; the other columns and their headings slide under it, together
- A scroll bar shows along the table's foot only while the table is wider than its room; a sideways swipe, or Shift and the wheel, scrolls it too
- Sorting and choosing a row still work wherever it is scrolled to, and keep the sideways position

#### Tooltip as needed

### Editing

#### Cut, Copy and Paste text

#### Undo and Redo

- Undo reverses the newest change, file writes included
- Redo makes again what undo took back, until a new change is made

#### Text boxes need to have full featured editor support

##### planned: Text boxes turn off macOS autocomplete

macOS changes no text while it is typed: what is typed is what is kept.

- No inline predictions, no autocorrect, no auto-capitals, no spelling or grammar marks, no text replacement, no browser autofill
- In a web view (Tauri, WKWebView) every text box carries writingsuggestions="false", autocorrect="off", autocapitalize="off", spellcheck="false" and autocomplete="off"
- In AppKit every NSTextView and NSTextField turns off automatic text completion, spelling correction, quote, dash and text replacement, and continuous spell checking
- A search box and a code box follow the same rule; no box opts back in

Evidence: WebKit's writingsuggestions attribute (<https://webkit.org/blog/15865/webkit-features-in-safari-18-0/>), spiked in Playwright WebKit (Safari 27.2) on 2026-11-15: writingSuggestions "false", spellcheck false; a textarea's spellcheck is on by default, so it is set on each box. diet_tracker's app/src/lib/TimePicker.svelte already sets autocomplete="off" and spellcheck="false".

- Proof (draft): Text boxes turn off macOS autocomplete
  - Tests: window check: every input and textarea in each window and sheet has the attributes below

#### Delete asks first

- A sheet says what will be deleted, with Delete and Cancel; Delete is red, and Return does not press it
- Deleted files go to the Trash, not away for good
- A delete is one change, so one undo brings everything back

#### A field error blocks Save, and invalid input is never written

### Pages

#### Settings page must have side bars where the settings are organized by category

#### History page that shows the pages navigated recently

#### Back and forward retrace pages visited, like a browser: keys, menu and mouse side buttons

### Things

- See [Component requirements](#component): what can be acted on, and buttons

### Text and Fonts

#### Use diffrent fonts as needed

#### Use different sizes as needed

- I should be able to adjust font size with keybinding
- I should be able to set default font size in settings page
- Autosave current font size as default font size on quit

#### Use different styles like bold, italics, headings, comments etc. as needed.

#### Choose font based on function and purpose.

#### Monospace for code and plain text.

#### Syntax highlight code always

#### Pick colors that enhance readability

#### Default font size for app is 16

#### Widths sized for text grow with the font size, so no label clips

#### Fonts need to look crisp and clear and easy to read.

#### Text must fit entirely within its container, with no clipping.

### Keyboard

#### Allow rebind of keys and shortcuts in settings

#### The app must have keyboard shortcuts

- Every common action has a key
- Unmodified keys work only when no text box has focus

#### A command palette (⌘K) reaches every action, screen and item

### Mouse

#### The mouse pointer appearance should change based on the thing below it while hovering, clicking or acting on that thing

#### Must support multi thing selection when applicable

- ⌘-click adds or removes one thing from the selection; ⇧-click selects a run
- An action on everything selected is one change, so one undo takes it all back

#### Must support drag and drop when applicable

#### The pointer should animate when applicable

#### Context menu where needed

### Data

#### Data lives seperately from the code

- Code and data live in separate repositories
- The data folder is configurable

#### Changes made to the data files outside the app show live, after 150 ms of quiet, with no restart

#### Try not not to store data unless it is necessary and performance critical

#### Data that can be computed should be computer

#### Compute rather than store

For example: Age. It can be calculated from date of birth. So no need seperate field for age.

#### Cache locally when possible

##### Cache all data which can be to be cached

##### Show loading screen during caching and wait till all data is cached locally.

##### Allow force refresh of cache

##### If caching involves downloading from internet then decide at what intervals.

Don't cache on every app start or you may hit bandwidth or api issues

### Testing

#### Write automated tests where sensible

#### Take screenshots or record a video of yourself for testing the app when automated test is not possible.

Use this as a last resort.

#### Testing should not hinder development speed

#### A window check sends its events the way a pointer does

- A mouse or key event goes to the scene, which picks what is under it; never straight to a control
- Sent straight to a control, an event reaches it even when something covers it, and the check passes on an app nobody can use: a divider that no real drag could move passed 83 such checks
- A check that sends a press where a control is, and reads that the control took it, proves the control can be reached
- A real-pointer proof exists beside the checks, [real_pointer.clj](../requirements/demo/cljfx/tools/real_pointer.clj): it moves the pointer, so it is run by hand, and after any change to what lies over what

### Development

- When applicable use REPL during development
- Follow Mockup based development for design

Design Idea -> Design Requirement -> Code Design Mockup -> Code Deisgn Approval -> Approve Requirement -> Start Implementation -> Review and Confirm if the output matches the mockups

## Touch and mobile

What changes for a web app used by touch, on a phone or a tablet.
Everything in [gui.org](#gui) still applies; this file adds to it, and where the two differ for touch, this file wins.

Not all of this is applicable to all apps. Pick what the app needs.

### General

#### For the PWA (Progressive Web App)

- One code base serves phone, tablet and desktop; no separate mobile site
- It runs in Safari on iOS and iPadOS and in Chrome on Android, the two latest major versions of each
- Follow Apple's [Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/) for iOS, as gui.org follows Apple Design for macOS

#### Touch is told apart from the mouse by what the device can do, never by its name

- CSS `@media (pointer: coarse)` and `(hover: none)` pick the touch rules; no user agent sniffing
- A device with both, a tablet with a trackpad, gets both: each input answers in its own way
- Pointer events (`pointerdown`, `pointerup`) handle mouse, pen and touch in one code path; no separate touch and mouse handlers

### planned: What gui.org rules become on the web

Every gui.org and components.org rule holds on the web, except as below.

#### Changed for the web

- Liquid Glass: CSS `backdrop-filter`, at most two glass layers on screen, so a mid-range phone keeps 60 fps
- Button sizes: 44 by 44 px or more
- Time and date pickers: the phone's own, through `<input type=date>` and `<input type=time>`
- Scroll areas: the browser's own scroll
- Windows, panes, tabs: one screen, bottom tabs, sheets from the bottom
- Narrow window: the tablet layout step
- Tooltip: a hold, or a small info button
- Right-click menu: a hold, as the gesture map says
- Restart the app: reload the page
- About: a line in Settings with the version and commit
- Keyboard shortcuts and ⌘K: only when a keyboard is attached; on a phone, a search box
- Save and restore session: the page address, plus browser storage
- Slow work off the UI thread: a Web Worker

#### Left out on the web

- The JavaFX toolkit, the file menu, the macOS menu bar
- Mouse pointer shapes, hover, several windows, macOS scroll settings

### Layout

#### The page fits the screen

- The viewport meta tag is `width=device-width, initial-scale=1, viewport-fit=cover`
- No page scrolls sideways at any width from 320 px up; a wide table scrolls in its own area, as gui.org says
- Pinch zoom is never turned off: no `maximum-scale` or `user-scalable=no`

#### Layout follows the width, in three steps

- Phone: below 600 px, one column
- Tablet: 600 px to 1023 px, a sidebar that folds away into a menu button
- Desktop: 1024 px and up, the desktop layout from gui.org
- A step is chosen by the width the app has, so a split screen or a rotated phone gets the right one

#### Content stays out of the notch and the home bar

- Padding uses `env(safe-area-inset-*)` on every edge, in portrait and landscape
- Nothing that can be tapped sits under the notch, the status bar or the home indicator

#### Height uses the dynamic viewport

- Full height panels use `100dvh`, never `100vh`, so the browser's own bars never hide the bottom of the page

#### Rotation keeps the place

- Turning the device keeps the scroll position, the selection and any text being typed

### Touch targets

#### Every tap target is 44 by 44 px or more

- The tappable area may be larger than what is drawn; padding counts
- Targets sit 8 px apart or more, so a thumb never hits two

#### The main actions are in reach of the thumb

- On a phone, the main action and the navigation sit in the bottom half of the screen
- Destructive actions are never next to the main action

#### Hover is never needed

- Anything shown on hover (a tooltip, a chevron, a row's buttons) is shown always or on tap when `(hover: none)`
- A tooltip becomes a long press, or a small info button beside the item

### Gestures

#### A tap answers at once

- The press shows within 100 ms, on `pointerdown`; the action runs on `pointerup` inside the target
- A finger that slides off the target before it lifts cancels the tap
- `touch-action: manipulation` on the page, so a tap never waits for a double tap zoom

#### Every gesture has a button too

- Swipe, long press and drag are shortcuts; each action they do is also reachable by a visible control

#### Gestures follow the platform

- Swipe a row sideways: shows its actions, as in iOS Mail; a full swipe does the first one, unless it deletes
- Long press: opens the context menu that gui.org gives a right click
- Pull down at the top of a list: refreshes, where the list can be refreshed
- Drag: a long press first lifts the thing, then it moves; a plain swipe still scrolls
- No gesture takes the screen edges: the browser and the system own them for back and home

#### planned: Each component kind has one gesture map

What tap, hold and swipe do is set by the component's kind, the same in every app.
Hold means 500 ms without moving more than 10 px.

- Button: tap runs it; hold runs its second action, with a fill that shows it coming, as components.org says; sliding off before lifting fires nothing
- Icon button: tap runs it; hold names it
- List row: tap opens it; swipe left shows its actions, a full swipe archives and never deletes; swipe right pins; hold lifts it, then a drag moves it
- List top: pull down refreshes, and a Refresh button does the same
- Chip: tap toggles it; hold, or right click, opens its menu
- Text field: the browser's own tap and hold, untouched
- Slider: tap the track jumps there; drag moves the thumb and never scrolls the page
- Sheet: drag the handle down, tap outside or press back to close it
- Page: swipe sideways goes to the next tab, only where nothing under the finger takes the swipe
- Never: double tap, or pinch on anything but the whole page
- An app maps each of its own elements to one of these kinds, in its own requirements
- Reference: [demo/web](../requirements/demo/web/src/touchdemo/core.cljs); run `npx shadow-cljs watch app` there, open <http://localhost:8030>

Evidence: demo/web (ClojureScript + Replicant, pointer events), checked on Playwright's Pixel 7 profile with touch events: tap, hold and swipe-left logged right, no page errors.

- Proof (draft): Each component kind has one gesture map
  - Tests: demo/web/e2e "gesture map"

#### Scrolling stays smooth and native

- Scroll is the browser's own, with its momentum; never redrawn in script
- `overscroll-behavior: contain` on inner scroll areas, so a sheet or list never drags the page behind it
- No `preventDefault` on `touchmove` except inside a drag that has started

### Text input

#### The right keyboard comes up

- Each field sets `type` and `inputmode` for what it holds: `email`, `tel`, `url`, `numeric`, `decimal`, `search`
- `enterkeyhint` names what Return does: `next`, `done`, `search`, `send`

#### Text never makes the page zoom

- Every text field's font is 16 px or more, so iOS Safari does not zoom in on focus

#### The keyboard never hides the field

- The field being typed in scrolls into view above the keyboard
- A bar fixed to the bottom moves up with the keyboard, using the `visualViewport` size

#### Autocomplete stays off

- As gui.org's "Text boxes turn off macOS autocomplete" says, and that covers the phone keyboards too

### Feedback

#### A press always shows

- A tapped control darkens or sinks, as gui.org's buttons do, and never only on hover
- `-webkit-tap-highlight-color: transparent`, so the browser's grey flash never doubles the app's own press

#### Loading never blocks the screen

- A slow network shows a spinner beside the words, as gui.org says, and the rest of the page stays usable

### Navigation

#### Back works the platform's way

- The browser's back, the iOS edge swipe and the Android back button all go back one page, as gui.org's back does
- Opening a sheet or a menu adds a history step, so back closes it first

#### Sheets come from the bottom on a phone

- A dialog on a phone is a sheet that slides up and can be swiped down to close
- On a tablet and on desktop it is the dialog gui.org gives

### Performance

#### The page is usable fast on a mid-range phone

- First load usable in 3 s or less over a slow 4G network, on a mid-range Android phone
- Taps answer, and scrolling runs, at 60 fps, as gui.org asks
- Images are sized for the screen they go to, with `srcset`, and load lazily below the fold

### Offline

#### planned: The app works offline

- A service worker keeps the app shell, so it opens with no network
- Changes made offline are kept and sent when the network comes back; nothing typed is lost
- The app says when it is offline, in one line, without blocking work
- Decide per app: not every app needs this

### Testing

#### Every layout step is checked at its width

- Playwright runs the window checks at 375 by 812 (phone), 820 by 1180 (tablet) and 1280 by 800 (desktop)
- Playwright's iPhone and Pixel device profiles turn on touch, so `pointer: coarse` is true in the check

#### A check finds what breaks the rules

- No sideways scroll on the page at 320 px wide
- Every visible control's box is 44 by 44 px or more on the phone profile
- Every text field's font is 16 px or more
- Every field has the `inputmode` or `type` its content needs

#### Gestures are checked as touches

- A check taps with `page.touchscreen.tap`, never a mouse click, on the touch profiles
- A swipe or long press is sent as touch events, the way a finger would, as gui.org's "A window check sends its events the way a pointer does" says

#### A real device is checked by hand

- Before a release, the app is opened on a real iPhone and a real Android phone, by hand, with a screenshot of each layout

## Window

Windows and their panes.
Part of the [GUI requirements](#gui), which say what holds for all of it: the toolkit, the look, motion and performance.

### The app must have a Window

#### A reference shows one way to build it

- [window.clj](../requirements/demo/cljfx/src/demo/window.clj) is a working reference in cljfx, not a library: an app follows what it does, and takes its code as an example
- Its rules are plain functions, tested without a window: `step`, `clamp-float`, `session` and `restore`
- Its window checks, [window_page_check.clj](../requirements/demo/cljfx/test/demo/window_page_check.clj), are the Verification lines below as code
- The reference passes its own checks: `clojure -M:test` and `clojure -M:check-window`, run in `demo/cljfx`
- This requirement decides, not the reference: where the two differ, the reference is wrong

#### A window has a size it starts at and a smallest size

- It opens at 960 by 600 px, and is never smaller than 480 by 400 px
- It is named for the page it shows
- A new window opens a step down and across from the last, so none hides another

#### A window has a title bar

- Every window has a title bar, the system's own or one drawn to match it
- It shows the window's name: the page it shows
- It drags the window, and a double press on it zooms the window as the system does
- It holds the close, minimise and zoom buttons, where the system puts them

#### A window can have tabs

- A new tab opens from the toolbar, the File menu and Cmd T, and becomes the one in front
- Each tab keeps its own page
- The tab bar shows once there are two tabs; with one tab there is none
- A tab closes from its own close button, the File menu and Cmd W
- Closing the tab in front moves to the one that takes its place, else the one before it; closing another leaves the one in front alone
- Closing a window's last tab closes the window
- Show Next Tab and Show Previous Tab are in the Window menu, each with a key, and go round at the ends

#### An app can have several windows

- A new window opens from the File menu and Cmd N
- Each window has its own tabs and its own floating windows
- [Panes](#panes) are the same in every window: their sizes, and which are hidden
- Closing the last window quits the app

#### Floating windows open inside the window

- A floating window opens from the toolbar, the Window menu and Cmd Shift F
- It opens over the page, clear of the sidebar and under the toolbar; each next one a step down and across
- It is named for the page it opened on, and keeps that page when the tab moves on
- It has a title bar and a close button, and no minimise
- Its title bar drags it; its bottom right corner resizes it, from 200 by 120 px to 480 by 360 px
- It never leaves the window: it stops at every edge, and when the window shrinks it is drawn back inside
- The place it was left at is kept: it goes back there when there is room again
- A press anywhere on it brings it to the front
- It does not block the page: a click beside it reaches what is under
- It fades in and grows slightly as it opens; under Reduce Motion it only fades

#### A window comes back as it was left

- The app reopens with the same windows, each at the same place and size
- Each with the same tabs, on the same pages, the same tab in front, and its floating windows where they were
- What is kept is plain text, one file, written whole or not at all
- It is written once things have been still for 400 ms, off the UI thread, and once more at quit; never at every change
- Closing the last window quits, and does not empty what is kept: the app comes back to the windows it had before
- Nothing kept is trusted: a window off every screen comes back where a first window opens, one too small at the smallest size, a page no longer known as the first page
- A file that cannot be read is moved aside, never written over, and the app opens as new

#### Verification

- Unit tests, with no window: tabs opening, closing and going round, each tab's own page, a window closing with its last tab, each window's own tabs, a floating window kept inside and its place kept, a session the same after a trip through text, and each untrusted thing in one coming back safe
- A window check reads each window's title bar: there, named for its page, with its three buttons
- A window check reads the File menu's commands, and that every command has a key
- It opens a tab, moves it to another page, goes back to the first and reads the first tab's own page; it closes a tab from its button, and reads the tab bar gone
- It opens a second window, gives it a tab and reads each window's own; it closes that window's tabs and reads one window left
- It opens a floating window and reads its place and size; drags it by its bar, past every edge; resizes it past both limits; opens a second and presses the first to the front
- It narrows the window with a floating window at its far corner and reads both inside; it clicks the page beside them and reads the click taken
- It moves and resizes the window, opens a tab and a floating window, writes the session, closes every window and opens what was kept: the same place, size, tabs, page and floating window
- It changes a page and reads the file: unchanged at once, changed 700 ms later; it closes every window and reads one window still kept
- It writes a file that cannot be read, and reads it moved aside and the session as none

### Panes

#### A reference shows one way to build them

- The panes of [window.clj](../requirements/demo/cljfx/src/demo/window.clj), the reference of [The app must have a Window](#the-app-must-have-a-window): a sidebar, a side panel and a pane under the page
- Their rules are plain functions, tested without a window: `layout`, `fit` and `clamp-size`
- This requirement decides, not the reference: where the two differ, the reference is wrong

#### Panes resize

- The divider between two panes drags to resize them, whether they sit side by side (width) or one above the other (height)
- A divider is 1 px to look at and 9 px to take hold of; over it the pointer shows which way it drags
- The divider is marked while it is dragged
- Each pane has a smallest and a largest size, and a size it starts at; a double click on its divider puts it back to that
- The size is remembered between runs; one kept outside the limits comes back within them
- A size is written when the drag ends, not at every move of it
- Sizes are kept with the session, in its one file: [A window comes back as it was left](#a-window-comes-back-as-it-was-left)
- The page keeps a smallest room of its own, 280 px wide: when a window has no room for the panes at their kept sizes, the side panel gives way first and then the sidebar, each down to its smallest; the kept sizes do not change

#### A pane can be hidden

- The sidebar and each side panel hide and show from a toolbar button, the View menu and a key: three ways, so a hidden pane is never lost
- The menu and the button say what they will do: Hide Sidebar, Show Sidebar
- A pane the user hid stays hidden at any width
- Which panes are hidden is remembered between runs

#### In a narrow window the sidebar shrinks to icons only and side panels hide

- A window under 720 px wide is narrow
- The sidebar shrinks to 56 px, icons only; each icon keeps its name as a tooltip
- Side panels hide, their dividers with them; a side panel's button is off meanwhile, and its tooltip says why
- Wide again, each comes back at its kept size
- The change glides in 200 ms; under Reduce Motion it happens at once
- A drag, or the window being resized, never glides: the pane follows at once

#### Verification

- Unit tests, with no window: the narrow rule at 719 and 720 px, a hidden pane at any width, the page's room at 760 px, a pane's limits, a divider following the pointer
- A window check drags each divider and reads the pane: following the pointer, stopping at its smallest and its largest, and back to its start on a double click
- It reads the kept size while dragging and after letting go: nothing, then the size; and a size kept outside the limits read back within them
- It sets both side panes to their largest at 760 px and reads the page: 280 px or more
- It narrows the window to 600 px and reads the sidebar 100 ms later, between 56 px and its full width, then at 56 px with no words and a tooltip; the side panel at 0 and its button off
- It widens the window and reads both back at their kept sizes; with Reduce Motion on, it reads the sidebar at 56 px 70 ms after narrowing
- It hides the sidebar from the toolbar, reads the View menu's "Show Sidebar", and fires it
- It hides a side panel, closes every window and opens what was kept: still hidden
- It counts frames through two glides each way and a divider drag: 55 a second or more

## Component

The things a window is made of.
Part of the [GUI requirements](#gui), which say what holds for all of it: the toolkit, the look, motion and performance.

### Things I can act on look different from things I cannot

- Anything clickable or actable looks it: a button, a link, a control
- Nothing that cannot be acted on looks clickable
- A clickable button looks like a button

### Buttons

#### A reference shows one way to build them

- [demo/cljfx](../requirements/demo/cljfx/) is a working reference in cljfx, not a library: an app follows what it does, and takes its code as an example
- The part worth copying is [ui.clj](../requirements/demo/cljfx/src/demo/ui.clj), with the look in [glass.css](../requirements/demo/cljfx/src/demo/glass.css); [button.clj](../requirements/demo/cljfx/src/demo/button.clj) is the demo's own page
- Its window checks, [window_check.clj](../requirements/demo/cljfx/test/demo/window_check.clj), are the Verification lines below as code; an app's own checks ask the same
- The reference passes its own checks: `clojure -M:test` and `clojure -M:check`, run in `demo/cljfx`
- This requirement decides, not the reference: where the two differ, the reference is wrong

#### One tinted glass button a page, the main action; every other toolbar button is regular glass, and a button in the page is plain

#### Buttons answer a press

- Hover: the colour eases to its hover shade in 120 ms
- Press: the button sinks to 97% of its size and 1 px down, in 120 ms
- Hold: it stays sunk for as long as it is held
- Release: it springs back in 420 ms, overshooting a little before it settles
- Space on a focused button answers the same way as the mouse
- Return presses the main button, wherever the focus is; it sinks once and springs back
- While a question is open, as before a delete, Return presses nothing
- Dragged off while held it rises, and back over the button it sinks again; let go off the button, nothing fires
- Escape lets go of a held press: the button rises and nothing fires, until the mouse or the key is up
- Under Reduce Motion it only changes colour

#### A held button fires its second action

- A button may have a second action, different from its click; a button with none only stays sunk
- Held for 500 ms, the second action fires, and letting go then does not fire the click as well
- A fill grows across the button while the hold counts, from 150 ms to 500 ms, so the second action is seen coming; a quick click is over before it shows
- Let go early and the fill fades away; under Reduce Motion it fades in where it would have grown
- A button with a second action shows a small mark at its trailing edge, so the action is not found by accident
- Its tooltip names both: what a click does and what a hold does
- The second action is also on the button's right-click menu, so the keyboard and a trackpad reach it
- A second action never deletes or overwrites; those stay a click that asks first

#### Button states

- Focused: a ring in the accent colour, on keyboard focus
- Disabled: 45% opacity; it answers no hover, press or hold
- A disabled button's tooltip says why it is off
- Busy: while its action runs it shows a spinner beside its words and does not fire again; the words end in an ellipsis, "Saving…"
- A busy button does not sink or change colour on a press: it never looks as if it took one
- Done: the button says so with a tick for 1 s, "Saved", and takes no press meanwhile
- Failed: the button turns into "Retry" in red and stays so until pressed; its tooltip says what failed
- Going busy and back is smooth: the button glides to its new width in 220 ms while the spinner opens beside the words and fades in
- The words never blank, and neither the button nor its neighbours jump
- Under Reduce Motion the width changes at once and the spinner only fades

#### Button kinds

- Main: tinted glass, one a page
- Plain: regular glass in a toolbar, a solid fill in the page
- Destructive: red words, never tinted and never the main one; they read at 4.5:1 like any others
- Icon and words: the icon leads
- Icon alone: a circle, with a tooltip that names it

#### Button sizes

- Every button on a page is one height, 44 px
- A button's words stay on one line: they never wrap, and the button grows wide enough to hold them with its shortcut
- A button with words is 76 px wide or wider
- Buttons in a pair, as Cancel and Delete, are equal width: that of the wider
- Where a row runs out of room, it scrolls or moves buttons into a menu; it never squeezes one

#### Verification

- A window check presses a button and reads its size: 100% at rest, 97% pressed, 97% after 1.5 s held, 100% once released
- It holds a button with a second action for 500 ms and counts one second action and no click
- It holds a button with no second action for 500 ms, lets go, and counts one click
- It presses a disabled button and counts nothing, with the size still 100%
- With Reduce Motion on, a press leaves the size at 100%
- It clicks a button that goes busy and reads its width 110 ms later: wider than at rest, narrower than once settled
- It reads the hold fill 300 ms into a hold: started, and not yet full
- It presses, sends a leave, an enter and a leave, and lets go: 100%, 97%, and nothing fired
- It presses, sends Escape and lets go: 100%, and nothing fired
- With the focus on another button it sends Return: the main button sinks and counts one click, and the focused one counts none
- It sends Space down, Escape, and Space up to a button: 97%, then nothing fired
- A window check reads the height of every button in each window and sheet: 44 px, all equal
- It narrows the window to its minimum width and reads each button: one line of words, 44 px tall
- It presses a busy button: 100%. It waits out the save: "Saved", then "Save"
- It makes a save fail: "Retry", nothing saved; it presses Retry and the save is counted
- It reads the tooltip of a disabled button and of one with a second action, and fires the right-click menu's item
- It reads the heights, the icon button's width, the words buttons' widths and a pair's two widths
- It draws each button without its words and reads the contrast of the words over the middle of it, at rest and under the pointer: 4.5 or more
- It counts frames through three presses and three busy glides: 55 a second or more
- With Reduce Motion on, it clicks a button that goes busy and reads its width 80 ms later: already settled

#### Ideas

- Read: [Button Ideas](buttons.png)

### Sliders

#### A reference shows one way to build them

- [demo/cljfx](../requirements/demo/cljfx/) is a working reference in cljfx, not a library: an app follows what it does, and takes its code as an example
- The part worth copying is [slider.clj](../requirements/demo/cljfx/src/demo/slider.clj), with the look in [glass.css](../requirements/demo/cljfx/src/demo/glass.css); [slider_page.clj](../requirements/demo/cljfx/src/demo/slider_page.clj) is the demo's own page
- Its window checks, [slider_check.clj](../requirements/demo/cljfx/test/demo/slider_check.clj), are the Verification lines below as code; an app's own checks ask the same
- The reference passes its own checks: `clojure -M:test` and `clojure -M:check-slider`, run in `demo/cljfx`; `clojure -M:slider` opens it
- This requirement decides, not the reference: where the two differ, the reference is wrong

#### A slider sets one value between two ends

- One thumb on a level track; the value is continuous, any point between the two ends
- A slider has a label that names what it sets, and a default value
- No stepped slider and no slider with two thumbs: a need for one is a new requirement

#### A slider looks like a track and a glass capsule

- The track is 4 px to look at and 44 px to take hold of, the height of a button
- The thumb is a glass capsule, 28 by 20 px
- The track is filled in the accent colour from its start up to the thumb; the rest is plain
- A slider is 120 px wide or wider
- A notch on the track marks the default value
- Over the thumb the pointer is an open hand, and a closed hand while it drags

#### The thumb answers a press

- Hover: the thumb eases to its hover shade in 120 ms
- Press: the thumb grows to 110% of its size in 120 ms, and stays so for as long as it is held
- Moving, the thumb stretches along the track, up to 36 px wide, and more the faster it moves; still again, it eases back in 220 ms
- Release: it springs back to 28 by 20 px in 420 ms, overshooting a little before it settles
- Under Reduce Motion it neither grows nor stretches; it only changes colour

#### The thumb swings where it stops

- Stopped after a move, the thumb swings on past where it stopped, back short of it, and settles there, as a pendulum
- It stops when it is let go while moving, when it is held still for 40 ms in a drag, and at the end of its glide to a press on the track
- The first swing is 10% of how far the thumb moved, the same way: 100 px moved swings 10 px, 200 px swings 20 px; there is no most
- How far it moved is counted from the press or from the last stop, whichever is later, and is how far the thumb went: past an end, the pointer adds nothing
- A glide to a press on the track has moved the thumb as far as it glided
- Five swings, each about half the one before; the first is furthest out at 120 ms, and the last ends where the thumb rests, 1400 ms on
- The swing is only the thumb, its fill and its bubble: the value stays where the pointer put it, and so does what is written
- The thumb swings no further than either end
- A swing under 0.5 px is not shown, and let go after a stop, with no move since, it does not swing again
- A press on a swinging thumb catches it where it is drawn, and a drag goes on from there; let go without a move, it eases home in 420 ms
- A move, a press on the track, a double click or Escape ends a swing, and the thumb is where the value puts it
- A double click and the keyboard move the thumb without a swing
- Under Reduce Motion the thumb never swings

#### A drag moves the thumb

- The thumb follows the pointer at once; a drag never glides, and swings only where it stops
- The drag goes on with the pointer above or below the slider, and off the window
- Past an end the thumb stops at that end, and takes up again when the pointer comes back
- Within 4 px of the notch the thumb snaps to the default value
- A press on the track, away from the thumb, glides the thumb to the pointer in 120 ms, swings there, and the same press goes on as a drag
- Under Reduce Motion the thumb lands there at once
- A double click puts the slider back to its default value; the thumb glides there in 120 ms, and at once under Reduce Motion
- Scrolling over a slider does not move it: the page under it scrolls

#### A bubble shows the value while it changes

- At rest a slider shows no number
- While the thumb is held a bubble sits over it with the value in its unit, "40%", and follows it
- The bubble fades in over 120 ms on the press and out over 120 ms on the release
- After a key press it shows for 1 s
- The bubble is glass, and its words read at 4.5:1
- It is never clipped by the window's edge, nor by the edge of a scrolling area the slider is in: near one it slides sideways and stays whole, 4 px clear
- The slider's tooltip says the value too, so it is read without a change

#### The value is written when the drag ends

- What the slider sets follows the thumb live, through the whole drag
- The value is written once, on the release, not at every move
- Escape during a drag puts the thumb and what it sets back to where the drag began, and writes nothing; the rest of that press does nothing
- One drag is one step for Undo, and so is a double click
- A double click on the track is one step too: its first click moves the thumb and is written, and the second, within 500 ms, joins that step

#### The keyboard moves a focused slider

- Left and Down lower it by 1% of the range, Right and Up raise it by 1%
- With Shift they move it 10%
- Home goes to the low end and End to the high end
- Each key press writes the value; a held key writes once, when it is let go
- Key presses less than 1 s apart are one step for Undo
- A key at an end does nothing, and nothing is written

#### Slider states

- Focused: a ring in the accent colour round the thumb, on keyboard focus
- Disabled: 45% opacity; it answers no hover, press, drag or key, and shows no bubble
- A disabled slider's tooltip says why it is off

#### Verification

- A window check sends its events the way a pointer does
- It drags the thumb to the middle, holds it still and reads the value: half the range; and the thumb 100 ms later: past the pointer, by no more than 10% of the move; and 1.1 s on: under the pointer
- It reads the value written during the drag and after letting go: nothing, then the value
- It reads what the slider sets halfway through a drag: already following
- It drags past each end and reads the value: the low end, the high end, and no further
- It drags, sends Escape and lets go: the value from before the drag, and nothing written
- It presses the track away from the thumb and reads the thumb 30 ms later: left its place, not yet under the pointer; 280 ms on: past the pointer, by no more than 10% of the glide; 1.8 s on: under the pointer; then it drags on and the thumb follows
- It drags to 3 px from the notch and reads the value: the default; and to 6 px from it: not the default
- It reads the notch's place and the fill's width: at the default, and up to the thumb
- It double clicks and reads the value: the default, written once
- It scrolls over the slider and reads the value and the page: the value as before, the page moved
- It reads the thumb's size at rest, held, 1.5 s held and once released: 100%, 110%, 110%, 100%
- It reads the thumb's width in a fast drag and once settled: wider than 28 px, then 28 px
- It reads the bubble at rest, held, and after the release: none, the value in its unit, none
- It drags to each end and reads the bubble's edges: inside the window, and at the low end no longer centred on the thumb
- It sends Right, Shift+Right, Home and End to a focused slider and reads the value after each: up 1%, up 10%, the low end, the high end
- It sends Left at the low end and counts nothing written
- It sends Right down five times and up once: moved 5%, written nothing until the key is up, then once
- It sends Right three times and reads the steps for Undo: one; it sends Undo and reads the value from before them
- It drags once, sends Undo and reads the value: the one before the drag
- It presses, drags and sends keys to a disabled slider: the value as before, no bubble, the thumb at 100%; and reads its opacity: 45%
- It reads the pointer over the thumb and during a drag: an open hand, a closed hand
- It reads the thumb's colour under the pointer, and its edge on keyboard focus: changed, and the accent colour
- It reads each slider's label: what it sets
- With Reduce Motion on, it presses the thumb and reads its size: 100%; it presses the track and reads the thumb 20 ms later: already under the pointer
- It reads the heights, the track's thickness, the thumb's size and the slider's width
- It reads the tooltip of a slider and of a disabled one
- It draws the bubble without its words and reads the contrast of the words over the middle of it: 4.5 or more
- It counts frames through three drags and three track presses: 55 a second or more

### Time pickers

#### A reference shows one way to build them

- [demo/cljfx](../requirements/demo/cljfx/) is a working reference in cljfx, not a library: an app follows what it does, and takes its code as an example
- The part worth copying is [time_picker.clj](../requirements/demo/cljfx/src/demo/time_picker.clj), with the look in [glass.css](../requirements/demo/cljfx/src/demo/glass.css); [time_picker_page.clj](../requirements/demo/cljfx/src/demo/time_picker_page.clj) is the demo's own page
- Its window checks, [time_picker_check.clj](../requirements/demo/cljfx/test/demo/time_picker_check.clj), are the Verification lines below as code; an app's own checks ask the same
- The reference passes its own checks: `clojure -M:test` and `clojure -M:check-time-picker`, run in `demo/cljfx`; `clojure -M:time-picker` opens it
- This requirement decides, not the reference: where the two differ, the reference is wrong

#### A time picker sets one time of day

- One field that is typed into, with wheels under it; the value is an hour and a minute, any minute of the day
- A time picker has a label that names what it sets
- Where the time is optional the field may be empty, and then shows a hint in grey, "9:30 AM"
- Where it is not, an emptied field is not taken: the line under it says "Not a time. Try 9:30 or 2130"
- No date, no seconds, no time zone, no pair of a start and an end, no ready-made choices such as "In 1 hour", and no clock face: a need for one is a new requirement

#### A time picker looks like a field

- The field is 44 px tall, the height of a button, and 120 px wide or wider
- The time is shown the way macOS is set to show it: "9:30 AM", or "09:30" on a 24-hour clock
- macOS's own 24-hour switch decides; with it unset, the region's habit does
- On a 12-hour clock twelve o'clock is shown with its word, "12:00 PM, noon" and "12:00 AM, midnight", in the field; on the wheels it is "12"
- Over the field the pointer is a text cursor

#### Typing sets the time

- Focus selects all of the field's text, so typing replaces it
- These are all taken: "9a", "930a", "9:30 am", "9.30p", "9p", "2130", "21:30", "noon", "midnight"; in either case, with or without a space
- Both the 12-hour and the 24-hour forms are taken, whatever macOS is set to show
- An hour from 1 to 12 with no AM or PM is never guessed at: "3", "3:30", "930" and "12" are not taken, and the line under the field asks "AM or PM? Type 3a or 3p"
- An hour from 13 to 23, and 0, is taken as it stands on the 24-hour clock
- Where macOS shows a 24-hour clock every hour is taken as it stands: "3" is 03:00
- Return, Tab or a click elsewhere takes what is typed, and the field then shows it in full: "930a" becomes "9:30 AM"
- Minutes past 59, hours past 23, and AM or PM after an hour of the 24-hour clock, "13p", are not a time
- What cannot be read as a time is not guessed at: the text stays, the field's edge turns red, a line under it says "Not a time. Try 9:30 or 2130", and nothing is written
- Typing again clears the red edge and the line

#### Wheels set the time

- The wheels open under the field on a click in it, on typing, and on Down; Tab into the field does not open them
- On a 12-hour clock there are three wheels side by side: hour 1 to 12, minute 00 to 59, AM and PM; on a 24-hour clock two: hour 00 to 23, minute 00 to 59
- A band across the middle marks the time; rows above and below curve away, shorter and fainter, as on a drum
- Five rows are to be seen on each wheel, or all of its rows where it has fewer, as AM and PM; the words in the band read at 4.5:1
- The hour and minute wheels go round: 59 runs on to 00, 12 to 1; AM and PM stop at their ends and spring back when pulled past
- They open showing the field's time; from an empty field, the next whole minute after now
- A drag turns a wheel and a fling coasts, slows and settles on a row; a scroll over a wheel turns it and it settles once the scroll stops; a click on a row brings it to the band
- Each turn eases onto its row, in 250 ms or less once let go; under Reduce Motion it lands at once
- A focused wheel turns one row on Up and Down; Left and Right move between wheels
- Typing a whole time turns the wheels to it; text that is not yet a time leaves them where they are
- Turning a wheel changes the field's text as it settles, and selects all of it, so typing still replaces it
- The wheels are glass, as wide as their words need and never narrower than the field
- They are never clipped by the window's edge: with no room under the field they open over it, and stay whole, 4 px clear
- Scrolling over the field alone scrolls the page under it, and the time does not change
- Return, Tab, Escape or a click elsewhere closes them; they open and close with a 120 ms fade, and at once under Reduce Motion

#### The time is written when it is taken

- The time is written once, when it is taken, not at every key
- Taking the time the field already had writes nothing
- Escape writes nothing
- A time set on the wheels is taken when they close by Return, Tab or a click elsewhere; turning them writes nothing while they are open
- Escape closes the wheels and puts the field back to the time it had
- One taken time is one step for Undo
- Command-Z while text is typed undoes the typing, in the field; with nothing typed it is the app's Undo

#### Time picker states

- Focused: a ring in the accent colour, on keyboard focus
- Disabled: 45% opacity; it answers no click and no key, and opens no wheels
- A disabled time picker's tooltip says why it is off
- Not a time: a red edge and the line under it, until the text changes or Escape puts the old time back

#### Verification

- A window check sends its keys and clicks the way a person does
- It gives the field the focus and reads what is selected: all of its text
- It types each of "9a", "930a", "9:30 am", "9.30p", "9p", "2130", "21:30", "noon" and "midnight", sends Return, and reads the field and the written time after each
- It types "3" and sends Return, and again with "3:30": the text still there, a red edge, "AM or PM? Type 3a or 3p", nothing written
- It empties a field that is not optional and sends Return: the line under it, nothing written
- It types "13" and "0" and reads the times: 1:00 PM and midnight
- It reads what is written while it types and after Return: nothing, then the time, once
- It types "abc" and sends Return: the text still there, a red edge, the line under it, nothing written; it types a digit and the edge and the line are gone
- It types, sends Escape twice, and reads the field: the time from before, nothing written
- It takes the time the field already had and counts nothing written
- It types "6p" and clicks elsewhere on the page: 6:00 PM, written
- It clicks the field and reads the wheels: open, five rows each and two on AM and PM, the field's time in the band
- It sends Tab into the field and reads the wheels: closed; it sends Down: open
- It sets a 24-hour clock and reads the wheels: two, hour 00 to 23
- It sends Up on the minute wheel at 00 and reads it: 59; on the hour wheel at 1: 12
- It drags the minute wheel two rows and lets go slowly: two minutes on, in the band and in the field, nothing written
- It flings a wheel and reads it every frame until it rests: moving, then still, on a whole row
- It scrolls over a wheel, stops, and reads it 300 ms later: settled on a row
- It clicks the row under the band and reads the time: one row on
- It pulls AM and PM past its end and reads it: back on its row
- It types "207p" and reads the wheels: 2, 07, PM
- It turns the wheels, sends Return and reads what is written: the wheels' time, once
- It turns the wheels and sends Escape: the field and the time from before, nothing written
- It puts the field at the window's bottom edge, opens the wheels and reads their edges: inside the window, over the field
- It draws the wheels without their words and reads the contrast of the band's words: 4.5 or more
- It opens the wheels and reads them 40 ms later: fading in; with Reduce Motion on, 20 ms later: fully there
- It counts frames through three flings: 55 a second or more
- It sets a 24-hour clock and reads the field: "09:30"; it types "9p" and reads "21:00"; it types "3" and reads "03:00"
- It reads the field at twelve: "12:00 PM, noon" and "12:00 AM, midnight"; and the hour wheel: "12"
- It empties an optional field and reads the hint and what is written: "9:30 AM" in grey, and no time
- It takes a time, sends Undo and reads the field: the time from before
- It clicks and sends keys to a disabled time picker: the time as before, no wheels; and reads its opacity: 45%
- It reads the field's height and width, and its edge on keyboard focus: the accent colour
- It reads the tooltip of a disabled time picker

#### Decided

- On 2026-11-13, by the owner, from three choices:
- An hour alone is asked about, not guessed: chosen over a daytime guess, 7 to 11 AM and 12 to 6 PM, and over whichever comes next on the clock, which gives a different answer at different times of day
- One time only: a start and an end together is a new requirement
- No quick buttons such as "Now" or "In 1 hour": they can be added later as a new requirement
- Up and Down move through the list, and do not step the minute: undone on 2026-11-16, below
- On 2026-11-16, by the owner, from a clock dial and iOS-style wheels tried side by side (demo.compare-page): wheels, as faster to pick; they replace the 15 minute list, and typing stays
- Up and Down turn the focused wheel one row: an exact minute no longer has to be typed

#### Ideas

- Why a typed field and not a dial: [NN/g on date input](https://www.nngroup.com/articles/date-input/), [Material's 24-hour clock research](https://material.io/blog/24-hour-clock-design-research), [Apple's pickers guidance](https://developer.apple.com/design/human-interface-guidelines/pickers)
- Why a short list and words for twelve: [Miksovsky on time dropdowns](https://jan.miksovsky.com/posts/2010/10-11-reconsidering-stock-controls-to-create-an-optimized-user-experience), [Time and Date on AM and PM](https://www.timeanddate.com/time/am-and-pm.html)
- Why wheels: [Apple's pickers guidance](https://developer.apple.com/design/human-interface-guidelines/pickers); tried against a dial in demo/cljfx, compare_page.clj

### Date pickers

- Proof: Date pickers
  - Tests: clojure -M:test (demo.date-picker-test), clojure -M:check-date-picker (demo.date-picker-check), run in demo/cljfx

#### A reference shows one way to build them

- demo/cljfx gets date_picker.clj, the part worth copying, and date_picker_page.clj, the demo's page, styled in glass.css
- `clojure -M:date-picker` opens it; `clojure -M:check-date-picker` runs its window checks
- This requirement decides, not the reference

#### A date picker sets one day

- One field that is typed into, with a month calendar under it; the value is a year, a month and a day
- A date picker has a label that names what it sets
- Where the date is optional the field may be empty, and then shows a hint in grey, "Fri, 20 Nov 2026"
- No time, no time zone, no range of a start and an end, no words such as "tomorrow" or "next fri": a need for one is a new requirement

#### A date picker looks like a field

- The field is 44 px tall, the height of a button, and 180 px wide or wider, with a calendar mark at its right end
- The date is shown the way macOS's region shows a medium date, with the weekday: "Fri, 20 Nov 2026"
- Over the field the pointer is a text cursor; over the calendar mark it is an arrow

#### Typing sets the date

- Focus selects all of the field's text, so typing replaces it
- These are all taken: "20 nov", "nov 20", "20 November 2026", "2026-11-20", and the region's short form, "20/11/2026" or "11/20/2026"; in either case
- A day and month with no year is the next such day from today, today included
- Return, Tab or a click elsewhere takes what is typed, and the field then shows it in full
- What is not a date, "31 Nov" or "abc", is not guessed at: the text stays, the edge turns red, a line under it says "Not a date. Try 20 Nov or 2026-11-20", and nothing is written
- Typing again clears the red edge and the line

#### A calendar offers days

- The calendar opens under the field on a click in the field or on its mark, and on Down; Tab into the field does not open it
- It shows one month: its name and year, the weekday initials, and six weeks at most; days of the months either side are dim and can be taken
- The week starts on the day macOS's region starts it
- It opens on the field's month with its day marked; from an empty field, on today's month with today marked
- Today has a ring in the accent colour; the taken day is filled with it
- ‹ and › go a month back and on; Page Up and Page Down do the same from the keyboard
- The arrow keys move the mark a day or a week, into the next month where needed; Return takes the marked day, and a click takes the day under it
- "Today" at its foot marks and takes today
- Escape closes an open calendar and leaves the typed text; a second Escape puts the field back to the date it had
- The calendar is glass, its words read at 4.5:1, it is never clipped by the window's edge, and it opens and closes with a 120 ms fade, at once under Reduce Motion

#### The date is written when it is taken

- The date is written once, when it is taken, not at every key or mark move
- Taking the date the field already had writes nothing; Escape writes nothing
- One taken date is one step for Undo

#### Date picker states

- Focused: a ring in the accent colour, on keyboard focus
- Disabled: 45% opacity; it answers no click and no key, opens no calendar, and its tooltip says why it is off
- Not a date: a red edge and the line under it, until the text changes or Escape puts the old date back

#### Verification

- A unit test reads each typed form above, and "31 Nov", "abc" and an empty field, into a date or a refusal
- A unit test reads a day and month with no year against a fixed today: the next such day
- A window check types "20 nov" and sends Return: the field reads "Fri, 20 Nov 2026" and the date is written once
- It types "31 Nov" and sends Return: the text still there, a red edge, the line under it, nothing written
- It clicks the field: the calendar open on the field's month, its day marked, today ringed
- It sends Right, Down and Return: the day eight days on is taken
- It sends Page Down: the next month shown; it clicks a dim day: that day taken
- It clicks "Today": today taken, the calendar closed
- It sends Escape twice after typing: the date from before, nothing written
- It takes a date, sends Undo: the date from before
- It sets a Monday-first region and reads the first weekday column: Monday
- It clicks and sends keys to a disabled date picker: no calendar, the date as before, 45% opacity
- It reads the field's height and width, the calendar's edges at the window's bottom, and the contrast of its words: 44 px, 180 px or more, inside the window, 4.5 or more
- It opens the calendar and reads it 40 ms later: fading in; with Reduce Motion on, 20 ms later: fully there

Evidence: JavaFX 27.0.1, in demo/cljfx/deps.edn, ships javafx/scene/control/DatePicker.class and com/sun/javafx/scene/control/DatePickerContent.class (a month grid on java.time.LocalDate and WeekFields); requirements/demo/cljfx/src/demo/time_picker.clj already builds a typed glass field with a list under it and its window checks in test/demo/time_picker_check.clj; mockup shown and approved on 2026-11-15

### Scroll areas and scroll bars

- Proof: Scroll areas and scroll bars
  - Tests: clojure -M:test (demo.scroll-test), clojure -M:check-scroll (demo.scroll-check), run in demo/cljfx

#### A reference shows one way to build them

- [demo/cljfx](../requirements/demo/cljfx/) is a working reference in cljfx, not a library: an app follows what it does, and takes its code as an example
- The part worth copying is [scroll.clj](../requirements/demo/cljfx/src/demo/scroll.clj), with the look in [glass.css](../requirements/demo/cljfx/src/demo/glass.css); [scroll_page.clj](../requirements/demo/cljfx/src/demo/scroll_page.clj) is the demo's own page
- Its window checks, [scroll_check.clj](../requirements/demo/cljfx/test/demo/scroll_check.clj), are the Verification lines below as code; an app's own checks ask the same
- The reference passes its own checks: `clojure -M:test` and `clojure -M:check-scroll`, run in `demo/cljfx`; `clojure -M:scroll` opens it
- This requirement decides, not the reference: where the two differ, the reference is wrong

#### A scroll area shows content larger than its room

- A scroll area is a fixed room with content that moves inside it, up and down, sideways, or both
- It scrolls only along an axis where the content is larger than the room; along the other it does not move, and shows no bar
- Content never draws outside its scroll area, over a sidebar, a toolbar or another panel
- The window scrolls nothing as a whole: each panel that can overflow is its own scroll area, and the sidebar, the toolbar and the page each scroll on their own
- [A wide table scrolls sideways in its own area](#gui) is one of these, and holds to all of this

#### macOS's scroll settings are followed

- System Settings, Appearance, "Show scroll bars" decides when the bars show: on scrolling only, always, or by what is plugged in, as macOS decides it
- "Click in the scroll bar to" decides what a click in the track does: go a page, or go to the spot clicked; Option and a click does the other
- The scroll direction is macOS's, natural or not; the app never turns it round
- A change to any of these takes hold within 1 s, with no restart

#### A scroll bar looks like a thin capsule

- The knob is a capsule, its length the room's share of the content, and never shorter than 24 px
- Its place along the track is the room's place along the content
- Shown only when scrolling, the bar floats over the content at its edge, with no track: the knob is 7 px thick, 3 px in from the edge
- With the pointer over the bar, the knob grows to 11 px and a track shows under it, in 120 ms
- Shown always, the bar takes its own 15 px beside the content, with a track, and the content is that much narrower; where both bars show, a square fills the corner
- In the dark theme the knob is light on dark, and reads at 3:1 or more against what is under it
- No arrow buttons at the ends of a bar
- Over a bar the pointer is the arrow, not a hand

#### A scroll bar shows while it is needed

- Shown only when scrolling, a bar shows the moment its area scrolls, and fades out over 300 ms once 1 s has passed with no scroll and no pointer over it
- It shows too, for 1 s, when its area first appears or its content grows, so it is seen that there is more
- With the pointer over the bar's 16 px edge it stays, and fades 1 s after the pointer leaves
- Faded out, a bar is not there for a click; its 16 px edge is, and brings it back

#### The trackpad and the wheel scroll the area under the pointer

- A swipe or the wheel scrolls the area under the pointer, not the one with the focus
- The content follows the fingers at once, one to one, with no lag and no smoothing added
- A trackpad scroll moves by the pixel and stops wherever the fingers leave it, never snapping to a line or a row
- Let go with speed, it glides on and slows to a stop, as macOS's own areas do; a touch on the trackpad stops the glide where it is
- A notched wheel moves the content a line, 40 px, a notch, eased over 100 ms; at once under Reduce Motion
- A sideways swipe scrolls sideways; Shift and the wheel do too
- A swipe more along one axis than the other keeps to that axis for the rest of the gesture, so a down swipe does not drift sideways

#### The edge gives, then springs back

- A trackpad swipe past an end pulls the content on, less and less the further it goes, and lets go back to the end in 300 ms, as a rubber band
- A glide that reaches an end bounces there in the same way
- A notched wheel stops at the end, with no give
- The pull is never more than a third of the room
- Under Reduce Motion the pull still follows the fingers, since they move it, but a glide stops at the end with no bounce

#### A scroll inside a scroll goes to the right one

- A gesture stays with the area it started in until the fingers lift and its glide ends, even when that area reaches its end
- A new gesture over an inner area that is at its end, pushing on past it, scrolls the area round it
- A gesture along an axis an inner area cannot scroll goes at once to the area round it: an up swipe over a wide table scrolls the page
- Over a control that is not a scroll area, a slider or a closed time picker, the area under it scrolls

#### A drag on the knob moves the content

- A press on the knob holds it, and the content follows the pointer at once, keeping where on the knob it was taken
- The drag goes on with the pointer off the bar and off the window, and never jumps back
- Past an end the knob stops, and takes up again when the pointer comes back
- Escape during a drag puts the content back where the drag began
- A press in the track, away from the knob, goes a page that way, or to the spot clicked, as macOS is set; held, it goes on a page each 100 ms until the knob is under the pointer
- A page is the room less one line, 40 px, so the last line seen is still there

#### The keyboard scrolls a focused area

- With the focus in an area and not in a text field, Up and Down scroll a line, Left and Right a line sideways
- Page Up and Page Down, Space and Shift and Space go a page; Option and Up or Down go a page too
- Home and End go to the top and the bottom; Command and Up or Down do too
- A key scroll eases over 150 ms, and is at once under Reduce Motion; a held key scrolls on smoothly, with no steps
- In a text field these keys move the caret, and the area follows the caret

#### What is wanted is brought into sight

- A control given the focus by Tab, out of sight, is scrolled into sight with 16 px clear of the edge, by the least that does it
- A row chosen by the keyboard, a search hit, or a thing jumped to from the command palette is scrolled into sight the same way
- A drag held within 24 px of an area's edge scrolls it that way, faster the nearer the edge, for drag and drop and for choosing many rows
- The area never scrolls on its own otherwise: new content arriving does not move what is in view

#### The place is kept

- Content that changes above what is in view, from a live reload or rows added, does not move what is in view: the first row seen stays where it was
- A scroll area added at the end of a list it shows to the bottom, such as a log, stays at the bottom while it is there, and stays put once scrolled up
- Each page's scroll place is kept as it is left, and is there on going back to it, and between runs
- Resizing the window keeps the first row seen in place

#### Content scrolls under glass

- Content scrolls on under a glass toolbar or bar, and is seen through it, as the glass layer floats over it
- Where content meets the edge of glass, it softens and fades over 16 px, so words under it never clash with the bar's words
- At the top, with nothing scrolled under, the edge shows no fade

#### Scrolling stays at the frame rate

- A scroll is drawn at the screen's frame rate, 55 a second or more, with any amount of content
- Only the rows in view, and a screen's worth either side, are built; a list of 100,000 rows scrolls as a list of 100 does
- Scrolling never waits on loading: a row whose data is not yet there shows its place, and fills when it comes, off the UI thread
- Images and heavy rows that come into view draw without a stutter

#### Verification

- A window check sends its scrolls, presses and keys the way a pointer and a keyboard do
- It reads an area whose content fits: no bar, and a scroll moves nothing
- It sets each of macOS's "Show scroll bars" choices and reads the bar: floating and 7 px with no track, or 15 px beside the content with a track
- It scrolls and reads the bar: there at once; and 1 s on with no scroll: still there; and 1.4 s on: gone
- It moves the pointer over the bar's edge and reads the knob: 11 px, a track under it; it reads it 2 s on: still there
- It reads the knob's length against the room's share of the content, for a short and a very long content: in step, and never under 24 px
- It sends a slow trackpad swipe of 7 px over a list of 32 px rows and reads the place once still: moved 7 px, not on a row's edge
- It sends a trackpad swipe with speed and reads the place as it glides and once still: moving on, then stopped further than the swipe went
- It sends a swipe past the bottom and reads the place: past the end by no more than a third of the room; and 400 ms after the lift: at the end
- It sends a wheel notch at the bottom: no give
- It sends a down swipe with a little sideways drift over an area that scrolls both ways: no sideways move
- It sends Shift and the wheel: a sideways move
- It sends a swipe over an inner area until its end, without lifting: the outer area as before; then a new swipe: the outer area moved
- It sends an up swipe over a wide table: the page moved, the table as before
- It drags the knob halfway and reads the place: half the content; it drags off the window and back: no jump
- It drags the knob, sends Escape and reads the place: where the drag began
- It clicks the track with each of macOS's click choices, and with Option: a page, the spot clicked, and the other
- It holds a press on the track and reads the place 500 ms on: paged on until the knob is under the pointer, no further
- It sends Down, Page Down, Space, End and Home to a focused area and reads the place after each: a line, a page less a line, a page less a line, the bottom, the top
- It sends Tab to a control out of sight and reads its edges: in the room, 16 px clear
- It holds a drag 10 px from the bottom edge and reads the place over 500 ms: moving down
- It adds rows above what is in view and reads the first row seen: the same row, at the same place
- It leaves a page scrolled, goes elsewhere, comes back, and reads the place: as left; and again after a restart
- It scrolls content under the glass toolbar and reads the pixels under it: content seen, fading at the glass's edge
- With Reduce Motion on, it sends Page Down and reads the place 20 ms later: already a page on; it sends a glide into the end: no bounce
- It reads the knob's contrast over light and dark content: 3 or more
- It counts frames through three swipes and three glides over a 100,000 row list: 55 a second or more
- It counts rows built while a 100,000 row list scrolls: a screen's worth and the rows either side, never all

#### Decided

- On 2026-11-14, by the owner:
- Under Reduce Motion the edge still stretches under the fingers, with no bounce: chosen over a hard stop, and over the same bounce as with it off
- The scroll place is kept between runs, not only while the app is open
- A log stays at its newest line while it is at the bottom, and that is part of this requirement, not one of its own
- The sizes and times stand: a 7 px bar, 11 px under the pointer, 15 px when always shown, a fade after 1 s, 40 px a wheel notch
- No screen reader or VoiceOver support, as [the GUI requirements](#gui) say
- A change to macOS's scroll settings takes hold within 1 s, not at once: the app is not told of the change, and looks for it every 500 ms
- On 2026-11-14 the owner tried the reference by hand with a real trackpad, its swipes, glides, edges and bars, and found it good: what the window checks send as a trackpad's events holds for a real one

#### Ideas

- [Apple's scroll views guidance](https://developer.apple.com/design/human-interface-guidelines/scroll-views)
- A way to jump far, such as a letter index or a date strip beside a long list, is a new requirement
- Zoom by pinch in a scroll area is a new requirement

### Status bar at the bottom

### Message bar at the bottom

## Testing

Testing requires these rules. You are allowed to bypass these rules with user permission if you want to test a feature or a fix but these rules become a bottleneck.

### Tests muse be small and simple.

### Tests must run fast.

### Prefer combining small tests to test a feature or a fix rather than writing one big test.

### Long or time consuming tests must be clearly marked.

### Don't write or run tests that run multiple times. One run is enough unless explicitly asked by me.

### Perfer headless tests as much as possible

### Tests run only on generated, invented data. Never real data, never a copy of it.

### Automated checks only

- A new check is a unit test first; a check on the live window only when the behaviour needs it: layout, focus, drag, frames.
- An agent may open the app on invented data and drive it; it never opens the real data.
- A look, at a snapshot or a window, is a self-check while building and never verifies anything.
- To show the owner something live, an agent asks in one message: what to open, numbered steps, what to look for.

### A GUI app opened for automated testing launches in the background

When a GUI app is opened for an automated test or check, it is always launched in the background.

- It does not come to the front, and it does not take the keyboard or the pointer from what the owner is doing.

### The commit hook runs related tests only

The commit hook runs the tests related to the staged files, never the full suite.

### One command runs every test, in parallel, each suite in a clean room

- One regression command, run by hand only, runs every suite in parallel, each in a clean room: a new directory under `~/tmp` with a throwaway home, a scrubbed environment and fresh invented data.
- `--only` and `--skip` take suite names, `--only` also one test as `unit/NAME`; `--list` prints each test with its one-line description, `--plan` prints what would run, `--fail-fast` stops at the first failure.
- Timing checks run in a serial lane after the parallel suites; each suite has a fixed timeout, so the command always ends.
- It prints a table of suite, result, seconds and count, writes its timings to a file kept out of git, and exits 0, 1 on any failure, 2 on a usage error.

### Every test has a timeout

Every test has a timeout, so no test hangs a run.

- Over it, a test is stopped and reported as `timeout`; the tests after it still run.
- Each suite has a default; a test that needs longer says so where it is defined, in seconds.
- It holds however the test is run, and `--list` prints it; a test with none is a fault.

### planned: Deploy first, test alongside

An app may deploy before its full tests finish, when the rules below hold. It trades a short window of risk for speed.

- A quick check runs before each deploy, under 1 minute: the app builds, starts and serves its main screens
- The full tests then run in parallel, in a subagent, against a copy of that exact commit, never the moving working copy
- The report names the commit, the failed test and its first error line; it is queued for the main agent, who reads it at its next natural stop
- A failure stops the line: no deploy goes out until that commit's failure is fixed, and the last commit that passed is put back on the server
- The previous build is kept beside the new one, so putting it back takes one command and under 30 s
- A change that writes or migrates data never takes this path: it waits for its tests, then deploys
- Tests run on the development machine, never on the server

### planned: One session builds, test agents run alongside

The main session only builds; test runs happen in separate agents at the same time, so building never waits for tests. It works with [Deploy first, test alongside](#planned-deploy-first-test-alongside) and [Every test run logs its wall clock time](#planned-every-test-run-logs-its-wall-clock-time).

- Read only: a test agent tests a git worktree of one commit, never the working tree being edited, and changes no file of the project
- Newest first: while a run is going, new commits queue; the next run takes only the newest, except a commit that touches data-writing code, which always gets its own run
- Fast lane, slow lane: every run takes the fast suites; a slow suite (over 2 min, by the test times log) runs only when its own files change, and once a night
- A failure is run again once, on the same commit: pass then is a flake, logged and listed, and the line goes on; fail twice stops the line
- A test that flakes 3 times in 7 days is quarantined: it moves out of the line's run, is listed, and a requirement to fix it is written
- Reports wait for the main session's next prompt, never interrupt an edit; each names the commit, the test, its first error line and the log
- While the line is stopped, the main session may keep building, but nothing deploys; the first job of its next turn is the fix
- At most 2 test agents at once, so the machine stays usable

### planned: Every test run logs its wall clock time

Each test, and each whole run, writes how long it took by the wall clock. The log finds slow tests, shows slowdowns, and predicts how long a run will take.

- One file per project: `tmp/test-times.tsv`, never committed (`tmp/` is in `.gitignore`)
- TSV: tab-separated, one result a line; the first line names the columns:
  `at commit suite test result seconds passed failed timeout`
- `at` is ISO 8601 with its zone; `result` is pass, fail, timeout or run; `seconds` has 2 decimals
- One line per test, its last three columns empty; one line per run, with `run` as its test and result, and its counts filled in
- Readers find columns by the header's names, never by position, so a column can be added later without breaking them
- A field never holds a tab or a newline: the writer turns either into one space
- Lines are only ever added; the file is kept forever
- Before a run starts, it prints an estimate from past lines: the sum of each test's last 5 times, as "about 2 min 10 s"; a test with no past line counts its timeout
- After a run, a test that took more than 2 times its usual (the median of its last 5) gets a warning line naming it and both times; nothing fails
- A failed or timed-out test is logged like a passing one, so estimates stay honest
- The log is written by the one command that runs the tests (testing.org's "One command runs every test"), so every suite gets it without code of its own

Evidence: `tmp/` is already ignored in Arcadia; `date +%s.%N` or the test runner's own timer gives wall clock seconds; a TSV appends with one `printf` per line, and `awk -F'\t'` reads it.

## Docs

### Goals

- `docs/` is a book-style design doc and repo bible for this repository.
- Name the folder `docs/`; `doc/` is acceptable. Every path below assumes `docs/`.
- A software engineer who has never seen this repo can rebuild an equivalent project from `docs/` alone, without the source code.
- Every fact lives in exactly one place and can be reached from `docs/README.md`.
- It reads well on GitHub, on GitLab and in local editors, and exports to PDF and EPUB.
- Write for humans first.
- AI agents get a short section in the root `AGENTS.md` that points here.
- All documentation goes in `docs/`. Create it if it's missing. If it exists, build on it: keep what's correct, fix what's stale, fold in the rest.
- No secrets, tokens, personal data or internal hostnames. Document config keys, not their values.

### Requirements and the docs

When a repo has a requirements file, it says what must be true and how it is verified; the chapters say how the app works and why. Each links to the other and never restates it.

- What the user sees and does is written once, in its requirement.
- A chapter changes only when building a requirement changed how the app works or why.
- A requirement's `:SOURCE:` names its chapter; a check refuses a `:SOURCE:` or a chapter link that does not resolve.

### References

Official sources for the rules in this document.

| Read                                                                                                                                                                       | For                                                                   |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| [CommonMark spec](https://spec.commonmark.org/)                                                                                                                            | Base Markdown syntax                                                  |
| [GFM spec](https://github.github.com/gfm/)                                                                                                                                 | Tables, task lists, strikethrough, autolinks                          |
| [GitHub alerts](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts) | Callout syntax                                                        |
| [GitLab alerts](https://docs.gitlab.com/user/markdown/#alerts)                                                                                                             | How GitLab renders callouts                                           |
| [Mermaid docs](https://mermaid.js.org/intro/)                                                                                                                              | Diagram syntax                                                        |
| [Mermaid config schema](https://mermaid.js.org/config/schema-docs/config.html)                                                                                             | `htmlLabels` and theming                                              |
| [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli)                                                                                                                   | `mmdc` options: background, config file                               |
| [D2 tour](https://d2lang.com/tour/intro)                                                                                                                                   | D2 language                                                           |
| [D2 CLI manual](https://d2lang.com/tour/man/)                                                                                                                              | Flags, themes, layout engines                                         |
| [D2 layout engines](https://d2lang.com/tour/layouts/)                                                                                                                      | ELK, the fallback when TALA isn't available                           |
| [TALA layout engine](https://d2lang.com/tour/tala/)                                                                                                                        | What TALA supports: position locking, per-container direction, `near` |
| [TALA is open source](https://d2lang.com/blog/tala-is-open-source/)                                                                                                        | Bundled since D2 v0.9.0; seeds and trade-offs                         |
| [Graphviz docs](https://graphviz.org/documentation/)                                                                                                                       | DOT language, `dot -Tsvg`                                             |
| [librsvg](https://gitlab.gnome.org/GNOME/librsvg)                                                                                                                          | `rsvg-convert`, used to check diagram labels                          |
| [C4 model](https://c4model.com/)                                                                                                                                           | System context and container diagrams                                 |
| [MADR](https://adr.github.io/madr/)                                                                                                                                        | Decision record format                                                |
| [markdownlint-cli2](https://github.com/DavidAnson/markdownlint-cli2)                                                                                                       | Lint config and rules                                                 |
| [lychee](https://github.com/lycheeverse/lychee)                                                                                                                            | Link checking, including anchors                                      |
| [pandoc manual](https://pandoc.org/MANUAL.html)                                                                                                                            | `--file-scope`, `--pdf-engine`, GFM input                             |
| [Typst docs](https://typst.app/docs/)                                                                                                                                      | PDF engine for pandoc                                                 |
| [AGENTS.md](https://agents.md/)                                                                                                                                            | Agent instruction file format                                         |
| [Claude Code and AGENTS.md](https://code.claude.com/docs/en/memory#agents-md)                                                                                              | When Claude Code reads `AGENTS.md`, and the `@AGENTS.md` import       |

### Read, explore and research (write nothing yet)

1. Follow every URL in [References](#references) and read it.
2. Map the whole repo and read everything that defines behavior: code, config, build and CI files, tests, git history, existing docs and notes.
3. Research from official sources: current versions and docs of the repo's languages, frameworks and key dependencies, the external services and APIs it uses, and its domain terms. Also check whether anything in References has changed since this document was written.
4. Check for `d2` v0.9.0 or later (it bundles TALA), Mermaid CLI (`mmdc`, or `npx -p @mermaid-js/mermaid-cli mmdc`), `markdownlint-cli2`, `lychee` or another link checker, `pandoc` with a PDF engine such as `typst`, `rsvg-convert`, and Graphviz `dot` if you'll need it. For anything missing, note an install command; prefer no-install runners (`npx`, `uvx`).
5. List the docs and notes in the repo root, for the root-file decisions in [Outline](#outline-checkpoint).

If you can't reach the web or a URL, say which, use the closest official source, and note what you assumed.

### Outline (checkpoint)

Propose three lists:

- The chapter list: file name and one-line purpose.
- The diagram list: chapter, type, tool and what it shows.
- The root-file decisions: for each doc or note in the repo root, whether it stays, moves into `docs/` or is folded into a chapter.

Start from this skeleton.
Drop what doesn't apply, split what's too big (for example, one chapter per package in a monorepo), and never pad: a small repo may need four chapters.
Name chapters `NN-kebab-name.md`, numbered in reading order, for example `03-architecture.md`.
The cover is the one exception: it is `docs/README.md`.

| Chapter                 | Covers                                                                                                  |
| ----------------------- | ------------------------------------------------------------------------------------------------------- |
| Cover (`README.md`)     | What this is, reading order, conventions, how to render diagrams and run checks                         |
| Overview                | Problem, users, scope, non-goals, success criteria                                                      |
| Architecture            | System context and container diagrams, components, tech stack with versions and why                     |
| One per major component | Responsibility, interfaces, internals, failure modes                                                    |
| Data                    | Data model (ER diagram), schemas, invariants, storage, migrations                                       |
| Interfaces              | Exact contracts with examples: APIs, CLI, events, file formats, external services used                  |
| Behavior                | Key flows (sequence diagrams), state machines, algorithms in pseudocode, errors, edge cases             |
| UI, if any              | Screens, navigation map, layout rules                                                                   |
| Configuration           | Every config key and environment variable: type, default, effect                                        |
| Build, run, deploy      | Toolchain and dependency versions with their purpose, exact commands, deployment, operations            |
| Quality                 | Testing approach, acceptance criteria taken from the tests (given / when / then), performance, security |
| Decisions               | One ADR per significant decision: context, decision, alternatives, consequences                         |
| Rebuild guide           | Ordered milestones from an empty folder, each with the chapters it needs and how to verify it           |
| Glossary                | Domain terms                                                                                            |
| Open questions          | Unknowns awaiting an answer                                                                             |

Stop here and wait for approval before writing.

### Write

#### Content

- Rebuildable: specify behavior, contracts, data shapes, configuration, versions and decisions precisely enough to reimplement. Name the source paths a section describes, for maintainers, but never rely on them.
- Prefer a diagram, then a table, then a list. Use prose only for reasons and trade-offs, at most three sentences per paragraph.
- One fact, one place: state it once and link to it everywhere else. No previews, recaps or filler. The root `README.md` and `AGENTS.md` link into `docs/`; they never restate it.
- Don't re-teach third-party tools; link to their official docs.
- No implementation code. Signatures, schemas and examples are fine where they are the contract; prefer neutral forms (JSON Schema, OpenAPI, SQL DDL, pseudocode).
- Each chapter: H1 title, one-line purpose, body, then previous / next links.
- Mark a command or claim you could not verify with a `> [!WARNING]` alert that says "Unverified" and why.

#### Markdown

- GitHub Flavored Markdown: CommonMark plus tables, task lists, strikethrough and autolinks.
- Callouts only as GitHub alerts (`> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]`), never nested inside other blocks. GitHub, GitLab and pandoc understand them; elsewhere they degrade to plain quotes.
- No raw HTML, collapsible sections or embedded media: they break editors and print.
- Link between pages with relative paths. Keep tables to at most five columns so they fit a printed page.
- One sentence per line, for clean diffs; turn off markdownlint's line-length rule (MD013).

#### Diagrams

- Draw one wherever there's structure, flow, state or relationships. At minimum: system context, architecture, data model, and each key flow.
- Prefer D2 with the TALA layout engine for software architecture diagrams (system context, containers, components, deployment). TALA draws orthogonal, whiteboard-style layouts made for architecture, unlike DAG layouts that grow in one direction. Set it inside each source with `vars: { d2-config: { layout-engine: tala } }`; if TALA isn't available, use ELK and say so in a comment in that source.
- TALA can rearrange a whole diagram after a small edit. When a layout must stay recognizable across edits, lock key shapes with `top` and `left`.
- Mermaid for flowcharts, sequence, state, ER and class diagrams. Graphviz only for graphs a tool generates as DOT, such as dependency graphs.
- Sources live in `docs/diagrams/`, named `<chapter>-<name>.mmd`, `.d2` or `.dot`, where `<chapter>` is the chapter's `NN` prefix, for example `03-system-context.d2`. Commit the rendered `.svg` next to each source and embed it as an image whose alt text says what it shows.
- Render on an opaque white background, so diagrams print well and stay readable in dark mode. Set Mermaid's root-level `htmlLabels: false` (the per-diagram setting is deprecated): labels inside `<foreignObject>` vanish in editors, PDF and EPUB.
- Keep each diagram to about 15 nodes; split bigger ones.

#### Build script

Commit one POSIX shell script, `docs/build.sh`, pinning tool versions where the runner allows (for example `npx pkg@x.y.z`):

- `diagrams`: render every source in `docs/diagrams/` to SVG, with Mermaid settings in a committed `docs/diagrams/mermaid.json`.
- `check`: markdownlint, link check including anchors, and a full re-render that fails if any committed SVG differs from the fresh one. Fail on any error.
- `export`: PDF and EPUB of the whole book into `docs/_build/` (ignored via `docs/.gitignore`); run pandoc from inside `docs/` with `--file-scope` so cross-chapter links become internal anchors.

### AI instructions and root cleanup

1. Create or update the root `AGENTS.md` with this section, merged with any existing content rather than duplicating it:

   ```markdown
   ## Documentation

   - Read `docs/README.md` first; `docs/` is the design source of truth.
   - If a change affects behavior, interfaces, data, configuration or dependencies, update the affected chapters and diagram sources in the same change, then run `docs/build.sh diagrams` and `docs/build.sh check`.
   - Follow the conventions in `docs/README.md`. Link to facts; never restate them.
   ```

2. Existing agent-specific files (`CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, Cursor rules in `.cursor/rules/`) get a pointer to `AGENTS.md`, not copied rules. In `CLAUDE.md`, that's the line `@AGENTS.md`, because Claude Code reads `AGENTS.md` only when no `CLAUDE.md` exists. Don't create agent-specific files that aren't there.

3. Apply the approved root-file decisions from [Outline](#outline-checkpoint), and trim the root `README.md` to what the project is plus a link to `docs/README.md`.

### Verify (definition of done)

- [ ] `docs/build.sh diagrams` and `docs/build.sh check` pass.
- [ ] Every SVG still shows its labels when rasterized with `rsvg-convert`.
- [ ] Every diagram image has alt text that says what it shows.
- [ ] `docs/build.sh export` produces a PDF and an EPUB you have inspected: diagrams visible, callouts and links intact.
- [ ] Build, test and run commands in the docs were executed successfully, or are marked unverified. Never run deploys.
- [ ] No fact appears twice: scan for repeated sentences, lists and tables, including in the root `README.md` and `AGENTS.md`.
- [ ] No table has more than five columns.
- [ ] No secrets, tokens, personal data or internal hostnames anywhere in `docs/`.
- [ ] Every chapter is reachable from `docs/README.md`, and the previous / next links form one chain.
- [ ] The Rebuild guide's milestones each name the chapters they need, and those chapters hold enough to reimplement without the source.
- [ ] The root `AGENTS.md` has the Documentation section, and each existing agent-specific file points to it.

## Data

### Plain text data

- The data is plain text that an editor, command-line tools, git and agents can read and change without the app

### The file round-trips byte for byte

- A data file read and written back with no change is the same bytes; comments survive

### An edit touches only what it names

- Changing one field changes only that line; the other lines and the order of fields stay

### Unreadable file never saved over

- A bad line gives an error with its line number, never an empty state a save could write

### Every write is a plan

- Each write checks its precondition, writes atomically and returns its inverse, so undo can reverse it

### Undo and redo last the session

- They cover every change made since the app opened; a commit, from any tool, clears nothing
- Quitting the app ends the session and its undo list

### Stale writes refused

- A write whose file hash no longer matches writes nothing, and the app reloads the file

### One set of ranges

- The edit forms and the commit checks read the same table of allowed ranges, so a form never saves what a check rejects

### Ids are permanent

- A new record gets one above the highest id, and a gap in ids stays a gap

### Commits

- The app writes files; a human commits them
- Checks pass before anything is committed
- Refuse commit if data is broken

### Errors name no values

- An error names the record and field, never the value, so it is safe to print or log
- Bad: `Record 42: phone "98765 43210" is not a valid number`
- Good: `Record 42: field phone is not a valid number`

## CLI

### Help

- `-h` and `--help` are a hard rule: every CLI app has both, on the main command and on every subcommand.
  Usage line, what the app does, every option, one runnable example.
  Exit 0, and nothing else runs - a help call never writes, never starts a daemon, never asks a question.
  argparse's default `add_help` gives both, and gives them per subcommand; a script that parses options by hand has to handle the pair itself.
- `<program> help` is the long help, and `-h=/`–help= the short one - the split and what each carries live in [rules/docs.md](docs.md).
  argparse gives no `help` command: add `sub.add_parser("help")`, or test `sys.argv[1:2] =` ["help"]= before `parse_args`.
- A bare call prints the main help too, unless a bare call is itself a real command (`bookmark2` with no arguments opens its window).

### Flags

- Short flags are the optional half.
  The long flag is the default spelling, and a short alias goes in when a free letter exists: `--due|-d`, `--priority|-p`.
  A letter already taken in that app goes to the next free one; when none fits, the long flag stands alone.
- Commands that write accept `--dry-run` and then write nothing.

### Behaviour

- The CLI writes through the same code path as the GUI.
- Exit 0 on success, 1 on any refusal or failure, with `prog: <message>` on stderr.

### Checks

`harness/checks/cli_help.py` decides the hard half: a runnable - options or not, per [rules/docs.md](docs.md) - must handle `-h`, `--help` and a `help` command, and the finding names the ones that are missing.
Which letter a short flag takes, and how a subcommand's help reads, stay prose: this file.

## Privacy

### No personal data in code, tests, docs, logs or commit messages

Real details about real people never go into anything committed, shared or printed.
Use invented data instead.

| Where  | Bad                                    | Good                                                 |
| ------ | -------------------------------------- | ---------------------------------------------------- |
| Test   | `name = "Priya Raman"` (a real person) | `name = "Test Person 1"` (invented)                  |
| Log    | `Saved Priya Raman, phone 98765 43210` | `Saved record 42`                                    |
| Commit | `fix: Priya's birth date parsed wrong` | `fix: birth dates with a two-digit year parse wrong` |
| Docs   | A screenshot showing real records      | A screenshot of the example data                     |

## Axioms

One axiom per agent1 rule: accepted without proof, where every project starts.
A project's corollary names one in `:FOLLOWS:`. The rule's file holds its text.

### Browser and computer use

[Browser and computer use](browser.md)

### Docs

[Docs](docs.md)

### External systems and accounts

[External systems and accounts](external.md)

### Git

[Git](git.md)

### Harness

[Harness](harness.md)

### Jobs

[Jobs](jobs.md)

### macOS

[macOS](macos.md)

### Markdown

[Markdown](markdown.md)

### Parallel sessions

[Parallel sessions](parallel_sessions.md)

### Pi packages

[Pi packages](pi.md)

### Removal and uninstall

[Removal and uninstall](removal.md)

### Repos

[Repos](repos.md)

### Ruled out

[Ruled out](ruled_out.md)

### Scripts

[Scripts](scripts.md)

### Theme

[Theme](theme.md)

### Tools

[Tools](tools.md)

### TUI

[TUI](tui.md)

### Working style

[Working style](working_style.md)
