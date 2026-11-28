# Publishing

agent1 builds two kinds of HTML: a book from every repo's docs folder, and one
shareable page of model and harness reviews.

## Books

The book publisher turns each repo's `docs/` into an HTML book in the GNU manual
style: one page per chapter, Next, Previous and Up links, and a local copy of
the gnu.org manual stylesheet. Books land in agent1's `books/` folder, which
git ignores, with an index page listing every book.

A docs folder in parts becomes a book in parts, in this order: Manual, Design,
Notes, then Rules and Prompts when those folders exist, as in agent1. A flat
docs folder becomes a one-part book. In each folder the contents page comes
first, then the other Markdown files by name - so numbered chapters read in
order - then subfolders the same way. A contents page that holds only its list
is skipped, and links to it go to the part's next chapter. The book title is
the first heading of the repo's root README.

Pandoc joins the chapters into one Texinfo file through a filter, and GNU
texi2any turns that into HTML. The filter makes headings into nodes with unique
names, turns links between chapters into cross references, copies images, and
draws Mermaid, D2 and Graphviz code blocks to SVG, cached by a hash of their
source. Links to files outside the docs folder become plain text; a link to a
`~/` or absolute path becomes code.

The first error stops the run: a link to a Markdown file in the docs folder
that is not a chapter, a link to a heading that does not exist, a missing image,
or a texi2any error. So a book that builds has no broken internal links.

A run can build every repo or only named ones; the list of books already built
is kept, so a partial run keeps the full index.

## The shareable page

One make target builds a single self-contained HTML page from the model and
harness reviews ([model_and_harness.yaml](../notes/model_and_harness.yaml)) with
pandoc, its own filter and stylesheet, then checks the result. The page includes
the model and harness reviews and leaves out model usage history.

______________________________________________________________________

[Previous: Install and uninstall](07_install_and_uninstall.md) · [Next: Decisions](09_decisions.md)
