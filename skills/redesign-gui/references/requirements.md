# Requirements

Every requirement applies to the mockups and to the code.

## 1. Proper desktop GUI app

Clear visual hierarchy, responsive resizing, and sensible empty, loading and
error states.

1. A themed in-app menu bar, drawn by the app, not the native OS menu, so it
   matches every theme.
2. On macOS, also fill the system menu bar with the same commands, because
   macOS always shows it.

## 2. Modern look

1. A current, modern desktop app, not a dated one: clean flat surfaces,
   subtle depth (soft shadows, layered surfaces) used sparingly, consistent
   rounded corners, a modern UI font.
2. Strong typographic hierarchy and plenty of whitespace do the work, not
   borders and boxes everywhere.
3. No dated styling: no bevels, heavy gradients, thick outlines, or crowded
   toolbars full of small icons.
4. One consistent, modern icon set with a single style and stroke weight.

## 3. Animations

1. Animations throughout make the app smooth and alive: opening and closing
   panels, dialogs and menus; switching, opening, closing and reordering
   tabs; list items added or removed; theme changes; hover and press
   feedback; loading and progress indicators.
2. Every animation has a purpose: it shows where something came from or
   went, what changed, or that the app is working. No decorative motion.
3. Fast: about 100-250 ms for most transitions, natural easing (ease-out
   entering, ease-in leaving). Nothing makes the user wait.
4. Animations never block input: typing, clicking and shortcuts keep working
   while one runs.
5. Smooth on macOS and Linux: 60 fps, no stutter or dropped frames, high-DPI
   screens included.
6. One shared set of motion tokens (durations and easing curves), like the
   spacing and color tokens.
7. Respect the OS reduce motion setting, and add an in-app setting to turn
   animations off or reduce them. Both replace motion with instant changes or
   simple fades.

## 4. Polish

1. Every interactive element has clear hover, pressed, focused, selected and
   disabled states, in every theme.
2. Empty states, loading states and error messages explain what happened and
   what to do next, in plain language.
3. No visual glitches: no flicker, layout jumps, clipped text or misaligned
   pixels at any size, scale or theme.

## 5. Comfort over density

A comfortable, calm layout over packing in as much as possible.

1. Generous spacing and padding, from the upper end of the spacing scale.
2. Interactive elements at least 32 px tall, never smaller than 24x24 px.
3. Readable text: base font size around 14-15 px, good line height, limited
   line length for long text.
4. Show only what the current task needs. Secondary information goes behind
   tabs, panels or disclosure toggles.
5. When some users need dense views, such as large tables, offer an optional
   compact mode. Comfortable is the default.

## 6. Consistency and alignment (high priority)

1. One spacing scale on a 4 px grid (4, 8, 12, 16, 24, 32). No one-off
   values.
2. Every element aligns to a shared layout grid: left edges, baselines and
   column widths line up across all screens.
3. One type scale (a small set of sizes and weights) and one icon size set,
   used the same way everywhere.
4. Each component (buttons, inputs, lists, dialogs, tabs) has one design and
   one set of sizes, reused on every screen. No slightly different copies.
5. The same action always looks and behaves the same: same label, icon,
   shortcut and position. Dialog buttons are always in the same order and
   place.
6. The same terms and capitalization style in the UI, the menus and the help.
7. Spacing, sizes and colors come only from design tokens. No hardcoded
   values in components.

## 7. Multiple windows and tabs

1. Multiple windows, each with its own set of tabs.
2. Standard actions with standard shortcuts: new window, new tab, close tab,
   close window, reopen closed tab, next and previous tab, jump to tab 1-9.
3. Tabs can be reordered, moved to another window, or moved into a new
   window, with the mouse (drag and drop) and with the keyboard.
4. Long tab titles truncate cleanly, with the full title in a tooltip. Many
   open tabs stay usable through scrolling or an overflow menu.
5. Closing a tab or window with unsaved work asks for confirmation.
6. Windows and tabs are restored on restart: size, position, open tabs, the
   active tab.
7. Settings such as theme and font size apply to all windows immediately.

## 8. Cross-platform: macOS and Linux

1. Works fully on macOS and Linux. On Linux, Wayland and X11, GNOME and KDE.
2. Each platform's conventions: Cmd on macOS and Ctrl on Linux, macOS
   shortcut labels (⌘ ⇧ ⌥) on macOS, the right window controls on each.
3. Settings and data in each platform's standard place:
   `~/Library/Application Support/` on macOS, XDG directories on Linux.
4. Platform-specific code lives in one small, clearly separated layer.
5. Every workflow is tested on both platforms.

## 9. Keyboard-only accessibility

Every feature can be reached and operated without a mouse.

1. Logical tab order and a clearly visible focus indicator.
2. Shortcuts for common actions, shown in menus and tooltips.
3. Keyboard switching between windows and tabs.
4. No keyboard traps. Esc closes dialogs and popovers.
5. WCAG 2.2 AA contrast for text and focus indicators in every theme.

## 10. Display and text scaling

1. Sharp rendering on high-DPI and Retina screens, and at OS scaling of
   125%, 150% and 200%.
2. An in-app font size setting that enlarges text without clipping or
   overlap, and keeps alignment intact. It persists across restarts.

## 11. Theming: 8 themes, 4 dark and 4 light

1. Required: Gruvbox Dark Hard (dark), Ayu Dark (dark), Ayu Light (light).
2. Propose the other 2 dark and 3 light themes in the mockup phase, for the
   user to approve or swap.
3. Follow each theme's official palette. When an official color fails AA
   contrast, adjust it as little as needed to pass, and list every change in
   the design system note.
4. Themes are built on design tokens (colors, spacing, typography): a new
   theme adds tokens only and changes no component.
5. Default to the OS light or dark setting, with a manual theme picker. The
   choice persists across restarts.

## 12. Built-in help, inside the app

1. Help shows inside the app, in its own panel, tab or window. It never opens
   an external browser or needs an internet connection.
2. Open it with F1 and from the Help menu, plus Cmd+? on macOS, the standard
   macOS help shortcut, since F1 needs the Fn key on most Mac keyboards.
3. Contextual: F1 opens the topic for the current screen or focused control.
4. Short inline hints and tooltips beside complex controls, linking to the
   full topic.
5. Searchable topics covering every feature and workflow.
6. Topics are Markdown files in a `help/` folder that the app loads, never
   text hardcoded in the UI.
7. A keyboard shortcut reference, opened with Ctrl+/ (Cmd+/ on macOS) from
   anywhere, or with `?` when no text field has focus. It shows the current
   platform's shortcuts.
8. A short getting-started guide on first launch, which can be dismissed and
   reopened from Help.
9. Help is fully keyboard-navigable, follows the active theme and font size,
   and uses the same components, spacing and terms as the rest of the app.
