---
name: test-cua-driver-with-freeform
metadata:
  scope: global
description: Smoke-test cua-driver on macOS by drawing a house (blue body, red roof, two yellow windows, brown door) on a new Apple Freeform board, then report which driver capabilities passed. Use when the user asks to test cua-driver, check that cua-driver still works, run the Freeform test, or draw a house in Freeform with cua-driver.
argument-hint: "[--background-only]"
---

# Test cua-driver with Freeform

Draw a house on a new Freeform board through cua-driver only, and report each
capability as pass or fail. Load the `cua-driver` skill first; its rules hold.

The house, in canvas order:

| Part    | Shape    | Fill       | How it gets its size          |
| ------- | -------- | ---------- | ----------------------------- |
| Body    | Square   | default    | default size                  |
| Roof    | Triangle | Maraschino | default size, nudged on top   |
| Door    | Square   | Mocha      | foreground drag of a handle   |
| Windows | Square   | Lemon      | foreground drag, then `cmd+d` |

## Helper

[scripts/cua_run.py](scripts/cua_run.py) wraps `cua-driver call`. Run
`cua_run.py help` for the full help. Three commands:

- `cua_run.py js FILE.js` runs a `run_script` file.
- `cua_run.py call TOOL JSON` calls one tool.
- `cua_run.py shot PID WID OUT.png` saves a window screenshot.

Write `.js` files and screenshots to the session scratchpad. Read every
screenshot with the Read tool; it is the only proof of canvas state.

## Facts this test relies on

Learned on cua-driver 0.38.0, macOS 26 (Darwin 25.5.0), 06 Nov 2026.

- Each `cua-driver call` is a new process. An `element_token` from one call
  is stale in the next. Inside `run_script`, target by `{role, name}`.
- `run_script` refuses `set_window_frame`, `invoke_menu`, `bring_to_front`.
  Call those with `cua_run.py call`.
- Screenshot pixels are the coordinate space for `x,y` and `drag`. The
  screenshot is smaller than the window in points; never convert by hand.
- A new shape lands at the viewport centre, selected, at a fixed canvas
  size. Zooming in before inserting does not make it smaller. When a shape
  already sits at the centre, the new one lands offset down and right
  (about 36 screenshot px at 100%). Read its position from a screenshot
  before nudging or dragging it.
- `shift+arrow` nudges the selection 10 pt, a plain arrow 1 pt. Both work in
  the background. At 100% zoom 10 pt is about 8 screenshot px.
- A background `drag` on a resize handle does nothing. Resizing needs
  `delivery_mode:"foreground"`, which moves the user's real pointer.
- Freeform has no size or position fields.
- Clicking an already selected shape enters text edit. `escape` leaves it
  and deselects.
- `invoke_menu` is refused while Freeform is in the background. After
  `bring_to_front` it works.
- `Format > Show Colours` opens a window titled `Colour Fill`. Its
  `AXRadioButton` pencils (`Mocha`, `Lemon`, `Maraschino`, ...) fill the
  selected shape.
- `cmd+d` duplicates the selection, offset down and right.
- The board window can land on another display. Check `list_windows`.
- The agent cursor overlay is one window covering the main display only
  (origin `0,0`). A window on another display gets no visible cursor, and
  `get_session` still says `cursor_visible:false` everywhere. Put Freeform on
  the main display, after asking: it covers what the user has there.
- `move_cursor` refuses with `screenshot_context_missing` unless the same
  process first read the window: call `get_window_state` in the same script.
- A session ends after 5 minutes idle, which an AskUserQuestion wait easily
  passes. Every later call is refused with `session has ended`. Run
  `start_session`, then set the cursor up again: its settings are per
  session.
- Another app can take focus back about a second after `bring_to_front`
  (Firefox did, while the user had it open). A foreground drag then only
  activates Freeform and resizes nothing. Call `bring_to_front` right before
  each foreground step; check focus with
  `osascript -e 'tell application "System Events" to get name of first process whose frontmost is true'` when a drag misses.
- The `Colour Fill` panel exists only while Freeform is active. Inactive, it
  is off screen and its pencils are unreadable: `bring_to_front` first.
- Background `cmd+a` selects nothing. To clear the board, click each shape
  (that selects it) and press `delete`.
- Keys the user types while Freeform is in front go into the selected shape
  as text. Ask the user to keep hands off the keyboard as well as the mouse
  during foreground steps. Remove stray text with a foreground
  `double_click`, `cmd+a`, `delete`, `escape`.
- A rejected or interrupted command may already have run. After one,
  screenshot before anything else; shapes can sit off view (a scrollbar
  shows it).

## Steps

### 0. Preflight

Run `cua-driver --version` and `cua-driver status`. Daemon down or
permissions missing: stop and report; do not grant permissions yourself.

Turn on the animated agent cursor so the user can watch, session
`freeform-test`:

```bash
cua_run.py call set_agent_cursor_enabled '{"enabled":true}'
cua_run.py call set_agent_cursor_theme \
  '{"theme_id":"cua.default","reduced_motion":"off"}'
cua_run.py call set_agent_cursor_motion '{"style":"comet_swoop",
  "timing":"deliberate","glide_duration_ms":0,"arc_size":0.4,
  "dwell_after_click_ms":250,"idle_hide_ms":0,"effects":{"glow":"on",
  "ripple":"on","squish":"on","trail":"on","magnet":"on"}}'
```

