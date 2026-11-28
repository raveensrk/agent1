# Publish the books

```bash
~/repos/agent1/script/publish_books          # every repo with a docs/ folder
~/repos/agent1/script/publish_books agent1   # only agent1
```

Open `~/repos/agent1/books/index.html`. The books folder is not committed. It
needs pandoc 3 and GNU texi2any 7 on the PATH, and mmdc, d2 and dot for
diagrams. A broken internal link stops the build with the file and link named;
fix it and run again. `publish_books help` has every option. How books are put
together is in [Publishing](../design/08_publishing.md).

## The shareable page

```bash
cd ~/repos/agent1 && make html
```

This needs pandoc and writes `dist/agent1.html`, one page of model and harness
reviews you can send to someone.

______________________________________________________________________

[Previous: Add a check](05_add_a_check.md) · [Next: Remove agent1](07_remove_agent1.md)
