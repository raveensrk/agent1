# Definition of done

The redesign is done when every box is ticked.

- [ ] The UI matches the approved mockups, and all 8 themes are implemented.
- [ ] The UI looks modern and polished: every interactive element has all its
  states, and there are no visual glitches.
- [ ] Animations match `docs/motion-spec.md`, run smoothly on both platforms,
  never block input, and respect reduce motion and the in-app setting.
- [ ] Layouts are comfortable, not dense, and meet the minimum control sizes.
- [ ] Every screen uses the shared grid, spacing scale, type scale and
  components, with no hardcoded spacing or color values in the code.
- [ ] Multiple windows and tabs work fully, moving tabs and restoring
  sessions included.
- [ ] Every workflow works on macOS and Linux, Wayland and X11.
- [ ] Every feature, help included, works end to end with the keyboard alone.
  The automated keyboard tests pass and the checklist is complete.
- [ ] Text stays readable and the layout holds at the largest font size and
  at 200% scaling.
- [ ] Help works inside the app, offline, and covers every feature.
- [ ] `docs/interface-contract.md` matches the final code, and the contract
  tests pass.
- [ ] Every new library is listed with a one-line reason.
- [ ] `docs/` holds the design brief, the final mockups, the keyboard map, the
  keyboard checklist, the motion spec, the interface contract, and a short
  design system note: tokens, spacing and layout grid, type scale, motion
  tokens, themes and every contrast adjustment, components, shortcuts,
  terminology, and the Laws of UX applied.