- `comet_swoop` is a wide arc with a trail. Other styles: `signature_arc`
  (default), `spring_settle`, `magnetic`, `adaptive`, `classic`.
- `deliberate` timing is slow enough to follow (450..1300 ms a move).
- `glide_duration_ms` must be 0: any other value fixes every move to that
  duration and flattens the style's own timing.
- `idle_hide_ms` 0 never hides the cursor; the maximum otherwise is 60000.
- `reduced_motion:"off"` keeps the animations even when macOS Reduce Motion
  is on; with it on, every move is a short straight glide with no effects.
- `cua-driver cursor-theme list` needs the `cua-cursor-theme` sidecar; when
  it is missing, `cua.default` is the only theme to rely on.

Tell the user the real mouse stays put in background steps; they watch the
agent cursor. Name the display the window is on.

### 1. New board, maximized

1. `launch_app` with `{"bundle_id":"com.apple.freeform"}`; note the pid.
2. In a script, click `{role:"AXButton", name:"New Board"}` on the Freeform
   window (`All Boards` or an open board; both have it). `list_windows` again: the same window id now carries
   the board title (`Untitled N`).
3. Maximize with `set_window_frame` to the main display's visible frame
   (`x:0`), so the agent cursor shows. A tiler
   or the Dock may shrink it; `effect:"unverifiable"` is fine if
   `list_windows` shows it filling the display.
4. Screenshot. Pass: empty dotted canvas.

### 2. Body and roof, background only

```js
const app = await cua.getApp({pid: PID, windowId: WID});
const insert = async (shape) => {
  await app.click({role: "AXMenuButton", name: "Insert Shape"});
  await cua.sleep(800);
  await app.click({role: "AXButton", name: shape});
  await cua.sleep(800);
};
await insert("Square");
await insert("Triangle");
for (let i = 0; i < 14; i++) {
  await cua.call("hotkey", {pid: PID, window_id: WID, keys: ["shift", "up"]});
  await cua.sleep(100);
}
return "ok";
```

14 nudges is 140 pt, about the square's height, if the triangle landed on
the square. It often lands offset (see Facts): screenshot, then nudge left
and up by the measured gap. Pass: triangle sits on the square with no gap and
no overlap; adjust with plain arrows.

With `--background-only`, stop here and report the rest as skipped.

### 3. Ask before foreground

Ask the user with AskUserQuestion: resizing the door and windows moves their
real mouse and brings Freeform forward, so hands off mouse and keyboard
until it finishes. Offer stop as the other option. No
yes, no foreground step. Then `bring_to_front` the board window.

### 4. Door

1. Insert a Square. Screenshot; read its handle positions.
2. `drag` with `delivery_mode:"foreground"` from the top-left handle inward,
   to about 30% of the side wide and 50% tall, anchored at the bottom-right.
3. Nudge it to the bottom centre of the body: `shift+left` steps, then plain
   `down` until its bottom meets the body's bottom.
4. `invoke_menu` `["Format","Show Colours"]`; `list_windows` for the
   `Colour Fill` window id; in a script click
   `{role:"AXRadioButton", name:"Mocha"}` on that window.
5. Screenshot. Pass: brown door, bottom centre.

### 5. Windows

1. Insert a Square. Foreground `drag` its bottom-right handle up-left to a
   small square, about 25% of the body side.
2. Nudge it into the body's top-left corner, about 12 px in from each edge.
3. Click `Lemon` in `Colour Fill`.
4. `hotkey` `cmd+d`, then nudge the copy to the mirror spot at top-right.
5. Screenshot. Pass: two yellow windows, level, clear of the door.

### 6. Roof colour

Click the roof's middle with a foreground click while nothing is selected,
then click `Maraschino`. If text edit opens instead, press `escape` and click
once more.

### 7. Clean up and verify

1. Foreground click empty canvas to deselect.
2. `invoke_menu` `["Format","Hide Colours"]`.
3. Final screenshot. Pass: red roof, blue body, two yellow windows, brown
   door, nothing selected.
4. Cursor tour: in one script, `move_cursor` with
   `target:{kind:"window",pid,window_id}` over roof, left window, right
   window, door, then empty canvas, `cua.sleep(700)` between. Read the points
   from the final screenshot. The real pointer does not move; the result
   text saying the app sees no hover is expected.
5. `end_session` for `freeform-test`. Never `cua-driver stop`.

Leave the board in place. Delete it or quit Freeform only if the user asks.

## Report

One table, one row per capability, then the final screenshot's absolute path.

| Capability                | Result |
| ------------------------- | ------ |
| launch_app                |        |
| AX click by role and name |        |
| set_window_frame          |        |
| background hotkey nudge   |        |
| background drag           |        |
| bring_to_front            |        |
| foreground drag           |        |
| invoke_menu               |        |
| click in a second window  |        |
| screenshot_out_file       |        |
| cursor theme and motion   |        |
| move_cursor tour          |        |
| cursor visible (user)     |        |

Background drag failing to resize is the known result, not a regression.
Record any other failure with its `refusal.code` or `summary` verbatim.
