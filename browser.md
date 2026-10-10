# Browser and computer use

When you drive any application with browser use or computer use, maximize that window before you start, and keep it maximized until the work is done. That way the contents stay fully visible.

When you open a website, or a local HTML file in a browser, stop at the first installed browser in this order:

1. Firefox
2. Chrome
3. System default browser

Always open a tab in an existing window. Do not open a new window if that browser already has one. A first window is allowed only when the browser is not running.

macOS commands:

- Firefox: `/Applications/Firefox.app/Contents/MacOS/firefox -new-tab URL`
- Chrome, only if Firefox is missing: tell the front window to make a new tab. Create a window only when Chrome has zero windows.
- System default, only if both are missing: `open URL`

Do not use `-new-window`, `open -na`, or `open -a Firefox URL`. Those can spawn a window.

A window's frame is not the app's to set on this machine: AeroSpace and Rectangle manage windows, so an accessibility frame shows the tile, not what the code asked for. Verify geometry with `screencapture -o -l <windowid>` and check for a running tiler before blaming AppKit.
